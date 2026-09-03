"""
migrar_html_para_texto.py
Atualiza as threads que têm '[somente HTML]' no corpo, buscando o HTML real
no Gmail e convertendo para texto plano. Não altera categoria nem status.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coletor_gmail import _conectar_gmail, _processar_thread
from paths import criar_log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO_DB = os.path.join(BASE_DIR, 'data', 'gestao.db')

log = criar_log('migrar_html')


def _threads_com_html(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT thread_id, mensagens_json
        FROM threads
        WHERE mensagens_json LIKE '%[somente HTML]%'
    """)
    return cur.fetchall()


def _atualizar_mensagens_json(conn: sqlite3.Connection, thread_id: str,
                               mensagens_novas: list[dict]) -> None:
    conn.execute(
        "UPDATE threads SET mensagens_json = ?, ultima_sync = datetime('now') "
        "WHERE thread_id = ?",
        (json.dumps(mensagens_novas, ensure_ascii=False), thread_id),
    )


def migrar() -> None:
    log.info('=' * 60)
    log.info('MIGRAÇÃO: [somente HTML] → texto extraído do HTML')
    log.info('=' * 60)

    conn = sqlite3.connect(BANCO_DB)
    conn.row_factory = sqlite3.Row

    pendentes = _threads_com_html(conn)
    log.info('Threads com [somente HTML]: %d', len(pendentes))

    if not pendentes:
        log.info('Nada a migrar.')
        conn.close()
        return

    service = _conectar_gmail()

    atualizadas = 0
    erros = 0

    for i, (thread_id, msgs_json_raw) in enumerate(pendentes, 1):
        try:
            msgs_antigas = json.loads(msgs_json_raw)
            tem_html = any(m.get('corpo_texto') == '[somente HTML]' for m in msgs_antigas)
            if not tem_html:
                continue

            thread_nova = _processar_thread(service, thread_id)
            if not thread_nova:
                log.warning('[%d/%d] Falha ao buscar thread %s', i, len(pendentes), thread_id)
                erros += 1
                continue

            msgs_novas = thread_nova['mensagens']

            # Preserva campos que não são do coletor (p.ex. campos extras gravados por outras funções)
            for j, (antiga, nova) in enumerate(zip(msgs_antigas, msgs_novas)):
                for campo in antiga:
                    if campo not in nova:
                        nova[campo] = antiga[campo]

            _atualizar_mensagens_json(conn, thread_id, msgs_novas)
            conn.commit()

            convertidos = sum(
                1 for a, n in zip(msgs_antigas, msgs_novas)
                if a.get('corpo_texto') == '[somente HTML]' and n.get('corpo_texto') != '[somente HTML]'
            )
            assunto = thread_nova.get('assunto', '')[:60]
            log.info('[%d/%d] ✓ %s — %d msg(s) convertida(s)', i, len(pendentes), assunto, convertidos)
            atualizadas += 1

            time.sleep(0.05)

        except Exception as exc:
            log.error('[%d/%d] Erro em %s: %s', i, len(pendentes), thread_id, exc)
            erros += 1

    conn.close()
    log.info('=' * 60)
    log.info('Migração concluída: %d atualizadas | %d erros', atualizadas, erros)
    log.info('=' * 60)


if __name__ == '__main__':
    migrar()
