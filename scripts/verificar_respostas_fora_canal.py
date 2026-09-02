"""
verificar_respostas_fora_canal.py
O que faz: para cada thread AF inativa, verifica se algum colaborador
           @finaud.com.br respondeu diretamente ao cliente sem copiar
           suporte@finaud.com.br. Gera relatório em logs/ sem alterar o banco.
Uso: python scripts/verificar_respostas_fora_canal.py [--limite N]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import criar_log

from google.auth.exceptions import RefreshError, TransportError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── Configuração ───────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENCIAIS = os.path.join(BASE_DIR, 'config', 'credenciais_gmail.json')
BANCO       = os.path.join(BASE_DIR, 'data', 'gestao.db')
SCOPES      = ['https://www.googleapis.com/auth/gmail.readonly']

# Endereços internos que não são "colaboradores" — excluídos da verificação
ENDERECOS_SISTEMA = {
    'suporte@finaud.com.br',
    'coleta.oraculo@finaud.com.br',
    'coleta.oraculo@finaudtec.com.br',
}

# Endereços que indicam que o suporte foi copiado — se aparecerem no Sent, é canal correto
MARCADORES_CANAL = {'suporte@finaud.com.br', 'coleta.oraculo@finaud.com.br'}

log = criar_log('verificar_respostas_fora_canal')

_cache_servicos: dict[str, object] = {}


# ── Autenticação ───────────────────────────────────────────────────────────────

def _conectar(conta: str):
    if conta not in _cache_servicos:
        creds = service_account.Credentials.from_service_account_file(
            CREDENCIAIS, scopes=SCOPES
        ).with_subject(conta)
        _cache_servicos[conta] = build('gmail', 'v1', credentials=creds)
    return _cache_servicos[conta]


# ── Extração de endereços ──────────────────────────────────────────────────────

_RE_EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}')

def _emails(texto: str) -> set[str]:
    return {e.lower() for e in _RE_EMAIL.findall(texto or '')}

def _colaboradores_da_thread(mensagens_json: str) -> set[str]:
    """Retorna colaboradores @finaud que aparecem na thread (exceto contas de sistema)."""
    try:
        msgs = json.loads(mensagens_json) if mensagens_json else []
    except Exception:
        return set()

    encontrados: set[str] = set()
    for m in msgs:
        for campo in ('remetente', 'destinatarios', 'cc', 'reply_to'):
            for e in _emails(m.get(campo, '')):
                if e.endswith('@finaud.com.br') or e.endswith('@finaudtec.com.br'):
                    if e not in ENDERECOS_SISTEMA:
                        encontrados.add(e)
    return encontrados

def _data_para_query(data_br: str) -> str:
    """Converte DD/MM/YYYY HH:MM para YYYY/MM/DD (formato de query Gmail)."""
    try:
        partes = data_br.split(' ')[0].split('/')
        return f'{partes[2]}/{partes[1]}/{partes[0]}'
    except Exception:
        return ''


# ── Verificação no Sent do colaborador ────────────────────────────────────────

def _buscar_resposta_fora_canal(colaborador: str, assunto: str, data_ultima: str) -> dict | None:
    """
    Busca na pasta Sent do colaborador uma resposta ao mesmo assunto
    enviada após data_ultima e sem copiar suporte@finaud.com.br.
    Retorna dict com detalhes ou None se não encontrou.
    """
    try:
        svc = _conectar(colaborador)
    except Exception as e:
        log.warning(f'Sem acesso à caixa de {colaborador}: {e}')
        return None


    data_query = _data_para_query(data_ultima)
    # Remove prefixos de resposta para busca mais ampla
    assunto_limpo = re.sub(r'^(re|fwd|fw|enc):\s*', '', assunto, flags=re.IGNORECASE).strip()
    query = f'in:sent subject:"{assunto_limpo}"'
    if data_query:
        query += f' after:{data_query}'

    try:
        resultado = svc.users().messages().list(
            userId='me', q=query, maxResults=10
        ).execute()
    except (HttpError, RefreshError, TransportError, Exception) as e:
        log.warning(f'Erro ao buscar Sent de {colaborador}: {e}')
        return None

    mensagens = resultado.get('messages', [])
    if not mensagens:
        return None

    for msg_ref in mensagens:
        try:
            msg = svc.users().messages().get(
                userId='me', id=msg_ref['id'], format='metadata',
                metadataHeaders=['To', 'Cc', 'Date', 'Subject']
            ).execute()
        except (HttpError, RefreshError, TransportError, Exception):
            continue

        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
        to_cc = (headers.get('To', '') + ' ' + headers.get('Cc', '')).lower()

        # Verifica se suporte NÃO foi copiado
        copiou_suporte = any(m in to_cc for m in MARCADORES_CANAL)
        if not copiou_suporte:
            return {
                'colaborador'   : colaborador,
                'data_resposta' : headers.get('Date', ''),
                'assunto_sent'  : headers.get('Subject', ''),
                'destinatarios' : headers.get('To', ''),
                'cc'            : headers.get('Cc', ''),
            }

        time.sleep(0.1)

    return None


# ── Loop principal ─────────────────────────────────────────────────────────────

def verificar(limite: int | None = None) -> list[dict]:
    conn = sqlite3.connect(BANCO)
    cur  = conn.cursor()

    sql = """
        SELECT thread_id, assunto, data_ultima_msg, mensagens_json, categoria
        FROM threads
        WHERE status_workflow = 'Aguardando Finaud'
          AND inativa_desde IS NOT NULL
        ORDER BY data_ultima_msg DESC
    """
    if limite:
        sql += f' LIMIT {limite}'

    threads = cur.fetchall() if False else cur.execute(sql).fetchall()
    conn.close()

    log.info(f'Verificando {len(threads)} threads AF inativas...')

    resultados: list[dict] = []

    for i, (thread_id, assunto, ultima_msg, msgs_json, categoria) in enumerate(threads, 1):
        colaboradores = _colaboradores_da_thread(msgs_json)
        if not colaboradores:
            continue

        if i % 50 == 0:
            log.info(f'  {i}/{len(threads)} threads processadas...')

        for colab in colaboradores:
            achado = _buscar_resposta_fora_canal(colab, assunto or '', ultima_msg or '')
            if achado:
                resultados.append({
                    'thread_id'       : thread_id,
                    'assunto'         : assunto,
                    'categoria'       : categoria,
                    'ultima_msg_banco': ultima_msg,
                    **achado,
                })
                log.info(
                    f'  FORA DO CANAL: {thread_id} | {colab} respondeu em {achado["data_resposta"]}'
                )
                break  # um colaborador confirmado já basta para a thread

        time.sleep(0.05)

    return resultados


# ── Relatório ─────────────────────────────────────────────────────────────────

def _salvar_relatorio(resultados: list[dict]) -> str:
    from paths import LOGS_DIR
    import datetime

    nome = os.path.join(LOGS_DIR, f'respostas_fora_canal_{datetime.date.today():%Y%m%d}.csv')
    campos = [
        'thread_id', 'assunto', 'categoria', 'ultima_msg_banco',
        'colaborador', 'data_resposta', 'assunto_sent', 'destinatarios', 'cc',
    ]
    with open(nome, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(resultados)
    return nome


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Verifica respostas enviadas fora do canal de suporte')
    parser.add_argument('--limite', type=int, default=None,
                        help='Limitar a N threads (omitir = todas as 794)')
    args = parser.parse_args()

    resultados = verificar(limite=args.limite)

    total_af  = 794  # número de referência
    encontrados = len(resultados)

    print(f'\n{"="*60}')
    print(f'Threads AF inativas verificadas: {args.limite or total_af}')
    print(f'Threads com resposta FORA DO CANAL: {encontrados}')
    if resultados:
        arquivo = _salvar_relatorio(resultados)
        print(f'Relatório salvo em: {arquivo}')
    print('='*60)

    log.info(f'Concluído — {encontrados} threads com resposta fora do canal.')


if __name__ == '__main__':
    main()
