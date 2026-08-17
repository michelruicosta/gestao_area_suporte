"""
executar_pipeline.py
O que faz: roda o pipeline completo do Oráculo 360 em sequência:
           1. Coleta e-mails novos do Gmail (coletor_gmail.py)
           2. Classifica threads sem categoria (classificador_ia.py)
Rodar: python scripts/executar_pipeline.py
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coletor_gmail import coletar
from classificador_ia import classificar_banco


def _linha(char: str = '─', n: int = 60) -> str:
    return char * n


def executar() -> None:
    inicio = time.time()
    agora  = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    print(_linha('═'))
    print(f'PIPELINE ORÁCULO 360  —  {agora}')
    print(_linha('═'))

    # ── Etapa 1: Coleta ───────────────────────────────────────────────────────
    print()
    print(_linha())
    print('ETAPA 1 — Coleta de e-mails (Gmail)')
    print(_linha())
    t1 = time.time()
    try:
        coletar()
    except Exception as e:
        print(f'\n[ERRO FATAL na coleta] {e}')
        print('Pipeline interrompido. Verifique o arquivo de credenciais e a conexão.')
        sys.exit(1)
    dur1 = time.time() - t1
    print(f'\n  Etapa 1 concluída em {dur1:.1f}s')

    # ── Etapa 2: Classificação ─────────────────────────────────────────────────
    print()
    print(_linha())
    print('ETAPA 2 — Classificação de threads')
    print(_linha())
    t2 = time.time()
    try:
        contagens = classificar_banco()
    except Exception as e:
        print(f'\n[ERRO FATAL na classificação] {e}')
        sys.exit(1)
    dur2 = time.time() - t2
    print(f'\n  Etapa 2 concluída em {dur2:.1f}s')

    # ── Resumo final ──────────────────────────────────────────────────────────
    dur_total = time.time() - inicio
    print()
    print(_linha('═'))
    print('PIPELINE CONCLUÍDO')
    print(_linha())
    print(f'  Classificadas → Principal : {contagens.get("principal", 0)}')
    print(f'  Descartadas  → Filtro §4  : {contagens.get("descartes", 0)}')
    print(f'  Aguardando   → Revisão    : {contagens.get("revisao", 0)}')
    print(f'  Tempo total  : {dur_total:.1f}s')
    print(_linha('═'))
    print()
    print('Abra http://localhost:5001 para ver o resultado nas telas.')
    print()


if __name__ == '__main__':
    executar()
