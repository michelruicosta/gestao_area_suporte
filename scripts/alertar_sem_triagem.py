# -*- coding: utf-8 -*-
"""
Alerta de threads sem triagem após carga — Oráculo 360.

Identifica threads do JSON 03 que não foram classificadas como Aguardando
nem como Concluídas e envia e-mail de alerta para os destinatários
configurados em data/json/config/alertas.json (id: sem_triagem_pos_carga).

Uso autônomo (chamado pelo executar_tudo ou manualmente):
    python scripts/alertar_sem_triagem.py

Ou importado pelo painel (tela de alertas — botão "Enviar"):
    from scripts.alertar_sem_triagem import buscar_sem_triagem, montar_html_sem_triagem, enviar_alerta_sem_triagem
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
for _p in (_SCRIPTS, _BASE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from paths import F_INTEGRADOR, load_concluidas, load_aguardando  # noqa: E402

# CADOCs que não passam por triagem — não geram alerta
CADOCS_SEM_TRIAGEM = frozenset({
    "IGNORADO",
    "FILTRADO_POR_DATA",
    "RISK_DRIVER_ALERTA",
    "RISK_DRIVER_RELATORIO",
    "RISK_DRIVER_RESP_AUTO",
    "FOGBUGZ",
    "LEIAUTES_BACEN",
})


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def buscar_sem_triagem() -> list[dict]:
    """Retorna lista de threads do JSON 03 sem triagem (nem AG nem CO)."""
    if not os.path.isfile(F_INTEGRADOR):
        return []

    with open(F_INTEGRADOR, encoding="utf-8") as f:
        dados = json.load(f)

    threads = dados.get("threads") or []
    co = load_concluidas()
    ag = load_aguardando()
    classificados = {r["threadId"] for r in co} | {r["threadId"] for r in ag}

    pendentes = []
    for t in threads:
        cadoc = (t.get("cadoc") or "").strip()
        if cadoc in CADOCS_SEM_TRIAGEM:
            continue
        if t.get("threadId", "") in classificados:
            continue
        pendentes.append(t)

    return pendentes


# ---------------------------------------------------------------------------
# Montagem do HTML do e-mail
# ---------------------------------------------------------------------------

def montar_html_sem_triagem(pendentes: list[dict]) -> str:
    """Monta o HTML do corpo do e-mail com a lista de threads sem triagem."""
    from email_alerta_template import montar_email_alerta, SEVERIDADE, tabela_threads

    total = len(pendentes)
    data_ref = datetime.now().strftime("%d/%m/%Y")

    linhas = [
        [
            t.get("cliente") or t.get("empresa") or "—",
            t.get("cadoc") or "(sem categoria)",
            t.get("threadId", "—"),
        ]
        for t in pendentes[:50]
    ]

    tabela = tabela_threads(["Empresa", "Categoria", "Thread ID"], linhas)

    rodape_extra = ""
    if total > 50:
        rodape_extra = (
            f'<p style="color:#9ca3af;font-size:12px;margin-top:8px;">'
            f'... e mais {total - 50} caso(s). Ver log completo no painel.</p>'
        )

    corpo = (
        f'<p style="font-size:14px;line-height:1.7;margin:0 0 16px;">'
        f'A carga de <strong>{data_ref}</strong> concluiu, mas <strong>{total} thread(s)</strong> '
        f'ficaram sem classificação — não estão nem em Aguardando nem em Concluídas. '
        f'Verifique e corrija antes da próxima carga.</p>'
        + tabela
        + rodape_extra
    )

    return montar_email_alerta(
        severidade=SEVERIDADE.ATENCAO,
        titulo=f"{total} thread(s) sem triagem",
        subtitulo=f"Verificação pós-carga · {data_ref}",
        corpo_html=corpo,
        rodape_extra=f"Alerta automático pós-carga · {data_ref}",
    )


# ---------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------

def _destinatarios() -> list[str]:
    """Lê destinatários do alertas.json para o alerta sem_triagem_pos_carga."""
    try:
        cfg_path = os.path.join(_BASE, "data", "json", "config", "alertas.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        for al in cfg.get("alertas", []):
            if al.get("id") == "sem_triagem_pos_carga" and al.get("ativo", True):
                return al.get("destinatarios", [])
    except Exception:
        pass
    return list(filter(None, [
        os.getenv("ORACULO_ALERTA_DESTINO", "").strip() or os.getenv("ADMIN_EMAIL", "").strip()
    ]))


def enviar_alerta_sem_triagem(html: str, destinatarios: list[str], total: int) -> tuple[bool, str]:
    """Envia o e-mail via SMTP. Retorna (sucesso, mensagem)."""
    if os.environ.get("ORACULO_ALERTA_EMAIL", "").strip().lower() in ("0", "false", "no", "off"):
        return False, "Envio desativado (ORACULO_ALERTA_EMAIL=0)"

    remetente = os.getenv("EMAIL_USER", "").strip()
    senha = os.getenv("EMAIL_PASS", "").strip()

    if not remetente or not senha:
        return False, "SMTP não configurado (EMAIL_USER/EMAIL_PASS ausentes)"
    if not destinatarios:
        return False, "Nenhum destinatário configurado"

    data_ref = datetime.now().strftime("%d/%m/%Y")
    assunto = f"[Oráculo 360] {total} thread(s) sem triagem após carga de {data_ref}"

    ok_geral, err_geral = True, ""
    for destino in destinatarios:
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destino
        msg["Subject"] = assunto
        msg.attach(MIMEText(html, "html"))
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg)
            server.quit()
        except Exception as exc:
            ok_geral, err_geral = False, str(exc)[:120]

    if ok_geral:
        return True, f"Alerta enviado para {', '.join(destinatarios)}"
    return False, f"Falha SMTP: {err_geral}"


# ---------------------------------------------------------------------------
# Execução autônoma (chamada pelo executar_tudo / pipeline_jobs)
# ---------------------------------------------------------------------------

def main() -> int:
    """Verifica threads sem triagem e envia alerta se houver. Retorna 0 ou 1."""
    pendentes = buscar_sem_triagem()
    total = len(pendentes)

    if total == 0:
        print("  [OK] Nenhuma thread sem triagem.")
        return 0

    print(f"  [ALERTA] {total} thread(s) sem triagem encontrada(s):")
    for t in pendentes:
        print(f"    {t.get('threadId', '?')}  cadoc={t.get('cadoc') or '(vazio)'}  "
              f"cliente={t.get('cliente') or t.get('empresa') or '—'}")

    destinatarios = _destinatarios()
    html = montar_html_sem_triagem(pendentes)
    ok, msg = enviar_alerta_sem_triagem(html, destinatarios, total)
    status = "[OK]" if ok else "[AVISO]"
    print(f"  {status} E-mail: {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
