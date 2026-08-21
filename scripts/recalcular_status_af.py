"""
recalcular_status_af.py
Recalcula o status das threads atualmente em "Aguardando Finaud" cujo último remetente
é um cliente externo — corrigindo as que deveriam ser "Concluída" pelo Fix H.

Uso: python scripts/recalcular_status_af.py [--dry-run]

  --dry-run   Mostra o que seria alterado sem gravar no banco.

Saída: lista de threads alteradas + contagem.
"""
import argparse, json, sqlite3, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import banco_threads as bt

BANCO = os.path.join(os.path.dirname(__file__), '..', 'data', 'oraculo360.db')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row

    threads = conn.execute(
        "SELECT thread_id, assunto, categoria, mensagens_json "
        "FROM threads WHERE status_workflow = 'Aguardando Finaud'"
    ).fetchall()

    alteradas = []
    for t in threads:
        msgs = json.loads(t['mensagens_json'] or '[]')
        if not msgs:
            continue
        novo_status, motivo = bt._determinar_status(msgs)
        if novo_status == 'Concluída':
            alteradas.append({
                'thread_id': t['thread_id'],
                'assunto': t['assunto'],
                'categoria': t['categoria'],
                'motivo': motivo,
            })

    print(f"\nThreads que mudariam de AF → Concluída: {len(alteradas)}\n")
    for a in alteradas:
        print(f"  [{a['categoria']}] {a['assunto'][:80]}")
        print(f"    Motivo: {a['motivo']}\n")

    if not alteradas:
        print("Nenhuma alteração necessária.")
        conn.close()
        return

    if args.dry_run:
        print("DRY-RUN: nenhuma alteração gravada.")
        conn.close()
        return

    ids = [a['thread_id'] for a in alteradas]
    conn.execute(
        f"UPDATE threads SET status_workflow = 'Concluída', "
        f"motivo_status = 'Fix H: cliente agradeceu sem pergunta ou documento' "
        f"WHERE thread_id IN ({','.join('?' * len(ids))})",
        ids,
    )
    conn.commit()
    conn.close()
    print(f"✅ {len(alteradas)} thread(s) atualizadas para Concluída.")


if __name__ == '__main__':
    main()
