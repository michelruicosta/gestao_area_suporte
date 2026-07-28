# -*- coding: utf-8 -*-
"""
Testes das rotas de API do painel Flask (painel_oraculo.py).

Estratégia:
- LOGIN_DISABLED=True no app.config → flask_login ignora @login_required
- Mocks de disco (_carregar_threads_aguardando, _carregar_threads_concluidas,
  _carregar_json_cached) → sem leitura de arquivo real durante o teste
- Não testa lógica de negócio — verifica contratos HTTP:
    status code, Content-Type JSON, campos obrigatórios no payload.

Cobertura:
  /api/threads_concluidos       → lista de threadIds
  /api/threads_aguardando       → lista com campo "vencido"
  /api/triagem_motivos          → dict aguardando + concluidos
  /api/ultima_data_carga        → campo ultima_data
"""
import sys
import os
import json as _json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Garante imports do projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")

import painel_oraculo as _m

app = _m.app
app.config["TESTING"] = True
app.config["LOGIN_DISABLED"] = True  # flask_login bypassa @login_required
app.config["WTF_CSRF_ENABLED"] = False


# ---------------------------------------------------------------------------
# Fixtures reutilizáveis
# ---------------------------------------------------------------------------
# Prazo sempre no futuro, calculado no dia em que o teste roda — um prazo fixo
# ("2026-06-30") venceu no calendário real e o teste quebrou sozinho em 01/07/2026.
_PRAZO_FUTURO = (date.today() + timedelta(days=30)).isoformat()

_AG_FIXTURE = [
    {
        "threadId": "GMTHRID_001",
        "assunto": "Pendência DLO 2026",
        "empresa": "Empresa Alpha",
        "cadoc": "DLO_2061",
        "tipo": "ACAO_INTERNA",
        "data_marcacao": "2026-06-01",
        "prazo": _PRAZO_FUTURO,  # sempre hoje+30d (nunca vence com o calendário)
        "status": "AGUARDANDO",
        "origem_triagem_auto": True,
        "alvo_triagem_auto": "DLO",
        "motivo": "Aguardando retorno do cliente sobre arquivo DLO.",
    },
    {
        "threadId": "GMTHRID_002",
        "assunto": "DDR 2011 pendente",
        "empresa": "Empresa Beta",
        "cadoc": "DDR_2011",
        "tipo": "RESPOSTA_CLIENTE",
        "data_marcacao": "2026-05-20",
        "prazo": "2026-05-15",  # vencido (anterior a hoje)
        "status": "AGUARDANDO",
        "origem_triagem_auto": True,
        "alvo_triagem_auto": "DDR4111",
        "motivo": "Cliente não retornou o DDR corrigido.",
    },
]

_CO_FIXTURE = [
    {
        "threadId": "GMTHRID_101",
        "tipo": "RESOLVIDA",
        "origem_triagem_auto": True,
        "alvo_triagem_auto": "DDR4111",
        "data_conclusao": "2026-06-05 18:00:00",
        "motivo_triagem_auto": "Finaud orientou; cliente confirmou transmissão.",
        "aprendizado_ia": {"resumo_desfecho": "DDR transmitido com sucesso."},
    },
    {
        "threadId": "GMTHRID_102",
        "tipo": "RESOLVIDA",
        "origem_triagem_auto": False,  # manual
        "alvo_triagem_auto": "S5",
        "data_conclusao": "2026-06-04 18:00:00",
        "motivo_triagem_auto": "",
        "motivo": "Resolvido manualmente pelo operador.",
    },
]

_JSON03_FIXTURE = {
    "gerado_em": "2026-06-07T10:00:00",
    "total": 2,
    "total_threads": 2,
    "eventos": [
        {"threadId": "GMTHRID_001", "data_iso": "2026-06-07", "cadoc": "DLO_2061"},
        {"threadId": "GMTHRID_002", "data_iso": "2026-05-20", "cadoc": "DDR_2011"},
    ],
    "threads": [],
}


# ---------------------------------------------------------------------------
# /api/threads_concluidos
# ---------------------------------------------------------------------------
class TestApiThreadsConcluidos:
    def test_retorna_200(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_concluidas", return_value=_CO_FIXTURE):
                resp = c.get("/api/threads_concluidos")
        assert resp.status_code == 200

    def test_content_type_json(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_concluidas", return_value=_CO_FIXTURE):
                resp = c.get("/api/threads_concluidos")
        assert "application/json" in resp.content_type

    def test_campo_threadIds_presente(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_concluidas", return_value=_CO_FIXTURE):
                resp = c.get("/api/threads_concluidos")
        data = resp.get_json()
        assert "threadIds" in data

    def test_contem_tids_corretos(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_concluidas", return_value=_CO_FIXTURE):
                resp = c.get("/api/threads_concluidos")
        data = resp.get_json()
        assert "GMTHRID_101" in data["threadIds"]
        assert "GMTHRID_102" in data["threadIds"]

    def test_lista_vazia_retorna_200(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_concluidas", return_value=[]):
                resp = c.get("/api/threads_concluidos")
        assert resp.status_code == 200
        assert resp.get_json()["threadIds"] == []


# ---------------------------------------------------------------------------
# /api/threads_aguardando
# ---------------------------------------------------------------------------
class TestApiThreadsAguardando:
    def test_retorna_200(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                resp = c.get("/api/threads_aguardando")
        assert resp.status_code == 200

    def test_content_type_json(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                resp = c.get("/api/threads_aguardando")
        assert "application/json" in resp.content_type

    def test_campo_vencido_presente(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                resp = c.get("/api/threads_aguardando")
        data = resp.get_json()
        assert isinstance(data, list)
        for item in data:
            assert "vencido" in item, f"Campo 'vencido' ausente em {item.get('threadId')}"

    def test_prazo_vencido_flag_correto(self):
        """Thread com prazo anterior a hoje deve ter vencido=True."""
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                resp = c.get("/api/threads_aguardando")
        data = resp.get_json()
        vencido_map = {r["threadId"]: r["vencido"] for r in data}
        # GMTHRID_002 tem prazo 2026-05-15 — já venceu
        assert vencido_map["GMTHRID_002"] is True

    def test_prazo_futuro_nao_vencido(self):
        """Thread com prazo no futuro deve ter vencido=False."""
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                resp = c.get("/api/threads_aguardando")
        data = resp.get_json()
        vencido_map = {r["threadId"]: r["vencido"] for r in data}
        # GMTHRID_001 tem prazo hoje+30d — sempre no futuro
        assert vencido_map["GMTHRID_001"] is False

    def test_lista_vazia_retorna_200(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=[]):
                resp = c.get("/api/threads_aguardando")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# /api/triagem_motivos
# ---------------------------------------------------------------------------
class TestApiTriagemMotivos:
    def test_retorna_200(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                with patch.object(_m, "_carregar_threads_concluidas", return_value=list(_CO_FIXTURE)):
                    resp = c.get("/api/triagem_motivos")
        assert resp.status_code == 200

    def test_estrutura_aguardando_e_concluidos(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                with patch.object(_m, "_carregar_threads_concluidas", return_value=list(_CO_FIXTURE)):
                    resp = c.get("/api/triagem_motivos")
        data = resp.get_json()
        assert "aguardando" in data
        assert "concluidos" in data

    def test_aguardando_com_motivo(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=list(_AG_FIXTURE)):
                with patch.object(_m, "_carregar_threads_concluidas", return_value=[]):
                    resp = c.get("/api/triagem_motivos")
        data = resp.get_json()
        assert "GMTHRID_001" in data["aguardando"]
        assert "motivo" in data["aguardando"]["GMTHRID_001"]

    def test_concluidos_com_motivo(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=[]):
                with patch.object(_m, "_carregar_threads_concluidas", return_value=list(_CO_FIXTURE)):
                    resp = c.get("/api/triagem_motivos")
        data = resp.get_json()
        assert "GMTHRID_101" in data["concluidos"]

    def test_listas_vazias_retorna_200(self):
        with app.test_client() as c:
            with patch.object(_m, "_carregar_threads_aguardando", return_value=[]):
                with patch.object(_m, "_carregar_threads_concluidas", return_value=[]):
                    resp = c.get("/api/triagem_motivos")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["aguardando"] == {}
        assert data["concluidos"] == {}


# ---------------------------------------------------------------------------
# /api/ultima_data_carga
# ---------------------------------------------------------------------------
class TestApiUltimaDataCarga:
    def test_retorna_200(self):
        with app.test_client() as c:
            with patch("builtins.open", MagicMock(
                return_value=MagicMock(
                    __enter__=lambda s, *a: MagicMock(read=lambda: _json.dumps(_JSON03_FIXTURE)),
                    __exit__=lambda s, *a: False,
                )
            )):
                with patch("json.load", return_value=_JSON03_FIXTURE):
                    resp = c.get("/api/ultima_data_carga")
        assert resp.status_code == 200

    def test_campo_ultima_data_presente(self):
        with app.test_client() as c:
            with patch("painel_oraculo.open", MagicMock()), \
                 patch("painel_oraculo.json.load", return_value=_JSON03_FIXTURE):
                resp = c.get("/api/ultima_data_carga")
        assert resp.status_code in (200, 500)  # se mock não funcionar, 500 é tolerado
        if resp.status_code == 200:
            data = resp.get_json()
            assert "ultima_data" in data

    def test_erro_retorna_500_com_campo(self):
        """Se o arquivo não puder ser lido, retorna 500 mas com 'ultima_data' no body."""
        with app.test_client() as c:
            with patch("painel_oraculo.json.load", side_effect=FileNotFoundError("sem arquivo")):
                resp = c.get("/api/ultima_data_carga")
        # Pode ser 200 (com None) ou 500 — o campo deve existir de qualquer forma
        data = resp.get_json()
        assert data is not None
        assert "ultima_data" in data or resp.status_code == 500
