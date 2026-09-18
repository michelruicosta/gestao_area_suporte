"""
test_log_acesso.py
Testes para a trilha de auditoria: tabela log_acesso, registrar_acesso e ler_log_acesso.
"""
from __future__ import annotations

import os
import sys

import pytest

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import banco_threads as bt


def _banco(monkeypatch, tmp_path):
    banco_tmp = str(tmp_path / 'audit_test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()
    return banco_tmp


def test_tabela_criada(monkeypatch, tmp_path):
    """criar_banco deve criar a tabela log_acesso."""
    import sqlite3
    banco_tmp = _banco(monkeypatch, tmp_path)
    with sqlite3.connect(banco_tmp) as conn:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert 'log_acesso' in tabelas


def test_registrar_login_app(monkeypatch, tmp_path):
    """registrar_acesso grava login com origem 'app'."""
    _banco(monkeypatch, tmp_path)
    bt.registrar_acesso('michel@finaud.com.br', 'login', origem='app', ip='127.0.0.1')
    logs = bt.ler_log_acesso()
    assert len(logs) == 1
    assert logs[0]['email'] == 'michel@finaud.com.br'
    assert logs[0]['tipo'] == 'login'
    assert logs[0]['origem'] == 'app'
    assert logs[0]['ip'] == '127.0.0.1'


def test_registrar_login_portal(monkeypatch, tmp_path):
    """registrar_acesso grava login com origem 'portal'."""
    _banco(monkeypatch, tmp_path)
    bt.registrar_acesso('michel@finaud.com.br', 'login', origem='portal', ip='10.0.0.1')
    logs = bt.ler_log_acesso()
    assert logs[0]['origem'] == 'portal'


def test_registrar_acesso_tela(monkeypatch, tmp_path):
    """registrar_acesso grava acesso a uma tela."""
    _banco(monkeypatch, tmp_path)
    bt.registrar_acesso(
        'michel@finaud.com.br', 'acesso',
        rota='/', tela='Classificação e Status', ip='127.0.0.1',
    )
    logs = bt.ler_log_acesso()
    assert logs[0]['tipo'] == 'acesso'
    assert logs[0]['rota'] == '/'
    assert logs[0]['tela'] == 'Classificação e Status'


def test_registrar_heartbeat(monkeypatch, tmp_path):
    """registrar_acesso grava heartbeat."""
    _banco(monkeypatch, tmp_path)
    bt.registrar_acesso('michel@finaud.com.br', 'heartbeat', rota='/', tela='Classificação e Status')
    logs = bt.ler_log_acesso()
    assert logs[0]['tipo'] == 'heartbeat'


def test_registrar_logout(monkeypatch, tmp_path):
    """registrar_acesso grava logout."""
    _banco(monkeypatch, tmp_path)
    bt.registrar_acesso('michel@finaud.com.br', 'logout', ip='127.0.0.1')
    logs = bt.ler_log_acesso()
    assert logs[0]['tipo'] == 'logout'


def test_ordem_mais_recente_primeiro(monkeypatch, tmp_path):
    """ler_log_acesso retorna o mais recente primeiro."""
    _banco(monkeypatch, tmp_path)
    bt.registrar_acesso('a@a.com', 'login', origem='app')
    bt.registrar_acesso('a@a.com', 'acesso', tela='Custos')
    bt.registrar_acesso('a@a.com', 'logout')
    logs = bt.ler_log_acesso()
    assert logs[0]['tipo'] == 'logout'
    assert logs[-1]['tipo'] == 'login'


def test_limite_respeitado(monkeypatch, tmp_path):
    """ler_log_acesso respeita o parâmetro limite."""
    _banco(monkeypatch, tmp_path)
    for i in range(10):
        bt.registrar_acesso('a@a.com', 'heartbeat', tela='Principal')
    logs = bt.ler_log_acesso(limite=5)
    assert len(logs) == 5


def test_falha_silenciosa_sem_banco(monkeypatch, tmp_path):
    """registrar_acesso nunca levanta exceção, mesmo com banco inexistente."""
    monkeypatch.setattr(bt, 'BANCO', str(tmp_path / 'nao_existe' / 'db.sqlite'))
    bt.registrar_acesso('x@x.com', 'login', origem='app')
