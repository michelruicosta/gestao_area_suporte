"""
QA – Script 13 (agente de correlação): correlação e-mail ↔ FOG.

Valida:
  1. _score_correlacao_fog detecta par com palavras-chave comuns no título (score >= 20).
  2. Par sem nenhuma semelhança retorna score < 20 (não correlacionado).
  3. calcular_correlacoes_email_fog gera dict com threadId → lista de FOGs.
  4. Registro FOG tem campos obrigatórios: fogId, tipo="FOG", assunto, score, motivos.

Alinhado à seção "Script 13" do REGISTRO_CORRECOES.md (2026-02-27).
"""
from __future__ import annotations

import importlib.util
import os
from tests.conftest import RAIZ


def _carregar_script13():
    path = os.path.join(RAIZ, "scripts", "13_correlacionar_threads.py")
    spec = importlib.util.spec_from_file_location("s13", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_score_fog_palavras_titulo_comuns():
    """Threads com palavras-chave iguais no título devem ter score >= 20."""
    mod = _carregar_script13()

    thread = {
        "threadId": "<test@mail>",
        "assunto": "CNPJ Alfanumérico - Impactos Finaud",
        "cliente": "Unicred",
        "cadoc": "OUTROS",
        "resumo_ia": "A Finaud está em fase de especificação das alterações para CNPJ alfanumérico.",
        "resolucao": "Aguardando documentação.",
        "tipo": "ARQUIVADA",
    }

    fog_reg = {
        "fogId": "9999",
        "threadId": "FOG:9999",
        "assunto": "CNPJ Alfanumérico será atribuído, a partir de Julho de 2026",
        "cliente": "",
        "cadoc": "",
        "resumo_ia": "Adequações no sistema para suportar CNPJ alfanumérico.",
        "tipo": "FOG",
        "status": "Aberto",
        "projeto": "RISK DRIVER",
        "data_conclusao": "2026-02-27",
    }

    score, motivos = mod._score_correlacao_fog(thread, fog_reg)
    assert score >= 20, f"Score esperado >= 20, obtido {score}. Motivos: {motivos}"
    assert any("titulo_comum" in m for m in motivos), f"Esperado motivo titulo_comum. Motivos: {motivos}"
    assert any("cnpj" in m or "alfanumerico" in m for m in motivos), f"Esperado cnpj ou alfanumerico nos motivos. Motivos: {motivos}"


def test_score_fog_sem_semelhanca():
    """Threads sem semelhança com o FOG devem retornar score < 20."""
    mod = _carregar_script13()

    thread = {
        "threadId": "<outro@mail>",
        "assunto": "Balancete DLO dezembro 2025",
        "cliente": "Cliente X",
        "cadoc": "DLO_2061",
        "resumo_ia": "Entrega do balancete DLO.",
        "resolucao": "Enviado.",
        "tipo": "ARQUIVADA",
    }

    fog_reg = {
        "fogId": "8888",
        "threadId": "FOG:8888",
        "assunto": "Ajuste na rotina de câmbio do sistema",
        "cliente": "",
        "cadoc": "DDR_2011",
        "resumo_ia": "Verificação de taxa de câmbio.",
        "tipo": "FOG",
        "status": "Fechado",
        "projeto": "RISK DRIVER",
        "data_conclusao": "2025-10-01",
    }

    score, motivos = mod._score_correlacao_fog(thread, fog_reg)
    assert score < 20, f"Score esperado < 20 (sem semelhança), obtido {score}. Motivos: {motivos}"


def test_calcular_correlacoes_email_fog_retorna_dict():
    """calcular_correlacoes_email_fog retorna dict threadId → lista de FOGs."""
    mod = _carregar_script13()

    threads = [{
        "threadId": "<cnpj@mail>",
        "assunto": "CNPJ Alfanumérico - Impactos Finaud",
        "cliente": "Unicred",
        "cadoc": "OUTROS",
        "resumo_ia": "Adequações necessárias para CNPJ alfanumérico.",
        "resolucao": "",
        "tipo": "ARQUIVADA",
    }]

    fogs = [{
        "fogId": "9999",
        "threadId": "FOG:9999",
        "assunto": "CNPJ Alfanumérico será atribuído, a partir de Julho de 2026",
        "cliente": "",
        "cadoc": "",
        "resumo_ia": "Sistema precisa suportar CNPJ alfanumérico.",
        "tipo": "FOG",
        "status": "Aberto",
        "projeto": "RISK DRIVER",
        "data_conclusao": "2026-02-27",
    }]

    resultado = mod.calcular_correlacoes_email_fog([], threads, fogs)

    assert isinstance(resultado, dict), "Esperado dict"
    assert "<cnpj@mail>" in resultado, "ThreadId não encontrado no resultado"
    rels = resultado["<cnpj@mail>"]
    assert len(rels) >= 1, "Esperado ao menos 1 correlação FOG"

    primeiro = rels[0]
    assert primeiro.get("tipo") == "FOG", "Esperado tipo=FOG"
    assert primeiro.get("fogId") == "9999", "Esperado fogId=9999"
    assert "score" in primeiro, "Campo score ausente"
    assert "motivos" in primeiro, "Campo motivos ausente"


def test_funcoes_puras_cacheadas_e_imutaveis():
    """Contrato da otimização de performance (REGISTRO 2026-06-16 17:40):
    as funções puras são cacheadas (@lru_cache) e _palavras_relevantes devolve
    frozenset (imutável) — proteção contra mutação acidental do valor cacheado
    e garantia de que chamadas repetidas com o mesmo texto não recalculam.
    """
    mod = _carregar_script13()

    # _palavras_relevantes deve devolver frozenset (imutável, seguro p/ cache)
    palavras = mod._palavras_relevantes("CNPJ Alfanumérico - Impactos Finaud")
    assert isinstance(palavras, frozenset), f"Esperado frozenset, obtido {type(palavras)}"
    assert "cnpj" in palavras and "alfanumerico" in palavras

    # Cache ativo: mesma string → exatamente o MESMO objeto (cache hit), sem recalcular
    assert mod._palavras_relevantes("texto repetido X") is mod._palavras_relevantes("texto repetido X")
    assert mod._normalizar("Alfanumérico") is mod._normalizar("Alfanumérico")
    assert mod._extrair_periodo("balancete 12/2025") == "12/2025"

    # Idempotência: resultado estável entre chamadas
    assert mod._palavras_relevantes("DLO dezembro") == mod._palavras_relevantes("DLO dezembro")


TESTS = [
    test_score_fog_palavras_titulo_comuns,
    test_score_fog_sem_semelhanca,
    test_calcular_correlacoes_email_fog_retorna_dict,
    test_funcoes_puras_cacheadas_e_imutaveis,
]
