import streamlit as st
import networkx as nx
import json
import os
import folium
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

# Función auxiliar para calcular distancia entre coordenadas
def distancia_coords(lat1, lon1, lat2, lon2):
    R = 6371000  # radio Tierra en metros
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Carga mínima para solo buscar el nodo más cercano
def cargar_nodos():
    nodos = []
    for archivo in os.listdir("grafo/nodos"):
        with open(f"grafo/nodos/{archivo}") as f:
            nodos.extend(json.load(f))
    return nodos

# Buscar nodo más cercano a coordenadas
def nodo_mas_cercano(lat, lon, nodos):
    min_dist = float("inf")
    nodo_cercano = None
    for n in nodos:
        dist = distancia_coords(lat, lon, n["y"], n["x"])
        if dist < min_dist:
            min_dist = dist
            nodo_cercano = n["id"]
    return nodo_cercano

# Cargar solo subgrafo local
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
    return G

st.title("🚶‍♂️ Calculador de rutas sobre el grafo por dirección")

geolocator = Nominatim(user_agent="grafo_app")
direccion1 = st.text_input("Dirección de origen", placeholder="Calle X, Valencia")
direccion2 = st.text_input("Dirección de destino", placeholder="Calle Y, Valencia")

if st.button("Calcular ruta"):
    try:
        location1 = geolocator.geocode(direccion1 + ", Valencia, España")
        location2 = geolocator.geocode(direccion2 + ", Valencia, España")

        if not location1 or not location2:
            st.error("No se pudieron encontrar las direcciones.")
        else:
            nodos = cargar_nodos()
            nodo1 = nodo_mas_cercano(location1.latitude, location1.longitude, nodos)
            nodo2 = nodo_mas_cercano(location2.latitude, location2.longitude, nodos)

            G = cargar_subgrafo(nodo1, nodo2)

            camino = nx.shortest_path(G, nodo1, nodo2, weight="distancia")
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in camino]

            m = folium.Map(location=coords[0], zoom_start=15)
            folium.Marker(coords[0], tooltip="Origen", icon=folium.Icon(color="green")).add_to(m)
            folium.Marker(coords[-1], tooltip="Destino", icon=folium.Icon(color="red")).add_to(m)
            folium.PolyLine(coords, color="blue", weight=4).add_to(m)

            st.success(f"Ruta de {len(camino)} nodos encontrada.")
            st_folium(m, width=700, height=500)

    except Exception as e:
        st.error(f"Error calculando la ruta: {e}")
