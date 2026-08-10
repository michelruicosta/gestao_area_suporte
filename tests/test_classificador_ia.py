"""
test_classificador_ia.py
Testes para scripts/classificador_ia.py — gabarito e integração ao prompt.
"""
from __future__ import annotations

import importlib
import json
import os
import sys

import pytest

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

CAMINHO_GAB = os.path.join(RAIZ, 'documentações', 'gabarito.json')

CATEGORIAS_VALIDAS = {
    'DDR_2011', 'SCD_4111', 'DRM_2060', 'DLO_2061', 'DLI_2062',
    'DRL_2160', 'S5', 'RETORNO_BACEN', 'FORCAPITAL', 'DRSAC_2030',
    'PVCA_6209', 'SUPORTE',
}


def test_gabarito_arquivo_existe():
    """gabarito.json existe em documentações/ e é JSON válido."""
    assert os.path.isfile(CAMINHO_GAB), 'gabarito.json não encontrado em documentações/'
    with open(CAMINHO_GAB, encoding='utf-8') as f:
        dados = json.load(f)
    assert isinstance(dados.get('exemplos'), list), "gabarito.json deve ter campo 'exemplos' (lista)"


def test_gabarito_campos_obrigatorios():
    """Cada exemplo tem id, categoria, assunto_exemplo e regra."""
    with open(CAMINHO_GAB, encoding='utf-8') as f:
        dados = json.load(f)
    campos = {'id', 'categoria', 'assunto_exemplo', 'regra'}
    for ex in dados['exemplos']:
        faltando = campos - set(ex.keys())
        assert not faltando, f"Exemplo {ex.get('id', '?')} sem campos: {faltando}"


def test_gabarito_categorias_validas():
    """Todos os exemplos usam categorias válidas do sistema."""
    with open(CAMINHO_GAB, encoding='utf-8') as f:
        dados = json.load(f)
    for ex in dados['exemplos']:
        cat = ex.get('categoria', '')
        assert cat in CATEGORIAS_VALIDAS, f"{ex['id']}: categoria '{cat}' inválida"


def test_gabarito_ids_unicos():
    """Todos os IDs no gabarito são únicos."""
    with open(CAMINHO_GAB, encoding='utf-8') as f:
        dados = json.load(f)
    ids = [ex['id'] for ex in dados['exemplos']]
    duplicados = [i for i in ids if ids.count(i) > 1]
    assert not duplicados, f"IDs duplicados no gabarito: {duplicados}"


def test_gabarito_integrado_no_prompt():
    """O conteúdo do gabarito aparece em _SISTEMA do classificador_ia."""
    mod = importlib.import_module('classificador_ia')
    sistema = mod._SISTEMA
    assert 'EXTRATO COMPROMISSADA' in sistema, \
        "_SISTEMA deve conter exemplos do gabarito (EXTRATO COMPROMISSADA)"
    assert 'G-DDR-001' in sistema, \
        "_SISTEMA deve conter o ID G-DDR-001"
    assert 'Exemplos confirmados' in sistema, \
        "_SISTEMA deve ter a seção 'Exemplos confirmados'"
