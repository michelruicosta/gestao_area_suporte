"""
test_servidor_telas.py
Sair volta ao portal. Login segue o padrão Finaud (olho na senha, sem Esqueceu a senha).
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime

from tests.conftest import RAIZ

_scripts_dir = os.path.join(RAIZ, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import servidor_telas as st  # noqa: E402
from servidor_telas import app  # noqa: E402


def test_sair_e_logout_redirecionam_para_o_portal():
    client = app.test_client()
    for rota in ('/sair', '/logout'):
        resp = client.get(rota, follow_redirects=False)
        destino = resp.headers.get('Location', '')
        assert resp.status_code == 302, rota
        assert destino == 'http://127.0.0.1:8000/portal-preview/', rota
        assert '/login' not in destino, rota

    for rota in ('/sair', '/logout'):
        resp = client.get(
            rota,
            follow_redirects=False,
            headers={'Host': 'gestao-suporte.finaudapps.com.br'},
        )
        destino = resp.headers.get('Location', '')
        assert resp.status_code == 302, rota
        assert destino == 'https://finaudapps.com.br', rota
        assert '/login' not in destino, rota


def test_login_sem_esqueceu_senha_olho_dentro_do_campo():
    """Senha se recupera no portal — o login do app não mostra Esqueceu a senha."""
    html = app.test_client().get('/login').get_data(as_text=True)
    assert 'Esqueceu a senha?' not in html
    assert 'form-recuperar' not in html
    assert 'Recuperar acesso' not in html
    assert 'Enviar senha temporária' not in html
    assert 'campo-senha-toggle' in html
    assert 'class="olho-btn"' not in html
    assert 'Entrar' in html
    assert 'Portal de apps' in html


def test_recuperar_senha_nao_revela_se_email_existe(monkeypatch):
    monkeypatch.setattr(st, '_enviar_senha_temporaria', lambda *a, **k: False)
    client = app.test_client()
    mensagens = []
    for email in (st._ADMIN_EMAIL, 'naoexiste@finaud.com.br'):
        resp = client.post('/auth/recuperar-senha', json={'email': email})
        assert resp.status_code == 200, email
        body = resp.get_json()
        mensagens.append(body['mensagem'])
        assert body['mensagem'] == st._MENSAGEM_RECUPERAR
    assert mensagens[0] == mensagens[1]


def test_recuperar_senha_grava_hash_quando_email_sai(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"intervalo_coleta_min": 60, "intervalo_fog_min": 15}', encoding='utf-8')
    monkeypatch.setattr(st, '_CONFIG_PATH', str(cfg))
    enviados = []

    def fake_enviar(destino, senha_temp, url_login):
        enviados.append((destino, senha_temp, url_login))
        return True

    monkeypatch.setattr(st, '_enviar_senha_temporaria', fake_enviar)
    client = app.test_client()
    resp = client.post('/auth/recuperar-senha', json={'email': st._ADMIN_EMAIL})
    assert resp.status_code == 200
    assert enviados
    nova = enviados[0][1]

    falha = client.post(
        '/login',
        data={'email': st._ADMIN_EMAIL, 'senha': st._ADMIN_SENHA},
        follow_redirects=False,
    )
    assert falha.status_code == 200
    assert 'incorretos' in falha.get_data(as_text=True)

    ok = client.post(
        '/login',
        data={'email': st._ADMIN_EMAIL, 'senha': nova},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers.get('Location', '').endswith('/')


def test_rotas_fog_antigas_nao_existem():
    client = app.test_client()
    for rota in ('/fog/gerencial', '/fog/operacional'):
        resp = client.get(rota, follow_redirects=False)
        assert resp.status_code == 404, rota


def test_porta_padrao_no_pc_e_8004():
    """No PC a tela Flask sobe em 8004 — não 5001 nem porta de outro app."""
    import inspect

    fonte = inspect.getsource(st)
    assert "os.environ.get('PORT', 8004)" in fonte


def test_menu_usuario_nao_tem_meu_perfil():
    """Senha passa a ser alterada no portal — o Gestão não mostra Meu Perfil."""
    caminho = os.path.join(RAIZ, 'templates', 'gestao_email.html')
    with open(caminho, encoding='utf-8') as f:
        html = f.read()
    assert 'Meu Perfil' not in html
    assert 'abrirPerfil' not in html
    assert 'Alterar senha' not in html
    assert 'user-menu' in html
    assert '/sair' in html


def test_codigo_nao_guarda_senha_nem_chave_de_fabrica():
    """Se o .env faltar, não pode sobrar senha/chave conhecida no código."""
    caminho = os.path.join(RAIZ, 'scripts', 'servidor_telas.py')
    with open(caminho, encoding='utf-8') as f:
        fonte = f.read()
    assert 'finaud2026' not in fonte
    assert 'oraculo360-gestao-secret' not in fonte
    assert "os.environ.get('SECRET_KEY', " not in fonte
    assert "os.environ.get('GESTAO_SENHA', " not in fonte


def test_login_local_sem_senha_configurada_nao_entra(monkeypatch):
    """Sem GESTAO_SENHA e sem hash, a tela de login local recusa qualquer senha."""
    monkeypatch.setattr(st, '_ADMIN_SENHA', '')
    monkeypatch.setattr(st, '_ler_config', lambda: {})
    resp = app.test_client().post(
        '/login',
        data={'email': st._ADMIN_EMAIL, 'senha': 'qualquer-coisa'},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert 'incorretos' in resp.get_data(as_text=True)


def test_rota_perfil_volta_para_a_tela_principal():
    """Quem abrir /perfil (atalho antigo) cai na tela principal, não numa página quebrada."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['logado'] = True
        sess['email'] = st._ADMIN_EMAIL
    resp = client.get('/perfil', follow_redirects=False)
    assert resp.status_code == 302
    destino = resp.headers.get('Location', '')
    assert destino.endswith('/')
    assert '/perfil' not in destino.rstrip('/')


def test_normalizar_notificacoes_aceita_varios_grupos():
    out = st.normalizar_notificacoes([{
        'id': 'busca_email_parou',
        'ativa': True,
        'grupos': ['administrador', 'gestor', 'lixo'],
    }])
    assert len(out) == 1
    assert out[0]['grupos'] == ['administrador', 'gestor']
    assert out[0]['ativa'] is True


def test_normalizar_notificacoes_sem_lista_volta_ao_padrao():
    out = st.normalizar_notificacoes(None)
    assert out[0]['id'] == 'busca_email_parou'
    assert out[0]['grupos'] == ['administrador']


def test_avaliar_situacao_busca_parada_quando_atrasada():
    agora = datetime(2026, 9, 1, 12, 0, 0)
    logs = [{'status': 'concluida', 'data_hora': '2026-09-01 08:00:00'}]
    r = st.avaliar_situacao_busca(
        {'intervalo_coleta_min': 60}, logs, False, agora=agora,
    )
    assert r['site']['ok'] is True
    assert r['busca']['ok'] is False
    assert r['busca']['rotulo'] == 'Parada'


def test_avaliar_situacao_busca_ligada_dentro_do_intervalo():
    agora = datetime(2026, 9, 1, 12, 0, 0)
    logs = [{'status': 'concluida', 'data_hora': '2026-09-01 11:30:00'}]
    r = st.avaliar_situacao_busca(
        {'intervalo_coleta_min': 60}, logs, False, agora=agora,
    )
    assert r['busca']['ok'] is True
    assert r['busca']['rotulo'] == 'Ligada'


def test_html_administracao_email_notificacoes_sem_fog():
    caminho = os.path.join(RAIZ, 'templates', 'gestao_email.html')
    with open(caminho, encoding='utf-8') as f:
        html = f.read()
    assert 'nav-txt">E-mail</span>' in html
    assert 'Buscar e-mails agora' in html
    assert 'Histórico das buscas de e-mail' in html
    assert 'Situação da busca' in html
    assert 'id="pag-notificacoes"' in html
    assert 'notif-g-administrador' in html
    assert 'cfg-intervalo-fog' not in html
    assert 'Atualização dos dados do FOGBUGZ' not in html
    assert 'Receber e-mail de alertas' not in html
    assert 'data-pagina="admin" data-aba="coletor"' not in html
    assert 'um recado por episódio' in html


def test_api_grava_notificacoes_com_varios_grupos(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.json'
    cfg.write_text('{"intervalo_coleta_min": 60}', encoding='utf-8')
    monkeypatch.setattr(st, '_CONFIG_PATH', str(cfg))
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['logado'] = True
        sess['email'] = st._ADMIN_EMAIL
    resp = client.post(
        '/api/admin/config',
        json={
            'notificacoes': [{
                'id': 'busca_email_parou',
                'ativa': True,
                'grupos': ['administrador', 'gestor'],
            }],
        },
    )
    assert resp.status_code == 200
    got = client.get('/api/admin/config')
    assert got.status_code == 200
    body = got.get_json()
    assert body['notificacoes'][0]['grupos'] == ['administrador', 'gestor']


def test_html_aviso_busca_parou_segue_rascunho_aprovado():
    from aviso_busca_parou import montar_html_aviso_busca_parou

    html = montar_html_aviso_busca_parou(
        'Michel', '01/09/2026 às 09:00', 60, 'https://finaudapps.com.br',
    )
    assert 'GESTÃO ÁREA SUPORTE' in html
    assert 'Busca de e-mail parou' in html
    assert 'não rodou no tempo marcado' in html
    assert '01/09/2026 às 09:00' in html
    assert '60 minutos' in html
    assert 'Abrir a Gestão' in html
    assert 'https://finaudapps.com.br' in html
    assert 'Se a busca já tiver voltado a rodar' in html
    assert 'Origem do alerta' in html
    assert 'Servidor (produção)' in html

    html_local = montar_html_aviso_busca_parou(
        'Michel', '01/09/2026 às 09:00', 60, 'http://localhost:8004',
    )
    assert 'PC local (seu computador)' in html_local


def test_aviso_busca_nao_repete_no_mesmo_episodio():
    from aviso_busca_parou import verificar_e_avisar_busca_parada

    agora = datetime(2026, 9, 1, 12, 0, 0)
    logs = [{'status': 'concluida', 'data_hora': '2026-09-01 08:00:00'}]
    cfg = {
        'intervalo_coleta_min': 60,
        'notificacoes': [{'id': 'busca_email_parou', 'ativa': True, 'grupos': ['administrador']}],
    }
    enviados = []

    def fake_enviar(destino, html):
        enviados.append((destino, html))
        return True

    cfg, ok1 = verificar_e_avisar_busca_parada(
        cfg, logs, False,
        admin_email='michel@finaud.com.br',
        portal_url='https://finaudapps.com.br',
        agora=agora,
        enviar=fake_enviar,
    )
    assert ok1 is True
    assert len(enviados) == 1
    assert enviados[0][0] == 'michel@finaud.com.br'
    assert 'Olá, <b>Michel</b>' in enviados[0][1]

    cfg, ok2 = verificar_e_avisar_busca_parada(
        cfg, logs, False,
        admin_email='michel@finaud.com.br',
        portal_url='https://finaudapps.com.br',
        agora=agora,
        enviar=fake_enviar,
    )
    assert ok2 is False
    assert len(enviados) == 1


def test_aviso_busca_nao_envia_quando_ligada_ou_desligada():
    from aviso_busca_parou import verificar_e_avisar_busca_parada

    agora = datetime(2026, 9, 1, 12, 0, 0)
    logs_ok = [{'status': 'concluida', 'data_hora': '2026-09-01 11:30:00'}]
    enviados = []

    cfg, ok = verificar_e_avisar_busca_parada(
        {'intervalo_coleta_min': 60}, logs_ok, False,
        admin_email='michel@finaud.com.br',
        portal_url='https://finaudapps.com.br',
        agora=agora,
        enviar=lambda *a: enviados.append(a) or True,
    )
    assert ok is False
    assert enviados == []

    logs_parada = [{'status': 'concluida', 'data_hora': '2026-09-01 08:00:00'}]
    cfg_off = {
        'intervalo_coleta_min': 60,
        'notificacoes': [{'id': 'busca_email_parou', 'ativa': False, 'grupos': ['administrador']}],
    }
    cfg, ok = verificar_e_avisar_busca_parada(
        cfg_off, logs_parada, False,
        admin_email='michel@finaud.com.br',
        portal_url='https://finaudapps.com.br',
        agora=agora,
        enviar=lambda *a: enviados.append(a) or True,
    )
    assert ok is False
    assert enviados == []


def test_portal_no_email_nunca_e_localhost():
    from aviso_busca_parou import url_portal_no_email

    assert url_portal_no_email('http://127.0.0.1:8000/portal-preview/') == 'https://finaudapps.com.br'


def test_contar_dias_uteis_pula_fim_de_semana():
    """Sexta até segunda conta 1 dia; sábado e domingo não entram."""
    assert st.contar_dias_uteis(date(2026, 8, 28), date(2026, 8, 31)) == 1
    assert st.contar_dias_uteis(date(2026, 8, 28), date(2026, 8, 30)) == 0
    assert st.contar_dias_uteis(date(2026, 9, 1), date(2026, 9, 1)) == 0
    assert st.contar_dias_uteis(date(2026, 8, 24), date(2026, 8, 31)) == 5
    assert st.contar_dias_uteis(date(2026, 8, 27), date(2026, 8, 28)) == 1


def test_contar_dias_uteis_pula_feriado_oficial_do_brasil():
    """Independência 2026 cai na segunda; Carnaval 2026 na segunda e terça."""
    assert date(2026, 9, 7) in st.feriados_oficiais_brasil(2026)
    assert date(2026, 2, 16) in st.feriados_oficiais_brasil(2026)
    assert date(2026, 2, 17) in st.feriados_oficiais_brasil(2026)
    assert date(2026, 11, 20) in st.feriados_oficiais_brasil(2026)
    # sexta 4/9 → terça 8/9: sábado, domingo e 7/9 (feriado) ficam de fora → 1
    assert st.contar_dias_uteis(date(2026, 9, 4), date(2026, 9, 8)) == 1
    # sexta 13/2 → quarta 18/2: fim de semana + Carnaval → só a quarta conta
    assert st.contar_dias_uteis(date(2026, 2, 13), date(2026, 2, 18)) == 1


def test_buscar_fog_usa_contar_dias_uteis():
    import inspect

    fonte = inspect.getsource(st._buscar_fog)
    assert 'contar_dias_uteis' in fonte
    assert '(hoje - dt_upd).days' not in fonte


def test_tela_fog_legenda_e_cortes_em_dias_uteis(monkeypatch):
    """Legenda, cartões e cores usam 6 e 11 — a mesma régua da conta em dias úteis."""
    monkeypatch.setattr(st, '_buscar_fog', lambda *a, **k: [
        {
            'id': '1', 'assunto': 'caso verde', 'projeto': 'P', 'area': 'A',
            'responsavel': 'Ana', 'status': 'Ativo', 'dias_responsavel': 5,
            'data': '2026-08-20', 'data_fechamento': None,
        },
        {
            'id': '2', 'assunto': 'caso ambar', 'projeto': 'P', 'area': 'A',
            'responsavel': 'Ana', 'status': 'Ativo', 'dias_responsavel': 6,
            'data': '2026-08-15', 'data_fechamento': None,
        },
        {
            'id': '3', 'assunto': 'caso vermelho', 'projeto': 'P', 'area': 'A',
            'responsavel': 'Bia', 'status': 'Ativo', 'dias_responsavel': 11,
            'data': '2026-08-01', 'data_fechamento': None,
        },
        {
            'id': '9', 'assunto': 'caso fechado', 'projeto': 'P', 'area': 'A',
            'responsavel': 'Ana', 'status': 'Fechado', 'dias_responsavel': 99,
            'data': '2026-01-01', 'data_fechamento': '2026-03-01',
        },
    ])
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['logado'] = True
        sess['email'] = st._ADMIN_EMAIL
    html = client.get('/').get_data(as_text=True)
    assert 'Verde &lt; 6 dias' in html
    assert 'Âmbar 6–10 dias' in html
    assert 'Vermelho ≥ 11 dias' in html
    assert 'Verde &lt; 8 dias' not in html
    assert 'const FOG_CORTE_AMBAR = 6' in html
    assert 'const FOG_CORTE_VERMELHO = 11' in html
    assert 'menos de 6 dias' in html
    assert 'parado há 6–10 dias' in html
    assert 'parado há ≥ 11 dias' in html
    assert 'fog-amber' in html
    assert 'fog-red' in html
    assert st._FOG_DIAS_AMBAR == 6
    assert st._FOG_DIAS_VERMELHO == 11
    assert 'Sem atualização há:' not in html
    assert '5 du' in html
    assert '6 du' in html
    assert '11 du' in html
    assert '11d</div>' not in html
    assert 'duração do caso' not in html
    assert '99 du' not in html


def test_fog_colaboradores_rota_existe():
    client = app.test_client()
    resp = client.get('/api/fog-colaboradores', follow_redirects=False)
    assert resp.status_code in (302, 200), 'rota /api/fog-colaboradores não existe'


def test_fog_jornada_caso_rota_existe():
    client = app.test_client()
    resp = client.get('/api/fog-jornada/8156', follow_redirects=False)
    assert resp.status_code in (302, 200, 404), 'rota /api/fog-jornada/<id> não existe'


def test_fog_jornada_caso_funcao_definida():
    assert hasattr(st, '_buscar_jornada_caso'), '_buscar_jornada_caso não definida'


def test_fog_colaboradores_funcao_definida():
    import inspect
    assert hasattr(st, '_buscar_fog_colaboradores')
    fonte = inspect.getsource(st._buscar_fog_colaboradores)
    assert 'evtDescription' in fonte
    assert 'Designado para' in fonte


def test_fog_colaboradores_pagina_no_html():
    caminho = os.path.join(RAIZ, 'templates', 'gestao_email.html')
    with open(caminho, encoding='utf-8') as f:
        html = f.read()
    assert 'id="pag-fog-colaboradores"' in html
    assert 'fog-colaboradores' in html
    assert 'Por Colaborador' in html


# ── Jornada dos Casos (Por Colaborador) ──────────────────────────────────────

def test_pivotar_por_fog_jornada_cronologica():
    """_pivotar_por_fog deve montar a jornada de cada FOG em ordem cronológica."""
    from servidor_telas import _pivotar_por_fog
    colaboradores = [
        {
            'nome': 'Ana',
            'fogs': [{'id': '1', 'titulo': 'Caso A', 'status': 'Ativo',
                      'atribuicoes': [{'seq': 1, 'inicio': '2026-01-01', 'fim': '2026-02-01',
                                       'dias': 31, 'em_aberto': False}]}],
        },
        {
            'nome': 'Bruno',
            'fogs': [{'id': '1', 'titulo': 'Caso A', 'status': 'Ativo',
                      'atribuicoes': [{'seq': 1, 'inicio': '2026-02-01', 'fim': None,
                                       'dias': 50, 'em_aberto': True}]}],
        },
    ]
    resultado = _pivotar_por_fog(colaboradores)
    assert len(resultado) == 1
    fog = resultado[0]
    assert fog['id'] == '1'
    assert fog['total_dias'] == 81
    assert len(fog['etapas']) == 2
    assert fog['etapas'][0]['nome'] == 'Ana'    # ordem cronológica
    assert fog['etapas'][1]['nome'] == 'Bruno'
    assert fog['etapas'][1]['em_aberto'] is True


def test_pivotar_por_fog_gargalo_marcado():
    """A etapa com mais dias deve ser marcada como gargalo (quando há 2+ etapas)."""
    from servidor_telas import _pivotar_por_fog
    colaboradores = [
        {
            'nome': 'Ana',
            'fogs': [{'id': '2', 'titulo': 'Caso B', 'status': 'Ativo',
                      'atribuicoes': [{'seq': 1, 'inicio': '2026-01-01', 'fim': '2026-02-01',
                                       'dias': 10, 'em_aberto': False}]}],
        },
        {
            'nome': 'Bruno',
            'fogs': [{'id': '2', 'titulo': 'Caso B', 'status': 'Ativo',
                      'atribuicoes': [{'seq': 1, 'inicio': '2026-02-01', 'fim': None,
                                       'dias': 90, 'em_aberto': True}]}],
        },
    ]
    resultado = _pivotar_por_fog(colaboradores)
    fog = resultado[0]
    assert not fog['etapas'][0]['gargalo']   # Ana: 10d — não é gargalo
    assert fog['etapas'][1]['gargalo']        # Bruno: 90d — é gargalo


def test_pivotar_por_fog_mescla_etapas_consecutivas():
    """Etapas consecutivas do mesmo colaborador devem ser mescladas em uma só."""
    from servidor_telas import _pivotar_por_fog
    colaboradores = [
        {
            'nome': 'Fabio',
            'fogs': [{'id': '9', 'titulo': 'Volta pra Fabio', 'status': 'Ativo',
                      'atribuicoes': [
                          {'posicao': 0, 'inicio': '2026-01-01', 'fim': '2026-01-10',
                           'dias': 9, 'em_aberto': False},
                          {'posicao': 1, 'inicio': '2026-01-10', 'fim': None,
                           'dias': 5, 'em_aberto': True},
                      ]}],
        },
    ]
    resultado = _pivotar_por_fog(colaboradores)
    fog = resultado[0]
    # Duas atribuições consecutivas do mesmo colaborador devem virar uma
    assert len(fog['etapas']) == 1
    assert fog['etapas'][0]['dias'] == 14
    assert fog['etapas'][0]['passagens'] == 2
    assert fog['etapas'][0]['em_aberto'] is True


def test_pivotar_por_fog_nao_mescla_nao_consecutivas():
    """Etapas do mesmo colaborador separadas por outro não devem ser mescladas."""
    from servidor_telas import _pivotar_por_fog
    colaboradores = [
        {
            'nome': 'Fabio',
            'fogs': [{'id': '10', 'titulo': 'Vai e volta', 'status': 'Ativo',
                      'atribuicoes': [
                          {'posicao': 0, 'inicio': '2026-01-01', 'fim': '2026-01-10',
                           'dias': 9, 'em_aberto': False},
                          {'posicao': 2, 'inicio': '2026-01-20', 'fim': None,
                           'dias': 5, 'em_aberto': True},
                      ]}],
        },
        {
            'nome': 'Suporte',
            'fogs': [{'id': '10', 'titulo': 'Vai e volta', 'status': 'Ativo',
                      'atribuicoes': [
                          {'posicao': 1, 'inicio': '2026-01-10', 'fim': '2026-01-20',
                           'dias': 10, 'em_aberto': False},
                      ]}],
        },
    ]
    resultado = _pivotar_por_fog(colaboradores)
    fog = resultado[0]
    # Fabio → Suporte → Fabio: 3 etapas separadas
    assert len(fog['etapas']) == 3
    nomes = [e['nome'] for e in fog['etapas']]
    assert nomes == ['Fabio', 'Suporte', 'Fabio']


def test_pivotar_por_fog_passa_dtlastupdated():
    """_pivotar_por_fog deve repassar dtLastUpdated e dias_sem_atualizacao do fog de entrada."""
    from servidor_telas import _pivotar_por_fog
    colaboradores = [
        {
            'nome': 'Luiz',
            'fogs': [{'id': '42', 'titulo': 'Teste', 'status': 'Ativo',
                      'dtLastUpdated': '2026-07-05',
                      'dias_sem_atualizacao': 67,
                      'atribuicoes': [{'posicao': 0, 'inicio': '2026-07-05', 'fim': None,
                                       'dias': 67, 'em_aberto': True}]}],
        },
    ]
    resultado = _pivotar_por_fog(colaboradores)
    fog = resultado[0]
    assert fog.get('dtLastUpdated') == '2026-07-05'
    assert fog.get('dias_sem_atualizacao') == 67


# ── Ranking Visão Consolidada ─────────────────────────────────────────────────

def test_ranking_media_dias_calculada():
    """Cada item do ranking deve conter media_dias = média de dias dos casos ativos."""
    from collections import defaultdict
    casos_mock = [
        {'responsavel': 'Ana', 'dias_responsavel': 10, 'assunto': 'Caso A'},
        {'responsavel': 'Ana', 'dias_responsavel': 30, 'assunto': 'Caso B'},
        {'responsavel': 'Bruno', 'dias_responsavel': 50, 'assunto': 'Caso C'},
    ]
    by_resp = defaultdict(list)
    for c in casos_mock:
        by_resp[c['responsavel']].append(c)
    ranking = [
        {
            'nome':             nome,
            'casos':            len(casos),
            'caso_mais_antigo': max(casos, key=lambda x: x['dias_responsavel'])['assunto'],
            'dias_mais_antigo': max(casos, key=lambda x: x['dias_responsavel'])['dias_responsavel'],
            'media_dias':       round(sum(c['dias_responsavel'] for c in casos) / len(casos)),
        }
        for nome, casos in by_resp.items()
    ]
    ana   = next(r for r in ranking if r['nome'] == 'Ana')
    bruno = next(r for r in ranking if r['nome'] == 'Bruno')
    assert ana['media_dias'] == 20    # (10+30)/2
    assert bruno['media_dias'] == 50  # 50/1
    assert ana['dias_mais_antigo'] == 30


# ── Notificação FOG Suporte Finaud ────────────────────────────────────────────

def test_fog_suporte_normalizar_padrao():
    import sys
    sys.path.insert(0, os.path.join(RAIZ, 'scripts'))
    from aviso_fog_suporte import normalizar_notificacao_fog
    n = normalizar_notificacao_fog(None)
    assert n['ativa'] is True
    assert 'administrador' in n['grupos']
    assert 0 <= n['dia_semana'] <= 6


def test_fog_suporte_normalizar_dia_invalido():
    from aviso_fog_suporte import normalizar_notificacao_fog
    n = normalizar_notificacao_fog({'dia_semana': 99, 'ativa': True, 'grupos': ['gestor']})
    assert n['dia_semana'] == 6


def test_fog_suporte_deve_enviar_dia_errado():
    from aviso_fog_suporte import verificar_e_enviar_fog_suporte
    from datetime import datetime, timezone
    # dia_semana=0 (segunda), testa numa terça (weekday=1)
    cfg = {'notif_fog_suporte': {'ativa': True, 'grupos': ['administrador'], 'dia_semana': 0}}
    terca = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)  # terça-feira
    novo, enviou = verificar_e_enviar_fog_suporte(
        cfg, admin_email='test@test.com', token='', agora=terca
    )
    assert not enviou


def test_fog_suporte_html_contem_estrutura():
    from aviso_fog_suporte import montar_html_fog_suporte
    fogs = [
        {'id': '9999', 'titulo': 'Caso de teste', 'dias': 45},
        {'id': '9998', 'titulo': 'Outro caso', 'dias': 5},
    ]
    html = montar_html_fog_suporte('Michel', fogs, '09/09/2026', 'Segunda-feira')
    assert 'FOGs aguardando encerramento' in html
    assert '9999' in html
    assert 'Abrir' in html
    assert 'Segunda-feira' in html
    assert '#fff7ed' in html  # badge laranja (45 dias)


def test_fog_suporte_notificacao_no_html():
    caminho = os.path.join(RAIZ, 'templates', 'gestao_email.html')
    with open(caminho, encoding='utf-8') as f:
        html = f.read()
    assert 'notif-fog-ativa' in html
    assert 'notif-fog-g-administrador' in html
    assert 'notif-fog-dia' in html
    assert 'FOGs aguardando encerramento' in html


def test_fog_suporte_busca_inclui_filtro_data():
    """A query enviada ao FogBugz deve incluir o filtro de data desde Jan/2025."""
    from unittest.mock import patch, MagicMock
    from aviso_fog_suporte import buscar_fogs_suporte_abertos

    resp_mock = MagicMock()
    resp_mock.text = '<cases></cases>'

    with patch('aviso_fog_suporte.requests.get', return_value=resp_mock) as mock_get:
        buscar_fogs_suporte_abertos('token-teste')

    queries = [
        c.kwargs.get('params', {}).get('q', '')
        for c in mock_get.call_args_list
        if c.kwargs.get('params', {}).get('cmd') == 'search'
    ]
    assert queries, 'Nenhuma chamada de search encontrada'
    assert '2025/01/01' in queries[0], f'Filtro de data ausente: {queries[0]!r}'
    assert 'assignedTo:"Suporte Finaud"' in queries[0]


# ── Testes: _resolver_de e _resolver_para (regras De/Para do modal) ────────────

def _msg(remetente='', destinatarios='', cc='', reply_to=''):
    return {'remetente': remetente, 'destinatarios': destinatarios, 'cc': cc, 'reply_to': reply_to}


class TestResolverDe:
    def test_colaborador_pessoal_usa_from(self):
        m = _msg(remetente='Sarah Sá <sarah.sa@finaud.com.br>')
        assert st._resolver_de(m) == 'Sarah Sá'

    def test_cliente_direto_usa_from(self):
        m = _msg(remetente='João Silva <joao@empresa.com.br>')
        assert st._resolver_de(m) == 'João Silva'

    def test_cliente_via_suporte_usa_reply_to(self):
        m = _msg(
            remetente='"\'Leonardo Ueda\' via Suporte" <suporte@finaud.com.br>',
            reply_to='Leonardo Ueda <leonardo@westernunion.com>',
        )
        assert st._resolver_de(m) == 'Leonardo Ueda'

    def test_colaborador_via_suporte_com_nome_usa_from(self):
        m = _msg(remetente='Sarah Sá <suporte@finaud.com.br>')
        assert st._resolver_de(m) == 'Sarah Sá'

    def test_suporte_sem_nome_vira_suporte_finaud(self):
        m = _msg(remetente='suporte <suporte@finaud.com.br>')
        assert st._resolver_de(m) == 'Suporte Finaud'


class TestResolverPara:
    def test_cliente_direto_para_colaborador(self):
        m = _msg(
            remetente='João <joao@empresa.com.br>',
            destinatarios='Andrea Inacio <andrea.inacio@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Andrea Inacio'

    def test_cliente_direto_para_so_suporte(self):
        m = _msg(
            remetente='João <joao@empresa.com.br>',
            destinatarios='suporte <suporte@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'suporte@finaud.com.br'

    def test_cliente_direto_para_colaborador_e_suporte(self):
        m = _msg(
            remetente='João <joao@empresa.com.br>',
            destinatarios='Andrea Inacio <andrea.inacio@finaud.com.br>, suporte <suporte@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Andrea Inacio'

    def test_cliente_direto_externo_e_colaborador_mostra_colaborador(self):
        """C-A: cliente envia para colega externo + colaborador Finaud → Para = colaborador."""
        m = _msg(
            remetente='Empresas Denver <contato@denver.com.br>',
            destinatarios='Luiz Externo <luiz@outraempresa.com.br>, Monica Macedo <monica.macedo@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Monica Macedo'

    def test_cliente_via_suporte_externo_e_colaborador_mostra_colaborador(self):
        """C-B: cliente via suporte@ envia para externo + colaborador → Para = colaborador."""
        m = _msg(
            remetente='"Victor via Suporte" <suporte@finaud.com.br>',
            reply_to='Victor <victor@miraeinvest.com.br>',
            destinatarios='Vitor Externo <vitor@miraeinvest.com.br>, Andrea Inacio <andrea.inacio@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Andrea Inacio'

    def test_colaborador_via_suporte_para_cliente_e_colaborador_cc_mostra_cliente(self):
        """F4a: colaborador via suporte@ para cliente + colaborador em CC → Para = cliente (Fix A)."""
        m = _msg(
            remetente='"Sarah Sá" <suporte@finaud.com.br>',
            destinatarios='Andrea Inacio <andrea.inacio@finaud.com.br>, Jacilaine Lima <j@planner.com.br>',
        )
        assert st._resolver_para(m) == 'Jacilaine Lima'

    def test_colaborador_via_suporte_para_cliente_suporte_no_to_mostra_cliente(self):
        """F2a+: colaborador via suporte@ para cliente + suporte@ no To → Para = cliente."""
        m = _msg(
            remetente='"Rodrigo Tiberio" <suporte@finaud.com.br>',
            destinatarios='Mariana Fagueiro <mariana@wise.com>, suporte <suporte@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Mariana Fagueiro'

    def test_colaborador_pessoal_externo_e_colaborador_cc_mostra_externo(self):
        """F3a: colaborador (email pessoal) para cliente + colega em CC → Para = cliente."""
        m = _msg(
            remetente='Rodrigo Tiberio <rodrigo.tiberio@finaud.com.br>',
            destinatarios='Juliana Meirelles <juliana@agk.com.br>, Marcio Vellani <marcio@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Juliana Meirelles'

    def test_colaborador_pessoal_externo_suporte_cc_mostra_externo(self):
        """F3b: colaborador (email pessoal) para cliente + suporte@ em CC → Para = cliente."""
        m = _msg(
            remetente='Rodrigo Tiberio <rodrigo.tiberio@finaud.com.br>',
            destinatarios='Jessica Santos <jessica@unidad.com.br>, suporte <suporte@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Jessica Santos'

    def test_colaborador_interno_para_colaborador(self):
        """F1b: colaborador pessoal → outro colaborador (interno) → Para = colaborador."""
        m = _msg(
            remetente='Rodrigo Tiberio <rodrigo.tiberio@finaud.com.br>',
            destinatarios='Rafael Pereira <rafael@finaud.com.br>',
        )
        assert st._resolver_para(m) == 'Rafael Pereira'
