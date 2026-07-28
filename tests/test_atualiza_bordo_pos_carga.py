"""
Testa _atualiza_data_de_carga_no_arquivo_de_bordo em executar_tudo.py.

Cenários cobertos:
- Todos os scripts de triagem E enriquecimento OK → ambos os campos atualizados
- Só grupo de triagem completo → só campo triagem atualizado
- Só grupo de enriquecimento completo → só campo enriquecimento atualizado
- Script 11 OK mas script 09 falhou → triagem NÃO atualizada (dado incompleto)
- Nenhum script rodou → arquivo não é modificado
- Arquivo inexistente → sem exceção
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from executar_tudo import _atualiza_data_de_carga_no_arquivo_de_bordo

_LINHA_ESTADO = (
    "| 1.002 | 3.673 | 4.675 | **648 passed, 23 xfailed** "
    "| **16/06/2026** ⚠️ 8 dias | **16/06/2026** ⚠️ 8 dias |\n"
)

_CONTEUDO_SESSAO = f"""\
# SESSAO_ATUAL — Oráculo 360 Finaud

| AG (aguardando) | CO (concluídas) | Total | pytest | Última carga triagem (02→11) | Último enriquecimento (12→17) |
|-----------------|-----------------|-------|--------|------------------------------|-------------------------------|
{_LINHA_ESTADO}
"""

_HOJE = datetime.now().strftime("%d/%m/%Y")

_TRIAGEM_COMPLETA = {
    "02_coletar_emails_gmail",
    "09_integrar_dados_painel",
    "11_triar_threads_por_cadoc",
}

_ENRIQUECIMENTO_COMPLETO = {
    "12_enriquecer_texto_imagens",
    "16_resumir_retorno_bacen_llm",
}


def _escrever_sessao(tmp_path) -> Path:
    sessao = tmp_path / "SESSAO_ATUAL.md"
    sessao.write_text(_CONTEUDO_SESSAO, encoding="utf-8")
    return sessao


def test_ambos_os_grupos_completos_atualizam_ambos_os_campos(tmp_path):
    sessao = _escrever_sessao(tmp_path)

    _atualiza_data_de_carga_no_arquivo_de_bordo(
        _TRIAGEM_COMPLETA | _ENRIQUECIMENTO_COMPLETO,
        _caminho_sessao=str(sessao),
    )

    conteudo = sessao.read_text(encoding="utf-8")
    assert f"**{_HOJE}** ✅" in conteudo
    assert "16/06/2026" not in conteudo
    assert "⚠️" not in conteudo


def test_so_triagem_completa_atualiza_so_campo_triagem(tmp_path):
    sessao = _escrever_sessao(tmp_path)

    _atualiza_data_de_carga_no_arquivo_de_bordo(
        _TRIAGEM_COMPLETA,
        _caminho_sessao=str(sessao),
    )

    conteudo = sessao.read_text(encoding="utf-8")
    assert f"**{_HOJE}** ✅" in conteudo
    assert "**16/06/2026** ⚠️ 8 dias" in conteudo  # enriquecimento intacto


def test_so_enriquecimento_completo_atualiza_so_campo_enriquecimento(tmp_path):
    sessao = _escrever_sessao(tmp_path)

    _atualiza_data_de_carga_no_arquivo_de_bordo(
        _ENRIQUECIMENTO_COMPLETO,
        _caminho_sessao=str(sessao),
    )

    conteudo = sessao.read_text(encoding="utf-8")
    assert f"**{_HOJE}** ✅" in conteudo
    assert "**16/06/2026** ⚠️ 8 dias" in conteudo  # triagem intacta


def test_script_11_ok_mas_09_falhou_nao_atualiza_triagem(tmp_path):
    """Script 09 (integrador) falhou — dados incompletos, data de triagem não deve ser gravada."""
    sessao = _escrever_sessao(tmp_path)
    conteudo_antes = sessao.read_text(encoding="utf-8")

    lista_ok = {
        "02_coletar_emails_gmail",
        "11_triar_threads_por_cadoc",  # script 09 ausente — falhou
    }
    _atualiza_data_de_carga_no_arquivo_de_bordo(lista_ok, _caminho_sessao=str(sessao))

    assert sessao.read_text(encoding="utf-8") == conteudo_antes


def test_nenhum_script_nao_modifica_arquivo(tmp_path):
    sessao = _escrever_sessao(tmp_path)
    conteudo_antes = sessao.read_text(encoding="utf-8")

    _atualiza_data_de_carga_no_arquivo_de_bordo(set(), _caminho_sessao=str(sessao))

    assert sessao.read_text(encoding="utf-8") == conteudo_antes


def test_arquivo_inexistente_nao_levanta_excecao(tmp_path):
    caminho = str(tmp_path / "nao_existe.md")
    _atualiza_data_de_carga_no_arquivo_de_bordo(
        _TRIAGEM_COMPLETA,
        _caminho_sessao=caminho,
    )
