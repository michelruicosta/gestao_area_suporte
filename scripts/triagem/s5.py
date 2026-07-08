# -*- coding: utf-8 -*-
"""
Triagem automática — categoria **S5**.

Apenas eventos com ``cadoc == "S5"``. Skeleton igual ao DLO:
  - com §6b (espelho núcleo-assunto);
  - com §3.5+ (F→C "obrigada" sem remessa mesmo sem C→F prévio);
  - sem regra F→C substantiva.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from triagem._protocolo import Bucket, Contexto, Regra, TabelaConcluir, TabelaAguardando
from triagem.helpers import (
    _assunto_representativo_evento,
    _cliente_agradecimento_apos_remessa_finaud,
    _cliente_reconhecimento_curto_com_historico_finaud,
    _cliente_somente_reconhecimento_curto_pos_remessa,
    _empresa_chave,
    _finaud_agradecimento_curto_sem_remessa,
    _finaud_finaud_agradecimento_relatorio,
    _finaud_finaud_conclusivo,
    _finaud_pedido_insumos_a_cliente,
    _finaud_somente_reconhecimento_curto,
    _fp_prazos,
    _get_ultima_mensagem,
    _nucleo_assunto_ddr,
    _par_conclusivo,
    _sec5_remessa_finaud,
    _sec5b_res_finaud_cliente,
    _sec5c_finaud_corpo_conclusivo,
    _texto_fio,
    _thread_vista_ate_data_ref,
    _transmitido_bacen,
    _ultima_e_cliente_para_finaud,
    _ultima_mensagem_finaud_para_cliente,
)


NOME = "S5"
CADOCS = frozenset({"S5"})
AGUARDA_ULTIMA_FINAUD_FINAUD = True
ESPELHO_NUCLEO_ASSUNTO = True
SEC35_SEM_MSG_CLIENTE_PREVIA = True


def _det_transmitido_bacen(ctx: Contexto) -> bool:
    return _transmitido_bacen(ctx.texto_fio)


def _veto_sec5_ult_cf_substantiva(ctx: Contexto) -> bool:
    ult = ctx.ultima_msg
    return bool(
        ult
        and _ultima_e_cliente_para_finaud(ult)
        and not _cliente_somente_reconhecimento_curto_pos_remessa(ult)
    )


def _det_sec5_remessa(ctx: Contexto) -> bool:
    ufc = _ultima_mensagem_finaud_para_cliente(ctx.thread)
    if not _sec5_remessa_finaud(ufc):
        return False
    return not _veto_sec5_ult_cf_substantiva(ctx)


def _det_sec5b_res(ctx: Contexto) -> bool:
    ufc = _ultima_mensagem_finaud_para_cliente(ctx.thread)
    if not _sec5b_res_finaud_cliente(ufc):
        return False
    if _det_sec5_remessa(ctx):
        return False
    return not _veto_sec5_ult_cf_substantiva(ctx)


def _det_sec5c_corpo_conclusivo(ctx: Contexto) -> bool:
    ufc = _ultima_mensagem_finaud_para_cliente(ctx.thread)
    if not _sec5c_finaud_corpo_conclusivo(ufc):
        return False
    if _det_sec5_remessa(ctx) or _det_sec5b_res(ctx):
        return False
    return not _veto_sec5_ult_cf_substantiva(ctx)


def _det_4d_cliente_agradece_pos_remessa(ctx: Contexto) -> bool:
    return _cliente_agradecimento_apos_remessa_finaud(ctx.thread, ctx.ultima_msg or {})


def _det_4e_s5(ctx: Contexto) -> bool:
    return _cliente_reconhecimento_curto_com_historico_finaud(ctx.thread, ctx.ultima_msg or {})


def _det_3inv_pedido_insumos_finaud(ctx: Contexto) -> bool:
    return _finaud_pedido_insumos_a_cliente(ctx.ultima_msg or {})


def _det_35_reconhecimento_curto(ctx: Contexto) -> bool:
    return _finaud_somente_reconhecimento_curto(ctx.ultima_msg or {}, ctx.thread)


def _det_35_plus_agradece_sem_cliente_previa(ctx: Contexto) -> bool:
    return _finaud_agradecimento_curto_sem_remessa(ctx.ultima_msg or {})


def _det_ff_encaminhamento(ctx: Contexto) -> bool:
    return True


def _det_3_insumo_cliente(ctx: Contexto) -> bool:
    return True


def _det_g3_par_conclusivo(ctx: Contexto) -> bool:
    """G3: cliente concorda ('de acordo', 'ok', etc.) após instrução da Finaud."""
    return _par_conclusivo(ctx.thread, ctx.ultima_msg or {})


REGRAS_CONCLUIR: TabelaConcluir = {
    "globais": [
        Regra(1, "Texto transmitido no BACEN", _det_transmitido_bacen,
              motivo="§3.1 transmitido no BACEN"),
        Regra(2, "Remessa Finaud → cliente", _det_sec5_remessa,
              motivo="§5 remessa Finaud → cliente"),
        Regra(3, "RES: Finaud → cliente", _det_sec5b_res,
              motivo="§5b RES Finaud → cliente"),
        Regra(4, "Texto conclusivo Finaud → cliente", _det_sec5c_corpo_conclusivo,
              motivo="§5c texto conclusivo Finaud → cliente"),
    ],
    "ultima_cliente_para_finaud": [
        Regra(1, "Cliente agradece após remessa Finaud → cliente",
              _det_4d_cliente_agradece_pos_remessa,
              motivo="§4d cliente agradece após remessa Finaud → cliente"),
        Regra(2, "§4e S5: agradecimento sem novo pedido",
              _det_4e_s5,
              motivo="S5 §4e: agradecimento sem novo pedido no texto"),
        Regra(3, "G3: cliente confirma concordância após instrução Finaud",
              _det_g3_par_conclusivo,
              motivo="S5 G3: cliente disse 'de acordo' após instrução da Finaud — penúltima é Finaud"),
    ],
}


REGRAS_AGUARDANDO: TabelaAguardando = {
    "ultima_finaud_para_cliente": [
        Regra(1, "Finaud pediu insumos ao cliente",
              _det_3inv_pedido_insumos_finaud, fila="entrega_cliente",
              motivo="§3-inv pedido Finaud"),
        Regra(2, "Finaud só reconheceu (C→F prévio existe)",
              _det_35_reconhecimento_curto, fila="finaud",
              motivo="§3.5 reconhecimento sem remessa"),
        Regra(3, "S5 §3.5+: Finaud só agradece (sem C→F prévio)",
              _det_35_plus_agradece_sem_cliente_previa, fila="finaud",
              motivo="S5 §3.5 — agradecimento sem remessa, sem C→F prévio"),
    ],
    "ultima_finaud_interna": [
        Regra(1, "Encaminhamento interno Finaud → Finaud",
              _det_ff_encaminhamento, fila="finaud",
              motivo="última mensagem Finaud→Finaud"),
    ],
    "ultima_cliente_para_finaud": [
        Regra(1, "Insumo do cliente — aguarda processamento Finaud",
              _det_3_insumo_cliente, fila="finaud",
              motivo="§3 última mensagem CLIENTE"),
    ],
}


_FRASES_AGUARDANDO: Dict[Tuple[Bucket, int], str] = {
    ("ultima_finaud_para_cliente", 1):
        "Triagem automática: Finaud solicitou insumos ao cliente — aguarda envio (§3-inv).",
    ("ultima_finaud_para_cliente", 2):
        "Triagem automática: Finaud reconheceu recebimento — aguarda envio da remessa (§3.5).",
    ("ultima_finaud_para_cliente", 3):
        "Triagem automática (S5): Finaud só agradece — aguarda envio de arquivo ao cliente.",
    ("ultima_finaud_interna", 1):
        "Triagem automática: última mensagem interna Finaud→Finaud — aguarda tratamento (S5).",
    ("ultima_cliente_para_finaud", 1):
        "Triagem automática: insumo do cliente — aguarda processamento Finaud (§3).",
}


def triar(
    dados: dict,
    dia_ref: Optional[date],
    cadocs: FrozenSet[str] = CADOCS,
    com_sec6b: bool = True,
    alvo_triagem: str = "S5",
    excluir_thread_ids: Optional[FrozenSet[str]] = None,
    aguardar_ultima_finaud_finaud: bool = AGUARDA_ULTIMA_FINAUD_FINAUD,
    sec35_agradecimento_sem_msg_cliente_previa: bool = SEC35_SEM_MSG_CLIENTE_PREVIA,
    incluir_relatorio_risk_driver: bool = False,
) -> Tuple[List[dict], List[dict], List[str]]:
    from triagem._base import triar_base
    return triar_base(
        dados=dados,
        dia_ref=dia_ref,
        cadocs=cadocs,
        alvo_triagem=alvo_triagem,
        regras_concluir=REGRAS_CONCLUIR,
        regras_aguardando=REGRAS_AGUARDANDO,
        frases_aguardando=_FRASES_AGUARDANDO,
        com_sec6b=com_sec6b,
        com_sec5_anexo=True,
        excluir_thread_ids=excluir_thread_ids,
        sec35_agradecimento_sem_msg_cliente_previa=sec35_agradecimento_sem_msg_cliente_previa,
        incluir_relatorio_risk_driver=incluir_relatorio_risk_driver,
    )
