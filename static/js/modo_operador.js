"use strict";

let modoOperadorActivo = false;
let ejecutandoComoOperador = false;

function actualizarModoOperador() {
  const boton = document.querySelector("#operator-mode");
  if (!boton) return;
  boton.classList.toggle("active", modoOperadorActivo);
  boton.setAttribute("aria-pressed", String(modoOperadorActivo));
  boton.textContent = modoOperadorActivo ? "Modo operador: ON" : "Modo operador: OFF";
}

window.alternarModoOperador = function() {
  modoOperadorActivo = !modoOperadorActivo;
  actualizarModoOperador();
  setProceso(modoOperadorActivo
    ? "Modo operador activo: se aplican restricciones topológicas, de carga, corriente y paralelos."
    : "Modo operador desactivado: las maniobras vuelven al modo libre.");
};

const registrarManiobraBaseOperador = registrarManiobra;
registrarManiobra = function(...argumentos) {
  if (ejecutandoComoOperador && !window.__grabacionOperadorOriginal) return;
  return registrarManiobraBaseOperador(...argumentos);
};

async function ejecutarConRestriccionesOperador(accion) {
  if (!modoOperadorActivo || modoGrabacionManiobras) return accion();
  const grabacionOriginal = modoGrabacionManiobras;
  window.__grabacionOperadorOriginal = grabacionOriginal;
  ejecutandoComoOperador = true;
  modoGrabacionManiobras = true;
  try {
    return await accion();
  } finally {
    modoGrabacionManiobras = grabacionOriginal;
    ejecutandoComoOperador = false;
    delete window.__grabacionOperadorOriginal;
  }
}

const manejarClickLineaBaseOperador = manejarClickLinea;
manejarClickLinea = function(...argumentos) {
  return ejecutarConRestriccionesOperador(() => manejarClickLineaBaseOperador(...argumentos));
};

const abrirCruceVirtualBaseOperador = abrirCruceVirtual;
abrirCruceVirtual = function(...argumentos) {
  return ejecutarConRestriccionesOperador(() => abrirCruceVirtualBaseOperador(...argumentos));
};

const operarEquipoBaseOperador = window.operarEquipo;
window.operarEquipo = function(...argumentos) {
  return ejecutarConRestriccionesOperador(() => operarEquipoBaseOperador(...argumentos));
};

actualizarModoOperador();
