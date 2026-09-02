"""Testes para coletor_enviados_colaboradores — funções de filtro de participantes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from coletor_enviados_colaboradores import (
    _normalizar,
    _extrair_email,
    _eh_externo,
    _externos_hdrs,
    _externos_thread,
    _ja_existe,
)


# ── _normalizar ───────────────────────────────────────────────────────────────

def test_normalizar_remove_re():
    assert _normalizar('Re: Autorização de câmbio') == 'autorização de câmbio'

def test_normalizar_remove_res():
    assert _normalizar('RES: Pedido de extrato') == 'pedido de extrato'

def test_normalizar_remove_fwd():
    # FWD: é removido, depois "Encaminhado:" também (está na regex _RE_PREFIXO)
    assert _normalizar('FWD: Encaminhado: mensagem') == 'mensagem'

def test_normalizar_iterativo():
    assert _normalizar('Re: Re: Assunto final') == 'assunto final'

def test_normalizar_sem_prefixo():
    assert _normalizar('Solicitação BCB 757') == 'solicitação bcb 757'

def test_normalizar_vazio():
    assert _normalizar('') == ''


# ── _extrair_email ────────────────────────────────────────────────────────────

def test_extrair_email_formato_abk():
    assert _extrair_email('Nome Sobrenome <fulano@exemplo.com>') == 'fulano@exemplo.com'

def test_extrair_email_formato_simples():
    assert _extrair_email('fulano@exemplo.com') == 'fulano@exemplo.com'

def test_extrair_email_nenhum():
    assert _extrair_email('sem email aqui') is None

def test_extrair_email_maiusculas_vira_lower():
    assert _extrair_email('Nome <FULANO@Exemplo.COM>') == 'fulano@exemplo.com'


# ── _eh_externo ───────────────────────────────────────────────────────────────

def test_eh_externo_dominio_externo():
    assert _eh_externo('cliente@empresa.com.br') is True

def test_eh_externo_finaud_nao():
    assert _eh_externo('andrea@finaud.com.br') is False

def test_eh_externo_finaudtec_nao():
    assert _eh_externo('suporte@finaudtec.com.br') is False


# ── _externos_hdrs ────────────────────────────────────────────────────────────

def test_externos_hdrs_extrai_from_e_to():
    hdrs = {
        'From': 'Andrea Inacio <andrea.inacio@finaud.com.br>',
        'To': 'Cliente ABC <cliente@abc.com.br>',
        'Cc': '',
    }
    result = _externos_hdrs(hdrs)
    assert 'cliente@abc.com.br' in result
    assert 'andrea.inacio@finaud.com.br' not in result

def test_externos_hdrs_ignora_finaud():
    hdrs = {
        'From': 'sarah.sa@finaud.com.br',
        'To': 'outra@finaud.com.br',
    }
    assert _externos_hdrs(hdrs) == set()

def test_externos_hdrs_multiplos_destinatarios():
    hdrs = {
        'From': 'andrea.inacio@finaud.com.br',
        'To': 'a@empresa.com, b@outra.org',
    }
    result = _externos_hdrs(hdrs)
    assert 'a@empresa.com' in result
    assert 'b@outra.org' in result


# ── _externos_thread ─────────────────────────────────────────────────────────

def test_externos_thread_remetente_principal():
    thread = {
        'remetente_principal': 'Cliente <cliente@empresa.com>',
        'mensagens': [],
    }
    result = _externos_thread(thread)
    assert 'cliente@empresa.com' in result

def test_externos_thread_ignora_finaud():
    thread = {
        'remetente_principal': 'suporte@finaud.com.br',
        'mensagens': [],
    }
    assert _externos_thread(thread) == set()

def test_externos_thread_varredura_mensagens():
    thread = {
        'remetente_principal': 'suporte@finaud.com.br',
        'mensagens': [
            {'remetente': 'cliente@empresa.com', 'destinatarios': ''},
            {'remetente': 'suporte@finaud.com.br', 'destinatarios': 'cliente@empresa.com'},
        ],
    }
    result = _externos_thread(thread)
    assert 'cliente@empresa.com' in result


# ── Integração: filtro de participantes ──────────────────────────────────────

def test_filtro_participante_match_correto():
    """Email da Andrea para cliente que já está na thread → deve bater."""
    hdrs = {
        'From': 'Andrea Inacio <andrea.inacio@finaud.com.br>',
        'To': 'cliente@empresa.com',
    }
    thread = {
        'remetente_principal': 'cliente@empresa.com',
        'mensagens': [],
    }
    externos_msg = _externos_hdrs(hdrs)
    externos_thr = _externos_thread(thread)
    assert bool(externos_msg & externos_thr)  # deve haver overlap

def test_filtro_participante_falso_positivo_bloqueado():
    """Email broadcast sem participante em comum com a thread → não deve bater."""
    hdrs = {
        'From': 'broadcast@outraempresa.com',
        'To': 'andrea.inacio@finaud.com.br',
    }
    thread = {
        'remetente_principal': 'cliente@empresa.com',  # cliente diferente
        'mensagens': [],
    }
    externos_msg = _externos_hdrs(hdrs)
    externos_thr = _externos_thread(thread)
    assert not bool(externos_msg & externos_thr)  # sem overlap


# ── _ja_existe ────────────────────────────────────────────────────────────────

def test_ja_existe_mesmo_par():
    msgs = [{'data': '01/09/2026 10:00', 'remetente': 'a@b.com'}]
    nova  = {'data': '01/09/2026 10:00', 'remetente': 'a@b.com'}
    assert _ja_existe(msgs, nova) is True

def test_ja_existe_data_diferente():
    msgs = [{'data': '01/09/2026 10:00', 'remetente': 'a@b.com'}]
    nova  = {'data': '02/09/2026 10:00', 'remetente': 'a@b.com'}
    assert _ja_existe(msgs, nova) is False

def test_ja_existe_lista_vazia():
    assert _ja_existe([], {'data': '01/09/2026', 'remetente': 'x@y.com'}) is False
