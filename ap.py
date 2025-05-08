import streamlit as st
import requests
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

st.set_page_config(layout="centered")
st.title("🚶‍♂️ Rutas seguras en Valencia (optimizado)")

# Inicialización segura del estado
for key in ["grafo", "origen_coords", "destino_coords", "nodo1", "nodo2", "error", "nodos"]:
    if key not in st.session_state:
        st.session_state[key] = None

# --- FUNCIONES AUXILIARES ---

@st.cache_data
def cargar_nodos():
    nodos = []
    for archivo in os.listdir("grafo/nodos"):
        if archivo.endswith(".json"):
            with open(f"grafo/nodos/{archivo}") as f:
                nodos.extend(json.load(f))
    return nodos

def distancia_coords(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def nodo_mas_cercano(lat, lon, nodos):
    return min(nodos, key=lambda n: distancia_coords(lat, lon, n["y"], n["x"]))["id"]

def reverse_geocode(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=17&addressdetails=0"
        headers = {"User-Agent": "grafo-app"}
        r = requests.get(url, headers=headers, timeout=4)
        return r.json().get("display_name", "Ubicación desconocida")
    except:
        return "Ubicación desconocida"

def buscar_direcciones(query):
    try:
        url = f"https://photon.komoot.io/api/?q={query}, Valencia, España&limit=5"
        r = requests.get(url, timeout=4)
        resultados = r.json()["features"]
        return [(res["properties"].get("name", "") + ", " + res["properties"].get("city", ""),
                 res["geometry"]["coordinates"][1], res["geometry"]["coordinates"][0]) for res in resultados]
    except:
        return []

def cargar_subgrafo(nodo1, nodo2, base_radio=500):
    nodos_deseados = set()
    todos_nodos = st.session_state.nodos
    id_coords = {n["id"]: (n["y"], n["x"]) for n in todos_nodos}

    lat1, lon1 = id_coords[nodo1]
    lat2, lon2 = id_coords[nodo2]

    # Calcular distancia entre origen y destino
    d = distancia_coords(lat1, lon1, lat2, lon2)

    # Ajustar radio dinámicamente: mitad de la distancia + margen
    radio = int(d / 2 + 800)
    st.info(f"🔄 Cargando subgrafo con radio ~{radio} m para conectar los puntos...")

    for n in todos_nodos:
        lat, lon = n["y"], n["x"]
        if (distancia_coords(lat1, lon1, lat, lon) < radio or
            distancia_coords(lat2, lon2, lat, lon) < radio):
            nodos_deseados.add(n["id"])

    G = nx.DiGraph()
    for n_id in nodos_deseados:
        lat, lon = id_coords[n_id]
        G.add_node(n_id, y=lat, x=lon)

    for archivo in os.listdir("grafo/aristas"):
        if archivo.endswith(".json"):
            with open(f"grafo/aristas/{archivo}") as f:
                for a in json.load(f):
                    if a["origen"] in nodos_deseados and a["destino"] in nodos_deseados:
                        G.add_edge(
                            a["origen"], a["destino"],
                            distancia=a["distancia"],
                            tiempo=a["tiempo"],
                            costo=a["costo_total"],
                            altura=a["altura_media"]
                        )
    return G, id_coords

# --- INTERFAZ STREAMLIT ---

if st.session_state.nodos is None:
    st.session_state.nodos = cargar_nodos()

query1 = st.text_input("📍 Dirección de origen")
opc1 = buscar_direcciones(query1) if query1 else []
sel1 = st.selectbox("Selecciona origen", opc1, format_func=lambda x: x[0]) if opc1 else None

query2 = st.text_input("🎯 Dirección de destino")
opc2 = buscar_direcciones(query2) if query2 else []
sel2 = st.selectbox("Selecciona destino", opc2, format_func=lambda x: x[0]) if opc2 else None

if st.button("Calcular ruta"):
    if not sel1 or not sel2:
        st.warning("Selecciona ambas direcciones en los desplegables.")
        st.stop()
    try:
        lat1, lon1 = sel1[1], sel1[2]
        lat2, lon2 = sel2[1], sel2[2]
        nodo1 = nodo_mas_cercano(lat1, lon1, st.session_state.nodos)
        nodo2 = nodo_mas_cercano(lat2, lon2, st.session_state.nodos)
        G, id_coords = cargar_subgrafo(nodo1, nodo2)

        st.session_state.grafo = G
        st.session_state.origen_coords = (G.nodes[nodo1]["y"], G.nodes[nodo1]["x"])
        st.session_state.destino_coords = (G.nodes[nodo2]["y"], G.nodes[nodo2]["x"])
        st.session_state.nodo1 = nodo1
        st.session_state.nodo2 = nodo2
        st.session_state.error = None
    except Exception as e:
        st.session_state.grafo = None
        st.session_state.error = str(e)

# --- VISUALIZACIÓN DE MAPA Y RESULTADOS ---

if st.session_state.grafo and st.session_state.origen_coords and st.session_state.destino_coords:
    G = st.session_state.grafo
    y1, x1 = st.session_state.origen_coords
    y2, x2 = st.session_state.destino_coords
    nodo1 = st.session_state.nodo1
    nodo2 = st.session_state.nodo2

    m = folium.Map(location=[(y1 + y2)/2, (x1 + x2)/2], zoom_start=14)


    folium.Marker([y1, x1], tooltip=reverse_geocode(y1, x1), icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([y2, x2], tooltip=reverse_geocode(y2, x2), icon=folium.Icon(color="red")).add_to(m)

    try:
        ruta = None
        modo = "dirigido"

        if nx.has_path(G, nodo1, nodo2):
            ruta = nx.shortest_path(G, nodo1, nodo2, weight="distancia")
        elif nx.has_path(G.to_undirected(), nodo1, nodo2):
            ruta = nx.shortest_path(G.to_undirected(), nodo1, nodo2, weight="distancia")
            modo = "no dirigido"

        if ruta:
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in ruta]
            folium.PolyLine(coords, color="blue", weight=4).add_to(m)

            distancia_total = sum(G[u][v].get("distancia", 0) for u, v in zip(ruta[:-1], ruta[1:]))
            tiempo_total = sum(G[u][v].get("tiempo", 0) for u, v in zip(ruta[:-1], ruta[1:]))
            aristas_riesgo = sum(1 for u, v in zip(ruta[:-1], ruta[1:]) if G[u][v].get("altura", 0) > 0)
            nodos_riesgo = sum(1 for n in ruta if G.nodes[n].get("altura", 0) > 0)

            st.success(f"Ruta encontrada ({len(ruta)} nodos, modo {modo})")
            st.markdown(f"📏 Distancia total: **{distancia_total:.1f} m**")
            st.markdown(f"⏱️ Tiempo estimado: **{tiempo_total:.2f} min**")
            st.markdown(f"⚠️ Aristas con riesgo: **{aristas_riesgo}**")
            st.markdown(f"⚠️ Nodos con riesgo: **{nodos_riesgo}**")

            if modo == "no dirigido":
                st.warning("⚠️ Se ha usado modo *no dirigido*. La ruta puede no respetar el sentido real de las calles.")
        else:
            st.warning("No hay ruta posible entre los puntos.")
    except Exception as e:
        st.error(f"Error calculando ruta: {e}")

    st_folium(m, use_container_width=True, height=550)

elif st.session_state.error:
    st.error(st.session_state.error)
