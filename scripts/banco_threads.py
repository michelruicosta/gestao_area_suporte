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

# §8.7 — assuntos de e-mails internos informativos (Finaud→Finaud sem ação pendente)
_ASSUNTOS_INFORMATIVOS = (
    'divulgação',
    'boas-vindas',
    'comunicado de saída',
    'comunicado de saida',
)

# §8.6 — detecta separador de Forwarded message (Formato A)
_FORWARD_SEP_RE = re.compile(
    r'-{5,}\s*(?:forwarded message|mensagem encaminhada)\s*-{5,}',
    re.IGNORECASE,
)
# Extensões de imagens inline — não contam como arquivo entregável (§8.6)
_IMAGENS_INLINE = frozenset({
    '.png', '.gif', '.jpg', '.jpeg', '.bmp', '.ico',
    '.webp', '.tif', '.tiff', '.svg',
})

# §8.8 — cliente encaminhou: prefixo ENC:/FWD: ou assunto com EXTRATO sem prefixo
_ENC_PREFIX = re.compile(r'^(enc|fwd?)\s*:', re.IGNORECASE)
_EXTRATO_RE = re.compile(r'\bextratos?\b', re.IGNORECASE)

# §8.9 — saudações com "?" que não indicam pedido de ação do cliente
_SAUDACOES_PERGUNTA = re.compile(r'\btudo\s+(?:bem|bom|certo)\s*\?', re.IGNORECASE)

# §8.10 — notificação de reação do Teams ("reacted to your message")
_REACAO_TEAMS_RE = re.compile(r'reacted to your message|reagiu à sua mensagem', re.IGNORECASE)


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

            CREATE TABLE IF NOT EXISTS snapshots (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT NOT NULL,
                categoria TEXT NOT NULL,
                af        INTEGER NOT NULL DEFAULT 0,
                ac        INTEGER NOT NULL DEFAULT 0,
                co        INTEGER NOT NULL DEFAULT 0,
                total     INTEGER NOT NULL DEFAULT 0
            );
        """)
        # Migração segura: adiciona colunas novas sem recriar o banco
        for col_def in [
            'motivo_classificacao TEXT',
            'motivo_status TEXT',
            'destinatario_principal TEXT',
            'remetente_ultima_msg TEXT',
            'destinatario_ultima_msg TEXT',
            'reply_to_ultima_msg TEXT',
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
    'informo que foi encaminhado',
    'informamos que foi encaminhado',
    'foi encaminhado ao bc',
    'foi encaminhado ao bacen',
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


def _tem_pergunta_acao(texto: str) -> bool:
    """§8.9: True se o texto tem pergunta real que exige ação do cliente.
    Remove URLs, cabeçalhos XML e saudações com '?' antes de checar."""
    t = re.sub(r'<https?://[^>]+>', '', texto)        # links <https://...>
    t = re.sub(r'https?://\S+', '', t)                # URLs soltas
    t = re.sub(r'^\s*<\?xml\b.*$', '', t, flags=re.MULTILINE)  # cabeçalho XML
    t = _SAUDACOES_PERGUNTA.sub('', t)                # "Tudo bem?", "Tudo bom?"
    return '?' in t


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

    ultimo        = msgs[-1]
    remetente     = (ultimo.get('remetente')     or '').lower()
    reply_to      = (ultimo.get('reply_to')      or '').lower()
    destinatario  = (ultimo.get('destinatarios') or '')
    assunto       = (ultimo.get('assunto')       or '')
    corpo_raw     = (ultimo.get('corpo_texto')   or '')
    tem_anexo     = bool(ultimo.get('nomes_anexos'))

    def _eh_finaud_addr(addr: str) -> bool:
        a = addr.lower()
        return '@finaud.com.br' in a or '@finaudtec.com.br' in a

    def _todos_destinatarios_finaud(campo: str) -> bool:
        """True somente se TODOS os endereços do campo To são @finaud / @finaudtec."""
        if not campo.strip():
            return False
        emails = re.findall(r'<([^>]+)>', campo)
        if not emails:
            emails = [e.strip() for e in re.split(r'[,;]', campo) if e.strip()]
        return bool(emails) and all(_eh_finaud_addr(e) for e in emails)

    eh_finaud_raw = _eh_finaud_addr(remetente)
    # Se From=suporte@ mas Reply-To é externo → é cliente enviando via suporte (§7)
    via_suporte = (eh_finaud_raw and reply_to and not _eh_finaud_addr(reply_to))
    eh_finaud   = eh_finaud_raw and not via_suporte
    para_finaud = _todos_destinatarios_finaud(destinatario)

    texto_novo  = _extrair_texto_novo(corpo_raw)
    texto_lower = texto_novo.lower()

    # §8.10: reação do Teams → cliente confirmou recebimento de mensagem da Finaud
    if _REACAO_TEAMS_RE.search(texto_novo):
        return 'Concluída', 'Cliente confirmou recebimento — reação do Teams'

    # ── Helpers §8.6 — detecção de forward ───────────────────────────────────

    def _tem_arquivo_entregavel(anexos: list) -> bool:
        """True se tem pelo menos um arquivo que não é imagem inline (§8.6)."""
        for a in (anexos or []):
            ext = ('.' + a.rsplit('.', 1)[-1].lower()) if '.' in a else ''
            if ext not in _IMAGENS_INLINE:
                return True
        return False

    def _eh_forward_para_cliente(texto: str) -> bool:
        """§8.6: True se o corpo contém forward cujo Para: aponta para cliente externo."""
        # Formato A: separador com traços
        m = _FORWARD_SEP_RE.search(texto)
        if m:
            trecho = texto[m.end():]
            mp = re.search(
                r'(?:^|\n)[>\s]*(?:para|to)\s*:\s*(.+)',
                trecho[:600], re.IGNORECASE,
            )
            if mp:
                emails = re.findall(r'<([^>]+)>', mp.group(1))
                if not emails:
                    emails = re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        mp.group(1),
                    )
                if emails and any(not _eh_finaud_addr(e) for e in emails):
                    return True
        # Formato B: headers citados com > (> De: @finaud ... > Para: cliente)
        de_m = re.search(
            r'(?:^|\n)\s*>\s*(?:de|from)\s*:.*?@(?:finaud|finaudtec)',
            texto, re.IGNORECASE,
        )
        if de_m:
            trecho_b = texto[de_m.start():]
            mp_b = re.search(
                r'(?:^|\n)\s*>\s*(?:para|to)\s*:\s*(.+)',
                trecho_b[:500], re.IGNORECASE,
            )
            if mp_b:
                emails = re.findall(r'<([^>]+)>', mp_b.group(1))
                if not emails:
                    emails = re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        mp_b.group(1),
                    )
                if emails and any(not _eh_finaud_addr(e) for e in emails):
                    return True
        return False

    # Regra especial §8.3: "transmitido no BACEN" encerra independente de quem mandou
    if 'transmitido no bacen' in texto_lower or 'transmitida no bacen' in texto_lower:
        return 'Concluída', 'Confirmação de entrega no BACEN'

    if eh_finaud:
        # Finaud → Finaud: verificar se é forward de entrega ao cliente (§8.6 Cenário 1)
        if para_finaud:
            if _eh_forward_para_cliente(corpo_raw):
                # Sub-caso 1a: tem arquivo real → Concluída
                if _tem_arquivo_entregavel(ultimo.get('nomes_anexos') or []):
                    return 'Concluída', 'Finaud entregou arquivo ao cliente e registrou internamente'
                # Sub-caso 1b: verificar sinal de conclusão
                if assunto.strip().upper().startswith('RES:'):
                    return 'Concluída', 'Finaud encaminhou confirmação ao cliente e registrou internamente'
                if any(f in texto_lower for f in _FRASES_CONCLUSIVAS_FINAUD):
                    return 'Concluída', 'Finaud encaminhou confirmação ao cliente e registrou internamente'
                # 1b-padrão: sem sinal claro → Aguardando Cliente (erro mais seguro)
                return 'Aguardando Cliente', 'Finaud escreveu ao cliente — aguarda retorno'
            # E-mail interno genuíno (Cenário 3)
            # §8.7: assunto informativo → sem ação pendente (strip RES:/ENC: antes)
            assunto_lower = re.sub(r'^(res|enc|fwd|fw)\s*:\s*', '', assunto.strip(), flags=re.IGNORECASE).lower()
            if any(assunto_lower.startswith(p) for p in _ASSUNTOS_INFORMATIVOS):
                return 'Concluída', 'Informativo interno — sem pendência'
            return 'Aguardando Finaud', 'E-mail interno — aguarda ação da Finaud'
        # Finaud → Cliente
        if tem_anexo:
            # §8.9: arquivo + pergunta real → cliente precisa responder
            if _tem_pergunta_acao(texto_novo):
                return 'Aguardando Cliente', 'Finaud enviou arquivo e aguarda resposta do cliente'
            return 'Concluída', 'Finaud enviou arquivo ao cliente'
        if assunto.strip().upper().startswith('RES:'):
            return 'Concluída', 'Finaud respondeu ao cliente'
        if any(f in texto_lower for f in _FRASES_CONCLUSIVAS_FINAUD):
            return 'Concluída', 'Finaud encerrou a conversa'
        return 'Aguardando Cliente', 'Finaud escreveu — aguarda retorno do cliente'

    # Remetente externo (cliente)
    # §8.8: cliente encaminhou algo (ENC:/FWD: ou assunto com EXTRATO) com texto vazio → Finaud precisa processar
    if _so_cortesia(texto_novo) and (_ENC_PREFIX.match(assunto.strip()) or _EXTRATO_RE.search(assunto)):
        return 'Aguardando Finaud', 'Cliente encaminhou — aguarda processamento da Finaud'
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
    remetente_primeiro    = msgs[0].get('remetente', '')     if msgs else ''
    destinatario_primeiro = msgs[0].get('destinatarios', '') if msgs else ''
    remetente_ultimo      = msgs[-1].get('remetente', '')    if msgs else ''
    destinatario_ultimo   = msgs[-1].get('destinatarios', '') if msgs else ''
    reply_to_ultimo       = msgs[-1].get('reply_to', '')     if msgs else ''
    novo_status, novo_motivo = _determinar_status(msgs)

    with _conectar() as conn:
        conn.execute("""
            INSERT INTO threads
                (thread_id, assunto, qtd_mensagens, data_primeira_msg,
                 data_ultima_msg, remetente_principal, destinatario_principal,
                 remetente_ultima_msg, destinatario_ultima_msg, reply_to_ultima_msg,
                 mensagens_json, ultima_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                assunto                 = excluded.assunto,
                qtd_mensagens           = excluded.qtd_mensagens,
                data_ultima_msg         = excluded.data_ultima_msg,
                remetente_principal     = excluded.remetente_principal,
                destinatario_principal  = excluded.destinatario_principal,
                remetente_ultima_msg    = excluded.remetente_ultima_msg,
                destinatario_ultima_msg = excluded.destinatario_ultima_msg,
                reply_to_ultima_msg     = excluded.reply_to_ultima_msg,
                mensagens_json          = excluded.mensagens_json,
                ultima_sync             = excluded.ultima_sync
        """, (
            thread['thread_id'],
            thread.get('assunto', ''),
            thread.get('qtd_mensagens', len(msgs)),
            thread.get('data_primeira_msg', ''),
            thread.get('data_ultima_msg', ''),
            remetente_primeiro,
            destinatario_primeiro,
            remetente_ultimo,
            destinatario_ultimo,
            reply_to_ultimo,
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
        status, motivo      = _determinar_status(msgs)
        dest_primeiro       = msgs[0].get('destinatarios', '')  if msgs else ''
        rem_ultimo          = msgs[-1].get('remetente', '')      if msgs else ''
        dest_ultimo         = msgs[-1].get('destinatarios', '')  if msgs else ''
        reply_to_ultimo     = msgs[-1].get('reply_to', '')       if msgs else ''
        with _conectar() as conn:
            conn.execute("""
                UPDATE threads
                SET status_workflow         = ?,
                    motivo_status           = ?,
                    destinatario_principal  = ?,
                    remetente_ultima_msg    = ?,
                    destinatario_ultima_msg = ?,
                    reply_to_ultima_msg     = ?
                WHERE thread_id = ?
            """, (status, motivo, dest_primeiro,
                  rem_ultimo, dest_ultimo, reply_to_ultimo, row['thread_id']))
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
                   remetente_ultima_msg, destinatario_ultima_msg, reply_to_ultima_msg,
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


# ── Snapshots de contadores por categoria ────────────────────────────────────

def salvar_snapshot() -> None:
    """Grava o estado atual dos contadores por categoria — chamado pelo coletor antes de cada rodada."""
    threads = buscar_por_destino('principal')
    contagens: dict[str, dict] = {}
    for t in threads:
        cat    = t.get('categoria') or 'DESCONHECIDA'
        status = t.get('status_workflow') or 'Aguardando Finaud'
        if cat not in contagens:
            contagens[cat] = {'af': 0, 'ac': 0, 'co': 0}
        if status == 'Aguardando Finaud':
            contagens[cat]['af'] += 1
        elif status == 'Aguardando Cliente':
            contagens[cat]['ac'] += 1
        elif status == 'Concluída':
            contagens[cat]['co'] += 1
    agora = _agora()
    with _conectar() as conn:
        conn.execute('DELETE FROM snapshots')
        conn.executemany(
            'INSERT INTO snapshots (data_hora, categoria, af, ac, co, total) VALUES (?,?,?,?,?,?)',
            [(agora, cat, c['af'], c['ac'], c['co'], c['af'] + c['ac'] + c['co'])
             for cat, c in contagens.items()],
        )


def ler_ultimo_snapshot() -> dict[str, dict]:
    """Retorna o último snapshot salvo como {categoria_id: {af, ac, co, total}}. Vazio se não houver snapshot."""
    with _conectar() as conn:
        rows = conn.execute(
            'SELECT categoria, af, ac, co, total FROM snapshots'
        ).fetchall()
    return {r['categoria']: dict(r) for r in rows}


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
