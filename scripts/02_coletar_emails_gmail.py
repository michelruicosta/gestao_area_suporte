# -*- coding: utf-8 -*-
"""
ORÁCULO 360 - Coletor de E-mail (01)

Responsabilidade: coletar e-mails brutos do Gmail via IMAP, sem classificação.
- Extrai campos exatamente como vêm do servidor (assunto, remetente, corpo, anexos).
- NÃO faz análise de cliente/responsável, NÃO limpa HTML, NÃO aplica regras de negócio.
- E-mails com assunto "Atualização de Comunicados e Normativos": anexos em data/normativos_oficiais/.
- Demais e-mails: em data/email_anexos/ anexos relevantes (documentos + imagens).
- Imagens inline (cid): gravadas se (a) Retorno Bacen no assunto, ou (b) assunto DLO/DLI/2061/2062 e “crítica/critica” no corpo — sempre exceto RD_* no texto; logos/assinaturas filtrados por anexo_imagem_eh_essencial (nome + dimensões; nesse contexto inline ≥ ~28 KB entra mesmo com print estreito). Parte `image/*` com Content-ID (cid no HTML) conta como inline mesmo sem `Content-Disposition: inline` (evita exigir 20 KB de “anexo explícito” em forwards).
- Saída: 01_extração_dados_brutos_gmail.json (consumido pelo 02 e pelo 04).

Período: DATA_COLETA_INICIO / DATA_LIMITE_EXCLUIR (DD-MMM-YYYY). Via executar_tudo.py, o orquestrador define por env.
"""

import io
import os
import re
import json
import sys
import socket
import imaplib
import email
import time
from email.header import decode_header
from dotenv import load_dotenv
from tqdm import tqdm 
from colorama import Fore, Style, init

init(autoreset=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

try:
    from scripts.monitor_consumo_ia import registrar_consumo
except ImportError:
    def registrar_consumo(servico, qtd, unidade, custo): pass

PASTA_ANEXOS_GERAL = os.path.join(BASE_DIR, 'data', 'email_anexos')
PASTA_NORMATIVOS_OFICIAIS = os.path.join(BASE_DIR, 'data', 'normativos_oficiais')
from paths import F_EMAILS_BRUTOS, F_MAPEAMENTO, registrar_execucao, verificar_dependencias
from pipeline_log import cabecalho, resumo, Cronometro, iniciar_log_standalone
ARQUIVO_SAIDA = F_EMAILS_BRUTOS

# Extensões consideradas relevantes para o projeto (documentos de trabalho / regulatório).
# Anexos com outras extensões NÃO são gravados em email_anexos (evita lotar a pasta).
EXTENSOES_RELEVANTES_ANEXOS = frozenset(
    ".pdf .doc .docx .xls .xlsx .csv .txt .zip .odt .ods .rtf .xml".split()
)
# Imagens: gravamos as que parecem conteúdo (anexo explícito OU inline com tamanho mínimo).
# Inline: limite menor (8 KB) + dimensões mínimas (área/lados) para não gravar logo de assinatura só pelo peso em bytes.
# Anexos explícitos: 20 KB para evitar ruído.
EXTENSOES_IMAGENS = frozenset(".png .jpg .jpeg .gif .bmp .webp .tiff .tif".split())
MIN_TAMANHO_IMAGEM_BYTES = 20 * 1024  # 20 KB — anexos explícitos e imagens inline grandes (prints, telas)
MIN_TAMANHO_IMAGEM_INLINE_BYTES = 8 * 1024  # 8 KB — inline: além disso, dimensões mínimas (evita logo de assinatura só pelo tamanho do ficheiro)
# Nomes que indicam assinatura/logo — inline com esses termos não são gravados
IMAGEM_INLINE_EXCLUIR_NOME = frozenset(
    "assinatura signature logo logotipo favicon icon sign".split()
)
# Imagens inline < 5 KB: só incluir se formato paisagem (tabela/relatório); logo/ícone costuma ser quadrado
MIN_TAMANHO_IMAGEM_INLINE_CONTEUDO_BYTES = 3 * 1024  # 3 KB — zona cinza para formato paisagem

ARQUIVO_REGRAS_NEGOCIO = F_MAPEAMENTO
_TIP_RETORNO_BACEN_CACHE = None


def _get_tipificacao_retorno_bacen():
    """Carrega TIPIFICACAO_RETORNO_BACEN (mesma fonte do classificador 04)."""
    global _TIP_RETORNO_BACEN_CACHE
    if _TIP_RETORNO_BACEN_CACHE is not None:
        return _TIP_RETORNO_BACEN_CACHE
    try:
        with open(ARQUIVO_REGRAS_NEGOCIO, "r", encoding="utf-8") as f:
            data = json.load(f)
        oque = data.get("O_QUE_ESTA_SENDO_ANALISADO") or data
        _TIP_RETORNO_BACEN_CACHE = oque.get("TIPIFICACAO_RETORNO_BACEN") or {}
    except Exception:
        _TIP_RETORNO_BACEN_CACHE = {}
    return _TIP_RETORNO_BACEN_CACHE


def assunto_indica_retorno_bacen(subject: str) -> bool:
    """Espelha ValidadorContextual.eh_retorno_bacen (04): termos_assunto no assunto."""
    if not subject:
        return False
    cfg = _get_tipificacao_retorno_bacen()
    al = subject.lower().strip()
    termos = cfg.get("termos_assunto") or []
    return any(t in al for t in termos)


def corpus_tem_indicador_rd_ddr(texto: str) -> bool:
    """Alinhado ao 04: RD_MOEDA / RD_* no texto → não tratar como Retorno Bacen (ex.: imagem inline)."""
    if not texto:
        return False
    return bool(re.search(r"\bRD_[A-Z0-9]{2,}\b", texto.upper()))


def corpus_indica_critica_em_relatorio_dlo(subject: str, corpus: str, corpo_texto_vazio: bool = False) -> bool:
    """
    Cliente menciona crítica em fio DLO/DLI (ex.: print da tela do BC no corpo) sem assunto tipo Retorno Bacen.
    Permite gravar imagens inline para teste/operação — ainda exige anexo_imagem_eh_essencial (sem logo).

    Inclui «inconsistência/inconsistencias» (ex.: «Informe 2061 voltou… com inconsistências») e
    «indício de qualidade» — mesmo sem a palavra «crítica», são telas/indicadores do portal BC.

    corpo_texto_vazio=True: cliente enviou só a imagem, sem texto escrito — assunto CADOC basta para
    autorizar a gravação (a imagem inline é o próprio conteúdo da mensagem).
    """
    if not subject:
        return False
    sl = subject.lower()
    if not any(x in sl for x in ("dlo", "dli", "2061", "2062")):
        return False
    if corpo_texto_vazio:
        return True
    if not corpus:
        return False
    cl = corpus.lower()
    tem_sinal_bc = (
        ("critica" in cl)
        or ("crítica" in cl)
        or ("inconsist" in cl)
        or ("indicio" in cl)
        or ("indício" in cl)
        or ("problema de qualidade" in cl)
    )
    return tem_sinal_bc


# Período: use ao rodar sozinho; ao rodar via executar_tudo.py, o orquestrador define por env.
# Formato DD-MMM-YYYY (IMAP exige mês em inglês - RFC 3501).
DATA_COLETA_INICIO = os.environ.get("DATA_COLETA_INICIO", "21-Jan-2026")
DATA_LIMITE_EXCLUIR = os.environ.get("DATA_LIMITE_EXCLUIR", "01-Feb-2026")

EMAIL_USER = os.getenv('GMAIL_USER')
EMAIL_PASS = os.getenv('GMAIL_APP_PASS')

def conectar_imap():
    """Conecta ao Gmail via IMAP4_SSL usando credenciais do .env (GMAIL_USER, GMAIL_APP_PASS). Retorna o objeto mail ou None."""
    try:
        socket.setdefaulttimeout(60)  # timeout global de 60s para operações IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)
        return mail
    except Exception as e:
        err_msg = str(e).lower()
        if "11001" in err_msg or "getaddrinfo" in err_msg or "name or service not known" in err_msg:
            print(f"{Fore.RED}[X] Erro de rede/DNS: não foi possível resolver 'imap.gmail.com'. Verifique: internet, firewall, proxy, DNS.")
        else:
            print(f"{Fore.RED}[X] Erro: {e}")
        return None

def anexo_eh_relevante(filename):
    """True se o anexo for de tipo relevante para o projeto (documentos)."""
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in EXTENSOES_RELEVANTES_ANEXOS


def parte_imagem_inline_semantica(part) -> bool:
    """
    True se a parte for image/* referenciável no HTML como cid (inline semântico).
    Alguns clientes (ex.: encaminhamentos) não enviam Content-Disposition: inline;
    só Content-ID — sem isso, anexo_imagem_eh_essencial caía na regra de anexo
    explícito (>= 20 KB) e prints menores eram descartados.
    """
    ct = (part.get_content_type() or "").lower()
    if not ct.startswith("image/"):
        return False
    disp = (part.get("Content-Disposition") or "").lower()
    if "attachment" in disp:
        return False
    if "inline" in disp:
        return True
    cid = part.get("Content-ID") or part.get("Content-Id")
    return bool(cid and str(cid).strip())


def _imagem_eh_formato_paisagem(payload_bytes):
    """
    True se a imagem for paisagem (largura >= 1.4 * altura).
    Tabelas, relatórios e indicadores costumam ser paisagem; logos/ícones costumam ser quadrados ou retrato.
    Retorna False se não for possível ler dimensões (sem PIL ou erro).
    """
    if not payload_bytes or len(payload_bytes) < 100:
        return False
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(payload_bytes))
        w, h = img.size
        img.close()
        if h <= 0:
            return False
        return w >= 1.4 * h
    except Exception:
        return False


def _imagem_inline_dimensoes_sugerem_conteudo(payload_bytes):
    """
    Inline >= 8 KB antes era aceite só pelo tamanho em bytes — logos de assinatura (ex.: Banvox image004.png)
    passavam. Exige área ou lados mínimos típicos de print/tela, não faixa de logo (~400×80 px).
    Retorna True se não for possível ler dimensões (mantém inclusão conservadora).
    """
    if not payload_bytes or len(payload_bytes) < 100:
        return False
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(payload_bytes))
        w, h = img.size
        img.close()
        if w <= 0 or h <= 0:
            return True
        area = w * h
        mx = max(w, h)
        mn = min(w, h)
        # Print/tabela: área razoável ou pelo menos um lado “de tela”
        if area >= 90_000:
            return True
        if mx >= 420:
            return True
        if mn >= 280:
            return True
        # Capturas de indício/crítica CRD frequentemente ~300–400 px de largura e baixa altura
        # (ex. 342×137); antes eram descartadas e só restava OCR de logo no .ocr.txt.
        if area >= 40_000 and mx >= 300:
            return True
        return False
    except Exception:
        return True


def anexo_imagem_eh_essencial(part, payload_bytes, filename, contexto_rb_ou_critica_dlo=False):
    """
    True se a imagem parecer conteúdo útil (gráfico, tabela, screenshot), não assinatura/logo.
    Critérios:
    - Anexo explícito: >= 20 KB.
    - Inline: (1) nome não pode conter assinatura/logo; (2) tamanho:
      - >= 8 KB → incluir só se dimensões sugerirem conteúdo (não logo de assinatura);
        Em contexto Retorno Bacen / crítica DLO+206x: imagens inline >= ~28 KB entram mesmo com
        dimensões modestas (prints estreitos do portal BC).
      - (3–8 KB) e formato paisagem (largura >= 1.4×altura) → incluir (tabela/relatório);
      - < 3 KB ou (3–8 KB e quadrado/retrato) → excluir (logo/ícone).
    """
    if not filename or not payload_bytes:
        return False
    ext = os.path.splitext(filename)[1].lower()
    if ext not in EXTENSOES_IMAGENS:
        return False
    eh_inline = parte_imagem_inline_semantica(part)
    size = len(payload_bytes)
    if eh_inline:
        # Inline: excluir se o nome sugerir assinatura/logo
        nome_lower = filename.lower()
        if any(termo in nome_lower for termo in IMAGEM_INLINE_EXCLUIR_NOME):
            return False
        if size >= MIN_TAMANHO_IMAGEM_INLINE_BYTES:
            if contexto_rb_ou_critica_dlo and size >= 28 * 1024:
                return True
            return _imagem_inline_dimensoes_sugerem_conteudo(payload_bytes)
        # Zona cinza (3–8 KB): só incluir se formato paisagem (tabela/indicadores)
        if size >= MIN_TAMANHO_IMAGEM_INLINE_CONTEUDO_BYTES and _imagem_eh_formato_paisagem(payload_bytes):
            return True
        return False
    # Anexo explícito
    return size >= MIN_TAMANHO_IMAGEM_BYTES


def walk_sem_embutidos(msg, dentro_de_rfc822=False):
    """
    Percorre as partes do MIME. Quando a parte é message/rfc822 (mensagem citada/embutida),
    recursa com dentro_de_rfc822=True para que anexos de lá não sejam atribuídos a esta mensagem.
    Gera (part, dentro_de_rfc822) para cada parte folha ou multipart (não gera para message/rfc822 em si).
    """
    if msg.get_content_type() == "message/rfc822":
        payload = msg.get_payload()
        if isinstance(payload, list):
            for sub in payload:
                yield from walk_sem_embutidos(sub, dentro_de_rfc822=True)
        return
    if not msg.is_multipart():
        yield msg, dentro_de_rfc822
        return
    for part in msg.get_payload():
        if part is None:
            continue
        yield from walk_sem_embutidos(part, dentro_de_rfc822)


def _nome_imagem_de_content_id(part, content_type):
    """
    Para imagens inline sem filename: usa Content-ID para gerar nome.
    Suporta: (1) Outlook/Word: image001.png@01DCA4B3.E48D9EE0 → image001.png;
             (2) UUID: 4545544a-3707-4700-90e4-e81d634143b6 → image_4545544a.png.
    Retorna None se não for imagem ou não houver Content-ID.
    """
    if not (content_type or "").startswith("image/"):
        return None
    cid = part.get("Content-ID") or part.get("Content-Id")
    if not cid:
        return None
    cid = cid.strip().strip("<>")
    if not cid:
        return None
    # Formato Outlook/Word: "image001.png@01DCA4B3.E48D9EE0" — usa a parte antes do @
    if "@" in cid:
        parte_antes = cid.split("@", 1)[0].strip()
        if parte_antes and "." in parte_antes:
            ext_ok = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif")
            if parte_antes.lower().endswith(ext_ok):
                return parte_antes
    # Formato UUID: usa primeiros 8 chars para nome curto
    base = cid.replace("-", "")[:8] if cid else "img"
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/gif": ".gif", "image/bmp": ".bmp", "image/webp": ".webp"}
    ext = ext_map.get((content_type or "").lower(), ".png")
    return f"image_{base}{ext}"


def limpar_nome_arquivo(nome):
    """Decodifica cabeçalho do anexo (encode) e remove caracteres proibidos no sistema de arquivos. Retorna nome seguro (máx. 120 chars)."""
    if not nome: return "sem_nome"
    try:
        partes = decode_header(nome)
        nome_decodificado = ""
        for conteudo, codificacao in partes:
            if isinstance(conteudo, bytes):
                nome_decodificado += conteudo.decode(codificacao or "utf-8", errors="replace")
            else:
                nome_decodificado += str(conteudo)
        nome = nome_decodificado
    except Exception:
        pass
    nome = nome.replace('\r', '').replace('\n', '').strip()
    proibidos = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '=', '%', '$', '#', '\t']
    for char in proibidos:
        nome = nome.replace(char, '_')
    return nome[:120]

def salvar_checkpoint(dados, silencioso=False):
    """Persiste a lista de e-mails em 01_extração_dados_brutos_gmail.json. Se silencioso=True, não imprime mensagem."""
    try:
        os.makedirs(os.path.dirname(ARQUIVO_SAIDA), exist_ok=True)
        with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        if not silencioso:
            tqdm.write(f"{Fore.CYAN}[*] Checkpoint: {len(dados)} registros.")
    except Exception as e:
        tqdm.write(f"{Fore.RED}[!] Erro: {e}")

def coletar_emails():
    """Função principal: conecta ao Gmail, busca e-mails no período (SINCE/BEFORE), baixa corpo e anexos e grava em ARQUIVO_SAIDA."""
    from pipeline_watchdog import iniciar_watchdog
    iniciar_watchdog(max_horas=3, nome_script="02_coletar")
    verificar_dependencias("02_coletar_emails", requer=["01_feriados"])
    relogio = Cronometro()
    cabecalho(2, "Coletar E-mails Gmail", periodo=DATA_COLETA_INICIO)

    tentativas_maximas = 3
    intervalo_retry = 15
    total_requisicoes = 0

    for tentativa in range(tentativas_maximas):
        try:
            os.makedirs(PASTA_ANEXOS_GERAL, exist_ok=True)
            mail = conectar_imap()
            if not mail:
                time.sleep(intervalo_retry)
                continue

            atividades = []
            mapa_existentes = {}
            if os.path.exists(ARQUIVO_SAIDA):
                try:
                    with open(ARQUIVO_SAIDA, 'r', encoding='utf-8') as f:
                        atividades = json.load(f)
                        mapa_existentes = {item['id']: item for item in atividades}
                    print(f"{Fore.BLUE}[i] {len(atividades)} registros existentes.")
                except (json.JSONDecodeError, OSError) as e_load:
                    # Guarda cópia do arquivo corrompido antes de sobrescrever (#62)
                    _ts_corr = datetime.now().strftime("%Y%m%d_%H%M")
                    _bkp_corr = ARQUIVO_SAIDA + f".backup_corrompido_{_ts_corr}"
                    try:
                        import shutil as _shutil
                        _shutil.copy2(ARQUIVO_SAIDA, _bkp_corr)
                        print(f"{Fore.RED}[!] ATENCAO: JSON corrompido — backup salvo em {os.path.basename(_bkp_corr)}")
                    except Exception:
                        pass
                    print(f"{Fore.RED}[!] Erro ao ler arquivo existente ({e_load}). Iniciando coleta do zero.")
                    atividades = []

            mail.select('"[Gmail]/Todos os e-mails"')
            # Sempre solicita X-GM-THRID para agrupar igual ao Gmail (1 msg = 1, 10 = 10).
            # Qualquer e-mail com @finaud.com.br em FROM ou TO entra (andrea, suporte, etc.), respeitando período.
            criterio_busca = f'(OR (FROM "@finaud.com.br") (TO "@finaud.com.br") SINCE "{DATA_COLETA_INICIO}" BEFORE "{DATA_LIMITE_EXCLUIR}")'
            status, messages = mail.search(None, criterio_busca)
            
            email_ids = messages[0].split()
            fila_download = [e_id for e_id in email_ids if e_id.decode() not in mapa_existentes]
            
            if not fila_download:
                print(f"{Fore.GREEN}[OK] Sincronizacao completa.")
                mail.logout()
                break

            print(f"{Fore.YELLOW}[>>] Coletando {len(fila_download)} emails...")
            
            _total_02 = len(fila_download)
            _idx_02 = 0
            with tqdm(total=len(email_ids), initial=len(atividades), desc="Progresso", unit="eml", colour="cyan") as pbar:
                for e_id in fila_download:
                    _idx_02 += 1
                    m_id = e_id.decode()
                    _eta_02 = relogio.eta(_idx_02, _total_02)
                    _eta_str = f"~{_eta_02//60}m{_eta_02%60:02d}s" if _eta_02 is not None else "..."
                    print(f"[02] progresso: {_idx_02}/{_total_02} emails | {_eta_str}", flush=True)
                    try:
                        fetch_attrs = "(INTERNALDATE RFC822 X-GM-THRID)"  # INTERNALDATE = fallback quando Date: header vazio
                        res, msg_data = mail.fetch(e_id, fetch_attrs)
                        total_requisicoes += 1
                        
                        if not msg_data or msg_data[0] is None:
                            pbar.update(1)
                            continue
                        
                        x_gm_thrid = None
                        internaldate_raw = None
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                # Extrai X-GM-THRID e INTERNALDATE da resposta
                                # Ex.: b'1 (INTERNALDATE "13-Feb-2026 14:48:31 +0000" X-GM-THRID 1278... RFC822 ...'
                                part0 = response_part[0]
                                if isinstance(part0, bytes):
                                    part0 = part0.decode(errors='replace')
                                m_thrid = re.search(r'X-GM-THRID\s+(\d+)', part0)
                                if m_thrid:
                                    x_gm_thrid = f"GMTHRID_{m_thrid.group(1)}"
                                m_idate = re.search(r'INTERNALDATE\s+"([^"]+)"', part0)
                                if m_idate:
                                    internaldate_raw = m_idate.group(1)
                                if not response_part[1]:
                                    continue
                                    
                                msg = email.message_from_bytes(response_part[1])
                                
                                # Decodifica assunto
                                subject_raw = msg.get("Subject", "Sem Assunto")
                                try:
                                    decoded_subject = decode_header(subject_raw)[0]
                                    subject, encoding = decoded_subject
                                    if isinstance(subject, bytes): 
                                        subject = subject.decode(encoding or "utf-8", errors="replace")
                                except Exception:
                                    subject = "Assunto Corrompido"
                                
                                # Campos brutos - SEM PROCESSAMENTO
                                sender = msg.get("From")
                                reply_to = msg.get("Reply-To")
                                destinatarios = msg.get("To")
                                copia_cc = msg.get("Cc")
                                date_raw = msg.get("Date") or internaldate_raw

                                message_id = msg.get("Message-ID")          # (não chame isso de thread)
                                in_reply_to = msg.get("In-Reply-To")
                                references_raw = msg.get("References")
                                references = re.findall(r"<[^>]+>", references_raw) if references_raw else []
                                # Prioridade: X-GM-THRID (Gmail) > References > In-Reply-To > message_id
                                thread_root = (x_gm_thrid if x_gm_thrid else
                                               references[0] if references else (in_reply_to or message_id))

                                corpo_html = ""
                                corpo_texto = ""
                                anexos = []

                                # Extrai corpo (HTML e texto) e anexos. Documentos dentro de message/rfc822
                                # são ignorados (evita duplicar PDF da mensagem citada); imagens lá dentro
                                # seguem com o mesmo m_id (prints no forward, ex.: Erro DLO).
                                # Imagens inline/cid: só em data/email_anexos se Retorno Bacen (JSON) ou DLO+crítica; sem RD_* no texto.
                                if msg.is_multipart():
                                    parts_list = list(walk_sem_embutidos(msg))
                                    for part, _dentro in parts_list:
                                        content_type = part.get_content_type()
                                        payload_bytes = part.get_payload(decode=True)
                                        if payload_bytes is None:
                                            payload_bytes = b''
                                        if content_type == "text/html":
                                            corpo_html += payload_bytes.decode(part.get_content_charset() or 'utf-8', errors='replace')
                                        elif content_type == "text/plain":
                                            corpo_texto += payload_bytes.decode(part.get_content_charset() or 'utf-8', errors='replace')

                                    corpus_para_rb = f"{subject or ''}\n{corpo_texto}\n{corpo_html}"
                                    sem_rd = not corpus_tem_indicador_rd_ddr(corpus_para_rb)
                                    _corpo_texto_vazio = len(corpo_texto.strip()) < 50
                                    permitir_imagem_inline_corpo = sem_rd and (
                                        assunto_indica_retorno_bacen(subject)
                                        or corpus_indica_critica_em_relatorio_dlo(subject, corpus_para_rb, corpo_texto_vazio=_corpo_texto_vazio)
                                    )

                                    for part, dentro_citacao in parts_list:
                                        content_type = part.get_content_type()
                                        filename = part.get_filename()
                                        payload_bytes = part.get_payload(decode=True)
                                        if payload_bytes is None:
                                            payload_bytes = b''
                                        # Anexos: mensagem principal sempre; encaminhados (rfc822) só imagens (prints de erro etc.)
                                        if not filename and (content_type or "").startswith("image/"):
                                            filename = _nome_imagem_de_content_id(part, content_type)
                                        # dentro_citacao: pular documentos (evita duplicata); manter imagens (ex.: crítica DLO de Thaiana)
                                        pular_por_citacao = dentro_citacao and not (content_type or "").startswith("image/")
                                        if filename and not pular_por_citacao:
                                            nome_limpo = limpar_nome_arquivo(filename)
                                            nome_final = f"{m_id}_{nome_limpo}"
                                            subject_lower = (subject or "").lower()
                                            if "atualiz" in subject_lower and "comunicados" in subject_lower:
                                                os.makedirs(PASTA_NORMATIVOS_OFICIAIS, exist_ok=True)
                                                caminho_completo = os.path.join(PASTA_NORMATIVOS_OFICIAIS, nome_final)
                                                gravar_anexo = True
                                            else:
                                                ext = os.path.splitext(filename)[1].lower()
                                                eh_inline = parte_imagem_inline_semantica(part)
                                                if ext in EXTENSOES_IMAGENS:
                                                    # GIFs inline são 100% assinaturas/logos — nunca contêm conteúdo BACEN
                                                    if eh_inline and ext == '.gif':
                                                        gravar_anexo = False
                                                    elif eh_inline and not permitir_imagem_inline_corpo:
                                                        gravar_anexo = False
                                                    else:
                                                        gravar_anexo = anexo_imagem_eh_essencial(
                                                            part,
                                                            payload_bytes,
                                                            filename,
                                                            permitir_imagem_inline_corpo,
                                                        )
                                                else:
                                                    gravar_anexo = anexo_eh_relevante(filename)
                                                caminho_completo = os.path.join(PASTA_ANEXOS_GERAL, nome_final) if gravar_anexo else None

                                            if gravar_anexo and payload_bytes and caminho_completo:
                                                with open(caminho_completo, 'wb') as f:
                                                    f.write(payload_bytes)
                                                entrada_anexo = {
                                                    "arquivo_disco": nome_final,
                                                    "nome_original": filename,
                                                    "tipo": content_type
                                                }
                                                # Registrar content_id para permitir substituição cid→arquivo no script 09
                                                cid_raw = (part.get("Content-ID") or part.get("Content-Id") or "").strip().strip("<>")
                                                if cid_raw:
                                                    entrada_anexo["content_id"] = cid_raw
                                                anexos.append(entrada_anexo)
                                else:
                                    raw = msg.get_payload(decode=True)
                                    payload = (raw or b'').decode(msg.get_content_charset() or 'utf-8', errors='replace')
                                    if msg.get_content_type() == "text/html": 
                                        corpo_html = payload
                                    else: 
                                        corpo_texto = payload

                                # JSON BRUTO - Campos como vieram do servidor
                                atividades.append({
                                "data_email": date_raw,
                                "id": m_id,

                                "message_id": message_id,
                                "in_reply_to": in_reply_to,
                                "references": references,
                                "references_raw": references_raw,
                                "thread_root": thread_root,
                                "x_gm_thrid": x_gm_thrid,  # ID de thread do Gmail (quando disponível)

                                "threadId": message_id,   # mantém o campo antigo, mas sem duplicar variável

                                "remetente": sender,
                                "reply_to": reply_to,
                                "destinatarios": destinatarios,
                                "cc": copia_cc,
                                "assunto": subject,

                                "corpo": corpo_html if corpo_html else corpo_texto,
                                "corpo_html": corpo_html,
                                "corpo_texto": corpo_texto,

                                "anexos_detectados": anexos

                                })
                                
                        if len(atividades) % 50 == 0:
                            salvar_checkpoint(atividades, silencioso=True)
                        pbar.update(1)

                    except Exception as e_inner:
                        tqdm.write(f"{Fore.RED}[X] {m_id}: {e_inner}")
                        pbar.update(1)
                        continue

            salvar_checkpoint(atividades, silencioso=True)
            registrar_consumo("gmail_imap", total_requisicoes, "requests", 0.0)
            registrar_execucao("02_coletar_emails", arquivo_saida=ARQUIVO_SAIDA)
            mail.logout()
            
            resumo(processados=len(fila_download), ignorados=len(atividades) - len(fila_download), tempo_s=relogio.elapsed)
            break

        except Exception as error:
            print(f"\n{Fore.RED}[X] Tentativa {tentativa + 1}/{tentativas_maximas} falhou: {error}")
            if tentativa + 1 < tentativas_maximas:
                print(f"   Aguardando {intervalo_retry}s para nova tentativa...")
                time.sleep(intervalo_retry)
            continue
    else:
        raise RuntimeError(
            f"Gmail inacessível após {tentativas_maximas} tentativas. "
            "Verifique conexão, credenciais IMAP e status do serviço Google."
        )

def reimport_ids(ids_str):
    """Remove mensagens do 01 para que sejam re-coletadas (útil após correções no parser de anexos)."""
    ids = [x.strip() for x in ids_str.split(",") if x.strip()]
    if not ids:
        return False
    if not os.path.exists(ARQUIVO_SAIDA):
        print(f"{Fore.YELLOW}[!] Arquivo {ARQUIVO_SAIDA} não existe.")
        return False
    with open(ARQUIVO_SAIDA, "r", encoding="utf-8") as f:
        dados = json.load(f)
    antes = len(dados)
    dados = [d for d in dados if str(d.get("id", "")) not in ids]
    removidos = antes - len(dados)
    if removidos == 0:
        print(f"{Fore.YELLOW}[!] Nenhum dos IDs {ids} encontrado no 01.")
        return False
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    print(f"{Fore.GREEN}[OK] Removidos {removidos} registro(s) do 01. Serão re-coletados na próxima execução.")
    return True


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Coletor de e-mails ORÁCULO 360")
    ap.add_argument("--reimport-ids", metavar="IDS", help="IDs separados por vírgula para re-coletar (ex.: 91947,91977)")
    args = ap.parse_args()
    with iniciar_log_standalone(2, "coletar_emails_gmail"):
        if args.reimport_ids:
            reimport_ids(args.reimport_ids)
        coletar_emails()
