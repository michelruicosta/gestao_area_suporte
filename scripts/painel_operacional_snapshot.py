# -*- coding: utf-8 -*-
"""Snapshot da mesma lógica de ``/api/dados?data=`` para estatísticas (leitura, sem Fluxo Flask)."""

from __future__ import annotations


def montagem_api_dados_snapshot(
    dados_json: dict | list,
    data_filtro_raw: str | None,
    *,
    busca_ativa: bool = False,
    modo_leitura_gestacao: bool = True,
):
    """Importação tardia evita ciclo quando ``painel_oraculo`` importa este módulo."""

    import painel_oraculo as mp  # pylint: disable=import-outside-toplevel

    dados_json_local = dados_json if isinstance(dados_json, dict) else {}
    eventos_lista = dados_json_local.get("eventos", []) if isinstance(dados_json_local, dict) else dados_json_local
    threads_lista = dados_json_local.get("threads", []) if isinstance(dados_json_local, dict) else []

    mapa_threads = {t.get("threadId"): t.get("mensagens", []) for t in threads_lista}
    mapa_thread_responsavel = {
        t.get("threadId"): t.get("responsavel") for t in threads_lista if t.get("threadId") and (t.get("responsavel") or "").strip()
    }

    cartao_overrides = mp.load_cartao_overrides()
    mp._patch_cadoc_desde_cartao_overrides(eventos_lista, threads_lista, cartao_overrides)

    concluidas = mp._carregar_threads_concluidas()
    concluidos_set = {r.get("threadId") for r in concluidas if isinstance(r, dict) and r.get("threadId")}
    concluida_qtd_msg = {}
    for r in concluidas:
        if not isinstance(r, dict) or not r.get("threadId"):
            continue
        q = r.get("qtd_mensagens_no_fechamento")
        concluida_qtd_msg[r.get("threadId")] = int(q) if q is not None else 0

    aguardando_lista = mp._carregar_threads_aguardando()
    aguardando_set = {r.get("threadId") for r in aguardando_lista if isinstance(r, dict) and r.get("threadId")}
    aguardando_qtd_msg = {}
    for r in aguardando_lista:
        if not isinstance(r, dict) or not r.get("threadId"):
            continue
        q = r.get("qtd_mensagens_no_fechamento")
        aguardando_qtd_msg[r.get("threadId")] = int(q) if q is not None else 0

    # Índices O(1) para evitar buscas lineares dentro do loop de eventos.
    # Sem estes dicts, cada evento faz next(rx for rx in concluidas...)
    # que é O(n) — com milhares de eventos e centenas de registros resulta
    # em O(n²), principal causa da lentidão ao trocar de data.
    #
    # IMPORTANTE — preservar a 1ª ocorrência:
    # ``aguardando_lista`` / ``concluidas`` vêm de ``load_*()`` na ordem
    # AUTO + MANUAL (ver paths.py). O código antigo fazia ``next(rx for rx
    # in aguardando_lista if ...)`` que retornava o 1º match → o registo AUTO.
    # Dict comprehension simples sobrescreveria o AUTO pelo MANUAL (mantém
    # último) e quebraria a regra de DATA REF (AUTO usa ``data_marcacao <= ref``;
    # MANUAL usa ``data_marcacao == ref``) — fios apareceriam AGUARDANDO só
    # no dia exato da marcação manual e PENDENTE nos dias seguintes, mesmo
    # tendo também um registo AUTO válido.
    concluidas_by_tid: dict = {}
    for r in concluidas:
        if isinstance(r, dict) and r.get("threadId") and r["threadId"] not in concluidas_by_tid:
            concluidas_by_tid[r["threadId"]] = r
    aguardando_by_tid: dict = {}
    for r in aguardando_lista:
        if isinstance(r, dict) and r.get("threadId") and r["threadId"] not in aguardando_by_tid:
            aguardando_by_tid[r["threadId"]] = r

    # ── Invariante "saiu de PENDENTE não volta" ──────────────────────
    # A antiga despromoção AG → PENDENTE quando chegava nova mensagem foi
    # removida: violava a regra de imutabilidade. Nova mensagem em fio
    # AGUARDANDO é tratada pela triagem na próxima corrida do pipeline
    # (regras §3/§3-inv mantêm AG, §5/§5b promovem a CO). Aqui, o painel
    # apenas LÊ o estado AG/CO já gravado em disco — nunca o muta.
    #
    # Se for preciso reactivar o comportamento antigo (ex: cenário de
    # gestação antes de a triagem correr), use o env
    # ORACULO_API_DESATIVA_PERSIST_SAIDA_AGUARDANDO=0 e descomente o bloco.

    import re  # pylint: disable=import-outside-toplevel
    from datetime import datetime  # pylint: disable=import-outside-toplevel

    if data_filtro_raw:
        data_ref_para_nao_resolvidos = mp._parse_data_ref(data_filtro_raw)
        if data_ref_para_nao_resolvidos is None:
            data_ref_para_nao_resolvidos = datetime.now().date()
    else:
        data_ref_para_nao_resolvidos = datetime.now().date()

    _dt_trava_classificacao_dia = mp._parse_data_ref(data_filtro_raw) if data_filtro_raw else None

    nao_resolvidos_ids = []
    for r in aguardando_lista:
        if not isinstance(r, dict) or not r.get("threadId"):
            continue
        data_marc = r.get("data_marcacao") or ""
        if not data_marc:
            continue
        try:
            dt = datetime.strptime(str(data_marc)[:10], "%Y-%m-%d").date()
            if (data_ref_para_nao_resolvidos - dt).days >= 7:
                nao_resolvidos_ids.append(r.get("threadId"))
        except (ValueError, TypeError):
            pass

    nova_interacao_ids = mp._threads_nova_interacao(data_ref=data_ref_para_nao_resolvidos)

    mp._aplicar_cartao_overrides_nos_sets(cartao_overrides, concluidos_set, aguardando_set, concluida_qtd_msg, mapa_threads)

    excluir_cadoc = [
        "IGNORADO",
        "INTERNO",
    ]
    if not busca_ativa:
        excluir_cadoc.append("FILTRADO_POR_DATA")

    # Threads que ficaram CONCLUÍDAS *após* a DATA REF mas estavam AGUARDANDO no momento da REF
    # (deduzido do campo ``marcacao_aguardante_pre_conclusao`` no registo CO). Sem unir estes
    # threadIds em ``payload.aguardando``, o front-end (que constrói AGUARDANDO_IDS a partir
    # desse payload) não consegue excluí-los do contador «Pendentes», mesmo que cada evento já
    # esteja marcado com ``status_processo: "AGUARDANDO"`` pelo bloco histórico abaixo.
    aguardando_historico_set: set = set()

    eventos_filtrados = []
    for _e_orig in eventos_lista:
        # Shallow copy: campos top-level (status, empresa, etc.) são mutados
        # livremente sem corromper o objeto cacheado em memória.
        e = dict(_e_orig)
        if e.get("cadoc") in excluir_cadoc:
            continue
        tid_early = e.get("threadId")
        if (e.get("status_processo") or "").upper() == "SEM_TRIAGEM" and tid_early not in aguardando_set and tid_early not in concluidos_set:
            continue
        assunto = (e.get("titulo") or e.get("assunto") or "").lower()

        tid = e.get("threadId")
        if tid in mapa_threads:
            e["mensagens"] = mapa_threads[tid]
        if tid in mapa_thread_responsavel:
            e["responsavel"] = mapa_thread_responsavel[tid]

        # Vista por DATA REF: conclusões posteriores à própria REF não podem sobrepor o cartão «naquele dia».
        # Persistimos ``marcacao_aguardante_pre_conclusao`` ao concluir (Aprender e Concluir) quando havia marcação «Aguardando».
        aplicou_historico_ref = False
        if (
            tid
            and _dt_trava_classificacao_dia is not None
            and tid in concluidos_set
        ):
            reg_co_hist = concluidas_by_tid.get(tid)
            if isinstance(reg_co_hist, dict):
                d_cls_global = mp._data_civil_em_registro(reg_co_hist.get("data_conclusao")) or mp._data_civil_em_registro(
                    reg_co_hist.get("data_marcacao")
                )
                if d_cls_global and d_cls_global > _dt_trava_classificacao_dia:
                    e["status"] = "aberto"
                    e.pop("reaberta_apos_conclusao", None)
                    marca_pre = (reg_co_hist.get("marcacao_aguardante_pre_conclusao") or "").strip()
                    d_m_pre = mp._data_civil_em_registro(marca_pre) if marca_pre else None
                    sp_hist = None
                    if marca_pre and d_m_pre is not None:
                        _oa = reg_co_hist.get("origem_aguardante_triagem_auto")
                        if _oa is None:
                            _oa = bool(
                                reg_co_hist.get("alvo_triagem_auto") or reg_co_hist.get("origem_triagem_auto")
                            )
                        else:
                            _oa = bool(_oa)
                        _cmp_ok = (
                            d_m_pre <= _dt_trava_classificacao_dia if _oa else d_m_pre == _dt_trava_classificacao_dia
                        )
                        if _cmp_ok:
                            sp_hist = "AGUARDANDO"
                    if sp_hist is None:
                        # 2026-05-12 (correção regressão Aguardando→Pendente):
                        # Quando o registro de conclusão veio da triagem
                        # automática mas não preserva ``marcacao_aguardante_pre_conclusao``
                        # (fluxo: pendente → concluído auto direto, sem passar
                        # por aguardando explícito), inferimos AGUARDANDO na
                        # vista histórica. Justificativa: se a triagem fechou
                        # o caso em D+N, no dia D ele ainda estava em algum
                        # estado de espera (cliente ou Finaud), nunca PENDENTE
                        # de classificação. Sem essa inferência, o card
                        # "pisca" como PENDENTE em dias passados.
                        # Aplicamos apenas para concluídos AUTO (não manual)
                        # pra preservar PENDENTE legítimo quando o operador
                        # fechou direto com "Aprender e Concluir".
                        _eh_concluido_auto = bool(
                            reg_co_hist.get("origem_triagem_auto")
                            or reg_co_hist.get("alvo_triagem_auto")
                        )
                        if _eh_concluido_auto:
                            e["status_processo"] = "AGUARDANDO"
                            e["aguardando"] = True
                            if tid:
                                aguardando_historico_set.add(tid)
                        else:
                            e["status_processo"] = "AGUARDANDO"
                            e.pop("aguardando", None)
                    else:
                        e["status_processo"] = sp_hist
                        e["aguardando"] = True
                        if sp_hist == "AGUARDANDO" and tid:
                            aguardando_historico_set.add(tid)
                    aplicou_historico_ref = True

        if not aplicou_historico_ref and tid in concluidos_set:
            current_qtd = len(e.get("mensagens") or [])
            stored_qtd = concluida_qtd_msg.get(tid) or 0
            if current_qtd > stored_qtd:
                e["status"] = "aberto"
                e["reaberta_apos_conclusao"] = True
                e["status_processo"] = "AGUARDANDO"
            else:
                e["status"] = "concluido"
                e["status_processo"] = "CONCLUÍDO"
        elif not aplicou_historico_ref:
            e["status"] = "aberto"
        if (not aplicou_historico_ref) and tid in aguardando_set and not (
            tid in concluidos_set and not e.get("reaberta_apos_conclusao")
        ):
            e["status_processo"] = "AGUARDANDO"
            e["aguardando"] = True
            reg_ag = aguardando_by_tid.get(tid)
            if reg_ag and not e.get("empresa"):
                emp_reg = (reg_ag.get("empresa") or "").strip()
                if not emp_reg:
                    motivo = (reg_ag.get("motivo") or "")
                    m = re.search(r"(?:da|de)\s+([A-Za-zÀ-ÿ\s]+?)(?:\s+sobre|\s+ref\.|\.|$)", motivo, re.I)
                    if m:
                        emp_reg = m.group(1).strip()
                if emp_reg:
                    e["empresa"] = emp_reg

        if (not aplicou_historico_ref) and _dt_trava_classificacao_dia is not None and tid:
            reg_co = concluidas_by_tid.get(tid)
            travou_concluido = False
            if reg_co and tid in concluidos_set:
                d_cls = mp._data_civil_em_registro(reg_co.get("data_conclusao")) or mp._data_civil_em_registro(
                    reg_co.get("data_marcacao")
                )
                # Trava CONCLUÍDO para qualquer REF >= ``data_conclusao`` (regra «saiu de pendente,
                # não volta»). Mensagens posteriores à conclusão NÃO reabrem retroactivamente o
                # cartão na vista histórica; só uma reabertura formal (nova entrada em AG, com
                # ``data_reabertura`` <= REF) é que tira o fio do estado CONCLUÍDO — e nesse caso o
                # bloco AGUARDANDO abaixo é quem trata.
                if d_cls is not None and d_cls <= _dt_trava_classificacao_dia:
                    _reg_ag_chk = aguardando_by_tid.get(tid)
                    _d_reabt_str_chk = (_reg_ag_chk.get("data_reabertura") or "").strip() if _reg_ag_chk else ""
                    _d_reabt_chk = mp._parse_data_ref(_d_reabt_str_chk) if _d_reabt_str_chk else None
                    _reabertura_activa_em_ref = (
                        _d_reabt_chk is not None and _d_reabt_chk <= _dt_trava_classificacao_dia
                    )
                    if not _reabertura_activa_em_ref:
                        e["status"] = "concluido"
                        e.pop("reaberta_apos_conclusao", None)
                        e["status_processo"] = "CONCLUÍDO"
                        e.pop("aguardando", None)
                        travou_concluido = True
            if not travou_concluido:
                reg_ag = aguardando_by_tid.get(tid)
                if reg_ag and tid in aguardando_set:
                    d_m = mp._data_civil_em_registro(reg_ag.get("data_marcacao")) or mp._data_civil_em_registro(
                        reg_ag.get("data_ref_operacional")
                    )
                    _e_auto = bool(reg_ag.get("alvo_triagem_auto") or reg_ag.get("origem_triagem_auto"))
                    # Reabertura: se o fio foi CONCLUÍDO e depois reaberto como AGUARDANDO,
                    # o registro de ag guarda ``data_conclusao_anterior`` (dia do fecho anterior)
                    # e ``data_reabertura`` (dia em que voltou a AGUARDANDO). Para dias entre
                    # esses dois marcos, o painel deve mostrar CONCLUÍDO — não AGUARDANDO.
                    _data_co_ant_str = (reg_ag.get("data_conclusao_anterior") or "").strip()
                    _data_reabt_str = (reg_ag.get("data_reabertura") or "").strip()
                    if _data_co_ant_str and _data_reabt_str:
                        d_co_ant = mp._parse_data_ref(_data_co_ant_str)
                        d_reabt = mp._parse_data_ref(_data_reabt_str)
                        if (d_co_ant and d_reabt
                                and d_co_ant <= _dt_trava_classificacao_dia < d_reabt):
                            e["status"] = "concluido"
                            e.pop("reaberta_apos_conclusao", None)
                            e["status_processo"] = "CONCLUÍDO"
                            e.pop("aguardando", None)
                            travou_concluido = True
                    if not travou_concluido:
                        _cmp_ok = d_m is not None and (
                            d_m <= _dt_trava_classificacao_dia if _e_auto else d_m == _dt_trava_classificacao_dia
                        )
                        if _cmp_ok:
                            if not (tid in concluidos_set and not e.get("reaberta_apos_conclusao")):
                                e["status_processo"] = "AGUARDANDO"
                                e["aguardando"] = True
        mp._aplicar_fallback_cliente_encaminhamento_interno_api(e)
        e.setdefault("canal", "E-mail")
        if e.pop("_painel_preservar_empresa_responsavel_fallback", False):
            e["empresa"] = mp._rotulo_empresa_gestao_para_api((e.get("empresa") or "Finaud").strip())
        else:
            e["empresa"] = mp._rotulo_empresa_gestao_para_api(mp._empresa_gestao_final(e))
        e["responsavel_pela_acao"] = mp._responsavel_pela_acao_from_mensagens(
            e.get("mensagens") or [],
            (e.get("responsavel") or "").strip(),
        )
        eventos_filtrados.append(e)

    # ── Separação FOG / E-mail ────────────────────────────────────────
    # FOG (FogBugz) deixa de ser injetado em /api/dados. Tickets de FOG
    # têm vida própria e canal próprio em /fog/operacional. A injeção
    # aqui trazia registos fora da janela de carga (≥ 2026-02-23) — ex.:
    # id=7469 de 2021-08-20 — para a vista de qualquer dia, classificados
    # como PENDENTE por o normalizador só reconhecer "fechado" exato e
    # falhar em "Fechado (Implementado)". A vista operacional de e-mail
    # passa a refletir só os fios do integrador 03.

    _mapa_par_mon = mp._mapa_pares_confirmados_para_api(mp._carregar_pares_confirmados_list())

    # Com DATA REF na query: particionar sempre por dia (busca=1 só inclui FILTRADO_POR_DATA no excluir_cadoc,
    # não deve voltar a «flat» total — senão a tela do dia mistura Fog + acervo inteiro como se fosse «hoje»).
    if not (data_filtro_raw and str(data_filtro_raw).strip()):
        # 2026-05-12 (perf): sem filtro de data, eventos_filtrados tem TODO o
        # acervo (6000+ eventos / ~460 MB no JSON). O front-end da
        # operacional SEMPRE passa data; esse modo "flat" é usado apenas
        # para descobrir os Sets (aguardando, nao_resolvidos, etc.).
        # Devolvemos as listas leves mas com ``hoje=[]`` para não
        # serializar 460MB inutilmente. Se algum chamador legado depender
        # de "hoje" cheio, ele passa a precisar mandar ``data`` na query.
        payload = {
            "hoje": [],
            "acumulado": [],
            "nao_resolvidos_eventos": [],
            "threads_em_monitoramento": mp._contar_tids_dedup_par_confirmado(
                [
                    r.get("threadId")
                    for r in concluidas
                    if isinstance(r, dict) and r.get("monitorar_resposta") is True and r.get("threadId")
                ],
                _mapa_par_mon,
            ),
            "aguardando": list(aguardando_set | aguardando_historico_set),
            "nao_resolvidos": nao_resolvidos_ids,
            "nova_interacao": nova_interacao_ids,
            "pares_sugeridos": {},
            "clusters_multi_thread": [],
            "pares_confirmados": _mapa_par_mon,
            "cartao_overrides": cartao_overrides,
        }
        return {"early_flat": True, "payload": payload}

    dt_limite = mp._parse_data_ref(data_filtro_raw)
    if dt_limite is None:
        return {"error": "Data inválida. Use YYYY-MM-DD ou DD/MM/YYYY.", "status_code": 400}

    from datetime import timedelta  # pylint: disable=import-outside-toplevel

    dia_anterior = dt_limite - timedelta(days=1)
    # Vista «ao vivo» (REF é hoje ou futuro): fio pendente sem ag/co que já tem mail *depois* do REF
    # some da lista do REF (pertence ao dia mais recente). Vista histórica (REF passado): não suprimir —
    # senão, após subir D+1/D+2, a tela do dia D fica vazia mesmo com dados intactos no 03.
    hoje_civil = mp.date.today()
    suprimir_multidia_sem_ag_co = dt_limite >= hoje_civil

    thread_datas_presentes = {}
    for evt in eventos_filtrados:
        try:
            tt = evt.get("threadId")
            ts_evt = evt.get("timestamp", "")
            dt_evt = mp._parse_dt_rapido(ts_evt) if ts_evt else None
            if dt_evt and tt:
                thread_datas_presentes.setdefault(tt, set()).add(dt_evt.date())
            for msg in evt.get("mensagens") or []:
                for campo in ("data_iso", "timestamp", "data_email"):
                    val = (msg.get(campo) or "").strip()
                    if not val:
                        continue
                    dd_dt = mp._parse_dt_rapido(val, dayfirst=True)
                    if dd_dt and tt:
                        thread_datas_presentes.setdefault(tt, set()).add(dd_dt.date())
                    if dd_dt:
                        break
        except Exception:
            continue

    hoje_da_selecao = []
    acumulado_pendente = []
    tids_hoje_acumulado = set()
    for evt in eventos_filtrados:
        try:
            tt = evt.get("threadId")
            datas_thread = thread_datas_presentes.get(tt) if tt else set()
            if not datas_thread:
                continue
            ev_filtrado = mp._filtrar_evento_por_data(evt, dt_limite)
            if dt_limite in datas_thread:
                _tem_post = any(mm > dt_limite for mm in datas_thread)
                if suprimir_multidia_sem_ag_co and _tem_post:
                    _ja = (tt in concluidos_set) or (tt in aguardando_set)
                    if not _ja:
                        continue
                ev_filtrado["eh_hoje"] = True
                hoje_da_selecao.append(ev_filtrado)
                if tt:
                    tids_hoje_acumulado.add(tt)
            elif dia_anterior in datas_thread and not mp._evento_concluido_operacional(evt):
                ev_filtrado["eh_hoje"] = False
                acumulado_pendente.append(ev_filtrado)
                if tt:
                    tids_hoje_acumulado.add(tt)
        except Exception:
            continue

    # Índice por threadId para evitar O(n) por uid em nao_resolvidos_ids.
    _evs_por_tid: dict = {}
    for _ev in eventos_filtrados:
        _tt = _ev.get("threadId")
        if _tt:
            _evs_por_tid.setdefault(_tt, []).append(_ev)

    nao_resolvidos_eventos = []
    for uid in nao_resolvidos_ids:
        if uid in tids_hoje_acumulado:
            continue
        cand = _evs_por_tid.get(uid) or []
        if not cand:
            continue
        ultimo = max(cand, key=lambda z: (z.get("timestamp_epoch") or 0, z.get("timestamp") or ""))
        evf = mp._filtrar_evento_por_data(ultimo, dt_limite)
        evf["eh_hoje"] = False
        nao_resolvidos_eventos.append(evf)

    eventos_visao_par = hoje_da_selecao + acumulado_pendente + nao_resolvidos_eventos
    pares_sugeridos = mp._computar_pares_sugeridos_operacional(eventos_visao_par)
    clusters_mt = mp._computar_clusters_multi_thread_operacional(eventos_visao_par)

    # ── Consolidação PENDENTE→CONCLUÍDO por par (sugerido + confirmado) ──
    # Quando duas threads são detectadas como par (auto via fingerprint
    # empresa+prazos, ou confirmadas manualmente) e a última mensagem do par
    # com data <= REF tem ``lado_responsavel=CLIENTE`` (= Finaud respondeu
    # por último) e existe pelo menos uma com ``lado=FINAUD`` (= houve pedido
    # cliente em algum momento), o ciclo está fechado e propagamos
    # CONCLUÍDO para ambas as threads em REF e dias seguintes (até nova
    # interacção que reabra o ciclo).
    # Promovemos só no payload — não persistimos em ``threads_concluidas_auto``,
    # KPIs Não Resolvidos e learnings IA continuam intactos.
    # Salvaguardas: respeitamos AGUARDANDO existente; só promovemos
    # PENDENTE→CONCLUÍDO (nunca o inverso, regra «saiu de pendente, não volta»).
    try:
        # Pares globais: além dos sugeridos do dia (filtrados a hoje+acumulado),
        # também consideramos pares calculados sobre o universo total de
        # ``eventos_filtrados`` para captar casos onde uma thread já está
        # CONCLUÍDA noutro REF e por isso não é vista como par no dia actual.
        _pares_globais = mp._computar_pares_sugeridos_operacional(eventos_filtrados) or {}
        _pares_consolidar = set()
        for _t, _lst in (pares_sugeridos or {}).items():
            for _o in (_lst or []):
                _ot = (_o or {}).get("threadId")
                if _ot:
                    _pares_consolidar.add(tuple(sorted([_t, _ot])))
        for _t, _lst in _pares_globais.items():
            for _o in (_lst or []):
                _ot = (_o or {}).get("threadId")
                if _ot:
                    _pares_consolidar.add(tuple(sorted([_t, _ot])))
        for _t, _ot in (_mapa_par_mon or {}).items():
            if _t and _ot:
                _pares_consolidar.add(tuple(sorted([_t, _ot])))

        # eventos do payload (REF + acumulado) por threadId — alvos da promoção
        _eventos_por_tid = {}
        for _ev in (hoje_da_selecao + acumulado_pendente):
            _tt = _ev.get("threadId")
            if _tt:
                _eventos_por_tid.setdefault(_tt, []).append(_ev)

        # mensagens completas (todas as datas) por threadId — vêm de
        # ``eventos_filtrados`` que já está enriquecido com ``mensagens``
        _msgs_por_tid_full = {}
        for _ev in eventos_filtrados:
            _tt = _ev.get("threadId")
            if not _tt:
                continue
            for _m in (_ev.get("mensagens") or [_ev]):
                _ts = _m.get("timestamp") or _m.get("data_iso") or _m.get("data_email") or ""
                try:
                    _dt = mp._parse_dt_rapido(_ts, dayfirst=True) if _ts else None
                except Exception:
                    _dt = None
                if not _dt:
                    continue
                _lado = (_m.get("lado_responsavel") or _ev.get("lado_responsavel") or "").upper()
                _msgs_por_tid_full.setdefault(_tt, []).append((_dt, _lado))

        for _ta, _tb in _pares_consolidar:
            # Só promovemos pares cujos eventos estejam no payload (hoje/acumulado).
            if _ta not in _eventos_por_tid and _tb not in _eventos_por_tid:
                continue
            _msgs_ate_ref = []
            for _tx in (_ta, _tb):
                for _dt, _lado in _msgs_por_tid_full.get(_tx, []):
                    if _dt.date() <= dt_limite:
                        _msgs_ate_ref.append((_dt, _lado))
            if not _msgs_ate_ref:
                continue
            _msgs_ate_ref.sort(key=lambda x: x[0])
            _ultimo_lado = _msgs_ate_ref[-1][1]
            _tem_pedido = any(_l == "FINAUD" for _, _l in _msgs_ate_ref)
            if _ultimo_lado != "CLIENTE" or not _tem_pedido:
                continue
            for _tx in (_ta, _tb):
                if _tx in aguardando_set:
                    continue
                for _ev in _eventos_por_tid.get(_tx, []):
                    _sp = (_ev.get("status_processo") or "").upper().replace("Í", "I")
                    if _sp != "AGUARDANDO":
                        continue
                    _ev["status"] = "concluido"
                    _ev["status_processo"] = "CONCLUÍDO"
                    _ev.pop("aguardando", None)
                    _ev["_fechado_por_par"] = True
    except Exception:
        pass

    _mon_tids = [
        r.get("threadId") for r in concluidas if isinstance(r, dict) and r.get("monitorar_resposta") is True and r.get("threadId")
    ]
    threads_em_monitoramento = mp._contar_tids_dedup_par_confirmado(_mon_tids, _mapa_par_mon)

    payload = {
        "hoje": hoje_da_selecao,
        "acumulado": acumulado_pendente,
        "nao_resolvidos_eventos": nao_resolvidos_eventos,
        "threads_em_monitoramento": threads_em_monitoramento,
        "aguardando": list(aguardando_set | aguardando_historico_set),
        "nao_resolvidos": nao_resolvidos_ids,
        "nova_interacao": nova_interacao_ids,
        "pares_sugeridos": pares_sugeridos,
        "clusters_multi_thread": clusters_mt,
        "pares_confirmados": _mapa_par_mon,
        "cartao_overrides": cartao_overrides,
    }
    return {"early_flat": False, "payload": payload}


def estado_cartao_de_evento_enriquecido(ev: dict, mp=None) -> str:
    if mp is None:
        import painel_oraculo as mp  # pylint: disable=reimported

    if mp._evento_concluido_operacional(ev) or (ev.get("status") or "").strip().lower() in ("concluido", "closed"):
        return "concluido"
    sp = (ev.get("status_processo") or "").strip().upper().replace("Í", "I")
    if sp == "AGUARDANDO" or ev.get("aguardando"):
        return "aguardando"
    return "aguardando"
