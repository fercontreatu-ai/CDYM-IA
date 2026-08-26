import re
from collections import defaultdict


def caracteristica_paso(paso):
    tipo=re.sub(r"[^a-z0-9]+","_",str(paso.get("tipo") or "dispositivo").lower()).strip("_")
    accion=str(paso.get("actual") or paso.get("accion") or "").upper()
    fno=str(paso.get("fno") or "")
    return f"{fno}:{tipo}:{accion}"


def reconstruir_preferencias(eventos):
    posiciones=defaultdict(list)
    precedencias=defaultdict(int)
    ejemplos=0
    for evento in eventos:
        protocolo=evento.protocolo_corregido or []
        if not protocolo:
            continue
        ejemplos+=1
        claves=[caracteristica_paso(p) for p in protocolo]
        total=max(1,len(claves)-1)
        for indice,clave in enumerate(claves):
            posiciones[clave].append(indice/total)
        for indice,a in enumerate(claves):
            for b in claves[indice+1:]:
                if a!=b:
                    precedencias[f"{a}>{b}"]+=1
    ranking={clave:sum(valores)/len(valores) for clave,valores in posiciones.items()}
    return {"ranking":ranking,"precedencias":dict(precedencias),"ejemplos":ejemplos,"version":1}
