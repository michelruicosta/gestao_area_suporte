"""
banco_threads.py
O que faz: cria e gerencia o banco de dados SQLite do Oráculo 360 —
           armazena todas as threads coletadas do Gmail, suas classificações
           e o estado de sincronização entre rodadas.
"""

import json
import os
import re
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
                thread_id              TEXT PRIMARY KEY,
                assunto                TEXT,
                qtd_mensagens          INTEGER,
                data_primeira_msg      TEXT,
                data_ultima_msg        TEXT,
                remetente_principal    TEXT,
                mensagens_json         TEXT,
                destino                TEXT,
                categoria              TEXT,
                status_workflow        TEXT,
                motivo_descarte        TEXT,
                motivo_classificacao   TEXT,
                ultima_sync            TEXT
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
        # Migração segura: adiciona colunas novas sem recriar o banco
        for col_def in [
            'motivo_classificacao TEXT',
            'motivo_status TEXT',
            'destinatario_principal TEXT',
        ]:
            try:
                conn.execute(f'ALTER TABLE threads ADD COLUMN {col_def}')
            except Exception:
                pass  # coluna já existe
    print(f'Banco criado/verificado: {BANCO}')


# ── Gravação ───────────────────────────────────────────────────────────────────

def _agora() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── Helpers de detecção de status (§8.1, §8.2, §8.3 da spec) ─────────────────

_SEP_HISTORICO = re.compile(
    r'^(-{3,}|_{3,}|from:|de:|on\s.{3,120}wrote:|em\s.{3,120}escreveu:)',
    re.IGNORECASE,
)

_CORTESIA = re.compile(
    r'\b(obrigad[ao]s?|muito\s+obrigad[ao]s?|ok|de\s+acordo|concordo|recebido|'
    r'perfeito|valeu|confirmado|certo|entendido|tudo\s+bem|sem\s+problemas|'
    r'bom\s+dia|boa\s+tarde|boa\s+noite|at[ée]\s+mais|abraços?|att)\b',
    re.IGNORECASE,
)

_FRASES_CONCLUSIVAS_FINAUD = (
    'segue em anexo',
    'conforme solicitado',
    'procedemos com',
)


def _extrair_texto_novo(corpo: str) -> str:
    """Remove histórico citado do corpo do e-mail; retorna só o texto novo."""
    if not corpo:
        return ''
    linhas = corpo.split('\n')
    resultado = []
    for linha in linhas:
        stripped = linha.strip()
        if stripped.startswith('>'):
            continue
        if _SEP_HISTORICO.match(stripped):
            break
        resultado.append(linha)
    return '\n'.join(resultado).strip()


def _so_cortesia(texto: str) -> bool:
    """True se o texto novo contém apenas frases de cortesia, sem conteúdo substantivo."""
    if not texto.strip():
        return True
    if '?' in texto:
        return False
    restante = _CORTESIA.sub('', texto.lower())
    restante = re.sub(r'[\s,!.;:\-\n\r]+', '', restante)
    return len(restante) < 15


def _determinar_status(msgs: list[dict]) -> tuple[str, str]:
    """
    Determina o status de workflow com base no §8.3 da spec.
    Olha sempre o último e-mail e apenas o texto novo (sem histórico citado).

    Retorna: (status, motivo)
      status: 'Aguardando Finaud' | 'Aguardando Cliente' | 'Concluída'
      motivo: texto amigável para exibição na tela
    """
    if not msgs:
        return 'Aguardando Finaud', 'Sem mensagens registradas'

    ultimo      = msgs[-1]
    remetente   = (ultimo.get('remetente')   or '').lower()
    assunto     = (ultimo.get('assunto')     or '')
    corpo_raw   = (ultimo.get('corpo_texto') or '')
    tem_anexo   = bool(ultimo.get('nomes_anexos'))
    eh_finaud   = '@finaud.com.br' in remetente or '@finaudtec.com.br' in remetente

    texto_novo  = _extrair_texto_novo(corpo_raw)
    texto_lower = texto_novo.lower()

    # Regra especial §8.3: "transmitido no BACEN" encerra independente de quem mandou
    if 'transmitido no bacen' in texto_lower or 'transmitida no bacen' in texto_lower:
        return 'Concluída', 'Confirmação de entrega no BACEN'

    if eh_finaud:
        if tem_anexo:
            return 'Concluída', 'Finaud enviou arquivo ao cliente'
        if assunto.strip().upper().startswith('RES:'):
            return 'Concluída', 'Finaud respondeu ao cliente'
        if any(f in texto_lower for f in _FRASES_CONCLUSIVAS_FINAUD):
            return 'Concluída', 'Finaud encerrou a conversa'
        return 'Aguardando Cliente', 'Finaud escreveu — aguarda retorno do cliente'

    # Remetente externo (cliente)
    # Veto: qualquer conteúdo real → Aguardando Finaud; só cortesia → Concluída
    if _so_cortesia(texto_novo):
        return 'Concluída', 'Cliente confirmou — sem pendência'
    return 'Aguardando Finaud', 'Cliente escreveu — aguarda resposta da Finaud'


def salvar_thread(thread: dict) -> None:
    """
    Insere ou atualiza uma thread no banco.
    - Nova thread: salva os campos do Gmail; destino/categoria/status ficam NULL.
    - Thread existente: atualiza campos do Gmail e, se já classificada
      (destino='principal'), atualiza status_workflow automaticamente baseado
      em quem enviou a última mensagem.
    """
    msgs = thread.get('mensagens', [])
    remetente    = msgs[0].get('remetente', '')    if msgs else ''
    destinatario = msgs[0].get('destinatarios', '') if msgs else ''
    novo_status, novo_motivo = _determinar_status(msgs)

    with _conectar() as conn:
        conn.execute("""
            INSERT INTO threads
                (thread_id, assunto, qtd_mensagens, data_primeira_msg,
                 data_ultima_msg, remetente_principal, destinatario_principal,
                 mensagens_json, ultima_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                assunto                = excluded.assunto,
                qtd_mensagens          = excluded.qtd_mensagens,
                data_ultima_msg        = excluded.data_ultima_msg,
                remetente_principal    = excluded.remetente_principal,
                destinatario_principal = excluded.destinatario_principal,
                mensagens_json         = excluded.mensagens_json,
                ultima_sync            = excluded.ultima_sync
        """, (
            thread['thread_id'],
            thread.get('assunto', ''),
            thread.get('qtd_mensagens', len(msgs)),
            thread.get('data_primeira_msg', ''),
            thread.get('data_ultima_msg', ''),
            remetente,
            destinatario,
            json.dumps(msgs, ensure_ascii=False),
            _agora(),
        ))
        # Atualiza status automaticamente apenas em threads já na Tela Principal
        conn.execute("""
            UPDATE threads SET status_workflow = ?, motivo_status = ?
            WHERE thread_id = ? AND destino = 'principal'
        """, (novo_status, novo_motivo, thread['thread_id']))


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
    motivo_classificacao: str | None = None,
) -> None:
    """
    Grava o resultado do classificador no banco.
    destino: 'principal' | 'revisao' | 'descartes'
    Threads que vão para 'principal' começam como 'Aguardando Finaud'.
    motivo_classificacao: a regra que determinou a categoria (exibida no tooltip).
    """
    if destino == 'principal':
        with _conectar() as conn:
            row = conn.execute(
                "SELECT mensagens_json FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        msgs = json.loads(row['mensagens_json']) if row and row['mensagens_json'] else []
        status, motivo_status = _determinar_status(msgs)
    else:
        status = None
        motivo_status = None

    with _conectar() as conn:
        conn.execute("""
            UPDATE threads
            SET destino              = ?,
                categoria            = ?,
                status_workflow      = ?,
                motivo_status        = ?,
                motivo_descarte      = ?,
                motivo_classificacao = ?
            WHERE thread_id = ?
        """, (destino, categoria, status, motivo_status,
               motivo_descarte, motivo_classificacao, thread_id))


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


def recalcular_status_todos() -> int:
    """
    Recalcula status_workflow, motivo_status e destinatario_principal
    para todas as threads do destino 'principal'.
    Usado para backfill após migrações de schema.
    Retorna o número de threads atualizadas.
    """
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT thread_id, mensagens_json FROM threads WHERE destino = 'principal'"
        ).fetchall()
    atualizadas = 0
    for row in rows:
        msgs = json.loads(row['mensagens_json']) if row['mensagens_json'] else []
        status, motivo  = _determinar_status(msgs)
        destinatario    = msgs[0].get('destinatarios', '') if msgs else ''
        with _conectar() as conn:
            conn.execute("""
                UPDATE threads
                SET status_workflow        = ?,
                    motivo_status          = ?,
                    destinatario_principal = ?
                WHERE thread_id = ?
            """, (status, motivo, destinatario, row['thread_id']))
        atualizadas += 1
    return atualizadas


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
                   data_ultima_msg, remetente_principal, destinatario_principal,
                   destino, categoria, status_workflow, motivo_status,
                   motivo_descarte, motivo_classificacao
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
