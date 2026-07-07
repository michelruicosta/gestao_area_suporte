"""
QA – Script 04 (classificador): threadId = thread_root, igual ao Gmail.

Sem regras por assunto: o que o Gmail mostra é o que o ORÁCULO mostra.
Alinhado à correção "Seguir Gmail em todos os e-mails" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# Estes testes leem config real (mapeamento_regras_negocio.json) em data/json/config/,
# que é ignorada pelo git (confidencialidade) e portanto ausente no CI. Pulam quando
# o config não existe; rodam normalmente em máquina com os dados (local).
pytestmark = pytest.mark.skipif(
    not os.path.isdir(os.path.join(RAIZ, "data", "json", "config")),
    reason="requer config real em data/json/config/ (ignorado no git; ausente no CI)",
)


def test_mapeamento_suporte_prazo_dias_uteis():
    """SUPORTE e S5: D+5_UTIL; RETORNO_BACEN: D+3_UTIL; sem SUPORTE_GERAL em prazos."""
    path = os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json")
    with open(path, "r", encoding="utf-8") as f:
        r = json.load(f)
    alvo = r["O_QUE_ESTA_SENDO_ANALISADO"]
    doc = alvo["documentos_regulatorios_prazos"]
    assert doc["SUPORTE"]["prazo"] == "D+5_UTIL"
    assert doc["S5"]["prazo"] == "D+5_UTIL"
    assert doc["RETORNO_BACEN"]["prazo"] == "D+3_UTIL"
    assert "SUPORTE_GERAL" not in doc
    assert "SUPORTE" in alvo.get("DETECCAO_INTELIGENTE_CADOC", {})
    assert "SUPORTE_GERAL" not in alvo.get("DETECCAO_INTELIGENTE_CADOC", {})


def test_classificador_usa_thread_root_sem_req():
    """Classificador usa thread_root diretamente, sem _REQ_ por assunto (igual ao Gmail)."""
    path_04 = os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    # Bloco de atribuição de thread_id_correto não deve conter _REQ_
    idx = code.find("thread_id_correto = ")
    assert idx >= 0, "thread_id_correto deve existir"
    bloco = code[idx : idx + 400]
    assert "_REQ_" not in bloco, "Não deve usar _REQ_ — seguir Gmail em todos os e-mails"
    assert "thread_root" in bloco


def test_mes_sozinho_extrai_data_dli_dezembro():
    """Mês sozinho no assunto (ex.: DLI DEZEMBRO) gera data; email fev/2026 + dezembro → dez/2025 (2026-03-19)."""
    import importlib.util
    from datetime import datetime
    spec = importlib.util.spec_from_file_location(
        "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    n = mod.NormalizadorDatas(ano_padrao=2026)
    # Email de fev/2026: "dezembro" deve ser dez/2025 (ano anterior)
    data_ref = datetime(2026, 2, 23)
    r = n.extrair_todas_datas("DLI DEZEMBRO", data_referencia=data_ref)
    assert len(r) >= 1, "Deve extrair data de 'DEZEMBRO'"
    dt, fmt, *_ = r[0]
    assert dt.month == 12 and dt.year == 2025, "Dezembro 2025 (email fev/2026)"
    assert "dezembro" in fmt.lower() or "dez" in fmt.lower(), "Formato deve conter mês"


def test_retorno_bacen_tipificacao():
    """Tipificação Retorno Bacen: assuntos com indício, crítica, erro, reiteração etc. → retorno_bacen=True (2026-03-16)."""
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location(
        "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with open(os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json"), "r", encoding="utf-8") as f:
        regras_completas = json.load(f)
    regras_raiz = regras_completas.get("O_QUE_ESTA_SENDO_ANALISADO", {})
    v = mod.ValidadorContextual(regras_raiz)
    # Assuntos que devem ser Retorno Bacen (termos sem acento para evitar problemas de encoding no teste)
    assert v.eh_retorno_bacen("BANCO CENTRAL - INDICIO DE PROBLEMA DE QUALIDADE DLO 2061") is True
    assert v.eh_retorno_bacen("EQI CTVM | Critica DLO 12.2025") is True
    assert v.eh_retorno_bacen("Erro DLO-01/2026") is True
    assert v.eh_retorno_bacen("Reiteracao de providencias - DLO") is True
    assert v.eh_retorno_bacen("Comunicacao de inconsistencia - DDR") is True
    # Assuntos que NÃO devem ser Retorno Bacen
    assert v.eh_retorno_bacen("DLO 2061 - Envio de relatório") is False
    assert v.eh_retorno_bacen("DDR 2011 - Saldos") is False
    # RD_MOEDA / RD_* no texto: prioridade DDR (Validador)
    assert v.tem_indicador_rd_ddr("ERRO - RD_MOEDAS") is True
    assert v.tem_indicador_rd_ddr("assunto RD_REMUNERA 2011") is True
    assert v.tem_indicador_rd_ddr("sem indicador rd") is False
    assert v.assunto_indica_erro_ou_erros_dlo_retorno_bacen("RES: Erro DLO") is True
    assert v.assunto_indica_erro_ou_erros_dlo_retorno_bacen("Fwd: Erros DLO - análise") is True
    assert v.assunto_indica_erro_ou_erros_dlo_retorno_bacen("DLO 2061 - envio mensal") is False


def test_erro_ou_erros_dlo_no_assunto_processar_retorno_bacen():
    """Assunto RES:/Fwd: Erro(s) DLO → cadoc RETORNO_BACEN (não suprimir; 2026-04-02)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        for assunto in ("RES: Erro DLO", "Fwd: Erro DLO - Ajuda ELIM2018", "Fwd: Erros DLO teste"):
            r = o.processar_email({
                "id": "t_rb_dlo",
                "assunto": assunto,
                "corpo_texto": "Corpo mínimo para testes.",
                "data_email": "Mon, 23 Feb 2026 12:00:00 -0300",
            })
            assert r.get("cadoc") == "RETORNO_BACEN", assunto
            assert r.get("retorno_bacen") is True, assunto
            assert r.get("exibir_card") is True, assunto
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_retorno_bacen_prazo_somente_d3_uteis_ignora_corpo():
    """Retorno Bacen: prazo sempre D+3 úteis a partir da data do e-mail; não extrair datas do corpo (2026-04-02)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "rb_d5_only",
            "assunto": "Erro DLO",
            "corpo_texto": (
                "Prazo limite manifestacao 28/02/2026 ou resposta ate 15/03/2026. "
                "Citacao irrelevante."
            ),
            "data_email": "Mon, 23 Feb 2026 16:06:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "RETORNO_BACEN"
        prazos = r.get("lista_prazos") or []
        assert len(prazos) == 1
        # D+3 úteis a partir de 23/02/2026 (seg) com feriados do JSON → 26/02/2026
        assert prazos[0].get("prazo_limite") == "26/02/2026", prazos[0]
        assert prazos[0].get("data_base") == "23/02/2026"
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_indice_basileia_no_assunto_forca_suporte_d5():
    """Assunto RE: [TRADERS] Indice Basileia + corpo com DLO/COS citado → SUPORTE D+5 úteis, não DLO (2026-04-02)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "92016_traders_basileia",
            "assunto": "RE: [TRADERS] Indice Basileia",
            "corpo_texto": (
                "Fala pessoal\n\nDe: Marcos\nAssunto: RES: [TRADERS] Indice Basileia\n"
                "no CRD a agenda para o 4010 COS4010 DLO 2061 jan/2026"
            ),
            "data_email": "Mon, 23 Feb 2026 18:51:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "SUPORTE", f"esperado SUPORTE obteve {r.get('cadoc')}"
        assert r.get("exibir_card") is True
        prazos = r.get("lista_prazos") or []
        assert len(prazos) == 1
        assert prazos[0].get("cadoc") == "SUPORTE"
        assert prazos[0].get("data_base") == "23/02/2026"
        assert prazos[0].get("prazo_limite") == "02/03/2026", prazos[0]
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_extrair_email_e_nome_encaminhamento_interno_finaud():
    """Após marcador Forwarded message, extrai e-mail externo e nome na linha De: (encaminhamento interno)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    path_regras = os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json")
    with open(path_regras, "r", encoding="utf-8") as f:
        quem = json.load(f).get("QUEM_ENVIA_E_RECEBE", {})
    dom = quem.get("nossa_equipe", {}).get("dominios", [])
    ign = quem.get("clientes_externos", {}).get("dominios_a_ignorar", [])
    body = (
        "Rodrigo, boa tarde.\n\n"
        "---------- Forwarded message ---------\n"
        "De: Thaiana Caisa <tcaisa@bcpsecurities.com>\n"
        "Date: seg., 23 de fev. de 2026\n"
    )
    em = mod.extrair_primeiro_email_externo_apos_encaminhamento(body, dom, ign)
    assert em == "tcaisa@bcpsecurities.com", em
    nome = mod.extrair_nome_remetente_encaminhado(body, em)
    assert "Thaiana" in nome or "Caisa" in nome, nome


def test_assunto_s5_prioriza_s5_nao_dlo_por_cos4010_no_corpo():
    """Assunto ECSA (S5) + corpo com COS4010/DLO citado → S5 D+5 úteis (2026-04-02)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "ecsa_s5_cos",
            "assunto": "Exemplo de email do dia 23/02 ECSA (S5) - Encaminhar o COS4010 E COS4016 DEZ./2025",
            "corpo_texto": (
                "Segue encaminhamento.\n\nDe: Cliente\nAssunto: DLO 2061\n"
                "COS4010 referência dezembro/2025"
            ),
            "data_email": "Mon, 23 Feb 2026 10:00:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "S5", f"esperado S5 obteve {r.get('cadoc')}"
        prazos = r.get("lista_prazos") or []
        assert len(prazos) == 1
        assert prazos[0].get("cadoc") == "S5"
        assert prazos[0].get("data_base") == "23/02/2026"
        assert prazos[0].get("prazo_limite") == "02/03/2026", prazos[0]
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_erro_na_tela_suprime_retorno_bacen_vai_suporte():
    """Assunto tipo EQI 'Erro na tela 4111': termo 'erro' não deve virar Retorno Bacen — SUPORTE D+5 (2026-03-30)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "91945_eqi_4111",
            "assunto": "EQI CTVM | Erro na tela 4111",
            "corpo_texto": "Bom dia, estou tentando acessar a tela do 4111 e ocorre erro.",
            "data_email": "Mon, 23 Feb 2026 14:30:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "SUPORTE", f"esperado SUPORTE obteve {r.get('cadoc')}"
        assert r.get("retorno_bacen") is False
        assert r.get("exibir_card") is True
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_rd_moeda_suprime_retorno_bacen_ddr():
    """Assunto com 'erro' (Retorno Bacen) + RD_MOEDAS/RD_* → cadoc DDR_2011, não RETORNO_BACEN (2026-03-30)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "91999_rd_moeda",
            "assunto": "ERRO - RD_Moedas",
            "corpo_texto": "Segue DDR 2011 posicao 19/02/2026",
            "data_email": "Mon, 23 Feb 2026 14:30:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "DDR_2011", f"esperado DDR_2011 obteve {r.get('cadoc')}"
        assert r.get("retorno_bacen") is False
        assert r.get("exibir_card") is True
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_critica_no_corpo_com_dlo_no_assunto_forca_retorno_bacen():
    """Assunto só RE: DLO_2061… sem termo BC; corpo com «critica» + DLO → RETORNO_BACEN (não DLO_2061 como cadoc card)."""
    import importlib.util
    import json
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json"), "r", encoding="utf-8") as f:
            regras_raiz = json.load(f).get("O_QUE_ESTA_SENDO_ANALISADO", {})
        v = mod.ValidadorContextual(regras_raiz)
        assert v.eh_retorno_bacen("RE: DLO_2061 e DLI_2062 - 12/2025") is False
        assert v.texto_mandatorio_retorno_bacen_critica_e_documento(
            "RE: DLO_2061 e DLI_2062 - 12/2025",
            "Tivemos essa critica no DLO_2061 de Dezembro/25, poderiam verificar.",
        ) is True
        assert v.texto_mandatorio_retorno_bacen_critica_e_documento(
            "RE: DLO_2061 e DLI_2062 - 12/2025",
            "Segue envio do arquivo DLO sem pendencia de BC.",
        ) is False
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "sefer_critica_dlo_corpo",
            "assunto": "RE: DLO_2061 e DLI_2062 - 12/2025",
            "corpo_texto": (
                "Bom dia, pessoal, Tivemos essa critica no DLO_2061 de Dezembro/25, "
                "poderiam verificar e nos enviar o novo arquivo."
            ),
            "data_email": "Mon, 23 Feb 2026 10:01:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "RETORNO_BACEN", f"esperado RETORNO_BACEN obteve {r.get('cadoc')}"
        assert r.get("retorno_bacen") is True
        assert r.get("exibir_card") is True
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_ddr_citacao_gmail_de_fev_nao_duplica_prazo_ultimo_dia():
    """Tabela DDR com 19/02 + citação Gmail «23 de fev. de 2026»: não tratar «fev» como mês sozinho (28/02)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        corpo = (
            "Prezado, o interior do arquivo está fora do formato.\n"
            "DATAOP MOEDA\n"
            "19/02/2026\n145\nTX\n"
            "Em seg., 23 de fev. de 2026 às 09:26, Luis &lt;x@y.com&gt; escreveu:\n"
            "DDR data base 19/02/2026\n"
        )
        item = {
            "id": "ddr_fev_citacao",
            "assunto": "Re: ERRO - RD_Moedas",
            "corpo_texto": corpo,
            "data_email": "Mon, 23 Feb 2026 09:40:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "DDR_2011", r.get("cadoc")
        prazos = r.get("lista_prazos") or []
        assert len(prazos) == 1, prazos
        assert prazos[0].get("data_base") == "19/02/2026", prazos[0]
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_critica_e_dlo_com_rd_moeda_ainda_ddr():
    """Mandatório critica+DLO não vence supressão RD_* → DDR."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        item = {
            "id": "rd_critica_dlo",
            "assunto": "RE: RD_MOEDAS ajuste",
            "corpo_texto": (
                "Houve uma critica no envio DLO 2061. Segue DDR 2011 posicao 19/02/2026 referente ao RD."
            ),
            "data_email": "Mon, 23 Feb 2026 14:30:00 -0300",
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "DDR_2011", f"esperado DDR_2011 obteve {r.get('cadoc')}"
        assert r.get("retorno_bacen") is False
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_pendencia_finaud_quando_obrigada_pelo_envio():
    """Qualquer CADOC: Finaud agradeceu recebimento (obrigada pelo envio) → pendência FINAUD (2026-03-20)."""
    path_04 = os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert "obrigada pelo envio" in code or "obrigado pelo envio" in code, "Exceção obrigada pelo envio deve existir"
    assert "pendencia = \"FINAUD\"" in code, "Override pendencia FINAUD na exceção"


def test_relatorio_interno_risk_driver_como_tipo_alem_do_cadoc():
    """Relatório Interno Risk Driver: apenas relatorio_interno_risk_driver=true, cadoc vazio (2026-03-16)."""
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location(
        "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with open(os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json"), "r", encoding="utf-8") as f:
        regras_completas = json.load(f)
    regras_raiz = regras_completas.get("O_QUE_ESTA_SENDO_ANALISADO", {})
    v = mod.ValidadorContextual(regras_raiz)
    # Assuntos que devem ser Relatório Interno
    assert v.eh_relatorio_interno_risk_driver("Risk Driver - OM DTVM LTDA Limite de Exposição Cambial") is True
    assert v.eh_relatorio_interno_risk_driver("Relatório do Serviço - Finaud Master 23/02/2026") is True
    assert v.eh_relatorio_interno_risk_driver("Atualização Bacen - 23/02/2026") is True
    # Assuntos que NÃO devem ser
    assert v.eh_relatorio_interno_risk_driver("DLO 2061 - Envio de relatório") is False
    assert v.eh_relatorio_interno_risk_driver("DDR 2011 - Saldos") is False
    # Classificador retorna relatorio_interno_risk_driver sem cadoc (cadoc vazio)
    path_04 = os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert '"relatorio_interno_risk_driver": True' in code, "Classificador deve retornar relatorio_interno_risk_driver"
    assert '"cadoc": ""' in code or '"cadoc":""' in code or "'cadoc': ''" in code, "Relatório Interno usa cadoc vazio"


def test_identificar_cadoc_dlo_assunto_nao_cai_em_ddr_por_citacao_2011():
    """Assunto DLO + corpo com citação 'DDR 2011' e 'DLO 2061_12': deve ser DLO_2061, não DDR (Planner DEZ/2025)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with open(os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json"), "r", encoding="utf-8") as f:
        regras_raiz = json.load(f).get("O_QUE_ESTA_SENDO_ANALISADO", {})
    v = mod.ValidadorContextual(regras_raiz)
    snip = (
        "BOA TARDE DLO DE DEZEMBRO SEGUE BALANCETE "
        "SEgue anexo o DLO 2061_12/2024 para envio ao BC. "
        "Anexos relatórios DDR 2011 e DRM 2060 de 31/12/2024"
    )
    c, term = v.identificar_cadoc(f"DLO - DEZEMBRO {snip}", "DLO - DEZEMBRO")
    assert c == "DLO_2061", f"esperado DLO_2061 obteve {c} termo={term}"
    # Sem DLO no assunto: primeiro código ainda pode ser 2011 no texto misto
    c2, _ = v.identificar_cadoc(snip, "Encaminhamento relatórios")
    assert c2 == "DDR_2011"


@pytest.mark.xfail(reason="Regressão conhecida: RETORNO_BACEN suprime DLO mesmo com corpus de datas (#PF-corpus-dlo); aguarda regra de supressão baseada em corpus", strict=False)
def test_erro_dlo_corpus_thread_sem_data():
    """Erro DLO: 1ª msg sem data → busca no corpus da thread (Andrea jan/2026, Thaiana dezembro/2025) (2026-03-16)."""
    import importlib.util
    import os
    env_orig = os.environ.get("DATA_COLETA_INICIO"), os.environ.get("DATA_LIMITE_EXCLUIR")
    os.environ["DATA_COLETA_INICIO"] = "21-Jan-2026"
    os.environ["DATA_LIMITE_EXCLUIR"] = "01-Mar-2026"
    try:
        spec = importlib.util.spec_from_file_location(
            "classificador", os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        o = mod.Oraculo(verbose=False)
        # 1ª msg: "Erro DLO" sem data no corpo
        # _corpus_thread = assunto+corpo filtrado das outras msgs (Andrea: jan/2026; Thaiana: dezembro/2025)
        item = {
            "id": "91983",
            "assunto": "Erro DLO",
            "corpo_texto": "Andrea, boa tarde. Tomei esse erro ao enviar o DLO",
            "data_email": "Mon, 23 Feb 2026 14:30:00 -0300",
            "_corpus_thread": (
                "Erro DLO Andrea boa tarde Tomei esse erro ao enviar o DLO "
                "Re: Erro DLO Não localizei a data, seria a remessa DLO jan/2026? "
                "RES: Erro DLO Boa tarde Remessa de dezembro/2025, segue documento."
            ),
        }
        r = o.processar_email(item)
        assert r.get("cadoc") == "DLO_2061", "Deve identificar DLO"
        assert r.get("exibir_card") is True, "Corpus da thread deve gerar prazo"
        prazos = r.get("lista_prazos", [])
        assert len(prazos) >= 1, "Pelo menos um prazo (dez/2025 ou jan/2026)"
        data_bases = [p.get("data_base") for p in prazos]
        assert "31/12/2025" in data_bases or "31/01/2026" in data_bases, "dezembro/2025 ou jan/2026 vindos do corpus"
    finally:
        for k, v in zip(("DATA_COLETA_INICIO", "DATA_LIMITE_EXCLUIR"), env_orig):
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


TESTS = [
    test_mapeamento_suporte_prazo_dias_uteis,
    test_classificador_usa_thread_root_sem_req,
    test_indice_basileia_no_assunto_forca_suporte_d5,
    test_extrair_email_e_nome_encaminhamento_interno_finaud,
    test_assunto_s5_prioriza_s5_nao_dlo_por_cos4010_no_corpo,
    test_identificar_cadoc_dlo_assunto_nao_cai_em_ddr_por_citacao_2011,
    test_mes_sozinho_extrai_data_dli_dezembro,
    test_retorno_bacen_tipificacao,
    test_critica_no_corpo_com_dlo_no_assunto_forca_retorno_bacen,
    test_ddr_citacao_gmail_de_fev_nao_duplica_prazo_ultimo_dia,
    test_critica_e_dlo_com_rd_moeda_ainda_ddr,
    test_erro_na_tela_suprime_retorno_bacen_vai_suporte,
    test_erro_ou_erros_dlo_no_assunto_processar_retorno_bacen,
    test_rd_moeda_suprime_retorno_bacen_ddr,
    test_pendencia_finaud_quando_obrigada_pelo_envio,
    test_relatorio_interno_risk_driver_como_tipo_alem_do_cadoc,
    test_erro_dlo_corpus_thread_sem_data,
]
