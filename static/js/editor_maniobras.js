"use strict";

function dispositivosEditablesProtocolo() {
  const vistos = new Set(), salida = [];
  for (const elemento of ultimoFlujo?.elementos?.values?.() || []) {
    const fid = String(elemento.g3e_fid || "");
    if (!fid || vistos.has(fid) || !corte.has(Number(elemento.g3e_fno))) continue;
    vistos.add(fid); salida.push(elemento);
  }
  return salida.sort((a, b) => String(a.circuito || "").localeCompare(String(b.circuito || "")) || String(a.codigo || a.g3e_fid).localeCompare(String(b.codigo || b.g3e_fid)));
}

function seleccionarManiobraProtocolo(titulo, actual = null) {
  const dispositivos = dispositivosEditablesProtocolo();
  if (!dispositivos.length) return Promise.reject(new Error("No hay dispositivos maniobrables dibujados."));
  return new Promise(resolve => {
    const fondo = document.createElement("div");
    fondo.className = "maneuver-picker-backdrop";
    const fidActual = String(actual?.fid || actual?.fidReal || actual?.elemento?.g3e_fid || actual?.id || "");
    fondo.innerHTML = `<section class="maneuver-picker" role="dialog" aria-modal="true"><h3>${esc(titulo)}</h3><label>Dispositivo<select id="maneuver-picker-device">${dispositivos.map(e => `<option value="${e.g3e_fid}"${String(e.g3e_fid) === fidActual ? " selected" : ""}>${esc(e.codigo_operacion || e.codigo || e.g3e_fid)} · ${esc(e.tipo || "Dispositivo")} · ${esc(e.circuito || "Sin celda")}</option>`).join("")}</select></label><label>Maniobra<select id="maneuver-picker-state"><option value="OPEN"${actual?.actual === "OPEN" ? " selected" : ""}>Abrir</option><option value="CLOSED"${actual?.actual === "CLOSED" ? " selected" : ""}>Cerrar</option></select></label><label>Motivo técnico<textarea id="maneuver-picker-reason" rows="3" required>${esc(actual?.motivo || "")}</textarea></label><div><button type="button" data-action="cancel">Cancelar</button><button type="button" data-action="accept">Aceptar</button></div></section>`;
    document.body.appendChild(fondo);
    const terminar = valor => { fondo.remove(); resolve(valor); };
    fondo.querySelector('[data-action="cancel"]').onclick = () => terminar(null);
    fondo.querySelector('[data-action="accept"]').onclick = () => {
      const motivo = fondo.querySelector("#maneuver-picker-reason").value.trim();
      if (!motivo) return alert("Debe indicar el motivo técnico de la maniobra.");
      terminar({elemento: ultimoFlujo.elementos.get(fondo.querySelector("#maneuver-picker-device").value), actual: fondo.querySelector("#maneuver-picker-state").value, motivo});
    };
  });
}

function construirPasoSeleccionado(seleccion, anterior = {}) {
  const e = seleccion.elemento;
  return {...anterior, id: String(e.g3e_fid), fid: e.g3e_fid, fidReal: e.g3e_fid, codigo: e.codigo_operacion || e.codigo || String(e.g3e_fid), tipo: e.tipo || "Dispositivo", circuito: e.circuito || "", subestacion: e.subestacion || "", nivel: e._nivel_kv || "", base: estadoBase(e), actual: seleccion.actual, elemento: e, virtual: false, custom: true, editadoManual: true, motivo: seleccion.motivo};
}

window.editarPasoProtocolo = async indice => {
  const anterior = ultimoProtocoloClasificado[indice]; if (!anterior) return;
  try { const seleccion = await seleccionarManiobraProtocolo("Editar maniobra", anterior); if (!seleccion) return; ultimoProtocoloClasificado[indice] = construirPasoSeleccionado(seleccion, anterior); await guardarAprendizajeProtocolo("EDITAR", seleccion.motivo); refrescarProtocoloEditado(); }
  catch (error) { alert(error.message); }
};

window.agregarPasoProtocolo = async (indice = 0) => {
  try { const seleccion = await seleccionarManiobraProtocolo("Agregar maniobra antes del paso " + (indice + 1)); if (!seleccion) return; ultimoProtocoloClasificado.splice(Math.max(0, Math.min(indice, ultimoProtocoloClasificado.length)), 0, construirPasoSeleccionado(seleccion)); await guardarAprendizajeProtocolo("AGREGAR", seleccion.motivo); refrescarProtocoloEditado(); }
  catch (error) { alert(error.message); }
};

htmlEditorProtocolo = function() {
  return '<section class="protocol-section protocol-editor"><div class="protocol-editor-head"><div><h3>Editar protocolo</h3><small>Edite el dispositivo o inserte una maniobra inmediatamente arriba del paso seleccionado. Después puede simular el protocolo actualizado.</small></div></div><ol class="protocol-edit-list">' + ultimoProtocoloClasificado.map((o, i) => '<li><span class="protocol-step">' + (i + 1) + '</span><div><b>' + esc(nombreAccion(o.actual)) + ' ' + esc(o.codigo) + '</b><small>' + esc(o.tipo || "Dispositivo") + ' · ' + esc(o.circuito || "Sin celda") + '</small></div><div class="protocol-edit-actions"><button type="button" onclick="agregarPasoProtocolo(' + i + ')">+ Arriba</button><button type="button" onclick="moverPasoProtocolo(' + i + ',-1)" title="Subir">↑</button><button type="button" onclick="moverPasoProtocolo(' + i + ',1)" title="Bajar">↓</button><button type="button" onclick="editarPasoProtocolo(' + i + ')">Editar</button><button type="button" class="danger" onclick="quitarPasoProtocolo(' + i + ')">Quitar</button></div></li>').join("") + '</ol></section>';
};

datosFilaExcel = function(o, i, normalizar = false) {
  const accion = o.accion || (normalizar ? nombreAccion(o.base) : nombreAccion(o.actual));
  const elemento = o.elemento || ultimoFlujo?.elementos?.get(String(o.fid || o.fidReal || o.id || ""));
  const subestacion = o.subestacion || elemento?.subestacion || "Sin dato";
  const celda = o.circuito || elemento?.circuito || "Sin dato";
  const nivel = o.nivel || elemento?._nivel_kv || "Sin dato";
  const tipo = o.tipo || elemento?.tipo || "Dispositivo";
  const fid = o.fid || o.fidReal || elemento?.g3e_fid || "";
  const direccion = o.direccion || "Dirección no disponible";
  const maniobra = o.manual?.grupos ? accion + " cruce aéreo separando la conexión entre " + codigoParesCruce(o.manual.grupos) + " de nivel de tensión " + nivel + " kV de la celda " + celda + " en la dirección " + direccion + "." : accion + " " + String(tipo).toLowerCase() + " " + (o.codigo || "") + " de nivel de tensión " + nivel + " kV de la celda " + celda + " en la dirección " + direccion + ".";
  return [i + 1, o.fechaTexto || fechaProtocolo(), subestacion, celda, o.codigo || "", tipo, accion, nivel, fid, direccion, maniobra, o.motivo || ""];
};

function construirManiobraManual(seleccion, anterior = {}) {
  const e = seleccion.elemento;
  return {...anterior, numero: anterior.numero || 0, tipo: e.tipo || "Dispositivo", codigo: e.codigo_operacion || e.codigo || String(e.g3e_fid), estado: seleccion.actual, fecha: anterior.fecha || new Date().toISOString(), fid: e.g3e_fid, circuito: e.circuito || "", subestacion: e.subestacion || "", nivel: e._nivel_kv || "", motivo: seleccion.motivo};
}

function renumerarManiobrasManuales() { maniobrasGrabadas.forEach((item, indice) => item.numero = indice + 1); }

function htmlEditorManiobrasManuales() {
  return '<section class="protocol-section protocol-editor"><div class="protocol-editor-head"><div><h3>Editar maniobras manuales</h3><small>Los cambios se conservan al guardar nuevamente la desconexión local.</small></div></div><ol class="protocol-edit-list">' + maniobrasGrabadas.map((o, i) => '<li><span class="protocol-step">' + (i + 1) + '</span><div><b>' + esc(nombreAccion(o.estado)) + ' ' + esc(o.codigo) + '</b><small>' + esc(o.tipo || "Dispositivo") + ' · ' + esc(o.circuito || "Sin celda") + '</small></div><div class="protocol-edit-actions"><button type="button" onclick="agregarManiobraManualArriba(' + i + ')">+ Arriba</button><button type="button" onclick="editarManiobraManual(' + i + ')">Editar</button><button type="button" class="danger" onclick="quitarManiobraManual(' + i + ')">Quitar</button></div></li>').join("") + '</ol></section>';
}

const verManiobrasGrabadasBaseEditor = window.verManiobrasGrabadas;
window.verManiobrasGrabadas = async function() {
  await verManiobrasGrabadasBaseEditor();
  const body = document.querySelector("#recorded-maneuvers-body");
  if (body && maniobrasGrabadas.length) body.insertAdjacentHTML("afterbegin", htmlEditorManiobrasManuales());
};

window.editarManiobraManual = async indice => {
  const anterior = maniobrasGrabadas[indice]; if (!anterior) return;
  try { const seleccion = await seleccionarManiobraProtocolo("Editar maniobra manual", {...anterior, actual: anterior.estado}); if (!seleccion) return; maniobrasGrabadas[indice] = construirManiobraManual(seleccion, anterior); renumerarManiobrasManuales(); actualizarBotonGrabacion(); await window.verManiobrasGrabadas(); }
  catch (error) { alert(error.message); }
};

window.agregarManiobraManualArriba = async indice => {
  try { const seleccion = await seleccionarManiobraProtocolo("Agregar maniobra manual antes del paso " + (indice + 1)); if (!seleccion) return; maniobrasGrabadas.splice(indice, 0, construirManiobraManual(seleccion)); renumerarManiobrasManuales(); actualizarBotonGrabacion(); await window.verManiobrasGrabadas(); }
  catch (error) { alert(error.message); }
};

window.quitarManiobraManual = async indice => {
  if (!maniobrasGrabadas[indice] || !confirm("¿Quitar esta maniobra manual?")) return;
  maniobrasGrabadas.splice(indice, 1); renumerarManiobrasManuales(); actualizarBotonGrabacion(); await window.verManiobrasGrabadas();
};
