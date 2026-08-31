from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager

from .tc1 import TC1Service

FNO_TIPOS = {17600: "Generador", 17900: "Puesta a Tierra", 18700: "Barraje Subestación", 18800: "Interruptor", 19000: "Conductor Primario", 19300: "Aisladero", 19400: "Cuchilla", 19600: "Seccionalizador", 19700: "Suiche", 19800: "Reconectador", 20100: "Pararrayos", 20200: "Capacitor", 20300: "Regulador", 20400: "Transformador", 20600: "Bajante", 22300: "Punto de Medida"}
FNO_NO_VISIBLES = {17900, 20100}
FNO_RED = tuple(fno for fno in FNO_TIPOS if fno not in FNO_NO_VISIBLES)
FNO_CORTE = {18800, 19300, 19400, 19600, 19700, 19800, 20400}
_TRACE_CACHE = {}
_TRACE_CACHE_LOCK = threading.RLock()
_TRACE_CACHE_SECONDS = 600
_CATALOG_CACHE = {}
_CATALOG_CACHE_LOCK = threading.RLock()
_CATALOG_CACHE_SECONDS = int(os.getenv("GTECH_CATALOG_CACHE_SECONDS", "600"))

_UC_RA2_PASO = {
    101, 201, 205, 301, 305, 401, 406, 511, 514, 535,
    701, 702, 703, 704, 712, 713, 715, 716, 718, 719,
    801, 802, 1001, 1002,
}
_UC_RA2_RETENCION = {
    102, 103, 104, 202, 203, 204, 206, 207, 208, 209,
    302, 303, 304, 306, 307, 308, 402, 403, 404, 405,
    407, 408, 409, 410, 532, 543, 546, 641, 705, 706,
    707, 708, 709, 710, 711, 714, 717, 720, 803, 804,
    805, 806, 1003, 1004,
}


def _nodos_barras(filas) -> set[int]:
    """Incluye ambos terminales de cada barra GTECH."""
    return {int(nodo) for fila in filas for nodo in fila if nodo}


def _clasificar_estructura_poste(tipo_adecuacion: str, tipo_instalacion: str, unidades: list[dict]) -> tuple[str, str]:
    """Clasifica por atributos constructivos GTech; nunca usa la geometría de la red."""
    atributos = " ".join((str(tipo_adecuacion or ""), str(tipo_instalacion or ""))).upper()
    if any(x in atributos for x in ("RETEN", "TERMINAL", "ANGULO", "ÁNGULO", "ANCLA", "DERIV")):
        return "RETENCION", "TIPO_ADECUACION"
    if any(x in atributos for x in ("SUSPENSION", "SUSPENSIÓN", "PASO")):
        return "PASO", "TIPO_ADECUACION"

    textos = " ".join(f"{x.get('norma','')} {x.get('grupo','')}" for x in unidades).upper()
    if any(x in textos for x in ("RETEN", "TERMINAL", "ANGULO", "ÁNGULO", "ANCLA", "DERIV")):
        return "RETENCION", "UNIDAD_CONSTRUCTIVA"
    if any(x in textos for x in ("SUSPENSION", "SUSPENSIÓN", "PASO")):
        return "PASO", "UNIDAD_CONSTRUCTIVA"

    codigos = {
        int(match.group(1))
        for unidad in unidades
        for match in [re.search(r"(?:NC-)?RA2-(\d{3,4})(?:-\d+)?\b", str(unidad.get("norma") or "").upper())]
        if match
    }
    if codigos.intersection(_UC_RA2_RETENCION):
        return "RETENCION", "UNIDAD_CONSTRUCTIVA"
    if codigos.intersection(_UC_RA2_PASO):
        return "PASO", "UNIDAD_CONSTRUCTIVA"
    return "SIN_CLASIFICAR", "SIN_DATO_CONSTRUCTIVO"


def _catalog_cache_get(key):
    with _CATALOG_CACHE_LOCK:
        cached = _CATALOG_CACHE.get(key)
        if cached and time.monotonic() - cached[0] < _CATALOG_CACHE_SECONDS:
            return copy.deepcopy(cached[1])
    return None


def _catalog_cache_set(key, value):
    with _CATALOG_CACHE_LOCK:
        _CATALOG_CACHE[key] = (time.monotonic(), copy.deepcopy(value))
        if len(_CATALOG_CACHE) > 256:
            oldest = min(_CATALOG_CACHE, key=lambda item: _CATALOG_CACHE[item][0])
            _CATALOG_CACHE.pop(oldest, None)
    return value


class GTechService:
    """Consulta de solo lectura de la red CENS de 34,5 kV."""

    def __init__(self):
        self.schema = os.getenv("ORACLE_SCHEMA", "GENERGIA")
        self.link = os.getenv("ORACLE_DB_LINK", "GTECH")

    def q(self, table: str) -> str:
        return f"{self.schema}.{table}@{self.link}"

    @staticmethod
    def _subestacion_normalizada(campo: str) -> str:
        return f"REPLACE(REPLACE(UPPER(TRIM({campo})),'R6-S/E ',''),' ','_')"

    @contextmanager
    def connection(self):
        import oracledb
        oracledb.defaults.fetch_lobs = False
        conn = oracledb.connect(user=os.environ["ORACLE_USER"], password=os.environ["ORACLE_PASSWORD"], host=os.environ["ORACLE_HOST"], port=int(os.getenv("ORACLE_PORT", "1521")), service_name=os.environ["ORACLE_SERVICE_NAME"])
        try:
            yield conn
        finally:
            conn.close()

    def listar_subestaciones(self) -> list[dict]:
        cache_key = ("subestaciones",)
        cached = _catalog_cache_get(cache_key)
        if cached is not None:
            return cached
        sql = f"""SELECT DISTINCT UPPER(TRIM(S.CODIGO)) FROM {self.q('ESUBESTA_AT')} S JOIN {self.q('CCOMUN')} M ON M.G3E_FID=S.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND S.CODIGO IS NOT NULL ORDER BY 1"""
        with self.connection() as conn:
            cur = conn.cursor(); cur.execute(sql)
            return _catalog_cache_set(cache_key, [{"codigo": str(r[0]).strip().upper()} for r in cur.fetchall()])

    def listar_interruptores(self, subestacion: str, circuito: str = "") -> list[dict]:
        sub_normalizada = subestacion.strip().upper().replace(" ", "_")
        circuito_normalizado = circuito.strip().upper()
        cache_key = ("interruptores", sub_normalizada, circuito_normalizado)
        cached = _catalog_cache_get(cache_key)
        if cached is not None:
            return cached
        filtros = ["M.EMPRESA_ORIGEN='CENS'", "C.G3E_FNO=18800", "REPLACE(TRIM(C.TENSION),',','.') IN ('13.8','34.5')", f"{self._subestacion_normalizada('C.SUBESTACION')}=:sub"]
        params = {"sub": sub_normalizada}
        if circuito:
            filtros.append("UPPER(TRIM(C.CIRCUITO))=:cto"); params["cto"] = circuito.strip().upper()
        sql = f"""SELECT C.G3E_FID,NVL(TRIM(M.CODIGO_OPERATIVO),TO_CHAR(C.G3E_FID)),UPPER(TRIM(C.SUBESTACION)),UPPER(TRIM(C.CIRCUITO)),NVL(TRIM(C.EST_OPERATIVO),''),NVL(TRIM(M.CODIGO_MARCACION),''),C.NODO1_ID,C.NODO2_ID,REPLACE(TRIM(C.TENSION),',','.') FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID WHERE {' AND '.join(filtros)} ORDER BY TO_NUMBER(REPLACE(TRIM(C.TENSION),',','.')) DESC,4,2"""
        with self.connection() as conn:
            cur = conn.cursor(); cur.execute(sql, params)
            resultado = [{"g3e_fid": int(r[0]), "codigo": str(r[1]).strip(), "subestacion": str(r[2]).strip(), "circuito": str(r[3] or "SIN CIRCUITO").strip(), "estado": str(r[4]).strip().upper(), "marcacion": str(r[5]).strip(), "nodo1": int(r[6] or 0), "nodo2": int(r[7] or 0), "tension": str(r[8]).strip()} for r in cur.fetchall()]
            return _catalog_cache_set(cache_key, resultado)

    def listar_circuitos(self, subestacion: str) -> list[dict]:
        interruptores=self.listar_interruptores(subestacion)
        barras=self.listar_barras_dispositivos(subestacion)
        barra_por_interruptor={int(d["g3e_fid"]):(int(b["g3e_fid"]),b["codigo"]) for b in barras for d in b.get("dispositivos",[]) if d.get("g3e_fno")==18800}
        return [{"codigo":x["circuito"],"interruptor":x["codigo"],"marcacion":x["marcacion"],"g3e_fid":x["g3e_fid"],"tension":x["tension"],"barra_fid":barra_por_interruptor.get(x["g3e_fid"],(None,""))[0],"barra_codigo":barra_por_interruptor.get(x["g3e_fid"],(None,""))[1]} for x in interruptores]

    def listar_barras_dispositivos(self, subestacion: str) -> list[dict]:
        subestacion=subestacion.strip().upper().replace(" ", "_")
        cache_key = ("barras", subestacion)
        cached = _catalog_cache_get(cache_key)
        if cached is not None:
            return cached
        with self.connection() as conn:
            cur=conn.cursor()
            cur.arraysize=2000;cur.prefetchrows=2000
            cur.execute(f"""SELECT MAX(NVL(S.MAIN_KV,0)) FROM {self.q('ESUBESTA_AT')} S JOIN {self.q('CCOMUN')} M ON M.G3E_FID=S.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND UPPER(TRIM(S.CODIGO))=:sub""",{"sub":subestacion})
            main_kv=float(cur.fetchone()[0] or 0)
            cur.execute(f"""SELECT C.G3E_FID,NVL(TRIM(M.CODIGO_OPERATIVO),TO_CHAR(C.G3E_FID)),NVL(TRIM(M.CODIGO_MARCACION),''),REPLACE(TRIM(C.TENSION),',','.'),NVL(C.NODO1_ID,0),NVL(C.NODO2_ID,0) FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND C.G3E_FNO=18700 AND {self._subestacion_normalizada('C.SUBESTACION')}=:sub AND REPLACE(TRIM(C.TENSION),',','.') IN ('13.8','34.5') AND C.ESTADO<>'RETIRADO' ORDER BY TO_NUMBER(REPLACE(TRIM(C.TENSION),',','.')),2""",{"sub":subestacion})
            barras=[{"g3e_fid":int(r[0]),"codigo":str(r[1] or "").strip(),"marcacion":str(r[2] or "").strip(),"nivel_kv":float(str(r[3]).replace(",",".")),"main_kv":main_kv,"requiere_medida_central":float(str(r[3]).replace(",","."))==13.8 or (float(str(r[3]).replace(",","."))==34.5 and main_kv>34.5),"nodos":[int(n) for n in (r[4],r[5]) if n]} for r in cur.fetchall()]
            nodos=sorted({n for b in barras for n in b["nodos"]})
            dispositivos=[]
            for inicio in range(0,len(nodos),400):
                lote=nodos[inicio:inicio+400]
                if not lote:continue
                binds=",".join(f":n{i}" for i in range(len(lote)));params={f"n{i}":n for i,n in enumerate(lote)}
                cur.execute(f"""SELECT C.G3E_FID,C.G3E_FNO,NVL(TRIM(M.CODIGO_OPERATIVO),TO_CHAR(C.G3E_FID)),NVL(TRIM(M.CODIGO_MARCACION),''),NVL(TRIM(C.CIRCUITO),''),REPLACE(TRIM(C.TENSION),',','.'),NVL(C.NODO1_ID,0),NVL(C.NODO2_ID,0) FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND C.G3E_FNO IN (18800,20400) AND C.ESTADO<>'RETIRADO' AND (C.NODO1_ID IN ({binds}) OR C.NODO2_ID IN ({binds}))""",params)
                dispositivos.extend({"g3e_fid":int(r[0]),"g3e_fno":int(r[1]),"tipo":"Interruptor" if int(r[1])==18800 else "Transformador","codigo":str(r[2] or "").strip(),"marcacion":str(r[3] or "").strip(),"circuito":str(r[4] or "").strip().upper(),"nivel_kv":float(str(r[5]).replace(",",".")),"nodos":[int(n) for n in (r[6],r[7]) if n]} for r in cur.fetchall())
        unicos={d["g3e_fid"]:d for d in dispositivos}
        for barra in barras:
            bn=set(barra["nodos"])
            barra["dispositivos"]=sorted((d for d in unicos.values() if bn.intersection(d["nodos"])),key=lambda d:(d["g3e_fno"],d["circuito"],d["codigo"]))
        return _catalog_cache_set(cache_key, barras)

    @staticmethod
    def _fila(r) -> dict:
        return {"g3e_fid": int(r[0]), "g3e_fno": int(r[1]), "codigo": str(r[2] or "").strip(), "marcacion": str(r[3] or "").strip(), "subestacion": str(r[4] or "").strip().upper(), "circuito": str(r[5] or "").strip().upper(), "nodo1": int(r[6] or 0), "nodo2": int(r[7] or 0), "estado": str(r[8] or "").strip().upper(), "estado_estable": str(r[9] or "").strip().upper(), "estado_operativo": str(r[10] or "").strip().upper(), "tipo": FNO_TIPOS.get(int(r[1]), f"FNO {r[1]}"), "calibre": str(r[11] or "").strip() if len(r) >= 15 else "", "material_conductor": str(r[12] or "").strip() if len(r) >= 15 else "", "tipo_conductor": str(r[13] or "").strip() if len(r) >= 15 else "", "codigo_conductor": str(r[14] or "").strip() if len(r) >= 15 else "", "ubicacion_gtech": str(r[15] or "").strip() if len(r) >= 18 else "", "gps_latitud": float(r[16]) if len(r) >= 18 and r[16] is not None else None, "gps_longitud": float(r[17]) if len(r) >= 18 and r[17] is not None else None, "longitud_m": float(r[18]) if len(r) >= 19 and r[18] is not None else None}

    def _elementos_circuitos(self, cur, circuitos: list[str], tension: str) -> list[dict]:
        binds = ",".join(f":c{i}" for i in range(len(circuitos)))
        params = {f"c{i}": c.upper() for i, c in enumerate(circuitos)}; params["tension"] = tension
        sql = f"""SELECT C.G3E_FID,C.G3E_FNO,NVL(M.CODIGO_OPERATIVO,''),NVL(M.CODIGO_MARCACION,''),NVL(C.SUBESTACION,''),NVL(C.CIRCUITO,''),NVL(C.NODO1_ID,0),NVL(C.NODO2_ID,0),NVL(C.ESTADO,''),NVL(C.EST_ESTABLE,''),NVL(C.EST_OPERATIVO,''),NVL(P.CALIBRE,''),NVL(P.MATERIAL,''),NVL(P.TIPO_CONDUCTOR,''),NVL(P.CODE_CONDUCTOR,''),NVL(M.UBICACION,''),M.COOR_GPS_LAT,M.COOR_GPS_LON,C.LONGITUD FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID LEFT JOIN {self.q('ECON_PRI_AT')} P ON P.G3E_FID=C.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND REPLACE(TRIM(C.TENSION),',','.')=:tension AND UPPER(TRIM(C.CIRCUITO)) IN ({binds}) AND C.ESTADO<>'RETIRADO' AND C.G3E_FNO IN ({','.join(map(str,FNO_RED))})"""
        cur.execute(sql, params)
        return [self._fila(r) for r in cur.fetchall()]

    def _vecinos(self, cur, nodos: list[int], tension: str) -> list[dict]:
        resultado = []
        for inicio in range(0, len(nodos), 250):
            lote = nodos[inicio:inicio+250]; binds = ",".join(f":n{i}" for i in range(len(lote))); params = {f"n{i}": n for i,n in enumerate(lote)}; params["tension"] = tension
            sql = f"""SELECT C.G3E_FID,C.G3E_FNO,NVL(M.CODIGO_OPERATIVO,''),NVL(M.CODIGO_MARCACION,''),NVL(C.SUBESTACION,''),NVL(C.CIRCUITO,''),NVL(C.NODO1_ID,0),NVL(C.NODO2_ID,0),NVL(C.ESTADO,''),NVL(C.EST_ESTABLE,''),NVL(C.EST_OPERATIVO,''),NVL(P.CALIBRE,''),NVL(P.MATERIAL,''),NVL(P.TIPO_CONDUCTOR,''),NVL(P.CODE_CONDUCTOR,''),NVL(M.UBICACION,''),M.COOR_GPS_LAT,M.COOR_GPS_LON,C.LONGITUD FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID LEFT JOIN {self.q('ECON_PRI_AT')} P ON P.G3E_FID=C.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND REPLACE(TRIM(C.TENSION),',','.')=:tension AND C.ESTADO<>'RETIRADO' AND C.G3E_FNO IN ({','.join(map(str,FNO_RED))}) AND (C.NODO1_ID IN ({binds}) OR C.NODO2_ID IN ({binds}))"""
            cur.execute(sql, params); resultado.extend(self._fila(r) for r in cur.fetchall())
        return resultado

    def _postes_media_tension(self, cur, geometrias: dict) -> list[dict]:
        puntos, extremos, segmentos = [], [], []
        for geo in geometrias.values():
            grupos = geo.get("coordinates") or []
            if geo.get("type") != "MultiLineString":
                grupos = [grupos]
            for coords in grupos:
                validos = [(float(p[0]), float(p[1])) for p in coords if len(p) >= 2]
                puntos.extend(validos)
                if validos:
                    extremos.extend((validos[0], validos[-1]))
                    segmentos.extend(zip(validos, validos[1:]))
        if not puntos:
            return []
        tamano_celda = .00025
        segmentos_por_celda = defaultdict(list)
        for segmento in segmentos:
            (ax, ay), (bx, by) = segmento
            ix0, ix1 = sorted((int(ax / tamano_celda), int(bx / tamano_celda)))
            iy0, iy1 = sorted((int(ay / tamano_celda), int(by / tamano_celda)))
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    segmentos_por_celda[(ix, iy)].append(segmento)
        minx, maxx = min(p[0] for p in puntos)-.00012, max(p[0] for p in puntos)+.00012
        miny, maxy = min(p[1] for p in puntos)-.00012, max(p[1] for p in puntos)+.00012
        sql = f"""SELECT P.G3E_FID,NVL(M.CODIGO_OPERATIVO,NVL(P.CODIGO,TO_CHAR(P.G3E_FID))),
        NVL(P.TIPO,''),NVL(P.MATERIAL,''),P.ALTURA,NVL(P.CLASE,''),NVL(P.USO,''),
        NVL(P.RESISTENCIA_KGF,''),NVL(P.TIPO_ADECUACION,''),NVL(P.TIPO_INSTALACION,''),
        M.COOR_GPS_LAT,M.COOR_GPS_LON,
        {','.join(f"NVL(N.NORMA{i},''),NVL(N.GRUPO{i},'')" for i in range(1,11))}
        FROM {self.q('EPOSTE_AT')} P JOIN {self.q('CCOMUN')} M ON M.G3E_FID=P.G3E_FID
        LEFT JOIN {self.q('B$NORMA_POSTE_AT')} N ON N.G3E_FID=P.G3E_FID
        WHERE M.EMPRESA_ORIGEN='CENS' AND M.COOR_GPS_LAT BETWEEN :miny AND :maxy
        AND M.COOR_GPS_LON BETWEEN :minx AND :maxx"""
        cur.execute(sql, {"minx":minx, "maxx":maxx, "miny":miny, "maxy":maxy})

        def distancia_segmento(px, py, a, b):
            ax,ay=a; bx,by=b; dx,dy=bx-ax,by-ay
            if not dx and not dy:
                return ((px-ax)**2+(py-ay)**2)**.5
            t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
            return ((px-(ax+t*dx))**2+(py-(ay+t*dy))**2)**.5

        postes = {}
        for r in cur.fetchall():
            lat, lon = r[10], r[11]
            if lat is None or lon is None:
                continue
            lon,lat=float(lon),float(lat)
            ix, iy = int(lon / tamano_celda), int(lat / tamano_celda)
            segmentos_cercanos = [segmento for dx in (-1, 0, 1) for dy in (-1, 0, 1) for segmento in segmentos_por_celda.get((ix + dx, iy + dy), ())]
            if segmentos and (not segmentos_cercanos or min(distancia_segmento(lon,lat,a,b) for a,b in segmentos_cercanos) > .00006):
                continue
            unidades=[{"norma":str(r[12+(i*2)] or "").strip(),"grupo":str(r[13+(i*2)] or "").strip()} for i in range(10)]
            unidades=[x for x in unidades if x["norma"] or x["grupo"]]
            estructura,fuente_estructura=_clasificar_estructura_poste(r[8],r[9],unidades)
            resistencia_texto=str(r[7] or "").strip()
            coincidencia_resistencia=re.search(r"\d+(?:[.,]\d+)?",resistencia_texto)
            resistencia_kgf=float(coincidencia_resistencia.group(0).replace(",",".")) if coincidencia_resistencia else None
            if resistencia_kgf is not None and resistencia_kgf < 50:resistencia_kgf=None
            postes[int(r[0])]={"g3e_fid":int(r[0]),"g3e_fno":17100,"codigo":str(r[1] or r[0]).strip(),
                "tipo":"Poste MT","tipo_poste":str(r[2]).strip(),"material":str(r[3]).strip(),
                "altura":float(r[4]) if r[4] is not None else None,"clase":str(r[5]).strip(),
                "uso":str(r[6] or "").strip(),"resistencia_kgf":resistencia_kgf,"resistencia_gtech":resistencia_texto,
                "tipo_adecuacion":str(r[8] or "").strip(),"tipo_instalacion":str(r[9] or "").strip(),
                "norma":unidades[0]["norma"] if unidades else "","grupo_norma":unidades[0]["grupo"] if unidades else "",
                "unidades_constructivas":unidades,"tipo_estructura":estructura,"fuente_tipo_estructura":fuente_estructura,
                "punto":[lon,lat]}
        return list(postes.values())
    @staticmethod
    def _camino(elementos: list[dict], raiz_fid: int, subestacion: str, nodo_barra: int, objetivo_sub: str = "") -> list[dict]:
        por_fid = {e["g3e_fid"]: e for e in elementos}; por_nodo = defaultdict(list)
        for e in elementos:
            if e["nodo1"]: por_nodo[e["nodo1"]].append(e)
            if e["nodo2"] and e["nodo2"] != e["nodo1"]: por_nodo[e["nodo2"]].append(e)
        raiz = por_fid.get(raiz_fid)
        if not raiz: return []
        salida = raiz["nodo2"] if raiz["nodo1"] == nodo_barra else raiz["nodo1"]
        cola = deque([(raiz_fid, salida)]); anterior = {raiz_fid: None}; objetivo = None
        while cola:
            fid, nodo_salida = cola.popleft(); actual = por_fid[fid]
            if fid != raiz_fid and actual["g3e_fno"] == 18800 and actual["subestacion"] != subestacion and (not objetivo_sub or actual["subestacion"] == objetivo_sub):
                objetivo = fid; break
            estado_corte = actual["estado_operativo"] or actual["estado_estable"]
            if fid != raiz_fid and actual["g3e_fno"] in FNO_CORTE and estado_corte == "OPEN":
                continue
            for nodo in (actual["nodo1"], actual["nodo2"]):
                if fid == raiz_fid and nodo != salida: continue
                for vecino in por_nodo.get(nodo, []):
                    vf = vecino["g3e_fid"]
                    if vf not in anterior:
                        anterior[vf] = fid; cola.append((vf, vecino["nodo2"] if vecino["nodo1"] == nodo else vecino["nodo1"]))
        if objetivo is None: return []
        fids=[]; actual=objetivo
        while actual is not None: fids.append(actual); actual=anterior[actual]
        return [por_fid[f] for f in reversed(fids)]

    @staticmethod
    def _red_alimentador(elementos: list[dict], raiz_fid: int, subestacion: str, nodo_barra: int) -> list[dict]:
        """Recorre todas las ramas desde el interruptor hasta sus limites electricos."""
        por_fid = {e["g3e_fid"]: e for e in elementos}
        por_nodo = defaultdict(list)
        for e in elementos:
            if e["nodo1"]:
                por_nodo[e["nodo1"]].append(e)
            if e["nodo2"] and e["nodo2"] != e["nodo1"]:
                por_nodo[e["nodo2"]].append(e)
        raiz = por_fid.get(raiz_fid)
        if not raiz:
            return []
        salida = raiz["nodo2"] if raiz["nodo1"] == nodo_barra else raiz["nodo1"]
        circuito_raiz = raiz["circuito"]
        incluidos = {raiz_fid}
        nodos_visitados = set()
        cola = deque([salida])
        while cola:
            nodo = cola.popleft()
            if not nodo or nodo in nodos_visitados:
                continue
            nodos_visitados.add(nodo)
            for equipo in por_nodo.get(nodo, []):
                fid = equipo["g3e_fid"]
                if fid == raiz_fid:
                    continue
                otra_celda = bool(equipo["circuito"] and equipo["circuito"] != circuito_raiz)
                # De la otra celda solo se muestra su equipo de frontera. No se
                # incorporan sus conductores ni se atraviesa hacia su red.
                if otra_celda:
                    if equipo["g3e_fno"] in FNO_CORTE:
                        equipo["frontera_externa"] = True
                        incluidos.add(fid)
                    continue
                incluidos.add(fid)
                # El limite se dibuja; solo se evita atravesarlo si esta abierto
                # o si corresponde al interruptor de otra subestacion.
                estado = equipo["estado_operativo"] or equipo["estado_estable"]
                remoto = equipo["g3e_fno"] == 18800 and equipo["subestacion"] != subestacion
                # El JSON conserva topologia, incluso a traves de dispositivos abiertos.
                # El estado OPEN se respeta despues en el calculo electrico del visor.
                if remoto:
                    equipo["frontera_externa"] = True
                    continue
                otro = equipo["nodo2"] if equipo["nodo1"] == nodo else equipo["nodo1"]
                if otro and otro not in nodos_visitados:
                    cola.append(otro)
        return [e for e in elementos if e["g3e_fid"] in incluidos]
    def trazar_circuito(self, subestacion: str, fid_raiz: int, force_refresh: bool = False) -> dict:
        subestacion = subestacion.strip().upper()
        cache_key = (subestacion, int(fid_raiz))
        with _TRACE_CACHE_LOCK:
            cached = _TRACE_CACHE.get(cache_key)
            if not force_refresh and cached and time.monotonic() - cached[0] < _TRACE_CACHE_SECONDS:
                return copy.deepcopy(cached[1])
        with self.connection() as conn:
            cur=conn.cursor()
            cur.arraysize=2000;cur.prefetchrows=2000
            cur.execute(f"""SELECT C.G3E_FID,C.G3E_FNO,NVL(M.CODIGO_OPERATIVO,''),NVL(M.CODIGO_MARCACION,''),NVL(C.SUBESTACION,''),NVL(C.CIRCUITO,''),NVL(C.NODO1_ID,0),NVL(C.NODO2_ID,0),NVL(C.ESTADO,''),NVL(C.EST_ESTABLE,''),NVL(C.EST_OPERATIVO,''),NVL(C.TENSION,'') FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID WHERE C.G3E_FID=:fid AND C.G3E_FNO=18800 AND M.EMPRESA_ORIGEN='CENS'""", {"fid":fid_raiz})
            row=cur.fetchone()
            if not row: raise ValueError("El interruptor seleccionado no existe en GTECH.")
            raiz=self._fila(row)
            tension=str(row[11] or '').strip().replace(',', '.')
            if tension not in {'13.8','34.5'}: raise ValueError('El interruptor debe ser de 13,8 o 34,5 kV.')
            raiz['tension']=tension
            cur.execute(f"""SELECT NVL(NODO1_ID,0),NVL(NODO2_ID,0) FROM {self.q('CCONECTIVIDAD_E')} WHERE G3E_FNO=18700 AND UPPER(TRIM(SUBESTACION))=:sub AND REPLACE(TRIM(TENSION),',','.')=:tension AND ESTADO<>'RETIRADO'""", {"sub":subestacion,"tension":tension})
            barras=_nodos_barras(cur.fetchall()); nodo_barra=next((n for n in (raiz['nodo1'],raiz['nodo2']) if n in barras),raiz['nodo1'])
            cur.execute(f"SELECT NVL(DIRECCION_SALIDA,''),NVL(DIRECCION_SALIDA2,''),NVL(SUB_FINAL,'') FROM {self.q('B$EINTERRU_AT')} WHERE G3E_FID=:fid", {"fid":fid_raiz})
            meta=cur.fetchone() or ("","","")
            texto_destino=" ".join(str(x or "").upper() for x in meta)
            cur.execute(f"SELECT UPPER(TRIM(CODIGO)) FROM {self.q('ESUBESTA_AT')} WHERE CODIGO IS NOT NULL")
            coincidencias=[str(r[0]).strip().upper() for r in cur.fetchall() if len(str(r[0]).strip()) >= 4 and str(r[0]).strip().upper() in texto_destino]
            objetivo_sub=max(coincidencias,key=len,default="")
            base=self._elementos_circuitos(cur,[raiz["circuito"]],tension)
            grados=defaultdict(int)
            for e in base:
                if e['nodo1']:grados[e['nodo1']]+=1
                if e['nodo2'] and e['nodo2']!=e['nodo1']:grados[e['nodo2']]+=1
            terminales=[n for n,g in grados.items() if g==1 and n!=nodo_barra]
            vecinos=self._vecinos(cur,terminales[:500],tension) if terminales else []
            candidatos=[]
            for e in vecinos:
                c=e['circuito']
                if c and c!=raiz['circuito'] and c not in candidatos:candidatos.append(c)
            if objetivo_sub:
                candidatos.sort(key=lambda c: 0 if any(e['circuito']==c and e['subestacion']==objetivo_sub for e in vecinos) else 1)
            elementos=base
            if candidatos: elementos=self._elementos_circuitos(cur,[raiz['circuito']]+candidatos[:12],tension)
            camino=self._red_alimentador(elementos,fid_raiz,subestacion,nodo_barra)
            if not camino: camino=base
            # Conserva en el JSON la celda del otro lado de cada dispositivo
            # de frontera sin incorporar sus conductores al circuito dibujado.
            por_nodo_completo = defaultdict(list)
            for elemento in elementos:
                for nodo in (elemento.get("nodo1"), elemento.get("nodo2")):
                    if nodo:
                        por_nodo_completo[nodo].append(elemento)
            for equipo in camino:
                if equipo.get("g3e_fno") not in (18800, 19300, 19400, 19600, 19700, 19800):
                    continue
                propio = str(equipo.get("circuito") or "").strip().upper()
                enlaces = {}
                for nodo in (equipo.get("nodo1"), equipo.get("nodo2")):
                    for vecino in por_nodo_completo.get(nodo, []):
                        if vecino.get("g3e_fid") == equipo.get("g3e_fid"):
                            continue
                        circuito = str(vecino.get("circuito") or "").strip().upper()
                        if not circuito or circuito == propio:
                            continue
                        sub_vecina = str(vecino.get("subestacion") or equipo.get("subestacion") or "").strip().upper()
                        enlaces[(circuito, sub_vecina)] = {
                            "circuito": circuito,
                            "subestacion": sub_vecina,
                            "nodo": nodo,
                        }
                equipo["celdas_enlazadas"] = sorted(
                    enlaces.values(), key=lambda item: (item["circuito"], item["subestacion"])
                )
            trafo_fids=[e['g3e_fid'] for e in camino if e['g3e_fno']==20400]
            detalles_trafos={}
            if trafo_fids:
                binds=','.join(f':t{i}' for i in range(len(trafo_fids)));params={f't{i}':f for i,f in enumerate(trafo_fids)}
                cur.execute(f"SELECT C.G3E_FID,NVL(M.CODIGO_OPERATIVO,''),NVL(M.CODIGO_MARCACION,''),NVL(C.TENSION,''),NVL(C.TENSION_SECUNDARIA,''),C.CAPACIDAD_NOMINAL,NVL(C.UNIDAD_MED_CAPACIDAD,''),NVL(T.USO,''),NVL(C.NODO_TRANSFORM_V,'') FROM {self.q('CCONECTIVIDAD_E')} C JOIN {self.q('CCOMUN')} M ON M.G3E_FID=C.G3E_FID LEFT JOIN {self.q('ETRANSFO_AT')} T ON T.G3E_FID=C.G3E_FID WHERE C.G3E_FID IN ({binds})",params)
                for r in cur.fetchall():detalles_trafos[int(r[0])]={'codigo_operacion':str(r[1]).strip(),'numero_transformador':str(r[2]).strip(),'tension_primaria':str(r[3]).strip(),'tension_secundaria':str(r[4]).strip(),'capacidad':float(r[5]) if r[5] is not None else None,'unidad_capacidad':str(r[6]).strip(),'uso':str(r[7]).strip(),'clave_usuarios':str(r[8]).strip(),'usuarios':[]}
                trafos_por_codigo={str(d.get('codigo_operacion') or '').strip().upper():d for d in detalles_trafos.values() if str(d.get('codigo_operacion') or '').strip()}
                usuarios_tc1,periodo_tc1=TC1Service().usuarios_por_transformadores(list(trafos_por_codigo),conn=conn)
                for codigo,detalle in trafos_por_codigo.items():
                    detalle['usuarios']=usuarios_tc1.get(codigo,[])
                    detalle['periodo_usuarios_tc1']=periodo_tc1
                    detalle['fuente_usuarios']='TC1_BRAE'
                for e in camino:
                    if e['g3e_fid'] in detalles_trafos:e.update(detalles_trafos[e['g3e_fid']]);e['codigo']=e.get('codigo_operacion') or e['codigo']
            lineas=[e['g3e_fid'] for e in camino if e['g3e_fno']==19000]
            geometrias={}
            for inicio in range(0,len(lineas),900):
                lote=lineas[inicio:inicio+900];binds=','.join(f':f{i}' for i in range(len(lote)));params={f'f{i}':f for i,f in enumerate(lote)}
                cur.execute(f"SELECT G3E_FID,SDO_UTIL.TO_GEOJSON(G3E_GEOMETRY) FROM {self.q('ECON_PRI_LN')} WHERE G3E_FID IN ({binds})",params)
                for fid,lob in cur.fetchall():
                    raw=lob.read() if hasattr(lob,'read') else lob
                    if raw: geometrias[int(fid)]=json.loads(raw)
            postes=self._postes_media_tension(cur,geometrias) if os.getenv("INCLUIR_POSTES_CIRCUITO", "1").lower() in {"1", "true", "si", "sí"} else []
            cur.execute(f"SELECT UPPER(TRIM(S.CODIGO)) FROM {self.q('ESUBESTA_AT')} S JOIN {self.q('CCOMUN')} M ON M.G3E_FID=S.G3E_FID WHERE M.EMPRESA_ORIGEN='CENS' AND S.MAIN_KV>34.5")
            fuentes=[str(r[0]).strip().upper() for r in cur.fetchall()]
            for e in camino:
                if e.get("frontera_externa"):
                    e["fuente_externa"] = e["g3e_fno"] == 18800 and e["subestacion"] in fuentes
        nodos={}
        for e in camino:
            geo=geometrias.get(e['g3e_fid'])
            if geo and geo.get('coordinates'):
                ps=geo['coordinates']; nodos[e['nodo1']]=ps[0][:2]; nodos[e['nodo2']]=ps[-1][:2]
                e['geometry']=geo
        for e in camino:
            if e.get("lat") is not None and e.get("lon") is not None:e["punto"]=[e["lon"],e["lat"]];continue
            puntos=[nodos[n] for n in (e['nodo1'],e['nodo2']) if n in nodos]
            if puntos: e['punto']=[sum(p[0] for p in puntos)/len(puntos),sum(p[1] for p in puntos)/len(puntos)]
        resultado={"subestacion":subestacion,"tension":tension,"raiz":raiz,"fuentes":fuentes,"circuitos":sorted({e['circuito'] for e in camino if e['circuito']}),"elementos":camino,"postes":postes,"nodos":[{"id":n,"punto":p} for n,p in nodos.items()],"version_topologia":7,"version_postes":3}
        with _TRACE_CACHE_LOCK:
            _TRACE_CACHE[cache_key]=(time.monotonic(),copy.deepcopy(resultado))
            if len(_TRACE_CACHE)>128:
                oldest=min(_TRACE_CACHE,key=lambda k:_TRACE_CACHE[k][0]);_TRACE_CACHE.pop(oldest,None)
        return resultado
