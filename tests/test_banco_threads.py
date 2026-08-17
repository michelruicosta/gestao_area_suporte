"""
test_banco_threads.py
Testes para a lógica de determinação de status de workflow em scripts/banco_threads.py.
Cobre §8.1 (Aguardando Finaud), §8.2 (Aguardando Cliente) e §8.3 (Concluída) da spec.
"""
from __future__ import annotations

import os
import sys

import pytest

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import banco_threads as bt


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msg(
    remetente: str,
    corpo: str = '',
    assunto: str = '',
    nomes_anexos: list | None = None,
) -> dict:
    return {
        'remetente': remetente,
        'corpo_texto': corpo,
        'assunto': assunto,
        'nomes_anexos': nomes_anexos or [],
    }


FINAUD  = 'Monica <monica@finaud.com.br>'
CLIENTE = 'João <joao@bancox.com.br>'


# ── _extrair_texto_novo ───────────────────────────────────────────────────────

def test_extrair_sem_historico():
    assert bt._extrair_texto_novo('texto simples') == 'texto simples'


def test_extrair_remove_linhas_citadas():
    corpo = 'Obrigado.\n> Segue o arquivo.\n> Att, Finaud'
    resultado = bt._extrair_texto_novo(corpo)
    assert '>' not in resultado
    assert 'Obrigado' in resultado


def test_extrair_corta_no_separador_tracos():
    corpo = 'Ok, recebido.\n---\nTexto do histórico antigo'
    resultado = bt._extrair_texto_novo(corpo)
    assert 'Ok, recebido' in resultado
    assert 'histórico' not in resultado


def test_extrair_corta_no_separador_on_wrote():
    corpo = 'Confirmado.\nOn Mon, 17 Aug 2026 wrote:\n> mensagem antiga'
    resultado = bt._extrair_texto_novo(corpo)
    assert 'Confirmado' in resultado
    assert 'mensagem antiga' not in resultado


def test_extrair_corpo_vazio():
    assert bt._extrair_texto_novo('') == ''


# ── _determinar_status — lista vazia ─────────────────────────────────────────

def test_status_sem_mensagens():
    assert bt._determinar_status([]) == 'Aguardando Finaud'


# ── _determinar_status — regra especial "transmitido no BACEN" ───────────────

def test_status_transmitido_bacen_pelo_cliente():
    """Cliente avisa transmissão ao BACEN → Concluída (regra especial §8.3)."""
    msgs = [_msg(CLIENTE, corpo='Transmitido no BACEN com sucesso.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_transmitida_bacen_variacao():
    """Variação 'transmitida no BACEN' também encerra."""
    msgs = [_msg(FINAUD, corpo='Arquivo transmitida no BACEN hoje.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_transmitido_bacen_no_historico_nao_conta():
    """'transmitido no BACEN' só no histórico citado (linha >) → NÃO encerra."""
    corpo = 'Preciso do relatório atualizado.\n> Transmitido no BACEN em agosto.'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    assert bt._determinar_status(msgs) == 'Aguardando Finaud'


# ── _determinar_status — remetente Finaud ─────────────────────────────────────

def test_status_finaud_res_no_assunto():
    """'RES:' no assunto com remetente Finaud → Concluída."""
    msgs = [_msg(FINAUD, assunto='RES: DDR_2011 Banco X')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_finaud_com_anexo():
    """Finaud envia mensagem com anexo → Concluída."""
    msgs = [_msg(FINAUD, nomes_anexos=['DDR_2011_20260817.zip'])]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_finaud_frase_segue_em_anexo():
    """Finaud usa 'segue em anexo' no texto → Concluída."""
    msgs = [_msg(FINAUD, corpo='Conforme combinado, segue em anexo o relatório.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_finaud_conforme_solicitado():
    """Finaud usa 'conforme solicitado' → Concluída."""
    msgs = [_msg(FINAUD, corpo='Conforme solicitado, segue o DDR atualizado.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_finaud_procedemos_com():
    """Finaud usa 'procedemos com' → Concluída."""
    msgs = [_msg(FINAUD, corpo='Procedemos com o envio ao BACEN.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_finaud_sem_sinal_encerramento():
    """Finaud respondeu mas sem sinal de encerramento → Aguardando Cliente."""
    msgs = [_msg(FINAUD, corpo='Verificamos aqui, precisamos de mais informações.')]
    assert bt._determinar_status(msgs) == 'Aguardando Cliente'


def test_status_finaud_res_minusculo():
    """'RES:' case-insensitive."""
    msgs = [_msg(FINAUD, assunto='res: DDR_2011 Banco X')]
    assert bt._determinar_status(msgs) == 'Concluída'


# ── _determinar_status — remetente cliente ────────────────────────────────────

def test_status_cliente_so_obrigado():
    """Cliente só disse 'obrigado' → Concluída."""
    msgs = [_msg(CLIENTE, corpo='Obrigado!')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_cliente_ok_recebido():
    """Cliente disse 'ok, recebido' → Concluída."""
    msgs = [_msg(CLIENTE, corpo='Ok, recebido.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_cliente_de_acordo():
    """Cliente disse 'de acordo' → Concluída."""
    msgs = [_msg(CLIENTE, corpo='De acordo, obrigado.')]
    assert bt._determinar_status(msgs) == 'Concluída'


def test_status_cliente_conteudo_real():
    """Cliente mandou conteúdo real (sem pergunta) → Aguardando Finaud."""
    msgs = [_msg(CLIENTE, corpo='Segue os dados para análise.')]
    assert bt._determinar_status(msgs) == 'Aguardando Finaud'


def test_status_veto_obrigado_com_pergunta():
    """Agradecimento + pergunta no mesmo e-mail → Aguardando Finaud (veto §8.3)."""
    msgs = [_msg(CLIENTE, corpo='Obrigado! Mas quando chegará o arquivo de setembro?')]
    assert bt._determinar_status(msgs) == 'Aguardando Finaud'


def test_status_cliente_so_pergunta():
    """Cliente fez apenas uma pergunta → Aguardando Finaud."""
    msgs = [_msg(CLIENTE, corpo='Boa tarde, quando será enviado o arquivo?')]
    assert bt._determinar_status(msgs) == 'Aguardando Finaud'


# ── _determinar_status — reabertura de caso (§8.4) ───────────────────────────

def test_status_reabertura_apos_concluida():
    """Thread 'concluída' → cliente manda conteúdo real → volta para Aguardando Finaud."""
    msgs = [
        _msg(FINAUD, corpo='Segue em anexo o DDR.', nomes_anexos=['DDR.zip']),
        _msg(CLIENTE, corpo='Obrigado!'),
        _msg(CLIENTE, corpo='Preciso do arquivo atualizado com os dados de agosto.'),
    ]
    assert bt._determinar_status(msgs) == 'Aguardando Finaud'


def test_status_reabertura_so_ultimo_e_mail_importa():
    """A função olha SÓ o último e-mail, não o histórico."""
    msgs = [
        _msg(CLIENTE, corpo='Segue os dados solicitados.'),
        _msg(FINAUD, corpo='Segue em anexo.', nomes_anexos=['arquivo.zip']),
    ]
    # Último é da Finaud com anexo → Concluída
    assert bt._determinar_status(msgs) == 'Concluída'
