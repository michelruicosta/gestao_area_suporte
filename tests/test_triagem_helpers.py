# -*- coding: utf-8 -*-
"""
Testes unitários para scripts/triagem/helpers.py

Cobre os detectores mais críticos: §5 (remessa), §3-inv (pedido insumos),
§4d (agradecimento pós-remessa), §3.5 (F agradecimento), §4f-rb (cliente
confirma BACEN), _finaud_entrega_conclusiva, _finaud_instruiu_cliente,
_cliente_agradecimento_conclusivo.

Cada teste usa dicts mínimos — não carrega JSON do pipeline.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from triagem.helpers import (
    _sec5_remessa_finaud,
    _finaud_pedido_insumos_a_cliente,
    _cliente_somente_reconhecimento_curto_pos_remessa,
    _finaud_somente_reconhecimento_curto,
    _cliente_confirma_protocolo_aceito_bacen,
    _finaud_entrega_conclusiva,
    _finaud_instruiu_cliente,
    _finaud_agendou_reuniao,
    _cliente_agradecimento_conclusivo,
    _sec5b_res_finaud_cliente,
    _sec5c_finaud_corpo_conclusivo,
    _transmitido_bacen,
    get_mensagens_efetivas,
)


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------
def _msg(corpo: str, origem: str = "FINAUD", destino: str = "CLIENTE",
         assunto: str = "", snippet: str = "") -> dict:
    return {
        "contato_origem": {"lado": origem, "email": f"teste@{'finaud.com.br' if origem == 'FINAUD' else 'cliente.com.br'}"},
        "contato_destino": {"lado": destino, "email": f"teste@{'cliente.com.br' if destino == 'CLIENTE' else 'finaud.com.br'}"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": assunto,
        "snippet": snippet,
    }


def _thread(*msgs) -> dict:
    return {"mensagens": list(msgs)}


# ---------------------------------------------------------------------------
# _transmitido_bacen
# ---------------------------------------------------------------------------
def test_transmitido_bacen_positivo():
    assert _transmitido_bacen("arquivo transmitido no Bacen com sucesso")
    assert _transmitido_bacen("enviados ao BACEN")
    assert _transmitido_bacen("transmitido no bc em 2026-01")

def test_transmitido_bacen_negativo():
    assert not _transmitido_bacen("aguardando retorno do cliente")
    assert not _transmitido_bacen("Por gentileza encaminhar o DDR")


# ---------------------------------------------------------------------------
# _sec5_remessa_finaud (§5)
# ---------------------------------------------------------------------------
def test_sec5_remessa_segue_anexo():
    m = _msg("Segue em anexo o arquivo DLO conforme solicitado.")
    assert _sec5_remessa_finaud(m)

def test_sec5_remessa_encaminh_anexo():
    m = _msg("Encaminho em anexo os documentos solicitados.")
    assert _sec5_remessa_finaud(m)

def test_sec5_remessa_nao_dispara_para_cliente():
    m = _msg("Segue em anexo o arquivo.", origem="CLIENTE", destino="FINAUD")
    assert not _sec5_remessa_finaud(m)

def test_sec5_remessa_pedido_insumos_veta():
    """Se o texto é pedido de insumos, §5 não deve disparar."""
    m = _msg("Por gentileza encaminhar os arquivos DLO para cálculo. Segue em anexo o modelo.")
    # "por gentileza encaminhar" veta §5 mesmo com "segue em anexo"
    assert not _sec5_remessa_finaud(m)

def test_sec5_sem_segue():
    m = _msg("Bom dia, retornaremos em breve.")
    assert not _sec5_remessa_finaud(m)


# ---------------------------------------------------------------------------
# _finaud_pedido_insumos_a_cliente (§3-inv)
# ---------------------------------------------------------------------------
def test_pedido_insumos_por_gentileza():
    m = _msg("Por gentileza encaminhar o arquivo DDR.")
    assert _finaud_pedido_insumos_a_cliente(m)

def test_pedido_insumos_poderia_encaminhar():
    m = _msg("Poderia encaminhar as posições COSIF?")
    assert _finaud_pedido_insumos_a_cliente(m)

def test_pedido_insumos_nao_dispara_cliente():
    m = _msg("Por gentileza encaminhar.", origem="CLIENTE", destino="FINAUD")
    assert not _finaud_pedido_insumos_a_cliente(m)

def test_pedido_insumos_nao_quando_remessa():
    m = _msg("Segue em anexo o DDR.")
    assert not _finaud_pedido_insumos_a_cliente(m)


# ---------------------------------------------------------------------------
# _sec5b_res_finaud_cliente
# ---------------------------------------------------------------------------
def test_sec5b_res_assunto():
    m = _msg("Conforme conversado, segue o relatório.", assunto="RES: DDR 2011 – Janeiro")
    assert _sec5b_res_finaud_cliente(m)

def test_sec5b_sem_res():
    m = _msg("Conforme conversado, segue o relatório.", assunto="DDR 2011")
    assert not _sec5b_res_finaud_cliente(m)

def test_sec5b_corpo_muito_curto():
    m = _msg("Ok.", assunto="RES: DDR")
    assert not _sec5b_res_finaud_cliente(m)


# ---------------------------------------------------------------------------
# _sec5c_finaud_corpo_conclusivo
# ---------------------------------------------------------------------------
def test_sec5c_cadastrado():
    m = _msg("A opção já foi cadastrada com sucesso no sistema.")
    assert _sec5c_finaud_corpo_conclusivo(m)

def test_sec5c_encerrado():
    m = _msg("Encerramos por aqui. Qualquer dúvida estamos à disposição.")
    assert _sec5c_finaud_corpo_conclusivo(m)

def test_sec5c_nao_dispara_cliente():
    m = _msg("A opção já foi cadastrada.", origem="CLIENTE", destino="FINAUD")
    assert not _sec5c_finaud_corpo_conclusivo(m)


# ---------------------------------------------------------------------------
# _finaud_entrega_conclusiva
# ---------------------------------------------------------------------------
def test_entrega_aceito_sta():
    m = _msg("Arquivo aceito no STA. Segue protocolo em anexo.")
    assert _finaud_entrega_conclusiva(m)

def test_entrega_transmitido():
    m = _msg("Remessa DDR_2011 transmitida ao Banco Central com sucesso.")
    assert _finaud_entrega_conclusiva(m)

def test_entrega_feito():
    m = _msg("Feito. Qualquer dúvida estamos à disposição.")
    assert _finaud_entrega_conclusiva(m)

def test_entrega_nao_dispara_cliente():
    m = _msg("Arquivo aceito no STA.", origem="CLIENTE", destino="FINAUD")
    assert not _finaud_entrega_conclusiva(m)

def test_entrega_veto_providenciarmos():
    m = _msg("Para que providenciarmos o reset, precisamos de confirmação.")
    assert not _finaud_entrega_conclusiva(m)


# ---------------------------------------------------------------------------
# _finaud_instruiu_cliente
# ---------------------------------------------------------------------------
def test_instruiu_para_solucionar():
    m = _msg("Para solucionar a crítica, transmita o arquivo como Substituição.")
    assert _finaud_instruiu_cliente(m)

def test_instruiu_responda_crd():
    m = _msg("Por favor, responda via CRD indicando a correção realizada.")
    assert _finaud_instruiu_cliente(m)

def test_instruiu_veto_aguardamos():
    m = _msg("Para solucionar, precisamos aguardamos retorno do BACEN.")
    assert not _finaud_instruiu_cliente(m)

def test_instruiu_veto_estamos_acompanhando():
    m = _msg("Estamos acompanhando o processo.")
    assert not _finaud_instruiu_cliente(m)

def test_instruiu_nao_dispara_cliente():
    m = _msg("Para solucionar, transmita como Substituição.", origem="CLIENTE", destino="FINAUD")
    assert not _finaud_instruiu_cliente(m)


# ---------------------------------------------------------------------------
# _cliente_agradecimento_conclusivo
# ---------------------------------------------------------------------------
def test_agradecimento_conclusivo_obrigado():
    m = _msg("Muito obrigado pela ajuda!", origem="CLIENTE", destino="FINAUD")
    assert _cliente_agradecimento_conclusivo(m)

def test_agradecimento_conclusivo_deu_certo():
    m = _msg("Deu certo! Obrigado.", origem="CLIENTE", destino="FINAUD")
    assert _cliente_agradecimento_conclusivo(m)

def test_agradecimento_nao_dispara_com_pergunta():
    m = _msg("Obrigado! Mas como faço para gerar o DLO?", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_agradecimento_conclusivo(m)

def test_agradecimento_nao_dispara_com_envio():
    m = _msg("Obrigado! Segue em anexo o arquivo.", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_agradecimento_conclusivo(m)

def test_agradecimento_nao_dispara_finaud():
    m = _msg("Obrigado!", origem="FINAUD", destino="CLIENTE")
    assert not _cliente_agradecimento_conclusivo(m)

def test_agradecimento_nao_dispara_corpo_longo_com_solicitacao():
    # Corpo longo com solicitação embutida → veto ativo mesmo com agradecimento
    corpo = "Obrigado pela ajuda! " + "Solicito por favor que verifique o arquivo " * 15
    m = _msg(corpo, origem="CLIENTE", destino="FINAUD")
    assert not _cliente_agradecimento_conclusivo(m)

def test_agradecimento_dispara_com_assinatura_corporativa():
    # Corpo longo mas agradecimento está nos primeiros 150 chars antes de assinatura corporativa
    corpo = "Obrigado Flávio!\n\nRaphael Marino\nManager | Risk\n+55 11 99999-0000\nraphael@empresa.com\nEmpresa Corretora S.A.\nRua Hungria, 1400, São Paulo\n" * 5
    m = _msg(corpo, origem="CLIENTE", destino="FINAUD")
    assert _cliente_agradecimento_conclusivo(m)

def test_agradecimento_valeu_simples():
    # "Valeu!" é agradecimento conclusivo — caso real: Monte Bravo após "já foi cadastrada"
    m = _msg("Valeu!", origem="CLIENTE", destino="FINAUD")
    assert _cliente_agradecimento_conclusivo(m)

def test_agradecimento_valeu_com_nome():
    m = _msg("Valeu Flavio! Ótima terça.", origem="CLIENTE", destino="FINAUD")
    assert _cliente_agradecimento_conclusivo(m)

def test_agradecimento_valeu_nao_dispara_com_pergunta():
    m = _msg("Valeu! Mas como faço para gerar o DLO?", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_agradecimento_conclusivo(m)

def test_agradecimento_valeu_nao_dispara_com_envio():
    m = _msg("Valeu! Segue em anexo o arquivo.", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_agradecimento_conclusivo(m)

def test_agradecimento_valeu_nao_dispara_finaud():
    # "Valeu" enviado pela Finaud não é agradecimento do cliente
    m = _msg("Valeu!", origem="FINAUD", destino="CLIENTE")
    assert not _cliente_agradecimento_conclusivo(m)


# ---------------------------------------------------------------------------
# _cliente_confirma_protocolo_aceito_bacen (§4f-rb)
# ---------------------------------------------------------------------------
def test_confirma_protocolo_aceito():
    m = _msg("O protocolo foi aceito pelo BACEN.", origem="CLIENTE", destino="FINAUD")
    assert _cliente_confirma_protocolo_aceito_bacen(m)

def test_confirma_bacen_aceitou():
    m = _msg("O BACEN aceitou o arquivo enviado!", origem="CLIENTE", destino="FINAUD")
    assert _cliente_confirma_protocolo_aceito_bacen(m)

def test_confirma_nao_dispara_com_duvida():
    m = _msg("O protocolo foi aceito, mas como faço para verificar?", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_confirma_protocolo_aceito_bacen(m)

def test_confirma_nao_dispara_finaud():
    m = _msg("Protocolo aceito pelo BACEN.", origem="FINAUD", destino="CLIENTE")
    assert not _cliente_confirma_protocolo_aceito_bacen(m)


# ---------------------------------------------------------------------------
# _finaud_somente_reconhecimento_curto (§3.5)
# ---------------------------------------------------------------------------
def test_sec35_obrigado_curto():
    thread = _thread(
        _msg("Por gentileza encaminhar o DDR.", origem="CLIENTE", destino="FINAUD"),
    )
    m = _msg("Obrigado!")
    assert _finaud_somente_reconhecimento_curto(m, thread)

def test_sec35_nao_dispara_sem_cliente():
    thread = _thread()
    m = _msg("Obrigado!")
    assert not _finaud_somente_reconhecimento_curto(m, thread)

def test_sec35_nao_dispara_corpo_longo():
    thread = _thread(_msg("ok", origem="CLIENTE", destino="FINAUD"))
    m = _msg("Obrigado pela sua colaboração! " + "texto " * 30)  # > 160 chars
    assert not _finaud_somente_reconhecimento_curto(m, thread)


# ---------------------------------------------------------------------------
# _cliente_somente_reconhecimento_curto_pos_remessa (§4d)
# ---------------------------------------------------------------------------
def test_sec4d_agradecimento_curto():
    m = _msg("Muito obrigado!", origem="CLIENTE", destino="FINAUD")
    assert _cliente_somente_reconhecimento_curto_pos_remessa(m)

def test_sec4d_nao_dispara_com_envio():
    m = _msg("Obrigado! Segue em anexo o arquivo.", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_somente_reconhecimento_curto_pos_remessa(m)

def test_sec4d_nao_dispara_com_pergunta():
    m = _msg("Obrigado! Tem como verificar o prazo?", origem="CLIENTE", destino="FINAUD")
    assert not _cliente_somente_reconhecimento_curto_pos_remessa(m)

def test_sec4d_nao_dispara_finaud():
    m = _msg("Obrigado!", origem="FINAUD", destino="CLIENTE")
    assert not _cliente_somente_reconhecimento_curto_pos_remessa(m)


# ---------------------------------------------------------------------------
# get_mensagens_efetivas — encaminhados expandidos
# ---------------------------------------------------------------------------
def test_get_mensagens_efetivas_sem_encaminhados():
    msgs = [_msg("Texto A"), _msg("Texto B", origem="CLIENTE", destino="FINAUD")]
    resultado = get_mensagens_efetivas(msgs)
    assert len(resultado) == 2

def test_get_mensagens_efetivas_expande_encaminhados():
    msg_com_enc = _msg("Resposta Finaud.")
    msg_com_enc["encaminhados"] = [
        {"de": "cliente@empresa.com", "corpo": "Mensagem original do cliente.", "data_email": "2026-01-10T10:00:00"}
    ]
    resultado = get_mensagens_efetivas([msg_com_enc])
    # deve ter a mensagem virtual + a original
    assert len(resultado) == 2
    assert resultado[0].get("_virtual") is True
    assert resultado[1] == msg_com_enc


# ---------------------------------------------------------------------------
# _finaud_instruiu_cliente — Sinal K (adicionado 2026-06-27)
# "para solucionar... precisará/deverá + verbo" — padrão Azumidtvm RETORNO_BACEN
# ---------------------------------------------------------------------------
def test_finaud_instruiu_cliente_sinal_k_precisara_seguir():
    """'para solucionar... precisará seguir' deve ser detectado como instrução conclusiva."""
    corpo = (
        "Para solucionar a crítica em específico precisará seguir as orientações "
        "do e-mail anterior iniciando com a importação da mesma versão do COS4010 "
        "transmitida e aceita pelo BC. Qualquer dúvida retorne à disposição."
    )
    assert _finaud_instruiu_cliente(_msg(corpo)) is True


def test_finaud_instruiu_cliente_sinal_k_devera_corrigir():
    """'para solucionar... deverá corrigir' também deve ser detectado."""
    corpo = "Para solucionar o problema deverá corrigir o arquivo antes de retransmitir."
    assert _finaud_instruiu_cliente(_msg(corpo)) is True


# ---------------------------------------------------------------------------
# _finaud_agendou_reuniao (criado 2026-06-27)
# Casos confirmados: Saygogroup DDR_2011 e BGC FORCAPITAL
# ---------------------------------------------------------------------------
def test_finaud_agendou_reuniao_horarios_sugeridos():
    """'pode ser nos horários sugeridos... à disposição' deve ser detectado."""
    corpo = "Prezado Murillo, boa tarde. Certo, então pode ser nos horários sugeridos das 17 hrs ou 17:30 hrs. À disposição."
    assert _finaud_agendou_reuniao(_msg(corpo)) is True


def test_finaud_agendou_reuniao_pode_enviar_convite():
    """'Sim tenho, pode enviar o convite' deve ser detectado."""
    corpo = "Sim tenho, pode enviar o convite por favor"
    assert _finaud_agendou_reuniao(_msg(corpo)) is True


def test_finaud_agendou_reuniao_podemos_agendar_sim():
    """'Podemos agendar sim' deve ser detectado."""
    corpo = "Podemos agendar sim! alguma sugestão de agenda?"
    assert _finaud_agendou_reuniao(_msg(corpo)) is True


def test_finaud_agendou_reuniao_veto_aguardamos():
    """Presença de 'aguardamos' cancela detecção de reunião agendada."""
    corpo = "Podemos agendar sim, aguardamos sua confirmação do horário."
    assert _finaud_agendou_reuniao(_msg(corpo)) is False


def test_finaud_agendou_reuniao_nao_dispara_para_cliente():
    """Mensagem do CLIENTE confirmando reunião não deve ser detectada."""
    corpo = "Pode ser nos horários sugeridos, obrigado."
    assert _finaud_agendou_reuniao(_msg(corpo, origem="CLIENTE")) is False


# ---------------------------------------------------------------------------
# tem_anexo_cadoc — detecção de entrega por nome de arquivo
# ---------------------------------------------------------------------------

from triagem.helpers import tem_anexo_cadoc


def _msg_com_anexo(nome_original):
    return {"anexos_detectados": [{"nome_original": nome_original, "nome": nome_original.lower()}]}


def test_tem_anexo_cadoc_ddr_zip():
    """ZIP com '2011' no nome → detectado como DDR_2011."""
    msg = _msg_com_anexo("21040668_2011_20260701_I_1.zip")
    assert tem_anexo_cadoc(msg, "DDR_2011") is True


def test_tem_anexo_cadoc_4111_zip():
    """ZIP com '4111' no nome → detectado como 4111."""
    msg = _msg_com_anexo("21040668_4111_20260701_I_1.zip")
    assert tem_anexo_cadoc(msg, "4111") is True


def test_tem_anexo_cadoc_s5_pdf():
    """PDF com 'quantitativo' no nome → detectado como S5."""
    msg = _msg_com_anexo("Relatorio Quantitativo por Periodo - S5.pdf")
    assert tem_anexo_cadoc(msg, "S5") is True


def test_tem_anexo_cadoc_s5_xlsx():
    """Excel com 'quantitativo' no nome → detectado como S5."""
    msg = _msg_com_anexo("RelatorioQuantitativoPeriodo.xlsx")
    assert tem_anexo_cadoc(msg, "S5") is True


def test_tem_anexo_cadoc_s5_nao_dispara_para_balancete():
    """PDF de balancete não deve ser detectado como S5 (não tem 'quantitativo')."""
    msg = _msg_com_anexo("BALANCETE 02 07 2026 - BANCO.pdf")
    assert tem_anexo_cadoc(msg, "S5") is False


def test_tem_anexo_cadoc_s5_pdf_nao_detecta_outros_cadocs():
    """PDF de S5 não deve disparar para DDR_2011."""
    msg = _msg_com_anexo("Relatorio Quantitativo por Periodo - S5.pdf")
    assert tem_anexo_cadoc(msg, "DDR_2011") is False


def test_tem_anexo_cadoc_cadoc_desconhecido_retorna_false():
    """CADOC sem termos mapeados → sempre False."""
    msg = _msg_com_anexo("qualquer_arquivo.zip")
    assert tem_anexo_cadoc(msg, "FORCAPITAL") is False
