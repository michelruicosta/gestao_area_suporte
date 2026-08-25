"""
executar_pipeline.py
O que faz: roda o pipeline completo do Gestão Área Suporte em sequência:
           1. Coleta e-mails novos do Gmail (coletor_gmail.py)
           2. Classifica threads sem categoria (classificador_regras.py)
Rodar: python scripts/executar_pipeline.py
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paths import criar_log
from coletor_gmail import coletar
from classificador_regras import classificar_banco

log = criar_log('pipeline')


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
    log.info('Abra http://localhost:5001 para ver o resultado nas telas.')


if __name__ == '__main__':
    executar()
