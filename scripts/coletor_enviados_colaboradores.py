"""
coletor_enviados_colaboradores.py
O que faz: complementa a coleta do oraculo@ lendo enviados e recebidos
           dos colaboradores de suporte listados em config.json.
           Captura respostas enviadas sem copiar suporte@ (cenário 4)
           e respostas do cliente direto ao colaborador (cenário 5).
           Nunca cria threads novas — só enriquece as que já existem no banco.
           Roda todo dia às 6h dentro do pipeline (executar_pipeline.py).
           Identificação da thread: Message-ID / In-Reply-To (não assunto).
"""
from __future__ import annotations

import json
import os
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

log = criar_log('coletor_colaboradores')
_cache_svc: dict[str, object] = {}


# ── Config ────────────────────────────────────────────────────────────────────

def _ler_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


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
    """Busca cabeçalhos para identificar a thread por cadeia de resposta."""
    try:
        msg = _svc(conta).users().messages().get(
            userId='me', id=msg_id, format='metadata',
            metadataHeaders=['Subject', 'Date', 'From', 'To', 'Cc',
                             'Message-ID', 'In-Reply-To', 'References']
        ).execute()
        return {h['name']: h['value']
                for h in msg.get('payload', {}).get('headers', [])}
    except (HttpError, RefreshError, Exception):
        return {}


# ── Índice por Message-ID ─────────────────────────────────────────────────────

def _construir_indice_mid(threads_banco: dict) -> dict[str, str]:
    """Constrói índice message_id → thread_id a partir das mensagens gravadas no banco."""
    indice: dict[str, str] = {}
    for tid, t in threads_banco.items():
        for msg in t.get('mensagens', []):
            mid = msg.get('message_id', '').strip()
            if mid:
                indice[mid] = tid
    return indice


def _thread_por_reply(in_reply_to: str, references: str,
                      indice_mid: dict[str, str]) -> str | None:
    """Retorna thread_id se In-Reply-To ou References aponta para mensagem conhecida no banco."""
    if in_reply_to:
        tid = indice_mid.get(in_reply_to.strip())
        if tid:
            return tid
    # References: cadeia de Message-IDs separados por espaço — checar da direita (mais recente)
    if references:
        for mid in reversed(references.split()):
            mid = mid.strip()
            if mid and mid in indice_mid:
                return indice_mid[mid]
    return None


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
    mid = nova.get('message_id', '').strip()
    if mid:
        # Message-ID é idêntico em todas as cópias do mesmo e-mail (RFC 5322).
        # Cobre o caso em que o mesmo e-mail chega via suporte@ e via caixa direta.
        for m in msgs:
            m_mid = m.get('message_id', '').strip()
            if m_mid:
                if m_mid == mid:
                    return True
            else:
                # Mensagem antiga sem message_id: fallback por (data, remetente).
                if (m.get('data', ''), m.get('remetente', '')) == (nova.get('data', ''), nova.get('remetente', '')):
                    return True
        return False
    # Nova sem message_id: fallback integral por (data, remetente).
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
    nos últimos N dias. Para cada mensagem encontrada, localiza a thread
    correta pelo cabeçalho In-Reply-To/References (Message-ID exato) — sem
    usar assunto. Se não encontrar correspondência no banco, descarta.
    Nunca cria threads novas.
    """
    cfg           = _ler_config()
    colaboradores = cfg.get('colaboradores_suporte', [])
    dias          = int(cfg.get('dias_coleta_colaboradores', 30))

    if not colaboradores:
        log.info('Nenhum colaborador em colaboradores_suporte — nada a fazer.')
        return {'colaboradores': 0, 'mensagens_novas': 0, 'threads_atualizadas': 0}

    data_corte = (datetime.now() - timedelta(days=dias)).strftime('%Y/%m/%d')

    threads_banco = _carregar_threads()
    indice_mid    = _construir_indice_mid(threads_banco)

    log.info('Banco: %d threads | %d message-ids indexados | %d colaboradores | últimos %d dias',
             len(threads_banco), len(indice_mid), len(colaboradores), dias)

    threads_mod: dict[str, dict] = {}
    total_novas = 0

    for colaborador in colaboradores:
        log.info('Verificando: %s', colaborador)

        queries = [
            f'in:sent after:{data_corte}',
            f'in:inbox after:{data_corte} -from:finaud.com.br -from:finaudtec.com.br',
        ]

        for query in queries:
            refs = _listar(colaborador, query)
            for ref in refs:
                # 1. Buscar cabeçalhos incluindo In-Reply-To e References
                hdrs = _headers(colaborador, ref['id'])

                in_reply_to = hdrs.get('In-Reply-To', '')
                references  = hdrs.get('References', '')

                # 2. Sem marcadores de resposta → não é reply de conversa conhecida
                if not in_reply_to and not references:
                    time.sleep(0.03)
                    continue

                # 3. Localizar thread pelo encadeamento de Message-IDs
                tid = _thread_por_reply(in_reply_to, references, indice_mid)
                if not tid:
                    time.sleep(0.03)
                    continue

                # 4. Encontrou — buscar mensagem completa e adicionar se nova
                detalhe = _detalhar(colaborador, ref['id'])
                if not detalhe:
                    time.sleep(0.03)
                    continue

                thread = threads_mod.get(tid) or dict(threads_banco[tid])
                thread['mensagens'] = list(thread['mensagens'])

                if _ja_existe(thread['mensagens'], detalhe):
                    time.sleep(0.03)
                    continue

                thread['mensagens'].append(detalhe)
                thread['mensagens'].sort(key=_chave_data)
                threads_mod[tid] = thread
                total_novas += 1
                log.info('  + thread %s | %s | %s',
                         tid, detalhe.get('remetente', '')[:45], detalhe.get('data', ''))

                time.sleep(0.05)

        time.sleep(0.1)

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
