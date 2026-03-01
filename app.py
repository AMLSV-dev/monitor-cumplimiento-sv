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

def resolver_url_real(url_google):
    """Sigue el link de Google para obtener la fuente real y el nombre del sitio"""
    try:
        res = requests.get(url_google, timeout=5, allow_redirects=True)
        url_final = res.url.split('?')[0]
        dominio = urlparse(url_final).netloc.replace('www.', '')
        
        # Mapeo de nombres cortos
        fuentes = {
            'fiscalia.gob.sv': 'FGR',
            'pnc.gob.sv': 'PNC',
            'laprensagrafica.com': 'LPG',
            'elsalvador.com': 'EDH',
            'diario.elmundo.sv': 'EL MUNDO',
            'x.com': 'X (Twitter)',
            'twitter.com': 'X (Twitter)'
        }
        nombre_sitio = fuentes.get(dominio, dominio.upper())
        return url_final, nombre_sitio
    except:
        return url_google, "FUENTE EXTERNA"

def buscar_noticias(f_i, f_f):
    # Query basado en Art. 6 - Amplio para no restringir
    terminos = '("lavado de dinero" OR "extorsión" OR "corrupción" OR "peculado" OR "enriquecimiento ilícito" OR "estafa" OR "narcotráfico")'
    fuentes = "site:fiscalia.gob.sv OR site:pnc.gob.sv OR site:laprensagrafica.com OR site:elsalvador.com OR site:diario.elmundo.sv"
    
    query = f"{terminos} ({fuentes}) after:{f_i} before:{f_f}"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=SV&ceid=SV:es-419"
    
    try:
        res = requests.get(rss_url, timeout=10)
        root = ET.fromstring(res.content)
        noticias = []
        for item in root.findall('.//item')[:30]:
            # Validación de fecha del RSS
            fecha_str = item.find('pubDate').text
            fecha_dt = datetime.strptime(fecha_str, '%a, %d %b %Y %H:%M:%S %Z')
            
            # Solo incluir si está en el rango solicitado
            if f_i <= fecha_dt.date() <= f_f:
                noticias.append({
                    'titulo': item.find('title').text,
                    'link_google': item.find('link').text,
                    'fecha': fecha_dt.strftime('%d/%m/%Y')
                })
        return noticias
    except:
        return []

def analizar_ia_nombres(titulo):
    """IA estricta para nombres de personas o empresas"""
    prompt = f"""
    Analiza este titular de noticia de El Salvador: "{titulo}"
    Extrae la información para cumplimiento legal:
    1. Nombre Propio: (Busca nombres de personas reales o nombres de empresas. Si el titular solo dice 'Pandilleros' pero no da nombres, pon 'No determinado').
    2. Departamento: (Ej. San Salvador, Santa Ana, etc).
    3. Delito: (Basado en el Art. 6 de la Ley de Lavado).
    
    Responde en JSON:
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

# --- INTERFAZ ---
st.title("🏦 CUMPLIMIENTOSV")

c1, c2, c3 = st.columns([0.25, 0.25, 0.5])
with c1:
    f_inicio = st.date_input("Desde", format="DD/MM/YYYY")
with c2:
    f_fin = st.date_input("Hasta", format="DD/MM/YYYY")
with c3:
    st.write("")
    st.write("")
    ejecutar = st.button("🚀")

if ejecutar:
    with st.spinner("Analizando y resolviendo enlaces reales..."):
        noticias = buscar_noticias(f_inicio, f_fin)
        
        if not noticias:
            st.info("No se hallaron noticias en el periodo exacto.")
        else:
            final_data = []
            for n in noticias:
                info = analizar_ia_nombres(n['titulo'])
                if info:
                    # Resolvemos la URL de Google para tener el sitio real
                    url_real, nombre_sitio = resolver_url_real(n['link_google'])
                    
                    final_data.append({
                        "Fecha": n['fecha'],
                        "Nombre (Persona/Empresa)": info['nombre'],
                        "Título de la Noticia": n['titulo'],
                        "Departamento/Ciudad": info['lugar'],
                        "Sitio": nombre_sitio,
                        "URL": url_real
                    })

            if final_data:
                df = pd.DataFrame(final_data)
                
                # Visualización
                st.dataframe(
                    df,
                    column_config={
                        "URL": st.column_config.LinkColumn("Link de la Noticia", display_text="Ver noticia"),
                        "Fecha": st.column_config.TextColumn("Fecha", width="small")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Descarga
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Descargar Reporte Excel", csv, f"Reporte_{f_inicio}.csv", "text/csv")
            else:
                st.info("No se encontraron nombres o delitos relevantes en los resultados.")
