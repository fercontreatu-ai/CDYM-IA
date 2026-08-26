let origenesBarrasIA = new Map();
let bloqueoEnsenanzaIA = "";
let objetivoEnsenanzaIA = [];

function mensajeChatIA(texto, rol="assistant") {
  const contenedor=document.querySelector("#ia-chat-messages");
  if (!contenedor) return;
  const item=document.createElement("div");
  item.className=`ia-chat-message ${rol}`;item.textContent=texto;
  contenedor.appendChild(item);contenedor.scrollTop=contenedor.scrollHeight;
}

window.abrirChatProtocoloIA=function(bloqueo=""){
  bloqueoEnsenanzaIA=bloqueo||bloqueoEnsenanzaIA;
  const panel=document.querySelector("#ia-teaching-panel");if(panel)panel.hidden=false;
  if(bloqueo)mensajeChatIA("No encontré una solución completa: "+bloqueo+"\nPuedes enseñarme ejecutando el protocolo correcto paso a paso en el mapa.");
};
window.cerrarChatProtocoloIA=()=>{const panel=document.querySelector("#ia-teaching-panel");if(panel)panel.hidden=true;};
window.hayEnsenanzaIAActiva=()=>Boolean(bloqueoEnsenanzaIA||objetivoEnsenanzaIA.length);
window.notificarFinGrabacionEnsenanzaIA=(total)=>{const estado=document.querySelector("#ia-teaching-mode");if(estado)estado.textContent=`Pendiente de guardar · ${total} maniobra(s)`;mensajeChatIA(`Grabación detenida con ${total} maniobra(s). Aún no están aprendidas. Pulsa “Terminar y aprender” para guardarlas permanentemente.`);};
window.notificarManiobraEnsenanzaIA=(maniobra,total)=>{const estado=document.querySelector("#ia-teaching-mode");if(estado)estado.textContent=`Grabando · ${total} maniobra(s)`;mensajeChatIA(`Paso ${total} grabado: ${maniobra.estado} ${maniobra.codigo}.`);};
window.iniciarEnsenanzaManualIA=async function(){if(modoGrabacionManiobras)return mensajeChatIA(`La grabación ya está activa con ${maniobrasGrabadas.length} maniobra(s).`);objetivoEnsenanzaIA=copiaSerializable(operacionesFinalesProtocolo());maniobrasGrabadas=[];actualizarBotonGrabacion();const iniciada=await iniciarGrabacionManiobras(false,true);if(iniciada)mensajeChatIA("Grabación iniciada desde el estado normal. El objetivo dibujado quedó guardado como referencia. Comprueba que el botón superior indique ‘Detener grabación (0)’; cada maniobra válida aumentará el contador. Al finalizar pulsa ‘Terminar y aprender’.");else mensajeChatIA("No fue posible iniciar la grabación. Revise el mensaje de estado de la aplicación.");};
async function guardarDemostracionManualIA(){const automaticas=objetivoEnsenanzaIA.length?objetivoEnsenanzaIA:operacionesFinalesProtocolo(),firma=await firmaProtocoloBase(automaticas.length?automaticas:maniobrasGrabadas.map(m=>({id:m.fid||m.id||m.codigo,actual:m.estado,codigo:m.codigo,circuito:m.circuito||""}))),protocolo=maniobrasGrabadas.map((m,posicion)=>{const elemento=ultimoFlujo?.elementos.get(String(m.fid||"")),actual=String(m.estado||"").toUpperCase(),base=elemento?estadoBase(elemento):(actual==="OPEN"?"CLOSED":"OPEN"),o={id:m.id||m.fid||("MANUAL-"+posicion),codigo:m.codigo||elemento?.codigo||m.fid||"",tipo:m.tipo||elemento?.tipo||"Dispositivo",circuito:m.circuito||elemento?.circuito||"",subestacion:m.subestacion||elemento?.subestacion||"",base,actual,elemento};return{clave:claveOperacionAprendida(o),posicion,codigo:o.codigo,tipo:o.tipo,fno:Number(elemento?.g3e_fno)||null,circuito:o.circuito,subestacion:o.subestacion,base:o.base,actual:o.actual,motivo:"Demostración manual del operador ante un bloqueo del planificador.",custom:!elemento,virtual:Boolean(m.id&&!m.fid),editadoManual:true};}),respuesta=await fetch(APP.guardarAprendizajeProtocolo,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":APP.csrf},body:JSON.stringify({firma,tipo_cambio:"DEMOSTRACION",motivo:"Secuencia enseñada manualmente porque el planificador no encontró una solución ejecutable. "+bloqueoEnsenanzaIA,protocolo,contexto:{origen:"MODO_ENSENANZA_IA",bloqueo:bloqueoEnsenanzaIA,objetivo:automaticas.map(o=>({clave:claveOperacionAprendida(o),codigo:o.codigo,tipo:o.tipo,actual:o.actual})),circuitos:[...seleccionados.values()].map(x=>({subestacion:x.subestacion,circuito:x.circuito,barra_fid:x.barra_fid||null}))}})}),datos=await respuesta.json();if(!respuesta.ok)throw new Error(datos.error||"No fue posible guardar la demostración.");return datos;}
window.finalizarEnsenanzaIA=async function(){if(!maniobrasGrabadas.length)return alert("Todavía no se ha grabado ninguna maniobra.");modoGrabacionManiobras=false;actualizarBotonGrabacion();try{const evidencia=await guardarDemostracionManualIA();const mensaje=`Aprendizaje confirmado · evento #${evidencia.evento_id} · ${evidencia.ejemplos} ejemplo(s) persistente(s) · ${maniobrasGrabadas.length} maniobra(s) guardada(s).`;mensajeChatIA(mensaje);setProceso(mensaje);await verManiobrasGrabadas();}catch(error){mensajeChatIA("NO SE GUARDÓ EL APRENDIZAJE: "+error.message);setProceso("No se guardó el aprendizaje: "+error.message);alert(error.message);}};
window.enviarChatProtocoloIA=async function(event){event.preventDefault();const input=document.querySelector("#ia-chat-input"),mensaje=input?.value.trim();if(!mensaje)return;mensajeChatIA(mensaje,"user");input.value="";try{const r=await fetch(APP.chatProtocoloIA,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":APP.csrf},body:JSON.stringify({mensaje,bloqueo:bloqueoEnsenanzaIA,protocolo:ultimoProtocoloClasificado.map(o=>({codigo:o.codigo,tipo:o.tipo,accion:o.actual,circuito:o.circuito})),maniobras:maniobrasGrabadas})}),d=await r.json();if(!r.ok)throw new Error(d.error||"No fue posible consultar el asistente.");document.querySelector("#ia-teaching-mode").textContent="Asistente local de enseñanza";mensajeChatIA(d.respuesta);}catch(error){mensajeChatIA("Error: "+error.message);}};

async function cargarOrigenesBarrasIA() {
  const barras = [...new Set((ultimoFlujo?.semillas || []).map(x => Number(x.barraFid)).filter(Number.isFinite))];
  if (!barras.length) return;
  const respuesta = await fetch(APP.origenesBarrasIA, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRFToken": APP.csrf},
    body: JSON.stringify({barras_fid: barras})
  });
  const datos = await respuesta.json();
  if (!respuesta.ok) throw new Error(datos.error || "No fue posible consultar el origen de las barras.");
  origenesBarrasIA = new Map(Object.entries(datos.origenes || {}));
}

function datosFuenteIA(clave) {
  const semilla = (ultimoFlujo?.semillas || []).find(x => x.key === clave);
  if (!semilla) return null;
  const resultado = ultimos.find(x => String(x.item?.fid) === String(semilla.fid));
  return {
    tension: Number(resultado?.item?.tension || semilla.nivel || 0),
    barraFid: semilla.barraFid ? String(semilla.barraFid) : "",
  };
}

window.paraleloNivelSuperiorIA = function (fuenteA, fuenteB) {
  const a = datosFuenteIA(fuenteA), b = datosFuenteIA(fuenteB);
  if (!a || !b || Math.abs(a.tension - 13.8) > 0.05 || Math.abs(b.tension - 13.8) > 0.05) return false;
  const nivelA = Number(origenesBarrasIA.get(a.barraFid)?.nivel_superior_kv);
  const nivelB = Number(origenesBarrasIA.get(b.barraFid)?.nivel_superior_kv);
  return nivelA > 0 && nivelB > 0 && Math.abs(nivelA - nivelB) < 0.05;
};

async function recuperarDemostracionExactaIA(objetivo) {
  const firma=await firmaProtocoloBase(objetivo),respuesta=await fetch(APP.aprendizajeProtocolo+"?firma="+encodeURIComponent(firma)),datos=await respuesta.json();
  if(!respuesta.ok||!datos.aprendizaje?.protocolo?.length)return false;
  const porClave=new Map(objetivo.map(o=>[String(claveOperacionAprendida(o)),o]));
  const porCodigo=new Map(objetivo.map(o=>[String(o.codigo||"").toUpperCase(),o]));
  const elementos=[...(ultimoFlujo?.elementos.values()||[])],fecha=new Date().toISOString();
  const recuperadas=datos.aprendizaje.protocolo.map((guardado,indice)=>{
    const clave=String(guardado.clave||""),base=porClave.get(clave)||porCodigo.get(String(guardado.codigo||"").toUpperCase()),elemento=ultimoFlujo?.elementos.get(clave)||elementos.find(e=>String(e.codigo||"").toUpperCase()===String(guardado.codigo||"").toUpperCase());
    return {...copiaSerializable(base||{}),numero:indice+1,id:base?.id||(!elemento?clave:undefined),fid:elemento?.g3e_fid||base?.fid||base?.fidReal,codigo:guardado.codigo||base?.codigo||elemento?.codigo||clave,tipo:guardado.tipo||base?.tipo||elemento?.tipo||"Dispositivo",circuito:guardado.circuito||base?.circuito||elemento?.circuito||"",subestacion:guardado.subestacion||base?.subestacion||elemento?.subestacion||"",estado:String(guardado.actual||base?.actual||"OPEN").toUpperCase(),fecha,aprendido:true};
  });
  if(!recuperadas.length)return false;
  maniobrasGrabadas=recuperadas;modoGrabacionManiobras=false;actualizarBotonGrabacion();
  await verManiobrasGrabadas();
  const titulo=document.querySelector("#recorded-maneuvers-title");if(titulo)titulo.textContent="Protocolo IA recuperado del aprendizaje";
  abrirChatProtocoloIA();
  mensajeChatIA(`Reconocí exactamente este escenario y recuperé ${recuperadas.length} maniobra(s) aprendidas. No necesitas enseñarlo nuevamente.`);
  setProceso(`IA: escenario reconocido. Se recuperaron ${recuperadas.length} maniobra(s) aprendidas.`);
  return true;
}

window.generarProtocoloIA = async function () {
  if (!ultimoFlujo || !ultimos.some(x => x.data)) {
    alert("Primero dibuje los circuitos y deje la red en el estado final deseado.");
    return;
  }
  const objetivo = operacionesFinalesProtocolo();
  if (!objetivo.length) {
    alert("La red todavía conserva su estado normal. Realice en el mapa las aperturas, cierres, cortes, cruces o enlaces que desea analizar.");
    return;
  }
  setProceso("IA: analizando el estado final, fuentes, restricciones y secuencia de maniobras...", true);
  try {
    if(await recuperarDemostracionExactaIA(objetivo))return;
    await cargarOrigenesBarrasIA();
    await abrirProtocoloManiobras();
    const titulo = document.querySelector("#protocol-modal-title");
    if (titulo) titulo.textContent = "Protocolo IA para el estado final dibujado";
    setProceso("Análisis IA terminado. Revise o simule el protocolo paso a paso.");
    abrirChatProtocoloIA();
    mensajeChatIA("El protocolo está disponible. Puedes preguntarme por los pasos o corregirlo para enseñarme una alternativa mejor.");
  } catch (error) {
    setProceso("La IA necesita una demostración del operador: " + error.message);
    abrirChatProtocoloIA(error.message);
    await iniciarEnsenanzaManualIA();
  }
};
