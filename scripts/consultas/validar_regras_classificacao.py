"""
Valida as regras de classificação de threads (§8 da spec).

Para cada thread do histórico, pega o último e-mail e aplica as regras §8:
  - AGUARDANDO_FINAUD  (§8.1)
  - AGUARDANDO_CLIENTE (§8.2)
  - CONCLUIDA          (§8.3)

Compara com o que o pipeline antigo classificou e reporta:
  - Cobertura de cada regra
  - Threads sem status (brecha)
  - Divergências entre nova classificação e pipeline antigo
  - Exemplos reais de cada caso estranho
"""

import json
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

# ── Caminhos ──────────────────────────────────────────────────────────────────
PROJETO_DADOS = r"D:\02_Finaud\Projetos\ativos\oraculo_360_finaud"
PASTA_PIPELINE = os.path.join(PROJETO_DADOS, "data", "json", "pipeline")

ARQUIVO_EMAILS   = os.path.join(PASTA_PIPELINE, "01_extração_dados_brutos_gmail.json")
ARQUIVO_CONCL    = os.path.join(PASTA_PIPELINE, "threads_concluidas_auto.json")
ARQUIVO_AGUARD   = os.path.join(PASTA_PIPELINE, "threads_aguardando_auto.json")

# ── Domínios Finaud (incluindo sistemas internos) ─────────────────────────────
DOMINIOS_FINAUD = (
    "@finaud.com.br",
    "@finaudtec.com.br",
    "finaud.fogbugz.com",      # sistema interno de tickets
)

# Remetentes / padrões de sistemas automáticos que NÃO entram na triagem nova
# (seriam filtrados pelo Campo 1 — regras de exclusão de remetente)
REMETENTES_AUTOMATICOS = (
    "riskdriver@finaud.com.br",
    "contato@finaud.com.br",       # e-mails marketing/comunicados Finaud
    "do-not-reply@finaud",
    "fogbugz",
    "noreply",
    "no-reply",
    "metamail",                    # Meta for Developers newsletter
    "sendgrid",
    "mailchimp",
    "unsubscribe",
)

# Palavras que indicam Concluída quando Finaud mandou o último
# (a IA entenderá variações — aqui apenas marcadores estruturais da regra)
FRASES_CONCLUIDA_FINAUD = [
    "transmitido no bacen",
    "transmitida no bacen",
    "transmitido ao bacen",
    "transmitida ao bacen",
    "enviamos ao bacen",
    "enviado ao bacen",
    "protocolo no bacen",
    # remessa — a IA reconhecerá variações; aqui os marcadores principais
    "segue em anexo",
    "segue anexo",
    "segue o arquivo",
    "seguem em anexo",
    "seguem anexo",
    "segue a remessa",
    "seguem os arquivos",
    "conforme solicitado",
    "procedemos com",
    "retransmitido",
    "arquivo enviado",
    "arquivos enviados",
    "encaminhamos o arquivo",
    "encaminhamos os arquivos",
    "favor conferir em anexo",
]

# Palavras que indicam Concluída quando o cliente mandou o último
# (a IA entenderá nuances; removido limite de tamanho de corpo)
FRASES_CONCLUIDA_CLIENTE = [
    "obrigado",
    "obrigada",
    "muito obrigado",
    "muito obrigada",
    "valeu",
    "perfeito",
    "de acordo",
    "ok,",
    "ok.",
    "ok!",
    "recebido",
    "confirmado",
    "certo,",
    "certo.",
    "ótimo",
    "otimo",
    "excelente",
    "entendido",
    "concordo",
    "funcionou",
    "deu certo",
]

# Padrão de "RES:" no assunto (resposta formal da Finaud)
PAD_ASSUNTO_RESPOSTA = re.compile(r"^(res|re|fw|fwd|enc)\s*:", re.IGNORECASE)

# Frases de cortesia que NÃO reabrem o caso (assinatura Finaud)
FRASES_CORTESIA_FINAUD = [
    "desde já agradeço",
    "permaneço à disposição",
    "permanecemos à disposição",
    "fico à disposição",
    "ficamos à disposição",
    "qualquer dúvida estou",
    "qualquer dúvida estamos",
]


# ── Funções auxiliares ────────────────────────────────────────────────────────

def parse_data(texto_data: str) -> datetime:
    """Converte string de data do e-mail para datetime."""
    try:
        return parsedate_to_datetime(texto_data)
    except Exception:
        return datetime.min


def email_de_finaud(remetente: str, reply_to) -> bool:
    """
    Retorna True se o e-mail foi enviado por alguém da Finaud.
    - Se reply_to está preenchido com endereço não-Finaud → é cliente via suporte@
    - Se remetente tem domínio Finaud e sem reply_to externo → é Finaud
    """
    remetente = (remetente or "").lower()
    reply_to_str = (reply_to or "").lower()

    # reply_to presente e não-finaud → cliente enviou via grupo suporte
    if reply_to_str:
        return any(d in reply_to_str for d in DOMINIOS_FINAUD)

    # Sem reply_to: o próprio remetente define
    return any(d in remetente for d in DOMINIOS_FINAUD)


def extrair_email_puro(campo: str) -> str:
    """Extrai o endereço de e-mail de strings como 'Nome <email>'."""
    m = re.search(r"<([^>]+)>", campo or "")
    if m:
        return m.group(1).lower()
    return (campo or "").strip().lower()


def email_interno(remetente: str, destinatarios: str, reply_to) -> bool:
    """
    Retorna True se é e-mail interno Finaud → Finaud
    (Finaud mandou para Finaud, sem reply_to externo).
    """
    if not email_de_finaud(remetente, reply_to):
        return False
    dest = (destinatarios or "").lower()
    # Se todos os destinatários são Finaud → interno
    enderecos_dest = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", dest)
    if not enderecos_dest:
        return False
    return all(any(d in e for d in DOMINIOS_FINAUD) for e in enderecos_dest)


def corpo_curto(corpo: str, limite=200) -> bool:
    """Corpo do e-mail é muito curto — provável confirmação/agradecimento."""
    return len((corpo or "").strip()) <= limite


def contem_frase(texto: str, frases: list) -> str | None:
    """Retorna a primeira frase encontrada no texto, ou None."""
    texto_lower = (texto or "").lower()
    for f in frases:
        if f in texto_lower:
            return f
    return None


def eh_remetente_automatico(remetente: str, reply_to) -> bool:
    """Retorna True se o remetente é um sistema automático filtrado pelo Campo 1."""
    texto = ((remetente or "") + " " + (reply_to or "")).lower()
    return any(p in texto for p in REMETENTES_AUTOMATICOS)


def classificar_thread(emails_thread: list) -> dict:
    """
    Recebe lista de e-mails de uma thread (já ordenada por data).
    Retorna dict com: status, regra_nova, motivo, ultimo_email
    Retorna status='FILTRADA' quando o último remetente seria bloqueado pelo Campo 1.
    """
    ultimo = emails_thread[-1]
    remetente  = ultimo.get("remetente") or ""
    reply_to   = ultimo.get("reply_to")
    destinats  = ultimo.get("destinatarios") or ""
    assunto    = ultimo.get("assunto") or ""
    corpo      = ultimo.get("corpo_texto") or ""

    # ── Campo 1 — thread filtrada (não entra na triagem nova) ─────────────────
    if eh_remetente_automatico(remetente, str(reply_to or "")):
        return {
            "status": "FILTRADA",
            "regra_nova": "campo1-excluido",
            "motivo": f"Remetente automático filtrado pelo Campo 1: {remetente[:60]}",
            "ultimo_email": ultimo,
        }

    de_finaud  = email_de_finaud(remetente, reply_to)
    de_interno = email_interno(remetente, destinats, reply_to)

    # ── §8.1 — Aguardando Finaud ──────────────────────────────────────────────
    if not de_finaud:
        # Último e-mail é do cliente
        # A IA entende nuances — verificamos apenas se há sinal claro de agradecimento/confirmação
        frase_concl = contem_frase(corpo, FRASES_CONCLUIDA_CLIENTE)
        if frase_concl:
            return {
                "status": "CONCLUIDA",
                "regra_nova": "§8.3-cliente",
                "motivo": f"Cliente agradeceu/confirmou: '{frase_concl}' (IA valida nuances)",
                "ultimo_email": ultimo,
            }
        return {
            "status": "AGUARDANDO_FINAUD",
            "regra_nova": "§8.1-cliente",
            "motivo": "Último e-mail é do cliente",
            "ultimo_email": ultimo,
        }

    if de_interno:
        # Finaud encaminhou internamente — ainda não foi pro cliente
        return {
            "status": "AGUARDANDO_FINAUD",
            "regra_nova": "§8.1-interno",
            "motivo": "Último e-mail é interno Finaud→Finaud",
            "ultimo_email": ultimo,
        }

    # ── Finaud mandou o último — pode ser Aguardando Cliente ou Concluída ─────

    # Verificar sinais de conclusão
    corpo_lower = corpo.lower()
    assunto_lower = assunto.lower()

    # Sinal 1: "transmitido no BACEN"
    if "transmitido" in corpo_lower and "bacen" in corpo_lower:
        return {
            "status": "CONCLUIDA",
            "regra_nova": "§8.3-transmitido-bacen",
            "motivo": "Texto menciona 'transmitido no BACEN'",
            "ultimo_email": ultimo,
        }

    # Sinal 2: "transmitida no BACEN" / "enviado ao BACEN" / "protocolo no BACEN"
    frase_concl_fin = contem_frase(corpo, FRASES_CONCLUIDA_FINAUD)
    if frase_concl_fin:
        return {
            "status": "CONCLUIDA",
            "regra_nova": "§8.3-texto-conclusivo",
            "motivo": f"Texto conclusivo: '{frase_concl_fin}'",
            "ultimo_email": ultimo,
        }

    # Sinal 3: assunto com "RES:" e corpo muito curto (resposta formal, sem conteúdo novo)
    if PAD_ASSUNTO_RESPOSTA.match(assunto) and corpo_curto(corpo, limite=400):
        return {
            "status": "CONCLUIDA",
            "regra_nova": "§8.3-res-curto",
            "motivo": f"Resposta formal ('{assunto[:60]}') com corpo curto",
            "ultimo_email": ultimo,
        }

    # Sem sinal de conclusão → aguardando cliente
    return {
        "status": "AGUARDANDO_CLIENTE",
        "regra_nova": "§8.2-finaud-enviou",
        "motivo": "Finaud mandou o último e-mail sem sinal conclusivo",
        "ultimo_email": ultimo,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Carregando dados...")
    with open(ARQUIVO_EMAILS, encoding="utf-8") as f:
        emails = json.load(f)
    with open(ARQUIVO_CONCL, encoding="utf-8") as f:
        concl_auto = {r["threadId"]: r for r in json.load(f)}
    with open(ARQUIVO_AGUARD, encoding="utf-8") as f:
        aguard_auto = {r["threadId"]: r for r in json.load(f)}

    print(f"  {len(emails):,} e-mails carregados")
    print(f"  {len(concl_auto):,} threads concluídas (pipeline antigo)")
    print(f"  {len(aguard_auto):,} threads aguardando (pipeline antigo)")

    # Agrupar por thread e ordenar por data
    threads: dict[str, list] = {}
    for e in emails:
        tid = e.get("thread_root") or e.get("x_gm_thrid") or ""
        if tid:
            threads.setdefault(tid, []).append(e)

    for tid, lista in threads.items():
        lista.sort(key=lambda x: parse_data(x.get("data_email", "")))

    print(f"  {len(threads):,} threads distintas\n")

    # Aplicar regras §8
    resultados = {}
    for tid, lista in threads.items():
        resultados[tid] = classificar_thread(lista)

    # ── Contagem por status ───────────────────────────────────────────────────
    contagem = {}
    for r in resultados.values():
        k = r["status"]
        contagem[k] = contagem.get(k, 0) + 1

    filtradas = contagem.get("FILTRADA", 0)
    triagem   = {k: v for k, v in contagem.items() if k != "FILTRADA"}

    print("=" * 60)
    print("RESULTADO — CLASSIFICAÇÃO §8 (novo sistema)")
    print("=" * 60)
    print(f"  {'FILTRADAS (Campo 1)':<25} {filtradas:>6,}  ← não entram na triagem")
    print()
    for status, qtd in sorted(triagem.items()):
        print(f"  {status:<25} {qtd:>6,}")
    print(f"  {'TOTAL EM TRIAGEM':<25} {sum(triagem.values()):>6,} threads")

    # ── Contagem por regra ────────────────────────────────────────────────────
    por_regra: dict[str, int] = {}
    for r in resultados.values():
        if r["status"] != "FILTRADA":
            k = r["regra_nova"]
            por_regra[k] = por_regra.get(k, 0) + 1

    print("\n--- Por regra (excluindo filtradas) ---")
    for regra, qtd in sorted(por_regra.items()):
        print(f"  {regra:<35} {qtd:>6,}")

    # ── Comparação com pipeline antigo ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("COMPARAÇÃO COM PIPELINE ANTIGO (excluindo filtradas)")
    print("=" * 60)

    map_antigo = {}
    for tid in concl_auto:
        map_antigo[tid] = "CONCLUIDA"
    for tid in aguard_auto:
        map_antigo[tid] = "AGUARDANDO"

    # Threads sem classificação no pipeline antigo (excluindo filtradas)
    sem_antigo = [
        tid for tid in resultados
        if tid not in map_antigo and resultados[tid]["status"] != "FILTRADA"
    ]
    print(f"\nThreads NÃO classificadas pelo pipeline antigo: {len(sem_antigo):,}")

    # Divergências (excluindo filtradas)
    divergencias = []
    for tid, res in resultados.items():
        if res["status"] == "FILTRADA":
            continue
        status_novo = res["status"]
        status_ant  = map_antigo.get(tid, "SEM_CLASSIFICACAO")

        # Mapear novo → antigo para comparar
        if status_novo in ("AGUARDANDO_FINAUD", "AGUARDANDO_CLIENTE"):
            equiv_novo = "AGUARDANDO"
        else:
            equiv_novo = "CONCLUIDA"

        if status_ant != "SEM_CLASSIFICACAO" and equiv_novo != status_ant:
            divergencias.append({
                "threadId": tid,
                "status_novo": status_novo,
                "regra_nova": res["regra_nova"],
                "motivo_novo": res["motivo"],
                "status_antigo": status_ant,
                "motivo_antigo": (
                    concl_auto.get(tid, {}).get("motivo_triagem_auto_tecnico")
                    or aguard_auto.get(tid, {}).get("motivo")
                    or ""
                ),
                "assunto": res["ultimo_email"].get("assunto", "")[:80],
                "remetente": res["ultimo_email"].get("remetente", "")[:80],
                "reply_to": str(res["ultimo_email"].get("reply_to") or "")[:80],
                "corpo_trecho": (res["ultimo_email"].get("corpo_texto") or "")[:300],
            })

    print(f"Divergências (novo ≠ antigo):              {len(divergencias):,}")

    # ── Exemplos de divergências ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EXEMPLOS DE DIVERGÊNCIAS (primeiros 15)")
    print("=" * 60)

    for i, d in enumerate(divergencias[:15], 1):
        print(f"\n[{i}] Thread: {d['threadId']}")
        print(f"    Assunto:       {d['assunto']}")
        print(f"    Remetente:     {d['remetente']}")
        print(f"    Reply-To:      {d['reply_to']}")
        print(f"    NOVO  → {d['status_novo']} ({d['regra_nova']}): {d['motivo_novo']}")
        print(f"    ANTIGO→ {d['status_antigo']}: {d['motivo_antigo'][:120]}")
        print(f"    Corpo trecho:  {d['corpo_trecho'][:200].strip()}")

    # ── Threads sem classificação no antigo — exemplos ────────────────────────
    print("\n" + "=" * 60)
    print(f"THREADS SEM CLASSIFICAÇÃO NO PIPELINE ANTIGO (primeiros 10 de {len(sem_antigo):,})")
    print("=" * 60)

    for tid in sem_antigo[:10]:
        res = resultados[tid]
        ult = res["ultimo_email"]
        print(f"\nThread: {tid}")
        print(f"  Assunto:   {ult.get('assunto','')[:80]}")
        print(f"  Remetente: {(ult.get('remetente') or '')[:80]}")
        print(f"  Reply-To:  {str(ult.get('reply_to') or '')[:80]}")
        print(f"  Regra §8:  {res['status']} ({res['regra_nova']}) — {res['motivo']}")
        print(f"  Corpo:     {(ult.get('corpo_texto') or '')[:200].strip()}")

    # ── Salvar divergências em JSON para consulta ─────────────────────────────
    saida = os.path.join(
        os.path.dirname(__file__), "..", "resultados",
        "validacao_regras_secao8.json"
    )
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({
            "total_threads": len(threads),
            "contagem_por_status": contagem,
            "contagem_por_regra": por_regra,
            "total_divergencias": len(divergencias),
            "total_sem_antigo": len(sem_antigo),
            "divergencias": divergencias,
            "sem_antigo": [
                {
                    "threadId": tid,
                    "status_novo": resultados[tid]["status"],
                    "regra_nova": resultados[tid]["regra_nova"],
                    "assunto": resultados[tid]["ultimo_email"].get("assunto", ""),
                    "remetente": resultados[tid]["ultimo_email"].get("remetente", ""),
                }
                for tid in sem_antigo
            ],
        }, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Resultado completo salvo em: {saida}")


if __name__ == "__main__":
    main()
