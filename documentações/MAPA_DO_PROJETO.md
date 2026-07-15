# 🗺️ MAPA DO PROJETO — Oráculo 360 Finaud

> **Para que serve este arquivo:** é a "carteira de referência" do Gestor do Projeto. Responde rápido a:
> *o que o sistema faz, qual o fluxo, quais regras não se quebram e onde mora cada coisa.*
>
> Para **o estado de agora** (onde paramos), use `SESSAO_ATUAL.md`. Este Mapa é o "como tudo se encaixa".
>
> _Atualizado: 2026-06-26._

---

## 1. O que o sistema faz (em 30 segundos)

Sistema de **triagem regulatória de e-mails da Finaud**. Coleta e-mails (Gmail), chat (Google Chat) e
casos (FogBugz); identifica o que é exigência regulatória do BACEN (CADOC, prazos etc.); decide
automaticamente se cada conversa está **AGUARDANDO** ação ou **CONCLUÍDA**; e mostra tudo num painel web
(Flask, `localhost:5000`).

---

## 2. O fluxo do pipeline (scripts numerados)

| # | Script | O que faz |
|---|--------|-----------|
| 01 | `01_coletar_feriados_bancarios.py` | Atualiza calendário de feriados bancários (base para cálculo de prazos). |
| 02 | `02_coletar_emails_gmail.py` | Coleta e-mails do Gmail. **Etapa crítica** — se falhar, o pipeline para. |
| 03 | `03_corrigir_anexos_resposta_finaud.py` | Corrige anexos em respostas da Finaud. |
| 04 | `04_mapear_clientes.py` | Mapeia/descobre clientes por domínio. |
| 05 | `05_classificar_emails_regulatorio.py` | Classifica e-mails (CADOC, prazos). **LENTO (horas).** Não rodar para correções pontuais. |
| 06 | `06_coletar_chat_google.py` | Coleta Google Chat. |
| 07 | `07_abrir_casos_fogbugz.py` | Abre casos no FogBugz. |
| 08 | `08_coletar_fogbugz.py` | Coleta dados do FogBugz. |
| 09 | `09_integrar_dados_painel.py` | Integra tudo para o painel (gera o `03_integrador_dados_site.json`). |
| 10 | `10_resolver_threads_aguardando.py` | Resolve/atualiza threads aguardando. |
| 11 | `11_triar_threads_por_cadoc.py` | **Motor de triagem** → grava `threads_aguardando_auto.json` / `threads_concluidas_auto.json`. |
| 12 | `12_enriquecer_texto_imagens.py` | OCR de imagens/anexos (texto dentro de prints). |
| 13 | `13_correlacionar_threads.py` | Correlaciona threads relacionadas. |
| 14 | `14_sincronizar_indicios_qualidade_crd.py` | Sincroniza indícios de qualidade CRD. |
| 15 | `15_reprocessar_aprendizados_ia.py` | Reprocessa aprendizados de IA. |
| 16 | `16_resumir_retorno_bacen_llm.py` | Resume retorno do BACEN via LLM. |
| 17 | `17_alertar_recorrencias_bacen.py` | Alerta recorrências do BACEN. |
| 20 | `20_baixar_imagens_b1.py` | Baixa imagens B1 (uso pontual). |

**Carga normal (dia a dia):** `02 → 05 (com `ORACULO_INCREMENTAL=1`) → 09 → 11`.
O **motor de triagem** vive em `scripts/triagem/` (`motor.py`, `helpers.py` + um módulo por categoria:
`cadoc6209`, `ddr4111`, `dli`, `dlo`, `drm`, `drsac`, `forcapital`, `retorno_bacen`, `s5`, `suporte`).

---

## 3. Regras invioláveis (não quebrar nunca)

A fonte completa é o `CLAUDE.md`. Resumo:

- **Backup antes** de qualquer script que grava JSON do pipeline (com timestamp).
- **Checar `python executar_tudo.py --status`** antes de rodar qualquer script. Nunca usar
  `ORACULO_IGNORAR_DEPS=1` sem aprovação explícita.
- **Nunca rodar dois scripts do pipeline em paralelo** (corrompe os JSONs).
- **Ler `SESSAO_ATUAL.md` antes de tudo.**
- **Script 05 é lento (horas)** — para spam/correções pontuais, editar o JSON 02 e rodar 09+11.
- **Toda correção de regra segue o PROTOCOLO de 7 passos** (topo do `REGISTRO_CORRECOES.md`):
  Análise → Simular → Corrigir → **Varredura retroativa** → Validar dupla → Testes (pytest) → Registrar.

---

## 4. Onde mora cada coisa

| Item | Local |
|------|-------|
| Orquestrador do ciclo | `executar_tudo.py` (rodar com `--status` para ver dependências) |
| Painel web (Flask) | `painel_oraculo.py` → `localhost:5000` |
| Jobs do painel (carga/reprocessa) | `pipeline_jobs.py` |
| Pipeline | `scripts/01..17, 20` |
| Motor de triagem | `scripts/triagem/` |
| JSONs do pipeline | `data/json/pipeline/` (02 brutos, 03 integrador, threads_aguardando/concluidas_auto) |
| Templates do painel | `templates/` |
| Logs por execução | `logs/pipeline/AAAAMMDD_HHMM_carga.json` |
| Testes | `tests/` (`pytest`) |
| Material arquivado (histórico) | `_archive/` |

---

## 5. Os documentos do projeto — para cada pergunta, um lugar

> Este Mapa é o ponto de entrada. Cada documento abaixo tem uma função específica
> e aponta de volta para cá quando precisar de contexto geral.

---

### Estado e controle

| Pergunta | Documento |
|---|---|
| Onde paramos / qual é o próximo passo? | `SESSAO_ATUAL.md` |
| O que ainda falta fazer? | `documentações/PENDENCIAS.md` |
| O que já foi corrigido e por quê? | `documentações/REGISTRO_CORRECOES.md` |
| Quais tarefas rodam automaticamente (cloud)? | `documentações/TAREFAS_AGENDADAS.md` |

---

### Triagem automática

| Pergunta | Documento |
|---|---|
| Como o motor decide AGUARDANDO vs. CONCLUÍDO? | `documentações/DOCUMENTACAO_TRIAGEM.md` ← **principal** |
| Resumo rápido das regras R0–R9 por CADOC? | `documentações/GUIA_REGRAS_MOTOR_TRIAGEM.md` |
| Quais padrões de anexo existem e o que significam? | `documentações/PADROES_ANEXOS.md` |
| Matriz CADOC × lado × tipo de ação? | `documentações/MATRIZ_PADROES_CADOC.md` |
| Como o fluxo Finaud↔Cliente é capturado pelo sistema? | `documentações/ANALISE_FLUXO_FINAUD_CLIENTE.md` |

---

### Pipeline e dados

| Pergunta | Documento |
|---|---|
| O que cada script entrega para o próximo? | `documentações/CONTRATOS_PIPELINE.md` |
| Quais variáveis de ambiente o sistema usa? | `documentações/VARIAVEIS_AMBIENTE.md` |
| Como a IA trabalha neste projeto? | `CLAUDE.md` |

---

### Tela e painel

| Pergunta | Documento |
|---|---|
| O que é cada campo da tela operacional? De onde vem? Quais regras? | `documentações/GUIA_CAMPOS_OPERACIONAL.md` ← **guia definitivo campo a campo** |
| Quais tipos de e-mail aparecem na tela? Como cada um exibe? Exemplos reais? | [Demo interativa — Tipos de Mensagem (T1–T9c)](https://claude.ai/code/artifact/cc2f705c-a5bb-479f-bd0e-9ba601c8cedb) ← Campo 13 do Guia |
| De onde vem cada dado? Qual JSON? Qual script criou? | `documentações/LINHAGEM_DADOS_OPERACIONAL.md` ← **mapa de origem dos dados** |
| Revisão de UX das telas (olhar de usuário novo)? | `documentações/REVISAO_TELAS.md` |
| Validação campo a campo com dados reais de produção (diário de análise)? | `documentações/VALIDACAO_CAMPOS_TELA.md` |

---

### Para analistas da Finaud

| Pergunta | Documento |
|---|---|
| O que é o status "Aguardando" e como usar? | `documentações/GUIA_STATUS_AGUARDANDO.md` |
| Como qualquer pessoa entra no projeto do zero? | `documentações/GUIA_DO_PROJETO_IA.md` |

---

### Análises e referência

| Pergunta | Documento |
|---|---|
| Auditoria completa do pipeline (achados e riscos)? | `documentações/ANALISE_FABLE_PIPELINE.md` |
| Quando o Gmail cria dois fios para o mesmo caso? | `documentações/PARES_E_CLUSTERS_THREADID_DISTINTOS.md` |

---

> **Documentos gerados automaticamente** (não editar manualmente):
> `documentações/AUDITORIA_ULTIMACARGA_VALIDACAO.md` · `documentações/AUDITORIA_MENSAL_202606.md`
>
> **Candidatos a arquivar** (possivelmente desatualizados — verificar antes de usar):
> `documentações/DOCUMENTACAO_TECNICA.md` (mai/2026) · `documentações/MANUAL_TECNICO.md` (mai/2026) ·
> `documentações/GUIA_ORGANIZACAO.md` · `documentações/BASELINE_ARQUITETURAL.md`

---

## 6. Glossário rápido

- **AG / CO** — threads **AGUARDANDO** ação vs **CONCLUÍDAS**.
- **F→C / C→F / F→F / C→C** — quem mandou a última mensagem: Finaud→Cliente, Cliente→Finaud, etc.
  (usado pelo motor para decidir se a conversa ainda espera resposta).
- **CADOC** — código de documento regulatório do BACEN (ex.: 2061, 6209, DDR 4111).
- **Thread** — uma conversa de e-mail (sequência de mensagens com o mesmo assunto).
- **Motor** — a lógica de triagem automática (`scripts/triagem/`) que classifica AG vs CO.
- **Carga** — uma rodada de coleta+processamento (geralmente um dia novo de e-mails).
- **Integrador** — o JSON consolidado (`03_integrador_dados_site.json`) que alimenta o painel.

---

## 7. Versionamento (git/GitHub)

- **Remote:** `git@github.com:michelruicosta/oraculo_360_finaud.git` (SSH).
- **Branches:** `main` = estável; `desenvolvimento-front_end` = trabalho do dia a dia. **Nunca commitar direto na `main`.**
- **Regra de ouro:** commit = salvar no PC (reversível); push = enviar ao GitHub (sempre com o OK do usuário).
- **O que NÃO vai pro git** (já no `.gitignore`): `.env` e segredos, a pasta `data/` inteira, `logs/`,
  `venv/`, backups (`*.backup_*`) e scripts ad-hoc (`_*`). A pasta `.claude/` é ignorada, **exceto
  `.claude/commands/`** — os comandos do Gestor são versionados de propósito.
- **Padrão de mensagem:** `fix:`, `feat:`, `test:`, `refactor:`, `docs:` (+ escopo), em português.
- **Atalho:** `/salvar` mostra o que mudou, commita e pergunta antes de enviar.

---

## 8. Como rodar uma carga (passo a passo)

Sequência normal do dia a dia: **02 → 05 (INCREMENTAL) → 09 → 11**. Sempre fazer **backup antes** de cada
script que grava JSON (regra do `CLAUDE.md`) e **nunca rodar dois scripts em paralelo**.

```powershell
# 0. Sempre conferir dependências antes
python executar_tudo.py --status

# 1. Coletar e-mails novos
python scripts/02_coletar_emails_gmail.py

# 2. Classificar (só se houver e-mails novos) — INCREMENTAL é o modo normal (~20 min)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
Copy-Item "data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json" "data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json.backup_$ts"
$env:ORACULO_INCREMENTAL="1"
python scripts/05_classificar_emails_regulatorio.py

# 3. Integrar para o painel
$ts2 = Get-Date -Format "yyyyMMdd_HHmm"
Copy-Item "data/json/pipeline/03_integrador_dados_site.json" "data/json/pipeline/03_integrador_dados_site.json.backup_$ts2"
python scripts/09_integrar_dados_painel.py

# 4. Triagem automática (motor)
$ts3 = Get-Date -Format "yyyyMMdd_HHmm"
Copy-Item "data/json/pipeline/threads_aguardando_auto.json" "data/json/pipeline/threads_aguardando_auto.json.backup_$ts3"
Copy-Item "data/json/pipeline/threads_concluidas_auto.json" "data/json/pipeline/threads_concluidas_auto.json.backup_$ts3"
$env:ORACULO_CARGA_EM_CURSO="1"; $env:TRIAGEM_AUTO_DDR4111="1"
python scripts/11_triar_threads_por_cadoc.py
```

- ⚠️ Use `$env:ORACULO_INCREMENTAL="1"` no script 05 em cargas normais. Modo completo (sem INCREMENTAL)
  só após mudança de regras do motor.
- Após o script 11, o pipeline já exporta a base de conhecimento BACEN (etapa 11c) automaticamente.
- Script 05 é **lento (horas)** no modo completo. Para correções pontuais, editar o JSON 02 e rodar só 09+11.

---

## 9. Dependências entre arquivos — impactos em cascata
*Adicionado em: 2026-06-21*

> **Para que serve esta seção:** quando você (IA ou pessoa) muda algo num arquivo, esta seção mostra o que mais precisa ser verificado. Evita o problema de "consertei uma coisa e quebrei outra sem perceber."

### 9.1 Fluxo de dados (o que cada script lê e grava)

```
Script 02  →  grava:  data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json
Script 05  →  lê:     02_...
           →  grava:  02_... (enriquece com classificação CADOC)
Script 09  →  lê:     02_... + outros (Chat, FogBugz)
           →  grava:  data/json/pipeline/03_integrador_dados_site.json
Script 11  →  lê:     03_...
           →  chama:  scripts/triagem/motor.py  (que chama helpers.py e módulos por CADOC)
           →  grava:  data/json/pipeline/threads_aguardando_auto.json
                      data/json/pipeline/threads_concluidas_auto.json
Tela web   →  lê:     threads_aguardando_auto.json + threads_concluidas_auto.json
           →  exibe:  painel em localhost:5000
```

### 9.2 Tabela de impactos — se mudar X, verificar Y

| Se você mudar... | Impacta diretamente | Verificar também |
|---|---|---|
| `scripts/triagem/helpers.py` | `scripts/triagem/motor.py` | Todos os módulos por CADOC (`ddr4111.py`, `dlo.py`, etc.) · testes em `tests/test_triagem_*.py` · `DOCUMENTACAO_TRIAGEM.md` |
| `scripts/triagem/motor.py` | Script 11 (que chama o motor) | `threads_aguardando_auto.json` e `threads_concluidas_auto.json` · tela web · `DOCUMENTACAO_TRIAGEM.md` |
| Qualquer módulo de CADOC (`ddr4111.py`, `dlo.py`...) | `motor.py` e `helpers.py` que o chamam | Testes específicos daquele CADOC · `DOCUMENTACAO_TRIAGEM.md` seção do CADOC |
| `scripts/11_triar_threads_por_cadoc.py` | Os JSONs de saída (`threads_*.json`) | Tela web · `pipeline_jobs.py` (se carga via tela) |
| `scripts/09_integrar_dados_painel.py` | `03_integrador_dados_site.json` | Scripts 11, 13, 14, 15, 16 (todos leem o 03) · tela web |
| `scripts/05_classificar_emails_regulatorio.py` | `02_classificação_dados_brutos_gmail_editado.json` | Script 09 (lê o 02) |
| `scripts/02_coletar_emails_gmail.py` | `02_classificação_dados_brutos_gmail_editado.json` | Script 05 (lê o 02) |
| `painel_oraculo.py` (tela web) | Templates em `templates/` | `pipeline_jobs.py` · `GUIA_CAMPOS_OPERACIONAL.md` |
| `pipeline_jobs.py` | Cargas disparadas pela tela | Logs em `logs/pipeline/` · MEL-07 (scripts_status) |
| Regras de triagem (qualquer) | Motor + JSONs de saída | Backfill retroativo obrigatório · `DOCUMENTACAO_TRIAGEM.md` · testes |

### 9.3 Estrutura dos arquivos de dados
*Documentado em: 2026-06-21*

> Antes de ler campos de qualquer arquivo, verificar aqui. Se o arquivo não estiver listado, documentar a estrutura antes de usar (regra do `CLAUDE.md`).

#### `threads_aguardando_auto.json` e `threads_concluidas_auto.json`
Cada item = uma thread (conversa). Contém **resumo** — não o texto das mensagens.

| Campo | O que contém |
|---|---|
| `threadId` | ID único da conversa no Gmail |
| `assunto` | Título do e-mail |
| `empresa` | Nome da empresa cliente |
| `cadoc` | Código regulatório (ex.: DDR_2011) |
| `responsavel` | Responsável na Finaud |
| `motivo` | Por que está AGUARDANDO ou CONCLUÍDA |
| `data_marcacao` | Data da classificação |
| `prazo` | Prazo regulatório |
| `status` | AGUARDANDO / CONCLUÍDO |
| `origem_triagem_auto` | Status antes da triagem automática |
| `alvo_triagem_auto` | Status definido pela triagem automática |

> Para ler o **texto das mensagens**, usar `03_integrador_dados_site.json`.

---

#### `03_integrador_dados_site.json`
Arquivo consolidado que alimenta o painel.

**Como navegar:**
```python
j03 = json.load(open('data/json/pipeline/03_integrador_dados_site.json', encoding='utf-8'))
threads = j03['threads']           # lista de threads
idx = {t['threadId']: t for t in threads}  # índice por threadId (para cruzar com AG/CO)
msgs = thread['mensagens']         # lista de mensagens de uma thread
lado = msg['contato_origem']['lado']  # 'FINAUD' ou 'CLIENTE'
```
*Confirmado em 2026-06-26 — esse é o caminho correto. Não existe chave `eventos` no topo do arquivo.*

Cada item dentro de `mensagens` = uma mensagem.

**Campos de cada evento (mensagem):**

| Campo | O que contém |
|---|---|
| `threadId` | ID da conversa à qual pertence |
| `corpo_limpo` | Texto da mensagem sem HTML |
| `lado_responsavel` | Responsabilidade da **thread** (`"FINAUD"` ou `"CLIENTE"`) — **não** indica quem enviou |
| `contato_origem` | Quem **enviou**: `{lado, nome, email}` — usar `contato_origem.lado` para saber se é FINAUD ou CLIENTE |
| `contato_destino` | Quem **recebeu**: `{lado, nome, email}` |
| `cadoc` | Código regulatório |
| `data_iso` | Data da mensagem |
| `titulo` | Assunto do e-mail |
| `corpo` | Texto completo (HTML) |
| `texto_imagens` | Texto extraído de imagens via OCR |

> ⚠️ `lado_responsavel` ≠ quem enviou a mensagem. Para saber o remetente: `contato_origem.lado`.

---

### 9.4 Arquivos JSON críticos — backup obrigatório antes de modificar

| Arquivo | Modificado por | Backup antes de rodar |
|---|---|---|
| `02_classificação_dados_brutos_gmail_editado.json` | Scripts 02, 05 | Sim — sempre |
| `03_integrador_dados_site.json` | Script 09 | Sim — sempre |
| `threads_aguardando_auto.json` | Script 11 | Sim — sempre |
| `threads_concluidas_auto.json` | Script 11 | Sim — sempre |

---

## 10. Regras ativas por área — inventário simplificado
*Documentado em: 2026-06-26 | Atualizar quando uma regra mudar*

> Nível alto — suficiente para a IA entender o que cada área faz sem ir no código. Casos raros e detalhes específicos estão no próprio código.

### 10.1 Motor de triagem (script 11 → `scripts/triagem/`)

*Grupo: Globais → CONCLUÍDO (valem para todos os 10 CADOCs)*
| Regra | O que significa |
|---|---|
| R1 | Texto foi transmitido oficialmente ao BACEN |
| R2 | Finaud enviou o arquivo/documento para o cliente |
| R3 | Finaud respondeu com "RES:" — resposta formal |
| R4 | Finaud enviou texto conclusivo para o cliente |

*Grupo: Última mensagem Cliente→Finaud → CONCLUÍDO*
| Regra | O que significa | CADOCs com regra específica |
|---|---|---|
| R1 | Cliente agradeceu após Finaud enviar documento | Todos |
| R2 | Cliente disse "de acordo", "ok", "ciente" após instrução da Finaud | Todos |
| R3 | Cliente agradeceu sem fazer novo pedido | Só DDR4111 e SUPORTE |

*Grupo: Última mensagem Finaud→Cliente → AGUARDANDO*
| Regra | O que significa | CADOCs com regra específica |
|---|---|---|
| R1 | Finaud pediu documento ou informação ao cliente | Todos |
| R2 | Finaud só acusou recebimento — havia pergunta anterior | Todos |
| R3 | Finaud só agradeceu — sem pergunta anterior do cliente | Todos |
| R4 | Finaud mandou mensagem substantiva — aguarda retorno | DRM, SUPORTE, DRSAC, FORCAPITAL, 6209 |

*Grupo: Casos especiais → AGUARDANDO*
| Caso | O que significa |
|---|---|
| F→F | Mensagem interna entre colaboradores da Finaud |
| C→F | Cliente enviou documento — Finaud ainda não processou |

> ⚠️ Este inventário vai mudar após a unificação arquitetural dos 10 supervisores — ver PENDENCIAS.md "Revisão arquitetural".

---

### 10.2 Pipeline — classificação de e-mails (script 05)

| Regra | O que faz |
|---|---|
| Domínios a ignorar | E-mails de domínios na lista `dominios_a_ignorar` são descartados (spam, notificações) |
| Identificação de cliente | Primeiro e-mail externo válido fora do domínio Finaud = cliente |
| Detecção de CADOC | Texto varrido por padrões (DDR, DLO, DLI, DRM, DRL, 4111) para identificar o CADOC |
| Modo incremental | Se `ORACULO_INCREMENTAL=1`, reutiliza classificação anterior para e-mails fora do período atual |

---

### 10.3 Pipeline — integração para o painel (script 09)

| Regra | O que faz |
|---|---|
| CADOC vazio → categoria automática | Thread sem CADOC recebe categoria por contexto: FOGBUGZ, RISK_DRIVER_RELATORIO, RISK_DRIVER_ALERTA, LEIAUTES_BACEN, RISK_DRIVER_RESP_AUTO, SUPORTE |
| Responsabilidade da thread | Calculada por quem enviou a última mensagem (Finaud ou Cliente) |
| Prazos DLO | Só threads DLO_2061 têm prazos filtrados por regra de negócio |

---

### 10.4 Tela — exibição (painel_oraculo.py)

| Regra | O que faz |
|---|---|
| Autenticação | Só usuários logados acessam o painel |
| Cache de dados | JSONs carregados em cache — não relidos a cada clique |
| Cotação do dólar | Buscada via AwesomeAPI em tempo real |

---

### 10.5 Enriquecimento — OCR de imagens (script 12)

| Regra | O que faz |
|---|---|
| Filtro de tamanho | Imagens muito pequenas (logos/assinaturas) não passam pelo OCR |
| Prioridade de fonte | 1º texto do PDF pesquisável → 2º `.ocr.txt` manual → 3º OCR automático → 4º placeholder |
| Cache de OCR | Resultado gravado em `cache_texto_imagens_validado.json` — não reprocessa o que já foi feito |
| GIFs | Descartados — 100% são logos/assinaturas, sem conteúdo BACEN |

---

### 10.6 Correlação de threads (script 13)

| Regra | O que faz |
|---|---|
| Score mínimo e-mail↔e-mail | 65 pontos para considerar duas threads relacionadas |
| Score mínimo e-mail↔FogBugz | 25 pontos para correlacionar thread com caso FogBugz |
| Critérios de score | CADOC igual + cliente igual + período próximo + palavras relevantes em comum |

---

### 10.7 Alertas de recorrência (script 17)

| Regra | O que faz |
|---|---|
| Detecção de recorrência | Mesmo cliente + mesma crítica já alertada anteriormente = recorrência |
| Cross-cliente | Mesma crítica em clientes diferentes também gera alerta |
| Estado de alertas | Alertas já enviados ficam gravados — não envia duplicata |
| Destinatários | Configurados em `data/json/config/alertas.json` por tipo de alerta |

---

## 11. Scripts de consulta — use antes de investigar, não reescreva do zero

Pasta: `scripts/consultas/`

Estes scripts são **somente leitura** — não alteram nenhum dado. Use sempre que precisar investigar o sistema. Rodam nos dois ambientes (produção e teste).

> **Regra para toda IA:** antes de escrever um script de investigação novo, verificar se já existe um aqui. Reescrever do zero desperdiça tempo e arrisca usar a lógica errada.

| Script | O que faz | Quando usar |
|---|---|---|
| `diagnostico_cenarios_email.py` | Mapeia todos os cenários de e-mail (A, B1, B2/B3, B4, Finaud→Cliente, Interno) nos dois ambientes. Mostra quantos e-mails existem em cada cenário e quantos aparecem na tela. Aponta furos reais (e-mails fora da tela que deveriam estar). | Ao investigar se algum tipo de e-mail não está sendo capturado ou exibido corretamente |

**Como rodar:**
```powershell
python scripts/consultas/diagnostico_cenarios_email.py
```

**Nota técnica (para a IA, não para Michel):** o script usa `x_gm_thrid` como ID real da thread no Gmail — não o campo `threadId` do JSON 01, que para e-mails enviados pela Finaud pode conter o `message_id` no lugar do GMTHRID, causando falso "não encontrado".
