"""
QA – Configuração e helpers compartilhados.

- RAIZ: raiz do projeto (para paths).
- Funções de contrato (decode MIME, deduplica CADOCs, filtro assinatura, extrair data)
  usadas pelos testes; espelham o comportamento esperado do frontend/painel.
"""
from __future__ import annotations

import os
import re
from email.header import decode_header as email_decode_header

# Raiz do projeto (pasta que contém painel_oraculo.py, data/, scripts/, etc.)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def decode_mime_header(s: str) -> str:
    """Decodifica RFC 2047 (=?charset?Q?…?= / =?charset?B?…?=). Contrato do frontend."""
    if s is None or not isinstance(s, str):
        return ""
    s = s.strip()
    if not s or "=?" not in s:
        return s
    try:
        parts = email_decode_header(s)
        out = []
        for part, charset in parts:
            if isinstance(part, bytes):
                enc = charset or "utf-8"
                try:
                    out.append(part.decode(enc, errors="replace"))
                except Exception:
                    out.append(part.decode("utf-8", errors="replace"))
            else:
                out.append(part or "")
        return "".join(out).strip() or s
    except Exception:
        return s


def deduplica_cadocs(lista_prazos: list | None, cadoc_fallback: str) -> str:
    """CADOCs únicos; fallback quando vazio. Contrato do frontend."""
    cadocs = [(p.get("cadoc") or "").strip() for p in (lista_prazos or []) if (p.get("cadoc") or "").strip()]
    unicos = list(dict.fromkeys(cadocs))
    if unicos:
        return ", ".join(unicos)
    return (cadoc_fallback or "").strip() or "—"


def cadoc_para_categoria_exibicao(cadoc: str | None) -> str:
    """Rótulo curto na tela (Operacional/Gestão): DDR, DLO, SUPORTE, etc. Chaves internas inalteradas."""
    c = (cadoc or "").strip()
    if not c:
        return "—"
    u = c.upper()
    curto = {
        "DDR_2011": "DDR",
        "DRM_2060": "DRM",
        "DLO_2061": "DLO",
        "DLI_2062": "DLI",
        "DRL_2160": "DRL",
        "4111": "4111",
        "RETORNO_BACEN": "RETORNO BACEN",
        "SUPORTE": "SUPORTE",
        "SUPORTE_GERAL": "SUPORTE",
        "S5": "S5",
    }
    return curto.get(u, c)


def filter_signature_from_attachment(corpo: str) -> str:
    """Remove linhas de assinatura; mantém conteúdo tipo TRADERS. Contrato do frontend."""
    if not corpo or not isinstance(corpo, str):
        return ""
    linhas = re.split(r"\r?\n", corpo)
    assinatura_like = [
        re.compile(r"\(\s*\d{2}\s*\)\s*\d{4,5}\s*[- ]?\d{4}"),
        re.compile(r"^\s*www\.", re.I),
        re.compile(r"\.com\.br\s*$"),
        re.compile(r"^\s*(A CONTÁBIL|RFA CONTÁBIL|Comerciante|CommERTMANDE)\s*[:.]?\s*$", re.I),
        re.compile(r"^\s*[^\s@]{1,30}\s*@\s*\S+\s*$"),
        re.compile(r"^\s*m\s+edson|edsonQ&rfa", re.I),
    ]
    email_dom_re = re.compile(r"@\S+\.(com|br|com\.br)\b", re.I)
    filtrado = []
    for linha in linhas:
        t = linha.strip()
        if not t:
            continue
        is_sig = any(r.search(t) for r in assinatura_like)
        if not is_sig and email_dom_re.search(t):
            idx_at = t.find("@")
            antes = ("" if idx_at <= 0 else t[:idx_at]).replace(" ", "").replace("\t", "")
            if len(t) <= 56 or (len(t) <= 130 and len(antes) <= 28):
                is_sig = True
        if not is_sig and len(t) < 45 and re.search(r"[\d()\-]{8,}", t):
            is_sig = True
        if not is_sig:
            filtrado.append(linha)
    return "\n".join(filtrado).strip() or ""


def extrair_data_evento(ev: dict) -> "datetime.date | None":
    """Contrato de _extrair_data_evento (painel). Extrai data de evento/mensagem."""
    if not ev:
        return None
    try:
        import datetime as dt
        import pytz
        from dateutil import parser as dateutil_parser
    except ImportError:
        return None
    tz_br = pytz.timezone("America/Sao_Paulo")
    ts = ev.get("timestamp_epoch")
    if ts is not None and ts != 0:
        n = int(ts)
        seg = n / 1000.0 if n > 1e12 else n
        d = dt.datetime.fromtimestamp(seg, tz=pytz.UTC)
        return d.astimezone(tz_br).date()
    ts_raw = (ev.get("timestamp") or "").strip()
    if ts_raw:
        try:
            return dateutil_parser.parse(ts_raw, dayfirst=True).date()
        except Exception:
            try:
                return dateutil_parser.parse(ts_raw).date()
            except Exception:
                pass
    data_iso = (ev.get("data_iso") or "").strip()
    if data_iso:
        try:
            return dateutil_parser.parse(data_iso).date()
        except Exception:
            pass
    return None
