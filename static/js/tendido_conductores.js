(function(){
  "use strict";

  let ultimoResultadoMedidas=[];
  const calcularAnalisisBase=calcularAnalisisConductores;
  calcularAnalisisConductores=function(ajustadas){
    ultimoResultadoMedidas=Array.isArray(ajustadas)?ajustadas:[];
    return calcularAnalisisBase(ajustadas);
  };

  const detalleLineaBase=contenidoDetalleLinea;
  function lineasConectadas(elemento){
    const codigo=String(elemento.codigo_conductor||"").toUpperCase();
    const circuito=String(elemento.circuito||"").toUpperCase();
    const subestacion=String(elemento.subestacion||"").toUpperCase();
    const candidatas=[...(ultimoFlujo?.elementos.values()||[])].filter(x=>Number(x.g3e_fno)===19000&&String(x.codigo_conductor||"").toUpperCase()===codigo&&String(x.circuito||"").toUpperCase()===circuito&&String(x.subestacion||"").toUpperCase()===subestacion);
    const porNodo=new Map();
    for(const linea of candidatas)for(const nodo of [linea.nodo1,linea.nodo2]){
      const clave=String(nodo??"");if(!clave)continue;
      if(!porNodo.has(clave))porNodo.set(clave,[]);
      porNodo.get(clave).push(linea);
    }
    const resultado=[],visitados=new Set(),pendientes=[elemento];
    while(pendientes.length){
      const linea=pendientes.pop(),fid=String(linea.g3e_fid);
      if(visitados.has(fid))continue;
      visitados.add(fid);resultado.push(linea);
      for(const nodo of [linea.nodo1,linea.nodo2])for(const vecina of porNodo.get(String(nodo??""))||[])if(!visitados.has(String(vecina.g3e_fid)))pendientes.push(vecina);
    }
    return resultado;
  }
  contenidoDetalleLinea=function(elemento){
    const detalle=detalleLineaBase(elemento);
    const ducto=Number(elemento.ampacidad_ducto_a);
    const aire=Number(elemento.ampacidad_aire_a);
    if(!Number.isFinite(ducto)||!Number.isFinite(aire))return detalle;
    const tipo=String(elemento.tipo_tendido||"").toUpperCase();
    const cantidad=lineasConectadas(elemento).length;
    const control=`<section class="conductor-installation"><label for="conductor-installation-${elemento.g3e_fid}">Tipo de tendido del tramo conectado (${cantidad} linea${cantidad===1?"":"s"})</label><select id="conductor-installation-${elemento.g3e_fid}" onchange="guardarTipoTendidoConductor(${elemento.g3e_fid})"><option value=""${tipo?"":" selected"}>Seleccione...</option><option value="DUCTO"${tipo==="DUCTO"?" selected":""}>Ducto / subterraneo · ${numeroEje(ducto)} A</option><option value="AIRE"${tipo==="AIRE"?" selected":""}>Aire · ${numeroEje(aire)} A</option></select><small id="conductor-installation-status-${elemento.g3e_fid}">${tipo?`Configuracion guardada: ${tipo==="DUCTO"?"ducto / subterraneo":"aire"}. Se conserva para estas lineas conectadas.`:"Seleccione la condicion real de instalacion antes de evaluar la cargabilidad."}</small></section>`;
    return control+detalle;
  };

  window.guardarTipoTendidoConductor=async function(fid){
    const elemento=ultimoFlujo?.elementos.get(String(fid));
    const selector=document.querySelector(`#conductor-installation-${fid}`);
    const estado=document.querySelector(`#conductor-installation-status-${fid}`);
    const tipo=selector?.value||"";
    if(!elemento||!tipo)return;
    selector.disabled=true;
    estado.className="";
    estado.textContent="Guardando configuracion y recalculando el analisis actual...";
    try{
      const conectadas=lineasConectadas(elemento),fids=conectadas.map(x=>x.g3e_fid);
      const respuesta=await fetch(APP.guardarTendidoConductor,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":APP.csrf},body:JSON.stringify({subestacion:elemento.subestacion,circuito:elemento.circuito,codigo_conductor:elemento.codigo_conductor,g3e_fids:fids,tipo_tendido:tipo})});
      const datos=await respuesta.json();
      if(!respuesta.ok)throw new Error(datos.error||"No fue posible guardar el tipo de tendido.");
      const fidsGuardados=new Set(datos.g3e_fids.map(String));
      for(const linea of ultimoFlujo.elementos.values()){
        if(!fidsGuardados.has(String(linea.g3e_fid)))continue;
        linea.tipo_tendido=datos.tipo_tendido;
        linea.ampacidad_a=datos.ampacidad_a;
      }
      if(ultimoResultadoMedidas.length){
        ultimoResultadoMedidas.forEach(x=>{x.conductores=[];});
        calcularAnalisisBase(ultimoResultadoMedidas);
        actualizarAlertasAnalisisMapa(ultimoResultadoMedidas);
      }
      estado.className="saved";
      estado.textContent=`Guardado en ${datos.g3e_fids.length} linea(s) conectada(s): ${datos.tipo_tendido==="DUCTO"?"ducto / subterraneo":"aire"}, ampacidad usada ${numeroEje(datos.ampacidad_a)} A. No se repitio la consulta historica.`;
      const ampacidad=document.querySelector(`#trafo-modal-body .trafo-grid div:nth-child(11) span`);
      if(ampacidad)ampacidad.textContent=`${numeroEje(datos.ampacidad_a)} A`;
    }catch(error){
      estado.className="error";
      estado.textContent=error.message;
      selector.value=elemento.tipo_tendido||"";
    }finally{selector.disabled=false;}
  };
})();
