# -*- coding: utf-8 -*-
"""
Testes unitários para scripts/llm_resumo_engine.py

Cobre: _parse_iso, _normalizar_ocr, _jaccard_bigrams, deduplicar_ocrs,
       selecionar_prompt (com prompts sintéticos, sem arquivo em disco).
"""
import sys, os
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from llm_resumo_engine import (
    _parse_iso,
    _normalizar_ocr,
    _jaccard_bigrams,
    deduplicar_ocrs,
    selecionar_prompt,
)


# ---------------------------------------------------------------------------
# _parse_iso
# ---------------------------------------------------------------------------
class TestParseIso:
    def test_formato_iso(self):
        resultado = _parse_iso("2026-01-15")
        assert resultado == datetime(2026, 1, 15)

    def test_formato_dd_mm_yyyy(self):
        resultado = _parse_iso("15/01/2026")
        assert resultado == datetime(2026, 1, 15)

    def test_retorna_none_vazio(self):
        assert _parse_iso("") is None
        assert _parse_iso(None) is None

    def test_retorna_none_invalido(self):
        assert _parse_iso("nao-e-data") is None

    def test_trunca_horario(self):
        resultado = _parse_iso("2026-01-15T10:30:00")
        assert resultado == datetime(2026, 1, 15)


# ---------------------------------------------------------------------------
# _normalizar_ocr
# ---------------------------------------------------------------------------
class TestNormalizarOcr:
    def test_remove_header_imagem(self):
        texto = "--- 001_image1.png ---\nconteudo do ocr aqui"
        resultado = _normalizar_ocr(texto)
        assert "image" not in resultado
        assert "conteudo do ocr aqui" in resultado

    def test_lowercase(self):
        resultado = _normalizar_ocr("TEXTO MAIUSCULO")
        assert resultado == resultado.lower()

    def test_remove_caracteres_especiais(self):
        resultado = _normalizar_ocr("texto! com, pontuacao.")
        assert "!" not in resultado
        assert "," not in resultado

    def test_normaliza_espacos(self):
        resultado = _normalizar_ocr("texto   com   espacos")
        assert "  " not in resultado

    def test_vazio(self):
        assert _normalizar_ocr("") == ""
        assert _normalizar_ocr(None) == ""


# ---------------------------------------------------------------------------
# _jaccard_bigrams
# ---------------------------------------------------------------------------
class TestJaccardBigrams:
    def test_textos_identicos(self):
        a = "o arquivo foi enviado ao bacen"
        assert _jaccard_bigrams(a, a) == 1.0

    def test_textos_sem_sobreposicao(self):
        a = "arquivo bacen transmitido"
        b = "cliente solicitou retorno"
        assert _jaccard_bigrams(a, b) == 0.0

    def test_sobreposicao_parcial(self):
        a = "arquivo bacen transmitido com sucesso"
        b = "arquivo bacen aceito pelo sistema"
        resultado = _jaccard_bigrams(a, b)
        assert 0.0 < resultado < 1.0

    def test_texto_com_uma_palavra(self):
        assert _jaccard_bigrams("arquivo", "arquivo") == 0.0

    def test_texto_vazio(self):
        assert _jaccard_bigrams("", "qualquer coisa") == 0.0
        assert _jaccard_bigrams("qualquer coisa", "") == 0.0


# ---------------------------------------------------------------------------
# deduplicar_ocrs
# ---------------------------------------------------------------------------
class TestDeduplicarOcrs:
    def test_lista_vazia(self):
        assert deduplicar_ocrs([]) == []

    def test_item_sem_ocr_ignorado(self):
        resultado = deduplicar_ocrs([{"id": "1", "ocr": ""}])
        assert resultado == []

    def test_textos_identicos_deduplica(self):
        ocr = "arquivo dlo foi transmitido ao bacen com sucesso"
        items = [
            {"id": "1", "ocr": ocr},
            {"id": "2", "ocr": ocr},
        ]
        resultado = deduplicar_ocrs(items)
        assert len(resultado) == 1
        assert resultado[0]["id"] == "1"

    def test_textos_distintos_mantem(self):
        items = [
            {"id": "1", "ocr": "arquivo dlo transmitido ao bacen com sucesso"},
            {"id": "2", "ocr": "cliente solicitou retorno sobre critica pendente"},
        ]
        resultado = deduplicar_ocrs(items)
        assert len(resultado) == 2

    def test_similar_acima_limiar_deduplica(self):
        base    = "o arquivo dlo foi transmitido ao banco central com sucesso hoje"
        similar = "o arquivo dlo foi transmitido ao banco central com sucesso ontem"
        # Jaccard bigrams real é ~0.818; usar limiar 0.75 para garantir dedup
        items = [{"id": "1", "ocr": base}, {"id": "2", "ocr": similar}]
        resultado = deduplicar_ocrs(items, limiar=0.75)
        assert len(resultado) == 1

    def test_preserva_ordem(self):
        items = [
            {"id": "A", "ocr": "texto alpha beta gamma delta"},
            {"id": "B", "ocr": "texto diferente completamente novo"},
        ]
        resultado = deduplicar_ocrs(items)
        assert resultado[0]["id"] == "A"
        assert resultado[1]["id"] == "B"


# ---------------------------------------------------------------------------
# selecionar_prompt (mock de carregar_prompts)
# ---------------------------------------------------------------------------
_PROMPTS_MOCK = [
    {
        "categoria": "RETORNO_BACEN",
        "ativo": True,
        "data_inicio": "2026-01-01",
        "data_fim": None,
        "id": "rb_v1",
        "texto": "Prompt RB v1",
    },
    {
        "categoria": "RETORNO_BACEN",
        "ativo": True,
        "data_inicio": "2026-03-01",
        "data_fim": None,
        "id": "rb_v2",
        "texto": "Prompt RB v2 mais recente",
    },
    {
        "categoria": "DDR",
        "ativo": True,
        "data_inicio": "2026-01-01",
        "data_fim": None,
        "id": "ddr_v1",
        "texto": "Prompt DDR v1",
    },
    {
        "categoria": "RETORNO_BACEN",
        "ativo": False,
        "data_inicio": "2025-01-01",
        "data_fim": None,
        "id": "rb_inativo",
        "texto": "Prompt inativo",
    },
]


class TestSelecionarPrompt:
    def test_retorna_prompt_mais_recente(self):
        with patch("llm_resumo_engine.carregar_prompts", return_value=_PROMPTS_MOCK):
            resultado = selecionar_prompt("RETORNO_BACEN", "2026-04-01")
        assert resultado["id"] == "rb_v2"

    def test_retorna_prompt_correto_para_data_anterior(self):
        with patch("llm_resumo_engine.carregar_prompts", return_value=_PROMPTS_MOCK):
            resultado = selecionar_prompt("RETORNO_BACEN", "2026-02-01")
        assert resultado["id"] == "rb_v1"

    def test_ignora_inativo(self):
        with patch("llm_resumo_engine.carregar_prompts", return_value=_PROMPTS_MOCK):
            # Data anterior ao rb_v1 (2026-01) e rb_v2 (2026-03) — ambos no futuro
            resultado = selecionar_prompt("RETORNO_BACEN", "2025-06-01")
        assert resultado is None

    def test_retorna_none_categoria_inexistente(self):
        with patch("llm_resumo_engine.carregar_prompts", return_value=_PROMPTS_MOCK):
            resultado = selecionar_prompt("CATEGORIA_INEXISTENTE", "2026-04-01")
        assert resultado is None

    def test_case_insensitive(self):
        with patch("llm_resumo_engine.carregar_prompts", return_value=_PROMPTS_MOCK):
            resultado = selecionar_prompt("retorno_bacen", "2026-04-01")
        assert resultado is not None

    def test_lista_vazia_retorna_none(self):
        with patch("llm_resumo_engine.carregar_prompts", return_value=[]):
            assert selecionar_prompt("RETORNO_BACEN") is None
