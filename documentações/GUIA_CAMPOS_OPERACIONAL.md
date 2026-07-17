# Guia de Campos — Tela Operacional (`/operacional`)

> **Para que serve:** descreve campo por campo o que aparece na tela operacional —
> de onde vem cada informação, qual script a preenche e quais regras se aplicam.
>
> Leia junto com: [Linhagem de Dados](LINHAGEM_DADOS_OPERACIONAL.md)
> — mostra o caminho completo de cada campo desde o e-mail até a tela (todos os JSONs intermediários).
>
> _Atualizado: 2026-07-16_

---

## Formato de cada campo

Todos os campos seguem esta estrutura:

- **O que mostra na tela** — o que o usuário vê, em linguagem simples
- **Passo 1 a 4** — o que cada script faz + o que pode dar errado naquele passo
- **Passo 5 — Caminho feliz** — tabela com o fluxo completo quando tudo funciona
- **⚠️ O que pode dar errado** — tabela consolidada de todos os problemas conhecidos
- **O que Michel faz para corrigir** — instruções diretas
- **Precisa rodar o pipeline?** — resposta direta com quais scripts
- **Como consultar quando algo der errado** — arquivo e campo
- **Status** — situação atual do campo

---

## Campo 1 — Assunto

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** o texto do assunto do e-mail no card da thread — por exemplo, `DDR 2011 - Posição Janeiro`. É o título que identifica aquela conversa. Prefixos de resposta (`Re:`, `RES:`, `ENC:`, `FW:`) são removidos pelo Script 05 para deixar o assunto limpo.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 acessa o Gmail e lê o campo `Subject:` de cada e-mail. O servidor pode entregar esse campo em formato codificado (caracteres especiais ou acentos) — o script decodifica para texto legível e grava como `assunto` no `01_extração_dados_brutos_gmail.json`, mantendo os prefixos como vieram.

*Em linguagem simples: é como abrir uma carta e copiar o assunto exatamente como está escrito no envelope.*

**O que pode dar errado neste passo:**
- Caractere que não consegue decodificar → substitui por `?` e grava assim, **sem aviso**
- Assunto completamente ilegível → grava `"Assunto Corrompido"`
- E-mail sem assunto → grava `"Sem Assunto"`

---

### Passo 2 — Classificação (Script 05)

O Script 05 usa o assunto para identificar o CADOC regulatório e remove os prefixos de resposta (`Re:`, `RES:`, `ENC:`, `FW:`). O assunto limpo é copiado para o `02_classificação_dados_brutos_gmail_editado.json`.

*Em linguagem simples: o classificador lê o assunto para entender do que se trata o e-mail e limpa os prefixos de "resposta" antes de gravar.*

**O que pode dar errado neste passo:** nenhum risco para o conteúdo do assunto — apenas limpeza de prefixos.

---

### Passo 3 — Integração (Script 09)

O Script 09 renomeia o campo `assunto` para `titulo` e grava no `03_integrador_dados_site.json`. O conteúdo não muda.

**O que pode dar errado neste passo:** nenhum risco — cópia direta.

---

### Passo 4 — Exibição na tela

A tela lê o campo `titulo` do JSON 03 e exibe no card. Se `titulo` vier vazio, exibe `"Sem título"` como fallback.

**O que pode dar errado neste passo:** se o pipeline não rodou após novo e-mail, o `titulo` pode estar desatualizado (mostra assunto de e-mail anterior da thread).

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail com assunto `Re: DDR 2011 - Posição Janeiro` | |
| Script 02 | Lê `Subject:`, decodifica, grava `assunto = "Re: DDR 2011 - Posição Janeiro"` no JSON 01 |
| Script 05 | Remove prefixo `Re:` → `assunto = "DDR 2011 - Posição Janeiro"` no JSON 02 |
| Script 09 | Renomeia para `titulo` e grava no JSON 03 |
| Tela | Exibe `"DDR 2011 - Posição Janeiro"` no card |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Assunto com caractere especial não decodificável | Assunto com `?` no meio | Encoding corrompido no e-mail de origem — fora do controle do sistema |
| Assunto completamente ilegível | `"Assunto Corrompido"` | Encoding inválido |
| E-mail enviado sem assunto | `"Sem Assunto"` | Remetente não preencheu o campo |
| Pipeline não rodou após novo e-mail | Assunto desatualizado | `titulo` no JSON 03 é do e-mail anterior |

---

### O que Michel faz para corrigir

O assunto vem do e-mail original e não pode ser corrigido pelo pipeline. Se aparecer com `?`, o encoding veio errado do remetente — problema na origem. Se aparecer `"Sem Assunto"`, o remetente não preencheu o campo.

**Precisa rodar o pipeline?** Não — não há como corrigir retroativamente.

**Como consultar quando algo der errado:** `data/json/pipeline/01_extração_dados_brutos_gmail.json` → campo `assunto` do e-mail pelo `id`.

**Status:** ✅ limpo — nenhum problema identificado. 29 de 4.786 threads têm assunto diferente da origem porque o Script 05 removeu o prefixo de resposta — comportamento correto.

---

## Campo 2 — ID do caso

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** um número no card da thread — por exemplo `78`. É o identificador único do **e-mail mais recente** daquela conversa, atribuído automaticamente pelo servidor IMAP do Gmail.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 acessa o Gmail via IMAP. O servidor entrega cada e-mail com um número de sequência único — o `id`. O script grava esse número no `01_extração_dados_brutos_gmail.json`. Antes de gravar, compara com os IDs já existentes — se já existe, o e-mail é ignorado (evita duplicatas).

*Em linguagem simples: é como um número de protocolo que a agência postal coloca no envelope. Não é você que escolhe — é o servidor que atribui automaticamente.*

**O que pode dar errado neste passo:** nenhum — o IMAP sempre entrega o `id` junto com o e-mail.

---

### Passo 2 — Classificação (Script 05)

Copia o `id` sem alterar para o `02_classificação_dados_brutos_gmail_editado.json`. Não usa o campo para nenhuma lógica.

**O que pode dar errado neste passo:** nenhum risco — cópia direta.

---

### Passo 3 — Integração (Script 09)

Copia o `id` para o `03_integrador_dados_site.json` mantendo o mesmo nome de campo.

**O que pode dar errado neste passo:** nenhum risco — cópia direta.

---

### Passo 4 — Exibição na tela

A tela agrupa os e-mails por thread e pega o **último da lista** (o mais recente). O `id` desse e-mail é exibido no card.

**O que pode dar errado neste passo:** se o pipeline não rodou após novo e-mail, a tela mostra o `id` do e-mail anterior da thread.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Novo e-mail chega na caixa da Finaud | Gmail atribui o número `78` a esse e-mail |
| Script 02 | Verifica que `78` não existe no JSON 01; baixa e grava `id = "78"` |
| Script 05 | Copia `id = "78"` para o JSON 02 |
| Script 09 | Copia `id = "78"` para o JSON 03 |
| Tela | Pega o e-mail mais recente da thread e exibe `78` no card |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Pipeline não rodou após novo e-mail | ID desatualizado (do e-mail anterior) | JSON 03 não foi atualizado desde o último e-mail |

---

### O que Michel faz para corrigir

Nenhuma ação necessária para o ID em si — é atribuído pelo Gmail e nunca está incorreto. Se mostrar ID desatualizado, basta rodar o pipeline.

**Precisa rodar o pipeline?** Script 09 se o ID estiver desatualizado.

**Como consultar quando algo der errado:** `data/json/pipeline/01_extração_dados_brutos_gmail.json` → campo `id` do e-mail.

**Status:** ✅ limpo — o campo sempre é preenchido corretamente pelo Gmail.

---

## Campo 3 — Remetente

> **Status do rastreamento:** ✅ Concluído em 10/07/2026.

**O que mostra na tela:** no histórico de mensagens de cada thread — linha "Remetente: Ana Paola do Nascimento · ana.paola@unicred.com.br". É a informação de quem enviou cada mensagem individual da conversa.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 extrai o campo `remetente` exatamente como vem do servidor — sem interpretação. Grava no `01_extração_dados_brutos_gmail.json`. Quando há `Reply-To:`, grava os dois campos separados (`remetente` e `reply_to_raw`) sem decidir qual é o "real" — essa decisão fica para o Script 05.

*Em linguagem simples: é o carteiro que copia exatamente o que está escrito no envelope — sem verificar se o endereço faz sentido.*

**O que pode dar errado neste passo:**
- Gmail fora do ar → Script 02 não roda → e-mail some sem rastro *(falha silenciosa — sem alerta)*
- E-mail com `Reply-To` preenchido → remetente real pode ser diferente do `De:` (resolvido no Passo 2)

---

### Passo 2 — Identificação do remetente real (Script 05)

O Script 05 decide quem é o remetente real. O campo `De:` nem sempre tem essa resposta — principalmente por causa do grupo `suporte@finaud.com.br`.

**Por que o Gmail substitui o remetente no grupo suporte:** o `suporte@finaud.com.br` é uma lista de distribuição. Quando um cliente envia para esse endereço, o Gmail redistribui para todos os membros e **substitui o `De:` original do cliente** pelo endereço do grupo, colocando o remetente real no `Reply-To:`.

**A regra (linhas 605–608):** se existe um `Reply-To:` e ele não é da Finaud, usa ele como remetente real.

**Cenários mapeados — validação de 8.825 e-mails em produção + 47 em TESTE (10/07/2026) — zero furos:**

*Lado do cliente:*

| Cenário | De: | Reply-To: | Como identifica o cliente | Funciona? |
|---|---|---|---|---|
| **A** — direto para colaboradora | `gustavo@banvox.com.br` | vazio | Campo `De:` | ✅ 1.342 casos |
| **B1** — para o grupo suporte | `'Gustavo' via Suporte <suporte@...>` | `gustavo@banvox.com.br` | Campo `Reply-To:` | ✅ 1.741 casos |
| **B2/B3** — suporte no Para/CC | `marcos@smartsafe.com.br` | vazio | Campo `De:` | ✅ 753 casos |
| **B4** — cópia interna do grupo | `suporte@finaud.com.br` | vazio | Não aplicável — interno | ✅ não exibe na tela |
| **BCC** — suporte em cópia oculta | `gustavo@banvox.com.br` | vazio | Campo `De:` (igual ao A) | ✅ tratado como A |

*Lado da Finaud:*

| Cenário | De: | Como o sistema trata | Funciona? |
|---|---|---|---|
| **FC** — Finaud responde ao cliente | `andrea@finaud.com.br` | Entra na mesma thread — mais uma mensagem | ✅ 3.191 casos |
| **FF** — Finaud envia internamente | `riskdriver@finaud.com.br` | Thread interna — `cliente = Finaud` | ✅ 1.790 casos |

**O que pode dar errado neste passo:**
- `contato_origem` vazio (falha silenciosa) — se o Script 05 não identificou o remetente, a linha "Remetente:" desaparece do histórico sem aviso

---

### Passo 3 — Integração (Script 09)

O Script 05 grava o remetente como objeto `contato_origem` com três campos: lado (`CLIENTE` ou `FINAUD`), nome e e-mail. O Script 09 copia esse objeto inteiro para cada mensagem dentro do JSON 03.

**O que pode dar errado neste passo:** nenhum risco adicional — cópia direta do `contato_origem`.

---

### Passo 4 — Exibição na tela

A tela lê o `contato_origem` e monta a linha de remetente no formato `Nome · email`. Remove automaticamente o sufixo `" via Suporte"` que o Gmail coloca no nome.

**O que pode dar errado neste passo:**
- Nome com caractere especial (ex.: `=?UTF-8?Q?Ana_Paola?=`) → exibe os símbolos brutos se a decodificação falhar. Nenhum aviso — falha silenciosa.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia para `suporte@finaud.com.br` | Gmail redistribui, coloca `Reply-To: leonardo.ueda@westernunion.com` |
| Script 02 | Grava `remetente = "suporte@finaud.com.br"` e `reply_to = "leonardo.ueda@westernunion.com"` no JSON 01 |
| Script 05 | `Reply-To` não é Finaud → `remetente_real = leonardo.ueda@westernunion.com`; grava `contato_origem = {lado: CLIENTE, nome: Leonardo Ueda, email: ...}` no JSON 02 |
| Script 09 | Copia `contato_origem` para o JSON 03 |
| Tela | Exibe `Remetente: Leonardo Ueda · leonardo.ueda@westernunion.com` |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Gmail fora do ar na hora da coleta | E-mail some sem rastro | Script 02 não coletou — falha silenciosa |
| `contato_origem` vazio | Linha "Remetente:" some do histórico | Script 05 não conseguiu identificar o remetente |
| Nome com caractere especial | Símbolos brutos (ex.: `=?UTF-8?Q?Ana_Paola?=`) | Falha de decodificação — problema de encoding no e-mail de origem |

---

### O que Michel faz para corrigir

- **Remetente não aparece:** verificar no `02_classificação_dados_brutos_gmail_editado.json` o `contato_origem` desse e-mail. Rodar Script 05 + Script 09.
- **Nome com símbolos brutos:** problema de encoding no e-mail de origem — sem correção possível pelo pipeline.

**Precisa rodar o pipeline?** Script 05 + Script 09.

**Como consultar quando algo der errado:** `python scripts/consultas/diagnostico_cenarios_email.py` — verifica se o e-mail foi capturado e em qual cenário foi classificado.

**Status:** ✅ limpo — varredura de 8.825 e-mails (produção) + 47 (TESTE) confirmou zero furos nos 7 cenários (10/07/2026).

---

## Campo 4 — Cliente

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** nome da pessoa que representa o cliente na thread — aparece no badge "Cliente" do modal (ex.: `Ana Paola do Nascimento`). É a **pessoa do lado de fora da Finaud**. Diferente do Campo 5 (Empresa), que é o nome da organização.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não cria este campo. Coleta os campos brutos (`remetente`, `destinatários`, `cc`, `reply_to`) que o Script 05 usará para identificar o cliente.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

O Script 05 resolve quem é a pessoa do cliente seguindo esta lógica:

- Quem enviou é **CLIENTE** → contato = nome/e-mail do remetente
- Quem enviou é **Finaud** → contato = nome/e-mail de quem recebeu do lado externo
- **Finaud para Finaud** → grava `"Finaud"` (thread interna)
- Não consegue identificar ninguém externo → grava `"CLIENTE_DESCONHECIDO"`

O resultado é gravado no campo `cliente` do JSON 02.

**O que pode dar errado neste passo:**
- Nome com encoding especial → pode ser gravado com símbolos brutos se a decodificação falhar

---

### Passo 3 — Integração (Script 09)

O Script 09 lê a **primeira mensagem** da thread para definir o contato do cliente de toda a conversa. Grava o campo `cliente` no JSON 03 a nível de thread (uma vez só, valendo para todas as mensagens).

**Análise de risco realizada em 13/07/2026:**

| Ambiente | Total de threads | CLIENTE_DESCONHECIDO | cliente=Finaud com CADOC externo |
|---|---|---|---|
| TESTE | 36 | 0 | 0 |
| Produção | 4.786 | 0 | 1.185 (todos RISK_DRIVER — correto) |

Os 1.185 com `cliente = "Finaud"` são relatórios automáticos do sistema de risco — genuinamente F→F, correto.

**O que pode dar errado neste passo:** nenhum risco identificado na prática — threads que começam F→F permanecem F→F.

---

### Passo 4 — Exibição na tela

- **Modal:** exibe `thread.cliente` no campo "Cliente". Se vazio, exibe `"—"`
- **Card da lista:** usa `empresa` primeiro; se vazia, usa `cliente` como fallback

**O que pode dar errado neste passo:**
- Nome com encoding especial → pode aparecer com símbolos brutos na tela

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail | `contato_origem.lado = CLIENTE`, `contato_origem.nome = "Ana Paola do Nascimento"` |
| Script 05 | Grava `cliente = "Ana Paola do Nascimento"` no JSON 02 |
| Script 09 | Lê primeira mensagem, confirma `lado = CLIENTE`, grava `cliente = "Ana Paola do Nascimento"` no JSON 03 |
| Tela (modal) | Exibe `Cliente: Ana Paola do Nascimento` |
| Tela (card) | Empresa vazia? Exibe `Ana Paola do Nascimento` no lugar |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Nome com encoding especial | Símbolos brutos (ex.: `=?UTF-8?Q?Ana_Paola?=`) | Falha de decodificação no e-mail de origem |
| `CLIENTE_DESCONHECIDO` (não ocorre hoje) | `"CLIENTE_DESCONHECIDO"` | Script 05 não identificou ninguém externo |

---

### O que Michel faz para corrigir

- **`CLIENTE_DESCONHECIDO`**: verificar no `02_classificação_dados_brutos_gmail_editado.json` o `contato_origem` da primeira mensagem da thread. Rodar Script 09 após identificar a causa.
- **Nome com símbolos brutos:** problema de encoding no e-mail — sem correção possível pelo pipeline.

**Precisa rodar o pipeline?** Script 09.

**Como consultar quando algo der errado:** `data/json/pipeline/03_integrador_dados_site.json` → campo `cliente` da thread pelo `threadId`.

**Status:** ✅ limpo — zero casos de `CLIENTE_DESCONHECIDO` em 4.786 threads de produção (13/07/2026).

---

## Campo 5 — Empresa

> **Status do rastreamento:** ✅ Concluído em 09/07/2026.
> Este campo serve de **exemplo do método** para os demais campos.

**O que mostra na tela:** nome oficial da empresa do cliente — aparece no card (ex: 📩 Unicred) e no badge "Empresa" do modal.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não contribui para este campo. Coleta os campos brutos que o Script 05 usará para resolver o `remetente_real`.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

Não contribui para este campo. Resolve o `remetente_real` (Campo 3), que o Script 09 usará para identificar a empresa.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 3 — Integração (Script 09)

O Script 09 pega o domínio do e-mail do `remetente_real` e consulta o `cadastro_clientes_cadoc.json`. Se encontra → grava o nome oficial. Se não encontra → grava string vazia `""`.

*Em linguagem simples: pega a parte depois do @ do e-mail (ex: `unicred.com.br`) e consulta a lista de cadastro. Se encontrar, grava o nome oficial da empresa. Se não encontrar, deixa em branco.*

**Onde no código:** `scripts/09_integrar_dados_painel.py`, função `_processar_threads()` — `"empresa": _resolver_empresa(...)` dentro do dict `thread_formatada`.

**Backup automático:** antes de gravar o novo JSON 03, o Script 09 cria automaticamente uma cópia em `03_integrador_dados_site.json.backup`.

**O que pode dar errado neste passo:**
- Domínio não cadastrado → empresa vazia, sem aviso *(Ex: Oz Câmbio enviou o primeiro e-mail; domínio `ozcambio.com.br` não estava no cadastro; card apareceu com nome da pessoa)*
- Domínio genérico (gmail, hotmail) → vazio intencional ✅
- Cadastro corrompido (vírgula extra, aspas faltando) → todas as threads ficam com `empresa: ""`, sem aviso
- Script 09 falha no meio → JSON 03 fica incompleto; threads somem da tela

---

### Passo 4 — Exibição na tela

Quando a tela carrega, chama `/api/dados`. O Flask lê o JSON 03 e para cada thread: se `empresa` vazia, tenta buscar novamente pelo e-mail do lado CLIENTE; depois aplica `_rotulo_empresa_gestao_para_api()` para padronizar nomes com base em `rotulos_empresa_gestao.json`.

⚠️ **Dupla computação:** `empresa` é calculado no Script 09 (Passo 3) **e** na API (Passo 4). Se a lógica dos dois divergir, a tela pode mostrar valor diferente do que está no arquivo.

**No card da lista:** prioridade: (1) nome oficial da empresa, (2) nome do cliente, (3) "DESCONHECIDO".

**No modal:** se empresa e cliente estiverem vazios, o badge "Empresa" desaparece completamente — não aparece em branco, some.

**O que pode dar errado neste passo:**
- Rótulo não cadastrado em `rotulos_empresa_gestao.json` → exibe domínio cru (ex: `oliveiratrust.com.br`)
- Cache desatualizado → tela mostra dados antigos mesmo após rodar Script 09

---

### Passo 5 — Caminho feliz

| Etapa | Quem faz | O que acontece | Resultado |
|---|---|---|---|
| 1 | Script 02 | Baixa e-mail com `From: compliance@lastrocapital.com.br` | JSON 01 → `remetente: compliance@lastrocapital.com.br` |
| 2 | Script 05 | Sem `Reply-To` → `remetente_real = remetente` | JSON 02 → `contato_origem.email: compliance@lastrocapital.com.br` |
| 3 | Script 09 | Extrai domínio `lastrocapital.com.br` → encontra no cadastro | JSON 03 → `"empresa": "Lastro Capital"` |
| 4 | API `/api/dados` | `_rotulo_empresa_gestao_para_api()` confirma nome | Payload → `"empresa": "Lastro Capital"` |
| 5 | JavaScript | Recebe `empresa: "Lastro Capital"` | Card: 📩 Lastro Capital; modal: badge "Empresa: Lastro Capital" |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Domínio não cadastrado | 📩 Nome da pessoa (fallback) ou "DESCONHECIDO" | `_resolver_empresa` não encontrou o domínio no cadastro |
| Cadastro corrompido | Empresa vazia em todas as threads | Script 09 usou lista vazia — sem aviso |
| Rótulo não cadastrado | Domínio cru (ex: `oliveiratrust.com.br`) | API não encontrou o rótulo em `rotulos_empresa_gestao.json` |
| Cache desatualizado após rodar Script 09 | Dados antigos na tela | Aguardar alguns segundos e recarregar |
| Script 09 falha no meio | Threads somem da tela | JSON 03 incompleto — restaurar backup |

---

### O que Michel faz para corrigir

- **Empresa vazia:** adicionar o domínio em `data/json/config/cadastro_clientes_cadoc.json` e rodar Script 09
- **Cadastro corrompido:** corrigir erro de sintaxe no arquivo antes de rodar Script 09
- **Cache desatualizado:** aguardar alguns segundos e recarregar; se persistir, reiniciar o servidor Flask
- **Script 09 falhou:** restaurar `03_integrador_dados_site.json.backup` e rodar Script 09 novamente

**Precisa rodar o pipeline?** Sim — Script 09 para qualquer correção no campo Empresa.

**Como consultar quando algo der errado:** `data/json/pipeline/03_integrador_dados_site.json` → campo `empresa` da thread. Se vazio, verificar `data/json/config/cadastro_clientes_cadoc.json` pelo domínio do e-mail do cliente.

**Status:** ✅ limpo — campo funcionando corretamente. Atenção ao ponto de dupla computação (Script 09 + API): se divergirem, a tela pode mostrar valor diferente do que está no JSON 03.

---

## Campo 6 — Responsável

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** nome da pessoa que deve agir agora na thread — aparece no badge `👤` do modal. Se o cliente aguarda resposta → é o analista da Finaud. Se a Finaud aguarda → é o colaborador do cliente.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não cria este campo. Coleta os campos brutos (`remetente`, `destinatários`, `cc`, `reply_to`) que o Script 05 usará.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

O Script 05 decide quem é o responsável com a função `identificar_cliente_e_responsavel_completo` (linhas 580–679):

- **Cliente enviou:** procura no "Para:" e no "CC:" um endereço `@finaud`. Se encontrar e estiver no cadastro `colaboradores_finaud` → usa o nome padronizado. Se não estiver cadastrado → usa o nome do campo "Para:". Se "Para:" não tiver nome → fallback `"Suporte Finaud"`.
- **Finaud enviou:** procura no "Para:" a primeira pessoa externa (não-Finaud). Usa o nome dela. Se não achar → usa o nome da empresa do cliente como fallback.

O campo `responsavel` é gravado no `02_classificação_dados_brutos_gmail_editado.json`.

**O que pode dar errado neste passo:**
- Colaborador não cadastrado em `colaboradores_finaud` → usa o nome do campo "Para:" do e-mail (pode vir em formato diferente do padrão)

---

### Passo 3 — Integração (Script 09)

O Script 09 calcula o responsável final com `_responsavel_pela_acao()`, que olha a **última mensagem** da thread:

| Última mensagem enviada por | Responsável calculado |
|---|---|
| Cliente → Finaud | Pessoa da Finaud no "Para:" desta mensagem |
| Finaud → Cliente | Pessoa do cliente no "Para:" desta mensagem |
| Finaud → Finaud (interno) | Pessoa da Finaud no "Para:" desta mensagem |
| Exceção "obrigada/obrigado pelo envio" | Quem enviou (Finaud) |
| Nenhum nome identificável | Fallback do Script 05 |

O resultado é gravado como `responsavel` no `03_integrador_dados_site.json`.

**O que pode dar errado neste passo:** se a última mensagem não tiver nome identificável, cai no fallback ("Suporte Finaud").

---

### Passo 4 — Exibição na tela

A tela exibe o valor `thread.responsavel` diretamente no badge `👤` do modal (elemento `mResp`). Sem recálculo na tela — o JSON é a fonte de verdade.

**O que pode dar errado neste passo:** nenhum risco adicional — leitura direta do JSON.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia relatório DDR para `michel@finaud.com.br` | `contato_origem.lado = CLIENTE`, destinatário = Michel |
| Script 05 | Remetente é cliente → busca "Para:" → encontra Michel no cadastro → `responsavel = "Michel Costa"` no JSON 02 |
| Script 09 | Última mensagem é do cliente → `responsavel = "Michel Costa"` no JSON 03 |
| Tela | Exibe badge `👤 Michel Costa` no modal |
| Michel responde → próxima carga | Última mensagem agora é Finaud→Cliente → `responsavel` passa a ser o nome do cliente |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| E-mail enviado só para `suporte@finaud` sem analista específico | `"Suporte Finaud"` | Nenhum `@finaud` individual no "Para:" — comportamento esperado |
| Nome do colaborador do cliente ausente no e-mail | Nome da empresa como fallback (ex: "Acme") | `extrair_nome_pessoa` retornou vazio |

---

### O que Michel faz para corrigir

Se mostrar "Suporte Finaud": verificar se o e-mail original tinha `@finaud` no "Para:" ou CC. Se sim → checar se o analista está em `colaboradores_finaud` no cadastro e corrigir; rodar Script 05 + Script 09. Se não → aguardar o analista responder; na próxima carga o nome aparece automaticamente.

**Precisa rodar o pipeline?** Script 05 + Script 09, nesta ordem. Fazer backup do JSON 03 antes.

**Como consultar quando algo der errado:**
- E-mail: `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json` → campo `responsavel`
- Thread: `data/json/pipeline/03_integrador_dados_site.json` → campo `responsavel`
- Colaboradores: `config/cadastro_clientes_cadoc.json` → seção `colaboradores_finaud`

**Status:** ✅ limpo — o campo sempre grava algo (nunca vazio). Valor genérico ("Suporte Finaud") ocorre apenas quando não há informação suficiente — comportamento esperado.

---

## Campo 7 — Categoria (CADOC)

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Corrigido em 16/07/2026 (snippet mostrava "SUPORTE" indevidamente em 9 threads).

**O que mostra na tela:** a categoria regulatória da thread — qual relatório do BACEN ela está relacionada. Exemplos: `DDR`, `DLO`, `DRM`, `SUPORTE`, `RETORNO BACEN`. Aparece no badge `📋` do modal e no snippet abaixo do assunto no card.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não cria este campo. Coleta apenas o assunto e o corpo bruto, que o Script 05 usará para identificar a categoria.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

A função `identificar_cadoc()` (linha 1326) analisa o assunto e o corpo na seguinte ordem de prioridade:

| Prioridade | Critério | Exemplo |
|---|---|---|
| 1 | Assunto com `S5` como palavra | → `S5` |
| 2 | Assunto com "Balancete de Câmbio" | → `DDR_2011` |
| 3 | Assunto com "Balancete" | → `DLO_2061` |
| 4 | Assunto com consulta de norma BCB | → `SUPORTE` |
| 5 | Assunto identifica exatamente 1 código numérico | → CADOC correspondente |
| 6 | Corpo tem código numérico | → CADOC correspondente |
| 7 | Corpo tem termo textual ("DDR", "DLO"...) | → CADOC correspondente |
| 8 | Nenhum critério atendido | → `OUTROS` |

O resultado é gravado como `cadoc` no `02_classificação_dados_brutos_gmail_editado.json`.

**O que pode dar errado neste passo:**
- Assunto genérico sem código ou termo → classifica como `OUTROS`
- Assunto com dois CADOCs (ex: encaminhamento DDR mencionando DLO) → pode pegar o CADOC errado

---

### Passo 3 — Integração (Script 09)

Copia o `cadoc` do e-mail para a thread. Se mensagens da mesma thread tiverem CADOCs diferentes, usa o mais frequente. A função `_injetar_cadoc_em_prazos()` garante que os prazos usem o CADOC correto: se um prazo tinha "SUPORTE" como padrão e a thread tem CADOC regulatório, substitui pelo CADOC real *(corrigido em 16/07/2026)*.

Grava `cadoc` no `03_integrador_dados_site.json`.

**O que pode dar errado neste passo:** thread com mensagens de CADOCs muito diferentes → o mais frequente pode não ser o mais correto.

---

### Passo 4 — Exibição na tela

A função `rotuloCategoriaChip()` converte o valor interno para o rótulo curto:

| Valor no JSON | Exibido |
|---|---|
| `DDR_2011` | `DDR` |
| `DRM_2060` | `DRM` |
| `DLO_2061` | `DLO` |
| `DLI_2062` | `DLI` |
| `DRL_2160` | `DRL` |
| `4111` | `4111` |
| `SUPORTE` / `SUPORTE_GERAL` | `SUPORTE` |
| `RETORNO_BACEN` | `RETORNO BACEN` |
| `S5` | `S5` |
| `DRSAC` | `DRSAC` |
| `FORCAPITAL` | `FORCAPITAL` |

**O que pode dar errado neste passo:** nenhum risco adicional — conversão de rótulo direta.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia "DDR 2011 - Posição Janeiro" | |
| Script 05 | Identifica código `2011` no assunto → `cadoc = "DDR_2011"` no JSON 02 |
| Script 09 | Copia `cadoc = "DDR_2011"` para a thread no JSON 03; prazos recebem o mesmo CADOC |
| Tela | Exibe badge `📋 DDR` no modal e "Categorias: DDR" no snippet do card |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Assunto genérico sem código ou termo | `OUTROS` | Nenhum critério da `identificar_cadoc` atendido |
| Assunto com dois CADOCs distintos | CADOC errado | Sistema pega o primeiro encontrado |
| Thread com mensagens de CADOCs diferentes | CADOC da maioria | Script 09 usa o mais frequente |

---

### O que Michel faz para corrigir

O badge `📋` no modal é clicável — permite corrigir o CADOC manualmente na tela sem rodar o pipeline.

**Precisa rodar o pipeline?** Não para correção manual via tela. Script 05 + Script 09 se quiser corrigir na origem.

**Como consultar quando algo der errado:**
- E-mail: `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json` → campo `cadoc`
- Thread: `data/json/pipeline/03_integrador_dados_site.json` → campo `cadoc`

**Status:** ✅ limpo — snippet corrigido em 16/07/2026 (9 threads que mostravam "SUPORTE" indevidamente agora exibem o CADOC correto da thread).

---

## Campo 8 — Status

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Problema identificado — ver nota abaixo.

**O que mostra na tela:** o estado atual da thread no badge `🏷` do modal. Na operação do dia a dia, os estados que importam são: **Aguardando** (alguém precisa agir) ou **Concluído** (assunto encerrado).

---

### Passo 1 — Coleta do e-mail (Script 02)

Não contribui para este campo.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

Não contribui para este campo.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 3 — Pipeline (Script 09 + Script 11)

**Script 09** cria o campo `status_processo` com base em uma regra simples:
- Thread tem prazo → `PENDENTE`
- Thread não tem prazo → `INFORMATIVO`

⚠️ **Este campo não representa Aguardando/Concluído** — é uma classificação interna baseada em prazos regulatórios, não no estado operacional real.

**Script 11** é quem define o estado real da operação. Classifica cada thread como AGUARDANDO ou CONCLUÍDO com base nas regras de negócio da Finaud. O resultado fica em:
- `data/json/pipeline/threads_aguardando_auto.json`
- `data/json/pipeline/threads_concluidas_auto.json`

**O que pode dar errado neste passo:**
- Thread nova sem histórico suficiente → motor do Script 11 não consegue classificar → fica como SEM_TRIAGEM, invisível na tela

---

### Passo 4 — Exibição na tela

A API `/api/dados` cruza os dois sistemas e injeta nos dados: `status = "concluido"` ou `aguardando = true`. A função `rotuloStatusOperacional()` exibe com esta ordem de prioridade:

| Condição verificada | Exibido |
|---|---|
| Thread está nas concluídas (Script 11) | `Concluído` |
| Thread está nas aguardando (Script 11) | `Aguardando` |
| `status_processo = PENDENTE` (Script 09) | `Pendente` |
| `status_processo = INFORMATIVO` (Script 09) | `Informativo` |
| Nenhuma das anteriores | `Pendente` (fallback) |

**O que pode dar errado neste passo:** nenhum risco adicional — leitura dos arquivos de triagem.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail com prazo regulatório | |
| Script 09 | Detecta prazo → `status_processo = "PENDENTE"` no JSON 03 |
| Script 11 | Analisa a thread → classifica como AGUARDANDO → grava em `threads_aguardando_auto.json` |
| API | Cruza os dois: thread está em AG → injeta `aguardando = true` |
| Tela | Exibe badge `🏷 Aguardando` no modal |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Thread ainda não classificada pelo motor | Invisível na tela (SEM_TRIAGEM) | Script 11 ainda não rodou ou não teve dados suficientes |
| Badge "Pendente" na busca para thread já concluída | `Pendente` na aba de busca | `status_processo` é campo de prazos, não reflete a triagem real |

---

### ⚠️ Problema identificado em 13/07/2026

O `status_processo` aparece na **aba de busca** e controla a **cor do ponto do card**. Como a regra é "tem prazo = PENDENTE", praticamente todas as threads aparecem como PENDENTE — inclusive as já concluídas. Isso não reflete a realidade operacional. **Investigação registrada em `documentações/PENDENCIAS.md`** — sessão dedicada para implementar a correção.

---

### O que Michel faz para corrigir

O badge `🏷` é clicável — permite alterar o status manualmente na tela. Para correção na origem, rodar o Script 11.

**Precisa rodar o pipeline?** Script 11 para atualizar a triagem.

**Como consultar quando algo der errado:**
- `data/json/pipeline/threads_aguardando_auto.json`
- `data/json/pipeline/threads_concluidas_auto.json`

**Status:** ⚠️ Problema identificado — `status_processo` (PENDENTE/INFORMATIVO) aparece em locais da tela que deveriam mostrar apenas Aguardando/Concluído. Ver PENDENCIAS.md.

---

## Campo 9 — Prazos

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Validado em produção (6.576 registros — zero erros de cálculo).

**O que mostra na tela:** a data-limite para envio de cada relatório regulatório. Cada thread pode ter mais de um prazo — um por mensagem recebida. O prazo mais recente aparece em destaque no card.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não contribui para este campo. Apenas coleta o e-mail bruto.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

É aqui que o prazo nasce. O script faz dois trabalhos:

**1. Busca a data de referência (`data_base`):**

| Prioridade | Onde busca |
|---|---|
| 1ª | Assunto do e-mail |
| 2ª | Corpo da mensagem atual |
| 3ª | Histórico de todas as mensagens da thread |
| 4ª | Data de envio do e-mail (último recurso) |

**Formatos reconhecidos:**

| Formato | Exemplo |
|---|---|
| DD/MM/AAAA | 29/06/2026 |
| DD.MM.AAAA ou DD-MM-AAAA | 29.06.2026 |
| AAAA-MM-DD (ISO) | 2026-06-29 |
| AAAAMMDD (compacto) | 20260629 |
| DD de Mês de AAAA | 29 de junho de 2026 |
| MM/AAAA (competência mensal) | 05/2026 → usa 31/05 |
| MM/AA (ano com 2 dígitos) | 04/26 → usa 30/04/2026 *(corrigido em 16/07/2026)* |
| Nome de arquivo com data | DRL2160_012026 → usa 31/01 |
| Intervalos de dias | "15 a 20/06/2026" → gera prazo por dia útil |

**2. Calcula o prazo-limite:**

| CADOC | Regra |
|---|---|
| DDR_2011 / 4111 | 3 dias úteis após `data_base` |
| RETORNO_BACEN / SUPORTE / S5 / FORCAPITAL / DRSAC | 5 dias úteis após `data_base` |
| DRL_2160 | 10 dias úteis após `data_base` |
| DRM_2060 | 5 dias úteis a partir do 1º dia do mês seguinte |
| DLO_2061 / DLI_2062 | Dia 5 do segundo mês seguinte à `data_base` |
| 6209 | Último dia útil do mês que segue o trimestre |

Feriados bancários nacionais são considerados automaticamente. O resultado fica em `lista_prazos` no `02_classificação_dados_brutos_gmail_editado.json`.

**O que pode dar errado neste passo:**
- Data extraída errada do assunto → prazo calculado errado desde a origem
- Feriado não cadastrado → prazo pode cair num feriado sem pular

---

### Passo 3 — Integração (Script 09)

Copia `lista_prazos` para o `03_integrador_dados_site.json` sem alteração. O prazo mais recente alimenta o campo `prazo`, usado pelo Script 11 na triagem.

**O que pode dar errado neste passo:** nenhum risco adicional — cópia direta.

---

### Passo 4 — Exibição na tela

A API `/api/dados` entrega `lista_prazos` para a tela. A função `rotuloDataPrazo()` formata e exibe o prazo mais recente no card.

**O que pode dar errado neste passo:** thread com muitas mensagens acumula vários prazos — o sistema sempre usa o mais recente, que pode não ser o mais relevante operacionalmente.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia "DDR 2011 - Posição 29/06/2026" | Assunto contém data `29/06/2026` e CADOC `DDR_2011` |
| Script 05 | Extrai `data_base = 29/06/2026`; aplica regra DDR (+3 dias úteis) → `prazo_limite = 02/07/2026` |
| Script 09 | Copia `lista_prazos` para o JSON 03 |
| Tela | Exibe prazo `02/07/2026` no card da thread |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Data extraída errada do assunto | Prazo incorreto | Regex pegou data errada no texto |
| Feriado não cadastrado | Prazo pode cair num feriado | Lista de feriados em `mapeamento_regras_negocio.json` desatualizada |
| Thread sem nenhuma data em nenhum lugar | Thread sem prazo — sem card na tela | Nenhum fallback encontrou uma data |

---

### O que Michel faz para corrigir

Se um prazo aparecer errado: verificar a `data_base` em `03_integrador_dados_site.json` para aquela thread. Corrigir a lógica de extração no Script 05 e rodar o pipeline novamente.

**Precisa rodar o pipeline?** Script 05 + Script 09 para recalcular os prazos.

**Como consultar quando algo der errado:** `data/json/pipeline/03_integrador_dados_site.json` → campo `lista_prazos` de cada thread.

**Status:** ✅ limpo — validado em produção (6.576 registros, zero erros de cálculo). Formato MM/AA (ex: 04/26) corrigido em 16/07/2026.

---

## Campo 10 — Responsável pela ação

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Bug identificado — ver nota abaixo.

**O que mostra na tela:** o nome de quem precisa agir agora na thread — aparece no card da lista como o "assignee". Diferente do Campo 6 (gravado no arquivo), este campo é **calculado na hora em que a tela carrega**, a partir das mensagens da thread.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não contribui para este campo.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

Não contribui diretamente. O Script 05 resolve o `responsavel` por e-mail individual, que o Script 09 usa como fallback.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 3 — Integração (Script 09)

Calcula e grava o campo `responsavel` no JSON 03 com a função `_responsavel_pela_acao()`. É o valor de fallback caso o cálculo da tela falhe. Usa `timestamp_epoch` para ordenar as mensagens e encontrar a última.

**O que pode dar errado neste passo:** quando uma mensagem tem `timestamp_epoch` zero ou ausente, o Script 09 pode escolher uma mensagem diferente da que o painel escolheria como "última" — gerando divergência.

---

### Passo 4 — Exibição na tela

Na hora de servir os dados, o painel recalcula o responsável com `_responsavel_pela_acao_from_mensagens()` e injeta em `responsavel_pela_acao`. Usa campos de texto (`data_email`, `data_iso`, `timestamp`) para ordenar as mensagens.

| Última mensagem | Quem aparece como responsável |
|---|---|
| Cliente → Finaud | Pessoa da Finaud que recebeu |
| Finaud → Finaud (interno) | Pessoa da Finaud que recebeu |
| Finaud → Cliente | Pessoa do cliente que recebeu |
| Finaud enviou "obrigada/obrigado pelo envio" | Pessoa da Finaud que enviou |

A tela usa: `responsavel_pela_acao` → `responsavel` → `'N/A'`.

**O que pode dar errado neste passo:** as duas funções (Script 09 e painel) ordenam de formas diferentes → divergência para threads com `timestamp_epoch = 0` (ver bug abaixo).

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia relatório DDR para a Finaud | Última mensagem é do cliente (C→F) |
| Script 09 | Última mensagem → origem CLIENTE, destino Rodrigo → `responsavel = "Rodrigo Tibério"` no JSON 03 |
| Painel | Recalcula na hora → mesma mensagem → `responsavel_pela_acao = "Rodrigo Tibério"` |
| Tela | Exibe "Rodrigo Tibério" no card |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Mensagem com `timestamp_epoch = 0` na thread | Responsável diferente do que está no JSON | Script 09 e painel escolhem mensagens diferentes como "última" |
| Nenhum nome identificável na última mensagem | `'N/A'` | Fallback esgotado |

---

### ⚠️ Bug identificado em 13/07/2026

**Em produção: 55 de 4.786 threads mostram na tela um responsável diferente do que está no JSON.** Causa: Script 09 ordena por `timestamp_epoch` (número); painel ordena por `data_email`/`data_iso` (texto). Quando `timestamp_epoch = 0`, cada um escolhe uma mensagem diferente como "última". Correção registrada em `documentações/PENDENCIAS.md`.

---

### O que Michel faz para corrigir

Não é possível corrigir editando o arquivo — o valor vem do cálculo em tempo real do painel. É necessário ajustar a lógica de ordenação no código.

**Precisa rodar o pipeline?** Não — valor calculado na hora de carregar a tela. Após correção do código, atualiza automaticamente.

**Como consultar quando algo der errado:** `data/json/pipeline/03_integrador_dados_site.json` → campo `responsavel` da thread (valor do Script 09; o valor na tela pode diferir para as 55 threads com bug).

**Status:** ⚠️ Bug identificado — 55 threads em produção mostram responsável diferente do JSON. Ver PENDENCIAS.md.

---

## Campo 11 — Quantidade de mensagens

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Validado em produção (4.786 registros — zero erros).

**O que mostra na tela:** o número de mensagens trocadas na thread — aparece no modal. Usado internamente para detectar se chegou uma resposta nova depois que a thread foi fechada.

---

### Passo 1 — Coleta do e-mail (Script 02)

Não calcula este campo, mas coleta as mensagens brutas que serão contadas depois.

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 2 — Classificação (Script 05)

Calcula `qtd_mensagens` como a contagem das mensagens classificadas naquele momento. Grava no `02_classificação_dados_brutos_gmail_editado.json`.

**O que pode dar errado neste passo:** nenhum risco — contagem simples.

---

### Passo 3 — Integração (Script 09)

Recalcula `qtd_mensagens` com base nas mensagens formatadas e grava no `03_integrador_dados_site.json`. Usa esse número para detectar resposta nova após fechamento: se `qtd_mensagens` atual > `qtd_mensagens_no_fechamento` → chegou mensagem nova.

**O que pode dar errado neste passo:** nenhum risco — contagem direta.

---

### Passo 4 — Exibição na tela

O painel recalcula a quantidade na hora de servir os dados, considerando o filtro de data ativo. Com filtro de um dia específico, o número pode ser menor do que o total da thread.

**O que pode dar errado neste passo:** número menor do que o total quando há filtro de data — comportamento esperado, não bug.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Thread tem 3 mensagens | |
| Script 05 | Conta 3 mensagens → `qtd_mensagens = 3` no JSON 02 |
| Script 09 | Reconta → confirma `qtd_mensagens = 3` no JSON 03 |
| Cliente responde (4ª mensagem) + pipeline roda | Script 09 detecta `4 > 3` → sinaliza mensagem nova após fechamento |
| Tela | Exibe contador atualizado no modal |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| Filtro de data ativo | Número menor do que o total da thread | Painel conta só mensagens no período filtrado — comportamento esperado |

---

### O que Michel faz para corrigir

Não há correção necessária — o campo é uma contagem simples e nunca apresenta dado incorreto. O número menor com filtro ativo é intencional.

**Precisa rodar o pipeline?** Não — qualquer recarga do Script 09 recalcula automaticamente.

**Como consultar quando algo der errado:** `data/json/pipeline/03_integrador_dados_site.json` → campo `qtd_mensagens` de cada thread.

**Status:** ✅ limpo — zero erros em 4.786 threads de produção (13/07/2026).

---

## Campo 12 — Data e horário

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Validado em produção (4.786 registros — zero erros).

**O que mostra na tela:** a data e hora da última mensagem da thread — aparece no card e no modal. É o campo que o sistema usa para ordenar as threads (mais recente no topo).

---

### Passo 1 — Coleta do e-mail (Script 02)

Coleta a data e hora a partir do cabeçalho `Date:` do Gmail. Dois campos são gravados:
- `timestamp`: data e hora formatada (ex.: `01/07/2026 18:01`)
- `data_iso`: só a data no formato ISO (ex.: `2026-07-01`) — usado para filtros e ordenação

Quando o cabeçalho `Date:` está vazio, usa `INTERNALDATE` (data de entrega do servidor Gmail) como fallback *(adicionado em 16/07/2026)*.

**O que pode dar errado neste passo:**
- E-mail com data errada no cabeçalho (clock do servidor fora do horário) → `timestamp` e `data_iso` ficam errados — thread aparece fora de ordem ou no dia errado
- `Date:` vazio sem `INTERNALDATE` → `timestamp_epoch = 0` — thread sem data

---

### Passo 2 — Classificação (Script 05)

Não altera os campos de data. Apenas os lê para extrair a `data_base` dos prazos (Campo 9).

**O que pode dar errado neste passo:** nenhum risco para este campo específico.

---

### Passo 3 — Integração (Script 09)

Copia `timestamp` e `data_iso` para o integrador sem alteração. O Script 09 usa `data_iso` para o filtro de carga: só processa mensagens da janela de datas da carga atual.

**O que pode dar errado neste passo:** nenhum risco adicional — cópia direta.

---

### Passo 4 — Exibição na tela

A tela usa `timestamp` para exibir e `data_iso` para filtrar. O filtro de data (botão de período) compara `data_iso` com o intervalo selecionado.

**O que pode dar errado neste passo:** nenhum risco adicional — leitura direta do JSON.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| E-mail chega com `Date: Wed, 01 Jul 2026 18:01:00 -0300` | |
| Script 02 | Converte → `timestamp = "01/07/2026 18:01"`, `data_iso = "2026-07-01"` no JSON 01 |
| Script 05 | Copia sem alterar para JSON 02 |
| Script 09 | Copia sem alterar para JSON 03 |
| Tela | Exibe `01/07/2026 18:01` no card; usa `2026-07-01` para filtros |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| E-mail com data errada no cabeçalho | Thread fora de ordem ou no dia errado | Clock do servidor do remetente desajustado |
| E-mail antigo encaminhado como novo | Data do encaminhamento, não do original | A data que conta é sempre a do envio, não do conteúdo |
| `Date:` vazio + sem `INTERNALDATE` | Thread sem data (`timestamp_epoch = 0`) | Dado inválido no cabeçalho do e-mail |

---

### O que Michel faz para corrigir

Se a data aparecer errada: o problema está no cabeçalho do e-mail original — não é possível corrigir retroativamente.

**Precisa rodar o pipeline?** Não — o campo vem direto do e-mail; só muda se o e-mail for recoletado.

**Como consultar quando algo der errado:** `data/json/pipeline/03_integrador_dados_site.json` → campos `timestamp` e `data_iso` de cada thread.

**Status:** ✅ limpo — zero erros em 4.786 threads de produção (13/07/2026). Fallback `INTERNALDATE` adicionado em 16/07/2026 para e-mails com `Date:` vazio.

---

## Campo 13 — Mensagens da thread (corpo do modal)

> **Status do rastreamento:** ✅ Concluído em 15/07/2026. Varredura de 8.848 mensagens (produção + TESTE) — todos os tipos identificados. Demo: https://claude.ai/code/artifact/cc2f705c-a5bb-479f-bd0e-9ba601c8cedb

**O que mostra na tela:** as mensagens trocadas na thread, exibidas no modal ao clicar num card. Cada mensagem tem: cabeçalho (número, data/hora, lado), remetente/destinatário e corpo. O corpo varia conforme o tipo do e-mail.

---

### Tipos de mensagem identificados em produção

| Tipo | Nome | Quando ocorre | Quantidade aprox. | Status na tela |
|---|---|---|---|---|
| **T1** | Normal | Mensagem com texto completo e estruturado | ~2.687 msgs | ✅ Exibe normalmente |
| **T2** | Curto | Texto muito curto (menos de 80 chars) — ex.: "Segue em anexo." | ~592 msgs | ✅ Exibe normalmente |
| **T3** | Follow-up Finaud | Finaud cobrando resposta do cliente | na base | ✅ Exibe normalmente |
| **T4** | Auto-reply | Resposta automática de ausência/férias | ~804 msgs | ⚠️ Exibe, mas IA deve ignorar |
| **T5** | Encaminhado | Mensagem com conteúdo de outro e-mail colado dentro | ~3.843 msgs | ✅ Exibe normalmente |
| **T6** | Histórico citado | Resposta com blocos de mensagens anteriores | na base | ✅ Recolhido em "▶ Histórico citado" |
| **T7** | Regulatório/BACEN | XML, retorno de validação, crítica do BACEN | na base | ✅ Exibe normalmente |
| **T8.1–8.4** | Imagem inline | Cliente enviou só um print colado no corpo — sem texto | 5 msgs confirmadas | ❌ Corpo vazio (UX-02 pendente) |
| **T8.5** | Só arquivo em anexo | E-mail sem texto, só arquivos anexados | raro | ✅ Exibe aviso com lista de arquivos |
| **T9a** | OCR legível | Arquivo com imagem — OCR extraiu texto com sucesso | ~917 msgs | ✅ Exibe texto extraído |
| **T9b** | OCR com erros | OCR rodou mas texto saiu com erros | incluso no 917 | ✅ Exibe, mas texto imperfeito |

---

### Passo 1 — Coleta do e-mail (Script 02)

Coleta cada e-mail e grava no JSON 01:
- `corpo`: HTML bruto do e-mail
- `corpo_limpo`: texto limpo (sem rodapés, assinaturas, citações repetidas)
- `formato_corpo`: `"html"` ou `"texto"`
- `anexos_detectados`: lista de arquivos (com `content_id` para imagens inline; sem para arquivos reais)
- `encaminhados`: conteúdo de e-mails encaminhados colados dentro do corpo
- `contato_origem.lado`: `"CLIENTE"` ou `"FINAUD"` — define a cor do badge na tela

**O que pode dar errado neste passo:**
- Imagens inline (`cid:`) chegam nos dados mas o Script 12 não as processa → Tipos T8.1–T8.4 ficam com corpo vazio
- E-mails com apenas rodapé de Google Groups → `corpo_limpo` e `anexos_detectados` ficam vazios → corpo aparece em branco (5 casos em produção)

---

### Passo 2 — Classificação (Script 05)

Não altera o corpo das mensagens. Usa `corpo_limpo` para detectar CADOC, prazos e padrões de triagem.

**O que pode dar errado neste passo:** nenhum risco para exibição do corpo.

---

### Passo 3 — Integração (Script 09 + Script 12)

**Script 12** processa arquivos anexados (PDF, XML, imagens separadas) e preenche `texto_imagens` com o texto extraído por OCR → Tipos T9a e T9b. Não processa imagens inline (`cid:`).

**Script 09** copia os campos para o JSON 03 sem alterar. Monta `mensagens[]` de cada thread em ordem cronológica.

**O que pode dar errado neste passo:**
- Script 12 falha no OCR → `texto_imagens` vazio → texto do arquivo não aparece na tela

---

### Passo 4 — Exibição na tela

O template `email_operacional.html` renderiza cada mensagem da lista `mensagens[]` no modal:

| Situação | O que o template faz |
|---|---|
| `corpo_limpo` tem texto | Exibe o texto (T1–T7) |
| `corpo_limpo` tem texto + `anexos_detectados` tem arquivos reais | Exibe texto + chips 📎 abaixo *(adicionado em 16/07/2026)* |
| `texto_imagens` tem texto | Exibe após o corpo (T9a, T9b) |
| `corpo_limpo` vazio + `anexos_detectados` tem arquivos reais | Exibe aviso "⚠ Sem texto — ver anexo" com lista de arquivos (T8.5) |
| `corpo_limpo` vazio + sem arquivo real + sem OCR | Corpo aparece em branco (T8.1–T8.4) |

**O que pode dar errado neste passo:**
- Tipos T8.1–T8.4 (imagem inline como único conteúdo) → corpo vazio até UX-02 ser implementado

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail com texto + arquivo .xlsx | |
| Script 02 | Extrai `corpo_limpo` (texto) e detecta `.xlsx` em `anexos_detectados` |
| Script 12 | Se `.xlsx` tiver imagens: roda OCR → preenche `texto_imagens` |
| Script 09 | Monta `mensagens[]` com `corpo_limpo`, `texto_imagens` e `anexos_detectados` no JSON 03 |
| Tela | Exibe texto do corpo + chip `📎 arquivo.xlsx` abaixo |

---

### ⚠️ O que pode dar errado

| Situação | O que aparece na tela | Por que acontece |
|---|---|---|
| E-mail só com imagem inline (print colado) | Corpo vazio | Script 02 coleta `cid:` mas Script 12 não processa — UX-02 pendente |
| Rodapé de Google Groups sem texto e sem anexo | Corpo em branco | `corpo_limpo` e `anexos_detectados` ficam vazios após limpeza |
| Script 12 falha no OCR | Texto do arquivo não aparece | `texto_imagens` vazio — arquivo com qualidade baixa |
| 365 alertas automáticos do Oráculo | Aparecem na fila indevidamente | Leiautes e normativos gerados pelo próprio sistema ainda não filtrados — UX-04 pendente |

---

### O que Michel faz para corrigir

- **Corpo vazio (T8.1–T8.4):** aguardar implementação de UX-02. Sem solução no momento.
- **Alertas automáticos na triagem:** aguardar implementação de UX-04. Registrado em PENDENCIAS.md.
- **OCR com texto errado:** arquivo fonte tem qualidade baixa — sem correção automática.

**Precisa rodar o pipeline?** Script 12 + Script 09 se quiser reprocessar OCR de um arquivo específico.

**Como consultar quando algo der errado:**
- `data/json/pipeline/03_integrador_dados_site.json` → `threads[].mensagens[]`
- Demo com todos os tipos e exemplos reais: https://claude.ai/code/artifact/cc2f705c-a5bb-479f-bd0e-9ba601c8cedb

**Status:** ⚠️ Dois problemas conhecidos: T8.1–T8.4 (imagens inline = corpo vazio) aguarda UX-02; 365 alertas automáticos na triagem aguarda UX-04. Ver PENDENCIAS.md.

---
