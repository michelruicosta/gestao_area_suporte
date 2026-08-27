"""SSO do portal abre o app sem a tela de login local."""
from __future__ import annotations

import os
import sys

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import portal_sso as sso  # noqa: E402
import servidor_telas as st  # noqa: E402
from servidor_telas import app  # noqa: E402


def test_home_sem_cookie_vai_para_login():
    resp = app.test_client().get('/', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in (resp.headers.get('Location') or '')


def test_home_com_cookie_do_portal_abre_direto(monkeypatch):
    monkeypatch.setattr(
        sso,
        'consultar_usuario_portal',
        lambda *a, **k: sso.UsuarioPortal(
            email='michel@finaud.com.br',
            nome='Michel Costa',
            perfil_codigo='administrador',
        ),
    )
    client = app.test_client()
    client.set_cookie('finaud_portal_sessao', 'token-teste')
    resp = client.get('/', follow_redirects=False)
    assert resp.status_code == 200
    assert b'login' not in (resp.headers.get('Location') or '').encode()


def test_login_get_com_cookie_do_portal_pula_a_tela(monkeypatch):
    monkeypatch.setattr(
        sso,
        'consultar_usuario_portal',
        lambda *a, **k: sso.UsuarioPortal(
            email='michel@finaud.com.br',
            nome='Michel Costa',
            perfil_codigo='administrador',
        ),
    )
    client = app.test_client()
    client.set_cookie('auditoria_sessao', 'token-teste')
    resp = client.get('/login', follow_redirects=False)
    assert resp.status_code == 302
    destino = resp.headers.get('Location') or ''
    assert destino.endswith('/')
    assert '/login' not in destino


def test_portal_auth_padrao_e_8000_nao_8002(monkeypatch):
    """No PC, 8002 é Normativos. SSO deste app consulta o portal na 8000."""
    monkeypatch.delenv('PORTAL_AUTH_URL', raising=False)
    import importlib

    importlib.reload(sso)
    assert sso.PORTAL_AUTH_URL == 'http://127.0.0.1:8000'
