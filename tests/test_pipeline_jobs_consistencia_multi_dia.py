# -*- coding: utf-8 -*-
"""Helpers de consistência multi-dia em ``pipeline_jobs``.

Testa o ``_re_triar_todos_dias_consistente`` (Opção 2): full reset do auto
AG/CO + identificação correcta dos dias a re-triar (∪ integrador, [d0..d1]).
Cobre a regressão em que threads que tocam dias dentro **e** fora de [d0..d1]
ficavam como PENDENTE na vista histórica dos dias fora.
"""
from __future__ import annotations

import json
import os
from collections import deque


def _job_stub() -> dict:
    """Job mínimo válido para os helpers (inclui ``log_tail`` que ``_append_log`` usa)."""
    return {"log_tail": deque(maxlen=48), "step_label": ""}


def test_datas_distintas_no_integrador_le_eventos(tmp_path, monkeypatch):
    import pipeline_jobs as pj

    pasta = tmp_path / "data" / "json" / "pipeline"
    pasta.mkdir(parents=True)
    integ = {
        "eventos": [
            {"threadId": "T1", "data_iso": "2026-02-23"},
            {"threadId": "T1", "data_iso": "2026-02-27"},
            {"threadId": "T2", "data_iso": "2026-02-25"},
            {"threadId": "T3", "data_iso": ""},  # ignorar vazio
            {"threadId": "T4", "data_iso": "data invalida"},  # ignorar inválido
            {"threadId": "T5", "data_iso": "2026-02-23"},  # duplicada
        ]
    }
    (pasta / "03_integrador_dados_site.json").write_text(
        json.dumps(integ, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(pj, "RAIZ_PROJETO", str(tmp_path))
    from datetime import date

    datas = pj._datas_distintas_no_integrador()
    assert datas == [date(2026, 2, 23), date(2026, 2, 25), date(2026, 2, 27)]


def test_limpar_todo_auto_ag_co_remove_todos(tmp_path, monkeypatch):
    """Reset full do AG/CO remove todos os registros."""
    import pipeline_jobs as pj

    pasta = tmp_path / "data" / "json" / "pipeline"
    pasta.mkdir(parents=True)
    ag_path = pasta / "threads_aguardando_auto.json"
    co_path = pasta / "threads_concluidas_auto.json"
    ag_path.write_text(
        json.dumps([
            {"threadId": "AUTO_1", "origem_triagem_auto": True, "data_marcacao": "2026-02-23"},
            {"threadId": "REG_2", "origem_triagem_auto": False, "data_marcacao": "2026-02-23"},
            {"threadId": "REG_3", "data_marcacao": "2026-02-24"},
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    co_path.write_text(
        json.dumps([
            {"threadId": "AUTO_C1", "origem_triagem_auto": True, "data_conclusao": "2026-02-24"},
            {"threadId": "REG_C2", "origem_triagem_auto": False, "data_conclusao": "2026-02-24"},
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(pj, "RAIZ_PROJETO", str(tmp_path))

    job = _job_stub()
    pj._limpar_todo_auto_ag_co(job)

    ag_apos = json.loads(ag_path.read_text(encoding="utf-8"))
    co_apos = json.loads(co_path.read_text(encoding="utf-8"))
    # Todos removidos
    assert ag_apos == []
    assert co_apos == []


def test_re_triar_todos_dias_consistente_combina_periodo_e_integrador(tmp_path, monkeypatch):
    """Cobertura: o helper combina [d0..d1] com datas do integrador, sem duplicar e em ordem."""
    import pipeline_jobs as pj
    from datetime import date

    pasta = tmp_path / "data" / "json" / "pipeline"
    pasta.mkdir(parents=True)
    # integrador tem 21, 23, 27 (alguns dentro do período, outros fora)
    integ = {
        "eventos": [
            {"threadId": "T1", "data_iso": "2026-02-21"},
            {"threadId": "T1", "data_iso": "2026-02-23"},
            {"threadId": "T2", "data_iso": "2026-02-27"},
        ]
    }
    (pasta / "03_integrador_dados_site.json").write_text(
        json.dumps(integ, ensure_ascii=False), encoding="utf-8"
    )
    # ficheiros AG/CO vazios
    (pasta / "threads_aguardando_auto.json").write_text("[]", encoding="utf-8")
    (pasta / "threads_concluidas_auto.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(pj, "RAIZ_PROJETO", str(tmp_path))

    # Capturar os dias passados ao re-triar (substituir Popen por stub)
    chamados: list[str] = []

    class _StubProc:
        def __init__(self, cmd, **_kw):
            chamados.append(" ".join(cmd))

        def wait(self):
            return 0

        @property
        def stdout(self):
            class _N:
                def readline(self):
                    return b""

            return _N()

    monkeypatch.setattr(pj.subprocess, "Popen", _StubProc)
    monkeypatch.setattr(pj, "_consumir_linhas_stdout", lambda *a, **k: None)

    job = _job_stub()
    pj._re_triar_todos_dias_consistente(date(2026, 2, 23), date(2026, 2, 25), job)

    # Esperado: 21 (integrador), 23 (∩), 24 (período só), 25 (período só), 27 (integrador)
    # Em ordem cronológica, sem duplicados.
    iso_chamados = []
    for c in chamados:
        for tok in c.split():
            if tok.count("/") == 2:
                # tok = DD/MM/YYYY
                d, m, y = tok.split("/")
                iso_chamados.append(f"{y}-{m}-{d}")
    assert iso_chamados == [
        "2026-02-21",
        "2026-02-23",
        "2026-02-24",
        "2026-02-25",
        "2026-02-27",
    ]


# ─── Caminho LEVE: acréscimo de dias novos no fim (sem re-triar os 138 dias) ───

def test_e_acrescimo_no_fim():
    import pipeline_jobs as pj
    from datetime import date

    assert pj._e_acrescimo_no_fim(date(2026, 6, 8), date(2026, 6, 7)) is True   # novo no fim
    assert pj._e_acrescimo_no_fim(date(2026, 6, 5), date(2026, 6, 7)) is False  # dia antigo → marreta
    assert pj._e_acrescimo_no_fim(date(2026, 6, 8), None) is False              # sem baseline → marreta
    assert pj._e_acrescimo_no_fim(date(2026, 6, 7), date(2026, 6, 7)) is False  # mesmo dia (não estrito)


def test_enriquecer_marcacao_preenche_so_quem_aguardava(tmp_path):
    import pipeline_jobs as pj

    co_path = tmp_path / "co.json"
    co_path.write_text(json.dumps([
        {"threadId": "X", "data_conclusao": "2026-06-08"},  # aguardava antes → preencher
        {"threadId": "Y", "data_conclusao": "2026-06-08",
         "marcacao_aguardante_pre_conclusao": "2026-06-01"},  # já tem → não tocar
        {"threadId": "Z", "data_conclusao": "2026-06-08"},  # não aguardava → não tocar
    ], ensure_ascii=False), encoding="utf-8")
    ag_antes = [
        {"threadId": "X", "data_marcacao": "2026-06-05"},
        {"threadId": "Y", "data_marcacao": "2026-06-02"},
    ]
    n = pj._enriquecer_marcacao_pre_conclusao(ag_antes, _job_stub(), co_path=str(co_path))
    co = {r["threadId"]: r for r in json.loads(co_path.read_text(encoding="utf-8"))}
    assert n == 1
    assert co["X"]["marcacao_aguardante_pre_conclusao"] == "2026-06-05"
    assert co["X"]["origem_aguardante_triagem_auto"] is True
    assert co["Y"]["marcacao_aguardante_pre_conclusao"] == "2026-06-01"  # inalterado
    assert "marcacao_aguardante_pre_conclusao" not in co["Z"]            # não aguardava


def test_re_triar_caminho_leve_so_periodo_sem_wipe(tmp_path, monkeypatch):
    """Acréscimo no fim: re-tria SÓ os dias novos, NÃO zera o histórico, e enriquece."""
    import pipeline_jobs as pj
    from datetime import date

    pasta = tmp_path / "data" / "json" / "pipeline"
    pasta.mkdir(parents=True)
    (pasta / "03_integrador_dados_site.json").write_text(json.dumps({"eventos": [
        {"threadId": "T1", "data_iso": "2026-02-21"},
        {"threadId": "T2", "data_iso": "2026-02-27"},
    ]}, ensure_ascii=False), encoding="utf-8")
    co_path = pasta / "threads_concluidas_auto.json"
    (pasta / "threads_aguardando_auto.json").write_text("[]", encoding="utf-8")
    co_path.write_text(json.dumps([{"threadId": "A", "data_conclusao": "2026-06-08"}],
                                  ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(pj, "RAIZ_PROJETO", str(tmp_path))

    chamados: list[str] = []

    class _StubProc:
        def __init__(self, cmd, **_kw):
            chamados.append(" ".join(cmd))

        def wait(self):
            return 0

        @property
        def stdout(self):
            class _N:
                def readline(self):
                    return b""
            return _N()

    monkeypatch.setattr(pj.subprocess, "Popen", _StubProc)
    monkeypatch.setattr(pj, "_consumir_linhas_stdout", lambda *a, **k: None)
    wiped = {"v": False}
    monkeypatch.setattr(pj, "_limpar_todo_auto_ag_co", lambda job: wiped.__setitem__("v", True))

    pj._re_triar_todos_dias_consistente(
        date(2026, 6, 8), date(2026, 6, 9), _job_stub(),
        max_dia_antes=date(2026, 2, 27),
        ag_antes=[{"threadId": "A", "data_marcacao": "2026-02-25"}],
    )

    iso = []
    for c in chamados:
        for tok in c.split():
            if tok.count("/") == 2:
                d, m, y = tok.split("/")
                iso.append(f"{y}-{m}-{d}")
    assert iso == ["2026-06-08", "2026-06-09"]   # só os dias novos
    assert wiped["v"] is False                    # NÃO zerou o histórico
    co = json.loads(co_path.read_text(encoding="utf-8"))
    assert co[0]["marcacao_aguardante_pre_conclusao"] == "2026-02-25"  # enriquecido
