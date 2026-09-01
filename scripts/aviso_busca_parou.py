"""Recado por e-mail quando a busca automática de e-mails para."""
from __future__ import annotations

import html as html_lib
import logging
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_log = logging.getLogger(__name__)

_GRUPOS_NOTIF = ('administrador', 'gestor', 'operador')
_NOTIF_BUSCA_ID = 'busca_email_parou'
_CHAVE_ENVIO = 'aviso_busca_enviado_para'
_ASSUNTO = 'Gestão Área Suporte — Busca de e-mail parou'
_PORTAL_PRODUCAO = 'https://finaudapps.com.br'
_INTERVALO_VIGIA_MIN = 15

_BG_HEADER = '#3333A8'
_BG_HEADER_GRAD = '#1e1e72'
_VERDE = '#8DC63F'


def _notificacao_busca_padrao() -> dict:
    return {
        'id': _NOTIF_BUSCA_ID,
        'titulo': 'Busca de e-mail parou',
        'descricao': (
            'A busca automática não rodou no tempo marcado em Agendamentos.'
        ),
        'ativa': True,
        'grupos': ['administrador'],
    }


def normalizar_notificacoes(bruto) -> list:
    """Garante a lista de notificações: o que é, ligada/desligada, grupos (vários)."""
    por_id: dict = {}
    if isinstance(bruto, list):
        for item in bruto:
            if not isinstance(item, dict):
                continue
            nid = str(item.get('id') or '').strip()
            if nid:
                por_id[nid] = item
    padrao = _notificacao_busca_padrao()
    salvo = por_id.get(_NOTIF_BUSCA_ID, {})
    grupos = salvo.get('grupos', padrao['grupos'])
    if not isinstance(grupos, list):
        grupos = list(padrao['grupos'])
    grupos_ok = [g for g in grupos if g in _GRUPOS_NOTIF]
    if not grupos_ok:
        grupos_ok = ['administrador']
    ativa = salvo.get('ativa', True)
    if not isinstance(ativa, bool):
        ativa = str(ativa).strip().lower() in ('1', 'true', 'sim', 'yes')
    return [{**padrao, 'ativa': ativa, 'grupos': grupos_ok}]


def _parse_data_hora_log(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor
    texto = str(valor).strip()[:19]
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def avaliar_situacao_busca(cfg: dict, logs, em_andamento: bool, agora=None) -> dict:
    """Informação da busca (luzes): não envia e-mail — isso é Notificações."""
    agora = agora or datetime.now()
    site = {
        'ok': True,
        'rotulo': 'Ligado',
        'detalhe': 'O programa da tela está no ar.',
    }
    if em_andamento:
        return {
            'site': site,
            'busca': {
                'ok': True,
                'rotulo': 'Buscando agora',
                'detalhe': 'A busca de e-mails está em andamento.',
            },
        }
    intervalo = int(cfg.get('intervalo_coleta_min') or 0)
    if intervalo <= 0:
        return {
            'site': site,
            'busca': {
                'ok': True,
                'rotulo': 'Automático desligado',
                'detalhe': 'O relógio da busca está em 0 minutos em Agendamentos.',
            },
        }
    ultimo_ok = None
    for log in logs or []:
        if str(log.get('status') or '') == 'concluida':
            ultimo_ok = log
            break
    if ultimo_ok is None:
        return {
            'site': site,
            'busca': {
                'ok': False,
                'rotulo': 'Parada',
                'detalhe': 'Ainda não há busca concluída no histórico.',
            },
        }
    quando = _parse_data_hora_log(ultimo_ok.get('data_hora'))
    if quando is None:
        return {
            'site': site,
            'busca': {
                'ok': False,
                'rotulo': 'Parada',
                'detalhe': 'Não foi possível ler a data da última busca.',
            },
        }
    minutos = (agora - quando).total_seconds() / 60.0
    detalhe = f'Última busca ok: {quando.strftime("%d/%m %H:%M")}.'
    if minutos > intervalo * 1.5:
        return {
            'site': site,
            'busca': {
                'ok': False,
                'rotulo': 'Parada',
                'detalhe': detalhe + ' Não rodou no intervalo combinado.',
            },
        }
    return {
        'site': site,
        'busca': {
            'ok': True,
            'rotulo': 'Ligada',
            'detalhe': detalhe,
        },
    }


def url_portal_no_email(url: str) -> str:
    """No recado sempre o portal publicado — não o endereço deste PC."""
    texto = (url or '').strip() or _PORTAL_PRODUCAO
    host = texto.lower()
    if '127.0.0.1' in host or 'localhost' in host:
        return _PORTAL_PRODUCAO
    return texto.rstrip('/')


def nome_do_email(endereco: str) -> str:
    local = (endereco or '').split('@')[0].strip()
    if not local:
        return ''
    token = re.split(r'[._\-+]', local)[0]
    if not token:
        return ''
    return token[:1].upper() + token[1:]


def _ultimo_log_concluido(logs) -> dict | None:
    for log in logs or []:
        if str(log.get('status') or '') == 'concluida':
            return log
    return None


def chave_episodio_parada(logs) -> str:
    ultimo = _ultimo_log_concluido(logs)
    if not ultimo:
        return 'nunca'
    return str(ultimo.get('data_hora') or 'nunca').strip()[:19] or 'nunca'


def texto_ultima_busca(logs) -> str:
    ultimo = _ultimo_log_concluido(logs)
    if not ultimo:
        return 'Ainda não houve busca concluída'
    quando = _parse_data_hora_log(ultimo.get('data_hora'))
    if quando is None:
        return 'Ainda não houve busca concluída'
    return quando.strftime('%d/%m/%Y às %H:%M')


def destinatarios_aviso_busca(grupos, admin_email: str, usuarios=None) -> list:
    """Quem recebe: e-mail do administrador no .env + usuários ativos do grupo."""
    saida: list[str] = []
    grupos_ok = [g for g in (grupos or []) if g in _GRUPOS_NOTIF]
    admin = (admin_email or '').strip()
    if 'administrador' in grupos_ok and admin:
        saida.append(admin.lower())
    for usuario in usuarios or []:
        if not isinstance(usuario, dict):
            continue
        if usuario.get('ativo') is False:
            continue
        perfil = str(usuario.get('perfil') or '').strip().lower()
        email = str(usuario.get('email') or '').strip()
        if perfil in grupos_ok and email:
            saida.append(email.lower())
    vistos = set()
    unicos = []
    for email in saida:
        if email not in vistos:
            vistos.add(email)
            unicos.append(email)
    return unicos


def montar_html_aviso_busca_parou(
    nome: str,
    ultima_busca: str,
    intervalo_min: int,
    url_portal: str,
) -> str:
    """HTML do recado — mesmo envelope do Portal / Auditoria (rascunho aprovado)."""
    nome_seg = html_lib.escape((nome or '').strip())
    saudacao = (
        f'Olá, <b>{nome_seg}</b>,' if nome_seg else 'Olá,'
    )
    ultima_seg = html_lib.escape(ultima_busca)
    intervalo_seg = html_lib.escape(f'{int(intervalo_min)} minutos')
    portal_seg = html_lib.escape(url_portal_no_email(url_portal))
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(_ASSUNTO)}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f1f5f9;">
    <tr><td align="center" style="padding:32px 12px;">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600"
             style="max-width:600px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;
                    box-shadow:0 4px 20px rgba(15,23,42,.08);border:1px solid #c8c8e8;">
        <tr><td style="background:linear-gradient(135deg,{_BG_HEADER} 0%,{_BG_HEADER_GRAD} 100%);padding:28px 32px 24px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>
              <td style="font-size:13px;font-weight:700;letter-spacing:1.5px;color:{_VERDE};text-transform:uppercase;">
                GESTÃO ÁREA SUPORTE
              </td>
            </tr>
            <tr>
              <td style="padding-top:8px;font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">
                Busca de e-mail parou
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:28px 32px 0 32px;color:#3333A8;font-size:14.5px;line-height:1.6;">
          <p style="margin:0 0 16px 0;">{saudacao}</p>
        </td></tr>
        <tr><td style="padding:0 32px 12px 32px;color:#3333A8;font-size:14.5px;line-height:1.6;">
          <p style="margin:0 0 14px 0;">
            A busca automática de e-mails <b>não rodou no tempo marcado</b> em Agendamentos.
          </p>
        </td></tr>
        <tr><td style="padding:8px 32px 8px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
                 style="background:#f1f5f9;border:1px solid #c8c8e8;border-left:4px solid {_BG_HEADER};border-radius:8px;">
            <tr>
              <td style="padding:14px 18px;font-size:12px;font-weight:700;color:#1e1e72;
                         text-transform:uppercase;letter-spacing:.5px;width:180px;">
                Última busca
              </td>
              <td style="padding:14px 18px;font-size:14px;color:#3333A8;">
                {ultima_seg}
              </td>
            </tr>
            <tr>
              <td style="padding:14px 18px;font-size:12px;font-weight:700;color:#1e1e72;
                         text-transform:uppercase;letter-spacing:.5px;border-top:1px solid #c8c8e8;">
                Deveria rodar a cada
              </td>
              <td style="padding:14px 18px;font-size:14px;color:#3333A8;border-top:1px solid #c8c8e8;">
                {intervalo_seg}
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td align="center" style="padding:16px 32px 8px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
            <tr><td align="center"
                    style="background:{_BG_HEADER};border-radius:10px;
                           box-shadow:0 4px 12px rgba(51,51,168,.25);">
              <a href="{portal_seg}" target="_blank"
                 style="display:inline-block;padding:13px 28px;font-size:14.5px;font-weight:700;
                        color:#ffffff;text-decoration:none;letter-spacing:.3px;">
                Abrir a Gestão →
              </a>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:8px 32px 8px 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
                 style="background:#f0f0ff;border:1px solid #c8c8e8;border-left:4px solid {_VERDE};border-radius:8px;">
            <tr><td style="padding:12px 16px;font-size:13px;color:#1e1e72;line-height:1.55;">
              Recado automático. Se a busca já tiver voltado a rodar, pode ignorar este e-mail.
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:20px 32px 28px 32px;border-top:1px solid #c8c8e8;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>
              <td style="font-size:11.5px;color:#8899bb;line-height:1.5;">
                Este e-mail foi enviado automaticamente pelo sistema
                <b style="color:#3333A8;">Gestão Área Suporte</b>.
                <br>Se você recebeu por engano, ignore esta mensagem.
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


def _smtp_credenciais() -> tuple[str, str]:
    remetente = (
        os.environ.get('EMAIL_USER')
        or os.environ.get('GMAIL_USER')
        or 'coleta.oraculo@finaud.com.br'
    )
    senha_smtp = os.environ.get('EMAIL_PASS') or os.environ.get('GMAIL_APP_PASS') or ''
    return remetente, senha_smtp


def enviar_aviso_busca_parou(destino: str, corpo_html: str) -> bool:
    """Envia o recado. Só retorna True se o e-mail saiu."""
    remetente, senha_smtp = _smtp_credenciais()
    if not senha_smtp:
        _log.warning('Aviso de busca parada: SMTP não configurado (EMAIL_PASS ou GMAIL_APP_PASS).')
        return False
    destino_limpo = (destino or '').strip()
    if not destino_limpo:
        return False
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destino_limpo
    msg['Subject'] = _ASSUNTO
    msg.attach(MIMEText(corpo_html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
            server.starttls()
            server.login(remetente, senha_smtp)
            server.send_message(msg)
        _log.info('Aviso de busca parada enviado para %s', destino_limpo)
        return True
    except Exception:
        _log.exception('Falha ao enviar aviso de busca parada')
        return False


def verificar_e_avisar_busca_parada(
    cfg: dict,
    logs,
    em_andamento: bool,
    *,
    admin_email: str,
    portal_url: str,
    agora=None,
    enviar=None,
) -> tuple[dict, bool]:
    """Envia no máximo um e-mail por episódio de parada. Devolve (config, enviou)."""
    cfg = dict(cfg or {})
    situacao = avaliar_situacao_busca(cfg, logs, em_andamento, agora=agora)
    chave_atual = str(cfg.get(_CHAVE_ENVIO) or '')
    if situacao['busca']['ok']:
        if chave_atual:
            cfg[_CHAVE_ENVIO] = ''
        return cfg, False

    notif = normalizar_notificacoes(cfg.get('notificacoes'))[0]
    if not notif.get('ativa'):
        return cfg, False

    chave = chave_episodio_parada(logs)
    if chave_atual == chave:
        return cfg, False

    destinos = destinatarios_aviso_busca(
        notif.get('grupos'),
        admin_email,
        cfg.get('usuarios'),
    )
    if not destinos:
        _log.warning('Aviso de busca parada: notificação ligada, mas ninguém para receber.')
        return cfg, False

    intervalo = int(cfg.get('intervalo_coleta_min') or 0)
    ultima = texto_ultima_busca(logs)
    portal = url_portal_no_email(portal_url)
    fn_enviar = enviar or enviar_aviso_busca_parou
    algum = False
    for destino in destinos:
        html = montar_html_aviso_busca_parou(
            nome_do_email(destino),
            ultima,
            intervalo,
            portal,
        )
        if fn_enviar(destino, html):
            algum = True
    if algum:
        cfg[_CHAVE_ENVIO] = chave
    return cfg, algum
