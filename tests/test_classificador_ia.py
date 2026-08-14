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


# ── Camada 1: assunto detecta cada CADOC ─────────────────────────────────────

@pytest.mark.parametrize('assunto,esperado', [
    ('DDR - 22/07/2026',                  'DDR_2011'),
    ('Doc. 2011-LIM',                     'DDR_2011'),
    ('EXTRATO COMPROMISSADA - TRUSTEE',   'DDR_2011'),
    ('Compromissadas JUNHO',              'DDR_2011'),
    ('PCAM - JULHO',                      'DDR_2011'),
    ('TVM - 30/06',                       'DDR_2011'),
    ('VMTM - erro de cálculo',            'DDR_2011'),
    ('DLO JUNHO 2026',                    'DLO_2061'),
    ('2061 - envio mensal',               'DLO_2061'),
    ('LEC - CÁLCULO JUNHO',               'DLO_2061'),
    ('COS4016 DE JUNHO',                  'DLO_2061'),
    ('DLI MAIO 2026',                     'DLI_2062'),
    ('2062 - envio',                      'DLI_2062'),
    ('DRM JUNHO',                         'DRM_2060'),
    ('ARQUIVO DRM - AZUMI',               'DRM_2060'),
    ('2060 - envio mensal',               'DRM_2060'),
    ('DRL 2026',                          'DRL_2160'),
    ('2160 - envio',                      'DRL_2160'),
    ('CADOC 4111 JULHO',                  'SALDOS_CONTABEIS_DIARIOS_4111'),
    ('Risk S5 JUNHO',                     'S5'),
    ('AVISO DE ATRASO - DRM 2060',        'RETORNO_BACEN'),
    ('INDICIO - DDR 2011',                'RETORNO_BACEN'),
    # Correção 01 — 12/08/2026: cedilha (Ç) em POSIÇÃO não era detectada
    ('Posição de Câmbio CAM0050 BACEN',      'DDR_2011'),
    ('Posição de Câmbio - 28/07/26',         'DDR_2011'),
    ('TRINUS - ENVIAR POSIÇÃO DDR 2011',     'DDR_2011'),
    # Correção 02 — 12/08/2026: PUs (plural) virava PUS maiúsculo sem match
    ('PUs dos títulos públicos 30/06/2026',  'DDR_2011'),
    # Correção 03 — 12/08/2026: DDRs (plural) virava DDRS sem match
    ('COLUNA: DDRs - 16/07/2026 e 17/07/2026',  'DDR_2011'),
    # Correção 04 — 12/08/2026: REMITLY é cliente que sempre envia DDR
    ('REMITLY : Movimento 2026.08.04',                              'DDR_2011'),
    # Correção 05 — 12/08/2026: PI EXPOSURE é relatório diário de posição (DDR)
    ('PI Exposure MiraeAsset Securities in Brazil_HK - 20260804_AUDIT', 'DDR_2011'),
])
def test_camada1_assunto_detecta_cadoc(assunto, esperado):
    """Camada 1: assunto com sinal inequívoco → categoria correta."""
    r = _classificar(assunto)
    assert esperado in r['categorias'], (
        f"Assunto '{assunto}': esperado '{esperado}', obtido {r['categorias']}"
    )


# ── Camada 2: corpo detecta quando assunto não tem sinal ─────────────────────

@pytest.mark.parametrize('corpo,esperado', [
    ('Preciso de ajuda com o DDR do mês',          'DDR_2011'),
    ('Arquivo 2011 com problema de envio',          'DDR_2011'),
    ('Envio do DLO - junho 2026',                   'DLO_2061'),
    ('Arquivo 2061 está pendente',                  'DLO_2061'),
    ('Cálculo do LEC está errado',                  'DLO_2061'),
    ('Planilha DLI não foi aceita',                 'DLI_2062'),
    ('Número 2062 — envio realizado',               'DLI_2062'),
    ('Arquivo DRM com inconsistência',              'DRM_2060'),
    ('Envio do 2060 do mês de junho',               'DRM_2060'),
    ('DRL - envio realizado com sucesso',            'DRL_2160'),
    ('Número 2160 — confirmado',                    'DRL_2160'),
    ('Saldos contábeis 4111 enviados',              'SALDOS_CONTABEIS_DIARIOS_4111'),
    # S5 via '\bS5\b' não dispara no corpo — ver Correção 24 e test_correcao24_s5_no_corpo_nao_dispara
    ('Arquivo DRSAC com rejeição',                  'DRSAC_2030'),
    ('Entrega do CADOC 2030 — confirmada',          'DRSAC_2030'),
    ('Arquivo PVCA rejeitado pelo sistema',         'PVCA_6209'),
    ('Entrega do 6209 do segundo trimestre',        'PVCA_6209'),
    ('Aviso de atraso recebido do BACEN',           'RETORNO_BACEN'),
])
def test_camada2_corpo_detecta_cadoc(corpo, esperado):
    """Camada 2: corpo com sinal de CADOC quando assunto não tem → categoria correta."""
    r = _classificar('dúvida', corpo=corpo)
    assert esperado in r['categorias'], (
        f"Corpo '{corpo[:50]}': esperado '{esperado}', obtido {r['categorias']}"
    )


# ── Camada 3: nome do anexo detecta quando assunto/corpo não têm sinal ────────

@pytest.mark.parametrize('nome_anexo,esperado', [
    ('COS4010_JUNHO.xml',                   'DLO_2061'),
    ('COS4016_JULHO.xml',                   'DLO_2061'),
    ('LEC_2026_06.xlsx',                    'DLO_2061'),
    ('EXTRATO_COMPROMISSADA_JUNHO.xml',     'DDR_2011'),
    ('DDR_DIARIO_22072026.xml',             'DDR_2011'),
    ('SALDOS_CONTABEIS_4111_JUN.xlsx',      'SALDOS_CONTABEIS_DIARIOS_4111'),
    ('DRM_2060_JUNHO.xml',                  'DRM_2060'),
    ('DRL_2160_JULHO.xml',                  'DRL_2160'),
    ('DLI_2062_JUN.xml',                    'DLI_2062'),
])
def test_camada3_anexo_detecta_cadoc(nome_anexo, esperado):
    """Camada 3: nome de anexo com sinal de CADOC quando assunto/corpo sem sinal → categoria correta."""
    r = _classificar('envio de arquivo', corpo='Segue em anexo.', nomes_anexos=[nome_anexo])
    assert esperado in r['categorias'], (
        f"Anexo '{nome_anexo}': esperado '{esperado}', obtido {r['categorias']}"
    )


# ── Camada 4: padrões de e-mail INTERNO ──────────────────────────────────────

@pytest.mark.parametrize('assunto', [
    'Boas-vindas à equipe Finaud',
    'Bem-vindo ao time!',
    'Comunicado de Saída — João Silva',
    'Comunicado de saida da colaboradora',
    'Seu código de verificação da conta Risk Driver',
    'Bruno convidou você para a reunião no Microsoft Teams',
    'Visita Finaud — agendamento',
])
def test_camada4_interno_por_assunto(assunto):
    """Camada 4: assunto com padrão de e-mail interno → INTERNO (não SUPORTE)."""
    r = _classificar(assunto)
    assert r['categorias'] == ['INTERNO'], (
        f"Assunto '{assunto}': esperado ['INTERNO'], obtido {r['categorias']}"
    )


# ── Correção 07: complemento DLO/DLI entre assunto e corpo/anexo ─────────────

def test_correcao07_assunto_dlo_corpo_dli():
    """Correção 07 — assunto detecta DLO; corpo tem sinal explícito de DLI → ambas."""
    r = _classificar(
        assunto='DLO JUNHO 2026',
        corpo='Segue o DLI (2062) referente ao mesmo período.',
    )
    assert 'DLO_2061' in r['categorias'], 'DLO deve estar nas categorias'
    assert 'DLI_2062' in r['categorias'], 'DLI deve ser detectado no corpo'


def test_correcao07_assunto_dli_corpo_dlo():
    """Correção 07 — assunto detecta DLI; corpo tem sinal explícito de DLO → ambas."""
    r = _classificar(
        assunto='DLI MAIO 2026',
        corpo='Planilha LEC e COS4016 do mês de maio também em anexo.',
    )
    assert 'DLI_2062' in r['categorias'], 'DLI deve estar nas categorias'
    assert 'DLO_2061' in r['categorias'], 'DLO deve ser detectado no corpo (LEC/COS4016)'


def test_correcao07_assunto_dlo_anexo_dli():
    """Correção 07 — assunto detecta DLO; nome do anexo tem sinal de DLI → ambas."""
    r = _classificar(
        assunto='DLO JULHO 2026',
        corpo='',
        nomes_anexos=['DLI_2062_JUL.xml'],
    )
    assert 'DLO_2061' in r['categorias'], 'DLO deve estar nas categorias'
    assert 'DLI_2062' in r['categorias'], 'DLI deve ser detectado no nome do anexo'


# ── Correção 08: REJEITADO no assunto → RETORNO_BACEN ────────────────────────

@pytest.mark.parametrize('assunto', [
    # Correção 08 — 12/08/2026: arquivo rejeitado = RETORNO_BACEN (não o CADOC do arquivo)
    'UNICRED - DRM (2060) 30 06 2026 - REJEITADO',
    'RES: GREEN DTVM - DRM 2060 - ARQUIVO REJEITADO',
    'DRM 30 06 2026 - ENTREGUE E REJEITADO',
    'Arquivo DLO maio rejeitado',
    '4111 - REJEITADO',
])
def test_correcao10_rd_remessa_diaria_ddr(assunto):
    """Correção 10 — 'RD' no assunto/anexo (Remessa Diária do DDR) → DDR_2011."""


# ── Correção 10: RD (Remessa Diária) → DDR_2011 ──────────────────────────────

@pytest.mark.parametrize('assunto,corpo,anexos', [
    # Correção 10 — 13/08/2026: RD = Remessa Diária, arquivo de importação do DDR
    ('RD MES 07-2026',                  '', []),
    ('RD MES 07-2026 - DESCONSIDERAR',  '', []),
    ('envio mensal',  '', ['RD_MOEDA_31-07-2026.csv']),   # via nome de anexo
])
def test_correcao10_rd_remessa_diaria_ddr(assunto, corpo, anexos):
    """Correção 10 — 'RD' no assunto/anexo (Remessa Diária do DDR) → DDR_2011."""
    r = _classificar(assunto, corpo=corpo, nomes_anexos=anexos)
    assert 'DDR_2011' in r['categorias'], (
        f"Assunto '{assunto}' / anexos {anexos}: esperado DDR_2011, obtido {r['categorias']}"
    )


# ── Correção 08: REJEITADO no assunto → RETORNO_BACEN ────────────────────────

@pytest.mark.parametrize('assunto', [
    # Correção 08 — 12/08/2026: arquivo rejeitado = RETORNO_BACEN (não o CADOC do arquivo)
    'UNICRED - DRM (2060) 30 06 2026 - REJEITADO',
    'RES: GREEN DTVM - DRM 2060 - ARQUIVO REJEITADO',
    'DRM 30 06 2026 - ENTREGUE E REJEITADO',
    'Arquivo DLO maio rejeitado',
    '4111 - REJEITADO',
])
def test_correcao08_rejeitado_assunto_retorno_bacen(assunto):
    """Correção 08 — 'REJEITADO' no assunto → RETORNO_BACEN (arquivo recusado pelo BACEN)."""
    r = _classificar(assunto)
    assert r['categorias'] == ['RETORNO_BACEN'], (
        f"Assunto '{assunto}': esperado ['RETORNO_BACEN'], obtido {r['categorias']}"
    )


# ── Correção 12: CADOC genérico (sem número) → SALDOS_CONTABEIS_DIARIOS_4111 ─

@pytest.mark.parametrize('assunto,corpo,esperado', [
    # Correção 12 — 13/08/2026: "CADOC" sem número = coloquial para SALDOS_4111
    ('DDR e CADOC',               '', ['DDR_2011', 'SALDOS_CONTABEIS_DIARIOS_4111']),
    ('CADOC e DDR - 14/07 a 17/07', '', ['DDR_2011', 'SALDOS_CONTABEIS_DIARIOS_4111']),
    # CADOC 4111 explícito não deve disparar CADOC genérico (mas 4111 já detecta SALDOS)
    ('CADOC 4111',                '', ['SALDOS_CONTABEIS_DIARIOS_4111']),
    # CADOC no corpo (sem assunto) → SALDOS_4111
    ('',                          'Segue abaixo DDR. Segue abaixo CADOC.', ['DDR_2011', 'SALDOS_CONTABEIS_DIARIOS_4111']),
])
def test_correcao12_cadoc_generico_saldos(assunto, corpo, esperado):
    """Correção 12 — CADOC sem número no texto → inclui SALDOS_CONTABEIS_DIARIOS_4111."""
    r = _classificar(assunto, corpo=corpo)
    assert sorted(r['categorias']) == sorted(esperado), (
        f"Assunto '{assunto}' / corpo '{corpo[:40]}': esperado {esperado}, obtido {r['categorias']}"
    )


# ── Correção 13: LEC não dispara DLO em "DRL-LEC" (componente do relatório DRL) ─

def test_correcao13_drl_lec_nao_dispara_dlo():
    """Correção 13 — 'DRL-LEC' no assunto: LEC é aba da planilha DRL, não sinal de DLO."""
    r = _classificar('Planilha DRL-LEC Junho/2026')
    assert 'DRL_2160' in r['categorias'], 'DRL deve ser detectado'
    assert 'DLO_2061' not in r['categorias'], (
        f"DLO não deve disparar em DRL-LEC; obtido {r['categorias']}"
    )


def test_correcao13_lec_sozinho_ainda_dispara_dlo():
    """Correção 13 — 'LEC' sem prefixo DRL- ainda dispara DLO_2061 normalmente."""
    r = _classificar('LEC JUNHO 2026')
    assert 'DLO_2061' in r['categorias'], (
        f"LEC sozinho deve disparar DLO; obtido {r['categorias']}"
    )


# ── Correção 14: TVM em "/TVM" (contexto DLO/TPF) não dispara DDR_2011 ────────

def test_correcao14_tpf_tvm_nao_dispara_ddr():
    """Correção 14 — 'TPF/TVM' em contexto DLO: TVM após barra não é sinal DDR."""
    r = _classificar('Re: DLO - TPF/TVM - maio/26')
    assert 'DLO_2061' in r['categorias'], 'DLO deve ser detectado'
    assert 'DDR_2011' not in r['categorias'], (
        f"DDR não deve disparar em TPF/TVM; obtido {r['categorias']}"
    )


def test_correcao14_tvm_sozinho_ainda_dispara_ddr():
    """Correção 14 — 'TVM' sozinho (sem barra) ainda dispara DDR_2011 normalmente."""
    r = _classificar('Relatórios de TVM e Dep a Vista - 04/08/2026')
    assert 'DDR_2011' in r['categorias'], (
        f"TVM sozinho deve disparar DDR; obtido {r['categorias']}"
    )


# ── Correção 15: planilha ZIIN "Saldos 4111 e Posição LFT" → DDR + SALDOS ────

def test_correcao15_ziin_posicao_lft_dispara_ddr():
    """Correção 15 — arquivo 'Saldos 4111 e Posição LFT.ods' contém DDR + SALDOS."""
    r = _classificar(
        assunto='2026.07.14 - FLUXO DE CAIXA - ZIIN',
        nomes_anexos=['image001.png', 'Saldos 4111 e Posição LFT.ods'],
    )
    assert 'DDR_2011' in r['categorias'], f"DDR esperado; obtido {r['categorias']}"
    assert 'SALDOS_CONTABEIS_DIARIOS_4111' in r['categorias'], f"SALDOS esperado; obtido {r['categorias']}"


def test_correcao15_posicao_lft_no_corpo():
    """Correção 15 — 'Posição LFT' mencionado no corpo também dispara DDR."""
    r = _classificar(assunto='FLUXO DE CAIXA', corpo='Segue planilha Saldos 4111 e Posição LFT do mês.')
    assert 'DDR_2011' in r['categorias'], f"DDR esperado; obtido {r['categorias']}"
    assert 'SALDOS_CONTABEIS_DIARIOS_4111' in r['categorias'], f"SALDOS esperado; obtido {r['categorias']}"


# ── Correção 16: VARIAÇÃO RELEVANTE e REITERAÇÃO → RETORNO_BACEN ─────────────

def test_correcao16_variacao_relevante_dispara_retorno():
    """Correção 16 — 'VARIAÇÃO RELEVANTE' no assunto é comunicado BACEN → RETORNO_BACEN."""
    r = _classificar('Fwd: 1a REITERACAO - BANCO CENTRAL - COMUNICACAO DE VARIACAO RELEVANTE NO DDR - 2011')
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao16_variacao_relevante_com_acento():
    """Correção 16 — variante com acento 'VARIAÇÃO RELEVANTE' também dispara."""
    r = _classificar('BANCO CENTRAL - COMUNICAÇÃO DE VARIAÇÃO RELEVANTE NO DDR - 2011')
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao16_reiteracao_sozinha_dispara_retorno():
    """Correção 16 — 'REITERAÇÃO' de comunicado BACEN no assunto → RETORNO_BACEN."""
    r = _classificar('1a REITERAÇÃO - BANCO CENTRAL - COMUNICACAO DE INCONSISTENCIA NO DRM - 2060')
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao16_variacao_relevante_nao_dispara_sem_contexto():
    """Correção 16 — 'variação relevante' sozinha sem contexto BACEN não deve aparecer no assunto de CADOC normal."""
    r = _classificar('DRM 06/2026 - VARIAÇÕES MENSAIS RELEVANTES DE POSIÇÃO')
    assert 'RETORNO_BACEN' not in r['categorias'], f"RETORNO nao esperado; obtido {r['categorias']}"


def test_correcao18_qualidade_bacen_assunto_dispara_retorno():
    """Correção 18 — 'QUALIDADE BACEN' no assunto antes do CADOC → RETORNO_BACEN."""
    r = _classificar('RE: DLO ABRIL E MAIO - QUALIDADE BACEN')
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao18_qualidade_bacen_nao_confunde_sem_bacen():
    """Correção 18 — 'QUALIDADE' sozinha sem 'BACEN' não ativa RETORNO."""
    r = _classificar('DLO ABRIL - QUALIDADE DOS DADOS')
    assert 'RETORNO_BACEN' not in r['categorias'], f"RETORNO nao esperado; obtido {r['categorias']}"


def test_correcao19_sinal_retorno_no_corpo_principal_com_cadoc_no_assunto():
    """Correção 19 — CADOC no assunto + sinal de RETORNO no corpo principal → RETORNO_BACEN."""
    corpo = (
        "Andrea, tudo bem?\n"
        "Recebemos um e-mail do Bacen de 'Comunicação de inconsistência no DRM - 2060'.\n"
        "Pode nos ajudar?\n"
    )
    r = _classificar('DRM JUNHO', corpo)
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao19_retorno_sta_no_corpo_principal_com_cadoc_no_assunto():
    """Correção 19 — CADOC no assunto + 'RETORNO DO STA' no corpo principal → RETORNO_BACEN."""
    corpo = (
        "O protocolo de retorno do STA apresentou rejeição com as seguintes mensagens:\n"
        "- Instituição não existe no Unicad\n"
    )
    r = _classificar('DRM 2060 - JUNHO', corpo)
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao19_sinal_retorno_apenas_citado_nao_dispara():
    """Correção 19 — sinal de RETORNO só no texto citado (após 'De:') NÃO ativa RETORNO."""
    corpo = (
        "Andrea,\n"
        "Pode ignorar meu e-mail anterior.\n\n"
        "De: Andrea Inacio\n"
        "Assunto: Re: DRM\n"
        "> Comunicação de inconsistência no DRM - 2060\n"
    )
    r = _classificar('DRM JUNHO', corpo)
    assert 'RETORNO_BACEN' not in r['categorias'], f"RETORNO nao esperado; obtido {r['categorias']}"


def test_correcao20_ajuste_bacen_no_assunto_dispara_retorno():
    """Correção 20 — 'AJUSTE BACEN' no assunto → RETORNO_BACEN (cliente com crítica do BACEN)."""
    r = _classificar('DRM JUNHO - AJUSTE BACEN')
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao20_criticas_ao_no_assunto_dispara_retorno():
    """Correção 20 — 'CRITICAS AO' no assunto → RETORNO_BACEN (BC criticando o CADOC)."""
    r = _classificar('BC - Criticas ao DRM 2026 ref. Maio/2026')
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao20_ajuste_sem_bacen_nao_dispara():
    """Correção 20 — 'AJUSTE' sozinho sem 'BACEN' não ativa RETORNO."""
    r = _classificar('DRM JUNHO - AJUSTE DE LAYOUT')
    assert 'RETORNO_BACEN' not in r['categorias'], f"RETORNO nao esperado; obtido {r['categorias']}"


# ── Correção 21 — Sinais 2, 3, 5, 6b, 7 do Grupo 2 (corpo/anexos dentro de Camada 1b) ──────────


def test_correcao21_sinal5_indicio_qualidade_prazo_dispara_retorno():
    """Correção 21 — Sinal 5: 'indício de qualidade' + 'prazo' no corpo principal → RETORNO_BACEN."""
    corpo = "Segue a crítica: indício de qualidade apurado pelo BACEN. Prazo para correção: 05/09/2026."
    r = _classificar('DLI 2062 MAIO CV', corpo)
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao21_sinal5_indicio_sem_prazo_nao_dispara():
    """Correção 21 — Sinal 5: 'indício de qualidade' sem 'prazo' NÃO ativa RETORNO."""
    corpo = "Verificamos indício de qualidade nos dados informados, sem pendência formal."
    r = _classificar('DLI 2062 MAIO', corpo)
    assert 'RETORNO_BACEN' not in r['categorias'], f"RETORNO nao esperado; obtido {r['categorias']}"


def test_correcao21_sinal7_crd_pendencia_dispara_retorno():
    """Correção 21 — Sinal 7: 'CRD' + 'pendência' no corpo principal → RETORNO_BACEN."""
    corpo = "Acessei o CRD e verifiquei que há pendência no cadastro da posição de junho/2026."
    r = _classificar('SMM 2060 - 06/2026', corpo)
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao21_sinal7_crd_sem_pendencia_nao_dispara():
    """Correção 21 — Sinal 7: 'CRD' sozinho sem 'pendência' NÃO ativa RETORNO."""
    corpo = "Acesse o CRD para verificar o status do arquivo enviado ontem."
    r = _classificar('DRM 06/2026 ref', corpo)
    assert 'RETORNO_BACEN' not in r['categorias'], f"RETORNO nao esperado; obtido {r['categorias']}"


def test_correcao21_sinal2_determinamos_a_corr_dispara_retorno():
    """Correção 21 — Sinal 2: 'determinamos a correção' no corpo → BACEN ordenando ajuste."""
    corpo = "Prezado, determinamos a correção dos dados informados conforme art. 5º da Resolução 4.966."
    r = _classificar('CADOC 4111 - 30/06/2026', corpo)
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao21_sinal3_possivel_inconsistencia_no_anexo_dispara():
    """Correção 21 — Sinal 3: 'possivel inconsistencia' no nome do anexo → RETORNO_BACEN."""
    r = _classificar('DRM 06/2026 urgente', '', ['comunicacao_possivel_inconsistencia_drm.eml'])
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


def test_correcao21_sinal6b_vcrd_no_corpo_dispara_retorno():
    """Correção 21 — Sinal 6b: 'VCRD' no corpo completo (inclui citações) → RETORNO_BACEN."""
    corpo = (
        "Andrea, pode verificar o andamento?\n\n"
        "De: Banco Central\n"
        "> Identificamos critica VCRD no arquivo DLO enviado em 30/06/2026.\n"
    )
    r = _classificar('DLO DRM 2060 - 06/2026', corpo)
    assert r['categorias'] == ['RETORNO_BACEN'], f"RETORNO esperado; obtido {r['categorias']}"


# ── Correção 22 — 'REUNIÃO' no assunto → SUPORTE ─────────────────────────────


def test_correcao22_reuniao_no_assunto_retorna_suporte():
    """Correção 22 — 'REUNIÃO' no assunto → SUPORTE (não entrega de CADOC)."""
    r = _classificar('Reunião - Demandas BACEN - DLO Junho (Antecipações)')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao22_reuniao_sem_cadoc_retorna_suporte():
    """Correção 22 — 'Reunião' no assunto sem CADOC também → SUPORTE."""
    r = _classificar('Reunião sobre processos internos')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


# ── Correção 23 — 'ERRO' no início + só DDR no assunto → SUPORTE ─────────────


def test_correcao23_erro_ddr_no_assunto_retorna_suporte():
    """Correção 23 — 'ERRO' no início + só DDR no assunto → pedido de suporte, não entrega."""
    r = _classificar('ERRO -- Taxa Referencial DDR')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao23_erro_vmtm_retorna_suporte():
    """Correção 23 — 'Erro ao calcular o VMTM' dispara DDR mas é pedido de suporte → SUPORTE."""
    r = _classificar('Erro ao calcular o VMTM do dia 30/07/2026')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao23_erro_com_dlo_nao_afeta():
    """Correção 23 — 'ERRO NO DLO' tem DLO no assunto (não só DDR) → mantém DLO_2061."""
    r = _classificar('ERRO NO DLO')
    assert 'DLO_2061' in r['categorias'], f"DLO_2061 esperado; obtido {r['categorias']}"


def test_correcao23_erro_drm_nao_afeta():
    """Correção 23 — assunto com DRM não é afetado pela regra (só DDR)."""
    r = _classificar('Erro - 2060 DRM')
    assert 'DRM_2060' in r['categorias'], f"DRM_2060 esperado; obtido {r['categorias']}"


# ── Correção 24 — '\bS5\b' no corpo não dispara S5 (só no assunto) ───────────


def test_correcao24_s5_no_corpo_nao_dispara():
    """Correção 24 — 'S5' no corpo indica tamanho de instituição, não entrega CADOC → SUPORTE."""
    r = _classificar('Freex Câmbio - Login Riskdriver',
                     'O login é exclusivo para o Risk Driver S5, segue o link abaixo:')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao24_s5_no_assunto_detecta():
    """Correção 24 — 'S5' no assunto ainda detecta S5 normalmente."""
    r = _classificar('Aceita: Risk S5')
    assert 'S5' in r['categorias'], f"S5 esperado; obtido {r['categorias']}"


def test_correcao24_resultado_quantitativo_no_assunto_detecta():
    """Correção 24 — 'Resultado Quantitativo' no assunto ainda detecta S5."""
    r = _classificar('Re: Arquivo COS. Segue o Resultado Quantitativo 06/2026. EXECUTIVE')
    assert 'S5' in r['categorias'], f"S5 esperado; obtido {r['categorias']}"


# ── Correção 25 — FORCAPITAL restrito ao assunto ─────────────────────────────


def test_correcao25_forcapital_email_no_corpo_nao_dispara():
    """Correção 25 — 'forcapital@...' no corpo (endereço de e-mail) não dispara FORCAPITAL → SUPORTE."""
    r = _classificar('RES: Risk Driver - NOVA SENHA - Acesso ao Sistema',
                     'To: gilvanice.rocha@brokerbrasilcambio.com.br, forcapital@finaud.com.br')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao25_projecao_capital_no_corpo_nao_dispara():
    """Correção 25 — 'projeção de capital' no corpo (contexto de suporte) não dispara FORCAPITAL → SUPORTE."""
    r = _classificar('Re: TESTES DE STRESS E PILAR 3',
                     'Realizei a projeção de capital com base nas instruções que você me enviou.')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao25_projecao_capital_no_assunto_detecta():
    """Correção 25 — 'Projeção de Capital' no assunto ainda detecta FORCAPITAL normalmente."""
    r = _classificar('Re: Projeção de Capital para Cenário Realista de DEZ25 a DEZ28')
    assert 'FORCAPITAL' in r['categorias'], f"FORCAPITAL esperado; obtido {r['categorias']}"


# ── Correção 26 — 'Instrução Normativa' sem CADOC no assunto → SUPORTE ────────


def test_correcao26_instrucao_normativa_sem_cadoc_retorna_suporte():
    """Correção 26 — circular regulatória encaminhada sem CADOC no assunto → SUPORTE."""
    r = _classificar('ENC: INSTRUÇÃO NORMATIVA BCB Nº 749',
                     'O sistema já está parametrizado para as alterações do DLI 2062?')
    assert r['categorias'] == ['SUPORTE'], f"SUPORTE esperado; obtido {r['categorias']}"


def test_correcao26_instrucao_normativa_com_cadoc_no_assunto_mantem_cadoc():
    """Correção 26 — 'Instrução Normativa' + código CADOC no assunto → mantém detecção normal."""
    r = _classificar('RES: Instrução Normativa BCB nº 721/26 - DLI 2062 - UNICRED')
    assert 'DLI_2062' in r['categorias'], f"DLI_2062 esperado; obtido {r['categorias']}"


# ── Correção 27 — CADASTRO + RISKDRIVER no assunto → DDR_2011 ────────────────


def test_correcao27_cadastro_riskdriver_retorna_ddr():
    """Correção 27 — cadastro de fundos no Risk Driver = entrega DDR → DDR_2011."""
    r = _classificar('CADASTRO DOS FUNDOS NO SISTEMA - RISKDRIVER')
    assert 'DDR_2011' in r['categorias'], f"DDR_2011 esperado; obtido {r['categorias']}"


def test_correcao27_riskdriver_sem_cadastro_nao_dispara_ddr():
    """Correção 27 — Risk Driver sozinho (sem cadastro) não vira DDR automaticamente."""
    r = _classificar('Re: Acesso ao Risk Driver - senha')
    assert 'DDR_2011' not in r['categorias'], f"DDR_2011 indevido; obtido {r['categorias']}"


# ── Correção 28 — 'POSICAO DD.MM.AAAA' no assunto → DDR_2011 ─────────────────


def test_correcao28_posicao_com_data_retorna_ddr():
    """Correção 28 — arquivo de posição com data no assunto = entrega DDR → DDR_2011."""
    r = _classificar('ENC: POSICAO 10.07.2026')
    assert 'DDR_2011' in r['categorias'], f"DDR_2011 esperado; obtido {r['categorias']}"


def test_correcao28_posicao_sem_data_nao_dispara_ddr():
    """Correção 28 — 'posição' genérico (sem data) não dispara DDR."""
    r = _classificar('RES: SSG - ENVIAR POSIÇÃO - 4111')
    assert 'DDR_2011' not in r['categorias'], f"DDR_2011 indevido; obtido {r['categorias']}"


# ── Correção 29 — 'EXTRATOS' no assunto → DDR_2011 ───────────────────────────


def test_correcao29_extratos_retorna_ddr():
    """Correção 29 — extratos de conta corrente/câmbio/aplicações no assunto = insumo DDR → DDR_2011."""
    r = _classificar('EXTRATOS - JUNHO-2026 - ATUAL')
    assert 'DDR_2011' in r['categorias'], f"DDR_2011 esperado; obtido {r['categorias']}"


# ── Correção 30 — código COS DLO solo no assunto → DLO_2061 ──────────────────


def test_correcao30_numero_4010_no_assunto_retorna_dlo():
    """Correção 30 — '4010' solo no assunto (ex.: '4010 Trinus') → DLO_2061."""
    r = _classificar('4010 Trinus')
    assert 'DLO_2061' in r['categorias'], f"DLO_2061 esperado; obtido {r['categorias']}"


def test_correcao30_cosifs_4010_no_assunto_retorna_dlo():
    """Correção 30 — 'COSIF''S 4010' no assunto também detecta DLO."""
    r = _classificar("RES: COSIF'S 4010 JUN/2026 - BANVOX DTVM. Seguem as remessas.")
    assert 'DLO_2061' in r['categorias'], f"DLO_2061 esperado; obtido {r['categorias']}"


# ── Correção 31 — 'COS 4010' (com espaço) nos nomes de arquivo → DLO_2061 ────


def test_correcao31_cos_espaco_4010_no_anexo_retorna_dlo():
    """Correção 31 — 'COS 4010' com espaço no nome do arquivo → DLO_2061."""
    r = _classificar('Arquivo COS',
                     'Segue arquivos COS junho/2026',
                     ['EXECUTIVE CORRETORA - COS 4010 06_2026.zip'])
    assert 'DLO_2061' in r['categorias'], f"DLO_2061 esperado; obtido {r['categorias']}"


def test_correcao31_cos_espaco_no_corpo_nao_dispara_dlo():
    """Correção 31 — 'COS 4010' com espaço no corpo não dispara DLO (evita balancete como SUPORTE)."""
    r = _classificar('ENC: BALANCETE TRADERS COMP 06-2026',
                     'Segue CADOC 4111. Quanto ao balancete COS 4010, verificar com contabilidade.',
                     ['62280490_4111_20260630.zip'])
    assert 'DLO_2061' not in r['categorias'], f"DLO_2061 indevido; obtido {r['categorias']}"
