# PENDÊNCIAS — Gestão Área Suporte

**Atualizado:** 2026-08-29 23:30
**Organização:** por etapa que bloqueia — reorganizado em 03/08/2026 para seguir as fases sem brechas.
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui.

---

## COLETOR + TELAS — Agrupar threads relacionadas via In-Reply-To/References (identificado em 28/08/2026)

**Prioridade: bug Outlook CORRIGIDO (commit `bce6add`, 29/08). Pode iniciar.**

### O problema confirmado

O Gmail às vezes cria `thread_id` distintos para o que é uma única conversa de negócio:
- Quando adiciona `**UNVERIFIED SENDER**` ao assunto (remetente externo não verificado)
- Quando os destinatários mudam no meio da troca (alguém entra ou sai do CC)
- Quando alguém responde em um ramo mais antigo da cadeia em vez da última mensagem

**Caso concreto confirmado (outro chat):** "Tratamento prudencial dos Direitos de Uso na
apuração do DLO" — aparece como 3 thread_ids separados no Gmail quando é 1 conversa de negócio.

### O que NÃO é problema

Durante a investigação de 29/08/2026, confirmamos que nem toda thread duplicada é erro:
- "Arquivo DLO maio rejeitado" — 2 threads no sistema, 2 conversas no Gmail → **correto**
- MiraeAsset relatórios diários — cliente usa "Responder" para enviar cada dia → **são entidades distintas**

### Regra de ouro antes de implementar

**Seguir o que o Gmail mostra na tela.** Se o Gmail mostra 2 conversas → nosso sistema mostrando
2 está certo. Só há problema quando o Gmail mostra 1 conversa mas o Gmail API retornou 2
`thread_id` distintos e nosso sistema mostra 2.

### O que fazer antes de escrever qualquer código

1. **Mapear os cenários** — para cada tipo de situação (UNVERIFIED SENDER, mudança de CC,
   resposta em ramo antigo, cliente usando Responder para novo relatório), verificar no Gmail
   como aparece na tela e como a API retorna. Montar tabela de cenários.
2. **Mostrar a tabela ao Michel** e definir: qual deve agrupar? qual não deve?
3. **Só depois:** propor o algoritmo de agrupamento, mostrar, obter OK, codificar.
4. **Testar com caso real:** "Tratamento prudencial dos Direitos de Uso" deve aparecer como 1
   entry após a implementação.

### Aprendizado de 29/08/2026

A primeira tentativa usou apenas `In-Reply-To`/`References` sem verificar o assunto. Resultado:
66 relatórios diários da MiraeAsset foram agrupados sob 1 canonical — cada um é uma entrega
separada. O algoritmo precisa distinguir:
- Mesmo assunto, 2 thread_ids → **agrupar** (é a mesma conversa que o Gmail dividiu)
- Assunto diferente, referência técnica → **não agrupar** (são entregas distintas que o cliente
  enviou como reply por hábito)

**Quando fazer:** chat dedicado após correção do bug Outlook em `_extrair_texto_novo()`.

---

## PROCESSO — Conferências automáticas do `/fechar` (identificado em 27/08/2026)

Ao corrigir o `/fechar` (ver `REGISTRO_CORRECOES.md`, 27/08 14:07), dois blocos foram
removidos porque mandavam rodar programas que existiam só no projeto antigo. As conferências
que eles faziam nunca rodaram neste projeto.

| # | O que falta | Por que importa | Prioridade |
|---|---|---|---|
| 1 | Recriar a **auditoria de documentação** e a **verificação de links quebrados** como scripts deste projeto, e devolver os dois passos ao `/fechar` | São o que pega sozinho documento citado que não existe — o erro que só foi descoberto à mão em 27/08 | MÉDIA |
| 2 | Definir a **conferência de números** do `/fechar` pelo banco `data/gestao.db` | O bloco antigo contava registros em `data/json/pipeline/threads_*.json`, da arquitetura anterior. Hoje o `/fechar` não confere se os números do `SESSAO_ATUAL.md` batem com a realidade | MÉDIA |

**Nomes ainda não aprovados** — seguir o padrão `ação_domínio.py` (`CLAUDE.md` §2.2) e propor
ao Michel antes de criar.

---

## TELAS — Melhorar textos do campo MOTIVO (identificado em 27/08/2026)

O campo **MOTIVO** exibido na tela de e-mails é hoje muito genérico em vários casos. Análise completa feita em 27/08 — motivos revisados com Michel caso a caso.

**Planilha de referência:** `documentações/varredura_motivos.xlsx` (76 motivos distintos, até 50 exemplos reais cada)

---

### ✅ Motivos já aprovados por Michel — aguardam implementação no código

| Motivo atual no banco | Novo texto aprovado | Status | Aprovado em |
|---|---|---|---|
| "Cliente enviou conteúdo — aguarda processamento da Finaud" (383x) | **Cliente enviou informações e extratos — aguarda processamento** | Aguardando Finaud | 27/08 manhã |
| "Cliente encaminhou — aguarda processamento da Finaud" (64x) | **consolidado no item acima** | Aguardando Finaud | 27/08 manhã |
| [caixa preta — entrega detectável] (~150x) | **consolidado no item acima** | Aguardando Finaud | 27/08 tarde |
| [caixa preta — pergunta do cliente] (~70x) | **Cliente fez pergunta — aguarda resposta da Finaud** | Aguardando Finaud | 27/08 tarde |
| "Fix H: cliente agradeceu sem pergunta ou documento" (41x) + "Cliente confirmou — sem pendência" (39x) | **Cliente agradeceu — problema resolvido** | Concluída | 27/08 tarde |
| "Finaud encerrou a conversa" (68x) | **Finaud concluiu a solicitação** | Concluída | 27/08 manhã |
| "Finaud escreveu — aguarda retorno do cliente" (49x) | **4 submotivos abaixo** | Aguardando Cliente | 27/08 manhã |

**4 submotivos (Aguardando Cliente):**
1. Finaud solicitou extrato ou planilha — aguarda envio
2. Finaud deu orientação técnica — aguarda execução
3. Finaud propôs reunião ou ligação — aguarda confirmação
4. Finaud fez pergunta — aguarda resposta

---

### ❌ Motivos ainda pendentes de decisão

| Motivo atual | Qtd | Situação |
|---|---|---|
| "Cliente escreveu — aguarda resposta da Finaud" — restante | ~130x | **Investigar antes de nomear** — o sistema não identificou o padrão; entender o que são antes de definir o texto (próximo chat) |
| "Fix R: cliente prometeu retornar..." | ~0x banco | ✅ Texto aprovado: **"Cliente prometeu retornar com informações — aguarda retorno"** — aguarda implementação |
| "Cliente enviou saudação — possível entrega de arquivo" | 13x | ✅ **Bug Outlook CORRIGIDO** (commit `bce6add`, 29/08). Das 16 threads: 3 mudaram de motivo (conteúdo real recuperado), 13 são genuinamente saudação. **Pendente:** aprovar texto final do motivo para as 13 que ficaram. Ver artefato: https://claude.ai/code/artifact/30448858-e3b1-4a40-a64d-4b989b0b7029 |
| "Finaud enviou arquivo sem linguagem de entrega" | 5x | ✅ Texto aprovado: **"Finaud enviou arquivo — aguarda retorno do cliente"** — aguarda implementação |

---

### Investigação pendente — antes de nomear o grupo restante

Os ~130 e-mails que sobram da caixa preta (nenhum padrão de entrega nem pergunta detectado) precisam ser investigados:
1. O que está nesses e-mails que o sistema não consegue identificar?
2. É possível melhorar a detecção e reduzir esse grupo?
3. Só depois de investigar: nomear o que sobrar de forma honesta.

**Quando fazer:** próximo chat dedicado — não implementar nada enquanto esta análise não estiver concluída.

---

### Implementação — quando todos os motivos estiverem aprovados

1. Alterar `_determinar_status()` em `scripts/banco_threads.py` com os novos textos
2. Expandir detecção de entrega: incluir "Seguem" em qualquer posição + "Anexo" como palavra solta + "Enviado" no passado
   - Caso real confirmado (29/08/2026): Brazabank (RE: DRM 05.2026) — corpo "Enviado o DDR de 29/05 ajustado e DRM referente a 05/2026 de substituição" não é detectado como entrega. Após o fix do `_so_cortesia()` este thread saiu da saudação mas caiu na caixa preta ("Cliente escreveu — aguarda resposta da Finaud"). Quando "enviado" for adicionado como termo de entrega, será classificado como "Cliente enviou informações e extratos — aguarda processamento".
3. Rodar `pytest tests/ -q` — zero regressões
4. Recalcular todos os registros com `recalcular_status_todos()`
5. Testar na tela de e-mails
6. Commitar

**Quando fazer:** após todos os motivos estarem aprovados — incluindo o grupo restante da caixa preta.

---

## TELAS — Alerta de motivos não identificados (identificado em 27/08/2026)

Quando um e-mail cair no motivo genérico ("fundo de gaveta"), o sistema precisa alertar Michel para que a regra possa ser corrigida. **O que não pode é acontecer sem que saibamos.**

**Decisões de Michel (27/08/2026):**

- **Badge visual na tela de e-mails** — descartado: Michel pode não acessar a tela num dia e perder o alerta
- **Contador no painel principal** — descartado como está: poluiria a tela do usuário. Aprovado apenas numa **tela gerencial separada** (formato planilha), onde todas as threads com motivo genérico ficam listadas para revisão
- **Relatório periódico por e-mail** — aprovado: uma vez por semana, o sistema envia um e-mail listando as threads que caíram no motivo genérico naquela semana

**O que fazer:**
1. Definir qual é o motivo genérico oficial (o "fundo de gaveta") — saída desta sessão
2. Implementar envio de e-mail semanal com threads nesse motivo
3. Criar tela gerencial (formato planilha) com listagem de threads por motivo — ver item abaixo

**Quando fazer:** após a definição dos motivos estar concluída nesta sessão.

---

## TELAS — Tela de gerenciamento de motivos + caixa preta (identificado em 27/08/2026)

**Prioridade: ALTA — Michel quer atacar junto com os e-mails da caixa preta.**

Tela de configuração/gerenciamento onde Michel (e a IA) possam:
1. Ver todos os motivos cadastrados com seus exemplos reais (como a análise feita em sessão de 27/08)
2. Consultar o que cada motivo significa sem precisar abrir o código
3. Ver os e-mails que caíram na "caixa preta" (motivo genérico) para revisar e criar novas regras
4. Adicionar ou ajustar regras sem precisar de sessão com a IA para isso

**Decisão de Michel (27/08/2026):** avaliar se caixa preta e gerenciamento de motivos ficam numa única tela ou em telas separadas — definir quando chegar na implementação.

**Por que é prioritária:** evita horas de sessão com a IA para ver regras e exemplos; Michel gerencia sozinho e só aciona a IA para dúvidas e ajustes.

**Quando fazer:** próxima fase após definição completa dos motivos nesta sessão.

---

## TELAS — Tela de notificações no app (identificado em 27/08/2026)

Michel pediu uma tela de notificações bem organizada dentro do app — centraliza avisos do sistema (motivos não identificados, alertas de prazo, atualizações importantes) em vez de depender só de e-mail ou badges espalhados.

**Quando fazer:** fase futura — após as telas principais estarem estáveis em produção.

---

## SERVIDOR VPS — Manutenção de infraestrutura

### 🟡 VPS — Python 3.9 desatualizado — risco de segurança futuro (identificado 25/08/2026)

O servidor Hostinger (`31.97.82.203`) roda **Python 3.9**, que já não recebe mais atualizações de segurança do Google (bibliotecas `google-api-core`, `google-auth` etc.) e ficará sem suporte de segurança em geral. Todos os apps da Finaud no VPS são afetados:

- `/srv/finaud/auditoria` (Auditoria IA)
- `/srv/finaud/tec/normativos` (Normativos)
- `/srv/finaud/tec/leiautes_bacen` (Leiautes)
- `/srv/finaud/tec/gestao_area_suporte` (Gestão Área Suporte)
- `/srv/finaud/portal-auth` (Portal Auth)

**O que fazer:** atualizar o Python do servidor para 3.10 ou superior (preferencialmente 3.11 ou 3.12) e retestar todos os apps. Verificar compatibilidade dos `requirements.txt` de cada app antes de atualizar.

**Quando fazer:** não é urgente agora — o sistema funciona. Planejar para uma janela de manutenção com o responsável do servidor.

**Impacto se não fizer:** com o tempo, pacotes de segurança deixarão de ser compatíveis com Python 3.9 e o servidor ficará vulnerável.

---

## COLETOR — Mostrar nome do colaborador Finaud em vez de "suporte" (identificado em 26/08/2026)

### O problema

Quando um colaborador da Finaud (ex.: Sarah Sá) responde a um cliente usando o endereço de grupo `suporte@finaud.com.br`, a mensagem chega assim no banco:

```
remetente: "Sarah Sá" <suporte@finaud.com.br>
reply_to:  (vazio)
```

O nome "Sarah Sá" **já está gravado** — o problema é que a tela e o classificador usam o endereço de e-mail (`suporte@finaud.com.br`) para identificar quem enviou. O resultado é que aparece "suporte" em vez de "Sarah Sá".

Compare com um cliente respondendo pelo mesmo grupo:

```
remetente: "'Leonardo Ueda' via Suporte" <suporte@finaud.com.br>
reply_to:  Leonardo Ueda <Leonardo.Ueda@westernunion.com>
```

O cliente traz "via Suporte" no nome — o colaborador Finaud **não traz**. Esse padrão é o que permite distinguir os dois casos.

### Por que é importante

- **Na tela:** hoje a thread aparece como enviada por "suporte", sem indicar quem da equipe respondeu.
- **No classificador:** uma resposta de Sarah a um cliente pode ser erroneamente tratada como e-mail novo de cliente, em vez de resposta de colaborador interno.
- **Para auditoria:** saber que Sarah respondeu (e não apenas que o grupo suporte respondeu) é informação de gestão.

### Como fazer

**Passo 1 — resolver o remetente real (em `coletor_gmail.py` ou `banco_threads.py`):**

Ao salvar uma mensagem, verificar:
- Se o `remetente` termina em `<suporte@finaud.com.br>` **e não contém "via Suporte"** → é um colaborador Finaud.
- Nesse caso, extrair o nome da parte antes do `<` (ex.: "Sarah Sá") e gravar um campo `remetente_real = "Sarah Sá (via suporte)"` — ou simplesmente preferir o nome na exibição.

**Passo 2 — exibir o nome na tela:**

Na tela de e-mails, onde o remetente é mostrado, usar o nome extraído do `From` em vez do endereço de e-mail quando o endereço for `suporte@finaud.com.br`.

**Passo 3 (opcional) — usar no classificador:**

Ao classificar, se o remetente real for da Finaud (nome sem "via Suporte" + endereço suporte@finaud.com.br), considerar como mensagem INTERNA (não como novo pedido de cliente).

### Evidência dos dados (26/08/2026)

Varrido o banco de produção. Padrão confirmado em 5 amostras:
- Colaboradores Finaud: `"Sarah Sá" <suporte@finaud.com.br>` — reply_to vazio
- Clientes: `'Leonardo Ueda' via Suporte <suporte@finaud.com.br>` — reply_to com e-mail real do cliente

**Quando fazer:** futuro — não é urgente. Priorizar quando a tela de e-mails estiver com mais uso.

---

## TELAS — Gerenciar lista de bloqueio automático pela tela (identificado em 26/08/2026)

Hoje a lista de endereços que são bloqueados automaticamente antes de chegar ao classificador (`_ENDERECOS_EXATOS` em `scripts/validador_classificacao.py`) só pode ser alterada diretamente no código. Se aparecer um novo spam recorrente, é necessário abrir o código para adicionar o endereço.

**O que fazer:** criar uma tela de administração (ou uma seção na tela existente) onde o Michel possa adicionar ou remover endereços da lista de bloqueio sem precisar mexer no código. A lista seria persistida em arquivo de configuração (JSON ou similar) e lida pelo `validador_classificacao.py` na inicialização.

**Quando fazer:** futuro — não é urgente. O sistema tem a correção manual como alternativa enquanto isso.

---

## TELAS — Painel Unificado configurável (identificado em 26/08/2026)

**Ideia:** substituir a navegação por seções separadas por um único painel onde o usuário seleciona quais widgets quer ver (Classificação e Status, Evolução, FOG Visão Consolidada, Lista de Casos, FOG Evolução). Cada widget auto-atualiza no mesmo intervalo já configurado. O botão de tela cheia por widget (já implementado em 26/08) seria a base para fullscreen por widget dentro do painel.

**Por que:** o sistema fica em atualização contínua — um painel facilita monitoramento sem precisar navegar entre telas. Ideia levantada por Michel em 26/08/2026.

**Quando fazer:** futuro — não é urgente. Implementar quando a base atual estiver estável em produção.

---

## ✅ CLASSIFICADOR DETERMINÍSTICO — CONCLUÍDO (placar: 764/768 — 99,5%)

> Ciclo de revisão completo em 17/08/2026. C40–C57 aplicados. Objetivo ≥750/768 **superado**.
> 4 residuais confirmados por Michel (ver seção abaixo). Sem novos erros identificados.

### ⚠️ RESIDUAIS — 4 confirmados por Michel (17/08/2026)

Threads sem correção viável com as ferramentas atuais. Determinístico erra em todas as 4. Aceitos por Michel; serão abordados na Fase 3 (OCR + leitura profunda).

- `INDICIO 2061 - DLO MAIO` → DLO_2061 (gabarito) vs. RETORNO_BACEN (obtido) — "INDICIO" sempre = RETORNO_BACEN (decisão Michel, 17/08)
- `RES: Erro do DRM e DLO` → RETORNO_BACEN (gabarito) vs. DLO_2061+DRM_2060 (obtido) — erro do BACEN em imagem; corpo textual menciona só DRM/DLO
- `RES: ARQUIVO DRM - AZUMI` → RETORNO_BACEN (gabarito) vs. DRM_2060 (obtido) — mesmo motivo
- `Re: Arquivos Regulatórios - ZIIN` → DLO_2061 (gabarito) vs. SUPORTE (obtido) — "DLO (2061)" em texto citado, além do limite de leitura do determinístico

---

### ✅ Convite Teams com assunto CADOC — resolvido pela C57 (17/08/2026)

Nova filosofia (C57): qualquer menção a CADOC = categoria CADOC. Gabaritos das 2 threads atualizados de SUPORTE → DLO_2061. Classificador agora acerta os dois casos.

- `(sem assunto)` → DLO_2061 ✅ (gabarito corrigido)
- `DLO` → DLO_2061 ✅ (gabarito corrigido)

---

### ✅ VMTM no corpo (sub-padrão 2a) — resolvido em C51–C54 (15–16/08/2026)

Gabaritos das 2 threads corrigidos de SUPORTE → DDR_2011 (C57 philosophy: VMTM menciona DDR → CADOC). Classificador acerta os dois casos no placar final.

---

### ✅ CADOC no corpo como contexto de pergunta (sub-padrão 2d) — resolvido pela C57 (17/08/2026)

Nova filosofia (C57): qualquer menção a CADOC no corpo = categoria CADOC. Gabaritos das threads atualizados de SUPORTE → categoria CADOC correspondente. Classificador acerta todos os casos no placar final de 764/767.

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

### ✅ Grupo C — Concluído (14 de 14 resolvidos)

✅ Resolvidos: PLANNER, DLO MAIO, ATUAL CORRETORA, DLI MAIO (C32) + Guru CTVM, COS 4010 junho, DRM 2060 Traders (C32) + AMARIL FRANKLIN 06 e 07 (C33) + DRM 05.2026 (C34b: "Enviado o DDR" no corpo) + Encaminhar composição fundo (C34c: DRM+DRL juntos no corpo) + Arquivo 2061. Segue o DLO 05/2026 (C35b: erro de gabarito — DLI removido) + MIRAE DRM junho/2026 (C36: gabarito DRM+DLO + COS4010 no anexo → DLO)

---

### ✅ Grupo D — Categoria extra adicionada indevidamente (RESOLVIDO em 15/08/2026)

O classificador acertava as categorias certas mas adicionava uma categoria extra.
*(Todos os 10 itens resolvidos — 7 por C40–C46, 1 por C47, 1 por C48, 1 por gabarito C37.)*

| Thread | Esperado | Situação |
|---|---|---|
| ~~Re: Planilha DRL-LEC Junho/2026~~ | ~~DLI+DLO~~ | ✅ C42 |
| ~~Re: REMITLY - Encaminhar COS4010 e LEC maio/2026~~ | ~~DLI+DLO~~ | ✅ C42+C46 gabarito |
| ~~RES: VIS : STA - DDR2011 e demais não disponíveis~~ | ~~DDR~~ | ✅ C40 (varredura 15/08) |
| ~~duvidas finaud~~ | ~~DLO~~ | ✅ C40–C46 (varredura 15/08) |
| ~~Re: Arquivo 2061 e 2062. Segue o DLI. ACCREDITO.~~ | ~~DLI~~ | ✅ C41 |
| ~~Re: COS4016 DE 06-2026. Segue o 4111. FAIRWAY~~ | ~~SCD~~ | ✅ C39/C38 (varredura 15/08) |
| ~~Saldos do dia 20/07 até 22/07~~ | ~~SCD~~ | ✅ C47 |
| ~~Saldos do dia 27/07 (retificação) e 28/07~~ | ~~DDR+SCD~~ | ✅ C37 (gabarito correto era DDR+SCD — ambos os arquivos presentes) |
| ~~Pendencias BACEN - 2011 ref. 30/01/2026~~ | ~~SCD~~ | ✅ C48 |
| ~~Remitly CC - 4010/4016 - 06/2026~~ | ~~DLO~~ | ✅ C40/C43 (varredura 15/08) |

---

### ✅ Grupo E — SUPORTE indevido no gabarito (RESOLVIDO em 15/08/2026)

Michel revisou as 5 threads e confirmou que todas são entregas simples de CADOC — o classificador estava certo; o gabarito é que tinha SUPORTE errado.

| Thread | Gabarito corrigido para | Situação |
|---|---|---|
| ~~Posição de Câmbio CAM0050 BACEN 28/07~~ | ~~DDR~~ | ✅ Gabarito corrigido |
| ~~Erro - 2060 DRM~~ | ~~DRM~~ | ✅ Gabarito corrigido |
| ~~Re: DLO - 30.06.2026. ATUAL Corretora~~ | ~~DLO~~ | ✅ Gabarito corrigido |
| ~~Re: Risk Driver - Guru~~ | ~~DLO~~ | ✅ Gabarito corrigido |
| ~~DRL - Jun/26~~ | ~~DRL~~ | ✅ Gabarito corrigido |

---

### ✅ Grupo F — Casos individuais — CONCLUÍDO (17/08/2026)

*(FREEX COS4010, Executive Corretora S5 e VBS SCD corrigidos em 14/08/2026 — C44, C45, C46.)*

| Thread | Esperado | Situação |
|---|---|---|
| INDICIO 2061 - DLO MAIO | DLO_2061 | ⚠️ RESIDUAL — ver seção de residuais acima |
| ENC: Risk Driver - CV INVESTIMENTOS | DLO+SUPORTE | ✅ Resolvido em C51–C54 (15–16/08) |
| Divulgação Instrução Normativa BCB nº 761 | INTERNO | ✅ C55 (17/08): padrão DIVULGAÇÃO INSTRUÇÃO NORMATIVA adicionado → INTERNO detectado |
| Re: Solicitação de treinamento – FREEX | S5 | ✅ Resolvido em C44–C46 (14/08) |

---

## ⏭ ETAPA ATUAL — App no ar; o que falta não é “subir a Fase 1”

> **✅ Produção no ar desde 25/08/2026:** `https://gestao-suporte.finaudapps.com.br` (Sair → portal aprovado em 26/08).
> **✅ Classificador determinístico concluído: 764/768 (99,5%) em 17/08/2026.**
> **Escopo redefinido em 17/08/2026:** sem IA por enquanto. O classificador determinístico é o único classificador.
> **26/08/2026 — Michel:** não vamos usar IA na classificação. O item SPEC §10 saiu desta lista. A IA (GPT-4o-mini, OCR, IA Assistente) permanece só como fase futura — ver seção ao final deste arquivo.

### ✅ AMOSTRA — Resolvido em 17/08/2026

- Caso 1 "[CV INVEST] DLO - 05/2026" → ✅ determinístico retorna DLO_2061 correto
- Caso 2 "FLUXO DE CAIXA - ZIIN" → ✅ determinístico retorna DDR_2011+SCD_4111 correto
- Caso 3 "RES: Erro do DRM e DLO" → movido para Fase 3 (OCR) — erro do BACEN está em imagem, sem OCR não há sinal detectável

---

### ✅ CLASSIFICADOR — §10 hierarquia de regras — resolvido em 17/08/2026

O classificador determinístico (C40–C57) passou a classificar 134/134 threads que o R6 retornou como INCERTO. Hierarquia de regras resolvida pela abordagem determinística — sem necessidade de reformular o §10 da spec para o GPT.

---

### ✅ CLASSIFICADOR — LEC: resolvido em 17/08/2026

Threads LEC ("Relatório 2061 - Ajuda na importação da planilha LEC", "Planilha LEC e ponderação 05/2026", "Fwd: Encaminhar a planilha LEC 06 2026 - MIRAE.") agora classificadas como DLO_2061 pelo determinístico. Sem regressões.

---

### ✅ CLASSIFICADOR — "Planilha LEC" INCERTO — resolvido em 17/08/2026

As 2 threads ("Fwd: Encaminhar a planilha LEC 06 2026 - MIRAE." e "Planilha LEC e ponderação 05/2026") agora retornam DLO_2061 pelo determinístico. Resolvido pelas melhorias C40–C57 sem alterar a spec.

---

### ✅ CLASSIFICADOR — 134 incertos — resolvido em 17/08/2026

Determinístico classifica 134/134 threads que o R6 retornou como INCERTO. Todos os casos DDR sem sinal no assunto (VMTM, Cadastro, COSIF, CNPJ, POSICAO, 2011-LIM) e keywords LEC agora detectados pelas regras C40–C57. Sem necessidade de enrichment da spec.

---

### ✅ TELAS — Painel delta (variação entre rodadas) — resolvido em 21/08/2026

Implementado como colunas VAR separadas na tabela principal (AF/VAR/AC/VAR/CO/VAR/TOTAL/VAR — 10 colunas). Abordagem aprovada por Michel: mais compacto e integrado do que o painel recolhível do protótipo. Delta calculado via `ler_penultimo_snapshot()` (fim da rodada N-1 vs. fim da rodada N). Commit `facf13c`.

---

### 🟡 BANCO — Adicionar campo `tipo_status` para rastreabilidade (identificado 18/08/2026)

Ideia de Michel: além do `motivo_status` (texto livre), salvar um campo estruturado `tipo_status` com categorias fixas — ex.: "ação_cliente", "cortesia", "entrega", "forward", "interno". Permite filtrar, auditar e construir relatórios.

**O que fazer:**
1. Definir com Michel o conjunto de tipos (mapeamento completo)
2. Adicionar coluna `tipo_status TEXT` no banco via migração segura
3. Preencher ao recalcular status em `_determinar_status()`
4. Atualizar a tela para exibir ou filtrar por tipo

**Por que ainda não foi feito:** requer decisão de design antes de implementar (envolve schema do banco e mudança em todas as branches de status).

---

### 🟡 SPEC — Definir comportamento em produção: threads novas vs. já classificadas (identificado 07/08/2026)

**Contexto:** em produção, novas threads chegam diariamente e threads existentes recebem novos e-mails. O sistema precisa saber o que fazer em cada caso.

**O que precisa ser definido:**
- Thread nova (nunca vista) → classifica e grava a categoria
- Thread já classificada + novo e-mail chegou → reclassifica? Ou atualiza só o status?
- Thread classificada manualmente (Tela de Revisão) → protege da reclassificação automática?
- Como o sistema sabe o que já foi processado → banco de Thread IDs já vistos

**Onde documentar:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §8 ou nova seção de ciclo de vida.

---

### 🟡 CLASSIFICADOR — Verificar dupla categoria: "COS 4010 junho/2026" (identificado 07/08/2026)

Thread classificada como SALDOS_CONTABEIS_DIARIOS_4111 + DLO_2061 com alta confiança. A IA viu COS4010 no assunto (→ DLO_2061) e "retificação do Doc 4111" no corpo (→ SALDOS_CONTABEIS_DIARIOS_4111). Michel considerou correto por ora.

**Dúvida:** o cliente tratava das duas entregas ao mesmo tempo ou só do DLO?
**Quando revisar:** fase 3 — após corrigir erros confirmados e resolver os INCERTO.

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

### 🟡 LIMPEZA — Rótulo do Outlook aparece como primeira linha do texto (identificado 18/08/2026)

Alguns e-mails gerados pelo Outlook têm um rótulo de classificação automático ("Classificação: Interno e Parceiros de Negócios") na primeira linha do corpo, antes do conteúdo real. O extrator `_extrair_texto_novo()` captura esse rótulo como se fosse a primeira linha da mensagem.

**Impacto atual:** 35 threads com esse padrão. Status não é afetado (o conteúdo real vem logo depois), mas o rótulo polui o texto que seria enviado para a IA classificar.

**O que fazer:** ao construir o módulo de limpeza de corpo na Fase 1, adicionar filtro para remover linhas que começam com `Classificação:` seguido de categorias do Outlook.

**Arquivo de destino:** módulo de limpeza do corpo — Passo 3 da Fase 1.

---

### ✅ STATUS — Threads de 1 msg do cliente com "Favor + verb" classificadas como Concluída — resolvido em 24/08/2026 (Fix U)

Causa real identificada: "Favor considerar... Obrigado." → "Obrigado" ativava Fix H → Concluída. A hipótese original (`_eh_cortesia_finaud("")`) estava incorreta — essa função só é chamada no branch Finaud, não no branch cliente.

Fix U aplicado: `\bfavor\b` adicionado ao `_PEDIDO_IMPLICITO` → bloqueia Fix H para qualquer mensagem com "Favor". 3 testes novos. 374 passando.

Casos originais corrigidos manualmente no banco (24/08/2026):
- `19ff7486cc830e8c` → AF
- `1a02411449b1e9c8` → AF

**Risco residual:** clientes que enviam pedidos sem a palavra "Favor" (ex.: "Considerar o valor +USD $331,463.18. Obrigado.") ainda caem no Fix H → Concluída. Corrigidos manualmente onde identificados; sem regra automática para cobrir imperativo sem "Favor".

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

### ✅ FILTRO §4 — E-mails automáticos com código de verificação e "via plataforma" — resolvido em 17/08/2026

Adicionados 2 padrões a `eh_automatico()` em `validador_classificacao.py`:
- Assunto com "código de verificação/acesso/segurança" ou "verification code" → filtrado
- Nome do remetente com "via Microsoft/Google/LinkedIn/Apple" → filtrado
11 testes adicionados em `tests/test_validador_filtro.py`. 206/206 passando.

### 🟡 FILTRO §4 — E-mails automáticos roteados via suporte@ — situação residual (identificado 06/08/2026)

Durante a validação com 768 threads, identificamos que e-mails automáticos que chegam **roteados pelo endereço `suporte@finaud.com.br`** não são barrados pelo filtro §4. O remetente original (ex.: Microsoft) fica escondido no **nome** do campo remetente (`'cvpar.com.br (via Microsoft)' via Suporte`), mas o endereço de e-mail aparece como `suporte@finaud.com.br` — que não está na lista de bloqueios.

**Exemplo confirmado por Michel (06/08/2026):** assunto `Seu código de verificação da conta de cvpar.com.br` — e-mail automático da Microsoft com código de acesso. Conteúdo irrelevante para o projeto. Passou pelo filtro, chegou à IA, que ficou incerta.

**O que fazer:** adicionar à função `eh_automatico()` detecção pelo **nome do remetente** quando contém padrões como `via Microsoft`, `via Google`, `via LinkedIn`, ou quando o nome indica notificação automática (`código de verificação`, `verification code`, etc.).

**Arquivo a alterar:** `scripts/validador_classificacao.py` → função `eh_automatico()`, e futuramente o coletor de produção.

---

### ✅ DADOS: Respostas da Finaud via suporte@ não chegavam ao banco — RESOLVIDO EM 18/08/2026

Causa raiz identificada: e-mails *enviados* via o grupo `suporte@finaud.com.br` não voltavam para `coleta.oraculo@finaud.com.br` — comportamento padrão do Google Groups. Correção: adicionado `suporte@finaud.com.br` à regra de roteamento "Cópia de segurança para IA - Interações Externas" no Google Workspace Admin. A partir de 18/08/2026, todos os envios via suporte@ chegam à caixa de coleta e entram no banco.

**Limitação residual:** e-mails enviados *antes* de 18/08/2026 não são recuperados por esta regra — o histórico dessas respostas permanece incompleto. Aceito como limitação; não bloqueia a Fase 1.

Ver detalhes em `documentações/REGISTRO_CORRECOES.md` — entrada de 18/08/2026 e `documentações/TAREFAS_AGENDADAS.md`.

---

### 🟡 ALINHAMENTO — IA e Michel precisam aprofundar entendimento sobre conteúdo e direcionamento dos e-mails (identificado 06/08/2026)

Durante a revisão dos casos da validação, Michel observou que a IA e ele ainda não estão alinhados sobre o conteúdo dos e-mails e seu direcionamento — a IA não tem clareza suficiente sobre o contexto de negócio por trás de cada tipo de interação.

**Exemplo concreto:** e-mail de cadastro de fundo para geração de DDR — a IA classificou como SUPORTE porque não havia DDR sendo entregue; Michel corrigiu explicando que o cadastro faz parte do fluxo DDR.

**O que fazer (posterior):** sessão dedicada para a IA aprender o contexto de negócio de cada categoria — como funciona o processo completo, quais interações fazem parte de cada fluxo regulatório, e o que parece SUPORTE mas é CADOC (e vice-versa). Não precisa ser feito antes da implementação, mas deve anteceder a primeira validação com dados reais em produção.

---

## ANTES DA FASE 3 — Ligar a IA

> Resolver tudo abaixo antes de conectar a IA classificadora.

---

### ⏸ OCR — RETORNO_BACEN — FASE FUTURA (movido em 17/08/2026)

> **Escopo atual:** o classificador identifica RETORNO_BACEN pelo assunto e corpo textual. OCR de imagens fica para quando a IA for conectada.

### ~~🔴 OCR — RETORNO_BACEN depende 100% das imagens para classificação e aprendizado~~ (identificado 30/07/2026 · Caso 3 AMOSTRA movido aqui em 17/08/2026)

Na análise do RETORNO_BACEN (1.298 e-mails), os elementos `[image:]` (36,3%) e `[cid:]` (41,0%) são os mais altos de todas as 12 categorias. Nesta categoria, o cliente envia **prints de tela** com as mensagens de erro do BACEN — o texto do e-mail diz apenas:

> *"Prezados, recebemos a seguinte crítica referente ao DLO de dezembro: [image: image.png]"*

O que está dentro da imagem é o erro real: código de crítica, conta contábil afetada, valor divergente. Sem ler a imagem, a IA recebe apenas a casca do e-mail.

**Impacto sem OCR:** a IA classifica como RETORNO_BACEN genérico sem entender o problema específico; o aprendizado da IA Assistente fica cego para o conteúdo mais importante desta categoria.

**Casos concretos que dependem de solução na Fase 3:**
- `RES: Erro do DRM e DLO` → determinístico retorna DLO+DRM; gabarito é RETORNO_BACEN (erro do BACEN em imagem — corpo informal sem sinal detectável em 600 chars)
- `RES: ARQUIVO DRM - AZUMI` → determinístico retorna DRM_2060; gabarito é RETORNO_BACEN (idem)
- `Re: Arquivos Regulatórios - ZIIN` → determinístico retorna SUPORTE; gabarito é DLO_2061 (menção ao DLO em texto citado, além do limite de leitura mesmo com 1.200 chars)

**O que decidir antes da Fase 3:**
1. Garantir que OCR está implementado antes de qualquer classificação de RETORNO_BACEN
2. Definir o que fazer se o OCR falhar: fila de revisão humana (já previsto pela regra L6)
3. Avaliar se é necessário OCR especializado para prints de sistema BACEN

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — Campo 6 (regra L6).

---

### ✅ CLASSIFICADOR — Convites de calendário (RESOLVIDO 07/08/2026)

Decisão tomada por Michel: qualquer e-mail com invite.ics ou link de reunião (Teams, Meet, Zoom) → **SUPORTE**, mesmo que o assunto mencione um CADOC. Registrado em §10 SUPORTE e §12 Decisões da spec.

---

### ⏸ IA ASSISTENTE — Como preservar o histórico completo para aprendizado — FASE FUTURA (identificado 30/07/2026)

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

## ✅ TELAS — §14 especificado em 17/08/2026

> As 3 telas foram definidas na spec (§14): Tela Principal, Tela de Revisão e Tela de Descartes.
> O design visual detalhado e a implementação fazem parte da Fase 1.

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

## ⏸ FASE FUTURA — IA e funcionalidades avançadas

> Itens abaixo ficam fora do escopo da Fase 1. Entram em discussão quando o sistema determinístico estiver rodando em produção.

| Item | O que é | Por que depois |
|---|---|---|
| GPT-4o-mini | Classificador de IA para casos que o determinístico não cobre | Precisamos de volume de classificações manuais (Tela de Revisão) para treinar e validar |
| OCR de imagens | Leitura de prints de erro do BACEN em RETORNO_BACEN | Depende da IA estar conectada; sem IA o OCR não traz benefício de classificação |
| IA Assistente de aprendizado | IA que aprende como cada caso foi resolvido e ajuda a responder | Depende de histórico classificado e validado |
| Preservação do histórico para aprendizado | Como guardar o corpo completo (com histórico citado) antes de limpar | Depende da IA Assistente estar definida |
| §10 — 3 distinções da IA | Encerrado em 26/08/2026: Michel decidiu não usar IA na classificação | Não retorna à fila ativa |

---

## APÓS A FASE 1 ESTAR RODANDO

> Fazer depois que o sistema (coletor + classificador + 3 telas) estiver funcionando em produção.

---

### 🟡 BANCO/TELAS — Remetente mascarado: 645 e-mails de clientes guardados com suporte@finaud no lugar do cliente real (identificado 26/08/2026)

#### O que é o problema

Quando um cliente envia e-mail para `suporte@finaud.com.br`, o e-mail é entregue pelo **Google Groups** (lista de suporte). Nessa entrega, o Gmail **substitui o remetente original** pelo endereço da lista. O campo `From` do e-mail, que deveria trazer o cliente, chega assim:

```
"'George Lucas Ramos Junckes' via Suporte" <suporte@finaud.com.br>
```

Em vez do correto:

```
George Lucas Ramos Junckes <george.junckes@eqi.com.br>
```

O nosso coletor (`scripts/coletor_gmail.py`, linha 129) lê o campo `From` e grava esse valor mascarado no banco como `remetente_principal` e como `remetente` de cada mensagem no JSON interno.

#### O que foi verificado (26/08/2026)

Varredura completa do banco de produção (`/srv/finaud/tec/gestao_area_suporte/data/gestao.db`) com 1.589 threads:

| Situação | Qtd |
|---|---|
| Threads com remetente mascarado (`suporte@finaud.com.br`) | 675 (42,5%) |
| → Clientes externos reais com dado errado no banco | **645** |
| → Sarah Sá / Pedro Silva / suporte genérico (Finaud enviando pela lista — dado correto) | ~20 |
| → Facebook/redes sociais roteados pela lista (automáticos) | ~6 (já filtrados) |

O e-mail bruto contém campos que revelam o remetente real:
- `X-Original-From: George Lucas Ramos Junckes <george.junckes@eqi.com.br>` — nome + e-mail real
- `X-Original-Sender: george.junckes@eqi.com.br` — só o e-mail real
- `Reply-To: George Lucas Ramos Junckes <george.junckes@eqi.com.br>` — já coletamos; resolve 645/645 casos

A Gmail API no formato `full` já retorna todos esses cabeçalhos. Hoje só lemos `From` e `Reply-To`. Os campos `X-Original-From` e `X-Original-Sender` chegam mas são ignorados.

#### O que o problema afeta — e o que NÃO afeta

**Não afeta (já resolvido no código atual):**

- **Tela principal de classificação e status** (`scripts/servidor_telas.py`, linha 405): já tem lógica que detecta `suporte@finaud` no remetente e usa o `Reply-To` no lugar. A coluna "DE" que Michel vê na tela já mostra o cliente correto — confirmado em tela em 26/08/2026.
- **Classificador determinístico** (`scripts/classificador_regras.py`): não usa o campo remetente em momento algum — classifica apenas por assunto, corpo e nome dos anexos. Completamente imune.
- **Lógica de status** (`scripts/banco_threads.py`, linha 366): já tem tratamento específico — quando vê `suporte@finaud` como remetente com Reply-To externo, entende que é cliente, não Finaud.
- **Filtro de automáticos** (`scripts/validador_classificacao.py`, função `eh_automatico()`): `suporte@finaud.com.br` não está na lista de bloqueados — e-mails de clientes passam normalmente. Correto.

**Afeta (problema cosmético e de qualidade de dado):**

- **O campo `remetente_principal` no banco**: guarda o valor mascarado. Dado de base incorreto, mesmo que as telas principais já contornem.
- **Telas secundárias** (`servidor_telas.py`, linhas 476 e 495): listagens de descartados e outras que usam `remetente_principal` diretamente sem o tratamento. Podem mostrar `suporte@finaud.com.br` em vez do cliente.
- **Qualidade do dado histórico**: se no futuro alguém exportar ou analisar o campo `remetente_principal` diretamente (relatório, BI, nova tela), receberá `suporte@finaud.com.br` nos 645 casos — sem o dado real do cliente.

#### Proposta de correção

**Parte 1 — Coletor (novos e-mails):** ao processar cada mensagem em `_processar_mensagem()` (`coletor_gmail.py`, linha 114), antes de gravar o `remetente`, verificar:

1. Se `From` contém `suporte@finaud.com.br` → tentar `X-Original-From` (já vem na API, só não é lido)
2. Se `X-Original-From` não existir → tentar `X-Original-Sender`
3. Se nem esse existir → manter `From` (fallback seguro)

Isso garante que todos os novos e-mails entrem no banco já com o remetente correto — sem precisar tratar nas telas.

**Parte 2 — Banco histórico (retroceder os 645 casos):** script de migração que percorre as 645 threads mascaradas, lê o `Reply-To` que já está salvo no JSON interno das mensagens, e atualiza o campo `remetente_principal` (e o `remetente` de cada mensagem no JSON). Antes de rodar: backup obrigatório em `data/backups/`.

**Parte 3 — Telas secundárias:** após a Parte 2, os campos já estarão corretos no banco — as telas que hoje usam `remetente_principal` direto passarão a mostrar o dado certo automaticamente, sem mudar o código delas.

#### Por que não é urgente

A tela que Michel usa diariamente já mostra o cliente correto. O classificador e o status funcionam bem. O problema é de qualidade do dado de base — relevante para o futuro (relatórios, novas telas, auditoria) mas sem impacto operacional hoje.

#### Arquivos a alterar

| Arquivo | O que muda |
|---|---|
| `scripts/coletor_gmail.py` | `_processar_mensagem()` — lógica de fallback para remetente: `X-Original-From` → `X-Original-Sender` → `From` |
| Script de migração (novo, descartável) | Percorre 645 threads mascaradas e atualiza `remetente_principal` + JSON usando o `Reply-To` salvo |
| `data/backups/AAAAMMDD_HHMM_fix_remetente/` | Backup obrigatório antes de rodar a migração |

**Quando fazer:** após a Fase 1 estar estável em produção — não bloqueia nada hoje.

---

### 🟡 CLASSIFICADOR — Avaliar remoção do limite de 3 mensagens por thread (identificado 19/08/2026)

Hoje o classificador lê apenas as 3 primeiras mensagens de cada thread. Uma simulação mostrou que, sem esse limite, 120 threads seriam reclassificadas — a maioria adicionando uma segunda categoria CADOC (ex.: DLO + DLI, DDR + SCD).

**Por que não mexer agora:** o sistema está funcionando bem (764/768). O impacto é grande e a decisão requer definir primeiro como distinguir entrega genuína de referência de passagem no corpo da mensagem.

**O que decidir antes de implementar:**
1. Estratégia de classificação: assunto manda (se sujeito já tem CADOC, corpo só confirma) vs. todos os sinais valem
2. Revisar as 5 threads onde a categoria *muda* (não adiciona) para confirmar se a nova classificação seria correta
3. Decidir se threads multi-categoria (DLO+DLI genuínos) devem ou não aparecer nas duas filas

**Arquivo a alterar:** `scripts/classificador_regras.py` — linha `for msg in mensagens[:3]`

---

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

### ✅ STATUS — Pente fino das AF — concluído (24/08/2026)

Pente fino completo das AF (todas as categorias). 8 correções manuais no banco. ~99% das threads estavam corretas. Ver `REGISTRO_CORRECOES.md` entrada 24/08 para detalhes.

---

### 🟡 MOTIVOS — Verificar cobertura em produção antes de montar a planilha (identificado 29/08/2026)

Após fechar o artefato de motivos (19 aprovados), rodar script que cruza todos os
`motivo_status` distintos no banco de produção com a lista aprovada — confirmar que nenhuma
thread ficou com motivo fora da lista. Só depois montar a planilha `matriz_classificacao_motivos.xlsx`.

**Script:** contar `SELECT motivo_status, COUNT(*) FROM threads GROUP BY motivo_status` e
comparar com os 19 motivos do artefato.

**Quando fazer:** imediatamente após o artefato ser fechado (Passo 1 do próximo chat).

---

### 🟡 TELA — Gerencial de busca por assunto (identificado 29/08/2026, futuro)

Michel pesquisa um assunto e a tela traz todas as informações da thread (status, motivo,
razão, histórico) sem precisar navegar pela tela de status atual. Pensado para buscar casos
específicos durante manutenções ou investigações.

**Quando fazer:** após a tela de regras estar funcionando (Passo 4 do próximo chat).

---

### 🟡 TELA FOG — Discussões do Google Chat vinculadas a casos (identificado 21/08/2026)

No projeto antigo, alguns cards da tela operacional do FOG mostravam mensagens do Google Chat vinculadas ao número do caso. Michel confirmou que quer avaliar manter esse recurso, mas foi postergado para não bloquear a implementação principal das telas FOG.

**O que decidir antes de implementar:**
1. O vínculo Google Chat ↔ caso FOG ainda acontece? Por qual mecanismo?
2. Onde estão esses dados hoje? (No projeto antigo vinham de `massa_bruta_fog.json`)
3. A exibição seria dentro do card (colapsável) ou em tela separada ao clicar?

**Quando fazer:** após as telas FOG (operacional + gerencial) estarem funcionando em produção.

---

### 🟡 TELA E-MAILS — Drill-down de categoria na tela Evolução (identificado 25/08/2026)

Hoje a tela Evolução mostra todas as categorias numa tabela com variações. A ideia é: ao **clicar numa categoria**, abrir um painel mostrando como aquela categoria específica se comportou ao longo do tempo (dia a dia ou semana a semana) — com um gráfico de linha para AF, AC e CO.

**Por que faz sentido:** a tabela é ótima para comparar todas as categorias ao mesmo tempo. O gráfico de linha faz sentido somente quando o foco é **uma categoria só**, mostrando tendência ao longo do tempo (ex.: "SALDOS_4111 estava em 9 há 3 semanas, subiu para 13 semana passada e caiu para 12 hoje").

**O que é necessário antes de implementar:**
1. Verificar se os snapshots salvos têm granularidade suficiente (diária) para traçar uma curva útil
2. Definir o visual: painel lateral, modal ou seção expansível abaixo da linha clicada?
3. Definir o período máximo exibido (últimos 30 dias? 90 dias?)

**Quando fazer:** após a Fase 1 estar estável em produção.

---
