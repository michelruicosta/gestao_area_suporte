"""
monitor_erros.py
O que faz: inicializa o monitoramento de erros via Sentry e filtra dados
           sensíveis (corpo de e-mail, remetente, assunto) antes do envio.
Uso: importar e chamar monitor_erros.iniciar() no início de cada script.
"""
from __future__ import annotations

import os
import re

# Nomes de campos que contêm dados pessoais — valor substituído por [REDACTED]
_CAMPOS_SENSIVEIS = frozenset({
    'body', 'snippet', 'payload', 'raw',
    'remetente', 'destinatario', 'assunto',
    'from', 'to', 'subject', 'message',
    'texto', 'conteudo', 'content', 'email_body',
})

_RE_EMAIL = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')


def _limpar_valor(chave: str, valor: object) -> object:
    if not isinstance(valor, str):
        return valor
    if chave.lower() in _CAMPOS_SENSIVEIS:
        return '[REDACTED]'
    if _RE_EMAIL.search(valor):
        return _RE_EMAIL.sub('[EMAIL OCULTO]', valor)
    return valor


def _limpar_dict(dados: dict) -> dict:
    resultado: dict = {}
    for chave, valor in dados.items():
        if isinstance(valor, dict):
            resultado[chave] = _limpar_dict(valor)
        elif isinstance(valor, list):
            resultado[chave] = [
                _limpar_dict(item) if isinstance(item, dict)
                else _limpar_valor(str(chave), item)
                for item in valor
            ]
        else:
            resultado[chave] = _limpar_valor(chave, valor)
    return resultado


def before_send(event: dict, hint: dict) -> dict:
    return _limpar_dict(event)


def iniciar(modo: str = 'pipeline') -> None:
    """
    modo='flask'    — inclui integração Flask (captura erros de rotas HTTP)
    modo='pipeline' — captura só exceções Python (scripts sem servidor web)
    Não faz nada se SENTRY_DSN não estiver definido no ambiente.
    """
    dsn = os.getenv('SENTRY_DSN', '').strip()
    if not dsn:
        return

    import sentry_sdk

    integracoes: list = []
    if modo == 'flask':
        from sentry_sdk.integrations.flask import FlaskIntegration
        integracoes.append(FlaskIntegration())

    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=False,
        before_send=before_send,
        integrations=integracoes,
    )
