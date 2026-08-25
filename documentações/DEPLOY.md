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

| Variável | Descrição | Obrigatória |
|---|---|---|
| `SECRET_KEY` | Chave secreta do Flask (qualquer string longa e aleatória) | Sim |
| `GESTAO_EMAIL` | E-mail de login na tela web | Sim |
| `GESTAO_SENHA` | Senha de login na tela web | Sim |
| `FOGBUGZ_TOKEN` | Token da API do FogBugz (gerar em Configurações > API) | Sim |
| `PORT` | Porta onde o servidor sobe (padrão: 5001) | Não |

**Variáveis que NÃO são mais necessárias** (eram do Oráculo, não do Gestão):
`OPENAI_API_KEY`, `GEMINI_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASS`, `CHAT_CREDENTIALS_JSON`

---

## Arquivos que sobem pelo git (código)

```
gestao_area_suporte/
├── scripts/
│   ├── servidor_telas.py        ← servidor Flask (ponto de entrada)
│   ├── banco_threads.py         ← acesso ao banco de dados de threads
│   ├── classificador_regras.py  ← classificador de e-mails
│   ├── coletor_gmail.py         ← coleta de e-mails via Gmail API
│   ├── executar_pipeline.py     ← orquestrador do pipeline
│   └── paths.py                 ← configuração de caminhos
├── templates/
│   ├── gestao_email.html        ← tela principal
│   └── gestao_login.html        ← tela de login
├── static/                      ← arquivos estáticos (CSS, JS, imagens)
├── config/                      ← configurações do projeto
├── documentações/               ← documentação (spec, pendências, registro)
├── requirements.txt             ← dependências Python
└── .env.example                 ← modelo de variáveis de ambiente
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
- `data/oraculo360.db` — banco do Oráculo (outro projeto)
- `data/banco.db`, `data/oraculo.db`, `data/threads.db` — arquivos vazios (0 KB)
- `data/backups/` — backups locais de desenvolvimento
- `data/validacao_classificacao/` — artefatos de validação do classificador (dev only)
- `data/email_anexos/`, `data/chat_anexos/`, `data/fog_anexos/` — anexos (avaliar necessidade)

**Como migrar os dados:** copiar via SFTP ou SCP para o diretório do projeto no servidor.

---

## Dependências Python

```bash
pip install -r requirements.txt
```

⚠️ **Atenção:** o `requirements.txt` atual inclui pacotes pesados do período Oráculo (`torch`, `easyocr`, `selenium`, `scipy`). Após a limpeza, criar um `requirements-prod.txt` com apenas o que o sistema atual usa — isso reduz drasticamente o tempo de instalação e o espaço em disco.

**Pacotes que o sistema realmente usa hoje:**
`flask`, `flask-login`, `python-dotenv`, `requests`, `google-api-python-client`, `google-auth`, `apscheduler` (verificar scheduler), `Werkzeug`

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
| 0 | Criar este documento | ✅ Concluído |
| 1 | Mover `chave_app_coleta.oraculo@finaud.com.br.txt` para `_archive/arquivos_raiz/` | ⏳ |
| 2 | Mover arquivos do Oráculo (`oraculo-ia-coleta.json`, bancos vazios) para `_archive/` | ⏳ |
| 3 | Organizar raiz — remover bilhetes e scripts avulsos soltos | ⏳ |
| 4 | Resolver duplicação `log/` vs `logs/` — unificar em `logs/` | ⏳ |
| 5 | Atualizar `.env.example` — remover variáveis do Oráculo, manter só as 5 necessárias | ⏳ |
| 6 | Implementar logging em arquivo + criar `requirements.txt` de produção enxuto | ⏳ |
| 7 | Teste geral local — aplicação funcionando 100%? | ⏳ |
| 8 | Deploy no servidor com instruções do Michel | ⏳ |

---

## Histórico

| Data | O que foi feito |
|---|---|
| 25/08/2026 | Documento criado — diagnóstico da estrutura atual |
