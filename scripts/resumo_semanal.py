"""Resumo semanal — Gestão Área Suporte. Enviado toda segunda-feira para grupos configurados."""
from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import smtplib
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

_log = logging.getLogger(__name__)

_NOTIF_ID      = 'resumo_semanal'
_GRUPOS_NOTIF  = ('administrador', 'gestor', 'operador')
_ASSUNTO_EMAIL = 'Gestão Área Suporte — Resumo Semanal'
_FOGBUGZ_URL   = 'https://finaud.fogbugz.com/api.asp'
_FOGBUGZ_FILTER = '218'
_BG_HEADER     = '#3333A8'
_BG_GRAD       = '#1e1e72'
_VERDE         = '#8DC63F'

_DIAS_SEMANA = [
    'Segunda-feira', 'Terça-feira', 'Quarta-feira',
    'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo',
]

_CADOC_INFO = {
    'DRM 2060':          'Inconsistências entre o DRM 2060 e os documentos COSIF 4060/4010 e/ou DDR 2011',
    'DLO 2061':          'Contas 891.20 e 891 (IRRBB) não preenchidas na data-base informada',
    'DDR 2011':          'Variação relevante identificada no DDR 2011 — BACEN solicitou correção e substituição',
    'LIM 2061':          'Inconsistência entre os valores do LIM 2061 e o balanço contábil (COSIF 4010/4016)',
    'DLI 2062':          'Saldo contábil do COSIF 4010 diverge dos valores informados no DLI 2062',
    'COSIF 4111':        'Saldo das contas do COSIF 4111 diverge do balancete 4010 — documento deve ser corrigido',
    'COSIF 4010/4016':   'Indícios de qualidade no COSIF 4010/4016 — balancete contábil com inconsistências',
    'DRL 2160':          'DRL rejeitado — pendente de correção e reenvio',
    'Atraso em remessa': 'Aviso de atraso na entrega de documentos ao BACEN — remessa pendente',
    'Outros':            'Tipo de documento não identificado automaticamente',
}

_CADOC_ORDER = [
    'DRM 2060', 'DLO 2061', 'DDR 2011', 'LIM 2061', 'DLI 2062',
    'COSIF 4111', 'COSIF 4010/4016', 'DRL 2160', 'Atraso em remessa', 'Outros',
]

# Ordem de detecção: mais específico primeiro
_CADOC_PATTERNS: list[tuple[str, re.Pattern]] = [
    ('Atraso em remessa', re.compile(r'ATRASO[\s\-]+EM[\s\-]+REMESSA', re.I)),
    ('DRL 2160',          re.compile(r'\bDRL\b', re.I)),
    ('COSIF 4111',        re.compile(r'\b4111\b', re.I)),
    ('COSIF 4010/4016',   re.compile(r'\b40(?:10|16)\b|IND[IÍ]CIO.*QUALIDADE(?!.*20\d\d)', re.I)),
    ('DLI 2062',          re.compile(r'\bDLI\b|\b2062\b|DOCUMENTO[\s\-]+2062', re.I)),
    ('LIM 2061',          re.compile(r'\bLIM\b', re.I)),
    ('DLO 2061',          re.compile(r'\bDLO\b|\b2061\b|DOCUMENTO[\s\-]+2061', re.I)),
    ('DDR 2011',          re.compile(r'\bDDR\b|\b2011\b', re.I)),
    ('DRM 2060',          re.compile(r'\bDRM\b|\b2060\b', re.I)),
]

_RE_PREFIXO  = re.compile(r'^(?:ENC:|FW:|Fwd:|Re:|RES:|Fw:|\[[^\]]+\])\s*', re.I)
_RE_BACEN    = re.compile(
    r'^BANCO\s+CENTRAL\s*[-–]\s*(?:\d+[Aa]\.\s+)?(?:REITERA[CÇ][AÃ]O\s+[^-–]{0,50}[-–]\s*|'
    r'AVISO\s+DE\s+|COMUNICA[CÇ][AÃ]O\s+DE\s+|IND[IÍ]CIO\s+DE\s+)?|^BC\s*[-–]\s*',
    re.I,
)
_RE_EMPRESA_ANTES_CADOC = re.compile(
    r'^(.+?)\s*[-–_|]\s*(?:DRM|DLO|DDR|LIM|DLI|DRL|COSIF|IND[IÍ]CIO|ATRASO|BACEN|BC\b)',
    re.I,
)
_DOMINIOS_GENERICOS = frozenset({
    'gmail', 'hotmail', 'yahoo', 'outlook', 'uol', 'bol', 'ig',
    'finaud', 'finaudtec',
})
_PALAVRAS_CADOC = re.compile(
    r'^(?:DRM|DLO|DDR|LIM|DLI|DRL|COSIF|IND[IÍ]CIO|ATRASO|BANCO|BC|SUPORTE|BACEN|COS|COMUNI|AVISO)\b',
    re.I,
)


# ── Config / normalização ──────────────────────────────────────────────────────

def resumo_semanal_padrao() -> dict:
    return {
        'id':         _NOTIF_ID,
        'titulo':     'Resumo Semanal Retorno BACEN',
        'descricao':  'Consolidado semanal dos retornos do BACEN em aberto — enviado toda segunda-feira.',
        'ativa':      True,
        'grupos':     ['administrador'],
        'dia_semana': 0,
    }


def normalizar_resumo_semanal(bruto: dict | None) -> dict:
    padrao = resumo_semanal_padrao()
    item   = bruto if isinstance(bruto, dict) else {}

    grupos = item.get('grupos', padrao['grupos'])
    if not isinstance(grupos, list):
        grupos = list(padrao['grupos'])
    grupos = [g for g in grupos if g in _GRUPOS_NOTIF] or ['administrador']

    ativa = item.get('ativa', True)
    if not isinstance(ativa, bool):
        ativa = str(ativa).strip().lower() in ('1', 'true', 'sim', 'yes')

    try:
        dia = int(item.get('dia_semana', 0))
    except (TypeError, ValueError):
        dia = 0
    dia = max(0, min(6, dia))

    return {**padrao, 'ativa': ativa, 'grupos': grupos, 'dia_semana': dia}


# ── Detecção de CADOC e empresa ───────────────────────────────────────────────

def _detectar_cadoc(assunto: str) -> str:
    for nome, pat in _CADOC_PATTERNS:
        if pat.search(assunto):
            return nome
    return 'Outros'


def _extrair_empresa(assunto: str, remetente: str) -> str:
    rem = remetente or ''

    # Padrão: "Nome - Empresa <email>"
    m = re.match(r'^[^<-]+ - ([^<@\n]{2,50}?)\s*<', rem)
    if m:
        c = m.group(1).strip().rstrip(' -')
        if c and 'suporte' not in c.lower() and 'finaud' not in c.lower():
            return c

    # Padrão: "'Nome | Empresa' via Suporte"
    m = re.search(r"'\s*[^|']+\|\s*([^']+)'\s+via", rem, re.I)
    if m:
        return m.group(1).strip()

    is_interno = '@finaud.com.br' in rem or '@finaudtec.com.br' in rem or 'via Suporte' in rem

    if not is_interno:
        # Tenta extrair do domínio do email
        m = re.search(r'<[^@]+@([^.>]+)\.', rem)
        if m:
            domain = m.group(1).lower()
            if domain not in _DOMINIOS_GENERICOS:
                return domain.capitalize()

    # Tenta extrair do assunto: empresa antes do nome do CADOC
    sub = assunto or ''
    for _ in range(5):
        novo = _RE_PREFIXO.sub('', sub).strip()
        if novo == sub:
            break
        sub = novo
    sub = _RE_BACEN.sub('', sub).strip()

    m = _RE_EMPRESA_ANTES_CADOC.match(sub)
    if m:
        c = m.group(1).strip(' -–|.,_')
        if c and not _PALAVRAS_CADOC.match(c) and 2 <= len(c) <= 60:
            return c

    return 'Sem empresa identificada'


# ── Busca no banco ────────────────────────────────────────────────────────────

def _caminho_banco() -> str:
    aqui = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(aqui, '..', 'data', 'gestao.db')


def buscar_dados_bacen() -> dict:
    """Retorna totais e grupos de threads RETORNO_BACEN em aberto por status e CADOC."""
    banco = _caminho_banco()
    if not os.path.exists(banco):
        return {}

    try:
        conn = sqlite3.connect(banco)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT assunto, remetente_principal, status_workflow
            FROM threads
            WHERE categoria = 'RETORNO_BACEN'
              AND status_workflow IN ('Aguardando Cliente', 'Aguardando Finaud')
            ORDER BY status_workflow, assunto
            """,
        ).fetchall()
        conn.close()
    except Exception:
        _log.exception('Resumo BACEN: falha ao ler banco.')
        return {}

    por_status: dict[str, dict[str, list[str]]] = {
        'Aguardando Cliente': defaultdict(list),
        'Aguardando Finaud':  defaultdict(list),
    }

    for row in rows:
        assunto  = row['assunto'] or ''
        remetente= row['remetente_principal'] or ''
        status   = row['status_workflow']
        cadoc    = _detectar_cadoc(assunto)
        empresa  = _extrair_empresa(assunto, remetente)
        por_status[status][cadoc].append(empresa)

    cliente = sum(len(v) for v in por_status['Aguardando Cliente'].values())
    finaud  = sum(len(v) for v in por_status['Aguardando Finaud'].values())

    return {
        'total':      cliente + finaud,
        'cliente':    cliente,
        'finaud':     finaud,
        'por_status': {
            k: dict(v) for k, v in por_status.items()
        },
    }


def _dias_uteis(inicio: date, fim: date) -> int:
    """Dias úteis (seg–sex) entre duas datas, sem contar o dia inicial."""
    if not inicio or not fim or fim <= inicio:
        return 0
    total = 0
    dia = inicio + timedelta(days=1)
    while dia <= fim:
        if dia.weekday() < 5:
            total += 1
        dia += timedelta(days=1)
    return total


def buscar_dados_fog_semanal(token: str) -> list[dict]:
    """Retorna casos FOG em aberto agrupados por responsável, ordenados por total desc."""
    if not token:
        return []
    hoje = datetime.now(timezone.utc).date()
    try:
        requests.get(_FOGBUGZ_URL, params={
            'token': token, 'cmd': 'setCurrentFilter', 'sFilter': _FOGBUGZ_FILTER,
        }, timeout=10)
        resp = requests.get(_FOGBUGZ_URL, params={
            'token': token,
            'cmd': 'search',
            'q': 'status:open',
            'cols': 'ixBug,sPersonAssignedTo,dtLastUpdated',
        }, timeout=30)
        root = ET.fromstring(resp.text)
        por_pessoa: dict[str, dict] = {}
        for case in root.findall('.//case'):
            pessoa = (case.findtext('sPersonAssignedTo') or '').strip() or 'Sem responsável'
            dt_str = (case.findtext('dtLastUpdated') or '').strip()
            try:
                dt_upd = datetime.fromisoformat(dt_str.replace('Z', '+00:00')).date()
                dias = _dias_uteis(dt_upd, hoje)
            except Exception:
                dias = 0
            if pessoa not in por_pessoa:
                por_pessoa[pessoa] = {'responsavel': pessoa, 'total': 0, 'max_dias': 0}
            por_pessoa[pessoa]['total'] += 1
            por_pessoa[pessoa]['max_dias'] = max(por_pessoa[pessoa]['max_dias'], dias)
        return sorted(por_pessoa.values(), key=lambda x: x['total'], reverse=True)
    except Exception:
        _log.exception('Resumo FOG semanal: erro ao buscar no FogBugz')
        return []


def buscar_fog_encerrados_semana(token: str) -> int:
    """Conta casos FOG encerrados nos últimos 7 dias via FogBugz API."""
    if not token:
        return 0
    corte = datetime.now(timezone.utc).date() - timedelta(days=7)
    corte_str = corte.isoformat()
    try:
        resp = requests.get(_FOGBUGZ_URL, params={
            'token': token,
            'cmd': 'search',
            'q': f'status:closed resolved:">={corte_str}"',
            'cols': 'ixBug,dtClosed',
        }, timeout=30)
        root = ET.fromstring(resp.text)
        total = 0
        for case in root.findall('.//case'):
            dt_str = (case.findtext('dtClosed') or '').strip()
            if not dt_str:
                continue
            try:
                dt_closed = datetime.fromisoformat(dt_str.replace('Z', '+00:00')).date()
                if dt_closed >= corte:
                    total += 1
            except Exception:
                pass
        return total
    except Exception:
        _log.exception('FOG encerrados semana: erro ao buscar no FogBugz')
        return 0


def buscar_movimento_semanal() -> dict:
    """Conta threads encerradas e novas na última semana (últimos 7 dias).

    Datas no banco no formato DD/MM/YYYY HH:MM — converte via substr para comparação ISO.
    """
    banco = _caminho_banco()
    if not os.path.exists(banco):
        return {'encerradas': 0, 'recebidas': 0, 'saldo': 0}
    try:
        conn = sqlite3.connect(banco)
        data_iso = (
            "substr(data_ultima_msg,7,4)||'-'||substr(data_ultima_msg,4,2)||'-'||substr(data_ultima_msg,1,2)"
        )
        data_prim_iso = (
            "substr(data_primeira_msg,7,4)||'-'||substr(data_primeira_msg,4,2)||'-'||substr(data_primeira_msg,1,2)"
        )
        (enc,) = conn.execute(
            f"""
            SELECT COUNT(*) FROM threads
            WHERE status_workflow = 'Concluída'
              AND data_ultima_msg IS NOT NULL AND data_ultima_msg != ''
              AND {data_iso} >= date('now','-7 days')
            """,
        ).fetchone()
        (rec,) = conn.execute(
            f"""
            SELECT COUNT(*) FROM threads
            WHERE data_primeira_msg IS NOT NULL AND data_primeira_msg != ''
              AND {data_prim_iso} >= date('now','-7 days')
            """,
        ).fetchone()
        conn.close()
        return {'encerradas': enc, 'recebidas': rec, 'saldo': enc - rec}
    except Exception:
        _log.exception('Resumo semanal: falha ao buscar movimento semanal.')
        return {'encerradas': 0, 'recebidas': 0, 'saldo': 0}


# ── HTML do e-mail ────────────────────────────────────────────────────────────

def _chip_recorrente() -> str:
    return (
        '<span style="display:inline-block;background:#fef3c7;color:#92400e;'
        'font-size:10px;font-weight:700;padding:1px 6px;border-radius:99px;'
        'vertical-align:middle;margin-left:4px;">recorrente</span>'
    )


def _linhas_cadoc_html(grupos: dict[str, list[str]]) -> str:
    linhas = []
    for cadoc in _CADOC_ORDER:
        empresas = grupos.get(cadoc)
        if not empresas:
            continue
        descricao = html_lib.escape(_CADOC_INFO.get(cadoc, ''))
        n = len(empresas)

        # Contagem para badge de recorrência
        contagem: dict[str, int] = defaultdict(int)
        for e in empresas:
            contagem[e.lower()] += 1

        itens_html = []
        vistos: set[str] = set()
        for emp in empresas:
            chave = emp.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            rec = _chip_recorrente() if contagem[chave] > 1 else ''
            cnt = f' ({contagem[chave]}×)' if contagem[chave] > 1 else ''
            itens_html.append(f'{html_lib.escape(emp)}{cnt}{rec}')

        empresas_html = '<br>'.join(itens_html)
        plural = 's' if n != 1 else ''

        linhas.append(
            f'<tr style="border-bottom:1px solid #e8edf5;">'
            f'<td style="padding:12px 14px;vertical-align:top;width:38%;">'
            f'<div style="font-weight:700;font-size:13px;color:#1e1e72;">{html_lib.escape(cadoc)}</div>'
            f'<div style="font-size:11.5px;color:#64748b;line-height:1.4;margin-top:3px;">{descricao}</div>'
            f'</td>'
            f'<td style="padding:12px 14px;vertical-align:top;font-size:13px;color:#1e1e72;line-height:1.7;">'
            f'{empresas_html}'
            f'</td>'
            f'<td style="padding:12px 14px;vertical-align:top;text-align:right;white-space:nowrap;">'
            f'<span style="display:inline-block;padding:2px 9px;border-radius:99px;'
            f'font-size:11.5px;font-weight:700;background:#f0f0ff;color:#3333A8;">'
            f'{n} caso{plural}</span>'
            f'</td>'
            f'</tr>'
        )
    return ''.join(linhas)


def _secao_html(titulo: str, n: int, grupos: dict[str, list[str]], cor_status: str) -> str:
    if n == 0:
        return ''
    plural = 's' if n != 1 else ''
    linhas = _linhas_cadoc_html(grupos)
    return f"""
  <tr><td style="padding:20px 32px 0;">
    <div style="background:#f8fafc;border-left:4px solid {cor_status};border-radius:0 6px 6px 0;
                padding:10px 14px;margin-bottom:12px;">
      <span style="font-size:13.5px;font-weight:700;color:#1e1e72;">{html_lib.escape(titulo)}</span>
      <span style="font-size:12px;color:#64748b;margin-left:8px;">{n} caso{plural}</span>
    </div>
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
           style="border:1px solid #c8c8e8;border-radius:8px;overflow:hidden;border-collapse:collapse;">
      <thead>
        <tr style="background:#f1f5f9;border-bottom:1px solid #c8c8e8;">
          <th style="padding:9px 14px;font-size:10.5px;font-weight:700;letter-spacing:.6px;
                     text-transform:uppercase;color:#1e1e72;text-align:left;">CADOC / Crítica</th>
          <th style="padding:9px 14px;font-size:10.5px;font-weight:700;letter-spacing:.6px;
                     text-transform:uppercase;color:#1e1e72;text-align:left;">Empresas</th>
          <th style="padding:9px 14px;width:80px;"></th>
        </tr>
      </thead>
      <tbody>{linhas}</tbody>
    </table>
  </td></tr>"""


def _fog_dias_badge(dias: int) -> str:
    if dias >= 60:
        bg, cor = '#fff1f2', '#be123c'
    elif dias >= 30:
        bg, cor = '#fff7ed', '#c2410c'
    else:
        bg, cor = '#f0f0ff', '#3333A8'
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:4px;'
        f'font-size:12px;font-weight:700;background:{bg};color:{cor};">'
        f'{dias} dias</span>'
    )


def _fog_linhas_html(dados_fog: list[dict]) -> str:
    if not dados_fog:
        return '<tr><td colspan="3" style="padding:16px;text-align:center;color:#64748b;font-size:13px;">Sem dados disponíveis.</td></tr>'
    linhas = []
    for p in dados_fog:
        nome   = html_lib.escape(p['responsavel'])
        total  = p['total']
        dias   = p['max_dias']
        badge  = _fog_dias_badge(dias)
        linhas.append(
            f'<tr style="border-bottom:1px solid #e8edf5;">'
            f'<td style="padding:10px 14px;font-size:13px;font-weight:600;color:#1e1e72;">{nome}</td>'
            f'<td style="padding:10px 14px;text-align:right;font-size:15px;font-weight:800;'
            f'color:{"#be123c" if total > 10 else "#1e1e72"};font-variant-numeric:tabular-nums;">{total}</td>'
            f'<td style="padding:10px 14px;text-align:right;">{badge}</td>'
            f'</tr>'
        )
    return ''.join(linhas)


def _delta_html(delta: int | None, invertido: bool = False) -> str:
    """Renderiza ▼▲ delta abaixo de um tile. invertido=True quando queda é ruim."""
    if delta is None:
        return ''
    if delta == 0:
        return '<div style="font-size:10px;color:#94a3b8;margin-top:3px;">sem variação</div>'
    queda = delta < 0
    bom   = queda if not invertido else not queda
    cor   = '#16a34a' if bom else '#a04800'
    seta  = '▼' if queda else '▲'
    abs_d = abs(delta)
    return (
        f'<div style="font-size:10px;font-weight:600;color:{cor};margin-top:3px;">'
        f'{seta} {abs_d} da semana anterior</div>'
    )


def _chips_movimento_html(cadoc_deltas: dict[str, int]) -> str:
    if not cadoc_deltas:
        return ''
    caindo  = [(c, d) for c, d in cadoc_deltas.items() if d < 0]
    subindo = [(c, d) for c, d in cadoc_deltas.items() if d > 0]
    caindo.sort(key=lambda x: x[1])   # mais negativo primeiro
    subindo.sort(key=lambda x: x[1], reverse=True)

    def chip_ok(cadoc: str, delta: int) -> str:
        return (
            f'<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 9px;'
            f'border-radius:4px;font-size:12px;font-weight:600;border:1px solid #a7f3d0;'
            f'background:#e8f8f0;color:#16a34a;white-space:nowrap;margin:3px 3px 0 0;">'
            f'{html_lib.escape(cadoc)} '
            f'<span style="font-size:11px;opacity:.7;font-weight:500;">▼{abs(delta)}</span></span>'
        )

    def chip_attn(cadoc: str, delta: int) -> str:
        return (
            f'<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 9px;'
            f'border-radius:4px;font-size:12px;font-weight:600;border:1px solid #fcd38d;'
            f'background:#fff4e8;color:#a04800;white-space:nowrap;margin:3px 3px 0 0;">'
            f'{html_lib.escape(cadoc)} '
            f'<span style="font-size:11px;opacity:.7;font-weight:500;">▲{delta}</span></span>'
        )

    blocos = []
    if caindo:
        chips = ''.join(chip_ok(c, d) for c, d in caindo)
        blocos.append(
            f'<div style="font-size:12px;color:#475569;margin-bottom:4px;">Fila caindo:</div>'
            f'<div style="display:flex;flex-wrap:wrap;">{chips}</div>'
        )
    if subindo:
        chips = ''.join(chip_attn(c, d) for c, d in subindo)
        blocos.append(
            f'<div style="font-size:12px;color:#475569;margin-top:10px;margin-bottom:4px;">Merece atenção:</div>'
            f'<div style="display:flex;flex-wrap:wrap;">{chips}</div>'
        )
    return ''.join(blocos)


def _gerar_narrativa(
    movimento: dict,
    finaud: int,
    fog_encerrados: int,
    deltas: dict | None = None,
) -> str:
    """Gera o parágrafo narrativo do resumo com base em números reais."""
    enc = movimento.get('encerradas', 0)
    rec = movimento.get('recebidas', 0)
    saldo = enc - rec

    if enc == 0 and rec == 0:
        return ''

    plural_enc = 's' if enc != 1 else ''
    plural_rec = 's' if rec != 1 else ''

    if saldo > 0:
        saldo_txt = f'<b>{saldo}</b> a mais do que as {rec} recebidas'
    elif saldo < 0:
        saldo_txt = f'<b>{abs(saldo)}</b> a menos do que as {rec} recebidas'
    else:
        saldo_txt = f'exatamente o mesmo número de threads recebidas (<b>{rec}</b>)'

    linha1 = (
        f'Nesta semana, <b>{enc}</b> thread{plural_enc} foram encerradas'
        f' — {saldo_txt}.'
    )

    linha2 = ''
    if finaud > 0:
        plural_fin = 's' if finaud != 1 else ''
        linha2 = (
            f' Das threads abertas do BACEN, <b>{finaud}</b> caso{plural_fin}'
            f' aguardam retorno da Finaud.'
        )

    linha3 = ''
    if fog_encerrados > 0:
        plural_fog = 's' if fog_encerrados != 1 else ''
        linha3 = (
            f' No FogBugz, <b>{fog_encerrados}</b> caso{plural_fog}'
            f' foram encerrados na semana.'
        )

    return linha1 + linha2 + linha3


def montar_html_resumo_semanal(
    nome: str,
    dados: dict,
    data_envio: str,
    dia_semana_label: str,
    dados_fog: list[dict] | None = None,
    deltas: dict | None = None,
    movimento: dict | None = None,
    fog_encerrados: int = 0,
) -> str:
    total   = dados.get('total', 0)
    cliente = dados.get('cliente', 0)
    finaud  = dados.get('finaud', 0)
    por_st  = dados.get('por_status', {})
    grp_cli = por_st.get('Aguardando Cliente', {})
    grp_fin = por_st.get('Aguardando Finaud', {})
    fog_total = sum(p['total'] for p in (dados_fog or []))

    mv       = movimento or {}
    enc      = mv.get('encerradas', 0)
    rec      = mv.get('recebidas',  0)
    saldo    = enc - rec

    saudacao = f'Olá, <b>{html_lib.escape(nome)}</b>,' if nome else 'Olá,'
    d_seg    = html_lib.escape(data_envio)
    dia_seg  = html_lib.escape(dia_semana_label)

    sec_cliente = _secao_html('Aguardando Cliente', cliente, grp_cli, '#f59e0b')
    sec_finaud  = _secao_html('Aguardando Finaud',  finaud,  grp_fin, '#3333A8')

    if total == 0:
        corpo_bacen = '<tr><td style="padding:32px;text-align:center;color:#64748b;font-size:14px;">Nenhum retorno BACEN em aberto esta semana.</td></tr>'
    else:
        corpo_bacen = sec_cliente + sec_finaud

    fog_linhas = _fog_linhas_html(dados_fog or [])

    # Deltas — só exibe quando snapshot disponível
    d = deltas or {}
    delta_af  = _delta_html(d.get('af'))
    delta_fog = _delta_html(d.get('fog'))

    # Tile 1 — saldo encerradas vs recebidas
    if saldo > 0:
        tile1_num = f'+{saldo}'
        tile1_cor_num = '#15803d'
        tile1_bg  = '#f0fdf4'
        tile1_bor = '#bbf7d0'
    elif saldo < 0:
        tile1_num = str(saldo)
        tile1_cor_num = '#be123c'
        tile1_bg  = '#fff1f2'
        tile1_bor = '#fecdd3'
    else:
        tile1_num = '0'
        tile1_cor_num = '#475569'
        tile1_bg  = '#f8fafc'
        tile1_bor = '#cbd5e1'
    tile1_sub = f'<div style="font-size:9.5px;color:#64748b;margin-top:3px;">de {enc} enc. / {rec} rec.</div>' if enc or rec else ''

    # Narrativa
    narrativa_txt = _gerar_narrativa(mv, finaud, fog_encerrados, d)
    secao_narrativa = ''
    if narrativa_txt:
        secao_narrativa = f"""
  <tr><td style="padding:16px 32px 0;">
    <p style="margin:0;font-size:13.5px;color:#334155;line-height:1.7;
              background:#f8fafc;border-left:3px solid {_VERDE};
              border-radius:0 6px 6px 0;padding:12px 16px;">
      {narrativa_txt}
    </p>
  </td></tr>"""

    # Seção "O que aconteceu nos e-mails" — narrativa + chips por categoria
    chips_mvmt = _chips_movimento_html(d.get('cadoc', {}))
    secao_mvmt = ''
    if chips_mvmt:
        secao_mvmt = f"""
  <tr><td style="padding:20px 32px 0;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
      <span style="font-size:13px;font-weight:700;color:#1c2b4a;text-transform:uppercase;letter-spacing:.08em;">Movimento por categoria</span>
      <div style="flex:1;height:1px;background:#e2e8f0;"></div>
    </div>
    {chips_mvmt}
  </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{html_lib.escape(_ASSUNTO_EMAIL)}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f1f5f9;">
<tr><td align="center" style="padding:32px 12px;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="640"
       style="max-width:640px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;
              box-shadow:0 4px 20px rgba(15,23,42,.08);border:1px solid #c8c8e8;">

  <!-- Cabeçalho -->
  <tr><td style="background:linear-gradient(135deg,{_BG_HEADER} 0%,{_BG_GRAD} 100%);padding:28px 32px 24px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:{_VERDE};text-transform:uppercase;margin-bottom:10px;">
      GESTÃO ÁREA SUPORTE
    </div>
    <div style="font-size:24px;font-weight:700;color:#ffffff;line-height:1.2;">
      Resumo Semanal
    </div>
    <div style="font-size:13px;color:#c8c8e8;margin-top:6px;">
      Referência: semana encerrada em {d_seg}
    </div>
  </td></tr>

  <!-- Saudação -->
  <tr><td style="padding:24px 32px 0;color:#1e1e72;font-size:14.5px;line-height:1.65;">
    <p style="margin:0 0 8px;">{saudacao}</p>
    <p style="margin:0;color:#475569;">
      Segue o consolidado da área de suporte nesta {dia_seg}.
    </p>
  </td></tr>

  {secao_narrativa}

  <!-- Destaques — 4 tiles -->
  <tr><td style="padding:20px 32px 0;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
      <tr>
        <td style="width:25%;padding:0 5px 0 0;">
          <div style="background:{tile1_bg};border:1px solid {tile1_bor};border-radius:8px;padding:14px 10px;text-align:center;">
            <div style="font-size:26px;font-weight:900;color:{tile1_cor_num};line-height:1;font-variant-numeric:tabular-nums;">{tile1_num}</div>
            <div style="font-size:10px;color:#6b7a9a;margin-top:4px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Enc. a mais</div>
            {tile1_sub}
          </div>
        </td>
        <td style="width:25%;padding:0 5px;">
          <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:8px;padding:14px 10px;text-align:center;">
            <div style="font-size:26px;font-weight:900;color:#3333A8;line-height:1;font-variant-numeric:tabular-nums;">{enc}</div>
            <div style="font-size:10px;color:#6b7a9a;margin-top:4px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Encerramentos</div>
          </div>
        </td>
        <td style="width:25%;padding:0 5px;">
          <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:8px;padding:14px 10px;text-align:center;">
            <div style="font-size:26px;font-weight:900;color:#4338CA;line-height:1;font-variant-numeric:tabular-nums;">{finaud}</div>
            <div style="font-size:10px;color:#4338CA;margin-top:4px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;opacity:.85;">Ag. Finaud</div>
            {delta_af}
          </div>
        </td>
        <td style="width:25%;padding:0 0 0 5px;">
          <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:14px 10px;text-align:center;">
            <div style="font-size:26px;font-weight:900;color:#15803d;line-height:1;font-variant-numeric:tabular-nums;">{fog_encerrados}</div>
            <div style="font-size:10px;color:#166534;margin-top:4px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">FOG encerrados</div>
            {delta_fog}
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- Separador BACEN -->
  <tr><td style="padding:24px 32px 0;">
    <div style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:13px;font-weight:700;color:#a04800;text-transform:uppercase;letter-spacing:.08em;">Retorno BACEN</span>
      <div style="flex:1;height:1px;background:#e2e8f0;"></div>
    </div>
  </td></tr>

  {corpo_bacen}

  {secao_mvmt}

  <!-- Nota BACEN -->
  <tr><td style="padding:16px 32px 0;">
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid {_VERDE};
                border-radius:0 6px 6px 0;padding:10px 14px;font-size:12px;color:#64748b;line-height:1.5;">
      A badge <span style="background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;
      padding:1px 6px;border-radius:99px;">recorrente</span> indica empresa que aparece mais de uma vez no mesmo grupo CADOC.
    </div>
  </td></tr>

  <!-- Separador FOG -->
  <tr><td style="padding:24px 32px 0;">
    <div style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:13px;font-weight:700;color:#1c2b4a;text-transform:uppercase;letter-spacing:.08em;">FogBugz — casos em aberto</span>
      <div style="flex:1;height:1px;background:#e2e8f0;"></div>
    </div>
  </td></tr>

  <!-- Tabela FOG -->
  <tr><td style="padding:12px 32px 0;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
           style="border:1px solid #c8c8e8;border-radius:8px;overflow:hidden;border-collapse:collapse;">
      <thead>
        <tr style="background:#f1f5f9;border-bottom:2px solid #c8c8e8;">
          <th style="padding:9px 14px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6b7a9a;text-align:left;">Responsável</th>
          <th style="padding:9px 14px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6b7a9a;text-align:right;">Em aberto</th>
          <th style="padding:9px 14px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6b7a9a;text-align:right;">Parado há (dias úteis)</th>
        </tr>
      </thead>
      <tbody>{fog_linhas}</tbody>
    </table>
    <p style="font-size:10.5px;color:#94a3b8;margin-top:8px;font-style:italic;">
      "Parado há" = dias úteis desde a última atualização no FogBugz. Dados de {d_seg}.
    </p>
  </td></tr>

  <!-- Rodapé -->
  <tr><td style="padding:20px 32px 24px;border-top:1px solid #c8c8e8;margin-top:20px;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
      <tr>
        <td style="font-size:11.5px;color:#8899bb;line-height:1.5;">
          Enviado toda {dia_seg}.<br>
          E-mails: gestao.db · FogBugz: API finaud.fogbugz.com<br>
          <span style="color:#b0bdd4;">Para parar de receber, acesse Notificações no sistema.</span>
        </td>
        <td align="right" valign="bottom">
          <div style="font-size:14px;font-weight:900;color:{_VERDE};letter-spacing:1px;">finaud</div>
        </td>
      </tr>
    </table>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── Envio SMTP ────────────────────────────────────────────────────────────────

def _smtp_credenciais() -> tuple[str, str]:
    remetente = (
        os.environ.get('EMAIL_USER')
        or os.environ.get('GMAIL_USER')
        or 'coleta.oraculo@finaud.com.br'
    )
    senha = os.environ.get('EMAIL_PASS') or os.environ.get('GMAIL_APP_PASS') or ''
    return remetente, senha


def enviar_resumo_semanal(destino: str, corpo_html: str) -> bool:
    remetente, senha = _smtp_credenciais()
    if not senha or not (destino or '').strip():
        _log.warning('Resumo BACEN: sem credenciais SMTP ou destinatário vazio.')
        return False
    msg = MIMEMultipart()
    msg['From']    = remetente
    msg['To']      = destino.strip()
    msg['Subject'] = _ASSUNTO_EMAIL
    msg.attach(MIMEText(corpo_html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as s:
            s.starttls()
            s.login(remetente, senha)
            s.send_message(msg)
        _log.info('Resumo BACEN: enviado para %s', destino)
        return True
    except Exception:
        _log.exception('Resumo BACEN: falha ao enviar para %s', destino)
        return False


def _destinatarios(grupos: list, admin_email: str, usuarios=None) -> list[str]:
    grupos_ok = [g for g in (grupos or []) if g in _GRUPOS_NOTIF]
    saida: list[str] = []
    admin = (admin_email or '').strip()
    if 'administrador' in grupos_ok and admin:
        saida.append(admin.lower())
    for u in usuarios or []:
        if not isinstance(u, dict) or u.get('ativo') is False:
            continue
        perfil = str(u.get('perfil') or '').strip().lower()
        email  = str(u.get('email') or '').strip()
        if perfil in grupos_ok and email:
            saida.append(email.lower())
    vistos: set[str] = set()
    unicos: list[str] = []
    for e in saida:
        if e not in vistos:
            vistos.add(e)
            unicos.append(e)
    return unicos


# ── Verificação e disparo ─────────────────────────────────────────────────────

def verificar_e_enviar_resumo_semanal(
    cfg: dict,
    *,
    admin_email: str,
    agora: datetime | None = None,
    enviar=None,
) -> tuple[dict, bool]:
    """Verifica se deve enviar o resumo hoje e envia. Retorna (cfg_atualizado, enviou)."""
    cfg   = dict(cfg or {})
    agora = agora or datetime.now(timezone.utc)

    cfg_notif = normalizar_resumo_semanal(cfg.get('resumo_semanal'))
    if not cfg_notif.get('ativa'):
        return cfg, False

    if agora.weekday() != cfg_notif.get('dia_semana', 0):
        return cfg, False

    hoje_str = agora.date().isoformat()
    if cfg.get('resumo_semanal_ultimo_envio') == hoje_str:
        return cfg, False

    dados = buscar_dados_bacen()
    if not dados or dados.get('total', 0) == 0:
        _log.info('Resumo semanal: nenhum caso BACEN em aberto — e-mail não enviado.')
        return cfg, False

    fog_token      = cfg.get('fogbugz_token') or os.environ.get('FOGBUGZ_TOKEN', '')
    dados_fog      = buscar_dados_fog_semanal(fog_token)
    fog_enc        = buscar_fog_encerrados_semana(fog_token)
    movimento      = buscar_movimento_semanal()

    # Tentar carregar snapshot da sexta anterior para calcular deltas
    from snapshot_semanal import carregar_ultimo_snapshot, calcular_deltas
    snapshot = carregar_ultimo_snapshot(antes_de=agora.date().isoformat())
    deltas = calcular_deltas(snapshot, dados, dados_fog) if snapshot else None
    if snapshot:
        _log.info('Resumo semanal: snapshot de %s carregado para deltas.', snapshot.get('data'))
    else:
        _log.info('Resumo semanal: sem snapshot anterior — deltas não exibidos.')

    destinos = _destinatarios(cfg_notif['grupos'], admin_email, cfg.get('usuarios'))
    if not destinos:
        _log.warning('Resumo semanal: notificação ligada mas sem destinatários configurados.')
        return cfg, False

    dia_label  = _DIAS_SEMANA[cfg_notif.get('dia_semana', 0)]
    data_envio = agora.strftime('%d/%m/%Y')
    fn_enviar  = enviar or enviar_resumo_semanal

    algum = False
    for destino in destinos:
        nome_dest = (destino.split('@')[0].split('.')[0] or '').capitalize()
        html = montar_html_resumo_semanal(
            nome_dest, dados, data_envio, dia_label,
            dados_fog, deltas, movimento, fog_enc,
        )
        if fn_enviar(destino, html):
            algum = True

    if algum:
        cfg['resumo_semanal_ultimo_envio'] = hoje_str
    return cfg, algum
