"""
test_servidor_telas.py
Sair volta ao portal. Recuperar senha segue o fluxo Finaud (e-mail → senha temporária).
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
        assert destino == 'https://finaudapps.com.br', rota
        assert '/login' not in destino, rota


def test_login_tem_fluxo_recuperar_senha():
    html = app.test_client().get('/login').get_data(as_text=True)
    assert 'Esqueceu a senha?' in html
    assert 'onclick="return false;"' not in html
    assert 'Recuperar acesso' in html
    assert 'form-recuperar' in html
    assert 'Enviar senha temporária' in html


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
