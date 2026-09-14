"""Testes para resumo_semanal — foco em _extrair_empresa com mapeamento de domínio."""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import resumo_semanal as rs


# Substitui o mapeamento real por um fixo para os testes não dependerem do JSON em disco
MAPEAMENTO_TESTE = {
    'cvdtvm.com.br': 'CV DTVM',
    'faircorretora.com.br': 'Fair Corretora',
    'brazabank.com.br': 'Braza Bank',
    'braza.com.br': 'Braza Bank',
}


@pytest.fixture(autouse=True)
def patch_mapeamento(monkeypatch):
    monkeypatch.setattr(rs, '_MAPEAMENTO_EMPRESAS', MAPEAMENTO_TESTE)


# ── Padrão 1: domínio no mapeamento ───────────────────────────────────────────

def test_dominio_mapeado_retorna_empresa():
    resultado = rs._extrair_empresa('CV INVEST | DLO JUL', 'Larissa <larissa@cvdtvm.com.br>')
    assert resultado == 'CV DTVM'


def test_dominio_mapeado_dois_dominios_mesma_empresa():
    r1 = rs._extrair_empresa('assunto', 'Contato <contato@brazabank.com.br>')
    r2 = rs._extrair_empresa('assunto', 'Contato <contato@braza.com.br>')
    assert r1 == 'Braza Bank'
    assert r2 == 'Braza Bank'


def test_dominio_mapeado_ignora_case():
    resultado = rs._extrair_empresa('assunto', 'Pessoa <PESSOA@FAIRCORRETORA.COM.BR>')
    assert resultado == 'Fair Corretora'


# ── Padrão 2: domínio fora do mapeamento ──────────────────────────────────────

def test_dominio_nao_mapeado_retorna_sem_empresa():
    resultado = rs._extrair_empresa('BALANCETE JULHO 2026', 'carlos-adcon <carlos-adcon@uol.com.br>')
    assert resultado == 'Sem empresa identificada'


def test_dominio_nao_mapeado_consultor_externo():
    resultado = rs._extrair_empresa('Remitly CC - 4010/4016', 'HEBERT <fiscal5@mrhenriqueconsult.com.br>')
    assert resultado == 'Sem empresa identificada'


# ── Remetente interno (finaud) — não deve buscar no mapeamento ────────────────

def test_interno_finaud_nao_usa_mapeamento():
    resultado = rs._extrair_empresa('assunto qualquer', 'Andrea <andrea@finaud.com.br>')
    # Remetente interno não deve retornar empresa via domínio
    assert resultado == 'Sem empresa identificada'
