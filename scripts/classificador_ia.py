"""
classificador_ia.py
Classifica threads de e-mail usando regras determinísticas (sem chamada a IA).
A fonte de verdade das regras está em documentações/regras_classificador_threads.json.

Fluxo:
  1. Thread confirmada no registro → retorna o que está salvo sem reprocessar.
  2. Camada 1 — assunto: RETORNO_BACEN → CADOC.
  3. Camada 2 — corpo: RETORNO_BACEN → CADOC.
  4. Camada 3 — nomes dos anexos: CADOC.
  5. Camada 4 — padrões de e-mail interno (boas-vindas, comunicado de saída…).
  6. Camada 5 — SUPORTE (catch-all).
"""

from __future__ import annotations

import json
import os
import re

try:
    import pytesseract
    from PIL import Image as _PILImage
    _OCR_DISPONIVEL = True
except ImportError:
    _OCR_DISPONIVEL = False

# ── Caminhos ──────────────────────────────────────────────────────────────────

BASE_DIR         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_REGRAS   = os.path.join(BASE_DIR, 'documentações', 'regras_classificador_threads.json')
PASTA_ANEXOS     = os.path.join(BASE_DIR, 'data', 'email_anexos')
ARQUIVO_REGISTRO = os.path.join(BASE_DIR, 'data', 'registro_definitivo_threads.json')

# ── Normalização de nomes de categoria ───────────────────────────────────────
# Converte variantes do nome legível para o código canônico do sistema.
_NORM_CATEGORIAS: dict[str, str] = {
    'Saldos Contábeis Diários 4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'saldos contábeis diários 4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'SALDOS CONTABEIS DIARIOS 4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'Saldos_Contabeis_Diarios_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'Saldos_CONTABEIS_DIARIOS_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'SALTOS_CONTABEIS_DIARIOS_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
    'Saltos_Contabeis_Diarios_4111':  'SALDOS_CONTABEIS_DIARIOS_4111',
}

# ── Registro definitivo ───────────────────────────────────────────────────────

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


# ── Padrões de detecção ───────────────────────────────────────────────────────

# Sinais de RETORNO_BACEN
_RETORNO_SINAIS_FORTES = [
    'AVISO DE ATRASO',
    'BANCO CENTRAL - AVISO',
    'COMUNICACAO DE INCONSISTENCIA',
    'COMUNICAÇÃO DE INCONSISTÊNCIA',
    'INDICIO DE PROBLEMA DE QUALIDADE',
    'INDÍCIO DE PROBLEMA DE QUALIDADE',
    'VARIACAO RELEVANTE',           # comunicado BACEN de variação acima da média
    'VARIAÇÃO RELEVANTE',           # idem com acento
    'REITERACAO',                   # 1ª/2ª reiteração de comunicado BACEN
    'REITERAÇÃO',                   # idem com acento
]
_RETORNO_SINAIS_VCRD = ['VCRD', 'CRITICA VCRD', 'CRÍTICA VCRD']
_RETORNO_SINAIS_INDICIO = ['INDICIO', 'INDÍCIO']

# Padrões DDR_2011 (regex aplicado sobre texto em maiúsculo)
_DDR_PADROES = [
    r'\bDDRS?\b',
    r'\b2011\b',
    r'EXTRATO COMPROMISSADA',
    r'COMPROMISSAD',           # cobre compromissada, compromissadas
    r'\bPCAM\b',
    r'(?<!/)\bTVM\b',          # não dispara em "/TVM" (ex: TPF/TVM em contexto DLO)
    r'OP\.\s*SELIC',
    r'POSI[CÇ][AÃ][OÃ] DE C[AÂ]MBIO',
    r'\bPU[S]?\b',
    r'\bVMTM\b',
    r'CADASTRO DE A[ÇC][OÕ]ES E OP[ÇC][OÕ]ES',
    r'\bREMITLY\b',
    r'PI EXPOSURE',
    r'\bRD\b',              # Remessa Diária — arquivos RD_MOEDA, RD_LFT, RD_NTN etc.
    r'SALDOS 4111 E POSI[CÇ][AÃ][OÃ] LFT',  # planilha ZIIN com DDR + SALDOS no mesmo arquivo
]

# Padrões INTERNO (regex aplicado sobre assunto em maiúsculo)
_INTERNO_PADROES_ASSUNTO = [
    r'BOAS.VINDAS',
    r'BOA.VINDA',
    r'BEM.VINDO',
    r'COMUNICADO DE SA[IÍ]DA',
    r'C[OÓ]DIGO DE VERIFICA',
    r'CONVIDOU VOC[EÊ]',
    r'INGRESSAR.*TEAMS',
    r'VISITA FINAUD',
]


# ── Funções de detecção ───────────────────────────────────────────────────────

def _tem_retorno_bacen(assunto_u: str, corpo_u: str) -> bool:
    """Retorna True se o texto contém sinais claros de RETORNO_BACEN."""
    texto = assunto_u + ' ' + corpo_u
    if any(s in texto for s in _RETORNO_SINAIS_FORTES):
        return True
    if any(s in texto for s in _RETORNO_SINAIS_VCRD):
        return True
    # INDICIO/INDÍCIO: só no assunto — no corpo é termo técnico comum
    if any(s in assunto_u for s in _RETORNO_SINAIS_INDICIO):
        return True
    # REJEITADO: só no assunto — no corpo aparece em contextos normais (ex.: "o arquivo foi rejeitado")
    if 'REJEITADO' in assunto_u:
        return True
    return False


def _detectar_cadoc(texto_u: str) -> list[str]:
    """
    Detecta categorias CADOC presentes em um texto (assunto, corpo ou anexos).
    Retorna lista ordenada das categorias identificadas.
    """
    cats: set[str] = set()

    # SALDOS_CONTABEIS_DIARIOS_4111
    # "CADOC" sem número de 4 dígitos imediatamente após = uso coloquial para SALDOS (Correção 12)
    if (re.search(r'\b4111\b', texto_u)
            or 'SALDOS CONT' in texto_u
            or 'FLUXO DE CAIXA' in texto_u
            or re.search(r'\bCADOC\b(?!\s{0,4}\d{4})', texto_u)):
        cats.add('SALDOS_CONTABEIS_DIARIOS_4111')

    # DRM_2060
    if re.search(r'\bDRM\b', texto_u) or re.search(r'\b2060\b', texto_u):
        cats.add('DRM_2060')

    # DRL_2160
    if (re.search(r'\bDRL\b', texto_u)
            or re.search(r'\bDLR\b', texto_u)   # typo frequente
            or re.search(r'\b2160\b', texto_u)):
        cats.add('DRL_2160')

    # DDR_2011
    if any(re.search(p, texto_u) for p in _DDR_PADROES):
        cats.add('DDR_2011')

    # DLO_2061 e DLI_2062 — sub-regra de distinção
    # LEC com lookbehind: não dispara DLO em "DRL-LEC" (LEC é componente do DRL, não DLO)
    tem_dlo = bool(
        re.search(r'\bDLO\b', texto_u)
        or re.search(r'\b2061\b', texto_u)
        or re.search(r'(?<!DRL-)\bLEC\b', texto_u)
        or 'COS4010' in texto_u
        or 'COS4016' in texto_u
        or 'COS4060' in texto_u
        or 'COS4066' in texto_u
    )
    tem_dli = bool(
        re.search(r'\bDLI\b', texto_u)
        or re.search(r'\b2062\b', texto_u)
    )
    if tem_dlo and tem_dli:
        cats.add('DLO_2061')
        cats.add('DLI_2062')
    elif tem_dlo:
        cats.add('DLO_2061')
    elif tem_dli:
        cats.add('DLI_2062')

    # S5
    if re.search(r'\bS5\b', texto_u) or 'RESULTADO QUANTITATIVO' in texto_u:
        cats.add('S5')

    # FORCAPITAL
    if ('FORCAPITAL' in texto_u
            or 'FOR CAPITAL' in texto_u
            or 'FOR-CAPITAL' in texto_u
            or 'PROJECAO DE CAPITAL' in texto_u
            or 'PROJEÇÃO DE CAPITAL' in texto_u):
        cats.add('FORCAPITAL')

    # DRSAC_2030
    if 'DRSAC' in texto_u or re.search(r'\b2030\b', texto_u):
        cats.add('DRSAC_2030')

    # PVCA_6209
    if (re.search(r'\bPVCA\b', texto_u)
            or re.search(r'\b6209\b', texto_u)
            or 'PAGAMENTOS DE VAREJO' in texto_u):
        cats.add('PVCA_6209')

    return sorted(cats)


def _eh_interno(assunto: str) -> bool:
    """Retorna True se o assunto corresponde a um padrão de e-mail interno."""
    au = assunto.upper()
    return any(re.search(p, au) for p in _INTERNO_PADROES_ASSUNTO)


def _ok(cats: list[str], motivo: str, regra_usada: str | None) -> dict:
    return {
        'categorias':     cats,
        'confianca':      'alta',
        'motivo':         motivo,
        'incerto':        False,
        'gabarito_usado': regra_usada,
    }


# ── Classificação determinística ──────────────────────────────────────────────

def _classificar_deterministico(
    assunto: str, corpo: str, anexos: str
) -> dict:
    au = assunto.upper()
    cu = corpo.upper()
    # xu_norm aqui: _ e . viram espaço para que \bDRM\b encontre "DRM" em "DRM_2060.xml"
    xu_norm = anexos.upper().replace('_', ' ').replace('.', ' ')

    # Camada 1a — RETORNO_BACEN pelo assunto (prioridade máxima)
    if _tem_retorno_bacen(au, ''):
        return _ok(['RETORNO_BACEN'], 'sinal de RETORNO_BACEN no assunto', 'RETORNO - Regra 01')

    # Camada 1b — CADOC pelo assunto
    cats = set(_detectar_cadoc(au))
    if cats:
        # Complemento DLO/DLI: se o assunto tem um mas não o outro,
        # busca só a metade faltante no corpo+anexos — evita falsos positivos
        # de outros CADOCs citados no contexto do e-mail.
        texto_resto = cu + ' ' + xu_norm
        if 'DLO_2061' in cats and 'DLI_2062' not in cats:
            if re.search(r'\bDLI\b', texto_resto) or re.search(r'\b2062\b', texto_resto):
                cats.add('DLI_2062')
        elif 'DLI_2062' in cats and 'DLO_2061' not in cats:
            if (re.search(r'\bDLO\b', texto_resto) or re.search(r'\b2061\b', texto_resto)
                    or re.search(r'(?<!DRL-)\bLEC\b', texto_resto)
                    or any(c in texto_resto for c in ('COS4010', 'COS4016', 'COS4060', 'COS4066'))):
                cats.add('DLO_2061')
        # Complemento DDR: planilha ZIIN "Saldos 4111 e Posição LFT" = SALDOS + DDR no mesmo arquivo
        if 'SALDOS_CONTABEIS_DIARIOS_4111' in cats and 'DDR_2011' not in cats:
            if re.search(r'SALDOS 4111 E POSI[CÇ][AÃ][OÃ] LFT', texto_resto):
                cats.add('DDR_2011')
        cats = sorted(cats)
        return _ok(cats, f'sinal de CADOC no assunto ({", ".join(cats)})', None)

    # Camada 2a — RETORNO_BACEN pelo corpo (cliente encaminhando e-mail do BACEN)
    if _tem_retorno_bacen('', cu):
        return _ok(['RETORNO_BACEN'], 'sinal de RETORNO_BACEN no corpo', 'RETORNO - Regra 01')

    # Camada 2b — CADOC pelo corpo
    cats = _detectar_cadoc(cu)
    if cats:
        return _ok(cats, f'sinal de CADOC no corpo ({", ".join(cats)})', None)

    # Camada 3 — CADOC pelos nomes dos anexos
    cats = _detectar_cadoc(xu_norm)
    if cats:
        return _ok(cats, f'sinal de CADOC nos anexos ({", ".join(cats)})', None)

    # Camada 4 — padrões de e-mail interno
    if _eh_interno(assunto):
        return _ok(['INTERNO'], 'padrão de e-mail interno no assunto', 'INTERNO - Regra 01')

    # Camada 5 — SUPORTE (catch-all)
    return _ok(['SUPORTE'], 'sem sinal de CADOC → SUPORTE', None)


# ── Ponto de entrada público ──────────────────────────────────────────────────

def classificar_thread(thread: dict, cliente=None, imagens: list = None) -> dict:
    """
    Classifica uma thread de e-mail de forma determinística (sem chamada a IA).

    Parâmetros
    ----------
    thread  : dict no formato do coletor_gmail.py
    cliente : ignorado (mantido para compatibilidade de assinatura)
    imagens : ignorado (nomes de anexos são lidos diretamente do campo 'nomes_anexos')

    Retorna
    -------
    {
      "categorias"    : list[str],
      "confianca"     : str,        "alta"
      "motivo"        : str,        explicação em português
      "incerto"       : bool,       sempre False (determinístico sempre decide)
      "gabarito_usado": str | None
    }
    """
    # Threads com status_regra "confirmada" no registro retornam o valor salvo.
    thread_id = thread.get('thread_id', '')
    if thread_id:
        reg    = _carregar_registro()
        entrada = reg.get('threads', {}).get(thread_id)
        if entrada and entrada.get('status_regra') == 'confirmada':
            return {
                'categorias':     entrada.get('categorias', []),
                'confianca':      'alta',
                'motivo':         f'Confirmada no registro ({entrada.get("regra_usada", "registro")})',
                'incerto':        False,
                'gabarito_usado': entrada.get('regra_usada'),
            }

    # Coleta de dados da thread
    mensagens    = thread.get('mensagens', [])
    assunto      = (thread.get('assunto') or '').strip()
    corpo_partes: list[str] = []
    nomes_anexos: list[str] = []

    for msg in mensagens[:3]:
        corpo_msg = (msg.get('corpo_texto') or '').strip()
        if corpo_msg:
            corpo_partes.append(corpo_msg[:600])
        nomes_anexos.extend(msg.get('nomes_anexos') or [])

    corpo  = ' '.join(corpo_partes)
    anexos = ' '.join(nomes_anexos)

    return _classificar_deterministico(assunto, corpo, anexos)


# ── OCR e imagens (mantidos para uso pelo pipeline) ──────────────────────────

def buscar_imagens(indice: int) -> list:
    """Retorna caminhos das imagens do índice informado na pasta de anexos."""
    if not os.path.isdir(PASTA_ANEXOS):
        return []
    prefix = f'{indice}_'
    exts   = {'.png', '.jpg', '.jpeg'}
    return sorted(
        os.path.join(PASTA_ANEXOS, arq)
        for arq in os.listdir(PASTA_ANEXOS)
        if arq.startswith(prefix)
        and os.path.splitext(arq)[1].lower() in exts
    )


def _extrair_texto_ocr(caminhos: list) -> str:
    """Extrai texto de imagens via OCR. Retorna '' se lista vazia ou OCR indisponível."""
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
