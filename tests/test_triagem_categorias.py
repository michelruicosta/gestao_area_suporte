# -*- coding: utf-8 -*-
"""
Testes de integração leve para os módulos de categoria de triagem.

Testa os detectores (Contexto -> bool) de cada categoria com threads
sintéticas mínimas. NÃO carrega JSON do pipeline nem chama triar() completo
(que exige arquivos em disco). Cobre a lógica de combinação de regras e
vetoes específicos de cada categoria.

Categorias cobertas: DDR4111, DLO, DLI, S5, SUPORTE, DRSAC, FORCAPITAL,
RETORNO_BACEN, DRM, CADOC6209 (onde aplicável).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from triagem._protocolo import Contexto
import triagem.ddr4111 as ddr
import triagem.dlo as dlo
import triagem.dli as dli
import triagem.s5 as s5
import triagem.suporte as sup
import triagem.drsac as drsac
import triagem.forcapital as fcp
import triagem.retorno_bacen as rb
import triagem.drm as drm
import triagem.cadoc6209 as c6209


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------
def _msg(corpo: str, origem: str = "FINAUD", destino: str = "CLIENTE",
         assunto: str = "", email_origem: str = "") -> dict:
    if not email_origem:
        email_origem = "teste@finaud.com.br" if origem == "FINAUD" else "teste@cliente.com.br"
    return {
        "contato_origem": {"lado": origem, "email": email_origem},
        "contato_destino": {"lado": destino,
                            "email": "teste@cliente.com.br" if destino == "CLIENTE" else "teste@finaud.com.br"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": assunto,
        "snippet": "",
        "data_email": "2026-01-10T10:00:00",
    }


def _thread(*msgs) -> dict:
    return {"mensagens": list(msgs), "threadId": "tid_test"}


def _ctx(ultima_msg=None, thread=None, texto_fio="", alvo="DDR4111") -> Contexto:
    return Contexto(
        tid="tid_test",
        thread=thread or _thread(),
        evento={"cadoc": alvo, "titulo": ""},
        ultima_msg=ultima_msg,
        texto_fio=texto_fio,
        alvo_triagem=alvo,
        dia_ref=None,
    )


# ===========================================================================
# DDR4111
# ===========================================================================
class TestDDR4111:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="arquivo transmitido no bacen com sucesso")
        assert ddr._det_transmitido_bacen(ctx)

    def test_transmitido_bacen_negativo(self):
        ctx = _ctx(texto_fio="aguardando retorno")
        assert not ddr._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o DDR.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th)
        assert ddr._det_sec5_remessa(ctx)

    def test_sec5_vetado_por_cf_substantiva(self):
        """§5 não dispara se última mensagem é C→F substantiva (não só agradecimento)."""
        remetente = _msg("Segue em anexo o DDR.")
        ult_cf = _msg("Segue os arquivos solicitados.", origem="CLIENTE", destino="FINAUD")
        th = _thread(remetente, ult_cf)
        ctx = _ctx(ultima_msg=ult_cf, thread=th)
        assert not ddr._det_sec5_remessa(ctx)

    def test_4e_ddr_agradecimento(self):
        """§4e DDR: cliente só agradece → concluir."""
        ult = _msg("Muito obrigado!", origem="CLIENTE", destino="FINAUD")
        ctx = _ctx(ultima_msg=ult)
        assert ddr._det_4e_ddr(ctx)

    def test_4e_ddr_nao_dispara_envio(self):
        # encaminh* veta reconhecimento curto
        ult = _msg("Obrigado! Segue em anexo o arquivo.", origem="CLIENTE", destino="FINAUD")
        ctx = _ctx(ultima_msg=ult)
        assert not ddr._det_4e_ddr(ctx)

    def test_3inv_pedido_insumos(self):
        ult = _msg("Por gentileza encaminhar o DDR.")
        ctx = _ctx(ultima_msg=ult)
        assert ddr._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto(self):
        msg_cf = _msg("Segue o arquivo.", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigado!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th)
        assert ddr._det_35_reconhecimento_curto(ctx)

    def test_ff_encaminhamento_sempre_true(self):
        ctx = _ctx()
        assert ddr._det_ff_encaminhamento(ctx)

    def test_3_insumo_cliente_sempre_true(self):
        ctx = _ctx()
        assert ddr._det_3_insumo_cliente(ctx)


# ===========================================================================
# DLO
# ===========================================================================
class TestDLO:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen ontem", alvo="DLO")
        assert dlo._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o DLO.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="DLO")
        assert dlo._det_sec5_remessa(ctx)

    def test_3inv_pedido_insumos(self):
        ult = _msg("Por gentileza encaminhar as posições DLO.")
        ctx = _ctx(ultima_msg=ult, alvo="DLO")
        assert dlo._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto(self):
        msg_cf = _msg("ok", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigado!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="DLO")
        assert dlo._det_35_reconhecimento_curto(ctx)

    def test_sec5_vetado_por_cf(self):
        remetente = _msg("Segue em anexo o DLO.")
        ult_cf = _msg("Arquivos em anexo.", origem="CLIENTE", destino="FINAUD")
        th = _thread(remetente, ult_cf)
        ctx = _ctx(ultima_msg=ult_cf, thread=th, alvo="DLO")
        assert not dlo._det_sec5_remessa(ctx)


# ===========================================================================
# DLI
# ===========================================================================
class TestDLI:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="enviados ao bacen hoje", alvo="DLI")
        assert dli._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o DLI.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="DLI")
        assert dli._det_sec5_remessa(ctx)

    def test_3inv_pedido_insumos(self):
        ult = _msg("Por gentileza encaminhar os arquivos DLI.")
        ctx = _ctx(ultima_msg=ult, alvo="DLI")
        assert dli._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_nao_dispara_sem_cf_previo(self):
        """DLI: §3.5 exige C→F prévio."""
        ult_fc = _msg("Obrigado!")
        th = _thread(ult_fc)  # nenhum C→F antes
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="DLI")
        assert not dli._det_35_reconhecimento_curto(ctx)


# ===========================================================================
# S5
# ===========================================================================
class TestS5:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen", alvo="S5")
        assert s5._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o S5.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="S5")
        assert s5._det_sec5_remessa(ctx)

    def test_35_plus_sem_cf_previo(self):
        """S5 tem §3.5+: F agradece sem C→F prévio → aguarda."""
        ult_fc = _msg("Obrigado pela sua colaboração!")
        th = _thread(ult_fc)  # sem C→F antes
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="S5")
        assert s5._det_35_plus_agradece_sem_cliente_previa(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Por gentileza encaminhar os dados S5.")
        ctx = _ctx(ultima_msg=ult, alvo="S5")
        assert s5._det_3inv_pedido_insumos_finaud(ctx)


# ===========================================================================
# SUPORTE
# ===========================================================================
class TestSUPORTE:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen", alvo="SUPORTE")
        assert sup._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o relatório.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="SUPORTE")
        assert sup._det_sec5_remessa(ctx)

    def test_4e_suporte_agradecimento(self):
        """§4e SUPORTE: cliente só agradece → concluir (diferente de DLO que não tem §4e)."""
        ult = _msg("Muito obrigado pela ajuda!", origem="CLIENTE", destino="FINAUD")
        ctx = _ctx(ultima_msg=ult, alvo="SUPORTE")
        assert sup._det_4e_suporte(ctx)

    def test_4e_suporte_nao_dispara_pergunta(self):
        ult = _msg("Obrigado! Como gero o relatório?", origem="CLIENTE", destino="FINAUD")
        ctx = _ctx(ultima_msg=ult, alvo="SUPORTE")
        assert not sup._det_4e_suporte(ctx)

    def test_fc_em_analise(self):
        ult = _msg("Estamos em análise, retornaremos em breve.")
        ctx = _ctx(ultima_msg=ult, alvo="SUPORTE")
        assert sup._det_sup_fc_em_analise(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Poderia encaminhar o comprovante?")
        ctx = _ctx(ultima_msg=ult, alvo="SUPORTE")
        assert sup._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_plus_sem_cf(self):
        ult = _msg("Obrigada!")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="SUPORTE")
        assert sup._det_35_plus_agradece_sem_cliente_previa(ctx)


# ===========================================================================
# DRSAC
# ===========================================================================
class TestDRSAC:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen", alvo="DRSAC")
        assert drsac._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o relatório DRSAC.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="DRSAC")
        assert drsac._det_sec5_remessa(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Por gentileza encaminhar o arquivo DRSAC.")
        ctx = _ctx(ultima_msg=ult, alvo="DRSAC")
        assert drsac._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto_com_cf(self):
        msg_cf = _msg("Recebido.", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigado!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="DRSAC")
        assert drsac._det_35_reconhecimento_curto(ctx)


# ===========================================================================
# FORCAPITAL
# ===========================================================================
class TestFORCAPITAL:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen", alvo="FORCAPITAL")
        assert fcp._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o arquivo FORCAPITAL.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="FORCAPITAL")
        assert fcp._det_sec5_remessa(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Por gentileza encaminhar os dados FORCAPITAL.")
        ctx = _ctx(ultima_msg=ult, alvo="FORCAPITAL")
        assert fcp._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto_com_cf(self):
        msg_cf = _msg("ok", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigada!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="FORCAPITAL")
        assert fcp._det_35_reconhecimento_curto(ctx)


# ===========================================================================
# RETORNO_BACEN
# ===========================================================================
class TestRETORNO_BACEN:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen com sucesso", alvo="RETORNO_BACEN")
        assert rb._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o relatório de retorno.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="RETORNO_BACEN")
        assert rb._det_sec5_remessa(ctx)

    def test_4f_rb_cliente_confirma_bacen(self):
        """§4f-rb exclusivo RETORNO_BACEN: cliente confirma que BACEN aceitou."""
        ult = _msg("O protocolo foi aceito pelo BACEN.", origem="CLIENTE", destino="FINAUD")
        ctx = _ctx(ultima_msg=ult, alvo="RETORNO_BACEN")
        assert rb._det_4f_rb_cliente_confirma_bacen(ctx)

    def test_4f_rb_nao_dispara_com_duvida(self):
        ult = _msg("O protocolo foi aceito, mas como proceder?", origem="CLIENTE", destino="FINAUD")
        ctx = _ctx(ultima_msg=ult, alvo="RETORNO_BACEN")
        assert not rb._det_4f_rb_cliente_confirma_bacen(ctx)

    def test_finaud_orientou_conclusivo(self):
        # _det_finaud_orientou_conclusivo busca última F→C dentro da thread
        ult = _msg("Para solucionar o problema, transmita como substituição.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="RETORNO_BACEN")
        assert rb._det_finaud_orientou_conclusivo(ctx)

    def test_finaud_orientou_veto_aguardamos(self):
        ult = _msg("Aguardamos retorno do BACEN para prosseguirmos.")
        ctx = _ctx(ultima_msg=ult, alvo="RETORNO_BACEN")
        assert not rb._det_finaud_orientou_conclusivo(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Por gentileza encaminhar o arquivo de crítica.")
        ctx = _ctx(ultima_msg=ult, alvo="RETORNO_BACEN")
        assert rb._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto(self):
        msg_cf = _msg("Recebido.", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigado!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="RETORNO_BACEN")
        assert rb._det_35_reconhecimento_curto(ctx)

    def test_rb_fc_em_analise(self):
        ult = _msg("Estamos analisando a crítica, retornaremos em breve.")
        ctx = _ctx(ultima_msg=ult, alvo="RETORNO_BACEN")
        assert rb._det_rb_fc_em_analise(ctx)

    def test_ff_encaminhamento(self):
        ctx = _ctx(alvo="RETORNO_BACEN")
        assert rb._det_ff_encaminhamento(ctx)

    def test_sec5b_res(self):
        ult = _msg("Conforme solicitado, segue o relatório.", assunto="RES: Crítica CRD - DDR")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="RETORNO_BACEN")
        assert rb._det_sec5b_res(ctx)

    def test_sec5c_corpo_conclusivo(self):
        ult = _msg("A opção já foi cadastrada com sucesso.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="RETORNO_BACEN")
        assert rb._det_sec5c_corpo_conclusivo(ctx)


# ===========================================================================
# DRM_2060  (estava sem nenhum teste — cobertura 0%)
# ===========================================================================
class TestDRM:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen", alvo="DRM_2060")
        assert drm._det_transmitido_bacen(ctx)

    def test_transmitido_bacen_negativo(self):
        ctx = _ctx(texto_fio="aguardando retorno do cliente", alvo="DRM_2060")
        assert not drm._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o DRM.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="DRM_2060")
        assert drm._det_sec5_remessa(ctx)

    def test_sec5_vetado_por_cf_substantiva(self):
        remetente = _msg("Segue em anexo o DRM.")
        ult_cf = _msg("Segue os arquivos solicitados para análise.",
                      origem="CLIENTE", destino="FINAUD")
        th = _thread(remetente, ult_cf)
        ctx = _ctx(ultima_msg=ult_cf, thread=th, alvo="DRM_2060")
        assert not drm._det_sec5_remessa(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Por gentileza encaminhar os dados do DRM.")
        ctx = _ctx(ultima_msg=ult, alvo="DRM_2060")
        assert drm._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto_com_cf(self):
        msg_cf = _msg("Recebido.", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigado!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="DRM_2060")
        assert drm._det_35_reconhecimento_curto(ctx)

    def test_35_plus_agradece_sem_cf_previo(self):
        ult = _msg("Obrigada pela colaboração!")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="DRM_2060")
        assert drm._det_35_plus_agradece_sem_cliente_previa(ctx)

    def test_fc_em_analise_corpo_longo(self):
        ult = _msg("Estamos analisando o material recebido e retornaremos em breve.")
        ctx = _ctx(ultima_msg=ult, alvo="DRM_2060")
        assert drm._det_fc_fc_em_analise(ctx)

    def test_fc_em_analise_corpo_curto_negativo(self):
        ult = _msg("ok")
        ctx = _ctx(ultima_msg=ult, alvo="DRM_2060")
        assert not drm._det_fc_fc_em_analise(ctx)

    def test_ff_encaminhamento_sempre_true(self):
        assert drm._det_ff_encaminhamento(_ctx(alvo="DRM_2060"))

    def test_3_insumo_cliente_sempre_true(self):
        assert drm._det_3_insumo_cliente(_ctx(alvo="DRM_2060"))


# ===========================================================================
# CADOC 6209  (estava sem nenhum teste — cobertura 0%)
# ===========================================================================
class TestCADOC6209:
    def test_transmitido_bacen(self):
        ctx = _ctx(texto_fio="transmitido no bacen", alvo="6209")
        assert c6209._det_transmitido_bacen(ctx)

    def test_transmitido_bacen_negativo(self):
        ctx = _ctx(texto_fio="aguardando posição do cliente", alvo="6209")
        assert not c6209._det_transmitido_bacen(ctx)

    def test_sec5_remessa(self):
        ult = _msg("Segue em anexo o CADOC 6209.")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="6209")
        assert c6209._det_sec5_remessa(ctx)

    def test_sec5_vetado_por_cf_substantiva(self):
        remetente = _msg("Segue em anexo o CADOC 6209.")
        ult_cf = _msg("Segue os arquivos solicitados para conferência.",
                      origem="CLIENTE", destino="FINAUD")
        th = _thread(remetente, ult_cf)
        ctx = _ctx(ultima_msg=ult_cf, thread=th, alvo="6209")
        assert not c6209._det_sec5_remessa(ctx)

    def test_3inv_pedido(self):
        ult = _msg("Por gentileza encaminhar os dados do 6209.")
        ctx = _ctx(ultima_msg=ult, alvo="6209")
        assert c6209._det_3inv_pedido_insumos_finaud(ctx)

    def test_35_reconhecimento_curto_com_cf(self):
        msg_cf = _msg("Recebido.", origem="CLIENTE", destino="FINAUD")
        ult_fc = _msg("Obrigado!")
        th = _thread(msg_cf, ult_fc)
        ctx = _ctx(ultima_msg=ult_fc, thread=th, alvo="6209")
        assert c6209._det_35_reconhecimento_curto(ctx)

    def test_35_plus_agradece_sem_cf_previo(self):
        ult = _msg("Obrigada pela colaboração!")
        th = _thread(ult)
        ctx = _ctx(ultima_msg=ult, thread=th, alvo="6209")
        assert c6209._det_35_plus_agradece_sem_cliente_previa(ctx)

    def test_fc_em_analise_corpo_longo(self):
        ult = _msg("Estamos analisando o material recebido e retornaremos em breve.")
        ctx = _ctx(ultima_msg=ult, alvo="6209")
        assert c6209._det_6209_fc_em_analise(ctx)

    def test_fc_em_analise_corpo_curto_negativo(self):
        ult = _msg("ok")
        ctx = _ctx(ultima_msg=ult, alvo="6209")
        assert not c6209._det_6209_fc_em_analise(ctx)

    def test_ff_encaminhamento_sempre_true(self):
        assert c6209._det_ff_encaminhamento(_ctx(alvo="6209"))

    def test_3_insumo_cliente_sempre_true(self):
        assert c6209._det_3_insumo_cliente(_ctx(alvo="6209"))


# ---------------------------------------------------------------------------
# _exclui_pergunta_social e _cliente_agradecimento_conclusivo (helpers.py)
# P-AUD-04: bug de perguntas sociais ("e você?", "tudo bem?") vetando agradecimentos
# ---------------------------------------------------------------------------
from triagem.helpers import (
    _exclui_pergunta_social,
    _cliente_agradecimento_conclusivo,
    _cliente_confirmou_solicitacao,
    _ff_comunicado_interno,
    _finaud_entrega_conclusiva,
    _finaud_instruiu_cliente,
)


class TestExcluiPerguntaSocial:
    def test_e_voce_excluido(self):
        assert _exclui_pergunta_social("Muito obrigada e você?")

    def test_tudo_bem_excluido(self):
        assert _exclui_pergunta_social("Tudo bem? Obrigado pelo auxílio.")

    def test_tudo_e_voce_excluido(self):
        assert _exclui_pergunta_social("Boa tarde, tudo e você? Obrigada!!")

    def test_pergunta_real_nao_excluida(self):
        assert not _exclui_pergunta_social("Vocês conseguem reprocessar até quando?")

    def test_pergunta_mista_nao_excluida(self):
        assert not _exclui_pergunta_social("E você, sabe até quando fica pendente?")


def _msg_cliente(corpo: str) -> dict:
    return {
        "contato_origem": {"lado": "CLIENTE", "email": "c@cliente.com"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": "",
        "snippet": "",
        "data_email": "2026-01-10T10:00:00",
    }


class TestClienteAgradecimentoConclusivoBugs:
    def test_codepe_tudo_bem_e_obrigada(self):
        """Bug 2: 'e você?' vetava agradecimento real da Codepe."""
        msg = _msg_cliente("Andrea, bom dia! Eu estou bem e você? Muito obrigada e uma ótima quarta-feira.")
        assert _cliente_agradecimento_conclusivo(msg)

    def test_bacen_retorno_tudo_bem(self):
        """Bug 2: 'tudo bem?' vetava agradecimento do BACEN."""
        msg = _msg_cliente("Boa tarde, Andrea, tudo bem? Perfeito. Rotina executada. Muito obrigado pelo auxílio.")
        assert _cliente_agradecimento_conclusivo(msg)

    def test_emojis_duplo_interrogacao_nao_veta(self):
        """Bug 1: emojis codificados como '??' não devem vetar agradecimento."""
        msg = _msg_cliente("Pedro, Que bom. ?? Entendi, muito obrigada pela sua ajuda.")
        assert _cliente_agradecimento_conclusivo(msg)

    def test_western_union_anexo_dados_e_falso_positivo(self):
        """Anti-FP: 'Anexo os dados...' com 'Obrigado' ao final não é agradecimento conclusivo."""
        msg = _msg_cliente("Prezados, tudo bem? Anexo os dados para reporte de DRL 01/2026. Obrigado!")
        assert not _cliente_agradecimento_conclusivo(msg)

    def test_wise_considere_valores_e_falso_positivo(self):
        """Anti-FP: cliente enviando dados DDR sem agradecimento real."""
        msg = _msg_cliente("Bom dia, Lucas Tudo bem? Considere os valores a seguir para o DDR do dia 05/05: USD 4517940")
        assert not _cliente_agradecimento_conclusivo(msg)

    def test_finaud_lado_nao_dispara(self):
        """Lado FINAUD não é cliente — deve retornar False."""
        msg = {"contato_origem": {"lado": "FINAUD", "email": "f@finaud.com"}, "corpo_limpo": "Muito obrigado!", "corpo": "Muito obrigado!"}
        assert not _cliente_agradecimento_conclusivo(msg)


# ---------------------------------------------------------------------------
# _cliente_confirmou_solicitacao (helpers.py) — P-AUD-02
# Detecta cliente confirmando que executou a ação pedida pela Finaud
# ---------------------------------------------------------------------------
class TestClienteConfirmouSolicitacao:
    def test_processo_efetuado_reenviado(self):
        """Caso real Iguá Corretora: 'Processo efetuado e reenviado o arquivo'."""
        msg = _msg_cliente("Processo efetuado e reenviado o arquivo Iguá Corretora de Cambio")
        assert _cliente_confirmou_solicitacao(msg)

    def test_arquivo_enviado_na_data_de_hoje(self):
        """Caso real Banvox: 'Arquivo enviado na data de hoje (13/04/2026)'."""
        msg = _msg_cliente("Lucas, bom dia! Espero que esteja bem. Arquivo enviado na data de hoje (13/04/2026).")
        assert _cliente_confirmou_solicitacao(msg)

    def test_realizado_conforme_solicitado(self):
        msg = _msg_cliente("Realizado conforme solicitado.")
        assert _cliente_confirmou_solicitacao(msg)

    def test_foi_reprocessado(self):
        msg = _msg_cliente("O arquivo foi reprocessado e reenviado ao sistema.")
        assert _cliente_confirmou_solicitacao(msg)

    def test_segue_em_anexo_nao_dispara(self):
        """Anti-FP: entrega de dado ('segue em anexo') não é confirmação de execução."""
        msg = _msg_cliente("Prezados, segue em anexo o arquivo DLO conforme solicitado. Obrigado!")
        assert not _cliente_confirmou_solicitacao(msg)

    def test_seguem_os_documentos_nao_dispara(self):
        """Anti-FP: 'Seguem os documentos' é entrega de dado, não confirmação."""
        msg = _msg_cliente("Bom dia! Seguem os documentos conforme solicitado.")
        assert not _cliente_confirmou_solicitacao(msg)

    def test_pedido_embutido_nao_dispara(self):
        """Anti-FP: mensagem com pedido não é confirmação conclusiva."""
        msg = _msg_cliente("Processo efetuado. Peço que verifique se está correto.")
        assert not _cliente_confirmou_solicitacao(msg)

    def test_finaud_nao_dispara(self):
        """Lado FINAUD não é cliente."""
        msg = {"contato_origem": {"lado": "FINAUD"}, "corpo_limpo": "Processo efetuado e reenviado.", "corpo": ""}
        assert not _cliente_confirmou_solicitacao(msg)


def _msg_finaud(corpo: str) -> dict:
    return {
        "contato_origem": {"lado": "FINAUD", "email": "f@finaud.com.br"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": "",
        "data_email": "2026-01-10T10:00:00",
    }


# ---------------------------------------------------------------------------
# _ff_comunicado_interno (helpers.py) — P-AUD-07
# Detecta e-mails F→F informativos sem demanda de resposta
# ---------------------------------------------------------------------------
class TestFfComunicadoInterno:
    def test_gerado_automaticamente_monitoramento(self):
        """Caso real: alerta 'Nenhum documento novo... gerado automaticamente pelo sistema de monitoramento'."""
        msg = _msg_finaud("Nenhum documento novo ou alterado foi identificado. Este e-mail foi gerado automaticamente pelo sistema de monitoramento FINAUD TEC.")
        assert _ff_comunicado_interno(msg, "Atualização na página de Leiautes do Bacen")

    def test_assunto_teste(self):
        """Caso real: assunto 'teste', corpo 'Riscos'."""
        msg = _msg_finaud("Riscos")
        assert _ff_comunicado_interno(msg, "teste")

    def test_13_salario_adiantamento(self):
        """Comunicado de RH sobre adiantamento do 13º salário."""
        msg = _msg_finaud("Informo sobre a possibilidade de adiantamento da 1ª parcela do 13º salário referente ao exercício de 2026.")
        assert _ff_comunicado_interno(msg, "Adiantamento do 13º Salário")

    def test_mega_sena_social(self):
        """E-mail social/pessoal — bolão da Mega Sena sem pergunta aberta."""
        msg = _msg_finaud("Pessoal, organizei o bolão da Mega Sena desta semana. Participação R$20.")
        assert _ff_comunicado_interno(msg, "Bolão da semana")

    def test_mega_sena_com_pergunta_nao_dispara(self):
        """Anti-FP: bolão com '?' — anti-FP bloqueia (caso real: 'Dá tempo de entrar ainda?')."""
        msg = _msg_finaud("Dá tempo de entrar ainda?")
        assert not _ff_comunicado_interno(msg, "RE: 30 ANOS DA MEGA SENA")

    def test_divulgacao_interna_finaud_norma(self):
        """Caso real: distribuição interna de norma regulatória (IN BCB 718)."""
        msg = _msg_finaud("Divulgação interna Finaud. Instrução Normativa BCB nº 718. Informamos que o Banco Central publicou...")
        assert _ff_comunicado_interno(msg, "Divulgação interna Finaud - Nova regulamentação")

    def test_centralizacao_ti(self):
        """Caso real: comunicado de infraestrutura de TI."""
        msg = _msg_finaud("Prezados, solicitamos que todas as solicitações de suporte sejam enviadas via e-mail.")
        assert _ff_comunicado_interno(msg, "Centralização das Solicitações de Suporte de Infraestrutura")

    def test_pedido_nao_dispara(self):
        """Anti-FP: mensagem com pedido ('por gentileza verificar') não é comunicado puro."""
        msg = _msg_finaud("@Rodrigo Tiberio, por gentileza verificar o motivo da divergência.")
        assert not _ff_comunicado_interno(msg, "Fwd: DLO - Verificar")

    def test_pergunta_nao_dispara(self):
        """Anti-FP: mensagem com '?' não é comunicado puro."""
        msg = _msg_finaud("Dá tempo de entrar ainda?")
        assert not _ff_comunicado_interno(msg, "RE: 30 ANOS DA MEGA SENA")

    def test_cliente_lado_nao_dispara(self):
        """Anti-FP: remetente CLIENTE — função exige FINAUD."""
        msg = _msg_cliente("Este e-mail foi gerado automaticamente pelo sistema de monitoramento FINAUD.")
        assert not _ff_comunicado_interno(msg, "Monitoramento")


# ---------------------------------------------------------------------------
# _finaud_entrega_conclusiva — novos padrões P-AUD-08 (2026-06-29)
# ---------------------------------------------------------------------------
class TestFinaudEntregaConclusivaPAud08:
    def test_enviando_em_anexo_projecao(self):
        """Caso real Fourtrade: Rodrigo enviou projeção de capital via 'enviando em anexo'."""
        msg = _msg_finaud("Bom dia Erivelto, Estamos enviando em anexo a projeção de capital sem o enquadramento do PL requerido pela nova norma.")
        assert _finaud_entrega_conclusiva(msg)

    def test_compartilhar_detalhes_estimativa(self):
        """Caso real CVPar: Rodrigo compartilhou detalhes da estimativa de projeções financeiras."""
        msg = _msg_finaud("Olá, Gostaria de compartilhar os detalhes da estimativa aplicada para as projeções financeiras, conforme o cronograma e premissas abaixo.")
        assert _finaud_entrega_conclusiva(msg)

    def test_enviando_em_anexo_cliente_nao_dispara(self):
        """Anti-FP: 'enviando em anexo' de CLIENTE não deve disparar (exige FINAUD)."""
        msg = _msg_cliente("Boa tarde, estamos enviando em anexo os documentos solicitados.")
        assert not _finaud_entrega_conclusiva(msg)


# ---------------------------------------------------------------------------
# _finaud_instruiu_cliente — novo padrão P-AUD-01 (2026-06-29)
# ---------------------------------------------------------------------------
class TestFinaudInstruiuClientePAud01:
    def test_habilitar_sta_autran(self):
        """Caso real Guru CTVM: Andrea instrui Felipe a habilitar DDR no STA via Autran."""
        msg = _msg_finaud(
            "O código da remessa não aparece habilitado na tela de envio do STA. "
            "Para efetuar a habilitação, o Máster, por meio do sistema Autran e dos grupos "
            "STRA1300 e STRA1310, poderá efetuar a autorização."
        )
        assert _finaud_instruiu_cliente(msg)

    def test_habilitar_slim800(self):
        """Variante com referência SLIM800 em vez de Autran."""
        msg = _msg_finaud(
            "Para efetuar a habilitação da transação, acesse o SLIM800 no STA "
            "e autorize o usuário responsável."
        )
        assert _finaud_instruiu_cliente(msg)

    def test_habilitar_sem_sta_nao_dispara(self):
        """Anti-FP: habilitação mencionada sem STA/Autran/SLIM800 não deve disparar."""
        msg = _msg_finaud("Para efetuar a habilitação, entre em contato com o suporte interno.")
        assert not _finaud_instruiu_cliente(msg)
