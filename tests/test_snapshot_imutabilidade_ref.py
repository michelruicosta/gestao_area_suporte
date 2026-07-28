# -*- coding: utf-8 -*-
"""Imutabilidade dos cartões por DATA REF após nova carga / conclusão posterior."""

from __future__ import annotations


def _dados_tid_e_dia_evento(tid: str, dia_iso: str) -> dict:
    return {
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR4111",
                "titulo": "Caso teste imutabilidade",
                "timestamp_epoch": 100,
                "timestamp": f"{dia_iso}T10:00:00",
                "data_iso": dia_iso,
            }
        ],
        "threads": [
            {
                "threadId": tid,
                "mensagens": [{"data_iso": dia_iso, "timestamp": f"{dia_iso}T10:00:00"}],
            }
        ],
    }


def _dados_min_tid(tid: str) -> dict:
    return _dados_tid_e_dia_evento(tid, "2026-02-23")


def test_vista_ref_antiga_mantem_aguardando_apos_conclusao_posterior(monkeypatch):
    """Conclusão no dia 24 não altera AGUARDANDO na vista REF 23 (com snapshot persistido)."""
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_IMUT_AG_01"
    dados = _dados_min_tid(tid)

    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-24 10:00:00",
            "qtd_mensagens_no_fechamento": 2,
            "marcacao_aguardante_pre_conclusao": "2026-02-23 08:00:00",
            "origem_aguardante_triagem_auto": True,
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-23")
    payload = out.get("payload") or {}
    todos = (
        payload.get("hoje", [])
        + payload.get("acumulado", [])
        + payload.get("nao_resolvidos_eventos", [])
        + payload.get("todos_flat", [])  # defensivo
    )
    ev = next((x for x in todos if isinstance(x, dict) and x.get("threadId") == tid), None)
    assert ev is not None, payload
    assert (ev.get("status_processo") or "").strip().upper() == "AGUARDANDO"
    assert ev.get("aguardando") is True


def test_vista_ref_antiga_sem_marca_backfill_fica_pendente(monkeypatch):
    """Registo antigo sem marcacao_*: vista anterior mostra PENDENTE (não CONCLUÍDO global)."""
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_IMUT_PEND_NO_SNAP"
    dados = _dados_min_tid(tid)
    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-24 10:00:00",
            "qtd_mensagens_no_fechamento": 2,
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-23")
    payload = out.get("payload") or {}
    todos = payload.get("hoje", []) + payload.get("acumulado", []) + payload.get("nao_resolvidos_eventos", [])
    ev = next((x for x in todos if isinstance(x, dict) and x.get("threadId") == tid), None)
    assert ev is not None
    assert (ev.get("status_processo") or "").strip().upper() == "PENDENTE"
    assert ev.get("aguardando") is None or ev.get("aguardando") is False


def test_vista_ref_passada_nao_esvazia_pendente_com_mail_dias_posteriores(monkeypatch):
    """Subir dia 25+ não deve apagar dados do 23; REF 23 (passada) ainda lista pendente com vários dias de mail."""
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot
    from datetime import date as real_date

    class _DataSoHoje:
        @staticmethod
        def today():
            return real_date(2026, 2, 27)

    monkeypatch.setattr(mp, "date", _DataSoHoje)

    tid = "THREAD_HIST_MULTI_DIA"
    dados = {
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR4111",
                "titulo": "caso teste",
                "timestamp_epoch": 10,
                "timestamp": "2026-02-23T09:00:00",
                "data_iso": "2026-02-23",
            }
        ],
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {"data_iso": "2026-02-23", "timestamp": "2026-02-23T09:00:00"},
                    {"data_iso": "2026-02-25", "timestamp": "2026-02-25T11:00:00"},
                ],
            }
        ],
    }

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: [])
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-23")
    payload = out.get("payload") or {}
    todos = payload.get("hoje", []) + payload.get("acumulado", []) + payload.get("nao_resolvidos_eventos", [])
    ev = next((x for x in todos if isinstance(x, dict) and x.get("threadId") == tid), None)
    assert ev is not None, "Fio pendente com 23 e 25 deve continuar na vista REF 23 (histórica)"
    sp = (ev.get("status_processo") or "").strip().upper().replace("Í", "I")
    assert sp in ("", "PENDENTE") or (ev.get("status") or "").strip().lower() == "aberto"


def test_payload_aguardando_inclui_threads_co_com_marcacao_pre_em_vista_historica(monkeypatch):
    """Regressão: thread CONCLUÍDA no dia 24 com ``marcacao_aguardante_pre_conclusao``
    do dia 23 tem de aparecer em ``payload.aguardando`` quando a vista é REF 23.

    Sem este union, o front-end (que constrói ``AGUARDANDO_IDS`` a partir desse
    payload) não consegue excluir o threadId do contador «Pendentes», e o cartão
    aparece como PENDENTE na tela apesar de cada evento já trazer
    ``status_processo: "AGUARDANDO"``. Repro do bug reportado em iniciar_periodo_unico
    quando re-uploaded multi-dia.
    """
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_HIST_MAR_PRE"
    dados = _dados_tid_e_dia_evento(tid, "2026-02-23")
    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-24 18:00:00",
            "qtd_mensagens_no_fechamento": 2,
            "marcacao_aguardante_pre_conclusao": "2026-02-23",
            "origem_aguardante_triagem_auto": True,
            "alvo_triagem_auto": "DDR4111",
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-23")
    payload = out.get("payload") or {}
    aguardando_lista = payload.get("aguardando") or []
    aguardando_ids = set()
    for x in aguardando_lista:
        if isinstance(x, str):
            aguardando_ids.add(x)
        elif isinstance(x, dict):
            aguardando_ids.add(x.get("threadId"))
    assert tid in aguardando_ids, (
        "thread com marcacao_aguardante_pre_conclusao tem de estar em "
        "payload.aguardando na vista histórica (caso contrário o front-end "
        "conta-a como PENDENTE)"
    )


def test_co_anterior_com_msg_posterior_em_ref_intermedia_fica_concluido(monkeypatch):
    """Regra «saiu de pendente não volta»: CO em 23 + msg em 27 → REF 24 deve ser CONCLUÍDO.

    Reproduz o bug observado pelo utilizador: depois de subir 25..27, a vista
    REF 24 (e 25, 26) mostra fios CONCLUÍDOS no dia 23 como PENDENTE só porque
    chegou nova mensagem em 27. A vista histórica tem de ser imutável.

    O cenário tem dois eventos do mesmo fio (um em 23, outro em 24): o evento
    de 23 entra em ``acumulado`` (dia anterior à REF) e o de 24 entra em
    ``hoje`` — em qualquer dos casos o ``status_processo`` tem de ser
    CONCLUÍDO, nunca PENDENTE, porque a conclusão (CO=23 18:00) é anterior
    ou igual à REF=24.
    """
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_CO_23_MSG_27"
    dados = {
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DLI_2062",
                "titulo": "fio CO em 23 com msg posterior",
                "timestamp_epoch": 100,
                "timestamp": "2026-02-23T10:00:00",
                "data_iso": "2026-02-23",
            },
            {
                "threadId": tid,
                "cadoc": "DLI_2062",
                "titulo": "fio CO em 23 com msg posterior",
                "timestamp_epoch": 200,
                "timestamp": "2026-02-24T09:00:00",
                "data_iso": "2026-02-24",
            },
        ],
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {"data_iso": "2026-02-23", "timestamp": "2026-02-23T10:00:00"},
                    {"data_iso": "2026-02-24", "timestamp": "2026-02-24T09:00:00"},
                    {"data_iso": "2026-02-27", "timestamp": "2026-02-27T11:00:00"},
                ],
            }
        ],
    }
    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-23 18:00:00",
            "qtd_mensagens_no_fechamento": 1,  # só conhecia a msg do 23 ao concluir
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-24")
    payload = out.get("payload") or {}
    todos = (
        payload.get("hoje", [])
        + payload.get("acumulado", [])
        + payload.get("nao_resolvidos_eventos", [])
    )
    evs_do_fio = [x for x in todos if isinstance(x, dict) and x.get("threadId") == tid]
    sps = [(x.get("status_processo") or "").strip().upper() for x in evs_do_fio]
    assert evs_do_fio, "fio com evento em 24 deve aparecer no payload (em hoje)"
    assert "PENDENTE" not in sps, (
        f"fio CO em 23 não pode aparecer como PENDENTE em REF=24, obtido {sps}"
    )
    # Pelo menos uma ocorrência tem de ser explicitamente CONCLUÍDO (a do dia 24, em ``hoje``).
    assert any("CONCLU" in s for s in sps), sps


def test_co_anterior_com_msg_posterior_em_ref_da_msg_continua_concluido(monkeypatch):
    """A nova mensagem em 27 NÃO «pendentiza» retroactivamente o fio em 27;
    a regra «saiu de pendente, não volta» tem de valer mesmo no dia em que
    chegou a mensagem nova (a interacção pode ser sinalizada por outros campos
    como ``nova_interacao`` / ``monitorar_resposta``, mas não por reabrir o
    cartão como PENDENTE)."""
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_CO_23_MSG_27_REF_27"
    dados = {
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DLI_2062",
                "titulo": "fio CO em 23 vista no dia da msg nova",
                "timestamp_epoch": 100,
                "timestamp": "2026-02-23T10:00:00",
                "data_iso": "2026-02-23",
            }
        ],
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {"data_iso": "2026-02-23", "timestamp": "2026-02-23T10:00:00"},
                    {"data_iso": "2026-02-27", "timestamp": "2026-02-27T11:00:00"},
                ],
            }
        ],
    }
    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-23 18:00:00",
            "qtd_mensagens_no_fechamento": 1,
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-27")
    payload = out.get("payload") or {}
    todos = (
        payload.get("hoje", [])
        + payload.get("acumulado", [])
        + payload.get("nao_resolvidos_eventos", [])
    )
    ev = next((x for x in todos if isinstance(x, dict) and x.get("threadId") == tid), None)
    assert ev is not None
    assert (ev.get("status_processo") or "").strip().upper() == "CONCLUÍDO"


def test_reabertura_formal_volta_a_aguardando_apos_data_reabertura(monkeypatch):
    """Excepção legítima: reabertura formal (entrou em AG outra vez, com
    ``data_reabertura``). Para REF >= data_reabertura, o fio mostra AGUARDANDO,
    apesar do CO anterior. (A regra «saiu de pendente, não volta» continua
    cumprida: o fio não volta a PENDENTE — vai para AGUARDANDO.)"""
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_REABERTO_FORMAL"
    dados = {
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR4111",
                "titulo": "reabertura formal",
                "timestamp_epoch": 100,
                "timestamp": "2026-02-23T10:00:00",
                "data_iso": "2026-02-23",
            }
        ],
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {"data_iso": "2026-02-23", "timestamp": "2026-02-23T10:00:00"},
                    {"data_iso": "2026-02-26", "timestamp": "2026-02-26T08:00:00"},
                ],
            }
        ],
    }
    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-23 18:00:00",
            "qtd_mensagens_no_fechamento": 1,
        }
    ]
    aguard = [
        {
            "threadId": tid,
            "data_marcacao": "2026-02-26 08:00:00",
            "data_conclusao_anterior": "2026-02-23",
            "data_reabertura": "2026-02-26",
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "DDR4111",
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: aguard)
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    # REF entre CO_anterior e reabertura → não deve listar como PENDENTE/AGUARDANDO.
    # O fio pode estar fora dos buckets do payload (filtrado naturalmente porque é CONCLUÍDO),
    # mas se aparecer, NÃO pode estar como PENDENTE nem AGUARDANDO.
    out_25 = montagem_api_dados_snapshot(dados, "2026-02-25")
    payload_25 = out_25.get("payload") or {}
    todos_25 = (
        payload_25.get("hoje", [])
        + payload_25.get("acumulado", [])
        + payload_25.get("nao_resolvidos_eventos", [])
    )
    sps_25 = [
        (x.get("status_processo") or "").strip().upper()
        for x in todos_25
        if isinstance(x, dict) and x.get("threadId") == tid
    ]
    assert "PENDENTE" not in sps_25 and "AGUARDANDO" not in sps_25, sps_25

    # REF == data_reabertura → AGUARDANDO (excepção da nova regra de trava)
    out_26 = montagem_api_dados_snapshot(dados, "2026-02-26")
    payload_26 = out_26.get("payload") or {}
    todos_26 = (
        payload_26.get("hoje", [])
        + payload_26.get("acumulado", [])
        + payload_26.get("nao_resolvidos_eventos", [])
    )
    ev_26 = next((x for x in todos_26 if isinstance(x, dict) and x.get("threadId") == tid), None)
    assert ev_26 is not None
    sp_26 = (ev_26.get("status_processo") or "").strip().upper()
    assert sp_26 == "AGUARDANDO", f"esperado AGUARDANDO em 26 (data_reabertura), obtido {sp_26!r}"


def test_vista_do_dia_da_conclusao_mostra_concluido(monkeypatch):
    import painel_oraculo as mp

    from painel_operacional_snapshot import montagem_api_dados_snapshot

    tid = "THREAD_IMUT_CO_MESMO_DIA"
    dados = _dados_tid_e_dia_evento(tid, "2026-02-24")
    conc = [
        {
            "threadId": tid,
            "data_conclusao": "2026-02-24 11:30:00",
            "qtd_mensagens_no_fechamento": 2,
            "marcacao_aguardante_pre_conclusao": "2026-02-23 08:00:00",
            "origem_aguardante_triagem_auto": True,
        }
    ]

    monkeypatch.setattr(mp, "_carregar_threads_concluidas", lambda: conc)
    monkeypatch.setattr(mp, "_carregar_threads_aguardando", lambda: [])
    monkeypatch.setattr(mp, "_carregar_eventos_fog", lambda: [])
    monkeypatch.setattr(mp, "load_cartao_overrides", lambda: {})
    monkeypatch.setattr(mp, "_threads_nova_interacao", lambda data_ref=None: [])

    out = montagem_api_dados_snapshot(dados, "2026-02-24")
    payload = out.get("payload") or {}
    todos = payload.get("hoje", []) + payload.get("acumulado", []) + payload.get("nao_resolvidos_eventos", [])
    ev = next((x for x in todos if isinstance(x, dict) and x.get("threadId") == tid), None)
    assert ev is not None
    assert (ev.get("status_processo") or "").strip().upper() == "CONCLUÍDO"
