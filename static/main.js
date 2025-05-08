let map = L.map("map").setView([39.5, -0.4], 10);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

let puntos = [];
let ids = [];
let lineaRuta = null;

map.on("click", function (e) {
  const lat = e.latlng.lat;
  const lng = e.latlng.lng;

  L.marker([lat, lng]).addTo(map);

  // Buscar el nodo más cercano
  fetch("/nodo_mas_cercano", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ x: lng, y: lat })
  })
    .then((res) => res.json())
    .then((data) => {
      ids.push(data.nodo);
      puntos.push([lat, lng]);

      if (ids.length === 2) {
        // Calcular ruta real
        fetch("/ruta", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ origen: ids[0], destino: ids[1] })
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.ruta) {
              if (lineaRuta) map.removeLayer(lineaRuta);
              lineaRuta = L.polyline(data.ruta.map(p => [p[1], p[0]])).addTo(map);
            } else {
              alert("Error al calcular ruta: " + data.error);
            }
          });
      }
    });
});
