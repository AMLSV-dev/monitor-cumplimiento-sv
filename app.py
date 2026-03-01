import streamlit as st
import pandas as pd
from openai import OpenAI
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
import json
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CUMPLIMIENTOSV - Pro v9.5", layout="wide")

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ Falta API Key en Secrets.")
    st.stop()

# --- FUNCIONES TÉCNICAS ---

def limpiar_url(url_google):
    """Sigue la redirección de Google para obtener el link original corto"""
    try:
        response = requests.get(url_google, timeout=5, allow_redirects=True)
        return response.url.split('?')[0] # Retorna la URL limpia sin parámetros
    except:
        return url_google # Si falla, devuelve la original

def buscar_noticias(f_inicio, f_fina):
    # Dorks específicos para FGR y medios de El Salvador
    fuentes = [
        "site:fiscalia.gob.sv/sala-de-prensa",
        "site:pnc.gob.sv",
        "site:laprensagrafica.com",
        "site:elsalvador.com",
        "site:diario.elmundo.sv"
    ]
    
    delitos = '("lavado de dinero" OR "extorsión" OR "corrupción" OR "peculado" OR "estafa")'
    query = f"{delitos} ({' OR '.join(fuentes)}) after:{f_inicio} before:{f_fina}"
    
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=SV&ceid=SV:es-419"
    
    try:
        res = requests.get(rss_url, timeout=10)
        root = ET.fromstring(res.content)
        noticias = []
        for item in root.findall('.//item')[:15]: # Limitamos para rapidez
            noticias.append({
                'titulo': item.find('title').text,
                'link_google': item.find('link').text,
                'fecha': item.find('pubDate').text
            })
        return noticias
    except:
        return []

def analizar_ia(titulo):
    prompt = f"""
    Analiza este titular de El Salvador: "{titulo}"
    Extrae la información para cumplimiento AML:
    1. Nombre completo de la persona o empresa acusada (Sé preciso).
    2. Departamento o Ciudad donde ocurrió.
    3. Delito exacto según Art. 6.
    
    Responde solo JSON:
    {{"nombre": "...", "lugar": "...", "delito": "...", "es_delito_art6": true/false}}
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
st.title("🏦 CUMPLIMIENTOSV - Sala de Prensa FGR & PNC")
st.markdown("Auditoría de medios con limpieza de enlaces y detección de nombres.")

col1, col2 = st.columns(2)
with col1:
    f_i = st.date_input("Desde", value=None)
with col2:
    f_f = st.date_input("Hasta", value=None)

if st.button("🚀 Ejecutar Monitoreo Avanzado"):
    if not f_i or not f_f:
        st.warning("Selecciona el rango de fechas.")
    else:
        with st.spinner("Buscando y limpiando enlaces oficiales..."):
            items = buscar_noticias(f_i, f_f)
            
            if not items:
                st.info("No se hallaron resultados.")
            else:
                final_rows = []
                prog = st.progress(0)
                
                for i, item in enumerate(items):
                    # 1. Análisis de IA para extraer nombre y lugar
                    info = analizar_ia(item['titulo'])
                    
                    if info and info['es_delito_art6']:
                        # 2. LIMPIEZA DE LINK (Aquí se quita el link largo de Google)
                        link_limpio = limpiar_url(item['link_google'])
                        
                        final_rows.append({
                            "Nombre (Natural/Jurídica)": info['nombre'],
                            "Título de la Noticia": item['titulo'],
                            "Departamento/Ciudad": info['lugar'],
                            "Link de la Noticia": link_limpio
                        })
                    prog.progress((i + 1) / len(items))

                if final_rows:
                    df = pd.DataFrame(final_rows)
                    st.success(f"Se encontraron {len(df)} registros validados.")
                    
                    # Previsualización solicitada
                    st.dataframe(df, use_container_width=True)

                    # Exportación a Excel
                    csv = df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 Descargar Reporte Excel", csv, "Reporte_AML_SV.csv", "text/csv")
                else:
                    st.info("No se encontraron delitos relevantes en este periodo.")
