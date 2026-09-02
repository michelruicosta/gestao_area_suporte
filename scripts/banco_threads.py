"""
banco_threads.py
O que faz: cria e gerencia o banco de dados SQLite do Gestão Área Suporte —
           armazena todas as threads coletadas do Gmail, suas classificações
           e o estado de sincronização entre rodadas.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO    = os.path.join(BASE_DIR, 'data', 'gestao.db')

# ── Passo C: termos gerenciados via tela de manutenção ───────────────────────
_REGRAS_CACHE: dict[str, list[str]] = {}

def recarregar_regras_do_banco() -> None:
    """Recarrega os termos de classificação da tabela regras_classificacao."""
    global _REGRAS_CACHE
    try:
        with _conectar() as conn:
            rows = conn.execute(
                "SELECT motivo, termos FROM regras_classificacao WHERE situacao = 'Ativa'"
            ).fetchall()
        _REGRAS_CACHE = {r[0]: json.loads(r[1]) for r in rows}
    except Exception:
        pass  # banco ainda não tem a tabela ou não está disponível

def _termos_db(motivo: str) -> tuple[str, ...]:
    """Retorna termos extras do banco para um motivo (vazio se não houver)."""
    if not _REGRAS_CACHE:
        recarregar_regras_do_banco()
    return tuple(_REGRAS_CACHE.get(motivo, []))

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

# §8.3 — bloco de assinatura: sign-off antes do nome/cargo/telefone/URLs
# Detecta palavras de encerramento ("Atenciosamente", "Att", etc.) que marcam o início
# do rodapé do e-mail. Tudo depois do sign-off é assinatura e deve ser ignorado ao
# verificar se o texto é "só cortesia" (_so_cortesia).
# Nota: U+200B (zero-width space) é removido do texto ANTES de aplicar esta regex,
# então o padrão usa apenas espaço e tab (não é necessário incluir ​ aqui).
_SIGN_OFF_RE = re.compile(
    r'(?:^|\r?\n)[ \t]*'
    r'(?:atenciosamente|att\.?|cordialmente|abra[cç]os?|regards?|sinceramente|'
    r'com\s+respeito|best\s+regards?|kind\s+regards?|grat[ao])'
    r'[ \t]*[,.]?[ \t]*(?:\r?\n|$)',
    re.IGNORECASE,
)


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

            CREATE TABLE IF NOT EXISTS log_coletas (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora         TEXT NOT NULL,
                tipo              TEXT NOT NULL,
                threads_proc      INTEGER NOT NULL DEFAULT 0,
                erros             INTEGER NOT NULL DEFAULT 0,
                duracao_seg       REAL,
                status            TEXT NOT NULL,
                mensagem          TEXT,
                classif_principal INTEGER NOT NULL DEFAULT 0,
                classif_descartes INTEGER NOT NULL DEFAULT 0,
                classif_revisao   INTEGER NOT NULL DEFAULT 0
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
            'visto_em TEXT',
            'inativa_desde TEXT',
        ]:
            try:
                conn.execute(f'ALTER TABLE threads ADD COLUMN {col_def}')
            except Exception:
                pass  # coluna já existe
        for col_def in [
            'classif_principal INTEGER NOT NULL DEFAULT 0',
            'classif_descartes INTEGER NOT NULL DEFAULT 0',
            'classif_revisao   INTEGER NOT NULL DEFAULT 0',
        ]:
            try:
                conn.execute(f'ALTER TABLE log_coletas ADD COLUMN {col_def}')
            except Exception:
                pass  # coluna já existe
    print(f'Banco criado/verificado: {BANCO}')


# ── Gravação ───────────────────────────────────────────────────────────────────

def _agora() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── Helpers de detecção de status (§8.1, §8.2, §8.3 da spec) ─────────────────

_SEP_HISTORICO = re.compile(
    r'^(-{3,}|_{3,}|\*?from:\*?|\*?de:\*?|on\s.{3,120}wrote:|em\s.{3,120}escreveu:)',
    re.IGNORECASE,
)

_CORTESIA = re.compile(
    r'\b(obrigad[ao]s?|muito\s+obrigad[ao]s?|ok|de\s+acordo|concordo|recebido|'
    r'perfeito|valeu|confirmado|certo|entendido|tudo\s+bem|sem\s+problemas|'
    r'bom\s+dia|boa\s+tarde|boa\s+noite|bom\s+final\s+de\s+semana|boa\s+semana|'
    r'nos?\s+ajudou|me\s+ajudou|ajudou\s+(?:muito|bastante)|'
    r'at[ée]\s+mais|abraços?|att)\b',
    re.IGNORECASE,
)

# Palavras que indicam confirmação explícita do cliente (distintas de mera saudação).
# "Boa tarde + Att" = saudação pura → NÃO confirma nada → não deve marcar Concluída.
# "Obrigado / Deu certo / Ok" = confirmação explícita → pode marcar Concluída.
_CONFIRMACAO_EXPLICITA = re.compile(
    r'\b(obrigad[ao]s?|muito\s+obrigad[ao]s?|ok\b|de\s+acordo|concordo|recebido|'
    r'perfeito|valeu|confirmado|entendido|sem\s+problemas|'
    r'nos?\s+ajudou|me\s+ajudou|ajudou|deu\s+certo|voltou|funcionou|resolveu|'
    r'certo\b|tudo\s+(bem|certo|ok|bom)|arquivos?\s+submetidos?|'
    r'pode\s+transmitir|'        # Guru CTVM: "Pode transmitir" = autorização do cliente (01/09/2026)
    r'pode\s+ignorar|'           # BCP: "Pode ignorar meu email" = retratação do cliente (01/09/2026)
    r'conversei\s+internamente|' # Planner SCD: cliente consultou equipe e trouxe resposta (01/09/2026)
    r'credenciamento\s+realizado|'     # VIS DTVM: cadastro no STA do BC concluído (01/09/2026)
    r'foi\s+homologado|'               # Unicred COS4010: "Sim, foi! Foi homologado em 11/03." (01/09/2026)
    r'grat[ao]s?)\b',                  # Kinel: "Grato mais uma vez" = agradecimento formal (01/09/2026)
    re.IGNORECASE,
)

_FRASES_CONCLUSIVAS_FINAUD = (
    'segue em anexo', 'segue anexo', 'seguem anexo', 'seguem em anexo',
    'segue o arquivo', 'segue os arquivos',
    'segue a remessa', 'seguem as remessas', 'seguem remessas',
    'segue protocolo', 'segue o protocolo', 'segue para controle',
    'encaminhamos', 'encaminho',
    'conforme solicitado',
    'procedemos com',
    'informo que foi encaminhado', 'informamos que foi encaminhado',
    'foi encaminhado ao bc', 'foi encaminhado ao bacen',
    'enviamos', 'acabamos de enviar', 'foi enviado', 'ok, enviado',
    'já está disponível', 'ja esta disponivel',
    'transmitimos a versão', 'transmitimos o arquivo', 'transmitimos a remessa',
    'estamos acompanhando o processamento',
    'estamos acompanhando os processamentos',
    'aceite do bc', 'aceite do bacen', 'aceito pelo sistema',
    'foram cadastrad', 'foi cadastrad',
    'foram inativad', 'foi inativad', 'foram ativad', 'foi ativad',
    'providenciamos o reset', 'providenciamos a inativação',
    'providenciamos o cadastro', 'providenciamos a ativação',
    'recebido e enviado', 'ok, recebido e enviado',
    'obrigada pelo retorno', 'obrigado pelo retorno',
    'certo, providenciamos', 'certo, verificamos',
    # Fix P: Finaud respondeu perguntas e ofereceu suporte adicional (sem pedir ação)
    'permanecemos à disposição para esclarecer',
    'permanecemos à disposição para eventuais esclarecimentos',
)

# Finaud prometeu retornar — bola ainda está com a Finaud
_FRASES_AGUARDANDO_FINAUD_ATIVA = (
    'retornaremos em breve', 'retornaremos', 'retornarei',
    'estamos verificando', 'estamos analisando', 'estamos investigando',
    'verificaremos', 'analisaremos', 'vamos verificar', 'vamos analisar',
    'nossa equipe técnica', 'equipe técnica irá', 'em análise',
    'em verificação', 'aguarde o retorno',
    'assim que tiver',
    'pedi para',
    'pedimos para',
    'estarei colocando',  # Fix L: "estarei colocando as remessas em dia" — Finaud prometeu agir
)

# Frases de entrega usadas no branch com arquivo real (superset de _FRASES_CONCLUSIVAS_FINAUD)
_FRASES_ENTREGA = _FRASES_CONCLUSIVAS_FINAUD + (
    'conforme anexo', 'em continuidade, segue',
    'para acompanhamento, conforme',
    'segue o 4111', 'segue a cópia', 'segue o ddr', 'segue o drm',
    'segue o dlo', 'segue o dli', 'segue o drl',
    'segue o scd', 'segue o drsac',
    'segue a apuração', 'obrigada. seguem', 'obrigado. seguem',
    'obrigada, seguem', 'obrigado, seguem',
    'segue o cadoc', 'providenciamos as remessas', 'providenciamos a remessa',
    'seguem os', 'seguem também',
    'providenciamos o ajuste',
    'providenciamos a correção',
    'já concluímos', 'concluímos',
    'enviando em anexo',
    'qualquer dúvida fico a disposição',  # Fix M: Finaud respondeu pergunta e encerrou
    # Termos de entrega do cliente aprovados em 01/09/2026
    'seguem as',        # "Seguem as posições de TVM's..."
    'seguem a ',        # "Seguem a planilha do DRL..."
    'seguem valores',   # "Seguem valores para geração do CADOC 4111..."
    'anexo ',           # "Anexo Posições da Western Union..." (palavra solta)
    'arquivos enviados',  # "Arquivos enviados: [...]"
    'favor considerar', # "Favor considerar os valores abaixo..."
    'enviado o',        # "Enviado o DDR de 29/05 ajustado..."
    'enviados os',      # "Enviados os arquivos..."
    'enviadas as',      # "Enviadas as planilhas..."
    'sem movimenta',    # "Compromissada: sem movimentação" — extrato diário TRUSTEE DTVM
)

# Bloqueiam detecção de cortesia — Finaud está pedindo algo ao cliente
_FRASES_PEDIDO_EXPLICITO = (
    'solicitamos encaminhar',
    'solicitamos que encaminhe',
    'solicitamos que envie',
    'solicitamos enviar',   # Fix J: "Obrigado. Solicitamos enviar também o COS4016..."
    'orientamos que',       # Fix J: "Tudo bem? Orientamos que seja realizada uma conferência..."
    'verifique ',           # Fix J: "Certo, verifique com a contabilidade se..."
    'poderia encaminhar por gentileza',
    'pode encaminhar por gentileza',
    'por gentileza, encaminhe',
    'solicito ',        # forma singular: "solicito também os balanços", "solicito que envie"
    'vou precisar',    # "vou precisar dos COSIFs", "vou precisar que você"
    'no aguardo',      # Fix S: "No aguardo." = Finaud está aguardando resposta do cliente → AC
)

# Subconjunto de _FRASES_PEDIDO_EXPLICITO que indica pedido de documento — AC específico
_FRASES_SOLICITA_EXTRATO = (
    'solicitamos encaminhar',
    'solicitamos que encaminhe',
    'solicitamos que envie',
    'solicitamos enviar',
    'poderia encaminhar por gentileza',
    'pode encaminhar por gentileza',
    'por gentileza, encaminhe',
    'solicito ',
    'vou precisar',
    'no aguardo',
)

# Finaud instruiu o cliente a realizar um procedimento — aguarda execução
_FRASES_ORIENTACAO_TECNICA = (
    'orientamos que',
    'verifique ',
)

# Finaud propôs contato síncrono — aguarda confirmação do cliente
_FRASES_REUNIAO = (
    'reunião',
    'ligação',
    'videoconferência',
    'teams',
    'meet',
)

_SAUDACAO_RE = re.compile(
    r'^(prezad[ao]s?|bom\s+dia|boa\s+tarde|boa\s+noite|ol[aá]|caro|cara)\b',
    re.IGNORECASE,
)

# Fix I: cliente confirma que o BACEN aceitou o arquivo → processo encerrado
_ACEITACAO_BACEN = re.compile(
    r'(?:protocolo|arquivo)\s+(?:(?:de\s+arquivo|(?:j[aá]\s+)?foi)\s+)?aceito\b',
    re.IGNORECASE,
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
            # Só para se já há conteúdo real antes — separador no início do corpo
            # é cabeçalho automático do Outlook/Teams, não histórico citado.
            if any(l.strip() for l in resultado):
                break
            continue
        resultado.append(linha)
    return '\n'.join(resultado).strip()


# Marcadores que indicam início do aviso de confidencialidade corporativo.
# Texto a partir deste ponto é boilerplate jurídico — não deve influenciar classificação.
_INICIO_DISCLAIMER = re.compile(
    r'(?:'
    r'este\s+e[\-\s]?mail\s+(?:e\s+seus\s+anexos|inclusive\s+seus\s+anexos)'
    r'|this\s+e[\-\s]?mail\s+(?:and\s+its\s+attachments|including\s+any\s+attachments)'
    r'|se\s+voc[eê]\s+recebeu\s+este\s+e[\-\s]?mail\s+(?:equivocadamente|por\s+engano)'
    r'|if\s+you\s+(?:have\s+)?received\s+this\s+(?:e[\-\s]?mail|message)\s+in\s+error'
    r'|[eé]\s+expressamente\s+proibid'
    r'|strictly\s+prohibited'
    r')',
    re.IGNORECASE,
)


def _truncar_no_disclaimer(texto: str) -> str:
    """Remove aviso de confidencialidade do texto antes de classificar.
    Retorna o texto até o início do disclaimer; se não houver, retorna inteiro."""
    m = _INICIO_DISCLAIMER.search(texto)
    return texto[:m.start()].rstrip() if m else texto


def _tem_pergunta_acao(texto: str) -> bool:
    """§8.9: True se o texto tem pergunta real que exige ação do cliente.
    Remove URLs, cabeçalhos XML e saudações com '?' antes de checar."""
    t = re.sub(r'<https?://[^>]+>', '', texto)        # links <https://...>
    t = re.sub(r'https?://\S+', '', t)                # URLs soltas
    t = re.sub(r'^\s*<\?xml\b.*$', '', t, flags=re.MULTILINE)  # cabeçalho XML
    t = _SAUDACOES_PERGUNTA.sub('', t)                # "Tudo bem?", "Tudo bom?"
    return '?' in t


def _so_cortesia(texto: str) -> bool:
    """True se o texto novo contém apenas frases de cortesia, sem conteúdo substantivo.

    Remove o bloco de assinatura (nome/cargo/telefone/URLs após o sign-off) antes de avaliar,
    para não confundir rodapé de e-mail com conteúdo real da mensagem.
    """
    if not texto.strip():
        return True
    # U+200B (zero-width space) aparece em assinaturas HTML — remove antes dos checks
    texto = texto.replace('​', '')
    # Trunca a partir do sign-off ("Atenciosamente", "Att", etc.): tudo após é assinatura
    m = _SIGN_OFF_RE.search(texto)
    sign_off_encontrado = m is not None
    if m:
        texto = texto[:m.start()]
    # Fallback: bloco de 4+ linhas em branco seguidas = assinatura sem sign-off explícito.
    # Só aplica quando não há sign-off explícito — se há, o texto já foi cortado no
    # ponto certo e o fallback poderia remover conteúdo real antes do sign-off.
    if not sign_off_encontrado:
        texto = re.sub(r'(\r?\n){4,}[\s\S]*', '', texto)
    # Remove URLs residuais (podem conter '?' que não indica pergunta real)
    texto = re.sub(r'https?://\S+', '', texto)
    texto = re.sub(r'\[https?://[^\]]*\]', '', texto)
    # Remove referências de imagens inline (Outlook [cid:...] e Gmail [image: ...])
    texto = re.sub(r'\[cid:[^\]]+\]', '', texto)
    texto = re.sub(r'\[image:[^\]]*\]', '', texto)
    # Remove menções @Nome<mailto:email> do Outlook/Teams — não é conteúdo real
    texto = re.sub(r'@[^<\n]+<mailto:[^>]+>', '', texto, flags=re.IGNORECASE)
    # Remove "tudo bem?", "tudo bom?" — saudações sociais que não são perguntas reais
    texto = _SAUDACOES_PERGUNTA.sub('', texto)
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
    cc_campo      = (ultimo.get('cc')            or '')
    assunto       = (ultimo.get('assunto')       or '')
    corpo_raw     = (ultimo.get('corpo_texto')   or '')

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
    # Fix Q: To: vazio → verifica CC (encaminhamento interno via lista/grupo)
    _campo_para = destinatario if destinatario.strip() else cc_campo
    para_finaud = _todos_destinatarios_finaud(_campo_para)

    texto_novo  = _truncar_no_disclaimer(_extrair_texto_novo(corpo_raw))
    texto_lower = texto_novo.lower()
    # Versão sem quebras de linha internas — para frases de entrega que podem ser
    # quebradas pelo cliente de e-mail (ex.: "segue em\r\nanexo" → "segue em anexo")
    texto_flat  = re.sub(r'\s+', ' ', texto_lower)

    # §8.10: reação do Teams → cliente confirmou recebimento de mensagem da Finaud
    if _REACAO_TEAMS_RE.search(texto_novo):
        return 'Concluída', 'Cliente agradeceu — problema resolvido'

    # ── Helpers §8.6 — detecção de forward ───────────────────────────────────

    def _tem_arquivo_entregavel(anexos: list) -> bool:
        """True se tem pelo menos um arquivo que não é imagem inline (§8.6)."""
        for a in (anexos or []):
            ext = ('.' + a.rsplit('.', 1)[-1].lower()) if '.' in a else ''
            if ext not in _IMAGENS_INLINE:
                return True
        return False

    def _eh_forward_para_cliente(texto: str) -> bool:
        """§8.6: True se o corpo contém forward cujo De: é Finaud e Para: aponta para cliente externo."""
        # Formato A: separador com traços
        m = _FORWARD_SEP_RE.search(texto)
        if m:
            trecho = texto[m.end():]
            # Fix O: De: no forward deve ser Finaud (evita falso positivo quando cliente encaminha notif. do BC)
            md = re.search(r'(?:^|\n)[>\s]*(?:de|from)\s*:\s*(.+)', trecho[:400], re.IGNORECASE)
            if md:
                emails_de = re.findall(r'<([^>]+)>', md.group(1))
                if not emails_de:
                    emails_de = re.findall(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        md.group(1),
                    )
                de_eh_finaud = bool(emails_de) and all(_eh_finaud_addr(e) for e in emails_de)
            else:
                de_eh_finaud = False
            if de_eh_finaud:
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

    def _eh_cortesia_finaud(texto: str) -> bool:
        """True se o texto da Finaud é só cortesia — sem pedido de ação ao cliente."""
        if not texto.strip():
            return True
        texto = texto.replace('​', '')
        texto_norm_completo = re.sub(r'[\r\n]+', ' ', texto).lower()
        if any(f in texto_norm_completo for f in _FRASES_PEDIDO_EXPLICITO):
            return False
        m = _SIGN_OFF_RE.search(texto)
        texto_antes = texto[:m.start()].strip() if m else texto.strip()
        if not texto_antes:
            return True
        t = re.sub(r'<https?://[^>]+>', '', texto_antes).strip()
        t = re.sub(r'https?://\S+', '', t).strip()
        linhas = [l.strip() for l in t.splitlines() if l.strip()]
        linhas = [l for l in linhas if not _SAUDACAO_RE.match(l)]
        if not linhas:
            return True
        t_content = ' '.join(linhas).lower()
        _cortesia = (
            'obrigada', 'obrigado', 'ok', 'certo', 'entendido',
            'recebido', 'anotado', 'ótimo', 'perfeito', 'tudo bem', 'com prazer',
            'isso', 'exatamente', 'correto',
        )
        return any(t_content.startswith(f) or t_content == f for f in _cortesia)

    # Regra especial §8.3: confirmação de transmissão ao BACEN — independente de quem enviou
    # re.search com âncora de linha: "Transmitido" pode vir após saudação ("Boa tarde!\n\nTransmitido...")
    _inicio_transmitido = bool(re.search(r'(?:^|\r?\n)\s*transmitid[oa]s?\b', texto_lower))
    _arquivos_transmitidos = bool(re.search(r'\barquivo[s]?\s+transmitid[oa]s?\b', texto_lower))
    _termos_bacen = _termos_db('Confirmação de entrega no BACEN')
    if ('transmitido no bacen' in texto_lower
            or 'transmitida no bacen' in texto_lower
            or (_inicio_transmitido and '?' not in texto_lower)
            or (_arquivos_transmitidos and '?' not in texto_lower)
            or any(t in texto_lower for t in _termos_bacen)):
        return 'Concluída', 'Confirmação de entrega no BACEN'

    if eh_finaud:
        # Finaud → Finaud: verificar se é forward de entrega ao cliente (§8.6 Cenário 1)
        if para_finaud:
            if _eh_forward_para_cliente(corpo_raw):
                # Sub-caso 1a: tem arquivo real → Concluída
                if _tem_arquivo_entregavel(ultimo.get('nomes_anexos') or []):
                    return 'Concluída', 'Finaud entregou arquivo ao cliente'
                # Sub-caso 1b: verificar sinal de conclusão
                if assunto.strip().upper().startswith('RES:'):
                    return 'Concluída', 'Finaud concluiu a solicitação'
                _fc = _FRASES_CONCLUSIVAS_FINAUD + _termos_db('Finaud concluiu a solicitação')
                if any(f in texto_flat for f in _fc):
                    return 'Concluída', 'Finaud concluiu a solicitação'
                # Fix N: texto_novo vazio = conteúdo dentro do forward; checar corpo completo
                if not texto_novo.strip():
                    corpo_flat_fwd = re.sub(r'\s+', ' ', corpo_raw).lower()
                    if any(f in corpo_flat_fwd for f in _fc):
                        return 'Concluída', 'Finaud concluiu a solicitação'
                # 1b-padrão: sem sinal claro → Aguardando Cliente (erro mais seguro)
                return 'Aguardando Cliente', 'Finaud fez pergunta — aguarda resposta'
            # E-mail interno genuíno (Cenário 3)
            # §8.7: assunto informativo → sem ação pendente (strip RES:/ENC: antes)
            assunto_lower = re.sub(r'^(res|enc|fwd|fw)\s*:\s*', '', assunto.strip(), flags=re.IGNORECASE).lower()
            if any(assunto_lower.startswith(p) for p in _ASSUNTOS_INFORMATIVOS):
                return 'Concluída', 'Finaud concluiu a solicitação'
            return 'Aguardando Finaud', 'E-mail interno — aguarda ação da Finaud'
        # Finaud → Cliente
        tem_arquivo_real = _tem_arquivo_entregavel(ultimo.get('nomes_anexos') or [])
        if tem_arquivo_real:
            if _tem_pergunta_acao(texto_novo):
                return 'Aguardando Cliente', 'Finaud enviou arquivo — aguarda retorno do cliente'
            if any(f in texto_flat for f in _FRASES_ENTREGA + _termos_db('Finaud entregou arquivo ao cliente')):
                return 'Concluída', 'Finaud entregou arquivo ao cliente'
            if any(f in texto_lower for f in _FRASES_AGUARDANDO_FINAUD_ATIVA + _termos_db('Finaud prometeu retornar')):
                return 'Aguardando Finaud', 'Finaud prometeu retornar'
            if not texto_novo.strip():
                return 'Concluída', 'Finaud entregou arquivo ao cliente'
            return 'Aguardando Cliente', 'Finaud enviou arquivo — aguarda retorno do cliente'
        # Sem arquivo real
        if assunto.strip().upper().startswith('RES:'):
            return 'Concluída', 'Finaud concluiu a solicitação'
        if any(f in texto_flat for f in _FRASES_CONCLUSIVAS_FINAUD + _termos_db('Finaud concluiu a solicitação')):
            return 'Concluída', 'Finaud concluiu a solicitação'
        if any(f in texto_lower for f in _FRASES_AGUARDANDO_FINAUD_ATIVA + _termos_db('Finaud prometeu retornar')):
            return 'Aguardando Finaud', 'Finaud prometeu retornar'
        if any(f in texto_flat for f in _FRASES_SOLICITA_EXTRATO):
            return 'Aguardando Cliente', 'Finaud fez pergunta — aguarda resposta'
        if any(f in texto_lower for f in _FRASES_ORIENTACAO_TECNICA):
            return 'Aguardando Cliente', 'Finaud fez pergunta — aguarda resposta'
        if any(f in texto_lower for f in _FRASES_REUNIAO):
            return 'Aguardando Cliente', 'Finaud fez pergunta — aguarda resposta'
        if _eh_cortesia_finaud(texto_novo):
            if len(msgs) == 1:
                return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
            if len(msgs) >= 2:
                ant = msgs[-2]
                rem_ant = (ant.get('remetente') or '').lower()
                anexos_ant = ant.get('nomes_anexos') or []
                if not _eh_finaud_addr(rem_ant) and _tem_arquivo_entregavel(anexos_ant):
                    return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
            return 'Concluída', 'Finaud concluiu a solicitação'
        if len(msgs) >= 2 and para_finaud and all(_eh_finaud_addr((m.get('remetente') or '').lower()) for m in msgs):
            return 'Aguardando Finaud', 'E-mail interno — aguarda ação da Finaud'
        return 'Aguardando Cliente', 'Finaud fez pergunta — aguarda resposta'

    # Remetente externo (cliente)
    # §8.8-BACEN: ENC: BANCO CENTRAL + [undefined] na assinatura (logo BANVOX sem sign-off)
    # _so_cortesia() falha porque o bloco de contato é longo; detecção direta pelo assunto+logo.
    if (_ENC_PREFIX.match(assunto.strip())
            and 'BANCO CENTRAL' in assunto.upper()
            and '[undefined]' in texto_lower):
        return 'Aguardando Finaud', 'BANVOX encaminhou alerta do BACEN sobre documento — aguarda análise da Finaud'
    # §8.8-PCAM: Fair Corretora encaminha relatório PCAM diário (ENC: PCAM DD.MM.YYYY)
    # _so_cortesia() falha: bloco de contato sem "Atenciosamente". Conteúdo real está no histórico.
    if _ENC_PREFIX.match(assunto.strip()) and 'PCAM' in assunto.upper():
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    # §8.8-ENC-ARQUIVO: forward (ENC:/FWD:) com arquivo não-imagem = entrega de dados
    # Cobre casos onde _so_cortesia() falha por assinatura corporativa com ícones/logos
    # Ex.: FREEX Câmbio envia balancete zip com assinatura que inclui [Logo Freex] etc. (01/09/2026)
    if (_ENC_PREFIX.match(assunto.strip())
            and _tem_arquivo_entregavel(ultimo.get('nomes_anexos') or [])):
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    # §8.8: cliente encaminhou algo (ENC:/FWD: ou assunto com EXTRATO) com texto vazio → Finaud precisa processar
    if _so_cortesia(texto_novo) and (_ENC_PREFIX.match(assunto.strip()) or _EXTRATO_RE.search(assunto)):
        if 'BANCO CENTRAL' in assunto.upper():
            return 'Aguardando Finaud', 'BANVOX encaminhou alerta do BACEN sobre documento — aguarda análise da Finaud'
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    # Fix I: cliente informa que o BACEN aceitou o arquivo → processo encerrado
    # Roda ANTES de §8.8b para não ser bloqueado por "Segue" no início da frase.
    # Ex.: "Segue protocolo de arquivo aceito do COS4111" — aceite do BACEN encerra o caso.
    _texto_sem_url_fi = re.sub(r'<https?://[^>]+>|https?://\S+', '', texto_novo)
    if (_ACEITACAO_BACEN.search(texto_lower)
            and '?' not in _texto_sem_url_fi):
        return 'Concluída', 'Confirmação de entrega no BACEN'
    # §8.8b: "Segue/Seguem/Enviado/Anexo/Arquivo(s) enviado(s)/reenviado(s)" no início de linha
    if re.search(r'(?:^|\r?\n)\s*(?:seguem?|enviados?|arquivos?\s+(?:re)?enviados?|anexo)\b', texto_lower):
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    # §8.8b.1: "segue" mid-frase, "em/anexo" entrega, ou relatório de status (aprovado 01/09/2026)
    _SEGUE_MID = (
        'segue a planilha', 'segue balancete', 'segue a base',
        'houve compromissada', 'houveram compromissada',  # Planner SCD: "não houve compromissada no dia"
        'sem movimenta',      # TRUSTEE DTVM: "Compromissada: sem movimentação / LFT: sem movimentação"
        'em anexo',       # "Em anexo arquivo solicitado" / "extratos em anexo"
        'anexo posições', # Western Union: relatório diário de posição de câmbio
        'anexo extratos', # BANVOX DTVM: extrato compromissada/custódia
        'anexo arquivo',  # entregas variadas: "Anexo arquivo DRL", "Anexo arquivo solicitado"
        'acabei de envi', # Planner: "Acabei de envia a documentação suporte do dia X" (01/09/2026)
        'pode seguir',    # Planner SCD: "pode seguir pois naqueles dias não tiveram" (01/09/2026)
        'apenas confirmando', # DTVM: "Apenas confirmando, o aumento de capital foi integralizado" (01/09/2026)
        'fyi',            # Western Union: "FYI" (forward interno, entrega de informação) (01/09/2026)
    ) + _termos_db('Cliente enviou informações e extratos — aguarda processamento')
    if any(f in texto_lower for f in _SEGUE_MID):
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    # §8.8b.2: arquivo não-imagem + "segue" no texto + sem "?" = entrega de dados mid-frase
    # Cobre "Prezados, segue o COS4010 para emissão do DRM" (Amaril Franklin, 01/09/2026).
    # Requer attachment real para não confundir com "segue o link de credencial + pergunta".
    if (_tem_arquivo_entregavel(ultimo.get('nomes_anexos') or [])
            and re.search(r'\bseguem?\b', texto_lower)
            and '?' not in texto_novo):
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    # §8.8c: saudação pura (sem palavra de confirmação) = provavelmente entrega de arquivo
    # "Boa Tarde + Att" ≠ confirmação; "Muito obrigado" = confirmação explícita
    if _so_cortesia(texto_novo) and _CONFIRMACAO_EXPLICITA.search(texto_lower):
        return 'Concluída', 'Cliente agradeceu — problema resolvido'
    if _so_cortesia(texto_novo):
        return 'Aguardando Finaud', 'Mensagem do cliente sem conteúdo para classificar — aguarda verificação'
    # Fix F: confirmação curta + assinatura corporativa sem sign-off explícito
    # Ex.: "De acordo\r\n\r\nEduardo Galasini\r\nFinance\r\nActivTrades CCTVM..."
    _primeiro_para = re.split(r'\r?\n\s*\r?\n', texto_novo)[0].strip()
    if ('?' not in texto_novo
            and _so_cortesia(_primeiro_para)
            and _CONFIRMACAO_EXPLICITA.search(_primeiro_para.lower())):
        return 'Concluída', 'Cliente agradeceu — problema resolvido'
    # Fix G: cliente agradece e compromete-se a agir por conta própria sem pedir nada à Finaud
    # Ex.: "Muito obrigado, realizaremos o procedimento e enviaremos a alteração do report ao BCB."
    _ACAO_PROPRIA = re.compile(
        r'\b(realizaremos|efetuaremos|enviaremos|encaminharemos|faremos|providenciaremos|'
        r'transmitiremos|corrigiremos|ajustaremos|reenviaremos)\b',
        re.IGNORECASE,
    )
    if ('?' not in texto_novo
            and _CONFIRMACAO_EXPLICITA.search(texto_lower)
            and _ACAO_PROPRIA.search(texto_lower)):
        return 'Concluída', 'Cliente agradeceu — problema resolvido'
    # Fix R: cliente prometeu retornar — ação pendente do cliente, não da Finaud
    # Ex.: "Vamos analisar e retornamos." / "Obrigada, retornarei amanhã."
    _CLIENTE_VAI_RETORNAR = re.compile(
        r'\bretornaremos\b|\bretornamos\b|\bretornarei\b|\bvamos\s+analisar\b'
        r'|\be\s+retorno\b'    # Fix V: "vou confirmar e retorno" — cliente prometeu voltar → AC
        r'|\bentrarei\s+em\s+contato\b',  # Sefer: "entrarei em contato para te informar" (01/09/2026)
        re.IGNORECASE,
    )
    if _CLIENTE_VAI_RETORNAR.search(texto_lower):
        return 'Aguardando Cliente', 'Cliente prometeu retornar com informações — aguarda retorno'
    # Fix H: cliente agradece sem pergunta e sem entrega de documento → Concluída
    # Regra aprovada por Michel em 21/08/2026: "se não houver perguntas, observações e
    # documento é concluída". Mais amplo que Fix G — não exige verbo de ação específico.
    # Ex.: "Muito obrigado, vou fazer de acordo." / "Obrigada pelo retorno."
    # §8.8b já bloqueou "Segue" no início de linha. Verificamos "segue/anexo" em qualquer
    # posição para cobrir "Obrigado, segue o arquivo." (entrega de doc, permanece AF).
    # Guarda adicional: palavras de pedido implícito sem "?" ("precisamos da planilha")
    # indicam que o cliente ainda espera algo da Finaud — permanece AF.
    _ENTREGA_DOC_CLI = re.compile(
        r'\bseguem?\b|\banexo\b|\bencaminho\b|\bencaminhamos\b|\bestou\s+enviando\b',
        re.IGNORECASE,
    )
    _PEDIDO_IMPLICITO = re.compile(
        r'\bprecis[ao]mos?\b|\bnecessit[ao]mos?\b|\bgostar[íi]amos?\b|\bprecisaria\b'
        r'|\bpreciso\b'    # "preciso desse arquivo" / "Preciso dessas planilhas" (01/09/2026)
        r'|\bpe[çc]o\s'    # Fix T: "Peço que inclua..." — pedido educado do cliente → AF
        r'|\bfavor\b'      # Fix U: "Favor considerar/enviar/verificar..." — pedido ao Finaud → AF
        r'|\bgentileza\b'  # "Gentileza enviar arquivo" / "Por gentileza enviar..." → AF
        r'|\bpoderia[m]?\b'   # "Poderia nos ajudar enviando..." → AF
        r'|\bpode\s+enviar\b',  # Planner SCD: "Pode enviar a SCD do jeito que está" = pedido (01/09/2026)
        re.IGNORECASE,
    )
    # Padrões de cobrança/follow-up: sempre são solicitações mesmo quando terminam com "?"
    # (diferente de _PEDIDO_IMPLICITO, que exige ausência de "?" para evitar dúvidas retóricas)
    _PEDIDO_FOLLOW_UP = re.compile(
        r'\balgu[mn]\s+retorno\b'          # "Algum retorno quanto a este caso?" (01/09/2026)
        r'|\bconsegui(?:u|ram)\b'          # "Conseguiu/Conseguiram verificar?" — cobrança (01/09/2026)
        r'|\bpor\s+favor\b'                # "Por favor seria contigo estes ajustes?" (01/09/2026)
        r'|\bfoi\s+poss[íi]vel\b'          # "Foi possível realizar as substituições?" (01/09/2026)
        r'|\breuni[aã]o\s+do\s+microsoft\s+teams\b'   # convite Teams = pedido de reunião (01/09/2026)
        r'|\bpe[çc]o\b'                               # Banvox: "peço que solicite ao Robson" + "?" (01/09/2026)
        r'|\bfavor\b'                                 # CV DTVM: "Favor solucionar com prioridade" + "?" (01/09/2026)
        r'|\bgentileza\b'                             # UNVERIFIED: "Por gentileza, poderia retornar?" (01/09/2026)
        r'|\bseria\s+poss[íi]vel\b'                  # Acesso negado: "seria possível desbloquear?" (01/09/2026)
        r'|\batualiza[çc](?:[aã]o|[oõ]es)\b'           # Fair/Unicred: "Alguma atualização?" / "temos atualizações?" (01/09/2026)
        r'|\bpode\s+(?:confirmar|verificar)\b'        # Coluna/Trinus: "Pode confirmar?" / "pode verificar?" (01/09/2026)
        r'|\bme\s+atualizar\b'                        # Trustee: "Agradeço se puder me atualizar do status" (01/09/2026)
        r'|\brefor[çc]ar\b'                           # Unicred DRL: "reforçar que o prazo de envio é hoje" (01/09/2026)
        r'|\bem\s+atraso\b'                           # Accredito: "estamos em atraso com as informações" (01/09/2026)
        r'|\bconsegue\s+me\s+confirmar\b',            # Intercam/IN BCB 757: "Consegue me confirmar se aplica?" (01/09/2026)
        re.IGNORECASE,
    )
    # Remove URLs e "??" (duplo ponto de interrogação informal/emoji) antes de checar
    # perguntas reais. "??" é ênfase informal ("Obrigado pelo aviso ??") — não é pergunta.
    # Mantém "?" simples: "Tudo bem?" e perguntas reais continuam bloqueando Fix H.
    _texto_sem_url_q = re.sub(r'<https?://[^>]+>|https?://\S+', '', texto_novo)
    _texto_sem_url_q = re.sub(r'\?\?+', '', _texto_sem_url_q)
    if ('?' not in _texto_sem_url_q
            and _CONFIRMACAO_EXPLICITA.search(texto_lower)
            and not _ENTREGA_DOC_CLI.search(texto_lower)
            and not _PEDIDO_IMPLICITO.search(texto_lower)):
        return 'Concluída', 'Cliente agradeceu — problema resolvido'
    if '?' not in _texto_sem_url_q and _PEDIDO_IMPLICITO.search(texto_lower):
        return 'Aguardando Finaud', 'Cliente fez solicitação — aguarda ação da Finaud'
    if _PEDIDO_FOLLOW_UP.search(texto_lower):
        return 'Aguardando Finaud', 'Cliente fez solicitação — aguarda ação da Finaud'
    # §8.8-DDR: último recurso para entrega de DDR com assinatura extensa (ex: Wise)
    # _so_cortesia() falha quando bloco de contato tem nome/cargo/empresa sem sign-off.
    # Só dispara após todas as outras regras falharem: DDR no assunto + sem "?" (URL-stripped).
    if (re.search(r'\bDDR\b', assunto, re.IGNORECASE)
            and '?' not in _texto_sem_url_q):
        return 'Aguardando Finaud', 'Cliente enviou informações e extratos — aguarda processamento'
    return 'Aguardando Finaud', 'Cliente fez pergunta — aguarda resposta da Finaud'


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
    para todas as threads ativas do destino 'principal'.
    Threads com inativa_desde preenchido são reativadas automaticamente
    se chegou nova mensagem após o arquivamento; as demais são ignoradas.
    Retorna o número de threads atualizadas.
    """
    with _conectar() as conn:
        # Reativa threads cujo inativa_desde é anterior à última mensagem.
        # data_ultima_msg é 'DD/MM/YYYY HH:MM'; inativa_desde é ISO — converte para comparar.
        conn.execute("""
            UPDATE threads
            SET inativa_desde = NULL
            WHERE inativa_desde IS NOT NULL
              AND (
                substr(data_ultima_msg,7,4)||'-'||substr(data_ultima_msg,4,2)||'-'
                ||substr(data_ultima_msg,1,2)||' '||substr(data_ultima_msg,12,5)
              ) > inativa_desde
        """)
        rows = conn.execute(
            "SELECT thread_id, mensagens_json FROM threads WHERE destino = 'principal' AND inativa_desde IS NULL"
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


def arquivar_threads_inativas(dias_af: int = 30, dias_ac: int = 60) -> dict:
    """
    Carimba inativa_desde nas threads sem resposta há mais dias que o limite.
    - Threads em status 'Aguardando Finaud': arquiva após `dias_af` dias.
    - Threads em status 'Aguardando Cliente': arquiva após `dias_ac` dias.
    Threads já arquivadas (inativa_desde IS NOT NULL) são ignoradas.
    Retorna {'af': N, 'ac': M} com a quantidade arquivada em cada grupo.

    data_ultima_msg é armazenada em formato 'DD/MM/YYYY HH:MM'; a conversão
    para ISO é feita via substr() para compatibilidade com julianday() do SQLite.
    """
    # Converte 'DD/MM/YYYY HH:MM' → 'YYYY-MM-DD HH:MM' para julianday()
    _iso = (
        "substr(data_ultima_msg,7,4)||'-'||substr(data_ultima_msg,4,2)||'-'"
        "||substr(data_ultima_msg,1,2)||' '||substr(data_ultima_msg,12,5)"
    )
    agora = _agora()
    with _conectar() as conn:
        af = conn.execute(f"""
            UPDATE threads
            SET    inativa_desde = ?
            WHERE  destino = 'principal'
              AND  inativa_desde IS NULL
              AND  status_workflow = 'Aguardando Finaud'
              AND  julianday('now') - julianday({_iso}) >= ?
        """, (agora, dias_af)).rowcount
        ac = conn.execute(f"""
            UPDATE threads
            SET    inativa_desde = ?
            WHERE  destino = 'principal'
              AND  inativa_desde IS NULL
              AND  status_workflow = 'Aguardando Cliente'
              AND  julianday('now') - julianday({_iso}) >= ?
        """, (agora, dias_ac)).rowcount
    return {'af': af, 'ac': ac}


# ── Consultas ──────────────────────────────────────────────────────────────────

def buscar_sem_classificar(apenas_nao_vistas: bool = False) -> list[dict]:
    """Retorna threads que o classificador ainda não processou."""
    filtro = " AND visto_em IS NULL" if apenas_nao_vistas else ""
    with _conectar() as conn:
        rows = conn.execute(
            f"SELECT * FROM threads WHERE destino IS NULL{filtro} ORDER BY data_ultima_msg DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def buscar_por_destino(destino: str, apenas_nao_vistas: bool = False) -> list[dict]:
    """
    Retorna threads de um destino específico para as telas.
    Threads arquivadas (inativa_desde IS NOT NULL) são excluídas — use
    buscar_threads_sem_retorno() para acessá-las.
    Não inclui mensagens_json (pesado) — use buscar_thread_completa para detalhes.
    """
    filtro = " AND visto_em IS NULL" if apenas_nao_vistas else ""
    with _conectar() as conn:
        rows = conn.execute(f"""
            SELECT thread_id, assunto, qtd_mensagens, data_primeira_msg,
                   data_ultima_msg, remetente_principal, destinatario_principal,
                   remetente_ultima_msg, destinatario_ultima_msg, reply_to_ultima_msg,
                   destino, categoria, status_workflow, motivo_status,
                   motivo_descarte, motivo_classificacao
            FROM   threads
            WHERE  destino = ? AND inativa_desde IS NULL{filtro}
            ORDER  BY data_ultima_msg DESC
        """, (destino,)).fetchall()
    return [dict(r) for r in rows]


def buscar_threads_sem_retorno() -> list[dict]:
    """
    Retorna threads arquivadas (inativa_desde IS NOT NULL) para o modal SEM RETORNO.
    Inclui inativa_desde para calcular há quantos dias está arquivada.
    """
    with _conectar() as conn:
        rows = conn.execute("""
            SELECT thread_id, assunto, qtd_mensagens, data_primeira_msg,
                   data_ultima_msg, remetente_principal, destinatario_principal,
                   remetente_ultima_msg, destinatario_ultima_msg, reply_to_ultima_msg,
                   destino, categoria, status_workflow, motivo_status,
                   motivo_descarte, motivo_classificacao, inativa_desde
            FROM   threads
            WHERE  destino = 'principal' AND inativa_desde IS NOT NULL
            ORDER  BY inativa_desde DESC
        """).fetchall()
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


def contar_nao_vistas() -> dict:
    """Retorna contagens de threads não vistas para os badges da sidebar."""
    with _conectar() as conn:
        nao_class = conn.execute(
            "SELECT COUNT(*) FROM threads WHERE (destino = 'revisao' OR destino IS NULL) AND visto_em IS NULL"
        ).fetchone()[0]
        bloqueados = conn.execute(
            "SELECT COUNT(*) FROM threads WHERE destino = 'descartes' AND visto_em IS NULL"
        ).fetchone()[0]
    return {'nao_class': nao_class, 'bloqueados': bloqueados}


def marcar_vistas(grupo: str) -> None:
    """Marca todas as threads de um grupo como vistas.
    grupo: 'bloqueados' ou 'nao_class'
    """
    with _conectar() as conn:
        if grupo == 'bloqueados':
            conn.execute(
                "UPDATE threads SET visto_em = ? WHERE destino = 'descartes' AND visto_em IS NULL",
                (_agora(),)
            )
        elif grupo == 'nao_class':
            conn.execute(
                "UPDATE threads SET visto_em = ? WHERE (destino = 'revisao' OR destino IS NULL) AND visto_em IS NULL",
                (_agora(),)
            )


# ── Snapshots de contadores por categoria ────────────────────────────────────

def salvar_snapshot() -> None:
    """Grava o estado atual dos contadores por categoria — chamado pelo coletor antes de cada rodada.
    Threads arquivadas (inativa_desde IS NOT NULL) são excluídas das contagens por categoria
    e agrupadas separadamente sob a categoria SEM RETORNO."""
    agora = _agora()
    with _conectar() as conn:
        rows_ativas = conn.execute("""
            SELECT COALESCE(categoria, 'DESCONHECIDA') AS categoria,
                   status_workflow, COUNT(*) AS cnt
            FROM   threads
            WHERE  destino = 'principal' AND inativa_desde IS NULL
            GROUP  BY categoria, status_workflow
        """).fetchall()
        rows_sr = conn.execute("""
            SELECT status_workflow, COUNT(*) AS cnt
            FROM   threads
            WHERE  destino = 'principal' AND inativa_desde IS NOT NULL
            GROUP  BY status_workflow
        """).fetchall()

    contagens: dict[str, dict] = {}
    for r in rows_ativas:
        cat = r['categoria']
        if cat not in contagens:
            contagens[cat] = {'af': 0, 'ac': 0, 'co': 0}
        sw = r['status_workflow'] or ''
        if sw == 'Aguardando Finaud':
            contagens[cat]['af'] += r['cnt']
        elif sw == 'Aguardando Cliente':
            contagens[cat]['ac'] += r['cnt']
        elif sw == 'Concluída':
            contagens[cat]['co'] += r['cnt']

    sr = {'af': 0, 'ac': 0}
    for r in rows_sr:
        sw = r['status_workflow'] or ''
        if sw == 'Aguardando Finaud':
            sr['af'] += r['cnt']
        elif sw == 'Aguardando Cliente':
            sr['ac'] += r['cnt']

    snapshot_rows = [
        (agora, cat, c['af'], c['ac'], c['co'], c['af'] + c['ac'] + c['co'])
        for cat, c in contagens.items()
    ]
    if sr['af'] + sr['ac'] > 0:
        snapshot_rows.append((agora, 'SEM RETORNO', sr['af'], sr['ac'], 0, sr['af'] + sr['ac']))

    with _conectar() as conn:
        conn.executemany(
            'INSERT INTO snapshots (data_hora, categoria, af, ac, co, total) VALUES (?,?,?,?,?,?)',
            snapshot_rows,
        )


def ler_ultimo_snapshot() -> dict[str, dict]:
    """Retorna o último snapshot salvo como {categoria_id: {af, ac, co, total}}. Vazio se não houver snapshot."""
    with _conectar() as conn:
        rows = conn.execute(
            'SELECT categoria, af, ac, co, total FROM snapshots '
            'WHERE data_hora = (SELECT MAX(data_hora) FROM snapshots)'
        ).fetchall()
    return {r['categoria']: dict(r) for r in rows}


def ler_penultimo_snapshot() -> dict[str, dict]:
    """Retorna o penúltimo snapshot (rodada anterior à última) para calcular o delta exibido na tabela principal.
    Com snapshots salvos no FIM de cada rodada, penúltimo = estado antes da última rodada = variação real."""
    with _conectar() as conn:
        row = conn.execute(
            'SELECT DISTINCT data_hora FROM snapshots ORDER BY data_hora DESC LIMIT 1 OFFSET 1'
        ).fetchone()
        if not row:
            return {}
        rows = conn.execute(
            'SELECT categoria, af, ac, co, total FROM snapshots WHERE data_hora = ?',
            (row['data_hora'],)
        ).fetchall()
    return {r['categoria']: dict(r) for r in rows}


def ler_snapshot_de_ontem() -> dict[str, dict]:
    """Retorna o último snapshot salvo antes de hoje — base para calcular a variação diária na tela principal."""
    hoje = datetime.now().strftime('%Y-%m-%d')
    with _conectar() as conn:
        row = conn.execute(
            "SELECT DISTINCT data_hora FROM snapshots WHERE date(data_hora) < ? ORDER BY data_hora DESC LIMIT 1",
            (hoje,)
        ).fetchone()
        if not row:
            return {}
        rows = conn.execute(
            'SELECT categoria, af, ac, co, total FROM snapshots WHERE data_hora = ?',
            (row['data_hora'],)
        ).fetchall()
    return {r['categoria']: dict(r) for r in rows}


# ── Log de execuções do coletor ───────────────────────────────────────────────

def registrar_coleta(tipo: str, threads_proc: int, erros: int,
                     duracao_seg: float, status: str, mensagem: str = '') -> int:
    """Grava o resultado de uma rodada do coletor. Retorna o id do registro criado."""
    with _conectar() as conn:
        cur = conn.execute(
            """INSERT INTO log_coletas
               (data_hora, tipo, threads_proc, erros, duracao_seg, status, mensagem)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (_agora(), tipo, threads_proc, erros, round(duracao_seg, 1), status, mensagem)
        )
        return cur.lastrowid


def atualizar_classif_coleta(log_id: int, principal: int,
                             descartes: int, revisao: int) -> None:
    """Adiciona o resultado da classificação a um registro de coleta já gravado."""
    with _conectar() as conn:
        conn.execute(
            """UPDATE log_coletas
               SET classif_principal=?, classif_descartes=?, classif_revisao=?
               WHERE id=?""",
            (principal, descartes, revisao, log_id)
        )


def ler_log_coletas(limite: int = 30) -> list[dict]:
    """Retorna as últimas N rodadas do coletor, mais recente primeiro."""
    with _conectar() as conn:
        rows = conn.execute(
            """SELECT id, data_hora, tipo, threads_proc, erros, duracao_seg, status,
                      mensagem, classif_principal, classif_descartes, classif_revisao
               FROM log_coletas ORDER BY id DESC LIMIT ?""",
            (limite,)
        ).fetchall()
    return [dict(r) for r in rows]


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
