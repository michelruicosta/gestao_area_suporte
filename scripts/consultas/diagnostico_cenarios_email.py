# diagnostico_cenarios_email.py
# Mapeia todos os cenários de e-mail em produção e teste.
# Uso: python scripts/consultas/diagnostico_cenarios_email.py
# Criado em: 10/07/2026
#
# ATENÇÃO: usa x_gm_thrid (ID real da thread no Gmail) para comparar com JSON 03.
# Não usar o campo threadId do JSON 01 diretamente — para e-mails enviados pela Finaud
# esse campo pode conter o message_id no lugar do GMTHRID, causando falso "não encontrado".

import json, sys, re
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

AMBIENTES = [
    {
        'nome': 'PRODUCAO',
        'arq01': r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud\data\json\pipeline\01_extração_dados_brutos_gmail.json',
        'arq03': r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud\data\json\pipeline\03_integrador_dados_site.json',
    },
    {
        'nome': 'TESTE',
        'arq01': r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud_TESTE\data\json\pipeline\01_extração_dados_brutos_gmail.json',
        'arq03': r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud_TESTE\data\json\pipeline\03_integrador_dados_site.json',
    },
]

DOMINIOS_FINAUD = ['@finaud.com.br', '@forcapital.com.br', '@oraculo', 'coletor@']
GRUPOS_SUPORTE = ['suporte@finaud.com.br', 'suporteforcapital@finaud.com.br']

def extrair_email(s):
    m = re.search(r'[\w.+%-]+@[\w.-]+', s or '')
    return m.group(0).lower() if m else ''

def eh_finaud(s):
    return any(d in (s or '').lower() for d in DOMINIOS_FINAUD)

def eh_suporte(s):
    return any(g in (s or '').lower() for g in GRUPOS_SUPORTE)

def eh_via_suporte(rem):
    rem = (rem or '').lower()
    return 'via suporte' in rem or eh_suporte(rem)

def thread_id_real(e):
    # Sempre preferir x_gm_thrid — é o ID real da thread no Gmail.
    # thread_root é o fallback calculado pelo script 02.
    return e.get('x_gm_thrid') or e.get('thread_root') or e.get('threadId')

for amb in AMBIENTES:
    print(f'\n{"="*70}')
    print(f'AMBIENTE: {amb["nome"]}')
    print(f'{"="*70}\n')

    try:
        with open(amb['arq01'], encoding='utf-8') as f:
            emails01 = json.load(f)
        with open(amb['arq03'], encoding='utf-8') as f:
            dados03 = json.load(f)
    except FileNotFoundError as e:
        print(f'  Arquivo nao encontrado: {e}')
        continue

    # Indexar JSON 03 pelo threadId real (GMTHRID quando disponivel)
    threads03_ids = set()
    for t in dados03.get('threads', []):
        if isinstance(t, dict) and t.get('threadId'):
            threads03_ids.add(t['threadId'])

    cenarios = defaultdict(list)

    for e in emails01:
        rem = e.get('remetente') or ''
        reply = e.get('reply_to') or ''
        para = e.get('destinatarios') or ''
        assunto = (e.get('assunto') or '')[:55]
        data = (e.get('data_email') or '')[:16]
        tid = thread_id_real(e)

        rem_email = extrair_email(rem)
        reply_email = extrair_email(reply)
        para_email = extrair_email(para)
        na_tela = tid in threads03_ids

        item = {
            'assunto': assunto, 'data': data,
            'de': rem_email or rem[:50], 'para': para[:60],
            'na_tela': na_tela, 'tid': tid,
        }

        if eh_via_suporte(rem) and not reply_email:
            cenarios['B4 — Suporte reencaminha interno (sem Reply-To)'].append(item)
        elif eh_via_suporte(rem) and reply_email and not eh_finaud(reply_email):
            cenarios['B1 — Cliente envia para grupo suporte'].append(item)
        elif eh_finaud(rem_email) and not eh_suporte(rem_email) and not eh_finaud(para_email) and not eh_via_suporte(rem):
            cenarios['FC — Finaud envia para cliente externo'].append(item)
        elif eh_finaud(rem_email) and not eh_suporte(rem_email) and eh_finaud(para_email):
            cenarios['FF — Interno (colaboradora para colaboradora)'].append(item)
        elif not eh_finaud(rem_email) and not eh_via_suporte(rem):
            para_lower = (para or '').lower()
            tem_suporte_no_para = any(g in para_lower for g in GRUPOS_SUPORTE)
            if tem_suporte_no_para:
                cenarios['B2B3 — Cliente envia com suporte no Para/CC'].append(item)
            else:
                cenarios['A — Cliente envia direto para colaboradora'].append(item)
        else:
            cenarios['OUTRO — nao classificado'].append(item)

    # Resumo por cenário
    total = sum(len(v) for v in cenarios.values())
    print(f'Total e-mails: {len(emails01)} | Classificados: {total}\n')

    for nome, itens in sorted(cenarios.items()):
        na_tela = sum(1 for i in itens if i['na_tela'])
        fora = len(itens) - na_tela
        status = '✅' if fora == 0 else f'⚠️  {fora} fora da tela'
        print(f'  [{len(itens):5d}] {nome}')
        print(f'         Na tela: {na_tela} | Fora da tela: {fora} {status}')

    # Detalhar cenários com emails fora da tela (possíveis furos)
    print()
    for nome, itens in sorted(cenarios.items()):
        fora = [i for i in itens if not i['na_tela']]
        if not fora:
            continue
        print(f'  DETALHE — {nome} — {len(fora)} fora da tela:')
        # Remetentes mais frequentes
        por_rem = defaultdict(int)
        for i in fora:
            por_rem[i['de']] += 1
        for rem, qtd in sorted(por_rem.items(), key=lambda x: -x[1])[:5]:
            print(f'    {rem}: {qtd} e-mails')
        # 3 exemplos
        print('  Exemplos:')
        for i in fora[:3]:
            print(f'    [{i["data"]}] De: {i["de"]}')
            print(f'    Assunto: {i["assunto"]}')
            print()
