"""
QA – Script verificar_thread_gmail.py: verificar quantas mensagens na thread no Gmail.

Alinhado à correção 2026-03-16 no REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import os

import pytest

from tests.conftest import RAIZ


@pytest.mark.xfail(reason="Pendente: verificar_thread_gmail.py não existe ainda", strict=False)
def test_verificar_thread_gmail_existe():
    """Script verificar_thread_gmail.py existe e usa X-GM-THRID para contar mensagens."""
    path = os.path.join(RAIZ, "scripts", "verificar_thread_gmail.py")
    assert os.path.isfile(path), "Script verificar_thread_gmail.py deve existir"
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    assert "X-GM-THRID" in code, "Deve usar X-GM-THRID para contar mensagens na conversa"
    assert "conectar_imap" in code or "IMAP4_SSL" in code, "Deve conectar ao Gmail via IMAP"
    assert "Mensagens na MESMA conversa" in code, "Deve exibir contagem de mensagens na thread"


TESTS = [test_verificar_thread_gmail_existe]
