"""Testa o cache em arquivo dos mapas de CID de threads (api_thread)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

MAPS_EXEMPLO = [
    {'message_id': 'msg1', 'cids': {'logo': 'att1'}, 'gmail_images': []},
    {'message_id': 'msg2', 'cids': {}, 'gmail_images': []},
]


@pytest.fixture(autouse=True)
def _dir_temporario(monkeypatch, tmp_path):
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_THREADS_DIR', str(tmp_path))


def test_cache_miss_retorna_none():
    import servidor_telas as st
    assert st._thread_cid_cache_ler('thread_inexistente', 3) is None


def test_cache_gravar_e_ler_mesmo_n(tmp_path, monkeypatch):
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_THREADS_DIR', str(tmp_path))

    st._thread_cid_cache_gravar('thread1', 2, MAPS_EXEMPLO)
    resultado = st._thread_cid_cache_ler('thread1', 2)

    assert resultado == MAPS_EXEMPLO


def test_cache_invalida_quando_n_muda(tmp_path, monkeypatch):
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_THREADS_DIR', str(tmp_path))

    st._thread_cid_cache_gravar('thread1', 2, MAPS_EXEMPLO)
    # Nova mensagem chegou — n mudou de 2 para 3
    assert st._thread_cid_cache_ler('thread1', 3) is None


def test_cache_nao_vaza_entre_threads(tmp_path, monkeypatch):
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_THREADS_DIR', str(tmp_path))

    st._thread_cid_cache_gravar('threadA', 2, MAPS_EXEMPLO)
    assert st._thread_cid_cache_ler('threadB', 2) is None


def test_cache_arquivo_corrompido_retorna_none(tmp_path, monkeypatch):
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_THREADS_DIR', str(tmp_path))

    caminho = tmp_path / 'thread1.json'
    caminho.write_bytes(b'json invalido {{{')
    assert st._thread_cid_cache_ler('thread1', 2) is None


def test_cache_atualiza_ao_regravar(tmp_path, monkeypatch):
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_THREADS_DIR', str(tmp_path))

    maps_v1 = [{'message_id': 'msg1', 'cids': {}, 'gmail_images': []}]
    maps_v2 = MAPS_EXEMPLO

    st._thread_cid_cache_gravar('thread1', 1, maps_v1)
    # Nova mensagem chegou — salva versão nova com n=2
    st._thread_cid_cache_gravar('thread1', 2, maps_v2)

    assert st._thread_cid_cache_ler('thread1', 1) is None
    assert st._thread_cid_cache_ler('thread1', 2) == maps_v2
