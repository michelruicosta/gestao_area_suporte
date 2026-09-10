"""
testar_status_ia.py
O que faz: compara o status calculado pelo sistema com o que o GPT-4o atribuiria,
           para medir quantos erros reais existem e confirmar se a IA é mais
           confiável que o sistema de regras atual.

Uso:
    set OPENAI_API_KEY=sk-...
    python scripts/testar_status_ia.py [--fase 1|2|3] [--limite N]

Fases:
    1 (padrão) — ~103 threads suspeitas (AF com Finaud último + Concluída com ? do cliente)
    2          — 100 aleatórias por status (AF / AC / Concluída)
    3          — todas as threads do banco (~1.625)

Resultado: data/teste_status_ia/YYYYMMDD_faseN_resultados.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import openai

BASE_DIR  = Path(__file__).parent.parent
BANCO     = BASE_DIR / 'data' / 'gestao.db'
SAIDA_DIR = BASE_DIR / 'data' / 'teste_status_ia'

MODELO     = 'gpt-4o'
TEMPERATURA = 0

_PROMPT_SISTEMA = """\
Você analisa e-mails de suporte de uma empresa de gestão de riscos financeiros chamada Finaud.
A Finaud ajuda fundos de investimento a enviar relatórios regulatórios ao Banco Central do Brasil.

Sua tarefa: ler a última mensagem de uma conversa por e-mail e dizer qual é o status correto.

Os três status possíveis:
- "Aguardando Finaud": o cliente enviou algo e está aguardando resposta ou ação da Finaud
- "Aguardando Cliente": a Finaud enviou algo e está aguardando resposta, arquivo ou confirmação do cliente
- "Concluída": a conversa foi encerrada sem pendências (cliente agradeceu/confirmou, ou Finaud fez entrega final sem pedir nada)

Responda APENAS com JSON válido, sem texto extra:
{"status": "<um dos três acima>", "motivo": "<frase curta em português explicando por quê>"}"""


# ── Banco ─────────────────────────────────────────────────────────────────────

def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
    return conn


# ── Detecção de remetente ──────────────────────────────────────────────────────

def _eh_finaud(remetente: str, reply_to: str) -> bool:
    """True se o remetente é Finaud e não é cliente enviando via suporte@."""
    rem = remetente.lower()
    rto = (reply_to or '').lower()
    eh_finaud_raw = '@finaud.com.br' in rem or '@finaudtec.com.br' in rem
    via_suporte = (
        eh_finaud_raw and rto
        and '@finaud' not in rto
        and '@finaudtec' not in rto
    )
    return eh_finaud_raw and not via_suporte


# ── Extração de texto limpo ────────────────────────────────────────────────────

_SEP_RE = re.compile(
    r'^(-{3,}|_{3,}|\*?from:\*?|\*?de:\*?'
    r'|on\s.{3,200}wrote:|em\s.{3,200}escreveu:)',
    re.IGNORECASE | re.MULTILINE,
)
_FWD_RE = re.compile(
    r'-{5,}\s*(?:forwarded\s+message|mensagem\s+encaminhada)',
    re.IGNORECASE,
)

def _texto_limpo(corpo: str, max_chars: int = 1_200) -> str:
    """Remove histórico citado e retorna só o texto novo."""
    if not corpo:
        return ''
    m_fwd = _FWD_RE.search(corpo)
    if m_fwd:
        corpo = corpo[:m_fwd.start()]
    linhas = corpo.splitlines()
    resultado = []
    for linha in linhas:
        if _SEP_RE.match(linha.strip()):
            break
        resultado.append(linha)
    return '\n'.join(resultado).strip()[:max_chars]


# ── Seleção de threads por fase ───────────────────────────────────────────────

def _threads_fase1(conn: sqlite3.Connection) -> list[dict]:
    """Grupo A (AF com Finaud último) + Grupo B (Concluída com ? do cliente)."""
    threads = []

    # Grupo A
    for row in conn.execute(
        "SELECT thread_id, assunto, status_workflow, motivo_status, mensagens_json "
        "FROM threads WHERE destino='principal' AND status_workflow='Aguardando Finaud'"
    ):
        msgs = json.loads(row['mensagens_json'])
        if not msgs:
            continue
        u = msgs[-1]
        if _eh_finaud(u.get('remetente', ''), u.get('reply_to', '')):
            threads.append({
                'thread_id':   row['thread_id'],
                'assunto':     row['assunto'],
                'status_atual': row['status_workflow'],
                'motivo_atual': row['motivo_status'],
                'grupo':       'A_af_finaud_ultimo',
                'ultima_msg':  u,
            })

    # Grupo B
    for row in conn.execute(
        "SELECT thread_id, assunto, status_workflow, motivo_status, mensagens_json "
        "FROM threads WHERE destino='principal' AND status_workflow='Concluída'"
    ):
        msgs = json.loads(row['mensagens_json'])
        if not msgs:
            continue
        u = msgs[-1]
        if not _eh_finaud(u.get('remetente', ''), u.get('reply_to', '')):
            if '?' in (u.get('corpo_texto') or ''):
                threads.append({
                    'thread_id':   row['thread_id'],
                    'assunto':     row['assunto'],
                    'status_atual': row['status_workflow'],
                    'motivo_atual': row['motivo_status'],
                    'grupo':       'B_concluida_cliente_pergunta',
                    'ultima_msg':  u,
                })
    return threads


def _threads_fase2(conn: sqlite3.Connection, n_por_status: int = 100) -> list[dict]:
    """100 aleatórias por status (AF / AC / Concluída)."""
    threads = []
    for status in ('Aguardando Finaud', 'Aguardando Cliente', 'Concluída'):
        rows = conn.execute(
            "SELECT thread_id, assunto, status_workflow, motivo_status, mensagens_json "
            "FROM threads WHERE destino='principal' AND status_workflow=?", (status,)
        ).fetchall()
        amostra = random.sample(rows, min(n_por_status, len(rows)))
        for row in amostra:
            msgs = json.loads(row['mensagens_json'])
            if not msgs:
                continue
            threads.append({
                'thread_id':   row['thread_id'],
                'assunto':     row['assunto'],
                'status_atual': row['status_workflow'],
                'motivo_atual': row['motivo_status'],
                'grupo':       f'amostra_{status.lower().replace(" ","_")}',
                'ultima_msg':  msgs[-1],
            })
    return threads


def _threads_fase3(conn: sqlite3.Connection) -> list[dict]:
    """Todas as threads do banco."""
    threads = []
    for row in conn.execute(
        "SELECT thread_id, assunto, status_workflow, motivo_status, mensagens_json "
        "FROM threads WHERE destino='principal'"
    ):
        msgs = json.loads(row['mensagens_json'])
        if not msgs:
            continue
        threads.append({
            'thread_id':   row['thread_id'],
            'assunto':     row['assunto'],
            'status_atual': row['status_workflow'],
            'motivo_atual': row['motivo_status'],
            'grupo':       'completo',
            'ultima_msg':  msgs[-1],
        })
    return threads


# ── Consulta à IA ─────────────────────────────────────────────────────────────

def _consultar_ia(cliente: openai.OpenAI, thread: dict) -> dict:
    u             = thread['ultima_msg']
    remetente_tipo = 'Finaud' if _eh_finaud(u.get('remetente', ''), u.get('reply_to', '')) else 'cliente externo'
    texto         = _texto_limpo(u.get('corpo_texto') or '')

    if not texto.strip():
        return {'status': 'SEM_TEXTO', 'motivo': 'corpo vazio ou só histórico'}

    prompt_usuario = (
        f"Remetente da última mensagem: {remetente_tipo}\n"
        f"Assunto da conversa: {thread['assunto']}\n\n"
        f"Texto da última mensagem:\n{texto}"
    )

    try:
        resp = cliente.chat.completions.create(
            model=MODELO,
            temperature=TEMPERATURA,
            messages=[
                {'role': 'system', 'content': _PROMPT_SISTEMA},
                {'role': 'user',   'content': prompt_usuario},
            ],
            max_tokens=150,
        )
        conteudo = resp.choices[0].message.content.strip()
        m = re.search(r'\{.*\}', conteudo, re.DOTALL)
        if m:
            dados = json.loads(m.group())
            return {
                'status': dados.get('status', '?'),
                'motivo': dados.get('motivo', ''),
            }
        return {'status': 'PARSE_ERROR', 'motivo': conteudo[:200]}
    except json.JSONDecodeError as e:
        return {'status': 'JSON_ERROR',  'motivo': str(e)[:100]}
    except Exception as e:
        return {'status': 'API_ERROR',   'motivo': str(e)[:100]}


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description='Valida status de threads via GPT-4o')
    parser.add_argument('--fase',   type=int, default=1, choices=[1, 2, 3])
    parser.add_argument('--limite', type=int, default=0,
                        help='Limitar a N threads (0 = sem limite)')
    args = parser.parse_args()

    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print('ERRO: variável OPENAI_API_KEY não definida.')
        print('  Execute: set OPENAI_API_KEY=sk-...')
        sys.exit(1)

    cliente = openai.OpenAI(api_key=api_key)
    conn    = _conectar()

    if args.fase == 1:
        threads = _threads_fase1(conn)
    elif args.fase == 2:
        threads = _threads_fase2(conn)
    else:
        threads = _threads_fase3(conn)
    conn.close()

    if args.limite > 0:
        threads = threads[:args.limite]

    print(f'Fase {args.fase} — {len(threads)} threads a testar')

    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    data_hoje  = datetime.now().strftime('%Y%m%d')
    caminho_csv = SAIDA_DIR / f'{data_hoje}_fase{args.fase}_resultados.csv'

    campos = ['thread_id', 'assunto', 'grupo',
              'status_atual', 'motivo_atual',
              'ia_status', 'ia_motivo', 'bate']

    resultados: list[dict] = []
    erros = 0

    with open(caminho_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for i, thread in enumerate(threads, 1):
            label = (thread['assunto'] or '')[:60]
            print(f'  [{i:3d}/{len(threads)}] {label:<60}', end=' ... ', flush=True)

            ia = _consultar_ia(cliente, thread)
            bate = ia['status'] == thread['status_atual']
            linha = {
                'thread_id':   thread['thread_id'],
                'assunto':     thread['assunto'],
                'grupo':       thread['grupo'],
                'status_atual': thread['status_atual'],
                'motivo_atual': thread['motivo_atual'],
                'ia_status':   ia['status'],
                'ia_motivo':   ia['motivo'],
                'bate':        'SIM' if bate else 'NÃO',
            }
            writer.writerow(linha)
            resultados.append(linha)

            icone = '✅' if bate else '❌'
            print(f'{icone}  IA: {ia["status"]}')
            if ia['status'] in ('API_ERROR', 'JSON_ERROR', 'PARSE_ERROR'):
                erros += 1

    # ── Resumo ────────────────────────────────────────────────────────────────
    validas      = [r for r in resultados if r['ia_status'] not in ('API_ERROR', 'JSON_ERROR', 'PARSE_ERROR', 'SEM_TEXTO')]
    divergencias = [r for r in validas if r['bate'] == 'NÃO']
    pct = 100 * len(divergencias) / len(validas) if validas else 0

    print()
    print('=' * 60)
    print(f'Fase {args.fase} concluída')
    print(f'  Testadas     : {len(resultados)}')
    print(f'  Válidas      : {len(validas)}')
    print(f'  Divergências : {len(divergencias)} ({pct:.0f}%)')
    print(f'  Erros de API : {erros}')
    print(f'  Resultado    : {caminho_csv}')
    print('=' * 60)

    if divergencias:
        print('\nDivergências encontradas:')
        for r in divergencias:
            print(f'  [{r["grupo"]}] {r["assunto"][:55]}')
            print(f'    Sistema: {r["status_atual"]}')
            print(f'    IA diz : {r["ia_status"]} — {r["ia_motivo"]}')


if __name__ == '__main__':
    main()
