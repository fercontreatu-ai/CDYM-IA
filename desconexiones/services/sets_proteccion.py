from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings


def normalizar_codigo(valor) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(valor or "").upper())


@lru_cache(maxsize=1)
def catalogo_sets() -> dict:
    path = Path(settings.DATA_DIR) / "sets_proteccion_13_8.json"
    if not path.exists():
        return {"alimentadores": {}, "dispositivos_linea": {}}
    with path.open("r", encoding="utf-8") as entrada:
        return json.load(entrada)


def set_sugerido(objeto: dict) -> tuple[float | None, str]:
    catalogo = catalogo_sets()
    fno = int(objeto.get("g3e_fno") or 0)
    codigos = [
        normalizar_codigo(objeto.get("codigo")),
        normalizar_codigo(objeto.get("circuito")),
        normalizar_codigo(objeto.get("marcacion")),
    ]
    grupo = "alimentadores" if fno == 18800 else "dispositivos_linea"
    for codigo in codigos:
        if codigo and codigo in catalogo.get(grupo, {}):
            return float(catalogo[grupo][codigo]["set_a"]), "EXCEL"
    return None, ""
