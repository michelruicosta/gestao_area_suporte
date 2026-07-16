"""
QA alinhado a REGISTRO_CORRECOES.md — validações pontuais de correções registradas.
Executado por `python run_qa.py` (ver tests/README_QA.md se existir).
"""
from __future__ import annotations

import json
import os

from tests.conftest import RAIZ


def test_helpers_sec4d_regex_layout_leiaute_definida_e_funcional():
    """2026-05-11: ``_RE_SEC4D_LAYOUT_LEIAUTE`` em ``scripts/triagem/helpers.py``
    é usada por ``_principal_cf_pergunta_tema_layout`` / ``_principal_fc_cita_tema_layout``
    (§4d, sub-veto). Sem a definição, a triagem DDR4111 inteira explode com
    ``NameError`` ao processar qualquer thread que caia em
    ``_sec4d_veto_pendencia_cliente_intermedia`` — e como o orquestrador captura
    a exceção, todos os fios DDR_2011 / 4111 / DRL_2160 ficam sem classificação
    (PENDENTE no painel apesar de baterem com regra).
    """
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)

    # Symbol existe no módulo (regressão: pode voltar a sumir num refactor)
    from triagem import helpers as _h  # noqa: WPS433
    assert hasattr(_h, "_RE_SEC4D_LAYOUT_LEIAUTE"), (
        "_RE_SEC4D_LAYOUT_LEIAUTE não definido em scripts/triagem/helpers.py — "
        "triagem DDR4111 vai falhar silenciosamente com NameError ao processar "
        "qualquer thread com C→F intermediária com '?' no caminho §4d"
    )
    rx = _h._RE_SEC4D_LAYOUT_LEIAUTE

    # Comportamento mínimo esperado pelos testes §4d
    assert rx.search("Houve alteração de layout do arquivo?"), "deve match 'layout'"
    assert rx.search("O leiaute segue o CRD"), "deve match 'leiaute'"
    assert rx.search("nada mudou no formato de colunas"), "deve match 'formato'"
    # Falso positivo control: termos genéricos não devem matchar
    assert not rx.search("Certo, o ajuste foi publicado em produção."), "não deve match 'ajuste'/'produção'"
    assert not rx.search("Experimente importar novamente"), "não deve match 'importar'"


def test_indices_snapshot_preservam_registo_auto_sobre_manual():
    """2026-05-11: índices ``aguardando_by_tid`` / ``concluidas_by_tid`` em
    ``painel_operacional_snapshot.py`` devem manter a 1ª ocorrência (AUTO antes
    de MANUAL, ver ``paths.load_aguardando``). Dict comprehension simples manteria
    a última ocorrência e quebraria a regra de DATA REF (fio AGUARDANDO em D-1
    virava PENDENTE em D quando o fio tinha registos em ambos os arquivos auto+manual).
    """
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    assert os.path.isfile(path_snap)
    with open(path_snap, "r", encoding="utf-8") as f:
        src = f.read()
    # Não deve haver dict comprehension simples de aguardando_by_tid / concluidas_by_tid
    # (essa forma sobrescreve com a última ocorrência → MANUAL ganha sobre AUTO).
    forma_quebrada_ag = (
        "aguardando_by_tid = {\n"
        "        r[\"threadId\"]: r for r in aguardando_lista"
    )
    forma_quebrada_co = (
        "concluidas_by_tid = {\n"
        "        r[\"threadId\"]: r for r in concluidas"
    )
    assert forma_quebrada_ag not in src, (
        "regressão 2026-05-11: aguardando_by_tid voltou a ser dict comprehension "
        "(sobrescreve AUTO por MANUAL — quebra DATA REF do dia seguinte)"
    )
    assert forma_quebrada_co not in src, (
        "regressão 2026-05-11: concluidas_by_tid voltou a ser dict comprehension "
        "(sobrescreve AUTO por MANUAL — quebra DATA REF do dia seguinte)"
    )
    # Deve existir guarda de 1ª ocorrência
    assert "if isinstance(r, dict) and r.get(\"threadId\") and r[\"threadId\"] not in aguardando_by_tid" in src
    assert "if isinstance(r, dict) and r.get(\"threadId\") and r[\"threadId\"] not in concluidas_by_tid" in src


def test_regra_cursor_imutabilidade_dia_ref_obrigatoria():
    """2026-04-27: regra sempre activa — dias 23/24, só correção pontual; verificar ambos em correção."""
    path_mdc = os.path.join(RAIZ, ".cursor", "rules", "oraculo-imutabilidade-dia-ref.mdc")
    assert os.path.isfile(path_mdc)
    with open(path_mdc, "r", encoding="utf-8") as f:
        txt = f.read()
    assert "alwaysApply: true" in txt
    assert "Imutabilidade" in txt
    assert "informar" in txt.lower() and "causa" in txt.lower()
    assert "23" in txt and "24" in txt
    assert "pontual" in txt.lower() and "ambos" in txt.lower()


def test_responsavel_pela_acao_registro_template_e_painel():
    """2026-04-02: card «Responsável pela ação» + API injeta responsavel_pela_acao."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Responsável pela ação" in html
    assert "responsavel_pela_acao" in html
    assert "responsavelPelaAcaoFromMensagens" in html
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "responsavel_pela_acao" in code
    assert "_responsavel_pela_acao_from_mensagens" in code
    assert "_excecao_obrigada_pelo_envio_ultima" in code
    assert "obrigado pelo envio" in code


def test_responsavel_pela_acao_regra_ultimo_fio():
    """2026-07-16: responsável = Para (quem recebeu). C→F=Finaud, F→C=Cliente, F→F=Finaud."""
    from painel_oraculo import _responsavel_pela_acao_from_mensagens

    msgs_ff = [
        {
            "data_email": "23/02/2026 10:00",
            "contato_origem": {"lado": "FINAUD", "nome": "Andrea", "email": "a@finaud.com.br"},
            "contato_destino": {"lado": "FINAUD", "nome": "Rodrigo", "email": "r@finaud.com.br"},
        },
    ]
    assert _responsavel_pela_acao_from_mensagens(msgs_ff, "Moneycorp") == "Rodrigo"

    msgs_fc = [
        {
            "data_email": "23/02/2026 11:00",
            "contato_origem": {"lado": "FINAUD", "nome": "Andrea", "email": "a@finaud.com.br"},
            "contato_destino": {"lado": "CLIENTE", "nome": "Hebert"},
            "corpo_limpo": "Obrigado pelo envio dos arquivos.",
        },
    ]
    assert _responsavel_pela_acao_from_mensagens(msgs_fc, "") == "Hebert"


def test_modal_operacional_sem_botoes_header_aguardar_aprender():
    """2026-04-27: modal do cartão — sem botões «Aguardando» / «Aprender e Concluir» na barra (pedido utilizador)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, encoding="utf-8") as f:
        html = f.read()
    assert 'id="mLearnFlow"' not in html
    assert 'id="mAguardandoBtn"' not in html


def test_modal_historico_id_sistema_paridade_json_ecra():
    """2026-04-27: campo id da mensagem no JSON visível no modal; título/coerência sem divergência de conta."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, encoding="utf-8") as f:
        html = f.read()
    assert "function linhaIdSistemaMsgModal" in html
    assert 'class="msg-id-sistema"' in html
    assert "Histórico da Conversa (" in html  # conta = grupos exibidos
    assert "efetivamente listadas abaixo" in html
    path_int = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    with open(path_int, encoding="utf-8") as f:
        code = f.read()
    assert '"qtd_mensagens": len(mensagens_formatadas)' in code


def test_verificar_cadeia_json_pipeline_script_presente():
    """2026-04-29: script verifica timestamps 01/02/03 e sugere atualiza_carga desde N."""
    path_py = os.path.join(RAIZ, "scripts", "verificar_cadeia_json_pipeline.py")
    assert os.path.isfile(path_py)
    with open(path_py, encoding="utf-8") as f:
        txt = f.read()
    assert "verificar_cadeia_json_pipeline" in path_py.lower()
    assert "atualiza_carga.py --desde 5" in txt
    assert "atualiza_carga.py --desde 9" in txt


def test_marcar_aguardando_envia_data_ref_operacional():
    """2026-03-30: operacional envia data_ref_operacional ao marcar Aguardando."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "data_ref_operacional" in html
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        assert "data_ref_operacional" in f.read()


def test_export_operacional_csv_email_operacional():
    """2026-04-27: botão Exportar planilha (CSV UTF-8) na tela operacional."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, encoding="utf-8") as f:
        html = f.read()
    assert "exportOperacionalCsv" in html
    assert "exportarOperacionalListaCsv" in html
    assert "__oraculoExportLista" in html
    assert "threadsUnionParaExport" in html
    assert "Data da extração" in html
    assert "nomeArquivoExtracaoEmailCsv" in html
    assert "extracao_de_email_" in html
    assert "linhasCsvComAgrupamentoAssunto" in html
    assert "chaveAgrupamentoAssuntoExport" in html
    assert "Agrupamento automático por assunto semelhante" in html
    assert "__oraculoCardAgrupPorTid" in html
    # Snapshot: Não resolvidos com ?data= também em modo busca (registro 2026-03-30).
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    assert "data_ref_para_nao_resolvidos" in code
    assert "(data_ref_para_nao_resolvidos - dt).days >= 7" in code
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        assert "montagem_api_dados_snapshot" in f.read()


def test_api_nao_resolvidos_busca_respeita_data_param():
    """2026-04-02: /api/dados com ?busca=1&data= usa a mesma DATA REF para Não resolvidos que ?data= (snapshot)."""
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    assert "data_ref_para_nao_resolvidos" in code
    assert "busca_ativa" in code
    assert "(data_ref_para_nao_resolvidos - dt).days >= 7" in code


def test_api_exclui_filtrado_por_data_com_data_ref_exceto_busca():
    """2026-04-17: com ?data=, FILTRADO_POR_DATA não entra nos KPIs; ?busca=1 mantém para localizar fio."""
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    assert "if not busca_ativa:" in code
    assert "excluir_cadoc.append(\"FILTRADO_POR_DATA\")" in code or "excluir_cadoc.append('FILTRADO_POR_DATA')" in code
    assert "not busca_ativa and not data_filtro_raw" not in code
    assert "if not (data_filtro_raw and str(data_filtro_raw).strip()):" in code


def test_api_desativa_persist_saida_aguardando_env():
    """Invariante "saiu de PENDENTE não volta": ``/api/dados`` nunca despromove
    AGUARDANDO → PENDENTE por nova mensagem (a antiga lógica condicional foi
    removida). O comentário no fonte deve documentar a remoção e referenciar
    a triagem como única responsável pela re-classificação.
    """
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    # A chamada ao persistor de saída automática NÃO pode existir no caminho
    # `/api/dados` (montagem_api_dados_snapshot); a despromoção viola a regra.
    assert "_persistir_saida_aguardando_por_nova_mensagem" not in code, (
        "painel_operacional_snapshot.py não pode chamar "
        "_persistir_saida_aguardando_por_nova_mensagem — viola a regra "
        "'saiu de PENDENTE não volta'."
    )
    assert "_tids_aguardando_com_nova_mensagem" not in code, (
        "painel_operacional_snapshot.py não pode invocar "
        "_tids_aguardando_com_nova_mensagem — usado apenas pela triagem."
    )
    # Documentação obrigatória da invariante na fonte
    assert "saiu de PENDENTE não volta" in code


def test_api_dados_concluido_alinha_status_processo_guard_aguardando():
    """2026-04-02: concluídas fechadas forçam CONCLUÍDO no payload; aguardando não sobrepõe sem reabertura."""
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    assert "status_processo\"] = \"CONCLUÍDO\"" in code or "status_processo'] = 'CONCLUÍDO'" in code
    assert "tid in aguardando_set and not (" in code
    assert "reaberta_apos_conclusao" in code


def test_api_dados_trava_mesma_data_ref_classificacao():
    """2026-04-02: vista ``?data=D`` não reverte a PENDENTE no dia D se classificação gravada em D."""
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_dt_trava_classificacao_dia" in code
    assert "travou_concluido" in code
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        assert "def _data_civil_em_registro" in f.read()


def test_imutabilidade_vista_ref_snapshot_e_marcacao_pre_conclusao():
    """2026-04-27: vista REF < data_conclusão — não herdar CONCLUÍDO global; campos em concluir_thread."""
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        code = f.read()
    assert "aplicou_historico_ref" in code
    assert "marcacao_aguardante_pre_conclusao" in code
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        body = f.read()
    assert "marcacao_aguardante_pre_conclusao" in body
    assert "origem_aguardante_triagem_auto" in body


def test_api_dados_usa_snapshot_unico_fonte_operacional():
    """2026-04-28: GET /api/dados delega a montagem_api_dados_snapshot (mesma lógica que estatísticas)."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "def api_dados(" in code
    assert "montagem_api_dados_snapshot(" in code
    assert "modo_leitura_gestacao=False" in code


def test_executar_tudo_preserva_dias_e_limpar_opcional():
    """2026-04-02: um dia civil → incremental + data-ref + pular 9b; limpeza antes opcional."""
    path_et = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_et, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_aplicar_preservacao_dias_ja_subidos_se_um_dia" in code
    assert "_executar_limpar_periodo_opcional" in code
    assert "ORACULO_LIMPAR_PERIODO_ANTES" in code
    assert "ORACULO_SUBIR_ALTERAR_DIAS_ANTERIORES" in code
    assert "ORACULO_EXECUTAR_9B_RESOLVER_AGUARDANDO" in code


def test_executar_tudo_refazer_dia_apaga_e_sobe():
    """2026-04-02: ORACULO_REFazer_DIA limpa o dia e define período antes do pipeline."""
    path_et = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_et, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_aplicar_refazer_um_dia_relimpar_e_periodo" in code
    assert "ORACULO_REFazer_DIA" in code
    assert "Refazer dia" in code


def test_script_diagnostico_thread_operacional_existe():
    """2026-04-02: fact-check 03 + triagem RB em memória por threadId/assunto."""
    path_d = os.path.join(RAIZ, "scripts", "diagnostico_thread_operacional.py")
    assert os.path.isfile(path_d)
    with open(path_d, "r", encoding="utf-8") as f:
        s = f.read()
    assert "triar(" in s and "CADOC_TRIAGEM_RETORNO_BACEN" in s and "--data-ref" in s


def test_script_snapshot_operacional_existe():
    """2026-04-17: snapshot criar/restaurar/listar para 02, 03, aguardando, concluídas."""
    path_s = os.path.join(RAIZ, "scripts", "snapshot_operacional.py")
    assert os.path.isfile(path_s)
    with open(path_s, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def cmd_criar" in s and "def cmd_restaurar" in s
    assert "threads_aguardando.json" in s and "threads_concluidas.json" in s
    assert "sub.add_parser(\"criar\"" in s


def test_operacional_busca_lista_unificada_status():
    """2026-03-30: com Buscar, lista mostra todos os status que batem no dia."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "threadsListaBuscaUnificada" in html
    assert "q ? \"busca\"" in html or 'q ? "busca"' in html


def test_operacional_toast_data_ref_casos_vs_eventos():
    """2026-04-02: toast ao filtrar por data distingue casos (fios) de eventos na API."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "casos ·" in html and "eventos (vários eventos podem ser o mesmo fio)" in html
    assert "eventos na API ·" in html and "casos (fios distintos)" in html


def test_operacional_ver_concluidos_e_kpi_role_button():
    """2026-04-15: Ver Concluídos / Atualizar / KPI Concluídos expostos a a11y (role button, aria-label)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="verConcluidos"' in html and 'role="button"' in html
    assert 'id="verConcluidos"' in html and "Ver Concluídos — alternar" in html
    assert 'id="refresh"' in html and 'aria-label="Atualizar dados"' in html
    assert 'id="kpiCardConcluidos"' in html and "Concluídos — casos resolvidos" in html


def test_operacional_kpi_concluidos_igual_mensagem_n_concluidos_dedup_par():
    """2026-04-27: N na mensagem de lista vazia = KPI (latestPorCasoOperacionalDedupPar), não Object.keys."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert (
        "const numConcluidos = latestPorCasoOperacionalDedupPar(threadsConcluidos).length"
        in html
    )
    assert "Object.keys(threadsConcluidos).length" not in html


def test_operacional_cartao_overrides_painel_estado():
    """2026-04-27: categoria/status por fio em painel_estado; API + UI."""
    path_paths = os.path.join(RAIZ, "scripts", "paths.py")
    with open(path_paths, "r", encoding="utf-8") as f:
        paths_src = f.read()
    assert 'F_CARTAO_OVERRIDES  = os.path.join(PAINEL_DIR, "cartao_overrides.json")' in paths_src
    assert "def load_cartao_overrides" in paths_src
    assert "def save_cartao_overrides" in paths_src

    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "/api/cartao_override" in code
    assert "_patch_cadoc_desde_cartao_overrides" in code
    assert "_aplicar_cartao_overrides_nos_sets" in code
    assert '"cartao_overrides": cartao_overrides' in code

    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="mCadocChip"' in html
    assert 'id="mStatusChip"' in html
    assert "z-index: 100000" in html and "#popoverCartaoCadoc" in html
    assert "portal.appendChild(popCad)" in html and "popoverCartaoStatus" in html
    assert "initCartaoOverrideChips" in html
    assert "CARTAO_OVERRIDES = payload.cartao_overrides" in html
    assert "async function salvarCartaoOverride" in html
    assert "fecharModalApos" in html and "closeModal" in html


def test_operacional_busca_respeita_data_ref():
    """2026-03-30: com DATA REF, Buscar não chama loadDataParaBusca (só filtra o dia)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    i = html.find('getElementById("q").addEventListener("input"')
    assert i != -1
    bloco = html[i : i + 900]
    assert "if (temData)" in bloco and "render();" in bloco and "return;" in bloco


def test_operacional_busca_id_ajusta_aba():
    """2026-03-30: busca só ID numérico alinha aba KPI; limpar busca recarrega DATA REF sem flash."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "maybeSelectFilterForSoloIdNumeric" in html


def test_script_patch_ddr_rd_moedas_um_prazo_existe():
    """2026-04-02: patch local JSON RD_Moedas — um prazo DDR 19/02 (remove 28/02 falso)."""
    path_sc = os.path.join(RAIZ, "scripts", "patch_json_ddr_rd_moedas_um_prazo.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "GMTHRID_1857918934374910718" in s
    assert "91935" in s and "19/02/2026" in s


def test_script_patch_retorno_bacen_91937_existe():
    """2026-04-02: patch local JSON Sefer DLO critica → RETORNO_BACEN (id 91937)."""
    path_sc = os.path.join(RAIZ, "scripts", "patch_json_retorno_bacen_91937.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "91937" in s and "RETORNO_BACEN" in s and "GMTHRID_1856203160807796370" in s


def test_matriz_sec6_regra_espelho_cluster_documentada():
    """2026-04-17: §6 regra espelho (Mirae 19/02 + casos similares) para automação futura."""
    path = os.path.join(RAIZ, "documentações", "MATRIZ_DECISOES_DDR_4111_E_EXCECOES.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "Regra espelho" in t and "automação futura" in t.lower()


def test_matriz_dli_wise_escopo_unico_dli():
    """2026-04-02: Wise mesmo fio — decisão documentada: caso só no âmbito DLI."""
    path = os.path.join(RAIZ, "documentações", "MATRIZ_DECISOES_DLI.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "GMTHRID_1857677212096008336" in t
    assert "âmbito DLI" in t or "escopo único DLI" in t
    assert "91961" in t and "92010" in t


def test_matriz_dlo_rascunho_23_documentado():
    """2026-04-02: matriz DLO dia 23 + Remitly/Planner; Wise fora do escopo DLO (só DLI)."""
    path = os.path.join(RAIZ, "documentações", "MATRIZ_DECISOES_DLO.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "DLO_2061" in t and "2026-02-23" in t
    assert "GMTHRID_1857918971250548150" in t
    assert "GMTHRID_1857677212096008336" in t
    assert "GMTHRID_1857679411473939866" in t
    assert "Aguardando (Finaud)" in t and "§3.5" in t
    assert "Rodrigo" in t and "Andrea" in t
    assert "Fora do escopo DLO" in t or "só em DLI" in t
    assert "DLI_2062" in t
    assert "triagem_auto_dlo.py" in t


def test_matriz_sec31_transmitido_bacen_concluido_documentado():
    """2026-04-18: §3.1 «transmitido no BACEN» → Concluído (cliente ou Finaud)."""
    path = os.path.join(RAIZ, "documentações", "MATRIZ_DECISOES_DDR_4111_E_EXCECOES.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "§3.1" in t
    assert "transmitido no BACEN" in t.lower()
    assert "GMTHRID_1857938643836228628" in t


def test_script_exportar_lista_ddr4111_validacao_excel_existe():
    """2026-04-16: exporta índice DDR/4111 dia 23 para Excel em documentações."""
    path_sc = os.path.join(RAIZ, "scripts", "exportar_lista_ddr4111_validacao_excel.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "DDR_4111_OPERACIONAL_2026-02-23_LISTA_VALIDACAO.xlsx" in s
    assert "DDR_4111_OPERACIONAL_2026-02-23_VALIDACAO_TRIAGEM.md" in s
    assert "Bola_pos_triagem" in s and "Interacao_evento_23_contatos" in s


def test_texto_imagens_cache_modulo_e_documentacao_limpar():
    """2026-04-08: cache persistente texto_imagens — módulo + limpar telas não apaga esse JSON."""
    path_mod = os.path.join(RAIZ, "scripts", "texto_imagens_cache.py")
    assert os.path.isfile(path_mod)
    with open(path_mod, "r", encoding="utf-8") as f:
        m = f.read()
    assert "cache_texto_imagens_validado.json" in m
    assert "def load_por_id" in m and "def merge_id" in m
    path_limpar = os.path.join(RAIZ, "scripts", "limpar_dados_telas_painel.py")
    with open(path_limpar, "r", encoding="utf-8") as f:
        lp = f.read()
    assert "cache_texto_imagens_validado" in lp
    path_02 = os.path.join(RAIZ, "scripts", "02_corrigir_anexos_resposta_finaud.py")
    with open(path_02, "r", encoding="utf-8") as f:
        s02 = f.read()
    assert "_preservar_ocr_no_cache" in s02 and "texto_imagens_cache" in s02
    path_seed = os.path.join(RAIZ, "scripts", "seed_cache_texto_imagens_de_03.py")
    assert os.path.isfile(path_seed)
    with open(path_seed, "r", encoding="utf-8") as f:
        assert "--todos-backups" in f.read()
    path_tic = os.path.join(RAIZ, "scripts", "texto_imagens_cache.py")
    with open(path_tic, "r", encoding="utf-8") as f:
        tic = f.read()
    assert "merge_por_id_longest" in tic and "write_por_id" in tic


def test_limpar_dados_telas_painel_empty_02_e_correlacoes():
    """2026-04-02: limpar telas — 02 com threads_processadas/resumo; correlacoes com metadados do 13."""
    path_sc = os.path.join(RAIZ, "scripts", "limpar_dados_telas_painel.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "_empty_02_classificador" in s
    assert '"threads_processadas"' in s and '"resumo"' in s
    assert "_empty_correlacoes" in s
    assert "total_com_correlacao_fog" in s
    assert "mapeamento_regras_negocio.json" in s and "PROTEGIDOS" in s


def test_script_aplicar_indice_basileia_suporte_existe():
    """2026-04-02: script alinha 02/03/threads_aguardando para ver SUPORTE na tela sem reprocessar tudo."""
    path_sc = os.path.join(RAIZ, "scripts", "aplicar_indice_basileia_suporte_json.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "classificacao_ajustada_em" in s
    assert "--dry-run" in s
    assert "threads_aguardando" in s
    assert "RE_S5_ASSUNTO" in s
    assert "match_regra_cadoc_por_assunto" in s


def test_classificador_indice_basileia_assunto_suporte():
    """2026-04-02: assunto Índice/Indice Basileia força SUPORTE antes de identificar_cadoc."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert "assunto_indice_basileia_suporte" in code
    assert "Assunto Índice Basileia → SUPORTE" in code


def test_classificador_prazo_ddr_dia_hifen_e_drsac_nao_ddr_por_tvm():
    """
    2026-04-23: (1) «mes» em «remessas» não rejeita DIARIA; (2) intervalo 19/02-20/02 gera prazos;
    (3) DRSAC no assunto → categoria DRSAC (TVM no corpo não força DDR); (4) FORCAPITAL/PROJEÇÃO;
    mapeamento com prazo D+5 para DRSAC e FORCAPITAL.
    """
    import importlib.util
    p05 = os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    with open(p05, "r", encoding="utf-8") as f:
        c05 = f.read()
    assert "_match_anchors_in_context" in c05
    assert "padrao_intervalo_hifen_barras" in c05
    assert "assunto_contem_marca_drsac" in c05
    assert "texto_indica_forcapital" in c05
    assert "cadoc\": \"DRSAC\"" in c05 or '"cadoc": "DRSAC"' in c05

    mpath = os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json")
    with open(mpath, "r", encoding="utf-8") as f:
        oq = json.load(f).get("O_QUE_ESTA_SENDO_ANALISADO", {})
    dr = (oq.get("documentos_regulatorios_prazos") or {}).get("DRSAC") or {}
    fc = (oq.get("documentos_regulatorios_prazos") or {}).get("FORCAPITAL") or {}
    assert dr.get("prazo") == "D+5_UTIL"
    assert fc.get("prazo") == "D+5_UTIL"
    det = oq.get("DETECCAO_INTELIGENTE_CADOC") or {}
    assert "DRSAC" in det and "FORCAPITAL" in det

    spec = importlib.util.spec_from_file_location("cl05", p05)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    V = mod.ValidadorContextual
    v0 = V(oq)
    assert v0.assunto_contem_marca_drsac("Re: [Traders] DRSAC — dúvida")
    assert v0.texto_indica_forcapital("Fwd: FORCAPITAL", "sem corpo")
    assert v0.texto_indica_forcapital("x", "relatório de projeção anual")
    assert not V._match_anchors_in_context(V.ANCORAS_MENSAIS, "2 - 20/02. seguem as remessas ")
    assert V._match_anchors_in_context(V.ANCORAS_MENSAIS, "remessa de janeiro/2026")

    from datetime import datetime
    with open(os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json"), encoding="utf-8") as f:
        regras = json.load(f).get("O_QUE_ESTA_SENDO_ANALISADO", {})
    fer = []
    for d in regras.get("feriados_nacionais", []):
        try:
            fer.append(datetime.strptime(d, "%Y-%m-%d").date())
        except Exception:
            pass
    N = mod.NormalizadorDatas(2026, fer)
    ass = "Re: DDR DIA 19/02 - 20/02. Seguem as remessas 19 e 20/02/2026."
    ref = datetime(2026, 2, 24)
    extr = N.extrair_todas_datas(ass, ref)
    assert len(extr) >= 2
    v = V(regras)
    ok = sum(
        1
        for t in extr
        if v.validar_data_para_contexto(
            t[0], t[1], t[2], "DIARIA", t[3] if len(t) > 3 else False, t[4] if len(t) > 4 else ""
        )
    )
    assert ok >= 2


def test_classificador_ignorar_newsletter_meta_utm_mapeamento():
    """2026-04-23: FILTROS com por_texto_mensagem_regex + deve_ignorar_mensagem_marketing no 05 (Meta m4d-newsletter)."""
    mpath = os.path.join(RAIZ, "data", "json", "config", "mapeamento_regras_negocio.json")
    with open(mpath, "r", encoding="utf-8") as f:
        oq = json.load(f).get("O_QUE_ESTA_SENDO_ANALISADO", {})
    fil = oq.get("FILTROS_DE_IGNORAR") or {}
    assert fil.get("por_texto_mensagem_regex")
    assert "STAY AHEAD" in (fil.get("por_assunto") or [])

    p05 = os.path.join(RAIZ, "scripts", "05_classificar_emails_regulatorio.py")
    with open(p05, "r", encoding="utf-8") as f:
        c05 = f.read()
    assert "deve_ignorar_mensagem_marketing_ou_bloqueio" in c05
    import importlib.util
    spec = importlib.util.spec_from_file_location("cl05b", p05)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    v = mod.ValidadorContextual(oq)
    ass = "Stay Ahead: Essential Meta Updates for Developers"
    blob = "https://developers.meta.com/?utm_source=email&utm_medium=m4d-newsletter-feb26"
    assert v.deve_ignorar_mensagem_marketing_ou_bloqueio(ass, blob[:200], blob)


def test_classificador_encaminhamento_interno_finaud_contato_e_pendencia():
    """2026-04-07: Finaud→Finaud no envelope + Fwd no corpo — extrair cliente do encaminhado; pendência FINAUD."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert "extrair_primeiro_email_externo_apos_encaminhamento" in code
    assert "Encaminhamento interno Finaud" in code
    assert 'elif o_lado == "FINAUD" and d_lado == "FINAUD":' in code


def test_api_fallback_cliente_fwd_interno_json_antigo():
    """2026-04-08: /api/dados e /api/threads infere cliente (HTML mailto + contato nas mensagens)."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_aplicar_fallback_cliente_encaminhamento_interno_api" in code
    assert "_api_fwd_primeiro_email_externo_apos_marcador" in code
    i = code.find("def _aplicar_fallback_cliente_encaminhamento_interno_api")
    assert i != -1
    bloco = code[i : i + 2800]
    assert "_emails_lado_cliente_do_evento(e)" in bloco
    assert "_api_contato_origem_finaud_para_fallback" in bloco
    assert "_api_aplicar_cliente_empresa_responsavel_interno_finaud" in bloco
    assert "_painel_preservar_empresa_responsavel_fallback" in code
    assert "_api_corpo_limpo_topo_sem_email_externo" in code
    assert "mailto:" in code and "_api_email_externo_valido_fwd" in code
    j = code.find("def _enriquecer_threads_com_empresa")
    assert j != -1
    assert "_aplicar_fallback_cliente_encaminhamento_interno_api(t)" in code[j : j + 2200]


def test_classificador_assunto_s5_prioridade_identificar_cadoc():
    """2026-04-02: palavra S5 no assunto → S5 em identificar_cadoc antes de DLO pelo corpo."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert r're.search(r"(?i)\bS5\b", assunto)' in code
    assert 'return "S5", "S5"' in code


def test_classificador_erro_na_tela_nao_e_retorno_bacen():
    """2026-03-30: suporte UI (erro na tela / acesso) suprime Retorno Bacen no 04."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert "assunto_indica_suporte_erro_tela_ou_acesso" in code
    assert "assunto_indica_erro_ou_erros_dlo_retorno_bacen" in code


def test_classificador_mes_sozinho_ignora_de_fev_em_data_extenso():
    """2026-04-02: «23 de fev. de 2026» não gera 28/02 via mês sozinho; PADRÃO 6 aceita fev. abreviado."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    expected_pat = r"padrao_extenso = r'(\d{1,2})\s+de\s+([a-zçã]+)\.?\s+de\s+(\d{2,4})'"
    assert expected_pat in code, "PADRÃO 6 deve aceitar mês abreviado com ponto (fev.)"
    assert "não é competência solta" in code and r"\d{1,2}\s+de\s+$" in code


def test_classificador_mandatorio_critica_corpo_mais_documento_retorno_bacen():
    """2026-04-02: critica/retorno bacen no texto + DLO/DDR… força RETORNO_BACEN; RD_* continua a suprimir."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert "texto_mandatorio_retorno_bacen_critica_e_documento" in code
    assert "Tipificação por corpo: critica/retorno bacen + documento" in code
    assert "texto_mandatorio_retorno_bacen_critica_e_documento(" in code
    assert "tem_indicador_rd_ddr" in code


def test_retorno_bacen_prazo_so_d3_uteis_sem_extrair_texto():
    """2026-04-02: Retorno Bacen usa só calculador D+3_UTIL; sem _resolver_prazo no corpo."""
    path_04 = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_04, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_resolver_prazo_retorno_bacen" not in code
    assert 'calculador.calcular_prazo_limite(data_email_dt, "RETORNO_BACEN")' in code


def test_integrador_08_corpo_evento_e_threads_concluidas_sem_nova_msg():
    """2026-03-30: eventos com corpo do 02; threads concluídas sem nova msg permanecem no 03."""
    path_08 = os.path.join(RAIZ, "scripts", "08_integrador_dados.py")
    with open(path_08, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_corpo_evento_a_partir_classificador" in code
    assert "thread_concluida_sem_nova_msg" in code


def test_modal_renderModalLocal_usa_corpo_limpo():
    """2026-03-30: fallback local do modal prioriza corpo_limpo com emailBodyToReadableTextFull."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    i = html.find("function renderModalLocal")
    assert i != -1
    bloco = html[i : i + 8000]
    assert "corpo_limpo" in bloco
    assert "emailBodyToReadableTextFull" in bloco
    assert "linhaDeParaModal(email)" in bloco
    assert "function linhaDeParaModal" in html


def test_modal_fallback_achata_eventos_para_exibir_texto_imagens():
    """2026-03-30: renderModalLocal deve achatar eventos (card) com mensagens[] para mostrar texto_imagens."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "flattenThreadRowsToMessages" in html
    assert "THREADS[threadId] vem de groupByThread(ALL_DATA)" in html


def test_ocr_modal_ficha_sem_imagem_e_tabelas():
    """2026-04: bloco OCR em layout ficha, sem <img>, com heurística de tabelas."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "msg-texto-imagens--ficha" in html
    assert "ocr-ficha-table" in html
    assert "Sem imagem no painel" in html


def test_ocr_crd_tabelas_seis_colunas_historico():
    """2026-04-02: prints CRD (Erro DLO) renderizam tabela 6 colunas + Histórico como no BC (tema escuro)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "ocrTryRenderTabelasCrd" in html
    assert "Protocolo de resposta" in html
    assert "ocr-ficha-table--crd" in html
    assert "ocrCrdHtmlHistorico" in html
    i = html.find(".ocr-ficha-table--crd{")
    assert i != -1
    bloco = html[i : i + 400]
    assert "table-layout:auto" in bloco
    assert "ocr-crd-col-comp" in html and "min-width:6.75rem" in html


def test_imagens_para_cadoc_tamanho_minimo_8kb():
    """2026-03-30: 09 inclui imagens inline ~8–20 KB (ex. Retorno Bacen) alinhadas ao coletor 01."""
    path_json = os.path.join(RAIZ, "data", "json", "mapeamento_regras_negocio.json")
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    o_que = data.get("O_QUE_ESTA_SENDO_ANALISADO") or data
    img = o_que.get("IMAGENS_PARA_CADOC") or {}
    assert int(img.get("tamanho_minimo_bytes", 0)) == 8192


def test_ocr_ficha_omitir_ruido_logo_banvox():
    """2026-03-31: não exibir ficha OCR só com logo/assinatura (Banvex + image00N.png)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "ocrTextoEhRuidoAssinaturaOuLogo" in html
    assert "banvex" in html.lower() or "banvox" in html.lower()


def test_ocr_sanitizar_prefixo_crd_operacional():
    """2026-03-30: modal corta ruído de barra do CRD e omite OCR pendente / logo BCP (alinhado ao 09)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "ocrSanitizarPrefixoTelaCrd" in html
    assert "ocrNormalizarInterfaceCrd" in html
    assert "bcp)" in html.lower() or "orum" in html.lower()


def test_modal_corta_assinatura_cid_inline():
    """2026-03-31: corpo sem bloco após [cid: (assinatura Outlook) no template."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "cortarTextoAposPrimeiroCidInline" in html
    assert "emailBodyToReadableTextFull" in html


def test_corpo_limpo_modal_aplica_strip_disclaimer_global():
    """2026-04-02: com corpo_limpo, exibição aplica strip + filtro como sem limpo; disclaimer EN genérico."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    i = html.find("function emailBodyToReadableTextFull")
    assert i != -1
    bloco = html[i : i + 1200]
    assert "filterSignatureFromAttachment(stripEmailBoilerplate" in bloco
    assert "cortarRodapeAssinaturaTipico" in html
    assert "This email is confidential" in html
    assert "sanitizarTextoCorpoParaExibicao" in html
    assert "sanitizarTextoCorpoParaExibicao(corpoSrc)" in html


def test_modal_corta_encerramento_cordial_at_te_e_disclaimer_esta_mensagem():
    """2026-04: strip corta a partir de Atenciosamente/At.te/Att e bloco «Esta mensagem pode conter»."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "function cortarCorpoAposEncerramentoCordial" in html
    assert "cortarCorpoAposEncerramentoCordial(t)" in html
    assert "function cortarRodapeAssinaturaInline" in html
    assert "cortarRodapeAssinaturaInline(out)" in html
    assert "Esta mensagem pode conter" in html
    path_08 = os.path.join(RAIZ, "scripts", "08_integrador_dados.py")
    with open(path_08, "r", encoding="utf-8") as f:
        c08 = f.read()
    assert "_cortar_apos_encerramento_cordial" in c08
    assert "_cortar_rodape_assinatura_inline" in c08


def test_modal_historico_oculta_cauda_citacao_redundante():
    """2026-04-02: histórico corta cauda após De:/Em escreveu só se redundante com msgs anteriores (citacaoEhRedundante)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "splitCorpoTopoECauda" in html
    assert "corpoTextoParaModalOcultandoCaudaCitacaoRedundante" in html
    assert "msgsAnterioresCronologicas" in html


def test_modal_corpo_principal_solo_topo_quando_encaminhados():
    """2026-04-02: com encaminhados[], corpoTextoParaModal usa só topo (splitCorpoTopoECauda) para não duplicar a pilha."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    i = html.find("function corpoTextoParaModal")
    assert i != -1
    bloco = html[i : i + 900]
    assert "msg.encaminhados" in bloco or "encList" in bloco
    assert "splitCorpoTopoECauda(msg.corpo" in bloco
    assert "encaminhados: []" in bloco
    assert "msgSoloTopo" in bloco


def test_modal_corpo_xml_crd_extracao_plana_sem_innerhtml():
    """2026-04-02: texto plano com <?xml/respostaCRD força pipeline plano em Modal/Full/sanitizar."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "function corpoTextoParecePlanoComXmlCitado" in html
    assert "respostaCRD" in html
    assert "corpoTextoParecePlanoComXmlCitado(html)" in html
    i = html.find("function emailBodyToReadableTextModal")
    assert i != -1
    assert "corpoTextoParecePlanoComXmlCitado(html)" in html[i : i + 800]
    i2 = html.find("function sanitizarTextoCorpoParaExibicao")
    assert i2 != -1
    bloco = html[i2 : i2 + 650]
    assert "corpoTextoParecePlanoComXmlCitado(t)" in bloco


def test_modal_corpo_texto_para_modal_fallback_limpo_vazio():
    """2026-04-02: corpoTextoParaModal usa modalText quando limpo sanitizado perde demais."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "limpoSanPerdeuDemais" in html
    assert "antes <= 28" in html


def test_coletor_01_inline_grande_exige_dimensoes_conteudo():
    """2026-03-31: inline ≥ 8 KB não basta — filtra logo de assinatura por dimensões (ex. Banvox image004)."""
    path_01 = os.path.join(RAIZ, "scripts", "01_coletor_email.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_imagem_inline_dimensoes_sugerem_conteudo" in code
    assert "90_000" in code or "90000" in code
    assert "size >= MIN_TAMANHO_IMAGEM_INLINE_BYTES" in code


def test_script_02_preserva_anexos_fwd_finaud():
    """2026-04-02: 02 não limpa anexos de resposta FINAUD quando assunto é Fwd:/FW: (inline do próprio forward)."""
    path_02 = os.path.join(RAIZ, "scripts", "02_corrigir_anexos_resposta_finaud.py")
    with open(path_02, "r", encoding="utf-8") as f:
        code = f.read()
    assert "assunto_eh_encaminhamento" in code
    assert "fwd:" in code and "continue" in code


def test_script_02_preserva_anexos_cliente_via_suporte_reply_to_externo():
    """2026-04-02: 02 não apaga inline do cliente quando From é lista @finaud mas Reply-To é externo (ex. 91937 Sefer)."""
    path_02 = os.path.join(RAIZ, "scripts", "02_corrigir_anexos_resposta_finaud.py")
    with open(path_02, "r", encoding="utf-8") as f:
        code = f.read()
    assert "nao_apagar_anexos_aparenta_mensagem_de_cliente" in code
    assert "reply_to_indica_remetente_externo_nao_finaud" in code
    assert "remetente_indica_cliente_via_canal_finaud" in code


def test_coletor_01_content_id_sem_disposition_inline():
    """2026-04-02: image/* com Content-ID conta como inline sem Content-Disposition: inline (cid no próprio MIME)."""
    path_01 = os.path.join(RAIZ, "scripts", "01_coletor_email.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "parte_imagem_inline_semantica" in code
    assert "Content-ID" in code and "Content-Id" in code
    assert "parte_imagem_inline_semantica(part)" in code


def test_coletor_01_critica_rb_relaxa_inline_peso():
    """2026-04-02: Retorno Bacen / crítica DLO: inline ≥ 28 KB entra mesmo com dimensões modestas (print BC estreito)."""
    path_01 = os.path.join(RAIZ, "scripts", "01_coletor_email.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "contexto_rb_ou_critica_dlo" in code
    assert "28 * 1024" in code
    assert "permitir_imagem_inline_corpo" in code


def test_coletor_01_corpus_dlo_inconsistencia_permite_inline_cid():
    """2026-04-22: «Informe 2061… inconsistências» activa gravar imagens inline (cid) sem a palavra «crítica»."""
    path_01 = os.path.join(RAIZ, "scripts", "01_coletor_email.py")
    with open(path_01, "r", encoding="utf-8") as f:
        code = f.read()
    assert "inconsist" in code and "corpus_indica_critica_em_relatorio_dlo" in code


def test_mapeamento_retorno_bacen_termos_incluem_informe_2061():
    """2026-04-22: TIPIFICACAO_RETORNO_BACEN inclui assuntos «Informe 2061/2062» e «inconsistência»."""
    path_json = os.path.join(RAIZ, "data", "json", "mapeamento_regras_negocio.json")
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    o_que = data.get("O_QUE_ESTA_SENDO_ANALISADO") or data
    tip = o_que.get("TIPIFICACAO_RETORNO_BACEN") or {}
    terms = [t.lower() for t in (tip.get("termos_assunto") or [])]
    assert "informe 2061" in terms
    assert "informe 2062" in terms


def test_09_normaliza_ocr_1876_para_876_rwaopad():
    """2026-04-07: 09 normaliza artefato OCR 1876.xx → 876.xx (árvore DLO/RWAOPAD)."""
    path_09 = os.path.join(RAIZ, "scripts", "09_enriquecer_texto_imagens.py")
    with open(path_09, "r", encoding="utf-8") as f:
        code = f.read()
    assert "_normalizar_ocr_prefixo_fantasma_conta_876" in code
    assert r"\b1876\." in code
    assert "_normalizar_ocr_interface_crd" in code


def test_09_enriquecer_flag_ids_e_sync_eventos():
    """2026-04: 09 aceita --ids e sincroniza texto_imagens para eventos."""
    path_09 = os.path.join(RAIZ, "scripts", "09_enriquecer_texto_imagens.py")
    with open(path_09, "r", encoding="utf-8") as f:
        c = f.read()
    assert '"--ids"' in c or "'--ids'" in c


def test_09_dimensoes_crd_estreita_retorno_bacen():
    """2026-04-10: 09 aceita capturas CRD estreitas (area+mx) para OCR Retorno Bacen."""
    path_09 = os.path.join(RAIZ, "scripts", "09_enriquecer_texto_imagens.py")
    with open(path_09, "r", encoding="utf-8") as f:
        code = f.read()
    assert "40_000" in code and "mx >= 300" in code


def test_oraculo_cenarios_pipeline_script_existe():
    """CLI cenários: apagar/acrescentar-dia/checklist e env ORACULO_DATA_* no executar_tudo."""
    path_cli = os.path.join(RAIZ, "scripts", "oraculo_cenarios_pipeline.py")
    assert os.path.isfile(path_cli)
    with open(path_cli, "r", encoding="utf-8") as f:
        c = f.read()
    assert "acrescentar-dia" in c and "checklist" in c and "limpar_periodo" in c
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "ORACULO_DATA_COLETA_INICIO" in ex and "ORACULO_DATA_LIMITE_EXCLUIR" in ex
    assert '"TRIAGEM_AUTO_DATA_REF"' in c
    assert 'ORACULO_PULAR_RESOLVER_AGUARDANDO_AUTO' in c
    assert "ORACULO_PULAR_RESOLVER_AGUARDANDO_AUTO" in ex
    assert "Limpeza GERAL" in c and "preservar-threads-painel" in c
    path_tr = os.path.join(RAIZ, "scripts", "triagem_auto_ddr4111.py")
    with open(path_tr, "r", encoding="utf-8") as f:
        assert "_strip_auto_para_tids" in f.read()


def test_triagem_strip_auto_para_tids_preserva_outros_threadids():
    """2026-04-17: strip seletivo — só remove auto dos threadId no conjunto."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _strip_auto_para_tids

    co = [
        {"threadId": "A", "origem_triagem_auto": True, "alvo_triagem_auto": "DDR4111"},
        {"threadId": "B", "origem_triagem_auto": True, "alvo_triagem_auto": "DDR4111"},
        {"threadId": "C", "origem_triagem_auto": False},
    ]
    out, n = _strip_auto_para_tids(co, "DDR4111", {"A"})
    assert n == 1
    assert len(out) == 2
    assert {r.get("threadId") for r in out} == {"B", "C"}


def test_triagem_strip_preserva_fecho_civil_anterior_ao_dia_ref():
    """2026-04-20: ao subir dia N+1, não apagar auto com data de fecho < dia_ref (KPI REF N)."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _strip_auto_para_tids

    dia = date(2026, 2, 24)
    ag = [
        {
            "threadId": "T1",
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_marcacao": "2026-02-23",
        },
        {
            "threadId": "T1",
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_marcacao": "2026-02-24",
        },
    ]
    out_ag, nag = _strip_auto_para_tids(
        ag, "RETORNO_BACEN", {"T1"}, dia_ref=dia, lista_aguardando=True
    )
    assert nag == 1
    assert len(out_ag) == 1
    assert out_ag[0].get("data_marcacao") == "2026-02-23"

    co = [
        {
            "threadId": "T2",
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_conclusao": "2026-02-23 10:00:00",
        },
        {
            "threadId": "T2",
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_conclusao": "2026-02-24 10:00:00",
        },
    ]
    out_co, nco = _strip_auto_para_tids(
        co, "RETORNO_BACEN", {"T2"}, dia_ref=dia, lista_aguardando=False
    )
    assert nco == 1
    assert len(out_co) == 1
    assert str(out_co[0].get("data_conclusao", "")).startswith("2026-02-23")


def test_triagem_registro_concluido_usa_dia_ref_quando_definido():
    """2026-04-20: data_conclusao automática alinha ao dia_ref (não ao relógio do servidor)."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _registro_concluido_auto

    r = _registro_concluido_auto(
        "X",
        3,
        "motivo",
        "RETORNO_BACEN",
        "C",
        alvo_triagem="RETORNO_BACEN",
        dia_fecho_operacional=date(2026, 2, 24),
    )
    assert str(r.get("data_conclusao", "")).startswith("2026-02-24")


def test_executar_tudo_cronometra_etapas():
    """2026-04-10: executar_tudo regista duração por etapa (perf_counter + resumo)."""
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        code = f.read()
    assert "time.perf_counter()" in code
    assert "tempos_etapas" in code
    assert "CRONOMETRAGEM POR ETAPA" in code


def test_triagem_auto_ddr4111_script_e_executar_tudo_opcional():
    """2026-04-02: triagem automática DDR/4111; executar_tudo com TRIAGEM_AUTO_DDR4111 após 9b."""
    path_sc = os.path.join(RAIZ, "scripts", "triagem_auto_ddr4111.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def run_triagem_ddr4111" in s
    assert "origem_triagem_auto" in s
    assert "def triar" in s
    assert "_sec5b_res_finaud_cliente" in s and "_nucleo_assunto_ddr" in s and "§6b" in s
    assert "_ultima_mensagem_finaud_para_cliente" in s and "_sec5c_finaud_corpo_conclusivo" in s
    assert "_finaud_pedido_insumos_a_cliente" in s and "§3-inv" in s
    assert "os.path.exists(os.path.join(BASE_DIR" in s and "PASTA_JSON" in s
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "TRIAGEM_AUTO_DDR4111" in ex
    assert "ORACULO_TRIAGEM_FILTRO_DATA_REF" in ex
    assert "_data_coleta_inicio_iso_triagem" in ex
    assert "triagem_auto_ddr4111" in ex
    assert "run_triagem_ddr4111" in ex
    assert "_executar_triagem_dli_9d" in ex
    assert "_executar_triagem_dlo_9e" in ex
    assert "_executar_triagem_retorno_bacen_9f" in ex
    assert "TRIAGEM_AUTO_DLO" in ex and "dlo_solo" in ex
    assert "TRIAGEM_AUTO_S5" in ex and "s5_on" in ex
    assert "TRIAGEM_AUTO_SUPORTE" in ex and "sup_on" in ex
    assert "TRIAGEM_AUTO_RETORNO_BACEN" in ex and "rb_on" in ex
    assert "CADOC_TRIAGEM_DLO" in s
    assert "CADOC_TRIAGEM_S5" in s
    assert "CADOC_TRIAGEM_SUPORTE" in s
    assert "CADOC_TRIAGEM_RETORNO_BACEN" in s
    assert "THREAD_IDS_EXCLUIR_TRIAGEM_DLO" in s
    assert "sec35_agradecimento_sem_msg_cliente_previa" in s
    assert "ag_resposta_cliente" in s and "RESPOSTA_CLIENTE" in s
    i_ddr = ex.find("if ddr_on:")
    assert i_ddr != -1
    bloco_ddr = ex[i_ddr : i_ddr + 2800]
    assert "run_triagem_ddr4111" in bloco_ddr
    assert "_executar_triagem_dli_9d" in bloco_ddr
    assert "_executar_triagem_dlo_9e" in bloco_ddr
    assert "_executar_triagem_s5_9g" in bloco_ddr
    assert "_executar_triagem_suporte_9h" in bloco_ddr
    assert "if rb_on:" in bloco_ddr
    assert "_executar_triagem_retorno_bacen_9f" in bloco_ddr


def test_triagem_auto_dli_script_e_executar_tudo_opcional():
    """2026-04-02: triagem DLI_2062; 9d em cadeia com DDR ou só com TRIAGEM_AUTO_DLI; alvo_triagem_auto DLI."""
    path_dli = os.path.join(RAIZ, "scripts", "triagem_auto_dli.py")
    assert os.path.isfile(path_dli)
    with open(path_dli, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def run_triagem_dli" in s
    assert "CADOC_TRIAGEM_DLI" in s and "_run_triagem_cadocs" in s
    assert '"DLI"' in s and '"triagem_auto_dli"' in s
    assert "aguardar_ultima_finaud_finaud=True" in s
    path_ddr = os.path.join(RAIZ, "scripts", "triagem_auto_ddr4111.py")
    with open(path_ddr, "r", encoding="utf-8") as f:
        ddr = f.read()
    assert "CADOC_TRIAGEM_DLI" in ddr and "alvo_triagem_auto" in ddr
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "TRIAGEM_AUTO_DLI" in ex
    assert "dli_solo" in ex and "elif dli_solo" in ex
    assert "9d. Triagem automática DLI_2062" in ex
    assert "triagem_auto_dli" in ex and "run_triagem_dli" in ex
    assert "_executar_triagem_dli_9d" in ex
    assert "_executar_triagem_dlo_9e" in ex


def test_matriz_retorno_bacen_rascunho_23_documentado():
    """2026-04-02: matriz Retorno Bacen + script triagem + threadIds snapshot 23/02."""
    path = os.path.join(RAIZ, "documentações", "MATRIZ_DECISOES_RETORNO_BACEN.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "RETORNO_BACEN" in t and "2026-02-23" in t
    assert "triagem_auto_retorno_bacen.py" in t
    assert "GMTHRID_1856203160807796370" in t
    assert "validar" in t.lower() and "TRIAGEM_AUTO_RETORNO_BACEN" in t
    assert "91937" in t and "92011" in t and "11 eventos" in t
    assert "Moneycorp" in t and "Finaud→Finaud" in t and "Rodrigo" in t


def test_classificador_primeiro_to_finaud_ff_e_script_reenvelope():
    """Envelope: 1.º To Finaud → F→F; script reaplicar 01→02 existe."""
    path_c = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_c, encoding="utf-8") as f:
        c = f.read()
    assert "def montar_contatos_origem_destino_para_item" in c
    assert "primeiro_to_em" in c and "contatos_somente_to" in c
    path_r = os.path.join(RAIZ, "scripts", "reaplicar_envelope_contatos_01_no_02.py")
    assert os.path.isfile(path_r)
    with open(path_r, encoding="utf-8") as f:
        r = f.read()
    assert "reaplicar_envelope_contatos_01_no_02" in r
    assert "09_enriquecer_texto_imagens" in r and "texto_imagens" in r


def test_classificador_preserva_cadoc_fora_do_periodo_env_var():
    """04 não reclassifica em massa FILTRADO_POR_DATA fora da janela quando preservação ligada."""
    path_c = os.path.join(RAIZ, "scripts", "04_classificador_regulatorio.py")
    with open(path_c, encoding="utf-8") as f:
        c = f.read()
    assert "ORACULO_PRESERVAR_CLASSIFICACAO_FORA_PERIODO" in c
    assert "PRESERVAR_CLASSIFICACAO_FORA_PERIODO" in c
    assert "def _analise_preservada_de_email_processado" in c
    assert "Preservação fora do período" in c
    assert "email_esta_no_periodo" in c and "_analise_preservada_de_email_processado(mapa_antigo" in c


def test_registro_pipeline_inclui_triagem_rb_apply():
    """Pipeline documentado: após 09, triagem RB --apply para não ficar só PENDENTE."""
    path = os.path.join(RAIZ, "REGISTRO_CORRECOES.md")
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "triagem_auto_retorno_bacen.py --apply" in t


def test_registro_explica_scripts_vs_json():
    """REGISTRO distingue .py (script) de JSON em data/json (prefixo 01/02/03)."""
    path = os.path.join(RAIZ, "REGISTRO_CORRECOES.md")
    with open(path, encoding="utf-8") as f:
        t = f.read()
    assert "## Scripts vs ficheiros JSON" in t
    assert "08_integrador_dados.py" in t and "03_integrador_dados_site.json" in t
    assert "04_classificador_regulatorio.py" in t


def test_integrador_08_preserva_texto_imagens_via_campo_02():
    """08 copia texto_imagens do 02; repõe vazios via cache + 03 backup; opt-out por env."""
    path = os.path.join(RAIZ, "scripts", "08_integrador_dados.py")
    with open(path, encoding="utf-8") as f:
        s = f.read()
    assert "texto_imagens" in s and 'msg.get("texto_imagens")' in s
    assert "restaurar_threads_se_vazio" in s
    assert "_mapa_texto_imagens_desde_03_dict" in s
    assert "INTEGRADOR_08_SEM_PRESERVAR_TEXTO_IMAGENS" in s
    assert "_sincronizar_texto_imagens_eventos_de_threads" in s


def test_triagem_auto_retorno_bacen_script_e_executar_tudo_opcional():
    """2026-04-02: triagem RETORNO_BACEN; 9f após 9h na cadeia DDR; só RB: TRIAGEM_AUTO_RETORNO_BACEN."""
    path_rb = os.path.join(RAIZ, "scripts", "triagem_auto_retorno_bacen.py")
    assert os.path.isfile(path_rb)
    with open(path_rb, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def run_triagem_retorno_bacen" in s
    assert "CADOC_TRIAGEM_RETORNO_BACEN" in s
    assert "sec35_agradecimento_sem_msg_cliente_previa=False" in s
    assert "aguardar_ultima_finaud_finaud=True" in s
    assert '"RETORNO_BACEN"' in s and '"triagem_auto_retorno_bacen"' in s
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "9h. Triagem automática SUPORTE" in ex
    assert "9f. Triagem automática Retorno Bacen" in ex
    assert "após 9h" in ex or "9h se DDR" in ex
    assert "triagem_auto_retorno_bacen" in ex


def test_triagem_auto_dlo_script_e_executar_tudo_opcional():
    """2026-04-02: triagem DLO_2062; 9e em cadeia; exclusão Wise; só DLO: TRIAGEM_AUTO_DLO."""
    path_dlo = os.path.join(RAIZ, "scripts", "triagem_auto_dlo.py")
    assert os.path.isfile(path_dlo)
    with open(path_dlo, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def run_triagem_dlo" in s
    assert "THREAD_IDS_EXCLUIR_TRIAGEM_DLO" in s
    assert "aguardar_ultima_finaud_finaud=True" in s
    assert "sec35_agradecimento_sem_msg_cliente_previa=True" in s
    assert '"DLO"' in s and '"triagem_auto_dlo"' in s
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "9e. Triagem automática DLO_2061" in ex
    assert "triagem_auto_dlo" in ex and "run_triagem_dlo" in ex


def test_triagem_auto_s5_script_e_executar_tudo_opcional():
    """2026-04-02: triagem S5; 9g após DLO com DDR; só S5: TRIAGEM_AUTO_S5; alvo_triagem_auto S5."""
    path_s5 = os.path.join(RAIZ, "scripts", "triagem_auto_s5.py")
    assert os.path.isfile(path_s5)
    with open(path_s5, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def run_triagem_s5" in s
    assert "CADOC_TRIAGEM_S5" in s and "_run_triagem_cadocs" in s
    assert "aguardar_ultima_finaud_finaud=True" in s
    assert "sec35_agradecimento_sem_msg_cliente_previa=True" in s
    assert '"S5"' in s and '"triagem_auto_s5"' in s
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "9g. Triagem automática S5" in ex
    assert "triagem_auto_s5" in ex and "run_triagem_s5" in ex
    assert "_executar_triagem_s5_9g" in ex


def test_triagem_auto_suporte_script_e_executar_tudo_opcional():
    """2026-04-02: triagem SUPORTE; 9h após S5 com DDR; só SUPORTE: TRIAGEM_AUTO_SUPORTE; alvo SUPORTE."""
    path_sup = os.path.join(RAIZ, "scripts", "triagem_auto_suporte.py")
    assert os.path.isfile(path_sup)
    with open(path_sup, "r", encoding="utf-8") as f:
        s = f.read()
    assert "def run_triagem_suporte" in s
    assert "CADOC_TRIAGEM_SUPORTE" in s and "_run_triagem_cadocs" in s
    assert "aguardar_ultima_finaud_finaud=True" in s
    assert "sec35_agradecimento_sem_msg_cliente_previa=True" in s
    assert '"SUPORTE"' in s and '"triagem_auto_suporte"' in s
    path_ex = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_ex, "r", encoding="utf-8") as f:
        ex = f.read()
    assert "9h. Triagem automática SUPORTE" in ex
    assert "triagem_auto_suporte" in ex and "run_triagem_suporte" in ex
    assert "_executar_triagem_suporte_9h" in ex


def test_triagem_suporte_ultima_fc_informativo_resposta_cliente():
    """2026-04-02: SUPORTE última F→C fora §5/§3-inv/§3.5 → Aguardando RESPOSTA_CLIENTE."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_SUPORTE, triar

    dados = {
        "threads": [
            {
                "threadId": "GMTHRID_TEST_SUPORTE_FC",
                "mensagens": [
                    {
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "corpo_limpo": "Como extrair o relatório? Pedido de apoio ao suporte.",
                        "data_iso": "2026-02-23",
                        "timestamp_epoch": 100,
                    },
                    {
                        "contato_origem": {"lado": "FINAUD"},
                        "contato_destino": {"lado": "CLIENTE"},
                        "corpo_limpo": "Estamos enviando o último realizado para o semestre anterior. O novo será em breve.",
                        "data_iso": "2026-02-23",
                        "timestamp_epoch": 200,
                    },
                ],
            }
        ],
        "eventos": [
            {
                "threadId": "GMTHRID_TEST_SUPORTE_FC",
                "cadoc": "SUPORTE",
                "cliente": "Warren",
                "titulo": "Re: Auditoria",
                "timestamp_epoch": 100,
                "lista_prazos": [
                    {
                        "data_base": "23/02/2026",
                        "prazo_limite": "02/03/2026",
                        "cadoc": "SUPORTE",
                    }
                ],
            }
        ],
    }
    co, ag, log = triar(
        dados,
        date(2026, 2, 23),
        CADOC_TRIAGEM_SUPORTE,
        True,
        alvo_triagem="SUPORTE",
        aguardar_ultima_finaud_finaud=True,
        sec35_agradecimento_sem_msg_cliente_previa=True,
    )
    assert not co
    assert len(ag) == 1
    assert ag[0].get("tipo") == "RESPOSTA_CLIENTE"
    assert any("Aguardando cliente (SUPORTE" in line for line in log)


def test_triagem_suporte_sec4e_obrigado_sem_remessa_f_c_concluido():
    """2026-04-23: §4e só cadoc SUPORTE — C→F só agradecimento após F→C informativo longo → Concluído; DRSAC não."""
    import copy
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_SUPORTE, triar

    tid_s = "GMTHRID_TEST_SUPORTE_4E"
    base_ev = {
        "threadId": tid_s,
        "cliente": "EQI",
        "titulo": "Re: Erro 4111",
        "timestamp_epoch": 300,
        "lista_prazos": [{"data_base": "23/02/2026", "prazo_limite": "02/03/2026", "cadoc": "SUPORTE"}],
    }
    msgs = [
        {
            "id": "m1",
            "contato_origem": {"lado": "CLIENTE"},
            "contato_destino": {"lado": "FINAUD"},
            "corpo_limpo": "Não consigo ver o 4111, aparece erro na tela.",
            "data_iso": "2026-02-23",
            "timestamp_epoch": 100,
        },
        {
            "id": "m2",
            "contato_origem": {"lado": "FINAUD"},
            "contato_destino": {"lado": "CLIENTE"},
            "corpo_limpo": (
                "Andrea: verifique o caminho Informações ao Banco Central > 4111 e a data-base. "
                "Se o erro persistir, envie print."
            ),
            "data_iso": "2026-02-23",
            "timestamp_epoch": 200,
        },
        {
            "id": "m3",
            "contato_origem": {"lado": "CLIENTE"},
            "contato_destino": {"lado": "FINAUD"},
            "corpo_limpo": "Agora deu certo Andrea. Obrigado!!",
            "data_iso": "2026-02-23",
            "timestamp_epoch": 300,
        },
    ]
    ev_sup = {**base_ev, "threadId": tid_s, "cadoc": "SUPORTE", "titulo": "Erro na tela 4111"}
    dados_s = {
        "threads": [{"threadId": tid_s, "mensagens": msgs}],
        "eventos": [ev_sup],
    }
    co, ag, log = triar(
        dados_s,
        date(2026, 2, 23),
        CADOC_TRIAGEM_SUPORTE,
        True,
        alvo_triagem="SUPORTE",
        aguardar_ultima_finaud_finaud=True,
        sec35_agradecimento_sem_msg_cliente_previa=True,
    )
    assert any(tid_s in (r.get("threadId") or "") for r in co)
    assert any("§4e" in line and "SUPORTE" in line for line in log)

    tid_d = "GMTHRID_TEST_DRSAC_NO_4E"
    msgs_d = copy.deepcopy(msgs)
    for i, m in enumerate(msgs_d, start=1):
        m["id"] = f"md{i}"
    ev_dr = {
        "threadId": tid_d,
        "cliente": "EQI",
        "cadoc": "DRSAC",
        "titulo": "DRSAC test",
        "timestamp_epoch": 300,
        "lista_prazos": [
            {"data_base": "23/02/2026", "prazo_limite": "02/03/2026", "cadoc": "DRSAC"},
        ],
    }
    dados_d = {"threads": [{"threadId": tid_d, "mensagens": msgs_d}], "eventos": [ev_dr]}
    # Passo 6 do refactor: DRSAC virou triagem própria (alvo=DRSAC, sem §4e
    # estruturalmente). Antes, usava CADOC_TRIAGEM_SUPORTE+alvo=SUPORTE e
    # contava com o veto ev_cadoc==SUPORTE pra impedir §4e em DRSAC.
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_DRSAC  # type: ignore
    co2, ag2, log2 = triar(
        dados_d,
        date(2026, 2, 23),
        CADOC_TRIAGEM_DRSAC,
        True,
        alvo_triagem="DRSAC",
        aguardar_ultima_finaud_finaud=True,
        sec35_agradecimento_sem_msg_cliente_previa=True,
    )
    assert not any(tid_d in (r.get("threadId") or "") for r in co2)
    assert any("§3 última mensagem CLIENTE" in line for line in log2)


def test_triagem_ddr4111_sec4e_obrigado_funcionou():
    """2026-04-23: §4e alvo DDR4111 + cadoc DDR_2011 — C→F só agradecimento após F→C informativo → Concluído."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_DDR4111, triar

    tid = "GMTHRID_TEST_DDR_4E_RD_MOEDAS"
    dados = {
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {
                        "id": "m1",
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "corpo_limpo": "Andrea, RD_Moedas com erro ao importar.",
                        "data_iso": "2026-02-24",
                        "timestamp_epoch": 100,
                    },
                    {
                        "id": "m2",
                        "contato_origem": {"lado": "FINAUD"},
                        "contato_destino": {"lado": "CLIENTE"},
                        "corpo_limpo": (
                            "Publicamos correção em produção. Pode tentar importar novamente e avisar."
                        ),
                        "data_iso": "2026-02-24",
                        "timestamp_epoch": 200,
                    },
                    {
                        "id": "m3",
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "corpo_limpo": "Andrea, boa tarde. Funcionou! Muito obrigado",
                        "data_iso": "2026-02-24",
                        "timestamp_epoch": 300,
                    },
                ],
            }
        ],
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR_2011",
                "cliente": "Ebury",
                "titulo": "ERRO - RD_Moedas",
                "timestamp_epoch": 300,
                "lista_prazos": [
                    {"data_base": "24/02/2026", "prazo_limite": "03/03/2026", "cadoc": "DDR_2011"},
                ],
            }
        ],
    }
    co, ag, log = triar(
        dados,
        date(2026, 2, 24),
        CADOC_TRIAGEM_DDR4111,
        True,
        alvo_triagem="DDR4111",
    )
    assert any(tid in (r.get("threadId") or "") for r in co)
    assert any("DDR4111 §4e" in line for line in log)


def test_triagem_sec4e_obrigado_com_url_query_nao_bloqueia():
    """2026-04-23: «?» só em URL (utm) não impede §4e — agradecimento puro continua Concluído."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_DDR4111, triar

    tid = "GMTHRID_TEST_DDR_4E_URL_QUERY"
    corpo_cli = (
        "Olá, Flávio! Muito obrigado!!\n\n"
        "Ver também: https://developers.meta.com/foo?utm_source=email&utm_medium=x"
    )
    dados = {
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {
                        "id": "m1",
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "corpo_limpo": "Poderiam cadastrar as opções.",
                        "data_iso": "2026-02-23",
                        "timestamp_epoch": 100,
                    },
                    {
                        "id": "m2",
                        "contato_origem": {"lado": "FINAUD"},
                        "contato_destino": {"lado": "CLIENTE"},
                        "corpo_limpo": "Boa tarde! As opções já foram cadastradas.",
                        "data_iso": "2026-02-24",
                        "timestamp_epoch": 200,
                    },
                    {
                        "id": "m3",
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "corpo_limpo": corpo_cli,
                        "data_iso": "2026-02-24",
                        "timestamp_epoch": 300,
                    },
                ],
            }
        ],
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR_2011",
                "cliente": "Monte Bravo",
                "titulo": "Cadastro de Ações",
                "timestamp_epoch": 300,
                "lista_prazos": [
                    {"data_base": "24/02/2026", "prazo_limite": "03/03/2026", "cadoc": "DDR_2011"},
                ],
            }
        ],
    }
    co, ag, log = triar(
        dados,
        date(2026, 2, 24),
        CADOC_TRIAGEM_DDR4111,
        True,
        alvo_triagem="DDR4111",
    )
    assert any(tid in (r.get("threadId") or "") for r in co)
    assert any("DDR4111 §4e" in line for line in log)


def test_triagem_vista_data_ref_e_rb_ultima_msg_ate_dia():
    """2026-04-02: com data-ref, triagem não usa mensagem posterior à REF (última = dia 23)."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import (
        CADOC_TRIAGEM_RETORNO_BACEN,
        _thread_vista_ate_data_ref,
        triar,
    )

    tid = "GMTHRID_TEST_RB_REFCUT"
    th = {
        "threadId": tid,
        "mensagens": [
            {
                "id": "m1",
                "data_iso": "2026-02-23",
                "timestamp_epoch": 100,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Segue a crítica do BC no anexo conforme CADOC.",
            },
            {
                "id": "m2",
                "data_iso": "2026-02-24",
                "timestamp_epoch": 200,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Certo, a questão está em análise com a área técnica. Retornaremos em breve.",
            },
        ],
    }
    v = _thread_vista_ate_data_ref(th, date(2026, 2, 23))
    assert len(v["mensagens"]) == 1 and v["mensagens"][0].get("id") == "m1"

    dados = {
        "threads": [th],
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "RETORNO_BACEN",
                "cliente": "Cliente QA",
                "titulo": "Re: Erro DLO",
                "timestamp_epoch": 100,
                "lista_prazos": [
                    {
                        "data_base": "23/02/2026",
                        "prazo_limite": "02/03/2026",
                        "cadoc": "RETORNO_BACEN",
                    }
                ],
            }
        ],
    }
    co, ag, log = triar(
        dados,
        date(2026, 2, 23),
        CADOC_TRIAGEM_RETORNO_BACEN,
        True,
        alvo_triagem="RETORNO_BACEN",
        aguardar_ultima_finaud_finaud=True,
        sec35_agradecimento_sem_msg_cliente_previa=False,
    )
    assert not co
    assert len(ag) == 1 and ag[0].get("threadId") == tid
    assert ag[0].get("tipo") == "ACAO_INTERNA"
    assert any("§3 última mensagem CLIENTE" in line for line in log), log


def test_09_excluir_nome_salvo_acima_bytes_infra():
    """2026-04-20: 09 tem infra de excluir_nome_salvo_acima_bytes para exceção por tamanho no filtro de nome."""
    path_09 = os.path.join(RAIZ, "scripts", "09_enriquecer_texto_imagens.py")
    with open(path_09, "r", encoding="utf-8") as f:
        code = f.read()
    assert "excluir_nome_salvo_acima_bytes" in code
    assert "salvo_acima" in code

    path_json = os.path.join(RAIZ, "data", "json", "mapeamento_regras_negocio.json")
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    o_que = data.get("O_QUE_ESTA_SENDO_ANALISADO") or data
    imp = o_que.get("IMAGENS_PARA_CADOC", {})
    assert "excluir_nome_salvo_acima_bytes" in imp
    # Limiar deve ser alto o suficiente para não incluir logos (que são tipicamente < 200KB)
    assert int(imp["excluir_nome_salvo_acima_bytes"]) >= 400_000


def test_triagem_retorno_bacen_ultima_fc_analise_aguarda_finaud():
    """2026-04-20: RETORNO_BACEN — última F→C substantiva em análise → Aguardando Finaud."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_RETORNO_BACEN, triar

    tid = "GMTHRID_TEST_RB_ANALISE"
    th = {
        "threadId": tid,
        "mensagens": [
            {
                "id": "m1",
                "data_iso": "2026-02-24",
                "timestamp_epoch": 100,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Recebemos crítica no DLO de dezembro referente às contas RWAOPAD 875 e 876.",
            },
            {
                "id": "m2",
                "data_iso": "2026-02-24",
                "timestamp_epoch": 200,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Prezada George, boa tarde. Certo, a questão das contas RWAOPAD 875 e 876 está em análise com a nossa área técnica sob a nota N°123.",
            },
        ],
    }
    dados = {
        "threads": [th],
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "RETORNO_BACEN",
                "cliente": "EQI CTVM",
                "titulo": "Re: EQI CTVM Critica DLO",
                "timestamp_epoch": 200,
                "lista_prazos": [],
            }
        ],
    }
    co, ag, log = triar(
        dados,
        date(2026, 2, 24),
        CADOC_TRIAGEM_RETORNO_BACEN,
        True,
        alvo_triagem="RETORNO_BACEN",
        aguardar_ultima_finaud_finaud=True,
        sec35_agradecimento_sem_msg_cliente_previa=False,
    )
    assert not co, f"Não deveria concluir: {co}"
    assert len(ag) == 1 and ag[0].get("threadId") == tid
    assert any("RETORNO_BACEN" in line and "análise" in line for line in log), log


def test_triagem_finaud_pedido_insumos_poderia_informar_qual():
    """2026-04-20: §3-inv — 'poderia, por gentileza, informar qual conta' capturado como pedido de insumos."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _finaud_pedido_insumos_a_cliente

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": "Boa tarde, Alison. Poderia, por gentileza, informar qual conta deve ser utilizada para a realização do ajuste?",
        "assunto": "DLO DEZ/25",
    }
    assert _finaud_pedido_insumos_a_cliente(ult) is True

    ult2 = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": "Poderia nos confirmar qual data base utilizar para o cálculo?",
        "assunto": "Re: DLI jan/2026",
    }
    assert _finaud_pedido_insumos_a_cliente(ult2) is True


def test_triagem_sec5c_corpo_conclusivo():
    """2026-04-02: §5c — Finaud→cliente com «já foi cadastrada» no corpo."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _sec5c_finaud_corpo_conclusivo

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": "Boa tarde! A opção de ação já foi cadastrada.",
        "assunto": "Re: Cliente | DDR | 2026-02-20",
    }
    assert _sec5c_finaud_corpo_conclusivo(ult) is True
    ult2 = {**ult, "corpo_limpo": "Aguardamos o envio dos arquivos."}
    assert _sec5c_finaud_corpo_conclusivo(ult2) is False


def test_triagem_sec5b_e_nucleo_assunto_cancelar_res():
    """2026-04-02: §5b RES Finaud→cliente; núcleo igual entre RES: e Cancelar: (Banvox-type)."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _nucleo_assunto_ddr, _sec5b_res_finaud_cliente

    a = "RES: BANVOX DTVM - EXTRATO COMPROMISSADA/CUSTÓDIA - 20/02/2026"
    b = "Cancelar: BANVOX DTVM - EXTRATO COMPROMISSADA/CUSTÓDIA - 20/02/2026"
    assert _nucleo_assunto_ddr(a) == _nucleo_assunto_ddr(b)
    assert len(_nucleo_assunto_ddr(a)) >= 12

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "assunto": "Re: RES: Monte Bravo | Cadastro de Ações | 2026-02-20",
        "corpo_limpo": "Prezados, confirmamos o encaminhamento conforme solicitado. " * 2,
    }
    assert _sec5b_res_finaud_cliente(ult) is True
    ult_corta = {**ult, "corpo_limpo": "curto"}
    assert _sec5b_res_finaud_cliente(ult_corta) is False


def test_triagem_sec5_segue_em_anexo_e_inv_pedido_obrigada():
    """2026-04-18: §5 reconhece «Segue em anexo»; §3-inv pedido F→C; §3.5 obrigada curta após C→F."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import (
        _finaud_pedido_insumos_a_cliente,
        _finaud_somente_reconhecimento_curto,
        _sec5_remessa_finaud,
    )

    ult_ddr = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": "Segue em anexo o DDR do dia 20/02/2026 para envio ao BC",
        "assunto": "Re: Emissão DDR 20/02/2026",
    }
    assert _sec5_remessa_finaud(ult_ddr) is True

    # 2026-04-23: §5 com quebra de linha entre saudação e «Seguem anexos»; só snippet (DLO/DLI + BC)
    assert _sec5_remessa_finaud(
        {
            "contato_origem": {"lado": "FINAUD"},
            "contato_destino": {"lado": "CLIENTE"},
            "corpo_limpo": "Prezado Alison, boa tarde.\n\nSeguem anexos os arquivos DLO e DLI referentes a 12/2025, "
            "gerados em caráter de substituição para envio ao Banco Central.",
            "assunto": "Re: DLO_2061 e DLI_2062",
        }
    )
    assert _sec5_remessa_finaud(
        {
            "contato_origem": {"lado": "FINAUD"},
            "contato_destino": {"lado": "CLIENTE"},
            "corpo_limpo": "",
            "snippet": "Seguem anexos os arquivos DLO e DLI — substituição para o BC",
            "assunto": "Re: DLO",
        }
    )

    ult_pedido = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": "Por gentileza enviar para cálculo dos DDRs dos dias 18, 19 e 20/02/2026:",
        "assunto": "Informações para DDRs",
    }
    assert _finaud_pedido_insumos_a_cliente(ult_pedido) is True

    ult_ob = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": "Marcos, bom dia ! Obrigada.",
        "assunto": "Re: SSG - ENVIAR POSIÇÃO - 4111",
    }
    th = {
        "mensagens": [
            {
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Segue em anexo o 4111 até a data-base de 20/02/2026.",
            }
        ]
    }
    assert _finaud_somente_reconhecimento_curto(ult_ob, th) is True


def test_triagem_sec4d_cliente_obrigado_apos_remessa_concluido():
    """2026-04-02: §4d — última C→F só agradecimento após F→C §5 → Concluído (não §3)."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import CADOC_TRIAGEM_DDR4111, triar

    tid = "T_SEC4D_MIGR_S5"
    dados = {
        "threads": [
            {
                "threadId": tid,
                "mensagens": [
                    {
                        "id": "m1",
                        "timestamp_epoch": 100,
                        "contato_origem": {"lado": "FINAUD"},
                        "contato_destino": {"lado": "CLIENTE"},
                        "corpo_limpo": (
                            "Welson, segue um base de alterações para maior entendimento "
                            "sobre os requisitos prudenciais alinhados na última reunião."
                        ),
                        "assunto": "Re: Migração S5",
                    },
                    {
                        "id": "m2",
                        "timestamp_epoch": 200,
                        "contato_origem": {"lado": "CLIENTE"},
                        "contato_destino": {"lado": "FINAUD"},
                        "corpo_limpo": "Muito obrigado, Rodrigo. Abs.",
                        "assunto": "Re: Migração S5",
                    },
                ],
            }
        ],
        "eventos": [
            {
                "threadId": tid,
                "cadoc": "DDR_2011",
                "cliente": "Contasimples",
                "titulo": "Re: Migração S5",
                "timestamp_epoch": 200,
                "lista_prazos": [
                    {
                        "cadoc": "DDR_2011",
                        "data_base": "01/02/2026",
                        "prazo_limite": "05/02/2026",
                    }
                ],
            }
        ],
    }
    co, ag, log = triar(dados, None, CADOC_TRIAGEM_DDR4111, True, "DDR4111")
    tids_co = {r.get("threadId") for r in co}
    tids_ag = {r.get("threadId") for r in ag}
    assert tid in tids_co, log
    assert tid not in tids_ag
    assert any("§4d" in line for line in log), log


def test_triagem_sec4d_agradecimento_acima_de_citacao_gmail():
    """§4d: agradecimento curto no topo; citação com «segue/base» não bloqueia."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud
    from resolver_aguardando_auto import _get_ultima_mensagem

    th = {
        "mensagens": [
            {
                "id": "a",
                "timestamp_epoch": 1,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Bom dia, segue um base de alterações para maior entendimento.",
            },
            {
                "id": "b",
                "timestamp_epoch": 2,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": (
                    "Rodrigo, boa tarde. Muito obrigado pelas informações. Abs., WL "
                    "Em seg., 23 de fev. de 2026, R <r@finaud.com.br> escreveu:\n\n"
                    "Bom dia, segue um base de alterações para maior entendimento."
                ),
            },
        ]
    }
    ult, _, _ = _get_ultima_mensagem(th)
    assert ult and ult.get("id") == "b"
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is True


def test_triagem_sec4d_agradecimento_com_pergunta_nao_e_somente_reconhecimento():
    """§4d: agradeço + «mas …» ou «?» no topo → não _cliente_agradecimento_apos_remessa_finaud (ex.: RD_Moedas)."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud
    from resolver_aguardando_auto import _get_ultima_mensagem

    th = {
        "mensagens": [
            {
                "id": "a",
                "timestamp_epoch": 1,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Welson, segue um base de alterações conforme alinhado.",
            },
            {
                "id": "b",
                "timestamp_epoch": 2,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": (
                    "Agradeço a rápida resposta, mas ouve alguma alteração de layout? "
                    "Talvez possa ser alguma particularidade da Ebury."
                ),
            },
        ]
    }
    ult, _, _ = _get_ultima_mensagem(th)
    assert ult and ult.get("id") == "b"
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is False


def test_triagem_sec4d_veto_pergunta_intermedia_sem_resposta_finaud():
    """§4d: C→F com «?» antes do obrigado final, sem F→C entre essa C→F e a última → não §4d."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud

    th = {
        "mensagens": [
            {
                "id": "r0",
                "timestamp_epoch": 1,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Segue um base de alterações conforme alinhado na reunião.",
            },
            {
                "id": "q1",
                "timestamp_epoch": 2,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Podem confirmar o prazo de envio até amanhã?",
            },
            {
                "id": "t2",
                "timestamp_epoch": 3,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Obrigado, abs.",
            },
        ]
    }
    ult = th["mensagens"][2]
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is False


def test_triagem_sec4d_pergunta_intermedia_com_resposta_finaud_permite_obrigado():
    """§4d: C→F com «?»; F→C depois; última C→F só obrigado → mantém §4d."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud

    th = {
        "mensagens": [
            {
                "id": "r0",
                "timestamp_epoch": 1,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Segue um base de alterações conforme alinhado.",
            },
            {
                "id": "q1",
                "timestamp_epoch": 2,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Podem confirmar o prazo de envio até amanhã?",
            },
            {
                "id": "f1",
                "timestamp_epoch": 3,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Confirmado: prazo até sexta conforme calendário BACEN.",
            },
            {
                "id": "t2",
                "timestamp_epoch": 4,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Perfeito, obrigado.",
            },
        ]
    }
    ult = th["mensagens"][3]
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is True


def test_triagem_sec4d_layout_pergunta_resposta_generica_nao_conclui():
    """§4d: pergunta «layout?» sem F→C posterior que cite layout/leiaute/formato → não §4d (Ebury)."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud

    th = {
        "mensagens": [
            {
                "id": "r0",
                "timestamp_epoch": 1,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Segue um base de alterações conforme alinhado.",
            },
            {
                "id": "qL",
                "timestamp_epoch": 2,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": (
                    "Agradeço a resposta, mas houve alteração de layout do arquivo? "
                    "Não alteramos do nosso lado."
                ),
            },
            {
                "id": "fG",
                "timestamp_epoch": 3,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": (
                    "Certo, o ajuste foi publicado em produção. "
                    "Experimente importar novamente e qualquer dúvida retorne."
                ),
            },
            {
                "id": "tF",
                "timestamp_epoch": 4,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Funcionou! Muito obrigado",
            },
        ]
    }
    ult = th["mensagens"][3]
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is False


def test_triagem_sec4d_layout_resposta_explicita_permite_obrigado():
    """§4d: F→C posterior menciona layout/leiaute/formato → último obrigado pode §4d."""
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud

    th = {
        "mensagens": [
            {
                "id": "r0",
                "timestamp_epoch": 1,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "Segue um base de alterações conforme alinhado.",
            },
            {
                "id": "qL",
                "timestamp_epoch": 2,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Houve alteração de layout do arquivo?",
            },
            {
                "id": "fL",
                "timestamp_epoch": 3,
                "contato_origem": {"lado": "FINAUD"},
                "contato_destino": {"lado": "CLIENTE"},
                "corpo_limpo": "O leiaute segue o CRD; nada mudou no formato de colunas.",
            },
            {
                "id": "tF",
                "timestamp_epoch": 4,
                "contato_origem": {"lado": "CLIENTE"},
                "contato_destino": {"lado": "FINAUD"},
                "corpo_limpo": "Entendido, obrigado.",
            },
        ]
    }
    ult = th["mensagens"][3]
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is True


def test_triagem_sec4d_fixture_rd_moedas_ebury_mensagens_reais_integrador():
    """
    Fio real **ERRO - RD_Moedas** (Ebury): mensagens extraídas do ``03_integrador_dados_site.json``
    de ``data/json_backup_antes_zerar`` → ``tests/fixtures/thread_GMTHRID_1857918934374910718_rd_moedas_ebury.json``.
    Última C→F (92091) «Funcionou / obrigado» **não** deve satisfazer §4d (pergunta layout 91936 sem F→C
    que cite layout/leiaute/formato antes do obrigado).
    """
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _cliente_agradecimento_apos_remessa_finaud
    from resolver_aguardando_auto import _get_ultima_mensagem

    path = os.path.join(
        RAIZ,
        "tests",
        "fixtures",
        "thread_GMTHRID_1857918934374910718_rd_moedas_ebury.json",
    )
    assert os.path.isfile(path), f"Fixture em falta (regenerar a partir do 03): {path}"
    with open(path, "r", encoding="utf-8") as f:
        th = json.load(f)
    assert th.get("threadId") == "GMTHRID_1857918934374910718"
    assert len(th.get("mensagens") or []) == 6
    ids = [m.get("id") for m in th["mensagens"]]
    assert ids == ["91929", "91935", "91936", "92077", "92083", "92091"]
    ult, _, lado = _get_ultima_mensagem(th)
    assert lado == "CLIENTE" and ult.get("id") == "92091"
    assert _cliente_agradecimento_apos_remessa_finaud(th, ult) is False


def test_limpar_periodo_remove_concluidas_por_thread_do_periodo():
    """limpar_periodo: tids do 03 no período; remove todos os registros no período."""
    path_lp = os.path.join(RAIZ, "scripts", "limpar_periodo.py")
    with open(path_lp, "r", encoding="utf-8") as f:
        code = f.read()
    assert "resolver_thread_ids_periodo_para_painel" in code
    assert "coletar_thread_ids_de_ficheiro_integrador" in code
    assert "_concluida_resumo_interacoes_data_no_periodo" in code
    assert "limpar_lista_json_por_data_ou_thread_id" in code
    assert "threads_concluidas.json" in code and "threads_aguardando.json" in code
    assert "resumo_interacoes" in code
    assert "preservar_threads_painel" in code
    assert "--preservar-threads-painel" in code
    assert "_formatar_periodo_human" in code
    assert "_configurar_saida_console" in code


def test_operacional_filtro_categoria_multiselect():
    """2026-04-02: dashboard operacional — filtro por categorias (dropdown + checkboxes, mesmo recorte da DATA REF)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="filtroCategoriaBtn"' in html
    assert 'id="filtroCategoriaPopover"' in html
    assert 'id="filtroCategoriaCheckboxes"' in html
    assert "labelsCategoriaThread" in html
    assert "filterThreadsByCategorias" in html
    assert "repopularSelectCategoriasFiltro" in html


def test_modal_crd_protocolo_fallback_conversa_unificada():
    """2026-04: protocolo CRD também a partir de conversa_unificada (Retorno Bacen)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "extrairProtocoloIndicioCrd(thread.conversa_unificada" in html


def test_script_reprocessar_rb_indicio_2061_existe():
    """2026-04: script lista 14 candidatas e chama 09 com --ids."""
    path_sc = os.path.join(RAIZ, "scripts", "reprocessar_rb_indicio_documento_2061.py")
    assert os.path.isfile(path_sc)
    with open(path_sc, "r", encoding="utf-8") as f:
        s = f.read()
    assert "IDS_INDICIO_DOC_2061" in s
    assert "09_enriquecer_texto_imagens.py" in s


def test_painel_contar_tids_dedup_par_confirmado_existe():
    """2026-04-02: API dados dedup monitoramento por par confirmado."""
    path_p = os.path.join(RAIZ, "painel_oraculo.py")
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_p, "r", encoding="utf-8") as f:
        code_core = f.read()
    with open(path_snap, "r", encoding="utf-8") as f:
        code_snap = f.read()
    assert "def _contar_tids_dedup_par_confirmado(" in code_core
    assert "_contar_tids_dedup_par_confirmado(_mon_tids" in code_snap


def test_operacional_html_clusters_multi_thread_badge():
    """2026-04-15: operacional consome clusters_multi_thread e mostra badge Grupo 3+."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "CLUSTERS_MULTI_THREAD" in html
    assert "clusters_multi_thread" in html
    assert "rebuildTidsEmClusterMulti" in html
    assert "Grupo 3+" in html


def test_operacional_funde_card_par_threads_reciproco():
    """2026-04-02: par Gmail sugerido/confirmado funde lista num card e modal com 2 fios."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "function aplicarFusaoCardsPar(" in html
    assert "function mergeThreadApiObjectsForModal(" in html
    assert "_fioThreadId" in html
    assert "function getReciprocalParPeer(" in html
    assert "threadsParaLista = aplicarFusaoCardsParEAgrupAssunto(threadsParaLista, modoFusaoPar)" in html
    assert "function aplicarFusaoCardsAgrupamentoAssunto(" in html
    assert "card-par-merge" in html
    assert "function latestPorCasoOperacionalDedupPar(" in html
    assert "modoFusaoPar" in html
    assert "getLatestParaStatusCard" in html


def test_matriz_ddr_mirae_cluster_e_section_6():
    """2026-04-02 / 2026-04-13: matriz — Mirae 19/02, §6, par Planner 91933+91940, par Fair 91973+91980; §5 remessa→Concluído e reabertura."""
    path_md = os.path.join(RAIZ, "documentações", "MATRIZ_DECISOES_DDR_4111_E_EXCECOES.md")
    assert os.path.isfile(path_md)
    with open(path_md, "r", encoding="utf-8") as f:
        md = f.read()
    assert "## 5. Fluxos DDR/4111 — política de **Concluído** após remessa Finaud e **reabertura**" in md
    assert "**Reabertura (mesmo card, dia seguinte ou após encerrado):**" in md
    assert "passa a **Pendente**" in md
    assert "após triagem** pode voltar a **Aguardando**" in md
    assert "GMTHRID_1857945692134753217" in md
    assert "GMTHRID_1857946244000662182" in md
    assert "GMTHRID_1857658685669939294" in md
    assert "§6 — Mesmo objecto operacional em vários" in md
    assert "1857925167668018751" in md and "1857973059228231907" in md
    assert "GMTHRID_1857919633775523126" in md  # 91933 Planner DLI dez
    assert "GMTHRID_1857921955423620769" in md  # 91940 remessas 2062
    assert "GMTHRID_1857930797949325527" in md  # 91973 Fair 4111
    assert "GMTHRID_1857934562842580009" in md  # 91980 Fair 4111
    assert "GMTHRID_1857930469980225262" in md  # 91972 Fair DDR 18+19
    assert "GMTHRID_1857679411473939866" in md  # 91971/91981 Planner DLO dez
    assert "GMTHRID_1857928522663377340" in md  # 91970 Trinus DDR 18–20
    assert "GMTHRID_1857928327148436929" in md  # 91969/91989 Amaril DDR 20/02
    assert "GMTHRID_1857927412300293351" in md  # 91967 Lev SUPORTE
    assert "GMTHRID_1857927004653440697" in md  # 91966/91985 Planner 4111 dez CV/SCD
    assert "GMTHRID_1857938643836228628" in md  # 91984 Braza DDR 18/02
    assert "GMTHRID_1857925783895198410" in md  # 91954/91960 WISE DDR 18–20/02
    assert "GMTHRID_1857491975811219122" in md  # 91948 Smartsafe SSG 4111 (Registo / Feito)
    assert "GMTHRID_1857673290831320590" in md  # 91946 Acredito DDR 19/02 (Registo / Feito)
    assert "**91943**" in md and "1857923719178397262" in md  # próximo sub-fila Coluna 4111
    assert "Fila **apenas** DDR_2011 + 4111" in md


def test_trava_aguardando_auto_usa_lte_data_ref():
    """2026-04-20: trava Aguardando automático usa <= (não ==) para classificação retroativa da triagem."""
    import inspect
    import painel_oraculo as p
    inspect.getsource(p._threads_nova_interacao)  # ficheiro carregado
    with open(os.path.join(RAIZ, "painel_operacional_snapshot.py"), "r", encoding="utf-8") as f:
        code = f.read()
    assert "d_m <= _dt_trava_classificacao_dia" in code, (
        "Trava Aguardando automático deve usar <= data_ref (não ==)"
    )
    assert "_e_auto" in code, "Deve diferenciar automático de manual na trava"


def test_acrescentar_dia_limpa_refazer_dia_residual():
    """2026-04-20: cmd_acrescentar_dia passa ORACULO_REFazer_DIA='' para não herdar sessão anterior."""
    import inspect
    from scripts.oraculo_cenarios_pipeline import cmd_acrescentar_dia
    src = inspect.getsource(cmd_acrescentar_dia)
    assert 'ORACULO_REFazer_DIA' in src and '""' in src, (
        "cmd_acrescentar_dia deve forçar ORACULO_REFazer_DIA='' no extra_env"
    )


def test_acrescentar_dia_chama_triagens_dia_anterior():
    """2026-04-22: cmd_acrescentar_dia chama _run_triagens_dia_anterior após executar_tudo.

    Garante que a função existe em oraculo_cenarios_pipeline e que cmd_acrescentar_dia
    a invoca — para fechar threads do dia D-1 que só se tornaram candidatos por nova
    mensagem no dia D.
    """
    import inspect
    from scripts.oraculo_cenarios_pipeline import cmd_acrescentar_dia, _run_triagens_dia_anterior

    sig = inspect.signature(_run_triagens_dia_anterior)
    assert len(sig.parameters) >= 1, "_run_triagens_dia_anterior deve aceitar pelo menos 1 param (d_novo)"

    src = inspect.getsource(cmd_acrescentar_dia)
    assert '_run_triagens_dia_anterior' in src, (
        "cmd_acrescentar_dia deve chamar _run_triagens_dia_anterior(d) após _run_executar_tudo"
    )

    src_fn = inspect.getsource(_run_triagens_dia_anterior)
    assert 'timedelta' in src_fn and 'dia_ant' in src_fn, (
        "_run_triagens_dia_anterior deve calcular o dia anterior com timedelta"
    )
    assert '--data-ref' in src_fn or 'TRIAGEM_AUTO_DATA_REF' in src_fn, (
        "_run_triagens_dia_anterior deve passar data_ref do dia anterior às triagens"
    )
    assert 'subprocess' in src_fn, (
        "_run_triagens_dia_anterior deve usar subprocess para isolar as triagens do dia anterior"
    )


def test_triagem_strip_preserva_registros_dia_anterior_qualquer_alvo():
    """2026-04-22: _strip_auto_para_tids preserva QUALQUER registro com cl < dia_ref, qualquer alvo.

    Regra definitiva: triagem com dia_ref=D jamais remove fechos automáticos de dias < D,
    independentemente do alvo de triagem (DDR4111, DLO, RETORNO_BACEN, etc.).
    """
    from datetime import date
    from scripts.triagem_auto_ddr4111 import _strip_auto_para_tids

    dia_ref = date(2026, 2, 24)

    # Registro do DLO com data_marcacao = 2026-02-23 (dia anterior) — deve ser preservado
    reg_dlo_23 = {
        "threadId": "TID_DLO_23",
        "origem_triagem_auto": True,
        "alvo_triagem_auto": "DLO",
        "data_marcacao": "2026-02-23",
    }
    # Registro do DDR4111 com data_marcacao = 2026-02-24 (mesmo dia) — deve ser removido
    reg_ddr_24 = {
        "threadId": "TID_DDR_24",
        "origem_triagem_auto": True,
        "alvo_triagem_auto": "DDR4111",
        "data_marcacao": "2026-02-24",
    }
    # Registro do RETORNO_BACEN com data_marcacao = 2026-02-23 — deve ser preservado
    reg_rb_23 = {
        "threadId": "TID_RB_23",
        "origem_triagem_auto": True,
        "alvo_triagem_auto": "RETORNO_BACEN",
        "data_marcacao": "2026-02-23",
    }

    tids_strip = {"TID_DLO_23", "TID_DDR_24", "TID_RB_23"}
    out, n = _strip_auto_para_tids(
        [reg_dlo_23, reg_ddr_24, reg_rb_23],
        alvo="DDR4111",
        tids=tids_strip,
        dia_ref=dia_ref,
        lista_aguardando=True,
    )
    out_tids = {r["threadId"] for r in out}
    assert "TID_DLO_23" in out_tids, (
        "_strip_auto_para_tids deve preservar registro DLO com data < dia_ref"
    )
    assert "TID_RB_23" in out_tids, (
        "_strip_auto_para_tids deve preservar registro RETORNO_BACEN com data < dia_ref"
    )
    assert "TID_DDR_24" not in out_tids, (
        "_strip_auto_para_tids deve remover registro DDR4111 com data == dia_ref"
    )
    assert n == 1, f"Esperado 1 removido, obteve {n}"


def test_triagem_fecho_anterior_exclui_qualquer_alvo():
    """2026-04-22: _tids_sem_reprocessar_triagem_fecho_anterior exclui threads com fecho de qualquer alvo < dia_ref.

    Garante que threads classificados pelo DLO, RETORNO_BACEN, etc. no dia 23 não
    entram na triagem DDR4111 do dia 24.
    """
    from datetime import date
    from scripts.triagem_auto_ddr4111 import _tids_sem_reprocessar_triagem_fecho_anterior

    dia_ref = date(2026, 2, 24)

    ag = [
        # DLO no dia 23 — deve ser excluído mesmo quando alvo="DDR4111"
        {"threadId": "TID_DLO_23", "origem_triagem_auto": True, "alvo_triagem_auto": "DLO", "data_marcacao": "2026-02-23"},
        # RETORNO_BACEN no dia 23 — idem
        {"threadId": "TID_RB_23", "origem_triagem_auto": True, "alvo_triagem_auto": "RETORNO_BACEN", "data_marcacao": "2026-02-23"},
        # DDR4111 no dia 24 — não deve ser excluído (data == dia_ref)
        {"threadId": "TID_DDR_24", "origem_triagem_auto": True, "alvo_triagem_auto": "DDR4111", "data_marcacao": "2026-02-24"},
        # Registro do dia 23 (anterior ao dia_ref) — deve ser excluído
        {"threadId": "TID_MANUAL_23", "origem_triagem_auto": False, "data_marcacao": "2026-02-23"},
    ]
    co: list = []

    excluidos = _tids_sem_reprocessar_triagem_fecho_anterior(ag, co, dia_ref, "DDR4111")

    assert "TID_DLO_23" in excluidos, "Thread DLO do dia 23 deve ser excluído do reprocesso DDR4111 do dia 24"
    assert "TID_RB_23" in excluidos, "Thread RETORNO_BACEN do dia 23 deve ser excluído do reprocesso DDR4111 do dia 24"
    assert "TID_DDR_24" not in excluidos, "Thread DDR4111 do dia 24 não deve ser excluído (data == dia_ref)"
    assert "TID_MANUAL_23" in excluidos, "Thread do dia 23 deve ser excluído (anterior ao dia_ref)"


def test_painel_thread_multidia_pendente_suprimido_no_dia_anterior():
    """2026-04-22: thread PENDENTE com mail em D e D+1 — vista **ao vivo** (REF ≥ hoje civil) suprime em D.

    Regra: thread PENDENTE (sem registro em ag/co) com evento em dia D e também em dias
    posteriores é suprimido da lista do dia D — pertence ao dia com atividade mais recente.
    Para DATA REF **passada** (menor que hoje), essa supressão não se aplica (vista histórica).
    Threads classificados (ag ou co) continuam visíveis normalmente em D.
    """
    path_snap = os.path.join(RAIZ, "painel_operacional_snapshot.py")
    with open(path_snap, "r", encoding="utf-8") as f:
        codigo = f.read()

    assert "suprimir_multidia_sem_ag_co" in codigo, (
        "painel_operacional_snapshot: supressão multirdia só na vista REF >= hoje civil"
    )
    assert "_tem_post = any(mm > dt_limite for mm in datas_thread)" in codigo, (
        "painel_operacional_snapshot: detetar atividade posterior à REF"
    )
    assert "_ja = (tt in concluidos_set) or (tt in aguardando_set)" in codigo, (
        "painel_operacional_snapshot: só suprime pendente livre se aguard/concl não fixou o dia"
    )


def test_nova_interacao_nao_contamina_dia_anterior():
    """2026-04-20: badge Nova resposta não aparece no dia D-1 ao subir o dia D.

    _threads_nova_interacao(data_ref=D-1) só deve retornar IDs cujo AGUARDO_RESOLVIDO
    foi gravado em D-1, não os de D (que são do pipeline do dia seguinte).
    """
    import tempfile, json as _json
    from datetime import date as _date
    from painel_oraculo import _threads_nova_interacao

    dia_23 = _date(2026, 2, 23)
    dia_24 = _date(2026, 2, 24)

    diario = [
        {"tipo": "AGUARDO_RESOLVIDO", "thread": "TID_23", "data": "2026-02-23", "assunto": "a"},
        {"tipo": "AGUARDO_RESOLVIDO", "thread": "TID_24", "data": "2026-02-24", "assunto": "b"},
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        _json.dump(diario, f)
        tmp = f.name

    import painel_oraculo as _p
    orig = _p.ARQUIVO_DIARIO
    _p.ARQUIVO_DIARIO = tmp
    try:
        # Vista do 23: só TID_23 deve ter badge
        ids_23 = _threads_nova_interacao(data_ref=dia_23)
        assert "TID_23" in ids_23, "TID_23 deve aparecer na vista do dia 23"
        assert "TID_24" not in ids_23, "TID_24 (do dia 24) não deve contaminar a vista do dia 23"

        # Vista do 24: só TID_24
        ids_24 = _threads_nova_interacao(data_ref=dia_24)
        assert "TID_24" in ids_24
        assert "TID_23" not in ids_24
    finally:
        _p.ARQUIVO_DIARIO = orig
        import os as _os
        _os.unlink(tmp)


def test_painel_clusters_multi_thread_tres_fios_mesmo_bucket():
    """2026-04-15: buckets 3+ threads — mesma empresa API + mesmo fingerprint lista_prazos."""
    from painel_oraculo import _computar_clusters_multi_thread_operacional

    fp = [{"cadoc": "DDR_2011", "data_base": "19/02/2026", "prazo_limite": "24/02/2026"}]
    base = {
        "empresa": "Mirae Invest",
        "lista_prazos": fp,
        "timestamp": "23/02/2026 12:00",
        "titulo": "A",
    }
    ev = [
        dict(base, threadId="T_CLUSTER_1", id="1", timestamp_epoch=3),
        dict(base, threadId="T_CLUSTER_2", id="2", timestamp_epoch=2),
        dict(base, threadId="T_CLUSTER_3", id="3", timestamp_epoch=1),
    ]
    c = _computar_clusters_multi_thread_operacional(ev)
    assert len(c) == 1
    assert set(c[0]["thread_ids"]) == {"T_CLUSTER_1", "T_CLUSTER_2", "T_CLUSTER_3"}
    assert c[0]["n_threads"] == 3


def test_doc_pares_e_clusters_threadid_distintos():
    """2026-04-14: doc pares/cluster + script lista pares automáticos."""
    path_doc = os.path.join(RAIZ, "documentações", "PARES_E_CLUSTERS_THREADID_DISTINTOS.md")
    path_py = os.path.join(RAIZ, "scripts", "gerar_documentacao_pares_threadid.py")
    assert os.path.isfile(path_doc)
    assert os.path.isfile(path_py)
    with open(path_doc, "r", encoding="utf-8") as f:
        doc = f.read()
    assert "GMTHRID_1857930797949325527" in doc
    assert "GMTHRID_1857934562842580009" in doc
    assert "pares_threads_confirmados.json" in doc
    assert "pipeline/pares_threads_confirmados.json" in doc
    assert "_computar_pares_sugeridos_operacional" in doc


def test_paths_pares_em_pipeline_cadastro_rotulos_em_config():
    """2026-04-27: pares em pipeline (zerável); cadastro/rotulos em config (mantidos na carga)."""
    import sys
    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    import paths

    assert "pipeline" in paths.F_PARES_THREADS.replace(os.sep, "/")
    assert paths.PIPELINE_DIR in paths.F_PARES_THREADS

    assert paths.CONFIG_DIR in paths.F_CADASTRO_CLIENTES
    assert paths.CONFIG_DIR in paths.F_ROTULOS
    assert "cadastro_clientes_cadoc.json" in paths.F_CADASTRO_CLIENTES


def test_ddr4111_doc_validacao_23_indice_e_script():
    """2026-04-14: documentação listagem DDR/4111 dia 23 + script regeneração."""
    path_doc = os.path.join(RAIZ, "documentações", "DDR_4111_OPERACIONAL_2026-02-23_VALIDACAO_TRIAGEM.md")
    path_py = os.path.join(RAIZ, "scripts", "gerar_documentacao_ddr4111_validacao_23.py")
    assert os.path.isfile(path_doc)
    assert os.path.isfile(path_py)
    with open(path_doc, "r", encoding="utf-8") as f:
        doc = f.read()
    assert "## Índice (resumo)" in doc
    assert "**Total de fios:** 31" in doc
    assert "GMTHRID_1857946244000662182" in doc
    with open(path_py, "r", encoding="utf-8") as f:
        assert "PROPOSTAS_EXTRAS" in f.read()


def test_modal_citacoes_aninhadas_e_api_crd():
    """2026-03: citações tipo PDF + /api/crd_indicio_qualidade + script export Excel."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "renderModalCiteStackHtml" in html
    assert "hydrateModalCrdBoxes" in html
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "api_crd_indicio_qualidade" in code
    path_export = os.path.join(RAIZ, "scripts", "sincronizar_json_indicios_qualidade_crd.py")
    assert os.path.isfile(path_export)
    with open(path_export, "r", encoding="utf-8") as f:
        ex = f.read()
        assert "crd_indicio_qualidade.json" in ex
        assert "indício-qualidade.xlsx" in ex or "indício-qualidade" in ex
    path_exec = os.path.join(RAIZ, "executar_tudo.py")
    with open(path_exec, "r", encoding="utf-8") as f:
        assert "sincronizar_json_indicios_qualidade_crd" in f.read()


def test_triagem_congela_tids_fecho_auto_anterior_a_dia_ref():
    """2026-04-20: não reprocessar threadId com Aguardando/Concluído automático de data < dia_ref."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _tids_sem_reprocessar_triagem_fecho_anterior

    dia = date(2026, 2, 24)
    ag = [
        {
            "threadId": "FROZ",
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_marcacao": "2026-02-23",
        }
    ]
    co: list = []
    t = _tids_sem_reprocessar_triagem_fecho_anterior(ag, co, dia, "RETORNO_BACEN")
    assert "FROZ" in t


def test_triagem_aguardando_antigo_reentra_se_fio_toca_dia_ref():
    """Aguardando D-1 não fica congelado se houver mensagem no dia D (re-triagem com vista até D)."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _tids_sem_reprocessar_triagem_fecho_anterior

    dia_ref = date(2026, 2, 24)
    tid = "TID_RB_COM_MSG_24"
    ag = [
        {
            "threadId": tid,
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_marcacao": "2026-02-23",
        }
    ]
    co: list = []
    mapa_t = {
        tid: {
            "threadId": tid,
            "mensagens": [{"data_iso": "2026-02-24T13:00:00"}],
        }
    }
    por_tid = {tid: {"cadoc": "RETORNO_BACEN", "data_iso": "2026-02-23"}}

    ex = _tids_sem_reprocessar_triagem_fecho_anterior(
        ag, co, dia_ref, "RETORNO_BACEN", mapa_t=mapa_t, por_tid=por_tid
    )
    assert tid not in ex


def test_triagem_concluido_posterior_a_dia_ref_fica_fora_da_triagem():
    """Concluído com data > dia_ref: não recandidatar (vista truncada a ≤ dia_ref)."""
    import sys
    from datetime import date

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _tids_sem_reprocessar_triagem_fecho_anterior

    dia_ref = date(2026, 2, 23)
    tid = "TID_FECHOU_24"
    ag: list = []
    co = [
        {
            "threadId": tid,
            "origem_triagem_auto": True,
            "alvo_triagem_auto": "RETORNO_BACEN",
            "data_conclusao": "2026-02-24 18:00:00",
        }
    ]
    ex = _tids_sem_reprocessar_triagem_fecho_anterior(ag, co, dia_ref, "RETORNO_BACEN")
    assert tid in ex


def test_script_auditar_fecho_triagem_dia_ref_existe():
    """2026-04-20: auditoria subset/diff de triagem por calendário D (antes vs depois de subir N+1)."""
    path = os.path.join(RAIZ, "scripts", "auditar_fecho_triagem_dia_ref.py")
    assert os.path.isfile(path)
    with open(path, "r", encoding="utf-8") as f:
        c = f.read()
    assert "def cmd_diff" in c and "_subset_por_dia" in c and "_fingerprint_por_tid" in c


def test_threads_status_arquivo_unico_em_pipeline():
    """2026-06-10: arquivos manuais migrados para auto — arquivo único por status."""
    import sys
    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)

    import paths

    # Constantes esperadas
    assert hasattr(paths, "F_AGUARDANDO_AUTO")
    assert hasattr(paths, "F_CONCLUIDAS_AUTO")
    # Legacy F_AGUARDANDO / F_CONCLUIDAS removidas (forçar migração)
    assert not hasattr(paths, "F_AGUARDANDO")
    assert not hasattr(paths, "F_CONCLUIDAS")

    # Arquivos ficam em pipeline/
    for p in (paths.F_AGUARDANDO_AUTO, paths.F_CONCLUIDAS_AUTO):
        assert paths.PIPELINE_DIR in p, f"{p} devia estar em pipeline/"

    # Helpers disponíveis
    for nome in ("load_aguardando", "save_aguardando", "load_concluidas", "save_concluidas"):
        assert hasattr(paths, nome), f"paths.{nome} em falta"

    # save_aguardando grava tudo no arquivo único
    import tempfile
    tmp = tempfile.mkdtemp(prefix="qa_unico_")
    try:
        bak_ag = paths.F_AGUARDANDO_AUTO
        paths.F_AGUARDANDO_AUTO = os.path.join(tmp, "ag_auto.json")
        try:
            paths.save_aguardando([
                {"threadId": "A", "origem_triagem_auto": True},
                {"threadId": "B", "origem_triagem_auto": False},
                {"threadId": "C"},
            ])
            ag = json.load(open(paths.F_AGUARDANDO_AUTO, encoding="utf-8"))
            assert len(ag) == 3, "save_aguardando deve gravar todos os registros"
            todos = paths.load_aguardando()
            assert len(todos) == 3
        finally:
            paths.F_AGUARDANDO_AUTO = bak_ag
    finally:
        import shutil as _sh
        _sh.rmtree(tmp, ignore_errors=True)


def test_triagem_tids_strip_apenas_novos_classificados():
    """
    2026-04-23: tids_strip em _run_triagem_cadocs deve começar com set() vazio e
    só incluir threads que receberam nova classificação (novos_co / novos_ag).
    Candidatos sem nova classificação ficam intactos → status nunca regride a PENDENTE.
    """
    path = os.path.join(RAIZ, "scripts", "triagem_auto_ddr4111.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    # A linha de inicialização de tids_strip não deve mais conter candidatos_pre
    lines = src.splitlines()
    linhas_tids_strip = [l.strip() for l in lines if "tids_strip" in l and "Set[str]" in l]
    assert linhas_tids_strip, "Deve existir declaração de tids_strip em _run_triagem_cadocs"
    for l in linhas_tids_strip:
        assert "candidatos_pre" not in l, \
            f"tids_strip não deve incluir candidatos_pre (regressão PENDENTE): {l}"
    # Deve inicializar com set() vazio
    assert any("set()" in l for l in linhas_tids_strip), \
        "tids_strip deve ser inicializado como set() vazio"


def test_executar_tudo_pula_etapa10_por_omissao():
    """
    2026-04-23: executar_tudo.py deve definir ORACULO_PULAR_RESOLVER_AGUARDANDO_AUTO=1
    com setdefault globalmente (não só em modo single-day), para que a etapa 10 nunca
    corra por omissão e o status não mude com a chegada de e-mails novos.
    """
    path = os.path.join(RAIZ, "executar_tudo.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert 'setdefault("ORACULO_PULAR_RESOLVER_AGUARDANDO_AUTO", "1")' in src, \
        "executar_tudo.py deve ter setdefault(ORACULO_PULAR_RESOLVER_AGUARDANDO_AUTO, 1) global"


def test_triagem_sec5_nao_aceita_segue_dentro_de_consegue():
    """
    2026-04-24: «Consegue encaminhar a remessa…» não dispara §5 (falso segue em Conseg**ue**).
    Deve cair em §3-inv (pedido ao cliente), não em Concluído.
    """
    import sys

    sc = os.path.join(RAIZ, "scripts")
    if sc not in sys.path:
        sys.path.insert(0, sc)
    from triagem_auto_ddr4111 import _finaud_pedido_insumos_a_cliente, _sec5_remessa_finaud

    ult = {
        "contato_origem": {"lado": "FINAUD"},
        "contato_destino": {"lado": "CLIENTE"},
        "corpo_limpo": (
            "Boa tarde, Consegue encaminhar a remessa DLO (2061) dez/2025 "
            "para análise do arquivo XML? Antecipadamente grata."
        ),
        "assunto": "RE: Informe 2061",
    }
    assert not _sec5_remessa_finaud(ult)
    assert _finaud_pedido_insumos_a_cliente(ult)


def test_ressurreicao_nao_remove_de_concluidas():
    """
    2026-04-23: _aplicar_verificacao_ressurreicao não deve mais remover threads de
    threads_concluidas*.json quando chegam mensagens novas — apenas marca ressuscitada=True
    como badge visual sem alterar o status gravado.
    """
    path = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert "_aplicar_verificacao_ressurreicao" in src
    # Confirma que a chamada destrutiva ao _salvar_threads_concluidas foi removida do bloco
    # de ressurreição (o bloco de ids_para_remover_dos_concluidos deve ter sumido)
    assert "ids_para_remover_dos_concluidos" not in src, \
        "09_integrar_dados_painel.py não deve mais ter ids_para_remover_dos_concluidos (ressurreição não-destrutiva)"
    assert 'ressuscitada' in src, \
        "Badge ressuscitada=True deve permanecer para indicação visual"


def test_gestao_direcao_rota_template_e_agregacao():
    """2026-04-28: tela Gestão & Direção + API agregada dos JSON (gestor/diretor/admin/gerencial)."""
    path_p = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_p, encoding="utf-8") as f:
        code = f.read()
    assert '@app.route("/gestao/direcao")' in code
    assert '@app.route("/api/gestao_direcao")' in code
    assert "coletar_stats_gestao_direcao" in code
    assert "painel_cards" in code
    assert "request.args.get" in code and "periodo" in code
    assert "PAPEIS_VISAO_GESTAO_DIRECAO" in code
    path_html = os.path.join(RAIZ, "templates", "gestao_direcao.html")
    assert os.path.isfile(path_html)
    with open(path_html, encoding="utf-8") as f:
        html = f.read()
    assert "/api/gestao_direcao" in html
    assert "gd-collab-stack" in html
    assert "total_cartoes_periodo" in code
    path_layout = os.path.join(RAIZ, "templates", "layout.html")
    with open(path_layout, encoding="utf-8") as f:
        lay = f.read()
    assert "/gestao/direcao" in lay
    assert "'gestor'" in lay or '"gestor"' in lay


def test_admin_pipeline_rotas_integracao_jobs():
    """2026-04-27: admin — página Pipeline e APIs ligadas a pipeline_jobs."""
    path_p = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_p, encoding="utf-8") as f:
        code = f.read()
    assert "import pipeline_jobs" in code
    assert "@app.route('/admin/pipeline')" in code
    assert "/api/admin/pipeline/run" in code
    assert "/api/admin/pipeline/job/" in code
    assert "def api_admin_pipeline_run" in code
    assert "pipeline_jobs.obter_estado" in code
    assert "iniciar_limpar_periodo" in code
    path_html = os.path.join(RAIZ, "templates", "admin_pipeline.html")
    assert os.path.isfile(path_html)
    with open(path_html, encoding="utf-8") as f:
        html = f.read()
    assert '/api/admin/pipeline/run' in html
    assert "tipo: 'deletar'" in html
    assert "Processar a fila de datas" in html
    assert "Incluir mais um dia" in html
    assert "Zerar todos os dados de processamento na máquina" in html
    assert "limpar_periodo.py" in html
    assert "btn-limpar-periodo" in html
    assert "limpar_periodo'" in html
    assert "Andamento do trabalho" in html
    assert "Mensagens do sistema" in html
    assert "st-log-wrap" in html
    path_layout = os.path.join(RAIZ, "templates", "layout.html")
    with open(path_layout, encoding="utf-8") as f:
        lay = f.read()
    assert '/admin/pipeline' in lay
    path_jobs = os.path.join(RAIZ, "pipeline_jobs.py")
    assert os.path.isfile(path_jobs)
    with open(path_jobs, encoding="utf-8") as f:
        assert "def obter_estado" in f.read()


def test_admin_pipeline_modal_confirmacao_e_grelha_passos():
    """2026-04-27: modal Excluir/Cancelar, overlay de andamento e grade de passos (sem window.confirm)."""
    path_html = os.path.join(RAIZ, "templates", "admin_pipeline.html")
    with open(path_html, encoding="utf-8") as f:
        html = f.read()
    assert "pipeline-modal-deletar" in html
    assert "pipeline-progress-overlay" in html
    assert "abrirModalAndamento" in html
    assert "montarTabelaLimparPeriodo" in html
    assert "pipeline-modal-cancelar" in html
    assert "confirmarEliminacaoPorModal" in html
    assert "actualizarGrelhaPassos" in html
    assert "st-passos-tbody" in html
    assert "btn-st-fechar" in html
    assert "Script / etapa" in html
    assert "Arquivos (JSON principal)" in html
    assert "montarTabelaPassosDeletar" in html
    path_jobs = os.path.join(RAIZ, "pipeline_jobs.py")
    with open(path_jobs, encoding="utf-8") as f:
        pj = f.read()
    assert "DELETE_GRUPO_OK" in pj
    assert "obter_plano_grupos_delecao" in pj
    assert html.count("window.confirm") == 0


def test_deletar_carga_mensagem_ui_admin_sem_executar_tudo_cli():
    """2026-04-27: via Admin Pipeline, rodapé do deletar aponta aos botões da página, não ao CLI."""
    path_py = os.path.join(RAIZ, "deletar_carga.py")
    path_jobs = os.path.join(RAIZ, "pipeline_jobs.py")
    with open(path_py, encoding="utf-8") as f:
        dc = f.read()
    with open(path_jobs, encoding="utf-8") as f:
        pj = f.read()
    assert "ORACULO_DELETAR_VIA_ADMIN_UI" in dc
    assert '"Começar atualização neste período"' in dc
    assert '"Processar a fila de datas"' in dc
    assert "ORACULO_DELETAR_VIA_ADMIN_UI" in pj
    assert "_append_deletar_resumo_plano" in pj


def test_oraculo_cenarios_print_run_executar_sem_seta_unicode():
    """2026-04-29: ``_run_executar_tudo`` não deve usar seta Unicode no print — stdout subprocess Windows (cp1252)."""
    path_sc = os.path.join(RAIZ, "scripts", "oraculo_cenarios_pipeline.py")
    with open(path_sc, encoding="utf-8") as f:
        txt = f.read()
    assert "\u2192" not in txt


def test_gestao_direcao_contatos_responsavel_tipos_flexiveis():
    """2026-04-27: semanal não pode rebentar se nome/responsável vierem como número no JSON."""
    from painel_oraculo import _nome_contato_dict_seguro, _responsavel_pela_acao_from_mensagens, _str_strip_seguro

    assert _str_strip_seguro(None) == ""
    assert _str_strip_seguro(42) == "42"
    assert _nome_contato_dict_seguro({"nome": 12345}) == "12345"
    assert _nome_contato_dict_seguro({"email": 99}) == ""

    msgs = [
        {
            "contato_origem": {"lado": "FINAUD"},
            "contato_destino": {"lado": "CLIENTE"},
            "responsavel": 7711,
            "responsavel_nome": "",
        }
    ]
    out = _responsavel_pela_acao_from_mensagens(msgs, "")
    assert out == ""


def test_equipe_gestao_direcao_sem_usuarios_json_so_operacional():
    """2026-04-29: Equipe Gestão — lados última mensagem + e-mail institucional @finaud nas mensagens."""
    from painel_oraculo import _colab_secao_equipe_gestacao_direcao

    msg_cf = [{
        "contato_origem": {"lado": "CLIENTE", "nome": "Cli"},
        "contato_destino": {
            "lado": "FINAUD",
            "nome": "Andrea",
            "email": "andrea.x@finaud.com.br",
        },
    }]
    assert _colab_secao_equipe_gestacao_direcao("Andrea", msg_cf) is True

    msg_cf_sem_mail = [{
        "contato_origem": {"lado": "CLIENTE", "nome": "Cli"},
        "contato_destino": {"lado": "FINAUD", "nome": "Pedro"},
    }]
    assert _colab_secao_equipe_gestacao_direcao("Pedro", msg_cf_sem_mail) is False

    msg_cf_gmail = [{
        "contato_origem": {"lado": "CLIENTE", "nome": "Cli"},
        "contato_destino": {"lado": "FINAUD", "nome": "Maria", "email": "maria@gmail.com"},
    }]
    assert _colab_secao_equipe_gestacao_direcao("Maria", msg_cf_gmail) is False

    msg_fc = [{
        "contato_origem": {"lado": "FINAUD", "nome": "Andrea", "email": "a@finaud.com.br"},
        "contato_destino": {"lado": "CLIENTE", "nome": "Cli"},
    }]
    assert _colab_secao_equipe_gestacao_direcao("Cli", msg_fc) is False


TESTS = [
    test_helpers_sec4d_regex_layout_leiaute_definida_e_funcional,
    test_indices_snapshot_preservam_registo_auto_sobre_manual,
    test_operacional_filtro_categoria_multiselect,
    test_09_normaliza_ocr_1876_para_876_rwaopad,
    test_ocr_sanitizar_prefixo_crd_operacional,
    test_09_enriquecer_flag_ids_e_sync_eventos,
    test_09_dimensoes_crd_estreita_retorno_bacen,
    test_oraculo_cenarios_pipeline_script_existe,
    test_triagem_strip_auto_para_tids_preserva_outros_threadids,
    test_triagem_strip_preserva_fecho_civil_anterior_ao_dia_ref,
    test_triagem_registro_concluido_usa_dia_ref_quando_definido,
    test_triagem_congela_tids_fecho_auto_anterior_a_dia_ref,
    test_script_auditar_fecho_triagem_dia_ref_existe,
    test_executar_tudo_cronometra_etapas,
    test_triagem_auto_ddr4111_script_e_executar_tudo_opcional,
    test_triagem_auto_dli_script_e_executar_tudo_opcional,
    test_triagem_auto_dlo_script_e_executar_tudo_opcional,
    test_triagem_auto_s5_script_e_executar_tudo_opcional,
    test_triagem_auto_suporte_script_e_executar_tudo_opcional,
    test_triagem_suporte_ultima_fc_informativo_resposta_cliente,
    test_triagem_suporte_sec4e_obrigado_sem_remessa_f_c_concluido,
    test_triagem_ddr4111_sec4e_obrigado_funcionou,
    test_triagem_sec4e_obrigado_com_url_query_nao_bloqueia,
    test_triagem_vista_data_ref_e_rb_ultima_msg_ate_dia,
    test_triagem_sec5_nao_aceita_segue_dentro_de_consegue,
    test_triagem_auto_retorno_bacen_script_e_executar_tudo_opcional,
    test_classificador_primeiro_to_finaud_ff_e_script_reenvelope,
    test_classificador_preserva_cadoc_fora_do_periodo_env_var,
    test_integrador_08_preserva_texto_imagens_via_campo_02,
    test_registro_explica_scripts_vs_json,
    test_registro_pipeline_inclui_triagem_rb_apply,
    test_matriz_retorno_bacen_rascunho_23_documentado,
    test_triagem_sec5c_corpo_conclusivo,
    test_triagem_sec5b_e_nucleo_assunto_cancelar_res,
    test_triagem_sec5_segue_em_anexo_e_inv_pedido_obrigada,
    test_triagem_sec4d_cliente_obrigado_apos_remessa_concluido,
    test_triagem_sec4d_agradecimento_acima_de_citacao_gmail,
    test_triagem_sec4d_agradecimento_com_pergunta_nao_e_somente_reconhecimento,
    test_triagem_sec4d_veto_pergunta_intermedia_sem_resposta_finaud,
    test_triagem_sec4d_pergunta_intermedia_com_resposta_finaud_permite_obrigado,
    test_triagem_sec4d_layout_pergunta_resposta_generica_nao_conclui,
    test_triagem_sec4d_layout_resposta_explicita_permite_obrigado,
    test_triagem_sec4d_fixture_rd_moedas_ebury_mensagens_reais_integrador,
    test_limpar_periodo_remove_concluidas_por_thread_do_periodo,
    test_api_exclui_filtrado_por_data_com_data_ref_exceto_busca,
    test_api_desativa_persist_saida_aguardando_env,
    test_api_dados_concluido_alinha_status_processo_guard_aguardando,
    test_api_dados_trava_mesma_data_ref_classificacao,
    test_api_dados_usa_snapshot_unico_fonte_operacional,
    test_executar_tudo_preserva_dias_e_limpar_opcional,
    test_executar_tudo_refazer_dia_apaga_e_sobe,
    test_script_snapshot_operacional_existe,
    test_script_diagnostico_thread_operacional_existe,
    test_modal_crd_protocolo_fallback_conversa_unificada,
    test_script_reprocessar_rb_indicio_2061_existe,
    test_matriz_ddr_mirae_cluster_e_section_6,
    test_ddr4111_doc_validacao_23_indice_e_script,
    test_matriz_dli_wise_escopo_unico_dli,
    test_matriz_dlo_rascunho_23_documentado,
    test_doc_pares_e_clusters_threadid_distintos,
    test_painel_clusters_multi_thread_tres_fios_mesmo_bucket,
    test_painel_contar_tids_dedup_par_confirmado_existe,
    test_operacional_html_clusters_multi_thread_badge,
    test_operacional_funde_card_par_threads_reciproco,
    test_operacional_busca_lista_unificada_status,
    test_operacional_toast_data_ref_casos_vs_eventos,
    test_operacional_ver_concluidos_e_kpi_role_button,
    test_operacional_busca_respeita_data_ref,
    test_marcar_aguardando_envia_data_ref_operacional,
    test_modal_operacional_sem_botoes_header_aguardar_aprender,
    test_export_operacional_csv_email_operacional,
    test_responsavel_pela_acao_registro_template_e_painel,
    test_responsavel_pela_acao_regra_ultimo_fio,
    test_api_nao_resolvidos_busca_respeita_data_param,
    test_operacional_busca_id_ajusta_aba,
    test_script_patch_ddr_rd_moedas_um_prazo_existe,
    test_script_patch_retorno_bacen_91937_existe,
    test_script_aplicar_indice_basileia_suporte_existe,
    test_classificador_indice_basileia_assunto_suporte,
    test_classificador_prazo_ddr_dia_hifen_e_drsac_nao_ddr_por_tvm,
    test_classificador_ignorar_newsletter_meta_utm_mapeamento,
    test_classificador_assunto_s5_prioridade_identificar_cadoc,
    test_classificador_encaminhamento_interno_finaud_contato_e_pendencia,
    test_api_fallback_cliente_fwd_interno_json_antigo,
    test_classificador_erro_na_tela_nao_e_retorno_bacen,
    test_classificador_mes_sozinho_ignora_de_fev_em_data_extenso,
    test_classificador_mandatorio_critica_corpo_mais_documento_retorno_bacen,
    test_retorno_bacen_prazo_so_d3_uteis_sem_extrair_texto,
    test_trava_aguardando_auto_usa_lte_data_ref,
    test_acrescentar_dia_limpa_refazer_dia_residual,
    test_acrescentar_dia_chama_triagens_dia_anterior,
    test_triagem_strip_preserva_registros_dia_anterior_qualquer_alvo,
    test_triagem_fecho_anterior_exclui_qualquer_alvo,
    test_painel_thread_multidia_pendente_suprimido_no_dia_anterior,
    test_nova_interacao_nao_contamina_dia_anterior,
    test_integrador_08_corpo_evento_e_threads_concluidas_sem_nova_msg,
    test_modal_renderModalLocal_usa_corpo_limpo,
    test_modal_citacoes_aninhadas_e_api_crd,
    test_modal_fallback_achata_eventos_para_exibir_texto_imagens,
    test_ocr_modal_ficha_sem_imagem_e_tabelas,
    test_ocr_crd_tabelas_seis_colunas_historico,
    test_imagens_para_cadoc_tamanho_minimo_8kb,
    test_ocr_ficha_omitir_ruido_logo_banvox,
    test_modal_corta_assinatura_cid_inline,
    test_corpo_limpo_modal_aplica_strip_disclaimer_global,
    test_modal_corta_encerramento_cordial_at_te_e_disclaimer_esta_mensagem,
    test_modal_historico_oculta_cauda_citacao_redundante,
    test_modal_corpo_principal_solo_topo_quando_encaminhados,
    test_modal_corpo_xml_crd_extracao_plana_sem_innerhtml,
    test_modal_corpo_texto_para_modal_fallback_limpo_vazio,
    test_coletor_01_inline_grande_exige_dimensoes_conteudo,
    test_coletor_01_content_id_sem_disposition_inline,
    test_coletor_01_critica_rb_relaxa_inline_peso,
    test_coletor_01_corpus_dlo_inconsistencia_permite_inline_cid,
    test_mapeamento_retorno_bacen_termos_incluem_informe_2061,
    test_script_02_preserva_anexos_fwd_finaud,
    test_script_02_preserva_anexos_cliente_via_suporte_reply_to_externo,
    test_09_excluir_nome_salvo_acima_bytes_infra,
    test_triagem_retorno_bacen_ultima_fc_analise_aguarda_finaud,
    test_triagem_finaud_pedido_insumos_poderia_informar_qual,

    test_triagem_tids_strip_apenas_novos_classificados,
    test_executar_tudo_pula_etapa10_por_omissao,
    test_gestao_direcao_rota_template_e_agregacao,
    test_admin_pipeline_rotas_integracao_jobs,
    test_admin_pipeline_modal_confirmacao_e_grelha_passos,
    test_deletar_carga_mensagem_ui_admin_sem_executar_tudo_cli,
    test_oraculo_cenarios_print_run_executar_sem_seta_unicode,
    test_gestao_direcao_contatos_responsavel_tipos_flexiveis,
    test_equipe_gestao_direcao_sem_usuarios_json_so_operacional,
    test_ressurreicao_nao_remove_de_concluidas,
]
