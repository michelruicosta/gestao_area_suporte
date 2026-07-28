"""
Testes de regressao para bugs #PF47, #PF46, #PF35, #PF33, #PF45 — motor.py / helpers.py / script 09
Camada 2 da blindagem do pipeline.

Referencias: documentacoes/REGISTRO_CORRECOES.md
"""

import sys
import importlib.util
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _msg_fc(corpo, email_finaud="andrea@finaud.com.br"):
    """Mensagem Finaud → Cliente com estrutura minima valida."""
    return {
        "contato_origem": {"lado": "FINAUD", "email": email_finaud},
        "contato_destino": {"lado": "CLIENTE", "email": "cliente@empresa.com"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "anexos": [],
    }


def _msg_cf(corpo):
    """Mensagem Cliente → Finaud."""
    return {
        "contato_origem": {"lado": "CLIENTE", "email": "cliente@empresa.com"},
        "contato_destino": {"lado": "FINAUD", "email": "andrea@finaud.com.br"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "anexos": [],
    }


def _importar_script09():
    """Importa 09_integrar_dados_painel.py pelo caminho absoluto."""
    caminho = ROOT / "scripts" / "09_integrar_dados_painel.py"
    spec = importlib.util.spec_from_file_location("script09", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# #PF47 — Bug Regra 4b bloqueava Regras 5/6/7
# Sintoma: thread com 2+ msgs, _ffar=None, caia em else e ficava em ACAO_INTERNA
# sem passar pelas Regras 5/6/7.
# ---------------------------------------------------------------------------

class TestPF47_Regra4bNaoBloqueiaRegras567:

    def test_ffar_none_para_agradecimento_simples(self):
        """_ffar nao deve disparar quando penultima nao e envio de relatorio F->F."""
        from triagem.helpers import _finaud_finaud_agradecimento_relatorio as _ffar
        # Padrao: cliente enviou arquivo, Finaud agradeceu — nao e F->F
        ultima = _msg_fc("Obrigada!")
        penultima = _msg_cf("Segue o arquivo solicitado.")
        resultado = _ffar(ultima, penultima)
        assert resultado is None, (
            f"_ffar nao deveria disparar aqui (nao e F->F), retornou: {resultado}"
        )

    def test_ffar_none_nao_impede_facr(self):
        """Quando _ffar=None, _facr deve ser avaliavel independentemente."""
        from triagem.helpers import (
            _finaud_agradecimento_curto_sem_remessa as _facr,
            _finaud_finaud_agradecimento_relatorio as _ffar,
        )
        ultima = _msg_fc("Obrigada!")
        penultima = _msg_cf("Segue o arquivo solicitado.")

        assert _ffar(ultima, penultima) is None
        # _facr deve retornar True — antes do fix #PF47 isso era bloqueado
        assert _facr(ultima) is True, (
            "_facr deveria retornar True para 'Obrigada!' sem pedido ou ? "
            "Regra 7 estava sendo bloqueada pelo elif largo da Regra 4b (#PF47)"
        )

    def test_ffar_none_nao_impede_fpic(self):
        """Quando _ffar=None, _fpic deve ser avaliavel independentemente."""
        from triagem.helpers import (
            _finaud_pedido_insumos_a_cliente as _fpic,
            _finaud_finaud_agradecimento_relatorio as _ffar,
        )
        ultima = _msg_fc("Peco a gentileza de nos enviar o arquivo atualizado.")
        penultima = _msg_cf("Voces receberam o relatorio anterior?")

        assert _ffar(ultima, penultima) is None
        assert _fpic(ultima) is True, (
            "_fpic deveria disparar — Regra 6 estava sendo bloqueada (#PF47)"
        )

    def test_ffar_aguardando_nao_vai_para_concluido(self):
        """_ffar='AGUARDANDO' nao deve ser confundido com conclusao."""
        from triagem.helpers import _finaud_finaud_agradecimento_relatorio as _ffar
        ultima = _msg_fc("Obrigada pelo envio dos dados. Iremos processar.")
        penultima = _msg_cf("Segue a planilha com as posicoes.")
        resultado = _ffar(ultima, penultima)
        assert resultado != "CONCLUIDO", (
            f"_ffar retornou CONCLUIDO indevidamente para dados brutos: {resultado}"
        )


# ---------------------------------------------------------------------------
# #PF46 — Motor: Regras 6/7 com anti-falso-positivo
# Sintoma: _facr disparava mesmo com pedido/pergunta disfarCado de agradecimento
# ---------------------------------------------------------------------------

class TestPF46_AntiFalsoPositivoFacr:

    def test_facr_nao_dispara_com_interrogacao(self):
        """_facr nao deve disparar se o corpo contem '?' (#PF46 anti-FP)."""
        from triagem.helpers import _finaud_agradecimento_curto_sem_remessa as _facr
        msg = _msg_fc("Obrigada! Voce poderia confirmar o recebimento?")
        assert _facr(msg) is False

    def test_facr_nao_dispara_com_pedido_gentileza(self):
        """_facr nao deve disparar se contem 'por gentileza'."""
        from triagem.helpers import _finaud_agradecimento_curto_sem_remessa as _facr
        msg = _msg_fc("Obrigada! Por gentileza, envie o comprovante.")
        assert _facr(msg) is False

    def test_facr_nao_dispara_com_solicito(self):
        """_facr nao deve disparar se contem 'solicito'."""
        from triagem.helpers import _finaud_agradecimento_curto_sem_remessa as _facr
        msg = _msg_fc("Obrigada pelo contato. Solicito o envio do arquivo.")
        assert _facr(msg) is False

    def test_facr_dispara_agradecimento_simples(self):
        """_facr deve disparar para agradecimento simples sem pedido."""
        from triagem.helpers import _finaud_agradecimento_curto_sem_remessa as _facr
        msg = _msg_fc("Obrigada!")
        assert _facr(msg) is True, "_facr deve retornar True para 'Obrigada!' (#PF46)"

    def test_facr_dispara_ok_obrigada_retorno(self):
        """_facr deve disparar para 'Ok. Obrigada pelo retorno'."""
        from triagem.helpers import _finaud_agradecimento_curto_sem_remessa as _facr
        msg = _msg_fc("Ok. Obrigada pelo retorno.")
        assert _facr(msg) is True

    def test_fpic_dispara_peco_a_gentileza(self):
        """_fpic deve detectar 'peco a gentileza' como pedido de insumo (#PF46)."""
        from triagem.helpers import _finaud_pedido_insumos_a_cliente as _fpic
        msg = _msg_fc("Peco a gentileza de nos enviar o extrato atualizado.")
        assert _fpic(msg) is True

    def test_fpic_dispara_por_gentileza_envie(self):
        """_fpic deve detectar 'por gentileza, envie' como pedido de insumo."""
        from triagem.helpers import _finaud_pedido_insumos_a_cliente as _fpic
        msg = _msg_fc("Por gentileza, envie o arquivo DDR referente ao mes de marco.")
        assert _fpic(msg) is True


# ---------------------------------------------------------------------------
# #PF35 — Motor Regra 5: Finaud entregou arquivo ao cliente
# Sintoma: motor ficava ACAO_INTERNA mesmo apos Finaud entregar o arquivo
# ---------------------------------------------------------------------------

class TestPF35_EntregaClienteDetectada:

    def test_fec_detecta_segue_em_anexo(self):
        """_fec deve detectar 'segue em anexo' como entrega (#PF35)."""
        from triagem.helpers import _finaud_entrega_conclusiva as _fec
        msg = _msg_fc("Segue em anexo o DDR para sua conferencia antes de transmitir.")
        assert _fec(msg) is True

    def test_fec_detecta_conforme_solicitado_segue(self):
        """_fec deve detectar 'conforme solicitado, segue...' como entrega."""
        from triagem.helpers import _finaud_entrega_conclusiva as _fec
        msg = _msg_fc("Conforme solicitado, segue o arquivo DDR para envio.")
        assert _fec(msg) is True

    def test_fec_nao_dispara_mensagem_generica(self):
        """_fec nao deve disparar para mensagem sem entrega."""
        from triagem.helpers import _finaud_entrega_conclusiva as _fec
        msg = _msg_fc("Estamos verificando o arquivo. Retornamos em breve.")
        assert not _fec(msg)

    def test_fec_detecta_acoes_cadastradas(self):
        """_fec deve detectar 'as acoes ja foram cadastradas' (#PF46 extensao)."""
        from triagem.helpers import _finaud_entrega_conclusiva as _fec
        # Esta variante pode nao estar no padrao exato — testar o que a regex cobre
        msg = _msg_fc("As opcoes de acoes ja foram cadastradas no sistema.")
        resultado = _fec(msg)
        # Se nao cobrir, isso vira bug documentado — nao falha silenciosamente
        assert resultado is True, (
            "_fec deveria cobrir 'as acoes ja foram cadastradas' — "
            "adicionado no #PF46; verificar regex no helpers.py"
        )

    def test_fec_detecta_segue_protocolo_ddr(self):
        """_fec deve detectar envio de protocolo DDR."""
        from triagem.helpers import _finaud_entrega_conclusiva as _fec
        msg = _msg_fc("Segue o protocolo do DDR transmitido ao BACEN.")
        assert _fec(msg) is True


# ---------------------------------------------------------------------------
# #PF33 — HTML residual removido do corpo dos cards
# ---------------------------------------------------------------------------

class TestPF33_SemHTMLResidual:

    @pytest.fixture(scope="class")
    def script09(self):
        return _importar_script09()

    def test_style_removido_do_corpo(self, script09):
        """Bloco <style> deve ser completamente removido, nao apenas as tags (#PF33)."""
        corpo = "<style>v\\:* {behavior:url(#default#VML);} .MsoNormal{margin:0;}</style><p>Texto real do email.</p>"
        resultado = script09.limpar_corpo_email(corpo)
        assert "behavior" not in resultado, "CSS residual 'behavior' encontrado"
        assert "MsoNormal" not in resultado, "CSS residual 'MsoNormal' encontrado"
        assert "Texto real" in resultado, "Texto legitimo foi removido"

    def test_script_removido_do_corpo(self, script09):
        """Bloco <script> deve ser completamente removido (#PF33)."""
        corpo = "<script>alert('teste')</script><p>Mensagem do cliente.</p>"
        resultado = script09.limpar_corpo_email(corpo)
        assert "alert" not in resultado
        assert "Mensagem do cliente" in resultado

    def test_corpo_texto_puro_preservado(self, script09):
        """Corpo sem HTML deve passar sem perder texto relevante."""
        corpo = "Segue o arquivo DDR conforme solicitado.\n\nAtenciosamente"
        resultado = script09.limpar_corpo_email(corpo)
        assert "Segue o arquivo DDR" in resultado


# ---------------------------------------------------------------------------
# #PF45 — Remetente original de encaminhamentos BACEN
# ---------------------------------------------------------------------------

class TestPF45_RemetenteOriginalFwd:

    @pytest.fixture(scope="class")
    def script09(self):
        return _importar_script09()

    def test_extrai_remetente_bcb_do_corpo(self, script09):
        """_extrair_remetente_original_fwd deve detectar @bcb.gov.br no encaminhamento (#PF45)."""
        corpo = (
            "---------- Mensagem encaminhada ----------\n"
            "De: drm-preenchimento@bcb.gov.br\n"
            "Para: financeiro@cliente.com.br\n"
            "Assunto: Retorno DRM - Critica 4592\n\n"
            "Prezado, identificamos divergencias..."
        )
        resultado = script09._extrair_remetente_original_fwd(corpo)
        assert resultado == "drm-preenchimento@bcb.gov.br", (
            f"Esperado 'drm-preenchimento@bcb.gov.br', obteve: {resultado!r}"
        )

    def test_extrai_remetente_fwd_de_generico(self, script09):
        """_extrair_remetente_original_fwd deve extrair padrao 'De:' no corpo."""
        corpo = "De: qualquer@banco.com\nPara: suporte@finaud.com.br\n\nTexto"
        resultado = script09._extrair_remetente_original_fwd(corpo)
        assert resultado is not None, "Deveria extrair remetente do padrao 'De:'"

    def test_retorna_falsy_sem_encaminhamento(self, script09):
        """Corpo sem encaminhamento deve retornar valor falsy (None ou string vazia)."""
        corpo = "Segue o arquivo conforme solicitado. Atenciosamente."
        resultado = script09._extrair_remetente_original_fwd(corpo)
        assert not resultado, f"Esperado valor falsy, obteve: {resultado!r}"
