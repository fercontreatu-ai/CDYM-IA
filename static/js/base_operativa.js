(function(){
  "use strict";
  let procedenciaBase=new Map();
  const calcularEnergiaOriginal=calcularEnergia;
  const entradasPatios=new Set(["P_IL10","P_IL20"]),salidaPatios="P_IL30",alimentadoresPatios=new Set(["PATC1","PATC2","PATC3","PATIOS"]);

  calcularEnergia=function(resultados,override={},incluirVirtuales=true){
    const elementos=(resultados||[]).flatMap(x=>x.data?.elementos||[]),porCodigo=new Map(elementos.map(e=>[String(e.codigo||e.circuito||"").toUpperCase(),e])),cerrado=codigo=>{const e=porCodigo.get(codigo),fid=String(e?.g3e_fid||"");if(!e)return false;return String(override[fid]||e.estado_simulado||estadoBase(e)).toUpperCase()!=="OPEN";},barraPatiosEnergizable=[...entradasPatios].some(cerrado);
    const preparados=(resultados||[]).map(resultado=>{
      if(!resultado.data||String(resultado.item?.subestacion||resultado.data?.subestacion||"").toUpperCase()!=="PATIOS")return resultado;
      const circuito=String(resultado.item?.circuito||resultado.data?.raiz?.circuito||resultado.data?.raiz?.codigo||"").toUpperCase(),suprimir=circuito===salidaPatios||(!barraPatiosEnergizable&&alimentadoresPatios.has(circuito));
      if(!suprimir)return resultado;
      return{...resultado,item:{...resultado.item,fid:""},data:{...resultado.data,raiz:null}};
    });
    const flujo=calcularEnergiaOriginal(preparados,override,incluirVirtuales);
    flujo.nodoPatios={barraEnergizable:barraPatiosEnergizable,entradas:{P_IL10:cerrado("P_IL10"),P_IL20:cerrado("P_IL20")},salidaComoFuente:false,alimentadoresHabilitados:barraPatiosEnergizable};
    return flujo;
  };

  function mismasFuentes(a,b){
    if(a.size!==b.size)return false;
    for(const x of a)if(!b.has(x))return false;
    return true;
  }
  function aclarar(color,proporcion=.42){
    const valor=String(color||"").replace("#","");
    if(!/^[0-9a-f]{6}$/i.test(valor))return color;
    const canal=i=>Math.round(parseInt(valor.slice(i,i+2),16)+(255-parseInt(valor.slice(i,i+2),16))*proporcion).toString(16).padStart(2,"0");
    return `#${canal(0)}${canal(2)}${canal(4)}`;
  }
  function nombreFuentes(conjunto){return [...conjunto].map(k=>String(k).split("@")[0]);}

  const dibujarBase=dibujarTodo;
  dibujarTodo=async function(resultados,...args){
    const estados={};
    for(const resultado of resultados||[])for(const e of resultado.data?.elementos||[])estados[String(e.g3e_fid)]=estadoBase(e);
    const base=calcularEnergia(resultados,estados,false);
    procedenciaBase=base.procedencia;
    for(const e of base.elementos.values()){
      const fuentes=procedenciaBase.get(String(e.g3e_fid))||new Set(),nombres=nombreFuentes(fuentes);
      e._fuentes_base_operativa=[...fuentes];
      e._traslado_base_operativa=fuentes.size===1&&!nombres.includes(e.circuito);
    }
    return dibujarBase(resultados,...args);
  };

  estiloLinea=function(e,flujo,color){
    const fid=String(e.g3e_fid),feeds=new Set(flujo.procedencia.get(fid)||[]),baseFeeds=new Set(procedenciaBase.get(fid)||[]),powered=feeds.size>0,parallel=feeds.size>1,nombres=nombreFuentes(feeds),transferida=powered&&!nombres.includes(e.circuito),estable=mismasFuentes(feeds,baseFeeds),trasladoBase=transferida&&estable&&e._traslado_base_operativa,cortada=operacionesVirtuales.cortesLinea.has(fid)||operacionesVirtuales.brakesafes.get(fid)?.estado==="OPEN",colorFuente=flujo.coloresFuente.get([...feeds][0])||color;
    e._traslado_operativo_vigente=Boolean(trasladoBase);
    e._traslado_simulacion=Boolean(transferida&&!trasladoBase);
    return{color:cortada?"#d97706":powered?(trasladoBase?aclarar(colorFuente):colorFuente):"#ff0022",weight:cortada?6:powered?4:5,opacity:trasladoBase?0.88:0.92,dashArray:cortada?"3 7":(parallel||e._traslado_simulacion)?"10 8":null};
  };

  const datosBase=datosElectricos;
  datosElectricos=function(e,flujo){const d=datosBase(e,flujo);return{...d,trasladoOperativoVigente:Boolean(e._traslado_operativo_vigente),trasladoSimulacion:Boolean(e._traslado_simulacion)};};
})();
