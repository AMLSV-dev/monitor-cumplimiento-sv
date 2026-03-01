import streamlit as st
import pandas as pd
from openai import OpenAI
import requests
import xml.etree.ElementTree as ET

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Intentar obtener la llave desde los Secrets de Streamlit
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    # Si no hay Secrets, mostrar el cuadro en la barra lateral
    api_key = st.sidebar.text_input("Ingresa tu OpenAI API Key", type="password")

# Solo inicializar el cliente si hay una llave
if api_key:
    client = OpenAI(api_key=api_key)
else:
    st.warning("⚠️ Falta la API Key. Por favor, configúrala en los Secrets de Streamlit o en la barra lateral.")
    st.stop()

# --- LÓGICA DE BÚSQUEDA ---
st.title("🇸🇻 Monitor de Lavado de Dinero (Art. 6)")
st.markdown("Herramienta de cumplimiento para Debida Diligencia en El Salvador.")

busqueda = st.text_input("Nombre del cliente o empresa a investigar:")
btn_buscar = st.button("Iniciar Auditoría")

# Función para buscar noticias (Google News RSS)
def buscar_noticias(query):
    # Buscamos noticias de los últimos 30 días en El Salvador
    url = f"https://news.google.com/rss/search?q={query}+when:30d&hl=es-419&gl=SV&ceid=SV:es-419"
    try:
        response = requests.get(url)
        root = ET.fromstring(response.content)
        return [{'title': item.find('title').text, 'link': item.find('link').text} for item in root.findall('.//item')[:10]]
    except:
        return []

if btn_buscar and busqueda:
    with st.spinner('Consultando medios salvadoreños y analizando con IA...'):
        noticias = buscar_noticias(busqueda)
        
        if not noticias:
            st.info("No se encontraron noticias recientes para este nombre.")
        else:
            resultados = []
            for n in noticias:
                # Llamada a la IA para clasificar según Art. 6
                prompt = f"Analiza si este titular de El Salvador menciona delitos de lavado, corrupción, extorsión o narcotráfico: '{n['title']}'. Si es positivo, extrae: Nombre, Delito y Ciudad. Si es negativo, responde: 'IGNORAR'."
                
                try:
                    chat_completion = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    respuesta = chat_completion.choices[0].message.content
                    
                    if "IGNORAR" not in respuesta.upper():
                        resultados.append({
                            "Hallazgo": respuesta,
                            "Noticia Original": n['title'],
                            "Enlace": n['link']
                        })
                except Exception as e:
                    st.error(f"Error de OpenAI: {e}")
                    st.stop()

            if resultados:
                df = pd.DataFrame(resultados)
                st.success("✅ Hallazgos encontrados:")
                st.table(df)
                
                # Exportación
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Reporte Excel", csv, "reporte_cumplimiento.csv", "text/csv")
            else:
                st.success("No se encontraron coincidencias negativas con los delitos del Art. 6.")
