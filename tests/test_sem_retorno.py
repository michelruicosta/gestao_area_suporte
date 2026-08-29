"""
test_sem_retorno.py
Testes para a feature de auto-arquivamento "Sem Retorno":
  - arquivar_threads_inativas: carimba inativa_desde nas threads inativas
  - recalcular_status_todos: reativa threads com nova mensagem após arquivamento
  - salvar_snapshot + buscar_threads_sem_retorno: integração dos contadores
"""
from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
import datetime

import pytest

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import banco_threads as bt


@pytest.fixture()
def banco_tmp(monkeypatch, tmp_path):
    """Redireciona bt.BANCO para um banco temporário limpo."""
    db = str(tmp_path / 'test_gestao.db')
    monkeypatch.setattr(bt, 'BANCO', db)
    bt.criar_banco()
    return db


def _agora_str() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _data_passada(dias: int) -> str:
    d = datetime.datetime.now() - datetime.timedelta(days=dias)
    return d.strftime('%Y-%m-%d %H:%M:%S')


def _inserir_thread(conn, thread_id: str, status: str, data_ultima_msg: str):
    conn.execute("""
        INSERT INTO threads
            (thread_id, assunto, destino, categoria, status_workflow,
             data_primeira_msg, data_ultima_msg, qtd_mensagens, mensagens_json)
        VALUES (?, 'Teste', 'principal', 'DDR_2011', ?, ?, ?, 1, '[]')
    """, (thread_id, status, data_ultima_msg, data_ultima_msg))


# ── arquivar_threads_inativas ─────────────────────────────────────────────────

def test_arquivar_af_stale(banco_tmp):
    """Threads AF sem resposta há mais de dias_af são arquivadas."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-af-stale', 'Aguardando Finaud', _data_passada(35))
    resultado = bt.arquivar_threads_inativas(dias_af=30, dias_ac=60)
    assert resultado['af'] == 1
    assert resultado['ac'] == 0
    with bt._conectar() as conn:
        row = conn.execute('SELECT inativa_desde FROM threads WHERE thread_id=?',
                           ('th-af-stale',)).fetchone()
    assert row['inativa_desde'] is not None


def test_arquivar_af_recente_nao_arquiva(banco_tmp):
    """Thread AF com menos de dias_af não é arquivada."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-af-ok', 'Aguardando Finaud', _data_passada(10))
    resultado = bt.arquivar_threads_inativas(dias_af=30, dias_ac=60)
    assert resultado['af'] == 0


def test_arquivar_ac_stale(banco_tmp):
    """Thread AC sem resposta há mais de dias_ac é arquivada."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-ac-stale', 'Aguardando Cliente', _data_passada(65))
    resultado = bt.arquivar_threads_inativas(dias_af=30, dias_ac=60)
    assert resultado['ac'] == 1


def test_arquivar_ja_arquivada_nao_duplica(banco_tmp):
    """Thread já arquivada não é contada novamente."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-ja-arq', 'Aguardando Finaud', _data_passada(40))
        conn.execute('UPDATE threads SET inativa_desde=? WHERE thread_id=?',
                     (_data_passada(5), 'th-ja-arq'))
    resultado = bt.arquivar_threads_inativas(dias_af=30, dias_ac=60)
    assert resultado['af'] == 0


# ── recalcular_status_todos — reativação ──────────────────────────────────────

def test_reativacao_nova_mensagem(banco_tmp):
    """Thread arquivada com data_ultima_msg posterior a inativa_desde é reativada."""
    arq_em = _data_passada(5)
    nova_msg = _agora_str()
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-reativa', 'Aguardando Finaud', nova_msg)
        conn.execute('UPDATE threads SET inativa_desde=? WHERE thread_id=?',
                     (arq_em, 'th-reativa'))
    bt.recalcular_status_todos()
    with bt._conectar() as conn:
        row = conn.execute('SELECT inativa_desde FROM threads WHERE thread_id=?',
                           ('th-reativa',)).fetchone()
    assert row['inativa_desde'] is None


def test_sem_nova_mensagem_permanece_arquivada(banco_tmp):
    """Thread arquivada sem nova mensagem mantém inativa_desde."""
    arq_em = _agora_str()
    msg_antes = _data_passada(40)
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-sem-retorno', 'Aguardando Finaud', msg_antes)
        conn.execute('UPDATE threads SET inativa_desde=? WHERE thread_id=?',
                     (arq_em, 'th-sem-retorno'))
    bt.recalcular_status_todos()
    with bt._conectar() as conn:
        row = conn.execute('SELECT inativa_desde FROM threads WHERE thread_id=?',
                           ('th-sem-retorno',)).fetchone()
    assert row['inativa_desde'] is not None


# ── buscar_threads_sem_retorno ────────────────────────────────────────────────

def test_buscar_sem_retorno_retorna_so_arquivadas(banco_tmp):
    """buscar_threads_sem_retorno retorna apenas threads com inativa_desde preenchido."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-ativa', 'Aguardando Finaud', _data_passada(5))
        _inserir_thread(conn, 'th-arq', 'Aguardando Cliente', _data_passada(70))
        conn.execute('UPDATE threads SET inativa_desde=? WHERE thread_id=?',
                     (_agora_str(), 'th-arq'))
    resultado = bt.buscar_threads_sem_retorno()
    ids = [r['thread_id'] for r in resultado]
    assert 'th-arq' in ids
    assert 'th-ativa' not in ids


# ── salvar_snapshot — integridade das contagens ───────────────────────────────

def test_salvar_snapshot_exclui_arquivadas_das_categorias(banco_tmp):
    """salvar_snapshot não conta threads arquivadas na categoria original."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-normal', 'Aguardando Finaud', _data_passada(2))
        _inserir_thread(conn, 'th-arq2', 'Aguardando Cliente', _data_passada(70))
        conn.execute('UPDATE threads SET inativa_desde=? WHERE thread_id=?',
                     (_agora_str(), 'th-arq2'))
    bt.salvar_snapshot()
    with bt._conectar() as conn:
        rows = conn.execute('SELECT categoria, af, ac FROM snapshots').fetchall()
    por_cat = {r['categoria']: r for r in rows}
    ddr = por_cat.get('DDR_2011')
    assert ddr is not None
    assert ddr['af'] == 1
    assert ddr['ac'] == 0


def test_salvar_snapshot_cria_linha_sem_retorno(banco_tmp):
    """salvar_snapshot cria uma linha SEM RETORNO quando há threads arquivadas."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-sr', 'Aguardando Finaud', _data_passada(40))
        conn.execute('UPDATE threads SET inativa_desde=? WHERE thread_id=?',
                     (_agora_str(), 'th-sr'))
    bt.salvar_snapshot()
    with bt._conectar() as conn:
        row = conn.execute("SELECT af, ac FROM snapshots WHERE categoria='SEM RETORNO'").fetchone()
    assert row is not None
    assert row['af'] == 1
    assert row['ac'] == 0


def test_salvar_snapshot_sem_arquivadas_nao_cria_linha_sr(banco_tmp):
    """salvar_snapshot não cria linha SEM RETORNO se não há threads arquivadas."""
    with bt._conectar() as conn:
        _inserir_thread(conn, 'th-normal2', 'Aguardando Finaud', _data_passada(2))
    bt.salvar_snapshot()
    with bt._conectar() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE categoria='SEM RETORNO'").fetchone()
    assert row is None
