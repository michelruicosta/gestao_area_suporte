"""Testes para coletor_enviados_colaboradores — matching por Message-ID e deduplicação."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from coletor_enviados_colaboradores import (
    _construir_indice_mid,
    _thread_por_reply,
    _ja_existe,
)


# ── _construir_indice_mid ─────────────────────────────────────────────────────

def test_construir_indice_basico():
    threads = {
        'tid_abc': {
            'mensagens': [
                {'message_id': '<msg1@mail.com>'},
                {'message_id': '<msg2@mail.com>'},
            ]
        }
    }
    indice = _construir_indice_mid(threads)
    assert indice['<msg1@mail.com>'] == 'tid_abc'
    assert indice['<msg2@mail.com>'] == 'tid_abc'

def test_construir_indice_ignora_sem_mid():
    threads = {
        'tid_xyz': {
            'mensagens': [
                {'message_id': ''},
                {'remetente': 'a@b.com'},  # sem chave message_id
            ]
        }
    }
    indice = _construir_indice_mid(threads)
    assert indice == {}

def test_construir_indice_multiplas_threads():
    threads = {
        'tid_1': {'mensagens': [{'message_id': '<a@x.com>'}]},
        'tid_2': {'mensagens': [{'message_id': '<b@x.com>'}]},
    }
    indice = _construir_indice_mid(threads)
    assert indice['<a@x.com>'] == 'tid_1'
    assert indice['<b@x.com>'] == 'tid_2'

def test_construir_indice_thread_sem_mensagens():
    threads = {'tid_vazio': {'mensagens': []}}
    assert _construir_indice_mid(threads) == {}

def test_construir_indice_thread_sem_chave_mensagens():
    threads = {'tid_sem': {}}
    assert _construir_indice_mid(threads) == {}


# ── _thread_por_reply ─────────────────────────────────────────────────────────

def test_thread_por_reply_in_reply_to_encontrado():
    indice = {'<original@mail.com>': 'tid_abc'}
    tid = _thread_por_reply('<original@mail.com>', '', indice)
    assert tid == 'tid_abc'

def test_thread_por_reply_references_quando_in_reply_to_ausente():
    indice = {'<antigo@mail.com>': 'tid_xyz'}
    tid = _thread_por_reply('', '<antigo@mail.com>', indice)
    assert tid == 'tid_xyz'

def test_thread_por_reply_references_fallback_quando_in_reply_to_nao_encontrado():
    """In-Reply-To não está no banco; References tem um ID conhecido."""
    indice = {'<antigo@mail.com>': 'tid_xyz'}
    tid = _thread_por_reply('<desconhecido@mail.com>', '<antigo@mail.com>', indice)
    assert tid == 'tid_xyz'

def test_thread_por_reply_references_mais_recente_prevalece():
    """References tem vários IDs; o mais à direita (mais recente) é checado primeiro."""
    indice = {
        '<antigo@mail.com>'  : 'tid_1',
        '<recente@mail.com>' : 'tid_2',
    }
    tid = _thread_por_reply('', '<antigo@mail.com> <recente@mail.com>', indice)
    assert tid == 'tid_2'

def test_thread_por_reply_nenhum_encontrado():
    indice = {'<outra@mail.com>': 'tid_abc'}
    tid = _thread_por_reply('<desconhecido@mail.com>', '', indice)
    assert tid is None

def test_thread_por_reply_sem_cabecalhos():
    indice = {'<a@b.com>': 'tid_abc'}
    tid = _thread_por_reply('', '', indice)
    assert tid is None

def test_thread_por_reply_indice_vazio():
    tid = _thread_por_reply('<msg@mail.com>', '', {})
    assert tid is None

def test_thread_por_reply_in_reply_to_com_espacos():
    """In-Reply-To com espaços em volta deve ser tratado (strip)."""
    indice = {'<msg@mail.com>': 'tid_abc'}
    tid = _thread_por_reply('  <msg@mail.com>  ', '', indice)
    assert tid == 'tid_abc'


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

def test_ja_existe_message_id_detecta_remetente_diferente():
    """Mesmo Message-ID com remetentes distintos (via suporte@ vs. direto) → duplicata."""
    mid = '<CABxyz123@mail.gmail.com>'
    msgs = [{'data': '31/08/2026 20:06',
             'remetente': "'Jacilaine' via Suporte <suporte@finaud.com.br>",
             'message_id': mid}]
    nova  = {'data': '31/08/2026 20:06',
             'remetente': 'Jacilaine das Neves Lima <jnlima@planner.com.br>',
             'message_id': mid}
    assert _ja_existe(msgs, nova) is True

def test_ja_existe_message_id_diferente_nao_duplicata():
    """Message-IDs diferentes com mesma data → não é duplicata."""
    msgs = [{'data': '31/08/2026 20:06', 'remetente': 'a@b.com',
             'message_id': '<id1@mail.com>'}]
    nova  = {'data': '31/08/2026 20:06', 'remetente': 'a@b.com',
             'message_id': '<id2@mail.com>'}
    assert _ja_existe(msgs, nova) is False

def test_ja_existe_sem_message_id_usa_fallback():
    """Sem message_id em nenhum dos dois → fallback por (data, remetente)."""
    msgs = [{'data': '01/09/2026 10:00', 'remetente': 'a@b.com', 'message_id': ''}]
    nova  = {'data': '01/09/2026 10:00', 'remetente': 'a@b.com', 'message_id': ''}
    assert _ja_existe(msgs, nova) is True

def test_ja_existe_nova_sem_message_id_nao_falso_positivo():
    """Nova mensagem sem message_id e remetente diferente → não é duplicata."""
    msgs = [{'data': '01/09/2026 10:00', 'remetente': 'a@b.com',
             'message_id': '<id1@mail.com>'}]
    nova  = {'data': '01/09/2026 10:00', 'remetente': 'outro@b.com', 'message_id': ''}
    assert _ja_existe(msgs, nova) is False
