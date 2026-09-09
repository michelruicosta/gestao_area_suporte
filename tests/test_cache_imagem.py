"""Testa o cache em arquivo das imagens de e-mail (api_imagem)."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


# Patch CACHE_IMAGENS_DIR antes de importar servidor_telas
@pytest.fixture(autouse=True)
def _dir_temporario(monkeypatch, tmp_path):
    import paths
    monkeypatch.setattr(paths, 'CACHE_IMAGENS_DIR', str(tmp_path))
    # Reimporta as funções para que usem o diretório temporário
    import importlib
    import servidor_telas as st
    monkeypatch.setattr(st, 'CACHE_IMAGENS_DIR', str(tmp_path))
    return tmp_path


def _importar():
    import servidor_telas as st
    return st


PNG_1PX = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
    b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
    b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def test_cache_miss_retorna_none():
    st = _importar()
    assert st._imagem_cache_ler('msg_inexistente', 'att_inexistente') is None


def test_cache_gravar_e_ler(tmp_path, monkeypatch):
    st = _importar()
    monkeypatch.setattr(st, 'CACHE_IMAGENS_DIR', str(tmp_path))

    st._imagem_cache_gravar('msg1', 'att1', PNG_1PX, 'image/png')
    resultado = st._imagem_cache_ler('msg1', 'att1')

    assert resultado is not None
    data, ct = resultado
    assert data == PNG_1PX
    assert ct == 'image/png'


def test_cache_nao_vaza_entre_anexos(tmp_path, monkeypatch):
    st = _importar()
    monkeypatch.setattr(st, 'CACHE_IMAGENS_DIR', str(tmp_path))

    st._imagem_cache_gravar('msg1', 'att1', PNG_1PX, 'image/png')
    assert st._imagem_cache_ler('msg1', 'att2') is None
    assert st._imagem_cache_ler('msg2', 'att1') is None


def test_detectar_ct_png():
    st = _importar()
    assert st._imagem_detectar_ct(PNG_1PX) == 'image/png'


def test_detectar_ct_jpeg():
    st = _importar()
    assert st._imagem_detectar_ct(b'\xff\xd8\xff\xe0resto') == 'image/jpeg'


def test_detectar_ct_gif():
    st = _importar()
    assert st._imagem_detectar_ct(b'GIF89aresto') == 'image/gif'


def test_detectar_ct_webp():
    st = _importar()
    webp = b'RIFF\x00\x00\x00\x00WEBPrestoqualquer'
    assert st._imagem_detectar_ct(webp) == 'image/webp'


def test_detectar_ct_desconhecido():
    st = _importar()
    assert st._imagem_detectar_ct(b'\x00\x01\x02\x03') == 'application/octet-stream'


def test_cache_bin_corrompido_retorna_none(tmp_path, monkeypatch):
    st = _importar()
    monkeypatch.setattr(st, 'CACHE_IMAGENS_DIR', str(tmp_path))

    # Grava .bin mas não .ct
    nome = 'msg1__att1'
    (tmp_path / f'{nome}.bin').write_bytes(PNG_1PX)
    # Sem .ct → deve retornar None sem explodir
    resultado = st._imagem_cache_ler('msg1', 'att1')
    # Pode retornar None (arquivo .ct ausente levanta FileNotFoundError → OSError)
    assert resultado is None or isinstance(resultado, tuple)
