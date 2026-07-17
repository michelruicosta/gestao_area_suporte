# Validação dos Campos da Tela de Triagem (Operacional)

**Iniciado:** 2026-07-08  
**Ambiente de referência:** Produção (`oraculo_360_finaud`) — 4.786 threads, última carga: 02/07/2026  
**Tela validada:** `/operacional` (`templates/email_operacional.html`)  
**Processo:** campo a campo, com dado real de produção, documentado e validado com Michel

---

## Como ler este documento

Cada campo tem:
- **O que é:** o que o usuário vê na tela
- **Campo no JSON:** o nome técnico de onde o dado vem
- **Script que preenche:** qual etapa do pipeline gera o valor
- **Achado em produção:** o que a varredura nos 4.786 threads revelou
- **Status:** ✅ OK / ⚠️ Atenção / ❌ Problema confirmado / 🔲 Aguarda validação com Michel

---

## Mapa de campos

### CARD (lista de threads)

| # | Campo visível | Campo no JSON | Script |
|---|---|---|---|
| 1 | Assunto/título | `titulo` / `assunto` | Script 05 |
| 2 | ID do caso | `id` | Script 09 |
| 3 | Cliente / Empresa | `empresa` → fallback `cliente` | Scripts 04 e 09 |
| 4 | Status (pill: PENDENTE / AGUARDANDO / CONCLUÍDO) | `status_processo` + arquivos de triagem | Scripts 09 e 11 |
| 5 | Responsável | `responsavel_pela_acao` / `responsavel` | Scripts 06 e 09 |
| 6 | Regra aplicada (badge: R1, R2…) | `regra` / `motivo` | Script 11 (motor) |
| 7 | Categorias (snippet abaixo do assunto) | `cadoc` + `lista_prazos[].cadoc` | Script 05 |

### MODAL (ao clicar no card)

| # | Campo visível | Campo no JSON | Script |
|---|---|---|---|
| 8 | Título completo | `titulo` / `assunto` | Script 05 |
| 9 | Cliente | `cliente` | Script 04 |
| 10 | Empresa | `empresa` (não existe) → usa `cliente` | — |
| 11 | Responsável | `responsavel_pela_acao` / `responsavel` | Scripts 06 e 09 |
| 12 | CADOC (chip clicável) | `cadoc` | Script 05 |
| 13 | Status | `status_processo` + triagem | Scripts 09 e 11 |
| 14 | Categoria do prazo | `lista_prazos[].cadoc` | Script 05 |
| 15 | Data-base | `lista_prazos[].data_base` | Script 05 |
| 16 | Prazo limite (vencimento) | `lista_prazos[].prazo_limite` | Script 05 |
| 17 | Mensagens (histórico) | `mensagens[]` | Script 06 |
| 18 | Corpo da mensagem | `mensagens[].corpo` / `corpo_limpo` | Script 06 |
| 19 | Quem enviou (FINAUD/CLIENTE) | `mensagens[].contato_origem.lado` | Script 06 |
| 20 | Remetente (nome/email) | `mensagens[].contato_origem.nome` | Script 06 |
| 21 | Anexos | `mensagens[].anexos_detectados[]` | Script 02 |

---

## Validação campo a campo

---

### Campo 1 — Assunto / Título

**O que o usuário vê:** primeira linha do card — o assunto do email (ex.: "GLOBAL EXCHANGE - DDR referente ao dia 29/06/2026")  
**Campo no JSON:** `titulo` (principal) com fallback em `assunto`  
**Script que preenche:** Script 05 — lê o assunto do email capturado pelo Script 06  

**Achado em produção (4.786 threads):**
- Threads sem assunto/título: **0** — sempre preenchido ✅
- Fonte: vem diretamente do campo `Subject:` do email, sem transformação
- Exemplo real: `"GLOBAL EXCHANGE - DDR referente ao dia 29/06/2026"`

**Cruzamento origem → tela (4.786 threads):**
- Assuntos idênticos: 4.757 ✅
- Com diferença: **29 threads** — padrão: origem tem `RES:`, `Re:` ou `ENC:` no início; tela remove o prefixo
- Exemplos:
  - Origem: `RES: SSG - ENVIAR POSIÇÃO - 4111` → Tela: `SSG - ENVIAR POSIÇÃO - 4111`
  - Origem: `Re: CADOCS - JANEIRO-26` → Tela: `CADOCS - JANEIRO-26`
- **Isso é comportamento correto** — Script 05 remove prefixos de resposta/encaminhamento para limpar o assunto

**Status:** ✅ OK — campo sempre preenchido; diferenças são limpeza intencional de prefixos  
**Validação Michel:** ✅ Cruzado com produção — nenhum problema identificado

---

### Campo 2 — ID do caso

**O que o usuário vê:** número abaixo do assunto (ex.: `99154`) — identificador único do registro no sistema  
**Campo no JSON:** `id` (número sequencial gerado pelo Script 09)  
**Script que preenche:** Script 09 (integrador) — atribui ID único ao unificar os dados

**Achado em produção:**
- Campo presente em todos os registros ✅
- É o ID interno do sistema (não é o ID do Gmail)
- O ID do Gmail (`threadId`) é separado — aparece nos badges de "🔗 fios"

**Status:** ✅ OK  
**Validação Michel:** ✅ Confirmado — Michel usa o **assunto** para localizar casos no dia a dia, não o ID. O ID pode ser útil para buscas técnicas internas (ex.: cruzar com FogBugz), mas não é um identificador de trabalho primário.

---

### Campo 3 — Cliente / Empresa

**O que o usuário vê:** `📩 Nome do Cliente` no card (ex.: `📩 Global Exchange`)  
**Campo no JSON:** a tela tenta `empresa` primeiro, depois usa `cliente` como fallback  
**Script que preenche:** Script 04 (mapeia clientes) → Script 09 (integra)

**⚠️ ATENÇÃO — Descoberta na varredura:**
- O campo `empresa` **não existe** no JSON de produção (verificado em todos os 4.786 threads)
- A tela sempre cai no fallback `cliente`
- Isso significa que a linha "Empresa" no modal fica sempre vazia/oculta
- O campo `cliente` está preenchido em todos os threads ✅

**Situação especial:** 1.420 threads têm `cliente = "Finaud"` — são threads internas do sistema (alertas automáticos, LEIAUTES_BACEN, RISK_DRIVER etc.) — não são clientes reais, é o comportamento correto.

**Cruzamento origem → tela (produção, 3.366 threads de clientes reais):**

40 threads com nome de cliente errado. Causa raiz — 3 tipos:

**Tipo A — Alias de departamento** (o mais comum — pode afetar qualquer empresa no futuro):

| O que aparece | Empresa real | Email real |
|---|---|---|
| `compliance` / `Compliance` | Oliveira Trust (8) + Monopólio (4) | `compliance@oliveiratrust.com.br` etc. |
| `Financeiro` | Atual Câmbio (5) + Accredito SCD (2) | `financeiro@atualcambio.com.br` etc. |
| `Risco Externo` / `risco` | Trustee DTVM (3) | `risco@trusteedtvm.com.br` |
| `Jmf` | BR Capital DTVM (1) | `jmf@brcapital.com.br` |
| `carlos-adcon` | Carol DTVM (6) | `carlos-adcon@uol.com.br` |
| `TC` | Traders DTVM (1) | alias interno |

**Tipo B — Campo CC/Reply-To capturado como cliente** (bug no Script 06):

| O que aparece | Empresa real |
|---|---|
| `cc: Adriana Martins` | ECSA (4 threads) |
| `cc: para: Rodrigo Marino` | ECSA (1 thread) |
| `cc: Thiago Pereira Machado \| UY3` | UY3 (1 thread) |
| `responder a: Celso Julich Junior - Unicred do Brasil` | Unicred do Brasil (1 thread) |
| `responder a: Rafaela Fonseca Hot - Unicred do Brasil` | Unicred do Brasil (1 thread) |

**Tipo C — Sem cliente identificável:**

| O que aparece | Situação |
|---|---|
| `contato` | Email via formulário de contato — empresa desconhecida |
| `DESCONHECIDO` | Thread entre Finaud e o BCB (Banco Central) — sem cliente externo. **Não existe no TESTE** ✅ |

**Correções necessárias:**
- **Tipo A (cadastro):** registrar emails de alias em `data/json/config/cadastro_clientes_cadoc.json` mapeando para o nome correto da empresa. Não resolve casos futuros de novas empresas com mesmo padrão — precisaria de regra genérica.
- **Tipo B (código):** Script 06 está capturando campo CC/Reply-To como remetente — bug a corrigir.
- **Tipo C:** sem ação necessária no TESTE.

**Status:** ❌ Problema confirmado — 40 threads (1,2% dos clientes reais) com nome errado na tela  
**Validação Michel:** ✅ Confirmado — "compliance" é cargo, não empresa; pode afetar qualquer cliente futuro com esse padrão; BACEN/DESCONHECIDO não existe no TESTE

---

### Campo 4 — Status (AGUARDANDO / CONCLUÍDO)

**O que o usuário vê:** pill colorido no canto direito do card (verde = CONCLUÍDO, azul = AGUARDANDO)  
**Campo no JSON:** combina `status_processo` do integrador + listas de triagem automática  
**Script que preenche:** Script 09 define `status_processo = "SEM_TRIAGEM"`; Script 11 (motor) sobrescreve com AGUARDANDO ou CONCLUÍDO

**Como funciona na tela (2026-07-16):**
- Threads com `status_processo == "SEM_TRIAGEM"` → **invisíveis na tela** (filtradas no snapshot)
- Threads no `threads_concluidas_auto.json` → mostra **CONCLUÍDO** (verde)
- Threads no `threads_aguardando_auto.json` → mostra **AGUARDANDO**
- Não existe mais PENDENTE nem INFORMATIVO na tela

**Estados internos:**
- `SEM_TRIAGEM` = thread chegou no integrador mas ainda não passou pelo motor — não aparece na tela
- `AGUARDANDO` / `CONCLUÍDO` = atribuídos exclusivamente pelo motor (Script 11)

**Correção aplicada em 2026-07-16:** eliminação de PENDENTE/INFORMATIVO — ver REGISTRO_CORRECOES.md.

**Status:** ✅ Corrigido em 2026-07-16  
**Validação Michel:** ✅ Confirmado — só AGUARDANDO e CONCLUÍDO devem aparecer na tela

---

### Campo 5 — Responsável

**O que o usuário vê:** nome abaixo do status no card (ex.: "Monica Macedo") — indica quem precisa agir  
**Campo no JSON:** `responsavel_pela_acao` (preferência) ou `responsavel` (fallback)  
**Script que preenche:** Script 06 captura o nome da mensagem; Script 09 integra; a tela também tenta deduzir pelo histórico de mensagens

**Como a tela determina o responsável:**
- Se a última mensagem é do **CLIENTE** → responsável é a Finaud (analista)
- Se a última mensagem é da **FINAUD** → responsável é o cliente
- O nome vem de `contato_destino.nome` da última mensagem

**Achado em produção:**
- Campo `responsavel` preenchido em todos os threads ✅
- Exemplo: última mensagem Finaud→Cliente; responsável = `Luiza Ferreira Milet` (cliente)

**Status:** ✅ OK — campo sempre preenchido  
**Validação Michel:** 🔲 Aguarda — o nome que aparece como responsável bate com quem realmente precisa agir? Algum caso onde está errado?

---

### Campo 6 — Regra aplicada (badge)

**O que o usuário vê:** badge pequeno no card (ex.: "R2", "§5") — indica qual regra do motor classificou a thread  
**Campo no JSON:** `regra` e `motivo` nos arquivos de triagem (`threads_concluidas_auto.json` / `threads_aguardando_auto.json`)  
**Script que preenche:** Script 11 (motor de triagem)

**Status:** ✅ OK — aparece apenas para threads que passaram pela triagem  
**Validação Michel:** 🔲 Aguarda — o badge de regra aparece para você? Faz sentido o que está escrito?

---

### Campo 7 — Categorias (CADOC)

**O que o usuário vê:** linha de snippet abaixo do assunto (ex.: "Categorias: DDR 2011") — e chip clicável no modal  
**Campo no JSON:** `cadoc` (campo principal) + `lista_prazos[].cadoc` (pode ter múltiplos)  
**Script que preenche:** Script 05 — detecta o CADOC pelo assunto, corpo e nome dos anexos

**Achado em produção (4.786 threads):**
- Threads sem cadoc: **0** ✅
- Distribuição: DDR_2011 (1.412), RISK_DRIVER_ALERTA (835), DLO_2061 (498), 4111 (386)...
- Caso especial: `lista_prazos[0].cadoc` pode ser diferente do `cadoc` do thread  
  (ex.: thread com `cadoc=LEIAUTES_BACEN` e `lista_prazos[0].cadoc=SUPORTE`)

**Status:** ✅ Corrigido em 16/07/2026 — `_injetar_cadoc_em_prazos()` no Script 09 agora substitui `SUPORTE` (default) pelo CADOC real do thread. 9 threads corrigidas; 14 casos legítimos (multi-CADOC) mantidos.  
**Validação Michel:** ✅ Concluído — snippet mostrará o CADOC correto após próxima execução do Script 09.

---

### Campo 8 — Data-base e Prazo limite (Vencimento)

**O que o usuário vê:** no modal — `📅 DD/MM/AAAA → ⏰ DD/MM/AAAA` (data de competência → prazo de entrega)  
**Campo no JSON:** `lista_prazos[].data_base` e `lista_prazos[].prazo_limite`  
**Script que preenche:** Script 05 — extrai datas do assunto/corpo do email e calcula prazo útil

**Achado em produção:**
- Threads **sem prazo**: **321** — todas com `status = INFORMATIVO` (correto — informativos não têm vencimento) ✅
- Threads com prazo: 4.465 threads
- Cada thread pode ter **múltiplos prazos** em `lista_prazos[]` (um por CADOC detectado)

**Status:** ✅ OK para os INFORMATIVOS sem prazo; resto precisa de validação  
**Validação Michel:** 🔲 Aguarda — algum caso onde a data-base ou o prazo está errado? (ex.: data 31/03 para "marco relevante" — esse tipo de bug)

---

### Campo 9 — Mensagens / Histórico

**O que o usuário vê:** no modal — lista de mensagens em ordem cronológica, com nome do remetente, data e corpo  
**Campo no JSON:** `mensagens[]` — array com cada email da thread  
**Script que preenche:** Script 06 (captura do Gmail) → Script 02 (baixa anexos) → Script 09 (integra)

**Campos de cada mensagem:**
| Campo | O que é | Preenchido? |
|---|---|---|
| `contato_origem.nome` | quem enviou (nome) | ✅ preenchido |
| `contato_origem.lado` | FINAUD ou CLIENTE | ✅ preenchido |
| `contato_origem.email` | email do remetente | ✅ preenchido |
| `contato_destino` | quem recebeu | ✅ preenchido |
| `data_email` | data/hora do envio | ✅ preenchido |
| `assunto` | assunto daquele email | ✅ preenchido |
| `corpo` | texto completo (com assinatura) | ✅ preenchido |
| `corpo_limpo` | texto sem quebras de linha | ✅ preenchido |
| `remetente` | campo legado | ❌ **VAZIO em 100% dos registros** |

**⚠️ ATENÇÃO — Campo `remetente` sempre vazio:**
O campo `remetente` da mensagem está **vazio em todos os registros** de produção verificados.
A informação real de quem enviou fica em `contato_origem.lado` / `contato_origem.nome`.
A tela usa `contato_origem` — mas se algum trecho do código ainda usa `remetente`, vai falhar silenciosamente.

**Status:** ✅ Campo `remetente` legado — vazio, mas nenhum código o usa. Verificado em 16/07/2026: template e scripts usam `contato_origem` para tudo. Campo morto, sem impacto.  
**Validação Michel:** ✅ Concluído — sem ação necessária.

---

### Campo 10 — Corpo da mensagem (texto)

**O que o usuário vê:** o conteúdo de cada email no modal  
**Campo no JSON:** `mensagens[].corpo` (texto original) e `mensagens[].corpo_limpo` (sem formatação)  
**Script que preenche:** Script 06 — extrai o corpo do email

**Achado em produção:**
- `corpo` — texto completo, com assinatura e formatação original
- `corpo_limpo` — texto concatenado sem quebras de linha (usado pelo motor para análise)
- **Assinatura:** não é removida automaticamente do `corpo`. O usuário vê a assinatura junto com o conteúdo.
- **Texto de imagens** (`texto_imagens`) — campo existe mas estava vazio na amostra (OCR de imagens)

**Status:** ✅ Corrigido em 16/07/2026 — `cortarRodapeAssinaturaInline()` no template ampliada: detecta "Att, Nome Sobrenome" / "Obrigado, Nome Sobrenome" / "Cordialmente, Nome" em textos planos. 94% das assinaturas removidas em produção (66/70).  
**Validação Michel:** ✅ Confirmado incomoda — corrigido. Verificação visual pendente (login necessário — sem senha disponível no ambiente de IA).

---

### Campo 11 — Anexos

**O que o usuário vê:** no modal — lista de arquivos anexados ao email (nome do arquivo)  
**Campo no JSON:** `mensagens[].anexos_detectados[]` — array com nome, tipo e status de download  
**Script que preenche:** Script 02 — detecta anexos no Gmail; Script 06 — captura metadados

**Status:** ✅ Corrigido em 16/07/2026 — quando mensagem tem corpo + anexos, chips com os nomes aparecem abaixo do texto (📎 arquivo.pdf). Antes só exibia quando o corpo estava vazio. 1.908 mensagens em produção afetadas.  
**Validação Michel:** 🔲 Aguarda verificação visual — abrir uma thread com arquivo .xlsx ou .pdf para confirmar os chips aparecem.

---

## Achados prioritários (resumo)

| Prioridade | Campo | Problema |
|---|---|---|
| ⚠️ Investigar | Campo `empresa` | Não existe no JSON — tela sempre usa `cliente` como fallback |
| ⚠️ Investigar | Campo `remetente` (mensagem) | Sempre vazio — info real está em `contato_origem` |
| ⚠️ Investigar | Divergência `cadoc` vs `lista_prazos[].cadoc` | Em alguns casos os dois diferem |
| 🔲 Validar | Prazos e datas | 321 sem prazo (INFORMATIVOS — parece correto) |
| 🔲 Validar | Assinatura no corpo | Não é removida — aparece para o usuário? |

---

*Documento gerado em 2026-07-08 — atualizar conforme avançamos na validação campo a campo com Michel.*
