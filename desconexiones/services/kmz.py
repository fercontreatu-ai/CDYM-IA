from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MAX_ARCHIVO_BYTES = 30 * 1024 * 1024
MAX_KML_BYTES = 100 * 1024 * 1024


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _primero(elemento, nombre):
    return next((n for n in elemento.iter() if _local(n.tag) == nombre), None)


def _texto(elemento, nombre, predeterminado=""):
    nodo = _primero(elemento, nombre)
    return (nodo.text or "").strip() if nodo is not None else predeterminado


def _coordenadas(texto):
    salida = []
    for token in (texto or "").replace("\n", " ").replace("\t", " ").split():
        try:
            partes = token.split(",")
            punto = [float(partes[0]), float(partes[1])]
            if len(partes) > 2 and partes[2] != "":
                punto.append(float(partes[2]))
            salida.append(punto)
        except (IndexError, ValueError):
            continue
    return salida


def _geometria(elemento):
    tipo = _local(elemento.tag)
    if tipo == "Point":
        puntos = _coordenadas(_texto(elemento, "coordinates"))
        return {"type": "Point", "coordinates": puntos[0]} if puntos else None
    if tipo == "LineString":
        puntos = _coordenadas(_texto(elemento, "coordinates"))
        return {"type": "LineString", "coordinates": puntos} if len(puntos) >= 2 else None
    if tipo == "Polygon":
        anillos = []
        for borde in (n for n in elemento.iter() if _local(n.tag) in {"outerBoundaryIs", "innerBoundaryIs"}):
            puntos = _coordenadas(_texto(borde, "coordinates"))
            if len(puntos) >= 3:
                if puntos[0][:2] != puntos[-1][:2]:
                    puntos.append(puntos[0])
                anillos.append(puntos)
        return {"type": "Polygon", "coordinates": anillos} if anillos else None
    if tipo == "Track":
        puntos = []
        for nodo in elemento.iter():
            if _local(nodo.tag) != "coord":
                continue
            try:
                partes = [float(x) for x in (nodo.text or "").split()]
                if len(partes) >= 2:
                    puntos.append(partes[:3])
            except ValueError:
                continue
        return {"type": "LineString", "coordinates": puntos} if len(puntos) >= 2 else None
    if tipo in {"MultiGeometry", "MultiTrack"}:
        geometrias = [geo for hijo in elemento if (geo := _geometria(hijo))]
        if not geometrias:
            return None
        tipos = {geo["type"] for geo in geometrias}
        if len(tipos) == 1 and next(iter(tipos)) in {"Point", "LineString", "Polygon"}:
            base = next(iter(tipos))
            return {"type": f"Multi{base}", "coordinates": [geo["coordinates"] for geo in geometrias]}
        return {"type": "GeometryCollection", "geometries": geometrias}
    return None


def _propiedades(placemark):
    salida = {"nombre": _texto(placemark, "name", "Elemento sin nombre"), "descripcion": _texto(placemark, "description")}
    for nodo in placemark.iter():
        tipo = _local(nodo.tag)
        if tipo == "Data":
            clave, valor = (nodo.attrib.get("name") or "").strip(), _texto(nodo, "value")
        elif tipo == "SimpleData":
            clave, valor = (nodo.attrib.get("name") or "").strip(), (nodo.text or "").strip()
        else:
            continue
        if clave:
            salida[clave] = valor
    return salida


def kml_a_geojson(contenido):
    try:
        raiz = ElementTree.fromstring(contenido)
    except ElementTree.ParseError as exc:
        raise ValueError(f"El KML interno no es válido: {exc}") from exc
    features = []
    compatibles = {"Point", "LineString", "Polygon", "MultiGeometry", "Track", "MultiTrack"}
    for placemark in (n for n in raiz.iter() if _local(n.tag) == "Placemark"):
        propiedades = _propiedades(placemark)
        for hijo in placemark:
            if _local(hijo.tag) not in compatibles:
                continue
            geometria = _geometria(hijo)
            if geometria:
                features.append({"type": "Feature", "properties": propiedades, "geometry": geometria})
    if not features:
        raise ValueError("El archivo no contiene puntos, líneas o polígonos compatibles.")
    return {"type": "FeatureCollection", "features": features}


def leer_kmz(archivo):
    nombre = Path(archivo.name or "proyecto.kmz").name
    if getattr(archivo, "size", 0) > MAX_ARCHIVO_BYTES:
        raise ValueError("El KMZ supera el tamaño máximo permitido de 30 MB.")
    contenido = archivo.read()
    if nombre.lower().endswith(".kml"):
        return nombre, kml_a_geojson(contenido)
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as kmz:
            candidatos = [i for i in kmz.infolist() if not i.is_dir() and i.filename.lower().endswith(".kml")]
            if not candidatos:
                raise ValueError("El KMZ no contiene un archivo KML.")
            principal = next((i for i in candidatos if Path(i.filename).name.lower() == "doc.kml"), candidatos[0])
            if principal.file_size > MAX_KML_BYTES:
                raise ValueError("El KML interno supera el tamaño máximo permitido de 100 MB.")
            return nombre, kml_a_geojson(kmz.read(principal))
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo KMZ está dañado o no es un ZIP válido.") from exc
