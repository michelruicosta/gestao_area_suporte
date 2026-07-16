# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-07-13
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui (nunca o
contrário, para não perder histórico). Ver regra completa no `CLAUDE.md`.

---

## ═══════════════════════════════════════════════════════
## AMBIENTE TESTE — plano de correção em ordem de execução
## ═══════════════════════════════════════════════════════

> **Como usar este plano:** abra o chat na pasta `oraculo_360_finaud_TESTE`, execute os passos
> na ordem numérica. Cada passo tem o arquivo exato, a thread que revelou o bug e o que fazer.
> Ao concluir um passo: registrar no REGISTRO_CORRECOES.md e riscar aqui.

---

## FASE 1 — Corrigir os bugs (código e configuração)

---

### ~~Passo 1 — Remover "marco" do mapa de meses~~ ✅ CONCLUÍDO

**Problema:** a palavra "marco" (como em "marco relevante") estava mapeada como mês de março.
Qualquer email com essa palavra gerava uma data falsa de 31/03/XXXX — que era aceita como prazo.

**Thread que revelou o bug:** `GMTHRID_1869725950497986970` — newsletter "Conexão" do BACEN
(`comunicacao@comunicacao.bcb.gov.br`). O texto "marco relevante para a modernização" gerou
prazo falso de 31/03/2026→06/04/2026.

**O que fazer:**
- Arquivo: `scripts/05_classificar_emails_regulatorio.py`
- Linha: ~803
- Antes: `'mar': 3, 'março': 3, 'marco': 3,`
- Depois: `'mar': 3, 'março': 3,`
- Remover apenas `'marco': 3` — "mar" e "março" são abreviações corretas do mês

**Como validar:** buscar no texto "marco relevante" e confirmar que `extrair_todas_datas()` não retorna 31/03.

---

### ~~Passo 2 — Adicionar filtro para newsletter do Banco Central~~ ✅ CONCLUÍDO

**Problema:** a lista de remetentes a ignorar (`FILTROS_DE_IGNORAR`) está vazia. O endereço
`comunicacao@comunicacao.bcb.gov.br` é o boletim institucional do BACEN — não é um cliente —
mas passa pelo sistema como se fosse email regulatório.

**Thread que revelou o bug:** `GMTHRID_1869725950497986970` — newsletter "Conexão" do BACEN,
assunto "Conexão | nº 58 | julho 2026". Classificada incorretamente como DDR_2011.

**O que fazer:**
- Arquivo: `data/json/config/mapeamento_regras_negocio.json`
- Campo: `FILTROS_DE_IGNORAR.por_conteudo_especifico`
- Antes: `[]`
- Depois: `["comunicacao@comunicacao.bcb.gov.br"]`

**Como validar:** rodar Script 05 sobre a thread "Conexão" e confirmar `cadoc = IGNORADO`.

---

### ~~Passo 3 — Corrigir prazo padrão do RETORNO_BACEN de D+5 para D+3~~ ✅ CONCLUÍDO

**Problema:** quando o BC rejeita um relatório sem informar prazo explícito no email, o sistema
usa D+5 dias úteis como fallback. Michel confirmou que o prazo correto é D+3 dias úteis.

**Thread que revelou o bug:** Auditoria #12 — identificado na verificação do arquivo de config.
Thread de referência: Intra Investimentos (#07) — email de rejeição do BC sem prazo explícito.

**O que fazer:**
- Arquivo: `data/json/config/mapeamento_regras_negocio.json`
- Buscar: `D+5_UTIL` na seção `RETORNO_BACEN`
- Trocar por: `D+3_UTIL`
- Verificar se `D+3_UTIL` já existe no calculador de prazos do Script 05 (se não existir, adicionar)

**Como validar:** conferir que threads de RETORNO_BACEN sem prazo explícito mostram D+3 na tela.

---

### ~~Passo 4 — Incluir nome dos anexos na detecção de CADOC~~ ✅ CONCLUÍDO

**Problema:** o Script 05 detecta o CADOC do email usando apenas o assunto + corpo do texto.
O nome dos arquivos anexados não entra nessa busca. Emails com assunto genérico mas nome de
arquivo descritivo são classificados como SUPORTE.

**Thread que revelou o bug:** Auditoria #08 — TC/Economatica, assunto "Saldos do dia 29 e 30/06",
anexo `Saldos 4111.xlsx`. O sistema classificou como SUPORTE porque "4111" só aparecia no nome
do arquivo, não no assunto nem no corpo.
- Buscar no JSON 01 por: `assunto` contendo "Saldos do dia" + remetente TC/Economatica

**O que fazer:**
- Arquivo: `scripts/05_classificar_emails_regulatorio.py`
- Função: `processar_email()` — onde monta `texto_completo = assunto + corpo` (linha ~1943)
- Adicionar: concatenar os `nome_original` de cada item em `anexos_detectados` ao `texto_completo`
- Exemplo: `texto_completo = f"{assunto} {corpo} {' '.join(a['nome_original'] for a in anexos)}`

**Também:** adicionar `4111` no cadastro da TC em `data/json/config/cadastro_clientes_cadoc.json`.

**Como validar:** processar a thread da TC e confirmar `cadoc = 4111` (não SUPORTE).

---

### ~~Passo 5 — Refinar regra "Balancete de Câmbio" para DDR_2011~~ ✅ CONCLUÍDO

**Problema:** a regra `#PF30` do Script 05 classifica qualquer email com "balancete" no assunto
como DLO_2061. "Balancete de Câmbio" é um documento específico do DDR_2011 (não do DLO).

**Thread que revelou o bug:** Auditoria #29 — Western Union (Jair Bonetti), assunto:
"Posição de Câmbio CAM0050 BACEN, Balancete de Câmbio PDF/Excel - BANCO 02/07/2026".
Classificado como DLO_2061 — correto seria DDR_2011.
- Buscar no JSON 01 por: `remetente` Western Union ou `assunto` contendo "Balancete de Câmbio"

**O que fazer:**
- Arquivo: `scripts/05_classificar_emails_regulatorio.py`
- Localizar a regra `#PF30` (buscar por `balancete` no arquivo)
- Antes: qualquer "balancete" → DLO_2061
- Depois: "balancete de câmbio" (com "câmbio" junto) → DDR_2011 | "balancete" sem "câmbio" → DLO_2061

**Como validar:** processar a thread da Western Union e confirmar `cadoc = DDR_2011`.

---

### ~~Passo 6 — Detectar consultas sobre normas e forçar SUPORTE~~ ✅ CONCLUÍDO

**Problema:** quando um cliente pergunta sobre como uma norma afeta o preenchimento de um
relatório (ex.: "como preencher o DRL após a nova IN BCB nº 755?"), o sistema detecta "DRL"
e "2160" e classifica como DRL_2160. O correto é SUPORTE — é uma dúvida, não um envio.

**Thread que revelou o bug:** Auditoria #32 — Terra Investimentos (Mayara), perguntou sobre
impacto da Instrução Normativa BCB nº 755 no preenchimento do DRL 2160.
- Buscar no JSON 01 por: remetente Terra Investimentos ou assunto contendo "Instrução Normativa"

**O que fazer:**
- Arquivo: `scripts/05_classificar_emails_regulatorio.py`
- Antes de atribuir um CADOC regulatório, verificar se o assunto contém padrões de consulta:
  "norma", "instrução normativa", "IN BCB", "dúvida", "impacto", "mudança", "atualização"
- Se sim → forçar `cadoc = SUPORTE`, independente do CADOC mencionado
- Ou: adicionar esses termos como `termos_exclusivos` que bloqueiam a detecção do CADOC

**Como validar:** processar a thread da Terra e confirmar `cadoc = SUPORTE` com prazo D+3.

---

~~Passo 7 — Fallback de data: usar data do email quando não há data no arquivo~~ ✅ CONCLUÍDO (2026-07-07 — ver REGISTRO_CORRECOES.md)

---

~~Passo 8 — Regra de prioridade: RETORNO_BACEN prevalece sobre outros CADOCs na thread~~ ✅ CONCLUÍDO (2026-07-07 — varredura do JSON 02 confirmou 0 threads afetadas; ampliação da detecção no Passo 8 Parte 1 resolveu o problema na raiz; ver REGISTRO_CORRECOES.md)

---

~~Passo 9 — Investigar: anexo XML não foi capturado pelo Script 02~~ ✅ CONCLUÍDO (2026-07-07 — ver REGISTRO_CORRECOES.md)

⚠️ **Pendência derivada:** implementar alerta `conteudo_incompleto = True` quando corpo menciona "em anexo" mas `anexos_detectados: []` — registrado como item separado abaixo.

---

~~Passo 10 — Investigar: email enviado por colaborador não capturado~~ ✅ CONCLUÍDO (2026-07-07 — ver REGISTRO_CORRECOES.md)

---

~~🔴 URGENTE — Verificar leitura do conteúdo dos anexos (pós-validação Fase 1)~~ ✅ CONCLUÍDO (2026-07-07 — confirmado: sistema não lê conteúdo interno; Script 02 baixa arquivos para `data/anexos/`; Script 05 usa nome do arquivo mas não abre; limitação conhecida documentada no REGISTRO_CORRECOES.md)

---

### Padrões de anexos como condições de triagem (melhorias futuras)

**Contexto:** mapeamento completo dos 9 padrões de anexos feito em 07/07/2026 — ver `documentações/PADROES_ANEXOS.md`.

**O que implementar (prioridade a definir com Michel):**

1. **Padrão A → CONCLUÍDO automático:** quando a Finaud envia ZIP no padrão BACEN (`CNPJ_CADOC_DATA_I/D_versao.zip`) em um email da Finaud (`lado = FINAUD`) → marcar thread como CONCLUÍDO automaticamente.
   - Arquivo alvo: `scripts/triagem/motor.py` ou supervisor de cada CADOC
   - Validar: não disparar para emails do CLIENTE com mesmo padrão (Padrão C)

2. **Padrões C/D/E/E2/F/H → AGUARDANDO:** quando o cliente envia um arquivo reconhecível (dados financeiros, template da Finaud preenchido, COSIF, retorno CRD) → pode ser usado para confirmar que a pendência ainda está em aberto.
   - Uso mais sutil: evidência de que o cliente está cooperando mas ainda aguarda ação da Finaud

3. **Extração de data do nome do arquivo (Padrão A/B):** ZIP com `DATA` no nome (`CNPJ_CADOC_YYYYMMDD_...`) ou ZIP Amaril Franklin (`DDMMYYYY.zip`) → extrair data de competência do nome antes de usar fallback de data do email.
   - Arquivo alvo: `scripts/05_classificar_emails_regulatorio.py`

**Próximo passo sugerido:** implementar item 1 (mais alto valor, mais direto). Discutir com Michel antes.

---

## FASE 2 — Corrigir os dados do TESTE (após Fase 1 concluída)

---

### ~~Passo 11 — Corrigir manualmente thread "Conexão" no JSON 02~~ ✅ CONCLUÍDO (2026-07-07 — Passo 2 (filtro BACEN) corrigiu automaticamente ao reprocessar via Fase 2)

**Problema:** o JSON 02 ainda tem `cadoc=DDR_2011` e prazos falsos para a newsletter do BACEN.
O Script 05 em modo incremental não reprocessa threads já classificadas — correção manual necessária.

**Thread:** `GMTHRID_1869725950497986970` em `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json`

**O que fazer:**
1. Fazer backup: `data/json/pipeline/backups/AAAAMMDD_HHMM_correcao_conexao/` com CONTEXTO.md
2. Editar o JSON 02: localizar `GMTHRID_1869725950497986970`
   - `cadoc` → `"IGNORADO"`
   - `prazos` → `[]`
   - `exibir_card` → `false`

---

### ~~Passo 12 — Reprocessar todos os dados do TESTE do zero~~ ✅ CONCLUÍDO (2026-07-07 — pipeline completo 01→16 rodado pela tela; backup em `20260707_1742_pre_fase2_reprocessamento/`)

---

### ~~Passo 13 — Validar as 9 correções thread por thread~~ ✅ CONCLUÍDO (2026-07-07 — todas validadas; ver REGISTRO_CORRECOES.md entrada 2026-07-07 Fase 2)

---

## FASE 3 — TESTE vira nova produção

---

### Passo 14 — Inicializar git no TESTE e conectar ao GitHub

**Por que:** a produção antiga tem histórico de coleta incompleto (conta `luiz.antonio` não
capturava emails dos colaboradores como Andrea). Com a nova conta `coleta.oraculo`, a coleta
começa limpa a partir de 03/07/2026. O TESTE, após os fixes, é o sistema correto.

**O que fazer:**
1. `git init` na pasta `oraculo_360_finaud_TESTE`
2. Criar repositório novo no GitHub (ex.: `oraculo_360_finaud`) ou reutilizar o existente em branch nova
3. Commit inicial com mensagem: `feat: sistema limpo com coleta via coleta.oraculo a partir de 03/07/2026`
4. Definir com Michel: o repositório GitHub antigo fica arquivado ou é substituído?

---

### Passo 15 — Configurar rotinas automáticas no TESTE

Após o git estar funcionando:
- Ativar pre-commit hook: `git config core.hooksPath .githooks`
- Verificar `executar_tudo.py --status` para confirmar dependências do pipeline
- Agendar próxima carga pelo painel

---

> **Atenção ao executar:** sempre seguir a ordem dos passos. Passos 1–10 são independentes entre
> si (podem ser feitos em qualquer ordem dentro da Fase 1), mas a Fase 2 só começa depois que
> todos os passos da Fase 1 estiverem concluídos. A Fase 3 só começa depois da Fase 2 validada.

---

## ═══════════════════════════════════════════════════════
## PRODUÇÃO — pendências do sistema principal (secundárias — foco atual é o TESTE)
## ═══════════════════════════════════════════════════════

---

## 🟡 Auto-cadastro de empresas e colaboradores (2026-07-08)

**Contexto:** levantado durante a validação campo a campo da tela operacional — campos `empresa` e `colaborador` nunca preenchidos no JSON.

**Regra definida com Michel:**
- Quando chega um e-mail de domínio desconhecido → sistema cadastra automaticamente a empresa (nome derivado do domínio) + adiciona o colaborador (nome + e-mail)
- Dispara **notificação na tela** para Michel confirmar ou corrigir o nome da empresa
- Quando o domínio já existe no cadastro → adiciona o colaborador silenciosamente (sem notificação)
- O cadastro (`cadastro_clientes_cadoc.json`) é a **fonte oficial** do nome da empresa

**Regra de exibição na tela:**
- Finaud envia → mostra colaborador da Finaud + empresa "Finaud"
- Cliente envia → mostra colaborador da empresa cliente + nome da empresa cliente

**Novos colaboradores Finaud a cadastrar (imediato):**
- `miguel.santos@finaud.com.br`
- `sarah.sa@finaud.com.br`

**O que implementar:**
1. Script 09 (ou Script 06): detectar domínio do remetente, consultar cadastro, cadastrar empresa/colaborador automaticamente
2. Painel: tela de notificações para confirmação/correção de empresas novas
3. Campo `empresa` passar a ser preenchido sempre (via cadastro)
4. Campo `colaborador` passar a ser preenchido com nome + e-mail do remetente

**Arquivos:** `scripts/09_integrar_dados_painel.py`, `data/json/config/cadastro_clientes_cadoc.json`, `painel_oraculo.py` (notificações)

---

## ✅ Arquitetura — tela consulta múltiplos arquivos ao vivo em vez de ler JSON pronto (2026-07-08)
**Resolvido em 2026-07-08** — campo `empresa` movido para Script 09. Ver REGISTRO_CORRECOES.md entrada 2026-07-08 22:03.

<!--

**Contexto:** identificado durante a validação campo a campo da tela operacional.

**Problema:** o painel (`painel_oraculo.py`) consulta `cadastro_clientes_cadoc.json` na hora de servir os dados para a tela, para enriquecer o campo `empresa` com o nome oficial da empresa. Isso significa que a tela não apenas lê o JSON — ela também faz lookups em outros arquivos a cada carregamento.

**Por que é errado:** a tela deveria apenas consumir o que já está pronto no JSON. Carregar dados de múltiplos arquivos ao vivo torna o sistema mais lento, mais difícil de entender e mais fácil de quebrar silenciosamente.

**Correção:** mover a resolução do campo `empresa` para o Script 09 (`09_integrar_dados_painel.py`): na hora de montar o evento, consultar `cadastro_clientes_cadoc.json`, resolver o nome oficial da empresa pelo e-mail ou domínio do cliente, e já gravar `empresa` no `03_integrador_dados_site.json`. A tela passa a ler o campo pronto, sem consulta adicional.

**Arquivos envolvidos:**
- `scripts/09_integrar_dados_painel.py` — adicionar a lógica de resolução de `empresa`
- `painel_oraculo.py` — remover a função `_enriquecer_threads_com_empresa` e suas chamadas
- `data/json/pipeline/03_integrador_dados_site.json` — passará a ter o campo `empresa` preenchido
-->

---

## 🟡 Campo 10 — Responsável pela ação: 55 threads divergem entre tela e JSON (registrado 13/07/2026)

**Contexto:** durante a documentação do Campo 10, comparamos o valor mostrado na tela (`responsavel_pela_acao`, calculado na hora pelo painel) com o valor gravado no JSON 03 (`responsavel`, calculado pelo Script 09). São 55 threads com resultados diferentes.

**Causa raiz:** as duas funções ordenam as mensagens de formas diferentes para achar a "última":
- `_responsavel_pela_acao()` no Script 09 → ordena por `timestamp_epoch` (número)
- `_responsavel_pela_acao_from_mensagens()` no painel → ordena por `data_email`/`data_iso`/`timestamp` (campos de texto)

Quando uma mensagem tem `timestamp_epoch` zero ou ausente mas tem a data em texto, cada função escolhe uma mensagem diferente como "última" — e o responsável muda.

**Impacto:** a tela mostra o valor do painel (runtime), que para 55 threads é diferente do que está gravado no JSON 03. Ou seja, o que aparece na tela para essas threads não bate com o arquivo.

**O que fazer:** unificar o critério de ordenação nas duas funções. O mais confiável é usar `timestamp_epoch` quando disponível, com fallback para `data_iso`/`data_email` — assim as duas funções encontram sempre a mesma "última mensagem".

**Arquivos:**
- `scripts/09_integrar_dados_painel.py` — função `_responsavel_pela_acao()` (~linha 82)
- `painel_oraculo.py` — função `_ordenar_mensagens_operacional_para_acao()` (~linha 2212)

**Quando fazer:** junto com a limpeza arquitetural de mover `responsavel_pela_acao` para o JSON (item já registrado neste arquivo, seção "Arquitetura — cálculos feitos na hora de servir").

---

## 🟡 Campo "Cliente" — bugs identificados na validação de campos (2026-07-08)

**Contexto:** levantado durante a validação campo a campo da tela operacional (`VALIDACAO_CAMPOS_TELA.md`).

### Bug A — Alias de departamento capturado como nome de cliente
**Problema:** quando a empresa usa um email de departamento como remetente (`compliance@empresa.com.br`, `financeiro@empresa.com.br`, `risco@empresa.com.br`), o sistema exibe o alias ("compliance", "Financeiro", "risco") em vez do nome da empresa — impossível saber de qual cliente se trata.
**Casos confirmados em produção:** 20 threads — Oliveira Trust, Monopólio, Atual Câmbio, Accredito SCD, Trustee DTVM, Carol DTVM, BR Capital DTVM, Traders DTVM.
**Correção:** cadastrar os emails de alias em `data/json/config/cadastro_clientes_cadoc.json` mapeando para o nome correto da empresa.
**Arquivo:** `data/json/config/cadastro_clientes_cadoc.json`

### ~~Bug B — Campo CC/Reply-To capturado como nome de cliente~~ ⚠️ NÃO CONFIRMADO

**Investigado em 09/07/2026:** varredura completa de 8.825 e-mails de produção não encontrou nenhum caso com o padrão descrito (`cc:` ou `responder a:` no nome do contato). A regra do Reply-To no Script 05 está funcionando corretamente — ela só é acionada para e-mails recebidos pelo grupo `suporte@finaud.com.br` (1.603 casos confirmados), que é o comportamento esperado.

**ECSA:** Adriana Martins é da Açoriana Corretora (`adm@acorianacorretora.com.br`) — e-mail diferente do domínio ECSA. Não é problema de Reply-To.
**Unicred / UY3:** clientes identificados corretamente nos dados de produção.

**Conclusão:** o Bug B foi documentado como "confirmado em produção" sem verificação nos dados. Não há correção necessária no código. Item encerrado.

### Bug C — Cliente DESCONHECIDO sem alerta
✅ **Resolvido em 2026-07-08** — alerta `cliente_desconhecido` adicionado ao sistema de notificações (`alertas.json` + `painel_oraculo.py`). Ver REGISTRO_CORRECOES.md entrada 2026-07-08 17:00.

---

## 🟡 Arquitetura — cálculos feitos na hora de servir que deveriam estar no pipeline (2026-07-08)

**Contexto:** identificado durante o mapeamento de linhagem de dados da tela operacional.

**Problema:** a tela faz dois cálculos que deveriam estar prontos no JSON 03:
- `empresa`: o Script 09 já tenta resolver, mas o `painel_operacional_snapshot.py` refaz o cálculo na hora de servir, usando `cadastro_clientes_cadoc.json` e `rotulos_empresa_gestao.json`
- `responsavel_pela_acao`: calculado a cada requisição relendo o array `mensagens` do JSON 03 — não está gravado no arquivo

Não está quebrado — funciona. Mas dificulta manutenção (quando algo dá errado, não se sabe se o problema está no Script 09 ou no painel) e pode causar lentidão em cargas grandes.

**O que fazer:**
1. Mover a resolução completa de `empresa` para o Script 09 — incluindo as regras de `rotulos_empresa_gestao.json`
2. Pré-calcular `responsavel_pela_acao` no Script 09 e gravar no JSON 03
3. Remover a lógica duplicada do `painel_operacional_snapshot.py`

**Arquivos:** `scripts/09_integrar_dados_painel.py`, `scripts/painel_operacional_snapshot.py`, `painel_oraculo.py`
**Quando fazer:** na revisão de enxugamento da aplicação — não é urgente.

---

## 🔴 Tela de Triagem — revisão UX com o Fable (registrado 2026-07-02)

**Contexto:** após concluir a revisão do Painel de Gestão (2ª rodada), Michel quer revisar a tela de Triagem (`/operacional`) — o coração do sistema, onde os analistas trabalham o dia inteiro.

**Diagnóstico inicial do Michel:** a tela está "muito poluída". É uma tela densa e precisa de atenção especial.

**Fluxo acordado:**
1. Abrir nova sessão dedicada à Triagem
2. Michel e IA revisam a tela juntos ao vivo (como usuário novo que nunca viu o sistema)
3. IA condensa o diagnóstico e contextualiza para o Fable
4. Fable ajusta a tela com base no briefing

**Arquivos relevantes:**
- Tela: `templates/email_operacional.html`
- Backend: `painel_oraculo.py` (endpoint `/api/triagem_motivos` e relacionados)
- Rota: `/operacional`

**Atenção:** é o coração do sistema — mudanças visuais podem afetar o fluxo dos analistas. Revisar com cuidado antes de qualquer alteração.

---

## 🔴 CORREÇÕES DA ANÁLISE FABLE — Pacote 1: falhas silenciosas (registrado 02/07/2026)

**Origem:** auditoria completa do pipeline — ver `documentações/ANALISE_FABLE_PIPELINE.md` (seções 3A e 4).

6 correções pequenas e de baixo risco, para 1 sessão dedicada:
- **S-03** disjuntor único do motor: try/except gigante em volta de TODAS as regras do pós-processamento (`scripts/triagem/motor.py:643-1062`) — trocar por proteção por regra + falha visível
- **S-04** normativo perdido em falha de IA: script 07 registra e-mail como processado mesmo quando a IA falha — não registrar, para reprocessar na próxima carga
- **S-05** coletas 06/08 fingindo sucesso: erro crítico engolido com print e exit 0 — re-levantar exceção
- **S-01** `datetime` sem import no script 02 (linha 373) — o backup de JSON corrompido quebra ao ser acionado
- **S-02** retomada por checkpoint do 05 perde os e-mails anteriores à interrupção — recarregar o JSON parcial na retomada
- **S-07** anexo entra em `anexos_baixados` (script 08) mesmo com download falho — mover append para dentro do if de sucesso

---

## 🟡 CORREÇÕES DA ANÁLISE FABLE — Pacote 2: responsabilidades (executar junto com a padronização de categorias)

**Origem:** `ANALISE_FABLE_PIPELINE.md` seções 3B e 4. **Depende de decisões do Michel:**
- **R-04** motor grava `origem_triagem_auto=False` em registros automáticos ("protege de re-triagem") — criar campo próprio (nome a aprovar) e devolver o significado real ao campo; exige backfill com backup
- **R-01** arquivo de triagem tem 4 escritores (11/motor, 09, 15, painel) — escrever o contrato de quem pode tocar em qual campo no MAPA_DO_PROJETO
- **R-07** todo CO recebe `regra="R1"` (decisão documentada) — decidir: gravar a regra real ou documentar que R1 = "concluído"
- **R-02** script 03 apaga anexos do JSON 01 sem deixar rastro — marcar em vez de apagar
- **R-03** script 04 escreve domínios descobertos em arquivo de CONFIG — mover para arquivo próprio em pipeline/
- **R-08** `clientes_externos` duplicado no mapeamento_regras_negocio.json — verificar leitores e eliminar um

---

## 🟡 CORREÇÕES DA ANÁLISE FABLE — Pacote 4: padronização e faxina (pode ser fatiado em sessões curtas)

**Origem:** `ANALISE_FABLE_PIPELINE.md` seções 3D/3E e 4:
- **P-08** backups soltos fora do padrão do projeto + bug: script 04 grava `.backup_04` mas a recuperação lê `.backup` (nunca acha)
- **P-10** paths.py ainda lista script 10 (removido) e não lista 17/20
- **P-11** docstrings desatualizados (11 e executar_tudo falam de arquivos _manual; 15 cita "script 10"; 07 diz OpenAI mas usa Gemini + client morto)
- **P-13** `_PyccFinder` (carrega .pyc sem .py) — muleta da bomba-relógio, hoje código morto perigoso
- **S-13** ALERTAS_REGRESSAO.json: 12,6 MB, 1.009 alertas, nenhum leitor — criar rotação e consumo (aviso no painel ou /iniciar)
- **S-11** retornos precoces sem `registrar_execucao` (03/06/07/08)
- **P-06** prazo fixo no código (30/11/2025→05/01/2026, DLO/B3) — documentar dono/validade ou remover
- **P-09** `scripts_status` do painel via parsing de stdout — unificar em pipeline_estado.json
- **P-12/P-14/P-15** imports antes da docstring (17/20) · logs em 3 estilos · formato canônico de datas por camada

---

## 🔵 CORREÇÕES DA ANÁLISE FABLE — Pacote 3: performance (sessão dedicada; casa com o backlog ijson)

**Origem:** `ANALISE_FABLE_PIPELINE.md` seções 3C e 4. **Mexe em contratos do painel — só com simulação e OK:**
- **P-01** corpos de e-mail em triplicata nos JSONs 01/02/03 (1,4 GB) — definir política de armazenamento único; estimativa de redução 40–60%
- **P-04** ijson no motor (já no backlog — unificar com este item)
- **P-02** salvamento progressivo regrava o JSON inteiro a cada 50/200 e-mails
- **P-05** duas rotinas divergentes de limpeza de corpo (05 e 09) — unificar num módulo

---

## 🟡 PLANEJADO — Padronização de categorias do pipeline (registrado 2026-07-02)

**Contexto:** durante a revisão do Painel de Gestão (item 2-I), mapeamos o problema de categorias
inconsistentes e chegamos às decisões abaixo. A implementação depende da análise Fable acima
(violação de responsabilidades) para garantir que a correção seja feita no lugar certo.

**Decisões já tomadas pelo Michel:**

1. **Fonte da verdade:** o Script 05 é quem define a categoria — os scripts seguintes apenas
   carregam. O supervisor (Script 11) define AGUARDANDO/CONCLUÍDO + motivo, não a categoria.

2. **Catálogo oficial de nomes** — códigos numéricos onde existem:

| Hoje no sistema | Código/nome oficial | Visível no painel |
|---|---|---|
| DDR_2011 | **2011** | sim |
| DRL_2160 | **2160** | sim |
| DLO / DLO_2061 | **2061** | sim |
| DLI / DLI_2062 | **2062** | sim |
| DRM_2060 | **2060** | sim |
| DRSAC | **2030** | sim |
| 4111 | **4111** | sim |
| S5 | **S5** | sim |
| RETORNO_BACEN | RETORNO_BACEN | sim |
| LEIAUTES_BACEN | LEIAUTES_BACEN | sim |
| SUPORTE | SUPORTE | sim |
| FORCAPITAL | FORCAPITAL | sim |
| FOGBUGZ | FOGBUGZ | **não** |
| RISK_DRIVER_ALERTA | RISK_DRIVER_ALERTA | **não** |
| RISK_DRIVER_RELATORIO | RISK_DRIVER_RELATORIO | **não** |
| RISK_DRIVER_RESP_AUTO | RISK_DRIVER_RESP_AUTO | **não** |

3. **Supervisores separados:** o supervisor `ddr4111.py` (que hoje agrupa 2011 + 4111 + 2160)
   deve ser dividido em três supervisores distintos — um por CADOC. Nomes propostos:
   `triagem_2011.py`, `triagem_4111.py`, `triagem_2160.py` (aguardam aprovação do Michel).
   Os demais supervisores com código numérico: `triagem_2061.py`, `triagem_2062.py`,
   `triagem_2060.py`, `triagem_2030.py`.

4. **Arquivo de configuração de visibilidade:** criar `config/categorias.py` com o catálogo
   acima — define nome oficial + se aparece nas páginas. O painel lê esse arquivo.

**O que fazer (após análise Fable):**
- Corrigir Script 05 para escrever os códigos numéricos no campo `cadoc`
- Criar novos supervisores separados
- Atualizar Script 11 para chamar os novos supervisores
- Atualizar `cadastro_clientes_cadoc.json`
- Backfill das 4.737 threads existentes
- Criar `config/categorias.py`
- Atualizar `painel_oraculo.py` para usar o catálogo

---

## 🔵 BACKLOG — Habilitar re-triagem completa sem limite de memória (registrado 30/06/2026)

**Problema identificado:** o script 11 (`11_triar_threads_por_cadoc.py`) carrega o arquivo
`03_integrador_dados_site.json` (389 MB) inteiro na memória via `json.load()` antes de qualquer
filtro. Em re-triagem completa (sem `data_ref`), isso causa `MemoryError` na máquina atual.

**Impacto:** não conseguimos rodar re-triagem histórica completa (backfill de regras novas sobre
todas as threads). Workaround atual: correção cirúrgica direta nos JSONs de AG/CO.

**Solução proposta: ijson (streaming JSON)**
Trocar o `json.load(f)` em `motor.py → precarregar_dados_03()` por leitura via `ijson`,
que processa o arquivo linha a linha sem carregar tudo na memória.

**O que fazer:**
1. `pip install ijson` no venv
2. Reescrever `precarregar_dados_03()` em `scripts/triagem/motor.py` para usar `ijson.items()`
3. Validar que o motor funciona igual em carga normal (pytest + carga de teste)
4. Testar re-triagem completa sem `data_ref` — deve rodar sem MemoryError

**Alternativa mais simples (lotes por CADOC):** criar script de backfill que carrega só
as threads de um CADOC por vez — sem mexer no motor, mas mais manual.

**Por que não fazer agora:** problema atual resolve com correção cirúrgica (Opção B).
ijson é sessão dedicada — mexe no coração do motor e precisa de validação completa.

---

## 🔵 MELHORIA DE TEMPLATE — Registrar estrutura do GUIA_DO_PROJETO_IA.md

**Identificado em:** 30/06/2026 (encerramento da sessão)

A estrutura de 8 seções definida para o `GUIA_DO_PROJETO_IA.md` deste projeto é mais madura do que as versões em outros projetos. Vale replicar como padrão.

**O que fazer:** quando abrir um dos outros projetos (normativos_ia, Auditoria IA, AppSheet, app_treino), revisar o GUIA_DO_PROJETO_IA.md de lá e atualizar com a estrutura daqui:
1. O que é o projeto (2 parágrafos)
2. Três palavras essenciais (tabela)
3. Fluxo em N passos (diagrama texto)
4. Mapa de documentos (tabela pergunta → arquivo)
5. O que NÃO tocar sem entender antes
6. Como começar — primeiros 10 minutos
7. Estado atual (números-chave com aviso de desatualização)
8. Glossário completo

---

## 🟡 EM ANDAMENTO — Reorganização da documentação

**Item restante:** revisar/consolidar seções do `CLAUDE.md` que estão espalhadas ou duplicadas.
(Frentes 1, 2 e 3 concluídas em 26/06 — ver REGISTRO_CORRECOES.md para histórico.)

---

## 🔵 BACKLOG — Revisão de sinônimos em todas as regras do motor (registrado 2026-06-24)

A G3 identificou que as regras do motor detectam alguns termos de concordância e agradecimento, mas podem estar faltando sinônimos usados pelos clientes. O mesmo pode ocorrer em outras regras além da G3.

**Regras a revisar:**
- `_cliente_agradecimento_conclusivo` — detecta agradecimentos ("obrigado", "grato"...) → verificar se faltam variações reais dos clientes
- `_cliente_somente_reconhecimento_curto_pos_remessa` (§4e) — idem
- `_par_conclusivo` (G3) — já ampliada em 24/06 com: anotado, recebido, ciente, combinado, tudo certo, procederemos conforme, seguiremos as instruções

**Como fazer:** extrair do JSON 03 os textos reais de últimas mensagens C→F que estão em AGUARDANDO com R2, e verificar manualmente se alguma deveria ser CO mas não foi detectada por falta de sinônimo.

**Quando fazer:** ao revisar qualidade da triagem (IF-01).

---

## 🔵 BACKLOG — Renomear funções do motor para nomes mais intuitivos (registrado 2026-06-24)

Os nomes internos das funções de triagem são jargão técnico e não dizem o que fazem para quem lê de fora. Exemplos identificados em 24/06:

| Nome atual | Nome sugerido |
|---|---|
| `_par_conclusivo` | `_cliente_concordou_apos_finaud` |
| `_sec5_remessa_finaud` | `_finaud_enviou_arquivo_ou_instrucao` |
| `_cliente_agradecimento_conclusivo` | `_cliente_so_agradeceu_sem_pedir_nada` |

**Risco:** alto — esses nomes aparecem em 30+ arquivos. Fazer apenas com levantamento completo e grep de todos os usos antes de renomear. **Não fazer junto com outras mudanças no motor.**

**Quando fazer:** em sessão dedicada, após Fase F→F concluída.

---

## 🟡 LIMPEZA DE NOMES — nomenclatura inconsistente (registrado 2026-06-19)

> **Não fazer agora.** Fazer APÓS a Fase 1 da implementação das regras de triagem (seção 13.11).
> Qualquer IA que pegar esta pendência deve aplicar o protocolo de 6 pontos completo antes de mexer em qualquer arquivo.

---

**O que é (em linguagem simples):**
O sistema usa nomes diferentes para o mesmo conceito em lugares diferentes — como se uma pessoa fosse chamada de "João", "Sr. Costa" e "o rapaz" dependendo de quem está falando. Isso confunde qualquer pessoa ou IA que entra no projeto.

**Exemplos concretos encontrados (em 30+ arquivos):**

| Conceito | Nomes diferentes que aparecem |
|---|---|
| "A categoria do CADOC desta thread" | `alvo_triagem_auto`, `alvo_triagem`, `cadoc` |
| "O grupo DDR_2011 + 4111 + DRL_2160" | `DDR4111` — parece uma coisa só, não um grupo |
| O sufixo `_auto` nos campos | Perdeu sentido após remoção da triagem manual |

**Como fazer (quando chegar a hora):**
1. Levantamento completo de todos os nomes inconsistentes no sistema (grep em todos os arquivos)
2. Definir um nome único e claro para cada conceito — validar com Michel antes de tocar no código
3. Aplicar o protocolo de 6 pontos para CADA rename individualmente
4. Renomear arquivo por arquivo, com backup antes de cada mudança
5. Rodar `pytest` após cada rename — zero regressões é pré-requisito para avançar

**Salvaguarda obrigatória:** backup em `data/json/pipeline/backups/AAAAMMDD_HHMM_rename_nomenclatura/` antes de qualquer alteração nos JSONs do pipeline.

---

## 🔵 BACKLOG — Simulação: teste de cada documento de consulta da IA (2026-06-19)

**O que é:**
Para cada documento que a IA consulta, simular uma situação real e verificar: a IA sabe quando ler aquele documento? Lê o correto para aquela situação? Extrai a informação certa?

**Os documentos a simular:**

| # | Documento | Quando a IA deveria consultar |
|---|-----------|-------------------------------|
| 1 | `SESSAO_ATUAL.md` | ✅ Já simulado — ao abrir o chat |
| 2 | `documentações/PENDENCIAS.md` | No INTAKE: "já está pendente?" |
| 3 | `documentações/REGISTRO_CORRECOES.md` | No INTAKE: "já foi feito antes?" |
| 4 | `CLAUDE.md` | Ao verificar regra inviolável ou protocolo obrigatório |
| 5 | `documentações/MAPA_DO_PROJETO.md` | Ao precisar entender o fluxo ou localizar algo no sistema |
| 6 | `documentações/DOCUMENTACAO_TRIAGEM.md` | Ao trabalhar em qualquer regra de triagem |
| 7 | `documentações/PLANO_IMPLEMENTACAO_MOTOR.md` | Ao verificar progresso da implementação |
| 8 | `documentações/MATRIZ_DECISOES_*.md` | Ao decidir regra específica por CADOC |
| 9 | `D:\template_projeto_ai\PROJETOS.md` | Ao abrir qualquer projeto — visão cruzada de todos |
| 10 | `MEMORY.md` + arquivos de memória | Contexto persistente entre sessões |

---

## 🔵 BACKLOG — Revisão e validação das documentações para leitura da IA (2026-06-19)

**O que é:** Revisar o que já existe (MAPA_DO_PROJETO.md, DOCUMENTACAO_TRIAGEM.md, REGISTRO_CORRECOES.md e outros), validar se está completo e correto para a IA ler, e preencher só o que faltar ou estiver desatualizado.

**Como fazer:**
1. Listar todos os documentos existentes
2. Para cada documento: verificar se está atualizado com o estado atual do sistema
3. Identificar decisões do Michel que estão só em conversas e nunca foram gravadas em arquivo
4. Preencher lacunas — sem duplicar o que já existe em outro arquivo
5. Validar com Michel seção por seção antes de fechar

---

## 🔵 BACKLOG — Renumeração dos scripts do pipeline (registrado 2026-06-29)

Script 10 foi removido em 29/06/2026. A sequência ficou com buracos: 09→11 (buraco no 10), 17→20 (buracos nos 18 e 19). O Script 20 é avulso/manual (não faz parte do pipeline automático). Renumerar em sessão dedicada após verificar todos os impactos (código interno, logs, documentação, testes).

---

## 🔵 BACKLOG — Motor: thread fica PENDENTE quando último evento é F→F (registrado 2026-06-23)

> **Diferente da G3:** a G3 trata de threads que terminam com o **cliente concordando** (C→F). Este item trata de threads onde o **último evento é Finaud→Finaud** (encaminhamento interno), e o motor simplesmente não classifica — a thread fica PENDENTE no integrador.

**Causa técnica:** o motor DDR tem `AGUARDA_ULTIMA_FINAUD_FINAUD = False` (`scripts/triagem/ddr4111.py`, linha 45). Quando o último evento é F→F, o motor não aplica nenhuma regra — a thread fica PENDENTE e não entra em nenhum JSON de triagem.

**O que provavelmente deveria acontecer:** quando a última é F→F, o motor deveria percorrer para trás até encontrar um evento que não seja F→F e decidir com base nesse contexto.

**Casos reais analisados em 23/06/2026:**
| Thread | Penúltimo | Diagnóstico |
|---|---|---|
| Monte Bravo DDR_2011 | C→F (cliente cobrou) | AGUARDANDO — cliente esperando |
| Cadastro Fundos SUPORTE | F→F (também interno) | AGUARDANDO — Rodrigo não respondeu definitivo |
| Arquivos atrasados 4111 | só 1 evento | AGUARDANDO — cliente Kinel esperando habilitação |

**Arquivos envolvidos:**
- `scripts/triagem/ddr4111.py` — linha 45: `AGUARDA_ULTIMA_FINAUD_FINAUD = False`
- `scripts/triagem/motor.py` — função `_run_triagem_cadocs`
- `scripts/verificar_pendentes_pos_carga.py` — script que gera o alerta de e-mail

---

---

## 🟡 Campo 9 — Prazos: limitações e casos sem prazo identificados em produção (registrado 13/07/2026)

**Contexto:** durante a documentação do Campo 9 (Prazos), validamos os 6.576 registros de produção — todos com prazo correto. Mas encontramos 303 threads com CADOC regulatório e sem prazo calculado. Investigação revelou 4 situações:

### Situação 1 — Bug: ano com 2 dígitos não reconhecido (20 casos)
O Script 05 não reconhece datas no formato `MM/YY` (ex.: "04/26", "05/26"). Trata apenas anos com 4 dígitos.

**Exemplos reais:**
- "DLI 2062 04/26" → deveria extrair abril/2026
- "DRM 2060_05/26 - ACCREDITO" → deveria extrair maio/2026
- "DRL 2160_05/26 - TRADERS" → deveria extrair maio/2026
- "DRM 04/26", "DRM 2060 - BASE 04/26", "DRM 2060 - BASE 01/26"

**O que fazer:** no Script 05, função `extrair_todas_datas()`, adicionar padrão para `(\d{1,2})/(\d{2})(?!\d)` interpretando o ano de 2 dígitos como 20XX (ex.: 26 → 2026). Validar que não conflita com padrão DD/MM existente.

**Arquivo:** `scripts/05_classificar_emails_regulatorio.py` — função `extrair_todas_datas()` (~linha 850)

### Situação 2 — A verificar com Michel: MM/AAAA bloqueado por tipo de CADOC (165 casos)
O sistema encontrou datas (ex.: "05/2026") mas rejeitou porque o CADOC esperava data de dia específico (DDR/4111 esperam DIARIO). Inclui circulares do BACEN ("ENC: BC Correio - Resolução BCB...") que podem não ser entregas de CADOC.

**Pergunta pendente:** threads como "CADOC 4111 CONGLOMERADO - 05/2026" e "ENC: BC Correio - Resolução BCB..." deveriam ter prazo calculado?

### Situação 3 — Correto sem prazo (50 casos)
Assuntos genéricos ("Guru CTVM: Informações Diárias", "Conexão", "Reunião DRM") — parecem threads de dúvida ou comunicação geral, não de entrega de CADOC. Comportamento provavelmente correto.

### Situação 4 — Formatos incomuns sem extração (38 casos)
Exemplos: "Wise DDR 29" (só dia sem mês), "CADOC 4111 11-05" (DD-MM sem ano), "Cota de fundos DDR 12.06".

**Arquivo:** `scripts/05_classificar_emails_regulatorio.py`

---

## 🔴 INVESTIGAÇÃO — status_processo: classificação Pendente/Informativo não reflete a operação (registrado 13/07/2026)

**Contexto:** durante a documentação do Campo 8 (Status), descobrimos que o campo `status_processo` existe no sistema mas Michel não sabia da sua existência. Ele usa os valores PENDENTE e INFORMATIVO, baseados em "tem prazo = PENDENTE, não tem prazo = INFORMATIVO" — uma lógica que não representa o que a operação precisa (Aguardando ou Concluído).

**O que foi descoberto:**
- 30 de 36 threads de TESTE estão como PENDENTE (todas que têm prazo, inclusive as já concluídas)
- Na aba de busca da tela, o rótulo do card vem do `status_processo` — mostrando PENDENTE para threads já encerradas
- A cor do ponto no card (laranja = atenção) é controlada pelo `status_processo`
- Nas abas principais (Aguardando/Concluídos) o campo é ignorado — mas na busca aparece para o usuário

**O que Michel quer:** usar apenas Aguardando/Concluído em todos os lugares, eliminando a confusão de Pendente/Informativo.

**Risco identificado:** a maior preocupação é que nenhuma thread fique sem classificação após a mudança.

**Próximos passos (para a sessão dedicada):**
1. Mapear todos os lugares onde `status_processo` é lido (tela + API + scripts)
2. Simular: se substituirmos por Aguardando/Concluído, alguma thread fica sem classificação?
3. Apresentar resultado para Michel decidir se avança
4. Só implementar após aprovação explícita

**Arquivos envolvidos:** `templates/email_operacional.html` (linhas 1192, 3566, 3585, 3588), `painel_oraculo.py` (linhas 2194, 3782, 3887–3903), `scripts/09_integrar_dados_painel.py` (linhas 935, 1252, 1445)

---

## 🔗 AGUARDANDO GATILHO — itens que só iniciam quando uma condição for cumprida

> **Como funciona:** o `/iniciar` verifica se alguma condição abaixo foi cumprida. Se sim, alerta Michel e move o item para ativo.

| O que fazer | Gatilho | Contexto |
|---|---|---|
| Aplicar modelo de documentação (GUIA + PADROES + Plano antes de agir) nos outros projetos: Auditoria IA, AppSheet, normativos_ia, app_treino | Fase 6 do plano de implementação do motor concluída | Padrão definido em `D:\template_projeto_ai\PADROES.md`; referência: `PROJETOS.md` seção IF-01 |
| Instalar Sentry (monitoramento de erros na nuvem — "caixa-preta" que captura falhas do pipeline com contexto completo e avisa na hora) e conectar ao Claude via conector oficial | Pipeline rodando automatizado sem supervisão diária, OU primeiro sistema em produção para cliente (frente Dev) | Decidido em 13/07/2026 na sessão de conectores MCP. Grátis até 5.000 erros/mês. Exige adicionar ~3 linhas nos scripts (código de produção → protocolo completo: quadro, testes, registro). Hoje o watchdog (`pipeline_watchdog.py`) + e-mails de alerta cobrem o essencial. Plano completo na memória do projeto: `conectores-mcp-plano.md` |

---

## 🟡 PENDENTE — Watchdog acumula entre etapas (baixa urgência)

Na 1ª tentativa da carga 15-16/06, o watchdog do **script 04** (limite 0,5h) disparou durante o script 13. Indício de que cada `iniciar_watchdog` não cancela o anterior — timers antigos com limite curto podem matar etapas posteriores longas. Não atrapalhou após o fix do script 13 (rápido agora), mas convém cancelar o watchdog da etapa anterior ao iniciar a próxima.

**Arquivo:** `pipeline_watchdog.py` / `executar_tudo.py`.

---

## 🟡 EM ANDAMENTO — Revisão de telas como usuário novo (iniciada 01/07/2026)

Michel quer percorrer cada tela do sistema como se fosse um usuário novo — verificar clareza, fluxo e o que pode confundir. Registro completo em `documentações/REVISAO_TELAS.md`.

**Telas já percorridas:** Login (sem achados), Visão Geral (corrigida), Painel de Gestão (1ª rodada: 5 achados corrigidos + 2-G pendente; 2ª rodada: 6 achados de lógica de dados abaixo, aguardando decisões).
**Próximas:** Triagem (E-mails), Produtividade por Analista, Base Conhecimento, Normativos, FOG Casos, FOG KPIs, IA Assistente, Custos APIs, Protótipos, Admin.

---

## 🟡 REVISÃO — Painel de Gestão: 1ª rodada de achados (registrado 01/07/2026)

**Página:** Painel de Gestão — rota `/painel/gestao` — arquivos `painel_oraculo.py` + `templates/painel_gestao.html`.
Referência completa: `documentações/REVISAO_TELAS.md`, pendência 2.

**✅ RESOLVIDOS nesta sessão (01/07/2026)** — migrados para `REGISTRO_CORRECOES.md` (entradas datadas):
- **2-B** "Perto de vencer" exibia casos vencidos ontem → filtro corrigido para só prazos de hoje/futuro (`dias_ate >= 0`).
- **2-C** Cliente "—" na tabela Fora do Prazo → passa a usar o campo `empresa` como segundo recurso.
- **2-D** "Unicred" (cliente) aparecia como analista → passa a ignorar casos onde responsável == cliente.
- **2-E** Race condition ao trocar filtros de período rápido → padrão `_pgReqId` descarta resposta atrasada.
- **2-F** Badge "ranking" no painel de colaboradores → agora mostra "N analistas" (contagem real).

**🔵 2-G. Painel "Assuntos" — "4111" sem prefixo de categoria (problema de pipeline)** — AINDA ABERTO
213 threads com `alvo_triagem_auto = '4111'` aparecem separadas das 307 com `'DDR4111'`. São o mesmo tipo de demanda. Correção definitiva = unificar no pipeline. No display, normalizar "4111" → "DDR_4111".
- **Quando:** sessão dedicada de pipeline (não corrigir no painel agora)
- **Arquivo:** scripts do pipeline (classificação) + `painel_oraculo.py` para normalização de display
- **Relacionado:** ver 2-I abaixo (a mesma poluição de categorias afeta o KPI "categoria + volumosa").

---

## 🔴 REVISÃO — Painel de Gestão: 2ª rodada — 6 achados de LÓGICA DE DADOS (registrado 01/07/2026)

**Página:** Painel de Gestão — rota `/painel/gestao` — backend `painel_oraculo.py`, frontend `templates/painel_gestao.html`.
**Contexto:** ao revisar a tela com dados já corrigidos (ver correção em lote de `data_conclusao`, `REGISTRO_CORRECOES.md` 15:43), o Michel apontou que **vários números da tela estão semanticamente errados** — não é bug de exibição, é a *forma como o número é construído*. Diagnóstico feito com script sobre as funções reais de produção (não estimativa). **Nada foi corrigido — 4 dos 6 dependem de decisão de negócio do Michel.**

**⚠️ Estas 6 pendências são de MÁXIMO cuidado:** mudam a lógica central do painel de gestão (o que a diretoria vê). Cada uma deve seguir o protocolo de 7 passos do `CLAUDE.md` (simular → corrigir → validar → testar → registrar), uma por vez, em sessão dedicada.

---

**✅ 2-H RESOLVIDO em 01/07/2026** — causa raiz corrigida no motor (carimbava "hoje" na
conclusão; 15 pontos + fallback) e backfill de **671** datas (a varredura completa achou mais que
as 388 da janela de 30d). KPIs reais: 503 resolvidos/30d, tempo médio 1,7d. Detalhes na entrada
21:05 do `REGISTRO_CORRECOES.md`.

**2-I. Categoria + volumosa está poluída por alertas internos e duplicados**
- **O que vimos (dados reais, 30 dias):** o KPI conta como "categorias": DDR_2011 (292), DDR4111 (116), **RISK_DRIVER_ALERTA (113)**, RETORNO_BACEN (110), **4111 (47)**, **RISK_DRIVER_RELATORIO (45)**, DLO_2061 (42) / DLO (31), LEIAUTES_BACEN (41), DLI_2062 (20) / DLI (7), **RISK_DRIVER_RESP_AUTO (6)**... No filtro de 7 dias, **RISK_DRIVER_ALERTA "ganha" o topo** (13) — que não é categoria de cliente.
- **Dois problemas somados:** (1) os tipos **RISK_DRIVER_\*** são alertas internos do sistema RiskDriver, não CADOCs de cliente — não deviam entrar na contagem de "categoria"; (2) **duplicados não unificados**: `4111`=`DDR4111`, `DLO`=`DLO_2061`, `DLI`=`DLI_2062` (mesmo problema-raiz do 2-G).
- **⚠️ DECISÃO DO MICHEL:** confirmar que devemos (a) **excluir** os RISK_DRIVER_* da contagem de categoria e (b) **unificar** os duplicados. Depende também da tabela oficial de equivalência de CADOCs.
- **Onde é montado:** `painel_oraculo.py` — `_calcula_kpis_topo`, bloco "Categoria com mais volume" (~linha 1554, `Counter` sobre `cadoc_real`/`alvo_triagem_auto`).

**2-J. "Casos resolvidos fora do prazo" — prazo de referência provavelmente errado**
- **O que vimos:** casos com atraso enorme e suspeito, ex.: Read/DRM_2060 **+325 dias** (prazo 08/08/2025, concluído 29/06/2026); Codepe/DLI **+297 dias**.
- **Como é criado:** thread cuja `data_conclusao` passou do **prazo mais ANTIGO** (`min`) da `lista_prazos` do integrador; atraso = conclusão − esse prazo (função `_casos_fora_do_prazo`, `painel_oraculo.py` ~linha 1615).
- **Suspeita da causa:** numa thread longa, o "prazo mais antigo" pode ser um prazo de 2025 **que já foi cumprido na época**. Como a thread só foi marcada concluída agora (e a conclusão virou a data da última mensagem), o sistema calcula um "atraso fantasma" de centenas de dias. O "+325d" é provavelmente isso.
- **⚠️ DECISÃO DO MICHEL:** "fora do prazo" deve ser medido contra **qual prazo** — o mais recente/vigente ou o primeiro? E a "conclusão" é mesmo a última mensagem, ou o momento em que a obrigação foi cumprida?
- **Arquivo:** `painel_oraculo.py` — `_casos_fora_do_prazo`.

**✅ 2-K e 2-L RESOLVIDOS em 01/07/2026** — ranking único só com analistas cadastrados em
`usuarios.json` (8 analistas cadastrados sem acesso; identificação por e-mail). Detalhes na
entrada 20:40 do `REGISTRO_CORRECOES.md`.

**2-M. Garantir que TODAS as informações reflitam o filtro escolhido**
- **Verificado no código:** KPIs do topo, "fora do prazo", "colaboradores" e "assuntos" **já filtram** pelo período selecionado (usam `concluidas_periodo`). ✅
- **Única exceção:** "Casos perto de vencer" **não** depende do período — é olho-pra-frente (prazos futuros em aberto). Faz sentido, mas **confirmar com o Michel** se ele quer que essa seção também respeite o filtro ou continue independente.
- **Arquivo:** `painel_oraculo.py` — endpoint `api_painel_gestao_dados` (~linha 1897) + `_casos_perto_de_vencer`.

**Ordem de ataque (atualizada 01/07/2026, noite):** ~~2-K/2-L~~ ✅ → ~~2-H~~ ✅ → **2-N**
(datas do AGUARDANDO, abaixo) → 2-I (categorias) → 2-J (fora do prazo) → 2-M (confirmar filtro).

**2-N. Varrer as datas do AGUARDANDO (pedido do Michel, 01/07/2026 à noite)**
- **Contexto:** o 2-H provou que o motor carimbava datas com o dia da carga em vez da data real
  da última mensagem (671 threads CO corrigidas). O Michel pediu para verificar se as threads em
  **AGUARDANDO** têm o mesmo problema nos seus campos de data (ex.: `data_marcacao` — a data em
  que a thread entrou na fila de espera).
- **Como atacar:** mesma receita do 2-H — simulação exaustiva (comparar campos de data com as
  mensagens reais do fio), mostrar distribuição, decidir critério com o Michel, backup, gravar, validar.
- **Arquivo:** `data/json/pipeline/threads_aguardando_auto.json` + `scripts/triagem/motor.py`
  (verificar onde `data_marcacao` é carimbada).

---

## 🔵 BACKLOG — ~170 threads CO com motivo desatualizado (regra correta)

Threads em CONCLUÍDO com a regra certa mas com o texto do motivo desatualizado (stale). A regra está correta — só o texto explicativo está errado. 24 foram corrigidas em 30/06 (motivo "aguarda tratamento"). Restam ~146.

**Quando fazer:** sessão dedicada de backfill, após confirmar critério de correção do motivo.

---

## 📋 CORREÇÕES PLANEJADAS — Aguardam nova arquitetura

| # | Título | Status |
|---|--------|--------|
| #PF30 Sit.1 | 241 e-mails com múltiplos CADOCs — registra só o primeiro | ⬜ Aguarda SQLite/Nível 2 |
| #PF29 | Thread com múltiplos prazos — fica Crítico quando qualquer prazo vence | ⬜ Aguarda nova arquitetura |

---

## ⏳ AGUARDANDO EXTERNO / DECISÃO

| # | Título | Detalhe |
|---|--------|---------|
| #15 | CVD TVM — thread em andamento, sem solução | Quando concluída, reavaliar inclusão na base de conhecimento |
| #30 | Atual Câmbio — thread [12] pendente de revisão de fluxo | [13] incluída na base; [12] planilha DRL 04/2026 aguarda revisão completa |

---

## 🔵 BACKLOG — Backfill de gaps da documentação de triagem (Grupos A–U)

Documentação de triagem: todos os 12 CADOCs concluídos em 18/06/2026 (seções 12.1 a 12.12 do `DOCUMENTACAO_TRIAGEM.md`). Durante a documentação foram mapeados ~50 gaps — threads classificadas diferente do que o motor deveria fazer. Parte foi resolvida pelos backfills das sessões G3/G4/P-AUD. Verificar quais grupos ainda restam antes de executar.

**O que fazer:** abrir seção 13.10 do `DOCUMENTACAO_TRIAGEM.md`, conferir quais grupos A–U ainda têm threads não corrigidas e executar o backfill dos que sobraram.

---

## 🗂️ BACKLOG — Melhorias e baixa prioridade

| # | Título | Área | Prioridade |
|---|--------|------|------------|
| #PF23 Sit.1 | 241 e-mails com múltiplos CADOCs — registra só o primeiro | Arquitetura | ⬜ Aguarda SQLite/Nível 2 |
| #PF20 | Prazos diferenciados por subcategoria RB (crítica/indício/reiteração) — hoje D+5 fixo | Operacional | ⬜ Levantamento manual |
| #PF21 | Varredura de hardcodes — mover para JSON de configuração | Código | ⬜ Pós-rastreio |
| #PF16 | Flag `visivel_no_painel:false` no JSON para categorias invisíveis (Risk Driver, spam) | Arquitetura | ⬜ Melhoria |
| #PF18 | Domínio de spam novo aparece no painel — requer intervenção manual | Pipeline | ⬜ Depende de #PF16 |
| #PF19 | Campo `colaborador_finaud` fixo por thread para filtrar por analista | Dados | ⬜ Avaliar necessidade |
| #PF3 | Risk Driver — decidir se deve aparecer em aba separada ou permanecer oculto | Interface | ⬜ Futuro |
| #PF15 | Busca de e-mail antigo direto na tela sem re-rodar pipeline | Interface | ⬜ Futuro |
| #PF17 | Exibir contagem de e-mails descartados por categoria invisível | Interface | ⬜ Depende de #PF16 |
| #PF14 | Controle de atraso do lado do cliente — flag indicando que atraso não é da Finaud | Operacional | ⬜ Futuro |
| #PF41 | Script 16 — resumo LLM cobre apenas 3,8% dos eventos RETORNO_BACEN | Pipeline | ⬜ Baixa cobertura |
| #PF40 | Script 15 — enriquecimento GPT-4o nunca executado: tela /aprendizados com dados incompletos | Dados | ⬜ Avaliar custo |
| #PF39 | Script 14 — banco de indícios CRD tem apenas 5 entradas (todas DLO) | Dados | ⬜ Enriquecer manualmente |
| #8 | Coluna DTVM — OCR via `--ids` (imagens já no disco) | Pipeline | ⬜ Próxima carga |
| #36 | Script 02 — extrair texto de PDFs na coleta (pdfplumber) | Pipeline | ⬜ Baixa |
| #37 | Script 02 — separar conteúdo encaminhado | Pipeline | ⬜ Baixa |
| #39 | Conglomerados — exibir grupo em vez de empresa individual | Interface | ⬜ Baixa |
| #43 | Script 05 — marcadores de encaminhamento em português | Pipeline | ⬜ Baixa |
| M26 | Boletins DLO automáticos FinaudTec LEC — re-rodar script 05 | Pipeline | ⬜ Próximo ciclo |
| M1 | Auto-coleta de novas críticas BACEN via OCR (script 18) | Qualidade | ⬜ Médio prazo |
| M2 | Magic numbers — documentar e mover para config | Código | ⬜ Baixa |
| M3 | Script 05 — dividir em módulos menores | Código | ⬜ Futuro |
| M4 | Padronizar progresso em todos os scripts do pipeline | Qualidade | ⬜ Médio prazo |
| M7 | `status_processo` no JSON 03 sempre "PENDENTE" mesmo para threads concluídas | Dados | ⬜ Baixa |
| M8 | Alerta de threads sem resposta — e-mail automático após X dias em AGUARDANDO sem nova mensagem | Operacional | ⬜ Backlog |
| M9 | 2 threads AGUARDANDO sem eventos — Ozcambio e Coluna DTVM (fora da janela de coleta mar/abr) | Pipeline | ⬜ Backlog |
| M10 | Thread Azumidtvm RETORNO_BACEN — mensagem da Finaud truncada no JSON 03 | Pipeline | ⬜ Backlog |
| M11 | Alerta para thread sem regra — e-mail para michel@finaud.com.br quando motor não classifica | Motor / Alertas | ⬜ Backlog |
| M12 | VIS DTVM RETORNO_BACEN "ERRO ARQUIVO 2062 04/2024" — Finaud respondeu "Ok, ciente" sem orientar | Motor / Classificação | ⬜ Revisar |
| M13 | Guru DDR_2011 "Informações Diárias" — cliente fez pergunta, Finaud respondeu "Ok, ciente" sem responder | Motor / Classificação | ⬜ Revisar |
| M14 | Intercam RETORNO_BACEN — thread com apenas 1 mensagem; verificar coleta no Gmail | Pipeline / Coleta | ⬜ Backlog |
| M15 | Fair Corretora RETORNO_BACEN — forwards do BACEN capturados como mensagem da Finaud | Pipeline / Coleta | ⬜ Backlog |
| M16 | Wise DDR_2011 — dois assuntos distintos misturados no mesmo threadId | Pipeline / Coleta | ⬜ Backlog |
| M17 | Finaud/Ebury SUPORTE — fragmento de texto regulatório sem contexto como última mensagem | Pipeline / Coleta | ⬜ Backlog |
| M18 | Planner DDR_2011 "DDR DIA 28/04" — só assinatura capturada, sem corpo real | Pipeline / Coleta | ⬜ Backlog |
| M19 | BPY RETORNO_BACEN — cliente respondeu com imagem sem texto; OCR pendente | Pipeline / OCR | ⬜ Backlog |
| M20 | Planner 4111 "CADOC 18/02" — só assinatura capturada, sem corpo real | Pipeline / Coleta | ⬜ Backlog |
| M21 | Spam/prospecção — parcialmente corrigido; aguarda M34 para garantir filtro automático | Pipeline / Coleta | ⚠️ Parcial |
| M22 | 7 threads com apenas saudação sem corpo (BPY, Ozcambio, 5× Planner) | Pipeline / Coleta | ⬜ Backlog |
| M23 | F→F "Obrigada Daniela" sem contexto anterior — DLO_2061 | Pipeline / Coleta | ⬜ Backlog |
| M24 | F→F "Obrigada Monica!" sem contexto anterior — DLO_2061 | Pipeline / Coleta | ⬜ Backlog |
| M34 | Thread com 1 única mensagem e sem contexto anterior (janela de coleta) — definir regra: CONCLUIDO ou AGUARDANDO? | Pipeline / Coleta | ⬜ Verificar ao finalizar análise CONCLUIDO |
| M35 | F→F em AGUARDANDO — coleta incompleta (cliente nunca entrou no sistema). Bloqueado por M10/M14-M18. | Pipeline / Coleta | ⬜ Bloqueado |

---

## ❌ CANCELADO

| # | Título | Motivo |
|---|--------|--------|
| #23 | Subcategorias RETORNO_BACEN (DLO/DRM/DDR/DLI) | Base de Conhecimento BACEN cobre essa visão |
| #14 | Construir tela `/painel/retorno-bacen` | Substituída pela Base de Conhecimento BACEN |

---

## 🔵 INICIATIVAS FUTURAS — Backlog estratégico

---

### [IF-00] IA lendo histórico de threads — usar marcações para ignorar mensagens irrelevantes

**Contexto (14/07/2026):** durante revisão de UX da tela Triagem, ficou definido que mensagens do tipo "Resposta automática" (ausente/férias) receberão uma etiqueta de identificação.

**Ideia para o futuro:** quando a IA for chamada para ler o histórico de uma thread e aprender o que foi discutido (ex.: resumir, responder, sugerir ação), ela deverá usar essas marcações para ignorar mensagens que não têm conteúdo real:
- Tipo 4 — Resposta automática → ignorar completamente ao resumir
- Outros tipos que vierem a ser marcados podem seguir a mesma lógica

**Por que importa:** sem essa marcação, a IA pode interpretar "Retornarei em 23/06" como conteúdo relevante da conversa e gerar resumos ou sugestões erradas.

**Pré-requisito:** concluir a implementação das etiquetas de tipo na tela (UX Tela Triagem — ver sessão 14/07/2026).

---

### ~~[UX-01] Exibir anexos detectados na tela quando o corpo da mensagem está vazio~~ ✅ CONCLUÍDO (15/07/2026 — ver REGISTRO_CORRECOES.md)

---

### [UX-02] ⚠️ PARCIALMENTE RESOLVIDO — Script 02 salvar + Script 12 processar imagens inline

**Contexto (14/07/2026):** e-mails onde o cliente enviou apenas um print de tela colado no corpo do e-mail — sem texto escrito. O Script 02 não salvava essas imagens; o Script 12 não as processava.

**Varredura de 15/07/2026 — 5 mensagens em produção:**
- 8.1 — Kinel Corretora · "print" · 25/06/2026 — assunto sem CADOC — **não corrigível automaticamente**
- 8.2 — Atual Câmbio · "2062 e 4010 março" · 10/06/2026 (msg_id 98411)
- 8.3 — Atual Câmbio · "2061" · 10/06/2026 (msg_id 98412)
- 8.4 — ARC Corretora · "DLI 2062 dez 2026 x 4016" · 19/03/2026 (msg_id 93720)
- 8.5 (variante) — Relatório Pilar III · Finaud · data a confirmar

**✅ Parte 1 resolvida (16/07/2026):** Script 02 corrigido para detectar `corpo_texto_vazio` e liberar salvamento de imagem inline quando assunto tem keyword CADOC (DLO/DLI/2061/2062). Fix prospectivo — novos e-mails com esse padrão serão capturados. Casos históricos (8.2/8.3/8.4) não reprocessados: produção é somente leitura; TESTE tem poucos dados.

**Pendente — Parte 2:** Script 12 ainda processa só arquivos em `email_anexos/`, não imagens salvas pelo Script 02 via `cid:`. Para os casos históricos 8.2/8.3/8.4 serem processados, seria necessário: (a) reimportar via `--reimport-ids` em produção (não fazemos) ou (b) aguardar nova carga com o fix ativo.

**T8.1 limitação permanente:** assunto "print" sem keyword CADOC — Script 02 não pode salvar automaticamente. Requer download manual da imagem do Gmail e gravação em `email_anexos/99031_print.png`.

---

### [UX-04] 🔴 Alertas automáticos do Oráculo entram na triagem indevidamente (identificado 15/07/2026)

**Contexto:** varredura de 8.848 mensagens (15/07/2026) identificou e-mails gerados pelo próprio sistema que ainda passam pelo pipeline e aparecem na fila de triagem.

**Quantidade:** 365 em produção + 2 em TESTE.

**Quais são:** e-mails com assuntos:
- "⚠️ Atenção: Atualização na página de Leiautes do Bacen"
- "⚠️ Atualização de Comunicados e Normativos"

Esses e-mails são gerados pelos Scripts 16/17 (alertas de leiautes e normativos) e chegam na caixa do grupo suporte via e-mail automático. Não são de clientes — não deveriam entrar na triagem.

**O que fazer:** filtrar esses e-mails no Script 05 ou Script 11, identificando por assunto ou remetente interno. Pode reutilizar o mecanismo de `FILTROS_DE_IGNORAR` já existente no mapeamento de regras.

**Arquivos:** `scripts/05_classificar_emails_regulatorio.py` ou `scripts/11_triar_threads_por_cadoc.py` + `data/json/config/mapeamento_regras_negocio.json`

**Como validar:** rodar pipeline e confirmar que threads com esses assuntos não aparecem na tela de triagem.

---

### [UX-03] ✅ Script 12 — ler xlsx indício-qualidade do BACEN quando presente (implementado 14/07/2026)

**Contexto:** varredura de 8.825 emails de produção mostrou 3 padrões para threads de indício de qualidade: 57% só texto, 40% print da tela do CRD (imagem inline), ~2% xlsx de evidência (COSIF/LEC, não o xlsx do BACEN). O arquivo `indicio-qualidade.xlsx` (6K, enviado pelo BACEN) vai para o cliente via BCCorreio — quando o cliente encaminha para a Finaud, normalmente não inclui o xlsx. Zero ocorrências na base atual.

**Implementado:** Script 12 agora detecta arquivos `.xlsx`/`.xls` com "indicio" + "qualidade" no nome, extrai o conteúdo estruturado e preenche `texto_imagens` com prioridade sobre OCR. Funções adicionadas: `_extrair_texto_xlsx_indicio()`, `_listar_xlsx_indicio_por_id()`. Ver REGISTRO_CORRECOES.md 14/07/2026.

---

> Itens identificados durante o planejamento de 18/06/2026. Não são urgentes — entram após a
> conclusão da implementação das regras de triagem (seção 13 de DOCUMENTACAO_TRIAGEM.md).

---

### [IF-01] Reestruturação de qualidade total do sistema

**Contexto (18/06/2026):** revisão completa de todo o sistema com objetivo de simplificação máxima e zero brechas estruturais.

**O que esta iniciativa cobre:**
1. **Scripts:** cada script auditado — o que faz, o que recebe, o que entrega, onde pode falhar
2. **JSONs:** estrutura de cada arquivo validada — campos obrigatórios, valores válidos, o que nunca deveria estar vazio
3. **Regras:** todas as regras do motor levantadas e verificadas — alguma é redundante? alguma conflita?
4. **Tela:** varrer todas as threads e padrões visíveis — o que é claro, o que é confuso, o que falta
5. **Fluxo de informação:** mapear quantos passos cada informação percorre desde a coleta até aparecer na tela

**Princípio inviolável:** falha silenciosa é pior do que falha visível. Varrer todo o sistema em busca de pontos onde uma falha pode acontecer sem log, sem aviso, sem flag.

**Pré-requisito:** concluir a implementação das regras de triagem (seção 13 do DOCUMENTACAO_TRIAGEM.md).

---

### [IF-02] Contrato de dados do pipeline

**Contexto (18/06/2026):** cada script do pipeline terá um "contrato" verificável — definição formal do que entra e do que sai, validada técnica e pelo negócio. Se o JSON não passa no contrato, o próximo script não roda.

**Pré-requisito:** concluir [IF-01].

---

## NOTAS TÉCNICAS

### Padrões de entrada de e-mail (#PF1 / #PF2)

| Padrão | Descrição | Status |
|--------|-----------|--------|
| A | Cliente envia para suporte ou Luiz diretamente | ✅ Capturado |
| B | Finaud (Andrea, Flávio etc.) responde ao cliente | ✅ Capturado |
| C | Cliente envia só para Andrea → Andrea copia suporte na resposta | ⚠️ Parcial: resposta da Andrea capturada; e-mail original do cliente não está na caixa |
| D | Suporte ou Finaud só no CC | ✅ Capturado (34 confirmados) |
| E | Cliente encaminha e-mail para suporte | ✅ Capturado |
| ❌ | Cliente envia só para Andrea e Andrea jamais copia suporte | Inacessível — limite técnico do Gmail |
