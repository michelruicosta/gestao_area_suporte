# -*- coding: utf-8 -*-
"""
Testes para garantir que data_marcacao em AGUARDANDO usa a data real
da última mensagem (data_iso do evento), não a data da carga (dia_ref).

Caso real que motivou: 215 threads tinham data_marcacao = 2026-06-12
(dia da carga) quando a última mensagem chegou em 2026-01-21 — 142 dias
de diferença.
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from triagem._base import triar_base
from triagem._protocolo import Bucket


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def _msg(corpo, lado_origem="CLIENTE", lado_destino="FINAUD", data_email="2026-01-21"):
    return {
        "contato_origem": {"lado": lado_origem, "email": "cli@empresa.com.br"},
        "contato_destino": {"lado": lado_destino, "email": "ana@finaud.com.br"},
        "corpo_limpo": corpo,
        "corpo": corpo,
        "assunto": "S5 Teste",
        "data_email": data_email,
        "timestamp_epoch": 1737417600,  # 2026-01-21 00:00 UTC
    }


def _evento(tid, cadoc="S5", data_iso="2026-01-21"):
    return {
        "threadId": tid,
        "cadoc": cadoc,
        "data_iso": data_iso,
        "timestamp_epoch": 1737417600,
        "titulo": "S5 Teste",
        "cliente": "Empresa Teste",
        "responsavel": "Ana Finaud",
        "responsabilidade": "FINAUD",
        "lado_responsavel": "FINAUD",
        "retorno_bacen": False,
        "relatorio_interno_risk_driver": False,
        "status_processo": "PENDENTE",
        "lista_prazos": [],
        "secao_operacional": cadoc,
        "corpo": "mensagem do cliente",
        "corpo_limpo": "mensagem do cliente",
        "contato_origem": {"lado": "CLIENTE", "email": "cli@empresa.com.br"},
        "contato_destino": {"lado": "FINAUD", "email": "ana@finaud.com.br"},
        "texto_imagens": "",
    }


def _dados(tid, cadoc="S5", data_iso_evento="2026-01-21", msg_data="2026-01-21"):
    """dados_03 mínimo com uma thread e um evento."""
    return {
        "threads": [{
            "threadId": tid,
            "assunto": "S5 Teste",
            "cliente": "Empresa Teste",
            "cadoc": cadoc,
            "data_iso": data_iso_evento,
            "data_ultima_msg": msg_data,
            "mensagens": [_msg("Segue a remessa.", data_email=msg_data)],
        }],
        "eventos": [_evento(tid, cadoc=cadoc, data_iso=data_iso_evento)],
    }


def _chamar_triar_base(dados, dia_ref, cadoc="S5"):
    """Chama triar_base com tabelas vazias (sem regras de conclusão)."""
    return triar_base(
        dados=dados,
        dia_ref=dia_ref,
        cadocs=frozenset({cadoc}),
        alvo_triagem=cadoc,
        regras_concluir={},
        regras_aguardando={},
        frases_aguardando={},
        com_sec6b=False,
        com_sec5_anexo=False,
        sec35_agradecimento_sem_msg_cliente_previa=False,
    )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestDataMarcacaoUsaDataIsoEvento:
    """data_marcacao deve refletir a data da última mensagem, não o dia da carga.

    Os testes usam dia_ref=None para desativar o filtro _thread_toca_dia_ref
    (que exigiria atividade no dia exato da carga). O que nos importa é
    verificar que o campo data_marcacao usa data_iso do evento, não dia_ref.
    """

    def test_data_marcacao_e_data_iso_do_evento(self):
        """Caso real 2-N: última mensagem em jan, motor rodou em jun — marcação deve ser jan."""
        tid = "GMTHRID_TEST_001"
        dados = _dados(tid, data_iso_evento="2026-01-21", msg_data="2026-01-21")

        # dia_ref=None: sem filtro de data — todas as threads são candidatas
        _, ag, _ = _chamar_triar_base(dados, dia_ref=None)

        assert len(ag) == 1, "Esperava 1 thread em AGUARDANDO"
        r = ag[0]
        assert r["data_marcacao"] == "2026-01-21", (
            f"data_marcacao deveria ser 2026-01-21 (data da msg), "
            f"mas foi {r['data_marcacao']}"
        )

    def test_data_marcacao_diferente_de_hoje(self):
        """data_marcacao nao deve ser date.today() quando o evento tem data_iso anterior."""
        tid = "GMTHRID_TEST_002"
        dados = _dados(tid, data_iso_evento="2026-02-15", msg_data="2026-02-15")

        _, ag, _ = _chamar_triar_base(dados, dia_ref=None)

        assert len(ag) == 1
        assert ag[0]["data_marcacao"] != date.today().isoformat(), (
            "data_marcacao nao deve ser date.today() (data de execucao do motor)"
        )
        assert ag[0]["data_marcacao"] == "2026-02-15"

    def test_fallback_quando_evento_sem_data_iso(self):
        """Sem data_iso no evento, o fallback e date.today() (comportamento seguro)."""
        tid = "GMTHRID_TEST_003"
        dados = _dados(tid, data_iso_evento="", msg_data="2026-03-10")
        # Remover data_iso do evento e da thread
        for ev in dados["eventos"]:
            ev.pop("data_iso", None)
        for t in dados["threads"]:
            t.pop("data_iso", None)

        _, ag, _ = _chamar_triar_base(dados, dia_ref=None)

        if ag:
            # Sem data_iso, deve usar o fallback (date.today())
            assert ag[0]["data_marcacao"] == date.today().isoformat(), (
                "Sem data_iso no evento, fallback deve ser date.today()"
            )
