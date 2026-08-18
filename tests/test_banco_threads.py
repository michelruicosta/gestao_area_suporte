"""
test_banco_threads.py
Testes para a lógica de determinação de status de workflow em scripts/banco_threads.py.
Cobre §8.1 (Aguardando Finaud), §8.2 (Aguardando Cliente), §8.3 (Concluída) e
§8.6 (Forwards) da spec.
"""
from __future__ import annotations

import os
import sys

import pytest

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import banco_threads as bt


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msg(
    remetente: str,
    corpo: str = '',
    assunto: str = '',
    nomes_anexos: list | None = None,
    destinatarios: str = '',
    reply_to: str = '',
) -> dict:
    return {
        'remetente': remetente,
        'corpo_texto': corpo,
        'assunto': assunto,
        'nomes_anexos': nomes_anexos or [],
        'destinatarios': destinatarios,
        'reply_to': reply_to,
    }


FINAUD  = 'Monica <monica@finaud.com.br>'
SUPORTE = 'Sarah Sá <suporte@finaud.com.br>'
CLIENTE = 'João <joao@bancox.com.br>'

# Corpo Formato A: separador com traços, Para: aponta para cliente externo
_FORWARD_A_PARA_CLIENTE = (
    'Registrando internamente.\n\n'
    '---------- Forwarded message ----------\n'
    'De: Sarah Sá <suporte@finaud.com.br>\n'
    'Para: Jacilaine Lima <jnlima@planner.com.br>\n'
    'Assunto: DDR 2011 - 13/08/2026\n\n'
    'Prezada, segue o arquivo DDR conforme solicitado.'
)

# Corpo Formato A: Para: aponta para outra Finaud (interno genuíno)
_FORWARD_A_PARA_FINAUD = (
    'Monica, por favor verifique.\n\n'
    '---------- Forwarded message ----------\n'
    'De: Andrea <andrea@finaud.com.br>\n'
    'Para: Monica <monica@finaud.com.br>\n'
    'Assunto: Verificar urgente\n\n'
    'Precisa de atenção.'
)

# Corpo Formato B: headers com >, De: @finaud, Para: cliente externo
_FORWARD_B_PARA_CLIENTE = (
    'Registro interno.\n\n'
    '> De: Andrea Inacio <andrea.inacio@finaud.com.br>\n'
    '> To: William Barbosa <william.oliveira@miraeinvest.com.br>\n'
    '> Assunto: DRL julho/2026\n'
)

# Falso positivo: "mensagem encaminhada" em texto corrido, sem traços
_FALSO_POSITIVO = (
    'Conforme a mensagem encaminhada anteriormente, confirmamos o recebimento.\n'
)


# ── _extrair_texto_novo ───────────────────────────────────────────────────────

def test_extrair_sem_historico():
    assert bt._extrair_texto_novo('texto simples') == 'texto simples'


def test_extrair_remove_linhas_citadas():
    corpo = 'Obrigado.\n> Segue o arquivo.\n> Att, Finaud'
    resultado = bt._extrair_texto_novo(corpo)
    assert '>' not in resultado
    assert 'Obrigado' in resultado


def test_extrair_corta_no_separador_tracos():
    corpo = 'Ok, recebido.\n---\nTexto do histórico antigo'
    resultado = bt._extrair_texto_novo(corpo)
    assert 'Ok, recebido' in resultado
    assert 'histórico' not in resultado


def test_extrair_corta_no_separador_on_wrote():
    corpo = 'Confirmado.\nOn Mon, 17 Aug 2026 wrote:\n> mensagem antiga'
    resultado = bt._extrair_texto_novo(corpo)
    assert 'Confirmado' in resultado
    assert 'mensagem antiga' not in resultado


def test_extrair_corpo_vazio():
    assert bt._extrair_texto_novo('') == ''


# ── _determinar_status — lista vazia ─────────────────────────────────────────

def test_status_sem_mensagens():
    assert bt._determinar_status([])[0] == 'Aguardando Finaud'


# ── _determinar_status — regra especial "transmitido no BACEN" ───────────────

def test_status_transmitido_bacen_pelo_cliente():
    """Cliente avisa transmissão ao BACEN → Concluída (regra especial §8.3)."""
    msgs = [_msg(CLIENTE, corpo='Transmitido no BACEN com sucesso.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_transmitida_bacen_variacao():
    """Variação 'transmitida no BACEN' também encerra."""
    msgs = [_msg(FINAUD, corpo='Arquivo transmitida no BACEN hoje.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_transmitido_bacen_no_historico_nao_conta():
    """'transmitido no BACEN' só no histórico citado (linha >) → NÃO encerra."""
    corpo = 'Preciso do relatório atualizado.\n> Transmitido no BACEN em agosto.'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# ── _determinar_status — remetente Finaud ─────────────────────────────────────

def test_status_finaud_res_no_assunto():
    """'RES:' no assunto com remetente Finaud → Concluída."""
    msgs = [_msg(FINAUD, assunto='RES: DDR_2011 Banco X')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_com_anexo():
    """Finaud envia mensagem com anexo → Concluída."""
    msgs = [_msg(FINAUD, nomes_anexos=['DDR_2011_20260817.zip'])]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_frase_segue_em_anexo():
    """Finaud usa 'segue em anexo' no texto → Concluída."""
    msgs = [_msg(FINAUD, corpo='Conforme combinado, segue em anexo o relatório.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_conforme_solicitado():
    """Finaud usa 'conforme solicitado' → Concluída."""
    msgs = [_msg(FINAUD, corpo='Conforme solicitado, segue o DDR atualizado.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_procedemos_com():
    """Finaud usa 'procedemos com' → Concluída."""
    msgs = [_msg(FINAUD, corpo='Procedemos com o envio ao BACEN.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_notificacao_foi_encaminhado_bc():
    """Finaud notifica que encaminhou ao BC → Concluída, sem pedido de resposta."""
    msgs = [_msg(FINAUD, corpo='Prezados, bom dia.\n\nInformo que foi encaminhado o arquivo de remessa DRL ao BC, ref. julho/2026.\n\nAtenciosamente.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_notificacao_informamos_encaminhado():
    """Finaud usa 'informamos que foi encaminhado' → Concluída."""
    msgs = [_msg(FINAUD, corpo='Informamos que foi encaminhado o DDR referente a 10/08.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_notificacao_foi_encaminhado_bacen():
    """Finaud usa 'foi encaminhado ao bacen' → Concluída."""
    msgs = [_msg(FINAUD, corpo='O arquivo foi encaminhado ao BACEN conforme protocolo.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_finaud_sem_sinal_encerramento():
    """Finaud respondeu mas sem sinal de encerramento → Aguardando Cliente."""
    msgs = [_msg(FINAUD, corpo='Verificamos aqui, precisamos de mais informações.')]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Cliente'


def test_status_finaud_res_minusculo():
    """'RES:' case-insensitive."""
    msgs = [_msg(FINAUD, assunto='res: DDR_2011 Banco X')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# ── _determinar_status — remetente cliente ────────────────────────────────────

def test_status_cliente_so_obrigado():
    """Cliente só disse 'obrigado' → Concluída."""
    msgs = [_msg(CLIENTE, corpo='Obrigado!')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_cliente_ok_recebido():
    """Cliente disse 'ok, recebido' → Concluída."""
    msgs = [_msg(CLIENTE, corpo='Ok, recebido.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_cliente_de_acordo():
    """Cliente disse 'de acordo' → Concluída."""
    msgs = [_msg(CLIENTE, corpo='De acordo, obrigado.')]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_status_cliente_conteudo_real():
    """Cliente mandou conteúdo real (sem pergunta) → Aguardando Finaud."""
    msgs = [_msg(CLIENTE, corpo='Segue os dados para análise.')]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


def test_status_veto_obrigado_com_pergunta():
    """Agradecimento + pergunta no mesmo e-mail → Aguardando Finaud (veto §8.3)."""
    msgs = [_msg(CLIENTE, corpo='Obrigado! Mas quando chegará o arquivo de setembro?')]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


def test_status_cliente_so_pergunta():
    """Cliente fez apenas uma pergunta → Aguardando Finaud."""
    msgs = [_msg(CLIENTE, corpo='Boa tarde, quando será enviado o arquivo?')]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# ── _determinar_status — reabertura de caso (§8.4) ───────────────────────────

def test_status_reabertura_apos_concluida():
    """Thread 'concluída' → cliente manda conteúdo real → volta para Aguardando Finaud."""
    msgs = [
        _msg(FINAUD, corpo='Segue em anexo o DDR.', nomes_anexos=['DDR.zip']),
        _msg(CLIENTE, corpo='Obrigado!'),
        _msg(CLIENTE, corpo='Preciso do arquivo atualizado com os dados de agosto.'),
    ]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


def test_status_reabertura_so_ultimo_e_mail_importa():
    """A função olha SÓ o último e-mail, não o histórico."""
    msgs = [
        _msg(CLIENTE, corpo='Segue os dados solicitados.'),
        _msg(FINAUD, corpo='Segue em anexo.', nomes_anexos=['arquivo.zip']),
    ]
    # Último é da Finaud com anexo → Concluída
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# ── _determinar_status — forwards §8.6 ───────────────────────────────────────

# Cenário 1a: Finaud→suporte, forward Formato A para cliente, com arquivo real → Concluída
def test_forward_1a_formato_a_com_arquivo():
    """§8.6 Cenário 1a: forward para cliente + arquivo .zip → Concluída."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_A_PARA_CLIENTE,
        destinatarios='suporte@finaud.com.br',
        nomes_anexos=['DDR_20260813.zip'],
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída'
    assert 'entregou arquivo' in motivo


# Cenário 1a: arquivo real + imagens (imagens não contam, .zip conta) → Concluída
def test_forward_1a_arquivo_real_com_imagens():
    """§8.6 Cenário 1a: arquivo .zip + imagens inline → Concluída (imagens ignoradas)."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_A_PARA_CLIENTE,
        destinatarios='suporte@finaud.com.br',
        nomes_anexos=['image001.png', 'DDR_20260813.zip'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# Cenário 1b-concluída: RES: no assunto → Concluída
def test_forward_1b_res_no_assunto():
    """§8.6 Cenário 1b: forward para cliente + RES: no assunto → Concluída."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_A_PARA_CLIENTE,
        assunto='RES: DDR 2011 - 13/08/2026',
        destinatarios='suporte@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# Cenário 1b-concluída: frase conclusiva no texto novo (antes do bloco forward) → Concluída
def test_forward_1b_frase_conclusiva():
    """§8.6 Cenário 1b: frase conclusiva no texto novo + forward para cliente → Concluída.
    Nota: texto novo vem ANTES do separador --- (depois é cortado por _extrair_texto_novo)."""
    corpo = 'Conforme solicitado, segue o encaminhamento.\n\n' + _FORWARD_A_PARA_CLIENTE
    msgs = [_msg(
        SUPORTE,
        corpo=corpo,
        destinatarios='suporte@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# Cenário 1b-padrão: forward para cliente, sem sinal claro → Aguardando Cliente
def test_forward_1b_padrao_aguarda_cliente():
    """§8.6 Cenário 1b-padrão: forward para cliente sem sinal → Aguardando Cliente."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_A_PARA_CLIENTE,
        destinatarios='suporte@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Cliente'


# Cenário 3: Finaud→Finaud sem forward → E-mail interno → Aguardando Finaud
def test_forward_cenario3_interno_sem_forward():
    """§8.6 Cenário 3: Finaud→Finaud sem forward → Aguardando Finaud."""
    msgs = [_msg(
        SUPORTE,
        corpo='Monica, por favor verifique este caso.',
        destinatarios='monica@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# Cenário 3: Finaud→Finaud COM forward mas Para: também Finaud → Aguardando Finaud
def test_forward_cenario3_forward_para_finaud():
    """§8.6 Cenário 3: forward cujo Para: é @finaud → E-mail interno → Aguardando Finaud."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_A_PARA_FINAUD,
        destinatarios='suporte@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# Formato B (setas >) — forward de Finaud para cliente externo → detectado corretamente
def test_forward_formato_b_setas_para_cliente():
    """§8.6 Formato B: > De: @finaud > Para: cliente → tratado como forward para cliente."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_B_PARA_CLIENTE,
        destinatarios='suporte@finaud.com.br',
    )]
    # Sem arquivo e sem frase conclusiva → Aguardando Cliente (1b-padrão)
    assert bt._determinar_status(msgs)[0] == 'Aguardando Cliente'


# Falso positivo: "mensagem encaminhada" em texto corrido sem traços → não ativa §8.6
def test_forward_falso_positivo_texto_corrido():
    """§8.6 Falso positivo: 'mensagem encaminhada' em parágrafo normal → Aguardando Finaud."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FALSO_POSITIVO,
        destinatarios='suporte@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# ── Regressões — comportamentos existentes não mudam ────────────────────────

def test_regressao_cliente_para_finaud_sem_forward():
    """Regressão §8.1: cliente envia sem forward → Aguardando Finaud."""
    msgs = [_msg(CLIENTE, corpo='Segue os dados para análise.')]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


def test_regressao_finaud_com_anexo_para_cliente():
    """Regressão §8.3: Finaud envia com anexo direto ao cliente → Concluída."""
    msgs = [_msg(FINAUD, nomes_anexos=['arquivo.zip'])]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_regressao_finaud_interno_genuino():
    """Regressão §8.1: Finaud→Finaud sem forward → E-mail interno → Aguardando Finaud."""
    msgs = [_msg(
        FINAUD,
        corpo='Andrea, pode cuidar deste caso?',
        destinatarios='andrea@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# ── §8.7 — internos informativos ─────────────────────────────────────────────

def test_interno_divulgacao_instrucao_normativa():
    """§8.7: 'Divulgação...' Finaud→Finaud → Concluída — informativo."""
    msgs = [_msg(
        FINAUD,
        assunto='Divulgação Instrução Normativa BCB nº 761',
        corpo='Prezados, segue a IN para conhecimento.',
        destinatarios='rafael@finaud.com.br',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída'
    assert 'nformativo' in motivo


def test_interno_boas_vindas():
    """§8.7: 'Boas-Vindas...' Finaud→Finaud → Concluída — informativo."""
    msgs = [_msg(
        FINAUD,
        assunto='Boas-Vindas ao time FINAUD - Miguel Santos',
        corpo='Olá Miguel, seja bem-vindo!',
        destinatarios='miguel@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_interno_comunicado_saida_res():
    """§8.7: 'RES: Comunicado de Saida' — strip do RES: antes de checar → Concluída."""
    msgs = [_msg(
        FINAUD,
        assunto='RES: Comunicado de Saida',
        corpo='Boa sorte na nova jornada!',
        destinatarios='pedro@finaud.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_interno_operacional_nao_vira_informativo():
    """Regressão §8.7: Finaud→Finaud operacional (sem assunto informativo) → Aguardando Finaud."""
    msgs = [_msg(
        FINAUD,
        assunto='Re: DLO - 30.06.2026',
        corpo='Prezados, segue em continuidade a apuração.',
        destinatarios='alecsandro@finaudtec.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


def test_regressao_so_imagens_nao_e_arquivo_entregavel():
    """Regressão §8.6: forward com só imagens inline não é sub-caso 1a → Aguardando Cliente."""
    msgs = [_msg(
        SUPORTE,
        corpo=_FORWARD_A_PARA_CLIENTE,
        destinatarios='suporte@finaud.com.br',
        nomes_anexos=['image001.png', 'image002.gif'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Cliente'


# ── §8.8 — cliente encaminhou extrato (ENC: ou EXTRATO no assunto) ────────────

def test_enc_prefix_texto_vazio_aguarda_finaud():
    """§8.8: cliente envia ENC: com texto vazio → Finaud precisa processar."""
    msgs = [_msg(
        CLIENTE,
        assunto='ENC: EXTRATOS COMPROMISSADAS/CUSTODIA (BANVOX) 12/08/2026',
        corpo='',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'ncaminhou' in motivo


def test_fwd_prefix_texto_curto_aguarda_finaud():
    """§8.8: cliente envia FWD: com texto só cortesia → Finaud precisa processar."""
    msgs = [_msg(
        CLIENTE,
        assunto='Fwd: extrato do dia',
        corpo='Atenciosamente',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'ncaminhou' in motivo


def test_extrato_no_assunto_texto_curto_aguarda_finaud():
    """§8.8: cliente envia EXTRATO no assunto (sem ENC:) com texto curto → Aguardando Finaud."""
    msgs = [_msg(
        CLIENTE,
        assunto='TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.07.29',
        corpo='Segue banvox',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'ncaminhou' in motivo


def test_extrato_no_assunto_texto_real_aguarda_finaud():
    """§8.8: cliente com EXTRATO no assunto + texto real → Aguardando Finaud (pergunta real)."""
    msgs = [_msg(
        CLIENTE,
        assunto='TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.07.29',
        corpo='Bom dia, há um valor divergente na linha 3. Podem verificar?',
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


def test_regressao_cliente_confirma_sem_enc_sem_extrato():
    """Regressão §8.8: cliente confirma com texto só cortesia, assunto normal → Concluída."""
    msgs = [_msg(
        CLIENTE,
        assunto='Re: DLO - 30.06.2026',
        corpo='Obrigado, recebemos.',
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# ── §8.9 — Finaud envia arquivo + pergunta real → Aguardando Cliente ──────────

def test_finaud_arquivo_com_pergunta_real_aguarda_cliente():
    """§8.9: Finaud envia arquivo + faz pergunta real → Aguardando Cliente."""
    msgs = [_msg(
        FINAUD,
        corpo='Prezado Jorge, boa tarde.\r\nVocê tem acesso ao Risk S4 e S5?',
        nomes_anexos=['image001.png', 'relatorio.pdf'],
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'
    assert 'aguarda resposta' in motivo


def test_finaud_arquivo_com_multiplas_perguntas_aguarda_cliente():
    """§8.9: Finaud envia arquivo + múltiplas perguntas reais → Aguardando Cliente."""
    msgs = [_msg(
        FINAUD,
        corpo='O aumento de capital foi feito em qual data?\nFoi feito com $ dos sócios?\nO BC já autorizou?',
        nomes_anexos=['dados.zip'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Cliente'


def test_finaud_arquivo_com_instrucao_sem_pergunta_aguarda_cliente():
    """§8.9: Finaud envia arquivo + instrução com pergunta → Aguardando Cliente."""
    msgs = [_msg(
        FINAUD,
        corpo='Alguma posição...? O relatório de DRL está pendente no BC.',
        nomes_anexos=['image001.png', 'DRL.zip'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Cliente'


def test_finaud_arquivo_tudo_bem_sozinho_concluida():
    """§8.9: Finaud entrega arquivo + só 'Tudo bem?' (saudação) → Concluída."""
    msgs = [_msg(
        FINAUD,
        corpo='Segue em anexo o DDR do dia.\r\nTudo bem?',
        nomes_anexos=['21040668_2011_20260814_I_1.zip'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_finaud_arquivo_ola_tudo_bem_concluida():
    """§8.9: 'Olá, tudo bem?' é saudação — não é pergunta de ação → Concluída."""
    msgs = [_msg(
        FINAUD,
        corpo='Olá, Erivelto, tudo bem?\r\nSegue em anexo as projeções conforme solicitado.',
        nomes_anexos=['projecoes.pdf'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_finaud_arquivo_url_com_interrogacao_concluida():
    """§8.9: URL com '?' na assinatura não conta como pergunta real → Concluída."""
    msgs = [_msg(
        FINAUD,
        corpo='Segue em anexo.\r\n\r\n<https://api.whatsapp.com/send?phone=551137222277>',
        nomes_anexos=['arquivo.zip'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_finaud_arquivo_xml_header_concluida():
    """§8.9: Cabeçalho <?xml...?> não conta como pergunta real → Concluída."""
    msgs = [_msg(
        FINAUD,
        corpo='<?xml version="1.0" encoding="UTF-8"?>\r\nSegue em anexo o arquivo.',
        nomes_anexos=['remessa.zip'],
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_regressao_finaud_arquivo_sem_pergunta_concluida():
    """Regressão §8.9: Finaud envia arquivo sem pergunta → Concluída (sem mudança)."""
    msgs = [_msg(FINAUD, corpo='Segue em anexo conforme solicitado.', nomes_anexos=['arquivo.zip'])]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


# ── §8.10 — Reação do Teams → Concluída ──────────────────────────────────────

def test_reacao_teams_heart_concluida():
    """§8.10: cliente reage com ❤️ a mensagem da Finaud → Concluída."""
    corpo = '[heart]         Jacilaine das Neves Lima reacted to your message:\r\nFrom: Sarah Sá <suporte@finaud.com.br>\r\nSegue o DRM do dia.'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída'
    assert 'reação' in motivo.lower() or 'Teams' in motivo


def test_reacao_teams_like_concluida():
    """§8.10: cliente reage com 👍 a mensagem da Finaud → Concluída."""
    corpo = '[like]  Paulo Henrique Barbosa Silveira reacted to your message:\r\nFrom: Sarah Sá <suporte@finaud.com.br>'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_reacao_teams_via_suporte_concluida():
    """§8.10: reação via suporte@ (remetente = cliente via suporte) → Concluída."""
    corpo = '[heart]         Jacilaine das Neves Lima reacted to your message:'
    msgs = [_msg(
        "'Jacilaine das Neves Lima' via Suporte <suporte@finaud.com.br>",
        corpo=corpo,
        reply_to='jacilaine@planner.com.br',
    )]
    assert bt._determinar_status(msgs)[0] == 'Concluída'


def test_regressao_cliente_escreveu_sem_reacao_aguarda_finaud():
    """Regressão §8.10: cliente escreve texto normal sem reação → Aguardando Finaud."""
    msgs = [_msg(CLIENTE, corpo='Bom dia, preciso do arquivo atualizado.')]
    assert bt._determinar_status(msgs)[0] == 'Aguardando Finaud'


# ── Snapshots de contadores ───────────────────────────────────────────────────

def test_snapshot_banco_vazio(monkeypatch, tmp_path):
    """Banco vazio → snapshot vazio → ler_ultimo_snapshot devolve {}."""
    banco_tmp = str(tmp_path / 'test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()
    bt.salvar_snapshot()
    assert bt.ler_ultimo_snapshot() == {}


def test_snapshot_grava_e_le(monkeypatch, tmp_path):
    """Após salvar threads, salvar_snapshot grava contagens corretas."""
    import json
    banco_tmp = str(tmp_path / 'test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()

    # Insere 2 threads manualmente: 1 AF, 1 CO na categoria DDR_2011
    def _inserir(thread_id, status):
        import sqlite3
        conn = sqlite3.connect(banco_tmp)
        conn.execute(
            "INSERT INTO threads (thread_id, assunto, destino, categoria, status_workflow) "
            "VALUES (?, 'Teste', 'principal', 'DDR_2011', ?)",
            (thread_id, status)
        )
        conn.commit(); conn.close()

    _inserir('t1', 'Aguardando Finaud')
    _inserir('t2', 'Concluída')

    bt.salvar_snapshot()
    snap = bt.ler_ultimo_snapshot()

    assert 'DDR_2011' in snap
    assert snap['DDR_2011']['af'] == 1
    assert snap['DDR_2011']['ac'] == 0
    assert snap['DDR_2011']['co'] == 1


def test_snapshot_sobrescreve_anterior(monkeypatch, tmp_path):
    """Segunda chamada a salvar_snapshot substitui a primeira — sem acumulação."""
    import sqlite3
    banco_tmp = str(tmp_path / 'test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()

    conn = sqlite3.connect(banco_tmp)
    conn.execute(
        "INSERT INTO threads (thread_id, assunto, destino, categoria, status_workflow) "
        "VALUES ('t1', 'X', 'principal', 'DRM_2060', 'Aguardando Finaud')"
    )
    conn.commit(); conn.close()

    bt.salvar_snapshot()
    bt.salvar_snapshot()  # segunda chamada — não deve duplicar

    snap = bt.ler_ultimo_snapshot()
    assert snap['DRM_2060']['af'] == 1  # apenas 1, não 2
