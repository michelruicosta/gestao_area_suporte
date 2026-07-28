# -*- coding: utf-8 -*-
"""
Testes de integração para _run_triagem_cadocs (scripts/triagem/motor.py).

Cobre as Regras 0, 1, 1b, 1c, 2, 2b, 3, 4, 5, 6, 7, 8 e 9-A/B/C
do bloco de pós-processamento.

O motor é executado com apply=True sobre dados de fixture (sem disco).
Cada teste controla:
  - dados_03  → mapa_pre com thread e mensagens específicas
  - triar()   → novos_co / novos_ag controlados (mock do módulo)
  - co/ag     → estado anterior (mock de load_concluidas/load_aguardando)
Verifica o que save_concluidas / save_aguardando recebem.

Não lê nem grava nenhum arquivo do pipeline.
"""
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import triagem.motor as _motor


# ---------------------------------------------------------------------------
# Reset do cache global entre testes
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_cache():
    _motor._CACHE_DADOS_03["dados"] = None
    _motor._CACHE_DADOS_03["mtime"] = None
    yield
    _motor._CACHE_DADOS_03["dados"] = None
    _motor._CACHE_DADOS_03["mtime"] = None


# ---------------------------------------------------------------------------
# Fábricas de fixture
# ---------------------------------------------------------------------------
def _msg(corpo, origem="FINAUD", destino="CLIENTE", assunto="", data_email="2026-06-15"):
    """Mensagem mínima com contato_origem/destino, corpo e data."""
    email_orig = "ana@finaud.com.br" if origem == "FINAUD" else "cli@empresa.com.br"
    email_dest = "cli@empresa.com.br" if destino == "CLIENTE" else "ana@finaud.com.br"
    return {
        "contato_origem": {"lado": origem, "email": email_orig},
        "contato_destino": {"lado": destino, "email": email_dest},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": assunto,
        "data_email": data_email,
        "timestamp_epoch": 1748736000,  # 2026-06-01 — usado como fallback por _parse_data_msg
    }


def _dados_03(tid, *msgs):
    """dados_03 mínimo com um thread."""
    return {
        "threads": [{"threadId": tid, "mensagens": list(msgs), "assunto": f"Thread {tid}"}],
        "eventos": [],
    }


def _rec_ag(tid, tipo="ACAO_INTERNA", alvo="DDR4111", cadoc="DDR_2011"):
    """Registro AGUARDANDO fictício como retornado por triar()."""
    return {
        "threadId": tid,
        "tipo": tipo,
        "status": "AGUARDANDO",
        "alvo_triagem_auto": alvo,
        "cadoc": cadoc,
        "origem_triagem_auto": True,
        "motivo": "triagem auto",
        "empresa": "Empresa Teste",
        "data_marcacao": "2026-06-10",
    }


def _rec_co(tid, alvo="DDR4111", data_conclusao="2026-06-10"):
    """Registro CONCLUIDO fictício como retornado por triar()."""
    return {
        "threadId": tid,
        "tipo": "RESOLVIDA",
        "status": "CONCLUIDO",
        "alvo_triagem_auto": alvo,
        "cadoc": "DDR_2011",
        "origem_triagem_auto": True,
        "motivo": "concluido auto",
        "data_conclusao": data_conclusao,
        "empresa": "Empresa Teste",
    }


# ---------------------------------------------------------------------------
# Executor central — isola todo I/O, devolve (co_salvo, ag_salvo)
# ---------------------------------------------------------------------------
def _run(dados_03, triar_return, co_existente=None, ag_existente=None, alvo_triagem="DDR4111"):
    """
    Executa _run_triagem_cadocs com I/O completamente mockado.

    Retorna (co_final, ag_final) — as listas que seriam gravadas em disco.
    """
    co_existente = list(co_existente or [])
    ag_existente = list(ag_existente or [])
    captured: dict = {}

    mock_triar_mod = MagicMock()
    mock_triar_mod.triar.return_value = triar_return

    with (
        patch("triagem.motor.os.path.isfile", return_value=True),
        patch("triagem.motor.os.path.getmtime", return_value=0.0),
        patch("triagem.motor.load_concluidas", return_value=co_existente),
        patch("triagem.motor.load_aguardando", return_value=ag_existente),
        patch(
            "triagem.motor.save_concluidas",
            side_effect=lambda x: captured.update({"co": list(x)}),
        ),
        patch(
            "triagem.motor.save_aguardando",
            side_effect=lambda x: captured.update({"ag": list(x)}),
        ),
        patch.dict("sys.modules", {"triagem_auto_ddr4111": mock_triar_mod}),
        # Guard de imutabilidade bloqueia CO→AG fora de carga (correto em produção).
        # Em testes, simulamos contexto de carga para permitir transições de status.
        patch.dict("os.environ", {"ORACULO_CARGA_EM_CURSO": "1"}),
    ):
        _motor._CACHE_DADOS_03["dados"] = dados_03
        _motor._CACHE_DADOS_03["mtime"] = 0.0

        from triagem.motor import _run_triagem_cadocs

        _run_triagem_cadocs(
            apply=True,
            data_ref=None,
            cadocs=frozenset({"DDR_2011"}),
            com_sec6b=False,
            log_prefix="TEST",
            alvo_triagem=alvo_triagem,
        )

    return captured.get("co", []), captured.get("ag", [])


def _get(lista, tid):
    """Devolve o registro com threadId=tid ou None."""
    for r in lista:
        if isinstance(r, dict) and str(r.get("threadId") or "").strip() == tid:
            return r
    return None


# ===========================================================================
# Regra 9-A: CO com última msg C→F + insumo do cliente → AG
# ===========================================================================
class TestRegra9A:
    def test_insumo_cliente_move_para_ag(self):
        """Thread fechada, mas última msg: cliente enviou insumo → reabre como AGUARDANDO."""
        tid = "t_r9a"
        msg = _msg("Segue o balancete para análise.", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid)], [], []),
        )

        assert _get(co, tid) is None, "R9-A: thread não deve ir para CO"
        r = _get(ag, tid)
        assert r is not None, "R9-A: thread deve ficar em AG"
        assert "#R9A" in (r.get("motivo") or ""), "R9-A: motivo deve registrar a regra"

    def test_nao_dispara_quando_transmitido(self):
        """Insumo + 'transmitido no BACEN' → thread já concluída, R9-A não reabre."""
        tid = "t_r9a_tx"
        msg = _msg("Segue o balancete. Já transmitido no BACEN.", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid)], [], []),
        )

        assert _get(co, tid) is not None, "R9-A não deve disparar com 'transmitido no BACEN'"

    def test_r9a_nao_dispara_sem_insumo(self):
        """Mensagem C→F sem padrão de insumo → thread continua CO."""
        tid = "t_r9a_neutro"
        msg = _msg("Bom dia! Tudo certo.", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid)], [], []),
        )

        assert _get(co, tid) is not None, "R9-A não deve disparar sem insumo"


# ===========================================================================
# Regra 9-B: CO com última msg F→C + Finaud pediu insumo → AG
# ===========================================================================
class TestRegra9B:
    def test_finaud_pediu_insumo_move_para_ag(self):
        """Finaud pediu insumo ao cliente → thread reabre como AGUARDANDO."""
        tid = "t_r9b"
        msg = _msg("Poderia nos enviar os extratos COSIF do período?", "FINAUD", "CLIENTE")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid)], [], []),
        )

        assert _get(co, tid) is None, "R9-B: thread não deve ir para CO"
        r = _get(ag, tid)
        assert r is not None, "R9-B: thread deve ficar em AG"
        assert "#R9B" in (r.get("motivo") or ""), "R9-B: motivo deve registrar a regra"

    def test_nao_dispara_com_remessa_sec5(self):
        """Finaud pediu E entregou arquivo (§5) → R9-B não dispara."""
        tid = "t_r9b_sec5"
        msg = _msg(
            "Poderia confirmar? Seguem os arquivos DDR para envio ao bacen.",
            "FINAUD", "CLIENTE",
        )
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid)], [], []),
        )

        assert _get(co, tid) is not None, "R9-B não deve disparar quando há remessa §5"

    def test_nao_dispara_com_bola_crd(self):
        """Finaud indicou encaminhar via CRD → R9-B não dispara (bola passou ao cliente)."""
        tid = "t_r9b_crd"
        msg = _msg(
            "Por gentileza encaminhar consulta ao BC via CRD.",
            "FINAUD", "CLIENTE",
        )
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid)], [], []),
        )

        assert _get(co, tid) is not None, "R9-B não deve disparar com bola CRD"


# ===========================================================================
# Regra 9-C (M31): CO com msg nova do cliente APÓS data_conclusao → AG
# ===========================================================================
class TestRegra9C:
    def test_msg_nova_apos_conclusao_move_para_ag(self):
        """Cliente mandou mensagem em jun/26 em thread concluída em mai/26 → reabre."""
        tid = "t_r9c"
        # Mensagem com data_email posterior à conclusão anterior (2026-05-01)
        msg = _msg("Preciso de ajuda adicional.", "CLIENTE", "FINAUD",
                   data_email="2026-06-15")

        co_ant = {
            "threadId": tid,
            "alvo_triagem_auto": "DDR4111",
            "origem_triagem_auto": True,
            "data_conclusao": "2026-05-01",
            "tipo": "RESOLVIDA",
        }
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid, data_conclusao="2026-05-01")], [], []),
            co_existente=[co_ant],
        )

        assert _get(co, tid) is None, "R9-C: thread não deve estar em CO"
        r = _get(ag, tid)
        assert r is not None, "R9-C: thread deve ficar em AG"
        assert "#R9C" in (r.get("motivo") or ""), "R9-C: motivo deve registrar a regra"

    def test_agradecimento_apos_conclusao_nao_reabre(self):
        """Cliente manda 'Valeu!' após conclusão → R9-C não reabre (permanece CONCLUÍDO)."""
        tid = "t_r9c_valeu"
        msg = _msg("Valeu Flavio! Ótima terça.", "CLIENTE", "FINAUD",
                   data_email="2026-06-15")
        co_ant = {
            "threadId": tid,
            "alvo_triagem_auto": "DDR4111",
            "origem_triagem_auto": True,
            "data_conclusao": "2026-06-10",
            "tipo": "RESOLVIDA",
        }
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid, data_conclusao="2026-06-10")], [], []),
            co_existente=[co_ant],
        )
        assert _get(co, tid) is not None, "R9-C: agradecimento não deve reabrir thread"
        assert _get(ag, tid) is None, "R9-C: thread não deve ir para AG por agradecimento"

    def test_obrigado_apos_conclusao_nao_reabre(self):
        """Cliente manda 'Obrigado!' após conclusão → R9-C não reabre."""
        tid = "t_r9c_obrigado"
        msg = _msg("Muito obrigado pela ajuda!", "CLIENTE", "FINAUD",
                   data_email="2026-06-15")
        co_ant = {
            "threadId": tid,
            "alvo_triagem_auto": "DDR4111",
            "origem_triagem_auto": True,
            "data_conclusao": "2026-06-10",
            "tipo": "RESOLVIDA",
        }
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([_rec_co(tid, data_conclusao="2026-06-10")], [], []),
            co_existente=[co_ant],
        )
        assert _get(co, tid) is not None, "R9-C: 'Obrigado!' não deve reabrir thread"
        assert _get(ag, tid) is None, "R9-C: thread não deve ir para AG por agradecimento"


# ===========================================================================
# Regra 0 (M30): recall/cancelamento de mensagem → CONCLUIDO
# ===========================================================================
class TestRegra0M30:
    def test_recall_fecha_thread(self):
        """Mensagem de recall → thread encerrada automaticamente."""
        tid = "t_r0"
        msg = _msg("I would like to recall the message sent earlier.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R0: thread deve ir para CO"
        assert _get(ag, tid) is None, "R0: thread não deve ficar em AG"

    def test_cancelamento_pt_fecha_thread(self):
        """Variante em português do recall."""
        tid = "t_r0_pt"
        msg = _msg("Mensagem cancelada pelo remetente.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R0-PT: thread deve ir para CO"


# ===========================================================================
# Regra 1: entrega conclusiva da Finaud → CONCLUIDO
# ===========================================================================
class TestRegra1:
    def test_aceito_sta_fecha_thread(self):
        """Finaud informa aceite no STA → CONCLUIDO."""
        tid = "t_r1"
        msg = _msg("Arquivo aceito no STA. Segue protocolo em anexo.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R1: thread deve ir para CO"
        assert _get(ag, tid) is None, "R1: thread não deve ficar em AG"

    def test_transmitido_bacen_fecha_thread(self):
        """Remessa transmitida ao BACEN → CONCLUIDO."""
        tid = "t_r1_tx"
        msg = _msg("Remessa DDR_2011 transmitida ao Banco Central com sucesso.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R1-tx: thread deve ir para CO"


# ===========================================================================
# Regra 1b: Finaud instruiu cliente com orientação conclusiva → CONCLUIDO
# ===========================================================================
class TestRegra1b:
    def test_instrucao_conclusiva_fecha_thread(self):
        """Finaud deu instrução conclusiva ao cliente → CONCLUIDO."""
        tid = "t_r1b"
        msg = _msg("Para solucionar a crítica, transmita o arquivo como Substituição.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R1b: thread deve ir para CO"
        assert _get(ag, tid) is None, "R1b: thread não deve ficar em AG"


# ===========================================================================
# Regra 1c: Finaud realizou reset/acesso → CONCLUIDO
# ===========================================================================
class TestRegra1c:
    def test_reset_senha_fecha_thread(self):
        """Finaud confirma reset de senha → CONCLUIDO."""
        tid = "t_r1c"
        msg = _msg("Realizei o reset de senha. O acesso foi liberado.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R1c: thread deve ir para CO"
        assert _get(ag, tid) is None, "R1c: thread não deve ficar em AG"


# ===========================================================================
# Regra 2: cliente agradece sem pedido adicional → CONCLUIDO
# ===========================================================================
class TestRegra2:
    def test_agradecimento_cliente_fecha_thread(self):
        """Cliente agradece curto sem '?' → CONCLUIDO."""
        tid = "t_r2"
        msg = _msg("Obrigado pela ajuda!", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R2: thread deve ir para CO"
        assert _get(ag, tid) is None, "R2: thread não deve ficar em AG"


# ===========================================================================
# Regra 2b: cliente confirmou conclusão → CONCLUIDO
# ===========================================================================
class TestRegra2b:
    def test_arquivo_aceito_cliente_fecha_thread(self):
        """Cliente informa que arquivo foi aceito no BACEN → CONCLUIDO."""
        tid = "t_r2b"
        msg = _msg("O arquivo foi aceito no BACEN com sucesso.", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R2b: thread deve ir para CO"
        assert _get(ag, tid) is None, "R2b: thread não deve ficar em AG"


# ===========================================================================
# Regra 3: cliente pergunta sem enviar dados → RESPOSTA_CLIENTE
# ===========================================================================
class TestRegra3:
    def test_pergunta_cliente_vira_resposta_cliente(self):
        """Cliente faz pergunta sem dados → tipo muda para RESPOSTA_CLIENTE."""
        tid = "t_r3"
        # "arquivo" está na lista de veto de _cpa — usar texto sem as palavras vetadas
        msg = _msg("Qual é o prazo para enviar o DDR?", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ACAO_INTERNA")], []),
        )

        assert _get(co, tid) is None, "R3: thread não deve ir para CO"
        r = _get(ag, tid)
        assert r is not None, "R3: thread deve ficar em AG"
        assert r.get("tipo") == "RESPOSTA_CLIENTE", (
            f"R3: esperado RESPOSTA_CLIENTE, obteve {r.get('tipo')!r}"
        )


# ===========================================================================
# Regra 4: F→F conclusivo → CONCLUIDO
# ===========================================================================
class TestRegra4:
    def test_ff_conclusivo_fecha_thread(self):
        """Dois colaboradores Finaud, último confirma conclusão → CONCLUIDO."""
        tid = "t_r4"
        msg1 = _msg("Segue o draft do DDR para revisão interna.", "FINAUD", "FINAUD")
        msg2 = _msg("Resolvido. O arquivo foi transmitido ao BACEN com sucesso.", "FINAUD", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg1, msg2),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is not None, "R4: thread deve ir para CO"
        assert _get(ag, tid) is None, "R4: thread não deve ficar em AG"


# ===========================================================================
# Regra 5 (#PF35): Finaud entregou arquivo para cliente transmitir → ENTREGA_CLIENTE
# ===========================================================================
class TestRegra5:
    def test_pf35_seguem_cadoc_entrega_cliente(self):
        """Finaud entrega cadoc para revisão → tipo ENTREGA_CLIENTE."""
        tid = "t_r5"
        # "seguem cadoc...envio ao BACEN" dispara _fec (Grupo 6 de motor.py);
        # sem "envio/bacen/banco central" o texto passa por R1 e chega ao R5.
        msg = _msg("Seguem cadoc para revisão do cliente.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ACAO_INTERNA")], []),
        )

        assert _get(co, tid) is None, "R5: thread não deve ir para CO"
        r = _get(ag, tid)
        assert r is not None, "R5: thread deve ficar em AG"
        assert r.get("tipo") == "ENTREGA_CLIENTE", (
            f"R5: esperado ENTREGA_CLIENTE, obteve {r.get('tipo')!r}"
        )

    def test_pf35_para_envio_ao_bacen(self):
        """'para envio ao bacen' no corpo (sem 'segue em anexo') → ENTREGA_CLIENTE."""
        tid = "t_r5b"
        # "segue em anexo" dispara _fec — usar construção alternativa
        msg = _msg("Os arquivos estão prontos para envio ao bacen.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ACAO_INTERNA")], []),
        )

        r = _get(ag, tid)
        assert r is not None
        assert r.get("tipo") == "ENTREGA_CLIENTE", (
            f"R5b: esperado ENTREGA_CLIENTE, obteve {r.get('tipo')!r}"
        )


# ===========================================================================
# Regra 6 (#PF46): Finaud pediu insumo/retorno ao cliente → RESPOSTA_CLIENTE
# ===========================================================================
class TestRegra6:
    def test_pf46_pedido_vira_resposta_cliente(self):
        """Finaud pede insumo → tipo RESPOSTA_CLIENTE."""
        tid = "t_r6"
        msg = _msg("Por gentileza encaminhar o arquivo DDR do período.")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ACAO_INTERNA")], []),
        )

        assert _get(co, tid) is None, "R6: thread não deve ir para CO"
        r = _get(ag, tid)
        assert r is not None, "R6: thread deve ficar em AG"
        assert r.get("tipo") == "RESPOSTA_CLIENTE", (
            f"R6: esperado RESPOSTA_CLIENTE, obteve {r.get('tipo')!r}"
        )


# ===========================================================================
# Regra 7 (#PF46 facr): Finaud agradeceu curto sem remessa → CONCLUIDO
# ===========================================================================
class TestRegra7:
    def test_agradecimento_curto_finaud_fecha_thread(self):
        """Finaud manda agradecimento curto sem §5 → CONCLUIDO."""
        tid = "t_r7"
        msg = _msg("Obrigada.", "FINAUD", "CLIENTE")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ACAO_INTERNA")], []),
        )

        assert _get(co, tid) is not None, "R7: thread deve ir para CO"
        assert _get(ag, tid) is None, "R7: thread não deve ficar em AG"

    def test_agradecimento_com_remessa_fecha_via_fec(self):
        """Finaud agradece + entrega arquivo → _fec (R1) dispara, não R7."""
        tid = "t_r7_sec5"
        # "Segue em anexo" aciona _fec antes de chegarmos ao R7.
        # O resultado correto é CONCLUIDO — mas via R1, não via _facr.
        msg = _msg("Obrigada. Segue em anexo o DDR para envio ao bacen.", "FINAUD", "CLIENTE")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ACAO_INTERNA")], []),
        )

        # _fec (R1) fecha a thread corretamente — CO é o resultado esperado
        assert _get(co, tid) is not None, (
            "R1 (_fec) deve fechar a thread quando Finaud entrega arquivo"
        )
        assert _get(ag, tid) is None


# ===========================================================================
# Regra 8 (#Grupo2): RESPOSTA/ENTREGA_CLIENTE com última msg do cliente → ACAO_INTERNA
# ===========================================================================
class TestRegra8:
    def test_grupo2_resposta_cliente_vira_acao_interna(self):
        """Cliente respondeu em thread RESPOSTA_CLIENTE → bola voltou à Finaud."""
        tid = "t_r8"
        msg = _msg("Bom dia, segue o documento solicitado.", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="RESPOSTA_CLIENTE")], []),
        )

        assert _get(co, tid) is None, "R8: thread não deve ir para CO"
        r = _get(ag, tid)
        assert r is not None, "R8: thread deve ficar em AG"
        assert r.get("tipo") == "ACAO_INTERNA", (
            f"R8: esperado ACAO_INTERNA, obteve {r.get('tipo')!r}"
        )

    def test_grupo2_entrega_cliente_vira_acao_interna(self):
        """ENTREGA_CLIENTE com msg do cliente → também vira ACAO_INTERNA."""
        tid = "t_r8b"
        msg = _msg("Arquivo enviado ao BACEN conforme solicitado.", "CLIENTE", "FINAUD")
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid, tipo="ENTREGA_CLIENTE")], []),
        )

        r = _get(ag, tid)
        assert r is not None, "R8b: thread deve ficar em AG"
        assert r.get("tipo") == "ACAO_INTERNA", (
            f"R8b: esperado ACAO_INTERNA, obteve {r.get('tipo')!r}"
        )


# ===========================================================================
# Guards gerais
# ===========================================================================
class TestGuards:
    def test_spam_vai_para_concluido_via_r0b(self):
        """E-mail de domínio spam → CONCLUÍDO via Regra 0b (spam/newsletter sem demanda).
        Antes da R0b, spam com 'Obrigado' ficava preso em AGUARDANDO.
        Agora vai para CONCLUÍDO, mas pelo motivo correto (R0b, não agradecimento).
        """
        tid = "t_spam"
        msg = {
            "contato_origem": {
                "lado": "CLIENTE",
                "email": "no-reply@messaging.metamail.com",
            },
            "contato_destino": {"lado": "FINAUD", "email": "ana@finaud.com.br"},
            "corpo_limpo": "Obrigado!",
            "corpo": "Obrigado!",
            "data_email": "2026-06-15",
        }
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        rec = _get(co, tid)
        assert rec is not None, "Spam: deve ir para CONCLUÍDO via Regra 0b"
        assert "R0b" in (rec.get("motivo_conclusao") or ""), "Spam: motivo deve ser R0b, não agradecimento"
        assert _get(ag, tid) is None, "Spam: não deve permanecer em AG"

    def test_sem_trigger_mantem_ag(self):
        """Mensagem neutra de Finaud (sem trigger) → thread permanece em AG."""
        tid = "t_neutro"
        msg = _msg(
            "Olá, estamos acompanhando o processo. "
            "Em breve retornaremos com mais informações.",
        )
        co, ag = _run(
            _dados_03(tid, msg),
            triar_return=([], [_rec_ag(tid)], []),
        )

        assert _get(co, tid) is None, "Neutro: thread não deve ir para CO"
        assert _get(ag, tid) is not None, "Neutro: thread deve ficar em AG"

    def test_dois_threads_independentes(self):
        """Duas threads na mesma corrida são classificadas independentemente."""
        tid_co = "t_multi_co"
        tid_ag = "t_multi_ag"

        dados = {
            "threads": [
                {"threadId": tid_co, "mensagens": [
                    _msg("Arquivo aceito no STA. Segue protocolo em anexo."),
                ], "assunto": "CO"},
                {"threadId": tid_ag, "mensagens": [
                    _msg("Qual é o prazo?", "CLIENTE", "FINAUD"),
                ], "assunto": "AG"},
            ],
            "eventos": [],
        }

        co, ag = _run(
            dados,
            triar_return=(
                [],
                [
                    _rec_ag(tid_co, tipo="ACAO_INTERNA"),
                    _rec_ag(tid_ag, tipo="ACAO_INTERNA"),
                ],
                [],
            ),
        )

        assert _get(co, tid_co) is not None, "Multi: tid_co deve ir para CO (R1)"
        assert _get(ag, tid_ag) is not None, "Multi: tid_ag deve ficar em AG (R3)"
        assert _get(co, tid_ag) is None, "Multi: tid_ag não deve ir para CO"
        assert _get(ag, tid_co) is None, "Multi: tid_co não deve ficar em AG"
