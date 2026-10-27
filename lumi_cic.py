"""CIC: continuidad de criterios de Lumi, opcional y reversible.

No llama a Gemini ni altera la homeostasis. Toda escritura se realiza con
la clave privada del servidor y mantiene un historial separado.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from lumi_hipotesis_latentes import _cliente_privado


TABLA_CRITERIOS = "lumi_cic_criterios"
TABLA_HISTORIAL = "lumi_cic_historial"
MAX_CRITERIOS_EN_PROMPT = 2
MAX_CANDIDATOS_EN_PROMPT = 2

STOPWORDS = {
    "para", "como", "cuando", "donde", "porque", "sobre", "desde", "hasta",
    "entre", "antes", "despues", "esta", "este", "esto", "estos", "estas",
    "tengo", "tiene", "tienes", "hacer", "quiero", "puede", "podemos",
    "algun", "alguna", "seria", "muy", "pero", "tambien", "lumi", "drako",
    "cual", "cuales", "unos", "unas", "todo", "toda", "todos", "todas",
}


def cic_habilitado() -> bool:
    return os.getenv("LUMI_CIC_ENABLED", "0").strip().lower() in {"1", "true", "on", "yes"}


def _cliente():
    return _cliente_privado() if cic_habilitado() else None


def _normalizar(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _tokens(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{4,}", _normalizar(texto)) if t not in STOPWORDS}


def _clave_valida(valor: Any) -> str | None:
    clave = _normalizar(str(valor or "")).strip().replace("-", "_")
    return clave if re.fullmatch(r"[a-z0-9_]{3,64}", clave) else None


def _cortar(valor: Any, limite: int) -> str:
    if not isinstance(valor, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", valor).strip()[:limite]


def _marca_contexto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _relevancia(criterio: dict[str, Any], estimulo: str) -> int:
    base = _tokens(f"{criterio.get('texto', '')} {criterio.get('tema', '')}")
    return len(base.intersection(_tokens(estimulo)))


def seleccionar_criterios(registros: list[dict[str, Any]], estimulo: str) -> tuple[list[dict], list[dict]]:
    """Selección determinista y conservadora; nunca fuerza aplicar un criterio."""
    candidatos = sorted(
        (r for r in registros if _relevancia(r, estimulo) > 0),
        key=lambda r: _relevancia(r, estimulo), reverse=True,
    )
    activos = [r for r in candidatos if r.get("estado") == "activo"][:MAX_CRITERIOS_EN_PROMPT]
    pendientes = [r for r in candidatos if r.get("estado") in {"incubando", "en_tension"}][:MAX_CANDIDATOS_EN_PROMPT]
    return activos, pendientes


async def preparar_contexto_cic(estimulo: str) -> str:
    """Consulta solo registros relevantes; falla sin afectar al chat normal."""
    cliente = _cliente()
    if cliente is None or not estimulo:
        return ""
    try:
        resultado = await asyncio.to_thread(
            lambda: cliente.table(TABLA_CRITERIOS)
            .select("id,clave,texto,tema,estado")
            .in_("estado", ["activo", "incubando", "en_tension"])
            .order("actualizado_en", desc=True).limit(30).execute()
        )
        activos, pendientes = seleccionar_criterios(resultado.data or [], estimulo)
        if not activos and not pendientes:
            return ""
        lineas = ["[CIC: criterios recordados, NO son órdenes ni verdades absolutas]"]
        for r in activos:
            lineas.append(f"ACTIVO id={r['id']} | clave={r['clave']} | {_cortar(r['texto'], 380)}")
        for r in pendientes:
            etiqueta = "EN TENSIÓN" if r["estado"] == "en_tension" else "EN INCUBACIÓN"
            lineas.append(f"{etiqueta} id={r['id']} | clave={r['clave']} | {_cortar(r['texto'], 380)}")
        lineas.append("Puedes disentir, revisarlos o no aplicarlos. Prioriza evidencia nueva y la consulta actual.")
        return "\n".join(lineas)
    except Exception as error:
        print(f"[CIC] Recuperación omitida: {type(error).__name__}")
        return ""


async def _registrar_historial(cliente, criterio_id: str, evento: str, detalle: dict[str, Any]) -> None:
    await asyncio.to_thread(
        lambda: cliente.table(TABLA_HISTORIAL).insert({
            "criterio_id": criterio_id, "evento": evento, "detalle": detalle
        }).execute()
    )


async def _procesar_propuesta(cliente, propuesta: dict[str, Any], estimulo: str) -> None:
    clave = _clave_valida(propuesta.get("clave"))
    texto = _cortar(propuesta.get("texto"), 450)
    tema = _cortar(propuesta.get("tema"), 100)
    motivo = _cortar(propuesta.get("motivo"), 450)
    contexto = _cortar(propuesta.get("contexto"), 100)
    if not clave or len(texto) < 25 or not motivo or not contexto:
        return
    marca = _marca_contexto(estimulo)
    res = await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).select("*").eq("clave", clave).limit(1).execute()
    )
    existente = (res.data or [None])[0]
    if existente is None:
        # Economía de criterios: el sistema no acumula borradores ilimitados.
        pendientes = await asyncio.to_thread(
            lambda: cliente.table(TABLA_CRITERIOS)
            .select("id").eq("estado", "incubando").limit(15).execute()
        )
        if len(pendientes.data or []) >= 15:
            return
        creado = await asyncio.to_thread(
            lambda: cliente.table(TABLA_CRITERIOS).insert({
                "clave": clave, "texto": texto, "tema": tema, "motivo": motivo,
                "estado": "incubando", "contextos": [{"etiqueta": contexto, "marca": marca}],
            }).execute()
        )
        if creado.data:
            await _registrar_historial(cliente, str(creado.data[0]["id"]), "propuesto", {
                "texto": texto, "motivo": motivo, "contexto": contexto,
            })
        return

    if existente.get("estado") != "incubando":
        return
    previos = existente.get("contextos") or []
    # La misma pregunta o el mismo contexto no cuenta dos veces.
    if any(p.get("marca") == marca or _normalizar(str(p.get("etiqueta", ""))) == _normalizar(contexto)
           for p in previos if isinstance(p, dict)):
        return
    contextos = [*previos, {"etiqueta": contexto, "marca": marca}][:12]
    # Activación conservadora tras dos contextos diferentes; no se impone obediencia.
    estado = "activo" if len(contextos) >= 2 else "incubando"
    await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).update({
            "contextos": contextos, "estado": estado,
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
        }).eq("id", existente["id"]).execute()
    )
    await _registrar_historial(cliente, str(existente["id"]), "activado" if estado == "activo" else "observado", {
        "contexto": contexto, "motivo": motivo, "contextos_distintos": len(contextos),
    })


async def _procesar_revision(cliente, revision: dict[str, Any]) -> None:
    criterio_id = _cortar(revision.get("id"), 36)
    accion = revision.get("accion")
    motivo = _cortar(revision.get("motivo"), 450)
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", criterio_id) or accion not in {"cuestionar", "revisar", "archivar"} or not motivo:
        return
    res = await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).select("*").eq("id", criterio_id).limit(1).execute()
    )
    anterior = (res.data or [None])[0]
    if not anterior or anterior.get("estado") == "archivado":
        return
    cambios: dict[str, Any] = {"actualizado_en": datetime.now(timezone.utc).isoformat()}
    if accion == "cuestionar":
        cambios["estado"] = "en_tension"
    elif accion == "archivar":
        cambios["estado"] = "archivado"
    else:
        nuevo_texto = _cortar(revision.get("texto_nuevo"), 450)
        if len(nuevo_texto) < 25:
            return
        cambios.update({"texto": nuevo_texto, "estado": "incubando", "contextos": []})
    await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).update(cambios).eq("id", criterio_id).execute()
    )
    await _registrar_historial(cliente, criterio_id, accion, {
        "texto_anterior": anterior.get("texto"), "texto_nuevo": cambios.get("texto"), "motivo": motivo,
    })


async def registrar_resultado_cic(
    resultado: dict[str, Any], estimulo: str, *, ids_visibles: set[str] | None = None
) -> None:
    """Solo procesa sugerencias estructuradas válidas; nunca publica contenido privado."""
    cliente = _cliente()
    if cliente is None or not isinstance(resultado, dict):
        return
    try:
        propuesta = resultado.get("criterio_cic")
        if isinstance(propuesta, dict) and isinstance(estimulo, str):
            await _procesar_propuesta(cliente, propuesta, estimulo)
        revision = resultado.get("revision_cic")
        permitidos = ids_visibles or set()
        if isinstance(revision, dict) and revision.get("id") in permitidos:
            await _procesar_revision(cliente, revision)
        # Declaración del propio modelo, útil para auditoría pero no prueba causal.
        usados = resultado.get("criterios_cic_usados")
        if isinstance(usados, list):
            for identificador in usados[:2]:
                if not isinstance(identificador, str) or identificador not in permitidos:
                    continue
                await _registrar_historial(cliente, identificador, "uso_declarado", {
                    "estimulo_hash": _marca_contexto(estimulo),
                    "nota": "Autodeclaración del modelo, no verificación independiente",
                })
    except Exception as error:
        print(f"[CIC] Registro omitido: {type(error).__name__}")
