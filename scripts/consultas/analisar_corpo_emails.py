"""
analisar_corpo_emails.py — analisa o que tem dentro do texto dos e-mails de uma categoria

Para que serve: mapear os elementos do Passo 3 (Campo 6 da especificação) em cada
categoria. Roda em cima dos dados reais de produção e mostra: quantos e-mails têm cada
elemento + exemplos do que detectou + exemplos do que NÃO detectou (para validar).

Como usar:
  1. Alterar PROJETO_DADOS para apontar ao projeto certo (ver projetos abaixo)
  2. Alterar CADOC_FILTRO para a categoria desejada (ver tabela abaixo)
  3. Rodar: python scripts/consultas/analisar_corpo_emails.py
  4. Comparar o total de e-mails com o número conhecido da categoria

Projetos disponíveis (onde estão os dados reais):
  oraculo_360_finaud      → D:\\02_Finaud\\Projetos\\ativos\\oraculo_360_finaud
                            (fonte principal — histórico completo, ~4.786 threads)
  oraculo_360_finaud_TESTE→ confirmar caminho (dados de 03/07 com e-mails individuais via BBC)
  gestao_area_suporte     → NÃO usar (só amostra de teste, ~36 threads)

Filtros por categoria:
  DDR_2011     → '2011'       SCD_4111  → '4111'
  DRM_2060     → '2060'       DLO_2061  → '2061'
  DLI_2062     → '2062'       DRL_2160  → '2160'
  S5           → 'S5'         SUPORTE   → 'SUPORTE'
  RETORNO_BACEN→ 'RETORNO'    FORCAPITAL→ 'FORCAPITAL'
  DRSAC_2030   → 'DRSAC'      PVCA_6209 → '6209'
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# ─── Configurar aqui ──────────────────────────────────────────────────────────
PROJETO_DADOS = r'D:\02_Finaud\Projetos\ativos\oraculo_360_finaud'
CADOC_FILTRO  = '6209'   # mudar para cada categoria (ver tabela no topo)
N_EXEMPLOS    = 3        # quantos exemplos mostrar por elemento (detectados + não detectados)
# ─────────────────────────────────────────────────────────────────────────────

PATH_J03 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '03_integrador_dados_site.json'
PATH_J01 = Path(PROJETO_DADOS) / 'data' / 'json' / 'pipeline' / '01_extração_dados_brutos_gmail.json'

SEP1 = '=' * 70
SEP2 = '─' * 70


# ─── Utilitários ──────────────────────────────────────────────────────────────

def carregar_json(path):
    """Carrega JSON — aceita lista direta ou objeto com chave 'data'/'emails'/'threads'."""
    if not path.exists():
        print(f'ERRO: arquivo não encontrado → {path}')
        sys.exit(1)
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    if isinstance(d, list):
        return d
    for chave in ('data', 'emails', 'threads'):
        if chave in d:
            return d[chave]
    return list(d.values())[0] if d else []


def tem_html(texto):
    """Detecta se o texto contém tags HTML."""
    return bool(re.search(r'<(html|div|br|p|span|table|td|tr|body)\b', texto or '', re.IGNORECASE))


def trecho_ao_redor(texto, padrao_re, chars_antes=50, chars_depois=150):
    """Retorna o trecho do texto em volta do padrão detectado."""
    m = padrao_re.search(texto or '')
    if not m:
        return (texto or '').strip()[:200].replace('\n', ' | ')
    inicio = max(0, m.start() - chars_antes)
    fim    = min(len(texto), m.end() + chars_depois)
    prefixo = '...' if inicio > 0 else ''
    sufixo  = '...' if fim < len(texto) else ''
    trecho = texto[inicio:fim].strip().replace('\n', ' | ')
    return f'{prefixo}{trecho}{sufixo}'


def trecho_inicio(texto, max_chars=200):
    """Retorna o início do texto (para os não detectados)."""
    return (texto or '').strip()[:max_chars].replace('\n', ' | ')


# ─── Carregar dados ───────────────────────────────────────────────────────────

print(f'Carregando JSON03...')
j03 = carregar_json(PATH_J03)
threads_cat = [t for t in j03 if CADOC_FILTRO in str(t.get('cadoc') or '')]
ids_cat = {t.get('threadId') for t in threads_cat}

print(f'Carregando JSON01...')
j01 = carregar_json(PATH_J01)
emails_cat = [e for e in j01 if e.get('x_gm_thrid') in ids_cat]


# ─── Validação de total ───────────────────────────────────────────────────────

print()
print(SEP1)
print(f'ANÁLISE DO CORPO DOS E-MAILS — categoria contém "{CADOC_FILTRO}"')
print(SEP1)
print(f'  Threads na categoria : {len(ids_cat):>6}')
print(f'  E-mails encontrados  : {len(emails_cat):>6}  ← conferir com o total conhecido')
print()

if not emails_cat:
    print('ERRO: nenhum e-mail encontrado — verificar CADOC_FILTRO')
    sys.exit(1)

total = len(emails_cat)


# ─── Passo 1 — formato de entrega ────────────────────────────────────────────

html_count  = sum(1 for e in emails_cat if tem_html(e.get('corpo') or ''))
texto_count = total - html_count
sem_corpo   = sum(1 for e in emails_cat if not (e.get('corpo') or '').strip())
sem_ct      = sum(1 for e in emails_cat if not (e.get('corpo_texto') or '').strip())

print(SEP2)
print('PASSO 1 — FORMATO DE ENTREGA')
print(SEP2)
print(f'  HTML (campo "corpo")         : {html_count:>6}  ({html_count/total*100:.1f}%)')
print(f'  Texto puro (campo "corpo")   : {texto_count:>6}  ({texto_count/total*100:.1f}%)')
print(f'  Corpo vazio                  : {sem_corpo:>6}  ({sem_corpo/total*100:.1f}%)')
print(f'  corpo_texto vazio            : {sem_ct:>6}  ({sem_ct/total*100:.1f}%)')
print()


# ─── Passo 3 — detecção de elementos ─────────────────────────────────────────

def analisar_elemento(nome, emails, detector_fn, padrao_re=None, n=N_EXEMPLOS):
    """
    Para um elemento do Passo 3:
    - conta quantos e-mails têm
    - mostra N exemplos detectados com contexto em volta do padrão
    - mostra N exemplos NÃO detectados (início do texto)
    Retorna a quantidade detectada.
    """
    detectados     = [e for e in emails if detector_fn(e.get('corpo_texto') or '')]
    nao_detectados = [e for e in emails if not detector_fn(e.get('corpo_texto') or '')]
    qtd = len(detectados)

    print(SEP2)
    print(f'ELEMENTO: {nome}')
    print(SEP2)
    print(f'  Detectado em: {qtd}/{total}  ({qtd/total*100:.1f}%)')
    print()

    # Exemplos detectados — com contexto ao redor do padrão
    n_det = min(n, qtd)
    print(f'  EXEMPLOS DETECTADOS ({n_det} de {qtd}):')
    if not detectados:
        print('     (nenhum)')
    for e in detectados[:n]:
        txt = e.get('corpo_texto') or ''
        ctx = trecho_ao_redor(txt, padrao_re) if padrao_re else trecho_inicio(txt)
        print(f'     assunto  : {str(e.get("assunto") or "")[:70]}')
        print(f'     contexto : {ctx}')
        print()

    # Exemplos não detectados — início do texto para checar se deveria ter sido detectado
    n_nd = min(n, len(nao_detectados))
    print(f'  EXEMPLOS NAO DETECTADOS ({n_nd} de {len(nao_detectados)}):')
    if not nao_detectados:
        print('     (todos foram detectados)')
    for e in nao_detectados[:n]:
        txt = e.get('corpo_texto') or ''
        print(f'     assunto  : {str(e.get("assunto") or "")[:70]}')
        print(f'     inicio   : {trecho_inicio(txt)}')
        print()

    return qtd


# Padrões de detecção — ajustados com base na análise do DDR_2011
PAD_ASSINATURA = re.compile(
    r'(?m)^\s*(att[,.\s]|atenciosamente|à disposição|a disposição'
    r'|cordialmente|desde já agradeço|antecipadamente grat'
    r'|obrigad[ao]\b|abs[,.\s]|abraços'
    r'|regards\b|best regards|kind regards|sincerely\b|cheers\b|best\s*,|thanks\s*,|thank you\s*,'
    r'|grat[ao][s]?[,\.\s])',
    re.IGNORECASE | re.MULTILINE
)

# Padrão auxiliar: nome próprio (para bloco nome+cargo no final)
_PAD_NOME_PROPRIO = re.compile(
    r'^[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][a-záéíóúàâêôãõç]+'
    r'(?:[ ](?:de |da |do |dos |das )?[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][a-záéíóúàâêôãõç]+){1,4}$',
    re.UNICODE
)

def tem_bloco_nome_final(texto, n_ultimas=15):
    """
    Detecta bloco nome+cargo no final do e-mail sem palavra de fechamento.
    Condições: linha em branco + linha que parece nome próprio + linha curta depois.

    Estratégia: corta o rodapé automático antes de procurar (no DDR o rodapé Google Groups
    fica depois da assinatura, empurrando-a para fora das últimas N linhas sem o corte).
    """
    # Cortar no rodapé automático para expor a assinatura que vem antes
    for marcador in ('To unsubscribe from this group',
                     'para cancelar a inscrição',
                     'você está recebendo este e-mail porque se inscreveu'):
        pos = texto.lower().find(marcador.lower())
        if pos != -1:
            texto = texto[:pos]

    linhas = texto.strip().split('\n')
    bloco = [l.rstrip() for l in (linhas[-n_ultimas:] if len(linhas) > n_ultimas else linhas)]
    for i in range(len(bloco) - 2):
        if bloco[i].strip() == '':
            prox = bloco[i + 1].strip()
            if _PAD_NOME_PROPRIO.match(prox) and 4 <= len(prox) <= 45:
                for j in range(i + 2, min(i + 5, len(bloco))):
                    seguinte = bloco[j].strip()
                    if seguinte and len(seguinte) <= 60:
                        return True
    return False

def det_assinatura(texto):
    return bool(PAD_ASSINATURA.search(texto)) or tem_bloco_nome_final(texto)

PAD_CITADO = re.compile(r'(?m)^>', re.MULTILINE)

PAD_ENCAMINHADO = re.compile(
    # Traços/underscores/iguais só disparam quando seguidos de cabeçalho de e-mail na próxima linha
    # (evita falso positivo em separadores decorativos dentro do corpo — encontrado no S5)
    r'(?:-{5,}|_{5,}|={5,})\s*\n\s*(?:de:|from:|para:|to:|data:|date:|enviado\s*em:|sent:)'
    r'|forwarded message|mensagem encaminhada'
    r'|begin forwarded|de:\s+\S+@\S+\s+enviado em:|from:\s+\S+@\S+\s+sent:',
    re.IGNORECASE
)

PAD_RODAPE = re.compile(
    r'(?i)(to unsubscribe from this group|para cancelar a inscrição'
    r'|você está recebendo este e-mail porque se inscreveu'
    r'|this message was sent to|if you no longer wish to receive)',
    re.IGNORECASE
)

PAD_IMG_IMAGE = re.compile(r'\[image:', re.IGNORECASE)
PAD_IMG_CID   = re.compile(r'\[cid:', re.IGNORECASE)


print()
print(SEP1)
print('PASSO 3 — ELEMENTOS NO TEXTO DOS E-MAILS (campo "corpo_texto")')
print(SEP1)
print()

qtd_assin  = analisar_elemento('Assinatura',                  emails_cat, det_assinatura,                         PAD_ASSINATURA)
qtd_citado = analisar_elemento('Historico citado (>)',         emails_cat, lambda t: bool(PAD_CITADO.search(t)),       PAD_CITADO)
qtd_encam  = analisar_elemento('Historico encaminhado (---)',  emails_cat, lambda t: bool(PAD_ENCAMINHADO.search(t)),  PAD_ENCAMINHADO)
qtd_rodape = analisar_elemento('Rodape automatico',            emails_cat, lambda t: bool(PAD_RODAPE.search(t)),       PAD_RODAPE)
qtd_img_i  = analisar_elemento('[image: ...]',                 emails_cat, lambda t: bool(PAD_IMG_IMAGE.search(t)),   PAD_IMG_IMAGE)
qtd_img_c  = analisar_elemento('[cid: ...]',                   emails_cat, lambda t: bool(PAD_IMG_CID.search(t)),     PAD_IMG_CID)


# ─── Resumo ───────────────────────────────────────────────────────────────────

print()
print(SEP1)
print(f'RESUMO — categoria "{CADOC_FILTRO}" ({total} e-mails)')
print(SEP1)
print(f'  {"Elemento":<38} {"Qtd":>6}  {"% emails":>8}  Barra')
print(f'  {"-"*38} {"-"*6}  {"-"*8}  {"-"*20}')

for nome, qtd in [
    ('Assinatura',                 qtd_assin),
    ('Historico citado (>)',        qtd_citado),
    ('Historico encaminhado (---)', qtd_encam),
    ('Rodape automatico',           qtd_rodape),
    ('[image: ...]',                qtd_img_i),
    ('[cid: ...]',                  qtd_img_c),
]:
    pct = qtd / total * 100
    barra = '#' * int(pct / 5)  # cada # = 5%
    print(f'  {nome:<38} {qtd:>6}  ({pct:>6.1f}%)  {barra}')

print()
print(SEP2)
print('COMO VALIDAR OS RESULTADOS:')
print('  1. Total bate com o numero conhecido da categoria?')
print('     Se nao: o filtro CADOC_FILTRO pode estar errado.')
print('  2. Exemplos DETECTADOS fazem sentido?')
print('     Se nao: o padrao esta capturando coisa errada (falso positivo).')
print('  3. Exemplos NAO DETECTADOS deveriam ter sido capturados?')
print('     Se sim: falta variacao no padrao (falso negativo).')
print('  Ajustar os PAD_* no topo do script e rodar de novo.')
print(SEP2)
