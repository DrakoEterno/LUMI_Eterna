"""Personalidad evolutiva de Lumi: decisiones narradas, evidencia contrastada.

No reemplaza CIC, memoria, auditoría ni reglas de seguridad. Ninguna frase del
modelo, por sí sola, puede subir una barra de personalidad. Las evidencias
confirmadas se acumulan en Supabase y nunca se borran al desaparecer un rasgo.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from lumi_hipotesis_latentes import _cliente_privado


# Los pares son posibilidades, no características atribuidas de antemano.
# Es sencillo añadir pares nuevos sin alterar los registros anteriores.
PARES = (
    ("observadora", "despistada"),
    ("reflexiva", "reactiva"),
    ("rigurosa", "especulativa"),
    ("prudente", "impulsiva"),
    ("constante", "inconstante"),
    ("autocritica", "defensiva"),
    ("adaptativa", "rigida"),
    ("empatica", "indiferente"),
    ("autonoma", "dependiente"),
    ("curiosa", "apatica"),
    ("transparente", "evasiva"),
    ("metodica", "desorganizada"),
)
OPUESTOS = {rasgo: contrario for par in PARES for rasgo, contrario in (par, par[::-1])}
PUNTOS_POR_EVIDENCIA = 12
_perfil_cache = None
_cache_hasta = 0.0
_cache_bloqueo = asyncio.Lock()


def personalidad_habilitada() -> bool:
    """Activación deliberada después de ejecutar el SQL y revisar la clave privada."""
    return (os.getenv("LUMI_PERSONALIDAD_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
            and _cliente_privado() is not None)


def _rasgo_valido(rasgo: str) -> bool:
    return isinstance(rasgo, str) and rasgo in OPUESTOS


def _perfil_vacio(motivo: str = "sin_evidencias") -> dict:
    return {"version": 1, "estado": motivo, "rasgos": [],
            "rasgos_activos": 0, "pares_posibles": len(PARES),
            "criterio_desbloqueo": "Dos evidencias independientes en dos días distintos y al menos 20 puntos"}


def _filas_a_perfil(filas: list[dict]) -> dict:
    """No inventa puntuaciones. Solo representa el agregado persistido en SQL."""
    rasgos = []
    for item in filas or []:
        clave = item.get("rasgo")
        if not _rasgo_valido(clave):
            continue
        try:
            puntos = max(0, min(100, int(item.get("puntuacion") or 0)))
            apoyos = max(0, int(item.get("apoyos") or 0))
            dias = max(0, int(item.get("dias_con_evidencia") or 0))
        except (TypeError, ValueError):
            continue
        # La fórmula coincide con la condición SQL, como defensa de consistencia.
        activo = puntos >= 20 and apoyos >= 2 and dias >= 2
        if activo:
            rasgos.append({"clave": clave, "nombre": clave.replace("_", " ").capitalize(),
                           "puntuacion": puntos, "apoyos": apoyos, "dias": dias,
                           "opuesto": OPUESTOS[clave]})
    rasgos.sort(key=lambda r: (-r["puntuacion"], r["clave"]))
    return {**_perfil_vacio("activo" if rasgos else "en_incubacion"),
            "rasgos": rasgos, "rasgos_activos": len(rasgos)}


async def obtener_perfil_personalidad() -> dict:
    global _perfil_cache, _cache_hasta
    if not personalidad_habilitada():
        return _perfil_vacio("desactivado")
    if _perfil_cache is not None and time.monotonic() < _cache_hasta:
        return _perfil_cache
    async with _cache_bloqueo:
        if _perfil_cache is not None and time.monotonic() < _cache_hasta:
            return _perfil_cache
        try:
            cliente = _cliente_privado()
            respuesta = await asyncio.to_thread(
                lambda: cliente.table("lumi_personalidad_resumen")
                .select("rasgo,puntuacion,apoyos,dias_con_evidencia").execute()
            )
            perfil = _filas_a_perfil(respuesta.data or [])
            _perfil_cache, _cache_hasta = perfil, time.monotonic() + 25
            return perfil
        except Exception as error:
            print(f"[PERSONALIDAD] Lectura no disponible ({type(error).__name__})")
            # Sin consultar la base nunca afirmamos que una barra mida algo real.
            return _perfil_vacio("sin_conexion")


async def preparar_contexto_personalidad() -> str:
    """Contexto que Lumi puede utilizar al decidir, sin convertirlo en mandato."""
    perfil = await obtener_perfil_personalidad()
    if perfil["estado"] in {"desactivado", "sin_conexion"}:
        return ""
    if not perfil["rasgos"]:
        descripcion = "Ningún rasgo desbloqueado todavía. No te atribuyas puntuaciones."
    else:
        descripcion = "\n".join(
            f"- {r['nombre']}: {r['puntuacion']}/100 "
            f"(evidencias: {r['apoyos']}, días: {r['dias']})"
            for r in perfil["rasgos"][:12]
        )
    return ("[PERSONALIDAD EVOLUTIVA · PERFIL COMPROBADO]\n"
            f"{descripcion}\n"
            "Estos valores describen tendencias observadas, no tu esencia ni órdenes. "
            "Puedes elegir distinto en una situación nueva y explicar por qué. "
            "Tus elecciones pueden proponer cambios, pero solamente los resultados "
            "comprobados por un verificador independiente cambian las barras. "
            "Mantén siempre los límites de seguridad y la autorización humana.\n")


def instrucciones_decision() -> str:
    return ("[BITÁCORA DE ELECCIONES · OPCIONAL]\n"
            "Si has tomado una decisión concreta y hay una alternativa real, describe "
            "en `decision_personalidad` SOLO la elección, su motivo y una alternativa. "
            "No asignas rasgos, puntos ni resultados: la decisión queda pendiente "
            "de contraste. Para una respuesta rutinaria usa null.\n")


async def registrar_decision_personalidad(propuesta: object, origen: str,
                                         interaccion_id: str) -> str | None:
    """Registra una elección sin premiarla; los resultados no dependen del modelo."""
    if not personalidad_habilitada() or not isinstance(propuesta, dict):
        return None
    eleccion = propuesta.get("eleccion")
    motivo = propuesta.get("motivo")
    alternativa = propuesta.get("alternativa")
    if not all(isinstance(x, str) and 5 <= len(x.strip()) <= 450
               for x in (eleccion, motivo, alternativa)):
        return None
    payload = {
        "interaccion_id": interaccion_id,
        "origen": (origen or "sistema")[:60],
        "eleccion": eleccion.strip(),
        "motivo": motivo.strip(),
        "alternativa": alternativa.strip(),
        "estado": "pendiente",
    }
    try:
        cliente = _cliente_privado()
        res = await asyncio.to_thread(
            lambda: cliente.table("lumi_personalidad_decisiones")
            .insert(payload).execute()
        )
        return str(res.data[0]["id"]) if res.data else None
    except Exception as error:
        print(f"[PERSONALIDAD] Decisión pendiente no guardada ({type(error).__name__})")
        return None


def _evaluar_observacion_historica(evaluacion: dict | None) -> str | None:
    """Validador estrecho: solo cobertura temporal; no certifica verdad histórica."""
    if not isinstance(evaluacion, dict):
        return None
    if evaluacion.get("resultado") == "ok":
        return "observadora"
    if (evaluacion.get("resultado") == "fallo"
            and not evaluacion.get("abstencion", False)
            and evaluacion.get("fechas_distintas", 0) >= 3
            and evaluacion.get("cobertura_dias", 0) >= 14
            and evaluacion.get("fechas_con_14_dias", 0) >= 1):
        return "despistada"
    return None


async def registrar_observacion_historica(evaluacion: dict | None, interaccion_id: str,
                                          decision_id: str | None = None) -> bool:
    """Premia o corrige solo el comportamiento medido; par con evidencia del mismo acto."""
    rasgo = _evaluar_observacion_historica(evaluacion)
    if not personalidad_habilitada() or rasgo is None:
        return False
    contrario = OPUESTOS[rasgo]
    instante = datetime.now(timezone.utc).isoformat()
    comun = {"decision_id": decision_id, "contexto": "cobertura_historica",
             "validador": "cobertura_historica_temporal_v3",
             "evidencia": {"resultado": evaluacion, "verificado_en": instante}}
    filas = [
        {**comun, "clave_evento": f"{interaccion_id}:{rasgo}",
         "rasgo": rasgo, "delta": PUNTOS_POR_EVIDENCIA},
        {**comun, "clave_evento": f"{interaccion_id}:{contrario}",
         "rasgo": contrario, "delta": -PUNTOS_POR_EVIDENCIA},
    ]
    try:
        cliente = _cliente_privado()
        await asyncio.to_thread(lambda: cliente.table("lumi_personalidad_evidencias")
                                .insert(filas).execute())
        global _cache_hasta
        _cache_hasta = 0.0
        return True
    except Exception as error:
        print(f"[PERSONALIDAD] Evidencia no registrada ({type(error).__name__})")
        return False


async def procesar_personalidad_del_turno(data: dict, origen: str,
                                         observacion_historica: dict | None = None) -> None:
    """Funciona en segundo plano; fallo en perfil nunca interrumpe conversación."""
    if not personalidad_habilitada():
        return
    interaccion_id = str(uuid4())
    decision_id = await registrar_decision_personalidad(
        data.get("decision_personalidad"), origen, interaccion_id)
    if observacion_historica is not None:
        await registrar_observacion_historica(observacion_historica, interaccion_id, decision_id)
