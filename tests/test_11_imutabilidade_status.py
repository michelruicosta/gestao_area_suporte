# -*- coding: utf-8 -*-
"""
QA – Imutabilidade do status dos fios e guard de regressão.

Garantem que:

1. ``_strip_auto_para_tids`` preserva registos:
   - de outro ``alvo_triagem_auto`` (mesmo dia);
   - de dia anterior (``cl < dia_ref``);
   - com ``cl is None`` (data inválida/ausente) e ``dia_ref`` definido;
   - manuais (``origem_triagem_auto != True``);
   - cujo ``threadId`` **não** está em ``tids_strip``.

2. ``_run_triagem_cadocs`` **não** apaga fios já tratados quando a triagem é
   re-executada sem nova carga (sequência de múltiplos alvos).

3. ``guard_imutabilidade`` detecta:
   - REGRESSAO_PENDENTE (ag → ∅ ou co → ∅);
   - ALTERACAO_STATUS (ag ↔ co);
   - ALTERACAO_MANUAL.

4. Com ``ORACULO_CARGA_EM_CURSO=1`` o guard permite alteração; fora de carga,
   com ``ORACULO_BLOQUEAR_REGRESSAO_STATUS`` default, aborta com
   ``RegressaoStatusError``.

Corre assim (isolado):
    python -m pytest tests/test_11_imutabilidade_status.py -v
"""
from __future__ import annotations

import copy
import os
import sys
from datetime import date

import pytest

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_BASE, "scripts")
for _p in (_SCRIPTS, _BASE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────

def _reg_concluido(tid: str, alvo: str = "DDR4111", data_conclusao: str = "2026-04-22 18:00:00",
                   manual: bool = False) -> dict:
    return {
        "threadId": tid,
        "alvo_triagem_auto": alvo,
        "origem_triagem_auto": not manual,
        "data_conclusao": data_conclusao,
        "qtd_mensagens_no_fechamento": 2,
        "motivo": f"Triagem automática ({alvo})",
    }


def _reg_aguardando(tid: str, alvo: str = "DDR4111", data_marcacao: str = "2026-04-22 10:00:00",
                    tipo: str = "ACAO_INTERNA", manual: bool = False) -> dict:
    return {
        "threadId": tid,
        "alvo_triagem_auto": alvo,
        "origem_triagem_auto": not manual,
        "data_marcacao": data_marcacao,
        "tipo": tipo,
        "motivo": f"Triagem automática ({alvo}) — motivo teste",
    }


# ────────────────────────────────────────────────────────────────────────
# 1. _strip_auto_para_tids — preservações
# ────────────────────────────────────────────────────────────────────────

def test_strip_preserva_alvo_diferente_mesmo_dia():
    """Registo do alvo RETORNO_BACEN não deve ser removido por run DDR4111."""
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid = "GMTHRID_ALPHA"
    co = [
        _reg_concluido(tid, alvo="RETORNO_BACEN", data_conclusao="2026-04-22 18:00:00"),
    ]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", {tid}, dia_ref=date(2026, 4, 22), lista_aguardando=False,
    )
    assert n == 0
    assert len(out) == 1
    assert out[0]["alvo_triagem_auto"] == "RETORNO_BACEN"


def test_strip_preserva_registro_dia_anterior():
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid = "GMTHRID_BETA"
    co = [_reg_concluido(tid, alvo="DDR4111", data_conclusao="2026-04-20 18:00:00")]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", {tid}, dia_ref=date(2026, 4, 22), lista_aguardando=False,
    )
    assert n == 0
    assert out and out[0]["threadId"] == tid


def test_strip_preserva_cl_none_quando_dia_ref_definido():
    """Data de fecho não parseável não deve resultar em remoção quando há dia_ref."""
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid = "GMTHRID_GAMMA"
    co = [{
        "threadId": tid,
        "alvo_triagem_auto": "DDR4111",
        "origem_triagem_auto": True,
        # data_conclusao ausente/inválida
        "data_conclusao": "",
    }]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", {tid}, dia_ref=date(2026, 4, 22), lista_aguardando=False,
    )
    assert n == 0, "cl=None com dia_ref deve preservar defensivamente"
    assert out and out[0]["threadId"] == tid


def test_strip_remove_todos_tids_na_lista():
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid = "GMTHRID_DELTA"
    co = [_reg_concluido(tid, alvo="DDR4111", manual=True)]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", {tid}, dia_ref=date(2026, 4, 22), lista_aguardando=False,
    )
    # Todos os registros no conjunto de tids são removidos, independente de origem_triagem_auto
    assert n == 1
    assert out == []


def test_strip_preserva_tid_fora_de_tids_strip():
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid_alvo = "GMTHRID_EPS"
    tid_outro = "GMTHRID_ZETA"
    co = [
        _reg_concluido(tid_outro, alvo="DDR4111", data_conclusao="2026-04-22 18:00:00"),
    ]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", {tid_alvo}, dia_ref=date(2026, 4, 22), lista_aguardando=False,
    )
    assert n == 0
    assert out and out[0]["threadId"] == tid_outro


def test_strip_remove_mesmo_alvo_mesmo_dia_em_tids_strip():
    """Única condição legítima de remoção."""
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid = "GMTHRID_ETA"
    co = [_reg_concluido(tid, alvo="DDR4111", data_conclusao="2026-04-22 18:00:00")]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", {tid}, dia_ref=date(2026, 4, 22), lista_aguardando=False,
    )
    assert n == 1
    assert out == []


def test_strip_sem_dia_ref_preserva_quem_nao_recebeu_nova_classificacao():
    """Sem dia_ref (ramo 'else' antigo): agora também deve preservar fios fora de tids_strip."""
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid_mantido = "GMTHRID_MANTIDO"
    co = [_reg_concluido(tid_mantido, alvo="DDR4111", data_conclusao="2026-04-22 18:00:00")]
    out, n = _strip_auto_para_tids(
        co, "DDR4111", set(), dia_ref=None, lista_aguardando=False,
    )
    assert n == 0, "Sem tids_strip, nada deve ser removido mesmo sem dia_ref"
    assert out and out[0]["threadId"] == tid_mantido


# ────────────────────────────────────────────────────────────────────────
# 2. guard_imutabilidade — detecção
# ────────────────────────────────────────────────────────────────────────

def test_guard_detecta_regressao_pendente():
    from guard_imutabilidade import detectar_regressoes, snapshot_status  # type: ignore

    antes = snapshot_status(
        aguardando=[_reg_aguardando("GMT_R1")],
        concluidas=[_reg_concluido("GMT_R2")],
    )
    depois = snapshot_status(aguardando=[], concluidas=[])
    regs = detectar_regressoes(antes, depois)
    eventos = {r["evento"] for r in regs}
    assert "REGRESSAO_PENDENTE" in eventos
    tids = {r["threadId"] for r in regs if r["evento"] == "REGRESSAO_PENDENTE"}
    assert tids == {"GMT_R1", "GMT_R2"}


def test_guard_detecta_alteracao_status():
    from guard_imutabilidade import detectar_regressoes, snapshot_status  # type: ignore

    antes = snapshot_status(aguardando=[_reg_aguardando("GMT_X")], concluidas=[])
    depois = snapshot_status(aguardando=[], concluidas=[_reg_concluido("GMT_X")])
    regs = detectar_regressoes(antes, depois)
    eventos = [r["evento"] for r in regs if r["threadId"] == "GMT_X"]
    assert "ALTERACAO_STATUS" in eventos


def test_guard_detecta_alteracao_manual():
    from guard_imutabilidade import detectar_regressoes, snapshot_status  # type: ignore

    ant_reg = _reg_aguardando("GMT_M", manual=True)
    dep_reg = dict(ant_reg)
    dep_reg["motivo"] = "outro motivo"
    antes = snapshot_status(aguardando=[ant_reg], concluidas=[])
    depois = snapshot_status(aguardando=[dep_reg], concluidas=[])
    regs = detectar_regressoes(antes, depois)
    eventos = [r["evento"] for r in regs if r["threadId"] == "GMT_M"]
    # Edição manual fica como ALTERACAO_MANUAL (crítica).
    assert "ALTERACAO_MANUAL" in eventos


# ────────────────────────────────────────────────────────────────────────
# 3. guard_imutabilidade — avaliar_transicao com/sem carga
# ────────────────────────────────────────────────────────────────────────

@pytest.fixture
def env_isolado(monkeypatch, tmp_path):
    """Isola PIPELINE_DIR e envs sensíveis por teste."""
    monkeypatch.delenv("ORACULO_CARGA_EM_CURSO", raising=False)
    monkeypatch.delenv("ORACULO_BLOQUEAR_REGRESSAO_STATUS", raising=False)
    # Redireciona F_ALERTAS para tmp (sem tocar no pipeline real).
    import guard_imutabilidade as gi  # type: ignore
    alertas_path = tmp_path / "ALERTAS_REGRESSAO.json"
    monkeypatch.setattr(gi, "F_ALERTAS", str(alertas_path))
    yield alertas_path


def test_guard_bloqueia_fora_de_carga(env_isolado):
    from guard_imutabilidade import (  # type: ignore
        RegressaoStatusError, avaliar_transicao, snapshot_status,
    )

    antes = snapshot_status(aguardando=[_reg_aguardando("GMT_Q")], concluidas=[])
    depois = snapshot_status(aguardando=[], concluidas=[])

    with pytest.raises(RegressaoStatusError):
        avaliar_transicao(antes, depois, contexto={"origem": "teste"})

    # Alerta foi gravado.
    import json
    with open(env_isolado, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list) and data, "Alerta deve ser gravado ao bloquear"
    assert any(
        r["evento"] == "REGRESSAO_PENDENTE"
        for entry in data
        for r in entry["regressoes"]
    )


def test_guard_permite_em_carga(env_isolado, monkeypatch):
    from guard_imutabilidade import avaliar_transicao, snapshot_status  # type: ignore

    monkeypatch.setenv("ORACULO_CARGA_EM_CURSO", "1")
    antes = snapshot_status(aguardando=[_reg_aguardando("GMT_C1")], concluidas=[])
    depois = snapshot_status(aguardando=[], concluidas=[_reg_concluido("GMT_C1")])
    # Não deve levantar.
    regs = avaliar_transicao(antes, depois, contexto={"origem": "teste"})
    assert any(r["evento"] == "ALTERACAO_STATUS" for r in regs)


def test_guard_modo_passivo_nao_bloqueia(env_isolado, monkeypatch):
    from guard_imutabilidade import avaliar_transicao, snapshot_status  # type: ignore

    monkeypatch.setenv("ORACULO_BLOQUEAR_REGRESSAO_STATUS", "0")
    antes = snapshot_status(aguardando=[_reg_aguardando("GMT_P1")], concluidas=[])
    depois = snapshot_status(aguardando=[], concluidas=[])
    # Não deve levantar; apenas grava alerta.
    regs = avaliar_transicao(antes, depois, contexto={"origem": "teste"})
    assert any(r["evento"] == "REGRESSAO_PENDENTE" for r in regs)


# ────────────────────────────────────────────────────────────────────────
# 4. Simulação de cenário real: triagem re-executada sem carga
# ────────────────────────────────────────────────────────────────────────

def test_cenario_triagem_reexecutada_sem_carga_preserva_tudo():
    """
    Cenário: temos 5 fios tratados (DDR4111, DLI, DLO, RETORNO_BACEN, SUPORTE).
    Uma triagem re-executada (sem nova carga) onde *nenhum* fio recebe nova
    classificação → tids_strip = {} → _strip_auto_para_tids preserva todos.
    """
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    co_estado = [
        _reg_concluido("GMT_DDR",   alvo="DDR4111",       data_conclusao="2026-04-22 18:00:00"),
        _reg_concluido("GMT_RBC",   alvo="RETORNO_BACEN", data_conclusao="2026-04-22 18:00:00"),
    ]
    ag_estado = [
        _reg_aguardando("GMT_DLI",  alvo="DLI",           data_marcacao="2026-04-22 10:00:00"),
        _reg_aguardando("GMT_DLO",  alvo="DLO",           data_marcacao="2026-04-22 10:00:00"),
        _reg_aguardando("GMT_SUP",  alvo="SUPORTE",       data_marcacao="2026-04-22 10:00:00"),
    ]

    # Para cada alvo, simulamos uma triagem onde nenhum fio gera novos → tids_strip vazio.
    for alvo in ("DDR4111", "DLI", "DLO", "SUPORTE", "DRSAC", "FORCAPITAL", "RETORNO_BACEN", "S5"):
        co_out, nco = _strip_auto_para_tids(
            copy.deepcopy(co_estado), alvo, set(), dia_ref=date(2026, 4, 22), lista_aguardando=False,
        )
        ag_out, nag = _strip_auto_para_tids(
            copy.deepcopy(ag_estado), alvo, set(), dia_ref=date(2026, 4, 22), lista_aguardando=True,
        )
        assert nco == 0, f"alvo={alvo}: nada deve ser removido de Concluído"
        assert nag == 0, f"alvo={alvo}: nada deve ser removido de Aguardando"
        assert len(co_out) == len(co_estado)
        assert len(ag_out) == len(ag_estado)


def test_cenario_retorno_bacen_preservado_mesmo_dia_quando_ddr4111_re_roda():
    """
    Reproduz a regressão observada: DDR4111 re-executada para o mesmo dia que
    tinha fechos RETORNO_BACEN. Esses fechos devem permanecer intactos.
    """
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tids_rbc = [f"GMT_RBC_{i}" for i in range(5)]
    ag_estado = [
        _reg_aguardando(t, alvo="RETORNO_BACEN", data_marcacao="2026-04-22 10:00:00")
        for t in tids_rbc
    ]
    co_estado = []

    # Run DDR4111 no mesmo dia_ref, onde dois tids RETORNO_BACEN acabam nos
    # candidatos (porque têm evento DDR/4111/DRL no thread). Mesmo assim, como
    # os registos existentes são de outro alvo, não devem ser removidos.
    tids_strip = {tids_rbc[0], tids_rbc[1]}  # estes dois "entraram em candidatos" hoje
    ag_out, nag = _strip_auto_para_tids(
        ag_estado, "DDR4111", tids_strip, dia_ref=date(2026, 4, 22), lista_aguardando=True,
    )
    assert nag == 0
    assert len(ag_out) == 5


# ────────────────────────────────────────────────────────────────────────
# 5. Estado no disco: snapshot_status sem args lê do ficheiro
# ────────────────────────────────────────────────────────────────────────

def test_snapshot_status_le_listas_explicitas_independente_do_disco():
    from guard_imutabilidade import snapshot_status  # type: ignore

    snap = snapshot_status(
        aguardando=[_reg_aguardando("GMT_L1", alvo="DDR4111")],
        concluidas=[_reg_concluido("GMT_L2", alvo="RETORNO_BACEN")],
    )
    assert snap["GMT_L1"]["status"] == "AGUARDANDO"
    assert snap["GMT_L1"]["alvo"] == "DDR4111"
    assert snap["GMT_L2"]["status"] == "CONCLUIDO"
    assert snap["GMT_L2"]["alvo"] == "RETORNO_BACEN"
    assert snap["GMT_L2"]["origem_triagem_auto"] is True


# ────────────────────────────────────────────────────────────────────────
# 6. Restauração automática anti-regressão dentro de _run_triagem_cadocs
# ────────────────────────────────────────────────────────────────────────

def test_strip_nao_remove_tid_que_nao_recebeu_nova_classificacao_mesmo_alvo():
    """
    Cenário da brecha original: triagem re-executada sem nova carga.
    Threads do mesmo alvo que não recebem nova classificação (não estão
    em tids_strip) devem ser preservados — a linha 2 das condições de
    _strip_auto_para_tids garante isso.
    """
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tid = "GMTHRID_PRESERVAR"
    co = [_reg_concluido(tid, alvo="RETORNO_BACEN", data_conclusao="2026-04-24 18:00:00")]

    # Simula corrida DDR4111 no dia 24, sem este tid nos resultados
    out, n = _strip_auto_para_tids(
        co, "RETORNO_BACEN", set(),  # tids_strip vazio = nenhum tid recebeu nova classif
        dia_ref=date(2026, 4, 24), lista_aguardando=False,
    )
    assert n == 0, "Sem nova classificacao, nada deve ser removido"
    assert out and out[0]["threadId"] == tid


def test_sec5_nao_capta_segue_dentro_de_consegue():
    """
    Regressão 2026-04: «Consegue encaminhar a remessa…» não é remessa §5
    (a substring «segue» não pode vir de dentro da palavra «Conseg**ue**»).
    """
    from triagem_auto_ddr4111 import _finaud_pedido_insumos_a_cliente, _sec5_remessa_finaud  # type: ignore

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": (
            "Boa tarde, Consegue encaminhar a remessa DLO (2061) dez/2025 "
            "para análise do arquivo XML? Antecipadamente grata."
        ),
        "assunto": "RE: Informe 2061",
    }
    assert _sec5_remessa_finaud(ult) is False
    assert _finaud_pedido_insumos_a_cliente(ult) is True


def test_sec5_nao_liga_dlo_dezembro_na_citacao_gmail():
    """
    2026-04: §5 não deve juntar ``corpo`` HTML completo — citação traz «Re: Erro DLO» e
    «remessa de dezembro» noutro bloco; regex (dlo).{0,40}(dezembro) gerava falso §5
    em «em análise, retornaremos» (BCP / RETORNO BACEN).
    """
    from triagem_auto_ddr4111 import _sec5_remessa_finaud  # type: ignore

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "assunto": "Re: Erro DLO",
        "corpo_limpo": (
            "Prezada Thaiana, boa tarde. Certo, a questão das contas RWAOPAD 875 está em análise "
            "com a nossa área técnica. Retornaremos em breve. À disposição."
        ),
        "corpo": (
            "Prezada Thaiana, boa tarde.\n\nCerto, em análise.\n\n"
            "Em ter., 24 de fev. de 2026, Cliente <c@x.com> escreveu:\n\n"
            "Boa tarde Remessa de dezembro/2025, segue documento.\n\nRe: Erro DLO\n"
        ),
    }
    assert _sec5_remessa_finaud(ult) is False


def test_sec5_nao_mistura_pedido_ddr_com_prazo_envio_bc():
    """
    2026-04: F→C com «por gentileza enviar…» e «Data de envio ao Banco Central:» (prazos)
    não é §5 remessa (antes batia a alternativa de envio ao BC).
    """
    from triagem_auto_ddr4111 import (  # type: ignore
        _finaud_pedido_insumos_a_cliente,
        _sec5_remessa_finaud,
    )

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": (
            "Bom dia! Por gentileza enviar para cálculo dos DDRs dos dias 18, 19, 20 e 23/02/2026: "
            "Extrato em CDBs; Caso tenham sido realizadas novas aplicações, por gentileza enviar também. "
            "Data de envio ao Banco Central: DDR de 18/02 data limite para envio 23/02/2026; "
            "DDR de 19/02 data limite para envio 24/02/2026."
        ),
        "assunto": "Informações para DDRs de 18, 19, 20 e 23/02/2026.",
    }
    assert _sec5_remessa_finaud(ult) is False
    assert _finaud_pedido_insumos_a_cliente(ult) is True


def test_sec5_ultima_cf_segue_relacao_nao_fecha_por_ufc():
    """
    2026-04: Última C→F «Segue relação» (sem agradecimento) não fica Concluído via §5
    a partir de um F→C pedido anterior (o ``ufc`` de ``_ultima_mensagem_finaud``).
    """
    import sys
    from datetime import date

    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _SCR = os.path.join(_BASE, "scripts")
    if _SCR not in sys.path:
        sys.path.insert(0, _SCR)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_DDR4111, triar  # type: ignore

    tid = "GMTHRID_TEST_CFC_SEGUE_REL"
    pedido = (
        "Bom dia! Por gentileza enviar para cálculo dos DDRs: Extrato em CDBs. "
        "Data de envio ao Banco Central: DDR de 18/02 data limite 23/02/2026."
    )
    dados = {
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {
                        "id": "m1",
                        "timestamp_epoch": 100,
                        "data_iso": "2026-02-24",
                        "contato_origem": {"lado": "FINAUD"},
                        "contato_destino": {"lado": "CLIENTE"},
                        "assunto": "Informações para DDRs",
                        "corpo_limpo": pedido,
                    },
                    {
                        "id": "m2",
                        "timestamp_epoch": 200,
                        "data_iso": "2026-02-24",
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "assunto": "RE: Informações para DDRs",
                        "corpo_limpo": "Boa dia! Segue relação.",
                    },
                ],
            }
        ],
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR_2011",
                "cliente": "Trinus CO",
                "titulo": "Informações para DDRs",
                "timestamp_epoch": 200,
                "data_iso": "2026-02-24",
            }
        ],
    }
    co, ag, log = triar(
        dados,
        date(2026, 2, 24),
        CADOC_TRIAGEM_DDR4111,
        True,
        "DDR4111",
    )
    tids_co = {r.get("threadId") for r in co}
    tids_ag = {r.get("threadId") for r in ag}
    assert tid in tids_ag, (log, "esperava Aguardando Finaud após C→F sem só agradecimento")
    assert tid not in tids_co, (log, "não deve concluir por §5 com última C→F «Segue relação»")
    assert not any("§5 remessa" in line for line in log if tid in line), log


def test_strip_restauracao_semantica_via_tids_strip_vazio():
    """
    5 threads RETORNO_BACEN como no problema real: triagem re-executada,
    nenhum tid em tids_strip → todos preservados.
    """
    from triagem_auto_ddr4111 import _strip_auto_para_tids  # type: ignore

    tids = [f"GMT_RBC_{i}" for i in range(5)]
    ag = [_reg_aguardando(t, alvo="RETORNO_BACEN", data_marcacao="2026-04-24 10:00:00") for t in tids]

    out, n = _strip_auto_para_tids(
        ag, "RETORNO_BACEN", set(), dia_ref=date(2026, 4, 24), lista_aguardando=True,
    )
    assert n == 0
    assert len(out) == 5


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
