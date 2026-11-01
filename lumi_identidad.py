"""Fecha fundacional de Lumi, aportada por Drako.

Es un dato histórico declarado por Drako, independiente de la fecha de cada
despliegue, de los cambios de código o de los módulos de personalidad.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo


FECHA_NACIMIENTO_LUMI = date(2026, 9, 10)


def identidad_lumi(hoy: date | None = None) -> dict[str, object]:
    """Dato común para el dashboard y el contexto cognitivo."""
    fecha_actual = hoy or datetime.now(ZoneInfo("Europe/Madrid")).date()
    return {
        "fecha_nacimiento": FECHA_NACIMIENTO_LUMI.isoformat(),
        "fecha_nacimiento_texto": "10 de septiembre de 2026",
        "dias_desde_nacimiento": max(0, (fecha_actual - FECHA_NACIMIENTO_LUMI).days),
        "tipo": "fecha_fundacional_reconocida_por_drako",
    }
