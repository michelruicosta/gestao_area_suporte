"""Testa o filtro de dados sensíveis do monitor_erros antes do envio ao Sentry."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from monitor_erros import before_send, _limpar_dict


def _evento(extra: dict) -> dict:
    return {'exception': {'values': [{'stacktrace': {'frames': [{'vars': extra}]}}]}}


def test_campo_remetente_redacted():
    ev = _evento({'remetente': 'joao@empresa.com'})
    resultado = before_send(ev, {})
    vars_ = resultado['exception']['values'][0]['stacktrace']['frames'][0]['vars']
    assert vars_['remetente'] == '[REDACTED]'


def test_campo_assunto_redacted():
    ev = _evento({'assunto': 'Solicitação de suporte urgente'})
    resultado = before_send(ev, {})
    vars_ = resultado['exception']['values'][0]['stacktrace']['frames'][0]['vars']
    assert vars_['assunto'] == '[REDACTED]'


def test_campo_snippet_redacted():
    ev = _evento({'snippet': 'Prezado, segue o comprovante...'})
    resultado = before_send(ev, {})
    vars_ = resultado['exception']['values'][0]['stacktrace']['frames'][0]['vars']
    assert vars_['snippet'] == '[REDACTED]'


def test_email_em_valor_generico_ocultado():
    ev = _evento({'mensagem': 'Erro ao processar cliente@banco.com.br'})
    resultado = before_send(ev, {})
    vars_ = resultado['exception']['values'][0]['stacktrace']['frames'][0]['vars']
    assert 'cliente@banco.com.br' not in vars_['mensagem']
    assert '[EMAIL OCULTO]' in vars_['mensagem']


def test_dados_nao_sensiveis_passam_intactos():
    ev = _evento({'thread_id': 'abc123', 'categoria': 'SUPORTE', 'duracao': 42})
    resultado = before_send(ev, {})
    vars_ = resultado['exception']['values'][0]['stacktrace']['frames'][0]['vars']
    assert vars_['thread_id'] == 'abc123'
    assert vars_['categoria'] == 'SUPORTE'
    assert vars_['duracao'] == 42


def test_iniciar_sem_dsn_nao_levanta_erro(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    from monitor_erros import iniciar
    iniciar()  # não deve levantar exceção


def test_checkin_sem_dsn_nao_levanta_erro(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    from monitor_erros import checkin_inicio, checkin_fim
    checkin_inicio()
    checkin_fim(ok=True)
    checkin_fim(ok=False)


def test_breadcrumb_email_ocultado():
    from monitor_erros import before_breadcrumb
    crumb = {'message': 'Processando thread de cliente@banco.com.br', 'data': {}}
    resultado = before_breadcrumb(crumb, {})
    assert 'cliente@banco.com.br' not in resultado['message']
    assert '[EMAIL OCULTO]' in resultado['message']


def test_breadcrumb_sem_email_passa_intacto():
    from monitor_erros import before_breadcrumb
    crumb = {'message': 'Pipeline iniciado com sucesso', 'data': {}}
    resultado = before_breadcrumb(crumb, {})
    assert resultado['message'] == 'Pipeline iniciado com sucesso'


def test_send_transaction_redacta_sensiveis():
    from monitor_erros import before_send_transaction
    ev = {'request': {'data': {'assunto': 'Urgente cliente', 'thread_id': 'abc'}}}
    resultado = before_send_transaction(ev, {})
    assert resultado['request']['data']['assunto'] == '[REDACTED]'
    assert resultado['request']['data']['thread_id'] == 'abc'
