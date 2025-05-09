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
    <strong>📅 Predicción meteorológica para el 8 de mayo de 2025 (Valencia):</strong><br>
    🌥️ <em>Nublado con intervalos soleados</em><br>
    🌡️ Temperatura media: <strong>22 °C</strong><br>
    💨 Viento moderado del este: <strong>20 km/h</strong><br>
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

if st.session_state.nodos is None:
    st.session_state.nodos = cargar_nodos()

col1, col2 = st.columns([1, 2])

with col1:
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

            emergencia, incidencias, parkings = cargar_recursos()
            penalizar_riesgo(G, emergencia, incidencias)

            st.session_state.grafo = G
            st.session_state.origen_coords = (G.nodes[nodo1]["y"], G.nodes[nodo1]["x"])
            st.session_state.destino_coords = (G.nodes[nodo2]["y"], G.nodes[nodo2]["x"])
            st.session_state.nodo1 = nodo1
            st.session_state.nodo2 = nodo2
            st.session_state.error = None

        except Exception as e:
            st.session_state.grafo = None
            st.session_state.error = str(e)

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
            ruta = nx.shortest_path(G, nodo1, nodo2, weight=criterio)
        elif nx.has_path(G.to_undirected(), nodo1, nodo2):
            ruta = nx.shortest_path(G.to_undirected(), nodo1, nodo2, weight=criterio)
            modo = "no dirigido"

        if ruta:
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in ruta]
            folium.PolyLine(coords, color="blue", weight=4).add_to(m)

            distancia_total = sum(G[u][v].get("distancia", 0) for u, v in zip(ruta[:-1], ruta[1:]))
            tiempo_total = sum(G[u][v].get("tiempo", 0) for u, v in zip(ruta[:-1], ruta[1:])) * 60
            aristas_riesgo = sum(1 for u, v in zip(ruta[:-1], ruta[1:]) if G[u][v].get("altura", 0) > 0)
            nodos_riesgo = sum(1 for n in ruta if G.nodes[n].get("altura", 0) > 0)

            with col1:
                st.success(f"Ruta encontrada ({len(ruta)} nodos, modo {modo})")
                st.markdown(f"🧮 Criterio optimizado: **{criterio}**")
                st.markdown(f"📏 Distancia total: **{distancia_total:.1f} m**")
                st.markdown(f"⏱️ Tiempo estimado: **{tiempo_total:.0f} segundos**")
                st.markdown(f"⚠️ Aristas con riesgo: **{aristas_riesgo}**")
                st.markdown(f"⚠️ Nodos con riesgo: **{nodos_riesgo}**")

                if modo == "no dirigido":
                    st.warning("⚠️ Se ha usado modo *no dirigido*. La ruta puede no respetar el sentido real de las calles.")

                p = parking_cercano(y2, x2, parkings)
                if p["is_underground"] == 1:
                    if any(G[u][v].get("altura", 0) > 0 for u, v in zip(ruta[:-1], ruta[1:])):
                        st.warning("🚨 El parking más cercano es subterráneo y hay riesgo de inundación.")
                    else:
                        st.info("ℹ️ El parking más cercano es subterráneo.")
                else:
                    st.success("🅿️ El parking más cercano es en superficie.")

    except Exception as e:
        with col1:
            st.error(f"Error calculando ruta: {e}")

    with col2:
        st_folium(m, use_container_width=True, height=600)

elif st.session_state.error:
    st.error(st.session_state.error)
