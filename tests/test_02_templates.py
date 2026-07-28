"""
QA – Templates (email_operacional.html).

Contrato do frontend: decode MIME, CADOCs únicos, filtro de assinatura em anexos.
Alinhado à seção "Templates" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from tests.conftest import (
    RAIZ,
    cadoc_para_categoria_exibicao,
    decode_mime_header,
    deduplica_cadocs,
    filter_signature_from_attachment,
)


def test_decode_mime_utf8():
    """Decode MIME: UTF-8 Q-encoding → texto legível (ex.: Alison Guimarães)."""
    raw = "=?UTF-8?Q?=27Alison_Guimar=C3=A3es_de_Miranda=27_via_Suporte?="
    decoded = decode_mime_header(raw)
    assert "Alison" in decoded and "Guimar" in decoded, f"Esperado nome legível, obtido: {decoded!r}"


def test_decode_mime_iso8859():
    """Decode MIME: ISO-8859-1 Q-encoding → texto legível."""
    raw = "=?iso-8859-1?Q?Cristiano_Abdalla_=7C_Conecta_C=E2mbio?="
    decoded = decode_mime_header(raw)
    assert "Cristiano" in decoded or "Abdalla" in decoded or "Conecta" in decoded, f"Obtido: {decoded!r}"


def test_decode_mime_plain_passthrough():
    """Decode MIME: texto sem encoding =?…?= deve permanecer igual."""
    plain = "Andrea Inacio"
    assert decode_mime_header(plain) == plain


def test_deduplica_cadocs_uma_vez():
    """CADOCs: lista com repetição deve resultar em uma única ocorrência por CADOC."""
    lista = [{"cadoc": "DLO_2061"}, {"cadoc": "DLO_2061"}, {"cadoc": "DLO_2061"}]
    assert deduplica_cadocs(lista, "") == "DLO_2061"


def test_deduplica_cadocs_multiplos():
    """CADOCs: DLO_2061 e DLI_2062 devem aparecer uma vez cada."""
    lista = [{"cadoc": "DLO_2061"}, {"cadoc": "DLI_2062"}, {"cadoc": "DLO_2061"}]
    out = deduplica_cadocs(lista, "")
    assert "DLO_2061" in out and "DLI_2062" in out
    assert out.count("DLO_2061") == 1


def test_deduplica_cadocs_fallback():
    """CADOCs: lista vazia deve usar fallback ou '—'."""
    assert deduplica_cadocs([], "FILTRADO_POR_DATA") == "FILTRADO_POR_DATA"
    assert deduplica_cadocs([], "") == "—"


def test_cadoc_para_categoria_exibicao_nomes_curtos():
    """Rótulos de tela: chaves internas → DDR, DLO, SUPORTE, etc. (JSON/classificador inalterados)."""
    assert cadoc_para_categoria_exibicao("DDR_2011") == "DDR"
    assert cadoc_para_categoria_exibicao("DLO_2061") == "DLO"
    assert cadoc_para_categoria_exibicao("SUPORTE_GERAL") == "SUPORTE"
    assert cadoc_para_categoria_exibicao("S5") == "S5"
    assert cadoc_para_categoria_exibicao("RETORNO_BACEN") == "RETORNO BACEN"
    assert cadoc_para_categoria_exibicao("FILTRADO_POR_DATA") == "FILTRADO_POR_DATA"


def test_filtro_assinatura_remove_telefone_e_empresa():
    """Filtro de assinatura: remove telefone e linha 'A CONTÁBIL'."""
    corpo = "A CONTÁBIL\nComerciante: () (11) 98465-3820 & (11) 4281-1342\nm edsonQ&rfacontábil.com.br"
    out = filter_signature_from_attachment(corpo)
    assert "98465" not in out, "Telefone deve ser removido"
    assert "A CONTÁBIL" not in out, "Linha de assinatura deve ser removida"
    assert isinstance(out, str)


def test_filtro_assinatura_mantem_conteudo_traders():
    """Filtro de assinatura: NÃO remove conteúdo tipo TRADERS (Indício, Prazo)."""
    corpo = "Indício de qualidade\nCritica\nPrazo para ação\nDados do indício\nDLO00047"
    out = filter_signature_from_attachment(corpo)
    assert "Indício" in out or "Prazo" in out or "Dados" in out or "DLO00047" in out, f"Obtido: {out!r}"


def test_filtro_assinatura_mantem_linha_longa_com_email_no_meio():
    """2026-04: linha operacional longa com e-mail no texto (ex. disclaimer Moneycorp) não some inteira."""
    corpo = (
        "Boa tarde! Houve rejeição sob a crítica XML.\n"
        "Se recebeu por engano avise ouvidoria@moneycorp.com ou telefone antes de apagar.\n"
        "user@empresa.com.br"
    )
    out = filter_signature_from_attachment(corpo)
    assert "rejeição" in out and "XML" in out, f"Obtido: {out!r}"
    assert "ouvidoria@moneycorp.com" in out, f"E-mail no meio de frase longa deve permanecer: {out!r}"
    assert "user@empresa.com.br" not in out, "Linha curta só com e-mail continua a ser removida"


def test_template_tem_funcoes_decode_deduplica_filtro():
    """email_operacional.html deve conter decodeMimeHeader, deduplicaCadocs e filterSignatureFromAttachment."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "decodeMimeHeader" in html
    assert "deduplicaCadocs" in html
    assert "mapCadocInternoParaCategoriaExibicao" in html
    assert "filterSignatureFromAttachment" in html


def test_template_render_texto_imagens_e_anexos():
    """Modal: renderTextoImagensBlock estrutura OCR em tabelas + ficha (sem img no modal; 2026-04)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "renderTextoImagensBlock" in html, "Template deve ter função para bloco OCR"
    assert "ocr-ficha-table" in html
    assert "ocrTextoParaHtmlEstruturado" in html


def test_busca_inclui_aguardando_quando_pesquisa_ativa():
    """Com texto no Buscar (q), lista unificada inclui Aguardando e Concluídos que batem (mesmo dia)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "threadsListaBuscaUnificada" in html
    assert "options.section === 'busca'" in html
    assert "todos os status neste dia" in html
    assert "item.assunto" in html
    assert "item.responsavel" in html


def test_template_padrao_b_aceita_datas_dd_mm_yyyy():
    """Padrão B: toIso e fmtData/calcAtraso devem aceitar DD/MM/YYYY (evita undefined e NaNd).
    Correção 2026-03-12: lista_prazos do integrador vem em DD/MM/YYYY."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "function toIso(" in html
    assert "toIso(iso)" in html or "toIso(prazoIso)" in html
    assert "padStart(2,'0')" in html, "toIso deve normalizar DD/MM/YYYY para ISO"


def test_template_resumo_estruturado_ocr_painel_aguardando():
    """Resumo estruturado (contexto/pendência): painel Aguardando exibe quando IA retorna resumo_estruturado."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "aguardoResumoEstruturado" in html
    assert "aguardoResumoContextoTxt" in html
    assert "aguardoResumoPendenciaTxt" in html
    assert "aguardoIndicadoresPrazo" in html
    assert "resumo_estruturado" in html


def test_operacional_4_estados_fluxo():
    """4 estados do fluxo: Pendentes (sub-filtros), Aguardando, Concluídos (em mon.), Não resolvidos.
    Correção 2026-03-16: sem impactar exibição atual."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "já tem um registro em Aguardando" in html
    assert "Marcar como recebido" in html or "mAguardandoBtnRecebido" in html
    assert "Pendentes" in html
    assert "clickable-sub" in html
    assert "data-filter=\"aguardando\"" in html or "data-filter='aguardando'" in html
    assert "data-filter=\"nao_resolvidos\"" in html or "data-filter='nao_resolvidos'" in html
    assert "kpiEmMonitoramento" in html or "em mon." in html
    assert "diasSemInteracao" in html or "nao_resolvidos" in html


def test_operacional_somente_atividade_na_data_ref():
    """Com DATA REF, filtro opcional esconde acumulado (dia anterior sem mensagem na REF)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "somenteDiaRefBtn" in html
    assert "somenteAtividadeDataRef" in html
    assert "hintDataRefAcumulado" in html
    assert "eh_hoje === true" in html or "eh_hoje===true" in html
    assert "updateHintDataRefAcumulado" in html


def test_operacional_exportacao_csv_planilha():
    """Exportação CSV — todos os estados no recorte; colunas incl. Categoria."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="exportOperacionalCsv"' in html
    assert "exportarOperacionalListaCsv" in html
    assert "__oraculoExportLista" in html
    assert "threadsUnionParaExport" in html
    assert "text/csv;charset=utf-8" in html
    assert "textoSnippetCategorias" in html
    assert "Data da extração" in html
    assert "nomeArquivoExtracaoEmailCsv" in html
    assert "extracao_de_email_" in html
    assert "formatarDataRefParaColunaExtracao" in html
    assert "chaveAgrupamentoAssuntoExport" in html
    assert "linhasCsvComAgrupamentoAssunto" in html
    assert "Agrupamento automático" in html
    assert "function aplicarFusaoCardsAgrupamentoAssunto(" in html
    assert "function aplicarFusaoCardsParEAgrupAssunto(" in html
    assert "__oraculoCardAgrupPorTid" in html


def test_operacional_modal_linha_remetente_destinatario():
    """Modal do operacional: cada mensagem pode mostrar Remetente/Destinatário (Da/Para) + dica das pastilhas FINAUD/CLIENTE."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "function linhaDeParaModal(" in html
    assert "${linhaDeParaModal(msg)}" in html
    assert "${linhaDeParaModal(email)}" in html
    assert "modal-dica-remetente" in html
    assert "linhaIdentifFioModal" in html
    assert "rebuildThreadIdParaIdEventoMap" in html
    assert "__oraculoThreadIdParaIdEvento" in html
    assert "_fioThreadId" in html


@pytest.mark.xfail(reason="Pendente: layout.html usa flatpickr onChange, não atributo onchange direto (#calendário)", strict=False)
def test_layout_data_ref_dispara_onchange():
    """DATA REF: alteração da data deve disparar recarregamento via onchange."""
    path_layout = os.path.join(RAIZ, "templates", "layout.html")
    with open(path_layout, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="global-date"' in html
    assert "onchange=\"atualizarDataGlobal()\"" in html
    assert "dataAlterada" in html


def test_operacional_sincroniza_com_data_ref():
    """Operacional: dataAlterada e initOperacional usam global-date e loadDataComFiltro."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'getElementById("global-date")' in html
    assert "loadDataComFiltro" in html
    assert "dataAlterada" in html


@pytest.mark.xfail(reason="Pendente: thread_datas_presentes não implementado no painel ainda", strict=False)
def test_pendentes_filtra_por_data_ref():
    """DATA REF: ao selecionar 24/02, exibe threads que têm mensagem no dia (igual ao Gmail).
    Correção 2026-03-16: backend usa thread_datas_presentes; frontend não aplica filtro extra."""
    path_painel = os.path.join(RAIZ, "painel_oraculo.py")
    with open(path_painel, "r", encoding="utf-8") as f:
        code = f.read()
    assert "thread_datas_presentes" in code
    assert "dt_limite in datas_thread" in code


def test_modal_exibe_texto_imagens():
    """Modal: quando msg.texto_imagens existe, exibe bloco OCR (ficha + tabelas heurísticas; 2026-04)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "texto_imagens" in html
    assert "msg-texto-imagens--ficha" in html
    assert "Texto extraído (OCR)" in html


def test_modal_deduplica_encaminhados():
    """Modal: não exibe encaminhados que já são mensagens reais na thread (correção 2026-03-16)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "assinaturaMsg" in html, "Template deve ter função assinaturaMsg para deduplicar"
    assert "normalizarRemetenteAssinatura" in html
    assert "sigEncSemData" in html
    # RFC2047 e via Suporte — normalizarRemetenteAssinatura usa decodeMimeHeader
    sub = html[html.find("function normalizarRemetenteAssinatura"): html.find("function normalizarRemetenteAssinatura") + 450]
    assert "decodeMimeHeader" in sub
    assert "assinaturasVistas" in html
    assert "ehDuplicata" in html or "_encaminhado" in html


def test_modal_citacao_colapsavel():
    """Modal: citações aninhadas (estilo PDF) + tabela CRD via /api/crd_indicio_qualidade (2026-03)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "normalizarAssuntoParaComparar" in html
    assert "assuntoThreadNorm" in html
    assert "msg-subject-line" in html
    assert "previewTextoCitacao" in html
    assert "modal-cite-stack" in html
    assert "hydrateModalCrdBoxes" in html
    assert "extrairProtocoloIndicioCrd" in html
    assert "temCitacaoHistorico" in html
    assert "citacaoEhRedundante" in html
    assert "sanitizarPrefDedupCitacao" in html
    assert "gruposRev" in html
    assert "corpoCitPre" in html and "citacaoEhRedundante(corpoCitPre" in html
    assert "corpusCitacoesNorm" in html and "corposNormalizadosSaoRedundantes" in html
    assert "Duração:" in html and "nucleoTextoCitacaoParaDedup" in html
    assert "partesDot" in html and "[·•]" in html
    assert "textoMensagemRealSoCorpoParaDedup" in html
    assert "corporaDedup" in html
    assert "corpoMensagemApenasTopo" in html
    assert "0.68" in html and "mensagemPaiOpcional" in html
    assert "removerBannersSegurancaEmailDedup" in html
    assert "prioridade: alta" in html
    assert "corpoTopoSemEnc" in html


@pytest.mark.xfail(reason="Pendente: qa_citacao_dedup_dlo.js ainda não criado", strict=False)
def test_qa_node_citacao_dedup_dlo_dezembro():
    """Mesmo cenário da UI: 91914 com assunto DLO - DEZEMBRO + corpo_limpo [url].pdf vs citação só .pdf — redundante.
    + Gustavo 91939 (10:07) vs citação 10:08 com "Prioridade: Alta" (correção 2026-03-30).
    + Citação 19/02 vs corpo aninhado em 91939 não deve ser redundante (correção 2026-03-30)."""
    node = shutil.which("node")
    if not node:
        return
    script = os.path.join(RAIZ, "scripts", "qa_citacao_dedup_dlo.js")
    assert os.path.isfile(script), f"Falta {script}"
    r = subprocess.run([node, script], cwd=RAIZ, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"node qa_citacao_dedup_dlo.js falhou: {r.stderr or r.stdout}"


def test_operacional_filtro_empresa_toda_thread_e_url():
    """Operacional: filtro ?empresa= percorre todos os eventos da thread; dataAlterada re-lê URL.
    Deep link ?empresa= também força aba aberto (mesmo mecanismo que ?responsavel=)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "filterThreadsByEmpresa" in html
    assert "needle.indexOf(cl)" in html or "needle.indexOf" in html
    assert "pSync.get(\"empresa\")" in html or 'pSync.get("empresa")' in html
    assert "deepLinkFilaGestao" in html


def test_operacional_filtro_responsavel_visao_gestao():
    """Operacional: ao chegar com ?responsavel=Nome (ex.: da Visão Gestão), filtra lista por responsável.
    Correção 2026-03-16: Ver fila da Andrea deve mostrar só threads com Andrea Inacio.
    Correção 2026-03-24: deep link força aba aberto; filtro percorre todos os eventos da thread."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "filterThreadsByResponsavel" in html, "Template deve ter função de filtro por responsável"
    assert "filtroResponsavel" in html
    assert "chipFiltroResponsavel" in html
    assert "params.get(\"responsavel\")" in html or 'params.get("responsavel")' in html
    assert "deepLinkFilaGestao" in html
    assert "eventoCombinaResponsavel" in html or "needle.indexOf(hay)" in html
    assert "baseAberto" in html and "threadsAbertos" in html


def test_operacional_pares_sugeridos_ui():
    """Operacional: API expõe pares_sugeridos; card mostra bloco e função irParaParSugerido."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "PAR_SUGERIDOS" in html
    assert "pares_sugeridos" in html
    assert "irParaParSugerido" in html
    assert "card-par-sugerido" in html
    assert "confirmarParThreads" in html
    assert "pares_confirmados" in html
    assert "data-par-tid" in html and "data-par-outro" in html
    assert "card-par-btn-confirmar" in html
    assert "getElementById('listaOperacional')" in html
    assert "closest('.card-par-btn-confirmar')" in html
    assert "só capture aqui funciona" in html or "fase *capture*" in html


def test_operacional_banner_busca_e_evento_concluido():
    """Banner só com acervo global (?busca=1 sem DATA REF); eventoConcluidoOperacional no painel."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "bannerBuscaGlobal" in html
    assert "dadosModoBuscaCompleta" in html
    assert "eventoConcluidoOperacional" in html
    assert "dadosModoBuscaCompleta && !temData" in html or "&& !temData" in html


def test_operacional_busca_id_solo_ajusta_aba_e_limpar_volta_data():
    """ID Gmail só números → maybeSelectFilterForSoloIdNumeric; com DATA REF a busca só render() local; sem data pode ?busca=1."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "maybeSelectFilterForSoloIdNumeric" in html
    assert "\\d{5,10}" in html or "d{5,10}" in html
    i = html.find('getElementById("q").addEventListener("input"')
    assert i != -1
    bloco = html[i : i + 1200]
    assert "render(); // Atualiza imediatamente" not in bloco
    assert "if (q) {" in bloco and "temData" in bloco
    assert "loadDataComFiltro(gd.value)" in bloco
    j = html.find("async function loadDataParaBusca")
    assert j != -1
    blocoBusca = html[j : j + 900]
    assert "encodeURIComponent(dBusca)" in blocoBusca or ("&data=" in blocoBusca and "busca=1" in blocoBusca)


def test_operacional_modal_data_ref_e_sem_fallback_assunto():
    """Modal: filtra mensagens até DATA REF; sem fallback por assunto fixo (evita trocar thread ao abrir)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "filterMensagensAteDataRef" in html
    assert "parseGlobalDateToEndMs" in html
    assert "mDataRefAviso" in html
    assert "setModalAvisoDataRef" in html
    assert "Critica 2061" not in html, "Fallback por assunto genérico foi removido"
    assert "tidNorm" in html and "String(t.threadId).trim()" in html


def test_operacional_aguardando_exclui_concluidos():
    """Operacional: aba Aguardando não deve exibir threads com status concluído (correção 2026-03-23)."""
    path_html = os.path.join(RAIZ, "templates", "email_operacional.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "concluido" in html and "threadsAguardando" in html
    assert "status" in html and "concluido" in html.lower()
    assert "options.section" in html or 'section ===' in html, "Card deve ter pill conforme seção"


def test_gestao_analistas_dinamicos():
    """Visão Gestão: cards de analistas com contagem dinâmica (correção 2026-03-23)."""
    path_html = os.path.join(RAIZ, "templates", "gestao_prototipo.html")
    with open(path_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "gestao-pendentes" in html
    assert "gestao-urgentes" in html
    assert "porAnalista" in html or "responsavelContem" in html
    assert "Distribuição por clientes" in html
    assert "clientes-dist-row" in html
    assert "Sem empresa identificada" in html
    assert "gestao-clientes-total" in html
    assert "gestao-analistas-totais" in html
    assert "gestao-outros-responsaveis" in html
    assert "matchQualquerCardAnalista" in html or "outrosResp" in html
    assert "mapCadocInternoParaCategoriaExibicao" in html
    assert "rotuloGrupoCadoc" in html


TESTS = [
    test_decode_mime_utf8,
    test_decode_mime_iso8859,
    test_decode_mime_plain_passthrough,
    test_deduplica_cadocs_uma_vez,
    test_deduplica_cadocs_multiplos,
    test_deduplica_cadocs_fallback,
    test_cadoc_para_categoria_exibicao_nomes_curtos,
    test_filtro_assinatura_remove_telefone_e_empresa,
    test_filtro_assinatura_mantem_conteudo_traders,
    test_template_tem_funcoes_decode_deduplica_filtro,
    test_busca_inclui_aguardando_quando_pesquisa_ativa,
    test_template_padrao_b_aceita_datas_dd_mm_yyyy,
    test_template_resumo_estruturado_ocr_painel_aguardando,
    test_operacional_4_estados_fluxo,
    test_operacional_somente_atividade_na_data_ref,
    test_operacional_exportacao_csv_planilha,
    test_operacional_modal_linha_remetente_destinatario,
    test_layout_data_ref_dispara_onchange,
    test_operacional_sincroniza_com_data_ref,
    test_pendentes_filtra_por_data_ref,
    test_modal_exibe_texto_imagens,
    test_template_render_texto_imagens_e_anexos,
    test_modal_deduplica_encaminhados,
    test_modal_citacao_colapsavel,
    test_qa_node_citacao_dedup_dlo_dezembro,
    test_operacional_filtro_empresa_toda_thread_e_url,
    test_operacional_filtro_responsavel_visao_gestao,
    test_operacional_pares_sugeridos_ui,
    test_operacional_busca_id_solo_ajusta_aba_e_limpar_volta_data,
    test_operacional_banner_busca_e_evento_concluido,
    test_operacional_modal_data_ref_e_sem_fallback_assunto,
    test_operacional_aguardando_exclui_concluidos,
    test_gestao_analistas_dinamicos,
]
