"""Testa o aquecimento do cache FogBugz na subida do servidor."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


def test_aquece_cache_chama_buscar_fog(monkeypatch):
    import servidor_telas as st
    chamadas = []

    def _fog_fake():
        chamadas.append(1)
        return [{'id': 1}]

    monkeypatch.setattr(st, '_buscar_fog', _fog_fake)
    st._aquece_cache_fog()
    assert len(chamadas) == 1


def test_aquece_cache_nao_propaga_excecao(monkeypatch):
    import servidor_telas as st

    def _fog_quebrado():
        raise RuntimeError('FogBugz indisponível')

    monkeypatch.setattr(st, '_buscar_fog', _fog_quebrado)
    st._aquece_cache_fog()  # não deve levantar exceção
