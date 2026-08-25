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
- Tela web acessada pelo time da Finaud em `localhost:5001` (local) ou no domínio do portal

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
GESTAO_SENHA=sua-senha-aqui
FOGBUGZ_TOKEN=seu-token-do-fogbugz-aqui
PORT=5001
```

| Variável | Descrição | Obrigatória |
|---|---|---|
| `SECRET_KEY` | Chave secreta do Flask — qualquer texto longo e aleatório | Sim |
| `GESTAO_EMAIL` | E-mail de login na tela web | Sim |
| `GESTAO_SENHA` | Senha de login na tela web | Sim |
| `FOGBUGZ_TOKEN` | Token da API do FogBugz — gerar em Configurações > API no FogBugz | Sim |
| `PORT` | Porta onde o servidor sobe (padrão: 5001) | Não |

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

O servidor sobe na porta definida em `PORT` (padrão 5001). Para rodar em produção, usar um processo manager (systemd, supervisor, ou o que o portal já usa).

---

## Como atualizar (após deploy inicial)

```bash
git pull origin main
# reiniciar o serviço (comando depende do servidor — ver seção abaixo)
```

---

## Configuração no servidor (Hostinger VPS)

> ⚠️ **Esta seção será preenchida por Michel com o passo a passo específico da Hostinger.**

```
[ espaço reservado para instruções do portal / Hostinger ]
```

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
| 6 | Implementar logging em arquivo (padrão DD-MM-AAAA) | ⏳ Pendente |
| 7 | Teste geral local — aplicação funcionando 100%? | ⏳ Pendente |
| 8 | Deploy no servidor com instruções do Michel | ⏳ Pendente |

---

## Histórico

| Data | O que foi feito |
|---|---|
| 25/08/2026 | Documento criado — diagnóstico da estrutura atual |
| 25/08/2026 | Etapas 1–5 concluídas — estrutura limpa, credencial movida, requirements enxuto, `.env.example` arquivado |
