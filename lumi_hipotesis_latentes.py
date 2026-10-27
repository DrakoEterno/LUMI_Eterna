"""Acceso privado al banco de hipótesis de LUMI.

No sustituye el cliente Supabase existente ni llama a Gemini.
Si falta LUMI_PRIVATE_DB_KEY, todas las funciones quedan inactivas.
"""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from typing import Any

from supabase import create_client


TABLA_HIPOTESIS = "lumi_hipotesis_latentes"
TABLA_BITACORA = "lumi_bitacora_metacognitiva"


@lru_cache(maxsize=1)
def _cliente_privado():
    """Solo usa la clave secreta del servidor, nunca la clave pública."""
    url = os.getenv("SUPABASE_URL", "").strip()
    clave = os.getenv("LUMI_PRIVATE_DB_KEY", "").strip()
    if not url or not clave.startswith("sb_secret_"):
        return None
    try:
        return create_client(url, clave)
    except Exception as error:
        print(f"[HIPOTESIS] Cliente privado no disponible: {type(error).__name__}")
        return None


def banco_disponible() -> bool:
    return _cliente_privado() is not None


async def guardar_hipotesis(
    contenido: str,
    *,
    fuente_latentstream_id: int | None = None,
    version_de: str | None = None,
    titulo: str | None = None,
    peso_resonancia: float | None = None,
    motivo_estado: str | None = None,
    contexto: dict[str, Any] | None = None,
) -> str | None:
    """Guarda una hipótesis reservada sin publicarla ni enviarla a Telegram."""
    cliente = _cliente_privado()
    texto = (contenido or "").strip()
    if cliente is None or not texto:
        return None

    datos: dict[str, Any] = {
        "contenido": texto,
        "estado": "reservada",
        "contexto": contexto if isinstance(contexto, dict) else {},
    }
    if fuente_latentstream_id is not None:
        datos["fuente_latentstream_id"] = fuente_latentstream_id
    if version_de is not None:
        datos["version_de"] = version_de
    if titulo:
        datos["titulo"] = titulo
    if peso_resonancia is not None:
        datos["peso_resonancia"] = peso_resonancia
    if motivo_estado:
        datos["motivo_estado"] = motivo_estado

    try:
        respuesta = await asyncio.to_thread(
            lambda: cliente.table(TABLA_HIPOTESIS).insert(datos).execute()
        )
        return str(respuesta.data[0]["id"]) if respuesta.data else None
    except Exception as error:
        print(f"[HIPOTESIS] Error al guardar: {type(error).__name__}")
        return None


async def leer_hipotesis_reservadas(limite: int) -> list[dict[str, Any]]:
    """Lectura exclusivamente interna; no crea endpoints ni muestra el banco."""
    cliente = _cliente_privado()
    if cliente is None or limite < 1:
        return []
    try:
        respuesta = await asyncio.to_thread(
            lambda: cliente.table(TABLA_HIPOTESIS)
            .select("id,titulo,contenido,peso_resonancia,contexto,creada_en")
            .in_("estado", ["reservada", "madurando"])
            .order("creada_en", desc=True)
            .limit(limite)
            .execute()
        )
        return respuesta.data or []
    except Exception as error:
        print(f"[HIPOTESIS] Error al leer: {type(error).__name__}")
        return []


async def registrar_bitacora(
    tipo_evento: str,
    motivo: str,
    *,
    hipotesis_id: str | None = None,
    criterio_anterior: dict[str, Any] | None = None,
    criterio_nuevo: dict[str, Any] | None = None,
    evidencia: dict[str, Any] | None = None,
    resultado: dict[str, Any] | None = None,
) -> str | None:
    """Añade una traza; no reescribe ni elimina entradas anteriores."""
    cliente = _cliente_privado()
    if cliente is None or not motivo.strip():
        return None

    datos = {
        "tipo_evento": tipo_evento,
        "motivo": motivo,
        "criterio_anterior": criterio_anterior or {},
        "criterio_nuevo": criterio_nuevo or {},
        "evidencia": evidencia or {},
        "resultado": resultado or {},
    }
    if hipotesis_id:
        datos["hipotesis_id"] = hipotesis_id

    try:
        respuesta = await asyncio.to_thread(
            lambda: cliente.table(TABLA_BITACORA).insert(datos).execute()
        )
        return str(respuesta.data[0]["id"]) if respuesta.data else None
    except Exception as error:
        print(f"[HIPOTESIS] Error al registrar bitácora: {type(error).__name__}")
        return None
