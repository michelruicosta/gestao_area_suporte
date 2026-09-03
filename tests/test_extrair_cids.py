"""Testes para _extrair_cids_payload — extração de imagens inline (CID) de payloads Gmail."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from servidor_telas import _extrair_cids_payload


def _payload_imagem(cid: str, att_id: str, mime: str = 'image/png') -> dict:
    return {
        'mimeType': mime,
        'headers': [{'name': 'Content-ID', 'value': f'<{cid}>'}],
        'body': {'attachmentId': att_id},
    }


def test_imagem_simples():
    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            {'mimeType': 'text/plain', 'body': {'data': ''}, 'headers': []},
            _payload_imagem('image001.png@01DD2E6C.28538210', 'att123'),
        ],
    }
    result = _extrair_cids_payload(payload)
    assert result == {
        'image001.png@01DD2E6C.28538210': {'attachment_id': 'att123', 'mime': 'image/png'}
    }


def test_sem_imagens():
    payload = {'mimeType': 'text/plain', 'parts': []}
    assert _extrair_cids_payload(payload) == {}


def test_aninhado_multipart():
    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            {
                'mimeType': 'multipart/related',
                'parts': [
                    _payload_imagem('img2@abc', 'att456', 'image/jpeg'),
                ],
            }
        ],
    }
    result = _extrair_cids_payload(payload)
    assert result == {'img2@abc': {'attachment_id': 'att456', 'mime': 'image/jpeg'}}


def test_multiplas_imagens():
    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            _payload_imagem('logo@x', 'att1', 'image/png'),
            _payload_imagem('screenshot@y', 'att2', 'image/png'),
        ],
    }
    result = _extrair_cids_payload(payload)
    assert len(result) == 2
    assert result['logo@x']['attachment_id'] == 'att1'
    assert result['screenshot@y']['attachment_id'] == 'att2'


def test_cid_sem_attachment_id_ignorado():
    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            {
                'mimeType': 'image/png',
                'headers': [{'name': 'Content-ID', 'value': '<sem-att@x>'}],
                'body': {},  # sem attachmentId
            }
        ],
    }
    result = _extrair_cids_payload(payload)
    assert result == {}


def test_cid_sem_header_ignorado():
    payload = {
        'mimeType': 'multipart/mixed',
        'parts': [
            {
                'mimeType': 'image/png',
                'headers': [],
                'body': {'attachmentId': 'att999'},
            }
        ],
    }
    result = _extrair_cids_payload(payload)
    assert result == {}
