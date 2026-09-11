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

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

import monitor_erros
monitor_erros.iniciar()

import banco_threads as bt
from paths import criar_log
from coletor_gmail import coletar
from classificador_regras import classificar_banco, reavaliar_automaticos
from coletor_enviados_colaboradores import coletar_colaboradores

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

    cfg = ler_config()

    # ── Etapa 1: Coleta Gmail ─────────────────────────────────────────────────
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

    # ── Etapa 2: Coleta colaboradores ─────────────────────────────────────────
    log.info(_linha())
    log.info('ETAPA 2 — Coleta de respostas dos colaboradores')
    log.info(_linha())
    t2 = time.time()
    try:
        r_col = coletar_colaboradores()
        log.info('Colaboradores — %d mensagens novas em %d threads.',
                 r_col['mensagens_novas'], r_col['threads_atualizadas'])
    except Exception as e:
        log.error('Falha no coletor de colaboradores (não fatal): %s', e)
    dur2 = time.time() - t2
    log.info('Etapa 2 concluída em %.1fs', dur2)

    # ── Etapa 3: Classificação de categorias ──────────────────────────────────
    log.info(_linha())
    log.info('ETAPA 3 — Classificação de threads')
    log.info(_linha())
    t3 = time.time()
    try:
        contagens = classificar_banco()
    except Exception as e:
        log.error('ERRO FATAL na classificação: %s', e)
        sys.exit(1)
    dur3 = time.time() - t3
    log.info('Etapa 3 concluída em %.1fs', dur3)

    # ── Etapa 4: Recalcular status (AF / AC / Concluída) ──────────────────────
    log.info(_linha())
    log.info('ETAPA 4 — Recálculo de status')
    log.info(_linha())
    t4 = time.time()
    try:
        n_status = bt.recalcular_status_todos()
        log.info('Status recalculado para %d threads.', n_status)
    except Exception as e:
        log.error('Falha no recálculo de status (não fatal): %s', e)
    dur4 = time.time() - t4
    log.info('Etapa 4 concluída em %.1fs', dur4)

    # ── Etapa 5: Arquivar threads inativas ────────────────────────────────────
    log.info(_linha())
    log.info('ETAPA 5 — Arquivar threads inativas (Sem Retorno)')
    log.info(_linha())
    t5 = time.time()
    try:
        dias_af = int(cfg.get('dias_sr_af', 30))
        dias_ac = int(cfg.get('dias_sr_ac', 60))
        contagens_sr = bt.arquivar_threads_inativas(dias_af=dias_af, dias_ac=dias_ac)
        total_sr = contagens_sr['af'] + contagens_sr['ac']
        log.info('Sem Retorno — arquivadas %d thread(s): %d AF, %d AC.',
                 total_sr, contagens_sr['af'], contagens_sr['ac'])
    except Exception as e:
        log.error('Falha no arquivamento de inativas (não fatal): %s', e)
    dur5 = time.time() - t5
    log.info('Etapa 5 concluída em %.1fs', dur5)

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
    """Uma passada completa: Gmail → colaboradores → categorias → status → arquiva inativas."""
    log.info('Coleta automática — início.')
    cfg = ler_config()

    log_id = coletar()

    try:
        r_col = coletar_colaboradores()
        log.info('Colaboradores — %d mensagens novas em %d threads.',
                 r_col['mensagens_novas'], r_col['threads_atualizadas'])
    except Exception as e:
        log.error('Falha no coletor de colaboradores: %s', e)

    contagens = classificar_banco()
    reavaliar_automaticos()
    if log_id:
        bt.atualizar_classif_coleta(
            log_id,
            contagens.get('principal', 0),
            contagens.get('descartes', 0),
            contagens.get('revisao', 0),
        )

    try:
        n_status = bt.recalcular_status_todos()
        log.info('Status recalculado para %d threads.', n_status)
    except Exception as e:
        log.error('Falha no recálculo de status: %s', e)

    try:
        dias_af = int(cfg.get('dias_sr_af', 30))
        dias_ac = int(cfg.get('dias_sr_ac', 60))
        contagens_sr = bt.arquivar_threads_inativas(dias_af=dias_af, dias_ac=dias_ac)
        total_sr = contagens_sr['af'] + contagens_sr['ac']
        if total_sr:
            log.info('Sem Retorno — arquivadas %d thread(s): %d AF, %d AC.',
                     total_sr, contagens_sr['af'], contagens_sr['ac'])
    except Exception as e:
        log.error('Falha no arquivamento de inativas: %s', e)

    log.info('Coleta automática — fim.')



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
    monitor_erros.checkin_inicio()
    try:
        rodar_coleta_ciclo()
        monitor_erros.checkin_fim(ok=True)
    except Exception:
        monitor_erros.checkin_fim(ok=False)
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
        lambda: _aplicar_intervalo_coleta(_AGENDADOR),
        'interval',
        minutes=1,
        id='ler_intervalo_config',
        replace_existing=True,
    )
    from aviso_busca_parou import _INTERVALO_VIGIA_MIN, verificar_e_avisar_busca_parada

    def _job_vigia_busca():
        cfg = ler_config()
        logs = bt.ler_log_coletas(limite=30)
        admin = (os.environ.get('GESTAO_EMAIL') or 'michel@finaud.com.br').strip()
        portal = (os.environ.get('PORTAL_URL') or 'https://finaudapps.com.br').rstrip('/')
        novo, _enviou = verificar_e_avisar_busca_parada(
            cfg,
            logs,
            False,
            admin_email=admin,
            portal_url=portal,
        )
        if novo.get('aviso_busca_enviado_para', '') != cfg.get('aviso_busca_enviado_para', ''):
            with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(novo, f, ensure_ascii=False, indent=2)

    _AGENDADOR.add_job(
        _job_vigia_busca,
        'interval',
        minutes=_INTERVALO_VIGIA_MIN,
        id='vigia_busca_email',
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
