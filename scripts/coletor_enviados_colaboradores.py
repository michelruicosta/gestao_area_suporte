"""
coletor_enviados_colaboradores.py
O que faz: complementa a coleta do oraculo@ lendo enviados e recebidos
           dos colaboradores de suporte listados em config.json.
           Captura respostas enviadas sem copiar suporte@ (cenário 4)
           e respostas do cliente direto ao colaborador (cenário 5).
           Nunca cria threads novas — só enriquece as que já existem no banco.
           Roda todo dia às 6h dentro do pipeline (executar_pipeline.py).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coletor_gmail import _processar_mensagem
from paths import criar_log

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENCIAIS = os.path.join(BASE_DIR, 'config', 'credenciais_gmail.json')
BANCO       = os.path.join(BASE_DIR, 'data', 'gestao.db')
CONFIG_PATH = os.path.join(BASE_DIR, 'data', 'config.json')
SCOPES      = ['https://www.googleapis.com/auth/gmail.readonly']

_RE_PREFIXO   = re.compile(r'^(re|res|fwd|fw|enc|encaminhado|rv|r):\s*', re.IGNORECASE)
_RE_EMAIL     = re.compile(r'[\w.+-]+@[\w.+-]+\.\w+')
_RE_EMAIL_ABK = re.compile(r'<([\w.+-]+@[\w.+-]+\.\w+)>')  # "Nome <email>"
_FINAUD_DOMS  = {'finaud.com.br', 'finaudtec.com.br'}
MAX_CANDIDATOS = 3  # mais que isso → assunto genérico demais, pular

log = criar_log('coletor_colaboradores')
_cache_svc: dict[str, object] = {}


# ── Config ────────────────────────────────────────────────────────────────────

def _ler_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


# ── Assunto normalizado ───────────────────────────────────────────────────────

def _normalizar(assunto: str) -> str:
    s = assunto.strip()
    while True:
        s2 = _RE_PREFIXO.sub('', s).strip()
        if s2 == s:
            break
        s = s2
    return s.lower()


# ── Gmail API ─────────────────────────────────────────────────────────────────

def _svc(conta: str):
    if conta not in _cache_svc:
        creds = service_account.Credentials.from_service_account_file(
            CREDENCIAIS, scopes=SCOPES
        ).with_subject(conta)
        _cache_svc[conta] = build('gmail', 'v1', credentials=creds)
    return _cache_svc[conta]


def _listar(conta: str, query: str, max_results: int = 200) -> list[dict]:
    try:
        resp = _svc(conta).users().messages().list(
            userId='me', q=query, maxResults=max_results
        ).execute()
        return resp.get('messages', [])
    except (HttpError, RefreshError, Exception) as e:
        log.warning('Erro ao listar %s (%s): %s', conta, query[:60], e)
        return []


def _detalhar(conta: str, msg_id: str) -> dict | None:
    try:
        msg = _svc(conta).users().messages().get(
            userId='me', id=msg_id, format='full'
        ).execute()
        return _processar_mensagem(msg)
    except (HttpError, RefreshError, Exception) as e:
        log.warning('Erro ao detalhar %s/%s: %s', conta, msg_id, e)
        return None


def _headers(conta: str, msg_id: str) -> dict:
    """Busca Subject, Date, From, To, Cc — mais rápido que full."""
    try:
        msg = _svc(conta).users().messages().get(
            userId='me', id=msg_id, format='metadata',
            metadataHeaders=['Subject', 'Date', 'From', 'To', 'Cc']
        ).execute()
        return {h['name']: h['value']
                for h in msg.get('payload', {}).get('headers', [])}
    except (HttpError, RefreshError, Exception):
        return {}


# ── Participantes ─────────────────────────────────────────────────────────────

def _extrair_email(texto: str) -> str | None:
    m = _RE_EMAIL_ABK.search(texto)
    if m:
        return m.group(1).lower()
    m = _RE_EMAIL.search(texto)
    return m.group(0).lower() if m else None


def _eh_externo(email: str) -> bool:
    return email.split('@')[-1].lower() not in _FINAUD_DOMS


def _externos_hdrs(hdrs: dict) -> set[str]:
    """Emails externos (não-Finaud) presentes no From/To/Cc do cabeçalho."""
    texto = ' '.join([hdrs.get('From', ''), hdrs.get('To', ''), hdrs.get('Cc', '')])
    return {e.lower() for e in _RE_EMAIL.findall(texto) if _eh_externo(e)}


def _externos_thread(thread: dict) -> set[str]:
    """Emails externos já conhecidos na thread (remetente_principal + primeiras msgs)."""
    emails: set[str] = set()
    e = _extrair_email(thread.get('remetente_principal', ''))
    if e and _eh_externo(e):
        emails.add(e)
    for msg in thread.get('mensagens', [])[:10]:
        e = _extrair_email(msg.get('remetente', ''))
        if e and _eh_externo(e):
            emails.add(e)
        for dest in msg.get('destinatarios', '').split(','):
            e = _extrair_email(dest.strip())
            if e and _eh_externo(e):
                emails.add(e)
    return emails


# ── Banco ─────────────────────────────────────────────────────────────────────

def _carregar_threads() -> dict[str, dict]:
    """Retorna threads em destino='principal' indexadas por thread_id."""
    conn = sqlite3.connect(BANCO)
    rows = conn.execute("""
        SELECT thread_id, assunto, mensagens_json, data_ultima_msg,
               data_primeira_msg, remetente_principal, destinatario_principal
        FROM threads WHERE destino = 'principal'
    """).fetchall()
    conn.close()
    resultado = {}
    for tid, assunto, mjson, dult, dpri, rem, dest in rows:
        try:
            msgs = json.loads(mjson) if mjson else []
        except Exception:
            msgs = []
        resultado[tid] = {
            'thread_id'              : tid,
            'assunto'                : assunto or '',
            'mensagens'              : msgs,
            'data_ultima_msg'        : dult or '',
            'data_primeira_msg'      : dpri or '',
            'remetente_principal'    : rem or '',
            'destinatario_principal' : dest or '',
        }
    return resultado


def _ja_existe(msgs: list[dict], nova: dict) -> bool:
    chave = (nova.get('data', ''), nova.get('remetente', ''))
    return any((m.get('data', ''), m.get('remetente', '')) == chave for m in msgs)


def _chave_data(m: dict) -> str:
    d = m.get('data', '')
    try:
        p = d.split(' ')
        dd, mm, aa = p[0].split('/')
        return f'{aa}-{mm}-{dd} {p[1] if len(p) > 1 else "00:00"}'
    except Exception:
        return d


def _salvar(thread: dict) -> None:
    msgs = thread['mensagens']
    if not msgs:
        return
    ultima = msgs[-1]
    conn = sqlite3.connect(BANCO)
    conn.execute("""
        UPDATE threads SET
            mensagens_json          = ?,
            qtd_mensagens           = ?,
            data_ultima_msg         = ?,
            remetente_ultima_msg    = ?,
            destinatario_ultima_msg = ?,
            reply_to_ultima_msg     = ?,
            ultima_sync             = ?
        WHERE thread_id = ?
    """, (
        json.dumps(msgs, ensure_ascii=False),
        len(msgs),
        ultima.get('data', ''),
        ultima.get('remetente', ''),
        ultima.get('destinatarios', ''),
        ultima.get('reply_to', ''),
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        thread['thread_id'],
    ))
    conn.commit()
    conn.close()


# ── Coleta ────────────────────────────────────────────────────────────────────

def coletar_colaboradores() -> dict:
    """
    Para cada colaborador, busca mensagens enviadas e recebidas de externos
    nos últimos N dias. Para cada mensagem encontrada, verifica se o assunto
    corresponde a uma thread do banco — se sim e a mensagem for nova, adiciona.
    Nunca cria threads novas, nunca sobrescreve mensagens existentes.
    """
    cfg          = _ler_config()
    colaboradores = cfg.get('colaboradores_suporte', [])
    dias         = int(cfg.get('dias_coleta_colaboradores', 30))

    if not colaboradores:
        log.info('Nenhum colaborador em colaboradores_suporte — nada a fazer.')
        return {'colaboradores': 0, 'mensagens_novas': 0, 'threads_atualizadas': 0}

    data_corte = (datetime.now() - timedelta(days=dias)).strftime('%Y/%m/%d')

    # Carregar banco e montar índice assunto_normalizado → [thread_ids]
    threads_banco = _carregar_threads()
    indice: dict[str, list[str]] = {}
    for tid, t in threads_banco.items():
        chave = _normalizar(t['assunto'])
        if chave:
            indice.setdefault(chave, []).append(tid)

    log.info('Banco: %d threads | índice: %d assuntos | %d colaboradores | últimos %d dias',
             len(threads_banco), len(indice), len(colaboradores), dias)

    threads_mod: dict[str, dict] = {}
    total_novas = 0

    for colaborador in colaboradores:
        log.info('Verificando: %s', colaborador)

        # Buscar mensagens recentes: enviadas (cenário 4) e inbox externos (cenário 5)
        queries = [
            f'in:sent after:{data_corte}',
            f'in:inbox after:{data_corte} -from:finaud.com.br -from:finaudtec.com.br',
        ]

        for query in queries:
            refs = _listar(colaborador, query)
            for ref in refs:
                # 1. Buscar headers (Subject, From, To, Cc)
                hdrs = _headers(colaborador, ref['id'])
                assunto_msg = _normalizar(hdrs.get('Subject', ''))
                candidatos  = indice.get(assunto_msg, [])
                if not candidatos:
                    time.sleep(0.03)
                    continue

                # 2. Filtrar por participante: só manter threads que já conhecem
                #    ao menos um email externo presente no From/To/Cc da mensagem
                externos_msg = _externos_hdrs(hdrs)
                if externos_msg:
                    candidatos = [
                        tid for tid in candidatos
                        if _externos_thread(threads_banco[tid]) & externos_msg
                    ]
                if not candidatos:
                    time.sleep(0.03)
                    continue

                # 3. Segurança extra: assunto genérico demais → pular
                if len(candidatos) > MAX_CANDIDATOS:
                    log.debug('Assunto "%s" → %d candidatos após filtro, pulando',
                              assunto_msg[:50], len(candidatos))
                    time.sleep(0.03)
                    continue

                # 4. Assunto + participante bateram — buscar mensagem completa
                detalhe = _detalhar(colaborador, ref['id'])
                if not detalhe:
                    time.sleep(0.03)
                    continue

                for tid in candidatos:
                    thread = threads_mod.get(tid) or dict(threads_banco[tid])
                    thread['mensagens'] = list(thread['mensagens'])

                    if _ja_existe(thread['mensagens'], detalhe):
                        continue

                    thread['mensagens'].append(detalhe)
                    thread['mensagens'].sort(key=_chave_data)
                    threads_mod[tid] = thread
                    total_novas += 1
                    log.info('  + thread %s | %s | %s',
                             tid, detalhe.get('remetente', '')[:45], detalhe.get('data', ''))

                time.sleep(0.05)

        time.sleep(0.1)

    # Salvar tudo
    for thread in threads_mod.values():
        _salvar(thread)

    log.info('Concluído — %d threads atualizadas, %d mensagens novas.',
             len(threads_mod), total_novas)

    return {
        'colaboradores'      : len(colaboradores),
        'mensagens_novas'    : total_novas,
        'threads_atualizadas': len(threads_mod),
    }


if __name__ == '__main__':
    r = coletar_colaboradores()
    print(f"\nColaboradores verificados  : {r['colaboradores']}")
    print(f"Mensagens novas adicionadas: {r['mensagens_novas']}")
    print(f"Threads atualizadas        : {r['threads_atualizadas']}")
