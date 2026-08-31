"""
executar_pipeline.py
O que faz: roda o pipeline completo do Gestão Área Suporte em sequência:
           1. Coleta e-mails novos do Gmail (coletor_gmail.py)
           2. Classifica threads sem categoria (classificador_regras.py)
Rodar uma vez:  python scripts/executar_pipeline.py
Relógio (à parte da tela): python scripts/executar_pipeline.py --agendar
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import banco_threads as bt
from paths import criar_log
from coletor_gmail import coletar
from classificador_regras import classificar_banco, reavaliar_automaticos

log = criar_log('pipeline')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_ROOT, 'data', 'config.json')
_CONFIG_DEFAULTS = {
    'intervalo_coleta_min': 60,
    'dias_sr_af': 30,
    'dias_sr_ac': 60,
}


def _linha(char: str = '─', n: int = 60) -> str:
    return char * n


def executar() -> None:
    inicio = time.time()
    agora  = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    log.info(_linha('═'))
    log.info('PIPELINE GESTÃO ÁREA SUPORTE  —  %s', agora)
    log.info(_linha('═'))

    # ── Etapa 1: Coleta ───────────────────────────────────────────────────────
    log.info(_linha())
    log.info('ETAPA 1 — Coleta de e-mails (Gmail)')
    log.info(_linha())
    t1 = time.time()
    try:
        coletar()
    except Exception as e:
        log.error('ERRO FATAL na coleta: %s', e)
        log.error('Pipeline interrompido. Verifique o arquivo de credenciais e a conexão.')
        sys.exit(1)
    dur1 = time.time() - t1
    log.info('Etapa 1 concluída em %.1fs', dur1)

    # ── Etapa 2: Classificação ─────────────────────────────────────────────────
    log.info(_linha())
    log.info('ETAPA 2 — Classificação de threads')
    log.info(_linha())
    t2 = time.time()
    try:
        contagens = classificar_banco()
    except Exception as e:
        log.error('ERRO FATAL na classificação: %s', e)
        sys.exit(1)
    dur2 = time.time() - t2
    log.info('Etapa 2 concluída em %.1fs', dur2)

    # ── Resumo final ──────────────────────────────────────────────────────────
    dur_total = time.time() - inicio
    log.info(_linha('═'))
    log.info('PIPELINE CONCLUÍDO')
    log.info(_linha())
    log.info('Classificadas → Principal : %d', contagens.get('principal', 0))
    log.info('Descartadas   → Filtro §4 : %d', contagens.get('descartes', 0))
    log.info('Aguardando    → Revisão   : %d', contagens.get('revisao', 0))
    log.info('Tempo total   : %.1fs', dur_total)
    log.info(_linha('═'))
    log.info('Abra http://localhost:8004 para ver o resultado nas telas.')


def ler_config() -> dict:
    try:
        with open(_CONFIG_PATH, encoding='utf-8') as f:
            dados = json.load(f)
    except Exception:
        dados = {}
    return {**_CONFIG_DEFAULTS, **dados}


def rodar_coleta_ciclo() -> None:
    """Uma passada: Gmail → classificar → reavaliar automáticos. Usada pelo relógio e pela tela."""
    log.info('Coleta automática — início.')
    log_id = coletar()
    contagens = classificar_banco()
    reavaliar_automaticos()
    if log_id:
        bt.atualizar_classif_coleta(
            log_id,
            contagens.get('principal', 0),
            contagens.get('descartes', 0),
            contagens.get('revisao', 0),
        )
    log.info('Coleta automática — fim.')


def rodar_sem_retorno() -> None:
    """Arquiva threads paradas (todo dia às 6h no modo --agendar)."""
    cfg = ler_config()
    dias_af = int(cfg.get('dias_sr_af', 30))
    dias_ac = int(cfg.get('dias_sr_ac', 60))
    log.info('Sem Retorno — iniciando (AF=%d dias, AC=%d dias).', dias_af, dias_ac)
    try:
        contagens = bt.arquivar_threads_inativas(dias_af=dias_af, dias_ac=dias_ac)
        total = contagens['af'] + contagens['ac']
        mensagem = f"Arquivadas {total} thread(s): {contagens['af']} AF, {contagens['ac']} AC."
        bt.registrar_coleta(
            tipo='sem_retorno',
            threads_proc=total,
            erros=0,
            duracao_seg=0,
            status='concluida',
            mensagem=mensagem,
        )
        log.info('Sem Retorno — %s', mensagem)
    except Exception as e:
        bt.registrar_coleta(
            tipo='sem_retorno',
            threads_proc=0,
            erros=1,
            duracao_seg=0,
            status='erro',
            mensagem=str(e),
        )
        log.exception('Sem Retorno — falhou: %s', e)
        raise


_intervalo_aplicado: int | None = None


def _aplicar_intervalo_coleta(scheduler) -> None:
    """Só remarca o relógio se o intervalo do config mudou — senão dispara coleta demais."""
    global _intervalo_aplicado
    minutos = int(ler_config().get('intervalo_coleta_min', 60))
    job = scheduler.get_job('coleta_automatica')
    if minutos <= 0:
        if job:
            scheduler.remove_job('coleta_automatica')
            log.info('Coleta automática desligada no config (intervalo 0).')
        _intervalo_aplicado = 0
        return
    if job is not None and minutos == _intervalo_aplicado:
        return
    if job is None:
        scheduler.add_job(
            _job_coleta_segura,
            'interval',
            minutes=minutos,
            id='coleta_automatica',
            replace_existing=True,
            next_run_time=datetime.now(),
        )
    else:
        scheduler.reschedule_job('coleta_automatica', trigger='interval', minutes=minutos)
    _intervalo_aplicado = minutos
    log.info('Coleta automática a cada %d minuto(s).', minutos)


def _job_coleta_segura() -> None:
    try:
        rodar_coleta_ciclo()
    except Exception:
        log.exception('Coleta automática falhou.')


_AGENDADOR = None


def ligar_agendador():
    """Relógio na sala dos fundos: não depende da tela Flask."""
    global _AGENDADOR
    from apscheduler.schedulers.background import BackgroundScheduler

    bt.criar_banco()
    _AGENDADOR = BackgroundScheduler(daemon=False)
    _aplicar_intervalo_coleta(_AGENDADOR)
    _AGENDADOR.add_job(
        rodar_sem_retorno,
        'cron',
        hour=6,
        minute=0,
        id='sem_retorno_diario',
        replace_existing=True,
    )
    _AGENDADOR.add_job(
        lambda: _aplicar_intervalo_coleta(_AGENDADOR),
        'interval',
        minutes=1,
        id='ler_intervalo_config',
        replace_existing=True,
    )
    _AGENDADOR.start()
    log.info('Agendador separado da tela — no ar.')
    return _AGENDADOR


def ficar_agendando() -> None:
    ligar_agendador()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        if _AGENDADOR is not None:
            _AGENDADOR.shutdown(wait=False)
        log.info('Agendador encerrado.')


if __name__ == '__main__':
    if '--agendar' in sys.argv:
        ficar_agendando()
    else:
        executar()
