# Guia de Campos — Tela Operacional (`/operacional`)

> **Para que serve:** descreve campo por campo o que aparece na tela operacional —
> de onde vem cada informação, qual script a preenche e quais regras se aplicam.
>
> Leia junto com: [Linhagem de Dados](LINHAGEM_DADOS_OPERACIONAL.md)
> — mostra o caminho completo de cada campo desde o e-mail até a tela (todos os JSONs intermediários).
>
> _Atualizado: 2026-07-13_

---

## Campo 1 — Assunto

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** o texto do assunto do e-mail aparece no card da thread — por exemplo, `Re: DDR 2011 - Posição Janeiro`. É o título que identifica o assunto daquela conversa. Prefixos de resposta (`Re:`, `RES:`, `ENC:`, `FW:`) são mantidos exatamente como vieram.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 acessa o Gmail e lê o campo `Subject:` de cada e-mail. O servidor pode entregar esse campo em formato codificado (caracteres especiais ou acentos em encoding específico) — o script decodifica para texto legível e grava como `assunto` no arquivo `01_extração_dados_brutos_gmail.json`.

*Em linguagem simples: é como abrir uma carta e copiar o assunto exatamente como está escrito no cabeçalho — com todos os prefixos de resposta e acentos.*

**O que pode dar errado:**

| Situação | O que o sistema faz |
|---|---|
| Assunto normal | Grava e exibe corretamente |
| Assunto com caractere que não consegue decodificar | Substitui o caractere por `?` e grava assim — **sem erro, sem aviso** |
| Assunto completamente ilegível | Grava `"Assunto Corrompido"` |
| E-mail sem assunto | Grava `"Sem Assunto"` |

⚠️ **Atenção:** o caso do meio é o mais perigoso. Se você ver um assunto com `?` no meio, significa que o e-mail chegou com caractere que o sistema não conseguiu decodificar. O assunto foi gravado e está sendo exibido, mas o texto está errado — e ninguém recebe aviso sobre isso.

---

### Passo 2 — Classificação (Script 05)

O Script 05 usa o assunto para ajudar a identificar o cliente e o CADOC regulatório — por exemplo, se o assunto contém `4111` ou `DDR`, isso influencia a classificação. O assunto em si é copiado sem alteração para o arquivo `02_classificação_dados_brutos_gmail_editado.json`.

*Em linguagem simples: o classificador lê o assunto para entender do que se trata o e-mail, mas não muda o texto — só o usa como pista.*

**O que pode dar errado:** nenhum risco para o campo em si — o assunto só é lido, nunca reescrito nesta etapa.

---

### Passo 3 — Integração (Script 09)

O Script 09 monta os dados que a tela vai exibir. Neste passo, o campo `assunto` é renomeado para `titulo` e gravado no arquivo `03_integrador_dados_site.json`. O conteúdo não muda.

*Em linguagem simples: é como passar a informação de uma ficha para outra — o texto é o mesmo, só o nome do campo muda de `assunto` para `titulo`.*

**O que pode dar errado:** nenhum risco — é uma cópia direta.

---

### Passo 4 — Exibição na tela

A tela lê o campo `titulo` do JSON 03 e exibe no card da thread. Se `titulo` vier vazio, a tela exibe `"Sem título"` como fallback.

*Em linguagem simples: a tela pega o texto e coloca no card. Se não tiver nada, escreve "Sem título" para não deixar o card em branco.*

**O que pode dar errado:** se o pipeline não rodou após um novo e-mail chegar, o `titulo` pode estar desatualizado — mostra o assunto de um e-mail anterior da thread, não do mais recente.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail com assunto `Re: DDR 2011 - Posição Janeiro` | |
| Script 02 | Lê o `Subject:`, decodifica, grava `assunto = "Re: DDR 2011 - Posição Janeiro"` no JSON 01 |
| Script 05 | Copia o `assunto` sem alterar para o JSON 02; usa o texto para identificar DDR_2011 |
| Script 09 | Renomeia para `titulo` e grava no JSON 03 |
| Tela | Exibe `"Re: DDR 2011 - Posição Janeiro"` no card |

---

### O que Michel faz para corrigir

O assunto vem do e-mail original e **não pode ser corrigido pelo pipeline**. Se aparecer com `?` no meio, o encoding veio errado do servidor do remetente — problema na origem, fora do controle do sistema. Se aparecer `"Sem Assunto"`, o remetente não preencheu o campo.

**Precisa rodar o pipeline?** Não — não há como corrigir retroativamente.

**Como consultar quando algo der errado:** abrir `data/json/pipeline/01_extração_dados_brutos_gmail.json` e buscar o e-mail pelo `id`; verificar o campo `assunto`.

**Status:** ✅ limpo — nenhum problema identificado nos dados.

---

## Campo 2 — ID do caso

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** um número que aparece no card da thread — por exemplo `78`. É o identificador único do **e-mail mais recente** daquela conversa, atribuído pelo servidor IMAP do Gmail.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 acessa o Gmail via IMAP. Quando o servidor entrega cada e-mail, ele envia junto um número de sequência único — esse é o `id`. O script grava esse número no arquivo `01_extração_dados_brutos_gmail.json` como campo `id`.

*Em linguagem simples: é como um número de protocolo que a agência postal coloca no envelope quando ele chega. Não é você que escolhe — é o servidor que atribui automaticamente.*

Antes de gravar, o Script 02 compara os IDs dos e-mails novos com os que já estão no arquivo. Se o `id` já existe, o e-mail é ignorado — evitando duplicatas.

*Em linguagem simples: é como o carteiro olhar a lista dos protocolos que já foram registrados antes de assinar o recebimento. Se o número já está na lista, ele não registra de novo.*

**O que pode dar errado:** nenhum — o IMAP sempre entrega o `id` junto com o e-mail. Não existe e-mail sem `id` neste protocolo.

---

### Passo 2 — Classificação (Script 05)

O Script 05 copia o `id` sem alterar para o arquivo `02_classificação_dados_brutos_gmail_editado.json`. Não usa o campo para nenhuma lógica.

**O que pode dar errado:** nenhum risco — cópia direta.

---

### Passo 3 — Integração (Script 09)

O Script 09 copia o `id` de cada e-mail para o arquivo `03_integrador_dados_site.json`, mantendo o mesmo nome de campo `id`.

**O que pode dar errado:** nenhum risco — cópia direta.

---

### Passo 4 — Exibição na tela

A tela agrupa os e-mails por thread e pega o **último da lista** (o mais recente). O `id` desse e-mail é exibido no card.

*Em linguagem simples: a tela olha todos os e-mails da conversa, pega o mais novo e mostra o número de protocolo dele.*

**O que pode dar errado:** se o pipeline não rodou após um novo e-mail chegar, a tela mostra o `id` do penúltimo e-mail — não do mais recente.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Novo e-mail chega na caixa da Finaud | Gmail atribui o número `78` a esse e-mail |
| Script 02 | Verifica que `78` não existe no JSON 01; baixa e grava `id = "78"` |
| Script 05 | Copia `id = "78"` para o JSON 02 sem alterar |
| Script 09 | Copia `id = "78"` para o JSON 03 sem alterar |
| Tela | Pega o e-mail mais recente da thread e exibe `78` no card |

---

### O que Michel faz para corrigir

Nenhuma ação necessária — o `id` é atribuído pelo Gmail automaticamente e nunca está incorreto.

**Precisa rodar o pipeline?** Não aplicável.

**Como consultar quando algo der errado:** verificar campo `id` no `data/json/pipeline/01_extração_dados_brutos_gmail.json`.

**Status:** ✅ limpo — o campo sempre é preenchido corretamente.

---

## Campo 3 — Remetente

> **Status do rastreamento:** ✅ Concluído em 10/07/2026.

**O que mostra na tela:** aparece no histórico de mensagens de cada thread — linha
"Remetente: Ana Paola do Nascimento - Unicred do Brasil · ana.paola@unicred.com.br".
É a informação bruta de quem enviou cada mensagem individual da conversa.

---

### Passo 1 — Coleta do e-mail bruto (Script 02)

`02_coletar_emails_gmail.py` acessa o Gmail via IMAP com a conta `coleta.oraculo@finaud.com.br`
e extrai o campo `remetente` exatamente como vem do servidor — sem interpretação.
Grava no `01_extração_dados_brutos_gmail.json`.

*Em linguagem simples: é o carteiro que vai até a caixa de correio, pega as cartas e anota
quem mandou cada uma. Ele copia exatamente o que está escrito no envelope — sem verificar
se o endereço é válido ou se faz sentido.*

**O que pode dar errado:**

- **Gmail fora do ar** → Script 02 não roda → JSON 01 não atualizado → e-mail some sem rastro
  *(falha silenciosa — sem alerta)*

  *Em linguagem simples: se a caixa de correio estiver fechada, o carteiro volta para casa
  sem avisar ninguém. O e-mail existia, mas o sistema nunca ficou sabendo.*

  *Exemplo: às 8h o Gmail teve instabilidade de 10 minutos. O Script 02 rodou nesse horário,
  não coletou nada, e registrou "0 e-mails novos" — sem erro, sem aviso. O e-mail da
  Western Union ficou perdido.*

- **E-mail com `Reply-To` preenchido** → o remetente real pode ser diferente do `From:`

  *Em linguagem simples: alguns e-mails têm dois endereços de remetente — o que enviou de
  fato e o que quer receber a resposta. O sistema anota os dois separadamente.*

  *Exemplo: o e-mail veio de `sistema@bacen.gov.br` mas o campo "responder para" era
  `regulatorio@bacen.gov.br`. O Script 02 anota os dois — `remetente` e `reply_to_raw`
  — sem decidir qual é o "real". Essa decisão fica para o Script 05.*

---

### Passo 2 — Identificação do remetente real (Script 05)

O script 05 precisa saber **quem está do outro lado da conversa**. O campo `De:` do e-mail
nem sempre tem essa resposta — e o principal motivo é o comportamento do grupo `suporte@finaud.com.br`.

**Por que o Gmail substitui o remetente no grupo suporte**

O `suporte@finaud.com.br` é uma lista de distribuição do Google Groups. Quando um cliente
envia um e-mail para esse endereço, o Gmail não entrega o e-mail diretamente — ele redistribui
para todos os membros do grupo. Nessa redistribuição, o Gmail **substitui o `De:` original do
cliente** pelo endereço do grupo, e coloca o remetente real no campo `Reply-To:`. Isso acontece
porque o grupo precisa aparecer como origem para que as respostas sejam enviadas corretamente
para todos os membros — não apenas para quem enviou.

**Exemplo real — o que chega no e-mail:**

```
De:       'Leonardo Ueda' via Suporte <suporte@finaud.com.br>
Reply-To: leonardo.ueda@westernunion.com
Para:     suporte@finaud.com.br
Assunto:  Re: Western Union - DLO março/26
```

Sem a regra, o sistema identificaria o remetente como `suporte@finaud.com.br` — ou seja,
a própria Finaud — e descartaria o e-mail como interno. O cliente ficaria invisível.

**A regra no script 05 (`scripts/05_classificar_emails_regulatorio.py`, linhas 605–608):**

```python
remetente_real = email_remetente
if email_reply and not eh_email_finaud_check(email_reply, dominios_finaud):
    remetente_real = email_reply
```

Em linguagem simples: "se existe um `Reply-To:` e ele não é da Finaud, use ele como
remetente real em vez do `De:`".

**O que aconteceria sem essa regra**

Todos os e-mails que chegam pelo grupo suporte (1.741 casos em produção) seriam classificados
como e-mails internos da Finaud e ignorados. Nenhum desses clientes apareceria na tela —
a conversa existiria no Gmail mas seria invisível no sistema.

---

### Todos os cenários de remetente mapeados

> **Validação (10/07/2026):** varredura completa de 8.825 e-mails em produção e 47 em teste —
> todos os cenários abaixo estão funcionando corretamente, zero furos encontrados.
> Script de consulta: `scripts/consultas/diagnostico_cenarios_email.py`

#### Lado do cliente — quando alguém de fora envia para a Finaud

| Cenário | De: | Para: | CC: | Reply-To: | Como identifica o cliente | Contato no card | Empresa no card | Responsável no card | Funciona? |
|---|---|---|---|---|---|---|---|---|---|
| **A** — Cliente envia direto para colaboradora | `gustavo@banvox.com.br` | `monica@finaud.com.br` | — | vazio | Campo `De:` | Gustavo Do Carmo Rudink | Banvox | Monica Macedo | ✅ 1.342 casos |
| **B1** — Cliente envia para o grupo suporte | `'Gustavo' via Suporte <suporte@finaud.com.br>` | `suporte@finaud.com.br` | — | `gustavo@banvox.com.br` | Campo `Reply-To:` | Leonardo Ueda | Western Union | Quem responder | ✅ 1.741 casos |
| **B2/B3** — Cliente envia com suporte no Para/CC | `marcos@smartsafe.com.br` | `monica@finaud.com.br` | `suporte@finaud.com.br` | vazio | Campo `De:` | Marcos Franco | Smartsafe Brasil | Monica Macedo | ✅ 753 casos |
| **B4** — Grupo reencaminha cópia interna para membros | `suporte@finaud.com.br` | `rodrigo@finaud.com.br` | — | vazio | Não aplicável — e-mail interno | — | — | — | ✅ não exibe na tela — correto |
| **BCC** — Suporte em cópia oculta | `gustavo@banvox.com.br` | `monica@finaud.com.br` | — | vazio | Campo `De:` (igual ao A) | Gustavo Do Carmo Rudink | Banvox | Monica Macedo | ✅ tratado como A |

#### Lado da Finaud — quando uma colaboradora envia ou responde

| Cenário | De: | Para: | Como o sistema trata | Contato no card | Empresa no card | Responsável no card | Funciona? |
|---|---|---|---|---|---|---|---|
| **FC** — Finaud responde ou envia para cliente | `andrea@finaud.com.br` | `wilson@ozcambio.com.br` | Entra na mesma thread do cliente — é mais uma mensagem da conversa | Wilson Lima | Oz Câmbio | Andrea Inacio | ✅ 3.191 casos |
| **FF** — Finaud envia internamente (colaboradora para colaboradora) | `riskdriver@finaud.com.br` | `michel@finaud.com.br` | Thread interna — aparece na tela com `cliente = Finaud` | Michel | Bacen / vazio | Michel | ✅ 1.790 casos |

> **Nota FC:** quando a Andrea responde para o cliente, o e-mail entra na thread existente
> do cliente (mesmo ID de conversa no Gmail). O card continua mostrando o cliente como contato
> principal — a resposta da Andrea só aumenta o contador de mensagens.

> **Nota FF:** e-mails do `riskdriver@finaud.com.br` são relatórios automáticos do sistema
> de risco. E-mails do `contato@finaud.com.br` são avisos do BACEN redistribuídos internamente.
> Ambos aparecem na tela como threads internas da Finaud, não como threads de clientes.

---

### Passo 3 — Integração (Script 09)

O Script 05 grava o remetente como um objeto chamado `contato_origem`, com três informações: o lado (`CLIENTE` ou `FINAUD`), o nome da pessoa e o e-mail. O Script 09 copia esse objeto inteiro para cada mensagem dentro do JSON 03 — sem alterar nenhum dado.

*Em linguagem simples: o Script 05 monta uma ficha com três campos — quem enviou, se é cliente ou Finaud, e o e-mail. O Script 09 cola essa ficha no registro da mensagem, sem tocar em nada.*

**O que pode dar errado:**

- **`contato_origem` vazio (falha silenciosa)** — se o Script 05 não conseguiu identificar o remetente (e-mail malformado ou caso não previsto), o `contato_origem` chega vazio no JSON 03 e a linha "Remetente:" simplesmente desaparece do histórico da thread. Nenhum aviso na tela, nenhum log de alerta.

---

### Passo 4 — Exibição na tela

A tela lê o `contato_origem` de cada mensagem e monta a linha de remetente no formato `Nome · email`. Antes de exibir, remove automaticamente o sufixo `" via Suporte"` que o Gmail coloca no nome quando o e-mail passou pelo grupo — para que o usuário veja o nome limpo, sem jargão técnico.

*Em linguagem simples: a tela pega a ficha montada pelo Script 05, limpa o nome se tiver sujeira do grupo, e exibe como "Remetente: Leonardo Ueda · leonardo.ueda@westernunion.com".*

**O que pode dar errado:**

- **Nome codificado** — nomes com caracteres especiais chegam às vezes no formato técnico de e-mail (ex.: `=?UTF-8?Q?Ana_Paola?=`). A tela tenta decodificar, mas se falhar, exibe os símbolos brutos em vez do nome legível. Nenhum aviso — falha silenciosa.

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail para `suporte@finaud.com.br` | Gmail redistribui, coloca `Reply-To: leonardo.ueda@westernunion.com` |
| Script 02 | Grava `remetente = "suporte@finaud.com.br"` e `reply_to = "leonardo.ueda@westernunion.com"` no JSON 01 |
| Script 05 | Detecta que `Reply-To` não é da Finaud → define `remetente_real = leonardo.ueda@westernunion.com`; monta `contato_origem = {lado: CLIENTE, nome: Leonardo Ueda, email: leonardo.ueda@westernunion.com}` no JSON 02 |
| Script 09 | Copia `contato_origem` para o JSON 03 sem alterar |
| Tela | Exibe `Remetente: Leonardo Ueda · leonardo.ueda@westernunion.com` no histórico da thread |

---

### O que Michel faz para corrigir

- **Remetente não aparece no histórico** (`contato_origem` vazio): verificar no `02_classificação_dados_brutos_gmail_editado.json` se o Script 05 processou o e-mail corretamente. Rodar Script 05 + Script 09 pode resolver.
- **Nome com símbolos brutos na tela**: problema de encoding que vem na origem do e-mail — sem correção possível pelo pipeline.

**Precisa rodar o pipeline?** Sim — Script 05 e Script 09 para reprocessar.

**Como consultar quando algo der errado:** rodar `python scripts/consultas/diagnostico_cenarios_email.py` para verificar se o e-mail foi capturado e em qual cenário foi classificado.

---

## Campo 4 — Cliente

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** nome da pessoa que representa o cliente naquela thread — aparece no badge "Cliente" do modal (ex.: `Ana Paola do Nascimento`). É a **pessoa do lado de fora da Finaud** que é o contato daquela conversa. Não é o nome da empresa (isso é o Campo 5 — Empresa).

---

### Passo 1 — Identificação do contato do cliente (Script 05)

O Script 05 resolve quem é a pessoa do cliente com base em quem enviou e quem recebeu cada e-mail, seguindo esta lógica:

- Se quem enviou é do lado **CLIENTE** → o contato é o nome/e-mail do remetente
- Se quem enviou é da **Finaud** → o contato é o nome/e-mail de quem recebeu do lado externo
- Se é **Finaud para Finaud** → grava `"Finaud"` (thread interna)
- Se não consegue identificar ninguém externo → grava `"CLIENTE_DESCONHECIDO"`

O resultado é gravado no campo `cliente` do JSON 02.

*Em linguagem simples: o Script 05 olha quem mandou e quem recebeu e decide "quem é a pessoa do cliente nesta conversa". Quando o cliente envia para a Finaud, o contato é quem mandou. Quando a Finaud envia para o cliente, o contato é quem recebeu.*

**O que pode dar errado:**
- Nome com encoding especial (ex.: `=?UTF-8?Q?Ana_Paola?=`) → pode ser gravado com símbolos brutos se a decodificação falhar

---

### Passo 2 — Classificação (Script 05 — continuação)

Não há etapa separada. O campo `cliente` é gravado diretamente no JSON 02 pelo mesmo script.

---

### Passo 3 — Integração (Script 09)

O Script 09 lê a **primeira mensagem** da thread para definir o contato do cliente de toda a conversa — usando a mesma lógica do Script 05. Grava o campo `cliente` no JSON 03 a nível de thread (uma vez só, valendo para todas as mensagens).

*Em linguagem simples: o Script 09 olha a primeira mensagem da conversa para decidir quem é o contato do cliente desta thread e grava esse nome uma vez, representando toda a conversa.*

**Análise de risco realizada em 13/07/2026:**

Levantamos a hipótese de que, se a primeira mensagem de uma thread fosse interna (Finaud → Finaud), o script poderia identificar o contato como `"Finaud"` ou `"CLIENTE_DESCONHECIDO"` — mesmo que as mensagens seguintes fossem com um cliente externo.

Para confirmar ou descartar, varremos os dois ambientes:

| Ambiente | Total de threads | CLIENTE_DESCONHECIDO | cliente=Finaud com CADOC externo |
|---|---|---|---|
| TESTE | 36 | 0 | 0 |
| Produção | 4.786 | 0 | 1.185 (todos RISK_DRIVER — correto) |

**Conclusão:** os 1.185 casos com `cliente = "Finaud"` em produção são todos relatórios automáticos do sistema de risco (`riskdriver@finaud.com.br`) enviados internamente — são genuinamente F→F, portanto `"Finaud"` é o valor correto. Zero casos de `CLIENTE_DESCONHECIDO` em 4.786 threads.

O risco não se materializa na prática: threads que começam F→F permanecem F→F. Nunca ocorre de um cliente externo entrar numa conversa que começou entre colaboradoras da Finaud.

---

### Passo 4 — Exibição na tela

- **No modal:** exibe `thread.cliente` diretamente no campo "Cliente". Se vazio, exibe `"—"`
- **No card da lista:** usa `empresa` em primeiro lugar; se empresa estiver vazia, usa `cliente` como fallback

*Em linguagem simples: no modal, mostra o nome da pessoa do cliente. No card da lista, tenta mostrar o nome da empresa — se não tiver empresa cadastrada, mostra o nome da pessoa no lugar.*

**O que pode dar errado:**
- Nome com encoding especial → pode aparecer com símbolos brutos na tela (mesma situação do Campo 3)

---

### Passo 5 — Caminho feliz

| Etapa | O que acontece |
|---|---|
| Cliente envia e-mail | `contato_origem.lado = CLIENTE`, `contato_origem.nome = "Ana Paola do Nascimento"` |
| Script 05 | Grava `cliente = "Ana Paola do Nascimento"` no JSON 02 |
| Script 09 | Lê a primeira mensagem da thread, confirma `lado = CLIENTE`, grava `cliente = "Ana Paola do Nascimento"` no JSON 03 |
| Tela (modal) | Exibe `Cliente: Ana Paola do Nascimento` |
| Tela (card) | Empresa vazia? Exibe `Ana Paola do Nascimento` no lugar da empresa |

---

### O que Michel faz para corrigir

- **`CLIENTE_DESCONHECIDO`** (não ocorre hoje, mas se ocorrer): investigar no `02_classificação_dados_brutos_gmail_editado.json` o `contato_origem` da primeira mensagem da thread para entender por que o cliente não foi identificado. Após identificar a causa, rodar Script 09.
- **Nome com símbolos brutos na tela**: problema de encoding que vem na origem do e-mail — sem correção possível pelo pipeline.

**Precisa rodar o pipeline?** Sim — Script 09.

**Como consultar quando algo der errado:** abrir `data/json/pipeline/03_integrador_dados_site.json` e buscar a thread pelo `threadId`; verificar o campo `cliente`.

**Status:** ✅ limpo — zero casos de `CLIENTE_DESCONHECIDO` confirmados em varredura de 4.786 threads de produção (13/07/2026).

---

## Campo 5 — Empresa

> **Status do rastreamento:** ✅ Concluído em 09/07/2026 — todos os 5 passos rastreados.
> Este campo serve de **exemplo do método** para os demais campos.

**O que mostra na tela:** nome oficial da empresa do cliente — aparece no card da lista
(ex: 📩 Unicred) e no badge "Empresa" do modal.

---

### Passo 1 — Resolução do nome oficial (Script 09)

`09_integrar_dados_painel.py` pega o domínio do e-mail do `remetente_real` (resolvido pelo
Script 05) e consulta o `cadastro_clientes_cadoc.json`. Se encontra → grava o nome oficial.
Se não encontra → grava string vazia `""`.

*Em linguagem simples: o sistema pega o endereço de e-mail do cliente, olha só a parte
depois do @ (exemplo: `unicred.com.br`) e consulta a lista de cadastro.
Se encontrar, pega o nome oficial da empresa. Se não encontrar, deixa em branco.*

**O que pode dar errado:**

- **Domínio não cadastrado** → empresa vazia, sem aviso na tela

  *Em linguagem simples: chegou e-mail de empresa que ainda não está na lista de cadastro.
  O sistema deixa o campo vazio e não avisa Michel.*

  *Exemplo: Oz Câmbio enviou o primeiro e-mail. O domínio `ozcambio.com.br` não estava
  no cadastro. O card apareceu com o nome da pessoa em vez do nome da empresa — Michel
  precisou identificar manualmente.*

- **Domínio genérico** (gmail, hotmail) → vazio intencional ✅

  *Em linguagem simples: pessoa física usando Gmail não tem empresa para mostrar.
  Isso é esperado e correto.*

- **Cadastro atualizado manualmente** → não reflete na hora

  *Em linguagem simples: Michel adiciona a empresa na lista, mas a tela só vai mostrar
  depois que o Script 09 rodar de novo — não atualiza na hora.*

  *Exemplo: Michel cadastrou a Lastro no arquivo de cadastro às 10h. A tela continuou
  mostrando empresa vazia até rodar o Script 09 às 14h na próxima carga.*

**O que acontece na tela quando empresa está vazia:**
- Card mostra o nome do cliente (nome bruto do `De:`) no lugar da empresa
- Modal mostra badge "Empresa" vazio
- Sistema não avisa Michel *(falha silenciosa)*

**O que Michel faz para corrigir:**
1. Acessa `data/json/config/cadastro_clientes_cadoc.json` e adiciona o domínio
2. Roda o Script 09 pelo painel (`/admin/pipeline`)
3. A tela atualiza após o Script 09 concluir — não é imediato

---

### Passo 2 — Gravação no JSON 03

**O que acontece:** depois de resolver o nome da empresa (Passo 1), o Script 09 monta um
dicionário com todos os campos da thread — incluindo `empresa` — e grava tudo no arquivo
`03_integrador_dados_site.json`. Esse arquivo é a "memória central" que a tela lê.

*Em linguagem simples: é como montar a ficha completa do caso. O Script 09 pega todas as
informações da thread (assunto, cliente, empresa, responsável, mensagens...), coloca em
uma ficha estruturada e salva no arquivo central. A tela operacional usa esse arquivo como
fonte de dados — ela não busca os e-mails diretamente, só lê o que está na ficha.*

**Onde no código:** `scripts/09_integrar_dados_painel.py`, função `_processar_threads()`,
linha ~1196 — bloco `thread_formatada = {...}`.

**Como `empresa` entra na ficha:**
```python
thread_formatada = {
    ...
    "empresa": _resolver_empresa({
        "assunto": thread.get("assunto", ""),
        "mensagens": mensagens_formatadas
    }),
    ...
}
```

*Em linguagem simples: o Script 09 chama a função que busca o nome da empresa no cadastro
e grava o resultado diretamente na ficha. Se a função não encontrar, grava string vazia.*

**Arquivo de saída:** `data/json/pipeline/03_integrador_dados_site.json`

**Backup automático:** antes de gravar o novo JSON 03, o Script 09 cria automaticamente
uma cópia do arquivo anterior em `03_integrador_dados_site.json.backup`.

**O que pode dar errado:**

- **Script 09 falha no meio da execução** → JSON 03 fica corrompido ou incompleto

  *Exemplo: Script 09 processou 30 das 36 threads e parou por erro de memória. O JSON 03
  ficou com só 30 threads. A tela sumiu com 6 cases sem avisar Michel.*

  *O que fazer: restaurar o backup e rodar o Script 09 de novo.*

- **Arquivo de cadastro corrompido** → todas as threads ficam com `empresa: ""`

  *Exemplo: alguém editou o `cadastro_clientes_cadoc.json` manualmente e introduziu uma
  vírgula a mais. O arquivo ficou inválido. O Script 09 usou lista vazia e gravou empresa
  vazia para todas as threads — sem aviso.*

---

### Passo 3 — Entrega pela API

**O que acontece:** quando a tela operacional carrega, ela faz uma chamada ao endereço
`/api/dados` do Flask. O Flask lê o JSON 03 (ou usa a cópia em memória, se ainda válida),
processa cada thread e devolve os dados para o navegador — incluindo o campo `empresa`.

**Caminho do código:**
1. `painel_oraculo.py` → rota `/api/dados` (linha 3540)
2. Chama `painel_operacional_snapshot.montagem_api_dados_snapshot()`
3. Para cada thread: se `empresa` vazia no JSON 03, tenta buscar novamente pelo e-mail do
   lado CLIENTE; depois aplica `_rotulo_empresa_gestao_para_api()` — consulta
   `rotulos_empresa_gestao.json` para padronizar nomes

**Dupla computação — ponto crítico:**
O campo `empresa` é calculado **duas vezes** — uma no Script 09 (Passos 1+2) e outra na
API (Passo 3). Mesmo que o Script 09 grave `empresa: ""`, a API pode preencher o campo.
Mas se a lógica dos dois lugares divergir, os resultados podem ser diferentes.

*Em linguagem simples: dois cozinheiros com receitas ligeiramente diferentes. Na maioria
das vezes o resultado parece igual — mas quando há diferença, o prato sai diferente
dependendo de quem cozinhou.*

**Cache em memória:** o Flask mantém o JSON 03 em memória. Quando o Script 09 atualiza
o arquivo, o cache invalida automaticamente.

**O que pode dar errado:**

- **Rótulo não cadastrado** → empresa fica como domínio cru (ex: `oliveiratrust.com.br`)

  *Exemplo: Oliveira Trust tinha o domínio cadastrado mas o rótulo estava escrito diferente.
  A tela mostrava `oliveiratrust.com.br` em vez do nome correto.*

- **Cache desatualizado** → tela mostra dados antigos mesmo após rodar Script 09

  *O que fazer: aguardar alguns segundos e recarregar. Se persistir, reiniciar o servidor Flask.*

---

### Passo 4 — Exibição na tela

**No card da lista** (`email_operacional.html`, linha ~3732):
```javascript
<span>📩 ${escapeHtml(decodeMimeHeader((latest.empresa || latest.cliente) || '') || 'DESCONHECIDO')}</span>
```

*Prioridade: (1) nome oficial da empresa, (2) nome do cliente, (3) "DESCONHECIDO".*

**No modal de detalhes (badge "Empresa")** (linha ~4617):
```javascript
var empresa = (thread.empresa || "").trim();
if (!empresa && currentThreadId && THREADS[currentThreadId]) {
    var ev = getThreadLatest(THREADS[currentThreadId]);
    empresa = (ev.empresa || ev.cliente || "").trim();
}
if (empresa) {
    empresaEl.textContent = empresa;
    empresaChip.style.display = "inline-flex";
} // se vazio: badge fica oculto (display: none)
```

*Se empresa e cliente estiverem vazios, o badge "Empresa" desaparece completamente — não
aparece em branco, some.*

**Resumo de fallback:**

| Situação | Card mostra | Modal badge |
|---|---|---|
| `empresa` preenchida | nome oficial | nome oficial |
| `empresa` vazia, `cliente` preenchido | nome bruto do De: | nome bruto do De: |
| ambos vazios | 📩 DESCONHECIDO | badge oculto |

---

### Passo 5 — Caminho feliz completo resumido

| Etapa | Quem faz | O que acontece | Resultado |
|---|---|---|---|
| 1 | Script 02 | Baixa o e-mail da Lastro Capital com `From: compliance@lastrocapital.com.br` | JSON 01 → `remetente: compliance@lastrocapital.com.br` |
| 2 | Script 05 | Sem `Reply-To` → `remetente_real = remetente` | JSON 02 → `contato_origem.email: compliance@lastrocapital.com.br` |
| 3 | Script 09 | Extrai domínio `lastrocapital.com.br` → encontra no cadastro | JSON 03 → `"empresa": "Lastro Capital"` |
| 4 | API `/api/dados` | Passa por `_rotulo_empresa_gestao_para_api()` → confirma nome | Payload → `"empresa": "Lastro Capital"` |
| 5 | JavaScript | Recebe `empresa: "Lastro Capital"` → monta card e modal | Card: 📩 Lastro Capital; modal: badge "Empresa: Lastro Capital" |

**Condições para o caminho feliz:**
- E-mail tem `From:` válido
- Sem `Reply-To` (ou com `Reply-To` do mesmo domínio)
- Domínio está em `cadastro_clientes_cadoc.json`
- Script 09 rodou após o último e-mail chegar
- Servidor Flask em execução

**Quando o caminho feliz quebra → ver Passos 1–4 para diagnóstico por etapa.**

---

### O que Michel faz para corrigir

- **Empresa vazia:** acessar `data/json/config/cadastro_clientes_cadoc.json`, adicionar o domínio da empresa e rodar o Script 09 pelo painel (`/admin/pipeline`)
- **Script 09 falhou no meio:** restaurar o backup `03_integrador_dados_site.json.backup` e rodar o Script 09 de novo
- **Cadastro corrompido:** abrir o `cadastro_clientes_cadoc.json` e corrigir o erro de sintaxe (vírgula, aspas faltando) antes de rodar o Script 09
- **Cache desatualizado após rodar Script 09:** aguardar alguns segundos e recarregar a tela; se persistir, reiniciar o servidor Flask

**Precisa rodar o pipeline?** Sim — Script 09 para qualquer correção no campo Empresa.

**Como consultar quando algo der errado:** abrir `data/json/pipeline/03_integrador_dados_site.json` e buscar a thread pelo `threadId`; verificar o campo `empresa`. Se estiver vazio, verificar o `data/json/config/cadastro_clientes_cadoc.json` pelo domínio do e-mail do cliente.

**Status:** ✅ limpo — campo funcionando corretamente. Atenção ao ponto de dupla computação (Script 09 + API): se os dois divergirem, a tela pode mostrar valor diferente do que está gravado no JSON 03.

---

## Campo 6 — Responsável

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** nome da pessoa que deve agir agora na thread. Se o cliente aguarda resposta → é o analista da Finaud. Se a Finaud aguarda resposta → é o colaborador do cliente. Aparece no badge `👤` dentro do modal do card.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 **não cria** este campo. Ele coleta os campos brutos do e-mail (`remetente`, `destinatários`, `cc`, `reply_to`) que o Script 05 usará depois para identificar o responsável.

---

### Passo 2 — Script 05 (classificação)

O Script 05 lê cada e-mail e decide quem é o responsável usando a função `identificar_cliente_e_responsavel_completo` (linhas 580–679):

**Caso A — o cliente enviou o e-mail:**
O sistema procura no campo "Para:" e no "CC:" um endereço `@finaud`. O nome encontrado vira o responsável.
- Se o endereço estiver no cadastro `colaboradores_finaud` → usa o nome padronizado do cadastro
- Se não estiver cadastrado → usa o nome que vier no próprio campo "Para:" do e-mail
- Se o "Para:" não tiver nome nenhum → cai no fallback `"Suporte Finaud"`

**Caso B — a Finaud enviou o e-mail:**
O sistema procura no "Para:" a primeira pessoa externa (não-Finaud). Usa o nome dessa pessoa como responsável. Se não achar nome → usa o nome da empresa do cliente como fallback.

O campo `responsavel` é gravado no arquivo `02_classificação_dados_brutos_gmail_editado.json` para cada e-mail.

---

### Passo 3 — Script 09 (integrador)

O Script 09 monta a thread e calcula o responsável final com a função `_responsavel_pela_acao()` (adicionada em 13/07/2026), que olha a **última mensagem** da thread:

| Última mensagem enviada por | Responsável calculado |
|---|---|
| Cliente → Finaud | pessoa da Finaud no "Para:" desta mensagem |
| Finaud → Cliente | pessoa do cliente no "Para:" desta mensagem |
| Finaud → Finaud (interno) | pessoa da Finaud no "Para:" desta mensagem |
| Exceção "obrigada pelo envio" | quem enviou (Finaud) |
| Nenhum nome identificável | fallback do Script 05 |

O resultado é gravado como `responsavel` no arquivo `03_integrador_dados_site.json`.

**Nota:** o Script 09 é a **fonte de verdade** — a tela apenas lê este campo, sem recalcular.

---

### Passo 4 — Tela operacional

A tela exibe o valor `thread.responsavel` diretamente no badge `👤` do modal (elemento `mResp`, linha ~4633 de `email_operacional.html`):

```javascript
document.getElementById("mResp").textContent = decodeMimeHeader(String(thread.responsavel || "").trim()) || "—";
```

*Sem recálculo na tela — o JSON é a fonte de verdade.*

---

### Passo 5 — Caminho feliz

1. Cliente envia e-mail para `michel@finaud.com.br`
2. Script 05: remetente não é Finaud → responsável = "Michel Costa" (primeiro Finaud no "Para:")
3. Script 09: última mensagem é do cliente → responsável confirmado = "Michel Costa"
4. Michel responde → próxima carga do Script 09: última mensagem agora é Finaud→Cliente → responsável passa a ser o nome do cliente
5. Cliente responde de volta → Script 09 calcula de novo: última mensagem é do cliente → responsável volta a ser "Michel Costa"

O badge `👤` sempre reflete quem deve agir com base na **última movimentação** da thread.

---

### O que pode dar errado

| Situação | O que aparece | Por que acontece |
|---|---|---|
| E-mail enviado para `suporte@finaud` sem analista específico no "Para:" e sem resposta ainda | `"Suporte Finaud"` | Nenhum `@finaud` individual no "Para:"; nenhuma resposta para extrair nome — **comportamento esperado** |
| Nome do colaborador do cliente não está no e-mail | Nome da empresa como fallback (ex: "Acme") | `extrair_nome_pessoa` retornou vazio; sistema usa nome da empresa |

**Não há falha silenciosa clássica aqui:** o sistema sempre grava algo — nunca fica em branco. O risco é gravar um valor genérico ("Suporte Finaud") em vez do nome certo, que ocorre apenas quando não há informação disponível.

---

### O que Michel faz para corrigir

**Se mostrar "Suporte Finaud" em vez do nome do analista:**
1. Verificar se o e-mail original tinha algum `@finaud` individual no "Para:" ou CC
2. Se sim: checar se o analista está no arquivo `config/cadastro_clientes_cadoc.json` (seção `colaboradores_finaud`) e corrigir se necessário; rodar Script 05 + Script 09
3. Se não (e-mail foi enviado para `suporte@finaud` apenas): aguardar o analista responder — na próxima carga do Script 09 o nome aparecerá automaticamente

**Precisa rodar o pipeline?** Script 05 e Script 09, nesta ordem. Fazer backup do `03_integrador_dados_site.json` antes.

**Como consultar quando algo der errado:**
- JSON do e-mail individual: `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json` → campo `responsavel` de cada mensagem
- JSON da thread: `data/json/pipeline/03_integrador_dados_site.json` → campo `responsavel` da thread
- Mapeamento de colaboradores: `config/cadastro_clientes_cadoc.json` → seção `colaboradores_finaud`

---

## Campo 7 — Categoria (CADOC)

> **Status do rastreamento:** ✅ Concluído em 13/07/2026.

**O que mostra na tela:** a categoria regulatória do e-mail — qual relatório do BACEN aquela thread está relacionada. Exemplos: `DDR`, `DLO`, `DRM`, `SUPORTE`, `RETORNO BACEN`. Aparece no badge `📋` do modal (elemento `mCadoc`) e também no card da lista.

---

### Passo 1 — Coleta do e-mail (Script 02)

O Script 02 **não cria** este campo. Coleta apenas o assunto e o corpo bruto do e-mail, que o Script 05 usará para identificar a categoria.

---

### Passo 2 — Script 05 (classificação)

É aqui que o CADOC é identificado. A função `identificar_cadoc()` (linha 1326) analisa o assunto e o corpo do e-mail seguindo esta ordem de prioridade:

| Prioridade | Critério | Exemplo |
|---|---|---|
| 1 | Assunto com `S5` como palavra | → `S5` |
| 2 | Assunto com "Balancete de Câmbio" | → `DDR_2011` |
| 3 | Assunto com "Balancete" | → `DLO_2061` |
| 4 | Assunto com consulta de norma BCB | → `SUPORTE` |
| 5 | Assunto identifica exatamente 1 código numérico (ex: 2011, 2061) | → CADOC correspondente |
| 6 | Corpo do e-mail tem código numérico | → CADOC correspondente |
| 7 | Corpo do e-mail tem termo textual (ex: "DDR", "DLO") | → CADOC correspondente |
| 8 | Nenhum critério atendido | → `OUTROS` |

O resultado é gravado como `cadoc` no arquivo `02_classificação_dados_brutos_gmail_editado.json`.

---

### Passo 3 — Script 09 (integrador)

Copia o `cadoc` do e-mail para a thread. Se mensagens da mesma thread tiverem CADOCs diferentes, o Script 09 usa o CADOC mais frequente entre as mensagens.

O campo é gravado como `cadoc` no arquivo `03_integrador_dados_site.json`.

---

### Passo 4 — Tela operacional

A função `rotuloCategoriaChip()` (linha 1180 de `email_operacional.html`) converte o valor interno para o rótulo curto de exibição:

| Valor no JSON | Exibido na tela |
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

---

### Passo 5 — Caminho feliz

E-mail com assunto "DDR 2011 - Posição Janeiro" → Script 05 identifica código `2011` no assunto → grava `DDR_2011` → Script 09 copia para a thread → tela exibe badge `📋 DDR`.

---

### O que pode dar errado

| Situação | O que aparece | Por que acontece |
|---|---|---|
| Assunto genérico sem código ou termo conhecido | `OUTROS` | Nenhum critério da função `identificar_cadoc` foi atendido |
| Assunto com dois CADOCs (ex: encaminhamento DDR mencionando DLO) | CADOC errado | Sistema pega o primeiro código encontrado; prioridade do assunto sobre o corpo minimiza isso |
| Thread com mensagens de CADOCs diferentes | CADOC da maioria | Script 09 usa o mais frequente entre as mensagens |

---

### O que Michel faz para corrigir

Se o CADOC estiver errado, é possível corrigir manualmente pelo modal da tela — o badge `📋` é clicável e sobrescreve o valor automatizado.

**Precisa rodar o pipeline?** Não para correção manual via tela. Sim (Script 05 + Script 09) se quiser corrigir na origem.

**Como consultar quando algo der errado:**
- JSON do e-mail: `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json` → campo `cadoc` de cada mensagem
- JSON da thread: `data/json/pipeline/03_integrador_dados_site.json` → campo `cadoc` da thread

---

## Campo 8 — Status

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Problema identificado — ver nota abaixo.

**O que mostra na tela:** o estado atual da thread no badge `🏷` do modal. Na operação do dia a dia, os estados que importam são dois: **Aguardando** (alguém precisa agir) ou **Concluído** (assunto encerrado).

---

### Passo 1 e 2 — Scripts 02 e 05

Não contribuem para este campo.

---

### Passo 3 — Script 09 (status_processo)

Cria o campo `status_processo` com base em uma regra simples:
- Thread tem prazo → `PENDENTE`
- Thread não tem prazo → `INFORMATIVO`

⚠️ **Este campo não representa Aguardando/Concluído** — é uma classificação interna baseada em prazos regulatórios, não no estado operacional real da thread.

---

### Passo 3b — Script 11 (triagem — fonte de verdade do Status)

É quem define o estado real da operação. Classifica cada thread como AGUARDANDO ou CONCLUÍDO com base nas regras de negócio da Finaud. O resultado fica em dois arquivos:
- `data/json/pipeline/threads_aguardando_auto.json`
- `data/json/pipeline/threads_concluidas_auto.json`

---

### Passo 4 — API `/api/dados`

Cruza os dois sistemas (Script 09 + Script 11) e injeta nos eventos:
- `status = "concluido"` → thread está em `threads_concluidas_auto.json`
- `aguardando = true` → thread está em `threads_aguardando_auto.json`

---

### Passo 5 — Tela operacional

A função `rotuloStatusOperacional()` (linha 1188 de `email_operacional.html`) combina tudo com esta ordem de prioridade:

| Condição verificada | Exibido |
|---|---|
| Thread está nas concluídas (Script 11) | `Concluído` |
| Thread está nas aguardando (Script 11) | `Aguardando` |
| `status_processo = PENDENTE` (Script 09) | `Pendente` |
| `status_processo = INFORMATIVO` (Script 09) | `Informativo` |
| Nenhuma das anteriores | `Pendente` (fallback) |

---

### ⚠️ Problema identificado em 13/07/2026

O `status_processo` aparece na **aba de busca** e controla a **cor do ponto do card** (laranja = atenção). Como a regra é "tem prazo = PENDENTE", praticamente todas as threads aparecem como PENDENTE na busca — inclusive as já concluídas. Isso não reflete a realidade operacional.

**O que deveria ser:** usar apenas Aguardando/Concluído em todos os lugares da tela, eliminando Pendente/Informativo da visão do operador.

**Investigação registrada em `documentações/PENDENCIAS.md`** — sessão dedicada para avaliar impacto e implementar a correção com segurança.

---

### O que Michel faz para corrigir

O badge `🏷` é clicável — permite alterar o status manualmente na tela. Para correção na origem, rodar o Script 11.

**Precisa rodar o pipeline?** Script 11 para atualizar a triagem.

**Como consultar quando algo der errado:**
- `data/json/pipeline/threads_aguardando_auto.json` — threads em aguardando
- `data/json/pipeline/threads_concluidas_auto.json` — threads concluídas

---

## Campo 9 — Prazos

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Validado em produção (6.576 registros — zero erros de cálculo). Limitações registradas em `documentações/PENDENCIAS.md`.

**O que mostra na tela:** a data-limite para envio de cada relatório regulatório. Cada thread pode ter mais de um prazo — um por mensagem recebida — pois o sistema recalcula a cada novo e-mail. O prazo mais recente é o que aparece em destaque no card.

---

### Passo 1 — Script 02

Não contribui para este campo. Apenas coleta o e-mail bruto.

---

### Passo 2 — Script 05 (onde o prazo nasce)

É aqui que o prazo é criado. O script faz dois trabalhos:

**1. Busca a data de referência (`data_base`)** — seguindo esta ordem de prioridade:

| Prioridade | Onde busca | Quando usa |
|---|---|---|
| 1ª | Assunto do e-mail | Sempre tenta primeiro |
| 2ª | Corpo da mensagem atual | Só se o assunto não tiver data |
| 3ª | Histórico de todas as mensagens da thread | Só se nem o corpo tiver data |
| 4ª | Data de envio do e-mail | Último recurso — quando não há data em nenhum lugar |

**Assunto ganha:** se a data estiver tanto no assunto quanto no corpo, o sistema usa a do assunto e ignora o corpo. Isso é intencional — o assunto tende a ter a data certa (ex.: "DDR de 29/06/2026"), enquanto o corpo pode ter várias datas espalhadas.

**Formatos reconhecidos:**

| Formato | Exemplo |
|---|---|
| DD/MM/AAAA | 29/06/2026 |
| DD.MM.AAAA ou DD-MM-AAAA | 29.06.2026 |
| AAAA-MM-DD (ISO) | 2026-06-29 |
| AAAAMMDD (compacto) | 20260629 |
| DD de Mês de AAAA | 29 de junho de 2026 |
| DD de Mês. de AAAA (Gmail) | 29 de jun. de 2026 |
| DD Mês AAAA (sem "de") | 29 junho 2026 |
| MM/AAAA (competência mensal) | 05/2026 → usa 31/05 |
| Mês/AAAA ou Mês de AAAA | Maio/2026 → usa 31/05 |
| Mês sozinho | "DLI DEZEMBRO" → usa 31/12 |
| MM AAAA (com espaço) | "COS 12 2025" → usa 31/12 |
| Nome de arquivo com data | DRL2160_012026 → usa 31/01 |
| Intervalos de dias | "15 a 20/06/2026" → gera prazo por dia útil |
| Lista de dias | "16, 19 e 20/01/2026" → gera 3 prazos |

⚠️ **Limitação conhecida:** ano com 2 dígitos (ex.: "04/26") **não é reconhecido**. Registrado em `documentações/PENDENCIAS.md` para correção futura.

**2. Calcula o prazo-limite** aplicando a regra do CADOC:

| CADOC | Regra |
|---|---|
| DDR_2011 / 4111 | 3 dias úteis após a data_base |
| RETORNO_BACEN / SUPORTE / S5 / FORCAPITAL / DRSAC | 5 dias úteis após a data_base |
| DRL_2160 | 10 dias úteis após a data_base |
| DRM_2060 | 5 dias úteis a partir do 1º dia do mês seguinte |
| DLO_2061 / DLI_2062 | Dia 5 do segundo mês seguinte à data_base |
| 6209 | Último dia útil do mês que segue o trimestre |

Feriados bancários nacionais são considerados automaticamente — fins de semana e datas da lista de feriados são pulados no cálculo.

O resultado fica gravado no campo `lista_prazos` dentro do arquivo `02_classificação_dados_brutos_gmail_editado.json`.

---

### Passo 3 — Script 09

Copia `lista_prazos` para o integrador (`03_integrador_dados_site.json`) sem alteração. O prazo mais recente alimenta também o campo `prazo`, usado pelo Script 11 na triagem.

---

### Passo 4 — Tela operacional

A API `/api/dados` entrega `lista_prazos` para a tela. A função `rotuloDataPrazo()` formata e exibe o prazo mais recente no card da thread.

---

### ⚠️ O que pode dar errado

| Situação | O que acontece |
|---|---|
| Assunto usa formato de ano com 2 dígitos (ex.: "04/26") | O sistema não reconhece a data — thread fica sem prazo calculado |
| Data extraída errada do assunto | Prazo calculado errado desde o início — a origem precisa ser corrigida no Script 05 |
| Feriado não cadastrado no sistema | Prazo pode cair num feriado sem pular — verificar em `data/json/config/mapeamento_regras_negocio.json` seção `feriados_nacionais` |
| Thread com muitas mensagens | Acumula vários prazos em `lista_prazos` — o sistema sempre usa o mais recente |

---

### O que Michel faz para corrigir

Se um prazo aparecer errado na tela: verificar a `data_base` em `03_integrador_dados_site.json` para aquela thread. Corrigir o assunto do e-mail de origem não resolve — é necessário ajustar a lógica de extração no Script 05 e rodar o pipeline novamente.

**Precisa rodar o pipeline?** Script 05 + Script 09 para recalcular os prazos.

**Como consultar:**
- `data/json/pipeline/03_integrador_dados_site.json` → campo `lista_prazos` de cada thread

---

## Campo 10 — Responsável pela ação

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Bug identificado — ver nota abaixo.

**O que mostra na tela:** o nome de quem precisa agir agora naquela thread — aparece no card da lista como o "assignee" (ícone de pessoa). É diferente do Campo 6 (Responsável): enquanto o Campo 6 é calculado e gravado no arquivo pelo Script 09, este campo é **calculado na hora em que a tela carrega**, a partir das mensagens da thread.

---

### Passo 1 e 2 — Scripts 02 e 05

Não contribuem para este campo.

---

### Passo 3 — Script 09

Calcula e grava o campo `responsavel` no JSON 03, usando a função `_responsavel_pela_acao()` — a mesma lógica do Campo 6. É o valor de fallback caso o cálculo da tela falhe.

---

### Passo 4 — API `/api/dados` (painel em tempo real)

Na hora de servir os dados para a tela, o painel recalcula o responsável usando a função `_responsavel_pela_acao_from_mensagens()` e injeta no campo `responsavel_pela_acao`. A lógica é a mesma do Script 09:

| Última mensagem | Quem aparece como responsável |
|---|---|
| Cliente enviou para Finaud | Pessoa da Finaud que recebeu |
| Finaud enviou para Finaud (interno) | Pessoa da Finaud que recebeu |
| Finaud enviou para Cliente | Pessoa do cliente que recebeu |
| Finaud enviou "obrigada/obrigado pelo envio" | Pessoa da Finaud que enviou |

---

### Passo 5 — Tela operacional

A tela usa `responsavel_pela_acao` (calculado pelo painel) com fallback para `responsavel` (gravado pelo Script 09):

```
responsavel_pela_acao → responsavel → 'N/A'
```

---

### Caminho feliz (como funciona quando tudo está certo)

1. Cliente envia relatório DDR para a Finaud
2. Script 09 lê a última mensagem → origem CLIENTE, destino Finaud (ex.: Rodrigo) → grava `responsavel = "Rodrigo Tibério"`
3. Painel recalcula na hora → mesma mensagem, mesma lógica → `responsavel_pela_acao = "Rodrigo Tibério"`
4. Tela exibe: **Rodrigo Tibério** no card

---

### ⚠️ Bug identificado em 13/07/2026

As duas funções (Script 09 e painel) ordenam as mensagens de formas diferentes para achar a "última":
- **Script 09:** usa `timestamp_epoch` (número inteiro)
- **Painel:** usa `data_email`, `data_iso` ou `timestamp` (campos de texto)

Quando uma mensagem tem `timestamp_epoch` zero ou ausente, cada função escolhe uma mensagem diferente como "última" — e o responsável mostrado muda. **Em produção: 55 de 4.786 threads mostram na tela um responsável diferente do que está no arquivo JSON.**

**Investigação registrada em `documentações/PENDENCIAS.md`** — correção junto com a limpeza arquitetural (unificar critério de ordenação).

---

### O que Michel faz para corrigir

Se o responsável aparecer errado na tela: o valor exibido vem do cálculo em tempo real do painel, não do JSON. Não é possível corrigir só editando o arquivo. É necessário ajustar a lógica de ordenação das mensagens no código.

**Precisa rodar o pipeline?** Não — o valor é calculado na hora de carregar a tela. Após a correção do código, o valor atualiza automaticamente.

**Como consultar:**
- `data/json/pipeline/03_integrador_dados_site.json` → campo `responsavel` de cada thread (valor gravado pelo Script 09)
- O valor exibido na tela pode diferir para as 55 threads com o bug

---

## Campo 11 — Quantidade de mensagens

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Validado em produção (4.786 registros — zero erros).

**O que mostra na tela:** o número de mensagens trocadas na thread — aparece no modal e é usado internamente para detectar se chegou uma resposta nova depois que a thread foi fechada.

---

### Passo 1 — Script 02

Não calcula este campo, mas coleta as mensagens brutas que serão contadas depois.

---

### Passo 2 — Script 05

Calcula `qtd_mensagens` como a contagem das mensagens classificadas naquele momento. Grava no arquivo `02_classificação_dados_brutos_gmail_editado.json`.

---

### Passo 3 — Script 09

Recalcula `qtd_mensagens` com base nas mensagens já formatadas e grava no `03_integrador_dados_site.json`. Também usa esse número para detectar se uma thread concluída recebeu mensagem nova:

- Se `qtd_mensagens` atual > `qtd_mensagens_no_fechamento` → chegou mensagem nova após o fechamento → sistema pode sinalizar para revisão

---

### Passo 4 — Tela operacional

O painel recalcula a quantidade na hora de servir os dados, considerando o filtro de data ativo. Se o usuário está vendo a tela com filtro de um dia específico, o número mostrado pode ser menor do que o total — mostra só as mensagens dentro do período filtrado.

---

### O que pode dar errado

Não há risco de dado incorreto: o campo é uma simples contagem. O único ponto de atenção é que o número na tela pode diferir do JSON quando há filtro de data ativo — isso é comportamento esperado, não bug.

**Precisa rodar o pipeline?** Não — qualquer recarga do Script 09 recalcula automaticamente.

**Como consultar:**
- `data/json/pipeline/03_integrador_dados_site.json` → campo `qtd_mensagens` de cada thread

---

## Campo 12 — Data e horário

> **Status do rastreamento:** ✅ Concluído em 13/07/2026. Validado em produção (4.786 registros — zero erros).

**O que mostra na tela:** a data e hora da última mensagem da thread — aparece no card e no modal. É o campo que o sistema usa para ordenar as threads (mais recente no topo).

---

### Passo 1 — Script 02

Coleta a data e hora de cada e-mail a partir do cabeçalho `Date:` do Gmail. Dois campos são gravados:
- `timestamp`: data e hora formatada para exibição (ex.: `01/07/2026 18:01`)
- `data_iso`: só a data no formato padrão ISO (ex.: `2026-07-01`) — usado para filtros e ordenação

---

### Passo 2 — Script 05

Não altera os campos de data, apenas os lê para extrair a data de referência dos prazos (campo `data_base` — ver Campo 9).

---

### Passo 3 — Script 09

Copia `timestamp` e `data_iso` para o integrador sem alteração. O Script 09 também usa `data_iso` para o filtro de carga: só processa mensagens da janela de datas da carga atual.

---

### Passo 4 — Tela operacional

A tela usa `timestamp` para exibir e `data_iso` para filtrar. O filtro de data da tela (botão de período) compara `data_iso` com o intervalo selecionado pelo usuário.

---

### O que pode dar errado

| Situação | O que acontece |
|---|---|
| E-mail com data errada no cabeçalho (clock do servidor fora do horário) | `timestamp` e `data_iso` ficam errados — thread aparece fora de ordem ou no dia errado |
| E-mail muito antigo encaminhado como novo | A data que conta é a do envio do encaminhamento, não a data original |

**Precisa rodar o pipeline?** Não — o campo vem direto do e-mail; só muda se o e-mail for recoletado.

**Como consultar:**
- `data/json/pipeline/03_integrador_dados_site.json` → campos `timestamp` e `data_iso` de cada thread

---
