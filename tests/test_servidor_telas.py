"""
test_servidor_telas.py
Sair volta ao portal. Login segue o padrão Finaud (olho na senha, sem Esqueceu a senha).
"""
from __future__ import annotations

import os
import sys

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import servidor_telas as st  # noqa: E402
from servidor_telas import app  # noqa: E402


def test_sair_e_logout_redirecionam_para_o_portal():
    client = app.test_client()
    for rota in ('/sair', '/logout'):
        resp = client.get(rota, follow_redirects=False)
        destino = resp.headers.get('Location', '')
        assert resp.status_code == 302, rota
        assert destino == 'http://127.0.0.1:8000/portal-preview/', rota
        assert '/login' not in destino, rota

    for rota in ('/sair', '/logout'):
        resp = client.get(
            rota,
            follow_redirects=False,
            headers={'Host': 'gestao-suporte.finaudapps.com.br'},
        )
        destino = resp.headers.get('Location', '')
        assert resp.status_code == 302, rota
        assert destino == 'https://finaudapps.com.br', rota
        assert '/login' not in destino, rota


def test_login_sem_esqueceu_senha_olho_dentro_do_campo():
    """Senha se recupera no portal — o login do app não mostra Esqueceu a senha."""
    html = app.test_client().get('/login').get_data(as_text=True)
    assert 'Esqueceu a senha?' not in html
    assert 'form-recuperar' not in html
    assert 'Recuperar acesso' not in html
    assert 'Enviar senha temporária' not in html
    assert 'campo-senha-toggle' in html
    assert 'class="olho-btn"' not in html
    assert 'Entrar' in html
    assert 'Portal de apps' in html


def test_recuperar_senha_nao_revela_se_email_existe(monkeypatch):
    monkeypatch.setattr(st, '_enviar_senha_temporaria', lambda *a, **k: False)
    client = app.test_client()
    mensagens = []
    for email in (st._ADMIN_EMAIL, 'naoexiste@finaud.com.br'):
        resp = client.post('/auth/recuperar-senha', json={'email': email})
        assert resp.status_code == 200, email
        body = resp.get_json()
        mensagens.append(body['mensagem'])
        assert body['mensagem'] == st._MENSAGEM_RECUPERAR
    assert mensagens[0] == mensagens[1]


def test_recuperar_senha_grava_hash_quando_email_sai(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"intervalo_coleta_min": 60, "intervalo_fog_min": 15}', encoding='utf-8')
    monkeypatch.setattr(st, '_CONFIG_PATH', str(cfg))
    enviados = []

    def fake_enviar(destino, senha_temp, url_login):
        enviados.append((destino, senha_temp, url_login))
        return True

    monkeypatch.setattr(st, '_enviar_senha_temporaria', fake_enviar)
    client = app.test_client()
    resp = client.post('/auth/recuperar-senha', json={'email': st._ADMIN_EMAIL})
    assert resp.status_code == 200
    assert enviados
    nova = enviados[0][1]

    falha = client.post(
        '/login',
        data={'email': st._ADMIN_EMAIL, 'senha': st._ADMIN_SENHA},
        follow_redirects=False,
    )
    assert falha.status_code == 200
    assert 'incorretos' in falha.get_data(as_text=True)

    ok = client.post(
        '/login',
        data={'email': st._ADMIN_EMAIL, 'senha': nova},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers.get('Location', '').endswith('/')


def test_rotas_fog_antigas_nao_existem():
    client = app.test_client()
    for rota in ('/fog/gerencial', '/fog/operacional'):
        resp = client.get(rota, follow_redirects=False)
        assert resp.status_code == 404, rota


def test_porta_padrao_no_pc_e_8004():
    """No PC a tela Flask sobe em 8004 — não 5001 nem porta de outro app."""
    import inspect

    fonte = inspect.getsource(st)
    assert "os.environ.get('PORT', 8004)" in fonte


def test_menu_usuario_nao_tem_meu_perfil():
    """Senha passa a ser alterada no portal — o Gestão não mostra Meu Perfil."""
    caminho = os.path.join(RAIZ, 'templates', 'gestao_email.html')
    with open(caminho, encoding='utf-8') as f:
        html = f.read()
    assert 'Meu Perfil' not in html
    assert 'abrirPerfil' not in html
    assert 'Alterar senha' not in html
    assert 'user-menu' in html
    assert '/sair' in html


def test_codigo_nao_guarda_senha_nem_chave_de_fabrica():
    """Se o .env faltar, não pode sobrar senha/chave conhecida no código."""
    caminho = os.path.join(RAIZ, 'scripts', 'servidor_telas.py')
    with open(caminho, encoding='utf-8') as f:
        fonte = f.read()
    assert 'finaud2026' not in fonte
    assert 'oraculo360-gestao-secret' not in fonte
    assert "os.environ.get('SECRET_KEY', " not in fonte
    assert "os.environ.get('GESTAO_SENHA', " not in fonte


def test_login_local_sem_senha_configurada_nao_entra(monkeypatch):
    """Sem GESTAO_SENHA e sem hash, a tela de login local recusa qualquer senha."""
    monkeypatch.setattr(st, '_ADMIN_SENHA', '')
    monkeypatch.setattr(st, '_ler_config', lambda: {})
    resp = app.test_client().post(
        '/login',
        data={'email': st._ADMIN_EMAIL, 'senha': 'qualquer-coisa'},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert 'incorretos' in resp.get_data(as_text=True)


def test_rota_perfil_volta_para_a_tela_principal():
    """Quem abrir /perfil (atalho antigo) cai na tela principal, não numa página quebrada."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['logado'] = True
        sess['email'] = st._ADMIN_EMAIL
    resp = client.get('/perfil', follow_redirects=False)
    assert resp.status_code == 302
    destino = resp.headers.get('Location', '')
    assert destino.endswith('/')
    assert '/perfil' not in destino.rstrip('/')
