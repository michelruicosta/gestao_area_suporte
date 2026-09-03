"""
test_coletor_html.py
Testes para _HTMLParaTexto e _extrair_texto do coletor_gmail.py.
"""
from __future__ import annotations

import base64
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from coletor_gmail import _HTMLParaTexto, _html_para_texto, _extrair_texto


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode('utf-8')).decode()


# ── _HTMLParaTexto ─────────────────────────────────────────────────────────────

def test_html_para_texto_simples():
    parser = _HTMLParaTexto()
    parser.feed('<p>Prezados, bom dia!</p><p>Seguem extratos em anexo.</p>')
    assert 'Prezados, bom dia!' in parser.resultado()
    assert 'Seguem extratos em anexo.' in parser.resultado()


def test_html_para_texto_remove_tags_script_style():
    parser = _HTMLParaTexto()
    parser.feed('<style>body{color:red}</style><p>Texto visível</p><script>alert(1)</script>')
    resultado = parser.resultado()
    assert 'Texto visível' in resultado
    assert 'color:red' not in resultado
    assert 'alert' not in resultado


def test_html_para_texto_br_vira_newline():
    parser = _HTMLParaTexto()
    parser.feed('Linha 1<br>Linha 2<br/>Linha 3')
    resultado = parser.resultado()
    assert 'Linha 1' in resultado
    assert 'Linha 2' in resultado
    assert 'Linha 3' in resultado
    assert '\n' in resultado


def test_html_para_texto_entidade_nbsp():
    # &nbsp; (U+00A0) é normalizado para espaço comum no resultado
    parser = _HTMLParaTexto()
    parser.feed('Olá&nbsp;mundo')
    assert 'Olá mundo' in parser.resultado()


def test_html_para_texto_sem_conteudo_retorna_vazio():
    parser = _HTMLParaTexto()
    parser.feed('<html><head><title>T</title></head><body></body></html>')
    assert parser.resultado() == ''


def test_html_para_texto_colapsa_espacos_extras():
    parser = _HTMLParaTexto()
    parser.feed('<p>   Texto   com   espaços   </p>')
    resultado = parser.resultado()
    assert '  ' not in resultado


# ── _html_para_texto (base64 decode + parse) ──────────────────────────────────

def test_html_para_texto_decodifica_base64():
    html = '<p>Relatório de serviço</p><p>Data: 01/09/2026</p>'
    resultado = _html_para_texto(_b64(html))
    assert 'Relatório de serviço' in resultado
    assert 'Data: 01/09/2026' in resultado


def test_html_para_texto_base64_invalido_retorna_vazio():
    resultado = _html_para_texto('não_é_base64_válido!!!')
    assert resultado == ''


# ── _extrair_texto com payload HTML-only ──────────────────────────────────────

def test_extrair_texto_html_only_extrai_conteudo():
    html = '<p>Bom dia, seguem extratos em anexo.</p>'
    payload = {'mimeType': 'text/html', 'body': {'data': _b64(html)}}
    resultado = _extrair_texto(payload)
    assert 'Bom dia' in resultado
    assert '[somente HTML]' not in resultado


def test_extrair_texto_plain_tem_prioridade_sobre_html():
    html = '<p>Versão HTML</p>'
    plain = 'Versão plain text'
    payload = {
        'mimeType': 'multipart/alternative',
        'parts': [
            {'mimeType': 'text/plain', 'body': {'data': _b64(plain)}},
            {'mimeType': 'text/html',  'body': {'data': _b64(html)}},
        ],
    }
    resultado = _extrair_texto(payload)
    assert resultado == plain
    assert 'HTML' not in resultado


def test_extrair_texto_usa_html_quando_nao_tem_plain():
    html = '<p>Atualização BACEN — 01/09/2026</p>'
    payload = {
        'mimeType': 'multipart/alternative',
        'parts': [
            {'mimeType': 'text/html', 'body': {'data': _b64(html)}},
        ],
    }
    resultado = _extrair_texto(payload)
    assert 'Atualização BACEN' in resultado
    assert '[somente HTML]' not in resultado


def test_extrair_texto_vazio_quando_sem_dados():
    payload = {'mimeType': 'text/html', 'body': {'data': ''}}
    assert _extrair_texto(payload) == ''
