"use strict";

const fetchBaseMedidas = window.fetch.bind(window);
const colaMedidas = [];
let consultasMedidasActivas = 0;
const MAX_CONSULTAS_MEDIDAS = 3;

function ejecutarSiguienteMedida() {
  while (consultasMedidasActivas < MAX_CONSULTAS_MEDIDAS && colaMedidas.length) {
    const siguiente = colaMedidas.shift();
    consultasMedidasActivas++;
    siguiente().finally(() => {
      consultasMedidasActivas--;
      ejecutarSiguienteMedida();
    });
  }
}

function encolarConsultaMedida(consulta) {
  return new Promise((resolve, reject) => {
    colaMedidas.push(async () => {
      try {
        resolve(await consulta());
      } catch (error) {
        reject(error);
      }
    });
    ejecutarSiguienteMedida();
  });
}

async function consultarMedidaConReintento(input, init) {
  let ultimoError;
  for (let intento = 1; intento <= 3; intento++) {
    try {
      return await fetchBaseMedidas(input, init);
    } catch (error) {
      ultimoError = error;
      if (intento < 3) await new Promise(resolve => setTimeout(resolve, intento * 750));
    }
  }
  throw ultimoError;
}

window.fetch = function(input, init) {
  const url = typeof input === "string" ? input : String(input?.url || "");
  if (!url.includes("/api/medidas/grafica/")) return fetchBaseMedidas(input, init);
  return encolarConsultaMedida(() => consultarMedidaConReintento(input, init));
};
