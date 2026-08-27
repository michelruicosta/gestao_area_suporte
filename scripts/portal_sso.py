"""SSO — confia no login do portal Finaud (cookie compartilhado)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PORTAL_AUTH_URL = os.environ.get("PORTAL_AUTH_URL", "http://127.0.0.1:8002").rstrip("/")
PORTAL_AUTH_LEGACY_URL = os.environ.get("PORTAL_AUTH_LEGACY_URL", "").rstrip("/")
COOKIE_AUDITORIA = os.environ.get("AUDITORIA_PORTAL_COOKIE_NAME", "auditoria_sessao")
COOKIE_PORTAL = os.environ.get("PORTAL_COOKIE_NAME", "finaud_portal_sessao")
TIMEOUT_SEG = float(os.environ.get("PORTAL_AUTH_TIMEOUT_SEG", "5"))


@dataclass(frozen=True)
class UsuarioPortal:
    email: str
    nome: str
    perfil_codigo: str


def consultar_usuario_portal(
    cookie_valor: str,
    *,
    cookie_name: str,
    auth_base_url: str | None = None,
) -> UsuarioPortal | None:
    base = (auth_base_url or PORTAL_AUTH_URL or "").rstrip("/")
    if not base or not cookie_valor:
        return None
    url = f"{base}/auth/me"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cookie": f"{cookie_name}={cookie_valor}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
        OSError,
    ) as exc:
        logger.info("SSO portal indisponivel ou sessao invalida (%s): %s", cookie_name, exc)
        return None

    email = str(data.get("email") or "").strip()
    if not email:
        return None
    return UsuarioPortal(
        email=email,
        nome=str(data.get("nome") or email),
        perfil_codigo=str(data.get("perfil_codigo") or "operador"),
    )


def usuario_pelos_cookies(cookies: dict[str, str]) -> UsuarioPortal | None:
    """Ordem Finaud: cookie Auditoria → cookie portal-auth."""
    tentativas = (
        (COOKIE_AUDITORIA, PORTAL_AUTH_URL),
        (COOKIE_PORTAL, PORTAL_AUTH_LEGACY_URL or PORTAL_AUTH_URL),
    )
    for nome, base in tentativas:
        valor = (cookies.get(nome) or "").strip()
        if not valor or not base:
            continue
        usuario = consultar_usuario_portal(valor, cookie_name=nome, auth_base_url=base)
        if usuario is not None:
            return usuario
    return None
