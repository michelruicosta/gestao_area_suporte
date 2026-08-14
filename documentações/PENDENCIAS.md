# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-08-14
**Organização:** por etapa que bloqueia — reorganizado em 03/08/2026 para seguir as fases sem brechas.
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui.

---

## 🔧 CLASSIFICADOR DETERMINÍSTICO — 40 erros restantes (placar: 727/767)

> Mapeado em 13/08/2026. Atacar grupo por grupo; ao concluir um grupo, remover daqui e gravar no REGISTRO_CORRECOES.md.
> Dois RETORNO (Sinal 6b) já estão corretos em produção — aparecem aqui só porque a validação usa corpo truncado.

### ✅ RETORNO_BACEN — resolvido (2 erros restantes só na validação truncada)

Esses dois estão corretos em produção (Sinal 6b detecta VCRD no corpo completo). Só aparecem como erro na validação com 600 chars porque o "VCRD" está além desse corte.
- `RES: ARQUIVO DRM - AZUMI` → RETORNO_BACEN (atual: DRM_2060)
- `RES: Erro do DRM e DLO` → RETORNO_BACEN (atual: DLO+DRM)

---

### ⚠️ Casos sem correção viável — convite Teams com assunto CADOC (13/08/2026)

Dois e-mails são convites de reunião no Microsoft Teams cujo assunto coincide com um código CADOC — o classificador confunde com entrega real.

- `(sem assunto)` → esperado SUPORTE, obtido DLO_2061
- `DLO` → esperado SUPORTE, obtido DLO_2061 (assunto é literalmente só "DLO")

**Por que não foi corrigido:** todos os sinais testados causaram regressões:
- `invite.ics` nos anexos → -3 regressões
- `teams.microsoft.com` no corpo → -2 regressões
- Combinação das duas → ainda -2 regressões

**Impacto:** 2 threads (0,3% do total). Deixar para revisão futura se aparecer padrão melhor.

---

### ⚠️ Casos sem correção viável — VMTM no corpo (sub-padrão 2a) (13/08/2026)

Dois e-mails de suporte técnico sobre o sistema VMTM (componente de cálculo do DDR) ficam com DDR_2011 incorreto.

- `SUPORTE - INTRA DTVM` → esperado SUPORTE, obtido DDR_2011 (VMTM no corpo principal — "gerando divergência no VMTM...")
- `ENC: PR` → esperado SUPORTE, obtido DDR_2011 (sinal DDR no conteúdo encaminhado)

**Por que não foi corrigido:** remover `\bVMTM\b` dos padrões DDR causa -9 regressões em threads legítimas (FLUXO DE CAIXA - ZIIN usa VMTM como sinal de entrega DDR). Nenhum sinal alternativo isolou esses dois casos sem causar dano.

**Impacto:** 2 threads (0,3% do total). Baixo impacto — registrado como não-corrigível no sub-padrão 2a.

---

### ⚠️ Casos sem correção viável — CADOC citado no corpo como contexto de pergunta (sub-padrão 2d) (13/08/2026)

Quatro e-mails de suporte têm código CADOC mencionado no **corpo** como contexto de uma dúvida ou pedido de acesso. O classificador os confunde com entrega real porque não há como distinguir deterministicamente "cita o código" de "entrega o arquivo".

- `MIRAE ASSET - BASILEIA - JUNHO DE 2026` → esperado SUPORTE, obtido DLO_2061 (corpo diz "aguardando o DLO/LEC de Junho")
- `RES: **UNVERIFIED SENDER** Re: PR` → esperado SUPORTE, obtido DLO_2061+SCD (corpo pede confirmação de envio de DLO e SaldosContábeis)
- `RES: Dados para o relatório` → esperado SUPORTE, obtido DLO_2061+S5 (corpo pergunta se COS4010 está disponível — dúvida, não entrega)
- `Re: **UNVERIFIED SENDER** Re: Solicitação de orientação técnica` → esperado SUPORTE, obtido DLO_2061 (corpo é dúvida sobre tratamento prudencial no DLO)

**Por que não foi corrigido:** padrão indistinguível deterministicamente. O CADOC no corpo pode ser tanto entrega real quanto contexto de pergunta — sem sinal estrutural que diferencie os casos.

**Impacto:** 4 threads (0,5% do total). Registrado como não-corrigível neste ciclo.

---

### ✅ Grupo A — SUPORTE classificado como CADOC — concluído (13/08/2026)

✅ Corrigidos: Reunião+CADOC (C22), ERRO+só DDR (C23), S5 no corpo (C24), FORCAPITAL no corpo (C25), Instrução Normativa sem CADOC (C26) — 7 threads corrigidas.
⚠️ Sem correção viável: 2 convites Teams + 2 VMTM + 4 CADOC no corpo como contexto → ver seções acima.

---

### ✅ Grupo B — CADOC real não detectado, fica em SUPORTE — concluído (14/08/2026)

Todos os 7 casos resolvidos:
- C27: CADASTRO+RISKDRIVER → DDR_2011 (+1 ganho)
- C28: POSICAO+data → DDR_2011 (+1 ganho)
- C29: EXTRATOS → DDR_2011 (+1 ganho)
- C30: 4010/4016 no assunto → DLO_2061 (+2 ganhos: "4010 Trinus" + "COSIF'S 4010")
- C31: COS+espaço nos anexos → DLO_2061 (+1 ganho: "Arquivo COS")
- Gabarito: "RES: Norma BCB - Risco de Liquidez e LCR" corrigido para SUPORTE (+1 ganho)
Placar parcial do Grupo B: 713 → 720/767 acertos.

---

### 🔴 Grupo C — Faltam categorias — 5 restantes (9 de 14 resolvidos)

✅ Resolvidos: PLANNER, DLO MAIO, ATUAL CORRETORA, DLI MAIO (C32: códigos 2011/2060/2061/2062 nos anexos) + Guru CTVM, COS 4010 junho, DRM 2060 Traders (C32: SCD via 4111/SALDOS nos anexos) + AMARIL FRANKLIN 06/2026 e 07/2026 (C33: 4010 no nome do arquivo)

| Thread | Esperado | Obtido atual | Sinal faltante |
|---|---|---|---|
| RES: DLO - 06/2026 - Encaminhar a composição do fundo | DLI+DLO+DRL+DRM | DLI+DLO | DRL e DRM citados no corpo como pergunta — a decidir com Michel |
| RE: DRM 05.2026 | DDR+DRM | DRM | "Enviado o DDR de 29/05 ajustado" no corpo (só sinal no corpo) |
| Prévia dos saldos contábeis de junho/2026 | DDR+DRM | DRM+SCD | DDR no corpo; SCD sobrando (assunto menciona "saldos contábeis") |
| Re: Arquivo 2061. Segue o DLO 05/2026. ACCREDITO. | DLI+DLO | DLO | Nenhum sinal de DLI no corpo nem nos anexos |
| Segue a remessa DRM (2060) junho/2026. MIRAE. | DRM+SCD | DRM | "saldos contábeis" no corpo (sem 4111/SALDOS nos anexos) |

---

### 🔴 Grupo D — Categoria extra adicionada indevidamente (10 threads)

O classificador acerta as categorias certas mas adiciona uma categoria a mais que não pertence.

| Thread | Esperado | Obtido (errado) |
|---|---|---|
| Re: Planilha DRL-LEC Junho/2026 | DLI+DLO | DDR+DLI+DLO+DRL |
| Re: REMITLY - Encaminhar COS4010 e LEC maio/2026 | DLI+DLO | DDR+DLI+DLO |
| RES: VIS : STA - DDR2011 e demais não disponíveis | DDR | DDR+DLI+DLO |
| duvidas finaud | DLO | DDR+DLO |
| Re: Arquivo 2061 e 2062. Segue o DLI. ACCREDITO. | DLI | DLI+DLO |
| Re: COS4016 DE 06-2026. Segue o 4111. FAIRWAY | SCD | DLO+SCD |
| Saldos do dia 20/07 até 22/07 | SCD | DDR+SCD |
| Saldos do dia 27/07 (retificação) e 28/07 | SCD | DDR+SCD |
| Pendencias BACEN - 2011 ref. 30/01/2026 | SCD | DDR |
| Remitly CC - 4010/4016 - 06/2026 | DLO | DDR |

---

### 🔴 Grupo E — Falta SUPORTE ao lado do CADOC (5 threads)

Classificador detecta o CADOC corretamente mas não reconhece que o e-mail também é de suporte.

| Thread | Esperado | Obtido (errado) |
|---|---|---|
| Posição de Câmbio CAM0050 BACEN... | DDR+SUPORTE | DDR |
| Erro - 2060 DRM | DRM+SUPORTE | DRM |
| Re: DLO - 30.06.2026. ATUAL Corretora de Câmbio | DLO+SUPORTE | DLO |
| Re: Risk Driver - Guru Corretora de Títulos | DLO+SUPORTE | DLO |
| DRL - Jun/26 | DRL+SUPORTE | DRL |

---

### 🔴 Grupo F — Casos individuais a avaliar (8 threads)

| Thread | Esperado | Obtido | Situação |
|---|---|---|---|
| INDICIO 2061 - DLO MAIO | DLO_2061 | RETORNO_BACEN | ⚠️ Pendente: "INDICIO" no assunto dispara RETORNO — Michel decide se a regra deve ser especificada |
| ENC: Risk Driver - CV INVESTIMENTOS | DLO+SUPORTE | RETORNO_BACEN | Falso RETORNO — verificar sinal disparado |
| Divulgação Instrução Normativa BCB nº 761 | INTERNO | SUPORTE | Categoria INTERNO não existe no classificador atual — avaliar se deve ser criada |
| Re: Encaminhar COS4010 jan a maio/2026. FREEX | S5 | DLO | S5 não detectado |
| Re: Solicitação de treinamento – FREEX | S5 | DLO | S5 não detectado |
| RE: Executive Corretora - Demonstrativo S5 | DLO | S5 | DLO não detectado |
| Re: COS4010 06/2026 - VBS SCD (VECTOR) | S5 | DLO+S5 | DLO a mais |
| Saldos do dia 20/07 até 22/07 (ver Grupo D) | — | — | — |

---

## ⏭ ETAPA ATUAL — Aprovar gabarito v2.0 + reduzir os 134 incertos

> Estado atual: gabarito v2.0 com 18 regras + 24 gabaritos integrado ao classificador.
> Amostra de controle: 15/20 corretas — REPROVADA. 3 casos precisam ser investigados antes de aprovar.

### 🔴 AMOSTRA — Investigar os 3 casos reprovados (um por vez) — (12/08/2026)

Rodar o ciclo: analisar → corrigir spec ou gabarito → amostra → se aprovada → commitar.

**Caso 1:** "[CV INVEST] DLO - 05/2026"
- Esperado: `[DLO_2061]` → Obtido: `[DLO_2061, DLI_2062]`
- Investigar: corpo menciona 4010/4016? Por que o GPT adicionou DLI?

**Caso 2:** "2026.07.07 - FLUXO DE CAIXA - ZIIN"
- Esperado: `[DDR_2011, SALDOS_CONTABEIS_DIARIOS_4111]` → Obtido: `[SALDOS_CONTABEIS_DIARIOS_4111]`
- Investigar: "FLUXO DE CAIXA" está nas keywords DDR da spec? Por que DDR_2011 sumiu?

**Caso 3:** "Erro do DRM e DLO"
- Esperado: `[DLO_2061, DRM_2060, RETORNO_BACEN]` → Obtido: `[DLO_2061, DRM_2060]`
- Investigar: corpo menciona crítica do BACEN? Por que RETORNO_BACEN sumiu?

**Critério de aprovação após correções:** amostra de 20 threads com ≤ 1 INCERTO e 0 erros.
**Quando aprovada:** commitar com tag `gabarito-v2-estavel`.

**Arquivo de destino:** `documentações/gabarito.json` e/ou `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10.

---

### 🔴 CLASSIFICADOR — Revisar o §10 da spec com hierarquia de regras (identificado 07/08/2026)

**Contexto:** R6 tem 134 incertos (17,4%). Tentativas de adicionar regras causaram regressões porque a spec não tem hierarquia — regras amplas conflitam com regras específicas e a IA não sabe qual usar.

**O que fazer:**
1. Ler cada categoria do §10
2. Reescrever as regras do mais específico para o mais geral
3. Adicionar instrução explícita: "aplique sempre a regra mais específica que se encaixar; regra geral só entra se nenhuma específica bater"
4. Testar amostra de 20 threads após cada categoria revisada (usar `--filtrar-ids` no validador)
5. Só rodar as 768 threads se a amostra não regredir

**Critério de sucesso:** resultado < 134 incertos sem regressão nas threads já corretas (baseline R6 = `rodada-6-baseline`).

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §10 completo.

---

### 🟡 CLASSIFICADOR — LEC: correção congelada — retomar após hierarquia do §10 (identificado 07/08/2026)

**O que foi feito:** parágrafo LEC adicionado ao §10 DLO_2061 + script atualizado para ler múltiplas mensagens. Testes mostraram que a mudança na spec causou 2 regressões em threads que estavam corretas no R6.

**O que ficou pendente:**
- 1 thread LEC ainda INCERTO: "Relatório 2061 - Ajuda na importação da planilha LEC" (WNT DTVM) — Michel confirmou que é DLO_2061
- Regressões causadas pela spec: "DLO maio/26" e "DTVM - DLO 2061 CALCULO DO PATRIMÔNIO DE REFERENCIA"
- Script de leitura multi-mensagem foi revertido para não causar mais instabilidade

**Pré-requisito:** resolver a hierarquia do §10 (item 🔴 acima) antes de retomar o LEC.

---

### 🔴 CLASSIFICADOR — Investigar por que "Planilha LEC" é INCERTO apesar de estar na spec (identificado 07/08/2026)

A spec §10 DLO_2061 já diz: "Planilha LEC no assunto = sinal de Alta confiança para DLO_2061". Mesmo assim, 2 threads com "Planilha LEC" no assunto retornaram INCERTO na R6. Antes de adicionar qualquer nova regra ao §10, entender o motivo — senão corremos o risco de novo colapso como o R3.

**Threads afetadas:**
- "Fwd: Encaminhar a planilha LEC 06 2026 - MIRAE." (andrea.inacio@finaud.com.br)
- "Planilha LEC e ponderação 05/2026" (jessica.silva@banvox.com.br)

**O que investigar:**
1. O que a IA respondeu de motivo para cada uma? (campo `motivo` no R6 JSONL)
2. O que estava no corpo (600 chars) dessas threads?
3. A regra LEC na spec está clara o suficiente ou precisa ser reformulada?

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §10 DLO_2061.

---

### 🟡 CLASSIFICADOR — Fechar os 134 incertos usando significado dos termos (identificado 07/08/2026)

Mapa dos incertos concluído. Abordagem aprovada: enriquecer a spec com o **significado dos termos** para que a IA raciocine corretamente — uma mudança por vez, amostra de 20 threads após cada adição.

**6 casos DDR sem sinal no assunto que a IA não soube classificar (Michel confirmou DDR):**
- "Erro ao calcular o VMTM do dia 30/07/2026" → VMTM é componente de cálculo DDR
- "Cadastro Operações - 29/05" (Terra Investimentos)
- "Criação de nova conta COSIF Junho/2026" → setup DDR
- "RES: Encaminhar o CNPJ do fundo Mirae Asset APEX fund LP" → setup DDR
- "ENC: POSICAO 10.07.2026" (Fair Corretora) → posição DDR
- "RE: Geração do arquivo Doc. 2011-LIM de 16/06 - Sefer" → "2011-LIM" = CADOC DDR

**3 keywords DDR que faltaram na varredura (verificar se já estão na spec):**
- "Posição de Câmbio" → DDR_2011
- "FLUXO DE CAIXA" → DDR_2011

**Pré-requisito:** resolver o item 🔴 acima (investigar LEC) antes de começar.

---

### 🟡 SPEC — Definir comportamento do classificador em produção: threads novas vs. já classificadas (identificado 07/08/2026)

**Contexto:** o projeto não é só as 768 threads de teste — em produção, novas threads chegam diariamente. A spec precisa definir como o classificador trata esse cenário antes de ir para produção.

**O que precisa ser definido:**
- Thread nova (nunca processada) → classifica e grava a categoria
- Thread já classificada → não reclassifica; usa o que está gravado
- Thread que recebeu nova resposta → reclassifica? Só se ainda estiver em aberto?
- Como o sistema sabe o que já foi processado → lista ou banco de IDs já classificados

**Por que importa:** sem essa regra, rodar o classificador duas vezes pode sobrescrever classificações corretas com resultados diferentes — mesmo com `temperature=0`, mudanças na spec geram resultados diferentes.

**Onde documentar:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — seção de ciclo de vida das threads (a definir).

---

### 🟡 CLASSIFICADOR — Verificar dupla categoria: "COS 4010 junho/2026" (identificado 07/08/2026)

Thread classificada como SALDOS_CONTABEIS_DIARIOS_4111 + DLO_2061 com alta confiança. A IA viu COS4010 no assunto (→ DLO_2061) e "retificação do Doc 4111" no corpo (→ SALDOS_CONTABEIS_DIARIOS_4111). Michel considerou correto por ora.

**Dúvida:** o cliente tratava das duas entregas ao mesmo tempo ou só do DLO?
**Quando revisar:** fase 3 — após corrigir erros confirmados e resolver os INCERTO.

---

### 🔴 SPEC §10 — Definir 3 distinções que a IA não sabe fazer (identificado 10/08/2026)

Durante os testes do gabarito (v1.0 a v1.3), ficou claro que a IA não tem regra conceitual para distinguir 3 situações. Sem essa distinção no §10, o gabarito não consegue corrigir esses casos — exemplos patcham sintomas, mas a raiz está na falta de regra.

**As 3 distinções que precisam ser definidas na spec:**

1. **Entrega de CADOC × SUPORTE**
   Quando um e-mail entregando um arquivo regulatório é classificado como CADOC (SCD, DDR, DLO…) e quando é SUPORTE? A IA está adicionando SUPORTE a entregas válidas de CADOC quando o corpo do e-mail é curto ("Segue até o dia XX").

2. **SUPORTE × RETORNO_BACEN**
   Quando o BACEN aparece no e-mail, é RETORNO_BACEN ou SUPORTE? A regra atual não separa claramente: RETORNO_BACEN = BACEN comunicando inconsistência sobre entrega nossa; SUPORTE = pedido de ajuda operacional sem BACEN envolvido.

3. **Arquivo 4016: quando é DLO, quando é DLI, quando os dois?**
   O COS4010 pode ser DLO ou DLI. O arquivo 4016 também. Sem regra clara, a IA erra ou omite uma das categorias. A definição precisa estar na spec antes de qualquer exemplo no gabarito.

**O que fazer:**
1. Rascunhar as 3 regras com Michel (quem sabe o negócio decide os critérios)
2. Escrever o texto no padrão do §10 e apresentar para aprovação
3. Gravar na spec após OK
4. Só então criar exemplos de gabarito para esses casos

**Bloqueador para:** COS4010+4016 (multi-categoria), qualquer caso onde SUPORTE é adicionado junto com CADOC.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §10.

---

### 🟡 CLASSIFICADOR — Gabarito v2.0: validar e expandir (atualizado 12/08/2026)

**Estado atual (12/08/2026):** `documentações/gabarito.json` v2.0 criado — 18 regras + 24 gabaritos. Integrado ao `classificador_ia.py` e ao `chat_ensino.py`. Amostra de controle: REPROVADA (15/20 — ver item 🔴 acima).

**O que resta:**
1. Corrigir os 3 casos reprovados na amostra (item 🔴 acima)
2. Após aprovação: usar `chat_ensino.py` para resolver os 134 incertos restantes — cada confirmação entra no registro e o gabarito pode crescer com novos exemplos
3. Commitar com tag `gabarito-v2-estavel` após amostra aprovada

**Resultado esperado:** menos incertos, mais consistência, gabarito crescendo a cada sessão de ensino.

---

## ⏭ ETAPA PARALELA — Completar a spec antes da Fase 1

> Resolver tudo abaixo antes de escrever a primeira linha de código de produção.

---


### 🟡 ENCODING — Corrigir codificação quebrada nos e-mails da TRUSTEE DTVM (identificado 30/07/2026)

Durante a validação do Campo 6, os e-mails da TRUSTEE DTVM apareceram com caracteres quebrados:
`movimenta??o`, `?cone`, `Descri??o`, `confian?a`. O texto original seria `movimentação`, `ícone`, `Descrição`, `confiança`.

**Causa provável:** e-mails enviados em codificação Windows-1252 processados como UTF-8.

**Impacto:** a IA classificadora recebe texto com `??` no lugar de palavras reais — pode prejudicar a classificação. Ocorre em todos os e-mails da TRUSTEE DTVM presentes no JSON01.

**O que fazer:**
1. Identificar quantos e-mails no JSON01 têm esse problema (buscar por U+FFFD no campo `corpo_texto`)
2. Verificar se o problema é só TRUSTEE ou há outros remetentes afetados
3. Implementar detecção e reconversão de encoding no coletor Gmail

**Arquivo de destino:** módulo de limpeza do corpo — Passo 3 da Fase 1.

---

### 🟡 CLASSIFICADOR — Palavra de fechamento "Abraço" (singular) não está no detector de assinatura (identificado 30/07/2026)

O padrão atual reconhece `abraços` (plural) mas não `abraço` (singular). São a mesma coisa na prática — e-mails que fecham com "Abraço," não terão a assinatura removida. A IA vai receber nome, cargo e telefone junto com o texto.

**O que fazer:** adicionar `abraço[,!.\s]` (singular) ao padrão `PAD_ASSINATURA`.

**Variações a incluir:** `abraço!`, `um abraço,`, `grande abraço,` (a abreviação `abs,` já está no padrão ✅).

**Arquivo a alterar:** módulo de limpeza do corpo quando for criado na Fase 1.

---

### 🟡 PAINEL — Fluxo de Retenção: como thread revisada por Michel entra no painel (identificado 06/08/2026)

A spec define que e-mails com confiança abaixo de 99% vão para **Retenção com alerta para Michel**. Mas o fluxo após a revisão não está especificado.

**Perguntas em aberto:**
1. O alerta chega como? (e-mail, notificação no painel, fila separada?)
2. Michel decide a categoria — onde registra essa decisão?
3. Quem processa a decisão no sistema?
4. A thread entra no painel automaticamente ou precisa de ação manual?

**Quando resolver:** ao definir o §13 (Telas do sistema) — é uma decisão de UX que afeta o design do painel.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §13 Telas (Fase 2).

---

### 🟡 FILTRO §4 — E-mails automáticos roteados via suporte@ escapam do filtro (identificado 06/08/2026)

Durante a validação com 768 threads, identificamos que e-mails automáticos que chegam **roteados pelo endereço `suporte@finaud.com.br`** não são barrados pelo filtro §4. O remetente original (ex.: Microsoft) fica escondido no **nome** do campo remetente (`'cvpar.com.br (via Microsoft)' via Suporte`), mas o endereço de e-mail aparece como `suporte@finaud.com.br` — que não está na lista de bloqueios.

**Exemplo confirmado por Michel (06/08/2026):** assunto `Seu código de verificação da conta de cvpar.com.br` — e-mail automático da Microsoft com código de acesso. Conteúdo irrelevante para o projeto. Passou pelo filtro, chegou à IA, que ficou incerta.

**O que fazer:** adicionar à função `eh_automatico()` detecção pelo **nome do remetente** quando contém padrões como `via Microsoft`, `via Google`, `via LinkedIn`, ou quando o nome indica notificação automática (`código de verificação`, `verification code`, etc.).

**Arquivo a alterar:** `scripts/validador_classificacao.py` → função `eh_automatico()`, e futuramente o coletor de produção.

---

### 🟡 DADOS — Respostas de colaboradores via suporte@ não aparecem no dado (identificado 05/08/2026)

Durante a simulação, confirmamos que **Flávio Camargo** (e possivelmente **Pedro Silva**, **Fábio Silva**, **Lucas Vellani**) responderam a threads que estão no dado, mas nenhuma resposta deles foi capturada. Os 113 threads onde Flávio é destinatário têm o seguinte padrão: 87 com apenas 1 mensagem (a do cliente), e 26 com respostas via `suporte@` que têm Reply-To de **clientes externos** (não do Flávio).

**Causa provável:** quando o colaborador responde via o grupo `suporte@finaud.com.br`, a regra de roteamento não captura essa mensagem (o envelope sender é o grupo, não o colaborador), e o Gmail pode não estar entregando cópias dessas respostas na caixa `coleta.oraculo@`.

**O que precisa ser investigado:**
1. Como esses colaboradores respondem na prática — via grupo, via e-mail direto, ou outro canal (WhatsApp, Teams)?
2. Se por e-mail: verificar diretamente na caixa `coleta.oraculo@finaud.com.br` no Gmail se existem threads com `From = flavio.camargo@finaud.com.br` que não foram capturadas na extração

**Impacto no sistema:** sem essas respostas, o status de threads atribuídas ao Flávio ficará sempre "Aguardando Finaud" — o sistema nunca verá que ele respondeu.

**Arquivo de destino:** a depender da causa — pode ser ajuste no roteamento do Google Workspace ou no coletor Gmail.

---

### 🟡 ALINHAMENTO — IA e Michel precisam aprofundar entendimento sobre conteúdo e direcionamento dos e-mails (identificado 06/08/2026)

Durante a revisão dos casos da validação, Michel observou que a IA e ele ainda não estão alinhados sobre o conteúdo dos e-mails e seu direcionamento — a IA não tem clareza suficiente sobre o contexto de negócio por trás de cada tipo de interação.

**Exemplo concreto:** e-mail de cadastro de fundo para geração de DDR — a IA classificou como SUPORTE porque não havia DDR sendo entregue; Michel corrigiu explicando que o cadastro faz parte do fluxo DDR.

**O que fazer (posterior):** sessão dedicada para a IA aprender o contexto de negócio de cada categoria — como funciona o processo completo, quais interações fazem parte de cada fluxo regulatório, e o que parece SUPORTE mas é CADOC (e vice-versa). Não precisa ser feito antes da implementação, mas deve anteceder a primeira validação com dados reais em produção.

---

## ANTES DA FASE 3 — Ligar a IA

> Resolver tudo abaixo antes de conectar a IA classificadora.

---

### 🔴 OCR — RETORNO_BACEN depende 100% das imagens para classificação e aprendizado (identificado 30/07/2026)

Na análise do RETORNO_BACEN (1.298 e-mails), os elementos `[image:]` (36,3%) e `[cid:]` (41,0%) são os mais altos de todas as 12 categorias. Nesta categoria, o cliente envia **prints de tela** com as mensagens de erro do BACEN — o texto do e-mail diz apenas:

> *"Prezados, recebemos a seguinte crítica referente ao DLO de dezembro: [image: image.png]"*

O que está dentro da imagem é o erro real: código de crítica, conta contábil afetada, valor divergente. Sem ler a imagem, a IA recebe apenas a casca do e-mail.

**Impacto sem OCR:** a IA classifica como RETORNO_BACEN genérico sem entender o problema específico; o aprendizado da IA Assistente fica cego para o conteúdo mais importante desta categoria.

**O que decidir antes da Fase 3:**
1. Garantir que OCR está implementado antes de qualquer classificação de RETORNO_BACEN
2. Definir o que fazer se o OCR falhar: fila de revisão humana (já previsto pela regra L6)
3. Avaliar se é necessário OCR especializado para prints de sistema BACEN

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — Campo 6 (regra L6).

---

### ✅ CLASSIFICADOR — Convites de calendário (RESOLVIDO 07/08/2026)

Decisão tomada por Michel: qualquer e-mail com invite.ics ou link de reunião (Teams, Meet, Zoom) → **SUPORTE**, mesmo que o assunto mencione um CADOC. Registrado em §10 SUPORTE e §12 Decisões da spec.

---

### 🟡 IA ASSISTENTE — Como preservar o histórico completo para aprendizado (identificado 30/07/2026)

O Passo 3 da limpeza remove o histórico citado (`>` e `---`) antes de passar o texto para a IA classificadora — correto para classificação. Mas a IA Assistente de Aprendizado precisa do histórico completo da thread para entender como cada caso foi resolvido.

**O problema:** se removermos o histórico para classificação, perdemos esse conteúdo para o aprendizado.

**Agravante:** as primeiras threads coletadas já chegaram com histórico de conversas anteriores a julho/2026 disponível apenas como conteúdo citado (`>`). Se esse `>` for removido, esse histórico pré-coleta se perde para sempre.

**O que precisa ser decidido:**
1. Como separar: texto limpo para classificação vs. thread completa para aprendizado?
2. Guardar o `corpo_texto` original (com todo o histórico) em campo separado antes de aplicar a limpeza?
3. Para a IA Assistente: reconstruir a thread completa via Gmail API?
4. O que fazer com threads com histórico anterior a julho/2026?

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — nova seção sobre IA Assistente.

---

## ANTES DAS TELAS — Especificar §13 (Telas do sistema)

### 🟡 PRAZOS — Visualização de itens atrasados e perto de vencer (identificado 04/08/2026)

**Decisão de Michel (04/08/2026):** a tela principal não deve poluir com alertas de prazo — criar tela ou painel separado para isso na Fase 2.

**O que a Fase 2 precisará entregar:**
- Mostrar itens **atrasados** (prazo vencido) separados dos itens em dia
- Mostrar itens **perto de vencer** (ex.: menos de X dias) com destaque visual
- Não exibir esses alertas misturados com a fila normal — painel ou filtro separado

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §13 Telas (Fase 2).

---



> Resolver tudo abaixo antes de definir o design das telas.

---

### 🟡 PAINEL DO GESTOR — Design para threads com múltiplos CADOCs (identificado 30/07/2026)

Uma thread pode gerar múltiplos registros (um DDR + um DRM, por exemplo). O painel precisa mostrar isso de forma clara.

**Perguntas abertas:**
1. O painel agrupa por **thread** (conversa) ou por **CADOC** (obrigação regulatória)?
2. Como mostrar "thread X tem DDR pendente e DRM concluído"?
3. Quais status existem para cada CADOC? (Aguardando → Em análise → Concluído → Vencido?)
4. O que o gestor mais precisa ver de relance?
5. Filtros: por cliente? por tipo de CADOC? por data de vencimento?

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §13 Telas.

---

### 🟡 PAINEL — Ideias para o painel lateral de categoria (identificado 31/07/2026)

Ideias levantadas por Michel para evoluir o painel:

1. **Fora do prazo:** antes da lista de threads em cada seção, mostrar quantas estão fora do prazo
   > AGUARDANDO FINAUD (54) · ⚠ 12 fora do prazo

2. **Linguagem do status no cartão:** em vez de "R2", mostrar "Aguardando a Finaud processar o material do cliente"

3. **Concluídas com regra:** na seção Concluídas, mostrar qual regra foi usada (ex.: "Encerrado pela regra R1")

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §13 Telas.

---

## APÓS A FASE 1 ESTAR RODANDO

> Fazer depois que o protótipo (coletor + classificador sem IA) estiver funcionando.

---

### 🟡 §8 — Threads "irmãs": quando a confirmação chega em thread separada (identificado 03/08/2026)

Situação onde o cliente, em vez de responder na thread original, abre um e-mail novo para confirmar (ex.: "DDR transmitido no BACEN" chega em thread B, mas a thread A ainda aparece como Aguardando Cliente).

**Decisão de Michel (03/08/2026):** deixar para a Fase 2. Na Fase 1, threads irmãs não ocorrem no dia a dia — a regra do último e-mail cobre todos os casos normais.

**Opção favorita para a Fase 2:** Camada 2 rastreia a **entrega**, não a thread — gestor encerra a entrega independente de qual thread trouxe a confirmação.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §8 e/ou §9.

---

### 🟡 NOVA ARQUITETURA — Simular modelo de duas camadas com dados reais (identificado 27/07/2026)

Confirmar com o histórico real que a IA extrai múltiplos CADOCs de um mesmo e-mail (ex.: "DDR + DRM + DLI de março"). Verificar quantos e-mails no histórico têm múltiplos CADOCs.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §9.

---

### 🟡 SPEC — Revisar formato dos Campos 1 a 5 (identificado 30/07/2026)

Os Campos 1 a 5 foram escritos antes do padrão do Campo 6 (que é mais rico e estruturado). Ajuste estético — não bloqueia nenhuma fase.

**Arquivo:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §7 (Campos 1 a 5).

---

### 🟡 NOVO PROJETO — Criar MAPA_DO_PROJETO.md para a nova arquitetura (identificado 28/07/2026)

O MAPA antigo foi arquivado. Quando a estrutura do novo código estiver definida, criar novo MAPA descrevendo o que o sistema faz, as duas partes principais, onde mora cada coisa e as regras que não se quebram.

**Quando fazer:** após a estrutura do novo código estar definida (Fase 1).

---

### 🟡 NOVO PROJETO — Escrever README.md (identificado 28/07/2026)

O README antigo foi arquivado. Escrever o novo só quando algo estiver funcionando — um README descreve um sistema que existe.

**Quando fazer:** após a Fase 1 estar funcional.

---
