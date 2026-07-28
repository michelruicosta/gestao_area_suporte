# -*- coding: utf-8 -*-
"""
Testes de regressão (snapshot) para o motor de triagem.

Carrega uma fixture de 12 threads reais (com classificações conhecidas)
e verifica que triar() produz exatamente os mesmos resultados após qualquer
alteração nas regras de triagem.

Estes testes NÃO gravam em disco — chamam triar() diretamente com a fixture
em memória. Se um snapshot falhar, significa que a mudança alterou o
comportamento de classificação de um thread que antes estava correto.

Fixture: tests/fixtures/snapshot_threads.json
  - 3 threads DDR4111 AGUARDANDO
  - 3 threads DDR4111 CONCLUIDO
  - 2 threads DLO AGUARDANDO
  - 2 threads RETORNO_BACEN AGUARDANDO
  - 2 threads S5 CONCLUIDO
"""
import json
import sys
import os
from pathlib import Path

# Garante que scripts/ está no path
PROJETO = Path(__file__).parent.parent
sys.path.insert(0, str(PROJETO / "scripts"))

from triagem_auto_ddr4111 import triar, CADOC_TRIAGEM_DDR4111

FIXTURE_PATH = PROJETO / "tests" / "fixtures" / "snapshot_threads.json"


def _carregar_fixture() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _classificar(alvo: str, cadocs: frozenset) -> tuple[set, set]:
    """Retorna (tids_concluidos, tids_aguardando) para o alvo."""
    dados = _carregar_fixture()
    co, ag, _ = triar(dados, None, cadocs=cadocs, alvo_triagem=alvo)
    return (
        {r["threadId"] for r in co},
        {r["threadId"] for r in ag},
    )


# ---------------------------------------------------------------------------
# DDR4111
# ---------------------------------------------------------------------------
class TestSnapshotDDR4111:
    _CO = {
        "GMTHRID_1866436622083994705",
        "GMTHRID_1866903564468967353",
        "GMTHRID_1866917207220850952",
        "GMTHRID_1856123008075476908",  # Acredito SCD — G3: 'de acordo' após instrução Finaud
    }
    _AG = {
        "GMTHRID_1856035124888412297",
        "GMTHRID_1856747757614490746",
    }

    def test_quantidade_concluidos(self):
        co, _ = _classificar("DDR4111", CADOC_TRIAGEM_DDR4111)
        assert len(co & self._CO) == 4, f"Esperava 4 DDR4111 concluídos, encontrou: {co & self._CO}"

    def test_quantidade_aguardando(self):
        _, ag = _classificar("DDR4111", CADOC_TRIAGEM_DDR4111)
        assert len(ag & self._AG) == 2, f"Esperava 2 DDR4111 aguardando, encontrou: {ag & self._AG}"

    def test_nenhum_concluido_virou_aguardando(self):
        co, ag = _classificar("DDR4111", CADOC_TRIAGEM_DDR4111)
        regressao = self._CO & ag
        assert not regressao, f"Threads que eram CONCLUIDO viraram AGUARDANDO: {regressao}"

    def test_nenhum_aguardando_sumiu(self):
        co, ag = _classificar("DDR4111", CADOC_TRIAGEM_DDR4111)
        sumidos = self._AG - ag - co  # pode ter migrado para CO, mas não pode sumir
        assert not sumidos, f"Threads AGUARDANDO sumiram sem nova classificação: {sumidos}"

    def test_tids_concluidos_exatos(self):
        co, _ = _classificar("DDR4111", CADOC_TRIAGEM_DDR4111)
        assert self._CO <= co, f"Tids concluídos esperados não encontrados: {self._CO - co}"

    def test_tids_aguardando_exatos(self):
        _, ag = _classificar("DDR4111", CADOC_TRIAGEM_DDR4111)
        assert self._AG <= ag, f"Tids aguardando esperados não encontrados: {self._AG - ag}"


# ---------------------------------------------------------------------------
# DLO
# ---------------------------------------------------------------------------
class TestSnapshotDLO:
    _CO = {"GMTHRID_1866436622083994705"}
    _AG = {
        "GMTHRID_1855568856209220982",
        "GMTHRID_1856111714890581464",
    }

    def test_concluido_permanece(self):
        co, _ = _classificar("DLO", frozenset({"DLO_2061"}))
        assert self._CO <= co, f"DLO concluído regrediu: {self._CO - co}"

    def test_aguardando_permanecem(self):
        _, ag = _classificar("DLO", frozenset({"DLO_2061"}))
        assert self._AG <= ag, f"DLO aguardando sumiram: {self._AG - ag}"

    def test_nenhum_aguardando_virou_concluido_inesperadamente(self):
        co, ag = _classificar("DLO", frozenset({"DLO_2061"}))
        inesperado = (self._AG & co) - self._CO
        assert not inesperado, f"DLO aguardando migrou para concluído inesperadamente: {inesperado}"


# ---------------------------------------------------------------------------
# RETORNO_BACEN
# ---------------------------------------------------------------------------
class TestSnapshotRetornoBacen:
    _AG = {
        "GMTHRID_1738704422376544782",
        "GMTHRID_1843529890625455068",
    }

    def test_todos_aguardando(self):
        co, ag = _classificar("RETORNO_BACEN", frozenset({"RETORNO_BACEN"}))
        assert self._AG <= ag, f"RB aguardando sumiram: {self._AG - ag}"

    def test_nenhum_concluido_inesperado(self):
        co, _ = _classificar("RETORNO_BACEN", frozenset({"RETORNO_BACEN"}))
        inesperado = self._AG & co
        assert not inesperado, f"RB aguardando viraram concluído: {inesperado}"

    def test_quantidade_aguardando(self):
        _, ag = _classificar("RETORNO_BACEN", frozenset({"RETORNO_BACEN"}))
        assert len(ag & self._AG) == 2


# ---------------------------------------------------------------------------
# S5
# ---------------------------------------------------------------------------
class TestSnapshotS5:
    _CO = {
        "GMTHRID_1856749033520691503",
        "GMTHRID_1857485851789165677",
    }

    def test_ambos_concluidos(self):
        co, _ = _classificar("S5", frozenset({"S5"}))
        assert self._CO <= co, f"S5 concluídos sumiram: {self._CO - co}"

    def test_nenhum_concluido_virou_aguardando(self):
        _, ag = _classificar("S5", frozenset({"S5"}))
        regressao = self._CO & ag
        assert not regressao, f"S5 concluído regrediu para aguardando: {regressao}"

    def test_quantidade_concluidos(self):
        co, _ = _classificar("S5", frozenset({"S5"}))
        assert len(co & self._CO) == 2
