"""
QA – Script 09 integrador: campo `empresa` nas threads do JSON 03.

Valida que _resolver_empresa retorna o nome correto da empresa ou vazio
nos casos esperados, e que o campo existe nas threads após _processar_threads.

Adicionado em 2026-07-09: campo empresa estava ausente do dict thread_formatada
em _processar_threads — calculado nos eventos individuais mas não propagado.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

from tests.conftest import RAIZ

sys.path.insert(0, RAIZ)

PATH_09 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")


def _carregar_mod():
    # Script 09 importa 'paths' que mora em scripts/ — precisa estar no sys.path
    scripts_dir = os.path.join(RAIZ, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("integrador09", PATH_09)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# _resolver_empresa
# ---------------------------------------------------------------------------

def test_resolver_empresa_por_dominio():
    """Domínio cadastrado → retorna nome da empresa."""
    mod = _carregar_mod()
    cadastro = mod._carregar_cadastro_empresas_09()
    if not cadastro:
        pytest.skip("Cadastro vazio — ambiente sem dados")

    # Pega o primeiro domínio cadastrado para montar um e-mail de teste
    empresa_alvo, info = next(
        ((e, i) for e, i in cadastro.items() if isinstance(i, dict) and i.get("dominios")),
        (None, None),
    )
    if not empresa_alvo:
        pytest.skip("Nenhuma empresa com domínio cadastrado")

    dominio = info["dominios"][0]
    msgs = [{"contato_origem": {"lado": "CLIENTE", "email": f"contato@{dominio}"}, "contato_destino": {}}]
    resultado = mod._resolver_empresa({"assunto": "", "mensagens": msgs})
    assert resultado == empresa_alvo, f"Esperava '{empresa_alvo}', recebeu '{resultado}'"


def test_resolver_empresa_sem_cliente_retorna_vazio():
    """Thread sem remetente CLIENTE (ex.: interna Finaud) → empresa vazia."""
    mod = _carregar_mod()
    msgs = [{"contato_origem": {"lado": "FINAUD", "email": "andrea@finaud.com.br"}, "contato_destino": {}}]
    resultado = mod._resolver_empresa({"assunto": "", "mensagens": msgs})
    assert resultado == "", f"Esperava vazio, recebeu '{resultado}'"


def test_resolver_empresa_dominio_generico_retorna_vazio():
    """Domínio genérico (gmail, hotmail) não identifica empresa."""
    mod = _carregar_mod()
    msgs = [{"contato_origem": {"lado": "CLIENTE", "email": "cliente@gmail.com"}, "contato_destino": {}}]
    resultado = mod._resolver_empresa({"assunto": "", "mensagens": msgs})
    assert resultado == "", f"Domínio genérico não deve resolver empresa, recebeu '{resultado}'"


def test_resolver_empresa_sem_mensagens_retorna_vazio():
    """Thread sem mensagens → empresa vazia."""
    mod = _carregar_mod()
    resultado = mod._resolver_empresa({"assunto": "", "mensagens": []})
    assert resultado == ""


# ---------------------------------------------------------------------------
# campo empresa presente nas threads do JSON 03
# ---------------------------------------------------------------------------

def test_json03_threads_tem_campo_empresa():
    """Após rodar Script 09, todas as threads do JSON 03 devem ter o campo 'empresa'."""
    arquivo = os.path.join(RAIZ, "data", "json", "pipeline", "03_integrador_dados_site.json")
    if not os.path.isfile(arquivo):
        pytest.skip("JSON 03 não encontrado")

    import json
    with open(arquivo, "r", encoding="utf-8") as f:
        dados = json.load(f)

    threads = dados.get("threads", [])
    if not threads:
        pytest.skip("Nenhuma thread no JSON 03")

    sem_campo = [t.get("threadId", "?") for t in threads if "empresa" not in t]
    assert not sem_campo, (
        f"{len(sem_campo)} thread(s) sem campo 'empresa': {sem_campo[:5]}"
    )
