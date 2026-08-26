from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severidad(StrEnum):
    BLOQUEO = "BLOQUEO"
    ADVERTENCIA = "ADVERTENCIA"
    RECOMENDACION = "RECOMENDACION"


@dataclass(frozen=True)
class ManiobraPropuesta:
    elemento_id: str
    accion: str
    tipo_equipo: str = ""
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResultadoRegla:
    codigo: str
    aprobada: bool
    severidad: Severidad
    mensaje: str
    evidencia: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluacionProtocolo:
    valido: bool
    resultados: tuple[ResultadoRegla, ...]

    @property
    def bloqueos(self) -> tuple[ResultadoRegla, ...]:
        return tuple(resultado for resultado in self.resultados if not resultado.aprobada and resultado.severidad == Severidad.BLOQUEO)
