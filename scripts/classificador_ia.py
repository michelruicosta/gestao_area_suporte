"""
classificador_ia.py
O que faz: recebe uma thread (formato do coletor_gmail.py) e classifica
           em uma ou mais categorias do §10 usando GPT como motor.
Entrada:   thread dict com mensagens[], assunto, etc.
Saída:     { categorias, confianca, motivo, incerto }

Modelo atual: gpt-4o-mini (OpenAI)
Para trocar de modelo: alterar a constante MODELO abaixo.
"""

import os
import json
import re

from dotenv import load_dotenv
from openai import OpenAI

try:
    import pytesseract
    from PIL import Image as _PILImage
    _OCR_DISPONIVEL = True
except ImportError:
    _OCR_DISPONIVEL = False

load_dotenv()

MODELO = 'gpt-4o-mini'

# ── Caminhos ──────────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_SPEC  = os.path.join(BASE_DIR, 'documentações', 'ESPECIFICACAO_NOVA_ARQUITETURA.md')
CAMINHO_GAB   = os.path.join(BASE_DIR, 'documentações', 'gabarito.json')
PASTA_ANEXOS     = os.path.join(BASE_DIR, 'data', 'email_anexos')
ARQUIVO_REGISTRO = os.path.join(BASE_DIR, 'data', 'registro_definitivo_threads.json')


# ── Extração do §10 do arquivo de spec ────────────────────────────────────────

def _extrair_secao10(caminho: str) -> str:
    with open(caminho, encoding='utf-8') as f:
        conteudo = f.read()
    m = re.search(
        r'(## 10\. Catálogo de categorias.*?)(?=## 11\.)',
        conteudo, re.DOTALL
    )
    if not m:
        raise RuntimeError('Seção §10 não encontrada na spec. Verifique o arquivo.')
    return m.group(1).strip()


# ── Gabarito (few-shot examples) ──────────────────────────────────────────────

def _formatar_gabarito(caminho: str) -> str:
    """Lê gabarito.json (v2) e formata regras + gabaritos para o prompt."""
    try:
        with open(caminho, encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        return ''

    regras    = dados.get('regras', [])
    gabaritos = dados.get('gabaritos', [])
    if not regras and not gabaritos:
        return ''

    def _cat_principal(entrada: dict) -> str:
        cats = entrada.get('categorias', [])
        return cats[0] if cats else ''

    linhas = [
        '## Regras confirmadas — aplicar sempre que o padrão aparecer',
        '',
        'Estas regras foram validadas por especialistas.',
        'O assunto determina a categoria; o corpo não muda a decisão.',
        '',
    ]
    por_cat_reg: dict[str, list] = {}
    for r in regras:
        por_cat_reg.setdefault(_cat_principal(r), []).append(r)

    for cat in sorted(por_cat_reg):
        linhas.append(f'**{cat}:**')
        for r in por_cat_reg[cat]:
            rid      = r.get('id', '')
            padrao   = r.get('padrao', '')
            instrucao = r.get('instrucao', '')
            excecao  = r.get('excecao', '')
            linhas.append(f'• [{rid}]')
            linhas.append(f'  Padrão: {padrao}')
            linhas.append(f'  Instrução: {instrucao}')
            if excecao:
                linhas.append(f'  Exceção: {excecao}')
        linhas.append('')

    linhas += [
        '---',
        '',
        '## Gabaritos — exemplos para casos ambíguos',
        '',
        'Use quando a regra não for suficiente para decidir com confiança.',
        '',
    ]
    por_cat_gab: dict[str, list] = {}
    for g in gabaritos:
        por_cat_gab.setdefault(_cat_principal(g), []).append(g)

    for cat in sorted(por_cat_gab):
        linhas.append(f'**{cat}:**')
        for g in por_cat_gab[cat]:
            gid    = g.get('id', '')
            assunto = g.get('assunto_exemplo', '')
            por_que = g.get('por_que_gabarito', '')
            cats_g  = g.get('categorias', [cat])
            cat_str = ', '.join(cats_g)
            linhas.append(f'• [{gid}] "{assunto}" → {cat_str}')
            linhas.append(f'  Por quê: {por_que}')
        linhas.append('')

    return '\n'.join(linhas)


# ── OCR ───────────────────────────────────────────────────────────────────────

def buscar_imagens(indice: int) -> list:
    """
    Retorna caminhos das imagens salvas para a thread de índice `indice`.
    Convenção: arquivos em PASTA_ANEXOS com nome '{indice}_*'.
    """
    if not os.path.isdir(PASTA_ANEXOS):
        return []
    prefix = f'{indice}_'
    exts   = {'.png', '.jpg', '.jpeg'}
    imgs   = [
        os.path.join(PASTA_ANEXOS, arq)
        for arq in os.listdir(PASTA_ANEXOS)
        if arq.startswith(prefix) and os.path.splitext(arq)[1].lower() in exts
    ]
    return sorted(imgs)


def _extrair_texto_ocr(caminhos: list) -> str:
    """
    Extrai texto das imagens via OCR.
    Ignora imagens que retornam menos de 30 chars (logos, assinaturas de e-mail).
    Retorna string vazia se OCR não estiver disponível ou não extrair nada útil.
    """
    if not _OCR_DISPONIVEL or not caminhos:
        return ''
    partes = []
    for caminho in caminhos[:4]:
        try:
            img   = _PILImage.open(caminho)
            texto = pytesseract.image_to_string(img, lang='por+eng').strip()
            if len(texto) >= 30:
                partes.append(texto)
        except Exception:
            pass
    return '\n\n'.join(partes)


# ── Normalização de nomes de categoria ───────────────────────────────────────
# A IA às vezes retorna o nome legível ("Saldos Contábeis Diários 4111") ao invés
# do código canônico. Este mapa corrige variações conhecidas.
_NORM_CATEGORIAS: dict[str, str] = {
    'Saldos Contábeis Diários 4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'saldos contábeis diários 4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'SALDOS CONTABEIS DIARIOS 4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'Saldos_Contabeis_Diarios_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'Saldos_CONTABEIS_DIARIOS_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'SALTOS_CONTABEIS_DIARIOS_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'Saltos_Contabeis_Diarios_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
}


# ── Registro definitivo — consulta antes de chamar o GPT ─────────────────────
# Threads confirmadas retornam o resultado salvo sem chamar o GPT.
# O cache é carregado uma vez por processo (lazy load); nunca altera o arquivo.

_REGISTRO_CACHE: dict | None = None


def _carregar_registro() -> dict:
    global _REGISTRO_CACHE
    if _REGISTRO_CACHE is None:
        if os.path.isfile(ARQUIVO_REGISTRO):
            with open(ARQUIVO_REGISTRO, encoding='utf-8') as f:
                _REGISTRO_CACHE = json.load(f)
        else:
            _REGISTRO_CACHE = {'threads': {}}
    return _REGISTRO_CACHE


# ── Sistema (construído uma vez ao carregar o módulo) ─────────────────────────

_SECAO10 = _extrair_secao10(CAMINHO_SPEC)
_GAB     = _formatar_gabarito(CAMINHO_GAB)
_GAB_SECAO = f'\n\n---\n\n{_GAB}' if _GAB else ''

_SISTEMA = f"""Você é o classificador de e-mails regulatórios do sistema Oráculo 360 da Finaud.

Sua função: dado um e-mail, identificar em qual(is) categoria(s) ele pertence com base \
nas regras abaixo.

{_SECAO10}{_GAB_SECAO}

---

## Instruções de classificação

- Um e-mail pode pertencer a mais de uma categoria (ex.: DLO + DLI no mesmo assunto). \
Liste todas.
- Use SUPORTE apenas quando nenhuma categoria CADOC for identificada no assunto, corpo \
ou nome dos anexos.
- Categorias válidas (use exatamente esses nomes):
  DDR_2011, SALDOS_CONTABEIS_DIARIOS_4111, DRM_2060, DLO_2061, DLI_2062, DRL_2160, S5,
  RETORNO_BACEN, FORCAPITAL, DRSAC_2030, PVCA_6209, SUPORTE

## Regras de prioridade — aplique nesta ordem

1. RETORNO_BACEN primeiro: quando o e-mail (no assunto, corpo ou histórico citado) \
mencionar que o BACEN criticou, rejeitou ou notificou um problema sobre uma entrega \
regulatória nossa — palavras-chave: "inconsistência", "aviso de atraso", "crítica", \
"indício de problema de qualidade" — classifique como RETORNO_BACEN. O remetente não \
importa: pode ser o próprio cliente encaminhando a mensagem do BACEN. Não combine \
com CADOC.

2. CADOC quando houver sinal: sinal de CADOC é qualquer referência à entrega de \
relatório regulatório — especificamente: números de CADOC (2011, 4111, 2060, 2061, \
2062, 2160), siglas (DDR, DRM, DLO, DLI, DRL, S5), frases-chave ("saldos contábeis"), \
nomes de formulários (COS4010, COS4016, EXTRATO COMPROMISSADA, PCAM, TVM, LEC) ou \
padrões de arquivo definidos no §10 acima. Se existir qualquer desses sinais → \
classifique pelo CADOC. Nunca adicione SUPORTE junto.
   Regra COS4010/COS4016: esses formulários servem a DLO e DLI. Sem menção explícita \
a 2061 ou 2062 → DLO_2061. Com ambos juntos (COS4010 + COS4016) → DLO_2061 + DLI_2062. \
Se 2062 ou "DLI" for explicitamente mencionado → DLI_2062 (ou DLO_2061 + DLI_2062).

3. SUPORTE como padrão final: sem sinal de CADOC e sem conteúdo de RETORNO_BACEN → \
classifique como SUPORTE. Nunca retorne INCERTO apenas porque não encontrou CADOC. \
Use INCERTO somente quando houver sinal de CADOC mas não for possível determinar qual \
categoria com confiança.
   Palavras regulatórias genéricas — "BACEN", "basileia", "instrução normativa", \
"limite operacional", "capital", "PLD/CFT", "risco de liquidez", "LCR", "senha", \
"acesso", "usuário", "permissão", "login", "reset", "mailing", "comunicado", \
"visita", "agendamento" — sem menção a número \
de CADOC (2011, 4111, 2060, 2061, 2062, 2160) ou sigla específica (DDR, DRM, DLO, \
DLI, DRL, S5) não são sinais de CADOC. Classifique como SUPORTE diretamente — \
nunca como INCERTO quando a única razão de dúvida são essas palavras genéricas.

## Formato de resposta — JSON válido com esta estrutura exata:

{{
  "categorias": ["CATEGORIA"],
  "confianca": "alta",
  "motivo": "explicação curta em português",
  "incerto": false,
  "gabarito_usado": "DDR - Regra 01 - EXTRATO COMPROMISSADA",
  "orientacao": null
}}

- "gabarito_usado": ID da regra ou gabarito que fundamentou a decisão. \
Use null quando a classificação vier diretamente das regras do §10.
- "orientacao": use null quando classificar com sucesso. \
Preencha APENAS quando "incerto": true ou "categorias": [] — explique o que precisaria \
estar no e-mail (assunto, corpo ou anexo) para você classificar com confiança.

Se não conseguir classificar com confiança suficiente, retorne:
{{
  "categorias": [],
  "confianca": "baixa",
  "motivo": "o que você viu no e-mail que gerou a dúvida",
  "incerto": true,
  "gabarito_usado": null,
  "orientacao": "o que precisaria estar no e-mail para você classificar com certeza"
}}

Exemplos de orientacao bem preenchida:
- Se o assunto ou corpo mencionasse o número do CADOC (2011, 2060, 2061...) ou a sigla \
(DDR, DRM, DLO), eu classificaria diretamente.
- O e-mail menciona erro no DRM mas não está claro se houve rejeição do BACEN. Se o \
histórico mencionasse inconsistência ou aviso de atraso, eu classificaria como RETORNO_BACEN."""


# ── Classificação ──────────────────────────────────────────────────────────────

def classificar_thread(thread: dict, cliente: OpenAI = None,
                       imagens: list = None) -> dict:
    """
    Classifica uma thread em uma ou mais categorias do §10.

    Parâmetros
    ----------
    thread  : dict no formato do coletor_gmail.py
    cliente : instância do openai.OpenAI (opcional — cria uma se não passada)
    imagens : lista de caminhos de imagens da thread (opcional).
              Quando fornecida, o texto extraído via OCR é incluído no prompt.
              Use buscar_imagens(indice) para obter os caminhos.

    Retorna
    -------
    {
      "categorias"    : list[str],        ex.: ["DDR_2011"] ou ["DLO_2061", "DLI_2062"]
      "confianca"     : str,              "alta" | "media" | "baixa"
      "motivo"        : str,              explicação em português
      "incerto"       : bool
      "gabarito_usado": str | None,       ID do gabarito que embasou a decisão, ou None
    }
    """
    # Threads com status_regra "confirmada" no registro não chamam o GPT.
    thread_id = thread.get('thread_id', '')
    if thread_id:
        reg    = _carregar_registro()
        entrada = reg.get('threads', {}).get(thread_id)
        if entrada and entrada.get('status_regra') == 'confirmada':
            return {
                'categorias':     entrada.get('categorias', []),
                'confianca':      'alta',
                'motivo':         f'Confirmada via {entrada.get("regra_usada", "registro")}',
                'incerto':        False,
                'gabarito_usado': entrada.get('regra_usada'),
            }

    if cliente is None:
        cliente = OpenAI()

    mensagens = thread.get('mensagens', [])
    assunto   = thread.get('assunto', '')

    # Lê até 3 mensagens da thread para dar contexto completo à IA.
    # A primeira mensagem inclui anexos; as demais só remetente + corpo.
    partes = []
    for i, msg in enumerate(mensagens[:3], start=1):
        rem  = msg.get('remetente', '')[:80]
        corp = msg.get('corpo_texto', '')[:300]
        anx  = msg.get('nomes_anexos', [])
        if i == 1:
            lista_anx = ', '.join(anx) if anx else '(nenhum)'
            partes.append(
                f"De: {rem}\nAnexos: {lista_anx}\n\n{corp}"
            )
        else:
            partes.append(f"--- Mensagem {i} ---\nDe: {rem}\n\n{corp}")

    email_texto = f"Assunto: {assunto}\n\n" + "\n\n".join(partes)

    # Acrescenta texto OCR das imagens quando disponível.
    if imagens:
        texto_ocr = _extrair_texto_ocr(imagens)
        if texto_ocr:
            email_texto += f'\n\nTexto extraído das imagens anexadas:\n{texto_ocr[:800]}'

    resposta = cliente.chat.completions.create(
        model=MODELO,
        max_tokens=512,
        temperature=0,
        response_format={'type': 'json_object'},  # garante JSON válido — sem erros de parse
        messages=[
            {'role': 'system', 'content': _SISTEMA},
            {'role': 'user',   'content': email_texto},
        ]
    )

    texto = resposta.choices[0].message.content.strip()

    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError:
        resultado = _resultado_erro(texto)

    resultado['categorias'] = [
        _NORM_CATEGORIAS.get(c, c) for c in resultado.get('categorias', [])
    ]

    return resultado


def _resultado_erro(texto_bruto: str) -> dict:
    return {
        'categorias': [],
        'confianca': 'baixa',
        'motivo': f'Erro ao interpretar resposta da IA: {texto_bruto[:120]}',
        'incerto': True
    }
