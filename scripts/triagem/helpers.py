# -*- coding: utf-8 -*-
"""
Helpers de triagem (detectores e utilitários compartilhados).

Funções movidas de ``scripts/triagem_auto_ddr4111.py`` no Passo 2 do refactor.
O arquivo legado mantém re-exports até o Passo 11 (limpeza final).

Não contém regras específicas de categoria — só primitivos reutilizáveis:
  - parse de datas, ordenação, vista temporal de threads
  - detectores §5 (remessa F→C), §3-inv (pedido), §3.5 (reconhecimento curto),
    §4d (cliente agradece após remessa), §4f-rb (cliente confirma BACEN aceitou)
  - utilitários de cluster (núcleo de assunto, empresa-chave, fingerprint de prazos)

As regras de cada categoria (RETORNO_BACEN, DDR4111, DLO, DLI, S5, SUPORTE)
ficam em ``scripts/triagem/<categoria>.py`` e usam estes helpers.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPTS = os.path.join(BASE_DIR, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


def _debug_session_log(
    location: str,
    message: str,
    data: dict,
    *,
    hypothesis_id: str = "",
) -> None:
    """No-op. Instrumentação de depuração de uma sessão antiga (sessionId dd321b).

    Fazia ``open()+append+close`` em ``debug-dd321b.log`` para CADA thread, em CADA
    um dos 15 módulos, em CADA execução do script 11. Com varredura de antivírus/I-O
    em cada abertura, isso travava o script 11 na prática (processo ocioso esperando
    I/O por minutos). Mantida como no-op para preservar as chamadas existentes sem
    custo. Não tem função no sistema — pode ser removida junto com as chamadas depois.
    """
    return

def _parse_iso_date_field(val: Any) -> Optional[date]:
    """Prefixo ``YYYY-MM-DD`` de ``data_conclusao`` / ``data_marcacao`` / ISO."""
    if not val:
        return None
    s = str(val).strip()
    if len(s) < 10 or s[4] != "-" or s[7] != "-":
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None

def _data_fecho_auto_aguardando(r: dict) -> Optional[date]:
    return _parse_iso_date_field(r.get("data_marcacao")) or _parse_iso_date_field(
        r.get("data_ref_operacional")
    )

def _data_fecho_auto_concluido(r: dict) -> Optional[date]:
    return _parse_iso_date_field(r.get("data_conclusao")) or _parse_iso_date_field(
        r.get("data_marcacao")
    )

def _merge_registros_por_threadid(base: List[dict], novos: List[dict]) -> List[dict]:
    """Último registo por ``threadId`` ganha (novos sobrescrevem base)."""
    by: Dict[str, dict] = {}
    for r in base:
        if isinstance(r, dict) and r.get("threadId"):
            by[str(r["threadId"]).strip()] = r
    for r in novos:
        if isinstance(r, dict) and r.get("threadId"):
            by[str(r["threadId"]).strip()] = r
    return list(by.values())

def _fp_prazos(lista_prazos: Any) -> Optional[frozenset]:
    if not lista_prazos or not isinstance(lista_prazos, list):
        return None
    tuplas = []
    for x in lista_prazos:
        if not isinstance(x, dict):
            continue
        c = (x.get("cadoc") or "").strip()
        db = (x.get("data_base") or "").strip()
        pl = (x.get("prazo_limite") or "").strip()
        if not c:
            continue
        tuplas.append((c, db, pl))
    if not tuplas:
        return None
    return frozenset(tuplas)

def _parse_data_msg(msg: dict) -> Optional[date]:
    """Extrai data da mensagem tentando os campos data_iso, timestamp, data_email e timestamp_epoch."""
    from paths import parse_data_flexivel
    for campo in ("data_iso", "timestamp", "data_email", "timestamp_epoch"):
        val = msg.get(campo)
        if val:
            d = parse_data_flexivel(val)
            if d:
                return d
    return None

def _get_ultima_mensagem(thread: dict):
    """Retorna (msg, data_msg, lado) da última mensagem da thread. lado = 'CLIENTE' ou 'FINAUD'."""
    mensagens = thread.get("mensagens") or []
    if not mensagens:
        return None, None, ""

    def _ord(m):
        ep = m.get("timestamp_epoch")
        if ep is not None:
            return ep
        d = _parse_data_msg(m)
        return d.toordinal() * 86400 if d else 0

    ultima = max(mensagens, key=_ord)
    data_msg = _parse_data_msg(ultima)
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    if not lado:
        lado = (ultima.get("responsabilidade") or ultima.get("lado") or "").strip().upper()
    return ultima, data_msg, lado if lado in ("CLIENTE", "FINAUD") else ""

def _ultima_mensagem_finaud_para_cliente(thread: dict) -> Optional[dict]:
    """Última mensagem do fio com origem FINAUD e destino CLIENTE (para §5 / §5b)."""
    msgs = thread.get("mensagens") or []
    if not isinstance(msgs, list):
        return None
    for m in reversed(msgs):
        if not isinstance(m, dict):
            continue
        co = m.get("contato_origem") or {}
        cd = m.get("contato_destino") or {}
        if (co.get("lado") or "").strip().upper() != "FINAUD":
            continue
        if (cd.get("lado") or "").strip().upper() != "CLIENTE":
            continue
        return m
    return None

def get_mensagens_efetivas(msgs: List[dict]) -> List[dict]:
    """
    Retorna a lista de mensagens enriquecida com os registros do campo
    ``encaminhados`` de cada mensagem, inseridos como mensagens virtuais
    **anteriores** à mensagem que os contém.

    Objetivo: reconstruir o histórico real da conversa quando o sistema de
    captura registrou apenas o reply (Finaud → Cliente) mas o email original
    do cliente ficou embutido como citação no campo ``encaminhados``.

    Regras:
    - Não altera o JSON original — retorna nova lista em memória.
    - Mensagens virtuais têm ``_virtual: True`` para que código downstream
      possa distingui-las das registradas.
    - O lado (FINAUD / CLIENTE) é inferido pelo email; quando não identificado
      usa o destino da mensagem-pai (quem enviou antes é o destino do reply).
    - Corpo da mensagem virtual = ``encaminhados[i].corpo`` sem tratamento
      adicional (limpeza de assinatura/disclaimer fica para etapa futura).

    Uso:
        from triagem.helpers import get_mensagens_efetivas
        msgs_completas = get_mensagens_efetivas(thread.get("mensagens") or [])
        ultima = msgs_completas[-1]
    """
    def _enc_to_msg(enc: dict, msg_pai: dict) -> dict:
        de_raw = (enc.get("de") or "").strip()
        # Tenta extrair email do padrão 'Nome <email@dominio>'
        m = re.search(r"<([^>]+@[^>]+)>", de_raw)
        email = m.group(1).lower() if m else ""

        # Se não achou email, usa o destino da mensagem pai
        # (quem recebeu o reply é quem enviou o encaminhado)
        if not email:
            cd_pai = msg_pai.get("contato_destino") or {}
            email = (cd_pai.get("email") or "").lower()

        is_finaud = "@finaud.com.br" in email or "@finaudtec.com.br" in email
        lado = "FINAUD" if is_finaud else "CLIENTE"

        corpo = (enc.get("corpo") or "").strip()
        data_str = (enc.get("data_email") or "")

        return {
            "contato_origem": {"email": email, "lado": lado, "nome": de_raw},
            "contato_destino": {},
            "corpo": corpo,
            "corpo_limpo": corpo,          # sem limpeza profunda (futura melhoria)
            "data_email": data_str,
            "data_iso": data_str[:10] if len(data_str) >= 10 else "",
            "assunto": msg_pai.get("assunto", ""),
            "_virtual": True,              # marcador: não veio do JSON de mensagens
        }

    resultado: List[dict] = []
    for m in msgs:
        enc_list = m.get("encaminhados") or []
        # Encaminhados são mensagens anteriores — inserir antes do reply
        for enc in reversed(enc_list):
            vm = _enc_to_msg(enc, m)
            # Evita duplicar se o mesmo email/corpo já está na lista registrada
            corpo_vm = vm["corpo"][:80]
            ja_existe = any(
                (r.get("corpo") or "")[:80] == corpo_vm
                for r in resultado[-3:]  # verifica só as últimas 3
            )
            if not ja_existe:
                resultado.append(vm)
        resultado.append(m)

    return resultado


def _texto_fio(evento: dict, thread: Optional[dict]) -> str:
    partes: List[str] = []
    for k in ("titulo", "assunto", "corpo_limpo", "corpo"):
        v = evento.get(k)
        if isinstance(v, str) and v.strip():
            partes.append(v)
    if thread:
        for m in thread.get("mensagens") or []:
            if not isinstance(m, dict):
                continue
            for k in ("assunto", "corpo_limpo", "corpo", "snippet"):
                v = m.get(k)
                if isinstance(v, str) and v.strip():
                    partes.append(v)
    return " ".join(partes).lower()

def _data_evento(evento: dict) -> Optional[date]:
    for campo in ("data_iso", "timestamp"):
        val = (evento.get(campo) or "").strip()[:10]
        if len(val) >= 10 and val[4] == "-":
            try:
                return date.fromisoformat(val[:10])
            except ValueError:
                pass
    return None

def _thread_toca_dia_ref(thread: dict, evento: dict, dia: date) -> bool:
    if _data_evento(evento) == dia:
        return True
    for m in thread.get("mensagens") or []:
        if isinstance(m, dict) and _parse_data_msg(m) == dia:
            return True
    return False

def _thread_vista_ate_data_ref(thread: dict, dia_ref: Optional[date]) -> dict:
    """
    Com ``dia_ref``, vista do thread só com mensagens cuja data é **≤ dia_ref**
    (alinha à DATA REF do calendário / ``TRIAGEM_AUTO_DATA_REF`` — não usa mensagens «futuras»).
    Mensagem sem data parseável mantém-se (compat.). Sem ``dia_ref``, devolve o thread original.
    """
    if dia_ref is None:
        return thread
    msgs = thread.get("mensagens") or []
    if not isinstance(msgs, list):
        return thread
    out: List[dict] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        d = _parse_data_msg(m)
        if d is None or d <= dia_ref:
            out.append(m)
    if not out:
        th2 = dict(thread)
        th2["mensagens"] = []
        return th2
    if len(out) == len(msgs):
        return thread
    th2 = dict(thread)
    th2["mensagens"] = out
    return th2

def _transmitido_bacen(texto: str) -> bool:
    return bool(
        re.search(
            r"transmitido[s]?\s+(no|ao|para\s+o)\s+(bacen|bc\b|banco\s+central)"
            r"|enviados?\s+(ao|no|para\s+o)\s+(bacen|bc\b|banco\s+central)"
            r"|transmitidos?\s+na\s+data\s+de\s+hoje"
            r"|submetidos?\s+ao\s+(bacen|bc\b)"
            r"|arquivos?\s+(foram?\s+)?transmitidos?"
            r"|j[aá]\s+transmiti\b|j[aá]\s+transmitimos\b"
            r"|transmitidos?\s+com\s+sucesso"
            r"|j[aá]\s+foi\s+transmitido"
            r"|arquivo\s+reenviado",
            texto,
            re.I,
        )
    )

def _strip_enc_assunto(assunto: str) -> str:
    """Remove cadeia inicial Re:/Fw:/Enc: (iterativo)."""
    s = (assunto or "").strip()
    for _ in range(8):
        s2 = re.sub(r"^(re|fw|fwd|enc|rv)\s*:\s*", "", s, count=1, flags=re.I).strip()
        if s2 == s:
            break
        s = s2
    return s

def _finaud_texto_e_pedido_insumo_ao_cliente(ult: dict) -> bool:
    """
    F→C cujo texto é pedido de insumos / DDRs ao cliente (§3-inv), **sem** depender de §5/5b/5c.
    Usado para vetar falso «§5 remessa» (ex.: bloco «Data de envio ao Banco Central» em lista de
    prazos DDR no mesmo e-mail de «por gentileza enviar…»).
    """
    if not _ultima_e_finaud_para_cliente(ult):
        return False
    corpo = (
        (ult.get("corpo_limpo") or ult.get("corpo") or "")
        + " "
        + (ult.get("assunto") or "")
    ).lower()
    # Cobertura de plural: "encaminhar AS posições", "enviar OS arquivos".
    # Cobertura de pontuação: "Por gentileza, encaminhar/enviar/informar" (vírgula após gentileza).
    return bool(
        re.search(
            r"pe[cç]o\s+[aà]\s+gentileza|pe[cç]o\s+a\s+gentileza|"
            r"disponibilidade\s+para\s+falarmos|tem\s+disponibilidade\s+para\s+falar|"
            r"por\s+gentileza[\s,]*(?:enviar|encaminhar|informar|envie|encaminhe)|"
            r"poderia\s+encaminhar|consegue\s+encaminhar|"
            r"(?<!por )encaminhar\s+(?:a|as|o|os)\s+(?:posi|remessa|4111|ddr|arquivo)|"
            r"enviar\s+(?:o|os|a|as)\s+arquivo|"
            r"por\s+favor.{0,40}encaminhar|"
            r"enviar\s+para\s+c[áa]lculo|enviar\s+para.{0,25}c[áa]lculo|"
            r"precisamos.{0,50}enviar|solicitamos|"
            r"falta\s+.{0,50}encaminhar|falta\s+.{0,30}planilha|"
            r"por\s+gentileza.{0,30}informar|poderia.{0,30}informar|"
            r"poderia\s+(?:nos\s+)?(?:informar|indicar|confirmar)\s+qual|"
            # Finaud pede que cliente transmita/responda ao BACEN (#Grupo2-1caso 2026-06-11)
            r"por\s+gentileza[\s,].{0,30}?transmita|"
            r"transmita\s+.{0,80}?(bacen|banco\s+central|bc\b|sta)|"
            r"transmita\s+a\s+vers[aã]o|"
            r"entre\s+em\s+contato\s+com\s+o\s+(banco\s+central|bacen)|"
            r"solicitar\s+a\s+dispensa|"
            r"por\s+gentileza.{0,40}responder?\s+.{0,30}?(bacen|banco\s+central|bc\b|inconsist)",
            corpo,
            re.I,
        )
    )

def _sec5_remessa_finaud(ultima: dict) -> bool:
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    cd = ultima.get("contato_destino") or {}
    lo = (co.get("lado") or "").strip().upper()
    ld = (cd.get("lado") or "").strip().upper()
    if lo != "FINAUD" or ld != "CLIENTE":
        return False
    # Pedido de insumos (prazos BC, etc.) nunca é remessa concluída §5
    if _finaud_texto_e_pedido_insumo_ao_cliente(ultima):
        return False
    # Não juntar ``corpo`` bruto (Gmail) com a cadeia completa: a citação (De:/Em …) traz
    # assuntos «Erro DLO» e corpos «remessa de dezembro» do histórico — a regex
    # ``\b(dlo|dli)\b.{0,40}?(dezembro|…)`` ligava falso positivo a uma resposta
    # «em análise, retornaremos» (BCP RWAOPAD, 2026-04). Usar só trecho *acima* da
    # citação + ``snippet`` + ``assunto``; se ``corpo_limpo`` vazio, topo do ``corpo``.
    corpo_topo = (ultima.get("corpo_limpo") or "").strip()
    if not corpo_topo:
        corpo_topo = _corpo_superior_a_citacao_encadeada(ultima.get("corpo") or "")
    partes: List[str] = []
    if corpo_topo:
        partes.append(corpo_topo)
    for k in ("snippet", "assunto"):
        v = ultima.get(k)
        if isinstance(v, str) and v.strip():
            partes.append(v.strip())
    corpo = " ".join(partes).lower()
    # «Segue anexo», «Segue em anexo», «Seguem os anexos», «segue o ddr» (texto real do Gmail usa «em»).
    # «Encaminho, em anexo», «encaminho em anexo os documentos» — padrão de remessa sem «segue».
    # RETORNO/DLO: «arquivos DLO e DLI», «substituição … Banco Central».
    # Importante: usar \b(segue|seguem)\b — sem isso, «Consegue encaminhar…» gera falso positivo
    # (a substring «segue» existe dentro de «Conse**gue**») e classifica pedido ao cliente como §5.
    if not re.search(
        r"\b(segue|seguem)\b.{0,100}?anexos?\b"
        r"|\b(segue|seguem)\b.{0,100}?(os\s+)?arquivos"
        r"|\b(segue|seguem)\b.{0,60}?(dlo|dli|bacen|banco\s+central)"
        r"|\bsegue\s+o\s+ddr\b"
        r"|\b(segue|seguem)\b.{0,80}?posic[aã][oõ](?:es)?\s+de\s+c[aâ]mbio"
        r"|\b(segue|seguem)\b.{0,80}?extratos?\b"
        r"|\b(segue|seguem)\b.{0,80}?aplicac[oõ][eẽ]?s?\b"
        r"|encaminh\w*\s*,?\s*(em\s+)?anexo"
        r"|substitui[cç][aã]o.{0,180}?(bacen|banco\s+central)"
        r"|\b(dlo|dli)\b.{0,40}?(dezembro|envio|bacen|substitui)"
        r"|(para\s+)?envio\s+ao\s+banco\s+central",
        corpo,
        re.I | re.DOTALL,
    ):
        return False
    return True

def tem_anexo_cadoc(mensagem: dict, cadoc: str) -> bool:
    """
    Retorna True se a mensagem contém ao menos um anexo cujo nome indica
    que é o arquivo oficial do cadoc (ZIP ou planilha enviada pela Finaud).

    Funciona com o campo ``anexos_detectados`` propagado pelo script 09 a
    partir do JSON 01. Cada entrada é ``{"nome": "<nome_em_minusculo>"}``.

    Regra: o nome do arquivo deve conter ao menos um dos termos do cadoc.
    Isso evita que anexos genéricos (``balancete.xlsx``, ``image.png``) sejam
    considerados como envio de remessa regulatória.

    Categorias sem arquivo ZIP (FORCAPITAL, DRSAC): sempre retorna False —
    a detecção por texto é o caminho único para essas categorias.

    S5 é uma exceção: a Finaud entrega o Relatório Quantitativo em PDF ou Excel
    (não ZIP). O termo "quantitativo" é específico o suficiente para não confundir
    com PDFs de balancete enviados pelos clientes.
    """
    _TERMOS: dict[str, list[str]] = {
        "DDR_2011":  ["ddr", "2011"],
        "DRL_2160":  ["drl", "2160"],
        "DLO_2061":  ["dlo", "2061", "cos4010", "cos4016", "lec"],
        "DLI_2062":  ["dli", "2062"],
        "DRM_2060":  ["drm", "2060"],
        "4111":      ["4111"],
        "S5":        ["quantitativo"],
    }
    # S5 usa PDF/Excel; demais CADOCs usam ZIP/planilha (nunca PDF — evita confundir
    # com PDFs de balancete que os clientes enviam como insumo)
    _EXTENSOES_S5  = (".pdf", ".xls", ".xlsx")
    _EXTENSOES_ZIP = (".zip", ".xls", ".xlsx", ".csv", ".txt")

    termos = _TERMOS.get(cadoc)
    if not termos:
        return False
    extensoes = _EXTENSOES_S5 if cadoc == "S5" else _EXTENSOES_ZIP
    for anx in (mensagem.get("anexos_detectados") or []):
        nome = (anx.get("nome") or anx.get("nome_original") or "").lower()
        if not nome:
            continue
        if not any(nome.endswith(ext) for ext in extensoes):
            continue
        if any(t in nome for t in termos):
            return True
    return False


def _sec5c_finaud_corpo_conclusivo(ultima: dict) -> bool:
    """
    Finaud → cliente com texto de encerramento sem «segue anexo» nem «RES:» no assunto
    (ex.: «A opção … já foi cadastrada»).
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    cd = ultima.get("contato_destino") or {}
    if (co.get("lado") or "").strip().upper() != "FINAUD":
        return False
    if (cd.get("lado") or "").strip().upper() != "CLIENTE":
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip().lower()
    if len(corpo) < 18:
        return False
    return bool(
        re.search(
            r"já\s+foi\s+cadastrad|já\s+cadastrad|cadastrad[ao]\s+com\s+sucesso|"
            r"cadastro\s+realizad|já\s+está\s+disponível\s+para|"
            r"atividade\s+está\s+conclu|encerramos\s+por\s+aqui",
            corpo,
            re.I,
        )
    )

def _finaud_entrega_conclusiva(ultima: dict) -> bool:
    """
    Detecta última mensagem F→C (ou F→F) que representa entrega/conclusão da demanda.

    Cobre os casos onde o sistema classificaria como ACAO_INTERNA mas a mensagem
    é na verdade uma entrega final:
      - "conforme solicitado, segue..."
      - "aceito pelo BACEN / aceito no STA"
      - "segue o protocolo DRL/DDR/DLO enviado e aceito"
      - "providenciamos o reset / criamos os acessos"
      - "remessa enviada / transmitido"
      - "segue anexo" (quando remetente é Finaud)

    Não dispara para F→F onde há pergunta aberta ou pedido de confirmação.

    Identificado em auditoria de 18/05/2026 — 9 casos ACAO_INTERNA incorretos.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    # Exige que remetente seja Finaud
    is_finaud = lado == "FINAUD" or "@finaud.com.br" in email or "@finaudtec.com.br" in email
    if not is_finaud:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if len(corpo) < 10:
        return False
    # Anti-falsos-positivos por contexto enganoso
    # "aceito pelo BACEN" dentro de explicação sobre indício equivocado = não conclusivo
    if re.search(r"equivocad|indício.*equivoc|dispara.*equivoc", corpo, re.I) and \
       re.search(r"aceito\s+(pelo\s+bacen|no\s+sta)", corpo, re.I):
        return False
    # "providenciarmos" (futuro condicional) ≠ "providenciamos" (passado confirmação)
    if re.search(r"\bprovidenciarmos\b", corpo, re.I):
        return False
    # "para (que) providenciamos o" = condicional/subjuntivo, não ação já concluída
    if re.search(r"para\s+(que\s+)?providenciamos\s+o", corpo, re.I):
        return False
    return bool(
        re.search(
            # Entrega conforme solicitado
            r"conforme\s+solicitado.{0,80}?(segue|encaminh|providenci|reset|acesso|remessa|arquivo|relat)"
            r"|conforme\s+acordado.{0,80}?(segue|encaminh)"
            # Aceite pelo BACEN / STA
            r"|aceito\s+(pelo\s+bacen|no\s+sta)"
            r"|enviado\s+e\s+aceito\s+(pelo\s+bacen|no\s+sta)"
            r"|arquivo.{0,30}?aceito.{0,30}?(bacen|sta)"
            r"|foram\s+aceitos\s+no\s+sta"
            # Protocolo enviado
            r"|segue\s+o\s+protocolo\s+(do\s+)?(drl|ddr|dlo|drm|4111)"
            r"|protocolo\s+\d{5,}.{0,60}?(aceito|enviado)"
            r"|segue.{0,20}?protocolos?\s+dos\s+envios"
            # Cadastro/importação concluídos (Finaud informa que fez)
            r"|as\s+op.{0,10}?es\s+(de\s+a.{0,5}?es\s+)?j.{1,3}?\s+(foram|est.{1,5}?)\s+cadastradas?"
            r"|j.{1,3}?\s+(est.{1,5}?\s+)?cadastrad.{1,5}?\s+no\s+sistema"
            r"|providenciamos\s+a\s+importa.{1,5}?o"
            r"|importamos\s+o\s+(arquivo|cosif|cos4010)"
            # Providências concluídas
            r"|providenciamos\s+o\s+(reset|acesso|cadastro|envio)"
            r"|criamos\s+os\s+acessos"
            r"|acabei\s+de\s+resetar\s+a\s+senha"
            r"|providenciei\s+um\s+novo\s+reset"
            r"|estar.{1,5}?\s+recebendo\s+um\s+novo\s+e.mail\s+com\s+a\s+senha"
            r"|realizei\s+a\s+cria.{1,5}?o\s+do\s+(seu\s+)?usu.{1,5}?rio"
            # Remessa/transmissão/envio concluído
            r"|remessa\s+(drl|ddr|dlo|drm|2011|2060|2061|2062|2160)\s+(enviada|transmitida)"
            r"|transmitid[ao]\s+(ao|para\s+o)\s+(bacen|banco\s+central)"
            r"|enviado\s+ao\s+(bacen|banco\s+central|bc)"
            r"|j.{1,3}?\s+foi\s+enviado\s+ao\s+banco\s+central"
            r"|documento\s+j.{1,3}?\s+foi\s+enviado\s+ao\s+banco\s+central"
            r"|os\s+ajustes\s+foram\s+realizados\s+e\s+o\s+documento\s+j.{1,3}?\s+foi\s+enviado"
            r"|arquivo\s+de\s+remessa\s+.{0,30}?\s+como\s+substitui.{1,5}?o.{0,60}?devidas\s+altera"
            # Relatório atualizado e enviado ao BC
            r"|relat.{1,10}?\s+foi\s+atualizado\s+e\s+enviado\s+ao\s+banco\s+central"
            # Transmissão de remessa concluída (ex: "Providenciamos a transmissão")
            r"|providenciamos\s+a\s+transmiss.{1,5}?o"
            r"|j.{1,3}?\s+enviamos\s+(a\s+voc.{1,3}?|ao\s+(bacen|bc|banco))"
            # Segue/seguiu anexo (Finaud enviando relatório/arquivo ao cliente)
            r"|\bsegue\s+(em\s+)?anexo\b"
            r"|\bseguiu\s+(em\s+)?anexo\b"
            r"|\bseguiu\s+.{0,30}?corre.{1,5}?es\b"
            # Enviado ao STA (Sistema de Transmissão de Arquivos BCB)
            r"|enviados?\s+ao\s+sta\b"
            r"|enviei\s+ao\s+sta\b"
            r"|gerado.{0,40}?e\s+enviado\s+ao\s+sta\b"
            # Cálculos/relatórios disponíveis para consulta na tela do sistema
            r"|j[aá]\s+est[aã]o\s+dispon[ií]veis\s+para\s+consulta\s+e\s+an[aá]lise\s+na\s+tela"
            # Já encaminhei as remessas ao STA/BACEN
            r"|j.{1,3}?\s+encaminhei\s+as\s+remessas.{0,60}?(sta|bacen|banco\s+central)"
            # Foi enviado como substituição (remessa de substituição transmitida)
            r"|foi\s+enviado\s+.{0,60}?como\s+substitui.{1,5}?o"
            r"|foi\s+enviado\s+.{0,30}?(arquivo|remessa)\s+de\s+(remessa|substitui.{1,5}?o)"
            # Finaud confirma ação concluída: "Ok, feito." / "Feito."
            r"|\bfeito\s*[,!.]"
            # ----------------------------------------------------------------
            # Grupo 1 — Fix interno confirmado (adicionado 2026-05-25)
            # "os ajustes sistêmicos [para solucionar X] foram concluídos"
            # Cobre variações com texto entre "sistêmicos" e "foram concluídos"
            # ----------------------------------------------------------------
            r"|ajustes\s+sist[eê]micos.{0,80}?foram\s+conclu[ií]dos"
            # ----------------------------------------------------------------
            # Grupo 2 — Finaud realizou ação concreta (adicionado 2026-05-25)
            # ----------------------------------------------------------------
            r"|realizei\s+as\s+devidas\s+corre[cç][oõ]es"
            r"|fiz\s+as\s+devidas\s+altera[cç][oõ]es"
            r"|a\s+pend[eê]ncia\s+est[aá]\s+sanada"
            r"|acabou\s+de\s+(te\s+|lhe\s+)?enviar\s+a\s+nova\s+vers[aã]o"
            # ----------------------------------------------------------------
            # Grupo 3 — Cadastro/tarefa concluída (#PF46 2026-06-10)
            # "as ações já foram cadastradas" / "está cadastrada"
            # ----------------------------------------------------------------
            r"|as\s+a.{1,5}?es\s+j.{1,3}?\s+foram\s+cadastradas?"
            r"|\best.{1,3}?\s+cadastrad[ao]\b"
            # ----------------------------------------------------------------
            # Grupo 4 — Resolução de ajuste sistêmico (auditoria 2026-06-13)
            # "foi solucionado o ajuste sistêmico"
            # ----------------------------------------------------------------
            r"|foi\s+solucionado\s+o\s+ajuste\s+sist[eê]mico"
            r"|foi\s+solucionado\s+o\s+ajuste\s+rela"
            r"|o\s+problema\s+foi\s+resolvido"
            # ----------------------------------------------------------------
            # Grupo 5 — Instrução de preenchimento entregue (auditoria 2026-06-13)
            # "segue a instrução de preenchimento" / "segue transcrito o resultado da pesquisa"
            # ----------------------------------------------------------------
            r"|segue\s+a\s+instru[çc][aã]o\s+de\s+preenchimento"
            r"|segue(m)?\s+as\s+instru[çc][oõ]es\s+de\s+preenchimento"
            r"|segue\s+transcrito\s+.{0,30}?resultado\s+da\s+pesquisa"
            r"|segue\s+uma\s+an[aá]lise\s+detalhada"
            # ----------------------------------------------------------------
            # Grupo 6 — Entrega de Cadoc/4111 ao cliente para envio ao BACEN (auditoria 2026-06-13)
            # "seguem Cadoc's 4111 dos dias ... para envio ao BACEN"
            # Finaud gerou os relatórios CADOC 4111 e está entregando ao cliente
            # ----------------------------------------------------------------
            r"|segue(m)?\s+cadoc.{0,60}?(?:bacen|banco\s+central|envio)"
            r"|segue(m)?\s+cadoc.{0,10}?4111"
            r"|segue\s+cadoc\s+4111"
            # ----------------------------------------------------------------
            # Grupo 7 — Orientação do BC repassada / Confirmação de adequação (2026-06-14)
            # "Segue abaixo a orientação do BC sobre a crítica X" → Finaud repassou instrução, encerrou
            # "Atende sim" (curto, cliente confirmou adequação) — veto se seguido de "mas"/"porém"
            # ----------------------------------------------------------------
            r"|segue\s+abaixo\s+a\s+orienta[çc][aã]o\s+do\s+bc\b"
            r"|segue\s+a\s+orienta[çc][aã]o\s+do\s+(bacen|banco\s+central)\b"
            r"|(?<!mas\s)(?<!por[eé]m\s)\batende\s+sim\b(?!\s*[,.]?\s*(mas|por[eé]m))"
            # Grupo 8 — Finaud envia projeção/análise financeira ao cliente (P-AUD-08, 2026-06-29)
            # "Estamos enviando em anexo a projeção..." / "Gostaria de compartilhar os detalhes da estimativa..."
            r"|\benviando\s+em\s+anexo\b"
            r"|gostaria\s+de\s+compartilhar\s+os\s+detalhes\s+da\s+estimativa"
            # ----------------------------------------------------------------
            # Grupo 9 — Finaud confirma que não há ação pendente (P-AUD-03, 2026-06-29)
            # "Não houve alteração na remessa" / "Não há nada a fazer" / "Não há pendência"
            # Finaud encerrou explicando que o assunto já está resolvido ou não requer ação.
            # ----------------------------------------------------------------
            r"|n[aã]o\s+houve\s+altera[cç][aã]o\s+na\s+remessa"
            r"|n[aã]o\s+h[aá]\s+nada\s+a\s+(fazer|retransmit|corrigir|ajustar)"
            r"|n[aã]o\s+h[aá]\s+pend[eê]ncia[s]?\b"
            r"|n[aã]o\s+h[aá]\s+nenhuma\s+pend[eê]ncia",
            corpo,
            re.I | re.DOTALL,
        )
    )


def _finaud_instruiu_cliente(ultima: dict) -> bool:
    """
    Detecta última mensagem F→C onde Finaud deu instruções conclusivas ao cliente.

    Diferente de ``_finaud_entrega_conclusiva`` (que detecta entrega física),
    esta função detecta o padrão "Finaud orientou claramente, bola no cliente":
      - "Para solucionar [X], [ação concreta]"
      - "gere/transmita como Substituição/Alteração"
      - "responda via CRD"
      - "já constam sanadas / podem desconsiderar"
      - "já pode ser providenciado / prosseguir com os cálculos"
      - "Verifique [X] e qualquer dúvida retorne"

    Vetos (Finaud ainda no processo):
      - "estamos acompanhando" — fix interno ainda em teste
      - "consegue/poderia verificar" — pergunta sem instrução definida
      - "aguardamos / aguarde" — Finaud esperando algo
      - "nos encaminhe" — cliente deve enviar algo À Finaud (§3-inv)

    Identificado em auditoria 2026-05-25 — 19 casos G3 incorretos como AGUARDANDO.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_finaud = lado == "FINAUD" or "@finaud.com.br" in email or "@finaudtec.com.br" in email
    if not is_finaud:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if len(corpo) < 20:
        return False

    # --- Vetos ---
    if re.search(r"estamos\s+acompanhando", corpo, re.I):
        return False
    if re.search(r"consegue\s+verificar|poderia\s+verificar", corpo, re.I):
        return False
    if re.search(r"\baguardamos\b|\baguarde\b", corpo, re.I):
        return False
    if re.search(r"verificaremos\s+internamente|analisaremos\s+intern", corpo, re.I):
        return False
    # "nos encaminhe" = cliente deve enviar algo à Finaud → §3-inv
    if re.search(r"\bnos\s+encaminhe\b|encaminhe.{0,40}?para\s+providenci", corpo, re.I):
        return False

    return bool(re.search(
        # Sinal A: "para solucionar" + verbo de ação (imperativo ou infinitivo)
        r"para\s+solucionar.{0,300}?"
        r"\b(transmita|transmitir|calcule|calcular|ger(e|ar)\b|importe|importar"
        r"|encaminhe|encaminhar|acesse|acessar|prossiga|prosseguir|responda|responder)"
        # Sinal B: gere/transmita/gerar/transmitir + substituição/alteração
        r"|(ger(e|ar)|transmita|transmitir).{0,80}?(substitui[çc][aã]o|altera[çc][aã]o)"
        # Sinal C: "responda via CRD" (sem "para solucionar" obrigatório)
        r"|responda\s+via\s+(o\s+)?crd"
        # Sinal D: "utilize o botão [incluir resposta]"
        r"|utilize\s+o\s+bot[aã]o"
        # Sinal E: problema já resolvido, cliente pode desconsiderar
        r"|j[aá]\s+const[aã]m\s+sanadas|podem\s+desconsiderar"
        # Sinal F: "já pode ser providenciado" / "prosseguir com os cálculos"
        r"|j[aá]\s+pode\s+(ser\s+)?providenciado"
        r"|prosseguir\s+com\s+os\s+c[aá]lculos"
        # Sinal G: "Verifique [X]" + "qualquer dúvida retorne"
        r"|\bverifique\b.{0,300}?qualquer\s+d[uú]vida\s+retorne"
        # Sinal H: Instrução de navegação no sistema (caminho passo-a-passo)
        # "faça o seguinte caminho. Risk Driver -> painel de controle -> ..."
        r"|fa[çc]a\s+o\s+seguinte\s+caminho"
        r"|fa[çc]a\s+o\s+seguinte\s+percurso"
        # Sinal I: Instrução passo-a-passo com verbos de ação sequenciais
        # "Clique no botão + ... editar ... salve"
        r"|clique\s+no\s+bot[aã]o.{0,300}?salve\b"
        r"|clique\s+em\s+.{0,100}?selecione\s+.{0,100}?salve\b"
        # Sinal J: Redirect para contabilidade (G4 — Finaud orientou e encaminhou)
        # "Verifique com a contabilidade" / "precisa solicitar ao contador"
        r"|verifique\s+com\s+a\s+contabilidade"
        r"|solicitar\s+ao\s+contador\s+para\s+registrar"
        r"|encaminhe\s+(para\s+)?(a\s+)?sua\s+contabilidade"
        r"|encaminhe\s+(para\s+)?a\s+contabilidade\b"
        # Sinal K: "para solucionar" + precisará/deverá + verbo de ação
        # Cobre explicações conclusivas onde o verbo está no futuro ("precisará seguir")
        # Confirmado em 2026-06-27 — caso Azumidtvm RETORNO_BACEN
        r"|para\s+solucionar.{0,300}?\b(precisar[aá]|dever[aá])\s+"
        r"(seguir|importar|transmitir|corrigir|ajustar|encaminhar|verificar|acessar|gerar|calcular)"
        # Sinal L: Finaud instrui habilitação de transação no STA/Autran (P-AUD-01, 2026-06-29)
        # "Para efetuar a habilitação, o Máster, por meio do sistema Autran..."
        r"|para\s+efetuar\s+a\s+habilita[çc][aã]o.{0,300}?(autran|sta\b|slim800)",
        corpo,
        re.I | re.DOTALL,
    ))


def _finaud_agendou_reuniao(ultima: dict) -> bool:
    """
    Detecta última mensagem F→C onde Finaud confirmou reunião agendada com o cliente.

    Cobre os casos onde a Finaud aceitou o horário sugerido ou confirmou disponibilidade
    para reunião — demanda encerrada do lado da Finaud, bola no cliente para enviar convite.
      - "pode ser nos horários sugeridos... à disposição"
      - "Sim tenho, pode enviar o convite"
      - "Podemos agendar sim... disponibilidade"

    Vetos: presença de pergunta aberta ou pedido de confirmação ainda pendente.

    Identificado em 2026-06-27 — casos Saygogroup DDR_2011 e BGC FORCAPITAL.
    Gera regra R6 no motor.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_finaud = lado == "FINAUD" or "@finaud.com.br" in email or "@finaudtec.com.br" in email
    if not is_finaud:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if len(corpo) < 5:
        return False

    # Vetos — Finaud ainda pedindo algo
    if re.search(r"\baguardamos\b|\baguarde\b|\bpor\s+gentileza\b", corpo, re.I):
        return False

    return bool(re.search(
        # "pode ser nos horários sugeridos"
        r"pode\s+ser\s+nos\s+hor[aá]rios"
        # "pode enviar o convite"
        r"|pode\s+enviar\s+o\s+convite"
        # "podemos agendar sim" / "podemos sim"
        r"|podemos\s+(agendar\s+)?sim\b"
        # "temos a parte da manhã / temos disponibilidade"
        r"|temos\s+(a\s+parte\s+da\s+manh[aã]|a\s+tarde|disponibilidade)"
        # "sim tenho" (confirmando disponibilidade de agenda)
        r"|^sim\s+tenho\b",
        corpo,
        re.I | re.DOTALL,
    ))


def _ff_comunicado_interno(ultima: dict, assunto: str = "") -> bool:
    """Retorna True se o último e-mail é F→F informativo/comunicado sem demanda de resposta.

    Captura avisos automáticos do sistema, e-mails de teste, comunicados de RH/TI
    e distribuições internas de normas regulatórias — situações em que ninguém de fora
    da Finaud precisa responder e o ciclo da thread está encerrado.

    Exemplos reais: alertas "Nenhum documento novo ou alterado..." (gerados automaticamente),
    assunto "teste", comunicado de 13º salário, bolão Mega Sena, "Divulgação interna Finaud".
    """
    co = ultima.get("contato_origem") or {}
    if co.get("lado") != "FINAUD":
        return False

    corpo = (ultima.get("corpo_limpo") or "").strip()
    assunto_l = assunto.lower()
    corpo_l = corpo.lower()
    combined = assunto_l + " " + corpo_l

    # Anti-FP: pedido/solicitação embutida → não é comunicado puro
    if re.search(
        r"\b(por\s+gentileza|solicito|solicitar|verificar|encaminhar|por\s+favor|preciso|aguardo|peço)\b",
        combined, re.I
    ):
        return False

    # Anti-FP: pergunta explícita → há demanda
    if "?" in corpo:
        return False

    # Padrão 1: e-mail gerado automaticamente pelo sistema de monitoramento
    if re.search(r"gerado\s+automaticamente\s+pelo\s+sistema\s+de\s+monitoramento", combined, re.I):
        return True

    # Padrão 2: e-mail de teste (assunto = "teste")
    if re.search(r"^\s*teste\s*$", assunto_l):
        return True

    # Padrão 3: comunicado de RH (adiantamento 13º salário)
    if re.search(
        r"13[oº°]\s*sal[aá]rio|adiantamento\s+d[ao]s?\s+(?:1[aª]\s+parcela|parcela).*sal[aá]rio"
        r"|sal[aá]rio.*adiantamento",
        combined, re.I
    ):
        return True

    # Padrão 4: e-mails pessoais/sociais sem demanda de trabalho
    if re.search(r"\b(mega\s+sena|bol[aã]o)\b", combined, re.I):
        return True

    # Padrão 5: distribuição interna de normas regulatórias
    if re.search(r"divulga[çc][aã]o\s+interna\s+finaud", combined, re.I):
        return True

    # Padrão 6: comunicado de infraestrutura/TI interno
    if re.search(r"centraliza[çc][aã]o\s+das\s+solicita[çc][oõ]es\s+de\s+suporte", combined, re.I):
        return True

    return False


def _cliente_confirmou_solicitacao(ultima: dict) -> bool:
    """Retorna True se o cliente confirmou que executou a ação solicitada pela Finaud.

    Diferente de entrega de dado (R2): aqui o cliente relata que FEZ algo
    (reprocessou, reenviou, executou o processo) — não apenas envia um arquivo para análise.
    Exemplos reais: "Processo efetuado e reenviado o arquivo" (Iguá Corretora),
    "Arquivo enviado na data de hoje" (Banvox após Finaud enviar relatório substituto).
    """
    co = ultima.get("contato_origem") or {}
    if co.get("lado") != "CLIENTE":
        return False
    corpo = (ultima.get("corpo_limpo") or "").strip()
    principal = _corpo_superior_a_citacao_encadeada(corpo) or corpo
    # Limpar ?? (emojis mal codificados) e truncar em 500 chars
    principal = re.sub(r"\?\?+", "", principal)[:500]

    # Anti-FP: entrega de dado — "segue", "em anexo", "segue em anexo", "seguem os documentos"
    if re.search(
        r"\b(segue[ms]?|em\s+anexo|encaminh|planilha|relat|extratos?|arquivo\s+segue)\b",
        principal, re.I
    ):
        return False
    # Anti-FP: pedido/solicitação embutido
    if re.search(
        r"\b(solicito|gostaria|poderia|preciso|aguardo|necessito|por\s+favor|peço|peço\s+que)\b",
        principal, re.I
    ):
        return False

    # Padrões de confirmação de execução
    return bool(re.search(
        r"\bprocesso\s+efetuado\b"
        r"|\b(?:arquivo|doc(?:umento)?s?)\s+(?:re-?enviado|reenviado|transmitido|enviado\s+(?:hoje|na\s+data\s+de\s+hoje|conforme\s+orientad|conforme\s+solicitad))\b"
        r"|\breenviado\s+o\s+arquivo\b"
        r"|\bfoi\s+(?:reprocessado|reenviado|re-?transmitido|executado|realizado)\b"
        r"|\b(?:realizado|executado|efetuado|concluído)\s+conforme\s+(?:solicitado|orientado|instrução|pedido)\b"
        r"|\b(?:reprocessado\s+e\s+reenviado|reenviado\s+e\s+reprocessado)\b",
        principal, re.I
    ))


def _exclui_pergunta_social(texto: str) -> bool:
    """Retorna True se o único '?' presente é reciprocidade social casual ('e você?', 'tudo bem?').

    Permite que _cliente_agradecimento_conclusivo não vete mensagens onde o cliente
    agradece e, por cortesia, devolve a saudação — sem abrir nenhuma pendência de negócio.
    Exemplos: "Muito obrigada e você?", "Tudo sim, e você? Obrigada!!", "Tudo bem? Obrigado."
    """
    sem_social = re.sub(
        r"\be\s+voc[eê]\s*\?|\btudo\s+bem\s*\?|\btudo\s+certo\s*\?|\bcomo\s+vai\s*\?|\btudo\s+e\s+voc[eê]\s*\?",
        "",
        texto,
        flags=re.I,
    )
    return "?" not in sem_social


def _cliente_agradecimento_conclusivo(ultima: dict) -> bool:
    """
    Detecta última mensagem C→F que é agradecimento puro sem pedido adicional.
    Quando o cliente só agradece/confirma sem fazer perguntas ou enviar dados,
    a demanda está encerrada → CONCLUÍDO.

    Exemplos: "Deu certo! Muito obrigado pela ajuda.", "Perfeito, já consegui gerar o DLO!",
              "Ok, funcionou. Obrigada!", "Resolvido, obrigado."

    Regra: última msg do CLIENTE, corpo curto (< 500 chars), sem '?', sem envio de dados,
    com termos de agradecimento/confirmação.

    Auditoria 18/05/2026.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_cliente = lado == "CLIENTE" or (
        "@finaud.com.br" not in email and "@finaudtec.com.br" not in email and lado != "FINAUD"
    )
    if not is_cliente:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if len(corpo) < 3:
        return False
    # Usa trecho acima da citação/assinatura para não reprovar por corpo longo
    principal = _corpo_superior_a_citacao_encadeada(corpo)
    if not principal:
        principal = corpo
    # Bug-fix: emojis mal codificados viram "??" e acionam o veto de "?" indevidamente.
    # Limpar sequências de ?? antes de qualquer verificação de ponto de interrogação.
    principal = re.sub(r"\?\?+", "", principal)
    # Corpo principal muito longo: tenta extrair só os primeiros 250 chars (antes da assinatura)
    # Assinaturas corporativas longas inflam o principal mas o agradecimento está no início
    if len(principal) > 500:
        # Verificar apenas o trecho inicial — se tiver "?" ali, é pergunta real
        trecho = principal[:250]
        if "?" in trecho and not _exclui_pergunta_social(trecho):
            return False
        # Se não tem agradecimento no início, desiste
        if not re.search(
            r"\b(obrigad[ao]|muito\s+obrigad[ao]|deu\s+certo|perfeito|"
            r"tudo\s+(certo|ok|bem|resolvido)|consegui|resolvido|solucionado|"
            r"funcionou|ok\s*[,!]|feito\s*[,!]|recebido\s*[,!]|anotado|entendido|ciente|valeu)\b",
            trecho, re.I
        ):
            return False
        # Verificar anti-FPs só no trecho inicial
        if re.search(
            r"\b(segue|seguem|encaminh|em\s+anexo|planilha|relat|extratos?|arquivo|balancete|cosif|lec)\b",
            trecho, re.I
        ):
            return False
        if re.search(
            r"\b(solicito|gostaria|poderia|por\s+favor|priorizar|reprocessar|preciso|aguardo|necessito)\b",
            trecho, re.I
        ):
            return False
        if re.search(r"\bpergunto\s*:|\bsó\s+uma\s+pergunta\b|\bqueria\s+saber\b", trecho, re.I):
            return False
        if re.search(r"(depois\s+(te|lhe|vos)\s+(atualizo|retorno)|vamos\s+(enviar|transmitir|verificar|encaminhar))", trecho, re.I):
            return False
        return True
    corpo = principal
    # Se tem '?' provavelmente há pergunta aberta — exceto perguntas sociais ("e você?", "tudo bem?")
    if "?" in corpo and not _exclui_pergunta_social(corpo):
        return False
    # Se menciona envio de dados/arquivo, não é agradecimento puro
    # "Anexo os/as/o/a [dados]" = cliente enviando arquivo → mesmo anti-FP de "segue em anexo"
    if re.search(
        r"\b(segue|seguem|encaminh|em\s+anexo|planilha|relat|extratos?|arquivo|balancete|cosif|lec)\b"
        r"|\banexo\s+(?:os?|as?)\b",
        corpo, re.I
    ):
        return False
    # Se contém pedido/solicitação embutido, não é agradecimento puro
    if re.search(
        r"\b(solicito|gostaria|poderia|por\s+favor|priorizar|reprocessar|preciso|aguardo|necessito)\b",
        corpo, re.I
    ):
        return False
    # "pedi via ..." = referência a submissão pendente, não agradecimento conclusivo
    if re.search(r"\bpedi\s+(via|ao|para|pelo)\b", corpo, re.I):
        return False
    # Pergunta implícita sem "?" (ex: "pergunto:", "só uma pergunta", "queria saber")
    if re.search(r"\bpergunto\s*:|\bsó\s+uma\s+pergunta\b|\bqueria\s+saber\b|\bgostaria\s+de\s+saber\b", corpo, re.I):
        return False
    # Promessa de ação futura — ainda há pendência ("depois te atualizo", "vamos enviar")
    if re.search(r"(depois\s+(te|lhe|vos)\s+(atualizo|retorno)|vamos\s+(enviar|transmitir|verificar|encaminhar))", corpo, re.I):
        return False
    # Detecta termos de agradecimento/confirmação conclusiva
    # "feito[,!\s]" seria muito amplo (captura "O pedido foi feito hoje") → exige pontuação
    # "tudo bem" removido: como saudação ("Tudo bem?") passa pelo _exclui_pergunta_social
    # e ainda seria encontrado aqui, gerando falsos positivos. "tudo certo/ok/resolvido"
    # permanecem porque são inequivocamente conclusivos.
    return bool(re.search(
        r"\b(obrigad[ao]|muito\s+obrigad[ao]|deu\s+certo|perfeito|"
        r"tudo\s+(certo|ok|resolvido)|consegui|resolvido|solucionado|"
        r"funcionou|ok\s*[,!]|feito\s*[,!]|recebido\s*[,!]|"
        r"anotado|entendido|ciente|valeu)\b",
        corpo, re.I
    ))


def _cliente_confirmou_conclusao(ultima: dict) -> bool:
    """
    Detecta última mensagem C→F onde cliente confirmou a conclusão da demanda
    sem usar termos de agradecimento (cobertos por _cac).

    Padrões (identificados em auditoria 2026-06-13):
    - "substituído/substituídos" — documento foi substituído/enviado ao BACEN
    - "foi aceito / foram aceitos" — BACEN aceitou o arquivo
    - "respondi os Índices de Qualidade do BACEN" — cliente respondeu via CRD
    - "Realizamos o envio conforme a orientação" — seguiu instrução da Finaud

    Veto: se há '?' no trecho principal → ainda há dúvida aberta.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_cliente = lado == "CLIENTE" or (
        "@finaud.com.br" not in email and "@finaudtec.com.br" not in email and lado != "FINAUD"
    )
    if not is_cliente:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if not corpo:
        return False
    principal = _corpo_superior_a_citacao_encadeada(corpo)
    if not principal:
        principal = corpo
    # Bug fix 2026-06-14: saudações com "?" não são perguntas reais.
    # Remove o bloco de saudação do início antes de verificar "?".
    principal_sem_saudacao = re.sub(
        r"^(bom\s+dia|boa\s+tarde|boa\s+noite)[,!.]?\s*\w*[,!.]?\s*"
        r"(tudo\s+(bem|legal|certo|ok|bom)\??|como\s+vai\??|como\s+est[aá]\??|espero\s+que\s+esteja\s+bem\.?)?\s*",
        "", principal, flags=re.I
    ).strip()
    if "?" in principal_sem_saudacao:
        return False
    return bool(re.search(
        # P1: documento substituído
        r"\bsubstitu[ií]d[oa]s?\b"
        r"|arquivo\s+substitu[ií]d[oa]"
        # P2: aceito pelo BACEN
        r"|foram\s+aceitos?\b"
        r"|\bfoi\s+aceito\b"
        r"|\baceito\s+(pelo|no)\s+(bacen|bc\b|banco\s+central|sta)"
        # P3: respondeu índices/crítica no CRD — alargado para cobrir "respondidos" (bug fix 2026-06-14)
        r"|respond\w*\s+.{0,30}?[ií]ndices?\s+(de\s+qualidade|do\s+bacen)"
        r"|[ií]ndices?\s+(de\s+qualidade\s+)?respondid"
        # P4: realizou envio conforme orientação
        r"|realizamos\s+o\s+envio\s+conforme"
        r"|realizei\s+o\s+envio\s+conforme"
        r"|envio\s+conforme\s+(a\s+)?orienta"
        # P5: cliente confirmou transmissão de arquivo regulatório (sem citar BACEN explicitamente)
        r"|transmitido[s]?\s+(o[s]?\s+)?(dlo|dli|ddr|drl|drm|4111|2011|2060|2061|2062|2160)"
        r"|transmitimos\s+(o[s]?\s+)?(dlo|dli|ddr|drl|drm)"
        # P6: Banco Central desconsiderou / retirou a crítica (adicionado 2026-06-14)
        # "o apontamento foi desconsiderado" — BC retirou o indício do CRD, problema encerrado
        r"|apontamento.{0,60}?foi\s+desconsiderado"
        r"|\bindício.{0,60}?foi\s+desconsiderado"
        r"|cr[ií]tica.{0,60}?foi\s+desconsiderada"
        r"|foi\s+desconsiderado.{0,60}?(apontamento|ind[ií]cio|cr[ií]tica)",
        principal, re.I | re.DOTALL,
    ))


def _finaud_acesso_concluido(ultima: dict) -> bool:
    """
    Detecta última mensagem F→C onde Finaud realizou reset de senha ou liberou acesso.
    Bola passou ao cliente (verificar/logar com nova senha) → CONCLUIDO.

    Padrões (identificados em auditoria 2026-06-13):
    - "realizei o reset / reset foi realizado"
    - "nova senha temporária foi encaminhada"
    - "acesso liberado / usuário liberado"
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_finaud = lado == "FINAUD" or "@finaud.com.br" in email or "@finaudtec.com.br" in email
    if not is_finaud:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if not corpo:
        return False
    principal = _corpo_superior_a_citacao_encadeada(corpo)
    if not principal:
        principal = corpo
    return bool(re.search(
        r"reali[sz]ei\s+o\s+reset"
        r"|reset\s+(foi\s+)?realizado"
        r"|nova\s+senha\s+(tempor[aá]ria\s+)?(foi\s+)?encaminhad"
        r"|acesso\s+liberado"
        r"|usu[aá]rio\s+liberado"
        r"|liberei\s+(seu|o)\s+acesso"
        r"|criamos\s+o\s+usu[aá]rio\b"
        r"|criamos\s+(o\s+)?acesso\b"
        # Adicionado 2026-06-13 — variações de acesso/login entregue
        r"|o\s+usu[aá]rio\s+j[aá]\s+foi\s+criado"
        r"|usu[aá]rios?\s+criados?\s+conforme\s+solicit"
        r"|para\s+se\s+logar\s+no\s+.{0,30}?informe\s+o\s+registro"
        r"|seguem\s+os\s+logins?\b"
        r"|segue(m)?\s+(os\s+)?dados\s+de\s+acesso"
        r"|Email\s*:\s*.+\s+Senha\s*:"
        # Adicionado 2026-06-14 — "apliquei um resetar" / "apliquei o reset"
        r"|apliquei\s+(um\s+)?reset(ar)?\b",
        principal, re.I | re.DOTALL,
    ))


def _finaud_confirma_aceite_bacen(ultima: dict) -> bool:
    """
    Detecta última mensagem F→C onde Finaud confirma que o arquivo está aceito
    no BACEN/STA, ou agradece o retorno do cliente informando o aceite.
    Demanda encerrada → CONCLUIDO.

    Padrões (identificados em auditoria 2026-06-13):
    - "arquivo aceito no STA / aceito pelo BACEN"
    - "obrigado pelo retorno com o aceite do BACEN"
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_finaud = lado == "FINAUD" or "@finaud.com.br" in email or "@finaudtec.com.br" in email
    if not is_finaud:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if not corpo:
        return False
    return bool(re.search(
        r"\baceito\s+(pelo|no)\s+(bacen|bc\b|banco\s+central|sta)"
        r"|\baceito\s+no\s+(sta|crd)\b"
        r"|obrigad.{0,50}?aceite\s+do\s+bacen"
        r"|obrigad.{0,30}?retorno.{0,60}?aceite"
        # Adicionado 2026-06-13 — "consta com o status ACEITO" no STA/CRD
        r"|consta\s+(com\s+o\s+status|como).{0,20}?aceito"
        r"|status\s+.{0,10}?aceito.{0,30}?(sta|crd|bacen|bc\b)",
        corpo, re.I | re.DOTALL,
    ))


def _cliente_pergunta_aberta(ultima: dict) -> bool:
    """
    Detecta última mensagem C→F que é uma pergunta sem envio de dados.
    Nesse caso o tipo deveria ser RESPOSTA_CLIENTE (Finaud precisa responder),
    não ACAO_INTERNA.

    Regra: última msg do CLIENTE, contém '?', não contém envio de dados/arquivos.

    Auditoria 18/05/2026.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    lado = (co.get("lado") or "").strip().upper()
    email = (co.get("email") or "").strip().lower()
    is_cliente = lado == "CLIENTE" or (
        "@finaud.com.br" not in email and "@finaudtec.com.br" not in email and lado != "FINAUD"
    )
    if not is_cliente:
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if "?" not in corpo:
        return False
    # Se também envia dados/arquivo, não é apenas pergunta — manter como ACAO_INTERNA
    if re.search(
        r"\b(segue|seguem|em\s+anexo|encaminh[oa]|planilha|relat|extratos?|arquivo|balancete|cosif|lec)\b",
        corpo, re.I
    ):
        return False
    return True


def _ultima_e_finaud_para_cliente(ult: Optional[dict]) -> bool:
    if not ult:
        return False
    co = ult.get("contato_origem") or {}
    cd = ult.get("contato_destino") or {}
    return (
        (co.get("lado") or "").strip().upper() == "FINAUD"
        and (cd.get("lado") or "").strip().upper() == "CLIENTE"
    )

def _finaud_analise_conclusiva(ultima: dict) -> bool:
    """Finaud entregou análise conclusiva — pergunta do cliente respondida definitivamente.
    Adicionado 2026-06-13 — cobre G4/G5 que não são capturados por _fec nem _fic.
    Vetoes: qualquer promessa de retorno futuro invalida o match.
    """
    if not _ultima_e_finaud_para_cliente(ultima):
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "")
    # Vetoes — presença de qualquer um cancela o match
    _vetoes = re.compile(
        r"\baguardamos\b"
        r"|\bretornaremos\b"
        r"|\bassim\s+que\s+tivermos\b"
        r"|\bpor\s+gentileza\b"
        r"|\baguarde\b"
        r"|\bem\s+breve\b",
        re.I,
    )
    if _vetoes.search(corpo):
        return False
    return bool(re.search(
        r"chegamos\s+(à|a)\s+seguinte\s+conclus[aã]o"
        r"|chegamos\s+(à|a)\s+conclus[aã]o\s+de\s+que"
        r"|ap[oó]s\s+anali(sar|sarmos).{0,50}?confirmo\s+que"
        r"|nossa\s+análise\s+foi\s+feita.{0,200}?chegamos"
        r"|o\s+novo\s+relat[oó]rio.{0,100}?contemplar[aá]\s+automaticamente"
        r"|os\s+dados\s+foram\s+validados\s+e\s+est[aã]o\s+corretos"
        r"|verificamos\s+e\s+est[aá]\s+(de\s+acordo|correto|ok)\b"
        r"|nossa\s+análise\s+aponta\s+que.{0,100}?n[aã]o\s+h[aá]\s+(erro|problema|inconsist)"
        r"|ap[oó]s\s+verifica[çc][aã]o.{0,100}?est[aá]\s+correto"
        r"|conclu[ií]mos\s+(que|a\s+análise).{0,100}?(correto|de\s+acordo|ok|sem\s+erro)"
        # Adicionado 2026-06-14 — análise quantitativa conclusiva (enquadramento S5/DLO)
        r"|if\s+est[aá]\s+enquadrad[ao]\b"
        r"|\bíndice\s+de\s+basileia\s+de\s+\d"
        r"|est[aá]\s+enquadrad[ao]\s+(acima|dentro)\s+do\s+(m[ií]nimo|limite)"
        r"|IF\s+est[aá]\s+em\s+conformidade"
        # Adicionado 2026-06-14 — confirmação de que valores batem/conferem
        r"|\best[aá]\s+batendo\s+com\s+os\s+valores\b"
        r"|\bvalores\s+(est[aã]o\s+)?batendo\b"
        r"|\bbate\s+com\s+o\s+cosif\b",
        corpo,
        re.I | re.DOTALL,
    ))


def _thread_tem_cliente_para_finaud(thread: dict) -> bool:
    for m in thread.get("mensagens") or []:
        if not isinstance(m, dict):
            continue
        co = m.get("contato_origem") or {}
        cd = m.get("contato_destino") or {}
        if (
            (co.get("lado") or "").strip().upper() == "CLIENTE"
            and (cd.get("lado") or "").strip().upper() == "FINAUD"
        ):
            return True
    return False

def _finaud_pedido_insumos_a_cliente(ult: dict) -> bool:
    """§3-inv: F→C pedindo dados/arquivos (última global); não é remessa §5/5b/5c."""
    if not _ultima_e_finaud_para_cliente(ult):
        return False
    if (
        _sec5_remessa_finaud(ult)
        or _sec5b_res_finaud_cliente(ult)
        or _sec5c_finaud_corpo_conclusivo(ult)
    ):
        return False
    return _finaud_texto_e_pedido_insumo_ao_cliente(ult)

_FACR_PALAVRAS_INSUMO = frozenset([
    "segue", "seguem", "segue em", "segue abaixo", "seguem em",
    "anexo", "encaminho", "encaminhei", "envio", "enviando",
    "planilha", "extrato", "arquivo", "documento",
])

def _finaud_agradecimento_curto_sem_remessa(ult: dict, penult: Optional[dict] = None) -> bool:
    """
    F→C curto com agradecimento, sem §5/5b/5c.
    penult: mensagem anterior (índice -2); quando fornecida, aplica anti-FP de insumo de cliente.
    Anti-FP: se penúltima é CLIENTE entregando dados/insumo, Finaud só acusou recebimento
    e ainda precisa processar — não é encerramento (#Grupo2-facr redesenho 2026-06-10).
    """
    if not _ultima_e_finaud_para_cliente(ult):
        return False
    if (
        _sec5_remessa_finaud(ult)
        or _sec5b_res_finaud_cliente(ult)
        or _sec5c_finaud_corpo_conclusivo(ult)
    ):
        return False
    corpo = (ult.get("corpo_limpo") or ult.get("corpo") or "").strip()
    if len(corpo) > 160:
        return False
    c_low = corpo.lower()
    if "anexo" in c_low and "segue" in c_low:
        return False
    # Anti-falso-positivo: pedido ou pergunta não é encerramento (#PF46)
    if "?" in corpo:
        return False
    if re.search(r"poderia|gostaria\s+de\s+solicitar|pe[cç]o\s+(a|à)\s+gentileza|por\s+gentileza|solicito\b|solicitar\b", c_low):
        return False
    # Anti-FP insumo: penúltima é CLIENTE entregando dados → Finaud acusou recebimento, ainda vai processar
    if penult:
        _co_pen = penult.get("contato_origem") or {}
        if (_co_pen.get("lado") or "").strip().upper() == "CLIENTE":
            _cp = (penult.get("corpo_limpo") or penult.get("corpo") or "").lower()
            if any(p in _cp for p in _FACR_PALAVRAS_INSUMO):
                return False
    return bool(re.search(r"obrigad|agrade[cç]o|thanks", c_low, re.I))

def _ordenacao_mensagem(msg: dict) -> Tuple[float, str]:
    """Ordenação cronológica aproximada (epoch → data_email)."""
    ep = msg.get("timestamp_epoch")
    if ep is not None:
        return (float(ep), str(msg.get("id") or ""))
    d = _parse_data_msg(msg)
    if d:
        return (float(d.toordinal() * 86400), str(msg.get("id") or ""))
    s = (msg.get("data_email") or msg.get("timestamp") or "").strip()
    return (0.0, s)

def _ultima_e_cliente_para_finaud(ult: Optional[dict]) -> bool:
    if not ult:
        return False
    co = ult.get("contato_origem") or {}
    cd = ult.get("contato_destino") or {}
    return (
        (co.get("lado") or "").strip().upper() == "CLIENTE"
        and (cd.get("lado") or "").strip().upper() == "FINAUD"
    )

def _corpo_superior_a_citacao_encadeada(corpo: str) -> str:
    """
    Trecho da mensagem **acima** da citação (De:/From:/Em … escreveu:), para §4d não
    confundir «segue anexo» do histórico citado com novo envio do cliente.
    """
    s = (corpo or "").strip()
    if not s:
        return ""
    cut = len(s)
    for pat in (
        r"\n\s*-{3,}\s*original\s+message",
        r"\n\s*from:",
        r"\n\s*de:",
        r"\n\s*on .{5,120}\s+wrote:",
        r"(?:^|\n)\s*em [a-zà-ú]{2,15}\.?\s*,\s*\d{1,2}\s+de\s+",  # linha nova: Em seg., 23 de...
        r"\bEm\s+(?:seg|ter|qua|qui|sex|s[aá]b|dom)\.?\s*,\s*\d{1,2}\s+de\s+",  # Gmail colado: «… Abs. Em seg.,»
        r">\s*escreveu\s*:",
        r"\n\s*escreveu:",
    ):
        m = re.search(pat, s, re.I)
        if m and m.start() >= 12:
            cut = min(cut, m.start())
    return s[:cut].strip()

def _cliente_somente_reconhecimento_curto_pos_remessa(ult: dict) -> bool:
    """
    C→F com texto essencialmente de agradecimento; não novo envio nem abertura de pendência.
    """
    if not _ultima_e_cliente_para_finaud(ult):
        return False
    corpo = (ult.get("corpo_limpo") or ult.get("corpo") or "").strip()
    principal = _corpo_superior_a_citacao_encadeada(corpo)
    if len(principal) > 520:
        return False
    pl = principal.lower()
    head = pl[:500]
    if re.search(
        r"segue.{0,35}anex|seguem.{0,35}anex|encaminh(o|amos|ei)|\banexo\b.{0,20}(segue|em anexo)|"
        r"por\s+gentileza\s+(enviar|encaminhar)|por\s+favor\b|diverg[eê]nc|inconsist|pend[eê]ncia|"
        r"d[uú]vida\s+(sobre|com)|solicit(o|amos)|\bpedi\b|\bpedimos\b",
        head,
        re.I,
    ):
        return False
    # Agradecimento + pergunta/ressalva não é «só» reconhecimento (ex.: RD_Moedas — layout?).
    # Remover URLs antes de procurar «?» — evita falso negativo (query ?utm, ?ref em links).
    head_sem_url = re.sub(r"https?://\S+", " ", head, flags=re.I)
    if "?" in head_sem_url:
        return False
    if re.search(
        r"(obrigad\w*|agrade[cç]o|thanks|grat\w*).{0,200}\bmas\b",
        head,
        re.I | re.DOTALL,
    ):
        return False
    return bool(
        re.search(r"obrigad|agrade[cç]o|thanks|muito\s+obrigad|grato|abra[cç]o|at[+e]", pl[:800], re.I)
    )


def _tem_msg_finaud_no_historico(thread: dict) -> bool:
    """True se o histórico da thread tem ao menos uma mensagem da Finaud.

    Protege §4e de threads onde Finaud nunca respondeu — o agradecimento do
    cliente seria sem contexto e não indica conclusão.
    """
    for m in (thread.get("mensagens") or []):
        lado = ((m.get("contato_origem") or {}).get("lado") or "").upper()
        if lado == "FINAUD":
            return True
    return False


def _cliente_reconhecimento_curto_com_historico_finaud(thread: dict, ult: dict) -> bool:
    """§4e com salvaguarda de histórico: exige pelo menos uma msg da Finaud
    antes de concluir pelo agradecimento do cliente.

    Versão estendida de ``_cliente_somente_reconhecimento_curto_pos_remessa``
    usada nos supervisores onde §4e está sendo habilitado pela primeira vez
    (DLO, DLI, DRM, S5, RETORNO_BACEN, DRSAC, FORCAPITAL, 6209).
    """
    if not _tem_msg_finaud_no_historico(thread):
        return False
    return _cliente_somente_reconhecimento_curto_pos_remessa(ult)


def _par_conclusivo(thread: dict, ult: dict) -> bool:
    """G3: cliente concorda com instrução da Finaud — par penúltima+última.

    Dispara quando:
    - última mensagem é do CLIENTE com termo de concordância ('de acordo', 'ok', etc.)
    - sem '?' no texto (sem nova pergunta junto)
    - penúltima mensagem é da FINAUD

    Complementa §4d/§4e: cobre casos onde o cliente não usa palavras de agradecimento
    mas confirma explicitamente a concordância com o que a Finaud instruiu.
    """
    if not _ultima_e_cliente_para_finaud(ult):
        return False
    corpo = (ult.get("corpo_limpo") or ult.get("corpo") or "").strip()
    principal = _corpo_superior_a_citacao_encadeada(corpo)
    if len(principal) > 800:
        return False
    pl = principal.lower()
    head_sem_url = re.sub(r"https?://\S+", " ", pl, flags=re.I)
    if "?" in head_sem_url:
        return False
    if not re.search(
        r"\bde\s+acordo\b|\bok\b|\bcerto\b|\bcorreto\b|\bperfeito\b|\bconfirmad\w*\b|\bentendid\w*\b"
        r"|\banotado\b|\brecebido\b|\bciente\b|\bcombinado\b|\btudo\s+certo\b"
        r"|\bprocederemos\s+conforme\b|\bseguiremos\s+(as\s+)?(instru[çc][õo]es|orienta[çc][õo]es)\b",
        pl[:500],
        re.I,
    ):
        return False
    msgs = sorted(
        [m for m in (thread.get("mensagens") or []) if isinstance(m, dict)],
        key=_ordenacao_mensagem,
    )
    idx_ult = _indice_mensagem_no_fio_ordenado(msgs, ult)
    if idx_ult <= 0:
        return False
    pen = msgs[idx_ult - 1]
    return (pen.get("contato_origem") or {}).get("lado", "").strip().upper() == "FINAUD"


def _finaud_envio_material_a_cliente_sem_sec5_literal(m: dict) -> bool:
    """
    F→C com corpo substantivo que indica envio de material (anexo, base, planilha, etc.),
    sem cair no padrão §3-inv (pedido de insumos ao cliente).
    Cobre textos reais sem «segue em anexo» nem RES: nem §5c.
    """
    if not m:
        return False
    co = m.get("contato_origem") or {}
    cd = m.get("contato_destino") or {}
    if (co.get("lado") or "").strip().upper() != "FINAUD":
        return False
    if (cd.get("lado") or "").strip().upper() != "CLIENTE":
        return False
    if _finaud_pedido_insumos_a_cliente(m):
        return False
    corpo = (m.get("corpo_limpo") or m.get("corpo") or "").strip()
    c = corpo.lower()
    if len(corpo) < 40:
        return False
    # Textos curtos («segue um base de alterações…») ainda são envio material.
    if len(corpo) < 80 and not re.search(
        r"\bsegue\b.{0,40}\b(base|anexo|planilha|arquivo)|base\s+de\s+alter",
        c,
        re.I,
    ):
        return False
    return bool(
        re.search(
            r"anexo|planilha|arquivo|documenta[cç][aã]o|\.xlsx|\.pdf|\.zip|"
            r"\bsegue\b|encaminh|base\s+de|material|dados\s+(solicit|enviad)|"
            r"conforme\s+alinhad|conforme\s+convers",
            c,
            re.I,
        )
    )

def _indice_mensagem_no_fio_ordenado(sorted_msgs: List[dict], ult: dict) -> int:
    try:
        return sorted_msgs.index(ult)
    except ValueError:
        uid = ult.get("id")
        if uid is not None:
            for i, m in enumerate(sorted_msgs):
                if m.get("id") == uid:
                    return i
        return max(0, len(sorted_msgs) - 1)

def _indice_ultima_remessa_finaud_antes(sorted_msgs: List[dict], idx_ult: int) -> int:
    """Índice da última mensagem F→C (§5/5b/5c/material) com posição ``< idx_ult``; ``-1`` se não houver."""
    last = -1
    for i in range(idx_ult):
        m = sorted_msgs[i]
        if (
            _sec5_remessa_finaud(m)
            or _sec5b_res_finaud_cliente(m)
            or _sec5c_finaud_corpo_conclusivo(m)
            or _finaud_envio_material_a_cliente_sem_sec5_literal(m)
        ):
            last = i
    return last

# Regex usada por _principal_{cf,fc}_*_tema_layout para detectar menções a
# layout/leiaute/formato no corpo do email (§4d, sub-veto de pendência cliente).
# Definida aqui (no módulo, antes do 1º uso) para evitar ``NameError`` quando
# uma thread DDR4111 cai em ``_sec4d_veto_pendencia_cliente_intermedia`` — a
# referência ficou sem definição após o refactor 2026-05-07 (commit 0f1c3f4)
# e fazia a triagem DDR4111 inteira explodir silenciosamente.
_RE_SEC4D_LAYOUT_LEIAUTE = re.compile(
    r"\b(layouts?|leiautes?|formato[s]?|formataç[aã]o|formataç[oõ]es)\b",
    re.IGNORECASE,
)


def _principal_cf_pergunta_tema_layout(corpo: str) -> bool:
    """C→F: ``?`` no trecho acima da citação e menção a layout/leiaute/formato."""
    pr = _corpo_superior_a_citacao_encadeada(corpo or "")
    if "?" not in pr[:700]:
        return False
    return bool(_RE_SEC4D_LAYOUT_LEIAUTE.search(pr))

def _principal_fc_cita_tema_layout(corpo: str) -> bool:
    """F→C: mesmo tema no texto novo (acima da citação)."""
    pr = _corpo_superior_a_citacao_encadeada(corpo or "")
    return bool(_RE_SEC4D_LAYOUT_LEIAUTE.search(pr[:1200]))

def _sec4d_veto_pendencia_cliente_intermedia(
    sorted_msgs: List[dict], idx_ult: int, i_remessa: int
) -> bool:
    """
    True → não aplicar §4d: entre a última remessa F→C e ``ult`` houve C→F que não é só
    reconhecimento curto **e** (caso geral) não houve F→C a seguir antes de ``ult``; ou
    (caso layout) pergunta com ``?`` sobre layout/leiaute/formato sem F→C posterior que cite
    o tema no topo (resposta só genérica «produção» não encerra a subdúvida).
    """
    if i_remessa < 0 or idx_ult <= i_remessa + 1:
        return False
    for j in range(i_remessa + 1, idx_ult):
        m = sorted_msgs[j]
        if not _ultima_e_cliente_para_finaud(m):
            continue
        corpo_m = (m.get("corpo_limpo") or m.get("corpo") or "").strip()
        if _principal_cf_pergunta_tema_layout(corpo_m):
            if not any(
                _ultima_e_finaud_para_cliente(sorted_msgs[k])
                and _principal_fc_cita_tema_layout(
                    (sorted_msgs[k].get("corpo_limpo") or sorted_msgs[k].get("corpo") or "")
                )
                for k in range(j + 1, idx_ult)
            ):
                return True
        if not _cliente_somente_reconhecimento_curto_pos_remessa(m):
            if not any(_ultima_e_finaud_para_cliente(sorted_msgs[k]) for k in range(j + 1, idx_ult)):
                return True
    return False

def _thread_teve_remessa_finaud_antes_de_msg(
    thread: dict, ult: dict
) -> bool:
    """True se alguma mensagem F→C §5/5b/5c ou envio material F→C ocorre antes de ``ult``."""
    msgs = [m for m in thread.get("mensagens") or [] if isinstance(m, dict)]
    if len(msgs) < 2:
        return False
    sorted_msgs = sorted(msgs, key=_ordenacao_mensagem)
    idx = _indice_mensagem_no_fio_ordenado(sorted_msgs, ult)
    if idx <= 0:
        return False
    for m in sorted_msgs[:idx]:
        if (
            _sec5_remessa_finaud(m)
            or _sec5b_res_finaud_cliente(m)
            or _sec5c_finaud_corpo_conclusivo(m)
            or _finaud_envio_material_a_cliente_sem_sec5_literal(m)
        ):
            return True
    return False

def _cliente_agradecimento_apos_remessa_finaud(thread: dict, ult: dict) -> bool:
    """§4d: última C→F só agradecimento após F→C §5/5b/5c ou envio material (ver ``_finaud_envio_material_…``)."""
    if not (
        _cliente_somente_reconhecimento_curto_pos_remessa(ult)
        and _thread_teve_remessa_finaud_antes_de_msg(thread, ult)
    ):
        return False
    msgs = [m for m in (thread.get("mensagens") or []) if isinstance(m, dict)]
    if len(msgs) < 2:
        return True
    sorted_msgs = sorted(msgs, key=_ordenacao_mensagem)
    idx_ult = _indice_mensagem_no_fio_ordenado(sorted_msgs, ult)
    i_rem = _indice_ultima_remessa_finaud_antes(sorted_msgs, idx_ult)
    if _sec4d_veto_pendencia_cliente_intermedia(sorted_msgs, idx_ult, i_rem):
        return False
    return True

def _cliente_confirma_protocolo_aceito_bacen(ult: dict) -> bool:
    """
    §4f-rb (RETORNO_BACEN): cliente confirma que o BACEN aceitou/aprovou/reprocessou
    o protocolo da crítica.

    Cobre o padrão típico em que toda a atuação da Finaud foi interna (F→F, instruindo
    o cliente a responder via CRD) e o cliente fecha o ciclo confirmando o resultado —
    onde §4d falha por não existir remessa F→C anterior.

    Dispara apenas quando a última mensagem é CLIENTE→FINAUD com texto canônico
    indicando aceite/aprovação/reprocessamento bem-sucedido pelo BACEN.
    """
    if not isinstance(ult, dict):
        return False
    co = ult.get("contato_origem") or {}
    cd = ult.get("contato_destino") or {}
    if (co.get("lado") or "").strip().upper() != "CLIENTE":
        return False
    if (cd.get("lado") or "").strip().upper() != "FINAUD":
        return False
    corpo = (ult.get("corpo_limpo") or ult.get("corpo") or "")
    assunto = ult.get("assunto") or ""
    texto = (corpo + " " + assunto).lower()
    # Veto: se cliente abre nova questão / pede algo, não fechar.
    if re.search(
        r"\b(d[uú]vida|por\s+favor|gentileza|poderia|pode\s+(me\s+)?(ajudar|enviar|verificar)|"
        r"como\s+(fa[cç]o|proceder|devo)|me\s+orient|aguardo\s+(retorno|posicionamento|orienta))",
        texto,
        re.I,
    ):
        return False
    padroes = (
        r"protocolo\s+(?:foi\s+|\w+\s+foi\s+)?(?:reprocessad|aceit|aprovad|deferid|homologad)",
        r"(?:reprocessad|aceit|aprovad|deferid|homologad)\w*\s+(?:pelo|junto\s+ao|no)\s+bacen",
        r"\bbacen\s+(?:aceitou|aprovou|deferiu|homologou|reprocessou)",
        r"em\s+seguida\s+foi\s+aceito",
    )
    return any(re.search(p, texto, re.I) for p in padroes)

def _finaud_somente_reconhecimento_curto(ult: dict, thread: dict) -> bool:
    """
    §3.5: última F→C é agradecimento/reconhecimento curto; cliente já tinha escrito;
    ainda não há «segue … anexo» (§5).
    """
    if not _ultima_e_finaud_para_cliente(ult):
        return False
    if (
        _sec5_remessa_finaud(ult)
        or _sec5b_res_finaud_cliente(ult)
        or _sec5c_finaud_corpo_conclusivo(ult)
    ):
        return False
    if not _thread_tem_cliente_para_finaud(thread):
        return False
    corpo = (ult.get("corpo_limpo") or ult.get("corpo") or "").strip()
    if len(corpo) > 160:
        return False
    c_low = corpo.lower()
    if "anexo" in c_low and "segue" in c_low:
        return False
    return bool(re.search(r"obrigad|agrade[cç]o|thanks", c_low, re.I))

def _sec5b_res_finaud_cliente(ultima: dict) -> bool:
    """
    Resposta Finaud → cliente com assunto **RES:** (após Re:/Fwd:), corpo com conteúdo mínimo.
    Cobre fechos sem a frase «segue em anexo» na última mensagem.
    """
    if not ultima:
        return False
    co = ultima.get("contato_origem") or {}
    cd = ultima.get("contato_destino") or {}
    if (co.get("lado") or "").strip().upper() != "FINAUD":
        return False
    if (cd.get("lado") or "").strip().upper() != "CLIENTE":
        return False
    core = _strip_enc_assunto(ultima.get("assunto") or "")
    if not re.match(r"^res\s*:", core, re.I):
        return False
    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if len(corpo) < 24:
        return False
    return True

def _nucleo_assunto_ddr(assunto: str) -> str:
    """
    Núcleo comparável entre **RES:** e **Cancelar:** (e cadeias Re:/Fwd:).
    Usado só em candidatos DDR_2011 / 4111.
    """
    s = _strip_enc_assunto(assunto).lower()
    for _ in range(4):
        prev = s
        s = re.sub(r"^cancelar\s*:\s*", "", s, count=1, flags=re.I).strip()
        s = re.sub(r"^res\s*:\s*", "", s, count=1, flags=re.I).strip()
        if s == prev:
            break
    return re.sub(r"\s+", " ", s).strip()

def _assunto_representativo_evento(ev: dict, ultima: Optional[dict]) -> str:
    for k in ("titulo", "assunto"):
        v = (ev.get(k) or "").strip()
        if v:
            return v
    if ultima and isinstance(ultima, dict):
        return (ultima.get("assunto") or "").strip()
    return ""

def _empresa_chave(empresa: str) -> str:
    s = (empresa or "").strip().lower()
    return s if len(s) >= 2 else ""


# ---------------------------------------------------------------------------
# Melhoria 1a — F→F conclusivo (19/05/2026)
# Detecta mensagens Finaud→Finaud cujo corpo indica que a tarefa foi concluída
# (aceite no STA, transmissão ao BACEN, desbloqueio, cadastro, etc.).
# Usado no motor.py como Regra 4 do pós-processamento.
# ---------------------------------------------------------------------------

_PAT_FF_CONCLUSIVO = re.compile(
    r"\b("
    # Aceitação no STA / BACEN
    r"aceito[s]?\s+(no|pelo|ao)\s+(sta|bacen|bc)|"
    r"foram?\s+aceito[s]?|arquivo[s]?\s+aceito[s]?|aceito\s+no\s+sta|"
    # Transmissão
    r"transmitido[s]?\s+(no|ao|para\s+o)\s+(sta|bacen|bc)|"
    r"j[aá]\s+transmitimos|j[aá]\s+foi\s+transmitido|"
    # Envio ao STA/BACEN — cobre "enviado ao STA", "arquivo enviado ao STA",
    # "já fiz as devidas alterações e enviado ao STA"
    r"enviado[s]?\s+(ao|para\s+o|no)\s+(sta|bacen|bc)|"
    r"remessa\s+enviada|foram?\s+enviado[s]?|j[aá]\s+foi\s+enviado|"
    # Resolvido / concluído
    r"deu\s+certo|foi\s+resolvido|est[aá]\s+resolvido|resolvido|"
    r"foi\s+conclu[ií]do|foram?\s+conclu[ií]do[s]?|conclu[ií]do[s]?|"
    # Desbloqueado / cadastrado / liberado / processado
    r"foi\s+desbloqueado|desbloqueado|j[aá]\s+est[aá]\s+desbloqueado|"
    r"foi\s+cadastrado|j[aá]\s+est[aá]\s+cadastrado|cadastrado\s+com\s+sucesso|"
    r"foi\s+liberado|j[aá]\s+est[aá]\s+liberado|liberado\s+para|"
    r"foi\s+processado|processado\s+com\s+sucesso|"
    # Ajustado / regularizado / corrigido — cobre "O download já está ajustado",
    # "já foi ajustado", "foi regularizado", "já está corrigido"
    r"j[aá]\s+(est[aá]|foi)\s+ajustado[s]?|foi\s+ajustado[s]?|ajustado\s+com\s+sucesso|"
    r"j[aá]\s+(est[aá]|foi)\s+regularizado[s]?|foi\s+regularizado[s]?|"
    r"j[aá]\s+(est[aá]|foi)\s+corrigido[s]?|foi\s+corrigido[s]?|corrigido\s+com\s+sucesso|"
    # Críticas / problemas resolvidos
    r"remessa\s+aceita|cr[íi]tica[s]?\s+solucionada[s]?|"
    r"cr[íi]tica[s]?\s+resolvida[s]?|cr[íi]tica[s]?\s+corrigida[s]?|"
    r"problema\s+resolvido|quest[aã]o\s+resolvida|"
    # Alterações feitas e enviadas
    r"devidas\s+altera[cç][oõ]es\s+e\s+enviado|"
    r"j[aá]\s+fiz\s+as\s+devidas\s+altera[cç][oõ]es|"
    # Entrega do que foi pedido internamente (F→F)
    # "Conforme solicitado, segue..." / "Conforme combinado, segue..." etc.
    r"conforme\s+solicitado.{0,80}?(segue|encaminh|providenci|arquivo|relat)|"
    r"conforme\s+combinado.{0,80}?(segue|encaminh)|"
    r"conforme\s+alinhado.{0,80}?(segue|encaminh)|"
    r"como\s+discutimos.{0,80}?(segue|encaminh)|"
    r"segue\s+conforme\s+(pedido|solicitado|combinado)"
    r")\b",
    re.I,
)


# Padrões para Melhoria 1b — agradecimento F→F com/sem relatório final
_PAT_FF_AGRADECIMENTO = re.compile(
    r"\b(obrigad[ao]|muito\s+obrigad[ao]|grat[ao]|agrade[cç]o|thanks|recebido"
    r"|recebemos|anotado|ok[\s,!.]|certo[\s,!.])\b",
    re.I,
)
# Relatório final enviado pela Finaud ao cliente/STA
_PAT_RELATORIO_FINAL = re.compile(
    r"\b(ddr|dlo|drm|dli|cadoc\s*4111|remessa|sta|bacen|transmit|enviado"
    r"|\.xml|\.zip|retificar|substitui[çc]|relat[oó]rio\s+final"
    r"|[Aa]rquivo\s+gerado|arquivo\s+enviado|arquivo\s+aceito"
    r"|documento\s+(gerado|enviado|aceito|corrigi)"
    r"|hqla|tabela\s+de\s+contas\s+hqla|relat[oó]rio\s+de\s+riscos"
    r"|segue[m]?\s+o\s+anexo\s+da\s+tabela)\b",
    re.I,
)
# Dados brutos enviados pelo cliente (Finaud ainda precisa trabalhar)
_PAT_DADOS_BRUTOS = re.compile(
    r"\b(cosif|lec|planilha|posicao|posição|saldo[s]?|extrato[s]?"
    r"|dados\s+brutos|balancete|carga\s+de\s+dados|arquivo[s]?\s+em\s+anexo"
    r"|segue[m]?\s+os\s+dados|segue[m]?\s+a\s+planilha)\b",
    re.I,
)


def _finaud_finaud_agradecimento_relatorio(ultima: dict, penultima: dict) -> str | None:
    """
    Melhoria 1b: detecta F→F onde a última mensagem é agradecimento e
    determina se a penúltima enviou relatório final ou dados brutos.

    Retorna:
        'CONCLUIDO'  — penúltima contém relatório final → thread encerrada
        'AGUARDANDO' — penúltima contém dados brutos → Finaud ainda vai trabalhar
        None         — sinal insuficiente, motor mantém status atual
    """
    def _is_finaud(msg: dict) -> bool:
        co = msg.get("contato_origem") or {}
        email = (co.get("email") or "").lower()
        lado = (co.get("lado") or "").upper()
        return "@finaud.com.br" in email or "@finaudtec.com.br" in email or lado == "FINAUD"

    # Caso especial: thread com 1 única mensagem F→F de agradecimento simples
    # (sem mensagem anterior capturada — ex: M23/M24 onde o original não foi coletado)
    if not penultima and _is_finaud(ultima):
        corpo_1 = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
        m_obrig = re.search(r"\bobrigad[ao]\b", corpo_1[:150], re.I)
        if m_obrig:
            # Tudo que vem depois do "obrigad..." deve ser muito curto (só nome/pontuação)
            resto = corpo_1[m_obrig.end():].strip()
            _veto_resto = re.compile(
                r"\bsolicitamos\b|\bencaminhar\b|\bpor\s+gentileza\b|\bpor\s+favor\b"
                r"|\bestou\s+copiando\b|\bestou\s+repassando\b|\bpara\s+alinhar\b"
                r"|\bpedimos\b|\baguardamos\b|\bprecisamos\b",
                re.I,
            )
            if not _veto_resto.search(resto) and "?" not in corpo_1[:150] and len(resto) < 60:
                return "CONCLUIDO"
        return None

    if not _is_finaud(ultima) or not _is_finaud(penultima):
        return None

    corpo_ult = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    if not _PAT_FF_AGRADECIMENTO.search(corpo_ult[:400]):
        return None

    # Veto: última ainda promete retorno futuro → não concluída
    _veto_ult = re.compile(
        r"\bretornaremos\b|\bretornar[ei]\b|\bem\s+breve\b|\baguarde\b"
        r"|\bainda\s+em\s+tratamento\b|\bainda\s+est[aá]\b|\bpermane[cs]e\s+em\b",
        re.I,
    )
    if _veto_ult.search(corpo_ult):
        return None

    # Corpo da penúltima como contexto do que foi enviado/recebido
    corpo_pen = (penultima.get("corpo_limpo") or penultima.get("corpo") or "").strip()
    assunto   = (penultima.get("titulo") or penultima.get("assunto") or "").strip()
    contexto  = (corpo_pen + " " + assunto)[:600]

    tem_relatorio   = bool(_PAT_RELATORIO_FINAL.search(contexto))
    tem_dados_brutos = bool(_PAT_DADOS_BRUTOS.search(contexto))

    if tem_relatorio and not tem_dados_brutos:
        return "CONCLUIDO"
    if tem_dados_brutos and not tem_relatorio:
        return "AGUARDANDO"
    return None  # ambíguo — não alterar


def _finaud_finaud_conclusivo(ultima: dict, penultima: dict) -> bool:
    """
    Retorna True quando:
      - última mensagem é de colaborador Finaud
      - penúltima mensagem também é de colaborador Finaud (loop interno)
      - corpo da última contém termo conclusivo (aceito STA, transmitido, resolvido…)

    Sinal: o colaborador confirmou internamente que a remessa/tarefa foi concluída.
    → motor.py usa isso para fechar como CONCLUÍDO em vez de deixar AGUARDANDO.
    """
    def _is_finaud(msg: dict) -> bool:
        co = msg.get("contato_origem") or {}
        email = (co.get("email") or "").lower()
        lado = (co.get("lado") or "").upper()
        return "@finaud.com.br" in email or "@finaudtec.com.br" in email or lado == "FINAUD"

    if not _is_finaud(ultima):
        return False
    if not _is_finaud(penultima):
        return False

    corpo = (ultima.get("corpo_limpo") or ultima.get("corpo") or "").strip()
    return bool(_PAT_FF_CONCLUSIVO.search(corpo))
