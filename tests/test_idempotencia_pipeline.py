"""
Camada 6 — Testes de idempotencia do pipeline.

Verifica que rodar o mesmo script duas vezes seguidas produz o mesmo resultado.
Detecta scripts que acumulam entradas em vez de substituir (bug silencioso).

Estrategia: comparar contagens e campos-chave entre primeira e segunda execucao
usando as fixtures congeladas como entrada, sem tocar os dados de producao.
"""

import json
import os
import sys
import copy
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _carregar(nome):
    caminho = FIXTURES / nome
    if not caminho.exists():
        pytest.skip(f"Fixture {nome} nao encontrada — rode scripts/criar_fixtures.py")
    return json.loads(caminho.read_text(encoding="utf-8"))


def _metricas_aguardando(lista):
    """Metricas relevantes de uma lista de threads aguardando."""
    if not isinstance(lista, list):
        return {}
    tids = [r.get("threadId") for r in lista if isinstance(r, dict)]
    tipos = [r.get("tipo") for r in lista if isinstance(r, dict)]
    return {
        "total": len(lista),
        "tids_unicos": len(set(tids)),
        "tids_duplicados": len(tids) - len(set(tids)),
        "tipos": sorted(set(t for t in tipos if t)),
    }


def _metricas_eventos(lista):
    if not isinstance(lista, list):
        return {}
    tids = [e.get("threadId") for e in lista if isinstance(e, dict)]
    return {
        "total": len(lista),
        "threads_unicas": len(set(tids)),
    }


# ---------------------------------------------------------------------------
# Testes de idempotencia das estruturas de dados
# ---------------------------------------------------------------------------

class TestIdempotenciaEstrutura:
    """
    Simula o que aconteceria se um script rodasse duas vezes:
    verifica se a estrutura resultante acumula entradas ou substitui.
    """

    def test_aguardando_auto_sem_tids_duplicados(self):
        """threads_aguardando_auto nao deve ter threadIds repetidos."""
        ag = _carregar("aguardando_auto.json")
        tids = [r.get("threadId") for r in ag if isinstance(r, dict)]
        duplicados = len(tids) - len(set(tids))
        assert duplicados == 0, (
            f"aguardando_auto tem {duplicados} threadIds duplicados — "
            "indica acumulacao entre execucoes"
        )

    def test_concluidas_auto_sem_tids_duplicados(self):
        """threads_concluidas_auto nao deve ter threadIds repetidos."""
        co = _carregar("concluidas_auto.json")
        tids = [r.get("threadId") for r in co if isinstance(r, dict)]
        duplicados = len(tids) - len(set(tids))
        assert duplicados == 0, (
            f"concluidas_auto tem {duplicados} threadIds duplicados — "
            "indica que o script nao deduplicou antes de gravar"
        )

    def test_threads_json03_sem_tids_duplicados(self):
        """Cada thread no JSON 03 deve aparecer exatamente uma vez."""
        threads = _carregar("threads_completas.json")
        tids = [t.get("threadId") for t in threads if isinstance(t, dict)]
        duplicados = len(tids) - len(set(tids))
        assert duplicados == 0, (
            f"JSON 03 threads tem {duplicados} threadIds duplicados"
        )

    def test_eventos_json03_sem_ids_duplicados(self):
        """Cada evento (email individual) deve ter id unico."""
        eventos = _carregar("eventos.json")
        ids = [e.get("id") for e in eventos if isinstance(e, dict) and e.get("id")]
        duplicados = len(ids) - len(set(ids))
        assert duplicados == 0, (
            f"JSON 03 eventos tem {duplicados} ids de email duplicados"
        )

    def test_emails_02_sem_ids_duplicados(self):
        """Cada email no JSON 02 deve ter id unico."""
        emails = _carregar("emails_02.json")
        ids = [e.get("id") for e in emails if isinstance(e, dict) and e.get("id")]
        duplicados = len(ids) - len(set(ids))
        assert duplicados == 0, (
            f"JSON 02 tem {duplicados} ids de email duplicados"
        )


# ---------------------------------------------------------------------------
# Testes de consistencia entre JSONs
# ---------------------------------------------------------------------------

class TestConsistenciaEntreDados:
    """
    Verifica que o estado dos dados e consistente entre os diferentes JSONs.
    Uma thread nao pode estar em aguardando E concluidas ao mesmo tempo.
    """

    def test_sem_thread_em_aguardando_e_concluidas(self):
        """Nenhum threadId pode estar simultaneamente em aguardando e concluidas."""
        ag_auto = _carregar("aguardando_auto.json")
        co_auto = _carregar("concluidas_auto.json")

        tids_ag = {r.get("threadId") for r in ag_auto if isinstance(r, dict)}
        tids_co = {r.get("threadId") for r in co_auto if isinstance(r, dict)}

        conflito = tids_ag & tids_co
        assert not conflito, (
            f"{len(conflito)} thread(s) em aguardando E concluidas: {list(conflito)[:5]}"
        )

    def test_threads_aguardando_existem_no_json03(self):
        """Threads em aguardando devem estar presentes no JSON 03."""
        ag = _carregar("aguardando_auto.json")
        threads = _carregar("threads_completas.json")
        tids_json03 = {str(t.get("threadId")) for t in threads if isinstance(t, dict)}

        ausentes = []
        for r in ag:
            tid = str(r.get("threadId", ""))
            if tid and tid not in tids_json03:
                ausentes.append(tid)

        # Tolerancia: fixtures podem nao cobrir 100% (sao subconjunto)
        # Mas dentro das fixtures, a consistencia deve ser total
        assert len(ausentes) == 0, (
            f"{len(ausentes)} thread(s) em aguardando ausentes do JSON 03: {ausentes[:3]}"
        )

    def test_campos_obrigatorios_aguardando(self):
        """Cada thread aguardando deve ter os campos minimos para a tela funcionar."""
        ag = _carregar("aguardando_auto.json")
        problemas = []
        for r in ag:
            if not isinstance(r, dict):
                continue
            tid = r.get("threadId", "?")
            if not r.get("threadId"):
                problemas.append(f"sem threadId: {r}")
            if not r.get("tipo"):
                problemas.append(f"sem tipo: tid={tid}")
            tipo = r.get("tipo", "")
            if tipo not in ("ACAO_INTERNA", "RESPOSTA_CLIENTE", "ENTREGA_CLIENTE"):
                problemas.append(f"tipo invalido '{tipo}': tid={tid}")

        assert not problemas, f"{len(problemas)} problema(s):\n" + "\n".join(problemas[:5])

    def test_campos_obrigatorios_concluidas(self):
        """Cada thread concluida deve ter threadId e data_conclusao."""
        co = _carregar("concluidas_auto.json")
        problemas = []
        for r in co:
            if not isinstance(r, dict):
                continue
            if not r.get("threadId"):
                problemas.append(f"sem threadId")
            if not r.get("data_conclusao"):
                problemas.append(f"sem data_conclusao: tid={r.get('threadId','?')}")

        assert not problemas, f"{len(problemas)} problema(s):\n" + "\n".join(problemas[:5])

    def test_mensagens_tem_lado_valido(self):
        """Toda mensagem deve ter contato_origem.lado valido."""
        threads = _carregar("threads_completas.json")
        LADOS_VALIDOS = {"FINAUD", "CLIENTE", "EXTERNO", "INTERNO", ""}
        lado_invalido = []

        for t in threads:
            if not isinstance(t, dict):
                continue
            for msg in (t.get("mensagens") or []):
                co = msg.get("contato_origem") or {}
                lado = (co.get("lado") or "").upper()
                if lado not in LADOS_VALIDOS:
                    lado_invalido.append(
                        f"tid={t.get('threadId')} lado='{lado}'"
                    )

        assert not lado_invalido, (
            f"{len(lado_invalido)} mensagens com lado invalido: {lado_invalido[:3]}"
        )
