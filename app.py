import streamlit as st
import pandas as pd
from openai import OpenAI
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# 1. Configuración de Claves
# Aquí el usuario pondrá su clave de OpenAI en la interfaz lateral
st.sidebar.title("Configuración")
api_key = st.sidebar.text_input("Ingresa tu OpenAI API Key", type="password")

if api_key:
    client = OpenAI(api_key=api_key)

# 2. Definición de Delitos Art. 6 (Para que la IA sepa qué buscar)
DELITOS_ART6 = "Narcotráfico, extorsión, secuestro, trata de personas, corrupción, peculado, soborno, enriquecimiento ilícito, evasión de impuestos, tráfico de armas."

# 3. Función para buscar noticias (Uso de RSS de Google News - GRATIS)
def buscar_noticias(query):
    url = f"https://news.google.com/rss/search?q={query}+when:30d&hl=es-419&gl=SV&ceid=SV:es-419"
    response = requests.get(url)
    root = ET.fromstring(response.content)
    articles = []
    for item in root.findall('.//item')[:10]: # Limitamos a 10 para ahorrar tokens inicialmente
        articles.append({
            'title': item.find('title').text,
            'link': item.find('link').text,
            'pubDate': item.find('pubDate').text
        })
    return articles

# 4. Función de Inteligencia Artificial
def analizar_con_ia(titular):
    prompt = f"""
    Actúa como un Oficial de Cumplimiento en El Salvador. 
    Analiza este titular de noticia: "{titular}"
    
    Extrae la información en este formato exacto de lista:
    Nombre: (Nombre de la persona o empresa mencionada como sospechosa/acusada)
    Delito: (Relaciónalo con uno de estos: {DELITOS_ART6})
    Ubicación: (Departamento o Ciudad de El Salvador mencionado)
    
    Si no hay un nombre claro o no es un delito del Art. 6, escribe "IGNORAR".
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", # El más barato y rápido
        messages=[{"role": "system", "content": "Eres un experto legal salvadoreño."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- INTERFAZ DE USUARIO ---
st.title("🇸🇻 Monitor de Lavado de Dinero (Art. 6)")
st.markdown("Busca noticias negativas para Debida Diligencia en El Salvador.")

busqueda = st.text_input("Nombre del cliente o empresa a investigar:")
btn_buscar = st.button("Iniciar Auditoría")

if btn_buscar and api_key:
    with st.spinner('Buscando en medios salvadoreños y analizando con IA...'):
        noticias = buscar_noticias(busqueda)
        resultados_finales = []

        for n in noticias:
            analisis = analizar_con_ia(n['title'])
            
            if "IGNORAR" not in analisis:
                # Procesar el texto de la IA para la tabla
                lineas = analisis.split('\n')
                res_dict = {
                    "Nombre": lineas[0].replace("Nombre: ", ""),
                    "Delito": lineas[1].replace("Delito: ", ""),
                    "Departamento/Ciudad": lineas[2].replace("Ubicación: ", ""),
                    "Título de la Noticia": n['title'],
                    "Link": n['link']
                }
                resultados_finales.append(res_dict)

        if resultados_finales:
            df = pd.DataFrame(resultados_finales)
            st.success(f"Se encontraron {len(df)} posibles coincidencias.")
            
            # Previsualización
            st.table(df)

            # Exportación a Excel
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exportar Reporte para Expediente (CSV)",
                data=csv,
                file_name=f"Cumplimiento_{busqueda}.csv",
                mime="text/csv"
            )
        else:
            st.info("No se hallaron registros negativos vinculados a delitos del Art. 6.")
elif btn_buscar and not api_key:
    st.error("Por favor, ingresa tu API Key de OpenAI en la barra lateral.")
