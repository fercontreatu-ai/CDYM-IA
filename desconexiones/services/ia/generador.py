from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


FNO_CORTE_CON_CARGA = {18800, 19600, 19700, 19800}
FNO_SECCIONAMIENTO = FNO_CORTE_CON_CARGA | {19300, 19400}
FNO_TRANSFORMADOR = 20400


@dataclass(frozen=True)
class RutaFuente:
    fuente_fid: str
    elementos: tuple[str, ...]


class GeneradorAislamiento:
    """Genera un corte seguro y verificable alrededor de un elemento objetivo."""

    def __init__(self, datos: dict[str, Any]):
        self.datos = datos
        self.elementos = {str(e["g3e_fid"]): e for e in datos.get("elementos", [])}
        self.por_nodo: dict[str, list[str]] = defaultdict(list)
        for fid, elemento in self.elementos.items():
            for nodo in self._nodos(elemento):
                self.por_nodo[nodo].append(fid)
        self.fuentes = {
            fid for fid, e in self.elementos.items()
            if int(e.get("g3e_fno") or 0) == 18800 and self._cerrado(e)
        }
        raiz = datos.get("raiz") or {}
        if raiz.get("g3e_fid") is not None:
            self.fuentes.add(str(raiz["g3e_fid"]))

    @staticmethod
    def _nodos(elemento):
        return tuple(str(n) for n in (elemento.get("nodo1"), elemento.get("nodo2")) if n not in (None, 0, "0"))

    @staticmethod
    def _cerrado(elemento):
        return str(elemento.get("estado_estable") or elemento.get("estado_operativo") or "CLOSED").upper() != "OPEN"

    def _nodo_fuente(self, fuente_fid: str) -> str | None:
        fuente = self.elementos[fuente_fid]
        nodos = self._nodos(fuente)
        if not nodos:
            return None
        # El lado de barra suele tener menos líneas de distribución conectadas.
        def puntaje(nodo):
            return sum(
                int(self.elementos[fid].get("g3e_fno") or 0) == 19000
                for fid in self.por_nodo[nodo] if fid != fuente_fid
            )
        return min(nodos, key=puntaje)

    def _fuentes_nodo(self):
        return {nodo: fid for fid in self.fuentes if (nodo := self._nodo_fuente(fid)) is not None}

    def _ruta_a_fuente(self, inicio: str, abiertos: set[str], excluidos: set[str]) -> RutaFuente | None:
        fuentes_nodo = self._fuentes_nodo()
        cola = deque([(inicio, tuple())])
        visitados = {inicio}
        while cola:
            nodo, ruta = cola.popleft()
            if nodo in fuentes_nodo:
                return RutaFuente(fuentes_nodo[nodo], ruta)
            for fid in self.por_nodo.get(nodo, []):
                if fid in abiertos or fid in excluidos:
                    continue
                elemento = self.elementos[fid]
                if not self._cerrado(elemento):
                    continue
                for siguiente in self._nodos(elemento):
                    if siguiente != nodo and siguiente not in visitados:
                        visitados.add(siguiente)
                        cola.append((siguiente, ruta + (fid,)))
        return None

    def _transformadores_energizados(self, abiertos: set[str], excluidos: set[str] | None = None):
        excluidos = excluidos or set()
        energizados = set()
        for fid, elemento in self.elementos.items():
            if int(elemento.get("g3e_fno") or 0) != FNO_TRANSFORMADOR:
                continue
            if any(self._ruta_a_fuente(nodo, abiertos, excluidos) for nodo in self._nodos(elemento)):
                energizados.add(fid)
        return energizados

    def generar(self, objetivo_fid: str) -> dict[str, Any]:
        objetivo_fid = str(objetivo_fid)
        objetivo = self.elementos.get(objetivo_fid)
        if not objetivo:
            return {"valido": False, "bloqueos": [f"El FID {objetivo_fid} no pertenece al circuito cargado."]}
        extremos = self._nodos(objetivo)
        if len(extremos) != 2:
            return {"valido": False, "bloqueos": ["El elemento objetivo no tiene dos extremos eléctricos identificados."]}
        if int(objetivo.get("g3e_fno") or 0) == 19000:
            return self._generar_puentes_linea(objetivo_fid, objetivo, extremos)

        abiertos: set[str] = set()
        planes: dict[str, str | None] = {}
        excluidos = {objetivo_fid}
        bloqueos = []
        evidencia = []
        max_iteraciones = max(1, len(self.elementos))
        for _ in range(max_iteraciones):
            rutas = [(extremo, self._ruta_a_fuente(extremo, abiertos, excluidos)) for extremo in extremos]
            rutas = [(extremo, ruta) for extremo, ruta in rutas if ruta]
            if not rutas:
                break
            progreso = False
            for extremo, ruta in rutas:
                candidato = next((fid for fid in ruta.elementos if int(self.elementos[fid].get("g3e_fno") or 0) in FNO_SECCIONAMIENTO), None)
                if not candidato:
                    bloqueos.append(
                        f"No existe equipo con capacidad de corte entre el extremo {extremo} y la fuente {ruta.fuente_fid}."
                    )
                    continue
                indice = ruta.elementos.index(candidato)
                requiere_proteccion = int(self.elementos[candidato].get("g3e_fno") or 0) not in FNO_CORTE_CON_CARGA
                protector = next((
                    fid for fid in ruta.elementos[indice + 1:]
                    if int(self.elementos[fid].get("g3e_fno") or 0) in FNO_CORTE_CON_CARGA
                ), None) if requiere_proteccion else None
                if requiere_proteccion and not protector:
                    bloqueos.append(
                        f"El seccionamiento {candidato} requiere descarga, pero no existe protección operable hacia la fuente {ruta.fuente_fid}."
                    )
                    continue
                if candidato not in abiertos:
                    abiertos.add(candidato)
                    planes[candidato] = protector
                    progreso = True
                    evidencia.append({"extremo": extremo, "fuente_fid": ruta.fuente_fid, "corte_fid": candidato, "protector_temporal_fid": protector})
            if bloqueos or not progreso:
                break

        pendientes = [extremo for extremo in extremos if self._ruta_a_fuente(extremo, abiertos, excluidos)]
        if pendientes:
            bloqueos.append("La simulación no logró dejar sin fuente todos los extremos del elemento objetivo.")
        if bloqueos:
            return {"valido": False, "objetivo": self._resumen(objetivo), "bloqueos": bloqueos, "evidencia": evidencia}

        antes = self._transformadores_energizados(set())
        despues = self._transformadores_energizados(abiertos)
        afectados = antes - despues
        cortes = sorted((self.elementos[fid] for fid in abiertos), key=lambda e: (e.get("subestacion", ""), e.get("circuito", ""), e.get("codigo", "")))
        directos = [e for e in cortes if not planes.get(str(e["g3e_fid"]))]
        protegidos: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in cortes:
            if protector := planes.get(str(e["g3e_fid"])):
                protegidos[protector].append(e)
        operaciones_des = [(e, "OPEN", "Corte con capacidad de interrupción para aislar el objetivo.") for e in directos]
        for protector_fid, seccionamientos in protegidos.items():
            protector = self.elementos[protector_fid]
            operaciones_des.append((protector, "OPEN", "Descargar temporalmente el circuito antes de operar seccionamiento sin capacidad de corte."))
            operaciones_des.extend((e, "OPEN", "Abrir el seccionamiento descargado más cercano al objetivo.") for e in seccionamientos)
            operaciones_des.append((protector, "CLOSED", "Restablecer el alimentador conservando aislado el sector de trabajo."))
        operaciones_norm = []
        for protector_fid, seccionamientos in reversed(list(protegidos.items())):
            protector = self.elementos[protector_fid]
            operaciones_norm.append((protector, "OPEN", "Descargar temporalmente el circuito antes de normalizar el seccionamiento."))
            operaciones_norm.extend((e, "CLOSED", "Cerrar el seccionamiento descargado para normalizar el sector.") for e in reversed(seccionamientos))
            operaciones_norm.append((protector, "CLOSED", "Restablecer el alimentador después de la normalización."))
        operaciones_norm.extend((e, "CLOSED", "Cerrar el equipo de corte para normalizar el circuito.") for e in reversed(directos))
        desenergizacion = [self._paso(e, accion, i + 1, motivo) for i, (e, accion, motivo) in enumerate(operaciones_des)]
        normalizacion = [self._paso(e, accion, i + 1, motivo) for i, (e, accion, motivo) in enumerate(operaciones_norm)]
        return {
            "valido": True,
            "objetivo": self._resumen(objetivo),
            "desenergizacion": desenergizacion,
            "normalizacion": normalizacion,
            "impacto": {"transformadores_estimados": len(afectados)},
            "evidencia": evidencia,
            "advertencias": [
                "Propuesta en modo recomendación: requiere simulación completa y aprobación del operador.",
                "Las cuchillas y aisladeros solo se proponen descargados mediante un equipo de protección temporal.",
            ],
        }

    def _generar_puentes_linea(self, objetivo_fid, objetivo, extremos):
        rutas = [(extremo, self._ruta_a_fuente(extremo, set(), {objetivo_fid})) for extremo in extremos]
        alimentados = [(extremo, ruta) for extremo, ruta in rutas if ruta]
        if not alimentados:
            puentes = [self._paso_puentes(objetivo, extremos[0], "OPEN", 1, "Abrir los puentes de la línea, que ya se encuentra sin fuente.")]
            normal = [self._paso_puentes(objetivo, extremos[0], "CLOSED", 1, "Reconectar los puentes para normalizar la línea.")]
            return self._respuesta_linea(objetivo, puentes, normal, [], set())

        protecciones: dict[str, list[str]] = defaultdict(list)
        evidencia = []
        for extremo, ruta in alimentados:
            protector = next((
                fid for fid in ruta.elementos
                if int(self.elementos[fid].get("g3e_fno") or 0) in FNO_CORTE_CON_CARGA
            ), None)
            if not protector:
                return {
                    "valido": False,
                    "objetivo": self._resumen(objetivo),
                    "bloqueos": [f"No existe protección con capacidad de corte para descargar los puentes del nodo {extremo}."],
                }
            protecciones[protector].append(extremo)
            evidencia.append({
                "extremo_alimentado": extremo,
                "fuente_fid": ruta.fuente_fid,
                "protector_temporal_fid": protector,
                "maniobra_virtual": "PUENTES_LINEA",
            })

        operaciones_des = []
        for protector_fid, nodos in protecciones.items():
            protector = self.elementos[protector_fid]
            operaciones_des.append((protector, "OPEN", "Descargar temporalmente el tramo antes de retirar los puentes de la línea."))
            operaciones_des.extend((objetivo, "OPEN", f"Abrir los puentes de alimentación de la línea en el nodo {nodo}.") for nodo in nodos)
            operaciones_des.append((protector, "CLOSED", "Volver a energizar el reconectador conservando aislada la línea intervenida."))
        operaciones_norm = []
        for protector_fid, nodos in reversed(list(protecciones.items())):
            protector = self.elementos[protector_fid]
            operaciones_norm.append((protector, "OPEN", "Descargar temporalmente el tramo antes de reconectar los puentes."))
            operaciones_norm.extend((objetivo, "CLOSED", f"Reconectar los puentes de la línea en el nodo {nodo}.") for nodo in reversed(nodos))
            operaciones_norm.append((protector, "CLOSED", "Volver a energizar el reconectador después de normalizar la línea."))

        desenergizacion = []
        for i, (elemento, accion, motivo) in enumerate(operaciones_des, 1):
            if elemento is objetivo:
                nodo = motivo.rsplit(" ", 1)[-1].rstrip(".")
                desenergizacion.append(self._paso_puentes(objetivo, nodo, accion, i, motivo))
            else:
                desenergizacion.append(self._paso(elemento, accion, i, motivo))
        normalizacion = []
        for i, (elemento, accion, motivo) in enumerate(operaciones_norm, 1):
            if elemento is objetivo:
                nodo = motivo.rsplit(" ", 1)[-1].rstrip(".")
                normalizacion.append(self._paso_puentes(objetivo, nodo, accion, i, motivo))
            else:
                normalizacion.append(self._paso(elemento, accion, i, motivo))
        return self._respuesta_linea(objetivo, desenergizacion, normalizacion, evidencia, {objetivo_fid})

    def _respuesta_linea(self, objetivo, desenergizacion, normalizacion, evidencia, excluidos):
        antes = self._transformadores_energizados(set())
        despues = self._transformadores_energizados(set(), excluidos)
        return {
            "valido": True,
            "objetivo": self._resumen(objetivo),
            "desenergizacion": desenergizacion,
            "normalizacion": normalizacion,
            "impacto": {"transformadores_estimados": len(antes - despues)},
            "evidencia": evidencia,
            "advertencias": [
                "La apertura de puentes es una maniobra virtual propuesta sobre el nodo GTECH indicado.",
                "Requiere verificación en campo, simulación completa y aprobación del operador.",
            ],
        }

    @staticmethod
    def _resumen(elemento):
        return {k: elemento.get(k) for k in ("g3e_fid", "codigo", "tipo", "circuito", "subestacion", "g3e_fno")}

    @classmethod
    def _paso(cls, elemento, accion, numero, motivo):
        return {
            "numero": numero,
            "g3e_fid": elemento.get("g3e_fid"),
            "codigo": elemento.get("codigo") or str(elemento.get("g3e_fid")),
            "tipo": elemento.get("tipo") or "Equipo de corte",
            "accion": accion,
            "circuito": elemento.get("circuito") or "",
            "subestacion": elemento.get("subestacion") or "",
            "motivo": motivo,
        }

    @classmethod
    def _paso_puentes(cls, elemento, nodo, accion, numero, motivo):
        codigo = elemento.get("codigo") or str(elemento.get("g3e_fid"))
        return {
            "numero": numero,
            "g3e_fid": elemento.get("g3e_fid"),
            "codigo": f"Puentes de {codigo} · nodo {nodo}",
            "tipo": "Puentes o conexión de línea",
            "accion": accion,
            "circuito": elemento.get("circuito") or "",
            "subestacion": elemento.get("subestacion") or "",
            "motivo": motivo,
            "virtual": True,
            "nodo": nodo,
        }
