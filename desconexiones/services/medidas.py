import json,re
from pathlib import Path
from django.conf import settings
CATALOGO=Path(settings.DATA_DIR)/"catalogo_medidas_alimentadores.json"
PRIORIDAD_FUENTE={"MED":0,"REL":1,"REC":2,"":3}
def normalizar(valor):return re.sub(r"[^A-Z0-9]","",str(valor or "").upper())
def cargar_catalogo():
    if not CATALOGO.exists():raise FileNotFoundError("No existe el catálogo liviano de medidas de alimentadores.")
    with CATALOGO.open("r",encoding="utf-8") as entrada:return json.load(entrada)
def medidas_subestacion(subestacion,niveles=(13.8,34.5)):
    clave=normalizar(subestacion);resultado=[]
    for item in cargar_catalogo().get("medidas",[]):
        if normalizar(item["subestacion"])!=clave or float(item["nivel_kv"]) not in niveles:continue
        for fuente in item.get("fuentes") or [""]:resultado.append({**item,"fuente":fuente})
    return sorted(resultado,key=lambda x:(float(x["nivel_kv"]),x["interruptor"],PRIORIDAD_FUENTE.get(x["fuente"],9)))
def coincidencia_preferida(dispositivo,medidas,nivel_kv):
    nombres={normalizar(dispositivo.get(k)) for k in ("codigo","marcacion","circuito")};nombres.discard("")
    candidatas=[m for m in medidas if float(m["nivel_kv"])==float(nivel_kv) and normalizar(m["interruptor"]) in nombres]
    return min(candidatas,key=lambda x:PRIORIDAD_FUENTE.get(x["fuente"],9),default=None)
