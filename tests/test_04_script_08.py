"""
QA – Script 08 (integrador): _parse_data_br.

DD/MM/YYYY em Brasília e RFC 2822 geram data_iso e timestamp_epoch corretos.
Alinhado à seção "Script 08" do REGISTRO_CORRECOES.md.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def test_parse_data_br_dd_mm_yyyy_e_rfc2822():
    """_parse_data_br aceita DD/MM/YYYY HH:MM (Brasília) e RFC 2822."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _parse_data_br = mod._parse_data_br

    data_iso, _, epoch = _parse_data_br("13/02/2026 11:48")
    assert data_iso == "2026-02-13", "data_iso esperado 2026-02-13, obtido " + str(data_iso)
    assert epoch > 0

    data_iso2, _, epoch2 = _parse_data_br("Fri, 13 Feb 2026 14:48:31 +0000")
    assert epoch2 > 0 and "2026" in data_iso2


def test_encaminhados_trunca_citacao_aninhada_e_rodape():
    """
    Cada bloco De:/Enviada em: não deve repetir corpo dos níveis internos;
    rodapés comuns (Trustee, BC) são cortados. Ver REGISTRO 2026-03-25.
    """
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8b", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ext = mod._extrair_encaminhados_de_corpo

    chain = (
        "Algo no topo\n\n"
        "De: Gustavo Teste\n"
        "Enviada em: quinta-feira, 19 de fevereiro de 2026 20:45\n"
        "Para: lucas@test.com\n"
        "Assunto: ENC teste\n\n"
        "Trecho apenas do nível 19.\n\n"
        "De: Corporativo <corp@test.com>\n"
        "Enviada em: quarta-feira, 18 de fevereiro de 2026 07:49\n"
        "Para: g@test.com\n"
        "Assunto: ENC dois\n\n"
        "Trecho apenas do nível 18.\n\n"
        "De: dlo@bcb.gov.br\n"
        "Enviada em: terça-feira, 17 de fevereiro de 2026 13:56\n"
        "Para: c@test.com\n"
        "Assunto: BC\n\n"
        "Trecho apenas do nível 17.\n"
        "Mensagem referente ao Correio Eletrônico: 999.\n"
    )
    enc = ext(chain)
    assert len(enc) >= 3, "esperado pelo menos 3 níveis De:/Enviada em:"
    corpos = [e.get("corpo") or "" for e in enc]
    assert any("Trecho apenas do nível 19." in c for c in corpos)
    assert any("Trecho apenas do nível 18." in c for c in corpos)
    assert any("Trecho apenas do nível 17." in c for c in corpos)
    # o corpo do 19 não deve carregar o texto do 18 (aninhado removido)
    for e in enc:
        if "nível 19" in (e.get("corpo") or ""):
            assert "nível 18" not in (e.get("corpo") or ""), "citação 19 não deve repetir 18"
            assert "nível 17" not in (e.get("corpo") or ""), "citação 19 não deve repetir 17"

    rodape = (
        "De: Alguém <a@b.com>\n"
        "Enviada em: segunda-feira, 23 de fevereiro de 2026 10:00\n"
        "Para: x@y.com\n"
        "Assunto: X\n\n"
        "Mensagem útil aqui.\n\n"
        "Antes de imprimir pense na sua responsabilidade com o Meio Ambiente.\n\n"
        "Este e-mail pode conter informação confidencial, privilegiada ou protegida.\n"
    )
    one = ext(rodape)
    assert len(one) == 1
    assert "Mensagem útil aqui." in one[0]["corpo"]
    assert "Antes de imprimir" not in one[0]["corpo"]
    assert "confidencial, privilegiada" not in one[0]["corpo"]


def test_corpo_evento_prioriza_corpo_limpo_do_classificador():
    """Eventos no 03 devem copiar corpo_limpo do 02 quando ``corpo`` vem vazio — modal operacional."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8d", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = mod._corpo_evento_a_partir_classificador
    raw, limpo = fn({"corpo": "", "corpo_limpo": "Texto útil do 02 sem corpo bruto."})
    assert "Texto útil" in limpo
    assert raw == ""


def test_limpar_corpo_corta_em_cid_inline_assinatura():
    """Texto após [cid: (assinatura Outlook) não entra em corpo_limpo — REGISTRO 2026-03-31."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8c", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    limpar = mod.limpar_corpo_email
    raw = (
        "Olá,\n\nConseguiu analisar?\n\n"
        "[cid:image004.png@01DCA4AC.3C285A80]\n\n"
        "Gustavo Rudink\nRisco\nAv. Brig.\n"
    )
    out = limpar(raw)
    assert "Conseguiu analisar" in out
    assert "Gustavo Rudink" not in out
    assert "image004" not in out.lower()


def test_limpar_corpo_corta_disclaimer_this_email_is_confidential():
    """Variante EN sem “(including any attachments)” — comum em bancos/corretoras (2026-04-02)."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8d", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    limpar = mod.limpar_corpo_email
    raw = (
        "Boa tarde.\n\nRemessa de dezembro/2025, segue documento.\n\n"
        "This email is confidential and subject to important disclaimers including "
        "Customer Identification Program.\n"
    )
    out = limpar(raw)
    assert "Remessa de dezembro" in out
    assert "confidential" not in out.lower()
    assert "Customer Identification" not in out


def test_limpar_corpo_corta_at_te_assinatura_e_disclaimer_esta_mensagem():
    """2026-04: após At.te/assinatura Moneycorp e «Esta mensagem pode conter» some do corpo_limpo."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8e", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    limpar = mod.limpar_corpo_email
    raw = (
        "Boa tarde, segue análise do erro.\n\n"
        "At.te,\n\n"
        "Ayrton Marra\n\n"
        "Senior Accounting Analyst\n\n"
        "Tel.:\n+55 11 3018 1830\n\n"
        "Esta mensagem pode conter conteúdo confidencial ou informação privilegiada. "
        "Se você recebeu esta mensagem indevidamente, apague.\n"
    )
    out = limpar(raw)
    assert "análise do erro" in out
    assert "At.te" not in out
    assert "Ayrton Marra" not in out
    assert "privilegiada" not in out.lower()


def test_limpar_corpo_mantem_atenciosamente_solicitamos():
    """Frase operacional «Atenciosamente solicitamos» não deve ser cortada pelo encerramento cordial."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8f", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    limpar = mod.limpar_corpo_email
    raw = "Atenciosamente solicitamos o envio do documento até sexta-feira.\n"
    out = limpar(raw)
    assert "solicitamos" in out
    assert "sexta-feira" in out


def test_limpar_corpo_corta_at_te_colado_cep_e_disclaimer_uma_linha():
    """Rodapé Moneycorp numa linha: At.te + CEP + «Esta mensagem pode conter» — corta a partir de At.te."""
    path_08 = os.path.join(RAIZ, "scripts", "09_integrar_dados_painel.py")
    spec = importlib.util.spec_from_file_location("o8g", path_08)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    limpar = mod.limpar_corpo_email
    raw = (
        "Podem avaliar o erro, por favor? At.te, São Paulo SP, CEP 04534-004 "
        "Esta mensagem pode conter conteúdo confidencial ou informação privilegiada. "
        "Se você recebeu esta mensagem indevidamente, apague.\n"
    )
    out = limpar(raw)
    assert "avaliar o erro" in out
    assert "At.te" not in out
    assert "04534-004" not in out
    assert "confidencial" not in out.lower()


TESTS = [
    test_parse_data_br_dd_mm_yyyy_e_rfc2822,
    test_encaminhados_trunca_citacao_aninhada_e_rodape,
    test_corpo_evento_prioriza_corpo_limpo_do_classificador,
    test_limpar_corpo_corta_em_cid_inline_assinatura,
    test_limpar_corpo_corta_disclaimer_this_email_is_confidential,
    test_limpar_corpo_corta_at_te_assinatura_e_disclaimer_esta_mensagem,
    test_limpar_corpo_mantem_atenciosamente_solicitamos,
    test_limpar_corpo_corta_at_te_colado_cep_e_disclaimer_uma_linha,
]
