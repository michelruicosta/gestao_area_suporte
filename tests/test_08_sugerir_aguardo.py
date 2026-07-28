"""
QA – API sugerir_aguardo: cenário UNICRED DDR (dados até 12/02 recebidos em 18/02).

Valida que o fluxo "✨ Sugerir" no painel Aguardando retorna motivo correto para threads
como UNICRED - DDRs e CADOC, onde o cliente já enviou "Segue até 12/02" em 18/02.

Alinhado à seção "2026-02-27 — IA citava apenas uma data em threads com envios incrementais" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import RAIZ

# Raiz no path para importar painel_oraculo
if RAIZ not in __import__("sys").path:
    __import__("sys").path.insert(0, RAIZ)


def _payload_unicred_ddr():
    """Payload simulado do frontend para a thread UNICRED - DDRs e CADOC."""
    return {
        "assunto": "UNICRED - DDRs e CADOC",
        "cadoc": "DDR_2011",
        "empresa": "Unicred",
        "quem_gera": "CLIENTE",
        "responsabilidade": "CLIENTE",
        "corpo_resumido": "Segue até o dia 12/02.",
        "historico": "Segue até 19/01... Segue até 21/01... Segue até 12/02.",
        "ultimo_lado": "CLIENTE",
        "data_email": "2026-02-18",
        "data_referencia": "2026-02-27",
        "prazo_regulatorio": "2026-02-19",
        "threadId": "test-unicred-001",
        "lista_prazos": [
            {"data_base": "2026-02-10", "prazo_limite": "2026-02-13", "cadoc": "DDR_2011"},
            {"data_base": "2026-02-11", "prazo_limite": "2026-02-18", "cadoc": "DDR_2011"},
            {"data_base": "2026-02-12", "prazo_limite": "2026-02-19", "cadoc": "DDR_2011"},
        ],
    }


def _resposta_ia_esperada():
    """Resposta JSON que a IA deve retornar para o cenário UNICRED (conforme prompt [A])."""
    return {
        "tipo": "ACAO_INTERNA",
        "motivo": "Gerar DDR com dados até 12/02 recebidos em 18/02 da Unicred",
        "observacao": "Cliente enviou em 18/02; DDRs ref. 10 e 11/02 já estavam vencidos.",
        "prazo_idx": 2,
    }


@pytest.mark.xfail(reason="Pendente: pós-processamento Padrão B (motivo formatado) não implementado", strict=False)
def test_api_sugerir_aguardo_unicred_com_mock():
    """
    Com payload UNICRED e OpenAI mockada, a API retorna motivo com data até 12/02,
    data de recebimento 18/02, empresa Unicred e tipo ACAO_INTERNA.
    """
    from painel_oraculo import app

    payload = _payload_unicred_ddr()
    resposta_mock = _resposta_ia_esperada()

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        # Sessão autenticada (admin existe em usuarios.json)
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create

            r = client.post(
                "/api/sugerir_aguardo",
                json=payload,
                content_type="application/json",
            )

    assert r.status_code == 200, f"Status esperado 200, obtido {r.status_code}: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data is not None, "Resposta deve ser JSON"

    motivo = (data.get("motivo") or "").strip()
    tipo = data.get("tipo", "")
    observacao = (data.get("observacao") or "").strip()

    # Motivo = padrão B preenchido (CADOC, empresa, prazo, status, recebido)
    assert "18/02" in motivo or "18/02" in motivo.replace(" ", ""), f"Motivo deve citar 18/02 (recebimento): {motivo}"
    assert "unicred" in motivo.lower(), f"Motivo deve citar Unicred: {motivo}"
    assert "ddr" in motivo.lower() or "gerar" in motivo.lower(), f"Motivo deve indicar ação: {motivo}"
    assert "Dados do cliente recebidos" in motivo or "recebidos" in motivo.lower(), f"Motivo Padrão B: {motivo}"
    assert tipo == "ACAO_INTERNA", f"Tipo esperado ACAO_INTERNA, obtido {tipo}"
    assert data.get("fonte") == "ia", "Fonte deve ser 'ia' quando OpenAI responde"


@pytest.mark.xfail(reason="Pendente: prefill sem OpenAI não retorna fonte=prefill", strict=False)
def test_api_sugerir_aguardo_prefill_sem_openai():
    """
    Sem OPENAI_API_KEY, a API retorna prefill (fonte=prefill).
    O prefill deve ter motivo não vazio e tipo válido.
    """
    from painel_oraculo import app

    payload = _payload_unicred_ddr()

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        # Remove chave para forçar fallback para prefill
        env_key = os.environ.get("OPENAI_API_KEY")
        try:
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            r = client.post(
                "/api/sugerir_aguardo",
                json=payload,
                content_type="application/json",
            )
        finally:
            if env_key is not None:
                os.environ["OPENAI_API_KEY"] = env_key

    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert (data.get("motivo") or "").strip(), "Prefill deve ter motivo não vazio"
    assert data.get("tipo") in ("ACAO_INTERNA", "ENTREGA_CLIENTE", "RESPOSTA_CLIENTE", "RESPOSTA_EM_OUTRO_EMAIL", "AGUARDANDO_PRAZO", "OUTRO", None) or not data.get("tipo")
    assert data.get("fonte") == "prefill", "Sem API key, fonte deve ser prefill"


@pytest.mark.xfail(reason="Pendente: prompt [G] ainda não cita 'Pendência com' ou 'tarefa concreta'", strict=False)
def test_prompt_redirecionamento_deve_dizer_tarefa_concreta():
    """
    Corrige 2026-03-11: categoria [G] redirecionamento deve exigir tarefa concreta,
    não só "Encaminhar para X — tema não tratado".
    """
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "Pendência com" in code or "tarefa concreta" in code, "Prompt [G] deve citar tarefa concreta ou formato 'Pendência com'"
    assert "NÃO use só \"Encaminhar para" in code or "O QUE o analista precisa fazer" in code, "Prompt [G] deve desaconselhar motivo vago"


def _payload_finaud_solicita_trinus():
    """Cenário: Finaud solicitou em 23/02 extratos ao cliente para DDRs 18,19,20/02. Solicitante=Finaud, Destinatário=cliente -> ENTREGA_CLIENTE."""
    return {
        "assunto": "Informações para DDRs de 18, 19 e 20/02/2026",
        "cadoc": "DDR_2011",
        "empresa": "Trinus Bank",
        "quem_gera": "FINAUD",
        "responsabilidade": "FINAUD",
        "corpo_resumido": "Por gentileza enviar para cálculo dos DDRs dos dias 18, 19 e 20/02: Extrato em CDBs; Operações Compromissadas.",
        "historico": "Informações para DDRs de 18, 19 e 20/02/2026. Bom dia! Por gentileza enviar para cálculo dos DDRs dos dias 18, 19 e 20/02/2026: Extrato em CDBs; Operações Compromissadas; Caso tenham sido realizadas novas aplicações, por gentileza enviar também. Data de envio ao Banco Central: DDR de 18/02 data limite para envio 23/02/2026; DDR de 19/02 data limite para envio 24/02/2026; DDR de 20/02 data limite para envio 25/02/2026.",
        "ultimo_lado": "FINAUD",
        "data_email": "2026-02-23",
        "data_referencia": "2026-02-27",
        "prazo_regulatorio": "2026-02-25",
        "threadId": "test-trinus-ddr-001",
        "lista_prazos": [
            {"data_base": "2026-02-18", "prazo_limite": "2026-02-23", "cadoc": "DDR_2011"},
            {"data_base": "2026-02-19", "prazo_limite": "2026-02-24", "cadoc": "DDR_2011"},
            {"data_base": "2026-02-20", "prazo_limite": "2026-02-25", "cadoc": "DDR_2011"},
        ],
    }


@pytest.mark.xfail(reason="Pendente: heurística finaud_solicita→ENTREGA_CLIENTE não implementada", strict=False)
def test_api_sugerir_aguardo_finaud_solicita_entregacliente():
    """
    Corrige 2026-03-11: quando FINAUD solicita dados ao cliente (por gentileza enviar, enviar para cálculo),
    Solicitante=Finaud, Destinatário=cliente -> tipo ENTREGA_CLIENTE (não ACAO_INTERNA).
    """
    from painel_oraculo import app

    payload = _payload_finaud_solicita_trinus()
    resposta_mock = {
        "tipo": "ENTREGA_CLIENTE",
        "motivo": "Aguardando extratos de Trinus Bank ref. 18, 19 e 20/02 para gerar DDR_2011",
        "observacao": "",
        "prazo_idx": 2,
    }

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True

        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create
            r = client.post("/api/sugerir_aguardo", json=payload, content_type="application/json")

    assert r.status_code == 200, f"Status {r.status_code}: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data is not None
    assert data.get("tipo") == "ENTREGA_CLIENTE", f"Quando Finaud solicita dados, tipo deve ser ENTREGA_CLIENTE: {data.get('tipo')}"
    motivo = (data.get("motivo") or "").lower()
    assert "trinus" in motivo
    # Padrão C: "Aguardando entrega do cliente até..."
    assert "entrega" in motivo or "cliente" in motivo


@pytest.mark.xfail(reason="Pendente: prompt SOLICITANTE/DESTINATÁRIO não implementado", strict=False)
def test_prompt_solicitante_destinatario():
    """Prompt deve exigir identificação de Solicitante e Destinatário para distinguir Finaud pede vs cliente entrega."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "SOLICITANTE" in code and ("DESTINATÁRIO" in code or "DESTINATARIO" in code)
    assert "_finaud_solicita_dados" in code or "finaud_solicita" in code


@pytest.mark.xfail(reason="Pendente: _cliente_questiona_divergencias não implementado", strict=False)
def test_prompt_cliente_questiona_divergencias():
    """Quando cliente questiona divergências e aguarda retorno, pendência é [nome] responder, não gerar."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_cliente_questiona_divergencias" in code or "cliente_questiona" in code
    assert "divergências" in code or "divergencias" in code
    assert "Monica" in code or "responder ao cliente sobre" in code
    assert "NÃO gerar" in code or "nao gerar" in code.lower()


def _payload_western_union():
    """Cenário: cliente enviou Anexo Posições da Western Union 23/02 — deve retornar ACAO_INTERNA + resumo_padrao."""
    return {
        "assunto": "Posição de Câmbio corretora, Balancete",
        "cadoc": "DDR_2011",
        "empresa": "Western Union",
        "quem_gera": "FINAUD",
        "historico": "Boa tarde! Anexo Posições da Western Union Corretora 23/02/2026: - Posição de Câmbio Contábil.",
        "ultimo_lado": "CLIENTE",
        "data_email": "2026-02-24",
        "data_referencia": "2026-02-27",
        "prazo_regulatorio": "2026-02-26",
        "lista_prazos": [{"data_base": "2026-02-23", "prazo_limite": "2026-02-26", "cadoc": "DDR_2011"}],
    }


@pytest.mark.xfail(reason="Pendente: prazo_sugerido/foco_monitoramento não retornados pelo sugerir_aguardo", strict=False)
def test_api_sugerir_aguardo_western_union_resumo_padrao():
    """Western Union: cliente enviou Anexo Posições -> ACAO_INTERNA + resumo_padrao preenchido."""
    from painel_oraculo import app

    payload = _payload_western_union()
    resposta_mock = {
        "tipo": "ACAO_INTERNA",
        "motivo": "Gerar DDR_2011 com dados até 23/02 recebidos em 24/02 da Western Union",
        "observacao": "",
        "prazo_idx": 0,
    }

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True
        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create
            r = client.post("/api/sugerir_aguardo", json=payload, content_type="application/json")

    assert r.status_code == 200
    data = r.get_json()
    assert data.get("tipo") == "ACAO_INTERNA"
    assert "western" in (data.get("motivo") or "").lower()
    # Padrão B: quadro exibido em painelFocoMonitor (não resumo_padrao); IA deve retornar prazo correto
    assert data.get("prazo_sugerido"), "Padrão B deve retornar prazo_sugerido para o quadro"
    assert data.get("foco_monitoramento") == "PRAZO_INTERNO"


def test_motivo_contextual_decodifica_mime_nomes():
    """
    Corrige 2026-03-17: motivo não deve exibir =?UTF-8?Q?…?= (RFC 2047).
    Nomes devem ser decodificados para exibição legível.
    """
    from painel_oraculo import _construir_motivo_contextual

    mime_nome = "=?UTF-8?Q?=27Alison_Guimar=C3=A3es_de_Miranda=27_via_Suporte?="
    latest = {
        "contato_origem": {"lado": "CLIENTE", "nome": mime_nome},
        "contato_destino": {"lado": "FINAUD", "nome": "Lucas Vellani"},
    }
    motivo = _construir_motivo_contextual(
        conteudo={},
        latest=latest,
        cadoc="4111",
        empresa="Sefer",
        responsavel="Lucas Vellani",
        lista_prazos=[{"prazo_limite": "25/02/2026"}],
    )
    assert motivo is not None
    assert "=?" not in motivo and "?=" not in motivo, f"Motivo não deve conter MIME encoded: {motivo}"
    assert "Alison" in motivo, f"Motivo deve conter nome decodificado: {motivo}"


def test_motivo_contextual_avenue_fernando_flavio_ddr():
    """
    Corrige 2026-03-17: motivo contextual com dados reais da thread.
    Cenário Avenue: Fernando Mallet (cliente) envia ao Flavio Camargo dados para DDR.
    Motivo deve ser "Fernando Mallet envia ao Flavio Camargo dados para DDR. Prazo: 23/02/2026",
    NÃO "Terra Investimentos" ou outro aprendizado de outra empresa.
    """
    from painel_oraculo import _construir_motivo_contextual

    latest = {
        "contato_origem": {"lado": "CLIENTE", "nome": "Fernando Mallet"},
        "contato_destino": {"lado": "FINAUD", "nome": "Flavio Camargo"},
    }
    lista_prazos = [
        {"data_base": "2026-02-12", "prazo_limite": "19/02/2026", "cadoc": "DDR_2011"},
        {"data_base": "2026-02-13", "prazo_limite": "20/02/2026", "cadoc": "DDR_2011"},
        {"data_base": "2026-02-18", "prazo_limite": "23/02/2026", "cadoc": "DDR_2011"},
    ]
    motivo = _construir_motivo_contextual(
        conteudo={},
        latest=latest,
        cadoc="DDR_2011",
        empresa="Avenue",
        responsavel="Flavio Camargo",
        lista_prazos=lista_prazos,
    )
    assert motivo is not None, "Motivo contextual deve ser gerado"
    assert "Fernando Mallet" in motivo, f"Motivo deve citar quem envia: {motivo}"
    assert "Flavio Camargo" in motivo, f"Motivo deve citar para quem: {motivo}"
    assert "DDR" in motivo, f"Motivo deve citar o que (DDR): {motivo}"
    assert "23/02" in motivo or "2026-02-23" in motivo, f"Motivo deve citar prazo mais recente (23/02): {motivo}"


@pytest.mark.xfail(reason="Pendente: prompt não instrui ordem cronológica explicitamente", strict=False)
def test_prompt_historico_ordem_cronologica():
    """O prompt deve instruir a IA a ler o histórico em ordem cronológica para entender o fluxo."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "ordem cronológica" in code or "mais antigo primeiro" in code, (
        "Prompt deve indicar que o histórico está em ordem cronológica para a IA entender o fluxo"
    )


@pytest.mark.xfail(reason="Pendente: _cliente_confirmou_resolucao não implementado", strict=False)
def test_prompt_cliente_confirmou_resolucao():
    """Quando cliente confirmou resolução (deu certo, obrigado), NÃO use 'Aguardando retorno'."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_cliente_confirmou_resolucao" in code or "cliente_confirmou" in code
    assert "deu certo" in code or "funcionou" in code
    assert "arquivar" in code
    assert "Aguardando retorno" in code  # RUIM quando cliente já confirmou


@pytest.mark.xfail(reason="Pendente: heurística Padrão A (Finaud enviou→RESPOSTA_CLIENTE) não implementada", strict=False)
def test_finaud_enviou_ao_cliente_padrao_a():
    """Quando Finaud enviou ao cliente (seguem anexos, para envio ao BACEN) → Padrão A (RESPOSTA_CLIENTE)."""
    from painel_oraculo import app

    payload = {
        "assunto": "DOC. 4111 de 19, 20 e 23/02/2026",
        "cadoc": "4111",
        "empresa": "Sefer Investimento",
        "quem_gera": "FINAUD",
        "historico": "Boa tarde! Sequem anexos DOC. 4111 de 19, 20 e 23/02/2026 para envio ao Banco Central.",
        "ultimo_lado": "FINAUD",
        "data_email": "2026-02-24",
        "prazo_regulatorio": "2026-02-26",
        "lista_prazos": [
            {"data_base": "2026-02-19", "prazo_limite": "2026-02-24", "cadoc": "4111"},
            {"data_base": "2026-02-20", "prazo_limite": "2026-02-25", "cadoc": "4111"},
            {"data_base": "2026-02-23", "prazo_limite": "2026-02-26", "cadoc": "4111"},
        ],
    }
    # IA poderia retornar ACAO_INTERNA; heurística força RESPOSTA_CLIENTE (Padrão A)
    resposta_mock = {"tipo": "ACAO_INTERNA", "motivo": "Gerar 4111", "observacao": "", "prazo_idx": 2}

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True
        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create
            r = client.post("/api/sugerir_aguardo", json=payload, content_type="application/json")

    assert r.status_code == 200
    data = r.get_json()
    assert data.get("tipo") == "RESPOSTA_CLIENTE", "Finaud enviou ao cliente → Padrão A (RESPOSTA_CLIENTE)"
    assert "Finaud já enviou" in (data.get("motivo") or "")


@pytest.mark.xfail(reason="Pendente: heurística segue_anexo→RESPOSTA_CLIENTE não implementada", strict=False)
def test_finaud_segue_anexo_remessa_drl_padrao_a():
    """Thread Mirae DRL: Finaud pediu planilha antes, depois enviou 'Segue anexo a remessa DRL' → Padrão A."""
    from painel_oraculo import app

    payload = {
        "assunto": "Encaminhar a planilha DRL jan/2026. Segue a remessa - MIRAE",
        "cadoc": "DRL_2160",
        "empresa": "Mirae Invest",
        "quem_gera": "FINAUD",
        "historico": (
            "Por gentileza enviar para cálculo a planilha DRL jan/2026. "
            "Cliente deve enviar até 10/02/2026. "
            "Prezados, boa tarde. Obrigada. Segue anexo a remessa DRL (2160) jan/2026. À disposição."
        ),
        "corpo_ultima_msg": "Prezados, boa tarde. Obrigada. Segue anexo a remessa DRL (2160) jan/2026. À disposição.",
        "ultimo_lado": "FINAUD",
        "data_email": "2026-02-24",
        "prazo_regulatorio": "2026-02-13",
        "lista_prazos": [
            {"data_base": "2026-01-31", "prazo_limite": "2026-02-10", "cadoc": "DRL_2160"},
            {"data_base": "2026-01-31", "prazo_limite": "2026-02-13", "cadoc": "DRL_2160"},
        ],
    }
    resposta_mock = {"tipo": "ENTREGA_CLIENTE", "motivo": "Aguardando planilha DRL", "observacao": "", "prazo_idx": 0}

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True
        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create
            r = client.post("/api/sugerir_aguardo", json=payload, content_type="application/json")

    assert r.status_code == 200
    data = r.get_json()
    assert data.get("tipo") == "RESPOSTA_CLIENTE", (
        "Finaud enviou 'Segue anexo a remessa DRL' → Padrão A (RESPOSTA_CLIENTE), "
        "mesmo com pedido anterior no histórico"
    )
    motivo = (data.get("motivo") or "").lower()
    assert (
        "finaud já enviou" in motivo or "remessa" in motivo or "drl enviado" in motivo
        or "resposta do cliente não obrigatória" in motivo or "resposta não obrigatória" in motivo
    ), f"Motivo deve indicar Padrão A (Finaud enviou): {data.get('motivo')}"


@pytest.mark.xfail(reason="Pendente: heurística finaud_orienta_encaminhar_bc→ENTREGA_CLIENTE não implementada", strict=False)
def test_finaud_orienta_encaminhar_bc_dlo_recusado():
    """DLO Recusado Nikos: Finaud orienta IF a encaminhar questionamento ao BC via CRD → motivo sobre encaminhamento, não 'DLO enviado'."""
    from painel_oraculo import app

    payload = {
        "assunto": "Re: DLO Recusado Nikos DTVM",
        "cadoc": "DLO_2061",
        "empresa": "Nikos DTVM",
        "quem_gera": "FINAUD",
        "historico": (
            "Prezado Gabriel, bom dia. Para solucionar, recebemos a orientação do gestor de riscos "
            "para que a IF encaminhe o questionamento transcrito abaixo ao BC via CRD: Prezados, No processo de validação "
            "do documento prudencial referente ao RWAOPAD - Abordagem Padronizada de Risco Operacional (Segmento S4), "
            "identificamos uma crítica sistêmica baseada na seguinte regra: ABS(875.01/100 - 876) ≤ 0,15. "
            "Acompanhe a devolutiva e qualquer dúvida retorne. Histórico encaminhado dentro desta mensagem."
        ),
        "corpo_ultima_msg": (
            "Prezado Gabriel, bom dia. Para solucionar, recebemos a orientação do gestor de riscos "
            "para que a IF encaminhe o questionamento transcrito abaixo ao BC via CRD."
        ),
        "ultimo_lado": "FINAUD",
        "data_email": "2026-02-24",
        "prazo_regulatorio": "2026-03-05",
        "lista_prazos": [{"data_base": "2026-01-31", "prazo_limite": "2026-03-05", "cadoc": "DLO_2061"}],
    }
    resposta_mock = {"tipo": "RESPOSTA_CLIENTE", "motivo": "DLO enviado ao cliente. Resposta não obrigatória", "observacao": "", "prazo_idx": 0}

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True
        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create
            r = client.post("/api/sugerir_aguardo", json=payload, content_type="application/json")

    assert r.status_code == 200
    data = r.get_json()
    # Heurística finaud_orienta_encaminhar_bc deve sobrescrever: ENTREGA_CLIENTE
    assert data.get("tipo") == "ENTREGA_CLIENTE", "Finaud orienta encaminhar ao BC → ENTREGA_CLIENTE"
    motivo = (data.get("motivo") or "").lower()
    assert "encaminhar" in motivo or "bc" in motivo or "questionamento" in motivo, f"Motivo deve citar encaminhamento ao BC: {motivo[:150]}"
    assert "dlo enviado ao cliente" not in motivo, f"Motivo não deveria dizer DLO enviado ao cliente: {motivo[:150]}"


@pytest.mark.xfail(reason="Pendente: heurística finaud_pergunta→ENTREGA_CLIENTE não implementada", strict=False)
def test_finaud_pergunta_ao_cliente_dlo_nao_enviado():
    """Quando Finaud encaminha dúvida ao cliente (ex.: qual conta usar) → DLO não foi enviado, aguardando resposta."""
    from painel_oraculo import app

    payload = {
        "assunto": "DLO DEZ/25 - Sefer Investimento",
        "cadoc": "DLO_2061",
        "empresa": "Sefer Investimento",
        "quem_gera": "FINAUD",
        "historico": "Boa tarde, Alison. Poderia, por gentileza, informar qual conta deve ser utilizada para a realização do ajuste? Como essa demanda costuma ser tratada pelo Lucas, não possuo familiaridade com o procedimento específico.",
        "ultimo_lado": "FINAUD",
        "data_email": "2026-02-24",
        "prazo_regulatorio": "2026-02-05",
        "lista_prazos": [{"data_base": "2026-01-31", "prazo_limite": "2026-02-05", "cadoc": "DLO_2061"}],
    }
    resposta_mock = {"tipo": "RESPOSTA_CLIENTE", "motivo": "DLO enviado ao cliente", "observacao": "", "prazo_idx": 0}

    def fake_create(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = json.dumps(resposta_mock)
        return resp

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "admin"
            sess["_fresh"] = True
        with patch("painel_oraculo.client") as mock_client:
            mock_client.chat.completions.create = fake_create
            r = client.post("/api/sugerir_aguardo", json=payload, content_type="application/json")

    assert r.status_code == 200
    data = r.get_json()
    # Heurística finaud_pergunta deve sobrescrever: ENTREGA_CLIENTE (cliente deve responder)
    assert data.get("tipo") == "ENTREGA_CLIENTE", "Finaud pergunta ao cliente → ENTREGA_CLIENTE"
    motivo = (data.get("motivo") or "").lower()
    # Motivo deve indicar aguardando cliente responder (dúvida) e NÃO "DLO enviado"
    assert "responder" in motivo, f"Motivo deveria conter 'responder': {motivo[:150]}"
    assert "dlo enviado ao cliente" not in motivo, f"Motivo não deveria dizer DLO enviado: {motivo[:150]}"


TESTS = [
    test_motivo_contextual_decodifica_mime_nomes,
    test_motivo_contextual_avenue_fernando_flavio_ddr,
    test_api_sugerir_aguardo_unicred_com_mock,
    test_finaud_orienta_encaminhar_bc_dlo_recusado,
    test_prompt_historico_ordem_cronologica,
    test_api_sugerir_aguardo_western_union_resumo_padrao,
    test_api_sugerir_aguardo_prefill_sem_openai,
    test_prompt_redirecionamento_deve_dizer_tarefa_concreta,
    test_api_sugerir_aguardo_finaud_solicita_entregacliente,
    test_finaud_enviou_ao_cliente_padrao_a,
    test_finaud_segue_anexo_remessa_drl_padrao_a,
    test_finaud_pergunta_ao_cliente_dlo_nao_enviado,
    test_prompt_solicitante_destinatario,
    test_prompt_cliente_questiona_divergencias,
    test_prompt_cliente_confirmou_resolucao,
]
