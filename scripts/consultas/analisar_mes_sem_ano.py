"""
analisar_mes_sem_ano.py — testa a inferência de ano quando o assunto tem só o mês

Hipótese: quando o assunto diz "DEZEMBRO" sem ano, a IA usa a data do e-mail como
âncora para inferir o ano correto.

Regra testada:
  - Mês mencionado < mês do e-mail → ano do e-mail
  - Mês mencionado = mês do e-mail → ano do e-mail
  - Mês mencionado > mês do e-mail → ano anterior

Validação: compara a inferência com a data que aparece nos nomes dos anexos
(que quase sempre têm o ano explícito).
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter
from email.utils import parsedate_to_datetime
from datetime import timezone

sys.stdout.reconfigure(encoding='utf-8')

PROJETO_DADOS = r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud'
PATH_J01 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '01_extração_dados_brutos_gmail.json'
PATH_J03 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '03_integrador_dados_site.json'

SEP = '=' * 70

CATS_TRIAGEM = {
    'DDR_2011', '4111', 'DRM_2060', 'DLO_2061', 'DLI_2062',
    'DRL_2160', 'S5', 'RETORNO_BACEN', 'SUPORTE', 'FORCAPITAL', 'DRSAC', '6209'
}

MESES_PT = {
    'janeiro':1, 'fevereiro':2, 'março':3, 'marco':3, 'abril':4,
    'maio':5, 'junho':6, 'julho':7, 'agosto':8, 'setembro':9,
    'outubro':10, 'novembro':11, 'dezembro':12,
    'jan':1, 'fev':2, 'mar':3, 'abr':4, 'mai':5, 'jun':6,
    'jul':7, 'ago':8, 'set':9, 'out':10, 'nov':11, 'dez':12,
}

# Detecta mês POR EXTENSO ou abreviado sem ano junto
PAD_MES_SEM_ANO = re.compile(
    r'\b(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|'
    r'outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\b'
    r'(?!\s*[/\-\.]\s*\d{2,4})',
    re.IGNORECASE
)

# Detecta data COM ano (MM/YYYY, MM-YYYY, YYYY/MM, YYYYMMDD nos anexos etc.)
PAD_COM_ANO = re.compile(
    r'\b(\d{2})[/\-\.](\d{4})\b'          # MM/YYYY
    r'|\b(\d{4})[/\-\.](\d{2})\b'          # YYYY/MM
    r'|\b(\d{4})(\d{2})\d{2}\b'            # YYYYMMDD (em nomes de arquivo)
    r'|\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[^\d]*(\d{4})\b', re.I
)


def parse_data(raw):
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
    except Exception:
        return None


def extrair_mes_com_ano(texto):
    """Extrai (ano, mês) de um texto que tem data completa."""
    for m in PAD_COM_ANO.finditer(texto):
        g = m.groups()
        try:
            if g[0] and g[1]:          # MM/YYYY
                return (int(g[1]), int(g[0]))
            if g[2] and g[3]:          # YYYY/MM
                return (int(g[2]), int(g[3]))
            if g[4] and g[5]:          # YYYYMMDD
                return (int(g[4]), int(g[5]))
            if g[6] and g[7]:          # jan/YYYY
                return (int(g[7]), MESES_PT.get(g[6].lower(), 0))
        except Exception:
            pass
    return None


def inferir_ano(mes_mencionado, data_email):
    """Regra de inferência: mês + data do e-mail → (ano, mês) provável."""
    m_email = data_email.month
    a_email = data_email.year
    if mes_mencionado <= m_email:
        return (a_email, mes_mencionado)
    else:
        return (a_email - 1, mes_mencionado)


def main():
    print(SEP)
    print('TESTE — INFERÊNCIA DE ANO QUANDO ASSUNTO TEM SÓ O MÊS')
    print(SEP)

    j01 = json.loads(PATH_J01.read_text(encoding='utf-8'))
    j03 = json.loads(PATH_J03.read_text(encoding='utf-8'))

    id_para_cat = {str(e['id']): e['cadoc'] for e in j03['eventos']}

    candidatos = []
    for e in j01:
        cat = id_para_cat.get(str(e['id']), '')
        if cat not in CATS_TRIAGEM:
            continue
        assunto = e.get('assunto', '')
        data_email = parse_data(e.get('data_email', ''))
        if not data_email:
            continue

        # Verifica se o assunto tem mês por extenso SEM ano
        m = PAD_MES_SEM_ANO.search(assunto)
        if not m:
            continue

        # Garante que não há data completa no assunto
        if PAD_COM_ANO.search(assunto):
            continue

        mes_nome = m.group(1).lower()
        mes_num = MESES_PT.get(mes_nome, 0)
        if not mes_num:
            continue

        # Tenta encontrar data com ano nos anexos (ground truth)
        data_confirmada = None
        for anx in (e.get('anexos_detectados') or []):
            nome = anx.get('nome_original', '')
            comp = extrair_mes_com_ano(nome)
            if comp:
                data_confirmada = comp
                break

        # Aplica a inferência
        inferido = inferir_ano(mes_num, data_email)

        candidatos.append({
            'cat':            cat,
            'assunto':        assunto,
            'data_email':     data_email,
            'mes_nome':       mes_nome,
            'mes_num':        mes_num,
            'inferido':       inferido,
            'confirmado':     data_confirmada,
            'tem_gt':         data_confirmada is not None,
        })

    print(f'\nE-mails com assunto "mês sem ano": {len(candidatos)}')

    # Avaliação onde temos ground-truth (data confirmada pelo anexo)
    com_gt = [c for c in candidatos if c['tem_gt']]
    print(f'Com data confirmada no anexo (ground truth): {len(com_gt)}')

    acertos = sum(1 for c in com_gt if c['inferido'] == c['confirmado'])
    erros   = [c for c in com_gt if c['inferido'] != c['confirmado']]

    if com_gt:
        print(f'\nResultado da inferência:')
        print(f'  ✅ Acertos: {acertos} de {len(com_gt)} ({100*acertos/len(com_gt):.1f}%)')
        print(f'  ❌ Erros:   {len(erros)}')

    if erros:
        print(f'\n--- CASOS EM QUE A INFERÊNCIA ERROU ---')
        for c in erros:
            print(f'\n  [{c["cat"]}] Assunto: {c["assunto"]}')
            print(f'  Data e-mail:  {c["data_email"].strftime("%d/%m/%Y")}')
            print(f'  Mês no assunto: {c["mes_nome"]}')
            print(f'  Inferido:     {c["inferido"][1]:02d}/{c["inferido"][0]}')
            print(f'  Correto:      {c["confirmado"][1]:02d}/{c["confirmado"][0]}')

    # Mostrar todos os casos — mesmo sem ground truth
    print(f'\n--- TODOS OS CASOS COM MÊS SEM ANO ---')
    print(f'{"#":>3}  {"Cat":<15} {"Data e-mail":>12}  {"Mês no assunto":>15}  {"Inferido":>10}  {"Confirmado":>12}  Assunto')
    print('─' * 110)
    for i, c in enumerate(candidatos, 1):
        gt = f'{c["confirmado"][1]:02d}/{c["confirmado"][0]}' if c['tem_gt'] else '(sem GT)'
        inf = f'{c["inferido"][1]:02d}/{c["inferido"][0]}'
        ok = '✅' if c['tem_gt'] and c['inferido'] == c['confirmado'] else ('❌' if c['tem_gt'] else '  ')
        print(f'{i:>3}  {c["cat"]:<15} {c["data_email"].strftime("%d/%m/%Y"):>12}  '
              f'{c["mes_nome"]:>15}  {inf:>10}  {gt:>12}  {ok} {c["assunto"][:50]}')

    print(f'\n{SEP}')
    print('FIM')
    print(SEP)


if __name__ == '__main__':
    main()
