# Linhagem de Dados — Do E-mail à Tela Operacional

> **Para que serve:** mostra o caminho completo de cada informação — desde o momento em que
> o e-mail chega na caixa da Finaud até o campo que aparece na tela. Permite saber exatamente
> de onde cada dado veio e qual script o criou.
>
> Leia junto com: [Guia de Campos da Tela Operacional](GUIA_CAMPOS_OPERACIONAL.md)
> — o Guia explica o que cada campo faz na tela; este documento explica de onde ele veio.
>
> _Atualizado: 2026-07-08_

---

## O fluxo completo

```
Gmail
  │
  ▼
Script 02 (captura)
  │  coleta os e-mails da caixa e salva tudo cru
  ▼
JSON 01 — Extração bruta  [01_extração_dados_brutos_gmail.json]
  │
  ▼
Script 05 (classifica)
  │  identifica o cliente, o CADOC, os prazos, separa quem é FINAUD e quem é CLIENTE
  ▼
JSON 02 — Classificação  [02_classificação_dados_brutos_gmail_editado.json]
  │
  ├──► Script 11 (triagem)
  │       decide AGUARDANDO ou CONCLUÍDO para cada thread
  │       └──► threads_aguardando_auto.json  /  threads_concluidas_auto.json
  │
  ├──► Script 13 (correlação)
  │       identifica threads do mesmo cliente que tratam do mesmo assunto
  │       └──► pares_threads_confirmados.json
  │
  └──► Script 09 (integra)
          agrupa mensagens por thread, resolve empresa, calcula status de prazo
          └──► JSON 03 — Integrador  [03_integrador_dados_site.json]
                │
                ▼
            Tela /operacional
               (lê os 6 arquivos abaixo)
```

---

## Os 6 arquivos que alimentam a tela

| # | Arquivo | O que fornece para a tela |
|---|---|---|
| 1 | `03_integrador_dados_site.json` | Dados principais: assunto, cliente, prazos, mensagens, status de prazo |
| 2 | `threads_aguardando_auto.json` | Quais cases estão AGUARDANDO + motivo da classificação |
| 3 | `threads_concluidas_auto.json` | Quais cases estão CONCLUÍDOS + motivo da classificação |
| 4 | `pares_threads_confirmados.json` | Badge de "par confirmado" (🔗 fios) — dois e-mails diferentes que são do mesmo caso |
| 5 | `cadastro_clientes_cadoc.json` | Resolução do nome oficial da empresa (lookup pelo domínio do remetente) |
| 6 | `rotulos_empresa_gestao.json` | Apelidos e nomes customizados de empresa (sobreposição manual do cadastro) |

> ⚠️ **Nota arquitetural (2026-07-08):** os arquivos 5 e 6 são lidos na hora de servir a tela
> (não apenas no pipeline). Isso significa que a tela faz processamento ao vivo — o que deveria
> ser feito no Script 09 e entregue pronto no JSON 03. Pendência registrada em `PENDENCIAS.md`.

---

## JSON 01 — Dados brutos do e-mail (gerado pelo Script 02)

> Uma cópia fiel do que chegou na caixa de entrada. O Script 02 não interpreta nada — apenas baixa e guarda.

| Campo | O que é em linguagem simples |
|---|---|
| `id` | Número que o Gmail deu para este e-mail específico (ex.: `"1"`) |
| `threadId` | Código técnico que o Gmail usa para agrupar os e-mails de um mesmo assunto (respostas ficam no mesmo grupo) |
| `message_id` | Código único que o servidor do remetente colocou no cabeçalho — serve para o sistema saber se já baixou este e-mail antes |
| `in_reply_to` | Código do e-mail ao qual este está respondendo — o sistema usa para montar a cadeia de respostas |
| `references` | Lista de todos os códigos anteriores da conversa — para rastrear o histórico completo |
| `thread_root` / `x_gm_thrid` | Código interno do Gmail para o grupo de e-mails (thread) — usado pelo Script 05 para unificação |
| `remetente` | Campo "DE:" bruto — exatamente como chegou, combinando nome e endereço: `"João Silva <joao@empresa.com.br>"` |
| `reply_to` | Campo "RESPONDER PARA:" do e-mail — às vezes diferente do remetente (ex.: e-mails enviados via sistema externo) |
| `destinatarios` | Campo "PARA:" bruto — todos os endereços de destino, separados por vírgula |
| `cc` | Campo "CC:" bruto — endereços que receberam cópia |
| `assunto` | Assunto do e-mail exatamente como o remetente escreveu |
| `corpo` | Corpo completo do e-mail (HTML cru, com tags e formatação) |
| `corpo_html` | Igual ao `corpo`, garantidamente em formato HTML |
| `corpo_texto` | Versão só-texto do corpo, sem formatação HTML |
| `data_email` | Data e hora em que o e-mail foi enviado: `"Fri, 3 Jul 2026 16:15:07 +0000"` |
| `anexos_detectados` | Lista de arquivos anexados ao e-mail (nome, tipo, tamanho) |

---

## JSON 02 — Dados classificados (gerado pelo Script 05)

> O Script 05 lê o JSON 01 e adiciona a interpretação: quem é o cliente, qual é o CADOC regulatório, quais são os prazos, quem é FINAUD e quem é CLIENTE.

**Campos mantidos do JSON 01 (sem alteração):** `data_email`, `id`, `threadId`, `assunto`, `remetente`, `corpo_html`

**Campos novos adicionados pelo Script 05:**

| Campo | O que é em linguagem simples | Como o Script 05 decide |
|---|---|---|
| `cliente` | Nome bruto de quem enviou — extraído do "DE:", sem o endereço de e-mail | Pega só o nome do campo `remetente` |
| `contato_origem` | Dados completos de quem enviou: lado (FINAUD ou CLIENTE), nome e e-mail separados | Verifica o domínio: `@finaud.com.br` → FINAUD; qualquer outro → CLIENTE |
| `contato_destino` | Dados completos de quem recebeu: lado, nome e e-mail separados | Mesmo critério de domínio |
| `responsavel` | Nome da pessoa que precisa agir (responder ou enviar) | Quem enviou por último: se foi o CLIENTE, a FINAUD é responsável, e vice-versa |
| `corpo_limpo` | Texto do e-mail sem HTML, sem histórico de respostas anteriores, sem assinaturas | Script 05 remove tudo que não é conteúdo novo |
| `cadoc` | Código do formulário regulatório ao qual este e-mail se refere (ex.: `"4111"`, `"6209"`) | Script 05 analisa o assunto e o corpo para identificar o CADOC |
| `prazos` | Lista de prazos regulatórios relacionados a este e-mail | Calculado com base no CADOC e na data do e-mail |
| `retorno_bacen` | Verdadeiro/falso: este e-mail é uma comunicação de retorno do BACEN? | Detectado pelo assunto e remetente |
| `exibir_card` | Verdadeiro/falso: este e-mail deve aparecer na tela? | Falso para e-mails internos, spam ou sem CADOC identificado |
| `tipo_painel` | Categoria interna de exibição | Derivado do CADOC e do tipo de comunicação |
| `finaud_somente_cc` | Verdadeiro se a Finaud recebeu o e-mail só em cópia (não era o destinatário principal) | Verifica se `@finaud.com.br` aparece só no CC, não no PARA |
| `tem_estrutura_complexa` | Verdadeiro se o corpo tem formatação muito complexa (tabelas, imagens embutidas) | Detectado pelo parser HTML |

**Campos removidos do JSON 01 (não passam para o JSON 02):**
`message_id`, `in_reply_to`, `references`, `references_raw`, `thread_root`, `x_gm_thrid`, `reply_to`, `destinatarios`, `cc`, `corpo`, `corpo_texto`

> São dados técnicos de cabeçalho usados só durante o processamento do Script 05. Depois de cumprirem seu papel (identificar threading, detectar Reply-To), não precisam mais ser carregados.

---

## JSON 03 — Dados integrados por thread (gerado pelo Script 09)

> O Script 09 agrupa todos os e-mails de um mesmo assunto em uma única "thread" (conversa), resolve o nome oficial da empresa e calcula o status de prazo.
>
> **Estrutura diferente:** ao contrário dos JSONs 01 e 02 (um registro por e-mail), o JSON 03 tem um registro por **thread** — que pode conter vários e-mails dentro do campo `mensagens`.

**Campos que vêm do JSON 02 (copiados do e-mail mais recente da thread):**

| Campo no JSON 03 | Vem de | O que é |
|---|---|---|
| `assunto` / `titulo` | JSON 02 `assunto` | Assunto do e-mail mais recente da thread |
| `cliente` | JSON 02 `cliente` | Nome bruto do cliente (do "DE:") |
| `cadoc` / `secao_operacional` | JSON 02 `cadoc` | Código do CADOC regulatório |
| `retorno_bacen` | JSON 02 `retorno_bacen` | Se é comunicação de retorno do BACEN |

**Campos novos criados pelo Script 09:**

| Campo | O que é em linguagem simples |
|---|---|
| `threadId` | Identificador único da conversa — agrupa todos os e-mails relacionados |
| `empresa` | Nome **oficial** da empresa do cliente — buscado no cadastro (`cadastro_clientes_cadoc.json`). Fica vazio se o domínio não estiver cadastrado. ⚠️ Requer Script 09 regenerado |
| `responsabilidade` / `lado_responsavel` | De quem é a vez de agir: `FINAUD` ou `CLIENTE` — calculado por quem enviou o último e-mail |
| `qtd_mensagens` | Quantos e-mails existem nesta conversa |
| `data_iso` | Data do e-mail mais recente, no formato padrão (`2026-07-03`) |
| `data_ultima_msg` | Idem — data da última mensagem (alias) |
| `timestamp` | Data e hora formatada para exibição (`"03/07 16:15"`) |
| `timestamp_epoch` | Data e hora em número — usado para ordenar os cards da tela |
| `status_processo` | Status do prazo regulatório: `PENDENTE`, `ATRASADO` ou `OK` — calculado com base nos prazos do CADOC |
| `lista_prazos` | Lista de prazos da thread — cada item tem: data-base, prazo-limite e o CADOC |
| `mensagens` | Todos os e-mails desta thread, na ordem — cada um com: id, data, assunto, contato_origem, contato_destino, corpo, corpo_limpo, anexos |
| `conversa_unificada` | Texto de todos os e-mails da thread concatenados — usado para busca e análise da IA |
| `link` | Link direto para abrir a conversa no Gmail |
| `thread_concluida_sem_nova_msg` | Verdadeiro se a thread já foi concluída e não chegou mensagem nova |

**Campos calculados na hora de servir (não estão gravados no JSON 03):**

| Campo | O que é | Calculado por |
|---|---|---|
| `empresa` (versão final) | Nome oficial refinado — usa o campo `empresa` do JSON 03 como base e aplica regras adicionais de `rotulos_empresa_gestao.json` | `painel_operacional_snapshot.py` ao carregar para a tela |
| `responsavel_pela_acao` | Quem deve agir agora — relê o array `mensagens` e verifica quem enviou por último | `painel_operacional_snapshot.py` ao carregar para a tela |

---

## Arquivos de triagem (gerados pelo Script 11)

> O Script 11 lê o JSON 03 e decide se cada thread está AGUARDANDO ou CONCLUÍDA, com base nas regras dos supervisores de cada CADOC.

### `threads_aguardando_auto.json`

| Campo | O que é em linguagem simples |
|---|---|
| `threadId` | Identifica qual thread está aguardando |
| `assunto` | Assunto da thread (copiado para facilitar leitura do arquivo) |
| `empresa` | Nome da empresa (copiado do JSON 03) |
| `cadoc` | CADOC da thread |
| `motivo` | Texto explicando por que está AGUARDANDO (em linguagem simples — este texto aparece no tooltip do card) |
| `regra` | Código interno da regra que classificou (ex.: `R2`, `R7`) |
| `tipo` | Tipo da classificação: `auto` (IA) ou `manual` (usuário) |
| `data_marcacao` | Quando foi marcado como AGUARDANDO |
| `prazo` | Até quando aguarda |
| `status` | Sempre `"aguardando"` neste arquivo |
| `qtd_mensagens_no_fechamento` | Quantas mensagens a thread tinha quando foi classificada |
| `origem_triagem_auto` | Verdadeiro se foi a IA que classificou; falso se foi o usuário |
| `alvo_triagem_auto` | Qual CADOC/categoria a IA usou para classificar |

### `threads_concluidas_auto.json`

| Campo | O que é em linguagem simples |
|---|---|
| `threadId` | Identifica qual thread está concluída |
| `tipo` | Tipo da classificação |
| `status` | Sempre `"concluido"` neste arquivo |
| `regra` | Código da regra que concluiu (ex.: `R1`, `R4`) |
| `data_conclusao` | Quando foi marcado como CONCLUÍDO |
| `motivo_triagem_auto` | Texto explicando por que está CONCLUÍDO (em linguagem simples — aparece no tooltip do card) |
| `motivo_triagem_auto_tecnico` | Versão técnica do mesmo motivo (para debug interno) |
| `empresa` | Nome da empresa (copiado) |
| `cadoc` | CADOC da thread |
| `aprendizado_ia` | Resumo que a IA gerou sobre o desfecho — contém: tipo de demanda, tempo de espera, se o prazo foi cumprido |
| `origem_triagem_auto` | Verdadeiro se foi a IA que classificou |
| `alvo_triagem_auto` | Qual CADOC/categoria a IA usou |
| `qtd_mensagens_no_fechamento` | Quantas mensagens tinha quando concluída |

---

## `pares_threads_confirmados.json` (gerado pelo Script 13)

> Registra quando dois e-mails diferentes (de threadIds distintos) foram identificados como parte do mesmo caso — por exemplo, quando o BACEN respondeu num e-mail novo em vez de responder na mesma conversa.
>
> ⚠️ No ambiente de teste este arquivo ainda não foi gerado (o Script 13 não foi executado).

---

## Matriz final — O que aparece na tela e de onde vem

| O que aparece na tela | Campo usado | Arquivo de origem | Criado por |
|---|---|---|---|
| **Assunto** do card | `titulo` (fallback: `assunto`) | JSON 03 | Script 02 captura; Script 09 copia sem alterar |
| **ID** do card | `id` | JSON 03 → JSON 02 → JSON 01 | Gmail (número atribuído na hora de baixar) |
| **Empresa / Cliente** do card | `empresa` → fallback `cliente` | `empresa`: JSON 03 + `cadastro_clientes_cadoc.json` + `rotulos_empresa_gestao.json`; `cliente`: JSON 02 | `empresa`: Script 09 + painel ao vivo; `cliente`: Script 05 |
| **Categorias** (pill de CADOC) | `lista_prazos[].cadoc` | JSON 03 | Script 05 identifica o CADOC; Script 09 organiza os prazos |
| **Status pill** (PENDENTE / AGUARDANDO / CONCLUÍDO) | `status_processo` + arquivos de triagem | JSON 03 + AG/CO JSONs | `status_processo` (prazo): Script 09; AGUARDANDO/CONCLUÍDO: Script 11 |
| **Motivo no tooltip** (ex.: "cliente confirmou recebimento") | `motivo` / `motivo_triagem_auto` | `threads_aguardando_auto.json` ou `threads_concluidas_auto.json` | Script 11 |
| **Regra badge** (ex.: "R4") | `regra` | AG/CO JSONs | Script 11 |
| **Responsável pela ação** | `responsavel_pela_acao` → fallback `responsavel` | Calculado ao vivo das `mensagens` do JSON 03 | `painel_operacional_snapshot.py` (calculado na hora de servir) |
| **Cor de urgência do card** (vermelho = crítico) | `lista_prazos[].prazo_limite` | JSON 03 | Script 05 calcula; Script 09 filtra pelas regras de negócio |
| **Badge "Par confirmado"** (🔗 fios) | `pares_threads_confirmados.json` | JSON de pares | Script 13 |
| **Badge "Nova resposta"** (📬) | Cruzamento AG JSONs com data atual | AG/CO JSONs | Calculado ao vivo pela tela |

---

## Campos do JSON 03 que existem mas não aparecem diretamente na tela

| Campo | Usado para | Necessário? |
|---|---|---|
| `lado_responsavel` | Alias de `responsabilidade` — mesmo valor, dois nomes | ⚠️ Duplicata — candidato a remover |
| `secao_operacional` | Alias de `cadoc` — mesmo valor, dois nomes | ⚠️ Duplicata — candidato a remover |
| `conversa_unificada` | Busca de texto e análise pela IA (Script 15) | ✅ Usado internamente |
| `thread_concluida_sem_nova_msg` | Lógica de reativação de cards | ✅ Necessário |
| `link` | Abrir a conversa no Gmail (usado no modal) | ✅ Necessário |
| `timestamp_epoch` | Ordenação dos cards por data | ✅ Necessário |
| `data_ultima_msg` | Alias de `data_iso` — mesmo valor, dois nomes | ⚠️ Duplicata — candidato a remover |
