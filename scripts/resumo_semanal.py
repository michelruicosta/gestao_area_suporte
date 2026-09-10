"""Resumo semanal de retornos BACEN — enviado toda segunda-feira para grupos configurados."""
from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import smtplib
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_log = logging.getLogger(__name__)

_NOTIF_ID      = 'resumo_semanal'
_GRUPOS_NOTIF  = ('administrador', 'gestor', 'operador')
_ASSUNTO_EMAIL = 'Gestão Área Suporte — Resumo Semanal Retorno BACEN'
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


def montar_html_resumo_semanal(
    nome: str,
    dados: dict,
    data_envio: str,
    dia_semana_label: str,
) -> str:
    total   = dados.get('total', 0)
    cliente = dados.get('cliente', 0)
    finaud  = dados.get('finaud', 0)
    por_st  = dados.get('por_status', {})
    grp_cli = por_st.get('Aguardando Cliente', {})
    grp_fin = por_st.get('Aguardando Finaud', {})

    saudacao = f'Olá, <b>{html_lib.escape(nome)}</b>,' if nome else 'Olá,'
    d_seg    = html_lib.escape(data_envio)
    dia_seg  = html_lib.escape(dia_semana_label)

    sec_cliente = _secao_html('Aguardando Cliente', cliente, grp_cli, '#f59e0b')
    sec_finaud  = _secao_html('Aguardando Finaud',  finaud,  grp_fin, '#3333A8')

    if total == 0:
        corpo = '<tr><td style="padding:32px;text-align:center;color:#64748b;font-size:14px;">Nenhum retorno BACEN em aberto esta semana.</td></tr>'
    else:
        corpo = sec_cliente + sec_finaud

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
    <div style="font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">
      Resumo Semanal — Retorno BACEN
    </div>
    <div style="font-size:13px;color:#c8c8e8;margin-top:6px;">
      Referência: semana encerrada em {d_seg}
    </div>
  </td></tr>

  <!-- Saudação -->
  <tr><td style="padding:24px 32px 0;color:#1e1e72;font-size:14.5px;line-height:1.65;">
    <p style="margin:0 0 14px;">{saudacao}</p>
    <p style="margin:0;">
      Segue o consolidado dos retornos do BACEN em aberto nesta {dia_seg}.
    </p>
  </td></tr>

  <!-- Totalizadores -->
  <tr><td style="padding:16px 32px 0;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
      <tr>
        <td style="width:33%;padding:0 6px 0 0;">
          <div style="background:#f0f0ff;border:1px solid #c8c8e8;border-radius:8px;padding:14px;text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#3333A8;line-height:1;">{total}</div>
            <div style="font-size:11px;color:#64748b;margin-top:4px;font-weight:600;">EM ABERTO</div>
          </div>
        </td>
        <td style="width:33%;padding:0 3px;">
          <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:14px;text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#92400e;line-height:1;">{cliente}</div>
            <div style="font-size:11px;color:#92400e;margin-top:4px;font-weight:600;">AG. CLIENTE</div>
          </div>
        </td>
        <td style="width:33%;padding:0 0 0 6px;">
          <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:14px;text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#1d4ed8;line-height:1;">{finaud}</div>
            <div style="font-size:11px;color:#1d4ed8;margin-top:4px;font-weight:600;">AG. FINAUD</div>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  {corpo}

  <!-- Nota rodapé -->
  <tr><td style="padding:20px 32px 0;">
    <div style="background:#f0f0ff;border:1px solid #c8c8e8;border-left:4px solid {_VERDE};
                border-radius:8px;padding:12px 16px;font-size:12.5px;color:#64748b;line-height:1.55;">
      Relatório automático gerado toda <b>{dia_seg}</b> com base na situação dos casos no sistema.
      A badge <span style="background:#fef3c7;color:#92400e;font-size:10px;font-weight:700;
      padding:1px 6px;border-radius:99px;">recorrente</span> indica empresa que aparece mais de uma vez no mesmo grupo CADOC.
    </div>
  </td></tr>

  <!-- Rodapé -->
  <tr><td style="padding:20px 32px 24px;border-top:1px solid #c8c8e8;margin-top:20px;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
      <tr>
        <td style="font-size:11.5px;color:#8899bb;line-height:1.5;">
          Este e-mail foi enviado automaticamente pelo sistema
          <b style="color:#3333A8;">Gestão Área Suporte</b>.<br>
          Para parar de receber, acesse Notificações no sistema.
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
        _log.info('Resumo BACEN: nenhum caso em aberto — e-mail não enviado.')
        return cfg, False

    destinos = _destinatarios(cfg_notif['grupos'], admin_email, cfg.get('usuarios'))
    if not destinos:
        _log.warning('Resumo BACEN: notificação ligada mas sem destinatários configurados.')
        return cfg, False

    dia_label  = _DIAS_SEMANA[cfg_notif.get('dia_semana', 0)]
    data_envio = agora.strftime('%d/%m/%Y')
    fn_enviar  = enviar or enviar_resumo_semanal

    algum = False
    for destino in destinos:
        nome_dest = (destino.split('@')[0].split('.')[0] or '').capitalize()
        html = montar_html_resumo_semanal(nome_dest, dados, data_envio, dia_label)
        if fn_enviar(destino, html):
            algum = True

    if algum:
        cfg['resumo_semanal_ultimo_envio'] = hoje_str
    return cfg, algum
