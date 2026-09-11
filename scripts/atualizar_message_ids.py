"""
atualizar_message_ids.py
O que faz: para cada thread aberta (AF/AC) sem Message-ID no banco,
           re-busca no Gmail e preenche o campo message_id nas mensagens.
           Não altera status, contagem, texto nem nenhum outro campo.

Uso:
  python scripts/atualizar_message_ids.py           → diagnóstico (não salva)
  python scripts/atualizar_message_ids.py --aplicar → aplica no banco
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coletor_gmail import _conectar_gmail, _processar_thread

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'gestao.db')


def _threads_sem_mid() -> list[dict]:
    """Retorna threads abertas onde nenhuma mensagem tem message_id."""
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


def _chave(m: dict) -> tuple[str, str]:
    """Chave de correspondência: (data, remetente)."""
    return (m.get('data', '').strip(), m.get('remetente', '').strip())


def _preencher_mids(msgs_banco: list[dict], msgs_gmail: list[dict]) -> tuple[list[dict], int]:
    """
    Para cada mensagem do banco sem message_id, tenta encontrar
    a correspondente no Gmail pela chave (data, remetente).
    Retorna a lista atualizada e quantos MIDs foram preenchidos.
    """
    # Indexar Gmail por chave
    indice: dict[tuple, str] = {}
    for m in msgs_gmail:
        mid = m.get('message_id', '').strip()
        if mid:
            chave = _chave(m)
            indice[chave] = mid

    atualizados = 0
    for m in msgs_banco:
        if m.get('message_id'):
            continue
        mid = indice.get(_chave(m))
        if mid:
            m['message_id'] = mid
            atualizados += 1

    return msgs_banco, atualizados


def _salvar_mid(thread_id: str, msgs: list[dict]) -> None:
    """Atualiza APENAS mensagens_json — não toca status nem nenhum outro campo."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE threads SET mensagens_json = ? WHERE thread_id = ?",
            (json.dumps(msgs, ensure_ascii=False), thread_id)
        )


def main():
    parser = argparse.ArgumentParser(
        description='Preenche Message-IDs ausentes nas threads abertas.'
    )
    parser.add_argument('--aplicar', action='store_true',
                        help='Aplica as atualizações no banco (sem esta flag, só diagnóstico)')
    args = parser.parse_args()

    modo = 'APLICAR' if args.aplicar else 'DIAGNÓSTICO (sem --aplicar, nada será salvo)'
    print(f'\n{"="*65}')
    print(f'  ATUALIZAR MESSAGE-IDs — modo: {modo}')
    print(f'{"="*65}\n')

    threads = _threads_sem_mid()
    print(f'Threads abertas sem Message-ID: {len(threads)}\n')

    if not threads:
        print('Nada a fazer — todas as threads já têm Message-ID.')
        return

    service = _conectar_gmail()

    corrigidas       = 0
    mids_preenchidos = 0
    nao_encontradas  = 0
    erros            = 0
    sem_match        = 0

    for i, t in enumerate(threads, 1):
        tid    = t['thread_id']
        assunto = (t['assunto'] or '')[:52]

        try:
            dados_gmail = _processar_thread(service, tid)
        except Exception as e:
            erros += 1
            if erros <= 5:
                print(f'  [{i:4d}] ERRO    {assunto}: {e}')
            continue

        if dados_gmail is None:
            nao_encontradas += 1
            continue

        msgs_banco = json.loads(t['mensagens_json'] or '[]')
        msgs_gmail = dados_gmail.get('mensagens', [])

        msgs_atualizadas, qtd = _preencher_mids(msgs_banco, msgs_gmail)

        if qtd == 0:
            sem_match += 1
            continue

        mids_preenchidos += qtd
        corrigidas += 1

        if args.aplicar:
            _salvar_mid(tid, msgs_atualizadas)

        if i <= 20 or i % 100 == 0:
            print(f'  [{i:4d}] +{qtd:2d} MID(s)  {assunto}')

        if i % 20 == 0:
            time.sleep(0.5)

    # ── Relatório ────────────────────────────────────────────────────────────────
    print(f'\n{"─"*65}')
    print('  RELATÓRIO')
    print(f'{"─"*65}')
    print(f'  Threads verificadas    : {len(threads):5d}')
    print(f'  Threads corrigidas     : {corrigidas:5d}  ← receberiam Message-IDs')
    print(f'  Message-IDs preenchidos: {mids_preenchidos:5d}')
    print(f'  Sem correspondência    : {sem_match:5d}  (msg do banco sem par no Gmail)')
    print(f'  Sumiram do Gmail       : {nao_encontradas:5d}')
    print(f'  Erros de acesso        : {erros:5d}')
    print()

    if not args.aplicar:
        print('  Rode com --aplicar para gravar os Message-IDs no banco.')
    else:
        print(f'  Concluído: {corrigidas} threads atualizadas, {mids_preenchidos} Message-IDs gravados.')
    print()


if __name__ == '__main__':
    main()
