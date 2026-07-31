"""
analisar_threads_datas.py — analisa threads e datas para definir as regras do Campo 8

Para que serve: responder as 3 questões do Campo 8 da especificação:
  Q1 — Thread ID: quantos e-mails por thread? Threads com e-mails de categorias diferentes?
  Q2 — Threads de canal: quais são? Quantas mensagens? Quantos meses abrangem?
  Q3 — Data de referência: o assunto/nome de anexo revela o mês de competência do CADOC?

Fonte: oraculo_360_finaud — histórico completo de produção (8.825 e-mails)
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

PROJETO_DADOS = r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud'
N_EXEMPLOS = 5

PATH_J01 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '01_extração_dados_brutos_gmail.json'
PATH_J03 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '03_integrador_dados_site.json'

SEP1 = '=' * 70
SEP2 = '─' * 70

CATS_TRIAGEM = {
    'DDR_2011', '4111', 'DRM_2060', 'DLO_2061', 'DLI_2062',
    'DRL_2160', 'S5', 'RETORNO_BACEN', 'SUPORTE', 'FORCAPITAL',
    'DRSAC', '6209'
}

# Padrões de data de competência no assunto (mês/ano do CADOC)
PAD_DATA_ASSUNTO = [
    re.compile(r'\b(\d{2})[/\-\.](\d{4})\b'),          # MM/YYYY ou MM-YYYY
    re.compile(r'\b(\d{4})[/\-\.](\d{2})\b'),          # YYYY/MM
    re.compile(r'\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[^\d]*(\d{4})\b', re.I),
]

MESES_PT = {'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,
            'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12}

def carregar_json(path):
    if not path.exists():
        print(f'ERRO: não encontrado → {path}')
        sys.exit(1)
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def parse_data(raw):
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
    except Exception:
        return None

def extrair_mes_competencia(assunto, anexos):
    """Tenta extrair mês/ano de competência do assunto ou nome de anexo."""
    textos = [assunto] + [a.get('nome_original', '') for a in (anexos or [])]
    for texto in textos:
        for pad in PAD_DATA_ASSUNTO:
            m = pad.search(texto)
            if m:
                g = m.groups()
                try:
                    if g[0].lower() in MESES_PT:
                        return (int(g[1]), MESES_PT[g[0].lower()])
                    a, b = int(g[0]), int(g[1])
                    if a > 1900:   # YYYY/MM
                        return (a, b)
                    elif b > 1900: # MM/YYYY
                        return (b, a)
                except Exception:
                    pass
    return None

def main():
    print(SEP1)
    print('ANÁLISE DE THREADS E DATAS — Campo 8 da Especificação')
    print(SEP1)

    j01 = carregar_json(PATH_J01)
    j03 = carregar_json(PATH_J03)
    eventos = j03['eventos']

    id_para_cat = {str(e['id']): e['cadoc'] for e in eventos}
    id_para_ev  = {str(e['id']): e for e in eventos}

    # Filtrar categorias de triagem
    emails = []
    for e in j01:
        cat = id_para_cat.get(str(e['id']), '')
        if cat in CATS_TRIAGEM:
            e['_categoria'] = cat
            emails.append(e)

    print(f'\nTotal de e-mails nas categorias de triagem: {len(emails)}')

    # ── Q1: Threads — estrutura ────────────────────────────────────────────
    print(f'\n{SEP1}')
    print('Q1 — ESTRUTURA DAS THREADS')
    print(SEP1)

    # Campo de thread disponível
    tem_thread_root  = sum(1 for e in emails if e.get('thread_root'))
    tem_x_gm_thrid   = sum(1 for e in emails if e.get('x_gm_thrid'))
    tem_threadId     = sum(1 for e in emails if e.get('threadId'))
    print(f'\nCampo thread_root preenchido:  {tem_thread_root} ({100*tem_thread_root/len(emails):.1f}%)')
    print(f'Campo x_gm_thrid preenchido:   {tem_x_gm_thrid} ({100*tem_x_gm_thrid/len(emails):.1f}%)')
    print(f'Campo threadId preenchido:      {tem_threadId} ({100*tem_threadId/len(emails):.1f}%)')

    # Usar thread_root como chave de agrupamento; fallback: x_gm_thrid
    def thread_key(e):
        return e.get('thread_root') or e.get('x_gm_thrid') or ''

    # Agrupar e-mails por thread
    threads = defaultdict(list)
    for e in emails:
        tk = thread_key(e)
        if tk:
            threads[tk].append(e)

    sem_thread = sum(1 for e in emails if not thread_key(e))
    print(f'\nE-mails com thread identificada: {sum(len(v) for v in threads.values())} ({len(threads)} threads únicas)')
    print(f'E-mails sem thread: {sem_thread}')

    # Distribuição de e-mails por thread
    tamanhos = sorted((len(v) for v in threads.values()), reverse=True)
    conta = Counter(tamanhos)
    print(f'\nDistribuição de e-mails por thread:')
    print(f'  {"Emails/thread":<18} {"Threads":>8} {"% do total":>12}')
    print(f'  {SEP2[:40]}')
    total_threads = len(tamanhos)
    for n in sorted(conta):
        pct = 100 * conta[n] / total_threads
        if pct >= 0.5 or n >= 10:
            barra = '█' * int(pct / 2)
            print(f'  {n:<18} {conta[n]:>8}   {pct:>6.1f}%  {barra}')

    print(f'\nThreads com 1 e-mail (isolados):  {conta.get(1,0)} ({100*conta.get(1,0)/total_threads:.1f}%)')
    print(f'Threads com 2-5 e-mails:          {sum(conta[n] for n in range(2,6))} ({100*sum(conta[n] for n in range(2,6))/total_threads:.1f}%)')
    print(f'Threads com 6-20 e-mails:         {sum(conta[n] for n in range(6,21))} ({100*sum(conta[n] for n in range(6,21))/total_threads:.1f}%)')
    print(f'Threads com 21+ e-mails:          {sum(conta[n] for n in tamanhos if n >= 21)} ({100*sum(conta[n] for n in tamanhos if n>=21)/total_threads:.1f}%)')

    # Threads com e-mails de mais de uma categoria (threads mistas)
    threads_mistas = {}
    for tk, msgs in threads.items():
        cats = set(e['_categoria'] for e in msgs)
        if len(cats) > 1:
            threads_mistas[tk] = (cats, msgs)

    print(f'\nThreads com e-mails de 2+ categorias distintas: {len(threads_mistas)}')
    if threads_mistas:
        print(f'Exemplos:')
        for tk, (cats, msgs) in list(threads_mistas.items())[:N_EXEMPLOS]:
            assunto = msgs[0].get('assunto', '')[:60]
            print(f'  {len(msgs)} msgs | {cats} | {assunto}')

    # ── Q2: Threads de canal ──────────────────────────────────────────────
    print(f'\n{SEP1}')
    print('Q2 — THREADS DE CANAL (reutilizadas por meses)')
    print(SEP1)

    # Canal = thread com muitos e-mails abrangendo múltiplos meses
    canais = []
    for tk, msgs in threads.items():
        datas = []
        for e in msgs:
            d = parse_data(e.get('data_email', ''))
            if d:
                datas.append(d)
        if not datas:
            continue
        datas.sort()
        span_dias = (datas[-1] - datas[0]).days
        n_meses = len(set((d.year, d.month) for d in datas))
        if len(msgs) >= 10 or n_meses >= 3:
            canais.append({
                'thread': tk,
                'msgs': msgs,
                'datas': datas,
                'span_dias': span_dias,
                'n_meses': n_meses,
                'cats': set(e['_categoria'] for e in msgs),
            })

    canais.sort(key=lambda x: (-x['span_dias'], -len(x['msgs'])))

    print(f'\nThreads com 10+ e-mails OU abrangendo 3+ meses: {len(canais)}')
    print(f'(como % do total de threads: {100*len(canais)/total_threads:.1f}%)')

    if canais:
        print(f'\nTop {min(10, len(canais))} threads de canal:')
        print(f'  {"Msgs":>5}  {"Meses":>6}  {"Período":>25}  Categorias')
        print(f'  {SEP2[:65]}')
        for c in canais[:10]:
            inicio = c['datas'][0].strftime('%b/%Y')
            fim = c['datas'][-1].strftime('%b/%Y')
            cats = ', '.join(sorted(c['cats']))
            assunto = c['msgs'][0].get('assunto', '')[:50]
            print(f'  {len(c["msgs"]):>5}  {c["n_meses"]:>6}  {inicio} → {fim}  [{cats}]')
            print(f'         Assunto: {assunto}')

    # ── Q3: Data de competência ───────────────────────────────────────────
    print(f'\n{SEP1}')
    print('Q3 — DATA DE COMPETÊNCIA DO CADOC (mês referência vs. data do e-mail)')
    print(SEP1)

    # Para e-mails com categoria que tem competência definida (DDR, DRM, DLO, DLI etc.)
    # comparar: mês do e-mail vs. mês de competência extraído do assunto/anexo
    cats_com_competencia = {'DDR_2011', 'DRM_2060', 'DLO_2061', 'DLI_2062', 'DRL_2160', 'S5', '4111'}

    encontrou_data   = 0
    nao_encontrou    = 0
    mesmo_mes        = 0
    mes_anterior     = 0
    dois_meses_antes = 0
    diferenca_meses  = Counter()

    exemplos_diff = []

    for e in emails:
        if e['_categoria'] not in cats_com_competencia:
            continue
        data_email = parse_data(e.get('data_email', ''))
        if not data_email:
            continue
        comp = extrair_mes_competencia(e.get('assunto', ''), e.get('anexos_detectados'))
        if not comp:
            nao_encontrou += 1
            continue
        encontrou_data += 1
        ano_comp, mes_comp = comp
        diff = (data_email.year * 12 + data_email.month) - (ano_comp * 12 + mes_comp)
        diferenca_meses[diff] += 1
        if diff == 0:
            mesmo_mes += 1
        elif diff == 1:
            mes_anterior += 1
        elif diff == 2:
            dois_meses_antes += 1
        if 0 < diff <= 3 and len(exemplos_diff) < 10:
            exemplos_diff.append({
                'cat': e['_categoria'],
                'assunto': e.get('assunto', '')[:65],
                'data_email': data_email.strftime('%Y-%m-%d'),
                'competencia': f'{mes_comp:02d}/{ano_comp}',
                'diff_meses': diff,
            })

    total_analisado = encontrou_data + nao_encontrou
    print(f'\nE-mails com categoria e data analisados: {total_analisado}')
    print(f'Com data de competência detectável no assunto/anexo: {encontrou_data} ({100*encontrou_data/max(1,total_analisado):.1f}%)')
    print(f'Sem data de competência detectável: {nao_encontrou} ({100*nao_encontrou/max(1,total_analisado):.1f}%)')

    if encontrou_data:
        print(f'\nDiferença entre data do e-mail e mês de competência:')
        print(f'  {"Diferença":>25}  {"Emails":>8}  {"% dos que têm data":>20}')
        print(f'  {SEP2[:55]}')
        for diff in sorted(diferenca_meses):
            n = diferenca_meses[diff]
            pct = 100 * n / encontrou_data
            label = {
                0: 'Mesmo mês',
                1: 'E-mail 1 mês depois',
                2: 'E-mail 2 meses depois',
                3: 'E-mail 3 meses depois',
               -1: 'E-mail 1 mês ANTES (antecipado)',
            }.get(diff, f'Diferença de {diff} meses')
            if pct >= 0.5 or abs(diff) <= 2:
                print(f'  {label:>25}  {n:>8}  {pct:>8.1f}%')

        print(f'\nExemplos de e-mails onde a data do e-mail é depois da competência:')
        for ex in exemplos_diff[:N_EXEMPLOS]:
            print(f'  [{ex["cat"]}] E-mail: {ex["data_email"]} | Competência: {ex["competencia"]} (+{ex["diff_meses"]} mês)')
            print(f'    Assunto: {ex["assunto"]}')

    # ── Datas disponíveis no J03 ──────────────────────────────────────────
    print(f'\n{SEP1}')
    print('CAMPOS DE DATA NO J03 (eventos do site)')
    print(SEP1)

    campos_data = set()
    for e in eventos[:50]:
        for k, v in vars(e).items() if hasattr(e, '__dict__') else []:
            if 'data' in k.lower() or 'date' in k.lower():
                campos_data.add(k)

    # Para PSCustomObject do PowerShell convertido
    ev0 = eventos[0]
    print(f'\nCampos disponíveis no primeiro evento J03:')
    if hasattr(ev0, '__dict__'):
        for k, v in vars(ev0).items():
            print(f'  {k}: {str(v)[:60]}')
    else:
        for k in dir(ev0):
            if not k.startswith('_'):
                try:
                    print(f'  {k}: {str(getattr(ev0, k))[:60]}')
                except Exception:
                    pass

    print(f'\n{SEP1}')
    print('FIM DA ANÁLISE')
    print(SEP1)


if __name__ == '__main__':
    main()
