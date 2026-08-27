from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from .scada_archivos import serie_dia_scada


VARIABLES = {
    "VOLTAJE": (("URS", "U RS"), ("UST", "U ST"), ("UTR", "U TR")),
    "CORRIENTE": (("IR", "I R"), ("IS", "I S"), ("IT", "I T")),
    "POTENCIAS": (("P", "P activa"), ("Q", "Q reactiva"), ("S", "S aparente")),
}
UNIDADES = {
    "URS": "kV", "UST": "kV", "UTR": "kV",
    "IR": "A", "IS": "A", "IT": "A",
    "P": "MW", "Q": "MVAr", "S": "MVA",
}
PRIORIDAD_FUENTE = ("MED", "REL", "REC", "")


class SeriesMedidasService:
    """Lee series históricas de alimentadores.sqlite sin permitir escrituras."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or (Path(settings.DATABASE_FILE)))

    def connection(self):
        if not self.path.exists():
            raise FileNotFoundError("No existe alimentadores.sqlite.")
        return sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=20)

    @staticmethod
    def validar_fecha(value: str | None) -> date | None:
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    def rango_global(self) -> tuple[str, str]:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT fecha FROM mediciones ORDER BY fecha_hora LIMIT 1")
            first = cur.fetchone()
            cur.execute("SELECT fecha FROM mediciones ORDER BY fecha_hora DESC LIMIT 1")
            last = cur.fetchone()
            if not first or not last:
                cur.execute("SELECT MIN(fecha),MAX(fecha) FROM seleccion_dia_reducido")
                rango = cur.fetchone()
                if rango and rango[0] and rango[1]:
                    return str(rango[0]), str(rango[1])
        if not first or not last:
            raise ValueError("La base de medidas está vacía.")
        return str(first[0]), str(last[0])

    @staticmethod
    def _pascua(anio: int) -> date:
        a=anio%19; b=anio//100; c=anio%100; d=b//4; e=b%4
        f=(b+8)//25; g=(b-f+1)//3; h=(19*a+b-d-g+15)%30
        i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
        mes=(h+l-7*m+114)//31; dia=(h+l-7*m+114)%31+1
        return date(anio,mes,dia)

    @staticmethod
    def _lunes_siguiente(fecha: date) -> date:
        return fecha + timedelta(days=(7-fecha.weekday())%7)

    @classmethod
    def es_festivo_colombia(cls, fecha: date) -> bool:
        if fecha.weekday()==6:
            return True
        anio=fecha.year
        fijos={(1,1),(5,1),(7,20),(8,7),(12,8),(12,25)}
        if (fecha.month,fecha.day) in fijos:
            return True
        trasladables=((1,6),(3,19),(6,29),(8,15),(10,12),(11,1),(11,11))
        festivos={cls._lunes_siguiente(date(anio,m,d)) for m,d in trasladables}
        pascua=cls._pascua(anio)
        festivos.update({pascua-timedelta(days=3),pascua-timedelta(days=2),
                         pascua+timedelta(days=43),pascua+timedelta(days=64),
                         pascua+timedelta(days=71)})
        return fecha in festivos

    def seleccionar_dia_maxima_corriente(self, medida: dict, dia_semana: int,
                                         tipo_dia: str, delta_porcentaje: float) -> dict:
        if dia_semana not in range(7):
            raise ValueError("El día de la semana no es válido.")
        tipo=str(tipo_dia or "ORDINARIO").upper()
        if dia_semana==6:
            tipo="FESTIVO"
        if tipo not in {"FESTIVO","ORDINARIO"}:
            raise ValueError("Seleccione festivo u ordinario.")
        delta=float(delta_porcentaje)
        if delta<5 or delta>60 or delta%5:
            raise ValueError("El delta debe estar entre 5% y 60%, en pasos de 5%.")
        subestacion=str(medida.get("medida_subestacion") or "").strip().upper()
        dispositivo=str(medida.get("medida_dispositivo") or "").strip().upper()
        fuente_solicitada=str(medida.get("medida_fuente") or "").strip().upper()
        with self.connection() as conn:
            reducida=conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='seleccion_dia_reducido'"
            ).fetchone()
            if reducida:
                categorias=("LUNES_ORDINARIO","MARTES_ORDINARIO","MIERCOLES_ORDINARIO",
                            "JUEVES_ORDINARIO","VIERNES_ORDINARIO","SABADO_ORDINARIO")
                categoria="FESTIVO" if tipo=="FESTIVO" else categorias[dia_semana]
                fila=conn.execute(
                    "SELECT fecha,fuente,carga_maxima_a,delta_maximo_observado_pct,"
                    "factor_escala_potencia,factor_potencia_mediano,"
                    "correlacion_kv_a_potencia,calidad_correlacion "
                    "FROM seleccion_dia_reducido WHERE upper(subestacion)=? "
                    "AND upper(interruptor)=? AND categoria=? AND delta_pct=?",
                    (subestacion,dispositivo,categoria,int(delta)),
                ).fetchone()
                if not fila:
                    raise ValueError(
                        f"La base reducida no tiene un día válido para {dispositivo}, "
                        f"{categoria.lower()}, delta {delta:g}%."
                    )
                return {
                    "fecha":str(fila[0]),"fuente":str(fila[1] or ""),
                    "carga_maxima_a":float(fila[2]),"delta_maximo_pct":float(fila[3]),
                    "factor_escala_potencia":float(fila[4]),
                    "factor_potencia_mediano":fila[5],
                    "correlacion_kv_a_potencia":fila[6],"calidad_correlacion":fila[7],
                    "tipo_dia":tipo,"categoria":categoria,"dia_semana":dia_semana,
                    "delta_configurado_pct":delta,"dias_evaluados":1,
                    "descartados_delta":0,"descartados_incompletos":0,
                    "origen_seleccion":"BASE_REDUCIDA",
                }
            rows=conn.execute(
                'SELECT fecha,fecha_hora,fuente,"IR","IS","IT" FROM mediciones '
                'WHERE subestacion=? AND interruptor=? ORDER BY fecha_hora',
                (subestacion,dispositivo),
            ).fetchall()
        por_fecha={}
        for row in rows:
            try:
                f=datetime.strptime(str(row[0]),"%Y-%m-%d").date()
            except ValueError:
                continue
            if f.weekday()!=dia_semana:
                continue
            festivo=self.es_festivo_colombia(f)
            if (tipo=="FESTIVO")!=festivo:
                continue
            por_fecha.setdefault(f,{}).setdefault(str(row[2] or "").upper(),[]).append(row)
        mejor=None; descartados_delta=0; descartados_incompletos=0
        for fecha,por_fuente in por_fecha.items():
            fuentes=set(por_fuente)
            fuente=fuente_solicitada if fuente_solicitada in fuentes else next((x for x in PRIORIDAD_FUENTE if x in fuentes),None)
            datos=por_fuente.get(fuente,[])
            if len(datos)!=96 or any(any(r[i] is None for i in (3,4,5)) for r in datos):
                descartados_incompletos+=1
                continue
            max_delta=0.0; maxima=0.0
            anterior=None
            for r in datos:
                actual=[abs(float(r[i])) for i in (3,4,5)]
                maxima=max(maxima,*actual)
                if anterior is not None:
                    for previo,nuevo in zip(anterior,actual):
                        base=max(abs(previo),abs(nuevo),1.0)
                        max_delta=max(max_delta,abs(nuevo-previo)/base*100)
                anterior=actual
            if max_delta>delta:
                descartados_delta+=1
                continue
            candidato={"fecha":fecha,"carga_maxima_a":maxima,"delta_maximo_pct":max_delta,"fuente":fuente}
            if mejor is None or (maxima,fecha)>(mejor["carga_maxima_a"],mejor["fecha"]):
                mejor=candidato
        if mejor is None:
            raise ValueError(
                f"No hay días válidos para {dispositivo}: 96 intervalos, "
                f"{tipo.lower()}, delta máximo {delta:g}%."
            )
        return {**mejor,"fecha":mejor["fecha"].isoformat(),"tipo_dia":tipo,
                "dia_semana":dia_semana,"delta_configurado_pct":delta,
                "dias_evaluados":len(por_fecha),"descartados_delta":descartados_delta,
                "descartados_incompletos":descartados_incompletos}
    def serie_dia(self, medida: dict, fecha: date, campos: tuple[tuple[str, str], ...]) -> dict:
        inicio = f"{fecha.isoformat()} 00:00:00"
        fin = f"{(fecha + timedelta(days=1)).isoformat()} 00:00:00"
        subestacion = str(medida.get("medida_subestacion") or medida.get("subestacion") or "").strip().upper()
        dispositivo = str(medida.get("medida_dispositivo") or medida.get("interruptor") or "").strip().upper()
        fuente_solicitada = str(medida.get("medida_fuente") or medida.get("fuente") or "").strip().upper()
        if not subestacion or not dispositivo:
            raise ValueError("La medida no tiene subestación o dispositivo configurado.")

        names = [name for name, _ in campos]
        quoted = ",".join(f'"{name}"' for name in names)
        sql = (
            f'SELECT fecha_hora,fuente,{quoted} FROM mediciones '
            "WHERE fecha_hora>=? AND fecha_hora<? AND subestacion=? AND interruptor=? "
            "ORDER BY fecha_hora"
        )
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (inicio, fin, subestacion, dispositivo))
            rows = cur.fetchall()

        fuentes = {str(row[1] or "").upper() for row in rows}
        fuente = fuente_solicitada if fuente_solicitada in fuentes else next((x for x in PRIORIDAD_FUENTE if x in fuentes), "")
        rows = [row for row in rows if str(row[1] or "").upper() == fuente]
        if not rows:
            return serie_dia_scada(medida, fecha, campos, UNIDADES)
        series = []
        for index, (name, label) in enumerate(campos, start=2):
            es_potencia = name in {"P", "Q", "S"}
            divisor = 1000.0 if es_potencia and str(medida.get("tipo_objeto") or "").upper() == "ALIMENTADOR" else 1.0
            points = [[str(row[0]), abs(float(row[index])) / divisor if es_potencia else float(row[index])] for row in rows if row[index] is not None]
            series.append({"clave": name, "nombre": label, "unidad": UNIDADES[name], "puntos": points})
        return {
            "subestacion": subestacion,
            "dispositivo": dispositivo,
            "fuente": fuente,
            "nivel_kv": medida.get("nivel_kv"),
            "cantidad_registros": len(rows),
            "potencias_convertidas_k_a_mega": str(medida.get("tipo_objeto") or "").upper() == "ALIMENTADOR",
            "series": series,
        }
