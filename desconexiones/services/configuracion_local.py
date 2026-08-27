from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def ruta_configuracion() -> Path:
    explicita = os.getenv("CDYM_LOCAL_CONFIG_FILE", "").strip()
    if explicita:
        return Path(explicita).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / ".cdym"
    return base / "CDYM" / "config.json"


def cargar_configuracion() -> dict:
    ruta = ruta_configuracion()
    contenido = {}
    if ruta.is_file():
        try:
            contenido = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            contenido = {}
    impuesta = os.getenv("CDYM_SCADA_DATA_DIR", "").strip()
    if impuesta:
        contenido["scada_data_dir"] = impuesta
        contenido["scada_data_dir_impuesta"] = True
    return contenido


def validar_carpeta_scada(valor: str) -> dict:
    texto = str(valor or "").strip().strip('"')
    if not texto:
        return {"ruta": "", "existe": False, "valida": False, "mensaje": "Seleccione la carpeta raíz de datos SCADA."}
    ruta = Path(texto).expanduser()
    try:
        resuelta = ruta.resolve()
        existe = resuelta.is_dir()
    except OSError:
        resuelta, existe = ruta, False
    anios = []
    if existe:
        try:
            anios = sorted(p.name for p in resuelta.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 4)
        except OSError:
            existe = False
    valida = existe and bool(anios)
    if not existe:
        mensaje = "La carpeta no existe o no está disponible."
    elif not anios:
        mensaje = "La carpeta existe, pero no contiene subcarpetas anuales como 2025 o 2026."
    else:
        mensaje = f"Carpeta disponible. Años encontrados: {', '.join(anios)}."
    return {"ruta": str(resuelta), "existe": existe, "valida": valida, "anios": anios, "mensaje": mensaje}


def guardar_carpeta_scada(valor: str) -> dict:
    if os.getenv("CDYM_SCADA_DATA_DIR", "").strip():
        raise ValueError("La ruta está impuesta mediante CDYM_SCADA_DATA_DIR y no puede cambiarse desde Admin.")
    estado = validar_carpeta_scada(valor)
    if not estado["valida"]:
        raise ValueError(estado["mensaje"])
    ruta = ruta_configuracion()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido = cargar_configuracion()
    contenido.pop("scada_data_dir_impuesta", None)
    contenido["scada_data_dir"] = estado["ruta"]
    descriptor, temporal = tempfile.mkstemp(prefix="config-", suffix=".json", dir=ruta.parent)
    os.close(descriptor)
    temporal_path = Path(temporal)
    try:
        temporal_path.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal_path.replace(ruta)
    finally:
        temporal_path.unlink(missing_ok=True)
    return estado


def estado_carpeta_scada() -> dict:
    config = cargar_configuracion()
    estado = validar_carpeta_scada(config.get("scada_data_dir", ""))
    estado["impuesta"] = bool(config.get("scada_data_dir_impuesta"))
    estado["archivo_configuracion"] = str(ruta_configuracion())
    return estado

