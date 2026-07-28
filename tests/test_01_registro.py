"""
QA – Registro de correções (REGISTRO_CORRECOES.md).

Garante que o arquivo existe e referência as principais correções.
Alinhado à seção "Registro" e ao fluxo: 1) ler correções 2) montar cenário QA 3) rodar QA.
"""
from __future__ import annotations

import os
from tests.conftest import RAIZ


def test_registro_existe_e_referencia_correcoes():
    """REGISTRO_CORRECOES.md deve existir e referir principais correções (filtro, MIME, CADOCs)."""
    path_reg = os.path.join(RAIZ, "documentações", "REGISTRO_CORRECOES.md")
    assert os.path.isfile(path_reg), f"Arquivo não encontrado: {path_reg}"
    with open(path_reg, "r", encoding="utf-8") as f:
        content = f.read()
    assert "FILTRADO_POR_DATA" in content or "filtro" in content.lower()
    assert "decodeMimeHeader" in content or "MIME" in content or "CADOCs únicos" in content


TESTS = [test_registro_existe_e_referencia_correcoes]
