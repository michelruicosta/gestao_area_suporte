# -*- coding: utf-8 -*-
"""
Testes unitários para:
  - scripts/guard_imutabilidade.py  (snapshot_status, detectar_regressoes,
                                     so_eventos_criticos, formatar_regressoes,
                                     avaliar_transicao, _env_on)
  - scripts/email_alerta_template.py (montar_email_alerta, tabela_threads,
                                       bloco_destaque, SEVERIDADE)
  - scripts/oraculo_cenarios_pipeline.py (_parse_dd_mm_yyyy, periodo_executar_tudo)

Sem dependência de arquivo em disco.
"""
import sys, os
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import guard_imutabilidade as guard
from guard_imutabilidade import (
    _env_on,
    snapshot_status,
    detectar_regressoes,
    so_eventos_criticos,
    formatar_regressoes,
    avaliar_transicao,
    RegressaoStatusError,
)
from email_alerta_template import (
    montar_email_alerta,
    tabela_threads,
    bloco_destaque,
    SEVERIDADE,
)
from oraculo_cenarios_pipeline import (
    _parse_dd_mm_yyyy,
    periodo_executar_tudo,
)


# ===========================================================================
# guard_imutabilidade — _env_on
# ===========================================================================
class TestEnvOn:
    def test_valor_1(self):
        with patch.dict(os.environ, {"TEST_FLAG": "1"}):
            assert _env_on("TEST_FLAG") is True

    def test_valor_true(self):
        with patch.dict(os.environ, {"TEST_FLAG": "true"}):
            assert _env_on("TEST_FLAG") is True

    def test_valor_0(self):
        with patch.dict(os.environ, {"TEST_FLAG": "0"}):
            assert _env_on("TEST_FLAG") is False

    def test_ausente_retorna_false(self):
        env = {k: v for k, v in os.environ.items() if k != "TEST_FLAG"}
        with patch.dict(os.environ, env, clear=True):
            assert _env_on("TEST_FLAG") is False

    def test_default_aplicado(self):
        env = {k: v for k, v in os.environ.items() if k != "TEST_FLAG"}
        with patch.dict(os.environ, env, clear=True):
            assert _env_on("TEST_FLAG", default="1") is True


# ===========================================================================
# guard_imutabilidade — snapshot_status
# ===========================================================================
def _rec(tid, status, auto=True, alvo="DDR4111", motivo=""):
    base = {
        "threadId": tid,
        "alvo_triagem_auto": alvo,
        "origem_triagem_auto": auto,
        "data_marcacao": "2026-01-10",
        "data_conclusao": "2026-01-10",
        "motivo": motivo,
        "tipo": "AUTO",
    }
    return base


class TestSnapshotStatus:
    def test_aguardando_e_concluido(self):
        ag = [_rec("tid1", "AGUARDANDO")]
        co = [_rec("tid2", "CONCLUIDO")]
        snap = snapshot_status(ag, co)
        assert snap["tid1"]["status"] == "AGUARDANDO"
        assert snap["tid2"]["status"] == "CONCLUIDO"

    def test_concluido_ganha_aguardando(self):
        """Mesmo tid em ag e co — concluído deve prevalecer."""
        ag = [_rec("tid1", "AGUARDANDO")]
        co = [_rec("tid1", "CONCLUIDO")]
        snap = snapshot_status(ag, co)
        assert snap["tid1"]["status"] == "CONCLUIDO"

    def test_sem_threadid_ignorado(self):
        ag = [{"alvo_triagem_auto": "DDR"}]  # sem threadId
        snap = snapshot_status(ag, [])
        assert len(snap) == 0

    def test_listas_vazias(self):
        snap = snapshot_status([], [])
        assert snap == {}


# ===========================================================================
# guard_imutabilidade — detectar_regressoes
# ===========================================================================
def _snap(tid, status="AGUARDANDO", auto=True):
    return {
        "status": status,
        "alvo": "DDR4111",
        "origem_triagem_auto": auto,
        "data_marcacao": "2026-01-10",
        "data_conclusao": "2026-01-10",
        "motivo": "",
        "tipo": "AUTO",
    }


class TestDetectarRegressoes:
    def test_sem_mudanca(self):
        s = {"tid1": _snap("tid1")}
        assert detectar_regressoes(s, s) == []

    def test_regressao_pendente(self):
        antes = {"tid1": _snap("tid1")}
        depois = {}
        regs = detectar_regressoes(antes, depois)
        assert len(regs) == 1
        assert regs[0]["evento"] == "REGRESSAO_PENDENTE"

    def test_alteracao_status(self):
        antes  = {"tid1": _snap("tid1", "AGUARDANDO")}
        depois = {"tid1": _snap("tid1", "CONCLUIDO")}
        regs = detectar_regressoes(antes, depois)
        assert any(r["evento"] == "ALTERACAO_STATUS" for r in regs)

    def test_novo_registro(self):
        antes  = {}
        depois = {"tid1": _snap("tid1")}
        regs = detectar_regressoes(antes, depois)
        assert regs[0]["evento"] == "NOVO_REGISTRO"

    def test_alteracao_manual(self):
        antes  = {"tid1": _snap("tid1", auto=False)}
        depois = {}
        regs = detectar_regressoes(antes, depois)
        assert regs[0]["evento"] == "ALTERACAO_MANUAL"

    def test_sem_mudanca_mesmos_dados(self):
        s1 = {"tid1": _snap("tid1", "AGUARDANDO")}
        s2 = {"tid1": _snap("tid1", "AGUARDANDO")}
        assert detectar_regressoes(s1, s2) == []


# ===========================================================================
# guard_imutabilidade — so_eventos_criticos
# ===========================================================================
class TestSoEventosCriticos:
    def test_filtra_criticos(self):
        regs = [
            {"evento": "REGRESSAO_PENDENTE", "threadId": "t1"},
            {"evento": "NOVO_REGISTRO",      "threadId": "t2"},
            {"evento": "ALTERACAO_STATUS",   "threadId": "t3"},
            {"evento": "ALTERACAO_AUTO",     "threadId": "t4"},
        ]
        criticos = so_eventos_criticos(regs)
        assert len(criticos) == 2
        eventos = {r["evento"] for r in criticos}
        assert "REGRESSAO_PENDENTE" in eventos
        assert "ALTERACAO_STATUS" in eventos

    def test_lista_vazia(self):
        assert so_eventos_criticos([]) == []


# ===========================================================================
# guard_imutabilidade — formatar_regressoes
# ===========================================================================
class TestFormatarRegressoes:
    def test_regressao_pendente(self):
        regs = [{
            "threadId": "tid1",
            "evento": "REGRESSAO_PENDENTE",
            "antes": {"status": "AGUARDANDO", "alvo": "DDR4111", "data_marcacao": "2026-01-10", "data_conclusao": ""},
            "depois": None,
        }]
        texto = formatar_regressoes(regs)
        assert "tid1" in texto
        assert "PENDENTE" in texto

    def test_alteracao_status(self):
        regs = [{
            "threadId": "tid2",
            "evento": "ALTERACAO_STATUS",
            "antes":  {"status": "AGUARDANDO"},
            "depois": {"status": "CONCLUIDO"},
        }]
        texto = formatar_regressoes(regs)
        assert "tid2" in texto

    def test_trunca_em_max_linhas(self):
        regs = [{"threadId": f"t{i}", "evento": "ALTERACAO_AUTO", "antes": {}, "depois": {}} for i in range(30)]
        texto = formatar_regressoes(regs, max_linhas=5)
        assert "(+25 eventos)" in texto

    def test_lista_vazia(self):
        assert formatar_regressoes([]) == ""


# ===========================================================================
# guard_imutabilidade — avaliar_transicao
# ===========================================================================
class TestAvaliarTransicao:
    def test_sem_criticos_nao_levanta(self):
        s = {"tid1": _snap("tid1")}
        # Sem mudança = sem críticos = não levanta
        result = avaliar_transicao(s, s)
        assert result == []

    def test_novo_registro_nao_levanta(self):
        antes  = {}
        depois = {"tid1": _snap("tid1")}
        # NOVO_REGISTRO não é crítico
        result = avaliar_transicao(antes, depois)
        assert any(r["evento"] == "NOVO_REGISTRO" for r in result)

    def test_regressao_fora_de_carga_levanta(self):
        antes  = {"tid1": _snap("tid1")}
        depois = {}
        env = {k: v for k, v in os.environ.items()
               if k not in ("ORACULO_CARGA_EM_CURSO", "ORACULO_BLOQUEAR_REGRESSAO_STATUS")}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(guard, "registar_alertas"):
                try:
                    avaliar_transicao(antes, depois)
                    levantou = False
                except (RegressaoStatusError, SystemExit):
                    levantou = True
        assert levantou

    def test_regressao_em_carga_nao_levanta(self):
        antes  = {"tid1": _snap("tid1")}
        depois = {}
        with patch.dict(os.environ, {"ORACULO_CARGA_EM_CURSO": "1"}):
            with patch.object(guard, "registar_alertas"):
                result = avaliar_transicao(antes, depois)
        assert any(r["evento"] == "REGRESSAO_PENDENTE" for r in result)


# ===========================================================================
# email_alerta_template — montar_email_alerta
# ===========================================================================
class TestMontarEmailAlerta:
    def test_retorna_html(self):
        html = montar_email_alerta(
            severidade=SEVERIDADE.ATENCAO,
            titulo="Teste",
            subtitulo="Subtítulo teste",
            corpo_html="<p>Conteúdo</p>",
        )
        assert "<!DOCTYPE html>" in html
        assert "Teste" in html

    def test_severidade_critico(self):
        html = montar_email_alerta(SEVERIDADE.CRITICO, "Crítico", "", "<p>x</p>")
        assert "CRITICO" in html

    def test_severidade_info(self):
        html = montar_email_alerta(SEVERIDADE.INFO, "Info", "", "<p>x</p>")
        assert "INFORMATIVO" in html

    def test_rodape_extra_incluido(self):
        html = montar_email_alerta(SEVERIDADE.INFO, "T", "", "<p/>", rodape_extra="rodape-teste")
        assert "rodape-teste" in html

    def test_sem_subtitulo_sem_div(self):
        html = montar_email_alerta(SEVERIDADE.INFO, "T", "", "<p/>")
        # subtitulo vazio não deve gerar div de subtítulo
        assert 'margin-top:8px' not in html

    def test_painel_url_customizado(self):
        html = montar_email_alerta(SEVERIDADE.INFO, "T", "", "<p/>",
                                   painel_url="http://meu-servidor:8080")
        assert "meu-servidor:8080" in html


# ===========================================================================
# email_alerta_template — tabela_threads
# ===========================================================================
class TestTabelaThreads:
    def test_gera_tabela_html(self):
        html = tabela_threads(["Cliente", "Status"], [["Empresa A", "Pendente"]])
        assert "<table" in html
        assert "Cliente" in html
        assert "Empresa A" in html

    def test_zebrado(self):
        linhas = [["A", "1"], ["B", "2"], ["C", "3"]]
        html = tabela_threads(["Nome", "Val"], linhas)
        assert "#ffffff" in html
        assert "#f8f8ff" in html

    def test_sem_linhas(self):
        html = tabela_threads(["Col"], [])
        assert "<table" in html
        assert "Col" in html

    def test_colunas_aparecem_no_header(self):
        html = tabela_threads(["Coluna1", "Coluna2"], [])
        assert "Coluna1" in html
        assert "Coluna2" in html


# ===========================================================================
# email_alerta_template — bloco_destaque
# ===========================================================================
class TestBlocoDestaque:
    def test_tipo_info(self):
        html = bloco_destaque("mensagem info", "info")
        assert "mensagem info" in html
        assert "<div" in html

    def test_tipo_alerta(self):
        html = bloco_destaque("mensagem alerta", "alerta")
        assert "mensagem alerta" in html

    def test_tipo_ok(self):
        html = bloco_destaque("tudo certo", "ok")
        assert "tudo certo" in html

    def test_tipo_desconhecido_fallback_info(self):
        html = bloco_destaque("fallback", "xyz")
        assert "fallback" in html


# ===========================================================================
# oraculo_cenarios_pipeline — _parse_dd_mm_yyyy
# ===========================================================================
class TestParseDdMmYyyy:
    def test_formato_barra(self):
        assert _parse_dd_mm_yyyy("10/01/2026") == date(2026, 1, 10)

    def test_formato_hifen(self):
        assert _parse_dd_mm_yyyy("10-01-2026") == date(2026, 1, 10)

    def test_ano_curto(self):
        assert _parse_dd_mm_yyyy("10/01/26") == date(2026, 1, 10)

    def test_invalido_levanta(self):
        import pytest
        with pytest.raises((ValueError, Exception)):
            _parse_dd_mm_yyyy("nao-e-data")


# ===========================================================================
# oraculo_cenarios_pipeline — periodo_executar_tudo
# ===========================================================================
class TestPeriodoExecutarTudo:
    def test_retorna_dois_strings(self):
        inicio, fim = periodo_executar_tudo(date(2026, 1, 10))
        assert isinstance(inicio, str)
        assert isinstance(fim, str)

    def test_dia_seguinte(self):
        inicio, fim = periodo_executar_tudo(date(2026, 1, 10))
        assert "10" in inicio
        assert "11" in fim

    def test_virada_de_mes(self):
        inicio, fim = periodo_executar_tudo(date(2026, 1, 31))
        assert "31" in inicio
        assert "1" in fim
        assert "Feb" in fim

    def test_ano_em_ambos(self):
        inicio, fim = periodo_executar_tudo(date(2026, 6, 7))
        assert "2026" in inicio
        assert "2026" in fim
