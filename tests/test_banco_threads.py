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


def test_status_transmitido_sem_mencao_bacen():
    """§8.3: 'Boa tarde!\n\nTransmitido os DLO e DLI' sem dizer 'no BACEN' → Concluída.
    Reproduz caso real 'DLO | DLI - Referente a MAI.2026' (20/08/2026): saudação precede 'Transmitido'.
    """
    corpo = 'Boa tarde!\n\nTransmitido os DLO e DLI referente a MAIO de 2026:\n\n[image: screenshot.png]'
    msgs = [
        _msg(FINAUD, corpo='Prezados, seguem remessas DLO e DLI de maio/2026 para transmissão ao BC.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_status_transmitido_sem_bacen_com_pergunta_nao_encerra():
    """§8.3: 'Transmitido' + pergunta → não deve encerrar (cliente tem dúvida)."""
    msgs = [_msg(CLIENTE, corpo='Transmitido, mas apareceu uma crítica. O que devo fazer?')]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_segue_sozinho_aguarda_finaud():
    """§8.3: cliente manda só 'Segue' (entregando arquivo) → Aguardando Finaud.
    Reproduz caso DDR DIA 28/07 — Paulo Henrique envia só 'Segue' + assinatura (20/08/2026).
    """
    corpo = 'Segue\r\n\r\n\r\nAtt\r\n\r\nPaulo Henrique\r\nPlanner SCD – Financeiro/SPB'
    msgs = [
        _msg(FINAUD, corpo='Prezado Paulo, segue remessa DDR para transmissão ao BC.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status} | {motivo}'


def test_status_segue_relacao_aguarda_finaud():
    """§8.3: 'Boa tarde! Segue relação.' → Aguardando Finaud.
    Reproduz caso 'Informações para DDRs de 29/07 a 05/08/2026' (20/08/2026).
    """
    corpo = 'Boa tarde!\r\n\r\nSegue relação.\r\n\r\nAtenciosamente,\r\nLeonardo Almeida\r\nTesouraria'
    msgs = [
        _msg(FINAUD, corpo='Prezado Leonardo, favor encaminhar a relação dos DDRs.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status} | {motivo}'


def test_status_segue_em_anexo_aguarda_finaud():
    """§8.3: 'Segue em anexo.' → Aguardando Finaud."""
    corpo = 'Segue em anexo.\r\n\r\nAtenciosamente,\r\nGabriel Santos'
    msgs = [
        _msg(FINAUD, corpo='Prezado Gabriel, favor encaminhar o COS4010.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status} | {motivo}'


def test_status_obrigado_deu_certo_conclui():
    """§8.3: 'Deu certo, obrigada!' → Concluída (não deve ser afetado pela regra do segue)."""
    corpo = 'Prezados, boa tarde,\r\n\r\ndeu certo, obrigada!\r\n\r\nAtenciosamente,\r\nTalita Santana'
    msgs = [
        _msg(FINAUD, corpo='Prezada Talita, efetuamos o cadastro do novo fundo.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_status_boa_tarde_att_aguarda_finaud():
    """§8.8c: 'Boa Tarde + Att' sem palavra de confirmação → Aguardando Finaud.
    Reproduz padrão Paulo Henrique (Planner): CADOC 4111 enviado com saudação + assinatura (20/08/2026).
    """
    corpo = 'Boa Tarde\r\n\r\n\r\nAtt\r\n\r\nPaulo Henrique\r\nPlanner SCD – Financeiro/SPB'
    msgs = [
        _msg(FINAUD, corpo='Prezado Paulo, favor encaminhar o CADOC 4111 do dia 16/07.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status} | {motivo}'


def test_status_bom_dia_att_aguarda_finaud():
    """§8.8c: 'Bom dia + Att' sem confirmação → Aguardando Finaud."""
    corpo = 'Bom dia\r\n\r\n\r\nAtt\r\n\r\nPaulo Henrique\r\nPlanner SCD – Financeiro/SPB'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status} | {motivo}'


def test_status_texto_vazio_cliente_aguarda_finaud():
    """§8.8c: texto completamente vazio de cliente → Aguardando Finaud (só anexo enviado)."""
    msgs = [_msg(CLIENTE, corpo='')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status} | {motivo}'


def test_status_muito_obrigado_conclui():
    """§8.8c: 'Muito obrigado!' → Concluída (palavra de confirmação explícita presente)."""
    corpo = 'Monica, bom dia.\r\n\r\nMuito obrigado!\r\n\r\nAtenciosamente,\r\nPedro'
    msgs = [
        _msg(FINAUD, corpo='Prezado Pedro, segue o relatório DLO conforme solicitado.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_finaud_solicito_aguarda_cliente():
    """§8.X: Finaud usa 'solicito' pedindo algo ao cliente → Aguardando Cliente.
    Reproduz caso 'ENC: BANCO CENTRAL - INCONSISTENCIA DRM' (20/08/2026).
    """
    corpo = (
        'Olá Luiza, bom dia.\r\n\r\nTudo bem?\r\n\r\n'
        'Para eu conseguir verificar a crítica apontada, vou precisar dos '
        "COSIFs de Junho (4010 e 4016).\r\nAproveitando, solicito também os "
        'balanços e a planilha LEC.\r\n\r\nAtenciosamente,\r\nMonica Macedo'
    )
    msgs = [
        _msg(CLIENTE, corpo='Prezados, segue a comunicação de inconsistência do DRM.'),
        _msg(FINAUD, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente', f'Esperado Aguardando Cliente, got: {status} | {motivo}'


def test_finaud_vou_precisar_aguarda_cliente():
    """§8.X: Finaud usa 'vou precisar' pedindo documentos → Aguardando Cliente."""
    corpo = (
        'Boa tarde, João.\r\n\r\n'
        'Vou precisar dos extratos de junho para verificar a divergência.\r\n\r\n'
        'Atenciosamente,\r\nAndrea Inacio'
    )
    msgs = [
        _msg(CLIENTE, corpo='Prezados, encontrei uma divergência no DRM.'),
        _msg(FINAUD, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente', f'Esperado Aguardando Cliente, got: {status} | {motivo}'


def test_finaud_recebemos_disponivel_conclui():
    """§8.X: Finaud informa que geração está disponível → Concluída (não é pedido).
    Reproduz caso 'Erro ao gerar o arquivo 4111' (20/08/2026).
    """
    corpo = (
        'Boa tarde.\r\n\r\nTudo bem?\r\n\r\n'
        'Recebemos a informação de que o cálculo e a geração do relatório '
        'já está disponível.\r\nQualquer dúvida retorne.\r\nÀ disposição.\r\n\r\n'
        'Atenciosamente,\r\nMonica Macedo'
    )
    msgs = [
        _msg(CLIENTE, corpo='Bom dia, tive um erro ao gerar o arquivo 4111.'),
        _msg(FINAUD, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


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


def test_status_cliente_obrigado_nos_ajudou():
    """§8.3: cliente agradece com 'nos ajudou muito' → Concluída.
    Reproduz caso 'Erro em classificação FPR no DLO' (Oslo, 20/08/2026).
    """
    corpo = 'Boa tarde, Obrigado Andrea, nos ajudou muito. Bom final de semana.'
    msgs = [
        _msg(FINAUD, corpo='Prezados, segue análise do erro de classificação FPR.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_status_cliente_muito_obrigado_ajudou():
    """§8.3: cliente agradece com 'muito obrigado me ajudou muito' → Concluída.
    Reproduz caso 'TRADERS - RSA 2030 - 06/2026 - PENDENTE' (20/08/2026).
    """
    corpo = 'Bom dia, Andrea, tudo bem ?\n\nmuito obrigado me ajudou muito.'
    msgs = [
        _msg(CLIENTE, corpo='Bom dia, Andrea, por favor poderia me ajudar?'),
        _msg(FINAUD, corpo='Prezado Marcos, bom dia. Caso a instituição não possua...'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


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


def test_cliente_obrigado_com_assinatura_via_suporte_concludes():
    """§8.3: cliente responde 'obrigado' via suporte@ com assinatura longa → Concluída.
    Reproduz o bug TRINUS: assinatura (nome+cargo+telefone+URLs) confundia _so_cortesia.
    """
    corpo = (
        'Boa tarde,\r\n\r\n'
        'Obrigado pelo retorno.\r\n\r\n\r\n'
        '​Atenciosamente,​​\r\n\r\n'
        '[https://assinatura.trinusco.com.br/logo.png]<https://trinus.co/>\r\n\r\n'
        'Luiz Eduardo Coelho Filho\r\n\r\n'
        'Risco\r\n\r\n'
        '+55 62 3773-1500\r\n\r\n'
        '[https://assinatura.trinusco.com.br/ico-ig.png]<https://www.instagram.com/somostrinus/>'
    )
    msgs = [_msg(
        'Luiz via Suporte <suporte@finaud.com.br>',
        corpo=corpo,
        assunto='RE: TRINUS - ENVIAR COS 4010 E 4016 DE JUN.2026',
        reply_to='Luiz <luiz@trinusco.com.br>',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_conteudo_real_mais_assinatura_nao_e_cortesia():
    """§8.3: e-mail com conteúdo real + assinatura não é tratado como cortesia → Aguardando Finaud."""
    corpo = (
        'Preciso que vocês verifiquem o arquivo enviado.\r\n\r\n'
        'Atenciosamente,\r\n'
        'João Silva\r\n'
        '+55 11 9999-0000\r\n'
        'https://empresa.com.br'
    )
    msgs = [_msg(
        CLIENTE,
        corpo=corpo,
        assunto='Re: Verificação de arquivo',
    )]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


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


def test_snapshot_acumula_historico(monkeypatch, tmp_path):
    """Duas chamadas a salvar_snapshot acumulam — ler_ultimo_snapshot devolve só o mais recente."""
    import sqlite3, time
    banco_tmp = str(tmp_path / 'test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()

    conn = sqlite3.connect(banco_tmp)
    conn.execute(
        "INSERT INTO threads (thread_id, assunto, destino, categoria, status_workflow) "
        "VALUES ('t1', 'X', 'principal', 'DRM_2060', 'Aguardando Finaud')"
    )
    conn.commit(); conn.close()

    # Força timestamps distintos via monkeypatch
    ts_seq = iter(['2026-08-20 10:00:00', '2026-08-20 10:05:00'])
    monkeypatch.setattr(bt, '_agora', lambda: next(ts_seq))

    bt.salvar_snapshot()
    bt.salvar_snapshot()

    # ler_ultimo_snapshot devolve só o snapshot mais recente (af=1, não duplicado)
    snap = bt.ler_ultimo_snapshot()
    assert snap['DRM_2060']['af'] == 1

    # O banco deve conter 2 momentos distintos acumulados
    with bt._conectar() as c:
        n_momentos = c.execute('SELECT COUNT(DISTINCT data_hora) FROM snapshots').fetchone()[0]
    assert n_momentos == 2, f'Esperado 2 momentos acumulados, mas havia {n_momentos}'


# ── Testes: registrar_coleta / ler_log_coletas ────────────────────────────────

def test_registrar_coleta_e_ler(monkeypatch, tmp_path):
    """registrar_coleta() grava; ler_log_coletas() retorna mais recente primeiro."""
    banco_tmp = str(tmp_path / 'test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()

    bt.registrar_coleta('incremental', 5, 0, 12.3, 'concluida', '')
    bt.registrar_coleta('historica', 100, 2, 120.5, 'concluida', '')

    logs = bt.ler_log_coletas()
    assert len(logs) == 2
    assert logs[0]['tipo'] == 'historica'     # mais recente primeiro (id DESC)
    assert logs[0]['threads_proc'] == 100
    assert logs[1]['tipo'] == 'incremental'
    assert logs[1]['threads_proc'] == 5


def test_registrar_coleta_erro(monkeypatch, tmp_path):
    """coleta com erro salva mensagem e status 'erro'."""
    banco_tmp = str(tmp_path / 'test.db')
    monkeypatch.setattr(bt, 'BANCO', banco_tmp)
    bt.criar_banco()

    bt.registrar_coleta('incremental', 0, 0, 1.0, 'erro', 'Falha de autenticação')

    logs = bt.ler_log_coletas()
    assert len(logs) == 1
    assert logs[0]['status'] == 'erro'
    assert 'Falha de autenticação' in logs[0]['mensagem']


# ── Fix B — "Arquivos transmitidos." → Concluída (20/08/2026) ─────────────────

def test_status_arquivos_transmitidos_conclui():
    """§8.3: 'Arquivos transmitidos.' no corpo (não no início de linha) → Concluída.
    Caso real: RES: Documentos retificados junho (20/08/2026).
    """
    corpo = 'Bom dia,\r\n\r\nArquivos transmitidos.\r\n\r\nObrigada.\r\n\r\nAtt,\r\n\r\nLuiza Milet.'
    msgs = [
        _msg(FINAUD, corpo='Prezada Luiza, segue o arquivo para transmissão.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_status_arquivos_transmitidos_com_pergunta_nao_encerra():
    """§8.3: 'Arquivos transmitidos?' com interrogação → não encerra (veto §8.3)."""
    corpo = 'Bom dia,\r\n\r\nArquivos transmitidos?\r\n\r\nAtt,'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


# ── Fix C — frase de entrega quebrada por \r\n não impedia Concluída (20/08/2026) ──

def test_status_cid_e_bloco_assinatura_sem_signoff_nao_bloqueia_obrigado():
    """Fix E: [cid:...] + bloco de assinatura sem sign-off explícito não deve impedir Concluída.
    Caso real: 'Re: Arquivo COS' — cliente respondeu 'Obrigado, Andrea' + 12 linhas em branco
    + [cid:logo] + 'Enio Feyh / Compliance / +55...' sem 'Atenciosamente' → ficava AF (20/08/2026).
    """
    corpo = (
        'Obrigado,  Andrea\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n'
        '[cid:a5345f28-54af-4093-b6f4-cae3c514ba1c]\r\n\r\n\r\n\r\n'
        'Enio Feyh\r\nCompliance\r\n+55 51 3303.3460\r\nexecutivecambio.com.br'
    )
    msgs = [
        _msg(FINAUD, corpo='Prezados, segue o resultado quantitativo.', nomes_anexos=['RQ_06_2026.xlsx']),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_status_mencao_outlook_nao_bloqueia_obrigado():
    """Fix D: '@Monica Macedo<mailto:...>' no texto não deve impedir detecção de 'Muito obrigado'.
    Caso real: '4010 Trinus' — cliente agradeceu com @mention do Outlook → ficava AF (20/08/2026).
    """
    corpo = (
        'Boa tarde,\r\n\r\n'
        'Muito obrigado @Monica Macedo<mailto:monica.macedo@finaud.com.br>.\r\n\r\n'
        '​Atenciosamente,​​\r\n\r\nLuiz Eduardo Coelho Filho\r\nRisco'
    )
    msgs = [
        _msg(FINAUD, corpo='Conforme solicitado, segue os arquivos de substituição.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_status_segue_em_anexo_quebrado_por_linha_conclui():
    """Fix C: 'segue em\\r\\nanexo' (linha quebrada) → Concluída.
    Caso real: TRINUS DTVM - Subst. DDR e DRM (ABR e MAR/2026).
    """
    corpo = (
        'Prezado Luís, boa tarde.\r\n\r\n'
        'Devidos as alterações do ultimo COS4010/4060 encaminhado para nós, segue em\r\n'
        'anexo os arquivos substituídos DDR e DRM referente a Abr2026, para serem\r\n'
        'encaminhados ao BACEN.\r\n\r\nAgradeço e permaneço a disposição.'
    )
    msgs = [_msg(FINAUD, corpo=corpo, nomes_anexos=['02276653_2011_20260430_S_4.zip'])]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída (Fix C), got: {status} | {motivo}'


# ── Fix F — confirmação curta + assinatura corporativa sem sign-off (20/08/2026) ──

def test_status_deacordo_com_assinatura_corporativa_conclui():
    """Fix F: 'De acordo' + assinatura corporativa sem sign-off → Concluída.
    Caso real: OP. SELIC ACTIVTRADES — 'De acordo\\r\\n\\r\\nEduardo Galasini\\r\\nFinance...'
    ficava AF porque _so_cortesia() falhava na assinatura (sem sign-off, <4 linhas em branco).
    """
    corpo = (
        'De acordo\r\n\r\n'
        'Eduardo Galasini\r\nFinance\r\n\r\n'
        'ActivTrades CCTVM\r\nRua Ângelo La Porta, 53 - Ático 1 e 2\r\n'
        'Florianópolis/SC - 88020-600\r\nBrasil\r\n'
        'egalasini@activtrades.com<mailto:egalasini@activtrades.com>\r\n'
        'www.activtrades.com.br<http://www.activtrades.com.br/>\r\n'
        'Ouvidoria: 0800-228-4827\r\n\r\n'
        'ActivTrades CCTVM is authorized and regulated in Brazil by BACEN/CVM\r\n'
        'Check here our Legal Disclaimer<https://activtrades.com.br/go/governanca/>'
    )
    msgs = [
        _msg(FINAUD, corpo='Segue em anexo o comprovante da operação SELIC.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída (Fix F), got: {status} | {motivo}'


def test_status_fixf_fp_conteudo_apos_deacordo_com_pergunta_nao_conclui():
    """Fix F — falso positivo: 'De acordo. [parágrafo] Pode reenviar?' → Aguardando Finaud.
    O '?' no texto todo veta o Fix F.
    """
    corpo = 'De acordo.\r\n\r\nPor favor, pode reenviar o arquivo atualizado?'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixf_fp_primeiro_para_longo_nao_e_cortesia():
    """Fix F — falso positivo: primeiro parágrafo longo com 'de acordo' não deve concluir.
    'De acordo com o pedido, precisamos da planilha atualizada.' → _so_cortesia = False.
    """
    corpo = 'De acordo com o pedido, precisamos da planilha atualizada.\r\n\r\nAtenciosamente,\r\nJoão Silva\r\nEmpresa X'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixf_fp_segue_antes_da_confirmacao_nao_conclui():
    """Fix F — regressão: 'Segue em anexo.' no início → linha 508 bloqueia antes do Fix F."""
    corpo = 'Segue em anexo o arquivo.\r\n\r\nObrigado.\r\n\r\nJoão Silva\r\nEmpresa X'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


# ── Fix G — cliente confirma e promete agir por conta própria (21/08/2026) ──

_CLIENTE_VIA = "'Murillo Oliveira | Saygo' via Suporte <suporte@finaud.com.br>"
_CLIENTE_REPLY = 'murillo.oliveira@saygogroup.com.br'


def test_status_cliente_obrigado_e_acao_propria_conclui():
    """Fix G: cliente agradece E promete agir por conta própria (sem pedir nada) → Concluída.
    Caso real: 'Muito obrigado, realizaremos o procedimento e enviaremos a alteração do report ao BCB.'
    ficava AF porque o texto longo impedia _so_cortesia() de retornar True.
    """
    corpo = 'Muito obrigado, realizaremos o procedimento e enviaremos a alteração do report ao BCB.\r\n\r\nAbs!'
    msgs = [
        _msg(FINAUD, corpo='Prezado, corrija assim: X.', destinatarios=_CLIENTE_REPLY),
        _msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída (Fix G), got: {status} | {motivo}'


def test_status_fixg_fp_com_pergunta_nao_conclui():
    """Fix G — falso positivo: obrigado + ação própria + pergunta → AF (? veta)."""
    corpo = 'Obrigado, realizaremos. Mas poderia verificar se está correto?'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixg_fp_segue_antes_nao_conclui():
    """Fix G — falso positivo: 'Segue' antes de 'obrigado' → AF (§8.8b bloqueia)."""
    corpo = 'Segue o arquivo. Obrigado, enviaremos a confirmação ao BCB.'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
