import csv
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings


ARCHIVO = Path(settings.DATA_DIR) / "consumos_transformadores_202607.csv"


def _clave(valor):
    return re.sub(r"[^A-Z0-9]", "", str(valor or "").upper())


def _numero_colombiano(valor):
    texto=str(valor or "").strip()
    if not texto:return None
    try:return float(texto.replace(".", "").replace(",", "."))
    except ValueError:return None


@lru_cache(maxsize=4)
def _cargar_catalogo(ruta, modificado_ns):
    catalogo={}
    with Path(ruta).open("r",encoding="cp1252",newline="") as archivo:
        for fila in csv.DictReader(archivo,delimiter=";"):
            codigo=_clave(fila.get("TRANSFORMADOR"))
            if not codigo:continue
            catalogo[codigo]={
                "periodo_consumo_transformador":str(fila.get("PERIODO") or "").strip(),
                # ENERGIASALIDA es la energía mensual agregada entregada a las
                # cargas conectadas al transformador; no es consumo por usuario.
                "consumo_transformador_kwh":_numero_colombiano(fila.get("ENERGIASALIDA")),
                "energia_entrada_transformador_kwh":_numero_colombiano(fila.get("ENERGIAENTRADA")),
                "capacidad_consumos_kva":_numero_colombiano(fila.get("KVA")),
                "municipio":str(fila.get("MUNICIPIO") or "").strip(),
                "cantidad_usuarios_consumos":int(_numero_colombiano(fila.get("CANT_USU_TOTAL")) or _numero_colombiano(fila.get("CANT_USU")) or 0),
                "clientes_otro_comercializador":int(_numero_colombiano(fila.get("CLIENTES_OC")) or 0),
                "consumo_otro_comercializador_kwh":_numero_colombiano(fila.get("CONSUMO_OTROS")) or 0,
                "fuente_consumo_transformador":"BD_MACRO_202607",
            }
    return catalogo


def catalogo_consumos_transformadores():
    if not ARCHIVO.exists():return {}
    return _cargar_catalogo(str(ARCHIVO),ARCHIVO.stat().st_mtime_ns)


def aplicar_consumos_transformadores(data):
    catalogo=catalogo_consumos_transformadores()
    encontrados=0;capacidad=0
    for elemento in data.get("elementos",[]):
        if int(elemento.get("g3e_fno") or 0)!=20400:continue
        detalle=None
        for codigo in (elemento.get("codigo_operacion"),elemento.get("codigo"),elemento.get("numero_transformador")):
            if _clave(codigo) in catalogo:
                detalle=catalogo[_clave(codigo)];break
        if detalle:
            elemento.update(detalle);encontrados+=1
            elemento["criterio_peso_carga"]="CONSUMO_TRANSFORMADOR" if (detalle.get("consumo_transformador_kwh") or 0)>0 else "CAPACIDAD_TRANSFORMADOR"
        else:
            capacidad+=1;elemento["criterio_peso_carga"]="CAPACIDAD_TRANSFORMADOR"
            elemento["fuente_consumo_transformador"]="CAPACIDAD_GTECH"
    data["cobertura_consumos_transformadores"]={"con_consumo":encontrados,"por_capacidad":capacidad,"fuente":ARCHIVO.name}
    data["fuente_potencias"]="EXCEL_CONSUMOS_TRANSFORMADORES"
    data["descripcion_fuente_potencias"]=f"{ARCHIVO.name}: {encontrados} transformador(es) por consumo y {capacidad} por capacidad instalada"
    data["fuente_consumos_usuarios"]="NO_APLICA_CONSUMO_AGREGADO_POR_TRANSFORMADOR"
    return data
