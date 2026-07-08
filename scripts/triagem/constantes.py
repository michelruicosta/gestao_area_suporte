# -*- coding: utf-8 -*-
"""
Constantes compartilhadas das triagens automáticas.

Cada categoria tem seu próprio conjunto de CADOC. Os módulos em
``scripts/triagem/<categoria>.py`` consomem estas constantes; os scripts
standalone (``scripts/triagem_auto_<categoria>.py``) importam daqui ou via
``triagem_auto_ddr4111`` (re-export para retrocompatibilidade).
"""
from __future__ import annotations


# CADOCs por triagem ----------------------------------------------------------
# Supervisores separados (DDR, 4111, DRL são independentes desde 2026-07-08)
CADOC_TRIAGEM_DDR   = frozenset({"DDR_2011"})
CADOC_TRIAGEM_4111  = frozenset({"4111"})
CADOC_TRIAGEM_DRL   = frozenset({"DRL_2160"})
# Conjunto combinado mantido para retrocompat (testes, motor legado)
CADOC_TRIAGEM_DDR4111 = CADOC_TRIAGEM_DDR | CADOC_TRIAGEM_4111 | CADOC_TRIAGEM_DRL
CADOC_TRIAGEM_DLI = frozenset({"DLI_2062"})
CADOC_TRIAGEM_DLO = frozenset({"DLO_2061"})
CADOC_TRIAGEM_RETORNO_BACEN = frozenset({"RETORNO_BACEN"})
CADOC_TRIAGEM_S5 = frozenset({"S5"})
# Passo 6 do refactor: SUPORTE/DRSAC/FORCAPITAL agora são triagens separadas.
CADOC_TRIAGEM_SUPORTE = frozenset({"SUPORTE"})
CADOC_TRIAGEM_DRSAC = frozenset({"DRSAC"})
CADOC_TRIAGEM_FORCAPITAL = frozenset({"FORCAPITAL"})
CADOC_TRIAGEM_DRM = frozenset({"DRM_2060"})
CADOC_TRIAGEM_6209 = frozenset({"6209"})

# Categorias internas/automáticas — fecham como Concluído assim que chegam.
CADOC_TRIAGEM_RISK_DRIVER_ALERTA    = frozenset({"RISK_DRIVER_ALERTA"})
CADOC_TRIAGEM_RISK_DRIVER_RELATORIO = frozenset({"RISK_DRIVER_RELATORIO"})
CADOC_TRIAGEM_RISK_DRIVER_RESP_AUTO = frozenset({"RISK_DRIVER_RESP_AUTO"})
CADOC_TRIAGEM_FOGBUGZ               = frozenset({"FOGBUGZ"})
CADOC_TRIAGEM_LEIAUTES_BACEN        = frozenset({"LEIAUTES_BACEN"})

# Retrocompat: alguns lugares ainda referenciam ``CADOC_ALVO``.
CADOC_ALVO = CADOC_TRIAGEM_DDR4111

# CADOCs ignorados em qualquer triagem.
EXCLUIR_CADOC = frozenset({"IGNORADO", "FILTRADO_POR_DATA"})

# Fios tratados só na triagem DLI (operacional); não duplicar DLO (matriz 2026-04-02).
THREAD_IDS_EXCLUIR_TRIAGEM_DLO = frozenset({"GMTHRID_1857677212096008336"})


__all__ = [
    "CADOC_TRIAGEM_DDR",
    "CADOC_TRIAGEM_4111",
    "CADOC_TRIAGEM_DRL",
    "CADOC_TRIAGEM_DDR4111",
    "CADOC_TRIAGEM_DLI",
    "CADOC_TRIAGEM_DLO",
    "CADOC_TRIAGEM_RETORNO_BACEN",
    "CADOC_TRIAGEM_S5",
    "CADOC_TRIAGEM_SUPORTE",
    "CADOC_TRIAGEM_DRSAC",
    "CADOC_TRIAGEM_FORCAPITAL",
    "CADOC_TRIAGEM_DRM",
    "CADOC_TRIAGEM_6209",
    "CADOC_TRIAGEM_RISK_DRIVER_ALERTA",
    "CADOC_TRIAGEM_RISK_DRIVER_RELATORIO",
    "CADOC_TRIAGEM_RISK_DRIVER_RESP_AUTO",
    "CADOC_TRIAGEM_FOGBUGZ",
    "CADOC_TRIAGEM_LEIAUTES_BACEN",
    "CADOC_ALVO",
    "EXCLUIR_CADOC",
    "THREAD_IDS_EXCLUIR_TRIAGEM_DLO",
]
