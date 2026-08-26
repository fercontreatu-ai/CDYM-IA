from collections.abc import Callable, Iterable

from .contratos import EvaluacionProtocolo, ManiobraPropuesta, ResultadoRegla, Severidad

Regla = Callable[[ManiobraPropuesta], ResultadoRegla]


def regla_accion_conocida(maniobra: ManiobraPropuesta) -> ResultadoRegla:
    acciones = {"OPEN", "CLOSED", "INSTALAR", "RETIRAR"}
    accion = maniobra.accion.strip().upper()
    return ResultadoRegla(
        codigo="IA-R000", aprobada=accion in acciones, severidad=Severidad.BLOQUEO,
        mensaje="La acción pertenece al catálogo operativo." if accion in acciones else f"Acción no reconocida: {maniobra.accion}.",
        evidencia={"accion": accion, "acciones_permitidas": sorted(acciones)},
    )


def regla_elemento_identificado(maniobra: ManiobraPropuesta) -> ResultadoRegla:
    identificado = bool(maniobra.elemento_id.strip())
    return ResultadoRegla(
        codigo="IA-R001", aprobada=identificado, severidad=Severidad.BLOQUEO,
        mensaje="El elemento está identificado." if identificado else "No se permite una maniobra sin identificador de elemento.",
        evidencia={"elemento_id": maniobra.elemento_id},
    )


class EvaluadorRestricciones:
    """Puerta determinista: ninguna IA puede omitir estos resultados."""

    def __init__(self, reglas: Iterable[Regla] | None = None):
        self.reglas = tuple(reglas or (regla_accion_conocida, regla_elemento_identificado))

    def evaluar(self, maniobras: Iterable[ManiobraPropuesta]) -> EvaluacionProtocolo:
        resultados = tuple(regla(maniobra) for maniobra in maniobras for regla in self.reglas)
        valido = not any(not r.aprobada and r.severidad == Severidad.BLOQUEO for r in resultados)
        return EvaluacionProtocolo(valido=valido, resultados=resultados)
