import streamlit as st
import pandas as pd
from openai import OpenAI
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
import json
from urllib.parse import urlparse

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CUMPLIMIENTOSV", layout="wide")

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("Configura la API Key en Secrets.")
    st.stop()

# --- FUNCIONES TÉCNICAS ---

def obtener_nombre_sitio(url):
    """Extrae un nombre amigable del dominio"""
    dominios = {
        'fiscalia.gob.sv': 'FGR',
        'pnc.gob.sv': 'PNC',
        'laprensagrafica.com': 'LPG',
        'elsalvador.com': 'EDH',
        'diario.elmundo.sv': 'MUNDO',
        'x.com': 'X (Twitter)',
        'twitter.com': 'X (Twitter)',
        'facebook.com': 'Facebook',
        'lapagina.com.sv': 'LA PÁGINA',
        'ultimahora.sv': 'ÚLTIMA HORA'
    }
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    return dominios.get(domain, domain.upper())

def buscar_noticias_ampliado(f_i, f_f):
    # Lista expandida basada en tu referencia
    terminos = '("lavado de dinero" OR "extorsión" OR "corrupción" OR "peculado" OR "MS-13" OR "Pandilla" OR "Mara" OR "Enriquecimiento ilícito" OR "Testaferro" OR "Estafa")'
    fuentes = "site:fiscalia.gob.sv OR site:pnc.gob.sv OR site:laprensagrafica.com OR site:elsalvador.com OR site:diario.elmundo.sv OR site:x.com OR site:facebook.com"
    
    query = f"{terminos} ({fuentes}) after:{f_i} before:{f_f}"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=SV&ceid=SV:es-419"
    
    try:
        res = requests.get(rss_url, timeout=10)
        root = ET.fromstring(res.content)
        noticias = []
        for item in root.findall('.//item')[:40]: # Aumentado a 40 resultados
            noticias.append({
                'titulo': item.find('title').text,
                'link': item.find('link').text,
                'fecha': item.find('pubDate').text
            })
        return noticias
    except:
        return []

def analizar_ia_flexible(titulo):
    """IA menos restrictiva para capturar más hallazgos"""
    prompt = f"""
    Analiza este titular: "{titulo}"
    Extrae:
    1. Sujeto (Persona, Empresa o grupo criminal como MS-13/18).
    2. Ciudad/Dpto de El Salvador.
    3. Delito (Basado en Art 6).
    
    Responde JSON:
    {{"nombre": "...", "lugar": "...", "delito": "..."}}
    """
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content)
    except:
        return None

# --- INTERFAZ COMPACTA ---
st.title("🏦 CUMPLIMIENTOSV")

# Fechas juntas y formato DD/MM/AAAA
c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
with c1:
    f_inicio = st.date_input("Desde", format="DD/MM/YYYY")
with c2:
    f_fin = st.date_input("Hasta", format="DD/MM/YYYY")
with c3:
    st.write(" ") # Espaciador
    ejecutar = st.button("🚀")

if ejecutar:
    with st.spinner("Buscando..."):
        noticias = buscar_noticias_ampliado(f_inicio, f_fin)
        
        if not noticias:
            st.info("Sin resultados.")
        else:
            datos_finales = []
            for n in noticias:
                info = analizar_ia_flexible(n['titulo'])
                if info:
                    # Obtenemos nombre del sitio y link
                    nombre_sitio = obtener_nombre_sitio(n['link'])
                    
                    datos_finales.append({
                        "Nombre (Natural/Jurídica)": info['nombre'],
                        "Título de la Noticia": n['titulo'],
                        "Departamento/Ciudad": info['lugar'],
                        "Sitio": nombre_sitio,
                        "URL": n['link']
                    })

            if datos_finales:
                df = pd.DataFrame(datos_finales)
                
                # Configuración de tabla para que el link sea el nombre del sitio
                st.dataframe(
                    df,
                    column_config={
                        "URL": st.column_config.LinkColumn(
                            "Link de la Noticia",
                            help="Haz clic para ver la fuente",
                            validate="^http",
                            display_text="Ver noticia" # O podrías usar df['Sitio']
                        ),
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Botón de descarga
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Descargar Excel", csv, "Reporte.csv", "text/csv")
            else:
                st.info("No se hallaron delitos críticos.")
