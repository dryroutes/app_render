import streamlit as st
import requests
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

# ✅ Después de todos los imports, ya puedes usar st
st.set_page_config(layout="centered")
st.title("🚶‍♂️ Rutas seguras en Valencia (optimizado)")

# ✅ Solo aquí puedes ya usar session_state
if "grafo" not in st.session_state:
    st.session_state.grafo = None
    st.session_state.origen_coords = None
    st.session_state.destino_coords = None
    st.session_state.nodo1 = None
    st.session_state.nodo2 = None
    st.session_state.error = None


if st.button("Calcular ruta") and sel1 and sel2:
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

# Mostrar el mapa aunque se recargue la app
if st.session_state.grafo:
    G = st.session_state.grafo
    y1, x1 = st.session_state.origen_coords
    y2, x2 = st.session_state.destino_coords
    nodo1 = st.session_state.nodo1
    nodo2 = st.session_state.nodo2

    m = folium.Map(location=[(y1 + y2)/2, (x1 + x2)/2], zoom_start=14)

    for u, v in G.edges():
        lat1, lon1 = G.nodes[u]["y"], G.nodes[u]["x"]
        lat2, lon2 = G.nodes[v]["y"], G.nodes[v]["x"]
        folium.PolyLine([(lat1, lon1), (lat2, lon2)], color="lightgray", weight=1).add_to(m)

    folium.Marker([y1, x1], tooltip=reverse_geocode(y1, x1), icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([y2, x2], tooltip=reverse_geocode(y2, x2), icon=folium.Icon(color="red")).add_to(m)

    try:
        if nx.has_path(G, nodo1, nodo2):
            ruta = nx.shortest_path(G, nodo1, nodo2, weight="distancia")
        elif nx.has_path(G.to_undirected(), nodo1, nodo2):
            ruta = nx.shortest_path(G.to_undirected(), nodo1, nodo2, weight="distancia")
        else:
            ruta = None

        if ruta:
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in ruta]
            folium.PolyLine(coords, color="blue", weight=4).add_to(m)
            st.success(f"Ruta encontrada ({len(ruta)} nodos)")
        else:
            st.warning("No hay ruta posible entre los puntos.")
    except Exception as e:
        st.error(f"Error calculando ruta: {e}")

    st_folium(m, width=700, height=500)

elif st.session_state.error:
    st.error(st.session_state.error)
