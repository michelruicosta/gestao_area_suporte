"""
sincronizar_abertas.py
O que faz: compara cada thread aberta (Aguardando Finaud / Aguardando Cliente) do banco
           com o Gmail e atualiza as que estiverem com mensagens faltando.

Uso:
  python scripts/sincronizar_abertas.py           → só mostra relatório (não muda nada)
  python scripts/sincronizar_abertas.py --aplicar → aplica as atualizações no banco
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from banco_threads import salvar_thread
from coletor_gmail import _conectar_gmail, _processar_thread

import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'gestao.db')


def _threads_abertas() -> list[dict]:
    """Retorna todas as threads AF e AC que estão na tela principal."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT thread_id, assunto, status_workflow, qtd_mensagens
            FROM   threads
            WHERE  destino = 'principal'
            AND    status_workflow IN ('Aguardando Finaud', 'Aguardando Cliente')
            ORDER  BY data_ultima_msg DESC
        """)
        return [dict(r) for r in cur.fetchall()]


def main():
    parser = argparse.ArgumentParser(description='Sincroniza threads abertas com o Gmail.')
    parser.add_argument('--aplicar', action='store_true',
                        help='Aplica as atualizações no banco (sem esta flag, só mostra o relatório)')
    args = parser.parse_args()

    modo = 'APLICAR' if args.aplicar else 'DIAGNÓSTICO (sem --aplicar, nada será alterado)'
    print(f'\n{"="*60}')
    print(f'  SINCRONIZAR ABERTAS — modo: {modo}')
    print(f'{"="*60}\n')

    threads = _threads_abertas()
    print(f'Threads abertas no banco (AF + AC): {len(threads)}\n')

    service = _conectar_gmail()

    divergentes   = []
    sem_divergencia = 0
    erros         = 0

    for i, t in enumerate(threads, 1):
        tid    = t['thread_id']
        assunto = (t['assunto'] or '')[:55]
        qtd_banco = t['qtd_mensagens'] or 0

        try:
            dados_gmail = _processar_thread(service, tid)
        except Exception as e:
            print(f'  [{i:4d}] ERRO ao buscar {tid}: {e}')
            erros += 1
            continue

        if dados_gmail is None:
            print(f'  [{i:4d}] NÃO ENCONTRADA no Gmail: {assunto}')
            erros += 1
            continue

        qtd_gmail = dados_gmail['qtd_mensagens']

        if qtd_gmail > qtd_banco:
            divergentes.append({
                'thread_id':  tid,
                'assunto':    assunto,
                'status':     t['status_workflow'],
                'qtd_banco':  qtd_banco,
                'qtd_gmail':  qtd_gmail,
                'faltando':   qtd_gmail - qtd_banco,
                'dados':      dados_gmail,
            })
            print(f'  [{i:4d}] DIVERGENTE  banco={qtd_banco} gmail={qtd_gmail}  {assunto}')
        else:
            sem_divergencia += 1

        # Pausa leve para não sobrecarregar a API
        if i % 20 == 0:
            time.sleep(0.5)

    # ── Relatório ────────────────────────────────────────────────────────────
    print(f'\n{"─"*60}')
    print(f'  RELATÓRIO')
    print(f'{"─"*60}')
    print(f'  Verificadas:      {len(threads):4d} threads')
    print(f'  Sem divergência:  {sem_divergencia:4d}')
    print(f'  Divergentes:      {len(divergentes):4d}  ← mensagens faltando no banco')
    print(f'  Erros de acesso:  {erros:4d}')
    print()

    if divergentes:
        print('  Threads com mensagens faltando:')
        for d in divergentes:
            print(f'    • {d["assunto"]:<55} '
                  f'banco={d["qtd_banco"]}  gmail={d["qtd_gmail"]}  '
                  f'(faltam {d["faltando"]})')
        print()

    # ── Aplicar ──────────────────────────────────────────────────────────────
    if not args.aplicar:
        if divergentes:
            print('  Rode com --aplicar para corrigir as divergências acima.')
        else:
            print('  Nenhuma divergência encontrada. Banco está atualizado.')
        print()
        return

    if not divergentes:
        print('  Nada a corrigir.')
        print()
        return

    print(f'  Aplicando correções em {len(divergentes)} thread(s)...\n')
    corrigidas = 0
    for d in divergentes:
        try:
            salvar_thread(d['dados'])
            corrigidas += 1
            print(f'  ✓ Atualizada: {d["assunto"]} ({d["qtd_banco"]} → {d["qtd_gmail"]} msgs)')
        except Exception as e:
            print(f'  ✗ Erro ao salvar {d["thread_id"]}: {e}')

    print(f'\n  Concluído: {corrigidas}/{len(divergentes)} threads atualizadas.')
    print()


if __name__ == '__main__':
    main()
