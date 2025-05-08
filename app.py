import streamlit as st
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium

# Cargar grafo completo desde archivos JSON
@st.cache_resource
def cargar_grafo():
    G = nx.DiGraph()
    for archivo in os.listdir("grafo/nodos"):
        with open(f"grafo/nodos/{archivo}") as f:
            nodos = json.load(f)
            for n in nodos:
                G.add_node(n["id"], x=n["x"], y=n["y"])

    for archivo in os.listdir("grafo/aristas"):
        with open(f"grafo/aristas/{archivo}") as f:
            aristas = json.load(f)
            for a in aristas:
                G.add_edge(
                    a["origen"], a["destino"],
                    distancia=a["distancia"],
                    tiempo=a["tiempo"],
                    costo=a["costo_total"],
                    altura=a["altura_media"]
                )
    return G

G = cargar_grafo()

# UI de Streamlit
st.title("🚶‍♂️ Calculador de rutas sobre el grafo")

nodos = list(G.nodes)
op_origen = st.selectbox("Selecciona nodo de origen", nodos)
op_destino = st.selectbox("Selecciona nodo de destino", nodos)

# Calcular y mostrar ruta
if st.button("Calcular ruta"):
    try:
        camino = nx.shortest_path(G, op_origen, op_destino, weight="distancia")
        coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in camino]

        # Crear mapa
        m = folium.Map(location=coords[0], zoom_start=14)
        folium.Marker(coords[0], tooltip="Origen", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(coords[-1], tooltip="Destino", icon=folium.Icon(color="red")).add_to(m)
        folium.PolyLine(coords, color="blue", weight=5).add_to(m)

        st.success(f"Ruta calculada con {len(camino)} nodos.")
        st_folium(m, width=700, height=500)

    except Exception as e:
        st.error(f"No se pudo calcular la ruta: {e}")
