# -*- coding: utf-8 -*-
"""
Testes para a regra F->F nuancada nos supervisores (Passo 5 do protocolo).

Cobre:
  - F->F sem sinal conclusivo -> AGUARDANDO (todos os supervisores)
  - F->F com 'aceito no STA' -> CONCLUIDO (DLO como representante)
  - DDR/4111: F->F antes ignorado (PENDENTE) agora vira AGUARDANDO
  - DDR/4111: F->F conclusivo vira CONCLUIDO
  - Regressao: C->F normal continua como AGUARDANDO (nao afetado)
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import triagem.dlo as dlo
import triagem.ddr4111 as ddr4111


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------
def _msg_ff(corpo: str = "encaminhamento interno", ts: int = 1750800000) -> dict:
    return {
        "contato_origem": {"lado": "FINAUD", "email": "ana@finaud.com.br"},
        "contato_destino": {"lado": "FINAUD", "email": "ana2@finaud.com.br"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": "Assunto",
        "data_email": "2026-06-24",
        "timestamp_epoch": ts,
    }


def _msg_cf(corpo: str = "por favor verificar") -> dict:
    return {
        "contato_origem": {"lado": "CLIENTE", "email": "cli@empresa.com.br"},
        "contato_destino": {"lado": "FINAUD", "email": "ana@finaud.com.br"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": "Assunto",
        "data_email": "2026-06-24",
        "timestamp_epoch": 1750800000,
    }


def _ev(tid: str, cadoc: str) -> dict:
    return {
        "threadId": tid,
        "cadoc": cadoc,
        "timestamp_epoch": 1750800000,
        "relatorio_interno_risk_driver": False,
        "titulo": f"Thread {tid}",
        "cliente": "Empresa Teste",
        "responsavel": "Ana",
        "lista_prazos": [],
        "texto_imagens": "",
    }


def _dados(tid: str, cadoc: str, *msgs) -> dict:
    return {
        "threads": [{"threadId": tid, "cadoc": cadoc, "mensagens": list(msgs), "assunto": f"T-{tid}"}],
        "eventos": [_ev(tid, cadoc)],
    }


DIA = date(2026, 6, 24)


# ---------------------------------------------------------------------------
# DLO: F->F sem sinal conclusivo -> AGUARDANDO
# ---------------------------------------------------------------------------
def test_dlo_ff_sem_sinal_fica_aguardando():
    tid = "T-DLO-01"
    dados = _dados(tid, "DLO_2061",
        _msg_cf("preciso verificar"),
        _msg_ff("encaminhamento interno para ana"),
    )
    co, ag, _ = dlo.triar(dados, dia_ref=DIA)
    assert any(r["threadId"] == tid for r in ag), "F->F sem sinal deve ser AGUARDANDO"
    assert not any(r["threadId"] == tid for r in co)


# ---------------------------------------------------------------------------
# DLO: F->F com 'aceito no STA' -> CONCLUIDO
# ---------------------------------------------------------------------------
def test_dlo_ff_aceito_sta_conclui():
    tid = "T-DLO-02"
    dados = _dados(tid, "DLO_2061",
        _msg_ff("estou verificando", ts=1750700000),              # penultima: F->F (ts menor)
        _msg_ff("arquivo aceito no STA com sucesso", ts=1750800000),  # ultima: F->F conclusivo (ts maior)
    )
    co, ag, _ = dlo.triar(dados, dia_ref=DIA)
    assert any(r["threadId"] == tid for r in co), "F->F conclusivo deve ser CONCLUIDO"
    assert not any(r["threadId"] == tid for r in ag)


# ---------------------------------------------------------------------------
# DDR/4111: F->F sem sinal -> AGUARDANDO (antes ficava PENDENTE/invisivel)
# ---------------------------------------------------------------------------
def test_ddr_ff_sem_sinal_fica_aguardando():
    tid = "T-DDR-01"
    dados = _dados(tid, "DDR_2011",
        _msg_cf("aguardo orientacao"),
        _msg_ff("encaminhamento interno"),
    )
    co, ag, _ = ddr4111.triar(dados, dia_ref=DIA)
    assert any(r["threadId"] == tid for r in ag), (
        "DDR/4111 F->F deve ser AGUARDANDO (antes ficava PENDENTE/invisivel)"
    )
    assert not any(r["threadId"] == tid for r in co)


# ---------------------------------------------------------------------------
# DDR/4111: F->F conclusivo -> CONCLUIDO
# ---------------------------------------------------------------------------
def test_ddr_ff_conclusivo_conclui():
    tid = "T-DDR-02"
    dados = _dados(tid, "DDR_2011",
        _msg_ff("verificando o arquivo", ts=1750700000),    # penultima: F->F (ts menor)
        _msg_ff("arquivo transmitido ao BACEN", ts=1750800000),  # ultima: F->F conclusivo (ts maior)
    )
    co, ag, _ = ddr4111.triar(dados, dia_ref=DIA)
    assert any(r["threadId"] == tid for r in co), "DDR F->F conclusivo deve ser CONCLUIDO"
    assert not any(r["threadId"] == tid for r in ag)


# ---------------------------------------------------------------------------
# Regressao: C->F normal continua AGUARDANDO (nao afetado pela mudanca)
# ---------------------------------------------------------------------------
def test_dlo_cf_normal_continua_aguardando():
    tid = "T-DLO-03"
    dados = _dados(tid, "DLO_2061",
        _msg_cf("por favor analisar"),
    )
    co, ag, _ = dlo.triar(dados, dia_ref=DIA)
    assert any(r["threadId"] == tid for r in ag), "C->F normal deve continuar AGUARDANDO"
    assert not any(r["threadId"] == tid for r in co)
