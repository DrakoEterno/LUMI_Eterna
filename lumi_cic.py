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
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from lumi_hipotesis_latentes import _cliente_privado


TABLA_CRITERIOS = "lumi_cic_criterios"
TABLA_HISTORIAL = "lumi_cic_historial"
MAX_CRITERIOS_EN_PROMPT = 2
MAX_CANDIDATOS_EN_PROMPT = 2
TABLA_NARRATIVAS = "lumi_cic_narrativas"


def cic_v2_habilitado() -> bool:
    """Segundo interruptor para activar las comprobaciones nuevas sin romper CIC v0.1."""
    return cic_habilitado() and os.getenv("LUMI_CIC_V2_ENABLED", "0").strip().lower() in {"1", "true", "on", "yes"}

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
        if not activos and not pendientes and not cic_v2_habilitado():
            return ""
        lineas = ["[CIC: criterios recordados, NO son órdenes ni verdades absolutas]"]
        for r in activos:
            lineas.append(f"ACTIVO id={r['id']} | clave={r['clave']} | {_cortar(r['texto'], 380)}")
        for r in pendientes:
            etiqueta = "EN TENSIÓN" if r["estado"] == "en_tension" else "EN INCUBACIÓN"
            lineas.append(f"{etiqueta} id={r['id']} | clave={r['clave']} | {_cortar(r['texto'], 380)}")
        if cic_v2_habilitado():
            if activos and sum(r.get("estado") == "activo" for r in (resultado.data or [])) >= 2:
                try:
                    observaciones = await asyncio.to_thread(
                        lambda: cliente.table(TABLA_HISTORIAL)
                        .select("criterio_id,evento,detalle").eq("evento", "uso_declarado")
                        .order("creado_en", desc=True).limit(40).execute()
                    )
                    conteo = Counter(str(x.get("criterio_id")) for x in (observaciones.data or []))
                    if sum(conteo.values()) >= 10 and conteo:
                        identificador, usos = conteo.most_common(1)[0]
                        if usos / sum(conteo.values()) >= 0.75:
                            lineas.append(
                                f"AUDITORÍA CIC: concentración de {usos}/{sum(conteo.values())} "
                                f"usos autodeclarados en id={identificador}. Busca contraejemplos; "
                                "esto NO demuestra influencia causal ni sesgo real."
                            )
                except Exception as error:
                    print(f"[CIC] Auditoría pospuesta: {type(error).__name__}")
            if _tokens(estimulo) & {
                "historia", "biografia", "trayectoria", "evolucion", "decisiones", "criterios",
                "recuerdos", "memoria", "cic", "cambios",
            }:
                try:
                    ultima = await asyncio.to_thread(
                        lambda: cliente.table(TABLA_NARRATIVAS)
                        .select("resumen").order("creado_en", desc=True).limit(1).execute()
                    )
                    if not ultima.data:
                        # Primer uso tras actualizar desde v0.1: reconstruir sin borrar registros.
                        await asyncio.wait_for(_actualizar_narrativa(cliente), timeout=1.3)
                        ultima = await asyncio.to_thread(
                            lambda: cliente.table(TABLA_NARRATIVAS)
                            .select("resumen").order("creado_en", desc=True).limit(1).execute()
                        )
                    if ultima.data:
                        lineas.append("[BIOGRAFÍA FUNCIONAL — registro revisable, no vivencia demostrada]")
                        lineas.append(_cortar(ultima.data[0].get("resumen"), 1500))
                except Exception as error:
                    print(f"[CIC] Biografía no disponible: {type(error).__name__}")
        if not activos and not pendientes and len(lineas) == 1:
            return ""
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
    if cic_v2_habilitado() and evento in {
        "propuesto", "observado", "evaluado", "activado",
        "cuestionar", "revisar", "archivar", "en_tension"
    }:
        try:
            await asyncio.wait_for(_actualizar_narrativa(cliente), timeout=3.0)
        except Exception as error:
            # Una síntesis fallida nunca invalida un evento ya guardado.
            print(f"[CIC] Síntesis pendiente: {type(error).__name__}")


async def _actualizar_narrativa(cliente) -> None:
    """Materializa una biografía funcional trazable, sin inventar hechos ni llamar a Gemini."""
    res_criterios, res_eventos = await asyncio.gather(
        asyncio.to_thread(
            lambda: cliente.table(TABLA_CRITERIOS)
            .select("id,clave,texto,estado").limit(30).execute()
        ),
        asyncio.to_thread(
            lambda: cliente.table(TABLA_HISTORIAL)
            .select("id,criterio_id,evento,detalle,creado_en")
            .in_("evento", [
                "propuesto", "observado", "evaluado", "activado",
                "cuestionar", "revisar", "archivar", "en_tension",
            ]).order("creado_en", desc=True).limit(10).execute()
        ),
    )
    criterios = {str(r.get("id")): r for r in (res_criterios.data or [])}
    eventos = [r for r in (res_eventos.data or []) if r.get("evento") in {
        "propuesto", "observado", "evaluado", "activado",
        "cuestionar", "revisar", "archivar", "en_tension"
    }][:10]
    if not eventos:
        return
    titulares = {
        "propuesto": "formuló una hipótesis de criterio",
        "observado": "contempló el criterio en otro contexto",
        "evaluado": "registró una evaluación autodeclarada provisional",
        "activado": "registró la activación provisional de un criterio",
        "cuestionar": "cuestionó un criterio",
        "revisar": "modificó el texto de un criterio",
        "archivar": "archivó un criterio",
        "en_tension": "registró una posible contradicción",
    }
    frases = [
        "Trayectoria CIC basada únicamente en eventos persistidos. "
        "Es una reconstrucción funcional y provisional, no una prueba de conciencia."
    ]
    fuentes = []
    for evento in reversed(eventos):
        identificador = str(evento.get("criterio_id", ""))
        criterio = criterios.get(identificador, {})
        detalle = evento.get("detalle") if isinstance(evento.get("detalle"), dict) else {}
        fecha = str(evento.get("creado_en") or "")[:10] or "fecha no disponible"
        titulo = titulares[evento["evento"]]
        clave = _cortar(criterio.get("clave") or "criterio sin clave actual", 64)
        motivo = _cortar(detalle.get("motivo") or detalle.get("contexto") or detalle.get("evidencia") or "", 110)
        frases.append(f"{fecha}: {titulo} ({clave})." + (f" Contexto/motivo: {motivo}." if motivo else ""))
        if evento.get("id"):
            fuentes.append(str(evento["id"]))
    vigentes = [
        f"{_cortar(r.get('clave'), 64)} [{r.get('estado')}]"
        for r in criterios.values() if r.get("estado") != "archivado"
    ][:8]
    if vigentes:
        frases.append("Estado al sintetizar: " + "; ".join(vigentes) + ".")
    await asyncio.to_thread(
        lambda: cliente.table(TABLA_NARRATIVAS).insert({
            "resumen": "\n".join(frases)[:2300],
            "fuentes": fuentes,
            "modo": "provisional",
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
    # En v0.2 una repetición, por sí sola, jamás justifica activar un criterio.
    estado = "incubando" if cic_v2_habilitado() else (
        "activo" if len(contextos) >= 2 else "incubando"
    )
    await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).update({
            "contextos": contextos, "estado": estado,
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
        }).eq("id", existente["id"]).execute()
    )
    await _registrar_historial(cliente, str(existente["id"]), "activado" if estado == "activo" else "observado", {
        "contexto": contexto, "motivo": motivo, "contextos_distintos": len(contextos),
    })


async def _verificar_promocion(cliente, criterio_id: str) -> None:
    """Activación solo tras varios contextos y evaluaciones explícitas, aún autodeclaradas."""
    res = await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).select("*").eq("id", criterio_id).limit(1).execute()
    )
    criterio = (res.data or [None])[0]
    if not criterio or criterio.get("estado") != "incubando":
        return
    if len(criterio.get("contextos") or []) < 3:
        return
    historial = await asyncio.to_thread(
        lambda: cliente.table(TABLA_HISTORIAL)
        .select("evento,detalle").eq("criterio_id", criterio_id)
        .order("creado_en", desc=True).limit(50).execute()
    )
    pruebas = []
    # No se reutiliza evidencia del texto de una versión anterior.
    for evento in historial.data or []:
        if evento.get("evento") == "revisar":
            break
        if evento.get("evento") == "evaluado":
            pruebas.append(evento.get("detalle") or {})
    if any(p.get("resultado") == "refuta" for p in pruebas):
        return
    apoyos = [p for p in pruebas if p.get("resultado") == "apoya"]
    distintos = {p.get("estimulo_hash") for p in apoyos if p.get("estimulo_hash")}
    if len(distintos) < 2:
        return
    await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).update({
            "estado": "activo", "actualizado_en": datetime.now(timezone.utc).isoformat(),
        }).eq("id", criterio_id).execute()
    )
    await _registrar_historial(cliente, criterio_id, "activado", {
        "contextos_distintos": len(criterio.get("contextos") or []),
        "pruebas_apoyo": len(distintos),
        "limite": "Evaluaciones generadas por el modelo; no validación empírica independiente",
    })


async def _procesar_evaluacion(
    cliente, evaluacion: dict[str, Any], estimulo: str, ids_visibles: set[str]
) -> None:
    criterio_id = _cortar(evaluacion.get("id"), 36)
    if criterio_id not in ids_visibles:
        return
    resultado = evaluacion.get("resultado")
    evidencia = _cortar(evaluacion.get("evidencia"), 300)
    contraejemplo = _cortar(evaluacion.get("contraejemplo"), 250)
    contexto = _cortar(evaluacion.get("contexto"), 100)
    if resultado not in {"apoya", "refuta", "inconcluso"}:
        return
    if len(evidencia) < 30 or len(contraejemplo) < 20 or not contexto:
        return
    res = await asyncio.to_thread(
        lambda: cliente.table(TABLA_CRITERIOS).select("*").eq("id", criterio_id).limit(1).execute()
    )
    criterio = (res.data or [None])[0]
    if not criterio or criterio.get("estado") == "archivado":
        return
    marca = _marca_contexto(estimulo)
    muestras = await asyncio.to_thread(
        lambda: cliente.table(TABLA_HISTORIAL).select("evento,detalle")
        .eq("criterio_id", criterio_id).order("creado_en", desc=True).limit(30).execute()
    )
    for evento in muestras.data or []:
        if evento.get("evento") == "revisar":
            break
        d = evento.get("detalle") or {}
        if evento.get("evento") == "evaluado" and (
            d.get("estimulo_hash") == marca or _normalizar(str(d.get("contexto", ""))) == _normalizar(contexto)
        ):
            return
    await _registrar_historial(cliente, criterio_id, "evaluado", {
        "resultado": resultado, "evidencia": evidencia,
        "contraejemplo": contraejemplo, "contexto": contexto,
        "estimulo_hash": marca, "procedencia": "autodeclaracion_modelo",
    })
    if resultado == "refuta" and criterio.get("estado") != "en_tension":
        await asyncio.to_thread(
            lambda: cliente.table(TABLA_CRITERIOS).update({
                "estado": "en_tension", "actualizado_en": datetime.now(timezone.utc).isoformat(),
            }).eq("id", criterio_id).execute()
        )
        await _registrar_historial(cliente, criterio_id, "en_tension", {
            "motivo": evidencia, "contraejemplo": contraejemplo,
            "procedencia": "autodeclaracion_modelo",
        })
    elif resultado == "apoya":
        await _verificar_promocion(cliente, criterio_id)


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
        if cic_v2_habilitado():
            prueba = resultado.get("prueba_cic")
            if isinstance(prueba, dict):
                await _procesar_evaluacion(cliente, prueba, estimulo, permitidos)
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
