"""
ORÁCULO 360 - Integrador de Dados (06)

Responsabilidade: ler a saída do classificador (02) e gerar a base unificada para o painel.
- Monta eventos (e-mails classificados com prazo, responsável, CADOC) e threads (conversas agrupadas).
- Aplica "ressurreição" de threads concluídas que tenham nova atividade (threads_concluidas.json).
- Threads só concluídas (sem nova msg) permanecem em ``threads[]`` para o modal (``/api/threads``); os cards vêm dos eventos.
- Limpa corpo de e-mail (assinaturas, citações) via limpar_corpo_email().

Entrada: 02_classificação_dados_brutos_gmail_editado.json, threads_concluidas.json.
Saída: 03_integrador_dados_site.json (consumido pelo painel: /api/dados, operacional, gerencial).
Não utiliza parâmetros de período; apenas agrega os JSONs já gerados.

Preservação de ``texto_imagens`` (OCR): o 02 em geral não traz esse campo; após o 09 enriquecer
o 03, uma nova corrida do 08 não deve esvaziar mensagens. Por omissão repomos a partir de
``cache_texto_imagens_validado.json`` e do backup ``03_integrador_dados_site.json.backup``
(03 anterior, criado antes de sobrescrever). Para regenerar o 03 sem repor OCR:
``INTEGRADOR_08_SEM_PRESERVAR_TEXTO_IMAGENS=1``.
"""
import json
import os
import re
import shutil
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
from html import unescape
from email.header import decode_header

try:
    import pytz
except ImportError:
    pytz = None

# ----------------------------------------------------------------------------
# CONFIGURAÇÃO DE CAMINHOS
# ----------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from paths import (F_EMAILS_CLASS, F_INTEGRADOR, F_INTEGRADOR_BACKUP,
                   F_EMAILS_BRUTOS,
                   PIPELINE_DIR, BACKUPS_DIR,
                   F_CADASTRO_CLIENTES,
                   load_concluidas, save_concluidas,
                   registrar_execucao, verificar_dependencias)
from pipeline_log import cabecalho, resumo as _resumo_log, Cronometro, iniciar_log_standalone

# ----------------------------------------------------------------------------
# RESOLUÇÃO DO CAMPO "empresa" (nome oficial via cadastro)
# ----------------------------------------------------------------------------

_cadastro_empresas_cache: dict | None = None

def _carregar_cadastro_empresas_09() -> dict:
    global _cadastro_empresas_cache
    if _cadastro_empresas_cache is None:
        try:
            with open(F_CADASTRO_CLIENTES, encoding="utf-8") as f:
                _cadastro_empresas_cache = json.load(f)
        except Exception:
            _cadastro_empresas_cache = {}
    return _cadastro_empresas_cache

_DOMINIOS_GENERICOS = frozenset({
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com",
    "msn.com", "yahoo.com", "yahoo.com.br", "icloud.com", "me.com",
    "bol.com.br", "uol.com.br", "terra.com.br", "ig.com.br", "protonmail.com",
})

def _nome_contato_seguro(d: dict) -> str:
    if not d or not isinstance(d, dict):
        return ""
    n = (d.get("nome") or "").strip()
    if n:
        return n
    em = (d.get("email") or "").strip()
    if em and "@" in em:
        return em.split("@")[0]
    return ""


def _responsavel_pela_acao(mensagens: list, fallback: str) -> str:
    """Responsável = quem recebeu a última mensagem (Para).
    C→F=Finaud, F→C=Cliente, C→C=Cliente, F→F=Finaud."""
    if not mensagens:
        return fallback
    ultima = sorted(mensagens, key=lambda m: m.get("timestamp_epoch", 0) or 0)[-1]
    cd = ultima.get("contato_destino") or {}
    return _nome_contato_seguro(cd) or fallback


def _resolver_empresa(evento: dict) -> str:
    """Resolve o nome oficial da empresa via cadastro_clientes_cadoc.json.
    Ordem: e-mail exato → domínio → nome da empresa no assunto → vazio.
    """
    cadastro = _carregar_cadastro_empresas_09()

    # Coleta e-mails do lado CLIENTE no evento e nas mensagens
    emails_cliente: list[str] = []
    for contato in (evento.get("contato_origem"), evento.get("contato_destino")):
        if isinstance(contato, dict) and (contato.get("lado") or "").upper() == "CLIENTE":
            em = (contato.get("email") or "").strip().lower()
            if em and "@" in em:
                emails_cliente.append(em)
    for msg in (evento.get("mensagens") or []):
        if not isinstance(msg, dict):
            continue
        for contato in (msg.get("contato_origem"), msg.get("contato_destino")):
            if isinstance(contato, dict) and (contato.get("lado") or "").upper() == "CLIENTE":
                em = (contato.get("email") or "").strip().lower()
                if em and "@" in em and em not in emails_cliente:
                    emails_cliente.append(em)

    for email in emails_cliente:
        # 1) E-mail exato
        for empresa, info in cadastro.items():
            if not isinstance(info, dict):
                continue
            for ex in (info.get("emails_exatos") or []):
                if isinstance(ex, str) and ex.strip().lower() == email:
                    return empresa
        # 2) Domínio
        dominio = email.split("@", 1)[1]
        if dominio in _DOMINIOS_GENERICOS or "finaud" in dominio:
            continue
        for empresa, info in cadastro.items():
            if not isinstance(info, dict):
                continue
            for d in (info.get("dominios") or []):
                if d and (dominio == d or dominio.endswith("." + d) or d in dominio):
                    return empresa

    # 3) Nome da empresa no assunto
    assunto = (evento.get("titulo") or evento.get("assunto") or "").strip().lower()
    if assunto:
        empresas_ord = sorted(
            [e for e in cadastro if e and len(e) >= 3],
            key=len, reverse=True
        )
        for empresa in empresas_ord:
            if empresa.lower() in assunto:
                return empresa

    return ""

PASTA_JSON = PIPELINE_DIR

ARQUIVO_ENTRADA_PREFERIDO = F_EMAILS_CLASS
ARQUIVO_ENTRADA_FALLBACK  = os.path.join(PIPELINE_DIR, "02_classificação_dados_brutos_gmail.json")

ARQUIVO_SAIDA  = F_INTEGRADOR

ARQUIVO_BACKUP = F_INTEGRADOR_BACKUP

try:
    from texto_imagens_cache import (
        load_por_id,
        merge_por_id_longest,
        restaurar_threads_se_vazio,
        texto_qualifica_para_cache,
    )
except ImportError:
    def load_por_id():  # type: ignore
        return {}

    def merge_por_id_longest(*_mapas):  # type: ignore
        return {}

    def restaurar_threads_se_vazio(_threads, _cache_map):  # type: ignore
        return 0

    def texto_qualifica_para_cache(s: str) -> bool:  # type: ignore
        return bool((s or "").strip())


# ----------------------------------------------------------------------------
# NOVA FUNÇÃO: Limpeza de Corpo de Email
# ----------------------------------------------------------------------------


def _cortar_rodape_assinatura_inline(texto: str) -> str:
    """
    Corta a partir de At.te / disclaimer / Atenciosamente, Nome no meio da linha (assinatura colada ao CEP).
    Alinhado a cortarRodapeAssinaturaInline em email_operacional.html.
    """
    if not texto or not isinstance(texto, str):
        return texto or ""
    norm = texto.replace("\r\n", "\n").replace("\r", "\n")
    idxs: List[int] = []
    m = re.search(r"\bAt\.?\s*te\b[,.]?\s*", norm, re.I)
    if m:
        idxs.append(m.start())
    m2 = re.search(
        r"\bEsta mensagem pode conter\s+(?:conte[uú]do|informa[cç][aã]o)\b",
        norm,
        re.I,
    )
    if m2:
        idxs.append(m2.start())
    m3 = re.search(r"\bAtenciosamente\s*,\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]", norm)
    if m3:
        idxs.append(m3.start())
    if not idxs:
        return texto
    idx = min(idxs)
    if idx <= 0:
        return ""
    return norm[:idx].rstrip()


def _cortar_apos_encerramento_cordial(texto: str) -> str:
    """
    Remove da primeira linha de encerramento (Atenciosamente, At.te, Att, etc.) até o fim.
    Não remove «Atenciosamente solicitamos» (texto após vírgula não começa com maiúscula de nome).
    Alinhado a cortarCorpoAposEncerramentoCordial em email_operacional.html.
    """
    if not texto or not isinstance(texto, str):
        return texto or ""
    lines = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def linha_eh_encerramento(raw: str) -> bool:
        s = raw.strip()
        if not s:
            return False
        if re.match(r"^(atenciosamente|atenciosos)[,.]?\s*$", s, re.I):
            return True
        if re.match(r"^at\.?\s*te\.?,?\s*$", s, re.I):
            return True
        if re.match(r"^att\.?,?\s*$", s, re.I):
            return True
        if re.match(r"^atte[,.]?\s*$", s, re.I):
            return True
        m = re.match(r"^(atenciosamente|atenciosos)\b([\s\S]*)$", s, re.I)
        if m:
            rest = (m.group(2) or "").strip()
            if not rest:
                return True
            if re.match(r"^[,.]\s*$", rest):
                return True
            after_comma = re.sub(r"^[,.]\s*", "", rest)
            if after_comma and re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]", after_comma):
                return True
            return False
        if re.match(r"^at\.?\s*te\b", s, re.I):
            return True
        if re.match(r"^cordialmente[,.]?\s*$", s, re.I):
            return True
        if re.match(r"^(abs|abra[çc]os|cumprimentos)[,.]?\s*$", s, re.I):
            return True
        if re.match(
            r"^(kind regards|best regards|regards|sincerely|yours sincerely|yours faithfully)[,.]?\s*$",
            s,
            re.I,
        ):
            return True
        if re.match(r"^(thanks|thank you)[,.]?\s*$", s, re.I):
            return True
        if re.match(r"^(obrigad[oa]|muito obrigad[oa])[,.]?\s*$", s, re.I):
            return True
        return False

    out = texto
    for i, ln in enumerate(lines):
        if linha_eh_encerramento(ln):
            out = "\n".join(lines[:i]).rstrip()
            break
    return _cortar_rodape_assinatura_inline(out)


def limpar_corpo_email(corpo_raw: str, mapa_cid: dict = None) -> str:
    """
    Remove assinaturas, citações, metadados e formatação do corpo do email.
    Resultado EXATAMENTE como VISUALIZACAO_DADOS_LIMPOS.md: só o texto principal.

    mapa_cid: dict {content_id_lower → arquivo_disco} construído a partir de
    anexos_detectados do e-mail; quando fornecido, substitui <img src="cid:X">
    por [imagem: arquivo.png] antes de remover as demais tags HTML.
    """
    if not corpo_raw:
        return ""

    texto = corpo_raw.replace('\r\n', '\n').replace('\r', '\n')

    # 0) #PF33: Remover blocos completos de <style>, <script> e <head> (conteúdo + tags).
    # Sem esta remoção, re.sub(r'<[^>]+>', '') abaixo apaga as tags mas deixa o CSS/JS
    # solto no texto (ex: "v\:* {behavior:url(#default#VML);}").
    texto = re.sub(r'<style[^>]*>.*?</style>', '', texto, flags=re.IGNORECASE | re.DOTALL)
    texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.IGNORECASE | re.DOTALL)
    texto = re.sub(r'<head[^>]*>.*?</head>', '', texto, flags=re.IGNORECASE | re.DOTALL)

    # 1) HTML — antes de remover tags, substituir <img cid:> por referência legível
    if mapa_cid:
        def _repl_img_cid(m):
            tag = m.group(0)
            src_m = re.search(r'src=["\']cid:([^"\'>\s]+)["\']', tag, re.IGNORECASE)
            if not src_m:
                return ''
            cid = src_m.group(1).lower().strip()
            arquivo = mapa_cid.get(cid, '')
            if arquivo:
                return f' [imagem: {arquivo}] '
            return ''  # cid sem arquivo correspondente — suprimir placeholder numérico
        texto = re.sub(r'<img\b[^>]*/?>', _repl_img_cid, texto, flags=re.IGNORECASE)

    texto = re.sub(r'<[^>]+>', '', texto)
    texto = unescape(texto)

    # 1b) Outlook/Word: imagens inline (assinatura, logos) viram [cid:...] no texto plano.
    # Cortar a partir do primeiro [cid: evita nome, cargo, endereço e segundo bloco de imagens da assinatura.
    m_cid = re.search(r"\[\s*cid\s*:\s*[^\]]+\]", texto, re.IGNORECASE)
    if m_cid:
        texto = texto[: m_cid.start()].strip()

    # 2) REMOVER BLOCO "Em ... escreveu:" e tudo depois (citação do email anterior)
    # Ex: "Em qua., 21 de jan. de 2026 às 17:08, Gabriel ... escreveu: Lucas, boa tarde!..."
    match_em_escreveu = re.search(r'\bEm\s+[\w.]+,?\s*\d{1,2}\s+de\s+\w+\.?\s+de\s+\d{4}.*?escreveu\s*:', texto, re.IGNORECASE | re.DOTALL)
    if match_em_escreveu:
        texto = texto[:match_em_escreveu.start()].strip()
    # Também "On ... wrote:"
    match_on_wrote = re.search(r'\bOn\s+[\w\s,]+\d{4}.*?wrote\s*:', texto, re.IGNORECASE | re.DOTALL)
    if match_on_wrote:
        texto = texto[:match_on_wrote.start()].strip()

    # 3) Linhas de metadados (De:, Enviado em:, Para:, Assunto:)
    for pattern in [
        r'^De:.*$', r'^From:.*$', r'^Para:.*$', r'^To:.*$', r'^Cc:.*$',
        r'^Assunto:.*$', r'^Subject:.*$', r'^Enviado em:.*$', r'^Sent:.*$',
        r'^Data:.*$', r'^Date:.*$',
    ]:
        texto = re.sub(pattern, '', texto, flags=re.MULTILINE | re.IGNORECASE)

    # 4) Linhas que começam com ">"
    linhas = [ln for ln in texto.split('\n') if not ln.strip().startswith('>') and not re.match(r'^[-=_]{3,}$', ln.strip())]
    texto = '\n'.join(linhas)

    texto = _cortar_apos_encerramento_cordial(texto)

    # 5) CORTAR NA ASSINATURA - mesmo sem newline antes (ex: "...alterações? Atenciosamente, Gabriel...")
    # Procurar a primeira ocorrência de qualquer marcador de assinatura e cortar dali
    marcas_assinatura = [
        # — com vírgula/ponto (já existiam) —
        "Atenciosamente,",
        "Atenciosamente.",
        "At.te,",
        "At.te.",
        "At. te,",
        "At.te ",
        "Cordialmente,",
        "Cordialmente.",
        "Att.",
        "Att,",
        "Abraços,",
        "Obrigado,",
        "Obrigada,",
        "Desde já agradeço",
        "Desde já permaneço",
        "Fico à disposição",
        "Permaneço à disposição",
        "Qualquer dúvida",
        "Best regards,",
        "Kind regards,",
        "Regards,",
        "Sincerely,",
        "Thanks,",
        "Thank you,",
        # — adicionados #PF33b: fechamentos sem vírgula e abreviações comuns —
        "\nAtenciosamente\n",   # 275 msgs: "Atenciosamente" sem vírgula antes do nome
        "\nAbs,\n",             # 186 msgs: abreviação de "Abraços"
        "\nAbs.\n",
        "\nAbs\n",
        "Grato,",               # 406 msgs: Grato/Grata/Saudações/Respeitosamente
        "Grato.",
        "Grata,",
        "Grata.",
        "Saudações,",
        "Saudações.",
        "Saudações\n",
        "Respeitosamente,",
        "Respeitosamente.",
        "Respeitosamente\n",
    ]
    pos_corte = len(texto)
    texto_lower = texto.lower()
    for marca in marcas_assinatura:
        idx = texto_lower.find(marca.lower())
        if idx != -1 and idx < pos_corte:
            pos_corte = idx
    texto = texto[:pos_corte].strip()

    # 6) Disclaimers (cortar tudo a partir daqui)
    for marca in [
        "Este e-mail pode conter",
        "This e-mail may contain",
        "This email may contain",
        "Esta mensagem e eventuais anexos podem conter",
        "Esta mensagem pode conter",
        "Este e-mail (inclusive seus anexos) é confidencial",
        "This e-mail (including any attachments) is confidential",
        "This email (including any attachments) is confidential",
        # Variante comum (ex.: BCP e outros bancos/corretoras): sem “(including any attachments)”
        "This email is confidential",
        "In the event this communication originates",
        "In the event this communication contains",
        "Se você recebeu este e-mail equivocadamente",
        "If you have received this e-mail in error",
        "If you have received this email in error",
        "AVISO LEGAL:",
        "CONFIDENTIALITY NOTICE:",
        "To unsubscribe from this group",
        "Antes de imprimir pense na sua responsabilidade",
        # — adicionados #PF33b: rodapés corporativos e mensagens automáticas —
        "Classificação: Interno",        # 552 msgs: tag de classificação de e-mail corporativo
        "Classificação: Pública",
        "Classificação: Público",
        "Classificação: Externo",
        "Por favor não responda a este e-mail",   # 649 msgs: rodapés de e-mail automático
        "Este é um e-mail automático",
        "Gerado automaticamente por FINAUD",
        "This message was sent automatically",
    ]:
        idx = texto.find(marca)
        if idx != -1:
            texto = texto[:idx].strip()

    # 7) Limpeza final
    texto = re.sub(r'\n{3,}', '\n\n', texto).strip()
    texto = re.sub(r' {2,}', ' ', texto)
    return texto.strip()


def _cortar_disclaimers_corpo(texto: str) -> str:
    """
    Corta a partir de avisos de confidencialidade / legais.
    Usado quando o corpo_limpo vem do 02 e ainda traz esses trechos.
    """
    if not texto or not isinstance(texto, str):
        return texto or ""
    t = texto
    marcas = [
        "Este e-mail (inclusive seus anexos) é confidencial",
        "This e-mail (including any attachments) is confidential",
        "This email (including any attachments) is confidential",
        "This email is confidential",
        "In the event this communication originates",
        "In the event this communication contains",
        "Se você recebeu este e-mail equivocadamente",
        "If you have received this e-mail in error",
        "If you have received this email in error",
        "Este e-mail pode conter",
        "Esta mensagem pode conter",
        "This e-mail may contain",
        "To unsubscribe from this group",
    ]
    for marca in marcas:
        idx = t.find(marca)
        if idx != -1:
            t = t[:idx].strip()
    return t.strip()


# ----------------------------------------------------------------------------
# Helpers para e-mails encaminhados (De:/Enviada em:/Assunto:) dentro do corpo
# ----------------------------------------------------------------------------

_RODAPE_CITACAO_INICIO = [
    "\n___________________",
    "\n-----Original Message-----",
    "\n________________________________",
    "\nAVISO IMPORTANTE:",
    "\nAntes de imprimir pense na sua responsabilidade",
    "\nEste e-mail pode conter informação confidencial",
    "\nEste e-mail pode conter informação confidencial, privilegiada",
    "\nThis e-mail may contain information that is confidential",
    "\nThis e-mail may contain information that is confidential, privileged",
    "\nThis email may contain information that is confidential",
    "\nTo unsubscribe from this group",
    "\nTo unsubscribe from this",
    "\nMensagem referente ao Correio Eletrônico:",
    "\nEsta mensagem não deve ser respondida",
    "\nCONFIDENTIALITY NOTICE:",
]


def _truncar_citacoes_aninhadas_corpo_enc(corpo: str, max_pass: int = 24) -> str:
    """
    Remove de um corpo de encaminhado/citação o trecho após um novo cabeçalho
    Outlook/EN (De:/From: seguido de Enviada em/Date e Assunto/Subject).

    Sem isso, o nível 19/02 repete texto dos níveis 18 e 17 já extraídos como outros itens.
    """
    if not corpo or not isinstance(corpo, str):
        return corpo or ""
    t = corpo.replace("\r\n", "\n").replace("\r", "\n")
    for _ in range(max_pass):
        changed = False
        m = re.search(r"\nDe:\s", t, re.IGNORECASE)
        if m:
            tail = t[m.start() :]
            head = t[: m.start()]
            hl = tail[:1200]
            if re.search(r"Enviada\s+em:|Enviadas:", hl, re.IGNORECASE) and re.search(
                r"(?:^|\n)\s*Assunto:", hl, re.IGNORECASE
            ):
                t = head.rstrip()
                changed = True
        if not changed:
            m2 = re.search(r"\nFrom:\s", t, re.IGNORECASE)
            if m2:
                tail = t[m2.start() :]
                head = t[: m2.start()]
                hl = tail[:1200]
                if re.search(r"Date:", hl, re.IGNORECASE) and re.search(
                    r"(?:^|\n)\s*Subject:", hl, re.IGNORECASE
                ):
                    t = head.rstrip()
                    changed = True
        if not changed:
            break
    return t.strip()


def _strip_rodapes_citacao_genericos(corpo: str, max_pass: int = 12) -> str:
    """
    Corta rodapés comuns (Trustee, BC, listas de e-mail) que poluem citações.
    Aplica iterativamente o marcador mais à esquerda para não deixar sobras.
    """
    if not corpo or not isinstance(corpo, str):
        return corpo or ""
    t = corpo.replace("\r\n", "\n").replace("\r", "\n")
    for _ in range(max_pass):
        cut = None
        for mk in _RODAPE_CITACAO_INICIO:
            p = t.find(mk)
            if p > 0 and (cut is None or p < cut):
                cut = p
        if cut is None:
            break
        t = t[:cut].rstrip()
    return t.strip()


def _sanear_corpo_item_encaminhado(corpo: str) -> str:
    """Encadeia truncamento de citação aninhada + remoção de rodapés genéricos."""
    t = _truncar_citacoes_aninhadas_corpo_enc(corpo)
    t = _strip_rodapes_citacao_genericos(t)
    return (t or "").strip()


def _decode_mime_words(s: str) -> str:
    """Decodifica cabeçalhos MIME (=?utf-8?Q?...?=) quando presentes."""
    if not isinstance(s, str) or "=?".encode() is None:
        return s or ""
    try:
        parts = decode_header(s)
        out = ""
        for chunk, enc in parts:
            if isinstance(chunk, bytes):
                out += chunk.decode(enc or "utf-8", errors="replace")
            else:
                out += str(chunk)
        return out
    except Exception:
        return s or ""


def _encontrar_blocos_encaminhados(texto: str) -> List[str]:
    """
    Retorna blocos dentro de 'texto' que parecem e-mails encaminhados.
    Suporta formatos comuns:
      - Outlook/PT: "De:" + "Enviada em:" + "Assunto:"
      - Gmail/EN: "From:" + "Date:" + "Subject:"
    """
    if not texto:
        return []

    t = texto.replace("\r\n", "\n")
    blocos: List[str] = []

    inicios = ["\nDe:", "De:", "\nFrom:", "From:"]
    idx = 0
    while True:
        inicio_pos = -1
        inicio_tag = None
        for tag in inicios:
            p = t.find(tag, idx)
            if p != -1 and (inicio_pos == -1 or p < inicio_pos):
                inicio_pos = p
                inicio_tag = tag.strip()
        if inicio_pos == -1:
            break

        resto = t[inicio_pos:]
        tem_outlook = (("Enviada em:" in resto or "Enviadas:" in resto) and "Assunto:" in resto)
        tem_gmail = ("Date:" in resto and "Subject:" in resto)
        if not (tem_outlook or tem_gmail):
            idx = inicio_pos + 2
            continue

        fim = len(t)
        for marcador in [
            "To unsubscribe from this group",
            "To unsubscribe from this",
            "\nDe:",
            "\nFrom:",
        ]:
            busca_de = 1 if marcador in ("\nDe:", "\nFrom:") and resto.startswith(marcador) else 0
            pos = resto.find(marcador, busca_de)
            if pos != -1:
                cand = inicio_pos + pos
                if cand > inicio_pos:
                    fim = min(fim, cand)

        bloco = t[inicio_pos:fim].strip()
        if bloco:
            blocos.append(bloco)
        # Avançar até o fim do bloco (evita reprocessar o mesmo texto e blocos sobrepostos)
        idx = fim if fim > inicio_pos else inicio_pos + 1

    return blocos


def _extrair_campo_enc(bloco: str, chaves: List[str]) -> str:
    for chave in chaves:
        m = re.search(rf"^{re.escape(chave)}\s*(.*)$", bloco, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def _parse_bloco_encaminhado(bloco: str) -> Dict[str, str]:
    """
    Retorna dict com campos padronizados:
      - data_email_br: "DD/MM/YYYY HH:MM" quando possível
      - de, para, assunto, corpo
    """
    b = bloco.replace("\r\n", "\n").strip()

    de = _extrair_campo_enc(b, ["De:", "From:"])
    para = _extrair_campo_enc(b, ["Para:", "To:"])
    assunto = _extrair_campo_enc(b, ["Assunto:", "Subject:"])
    enviada = _extrair_campo_enc(b, ["Enviada em:", "Enviadas:", "Date:"])

    corpo = ""
    assunto_idx = None
    for key in ["Assunto:", "Subject:"]:
        pos = b.lower().find(key.lower())
        if pos != -1:
            assunto_idx = pos
            break
    if assunto_idx is not None:
        tail = b[assunto_idx:]
        tail_lines = tail.split("\n")
        if len(tail_lines) > 1:
            corpo = "\n".join(tail_lines[1:]).strip()

    # Normalizar data BR (ex.: "quinta-feira, 12 de fevereiro de 2026 08:30")
    data_email_br = ""
    m = re.search(r"(\d{1,2})\s+de\s+([a-zç]+)\s+de\s+(\d{4})\s+(\d{2}:\d{2})", enviada, flags=re.IGNORECASE)
    if m:
        dia = int(m.group(1))
        mes_nome = m.group(2).lower()
        ano = int(m.group(3))
        hhmm = m.group(4)
        meses = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
            "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
            "outubro": 10, "novembro": 11, "dezembro": 12,
        }
        meses_curtos = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
                       "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
        mes = meses.get(mes_nome) or meses_curtos.get(mes_nome.rstrip("."))
        if mes:
            data_email_br = f"{dia:02d}/{mes:02d}/{ano} {hhmm}"

    return {
        "de": _decode_mime_words(de),
        "para": _decode_mime_words(para),
        "assunto": _decode_mime_words(assunto),
        "enviada_em_raw": enviada,
        "data_email_br": data_email_br,
        "corpo": corpo.strip(),
    }


def _extrair_citacoes_escreveu(corpo_raw: str) -> List[Dict[str, str]]:
    """
    Extrai citações no formato "Em dia, DD de MMM de AAAA às HH:MM, Nome <email> escreveu:".
    Retorna lista de dicts com data_email, de, para, assunto, corpo (para/assunto vazios).
    """
    if not corpo_raw:
        return []
    texto = corpo_raw.replace("\r\n", "\n")
    citacoes: List[Dict[str, str]] = []
    meses_curtos = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
                    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
    for m in re.finditer(r"Em\s+.+?escreveu:\s*", texto, re.IGNORECASE | re.DOTALL):
        cabecalho = m.group(0)
        inicio_corpo = m.end()
        proximo = texto.find("\nEm ", inicio_corpo)
        if proximo == -1:
            proximo = len(texto)
        corpo = texto[inicio_corpo:proximo].strip()
        if not corpo:
            continue
        dm = re.search(r"(\d{1,2})\s+de\s+(\w+)\.?\s+de\s+(\d{4})\s+às\s+(\d{2}:\d{2}),\s*([^<]+)", cabecalho, re.IGNORECASE)
        data_email_br = ""
        de = ""
        if dm:
            dia, mes_str, ano = int(dm.group(1)), dm.group(2).lower().rstrip("."), int(dm.group(3))
            hhmm = dm.group(4)
            mes = meses_curtos.get(mes_str)
            if mes:
                data_email_br = f"{dia:02d}/{mes:02d}/{ano} {hhmm}"
            de = _decode_mime_words(dm.group(5).strip())
        citacoes.append({
            "data_email": data_email_br,
            "de": de,
            "para": "",
            "assunto": "",
            "corpo": corpo[:80000],
        })
    return citacoes


def _extrair_encaminhados_de_corpo(corpo_raw: str) -> List[Dict[str, str]]:
    """
    Extrai submensagens encaminhadas de dentro do corpo bruto de um e-mail.
    Inclui blocos De:/Enviada em:/Assunto: e citações "Em ... escreveu:".
    Retorna lista de dicts com campos:
      - data_email, de, para, assunto, corpo
    """
    if not corpo_raw:
        return []
    blocos = _encontrar_blocos_encaminhados(corpo_raw)
    encaminhados: List[Dict[str, str]] = []
    for b in blocos:
        pb = _parse_bloco_encaminhado(b)
        if not pb.get("corpo"):
            continue
        data_email = pb.get("data_email_br") or ""
        corpo_san = _sanear_corpo_item_encaminhado(pb.get("corpo") or "")
        if not corpo_san:
            continue
        encaminhados.append(
            {
                "data_email": data_email,
                "de": pb.get("de") or "",
                "para": pb.get("para") or "",
                "assunto": pb.get("assunto") or "",
                "corpo": corpo_san[:15000],
            }
        )
    citacoes = _extrair_citacoes_escreveu(corpo_raw)
    for c in citacoes:
        corpo_san = _sanear_corpo_item_encaminhado(c.get("corpo") or "")
        if not corpo_san:
            continue
        encaminhados.append({
            "data_email": c.get("data_email") or "",
            "de": c.get("de") or "",
            "para": c.get("para") or "",
            "assunto": c.get("assunto") or "",
            "corpo": corpo_san[:15000],
        })
    return encaminhados


def _extrair_remetente_original_fwd(corpo_raw: str) -> str:
    """
    #PF45: Extrai o remetente do e-mail original dentro de um encaminhamento.
    Prioriza remetentes @bcb.gov.br (notificações BACEN encaminhadas pelo cliente).
    Retorna o e-mail encontrado ou string vazia se não houver encaminhamento.
    """
    if not corpo_raw:
        return ""
    matches = re.findall(
        r'(?:^|\n)\s*(?:De|From)\s*:\s*[^\n<]*?([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
        corpo_raw, re.IGNORECASE
    )
    if not matches:
        return ""
    # Priorizar @bcb.gov.br
    for m in matches:
        if "bcb.gov.br" in m.lower():
            return m.lower().strip()
    # Fallback: primeiro remetente encontrado
    return matches[0].lower().strip()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _parse_data_br(data_email: str) -> Tuple[str, str, int]:
    """
    Recebe 'DD/MM/YYYY HH:MM' (em horário de Brasília), RFC ou ISO e devolve:
      - data_iso (YYYY-MM-DD)
      - timestamp_display (DD/MM/YYYY HH:MM)
      - timestamp_epoch (int, UTC)
    Strings DD/MM/YYYY HH:MM sem timezone são interpretadas como America/Sao_Paulo.
    """
    if not data_email:
        return "", "", 0

    tz_br = pytz.timezone("America/Sao_Paulo") if pytz else None

    # Formato esperado do 02 (classificador): 'DD/MM/YYYY HH:MM' já em horário de Brasília
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(data_email.strip(), fmt)
            if tz_br is not None:
                dt = tz_br.localize(dt)
                ts = int(dt.astimezone(pytz.UTC).timestamp())
            else:
                ts = int(dt.timestamp())
            return dt.strftime("%Y-%m-%d"), dt.strftime("%d/%m/%Y %H:%M"), ts
        except Exception:
            pass

    # Fallback: ISO (Z = UTC)
    try:
        dt = datetime.fromisoformat(data_email.replace("Z", "+00:00").strip())
        if dt.tzinfo is None and pytz:
            dt = pytz.UTC.localize(dt)
        if dt.tzinfo is not None and pytz:
            ts = int(dt.astimezone(pytz.UTC).timestamp())
            dt_br = dt.astimezone(tz_br)
            return dt_br.strftime("%Y-%m-%d"), dt_br.strftime("%d/%m/%Y %H:%M"), ts
        return dt.strftime("%Y-%m-%d"), dt.strftime("%d/%m/%Y %H:%M"), int(dt.timestamp())
    except Exception:
        pass

    # Fallback: RFC 2822 (ex.: "Fri, 13 Feb 2026 14:48:31 +0000") — do 01 quando 04 não converteu
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(data_email.strip())
        if dt.tzinfo is None and pytz:
            dt = pytz.UTC.localize(dt)
        if pytz and dt.tzinfo is not None:
            ts = int(dt.astimezone(pytz.UTC).timestamp())
            dt_br = dt.astimezone(tz_br)
            return dt_br.strftime("%Y-%m-%d"), dt_br.strftime("%d/%m/%Y %H:%M"), ts
        return dt.strftime("%Y-%m-%d"), dt.strftime("%d/%m/%Y %H:%M"), int(dt.timestamp())
    except Exception:
        pass

    print(f"[AVISO] timestamp_epoch=0 — data não reconhecida: {data_email!r}")
    return "", data_email, 0


def _carregar_entrada() -> Dict[str, Any]:
    """Carrega o JSON de entrada preferindo o arquivo *_editado.json."""
    for caminho in (ARQUIVO_ENTRADA_PREFERIDO, ARQUIVO_ENTRADA_FALLBACK):
        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    dados = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                raise RuntimeError(f"Arquivo de entrada encontrado mas nao pode ser lido ({caminho}): {e}") from e

            # Valida se o arquivo tem conteúdo mínimo para evitar sobrescrever dados bons com arquivo vazio
            emails = dados if isinstance(dados, list) else dados.get("emails_processados") or dados.get("emails") or []
            if len(emails) < 5:
                raise RuntimeError(
                    f"Arquivo de entrada suspeito — apenas {len(emails)} registro(s) em {os.path.basename(caminho)}. "
                    "Verifique se o script 05 rodou corretamente antes de continuar."
                )
            return dados

    raise FileNotFoundError("Nenhum arquivo de entrada encontrado (02_classificacao...).")


def _normalizar_lista_emails(payload: Any) -> List[Dict[str, Any]]:
    """Retorna uma lista de emails no formato esperado pelo integrador."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("emails_processados"), list):
            return payload["emails_processados"]
        # compat: alguns formatos podem usar 'emails'
        if isinstance(payload.get("emails"), list):
            return payload["emails"]
    return []


def _injetar_cadoc_em_prazos(prazos: Any, cadoc: str) -> List[Dict[str, Any]]:
    """Garante que cada item da lista de prazos tenha o campo 'cadoc' preenchido (com cadoc quando faltar)."""
    if not isinstance(prazos, list):
        return []
    out = []
    for p in prazos:
        if not isinstance(p, dict):
            continue
        p2 = dict(p)
        p2.setdefault("cadoc", cadoc)
        out.append(p2)
    return out


def _filtrar_prazos_regra_negocio(
    lista_prazos: List[Dict[str, Any]], cadoc: str, assunto: str
) -> List[Dict[str, Any]]:
    """
    Regras de negócio: para DLO_2061 (Remessa Demonstrações B3), exibir apenas o prazo
    data_base 30/11/2025 → prazo_limite 05/01/2026. Demais casos retorna a lista inalterada.
    """
    if not lista_prazos or cadoc != "DLO_2061":
        return lista_prazos
    assunto_upper = (assunto or "").upper()
    if "REMESSA" not in assunto_upper or "B3" not in assunto_upper:
        return lista_prazos
    filtrado = [
        p for p in lista_prazos
        if (p.get("data_base") == "30/11/2025" and p.get("prazo_limite") == "05/01/2026")
    ]
    return filtrado if filtrado else lista_prazos


def _calcular_status(item: Dict[str, Any]) -> str:
    """Marcador pré-motor: thread ainda não passou pela triagem automática."""
    return "SEM_TRIAGEM"


def _responsabilidade_por_lado(email_proc: Dict[str, Any]) -> str:
    """
    Regra de negócio (conforme você descreveu):
      - Se CLIENTE enviou para FINAUD -> pendência é FINAUD
      - Se FINAUD enviou para CLIENTE -> pendência é CLIENTE
    Na prática: responsabilidade = contato_destino.lado (FINAUD/CLIENTE)
    """
    contato_dest = email_proc.get("contato_destino") or {}
    lado = (contato_dest.get("lado") or "").upper().strip()
    return lado if lado in ("FINAUD", "CLIENTE") else ""


# ----------------------------------------------------------------------------
# Corpo no evento individual (alinha às mensagens em _processar_threads)
# ----------------------------------------------------------------------------

def _corpo_evento_a_partir_classificador(e: Dict[str, Any],
                                          _anexos_por_id: dict = None) -> Tuple[str, str]:
    """
    O classificador (02) costuma preencher ``corpo_limpo`` sem repetir ``corpo`` texto puro.
    Sem isto, ``eventos[]`` no 03 ficam com corpo vazio e o modal (fallback por evento) não mostra texto.

    _anexos_por_id: mapa id→[{arquivo_disco, content_id}] carregado do JSON01; quando fornecido,
    permite substituir <img cid:X> por [imagem: arquivo.png] no corpo_limpo.
    """
    corpo_limpo_02 = (e.get("corpo_limpo") or "").strip()
    corpo_raw = (e.get("corpo") or "").strip()
    if not corpo_raw:
        corpo_raw = (e.get("corpo_html") or "").strip()

    # Construir mapa_cid a partir do JSON01 (via _anexos_por_id)
    mapa_cid = {}
    if _anexos_por_id is not None:
        for a in (_anexos_por_id.get(str(e.get("id") or ""), [])):
            cid = (a.get("content_id") or "").strip().strip("<>").lower()
            arq = a.get("arquivo_disco", "")
            if cid and arq:
                mapa_cid[cid] = arq

    # Se o corpo_raw tem referências cid: que podemos substituir, regenerar mesmo
    # que corpo_limpo_02 já exista (ele foi gerado antes do fix de cid)
    tem_cid_substituivel = bool(mapa_cid) and bool(
        re.search(r'src=["\']cid:', corpo_raw, re.IGNORECASE))

    if corpo_limpo_02 and corpo_limpo_02 != "(sem conteúdo textual)" and not tem_cid_substituivel:
        corpo_limpo = _cortar_disclaimers_corpo(corpo_limpo_02)
    else:
        corpo_limpo = _cortar_disclaimers_corpo(limpar_corpo_email(corpo_raw, mapa_cid or None))
    return corpo_raw, corpo_limpo


def _mapa_texto_imagens_desde_03_dict(dados_03: Dict[str, Any]) -> Dict[str, str]:
    """Extrai id de mensagem/evento → texto_imagens mais longo a partir de um 03 já gerado."""
    out: Dict[str, str] = {}
    if not isinstance(dados_03, dict):
        return out
    for t in dados_03.get("threads") or []:
        if not isinstance(t, dict):
            continue
        for msg in t.get("mensagens") or []:
            if not isinstance(msg, dict):
                continue
            mid = str(msg.get("id") or msg.get("message_id") or "").strip()
            if not mid:
                continue
            ti = (msg.get("texto_imagens") or "").strip()
            if not texto_qualifica_para_cache(ti):
                continue
            ant = (out.get(mid) or "").strip()
            if len(ti) > len(ant):
                out[mid] = ti
    for ev in dados_03.get("eventos") or []:
        if not isinstance(ev, dict):
            continue
        mid = str(ev.get("id") or "").strip()
        if not mid:
            continue
        ti = (ev.get("texto_imagens") or "").strip()
        if not texto_qualifica_para_cache(ti):
            continue
        ant = (out.get(mid) or "").strip()
        if len(ti) > len(ant):
            out[mid] = ti
    return out


def _sincronizar_texto_imagens_eventos_de_threads(
    eventos: List[Dict[str, Any]], threads: List[Dict[str, Any]]
) -> None:
    """Preenche evento['texto_imagens'] a partir das mensagens das threads quando o evento está vazio."""
    por_id: Dict[str, str] = {}
    for t in threads or []:
        for msg in (t.get("mensagens") or []):
            mid = msg.get("id") or msg.get("message_id")
            if mid is None:
                continue
            ti = (msg.get("texto_imagens") or "").strip()
            if not ti:
                continue
            s = str(mid)
            ant = (por_id.get(s) or "").strip()
            if len(ti) > len(ant):
                por_id[s] = ti
    for ev in eventos or []:
        if (ev.get("texto_imagens") or "").strip():
            continue
        eid = ev.get("id")
        if eid is None:
            continue
        ti = por_id.get(str(eid))
        if ti:
            ev["texto_imagens"] = ti


# ----------------------------------------------------------------------------
# NOVA FUNÇÃO: Processar threads_processadas do 01_b
# ----------------------------------------------------------------------------

def _processar_thread_unica(thread: Dict[str, Any], _anexos_por_id: dict) -> "Dict[str, Any] | None":
    """Processa uma única thread. Separado para permitir timeout por item."""
    mensagens = thread.get("mensagens", [])
    if not mensagens:
        return None

    ultima_msg = mensagens[-1]
    primeira_msg = mensagens[0]
    cliente = ""
    origem = primeira_msg.get("contato_origem", {})
    destino = primeira_msg.get("contato_destino", {})

    if origem.get("lado") == "CLIENTE":
        cliente = origem.get("nome", "") or origem.get("email", "")
    elif destino.get("lado") == "CLIENTE":
        cliente = destino.get("nome", "") or destino.get("email", "")
    elif origem.get("lado") == "FINAUD" and destino.get("lado") == "FINAUD":
        cliente = (primeira_msg.get("cliente") or "").strip()
        if not cliente:
            cliente = destino.get("nome", "") or destino.get("email", "")
    if not cliente:
        cliente = "CLIENTE_DESCONHECIDO"

    data_ultima = ultima_msg.get("data_email", "")
    data_iso, timestamp_display, ts_epoch = _parse_data_br(data_ultima)

    mensagens_formatadas = []
    ids_vistos: set = set()
    fingerprints_vistos: set = set()
    for msg in mensagens:
        msg_id = msg.get("id") or msg.get("message_id")
        chave_id = str(msg_id) if msg_id is not None else None
        data_email = (msg.get("data_email") or "").strip()
        corpo_fp = (msg.get("corpo_limpo") or msg.get("corpo") or "")[:500]
        fingerprint = (data_email, corpo_fp)
        if chave_id is not None and chave_id in ids_vistos:
            continue
        if fingerprint in fingerprints_vistos:
            continue
        if chave_id is not None:
            ids_vistos.add(chave_id)
        fingerprints_vistos.add(fingerprint)

        msg_data_iso, msg_timestamp_display, msg_ts_epoch = _parse_data_br(msg.get("data_email", ""))
        corpo_limpo_01b = msg.get("corpo_limpo", "").strip()
        corpo_raw = msg.get("corpo", "")

        mapa_cid_msg = {}
        for a in (_anexos_por_id.get(str(msg.get("id") or ""), [])):
            cid = (a.get("content_id") or "").strip().strip("<>").lower()
            arq = a.get("arquivo_disco", "")
            if cid and arq:
                mapa_cid_msg[cid] = arq

        tem_cid_sub = bool(mapa_cid_msg) and bool(
            re.search(r'src=["\']cid:', corpo_raw, re.IGNORECASE))

        if corpo_limpo_01b and corpo_limpo_01b != "(sem conteúdo textual)" and not tem_cid_sub:
            corpo_limpo = corpo_limpo_01b
        else:
            corpo_limpo = limpar_corpo_email(corpo_raw, mapa_cid_msg or None)
        corpo_limpo = _cortar_disclaimers_corpo(corpo_limpo)

        mensagens_formatadas.append({
            "id": msg.get("id"),
            "data_email": msg.get("data_email"),
            "data_iso": msg_data_iso,
            "timestamp": msg_timestamp_display,
            "timestamp_epoch": msg_ts_epoch,
            "assunto": msg.get("assunto"),
            "contato_origem": msg.get("contato_origem", {}),
            "contato_destino": msg.get("contato_destino", {}),
            "responsavel": msg.get("responsavel"),
            "cadoc": msg.get("cadoc"),
            "prazos": _filtrar_prazos_regra_negocio(
                _injetar_cadoc_em_prazos(msg.get("prazos", []), thread.get("cadoc", "")),
                thread.get("cadoc", ""), thread.get("assunto", ""),
            ),
            "corpo": corpo_raw,
            "corpo_limpo": corpo_limpo,
            "formato_corpo": msg.get("formato_corpo", "texto"),
            "texto_imagens": (msg.get("texto_imagens") or "").strip(),
            "encaminhados": _extrair_encaminhados_de_corpo(corpo_raw),
            "remetente_original_fwd": _extrair_remetente_original_fwd(corpo_raw),
            "anexos_detectados": _anexos_por_id.get(str(msg.get("id") or ""), []),
        })

    # (o restante do processamento da thread continua abaixo — cadoc, responsável, etc.)
    # Retorna estrutura parcial; será complementada em _processar_threads
    return {
        "_thread_original": thread,
        "_mensagens_formatadas": mensagens_formatadas,
        "_cliente": cliente,
        "_data_iso": data_iso,
        "_timestamp": timestamp_display,
        "_ts_epoch": ts_epoch,
    }


def _processar_threads(threads_raw: List[Dict[str, Any]], _anexos_por_id: dict = None) -> List[Dict[str, Any]]:
    """
    Transforma threads_processadas do 01_b para o formato do painel.

    AGORA COM LIMPEZA DE TEXTO via limpar_corpo_email() e timeout por thread.
    """
    from pipeline_watchdog import processar_com_timeout
    _timeout_thread = int(os.environ.get("ORACULO_TIMEOUT_THREAD", "30"))
    _erros_timeout = 0

    if _anexos_por_id is None:
        _anexos_por_id = {}
    threads_formatadas = []

    for thread in threads_raw:
        if not isinstance(thread, dict):
            continue

        mensagens = thread.get("mensagens", [])
        if not mensagens:
            continue

        _tid = thread.get("threadId") or "?"
        _desc = f"thread {_tid} ({len(mensagens)} msgs)"

        parcial, _ok = processar_com_timeout(
            _processar_thread_unica, (thread, _anexos_por_id),
            timeout_s=_timeout_thread,
            item_desc=_desc,
        )
        if not _ok or parcial is None:
            _erros_timeout += 1
            continue

        mensagens_formatadas = parcial["_mensagens_formatadas"]
        cliente = parcial["_cliente"]
        data_iso = parcial["_data_iso"]
        timestamp_display = parcial["_timestamp"]
        ts_epoch = parcial["_ts_epoch"]

        # Detecta cadoc quando vazio (threads Risk Driver, FogBugz, respostas automáticas)
        _cadoc_raw = thread.get("cadoc") or ""
        if not _cadoc_raw:
            _assunto_th = (thread.get("assunto") or "").lower()
            _emails_orig_th = set()
            for _m in mensagens:
                _em = ((_m.get("contato_origem") or {}).get("email") or "").lower()
                if _em:
                    _emails_orig_th.add(_em)
            if any(
                "fogbugz" in _em or ("do-not-reply" in _em and "finaud" in _em)
                for _em in _emails_orig_th
            ):
                _cadoc_raw = "INTERNO"  # e-mails gerados pelo sistema FogBugz
            elif any("riskdriver@" in _em for _em in _emails_orig_th):
                _cadoc_raw = "INTERNO"  # alertas e relatórios automáticos do Risk Driver
            elif "contato@finaud.com.br" in _emails_orig_th and (
                "leiaute" in _assunto_th or "layout" in _assunto_th or "atualiza" in _assunto_th
            ):
                _cadoc_raw = "INTERNO"  # notificações de leiautes BACEN geradas internamente
            elif "resposta autom" in _assunto_th and "risk driver" in _assunto_th:
                _cadoc_raw = "INTERNO"  # respostas automáticas do Risk Driver
            elif "risk driver" in _assunto_th or "risco driver" in _assunto_th:
                _cadoc_raw = "SUPORTE"
            # Grupo 6 (externos sem cadoc) e demais: preservar vazio — revisão pendente

        # Propagar cadoc detectado para eventos que ainda estão com cadoc vazio
        if _cadoc_raw:
            for _m in mensagens_formatadas:
                if not (_m.get("cadoc") or "").strip():
                    _m["cadoc"] = _cadoc_raw

        # Monta a thread completa
        thread_formatada = {
            "threadId": thread.get("threadId"),
            "assunto": thread.get("assunto"),
            "cliente": cliente,
            "empresa": _resolver_empresa({"assunto": thread.get("assunto", ""), "mensagens": mensagens_formatadas}),
            "responsavel": thread.get("responsavel"),
            "responsabilidade": thread.get("pendencia", ""),  # FINAUD ou CLIENTE
            "lado_responsavel": thread.get("pendencia", ""),  # Alias
            "cadoc": _cadoc_raw or "SUPORTE",
            "secao_operacional": _cadoc_raw or "SUPORTE",
            "retorno_bacen": bool(thread.get("retorno_bacen", False)),  # Tipificação: comunicações BC
            # Sempre igual a len(mensagens) efetivamente gravadas (dedup por id/fingerprint)
            "qtd_mensagens": len(mensagens_formatadas),
            "data_iso": data_iso,
            "data_ultima_msg": timestamp_display,
            "timestamp": timestamp_display,
            "timestamp_epoch": ts_epoch,
            "status_processo": "SEM_TRIAGEM",
            "lista_prazos": _filtrar_prazos_regra_negocio(
                thread.get("prazos", []), thread.get("cadoc", ""), thread.get("assunto", "")
            ),
            "mensagens": mensagens_formatadas,
            "conversa_unificada": thread.get("conversa_unificada", ""),
            # Campos extras para compatibilidade com eventos individuais
            "titulo": thread.get("assunto"),
            "link": ""  # Pode ser preenchido futuramente
        }
        
        # PF42: recalcula responsavel a partir da última mensagem (mesma lógica da tela).
        # O JSON é a fonte de verdade — a tela apenas lê este campo.
        thread_formatada["responsavel"] = _responsavel_pela_acao(
            mensagens_formatadas,
            thread_formatada.get("responsavel") or "Suporte Finaud",
        )

        threads_formatadas.append(thread_formatada)

    # Ordena threads por data da última mensagem (mais recente primeiro)
    threads_formatadas.sort(key=lambda x: x.get("timestamp_epoch", 0), reverse=True)

    if _erros_timeout:
        print(f"[AVISO] {_erros_timeout} thread(s) puladas por timeout ({_timeout_thread}s). "
              f"Verifique ORACULO_VERBOSE=1 para identificar quais.", flush=True)

    return threads_formatadas


# ----------------------------------------------------------------------------
# Verificação de "Ressurreição" (threads concluídas que reabriram)
# ----------------------------------------------------------------------------

def _carregar_threads_concluidas() -> List[Dict[str, Any]]:
    """Lê a lista unificada (auto + manual) de concluídas — ver paths.py."""
    try:
        return load_concluidas()
    except Exception:
        return []


def _salvar_threads_concluidas(lista: List[Dict[str, Any]]) -> None:
    """Grava concluídas separando auto/manual por ``origem_triagem_auto``."""
    save_concluidas(lista)


def _aplicar_verificacao_ressurreicao(threads_formatadas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Verificação de Ressurreição — modo não-destrutivo:
    - Carrega threads_concluidas.json.
    - Para cada thread: se threadId está nos concluídos e chegaram mais mensagens, marca
      ``ressuscitada=True`` como indicador visual (badge) mas **NÃO remove da lista de
      concluídas** — o status Concluído permanece intacto até o utilizador apagar a carga
      e re-subir. Isso evita que a chegada de qualquer e-mail novo reverta o status para
      PENDENTE sem acção explícita do utilizador.
    - threads sem entrada nos concluídos: incluídas normalmente para o site.
    """
    concluidas = _carregar_threads_concluidas()
    por_thread_id: Dict[str, Dict[str, Any]] = {}
    for reg in concluidas:
        if not isinstance(reg, dict):
            continue
        tid = reg.get("threadId")
        if tid and tid not in por_thread_id:
            por_thread_id[tid] = reg

    threads_para_saida: List[Dict[str, Any]] = []
    tids_ressuscitadas: set = set()  # #PF32: IDs das threads removidas de concluídas

    for thread in threads_formatadas:
        tid = thread.get("threadId")
        if not tid:
            threads_para_saida.append(thread)
            continue
        reg = por_thread_id.get(tid)
        if reg is None:
            threads_para_saida.append(thread)
            continue
        qtd_fechamento = reg.get("qtd_mensagens_no_fechamento", 0)
        qtd_atual = thread.get("qtd_mensagens", 0)
        t_copy = dict(thread)
        if qtd_atual > qtd_fechamento:
            # #PF32 CORREÇÃO: mensagem nova após conclusão → remove das concluídas e
            # marca para reprocessamento pelo motor (script 11) na próxima carga.
            # Antes desta correção: badge visual apenas, thread permanecia concluída.
            t_copy["ressuscitada"] = True
            tids_ressuscitadas.add(tid)
        else:
            t_copy["thread_concluida_sem_nova_msg"] = True
        threads_para_saida.append(t_copy)

    # #PF32: Salva concluídas sem as threads ressuscitadas — script 11 as reprocessará
    if tids_ressuscitadas:
        concluidas_atualizadas = [r for r in concluidas if r.get("threadId") not in tids_ressuscitadas]
        _salvar_threads_concluidas(concluidas_atualizadas)
        print(f"[#PF32] {len(tids_ressuscitadas)} thread(s) ressuscitada(s) removida(s) de concluídas → aguardando reprocessamento pelo motor")

    return threads_para_saida


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> None:
    """Orquestra o integrador: carrega 02, processa eventos e threads, aplica ressurreição de concluídas e grava 03_integrador_dados_site.json (e backup)."""
    from pipeline_watchdog import iniciar_watchdog
    iniciar_watchdog(max_horas=2, nome_script="09_integrar")

    verificar_dependencias("09_integrar", requer=["05_classificar", "08_coletar_fog"])
    relogio_09 = Cronometro()
    cabecalho(9, "Integrar Dados Painel", periodo=os.environ.get("DATA_COLETA_INICIO", "--"))
    
    # Backup do arquivo existente (opcional se sem permissão)
    if os.path.exists(ARQUIVO_SAIDA):
        try:
            shutil.copy2(ARQUIVO_SAIDA, ARQUIVO_BACKUP)
            print(f"[OK] Backup criado: {ARQUIVO_BACKUP}")
        except OSError:
            print(f"[AVISO] Backup nao criado (permissao?): {ARQUIVO_BACKUP}")
    
    # Mapa id → anexos_detectados do JSON 01 (para propagar para mensagens no JSON 03)
    _anexos_por_id: dict = {}
    if os.path.isfile(F_EMAILS_BRUTOS):
        try:
            with open(F_EMAILS_BRUTOS, encoding="utf-8") as _f01:
                for _e01 in json.load(_f01):
                    _eid = str(_e01.get("id") or "")
                    if _eid and _e01.get("anexos_detectados"):
                        _anexos_por_id[_eid] = [
                            {
                                "nome": (a.get("nome_original") or a.get("arquivo_disco") or "").lower(),
                                "arquivo_disco": a.get("arquivo_disco", ""),
                                "content_id": a.get("content_id", ""),
                            }
                            for a in _e01["anexos_detectados"]
                            if isinstance(a, dict) and (a.get("nome_original") or a.get("arquivo_disco"))
                        ]
            print(f"[OK] Mapa de anexos carregado: {len(_anexos_por_id)} emails com anexo(s)")
        except Exception as _e_anx:
            print(f"[AVISO] Nao foi possivel carregar anexos do JSON 01: {_e_anx}")

    payload = _carregar_entrada()
    print(f"[OK] JSON carregado: {ARQUIVO_ENTRADA_PREFERIDO if os.path.exists(ARQUIVO_ENTRADA_PREFERIDO) else ARQUIVO_ENTRADA_FALLBACK}")
    
    # ========================================================================
    # PROCESSAMENTO DE EVENTOS INDIVIDUAIS (compatibilidade retroativa)
    # ========================================================================
    
    emails = _normalizar_lista_emails(payload)
    eventos: List[Dict[str, Any]] = []

    _t0_09 = time.time()
    _total_09 = len(emails)
    _intv_09 = max(1, _total_09 // 20)

    for _idx_09, e in enumerate(emails):
        if _idx_09 > 0 and _idx_09 % _intv_09 == 0:
            _el_09 = time.time() - _t0_09
            _eta_09 = int((_el_09 / _idx_09) * (_total_09 - _idx_09))
            print(f"[09] progresso: {_idx_09}/{_total_09} emails | ~{_eta_09//60}m{_eta_09%60:02d}s", flush=True)
        # Campos do 01_b novo
        assunto = e.get("assunto") or e.get("titulo") or ""
        cadoc = e.get("cadoc") or e.get("analise", {}).get("cadoc") or "SUPORTE"
        cliente = "Finaud" if cadoc == "INTERNO" else (e.get("cliente") or "DESCONHECIDO")
        responsavel = e.get("responsavel") or ""

        data_iso, timestamp_display, ts_epoch = _parse_data_br(e.get("data_email", ""))

        # Prazos (padroniza para o campo que o HTML espera)
        prazos = e.get("prazos") or e.get("lista_prazos") or e.get("analise", {}).get("lista_prazos") or []
        lista_prazos = _injetar_cadoc_em_prazos(prazos, cadoc)
        lista_prazos = _filtrar_prazos_regra_negocio(lista_prazos, cadoc, assunto)

        responsabilidade = _responsabilidade_por_lado(e)
        
        corpo_raw, corpo_limpo = _corpo_evento_a_partir_classificador(e, _anexos_por_id)

        evento = {
            "id": e.get("id"),
            "threadId": e.get("threadId"),
            "titulo": assunto,
            "cliente": cliente,
            "empresa": _resolver_empresa(e),
            "responsavel": responsavel,
            "responsabilidade": responsabilidade,   # coluna 'Pendência' (FINAUD/CLIENTE)
            "lado_responsavel": responsabilidade,   # alias (caso você use em outro ponto)
            "secao_operacional": cadoc,             # filtro por tipo/cadoc
            "cadoc": cadoc,
            "data_iso": data_iso,
            "timestamp": timestamp_display,
            "timestamp_epoch": ts_epoch,
            "status_processo": _calcular_status({"lista_prazos": lista_prazos}),
            "lista_prazos": lista_prazos,
            "retorno_bacen": bool(e.get("retorno_bacen", False)),  # Tipificação: comunicações BC (indício, crítica, erro)
            "link": e.get("link", ""),  # se futuramente o coletor trouxer link do Gmail
            "texto_imagens": (e.get("texto_imagens") or "").strip(),
            # Extras úteis para o modal (histórico):
            "contato_origem": e.get("contato_origem", {}),
            "contato_destino": e.get("contato_destino", {}),
            "corpo": corpo_raw,  # Original para referência
            "corpo_limpo": corpo_limpo,  # ✨ AGORA LIMPO!
        }

        eventos.append(evento)

    # Ordena por data (mais recente primeiro)
    eventos.sort(key=lambda x: x.get("timestamp_epoch", 0), reverse=True)
    
    sem_triagem = sum(1 for e in eventos if e.get("status_processo") == "SEM_TRIAGEM")
    filtrados   = sum(1 for e in eventos if e.get("cadoc") in ("FILTRADO_POR_DATA", "IGNORADO"))
    print(f"[OK] {len(eventos)} eventos processados: {sem_triagem} aguardando triagem | {filtrados} filtrados")
    
    # ========================================================================
    # NOVO: PROCESSAMENTO DE THREADS
    # ========================================================================
    
    threads_processadas_raw = payload.get("threads_processadas", []) if isinstance(payload, dict) else []
    threads_formatadas = []
    
    if threads_processadas_raw:
        threads_formatadas = _processar_threads(threads_processadas_raw, _anexos_por_id)
        n_msgs   = sum(t.get("qtd_mensagens", 0) for t in threads_formatadas)
        n_rb     = sum(1 for t in threads_formatadas if t.get("retorno_bacen"))
        n_multip = sum(1 for t in threads_formatadas if t.get("qtd_mensagens", 0) > 1)
        print(f"[OK] {len(threads_formatadas)} threads | {n_msgs} mensagens | {n_multip} com 2+ msgs | {n_rb} retorno_bacen")
    else:
        print(f"[AVISO] Nenhuma thread encontrada no JSON de entrada")
        print(f"   Campo 'threads_processadas' esta vazio ou ausente")

    sem_preservar_ti = os.environ.get("INTEGRADOR_08_SEM_PRESERVAR_TEXTO_IMAGENS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    mapa_prev_03: Dict[str, str] = {}
    if not sem_preservar_ti and os.path.isfile(ARQUIVO_BACKUP):
        try:
            with open(ARQUIVO_BACKUP, encoding="utf-8") as _bf:
                _prev = json.load(_bf)
            mapa_prev_03 = _mapa_texto_imagens_desde_03_dict(_prev if isinstance(_prev, dict) else {})
        except Exception as e_bkp_ti:
            print(f"[AVISO] Nao foi possivel carregar backup do OCR ({e_bkp_ti}). Textos de imagens do 03 anterior nao serao repostos.")
            mapa_prev_03 = {}
    combinado_ti: Dict[str, str] = {}
    if not sem_preservar_ti:
        combinado_ti = merge_por_id_longest(load_por_id(), mapa_prev_03)
    if threads_formatadas and combinado_ti:
        n_ti = restaurar_threads_se_vazio(threads_formatadas, combinado_ti)
        if n_ti:
            print(f"[OK] texto_imagens: {n_ti} mensagem(ns) reposta(s) (cache + 03 anterior)")

    # Verificação de Ressurreição: concluídas com mais mensagens voltam ao painel;
    # concluídas com mesma qtd não entram no JSON do site
    threads_para_site = _aplicar_verificacao_ressurreicao(threads_formatadas)
    n_marcadas = sum(1 for t in threads_para_site if t.get("thread_concluida_sem_nova_msg"))
    if n_marcadas:
        print(f"[OK] Ressurreicao: {n_marcadas} thread(s) concluida(s) sem nova msg mantida(s) no JSON (modal /api/threads)")

    # Alinhar threadId dos eventos ao threadId da thread que contém a mensagem do evento,
    # para que a API (mapa_threads[tid]) encontre as mensagens no modal.
    msg_id_para_thread_id: Dict[str, str] = {}
    chave_assunto_cliente_para_tid: Dict[Tuple[str, str], str] = {}
    for t in threads_para_site:
        tid = t.get("threadId")
        if not tid:
            continue
        for msg in (t.get("mensagens") or []):
            mid = msg.get("id") or msg.get("message_id")
            if mid is not None:
                msg_id_para_thread_id[str(mid)] = tid
        assunto = (t.get("assunto") or t.get("titulo") or "").strip().lower()[:100]
        cliente = (t.get("cliente") or "").strip()
        if assunto and cliente:
            chave_assunto_cliente_para_tid[(assunto, cliente)] = tid
    for ev in eventos:
        eid = ev.get("id")
        if eid is not None and str(eid) in msg_id_para_thread_id:
            ev["threadId"] = msg_id_para_thread_id[str(eid)]
        else:
            # Fallback: evento pode ter id diferente (ex.: duplicata); associa por assunto+cliente
            assunto_ev = (ev.get("titulo") or ev.get("assunto") or "").strip().lower()[:100]
            cliente_ev = (ev.get("cliente") or "").strip()
            if assunto_ev and cliente_ev and (assunto_ev, cliente_ev) in chave_assunto_cliente_para_tid:
                ev["threadId"] = chave_assunto_cliente_para_tid[(assunto_ev, cliente_ev)]

    if combinado_ti:
        for ev in eventos:
            if (ev.get("texto_imagens") or "").strip():
                continue
            eid = ev.get("id")
            if eid is None:
                continue
            ti_ev = combinado_ti.get(str(eid))
            if ti_ev:
                ev["texto_imagens"] = ti_ev

    _sincronizar_texto_imagens_eventos_de_threads(eventos, threads_para_site)

    # ========================================================================
    # MONTAGEM DO JSON DE SAÍDA (RETROCOMPATÍVEL)
    # ========================================================================
    
    saida = {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(eventos),
        "total_threads": len(threads_para_site),
        "eventos": eventos,  # Mantém formato antigo (lista plana)
        "threads": threads_para_site  # Threads após verificação de Ressurreição
    }

    # Propagar cadoc da thread para eventos raiz com cadoc vazio.
    _cadoc_por_tid = {t["threadId"]: t.get("cadoc") or "" for t in saida["threads"] if t.get("threadId")}
    _propagados = 0
    for ev in saida["eventos"]:
        _cadoc_thread = _cadoc_por_tid.get(ev.get("threadId") or "")
        if not (ev.get("cadoc") or "").strip() and _cadoc_thread:
            ev["cadoc"] = _cadoc_thread
            ev["secao_operacional"] = _cadoc_thread
            _propagados += 1
    if _propagados:
        print(f"[OK] Cadoc propagado para {_propagados} evento(s) com cadoc vazio.")

    # Corrigir threads cujo cadoc difere do cadoc de todos os seus eventos
    # (ex.: thread=SUPORTE mas todos os eventos=IGNORADO — spam detectado pelo filtro de dominios)
    _evs_por_tid_saida = {}
    for ev in saida["eventos"]:
        _evs_por_tid_saida.setdefault(ev.get("threadId",""), []).append(ev.get("cadoc") or "")
    _threads_corrigidas = 0
    for t in saida["threads"]:
        tid = t.get("threadId","")
        cadocs_ev = set(_evs_por_tid_saida.get(tid, []))
        if cadocs_ev and cadocs_ev <= {"IGNORADO", "FILTRADO_POR_DATA"} and t.get("cadoc") not in ("IGNORADO","FILTRADO_POR_DATA"):
            cadoc_novo = cadocs_ev.pop()
            t["cadoc"] = cadoc_novo
            t["secao_operacional"] = cadoc_novo
            _threads_corrigidas += 1
    if _threads_corrigidas:
        print(f"[OK] Cadoc de thread corrigido para IGNORADO/FILTRADO em {_threads_corrigidas} thread(s) de spam.")

    # ── Item 29: Expandir encaminhados BACEN quando corpo_limpo está vazio ───
    # Quando o cliente encaminha um e-mail do BACEN com apenas "Segue para
    # providências", o corpo_limpo fica vazio (o limpador corta conteúdo citado).
    # Aqui extraímos o texto do Fw: do HTML bruto e injetamos em corpo_limpo.
    _PAT_BCB_HEADER = re.compile(
        r'(?:De|From)\s*:\s*[^\n<@]*@bcb\.gov\.br|'
        r'(?:dli|dlo|drm|ddr|cadoc|bacen)\s*@\s*bcb\.gov\.br',
        re.I,
    )
    _enc_expandidos = 0
    for ev in saida["eventos"]:
        corpo_limpo = (ev.get("corpo_limpo") or "").strip()
        if len(corpo_limpo) >= 80:
            continue  # já tem conteúdo suficiente
        corpo_html = ev.get("corpo") or ""
        if len(corpo_html) < 300:
            continue
        # Verificar se HTML tem cabeçalho de e-mail BCB encaminhado
        corpo_txt = re.sub(r"<[^>]+>", " ", corpo_html)
        corpo_txt = re.sub(r"&nbsp;", " ", corpo_txt)
        corpo_txt = re.sub(r"&lt;", "<", corpo_txt)
        corpo_txt = re.sub(r"&gt;", ">", corpo_txt)
        corpo_txt = re.sub(r"\s+", " ", corpo_txt).strip()
        m = _PAT_BCB_HEADER.search(corpo_txt)
        if not m:
            continue
        # Extrair a partir do cabeçalho BCB
        enc_content = corpo_txt[m.start():]
        # Cortar em assinatura ou limite razoável
        enc_content = enc_content[:1200].strip()
        if len(enc_content) > 60:
            ev["corpo_limpo"] = enc_content
            _enc_expandidos += 1
    if _enc_expandidos:
        print(f"[OK] Item 29: corpo_limpo expandido do Fw: BACEN em {_enc_expandidos} evento(s).")

    os.makedirs(PASTA_JSON, exist_ok=True)
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, indent=2, ensure_ascii=False)
    _resumo_log(processados=len(eventos), ignorados=0, tempo_s=relogio_09.elapsed)
    registrar_execucao("09_integrar", arquivo_saida=ARQUIVO_SAIDA)

    # ========================================================================
    # TESTE DE REGRESSÃO SIMPLES
    # ========================================================================
    
    print(f"\n{'='*70}")
    print("TESTE DE REGRESSAO")
    print(f"{'='*70}")
    
    # Verifica se manteve campos essenciais
    if eventos:
        primeiro_evento = eventos[0]
        campos_obrigatorios = ["id", "cadoc", "responsavel", "lista_prazos", "cliente"]
        
        for campo in campos_obrigatorios:
            if campo in primeiro_evento:
                print(f"   [OK] Campo '{campo}' presente: {primeiro_evento[campo]}")
            else:
                print(f"   [FALTA] Campo '{campo}' AUSENTE!")
        
        # ✨ Verifica a limpeza de texto
        if "corpo_limpo" in primeiro_evento:
            corpo_limpo = primeiro_evento["corpo_limpo"]
            corpo_raw = primeiro_evento.get("corpo", "")
            print(f"\n   Exemplo de limpeza:")
            print(f"   Tamanho original: {len(corpo_raw)} caracteres")
            print(f"   Tamanho limpo: {len(corpo_limpo)} caracteres")
            print(f"   Reducao: {100 - (len(corpo_limpo) * 100 / len(corpo_raw) if corpo_raw else 0):.1f}%")
    
    if threads_para_site:
        primeira_thread = threads_para_site[0]
        print(f"\n   Thread exemplo: {primeira_thread.get('threadId')}")
        print(f"   Mensagens: {primeira_thread.get('qtd_mensagens')}")
        print(f"   Responsabilidade: {primeira_thread.get('responsabilidade')}")
        print(f"   Prazos: {len(primeira_thread.get('lista_prazos', []))}")
        
        if primeira_thread.get("mensagens"):
            primeira_msg = primeira_thread["mensagens"][0]
            corpo_limpo = primeira_msg.get("corpo_limpo", "")
            print(f"\n   Previa do corpo limpo (primeiros 150 caracteres):")
            print(f"   {corpo_limpo[:150]}...")
    
    print(f"\n{'='*70}")
    print(f"CONCLUIDO!")
    print(f"{'='*70}")
    print(f"Arquivo gerado: {ARQUIVO_SAIDA}")
    print(f"Eventos individuais: {len(eventos)}")
    print(f"Threads agrupadas: {len(threads_para_site)}")
    print(f"Backup: {ARQUIVO_BACKUP}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    with iniciar_log_standalone(9, "integrar_dados_painel"):
        main()