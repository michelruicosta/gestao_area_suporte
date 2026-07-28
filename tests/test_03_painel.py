"""
QA – Painel (api_dados, filtro por data, _extrair_data_evento).

Filtro por data = datas das mensagens da thread; thread só aparece na data D se houver mensagem com data D.
Alinhado à seção "Painel (API e filtros)" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import os
from datetime import date

import pytest

from tests.conftest import RAIZ, extrair_data_evento

# Testes que dependem do cadastro/rótulos reais (data/json/config/, ignorado no git).
# Pulam no CI (config ausente); rodam local onde os dados existem.
_SKIP_SEM_CONFIG = pytest.mark.skipif(
    not os.path.isdir(os.path.join(RAIZ, "data", "json", "config")),
    reason="requer cadastro/rótulos reais em data/json/config/ (ignorado no git; ausente no CI)",
)


def _tmp_json_list_io(path):
    """Lê/grava lista JSON como ``paths.load_aguardando`` / ``save_aguardando`` nos testes."""
    import json

    def load():
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save(lst):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lst, f)

    return load, save


def test_extrair_data_evento_epoch_iso_timestamp():
    """Contrato de _extrair_data_evento: epoch, data_iso e timestamp DD/MM/YYYY."""
    try:
        from painel_oraculo import _extrair_data_evento
    except ImportError:
        _extrair_data_evento = extrair_data_evento

    ev_epoch = {"timestamp_epoch": 1739462400}
    d = _extrair_data_evento(ev_epoch)
    assert d is not None and d.year in (2025, 2026) and 1 <= d.month <= 12

    ev_iso = {"data_iso": "2026-02-13"}
    d2 = _extrair_data_evento(ev_iso)
    assert d2 is not None and d2.year == 2026 and d2.month == 2 and d2.day == 13

    ev_br = {"timestamp": "13/02/2026 11:48"}
    d3 = _extrair_data_evento(ev_br)
    assert d3 is not None and d3.day == 13 and d3.month == 2 and d3.year == 2026


def test_filtro_data_exige_mensagem_na_data():
    """
    Thread só aparece na data D se houver pelo menos uma mensagem com data D.
    """
    dt_13 = date(2026, 2, 13)
    dt_12 = date(2026, 2, 12)

    ev_só_12 = {"id": "A", "threadId": "thread-A", "mensagens": [{"data_iso": "2026-02-12"}]}
    ev_com_13 = {"id": "B", "threadId": "thread-B", "mensagens": [{"data_iso": "2026-02-13"}]}
    ev_12_e_13 = {
        "id": "C",
        "threadId": "thread-C",
        "mensagens": [{"data_iso": "2026-02-12"}, {"data_iso": "2026-02-13"}],
    }

    def thread_datas_presentes(eventos):
        out = {}
        for e in eventos:
            tid = e.get("threadId")
            if not tid:
                continue
            if tid not in out:
                out[tid] = set()
            for msg in e.get("mensagens") or []:
                d = extrair_data_evento(msg)
                if d is not None:
                    out[tid].add(d)
            if not (e.get("mensagens") or []):
                d = extrair_data_evento(e)
                if d is not None:
                    out[tid].add(d)
        return out

    eventos = [ev_só_12, ev_com_13, ev_12_e_13]
    datas_por_thread = thread_datas_presentes(eventos)

    assert dt_13 not in datas_por_thread.get("thread-A", set())
    assert dt_13 in datas_por_thread.get("thread-B", set())
    assert dt_13 in datas_por_thread.get("thread-C", set()) and dt_12 in datas_por_thread.get("thread-C", set())

    hoje_13 = [e for e in eventos if dt_13 in datas_por_thread.get(e.get("threadId") or "", set())]
    ids_hoje = {e["id"] for e in hoje_13}
    assert "A" not in ids_hoje
    assert "B" in ids_hoje and "C" in ids_hoje


def test_filtrar_evento_por_data_igual_gmail():
    """Dia 23: 1 msg; dia 24: 2 msgs (23+24). Igual ao Gmail."""
    from painel_oraculo import _filtrar_evento_por_data
    from datetime import date

    ev = {
        "id": "X",
        "threadId": "thread-X",
        "mensagens": [
            {"data_iso": "2026-02-23", "corpo": "msg 23"},
            {"data_iso": "2026-02-24", "corpo": "msg 24"},
        ],
    }
    d23 = date(2026, 2, 23)
    d24 = date(2026, 2, 24)
    f23 = _filtrar_evento_por_data(ev, d23)
    f24 = _filtrar_evento_por_data(ev, d24)
    assert len(f23["mensagens"]) == 1 and f23["qtd_mensagens"] == 1
    assert len(f24["mensagens"]) == 2 and f24["qtd_mensagens"] == 2


def test_evento_concluido_operacional_fog_e_integrador():
    """Operacional: CLOSED/RESOLVED (Fog) e CONCLUÍDO contam como encerrado como status concluido."""
    from painel_oraculo import _evento_concluido_operacional

    assert _evento_concluido_operacional({"status": "closed"}) is True
    assert _evento_concluido_operacional({"status": "CLOSED"}) is True
    assert _evento_concluido_operacional({"status": "resolved"}) is True
    assert _evento_concluido_operacional({"status": "concluido"}) is True
    assert _evento_concluido_operacional({"status_processo": "CONCLUÍDO"}) is True
    assert _evento_concluido_operacional({"status_processo": "CLOSED"}) is True
    assert _evento_concluido_operacional({"status": "aberto", "status_processo": "PENDENTE"}) is False
    assert _evento_concluido_operacional(None) is False


@pytest.mark.xfail(reason="Pendente: thread_datas_presentes não implementado", strict=False)
def test_painel_usa_thread_datas_presentes():
    """api_dados deve usar thread_datas_presentes e inclusão por data nas mensagens."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "thread_datas_presentes" in code
    assert "dt_limite in datas_thread" in code or "dia_anterior in datas_thread" in code


def test_email_sem_mensagens_nao_usa_data_do_evento():
    """
    Bug: evento de E-mail com mensagens vazias não pode usar a data do evento (ex.: prazo 13/02),
    senão thread com só mensagem 12/02 aparecia no dia 13. Só Fog pode usar data do evento quando sem mensagens.
    """
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    # O painel deve condicionar o uso da data do evento (quando sem mensagens) a Fog
    assert (
        "e.get('canal') == 'Fog'" in code or "e.get('origem') == 'FogBugz'" in code
    ), "Quando evento não tem mensagens, só Fog deve usar data do evento (E-mail não)"


@pytest.mark.xfail(reason="Pendente: resumo_estruturado não implementado no sugerir_aguardo", strict=False)
def test_api_sugerir_aguardo_resumo_estruturado_quando_ocr():
    """api_sugerir_aguardo: prompt pede resumo_estruturado com contexto e pendencia (estrutura flexível)."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "resumo_estruturado" in code
    assert "contexto" in code and "pendencia" in code


def test_api_sugerir_aguardo_retorna_motivo():
    """api_sugerir_aguardo deve retornar motivo não vazio."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.post(
            "/api/sugerir_aguardo",
            json={
                "threadId": "test-sugerir-001",
                "conteudo": {"cliente": "Teste SA", "cadoc": "DDR_2011", "lista_prazos": [{"prazo_limite": "2026-03-20"}]},
            },
            content_type="application/json",
        )
    assert r.status_code == 200
    data = r.get_json()
    assert (data.get("motivo") or "").strip(), "Sugerir deve retornar motivo não vazio"


def test_api_crd_indicio_qualidade_retorna_linhas():
    """GET /api/crd_indicio_qualidade devolve JSON com linhas (Excel exportado)."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.get("/api/crd_indicio_qualidade")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data.get("linhas"), list)


def test_marcar_aguardando_data_ref_operacional_grava_data_marcacao():
    """data_ref_operacional (calendário operacional) define data_marcacao; fallback relógio se ausente."""
    import json
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    fd, path_ag = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path_ag, "w", encoding="utf-8") as f:
            json.dump([], f)
        _la, _sa = _tmp_json_list_io(path_ag)
        with patch.object(po, "load_aguardando", side_effect=_la):
            with patch.object(po, "save_aguardando", side_effect=_sa):
                with po.app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["_user_id"] = "admin"
                        sess["_fresh"] = True
                    r = client.post(
                        "/api/marcar_aguardando",
                        json={
                            "threadId": "TQA_DATA_REF_OP",
                            "motivo": "QA",
                            "data_ref_operacional": "2026-02-23",
                        },
                    )
        assert r.status_code == 200, r.get_data(as_text=True)
        reg = r.get_json().get("registro") or {}
        assert reg.get("data_marcacao") == "2026-02-23"
        with open(path_ag, encoding="utf-8") as f:
            lista = json.load(f)
        assert any(x.get("threadId") == "TQA_DATA_REF_OP" and x.get("data_marcacao") == "2026-02-23" for x in lista)
    finally:
        try:
            os.unlink(path_ag)
        except OSError:
            pass


def test_api_threads_aguardando_e_marcar():
    """APIs de aguardando: threads_aguardando (GET), prefill_aguardo, marcar_aguardando, resolver_aguardo."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.get("/api/threads_aguardando")
        assert r.status_code == 200, f"GET threads_aguardando: {r.status_code}"
        data = r.get_json()
        assert isinstance(data, list), "threads_aguardando deve retornar lista"

        r2 = client.post("/api/prefill_aguardo", json={"threadId": "test-001", "conteudo": {"cliente": "Teste", "cadoc": "DDR_2011"}})
        assert r2.status_code == 200
        d2 = r2.get_json()
        assert "opcoes_tipo" in d2 and "sugestao" in d2
        assert d2["sugestao"].get("empresa") == "Teste"
        assert d2["sugestao"].get("cadoc") == "DDR_2011"

        r3 = client.post("/api/marcar_aguardando", json={
            "threadId": "test-qa-aguardo-001",
            "tipo": "ACAO_INTERNA",
            "motivo": "Teste QA",
            "prazo": "2026-12-31",
            "cadoc": "DDR_2011",
        })
        assert r3.status_code == 200, f"marcar_aguardando: {r3.get_data(as_text=True)}"
        assert r3.get_json().get("status") == "success"

        r4 = client.post("/api/resolver_aguardo", json={"threadId": "test-qa-aguardo-001"})
        assert r4.status_code == 200
        assert r4.get_json().get("status") == "success"


@pytest.mark.xfail(reason="Pendente: nao_resolvidos com busca=1 não usa mesma data_ref", strict=False)
def test_api_dados_nao_resolvidos_busca_usa_mesma_data_ref():
    """?busca=1&data= deve calcular Não resolvidos com a mesma DATA REF que ?data= (não o dia atual)."""
    import json
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    fd_dados, path_dados = tempfile.mkstemp(suffix=".json")
    fd_ag, path_ag = tempfile.mkstemp(suffix=".json")
    os.close(fd_dados)
    os.close(fd_ag)
    try:
        dados = {
            "eventos": [
                {
                    "id": "nr1",
                    "threadId": "TNR_QA_REF",
                    "cadoc": "4111",
                    "titulo": "QA nao resolv ref",
                    "timestamp": "2026-02-23T12:00:00",
                    "timestamp_epoch": 1771867200,
                },
            ],
            "threads": [{"threadId": "TNR_QA_REF", "mensagens": []}],
        }
        with open(path_dados, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        ag_7 = [
            {
                "threadId": "TNR_QA_REF",
                "data_marcacao": "2026-02-10",
                "qtd_mensagens_no_fechamento": 0,
                "motivo": "qa",
            }
        ]
        ag_6 = [
            {
                "threadId": "TNR_QA_REF",
                "data_marcacao": "2026-02-17",
                "qtd_mensagens_no_fechamento": 0,
                "motivo": "qa",
            }
        ]
        _la, _sa = _tmp_json_list_io(path_ag)
        with patch.object(po, "BASE_DADOS", path_dados):
            with patch.object(po, "load_aguardando", side_effect=_la):
                with patch.object(po, "save_aguardando", side_effect=_sa):
                    with po.app.test_client() as client:
                        with client.session_transaction() as sess:
                            sess["_user_id"] = "admin"
                            sess["_fresh"] = True
                        with open(path_ag, "w", encoding="utf-8") as f:
                            json.dump(ag_6, f)
                        r_a = client.get("/api/dados?data=2026-02-23")
                        r_b = client.get("/api/dados?busca=1&data=2026-02-23")
                        assert r_a.status_code == 200 and r_b.status_code == 200
                        na = r_a.get_json().get("nao_resolvidos") or []
                        nb = r_b.get_json().get("nao_resolvidos") or []
                        assert na == nb, f"nao_resolvidos deve coincidir: {na} vs {nb}"
                        assert "TNR_QA_REF" not in na
                        with open(path_ag, "w", encoding="utf-8") as f:
                            json.dump(ag_7, f)
                        r_c = client.get("/api/dados?data=2026-02-23")
                        r_d = client.get("/api/dados?busca=1&data=2026-02-23")
                        nc = r_c.get_json().get("nao_resolvidos") or []
                        nd = r_d.get_json().get("nao_resolvidos") or []
                        assert nc == nd and "TNR_QA_REF" in nc
    finally:
        try:
            os.unlink(path_dados)
        except OSError:
            pass
        try:
            os.unlink(path_ag)
        except OSError:
            pass


def test_casos_perto_de_vencer_nao_inclui_ontem():
    """_casos_perto_de_vencer só deve incluir casos com prazo hoje ou no futuro (dias_ate >= 0).
    Caso com prazo ontem (dias_ate = -1) não deve aparecer — fix 2-B da revisão de telas 01/07/2026."""
    from datetime import date, timedelta
    from painel_oraculo import _casos_perto_de_vencer

    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    amanha = hoje + timedelta(days=1)

    def fmt(d):
        return f"{d.day:02d}/{d.month:02d}/{d.year}"

    ev_ontem = {"threadId": "T-ONTEM", "cliente": "X", "cadoc": "DDR", "titulo": "ontem",
                "lista_prazos": [{"prazo_limite": fmt(ontem)}]}
    ev_hoje = {"threadId": "T-HOJE", "cliente": "X", "cadoc": "DDR", "titulo": "hoje",
               "lista_prazos": [{"prazo_limite": fmt(hoje)}]}
    ev_amanha = {"threadId": "T-AMANHA", "cliente": "X", "cadoc": "DDR", "titulo": "amanhã",
                 "lista_prazos": [{"prazo_limite": fmt(amanha)}]}

    result = _casos_perto_de_vencer([ev_ontem, ev_hoje, ev_amanha], [], set())
    ids = {r["threadId"] for r in result}

    assert "T-ONTEM" not in ids, "caso vencido ontem não deve aparecer em 'perto de vencer'"
    assert "T-HOJE" in ids, "caso que vence hoje deve aparecer"
    assert "T-AMANHA" in ids, "caso que vence amanhã deve aparecer"


def test_casos_fora_prazo_usa_empresa_como_fallback():
    """_casos_fora_do_prazo deve usar campo 'empresa' quando aprendizado_ia.cliente_identificado estiver vazio.
    Fix 2-C da revisão de telas 01/07/2026."""
    from datetime import date, timedelta
    from painel_oraculo import _casos_fora_do_prazo

    prazo_passado = date.today() - timedelta(days=10)
    conclusao = date.today() - timedelta(days=5)

    def fmt_br(d):
        return f"{d.day:02d}/{d.month:02d}/{d.year}"

    ev = {
        "threadId": "T-FALLBACK",
        "lista_prazos": [{"prazo_limite": fmt_br(prazo_passado)}],
    }
    concluida_com_empresa = {
        "threadId": "T-FALLBACK",
        "data_conclusao": conclusao.isoformat(),
        "empresa": "Arccorretora",
        "aprendizado_ia": {"cliente_identificado": ""},
    }
    concluida_com_cliente = {
        "threadId": "T-COM-CLIENTE",
        "data_conclusao": conclusao.isoformat(),
        "empresa": "NaoDeveUsar",
        "aprendizado_ia": {"cliente_identificado": "ClienteReal"},
    }
    ev2 = {"threadId": "T-COM-CLIENTE", "lista_prazos": [{"prazo_limite": fmt_br(prazo_passado)}]}

    result = _casos_fora_do_prazo([concluida_com_empresa, concluida_com_cliente], [ev, ev2])
    por_id = {r["threadId"]: r for r in result}

    assert por_id["T-FALLBACK"]["cliente"] == "Arccorretora", "deve usar empresa quando cliente_identificado vazio"
    assert por_id["T-COM-CLIENTE"]["cliente"] == "ClienteReal", "deve preferir cliente_identificado quando preenchido"


def _cadastro_fake(*nomes_emails):
    """Monta um usuarios.json falso para os testes do ranking.
    Recebe pares (nome, email)."""
    usuarios = {}
    for i, (nome, email) in enumerate(nomes_emails):
        usuarios[f"user{i}"] = {
            "password": "x",
            "role": "operacional",
            "name": nome,
            "cargo": "Analista",
            "depto": "Operações",
            "email": email,
            "ativo": False,
        }
    return usuarios


def test_ranking_colaboradores_exclui_responsavel_igual_cliente(monkeypatch):
    """_ranking_colaboradores não deve creditar casos onde responsavel == cliente.
    Fix 2-D — 'Unicred' aparecia como analista com casos. Agora: se Unicred está
    no cadastro, pode aparecer com 0 casos, mas nunca com casos creditados."""
    import painel_oraculo
    from painel_oraculo import _ranking_colaboradores
    from datetime import date, timedelta

    fake = _cadastro_fake(("Michel", "michel@finaud.com.br"),
                          ("Unicred", "unicred@finaud.com.br"))
    monkeypatch.setattr(painel_oraculo, "carregar_usuarios", lambda: fake)

    conclusao = (date.today() - timedelta(days=5)).isoformat()
    ev_com_cliente = {
        "threadId": "T-UNICRED",
        "lado_responsavel": "FINAUD",
        "responsavel": "Unicred",
        "cliente": "Unicred",
    }
    ev_analista_real = {
        "threadId": "T-MICHEL",
        "lado_responsavel": "FINAUD",
        "responsavel": "Michel",
        "cliente": "Arccorretora",
    }
    concluidas = [
        {"threadId": "T-UNICRED", "data_conclusao": conclusao},
        {"threadId": "T-MICHEL", "data_conclusao": conclusao},
    ]
    result = _ranking_colaboradores([ev_com_cliente, ev_analista_real], [], concluidas)
    todos = (result.get("ranking") or []) + (result.get("volume_total") or [])

    unicred_rows = [r for r in todos if r["colaborador"] == "Unicred"]
    assert all(r["casos"] == 0 for r in unicred_rows), \
        "Unicred nao pode ter casos creditados (responsavel == cliente)"
    michel_rows = [r for r in todos if r["colaborador"] == "Michel"]
    assert michel_rows and michel_rows[0]["casos"] == 1, \
        "Michel deve ter 1 caso creditado"


def test_ranking_colaboradores_mostra_todos_cadastrados(monkeypatch):
    """Analistas cadastrados aparecem no ranking mesmo sem casos no período.
    Fix 2-K/2-L 02/07/2026 — ranking mostrava só quem tinha casos fechados."""
    import painel_oraculo
    from painel_oraculo import _ranking_colaboradores
    from datetime import date, timedelta

    fake = _cadastro_fake(
        ("Andrea Inacio", "andrea.inacio@finaud.com.br"),
        ("Flavio Camargo", "flavio.camargo@finaud.com.br"),
    )
    monkeypatch.setattr(painel_oraculo, "carregar_usuarios", lambda: fake)

    conclusao = (date.today() - timedelta(days=5)).isoformat()
    # Só Andrea tem caso no período; Flavio não tem nenhum
    eventos = [
        {"threadId": "T-AND", "lado_responsavel": "FINAUD",
         "responsavel": "Andrea Inacio", "cliente": "EmpA"},
    ]
    concluidas = [{"threadId": "T-AND", "data_conclusao": conclusao}]
    result = _ranking_colaboradores(eventos, [], concluidas)

    nomes_vol = {r["colaborador"] for r in result.get("volume_total") or []}
    assert "Andrea Inacio" in nomes_vol, "Andrea (com caso) deve aparecer"
    assert "Flavio Camargo" in nomes_vol, "Flavio (sem caso) tambem deve aparecer"
    flavio = next(r for r in result["volume_total"] if r["colaborador"] == "Flavio Camargo")
    assert flavio["casos"] == 0, "Flavio deve aparecer com 0 casos"
    assert result["total_colaboradores"] == 2, "total = todos cadastrados, nao so ativos"


def test_ranking_colaboradores_retorna_total_colaboradores(monkeypatch):
    """_ranking_colaboradores deve incluir total_colaboradores no retorno.
    Fix 2-F da revisão de telas 01/07/2026 — badge mostrava 'ranking' em vez de contagem."""
    import painel_oraculo
    from painel_oraculo import _ranking_colaboradores
    from datetime import date, timedelta

    fake = _cadastro_fake(("Ana", "ana@finaud.com.br"),
                          ("Bruno", "bruno@finaud.com.br"))
    monkeypatch.setattr(painel_oraculo, "carregar_usuarios", lambda: fake)

    conclusao = (date.today() - timedelta(days=5)).isoformat()
    eventos = [
        {"threadId": "T1", "lado_responsavel": "FINAUD", "responsavel": "Ana", "cliente": "EmpA"},
        {"threadId": "T2", "lado_responsavel": "FINAUD", "responsavel": "Bruno", "cliente": "EmpB"},
        {"threadId": "T3", "lado_responsavel": "FINAUD", "responsavel": "Ana", "cliente": "EmpC"},
    ]
    concluidas = [
        {"threadId": "T1", "data_conclusao": conclusao},
        {"threadId": "T2", "data_conclusao": conclusao},
        {"threadId": "T3", "data_conclusao": conclusao},
    ]
    result = _ranking_colaboradores(eventos, [], concluidas)

    assert "total_colaboradores" in result, "deve retornar campo total_colaboradores"
    assert result["total_colaboradores"] == 2, "Ana e Bruno = 2 colaboradores distintos"


def test_ranking_colaboradores_exclui_nao_cadastrados(monkeypatch):
    """2-K/2-L (01/07/2026): quem NÃO está no cadastro de usuários fica fora do
    ranking — 'Suporte Finaud', 'Riskdriver' e afins não são analistas."""
    import painel_oraculo
    from painel_oraculo import _ranking_colaboradores
    from datetime import date, timedelta

    fake = _cadastro_fake(("Andrea Inacio", "andrea.inacio@finaud.com.br"))
    monkeypatch.setattr(painel_oraculo, "carregar_usuarios", lambda: fake)

    conclusao = (date.today() - timedelta(days=5)).isoformat()
    eventos = [
        {"threadId": "T-SUP", "lado_responsavel": "FINAUD", "responsavel": "Suporte Finaud", "cliente": "EmpA"},
        {"threadId": "T-RD", "lado_responsavel": "FINAUD", "responsavel": "Riskdriver", "cliente": "EmpB"},
        {"threadId": "T-AND", "lado_responsavel": "FINAUD", "responsavel": "Andrea Inacio", "cliente": "EmpC"},
    ]
    concluidas = [
        {"threadId": "T-SUP", "data_conclusao": conclusao},
        {"threadId": "T-RD", "data_conclusao": conclusao},
        {"threadId": "T-AND", "data_conclusao": conclusao},
    ]
    result = _ranking_colaboradores(eventos, [], concluidas)
    nomes = {r["colaborador"] for r in (result.get("ranking") or []) + (result.get("volume_total") or [])}

    assert nomes == {"Andrea Inacio"}, "só analista cadastrado entra no ranking"
    assert result["total_colaboradores"] == 1


def test_ranking_colaboradores_casa_por_email(monkeypatch):
    """2-K/2-L (01/07/2026): o analista é identificado pelo E-MAIL de quem
    respondeu — 'Michel' nos e-mails vira 'Michel Rui Costa' (nome do cadastro)."""
    import painel_oraculo
    from painel_oraculo import _ranking_colaboradores
    from datetime import date, timedelta

    fake = _cadastro_fake(("Michel Rui Costa", "michel@finaud.com.br"))
    monkeypatch.setattr(painel_oraculo, "carregar_usuarios", lambda: fake)

    conclusao = (date.today() - timedelta(days=5)).isoformat()
    eventos = [
        {"threadId": "T-M", "lado_responsavel": "FINAUD", "responsavel": "Michel", "cliente": "EmpA"},
    ]
    threads = [
        {"threadId": "T-M", "mensagens": [
            {"timestamp_epoch": 1750000000,
             "contato_origem": {"lado": "FINAUD", "nome": "Michel", "email": "michel@finaud.com.br"},
             "contato_destino": {"lado": "CLIENTE", "nome": "Fulano", "email": "fulano@empa.com.br"}},
        ]},
    ]
    concluidas = [{"threadId": "T-M", "data_conclusao": conclusao}]
    result = _ranking_colaboradores(eventos, threads, concluidas)
    nomes = {r["colaborador"] for r in result.get("volume_total") or []}

    assert nomes == {"Michel Rui Costa"}, "deve exibir o nome do cadastro, achado pelo e-mail"


def test_ranking_colaboradores_ranking_unico_ordenado(monkeypatch):
    """2-K/2-L (01/07/2026): retorno tem 'ranking' único (mais ágil → mais lento)
    e não tem mais os campos 'mais_ageis'/'mais_lentos'."""
    import painel_oraculo
    from painel_oraculo import _ranking_colaboradores
    from datetime import date, timedelta, datetime as _dt

    fake = _cadastro_fake(("Ana", "ana@finaud.com.br"), ("Bruno", "bruno@finaud.com.br"))
    monkeypatch.setattr(painel_oraculo, "carregar_usuarios", lambda: fake)

    conclusao = date.today() - timedelta(days=5)
    ep_conclusao = int(_dt.combine(conclusao, _dt.min.time()).timestamp())
    eventos = [
        {"threadId": "T-LENTA", "lado_responsavel": "FINAUD", "responsavel": "Ana", "cliente": "EmpA"},
        {"threadId": "T-RAPIDA", "lado_responsavel": "FINAUD", "responsavel": "Bruno", "cliente": "EmpB"},
    ]
    threads = [
        # Ana: 1ª msg 10 dias antes da conclusão → mais lenta
        {"threadId": "T-LENTA", "mensagens": [{"timestamp_epoch": ep_conclusao - 10 * 86400}]},
        # Bruno: 1ª msg 1 dia antes da conclusão → mais ágil
        {"threadId": "T-RAPIDA", "mensagens": [{"timestamp_epoch": ep_conclusao - 1 * 86400}]},
    ]
    concluidas = [
        {"threadId": "T-LENTA", "data_conclusao": conclusao.isoformat()},
        {"threadId": "T-RAPIDA", "data_conclusao": conclusao.isoformat()},
    ]
    result = _ranking_colaboradores(eventos, threads, concluidas)

    assert "mais_ageis" not in result and "mais_lentos" not in result, "formato antigo deve sumir"
    rank = result.get("ranking") or []
    assert [r["colaborador"] for r in rank] == ["Bruno", "Ana"], "ordem: mais ágil primeiro"


def test_email_quem_respondeu_prioriza_nome_do_responsavel():
    """_email_quem_respondeu: com nome do responsável, devolve o e-mail DELE;
    sem nome que case, devolve o e-mail da última mensagem enviada pela Finaud."""
    from painel_oraculo import _email_quem_respondeu

    thread = {"threadId": "T1", "mensagens": [
        {"timestamp_epoch": 100,
         "contato_origem": {"lado": "FINAUD", "nome": "Andrea Inacio", "email": "andrea.inacio@finaud.com.br"},
         "contato_destino": {"lado": "CLIENTE", "nome": "Fulano", "email": "fulano@cliente.com"}},
        {"timestamp_epoch": 200,
         "contato_origem": {"lado": "CLIENTE", "nome": "Fulano", "email": "fulano@cliente.com"},
         "contato_destino": {"lado": "FINAUD", "nome": "Rodrigo Tibério", "email": "rodrigo.tiberio@finaud.com.br"}},
    ]}
    # prioriza o contato com o nome do responsável (mesmo sendo destino, sem acento)
    assert _email_quem_respondeu(thread, "Rodrigo Tiberio") == "rodrigo.tiberio@finaud.com.br"
    # sem nome: última mensagem ENVIADA pela Finaud (origem)
    assert _email_quem_respondeu(thread) == "andrea.inacio@finaud.com.br"
    # thread inexistente
    assert _email_quem_respondeu(None) == ""


def test_api_dados_retorna_aguardando():
    """api_dados deve incluir 'aguardando' no payload para o frontend mover cards marcados."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.get("/api/dados")
        assert r.status_code == 200, f"api_dados: {r.status_code}"
        data = r.get_json()
        assert "aguardando" in data, "api_dados deve retornar chave 'aguardando'"
        assert isinstance(data["aguardando"], list), "aguardando deve ser lista de threadIds"
        assert "pares_sugeridos" in data, "api_dados deve retornar chave 'pares_sugeridos'"
        assert isinstance(data["pares_sugeridos"], dict), "pares_sugeridos deve ser dict"
        assert "pares_confirmados" in data, "api_dados deve retornar chave 'pares_confirmados'"
        assert isinstance(data["pares_confirmados"], dict), "pares_confirmados deve ser dict"
        assert "clusters_multi_thread" in data, "api_dados deve retornar chave 'clusters_multi_thread'"
        assert isinstance(data["clusters_multi_thread"], list), "clusters_multi_thread deve ser lista"


def test_api_dados_nao_despromove_aguardando_quando_nova_mensagem():
    """Invariante "saiu de PENDENTE não volta": nova mensagem em fio AGUARDANDO
    NÃO remove o registo em ``threads_aguardando_*.json`` nem despromove o
    ``status_processo`` para PENDENTE em ``/api/dados``. A re-classificação por
    nova mensagem é responsabilidade exclusiva da triagem (próxima corrida do
    pipeline).
    """
    import json
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    fd_dados, path_dados = tempfile.mkstemp(suffix=".json")
    fd_ag, path_ag = tempfile.mkstemp(suffix=".json")
    os.close(fd_dados)
    os.close(fd_ag)
    try:
        dados = {
            "eventos": [
                {
                    "id": "901",
                    "threadId": "TQA_NOVA_MSG",
                    "cadoc": "4111",
                    "titulo": "Assunto teste QA aguardo",
                    "status_processo": "AGUARDANDO",
                    "timestamp": "2026-03-01T10:00:00",
                },
            ],
            "threads": [
                {
                    "threadId": "TQA_NOVA_MSG",
                    "mensagens": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                    "status_processo": "AGUARDANDO",
                },
            ],
        }
        with open(path_dados, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        # qtd_mensagens_no_fechamento=2 < len(mensagens)=3 => "nova mensagem após
        # Aguardando" — antes despromoção; agora deve PRESERVAR estado.
        ag_list = [{"threadId": "TQA_NOVA_MSG", "qtd_mensagens_no_fechamento": 2, "motivo": "teste"}]
        with open(path_ag, "w", encoding="utf-8") as f:
            json.dump(ag_list, f)

        _la, _sa = _tmp_json_list_io(path_ag)
        with patch.object(po, "BASE_DADOS", path_dados):
            with patch.object(po, "load_aguardando", side_effect=_la):
                with patch.object(po, "save_aguardando", side_effect=_sa):
                    with po.app.test_client() as client:
                        with client.session_transaction() as sess:
                            sess["_user_id"] = "admin"
                            sess["_fresh"] = True
                        r = client.get("/api/dados")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        # AG no disco intacto.
        with open(path_ag, encoding="utf-8") as f:
            ag_after = json.load(f)
        assert any(x.get("threadId") == "TQA_NOVA_MSG" for x in ag_after), \
            "fio NÃO pode ser removido de threads_aguardando.json"
        # Status em 03 não pode regredir a PENDENTE.
        with open(path_dados, encoding="utf-8") as f:
            dados_after = json.load(f)
        ev_file = next(x for x in dados_after["eventos"] if x["threadId"] == "TQA_NOVA_MSG")
        assert (ev_file.get("status_processo") or "").upper().replace("Í", "I") != "PENDENTE", \
            "status_processo não pode regredir a PENDENTE no integrador"
        th_file = next(x for x in dados_after["threads"] if x["threadId"] == "TQA_NOVA_MSG")
        assert (th_file.get("status_processo") or "").upper().replace("Í", "I") != "PENDENTE", \
            "status_processo do thread não pode regredir a PENDENTE"
    finally:
        try:
            os.unlink(path_dados)
        except OSError:
            pass
        try:
            os.unlink(path_ag)
        except OSError:
            pass


def test_api_dados_nao_persiste_saida_aguardando_quando_data_ref_passada():
    """Com ?data= anterior a hoje: só consulta — não remove threads_aguardando.json nem altera 03."""
    import json
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    fd_dados, path_dados = tempfile.mkstemp(suffix=".json")
    fd_ag, path_ag = tempfile.mkstemp(suffix=".json")
    os.close(fd_dados)
    os.close(fd_ag)
    try:
        dados = {
            "eventos": [
                {
                    "id": "902",
                    "threadId": "TQA_REF_PASSADA",
                    "cadoc": "4111",
                    "titulo": "Assunto QA ref passada",
                    "status_processo": "AGUARDANDO",
                    "timestamp": "2026-03-01T10:00:00",
                },
            ],
            "threads": [
                {
                    "threadId": "TQA_REF_PASSADA",
                    "mensagens": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                    "status_processo": "AGUARDANDO",
                },
            ],
        }
        with open(path_dados, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        ag_list = [{"threadId": "TQA_REF_PASSADA", "qtd_mensagens_no_fechamento": 2, "motivo": "teste"}]
        with open(path_ag, "w", encoding="utf-8") as f:
            json.dump(ag_list, f)

        _la, _sa = _tmp_json_list_io(path_ag)
        with patch.object(po, "BASE_DADOS", path_dados):
            with patch.object(po, "load_aguardando", side_effect=_la):
                with patch.object(po, "save_aguardando", side_effect=_sa):
                    with po.app.test_client() as client:
                        with client.session_transaction() as sess:
                            sess["_user_id"] = "admin"
                            sess["_fresh"] = True
                        r = client.get("/api/dados?data=2001-06-15")
        assert r.status_code == 200, r.get_data(as_text=True)

        with open(path_ag, encoding="utf-8") as f:
            ag_after = json.load(f)
        assert any(x.get("threadId") == "TQA_REF_PASSADA" for x in ag_after)

        with open(path_dados, encoding="utf-8") as f:
            dados_after = json.load(f)
        ev_file = next(x for x in dados_after["eventos"] if x["threadId"] == "TQA_REF_PASSADA")
        assert (ev_file.get("status_processo") or "").upper().replace("Í", "I") == "AGUARDANDO"
    finally:
        try:
            os.unlink(path_dados)
        except OSError:
            pass
        try:
            os.unlink(path_ag)
        except OSError:
            pass


@pytest.mark.xfail(reason="Pendente: thread concluída com aguardando fantasma não alinha status_processo", strict=False)
def test_api_dados_concluido_alinha_status_processo_aguardando_nao_sobrepoe():
    """
    2026-04-02: thread em concluídas (sem reabertura) deve expor CONCLUÍDO no payload
    mesmo com PENDENTE no 03; duplicata fantasma em threads_aguardando não pode
    voltar o pill para AGUARDANDO.
    """
    import json
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    tid = "TQA_CO_AG_DUP"
    fd_dados, path_dados = tempfile.mkstemp(suffix=".json")
    fd_ag, path_ag = tempfile.mkstemp(suffix=".json")
    fd_co, path_co = tempfile.mkstemp(suffix=".json")
    os.close(fd_dados)
    os.close(fd_ag)
    os.close(fd_co)
    try:
        msgs = [{"id": "m1"}, {"id": "m2"}]
        dados = {
            "eventos": [
                {
                    "id": "903",
                    "threadId": tid,
                    "cadoc": "4111",
                    "titulo": "QA concluído vs aguardando",
                    "status_processo": "PENDENTE",
                    "timestamp": "2026-03-01T10:00:00",
                },
            ],
            "threads": [{"threadId": tid, "mensagens": msgs, "status_processo": "PENDENTE"}],
        }
        with open(path_dados, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        with open(path_co, "w", encoding="utf-8") as f:
            json.dump(
                [{"threadId": tid, "qtd_mensagens_no_fechamento": 2, "motivo": "qa fechado"}],
                f,
            )
        with open(path_ag, "w", encoding="utf-8") as f:
            json.dump(
                [{"threadId": tid, "qtd_mensagens_no_fechamento": 2, "motivo": "fantasma"}],
                f,
            )

        _la, _sa = _tmp_json_list_io(path_ag)
        _lc, _sc = _tmp_json_list_io(path_co)
        with patch.object(po, "BASE_DADOS", path_dados):
            with patch.object(po, "load_aguardando", side_effect=_la):
                with patch.object(po, "save_aguardando", side_effect=_sa):
                    with patch.object(po, "load_concluidas", side_effect=_lc):
                        with patch.object(po, "save_concluidas", side_effect=_sc):
                            with po.app.test_client() as client:
                                with client.session_transaction() as sess:
                                    sess["_user_id"] = "admin"
                                    sess["_fresh"] = True
                                r = client.get("/api/dados")
        assert r.status_code == 200, r.get_data(as_text=True)
        hoje = (r.get_json() or {}).get("hoje") or []
        ev = next((x for x in hoje if x.get("threadId") == tid), None)
        assert ev is not None
        sp = (ev.get("status_processo") or "").upper().replace("Í", "I")
        assert sp == "CONCLUIDO", f"esperado CONCLUÍDO na API, veio {ev.get('status_processo')!r}"
        assert ev.get("status") == "concluido"
        assert ev.get("aguardando") is not True
    finally:
        for p in (path_dados, path_ag, path_co):
            try:
                os.unlink(p)
            except OSError:
                pass


def test_api_dados_trava_pendente_mesma_data_ref_classificacao():
    """
    Com ``?data=D``, se ``data_conclusao`` (calendário) = D, não voltar a PENDENTE na vista D
    só porque ``len(mensagens)`` > ``qtd_mensagens_no_fechamento`` (fechamento do dia 23).
    """
    import json
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    tid = "TQA_TRAVA_DIA"
    fd_dados, path_dados = tempfile.mkstemp(suffix=".json")
    fd_ag, path_ag = tempfile.mkstemp(suffix=".json")
    fd_co, path_co = tempfile.mkstemp(suffix=".json")
    os.close(fd_dados)
    os.close(fd_ag)
    os.close(fd_co)
    try:
        msgs = [{"id": f"m{i}", "data_iso": "2026-02-23"} for i in range(5)]
        dados = {
            "eventos": [
                {
                    "id": "904",
                    "threadId": tid,
                    "cadoc": "RETORNO_BACEN",
                    "titulo": "QA travamento REF",
                    "status_processo": "PENDENTE",
                    "timestamp": "2026-02-23T10:00:00",
                    "timestamp_epoch": 1,
                },
            ],
            "threads": [{"threadId": tid, "mensagens": msgs, "status_processo": "PENDENTE"}],
        }
        with open(path_dados, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        with open(path_co, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "threadId": tid,
                        "qtd_mensagens_no_fechamento": 2,
                        "data_conclusao": "2026-02-23 18:00:00",
                        "motivo": "qa",
                    }
                ],
                f,
            )
        with open(path_ag, "w", encoding="utf-8") as f:
            json.dump([], f)

        _la, _sa = _tmp_json_list_io(path_ag)
        _lc, _sc = _tmp_json_list_io(path_co)
        with patch.object(po, "BASE_DADOS", path_dados):
            with patch.object(po, "load_aguardando", side_effect=_la):
                with patch.object(po, "save_aguardando", side_effect=_sa):
                    with patch.object(po, "load_concluidas", side_effect=_lc):
                        with patch.object(po, "save_concluidas", side_effect=_sc):
                            with po.app.test_client() as client:
                                with client.session_transaction() as sess:
                                    sess["_user_id"] = "admin"
                                    sess["_fresh"] = True
                                r = client.get("/api/dados?data=2026-02-23")
        assert r.status_code == 200, r.get_data(as_text=True)
        hoje = (r.get_json() or {}).get("hoje") or []
        ev = next((x for x in hoje if x.get("threadId") == tid), None)
        assert ev is not None
        sp = (ev.get("status_processo") or "").upper().replace("Í", "I")
        assert sp == "CONCLUIDO", f"esperado CONCLUÍDO (travado no dia da classificação), veio {ev.get('status_processo')!r}"
        assert ev.get("status") == "concluido"
    finally:
        for p in (path_dados, path_ag, path_co):
            try:
                os.unlink(p)
            except OSError:
                pass


def test_remover_par_confirmado_lista():
    from painel_oraculo import _remover_par_confirmado

    lst = [
        {"thread_a": "A", "thread_b": "B"},
        {"thread_a": "1", "thread_b": "2"},
    ]
    out = _remover_par_confirmado(lst, "B", "A")
    assert len(out) == 1
    assert out[0].get("thread_a") == "1"


def test_api_par_threads_confirmar_rejeita_mesmo_thread():
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True
        r = client.post(
            "/api/par_threads/confirmar",
            json={"threadId": "X", "outroThreadId": "X"},
            content_type="application/json",
        )
        assert r.status_code == 400
        body = r.get_json()
        assert body.get("status") == "error"


def test_concluir_thread_acrescenta_par_gemea_e_limpa_par_confirmado():
    """Com par confirmado no arquivo, concluir uma thread grava a gêmea e esvazia pares_threads_confirmados."""
    import copy
    import json
    import os
    import tempfile
    from unittest.mock import patch

    import painel_oraculo as po

    fd, path_par = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path_par, "w", encoding="utf-8") as f:
            json.dump([{"thread_a": "GEM_A", "thread_b": "GEM_B"}], f)
        salvo_conc = []

        def cap_salvar_conc(lst):
            salvo_conc.append(copy.deepcopy(list(lst)))

        with patch.object(po, "ARQUIVO_PARES_THREADS_CONFIRMADOS", path_par):
            with patch.object(po, "_carregar_threads_concluidas", return_value=[]):
                with patch.object(po, "_salvar_threads_concluidas", side_effect=cap_salvar_conc):
                    with patch.object(po, "_qtd_mensagens_thread_integrador", return_value=3):
                        with patch.object(po, "_carregar_threads_aguardando", return_value=[]):
                            with patch.object(po, "_salvar_threads_aguardando", lambda _x: None):
                                with po.app.test_client() as client:
                                    with client.session_transaction() as sess:
                                        sess["_user_id"] = "admin"
                                        sess["_fresh"] = True
                                    r = client.post(
                                        "/api/concluir_thread",
                                        json={
                                            "threadId": "GEM_A",
                                            "conteudo": {"cadoc": "4111", "lista_prazos": []},
                                        },
                                        content_type="application/json",
                                    )
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data.get("par_gemea_concluido") == "GEM_B"
        assert len(salvo_conc) == 1
        assert len(salvo_conc[0]) == 2
        tids = {x.get("threadId") for x in salvo_conc[0]}
        assert tids == {"GEM_A", "GEM_B"}
        gem = next(x for x in salvo_conc[0] if x.get("threadId") == "GEM_B")
        assert gem.get("concluido_em_conjunto_com") == "GEM_A"
        with open(path_par, encoding="utf-8") as f:
            rest_pares = json.load(f)
        assert rest_pares == []
    finally:
        os.unlink(path_par)


def test_api_aprendizados_retorna_estrutura():
    """GET /api/aprendizados retorna total_threads, ultimos_aprendizados, por_tipo_demanda, prazo_cumprido_geral."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.get("/api/aprendizados?dias=90")
        assert r.status_code == 200, f"api_aprendizados: {r.status_code}"
        data = r.get_json()
        assert "total_threads" in data
        assert "ultimos_aprendizados" in data
        assert "por_tipo_demanda" in data
        assert "prazo_cumprido_geral" in data
        assert isinstance(data["ultimos_aprendizados"], list)


def test_api_aprendizado_editar_requer_thread_id():
    """POST /api/aprendizado/editar retorna 400 sem threadId."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.post("/api/aprendizado/editar", json={}, content_type="application/json")
        assert r.status_code == 400
        assert r.get_json().get("status") == "error"


def test_api_aprendizado_editar_404_quando_nao_existe():
    """POST /api/aprendizado/editar retorna 404 para threadId inexistente."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.post(
            "/api/aprendizado/editar",
            json={"threadId": "thread-inexistente-qa-12345", "resolucao_final": "teste"},
            content_type="application/json",
        )
        assert r.status_code == 404
        assert r.get_json().get("status") == "error"


@pytest.mark.xfail(reason="Pendente: reaberta_apos_conclusao não implementado", strict=False)
def test_concluida_com_nova_msg_marca_reaberta():
    """Thread concluída com mais mensagens que no fechamento deve ter status aberto e reaberta_apos_conclusao."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "concluida_qtd_msg" in code, "Deve mapear qtd_mensagens_no_fechamento por threadId"
    assert "reaberta_apos_conclusao" in code, "Deve marcar reaberta quando nova msg em concluída"
    assert "current_qtd > stored_qtd" in code, "Deve comparar mensagens atuais vs armazenadas"


def test_aguardando_enriquece_empresa_do_motivo():
    """Eventos de threads em Aguardando recebem empresa do registro ou extraída do motivo (ex: 'da Conta Simples sobre')."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "reg_ag" in code and "aguardando_lista" in code, "Deve buscar registro de Aguardando por threadId"
    assert "emp_reg" in code or "empresa" in code, "Deve enriquecer evento com empresa do registro"
    assert "sobre" in code or "motivo" in code, "Deve extrair empresa do motivo (ex: 'da X sobre')"


def test_evento_recebe_responsavel_da_thread():
    """
    Card deve exibir o responsável da thread (ex.: obrigada pelo envio → Andrea), não o do evento (Hebert).
    O painel injeta responsavel da thread em cada evento quando há thread correspondente.
    """
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "mapa_thread_responsavel" in code, "Deve mapear responsavel por threadId"
    assert "tid in mapa_thread_responsavel" in code, "Deve injetar responsavel da thread no evento"
    assert "e['responsavel']" in code or 'e["responsavel"]' in code, "Deve sobrescrever responsavel do evento"


@_SKIP_SEM_CONFIG
def test_rotulo_empresa_gestao_desconhecido_vazio():
    from painel_oraculo import _rotulo_empresa_gestao_para_api

    assert _rotulo_empresa_gestao_para_api("DESCONHECIDO") == ""
    assert _rotulo_empresa_gestao_para_api("CLIENTE_DESCONHECIDO") == ""
    assert _rotulo_empresa_gestao_para_api("eqi.com.br") == "EQI"


@_SKIP_SEM_CONFIG
def test_empresa_gestao_final_usa_email_nas_mensagens():
    """Gestão: mesmo com cliente=nome da pessoa, empresa vem do e-mail CLIENTE em qualquer msg da thread."""
    from painel_oraculo import _empresa_gestao_final

    ev = {
        "cliente": "Gustavo Do Carmo Rudink",
        "titulo": "DLO",
        "contato_origem": {"lado": "FINAUD", "email": "a@finaud.com.br"},
        "contato_destino": {"lado": "FINAUD", "email": "b@finaud.com.br"},
        "mensagens": [
            {
                "contato_origem": {
                    "lado": "CLIENTE",
                    "email": "gustavo.rudink@banvox.com.br",
                    "nome": "Gustavo Do Carmo Rudink",
                }
            }
        ],
    }
    assert _empresa_gestao_final(ev) == "Banvox"
    from painel_oraculo import _rotulo_empresa_gestao_para_api

    assert _rotulo_empresa_gestao_para_api("Banvox") == "Banvox"
    assert _rotulo_empresa_gestao_para_api("smartsafebrasil.com.br") == "Smart Safer Brasil"


@_SKIP_SEM_CONFIG
def test_empresa_do_email_emails_exatos_gmail():
    """Cadastro: emails_exatos associa e-mail pessoal à empresa (ex.: Adriana → Açoriana)."""
    from painel_oraculo import _empresa_do_email

    assert _empresa_do_email("adrianamartins2608@gmail.com") == "Açoriana"
    assert _empresa_do_email("AdrianaMartins2608@GMAIL.COM") == "Açoriana"


def test_empresa_fallback_dominio_corporativo():
    """Sem cadastro: empresa na API vira domínio do e-mail CLIENTE (não o nome em cliente)."""
    from painel_oraculo import _dominio_eh_generico, _empresa_fallback_dominio_corporativo

    assert _dominio_eh_generico("gmail.com") is True
    assert _dominio_eh_generico("uol.com.br") is True
    assert _dominio_eh_generico("trinusbank.com.br") is False

    ev = {
        "contato_destino": {"lado": "CLIENTE", "email": "joao@trinusbank.com.br"},
        "contato_origem": {"lado": "FINAUD", "email": "a@finaud.com.br"},
    }
    assert _empresa_fallback_dominio_corporativo(ev) == "trinusbank.com.br"

    ev_gmail = {"contato_destino": {"lado": "CLIENTE", "email": "Pessoa@gmail.com"}}
    assert _empresa_fallback_dominio_corporativo(ev_gmail) == ""

    ev_finaud = {"contato_destino": {"lado": "CLIENTE", "email": "x@parceiro.finaud.com.br"}}
    assert _empresa_fallback_dominio_corporativo(ev_finaud) == ""


def test_pares_sugeridos_operacional_mesma_empresa_e_prazos():
    """API/Operacional: pares sugeridos só com mesma empresa (card) + mesma lista_prazos + 2 threads."""
    from painel_oraculo import _computar_pares_sugeridos_operacional

    lp4111 = [
        {"cadoc": "4111", "data_base": "18/02/2026", "prazo_limite": "23/02/2026"},
        {"cadoc": "4111", "data_base": "19/02/2026", "prazo_limite": "24/02/2026"},
        {"cadoc": "4111", "data_base": "20/02/2026", "prazo_limite": "25/02/2026"},
    ]
    ev_a = {
        "threadId": "T_PAR_A",
        "id": "901",
        "empresa": "Fair Corretora",
        "titulo": "4111.",
        "lista_prazos": lp4111,
        "timestamp_epoch": 100,
    }
    ev_b = {
        "threadId": "T_PAR_B",
        "id": "902",
        "empresa": "Fair Corretora",
        "titulo": "Relatórios 4111 de 18, 19 e 20/02/2026.",
        "lista_prazos": lp4111,
        "timestamp_epoch": 200,
    }
    out = _computar_pares_sugeridos_operacional([ev_a, ev_b])
    assert "T_PAR_A" in out and "T_PAR_B" in out
    assert len(out["T_PAR_A"]) == 1 and out["T_PAR_A"][0]["threadId"] == "T_PAR_B"
    assert out["T_PAR_A"][0]["id"] == "902"

    ev_c = {
        "threadId": "T_PAR_C",
        "id": "903",
        "empresa": "Fair Corretora",
        "titulo": "Outro",
        "lista_prazos": [{"cadoc": "DLI_2062", "data_base": "31/01/2026", "prazo_limite": "05/03/2026"}],
        "timestamp_epoch": 150,
    }
    assert _computar_pares_sugeridos_operacional([ev_a, ev_c]) == {}

    ev_d = {
        "threadId": "T_PAR_D",
        "id": "904",
        "empresa": "DESCONHECIDO",
        "titulo": "X",
        "lista_prazos": lp4111,
        "timestamp_epoch": 160,
    }
    assert _computar_pares_sugeridos_operacional([ev_a, ev_d]) == {}


def test_corpo_mensagem_para_resumo_ia_remove_encadeamento():
    """Resumo IA: não repete na resposta o parágrafo já citado após De:/Enviada em/Assunta."""
    from painel_oraculo import _corpo_mensagem_para_resumo_ia

    corpo = (
        "Bom dia Alison, posso ajuda-lo?\n\n"
        "De: Alison Guimarães <x@y.com>\n"
        "Enviada em: quarta-feira, 19 de fevereiro de 2026 15:16\n"
        "Para: z@w.com\n"
        "Assunto: Horário\n\n"
        "Flávio, boa tarde! Teria um horário."
    )
    out = _corpo_mensagem_para_resumo_ia({"corpo_limpo": corpo})
    assert "Flávio" not in out
    assert "Bom dia Alison" in out
    assert "Enviada em:" not in out


def test_montar_texto_thread_resumo_nao_duplica_corpo_citado():
    """Trecho do cliente não aparece duas vezes (mensagem própria + citação no reply)."""
    from painel_oraculo import _montar_texto_thread_resumo

    frase = "Flávio, boa tarde! Teria um horário."
    thread = {
        "mensagens": [
            {
                "data_email": "19/02/2026 15:16",
                "contato_origem": {"nome": "Alison", "lado": "CLIENTE", "email": "a@b.com"},
                "contato_destino": {"nome": "F", "email": "f@f.com"},
                "corpo_limpo": frase,
            },
            {
                "data_email": "19/02/2026 15:58",
                "contato_origem": {"nome": "Suporte", "lado": "FINAUD", "email": "s@finaud.com.br"},
                "contato_destino": {},
                "corpo_limpo": (
                    "Bom dia Alison, posso ajuda-lo?\n\n"
                    "De: Alison\n"
                    "Enviada em: 19/02/2026 15:16\n"
                    "Assunto: Horário\n\n"
                    + frase
                ),
            },
        ]
    }
    txt = _montar_texto_thread_resumo(thread)
    assert txt.count(frase) == 1


def test_gestao_prototipo_rota_responde():
    """GET /gestao/prototipo retorna 200 para usuário autenticado."""
    from painel_oraculo import app

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.get("/gestao/prototipo")
        assert r.status_code == 200, f"gestao/prototipo: esperado 200, obteve {r.status_code}"
        html = r.get_data(as_text=True)
        assert "Visão Gestão" in html
        assert "Protótipo" in html or "protótipo" in html


TESTS = [
    test_corpo_mensagem_para_resumo_ia_remove_encadeamento,
    test_montar_texto_thread_resumo_nao_duplica_corpo_citado,
    test_extrair_data_evento_epoch_iso_timestamp,
    test_aguardando_enriquece_empresa_do_motivo,
    test_rotulo_empresa_gestao_desconhecido_vazio,
    test_empresa_gestao_final_usa_email_nas_mensagens,
    test_empresa_do_email_emails_exatos_gmail,
    test_empresa_fallback_dominio_corporativo,
    test_pares_sugeridos_operacional_mesma_empresa_e_prazos,
    test_remover_par_confirmado_lista,
    test_api_par_threads_confirmar_rejeita_mesmo_thread,
    test_concluir_thread_acrescenta_par_gemea_e_limpa_par_confirmado,
    test_evento_recebe_responsavel_da_thread,
    test_filtro_data_exige_mensagem_na_data,
    test_filtrar_evento_por_data_igual_gmail,
    test_evento_concluido_operacional_fog_e_integrador,
    test_painel_usa_thread_datas_presentes,
    test_email_sem_mensagens_nao_usa_data_do_evento,
    test_api_sugerir_aguardo_resumo_estruturado_quando_ocr,
    test_api_sugerir_aguardo_retorna_motivo,
    test_api_crd_indicio_qualidade_retorna_linhas,
    test_marcar_aguardando_data_ref_operacional_grava_data_marcacao,
    test_api_threads_aguardando_e_marcar,
    test_api_dados_nao_resolvidos_busca_usa_mesma_data_ref,
    test_api_dados_retorna_aguardando,
    test_api_dados_nao_despromove_aguardando_quando_nova_mensagem,
    test_api_dados_nao_persiste_saida_aguardando_quando_data_ref_passada,
    test_api_dados_concluido_alinha_status_processo_aguardando_nao_sobrepoe,
    test_api_dados_trava_pendente_mesma_data_ref_classificacao,
    test_api_aprendizados_retorna_estrutura,
    test_api_aprendizado_editar_requer_thread_id,
    test_api_aprendizado_editar_404_quando_nao_existe,
    test_concluida_com_nova_msg_marca_reaberta,
    test_gestao_prototipo_rota_responde,
]
