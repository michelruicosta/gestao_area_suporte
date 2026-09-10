# SESSAO_ATUAL — Histórico setembro 2026

> Arquivo de arquivo do diário de sessões. Cada bloco abaixo foi o diário completo de uma sessão
> antes de ser movido para cá pelo `/fechar`.
> Arquivo ativo: `SESSAO_ATUAL.md`

---

## 📓 Diário da sessão (2026-09-09) — Coletor de colaboradores: verificação pós-deploy do fix Message-ID/In-Reply-To

### O que foi feito

Sessão retomada após compactação de contexto — estado verificado e confirmado íntegro.

1. **Estado confirmado** — coletor ativo com fix Message-ID/In-Reply-To ✅, 653 testes passando, produção ativa.

2. **Como os testes foram feitos** — explicado para Michel: 20 testes unitários pytest cobrindo `_construir_indice_mid`, `_thread_por_reply` e `_ja_existe`; validação com dados reais (Gmail das 6 caixas): 84 mensagens novas em 45 threads, sem contaminação.

3. **Como ver na tela** — orientado: buscar "Trustee" ou "DRM - 2060", thread Trustee DTVM deve ter 2 mensagens. Identificados dados da thread: assunto "ENC: BANCO CENTRAL - COMUNICACAO DE INCONSISTENCIA NO DRM - 2060", data 01/09/2026.

4. **Confirmação visual** — Michel abriu a thread na tela do sistema e confirmou: De: Miguel Santos → Para: Igor Menezes Costa (`icosta.ext@trusteedtvm.com.br`), data 01/09/2026, conteúdo correto (pedido do COS4060). BUG CRÍTICO encerrado e confirmado na tela ✅.

5. **Nenhuma alteração de código nesta sessão.**

### Estado atual

**pytest:** 653 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅.
**Coletor de colaboradores:** ATIVO com fix Message-ID/In-Reply-To ✅.
**BUG CRÍTICO DRM 2060:** resolvido e confirmado na tela por Michel ✅.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — acabamentos menores: Cenário 2b (COSIF citada 2× perde espaços duplos) e `white-space: nowrap` na coluna Valor
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-09 18:30 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-09) — Contaminação cruzada DRM 2060: investigação, restauração e prevenção

### O que foi feito

1. **Investigação do bug** — Michel relatou que o sistema mostrava mensagens erradas na thread Trustee DTVM (`1a05d9178be1c1b7`). Sistema: 22 msgs, última Flávio → Raphael (WU). Gmail real: 2 msgs, Miguel Santos → Igor Menezes Costa (Trustee). Outras threads do DRM 2060 com o mesmo problema.

2. **Causa raiz confirmada** — `scripts/coletor_enviados_colaboradores.py` identifica a qual thread uma mensagem pertence pelo assunto normalizado (sem Re:/ENC:/FW:). Com 20+ threads compartilhando "BANCO CENTRAL - COMUNICACAO DE INCONSISTENCIA NO DRM - 2060", todas caem na mesma chave — mensagens de um cliente vão parar em threads de outros. 527 threads contaminadas em 8 ondas entre 02/09 e 09/09/2026.

3. **Restauração do banco** — re-buscamos os 527 threads diretamente na API do Gmail via `_processar_thread` + `salvar_thread`. 168 threads decontaminadas. Trustee DTVM: 22 msgs → 2 msgs, destinatário corrigido (WU → Trustee) ✅. Snapshots antes/depois em `data/backups/snapshot_antes_restauracao.csv` e `snapshot_depois_restauracao.csv`. Backup do banco em `data/backups/20260909_1529_restauracao_banco/`.

4. **Prevenção** — `executar_pipeline.py` (função `rodar_sem_retorno`): `coletar_colaboradores()` desativado com comentário explicativo até o bug ser corrigido.

5. **Documentação** — `PENDENCIAS.md` e `REGISTRO_CORRECOES.md` atualizados com a contaminação.

6. **Commit `e714861`**, push e deploy VPS — tela + agendador ativos ✅.

7. **Fix do coletor encontrado já implementado** — ao fechar a sessão, descobrimos que a sessão anterior havia implementado o fix completo em `coletor_enviados_colaboradores.py` (usando `Message-ID`/`In-Reply-To` em vez de assunto), reativado o coletor em `executar_pipeline.py` e escrito 20 testes, mas não havia commitado. 638 testes passando ✅. Coletor voltou a rodar — bug resolvido.

### Estado atual

**pytest:** 638 passed ✅ (test_coletor_colaboradores.py reescrito com nova lógica).
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `e714861` publicado.
**Coletor de colaboradores:** ATIVO com fix de Message-ID/In-Reply-To. ✅

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

Último /fechar: 2026-09-09 17:00 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-09) — Modal: Cenário 3 — listas com marcadores implementadas e publicadas

### O que foi feito

Sessão dedicada ao **Cenário 3 da leitura inteligente**: detecção automática de listas com marcadores (`-`, `*`, `•`, `N.`, `N)`) no texto das mensagens do modal, renderizando `<ul>`/`<ol>` em vez de texto plano.

1. **Pesquisa na base local** — varridos os 153 threads com listas no banco (`corpo_texto`): padrão traço (`- item`), asterisco Outlook (`  *   item`), numerada (`1. texto`). Falsos positivos identificados: URLs nos itens, traço no meio de frase, menos de 3 itens, item >300 chars.

2. **Implementação em `templates/gestao_email.html`:**
   - CSS adicionado: `.msg-lista` e `.msg-lista li` (~linha 661)
   - Nova função `_listaMarcadores(texto)` inserida após `_tabelaEspacos`:
     - Detecta ≥3 itens consecutivos (linhas em branco entre itens são toleradas)
     - Exclui URLs nos itens e itens >300 chars
     - Retorna HTML com `.msg-tcampos-badge` + `<ul>`/`<ol class="msg-lista">` + toggle "Ver texto original"
   - 5 call sites encadeados: `m.texto_novo` (×2), `m.corpo_encaminhado`, `m.historico_citado`, `m.corpo`

3. **Validação Node.js** — 6 casos reais: 4 devem detectar (ul seguido, ul com blanks, ol numerada), 2 devem ignorar (URLs, só 2 itens). Resultado: **6/6 ✅**.

4. **pytest:** 640 passed ✅ (zero regressões).

5. **Teste na UI:** Michel pesquisou "Posição de Câmbio corretora" na Visão Geral → thread `1a010965b497ec0f` → badge "📋 Lista detectada" apareceu, `<ul>` renderizado, toggle funcionou.

6. **Commit, push e deploy na VPS:** commit `a5521b5`, serviço `gestao-suporte` active ✅. Site responde normalmente em `gestao-suporte.finaudapps.com.br`.

### Estado atual

**pytest:** 640 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `a5521b5` publicado.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — acabamentos menores: Cenário 2b (COSIF citada 2× perde espaços duplos) e `white-space: nowrap` na coluna Valor
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-09 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — Tabela COSIF no modal: validação do Cenário 2 + registro + Cenário 3 aberto

### O que foi feito

Sessão de diagnóstico — retomada de chat que esgotou o contexto. Michel relatou que a tabela COSIF (thread `1a06e8e5284ba878`, "Re: DLO e DLI - JULHO 2026") não aparecia mais no bloco "Histórico da conversa" após reiniciar o servidor, e pediu que a correção fosse **testada antes** de qualquer novo pedido de reinício.

1. **Diagnóstico — não era bug.** A função `_tabelaEspacos` (commit `2bd95e5`) estava correta. Prova em duas camadas:
   - Função extraída do template e rodada no **Node** com os 6 textos reais que `/api/thread` envia: só o histórico citado do **2º card** (Jacilaine) detecta — "📊 4 colunas · 8 linhas"; os outros cinco devolvem `null`, como devem.
   - **Aba logada do Browser pane:** JS servido já era o novo, `_thrData` correto, 1 badge no DOM dentro do bloco colapsado do 2º card.
   - Michel expandia o histórico do **1º card** (Andrea, mais recente), onde a tabela é citada pela 2ª vez e o cliente de e-mail esmagou os espaços duplos — não há colunas para detectar (limite anotado como Cenário 2b).
   - O "3 colunas · 6 linhas" visto antes era a versão antiga pegando a 2ª linha de dados como cabeçalho; "4 colunas · 8 linhas" é o correto.
2. **Registro:** `REGISTRO_CORRECOES.md` 08/09 23:30 — Cenários 1 e 2 (nenhum dos dois estava registrado); `PENDENCIAS.md` — Cenário 3 (listas com marcadores) + Cenário 2b + `nowrap` na coluna Valor. Commit `220c2fb` (só documentação).
3. **Deploy:** `220c2fb` publicado na VPS — levou o `2bd95e5`, que estava só no GitHub. Tela e agendador `active`; site responde em 0,35s.
4. **Memória nova:** `feedback_testar_antes_de_pedir_restart` — provar correção de tela (Node com dados reais + aba logada) antes de pedir reinício; F5 troca o JS carregado, reiniciar o servidor não.

### Estado atual

**pytest:** 635 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `220c2fb` publicado.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — leitura inteligente **Cenário 3: listas com marcadores** (Cenários 1 e 2 feitos, registrados e publicados; detalhe em `PENDENCIAS.md` — levantar 5–10 threads reais antes de implementar)
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-08 23:55 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — Redesign telas Evolução e Classificação e Status

### O que foi feito

Redesign visual completo das duas telas principais da aba de e-mails, aprovado por Michel após mockup interativo.

**1. Variação embutida no número (tela principal e Evolução) — commits `2d4191c` e `db70954`:**
- Antes: cada métrica tinha uma coluna de número + uma coluna VAR separada → 10 colunas na tela principal, 9 na Evolução.
- Depois: o badge de variação (▲3 / ▼1) fica embutido dentro da célula do número → 6 colunas na tela principal, 5 na Evolução.
- Funções JS novas: `_numDelta()` (tela principal), `evoCelNum()` e `evoBdg()` (Evolução).
- Tela principal comparava com "ontem" → passou a comparar com a **última rodada** (`ler_penultimo_snapshot()` em `servidor_telas.py`).
- Legenda da tela principal atualizada: "Variação desde a última atualização".
- Aba Evolução ganhou barra de contexto: "Comparando **este mês** com **mês passado**" (atualizada por `getEvoCompLabel()` a cada `renderEvo()`).
- Categorias na aba Evolução viraram **multiselect** (clique adiciona/remove; antes era seleção única).

**2. Legenda da aba Evolução igual à tela principal — commits `ccd74f3` e `4b5973d`:**
- Antes: rodapé `evo-ft` com badges-pílula em tamanho diferente do texto de comparação.
- Depois: uma única `card-legenda` com tudo na mesma linha e no mesmo tamanho: `● Comparando... · ▲ AF/AC cresceu · ▼ AF/AC caiu · ...`

**Deploy VPS:** todos os commits publicados; serviço ativo ✅.

### Estado atual

**pytest:** 608 passed ✅ (mudanças de UI pura — sem testes dedicados; registrado no REGISTRO).
**Produção:** `gestao-suporte.finaudapps.com.br` — serviço ativo ✅.

---

## 📓 Diário da sessão (2026-09-08) — Fix: CI — pacotes Google ausentes no requirements-dev.txt

### O que foi feito

Diagnóstico e correção do CI que estava falhando desde o commit `483720b`.

1. **Causa identificada:** `requirements-dev.txt` não listava os pacotes do Google (`google-api-python-client`, `google-auth` e 4 outros). Esses pacotes são importados a nível de módulo em `coletor_gmail.py` e `coletor_enviados_colaboradores.py` — os testes `test_coletor_html.py` e `test_coletor_colaboradores.py` quebravam com `ImportError` antes de rodar qualquer asserção. Localmente passava porque os pacotes estavam instalados no Python global do usuário.

2. **Correção:** adicionados os 6 pacotes ao `requirements-dev.txt` com as mesmas versões já usadas em produção no `requirements.txt`.

3. **Commit `9f97437`, push feito.** CI vai rodar automaticamente.

### Estado ao fechar

**pytest:** 608 passed ✅. **Produção:** ativa ✅.

---

## 📓 Diário da sessão (2026-09-08) — Fix: filtro de período Lista de Casos + campo data vazio

### O que foi feito

**Dois bugs de interface corrigidos na tela FogBugz Lista de Casos.**

1. **Filtro de período não aplicava (commits `28c5004` e `22f8959`):**
   - `fogFiltrar()` tinha controles de período na tela (Hoje, Semana, Personalizado + Aplicar) mas ignorava completamente os valores — todos os casos apareciam sempre.
   - Causa: lógica de filtragem por data nunca foi escrita quando os controles foram criados.
   - Correção: adicionado pré-cálculo de `_dtIni`/`_dtFim` em `fogFiltrar()`, com comparação contra o atributo `data-data` (data de abertura) de cada linha.
   - Padrão de abertura alterado para sem filtro ativo (opção B aprovada por Michel): ao abrir a página todos os casos aparecem; filtro só age quando selecionado.

2. **Campo de data vazio mostrava "dd" cortado:**
   - `.dt-disp.vazio` tinha `width:0;overflow:hidden` — o texto "dd/mm/aaaa" vazava como "dd".
   - Corrigido para `display:none`. Campos vazios mostram só 📅. Afeta todos os 3 seletores de período do sistema (E-mails Evolução, FOG Lista, FOG Evolução).

3. **Deploy VPS:** ambas as correções publicadas. Serviço ativo ✅.

### Estado atual

**pytest:** 608 passed ✅ (zero regressões).
**Produção:** `gestao-suporte.finaudapps.com.br` — serviço ativo ✅.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-08 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — Fix: mensagens duplicadas (coletor colaboradores)

### O que foi feito

**Bug reportado:** thread DRM - 2060 PLANNER CORRETORA exibia 2 mensagens no sistema, mas o Gmail mostrava apenas 1.

**Causa raiz identificada:** o mesmo e-mail físico chegava em dois caminhos — via `suporte@finaud.com.br` (Google Groups mascarando o remetente) e diretamente na caixa da Andrea. O campo `message_id` (RFC 5322, único por e-mail em qualquer caixa) **não estava sendo gravado**, então o filtro anti-duplicata só comparava `(data, remetente)` — que difere entre as duas cópias.

**Correção (commits desta sessão):**

1. **`coletor_gmail.py` — `_processar_mensagem()`:** adicionado `'message_id': h('Message-ID')` ao dict de retorno. Todas as mensagens capturadas por qualquer coletor agora armazenam o Message-ID.

2. **`coletor_enviados_colaboradores.py` — `_ja_existe()`:** reescrita completa. Lógica nova:
   - Ambos com `message_id` → comparação definitiva; se IDs diferentes, **não cai no fallback** (evita falso positivo por `(data, remetente)` coincidente)
   - Mensagem antiga sem `message_id` → fallback por `(data, remetente)` apenas para aquela mensagem
   - Nova sem `message_id` → fallback integral

3. **`tests/test_coletor_colaboradores.py`:** 4 novos testes cobrindo os 4 cenários da lógica nova.

4. **Limpeza do banco:** 244 mensagens duplicadas removidas de 151 threads (backup em `data/backups/20260908_1221_dedup_mensagens/` antes da limpeza).

5. **Verificação de status:** dry-run em todas as 1.541 threads ativas → zero divergências. A recalculação de 02/09/2026 já havia corrigido tudo.

6. **Deploy na VPS:** serviço reiniciado, ativo ✅.

### Estado atual

**pytest:** testes passando, zero regressões.
**Produção:** `gestao-suporte.finaudapps.com.br` — serviço ativo ✅.
**Banco:** limpo de duplicatas, backup disponível.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Investigação em chat dedicado.

---

## 📓 Diário da sessão (2026-09-06) — Alerta "busca parada": origem do alerta

### O que foi feito

**Diagnóstico de alerta + melhoria no e-mail de notificação**

Michel recebeu o e-mail "Busca de e-mail parou" e não sabia se o problema era no PC dele ou no servidor de produção. Investigamos o log do dia e confirmamos: foi um `WinError 10060` (timeout de rede do Windows) no PC local às 00:41 do dia 05/09 — a busca voltou sozinha na hora seguinte (01:41).

**Melhoria implementada (commit `efcba4a`):**

- Nova linha "Origem do alerta" no quadro do e-mail: "PC local (seu computador)" ou "Servidor (produção)"
- Nova função `origem_do_alerta(portal_url)` em `scripts/aviso_busca_parou.py`
- 2 asserções novas no teste existente (cenário servidor e cenário local)
- Deploy na VPS ✅

### Estado atual

**Commits:** `efcba4a` — no GitHub e na VPS.
**Produção:** `gestao-suporte.finaudapps.com.br` — serviço ativo ✅.
**pytest:** 583 testes passando, zero regressões.

### Próximo passo

🔴 **Chat dedicado: correção de status de todas as threads**

`recalcular_status_todos()` só processa threads ativas (`inativa_desde IS NULL`) — threads arquivadas ficam com status congelado. Chat dedicado já preparado.

**Antes de qualquer mudança no modal:**
🟡 **Spec display modal A–G** — mapear comportamento atual e desejado com exemplos reais (ver PENDENCIAS.md).

**Pendências que continuam:**
- 🟡 Passo C — tela de manutenção de regras
- 🔴 Threads irmãs — investigação em chat dedicado
- 🔴 Monitorar caixas da Andrea e Sarah

Último /fechar: 2026-09-06 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — UX modal thread: histórico sob demanda

### O que foi feito

**Melhoria de UX no modal de visualização de threads** — design aprovado por Michel após protótipo interativo.

1. **Problema:** modal com dois scrolls simultâneos — externo (modal) e interno por mensagem (`max-height: 14rem`). Em threads longas era necessário scrollar em dois níveis ao mesmo tempo.

2. **Design aprovado:** Michel aprovou o protótipo (artifact publicado na sessão). Modal abre direto nas 2 mensagens mais recentes; histórico oculto atrás de um botão; borda colorida por remetente.

3. **`gestao_email.html` (commits `d585ddc` + `a528a1f`):**
   - CSS: removido `max-height: 14rem; overflow-y: auto` do `.msg-body` — scroll único
   - CSS: `.msg-card-cliente` (borda azul), `.msg-card-finaud` (borda verde), `.msg-ver-historico` (botão pílula), `.msg-historico-colapsado`
   - JS: `_renderMsgHtml()` extrai HTML por mensagem; `_renderThreadBody()` divide em `recentes` (2 primeiros = 2 mais recentes) e `historico`
   - JS: `_togHist()` expande/oculta seção de histórico; `_togHistMsg(idx)` recolhe mensagem individual via DOM (preserva inner toggles B/E/C/D/F)
   - **Bug corrigido:** API retorna newest no índice 0 (`reversed(stored_msgs)` em `servidor_telas.py:789`); slicing inicial estava invertido

4. **Deploy VPS:** serviço ativo ✅.

### Estado atual

**pytest:** 608 passed ✅ (zero regressões — mudança de UI pura, sem teste dedicado).
**Produção:** `gestao-suporte.finaudapps.com.br` — serviço ativo ✅.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-08 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — Verificação e-mails do dia + criação serviço agendador VPS

### O que foi feito

Sessão operacional — verificação dos e-mails de 08/09 e manutenção da VPS.

1. **Verificação dos e-mails de hoje:** consultado o banco local — 76 threads com atividade em 08/09, todas classificadas corretamente. As 4 sem categoria são e-mails automáticos de sistema (relatórios Risk Driver, FogBugz, newsletter Bacen), corretamente em destino `descartes`.

2. **Diagnóstico da VPS via SSH:**
   - Tela (`gestao-suporte`): ativa ✅
   - Agendador externo (`gestao-suporte-agendador`): **inexistente** — nunca tinha sido criado no systemd
   - Coleta estava sendo feita pelo agendador legado dentro da tela; última rodada: 16:36
   - Disparada coleta manual: 9 threads atualizadas, 7 classificadas, 0 erros

3. **Criação do serviço `gestao-suporte-agendador` na VPS:**
   - Criado `/etc/systemd/system/gestao-suporte-agendador.service` (roda `executar_pipeline.py --agendar`)
   - Adicionado `GESTAO_AGENDADOR_EXTERNO=1` no `.env` da VPS
   - Serviço habilitado e iniciado; tela reiniciada para ler a nova variável
   - Ambos os serviços: `active` ✅

4. **`REGISTRO_CORRECOES.md`:** entrada registrada (sem código alterado — mudança só na VPS).

### Estado atual

**pytest:** 608 passed ✅ (não rodado nesta sessão — nenhum código alterado).
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-08 20:00 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — Fix: campo Para — colaborador @finaud em vez de suporte

### O que foi feito

Correção do campo "Para:" na lista e no modal de threads — dois commits.

1. **Fix 1 — modal mostrava pessoa externa do CC (`4062f9c`):**
   - Quando e-mail chegava de externo para `suporte@finaud.com.br` com CC externo (ex.: Mariana Pereira da Ebury), o modal mostrava "Para: Mariana Pereira" em vez de `suporte@finaud.com.br`.
   - Causa: `_resolver_para` ia direto ao CC quando via `suporte@` no To, sem verificar se o CC era @finaud.
   - Correção: nova função `_primeiro_finaud_no_cc` filtra o CC por @finaud antes de exibir.

2. **Fix 2 — lista e modal ignoravam colaborador @finaud no To (`b4e118e`):**
   - Quando o To tinha `suporte + andrea + rodrigo`, o campo Para exibia `suporte@finaud.com.br` porque era o primeiro @finaud encontrado.
   - A spec (§7, Campo 3, Passo 1) confirma: CC só é consultado quando o To não identifica nenhum @finaud além do suporte.
   - Impacto verificado antes: 120 de 998 threads ativas (12%) — principalmente andrea (71), marcio (17), monica (8).
   - Correção: `_primeiro_finaud_colaborador` pula endereços de suporte; `suporteforcapital@finaud.com.br` tratado como suporte.
   - Afeta lista (`_primeiro_finaud_ou_primeiro`) e modal (`_resolver_para`).

3. **Validação e deploy:**
   - 608 testes ✅ (zero regressões em ambos os commits)
   - Push e deploy na VPS — serviço ativo ✅
   - Testado na tela: thread DDR Raúl Salazar passou de `suporte@finaud.com.br` → `andrea.inacio@finaud.com.br`

### Estado atual

**pytest:** 608 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — serviço ativo ✅. Commits `4062f9c` e `b4e118e` publicados.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-08 21:00 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-08) — Sentry monitoring + 3 otimizações de performance

### O que foi feito

Duas sessões encadeadas (a segunda retomou da primeira, que esgotou o contexto).

**Sentry monitoring (sessão anterior — contexto esgotado):**
1. Projeto `gestao-area-suporte` criado no Sentry. DSN adicionado ao `.env` da VPS.
2. `scripts/monitor_erros.py` — centraliza toda a integração Sentry:
   - Filtros de dados sensíveis LGPD: `before_send`, `before_send_transaction`, `before_breadcrumb` — campos pessoais (`remetente`, `assunto`, `body`, etc.) substituídos por `[REDACTED]`; e-mails detectados por regex → `[EMAIL OCULTO]`
   - `send_default_pii=False` — sem IP nem sessão de usuário
   - Tracing (`traces_sample_rate=0.2`), Profiling (`profiles_sample_rate=1.0`), Logging (WARNING+)
   - Cron monitor `relogio-coleta` — detecta se o pipeline parar silenciosamente
3. `scripts/servidor_telas.py` — `monitor_erros.iniciar(modo='flask')` antes de `app = Flask(...)`
4. `scripts/executar_pipeline.py` — `monitor_erros.iniciar()` + `checkin_inicio()`/`checkin_fim()` ao redor do job agendado
5. Fix 503 pós-deploy: `sentry-sdk` não estava instalado no venv da VPS → instalado com `venv/bin/pip`
6. Fix extra `[profiling]` inexistente no sentry-sdk 2.x → removido do `requirements.txt`
7. 10 testes em `tests/test_monitor_erros.py` ✅

**Profiling Sentry revelou 3 rotas lentas — todas corrigidas nesta sessão:**

| Rota | Causa | Correção | Melhora |
|---|---|---|---|
| `api_imagem` (4,81s) | Chamada ao Gmail a cada requisição de imagem | Cache em arquivo `data/cache_imagens_gmail/` | ~4,8s → <10ms da 2ª vez |
| `index` (3,44s) | Chamada ao FogBugz fria após cada reinício | Thread de aquecimento de cache ao subir servidor | ~3,4s → <50ms pós-deploy |
| `api_thread` (3,04s) | Buscava thread completa no Gmail para mapas de imagem inline | Cache em arquivo `data/cache_threads_gmail/` (invalida quando nova mensagem chega) | ~3s → <10ms da 2ª abertura |

**Novos testes:** 9 (cache_imagem) + 2 (aquece_cache_fog) + 6 (cache_thread) = **17 testes novos**.
**3 deploys via SSH.** Servidor ativo ✅.

### Estado atual

**pytest:** 635 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commits `a7cf548`, `055aa7b`, `64c43d6` publicados.

Último /fechar: 2026-09-08 23:00 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-09) — Sentry: guia interativo + fix UndefinedError media_dias

### O que foi feito

1. **Guia interativo do Sentry** — artifact publicado em claude.ai com 6 abas (Erros, Rastreamento, Perfis, Logs, Relógio, Proteção de Dados), cada uma seguindo a estrutura âncora simples → conceito técnico → consequência prática → o que fazer. Dados reais do projeto (4,81s, nomes das rotas, filtros LGPD).

2. **Fix: `UndefinedError 'dict object' has no attribute 'media_dias'`** — Sentry capturou o erro às 13h21 de hoje na rota `index` (`gestao_email.html`, linha 2104).
   - **Causa:** template tinha coluna "Média/caso" usando `p.media_dias` no ranking FOG, mas `servidor_telas.py` não calculava esse campo no dict. As mudanças estavam no working tree não commitado; o servidor em produção rodava `a5521b5` (commit anterior) sem o campo.
   - **Correção:** `media_dias` adicionado ao dict do ranking em `index()` (`servidor_telas.py`, linha 663); template com coluna "Média/caso" + grid 6 colunas + ordenação; teste `test_ranking_media_dias_calculada` adicionado.
   - **642 testes passando ✅**. Commit `32fb917`, push e deploy na VPS — tela + agendador ativos.

### Estado atual

**pytest:** 642 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `32fb917` publicado.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — acabamentos menores: Cenário 2b (COSIF citada 2× perde espaços duplos) e `white-space: nowrap` na coluna Valor
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-09 14:45 — memórias revisadas ✅

---
