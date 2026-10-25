"""Acceso privado a Dashboard/Telegram para el backend de LUMI Eterna.

No importa ni modifica la memoria, Gemini, Supabase o la lógica de Lumi.
"""

import os
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials


_basic = HTTPBasic(auto_error=False)


def verificar_dashboard(
    credenciales: HTTPBasicCredentials | None = Depends(_basic),
) -> None:
    usuario = os.getenv("LUMI_DASHBOARD_USER", "")
    password = os.getenv("LUMI_DASHBOARD_PASSWORD", "")
    if not usuario or not password:
        raise HTTPException(status_code=503, detail="Dashboard sin configurar")

    correcto = bool(credenciales) and (
        secrets.compare_digest(credenciales.username.encode(), usuario.encode())
        & secrets.compare_digest(credenciales.password.encode(), password.encode())
    )
    if not correcto:
        raise HTTPException(
            status_code=401,
            detail="Acceso privado",
            headers={"WWW-Authenticate": 'Basic realm="Lumi"'},
        )


def verificar_webhook_telegram(request: Request) -> None:
    secreto = os.getenv("LUMI_TELEGRAM_WEBHOOK_SECRET", "")
    if not secreto:
        raise HTTPException(status_code=503, detail="Webhook sin configurar")
    recibido = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secrets.compare_digest(recibido, secreto):
        raise HTTPException(status_code=403, detail="Webhook no autorizado")
