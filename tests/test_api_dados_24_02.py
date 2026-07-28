"""
QA – API /api/dados retorna pendentes para data 24/02/2026.

Valida que a API retorna eventos e pendentes_ids quando data=2026-02-24,
garantindo que e-mails do dia 24/02 apareçam no Dashboard Operacional.

Alinhado à correção "Pendentes acumulam + fallback para 24/02" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import os

from tests.conftest import RAIZ

if RAIZ not in __import__("sys").path:
    __import__("sys").path.insert(0, RAIZ)

ARQUIVO_03 = os.path.join(RAIZ, "data", "json", "03_integrador_dados_site.json")


def test_api_dados_24_02_retorna_eventos_e_pendentes():
    """
    GET /api/dados?data=2026-02-24 deve retornar hoje com eventos e pendentes_ids não vazios.
    Simula o fluxo do frontend ao selecionar DATA REF 24/02/2026.
    """
    from painel_oraculo import app

    if not os.path.isfile(ARQUIVO_03):
        return  # Sem 03, pula

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        r = client.get("/api/dados?data=2026-02-24")
        assert r.status_code == 200, f"Esperado 200, obteve {r.status_code}"

        data = r.get_json()
        assert data is not None, "Resposta não é JSON"
        assert "error" not in data or not data["error"], f"API retornou erro: {data.get('error')}"

        hoje = data.get("hoje", [])
        pendentes_ids = data.get("pendentes_ids", [])

        assert len(hoje) > 0, (
            f"API retornou hoje vazio para 24/02. "
            f"Verifique se 03_integrador_dados_site.json tem eventos com data 24/02."
        )
        assert len(pendentes_ids) > 0, (
            f"API retornou pendentes_ids vazio para 24/02. "
            f"Pendentes devem acumular independente da data."
        )

        # Simula lógica do frontend: threads com atividade em 24/02 devem estar em pendentes ou ter eh_hoje
        tids_hoje = {e.get("threadId") for e in hoje if e.get("threadId")}
        com_eh_hoje = [e for e in hoje if e.get("eh_hoje")]
        pendentes_set = set(pendentes_ids)
        inter = pendentes_set & tids_hoje

        assert len(inter) > 0 or len(com_eh_hoje) > 0, (
            f"Nenhum pendente com atividade em 24/02. "
            f"pendentes_ids={len(pendentes_ids)}, eh_hoje={len(com_eh_hoje)}"
        )


def test_api_dados_aceita_data_dd_mm_yyyy():
    """API deve aceitar data em DD/MM/YYYY (normalizarDataParaApi no frontend)."""
    from painel_oraculo import app

    if not os.path.isfile(ARQUIVO_03):
        return

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        # Frontend pode enviar 24/02/2026; backend _parse_data_ref aceita
        for param in ["2026-02-24", "24/02/2026"]:
            r = client.get(f"/api/dados?data={param}")
            assert r.status_code == 200, f"data={param!r}: esperado 200, obteve {r.status_code}"
            data = r.get_json()
            if data and "error" not in data:
                assert len(data.get("hoje", [])) > 0, f"data={param!r}: hoje vazio"


TESTS = [
    test_api_dados_24_02_retorna_eventos_e_pendentes,
    test_api_dados_aceita_data_dd_mm_yyyy,
]
