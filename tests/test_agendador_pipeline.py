"""Relógio da coleta fica à parte da tela (melhoria 3)."""
from __future__ import annotations

import os
import sys

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import executar_pipeline as pipe  # noqa: E402
import servidor_telas as st  # noqa: E402


def test_pytest_nao_liga_o_relogio_na_tela():
    """Abrir os testes não pode disparar coleta de e-mail."""
    assert st._deve_ligar_agendador_na_tela() is False
    assert st._scheduler.running is False


def test_flag_externo_desliga_relogio_da_tela(monkeypatch):
    monkeypatch.setenv('GESTAO_AGENDADOR_EXTERNO', '1')
    assert st._agendador_externo_ligado() is True
    monkeypatch.delenv('GESTAO_AGENDADOR_EXTERNO', raising=False)
    assert st._agendador_externo_ligado() is False


def test_pipeline_tem_modo_agendar():
    caminho = os.path.join(RAIZ, 'scripts', 'executar_pipeline.py')
    fonte = open(caminho, encoding='utf-8').read()
    assert '--agendar' in fonte
    assert 'def ligar_agendador' in fonte
    assert 'def rodar_coleta_ciclo' in fonte
    assert 'def ficar_agendando' in fonte


def test_reagendar_nao_mexo_se_relogio_for_externo(monkeypatch):
    monkeypatch.setattr(st, '_deve_ligar_agendador_na_tela', lambda: False)
    st._reagendar_coleta(15)
    assert st._scheduler.get_job('coleta_automatica') is None


def test_ler_config_pipeline_nao_quebra(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"intervalo_coleta_min": 45}', encoding='utf-8')
    monkeypatch.setattr(pipe, '_CONFIG_PATH', str(cfg))
    assert pipe.ler_config()['intervalo_coleta_min'] == 45
