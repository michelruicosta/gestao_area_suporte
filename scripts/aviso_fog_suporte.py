"""Notificação semanal de FOGs abertos no Suporte Finaud — possíveis casos não encerrados."""
from __future__ import annotations

import html as html_lib
import logging
import os
import re
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

_log = logging.getLogger(__name__)

_NOTIF_FOG_ID    = 'fog_suporte_abertos'
_GRUPOS_NOTIF    = ('administrador', 'gestor', 'operador')
_FOGBUGZ_URL     = 'https://finaud.fogbugz.com/api.asp'
_FOGBUGZ_FILTER  = '218'
_FOGBUGZ_BASE    = 'https://finaud.fogbugz.com/f/cases/'
_ASSUNTO         = 'Gestão Área Suporte — FOGs aguardando encerramento'
_PORTAL_PRODUCAO = 'https://finaudapps.com.br'

_BG_HEADER      = '#3333A8'
_BG_HEADER_GRAD = '#1e1e72'
_VERDE          = '#8DC63F'

_DIAS_SEMANA = [
    'Segunda-feira', 'Terça-feira', 'Quarta-feira',
    'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo',
]


# ── Config / normalização ──────────────────────────────────────────────────────

def notificacao_fog_padrao() -> dict:
    return {
        'id':         _NOTIF_FOG_ID,
        'titulo':     'FOGs aguardando encerramento',
        'descricao':  'FOGs abertos no Suporte Finaud — possíveis casos resolvidos sem encerramento.',
        'ativa':      True,
        'grupos':     ['administrador'],
        'dia_semana': 0,
    }


def normalizar_notificacao_fog(bruto: dict | None) -> dict:
    """Garante os campos da notificação FOG: ativa, grupos e dia_semana."""
    padrao = notificacao_fog_padrao()
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


# ── Busca no FogBugz ──────────────────────────────────────────────────────────

def buscar_fogs_suporte_abertos(token: str) -> list[dict]:
    """Retorna FOGs abertos atribuídos ao Suporte Finaud, ordenados por dias em aberto (desc)."""
    if not token:
        return []
    hoje = datetime.now(timezone.utc).date()
    try:
        requests.get(_FOGBUGZ_URL, params={
            'token': token, 'cmd': 'setCurrentFilter', 'sFilter': _FOGBUGZ_FILTER,
        }, timeout=10)
        resp = requests.get(_FOGBUGZ_URL, params={
            'token': token, 'cmd': 'search',
            'q': 'assignedTo:"Suporte Finaud" opened:"2025/01/01..today"',
            'cols': 'ixBug,sTitle,dtOpened,sPersonAssignedTo',
        }, timeout=30)
        root = ET.fromstring(resp.text)
        fogs = []
        for case in root.findall('.//case'):
            if (case.findtext('sPersonAssignedTo') or '').strip() != 'Suporte Finaud':
                continue
            bug_id = (case.findtext('ixBug') or '').strip()
            titulo = (case.findtext('sTitle') or '').strip()
            dt_str = (case.findtext('dtOpened') or '').strip()
            if not bug_id:
                continue
            try:
                dt_aberto = datetime.fromisoformat(dt_str.replace('Z', '+00:00')).date()
                dias = max(0, (hoje - dt_aberto).days)
            except Exception:
                dias = 0
            fogs.append({'id': bug_id, 'titulo': titulo, 'dias': dias})
        fogs.sort(key=lambda f: f['dias'], reverse=True)
        return fogs
    except Exception:
        _log.exception('FOG suporte: erro ao buscar no FogBugz')
        return []


# ── E-mail ────────────────────────────────────────────────────────────────────

def _badge_cor(dias: int) -> tuple[str, str]:
    if dias >= 60:
        return '#fff1f2', '#be123c'
    if dias >= 30:
        return '#fff7ed', '#c2410c'
    return '#f0f0ff', '#3333A8'


def _linha_fog_html(fog: dict) -> str:
    bg, cor = _badge_cor(fog['dias'])
    link    = html_lib.escape(f"{_FOGBUGZ_BASE}{fog['id']}")
    fog_id  = html_lib.escape(str(fog['id']))
    titulo  = html_lib.escape(fog['titulo'])
    dias    = int(fog['dias'])
    return (
        f'<tr style="border-bottom:1px solid #e8edf5;">'
        f'<td style="padding:12px 14px;font-weight:700;font-size:13px;color:#1e1e72;'
        f'white-space:nowrap;font-variant-numeric:tabular-nums;">{fog_id}</td>'
        f'<td style="padding:12px 14px;font-size:13.5px;color:#1e1e72;line-height:1.4;">{titulo}</td>'
        f'<td style="padding:12px 14px;text-align:right;white-space:nowrap;">'
        f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
        f'font-size:12px;font-weight:700;background:{bg};color:{cor};">{dias} dias</span></td>'
        f'<td style="padding:12px 14px;text-align:center;">'
        f'<a href="{link}" target="_blank" style="display:inline-block;background:#3333A8;'
        f'color:#ffffff;text-decoration:none;padding:5px 13px;border-radius:6px;'
        f'font-size:12px;font-weight:600;">Abrir</a></td>'
        f'</tr>'
    )


def _nome_do_email(endereco: str) -> str:
    local = (endereco or '').split('@')[0].strip()
    if not local:
        return ''
    token = re.split(r'[._\-+]', local)[0]
    return (token[:1].upper() + token[1:]) if token else ''


def montar_html_fog_suporte(
    nome: str,
    fogs: list[dict],
    data_envio: str,
    dia_semana_label: str,
) -> str:
    """Gera o HTML do e-mail com a tabela de FOGs."""
    saudacao = f'Olá, <b>{html_lib.escape(nome)}</b>,' if nome else 'Olá,'
    n = len(fogs)
    plural   = 's' if n != 1 else ''
    linhas   = ''.join(_linha_fog_html(f) for f in fogs)
    d_seg    = html_lib.escape(data_envio)
    dia_seg  = html_lib.escape(dia_semana_label)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{html_lib.escape(_ASSUNTO)}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f1f5f9;">
<tr><td align="center" style="padding:32px 12px;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600"
       style="max-width:600px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;
              box-shadow:0 4px 20px rgba(15,23,42,.08);border:1px solid #c8c8e8;">

  <!-- Cabeçalho -->
  <tr><td style="background:linear-gradient(135deg,{_BG_HEADER} 0%,{_BG_HEADER_GRAD} 100%);padding:28px 32px 24px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:{_VERDE};text-transform:uppercase;margin-bottom:10px;">
      GESTÃO ÁREA SUPORTE
    </div>
    <div style="font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">
      FOGs aguardando encerramento
    </div>
  </td></tr>

  <!-- Saudação -->
  <tr><td style="padding:24px 32px 0;color:#3333A8;font-size:14.5px;line-height:1.65;">
    <p style="margin:0 0 14px;">{saudacao}</p>
    <p style="margin:0 0 14px;">
      Os FOGs abaixo estão atribuídos ao <b>Suporte Finaud</b> e podem já ter sido resolvidos.
      Verifique cada caso e encerre os que foram concluídos.
    </p>
  </td></tr>

  <!-- Resumo -->
  <tr><td style="padding:4px 32px 0;">
    <div style="background:#f1f5f9;border:1px solid #c8c8e8;border-left:4px solid {_BG_HEADER};
                border-radius:8px;padding:14px 18px;font-size:13px;color:#1e1e72;line-height:1.55;">
      📋 &nbsp;<b>{n} FOG{plural}</b> aguardando encerramento
      &nbsp;·&nbsp; enviado em {d_seg} (toda {dia_seg})
    </div>
  </td></tr>

  <!-- Tabela de FOGs -->
  <tr><td style="padding:20px 32px 0;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
           style="border:1px solid #c8c8e8;border-radius:8px;overflow:hidden;border-collapse:collapse;">
      <thead>
        <tr style="background:#f1f5f9;border-bottom:1px solid #c8c8e8;">
          <th style="padding:10px 14px;font-size:10.5px;font-weight:700;letter-spacing:.7px;
                     text-transform:uppercase;color:#1e1e72;text-align:left;width:68px;">FOG</th>
          <th style="padding:10px 14px;font-size:10.5px;font-weight:700;letter-spacing:.7px;
                     text-transform:uppercase;color:#1e1e72;text-align:left;">Título do caso</th>
          <th style="padding:10px 14px;font-size:10.5px;font-weight:700;letter-spacing:.7px;
                     text-transform:uppercase;color:#1e1e72;text-align:right;width:100px;">Em aberto</th>
          <th style="padding:10px 14px;width:72px;"></th>
        </tr>
      </thead>
      <tbody>{linhas}</tbody>
      <tfoot>
        <tr style="background:#f8fafc;border-top:1px solid #c8c8e8;">
          <td colspan="4" style="padding:10px 14px;font-size:12px;color:#64748b;font-style:italic;">
            Casos acima de 60 dias em vermelho · 30–60 dias em laranja · abaixo de 30 em azul
          </td>
        </tr>
      </tfoot>
    </table>
  </td></tr>

  <!-- Nota -->
  <tr><td style="padding:20px 32px 0;">
    <div style="background:#f0f0ff;border:1px solid #c8c8e8;border-left:4px solid {_VERDE};
                border-radius:8px;padding:12px 16px;font-size:13px;color:#1e1e72;line-height:1.55;">
      Recado automático enviado toda <b>{dia_seg}</b>. Se os casos já foram encerrados,
      pode ignorar este e-mail. Para parar de receber, acesse Notificações no sistema.
    </div>
  </td></tr>

  <!-- Rodapé -->
  <tr><td style="padding:20px 32px 24px;border-top:1px solid #c8c8e8;margin-top:20px;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
      <tr>
        <td style="font-size:11.5px;color:#8899bb;line-height:1.5;">
          Este e-mail foi enviado automaticamente pelo sistema
          <b style="color:#3333A8;">Gestão Área Suporte</b>.<br>
          Se você recebeu por engano, ignore esta mensagem.
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


# ── Envio ─────────────────────────────────────────────────────────────────────

def _smtp_credenciais() -> tuple[str, str]:
    remetente = (
        os.environ.get('EMAIL_USER')
        or os.environ.get('GMAIL_USER')
        or 'coleta.oraculo@finaud.com.br'
    )
    senha = os.environ.get('EMAIL_PASS') or os.environ.get('GMAIL_APP_PASS') or ''
    return remetente, senha


def enviar_aviso_fog_suporte(destino: str, corpo_html: str) -> bool:
    remetente, senha = _smtp_credenciais()
    if not senha or not (destino or '').strip():
        return False
    msg = MIMEMultipart()
    msg['From']    = remetente
    msg['To']      = destino.strip()
    msg['Subject'] = _ASSUNTO
    msg.attach(MIMEText(corpo_html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as s:
            s.starttls()
            s.login(remetente, senha)
            s.send_message(msg)
        _log.info('FOG suporte: aviso enviado para %s', destino)
        return True
    except Exception:
        _log.exception('FOG suporte: falha ao enviar para %s', destino)
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

def verificar_e_enviar_fog_suporte(
    cfg: dict,
    *,
    admin_email: str,
    token: str,
    agora: datetime | None = None,
    enviar=None,
) -> tuple[dict, bool]:
    """Verifica se deve enviar o aviso hoje e envia. Retorna (cfg_atualizado, enviou)."""
    cfg   = dict(cfg or {})
    agora = agora or datetime.now(timezone.utc)

    cfg_notif = normalizar_notificacao_fog(cfg.get('notif_fog_suporte'))
    if not cfg_notif.get('ativa'):
        return cfg, False

    if agora.weekday() != cfg_notif.get('dia_semana', 0):
        return cfg, False

    hoje_str = agora.date().isoformat()
    if cfg.get('notif_fog_suporte_ultimo_envio') == hoje_str:
        return cfg, False

    fogs = buscar_fogs_suporte_abertos(token)
    if not fogs:
        _log.info('FOG suporte: nenhum FOG aberto no Suporte Finaud — e-mail não enviado.')
        return cfg, False

    destinos = _destinatarios(cfg_notif['grupos'], admin_email, cfg.get('usuarios'))
    if not destinos:
        _log.warning('FOG suporte: notificação ligada mas sem destinatários.')
        return cfg, False

    dia_label  = _DIAS_SEMANA[cfg_notif.get('dia_semana', 0)]
    data_envio = agora.strftime('%d/%m/%Y')
    fn_enviar  = enviar or enviar_aviso_fog_suporte

    algum = False
    for destino in destinos:
        html = montar_html_fog_suporte(
            _nome_do_email(destino),
            fogs,
            data_envio,
            dia_label,
        )
        if fn_enviar(destino, html):
            algum = True

    if algum:
        cfg['notif_fog_suporte_ultimo_envio'] = hoje_str
    return cfg, algum
