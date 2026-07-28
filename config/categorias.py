# Catálogo oficial de categorias do pipeline.
# visivel=True  → aparece nas páginas (triagem + painel de gestão)
# visivel=False → não aparece (altere aqui para mudar, sem tocar no restante do código)
#
# "alvo" = valor que chega do campo alvo_triagem_auto ou cadoc
# "display" = nome que aparece na tela
#
# Para o grupo DDR4111 (2011 / 4111 / 2160), o painel usa o campo `cadoc`
# da thread (já classificado pelo Script 05) em vez do alvo_triagem_auto.

CATEGORIAS: dict[str, dict] = {
    # CADOCs com código numérico — vindos do campo cadoc (Script 05)
    "DDR_2011":              {"display": "2011",                  "visivel": True},
    "4111":                  {"display": "4111",                  "visivel": True},
    "DRL_2160":              {"display": "2160",                  "visivel": True},
    "DLO_2061":              {"display": "2061",                  "visivel": True},
    "DLO":                   {"display": "2061",                  "visivel": True},
    "DLI_2062":              {"display": "2062",                  "visivel": True},
    "DLI":                   {"display": "2062",                  "visivel": True},
    "DRM_2060":              {"display": "2060",                  "visivel": True},
    "DRSAC":                 {"display": "2030",                  "visivel": True},
    # Nome do supervisor genérico — nunca deve chegar aqui após a correção do Fable
    # mas mantido como fallback para não quebrar enquanto o pipeline não for corrigido
    "DDR4111":               {"display": "DDR4111",               "visivel": False},
    # CADOCs com nome descritivo
    "S5":                    {"display": "S5",                    "visivel": True},
    "RETORNO_BACEN":         {"display": "RETORNO_BACEN",         "visivel": False},
    "LEIAUTES_BACEN":        {"display": "LEIAUTES_BACEN",        "visivel": False},
    "SUPORTE":               {"display": "SUPORTE",               "visivel": True},
    "FORCAPITAL":            {"display": "FORCAPITAL",            "visivel": True},
    "6209":                  {"display": "6209",                  "visivel": True},
    # Internos — não aparecem nas páginas
    "FOGBUGZ":               {"display": "FOGBUGZ",               "visivel": False},
    "RISK_DRIVER_ALERTA":    {"display": "RISK_DRIVER_ALERTA",    "visivel": False},
    "RISK_DRIVER_RELATORIO": {"display": "RISK_DRIVER_RELATORIO", "visivel": False},
    "RISK_DRIVER_RESP_AUTO": {"display": "RISK_DRIVER_RESP_AUTO", "visivel": False},
}


def categoria_display(alvo: str, cadoc_raw: str = "") -> tuple[str, bool]:
    """Retorna (nome_display, visivel) para uma thread.

    Para o grupo DDR4111, usa cadoc_raw (campo 'cadoc' da thread no integrador)
    que já tem o valor correto (DDR_2011 / 4111 / DRL_2160).
    """
    chave = cadoc_raw.strip() if (alvo == "DDR4111" and cadoc_raw.strip()) else alvo.strip()
    cfg = CATEGORIAS.get(chave)
    if cfg:
        return cfg["display"], cfg["visivel"]
    return chave, True  # desconhecido → mostra como está, visível
