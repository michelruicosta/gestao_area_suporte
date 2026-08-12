"""
test_classificador_ia.py
Testes para scripts/classificador_ia.py — classificador determinístico de threads.
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

CAMINHO_REGRAS = os.path.join(RAIZ, 'documentações', 'regras_classificador_threads.json')

CATEGORIAS_VALIDAS = {
    'DDR_2011', 'SALDOS_CONTABEIS_DIARIOS_4111', 'DRM_2060', 'DLO_2061', 'DLI_2062',
    'DRL_2160', 'S5', 'RETORNO_BACEN', 'FORCAPITAL', 'DRSAC_2030',
    'PVCA_6209', 'SUPORTE', 'INTERNO',
}


# ── Testes do arquivo regras_classificador_threads.json ───────────────────────

def test_regras_arquivo_existe():
    """regras_classificador_threads.json existe e tem as seções regras_prioridade, regras e gabaritos."""
    assert os.path.isfile(CAMINHO_REGRAS), 'regras_classificador_threads.json não encontrado em documentações/'
    with open(CAMINHO_REGRAS, encoding='utf-8') as f:
        dados = json.load(f)
    assert isinstance(dados.get('regras_prioridade'), list), "deve ter campo 'regras_prioridade' (lista)"
    assert isinstance(dados.get('regras'), list), "deve ter campo 'regras' (lista)"
    assert isinstance(dados.get('gabaritos'), list), "deve ter campo 'gabaritos' (lista)"


def test_regras_campos_obrigatorios():
    """Regras de prioridade têm ordem e instrucao. Regras têm id, categorias, padrao, instrucao. Gabaritos têm id, categorias, assunto_exemplo, por_que_gabarito."""
    with open(CAMINHO_REGRAS, encoding='utf-8') as f:
        dados = json.load(f)
    campos_prioridade = {'ordem', 'id', 'instrucao'}
    campos_regra      = {'id', 'categorias', 'padrao', 'instrucao'}
    campos_gabarito   = {'id', 'categorias', 'assunto_exemplo', 'por_que_gabarito'}
    for p in dados['regras_prioridade']:
        faltando = campos_prioridade - set(p.keys())
        assert not faltando, f"Prioridade {p.get('id', '?')} sem campos: {faltando}"
    for r in dados['regras']:
        faltando = campos_regra - set(r.keys())
        assert not faltando, f"Regra {r.get('id', '?')} sem campos: {faltando}"
    for g in dados['gabaritos']:
        faltando = campos_gabarito - set(g.keys())
        assert not faltando, f"Gabarito {g.get('id', '?')} sem campos: {faltando}"


def test_regras_categorias_validas():
    """Todas as entradas usam categorias válidas do sistema."""
    with open(CAMINHO_REGRAS, encoding='utf-8') as f:
        dados = json.load(f)
    for entrada in dados['regras'] + dados['gabaritos']:
        cats = entrada.get('categorias', [])
        assert isinstance(cats, list) and cats, \
            f"{entrada.get('id', '?')}: 'categorias' deve ser lista não vazia"
        for cat in cats:
            assert cat in CATEGORIAS_VALIDAS, \
                f"{entrada.get('id', '?')}: categoria '{cat}' inválida"


def test_regras_ids_unicos():
    """Todos os IDs em regras + gabaritos são únicos."""
    with open(CAMINHO_REGRAS, encoding='utf-8') as f:
        dados = json.load(f)
    ids = [e['id'] for e in dados['regras'] + dados['gabaritos']]
    duplicados = [i for i in ids if ids.count(i) > 1]
    assert not duplicados, f"IDs duplicados: {duplicados}"


# ── Testes de normalização ────────────────────────────────────────────────────

def test_normalizacao_saldos_contabeis():
    """Variações do nome legível de SALDOS_CONTABEIS_DIARIOS_4111 são normalizadas."""
    mod = importlib.import_module('classificador_ia')
    norm = mod._NORM_CATEGORIAS
    variacoes = [
        'Saldos Contábeis Diários 4111',
        'saldos contábeis diários 4111',
        'SALDOS CONTABEIS DIARIOS 4111',
        'Saldos_Contabeis_Diarios_4111',
    ]
    for v in variacoes:
        assert norm.get(v) == 'SALDOS_CONTABEIS_DIARIOS_4111', \
            f"Variação '{v}' não normalizada corretamente"


# ── Testes do classificador determinístico ────────────────────────────────────

def _classificar(assunto: str, corpo: str = '', nomes_anexos: list | None = None) -> dict:
    """Atalho para chamar classificar_thread com thread simples."""
    mod = importlib.import_module('classificador_ia')
    thread = {
        'assunto': assunto,
        'mensagens': [{'corpo_texto': corpo, 'nomes_anexos': nomes_anexos or []}],
    }
    return mod.classificar_thread(thread)


def test_classificar_extrato_compromissada_ddr():
    """'EXTRATO COMPROMISSADA' no assunto → DDR_2011."""
    r = _classificar('EXTRATO COMPROMISSADA - TRUSTEE DTVM - JUNHO 2026')
    assert r['categorias'] == ['DDR_2011']
    assert r['incerto'] is False


def test_classificar_dtvm_nao_aciona_ddr():
    """'DTVM' no assunto NÃO ativa DDR (word boundary evita confundir DTVM com TVM)."""
    r = _classificar('DTVM - COS4016 DE JUNHO/2026')
    assert 'DDR_2011' not in r['categorias'], 'DTVM não deve acionar DDR_2011'
    assert 'DLO_2061' in r['categorias'], 'COS4016 deve acionar DLO_2061'


def test_classificar_dlo_e_dli_juntos():
    """Assunto com DLO e DLI → ambas as categorias."""
    r = _classificar('DLO E DLI - JUNHO 2026')
    assert 'DLO_2061' in r['categorias']
    assert 'DLI_2062' in r['categorias']


def test_classificar_retorno_bacen_aviso_de_atraso():
    """'AVISO DE ATRASO' no assunto → RETORNO_BACEN (prioridade máxima)."""
    r = _classificar('BANCO CENTRAL - AVISO DE ATRASO - DDR 2011')
    assert r['categorias'] == ['RETORNO_BACEN']


def test_classificar_retorno_bacen_no_corpo():
    """'AVISO DE ATRASO' no corpo (cliente encaminhando e-mail do BACEN) → RETORNO_BACEN."""
    r = _classificar(
        assunto='Fwd: FW: resposta BACEN',
        corpo='Segue o e-mail: BANCO CENTRAL - AVISO DE ATRASO referente ao arquivo DRM'
    )
    assert r['categorias'] == ['RETORNO_BACEN']


def test_classificar_suporte_sem_sinais():
    """Assunto e corpo sem qualquer sinal de CADOC → SUPORTE."""
    r = _classificar('dúvida sobre o sistema', corpo='Olá, tudo bem? Preciso de ajuda.')
    assert r['categorias'] == ['SUPORTE']
    assert r['incerto'] is False


def test_classificar_interno_boas_vindas():
    """Assunto com 'boas-vindas' → INTERNO."""
    r = _classificar('Boas-vindas à equipe Finaud!')
    assert r['categorias'] == ['INTERNO']


def test_classificar_cadoc_por_anexo():
    """Sem CADOC no assunto/corpo mas nome do anexo tem '4111' → SALDOS_CONTABEIS_DIARIOS_4111."""
    r = _classificar(
        assunto='2026.07.14 - FLUXO DE CAIXA - ZIIN',
        corpo='',
        nomes_anexos=['CADOC_4111_JULHO.xlsx']
    )
    assert r['categorias'] == ['SALDOS_CONTABEIS_DIARIOS_4111']


def test_classificar_drl_typo_dlr():
    """'DLR' (erro de digitação para DRL) no assunto → DRL_2160."""
    r = _classificar('DLR junho')
    assert 'DRL_2160' in r['categorias']


# ── Testes do registro ────────────────────────────────────────────────────────

def test_registro_thread_confirmada_nao_reprocessa(monkeypatch):
    """Thread com status_regra 'confirmada' no registro retorna resultado salvo sem reclassificar."""
    mod = importlib.import_module('classificador_ia')

    registro_mock = {
        'threads': {
            'thread-confirmada-001': {
                'assunto':                'DDR DIA 22/07',
                'categorias':             ['DDR_2011'],
                'status_regra':           'confirmada',
                'regra_usada':            'G-DDR-001',
                'motivo_regra_usada':     'Teste unitario',
                'data_confirmacao_regra': '2026-08-11',
            }
        }
    }
    monkeypatch.setattr(mod, '_REGISTRO_CACHE', registro_mock)

    thread = {
        'thread_id': 'thread-confirmada-001',
        'assunto':   'DDR DIA 22/07',
        'mensagens': [],
    }

    resultado = mod.classificar_thread(thread)
    assert resultado['categorias'] == ['DDR_2011'], 'deve devolver categorias do registro'
    assert resultado['incerto'] is False, 'confirmada nao pode ser incerta'
    assert resultado['gabarito_usado'] == 'G-DDR-001', 'deve preservar regra_usada do registro'


def test_registro_thread_incerta_classifica_deterministicamente(monkeypatch):
    """Thread com status_regra 'incerta' no registro passa pelo classificador determinístico."""
    mod = importlib.import_module('classificador_ia')

    registro_mock = {
        'threads': {
            'thread-incerta-001': {
                'assunto':      'e-mail sem categoria',
                'categorias':   [],
                'status_regra': 'incerta',
                'regra_usada':  None,
            }
        }
    }
    monkeypatch.setattr(mod, '_REGISTRO_CACHE', registro_mock)

    thread = {
        'thread_id': 'thread-incerta-001',
        'assunto':   'DRM JUNHO 2026',
        'mensagens': [],
    }

    resultado = mod.classificar_thread(thread)
    assert resultado['categorias'] == ['DRM_2060'], 'deve classificar deterministicamente pelo assunto'
    assert resultado['incerto'] is False


# ── Testes de OCR / imagens ───────────────────────────────────────────────────

def test_ocr_ignorado_sem_imagens():
    """_extrair_texto_ocr com lista vazia retorna string vazia."""
    mod = importlib.import_module('classificador_ia')
    resultado = mod._extrair_texto_ocr([])
    assert resultado == '', '_extrair_texto_ocr([]) deve retornar string vazia'


def test_buscar_imagens_pasta_inexistente(tmp_path, monkeypatch):
    """buscar_imagens retorna lista vazia quando pasta de anexos não existe."""
    mod = importlib.import_module('classificador_ia')
    monkeypatch.setattr(mod, 'PASTA_ANEXOS', str(tmp_path / 'nao_existe'))
    resultado = mod.buscar_imagens(0)
    assert resultado == [], 'buscar_imagens deve retornar [] quando pasta não existe'


def test_buscar_imagens_filtra_por_indice(tmp_path, monkeypatch):
    """buscar_imagens retorna só as imagens do índice correto."""
    mod = importlib.import_module('classificador_ia')
    monkeypatch.setattr(mod, 'PASTA_ANEXOS', str(tmp_path))

    (tmp_path / '3_image001.png').write_bytes(b'')
    (tmp_path / '3_image002.jpg').write_bytes(b'')
    (tmp_path / '5_image001.png').write_bytes(b'')   # outro índice
    (tmp_path / '3_documento.pdf').write_bytes(b'')  # não é imagem

    resultado = mod.buscar_imagens(3)
    nomes = [os.path.basename(p) for p in resultado]
    assert '3_image001.png' in nomes, 'deve incluir 3_image001.png'
    assert '3_image002.jpg' in nomes, 'deve incluir 3_image002.jpg'
    assert '5_image001.png' not in nomes, 'não deve incluir imagens de outro índice'
    assert '3_documento.pdf' not in nomes, 'não deve incluir PDFs'
