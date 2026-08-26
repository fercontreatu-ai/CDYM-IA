from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from desconexiones.services.gtech import GTechService
from desconexiones.services.sac import SacService


def normalizar(valor) -> str:
    return str(valor or "").strip().upper()


class Command(BaseCommand):
    help = (
        "Compara el circuito de los usuarios conectados a la red CENS en SAC "
        "con el circuito físico de su transformador en GTECH."
    )

    def add_arguments(self, parser):
        parser.add_argument("--operador-red", type=int, default=161)
        parser.add_argument(
            "--incluir-inactivos",
            action="store_true",
            help="Incluye clientes cuyo estado de cliente o suministro no sea activo.",
        )
        parser.add_argument(
            "--salida",
            type=Path,
            help="Directorio de salida (predeterminado: datos/comparaciones/fecha_hora).",
        )

    def handle(self, *args, **options):
        operador = options["operador_red"]
        incluir_inactivos = options["incluir_inactivos"]
        marca = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        salida = options["salida"] or Path(settings.DATA_DIR) / "comparaciones" / marca
        salida = Path(salida).expanduser().resolve()
        salida.mkdir(parents=True, exist_ok=True)

        self.stdout.write("Consultando la relación transformador-circuito en GTECH...")
        mapa_gtech, ambiguos_gtech, total_gtech = self._cargar_transformadores_gtech()
        self.stdout.write(
            f"GTECH: {total_gtech:,} filas, {len(mapa_gtech):,} transformadores únicos, "
            f"{len(ambiguos_gtech):,} códigos ambiguos."
        )

        self.stdout.write("Descargando el padrón independiente de clientes activos GTECH/CENS...")
        usuarios_gtech, resumen_gtech = self._cargar_usuarios_gtech(
            salida / "usuarios_activos_gtech_cens.csv"
        )
        self.stdout.write(
            f"Clientes GTECH: {resumen_gtech['filas']:,} filas, "
            f"{len(usuarios_gtech):,} NIU únicos."
        )

        archivos = {
            "completo": salida / "usuarios_red_cens_comparacion.csv",
            "diferencias": salida / "usuarios_circuito_diferente.csv",
            "sin_gtech": salida / "usuarios_transformador_sin_gtech.csv",
            "sin_transformador": salida / "usuarios_sin_transformador_sac.csv",
            "ambiguos": salida / "usuarios_transformador_ambiguo_gtech.csv",
            "solo_sac": salida / "usuarios_solo_sac.csv",
            "solo_gtech": salida / "usuarios_solo_gtech.csv",
        }
        encabezado = [
            "niu",
            "activo_sac",
            "estado_cliente_sac",
            "estado_suministro_sac",
            "operador_red",
            "comercializador",
            "transformador_sac",
            "circuito_sac",
            "transformador_gtech",
            "circuito_gtech",
            "subestacion_gtech",
            "g3e_fid_transformador",
            "resultado",
            "existe_como_cliente_gtech",
            "circuito_cliente_gtech",
            "subestacion_cliente_gtech",
            "g3e_fid_cliente",
            "comparacion_padron",
        ]
        manejadores = {}
        escritores = {}
        try:
            for clave, ruta in archivos.items():
                manejadores[clave] = ruta.open("w", newline="", encoding="utf-8-sig")
                escritores[clave] = csv.DictWriter(manejadores[clave], fieldnames=encabezado, delimiter=";")
                escritores[clave].writeheader()
            resumen = self._exportar_sac(
                operador,
                incluir_inactivos,
                mapa_gtech,
                ambiguos_gtech,
                usuarios_gtech,
                escritores,
            )
            sac_nius = resumen.pop("sac_nius")
            for niu, cliente in usuarios_gtech.items():
                if niu in sac_nius:
                    continue
                escritores["solo_gtech"].writerow(self._fila_solo_gtech(niu, cliente))
        finally:
            for manejador in manejadores.values():
                manejador.close()

        metadata = {
            "generado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
            "operador_red": operador,
            "solo_activos": not incluir_inactivos,
            "criterio_activo": "ESTADO_CLIENTE = 0 AND ESTADO_SUMINISTRO = 0",
            "criterio_gtech": "CCONECTIVIDAD_E.G3E_FNO = 20700 AND ESTADO = OPERACION; ACTIVO es informativo",
            "comparacion": "CIRCUITO SAC contra CIRCUITO GTECH del CODIGO_UBIC_TRANSFORMADOR",
            "fecha_corte_sac": resumen.pop("fecha_corte_sac"),
            "transformadores_gtech_filas": total_gtech,
            "transformadores_gtech_unicos": len(mapa_gtech),
            "transformadores_gtech_ambiguos": len(ambiguos_gtech),
            "clientes_gtech_filas": resumen_gtech["filas"],
            "clientes_gtech_nius_unicos": len(usuarios_gtech),
            "clientes_gtech_nius_duplicados": resumen_gtech["duplicados"],
            "resultados": dict(resumen["resultados"]),
            "comparacion_padrones": dict(resumen["comparacion_padrones"]),
            "total_exportado": resumen["total_exportado"],
            "archivos": {clave: ruta.name for clave, ruta in archivos.items()},
        }
        with (salida / "resumen.json").open("w", encoding="utf-8") as archivo:
            json.dump(metadata, archivo, ensure_ascii=False, indent=2)
        self._crear_excel_resumen(salida / "resumen.xlsx", metadata)

        self.stdout.write(self.style.SUCCESS(f"Comparación terminada: {salida}"))
        self.stdout.write(f"Usuarios exportados: {metadata['total_exportado']:,}")
        for resultado, cantidad in sorted(metadata["resultados"].items()):
            self.stdout.write(f"  {resultado}: {cantidad:,}")

    def _cargar_transformadores_gtech(self):
        servicio = GTechService()
        por_codigo = defaultdict(list)
        sql = f"""
            SELECT UPPER(TRIM(NVL(M.CODIGO_OPERATIVO, M.CODIGO_MARCACION))),
                   UPPER(TRIM(NVL(C.CIRCUITO, ''))),
                   UPPER(TRIM(NVL(C.SUBESTACION, ''))),
                   C.G3E_FID
            FROM {servicio.q('CCONECTIVIDAD_E')} C
            JOIN {servicio.q('CCOMUN')} M ON M.G3E_FID = C.G3E_FID
            WHERE M.EMPRESA_ORIGEN = 'CENS'
              AND C.G3E_FNO = 20400
              AND C.ESTADO <> 'RETIRADO'
        """
        with servicio.connection() as conn:
            cur = conn.cursor()
            cur.arraysize = 10000
            cur.prefetchrows = 10000
            cur.execute(sql)
            total = 0
            while True:
                filas = cur.fetchmany(10000)
                if not filas:
                    break
                total += len(filas)
                for codigo, circuito, subestacion, fid in filas:
                    codigo = normalizar(codigo)
                    if codigo:
                        por_codigo[codigo].append(
                            {
                                "codigo": codigo,
                                "circuito": normalizar(circuito),
                                "subestacion": normalizar(subestacion),
                                "fid": int(fid),
                            }
                        )
        mapa = {}
        ambiguos = {}
        for codigo, items in por_codigo.items():
            relaciones = {(x["circuito"], x["subestacion"]) for x in items}
            if len(relaciones) == 1:
                mapa[codigo] = items[0]
            else:
                ambiguos[codigo] = items
        return mapa, ambiguos, total

    def _cargar_usuarios_gtech(self, ruta):
        servicio = GTechService()
        encabezado = [
            "niu", "activo_gtech", "codigo_cliente_gtech", "tipo_cliente_gtech",
            "comercializador_gtech", "distribuidor_gtech", "circuito_gtech",
            "subestacion_gtech", "g3e_fid_cliente",
        ]
        usuarios = {}
        filas_total = 0
        duplicados = 0
        sql = f"""
            SELECT E.NIU, E.ACTIVO, E.CODIGO, E.TIPO_CLIENTE,
                   E.COMERCIALIZADOR, E.DISTRIBUIDOR,
                   C.CIRCUITO, C.SUBESTACION, E.G3E_FID
            FROM {servicio.q('ECLIENTE_AT')} E
            JOIN {servicio.q('CCONECTIVIDAD_E')} C ON C.G3E_FID = E.G3E_FID
            WHERE C.G3E_FNO = 20700
              AND UPPER(TRIM(C.ESTADO)) = 'OPERACION'
              AND E.NIU IS NOT NULL
        """
        with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=encabezado, delimiter=";")
            escritor.writeheader()
            with servicio.connection() as conn:
                cur = conn.cursor()
                cur.arraysize = 10000
                cur.prefetchrows = 10000
                cur.execute(sql)
                while True:
                    filas = cur.fetchmany(10000)
                    if not filas:
                        break
                    for niu, activo, codigo, tipo, comercializador, distribuidor, circuito, subestacion, fid in filas:
                        filas_total += 1
                        item = {
                            "niu": normalizar(niu),
                            "activo_gtech": normalizar(activo),
                            "codigo_cliente_gtech": normalizar(codigo),
                            "tipo_cliente_gtech": normalizar(tipo),
                            "comercializador_gtech": normalizar(comercializador),
                            "distribuidor_gtech": normalizar(distribuidor),
                            "circuito_gtech": normalizar(circuito),
                            "subestacion_gtech": normalizar(subestacion),
                            "g3e_fid_cliente": int(fid),
                        }
                        escritor.writerow(item)
                        if item["niu"] in usuarios:
                            duplicados += 1
                            previo = usuarios[item["niu"]]
                            if item["circuito_gtech"] and item["circuito_gtech"] != previo["circuito_gtech"]:
                                previo["circuito_gtech"] = "AMBIGUO"
                        else:
                            usuarios[item["niu"]] = item
                    if filas_total % 100000 < len(filas):
                        self.stdout.write(f"GTECH clientes: {filas_total:,} filas descargadas...")
        return usuarios, {"filas": filas_total, "duplicados": duplicados}

    def _exportar_sac(self, operador, incluir_inactivos, mapa_gtech, ambiguos_gtech, usuarios_gtech, escritores):
        servicio = SacService()
        resultados = Counter()
        total = 0
        sac_nius = set()
        comparacion_padrones = Counter()
        with servicio.connection() as conn:
            cur = conn.cursor()
            cur.arraysize = 10000
            cur.prefetchrows = 10000
            cur.execute("SELECT MAX(FECHA) FROM SAC_BI.VAL_CLIENTES@SAC")
            fecha_corte = cur.fetchone()[0]
            filtro_activo = "" if incluir_inactivos else "AND ESTADO_CLIENTE = 0 AND ESTADO_SUMINISTRO = 0"
            cur.execute(
                f"""
                    SELECT CLIENTE_ID, ESTADO_CLIENTE, ESTADO_SUMINISTRO,
                           OPERADOR_RED, COMERCIALIZADOR,
                           CODIGO_UBIC_TRANSFORMADOR, CIRCUITO
                    FROM SAC_BI.VAL_CLIENTES@SAC
                    WHERE FECHA = :fecha
                      AND OPERADOR_RED = :operador
                      {filtro_activo}
                    ORDER BY CLIENTE_ID
                """,
                {"fecha": fecha_corte, "operador": operador},
            )
            while True:
                filas = cur.fetchmany(10000)
                if not filas:
                    break
                for niu, estado_cliente, estado_suministro, op_red, comercializador, trafo, circuito_sac in filas:
                    total += 1
                    niu_normalizado = normalizar(niu)
                    sac_nius.add(niu_normalizado)
                    codigo_trafo = normalizar(trafo)
                    circuito_sac = normalizar(circuito_sac)
                    gtech = mapa_gtech.get(codigo_trafo)
                    if not codigo_trafo:
                        resultado = "SIN_TRANSFORMADOR_SAC"
                    elif codigo_trafo in ambiguos_gtech:
                        resultado = "TRANSFORMADOR_AMBIGUO_GTECH"
                    elif not gtech:
                        resultado = "TRANSFORMADOR_NO_ENCONTRADO_GTECH"
                    elif not circuito_sac:
                        resultado = "SIN_CIRCUITO_SAC"
                    elif not gtech["circuito"]:
                        resultado = "SIN_CIRCUITO_GTECH"
                    elif circuito_sac == gtech["circuito"]:
                        resultado = "COINCIDE"
                    else:
                        resultado = "CIRCUITO_DIFERENTE"
                    resultados[resultado] += 1
                    cliente_gtech = usuarios_gtech.get(niu_normalizado)
                    comparacion_padron = "EN_SAC_Y_GTECH" if cliente_gtech else "SOLO_SAC"
                    comparacion_padrones[comparacion_padron] += 1
                    fila = {
                        "niu": niu_normalizado,
                        "activo_sac": estado_cliente == 0 and estado_suministro == 0,
                        "estado_cliente_sac": estado_cliente,
                        "estado_suministro_sac": estado_suministro,
                        "operador_red": op_red,
                        "comercializador": comercializador,
                        "transformador_sac": codigo_trafo,
                        "circuito_sac": circuito_sac,
                        "transformador_gtech": gtech["codigo"] if gtech else "",
                        "circuito_gtech": gtech["circuito"] if gtech else "",
                        "subestacion_gtech": gtech["subestacion"] if gtech else "",
                        "g3e_fid_transformador": gtech["fid"] if gtech else "",
                        "resultado": resultado,
                        "existe_como_cliente_gtech": bool(cliente_gtech),
                        "circuito_cliente_gtech": cliente_gtech["circuito_gtech"] if cliente_gtech else "",
                        "subestacion_cliente_gtech": cliente_gtech["subestacion_gtech"] if cliente_gtech else "",
                        "g3e_fid_cliente": cliente_gtech["g3e_fid_cliente"] if cliente_gtech else "",
                        "comparacion_padron": comparacion_padron,
                    }
                    escritores["completo"].writerow(fila)
                    if not cliente_gtech:
                        escritores["solo_sac"].writerow(fila)
                    destino = {
                        "CIRCUITO_DIFERENTE": "diferencias",
                        "TRANSFORMADOR_NO_ENCONTRADO_GTECH": "sin_gtech",
                        "SIN_TRANSFORMADOR_SAC": "sin_transformador",
                        "TRANSFORMADOR_AMBIGUO_GTECH": "ambiguos",
                    }.get(resultado)
                    if destino:
                        escritores[destino].writerow(fila)
                if total % 100000 < len(filas):
                    self.stdout.write(f"SAC: {total:,} usuarios procesados...")
        comparacion_padrones["SOLO_GTECH"] = len(set(usuarios_gtech) - sac_nius)
        return {
            "fecha_corte_sac": fecha_corte,
            "total_exportado": total,
            "resultados": resultados,
            "comparacion_padrones": comparacion_padrones,
            "sac_nius": sac_nius,
        }

    @staticmethod
    def _fila_solo_gtech(niu, cliente):
        return {
            "niu": niu,
            "activo_sac": "",
            "estado_cliente_sac": "",
            "estado_suministro_sac": "",
            "operador_red": "",
            "comercializador": "",
            "transformador_sac": "",
            "circuito_sac": "",
            "transformador_gtech": "",
            "circuito_gtech": "",
            "subestacion_gtech": "",
            "g3e_fid_transformador": "",
            "resultado": "NO_APLICA_SOLO_GTECH",
            "existe_como_cliente_gtech": True,
            "circuito_cliente_gtech": cliente["circuito_gtech"],
            "subestacion_cliente_gtech": cliente["subestacion_gtech"],
            "g3e_fid_cliente": cliente["g3e_fid_cliente"],
            "comparacion_padron": "SOLO_GTECH",
        }

    @staticmethod
    def _crear_excel_resumen(ruta, metadata):
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise CommandError("Falta openpyxl; instale las dependencias del proyecto.") from exc
        libro = Workbook()
        hoja = libro.active
        hoja.title = "Resumen"
        hoja.append(["Concepto", "Valor"])
        for clave in (
            "generado_en",
            "operador_red",
            "solo_activos",
            "criterio_activo",
            "criterio_gtech",
            "fecha_corte_sac",
            "transformadores_gtech_filas",
            "transformadores_gtech_unicos",
            "transformadores_gtech_ambiguos",
            "clientes_gtech_filas",
            "clientes_gtech_nius_unicos",
            "clientes_gtech_nius_duplicados",
            "total_exportado",
        ):
            hoja.append([clave, metadata[clave]])
        hoja.append([])
        hoja.append(["Resultado", "Cantidad"])
        for resultado, cantidad in sorted(metadata["resultados"].items()):
            hoja.append([resultado, cantidad])
        hoja.append([])
        hoja.append(["Comparación de padrones", "Cantidad"])
        for resultado, cantidad in sorted(metadata["comparacion_padrones"].items()):
            hoja.append([resultado, cantidad])
        hoja.freeze_panes = "A2"
        hoja.column_dimensions["A"].width = 42
        hoja.column_dimensions["B"].width = 28
        libro.save(ruta)
