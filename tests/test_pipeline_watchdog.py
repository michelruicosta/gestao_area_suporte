# -*- coding: utf-8 -*-
"""
Testes para scripts/pipeline_watchdog.py

Cobre o comportamento de cancelamento automático do watchdog anterior
quando um novo é iniciado (proteção contra timer acumulado entre scripts).
"""
import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pipeline_watchdog


def _resetar_estado_global():
    """Limpa o evento global entre testes para isolar o estado."""
    pipeline_watchdog._evento_parar_atual = None


def test_watchdog_cancela_anterior():
    """
    Quando um segundo watchdog é iniciado, o evento do primeiro deve ser sinalizado
    (parado). Garante que timers curtos não matem o processo durante scripts posteriores.
    """
    _resetar_estado_global()

    pipeline_watchdog.iniciar_watchdog(max_horas=1, nome_script="script_A")
    evento_a = pipeline_watchdog._evento_parar_atual
    assert evento_a is not None
    assert not evento_a.is_set(), "evento do script_A não deve estar sinalizado ainda"

    pipeline_watchdog.iniciar_watchdog(max_horas=2, nome_script="script_B")
    evento_b = pipeline_watchdog._evento_parar_atual

    assert evento_a.is_set(), "evento do script_A deve ter sido sinalizado ao iniciar script_B"
    assert not evento_b.is_set(), "evento do script_B não deve estar sinalizado"
    assert evento_a is not evento_b, "cada watchdog deve ter seu próprio evento"


def test_watchdog_thread_para_quando_cancelada():
    """
    A thread do watchdog deve encerrar dentro de 2 segundos quando seu evento é sinalizado.
    """
    _resetar_estado_global()

    pipeline_watchdog.iniciar_watchdog(max_horas=1, nome_script="script_cancel")
    evento = pipeline_watchdog._evento_parar_atual
    thread_nome = "watchdog-script_cancel"

    threads_antes = {t.name for t in threading.enumerate()}
    assert thread_nome in threads_antes

    evento.set()
    time.sleep(0.1)  # dá tempo para a thread acordar e encerrar

    threads_depois = {t.name for t in threading.enumerate()}
    assert thread_nome not in threads_depois, "thread do watchdog deve ter encerrado após evento.set()"


def test_tres_watchdogs_em_sequencia():
    """
    Simula 3 scripts em sequência: apenas o último evento deve estar ativo.
    """
    _resetar_estado_global()

    pipeline_watchdog.iniciar_watchdog(max_horas=0.5, nome_script="s04")
    ev4 = pipeline_watchdog._evento_parar_atual

    pipeline_watchdog.iniciar_watchdog(max_horas=12, nome_script="s05")
    ev5 = pipeline_watchdog._evento_parar_atual

    pipeline_watchdog.iniciar_watchdog(max_horas=1, nome_script="s13")
    ev13 = pipeline_watchdog._evento_parar_atual

    assert ev4.is_set(), "s04 deve estar cancelado"
    assert ev5.is_set(), "s05 deve estar cancelado"
    assert not ev13.is_set(), "s13 (último) deve estar ativo"
