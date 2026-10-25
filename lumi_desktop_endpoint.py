"""Nueva ruta opcional del servidor Lumi; reutiliza el cerebro ya existente."""
import asyncio
import os
import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


class MensajeEscritorio(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def crear_router_escritorio(procesador) -> APIRouter:
    router = APIRouter()
    cola = asyncio.Lock()

    @router.post("/desktop/chat")
    async def chatear(mensaje: MensajeEscritorio, authorization: str | None = Header(default=None)) -> dict[str, str]:
        clave = os.getenv("LUMI_DESKTOP_TOKEN", "")
        if not clave:
            raise HTTPException(503, detail="Integración de escritorio no activada")
        if not secrets.compare_digest(authorization or "", "Bearer " + clave):
            raise HTTPException(401, detail="No autorizado")
        async with cola:
            respuesta, _imagen = await procesador(mensaje.text, origen="desktop")
        return {"respuesta": respuesta or ""}

    return router
