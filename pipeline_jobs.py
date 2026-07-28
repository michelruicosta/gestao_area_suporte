"""
Orquestração de jobs do pipeline para a UI administrativa do painel.
Um job activo por processo Flask; estado em memória.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from datetime import date, datetime, timedelta
from typing import Any, Callable

RAIZ_PROJETO = os.path.dirname(os.path.abspath(__file__))
EXECUTAR_TUDO = os.path.join(RAIZ_PROJETO, "executar_tudo.py")
DELETAR_CARGA = os.path.join(RAIZ_PROJETO, "deletar_carga.py")
LIMPAR_PERIODO = os.path.join(RAIZ_PROJETO, "scripts", "limpar_periodo.py")
CENARIOS = os.path.join(RAIZ_PROJETO, "scripts", "oraculo_cenarios_pipeline.py")

_LOG_RUNS_PATH = os.path.join(RAIZ_PROJETO, "data", "logs", "pipeline_runs.json")
_log_runs_lock = threading.Lock()


def _gravar_pipeline_run(job: dict[str, Any]) -> None:
    """Registra o resultado de um job em pipeline_runs.json (um objeto por linha = append seguro)."""
    try:
        started = float(job.get("started_at") or 0)
        finished = float(job.get("finished_at") or time.time())
        entrada: dict[str, Any] = {
            "timestamp_inicio": datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp_fim":    datetime.fromtimestamp(finished).strftime("%Y-%m-%d %H:%M:%S"),
            "duracao_s":        round(finished - started, 1),
            "tipo":             job.get("kind", ""),
            "status":           job.get("status", ""),
            "returncode":       job.get("returncode"),
            "erro":             job.get("error"),
            "periodo_ini":      job.get("periodo_ini"),
            "periodo_fim":      job.get("periodo_fim"),
            "dias_lista":       job.get("dias_lista"),
            "etapas_concluidas": job.get("steps_done"),
            "scripts_status":    job.get("scripts_status") or {},
        }
        os.makedirs(os.path.dirname(_LOG_RUNS_PATH), exist_ok=True)
        with _log_runs_lock:
            runs: list = []
            if os.path.exists(_LOG_RUNS_PATH):
                try:
                    with open(_LOG_RUNS_PATH, encoding="utf-8") as f:
                        runs = json.load(f)
                    if not isinstance(runs, list):
                        runs = []
                except Exception:
                    runs = []
            runs.append(entrada)
            if len(runs) > 90:          # mantém últimas 90 execuções (~3 meses de cargas diárias)
                runs = runs[-90:]
            with open(_LOG_RUNS_PATH, "w", encoding="utf-8") as f:
                json.dump(runs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # log nunca deve quebrar o pipeline


def _formatar_dd_mm_yy(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year}"

MES_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
ETAPAS_EXECUTAR_TUDO = 16

_lock = threading.Lock()
_JOB_ATIVO: str | None = None
_jobs: dict[str, dict[str, Any]] = {}

_LINHA_ETAPA = re.compile(r"--- Etapa\s+(.+?)\s*---")
_DUR_ETAPA = re.compile(r"Dura(?:ç|c)ão desta etapa:\s*([\d.]+)", re.I)
_ETAPA_ORDINAL = re.compile(r"^\s*(\d+)[.).]")
_ERRO_ETAPA = re.compile(r"ERRO na execucao de|ERRO ao importar|PIPELINE INTERROMPIDO", re.I)
_PROGRESSO_LLM = re.compile(r"\[16\]\s+progresso:\s*(\d+)/(\d+)", re.I)
_PROGRESSO_ETAPA = re.compile(r"\[(\d+)\]\s+progresso:\s*(\d+)/(\d+)", re.I)
_DELETE_GRUPO_OK = re.compile(
    r"\[DELETE_GRUPO_OK\]\s*idx=(\d+)\s+total=(\d+)\s+pct=(\d+)\s+titulo=(.+)"
)


def parse_data_br_ou_iso(s: str) -> date:
    """Aceita DD/MM/YYYY ou YYYY-MM-DD."""
    x = (s or "").strip().replace("-", "/")
    if not x:
        raise ValueError("Data vazia")
    partes = [p for p in x.split("/") if p]
    if len(partes) != 3:
        raise ValueError("Use DD/MM/YYYY ou YYYY-MM-DD")
    if len(partes[0]) == 4:
        y, m, da = int(partes[0]), int(partes[1]), int(partes[2])
        return date(y, m, da)
    d, m, y = int(partes[0]), int(partes[1]), int(partes[2])
    if y < 100:
        y += 2000
    return date(y, m, d)


def _dd_mmm_yyyy(d: date) -> str:
    return f"{d.day}-{MES_EN[d.month - 1]}-{d.year}"


def env_periodo_inicio_fim_inclusivos(d_ini: date, d_fim: date) -> dict[str, str]:
    """Intervalo de dias civis inclusivos → [DATA_COLETA_INICIO, DATA_LIMITE_EXCLUIR) em DD-MMM-YYYY."""
    if d_fim < d_ini:
        raise ValueError("A data final é anterior ao início.")
    return {
        "ORACULO_DATA_COLETA_INICIO": _dd_mmm_yyyy(d_ini),
        "ORACULO_DATA_LIMITE_EXCLUIR": _dd_mmm_yyyy(d_fim + timedelta(days=1)),
    }


def _env_utf8(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Env para subprocessos do pipeline com stdout/stderr forçados a UTF-8.

    Sem ``PYTHONIOENCODING=utf-8`` o ``print`` de linhas com emoji/acento (ex.: a linha
    ``⏱ Duração desta etapa`` do ``executar_tudo``) falha ao codificar no pipe do Windows
    (cp1252): a linha inteira é perdida e, com ela, o ``scripts_status`` por etapa (MEL-07) e
    os tempos por etapa no log. O ``iniciar_deletar_carga`` já usava este padrão; aqui fica
    centralizado para todos os subprocessos cuja saída é consumida por ``_consumir_linhas_stdout``.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def _novo_job(kind: str) -> tuple[str, dict[str, Any]]:
    jid = str(uuid.uuid4())
    j: dict[str, Any] = {
        "id": jid,
        "kind": kind,
        "status": "running",
        "started_at": time.time(),
        "finished_at": None,
        "returncode": None,
        "error": None,
        "step_label": "Iniciando…",
        "steps_done": 0,
        "total_steps_est": ETAPAS_EXECUTAR_TUDO,
        "last_step_s": None,
        "etapa_atual_ord": None,
        "scripts_status": {},   # "02" → "ok" | "err"
        "_etapa_tem_erro": False,
        "dia_atual": None,
        "dias_total": None,
        "log_tail": deque(maxlen=48),
        "last_log_at": time.time(),
    }
    return jid, j


def _append_log(job: dict[str, Any], line: str) -> None:
    job["log_tail"].append(line.rstrip()[:500])
    job["last_log_at"] = time.time()


def _on_line_executar_tudo(job: dict[str, Any], line: str) -> None:
    m = _LINHA_ETAPA.search(line)
    if m:
        label = m.group(1).strip()
        job["step_label"] = label
        job["_etapa_tem_erro"] = False  # reseta ao entrar em nova etapa
        mo = _ETAPA_ORDINAL.match(label)
        if mo:
            try:
                job["etapa_atual_ord"] = int(mo.group(1))
            except ValueError:
                pass
        return
    if _ERRO_ETAPA.search(line):
        job["_etapa_tem_erro"] = True
    m = _DUR_ETAPA.search(line)
    if m:
        try:
            job["last_step_s"] = float(m.group(1))
        except ValueError:
            pass
        ord_atual = job.get("etapa_atual_ord")
        if ord_atual and 1 <= ord_atual <= 16:
            num = f"{ord_atual:02d}"
            job.setdefault("scripts_status", {})[num] = "err" if job.get("_etapa_tem_erro") else "ok"
        job["steps_done"] = min(int(job.get("steps_done") or 0) + 1, ETAPAS_EXECUTAR_TUDO)
        # Limpa sub-progresso LLM ao encerrar a etapa
        job.pop("llm_feitas", None)
        job.pop("llm_total", None)
        return
    # Sub-progresso genérico: "[NN] progresso: X/Y label"
    m = _PROGRESSO_ETAPA.search(line)
    if m:
        try:
            etapa_n = int(m.group(1))
            feitas   = int(m.group(2))
            total_p  = int(m.group(3))
            job["sub_etapa_n"]      = etapa_n
            job["sub_etapa_feitas"] = feitas
            job["sub_etapa_total"]  = total_p
            # compatibilidade com campo legado do LLM
            if etapa_n == 16:
                job["llm_feitas"] = feitas
                job["llm_total"]  = total_p
        except ValueError:
            pass


def _consumir_linhas_stdout(proc: subprocess.Popen, job: dict[str, Any]) -> None:
    assert proc.stdout
    # Decodificar SEMPRE como UTF-8: os subprocessos são lançados com PYTHONIOENCODING=utf-8
    # (ver _env_utf8). Herdar sys.stdout.encoding do processo Flask geraria mojibake no Windows
    # (cp1252) e quebraria o parser de "Duração desta etapa" — e com ele o scripts_status (MEL-07).
    for raw in iter(proc.stdout.readline, b""):
        if not raw:
            break
        try:
            line = raw.decode("utf-8", errors="replace")
        except Exception:
            line = str(raw)
        _on_line_executar_tudo(job, line)
        _append_log(job, line)
    proc.stdout.close()


def _finalizar_job(jid: str, rc: int | None, err: str | None) -> None:
    global _JOB_ATIVO
    with _lock:
        if jid in _jobs:
            _jobs[jid]["status"] = "done" if rc == 0 else "failed"
            _jobs[jid]["finished_at"] = time.time()
            _jobs[jid]["returncode"] = rc
            _jobs[jid]["error"] = err
            if rc is None:
                _jobs[jid]["status"] = "failed"
        if _JOB_ATIVO == jid:
            _JOB_ATIVO = None
    job_snap = dict(_jobs.get(jid) or {})
    _gravar_pipeline_run(job_snap)


def pode_iniciar() -> tuple[bool, str | None]:
    with _lock:
        if _JOB_ATIVO:
            return False, "Já há um trabalho pipeline em execução. Espere pela conclusão."
        return True, None


def obter_estado(job_id: str) -> dict | None:
    with _lock:
        j = _jobs.get(job_id)
        if not j:
            return None
        out = {k: v for k, v in j.items() if k != "log_tail"}
        out["log_tail"] = list(j.get("log_tail") or [])
        now = time.time()
        elapsed = now - float(j.get("started_at") or now)
        out["elapsed_s"] = round(elapsed, 1)
        last_log = float(j.get("last_log_at") or now)
        out["silencio_s"] = round(now - last_log, 1)  # segundos sem nova linha de log
        raw_sd = int(j.get("steps_done") or 0)
        tot = max(int(j.get("total_steps_est") or ETAPAS_EXECUTAR_TUDO), 1)
        llm_feitas = j.get("llm_feitas")
        llm_total  = j.get("llm_total")
        sub_feitas = j.get("sub_etapa_feitas")
        sub_total  = j.get("sub_etapa_total")
        sub_n      = j.get("sub_etapa_n")
        eta = 0.0
        if raw_sd < tot and raw_sd > 0:
            tempo_medio_etapa = elapsed / raw_sd
            etapas_restantes  = tot - raw_sd
            if sub_feitas and sub_total and sub_feitas > 0 and sub_total > sub_feitas:
                # Etapa em curso com sub-progresso: usa velocidade real dos itens
                eta_sub     = (elapsed / sub_feitas) * (sub_total - sub_feitas)
                eta_pos_sub = tempo_medio_etapa * max(0, etapas_restantes - 1)
                eta = max(0.0, eta_sub + eta_pos_sub)
            else:
                eta = max(0.0, tempo_medio_etapa * etapas_restantes)
        out["eta_s_aprox"] = round(eta, 1)
        # Sub-progresso exposto para o front (qualquer etapa)
        if sub_feitas is not None and sub_total and sub_n is not None:
            pct = int(100 * sub_feitas / max(sub_total, 1))
            out["llm_progresso_txt"] = f"Triando threads — {sub_feitas}/{sub_total} ({pct}%)"
        elif llm_feitas is not None and llm_total:
            out["llm_progresso_txt"] = f"{llm_feitas}/{llm_total} threads LLM"
        else:
            out["llm_progresso_txt"] = None
        if j.get("dia_atual") and j.get("dias_total"):
            out["dia_progresso_txt"] = f"Dia {j['dia_atual']}/{j['dias_total']}"
        else:
            out["dia_progresso_txt"] = None
        return out


def _run_executar_um_env(extra_env: dict[str, str], job: dict[str, Any]) -> int:
    env = _env_utf8(extra_env)
    proc = subprocess.Popen(
        [sys.executable, EXECUTAR_TUDO],
        cwd=RAIZ_PROJETO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )
    _consumir_linhas_stdout(proc, job)
    rc = proc.wait()
    job["steps_done"] = ETAPAS_EXECUTAR_TUDO
    return int(rc)


def _append_deletar_resumo_plano(job: dict[str, Any], incluir_backups: bool) -> None:
    """Lista em linguagem para o usuário o que entra na operação (antes do output do script)."""
    _append_log(job, "Resumo — o que esta operacao faz:")
    _append_log(
        job,
        "[apagar] data/json/pipeline/ — trabalho ja gerado (01/02/03, integrador, pares Gmail confirmados,",
    )
    _append_log(job, "         estados Aguardando/Concluido nos JSON de carga, correlacoes, etc.)")
    if incluir_backups:
        _append_log(
            job,
            "[apagar] data/json/_backups/ — copias de seguranca antigas nesta maquina (opcao assinalada)",
        )
    else:
        _append_log(job, "[manter] data/json/_backups/ — copias de seguranca (opcao nao assinalada)")
    _append_log(
        job,
        "[manter] data/json/config/ — regras, cadastro clientes (CADOC), rótulos, usuários, …",
    )
    _append_log(
        job,
        "[manter] ajustes manuais de cartao (cartao_overrides em painel_estado), se existirem.",
    )
    _append_log(job, "—")
    _append_log(job, "Segue o relatorio do programa de limpeza:")


def iniciar_deletar_carga(backups: bool = False) -> tuple[str | None, str | None]:
    ok, msg = pode_iniciar()
    if not ok:
        return None, msg

    from deletar_carga import obter_plano_grupos_delecao

    jid, job = _novo_job("deletar_carga")
    plano = obter_plano_grupos_delecao(bool(backups))
    job["delete_etapas"] = plano
    n_grupos = max(len(plano), 1)
    job["total_steps_est"] = n_grupos
    job["steps_done"] = 0
    job["incluir_backups"] = bool(backups)
    job["step_label"] = "Apagar pasta pipeline/…"

    def run() -> None:
        rc: int | None = None
        err: str | None = None
        try:
            _append_deletar_resumo_plano(job, bool(backups))
            cmd = [sys.executable, DELETAR_CARGA, "--sim"]
            if backups:
                cmd.append("--backups")
                job["step_label"] = "Apagar pipeline/ (+ _backups se selecionado)…"
            proc_env = os.environ.copy()
            proc_env["ORACULO_DELETAR_VIA_ADMIN_UI"] = "1"
            proc_env.setdefault("PYTHONIOENCODING", "utf-8")
            proc = subprocess.Popen(
                cmd,
                cwd=RAIZ_PROJETO,
                env=proc_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            assert proc.stdout
            for raw in iter(proc.stdout.readline, b""):
                if not raw:
                    break
                try:
                    line = raw.decode("utf-8", errors="replace")
                except Exception:
                    line = str(raw)
                m = _DELETE_GRUPO_OK.search(line)
                if m:
                    with _lock:
                        job["steps_done"] = int(m.group(1))
                        job["total_steps_est"] = int(m.group(2))
                        job["step_label"] = m.group(4).strip()
                else:
                    with _lock:
                        job["step_label"] = "Apagando arquivos…"
                _append_log(job, line)
            proc.stdout.close()
            rc = proc.wait()
            if rc != 0:
                err = f"deletar_carga terminou com código {rc}"
            else:
                with _lock:
                    tt = int(job.get("total_steps_est") or n_grupos)
                    job["steps_done"] = tt
        except Exception as e:
            rc = -1
            err = str(e)
        finally:
            _finalizar_job(jid, rc, err)

    with _lock:
        _jobs[jid] = job
        global _JOB_ATIVO
        _JOB_ATIVO = jid
    threading.Thread(target=run, daemon=True).start()
    return jid, None


def iniciar_limpar_periodo(
    data_unica: str | None,
    data_de: str | None,
    data_ate: str | None,
    preservar_threads_painel: bool,
    forcar_remover_manuais: bool = False,
) -> tuple[str | None, str | None]:
    """Remove apenas movimento de um dia ou intervalo nos JSON (`limpar_periodo.py`)."""
    ok, msg = pode_iniciar()
    if not ok:
        return None, msg

    u = (data_unica or "").strip()
    de_raw = (data_de or "").strip()
    ate_raw = (data_ate or "").strip()

    cmd_label = ""
    try:
        if u:
            d = parse_data_br_ou_iso(u)
            arg_data = _formatar_dd_mm_yy(d)
            cmd = [sys.executable, LIMPAR_PERIODO, "--data", arg_data]
            cmd_label = f"limpar período --data {arg_data}"
        elif de_raw and ate_raw:
            d0 = parse_data_br_ou_iso(de_raw)
            d1 = parse_data_br_ou_iso(ate_raw)
            if d1 < d0:
                d0, d1 = d1, d0
            cmd = [
                sys.executable,
                LIMPAR_PERIODO,
                "--de",
                _formatar_dd_mm_yy(d0),
                "--ate",
                _formatar_dd_mm_yy(d1),
            ]
            cmd_label = f"limpar período {_formatar_dd_mm_yy(d0)} -> {_formatar_dd_mm_yy(d1)}"
        else:
            return None, (
                "Preencha um dia ou ambas as datas do intervalo (início e fim)."
            )
    except ValueError as e:
        return None, str(e)

    if preservar_threads_painel:
        cmd.append("--preservar-threads-painel")

    jid, job = _novo_job("limpar_periodo")
    job["total_steps_est"] = 1
    job["step_label"] = f"Limpando dados nos JSON ({cmd_label})…"
    job["periodo_ini"] = _formatar_dd_mm_yy(d0) if not u else _formatar_dd_mm_yy(d)
    job["periodo_fim"] = _formatar_dd_mm_yy(d1) if not u else _formatar_dd_mm_yy(d)

    def run() -> None:
        rc: int | None = None
        err: str | None = None
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=RAIZ_PROJETO,
                env=_env_utf8(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            assert proc.stdout
            for raw in iter(proc.stdout.readline, b""):
                if not raw:
                    break
                try:
                    line = raw.decode("utf-8", errors="replace")
                except Exception:
                    line = str(raw)
                job["step_label"] = "Limpeza nos arquivos 01 / 02 / 03…"
                _append_log(job, line)
            proc.stdout.close()
            rc = proc.wait()
            if rc != 0:
                err = f"limpar_periodo terminou com código {rc}"
            job["steps_done"] = 1
        except Exception as e:
            rc = -1
            err = str(e)
        finally:
            _finalizar_job(jid, rc, err)

    with _lock:
        _jobs[jid] = job
        global _JOB_ATIVO
        _JOB_ATIVO = jid
    threading.Thread(target=run, daemon=True).start()
    return jid, None


def _limpar_auto_ag_co_periodo(d0: date, d1: date, job: dict[str, Any]) -> None:
    """Remove entradas **automáticas** de ``threads_aguardando_auto.json`` /
    ``threads_concluidas_auto.json`` cujas datas (data_marcacao / data_conclusao)
    caem dentro de ``[d0..d1]``.

    Necessário antes do re-triar cronológico em ``iniciar_periodo_unico``: se o
    AG/CO tiver registos auto remanescentes (de uma corrida anterior) com
    ``data_conclusao`` dentro do período, o guard
    ``_tids_sem_reprocessar_triagem_fecho_anterior`` (regra ``cl > dia_ref``)
    exclui esses threadIds da triagem dos dias mais antigos do período, e a
    consequente CO criada no último dia fica sem ``marcacao_aguardante_pre_conclusao``
    (porque o thread nunca passou por AG no período). Sem esse campo, o painel
    histórico mostra o cartão como **PENDENTE** nos dias anteriores em vez de
    **AGUARDANDO**.

    Preserva tudo o que estiver fora do intervalo.
    """
    import json as _json
    iso_ini = d0.isoformat()
    iso_fim = d1.isoformat()
    pasta = os.path.join(RAIZ_PROJETO, "data", "json", "pipeline")
    alvos = [
        ("threads_aguardando_auto.json", ("data_marcacao", "data_ref_operacional")),
        ("threads_concluidas_auto.json", ("data_conclusao",)),
    ]
    for nome, campos in alvos:
        path = os.path.join(pasta, nome)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                lista = _json.load(f)
        except Exception as e:
            _append_log(job, f"[limpar-auto] aviso: falhou ler {nome}: {e}")
            continue
        if not isinstance(lista, list):
            continue
        antes = len(lista)
        novos: list = []
        for r in lista:
            if not isinstance(r, dict):
                novos.append(r)
                continue
            data_str = ""
            for c in campos:
                v = r.get(c)
                if v:
                    data_str = str(v)[:10]
                    break
            if data_str and iso_ini <= data_str <= iso_fim:
                continue  # remove
            novos.append(r)
        if len(novos) != antes:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(novos, f, indent=2, ensure_ascii=False)
                _append_log(job, f"[limpar-auto] {nome}: {antes - len(novos)} auto removidos do período")
            except Exception as e:
                _append_log(job, f"[limpar-auto] aviso: falhou gravar {nome}: {e}")


def _limpar_todo_auto_ag_co(job: dict[str, Any]) -> None:
    """Reset completo de ``threads_aguardando_auto.json`` /
    ``threads_concluidas_auto.json``.

    Necessário antes do re-triar cronológico **completo** (Opção 2): sem este
    reset, threads com ``data_conclusao`` em dias posteriores são excluídos
    pelo guard ``cl > dia_ref`` em ``_tids_sem_reprocessar_triagem_fecho_anterior``
    quando re-triar dias mais antigos, impedindo a criação dos AG históricos
    e o enriquecimento posterior de ``marcacao_aguardante_pre_conclusao``.
    """
    import json as _json
    pasta = os.path.join(RAIZ_PROJETO, "data", "json", "pipeline")
    alvos = ("threads_aguardando_auto.json", "threads_concluidas_auto.json")
    for nome in alvos:
        path = os.path.join(pasta, nome)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                lista = _json.load(f)
        except Exception as e:
            _append_log(job, f"[reset-auto] aviso: falhou ler {nome}: {e}")
            continue
        if not isinstance(lista, list):
            continue
        novos = []
        if len(novos) != len(lista):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(novos, f, indent=2, ensure_ascii=False)
                _append_log(
                    job,
                    f"[reset-auto] {nome}: {len(lista)} registros removidos (reset full)",
                )
            except Exception as e:
                _append_log(job, f"[reset-auto] aviso: falhou gravar {nome}: {e}")


def _datas_distintas_no_integrador() -> list[date]:
    """Lista ordenada de datas distintas presentes em ``eventos`` do integrador."""
    import json as _json
    integ_path = os.path.join(
        RAIZ_PROJETO, "data", "json", "pipeline", "03_integrador_dados_site.json"
    )
    if not os.path.isfile(integ_path):
        return []
    try:
        with open(integ_path, encoding="utf-8") as f:
            integ = _json.load(f)
    except Exception:
        return []
    datas: set[date] = set()
    for ev in integ.get("eventos") or []:
        if not isinstance(ev, dict):
            continue
        di = (ev.get("data_iso") or "")[:10]
        if not di:
            continue
        try:
            datas.add(date.fromisoformat(di))
        except ValueError:
            continue
    return sorted(datas)


def _snapshot_estado_pre_carga() -> tuple[date | None, list]:
    """Captura, ANTES da carga, (maior dia já no integrador, lista AGUARDANDO atual).

    Usado por ``_re_triar_todos_dias_consistente`` para (1) decidir se a carga é só
    acréscimo de dias novos no fim e (2) reconstruir ``marcacao_aguardante_pre_conclusao``
    nas threads que passarem de AGUARDANDO→CONCLUÍDA durante a carga.
    """
    import json as _json
    dias = _datas_distintas_no_integrador()
    max_dia = dias[-1] if dias else None
    ag: list = []
    p = os.path.join(RAIZ_PROJETO, "data", "json", "pipeline", "threads_aguardando_auto.json")
    try:
        with open(p, encoding="utf-8") as f:
            ag = _json.load(f)
        if not isinstance(ag, list):
            ag = []
    except Exception:
        ag = []
    return max_dia, ag


def _e_acrescimo_no_fim(d0: date, max_dia_antes: date | None) -> bool:
    """True se ``d0`` é estritamente posterior a tudo que já existia no integrador
    antes da carga → acréscimo de dias novos no fim (elegível ao caminho leve)."""
    return max_dia_antes is not None and d0 > max_dia_antes


def _enriquecer_marcacao_pre_conclusao(
    ag_antes: list, job: dict[str, Any], co_path: str | None = None
) -> int:
    """Preenche ``marcacao_aguardante_pre_conclusao`` nas threads agora CONCLUÍDAS
    que estavam AGUARDANDO antes da carga (usa a ``data_marcacao`` antiga).

    Garante que a vista histórica mostre AGUARDANDO (não PENDENTE) nos dias
    anteriores à conclusão — o mesmo efeito que o re-triar completo (marreta)
    produz, sem precisar re-triar os 138 dias. Idempotente: só toca registros
    concluídos sem o campo. Devolve o número de threads enriquecidas.
    """
    import json as _json
    ag_map: dict[str, str] = {}
    for r in ag_antes or []:
        if isinstance(r, dict) and r.get("threadId"):
            d = (r.get("data_marcacao") or r.get("data_ref_operacional") or "")[:10]
            if d:
                ag_map[str(r["threadId"])] = d
    if not ag_map:
        return 0
    p = co_path or os.path.join(RAIZ_PROJETO, "data", "json", "pipeline", "threads_concluidas_auto.json")
    try:
        with open(p, encoding="utf-8") as f:
            co = _json.load(f)
    except Exception:
        return 0
    if not isinstance(co, list):
        return 0
    n = 0
    for r in co:
        if not isinstance(r, dict):
            continue
        tid = str(r.get("threadId") or "")
        if not tid or r.get("marcacao_aguardante_pre_conclusao"):
            continue
        old = ag_map.get(tid)
        if old:
            r["marcacao_aguardante_pre_conclusao"] = old
            r["origem_aguardante_triagem_auto"] = True
            n += 1
    if n:
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(co, f, ensure_ascii=False, indent=2)
        _append_log(job, f"[enriquecimento] marcacao_aguardante preenchido em {n} thread(s) concluída(s)")
    return n


def _re_triar_todos_dias_consistente(
    d0: date, d1: date, job: dict[str, Any],
    max_dia_antes: date | None = None, ag_antes: list | None = None,
) -> None:
    """Re-triar **todos** os dias presentes no integrador (∪ ``[d0..d1]``) em
    ordem cronológica, depois de um reset completo do estado auto.

    Razão (Opção 2 — consistência multi-dia): threads que tocam dias dentro e
    fora do período ficavam com triagem obsoleta porque o re-triar de
    ``[d0..d1]`` só processa threads com actividade em cada dia desse intervalo.
    Para os dias fora do intervalo, o guard ``cl > dia_ref`` em
    ``_tids_sem_reprocessar_triagem_fecho_anterior`` excluía os threads que já
    tinham CO em dias posteriores — resultando em ``marcacao_aguardante_pre_conclusao``
    em falta e cards a aparecer como PENDENTE na vista histórica.

    Solução robusta: limpar todo o estado auto AG/CO (manuais preservados) e
    re-triar todos os dias do mais antigo ao mais recente. Cada dia constrói a
    sua AG limpa; quando um dia posterior promove a thread a CO, a lógica de
    enriquecimento em ``triagem_auto_ddr4111._run_triagem_cadocs`` popula
    ``marcacao_aguardante_pre_conclusao`` a partir da AG do dia anterior.

    Caminho LEVE (acréscimo de dias novos no fim): se ``[d0..d1]`` é estritamente
    posterior ao maior dia que já existia no integrador antes desta carga
    (``max_dia_antes``), NÃO é preciso zerar e re-triar os 138 dias. Re-tria só os
    dias novos (preservando os dias antigos) e enriquece o marcador histórico a
    partir do AGUARDANDO de antes da carga (``ag_antes``). Provado equivalente à
    marreta neste cenário (REGISTRO 2026-06-16). Re-subir/reprocessar dias ANTIGOS
    (``d0 <= max_dia_antes``) mantém a marreta completa por segurança.
    """
    if _e_acrescimo_no_fim(d0, max_dia_antes):
        _append_log(
            job,
            f"[consistência] dias novos no fim (após {max_dia_antes.isoformat()}) "
            f"→ caminho leve: re-triar só {d0.isoformat()}..{d1.isoformat()} "
            f"(sem zerar nem re-triar o histórico)",
        )
        cmd_base = [sys.executable, CENARIOS]
        d = d0
        while d <= d1:
            ddmm = f"{d.day:02d}/{d.month:02d}/{d.year}"
            job["step_label"] = f"re-triar (leve) {ddmm}"
            proc = subprocess.Popen(
                [*cmd_base, "re-triar", "--data", ddmm],
                cwd=RAIZ_PROJETO, env=_env_utf8(), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, bufsize=0,
            )
            _consumir_linhas_stdout(proc, job)
            if proc.wait() != 0:
                _append_log(job, f"[aviso] re-triar leve {ddmm} rc!=0 (não fatal)")
            d += timedelta(days=1)
        _enriquecer_marcacao_pre_conclusao(ag_antes or [], job)
        return

    job["step_label"] = "Reset estado auto AG/CO antes do re-triar consistente"
    _limpar_todo_auto_ag_co(job)

    datas = set(_datas_distintas_no_integrador())
    d = d0
    while d <= d1:
        datas.add(d)
        d += timedelta(days=1)
    todas = sorted(datas)
    if not todas:
        return
    _append_log(
        job,
        f"[re-triar-tudo] {len(todas)} dia(s) a re-triar em ordem cronológica",
    )
    cmd_base = [sys.executable, CENARIOS]
    for d in todas:
        ddmm = f"{d.day:02d}/{d.month:02d}/{d.year}"
        job["step_label"] = f"re-triar (consistência) {ddmm}"
        cmd_rt = [*cmd_base, "re-triar", "--data", ddmm]
        proc_rt = subprocess.Popen(
            cmd_rt,
            cwd=RAIZ_PROJETO,
            env=_env_utf8(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        _consumir_linhas_stdout(proc_rt, job)
        rc_rt = proc_rt.wait()
        if rc_rt != 0:
            _append_log(
                job, f"[aviso] re-triar consistência {ddmm} retornou rc={rc_rt} (não fatal)"
            )


def iniciar_periodo_unico(data_ini: str, data_fim: str) -> tuple[str | None, str | None]:
    ok, msg = pode_iniciar()
    if not ok:
        return None, msg
    try:
        d0 = parse_data_br_ou_iso(data_ini)
        d1 = parse_data_br_ou_iso(data_fim)
        env_ov = env_periodo_inicio_fim_inclusivos(d0, d1)
        # Desativa a triagem automática na corrida principal do executar_tudo.
        # Para intervalos multi-dia, o executar_tudo não define TRIAGEM_AUTO_DATA_REF,
        # pelo que a triagem usaria date.today() como data_marcacao/data_conclusao —
        # valores incorrectos que o re-triar subsequente não consegue corrigir
        # (threads CONCLUÍDOS com data_conclusao=hoje são excluídos pelo guard
        # _tids_sem_reprocessar_triagem_fecho_anterior por terem data > dia_ref).
        # O re-triar chamado a seguir (um por dia, do mais antigo ao mais recente)
        # faz a classificação com TRIAGEM_AUTO_DATA_REF correcto para cada dia.
        for _flag in (
            "TRIAGEM_AUTO_DDR4111", "TRIAGEM_AUTO_DLI", "TRIAGEM_AUTO_DLO",
            "TRIAGEM_AUTO_S5", "TRIAGEM_AUTO_SUPORTE", "TRIAGEM_AUTO_RETORNO_BACEN",
        ):
            env_ov[_flag] = "0"
    except ValueError as e:
        return None, str(e)

    jid, job = _novo_job("periodo_unico")
    job["periodo_ini"] = _formatar_dd_mm_yy(d0)
    job["periodo_fim"] = _formatar_dd_mm_yy(d1)

    def run() -> None:
        rc: int | None = None
        err: str | None = None
        try:
            job["step_label"] = (
                f"Ciclo único {_dd_mmm_yyyy(d0)} até {_dd_mmm_yyyy(d1)} inclusivo "
                f"(limite exclusivo {_dd_mmm_yyyy(d1 + timedelta(days=1))})"
            )
            _max_antes, _ag_antes = _snapshot_estado_pre_carga()
            rc = _run_executar_um_env(env_ov, job)
            if rc != 0:
                err = f"executar_tudo saiu com código {rc}"
                return
            # Opção 2 — consistência multi-dia: reset completo do estado auto
            # AG/CO seguido de re-triar cronológico de todos os dias presentes
            # no integrador (∪ [d0..d1]). Garante que threads que tocam dias
            # dentro e fora de [d0..d1] obtenham AG/CO consistentes em todas
            # as vistas históricas, com ``marcacao_aguardante_pre_conclusao``
            # correctamente preenchido pela lógica de enriquecimento em
            # ``triagem_auto_ddr4111._run_triagem_cadocs``.
            _re_triar_todos_dias_consistente(d0, d1, job, _max_antes, _ag_antes)
        except Exception as e:
            rc = -1
            err = str(e)
        finally:
            _finalizar_job(jid, rc, err)

    with _lock:
        _jobs[jid] = job
        global _JOB_ATIVO
        _JOB_ATIVO = jid
    threading.Thread(target=run, daemon=True).start()
    return jid, None


def iniciar_lista_dias(
    datas_texto: str,
    modo: str,
    incremental: bool,
    triagem_todo_o_03: bool,
) -> tuple[str | None, str | None]:
    ok, msg = pode_iniciar()
    if not ok:
        return None, msg

    linhas = []
    for lin in (datas_texto or "").replace(",", "\n").splitlines():
        t = lin.strip()
        if t:
            linhas.append(t)
    dias: list[date] = []
    for ln in linhas:
        try:
            dias.append(parse_data_br_ou_iso(ln))
        except ValueError as e:
            return None, f'Data inválida "{ln}": {e}'
    if not dias:
        return None, "Indique pelo menos uma data (DD/MM/YYYY ou uma por linha)."

    dias_sorted = sorted(set(dias))
    modo = (modo or "").strip().lower()
    if modo not in ("subir", "acrescentar-dia"):
        return None, 'Modo deve ser "subir" ou "acrescentar-dia".'

    jid, job = _novo_job("lista_dias")
    job["dias_total"] = len(dias_sorted)
    job["dias_lista"] = [_formatar_dd_mm_yy(d) for d in dias_sorted]
    total = len(dias_sorted)

    cmd_base = [sys.executable, CENARIOS]

    def run() -> None:
        rc_exit = 0
        err_txt: str | None = None
        try:
            _max_antes, _ag_antes = _snapshot_estado_pre_carga()
            for idx, dr in enumerate(dias_sorted):
                job["dia_atual"] = idx + 1
                ddmm = f"{dr.day:02d}/{dr.month:02d}/{dr.year}"
                cmd = [*cmd_base, modo, "--data", ddmm]
                if modo == "subir":
                    if incremental:
                        cmd.append("--incremental")
                    if triagem_todo_o_03:
                        cmd.append("--triagem-todo-o-03")
                job["steps_done"] = 0
                job["etapa_atual_ord"] = None
                job["step_label"] = f"({idx + 1}/{total}) `{modo}` {ddmm}"
                proc = subprocess.Popen(
                    cmd,
                    cwd=RAIZ_PROJETO,
                    env=_env_utf8(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                )
                _consumir_linhas_stdout(proc, job)
                rc_exit = proc.wait()
                if rc_exit != 0:
                    err_txt = f"Cenários saiu com código {rc_exit} em {ddmm}"
                    break
                # Em modo "subir" multi-dia: após integrar dia D (idx>0), re-triar D-1
                # para classificar threads que só se tornaram candidatos depois que D foi
                # integrado no JSON 03. Espelha o passo extra que "acrescentar-dia" já faz
                # via _run_triagens_dia_anterior. Sem isso, threads com mensagens em D-1 e D
                # ficam PENDENTE na visão histórica de D-1.
                if modo == "subir" and len(dias_sorted) > 1 and idx > 0:
                    dia_anterior = dias_sorted[idx - 1]
                    ddmm_ant = f"{dia_anterior.day:02d}/{dia_anterior.month:02d}/{dia_anterior.year}"
                    job["step_label"] = f"({idx + 1}/{total}) re-triar {ddmm_ant}"
                    cmd_rt = [*cmd_base, "re-triar", "--data", ddmm_ant]
                    proc_rt = subprocess.Popen(
                        cmd_rt,
                        cwd=RAIZ_PROJETO,
                        env=_env_utf8(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        bufsize=0,
                    )
                    _consumir_linhas_stdout(proc_rt, job)
                    rc_rt = proc_rt.wait()
                    if rc_rt != 0:
                        _append_log(job, f"[aviso] re-triar {ddmm_ant} retornou rc={rc_rt} (não fatal)")
            # Opção 2 — consistência multi-dia: depois de processar toda a
            # lista de datas, fazer reset full do auto AG/CO e re-triar
            # cronologicamente todos os dias do integrador (∪ [min..max] da
            # lista). Cobre threads multi-dia que tocam dias fora da lista.
            if rc_exit == 0 and dias_sorted:
                _re_triar_todos_dias_consistente(
                    dias_sorted[0], dias_sorted[-1], job, _max_antes, _ag_antes
                )
        except Exception as e:
            rc_exit = -1
            err_txt = str(e)
        finally:
            job["steps_done"] = ETAPAS_EXECUTAR_TUDO
            _finalizar_job(jid, rc_exit, err_txt)

    with _lock:
        _jobs[jid] = job
        global _JOB_ATIVO
        _JOB_ATIVO = jid
    threading.Thread(target=run, daemon=True).start()
    return jid, None
