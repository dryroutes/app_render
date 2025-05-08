let map = L.map("map").setView([39.5, -0.4], 10);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

let puntos = [];
let lineaRuta = null;

map.on("click", function (e) {
  L.marker(e.latlng).addTo(map);
  puntos.push(e.latlng);
  if (puntos.length === 2) {
    // Aquí necesitas sustituir por lógica real para obtener IDs de nodos
    fetch("/ruta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origen: 94615698, destino: 420055138 }) // Sustituye con IDs reales
    })
    .then(res => res.json())
    .then(data => {
      if (lineaRuta) map.removeLayer(lineaRuta);
      if (data.ruta) {
        lineaRuta = L.polyline(data.ruta.map(p => [p[1], p[0]])).addTo(map);
      } else {
        alert("Error: " + data.error);
      }
    });
  }
});
