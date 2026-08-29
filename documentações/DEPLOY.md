# DEPLOY — Gestão Área Suporte

**Documento criado:** 25/08/2026
**Responsável:** Michel Rui Costa
**Plataforma:** VPS Hostinger (instruções específicas serão adicionadas por Michel)
**Contexto:** este projeto faz parte de um portal maior — não sobe de forma isolada.

---

## O que é este sistema

Aplicação web em Flask (Python) que centraliza a gestão da área de suporte da Finaud:
- Lê e classifica e-mails da caixa de coleta via Gmail API
- Integra com FogBugz para acompanhamento de casos de suporte
- Tela web no PC: `http://localhost:8004` (não mandar o link se o servidor não estiver no ar). No site: o domínio publicado.

**Tecnologia:** Python 3.x + Flask + SQLite + Gmail API + FogBugz API

---

## Variáveis de ambiente necessárias

Criar um arquivo `.env` no servidor com estas variáveis (nunca commitar o `.env` real):

Criar o arquivo `.env` no servidor copiando o bloco abaixo e preenchendo os valores:

```
# Gestão Área Suporte — variáveis de ambiente
# Copie este bloco, preencha os valores e salve como .env na raiz do projeto

SECRET_KEY=coloque-aqui-uma-string-longa-e-aleatoria
GESTAO_EMAIL=michel@finaud.com.br
FOGBUGZ_TOKEN=seu-token-do-fogbugz-aqui
PORT=8004
```

| Variável | Descrição | Obrigatória |
|---|---|---|
| `SECRET_KEY` | Chave secreta do Flask — texto longo e aleatório. **Sem ela o servidor não sobe.** Não há valor de fábrica. | Sim |
| `GESTAO_EMAIL` | E-mail aceito no login direto da tela (se alguém abrir o app sem passar pelo portal) | Sim |
| `GESTAO_SENHA` | Só se quiser login direto nesta tela. O dia a dia é o portal. **Não** há senha de fábrica. | Não |
| `FOGBUGZ_TOKEN` | Token da API do FogBugz — gerar em Configurações > API no FogBugz | Sim |
| `PORT` | Porta onde o servidor sobe no PC (padrão: **8004**) | Não |

⚠️ **Lembrete:** a senha do Gmail (`GMAIL_APP_PASS`) está em `_archive/arquivos_raiz/chave_app_coleta.oraculo@finaud.com.br.txt` — adicionar ao `.env` quando necessário.

---

## Arquivos que sobem pelo git (código)

```
gestao_area_suporte/
├── scripts/
│   ├── servidor_telas.py           ← servidor Flask (ponto de entrada)
│   ├── banco_threads.py            ← acesso ao banco de dados de threads
│   ├── classificador_regras.py     ← classificador de e-mails
│   ├── validador_classificacao.py  ← filtros de e-mails automáticos (usado pelo classificador)
│   ├── coletor_gmail.py            ← coleta de e-mails via Gmail API
│   ├── executar_pipeline.py        ← orquestrador do pipeline
│   ├── recalcular_status_af.py     ← recalcula status de threads aguardando/finalizadas
│   └── paths.py                    ← configuração de caminhos
├── ferramentas_dev/                ← ferramentas de desenvolvimento — NÃO sobem ao servidor
├── templates/
│   ├── gestao_email.html           ← tela principal
│   └── gestao_login.html           ← tela de login
├── static/                         ← arquivos estáticos (CSS, JS, imagens)
├── config/
│   ├── categorias.py               ← configuração de categorias
│   └── regras_classificador_threads.json  ← regras de classificação de e-mails
├── documentações/                  ← documentação (spec, pendências, registro)
├── requirements.txt                ← dependências Python de produção
└── requirements-dev.txt            ← dependências só para testes locais
```

---

## Dados que precisam ser migrados manualmente

Estes arquivos **não sobem pelo git** (estão no `.gitignore`) mas precisam estar no servidor:

| Arquivo / Pasta | Tamanho | O que é |
|---|---|---|
| `data/registro_definitivo_threads.json` | ~328 KB | Banco principal de threads de e-mail |
| `data/json/config/` | ~85 KB total | Configurações do sistema (regras, clientes, usuários) |
| `data/json/consumo_api.json` | ~6 KB | Registro de uso da API |

**Não migrar:**
- `data/gestao.db` — o banco SQLite é gerado automaticamente pelo sistema na primeira execução
- `data/backups/` — backups locais de desenvolvimento
- `data/validacao_classificacao/` — artefatos de validação do classificador (dev only)
- `data/email_anexos/`, `data/chat_anexos/`, `data/fog_anexos/` — anexos (avaliar necessidade)

**Como migrar os dados:** copiar via SFTP ou SCP para o diretório do projeto no servidor.

---

## Dependências Python

```bash
pip install -r requirements.txt
```

O `requirements.txt` contém apenas os pacotes que o sistema usa em produção — limpo e enxuto desde 25/08/2026. O `requirements-dev.txt` é exclusivo para testes locais e não deve ser instalado no servidor.

---

## Logging (obrigatório antes do deploy)

O sistema atual não grava logs em arquivo — tudo vai para o terminal. Em produção isso impede diagnóstico remoto.

**Padrão definido por Michel:**
```
logs/
├── servidor_DD-MM-AAAA.log    ← acessos e erros do servidor Flask
├── coletor_DD-MM-AAAA.log     ← cada execução do robô de coleta
└── pipeline_DD-MM-AAAA.log    ← execuções do classificador
```
- Um arquivo por módulo por dia
- Data no formato brasileiro (DD-MM-AAAA)
- Rotação automática diária (Python `logging.handlers.TimedRotatingFileHandler`)
- Implementar em `servidor_telas.py`, `coletor_gmail.py` e `executar_pipeline.py`

---

## Como iniciar o servidor

```bash
cd gestao_area_suporte
python scripts/servidor_telas.py
```

O servidor sobe na porta definida em `PORT` (no PC, padrão **8004**). Não mandar localhost se não estiver no ar. Para rodar em produção, usar um processo manager (systemd, supervisor, ou o que o portal já usa).

---

## Ritual de deploy — quem executa: Claude (via SSH)

**Quando Michel disser "publicar", "publicar em produção" ou "atualizar a VPS"**, Claude executa os passos abaixo.
Nunca executar sem o OK explícito de Michel. Nunca pedir para Michel colar SSH.

### Pré-requisito
Commit + push na `main` já feito e confirmado por Michel.

### Comando típico (um bloco só)

```bash
ssh -o RequestTTY=no finaud-vps "export TERM=dumb
  sudo -u finaud-tec bash -lc 'cd /srv/finaud/tec/gestao_area_suporte && git checkout main && git pull origin main'
  systemctl restart gestao-suporte
  systemctl is-active gestao-suporte"
```

### Passo a passo detalhado

| Passo | O que fazer | Atenção |
|---|---|---|
| 1 | SSH via alias `finaud-vps` com `-o RequestTTY=no` | Nunca pedir para Michel colar o comando |
| 2 | `git checkout main && git pull origin main` como `finaud-tec` | Se o pull bloquear por arquivo local: mostrar o diff e **perguntar** — nunca apagar produção no escuro |
| 3 | Se `requirements.txt` mudou: `pip install -r requirements.txt` no venv do app | Este app é Flask — **não rodar npm build** |
| 4 | `systemctl restart gestao-suporte` | Se o relógio separado já estiver no ar: também `systemctl restart gestao-suporte-agendador` |
| 5 | Verificar: `systemctl is-active gestao-suporte` deve retornar `active` | Se não: `journalctl -u gestao-suporte -n 50` para diagnóstico |
| 6 | Abrir `https://gestao-suporte.finaudapps.com.br` e confirmar funcionando | Após "Sair": deve redirecionar para `https://finaudapps.com.br` — **não** para `/login` deste app |

> Michel faz Ctrl+F5 se a tela antiga persistir (cache do browser).

---

## Configuração no servidor (Hostinger VPS)

**Subdomínio aprovado:** `gestao-suporte.finaudapps.com.br`  
**Porta interna:** `8004` (sequência das outras apps Finaud: 8000–8003)  
**Roteiro completo:** `D:\03_Modelos_e_ferramentas\template_projeto_ai\roteiro_deploy_flask_vps_finaud.md`

### Parâmetros fixos do app

| Parâmetro | Valor |
|---|---|
| Subdomínio | `gestao-suporte.finaudapps.com.br` |
| Pasta no servidor | `/srv/finaud/tec/gestao_area_suporte` |
| Usuário Linux | `finaud-tec` (compartilhado com normativos e leiautes_bacen) |
| Serviço systemd (tela) | `gestao-suporte` |
| Serviço systemd (relógio) | `gestao-suporte-agendador` — `python scripts/executar_pipeline.py --agendar` |
| Callable Gunicorn | `servidor_telas:app` |
| WorkingDirectory systemd | `/srv/finaud/tec/gestao_area_suporte/scripts` |
| PYTHONPATH systemd | `/srv/finaud/tec/gestao_area_suporte/scripts` |
| Workers Gunicorn | `1` (pode permanecer 1) |
| Separar relógio da tela | No `.env` da tela: `GESTAO_AGENDADOR_EXTERNO=1`. Sem isso, a tela ainda liga o relógio sozinha (não para o e-mail no pull). |
| Autenticação Gmail | Service Account — não expira |

---

## Plano de limpeza antes do deploy

Executar em ordem — testar a aplicação após cada etapa antes de avançar.

| Etapa | O que fazer | Status |
|---|---|---|
| 0 | Criar este documento | ✅ Concluído (25/08/2026) |
| 1 | Mover credencial Gmail para `config/credenciais_gmail.json` | ✅ Concluído (25/08/2026) |
| 2 | Mover arquivos do Oráculo (bancos vazios) para `_archive/` | ✅ Concluído (25/08/2026) |
| 3 | Organizar raiz — requirements limpo, scripts avulsos arquivados | ✅ Concluído (25/08/2026) |
| 4 | Resolver duplicação `log/` vs `logs/` — unificar em `logs/` | ✅ Concluído (25/08/2026) |
| 5 | Arquivar `.env.example` — variáveis documentadas no DEPLOY.md | ✅ Concluído (25/08/2026) |
| 6 | Implementar logging em arquivo (padrão DD-MM-AAAA) | ✅ Concluído (25/08/2026) |
| 7 | Teste geral local — aplicação funcionando 100%? | ✅ Concluído (25/08/2026) |
| 8 | Deploy no servidor Hostinger | ✅ Concluído (25/08/2026) |

---

## Histórico

| Data | O que foi feito |
|---|---|
| 25/08/2026 | Documento criado — diagnóstico da estrutura atual |
| 25/08/2026 | Etapas 1–5 concluídas — estrutura limpa, credencial movida, requirements enxuto, `.env.example` arquivado |
| 25/08/2026 | Etapa 6 concluída — logging em arquivo implementado nos 3 scripts de produção; padrão DD-MM-AAAA |
| 25/08/2026 | Etapa 7 concluída — todas as telas testadas e funcionando; rotas mortas /fog/gerencial e /fog/operacional identificadas (código morto; removidas em 26/08/2026) |
| 25/08/2026 | Etapa 8 concluída — primeiro deploy no servidor Hostinger VPS; sistema acessível em https://gestao-suporte.finaudapps.com.br com SSL ativo |
