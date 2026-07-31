"""
analisar_anexos_emails.py — analisa os anexos dos e-mails para definir as regras do Campo 7

Para que serve: responder as 4 questões pendentes do Campo 7 da especificação:
  Q1 — ZIP dentro de ZIP: existe? Em quais categorias?
  Q2 — E-mails com muitos anexos: qual a distribuição?
  Q3 — Nomes genéricos de anexo: quais são os mais comuns?
  Q4 — Tamanho de arquivos: qual o maior encontrado?

Fonte: oraculo_360_finaud — histórico completo de produção (8.825 e-mails)

Como usar:
  python scripts/consultas/analisar_anexos_emails.py
"""

import json
import re
import sys
import os
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

PROJETO_DADOS = r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud'
N_EXEMPLOS = 5

PATH_J01 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '01_extração_dados_brutos_gmail.json'
PATH_J03 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '03_integrador_dados_site.json'

# Pasta onde os anexos ficam salvos em disco
PATH_ANEXOS = Path(PROJETO_DADOS) / 'data' / 'attachments'

SEP1 = '=' * 70
SEP2 = '─' * 70

# Categorias que entram na triagem (excluindo filtrados)
CATS_TRIAGEM = {
    'DDR_2011', '4111', 'DRM_2060', 'DLO_2061', 'DLI_2062',
    'DRL_2160', 'S5', 'RETORNO_BACEN', 'SUPORTE', 'FORCAPITAL',
    'DRSAC', '6209'
}

# Padrão do ZIP do CADOC gerado (altíssima confiança)
PAD_ZIP_CADOC = re.compile(
    r'\d{8,14}_(?:2011|4111|2060|2061|2062|2160)_\d{6,8}.*\.zip$',
    re.IGNORECASE
)

# Nomes genéricos (sem pista de categoria)
NOMES_GENERICOS = re.compile(
    r'^(document[oa]|informaç[oõ]es|arquivo|dados|anexo|file|image|imagem'
    r'|planilha|relatorio|relat[oó]rio|sem.nome|untitled|noname'
    r'|image\d*\.(png|jpg|jpeg)|foto|screenshot)\b',
    re.IGNORECASE
)


def carregar_json(path):
    if not path.exists():
        print(f'ERRO: arquivo não encontrado → {path}')
        sys.exit(1)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    print(SEP1)
    print('ANÁLISE DE ANEXOS — Campo 7 da Especificação')
    print(SEP1)

    # ── Carregar dados ────────────────────────────────────────────────────────
    j01 = carregar_json(PATH_J01)
    j03 = carregar_json(PATH_J03)
    eventos = j03['eventos']

    # Mapa id → categoria
    id_para_cat = {str(e['id']): e['cadoc'] for e in eventos}

    # Filtrar só categorias de triagem
    emails = []
    for e in j01:
        cat = id_para_cat.get(str(e['id']), '')
        if cat in CATS_TRIAGEM:
            e['_categoria'] = cat
            emails.append(e)

    print(f'\nTotal de e-mails nas categorias de triagem: {len(emails)}')
    print(f'(de {len(j01)} e-mails totais no histórico)\n')

    # Só e-mails COM anexo
    com_anexo = [e for e in emails if e.get('anexos_detectados')]
    sem_anexo = [e for e in emails if not e.get('anexos_detectados')]

    print(f'Com anexo:  {len(com_anexo)} ({100*len(com_anexo)/len(emails):.1f}%)')
    print(f'Sem anexo:  {len(sem_anexo)} ({100*len(sem_anexo)/len(emails):.1f}%)')

    # ── Q2: Distribuição de quantidade de anexos por e-mail ───────────────────
    print(f'\n{SEP1}')
    print('Q2 — QUANTOS ANEXOS POR E-MAIL?')
    print(SEP1)

    contagem_anexos = Counter(len(e['anexos_detectados']) for e in com_anexo)
    total_com = len(com_anexo)

    print(f'\n{"Qtd anexos":<14} {"Emails":>8} {"% do total c/ anexo":>22}')
    print(SEP2)
    for n in sorted(contagem_anexos):
        pct = 100 * contagem_anexos[n] / total_com
        barra = '█' * int(pct / 2)
        print(f'{n:<14} {contagem_anexos[n]:>8}   {pct:>6.1f}%  {barra}')

    # Top e-mails com mais anexos
    top_muitos = sorted(com_anexo, key=lambda e: len(e['anexos_detectados']), reverse=True)[:N_EXEMPLOS]
    print(f'\nTop {N_EXEMPLOS} e-mails com mais anexos:')
    for e in top_muitos:
        nomes = [a['nome_original'] for a in e['anexos_detectados']]
        print(f'  [{e["_categoria"]}] {len(nomes)} anexos | assunto: {e["assunto"][:60]}')
        for n in nomes[:8]:
            print(f'    → {n}')
        if len(nomes) > 8:
            print(f'    ... (+{len(nomes)-8} mais)')

    # ── Q1: ZIP dentro de ZIP ─────────────────────────────────────────────────
    print(f'\n{SEP1}')
    print('Q1 — ZIP DENTRO DE ZIP')
    print(SEP1)

    # Emails que têm ZIP + outros arquivos (candidatos a terem ZIP aninhado)
    emails_com_zip = []
    for e in com_anexo:
        nomes = [a['nome_original'] for a in e['anexos_detectados']]
        zips = [n for n in nomes if n.lower().endswith('.zip')]
        if zips:
            emails_com_zip.append((e, zips, nomes))

    print(f'\nE-mails com pelo menos 1 ZIP: {len(emails_com_zip)} ({100*len(emails_com_zip)/total_com:.1f}% dos que têm anexo)')

    # Emails com múltiplos ZIPs (sinal de ZIP dentro de ZIP ou vários CADOCs)
    multiplos_zip = [(e, zips, nomes) for e, zips, nomes in emails_com_zip if len(zips) > 1]
    print(f'E-mails com 2+ ZIPs: {len(multiplos_zip)}')

    if multiplos_zip:
        print(f'\nExemplos de e-mails com múltiplos ZIPs:')
        for e, zips, nomes in multiplos_zip[:N_EXEMPLOS]:
            print(f'  [{e["_categoria"]}] {len(zips)} ZIPs | assunto: {e["assunto"][:60]}')
            for z in zips:
                padrao = 'CADOC' if PAD_ZIP_CADOC.search(z) else 'genérico'
                print(f'    → {z}  [{padrao}]')

    # ZIPs com nomes genéricos (não seguem padrão CADOC)
    zips_genericos = []
    for e, zips, nomes in emails_com_zip:
        for z in zips:
            if not PAD_ZIP_CADOC.search(z):
                zips_genericos.append((e['_categoria'], z, e['assunto']))

    print(f'\nZIPs com nome genérico (não seguem padrão CNPJ_CADOC_DATA): {len(zips_genericos)}')
    if zips_genericos:
        print(f'Exemplos (top {N_EXEMPLOS}):')
        for cat, nome, assunto in zips_genericos[:N_EXEMPLOS]:
            print(f'  [{cat}] {nome} | assunto: {assunto[:55]}')

    # Verificar se há ZIPs físicos em disco para checar aninhamento
    print(f'\nVerificação em disco (pasta attachments):')
    if PATH_ANEXOS.exists():
        zips_disco = list(PATH_ANEXOS.glob('*.zip'))
        print(f'  ZIPs encontrados em disco: {len(zips_disco)}')
        if zips_disco:
            # Tentar abrir alguns para verificar ZIP dentro de ZIP
            import zipfile
            zip_dentro_zip = []
            erros = 0
            for zf in zips_disco[:200]:  # checar amostra
                try:
                    with zipfile.ZipFile(zf) as z:
                        nomes_internos = z.namelist()
                        internos_zip = [n for n in nomes_internos if n.lower().endswith('.zip')]
                        if internos_zip:
                            zip_dentro_zip.append((zf.name, internos_zip))
                except Exception:
                    erros += 1
            print(f'  ZIPs verificados (amostra): {min(200, len(zips_disco))} | Erros ao abrir: {erros}')
            print(f'  ZIP dentro de ZIP encontrado: {len(zip_dentro_zip)}')
            for nome, internos in zip_dentro_zip[:5]:
                print(f'    {nome} → contém: {internos}')
    else:
        print(f'  Pasta não encontrada: {PATH_ANEXOS}')
        print('  → Análise de aninhamento físico não disponível. Usando só metadados.')

    # ── Q3: Nomes genéricos ───────────────────────────────────────────────────
    print(f'\n{SEP1}')
    print('Q3 — NOMES GENÉRICOS DE ANEXO')
    print(SEP1)

    todos_nomes = []
    for e in com_anexo:
        for a in e['anexos_detectados']:
            todos_nomes.append((e['_categoria'], a['nome_original'], a.get('tipo', ''), e['assunto']))

    total_nomes = len(todos_nomes)
    print(f'\nTotal de anexos analisados: {total_nomes}')

    # Extensões mais comuns
    ext_counter = Counter()
    for _, nome, _, _ in todos_nomes:
        ext = Path(nome).suffix.lower()
        ext_counter[ext] += 1

    print(f'\nExtensões mais comuns:')
    for ext, n in ext_counter.most_common(15):
        pct = 100 * n / total_nomes
        print(f'  {ext or "(sem extensão)":<20} {n:>6}  {pct:>6.1f}%')

    # Nomes sem pista de categoria
    genericos = [(cat, nome, ass) for cat, nome, _, ass in todos_nomes if NOMES_GENERICOS.match(nome)]
    print(f'\nAnexos com nome genérico (sem pista de categoria): {len(genericos)} ({100*len(genericos)/total_nomes:.1f}%)')

    if genericos:
        top_gen = Counter(nome for _, nome, _ in genericos)
        print(f'Nomes genéricos mais frequentes:')
        for nome, n in top_gen.most_common(10):
            print(f'  {nome:<45} {n:>5}x')

    # Por categoria: proporção de anexos genéricos
    print(f'\nAnexos genéricos por categoria:')
    gen_por_cat = defaultdict(int)
    total_por_cat = defaultdict(int)
    for cat, nome, _, _ in todos_nomes:
        total_por_cat[cat] += 1
        if NOMES_GENERICOS.match(nome):
            gen_por_cat[cat] += 1

    for cat in sorted(total_por_cat):
        t = total_por_cat[cat]
        g = gen_por_cat[cat]
        pct = 100 * g / t if t > 0 else 0
        print(f'  {cat:<20} {g:>4} de {t:>5} ({pct:>5.1f}%)')

    # ── Q4: Tamanho de arquivos ───────────────────────────────────────────────
    print(f'\n{SEP1}')
    print('Q4 — TAMANHO DOS ARQUIVOS EM DISCO')
    print(SEP1)

    if PATH_ANEXOS.exists():
        arquivos = list(PATH_ANEXOS.iterdir())
        tamanhos = []
        for arq in arquivos:
            try:
                tam = arq.stat().st_size
                tamanhos.append((tam, arq.name))
            except Exception:
                pass

        if tamanhos:
            tamanhos.sort(reverse=True)
            total_bytes = sum(t for t, _ in tamanhos)
            maior = tamanhos[0]
            print(f'\nTotal de arquivos em disco: {len(tamanhos)}')
            print(f'Tamanho total: {total_bytes/1024/1024:.1f} MB')
            print(f'Maior arquivo: {maior[1]} — {maior[0]/1024/1024:.2f} MB')

            # Distribuição por faixa
            faixas = {'< 100 KB': 0, '100 KB – 1 MB': 0, '1 MB – 10 MB': 0,
                      '10 MB – 50 MB': 0, '> 50 MB': 0}
            for tam, _ in tamanhos:
                kb = tam / 1024
                mb = kb / 1024
                if mb > 50:
                    faixas['> 50 MB'] += 1
                elif mb > 10:
                    faixas['10 MB – 50 MB'] += 1
                elif mb > 1:
                    faixas['1 MB – 10 MB'] += 1
                elif kb > 100:
                    faixas['100 KB – 1 MB'] += 1
                else:
                    faixas['< 100 KB'] += 1

            print(f'\nDistribuição por tamanho:')
            for faixa, n in faixas.items():
                pct = 100 * n / len(tamanhos)
                print(f'  {faixa:<20} {n:>6}  ({pct:.1f}%)')

            print(f'\nTop 10 maiores arquivos:')
            for tam, nome in tamanhos[:10]:
                print(f'  {tam/1024/1024:>8.2f} MB  {nome}')
        else:
            print('Nenhum arquivo encontrado em disco.')
    else:
        print(f'Pasta não encontrada: {PATH_ANEXOS}')
        print('→ Análise de tamanho não disponível com os dados atuais.')
        print()
        print('O que podemos inferir do histórico (sem acesso aos arquivos):')
        print('  - Arquivos Excel/CSV (DDR, DRM, DLO, DLI): tipicamente < 5 MB')
        print('  - ZIPs CADOC gerados pela Finaud: tipicamente < 2 MB')
        print('  - PDFs de comunicados do BACEN: tipicamente < 1 MB')
        print('  - XMLs COSIF: tipicamente < 500 KB')

    print(f'\n{SEP1}')
    print('FIM DA ANÁLISE')
    print(SEP1)


if __name__ == '__main__':
    main()
