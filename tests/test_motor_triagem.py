# -*- coding: utf-8 -*-
"""
Testes unitários para scripts/triagem/motor.py

Cobre funções puras/quase-puras do motor (sem I/O de disco):
  _strip_auto, _strip_auto_para_tids, _alvo_triagem_registro,
  _registro_concluido_auto, _registro_aguardando_auto,
  _eventos_por_cadocs, _melhor_evento_por_tid,
  _lista_candidatos_triagem, _tids_sem_reprocessar_triagem_fecho_anterior
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from triagem.motor import (
    _strip_auto,
    _strip_auto_para_tids,
    _alvo_triagem_registro,
    _data_conclusao_da_ultima_msg,
    _registro_concluido_auto,
    _registro_aguardando_auto,
    _eventos_por_cadocs,
    _melhor_evento_por_tid,
    _lista_candidatos_triagem,
    _tids_sem_reprocessar_triagem_fecho_anterior,
    _gerar_resumo_motivo,
    EXCLUIR_CADOC,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reg(tid, auto=True, alvo="DDR4111", data_co="2026-06-01", data_ag="2026-06-01"):
    return {
        "threadId": tid,
        "origem_triagem_auto": auto,
        "alvo_triagem_auto": alvo,
        "data_conclusao": data_co,
        "data_marcacao": data_ag,
        "motivo": "teste",
        "tipo": "RESOLVIDA",
    }


def _ev(tid, cadoc="DDR_2011", ts=1000, risk_driver=False):
    return {
        "threadId": tid,
        "cadoc": cadoc,
        "timestamp_epoch": ts,
        "relatorio_interno_risk_driver": risk_driver,
        "titulo": f"Thread {tid}",
        "cliente": "Empresa Teste",
        "responsavel": "Ana",
        "lista_prazos": [],
        "texto_imagens": "",
    }


def _th(tid, mensagens=None):
    return {
        "threadId": tid,
        "mensagens": mensagens or [],
    }


# ---------------------------------------------------------------------------
# _alvo_triagem_registro
# ---------------------------------------------------------------------------
class TestAlvoTriagemRegistro:
    def test_retorna_alvo_presente(self):
        assert _alvo_triagem_registro({"alvo_triagem_auto": "DLO"}) == "DLO"

    def test_fallback_ddr4111(self):
        assert _alvo_triagem_registro({}) == "DDR4111"

    def test_strip_espacos(self):
        assert _alvo_triagem_registro({"alvo_triagem_auto": "  S5  "}) == "S5"


# ---------------------------------------------------------------------------
# _strip_auto
# ---------------------------------------------------------------------------
class TestStripAuto:
    def test_remove_entradas(self):
        lista = [_reg("t1"), _reg("t2", auto=False)]
        resultado, n = _strip_auto(lista)
        assert n == 2
        assert len(resultado) == 0

    def test_remove_somente_alvo_correto(self):
        lista = [_reg("t1", alvo="DDR4111"), _reg("t2", alvo="DLO")]
        resultado, n = _strip_auto(lista, alvo="DDR4111")
        assert n == 1
        assert any(r["threadId"] == "t2" for r in resultado)

    def test_remove_todos_independente_de_origem(self):
        lista = [_reg("t1", auto=False)]
        resultado, n = _strip_auto(lista)
        assert n == 1
        assert len(resultado) == 0

    def test_lista_vazia(self):
        resultado, n = _strip_auto([])
        assert resultado == []
        assert n == 0


# ---------------------------------------------------------------------------
# _strip_auto_para_tids
# ---------------------------------------------------------------------------
class TestStripAutoParaTids:
    def test_remove_apenas_tids_em_set(self):
        lista = [_reg("t1"), _reg("t2"), _reg("t3")]
        resultado, n = _strip_auto_para_tids(lista, "DDR4111", {"t1", "t3"})
        assert n == 2
        assert len(resultado) == 1
        assert resultado[0]["threadId"] == "t2"

    def test_remove_todos_no_set_independente_de_origem(self):
        lista = [_reg("t1", auto=False)]
        resultado, n = _strip_auto_para_tids(lista, "DDR4111", {"t1"})
        assert n == 1
        assert len(resultado) == 0

    def test_preserva_outro_alvo(self):
        lista = [_reg("t1", alvo="DLO")]
        resultado, n = _strip_auto_para_tids(lista, "DDR4111", {"t1"})
        assert n == 0
        assert len(resultado) == 1

    def test_preserva_fecho_anterior_a_dia_ref(self):
        """Fecho com data < dia_ref deve ser preservado."""
        lista = [_reg("t1", data_co="2026-05-01")]
        dia_ref = date(2026, 6, 1)
        resultado, n = _strip_auto_para_tids(lista, "DDR4111", {"t1"}, dia_ref=dia_ref)
        assert n == 0
        assert len(resultado) == 1

    def test_remove_fecho_igual_a_dia_ref(self):
        """Fecho com data == dia_ref deve ser removido (novo run re-triagem)."""
        lista = [_reg("t1", data_co="2026-06-01")]
        dia_ref = date(2026, 6, 1)
        resultado, n = _strip_auto_para_tids(lista, "DDR4111", {"t1"}, dia_ref=dia_ref)
        assert n == 1
        assert len(resultado) == 0

    def test_lista_vazia(self):
        resultado, n = _strip_auto_para_tids([], "DDR4111", {"t1"})
        assert resultado == []
        assert n == 0


# ---------------------------------------------------------------------------
# _registro_concluido_auto
# ---------------------------------------------------------------------------
class TestRegistroConcluido:
    def test_campos_obrigatorios(self):
        r = _registro_concluido_auto("tid1", 5, "Motivo", "DDR_2011", "Empresa X")
        assert r["threadId"] == "tid1"
        assert r["tipo"] == "RESOLVIDA"
        assert r["origem_triagem_auto"] is True
        assert r["alvo_triagem_auto"] == "DDR4111"
        assert "data_conclusao" in r
        assert "aprendizado_ia" in r

    def test_motivo_truncado_900(self):
        motivo_longo = "x" * 1000
        r = _registro_concluido_auto("t1", 1, motivo_longo, "DDR", "Emp")
        assert len(r["motivo_triagem_auto"]) <= 900

    def test_alvo_customizado(self):
        r = _registro_concluido_auto("t1", 1, "m", "DLO_2061", "E", alvo_triagem="DLO")
        assert r["alvo_triagem_auto"] == "DLO"

    def test_dia_fecho_operacional(self):
        r = _registro_concluido_auto("t1", 1, "m", "DDR", "E",
                                     dia_fecho_operacional=date(2026, 6, 5))
        assert "2026-06-05" in r["data_conclusao"]

    def test_sem_dia_fecho_usa_data_da_ultima_msg(self):
        """2-H (01/07/2026): sem dia de fecho, a conclusão usa a data REAL da
        última mensagem da thread — nunca o dia em que o script rodou.
        671 threads ficaram com data errada por causa do carimbo 'hoje'."""
        th = {"threadId": "t1", "mensagens": [
            {"data_iso": "2026-01-10"},
            {"data_iso": "2026-01-21"},
        ]}
        r = _registro_concluido_auto("t1", 2, "m", "DDR", "E", thread=th)
        assert r["data_conclusao"] == "2026-01-21 18:00:00"

    def test_sem_dia_fecho_e_sem_thread_cai_no_agora(self):
        """Sem dia de fecho E sem mensagens: mantém o comportamento antigo (agora)."""
        r = _registro_concluido_auto("t1", 1, "m", "DDR", "E")
        assert r["data_conclusao"].startswith(date.today().isoformat())


# ---------------------------------------------------------------------------
# _data_conclusao_da_ultima_msg (2-H, 01/07/2026)
# ---------------------------------------------------------------------------
class TestDataConclusaoDaUltimaMsg:
    def test_usa_data_da_ultima_msg(self):
        assert _data_conclusao_da_ultima_msg({"data_iso": "2026-01-21"}) == "2026-01-21"

    def test_msg_sem_data_legivel_cai_em_hoje(self):
        assert _data_conclusao_da_ultima_msg({}) == date.today().isoformat()

    def test_sem_msg_cai_em_hoje(self):
        assert _data_conclusao_da_ultima_msg(None) == date.today().isoformat()


# ---------------------------------------------------------------------------
# _registro_aguardando_auto
# ---------------------------------------------------------------------------
class TestRegistroAguardando:
    def test_campos_obrigatorios(self):
        ev = _ev("tid1")
        th = _th("tid1")
        r = _registro_aguardando_auto("tid1", ev, th, "ACAO_INTERNA", "Aguardando", "2026-06-01")
        assert r["threadId"] == "tid1"
        assert r["status"] == "AGUARDANDO"
        assert r["origem_triagem_auto"] is True
        assert "empresa" in r
        assert "cadoc" in r

    def test_qtd_mensagens(self):
        msgs = [{"id": f"m{i}"} for i in range(5)]
        th = _th("t1", mensagens=msgs)
        r = _registro_aguardando_auto("t1", _ev("t1"), th, "T", "M", "2026-06-01")
        assert r["qtd_mensagens_no_fechamento"] == 5

    def test_alvo_triagem_customizado(self):
        r = _registro_aguardando_auto("t1", _ev("t1"), _th("t1"), "T", "M", "2026-06-01",
                                      alvo_triagem="DLO")
        assert r["alvo_triagem_auto"] == "DLO"


# ---------------------------------------------------------------------------
# _eventos_por_cadocs
# ---------------------------------------------------------------------------
class TestEventosPorCadocs:
    def test_filtra_cadoc_correto(self):
        dados = {
            "eventos": [
                _ev("t1", cadoc="DDR_2011"),
                _ev("t2", cadoc="DLO_2061"),
                _ev("t3", cadoc="IGNORADO"),
            ]
        }
        resultado = _eventos_por_cadocs(dados, frozenset({"DDR_2011"}))
        assert len(resultado) == 1
        assert resultado[0]["threadId"] == "t1"

    def test_exclui_ignorado_e_filtrado(self):
        dados = {
            "eventos": [
                _ev("t1", cadoc="IGNORADO"),
                _ev("t2", cadoc="FILTRADO_POR_DATA"),
            ]
        }
        resultado = _eventos_por_cadocs(dados, frozenset({"IGNORADO", "FILTRADO_POR_DATA"}))
        assert resultado == []

    def test_exclui_risk_driver_por_padrao(self):
        dados = {"eventos": [_ev("t1", cadoc="DDR_2011", risk_driver=True)]}
        resultado = _eventos_por_cadocs(dados, frozenset({"DDR_2011"}))
        assert resultado == []

    def test_inclui_risk_driver_quando_pedido(self):
        dados = {"eventos": [_ev("t1", cadoc="", risk_driver=True)]}
        resultado = _eventos_por_cadocs(dados, frozenset(), incluir_relatorio_risk_driver=True)
        assert len(resultado) == 1

    def test_dados_vazio(self):
        assert _eventos_por_cadocs({}, frozenset({"DDR_2011"})) == []


# ---------------------------------------------------------------------------
# _melhor_evento_por_tid
# ---------------------------------------------------------------------------
class TestMelhorEventoPorTid:
    def test_retorna_mais_recente(self):
        evs = [
            _ev("t1", ts=100),
            _ev("t1", ts=200),  # mais recente
        ]
        resultado = _melhor_evento_por_tid(evs)
        assert resultado["t1"]["timestamp_epoch"] == 200

    def test_threads_diferentes(self):
        evs = [_ev("t1", ts=100), _ev("t2", ts=50)]
        resultado = _melhor_evento_por_tid(evs)
        assert "t1" in resultado
        assert "t2" in resultado

    def test_lista_vazia(self):
        assert _melhor_evento_por_tid([]) == {}


# ---------------------------------------------------------------------------
# _lista_candidatos_triagem
# ---------------------------------------------------------------------------
class TestListaCandidatosTriagem:
    def test_exclui_tids_em_excluir(self):
        mapa_t = {"t1": _th("t1"), "t2": _th("t2")}
        por_tid = {"t1": _ev("t1"), "t2": _ev("t2")}
        resultado = _lista_candidatos_triagem(mapa_t, por_tid, None, frozenset({"t1"}))
        assert "t1" not in resultado
        assert "t2" in resultado

    def test_exclui_sem_thread(self):
        mapa_t = {"t2": _th("t2")}
        por_tid = {"t1": _ev("t1"), "t2": _ev("t2")}
        resultado = _lista_candidatos_triagem(mapa_t, por_tid, None, frozenset())
        assert "t1" not in resultado
        assert "t2" in resultado

    def test_lista_vazia(self):
        resultado = _lista_candidatos_triagem({}, {}, None, frozenset())
        assert resultado == []


# ---------------------------------------------------------------------------
# _gerar_resumo_motivo  (gerador do texto legível — ~145 linhas sem teste)
# ---------------------------------------------------------------------------
class TestGerarResumoMotivo:
    def test_sec5_remessa(self):
        txt = _gerar_resumo_motivo("§5 remessa finaud", "DDR_2011", "Empresa X")
        assert "enviou" in txt.lower()

    def test_transmitido_bacen(self):
        txt = _gerar_resumo_motivo("transmitido no bacen", "DDR_2011", "Empresa X")
        assert "transmitido ao bacen" in txt.lower()

    def test_automatico_risk_driver(self):
        txt = _gerar_resumo_motivo("automatico sem acao humana", "", "")
        assert "autom" in txt.lower()  # "automático"

    def test_4f_protocolo_aceito(self):
        txt = _gerar_resumo_motivo("§4f protocolo aceito", "RETORNO_BACEN", "Cliente Y")
        assert "protocolo aceito" in txt.lower()

    def test_4e_agradecimento(self):
        txt = _gerar_resumo_motivo("§4e agradecimento sem novo pedido", "DDR_2011", "Cliente Z")
        assert "agradeceu" in txt.lower()

    def test_5d_orientou(self):
        txt = _gerar_resumo_motivo("§5d orientou conclusivamente", "RETORNO_BACEN", "Cli")
        assert "orientou" in txt.lower()

    def test_nunca_vazio(self):
        # motivo sem nenhum marcador conhecido → fallback, mas nunca vazio
        txt = _gerar_resumo_motivo("motivo qualquer sem marcador", "DDR_2011", "Empresa")
        assert isinstance(txt, str) and len(txt) > 0

    def test_fallback_truncado_300(self):
        txt = _gerar_resumo_motivo("z" * 500, "", "")
        assert len(txt) <= 300

    def test_usa_assunto_da_thread(self):
        th = {"mensagens": [{"contato_origem": {"lado": "FINAUD", "nome": "Ana"},
                             "corpo_limpo": "Segue", "data_email": "2026-06-01",
                             "assunto": "DDR Janeiro"}],
              "assunto": "DDR Janeiro"}
        txt = _gerar_resumo_motivo("§5 remessa finaud", "DDR_2011", "Empresa X", th)
        assert "DDR Janeiro" in txt


# ---------------------------------------------------------------------------
# _tids_sem_reprocessar_triagem_fecho_anterior  (guard de imutabilidade)
# ---------------------------------------------------------------------------
class TestTidsSemReprocessarFechoAnterior:
    def test_co_anterior_a_dia_ref_e_preservado(self):
        """CONCLUÍDO com data < dia_ref → fica no conjunto 'não reprocessar'."""
        co = [_reg("t1", data_co="2026-05-20")]
        out = _tids_sem_reprocessar_triagem_fecho_anterior(
            [], co, date(2026, 6, 1), "DDR4111", mapa_t={"t1": _th("t1")}, por_tid={}
        )
        assert "t1" in out

    def test_co_posterior_a_dia_ref_e_excluido(self):
        """CONCLUÍDO com data > dia_ref → também excluído da triagem truncada (H2)."""
        co = [_reg("t1", data_co="2026-06-10")]
        out = _tids_sem_reprocessar_triagem_fecho_anterior(
            [], co, date(2026, 6, 1), "DDR4111", mapa_t={"t1": _th("t1")}, por_tid={}
        )
        assert "t1" in out

    def test_dia_ref_none_protege_co_sem_msg_nova(self):
        """Sem dia_ref: CO sem mensagem nova após conclusão é protegido."""
        co = [_reg("t1", data_co="2026-06-01")]
        out = _tids_sem_reprocessar_triagem_fecho_anterior(
            [], co, None, "DDR4111", mapa_t={"t1": _th("t1")}, por_tid={}
        )
        assert "t1" in out
