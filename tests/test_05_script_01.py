"""
QA – Script 01 (coletor e-mail): mensagem amigável em erro getaddrinfo.

Alinhado à seção "Script 01" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import os
from tests.conftest import RAIZ


def test_01_mensagem_amigavel_getaddrinfo():
    """Em erro getaddrinfo/rede deve sugerir internet, firewall, proxy ou DNS."""
    path_01 = os.path.join(RAIZ, "scripts", "02_coletar_emails_gmail.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "getaddrinfo" in code or "Errno 11001" in code or "rede" in code.lower() or "DNS" in code
    assert "firewall" in code.lower() or "proxy" in code.lower() or "internet" in code.lower() or "DNS" in code


def test_02_x_gm_thrid_para_agrupar_threads():
    """Coletor usa X-GM-THRID do Gmail para agrupar conversas (correção 2026-03-11)."""
    path_01 = os.path.join(RAIZ, "scripts", "02_coletar_emails_gmail.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "X-GM-THRID" in code, "Deve usar X-GM-THRID no FETCH"
    assert "x_gm_thrid" in code, "Deve gravar x_gm_thrid no JSON"
    assert "thread_root" in code and "x_gm_thrid" in code, "thread_root deve priorizar x_gm_thrid"


def test_03_qualquer_finaud_com_br_em_from_to():
    """Coletor busca qualquer @finaud.com.br em FROM/TO (correção 2026-03-19)."""
    path_01 = os.path.join(RAIZ, "scripts", "02_coletar_emails_gmail.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert 'FROM "@finaud.com.br"' in code, "Critério deve usar @finaud.com.br em FROM"
    assert 'TO "@finaud.com.br"' in code, "Critério deve usar @finaud.com.br em TO"


def test_04_imagens_inline_exceto_assinatura():
    """Coletor grava imagens inline (dentro do corpo), exceto assinatura/logo (correção 2026-03-20)."""
    path_01 = os.path.join(RAIZ, "scripts", "02_coletar_emails_gmail.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "IMAGEM_INLINE_EXCLUIR_NOME" in code, "Deve ter lista de exclusão para inline"
    assert "assinatura" in code.lower() or "signature" in code.lower()
    assert "eh_inline" in code or "inline" in code, "Deve tratar imagens inline"


def test_05_content_id_formato_outlook():
    """Coletor trata Content-ID no formato Outlook/Word (image001.png@01DCA4B3.E48D9EE0) — correção 2026-03-20."""
    path_01 = os.path.join(RAIZ, "scripts", "02_coletar_emails_gmail.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert '"@" in cid' in code or "'@' in cid" in code, "Deve detectar formato filename@id"
    assert 'split("@", 1)' in code or 'split(\'@\', 1)' in code, "Deve extrair parte antes do @"
    assert "20 * 1024" in code or "MIN_TAMANHO_IMAGEM_BYTES" in code, "Tamanho mínimo para anexos imagem explícitos"


def test_06_imagem_inline_somente_retorno_bacen():
    """Imagens inline (cid): Retorno Bacen ou DLO/DLI + crítica no corpo; sem RD_* (2026-03-30 / 31)."""
    path_01 = os.path.join(RAIZ, "scripts", "02_coletar_emails_gmail.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "assunto_indica_retorno_bacen" in code
    assert "corpus_tem_indicador_rd_ddr" in code
    assert "permitir_imagem_inline_corpo" in code
    assert "corpus_indica_critica_em_relatorio_dlo" in code
    assert "TIPIFICACAO_RETORNO_BACEN" in code or "tipificacao_retorno_bacen" in code.lower()


TESTS = [
    test_01_mensagem_amigavel_getaddrinfo,
    test_02_x_gm_thrid_para_agrupar_threads,
    test_03_qualquer_finaud_com_br_em_from_to,
    test_04_imagens_inline_exceto_assinatura,
    test_05_content_id_formato_outlook,
    test_06_imagem_inline_somente_retorno_bacen,
]
