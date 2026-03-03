import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
from pyproj import Transformer

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="EMT Madrid Storytelling", layout="wide")

@st.cache_data
def load_data():
    url = "https://datos.madrid.es/dataset/900023-0-emt-paradas-autobus/resource/900023-0-emt-paradas-autobus/download/900023-0-emt-paradas-autobus.csv"
    response = requests.get(url)
    df = pd.read_csv(io.StringIO(response.content.decode('latin-1')), sep=',')
    
    # Limpieza de nombres de columnas
    df.columns = df.columns.str.strip()
    col_x = 'posX' if 'posX' in df.columns else 'POSX'
    col_y = 'posY' if 'posY' in df.columns else 'POSY'

    # Transformación de coordenadas Bonus
    transformer = Transformer.from_crs("epsg:23030", "epsg:4326", always_xy=True)
    df['latitud_corregida'], df['longitud_corregida'] = zip(*df.apply(
        lambda row: transformer.transform(row[col_x], row[col_y])[::-1], axis=1))
    return df

df = load_data()
VEL_MEDIA = 216 # metros/minuto

st.title("Storytelling: La Red de Autobuses de Madrid")
st.markdown("---")

# Se añaden las pestañas corregidas
tab0, tab1, tab2, tab3 = st.tabs(["Introducción", "Vista General", "Análisis por Línea", "Diccionario"])

# --- TAB 0: INTRODUCCIÓN ---
with tab0:
    # Encabezado con logo y título
    col_izq, col_der = st.columns([3, 1])
    
    with col_izq:
        st.header("Dashboard de paradas de autobuses de Madrid")
    with col_der:
        st.image("logo_emt.png")    

    st.markdown(f"""
    **Asignatura:** Visualización de datos  
    **Alumno:** Miguel González Lavín (201911481) - 2ºA MITT+MBD  
    **Curso:** 2025/2026
    
    ---
    
    ### Contexto del Proyecto
    Esta aplicación ha sido desarrollada como proyecto final para la asignatura de **Visualización de datos**. El propósito fundamental es transformar datos brutos de transporte público en información accionable y comprensible, permitiendo a cualquier usuario investigar la estructura y eficiencia de la red de autobuses de Madrid (EMT).
    
    El análisis se centra en la **infraestructura física** (paradas, distancias y coordenadas), permitiendo identificar patrones de densidad y entender cómo se distribuyen los kilómetros de servicio a lo largo de la capital.
    
    ### Metodología y Datos
    Los datos se consumen en **tiempo real** directamente desde el Portal de Datos Abiertos del Ayuntamiento de Madrid. Esto asegura que la información visualizada corresponda a la red vigente en el momento de la consulta:
    
    * **Fuente:** [Portal de Datos Abiertos - Ayuntamiento de Madrid](https://datos.madrid.es/dataset/900023-0-emt-paradas-autobus/resource/900023-0-emt-paradas-autobus)
    * **Procesamiento Técnico:** Debido a que las coordenadas originales se encuentran en formato **ED50 / UTM zone 30N (EPSG:23030)**, el sistema realiza una transformación automática mediante la librería `pyproj` al estándar **WGS84 (EPSG:4326)** para permitir su correcta representación en mapas interactivos de Folium.
    """)

    col_izq_img, col_centro_img, col_der_img = st.columns([1, 4, 1])

    with col_centro_img:
        st.image("imagen_emt_link.png", caption="Red de Transporte Público de Madrid")

    st.markdown("---")

    col_desc1, col_desc2 = st.columns(2)
    
    with col_desc1:
        st.subheader("Análisis Macro (Global)")
        st.write("""
        En la pestaña **Vista General**, el enfoque es el conjunto de la red. 
        * **Métricas Core:** Visualización rápida del tamaño total de la red en kilómetros y tiempo medio de trayecto entre paradas.
        * **Densidad:** Un mapa de calor que revela las zonas de Madrid con mayor concentración de infraestructura.
        * **Jerarquía:** Uso de Treemaps para entender qué destinos finales (cabeceras) absorben la mayor parte del flujo de la red.
        """)

    with col_desc2:
        st.subheader("Análisis Micro (Líneas)")
        st.write("""
        En la pestaña **Análisis por Línea**, el dashboard permite "hacer zoom" en cada servicio individual.
        * **Itinerarios:** Mapeo punto a punto de la línea seleccionada con clusters de paradas.
        * **Dinámica de Tramos:** Gráficos que comparan la distancia entre paradas consecutivas para detectar tramos largos o zonas de alta frecuencia de paradas.
        * **Crecimiento:** Un análisis acumulativo de la longitud de la línea según el orden de sus paradas.
        """)

    st.info("""
    **Nota técnica:** Para los cálculos de tiempo estimado, se utiliza una velocidad media de 13 km/h (216 m/min), 
    basada en los estándares de movilidad urbana para tráfico mixto en grandes ciudades.
    """)

# --- TAB 1: VISTA GENERAL (CORREGIDA) ---
with tab1:
    st.header("Análisis Global de la Red")
    
    # KPIs Globales (se mantienen igual)
    col1, col2, col3, col4, col5 = st.columns(5)
    total_lineas = df['line'].nunique()
    total_paradas = len(df)
    longitud_red_km = df.groupby(['line', 'sentido'])['distancia'].max().sum() / 1000
    dist_media_global = df.groupby(['line', 'sentido'])['distancia'].diff().mean()
    tiempo_medio_global = dist_media_global / VEL_MEDIA

    col1.metric("Nº Líneas", f"{total_lineas}")
    col2.metric("Longitud Red", f"{longitud_red_km:,.0f} km")
    col3.metric("Total Paradas", f"{total_paradas:,}")
    col4.metric("Dist. Media", f"{dist_media_global:.0f} m")
    col5.metric("Tiempo Medio", f"{tiempo_medio_global:.1f} min")

    st.divider()
    
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("Densidad Geográfica de Paradas")
        # Creamos el objeto mapa base
        m_heat = folium.Map(location=[40.4167, -3.7033], zoom_start=11, tiles="OpenStreetMap")
        
        # Preparamos los datos: solo lat y lon, eliminando nulos
        data_heat = df[['latitud_corregida', 'longitud_corregida']].dropna().values.tolist()
        
        # Añadimos el HeatMap con parámetros de optimización
        HeatMap(data_heat, radius=10, blur=15, min_opacity=0.5).add_to(m_heat)
        
        # Renderizado con clave única y dimensiones controladas
        st_folium(m_heat, width=700, height=450, key="global_heatmap_fixed")
        
    with col_right:
        st.subheader("Top 10 Líneas con más Paradas")
        top_10 = df['line'].value_counts().head(10).reset_index()
        top_10.columns = ['Línea', 'Num_Paradas']
        top_10['Línea'] = top_10['Línea'].astype(str) 
        
        fig_top = px.bar(top_10, x='Línea', y='Num_Paradas', color='Num_Paradas', 
                         color_continuous_scale="Viridis", text='Num_Paradas')
        
        fig_top.update_layout(
            xaxis={'type': 'category', 'categoryorder': 'total descending'}, 
            showlegend=False, 
            height=450,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_top, use_container_width=True)

    st.divider()

    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Análisis de Complejidad")
        df_complejidad = df.groupby('line').agg({'secuencia': 'max', 'distancia': 'max'}).reset_index()
        fig_scatter = px.scatter(df_complejidad, x="distancia", y="secuencia", 
                                 hover_name="line", trendline="ols",
                                 labels={'distancia': 'Longitud (m)', 'secuencia': 'Total Paradas'},
                                 color="distancia", color_continuous_scale="Portland")
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col_b:
        st.subheader("Jerarquía de Destinos Finales")
        fig7 = px.treemap(df.head(1500), path=['nameTo', 'line'], values='distancia',
                          color='distancia', color_continuous_scale='Blues')
        st.plotly_chart(fig7, use_container_width=True)

# --- TAB 2: ANÁLISIS POR LÍNEA ---
with tab2:
    st.sidebar.header("Control de Datos")
    linea_sel = st.sidebar.selectbox("Selecciona Línea:", sorted(df['line'].unique()))
    sentido_sel = st.sidebar.radio("Sentido de trayecto:", [1, 2], captions=["Ida", "Vuelta"])
    
    df_linea = df[(df['line'] == linea_sel) & (df['sentido'] == sentido_sel)].sort_values('secuencia')
    
    st.header(f"Detalle Operativo: Línea {linea_sel}")

    k1, k2, k3, k4 = st.columns(4)
    paradas_linea = len(df_linea)
    long_linea_km = df_linea['distancia'].max() / 1000
    dist_media_linea = df_linea['distancia'].diff().mean()
    tiempo_medio_linea = dist_media_linea / VEL_MEDIA

    k1.metric("Paradas", f"{paradas_linea}")
    k2.metric("Longitud", f"{long_linea_km:.2f} km")
    k3.metric("Dist. Media", f"{dist_media_linea:.0f} m")
    k4.metric("Tiempo Estimado", f"{tiempo_medio_linea:.1f} min/parada")

    st.divider()

    col_map, col_table = st.columns([2, 1])
    with col_map:
        st.subheader("Itinerario Geográfico")
        m_linea = folium.Map(location=[df_linea['latitud_corregida'].mean(), 
                                      df_linea['longitud_corregida'].mean()], zoom_start=13)
        mc = MarkerCluster().add_to(m_linea)
        for _, r in df_linea.iterrows():
            folium.Marker([r['latitud_corregida'], r['longitud_corregida']], 
                          popup=f"P{r['secuencia']}: {r['descparada']}").add_to(mc)
        st_folium(m_linea, width=750, height=400, key="line_map")

    with col_table:
        st.subheader("Lista de Paradas")
        st.dataframe(df_linea[['secuencia', 'descparada']].rename(
            columns={'secuencia':'Orden', 'descparada':'Nombre'}), 
            use_container_width=True, hide_index=True, height=400)

    st.divider()
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("Distancia entre Paradas (Tramos)")
        df_linea['salto'] = df_linea['distancia'].diff().fillna(0)
        fig_saltos = px.bar(df_linea, x="secuencia", y="salto", color="salto",
                            labels={'salto':'Metros', 'secuencia':'Nº Parada'})
        st.plotly_chart(fig_saltos, use_container_width=True)
        
    with col_g2:
        st.subheader("Crecimiento Kilométrico")
        fig_acc = px.area(df_linea, x="secuencia", y="distancia", color_discrete_sequence=['#4CB391'])
        st.plotly_chart(fig_acc, use_container_width=True)

# --- TAB 3: DICCIONARIO ---
with tab3:
    st.header("Glosario y Metadatos")
    st.table(pd.DataFrame({
        "Variable": ["line", "secuencia", "distancia", "sentido", "latitud_corregida"],
        "Definición": [
            "ID de línea EMT", 
            "Orden de parada", 
            "Metros acumulados", 
            "1: Ida / 2: Vuelta", 
            "Transformación WGS84 vía pyproj"
        ]
    }))