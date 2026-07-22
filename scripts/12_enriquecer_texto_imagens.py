"""
ORÁCULO 360 - Enriquecer 03 com texto_imagens (anexos filtrados + OCR)

Lê 03_integrador_dados_site.json e data/email_anexos; aplica filtro de IMAGENS_PARA_CADOC;
por mensagem: (0) se existir PDF ``ID_*.pdf`` com texto de crítica CRD (ELIM + 2061/…), usa só esse
texto (igual ao PDF pesquisável); (1) por imagem: ``.legivel.txt`` (texto colado do PDF) se existir;
(2) ``.ocr.txt``; (3) OCR (Tesseract/EasyOCR); (4) placeholder. Normaliza rótulos típicos da tela CRD e **1876.xx → 876.xx** em árvore RWAOPAD/DLO (artefato de OCR).

Persistência: após OCR válido, grava em data/json/cache_texto_imagens_validado.json; na abertura
do 03, repõe texto_imagens quando os anexos foram removidos pelo 02. O 02 copia .ocr.txt/.legivel.txt
para esse cache antes de apagar ficheiros.

Sem instalar nada no Windows: crie arquivos .ocr.txt manualmente ao lado de cada imagem
(nome da imagem + .ocr.txt) com o texto extraído (ex.: colar de um OCR online). Ou use só no venv:
  pip install easyocr  → OCR puro em Python, sem Tesseract no sistema.

Uso:
  python scripts/12_enriquecer_texto_imagens.py   # incremental; 2 msgs paralelas; 2 workers/anexo
  python scripts/12_enriquecer_texto_imagens.py --workers-msg 4 --workers 2   # mais rápido (4 msgs paralelas)
  python scripts/12_enriquecer_texto_imagens.py --workers 1 --workers-msg 1   # máquina lenta: sequencial
  python scripts/12_enriquecer_texto_imagens.py --no-incremental   # reprocessa todas as mensagens
  python scripts/12_enriquecer_texto_imagens.py --sem-ocr   # só .ocr.txt ou placeholder (rápido)
  python scripts/12_enriquecer_texto_imagens.py --salvar-a-cada 100
  python scripts/12_enriquecer_texto_imagens.py --debug   # diagnostica lentidão (tempo e uso de OCR)
  python scripts/12_enriquecer_texto_imagens.py --memoria-baixa   # evita pico de RAM (Windows fecha o processo)
  python scripts/12_enriquecer_texto_imagens.py --data 23/02/2026   # só mensagens do dia 23 (rápido)
  python scripts/12_enriquecer_texto_imagens.py --data 23/02/2026 --rapido   # dia 23 + modo rápido
  python scripts/12_enriquecer_texto_imagens.py --ids 91939,92020 --no-incremental  # só estes IDs Gmail (mensagens no 03)
"""
import argparse
import sys
import warnings

# Suprime UserWarning do PyTorch/EasyOCR sobre pin_memory sem GPU (evita poluir saída)
warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)
import gc

# Configuração de modo de execução — definida em main() via argumentos CLI.
# Encapsulada num objeto para evitar dois globais soltos (#52).
class _ModoExecucao:
    memoria_baixa: bool = False  # --memoria-baixa: sequencial, só Tesseract, imagens menores
    rapido: bool = False         # --rapido: paralelo 2x2, só PSM 6, imagens menores

_modo = _ModoExecucao()

# Aliases de compatibilidade — mantidos para não alterar as funções internas
_MEMORIA_BAIXA: bool = False
_RAPIDO: bool = False
import json
import os
import shutil
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import texto_imagens_cache  # noqa: E402

from paths import F_INTEGRADOR, F_INTEGRADOR_BACKUP, F_MAPEAMENTO, PIPELINE_DIR, registrar_execucao, verificar_dependencias
from pipeline_log import cabecalho, resumo as _resumo_12, Cronometro as _Cron12, iniciar_log_standalone
PASTA_JSON    = PIPELINE_DIR
PASTA_ANEXOS  = os.path.join(BASE_DIR, "data", "email_anexos")
PASTA_LOGS    = os.path.join(BASE_DIR, "logs", "ocr")
ARQUIVO_03        = F_INTEGRADOR
ARQUIVO_03_BACKUP = F_INTEGRADOR_BACKUP
ARQUIVO_REGRAS    = F_MAPEAMENTO
LOG_ENRIQUECER = os.path.join(PASTA_LOGS, "09_enriquecer_texto_imagens.log")

_log_file = None


def _imagem_arquivo_dimensoes_conteudo_util(path: str) -> bool:
    """
    Alinha ao coletor 01 (_imagem_inline_dimensoes_sugerem_conteudo): não OCR em logos de assinatura
    (ex. 342×15 px Banvox) gravados antes da regra de dimensões.
    """
    if not path or not os.path.isfile(path):
        return True
    try:
        from PIL import Image

        with Image.open(path) as img:
            w, h = img.size
        if w <= 0 or h <= 0:
            return True
        area = w * h
        mx, mn = max(w, h), min(w, h)
        if area >= 90_000:
            return True
        if mx >= 420:
            return True
        if mn >= 280:
            return True
        # Capturas de indício/crítica CRD frequentemente ~300–400 px de largura e baixa altura
        # (ex. 342×137); antes eram descartadas e só restava OCR de logo «Banvex» no .ocr.txt.
        if area >= 40_000 and mx >= 300:
            return True
        return False
    except Exception:
        return True


def _extrair_texto_xlsx_indicio(path: str) -> str:
    """
    Lê indicio-qualidade*.xlsx enviado pelo BACEN e converte para texto estruturado.
    Prioridade: openpyxl (xlsx) → xlrd (xls antigo). Retorna '' se nenhum instalado ou falhar.
    """
    if not path or not os.path.isfile(path):
        return ""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        linhas = []
        for row in ws.iter_rows(values_only=True):
            partes = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if partes:
                linhas.append("  |  ".join(partes))
        wb.close()
        return "\n".join(linhas).strip()
    except ImportError:
        pass
    except Exception:
        return ""
    try:
        import xlrd
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        linhas = []
        for r in range(ws.nrows):
            partes = [str(ws.cell_value(r, c)).strip() for c in range(ws.ncols)
                      if str(ws.cell_value(r, c)).strip()]
            if partes:
                linhas.append("  |  ".join(partes))
        return "\n".join(linhas).strip()
    except Exception:
        return ""


def _extrair_texto_pdf(path_pdf: str) -> str:
    """Extrai texto de todas as páginas (pdfplumber). Retorna '' se falhar."""
    if not path_pdf or not os.path.isfile(path_pdf):
        return ""
    try:
        import pdfplumber

        partes: list[str] = []
        with pdfplumber.open(path_pdf) as pdf:
            for page in pdf.pages:
                t = (page.extract_text() or "").strip()
                if t:
                    partes.append(t)
        return "\n\n".join(partes).strip()
    except Exception:
        return ""


def _texto_eh_critica_crd_extraido_pdf(texto: str) -> bool:
    """True se o texto do PDF parece a tabela de críticas do CRD (ELIM + 2061/documento)."""
    t = (texto or "").strip()
    if len(t) < 80:
        return False
    if not re.search(r"ELIM\d{3,}", t, re.I):
        return False
    tl = t.lower()
    return (
        "2061" in tl
        or "documento" in tl
        or "código do evento" in tl
        or "codigo do evento" in tl
        or "respostacrd" in tl.replace(" ", "")
    )


def _listar_xlsx_indicio_por_id(pasta_anexos: str) -> dict[str, list[tuple[str, str]]]:
    """
    Varre email_anexos por arquivos .xlsx/.xls cujo nome contenha 'indicio' e 'qualidade'.
    Esses arquivos são enviados pelo BACEN junto com a notificação e têm prioridade sobre
    o OCR de prints do CRD (mesmas informações, sem risco de erro de leitura).
    Retorna dict msg_id -> [(path, nome)].
    """
    if not os.path.isdir(pasta_anexos):
        return {}
    por_id: dict[str, list[tuple[str, str]]] = {}
    for nome in os.listdir(pasta_anexos):
        if "_" not in nome:
            continue
        ext = os.path.splitext(nome)[1].lower()
        if ext not in (".xlsx", ".xls"):
            continue
        nome_lower = nome.lower()
        if ("indicio" not in nome_lower and "indício" not in nome_lower):
            continue
        if "qualidade" not in nome_lower:
            continue
        msg_id = nome.split("_", 1)[0]
        path = os.path.join(pasta_anexos, nome)
        if os.path.isfile(path):
            por_id.setdefault(msg_id, []).append((path, nome))
    return por_id


def _listar_pdfs_por_id(regras: dict) -> dict[str, list[tuple[str, str]]]:
    """
    PDFs em email_anexos com prefixo msg_id (ex.: 91983_export.pdf).
    Usado para preencher texto_imagens com o mesmo texto pesquisável do PDF (quando o anexo existe).
    """
    if not os.path.isdir(PASTA_ANEXOS):
        return {}
    excluir = [x.lower() for x in (regras or {}).get("excluir_nome_contem", [])]
    min_pdf = 400
    max_pdf = 5
    por_id: dict[str, list[tuple[str, str, int]]] = {}
    for nome in os.listdir(PASTA_ANEXOS):
        if "_" not in nome:
            continue
        ext = os.path.splitext(nome)[1].lower()
        if ext != ".pdf":
            continue
        path = os.path.join(PASTA_ANEXOS, nome)
        if not os.path.isfile(path):
            continue
        nome_lower = nome.lower()
        if any(x in nome_lower for x in excluir):
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if size < min_pdf:
            continue
        real_id = nome.split("_", 1)[0]
        por_id.setdefault(real_id, []).append((path, nome, size))
    for k in por_id:
        por_id[k].sort(key=lambda x: -x[2])
        por_id[k] = [(p, n) for p, n, _ in por_id[k][:max_pdf]]
    return por_id


def _melhor_texto_crd_de_pdfs(msg_id: str, cache_pdf: dict) -> tuple[str, str] | None:
    """Retorna (nome_arquivo, texto) do PDF com maior texto CRD-like, ou None."""
    pdfs = cache_pdf.get(str(msg_id), [])
    best: tuple[str, str, int] | None = None
    for path, nome in pdfs:
        raw = _extrair_texto_pdf(path)
        if not _texto_eh_critica_crd_extraido_pdf(raw):
            continue
        ln = len(raw)
        if best is None or ln > best[2]:
            best = (nome, raw, ln)
    if not best:
        return None
    return best[0], best[1]


def _normalizar_ocr_interface_crd(texto: str) -> str:
    """
    Aproxima o OCR ao texto da interface / PDF: rótulos de paginação e bullets do CRD.
    """
    if not (texto or "").strip():
        return texto or ""
    t = texto
    t = re.sub(
        r"Anterio!\s*n\s*Pr[oó](?:ximo)?\s*Total",
        "Anterior | Próximo Total",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r"Anterio!\s*n\s*Pr[oó](?:ximo)?",
        "Anterior | Próximo",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r"(?m)^\*\s*O\s+Enviado\s+para\s+sistema\s+de\s+neg[oó]cio",
        "Enviado para sistema de negócio",
        t,
    )
    t = re.sub(
        r"(?m)^\*O\s+Enviado\s+para\s+sistema\s+de\s+neg[oó]cio",
        "Enviado para sistema de negócio",
        t,
    )
    t = re.sub(r"(?m)^\*\s*O\s+Em\s+processamento\s+pelo\s+CRD", "Em processamento pelo CRD", t)
    t = re.sub(r"(?m)^\*O\s+Em\s+processamento\s+pelo\s+CRD", "Em processamento pelo CRD", t)
    t = re.sub(r"(?m)^A\s+Rejeitado\s+pelo\s+sistema\s+de\s+negócio", "Rejeitado pelo sistema de negócio", t)
    t = re.sub(r"Histórico da situação\s*-\s*$", "Histórico da situação", t, flags=re.MULTILINE)
    t = _normalizar_ocr_prefixo_fantasma_conta_876(t)
    t = _ocr_corrigir_erros_comuns(t)
    return t


def _ocr_corrigir_erros_comuns(texto: str) -> str:
    """
    Corrige erros recorrentes de OCR em telas do Bacen (indícios, CRD)
    e assinaturas de e-mail. Aplicado após sanitização de prefixo/interface.
    """
    if not (texto or "").strip():
        return texto or ""
    t = texto

    # --- Grupo 1: palavras corrompidas em telas de indício Bacen ---
    t = re.sub(r"\bstu[as]?ção\b", "situação", t, flags=re.IGNORECASE)
    t = re.sub(r"\bstus[aã]o\b", "situação", t, flags=re.IGNORECASE)
    t = re.sub(r"\bstusção\b", "situação", t, flags=re.IGNORECASE)
    t = re.sub(r"\bTrodeidico\b", "Tipo de indício", t)
    t = re.sub(r"\bTwode\s+nácia\b", "Tipo de indício", t)
    t = re.sub(r"\bCrtca\b", "Crítica", t)
    t = re.sub(r"\berítica\b", "crítica", t)
    t = re.sub(r"\bidentficad", "identificad", t)
    t = re.sub(r"\bransações\b", "transações", t)
    t = re.sub(r"\bluidadas\b", "liquidadas", t)
    t = re.sub(r"\bMistórico\b", "Histórico", t)

    # Cabeçalho da linha de indício Bacen: "Tipo de indício Inconsistência - situação: X"
    # O OCR perde os dois-pontos após "indício" e "situação" nessa linha específica;
    # \.? consome ponto solto que às vezes fica após "situação" no OCR
    t = re.sub(
        r"(Tipo de ind[ií]cio)\s+(Inconsist[eê]ncia\s+-\s+situa[çc][aã]o)\.?",
        r"\1: \2:",
        t,
    )

    # --- Grupo 2: email — & no lugar de @ em endereços (domínios com ou sem hífen) ---
    t = re.sub(r"(\w)&([\w][\w-]*(?:\.[\w][\w-]*)+)", r"\1@\2", t)

    # --- Grupo 3: www ---
    t = re.sub(r"\bWIWW\.", "www.", t)

    # --- Grupo 4: XML CRD — tags corrompidas ---
    t = re.sub(r"<\s*tacRD\b", "<respostaCRD", t)
    t = re.sub(r"</respostacRD>", "</respostaCRD>", t)
    t = re.sub(r"situaçao", "situação", t)
    t = re.sub(r"descriçcao", "descricao", t)
    t = re.sub(r"<complemento»>", "<complemento>", t)

    # --- Grupo 5: lixo de barra de menu após "Exibir" em print CRD ---
    # Captura qualquer sequência de lixo até "gode" (palavra que fecha o artefato)
    t = re.sub(
        r"(Exibir)\s+[\w\s=]+?gode\b",
        r"\1 [menu do sistema]",
        t,
    )

    # --- Grupo 6: abreviações corrompidas ---
    # "doe." → "doc." quando seguido de número ou espaço+número (referência a documento)
    t = re.sub(r"\bdoe\.(\s+\d)", r"doc.\1", t)

    return t


def _normalizar_ocr_prefixo_fantasma_conta_876(texto: str) -> str:
    """
    Em prints DLO / árvore RWAOPAD, o código de conta é **876.xx** (ex.: 876.02).
    O OCR costuma prefixar **1** (ícone +, borda de célula ou coluna) → **1876.02**, inexistente na tela.
    Corrige para alinhar texto_imagens ao que o analista vê e ao PDF quando aplicável.
    """
    if not (texto or "").strip():
        return texto or ""
    t = texto
    # Caso principal: 1876.02 → 876.02 (todas as subníveis 1876.20.10 etc.)
    t = re.sub(r"\b1876\.", "876.", t)
    # OCR partiu "876." em "1" + "876." na mesma linha
    t = re.sub(r"\b1\s+876\.", "876.", t)
    return t


def _ocr_sanitizar_prefixo_tela_crd(texto: str) -> str:
    """
    Remove linhas iniciais de ruído de OCR em capturas do CRD (barra de título / menus),
    alinhando o texto ao que o analista vê na tabela (a partir de 'Código do evento' ou código ELIM).
    """
    t = (texto or "").strip()
    if not t or t.startswith("[Anexo:"):
        return texto or ""
    lines = t.splitlines()
    start = 0
    for i, line in enumerate(lines):
        sl = line.strip()
        if re.search(r"(?i)c[oó]digo\s+do\s+evento", sl):
            start = i
            break
        if re.search(r"(?i)\bELIM\d{4,}\b", sl):
            start = i
            break
    else:
        return t
    return "\n".join(lines[start:]).strip()


def _ocr_texto_eh_ruido_logo_assinatura(nome_arquivo: str, texto: str) -> bool:
    """OCR curto de nome imageNNN.png sem dígitos (ex.: 'Banvex') — típico logo, não tela BC."""
    t = (texto or "").strip()
    if not t:
        return True
    if re.match(r"^(banvox|banvex|bancx|banv[eo]x\.?)$", t, re.I):
        return True
    t1 = re.sub(r"\s+", " ", t).strip()
    if re.match(r"(?i)^bcp\)\s*(orum|forum|fórum|foru)$", t1):
        return True
    base = os.path.basename(nome_arquivo or "")
    is_outlook_image = bool(re.search(r"(?:^|_)image\d+(?:\.png)?$", base, re.I))
    if is_outlook_image:
        compact = re.sub(r"[^\w\u00C0-\u024F]", "", t, flags=re.UNICODE)
        if len(compact) < 14 and not re.search(r"\d", t):
            return True
    if not is_outlook_image:
        return False
    if re.search(r"\d", t):
        return False
    if "\n" in t:
        return False
    words = t.split()
    if len(words) == 1 and len(t) <= 10:
        return True
    return False


def _extrair_data_msg(msg) -> datetime | None:
    """Extrai datetime da mensagem (data_email, data_iso ou timestamp). Retorna None se não parsear."""
    for campo in ("data_email", "data_iso", "timestamp"):
        val = (msg.get(campo) or "").strip()
        if not val:
            continue
        # DD/MM/YYYY ou DD/MM/YYYY HH:MM
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", val)
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except (ValueError, IndexError):
                pass
        # YYYY-MM-DD
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", val)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except (ValueError, IndexError):
                pass
    return None


def _log(msg, also_print=True):
    """Registra mensagem no log (arquivo) e opcionalmente na tela."""
    global _log_file
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    if also_print:
        print(msg)
    if _log_file is None and PASTA_LOGS:
        try:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            _log_file = open(LOG_ENRIQUECER, "a", encoding="utf-8")
        except Exception:
            pass
    if _log_file:
        try:
            _log_file.write(line.rstrip() + "\n")
            _log_file.flush()
        except Exception:
            pass


def carregar_regras_imagens():
    """Carrega IMAGENS_PARA_CADOC do mapeamento."""
    if not os.path.isfile(ARQUIVO_REGRAS):
        return {}
    with open(ARQUIVO_REGRAS, "r", encoding="utf-8") as f:
        data = json.load(f)
    o_que = data.get("O_QUE_ESTA_SENDO_ANALISADO") or data
    return o_que.get("IMAGENS_PARA_CADOC", {})


def _listar_todos_anexos_por_id(regras):
    """Uma vez só: lista email_anexos e agrupa por prefixo (msg_id). Retorna dict id -> [(path, nome), ...].
    Inclui (1) imagens elegíveis por extensão/tamanho e (2) arquivos .ocr.txt quando não existir a imagem
    (ex.: só restaram .ocr.txt após limpeza de anexos), para o texto extraído aparecer no painel.

    excluir_nome_salvo_acima_bytes: exceção ao excluir_nome_contem — nomes que normalmente seriam
    excluídos são reincluídos se o arquivo tiver tamanho >= este valor (bytes). Cobre casos como
    Outlook-*.png de 140KB que são capturas de tela do cliente (ex. erros RETORNO BACEN) e não
    logos de assinatura (que costumam ter 8–20KB).
    """
    if not os.path.isdir(PASTA_ANEXOS):
        return {}
    ext_ok = set((e.lower() for e in regras.get("extensoes_imagem", [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"])))
    excluir = [x.lower() for x in regras.get("excluir_nome_contem", [])]
    min_bytes = int(regras.get("tamanho_minimo_bytes", 20000))
    max_imagens = int(regras.get("max_imagens_por_email", 20))
    # Exceção por tamanho: nomes excluídos mas com arquivo grande demais para ser logo/ícone
    salvo_acima = int(regras.get("excluir_nome_salvo_acima_bytes", 80_000))

    por_id = {}
    for nome in os.listdir(PASTA_ANEXOS):
        if "_" not in nome:
            continue
        msg_id = nome.split("_", 1)[0]
        path = os.path.join(PASTA_ANEXOS, nome)
        if not os.path.isfile(path):
            continue
        base, ext = os.path.splitext(nome)
        if ext.lower() not in ext_ok:
            continue
        nome_lower = nome.lower()
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        # Verificar exclusão pelo nome — mas permitir se arquivo for grande demais para ser logo
        if any(x in nome_lower for x in excluir):
            if size < salvo_acima:
                continue
            # Arquivo grande com nome excluído: tratar como conteúdo (ex. Outlook-*.png screenshot)
        if size < min_bytes:
            continue
        por_id.setdefault(msg_id, []).append((path, nome, size))

    for k in por_id:
        por_id[k].sort(key=lambda x: -x[2])
        por_id[k] = [(p, n) for p, n, _ in por_id[k][:max_imagens]]

    # Incluir .ocr.txt no cache quando NÃO houver imagem correspondente (ex.: só restaram .ocr.txt)
    # bases_por_id = set dos nomes de anexo já no cache (ex.: "91611_image001.png") para evitar duplicata
    bases_por_id = {mid: set(n for p, n in por_id.get(mid, [])) for mid in por_id}
    for nome in os.listdir(PASTA_ANEXOS):
        if "_" not in nome:
            continue
        if nome.lower().endswith(".ocr.txt"):
            # "91611_image001.png.ocr.txt" -> nome_imagem = "91611_image001.png"
            nome_imagem = nome[:-8]
        elif nome.lower().endswith("_ocr.txt"):
            # "91611_image001_ocr.txt" -> nome_imagem = "91611_image001.png"
            nome_imagem = nome[:-7] + ".png"
        else:
            continue
        msg_id = nome_imagem.split("_", 1)[0] if "_" in nome_imagem else ""
        if not msg_id:
            continue
        path = os.path.join(PASTA_ANEXOS, nome)
        if not os.path.isfile(path):
            continue
        if nome_imagem not in bases_por_id.get(msg_id, set()):
            por_id.setdefault(msg_id, []).append((path, nome_imagem))
            bases_por_id.setdefault(msg_id, set()).add(nome_imagem)
    for k in por_id:
        por_id[k] = por_id[k][:max_imagens]
    return por_id


def listar_anexos_imagem(msg_id, regras, cache_anexos):
    """Retorna anexos filtrados para msg_id usando cache pré-montado."""
    if not msg_id:
        return []
    return cache_anexos.get(str(msg_id), [])


def _achar_tesseract_windows():
    """
    No Windows, procura tesseract.exe em: ProgramFiles, ProgramFiles(x86), PATH.
    Retorna o caminho completo do executável ou None.
    Assim funciona mesmo quando o processo não recebeu o PATH atualizado (ex.: executar_tudo pelo IDE).
    """
    if os.name != "nt":
        return None
    candidatos = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidatos.append(os.path.join(pf, "Tesseract-OCR", "tesseract.exe"))
    candidatos.append(os.path.join(pf86, "Tesseract-OCR", "tesseract.exe"))
    candidatos.append(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    candidatos.append(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")
    for path in candidatos:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    # Busca no PATH do processo (pode ter sido atualizado pelo Chocolatey em outra sessão)
    path_env = os.environ.get("PATH", "")
    for base in path_env.split(os.pathsep):
        base = base.strip()
        if not base:
            continue
        exe = os.path.join(base, "tesseract.exe")
        if os.path.isfile(exe):
            return os.path.abspath(exe)
    return None


def _configurar_tesseract_windows():
    """No Windows, define tesseract_cmd para o executável encontrado (caminho fixo ou PATH)."""
    if os.name != "nt":
        return
    try:
        import pytesseract
        if hasattr(pytesseract, "pytesseract"):
            p = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
            if p and os.path.isfile(p):
                return
        path_exe = _achar_tesseract_windows()
        if path_exe:
            pytesseract.pytesseract.tesseract_cmd = path_exe
    except Exception:
        pass


# EasyOCR: lazy reader (só carrega se for usar); permite OCR sem instalar Tesseract no sistema
_easyocr_reader = None


def _get_easyocr_reader():
    """Retorna o reader EasyOCR (lazy); None se não disponível."""
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(["pt"], gpu=False, verbose=False)
        return _easyocr_reader
    except Exception:
        return None


def _rodar_ocr_easyocr(path_imagem):
    """Extrai texto com EasyOCR (só pip, sem instalar nada no Windows). Retorna '' se falhar."""
    if not path_imagem or not os.path.isfile(path_imagem):
        return ""
    reader = _get_easyocr_reader()
    if reader is None:
        return ""
    try:
        result = reader.readtext(path_imagem)
        return " ".join((r[1] for r in result)).strip()
    except Exception:
        return ""


def _diagnostico_ocr():
    """
    Retorna (tesseract_ok, easyocr_ok, mensagem_diagnostico).
    mensagem_diagnostico explica por que o Tesseract não está disponível, se for o caso.
    """
    msg_tess = ""
    tess_ok = False
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        _configurar_tesseract_windows()
        pytesseract.get_tesseract_version()
        tess_ok = True
    except ImportError as e:
        msg_tess = f"pytesseract não instalado no venv: {e}"
    except Exception as e:
        path_exe = _achar_tesseract_windows() if os.name == "nt" else None
        if path_exe:
            msg_tess = f"Tesseract encontrado em {path_exe} mas falhou ao chamar: {e}"
        else:
            msg_tess = f"tesseract.exe não encontrado (caminhos fixos e PATH). Erro ao usar: {e}"

    easy_ok = False
    try:
        import easyocr  # noqa: F401
        easy_ok = True
    except ImportError:
        pass

    return tess_ok, easy_ok, msg_tess


def _ocr_tesseract_disponivel():
    """True se Tesseract (pytesseract + binário) estiver disponível."""
    ok, _, _ = _diagnostico_ocr()
    return ok


def _ocr_disponivel():
    """True se pelo menos um OCR estiver disponível (Tesseract ou EasyOCR)."""
    if _ocr_tesseract_disponivel():
        return True
    try:
        import easyocr  # noqa: F401
        return True
    except ImportError:
        return False


def _preprocessar_imagem_ocr(img):
    """Redimensiona se muito pequena (ajuda Tesseract em screenshots) ou muito grande (acelera OCR)."""
    from PIL import Image
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    # memoria-baixa: 1500px | rapido: 1800px | normal: 2400px
    max_dim = 1500 if _MEMORIA_BAIXA else (1800 if _RAPIDO else 2400)
    if max(w, h) > max_dim:
        fator = max_dim / max(w, h)
        nova_w = int(w * fator)
        nova_h = int(h * fator)
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        img = img.resize((nova_w, nova_h), resample)
        w, h = img.size
    # Se largura < 800px, aumenta 2x para melhor reconhecimento de texto pequeno
    if w > 0 and w < 800:
        nova_largura = min(w * 2, 1600)
        fator = nova_largura / w
        nova_altura = int(h * fator)
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        img = img.resize((nova_largura, nova_altura), resample)
    return img


def _rodar_ocr_imagem(path_imagem, lang="por"):
    """
    Extrai texto com Tesseract. PSM 6 primeiro (cobre maioria); PSM 4 só se vazio.
    Se o idioma 'por' não estiver instalado (por.traineddata), tenta 'eng'.
    Fecha a imagem ao final para liberar RAM (evita pico de memória no Windows).
    """
    if not path_imagem or not os.path.isfile(path_imagem):
        return ""
    img = None
    try:
        import pytesseract
        from PIL import Image
        _configurar_tesseract_windows()
        img = Image.open(path_imagem).copy()
        img = _preprocessar_imagem_ocr(img)
        idiomas = [lang]
        if lang == "por":
            idiomas.append("eng")
        for lang_try in idiomas:
            try:
                texto = pytesseract.image_to_string(img, lang=lang_try, config="--psm 6")
                texto = (texto or "").strip()
                if texto and len(texto) > 2:
                    return texto
                # Modo rapido: pula PSM 4 (economiza ~50% tempo em imagens vazias/pouco texto)
                if not _RAPIDO:
                    texto = pytesseract.image_to_string(img, lang=lang_try, config="--psm 4")
                    texto = (texto or "").strip()
                    if texto:
                        return texto
            except Exception as e:
                msg = str(e).lower()
                if "traineddata" in msg or "load" in msg and "language" in msg:
                    continue
                return ""
        return ""
    except Exception:
        return ""
    finally:
        if img is not None and hasattr(img, "close"):
            try:
                img.close()
            except Exception:
                pass


def _corrigir_portugues_ocr(texto):
    """
    Corrige palavras em português que o OCR costuma errar:
    acentos faltando, ¢/&/4 em vez de ã/ç/õ, etc.
    """
    if not texto or not isinstance(texto, str):
        return texto
    t = texto
    # Padrões de OCR: & e 4 muitas vezes saem no lugar de ã
    t = t.replace("&o", "ão")
    t = t.replace("&ao", "ão")
    t = t.replace("4o", "ão")  # omiss4o -> omissão
    t = t.replace("4a", "ã")
    # Substituições comuns (ordem: mais específicas primeiro)
    substituicoes = [
        ("Tipo de indicio", "Tipo de indício"),
        ("Inconsisténcia", "Inconsistência"),
        (" indicio ", " indício "),
        ("Indicio ", "Indício "),
        ("indicio de", "indício de"),
        ("Critica ", "Crítica "),
        ("Critica\n", "Crítica\n"),
        (" dia util ", " dia útil "),
        ("dia util do", "dia útil do"),
        ("Interagao", "Interação"),
        ("interagão", "interação"),
        ("Asoma ", "A soma "),
        ("informacdo", "informação"),
        ("informacao", "informação"),
        ("informacoes", "informações"),
        ("informacões", "informações"),
        ("informacées", "informações"),
        (" do ultimo ", " do último "),
        (" do més", " do mês"),
        (" do mês", " do mês"),
        (" ultimo dia", " último dia"),
        ("aplicacao", "aplicação"),
        ("instituicão", "instituição"),
        ("instituico", "instituição"),
        ("institui¢ao", "instituição"),
        (" instituico", " instituição"),
        ("apuracao", "apuração"),
        ("contabeis", "contábeis"),
        ("exposicées", "exposições"),
        ("exposi¢des", "exposições"),
        ("exposicoes", "exposições"),
        ("exposicões", "exposições"),
        ("exposicao ", "exposição "),
        ("correcao", "correção"),
        ("correcdo", "correção"),
        ("corre¢ao", "correção"),
        ("substituico", "substituição"),
        ("interagão", "interação"),
        ("interagao", "interação"),
        ("intera¢ao", "interação"),
        ("interacao ", "interação "),
        ("interacao.", "interação."),
        ("siuscéo", "Situação"),
        ("situacao", "situação"),
        ("negécio", "negócio"),
        ("detalhamentos Cosif", "detalhamentos Cosif"),
        ("valor contabil", "valor contábil"),
        ("contabil", "contábil"),
        ("Historico", "Histórico"),
        ("relativas 4 conta", "relativas à conta"),
        (" 4 conta", " à conta"),
        ("0 botao", "o botão"),
        (" botao ", " botão "),
        ("botao ", "botão "),
        ("serlistados", "ser listados"),
        ("agéo", "ação"),
        ("omissão ", "omissão "),
        ("omissao ", "omissão "),
        ("Usuario ", "Usuário "),
        (" possivel ", " possível "),
        ("excluidos", "excluídos"),
        (" nao ", " não "),
        (" nao.", " não."),
        (" nao,", " não,"),
        (" nao\n", " não\n"),
        ("cédigo", "código"),
    ]
    for antigo, novo in substituicoes:
        t = t.replace(antigo, novo)
    return t


def extrair_texto_imagem(path_imagem, nome, usar_ocr=True, salvar_ocr_txt=True, corrigir_portugues=True, usado_ocr_list=None):
    """
    Retorna o texto da imagem:
    (0) se existir ``imagem.legivel.txt`` (texto colado do PDF / tela), usa-o;
    (1) se path_imagem for um .ocr.txt, lê e devolve; (2) lê .ocr.txt ao lado da imagem se existir;
    (3) senão roda OCR e opcionalmente grava .ocr.txt; (4) senão placeholder.
    Se corrigir_portugues=True, aplica correções de acentuação/português ao texto do OCR.
    Se usado_ocr_list for uma lista, append(path_imagem) quando rodar OCR (para debug).
    """
    path_lower = path_imagem.lower() if isinstance(path_imagem, str) else ""
    if path_lower.endswith(".ocr.txt") or path_lower.endswith("_ocr.txt"):
        try:
            with open(path_imagem, "r", encoding="utf-8", errors="replace") as f:
                conteudo = f.read().strip()
            if corrigir_portugues:
                conteudo = _corrigir_portugues_ocr(conteudo)
            return conteudo
        except Exception:
            return f"[Anexo: {nome} — erro ao ler .ocr.txt]"
    base = path_imagem
    path_legivel = os.path.splitext(base)[0] + ".legivel.txt"
    if os.path.isfile(path_legivel):
        try:
            with open(path_legivel, "r", encoding="utf-8", errors="replace") as f:
                conteudo = f.read().strip()
            if corrigir_portugues:
                conteudo = _corrigir_portugues_ocr(conteudo)
            return conteudo
        except Exception:
            pass
    # Tentar também "imagem.png.ocr.txt" (convenção alternativa ao "imagem.ocr.txt")
    path_txt_alt = path_imagem + ".ocr.txt"
    if os.path.isfile(path_txt_alt):
        try:
            with open(path_txt_alt, "r", encoding="utf-8", errors="replace") as f:
                conteudo = f.read().strip()
            if corrigir_portugues:
                conteudo = _corrigir_portugues_ocr(conteudo)
            return conteudo
        except Exception:
            pass
    for suf in [".ocr.txt", "_ocr.txt"]:
        path_txt = os.path.splitext(base)[0] + suf if not base.endswith(suf) else base
        if not path_txt.endswith(".txt"):
            path_txt = os.path.splitext(base)[0] + suf
        if os.path.isfile(path_txt):
            try:
                with open(path_txt, "r", encoding="utf-8", errors="replace") as f:
                    conteudo = f.read().strip()
                if corrigir_portugues:
                    conteudo = _corrigir_portugues_ocr(conteudo)
                return conteudo
            except Exception:
                pass
    if usar_ocr:
        if usado_ocr_list is not None:
            usado_ocr_list.append(path_imagem)
        texto = _rodar_ocr_imagem(path_imagem)
        # EasyOCR carrega modelo pesado — pular em memoria-baixa e rapido
        if not texto and not _MEMORIA_BAIXA and not _RAPIDO:
            texto = _rodar_ocr_easyocr(path_imagem)
        if texto:
            if corrigir_portugues:
                texto = _corrigir_portugues_ocr(texto)
            if salvar_ocr_txt:
                path_txt = os.path.splitext(path_imagem)[0] + ".ocr.txt"
                try:
                    with open(path_txt, "w", encoding="utf-8") as f:
                        f.write(texto)
                except Exception:
                    pass
            return texto
    return f"[Anexo: {nome} — OCR pendente]"


def enriquecer_mensagem(
    msg,
    regras,
    cache_anexos,
    usar_ocr=True,
    salvar_ocr_txt=True,
    usado_ocr_list=None,
    workers=1,
    cache_pdf=None,
    cache_xlsx_indicio=None,
):
    """
    Preenche msg['texto_imagens'] a partir de email_anexos filtrados (cache).
    Prioridade: (1) PDF com texto CRD; (2) xlsx indicio-qualidade do BACEN; (3) imagens / OCR.
    Se usado_ocr_list for passada, preenche com os path das imagens em que rodou OCR (para debug).
    workers: processar anexos em paralelo (1 = sequencial; >1 acelera quando há OCR).
    """
    cache_pdf = cache_pdf if isinstance(cache_pdf, dict) else {}
    msg_id = msg.get("id") or msg.get("message_id")

    # Prioridade 2: xlsx indicio-qualidade enviado pelo BACEN (mais limpo que OCR)
    if cache_xlsx_indicio:
        xlsx_list = cache_xlsx_indicio.get(str(msg_id), [])
        if xlsx_list:
            partes_xlsx = []
            for path_xlsx, nome_xlsx in xlsx_list:
                texto_xlsx = _extrair_texto_xlsx_indicio(path_xlsx)
                if texto_xlsx:
                    partes_xlsx.append(f"--- {nome_xlsx} ---\n{texto_xlsx}")
            if partes_xlsx:
                msg["texto_imagens"] = "\n\n".join(partes_xlsx)
                texto_imagens_cache.record_from_message(msg)
                return (len(xlsx_list), usado_ocr_list) if usado_ocr_list is not None else len(xlsx_list)

    pdf_pair = _melhor_texto_crd_de_pdfs(str(msg_id), cache_pdf)
    if pdf_pair:
        nome_pdf, texto_pdf = pdf_pair
        tp = _normalizar_ocr_interface_crd(_ocr_sanitizar_prefixo_tela_crd(texto_pdf))
        if (tp or "").strip() and not _ocr_texto_eh_ruido_logo_assinatura(nome_pdf, tp):
            msg["texto_imagens"] = f"--- {nome_pdf} ---\n{tp.strip()}"
            texto_imagens_cache.record_from_message(msg)
            return (1, usado_ocr_list) if usado_ocr_list is not None else 1
    anexos = listar_anexos_imagem(msg_id, regras, cache_anexos)
    if not anexos:
        if (msg.get("texto_imagens") or "").strip():
            return (0, usado_ocr_list) if usado_ocr_list is not None else 0
        msg["texto_imagens"] = ""
        return (0, usado_ocr_list) if usado_ocr_list is not None else 0

    def extrair_um(path, nome):
        ext = os.path.splitext(nome or "")[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"):
            if os.path.isfile(path) and not _imagem_arquivo_dimensoes_conteudo_util(path):
                return (nome, None)
        texto = extrair_texto_imagem(path, nome, usar_ocr=usar_ocr, salvar_ocr_txt=salvar_ocr_txt, usado_ocr_list=usado_ocr_list)
        if texto and not (texto.strip().startswith("[Anexo:") and "OCR pendente" in texto):
            texto = _normalizar_ocr_interface_crd(_ocr_sanitizar_prefixo_tela_crd(texto))
        if texto and _ocr_texto_eh_ruido_logo_assinatura(nome, texto):
            return (nome, None)
        return (nome, texto)

    if workers is None or workers <= 1:
        resultados = [extrair_um(path, nome) for path, nome in anexos]
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(anexos))) as ex:
            futuras = {ex.submit(extrair_um, path, nome): (path, nome) for path, nome in anexos}
            resultados = [f.result() for f in as_completed(futuras)]
        # Manter ordem original dos anexos (as_completed não garante ordem)
        ordem = {nome: i for i, (path, nome) in enumerate(anexos)}
        resultados.sort(key=lambda x: ordem.get(x[0], 999))

    partes = []
    conteudos_vistos = set()
    for nome, texto in resultados:
        if texto is None:
            continue
        ts = (texto or "").strip()
        if ts.startswith("[Anexo:") and "OCR pendente" in ts:
            continue
        if ts in conteudos_vistos:
            continue
        conteudos_vistos.add(ts)
        partes.append(f"--- {nome} ---\n{texto}")
    msg["texto_imagens"] = "\n\n".join(partes)
    texto_imagens_cache.record_from_message(msg)
    return (len(anexos), usado_ocr_list) if usado_ocr_list is not None else len(anexos)


def _ocr_txt_existe(path_imagem: str) -> bool:
    """Retorna True se já existe .ocr.txt para a imagem (resultado de OCR anterior)."""
    if path_imagem.lower().endswith((".ocr.txt", "_ocr.txt")):
        return True
    # Convenção 1: imagem.png.ocr.txt
    if os.path.isfile(path_imagem + ".ocr.txt"):
        return True
    # Convenção 2: imagem.ocr.txt (sem extensão da imagem)
    raiz = os.path.splitext(path_imagem)[0]
    if os.path.isfile(raiz + ".ocr.txt") or os.path.isfile(raiz + "_ocr.txt"):
        return True
    return False


def _parse_ids_csv(s: str) -> set[str]:
    """Lista de IDs Gmail separados por vírgula (espaços ignorados)."""
    if not (s or "").strip():
        return set()
    out = set()
    for part in s.replace(";", ",").split(","):
        p = part.strip()
        if p:
            out.add(p)
    return out


def sync_texto_imagens_eventos_desde_threads(data: dict) -> int:
    """
    Copia texto_imagens das mensagens nas threads para eventos com o mesmo id
    (o modal usa threads; alguns fluxos leem eventos).
    """
    threads = data.get("threads") or []
    eventos = data.get("eventos") or []
    mapa: dict[str, str] = {}
    for t in threads:
        for msg in t.get("mensagens") or []:
            mid = str(msg.get("id") or msg.get("message_id") or "").strip()
            if not mid:
                continue
            ti = (msg.get("texto_imagens") or "").strip()
            if ti:
                mapa[mid] = msg["texto_imagens"]
    n = 0
    for ev in eventos:
        eid = str(ev.get("id") or "").strip()
        if eid in mapa:
            ev["texto_imagens"] = mapa[eid]
            n += 1
    return n


def _barra_progresso(atual: int, total: int, largura: int = 40, extra: str = "") -> str:
    """Gera string com barra de progresso ASCII para exibição no terminal."""
    if total <= 0:
        return ""
    pct = atual / total
    feito = int(largura * pct)
    barra = "#" * feito + "-" * (largura - feito)
    return f"\r  [{barra}] {atual}/{total} ({pct:.0%}){extra}   "


def main():
    global _log_file
    ap = argparse.ArgumentParser(description="Enriquecer 03 com texto extraído de anexos (imagens) via .ocr.txt ou OCR.")
    ap.add_argument("--sem-ocr", action="store_true", help="Não rodar OCR; usar só .ocr.txt existentes ou placeholder")
    ap.add_argument("--nao-salvar-ocr", action="store_true", help="Não gravar .ocr.txt ao rodar OCR (só preencher 03)")
    ap.add_argument("--no-incremental", action="store_true", help="Reprocessa todas as mensagens (padrão: incremental)")
    ap.add_argument("--salvar-a-cada", type=int, default=150, metavar="N", help="Salvar 03 a cada N mensagens processadas (default 150)")
    ap.add_argument("--workers", type=int, default=2, metavar="N", help="Anexos em paralelo por msg (default 2; use 1 se travar)")
    ap.add_argument("--workers-msg", type=int, default=2, metavar="N", help="Mensagens em paralelo (default 2; use 1 se travar)")
    ap.add_argument("--memoria-baixa", action="store_true", help="Sequencial, só Tesseract — evita Windows fechar por falta de RAM")
    ap.add_argument("--rapido", action="store_true", help="Paralelo 2x2, só PSM 6, imagens menores — mais rápido (usa mais RAM)")
    ap.add_argument("--debug", action="store_true", help="Registra tempo por mensagem e uso de OCR")
    ap.add_argument("--data", type=str, default="", metavar="DD/MM/YYYY", help="Só processar mensagens desta data (ex: 23/02/2026)")
    ap.add_argument(
        "--ids",
        type=str,
        default="",
        metavar="ID,ID,...",
        help="Só mensagens com estes ids Gmail (no 03, threads[].mensagens[].id). Combinável com --data.",
    )
    args = ap.parse_args()
    from pipeline_watchdog import iniciar_watchdog
    iniciar_watchdog(max_horas=8, nome_script="12_enriquecer_imagens")
    global _MEMORIA_BAIXA, _RAPIDO
    _MEMORIA_BAIXA = args.memoria_baixa
    _RAPIDO = args.rapido
    if _MEMORIA_BAIXA and _RAPIDO:
        _RAPIDO = False  # memoria-baixa tem prioridade
    # Sincroniza objeto de configuração
    _modo.memoria_baixa = _MEMORIA_BAIXA
    _modo.rapido = _RAPIDO
    usar_ocr = not args.sem_ocr
    salvar_ocr_txt = not args.nao_salvar_ocr
    incremental = not args.no_incremental
    salvar_a_cada = max(50, args.salvar_a_cada)
    data_filtro = None  # (dia, mes, ano) ou None = todos
    if args.data:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", args.data.strip())
        if m:
            data_filtro = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            _log(f"AVISO: --data '{args.data}' inválido; use DD/MM/YYYY. Processando todos.")
    # Quando chamado pelo pipeline (sem --data), usa DATA_COLETA_INICIO do ambiente
    # para processar só as mensagens do dia atual — evita reprocessar backlog completo.
    # Desativar com ORACULO_SCRIPT12_SEM_FILTRO_DATA=1 (ex.: para zerar backlog manualmente).
    if data_filtro is None and not os.environ.get("ORACULO_SCRIPT12_SEM_FILTRO_DATA", "").strip():
        _dc = os.environ.get("DATA_COLETA_INICIO", "").strip()
        if _dc:
            # Formato DD-MMM-YYYY (ex: 2-Jun-2026)
            _MES = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                    "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
            _m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", _dc)
            if _m:
                _mes = _MES.get(_m.group(2).lower())
                if _mes:
                    data_filtro = (int(_m.group(1)), _mes, int(_m.group(3)))
                    _log(f"   [12] Filtro de data automático via DATA_COLETA_INICIO: {_dc} → {data_filtro[0]:02d}/{data_filtro[1]:02d}/{data_filtro[2]}")
                    _log(f"   [12] Para processar backlog completo: ORACULO_SCRIPT12_SEM_FILTRO_DATA=1")
    if _MEMORIA_BAIXA:
        workers, workers_msg = 1, 1
    elif _RAPIDO:
        workers, workers_msg = 2, 2
    else:
        workers, workers_msg = max(1, args.workers), max(1, args.workers_msg)
    debug = args.debug

    if os.name == "nt":
        try:
            import ctypes
            BELOW_NORMAL = 0x4000
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), BELOW_NORMAL)
        except Exception:
            pass

    _relogio_12 = _Cron12()
    cabecalho(12, "Enriquecer Texto Imagens", periodo=os.environ.get("DATA_COLETA_INICIO", "--"))

    verificar_dependencias("12_enriquecer_ocr", requer=["09_integrar"])
    regras = carregar_regras_imagens()
    if not regras:
        _log("AVISO: IMAGENS_PARA_CADOC não encontrado; usando filtros padrão.")

    if not os.path.isfile(ARQUIVO_03):
        _log(f"Arquivo não encontrado: {ARQUIVO_03}")
        return

    _log("Carregando cache de anexos...")
    cache_anexos = _listar_todos_anexos_por_id(regras)
    cache_pdf = _listar_pdfs_por_id(regras)
    cache_xlsx_indicio = _listar_xlsx_indicio_por_id(PASTA_ANEXOS)
    total_arquivos = sum(len(v) for v in cache_anexos.values())
    _log(
        f"  {len(cache_anexos)} mensagens com imagem | {total_arquivos} imagens elegíveis"
        f" | {len(cache_pdf)} id(s) com PDF em email_anexos"
        f" | {len(cache_xlsx_indicio)} id(s) com xlsx indício-qualidade"
    )

    if usar_ocr:
        tess_ok, easy_ok, msg_diag = _diagnostico_ocr()
        if tess_ok:
            _log("  OCR: Tesseract disponível")
        elif easy_ok:
            _log("  OCR: EasyOCR disponível")
        else:
            _log("  AVISO: Nenhum OCR disponível — só .ocr.txt ou placeholder")
            if msg_diag:
                _log(f"  Diagnóstico: {msg_diag}")
            usar_ocr = False
    else:
        _log("  OCR: desativado (--sem-ocr)")

    if _MEMORIA_BAIXA:
        _log("  [memoria-baixa] Sequencial, só Tesseract, imagens até 1500px — evita pico de RAM")
    elif _RAPIDO:
        _log("  [rapido] Paralelo 2x2, só PSM 6, imagens até 1800px")
    _log(f"  Modo: {'INCREMENTAL' if incremental else 'COMPLETO'} | Workers: {workers} anexos/msg | {workers_msg} msgs paralelas | Checkpoint: a cada {salvar_a_cada} msgs")
    if data_filtro:
        _log(f"  Filtro por data: {data_filtro[0]:02d}/{data_filtro[1]:02d}/{data_filtro[2]} (só mensagens deste dia)")

    ids_set = _parse_ids_csv(args.ids)
    if ids_set:
        _log(f"  Filtro por --ids: {len(ids_set)} id(s)")

    _log("Carregando 03...")
    try:
        with open(ARQUIVO_03, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _log(f"ERRO ao carregar {ARQUIVO_03}: {e}")
        return

    threads = data.get("threads", [])
    cache_disk = texto_imagens_cache.load_por_id()
    n_restauradas = texto_imagens_cache.restaurar_threads_se_vazio(threads, cache_disk)
    if n_restauradas:
        _log(
            f"  Cache texto_imagens: {n_restauradas} mensagem(ns) repostas no 03 "
            f"(anexos ausentes; ver data/json/cache_texto_imagens_validado.json)"
        )

    # -----------------------------------------------------------------------
    # PRÉ-FILTRO: monta fila somente com (thread_idx, msg_idx, msg) que precisam processar
    # Critério de pulo (incremental):
    #   1. texto_imagens já preenchido no JSON, OU
    #   2. msg_id não tem imagens no cache, OU
    #   3. todos os anexos já têm .ocr.txt em disco (mesmo se o JSON foi regenerado)
    # -----------------------------------------------------------------------
    fila = []       # [(thread_idx, msg_idx, msg)]
    total_msg = 0
    puladas_prefilter = 0
    puladas_sem_anexo = 0
    puladas_data = 0
    puladas_incremental = 0

    for ti, thread in enumerate(threads):
        for mi, msg in enumerate(thread.get("mensagens", [])):
            total_msg += 1
            msg_id = str(msg.get("id") or msg.get("message_id") or "")

            if ids_set and msg_id not in ids_set:
                continue

            # Sem ficheiros em disco: manter texto já reposto do cache JSON (ou incremental anterior)
            if msg_id not in cache_anexos and msg_id not in cache_pdf:
                if (msg.get("texto_imagens") or "").strip():
                    puladas_incremental += 1
                    puladas_prefilter += 1
                    continue
                msg.setdefault("texto_imagens", "")
                puladas_sem_anexo += 1
                puladas_prefilter += 1
                continue

            # Filtro por data: pular se mensagem não for do dia selecionado
            if data_filtro:
                dt_msg = _extrair_data_msg(msg)
                if not dt_msg or (dt_msg.day, dt_msg.month, dt_msg.year) != data_filtro:
                    puladas_data += 1
                    puladas_prefilter += 1
                    continue

            # Modo incremental: pular se JSON já tem texto OU todos os .ocr.txt existem
            if incremental:
                if (msg.get("texto_imagens") or "").strip():
                    puladas_incremental += 1
                    puladas_prefilter += 1
                    continue
                anexos = cache_anexos.get(msg_id, [])
                if anexos and all(_ocr_txt_existe(p) for p, _ in anexos):
                    # Já há .ocr.txt para todas as imagens: lê rápido sem OCR pesado
                    fila.append((ti, mi, msg, True))  # True = só_leitura
                    continue

            fila.append((ti, mi, msg, False))  # False = pode precisar de OCR

    total_fila = len(fila)
    _log(f"\n  Total mensagens : {total_msg}")
    _log(f"  Pré-puladas     : {puladas_prefilter} (sem anexo: {puladas_sem_anexo} | fora da data: {puladas_data} | já concluído: {puladas_incremental})")
    _log(f"  A processar     : {total_fila}")

    if ids_set:
        ids_em_threads = set()
        for thread in threads:
            for msg in thread.get("mensagens", []):
                mid = str(msg.get("id") or msg.get("message_id") or "")
                if mid in ids_set:
                    ids_em_threads.add(mid)
        ausentes_threads = ids_set - ids_em_threads
        if ausentes_threads:
            _log(f"  AVISO --ids não existem em threads[].mensagens: {sorted(ausentes_threads)}")
        sem_arquivo = sorted(ids_set - set(cache_anexos.keys()) - set(cache_pdf.keys()))
        if sem_arquivo:
            _log(
                "  AVISO --ids sem imagem nem PDF em email_anexos (rodar 01 com período IMAP e "
                f"--reimport-ids …): {sem_arquivo}"
            )

    if total_fila == 0:
        n_sync = sync_texto_imagens_eventos_desde_threads(data)
        if n_sync:
            _log(f"  Sincronizado texto_imagens → eventos: {n_sync} evento(s)")
        try:
            shutil.copy2(ARQUIVO_03, ARQUIVO_03_BACKUP)
        except OSError as e_bkp:
            _log(f"  [AVISO] Backup nao criado: {e_bkp}")
        with open(ARQUIVO_03, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _log("\n[OK] Nada a enriquecer na fila; 03 gravado (sync eventos se houver).")
        return

    # -----------------------------------------------------------------------
    # PROCESSAMENTO com barra de progresso (mensagens em paralelo)
    # -----------------------------------------------------------------------
    def processar_item(item):
        ti, mi, msg, so_leitura = item
        ocr_paths = [] if debug else None
        t0 = time.perf_counter() if debug else None
        result = enriquecer_mensagem(
            msg,
            regras,
            cache_anexos,
            usar_ocr=(False if so_leitura else usar_ocr),
            salvar_ocr_txt=salvar_ocr_txt,
            usado_ocr_list=ocr_paths,
            workers=workers,
            cache_pdf=cache_pdf,
            cache_xlsx_indicio=cache_xlsx_indicio,
        )
        n = result[0] if isinstance(result, tuple) else result
        if debug and ocr_paths:
            dt = time.perf_counter() - t0
            _log(f"\n  [DEBUG] id={msg.get('id')} {n} anexo(s) {dt:.1f}s OCR={[os.path.basename(p) for p in ocr_paths[:3]]}", also_print=True)
        # Modo memoria-baixa: liberar RAM após cada mensagem
        if _MEMORIA_BAIXA:
            gc.collect()
        return n

    processadas = 0
    total_anexos = 0
    t_inicio = time.perf_counter()
    vel_suavizada = 0.0
    batch_size = min(workers_msg, total_fila)

    print("")  # linha antes da barra
    with ThreadPoolExecutor(max_workers=workers_msg) as ex_msg:
        idx = 0
        while idx < total_fila:
            batch = fila[idx:idx + batch_size]
            futuras = [ex_msg.submit(processar_item, item) for item in batch]
            for f in as_completed(futuras):
                n = f.result()
                if n:
                    total_anexos += n
                    processadas += 1

            idx += len(batch)

            # rapido: gc a cada 10 msgs enriquecidas para evitar acúmulo de RAM
            if _RAPIDO and processadas > 0 and processadas % 10 == 0:
                gc.collect()

            # Checkpoint periódico
            if processadas and processadas % salvar_a_cada == 0:
                print(f"\n  Salvando checkpoint ({processadas} processadas)...", end="", flush=True)
                try:
                    sync_texto_imagens_eventos_desde_threads(data)
                    with open(ARQUIVO_03, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f" ERRO: {e}", end="")
                gc.collect()

            # Barra de progresso
            decorrido = time.perf_counter() - t_inicio
            vel_instant = idx / decorrido if decorrido > 0.1 else 0
            alpha = 0.25
            vel_suavizada = alpha * vel_instant + (1 - alpha) * vel_suavizada if vel_suavizada else vel_instant
            vel = max(0.1, vel_suavizada)
            restante = int((total_fila - idx) / vel) if vel > 0 else 0
            extra = f" | {processadas} enriquecidas | {vel:.1f} msg/s | ~{restante}s restante"
            print(_barra_progresso(idx, total_fila, extra=extra), end="", flush=True)
            print(f"\n[12] progresso: {idx}/{total_fila} mensagens | ~{restante//60}m{restante%60:02d}s", flush=True)

    print("")  # quebra de linha após a barra

    _log("Salvando 03 e backup...")
    n_sync = sync_texto_imagens_eventos_desde_threads(data)
    if n_sync:
        _log(f"  texto_imagens copiado para {n_sync} evento(s) (mesmo id que mensagem na thread)")
    try:
        shutil.copy2(ARQUIVO_03, ARQUIVO_03_BACKUP)
    except OSError as e_bkp:
        _log(f"  [AVISO] Backup nao criado: {e_bkp}")
    with open(ARQUIVO_03, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    _resumo_12(processados=processadas, ignorados=puladas_prefilter, tempo_s=_relogio_12.elapsed)
    registrar_execucao("12_enriquecer_ocr", arquivo_saida=ARQUIVO_03)

    decorrido_total = time.perf_counter() - t_inicio
    _log("=" * 60)
    _log(f"[OK] Concluído em {decorrido_total:.1f}s")
    _log(f"  Mensagens totais      : {total_msg}")
    _log(f"  Pré-puladas           : {puladas_prefilter}")
    _log(f"  Processadas           : {processadas}")
    _log(f"  Imagens enriquecidas  : {total_anexos}")
    _log(f"  Backup                : {ARQUIVO_03_BACKUP}")
    _log("  Atualize o painel (F5) para ver o texto extraído.")
    _log("=" * 60)

    if _log_file:
        try:
            _log_file.close()
        except Exception:
            pass
        _log_file = None


if __name__ == "__main__":
    with iniciar_log_standalone(12, "enriquecer_texto_imagens"):
        main()
