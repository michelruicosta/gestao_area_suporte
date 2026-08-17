"""
servidor_telas.py
O que faz: servidor Flask que serve as telas de Gestão de E-mail do Oráculo 360
           e fornece dados ao vivo do banco SQLite via API REST.
Porta: 5000   Rodar: python scripts/servidor_telas.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from functools import wraps

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR    = os.path.dirname(_SCRIPTS_DIR)

sys.path.insert(0, _SCRIPTS_DIR)
import banco_threads as bt

app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT_DIR, 'templates'),
    static_folder=os.path.join(_ROOT_DIR, 'static'),
)
app.secret_key = os.environ.get('SECRET_KEY', 'oraculo360-gestao-secret')

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
    return render_template('gestao_email.html', email=session.get('email', ''))


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

    return jsonify({
        'categorias': categorias,
        'totais':     {'af': total_af, 'ac': total_ac, 'co': total_co, 'total': total},
        'nao_class':  cd.get('revisao', 0) + cd.get('sem_classificar', 0),
        'bloqueados': cd.get('descartes', 0),
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
                if _eh_suporte(t.get('remetente_ultima_msg') or '')
                   and not _eh_finaud_addr(t.get('reply_to_ultima_msg') or '')
                   and (t.get('reply_to_ultima_msg') or '')
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
        bt.buscar_por_destino('revisao') + bt.buscar_sem_classificar(),
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
    threads = sorted(bt.buscar_por_destino('descartes'), key=_chave_data, reverse=True)
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


# ── Inicialização ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    bt.criar_banco()
    porta = int(os.environ.get('PORT', 5001))
    print(f'Gestão de E-mail — http://localhost:{porta}')
    app.run(host='0.0.0.0', port=porta, debug=True)
