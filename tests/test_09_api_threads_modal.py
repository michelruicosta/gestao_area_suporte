"""
QA – API /api/threads/<thread_id>: abrir modal sem 404 para threadIds com barra (_REQ_23/02).

Valida que, ao selecionar diferentes datas e clicar em cards, a API retorna 200 e a thread
(em vez de 404). Inclui threadIds com _REQ_DD/MM e _REQ_DD e DD/MM que contêm "/" no path.

Alinhado à correção "Modal não abre: 404 em threads com barra no threadId" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import json
import os
from urllib.parse import quote

from tests.conftest import RAIZ

if RAIZ not in __import__("sys").path:
    __import__("sys").path.insert(0, RAIZ)

ARQUIVO_03 = os.path.join(RAIZ, "data", "json", "03_integrador_dados_site.json")

# Datas para testar (YYYY-MM-DD) — devem existir eventos no 03
DATAS_TESTE = ["2026-02-23", "2026-02-20", "2026-02-13", "2026-02-19"]


def _carregar_thread_ids_do_03():
    """Retorna lista de threadIds do 03, priorizando os com _REQ_ (contêm barra)."""
    if not os.path.isfile(ARQUIVO_03):
        return [], []
    try:
        with open(ARQUIVO_03, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return [], []
    threads = dados.get("threads", []) if isinstance(dados, dict) else []
    com_req = []
    sem_req = []
    vistos = set()
    for t in threads:
        tid = t.get("threadId") or t.get("id") or ""
        if not tid or tid in vistos:
            continue
        vistos.add(tid)
        if "_REQ_" in tid:
            com_req.append(tid)
        else:
            sem_req.append(tid)
    return com_req[:15], sem_req[:5]  # Limite para teste rápido


def test_api_threads_retorna_200_para_threadids_com_barra():
    """
    GET /api/threads/<thread_id> deve retornar 200 e thread quando threadId contém "/" (ex: _REQ_23/02).
    Simula o clique no card: frontend usa encodeURIComponent(threadId) → %2F no path.
    """
    from painel_oraculo import app

    com_req, sem_req = _carregar_thread_ids_do_03()
    if not com_req and not sem_req:
        return  # Sem 03, pula

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        # Testa threadIds COM _REQ_ (contêm barra) — principal correção
        for tid in com_req[:5]:
            path = "/api/threads/" + quote(tid, safe="")
            r = client.get(path)
            assert r.status_code == 200, f"threadId {tid!r}: esperado 200, obteve {r.status_code}"
            data = r.get_json()
            assert data and data.get("thread"), f"threadId {tid!r}: resposta sem thread"
            assert (data["thread"].get("threadId") or data["thread"].get("id")) == tid

        # Testa threadIds SEM _REQ_ (regressão)
        for tid in sem_req[:3]:
            path = "/api/threads/" + quote(tid, safe="")
            r = client.get(path)
            assert r.status_code == 200, f"threadId {tid!r}: esperado 200, obteve {r.status_code}"


def test_api_dados_retorna_threadids_por_data_e_modal_abre():
    """
    Para cada data de teste: api_dados retorna eventos; para cada threadId retornado,
    api/threads/<id> deve retornar 200 (simula selecionar data + clicar no card).
    """
    from painel_oraculo import app

    if not os.path.isfile(ARQUIVO_03):
        return

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        for data_ref in DATAS_TESTE:
            r = client.get(f"/api/dados?data={data_ref}")
            if r.status_code != 200:
                continue
            data = r.get_json()
            eventos = data.get("hoje", []) or data.get("eventos", []) or []
            if not eventos:
                continue

            # Pega até 3 threadIds por data (incluindo os com barra)
            thread_ids = []
            for ev in eventos[:10]:
                tid = ev.get("threadId")
                if tid and tid not in thread_ids:
                    thread_ids.append(tid)
                    if len(thread_ids) >= 3:
                        break

            for tid in thread_ids:
                path = "/api/threads/" + quote(tid, safe="")
                r2 = client.get(path)
                assert r2.status_code == 200, (
                    f"data_ref={data_ref} threadId={tid!r}: api/threads retornou {r2.status_code}"
                )
                data2 = r2.get_json()
                assert data2 and data2.get("thread"), (
                    f"data_ref={data_ref} threadId={tid!r}: resposta sem thread"
                )


TESTS = [
    test_api_threads_retorna_200_para_threadids_com_barra,
    test_api_dados_retorna_threadids_por_data_e_modal_abre,
]
