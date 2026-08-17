"""
banco_threads.py
O que faz: cria e gerencia o banco de dados SQLite do Oráculo 360 —
           armazena todas as threads coletadas do Gmail, suas classificações
           e o estado de sincronização entre rodadas.
"""

import json
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO    = os.path.join(BASE_DIR, 'data', 'oraculo360.db')


# ── Conexão ────────────────────────────────────────────────────────────────────

def _conectar() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(BANCO), exist_ok=True)
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
    return conn


# ── Criação do banco ───────────────────────────────────────────────────────────

def criar_banco() -> None:
    """Cria o banco e as tabelas, se ainda não existirem."""
    with _conectar() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS threads (
                thread_id           TEXT PRIMARY KEY,
                assunto             TEXT,
                qtd_mensagens       INTEGER,
                data_primeira_msg   TEXT,
                data_ultima_msg     TEXT,
                remetente_principal TEXT,
                mensagens_json      TEXT,
                destino             TEXT,
                categoria           TEXT,
                status_workflow     TEXT,
                motivo_descarte     TEXT,
                ultima_sync         TEXT
            );

            CREATE TABLE IF NOT EXISTS controle_sync (
                chave TEXT PRIMARY KEY,
                valor TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_destino
                ON threads (destino);

            CREATE INDEX IF NOT EXISTS idx_data_ultima
                ON threads (data_ultima_msg);
        """)
    print(f'Banco criado/verificado: {BANCO}')


# ── Gravação ───────────────────────────────────────────────────────────────────

def _agora() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def salvar_thread(thread: dict) -> None:
    """
    Insere ou atualiza uma thread no banco.
    Em caso de conflito (thread já existe), atualiza os campos do Gmail mas
    preserva destino, categoria, status e motivo_descarte — que são definidos
    pelo classificador ou pelo Michel, não pelo coletor.
    """
    msgs = thread.get('mensagens', [])
    remetente = msgs[0].get('remetente', '') if msgs else ''

    with _conectar() as conn:
        conn.execute("""
            INSERT INTO threads
                (thread_id, assunto, qtd_mensagens, data_primeira_msg,
                 data_ultima_msg, remetente_principal, mensagens_json, ultima_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                assunto             = excluded.assunto,
                qtd_mensagens       = excluded.qtd_mensagens,
                data_ultima_msg     = excluded.data_ultima_msg,
                remetente_principal = excluded.remetente_principal,
                mensagens_json      = excluded.mensagens_json,
                ultima_sync         = excluded.ultima_sync
        """, (
            thread['thread_id'],
            thread.get('assunto', ''),
            thread.get('qtd_mensagens', len(msgs)),
            thread.get('data_primeira_msg', ''),
            thread.get('data_ultima_msg', ''),
            remetente,
            json.dumps(msgs, ensure_ascii=False),
            _agora(),
        ))


def salvar_threads(threads: list[dict]) -> None:
    """Salva uma lista de threads (importação histórica em lote)."""
    for t in threads:
        salvar_thread(t)


# ── Classificação ──────────────────────────────────────────────────────────────

def atualizar_classificacao(
    thread_id: str,
    destino: str,
    categoria: str | None = None,
    motivo_descarte: str | None = None,
) -> None:
    """
    Grava o resultado do classificador no banco.
    destino: 'principal' | 'revisao' | 'descartes'
    Threads que vão para 'principal' começam como 'Aguardando Finaud'.
    """
    status = 'Aguardando Finaud' if destino == 'principal' else None
    with _conectar() as conn:
        conn.execute("""
            UPDATE threads
            SET destino         = ?,
                categoria       = ?,
                status_workflow = ?,
                motivo_descarte = ?
            WHERE thread_id = ?
        """, (destino, categoria, status, motivo_descarte, thread_id))


def classificar_manual(thread_id: str, categoria: str) -> None:
    """
    Registra classificação manual feita pelo Michel na Tela de Revisão.
    Move a thread de 'revisao' para 'principal'.
    """
    with _conectar() as conn:
        conn.execute("""
            UPDATE threads
            SET destino         = 'principal',
                categoria       = ?,
                status_workflow = 'Aguardando Finaud'
            WHERE thread_id = ?
        """, (categoria, thread_id))


def atualizar_status(thread_id: str, status_workflow: str) -> None:
    """Atualiza o status de workflow de uma thread (chamado pela Tela Principal)."""
    with _conectar() as conn:
        conn.execute(
            "UPDATE threads SET status_workflow = ? WHERE thread_id = ?",
            (status_workflow, thread_id)
        )


# ── Consultas ──────────────────────────────────────────────────────────────────

def buscar_sem_classificar() -> list[dict]:
    """Retorna threads que o classificador ainda não processou."""
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM threads WHERE destino IS NULL ORDER BY data_ultima_msg DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def buscar_por_destino(destino: str) -> list[dict]:
    """
    Retorna threads de um destino específico para as telas.
    Não inclui mensagens_json (pesado) — use buscar_thread_completa para detalhes.
    """
    with _conectar() as conn:
        rows = conn.execute("""
            SELECT thread_id, assunto, qtd_mensagens, data_primeira_msg,
                   data_ultima_msg, remetente_principal,
                   destino, categoria, status_workflow, motivo_descarte
            FROM   threads
            WHERE  destino = ?
            ORDER  BY data_ultima_msg DESC
        """, (destino,)).fetchall()
    return [dict(r) for r in rows]


def buscar_thread_completa(thread_id: str) -> dict | None:
    """
    Retorna uma thread com o conteúdo completo das mensagens.
    Usado pelo modal de detalhes nas telas.
    """
    with _conectar() as conn:
        row = conn.execute(
            "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get('mensagens_json'):
        d['mensagens'] = json.loads(d['mensagens_json'])
    del d['mensagens_json']
    return d


def contar_por_destino() -> dict:
    """
    Retorna contagens para o cabeçalho das telas:
    { principal: N, revisao: N, descartes: N, sem_classificar: N, total: N }
    """
    with _conectar() as conn:
        rows = conn.execute("""
            SELECT COALESCE(destino, 'sem_classificar') AS destino,
                   COUNT(*) AS total
            FROM   threads
            GROUP  BY destino
        """).fetchall()
    contagens: dict = {'principal': 0, 'revisao': 0, 'descartes': 0, 'sem_classificar': 0}
    for row in rows:
        chave = row['destino']
        if chave in contagens:
            contagens[chave] = row['total']
    contagens['total'] = sum(v for k, v in contagens.items() if k != 'total')
    return contagens


# ── Controle de sincronização com o Gmail ─────────────────────────────────────

def get_controle_sync(chave: str) -> str | None:
    """Lê o último marcador de sincronização (ex: historyId do Gmail)."""
    with _conectar() as conn:
        row = conn.execute(
            "SELECT valor FROM controle_sync WHERE chave = ?", (chave,)
        ).fetchone()
    return row['valor'] if row else None


def set_controle_sync(chave: str, valor: str) -> None:
    """Grava o marcador de sincronização após cada coleta bem-sucedida."""
    with _conectar() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO controle_sync (chave, valor) VALUES (?, ?)",
            (chave, valor)
        )


# ── Execução direta (teste rápido) ────────────────────────────────────────────

if __name__ == '__main__':
    criar_banco()
    contagens = contar_por_destino()
    print(f'Threads no banco : {contagens}')
