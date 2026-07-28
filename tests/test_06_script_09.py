"""
QA – Script 09 (enricher): --incremental e log em arquivo.

Alinhado à seção "Script 09" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import os
import tempfile

from tests.conftest import RAIZ


def test_09_incremental_e_log():
    """Script 09 deve ter modo incremental (--incremental ou --no-incremental) e log em arquivo (LOG_ENRIQUECER ou _log)."""
    path_09 = os.path.join(RAIZ, "scripts", "12_enriquecer_texto_imagens.py")
    with open(path_09, "r", encoding="utf-8") as f:
        code = f.read()
    assert "--incremental" in code or "--no-incremental" in code, "Deve ter opção de modo incremental"
    assert "incremental" in code.lower()
    assert "log" in code.lower() and ("_log" in code or "LOG_ENRIQUECER" in code or "logs" in code)


def test_09_sanitiza_crd_e_filtra_logo_bcp():
    """2026-03-30: prefixo CRD + ruído imageNNN (BCP fórum / fragmentos curtos)."""
    import importlib.util

    path_09 = os.path.join(RAIZ, "scripts", "12_enriquecer_texto_imagens.py")
    spec = importlib.util.spec_from_file_location("enrich09qa", path_09)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ruido = "p o D lixo\nCódigo do evento Descrição\nELIM2018 x 1"
    out = mod._ocr_sanitizar_prefixo_tela_crd(ruido)
    assert out.startswith("Código do evento")
    assert mod._ocr_texto_eh_ruido_logo_assinatura("91983_image002.png", "bcp) orum")
    assert mod._ocr_texto_eh_ruido_logo_assinatura("91983_image004", "(TA\nE")
    assert not mod._ocr_texto_eh_ruido_logo_assinatura(
        "91983_image001.png",
        "ELIM2018 Documento 2061 372548110",
    )
    n = mod._normalizar_ocr_interface_crd("Anterio! n Pro Total: 2\n*O Enviado para sistema de negocio")
    assert "Anterior | Próximo Total" in n
    assert "Enviado para sistema de neg" in n
    n876 = mod._normalizar_ocr_interface_crd(
        "1876.02 - INDICADOR R$ 0\n1876.20.10 - ILDC\n1 876.30 - BI"
    )
    assert "876.02" in n876 and "1876." not in n876
    assert "876.20.10" in n876
    assert "876.30" in n876
    assert mod._texto_eh_critica_crd_extraido_pdf(
        "Codigo do evento x ELIM2018 Documento 2061 " + "z" * 120
    )


def test_09_dimensoes_captura_crd_estreita():
    """2026-04-10: PNG ~342×137 (indício CRD) não é descartado antes do OCR."""
    import importlib.util

    from PIL import Image

    path_09 = os.path.join(RAIZ, "scripts", "12_enriquecer_texto_imagens.py")
    spec = importlib.util.spec_from_file_location("enrich09qa2", path_09)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.png")
        Image.new("RGB", (342, 137), color=(240, 240, 240)).save(p)
        assert mod._imagem_arquivo_dimensoes_conteudo_util(p)
        p2 = os.path.join(td, "logo.png")
        Image.new("RGB", (342, 15), color=(255, 255, 255)).save(p2)
        assert not mod._imagem_arquivo_dimensoes_conteudo_util(p2)


TESTS = [
    test_09_incremental_e_log,
    test_09_sanitiza_crd_e_filtra_logo_bcp,
    test_09_dimensoes_captura_crd_estreita,
]
