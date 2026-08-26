const capaKmz = L.layerGroup().addTo(map);
let kmzActual = null;

function popupKmz(feature) {
  const propiedades = feature?.properties || {}, nombre = propiedades.nombre || "Elemento KMZ";
  const filas = Object.entries(propiedades).filter(([k,v]) => k !== "nombre" && v !== null && String(v).trim()).slice(0,20).map(([k,v]) => `<dt>${esc(k)}</dt><dd>${esc(String(v))}</dd>`).join("");
  return `<section class="kmz-popup"><h3>${esc(nombre)}</h3>${filas ? `<dl>${filas}</dl>` : ""}</section>`;
}

function estiloKmz(feature) {
  return (feature?.geometry?.type || "").includes("Polygon")
    ? {color:"#a65b00",weight:3,opacity:.95,fillColor:"#ffb347",fillOpacity:.22}
    : {color:"#e07000",weight:5,opacity:.95,dashArray:"10 6"};
}

function dibujarKmz(nombre, geojson) {
  capaKmz.clearLayers();
  const dibujo = L.geoJSON(geojson, {
    style: estiloKmz,
    pointToLayer: (_f, latlng) => L.circleMarker(latlng,{radius:8,color:"#fff",weight:2,fillColor:"#e07000",fillOpacity:1}),
    onEachFeature: (feature, layer) => layer.bindPopup(() => popupKmz(feature)),
  }).addTo(capaKmz);
  kmzActual = {nombre, geojson};
  if (!map.hasLayer(capaKmz)) capaKmz.addTo(map);
  document.querySelector("#kmz-visible").checked = true;
  document.querySelector("#kmz-layer-name").textContent = nombre;
  document.querySelector("#kmz-layer-controls").hidden = false;
  const bounds = dibujo.getBounds();
  if (bounds.isValid()) map.fitBounds(bounds.pad(.08));
}

window.eliminarKmz = () => {
  capaKmz.clearLayers();
  if (map.hasLayer(capaKmz)) map.removeLayer(capaKmz);
  kmzActual = null;
  document.querySelector("#kmz-layer-controls").hidden = true;
  setProceso("La capa KMZ fue eliminada del dibujo.");
};

document.querySelector("#kmz-visible")?.addEventListener("change", event => {
  if (!kmzActual) return;
  event.target.checked ? capaKmz.addTo(map) : map.removeLayer(capaKmz);
  setProceso(event.target.checked ? `Capa KMZ visible: ${kmzActual.nombre}.` : `Capa KMZ oculta: ${kmzActual.nombre}.`);
});

document.querySelector("#open-kmz-file")?.addEventListener("change", async event => {
  const input = event.target, archivo = input.files?.[0];
  if (!archivo) return;
  const datos = new FormData(); datos.append("archivo", archivo);
  setProceso(`Cargando proyecto KMZ: ${archivo.name}...`, true);
  try {
    const respuesta = await fetch("/api/kmz/", {method:"POST",headers:{"X-CSRFToken":APP.csrf},body:datos});
    const resultado = await respuesta.json();
    if (!respuesta.ok) throw new Error(resultado.error || "No fue posible leer el KMZ.");
    dibujarKmz(resultado.nombre, resultado.geojson);
    const resumen = Object.entries(resultado.tipos || {}).map(([tipo,cantidad]) => `${cantidad} ${tipo}`).join(", ");
    setProceso(`KMZ cargado: ${resultado.elementos} elemento(s)${resumen ? ` · ${resumen}` : ""}.`);
  } catch (error) {
    alert(error.message); setProceso(error.message);
  } finally { input.value = ""; }
});
