"""Acceso privado a LUMI mediante una sola contraseña y sesión segura.

No toca el cerebro de LUMI ni la validación del webhook de Telegram.
La variable de Render LUMI_DASHBOARD_PASSWORD sigue siendo la contraseña.
"""

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

COOKIE = "lumi_dashboard_session"
SESSION_DAYS = 7
SESSION_DAYS_REMEMBER = 30
MAX_ATTEMPTS = 10
LOCKOUT_SECONDS = 15 * 60
_failed_attempts = defaultdict(deque)


def _password() -> str:
    value = os.getenv("LUMI_DASHBOARD_PASSWORD", "")
    if not value:
        raise HTTPException(status_code=503, detail="Configura LUMI_DASHBOARD_PASSWORD en Render")
    return value


def _signing_key() -> bytes:
    # Una clave opcional separada permite invalidar sesiones sin cambiar la contraseña.
    secret = os.getenv("LUMI_DASHBOARD_SESSION_SECRET") or _password()
    return hashlib.sha256(("LUMI/dashboard/V8/" + secret).encode("utf-8")).digest()


def crear_sesion(*, recordar: bool = False) -> tuple[str, int]:
    max_age = 86400 * (SESSION_DAYS_REMEMBER if recordar else SESSION_DAYS)
    issued = int(time.time())
    payload = f"{issued}.{issued + max_age}"
    signature = hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}", max_age


def tiene_sesion(request: Request) -> bool:
    token = request.cookies.get(COOKIE, "")
    if len(token) > 256:
        return False
    try:
        issued_text, expiry_text, signature = token.split(".")
        issued, expiry = int(issued_text), int(expiry_text)
        now = int(time.time())
        if issued > now + 60 or expiry < now or expiry - issued > 31 * 86400:
            return False
        payload = f"{issued}.{expiry}"
        expected = hmac.new(_signing_key(), payload.encode("ascii"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, AttributeError):
        return False


def verificar_dashboard(request: Request) -> None:
    if not tiene_sesion(request):
        # Sin WWW-Authenticate: evita la ventana de usuario/contraseña que se
        # reiniciaba en el móvil/tablet al actualizarse el dashboard.
        raise HTTPException(status_code=401, detail="Sesión expirada o sin iniciar")


def validar_origen(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc.lower() != request.headers.get("host", "").lower():
        raise HTTPException(status_code=403, detail="Origen no permitido")


def comprobar_password(request: Request, candidato: str) -> bool:
    # Limitación por IP: evita ataques de fuerza bruta casuales. En un despliegue
    # con múltiples workers se recomienda añadir un limitador compartido.
    ip = request.client.host if request.client else "desconocido"
    attempts = _failed_attempts[ip]
    now = time.monotonic()
    while attempts and now - attempts[0] > LOCKOUT_SECONDS:
        attempts.popleft()
    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera 15 minutos")
    correcto = hmac.compare_digest(candidato.encode("utf-8"), _password().encode("utf-8"))
    if correcto:
        attempts.clear()
    else:
        attempts.append(now)
    return correcto


def cookie_segura(request: Request) -> bool:
    # HTTPS en Render; permite pruebas por HTTP solo en localhost.
    host = request.url.hostname or ""
    return host not in ("localhost", "127.0.0.1", "::1")


def verificar_webhook_telegram(request: Request) -> None:
    secreto = os.getenv("LUMI_TELEGRAM_WEBHOOK_SECRET", "")
    if not secreto:
        raise HTTPException(status_code=503, detail="Falta LUMI_TELEGRAM_WEBHOOK_SECRET")
    recibido = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(recibido, secreto):
        raise HTTPException(status_code=403, detail="Acceso denegado")
