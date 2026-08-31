from __future__ import annotations

import copy
import os
import threading
import time
from contextlib import contextmanager


_TC1_CACHE: dict[tuple[str, ...], tuple[float, tuple]] = {}
_TC1_CACHE_LOCK = threading.RLock()
_TC1_CACHE_SECONDS = int(os.getenv("TC1_CACHE_SECONDS", "600"))


class TC1Service:
    """Padrón de usuarios de red reportado en TC1 a través de BRAE."""

    schema = os.getenv("BRAE_SCHEMA", "BRAE")
    link = os.getenv("BRAE_DB_LINK", "BRAE")

    def q(self, table: str) -> str:
        return f"{self.schema}.{table}@{self.link}"

    @contextmanager
    def connection(self):
        import oracledb

        oracledb.defaults.fetch_lobs = False
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            host=os.environ["ORACLE_HOST"],
            port=int(os.getenv("ORACLE_PORT", "1521")),
            service_name=os.environ["ORACLE_SERVICE_NAME"],
        )
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _texto(valor) -> str:
        return str(valor or "").strip()

    def usuarios_por_transformadores(self, codigos: list[str], conn=None) -> tuple[dict[str, list[dict]], str]:
        codigos = sorted({self._texto(codigo).upper() for codigo in codigos if self._texto(codigo)})
        if not codigos:
            return {}, ""
        cache_key = tuple(codigos)
        with _TC1_CACHE_LOCK:
            cached = _TC1_CACHE.get(cache_key)
            if cached and time.monotonic() - cached[0] < _TC1_CACHE_SECONDS:
                return copy.deepcopy(cached[1])

        propio = conn is None
        contexto = self.connection() if propio else None
        conexion = contexto.__enter__() if contexto else conn
        try:
            cur = conexion.cursor()
            cur.arraysize = 5000
            cur.prefetchrows = 5000
            cur.execute(f"SELECT MAX(TC1_PERIODO) FROM {self.q('QA_TTC1')}")
            periodo_raw = cur.fetchone()[0]
            if periodo_raw is None:
                return {codigo: [] for codigo in codigos}, ""
            periodo = str(periodo_raw).strip()
            resultado = {codigo: [] for codigo in codigos}
            for inicio in range(0, len(codigos), 500):
                lote = codigos[inicio:inicio + 500]
                binds = ",".join(f":t{i}" for i in range(len(lote)))
                params = {f"t{i}": codigo for i, codigo in enumerate(lote)}
                params["periodo"] = periodo_raw
                cur.execute(
                    f"""
                    SELECT UPPER(TRIM(T.TC1_CODCONEX)), TRIM(T.TC1_TC1),
                           TRIM(T.TC1_CODCONEX), TRIM(T.TC1_TIPCONEX),
                           T.TC1_NT, T.TC1_NTP, TRIM(T.TC1_PROPACTIV),
                           TRIM(T.TC1_CONEXRED), TRIM(T.TC1_IDCOMER),
                           NVL(TRIM(C.TC1_DESCRIPCION), ''), TRIM(T.TC1_IDMERC),
                           TRIM(T.TC1_GC), TRIM(T.TC1_CODFRONCOM),
                           TRIM(T.TC1_CODCIRC), TRIM(T.TC1_CODDANE),
                           TRIM(T.TC1_UBIC), TRIM(T.TC1_DIREC),
                           TRIM(T.TC1_CONESP), TRIM(T.TC1_CODARESP),
                           TRIM(T.TC1_TIPARESP), TRIM(T.TC1_ESTSECT),
                           T.TC1_ALTITUD, TRIM(T.TC1_LONGITUD), TRIM(T.TC1_LATITUD),
                           TRIM(T.TC1_AUTOGEN), TRIM(T.TC1_EXPENER),
                           TRIM(T.TC1_CAPAUTOGENR), TRIM(T.TC1_TIPGENR),
                           TRIM(T.TC1_CODFRONEXP), T.TC1_FENTGEN,
                           TRIM(T.TC1_CONTRESP), TRIM(T.TC1_CAPCONTRESP),
                           TRIM(T.TC1_IUA), TRIM(T.TC1_CODTRANSF)
                      FROM {self.q('QA_TTC1')} T
                      LEFT JOIN {self.q('QA_TTC1_COMERCIALIZADORAS')} C
                        ON TO_CHAR(C.TC1_IDCOMER) = TRIM(T.TC1_IDCOMER)
                     WHERE T.TC1_PERIODO = :periodo
                       AND UPPER(TRIM(T.TC1_CODCONEX)) IN ({binds})
                    """,
                    params,
                )
                for row in cur.fetchall():
                    codigo, niu = self._texto(row[0]).upper(), self._texto(row[1])
                    if not codigo or not niu:
                        continue
                    comercializador_codigo = self._texto(row[8])
                    es_cens = comercializador_codigo == "604"
                    resultado.setdefault(codigo, []).append({
                        "niu": niu,
                        "iua": self._texto(row[32]),
                        "fuente_usuario": "TC1_BRAE",
                        "activo_tc1": True,
                        "periodo_tc1": periodo,
                        "codigo_conexion": self._texto(row[2]),
                        "tipo_conexion": self._texto(row[3]),
                        "nivel_tension": row[4],
                        "nivel_tension_primario": row[5],
                        "propiedad_activo": self._texto(row[6]),
                        "conexion_red": self._texto(row[7]),
                        "comercializador_codigo": comercializador_codigo,
                        "comercializador_nombre": self._texto(row[9]) or "Sin identificar",
                        "comercializador_cens": es_cens,
                        "otro_comercializador": bool(comercializador_codigo) and not es_cens,
                        "mercado_codigo": self._texto(row[10]),
                        "grupo_calidad": self._texto(row[11]),
                        "codigo_frontera_comercial": self._texto(row[12]),
                        "circuito_cliente": self._texto(row[13]),
                        "codigo_transformador_tc1": codigo,
                        "identificador_transformador_tc1": self._texto(row[33]),
                        "codigo_dane": self._texto(row[14]),
                        "ubicacion_tipo": self._texto(row[15]),
                        "direccion": self._texto(row[16]),
                        "condicion_especial": self._texto(row[17]),
                        "codigo_area_especial": self._texto(row[18]),
                        "tipo_area_especial": self._texto(row[19]),
                        "estrato_sector": self._texto(row[20]),
                        "altitud": float(row[21]) if row[21] not in (None, "") else None,
                        "longitud": self._texto(row[22]),
                        "latitud": self._texto(row[23]),
                        "autogenerador": self._texto(row[24]),
                        "exporta_energia": self._texto(row[25]),
                        "capacidad_autogeneracion": self._texto(row[26]),
                        "tipo_generacion": self._texto(row[27]),
                        "codigo_frontera_exportacion": self._texto(row[28]),
                        "fecha_entrada_generacion": row[29].isoformat() if row[29] else "",
                        "contrato_respaldo": self._texto(row[30]),
                        "capacidad_contrato_respaldo": self._texto(row[31]),
                    })
        finally:
            if contexto:
                contexto.__exit__(None, None, None)

        salida = (resultado, periodo)
        with _TC1_CACHE_LOCK:
            _TC1_CACHE[cache_key] = (time.monotonic(), copy.deepcopy(salida))
            if len(_TC1_CACHE) > 128:
                oldest = min(_TC1_CACHE, key=lambda item: _TC1_CACHE[item][0])
                _TC1_CACHE.pop(oldest, None)
        return salida
