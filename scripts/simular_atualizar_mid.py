"""
simular_atualizar_mid.py
O que faz: SIMULAÇÃO — verifica quantas threads abertas (AF/AC) sem Message-ID
           conseguiriam recuperar o ID a partir do Gmail.
           Não altera nada no banco.

Uso:
  python scripts/simular_atualizar_mid.py           → amostra de 100 threads
  python scripts/simular_atualizar_mid.py --todas   → todas as threads sem MID
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coletor_gmail import _conectar_gmail, _processar_thread

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'gestao.db')


def _threads_sem_mid() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT thread_id, assunto, status_workflow, qtd_mensagens, mensagens_json
            FROM   threads
            WHERE  destino = 'principal'
            AND    status_workflow IN ('Aguardando Finaud', 'Aguardando Cliente')
            ORDER  BY data_ultima_msg DESC
        """)
        resultado = []
        for r in cur.fetchall():
            msgs = json.loads(r['mensagens_json'] or '[]')
            if not any(m.get('message_id') for m in msgs):
                resultado.append(dict(r))
        return resultado


def main():
    parser = argparse.ArgumentParser(description='Simulação: recuperação de Message-IDs.')
    parser.add_argument('--todas', action='store_true',
                        help='Verificar todas as threads sem MID (mais lento)')
    args = parser.parse_args()

    print(f'\n{"="*65}')
    print('  SIMULAÇÃO — Recuperação de Message-IDs')
    print(f'  Modo: {"TODAS as threads" if args.todas else "Amostra de 100 threads"}')
    print(f'{"="*65}\n')

    threads_sem_mid = _threads_sem_mid()
    total_sem_mid   = len(threads_sem_mid)
    print(f'Threads abertas SEM Message-ID no banco: {total_sem_mid}')

    if not threads_sem_mid:
        print('Nada a verificar — todas as threads já têm Message-ID.')
        return

    if args.todas:
        amostra = threads_sem_mid
        print(f'Verificando todas as {total_sem_mid} threads...\n')
    else:
        tamanho = min(100, total_sem_mid)
        amostra = random.sample(threads_sem_mid, tamanho)
        print(f'Verificando amostra de {tamanho} threads (de {total_sem_mid})...\n')

    service = _conectar_gmail()

    recuperadas       = 0
    sem_mid_no_gmail  = 0
    nao_encontradas   = 0
    erros             = 0

    for i, t in enumerate(amostra, 1):
        tid     = t['thread_id']
        assunto = (t['assunto'] or '')[:50]

        try:
            dados = _processar_thread(service, tid)
        except Exception as e:
            print(f'  [{i:3d}] ERRO      {assunto} — {e}')
            erros += 1
            continue

        if dados is None:
            print(f'  [{i:3d}] SUMIU     {assunto}')
            nao_encontradas += 1
            continue

        msgs_gmail = dados.get('mensagens', [])
        tem_mid = any(m.get('message_id') for m in msgs_gmail)

        if tem_mid:
            recuperadas += 1
            qtd_com = sum(1 for m in msgs_gmail if m.get('message_id'))
            qtd_sem  = len(msgs_gmail) - qtd_com
        else:
            sem_mid_no_gmail += 1
            print(f'  [{i:3d}] SEM MID  {assunto}')

        if i % 20 == 0:
            time.sleep(0.5)

    # ── Relatório ────────────────────────────────────────────────────────────────
    verificadas = len(amostra)
    print(f'\n{"─"*65}')
    print('  RESULTADO DA SIMULAÇÃO')
    print(f'{"─"*65}')
    print(f'  Verificadas na amostra  : {verificadas:4d}')
    print(f'  Recuperariam MID        : {recuperadas:4d}  ({recuperadas/verificadas*100:.0f}%)')
    print(f'  Sem MID mesmo no Gmail  : {sem_mid_no_gmail:4d}  ({sem_mid_no_gmail/verificadas*100:.0f}%)')
    print(f'  Sumiram do Gmail        : {nao_encontradas:4d}  ({nao_encontradas/verificadas*100:.0f}%)')
    print(f'  Erros                   : {erros:4d}')

    if not args.todas:
        taxa = recuperadas / verificadas if verificadas else 0
        estimado = int(total_sem_mid * taxa)
        print(f'\n  Estimativa para {total_sem_mid} threads totais:')
        print(f'    Recuperariam MID   : ~{estimado} threads')
        print(f'    Não recuperariam   : ~{total_sem_mid - estimado} threads')

    print()


if __name__ == '__main__':
    main()
