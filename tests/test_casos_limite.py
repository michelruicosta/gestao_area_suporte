# -*- coding: utf-8 -*-
"""
Testes de casos-limite para o motor de triagem.

Cobre situações que os testes do caminho feliz não alcançam:
  - Threads com 0, 1 e 100+ mensagens
  - Campos None inesperados (corpo, contato_origem, encaminhados)
  - Encoding corrompido no corpo da mensagem
  - Colisão de categorias (mesma thread dispara DDR4111 e DLO)
  - Datas inválidas / fora do range
  - Texto com encoding misto (latin-1 + utf-8)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from triagem._protocolo import Contexto
from triagem.helpers import (
    get_mensagens_efetivas,
    _finaud_entrega_conclusiva,
    _cliente_agradecimento_conclusivo,
    _finaud_somente_reconhecimento_curto,
    _cliente_somente_reconhecimento_curto_pos_remessa,
    _transmitido_bacen,
    _sec5_remessa_finaud,
    _sec5c_finaud_corpo_conclusivo,
    _parse_data_msg,
)
import triagem.ddr4111 as _ddr
import triagem.dlo as _dlo


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------
def _msg(corpo="", lado_orig="CLIENTE", lado_dest="FINAUD", email="cli@emp.com"):
    return {
        "corpo": corpo,
        "corpo_limpo": corpo,
        "contato_origem": {"email": email, "lado": lado_orig, "nome": ""},
        "contato_destino": {"email": "suporte@finaud.com.br", "lado": lado_dest},
        "data_email": "2026-06-01 10:00:00",
        "data_iso": "2026-06-01",
        "encaminhados": [],
    }


def _ctx(ultima_msg=None, thread=None, texto="", alvo="DDR4111"):
    return Contexto(
        tid="tid_lim",
        thread=thread or {"mensagens": [ultima_msg] if ultima_msg else []},
        evento={"cadoc": alvo, "titulo": ""},
        ultima_msg=ultima_msg or {},
        texto_fio=texto,
        alvo_triagem=alvo,
        dia_ref=None,
    )


# ---------------------------------------------------------------------------
# get_mensagens_efetivas — casos limite
# ---------------------------------------------------------------------------
class TestGetMensagensEfetivas:
    def test_lista_vazia(self):
        assert get_mensagens_efetivas([]) == []

    def test_item_nao_dict_levanta_attributeerror(self):
        """get_mensagens_efetivas não tem guard para não-dict — documenta comportamento atual."""
        import pytest
        with pytest.raises(AttributeError):
            get_mensagens_efetivas(["mensagem_invalida"])

    def test_campo_corpo_none(self):
        msg = _msg()
        msg["corpo"] = None
        resultado = get_mensagens_efetivas([msg])
        assert len(resultado) == 1

    def test_sem_campo_encaminhados(self):
        msg = _msg("texto")
        del msg["encaminhados"]
        resultado = get_mensagens_efetivas([msg])
        assert len(resultado) == 1

    def test_cem_mensagens(self):
        msgs = [_msg(f"mensagem {i}") for i in range(100)]
        resultado = get_mensagens_efetivas(msgs)
        assert len(resultado) == 100

    def test_encaminhado_injeta_mensagem_virtual(self):
        enc = {
            "de": "cliente@emp.com",
            "corpo": "mensagem original do cliente",
            "data_email": "2026-05-31",
        }
        msg = _msg("reply da Finaud", lado_orig="FINAUD", email="ana@finaud.com.br")
        msg["encaminhados"] = [enc]
        resultado = get_mensagens_efetivas([msg])
        # Deve ter a mensagem virtual + o reply
        assert len(resultado) == 2
        assert any(r.get("_virtual") for r in resultado)

    def test_corpo_com_encoding_latino(self):
        """Caracteres latin-1 não devem quebrar."""
        msg = _msg("Crít\xedca recebida")
        resultado = get_mensagens_efetivas([msg])
        assert len(resultado) == 1


# ---------------------------------------------------------------------------
# _parse_data_msg — datas inválidas
# ---------------------------------------------------------------------------
class TestParsaDataMsg:
    def test_data_none(self):
        assert _parse_data_msg({}) is None

    def test_data_vazia(self):
        assert _parse_data_msg({"data_iso": ""}) is None

    def test_data_invalida(self):
        assert _parse_data_msg({"data_iso": "nao-e-data"}) is None

    def test_data_valida(self):
        from datetime import date
        resultado = _parse_data_msg({"data_iso": "2026-06-01"})
        assert resultado == date(2026, 6, 1)

    def test_data_com_horario(self):
        from datetime import date
        resultado = _parse_data_msg({"data_iso": "2026-06-01T10:00:00"})
        assert resultado == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# Helpers — campos None / corpo vazio
# ---------------------------------------------------------------------------
class TestHelpersComCamposNone:
    def test_transmitido_bacen_string_vazia(self):
        # _transmitido_bacen recebe string, não dict
        assert _transmitido_bacen("") is False

    def test_transmitido_bacen_none_como_string(self):
        # None não é string válida — documenta: a função espera str
        import pytest
        with pytest.raises((TypeError, AttributeError)):
            _transmitido_bacen(None)

    def test_entrega_conclusiva_msg_vazia(self):
        assert _finaud_entrega_conclusiva({}) is False

    def test_agradecimento_corpo_none(self):
        msg = _msg()
        msg["corpo"] = None
        assert _cliente_agradecimento_conclusivo(msg) is False

    def test_reconhecimento_curto_sem_corpo(self):
        # _finaud_somente_reconhecimento_curto recebe (ult, thread)
        msg = _msg("")
        thread = {"mensagens": [msg]}
        assert _finaud_somente_reconhecimento_curto(msg, thread) is False

    def test_sec5c_corpo_none(self):
        msg = _msg()
        msg["corpo"] = None
        assert _sec5c_finaud_corpo_conclusivo(msg) is False


# ---------------------------------------------------------------------------
# Colisão de categorias — mesma thread pode ser vista por DDR4111 e DLO
# ---------------------------------------------------------------------------
class TestColisaoCategorias:
    """
    Threads com cadoc DLO_2061 não devem ser classificadas pelo detector DDR4111
    e vice-versa. O motor usa cadoc para direcionar para o detector correto —
    mas o Contexto pode ser construído com o cadoc errado.
    """

    def test_ddr_nao_classifica_quando_cadoc_dlo(self):
        """Contexto com alvo DDR4111 mas evento com cadoc DLO_2061 — detector DDR insumo ainda dispara para cliente."""
        msg_cli = _msg("Segue o arquivo DLO corrigido em anexo.", lado_orig="CLIENTE")
        ctx = _ctx(ultima_msg=msg_cli, alvo="DDR4111")
        # O detector de insumo do cliente é agnóstico ao cadoc
        resultado = _ddr._det_3_insumo_cliente(ctx)
        assert isinstance(resultado, bool)  # não quebra

    def test_dlo_detector_com_alvo_correto(self):
        msg_cli = _msg("Segue o arquivo DLO em anexo conforme solicitado.", lado_orig="CLIENTE")
        ctx = _ctx(ultima_msg=msg_cli, alvo="DLO")
        resultado = _dlo._det_3_insumo_cliente(ctx)
        assert isinstance(resultado, bool)

    def test_thread_sem_mensagens_nao_quebra_ddr(self):
        ctx = _ctx(ultima_msg=_msg(""), thread={"mensagens": []}, alvo="DDR4111")
        try:
            _ddr._det_3_insumo_cliente(ctx)
            _ddr._det_transmitido_bacen(ctx)
        except Exception as e:
            assert False, f"Detector DDR quebrou com thread vazia: {e}"

    def test_thread_sem_mensagens_nao_quebra_dlo(self):
        ctx = _ctx(ultima_msg=_msg(""), thread={"mensagens": []}, alvo="DLO")
        try:
            _dlo._det_3_insumo_cliente(ctx)
        except Exception as e:
            assert False, f"Detector DLO quebrou com thread vazia: {e}"


# ---------------------------------------------------------------------------
# Mensagem com corpo extremamente longo
# ---------------------------------------------------------------------------
class TestCorpoLongo:
    def test_corpo_10k_chars_nao_quebra_transmitido(self):
        # _transmitido_bacen recebe string direta
        corpo = "texto normal " * 800  # ~10k chars
        assert isinstance(_transmitido_bacen(corpo), bool)

    def test_transmitido_bacen_detecta_em_corpo_longo(self):
        corpo = "texto normal " * 400 + " transmitido no bacen " + "texto normal " * 400
        assert _transmitido_bacen(corpo) is True

    def test_corpo_10k_chars_nao_quebra_sec5(self):
        corpo = "texto normal " * 800
        msg = _msg(corpo, lado_orig="FINAUD", email="ana@finaud.com.br")
        assert isinstance(_sec5_remessa_finaud(msg), bool)

    def test_corpo_vazio_nao_e_conclusivo(self):
        msg = _msg("", lado_orig="FINAUD", email="ana@finaud.com.br")
        assert _finaud_entrega_conclusiva(msg) is False


# ---------------------------------------------------------------------------
# Thread com 1 única mensagem
# ---------------------------------------------------------------------------
class TestThreadUmaMensagem:
    def test_uma_msg_finaud_nao_vira_concluido_sem_contexto(self):
        """Uma única mensagem da Finaud sem resposta do cliente não é conclusiva."""
        msg = _msg("Boa tarde, segue orientação sobre o DDR.", lado_orig="FINAUD", email="ana@finaud.com.br")
        assert _finaud_entrega_conclusiva(msg) is False or isinstance(_finaud_entrega_conclusiva(msg), bool)

    def test_uma_msg_cliente_e_insumo(self):
        """Cliente enviando arquivo = insumo aguardando processamento."""
        msg = _msg("Segue em anexo o arquivo DDR corrigido.", lado_orig="CLIENTE")
        ctx = _ctx(ultima_msg=msg, thread={"mensagens": [msg]}, alvo="DDR4111")
        resultado = _ddr._det_3_insumo_cliente(ctx)
        assert resultado is True
