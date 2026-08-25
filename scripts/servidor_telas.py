"""
servidor_telas.py
O que faz: servidor Flask que serve as telas de Gestão de E-mail do Gestão Área Suporte
           e fornece dados ao vivo do banco SQLite via API REST.
Porta: 5000   Rodar: python scripts/servidor_telas.py
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import threading

# Windows usa charmap por padrão — força UTF-8 para suportar emojis nos logs
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import requests
import xml.etree.ElementTree as _ET
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from apscheduler.schedulers.background import BackgroundScheduler

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR    = os.path.dirname(_SCRIPTS_DIR)
_CONFIG_PATH = os.path.join(_ROOT_DIR, 'data', 'config.json')

sys.path.insert(0, _SCRIPTS_DIR)
import banco_threads as bt

app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT_DIR, 'templates'),
    static_folder=os.path.join(_ROOT_DIR, 'static'),
)
app.secret_key = os.environ.get('SECRET_KEY', 'oraculo360-gestao-secret')

_coleta_em_andamento = False
_ultimo_erro_coleta: str | None = None

# ── Configurações persistentes ─────────────────────────────────────────────────

def _ler_config() -> dict:
    try:
        with open(_CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'intervalo_coleta_min': 60, 'intervalo_fog_min': 15}

def _salvar_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── Agendador de coleta automática ────────────────────────────────────────────

_scheduler = BackgroundScheduler(daemon=True)

def _job_coleta_automatica():
    global _coleta_em_andamento, _ultimo_erro_coleta
    if _coleta_em_andamento:
        return
    _coleta_em_andamento = True
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
        import traceback
        _ultimo_erro_coleta = str(e)
        print(f'[ERRO] Coleta automática falhou: {e}')
        traceback.print_exc()
    finally:
        _coleta_em_andamento = False

def _reagendar_coleta(intervalo_min: int) -> None:
    if _scheduler.get_job('coleta_automatica'):
        _scheduler.remove_job('coleta_automatica')
    if intervalo_min > 0:
        _scheduler.add_job(
            _job_coleta_automatica,
            'interval',
            minutes=intervalo_min,
            id='coleta_automatica',
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


# Credencial de acesso (variáveis de ambiente sobrescrevem o padrão)
_ADMIN_EMAIL = os.environ.get('GESTAO_EMAIL', 'michel@finaud.com.br')
_ADMIN_SENHA = os.environ.get('GESTAO_SENHA', 'finaud2026')

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


# ── Autenticação ──────────────────────────────────────────────────────────────

def _requer_login(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get('logado'):
            if request.is_json:
                return jsonify({'erro': 'não autenticado'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return _wrap


@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        senha = (request.form.get('senha') or '').strip()
        if email == _ADMIN_EMAIL and senha == _ADMIN_SENHA:
            session['logado'] = True
            session['email']  = email
            return redirect(url_for('index'))
        erro = 'E-mail ou senha incorretos.'
    return render_template('gestao_login.html', erro=erro)


@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('login'))


# ── Tela principal ─────────────────────────────────────────────────────────────

@app.route('/')
@_requer_login
def index():
    from collections import defaultdict
    _fog = _buscar_fog()
    ativos   = [t for t in _fog if t['status'] == 'Ativo']
    fechados = [t for t in _fog if t['status'] == 'Fechado']
    n = len(ativos) or 1
    em_and  = sum(1 for t in ativos if t['dias_responsavel'] < 8)
    atencao = sum(1 for t in ativos if 8 <= t['dias_responsavel'] < 15)
    critico = sum(1 for t in ativos if t['dias_responsavel'] >= 15)
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
    return jsonify({
        'categorias': categorias,
        'totais':     {'af': total_af, 'ac': total_ac, 'co': total_co, 'total': total},
        'nao_class':  nv['nao_class'],
        'bloqueados': nv['bloqueados'],
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
            import traceback
            _ultimo_erro_coleta = str(e)
            print(f'[ERRO] Coleta falhou: {e}')
            traceback.print_exc()
        finally:
            _coleta_em_andamento = False

    _coleta_em_andamento = True
    threading.Thread(target=_rodar, daemon=True).start()
    return jsonify({'ok': True, 'mensagem': 'Coleta iniciada em segundo plano.'})


@app.route('/api/admin/status-coleta')
@_requer_login
def api_admin_status_coleta():
    return jsonify({'em_andamento': _coleta_em_andamento, 'ultimo_erro': _ultimo_erro_coleta})


@app.route('/api/admin/log-coletas')
@_requer_login
def api_admin_log_coletas():
    logs = bt.ler_log_coletas(limite=30)
    return jsonify({'logs': logs})


@app.route('/api/admin/config', methods=['GET'])
@_requer_login
def api_admin_config_get():
    return jsonify(_ler_config())


@app.route('/api/admin/config', methods=['POST'])
@_requer_login
def api_admin_config_post():
    dados = request.get_json(silent=True) or {}
    cfg = _ler_config()
    if 'intervalo_coleta_min' in dados:
        cfg['intervalo_coleta_min'] = max(0, int(dados['intervalo_coleta_min']))
    if 'intervalo_fog_min' in dados:
        cfg['intervalo_fog_min'] = max(1, int(dados['intervalo_fog_min']))
    _salvar_config(cfg)
    _reagendar_coleta(cfg['intervalo_coleta_min'])
    return jsonify({'ok': True, 'config': cfg})


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
    session.clear()
    return redirect(url_for('login'))


@app.route('/perfil')
@_requer_login
def perfil():
    return render_template('perfil.html')


@app.route('/configuracoes')
@_requer_login
def configuracoes():
    return render_template('configuracoes.html')


# ── FOG: Telas de Casos ───────────────────────────────────────────────────────

_fog_evo_cache: dict[str, tuple[float, list]] = {}
_FOG_CACHE_TTL = 600  # 10 minutos


def _buscar_fog(periodo: str = '6m') -> list[dict]:
    """Busca casos do FogBugz limitado ao período. Cache de 10 min por período."""
    import time
    cache_entry = _fog_evo_cache.get(periodo)
    if cache_entry and (time.time() - cache_entry[0]) < _FOG_CACHE_TTL:
        return cache_entry[1]

    token = os.environ.get('FOGBUGZ_TOKEN', '')
    if not token:
        print('⚠️  FOGBUGZ_TOKEN não encontrado no .env — FOG sem dados.')
        return []

    hoje = datetime.now(timezone.utc).date()
    if periodo == 'semana':
        desde = hoje - timedelta(days=7)
    elif periodo == 'mes':
        desde = hoje - timedelta(days=30)
    elif periodo == '3m':
        desde = hoje - timedelta(days=90)
    elif periodo == '6m':
        desde = hoje - timedelta(days=180)
    else:
        desde = hoje.replace(year=hoje.year - 2)
    desde_str = desde.strftime('%Y/%m/%d')

    url = 'https://finaud.fogbugz.com/api.asp'
    try:
        requests.get(url, params={'token': token, 'cmd': 'setCurrentFilter', 'sFilter': '218'}, timeout=10)
        resp = requests.get(url, params={
            'token': token,
            'cmd': 'search',
            'q': f'opened:"{desde_str}..today"',
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
                dias = (hoje - dt_upd).days
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
        _fog_evo_cache[periodo] = (time.time(), resultado)
        return resultado
    except Exception as e:
        print(f'⚠️  Erro ao buscar FOG ({periodo}): {e}')
        return []


@app.route('/api/fog-evolucao')
@_requer_login
def api_fog_evolucao():
    periodo = request.args.get('periodo', 'semana')
    return jsonify(_buscar_fog(periodo))


@app.route('/fog/operacional')
@_requer_login
def fog_operacional():
    _fog = _buscar_fog()
    projetos     = sorted({t['projeto']    for t in _fog})
    areas        = sorted({t['area']       for t in _fog})
    responsaveis = sorted({t['responsavel'] for t in _fog if t['status'] == 'Ativo'})
    return render_template('fog_operacional.html',
                           tarefas=_fog, projetos=projetos,
                           areas=areas, responsaveis=responsaveis,
                           simulado=False)


@app.route('/fog/gerencial')
@_requer_login
def fog_gerencial():
    from collections import defaultdict
    _fog = _buscar_fog()
    ativos   = [t for t in _fog if t['status'] == 'Ativo']
    fechados = [t for t in _fog if t['status'] == 'Fechado']
    n = len(ativos) or 1
    em_and  = sum(1 for t in ativos if t['dias_responsavel'] < 8)
    atencao = sum(1 for t in ativos if 8 <= t['dias_responsavel'] < 15)
    critico = sum(1 for t in ativos if t['dias_responsavel'] >= 15)
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
    stats = {
        'total_ativos':     len(ativos),
        'em_andamento':     {'qtd': em_and,  'perc': round(em_and  / n * 100)},
        'atencao':          {'qtd': atencao, 'perc': round(atencao / n * 100)},
        'critico':          {'qtd': critico, 'perc': round(critico / n * 100)},
        'total_concluidos': len(fechados),
        'ranking':          ranking,
    }
    return render_template('fog_gerencial.html', stats=stats, simulado=False)


# ── Inicialização ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    bt.criar_banco()
    cfg_inicial = _ler_config()
    _reagendar_coleta(cfg_inicial.get('intervalo_coleta_min', 60))
    _scheduler.start()
    porta = int(os.environ.get('PORT', 5001))
    print(f'Gestão de E-mail — http://localhost:{porta}')
    app.run(host='0.0.0.0', port=porta, debug=True, use_reloader=False)
