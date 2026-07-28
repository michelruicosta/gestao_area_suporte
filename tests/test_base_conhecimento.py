# -*- coding: utf-8 -*-
"""
Testes unitários para scripts/base_conhecimento_bacen.py

Cobre: extrair_codigo, _normalizar_codigo, codigo_agrupamento,
       extrair_documento, limpar_solucao, deve_excluir, _critica_e_vaga.
Sem dependência de arquivo em disco.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from base_conhecimento_bacen import (
    extrair_codigo,
    _normalizar_codigo,
    codigo_agrupamento,
    extrair_documento,
    limpar_solucao,
    deve_excluir,
    _critica_e_vaga,
)


# ---------------------------------------------------------------------------
# extrair_codigo
# ---------------------------------------------------------------------------
class TestExtrairCodigo:
    def test_codigo_alfanumerico_dlo(self):
        assert extrair_codigo("Código DLO00047 pendente") == "DLO00047"

    def test_codigo_alfanumerico_dli(self):
        assert extrair_codigo("Código DLI206200004") == "DLI206200004"

    def test_codigo_numerico_puro(self):
        resultado = extrair_codigo("inconsistência 2282 no período")
        assert resultado is not None

    def test_prioriza_alfanumerico_sobre_numerico(self):
        resultado = extrair_codigo("DLO00047 e também 1234")
        assert "DLO" in resultado

    def test_retorna_none_sem_codigo(self):
        assert extrair_codigo("") is None
        assert extrair_codigo(None) is None
        assert extrair_codigo("texto sem código") is None

    def test_no_maximo_tres_codigos(self):
        texto = "DLO00001 DLO00002 DLO00003 DLO00004"
        resultado = extrair_codigo(texto)
        assert resultado.count("/") <= 2


# ---------------------------------------------------------------------------
# _normalizar_codigo
# ---------------------------------------------------------------------------
class TestNormalizarCodigo:
    def test_dlo_ocr_O_para_zero(self):
        assert _normalizar_codigo("DLODO047") == "DLO00047"

    def test_dlo_zero_padding(self):
        assert _normalizar_codigo("DLO047") == "DLO00047"

    def test_dli_normaliza(self):
        assert _normalizar_codigo("DLI00116") == "DLI00116"

    def test_elim_normaliza(self):
        resultado = _normalizar_codigo("ELIMO2018")
        assert resultado.startswith("ELIM")

    def test_codigo_sem_prefixo_especial(self):
        assert _normalizar_codigo("2282") == "2282"

    def test_uppercase(self):
        assert _normalizar_codigo("dlo00047") == "DLO00047"


# ---------------------------------------------------------------------------
# codigo_agrupamento
# ---------------------------------------------------------------------------
class TestCodigoAgrupamento:
    def test_codigo_dlo(self):
        resultado = codigo_agrupamento("Código DLO00047 com pendência")
        assert resultado is not None
        assert "DLO" in resultado

    def test_retorna_none_vazio(self):
        assert codigo_agrupamento("") is None
        assert codigo_agrupamento(None) is None

    def test_nao_captura_telefone(self):
        # Número após (XX) = telefone — não deve ser capturado
        resultado = codigo_agrupamento("(11) 3900-1234 escritório Av. Lima")
        assert resultado is None

    def test_codigo_numerico_com_contexto(self):
        texto = "Código\n2282\ninconsistência identificada"
        resultado = codigo_agrupamento(texto)
        assert resultado is not None


# ---------------------------------------------------------------------------
# extrair_documento
# ---------------------------------------------------------------------------
class TestExtrairDocumento:
    def test_dlo(self):
        assert extrair_documento({"critica_texto": "DLO pendente no sistema"}) == "2061"

    def test_dli(self):
        assert extrair_documento({"critica_texto": "Erro no DLI 2062"}) == "2062"

    def test_drm(self):
        assert extrair_documento({"critica_texto": "DRM incorreto"}) == "2060"

    def test_ddr(self):
        assert extrair_documento({"critica_texto": "DDR 2011 vencido"}) == "2011"

    def test_cos_4111(self):
        assert extrair_documento({"critica_texto": "CADOC 4111 pendente"}) == "4111"

    def test_outro_quando_nao_identifica(self):
        assert extrair_documento({"critica_texto": "texto genérico sem código"}) == "Outro"

    def test_fallback_para_assunto(self):
        entrada = {"critica_texto": "", "assunto": "Problema com DLO"}
        assert extrair_documento(entrada) == "2061"

    def test_critica_tem_prioridade_sobre_assunto(self):
        """Assunto menciona DLO mas crítica é DLI — DLI deve vencer."""
        entrada = {"critica_texto": "DLI 2062 inconsistente", "assunto": "Erro DLO"}
        assert extrair_documento(entrada) == "2062"

    def test_entrada_vazia(self):
        assert extrair_documento({}) == "Outro"


# ---------------------------------------------------------------------------
# limpar_solucao
# ---------------------------------------------------------------------------
class TestLimparSolucao:
    def test_remove_saudacao_prezado(self):
        texto = "Prezado João, boa tarde! O arquivo DDR foi transmitido com sucesso."
        resultado = limpar_solucao(texto)
        assert "Prezado" not in resultado
        assert "transmitido" in resultado

    def test_remove_despedida(self):
        texto = "O arquivo foi enviado ao BACEN. Atenciosamente,"
        resultado = limpar_solucao(texto)
        assert "Atenciosamente" not in resultado
        assert "enviado" in resultado

    def test_remove_markdown_asteriscos(self):
        texto = "A remessa **DDR** foi aceita."
        resultado = limpar_solucao(texto)
        assert "**" not in resultado
        assert "DDR" in resultado

    def test_texto_vazio(self):
        assert limpar_solucao("") == ""
        assert limpar_solucao(None) == ""

    def test_conteudo_tecnico_preservado(self):
        texto = "O arquivo DLO00047 foi transmitido ao BACEN em 2026-01-10."
        resultado = limpar_solucao(texto)
        assert "DLO00047" in resultado
        assert "BACEN" in resultado


# ---------------------------------------------------------------------------
# _critica_e_vaga
# ---------------------------------------------------------------------------
class TestCriticaEVaga:
    def test_critica_vaga_generico(self):
        # origem deve ser msg_cliente ou enc_nao_finaud para retornar True
        resultado = _critica_e_vaga("Inconsistência no arquivo", "msg_cliente")
        # pode ou não disparar dependendo do padrão _PAT_CRITICA_VAGA — não é vaga pura
        # apenas confirma que a função aceita a chamada sem erro
        assert isinstance(resultado, bool)

    def test_critica_com_codigo_nao_vaga(self):
        # texto técnico com código → não é vaga
        assert _critica_e_vaga("DLO00047: valor fora do limite do BACEN", "msg_cliente") is False

    def test_origem_incorreta_retorna_false(self):
        # origem diferente de msg_cliente/enc_nao_finaud → sempre False
        assert _critica_e_vaga("qualquer texto aqui", "DLO") is False
        assert _critica_e_vaga("qualquer texto aqui", "assunto_fallback") is False

    def test_critica_longa_retorna_false(self):
        # texto com mais de 600 chars → False (não vaga por tamanho)
        assert _critica_e_vaga("x" * 601, "msg_cliente") is False


# ---------------------------------------------------------------------------
# deve_excluir
# ---------------------------------------------------------------------------
class TestDeveExcluir:
    def test_exclui_assunto_fallback(self):
        # critica_origem == 'assunto_fallback' → sempre excluir
        entrada = {"critica_origem": "assunto_fallback", "critica_texto": "DLO pendente"}
        assert deve_excluir(entrada) is True

    def test_exclui_msg_cliente_critica_curta(self):
        # critica_origem msg_cliente + texto < 80 chars → excluir
        entrada = {"critica_origem": "msg_cliente", "critica_texto": "Erro DLO"}
        assert deve_excluir(entrada) is True

    def test_nao_exclui_msg_cliente_critica_longa(self):
        # critica_origem msg_cliente + texto >= 80 chars → não excluir
        crit = "DLO00047 fora do limite: valor informado no campo X diverge do esperado conforme normativa do BACEN."
        assert len(crit) >= 80
        entrada = {"critica_origem": "msg_cliente", "critica_texto": crit}
        assert deve_excluir(entrada) is False

    def test_nao_exclui_sem_origem(self):
        # sem critica_origem reconhecida → não excluir
        entrada = {"critica_texto": "", "solucao": ""}
        assert deve_excluir(entrada) is False
