"""
coletor_gmail.py
O que faz: conecta na caixa de coleta do Oráculo 360 via Gmail API (service account),
           importa TODAS as threads na primeira vez e, nas rodadas seguintes,
           busca apenas o que é novo ou foi atualizado. Salva diretamente no banco SQLite.
"""

import os
import sys
import base64
import time
from email.utils import parsedate_to_datetime
from email.header import decode_header as _decode_header

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from banco_threads import (criar_banco, salvar_thread, get_controle_sync,
                           set_controle_sync, salvar_snapshot, registrar_coleta)

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Configuração ───────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENCIAIS = os.path.join(BASE_DIR, 'oraculo-ia-coleta.json')
CONTA       = 'coleta.oraculo@finaud.com.br'
SCOPES      = ['https://www.googleapis.com/auth/gmail.readonly']
CHECKPOINT  = 50   # imprime progresso a cada N threads


# ── Autenticação ───────────────────────────────────────────────────────────────

def _conectar_gmail():
    creds = service_account.Credentials.from_service_account_file(
        CREDENCIAIS, scopes=SCOPES
    ).with_subject(CONTA)
    return build('gmail', 'v1', credentials=creds)


# ── Decodificação de cabeçalhos MIME ──────────────────────────────────────────

def _decodificar(valor: str) -> str:
    if not valor:
        return ''
    try:
        partes = _decode_header(valor)
        resultado = ''
        for conteudo, codificacao in partes:
            if isinstance(conteudo, bytes):
                resultado += conteudo.decode(codificacao or 'utf-8', errors='replace')
            else:
                resultado += str(conteudo)
        return resultado.strip()
    except Exception:
        return valor


# ── Extração de corpo texto ────────────────────────────────────────────────────

def _extrair_texto(payload: dict) -> str:
    mime = payload.get('mimeType', '')

    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        return ''

    if mime == 'text/html':
        data = payload.get('body', {}).get('data', '')
        return '[somente HTML]' if data else ''

    texto_plain = ''
    texto_html  = ''
    for part in payload.get('parts', []):
        sub_mime = part.get('mimeType', '')
        if sub_mime == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                texto_plain += base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        elif sub_mime == 'text/html':
            data = part.get('body', {}).get('data', '')
            if data and not texto_plain:
                texto_html = '[somente HTML]'
        elif sub_mime.startswith('multipart/'):
            sub = _extrair_texto(part)
            if sub and sub != '[somente HTML]':
                texto_plain += sub
            elif sub and not texto_plain:
                texto_html = sub

    return texto_plain or texto_html or ''


# ── Extração de nomes de anexos ────────────────────────────────────────────────

def _extrair_anexos(payload: dict) -> list[str]:
    nomes = []
    for part in payload.get('parts', []):
        nome = _decodificar(part.get('filename', ''))
        if nome:
            nomes.append(nome)
        if part.get('mimeType', '').startswith('multipart/'):
            nomes.extend(_extrair_anexos(part))
    return nomes


# ── Processamento de uma mensagem ─────────────────────────────────────────────

def _processar_mensagem(msg: dict) -> dict:
    headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}

    def h(nome: str) -> str:
        return _decodificar(headers.get(nome, ''))

    data_raw = h('Date')
    try:
        dt      = parsedate_to_datetime(data_raw)
        data_br = dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        data_br = data_raw

    return {
        'data'         : data_br,
        'remetente'    : h('From'),
        'reply_to'     : h('Reply-To'),
        'destinatarios': h('To'),
        'cc'           : h('Cc'),
        'assunto'      : h('Subject'),
        'corpo_texto'  : _extrair_texto(msg.get('payload', {})),
        'nomes_anexos' : _extrair_anexos(msg.get('payload', {})),
    }


# ── Processamento de uma thread completa ──────────────────────────────────────

def _processar_thread(service, thread_id: str) -> dict | None:
    """Busca e monta os dados de uma thread completa do Gmail."""
    try:
        thread   = service.users().threads().get(
            userId='me', id=thread_id, format='full'
        ).execute()
        mensagens = thread.get('messages', [])
        if not mensagens:
            return None

        msgs = [_processar_mensagem(m) for m in mensagens]

        return {
            'thread_id'      : thread_id,
            'assunto'        : msgs[0]['assunto'],
            'qtd_mensagens'  : len(mensagens),
            'data_primeira_msg': msgs[0]['data'],
            'data_ultima_msg': msgs[-1]['data'],
            'mensagens'      : msgs,
        }
    except HttpError as e:
        print(f'  [ERRO] Thread {thread_id}: {e}')
        time.sleep(1)
        return None


# ── Importação histórica completa (primeira vez) ──────────────────────────────

def _importar_historico(service) -> tuple[str | None, int, int]:
    """
    Percorre TODAS as threads da caixa de coleta e salva no banco.
    Retorna (ultimo_hist_id, total_threads, total_erros).
    """
    print('Modo: importação histórica completa...')

    page_token     = None
    total          = 0
    erros          = 0
    ultimo_hist_id = None

    while True:
        params: dict = {'userId': 'me', 'maxResults': 500}
        if page_token:
            params['pageToken'] = page_token

        try:
            resultado      = service.users().threads().list(**params).execute()
            threads_pagina = resultado.get('threads', [])
        except HttpError as e:
            print(f'[ERRO] Falha ao listar threads: {e}')
            break

        if not threads_pagina:
            break

        for info in threads_pagina:
            thread_id = info['id']
            total    += 1

            # O historyId da listagem é suficiente para rastrear a posição mais recente
            hist_id = info.get('historyId')
            if hist_id and (not ultimo_hist_id or int(hist_id) > int(ultimo_hist_id)):
                ultimo_hist_id = hist_id

            thread_data = _processar_thread(service, thread_id)
            if thread_data:
                salvar_thread(thread_data)
                print(f'  [{total:>4}] {thread_data["assunto"][:65]}')
            else:
                erros += 1

            if total % CHECKPOINT == 0:
                print(f'  ... {total} threads salvas no banco')

        page_token = resultado.get('nextPageToken')
        if not page_token:
            break

        time.sleep(0.1)

    print(f'\nImportação concluída: {total} threads | {erros} erros')
    return (str(ultimo_hist_id) if ultimo_hist_id else None), total, erros


# ── Sincronização incremental (rodadas seguintes) ─────────────────────────────

def _sincronizar_incremental(service, start_history_id: str) -> tuple[str | None, int, int]:
    """
    Usa a API de histórico do Gmail para buscar apenas threads que mudaram
    desde a última sincronização. Muito mais rápido que reimportar tudo.

    Retorna (novo_hist_id, threads_salvas, erros).
    novo_hist_id=None significa que o historyId expirou → chamador refaz importação histórica.
    """
    print(f'Modo: sincronização incremental (desde historyId {start_history_id})...')

    thread_ids_novas: set = set()
    page_token           = None
    novo_hist_id         = start_history_id

    while True:
        params: dict = {
            'userId'        : 'me',
            'startHistoryId': start_history_id,
            'historyTypes'  : ['messageAdded'],
        }
        if page_token:
            params['pageToken'] = page_token

        try:
            resultado = service.users().history().list(**params).execute()
        except HttpError as e:
            if 'invalidHistoryId' in str(e) or e.resp.status == 404:
                print('[AVISO] historyId expirou. Será feita importação histórica completa.')
                return None, 0, 0
            print(f'[ERRO] Falha na sincronização incremental: {e}')
            return start_history_id, 0, 0  # mantém o historyId anterior

        for entrada in resultado.get('history', []):
            for msg_info in entrada.get('messagesAdded', []):
                thread_ids_novas.add(msg_info['message']['threadId'])
            hist_atual = entrada.get('id')
            if hist_atual and int(hist_atual) > int(novo_hist_id):
                novo_hist_id = hist_atual

        page_token = resultado.get('nextPageToken')
        if not page_token:
            break

    if not thread_ids_novas:
        print('Nenhuma thread nova desde a última sincronização.')
        return novo_hist_id, 0, 0

    salvadas = 0
    erros_thread = 0
    print(f'{len(thread_ids_novas)} thread(s) nova(s)/atualizada(s). Salvando...')
    for thread_id in thread_ids_novas:
        thread_data = _processar_thread(service, thread_id)
        if thread_data:
            salvar_thread(thread_data)
            salvadas += 1
            print(f'  Atualizada: {thread_data["assunto"][:65]}')
        else:
            erros_thread += 1

    return novo_hist_id, salvadas, erros_thread


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def coletar() -> None:
    print('=' * 60)
    print('COLETOR GMAIL — caixa de coleta do Oráculo 360')
    print('=' * 60)

    _inicio = time.time()
    tipo = 'incremental'
    threads_proc = 0
    total_erros = 0

    try:
        criar_banco()

        # Snapshot do estado antes desta rodada — base para o delta exibido na tela
        salvar_snapshot()
        print('Snapshot de contadores salvo.')

        service = _conectar_gmail()

        start_hist_id = get_controle_sync('last_history_id')

        if start_hist_id:
            novo_hist_id, tp, err = _sincronizar_incremental(service, start_hist_id)
            if novo_hist_id is None:
                # historyId expirou: reimporta tudo
                tipo = 'historica'
                novo_hist_id, threads_proc, total_erros = _importar_historico(service)
            else:
                threads_proc = tp
                total_erros = err
        else:
            tipo = 'historica'
            novo_hist_id, threads_proc, total_erros = _importar_historico(service)

        if novo_hist_id:
            set_controle_sync('last_history_id', str(novo_hist_id))
            print(f'Marcador de sincronização atualizado: {novo_hist_id}')

        duracao = time.time() - _inicio
        registrar_coleta(tipo, threads_proc, total_erros, duracao, 'concluida')

        print()
        print('=' * 60)
        print('Coleta concluída.')
        print('=' * 60)

    except Exception as exc:
        duracao = time.time() - _inicio
        registrar_coleta(tipo, threads_proc, total_erros, duracao, 'erro', str(exc))
        print(f'\n[ERRO FATAL] {exc}')
        raise


if __name__ == '__main__':
    coletar()
