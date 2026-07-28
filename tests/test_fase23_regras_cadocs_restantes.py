# -*- coding: utf-8 -*-
"""
FASE 2+3 TDD — Campo 'regra' (R1-R5) para os CADOCs restantes

Threads REAIS do JSON 03 (2026-06-22):
  DRL_2160  CO: GMTHRID_1868178463637068071  (Fair Corretora — Silvio Basque)
  DRL_2160  AG: GMTHRID_1868094930909531258  (Siberio Silva)
  DLO_2061  CO: GMTHRID_1868181648899476642  (Global Exchange)
  DLO_2061  AG: GMTHRID_1868062528457401587  (ARC Corretora)
  DLI_2062  CO: GMTHRID_1867730689288797690  (BR Capital)
  DLI_2062  AG: GMTHRID_1868180969240092640  (Atual Cambio — C->F)
  S5        CO: GMTHRID_1867627979941080551  (Vector)
  S5        AG: GMTHRID_1868091022129919412  (Numatur — C->F)
  DRM_2060  CO: GMTHRID_1867452968061342893  (Guru)
  DRM_2060  AG: GMTHRID_1867550667292818754  (Paulo Ricardo)
  RB        CO: GMTHRID_1868148778055039711  (Mattar)
  RB        AG: GMTHRID_1868179684513048461  (Atual Cambio — F->C)
  SUPORTE   CO: GMTHRID_1862656638909561659  (BPY Global — C->F)
  SUPORTE   AG: GMTHRID_1868184207384194941  (Encaminhamento interno — F->F)
  DRSAC     CO: GMTHRID_1858833627365979844  (Braza Bank)   [nenhum AG real]
  FORCAP    CO: GMTHRID_1867168849677753406  (Braza Bank)
  FORCAP    AG: GMTHRID_1866277922663444277  (Encaminhamento interno — F->F)
  6209      AG: GMTHRID_1863628234606221398  (Wise)         [nenhum CO real]
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import triagem.motor as _motor

_JSON03 = os.path.join(os.path.dirname(__file__), "..", "data", "json", "pipeline", "03_integrador_dados_site.json")
pytestmark = pytest.mark.skipif(not os.path.isfile(_JSON03), reason="JSON 03 não disponível (ambiente sem dados de produção)")


# ---------------------------------------------------------------------------
# Fixture: reset cache global entre testes
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_cache():
    _motor._CACHE_DADOS_03["dados"] = None
    _motor._CACHE_DADOS_03["mtime"] = None
    yield
    _motor._CACHE_DADOS_03["dados"] = None
    _motor._CACHE_DADOS_03["mtime"] = None


# ---------------------------------------------------------------------------
# Executor central
# ---------------------------------------------------------------------------
def _run(thread_ids, alvo_triagem, cadocs):
    """Roda o motor com threads REAIS filtradas do JSON 03."""
    with open(
        "data/json/pipeline/03_integrador_dados_site.json", encoding="utf-8"
    ) as f:
        tudo = json.load(f)

    threads_f = [t for t in tudo.get("threads", []) if t.get("threadId") in thread_ids]
    eventos_f = [e for e in tudo.get("eventos", []) if e.get("threadId") in thread_ids]
    dados = {"threads": threads_f, "eventos": eventos_f}

    captured = {}

    with (
        patch("triagem.motor.os.path.isfile", return_value=True),
        patch("triagem.motor.os.path.getmtime", return_value=0.0),
        patch("triagem.motor.load_concluidas", return_value=[]),
        patch("triagem.motor.load_aguardando", return_value=[]),
        patch("triagem.motor.save_concluidas", side_effect=lambda x: captured.update({"co": list(x)})),
        patch("triagem.motor.save_aguardando", side_effect=lambda x: captured.update({"ag": list(x)})),
        patch.dict("os.environ", {"ORACULO_CARGA_EM_CURSO": "1"}),
    ):
        _motor._CACHE_DADOS_03["dados"] = dados
        _motor._CACHE_DADOS_03["mtime"] = 0.0

        from triagem.motor import _run_triagem_cadocs
        _run_triagem_cadocs(
            apply=True,
            data_ref=None,
            cadocs=cadocs,
            com_sec6b=False,
            log_prefix="TEST",
            alvo_triagem=alvo_triagem,
        )

    return captured.get("co", []), captured.get("ag", [])


def _get(lista, tid):
    for r in lista:
        if isinstance(r, dict) and str(r.get("threadId") or "").strip() == tid:
            return r
    return None


# ============================================================================
# DRL_2160 (via modulo DDR4111)
# ============================================================================

class TestDRL2160:
    CO = "GMTHRID_1868178463637068071"
    AG = "GMTHRID_1868094930909531258"
    CADOCS = frozenset({"DRL_2160"})
    ALVO = "DDR4111"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "DRL_2160 CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1", f"Esperava R1, got {r.get('regra')}"

    def test_ag_tem_status_aguardando_e_regra_preenchida(self):
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "DRL_2160 AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] in {"R2", "R3", "R4", "R5"}, f"Regra inesperada: {r.get('regra')}"


# ============================================================================
# DLO_2061
# ============================================================================

class TestDLO2061:
    CO = "GMTHRID_1868181648899476642"
    AG = "GMTHRID_1868062528457401587"
    CADOCS = frozenset({"DLO_2061"})
    ALVO = "DLO"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "DLO CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"

    def test_ag_tem_status_aguardando_e_regra_fc(self):
        """ARC Corretora — ultima mensagem F->C, esperamos R3 ou R4."""
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "DLO AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] in {"R3", "R4"}, f"F->C esperava R3/R4, got {r.get('regra')}"


# ============================================================================
# DLI_2062
# ============================================================================

class TestDLI2062:
    CO = "GMTHRID_1867730689288797690"
    AG = "GMTHRID_1868180969240092640"
    CADOCS = frozenset({"DLI_2062"})
    ALVO = "DLI"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "DLI CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"

    def test_ag_virou_co_apos_carga_17jun(self):
        """Galdino Alvim — carga 17/06 adicionou: Finaud enviou DLI + cliente acusou recebimento (vazio).
        Motor classifica como CONCLUÍDO (§5 remessa Finaud→cliente) com R1."""
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(co, self.AG)
        assert r is not None, "DLI deveria estar CONCLUIDO (Finaud entregou, cliente acusou recebimento)"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1", f"§5 remessa esperava R1, got {r.get('regra')}"


# ============================================================================
# S5
# ============================================================================

class TestS5:
    CO = "GMTHRID_1867627979941080551"
    AG = "GMTHRID_1868091022129919412"
    CADOCS = frozenset({"S5"})
    ALVO = "S5"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "S5 CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"

    def test_ag_tem_status_aguardando_e_regra_r2(self):
        """Numatur — ultima mensagem C->F, esperamos R2."""
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "S5 AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] == "R2", f"C->F esperava R2, got {r.get('regra')}"


# ============================================================================
# DRM_2060
# ============================================================================

class TestDRM2060:
    CO = "GMTHRID_1867452968061342893"
    AG = "GMTHRID_1867550667292818754"
    CADOCS = frozenset({"DRM_2060"})
    ALVO = "DRM_2060"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "DRM CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"

    def test_ag_tem_status_aguardando_e_regra_preenchida(self):
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "DRM AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] in {"R2", "R3", "R4", "R5"}, f"Regra inesperada: {r.get('regra')}"


# ============================================================================
# RETORNO_BACEN
# ============================================================================

class TestRetornoBacen:
    CO = "GMTHRID_1868148778055039711"
    AG = "GMTHRID_1868179684513048461"
    CADOCS = frozenset({"RETORNO_BACEN"})
    ALVO = "RETORNO_BACEN"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "RB CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"

    def test_ag_tem_status_aguardando_e_regra_r2(self):
        """Galdino Alvim — carga 17/06 adicionou resposta do cliente (C->F).
        Motor classifica como AGUARDANDO com R2 (última mensagem é do cliente)."""
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "RB AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] == "R2", f"C->F esperava R2, got {r.get('regra')}"


# ============================================================================
# SUPORTE
# ============================================================================

class TestSuporte:
    CO = "GMTHRID_1862656638909561659"
    AG = "GMTHRID_1868184207384194941"
    CADOCS = frozenset({"SUPORTE"})
    ALVO = "SUPORTE"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "SUPORTE CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"

    def test_ag_comunicado_interno_vai_para_concluido(self):
        """Thread F→F com assunto 'teste' e corpo 'Riscos' → CONCLUÍDO via Regra 0c.
        O supervisor classifica como R5 (F→F AGUARDANDO), mas o pós-processamento
        da Regra 0c reconhece como e-mail de teste interno e move para CONCLUÍDO.
        """
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(co, self.AG)
        assert r is not None, "SUPORTE AG (e-mail de teste) deveria ir para CONCLUÍDO via R0c"
        assert "R0c" in (r.get("motivo_conclusao") or ""), f"Esperava motivo R0c, got: {r.get('motivo_conclusao')}"
        assert _get(ag, self.AG) is None, "Thread de teste não deve permanecer em AGUARDANDO"


# ============================================================================
# DRSAC  (thread real vai para AG com F->C fallback — R3)
# ============================================================================

class TestDRSAC:
    AG = "GMTHRID_1858833627365979844"
    CADOCS = frozenset({"DRSAC"})
    ALVO = "DRSAC"

    def test_ag_tem_status_aguardando_e_regra_preenchida(self):
        """Thread real classificada como AG pelo motor (ultima F->C fora §5/§3-inv/§3.5)."""
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "DRSAC AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] in {"R2", "R3", "R4", "R5"}, f"Regra inesperada: {r.get('regra')}"


# ============================================================================
# FORCAPITAL
# ============================================================================

class TestForcapital:
    CO = "GMTHRID_1867168849677753406"
    CADOCS = frozenset({"FORCAPITAL"})
    ALVO = "FORCAPITAL"

    def test_co_tem_status_concluido_e_regra_r1(self):
        co, ag = _run([self.CO], self.ALVO, self.CADOCS)
        r = _get(co, self.CO)
        assert r is not None, "FORCAPITAL CO deveria estar CONCLUIDO"
        assert r["status"] == "CONCLUIDO"
        assert "regra" in r
        assert r["regra"] == "R1"


# ============================================================================
# 6209  (sem dados CO reais — testa so AG)
# ============================================================================

class TestCadoc6209:
    AG = "GMTHRID_1863628234606221398"
    CADOCS = frozenset({"6209"})
    ALVO = "6209"

    def test_ag_tem_status_aguardando_e_regra_preenchida(self):
        """Wise — regra exata depende da direcao; validamos que campo existe e e valido."""
        co, ag = _run([self.AG], self.ALVO, self.CADOCS)
        r = _get(ag, self.AG)
        assert r is not None, "6209 AG deveria estar AGUARDANDO"
        assert r["status"] == "AGUARDANDO"
        assert "regra" in r
        assert r["regra"] in {"R2", "R3", "R4", "R5"}, f"Regra inesperada: {r.get('regra')}"


# ============================================================================
# G3 — par conclusivo: cliente diz "de acordo" após instrução da Finaud
# ============================================================================

class TestG3ParConclusivo:
    """G3: última CLIENTE com concordância ('de acordo', 'ok', etc.) + penúltima FINAUD → CONCLUÍDO R1.

    Caso positivo: Acredito SCD (4111) — cliente confirma 'de acordo com os procedimentos'
    após Andrea (Finaud) instruir sobre preenchimento do 4111. Sem '?', penúltima é Finaud.

    Caso de proteção: Fourtrade (DRM_2060) — cliente diz 'Agradeço... está correto dessa
    forma?' — tem '?' → deve permanecer AGUARDANDO (G3 não dispara).
    """

    # Acredito SCD — concordância pura após instrução Finaud → deve ser CONCLUÍDO
    CO = "GMTHRID_1856123008075476908"
    CADOCS_CO = frozenset({"4111"})
    ALVO_CO = "DDR4111"

    # Fourtrade — concordância + nova pergunta → deve permanecer AGUARDANDO
    AG = "GMTHRID_1861275516695476038"
    CADOCS_AG = frozenset({"DRM_2060"})
    ALVO_AG = "DRM_2060"

    def test_acredito_scd_concordancia_vira_concluido(self):
        """Acredito SCD: 'De acordo com os procedimentos' após instrução Finaud → CONCLUÍDO R1."""
        co, ag = _run([self.CO], self.ALVO_CO, self.CADOCS_CO)
        r = _get(co, self.CO)
        assert r is not None, "Acredito SCD deveria estar CONCLUIDO (G3: cliente concordou sem nova pergunta)"
        assert r["status"] == "CONCLUIDO"
        assert r["regra"] == "R1"

    def test_fourtrade_concordancia_com_pergunta_fica_aguardando(self):
        """Fourtrade: 'está correto dessa forma?' — tem '?' → G3 não dispara, AGUARDANDO."""
        co, ag = _run([self.AG], self.ALVO_AG, self.CADOCS_AG)
        r = _get(ag, self.AG)
        assert r is not None, "Fourtrade deveria estar AGUARDANDO (G3: cliente fez nova pergunta)"
        assert r["status"] == "AGUARDANDO"
        assert r["regra"] in {"R2", "R3", "R4", "R5"}
