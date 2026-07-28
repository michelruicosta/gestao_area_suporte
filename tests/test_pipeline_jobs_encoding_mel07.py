# -*- coding: utf-8 -*-
"""MEL-07 / encoding dos subprocessos do pipeline (``pipeline_jobs``).

Trava o contrato que estava quebrado em produção (validação 2026-06-16): o
``scripts_status`` por etapa vinha **vazio** porque a linha ``⏱ Duração desta etapa``
(com emoji) era perdida no pipe cp1252 do Windows. A correção: lançar os subprocessos
com ``PYTHONIOENCODING=utf-8`` (``_env_utf8``) e decodificar o stdout sempre como UTF-8.

Estes testes cobrem:
  • ``_env_utf8`` força ``PYTHONIOENCODING=utf-8`` e mescla extras;
  • ``_consumir_linhas_stdout`` decodifica UTF-8 (emoji/acento) e popula ``scripts_status``;
  • a etapa com erro vira ``err`` (não ``ok``).
"""
from __future__ import annotations

import io


class _FakeProc:
    """Subprocesso falso cujo ``stdout`` entrega bytes (como o pipe real)."""

    def __init__(self, data: bytes):
        self.stdout = io.BytesIO(data)


def test_env_utf8_forca_pythonioencoding():
    import pipeline_jobs as pj

    env = pj._env_utf8()
    assert env["PYTHONIOENCODING"] == "utf-8"
    # mescla extras sem perder o encoding
    env2 = pj._env_utf8({"ORACULO_INCREMENTAL": "1"})
    assert env2["PYTHONIOENCODING"] == "utf-8"
    assert env2["ORACULO_INCREMENTAL"] == "1"


def test_consumir_linhas_popula_scripts_status_com_emoji_utf8():
    import pipeline_jobs as pj

    # Linha real do executar_tudo (laço principal, linha 421): tem o emoji ⏱ + acento.
    data = (
        "--- Etapa 13. Correlacionar threads ---\n"
        "   ⏱ Duração desta etapa: 56.40s (0.94 min)\n"
    ).encode("utf-8")
    job = pj._novo_job("teste")[1]

    pj._consumir_linhas_stdout(_FakeProc(data), job)

    # O status por etapa (MEL-07) tem de ser preenchido a partir da linha de duração.
    assert job["scripts_status"].get("13") == "ok"
    # E o acento tem de sobreviver (decodificou UTF-8, não cp1252 → sem mojibake).
    assert any("Duração desta etapa" in linha for linha in job["log_tail"])


def test_consumir_linhas_marca_err_quando_etapa_falha():
    import pipeline_jobs as pj

    data = (
        "--- Etapa 09. Integrar dados do painel ---\n"
        "   ERRO na execucao de 09_integrar_dados_painel: boom\n"
        "   Duração desta etapa: 1.20s (0.02 min)\n"
    ).encode("utf-8")
    job = pj._novo_job("teste")[1]

    pj._consumir_linhas_stdout(_FakeProc(data), job)

    assert job["scripts_status"].get("09") == "err"
