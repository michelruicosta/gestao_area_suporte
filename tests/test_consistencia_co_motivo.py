# -*- coding: utf-8 -*-
"""
Testes de consistência entre regra e motivo nos registros de CONCLUÍDO.

Garante que threads com motivo F→F "aguarda tratamento" nunca apareçam
em CO — combinação impossível: F→F interno aguardando não pode ser concluído.

Origem: investigação da thread Atual Câmbio em 30/06/2026, que revelou 7 threads
com esse padrão incorretamente em CO (corrigidas no mesmo dia).
"""
import json
import os
import pytest

# ── Padrões de motivo que indicam AGUARDANDO (nunca devem aparecer em CO) ──────

_MOTIVOS_FF_AGUARDANDO = [
    "última mensagem interna finaud→finaud — aguarda tratamento",
]


def _tem_motivo_ff_aguardando(registro: dict) -> bool:
    """Retorna True se o registro tem motivo F→F de aguardando — inválido em CO."""
    motivo = (registro.get("motivo") or "").lower()
    return any(padrao in motivo for padrao in _MOTIVOS_FF_AGUARDANDO)


# ── Testes unitários (dados mockados, sem arquivo) ──────────────────────────────

def test_detecta_motivo_ff_aguardando():
    """Thread com motivo F→F aguarda tratamento é detectada como inválida em CO."""
    registro = {
        "threadId": "GMTHRID_FAKE001",
        "empresa": "Empresa Teste",
        "cadoc": "DDR_2011",
        "regra": "R1",
        "motivo": "Triagem automática: última mensagem interna Finaud→Finaud — aguarda tratamento (DDR4111).",
    }
    assert _tem_motivo_ff_aguardando(registro)


def test_nao_detecta_motivo_de_entrega():
    """Thread com motivo de entrega ao cliente não é flagrada."""
    registro = {
        "threadId": "GMTHRID_FAKE002",
        "empresa": "Terra",
        "cadoc": "DDR_2011",
        "regra": "R1",
        "motivo": "Triagem automática: Finaud entregou relatório ao cliente — Pedro Silva → Terra (DDR4111).",
    }
    assert not _tem_motivo_ff_aguardando(registro)


def test_nao_detecta_motivo_r2():
    """Thread concluída via R2 (transmissão ao cliente) não é flagrada."""
    registro = {
        "threadId": "GMTHRID_FAKE003",
        "empresa": "Banvox",
        "cadoc": "DLO_2061",
        "regra": "R2",
        "motivo": "Triagem automática: Finaud transmitiu arquivo ao cliente (DLO_2061).",
    }
    assert not _tem_motivo_ff_aguardando(registro)


def test_nao_detecta_motivo_r5_conclusivo():
    """Thread F→F conclusiva (R5) com motivo correto não é flagrada."""
    registro = {
        "threadId": "GMTHRID_FAKE004",
        "empresa": "Finaud",
        "cadoc": "SUPORTE",
        "regra": "R5",
        "motivo": "Triagem automática: F→F conclusivo — Finaud encerrou internamente (SUPORTE).",
    }
    assert not _tem_motivo_ff_aguardando(registro)


def test_motivo_vazio_nao_detectado():
    """Thread sem motivo não é flagrada."""
    assert not _tem_motivo_ff_aguardando({"threadId": "GMTHRID_FAKE005"})


# ── Teste contra dados reais (pula se arquivo não existir — CI não tem dados) ───

def _caminho_co():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "json", "pipeline", "threads_concluidas_auto.json")


def test_co_sem_motivo_ff_aguardando():
    """Nenhum registro em CO deve ter motivo F→F 'aguarda tratamento'."""
    path = _caminho_co()
    if not os.path.exists(path):
        pytest.skip("Arquivo CO não encontrado (ambiente sem dados de pipeline)")

    with open(path, encoding="utf-8") as f:
        co = json.load(f)

    violacoes = [t for t in co if _tem_motivo_ff_aguardando(t)]

    if violacoes:
        detalhes = "\n".join(
            f"  - {t.get('empresa','?')} / {t.get('cadoc','?')} "
            f"(regra={t.get('regra','?')}, tid={t.get('threadId','?')[:30]})"
            for t in violacoes[:10]
        )
        pytest.fail(
            f"{len(violacoes)} thread(s) em CO com motivo F→F 'aguarda tratamento' "
            f"— status e motivo contraditórios:\n{detalhes}"
        )
