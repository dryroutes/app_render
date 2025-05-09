import streamlit as st
import requests
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

st.set_page_config(layout="wide")
st.title("🚶‍♂️ Rutas seguras en Valencia")

st.markdown("""
<div style="background-color:#f0f0f5; padding:10px; border-radius:8px; margin-bottom:20px; color:#222;">
    <strong>🗕️ Predicción meteorológica para el 8 de mayo de 2025 (Valencia):</strong><br>
    ☁️ <em>Nublado con intervalos soleados</em><br>
    🌡️ Temperatura media: <strong>22 °C</strong><br>
    🌬️ Viento moderado del este: <strong>20 km/h</strong><br>
    🌧️ Probabilidad de precipitación: <strong>10%</strong>
</div>
""", unsafe_allow_html=True)

criterio = st.selectbox(
    "🔎 ¿Qué criterio deseas optimizar para la ruta segura?",
    options={
        "distancia": "Ruta más corta (distancia)",
        "tiempo": "Ruta más rápida (tiempo)",
        "altura": "Ruta menos expuesta al agua (altura de inundación)",
        "costo_total": "Ruta con menor riesgo estimado (riesgo)"
    },
    format_func=lambda x: {
        "distancia": "Ruta más corta (distancia)",
        "tiempo": "Ruta más rápida (tiempo)",
        "altura": "Ruta menos expuesta al agua (altura de inundación)",
        "costo_total": "Ruta con menor riesgo estimado (riesgo)"
    }[x]
)

for key in ["grafo", "origen_coords", "destino_coords", "nodo1", "nodo2", "error", "nodos"]:
    if key not in st.session_state:
        st.session_state[key] = None

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

def cargar_subgrafo(nodo1, nodo2):
    nodos_deseados = set()
    todos_nodos = st.session_state.nodos
    id_coords = {n["id"]: (n["y"], n["x"]) for n in todos_nodos}

    lat1, lon1 = id_coords[nodo1]
    lat2, lon2 = id_coords[nodo2]
    d = distancia_coords(lat1, lon1, lat2, lon2)
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
                            costo_total=a["costo_total"],
                            altura=a["altura_media"]
                        )
    return G, id_coords

def cargar_recursos():
    with open("datos/servicios_emergencia_provincia_valencia.json") as f1, \
         open("datos/incidencias_valencia_2025-05-09.json") as f2, \
         open("datos/parkings_valencia_binario.json") as f3:
        emergencia = json.load(f1)
        incidencias = json.load(f2)
        parkings = json.load(f3)
    return emergencia, incidencias, parkings

def penalizar_riesgo(G, emergencia, incidencias):
    for u, v, data in G.edges(data=True):
        if data.get("altura", 0) > 0:
            y, x = G.nodes[u]["y"], G.nodes[u]["x"]
            for recurso in emergencia + incidencias:
                ry = recurso.get("latitud", recurso.get("lat"))
                rx = recurso.get("longitud", recurso.get("lng"))
                if distancia_coords(y, x, ry, rx) < 150:
                    for k in ["distancia", "tiempo", "costo_total", "altura"]:
                        if k in data:
                            data[k] *= 2
                    break

def parking_cercano(y_dest, x_dest, parkings):
    return min(parkings, key=lambda p: distancia_coords(y_dest, x_dest, p["lat"], p["lon"]))
