"use strict";

const fechasPlaneacionPostoperativa = new Map();
const escenariosProgramadosPostoperativos = new Map();
const postFecha = document.querySelector("#postoperative-date");
const postVariable = measureVariable;
const postEjecutar = document.querySelector("#postoperative-run");
const postEstado = document.querySelector("#postoperative-status");
const postGraficas = document.querySelector("#postoperative-charts");

const ajustarPorTransferenciasBasePost = ajustarPorTransferencias;
ajustarPorTransferencias = function(...argumentos) {
  const ajustadas = ajustarPorTransferenciasBasePost(...argumentos);
  for (const resultado of ajustadas) {
    const energiaOriginal = energiaUsuarios(resultado.analisis?.usuariosOriginales || new Map());
    const energiaDesconectada = energiaUsuarios(resultado.analisis?.usuariosDesconectados || new Map());
    const cantidadOriginal = resultado.analisis?.usuariosOriginales?.size || 0;
    const cantidadDesconectada = resultado.analisis?.usuariosDesconectados?.size || 0;
    const fraccionDeslastre = Math.max(0, Math.min(1, energiaOriginal > 0 ? energiaDesconectada / energiaOriginal : cantidadOriginal > 0 ? cantidadDesconectada / cantidadOriginal : 0));
    if (fraccionDeslastre > 0) {
      const aplicarDeslastre = (datos, base) => {
        for (const serie of datos?.series || []) {
          const serieBase = (base?.series || []).find(s => s.clave === serie.clave);
          serie.puntos = (serie.puntos || []).map((p, i) => [p[0], Math.max(0, Number(p[1]) - Number(serieBase?.puntos?.[i]?.[1] || 0) * fraccionDeslastre)]);
        }
      };
      aplicarDeslastre(resultado.corrienteAjustada, resultado.respuesta?.alimentador_corrientes);
      if (!(resultado.ajustada?.series || []).some(s => String(s.clave || "").toUpperCase().startsWith("U"))) aplicarDeslastre(resultado.ajustada, resultado.respuesta?.alimentador);
      resultado.deslastrado = fraccionDeslastre;
    }
    const vinculo = itemDeAlimentador(resultado.analisis);
    if (!vinculo?.item) continue;
    escenariosProgramadosPostoperativos.set(claveCircuitoPost(vinculo.item), {
      variable_principal: measureVariable?.value || "CORRIENTE",
      serie_principal: copiaSerializable(resultado.ajustada),
      corriente: copiaSerializable(resultado.corrienteAjustada),
      carga_cedida: Number(resultado.cedido || 0),
      carga_recibida: Number(resultado.recibido || 0),
      carga_deslastrada: Number(resultado.deslastrado || 0),
      movimientos_345: copiaSerializable(resultado.movimientos345 || []),
    });
  }
  return ajustadas;
};

function claveCircuitoPost(item) {
  return `${String(item.subestacion || "").toUpperCase()}|${String(item.fid || item.g3e_fid || "")}`;
}

function fechasPlaneacionActuales() {
  const resultado = new Map(fechasPlaneacionPostoperativa);
  for (const item of seleccionados.values()) {
    const clave = claveCircuitoPost(item);
    let fecha = "";
    if (measureMode?.value === "HISTORICO") {
      fecha = cacheFechasAnalisis.get(claveCacheAnalisis({fid: item.fid, subestacion: item.subestacion}))?.fecha || "";
    } else {
      fecha = measureDate?.value || "";
    }
    if (fecha) resultado.set(clave, {
      circuito: item.circuito || item.nombre || "",
      subestacion: item.subestacion || "",
      fid: item.fid,
      fecha_programada: fecha,
      escenario_programado: copiaSerializable(escenariosProgramadosPostoperativos.get(clave) || resultado.get(clave)?.escenario_programado || null),
    });
  }
  return resultado;
}

function actualizarEstadoPostoperativo() {
  const fechas = fechasPlaneacionActuales();
  if (measureDate?.min && postFecha) postFecha.min = measureDate.min;
  if (measureDate?.max && postFecha) postFecha.max = measureDate.max;
  postEjecutar.disabled = !postFecha?.value || !fechas.size;
  if (!fechas.size) {
    postEstado.textContent = "Ejecute el análisis histórico máximo y guarde la desconexión para registrar la fecha de cada circuito.";
    return;
  }
  const resumen = [...fechas.values()].map(x => `${x.circuito}: ${x.fecha_programada}`).join(" · ");
  postEstado.textContent = `Planeación disponible · ${resumen}`;
}

function serializarPlaneacionPostoperativa() {
  return [...fechasPlaneacionActuales().values()].map(copiaSerializable);
}

async function guardarArchivoPostoperativo() {
  if (!ultimos.length) return alert("Primero dibuje al menos un circuito.");
  const centro = map.getCenter();
  const archivo = {
    formato: "CDYM-DESCONEXION",
    version: 6,
    guardado_en: new Date().toISOString(),
    circuitos: [...seleccionados.values()].map(copiaSerializable),
    estados: estadosFisicosActuales(),
    virtuales: serializarVirtuales(),
    maniobras_manuales: copiaSerializable(maniobrasGrabadas),
    capas_visibles: copiaSerializable(visibilidadMapa),
    analisis: {
      fecha: measureDate?.value || "",
      variable: measureVariable?.value || "CORRIENTE",
      modo: measureMode?.value || "FECHA",
      dia_semana: measureWeekday?.value || "0",
      tipo_dia: measureDayType?.value || "ORDINARIO",
      delta: measureDelta?.value || "20",
      hora_inicio: document.querySelector("#analysis-start-time")?.value || "",
      hora_fin: document.querySelector("#analysis-end-time")?.value || "",
      ejecutado: Boolean(fechaCorrientesAnalisis),
      fecha_calculada: fechaCorrientesAnalisis,
      fechas_maximas: serializarFechasAnalisis(),
      planeacion_circuitos: serializarPlaneacionPostoperativa(),
    },
    vista: {lat: centro.lat, lng: centro.lng, zoom: map.getZoom()},
  };
  const contenido = JSON.stringify(archivo, null, 2);
  const marca = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const nombreSugerido = `desconexion-cdym-${marca}.json`;
  if ("showSaveFilePicker" in window) {
    try {
      const handle = await window.showSaveFilePicker({suggestedName: nombreSugerido, types: [{description: "Desconexión CDYM", accept: {"application/json": [".json"]}}]});
      const writable = await handle.createWritable();
      await writable.write(contenido);
      await writable.close();
      setProceso(`Copia completa y fechas de planeación guardadas en ${handle.name}.`);
      return;
    } catch (error) {
      if (error?.name === "AbortError") return setProceso("Guardado cancelado por el usuario.");
      console.warn("No fue posible usar el selector de archivos.", error);
    }
  }
  const blob = new Blob([contenido], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url; enlace.download = nombreSugerido; enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  setProceso("Copia completa y fechas de planeación descargadas.");
}

window.guardarDesconexionArchivo = guardarArchivoPostoperativo;

const abrirDesconexionBasePost = abrirDesconexionGuardada;
abrirDesconexionGuardada = async function(archivo) {
  fechasPlaneacionPostoperativa.clear();
  escenariosProgramadosPostoperativos.clear();
  for (const item of archivo?.analisis?.planeacion_circuitos || []) {
    if (item?.fecha_programada) {
      fechasPlaneacionPostoperativa.set(claveCircuitoPost(item), item);
      if (item.escenario_programado) escenariosProgramadosPostoperativos.set(claveCircuitoPost(item), item.escenario_programado);
    }
  }
  const tieneEscenariosGuardados = (archivo?.analisis?.planeacion_circuitos || []).some(item => item?.escenario_programado);
  const archivoRestauracion = archivo?.analisis
    ? {...archivo, analisis: {...archivo.analisis, ejecutado: false}}
    : archivo;
  await abrirDesconexionBasePost(archivoRestauracion);
  actualizarEstadoPostoperativo();
  setProceso(tieneEscenariosGuardados
    ? "Desconexión abierta con el análisis programado guardado; no se repitieron consultas ni cálculos."
    : "Desconexión abierta sin recalcular. Este archivo antiguo requiere pulsar Recalcular todo para crear el escenario comparativo.");
};

function maximoSeriePost(datos) {
  const valores = (datos?.series || []).flatMap(s => (s.puntos || []).map(p => Math.abs(Number(p[1]))).filter(Number.isFinite));
  return valores.length ? Math.max(...valores) : null;
}

function normalizarEjeDiarioPost(datos) {
  return (datos?.series || []).map(serie => ({
    ...serie,
    puntos: (serie.puntos || []).map((p, indice) => {
      const texto = String(p[0] || "");
      const hora = texto.match(/(?:T|\s)(\d{2}:\d{2}(?::\d{2})?)/)?.[1]
        || `${String(Math.floor(indice / 4)).padStart(2, "0")}:${String((indice % 4) * 15).padStart(2, "0")}:00`;
      return [`2000-01-01T${hora.length === 5 ? hora + ":00" : hora}`, Number(p[1])];
    }),
  }));
}

function combinarSeriesPost(programado, real) {
  const coloresProgramados = ["#74a9e6", "#f3ad63", "#63bd91"];
  const coloresReales = ["#0057b8", "#d14900", "#007a4d"];
  return {
    series: [
      ...normalizarEjeDiarioPost(programado).map((s, i) => ({...s, original: true, color: coloresProgramados[i % coloresProgramados.length], nombre: `Programado · ${s.nombre || s.clave}`})),
      ...normalizarEjeDiarioPost(real).map((s, i) => ({...s, color: coloresReales[i % coloresReales.length], nombre: `Real · ${s.nombre || s.clave}`})),
    ],
  };
}

function clavesCorrientePost(datos) {
  return (datos?.series || []).filter(s => (s.puntos || []).some(p => Number.isFinite(Number(p[1])))).map(s => String(s.clave || "").toUpperCase()).filter(k => ["IR", "IS", "IT"].includes(k));
}

function faseMayorRealPost(datos) {
  const candidatas = (datos?.series || []).filter(s => ["IR", "IS", "IT"].includes(String(s.clave || "").toUpperCase()) && (s.puntos || []).some(p => Number.isFinite(Number(p[1]))));
  if (!candidatas.length) return String(datos?.series?.[0]?.clave || "TODAS").toUpperCase();
  return String(candidatas.reduce((mejor, serie) => maximoSeriePost({series: [serie]}) > maximoSeriePost({series: [mejor]}) ? serie : mejor).clave).toUpperCase();
}

function filtrarFasePost(datos, fase) {
  if (fase === "TODAS") return datos;
  return {...datos, series: (datos?.series || []).filter(s => String(s.clave || "").toUpperCase() === fase)};
}

function actualizarGraficaFasePost(resultado, indice, fase) {
  const programado = filtrarFasePost(resultado.programado.alimentador, fase);
  const real = filtrarFasePost(resultado.real.alimentador, fase);
  const maxProgramado = document.querySelector(`#postoperative-max-planned-${indice}`);
  const maxReal = document.querySelector(`#postoperative-max-real-${indice}`);
  if (maxProgramado) maxProgramado.textContent = numeroEje(maximoSeriePost(programado));
  if (maxReal) maxReal.textContent = numeroEje(maximoSeriePost(real));
  mostrarGrafica(document.querySelector(`#postoperative-chart-${indice}`), combinarSeriesPost(programado, real));
}

async function consultarDiaPost(item, fecha, variable) {
  const q = new URLSearchParams({fid: item.fid, subestacion: item.subestacion, variable, modo: "FECHA", fecha});
  const respuesta = await fetch(`${APP.medidasGrafica}?${q}`);
  const datos = await respuesta.json();
  if (!respuesta.ok) throw new Error(datos.error || "No fue posible consultar la medida.");
  const tienePuntos = (datos.alimentador?.series || []).some(s => (s.puntos || []).some(p => Number.isFinite(Number(p[1]))));
  if (!tienePuntos) {
    const error = new Error(`No existen registros de ${variable.toLowerCase()} para ${fecha}. Disponible hasta ${datos.fecha_maxima || "la última fecha informada"}.`);
    error.fechaMinima = datos.fecha_minima;
    error.fechaMaxima = datos.fecha_maxima;
    throw error;
  }
  return datos;
}

function serieProgramadaPost(item, variable) {
  const escenario = item.escenario_programado || escenariosProgramadosPostoperativos.get(claveCircuitoPost(item));
  if (!escenario) return null;
  if (variable === "CORRIENTE") return escenario.corriente || null;
  if (escenario.variable_principal === variable) return escenario.serie_principal || null;
  return null;
}

postEjecutar?.addEventListener("click", async () => {
  const planeacion = [...fechasPlaneacionActuales().values()];
  const fechaReal = postFecha.value, variable = postVariable.value;
  if (!fechaReal || !planeacion.length) return actualizarEstadoPostoperativo();
  if (!postFecha.checkValidity()) {
    postFecha.reportValidity();
    postEstado.textContent = `Seleccione una fecha entre ${postFecha.min || "el inicio disponible"} y ${postFecha.max || "el último día disponible"}.`;
    return;
  }
  postEjecutar.disabled = true;
  postEstado.textContent = `Comparando ${planeacion.length} circuito(s) contra ${fechaReal}...`;
  document.querySelectorAll(".postoperative-comparison-chart").forEach(elemento => elemento.remove());
  const resultados = [];
  for (let i = 0; i < planeacion.length; i++) {
    const item = planeacion[i];
    try {
      const serieProgramada = serieProgramadaPost(item, variable);
      if (!serieProgramada?.series?.some(s => s.puntos?.length)) throw new Error(`El archivo no contiene la curva programada ajustada de ${variable.toLowerCase()}. Ejecute nuevamente el análisis de planeación y guarde la desconexión.`);
      const real = await consultarDiaPost(item, fechaReal, variable);
      const programado = {alimentador: serieProgramada};
      resultados.push({item, programado, real, faseInicial: variable === "CORRIENTE" ? faseMayorRealPost(real.alimentador) : "TODAS"});
      postEstado.textContent = `Consultados ${i + 1} de ${planeacion.length} circuito(s)...`;
    } catch (error) {
      if (error.fechaMinima && postFecha) postFecha.min = error.fechaMinima;
      if (error.fechaMaxima && postFecha) postFecha.max = error.fechaMaxima;
      resultados.push({item, error: error.message});
    }
  }
  resultados.forEach((x, i) => {
    const normalizar = valor => String(valor || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Z0-9]/gi, "").toUpperCase();
    const circuitoBuscado = normalizar(x.item.circuito || x.item.nombre);
    const tarjetas = [...document.querySelectorAll(".maneuver-chart-card")];
    const tarjeta = tarjetas.find(card => normalizar(card.querySelector("h3")?.textContent).includes(circuitoBuscado)) || tarjetas[i];
    const contenedor = tarjeta?.querySelector(".measurement-charts");
    if (!contenedor) {
      console.warn("No se encontró la tarjeta para insertar el comparativo", x.item);
      return;
    }
    const articulo = document.createElement("article");
    articulo.className = `postoperative-comparison-chart${x.error ? " error" : ""}`;
    articulo.innerHTML = x.error
      ? `<h4>Programado ajustado vs. real</h4><p class="chart-message error">${esc(x.error)}</p>`
      : `<div class="postoperative-inline-head"><div><h4>Programado ajustado vs. real</h4><p class="chart-origin">Escenario de ${esc(x.item.fecha_programada)} · medición real ${esc(fechaReal)}</p></div>${variable === "CORRIENTE" ? `<label class="postoperative-phase-control">Fases<select id="postoperative-phase-${i}"><option value="TODAS">Las 3 fases</option>${clavesCorrientePost(x.real.alimentador).map(f => `<option value="${f}"${f === x.faseInicial ? " selected" : ""}>${f}${f === x.faseInicial ? " · mayor real" : ""}</option>`).join("")}</select></label>` : ""}</div><div class="postoperative-summary"><span><b>Máximo programado ajustado</b><i id="postoperative-max-planned-${i}"></i></span><span><b>Máximo real medido</b><i id="postoperative-max-real-${i}"></i></span></div><div id="postoperative-chart-${i}" class="daily-chart"></div>`;
    contenedor.appendChild(articulo);
    if (x.error) return;
    actualizarGraficaFasePost(x, i, x.faseInicial);
    document.querySelector(`#postoperative-phase-${i}`)?.addEventListener("change", event => actualizarGraficaFasePost(x, i, event.target.value));
  });
  const correctos = resultados.filter(x => !x.error).length;
  postEstado.textContent = `Comparación terminada: ${correctos} de ${resultados.length} circuito(s) con datos para ${fechaReal}.`;
  postEjecutar.disabled = false;
});

postFecha?.addEventListener("change", actualizarEstadoPostoperativo);
postVariable?.addEventListener("change", actualizarEstadoPostoperativo);
if (measureStatus) new MutationObserver(actualizarEstadoPostoperativo).observe(measureStatus, {childList: true, characterData: true, subtree: true});
actualizarEstadoPostoperativo();
