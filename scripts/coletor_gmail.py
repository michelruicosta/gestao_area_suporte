"""
coletor_gmail.py
O que faz: conecta na caixa oraculo@finaud.com.br via Gmail API (service account),
           extrai TODAS as threads do histórico com os campos do §7 da spec,
           e salva em data/json/pipeline/01_extração_dados_brutos_gmail.json.

Saída por thread:
  thread_id, assunto, qtd_mensagens, data_primeira_msg, data_ultima_msg
  mensagens[]: remetente, reply_to, destinatarios, cc, assunto,
               corpo_texto, nomes_anexos, data

Uso: python scripts/coletor_gmail.py
"""

import os
import sys
import json
import base64
import time
from email.utils import parsedate_to_datetime
from email.header import decode_header as _decode_header

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import F_EMAILS_BRUTOS, backup_pre_carga, limpar_nome_arquivo

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Configuração ───────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENCIAIS = os.path.join(BASE_DIR, 'oraculo-ia-coleta.json')
CONTA       = 'coleta.oraculo@finaud.com.br'
SCOPES      = ['https://www.googleapis.com/auth/gmail.readonly']
CHECKPOINT  = 50   # salva a cada N threads processadas


# ── Autenticação ───────────────────────────────────────────────────────────────

def _conectar():
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
    """Percorre o payload recursivamente e retorna o melhor texto disponível."""
    mime = payload.get('mimeType', '')

    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        return ''

    if mime == 'text/html':
        # guarda como fallback — texto puro é preferido
        data = payload.get('body', {}).get('data', '')
        return '[somente HTML]' if data else ''

    # multipart: percorre parts em busca de texto puro primeiro
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
    """Retorna lista de nomes de arquivos anexados (só nomes, sem download)."""
    nomes = []
    for part in payload.get('parts', []):
        nome = part.get('filename', '')
        if nome:
            nomes.append(limpar_nome_arquivo(_decodificar(nome)))
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


# ── Gravação com checkpoint ───────────────────────────────────────────────────

def _salvar(dados: list, silencioso: bool = False) -> None:
    os.makedirs(os.path.dirname(F_EMAILS_BRUTOS), exist_ok=True)
    tmp = F_EMAILS_BRUTOS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, F_EMAILS_BRUTOS)
    if not silencioso:
        print(f'   💾 Checkpoint: {len(dados)} threads salvas.')


# ── Coleta principal ──────────────────────────────────────────────────────────

def coletar() -> None:
    print('=' * 60)
    print('COLETOR GMAIL — oraculo@finaud.com.br')
    print('Extraindo histórico completo...')
    print('=' * 60)

    service = _conectar()

    # Backup do arquivo atual antes de sobrescrever
    backup_pre_carga('coleta_historico')

    threads_json: list[dict] = []
    page_token = None
    total      = 0
    erros      = 0

    while True:
        params: dict = {'userId': 'me', 'maxResults': 500}
        if page_token:
            params['pageToken'] = page_token

        try:
            resultado      = service.users().threads().list(**params).execute()
            threads_pagina = resultado.get('threads', [])
        except HttpError as e:
            print(f'\n[ERRO] Falha ao listar threads: {e}')
            break

        if not threads_pagina:
            break

        for info in threads_pagina:
            thread_id = info['id']
            total    += 1

            try:
                thread   = service.users().threads().get(
                    userId='me', id=thread_id, format='full'
                ).execute()
                mensagens = thread.get('messages', [])

                if not mensagens:
                    continue

                msgs = [_processar_mensagem(m) for m in mensagens]

                threads_json.append({
                    'thread_id'      : thread_id,
                    'assunto'        : msgs[0]['assunto'],
                    'qtd_mensagens'  : len(mensagens),
                    'data_primeira_msg': msgs[0]['data'],
                    'data_ultima_msg': msgs[-1]['data'],
                    'mensagens'      : msgs,
                })

                print(f'  [{total:>4}] {msgs[0]["assunto"][:65]}')

            except HttpError as e:
                erros += 1
                print(f'  [ERRO] Thread {thread_id}: {e}')
                time.sleep(1)   # aguarda 1 s antes de continuar após erro de API

            if total % CHECKPOINT == 0:
                _salvar(threads_json)

        page_token = resultado.get('nextPageToken')
        if not page_token:
            break

    _salvar(threads_json)

    print()
    print('=' * 60)
    print(f'✅ Coleta concluída!')
    print(f'   Threads extraídas : {len(threads_json)}')
    print(f'   Erros             : {erros}')
    print(f'   Arquivo           : {F_EMAILS_BRUTOS}')
    print('=' * 60)


if __name__ == '__main__':
    coletar()
