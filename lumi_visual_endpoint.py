"""Estado visual protegido y de solo lectura para el cuerpo de Lumi.

Las etiquetas son una *representación* de las variables originales de
homeostasis; no son pensamientos ni una nueva evaluación de Gemini.
No se exponen la memoria, el monólogo interno ni claves de terceros.
"""

from __future__ import annotations

import math
import os
import secrets
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse


def _normalizar(valor: Any, predeterminado: float = 0.5) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return predeterminado
    if not math.isfinite(numero):
        return predeterminado
    return max(0.0, min(1.0, numero))


def calcular_visual(homeostasis: Any) -> dict[str, object]:
    """Traduce SOLO variables existentes del núcleo a señales de animación.

    Cuando el estado sea ambiguo se usa neutral: la interfaz no debe
    inventar enfado, miedo o cariño basándose en las palabras del chat.
    """
    valencia = _normalizar(getattr(homeostasis, "valencia", 0.5))
    dopamina = _normalizar(getattr(homeostasis, "dopamina", 0.5))
    alerta = _normalizar(getattr(homeostasis, "norepinefrina", 0.2))
    fatiga = _normalizar(getattr(homeostasis, "adenosina", 0.1))
    oxitocina = _normalizar(getattr(homeostasis, "oxitocina", 0.5))
    en_sueno = bool(getattr(homeostasis, "en_sueno", False))

    if en_sueno:
        expresion, matiz, brillo, pulso = "neutral", "reposo", 0.03, 0.10
    elif fatiga >= 0.86:
        expresion, matiz, brillo, pulso = "neutral", "cansancio", 0.10, 0.15
    elif valencia >= 0.67 and dopamina >= 0.66:
        expresion, matiz, brillo, pulso = "joy", "ilusion", 0.96, 0.82
    elif valencia >= 0.62 and oxitocina >= 0.78:
        expresion, matiz, brillo, pulso = "joy", "afecto", 0.58, 0.28
    elif valencia >= 0.62:
        expresion, matiz, brillo, pulso = "joy", "alegria", 0.70, 0.42
    elif valencia <= 0.29:
        expresion, matiz, brillo, pulso = "sadness", "baja_valencia", 0.08, 0.16
    elif alerta >= 0.81 and dopamina >= 0.72:
        expresion, matiz, brillo, pulso = "surprise", "activacion", 0.69, 0.65
    else:
        expresion, matiz, brillo, pulso = "neutral", "equilibrio", 0.24, 0.25

    # No se devuelve ningún valor emocional bruto: solo instrucciones
    # audiovisuales de rango limitado para el pet.
    return {
        "version": 1,
        "expression": expresion,
        "nuance": matiz,
        "cyan_glow": round(brillo, 2),
        "pulse": round(pulso, 2),
    }


def crear_router_visual(proveedor_homeostasis: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/desktop/visual")
    def estado_visual(authorization: str | None = Header(default=None)) -> JSONResponse:
        clave = os.getenv("LUMI_DESKTOP_TOKEN", "")
        if not clave:
            raise HTTPException(503, detail="Estado visual desactivado")
        if not secrets.compare_digest(authorization or "", "Bearer " + clave):
            raise HTTPException(401, detail="No autorizado")

        datos = calcular_visual(proveedor_homeostasis())
        return JSONResponse(datos, headers={"Cache-Control": "no-store"})

    return router
