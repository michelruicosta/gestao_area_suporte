# Guia de Campos — Tela Operacional (`/operacional`)

> **Para que serve:** descreve campo por campo o que aparece na tela operacional —
> de onde vem cada informação, qual script a preenche e quais regras se aplicam.
>
> Leia junto com: [Linhagem de Dados](LINHAGEM_DADOS_OPERACIONAL.md)
> — mostra o caminho completo de cada campo desde o e-mail até a tela (todos os JSONs intermediários).
>
> _Atualizado: 2026-07-10_

---

## Campo 1 — Assunto

**A história:** Um e-mail chega para a Finaud com um assunto definido pelo remetente —
por exemplo `Re: SSG - ENVIAR POSIÇÃO - 4111`. Esse assunto percorre o pipeline inteiro
sem ser alterado e aparece na tela exatamente como chegou, prefixos incluídos.

**Regras:**
- O assunto nunca é alterado pelo pipeline — o que o remetente escreveu é o que aparece na tela
- Prefixos de resposta (`Re:`, `RES:`, `ENC:`, `FW:`) são mantidos

**O passo a passo técnico:**

| Etapa | Script | O que faz com o assunto | Arquivo gerado |
|---|---|---|---|
| 1 | `02_coletar_emails_gmail.py` | Captura o e-mail do Gmail e salva o assunto original | `01_extração_dados_brutos_gmail.json` → campo `assunto` |
| 2 | `05_classificar_emails_regulatorio.py` | Classifica o e-mail (regulatório? qual cliente?) — copia o assunto sem alterar | `02_classificação_dados_brutos_gmail_editado.json` → campo `assunto` |
| 3 | `09_integrar_dados_painel.py` | Monta os dados da tela — copia o assunto sem alterar | `03_integrador_dados_site.json` → campo `titulo` |
| 4 | Tela (`email_operacional.html`) | Exibe o `titulo` diretamente no card | — |

**Bugs conhecidos:** nenhum. O campo sempre é preenchido (todo e-mail tem assunto).

---

## Campo 2 — ID do caso

**A história:** Quando um e-mail chega na caixa da Finaud, o servidor do Gmail atribui automaticamente um número único para ele — como um protocolo. Esse número percorre o pipeline sem ser alterado e aparece no card como identificador do caso (ex.: `78`).

**Regras:**
- O ID é atribuído pelo servidor do Gmail no momento em que o e-mail é baixado — o sistema não cria um ID próprio
- O card exibe o ID do **e-mail mais recente** da thread
- Não é um número sequencial do pipeline — é o número que o Gmail deu para aquele e-mail na caixa de entrada

**O passo a passo técnico:**

| Etapa | Script | O que faz com o ID | Arquivo gerado |
|---|---|---|---|
| 1 | `02_coletar_emails_gmail.py` | Baixa o e-mail e registra o número que o Gmail atribuiu | `01_extração_dados_brutos_gmail.json` → campo `id` |
| 2 | `05_classificar_emails_regulatorio.py` | Classifica o e-mail — copia o `id` sem alterar | `02_classificação_dados_brutos_gmail_editado.json` → campo `id` |
| 3 | `09_integrar_dados_painel.py` | Monta os dados da tela — copia o `id` sem alterar | `03_integrador_dados_site.json` → campo `id` |
| 4 | Tela (`email_operacional.html`) | Exibe o `id` do e-mail mais recente da thread no card | — |

**Bugs conhecidos:** nenhum. O campo sempre é preenchido.

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

## Campo 4 — Cliente

> **Status do rastreamento:** ✅ Concluído em 10/07/2026.

**O que mostra na tela:** nome da pessoa que enviou o e-mail — aparece no badge "Cliente"
do modal (ex: "Ana Paola do Nascimento - Unicred do Brasil") e como linha de apoio no card
da lista.

**De onde vem:** diretamente do `remetente_real` resolvido pelo Script 05 (Campo 3 — Remetente,
Passo 2). O Script 09 copia esse valor para o campo `cliente` no JSON 03 sem alteração.

*Em linguagem simples: o sistema pega o nome da pessoa que enviou o e-mail — já com o
ajuste do Reply-To quando necessário — e exibe como "Cliente" no card. Não há lógica
adicional: é o mesmo remetente real do Campo 3, só exibido com outro rótulo na tela.*

**Arquivo e campo:** `03_integrador_dados_site.json` → campo `cliente`

**O que pode dar errado:**

- **Nome codificado** (ex: `=?UTF-8?Q?Ana_Paola?=`) → aparece com símbolos estranhos na tela

  *Em linguagem simples: e-mails com nomes acentuados às vezes chegam com uma codificação
  especial. A função `decodeMimeHeader()` na tela tenta converter — mas pode falhar em
  alguns casos.*

- **E-mail do grupo suporte sem Reply-To** (cenário B4) → cliente fica como `suporte@finaud.com.br`

  *Em linguagem simples: quando o grupo suporte reencaminha uma cópia interna para os membros
  e não há Reply-To, o sistema não consegue identificar o cliente real. Esses casos não
  aparecem na tela — são filtrados como e-mails internos. Correto.*

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

> ✅ **Campos 3, 4 e 5** rastreamento completo em 10/07/2026.
> Campo 5 (Empresa) serve de **modelo e exemplo** para o rastreamento dos demais campos.

---
