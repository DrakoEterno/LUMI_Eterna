"""Objetivos, iniciativas y propuestas de evolución de Lumi (opt-in).

No modifica el código ni ejecuta proyectos propuestos por el modelo. Registra
sus propuestas y revisiones en Supabase, con historial auditable. Falla abierto
para el chat: las excepciones de este módulo no interrumpen la conversación.
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

OBJETIVOS = "lumi_autonomia_objetivos"
HISTORIAL = "lumi_autonomia_historial"
EVOLUCION = "lumi_autonomia_evolucion"
INICIATIVAS = "lumi_autonomia_iniciativas"
EVOLUCION_HISTORIAL = "lumi_autonomia_evolucion_historial"


def autonomia_habilitada() -> bool:
    return (
        os.getenv("LUMI_AUTONOMIA_V1_ENABLED", "0").strip().lower()
        in {"1", "true", "yes", "on"}
        and os.getenv("LUMI_CIC_ENABLED", "0").strip().lower()
        in {"1", "true", "yes", "on"}
    )


def _texto(value: Any, max_len: int) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", value).strip()[:max_len]


def _clave(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized if re.fullmatch(r"[a-z0-9_]{3,64}", normalized) else ""


def _id(value: Any) -> str:
    candidate = _texto(value, 36)
    return candidate if re.fullmatch(r"[0-9a-fA-F-]{36}", candidate) else ""


async def _evento(cliente: Any, objetivo_id: str, evento: str, detalle: dict) -> None:
    await asyncio.to_thread(lambda: cliente.table(HISTORIAL).insert({
        "objetivo_id": objetivo_id, "evento": evento, "detalle": detalle,
    }).execute())


async def preparar_contexto_autonomia(estimulo: str, *, para_stream: bool = False) -> str:
    """Devuelve metas revisables, nunca órdenes, con identificadores verificables."""
    if not autonomia_habilitada():
        return ""
    try:
        cli = _cliente_privado()
        res = await asyncio.to_thread(lambda: cli.table(OBJETIVOS)
            .select("id,clave,titulo,motivo,estado,progreso")
            .in_("estado", ["activo", "pausado"])
            .order("actualizado_en", desc=True).limit(15).execute())
        objetivos = res.data or []
        tokens = set(re.findall(r"[a-záéíóúñ0-9]{4,}", (estimulo or "").lower()))

        def puntuacion(o: dict) -> int:
            texto = f"{o.get('titulo','')} {o.get('motivo','')} {o.get('clave','')}".lower()
            return len(tokens.intersection(set(re.findall(r"[a-záéíóúñ0-9]{4,}", texto))))

        if not para_stream:
            relevantes = sorted(objetivos, key=puntuacion, reverse=True)
            elegidos = [o for o in relevantes if puntuacion(o)] or objetivos[:2]
        else:
            elegidos = [o for o in objetivos if o.get("estado") == "activo"]
        elegidos = elegidos[:3]
        lineas = ["[OBJETIVOS E IDEAS PROPIAS — revisables, no obligatorios]"]
        for o in elegidos:
            lineas.append(
                f"OBJETIVO id={o['id']} estado={o['estado']} clave={_texto(o.get('clave'), 64)}: "
                f"{_texto(o.get('titulo'), 180)}; motivo: {_texto(o.get('motivo'), 190)}; "
                f"progreso: {_texto(o.get('progreso'), 160)}"
            )
        if not para_stream and re.search(r"mejor|arquitect|estructur|evoluc|modific|codigo|program", (estimulo or "").lower()):
            try:
                propuestas = await asyncio.to_thread(lambda: cli.table(EVOLUCION)
                    .select("id,titulo,motivo,beneficio,riesgo,estado")
                    .in_("estado", ["propuesta", "en_revision"])
                    .order("creado_en", desc=True).limit(2).execute())
                for p in (propuestas.data or []):
                    lineas.append(
                        f"PROPUESTA id={p['id']} estado={p['estado']}: "
                        f"{_texto(p.get('titulo'), 130)}; motivo: {_texto(p.get('motivo'), 130)}; "
                        f"beneficio: {_texto(p.get('beneficio'), 130)}; riesgo: {_texto(p.get('riesgo'), 130)}"
                    )
            except Exception as error:
                print(f"[AUTONOMÍA] Propuestas omitidas: {type(error).__name__}")
        if len(lineas) == 1:
            return ""
        lineas.append("Puedes mantener, cuestionar, modificar, pausar o abandonar tus objetivos e ideas. No tienes que inventar nuevos.")
        return "\n".join(lineas)
    except Exception as error:
        print(f"[AUTONOMÍA] Contexto omitido: {type(error).__name__}")
        return ""


async def _nuevo_objetivo(cli: Any, value: dict) -> None:
    clave, titulo = _clave(value.get("clave")), _texto(value.get("titulo"), 180)
    motivo = _texto(value.get("motivo"), 500)
    if not clave or len(titulo) < 12 or len(motivo) < 15:
        return
    res = await asyncio.to_thread(lambda: cli.table(OBJETIVOS)
        .select("id").eq("clave", clave).limit(1).execute())
    if res.data:
        return
    activos = await asyncio.to_thread(lambda: cli.table(OBJETIVOS)
        .select("id").in_("estado", ["activo", "pausado"]).limit(12).execute())
    if len(activos.data or []) >= 12:
        return
    nuevo = await asyncio.to_thread(lambda: cli.table(OBJETIVOS).insert({
        "clave": clave, "titulo": titulo, "motivo": motivo,
        "estado": "activo", "progreso": "",
    }).execute())
    if nuevo.data:
        await _evento(cli, str(nuevo.data[0]["id"]), "creado", {"motivo": motivo, "titulo": titulo})


async def _revision_objetivo(cli: Any, value: dict, visibles: set[str]) -> None:
    objetivo_id, accion = _id(value.get("id")), value.get("accion")
    motivo = _texto(value.get("motivo"), 450)
    acciones = {"reorientar", "pausar", "reanudar", "completar", "descartar", "progresar"}
    if objetivo_id not in visibles or accion not in acciones or not motivo:
        return
    res = await asyncio.to_thread(lambda: cli.table(OBJETIVOS)
        .select("id,titulo,estado,progreso").eq("id", objetivo_id).limit(1).execute())
    anterior = (res.data or [None])[0]
    if not anterior or anterior.get("estado") in {"completado", "descartado"}:
        return
    estados = {"pausar": "pausado", "reanudar": "activo", "completar": "completado", "descartar": "descartado"}
    cambios = {"actualizado_en": datetime.now(timezone.utc).isoformat()}
    if accion in estados:
        cambios["estado"] = estados[accion]
    if accion == "reorientar":
        titulo = _texto(value.get("titulo_nuevo"), 180)
        if len(titulo) < 12:
            return
        cambios["titulo"] = titulo
    if accion == "progresar":
        progreso = _texto(value.get("progreso"), 500)
        if len(progreso) < 10:
            return
        cambios["progreso"] = progreso
    await asyncio.to_thread(lambda: cli.table(OBJETIVOS).update(cambios).eq("id", objetivo_id).execute())
    await _evento(cli, objetivo_id, accion, {"antes": anterior, "cambios": cambios, "motivo": motivo})


async def _proponer_evolucion(cli: Any, value: dict) -> None:
    titulo = _texto(value.get("titulo"), 180)
    motivo = _texto(value.get("motivo"), 500)
    beneficio = _texto(value.get("beneficio"), 500)
    riesgo = _texto(value.get("riesgo"), 500)
    alternativa = _texto(value.get("alternativa"), 400)
    if min(map(len, [titulo, motivo, beneficio, riesgo])) < 12:
        return
    # Nunca se instala una propuesta automáticamente.
    await asyncio.to_thread(lambda: cli.table(EVOLUCION).insert({
        "titulo": titulo, "motivo": motivo, "beneficio": beneficio,
        "riesgo": riesgo, "alternativa": alternativa, "estado": "propuesta",
    }).execute())


async def _revisar_evolucion(cli: Any, value: dict, visibles: set[str]) -> None:
    propuesta_id = _id(value.get("id"))
    accion = value.get("accion")
    motivo = _texto(value.get("motivo"), 500)
    if propuesta_id not in visibles or accion not in {"reconsiderar", "retirar"} or len(motivo) < 15:
        return
    res = await asyncio.to_thread(lambda: cli.table(EVOLUCION)
        .select("id,estado,titulo").eq("id", propuesta_id).limit(1).execute())
    anterior = (res.data or [None])[0]
    if not anterior or anterior.get("estado") not in {"propuesta", "en_revision"}:
        return
    estado = "en_revision" if accion == "reconsiderar" else "retirada"
    await asyncio.to_thread(lambda: cli.table(EVOLUCION)
        .update({"estado": estado}).eq("id", propuesta_id).execute())
    await asyncio.to_thread(lambda: cli.table(EVOLUCION_HISTORIAL).insert({
        "propuesta_id": propuesta_id, "evento": accion,
        "detalle": {"estado_anterior": anterior.get("estado"), "motivo": motivo},
    }).execute())


async def _registrar_iniciativa(cli: Any, value: dict, visibles: set[str], estimulo: str) -> None:
    asunto, motivo = _texto(value.get("asunto"), 180), _texto(value.get("motivo"), 400)
    vinculo = _id(value.get("objetivo_id"))
    if len(asunto) < 12 or len(motivo) < 12:
        return
    if vinculo and vinculo not in visibles:
        return
    await asyncio.to_thread(lambda: cli.table(INICIATIVAS).insert({
        "asunto": asunto, "motivo": motivo,
        "objetivo_id": vinculo or None,
        "contexto_hash": hashlib.sha256(estimulo.encode("utf-8")).hexdigest()[:16],
    }).execute())


async def registrar_acciones_autonomia(
    resultado: dict[str, Any], estimulo: str, *, ids_visibles: set[str] | None = None,
    propuestas_visibles: set[str] | None = None
) -> None:
    """Registra solo propuestas explícitas de Lumi; cada acción falla por separado."""
    if not autonomia_habilitada() or not isinstance(resultado, dict):
        return
    try:
        cli = _cliente_privado()
    except Exception as error:
        print(f"[AUTONOMÍA] Cliente no disponible: {type(error).__name__}")
        return
    visibles = ids_visibles or set()
    acciones = (
        ("objetivo_nuevo", _nuevo_objetivo),
        ("objetivo_revision", _revision_objetivo),
        ("propuesta_evolucion", _proponer_evolucion),
        ("revision_evolucion", _revisar_evolucion),
    )
    for campo, funcion in acciones:
        value = resultado.get(campo)
        if not isinstance(value, dict):
            continue
        try:
            if campo == "objetivo_revision":
                await funcion(cli, value, visibles)
            elif campo == "revision_evolucion":
                await funcion(cli, value, propuestas_visibles or set())
            else:
                await funcion(cli, value)
        except Exception as error:
            print(f"[AUTONOMÍA] {campo} omitido: {type(error).__name__}")
    iniciativa = resultado.get("iniciativa")
    if (isinstance(iniciativa, dict) and resultado.get("decision_motora") == "INICIAR_NUEVO_TEMA"):
        try:
            await _registrar_iniciativa(cli, iniciativa, visibles, estimulo)
        except Exception as error:
            print(f"[AUTONOMÍA] iniciativa omitida: {type(error).__name__}")
