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
    'COMUNICACAO DE VARIACAO RELEVANTE',   # C51: título exato do comunicado BACEN
    'COMUNICAÇÃO DE VARIAÇÃO RELEVANTE',   # idem com acento
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
    # C43: VMTM removido — sigla de cálculo que aparece em suporte; nenhuma thread DDR depende dele
    r'CADASTRO DE A[ÇC][OÕ]ES E OP[ÇC][OÕ]ES',
    r'REMITLY\s*:\s*MOVIMENTO',  # C37: só o padrão DDR diário "REMITLY : Movimento DD.MM.AAAA"
    r'PI EXPOSURE',
    r'\bRD\b',              # Remessa Diária — arquivos RD_MOEDA, RD_LFT, RD_NTN etc.
    r'SALDOS 4111 E POSI[CÇ][AÃ][OÃ] LFT',  # planilha ZIIN com DDR + SALDOS no mesmo arquivo
    r'CADASTRO.*RISKDRIVER|RISKDRIVER.*CADASTRO',  # cadastro de fundos no Risk Driver = entrega DDR (C27)
    r'POSICAO\s+\d{2}[./]\d{2}[./]\d{4}',          # 'POSICAO DD.MM.AAAA' no assunto = arquivo de posição DDR (C28)
    r'\bEXTRATO[S]?\b',                             # extratos de conta/câmbio/aplicações = insumo DDR (C29)
]

# Marcadores de início de texto citado/encaminhado no corpo do e-mail
_MARC_CITACAO = re.compile(
    r'^(>|De:|From:|Enviada em:|Sent:|Em \w)',
    re.MULTILINE | re.IGNORECASE,
)

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
    r'DIVULGA[CÇ][AÃ]O\s+INSTRU[CÇ][AÃ]O NORMATIVA',  # C55: Finaud divulgando norma internamente
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
    # C35: excluir 'SALDOS CONT' quando seguido de nome de mês + /ano — é frequência mensal,
    # não diária. SCD = Saldos Contábeis DIÁRIOS. Ex.: "saldos contábeis de junho/2026" ≠ SCD.
    _SALDOS_MENSAL = re.compile(
        r'SALDOS CONT\w*\b.{0,30}\b'
        r'(?:JANEIRO|FEVEREIRO|MAR[CÇ]O|ABRIL|MAIO|JUNHO|JULHO|AGOSTO'
        r'|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)\b.{0,10}/\d{4}',
        re.DOTALL
    )
    _saldos_cont_mensal = bool(_SALDOS_MENSAL.search(texto_u))
    if (re.search(r'\b4111\b', texto_u)
            or ('SALDOS CONT' in texto_u and not _saldos_cont_mensal)
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
    # C38: COS4010 removido — mencionado em texto livre (assunto/corpo) não indica entrega DLO;
    # o sinal correto é COS4010 em NOME DE ARQUIVO, tratado pelo C36 no bloco `if cats:`.
    # C39: COS4016 + \b4111\b no mesmo texto → 4111 é o entregável; COS4016 é referência, não DLO.
    # Ex.: "COS4016 DE 06-2026. Segue o 4111 30/06/2026" → SCD, não DLO+SCD.
    tem_dlo = bool(
        re.search(r'\bDLO\b', texto_u)
        or re.search(r'\b2061\b', texto_u)
        or re.search(r'(?<!DRL-)\bLEC\b', texto_u)
        or ('COS4016' in texto_u and not re.search(r'\b4111\b', texto_u))
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

    # S5 — somente via 'RESULTADO QUANTITATIVO' em qualquer contexto;
    # '\bS5\b' é verificado separadamente só no assunto (Camada 1b),
    # pois no corpo 'S5' indica tamanho de instituição BACEN, não entrega CADOC
    # C54: plural 'RESULTADOS QUANTITATIVOS' adicionado — ex.: "cálculo dos Resultados Quantitativos"
    if re.search(r'RESULTADO[S]?\s+QUANTITATIVO[S]?', texto_u):
        cats.add('S5')

    # FORCAPITAL — somente via assunto (Camada 1b);
    # no corpo, termos como 'projeção de capital' aparecem em contexto de suporte,
    # e 'forcapital' pode ser endereço de e-mail (forcapital@finaud.com.br)
    pass  # verificação movida para Camada 1b em _classificar_deterministico

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


def _extrair_corpo_principal(corpo: str) -> str:
    """Retorna só a parte do corpo anterior ao primeiro trecho citado/encaminhado."""
    m = _MARC_CITACAO.search(corpo)
    return corpo[:m.start()].strip() if m else corpo.strip()


def _ok(cats: list[str], motivo: str, regra_usada: str | None) -> dict:
    return {
        'categorias':     cats,
        'confianca':      'alta',
        'motivo':         motivo,
        'incerto':        False,
        'gabarito_usado': regra_usada,
    }


# ── Pré-processamento de corpo ────────────────────────────────────────────────

def _corpo_sem_citacoes(corpo: str) -> str:
    """Remove linhas citadas ('>') e blocos encaminhados Outlook ('De:...Enviada em:').

    E-mails de resposta carregam o texto citado do remetente anterior. Esses
    trechos podem conter nomes de CADOC de entregas antigas que nada têm a ver
    com a entrega atual — e causam falsos positivos. Removê-los garante que a
    detecção de CADOC analisa só o texto da mensagem corrente.

    C50: além das linhas '>', também trunca no início de blocos encaminhados
    no formato Outlook ('De: X\n...\nEnviada em: Y'). Esses blocos não usam '>'
    mas carregam o corpo completo do e-mail original — inclusive menções a
    CADOC que são contexto histórico, não entrega atual.
    """
    linhas = corpo.split('\n')
    resultado = []
    for i, linha in enumerate(linhas):
        stripped = linha.strip()
        if stripped.startswith('>'):
            continue
        # C50: linha começa com 'De: ' → verificar se é cabeçalho Outlook
        # (seguido por 'Enviada em:' ou 'Sent:' nas próximas 6 linhas)
        if re.match(r'^De:\s+\S', stripped, re.IGNORECASE):
            trecho = '\n'.join(l.strip() for l in linhas[i:i + 6]).upper()
            if 'ENVIADA EM:' in trecho or 'SENT:' in trecho:
                break
        resultado.append(linha)
    return '\n'.join(resultado)


# ── Classificação determinística ──────────────────────────────────────────────

def _classificar_deterministico(
    assunto: str, corpo: str, anexos: str
) -> dict:
    au = assunto.upper()
    # C46: remover linhas citadas ('> ...') antes da detecção — texto de e-mails
    # anteriores pode conter nomes de CADOC de entregas antigas que causam
    # falsos positivos na mensagem atual.
    cu = _corpo_sem_citacoes(corpo).upper()
    # xu_norm aqui: _ e . viram espaço para que \bDRM\b encontre "DRM" em "DRM_2060.xml"
    xu_norm = anexos.upper().replace('_', ' ').replace('.', ' ')

    # Camada 1a — RETORNO_BACEN pelo assunto (prioridade máxima)
    if _tem_retorno_bacen(au, ''):
        return _ok(['RETORNO_BACEN'], 'sinal de RETORNO_BACEN no assunto', 'RETORNO - Regra 01')
    # 'QUALIDADE BACEN' no assunto indica crítica de qualidade do BACEN (ex.: DLO QUALIDADE BACEN)
    if 'QUALIDADE BACEN' in au:
        return _ok(['RETORNO_BACEN'], "'QUALIDADE BACEN' no assunto", 'RETORNO - Regra 01')
    # 'AJUSTE BACEN' no assunto → cliente pedindo ajuste por crítica do BACEN
    if 'AJUSTE BACEN' in au:
        return _ok(['RETORNO_BACEN'], "'AJUSTE BACEN' no assunto", 'RETORNO - Regra 01')
    # 'CRITICAS AO' no assunto → BC apontando críticas ao CADOC enviado
    if 'CRITICAS AO' in au or 'CRÍTICAS AO' in au:
        return _ok(['RETORNO_BACEN'], "'CRITICAS AO' no assunto", 'RETORNO - Regra 01')

    # Camada 1b — CADOC pelo assunto
    _pendencia_bacen = False  # C48: flag para suprimir Camada 2b quando assunto indica pendência
    cats = set(_detectar_cadoc(au))
    cats_au_original = frozenset(cats)  # C41: guarda cats antes de qualquer complemento
    # '\bS5\b' só no assunto — no corpo é tamanho de instituição BACEN (S1–S5), não entrega CADOC
    if re.search(r'\bS5\b', au):
        cats.add('S5')
    # FORCAPITAL só no assunto — no corpo aparece como endereço de e-mail ou contexto de suporte
    _FC_SINAIS = ('FORCAPITAL', 'FOR CAPITAL', 'FOR-CAPITAL', 'PROJECAO DE CAPITAL', 'PROJEÇÃO DE CAPITAL')
    if any(s in au for s in _FC_SINAIS):
        cats.add('FORCAPITAL')
    # Códigos COS DLO solo no assunto (ex.: '4010 Trinus', 'COSIF'S 4010') — no corpo podem ser contexto (C30)
    if re.search(r'\b(?:4010|4016|4060|4066)\b', au):
        cats.add('DLO_2061')
    # C40: "DDR2011" colado (sem espaço) no assunto — ex.: "VIS STA - DDR2011 e demais não disponíveis"
    # No corpo pode ser referência ao relatório do cliente ("nosso relatório de DDR2011") — restrito ao assunto
    if re.search(r'(?<!\w)DDR\d{4}(?!\w)', au):
        cats.add('DDR_2011')
    # C47: 'Saldos do dia DD/MM' no assunto = envio de saldos diários → SCD
    # No corpo, 'saldos do dia' pode aparecer como contexto/pedido — restrito ao assunto
    if re.search(r'SALDOS DO DIA\b', au):
        cats.add('SALDOS_CONTABEIS_DIARIOS_4111')
    # C48: 'PENDENCIAS BACEN' no assunto → o CADOC mencionado é contexto de pendência, não entrega.
    # Ex.: "Pendencias BACEN - 2011 ref. 30/01/2026" = DDR com pendência no BACEN; quem decide
    # a categoria é o que foi enviado no corpo/anexos (ex.: SCD para resolver a pendência).
    if cats and ('BACEN' in au) and ('PENDENCIAS' in au or 'PENDÊNCIA' in au or 'PENDÊNCIAS' in au):
        cats = set()
        cats_au_original = frozenset()
        _pendencia_bacen = True  # C48: corpo também menciona o CADOC da pendência — suprimir Camada 2b
    # 'INSTRUÇÃO NORMATIVA' sem CADOC no assunto = circular regulatória encaminhada, não entrega CADOC
    # (se o assunto também tiver código CADOC, ex.: 'DLI 2062', mantém a detecção normal)
    if not cats and ('INSTRUÇÃO NORMATIVA' in au or 'INSTRUCAO NORMATIVA' in au) and not _eh_interno(assunto):
        return _ok(['SUPORTE'], "'instrução normativa' no assunto sem código CADOC — circular regulatória, não entrega", None)
    if cats:
        # 'REUNIÃO' + CADOC no assunto = pauta/convite de reunião sobre o CADOC → SUPORTE, não entrega
        if 'REUNI' in au:
            return _ok(['SUPORTE'], "'reunião' + CADOC no assunto — pauta/convite, não entrega", None)
        # 'ERRO' no início + só DDR no assunto = pedido de suporte sobre erro de cálculo DDR, não entrega
        if au.startswith('ERRO') and cats == {'DDR_2011'}:
            return _ok(['SUPORTE'], "'erro' no início do assunto com só DDR — pedido de suporte, não entrega", None)
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
        # C32: complemento de código pelos nomes dos arquivos (padrão BACEN CNPJ_CÓDIGO_DATA)
        # Quando o assunto detectou um ou mais CADOCs, checar se os anexos têm arquivos de
        # outros CADOCs pelo código numérico no nome (2011=DDR, 2060=DRM, 2061=DLO, 2062=DLI).
        # 'SALDOS+4111' exige as duas palavras juntas — evita falso positivo em nomes como
        # 'DLI CV - MAIO _ 4111 CV' (4111 como referência interna, não arquivo SCD).
        if 'DDR_2011' not in cats and re.search(r'\b2011\b', xu_norm):
            cats.add('DDR_2011')
        if 'DRM_2060' not in cats and re.search(r'\b2060\b', xu_norm):
            cats.add('DRM_2060')
        if 'DLO_2061' not in cats and re.search(r'\b2061\b', xu_norm):
            cats.add('DLO_2061')
        if 'DLI_2062' not in cats and re.search(r'\b2062\b', xu_norm):
            cats.add('DLI_2062')
        if 'SALDOS_CONTABEIS_DIARIOS_4111' not in cats:
            if re.search(r'\b4111\b', xu_norm) and 'SALDOS' in xu_norm:
                cats.add('SALDOS_CONTABEIS_DIARIOS_4111')
        # C53: código COS DLO no assunto + 4111 no corpo = retificação de SCD junto com DLO
        # Ex.: "COS 4010 junho/2026" → DLO detectado do assunto; corpo diz "retificação do Doc 4111"
        if 'SALDOS_CONTABEIS_DIARIOS_4111' not in cats:
            if re.search(r'\b(?:4010|4016|4060|4066)\b', au) and re.search(r'\b4111\b', cu):
                cats.add('SALDOS_CONTABEIS_DIARIOS_4111')
        # C33: 4010 no nome do arquivo → DLO_2061 (padrão CNPJ_4010_DATA.xml = envio via COS4010)
        # Não incluir 4016: em testes, 4016 aparece em arquivos DLI (MIRAE), não DLO.
        if 'DLO_2061' not in cats and re.search(r'\b4010\b', xu_norm):
            cats.add('DLO_2061')
        # C36: COS4010 no nome do arquivo → DLO_2061
        # C33 usa \b4010\b que não bate em 'COS4010' (sem fronteira de palavra antes do 4).
        # Ex.: MIRAE envia 'COS4010_2026-06-I.zip' para validação do DRM — arquivo DLO.
        if 'DLO_2061' not in cats and 'COS4010' in xu_norm:
            cats.add('DLO_2061')
        # C34b: verbo de entrega + DDR no corpo → DDR_2011
        # Ex.: "Enviado o DDR de 29/05 ajustado e DRM" — duas entregas num mesmo e-mail cujo
        # assunto menciona só DRM. Padrão exige verbo explícito de envio próximo de DDR (≤60 chars)
        # para não disparar em corpos que apenas citam DDR como contexto ou referência.
        _DDR_ENVIADO = re.compile(
            r'(?:ENVIADO|ENCAMINHADO|ENVIANDO)\b.{0,60}\bDDR\b',
            re.DOTALL
        )
        if 'DDR_2011' not in cats and _DDR_ENVIADO.search(cu):
            cats.add('DDR_2011')
        # C34c: DRM e DRL mencionados juntos no corpo → adicionar ambos
        # O par DRM+DRL simultâneo no corpo de um e-mail de entrega indica que ambos os CADOCs
        # fazem parte do processo (mesmo que ainda não tenham sido enviados nessa mensagem).
        # Em 767 threads, nenhuma com só DRM ou só DRL no corpo falhou — o par é discriminante.
        if re.search(r'\bDRM\b', cu) and re.search(r'\bDRL\b', cu):
            if 'DRM_2060' not in cats:
                cats.add('DRM_2060')
            if 'DRL_2160' not in cats:
                cats.add('DRL_2160')
        # Sinal D: corpo principal (sem citações) pode ter crítica do BACEN mesmo com CADOC no assunto
        corpo_principal_u = _extrair_corpo_principal(corpo).upper()
        if _tem_retorno_bacen('', corpo_principal_u) or 'RETORNO DO STA' in corpo_principal_u:
            return _ok(['RETORNO_BACEN'], 'sinal de RETORNO_BACEN no corpo principal (sem citações)', 'RETORNO - Regra 01')
        # Sinal 5: 'indício de qualidade' + 'prazo' no corpo principal → BACEN apontou prazo para corrigir
        if ('INDICIO DE QUALIDADE' in corpo_principal_u or 'INDÍCIO DE QUALIDADE' in corpo_principal_u) and 'PRAZO' in corpo_principal_u:
            return _ok(['RETORNO_BACEN'], "'indício de qualidade' + 'prazo' no corpo principal", 'RETORNO - Regra 01')
        # Sinal 7: CRD (sistema BACEN de críticas) + 'pendência' no corpo principal → cliente checou o CRD e encontrou pendência
        if re.search(r'\bCRD\b', corpo_principal_u) and ('PENDENCIA' in corpo_principal_u or 'PENDÊNCIA' in corpo_principal_u):
            return _ok(['RETORNO_BACEN'], "'CRD' + 'pendência' no corpo principal", 'RETORNO - Regra 01')
        # Sinal 2: BACEN ordenando correção explicitamente no corpo completo
        if 'DETERMINAMOS A CORR' in cu:
            return _ok(['RETORNO_BACEN'], "'determinamos a correção' no corpo (BACEN ordena)", 'RETORNO - Regra 01')
        # Sinal 3: sinais de crítica do BACEN nos nomes dos anexos (arquivo recebido do BACEN)
        _SINAIS_ANEXO_EXTRA = ['POSSIVEL INCONSISTENCIA', 'POSSÍVEL INCONSISTÊNCIA',
                               'COMUNICACAO DE POSSIVEL', 'COMUNICAÇÃO DE POSSÍVEL']
        if (any(s in xu_norm for s in _RETORNO_SINAIS_FORTES + _RETORNO_SINAIS_VCRD)
                or any(s in xu_norm for s in _SINAIS_ANEXO_EXTRA)):
            return _ok(['RETORNO_BACEN'], 'sinal de RETORNO_BACEN nos nomes dos anexos', 'RETORNO - Regra 01')
        # Sinal 6b: VCRD no corpo completo (inclui citações) — crítica de VCRD encaminhada no histórico
        # Usa corpo.upper() e não cu (cu tem citações removidas pelo C46; VCRD em '>' é sinal real)
        if any(s in corpo.upper() for s in _RETORNO_SINAIS_VCRD):
            return _ok(['RETORNO_BACEN'], 'sinal VCRD no corpo completo', 'RETORNO - Regra 01')
        # C41: DLO e DLI ambos em cats, DLO veio do assunto (não do complemento), mas assunto
        # menciona DLI explicitamente sem DLO → 2061 era referência de arquivo, não entrega.
        # Colocado por último para sobrepor o complemento DLI→DLO (corpo pode mencionar DLO
        # como promessa futura "Enviaremos em breve o DLO" — que o complemento capturaria).
        if ('DLO_2061' in cats and 'DLI_2062' in cats
                and 'DLO_2061' in cats_au_original  # DLO veio do assunto, não do complemento
                and re.search(r'\bDLI\b', au) and not re.search(r'\bDLO\b', au)):
            cats.discard('DLO_2061')
        # C42: 'DRL-LEC' no assunto é nome do template DLO, não entrega DRL_2160.
        # Se DRL+DLO+DLI estão em cats e DRL vem só de prefixo 'DRL-' (sem DRL solo)
        # → DRL_2160 é ruído do nome do template herdado pelo reply chain.
        if ('DRL_2160' in cats and 'DLO_2061' in cats and 'DLI_2062' in cats
                and re.search(r'\bDRL-', au)
                and not re.search(r'\bDRL\b(?!-)', au)):
            cats.discard('DRL_2160')
        # C44: COS4016 no corpo de e-mail S5 (resultado quantitativo) é referência histórica,
        # não entrega DLO. Guard: só remove DLO quando S5 e DLO coexistem, assunto não tem
        # sinal DLO genuíno, e corpo não tem outro sinal DLO além de COS4016.
        if 'DLO_2061' in cats and 'S5' in cats:
            _au_sem_dlo = not (
                re.search(r'\bDLO\b', au) or re.search(r'\b2061\b', au)
                or re.search(r'(?<!DRL-)\bLEC\b', au)
                or re.search(r'\b(?:4016|4060|4066)\b', au)
                or any(c in au for c in ('COS4016', 'COS4060', 'COS4066'))
                or re.search(r'\bDLI\b', au)
            )
            _cu_sem_dlo_forte = not (
                re.search(r'\bDLO\b', cu) or re.search(r'\b2061\b', cu)
                or re.search(r'(?<!DRL-)\bLEC\b', cu)
                or 'COS4060' in cu or 'COS4066' in cu
            )
            if _au_sem_dlo and _cu_sem_dlo_forte and 'COS4016' in cu:
                cats.discard('DLO_2061')
        # C45: S5 no assunto indica entrega do relatório S5 — COS4010/4016 anexados são
        # componentes desse relatório, não entrega DLO separada. DLO e S5 nunca coexistem
        # numa entrega real; quando o cliente menciona S5, a categoria é só S5.
        if 'DLO_2061' in cats and 'S5' in cats and re.search(r'\bS5\b', au):
            cats.discard('DLO_2061')
        cats = sorted(cats)
        return _ok(cats, f'sinal de CADOC no assunto ({", ".join(cats)})', None)

    # Camada 2a — RETORNO_BACEN pelo corpo (cliente encaminhando e-mail do BACEN).
    # Usa corpo completo (não stripped): VCRD/crítica do BACEN em texto citado é sinal
    # real — o BACEN respondeu com erro, independente de aparecer em trecho '> ...'.
    if _tem_retorno_bacen('', corpo.upper()):
        return _ok(['RETORNO_BACEN'], 'sinal de RETORNO_BACEN no corpo', 'RETORNO - Regra 01')

    # Camada 2b — CADOC pelo corpo
    # C48: quando assunto indica pendência BACEN, corpo cita o CADOC por contexto — pular detecção
    cats = set() if _pendencia_bacen else set(_detectar_cadoc(cu))
    # C52: 'SALDOS CONT' no corpo é contexto explicativo, não entrega — remover SCD se for
    # o único gatilho (4111, FLUXO DE CAIXA e CADOC continuam válidos no corpo)
    if 'SALDOS_CONTABEIS_DIARIOS_4111' in cats:
        if not (re.search(r'\b4111\b', cu)
                or 'FLUXO DE CAIXA' in cu
                or re.search(r'\bCADOC\b(?!\s{0,4}\d{4})', cu)):
            cats.discard('SALDOS_CONTABEIS_DIARIOS_4111')
    if cats:
        # C44: COS4016 no corpo de e-mail S5 (resultado quantitativo) é referência histórica,
        # não entrega DLO. Guard espelha o da Camada 1b.
        if 'DLO_2061' in cats and 'S5' in cats:
            _au_sem_dlo = not (
                re.search(r'\bDLO\b', au) or re.search(r'\b2061\b', au)
                or re.search(r'(?<!DRL-)\bLEC\b', au)
                or re.search(r'\b(?:4016|4060|4066)\b', au)
                or any(c in au for c in ('COS4016', 'COS4060', 'COS4066'))
                or re.search(r'\bDLI\b', au)
            )
            _cu_sem_dlo_forte = not (
                re.search(r'\bDLO\b', cu) or re.search(r'\b2061\b', cu)
                or re.search(r'(?<!DRL-)\bLEC\b', cu)
                or 'COS4060' in cu or 'COS4066' in cu
            )
            if _au_sem_dlo and _cu_sem_dlo_forte and 'COS4016' in cu:
                cats.discard('DLO_2061')
        cats = sorted(cats)
        return _ok(cats, f'sinal de CADOC no corpo ({", ".join(cats)})', None)

    # Camada 3 — CADOC pelos nomes dos anexos
    cats_set = set(_detectar_cadoc(xu_norm))
    # 'COS 4010' (com espaço) nos nomes de arquivo = entrega DLO — no corpo pode ser contexto de pergunta (C31)
    if re.search(r'COS\s*(?:4010|4016|4060|4066)', xu_norm):
        cats_set.add('DLO_2061')
    cats = sorted(cats_set)
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
