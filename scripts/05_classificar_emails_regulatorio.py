"""
ORÁCULO 360 - Classificador Regulatório (02)

Responsabilidade: classificar e-mails do 01 (CADOC, prazos, cliente, responsável), limpar HTML/assinaturas
e agrupar por thread. Gera 02_classificação_dados_brutos_gmail_editado.json (eventos + threads_processadas).

Entrada: 01_extração_dados_brutos_gmail.json, mapeamento_regras_negocio.json.
Saída: 02_classificação_dados_brutos_gmail_editado.json (consumido pelo 06_integrador_dados).

Modos: ORACULO_VERBOSE=1 para detalhe por e-mail; ORACULO_INCREMENTAL=1 para processar apenas e-mails novos
(carrega saída anterior e reutiliza classificações já existentes).
Período: DATA_COLETA_INICIO / DATA_LIMITE_EXCLUIR (DD-MMM-YYYY).

Quando o 01 acumula vários dias e o período do 04 é só um dia (ex.: correr 24 com 23+24 no 01),
sem reutilização todos os e-mails fora da janela viram FILTRADO_POR_DATA e o operacional
“estraga” o dia anterior. Por omissão ``ORACULO_PRESERVAR_CLASSIFICACAO_FORA_PERIODO=1`` (ou ausente)
reaproveita a classificação do JSON 02 anterior para esses ids. Desligar: ``=0``.
"""

import json
import os
import re
import sys
import calendar
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from email.utils import parsedate_to_datetime
from html import unescape
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ============================================================================
# CONFIGURAÇÃO DE ARQUIVOS - CAMINHOS FIXOS
# ============================================================================

# Caminho base do projeto (pai da pasta scripts)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Caminhos fixos (CORRIGIDOS)
from paths import F_MAPEAMENTO, F_EMAILS_BRUTOS, F_EMAILS_CLASS, registrar_execucao, verificar_dependencias
from pipeline_log import cabecalho, resumo, Cronometro, iniciar_log_standalone
ARQUIVO_REGRAS   = F_MAPEAMENTO
ARQUIVO_ENTRADA  = F_EMAILS_BRUTOS
ARQUIVO_SAIDA    = F_EMAILS_CLASS

# Período: use ao rodar sozinho; ao rodar via executar_tudo.py, o orquestrador define por env.
# Formato DD-MMM-YYYY (mesmo do 01_coletor_email).
DATA_COLETA_INICIO = os.environ.get("DATA_COLETA_INICIO", "21-Jan-2026")
DATA_LIMITE_EXCLUIR = os.environ.get("DATA_LIMITE_EXCLUIR", "01-Feb-2026")

# Modo resumo: quando False, não imprime detalhe por email (evita poluir o log).
# Use ORACULO_VERBOSE=1 no ambiente para ver todos os detalhes.
VERBOSE = os.environ.get("ORACULO_VERBOSE", "").strip().lower() in ("1", "true", "yes")

# Modo incremental: quando True, carrega a saída anterior do 02 e processa apenas e-mails novos (por id).
# Muito mais rápido em reexecuções em que o 01 só ganhou poucos e-mails. Use ORACULO_INCREMENTAL=1.
INCREMENTAL = os.environ.get("ORACULO_INCREMENTAL", "").strip().lower() in ("1", "true", "yes")

# Reaproveitar classificação do 02 anterior para e-mails cuja data cai FORA do período atual
# (evita FILTRADO_POR_DATA em massa quando o 01 tem vários dias e o 04 corre só um).
PRESERVAR_CLASSIFICACAO_FORA_PERIODO = os.environ.get(
    "ORACULO_PRESERVAR_CLASSIFICACAO_FORA_PERIODO", "1"
).strip().lower() not in ("0", "false", "no", "")

# Variável global para mapeamento (carregada no main)
MAPEAMENTO_CLIENTES = {}

# Acumula domínios sem nome no mapeamento — exibidos ao final da classificação (#42)
_DOMINIOS_SEM_NOME: set = set()


# ============================================================================
# LIMPEZA DE HTML → TEXTO LIMPO
# ============================================================================

def limpar_html_para_texto(html):
    """Converte HTML em texto plano: remove tags, decodifica entidades e preserva quebras de linha quando possível."""
    if not html:
        return ""

    try:
        # Se BeautifulSoup não estiver disponível, faz fallback simples
        if BeautifulSoup is None:
            texto = re.sub(r'<[^>]+>', ' ', html)
            texto = re.sub(r'\s+', ' ', texto).strip()
            return texto

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts/styles
        for tag in soup(["script", "style"]):
            tag.decompose()

        # Converte <br> em \n
        for tag in soup.find_all("br"):
            tag.replace_with("\n")

        # Adiciona \n antes/depois de tags de bloco (preserva estrutura)
        for tag in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", 
                                   "h4", "h5", "h6", "blockquote", "table"]):
            tag.insert_before("\n")
            tag.insert_after("\n")

        # Pega o texto
        texto = soup.get_text()

        # Normalizações
        texto = texto.replace("\xa0", " ")
        texto = re.sub(r"[ \t]+", " ", texto)          # espaços duplicados
        texto = re.sub(r"\n\s*\n+", "\n\n", texto)     # blocos vazios
        texto = re.sub(r" *\n *", "\n", texto)         # limpa espaços ao redor de \n

        return texto.strip()

    except Exception:
        # Fallback simples
        texto = re.sub(r'<[^>]+>', ' ', str(html))
        texto = re.sub(r'\s+', ' ', texto).strip()
        return texto


# ============================================================================
# LIMPEZA PROFUNDA DO CORPO (REMOVE ASSINATURAS, DISCLAIMERS, CITAÇÕES)
# ============================================================================

def limpar_corpo_profundo(texto):
    """
    Remove assinaturas, disclaimers legais, citações de emails anteriores,
    telefones, endereços, cargos, URLs e texto institucional.
    
    Entrada: texto já sem HTML (saída de limpar_html_para_texto)
    Saída: apenas o conteúdo útil/acionável da mensagem
    
    CHANGELOG:
    - v1: Versão inicial
    - v2: Corrigido regex De: para exigir <email@dom>, adicionado Att;, 
          disclaimers Avenue, URLs, cargos isolados
    - v3: Removido [cid: dos disclaimers (fix 90109 vazio), cortado citações
          Gmail (>), detectado bloco assinatura nome+cargo, normalização \r\n
    """
    if not texto or not texto.strip():
        return ""

    t = texto

    # Normaliza quebras de linha (Windows → Unix)
    t = t.replace('\r\n', '\n').replace('\r', '\n')

    # ---------------------------------------------------------------
    # 1) MENSAGENS PROTEGIDAS (Microsoft Purview)
    # ---------------------------------------------------------------
    if re.search(r'enviou uma mensagem protegida|Microsoft Purview|Message Encryption', t, re.IGNORECASE):
        return "Mensagem protegida (conteúdo criptografado)."

    # ---------------------------------------------------------------
    # 2) CORTAR EM CITAÇÕES DE EMAILS ANTERIORES
    #    Regex exige <email@dominio> para evitar cortar "De:" solto
    # ---------------------------------------------------------------
    marcadores_citacao = [
        r'De:\s+[^<\n]+<[\w\.\-]+@[\w\.\-]+>',
        r'From:\s+[^<\n]+<[\w\.\-]+@[\w\.\-]+>',
        r'Enviado?a?\s*em:\s*\w+',
        r'Sent:\s*\w+',
        r'-----\s*Original\s*Message\s*-----',
        r'_{10,}',
        r'---------- Forwarded message ---------',
        r'Em\s+\w{3,4}\.?,?\s*\d{1,2}\s+de\s+\w+\.?\s+de\s+\d{4}\s+[àa]s\s+\d{1,2}:\d{2}.+escreveu\s*:',
        r'On\s+[\w\s,]+\d{4}.+wrote\s*:',
    ]

    pos_corte = len(t)
    for padrao in marcadores_citacao:
        match = re.search(padrao, t, re.IGNORECASE | re.MULTILINE)
        if match and match.start() < pos_corte:
            pos_corte = match.start()
    t = t[:pos_corte]

    # ---------------------------------------------------------------
    # 3) CORTAR EM MARCADORES DE ASSINATURA
    # ---------------------------------------------------------------
    marcas_assinatura = [
        r'Atenciosamente[\.\,]?',
        r'Cordialmente[\.\,]?',
        r'Att[\.\,;]\s',
        r'Att\s*\n',
        r'Kind\s+Regards',
        r'Best\s+Regards',
        r'Regards[\.\,]',
        r'Thanks[\.\,]',
        r'Thank\s+you[\.\,]',
    ]

    pos_assinatura = len(t)
    for padrao in marcas_assinatura:
        match = re.search(padrao, t, re.IGNORECASE)
        if match and match.start() < pos_assinatura:
            pos_assinatura = match.start()
    t = t[:pos_assinatura]

    # ---------------------------------------------------------------
    # 4) REMOVER DISCLAIMERS LEGAIS
    #    (NÃO inclui [cid: aqui — tratado nas linhas)
    # ---------------------------------------------------------------
    disclaimers = [
        "Este e-mail pode conter",
        "This e-mail may contain",
        "This email may contain",
        "The information contained in this message",
        "The information transmitted",
        "The content of this message",
        "Mensagem confidencial",
        "informações confidenciais e/ou privilegiadas",
        "Aviso legal:",
        "To unsubscribe from this group",
        "Antes de imprimir pense",
        "Avenue is the brand name",
        "Se você não deseja mais receber uma notificação automática do FogBugz",
        "Don't want FogBugz notifications anymore",
    ]

    for marca in disclaimers:
        idx = t.lower().find(marca.lower())
        if idx != -1:
            t = t[:idx]

    # ---------------------------------------------------------------
    # 5) DETECTAR BLOCO DE ASSINATURA: nome próprio + cargo
    #    Ex: "Andrea Inacio\nCoordenadora de Suporte"
    # ---------------------------------------------------------------
    padrao_assinatura_bloco = re.search(
        r'\n([A-Z][a-záàãâéêíóôõúç]+\s+[A-Z][a-záàãâéêíóôõúç]+)\s*\n'
        r'\s*(Coordenador|Analista|Gerente|Diretor|Supervisor|Manager|BackOffice|Cash Management)',
        t, re.IGNORECASE
    )
    if padrao_assinatura_bloco:
        t = t[:padrao_assinatura_bloco.start()]

    # ---------------------------------------------------------------
    # 6) FILTRAR LINHAS INDIVIDUAIS
    # ---------------------------------------------------------------
    linhas = t.split('\n')
    linhas_limpas = []
    for linha in linhas:
        l = linha.strip()
        if not l:
            continue

        # Citações Gmail (linhas com >)
        if l.startswith('>'):
            continue

        # Imagens embutidas [cid:...] ou [descrição]
        if re.match(r'^\[.*\]$', l):
            continue
        if l.startswith('[signature_') or l.startswith('[cid:'):
            continue

        # Telefone/Ramal
        if re.match(r'^(Fone|Tel\.?|Phone|Telefone)\s*:?\s*[\(\+\d]', l, re.IGNORECASE):
            continue
        if re.match(r'^RAMAL\s+\d+', l, re.IGNORECASE):
            continue
        if re.match(r'^\+?\d[\d\s\-\(\)]{8,}$', l):
            continue
        if re.match(r'^Office:\s*\+', l, re.IGNORECASE):
            continue

        # Endereço
        if re.match(r'^(Rua|Av\.?|Avenida|Alameda)\s+.+\d', l, re.IGNORECASE):
            continue
        if re.match(r'^(Itaim Bibi|Butantã|Jardim|Post Code|CEP)', l, re.IGNORECASE):
            continue

        # URLs isoladas (linha que é só URL)
        if re.match(r'^(https?://|www\.|<https?://)', l, re.IGNORECASE):
            continue

        # Cargo isolado (linha curta)
        if re.match(r'^(Analista|Coordenador|Gerente|Diretor|Supervisor|BackOffice|Manager)\b', l, re.IGNORECASE) and len(l) < 80:
            continue

        # Setor isolado
        if re.match(r'^(Suporte|Financeiro|Compliance|SPB)$', l, re.IGNORECASE):
            continue

        # Email isolado numa linha
        if re.match(r'^[\w\.\-]+@[\w\.\-]+\.\w+(<.*>)?$', l) and len(l) < 120:
            continue

        # Nome próprio isolado (2-3 palavras, sem verbo)
        if re.match(r'^[A-Z][a-záàãâéêíóôõúç]+(\s+[A-Z][a-záàãâéêíóôõúç]+){1,2}$', l) and len(l) < 40:
            continue

        linhas_limpas.append(l)

    t = '\n'.join(linhas_limpas)

    # ---------------------------------------------------------------
    # 7) LIMPEZA DE MARKUP RESIDUAL INLINE
    # ---------------------------------------------------------------
    t = re.sub(r'<mailto:[^>]+>', '', t)
    t = re.sub(r'<https?://[^>]+>', '', t)
    t = re.sub(r'\[cid:[^\]]+\]', '', t)
    t = re.sub(r'\[signature_[^\]]+\]', '', t)

    # ---------------------------------------------------------------
    # 8) LIMPEZA FINAL
    # ---------------------------------------------------------------
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r' {2,}', ' ', t)
    t = t.strip()

    if not t:
        return "(sem conteúdo textual)"
    return t


# ============================================================================
# IDENTIFICAÇÃO DE CLIENTE E RESPONSÁVEL
# ============================================================================

def extrair_email_simples(texto):
    """Extrai email de 'Nome <email@dominio.com>'"""
    if not texto:
        return ""
    match = re.search(r'<([^>]+)>', texto)
    if match:
        return match.group(1).strip().lower()
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', texto)
    if match:
        return match.group(0).strip().lower()
    return texto.strip().lower()

def extrair_todos_emails_texto(texto):
    """Extrai TODOS os emails de uma string"""
    if not texto:
        return []
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', texto.lower())
    return [e.strip() for e in emails]

def extrair_dominio_email(email_addr):
    """Extrai domínio de um email"""
    if '@' in email_addr:
        return email_addr.split('@')[1].lower()
    return ""

def extrair_nome_pessoa(texto):
    """Extrai nome da pessoa de 'Nome <email>'"""
    if not texto:
        return ""

    # #PF6: decodificar encoding MIME (=?UTF-8?Q?...?= ou =?Windows-1252?Q?...?=)
    if '=?' in texto:
        try:
            from email.header import decode_header as _dh, make_header as _mh
            texto = str(_mh(_dh(texto)))
        except Exception:
            pass

    texto = texto.replace("'", "").replace('"', '')
    
    # Padrão: Nome via Algo <email>
    match_via = re.search(r'^([^<]+?)\s+via\s+', texto, re.IGNORECASE)
    if match_via:
        return match_via.group(1).strip()
    
    # Padrão normal: Nome <email>
    match = re.search(r'^([^<]+)<', texto)
    if match:
        nome = match.group(1).strip()
        nome = nome.split(',')[0].strip()
        return nome
    
    # Fallback: deduz do email
    email_addr = extrair_email_simples(texto)
    if email_addr and '@' in email_addr:
        nome = email_addr.split('@')[0]
        return nome.replace('.', ' ').title()
    
    return texto.strip()

def eh_email_finaud_check(email, dominios_finaud):
    """Verifica se email pertence à Finaud"""
    if not email:
        return False
    return any(dominio in email for dominio in dominios_finaud)

def eh_email_ignorar_check(email, dominios_ignorar):
    """Verifica se email deve ser ignorado"""
    if not email:
        return False
    dominio = extrair_dominio_email(email)
    return any(ignorar in dominio for ignorar in dominios_ignorar)

def encontrar_email_cliente_valido(emails_list, dominios_finaud, dominios_ignorar):
    """Encontra primeiro email que é de cliente"""
    for email in emails_list:
        if not email:
            continue
        if eh_email_finaud_check(email, dominios_finaud):
            continue
        if eh_email_ignorar_check(email, dominios_ignorar):
            continue
        return email
    return None


def extrair_primeiro_email_externo_apos_encaminhamento(
    texto: str, dominios_finaud, dominios_ignorar
) -> Optional[str]:
    """
    Só após marcador típico de encaminhamento (Gmail/Outlook): primeiro e-mail que não é Finaud.
    Uso restrito ao ramo «Finaud → Finaud» no envelope, para não misturar com assinaturas fora do Fwd.
    """
    if not texto or not str(texto).strip():
        return None
    low = texto.lower()
    marcadores = (
        "---------- forwarded message ---------",
        "-----forwarded message-----",
        "-----original message-----",
        "begin forwarded message",
        "original message -----",
    )
    idx = -1
    for m in marcadores:
        j = low.find(m)
        if j >= 0:
            idx = j if idx < 0 else min(idx, j)
    if idx < 0:
        return None
    trecho = texto[idx : idx + 14000]
    padroes = (
        r"(?i)\bDe:\s*.+?<([^\s<>]+@[^\s<>]+)>",
        r"(?i)\bFrom:\s*.+?<([^\s<>]+@[^\s<>]+)>",
        r"(?i)\bDe:\s*[\"']?[^\"'<\n]*[\"']?\s*<([^\s<>]+@[^\s<>]+)>",
    )
    for pat in padroes:
        for m in re.finditer(pat, trecho):
            em = (m.group(1) or "").strip().lower()
            if not em or "@" not in em:
                continue
            if eh_email_finaud_check(em, dominios_finaud):
                continue
            if eh_email_ignorar_check(em, dominios_ignorar):
                continue
            return em
    return None


def _inferir_empresa_de_assunto_ou_fwd(
    assunto: str,
    corpo_fwd: str,
    mapa_nomes_cli: dict,
    dominios_finaud,
    dominios_ignorar,
) -> Optional[str]:
    """
    Melhoria 2: infere empresa pelo token inicial do assunto (antes do primeiro ' - ').
    Melhoria 3: infere empresa por e-mail externo em Para:/To:/Cc: no bloco Fwd.
    Retorna nome do cliente ou None se não conseguir inferir.
    """
    import unicodedata as _ud

    def _norm(s: str) -> str:
        s = _ud.normalize("NFD", s.lower())
        return "".join(c for c in s if _ud.category(c) != "Mn")

    # --- Melhoria 2: assunto ---
    if assunto:
        partes = re.split(r"\s+-\s+", assunto.strip(), maxsplit=1)
        token_asu = _norm(partes[0].strip()) if partes else ""
        if token_asu and len(token_asu) >= 3:
            for _dom, _nome in mapa_nomes_cli.items():
                tokens_nome = _norm(_nome).split()
                if tokens_nome and (
                    token_asu == _norm(_nome)
                    or token_asu == tokens_nome[0]
                    or (len(token_asu) >= 4 and tokens_nome[0].startswith(token_asu))
                    or (len(tokens_nome[0]) >= 4 and token_asu.startswith(tokens_nome[0]))
                ):
                    return _nome

    # --- Melhoria 3: Para:/To:/Cc: no bloco encaminhado ---
    if corpo_fwd:
        low = corpo_fwd.lower()
        marcadores = (
            "---------- forwarded message ---------",
            "-----forwarded message-----",
            "-----original message-----",
            "begin forwarded message",
            "original message -----",
        )
        idx = -1
        for _m in marcadores:
            j = low.find(_m)
            if j >= 0:
                idx = j if idx < 0 else min(idx, j)
        if idx >= 0:
            trecho = corpo_fwd[idx: idx + 3000]
            padroes_dest = (
                r"(?i)\bPara:\s*[^<\n]*<([^\s<>]+@[^\s<>]+)>",
                r"(?i)\bTo:\s*[^<\n]*<([^\s<>]+@[^\s<>]+)>",
                r"(?i)\bCc:\s*[^<\n]*<([^\s<>]+@[^\s<>]+)>",
                r"(?i)\bPara:\s*([^\s<>\n]+@[^\s<>\n]+)",
                r"(?i)\bTo:\s*([^\s<>\n]+@[^\s<>\n]+)",
            )
            for _pat in padroes_dest:
                for _match in re.finditer(_pat, trecho):
                    em = (_match.group(1) or "").strip().lower()
                    if not em or "@" not in em:
                        continue
                    if eh_email_finaud_check(em, dominios_finaud):
                        continue
                    if eh_email_ignorar_check(em, dominios_ignorar):
                        continue
                    dom = extrair_dominio_email(em)
                    nome = mapa_nomes_cli.get(dom)
                    if not nome:
                        _DOMINIOS_SEM_NOME.add(dom)
                        nome = dom.split(".")[0].capitalize()
                    return nome

    return None


def extrair_nome_remetente_encaminhado(texto: str, email_lc: str) -> str:
    """Nome na mesma linha 'De: … <email>' do bloco encaminhado, se existir."""
    email_lc = (email_lc or "").strip().lower()
    if not email_lc:
        return ""
    for line in texto.splitlines():
        if email_lc not in line.lower():
            continue
        m = re.search(r"(?i)De:\s*(.+?)\s*<", line)
        if m:
            frag = m.group(1).strip().strip('"').strip("'")
            nome = extrair_nome_pessoa(frag)
            return nome or frag
        break
    return ""

def encontrar_responsavel_finaud_nome(destinatarios, cc, colaboradores_finaud, remetente_original):
    """Encontra nome do colaborador Finaud nos destinatários/CC, ignorando auto-cópia"""
    todos_dest = []
    
    for campo in [destinatarios, cc]:
        if not campo:
            continue
        partes = campo.split(',')
        for parte in partes:
            email = extrair_email_simples(parte.strip())
            nome = extrair_nome_pessoa(parte.strip())
            if email:
                todos_dest.append((email, nome))
    
    email_remetente = extrair_email_simples(remetente_original or "")
    
    for email_dest, nome_dest in todos_dest:
        # Ignora se for o próprio remetente
        if email_dest == email_remetente:
            continue
            
        if '@finaud' in email_dest:
            usuario = email_dest.split('@')[0]
            
            # Testa variações no mapeamento
            for chave in [usuario, usuario.replace('.', '_'), usuario.replace('.', '')]:
                if chave in colaboradores_finaud:
                    return colaboradores_finaud[chave]
            
            # Se não achou, usa nome extraído
            if nome_dest and nome_dest != email_dest:
                return nome_dest
    
    return "Suporte Finaud"

def identificar_cliente_e_responsavel_completo(email_data, mapeamento_clientes):
    """
    Identifica cliente e responsável baseado em remetente/destinatários
    
    REGRA:
    - Cliente ENVIA → Responsável = pessoa da FINAUD
    - FINAUD ENVIA → Responsável = pessoa do CLIENTE
    """
    dominios_finaud = mapeamento_clientes.get('nossa_equipe', {}).get('dominios', [])
    mapa_nomes = mapeamento_clientes.get('mapeamento_nomes_clientes', {})
    dominios_ignorar = mapeamento_clientes.get('clientes_externos', {}).get('dominios_a_ignorar', [])
    colaboradores_finaud = mapeamento_clientes.get('colaboradores_finaud', {})
    
    remetente = email_data.get('remetente', '')
    destinatarios = email_data.get('destinatarios', '')
    reply_to = email_data.get('reply_to', '')
    cc = email_data.get('cc', '')
    
    # Extrai emails
    email_remetente = extrair_email_simples(remetente)
    email_reply = extrair_email_simples(reply_to)
    emails_dest = extrair_todos_emails_texto(destinatarios)
    emails_cc = extrair_todos_emails_texto(cc)
    todos_destinatarios = emails_dest + emails_cc
    
    # Determina remetente real (prioriza Reply-To)
    remetente_real = email_remetente
    if email_reply and not eh_email_finaud_check(email_reply, dominios_finaud):
        remetente_real = email_reply
    
    # CASO 1: CLIENTE ENVIOU
    if not eh_email_finaud_check(remetente_real, dominios_finaud):
        dominio_cliente = extrair_dominio_email(remetente_real)
        
        # Nome da EMPRESA
        nome_cliente = mapa_nomes.get(dominio_cliente, None)
        if not nome_cliente:
            _DOMINIOS_SEM_NOME.add(dominio_cliente)
            nome_cliente = dominio_cliente.split('.')[0].capitalize()
        
        # Nome da PESSOA da Finaud que deve responder
        responsavel = encontrar_responsavel_finaud_nome(destinatarios, cc, colaboradores_finaud, remetente)
        
        return nome_cliente, responsavel
    
    # CASO 2: FINAUD ENVIOU
    if eh_email_finaud_check(remetente_real, dominios_finaud):
        cliente_email = encontrar_email_cliente_valido(todos_destinatarios, dominios_finaud, dominios_ignorar)
        
        if cliente_email:
            dominio_cliente = extrair_dominio_email(cliente_email)
            
            # Nome da EMPRESA
            nome_cliente = mapa_nomes.get(dominio_cliente, None)
            if not nome_cliente:
                _DOMINIOS_SEM_NOME.add(dominio_cliente)
                nome_cliente = dominio_cliente.split('.')[0].capitalize()
            
            # Nome da PESSOA do cliente
            nome_responsavel = None
            email_remetente_original = extrair_email_simples(remetente)
            
            # Procura nos destinatários, ignorando auto-cópia
            for dest in destinatarios.split(',') if destinatarios else []:
                dest = dest.strip()
                email_dest = extrair_email_simples(dest)
                
                if email_dest == email_remetente_original:
                    continue
                if eh_email_finaud_check(email_dest, dominios_finaud):
                    continue
                if eh_email_ignorar_check(email_dest, dominios_ignorar):
                    continue
                
                nome_responsavel = extrair_nome_pessoa(dest)
                if nome_responsavel:
                    break
            
            # Tenta no CC se não achou
            if not nome_responsavel and cc:
                for dest in cc.split(','):
                    dest = dest.strip()
                    email_dest = extrair_email_simples(dest)
                    
                    if email_dest == email_remetente_original:
                        continue
                    if eh_email_finaud_check(email_dest, dominios_finaud):
                        continue
                    if eh_email_ignorar_check(email_dest, dominios_ignorar):
                        continue
                    
                    nome_responsavel = extrair_nome_pessoa(dest)
                    if nome_responsavel:
                        break
            
            # Fallback: usa nome da empresa
            if not nome_responsavel:
                nome_responsavel = nome_cliente
            
            return nome_cliente, nome_responsavel
    
    return "DESCONHECIDO", "Suporte Finaud"


# ============================================================================
# CLASSE: FILTRO DE HISTÓRICO DE EMAIL
# ============================================================================

class FiltroHistorico:
    """Remove conteúdo de histórico de emails, mantendo apenas a thread atual"""
    
    MARCADORES_HISTORICO = [
        r'-----Original Message-----',
        r'De:.*Enviada em:.*\d{4}',  # Mais específico
        r'From:.*Sent:.*\d{4}',
        r'\[Texto das mensagens anteriores oculto\]',
        r'Em.*\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4}.*escreveu:',
        r'On.*\d{1,2}.*\d{4}.*wrote:',
        r'---------- Forwarded message ---------',
    ]
    
    @staticmethod
    def extrair_mensagem_atual(texto: str) -> str:
        """
        Extrai apenas a mensagem atual, removendo histórico/quotes
        CORREÇÃO: Corta mais agressivamente em datas antigas
        """
        if not texto:
            return ""
        
        # Procura pelo primeiro marcador de histórico
        posicao_corte = len(texto)
        
        for marcador in FiltroHistorico.MARCADORES_HISTORICO:
            match = re.search(marcador, texto, re.IGNORECASE | re.MULTILINE)
            if match:
                posicao_corte = min(posicao_corte, match.start())
        
        # Corta em "Enviada em: DD de MES de AAAA" — cabeçalho de e-mail encaminhado (Outlook).
        # Qualquer ocorrência desse padrão no corpo indica que o texto seguinte é histórico
        # de um encaminhamento e não deve ser usado para extração de datas/prazos.
        # Corrigido em #62: antes só detectava "janeiro de 2026"; agora detecta qualquer mês
        # (fevereiro, março, …) evitando prazos falsos gerados a partir de cabeçalhos Fwd.
        _MESES_PT = (r'(?:janeiro|fevereiro|mar[cç]o|abril|maio|junho|'
                     r'julho|agosto|setembro|outubro|novembro|dezembro)')
        padrao_data_enviada = rf'Enviada em:.*?\d{{1,2}}\s+de\s+{_MESES_PT}\s+de\s+\d{{4}}'
        for match in re.finditer(padrao_data_enviada, texto, re.IGNORECASE):
            posicao_corte = min(posicao_corte, match.start())
        
        # Retorna apenas o texto antes do histórico
        mensagem_atual = texto[:posicao_corte].strip()
        
        return mensagem_atual


# ============================================================================
# CLASSE: FILTRO POR DATA DO EMAIL
# ============================================================================

class FiltroPorData:
    """Filtra emails pelo período de coleta configurado"""
    
    def __init__(self, data_inicio: str, data_fim: str):
        """
        Args:
            data_inicio: String no formato "DD-MMM-YYYY" (ex: "21-Jan-2026")
            data_fim: String no formato "DD-MMM-YYYY" (ex: "22-Jan-2026")
        """
        self.data_inicio = self._converter_data(data_inicio)
        self.data_fim = self._converter_data(data_fim)
    
    def _converter_data(self, data_str: str) -> datetime:
        """Converte string DD-MMM-YYYY para datetime"""
        try:
            return datetime.strptime(data_str, "%d-%b-%Y")
        except:
            # Fallback para formato alternativo
            return datetime.strptime(data_str, "%d-%B-%Y")
    
    def email_esta_no_periodo(self, data_email_str: str) -> bool:
        """
        Verifica se o email está no período de coleta
        
        Args:
            data_email_str: String de data do email (formato RFC 2822)
                          Ex: "Wed, 21 Jan 2026 08:54:05 -0300"
        
        Returns:
            True se email está no período, False caso contrário
        """
        try:
            # Parse da data do email
            data_email = parsedate_to_datetime(data_email_str)
            
            # Remove timezone para comparação
            data_email = data_email.replace(tzinfo=None)
            
            # Verifica se está no intervalo [inicio, fim)
            return self.data_inicio <= data_email < self.data_fim
            
        except Exception as e:
            print(f"  [AVISO] Erro ao parsear data '{data_email_str}': {e}")
            return False


# ============================================================================
# CLASSE: NORMALIZADOR DE DATAS (COM TODAS AS CORREÇÕES)
# ============================================================================

class NormalizadorDatas:
    """
    CAMADA 1: Converte qualquer formato de data para datetime
    CORREÇÕES APLICADAS:
    - Lista de dias (Caso 1)
    - Formato ISO com hífen e ponto (Casos 3, 4, 14)
    - Mês por extenso (Caso 7)
    - Mês abreviado (Caso 20)
    - Intervalo de datas (Caso 11)
    """
    
    MESES = {
        'jan': 1, 'janeiro': 1,
        'fev': 2, 'fevereiro': 2,
        'mar': 3, 'março': 3,
        'abr': 4, 'abril': 4,
        'mai': 5, 'maio': 5,
        'jun': 6, 'junho': 6,
        'jul': 7, 'julho': 7,
        'ago': 8, 'agosto': 8,
        'set': 9, 'setembro': 9,
        'out': 10, 'outubro': 10,
        'nov': 11, 'novembro': 11,
        'dez': 12, 'dezembro': 12
    }
    
    def __init__(self, ano_padrao=None, feriados=None):
        self.ano_padrao = ano_padrao if ano_padrao is not None else datetime.now().year
        self.feriados = feriados or []
    
    def normalizar_ano(self, ano_str: str) -> int:
        """Converte ano de 2 ou 4 dígitos para formato completo"""
        ano = int(ano_str)
        if ano < 100:
            return 2000 + ano if ano < 50 else 1900 + ano
        return ano
    
    def eh_dia_util(self, data: datetime) -> bool:
        """Verifica se é dia útil"""
        return data.weekday() < 5 and data.date() not in self.feriados
    
    def gerar_dias_uteis_intervalo(self, data_inicio: datetime, data_fim: datetime) -> List[datetime]:
        """
        Gera lista de dias úteis entre duas datas (CORREÇÃO CASO 11)
        """
        dias_uteis = []
        data_atual = data_inicio
        
        while data_atual <= data_fim:
            if self.eh_dia_util(data_atual):
                dias_uteis.append(data_atual)
            data_atual += timedelta(days=1)
        
        return dias_uteis
    
    def _ctx_pre_pos(self, texto: str, match) -> tuple:
        """Retorna (contexto_pre, contexto_pos) para detectar pergunta (?) em cenários desconhecidos."""
        ctx_pre = texto[max(0, match.start()-30):match.start()]
        ctx_pos = texto[match.end():match.end()+15]
        return ctx_pre, ctx_pos
    
    def extrair_todas_datas(self, texto: str, data_referencia: Optional[datetime] = None) -> List[Tuple]:
        """
        Retorna lista de (datetime, formato_original, contexto_pre, is_intervalo, contexto_pos)
        contexto_pos: texto após a data — "?" indica pergunta/hipótese (rejeita em cenários desconhecidos).
        data_referencia: quando mês sozinho, usa para inferir ano.
        """
        texto_limpo = texto.replace('\xa0', ' ').replace('\t', ' ')
        datas_encontradas = []
        
        # =====================================================================
        # PADRÃO 0: INTERVALO DE DATAS (CASO 11) - PRIORIDADE MÁXIMA
        # Ex: "15/01/2026 A 20/01/2026" → gera dias úteis entre elas
        # CORREÇÃO: Marca is_intervalo=True
        # =====================================================================
        padrao_intervalo = r'(\d{1,2})/(\d{1,2})/(\d{4})\s+[AaEe]\s+(\d{1,2})/(\d{1,2})/(\d{4})'
        for match in re.finditer(padrao_intervalo, texto_limpo):
            try:
                dia1, mes1, ano1 = int(match.group(1)), int(match.group(2)), int(match.group(3))
                dia2, mes2, ano2 = int(match.group(4)), int(match.group(5)), int(match.group(6))
                
                data_inicio = datetime(ano1, mes1, dia1)
                data_fim = datetime(ano2, mes2, dia2)
                
                # Gera todos os dias úteis do intervalo
                dias_uteis = self.gerar_dias_uteis_intervalo(data_inicio, data_fim)
                
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                for data_util in dias_uteis:
                    datas_encontradas.append((data_util, match.group(0), ctx_pre, True, ctx_pos))
                
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 0b: D1 ATÉ D2/MM ou D1 a D2/MM/AAAA (ex.: "18 ATÉ 20/02", "18 a 20/02/2026")
        # DDR/4111: intervalo de dias no mesmo mês. Ano: do sufixo ou data_referencia.
        # Lookbehind (?<![/\d]) impede capturar o MM de uma data anterior como D1
        # (ex.: em "24/02 a 26/02", evita matchar "02 a 26/02"). O caso "DD/MM a DD/MM"
        # é tratado pelo Padrão 0d abaixo.
        # =====================================================================
        padrao_intervalo_dias = r'(?<![/\d])(\d{1,2})\s+(?:ATÉ|até|a|A)\s+(\d{1,2})/(\d{1,2})(?:/(\d{4}))?'
        for match in re.finditer(padrao_intervalo_dias, texto_limpo, re.IGNORECASE):
            try:
                dia1, dia2 = int(match.group(1)), int(match.group(2))
                mes = int(match.group(3))
                ano = int(match.group(4)) if match.group(4) else (data_referencia.year if data_referencia else self.ano_padrao)
                if mes > 12 or dia1 > 31 or dia2 > 31:
                    continue
                for dia in range(min(dia1, dia2), max(dia1, dia2) + 1):
                    try:
                        dt = datetime(ano, mes, dia)
                        ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                        datas_encontradas.append((dt, match.group(0), ctx_pre, True, ctx_pos))
                    except ValueError:
                        pass
            except (ValueError, TypeError):
                continue
        
        # =====================================================================
        # PADRÃO 0c: dd/mm - dd/mm (e opcional /aaaa no 2.º) — "DDR DIA 19/02 - 20/02"
        # O hífen entre datas não era coberto por 0b (só "ATÉ"/"a"). is_intervalo=True
        # para o validador aceitar sem âncora no fragmento "remessas".
        # =====================================================================
        padrao_intervalo_hifen_barras = r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*-\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?'
        for match in re.finditer(padrao_intervalo_hifen_barras, texto_limpo):
            try:
                d1, m1 = int(match.group(1)), int(match.group(2))
                ano1 = self.normalizar_ano(match.group(3)) if match.group(3) else (data_referencia.year if data_referencia else self.ano_padrao)
                d2, m2 = int(match.group(4)), int(match.group(5))
                ano2 = self.normalizar_ano(match.group(6)) if match.group(6) else ano1
                if m1 != m2 or ano1 != ano2 or m1 > 12 or d1 > 31 or d2 > 31:
                    # Intervalos com mudança de mês/ano: não expande aqui; outros padrões cobrem
                    continue
                inicio = datetime(ano1, m1, min(d1, d2))
                fim = datetime(ano1, m1, max(d1, d2))
                dias_uteis = self.gerar_dias_uteis_intervalo(inicio, fim)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                for data_util in dias_uteis:
                    datas_encontradas.append(
                        (data_util, match.group(0), ctx_pre, True, ctx_pos)
                    )
            except (ValueError, TypeError, AttributeError):
                continue

        # =====================================================================
        # PADRÃO 0d: dd/mm a dd/mm (com " a " / "até") — "DDR 24/02 a 26/02"
        # Mesmo escopo do 0c (hífen), mas com conector textual; mesmo mês/ano.
        # Sem este padrão, expressões "DD/MM a DD/MM" caíam no 0b errado
        # (que capturava o MM da 1.ª data como D1).
        # =====================================================================
        padrao_intervalo_a_barras = r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s+(?:ATÉ|até|a|A)\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?'
        for match in re.finditer(padrao_intervalo_a_barras, texto_limpo, re.IGNORECASE):
            try:
                d1, m1 = int(match.group(1)), int(match.group(2))
                ano1 = self.normalizar_ano(match.group(3)) if match.group(3) else (data_referencia.year if data_referencia else self.ano_padrao)
                d2, m2 = int(match.group(4)), int(match.group(5))
                ano2 = self.normalizar_ano(match.group(6)) if match.group(6) else ano1
                if m1 != m2 or ano1 != ano2 or m1 > 12 or d1 > 31 or d2 > 31:
                    # Intervalos com mudança de mês/ano: não expande aqui; 0a cobre com sufixo de ano
                    continue
                inicio = datetime(ano1, m1, min(d1, d2))
                fim = datetime(ano1, m1, max(d1, d2))
                dias_uteis = self.gerar_dias_uteis_intervalo(inicio, fim)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                for data_util in dias_uteis:
                    datas_encontradas.append(
                        (data_util, match.group(0), ctx_pre, True, ctx_pos)
                    )
            except (ValueError, TypeError, AttributeError):
                continue

        # =====================================================================
        # PADRÃO 1: LISTA DE DIAS (CASO 1) - ALTA PRIORIDADE
        # Ex: "16, 19 e 20/01/2026" → gera 16/01, 19/01, 20/01
        # CORREÇÃO: Word boundary para não pegar "26" de "2026"
        # =====================================================================
        padrao_lista = r'\b(\d{1,2}(?:\s*,\s*\d{1,2})*)\s+[eaEA]\s+(\d{1,2})/(\d{1,2})/(\d{4})'
        for match in re.finditer(padrao_lista, texto_limpo):
            try:
                dias_str = match.group(1)
                dias = re.findall(r'\d+', dias_str)
                mes = int(match.group(3))
                ano = int(match.group(4))
                
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                for dia_str in dias:
                    dia = int(dia_str)
                    dt = datetime(ano, mes, dia)
                    datas_encontradas.append((dt, dia_str, ctx_pre, False, ctx_pos))
                ultimo_dia = int(match.group(2))
                dt_ultimo = datetime(ano, mes, ultimo_dia)
                datas_encontradas.append((dt_ultimo, f"{ultimo_dia}/{mes}/{ano}", ctx_pre, False, ctx_pos))
                
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 2: FORMATO ISO COMPLETO (CASOS 3, 4, 14) - CORREÇÃO CRÍTICA
        # Ex: "2026-01-21" ou "2026.01.20"
        # =====================================================================
        # Hífen
        padrao_iso_hifen = r'(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)'
        for match in re.finditer(padrao_iso_hifen, texto_limpo):
            try:
                ano, mes, dia = int(match.group(1)), int(match.group(2)), int(match.group(3))
                dt = datetime(ano, mes, dia)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # Ponto
        padrao_iso_ponto = r'(?<!\d)(\d{4})\.(\d{1,2})\.(\d{1,2})(?!\d)'
        for match in re.finditer(padrao_iso_ponto, texto_limpo):
            try:
                ano, mes, dia = int(match.group(1)), int(match.group(2)), int(match.group(3))
                dt = datetime(ano, mes, dia)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 3: DD/MM/AAAA ou DD.MM.AAAA ou DD-MM-AAAA
        # =====================================================================
        padrao_barra = r'(?<!\d)(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})(?!\d)'
        for match in re.finditer(padrao_barra, texto_limpo):
            try:
                dia, mes, ano = int(match.group(1)), int(match.group(2)), self.normalizar_ano(match.group(3))
                dt = datetime(ano, mes, dia)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 4: DD/MM (assume ano padrão)
        # CORREÇÃO: Não pega "26" de "2026"
        # =====================================================================
        padrao_sem_ano = r'(?<!\d)(\d{1,2})/(\d{1,2})(?![/\d])'
        for match in re.finditer(padrao_sem_ano, texto_limpo):
            try:
                dia, mes = int(match.group(1)), int(match.group(2))
                if mes > 12:
                    if dia <= 12:
                        continue  # MM/YY inequívoco — já tratado pelo PADRÃO 8b2
                    dia, mes = mes, dia
                dt = datetime(self.ano_padrao, mes, dia)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 5: AAAAMMDD (compacto)
        # =====================================================================
        padrao_compacto = r'(?<!\d)(\d{8})(?!\d)'
        for match in re.finditer(padrao_compacto, texto_limpo):
            ano_str, mes_str, dia_str = match.group(1)[:4], match.group(1)[4:6], match.group(1)[6:]
            try:
                dt = datetime(int(ano_str), int(mes_str), int(dia_str))
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 6: DD de MÊS de AAAA (CASO 7 - Mês por extenso)
        # =====================================================================
        # Mês abreviado com ponto (Gmail: "23 de fev. de 2026") — sem o \.? o "fev" cai só no PADRÃO 10 (mês sozinho) → último dia do mês.
        padrao_extenso = r'(\d{1,2})\s+de\s+([a-zçã]+)\.?\s+de\s+(\d{2,4})'
        for match in re.finditer(padrao_extenso, texto_limpo, re.IGNORECASE):
            try:
                dia = int(match.group(1))
                mes_nome = match.group(2).lower()
                mes = self.MESES.get(mes_nome)
                ano = self.normalizar_ano(match.group(3))
                if mes:
                    dt = datetime(ano, mes, dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except (ValueError, KeyError):
                continue
        
        # =====================================================================
        # PADRÃO 7: DD MÊS AAAA (sem "de")
        # =====================================================================
        padrao_extenso_sem_de = r'(\d{1,2})\s+([a-zçã]+)\s+(\d{2,4})'
        for match in re.finditer(padrao_extenso_sem_de, texto_limpo, re.IGNORECASE):
            try:
                dia = int(match.group(1))
                mes_nome = match.group(2).lower()
                mes = self.MESES.get(mes_nome)
                ano = self.normalizar_ano(match.group(3))
                if mes:
                    dt = datetime(ano, mes, dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except (ValueError, KeyError):
                continue
        
        # =====================================================================
        # PADRÃO 8: MM/AAAA (competência mensal)
        # =====================================================================
        padrao_mensal = r'(?<![/\d])(\d{1,2})/(\d{4})(?![/\d])'
        for match in re.finditer(padrao_mensal, texto_limpo):
            try:
                mes, ano = int(match.group(1)), int(match.group(2))
                if mes <= 12:
                    # Retorna último dia do mês (CORREÇÃO CASOS 7, 13, 19, 20)
                    ultimo_dia = calendar.monthrange(ano, mes)[1]
                    dt = datetime(ano, mes, ultimo_dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 8b: MM AAAA (competência com espaço - ex.: "COS 12 2025", assunto)
        # Distingue relatório por competência (só assunto) de corpo com outras datas.
        # =====================================================================
        padrao_mensal_espaco = r'(?<!\d)(\d{1,2})\s+(\d{4})(?!\d)'
        for match in re.finditer(padrao_mensal_espaco, texto_limpo):
            try:
                mes, ano = int(match.group(1)), int(match.group(2))
                _ano_atual = datetime.now().year
                if 1 <= mes <= 12 and (_ano_atual - 2) <= ano <= (_ano_atual + 2):
                    ultimo_dia = calendar.monthrange(ano, mes)[1]
                    dt = datetime(ano, mes, ultimo_dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue
        
        # =====================================================================
        # PADRÃO 8b2: MM/YY — ano com 2 dígitos onde YY > 12 (inequivocamente ano, não dia)
        # Ex: "DLI 2062 04/26" → abril/2026 → 30/04/2026 (último dia do mês de competência)
        # Deve vir ANTES do PADRÃO 4 (DD/MM) para interceptar antes da troca dia↔mês.
        # Só captura quando o 2º número > 12 — evita ambiguidade com DD/MM normais.
        # =====================================================================
        padrao_mm_aa = r'(?<![/\d])(\d{1,2})/(\d{2})(?![/\d])'
        for match in re.finditer(padrao_mm_aa, texto_limpo):
            try:
                parte1, parte2 = int(match.group(1)), int(match.group(2))
                if parte2 <= 12:
                    continue  # ambíguo — deixa PADRÃO 4 (DD/MM) resolver
                if parte1 > 12:
                    continue  # nem mes nem dia válido
                mes = parte1
                ano = self.normalizar_ano(match.group(2))
                ultimo_dia = calendar.monthrange(ano, mes)[1]
                dt = datetime(ano, mes, ultimo_dia)
                ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except (ValueError, TypeError):
                continue

        # =====================================================================
        # PADRÃO 8c: #PF26 — Data embutida em código de arquivo (ex: DRL2160_012026, DRM2060_022026)
        # Cliente usa nome do arquivo como assunto: "DRL2160_012026" → mês=01, ano=2026 → 31/01/2026
        # =====================================================================
        padrao_cadoc_data = r'(?:DDR|DLO|DLI|DRM|DRL|4111)\d*[_\-](\d{2})(\d{4})(?!\d)'
        for match in re.finditer(padrao_cadoc_data, texto_limpo, re.IGNORECASE):
            try:
                mes, ano = int(match.group(1)), int(match.group(2))
                _ano_atual = datetime.now().year
                if 1 <= mes <= 12 and (_ano_atual - 2) <= ano <= (_ano_atual + 2):
                    ultimo_dia = calendar.monthrange(ano, mes)[1]
                    dt = datetime(ano, mes, ultimo_dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except ValueError:
                continue

        # =====================================================================
        # PADRÃO 9: MÊS de AAAA ou MÊS/AAAA (CASOS 7, 20)
        # Ex: "Dezembro/25", "Nov/25", "Janeiro de 2026"
        # =====================================================================
        padrao_mes_ano = r'([a-zçã]+)\s*(?:de\s+|/)(\d{2,4})'
        for match in re.finditer(padrao_mes_ano, texto_limpo, re.IGNORECASE):
            try:
                mes_nome = match.group(1).lower()
                mes = self.MESES.get(mes_nome)
                ano = self.normalizar_ano(match.group(2))
                if mes:
                    # Retorna último dia do mês
                    ultimo_dia = calendar.monthrange(ano, mes)[1]
                    dt = datetime(ano, mes, ultimo_dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except (ValueError, KeyError):
                continue
        
        # =====================================================================
        # PADRÃO 10: MÊS sozinho (ex.: "DLI DEZEMBRO", "DDR JANEIRO")
        # Ano: se data_referencia (data do email) disponível e mes > mes_email → ano anterior
        # (ex.: email fev/2026, "dezembro" → dez/2025). Senão usa ano_padrao.
        # =====================================================================
        meses_regex = '|'.join(sorted(self.MESES.keys(), key=len, reverse=True))
        padrao_mes_sozinho = r'(?<![a-z])\b(' + meses_regex + r')\b(?![a-z0-9/])'
        for match in re.finditer(padrao_mes_sozinho, texto_limpo, re.IGNORECASE):
            try:
                # "23 de fev. de 2026" — o token "fev" não é competência solta; evita 28/02 (último dia) falso.
                _start = match.start()
                _pre = texto_limpo[max(0, _start - 16) : _start]
                if re.search(r"\d{1,2}\s+de\s+$", _pre):
                    continue
                mes_nome = match.group(1).lower()
                mes = self.MESES.get(mes_nome)
                if mes:
                    if data_referencia:
                        # Email fev/2026 + "dezembro" → dez/2025 (mês citado já passou no ano?)
                        ano = data_referencia.year - 1 if mes > data_referencia.month else data_referencia.year
                    else:
                        ano = self.ano_padrao
                    ultimo_dia = calendar.monthrange(ano, mes)[1]
                    dt = datetime(ano, mes, ultimo_dia)
                    ctx_pre, ctx_pos = self._ctx_pre_pos(texto_limpo, match)
                    datas_encontradas.append((dt, match.group(0), ctx_pre, False, ctx_pos))
            except (ValueError, KeyError):
                continue
        
        # Remove duplicatas mantendo a ordem (5-tupla: dt, fmt, ctx, is_intervalo, ctx_pos)
        datas_unicas = []
        datas_vistas = set()
        for t in datas_encontradas:
            dt, fmt, ctx = t[0], t[1], t[2]
            is_intervalo = t[3]
            ctx_pos = t[4] if len(t) >= 5 else ""
            if dt not in datas_vistas:
                datas_vistas.add(dt)
                datas_unicas.append((dt, fmt, ctx, is_intervalo, ctx_pos))
        
        return datas_unicas


# ============================================================================
# CLASSE: VALIDADOR CONTEXTUAL (COM FILTROS CORRIGIDOS)
# ============================================================================

class ValidadorContextual:
    """
    CAMADA 2: Valida se a data faz sentido para o tipo de relatório
    CORREÇÕES:
    - Filtro de contextos negativos (Caso 1)
    - Prioridade de âncoras positivas
    - Filtro de datas explicativas (Caso 21)
    """
    
    ANCORAS_DIARIAS = [
        'dia', 'base', 'dias', 'diário', 'diaria',
        'posição', 'posicao', 'saldo', 'extrato', 'balancete',
        'dos dias', 'do dia', 'ddr de', '4111', 'data-base', 'data base'
    ]
    
    ANCORAS_MENSAIS = [
        'competência', 'competencia', 'mês', 'mes', 'mensal',
        'período', 'periodo', 'ref', 'referente', 'competencia',
        'remessa de', 'remessa do', 'dlo ', 'cos ', 'dlr '
    ]
    
    # Contextos que indicam que NÃO é data base
    CONTEXTOS_NEGATIVOS = [
        'prazo', 'limite', 'envio', 'vencimento', 'entrega',
        'deadline', 'até', 'ate', 'encerramento'
    ]
    
    # CORREÇÃO CASO 21: Contextos explicativos
    CONTEXTOS_EXPLICATIVOS = [
        'posteriores a', 'a partir de', 'desde', 'para datas bases posteriores a',
        'após', 'apos', 'anterior a', 'antes de'
    ]
    
    # Contextos que indicam pergunta/hipótese (ex.: "seria a remessa DLO jan/2026?")
    # Rejeita para priorizar a afirmação (ex.: "Remessa de dezembro/2025")
    CONTEXTOS_INDICAM_PERGUNTA = [
        'seria a ', 'seria o ', 'seriam '
    ]
    
    @staticmethod
    def _match_anchors_in_context(ancoras, contexto_lower: str) -> bool:
        """
        Evita falso positivo: 'mes' em 'remessas' era tratado como âncora MENSAL e rejeitava
        DIARIA (ex.: assunto 'DDR DIA 19/02 - 20/02. Seguem as remessas 19 e 20/02/2026').
        Âncoras curtas (até 3 caracteres) exigem limites de palavra; demais, substring.
        """
        if not contexto_lower or not ancoras:
            return False
        for a in ancoras:
            al = (a or "").lower().strip()
            if not al:
                continue
            if len(al) <= 3:
                if re.search(
                    r"(?<![0-9a-záéíóúãõç])" + re.escape(al) + r"(?![0-9a-záéíóúãõç])",
                    contexto_lower,
                    re.IGNORECASE,
                ):
                    return True
            else:
                if al in contexto_lower:
                    return True
        return False
    
    def __init__(self, regras_json):
        self.regras = regras_json
        self.deteccao_cadoc = regras_json.get("DETECCAO_INTELIGENTE_CADOC", {})
        _classif = regras_json.get("CLASSIFICACAO_EMAIL", {})
        self.filtros_lixo    = _classif.get("lixo", {})
        self.filtros_interno = _classif.get("interno", {})
        self.retorno_bacen = regras_json.get("TIPIFICACAO_RETORNO_BACEN", {})

    def eh_email_interno(self, remetente: str, assunto: str) -> bool:
        """Verifica se o email é interno (guardado para consulta, nunca vai à triagem)."""
        fil = self.filtros_interno
        if not fil:
            return False
        for rem in fil.get("por_remetente", []):
            if rem and rem.lower() in (remetente or "").lower():
                return True
        assunto_upper = (assunto or "").upper()
        for padrao in fil.get("por_assunto", []):
            if (padrao or "").upper() in assunto_upper:
                return True
        return False

    def eh_email_lixo_por_remetente(self, remetente: str) -> bool:
        """Verifica se o remetente está na lista de lixo (descartado completamente)."""
        for rem in self.filtros_lixo.get("por_remetente", []):
            if rem and rem.lower() in (remetente or "").lower():
                return True
        return False

    def deve_ignorar_assunto(self, assunto: str) -> bool:
        """Verifica se o assunto está na lista de lixo por assunto."""
        assunto_upper = (assunto or "").upper()
        for filtro in self.filtros_lixo.get("por_assunto", []):
            if (filtro or "").upper() in assunto_upper:
                return True
        return False

    def deve_ignorar_mensagem_marketing_ou_bloqueio(
        self, assunto: str, corpo: str, corpo_ou_texto_completo: str = ""
    ) -> bool:
        """Verifica se o email é lixo por conteúdo (newsletter, marketing, UTM)."""
        fil = self.filtros_lixo
        if not fil:
            return False
        blob = f"{assunto or ''}\n{corpo or ''}\n{corpo_ou_texto_completo or ''}"[:200000]
        if not blob.strip():
            return False
        for pat in fil.get("por_conteudo_regex", []) or []:
            p = (pat or "").strip()
            if p:
                try:
                    if re.search(p, blob, re.IGNORECASE | re.DOTALL):
                        return True
                except re.error:
                    continue
        return False
    
    def identificar_cadoc(self, texto: str, assunto: str = "") -> Tuple[str, Optional[str]]:
        """
        Identifica qual tipo de relatório
        Assunto com «S5» como palavra (ex.: ECSA (S5) - Encaminhar o COS4010…): **S5** antes de
        códigos/termos no corpo — evita DLO só por COS4010/4016 citados.
        CORREÇÃO CASOS 8, 10, 17, 19: Prioridade para códigos numéricos
        Assunto com DLO (sem DDR): prioriza 2061+ sobre 2011 — evita citacao antiga
        \"DDR 2011\" em corpo/Outlook vencer \"DLO\" no assunto (ex.: Planner DLO - DEZEMBRO).
        Código 2061 aceita sufixo tipo 2061_12 (\\b2061\\b não pegava 2061_12).
        """
        texto_upper = texto.upper()
        assunto_u = (assunto or "").upper()
        if assunto and re.search(r"(?i)\bS5\b", assunto):
            return "S5", "S5"

        # #PF30: Balancete de Câmbio → DDR_2011 (posição cambial, insumo do DDR)
        # Balancete sem "câmbio" → DLO_2061 (balanço patrimonial, insumo do DLO)
        if assunto and re.search(r"(?i)\bbalancete\s+de\s+c[aâ]mbio\b", assunto):
            return "DDR_2011", "balancete de câmbio"
        if assunto and re.search(r"(?i)\bbalancete\b", assunto):
            return "DLO_2061", "balancete"

        # Consulta sobre norma regulatória → SUPORTE (é uma dúvida, não envio de relatório)
        # "Norma BCB", "IN BCB" e "Instrução Normativa" no assunto indicam pergunta, não relatório.
        if assunto and re.search(r"(?i)\bnorma\s+bcb\b|\bIN\s+BCB\b|\binstrução\s+normativa\b|\binstrucao\s+normativa\b", assunto):
            return "SUPORTE", "consulta norma BCB"

        # #PF23 Situação 2: se o assunto sozinho identifica exatamente 1 CADOC, usar esse.
        # Evita que citações de CADOCs no corpo (histórico, assinatura) sobreponham o assunto.
        if assunto:
            _cadocs_no_assunto = []
            _codigos_sit2 = [('2011','DDR_2011'),('2060','DRM_2060'),('2061','DLO_2061'),
                             ('2062','DLI_2062'),('2160','DRL_2160'),('4111','4111')]
            for _cod, _cad in _codigos_sit2:
                if re.search(r'(?<![0-9])' + _cod + r'(?![0-9])', assunto_u):
                    _cadocs_no_assunto.append((_cod, _cad))
            # Termos textuais no assunto
            if not _cadocs_no_assunto:
                for _cad, _cfg in self.deteccao_cadoc.items():
                    for _termo in _cfg.get("termos_obrigatorios", []):
                        if re.search(r'\b' + re.escape(_termo.upper()) + r'\b', assunto_u):
                            _cadocs_no_assunto.append((_termo, _cad))
                            break
            if len(_cadocs_no_assunto) == 1:
                return _cadocs_no_assunto[0][1], _cadocs_no_assunto[0][0]

        prefer_dlo_no_assunto = bool(re.search(r'\bDLO\b', assunto_u)) and not re.search(r'\bDDR\b', assunto_u)

        # PRIORIDADE 1: Códigos numéricos — ordem importa quando há vários no mesmo texto
        codigo_cadoc_ordem_default = [
            ('2011', 'DDR_2011'),
            ('2060', 'DRM_2060'),
            ('2061', 'DLO_2061'),
            ('2062', 'DLI_2062'),
            ('2160', 'DRL_2160'),
            ('4111', '4111'),
        ]
        if prefer_dlo_no_assunto:
            codigo_cadoc_ordem = [
                ('2061', 'DLO_2061'),
                ('2062', 'DLI_2062'),
                ('2160', 'DRL_2160'),
                ('2060', 'DRM_2060'),
                ('4111', '4111'),
                ('2011', 'DDR_2011'),
            ]
        else:
            codigo_cadoc_ordem = codigo_cadoc_ordem_default

        for codigo, cadoc in codigo_cadoc_ordem:
            # Não-digitos nas bordas: "2061_12/2024" e "DDR 2011" sem confundir 12011
            if re.search(r'(?<![0-9])' + codigo + r'(?![0-9])', texto_upper):
                return cadoc, codigo
        
        # PRIORIDADE 2: Termos textuais
        for cadoc, config in self.deteccao_cadoc.items():
            for termo in config.get("termos_obrigatorios", []):
                if re.search(r'\b' + re.escape(termo.upper()) + r'\b', texto_upper):
                    return cadoc, termo
        
        return "OUTROS", None
    
    def obter_tipo_esperado(self, cadoc: str) -> str:
        """Retorna 'DIARIA' ou 'MENSAL' baseado no cadoc"""
        config = self.deteccao_cadoc.get(cadoc, {})
        return config.get("tipo_data_esperada", "DIARIA")

    def eh_retorno_bacen(self, assunto: str) -> bool:
        """Verifica se o assunto indica comunicação do BC sobre qualidade (indício, crítica, erro, reiteração, etc.)."""
        if not assunto or not isinstance(assunto, str):
            return False
        al = assunto.lower().strip()
        termos = self.retorno_bacen.get("termos_assunto", [])
        return any(t in al for t in termos)

    def texto_mandatorio_retorno_bacen_critica_e_documento(self, assunto: str, corpo: str) -> bool:
        """
        Assunto + corpo: se há sinal de rejeição/crítica do BC («crítica», «retorno bacen», «rejeitado»,
        «recusado», «aviso bacen») **e** menção a documento regulatório (DDR, 4111, DLO, DLI, DRL, RA,
        DRM ou códigos 2060/2061/2062/2160), força tipificação Retorno Bacen — evita classificar só como
        DLO/DLI quando a queixa está no texto (ex.: RE: DLO_2061… com «arquivo rejeitado» no corpo).
        """
        blob = f"{assunto or ''}\n{corpo or ''}"
        if not blob.strip():
            return False
        low = blob.lower()
        tem_sinal_bc = (
            bool(re.search(r"(?i)\bcr[ií]tica\b", blob))
            or "retorno do bacen" in low
            or "retorno bacen" in low
            or bool(re.search(r"(?i)\brejeit(ado|ados|ada|adas)\b", blob))
            or bool(re.search(r"(?i)\brecus(ado|ada|a)\b", blob))
            or "aviso bacen" in low
            or "avisos do bacen" in low
        )
        if not tem_sinal_bc:
            return False
        up = blob.upper()
        # DLO_2061, DLI_2062, tokens DDR/DRM/RA e códigos numéricos alinhados ao identificar_cadoc
        padroes_doc = (
            r"(?<![A-Z0-9])DLO(?![a-z])",
            r"(?<![A-Z0-9])DLI(?![a-z])",
            r"(?<![A-Z0-9])DRL(?![a-z])",
            r"\bDDR\b",
            r"(?<![A-Z0-9])DRM(?![a-z])",
            r"(?<![0-9])4111(?![0-9])",
            r"(?<![0-9])2060(?![0-9])",
            r"(?<![0-9])2061(?![0-9])",
            r"(?<![0-9])2062(?![0-9])",
            r"(?<![0-9])2160(?![0-9])",
            r"\bRA\b",
        )
        return any(re.search(p, up) for p in padroes_doc)

    def tem_indicador_rd_ddr(self, texto: str) -> bool:
        """
        RD_MOEDA, RD_MOEDAS ou RD_<sufixo> (ex.: RD_REMUNERA) no assunto/corpo indicam DDR (Risk Driver),
        não Retorno Bacen — evita classificar só por 'erro' no assunto quando o caso é relatório diário RD_*.
        """
        if not texto or not isinstance(texto, str):
            return False
        t = texto.upper()
        # RD_MOEDA(S) e demais RD_* com pelo menos 2 caracteres após RD_
        return bool(re.search(r"\bRD_[A-Z0-9]{2,}\b", t))

    def assunto_indica_suporte_erro_tela_ou_acesso(self, assunto: str) -> bool:
        """
        "Erro" no assunto também casa com TIPIFICACAO_RETORNO_BACEN, mas frases como
        "erro na tela" / "erro ao acessar" são chamados de suporte (cliente/4111 na UI),
        não comunicação do BC sobre qualidade de documento.

        Padrões adicionais (2026-05): erros operacionais no sistema Finaud — importação,
        cálculo, cpad, usuário, acesso, realização — são suporte, não retorno BACEN.
        """
        if not assunto or not isinstance(assunto, str):
            return False
        a = assunto.lower()
        _PADROES_SUPORTE = [
            r"\berro\s+na\s+tela\b",           # erro na tela
            r"\berro\s+ao\s+acess",             # erro ao acessar
            r"\berro\s+(ao\s+)?(import)",       # erro importação / erro ao importar
            r"\berro\s+importa",                # erro importação (sem "ao")
            r"\berro\s*[-–]?\s*c[aá]lculo",     # erro cálculo / erro - cálculo / erro – cálculo
            r"\berro\s+cpad\b",                 # erro cpad
            r"\berro\s+usu[aá]rio",             # erro usuário
            r"\berro\s+(ao\s+|para\s+)?realizar",  # erro ao realizar / erro para realizar
            r"\berro\s+(ao\s+|na\s+)?gera",     # erro ao gerar / erro na geração
            r"\berro\s+de\s+login\b",           # erro de login
            r"\berro\s+de\s+acesso\b",          # erro de acesso
        ]
        return any(re.search(p, a) for p in _PADROES_SUPORTE)

    def assunto_indica_erro_ou_erros_dlo_retorno_bacen(self, assunto: str) -> bool:
        """
        Assunto com «erro DLO» ou «erros DLO» (singular/plural): comunicação típica de rejeição/crítica
        no CRD sobre o DLO — tipificar como Retorno Bacen (D+5 úteis), alinhado ao operacional.
        """
        if not assunto or not isinstance(assunto, str):
            return False
        return bool(re.search(r"(?i)\berros?\s+dlo\b", assunto))

    def assunto_indice_basileia_suporte(self, assunto: str) -> bool:
        """
        Assunto com termos que indicam suporte técnico, análise ou ajuste interno —
        força SUPORTE com prazo D+5 úteis mesmo que o corpo mencione CADOCs regulatórios.
        Padrões adicionados em #PF30 (2026-06-09): RWACPAD, RWAJUR, teste de estresse,
        cálculo de basileia, edição nas contas, direcionamento de demandas, painel Risk Driver.
        """
        if not assunto or not isinstance(assunto, str):
            return False
        a = assunto.lower()
        _PADROES = [
            r"\b[íi]ndice\s+basil[eé]ia\b",        # índice basileia (padrão original)
            r"\bcalculo\s+d[ae]\s+basil[eé]ia\b",   # cálculo de basileia
            r"\bbasil[eé]ia\b",                      # basileia sozinho no assunto
            r"\brwacpad\b",                          # RWACPAD
            r"\brwajur\b",                           # RWAJUR1/RWAJUR3
            r"\bteste\s+de\s+estresse\b",            # teste de estresse
            r"\bpainel\s+teste\b",                   # painel teste de estresse
            r"\bedi[cç][aã]o\s+nas\s+contas\b",      # edição nas contas
            r"\bdirecionamento\s+das?\s+demandas\b",  # direcionamento das demandas
            r"\batualizar\s+extrato\b",              # atualizar extrato do fundo
            r"\bstress\s+test\b",                    # stress test
        ]
        return any(re.search(p, a) for p in _PADROES)
    
    def assunto_contem_marca_drsac(self, assunto: str) -> bool:
        """
        Assunto com a marca «DRSAC» (ex.: fios [Traders] DRSAC, compliance / Res. 4557) —
        categoria DRSAC (prazo alinhado a SUPORTE) antes de identificar_cadoc, para não
        classificar como DDR_2011 por menção a «TVM» no corpo.
        """
        if not assunto or not isinstance(assunto, str):
            return False
        return bool(re.search(r"(?i)\bDRSAC\b", assunto))

    def texto_indica_6209(self, assunto: str, corpo: str) -> bool:
        """CADOC 6209: termo '6209' no assunto ou corpo — Pagamentos de Varejo (trimestral)."""
        blob = f"{assunto or ''} {corpo or ''}"
        return bool(re.search(r"\b6209\b", blob))

    def texto_indica_forcapital(self, assunto: str, corpo: str) -> bool:
        """
        FORCAPITAL: palavras-chave no assunto ou no texto da mensagem (após corte de citação).
        """
        blob = f"{assunto or ''} {corpo or ''}"
        if not isinstance(blob, str) or not blob.strip():
            return False
        if re.search(r"(?i)\bFORCAPITAL\b", blob):
            return True
        if re.search(r"(?i)projeção", blob):
            return True
        if re.search(r"(?i)\bprojecao\b", blob):
            return True
        return False

    def validar_data_para_contexto(self, dt: datetime, formato_original: str,
                                   contexto_pre: str, tipo_esperado: str, is_intervalo: bool = False,
                                   contexto_pos: str = "") -> bool:
        """
        Valida se a data encontrada é compatível com o tipo de relatório.
        contexto_pos: texto após a data — "?" indica pergunta (universal, cenários desconhecidos).
        """
        # FILTRO DE ANO (CORREÇÃO 4): Rejeita datas muito antigas ou futuras
        _ano_atual = datetime.now().year
        if dt.year < (_ano_atual - 2) or dt.year > (_ano_atual + 2):
            return False
        
        # EXCEÇÃO PARA INTERVALOS (CORREÇÃO 2): Sempre aceita
        if is_intervalo:
            return True
        
        # Sinal universal de pergunta: "?" após a data (qualquer redação)
        if contexto_pos and "?" in contexto_pos[:20]:
            return False
        
        contexto_lower = contexto_pre.lower()
        
        # FILTRO CRÍTICO (CASO 21): Rejeita datas em contextos explicativos
        tem_contexto_explicativo = any(exp in contexto_lower for exp in self.CONTEXTOS_EXPLICATIVOS)
        if tem_contexto_explicativo:
            return False
        
        # Rejeita datas em perguntas/hipóteses (ex.: "seria a remessa DLO jan/2026?")
        # Prioriza afirmações (ex.: "Remessa de dezembro/2025, segue documento")
        tem_pergunta = any(p in contexto_lower for p in self.CONTEXTOS_INDICAM_PERGUNTA)
        if tem_pergunta:
            return False
        
        # Se o formato é mensal, só aceita para relatórios mensais
        if re.match(r'\d{1,2}/\d{4}', formato_original) or \
           re.search(r'[a-z]+\s*/?\s*\d{2,4}', formato_original, re.IGNORECASE):
            return tipo_esperado == "MENSAL"
        
        # Para datas completas
        if tipo_esperado == "DIARIA":
            tem_ancora_diaria = self._match_anchors_in_context(self.ANCORAS_DIARIAS, contexto_lower)
            tem_ancora_mensal = self._match_anchors_in_context(self.ANCORAS_MENSAIS, contexto_lower)
            tem_contexto_negativo = any(palavra in contexto_lower for palavra in self.CONTEXTOS_NEGATIVOS)
            
            # Âncora positiva tem prioridade
            if tem_ancora_diaria:
                return True
            
            # Se tem negativo mas nenhuma âncora, rejeita
            if tem_contexto_negativo and not tem_ancora_diaria:
                return False
            
            if tem_ancora_mensal:
                return False
            
            # Default com filtro negativo
            return not tem_contexto_negativo
        
        elif tipo_esperado == "MENSAL":
            tem_ancora_mensal = self._match_anchors_in_context(self.ANCORAS_MENSAIS, contexto_lower)
            # Para mensal, aceita último dia do mês
            return tem_ancora_mensal or dt.day >= 28
        
        return False


# ============================================================================
# CLASSE: CALCULADOR DE PRAZOS
# ============================================================================

class CalculadorPrazos:
    """CAMADA 3: Calcula prazos baseado nas regras"""
    
    def __init__(self, regras_json):
        self.regras_prazos = regras_json.get("documentos_regulatorios_prazos", {})
        self.feriados = []
        for d in regras_json.get("feriados_nacionais", []):
            try:
                self.feriados.append(datetime.strptime(d, "%Y-%m-%d").date())
            except:
                pass
    
    def eh_dia_util(self, data: datetime) -> bool:
        return data.weekday() < 5 and data.date() not in self.feriados
    
    def adicionar_dias_uteis(self, dt_base: datetime, dias_uteis: int) -> datetime:
        data_atual = dt_base
        contagem = 0
        while contagem < dias_uteis:
            data_atual += timedelta(days=1)
            if self.eh_dia_util(data_atual):
                contagem += 1
        return data_atual
    
    def calcular_prazo_limite(self, dt_base: datetime, cadoc: str) -> str:
        if cadoc == "SUPORTE_GERAL":
            cadoc = "SUPORTE"
        config = self.regras_prazos.get(cadoc, {"prazo": "D+3_UTIL"})
        regra = config.get("prazo", "D+3_UTIL")
        
        # D+N_UTIL
        if "D+" in regra and "UTIL" in regra and "MES" not in regra:
            dias = int(re.search(r'\d+', regra).group())
            prazo = self.adicionar_dias_uteis(dt_base, dias)
            return prazo.strftime("%d/%m/%Y")
        
        # D+N_UTIL_MES_SEGUINTE
        if "MES_SEGUINTE" in regra:
            primeiro_dia_prox_mes = datetime(dt_base.year, dt_base.month, 1) + timedelta(days=32)
            primeiro_dia_prox_mes = primeiro_dia_prox_mes.replace(day=1)
            dias = int(re.search(r'\d+', regra).group())
            prazo = self.adicionar_dias_uteis(primeiro_dia_prox_mes, dias)
            return prazo.strftime("%d/%m/%Y")
        
        # DIA_N_SEGUNDO_MES
        if "SEGUNDO_MES" in regra:
            mes_alvo = dt_base.month + 2
            ano_alvo = dt_base.year
            if mes_alvo > 12:
                mes_alvo -= 12
                ano_alvo += 1
            dia = int(re.search(r'\d+', regra).group())
            prazo = datetime(ano_alvo, mes_alvo, dia)
            return prazo.strftime("%d/%m/%Y")

        # ULTIMO_DU_MES_SUBSEQUENTE_TRIMESTRE (CADOC 6209 — trimestral)
        # Encontra o fim do trimestre da data-base, depois calcula o último DU do mês seguinte.
        if "TRIMESTRE" in regra:
            # Fim do trimestre civil que contém dt_base
            trim_fim_mes = ((dt_base.month - 1) // 3 + 1) * 3  # 3, 6, 9 ou 12
            import calendar
            ultimo_dia_trim = calendar.monthrange(dt_base.year, trim_fim_mes)[1]
            # Mês subsequente ao trimestre
            mes_sub = trim_fim_mes + 1
            ano_sub = dt_base.year
            if mes_sub > 12:
                mes_sub = 1
                ano_sub += 1
            ultimo_dia_sub = calendar.monthrange(ano_sub, mes_sub)[1]
            # Recua até encontrar dia útil
            candidato = datetime(ano_sub, mes_sub, ultimo_dia_sub)
            while candidato.weekday() >= 5 or candidato.date() in self.feriados:
                candidato -= timedelta(days=1)
            return candidato.strftime("%d/%m/%Y")

        # Fallback
        prazo = self.adicionar_dias_uteis(dt_base, 3)
        return prazo.strftime("%d/%m/%Y")


# ============================================================================
# CLASSE: ORQUESTRADOR PRINCIPAL
# ============================================================================

class Oraculo:
    """Orquestrador principal - integra todas as camadas com correções"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        if not ARQUIVO_REGRAS:
            raise FileNotFoundError("Regras JSON não encontradas.")
        
        with open(ARQUIVO_REGRAS, 'r', encoding='utf-8') as f:
            regras_raiz = json.load(f).get("O_QUE_ESTA_SENDO_ANALISADO", {})
        
        # Inicializa componentes
        feriados_datas = []
        for d in regras_raiz.get("feriados_nacionais", []):
            try:
                feriados_datas.append(datetime.strptime(d, "%Y-%m-%d").date())
            except ValueError:
                print(f"  [!] Feriado com formato inválido ignorado: {d!r}")
        
        self.normalizador = NormalizadorDatas(ano_padrao=datetime.now().year, feriados=feriados_datas)
        self.validador = ValidadorContextual(regras_raiz)
        self.calculador = CalculadorPrazos(regras_raiz)
        self.filtro_historico = FiltroHistorico()
        self.filtro_data = FiltroPorData(DATA_COLETA_INICIO, DATA_LIMITE_EXCLUIR)
    
    def log(self, nivel: str, mensagem: str):
        if self.verbose:
            print(f"  [{nivel.upper()}] {mensagem}")
    
    def _priorizar_por_ancora(self, candidatas: List[Tuple], tipo_esperado: str) -> List:
        """Quando múltiplas datas: preferir as que têm âncora no contexto (cenários desconhecidos)."""
        if len(candidatas) <= 1:
            return [c[0] for c in candidatas]
        ancoras = (self.validador.ANCORAS_MENSAIS if tipo_esperado == "MENSAL" 
                   else self.validador.ANCORAS_DIARIAS)
        com_ancora = []
        sem_ancora = []
        for dt, ctx in candidatas:
            ctx_l = (ctx or "").lower()
            if self.validador._match_anchors_in_context(ancoras, ctx_l):
                com_ancora.append(dt)
            else:
                sem_ancora.append(dt)
        if com_ancora and sem_ancora:
            self.log("PRIORIZA", f"Prefere {len(com_ancora)} datas com âncora sobre {len(sem_ancora)} sem")
            return com_ancora
        return [c[0] for c in candidatas]
    
    def processar_email(self, item: dict) -> dict:
        """Processa um email e retorna a análise completa"""
        id_item = item.get('id', 'N/A')
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"PROCESSANDO ID: {id_item}")
            print(f"{'='*60}")
        
        # FILTRO CRÍTICO: Verifica data do email (CASO 10, 12, 13, 16)
        data_email_str = item.get('data_email', '')
        assunto = item.get('assunto', '')
        remetente = item.get('remetente', '')
        corpo_bruto = item.get('corpo_texto') or item.get('corpo', '')
        retorno_bacen = self.validador.eh_retorno_bacen(assunto)
        if not retorno_bacen:
            retorno_bacen = self.validador.texto_mandatorio_retorno_bacen_critica_e_documento(
                assunto, corpo_bruto
            )
            if retorno_bacen:
                self.log("RETORNO_BACEN", "Tipificação por corpo: critica/retorno bacen + documento (DLO/DDR/…) — mandatório")
        if not retorno_bacen and self.validador.assunto_indica_erro_ou_erros_dlo_retorno_bacen(assunto):
            retorno_bacen = True
            self.log("RETORNO_BACEN", "Tipificação por assunto: erro/erros DLO → Retorno Bacen")
        # RD_MOEDA / RD_* (Risk Driver): prioridade DDR — não Retorno Bacen só por "erro" no assunto
        if retorno_bacen and self.validador.tem_indicador_rd_ddr(f"{assunto} {corpo_bruto}"):
            retorno_bacen = False
            self.log("INFO", "Retorno Bacen suprimido: indicador RD_MOEDA/RD_* (classificar como DDR)")
        # Erro de tela/acesso (UI): não é retorno BC sobre documento — mesmo com "erro" nos termos do JSON
        if retorno_bacen and self.validador.assunto_indica_suporte_erro_tela_ou_acesso(assunto):
            retorno_bacen = False
            self.log("INFO", "Retorno Bacen suprimido: assunto indica suporte (erro na tela / acesso)")
        if not self.filtro_data.email_esta_no_periodo(data_email_str):
            self.log("FILTRO", f"Email fora do período [{DATA_COLETA_INICIO} a {DATA_LIMITE_EXCLUIR})")
            return {"exibir_card": False, "cadoc": "FILTRADO_POR_DATA", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}

        if self.verbose:
            print(f"ASSUNTO: {assunto[:100]}{'...' if len(assunto) > 100 else ''}")

        # INTERNO: FogBugz, Risk Driver, Leiautes, etc. — guardados para consulta, nunca vão à triagem
        if self.validador.eh_email_interno(remetente, assunto):
            self.log("INTERNO", f"Email interno: {assunto[:80]}")
            return {
                "exibir_card": False,
                "cadoc": "INTERNO",
                "lista_prazos": [],
                "tipo_painel": "",
                "retorno_bacen": retorno_bacen
            }

        # FILTRO: Verifica se deve ignorar por assunto (CASOS 5, 18)
        if self.validador.eh_email_lixo_por_remetente(remetente):
            self.log("FILTRO", f"Remetente na lista de lixo: {remetente}")
            return {"exibir_card": False, "cadoc": "IGNORADO", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}

        if self.validador.deve_ignorar_assunto(assunto):
            self.log("FILTRO", "Assunto está na lista de ignorar")
            return {"exibir_card": False, "cadoc": "IGNORADO", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}

        # CORREÇÃO CRÍTICA: Remove histórico ANTES de extrair datas
        corpo = self.filtro_historico.extrair_mensagem_atual(corpo_bruto)

        if self.validador.deve_ignorar_mensagem_marketing_ou_bloqueio(assunto, corpo, corpo_bruto):
            self.log("FILTRO", "E-mail de publicidade / newsletter (mapeamento: corpo, UTM ou padrão)")
            return {"exibir_card": False, "cadoc": "IGNORADO", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        # RETORNO BACEN: sempre D+3 úteis a partir da data do e-mail (documentos_regulatorios_prazos.RETORNO_BACEN)
        if retorno_bacen:
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo_str = self.calculador.calcular_prazo_limite(data_email_dt, "RETORNO_BACEN")
                self.log("RETORNO_BACEN", f"cadoc=RETORNO_BACEN D+3_UTIL {data_email_dt.strftime('%d/%m/%Y')} → {prazo_str}")
                return {
                    "exibir_card": True,
                    "cadoc": "RETORNO_BACEN",
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo_str,
                        "cadoc": "RETORNO_BACEN",
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": True,
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar RETORNO_BACEN: {e}")
                return {"exibir_card": False, "cadoc": "RETORNO_BACEN", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": True}
        
        # Assunto «Índice Basileia»: SUPORTE (D+5 úteis), independente de menções DLO/COS no texto citado
        if self.validador.assunto_indice_basileia_suporte(assunto):
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo = self.calculador.calcular_prazo_limite(data_email_dt, "SUPORTE")
                self.log("INFO", "Assunto Índice Basileia → SUPORTE (D+5 úteis)")
                return {
                    "exibir_card": True,
                    "cadoc": "SUPORTE",
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo,
                        "cadoc": "SUPORTE"
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": retorno_bacen
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar SUPORTE (Índice Basileia): {e}")
                return {"exibir_card": False, "cadoc": "SUPORTE", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        # Assunto com marca DRSAC — categoria própria (D+5 úteis, como SUPORTE); não DDR por TVM no corpo
        if self.validador.assunto_contem_marca_drsac(assunto):
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo = self.calculador.calcular_prazo_limite(data_email_dt, "DRSAC")
                self.log("INFO", "Assunto com DRSAC → categoria DRSAC (D+5 úteis)")
                return {
                    "exibir_card": True,
                    "cadoc": "DRSAC",
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo,
                        "cadoc": "DRSAC"
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": retorno_bacen
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar DRSAC: {e}")
                return {"exibir_card": False, "cadoc": "DRSAC", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}

        # CADOC 6209: termo "6209" no assunto ou corpo — Pagamentos de Varejo (trimestral)
        if self.validador.texto_indica_6209(assunto, corpo):
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo = self.calculador.calcular_prazo_limite(data_email_dt, "6209")
                self.log("INFO", "Termo 6209 → categoria 6209 (trimestral)")
                return {
                    "exibir_card": True,
                    "cadoc": "6209",
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo,
                        "cadoc": "6209"
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": retorno_bacen
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar 6209: {e}")
                return {"exibir_card": False, "cadoc": "6209", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}

        # FORCAPITAL: palavras-chave (assunto ou corpo) antes de códigos/termos de relatório
        if self.validador.texto_indica_forcapital(assunto, corpo):
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo = self.calculador.calcular_prazo_limite(data_email_dt, "FORCAPITAL")
                self.log("INFO", "FORCAPITAL / PROJEÇÃO → categoria FORCAPITAL (D+5 úteis)")
                return {
                    "exibir_card": True,
                    "cadoc": "FORCAPITAL",
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo,
                        "cadoc": "FORCAPITAL"
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": retorno_bacen
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar FORCAPITAL: {e}")
                return {"exibir_card": False, "cadoc": "FORCAPITAL", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        # Identifica tipo de relatório (busca em assunto + corpo + nomes de anexos; assunto desambigua DLO vs DDR em citações)
        nomes_anexos = " ".join(a.get("nome_original", "") for a in item.get("anexos_detectados") or [])
        texto_completo = f"{assunto} {corpo} {nomes_anexos}"
        cadoc, termo = self.validador.identificar_cadoc(texto_completo, assunto)
        # Mencionar "4111" no assunto não é envio de relatório — erro na tela → SUPORTE (D+5)
        if self.validador.assunto_indica_suporte_erro_tela_ou_acesso(assunto):
            cadoc, termo = "OUTROS", None
        
        if cadoc == "OUTROS":
            # SUPORTE: suporte genérico, prazo 5 dias úteis (data do email)
            self.log("INFO", "Não identificado como relatório monitorado → SUPORTE (D+5 úteis)")
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo = self.calculador.calcular_prazo_limite(data_email_dt, "SUPORTE")
                return {
                    "exibir_card": True,
                    "cadoc": "SUPORTE",
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo,
                        "cadoc": "SUPORTE"
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": retorno_bacen
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar SUPORTE: {e}")
                return {"exibir_card": False, "cadoc": "SUPORTE", "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        self.log("CADOC", f"Identificado: {cadoc} (termo: '{termo}')")
        
        # CASO ESPECIAL: SUPORTE, DRSAC, FORCAPITAL (inclui ex-gatilhos SUPORTE_GERAL no JSON) e S5: data do email
        if cadoc in ("SUPORTE", "S5", "DRSAC", "FORCAPITAL", "6209"):
            try:
                data_email_dt = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
                prazo = self.calculador.calcular_prazo_limite(data_email_dt, cadoc)
                self.log(cadoc, f"Usando data do email: {data_email_dt.strftime('%d/%m/%Y')}")
                self.log("PRAZO", f"{data_email_dt.strftime('%d/%m/%Y')} → {prazo}")
                
                return {
                    "exibir_card": True,
                    "cadoc": cadoc,
                    "lista_prazos": [{
                        "data_base": data_email_dt.strftime("%d/%m/%Y"),
                        "prazo_limite": prazo,
                        "cadoc": cadoc
                    }],
                    "tipo_painel": "REGULATORIO",
                    "retorno_bacen": retorno_bacen
                }
            except Exception as e:
                self.log("ERRO", f"Falha ao processar {cadoc}: {e}")
                return {"exibir_card": False, "cadoc": cadoc, "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        # Descobre tipo de data esperado
        tipo_esperado = self.validador.obter_tipo_esperado(cadoc)
        self.log("TIPO", f"Tipo de data esperado: {tipo_esperado}")
        
        # BUSCA PRIORITÁRIA: Assunto primeiro, depois corpo.
        # Para relatórios MENSAL (ex.: DLO_2061, COS): se o assunto tiver data de competência válida
        # (ex.: "COS 12 2025" → 31/12/2025), usa só o assunto e não busca no corpo; assim evita
        # datas de cabeçalho ("Enviada em: 12 de fevereiro de 2026") ou outras do corpo. Outros
        # relatórios em que o assunto não tenha data continuam usando o corpo.
        # data_referencia: data do email para inferir ano em "mês sozinho" (ex.: fev/2026 + dezembro → dez/2025)
        data_referencia = None
        try:
            data_referencia = parsedate_to_datetime(data_email_str).replace(tzinfo=None)
        except Exception:
            pass
        
        todas_datas = []
        
        if assunto.strip():
            datas_assunto = self.normalizador.extrair_todas_datas(assunto, data_referencia)
            if datas_assunto:
                self.log("FONTE", f"✓ Encontrou {len(datas_assunto)} datas no ASSUNTO")
                todas_datas = datas_assunto
            else:
                self.log("FONTE", "✗ Nenhuma data no assunto, buscando no CORPO...")
        
        if not todas_datas and corpo.strip():
            datas_corpo = self.normalizador.extrair_todas_datas(corpo, data_referencia)
            if datas_corpo:
                self.log("FONTE", f"✓ Encontrou {len(datas_corpo)} datas no CORPO")
                todas_datas = datas_corpo
        
        self.log("EXTRAÇÃO", f"{len(todas_datas)} datas brutas encontradas")
        
        # CASO 17: Se não achou data na mensagem atual, busca no corpus de TODAS as mensagens da thread
        # Ex.: "Erro DLO" — 1ª msg sem data; 2ª (Andrea) "jan/2026"; 3ª (Thaiana) "dezembro/2025"
        if not todas_datas:
            corpus_thread = item.get("_corpus_thread") or ""
            if corpus_thread.strip():
                self.log("FONTE", "Buscando datas no corpus da THREAD (todas as mensagens)...")
                datas_thread = self.normalizador.extrair_todas_datas(corpus_thread, data_referencia)
                if datas_thread:
                    self.log("FONTE", f"✓ Encontrou {len(datas_thread)} datas no corpus da thread")
                    todas_datas = datas_thread
            if not todas_datas:
                # FALLBACK: usa a data de envio do e-mail quando não há data no conteúdo
                # Ex.: Guru CTVM "Informações Diárias" — corpo só tem "Segue em anexo: 4111... 2011 (DDR)."
                if data_referencia:
                    self.log("INFO", f"Nenhuma data no conteúdo — usando data de envio do e-mail como fallback: {data_referencia.strftime('%d/%m/%Y')}")
                    todas_datas = [(data_referencia, data_referencia.strftime("%d/%m/%Y"), "data_envio", False)]
                else:
                    self.log("INFO", "Nenhuma data encontrada na thread do dia")
                    return {"exibir_card": False, "cadoc": cadoc, "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        # FILTRO DE QUANTIDADE (CORREÇÃO 3): Detecta listas/tabelas de competências
        # Se encontrou muitas datas mensais, provavelmente é lista de referência
        datas_mensais = [d for d in todas_datas if d[3] is False and  # não é intervalo
                         (re.match(r'\d{1,2}/\d{4}', d[1]) or 
                          re.search(r'[a-z]+.*\d{2,4}', d[1], re.IGNORECASE))]
        
        if tipo_esperado == "MENSAL" and len(datas_mensais) >= 8:
            self.log("FILTRO", f"Detectadas {len(datas_mensais)} competências - parece lista/tabela, não data base")
            return {"exibir_card": False, "cadoc": cadoc, "lista_prazos": [], "tipo_painel": "", "retorno_bacen": retorno_bacen}
        
        # Valida cada data; guarda (dt, ctx) para priorização
        candidatas = []
        for t in todas_datas:
            dt, fmt, ctx = t[0], t[1], t[2]
            is_intervalo = t[3]
            ctx_pos = t[4] if len(t) >= 5 else ""
            if self.validador.validar_data_para_contexto(dt, fmt, ctx, tipo_esperado, is_intervalo, ctx_pos):
                self.log("ACEITA", f"✓ {dt.strftime('%d/%m/%Y')} (formato: {fmt})")
                candidatas.append((dt, ctx))
            else:
                self.log("REJEITA", f"✗ {dt.strftime('%d/%m/%Y')} (incompatível com {tipo_esperado})")
        
        # Priorização: quando múltiplas datas, preferir as que têm âncora no contexto (cenários desconhecidos)
        datas_validas = self._priorizar_por_ancora(candidatas, tipo_esperado)
        
        # Calcula prazos (remove duplicatas - CASO 16)
        prazos_finais = []
        for dt in sorted(set(datas_validas)):
            prazo = self.calculador.calcular_prazo_limite(dt, cadoc)
            self.log("PRAZO", f"{dt.strftime('%d/%m/%Y')} → {prazo}")
            prazos_finais.append({
                "data_base": dt.strftime("%d/%m/%Y"),
                "prazo_limite": prazo,
                "cadoc": cadoc
            })
        
        if self.verbose:
            print(f"\nRESUMO: {len(prazos_finais)} prazos gerados para ID {id_item}\n")
        
        return {
            "exibir_card": len(prazos_finais) > 0,
            "tipo_painel": "REGULATORIO" if len(prazos_finais) > 0 else "",
            "cadoc": cadoc,
            "lista_prazos": prazos_finais,
            "retorno_bacen": retorno_bacen
        }


def montar_contatos_origem_destino_para_item(item, map_clientes):
    """
    Define ``contato_origem`` / ``contato_destino`` (lados FINAUD ou CLIENTE) e
    ajusta ``cliente`` / ``responsavel`` quando há encaminhamento interno.

    Regra quando a origem é FINAUD: o **primeiro** endereço no campo **To**
    (excluindo auto-cópia do remetente) é o interlocutor principal. Se for
    domínio Finaud, o envio é **F→F**, mesmo que exista cliente apenas no CC
    (evita classificar Andrea→Rodrigo como F→C por causa de CC).
    """
    cliente, responsavel = identificar_cliente_e_responsavel_completo(item, map_clientes)

    dominios_finaud = map_clientes.get("nossa_equipe", {}).get("dominios", [])
    dominios_ignorar = map_clientes.get("clientes_externos", {}).get("dominios_a_ignorar", [])
    colaboradores_finaud = map_clientes.get("colaboradores_finaud", {})

    remetente_raw = item.get("remetente", "")
    reply_to_raw = item.get("reply_to", "")
    destinatarios_raw = item.get("destinatarios", "")
    cc_raw = item.get("cc", "")

    remetente_email = extrair_email_simples(remetente_raw)
    reply_email = extrair_email_simples(reply_to_raw)

    remetente_real_email = remetente_email
    if reply_email and not eh_email_finaud_check(reply_email, dominios_finaud):
        remetente_real_email = reply_email

    remetente_nome = extrair_nome_pessoa(remetente_raw) or remetente_real_email
    origem_lado = "FINAUD" if eh_email_finaud_check(remetente_real_email, dominios_finaud) else "CLIENTE"

    contato_origem = {
        "lado": origem_lado,
        "nome": remetente_nome,
        "email": remetente_real_email,
    }

    def _parse_contatos_lista(campo):
        lst = []
        if not campo:
            return lst
        for parte in campo.split(","):
            parte = parte.strip()
            em = extrair_email_simples(parte)
            nm = extrair_nome_pessoa(parte)
            if em:
                lst.append((em, nm))
        return lst

    contatos_somente_to = _parse_contatos_lista(destinatarios_raw)
    contatos_dest = contatos_somente_to + _parse_contatos_lista(cc_raw)

    if origem_lado == "CLIENTE":
        email_remetente_original = extrair_email_simples(remetente_raw)
        destino_email = None
        destino_nome = None

        for em, nm in contatos_dest:
            if em == email_remetente_original:
                continue
            if eh_email_finaud_check(em, dominios_finaud):
                destino_email = em
                usuario = em.split("@")[0]
                for chave in [usuario, usuario.replace(".", "_"), usuario.replace(".", "")]:
                    if chave in colaboradores_finaud:
                        destino_nome = colaboradores_finaud[chave]
                        break
                if not destino_nome:
                    destino_nome = nm or em
                break

        if not destino_email:
            destino_email = "suporte@finaud.com.br"
            destino_nome = "Suporte Finaud"

        contato_destino = {
            "lado": "FINAUD",
            "nome": destino_nome,
            "email": destino_email,
        }
    else:
        email_remetente_original = extrair_email_simples(remetente_raw)

        primeiro_to_em = None
        primeiro_to_nm = None
        for em, nm in contatos_somente_to:
            if em == email_remetente_original:
                continue
            primeiro_to_em, primeiro_to_nm = em, nm
            break

        if primeiro_to_em and eh_email_finaud_check(primeiro_to_em, dominios_finaud):
            usuario = primeiro_to_em.split("@")[0]
            destino_finaud_nm = primeiro_to_nm or primeiro_to_em
            for chave in [usuario, usuario.replace(".", "_"), usuario.replace(".", "")]:
                if chave in colaboradores_finaud:
                    destino_finaud_nm = colaboradores_finaud[chave]
                    break
            contato_destino = {
                "lado": "FINAUD",
                "nome": destino_finaud_nm,
                "email": primeiro_to_em,
            }
            partes_corpo = []
            ct = (item.get("corpo_texto") or "").strip()
            if ct:
                partes_corpo.append(ct)
            ch = item.get("corpo_html") or item.get("corpo") or ""
            if ch:
                partes_corpo.append(limpar_html_para_texto(ch))
            corpo_fwd = "\n".join(partes_corpo) if partes_corpo else ""
            ext_em = extrair_primeiro_email_externo_apos_encaminhamento(
                corpo_fwd, dominios_finaud, dominios_ignorar
            )
            mapa_nomes_cli = map_clientes.get("mapeamento_nomes_clientes", {})
            if ext_em:
                dom_ex = extrair_dominio_email(ext_em)
                nome_cli = mapa_nomes_cli.get(dom_ex)
                if not nome_cli:
                    _DOMINIOS_SEM_NOME.add(dom_ex)
                    nome_cli = dom_ex.split(".")[0].capitalize()
                cliente = nome_cli
                responsavel = extrair_nome_remetente_encaminhado(corpo_fwd, ext_em) or nome_cli
            else:
                _inf = _inferir_empresa_de_assunto_ou_fwd(
                    item.get("assunto", ""), corpo_fwd, mapa_nomes_cli, dominios_finaud, dominios_ignorar
                )
                cliente = _inf if _inf else "Encaminhamento interno Finaud"
                responsavel = destino_finaud_nm or "Suporte Finaud"
        else:
            emails_dest = [em for em, _ in contatos_dest]
            cliente_email = encontrar_email_cliente_valido(emails_dest, dominios_finaud, dominios_ignorar)

            if cliente_email:
                destino_email = cliente_email
                destino_nome = ""
                for em, nm in contatos_dest:
                    if em == cliente_email:
                        destino_nome = nm or em
                        break
                if not destino_nome:
                    destino_nome = cliente
                contato_destino = {
                    "lado": "CLIENTE",
                    "nome": destino_nome,
                    "email": destino_email,
                }
            else:
                destino_finaud_em = None
                destino_finaud_nm = None
                for em, nm in contatos_dest:
                    if em == email_remetente_original:
                        continue
                    if eh_email_finaud_check(em, dominios_finaud):
                        destino_finaud_em = em
                        usuario = em.split("@")[0]
                        for chave in [usuario, usuario.replace(".", "_"), usuario.replace(".", "")]:
                            if chave in colaboradores_finaud:
                                destino_finaud_nm = colaboradores_finaud[chave]
                                break
                        if not destino_finaud_nm:
                            destino_finaud_nm = nm or em
                        break
                if destino_finaud_em:
                    contato_destino = {
                        "lado": "FINAUD",
                        "nome": destino_finaud_nm,
                        "email": destino_finaud_em,
                    }
                    partes_corpo = []
                    ct = (item.get("corpo_texto") or "").strip()
                    if ct:
                        partes_corpo.append(ct)
                    ch = item.get("corpo_html") or item.get("corpo") or ""
                    if ch:
                        partes_corpo.append(limpar_html_para_texto(ch))
                    corpo_fwd = "\n".join(partes_corpo) if partes_corpo else ""
                    ext_em = extrair_primeiro_email_externo_apos_encaminhamento(
                        corpo_fwd, dominios_finaud, dominios_ignorar
                    )
                    mapa_nomes_cli = map_clientes.get("mapeamento_nomes_clientes", {})
                    if ext_em:
                        dom_ex = extrair_dominio_email(ext_em)
                        nome_cli = mapa_nomes_cli.get(dom_ex)
                        if not nome_cli:
                            _DOMINIOS_SEM_NOME.add(dom_ex)
                            nome_cli = dom_ex.split(".")[0].capitalize()
                        cliente = nome_cli
                        responsavel = extrair_nome_remetente_encaminhado(corpo_fwd, ext_em) or nome_cli
                    else:
                        _inf = _inferir_empresa_de_assunto_ou_fwd(
                            item.get("assunto", ""), corpo_fwd, mapa_nomes_cli, dominios_finaud, dominios_ignorar
                        )
                        cliente = _inf if _inf else "Encaminhamento interno Finaud"
                        responsavel = destino_finaud_nm or "Suporte Finaud"
                else:
                    destino_email = ""
                    destino_nome = cliente if cliente else "DESCONHECIDO"
                    contato_destino = {
                        "lado": "CLIENTE",
                        "nome": destino_nome,
                        "email": destino_email,
                    }

    # Correção relay suporte@: quando Finaud enviou via relay suporte@finaud.com.br
    # e o cliente é identificado como externo, o email vai para CLIENTE (não F→F).
    # Critério: destino = suporte@finaud.com.br + cliente real (não interno).
    _INTERNO = {"finaud", "encaminhamento interno finaud", "desconhecido", ""}
    if (
        contato_destino.get("lado") == "FINAUD"
        and contato_destino.get("email") == "suporte@finaud.com.br"
        and origem_lado == "FINAUD"
        and (cliente or "").lower() not in _INTERNO
    ):
        contato_destino = {
            "lado": "CLIENTE",
            "nome": cliente,
            "email": "suporte@finaud.com.br",
        }

    return contato_origem, contato_destino, cliente, responsavel


def _analise_preservada_de_email_processado(ep0: dict) -> Optional[dict]:
    """
    Monta o dict ``analise`` a partir de um ``emails_processados`` do 02 anterior,
    para não substituir CADOC/prazos por FILTRADO_POR_DATA quando a data do 01
    cai fora da janela atual do classificador.
    """
    if not isinstance(ep0, dict):
        return None
    oc = (ep0.get("cadoc") or "").strip()
    if not oc or oc in ("FILTRADO_POR_DATA", "IGNORADO", "INTERNO"):
        return None
    return {
        "exibir_card": bool(ep0.get("exibir_card")),
        "cadoc": oc,
        "lista_prazos": list(ep0.get("prazos") or []),
        "tipo_painel": ep0.get("tipo_painel") or "",
        "retorno_bacen": bool(ep0.get("retorno_bacen")),
    }


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def main():
    """Execução principal: carrega 01 e regras, classifica cada e-mail (ou reutiliza no incremental), agrega threads e grava 02_classificação_dados_brutos_gmail_editado.json."""
    from pipeline_watchdog import iniciar_watchdog, processar_com_timeout, salvar_checkpoint, carregar_checkpoint, limpar_checkpoint
    iniciar_watchdog(max_horas=12, nome_script="05_classificar")

    relogio = Cronometro()
    cabecalho(5, "Classificar E-mails Regulatorio", periodo=os.environ.get("DATA_COLETA_INICIO", "--"), modo="INCREMENTAL" if os.environ.get("ORACULO_INCREMENTAL", "").strip().lower() in ("1","true","yes") else "COMPLETO")
    verificar_dependencias("05_classificar", requer=["03_corrigir_anexos", "04_mapear_clientes"])
    global DATA_COLETA_INICIO, DATA_LIMITE_EXCLUIR

    # Carrega 01 primeiro (para inferir período quando rodado standalone)
    try:
        with open(ARQUIVO_ENTRADA, 'r', encoding='utf-8') as f:
            emails = json.load(f)
    except Exception as e:
        print(f"ERRO ao carregar {ARQUIVO_ENTRADA}: {e}")
        return

    # CORREÇÃO DEFINITIVA: quando rodado standalone (env não definido), inferir período dos dados
    # Evita que 04/08 deixem a tela vazia ao usar defaults desatualizados (ex: 21-Jan a 01-Feb)
    if not os.environ.get("DATA_COLETA_INICIO") and not os.environ.get("DATA_LIMITE_EXCLUIR"):
        datas = []
        for e in emails:
            de = e.get("data_email", "")
            if de:
                try:
                    dt = parsedate_to_datetime(de)
                    datas.append(dt.replace(tzinfo=None))
                except Exception:
                    pass
        if datas:
            data_min = min(datas)
            data_max = max(datas)
            data_inicio = data_min - timedelta(days=1)
            data_fim = data_max + timedelta(days=2)
            DATA_COLETA_INICIO = data_inicio.strftime("%d-%b-%Y")
            DATA_LIMITE_EXCLUIR = data_fim.strftime("%d-%b-%Y")
            print(f"Periodo inferido dos dados: {DATA_COLETA_INICIO} ate {DATA_LIMITE_EXCLUIR}")

    if VERBOSE:
        print("\n" + "="*60)
        print("ORÁCULO - VERSÃO 3.1 - LIMPEZA PROFUNDA CORPO_LIMPO (10/02/2026)")
        print("CORREÇÕES: html_para_texto, corpo_profundo_v3, corpo_texto_prioritario, corpo_limpo_nas_threads")
        print("="*60)
        print(f"Período: {DATA_COLETA_INICIO} até {DATA_LIMITE_EXCLUIR}")
        print("="*60 + "\n")
    else:
        print(f"\nClassificação Regulatória — Período: {DATA_COLETA_INICIO} até {DATA_LIMITE_EXCLUIR}")
    
    # Carrega mapeamento de clientes
    global MAPEAMENTO_CLIENTES
    try:
        with open(ARQUIVO_REGRAS, 'r', encoding='utf-8') as f:
            regras_completas = json.load(f)
            MAPEAMENTO_CLIENTES = regras_completas.get('QUEM_ENVIA_E_RECEBE', {})
        if VERBOSE:
            print(f"✅ Mapeamento de clientes carregado")
    except Exception as e:
        print(f"AVISO: Erro ao carregar mapeamento: {e}")
        MAPEAMENTO_CLIENTES = {}
    
    oraculo = Oraculo(verbose=VERBOSE)

    total_emails = len(emails)
    ids_01_atual = {str(e.get("id")) for e in emails if e.get("id") is not None}
    mapa_antigo = {}
    threads_map_inicial = {}
    ids_ja_processados = set()
    if (INCREMENTAL or PRESERVAR_CLASSIFICACAO_FORA_PERIODO) and os.path.exists(ARQUIVO_SAIDA):
        try:
            with open(ARQUIVO_SAIDA, 'r', encoding='utf-8') as f_saida:
                dados_antigos = json.load(f_saida)
            for e in (dados_antigos.get("emails_processados") or []):
                eid = e.get("id")
                if eid is not None:
                    mapa_antigo[str(eid)] = e
            if INCREMENTAL:
                for th in (dados_antigos.get("threads_processadas") or []):
                    th_id = th.get("threadId") or "SEM_THREAD"
                    threads_map_inicial[th_id] = {"threadId": th_id, "mensagens": list(th.get("mensagens") or [])}
                ids_ja_processados = {eid for eid in mapa_antigo if eid in ids_01_atual}
        except Exception as e:
            if VERBOSE:
                print(f"AVISO: falha ao carregar 02 anterior ({e}); incremental/preservação indisponível.")
            mapa_antigo = {}
            threads_map_inicial = {}
            ids_ja_processados = set()

    # Pré-monta corpus por thread (assunto + corpo filtrado de cada msg) para extração de datas em CASO 17
    # Quando uma msg não tem data, busca nas outras mensagens da mesma thread (ex.: Erro DLO)
    # Em modo incremental: reconstrói apenas as threads que têm e-mails novos (as demais não serão
    # reclassificadas, portanto seu corpus é irrelevante). Reduz O(N_total) para O(N_threads_novas).
    _filtro = FiltroHistorico()
    _corpus_por_thread = {}
    if INCREMENTAL and ids_ja_processados:
        _tids_com_novos = {
            e.get("thread_root") or e.get("threadId") or e.get("message_id") or "SEM_THREAD"
            for e in emails
            if str(e.get("id", "")) not in ids_ja_processados
        }
        _emails_para_corpus = [
            e for e in emails
            if (e.get("thread_root") or e.get("threadId") or e.get("message_id") or "SEM_THREAD") in _tids_com_novos
        ]
        print(f"   Corpus incremental: {len(_emails_para_corpus)} e-mails em {len(_tids_com_novos)} threads "
              f"(ignorando {total_emails - len(_emails_para_corpus)} e-mails de threads sem novidade)")
    else:
        _emails_para_corpus = emails
    for e in _emails_para_corpus:
        tid = e.get("thread_root") or e.get("threadId") or e.get("message_id") or "SEM_THREAD"
        corpo_bruto = e.get("corpo_texto") or e.get("corpo") or ""
        corpo_filtrado = _filtro.extrair_mensagem_atual(corpo_bruto)
        asst = (e.get("assunto") or "").strip()
        partes = _corpus_por_thread.get(tid, [])
        partes.append(f"{asst} {corpo_filtrado}".strip())
        _corpus_por_thread[tid] = partes
    for tid, partes in _corpus_por_thread.items():
        _corpus_por_thread[tid] = " ".join(p for p in partes if p)
    if PRESERVAR_CLASSIFICACAO_FORA_PERIODO and not INCREMENTAL and mapa_antigo:
        print(
            f"   Preservação fora do período: {len(mapa_antigo)} e-mail(ns) no 02 anterior "
            f"(ids com data ∉ [{DATA_COLETA_INICIO}, {DATA_LIMITE_EXCLUIR}) reutilizam CADOC/prazos)."
        )
    num_novos = total_emails - len(ids_ja_processados)
    if INCREMENTAL and ids_ja_processados:
        print(f"Total de emails: {total_emails} (incremental: {num_novos} novos, {len(ids_ja_processados)} reutilizados)")
    else:
        print(f"Total de emails: {total_emails}")
    if not VERBOSE:
        print("   (modo resumo — use ORACULO_VERBOSE=1 para ver detalhe por email)")
        # Barra de progresso (atualizada a cada email)
        BARRA_LARGURA = 40
        def _atualizar_barra(atual, total):
            if total <= 0:
                return
            preenchido = int(BARRA_LARGURA * (atual + 1) / total)
            barra = "=" * preenchido + " " * (BARRA_LARGURA - preenchido)
            pct = int(100 * (atual + 1) / total)
            sys.stdout.write(f"\r   [{barra}] {atual + 1}/{total}  {pct}%")
            sys.stdout.flush()
        print("   ", end="")
    
    # ESTRUTURA NOVA DO ARQUIVO DE SAÍDA
    resultado_final = {
        "total_emails": len(emails),
        "emails_processados": [],
        "threads_processadas": [],
        "resumo": {
            "com_prazos": 0,
            "sem_prazos": 0,
            "filtrados": 0
        }
    }
    
    # Índice de threads: em modo incremental, inicia com as threads da saída anterior; senão, vazio.
    threads_map = dict(threads_map_inicial) if threads_map_inicial else {}  # threadId -> {"threadId":..., "mensagens":[...]}

    import time as _time_05
    _t0_05 = _time_05.time()
    _intervalo_prog_05 = max(1, total_emails // 20)  # emite ~20 vezes por execução

    # Checkpoint: retoma do último índice gravado (protege contra interrupções)
    _ckpt = carregar_checkpoint("05_classificar")
    _ckpt_idx_inicio = (_ckpt.get("ultimo_idx", -1) + 1) if isinstance(_ckpt, dict) else 0
    if _ckpt_idx_inicio > 0:
        print(f"[checkpoint] retomando do e-mail {_ckpt_idx_inicio}/{total_emails} (interrupção anterior)", flush=True)

    _timeout_por_email = int(os.environ.get("ORACULO_TIMEOUT_EMAIL", "60"))
    _erros_timeout = 0

    for idx, item in enumerate(emails):
        # Retomada: pula e-mails já processados antes da interrupção
        if idx < _ckpt_idx_inicio:
            continue

        # Progresso estruturado a cada 5% (parseable pelo pipeline_jobs)
        if idx > 0 and idx % _intervalo_prog_05 == 0:
            _el = _time_05.time() - _t0_05
            _eta_s = int((_el / idx) * (total_emails - idx)) if idx else 0
            _eta_m, _eta_sg = _eta_s // 60, _eta_s % 60
            print(f"\n[05] progresso: {idx}/{total_emails} emails | ~{_eta_m}m{_eta_sg:02d}s restantes", flush=True)
            salvar_checkpoint("05_classificar", {"ultimo_idx": idx - 1, "total": total_emails})

        eid = str(item.get("id")) if item.get("id") is not None else None
        # Modo incremental: reutiliza e-mail já classificado (evita reprocessar ~1500 quando só chegaram 10 novos).
        if INCREMENTAL and eid and eid in ids_ja_processados:
            ep_antigo = mapa_antigo.get(eid)
            if ep_antigo:
                resultado_final["emails_processados"].append(ep_antigo)
                if ep_antigo.get("exibir_card"):
                    resultado_final["resumo"]["com_prazos"] += 1
                elif ep_antigo.get("cadoc") in ["FILTRADO_POR_DATA", "IGNORADO"]:
                    resultado_final["resumo"]["filtrados"] += 1
                else:
                    resultado_final["resumo"]["sem_prazos"] += 1
            if not VERBOSE:
                _atualizar_barra(idx, total_emails)
            continue

        tid = item.get("thread_root") or item.get("threadId") or item.get("message_id") or "SEM_THREAD"
        item["_corpus_thread"] = _corpus_por_thread.get(tid, "")
        analise = None
        if (
            PRESERVAR_CLASSIFICACAO_FORA_PERIODO
            and not INCREMENTAL
            and eid
            and eid in mapa_antigo
            and not oraculo.filtro_data.email_esta_no_periodo(item.get("data_email", ""))
        ):
            analise = _analise_preservada_de_email_processado(mapa_antigo[eid])
        if analise is None:
            _desc_email = f"email id={eid} assunto={str(item.get('assunto',''))[:50]}"
            analise, _ok = processar_com_timeout(
                oraculo.processar_email, (item,),
                timeout_s=_timeout_por_email,
                item_desc=_desc_email,
            )
            if not _ok:
                _erros_timeout += 1
                analise = {"cadoc": "ERRO_TIMEOUT", "exibir_card": False}
                if VERBOSE:
                    print(f"   [SKIP] {_desc_email} — timeout após {_timeout_por_email}s", flush=True)
        
        # Guarda a análise no item original
        item["analise"] = analise
        
        # === PROCESSAMENTO ADICIONAL: CLIENTE, RESPONSÁVEL E LIMPEZA HTML ===
        
        # 1. Limpar HTML → Texto limpo
        # Prioriza corpo_texto (tem \n naturais das quebras de linha)
        # Fallback para corpo_html quando corpo_texto não existe
        corpo_html = item.get('corpo_html') or item.get('corpo', '')
        corpo_texto_raw = item.get('corpo_texto', '').strip()
        if corpo_texto_raw:
            corpo_limpo = corpo_texto_raw
        else:
            corpo_limpo = limpar_html_para_texto(corpo_html)
        
        # 1.1 Limpeza profunda: remove assinaturas, disclaimers, citações
        corpo_limpo = limpar_corpo_profundo(corpo_limpo)
        
        # 1.2 Normaliza para linha única (sem \n no campo corpo_limpo)
        corpo_limpo = re.sub(r'\s+', ' ', corpo_limpo).strip()

        # 1.3 Fallback para e-mails cujo corpo inteiro é um Fwd encaminhado sem texto próprio.
        # Só entra quando limpar_corpo_profundo cortou tudo (placeholder ou vazio).
        # Não altera e-mails normais que têm conteúdo antes do marcador de Fwd.
        _PLACEHOLDER = "(sem conteúdo textual)"
        _RE_FWD_HEADER = re.compile(
            r'---------- Forwarded message ---------\s*'
            r'(?:(?:De|From|Para|To|Data|Date|Assunto|Subject)\s*:.*\n)*',
            re.IGNORECASE | re.MULTILINE,
        )
        if corpo_limpo in ("", _PLACEHOLDER):
            _raw = corpo_texto_raw or limpar_html_para_texto(corpo_html)
            _m = _RE_FWD_HEADER.search(_raw)
            if _m:
                _fwd_body = _raw[_m.end():].strip()
                _fwd_body = re.sub(r'\s+', ' ', _fwd_body).strip()
                if _fwd_body:
                    corpo_limpo = _fwd_body

        # 2. Cliente, responsável e contatos (origem/destino); F→F quando o 1.º To é Finaud
        contato_origem, contato_destino, cliente, responsavel = montar_contatos_origem_destino_para_item(
            item, MAPEAMENTO_CLIENTES
        )

        # 3. Detectar complexidade (para otimizar custo de IA no futuro)
        html_low = (corpo_html or "").lower()

        tem_tabela = "<table" in html_low
        tem_lista  = "<ul" in html_low or "<ol" in html_low
        tem_enfase = "<b" in html_low or "<strong" in html_low

       
        # Decisão: IA deve usar HTML ou texto?
        # HTML = Mais caro mas preciso / Texto = Mais barato mas perde estrutura
        usar_html_para_ia = tem_tabela or (tem_lista and tem_enfase)

        # ======================================================================
        # #PF44: Padrão D — Finaud só em CC (cliente envia para terceiro, Finaud em cópia)
        # Quando Finaud não está no remetente nem no Para, mas está no CC, e o e-mail
        # tem um CADOC identificado, exibir o card mesmo sem prazo extraído.
        # Motivo: a Finaud foi copiada em uma conversa regulatória e precisa estar ciente.
        # Sem esta correção, exibir_card=False porque len(prazos_finais)==0.
        _dominios_finaud_pf44 = MAPEAMENTO_CLIENTES.get('nossa_equipe', {}).get('dominios', [])
        def _eh_finaud_pf44(txt):
            return any(d in (txt or '').lower() for d in _dominios_finaud_pf44)
        _remetente_raw = item.get('remetente', '') or ''
        _para_raw      = item.get('destinatarios', '') or ''
        _cc_raw        = item.get('cc', '') or ''
        _finaud_so_cc  = (
            not _eh_finaud_pf44(_remetente_raw)
            and not _eh_finaud_pf44(_para_raw)
            and _eh_finaud_pf44(_cc_raw)
            and bool(analise.get('cadoc'))
            and not analise.get('exibir_card')
            and analise.get('cadoc') != "INTERNO"
        )
        if _finaud_so_cc:
            analise = dict(analise)  # cópia para não alterar cache
            analise['exibir_card'] = True
            analise['tipo_painel'] = 'REGULATORIO'
            analise['finaud_somente_cc'] = True
        # ======================================================================

        # Converte data_email para formato brasileiro em horário de Brasília
        data_original = item.get('data_email', '')
        data_formatada = ''
        try:
            import pytz
            dt_obj = parsedate_to_datetime(data_original)
            if dt_obj.tzinfo is None:
                import datetime as _dt
                dt_obj = pytz.UTC.localize(dt_obj)
            tz_br = pytz.timezone('America/Sao_Paulo')
            dt_br = dt_obj.astimezone(tz_br)
            data_formatada = dt_br.strftime('%d/%m/%Y %H:%M')  # DD/MM/YYYY HH:mm (Brasília)
        except Exception:
            data_formatada = data_original  # Fallback
           
        
        
        # threadId = thread_root (X-GM-THRID quando disponível) — igual ao Gmail, sem regras por assunto.
        # O que o Gmail mostra (1 thread, 10 threads) é o que o ORÁCULO mostra.
        thread_id_correto = (
            item.get('thread_root') or
            item.get('threadId') or
            item.get('message_id') or
            "SEM_THREAD"
        )
        
        # Cria registro formatado para o resultado final
        email_processado = {
            "data_email": data_formatada,
            "threadId": thread_id_correto,  # ✅ CORRIGIDO: usa thread_root para agrupar
            "id": item.get('id'),
            "cliente": "Finaud" if analise.get("cadoc") == "INTERNO" else cliente,
            "assunto": item.get('assunto'),
            "remetente": item.get('remetente'),        # ✅ #PF43: campo preservado do JSON 01
            "contato_origem": contato_origem,          # ✅ Quem mandou (lado/nome/email)
            "contato_destino": contato_destino,        # ✅ Quem recebe (lado/nome/email)
            "responsavel": responsavel,                # ✅ PROCESSADO
            "corpo_limpo": corpo_limpo,                # ✅ Texto limpo (1KB) - Para 80% dos casos
            "corpo_html": corpo_html,                  # ✅ HTML original (5KB) - Quando precisa precisão
            "tem_estrutura_complexa": usar_html_para_ia,  # ✅ Flag: IA deve usar HTML?
            "cadoc": analise.get("cadoc"),
            "tipo_painel": analise.get("tipo_painel", ""),
            "exibir_card": analise.get("exibir_card", False),
            "prazos": analise.get("lista_prazos", []),
            "retorno_bacen": analise.get("retorno_bacen", False),
            "finaud_somente_cc": analise.get("finaud_somente_cc", False),  # #PF44: Padrão D
        }
        resultado_final["emails_processados"].append(email_processado)
        # --- Consolidação por thread (histórico completo para IA) ---
        th_id = email_processado.get("threadId") or "SEM_THREAD"
        th = threads_map.get(th_id)
        if not th:
            th = {"threadId": th_id, "mensagens": []}
            threads_map[th_id] = th
        # Deduplicação: (1) por id/message_id; (2) por conteúdo (mesmo data_email + mesmo corpo = mesmo e-mail com outro id).
        msg_id = email_processado.get("id") or email_processado.get("message_id") or item.get("id") or item.get("message_id")
        data_email = (email_processado.get("data_email") or item.get("data_email") or "").strip()
        corpo_para_fingerprint = (email_processado.get("corpo_limpo") or item.get("corpo_html") or item.get("corpo") or item.get("corpo_texto") or "")[:500]
        ids_ja_na_thread = {str(m.get("id") or m.get("message_id") or "") for m in th["mensagens"]}
        ja_tem_pelo_conteudo = any(
            (m.get("data_email") or "").strip() == data_email and
            (m.get("corpo_limpo") or m.get("corpo") or "")[:500] == corpo_para_fingerprint
            for m in th["mensagens"]
        )
        if msg_id is not None and str(msg_id) in ids_ja_na_thread:
            pass  # já existe mensagem com esse id na thread
        elif ja_tem_pelo_conteudo:
            pass  # mesma data + mesmo corpo (e-mail duplicado com id diferente, ex.: 91611 e 91607)
        else:
            # CORREÇÃO DEFINITIVA: corpo da thread vem SEMPRE do item bruto; para o modal exibir texto completo
            # (igual ao PDF), gravamos SEMPRE como TEXTO LIMPO. Se gravarmos HTML, o frontend
            # (emailBodyToReadableText + stripEmailBoilerplate) corta quase tudo e sobra só "Lucas,".
            corpo_bruto_thread = item.get("corpo_html") or item.get("corpo") or item.get("corpo_texto") or ""
            corpo_completo = limpar_html_para_texto(corpo_bruto_thread)
            usar_html = False
            th["mensagens"].append({
                "id": email_processado.get("id"),
                "data_email": email_processado.get("data_email"),
                "assunto": email_processado.get("assunto"),
                "cliente": email_processado.get("cliente"),
                "contato_origem": email_processado.get("contato_origem"),
                "contato_destino": email_processado.get("contato_destino"),
                "responsavel": email_processado.get("responsavel"),
                "cadoc": email_processado.get("cadoc"),
                "prazos": email_processado.get("prazos", []),
                "retorno_bacen": email_processado.get("retorno_bacen", False),
                "tem_estrutura_complexa": email_processado.get("tem_estrutura_complexa", False),
                "corpo": corpo_completo,
                "corpo_limpo": email_processado.get("corpo_limpo", ""),
                "formato_corpo": "html" if usar_html else "texto"
            })

        
        # Atualiza contadores do resumo
        if analise.get("exibir_card"):
            resultado_final["resumo"]["com_prazos"] += 1
        elif analise.get("cadoc") in ["FILTRADO_POR_DATA", "IGNORADO", "INTERNO"] or analise.get("cadoc") == "":
            resultado_final["resumo"]["filtrados"] += 1
        else:
            resultado_final["resumo"]["sem_prazos"] += 1
        
        # Barra de progresso (modo resumo)
        if not VERBOSE:
            _atualizar_barra(idx, total_emails)
        
        # Salvamento progressivo a cada 200 e-mails (evita gravar 161MB a cada iteração).
        # Usa indent=None nos saves intermediários; o save final usa indent=4.
        if not INCREMENTAL and idx % 200 == 0:
            with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f_out:
                json.dump(resultado_final, f_out, indent=None, ensure_ascii=False)
    
    # Em modo incremental, recalcula resumo a partir do total (evita deriva por reutilização)
    if INCREMENTAL and resultado_final["emails_processados"]:
        resultado_final["resumo"]["com_prazos"] = sum(1 for e in resultado_final["emails_processados"] if e.get("exibir_card"))
        resultado_final["resumo"]["filtrados"] = sum(1 for e in resultado_final["emails_processados"] if e.get("cadoc") in ["FILTRADO_POR_DATA", "IGNORADO", "INTERNO"] or e.get("cadoc") == "")
        resultado_final["resumo"]["sem_prazos"] = len(resultado_final["emails_processados"]) - resultado_final["resumo"]["com_prazos"] - resultado_final["resumo"]["filtrados"]
    
    if not VERBOSE:
        sys.stdout.write("\n")
        sys.stdout.flush()
    
    # RELATÓRIO FINAL MELHORADO
    # --- Gera visão consolidada por thread (para histórico completo no painel e IA) ---
    threads_processadas = []
    for th_id, th in threads_map.items():
        msgs = th.get("mensagens", [])
        # ordena por data (formato BR) quando possível
        def _parse_dt_br(s):
            try:
                return datetime.strptime(s, "%d/%m/%Y %H:%M")
            except Exception:
                return datetime.min
        msgs_sorted = sorted(msgs, key=lambda m: _parse_dt_br(m.get("data_email", "")))
        if not msgs_sorted:
            continue
        ultima = msgs_sorted[-1]
        o_lado = (ultima.get("contato_origem") or {}).get("lado") or ""
        d_lado = (ultima.get("contato_destino") or {}).get("lado") or ""
        if o_lado == "CLIENTE":
            pendencia = "FINAUD"
        elif o_lado == "FINAUD" and d_lado == "FINAUD":
            pendencia = "FINAUD"
        else:
            pendencia = "CLIENTE"
        # consolida prazos (união)
        prazos_set = set()
        prazos = []
        for m in msgs_sorted:
            for pz in (m.get("prazos") or []):
                chave = (pz.get("data_base"), pz.get("prazo_limite"))
                if chave not in prazos_set:
                    prazos_set.add(chave)
                    prazos.append(pz)
        # Escolhe cadoc preferencial da thread.
        #
        # Regra (item 22 — fix): RETORNO_BACEN só vence quando uma mensagem do lado
        # CLIENTE (ou EXTERNO) tiver essa classificação. Mensagens da Finaud explicando
        # ou orientando sobre o BACEN não devem sobrescrever o cadoc original da thread
        # (ex.: Warren DLO → Finaud responde sobre notificação → thread não deve virar RB;
        #  Galapagos SUPORTE → Finaud menciona BACEN na resposta → thread fica SUPORTE).
        cadoc_thread = ""
        _IGNORADOS = {"FILTRADO_POR_DATA", "IGNORADO"}
        for m in msgs_sorted:
            c = (m.get("cadoc") or "")
            if c != "RETORNO_BACEN":
                continue
            # Só aceita RB como cadoc da thread se veio do lado CLIENTE/externo
            lado_orig = (m.get("contato_origem") or {}).get("lado", "").upper()
            email_orig = (m.get("contato_origem") or {}).get("email", "").lower()
            is_finaud = (
                lado_orig == "FINAUD"
                or "@finaud.com.br" in email_orig
                or "@finaudtec.com.br" in email_orig
            )
            if not is_finaud:
                cadoc_thread = "RETORNO_BACEN"
                break
        if cadoc_thread != "RETORNO_BACEN":
            for m in msgs_sorted:
                c = (m.get("cadoc") or "")
                if c and c not in _IGNORADOS:
                    cadoc_thread = c
                    break
        # SUPORTE / DRSAC / FORCAPITAL / 6209: usar apenas o prazo mais recente (última mensagem), não múltiplos
        if cadoc_thread in ("SUPORTE", "DRSAC", "FORCAPITAL", "6209") and len(prazos) > 1:
            prazos_suporte_com_dt = []
            for pz in prazos:
                try:
                    dt_base = datetime.strptime(pz.get("data_base", ""), "%d/%m/%Y")
                    prazos_suporte_com_dt.append((dt_base, pz))
                except Exception:
                    pass
            if prazos_suporte_com_dt:
                prazos_suporte_com_dt.sort(key=lambda x: x[0], reverse=True)
                prazos = [prazos_suporte_com_dt[0][1]]
        # Exceção: Finaud agradeceu recebimento (obrigada pelo envio) → ela precisa gerar e enviar ao cliente (qualquer CADOC)
        corpo_ultima = (ultima.get("corpo", "") or ultima.get("corpo_limpo", "") or "").lower()
        obrigada_exception = (ultima.get("contato_origem", {}).get("lado") == "FINAUD"
            and ("obrigada pelo envio" in corpo_ultima or "obrigado pelo envio" in corpo_ultima))
        if obrigada_exception:
            pendencia = "FINAUD"
        # Responsável: na exceção "obrigada pelo envio", quem enviou (Finaud) é o responsável, não o destinatário
        responsavel = ultima.get("responsavel")
        if obrigada_exception:
            responsavel = ultima.get("contato_origem", {}).get("nome") or ultima.get("contato_origem", {}).get("email", "").split("@")[0] or responsavel
        # texto unificado (para IA): concatena mensagens com cabeçalho
        partes = []
        for m in msgs_sorted:
            partes.append(f"--- {m.get('data_email')} | {m.get('contato_origem', {}).get('lado')} → {m.get('contato_destino', {}).get('lado')} | {m.get('id')} ---\n{m.get('corpo', '')}".strip())
        conversa_unificada = "\n\n".join(partes)
        retorno_bacen_thread = any(m.get("retorno_bacen") for m in msgs_sorted)
        threads_processadas.append({
            "threadId": th_id,
            "qtd_mensagens": len(msgs_sorted),
            "assunto": msgs_sorted[0].get("assunto"),
            "cadoc": cadoc_thread,
            "pendencia": pendencia,
            "responsavel": responsavel,
            "prazos": prazos,
            "retorno_bacen": retorno_bacen_thread,
            "mensagens": msgs_sorted,
            "conversa_unificada": conversa_unificada,
        })
    resultado_final["threads_processadas"] = threads_processadas

    # 🔧 SALVAMENTO FINAL - Salva novamente com threads_processadas populado
    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f_out:
        json.dump(resultado_final, f_out, indent=4, ensure_ascii=False)

    # Checkpoint concluído — remove arquivo de retomada
    limpar_checkpoint("05_classificar")
    if _erros_timeout:
        print(f"\n[AVISO] {_erros_timeout} e-mail(s) pulados por timeout ({_timeout_por_email}s). "
              f"Verifique com ORACULO_VERBOSE=1 se quiser identificar quais.", flush=True)

    print(f"\n{'='*60}")
    print("RESUMO FINAL:")
    print(f"   • Emails com prazos: {resultado_final['resumo']['com_prazos']}")
    print(f"   • Emails sem prazos: {resultado_final['resumo']['sem_prazos']}")
    print(f"   • Emails filtrados: {resultado_final['resumo']['filtrados']}")
    print(f"   • Total processado: {resultado_final['total_emails']}")
    print(f"\n   AGRUPAMENTO DE THREADS:")
    print(f"   • Threads únicas: {len(threads_processadas)}")
    if threads_processadas:
        total_msgs = sum(t.get('qtd_mensagens', 0) for t in threads_processadas)
        media_msgs = total_msgs / len(threads_processadas)
        threads_multiplas = sum(1 for t in threads_processadas if t.get('qtd_mensagens', 0) > 1)
        print(f"   • Mensagens agrupadas: {total_msgs}")
        print(f"   • Média msg/thread: {media_msgs:.1f}")
        print(f"   • Threads com múltiplas msgs: {threads_multiplas}")
    print(f"{'='*60}")
    if _DOMINIOS_SEM_NOME:
        print(f"\n[ATENCAO] {len(_DOMINIOS_SEM_NOME)} dominio(s) sem nome no mapeamento — cliente aparece com nome incompleto na tela:")
        for dom in sorted(_DOMINIOS_SEM_NOME):
            print(f"   -> {dom}  (aparece como '{dom.split('.')[0].capitalize()}')")
        print("   Para corrigir: adicione esses dominios em mapeamento_regras_negocio.json > QUEM_ENVIA_E_RECEBE > mapeamento_nomes_clientes")
    resumo(processados=resultado_final.get('total_emails',0), ignorados=resultado_final['resumo'].get('filtrados',0), tempo_s=relogio.elapsed)
    registrar_execucao("05_classificar", arquivo_saida=ARQUIVO_SAIDA)
    print(f"CONCLUIDO: {ARQUIVO_SAIDA}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    with iniciar_log_standalone(5, "classificar_emails_regulatorio"):
        main()