from __future__ import annotations

import copy
import os
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import date


_SAC_CACHE: dict[tuple[str, ...], tuple[float, tuple]] = {}
_SAC_CACHE_LOCK = threading.RLock()
_SAC_CACHE_SECONDS = int(os.getenv("SAC_CACHE_SECONDS", "600"))


class SacService:
    """Consulta de solo lectura de clientes, transformadores y consumos CENS en SAC."""

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
            cur = conn.cursor()
            cur.arraysize = 2000
            cur.prefetchrows = 2000
            cur.execute("SET TRANSACTION READ ONLY")
            yield conn
        finally:
            conn.rollback()
            conn.close()

    @staticmethod
    def _columna_disponible(cur, tabla: str, candidatas: tuple[str, ...]) -> str | None:
        """Encuentra una columna conocida sin depender de una versión concreta de SAC."""
        try:
            cur.execute(f"SELECT * FROM {tabla} WHERE 1=0")
            disponibles = {str(col[0]).upper() for col in cur.description or []}
            return next((nombre for nombre in candidatas if nombre in disponibles), None)
        except Exception:
            return None

    @staticmethod
    def _estado_transformador_activo(valor):
        if valor is None or str(valor).strip() == "":
            return None
        texto = str(valor).strip().upper()
        if texto in {"0", "A", "I", "ACTIVO", "ACTIVE", "INSTALADO", "SERVICIO", "EN SERVICIO", "OPERACION", "OPERACIÓN"}:
            return True
        if texto in {"1", "R", "INACTIVO", "INACTIVE", "RETIRADO", "FUERA DE SERVICIO", "BAJA"}:
            return False
        return None

    def usuarios_por_transformadores(self, codigos: list[str]) -> tuple[dict[str, list[dict]], dict[str, int], dict[str, dict]]:
        codes = sorted({str(code).strip().upper() for code in codigos if str(code).strip()})
        if not codes:
            return {}, {}, {}
        cache_key = tuple(codes)
        with _SAC_CACHE_LOCK:
            cached = _SAC_CACHE.get(cache_key)
            if cached and time.monotonic() - cached[0] < _SAC_CACHE_SECONDS:
                return copy.deepcopy(cached[1])

        users_by_transformer: dict[str, list[dict]] = {code: [] for code in codes}
        excluded_by_transformer: dict[str, int] = {code: 0 for code in codes}
        transformer_status: dict[str, dict] = {
            code: {"en_sac_transformador": False, "activo_sac_transformador": None} for code in codes
        }
        with self.connection() as conn:
            cur = conn.cursor()
            cur.arraysize = 2000
            cur.prefetchrows = 2000
            estado_col = self._columna_disponible(
                cur,
                "SAC.TRANSFORMADORES@SAC",
                ("ESTADO_TRANSFORMADOR", "ESTADO", "ESTADO_ACTIVO", "ACTIVO"),
            )
            estado_expr = estado_col or "NULL"
            cur.execute("SELECT MAX(FECHA) FROM SAC_BI.VAL_CLIENTES@SAC")
            cutoff = cur.fetchone()[0]
            for start in range(0, len(codes), 500):
                batch = codes[start:start + 500]
                binds = ",".join(f":t{i}" for i in range(len(batch)))
                params = {f"t{i}": value for i, value in enumerate(batch)}

                cur.execute(
                    f"SELECT CODIGO_UBIC_TRANSFORMADOR, MACROMEDIDOR_PRINCIPAL, {estado_expr}, TRANSFORMADOR_ID "
                    f"FROM SAC.TRANSFORMADORES@SAC WHERE CODIGO_UBIC_TRANSFORMADOR IN ({binds})",
                    params,
                )
                macros = {}
                for code, client_id, estado, transformer_id in cur.fetchall():
                    normalized_code = str(code or "").strip().upper()
                    if not normalized_code:
                        continue
                    if client_id is not None:
                        macros[normalized_code] = str(client_id).strip()
                    transformer_status[normalized_code] = {
                        "en_sac_transformador": True,
                        "activo_sac_transformador": self._estado_transformador_activo(estado),
                        "estado_transformador_sac": str(estado or "").strip(),
                        "transformador_id_sac": int(transformer_id) if transformer_id is not None else None,
                    }

                sql = f"""
                    SELECT CODIGO_UBIC_TRANSFORMADOR, CLIENTE_ID, COMERCIALIZADOR, OPERADOR_RED, ESTADO_CLIENTE, ESTADO_SUMINISTRO, NOMBRE, DIRECCION, FECHA_FACTURACION_ACT, FECHA_LECTURA_ACT
                    FROM SAC_BI.VAL_CLIENTES@SAC
                    WHERE FECHA = :cutoff
                      AND CODIGO_UBIC_TRANSFORMADOR IN ({binds})
                """
                cur.execute(sql, {**params, "cutoff": cutoff})
                for code, client_id, comercializador, operador_red, estado_cliente, estado_suministro, nombre, direccion, fecha_facturacion, fecha_lectura in cur.fetchall():
                    normalized_code = str(code or "").strip().upper()
                    niu = str(client_id).strip()
                    if macros.get(normalized_code) == niu:
                        excluded_by_transformer[normalized_code] = excluded_by_transformer.get(normalized_code, 0) + 1
                        continue
                    comercializador_codigo=int(comercializador) if comercializador is not None else None
                    users_by_transformer.setdefault(normalized_code, []).append({"niu":niu,"en_sac_cens":True,"activo_sac":estado_cliente==0 and estado_suministro==0,"estado_cliente_sac":estado_cliente,"estado_suministro_sac":estado_suministro,"nombre":str(nombre or "").strip(),"direccion":str(direccion or "").strip(),"fecha_facturacion_juliana":fecha_facturacion,"fecha_lectura_juliana":fecha_lectura,"comercializador_codigo":comercializador_codigo,"comercializador_nombre":"CENS" if comercializador_codigo==604 else (f"Otro comercializador ({comercializador_codigo})" if comercializador_codigo else "Sin identificar"),"comercializador_cens":comercializador_codigo==604,"otro_comercializador":comercializador_codigo is not None and comercializador_codigo!=604,"operador_red":int(operador_red) if operador_red is not None else None})

        all_users = [user for users in users_by_transformer.values() for user in users]
        details = self.consumos_mes_por_transformador(users_by_transformer, transformer_status)
        for user in all_users:
            user.update(details.get(user["niu"], {
                "en_sac_cens": False,
                "activo_sac": False,
                "nombre": "",
                "ultimo_consumo_kwh": None,
                "fecha_ultima_lectura": "",
                "fecha_ultima_facturacion": "",
                "comercializador_codigo": None,
                "comercializador_nombre": "Sin identificar",
                "comercializador_cens": False,
            }))
        resultado = (users_by_transformer, excluded_by_transformer, transformer_status)
        with _SAC_CACHE_LOCK:
            _SAC_CACHE[cache_key] = (time.monotonic(), copy.deepcopy(resultado))
            if len(_SAC_CACHE) > 128:
                oldest = min(_SAC_CACHE, key=lambda item: _SAC_CACHE[item][0])
                _SAC_CACHE.pop(oldest, None)
        return resultado

    @staticmethod
    def _fecha_juliana(valor):
        try:
            return date.fromordinal(int(valor) - 1721425)
        except (TypeError, ValueError, OverflowError):
            return None

    def consumos_mes_por_transformador(self, usuarios_por_trafo: dict[str, list[dict]], estado_transformadores: dict[str, dict]) -> dict[str, dict]:
        """Usa un NIU activo para fijar el mes por transformador y consulta en cuatro lectores."""
        resultado={str(u["niu"]):dict(u,ultimo_consumo_kwh=None,fecha_ultima_lectura="",fecha_ultima_facturacion="") for usuarios in usuarios_por_trafo.values() for u in usuarios}
        grupos={}
        for codigo,usuarios in usuarios_por_trafo.items():
            referencia=next((u for u in usuarios if u.get("activo_sac") is True and self._fecha_juliana(u.get("fecha_facturacion_juliana"))),None)
            if not referencia:continue
            fecha=self._fecha_juliana(referencia.get("fecha_facturacion_juliana"));grupos.setdefault((fecha.year,fecha.month),[]).extend(int(str(u["niu"])) for u in usuarios if u.get("activo_sac") is True and str(u.get("niu","")).isdigit())
        trabajos=[]
        for (anio,mes),nius in grupos.items():
            inicio_mes=date(anio,mes,1);fin_mes=date(anio+1,1,1) if mes==12 else date(anio,mes+1,1);j0=inicio_mes.toordinal()+1721425;j1=fin_mes.toordinal()+1721425-1
            trabajos.extend((anio,mes,nius[inicio:inicio+900],j0,j1) for inicio in range(0,len(nius),900))
        if not trabajos:return resultado
        cantidad_lectores=min(4,len(trabajos));colas=[trabajos[i::cantidad_lectores] for i in range(cantidad_lectores)]
        def consultar_cola(cola):
            salida=[]
            with self.connection() as conn:
                cur=conn.cursor();cur.arraysize=2000;cur.prefetchrows=2000
                for anio,mes,lote,j0,j1 in cola:
                    binds=",".join(f":n{i}" for i in range(len(lote)));params={f"n{i}":v for i,v in enumerate(lote)};params.update({"j0":j0,"j1":j1})
                    cur.execute(f"""SELECT F.CLIENTE_ID,MAX(F.CONSUMO_ACTIVA) KEEP (DENSE_RANK LAST ORDER BY F.FECHA_FACTURACION,F.CONSECUTIVO),MAX(F.DIAS_FACTURADOS) KEEP (DENSE_RANK LAST ORDER BY F.FECHA_FACTURACION,F.CONSECUTIVO) FROM SAC.CLI_FACTURACION@SAC F WHERE F.CLIENTE_ID IN ({binds}) AND F.FECHA_FACTURACION BETWEEN :j0 AND :j1 GROUP BY F.CLIENTE_ID""",params)
                    salida.extend((anio,mes,*fila) for fila in cur.fetchall())
            return salida
        with ThreadPoolExecutor(max_workers=cantidad_lectores) as executor:
            for filas in executor.map(consultar_cola,colas):
                for anio,mes,niu,consumo,dias in filas:
                    item=resultado[str(niu)];ff=self._fecha_juliana(item.get("fecha_facturacion_juliana"));fl=self._fecha_juliana(item.get("fecha_lectura_juliana"));item.update({"ultimo_consumo_kwh":float(consumo) if consumo is not None else None,"dias_facturados":int(dias) if dias is not None else None,"fecha_ultima_facturacion":ff.isoformat() if ff else "","fecha_ultima_lectura":fl.isoformat() if fl else "","mes_consumo_sac":f"{anio:04d}-{mes:02d}","mes_referencia_transformador":True})
        return resultado

    def ultimos_consumos(self, nius: list[str]) -> dict[str, dict]:
        numeric_nius = sorted({int(str(niu).strip()) for niu in nius if str(niu).strip().isdigit()})
        if not numeric_nius:
            return {}

        result: dict[str, dict] = {}
        with self.connection() as conn:
            cur = conn.cursor()
            cur.arraysize = 2000
            cur.prefetchrows = 2000
            nombre_col = self._columna_disponible(
                cur,
                "SAC.CLIENTES@SAC",
                ("NOMBRE_CLIENTE", "NOMBRE_COMPLETO", "RAZON_SOCIAL", "NOMBRES", "NOMBRE"),
            )
            nombre_expr = f"C.{nombre_col}" if nombre_col else "NULL"
            for start in range(0, len(numeric_nius), 500):
                batch = numeric_nius[start:start + 500]
                binds = ",".join(f":n{i}" for i in range(len(batch)))
                params = {f"n{i}": value for i, value in enumerate(batch)}
                sql = f"""
                    SELECT CLIENTE_ID, ESTADO_CLIENTE, ESTADO_SUMINISTRO,
                           ESTADO_FACTURACION, FECHA_LECTURA, FECHA_FACTURACION,
                           DIAS_FACTURADOS, CONSUMO_ACTIVA, FECHA_SISTEMA,
                           OPERADOR_RED, DIRECCION, GPS_LATITUD, GPS_LONGITUD, NOMBRE_USUARIO
                    FROM (
                        SELECT F.CLIENTE_ID, C.ESTADO_CLIENTE, C.ESTADO_SUMINISTRO,
                               C.ESTADO_FACTURACION,
                               TO_CHAR(TO_DATE(TO_CHAR(F.FECHA_LECTURA), 'J'), 'YYYY-MM-DD') FECHA_LECTURA,
                               TO_CHAR(TO_DATE(TO_CHAR(F.FECHA_FACTURACION), 'J'), 'YYYY-MM-DD') FECHA_FACTURACION,
                               F.DIAS_FACTURADOS, F.CONSUMO_ACTIVA, F.FECHA_SISTEMA,
                               F.OPERADOR_RED, C.DIRECCION, C.GPS_LATITUD, C.GPS_LONGITUD,
                               {nombre_expr} NOMBRE_USUARIO,
                               ROW_NUMBER() OVER (
                                   PARTITION BY F.CLIENTE_ID
                                   ORDER BY F.FECHA_FACTURACION DESC, F.CONSECUTIVO DESC
                               ) RN
                        FROM SAC.CLI_FACTURACION@SAC F
                        JOIN SAC.CLIENTES@SAC C ON C.CLIENTE_ID = F.CLIENTE_ID
                        WHERE F.CLIENTE_ID IN ({binds})
                    )
                    WHERE RN = 1
                """
                cur.execute(sql, params)
                for row in cur.fetchall():
                    active = row[1] == 0 and row[2] == 0 and row[3] == 0
                    result[str(row[0])] = {
                        "en_sac_cens": True,
                        "activo_sac": active,
                        "nombre": str(row[13] or "").strip(),
                        "estado_cliente_sac": row[1],
                        "estado_suministro_sac": row[2],
                        "estado_facturacion_sac": row[3],
                        "fecha_ultima_lectura": str(row[4] or ""),
                        "fecha_ultima_facturacion": str(row[5] or ""),
                        "dias_facturados": int(row[6]) if row[6] is not None else None,
                        "ultimo_consumo_kwh": float(row[7]) if row[7] is not None else None,
                        "fecha_carga_sac": row[8].isoformat() if row[8] else "",
                        "operador_red": int(row[9]) if row[9] is not None else None,
                        "direccion": str(row[10] or "").strip(),
                        "gps_latitud": float(str(row[11]).replace(",", ".")) if row[11] not in (None, "") else None,
                        "gps_longitud": float(str(row[12]).replace(",", ".")) if row[12] not in (None, "") else None,
                    }

                cur.execute("SELECT MAX(FECHA) FROM SAC_BI.VAL_CLIENTES@SAC")
                cutoff = cur.fetchone()[0]
                commercial_sql = f"""
                    SELECT CLIENTE_ID, COMERCIALIZADOR, OPERADOR_RED
                    FROM SAC_BI.VAL_CLIENTES@SAC
                    WHERE FECHA = :cutoff
                      AND CLIENTE_ID IN ({binds})
                """
                cur.execute(commercial_sql, {**params, "cutoff": cutoff})
                for cliente_id, comercializador, operador_red in cur.fetchall():
                    item = result.setdefault(str(cliente_id), {"en_sac_cens": True})
                    code = int(comercializador) if comercializador is not None else None
                    item["comercializador_codigo"] = code
                    item["comercializador_nombre"] = (
                        "CENS" if code == 604 else (f"Otro comercializador ({code})" if code else "Sin identificar")
                    )
                    item["comercializador_cens"] = code == 604
                    item["otro_comercializador"] = code is not None and code != 604
                    if item.get("operador_red") is None and operador_red is not None:
                        item["operador_red"] = int(operador_red)

            codes = sorted({item.get("comercializador_codigo") for item in result.values() if item.get("comercializador_codigo")})
            if codes:
                binds = ",".join(f":c{i}" for i in range(len(codes)))
                cur.execute(
                    f"SELECT TC1_IDCOMER, TC1_DESCRIPCION FROM BRAE.QA_TTC1_COMERCIALIZADORAS@BRAE WHERE TC1_IDCOMER IN ({binds})",
                    {f"c{i}": code for i, code in enumerate(codes)},
                )
                names = {int(code): str(name or "").strip() for code, name in cur.fetchall()}
                for item in result.values():
                    code = item.get("comercializador_codigo")
                    if code in names:
                        item["comercializador_nombre"] = names[code]
        return result
