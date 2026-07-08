# REVISÃO DE TELAS — Oráculo 360 Finaud

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

**Início:** 2026-07-01
**O que é:** revisão de cada tela do sistema como se fosse a primeira vez de um usuário novo —
buscando confusão, falta de clareza, informação que falta ou que engana, fluxo quebrado.
**Como funciona:** Michel e a IA navegam juntos pelo navegador embutido do console. A cada
achado, vira uma pendência numerada abaixo — nada é corrigido nesta sessão, só documentado.
**Quando ajustar:** cada pendência aqui migra para `PENDENCIAS.md` (ou vira correção direta,
seguindo o protocolo do `CLAUDE.md`) numa sessão futura, uma de cada vez.

**Regra desta revisão:** nenhuma pendência fica com dúvida. Se o "porquê" ou o "como corrigir"
não estiver 100% claro no momento em que for escrito, a IA para e pergunta antes de registrar.

---

## Formato de cada pendência

> ### N. Título curto do achado
> - **Tela:** onde exatamente (menu → submenu → elemento)
> - **O que vimos:** fato observado, sem interpretação
> - **Por que incomoda:** o problema concreto pra quem usa o sistema
> - **O que fazer:** sugestão de ajuste (ou "a definir" se ainda não sabemos)
> - **Impacto se não mexer:** o que continua confuso/errado enquanto não for corrigido

---

## Pendências encontradas

### 1. Redesenho da tela inicial (Visão Geral) — card único de e-mails + FOG/Normativos corrigidos + limpeza de seções

- **Tela:** Home / Visão Geral (`templates/index.html`, rota `/`)

- **O que vimos (fatos confirmados no código e ao vivo no navegador):**
  1. A tela mostrava 5 cards no topo: "E-mails Pendentes" (0), "FOG (Em Aberto)" (0), "Normativos (Hoje)" (0), "Fluxos Atrasados" e "Aguardando Resposta" (996, 877 vencidos).
  2. **"E-mails Pendentes" e "FOG (Em Aberto)" sempre mostram 0:** os dois buscam dados em `/api/dados` **sem informar uma data**. Testado ao vivo: chamando esse endereço sem data → 0 registros; com `?data=2026-07-01` → 106 registros reais. Ou seja, esses dois cards nunca vão mostrar o número certo, não importa o dia.
  3. **"Normativos (Hoje)" é um número morto:** o HTML fixa o valor em "0" e nenhum trecho de JavaScript jamais escreve outro valor nele — não está ligado a nenhum dado.
  4. **"Aguardando Resposta" (996/877 vencidos) é o único dos 5 que funciona certo** — busca de `/api/threads_aguardando`, endereço diferente dos outros dois.
  5. A saudação dizia genericamente "operação hoje" sem mostrar a data real da última carga.
  6. Existia uma seção "Acesso Rápido" (Fluxo Recorrente, Normativos, Configurações, Sair) e dois botões no topo ("Ir para E-mails", "Ir para Fogs").

- **Por que incomoda:** os 3 primeiros cards que um usuário novo vê dizem "0, 0, 0" — passando a falsa impressão de que está tudo em dia — enquanto existem 996 e-mails aguardando resposta (877 vencidos). "Aguardando Resposta" e "E-mails Pendentes" soam como o mesmo conceito mas mostram números completamente diferentes. A seção "Acesso Rápido" duplica um botão de Sair que já existe no cadastro do usuário.

- **Decisão tomada com Michel (validada em 01/07/2026):**
  1. **Um único card de e-mails**, mostrando os mesmos 4 números que já existem na tela de Triagem (`email_operacional.html`): **Pendente, Aguardando, Concluído, Não resolvidos**.
  2. **Caminho A escolhido:** a Home e a Triagem **têm que usar o mesmo cálculo internamente** — não pode haver dois lugares calculando o mesmo número de jeitos diferentes. Isso exige **extrair a lógica de contagem hoje presa dentro de `email_operacional.html`** (função `renderKPIs` + a montagem das listas `threadsAbertos/threadsAguardando/threadsConcluidos/threadsNaoResolvidos`, ~200 linhas com fusão de pares e agrupamento por assunto) para um lugar comum, e a Home passa a chamar esse mesmo lugar. É mais trabalho que um cálculo simples, mas garante que os dois números **nunca divergem**.
  3. **"Concluído" conta o dia mais recente da carga**, não o total histórico (3.741) — junto com a saudação, tudo na Home reflete o dia mais recente de dados, não o total acumulado desde sempre.
  4. **Saudação nova:** "Olá, {nome do usuário}. Aqui estão as informações do dia XX/XX/XXXX." — a data vem do mesmo endereço que já existe no sistema (`/api/ultima_data_carga`), usado hoje pelo seletor de data de outras telas.
     - ⚠️ **Armadilha encontrada e corrigida (01/07/2026):** esse endereço devolve 2 campos — `ultima_data` (data do e-mail mais recente recebido) e `gerado_em` (quando o pipeline realmente rodou). Testado ao vivo: hoje `gerado_em = 2026-07-01 12:55`, mas `ultima_data = 2026-06-30` (não chegou e-mail novo exatamente hoje). Usar `ultima_data` mostraria a carga de hoje como se fosse "zero" — reproduzindo o mesmo bug que estamos corrigindo. **Decisão:** a Home usa `gerado_em` (dia em que a carga rodou) como a data única de referência da página — a mesma data vale para o card de e-mails, o de FOG e o de Normativos. Não precisa criar nenhum endereço novo para isso, o campo já existe.
  5. **FOG (Em Aberto) também precisa refletir dado real** (não mais 0 fixo). Já existe uma função pronta no sistema (`_carregar_eventos_fog()` + a mesma contagem de "ativos"/"críticos" usada em `/fog/gerencial`) — reaproveitar essa função em vez do cálculo quebrado atual, em vez de criar um cálculo novo.
  6. **Normativos (Hoje) também precisa refletir dado real.** Investigado: o arquivo de origem (`registros_id_emails_de_envios_ao_fog.json`) tem um campo confiável de data, `data_leitura` (ex.: `"01/07/2026 12:54"`), então dá para filtrar certo pelo dia mais recente. **Decidido com Michel (01/07/2026):** o card conta só os blocos/normas com `impacto_detectado=true` na data mais recente — ou seja, só o que realmente precisa de atenção, não o total lido no dia.
  7. **Remover da Home:** o card "Fluxos Atrasados" e o card "Aguardando Resposta" (ambos somem — o "Aguardando" e o "Não resolvidos" passam a viver dentro do novo card único de e-mails).
  8. **Remover a seção "Acesso Rápido" inteira** (Fluxo Recorrente, Normativos, Configurações, Sair) — o "Sair" já existe dentro do cadastro/menu do usuário, não precisa duplicar.
  9. **Remover os 2 botões do topo** ("Ir para E-mails", "Ir para Fogs").
  10. **✅ Decidido (01/07/2026) — comportamento quando não há carga rodada no dia: opção (B).** Se a tela for aberta num dia em que a carga ainda não rodou (ex.: abrir 02/07 sem carga daquele dia), os 3 cards ficam com "**--**" em vez de número — só mostram dado quando a carga tiver rodado exatamente no dia da visita. **Motivo da escolha (Michel):** quando o projeto estiver em produção, a carga vai rodar todos os dias — então o estado vazio da opção B será raro na prática, e não vale a pena aceitar a ambiguidade da opção A (mostrar dado de outro dia sem deixar isso óbvio o bastante) só por causa do período de testes atual, em que as cargas ainda são espaçadas.
      - **Como isso é verificado tecnicamente:** comparar a data de hoje (calendário) com `gerado_em` (a data/hora em que o pipeline rodou pela última vez, campo já existente em `/api/ultima_data_carga`) — só igual = mostra os números; diferente = mostra "--" nos 3 cards.
  11. **✅ Resolvido (01/07/2026 14:55) — nome na saudação:** Michel perguntou se a saudação usaria o nome do usuário ou o perfil/role. Conferido no código: já usa o nome (`current_user.name`), nunca o perfil — o problema era o dado. A conta de login (`admin`) tinha `"name": "Administrador"` gravado por engano. Corrigido para "Michel Rui Costa" e removida a conta duplicada `michelruicosta` que já tinha o nome certo. Detalhe completo da correção → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 14:55`.

- **Impacto se não mexer:** a tela inicial continua mostrando números que enganam (0 onde deveria mostrar 996), um card morto (Normativos), e seções redundantes que não agregam nada além do que já existe em outras telas.

- **Status:** ✅ **Implementado e validado em 01/07/2026 15:20.** Detalhe técnico completo da correção → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 15:20`.

---

### 2. Painel de Gestão — 6 achados + 1 validação de dados

- **Tela:** Painel de Gestão (`templates/painel_gestao.html`, rota `/painel/gestao`)
- **Backend:** `painel_oraculo.py` — funções `_casos_fora_do_prazo`, `_casos_perto_de_vencer`, `_ranking_colaboradores`, `_assuntos_lentos`, endpoint `/api/painel_gestao/dados`

- **Contexto desta revisão:** antes de percorrer os itens de UX, identificamos e corrigimos um problema grave de dados que distorcia todos os KPIs da tela (ver `REGISTRO_CORRECOES.md`, entrada `2026-07-01 15:43`). A análise abaixo foi feita com os dados já corretos.

**Varredura completa de componentes (01/07/2026):**
- **Header/subtítulo:** ✅ correto
- **Toolbar de período (7d, 30d, 90d, Mês corrente, Personalizado):** ✅ todos testados individualmente — cada um retorna dado correto quando clicado isolado (ver 2-A-filtros); race condition quando clicar múltiplos rápidos (ver 2-E, afeta TODOS os botões)
- **4 KPIs do topo:** ✅ corretos (ver 2-A)
- **Banner "Retorno BACEN tem tela própria":** ✅ link funciona (200 OK para `/painel/base-conhecimento-bacen`)
- **Painel "Casos resolvidos fora do prazo":** cliente "—" nos mais críticos (ver 2-C)
- **Painel "Casos perto de vencer":** título enganoso (ver 2-B); dados individuais corretos
- **Painel "Performance por colaborador":** Unicred como analista (ver 2-D); contador "ranking" (ver 2-F)
- **Painel "Assuntos que demoraram mais":** "4111" sem prefixo (ver 2-G — problema do pipeline, não do painel)

---

#### 2-A. ✅ KPIs do topo — validados após correção de dados

- **O que vimos:** 4 cards: Casos Resolvidos (942, +16,6%), Tempo Médio de Resolução (45,8d), Fora do Prazo (521, 55,3%), Categoria Mais Volumosa (DDR_2011, 292 casos). Período padrão ao abrir: 30 dias (02/06/2026 → 01/07/2026).
- **Validação:** números batem exatamente com a simulação feita antes da correção. Calculadora de período está correta.
- **Status:** ✅ Corretos — sem pendência.

---

#### 2-A-filtros. Validação dos filtros de período — todos funcionam individualmente

- **Testado em:** 01/07/2026 (data de hoje)
- **Método:** cada filtro testado isolado — página carregada, aguardado o período anterior completar, clicado o botão alvo, aguardado a resposta retornar. Nenhum filtro testado em sequência rápida (o que aciona a race condition do 2-E).
- **Resultado:** **todos os 5 filtros retornam dados corretos** quando usados individualmente.

| Filtro | Período exibido | Casos | Tempo médio | Fora do prazo | CADOC top | Resultado |
|--------|----------------|-------|-------------|---------------|-----------|-----------|
| **7 dias** | 25/06/2026 → 01/07/2026 | 44 | 4.5d | 6 | RISK_DRIVER_ALERTA | ✅ correto |
| **30 dias** (padrão) | 02/06/2026 → 01/07/2026 | 942 | 45.8d | 521 | DDR_2011 | ✅ correto |
| **90 dias** | 03/04/2026 → 01/07/2026 | 2.347 | 23.8d | 811 | DDR_2011 | ✅ correto |
| **Mês corrente** | 01/07/2026 → 01/07/2026 | 0 | — | 0 | — | ✅ correto¹ |
| **Personalizado** (abr/26) | 01/04/2026 → 30/04/2026 | 627 | 0.7d | 52 | RISK_DRIVER_ALERTA | ✅ correto |

¹ Mês corrente = julho 2026. Hoje é 01/07 (primeiro dia do mês), então o período é 01/07→01/07. Total 0 é esperado: nenhum caso foi concluído hoje. Correto.

- **O que os filtros cobrem:** o período é calculado a partir da `data_conclusao` dos casos. Cada botão ajusta o intervalo e a tela refaz todos os KPIs e painéis para aquele intervalo.
- **Pendência ativa:** a race condition (2-E abaixo) não foi corrigida — afeta todos os filtros quando clicados rapidamente um após o outro. Cada filtro individual funciona; o problema ocorre na transição entre eles.

---

#### 2-B. "Casos perto de vencer" exibindo casos já vencidos

- **O que vimos:** a seção se chama **"Casos perto de vencer"** e lista 10 casos. Todos os 10 têm status **"vencido há 1d"** — prazo 30/06/2026, hoje 01/07/2026. Nenhum caso futuro na lista.
- **Por que incomoda:** "perto de vencer" significa "vai vencer em breve" — não "já venceu ontem". Um usuário que lê essa seção espera uma lista de alertas preventivos para agir antes do prazo. Mas o que aparece são casos que já perderam o prazo. Isso confunde e tira o senso de urgência — se tudo já venceu, por que a seção se chama "perto de vencer"?
- **O que fazer (duas opções — Michel decide):**
  - **Opção 1 — Ajustar o filtro:** mostrar apenas casos com prazo nos próximos N dias (ex.: 7 dias). Casos já vencidos não entram aqui — eles já aparecem na tabela "Casos resolvidos fora do prazo" acima.
  - **Opção 2 — Renomear a seção:** se a intenção for mesmo mostrar casos recém-vencidos + futuros próximos, mudar o nome para "Casos urgentes (vencidos ou a vencer em 7 dias)" e deixar claro na interface o critério.
- **Impacto se não mexer:** usuário lê "perto de vencer" e vê 10 casos todos já vencidos — a seção perde o propósito de alerta preventivo.

- **Status:** ✅ **Implementado e validado em 01/07/2026.** Detalhes → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 — 2-B`.

---

#### 2-C. Cliente aparece como "—" na tabela "Fora do Prazo"

- **O que vimos:** nas primeiras linhas da tabela "Casos resolvidos fora do prazo" (521 linhas), pelo menos 3 das 5 primeiras mostram "**—**" no campo Cliente. Exemplos reais:
  - `— | DLO | prazo 12/07/2024 | concluído 10/06/2026 | +698 dias`
  - `— | DRM_2060 | prazo 08/08/2025 | concluído 29/06/2026 | +325 dias`
  - `— | DLI | prazo 05/09/2025 | concluído 29/06/2026 | +297 dias`
- **Por que incomoda:** sem saber qual cliente é, o gestor não consegue agir. "—" não diz nada — é um dado faltante mascarado. Os atrasos são enormes (+698 dias!), então esses casos são exatamente os mais críticos e são justamente os que não têm cliente identificado.
- **O que fazer:**
  1. **Investigar a origem:** verificar no integrador (`03_integrador_dados_site.json`) o campo `cliente` dessas threads específicas — se está vazio lá, o problema é de origem (thread sem empresa associada no cadastro); se está preenchido lá e "—" é um bug de exibição, é uma correção simples no template.
  2. Se o dado realmente não existe: exibir "Sem cliente cadastrado" em vez de "—", e marcar esses registros para revisão manual.
- **Impacto se não mexer:** os casos mais atrasados do sistema aparecem sem identificação — gestor não sabe quem é o cliente e não consegue priorizar ação.

- **Status:** ✅ **Implementado e validado em 01/07/2026.** Detalhes → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 — 2-C`.

---

#### 2-D. "Unicred" aparece como analista na seção Colaboradores

- **O que vimos:** a seção "Mais ágeis" lista:
  1. **Unicred** — 3h médio · 1 caso
  2. Michel — 6h médio · 63 casos
  3. Riskdriver — 9h médio · 6 casos
- **Por que incomoda:** "Unicred" é o nome de um **cliente** (empresa), não de um analista da Finaud. A seção deveria listar apenas os colaboradores/analistas internos que trabalharam nos casos. Quando a thread não tem analista atribuído, o sistema parece estar usando o nome do cliente como substituto.
- **O que fazer:** investigar como o campo de analista é preenchido nas threads. Se o campo de responsável estiver vazio em algumas threads, a tela deve mostrar "Sem analista" ou simplesmente excluir essas threads do ranking de colaboradores — nunca o nome do cliente.
- **Impacto se não mexer:** o gestor vê "Unicred" como se fosse um funcionário da equipe — dado completamente errado para tomada de decisão sobre desempenho interno.

- **Status:** ✅ **Implementado e validado em 01/07/2026.** Detalhes → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 — 2-D`.

---

#### 2-E. Race condition nos filtros de período — dados do período errado aparecem na tela

- **O que vimos:** ao clicar qualquer filtro de período logo após outro (ex.: 30d → 7d → 90d em sequência rápida), a tela exibe dados do período errado — o botão ativo pode mostrar "7 dias" enquanto os KPIs exibem números do "30 dias". Em alguns casos a tela trava em "Carregando…" enquanto o dado errado persiste nos cards. **Afeta todos os 5 filtros, não só "Mês corrente"** (identificado e confirmado em teste de 01/07/2026).
- **Causa técnica:** as APIs têm tempos de resposta muito diferentes (7d = 14–15s, mes_corrente = 15s, 90d = 5s, 30d = 6s). Quando dois pedidos estão em voo ao mesmo tempo, o que chegar por último sobrescreve a tela — sem verificar se ainda é o pedido atual. Não há cancelamento da requisição anterior.
- **Por que incomoda:** usuário clica nos filtros naturalmente (um atrás do outro), vê dados misturados sem mensagem de erro — pode tomar decisão com informação do período errado sem perceber.
- **O que fazer:** no JavaScript (`templates/painel_gestao.html`, função `carregarPainel`), adicionar um contador de requisição (`_pgReqId`). A cada clique de filtro: incrementar o contador e guardar o valor atual; quando a resposta chegar, só atualizar a tela se o contador ainda bater com o pedido que gerou a resposta. Qualquer resposta "velha" é descartada silenciosamente.
- **Impacto se não mexer:** usuário que clicar em mais de um período durante a sessão pode ver dados misturados. O sistema parece funcionar mas exibe o período errado sem aviso.

- **Status:** ✅ **Implementado e validado em 01/07/2026.** Padrão `_pgReqId` adicionado em `carregarPainel` — respostas atrasadas são descartadas. Sem teste unitário: lógica JS de template, sem infraestrutura JS no projeto. Detalhes → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 — 2-E`.

---

---

#### 2-F. Painel "Colaboradores" — contador mostra "ranking" em vez de número

- **O que vimos:** os painéis 1, 2 e 4 mostram um número no canto direito do cabeçalho (521, 10, 5). O painel "Performance por colaborador" mostra o texto fixo **"ranking"** — não é um número.
- **Por que incomoda:** o padrão visual da tela inteira é "número de itens" no badge do painel. "ranking" quebra esse padrão e não passa informação objetiva ("quantos colaboradores têm dados?").
- **O que fazer:** trocar o texto fixo "ranking" por uma contagem real — ex.: `7 analistas` (número de colaboradores distintos com tempo medido no período). Mudança de 1 linha no JavaScript (`renderColaboradores`).
- **Onde:** `templates/painel_gestao.html`, função `renderColaboradores`, linha que define `cntColab.textContent`.

- **Status:** ✅ **Implementado e validado em 01/07/2026.** Badge mostra "15 analistas" (30d). Detalhes → `REGISTRO_CORRECOES.md`, entrada `2026-07-01 — 2-F`.

---

#### 2-G. Painel "Assuntos" — "4111" aparece sem prefixo de categoria

- **O que vimos:** a tabela "Assuntos que demoraram mais" lista: S5, DDR_2011, SUPORTE, DLO, **4111**. O código "4111" é o mesmo CADOC que aparece em outras partes como "DDR4111" ou "DDR_4111" — mas aqui está sem prefixo. Causa: algumas threads têm `alvo_triagem_auto = '4111'` (213 threads) enquanto outras têm `'DDR4111'` (307 threads), e o painel exibe o campo como veio sem normalizar.
- **Por que incomoda:** gestores precisam saber que "4111" e "DDR4111" são o mesmo tipo de demanda. Da forma atual, eles aparecem separados, distorcendo os contadores e tempos médios.
- **O que fazer:** a correção definitiva é no pipeline (unificar os valores de `alvo_triagem_auto`). No painel, uma normalização simples resolve o display: se o valor for `'4111'`, exibir como `'DDR_4111'`. **Isso é assunto para sessão dedicada de pipeline** — não corrigir aqui.
- **Impacto se não mexer:** os totais de DDR_4111 aparecem fragmentados em dois grupos; o tempo médio de cada um é menos representativo do que seria com os dados unificados.

---

- **Status geral da pendência 2:**
  - **1ª rodada (UX):** 2-A validado (sem pendência); **2-B, 2-C, 2-D, 2-E, 2-F corrigidos e validados em 01/07/2026** (ver REGISTRO_CORRECOES.md); 2-G (prefixo "4111") encaminhado para sessão de pipeline.
  - **2ª rodada (lógica de dados, 01/07/2026):** 6 achados novos — **2-H** (tempo médio inflado), **2-I** (categoria+volumosa poluída por RISK_DRIVER_* e duplicados), **2-J** (fora do prazo com prazo de referência errado), **2-K** (ranking colaboradores: rank único, só Finaud), **2-L** (volume colaboradores: excluir Suporte/RiskDriver), **2-M** (confirmar que tudo reflete o filtro). Detalhe completo e decisões pendentes do Michel → `PENDENCIAS.md`, seção "REVISÃO — Painel de Gestão: 2ª rodada". **4 dos 6 dependem de decisão de negócio antes de corrigir.**

---

## Telas já percorridas

| # | Tela | Status |
|---|------|--------|
| 1 | Login | ✅ percorrida — sem achados |
| 2 | Visão Geral (dashboard) | ✅ percorrida — pendência 1 implementada (card único de e-mails, FOG/Normativos reais, limpeza de seções) |
| 3 | Painel de Gestão | ✅ percorrida — 4 achados registrados (pendências 2-B a 2-E), dados corrigidos (entrada 2026-07-01 15:43 no REGISTRO) |
