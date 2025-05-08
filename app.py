import streamlit as st
import requests
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

st.set_page_config(layout="centered")
st.title("🚶‍♂️ Calculador de rutas sobre el grafo por dirección (con autocompletado)")

# ----------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------

def distancia_coords(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def cargar_nodos():
    nodos = []
    for archivo in os.listdir("grafo/nodos"):
        with open(f"grafo/nodos/{archivo}") as f:
            nodos.extend(json.load(f))
    return nodos

def nodo_mas_cercano(lat, lon, nodos):
    min_dist = float("inf")
    nodo_cercano = None
    for n in nodos:
        dist = distancia_coords(lat, lon, n["y"], n["x"])
        if dist < min_dist:
            min_dist = dist
            nodo_cercano = n["id"]
    return nodo_cercano

def cargar_subgrafo(nodo1, nodo2, radio_m=500):
    nodos_deseados = set()
    todos_nodos = []
    for archivo in os.listdir("grafo/nodos"):
        with open(f"grafo/nodos/{archivo}") as f:
            todos_nodos.extend(json.load(f))
    id_coords = {n["id"]: (n["y"], n["x"]) for n in todos_nodos}

    lat1, lon1 = id_coords[nodo1]
    lat2, lon2 = id_coords[nodo2]

    for n in todos_nodos:
        lat, lon = n["y"], n["x"]
        if (distancia_coords(lat1, lon1, lat, lon) < radio_m or
            distancia_coords(lat2, lon2, lat, lon) < radio_m):
            nodos_deseados.add(n["id"])

    G = nx.DiGraph()
    for n_id in nodos_deseados:
        lat, lon = id_coords[n_id]
        G.add_node(n_id, y=lat, x=lon)

    for archivo in os.listdir("grafo/aristas"):
        with open(f"grafo/aristas/{archivo}") as f:
            aristas = json.load(f)
            for a in aristas:
                if a["origen"] in nodos_deseados and a["destino"] in nodos_deseados:
                    G.add_edge(
                        a["origen"], a["destino"],
                        distancia=a["distancia"],
                        tiempo=a["tiempo"],
                        costo=a["costo_total"],
                        altura=a["altura_media"]
                    )
    return G, id_coords

# ----------------------------------------------------
# AUTOCOMPLETADO USANDO PHOTON
# ----------------------------------------------------

def buscar_direcciones(query):
    try:
        url = f"https://photon.komoot.io/api/?q={query}, Valencia, España&limit=5"
        r = requests.get(url, timeout=4)
        resultados = r.json()["features"]
        opciones = []
        for res in resultados:
            nombre = res["properties"].get("name", "")
            calle = res["properties"].get("street", "")
            ciudad = res["properties"].get("city", "")
            label = f"{nombre or calle}, {ciudad}".strip(", ")
            coords = res["geometry"]["coordinates"]
            opciones.append((label, coords[1], coords[0]))  # (nombre, lat, lon)
        return opciones
    except Exception as e:
        return []

# ----------------------------------------------------
# UI DE STREAMLIT
# ----------------------------------------------------

st.subheader("Dirección de origen:")
query_origen = st.text_input("Buscar origen", key="origen_input")
opciones_origen = buscar_direcciones(query_origen) if query_origen else []

origen_seleccionado = st.selectbox("Elige una dirección de origen", opciones_origen, format_func=lambda x: x[0]) if opciones_origen else None

st.subheader("Dirección de destino:")
query_destino = st.text_input("Buscar destino", key="destino_input")
opciones_destino = buscar_direcciones(query_destino) if query_destino else []

destino_seleccionado = st.selectbox("Elige una dirección de destino", opciones_destino, format_func=lambda x: x[0]) if opciones_destino else None
# ... (todo lo anterior igual: imports, funciones auxiliares, autocompletado)
# Inicializar variables en la sesión
if "grafo" not in st.session_state:
    st.session_state.grafo = None
    st.session_state.lat1 = None
    st.session_state.lat2 = None
    st.session_state.lon1 = None
    st.session_state.lon2 = None
    st.session_state.id1 = None
    st.session_state.id2 = None
    st.session_state.error = None

# Cuando se pulsa el botón, se guarda el estado
if st.button("Calcular ruta") and origen_seleccionado and destino_seleccionado:
    try:
        lat1, lon1 = origen_seleccionado[1], origen_seleccionado[2]
        lat2, lon2 = destino_seleccionado[1], destino_seleccionado[2]

        nodos = cargar_nodos()
        id1 = nodo_mas_cercano(lat1, lon1, nodos)
        id2 = nodo_mas_cercano(lat2, lon2, nodos)

        G, id_coords = cargar_subgrafo(id1, id2)

        st.session_state.grafo = G
        st.session_state.lat1 = lat1
        st.session_state.lon1 = lon1
        st.session_state.lat2 = lat2
        st.session_state.lon2 = lon2
        st.session_state.id1 = id1
        st.session_state.id2 = id2
        st.session_state.error = None

    except Exception as e:
        st.session_state.error = f"Error calculando: {e}"

# Mostrar el mapa si ya hay grafo en la sesión
if st.session_state.grafo:
    G = st.session_state.grafo
    lat1 = st.session_state.lat1
    lon1 = st.session_state.lon1
    lat2 = st.session_state.lat2
    lon2 = st.session_state.lon2
    id1 = st.session_state.id1
    id2 = st.session_state.id2

    m = folium.Map(location=[(lat1+lat2)/2, (lon1+lon2)/2], zoom_start=15)

    for n in G.nodes():
        y, x = G.nodes[n]["y"], G.nodes[n]["x"]
        folium.CircleMarker(location=[y, x], radius=2, color="gray", fill=True, fill_opacity=0.3).add_to(m)

    for u, v in G.edges():
        y1, x1 = G.nodes[u]["y"], G.nodes[u]["x"]
        y2, x2 = G.nodes[v]["y"], G.nodes[v]["x"]
        folium.PolyLine(locations=[(y1, x1), (y2, x2)], color="lightgray", weight=1).add_to(m)

    folium.Marker([lat1, lon1], tooltip="Origen", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([lat2, lon2], tooltip="Destino", icon=folium.Icon(color="red")).add_to(m)

    try:
        ruta = nx.shortest_path(G, id1, id2, weight="distancia")
        coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in ruta]
        folium.PolyLine(coords, color="blue", weight=4).add_to(m)
        st.success(f"Ruta de {len(ruta)} nodos.")
    except nx.NetworkXNoPath:
        st.warning("No hay ruta entre los puntos seleccionados.")

    st_folium(m, width=700, height=500)

elif st.session_state.error:
    st.error(st.session_state.error)
