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
        # Seta o filtro antes de buscar (mesma lógica dos casos abertos)
        requests.get(_FOGBUGZ_URL, params={
            'token': token, 'cmd': 'setCurrentFilter', 'sFilter': _FOGBUGZ_FILTER,
        }, timeout=10)
        resp = requests.get(_FOGBUGZ_URL, params={
            'token': token,
            'cmd': 'search',
            'q': f'status:closed closed:">={corte_str}"',
            'cols': 'ixBug,dtClosed',
            'max': '500',
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


# ── Badge de CADOC colorido (inline CSS para e-mail) ─────────────────────────

_CBADGE_ESTILOS: dict[str, str] = {
    'DRM 2060':          'background:#fff4e8;color:#7c2d00;border:1px solid #fcd38d;',
    'DLO 2061':          'background:#fef3c7;color:#78350f;border:1px solid #fde68a;',
    'DDR 2011':          'background:#f0fdf4;color:#14532d;border:1px solid #bbf7d0;',
    'LIM 2061':          'background:#f0f4ff;color:#312e81;border:1px solid #c7d2fe;',
    'DLI 2062':          'background:#fdf4ff;color:#6b21a8;border:1px solid #e9d5ff;',
    'COSIF 4111':        'background:#fef9c3;color:#713f12;border:1px solid #fde68a;',
    'COSIF 4010/4016':   'background:#fef9c3;color:#713f12;border:1px solid #fde68a;',
    'DRL 2160':          'background:#f0f9ff;color:#0c4a6e;border:1px solid #bae6fd;',
    'Atraso em remessa': 'background:#fafafa;color:#52525b;border:1px solid #d4d4d8;',
    'Outros':            'background:#fafafa;color:#52525b;border:1px solid #d4d4d8;',
}


def _cbadge_email(cadoc: str) -> str:
    estilo = _CBADGE_ESTILOS.get(cadoc, 'background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;')
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'font-size:11px;font-weight:700;white-space:nowrap;{estilo}">'
        f'{html_lib.escape(cadoc)}</span>'
    )


def _bacen_totais_html(total: int, cliente: int, finaud: int) -> str:
    return (
        f'<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0"'
        f' style="margin-bottom:18px;">'
        f'<tr>'
        f'<td style="width:33%;padding-right:8px;">'
        f'<div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:6px;padding:10px 12px;">'
        f'<div style="font-size:22px;font-weight:800;color:#1c2b4a;font-variant-numeric:tabular-nums;">{total}</div>'
        f'<div style="font-size:10.5px;font-weight:600;color:#6b7a9a;margin-top:2px;">Total em aberto</div>'
        f'</div></td>'
        f'<td style="width:33%;padding-right:8px;">'
        f'<div style="background:#fffbeb;border:1px solid #fcd38d;border-radius:6px;padding:10px 12px;">'
        f'<div style="font-size:22px;font-weight:800;color:#b45309;font-variant-numeric:tabular-nums;">{cliente}</div>'
        f'<div style="font-size:10.5px;font-weight:600;color:#b45309;opacity:.85;margin-top:2px;">Aguardando cliente</div>'
        f'</div></td>'
        f'<td style="width:33%;">'
        f'<div style="background:#f0f4ff;border:1px solid #c7d2fe;border-radius:6px;padding:10px 12px;">'
        f'<div style="font-size:22px;font-weight:800;color:#4338CA;font-variant-numeric:tabular-nums;">{finaud}</div>'
        f'<div style="font-size:10.5px;font-weight:600;color:#4338CA;opacity:.85;margin-top:2px;">Aguardando Finaud</div>'
        f'</div></td>'
        f'</tr></table>'
    )


def _bacen_cards_email(
    grupos: dict[str, list[str]],
    cor_borda: str,
    cor_pill_bg: str,
    cor_pill_txt: str,
    cor_pill_bor: str,
) -> str:
    cards: list[str] = []
    for cadoc in _CADOC_ORDER:
        empresas = grupos.get(cadoc)
        if not empresas:
            continue
        descricao = html_lib.escape(_CADOC_INFO.get(cadoc, ''))
        n = len(empresas)
        contagem: dict[str, int] = defaultdict(int)
        for e in empresas:
            contagem[e.lower()] += 1
        itens: list[str] = []
        vistos: set[str] = set()
        for emp in empresas:
            chave = emp.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            esc = html_lib.escape(emp)
            if contagem[chave] > 1:
                rec_badge = (
                    f'<span style="display:inline-block;padding:1px 6px;border-radius:10px;'
                    f'font-size:10px;font-weight:700;background:#fff4e8;color:#a04800;'
                    f'border:1px solid #fcd38d;">{contagem[chave]}×</span>'
                )
                itens.append(f'{esc}&nbsp;{rec_badge}')
            else:
                itens.append(esc)
        empresas_txt = ' &nbsp;·&nbsp; '.join(itens)
        badge = _cbadge_email(cadoc)
        cards.append(
            f'<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0"'
            f' style="border:1px solid #e8edf5;border-left:3px solid {cor_borda};'
            f'border-radius:7px;margin-bottom:8px;">'
            f'<tr><td style="background:#f8fafc;padding:9px 12px;border-bottom:1px solid #e8edf5;">'
            f'<table width="100%" border="0" cellspacing="0" cellpadding="0"><tr>'
            f'<td style="vertical-align:top;padding-right:10px;">'
            f'{badge}'
            f'<div style="font-size:11.5px;color:#475569;line-height:1.4;margin-top:4px;">{descricao}</div>'
            f'</td>'
            f'<td style="text-align:right;white-space:nowrap;vertical-align:top;">'
            f'<span style="display:inline-block;min-width:36px;padding:4px 10px;border-radius:20px;'
            f'font-size:14px;font-weight:800;text-align:center;font-variant-numeric:tabular-nums;'
            f'background:{cor_pill_bg};color:{cor_pill_txt};border:1px solid {cor_pill_bor};">{n}</span>'
            f'</td>'
            f'</tr></table>'
            f'</td></tr>'
            f'<tr><td style="padding:8px 12px;font-size:12.5px;color:#1c2b4a;line-height:1.7;">'
            f'{empresas_txt}'
            f'</td></tr>'
            f'</table>'
        )
    return ''.join(cards)


def _o_que_aconteceu_corpo(
    movimento: dict,
    dados: dict,
    deltas: dict | None,
    fog_encerrados: int,
) -> str:
    enc     = movimento.get('encerradas', 0)
    rec     = movimento.get('recebidas',  0)
    saldo   = enc - rec
    total   = dados.get('total', 0)
    cliente = dados.get('cliente', 0)
    finaud  = dados.get('finaud', 0)

    partes: list[str] = []
    if enc or rec:
        if saldo > 0:
            tendencia = (
                f'a equipe encerrou <b style="color:#16a34a;">{saldo} casos a mais</b>'
                f' do que recebeu'
            )
        elif saldo < 0:
            tendencia = (
                f'a fila cresceu <b style="color:#a04800;">{abs(saldo)} casos</b>'
                f' além do que foi resolvido'
            )
        else:
            tendencia = f'o volume de encerramentos igualou o de entradas (<b>{enc}</b>)'
        partes.append(
            f'Foram recebidas <b>{rec}</b> threads e encerradas <b>{enc}</b> — {tendencia}.'
        )

    if total > 0:
        partes.append(
            f'No Retorno BACEN, há <b>{total}</b> casos em aberto: '
            f'<b>{cliente}</b> aguardam resposta dos clientes e <b>{finaud}</b> aguardam a Finaud.'
        )

    if fog_encerrados > 0:
        plural = 's' if fog_encerrados != 1 else ''
        partes.append(
            f'No FogBugz, <b>{fog_encerrados}</b> caso{plural} foram encerrados na semana.'
        )

    if not partes:
        return ''

    texto = ' '.join(partes)
    nota  = ''
    if not deltas:
        nota = (
            '<div style="font-size:11px;color:#94a3b8;margin-top:10px;font-style:italic;">'
            'Comparação por categoria com a semana anterior estará disponível a partir da próxima segunda-feira.'
            '</div>'
        )
    return f'<div style="font-size:13.5px;line-height:1.75;color:#1c2b4a;">{texto}</div>{nota}'


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

    mv    = movimento or {}
    enc   = mv.get('encerradas', 0)
    rec   = mv.get('recebidas',  0)
    saldo = enc - rec

    nome_esc = html_lib.escape(nome) if nome else ''
    d_seg    = html_lib.escape(data_envio)
    dia_seg  = html_lib.escape(dia_semana_label)
    d = deltas or {}

    # ── Narrativa (parágrafo antes dos tiles) ─────────────────────────────────
    narrativa_txt = _gerar_narrativa(mv, finaud, fog_encerrados, d)

    # ── Tiles 2×2 ─────────────────────────────────────────────────────────────
    if saldo > 0:
        t1_val, t1_cor = f'+{saldo}', '#16a34a'
        t1_sub = '<div style="font-size:11px;font-weight:600;color:#16a34a;margin-top:2px;">▼ do que na semana anterior</div>'
    elif saldo < 0:
        t1_val, t1_cor = str(saldo), '#a04800'
        t1_sub = '<div style="font-size:11px;font-weight:600;color:#a04800;margin-top:2px;">▲ do que na semana anterior</div>'
    else:
        t1_val, t1_cor = '0', '#475569'
        t1_sub = '<div style="font-size:11px;color:#94a3b8;margin-top:2px;">sem variação</div>'
    if enc or rec:
        t1_sub += f'<div style="font-size:10px;color:#94a3b8;margin-top:1px;">de {enc} enc. / {rec} rec.</div>'

    af_delta_html = _delta_html(d.get('af'))
    fog_delta_html = _delta_html(d.get('fog'))
    t4_cor = '#a04800' if fog_encerrados == 0 else '#16a34a'

    # ── "O que aconteceu nos e-mails" ─────────────────────────────────────────
    oqae_corpo = _o_que_aconteceu_corpo(mv, dados, deltas, fog_encerrados)
    chips_mvmt = _chips_movimento_html(d.get('cadoc', {}))
    secao_chips = ''
    if chips_mvmt:
        secao_chips = (
            f'<div style="margin-top:16px;padding-top:14px;border-top:1px solid #e8edf5;">'
            f'<div style="font-size:12px;font-weight:700;color:#1c2b4a;margin-bottom:8px;">Movimento por categoria</div>'
            f'{chips_mvmt}</div>'
        )

    # ── Seção BACEN ───────────────────────────────────────────────────────────
    bacen_totais = _bacen_totais_html(total, cliente, finaud)
    if total == 0:
        bacen_corpo = (
            '<div style="padding:24px;text-align:center;color:#6b7a9a;font-size:14px;">'
            'Nenhum retorno BACEN em aberto esta semana.</div>'
        )
    else:
        cards_cli = _bacen_cards_email(grp_cli, '#f59e0b', '#fffbeb', '#b45309', '#fcd38d')
        cards_fin = _bacen_cards_email(grp_fin, '#6366f1', '#eef2ff', '#4338CA', '#c7d2fe')
        grupo_cli = ''
        if cliente > 0:
            plural = 's' if cliente != 1 else ''
            grupo_cli = (
                f'<div style="font-size:12px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;padding:6px 10px;border-radius:5px;margin-bottom:8px;'
                f'background:#fffbeb;color:#b45309;border:1px solid #fde68a;">'
                f'Aguardando cliente — o cliente precisa responder'
                f'<span style="font-size:11px;font-weight:500;opacity:.75;margin-left:6px;">'
                f'{cliente} caso{plural}</span></div>'
                + cards_cli
            )
        grupo_fin = ''
        if finaud > 0:
            plural = 's' if finaud != 1 else ''
            grupo_fin = (
                f'<div style="font-size:12px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;padding:6px 10px;border-radius:5px;'
                f'margin-top:16px;margin-bottom:8px;'
                f'background:#eef2ff;color:#4338CA;border:1px solid #c7d2fe;">'
                f'Aguardando Finaud — a Finaud precisa agir'
                f'<span style="font-size:11px;font-weight:500;opacity:.75;margin-left:6px;">'
                f'{finaud} caso{plural}</span></div>'
                + cards_fin
            )
        bacen_corpo = grupo_cli + grupo_fin

    # ── FOG ───────────────────────────────────────────────────────────────────
    fog_linhas = _fog_linhas_html(dados_fog or [])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Gestão Área Suporte — Resumo Semanal</title>
</head>
<body style="margin:0;padding:24px 12px 48px;background:#f7f8fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#1c2b4a;">

<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width:720px;margin:0 auto;">
<tr><td>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 12px rgba(0,0,0,.08);">

  <!-- CABEÇALHO -->
  <tr><td style="background:#4338CA;padding:28px 32px 24px;">
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:rgba(255,255,255,.55);margin-bottom:6px;">
      Gestão Área Suporte
    </div>
    <div style="font-size:26px;font-weight:800;color:#ffffff;letter-spacing:-.02em;line-height:1.15;">
      Resumo Semanal
    </div>
    <div style="font-size:12px;color:rgba(255,255,255,.6);margin-top:8px;">
      Retorno Bacen: posição em {d_seg}
    </div>
  </td></tr>

  <!-- SAUDAÇÃO + NARRATIVA -->
  <tr><td style="padding:28px 32px 0;">
    <div style="font-size:15px;margin-bottom:14px;">
      Olá, <b style="color:#4338CA;">{nome_esc}</b>,
    </div>
    <div style="font-size:15px;line-height:1.7;color:#1c2b4a;margin-bottom:20px;">
      {narrativa_txt}
    </div>

    <!-- DESTAQUES 2×2 -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
           style="background:#f7f8fa;border:1px solid #dde2ec;border-radius:7px;margin-bottom:0;">
      <tr>
        <td style="padding:14px 18px 7px;width:50%;vertical-align:top;">
          <div style="font-size:22px;font-weight:800;color:{t1_cor};font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1;">{t1_val}</div>
          <div style="font-size:11px;color:#6b7a9a;font-weight:500;margin-top:3px;">Casos encerrados a mais</div>
          {t1_sub}
        </td>
        <td style="padding:14px 18px 7px;width:50%;vertical-align:top;">
          <div style="font-size:22px;font-weight:800;color:#16a34a;font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1;">{enc}</div>
          <div style="font-size:11px;color:#6b7a9a;font-weight:500;margin-top:3px;">Novos encerramentos</div>
          <div style="font-size:11px;font-weight:600;color:#16a34a;margin-top:2px;">concluídos esta semana</div>
        </td>
      </tr>
      <tr>
        <td style="padding:7px 18px 14px;width:50%;vertical-align:top;border-top:1px solid #e8edf5;">
          <div style="font-size:22px;font-weight:800;color:#4338CA;font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1;">{finaud}</div>
          <div style="font-size:11px;color:#6b7a9a;font-weight:500;margin-top:3px;">Aguardando Finaud</div>
          {af_delta_html}
        </td>
        <td style="padding:7px 18px 14px;width:50%;vertical-align:top;border-top:1px solid #e8edf5;">
          <div style="font-size:22px;font-weight:800;color:{t4_cor};font-variant-numeric:tabular-nums;letter-spacing:-.02em;line-height:1;">{fog_encerrados}</div>
          <div style="font-size:11px;color:#6b7a9a;font-weight:500;margin-top:3px;">FogBugz — encerrados</div>
          {fog_delta_html}
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- HR -->
  <tr><td style="padding:24px 32px 0;"><div style="border-top:1px solid #dde2ec;"></div></td></tr>

  <!-- O QUE ACONTECEU NOS E-MAILS -->
  <tr><td style="padding:20px 32px 24px;">
    <div style="font-size:13px;font-weight:700;color:#1c2b4a;margin-bottom:10px;">
      O que aconteceu nos e-mails
      <span style="display:inline-block;width:60px;height:1px;background:#dde2ec;vertical-align:middle;margin-left:10px;"></span>
    </div>
    {oqae_corpo}
    {secao_chips}
  </td></tr>

  <!-- HR -->
  <tr><td style="padding:0 32px;"><div style="border-top:1px solid #dde2ec;"></div></td></tr>

  <!-- RETORNO BACEN -->
  <tr><td style="padding:24px 32px 0;">
    <div style="font-size:13px;font-weight:700;color:#a04800;margin-bottom:14px;">
      Retorno Bacen
      <span style="display:inline-block;width:60px;height:1px;background:#dde2ec;vertical-align:middle;margin-left:10px;"></span>
    </div>
    {bacen_totais}
    {bacen_corpo}
  </td></tr>

  <!-- HR -->
  <tr><td style="padding:24px 32px 8px;"><div style="border-top:1px solid #dde2ec;"></div></td></tr>

  <!-- FOGBUGZ -->
  <tr><td style="padding:0 32px 0;">
    <div style="font-size:13px;font-weight:700;color:#1c2b4a;margin-bottom:12px;">
      FogBugz — Casos em aberto ({fog_total} no total)
      <span style="display:inline-block;width:40px;height:1px;background:#dde2ec;vertical-align:middle;margin-left:10px;"></span>
    </div>
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
           style="border-collapse:collapse;border:1px solid #dde2ec;border-radius:7px;overflow:hidden;">
      <thead>
        <tr style="background:#f7f8fa;border-bottom:2px solid #dde2ec;">
          <th style="padding:8px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6b7a9a;text-align:left;">Responsável</th>
          <th style="padding:8px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6b7a9a;text-align:right;">Em aberto</th>
          <th style="padding:8px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#6b7a9a;text-align:right;">Parado há (dias úteis)</th>
        </tr>
      </thead>
      <tbody>{fog_linhas}</tbody>
    </table>
    <p style="font-size:10.5px;color:#94a3b8;margin-top:8px;font-style:italic;">
      "Parado há" = dias úteis desde a última atualização no FogBugz. Dados de {d_seg}.
    </p>
  </td></tr>

  <!-- RODAPÉ -->
  <tr><td style="padding:16px 32px;border-top:1px solid #dde2ec;margin-top:8px;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
      <tr>
        <td style="font-size:10.5px;color:#6b7a9a;line-height:1.5;">
          Enviado toda {dia_seg}.<br>
          E-mails: gestao.db · FogBugz: finaud.fogbugz.com
        </td>
        <td align="right" valign="middle">
          <span style="font-size:14px;font-weight:900;color:{_VERDE};letter-spacing:1px;">finaud</span>
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
