"""
servidor_telas.py
O que faz: servidor Flask que serve as telas de Gestão de E-mail do Gestão Área Suporte
           e fornece dados ao vivo do banco SQLite via API REST.
Porta: 5000   Rodar: python scripts/servidor_telas.py
"""

from __future__ import annotations

import html as html_lib
import io
import json
import os
import re
import secrets
import smtplib
import string
import sys
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Windows usa charmap por padrão — força UTF-8 para suportar emojis nos logs
# pytest captura stdout; reembrulhar fecha o arquivo interno da suíte
if (
    sys.platform == 'win32'
    and hasattr(sys.stdout, 'buffer')
    and 'pytest' not in sys.modules
):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import requests
import xml.etree.ElementTree as _ET
from datetime import date, datetime, timezone, timedelta
from functools import wraps

from dateutil.easter import easter

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR    = os.path.dirname(_SCRIPTS_DIR)
_CONFIG_PATH = os.path.join(_ROOT_DIR, 'data', 'config.json')

sys.path.insert(0, _SCRIPTS_DIR)
import banco_threads as bt
from aviso_busca_parou import (
    _INTERVALO_VIGIA_MIN,
    avaliar_situacao_busca,
    normalizar_notificacoes,
    verificar_e_avisar_busca_parada,
)
from paths import criar_log
from portal_sso import COOKIE_AUDITORIA, COOKIE_PORTAL, usuario_pelos_cookies

_log = criar_log('servidor')

app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT_DIR, 'templates'),
    static_folder=os.path.join(_ROOT_DIR, 'static'),
)


def _exigir_secret_key() -> str:
    """Sem chave no .env o servidor não sobe — não há senha/segredo de fábrica."""
    chave = (os.environ.get('SECRET_KEY') or '').strip()
    if not chave:
        raise RuntimeError(
            'SECRET_KEY ausente. Defina no .env do servidor. Sem isso o Gestão não sobe.'
        )
    return chave


app.secret_key = _exigir_secret_key()

@app.after_request
def sem_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

_coleta_em_andamento = False
_ultimo_erro_coleta: str | None = None

# ── Configurações persistentes ─────────────────────────────────────────────────

_CONFIG_DEFAULTS: dict = {
    'intervalo_coleta_min': 60,
    'intervalo_fog_min': 15,
    'dias_sr_af': 30,
    'dias_sr_ac': 60,
}

def _ler_config() -> dict:
    try:
        with open(_CONFIG_PATH, encoding='utf-8') as f:
            dados = json.load(f)
    except Exception:
        dados = {}
    return {**_CONFIG_DEFAULTS, **dados}

def _salvar_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── Agendador de coleta automática ────────────────────────────────────────────
# Relógio alvo: processo à parte (`executar_pipeline.py --agendar`).
# Na tela só liga se GESTAO_AGENDADOR_EXTERNO não estiver ativo (compatível com o servidor atual).

_scheduler = BackgroundScheduler(daemon=True)


def _agendador_externo_ligado() -> bool:
    flag = (os.environ.get('GESTAO_AGENDADOR_EXTERNO') or '').strip().lower()
    return flag in ('1', 'true', 'sim', 'yes')


def _deve_ligar_agendador_na_tela() -> bool:
    if 'pytest' in sys.modules:
        return False
    return not _agendador_externo_ligado()


def _job_coleta_automatica():
    global _coleta_em_andamento, _ultimo_erro_coleta
    if _coleta_em_andamento:
        return
    _coleta_em_andamento = True
    _ultimo_erro_coleta = None
    _log.info('Coleta automática disparada pelo agendador.')
    try:
        from executar_pipeline import rodar_coleta_ciclo
        rodar_coleta_ciclo()
    except Exception as e:
        _ultimo_erro_coleta = str(e)
        _log.exception('Coleta automática falhou: %s', e)
    finally:
        _coleta_em_andamento = False

def _reagendar_coleta(intervalo_min: int) -> None:
    if not _deve_ligar_agendador_na_tela():
        return
    if _scheduler.get_job('coleta_automatica'):
        _scheduler.remove_job('coleta_automatica')
    if intervalo_min > 0:
        _scheduler.add_job(
            _job_coleta_automatica,
            'interval',
            minutes=intervalo_min,
            id='coleta_automatica',
            replace_existing=True,
            next_run_time=datetime.now(),
        )


def _job_sem_retorno():
    """Job diário (06h) que arquiva threads sem resposta conforme os limites configurados."""
    try:
        from executar_pipeline import rodar_sem_retorno
        rodar_sem_retorno()
    except Exception:
        _log.exception('Sem Retorno — falhou.')


def _job_vigia_busca():
    """Olha se a busca atrasou e manda o recado (no máximo um por episódio)."""
    try:
        cfg = _ler_config()
        logs = bt.ler_log_coletas(limite=30)
        novo, _enviou = verificar_e_avisar_busca_parada(
            cfg,
            logs,
            _coleta_em_andamento,
            admin_email=_ADMIN_EMAIL,
            portal_url=_PORTAL_URL,
        )
        if novo.get('aviso_busca_enviado_para', '') != cfg.get('aviso_busca_enviado_para', ''):
            _salvar_config(novo)
    except Exception:
        _log.exception('Vigia da busca — falhou.')


def _agendar_vigia_busca() -> None:
    if _scheduler.get_job('vigia_busca_email'):
        return
    _scheduler.add_job(
        _job_vigia_busca,
        'interval',
        minutes=_INTERVALO_VIGIA_MIN,
        id='vigia_busca_email',
        replace_existing=True,
    )


class _Usuario:
    """Mock de current_user para compatibilidade com layout.html (que usa Flask-Login)."""
    def __init__(self, autenticado: bool, email: str = ''):
        self.is_authenticated = autenticado
        self.role  = 'admin' if autenticado else ''
        self.email = email
        self.nome  = email.split('@')[0] if email else ''
        self.name  = self.nome   # layout.html: current_user.name
        self.id    = self.nome   # layout.html: current_user.id


@app.context_processor
def _injetar_usuario():
    logado = bool(session.get('logado'))
    return {'current_user': _Usuario(logado, session.get('email', ''))}


@app.context_processor
def _injetar_portal_url():
    return {'portal_url': _url_portal_destino()}


# Login do dia a dia = portal. GESTAO_SENHA só se estiver no .env — sem senha de fábrica.
_ADMIN_EMAIL = os.environ.get('GESTAO_EMAIL', 'michel@finaud.com.br')
_ADMIN_SENHA = (os.environ.get('GESTAO_SENHA') or '').strip()
_PORTAL_URL = os.environ.get('PORTAL_URL', 'https://finaudapps.com.br').rstrip('/')
_PORTAL_PREVIEW_LOCAL = 'http://127.0.0.1:8000/portal-preview/'
_MENSAGEM_RECUPERAR = (
    'Se este e-mail estiver cadastrado e ativo, enviaremos uma senha temporária em instantes.\n\n'
    'Não recebeu? Verifique o spam ou contate o administrador do sistema.'
)
_ALFABETO_SENHA_TEMP = string.ascii_letters + string.digits


def _url_portal_destino() -> str:
    """Neste PC volta à prévia do portal; no ar continua finaudapps.com.br."""
    host = (request.host or '').split(':')[0].strip().lower()
    if host in ('127.0.0.1', 'localhost'):
        return _PORTAL_PREVIEW_LOCAL
    return _PORTAL_URL


def _senha_confere(senha: str) -> bool:
    """Confere com o hash gravado, ou com GESTAO_SENHA do .env. Sem os dois, o login local falha."""
    if not senha:
        return False
    h = _ler_config().get('senha_hash')
    if h:
        return check_password_hash(h, senha)
    if not _ADMIN_SENHA:
        return False
    return senha == _ADMIN_SENHA


def _gravar_senha_hash(senha: str) -> None:
    cfg = _ler_config()
    cfg['senha_hash'] = generate_password_hash(senha)
    _salvar_config(cfg)


def _gerar_senha_temporaria(tamanho: int = 12) -> str:
    return ''.join(secrets.choice(_ALFABETO_SENHA_TEMP) for _ in range(tamanho))


def _smtp_credenciais() -> tuple[str, str]:
    remetente = (
        os.environ.get('EMAIL_USER')
        or os.environ.get('GMAIL_USER')
        or 'coleta.oraculo@finaud.com.br'
    )
    senha_smtp = os.environ.get('EMAIL_PASS') or os.environ.get('GMAIL_APP_PASS') or ''
    return remetente, senha_smtp


def _enviar_senha_temporaria(destino: str, senha_temporaria: str, url_login: str) -> bool:
    """Envia senha temporária por SMTP. Só retorna True se o e-mail saiu."""
    remetente, senha_smtp = _smtp_credenciais()
    if not senha_smtp:
        _log.warning('Recuperação de senha: SMTP não configurado (EMAIL_PASS ou GMAIL_APP_PASS).')
        return False
    destino_seg = html_lib.escape(destino.strip())
    senha_seg = html_lib.escape(senha_temporaria)
    login_seg = html_lib.escape(url_login)
    corpo_html = f"""<!DOCTYPE html>
<html lang="pt-BR"><body style="margin:0;padding:24px;background:#f1f5f9;font-family:Segoe UI,Arial,sans-serif;color:#1e1e72;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;border:1px solid #c8c8e8;">
    <tr><td style="padding:24px 28px;background:#001c5b;color:#fff;border-radius:12px 12px 0 0;">
      <div style="font-size:12px;letter-spacing:.12em;color:#b4d84a;font-weight:700;">GESTÃO ÁREA SUPORTE</div>
      <div style="font-size:22px;font-weight:700;margin-top:8px;">Recuperação de acesso</div>
    </td></tr>
    <tr><td style="padding:24px 28px;font-size:14px;line-height:1.6;">
      <p style="margin:0 0 14px;">Recebemos um pedido de recuperação de acesso. Use os dados abaixo para entrar:</p>
      <p style="margin:0 0 8px;"><b>E-mail:</b> {destino_seg}</p>
      <p style="margin:0 0 16px;"><b>Senha temporária:</b> {senha_seg}</p>
      <p style="margin:0 0 16px;"><a href="{login_seg}" style="color:#001c5b;">Abrir o login</a></p>
      <p style="margin:0;font-size:13px;color:#5b6478;">Troque esta senha assim que entrar. Se você não pediu esta recuperação, ignore o e-mail.</p>
    </td></tr>
  </table>
</body></html>"""
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destino.strip()
    msg['Subject'] = 'Gestão Área Suporte — senha temporária'
    msg.attach(MIMEText(corpo_html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
            server.starttls()
            server.login(remetente, senha_smtp)
            server.send_message(msg)
        _log.info('Senha temporária enviada para %s', destino.strip())
        return True
    except Exception:
        _log.exception('Falha ao enviar senha temporária')
        return False


# ── Mapeamento categoria → nome de exibição ────────────────────────────────────

_NOMES_CATEGORIA: dict[str, str] = {
    'DDR_2011':                      'DDR 2011',
    'SALDOS_CONTABEIS_DIARIOS_4111': 'Saldos Contábeis 4111',
    'DRM_2060':                      'DRM 2060',
    'DLO_2061':                      'DLO 2061',
    'DLI_2062':                      'DLI 2062',
    'DRL_2160':                      'DRL 2160',
    'S5':                            'S5',
    'RETORNO_BACEN':                 'Retorno BACEN',
    'FORCAPITAL':                    'ForCapital',
    'DRSAC_2030':                    'DRSAC 2030',
    'PVCA_6209':                     'PVCA 6209',
    'CADOC':                         'CADOC',
    'SUPORTE':                       'Suporte',
    'INTERNO':                       'Interno',
}

_ORDEM_CATEGORIAS = list(_NOMES_CATEGORIA.keys())


def _nome_cat(cat_id: str) -> str:
    return _NOMES_CATEGORIA.get(cat_id, cat_id)


# ── Helpers §7 — "De" e "Para" ────────────────────────────────────────────────

_RE_NOME  = re.compile(r'^([^<]+?)\s*<')
_RE_EMAIL = re.compile(r'<([^>]+)>')


def _extrair_nome(raw: str) -> str:
    """'Nome <email>' → 'Nome'; 'email@' → 'email@'."""
    m = _RE_NOME.match(raw.strip())
    if m:
        return m.group(1).strip()
    m = _RE_EMAIL.search(raw)
    if m:
        return m.group(1).strip()
    return raw.strip()


def _extrair_email(raw: str) -> str:
    """'Nome <email>' → 'email'; 'email@dominio' → 'email@dominio'."""
    m = _RE_EMAIL.search(raw.strip())
    if m:
        return m.group(1).strip()
    s = raw.strip()
    return s if '@' in s else s


def _eh_finaud_addr(raw: str) -> bool:
    a = (raw or '').lower()
    return '@finaud.com.br' in a or '@finaudtec.com.br' in a


def _eh_suporte(raw: str) -> bool:
    return 'suporte@finaud.com.br' in raw.lower()


def _primeiro_finaud_ou_primeiro(raw: str) -> str:
    """De uma lista de destinatários, retorna o primeiro @finaud; senão, o primeiro da lista."""
    emails = _RE_EMAIL.findall(raw)
    if not emails:
        emails = [e.strip() for e in re.split(r'[,;]', raw) if '@' in e.strip()]
    for e in emails:
        if '@finaud' in e.lower() or '@finaudtec' in e.lower():
            return e.strip()
    return emails[0].strip() if emails else raw.strip()


def _resolver_de(msg: dict) -> str:
    """§7 Campo 1: From=suporte@ → usa Reply-To; caso contrário usa From."""
    from_raw = msg.get('remetente', '')
    reply_to = msg.get('reply_to', '')
    if _eh_suporte(from_raw):
        return _extrair_nome(reply_to) if reply_to else _extrair_nome(from_raw)
    return _extrair_nome(from_raw)


def _resolver_para(msg: dict) -> str:
    """§7 Campo 2: To=suporte@ → mostra CC; CC vazio → mostra suporte."""
    to_raw = msg.get('destinatarios', '')
    cc_raw = msg.get('cc', '')
    if _eh_suporte(to_raw):
        return _extrair_nome(cc_raw) if cc_raw else 'suporte@finaud.com.br'
    return _extrair_nome(to_raw)


def _formatar_data(iso: str | None) -> str:
    if not iso:
        return ''
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return iso[:10] if iso else ''


def _chave_data(t: dict) -> str:
    """'DD/MM/AAAA HH:MM' → 'AAAAMMDD HHMM' para ordenação correta por data."""
    d = t.get('data_ultima_msg') or ''
    try:
        return datetime.strptime(d[:16], '%d/%m/%Y %H:%M').strftime('%Y%m%d%H%M')
    except Exception:
        return d


def _parametros_cookie_portal() -> dict:
    """Mesmo domínio do cookie do portal, para o Sair encerrar a sessão do grupo."""
    params = {'path': '/', 'httponly': True, 'samesite': 'lax'}
    domain = os.environ.get('AUTH_COOKIE_DOMAIN', '.finaudapps.com.br').strip()
    if domain:
        params['domain'] = domain
    secure_env = os.environ.get('AUTH_COOKIE_SECURE')
    if secure_env is None:
        params['secure'] = bool(domain)
    elif secure_env.strip().lower() in ('1', 'true', 'yes'):
        params['secure'] = True
    return params


def _redirecionar_ao_portal_saindo():
    session.clear()
    resp = redirect(_url_portal_destino())
    params = _parametros_cookie_portal()
    for nome in (COOKIE_AUDITORIA, COOKIE_PORTAL):
        resp.delete_cookie(nome, **params)
    return resp


def _aplicar_sso_portal() -> bool:
    """Abre o app se o cookie do portal ainda for válido."""
    if session.get('logado'):
        return True
    usuario = usuario_pelos_cookies(request.cookies)
    if usuario is None:
        return False
    session['logado'] = True
    session['email'] = usuario.email
    return True


def _requer_login(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get('logado'):
            _aplicar_sso_portal()
        if not session.get('logado'):
            if request.is_json:
                return jsonify({'erro': 'não autenticado'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return _wrap


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET' and _aplicar_sso_portal():
        return redirect(url_for('index'))
    erro = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        senha = (request.form.get('senha') or '').strip()
        if email.lower() == _ADMIN_EMAIL.lower() and _senha_confere(senha):
            session['logado'] = True
            session['email']  = _ADMIN_EMAIL
            return redirect(url_for('index'))
        erro = 'E-mail ou senha incorretos.'
    return render_template('gestao_login.html', erro=erro)


@app.route('/auth/recuperar-senha', methods=['POST'])
def recuperar_senha():
    """Mesmo fluxo do portal Finaud: e-mail → senha temporária. Sempre a mesma mensagem (não revela se o e-mail existe)."""
    dados = request.get_json(silent=True) or {}
    email = (dados.get('email') or request.form.get('email') or '').strip()
    if email.lower() == _ADMIN_EMAIL.lower():
        temp = _gerar_senha_temporaria()
        url_login = request.host_url.rstrip('/') + url_for('login')
        if _enviar_senha_temporaria(_ADMIN_EMAIL, temp, url_login):
            _gravar_senha_hash(temp)
    return jsonify({'mensagem': _MENSAGEM_RECUPERAR})


@app.route('/sair')
def sair():
    return _redirecionar_ao_portal_saindo()


# ── Tela principal ─────────────────────────────────────────────────────────────

@app.route('/')
@_requer_login
def index():
    from collections import defaultdict
    _fog = _buscar_fog()
    ativos   = [t for t in _fog if t['status'] == 'Ativo']
    fechados = [t for t in _fog if t['status'] == 'Fechado']
    n = len(ativos) or 1
    em_and  = sum(1 for t in ativos if t['dias_responsavel'] < _FOG_DIAS_AMBAR)
    atencao = sum(1 for t in ativos if _FOG_DIAS_AMBAR <= t['dias_responsavel'] < _FOG_DIAS_VERMELHO)
    critico = sum(1 for t in ativos if t['dias_responsavel'] >= _FOG_DIAS_VERMELHO)
    by_resp: dict = defaultdict(list)
    for t in ativos:
        by_resp[t['responsavel']].append(t)
    ranking = sorted([
        {
            'nome':             nome,
            'casos':            len(casos),
            'caso_mais_antigo': max(casos, key=lambda x: x['dias_responsavel'])['assunto'],
            'dias_mais_antigo': max(casos, key=lambda x: x['dias_responsavel'])['dias_responsavel'],
        }
        for nome, casos in by_resp.items()
    ], key=lambda x: x['dias_mais_antigo'], reverse=True)
    fog_stats = {
        'total_ativos':     len(ativos),
        'em_andamento':     {'qtd': em_and,  'perc': round(em_and  / n * 100)},
        'atencao':          {'qtd': atencao, 'perc': round(atencao / n * 100)},
        'critico':          {'qtd': critico, 'perc': round(critico / n * 100)},
        'total_concluidos': len(fechados),
        'ranking':          ranking,
    }
    fog_projetos     = sorted({t['projeto']     for t in _fog})
    fog_areas        = sorted({t['area']        for t in _fog})
    fog_responsaveis = sorted({t['responsavel'] for t in _fog if t['status'] == 'Ativo'})
    return render_template(
        'gestao_email.html',
        email=session.get('email', ''),
        fog_tarefas=_fog,
        fog_projetos=fog_projetos,
        fog_areas=fog_areas,
        fog_responsaveis=fog_responsaveis,
        fog_stats=fog_stats,
        fog_simulado=False,
        fog_corte_ambar=_FOG_DIAS_AMBAR,
        fog_corte_vermelho=_FOG_DIAS_VERMELHO,
    )


# ── API: Resumo ───────────────────────────────────────────────────────────────

@app.route('/api/resumo')
@_requer_login
def api_resumo():
    threads = bt.buscar_por_destino('principal')

    contagens: dict[str, dict] = {}
    for t in threads:
        cat    = t.get('categoria') or 'DESCONHECIDA'
        status = t.get('status_workflow') or 'Aguardando Finaud'
        if cat not in contagens:
            contagens[cat] = {'af': 0, 'ac': 0, 'co': 0}
        if status == 'Aguardando Finaud':
            contagens[cat]['af'] += 1
        elif status == 'Aguardando Cliente':
            contagens[cat]['ac'] += 1
        elif status == 'Concluída':
            contagens[cat]['co'] += 1

    total_af = total_ac = total_co = 0
    categorias = []
    for cat_id in _ORDEM_CATEGORIAS:
        if cat_id not in contagens:
            continue
        c = contagens.pop(cat_id)
        tot = c['af'] + c['ac'] + c['co']
        total_af += c['af']; total_ac += c['ac']; total_co += c['co']
        categorias.append({'id': cat_id, 'nome': _nome_cat(cat_id),
                           'af': c['af'], 'ac': c['ac'], 'co': c['co'], 'total': tot})
    for cat_id, c in contagens.items():
        tot = c['af'] + c['ac'] + c['co']
        total_af += c['af']; total_ac += c['ac']; total_co += c['co']
        categorias.append({'id': cat_id, 'nome': _nome_cat(cat_id),
                           'af': c['af'], 'ac': c['ac'], 'co': c['co'], 'total': tot})

    total = total_af + total_ac + total_co
    cd    = bt.contar_por_destino()

    # Delta: compara estado atual com o último snapshot de ontem (variação diária)
    snapshot = bt.ler_snapshot_de_ontem()
    for cat in categorias:
        snap = snapshot.get(cat['id'])
        if snap:
            cat['delta_af']  = cat['af']    - snap['af']
            cat['delta_ac']  = cat['ac']    - snap['ac']
            cat['delta_co']  = cat['co']    - snap['co']
            cat['delta_tot'] = cat['total'] - snap['total']
        else:
            cat['delta_af']  = None
            cat['delta_ac']  = None
            cat['delta_co']  = None
            cat['delta_tot'] = None

    nv = bt.contar_nao_vistas()

    sr_threads = bt.buscar_threads_sem_retorno()
    sr_af = sum(1 for t in sr_threads if t.get('status_workflow') == 'Aguardando Finaud')
    sr_ac = sum(1 for t in sr_threads if t.get('status_workflow') == 'Aguardando Cliente')
    sr_total = sr_af + sr_ac
    snapshot_sr = snapshot.get('SEM RETORNO')
    sem_retorno = {
        'af':        sr_af,
        'ac':        sr_ac,
        'total':     sr_total,
        'delta_af':  (sr_af  - snapshot_sr['af'])    if snapshot_sr else None,
        'delta_ac':  (sr_ac  - snapshot_sr['ac'])    if snapshot_sr else None,
        'delta_tot': (sr_total - snapshot_sr['total']) if snapshot_sr else None,
    }

    return jsonify({
        'categorias':   categorias,
        'totais':       {'af': total_af, 'ac': total_ac, 'co': total_co, 'total': total},
        'sem_retorno':  sem_retorno,
        'nao_class':    nv['nao_class'],
        'bloqueados':   nv['bloqueados'],
    })


# ── API: Threads de uma categoria ─────────────────────────────────────────────

@app.route('/api/categoria/<cat_id>')
@_requer_login
def api_categoria(cat_id: str):
    threads = sorted(
        [t for t in bt.buscar_por_destino('principal') if t.get('categoria') == cat_id],
        key=_chave_data, reverse=True,
    )
    resultado = [
        {
            'thread_id':            t['thread_id'],
            'assunto':              t.get('assunto') or '(sem assunto)',
            'de':   _extrair_email(
                        t.get('reply_to_ultima_msg') or ''
                        if _eh_suporte(t.get('remetente_ultima_msg') or '')
                           and (t.get('reply_to_ultima_msg') or '')
                        else t.get('remetente_ultima_msg') or ''
                    ),
            'para': (
                _primeiro_finaud_ou_primeiro(t.get('destinatario_ultima_msg') or '')
                if (not _eh_finaud_addr(t.get('remetente_ultima_msg') or ''))
                   or (_eh_suporte(t.get('remetente_ultima_msg') or '')
                       and (t.get('reply_to_ultima_msg') or '')
                       and not _eh_finaud_addr(t.get('reply_to_ultima_msg') or ''))
                else _extrair_email(t.get('destinatario_ultima_msg') or '')
            ),
            'data':                 _formatar_data(t.get('data_ultima_msg')),
            'qtd_mensagens':        t.get('qtd_mensagens', 0),
            'status':               t.get('status_workflow') or 'Aguardando Finaud',
            'motivo_status':        t.get('motivo_status') or '',
            'motivo_classificacao': t.get('motivo_classificacao') or '',
        }
        for t in threads
    ]
    return jsonify({'categoria_id': cat_id, 'categoria_nome': _nome_cat(cat_id),
                    'threads': resultado})


# ── API: Thread completa ──────────────────────────────────────────────────────

@app.route('/api/thread/<thread_id>')
@_requer_login
def api_thread(thread_id: str):
    t = bt.buscar_thread_completa(thread_id)
    if not t:
        abort(404)
    mensagens = [
        {
            'de':     _resolver_de(m),
            'para':   _resolver_para(m),
            'data':   _formatar_data(m.get('data')),
            'assunto': m.get('assunto') or '',
            'corpo':  m.get('corpo_texto') or '',
            'anexos': m.get('nomes_anexos') or [],
        }
        for m in reversed(t.get('mensagens', []))
    ]
    return jsonify({
        'thread_id':            t['thread_id'],
        'assunto':              t.get('assunto') or '(sem assunto)',
        'categoria':            t.get('categoria') or '',
        'categoria_nome':       _nome_cat(t.get('categoria') or ''),
        'status':               t.get('status_workflow') or '',
        'motivo_classificacao': t.get('motivo_classificacao') or '',
        'mensagens':            mensagens,
    })


# ── API: Não classificados ─────────────────────────────────────────────────────

@app.route('/api/nao-classificados')
@_requer_login
def api_nao_classificados():
    threads = sorted(
        bt.buscar_por_destino('revisao', apenas_nao_vistas=True) + bt.buscar_sem_classificar(apenas_nao_vistas=True),
        key=_chave_data, reverse=True,
    )
    resultado = [
        {
            'thread_id':     t['thread_id'],
            'assunto':       t.get('assunto') or '(sem assunto)',
            'data':          _formatar_data(t.get('data_ultima_msg')),
            'qtd_mensagens': t.get('qtd_mensagens', 0),
            'remetente':     _extrair_nome(t.get('remetente_principal') or ''),
        }
        for t in threads
    ]
    return jsonify({'threads': resultado, 'total': len(resultado)})


# ── API: Bloqueados por filtro ─────────────────────────────────────────────────

@app.route('/api/bloqueados')
@_requer_login
def api_bloqueados():
    threads = sorted(bt.buscar_por_destino('descartes', apenas_nao_vistas=True), key=_chave_data, reverse=True)
    resultado = [
        {
            'thread_id':       t['thread_id'],
            'assunto':         t.get('assunto') or '(sem assunto)',
            'data':            _formatar_data(t.get('data_ultima_msg')),
            'qtd_mensagens':   t.get('qtd_mensagens', 0),
            'remetente':       _extrair_nome(t.get('remetente_principal') or ''),
            'motivo_descarte': t.get('motivo_descarte') or '',
        }
        for t in threads
    ]
    return jsonify({'threads': resultado, 'total': len(resultado)})


# ── API: Marcar como vistas ───────────────────────────────────────────────────

@app.route('/api/marcar-vistas', methods=['POST'])
@_requer_login
def api_marcar_vistas():
    dados = request.get_json(silent=True) or {}
    grupo = (dados.get('grupo') or '').strip()
    if grupo not in ('bloqueados', 'nao_class'):
        return jsonify({'erro': 'grupo inválido'}), 400
    bt.marcar_vistas(grupo)
    return jsonify({'ok': True})


# ── API: Classificar manualmente ──────────────────────────────────────────────

@app.route('/api/classificar/<thread_id>', methods=['POST'])
@_requer_login
def api_classificar(thread_id: str):
    dados = request.get_json(silent=True) or {}
    categoria = (dados.get('categoria') or '').strip()
    if not categoria:
        return jsonify({'erro': 'campo "categoria" é obrigatório'}), 400
    if categoria not in _NOMES_CATEGORIA:
        return jsonify({'erro': f'categoria desconhecida: {categoria}'}), 400
    bt.classificar_manual(thread_id, categoria)
    return jsonify({'ok': True, 'thread_id': thread_id, 'categoria': categoria})


# ── API: Admin — coletor e log ────────────────────────────────────────────────

@app.route('/api/admin/coletar', methods=['POST'])
@_requer_login
def api_admin_coletar():
    global _coleta_em_andamento
    if _coleta_em_andamento:
        return jsonify({'erro': 'Coleta já em andamento. Aguarde o término.'}), 409

    def _rodar():
        global _coleta_em_andamento, _ultimo_erro_coleta
        _ultimo_erro_coleta = None
        try:
            sys.path.insert(0, _SCRIPTS_DIR)
            from coletor_gmail import coletar
            from classificador_regras import classificar_banco
            log_id = coletar()
            contagens = classificar_banco()
            if log_id:
                bt.atualizar_classif_coleta(
                    log_id,
                    contagens.get('principal', 0),
                    contagens.get('descartes', 0),
                    contagens.get('revisao', 0),
                )
        except Exception as e:
            _ultimo_erro_coleta = str(e)
            _log.exception('Coleta falhou: %s', e)
        finally:
            _coleta_em_andamento = False

    _coleta_em_andamento = True
    threading.Thread(target=_rodar, daemon=True).start()
    return jsonify({'ok': True, 'mensagem': 'Coleta iniciada em segundo plano.'})


@app.route('/api/admin/status-coleta')
@_requer_login
def api_admin_status_coleta():
    return jsonify({'em_andamento': _coleta_em_andamento, 'ultimo_erro': _ultimo_erro_coleta})


@app.route('/api/threads/sem-retorno')
@_requer_login
def api_threads_sem_retorno():
    threads = bt.buscar_threads_sem_retorno()
    resultado = [
        {
            'thread_id':     t['thread_id'],
            'assunto':       t.get('assunto') or '(sem assunto)',
            'de':  _extrair_email(
                       t.get('reply_to_ultima_msg') or ''
                       if _eh_suporte(t.get('remetente_ultima_msg') or '')
                          and (t.get('reply_to_ultima_msg') or '')
                       else t.get('remetente_ultima_msg') or ''
                   ),
            'para': (
                _primeiro_finaud_ou_primeiro(t.get('destinatario_ultima_msg') or '')
                if (not _eh_finaud_addr(t.get('remetente_ultima_msg') or ''))
                   or (_eh_suporte(t.get('remetente_ultima_msg') or '')
                       and (t.get('reply_to_ultima_msg') or '')
                       and not _eh_finaud_addr(t.get('reply_to_ultima_msg') or ''))
                else _extrair_email(t.get('destinatario_ultima_msg') or '')
            ),
            'data':          _formatar_data(t.get('data_ultima_msg')),
            'qtd_mensagens': t.get('qtd_mensagens', 0),
            'status_workflow': t.get('status_workflow') or 'Aguardando Finaud',
            'categoria': t.get('categoria') or '',
            'inativa_desde': t.get('inativa_desde'),
        }
        for t in threads
    ]
    return jsonify({'threads': resultado})


@app.route('/api/admin/log-coletas')
@_requer_login
def api_admin_log_coletas():
    logs = bt.ler_log_coletas(limite=30)
    return jsonify({'logs': logs})


@app.route('/api/admin/config', methods=['GET'])
@_requer_login
def api_admin_config_get():
    cfg = dict(_ler_config())
    cfg.pop('senha_hash', None)
    cfg['notificacoes'] = normalizar_notificacoes(cfg.get('notificacoes'))
    return jsonify(cfg)


@app.route('/api/admin/config', methods=['POST'])
@_requer_login
def api_admin_config_post():
    dados = request.get_json(silent=True) or {}
    cfg = _ler_config()
    if 'intervalo_coleta_min' in dados:
        cfg['intervalo_coleta_min'] = max(0, int(dados['intervalo_coleta_min']))
    if 'intervalo_fog_min' in dados:
        cfg['intervalo_fog_min'] = max(1, int(dados['intervalo_fog_min']))
    if 'dias_sr_af' in dados:
        cfg['dias_sr_af'] = max(1, int(dados['dias_sr_af']))
    if 'dias_sr_ac' in dados:
        cfg['dias_sr_ac'] = max(1, int(dados['dias_sr_ac']))
    if 'notificacoes' in dados:
        cfg['notificacoes'] = normalizar_notificacoes(dados.get('notificacoes'))
    _salvar_config(cfg)
    _reagendar_coleta(cfg['intervalo_coleta_min'])
    visivel = {k: v for k, v in cfg.items() if k != 'senha_hash'}
    visivel['notificacoes'] = normalizar_notificacoes(visivel.get('notificacoes'))
    return jsonify({'ok': True, 'config': visivel})


@app.route('/api/admin/situacao-busca')
@_requer_login
def api_admin_situacao_busca():
    cfg = _ler_config()
    logs = bt.ler_log_coletas(limite=30)
    return jsonify(avaliar_situacao_busca(cfg, logs, _coleta_em_andamento))


@app.route('/api/admin/log-detalhe/<int:log_id>')
@_requer_login
def api_admin_log_detalhe(log_id):
    with bt._conectar() as conn:
        log = conn.execute(
            'SELECT id, data_hora, status, mensagem, duracao_seg FROM log_coletas WHERE id = ?',
            (log_id,)
        ).fetchone()
        if not log:
            abort(404)
        resultado = {
            'id': log['id'],
            'status': log['status'],
            'mensagem': log['mensagem'] or '',
            'threads': [],
        }
        if log['status'] == 'concluida':
            dur = log['duracao_seg'] or 0
            janela = int(dur + 30)
            rows = conn.execute(
                '''SELECT assunto, categoria, status_workflow, motivo_status, destino
                   FROM threads
                   WHERE ultima_sync >= datetime(?, ? || ' seconds')
                     AND ultima_sync <= datetime(?, '+5 seconds')
                   ORDER BY ultima_sync, assunto''',
                (log['data_hora'], f'-{janela}', log['data_hora'])
            ).fetchall()
            resultado['threads'] = [
                {
                    'assunto': r['assunto'],
                    'categoria': r['categoria'],
                    'status': r['status_workflow'],
                    'motivo': r['motivo_status'],
                    'destino': r['destino'],
                }
                for r in rows
            ]
    return jsonify(resultado)


@app.route('/api/historico')
@_requer_login
def api_historico():
    from collections import OrderedDict
    with bt._conectar() as conn:
        rows = conn.execute(
            'SELECT data_hora, categoria, af, ac, co, total FROM snapshots ORDER BY data_hora'
        ).fetchall()
    snaps: OrderedDict = OrderedDict()
    for r in rows:
        dt = r['data_hora']
        if dt not in snaps:
            snaps[dt] = {}
        snaps[dt][r['categoria']] = {
            'af': r['af'], 'ac': r['ac'], 'co': r['co'], 'total': r['total']
        }
    return jsonify({
        'historico': [{'data_hora': dt, 'categorias': cats} for dt, cats in snaps.items()]
    })


@app.route('/api/historico/limites')
@_requer_login
def api_historico_limites():
    with bt._conectar() as conn:
        row = conn.execute('SELECT MIN(data_hora), MAX(data_hora) FROM snapshots').fetchone()
    return jsonify({'min': row[0], 'max': row[1]})


# ── Rotas stub (referenciadas no layout.html mas não implementadas aqui) ──────

@app.route('/custos')
@_requer_login
def page_custos():
    return render_template('monitor_custos_ia.html')


@app.route('/logout')
def logout():
    return _redirecionar_ao_portal_saindo()


@app.route('/perfil')
@_requer_login
def perfil():
    # Senha e dados da conta ficam no portal Finaud — não há tela de perfil neste app.
    return redirect(url_for('index'))


@app.route('/configuracoes')
@_requer_login
def configuracoes():
    return render_template('configuracoes.html')


# ── FOG: Telas de Casos ───────────────────────────────────────────────────────

_fog_evo_cache: dict[str, tuple[float, list]] = {}
_FOG_CACHE_TTL = 600  # 10 minutos
# Cortes de cor (dias úteis). Verde abaixo do âmbar; vermelho a partir deste valor.
_FOG_DIAS_AMBAR = 6
_FOG_DIAS_VERMELHO = 11
_cache_feriados_brasil: dict[int, set[date]] = {}


def feriados_oficiais_brasil(ano: int) -> set[date]:
    """Datas oficiais do Brasil naquele ano (nacionais, inclusive as que mudam de dia).

    Calendário usado por bancos: Carnaval, Sexta-feira Santa, Corpus Christi
    e Consciência Negra (a partir de 2024). Sem feriado de cidade.
    """
    if ano in _cache_feriados_brasil:
        return _cache_feriados_brasil[ano]
    pascoa = easter(ano)
    feriados = {
        date(ano, 1, 1),
        pascoa - timedelta(days=48),  # segunda de Carnaval
        pascoa - timedelta(days=47),  # terça de Carnaval
        pascoa - timedelta(days=2),   # Sexta-feira Santa
        date(ano, 4, 21),
        date(ano, 5, 1),
        pascoa + timedelta(days=60),  # Corpus Christi
        date(ano, 9, 7),
        date(ano, 10, 12),
        date(ano, 11, 2),
        date(ano, 11, 15),
        date(ano, 12, 25),
    }
    if ano >= 2024:
        feriados.add(date(ano, 11, 20))
    _cache_feriados_brasil[ano] = feriados
    return feriados


def contar_dias_uteis(inicio: date, fim: date) -> int:
    """Quantos dias de segunda a sexta separam duas datas.

    Não conta o dia inicial. Sábado, domingo e feriado oficial do Brasil
    ficam de fora. Mesmo dia (ou fim antes do início) devolve 0.
    """
    if inicio is None or fim is None:
        return 0
    if fim <= inicio:
        return 0
    total = 0
    dia = inicio + timedelta(days=1)
    while dia <= fim:
        if dia.weekday() < 5 and dia not in feriados_oficiais_brasil(dia.year):
            total += 1
        dia += timedelta(days=1)
    return total


def _buscar_fog(periodo: str = 'desde2025', inicio: str = None, fim: str = None) -> list[dict]:
    """Busca casos do FogBugz limitado ao período. Cache de 10 min por período."""
    import time
    cache_key = f'{inicio}|{fim}' if (inicio and fim) else periodo
    cache_entry = _fog_evo_cache.get(cache_key)
    if cache_entry and (time.time() - cache_entry[0]) < _FOG_CACHE_TTL:
        return cache_entry[1]

    token = os.environ.get('FOGBUGZ_TOKEN', '')
    if not token:
        _log.warning('FOGBUGZ_TOKEN não encontrado no .env — FOG sem dados.')
        return []

    hoje = datetime.now(timezone.utc).date()
    if inicio and fim:
        desde_str = inicio.replace('-', '/')
        ate_str = fim.replace('-', '/')
        q_str = f'opened:"{desde_str}..{ate_str}"'
    else:
        if periodo == 'semana':
            desde = hoje - timedelta(days=7)
        elif periodo == 'mes':
            desde = hoje - timedelta(days=30)
        elif periodo == '3m':
            desde = hoje - timedelta(days=90)
        elif periodo == '6m':
            desde = hoje - timedelta(days=180)
        elif periodo == 'desde2025':
            desde = hoje.replace(year=2025, month=1, day=1)
        else:
            desde = hoje.replace(year=hoje.year - 2)
        q_str = f'opened:"{desde.strftime("%Y/%m/%d")}..today"'

    url = 'https://finaud.fogbugz.com/api.asp'
    try:
        requests.get(url, params={'token': token, 'cmd': 'setCurrentFilter', 'sFilter': '218'}, timeout=10)
        resp = requests.get(url, params={
            'token': token,
            'cmd': 'search',
            'q': q_str,
            'cols': 'ixBug,sTitle,fOpen,sPersonAssignedTo,dtOpened,dtLastUpdated,dtClosed,sProject,sArea',
        }, timeout=60)
        resp.raise_for_status()
        root = _ET.fromstring(resp.text)
        resultado = []
        for c in root.findall('.//case'):
            def _t(tag): return (c.findtext(tag) or '').strip()
            status = 'Ativo' if _t('fOpen') == 'true' else 'Fechado'
            dt_str = _t('dtLastUpdated') or _t('dtOpened')
            try:
                dt_upd = datetime.fromisoformat(dt_str.replace('Z', '+00:00')).date()
                dias = contar_dias_uteis(dt_upd, hoje)
            except Exception:
                dias = 0
            dt_closed = _t('dtClosed')
            resultado.append({
                'id':               _t('ixBug'),
                'assunto':          _t('sTitle'),
                'projeto':          _t('sProject'),
                'area':             _t('sArea'),
                'responsavel':      _t('sPersonAssignedTo'),
                'status':           status,
                'dias_responsavel': dias,
                'data':             _t('dtOpened')[:10],
                'data_fechamento':  dt_closed[:10] if dt_closed else None,
            })
        resultado.sort(key=lambda x: x['dias_responsavel'], reverse=True)
        _fog_evo_cache[cache_key] = (time.time(), resultado)
        return resultado
    except Exception as e:
        _log.warning('Erro ao buscar FOG (%s): %s', cache_key, e)
        return []


@app.route('/api/fog-evolucao')
@_requer_login
def api_fog_evolucao():
    inicio = request.args.get('inicio', '')
    fim = request.args.get('fim', '')
    if inicio and fim:
        return jsonify(_buscar_fog(inicio=inicio, fim=fim))
    periodo = request.args.get('periodo', 'desde2025')
    return jsonify(_buscar_fog(periodo))


# ── Inicialização ─────────────────────────────────────────────────────────────
# Banco sempre. Relógio na tela só se o processo separado ainda não estiver no ar.

bt.criar_banco()
_cfg_inicial = _ler_config()
if _deve_ligar_agendador_na_tela():
    _reagendar_coleta(_cfg_inicial.get('intervalo_coleta_min', 60))
    _scheduler.add_job(
        _job_sem_retorno,
        'cron',
        hour=6,
        minute=0,
        id='sem_retorno_diario',
        replace_existing=True,
    )
    _agendar_vigia_busca()
    if not _scheduler.running:
        _scheduler.start()
        _log.info(
            'Agendador na tela (legado) — coleta a cada %d minuto(s). '
            'Para separar: GESTAO_AGENDADOR_EXTERNO=1 + python scripts/executar_pipeline.py --agendar',
            _cfg_inicial.get('intervalo_coleta_min', 60),
        )
else:
    _log.info(
        'Agendador na tela desligado (pytest ou GESTAO_AGENDADOR_EXTERNO). '
        'O relógio deve ser: python scripts/executar_pipeline.py --agendar'
    )

if __name__ == '__main__':
    porta = int(os.environ.get('PORT', 8004))
    _log.info('Gestão de E-mail — http://localhost:%d', porta)
    app.run(host='0.0.0.0', port=porta, debug=True, use_reloader=False)
