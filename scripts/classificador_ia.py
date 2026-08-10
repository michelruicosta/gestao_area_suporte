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

load_dotenv()

MODELO = 'gpt-4o-mini'

# ── Caminhos ──────────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_SPEC  = os.path.join(BASE_DIR, 'documentações', 'ESPECIFICACAO_NOVA_ARQUITETURA.md')
CAMINHO_GAB   = os.path.join(BASE_DIR, 'documentações', 'gabarito.json')


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
    """Lê gabarito.json e formata como seção de texto para o prompt."""
    try:
        with open(caminho, encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        return ''

    exemplos = dados.get('exemplos', [])
    if not exemplos:
        return ''

    por_cat: dict[str, list] = {}
    for ex in exemplos:
        cat = ex.get('categoria', '')
        por_cat.setdefault(cat, []).append(ex)

    linhas = [
        '## Exemplos confirmados — aprenda pelo exemplo',
        '',
        'Os casos abaixo foram revisados e confirmados por especialistas.',
        'Quando o e-mail se encaixar num desses padrões, aplique a categoria indicada —',
        'mesmo que o corpo esteja fraco, vazio ou em imagem.',
        '',
    ]
    for cat, exs in por_cat.items():
        linhas.append(f'**{cat} — padrões confirmados:**')
        for ex in exs:
            eid   = ex.get('id', '')
            subj  = ex.get('assunto_exemplo', '')
            regra = ex.get('regra', '')
            linhas.append(f'• [{eid}] Exemplo: "{subj}" → {cat}')
            linhas.append(f'  {regra}')
        linhas.append('')

    return '\n'.join(linhas)


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
  DDR_2011, SCD_4111, DRM_2060, DLO_2061, DLI_2062, DRL_2160, S5,
  RETORNO_BACEN, FORCAPITAL, DRSAC_2030, PVCA_6209, SUPORTE

## Formato de resposta — JSON válido com esta estrutura exata:

{{
  "categorias": ["CATEGORIA"],
  "confianca": "alta",
  "motivo": "explicação curta em português",
  "incerto": false
}}

Se não conseguir classificar com confiança suficiente, retorne:
{{
  "categorias": [],
  "confianca": "baixa",
  "motivo": "motivo da incerteza",
  "incerto": true
}}"""


# ── Classificação ──────────────────────────────────────────────────────────────

def classificar_thread(thread: dict, cliente: OpenAI = None) -> dict:
    """
    Classifica uma thread em uma ou mais categorias do §10.

    Parâmetros
    ----------
    thread  : dict no formato do coletor_gmail.py
    cliente : instância do openai.OpenAI (opcional — cria uma se não passada)

    Retorna
    -------
    {
      "categorias" : list[str],   ex.: ["DDR_2011"] ou ["DLO_2061", "DLI_2062"]
      "confianca"  : str,         "alta" | "media" | "baixa"
      "motivo"     : str,         explicação em português
      "incerto"    : bool
    }
    """
    if cliente is None:
        cliente = OpenAI()

    mensagens = thread.get('mensagens', [])
    assunto   = thread.get('assunto', '')

    msg0      = mensagens[0] if mensagens else {}
    remetente = msg0.get('remetente', '')
    corpo     = msg0.get('corpo_texto', '')[:600]
    anexos    = msg0.get('nomes_anexos', [])
    lista_anexos = ', '.join(anexos) if anexos else '(nenhum)'

    email_texto = (
        f"Assunto: {assunto}\n"
        f"De: {remetente}\n"
        f"Anexos: {lista_anexos}\n"
        f"\nCorpo (início):\n{corpo}"
    )

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

    return resultado


def _resultado_erro(texto_bruto: str) -> dict:
    return {
        'categorias': [],
        'confianca': 'baixa',
        'motivo': f'Erro ao interpretar resposta da IA: {texto_bruto[:120]}',
        'incerto': True
    }
