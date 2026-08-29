"""
Testes do filtro §4 (eh_automatico) do validador_classificacao.py.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validador_classificacao import eh_automatico


def _thread(assunto: str = "", remetente: str = "") -> dict:
    return {"assunto": assunto, "mensagens": [{"remetente": remetente, "nomes_anexos": []}]}


# ── Casos que DEVEM ser filtrados ────────────────────────────────────────────

def test_filtro_codigo_verificacao_portugues():
    t = _thread("Seu código de verificação da conta de cvpar.com.br")
    assert eh_automatico(t) is not None

def test_filtro_codigo_verificacao_sem_acento():
    t = _thread("Codigo de verificacao - 123456")
    assert eh_automatico(t) is not None

def test_filtro_codigo_acesso():
    t = _thread("Seu código de acesso temporário")
    assert eh_automatico(t) is not None

def test_filtro_verification_code_ingles():
    t = _thread("Your verification code is 789012")
    assert eh_automatico(t) is not None

def test_filtro_codigo_seguranca():
    t = _thread("Código de segurança: 445566")
    assert eh_automatico(t) is not None

def test_filtro_via_microsoft():
    t = _thread("Reunião de alinhamento", remetente='"cliente (via Microsoft)" <noreply@microsoft.com>')
    assert eh_automatico(t) is not None

def test_filtro_via_google():
    t = _thread("Convite", remetente='"Calendário (via Google)" <calendar@google.com>')
    assert eh_automatico(t) is not None

def test_filtro_aceito_convite():
    t = _thread("Aceito: Reunião semanal")
    assert eh_automatico(t) is not None

def test_filtro_aceita_convite():
    t = _thread("Aceita: Risk S5 — reunião mensal")
    assert eh_automatico(t) is not None


# ── Casos que NÃO devem ser filtrados ────────────────────────────────────────

def test_nao_filtra_email_normal_cadoc():
    t = _thread("DDR - Maio/2026", remetente='"João Silva" <joao@cliente.com.br>')
    assert eh_automatico(t) is None

def test_nao_filtra_suporte_normal():
    t = _thread("Erro no sistema DLO", remetente='"Ana Costa" <ana@finaud.com.br>')
    assert eh_automatico(t) is None

def test_nao_filtra_assunto_vazio():
    t = _thread("", remetente='"Cliente" <cliente@empresa.com.br>')
    assert eh_automatico(t) is None


# ── FogBugz: filtrado pelo assunto, independente do remetente ─────────────────

@pytest.mark.parametrize("assunto", [
    "FogBugz (Caso 8568) RISK DRIVER - BC - Instrução Normativa BCB Nº 771",
    "FogBugz (Caso 8291) DLI - Verificar erro na tela DLI",
    "FogBugz (Caso 5972) RISK DRIVER - Disponibilizar base atualizada",
])
def test_fogbugz_filtrado_pelo_assunto_independente_de_remetente(assunto):
    """FogBugz deve ser filtrado apenas pelo assunto — remetente pode variar."""
    t = _thread(assunto, remetente='"Qualquer Nome" <qualquer@outro.com.br>')
    assert eh_automatico(t) is not None, \
        f"FogBugz não filtrado para assunto: '{assunto}'"


def test_filtro_cestaincentivo_bloqueado():
    """contato@cestaincentivo.com.br deve ser bloqueado pelo endereço exato (26/08/2026)."""
    t = _thread("Cesta de Solidariedade", remetente='"Cesta Incentivo" <contato@cestaincentivo.com.br>')
    motivo = eh_automatico(t)
    assert motivo is not None, "cestaincentivo.com.br não foi bloqueado"
    assert 'cestaincentivo.com.br' in motivo
