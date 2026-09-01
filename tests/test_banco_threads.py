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
    cc: str = '',
) -> dict:
    return {
        'remetente': remetente,
        'corpo_texto': corpo,
        'assunto': assunto,
        'nomes_anexos': nomes_anexos or [],
        'destinatarios': destinatarios,
        'reply_to': reply_to,
        'cc': cc,
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


def test_extrair_nao_descarta_conteudo_apos_cabecalho_outlook():
    # Outlook coloca "De: ..." no INÍCIO do corpo antes do texto real.
    # A função não deve parar aí — deve pular o cabeçalho e retornar o texto.
    corpo = (
        '\n\nDe: Risco Externo <risco@trustee.com>\n'
        'Enviada em: sexta-feira, 31 de julho de 2026 15:40\n'
        'Para: suporte@finaud.com.br\n'
        'Assunto: RES: DLO\n\n'
        'Miguel, segue planilha preenchida.'
    )
    resultado = bt._extrair_texto_novo(corpo)
    assert 'segue planilha preenchida' in resultado


def test_extrair_separador_apos_conteudo_real_ainda_corta():
    # Comportamento antigo preservado: "De:" após texto real = histórico citado, deve cortar.
    corpo = 'Obrigado pela orientação.\n\nDe: Finaud <suporte@finaud.com.br>\nTexto antigo'
    resultado = bt._extrair_texto_novo(corpo)
    assert 'Obrigado' in resultado
    assert 'Texto antigo' not in resultado


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


def test_status_entrega_apos_4_linhas_em_branco_com_sign_off():
    """§8.8c fix: cumprimento + 4 linhas em branco + texto de entrega + sign-off → não é saudação.
    Caso real Brazabank (RE: DRM 05.2026, 03/07/2026): _so_cortesia() cortava em 4 linhas em
    branco e descartava 'Enviado o DDR de 29/05 ajustado e DRM referente a 05/2026'.
    Fix: fallback das 4 linhas só se aplica quando não há sign-off explícito.
    """
    corpo = (
        'Prezados, boa tarde!\n'
        '\n'
        '\n'
        '\n'
        'Enviado o DDR de 29/05 ajustado e DRM referente a 05/2026 de substituição:\n'
        '\n'
        '[cid:38f6c55a-19af-43a4-863b-5049d5e54c38]\n'
        '\n'
        ' ATT\n'
        '\n'
        'Talitha Gonzalez\n'
        'Analista SR Risk\n'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert 'saudação' not in motivo.lower(), (
        f'Esperado motivo sem "saudação" (entrega real no corpo), got: {status} | {motivo}'
    )


def test_status_cumprimento_4_linhas_sem_sign_off_e_apenas_assinatura():
    """§8.8c: fallback das 4 linhas ainda funciona quando não há sign-off explícito.
    Garante que o fix não quebra o caso original: cumprimento + 4+ linhas em branco
    + bloco de assinatura sem 'Att'/'Atenciosamente' → ainda classifica como saudação.
    """
    corpo = (
        'Prezados, boa tarde!\n'
        '\n'
        '\n'
        '\n'
        'Paulo Henrique\n'
        'Planner SCD – Financeiro/SPB\n'
        'Avenida Brigadeiro Faria Lima, 3.900\n'
        'Telefone: (11) 2172-2504\n'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert 'sem conteúdo' in motivo.lower(), (
        f'Esperado motivo com "sem conteúdo" (sem sign-off, só assinatura após 4 linhas), '
        f'got: {status} | {motivo}'
    )


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
    assert 'Finaud concluiu' in motivo


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
    assert 'informações' in motivo


def test_fwd_prefix_texto_curto_aguarda_finaud():
    """§8.8: cliente envia FWD: com texto só cortesia → Finaud precisa processar."""
    msgs = [_msg(
        CLIENTE,
        assunto='Fwd: extrato do dia',
        corpo='Atenciosamente',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'informações' in motivo


def test_extrato_no_assunto_texto_curto_aguarda_finaud():
    """§8.8: cliente envia EXTRATO no assunto (sem ENC:) com texto curto → Aguardando Finaud."""
    msgs = [_msg(
        CLIENTE,
        assunto='TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.07.29',
        corpo='Segue banvox',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'informações' in motivo


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
    assert 'aguarda retorno' in motivo


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
    assert 'agradeceu' in motivo


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


# ── Grupo CADOC 4111 (01/09/2026) ────────────────────────────────────────────

def test_cadoc_conversei_internamente_e_concluida():
    """CADOC grupo: "Conversei internamente e, as próximas planilhas estarão..."
    Cliente consultou equipe e trouxe a resposta → Concluída.
    Reproduz thread 'RE: CADOC 4111 DIA 27/07 - Dúvida SCD' (Planner SCD, 01/09/2026).
    """
    corpo = (
        'Oi Sarah!\r\n\r\n'
        'Usar o valor nessas duas contas:\r\n\r\n'
        'Disponibilidades e Depósitos bancários\r\n\r\n'
        'Conversei internamente e, as próximas planilhas estarão com essas duas contas preenchidas'
    )
    msgs = [_msg(CLIENTE, assunto='RE: CADOC 4111 DIA 27/07 - Dúvida SCD', corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_cadoc_pode_enviar_scd_e_solicitacao():
    """CADOC grupo: "Pode enviar a SCD do jeito que está no relatório" (sem "?")
    Cliente pede à Finaud que envie o arquivo gerado → solicitação.
    Reproduz thread 'CADOC 4111 DIA 17/07 20/07 21/07 E 22/07' (Planner SCD, 01/09/2026).
    """
    corpo = 'Boa Tarde!\r\n\r\nPode enviar a SCD do jeito que está no relatório. Os outros dias também estão zerados'
    msgs = [
        _msg(CLIENTE, corpo='Bom dia!'),
        _msg(CLIENTE, corpo='Oi Sarah! Faltou o anexo do dia 22/07 da SCD'),
        _msg(CLIENTE, assunto='CADOC 4111 DIA 17/07 20/07 21/07 E 22/07', corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert 'solicitação' in motivo, f'Esperado motivo solicitação, got: {motivo}'


def test_cadoc_peco_com_pergunta_e_solicitacao():
    """CADOC grupo: "De quais informações você se refere? ... peço que solicite ao Robson"
    Mensagem tem "?" mas contém "peço" → _PEDIDO_FOLLOW_UP dispara → solicitação.
    Reproduz thread 'RES: 4111 Do dia 16/07/2026 e 17/07/2026' (Banvox, 01/09/2026).
    """
    corpo = (
        'Miguel, bom dia! Espero que esteja bem. '
        'De quais informações você se refere? '
        'Eu mando somente os extratos de compromissada e custódia da Banvox, '
        'e os mesmos já foram enviados dessas respectivas datas. '
        'Caso não seja isso, peço que solicite ao Robson. Desde já agradeço.'
    )
    msgs = [_msg(CLIENTE, assunto='RES: 4111 Do dia 16/07/2026 e 17/07/2026', corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert 'solicitação' in motivo, f'Esperado motivo solicitação, got: {motivo}'


# ── Grupo BANCO CENTRAL aviso (01/09/2026) ───────────────────────────────────

def test_bc_aviso_credenciamento_realizado_e_concluida():
    """BC aviso grupo: "Credenciamento realizado." — cliente confirma fim do processo STA.
    Reproduz thread 'BANCO CENTRAL - AVISO DE ATRASO - CNPJ 38.429.045' (VIS DTVM, 01/09/2026).
    """
    msgs = [
        _msg(CLIENTE, corpo='Monica, bom dia.\r\n\r\nGentileza verificar o aviso de atraso.'),
        _msg(CLIENTE, corpo='Monica, boa tarde.\r\n\r\nPreciso do seu nome completo, data de nascimento e CPF.'),
        _msg(CLIENTE, corpo='Monica, boa tarde.\r\n\r\nSegue seu login: 436880001.MOMACEDO'),
        _msg(CLIENTE, corpo='Monica, bom dia.\r\n\r\nSegue evidência da senha e conta ativa.'),
        _msg(CLIENTE, corpo='Monica,\r\n\r\nCredenciamento realizado.'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_bc_aviso_favor_solucionar_com_pergunta_e_solicitacao():
    """BC aviso grupo: "Será que esquecemos do 4011?. Favor solucionar com prioridade."
    "?" bloqueia _PEDIDO_IMPLICITO, mas "favor" em _PEDIDO_FOLLOW_UP dispara → solicitação.
    Reproduz thread 'Fw: BANCO CENTRAL - AVISO - CNPJ 50.286.774' (CV DTVM, 01/09/2026).
    """
    corpo = 'Bom dia .\r\n\r\nSerá que esquecemos do 4011 ?.\r\n\r\nFavor solucionar com prioridade .'
    msgs = [_msg(CLIENTE, assunto='Fw: BANCO CENTRAL - AVISO DE ATRASO EM REMESSA DE DOCUMENTO', corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert 'solicitação' in motivo, f'Esperado solicitação, got: {motivo}'


def test_bc_grato_pela_colaboracao_e_concluida():
    """BC aviso grupo: "Grato mais uma vez pela colaboração e atenção" = agradecimento formal → Concluída.
    Reproduz thread 'Re: Arquivos para Bacen' (Kinel Corretora, 01/09/2026).
    """
    msgs = [
        _msg(FINAUD, corpo='Tenho disponibilidade hoje às 11 hrs ou às 15 hrs. Retorne por gentileza.'),
        _msg(CLIENTE, corpo='Hoje as 11hrs, te chamo\r\n\r\nGrato mais uma vez pela colaboração e atenção'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_regressao_favor_em_pedido_implicito_sem_pergunta():
    """Regressão: "favor" sem "?" já era solicitação via _PEDIDO_IMPLICITO — não deve regredir."""
    msgs = [_msg(CLIENTE, corpo='Favor enviar o arquivo atualizado.')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'solicitação' in motivo


# ── Grupo ENC: outros (01/09/2026) ───────────────────────────────────────────

def test_enc_risk_driver_arquivo_ja_foi_aceito_concluida():
    """ENC outros grupo: "o arquivo já foi aceito... seguiremos assim para este mês"
    _ACEITACAO_BACEN agora cobre "já foi aceito" → Concluída via Fix I.
    Reproduz thread 'ENC: Risk Driver - ID CORRETORA' (Denver Contábil, 01/09/2026).
    """
    corpo = (
        'Prezados, bom dia!\r\n\r\n'
        'Veliquei e realmente está -8, não entendi como o Bacen aceitou, vou verificar aqui. '
        'Mas o arquivo já foi aceito, se for só um alerta e não afetar os informes que usamos '
        'no sistema, seguiremos assim para este mês.'
    )
    msgs = [
        _msg(CLIENTE, corpo='Prezados, boa tarde!\r\n\r\nRecebi este e-mail ao realizar o 2061, qual seria o motivo do alerta?'),
        _msg(FINAUD, corpo='Prezado Jean, bom dia.\r\n\r\nAcredito que o sistema apresentou a mensagem porque não localizou a conta cosif.'),
        _msg(CLIENTE, assunto='ENC: Risk Driver - ID CORRETORA - CONTA(S) COSIF(S) NÃO CADASTRADA(S)', corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'Esperado Concluída, got: {status} | {motivo}'


def test_enc_freex_zip_so_assinatura_e_entrega():
    """ENC outros grupo: forward com zip real + assinatura com ícones ([Logo], [Instagram] etc.)
    §8.8-ENC-ARQUIVO: ENC: + arquivo não-imagem → entrega independente de _so_cortesia().
    Reproduz thread 'ENC: FREEX CORRETORA - Balancete e arquivos 05-2026' (01/09/2026).
    """
    corpo = (
        '[Logo Freex]\r\n\r\n'
        '[Instagram]<https://www.instagram.com/freexcambio/>\r\n'
        '[LinkedIn]<https://www.linkedin.com/company/freex-cambio/>\r\n'
        'patricia antero\r\nSupervisora Financeira\r\n[??]\r\n+55 11 5108-5138'
    )
    msgs = [_msg(
        CLIENTE,
        assunto='ENC: FREEX CORRETORA - Balancete e arquivos 05-2026',
        corpo=corpo,
        nomes_anexos=['image001.png', 'image002.png', 'COS4010_2026-05-I.zip'],
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert 'informações' in motivo, f'Esperado motivo entrega, got: {motivo}'


def test_regressao_enc_sem_arquivo_nao_imagem_nao_e_enc_arquivo():
    """Regressão §8.8-ENC-ARQUIVO: ENC: sem arquivo não-imagem não dispara a nova regra."""
    msgs = [_msg(
        CLIENTE,
        assunto='ENC: relatório pendente',
        corpo='Bom dia, segue conforme solicitado.',
        nomes_anexos=['foto.png', 'logo.jpg'],
    )]
    # Sem zip/xlsx, não deve ser pego pela nova regra — cai no fluxo normal
    status, _ = bt._determinar_status(msgs)
    # "segue" → deve ser entrega de todas formas (§8.8b), mas via outro caminho
    assert status == 'Aguardando Finaud'


# ── UNVERIFIED SENDER outros — grupo 01/09/2026 ──────────────────────────────

# ── Cobranças: "atualização?", "conseguiu?", "pode confirmar/verificar?" ─────

def test_cobranca_alguma_atualizacao_e_solicitacao():
    """Thread A: 'Alguma atualização sobre a regularização?' → solicitação."""
    msgs = [
        _msg(CLIENTE, corpo='Alguma inconsistência no DRM 2060.'),
        _msg(CLIENTE, corpo='Srs,\r\nAlguma atualização sobre a regularização?\r\n\r\nRodrigo Nelson'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', f'Esperado solicitação, got: {motivo}'


def test_cobranca_conseguiu_verificar_singular_e_solicitacao():
    """Thread B: 'O time conseguiu verificar essa pendência?' — singular → solicitação."""
    msgs = [
        _msg(CLIENTE, corpo='Sarah, bom dia!\r\n\r\nO time conseguiu verificar essa pendência?\r\n\r\nAt.te,'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', f'Esperado solicitação, got: {motivo}'


def test_cobranca_temos_atualizacoes_e_solicitacao():
    """Thread C: 'temos atualizações?' → solicitação."""
    msgs = [_msg(
        CLIENTE,
        corpo='Bom dia!!\r\nTudo bem?\r\n\r\nQuanto a este ponto, temos atualizações?\r\n\r\nAgradeço e aguardo.',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', f'Esperado solicitação, got: {motivo}'


def test_cobranca_pode_confirmar_e_solicitacao():
    """Thread D: 'Envio efetuado. Pode confirmar?' → solicitação."""
    msgs = [_msg(
        CLIENTE,
        corpo='Boa tarde, Monica.\r\n\r\nEnvio efetuado.\r\n\r\nPode confirmar?\r\n\r\nAtt., Ivan Cândido',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', f'Esperado solicitação, got: {motivo}'


def test_cobranca_pode_verificar_e_solicitacao():
    """Thread E: 'Está constando como atrasado. pode verificar?' → solicitação."""
    msgs = [_msg(
        CLIENTE,
        corpo='Bom dia,\r\n\r\nEstá constando como atrasado.\r\n\r\n@monica.macedo@finaud.com.br pode verificar?',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', f'Esperado solicitação, got: {motivo}'


def test_regressao_conseguiram_plural_ainda_funciona():
    """Regressão: 'conseguiram' plural ainda dispara após mudança para regex combinado."""
    msgs = [_msg(CLIENTE, corpo='Conseguiram regularizar o arquivo? Aguardo retorno.')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', f'Esperado solicitação, got: {motivo}'


def test_unverified_gentileza_com_pergunta_e_solicitacao():
    """Thread A: 'Por gentileza, poderia retornar?' com '?' → solicitação.
    'gentileza' agora está em _PEDIDO_FOLLOW_UP, que dispara mesmo com '?'.
    """
    msgs = [
        _msg(FINAUD, corpo='Prezada Luiza, bom dia. Segue o acesso.'),
        _msg(CLIENTE, corpo='Boa tarde, Por gentileza, poderia retornar?'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', (
        f'Esperado motivo de solicitação, got: {motivo}'
    )


def test_unverified_usuario_inexistente_e_caixa_preta():
    """Thread B: 'não consegui desbloquear... usuário é inexistente' → caixa preta genuína.
    Conteúdo técnico específico; nenhuma regra automática cobre.
    """
    msgs = [_msg(
        CLIENTE,
        corpo=(
            'Boa tarde, Perdão, eu não consegui desbloquear. '
            'Eu tenho salvo esse usuário: lmilet@GLOBALEXCHANGE, '
            'mas está informando que o usuário é inexistente.'
        ),
    )]
    _, motivo = bt._determinar_status(msgs)
    assert motivo == 'Cliente escreveu — aguarda resposta da Finaud', (
        f'Esperado caixa preta, got: {motivo}'
    )


# ── Usuário bloqueado / acesso — grupo 01/09/2026 ────────────────────────────

def test_acesso_negado_seria_possivel_e_solicitacao():
    """Thread C: 'seria possível desbloquear?' com '?' → solicitação.
    'seria possível' em _PEDIDO_FOLLOW_UP, que dispara mesmo com '?'.
    """
    msgs = [_msg(
        CLIENTE,
        corpo=(
            'Boa tarde, minha conta msapaio@nixfin se encontra como acesso negado.\n\n'
            'Atualmente utilizados esta conta em dois computadores, seria possível desbloquear?\n\nAtt'
        ),
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado Aguardando Finaud, got: {status}'
    assert motivo != 'Cliente escreveu — aguarda resposta da Finaud', (
        f'Esperado motivo de solicitação, got: {motivo}'
    )


def test_acesso_trinus_credencial_com_pergunta_e_caixa_preta():
    """Thread A: entrega de credencial + pergunta aberta → genuína (conteúdo misto)."""
    msgs = [
        _msg(CLIENTE, corpo='@Arleson poderia auxiliar? @Monica seria STA da DTVM ou SCD?'),
        _msg(
            CLIENTE,
            corpo=(
                'Monica Macedo, segue o link com a credencial BC da DTVM, abra o link com seu email.\n'
                'https://share.1password.com/s#exemplo\n\n'
                'Outro ponto, você tinha acesso ao BC da SCD?\n\nObrigado.'
            ),
        ),
    ]
    _, motivo = bt._determinar_status(msgs)
    assert motivo == 'Cliente escreveu — aguarda resposta da Finaud', (
        f'Esperado caixa preta, got: {motivo}'
    )


def test_acesso_senha_nova_sem_pergunta_e_caixa_preta():
    """Thread B: cliente informa nova senha do arquivo C6 sem fazer pergunta → genuína."""
    msgs = [
        _msg(FINAUD, corpo='Podem verificar? Houve alguma mudança na senha?'),
        _msg(
            CLIENTE,
            corpo=(
                'Andrea, Boa tarde\n\n'
                'O banco alterou a senha agora são os 4 primeiros dígitos 4432, '
                'desculpe-nos por não termos avisado antes, juntamento com o envio dos extratos.\n\nSds'
            ),
        ),
    ]
    _, motivo = bt._determinar_status(msgs)
    assert motivo == 'Cliente escreveu — aguarda resposta da Finaud', (
        f'Esperado caixa preta, got: {motivo}'
    )


def test_unverified_indice_basileia_duvida_e_caixa_preta():
    """Thread C: dúvida técnica sobre cálculo do Índice de Basileia → caixa preta genuína."""
    msgs = [_msg(
        CLIENTE,
        corpo=(
            'Rodrigo, boa tarde. '
            'Certo que isso não é por nenhum erro sistêmico ou de cálculo? '
            'Na provisão que realizamos anteriormente não está próximo do que temos em sistema.'
        ),
    )]
    _, motivo = bt._determinar_status(msgs)
    assert motivo == 'Cliente escreveu — aguarda resposta da Finaud', (
        f'Esperado caixa preta, got: {motivo}'
    )


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


# ── Fix H: cliente agradece sem pergunta e sem documento → Concluída ──────────

def test_status_fixh_wilson_lima_vou_fazer():
    """Fix H — caso-gatilho: 'Muito obrigado, vou fazer de acordo.' → Concluída."""
    corpo = (
        'Boa noite Andrea\n\n'
        'Muito obrigado, vou fazer de acordo com a orientação.\n\n\n'
        'Abraço e fique com Deus.'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixh_wilson_lima_com_citacao_asterisco():
    """Fix H + SEP_HISTORICO — *De:* (formato Gmail) é tratado como separador de histórico.

    O corpo real de Wilson Lima incluía '*De: Andrea Inacio...' seguido do histórico
    de Andrea que continha 'segue'. Sem o fix, §8.8b disparava 'AF'. Com o fix,
    _extrair_texto_novo corta no *De:* e Fix H detecta Concluída.
    """
    corpo = (
        'Boa noite Andrea\n\n'
        'Muito obrigado, vou fazer de acordo com a orientação.\n\n\n'
        'Abraço e fique com Deus.\n\n'
        '*De:* Andrea Inacio <andrea.inacio@finaud.com.br>\n'
        '*Enviada em:* sexta-feira, 3 de julho de 2026\n'
        'Segue o exemplo abaixo:\n\n'
        '...'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixh_obrigada_pelo_retorno():
    """Fix H — agradecimento simples sem ação → Concluída."""
    corpo = 'Obrigada pelo retorno.'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixh_conseguindo_gerar_arquivo():
    """Fix H — cliente informa que resolveu + obrigado, sem perguntas → Concluída."""
    corpo = 'Obrigado, já estou conseguindo gerar o arquivo.'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixh_fp_com_pergunta():
    """Fix H — falso positivo: obrigado + pergunta → AF (? veta)."""
    corpo = 'Obrigado! Mas tenho uma dúvida: quando chega o arquivo?'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixh_talita_obrigada_era_erro_bc():
    """Fix H — 'Obrigada, era erro do próprio Bc.' com ? somente em URL de assinatura → Concluída.

    O corpo real da Talita tinha '?' numa URL do bloco de assinatura — isso bloqueava
    Fix H com a checagem '?' not in texto_novo. Com o fix, somente URLs são removidas
    antes de checar o ?, então o ? da assinatura não veta mais.
    """
    corpo = (
        'Boa tarde @Andrea Inacio<mailto:andrea.inacio@finaud.com.br>,\n\n'
        'Obrigada,\n'
        'era erro do próprio Bc.\n\n'
        'Atenciosamente,\n\n'
        'Talita Santana\n'
        'Tesouraria\n'
        'Tel: (11) 2626-9780\n'
        'https://www.empresa.com.br/portal?token=abc123\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixh_fp_pergunta_real_nao_vira_concluida():
    """Fix H — pergunta real (não URL) ainda veta Fix H após o fix."""
    corpo = (
        'Obrigada!\n\n'
        'Mas quando vocês conseguem corrigir isso?\n\n'
        'Atenciosamente,\nTalita\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixh_fp_cvpar_peco_que_verifique():
    """Fix H — 'Peço que verifique... Obrigada.' com 'Tudo bem?' → AF.

    CVPAR encerrou com 'Obrigada' mas o conteúdo é um pedido ativo à Finaud.
    'Tudo bem?' está no texto e NÃO é URL, portanto não é removido — mantém ? e
    bloqueia Fix H corretamente.
    """
    corpo = (
        'Monica, bom dia.\n'
        'Tudo bem?\n\n'
        'Não recebemos nenhum apontamento no CRD.\n\n'
        'Peço por gentileza, que verifique as informações e realize o reprocessamento.\n\n'
        'Obrigada.\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixh_fp_segue_mid_sentence():
    """Fix H — falso positivo: obrigado + segue (entrega de doc) fora do início de linha → AF."""
    corpo = 'Obrigado, segue a planilha conforme solicitado.'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


# ── Fix I — aceite do BACEN ───────────────────────────────────────────────────

def test_status_fixi_robson_protocolo_aceito():
    """Fix I — 'Segue protocolo de arquivo aceito' → Concluída.

    Caso Robson/Banvox: cliente envia protocolo de aceite do BACEN.
    Deve rodar antes de §8.8b ('Segue' no início de linha → AF).
    Michel confirmou em 23/08/2026: se o protocolo foi aceito pelo BACEN, o caso fechou.
    """
    corpo = (
        'Miguel,\n\n'
        'Segue protocolo de arquivo aceito do COS4111 de 30/06/2026 da Banvox DTVM.\n\n'
        'Atenciosamente,\n\n'
        'Robson S. Neves\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixi_arquivo_aceito():
    """Fix I — 'arquivo aceito' no corpo → Concluída."""
    corpo = 'Bom dia, o arquivo foi aceito pelo BACEN. Atenciosamente, João.'
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixi_fp_protocolo_aceito_com_pergunta():
    """Fix I — falso positivo: 'protocolo aceito' + pergunta → AF (não é encerramento)."""
    corpo = (
        'Miguel,\n\n'
        'Segue protocolo de arquivo aceito do COS4111.\n\n'
        'Poderia confirmar o recebimento?\n\n'
        'Atenciosamente,\n\n'
        'Robson S. Neves\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


# ── Fix H — strip de ?? informal ─────────────────────────────────────────────

def test_status_fixh_obrigado_com_dupla_interrogacao():
    """Fix H — 'Obrigado pelo aviso ??' → Concluída.

    Caso Paulo/CADOC 4111 27/07: '??' é ênfase informal (emoji garbado), não pergunta.
    Michel confirmou em 23/08/2026: cliente agradeceu pelo aviso, assunto encerrado.
    """
    corpo = (
        'Oi Sarah! Bom dia\r\n\r\n'
        'Obrigado pelo aviso ??\r\n\r\n'
        'Att\r\n\r\n'
        'Paulo Henrique\r\n'
        'Planner SCD\r\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixh_fp_dupla_interrogacao_com_pedido():
    """Fix H — falso positivo: '??' com pedido explícito → AF.

    'Tudo bem?' (simples) ainda bloqueia Fix H mesmo depois do strip de '??'.
    """
    corpo = (
        'Monica, bom dia.\n'
        'Tudo bem?\n\n'
        'Poderia verificar o arquivo ??\n\n'
        'Obrigada.\n'
    )
    msgs = [_msg(_CLIENTE_VIA, corpo=corpo, reply_to=_CLIENTE_REPLY)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


# ── Fix J — Finaud pede algo ao cliente após cortesia ────────────────────────

def test_status_fixj_solicitamos_enviar():
    """Fix J — Finaud: 'Obrigado. Solicitamos enviar o COS4016...' → AC.

    Caso DLO_2061 Re: COS 4010 junho/2026: Finaud recebe arquivo do cliente
    mas pede o COS4016 também. Sistema estava retornando AF por confundir
    'Obrigado' inicial com cortesia pura. Michel confirmou em 23/08/2026: AC.
    """
    corpo = (
        'Prezado Silvio, boa tarde.\n\n'
        'Obrigado.\n'
        'Por se tratar de mês de fechamento de semestre, solicitamos enviar também o'
        ' COS4016 06/2026.\n\n'
        'Grata.\n\n'
        'Andrea Inacio\nCoordenadora de Suporte\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixj_orientamos_que():
    """Fix J — Finaud: 'Tudo bem? Orientamos que seja realizada uma conferência...' → AC.

    Caso SUPORTE Re: COLOP UNICAD PL MINIMO: Finaud repassa orientação e pede
    que cliente confira informações no sistema. Sistema retornava AF por confundir
    'Tudo bem?' com cortesia pura. Michel confirmou em 23/08/2026: AC.
    """
    corpo = (
        'Prezada Marcia, boa tarde.\n\n'
        'Tudo bem?\n\n'
        'Segue transcrito abaixo a orientação do nosso gestor:\n\n'
        'Em relação à comunicação do Banco Central sobre a IN BCB nº 754/2026,'
        ' orientamos que seja realizada uma conferência das informações cadastradas'
        ' no módulo "Operações" do Unicad.\n\n'
        'Atenciosamente,\nEquipe de Suporte Finaud\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixj_verifique():
    """Fix J — Finaud: 'Certo, verifique com a contabilidade se...' → AC.

    Caso DDR_2011 Re: DÚVIDA DDR - 49820 obrigações ME: Finaud pede ao cliente
    que verifique internamente os dados contábeis. Sistema retornava AF por
    confundir 'Certo' inicial com cortesia pura. Michel confirmou 23/08/2026: AC.
    """
    corpo = (
        'Prezado Isaac, boa tarde.\n\n'
        'Certo, verifique com a contabilidade se a composição do registro do saldo'
        ' do cosif 4.9.8.20.00.00-7 corresponde ao registro do mesmo saldo na'
        ' 3.2.8.20.00.00-7.\n\n'
        'Atenciosamente,\nMonica\nFinaud\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixj_fp_verifiquei():
    """Fix J — falso positivo: 'verifiquei' (passado) não aciona 'verifique ' (imperativo).

    'Certo, verifiquei os dados e está correto.' — Finaud confirmando, não pedindo
    ao cliente — _eh_cortesia_finaud deve continuar retornando True. O espaço em
    'verifique ' garante que 'verifiquei' (letra 'i' ≠ espaço) não seja capturado.
    Com 1 msg de Finaud e cortesia pura → 'Aguardando Finaud' (acusou recibo).
    Nota: usa 'Prezado' (singular) — '_SAUDACAO_RE' filtra singular/a, não 's'.
    """
    corpo = (
        'Prezado Isaac, boa tarde.\n\n'
        'Certo, verifiquei os dados e está tudo correto.\n\n'
        'Atenciosamente,\nMonica\nFinaud\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    # Finaud só confirmou (não pediu nada) — deve ser AF (acusou recibo), não AC
    assert status == 'Aguardando Finaud'


# ── Fix K — _SAUDACAO_RE filtra plural (Prezados/Prezadas) ───────────────────

def test_status_fixk_prezados_cortesia_pura():
    """Fix K — 'Prezados, boa tarde. Recebido. Obrigada.' → AF, não AC.

    _SAUDACAO_RE só filtrava 'Prezado'/'Prezada' (singular). Com 'Prezados'
    (plural) não filtrado, o texto 'prezados, boa tarde. recebido. obrigada.'
    não começava com cortesia → _eh_cortesia_finaud retornava False → AC (errado).
    Correção: adicionar 's?' ao padrão → 'prezad[ao]s?'.
    Impacto nos dados atuais: 0 threads (Finaud usa Prezados em e-mails com
    conteúdo substantivo, não em acuses de recibo puros).
    """
    corpo = (
        'Prezados, boa tarde.\n\n'
        'Recebido. Obrigada!\n\n'
        'Atenciosamente,\nAndrea Inacio\nCoordenadora de Suporte\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixl_estarei_colocando_remessas():
    """Fix L — 'Agradeço pelo envio. Logo, estarei colocando as remessas em dia.' → AF.

    Finaud agradeceu o envio do cliente e prometeu agir (colocar remessas em dia).
    Sem o fix, o texto não iniciava com palavra de cortesia reconhecida ('agradeço'
    não estava na lista) e não havia frase de pedido → _eh_cortesia_finaud retornava
    False → AC (errado). Fix: adicionar 'estarei colocando' a
    _FRASES_AGUARDANDO_FINAUD_ATIVA → Finaud prometeu retornar → AF.
    """
    corpo = (
        'Bruno,\n\n'
        'Agradeço pelo envio.\n'
        'Logo, estarei colocando as remessas em dia.\n\n'
        'Att.\n\nMônica Macedo\nAnalista de Suporte Jr.\nSuporte\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixm_qualquer_duvida_fico_disposicao_conclui():
    """Fix M — Finaud responde pergunta com arquivo + 'Qualquer dúvida fico a disposição' → Concluída.

    Quando Finaud envia mensagem com anexo 'noname' e texto informacional encerrado com
    'Qualquer dúvida fico a disposição', o sistema marcava AC 'sem linguagem de entrega'
    porque não havia frase de entrega explícita. Fix: adicionar a frase a _FRASES_ENTREGA.
    Diferente de 'Qualquer dúvida retorne' (usado também em e-mails com pedido ao cliente).
    """
    corpo = (
        'Prezado Paulo, boa noite.\n\n'
        'Recebemos a informação interna de que o usuário e a senha para autenticação\n'
        'na WebApi são os mesmos para acessar o Risk Driver.\n\n'
        'Qualquer dúvida fico a disposição.\n\n'
        'Andrea Inacio\nCoordenadora de Suporte\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo, nomes_anexos=['noname', 'image.png'])]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


# ── Fix N — forward com texto_novo vazio: verificar corpo completo (23/08/2026) ──

def test_status_fixn_forward_vazio_frase_conclusiva_no_corpo():
    """Fix N — §8.6 forward (para_finaud=True): texto_novo vazio + frase conclusiva no corpo → Concluída.

    Monte Bravo | Cadastro de Ações e Opções | 2026-07-15: Finaud encaminhou
    internamente um forward cujo "Para:" é o cliente externo (ops@montebravo.com.br) e
    a resposta dentro do forward dizia 'As opções de ação já foram cadastradas'.
    _extrair_texto_novo strip tudo a partir do '----------', então texto_novo ficava vazio.
    Sem Fix N, o código caía em AC 'sem sinal claro'.
    Fix: quando texto_novo.strip() está vazio, checar _FRASES_CONCLUSIVAS_FINAUD
    no corpo completo → Concluída.
    """
    sep = '---------- Forwarded message ---------\r\n'
    corpo = (
        sep
        + 'De: Bruno Finaud <bruno@finaud.com.br>\r\n'
        + 'Para: ops@montebravo.com.br\r\n\r\n'
        + 'As opções de ação já foram cadastradas. '
        + 'Desde já agradeço e permaneço à disposição.\r\n'
    )
    msgs = [_msg(
        SUPORTE,
        corpo=corpo,
        destinatarios='suporte@finaud.com.br',
    )]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixn_fp_forward_vazio_sem_frase_conclusiva():
    """Fix N — falso positivo: texto_novo vazio mas corpo sem frase conclusiva → AC (padrão).

    Garante que o Fix N não altera o comportamento padrão quando o forward não
    contém nenhuma frase conclusiva reconhecida.
    """
    sep = '---------- Forwarded message ---------\r\n'
    corpo = (
        sep
        + 'De: Bruno Finaud <bruno@finaud.com.br>\r\n'
        + 'Para: ops@montebravo.com.br\r\n\r\n'
        + 'Segue o pedido de cadastro das opções de ação.\r\n'
    )
    msgs = [_msg(
        SUPORTE,
        corpo=corpo,
        destinatarios='suporte@finaud.com.br',
    )]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


# ── Fix O — _eh_forward_para_cliente exige De: seja Finaud no Format A (23/08/2026) ──

def test_status_fixo_forward_de_externo_nao_ativa_secao_86():
    """Fix O — §8.6 Format A: Se De: no forward é externo (ex: BC), não ativa §8.6 → AF (cenário 3).

    Re: 1ª REITERAÇÃO - COMUNICAÇÃO DE VARIAÇÃO RELEVANTE NO DDR: Andrea (Finaud) escreve
    a Rodrigo (Finaud) com corpo contendo uma notificação do BC que tinha um "Para:" externo
    no forward header. Sem Fix O, _eh_forward_para_cliente disparava com o Para: do BC
    (externo), mandando para §8.6 AC. Com Fix O, De: é BC (externo, não Finaud) → não ativa
    §8.6 → cai em Cenário 3 (e-mail interno) → AF.
    """
    sep = '---------- Forwarded message ---------\r\n'
    corpo = (
        'Rodrigo e Monica, boa tarde.\n\n'
        'Conforme a comunicação do BC, há variação cambial acima da média.\n\n'
        + sep
        + 'De: Banco Central <noreply@bacen.gov.br>\r\n'
        + 'Para: andrea.inacio@finaud.com.br\r\n\r\n'
        + 'Prezados, variação cambial detectada em 23/06/2026.\r\n'
    )
    msgs = [_msg(
        FINAUD,
        corpo=corpo,
        destinatarios='rodrigo.tiberio@finaud.com.br',
    )]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'Esperado AF (Fix O), got: {status} | {motivo}'


def test_status_fixp_permanecemos_esclarecer_conclui():
    """Fix P — 'Permanecemos à disposição para esclarecer qualquer ponto adicional' → Concluída.

    CV INVEST DLO 05/2026: Rodrigo respondeu todas as dúvidas do cliente sobre
    diferenças entre projeções e fechou com oferta opcional de reunião.
    Sem Fix P, nenhuma frase conclusiva era detectada → AC (errado).
    Fix: adicionar forma longa de 'permanecemos à disposição para esclarecer'
    a _FRASES_CONCLUSIVAS_FINAUD.
    """
    corpo = (
        'Prezados,\n\n'
        'Analisamos os pontos levantados e gostaríamos de compartilhar nossas considerações.\n\n'
        'O capital social de R$ 8.350.000,00 decorre da premissa adotada para a simulação.\n\n'
        'Permanecemos à disposição para esclarecer qualquer ponto adicional.\n\n'
        'Atenciosamente,\nRodrigo Tiberio\nGerente de Riscos\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixp_permanecemos_eventuais_esclarecimentos_conclui():
    """Fix P — 'Permanecemos à disposição para eventuais esclarecimentos' → Concluída."""
    corpo = (
        'Prezados,\n\n'
        'Segue a projeção de capital conforme cenários solicitados.\n\n'
        'Permanecemos à disposição para eventuais esclarecimentos.\n\n'
        'Atenciosamente,\nRodrigo Tiberio\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo, nomes_anexos=['projecao.pdf'])]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixp_fp_permanecemos_curto_com_pedido_nao_conclui():
    """Fix P — falso positivo: 'permanecemos à disposição' curto + pedido explícito → AC.

    Guru CTVM: Finaud pede que o cliente envie o 2060 e fecha com 'Permanecemos à disposição'.
    A forma CURTA sem 'para esclarecer/esclarecimentos' não está em _FRASES_CONCLUSIVAS_FINAUD.
    """
    corpo = (
        'Prezada Andrea,\n\n'
        'Por último, poderiam enviar o 2060 antes de protocolarem, por favor?\n\n'
        'Permanecemos à disposição.\n\n'
        'Andrea Inacio\nCoordenadora de Suporte\n'
    )
    msgs = [_msg(FINAUD, corpo=corpo)]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixo_forward_de_finaud_ainda_ativa_secao_86():
    """Fix O — regressão: Format A com De: Finaud E Para: externo continua ativando §8.6.

    Garante que o Fix O não quebra o caso correto: quando Finaud realmente encaminhou
    para o cliente (De: Finaud, Para: externo) o §8.6 ainda deve ativar.
    Corpo sem frase conclusiva → AC 1b-padrão (Fix N não interfere: texto_novo não é vazio).
    """
    sep = '---------- Forwarded message ---------\r\n'
    # Corpo com texto ANTES do forward (texto_novo não-vazio) e sem frase conclusiva
    corpo = (
        'Fyi — encaminhei ao cliente.\r\n\r\n'
        + sep
        + 'De: Andrea Inacio <andrea.inacio@finaud.com.br>\r\n'
        + 'Para: ops@montebravo.com.br\r\n\r\n'
        + 'Prezada, por favor verifique o status do arquivo.\r\n'
    )
    msgs = [_msg(
        SUPORTE,
        corpo=corpo,
        destinatarios='suporte@finaud.com.br',
    )]
    # §8.6 ativa (De: Finaud, Para: externo) + sem frase conclusiva → AC (1b-padrão)
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


# ── Fix Q — To: vazio → fallback para CC ─────────────────────────────────────

def test_status_fixq_to_vazio_cc_so_finaud_cenario3_af():
    """Fix Q — To: vazio, CC: só Finaud, sem forward no corpo → Cenário 3 → AF.

    Monica envia notificação interna (To: vazio, CC: suporte@finaud.com.br).
    Sem encaminhamento para cliente no corpo → Cenário 3 → AF.
    """
    corpo = (
        'Fyi — enviei confirmação ao cliente.\n\n'
        'Mônica Macedo\nAnalista de Suporte Jr.\n'
    )
    msgs = [_msg(
        FINAUD,
        corpo=corpo,
        assunto='Fwd: SSG - ENVIAR POSIÇÃO - 4111',
        destinatarios='',
        cc='suporte <suporte@finaud.com.br>',
    )]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixq_to_vazio_cc_externo_nao_muda_caminho():
    """Fix Q — To: vazio, CC: endereço externo → para_finaud=False → Finaud→Cliente.

    Quando o CC tem endereço externo, o fallback não trata como interno.
    Sem frase conclusiva e assunto sem RES: → AC.
    """
    corpo = 'Verificamos a situação e aguardamos seu retorno.\n\nAndrea Inacio\n'
    msgs = [_msg(
        FINAUD,
        corpo=corpo,
        assunto='Acompanhamento do caso',
        destinatarios='',
        cc='cliente@externo.com.br',
    )]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixq_to_preenchido_cc_ignorado():
    """Fix Q — regressão: quando To: está preenchido, CC não afeta para_finaud.

    Garante que o fallback só age quando To: está vazio — comportamento normal inalterado.
    To: externo + CC: Finaud → para_finaud=False (To: tem precedência) → AC.
    """
    corpo = 'Verificamos a situação e aguardamos seu retorno.\n\nAndrea Inacio\n'
    msgs = [_msg(
        FINAUD,
        corpo=corpo,
        assunto='Acompanhamento do caso',
        destinatarios='cliente@externo.com.br',
        cc='suporte@finaud.com.br',
    )]
    # To: tem externo → para_finaud=False → Finaud→Cliente → AC
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixr_cliente_vai_retornar_ac():
    """Fix R — cliente diz 'Vamos analisar e retornamos' → Aguardando Cliente.

    Mesmo com 'obrigada' (que ativaria Fix H → Concluída), a promessa do cliente
    de retornar indica que a ação pendente é do cliente → AC, não Concluída.
    """
    corpo = 'Boa tarde, Rodrigo.\n\nVamos analisar e retornamos.\n\nObrigada pelo envio.\n\nJuliana\n'
    msgs = [
        _msg(FINAUD, corpo='Seguem em anexo as projeções de capital.', assunto='Projeção de Capital'),
        _msg('juliana@agkcorretora.com.br', corpo=corpo, assunto='Re: Projeção de Capital'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'
    assert 'prometeu retornar' in motivo


def test_status_fixr_retornarei_ac():
    """Fix R — cliente diz 'retornarei amanhã' → Aguardando Cliente."""
    corpo = 'Muito obrigado, retornarei amanhã com mais detalhes.\n\nAtt, Carlos\n'
    msgs = [
        _msg(FINAUD, corpo='Segue o relatório conforme solicitado.', assunto='Relatório'),
        _msg('carlos@cliente.com.br', corpo=corpo, assunto='Re: Relatório'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixr_nao_afeta_agradecimento_simples():
    """Fix R — regressão: agradecimento simples sem promessa de retorno → Fix H (Concluída)."""
    corpo = 'Muito obrigado! Tudo certo.\n\nAtt, Carlos\n'
    msgs = [
        _msg(FINAUD, corpo='Segue o relatório conforme solicitado.', assunto='Relatório'),
        _msg('carlos@cliente.com.br', corpo=corpo, assunto='Re: Relatório'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixs_no_aguardo_finaud_ac():
    """Fix S — Finaud diz 'No aguardo' → Aguardando Cliente.

    "Certo, podemos agendar... No aguardo." começa com 'Certo' (palavra de cortesia),
    mas 'No aguardo' indica que a Finaud está esperando resposta — deve ser AC, não Concluída.
    """
    corpo = (
        'Certo, podemos agendar para o dia 21/07 às 10 hrs ou as 11 hrs.\n\n'
        'No aguardo.\nGrata.\n\nAndrea Inacio\nCoordenadora de Suporte\n'
    )
    msgs = [
        _msg('henrique@cliente.com.br', corpo='Gostaria de agendar uma visita.', assunto='Re: Visita Finaud'),
        _msg(FINAUD, corpo=corpo, assunto='Re: Visita Finaud'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'


def test_status_fixs_nao_afeta_cortesia_sem_aguardo():
    """Fix S — regressão: 'Certo, à disposição.' sem 'no aguardo' → Concluída (cortesia pura)."""
    corpo = 'Certo, qualquer dúvida estou à disposição.\n\nAndrea Inacio\n'
    msgs = [
        _msg('henrique@cliente.com.br', corpo='Obrigado pelo atendimento.', assunto='Re: Suporte'),
        _msg(FINAUD, corpo=corpo, assunto='Re: Suporte'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


def test_status_fixt_peco_que_cliente_bloqueia_fixh_af():
    """Fix T — cliente diz 'Peço que inclua... Obrigado.' → Aguardando Finaud.

    'Obrigado' ativaria Fix H → Concluída, mas 'Peço que' é pedido explícito do cliente.
    Fix T adiciona 'peço ' ao _PEDIDO_IMPLICITO → Fix H bloqueado → AF.
    """
    corpo = 'Peço que inclua esta aplicação no DRM – 06-2026.\n\nObrigado.\n\nIvan Cândido\n'
    msgs = [
        _msg(FINAUD, corpo='Segue remessa DRM conforme solicitado.', assunto='DRM 2060'),
        _msg('ivan@colunadtvm.com.br', corpo=corpo, assunto='DRM 2060'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixt_nao_afeta_obrigado_simples():
    """Fix T — regressão: 'Obrigado.' sem pedido → Fix H ainda funciona → Concluída."""
    corpo = 'Obrigado pelo envio!\n\nIvan Cândido\n'
    msgs = [
        _msg(FINAUD, corpo='Segue remessa DRM conforme solicitado.', assunto='DRM 2060'),
        _msg('ivan@colunadtvm.com.br', corpo=corpo, assunto='DRM 2060'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


# ── Fix U: "Favor + verbo" do cliente bloqueia Fix H → AF ────────────────────

def test_status_fixu_favor_considerar_bloqueia_fixh_af():
    """Fix U — 'Favor considerar estes documentos. Obrigado.' → AF.

    O 'Obrigado' ativaria o Fix H → Concluída, mas 'Favor + verbo'
    indica pedido de ação ao Finaud — deve bloquear Fix H e retornar AF.
    Caso real: Jair Bonetti (Western Union), posição de câmbio 02/07/2026.
    """
    corpo = (
        'Bom dia, pessoal!\n\n'
        'Favor considerar estes documentos para a posição do dia 02/07/2026.\n\n'
        'Obrigado.\n\nJair Bonetti\n'
    )
    msgs = [_msg('jair@wu.com', corpo=corpo, assunto='Posição de Câmbio 02/07')]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixu_favor_desconsiderar_bloqueia_fixh_af():
    """Fix U — 'Favor, desconsiderar e-mail anterior e considerar este.' → AF.

    Cliente pede ao Finaud para usar dados corrigidos — pedido de ação sem resposta.
    Caso real: Fernando de Sales Santos (Travelex), RD MES 07-2026.
    """
    corpo = (
        'Prezados (as),\n'
        'Favor, desconsiderar e-mail anterior e considerar este.\n\n'
        '31/07/2026\nSALDOS BANCOS\nMOEDA\nUSD 197,97\n'
    )
    msgs = [_msg('fernando@travelex.com', corpo=corpo, assunto='RD MES 07-2026 - DESCONSIDERAR')]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'


def test_status_fixu_nao_afeta_obrigado_sem_favor():
    """Fix U — regressão: 'Obrigado.' sem 'Favor' → Fix H ainda funciona → Concluída."""
    corpo = 'Obrigado pela atenção!\n\nCarlos\n'
    msgs = [
        _msg(FINAUD, corpo='Segue o DDR 2011 conforme solicitado.', assunto='DDR 2011'),
        _msg('carlos@cliente.com', corpo=corpo, assunto='Re: DDR 2011'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


# ── Fix V: "e retorno" do cliente → Aguardando Cliente (AC) ──────────────────

def test_status_fixv_e_retorno_cliente_prometeu_voltar_ac():
    """Fix V — 'vou confirmar com o extrato amanhã e retorno' → Aguardando Cliente.

    'ok' ativaria Fix H → Concluída, mas o cliente prometeu voltar
    com confirmação — ação pendente do cliente → AC.
    Caso real: Celso Julich Jr. (Unicred), fluxo de caixa ZIIN 08/07/2026.
    """
    corpo = (
        'Boa noite!\n\n'
        'A principio está ok, vou confirmar com o extrato amanha e retorno.\n\n'
        'Celso Julich Junior\nUnicred do Brasil\n'
    )
    msgs = [
        _msg('celso@unicred.com', corpo='Bom dia! Segue até o dia 08/07', assunto='FLUXO DE CAIXA - ZIIN'),
        _msg('celso@unicred.com', corpo=corpo, assunto='FLUXO DE CAIXA - ZIIN'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'
    assert 'prometeu retornar' in motivo


# ── Passo B — 4 motivos novos ─────────────────────────────────────────────────

def test_passo_b_solicita_extrato():
    """Passo B: Finaud usa 'vou precisar' sem anexo → AC 'Finaud solicitou extrato ou planilha'."""
    msgs = [
        _msg('cliente@empresa.com', corpo='Bom dia, precisamos de ajuda.', assunto='Balanços'),
        _msg(FINAUD, corpo='Bom dia! Vou precisar dos balanços de 2024 para dar continuidade.', assunto='Re: Balanços'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'
    assert 'extrato ou planilha' in motivo


def test_passo_b_orientacao_tecnica():
    """Passo B: Finaud usa 'orientamos que' → AC 'Finaud deu orientação técnica'."""
    msgs = [
        _msg('cliente@empresa.com', corpo='Como procedo com o COSIF?', assunto='COSIF'),
        _msg(FINAUD, corpo='Orientamos que acesse o portal e faça o upload do arquivo conforme o manual.', assunto='Re: COSIF'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'
    assert 'orientação técnica' in motivo


def test_passo_b_proposta_reuniao():
    """Passo B: Finaud menciona 'reunião' sem anexo → AC 'Finaud propôs reunião ou ligação'."""
    msgs = [
        _msg('cliente@empresa.com', corpo='Precisamos conversar sobre o relatório.', assunto='Relatório'),
        _msg(FINAUD, corpo='Podemos fazer uma reunião amanhã às 14h para alinharmos?', assunto='Re: Relatório'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Cliente'
    assert 'reunião ou ligação' in motivo


def test_passo_b_cliente_fez_solicitacao():
    """Passo B: cliente usa 'precisamos' sem '?' → AF 'Cliente fez solicitação'."""
    msgs = [
        _msg('cliente@empresa.com', corpo='Precisamos do relatório até sexta-feira.', assunto='Relatório'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'solicitação' in motivo


def test_passo_b_cliente_pergunta_nao_ativa_solicitacao():
    """Passo B — regressão: cliente usa 'precisamos?' com '?' → não ativa 'Cliente fez solicitação'."""
    msgs = [
        _msg('cliente@empresa.com', corpo='Precisamos mesmo enviar isso agora?', assunto='Dúvida'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'solicitação' not in motivo


# ── _determinar_status — _PEDIDO_FOLLOW_UP (Decisão 12 — 01/09/2026) ─────────

def test_status_algum_retorno_e_solicitacao():
    """'Algum retorno quanto a este caso?' → follow-up = solicitação mesmo com '?'."""
    msgs = [
        _msg(FINAUD, corpo='Monica, segue o arquivo DDR (2011) da ZIIN.'),
        _msg(CLIENTE, corpo='Pessoal, boa tarde! Tudo bem?\r\n\r\nAlgum retorno quanto a este caso?\r\n\r\nAtt.,\r\nLuis Paulo'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente fez solicitação — aguarda ação da Finaud'

def test_status_conseguiram_regularizar_e_solicitacao():
    """'Conseguiram regularizar a situação?' → cobrança sobre ação da Finaud = solicitação."""
    msgs = [
        _msg(FINAUD, corpo='Segue evidência de aceite do DDR no STA.'),
        _msg(CLIENTE, corpo='Olá, tudo bem?\r\n\r\nVocês conseguiram regularizar a situação do documento em atraso?\r\n\r\nAtenciosamente,\r\nGuilherme Marin'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente fez solicitação — aguarda ação da Finaud'

def test_status_precisamos_com_pergunta_nao_e_follow_up():
    """'Precisamos mesmo enviar isso agora?' (dúvida retórica com ?) → NÃO é solicitação."""
    msgs = [_msg(CLIENTE, corpo='Precisamos mesmo enviar isso agora?')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'solicitação' not in motivo


# ── Truncagem de aviso de confidencialidade ───────────────────────────────────

_DISCLAIMER = (
    '\n\nEste e-mail e seus anexos destinam-se exclusivamente ao(s) destinatário(s) '
    'acima. Se você recebeu este e-mail equivocadamente, por favor, nos informe '
    'imediatamente e destrua o original.'
)


def test_disclaimer_nao_dispara_favor():
    """Disclaimer com 'por favor' não deve classificar como 'Cliente fez solicitação'."""
    corpo = 'Venho solicitar o cancelamento dos serviços.' + _DISCLAIMER
    msgs = [_msg('cliente@empresa.com', corpo=corpo, assunto='Distrato')]
    status, motivo = bt._determinar_status(msgs)
    assert 'solicitação' not in motivo


def test_disclaimer_conteudo_real_preservado():
    """'Favor' no conteúdo real (antes do disclaimer) ainda classifica corretamente."""
    corpo = 'Favor encaminhar o extrato até sexta.' + _DISCLAIMER
    msgs = [_msg('cliente@empresa.com', corpo=corpo, assunto='Extrato')]
    status, motivo = bt._determinar_status(msgs)
    assert 'solicitação' in motivo


def test_truncar_no_disclaimer_unitario():
    """_truncar_no_disclaimer corta no marcador e preserva texto anterior."""
    texto = 'Mensagem real aqui.\n\nEste e-mail e seus anexos destinam-se exclusivamente...'
    resultado = bt._truncar_no_disclaimer(texto)
    assert 'Mensagem real aqui.' in resultado
    assert 'destinam-se' not in resultado


def test_truncar_no_disclaimer_sem_disclaimer():
    """_truncar_no_disclaimer devolve texto intacto quando não há disclaimer."""
    texto = 'Mensagem sem aviso algum.'
    assert bt._truncar_no_disclaimer(texto) == texto


def test_status_fixv_nao_afeta_retorno_bacen():
    """Fix V — regressão: 'retorno' como substantivo ('retorno BACEN') → não ativa Fix V."""
    corpo = (
        'Obrigado pela transmissão. O retorno do BACEN foi positivo.\n\nAtt, Ana\n'
    )
    msgs = [
        _msg(FINAUD, corpo='Segue DDR transmitido ao BACEN.', assunto='DDR 2011'),
        _msg('ana@cliente.com', corpo=corpo, assunto='Re: DDR 2011'),
    ]
    status, _ = bt._determinar_status(msgs)
    assert status == 'Concluída'


# ── Novos termos de entrega do cliente (01/09/2026) ───────────────────────────

def test_status_seguem_as_posicoes_aguarda_finaud():
    """'Seguem as posições de TVM's...' → cliente entregando dados → Aguardando Finaud.
    Reproduz caso 'Relatórios de TVM e Dep a Vista' (Western Union / TRUSTEE).
    """
    corpo = (
        'Prezados, bom dia!\r\n\r\n'
        'Seguem as posições de TVM’s e o relatório do Deposito a Vista.\r\n\r\n'
        'Atenciosamente,\r\nJair Bonetti'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_seguem_valores_cadoc_aguarda_finaud():
    """'Seguem valores para geração do CADOC 4111' → entrega → Aguardando Finaud.
    Reproduz caso TRUSTEE DTVM - CADOC 4111 (Robson Soares Neves).
    """
    corpo = (
        'Miguel, boa tarde!\r\n\r\n'
        'Seguem valores para geração do CADOC 4111 ref. 07/08/2026 A 12/08/2026 da TRUSTEE DTVM.\r\n\r\n'
        'Atenciosamente,\r\nRobson'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_anexo_posicoes_aguarda_finaud():
    """'Bom dia! Anexo Posições da Western Union...' → entrega → Aguardando Finaud.
    Reproduz caso Posição de Câmbio corretora (Jair Bonetti, Western Union).
    """
    corpo = (
        'Bom dia, pessoal!\r\n\r\n'
        'Anexo Posições da Western Union Corretora 14/08/2026:\r\n\r\n'
        '- Posição de Câmbio Contábil Change.\r\n'
        '- Balancete de Câmbio Change em PDF e Excel.\r\n\r\n'
        'Att,\r\nJair'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_arquivos_enviados_aguarda_finaud():
    """'Arquivos enviados:' → entrega → Aguardando Finaud."""
    corpo = (
        'Miguel, boa noite!\r\n\r\n'
        'Arquivos enviados:\r\n\r\n'
        'Atenciosamente,\r\nRisco Externo'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_favor_considerar_aguarda_finaud():
    """'Favor considerar os valores abaixo' → entrega de dados → Aguardando Finaud.
    Reproduz caso REMITLY : Movimento (Lidiane Moreira) e BANVOX DTVM (Robson).
    """
    corpo = (
        'Bom dia,\r\n\r\n'
        'Favor considerar os valores abaixo. Identificamos que as vendas de Outbound '
        'não haviam sido incluídas anteriormente.\r\n\r\n'
        'Atenciosamente,\r\nLidiane'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_enviado_o_ddr_aguarda_finaud():
    """'Enviado o DDR de 29/05 ajustado' → entrega → Aguardando Finaud.
    Reproduz caso Brazabank (RE: DRM 05.2026) mencionado no PENDENCIAS.
    """
    corpo = (
        'Bom dia,\r\n\r\n'
        'Enviado o DDR de 29/05 ajustado e DRM referente a 05/2026 de substituição.\r\n\r\n'
        'Att,\r\nEquipe Brazabank'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_trustee_sem_movimentacao_aguarda_finaud():
    """'Compromissada: sem movimentação' → extrato diário TRUSTEE DTVM → Aguardando Finaud.
    Reproduz os 24 casos de extrato compromissada/LFT da TRUSTEE DTVM.
    """
    corpo = (
        'Compromissada: sem movimentação\r\n\r\n'
        'LFT: sem movimentação\r\n\r\n'
        'Atenciosamente,\r\nTRUSTEE DTVM'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'


def test_status_gentileza_enviar_solicita_finaud():
    """'Gentileza enviar arquivo' → pedido implícito → motivo 'Cliente fez solicitação'.
    Reproduz os 17 casos de pedido implícito sem ponto de interrogação.
    """
    corpo = (
        'Prezados, boa tarde!\r\n\r\n'
        'Gentileza enviar arquivo.\r\n\r\n'
        'Atenciosamente,\r\nJacilaine'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got status: {status} | {motivo}'
    assert 'solicita' in motivo.lower(), f'motivo errado: {motivo}'


def test_status_poderia_nos_ajudar_solicita_finaud():
    """'Poderia nos ajudar enviando a substituição...' → pedido implícito → 'Cliente fez solicitação'."""
    corpo = (
        'Pessoal, bom dia.\r\n\r\n'
        'Poderiam nos ajudar enviando a substituição dos arquivos solicitados.\r\n\r\n'
        'Att,\r\nCliente'
    )
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got status: {status} | {motivo}'
    assert 'solicita' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_preciso_singular_solicita_finaud():
    """'preciso desse arquivo' → pedido implícito singular → 'Cliente fez solicitação'."""
    corpo = 'Entao... preciso desse arquivo com os dados de jun/26.\r\n\r\nAtt,\r\nCliente'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'solicita' in motivo.lower(), f'motivo errado: {motivo}'


# ── §8.8b extensão — seguem/segue mid-frase (01/09/2026) ─────────────────────

def test_status_seguem_o_mapa_inicio_linha_aguarda_finaud():
    """'Seguem o novo Mapa resumido...' no início da linha → §8.8b estendido → Aguardando Finaud."""
    corpo = 'Prezados,\r\n\r\nSeguem o novo Mapa resumido dos Orçamentos Gerenciais.\r\n\r\nAtt,'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_segue_planilha_mid_frase_aguarda_finaud():
    """'segue a planilha do DRL' mid-frase → §8.8b.1 → Aguardando Finaud."""
    corpo = 'Prezados, em continuação, segue a planilha do DRL relativo ao mês 07/2026.\r\n\r\nAtenciosamente,'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_segue_balancete_mid_frase_aguarda_finaud():
    """'Pessoal, segue balancete e arquivos.' → §8.8b.1 → Aguardando Finaud."""
    corpo = 'Pessoal, segue balancete e arquivos.\r\n\r\nAtenciosamente,'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_segue_base_mid_frase_aguarda_finaud():
    """'segue a base completa de Maio/2026' mid-frase → §8.8b.1 → Aguardando Finaud."""
    corpo = 'Boa tarde, segue a base completa de Maio/2026.\r\n\r\nObrigado!'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_planner_nao_houve_compromissada_aguarda_finaud():
    """'Neste dia não houve compromissada' → relatório status Planner SCD → Aguardando Finaud."""
    corpo = 'Bom dia\r\n\r\nNeste dia não houve compromissada\r\n\r\nAtt\r\n\r\nPaulo Henrique\r\nPlanner SCD'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_planner_nao_houveram_compromissadas_aguarda_finaud():
    """'Nestes dias não houveram compromissadas' → plural → Aguardando Finaud."""
    corpo = 'Bom dia\r\n\r\nNestes dias não houveram compromissadas\r\n\r\nAtt\r\n\r\nPaulo Henrique\r\nPlanner SCD'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'


# ── §8.8b.1 — termos "em anexo" e "anexo [objeto]" (01/09/2026) ──────────────

def test_status_em_anexo_arquivo_aguarda_finaud():
    """'Em anexo arquivo solicitado' → entrega mid-frase → Aguardando Finaud."""
    corpo = 'Andrea,\r\n\r\nEm anexo arquivo solicitado.\r\n\r\nAtt,\r\nCliente'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_extratos_em_anexo_aguarda_finaud():
    """'extratos em anexo. Att;' → ENC: EXTRATOS BANVOX/TRUSTEE → Aguardando Finaud."""
    corpo = 'Bom dia,\r\n\r\nExtratos em anexo.\r\n\r\nAtt;\r\nCliente'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_anexo_posicoes_western_union_aguarda_finaud():
    """'Anexo Posições da Western Union Corretora [data]' → relatório diário → Aguardando Finaud."""
    corpo = 'Pessoal!\r\n\r\nAnexo Posições da Western Union Corretora 14/08/2026:\r\n- Posição de Câmbio Contábil\r\n\r\nAtt'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_status_anexo_extratos_banvox_aguarda_finaud():
    """'Anexo extratos da Banvox referentes aos dias X' → BANVOX extrato → Aguardando Finaud."""
    corpo = 'Prezados, bom dia!\r\n\r\nEspero que estejam bem.\r\nAnexo extratos da Banvox referentes aos dias 27 e 28/07/2026.\r\n\r\nAtenciosamente,\r\nJessica Barros'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status} | {motivo}'
    assert 'enviou' in motivo.lower() or 'extratos' in motivo.lower(), f'motivo errado: {motivo}'

def test_nao_filtra_qualquer_anexo_disclaimer():
    """'qualquer anexo é proibida' (disclaimer jurídico) NÃO deve ser detectado como entrega."""
    corpo = 'Qualquer reprodução ou cópia desta mensagem ou de qualquer anexo é estritamente proibida.\r\n\r\nAtt,\r\nCliente'
    msgs = [_msg(CLIENTE, corpo=corpo)]
    status, motivo = bt._determinar_status(msgs)
    # Deve cair em caixa preta — não é entrega
    assert motivo != 'Cliente enviou informações e extratos — aguarda processamento', \
        f'disclaimer foi erroneamente detectado como entrega: {motivo}'


# ── _determinar_status — §8.8 ENC: BANCO CENTRAL (Decisão 9 — 01/09/2026) ───

def test_status_enc_banco_central_motivo_especifico():
    """ENC: BANCO CENTRAL + texto só assinatura ([undefined]) → motivo específico BACEN."""
    corpo = '[undefined]\r\n\r\nAtenciosamente,\r\nJessica Barros da Silva\r\nBANVOX DTVM'
    msgs = [
        _msg(CLIENTE, corpo='Prezados, segue a comunicação do BACEN.'),
        _msg(CLIENTE, corpo=corpo, assunto='ENC: BANCO CENTRAL - INDÍCIO DE PROBLEMA DE QUALIDADE IDENTIFICADO NO DOCUMENTO 4010 - CNPJ 02.671.743'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status}'
    assert 'BACEN' in motivo, f'motivo não menciona BACEN: {motivo}'
    assert motivo == 'BANVOX encaminhou alerta do BACEN sobre documento — aguarda análise da Finaud'


def test_status_enc_banco_central_sem_signoff_motivo_especifico():
    """ENC: BANCO CENTRAL + [undefined] + bloco de contato sem sign-off → motivo BACEN.
    Reproduz o padrão real da assinatura BANVOX (Jessica): logo [undefined] + nome/cargo/tel/endereço
    sem 'Atenciosamente' explícito, fazendo _so_cortesia() retornar False e §8.8 não disparar.
    """
    corpo = (
        '\r\n\r\n[undefined]\r\n Jessica Barros da Silva\r\n  Contabilidade de Fundos\r\n'
        '  E-mail: jessica.silva@banvox.com.br\r\n  Ramal: +55 11 2197-4619\r\n'
        '  Av. Brig. Faria Lima, 3732, 6 andar, Itaim Bibi, São Paulo/SP'
    )
    msgs = [
        _msg(CLIENTE, corpo='Prezados, segue o indício de qualidade do BACEN.'),
        _msg(CLIENTE, corpo=corpo,
             assunto='ENC: BANCO CENTRAL - INDÍCIO DE PROBLEMA DE QUALIDADE IDENTIFICADO NO DOCUMENTO 4010 - CNPJ 02.671.743'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status}'
    assert motivo == 'BANVOX encaminhou alerta do BACEN sobre documento — aguarda análise da Finaud', \
        f'motivo errado: {motivo}'


def test_status_enc_banco_central_nao_afeta_enc_sem_bacen():
    """ENC: sem BANCO CENTRAL no assunto → motivo genérico de entrega (sem regressão)."""
    corpo = '\r\nAtenciosamente,\r\nJessica'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='ENC: DLO Jun/2026')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status}'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento', \
        f'motivo inesperado para ENC sem BACEN: {motivo}'


def test_status_trustee_sem_movimentacao_aguarda_finaud():
    """TRUSTEE DTVM envia extrato diário 'sem movimentação' → entrega de informação (01/09/2026)."""
    corpo = (
        'Compromissada: sem movimentação\r\n\r\nLFT: sem movimentação\r\n\r\n'
        'Atenciosamente,\r\n\r\nRobson S. Neves\r\nContabilidade de Fundos'
    )
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.07.31')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status}'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento', \
        f'motivo errado: {motivo}'


def test_status_arquivo_submetido_concluida():
    """'Arquivo submetido.' (cliente confirmou envio ao BACEN) → Concluída (01/09/2026).
    Reproduz thread DRM Trustee 06/26: Jessica (BANVOX) confirmou submissão do DRM 2060.
    """
    corpo = (
        'Pedro, boa tarde!\r\n\r\nEstou bem e espero que esteja também.\r\n\r\n'
        'Arquivo submetido.\r\n\r\nAtenciosamente,\r\nJessica Barros da Silva'
    )
    msgs = [
        _msg(FINAUD, corpo='Jessica, segue o DRM 2060 para submissão ao BACEN.'),
        _msg(CLIENTE, corpo=corpo),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída', f'got: {status} | {motivo}'


# ── _determinar_status — §8.8-PCAM (Decisão 11 — 01/09/2026) ────────────────

def test_status_enc_pcam_fair_corretora_entrega():
    """ENC: PCAM DD.MM.YYYY + corpo só com bloco de contato (sem Atenciosamente) → entrega."""
    corpo = (
        '\r\n\r\nJosélia Maria da Silva\r\nDepartamento Financeiro\r\n'
        'Fair Corretora de Câmbio S/A\r\nTelefone: (011) 3191-2605\r\n'
        'E mail: jsilva@faircorretora.com.br<mailto:jsilva@faircorretora.com.br>'
    )
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='ENC: PCAM 16.07.2026')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud', f'got: {status}'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'

def test_status_enc_pcam_nao_afeta_sem_enc_prefix():
    """'PCAM' no assunto sem prefixo ENC: não deve ser afetado pela regra §8.8-PCAM."""
    corpo = 'Segue o relatório PCAM do dia.\r\nAtenciosamente,\r\nJosélia'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='PCAM 16.07.2026')]
    status, motivo = bt._determinar_status(msgs)
    # deve cair em §8.8b pelo "Segue" no início — não em §8.8-PCAM
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'


# ── Grupo DDR — Decisão 13 (01/09/2026) ────────────────────────────────────────


def test_so_cortesia_strip_image_inline():
    # [image: ...] sem sign-off: após strip da imagem, só sobra saudação → True
    corpo = '[image: logo.png]\r\n\r\nAtenciosamente,\r\nCarlos'
    assert bt._so_cortesia(corpo) is True


def test_so_cortesia_strip_image_inline_com_conteudo():
    # [image: ...] + texto real: strip da imagem não elimina conteúdo → False
    corpo = '[image: logo.png]\r\n\r\nPrecisamos do arquivo DDR até amanhã.'
    assert bt._so_cortesia(corpo) is False


def test_status_ddr_segue_mid_acabei_de_envi():
    # Thread 1: Planner envia "Acabei de envia a documentação suporte do dia X"
    # _SEGUE_MID: 'acabei de envi' → §8.8b → entrega (01/09/2026)
    corpo = 'Acabei de envia a documentação suporte do dia 04/08.\r\n\r\nAtenciosamente,\r\nClarissa'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='DDR DIA 04/08')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'


def test_status_ddr_segue_mid_pode_seguir():
    # Thread 4: Planner SCD envia "pode seguir pois naqueles dias não tiveram"
    # _SEGUE_MID: 'pode seguir' → §8.8b → entrega (01/09/2026)
    corpo = 'Boa tarde! Pode seguir pois naqueles dias não tiveram movimentação.\r\n\r\nAtt,\r\nPatricia'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='DDR DIA 09/07 E 10/07')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'


def test_status_ddr_assunto_corpo_so_assinatura():
    # Thread 2: Wise envia DDR com corpo apenas bloco de contato extenso (sem sign-off)
    # §8.8-DDR: DDR no assunto + sem "?" + sem solicitação → entrega (01/09/2026)
    corpo = (
        '[image: image.png]\r\n\r\n'
        'Henrique Rezende (he/him)\r\n\r\n'
        'Financial Risk Manager - Latam\r\n\r\n'
        'henrique.rezende@wise.com <email@trasnferwise.com>\r\n\r\n'
        'Wise\r\n'
        '<https://wise.com/?utm_source=emailsignature>\r\n'
        '| What we do\r\n'
        '<https://www.wise.jobs/what-we-do/>\r\n'
    )
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='DDR - 17/07 a 24/07')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'


def test_status_ddr_assunto_com_pergunta_nao_e_entrega():
    # §8.8-DDR NÃO deve disparar quando há "?" no corpo — é uma dúvida real
    corpo = 'Bom dia. Vocês conseguiram processar o DDR de julho?\r\n\r\nAtt,\r\nCarlos'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='DDR - 07/2026')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert 'extratos' not in motivo


# ── Grupo DLO — Decisão 14 (01/09/2026) ────────────────────────────────────────


def test_status_dlo_por_favor_com_pergunta_e_solicitacao():
    # Thread DLO00159: "Por favor seria contigo estes ajustes ?" — pedido com "?"
    # _PEDIDO_FOLLOW_UP: 'por favor' dispara mesmo com "?" (01/09/2026)
    corpo = 'Bom dia, Moises, tudo bem ?\r\n\r\nPor favor seria contigo estes ajustes ?\r\n\r\nMuito obrigado Moisés.'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='RES: Prestação de Esclarecimento DLO00159')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente fez solicitação — aguarda ação da Finaud'


def test_status_dlo_apenas_confirmando_e_entrega():
    # DTVM DLO 2061: "Apenas confirmando, o aumento de capital foi integralizado"
    # _SEGUE_MID: 'apenas confirmando' → §8.8b → entrega (01/09/2026)
    corpo = 'Rodrigo, bom dia.\r\n\r\nApenas confirmando, o aumento de capital, R$ 1.950.000,00 foi integralizado.\r\n\r\nAtenciosamente,\r\nBarbara'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='DTVM - DLO 2061 CALCULO DO PATRIMÔNIO')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'


def test_status_dlo_fyi_forward_e_entrega():
    # DLO Junho/2026: "FYI\r\nRaphael Marino..." — forward com só assinatura
    # _SEGUE_MID: 'fyi' → §8.8b → entrega (01/09/2026)
    corpo = 'FYI\r\n\r\nRaphael Marino\r\nManager | Credit and Risk Management\r\n\r\nraphael.pinheiromarino@wu.com'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='FW: DLO Junho/2026')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente enviou informações e extratos — aguarda processamento'


def test_status_dlo_foi_possivel_com_pergunta_e_solicitacao():
    # DLO/DLI abril/26: "Foi possível realizar as substituições ?" — cobrança
    # _PEDIDO_FOLLOW_UP: 'foi possível' dispara mesmo com "?" (01/09/2026)
    corpo = 'Bom dia,\r\n\r\nFoi possível realizar as substituições ?\r\n\r\nAtenciosamente,\r\nLuiz Eduardo'
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='RE: DLO/DLI abril/26.')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente fez solicitação — aguarda ação da Finaud'


def test_status_dlo_pode_transmitir_e_concluida():
    # Guru CTVM: "Pode transmitir. O problema foi um aumento de capital..."
    # _CONFIRMACAO_EXPLICITA: 'pode transmitir' = autorização → Concluída (01/09/2026)
    corpo = 'Olá Andrea,\r\n\r\nPode transmitir. O problema foi um aumento de capital no último dia do mês.\r\n\r\nAtenciosamente,\r\nGuilherme'
    msgs = [
        _msg(FINAUD, corpo='Segue em anexo a remessa DLO para validação.'),
        _msg(CLIENTE, corpo=corpo, assunto='Re: Guru CTVM: Planilha LEC para DLO 05/2026'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída'
    assert motivo == 'Cliente agradeceu — problema resolvido'


def test_status_dlo_pode_ignorar_e_concluida():
    # BCP Securities: "Pode ignorar meu email." — retratação do cliente
    # _CONFIRMACAO_EXPLICITA: 'pode ignorar' → Concluída (01/09/2026)
    corpo = 'Andrea,\r\n\r\nPode ignorar meu email.\r\n\r\nAtenciosamente,\r\nThaiana'
    msgs = [
        _msg(CLIENTE, corpo='Continuo tomando erro no DRM por conta de layout'),
        _msg(FINAUD, corpo='Olá, verificando...'),
        _msg(CLIENTE, corpo=corpo, assunto='RES: Erro do DRM e DLO'),
    ]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Concluída'
    assert motivo == 'Cliente agradeceu — problema resolvido'


def test_status_dlo_teams_invite_e_solicitacao():
    # DLO / DLO-Maio: convite de reunião Teams = pedido para Finaud entrar na reunião
    # _PEDIDO_FOLLOW_UP: 'reunião do microsoft teams' → solicitação (01/09/2026)
    corpo = (
        'Reunião do Microsoft Teams\r\n'
        'Ingressar: https://teams.microsoft.com/meet/285391606170599?p=exBUuaPViFZIfhT9fk\r\n'
        'ID da Reunião: 285 391 606 170 599\r\n'
        'Senha: xy7Xg3W7'
    )
    msgs = [_msg(CLIENTE, corpo=corpo, assunto='DLO')]
    status, motivo = bt._determinar_status(msgs)
    assert status == 'Aguardando Finaud'
    assert motivo == 'Cliente fez solicitação — aguarda ação da Finaud'
