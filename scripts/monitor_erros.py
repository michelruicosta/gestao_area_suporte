"""
monitor_erros.py
O que faz: inicializa o monitoramento de erros via Sentry, filtra dados
           sensíveis antes do envio e registra o batimento do relógio de coleta.
Uso: monitor_erros.iniciar() no início de cada script.
     monitor_erros.checkin_inicio() / checkin_fim() ao redor do job agendado.
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


def before_send_transaction(event: dict, hint: dict) -> dict:
    return _limpar_dict(event)


def before_breadcrumb(crumb: dict, hint: dict) -> dict:
    """Filtra mensagens de log antes de enviarem ao Sentry."""
    msg = crumb.get('message', '')
    if isinstance(msg, str):
        if _RE_EMAIL.search(msg):
            crumb['message'] = _RE_EMAIL.sub('[EMAIL OCULTO]', msg)
    if isinstance(crumb.get('data'), dict):
        crumb['data'] = _limpar_dict(crumb['data'])
    return crumb


def iniciar(modo: str = 'pipeline') -> None:
    """
    modo='flask'    — inclui integração Flask (captura erros de rotas HTTP)
    modo='pipeline' — captura só exceções Python (scripts sem servidor web)
    Não faz nada se SENTRY_DSN não estiver definido no ambiente.
    """
    dsn = os.getenv('SENTRY_DSN', '').strip()
    if not dsn:
        return

    import logging as _logging
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    integracoes: list = [
        LoggingIntegration(
            level=_logging.WARNING,
            event_level=_logging.ERROR,
        ),
    ]
    if modo == 'flask':
        from sentry_sdk.integrations.flask import FlaskIntegration
        integracoes.append(FlaskIntegration())

    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=False,
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        before_breadcrumb=before_breadcrumb,
        traces_sample_rate=0.2,
        profiles_sample_rate=1.0,
        integrations=integracoes,
    )


_SLUG_RELOGIO = 'relogio-coleta'
_MONITOR_CONFIG = {
    'schedule': {'type': 'interval', 'value': 60, 'unit': 'minute'},
    'checkin_margin': 5,
    'max_runtime': 20,
}
_checkin_id_atual: str | None = None


def checkin_inicio() -> None:
    """Registra no Sentry que o relógio de coleta começou a rodar."""
    global _checkin_id_atual
    if not os.getenv('SENTRY_DSN', '').strip():
        return
    try:
        import sentry_sdk
        from sentry_sdk.tracing import MonitorStatus
        _checkin_id_atual = sentry_sdk.capture_check_in(
            monitor_slug=_SLUG_RELOGIO,
            status=MonitorStatus.IN_PROGRESS,
            monitor_config=_MONITOR_CONFIG,
        )
    except Exception:
        pass


def checkin_fim(ok: bool = True) -> None:
    """Registra no Sentry que o relógio terminou (ok=True) ou falhou (ok=False)."""
    global _checkin_id_atual
    if not os.getenv('SENTRY_DSN', '').strip():
        return
    try:
        import sentry_sdk
        from sentry_sdk.tracing import MonitorStatus
        status = MonitorStatus.OK if ok else MonitorStatus.ERROR
        sentry_sdk.capture_check_in(
            monitor_slug=_SLUG_RELOGIO,
            status=status,
            check_in_id=_checkin_id_atual,
            monitor_config=_MONITOR_CONFIG,
        )
    except Exception:
        pass
    finally:
        _checkin_id_atual = None
