"""
test_servidor_telas.py
Sair encerra a sessão e volta ao portal Finaud — nunca ao /login deste app.
"""
from __future__ import annotations

import os
import sys

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from servidor_telas import app  # noqa: E402


def test_sair_e_logout_redirecionam_para_o_portal():
    client = app.test_client()
    for rota in ('/sair', '/logout'):
        resp = client.get(rota, follow_redirects=False)
        destino = resp.headers.get('Location', '')
        assert resp.status_code == 302, rota
        assert destino == 'https://finaudapps.com.br', rota
        assert '/login' not in destino, rota
