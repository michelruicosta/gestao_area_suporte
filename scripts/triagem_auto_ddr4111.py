# -*- coding: utf-8 -*-
"""
Triagem automática DDR/4111 — grava ``threads_concluidas.json`` /
``threads_aguardando.json``.

Após o refactor (Passos 5–11), este arquivo é um **hub fino**:
  - CLI entry point para a triagem DDR4111 (``run_triagem_ddr4111`` /
    ``main``);
  - **dispatcher** ``triar(...)`` que delega para o módulo da categoria em
    ``scripts/triagem/<alvo>.py``;
  - re-exports de constantes / helpers / runner para manter retrocompat com
    código que ainda importa daqui (testes, painel, integração).

A lógica de cada categoria (regras, tabelas declarativas) vive em
``scripts/triagem/<categoria>.py``. As funções utilitárias estão em
``scripts/triagem/helpers.py`` e ``scripts/triagem/motor.py``.

Uso:
  python scripts/triagem_auto_ddr4111.py --dry-run
  python scripts/triagem_auto_ddr4111.py --apply
  python scripts/triagem_auto_ddr4111.py --apply --data-ref 2026-02-23

Variáveis de ambiente (``executar_tudo``): ``TRIAGEM_AUTO_DDR4111=1`` liga
9c–9h (DDR, DLI, DLO, S5, SUPORTE). DRSAC / FORCAPITAL ligam com
``TRIAGEM_AUTO_DRSAC=1`` / ``TRIAGEM_AUTO_FORCAPITAL=1``. Retorno Bacen exige
``TRIAGEM_AUTO_RETORNO_BACEN=1`` explícito.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import FrozenSet, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(BASE_DIR, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


# ---------------------------------------------------------------------------
# Re-exports para retrocompat (testes, scripts standalone, integração).
# Toda a lógica viva está em ``scripts/triagem/``.
# ---------------------------------------------------------------------------
from triagem.constantes import (  # noqa: E402,F401
    CADOC_ALVO,
    CADOC_TRIAGEM_DDR,
    CADOC_TRIAGEM_4111,
    CADOC_TRIAGEM_DRL,
    CADOC_TRIAGEM_DDR4111,
    CADOC_TRIAGEM_DLI,
    CADOC_TRIAGEM_DLO,
    CADOC_TRIAGEM_DRSAC,
    CADOC_TRIAGEM_FORCAPITAL,
    CADOC_TRIAGEM_RETORNO_BACEN,
    CADOC_TRIAGEM_S5,
    CADOC_TRIAGEM_SUPORTE,
    EXCLUIR_CADOC,
    THREAD_IDS_EXCLUIR_TRIAGEM_DLO,
)
from triagem.helpers import (  # noqa: E402,F401
    _cliente_agradecimento_apos_remessa_finaud,
    _finaud_pedido_insumos_a_cliente,
    _nucleo_assunto_ddr,
    _sec5_remessa_finaud,
    _sec5c_finaud_corpo_conclusivo,
)
from triagem.motor import (  # noqa: E402,F401
    _registro_concluido_auto,
    _run_triagem_cadocs,
    _strip_auto_para_tids,
    _tids_sem_reprocessar_triagem_fecho_anterior,
)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
def triar(
    dados: dict,
    dia_ref: Optional[date],
    cadocs: FrozenSet[str] = CADOC_TRIAGEM_DDR4111,
    com_sec6b: bool = True,
    alvo_triagem: str = "DDR4111",
    excluir_thread_ids: Optional[FrozenSet[str]] = None,
    aguardar_ultima_finaud_finaud: bool = False,
    sec35_agradecimento_sem_msg_cliente_previa: bool = False,
    incluir_relatorio_risk_driver: bool = False,
) -> Tuple[List[dict], List[dict], List[str]]:
    """Dispatcher: delega para o módulo da categoria correspondente.

    Cada alvo conhecido tem implementação dedicada em ``triagem/<alvo>.py``.
    Saída byte-idêntica ao legado garantida via ``motivo_legado`` nas tabelas.
    Retorna ``(novos_concluidos, novos_aguardando, linhas_log)``.
    """
    kwargs = dict(
        cadocs=cadocs,
        com_sec6b=com_sec6b,
        alvo_triagem=alvo_triagem,
        excluir_thread_ids=excluir_thread_ids,
        aguardar_ultima_finaud_finaud=aguardar_ultima_finaud_finaud,
        sec35_agradecimento_sem_msg_cliente_previa=sec35_agradecimento_sem_msg_cliente_previa,
        incluir_relatorio_risk_driver=incluir_relatorio_risk_driver,
    )

    if alvo_triagem == "RETORNO_BACEN":
        from triagem import retorno_bacen as _cat
    elif alvo_triagem == "DDR4111":
        from triagem import ddr4111 as _cat  # retrocompat — mantido enquanto há registros legados
    elif alvo_triagem == "DDR":
        from triagem import ddr as _cat
    elif alvo_triagem == "4111":
        from triagem import cadoc4111 as _cat
    elif alvo_triagem == "DRL":
        from triagem import drl as _cat
    elif alvo_triagem == "S5":
        from triagem import s5 as _cat
    elif alvo_triagem == "DLI":
        from triagem import dli as _cat
    elif alvo_triagem == "DLO":
        from triagem import dlo as _cat
    elif alvo_triagem == "SUPORTE":
        from triagem import suporte as _cat
    elif alvo_triagem == "DRSAC":
        from triagem import drsac as _cat
    elif alvo_triagem == "FORCAPITAL":
        from triagem import forcapital as _cat
    elif alvo_triagem == "DRM_2060":
        from triagem import drm as _cat
    elif alvo_triagem == "6209":
        from triagem import cadoc6209 as _cat
    else:
        raise ValueError(
            f"alvo_triagem={alvo_triagem!r} não tem módulo de triagem dedicado em "
            f"scripts/triagem/. Adicione um novo módulo (cf. triagem/retorno_bacen.py) "
            f"e registre o dispatch acima."
        )
    return _cat.triar(dados, dia_ref, **kwargs)


# ---------------------------------------------------------------------------
# CLI entry point — DDR4111
# ---------------------------------------------------------------------------
def run_triagem_ddr4111(apply: bool, data_ref: Optional[str] = None) -> int:
    """Chamada programática (ex.: ``executar_tudo`` com ``TRIAGEM_AUTO_DDR4111=1``).

    Executa DDR_2011, 4111 e DRL_2160 em passes separados (supervisores independentes).
    """
    rc = 0
    for cadocs, alvo in [
        (CADOC_TRIAGEM_DDR,  "DDR"),
        (CADOC_TRIAGEM_4111, "4111"),
        (CADOC_TRIAGEM_DRL,  "DRL"),
    ]:
        rc |= _run_triagem_cadocs(
            apply,
            data_ref,
            cadocs,
            True,
            "triagem_auto_ddr4111",
            alvo,
        )
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Triagem automática DDR/4111 → threads_*.json",
        epilog=(
            "Outros alvos: triagem_auto_dli/dlo/s5/suporte/drsac/forcapital/"
            "retorno_bacen.py. Gravar: --apply."
        ),
    )
    ap.add_argument("--dry-run", action="store_true", help="Só imprime, não grava")
    ap.add_argument("--apply", action="store_true", help="Grava em data/json")
    ap.add_argument(
        "--data-ref",
        default=os.environ.get("TRIAGEM_AUTO_DATA_REF", "").strip() or None,
        metavar="YYYY-MM-DD",
        help="Só threads com actividade neste dia (opcional)",
    )
    args = ap.parse_args()

    if args.apply and args.dry_run:
        print("Use só um de: --dry-run ou --apply")
        return 1
    if not args.apply and not args.dry_run:
        print("Indique --dry-run ou --apply")
        return 1

    return run_triagem_ddr4111(apply=args.apply, data_ref=args.data_ref)


if __name__ == "__main__":
    sys.exit(main())
