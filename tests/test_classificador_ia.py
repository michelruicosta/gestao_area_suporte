"""
test_classificador_ia.py
Testes para scripts/classificador_ia.py — regras_classificador_threads e integração ao prompt.
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
    'PVCA_6209', 'SUPORTE',
}


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


def test_regras_integradas_no_prompt():
    """O conteúdo do regras_classificador_threads (prioridade + regras + gabaritos) aparece em _SISTEMA."""
    mod = importlib.import_module('classificador_ia')
    sistema = mod._SISTEMA
    assert 'Regras de prioridade' in sistema, \
        "_SISTEMA deve ter a seção 'Regras de prioridade'"
    assert 'PRIORIDADE - 01 - RETORNO_BACEN' in sistema, \
        "_SISTEMA deve conter a prioridade RETORNO_BACEN"
    assert 'EXTRATO COMPROMISSADA' in sistema, \
        "_SISTEMA deve conter a DDR - Regra 01 (EXTRATO COMPROMISSADA)"
    assert 'DDR - Regra 01' in sistema, \
        "_SISTEMA deve conter o ID 'DDR - Regra 01'"
    assert 'Regras confirmadas' in sistema, \
        "_SISTEMA deve ter a seção 'Regras confirmadas'"
    assert 'Gabaritos' in sistema, \
        "_SISTEMA deve ter a seção 'Gabaritos'"


def test_ocr_ignorado_sem_imagens():
    """classificar_thread sem imagens não altera o email_texto enviado à IA."""
    mod = importlib.import_module('classificador_ia')
    # Verifica que _extrair_texto_ocr retorna vazio quando lista vazia
    resultado = mod._extrair_texto_ocr([])
    assert resultado == '', '_extrair_texto_ocr([]) deve retornar string vazia'


def test_buscar_imagens_pasta_inexistente(tmp_path, monkeypatch):
    """buscar_imagens retorna lista vazia quando pasta de anexos não existe."""
    mod = importlib.import_module('classificador_ia')
    monkeypatch.setattr(mod, 'PASTA_ANEXOS', str(tmp_path / 'nao_existe'))
    resultado = mod.buscar_imagens(0)
    assert resultado == [], 'buscar_imagens deve retornar [] quando pasta não existe'


def test_gabarito_usado_no_sistema():
    """O campo gabarito_usado aparece no formato de resposta do _SISTEMA."""
    mod = importlib.import_module('classificador_ia')
    assert 'gabarito_usado' in mod._SISTEMA, \
        '_SISTEMA deve solicitar o campo gabarito_usado no JSON de resposta'


def test_orientacao_no_sistema():
    """O campo orientacao aparece no formato de resposta do _SISTEMA com instrução de uso."""
    mod = importlib.import_module('classificador_ia')
    assert 'orientacao' in mod._SISTEMA, \
        '_SISTEMA deve conter o campo orientacao no formato de resposta'
    assert 'incerto' in mod._SISTEMA and 'orientacao' in mod._SISTEMA, \
        '_SISTEMA deve instruir a preencher orientacao quando incerto ou categorias vazias'


def test_registro_thread_confirmada_nao_chama_gpt(monkeypatch):
    """Thread com status_regra 'confirmada' no registro retorna resultado salvo sem chamar o GPT."""
    import importlib
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

    class _ClienteFalso:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise AssertionError('GPT foi chamado — nao deveria para thread confirmada')

    resultado = mod.classificar_thread(thread, cliente=_ClienteFalso())
    assert resultado['categorias'] == ['DDR_2011'], 'deve devolver categorias do registro'
    assert resultado['incerto'] is False, 'confirmada nao pode ser incerta'
    assert resultado['gabarito_usado'] == 'G-DDR-001', 'deve preservar regra_usada do registro'


def test_registro_thread_incerta_chama_gpt(monkeypatch):
    """Thread com status_regra 'incerta' no registro passa pelo GPT normalmente."""
    import importlib
    mod = importlib.import_module('classificador_ia')

    registro_mock = {
        'threads': {
            'thread-incerta-001': {
                'assunto':      'e-mail sem categoria',
                'categorias':   [],
                'status_regra': 'incerta',
                'regra_usada':  'R6',
            }
        }
    }
    monkeypatch.setattr(mod, '_REGISTRO_CACHE', registro_mock)

    thread = {
        'thread_id': 'thread-incerta-001',
        'assunto':   'e-mail sem categoria',
        'mensagens': [{'remetente': 'teste@finaud.com', 'corpo_texto': 'corpo', 'nomes_anexos': []}],
    }

    gpt_chamado = {'sim': False}
    _resp_json  = '{"categorias":["SUPORTE"],"confianca":"alta","motivo":"teste","incerto":false,"gabarito_usado":null}'

    class _ClienteFalso:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    gpt_chamado['sim'] = True

                    class _Msg:
                        content = _resp_json

                    class _Choice:
                        message = _Msg()

                    class _Resp:
                        choices = [_Choice()]

                    return _Resp()

    resultado = mod.classificar_thread(thread, cliente=_ClienteFalso())
    assert gpt_chamado['sim'], 'GPT deveria ter sido chamado para thread incerta'
    assert resultado['categorias'] == ['SUPORTE']


def test_buscar_imagens_filtra_por_indice(tmp_path, monkeypatch):
    """buscar_imagens retorna só as imagens do índice correto."""
    mod = importlib.import_module('classificador_ia')
    monkeypatch.setattr(mod, 'PASTA_ANEXOS', str(tmp_path))

    # Criar arquivos de teste
    (tmp_path / '3_image001.png').write_bytes(b'')
    (tmp_path / '3_image002.jpg').write_bytes(b'')
    (tmp_path / '5_image001.png').write_bytes(b'')  # outro índice
    (tmp_path / '3_documento.pdf').write_bytes(b'')  # não é imagem

    resultado = mod.buscar_imagens(3)
    nomes = [os.path.basename(p) for p in resultado]
    assert '3_image001.png' in nomes, 'deve incluir 3_image001.png'
    assert '3_image002.jpg' in nomes, 'deve incluir 3_image002.jpg'
    assert '5_image001.png' not in nomes, 'não deve incluir imagens de outro índice'
    assert '3_documento.pdf' not in nomes, 'não deve incluir PDFs'
