import streamlit as st
import pandas as pd
from openai import OpenAI
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import time

# --- CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="CUMPLIMIENTOSV - Monitor AML", layout="wide")

# Cargar API Key desde Secrets
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ Configura la OPENAI_API_KEY en los Secrets de Streamlit.")
    st.stop()

# --- LÓGICA DE TU SCRIPT (Adaptada a Python) ---
FRASES_DELITO = [
    'lavado de dinero', 'narcotráfico', 'extorsión', 'enriquecimiento ilícito',
    'peculado', 'corrupción', 'estafa', 'evasión de impuestos', 'trata de personas',
    'agrupaciones ilícitas', 'soborno', 'malversación', 'fraude'
]

DEPARTAMENTOS = [
    'San Salvador', 'Santa Ana', 'San Miguel', 'La Libertad', 'Sonsonate',
    'Ahuachapán', 'Usulután', 'Chalatenango', 'La Paz', 'Cabañas',
    'Morazán', 'San Vicente', 'Cuscatlán', 'La Unión'
]

# --- FUNCIONES DE BÚSQUEDA ---
def buscar_noticias_historicas(fecha_inicio, fecha_fin):
    """
    Usa el buscador de Google News filtrando por rango de fechas exacto.
    """
    # Formato para Google: after:YYYY-MM-DD before:YYYY-MM-DD
    f_in = fecha_inicio.strftime('%Y-%m-%d')
    f_out = fecha_fin.strftime('%Y-%m-%d')
    
    # Construimos un query con los delitos principales de tu Art. 6
    query = f'site:laprensagrafica.com OR site:elsalvador.com OR site:diario.elmundo.sv after:{f_in} before:{f_out} ("{"\" OR \"".join(FRASES_DELITO[:5])}")'
    
    url = f"https://news.google.com/rss/search?q={query}&hl=es-419&gl=SV&ceid=SV:es-419"
    
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        noticias = []
        for item in root.findall('.//item')[:20]: # Limitamos a 20 para control de costos
            noticias.append({
                'titulo': item.find('title').text,
                'link': item.find('link').text,
                'fecha': item.find('pubDate').text
            })
        return noticias
    except Exception as e:
        st.error(f"Error al conectar con las fuentes: {e}")
        return []

def analizar_noticia_con_ia(titulo):
    """
    Usa OpenAI para extraer los campos que necesitas de forma estructurada.
    """
    prompt = f"""
    Eres un Oficial de Cumplimiento en El Salvador. Analiza este titular: "{titulo}"
    Extrae la información en formato JSON siguiendo el Art. 6 de la Ley de Lavado:
    {{
        "nombre": "Nombre de persona o empresa acusada/mencionada (Si no hay, 'Desconocido')",
        "delito": "Tipo de delito detectado",
        "ciudad": "Departamento o ciudad de El Salvador (Si no dice, 'No especificado')",
        "es_relevante": true/false (solo si es un delito de lavado, activos o generador)
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except:
        return None

# --- UI PRINCIPAL ---
st.title("🏦 CUMPLIMIENTOSV - Sistema de Monitoreo AML")
st.subheader("Búsqueda por Periodos de Fecha (Art. 6)")

with st.expander("⚙️ Filtros de Período", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha Inicial", datetime.now() - timedelta(days=30))
    with col2:
        fecha_fin = st.date_input("Fecha Final", datetime.now())

if st.button("🚀 Iniciar Monitoreo por Fechas"):
    with st.spinner(f"Escaneando medios desde {fecha_inicio} hasta {fecha_fin}..."):
        noticias_raw = buscar_noticias_historicas(fecha_inicio, fecha_fin)
        
        if not noticias_raw:
            st.warning("No se encontraron noticias en este rango de fechas con esas palabras clave.")
        else:
            resultados = []
            barra_progreso = st.progress(0)
            
            for i, n in enumerate(noticias_raw):
                # Análisis con IA
                analisis_json = analizar_noticia_con_ia(n['titulo'])
                if analisis_json:
                    import json
                    data = json.loads(analisis_json)
                    
                    if data.get("es_relevante"):
                        resultados.append({
                            "Fecha Noticia": n['fecha'],
                            "Nombre (Sujeto)": data['nombre'],
                            "Título de la Noticia": n['titulo'],
                            "Delito": data['delito'],
                            "Departamento/Ciudad": data['ciudad'],
                            "Link": n['link']
                        })
                barra_progreso.progress((i + 1) / len(noticias_raw))

            if resultados:
                df = pd.DataFrame(resultados)
                st.success(f"Se encontraron {len(df)} hallazgos relevantes para cumplimiento.")
                
                # Previsualización
                st.dataframe(df, use_container_width=True)

                # Exportación
                col_ex1, col_ex2 = st.columns(2)
                with col_ex1:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("📊 Exportar a Excel (CSV)", csv, f"Reporte_AML_{fecha_inicio}.csv", "text/csv")
                
                with col_ex2:
                    st.info("Para PDF: Usa el botón de imprimir de tu navegador y guarda como PDF.")
            else:
                st.info("Se encontraron noticias, pero la IA determinó que ninguna aplica al Art. 6 (ej. noticias viales o deportes).")
