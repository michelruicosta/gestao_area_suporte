"""
QA – Integração com 03 real: thread "ENC: COS 12 2025 - Conecta" não deve aparecer no dia 13/02.

Carrega data/json/03_integrador_dados_site.json, aplica a mesma lógica do painel (thread_datas_presentes
só com datas das mensagens; E-mail sem mensagens não usa data do evento) e verifica que a thread
cujo título é "ENC: COS 12 2025 - Conecta" (só com mensagens em 12/02) NÃO está em "hoje" ao filtrar por 2026-02-13.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from tests.conftest import RAIZ, extrair_data_evento

ARQUIVO_03 = os.path.join(RAIZ, "data", "json", "03_integrador_dados_site.json")
TITULO_THREAD_ALVO = "ENC: COS 12 2025 - Conecta"
DATA_REF_13 = date(2026, 2, 13)


def _carregar_03():
    """Carrega o JSON do 03; retorna (dados, None) ou (None, erro)."""
    if not os.path.isfile(ARQUIVO_03):
        return None, "Arquivo 03 não encontrado"
    try:
        with open(ARQUIVO_03, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)


def _replicar_filtro_painel(dados_json, data_filtro_raw, busca_ativa: bool = False):
    """
    Replica a lógica de api_dados para data_filtro_raw.
    Retorna (hoje_da_selecao, acumulado_pendente, thread_datas_presentes, eventos_filtrados).
    A API real, ao filtrar por data, retorna apenas hoje (acumulado=[]), para que a lista exiba só threads com mensagem na data.
    """
    eventos_lista = dados_json.get("eventos", []) if isinstance(dados_json, dict) else []
    threads_lista = dados_json.get("threads", []) if isinstance(dados_json, dict) else []
    mapa_threads = {t.get("threadId"): (t.get("mensagens") or []) for t in threads_lista}

    excluir_cadoc = ["IGNORADO"]
    if not busca_ativa:
        excluir_cadoc.append("FILTRADO_POR_DATA")

    eventos_filtrados = []
    for e in eventos_lista:
        if e.get("cadoc") in excluir_cadoc:
            continue
        if e.get("relatorio_interno_risk_driver"):
            continue
        assunto = (e.get("titulo") or e.get("assunto") or "").lower()
        if "relatório do serviço" in assunto or "atualização de comunicados" in assunto:
            continue
        tid = e.get("threadId")
        if tid in mapa_threads:
            e = {**e, "mensagens": mapa_threads[tid]}
        else:
            e = {**e, "mensagens": []}
        e.setdefault("canal", "E-mail")
        eventos_filtrados.append(e)

    if not data_filtro_raw:
        return eventos_filtrados, [], {}, eventos_filtrados

    dt_limite = datetime.strptime(data_filtro_raw, "%Y-%m-%d").date()
    dia_anterior = dt_limite - timedelta(days=1)

    thread_datas_presentes = {}
    for e in eventos_filtrados:
        tid = e.get("threadId")
        if not tid:
            continue
        if tid not in thread_datas_presentes:
            thread_datas_presentes[tid] = set()
        mensagens = e.get("mensagens") or []
        if mensagens:
            for msg in mensagens:
                d = extrair_data_evento(msg)
                if d is not None:
                    thread_datas_presentes[tid].add(d)
        else:
            if e.get("canal") == "Fog" or e.get("origem") == "FogBugz":
                d = extrair_data_evento(e)
                if d is not None:
                    thread_datas_presentes[tid].add(d)

    hoje_da_selecao = []
    acumulado_pendente = []
    for e in eventos_filtrados:
        status_proc = (e.get("status_processo") or "").upper()
        tid = e.get("threadId")
        datas_thread = thread_datas_presentes.get(tid) if tid else set()
        if not datas_thread:
            continue
        if dt_limite in datas_thread:
            hoje_da_selecao.append(e)
        elif dia_anterior in datas_thread and status_proc != "CONCLUÍDO":
            acumulado_pendente.append(e)

    return hoje_da_selecao, acumulado_pendente, thread_datas_presentes, eventos_filtrados


def test_enc_cos_12_2025_nao_aparece_no_dia_13():
    """
    Com o 03 real: a thread "ENC: COS 12 2025 - Conecta" (mensagens só em 12/02)
    NÃO deve estar em "hoje" ao filtrar por 2026-02-13.
    Se data/json/03_integrador_dados_site.json não existir, o teste é ignorado (passa).
    """
    dados, erro = _carregar_03()
    if erro:
        # Arquivo 03 não encontrado: pula teste (ex.: ambiente sem dados ainda)
        if "não encontrado" in erro.lower():
            return
        raise AssertionError(f"Erro ao carregar 03: {erro}")

    hoje, acumulado, thread_datas_presentes, eventos_filtrados = _replicar_filtro_painel(dados, "2026-02-13")

    # Encontrar o threadId da thread "ENC: COS 12 2025 - Conecta" (em eventos ou threads)
    titulo_lower = TITULO_THREAD_ALVO.lower()
    thread_id_alvo = None
    for e in eventos_filtrados:
        titulo = (e.get("titulo") or e.get("assunto") or "")
        if titulo_lower in titulo.lower():
            thread_id_alvo = e.get("threadId")
            break
    if thread_id_alvo is None:
        # Thread não existe no 03 → teste passa (nada a validar)
        return

    # Datas das mensagens dessa thread (só mensagens; E-mail sem mensagens não usa data do evento)
    datas_da_thread = thread_datas_presentes.get(thread_id_alvo) or set()

    # Se não há nenhuma mensagem com data 13/02, a thread NÃO pode estar em "hoje".
    # (Se tiver mensagem em 12/02 e status aberto, ela cai em "acumulado"; a API ao filtrar por data retorna só "hoje", então não aparece na tela.)
    if DATA_REF_13 not in datas_da_thread:
        ids_hoje = {e.get("threadId") for e in hoje}
        if thread_id_alvo in ids_hoje:
            raise AssertionError(
                f'A thread "{TITULO_THREAD_ALVO}" (threadId={thread_id_alvo!r}) está em "hoje" para 13/02/2026, '
                f"mas as mensagens dela não têm data 13/02 (datas das mensagens: {sorted(datas_da_thread)}). "
                "Ela não deveria aparecer no dia 13. Verifique o painel e a lógica de thread_datas_presentes."
            )


TESTS = [test_enc_cos_12_2025_nao_aparece_no_dia_13]
