# Guia de Campos — Tela Operacional (`/operacional`)

> **Para que serve:** descreve campo por campo o que aparece na tela operacional —
> de onde vem cada informação, qual script a preenche e quais regras se aplicam.
>
> Leia junto com: [Linhagem de Dados](LINHAGEM_DADOS_OPERACIONAL.md)
> — mostra o caminho completo de cada campo desde o e-mail até a tela (todos os JSONs intermediários).
>
> _Atualizado: 2026-07-08_

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

## Campo 3 — Empresa

> **Status do rastreamento:** ✅ Concluído em 09/07/2026 — todos os 5 passos rastreados.
> Este campo serve de **exemplo do método** para os demais campos.

**O que mostra na tela:** nome oficial da empresa do cliente — aparece no card da lista
e no badge "Empresa" do modal.

---

### Passo 1 — Origem: como o e-mail entra no sistema e como o nome da empresa é resolvido

**Etapa 1.1 — Coleta do e-mail (Script 02)**

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

**Etapa 1.2 — Identificação do remetente real (Script 05)**

`05_classificar_emails_regulatorio.py` lê o `remetente` do JSON 01 e determina o
`remetente_real`. Se o campo `Reply-To` estiver preenchido e não for da Finaud, o sistema
usa o `Reply-To` como remetente real — ignorando o `From:`.

*Em linguagem simples: o sistema tenta descobrir quem realmente mandou o e-mail. Mas tem
uma regra problemática: se o e-mail tiver um campo "responder para" preenchido com endereço
de fora da Finaud, o sistema assume que esse é o remetente real — mesmo que não seja.
Isso é o Bug B conhecido: o sistema confunde "quem quer receber a resposta" com
"quem mandou o e-mail".*

**O que pode dar errado:**

- **`Reply-To` de domínio diferente** → empresa identificada errada

  *Em linguagem simples: o e-mail veio da ECSA, mas o "responder para" apontava para
  outro endereço. O sistema achou que o e-mail era de outra empresa.*

  *Exemplo real: 5 threads da ECSA apareciam com `cc: Adriana Martins` como cliente porque
  o Reply-To era de outro domínio. O sistema trocou o remetente real pelo endereço de resposta.*

- **Remetente de departamento** (ex: `compliance@empresa.com`) → domínio correto mas nome
  pode não estar no cadastro

  *Em linguagem simples: a empresa usa um e-mail de setor em vez do e-mail pessoal.
  O sistema reconhece o domínio mas pode não encontrar o nome da empresa.*

  *Exemplo: Oliveira Trust envia de `compliance@oliveiratrust.com.br`. O domínio está certo,
  mas se o cadastro tiver só `contato@oliveiratrust.com.br`, o sistema não encontra e deixa
  a empresa vazia.*

- **Remetente vazio ou malformado** → empresa fica vazia, sem aviso

  *Em linguagem simples: se o e-mail chegar com o campo "de quem" em branco ou com erro,
  o sistema simplesmente não preenche a empresa — e não avisa ninguém.*

  *Exemplo: e-mail encaminhado automaticamente por sistema externo às vezes chega sem o
  campo `From:` correto — aparece como `<>` ou só o nome sem o endereço.*

**Etapa 1.3 — Resolução do nome oficial (Script 09)**

`09_integrar_dados_painel.py` pega o domínio do e-mail do lado CLIENTE e consulta o
`cadastro_clientes_cadoc.json`. Se encontra → grava o nome oficial. Se não encontra →
grava string vazia `""`.

*Em linguagem simples: o sistema pega o endereço de e-mail do cliente, olha só a parte
depois do @ (exemplo: `seferinvestimentos.com.br`) e consulta a lista de cadastro.
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

  *Exemplo: colaborador da Finaud encaminhou algo do Gmail pessoal. Campo empresa fica
  vazio — comportamento correto, não é bug.*

- **Cadastro atualizado manualmente** → não reflete na hora

  *Em linguagem simples: Michel adiciona a empresa na lista, mas a tela só vai mostrar
  depois que o Script 09 rodar de novo — não atualiza na hora.*

  *Exemplo: Michel cadastrou a Lastro no arquivo de cadastro às 10h. A tela continuou
  mostrando empresa vazia até rodar o Script 09 às 14h na próxima carga.*

**O que acontece na tela quando empresa está vazia:**
- Card mostra o nome do cliente (nome bruto do `DE:`) no lugar da empresa
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
(Etapa 1.3 do Passo 1) e grava o resultado diretamente na ficha. Se a função não encontrar,
grava string vazia — e a ficha fica com `"empresa": ""`.*

**Arquivo de saída:** `data/json/pipeline/03_integrador_dados_site.json`

*Em linguagem simples: um arquivo de texto grande que contém a ficha de todas as threads.
A tela lê esse arquivo a cada vez que alguém abre ou atualiza a tela operacional.*

**Backup automático:** antes de gravar o novo JSON 03, o Script 09 cria automaticamente
uma cópia do arquivo anterior em `03_integrador_dados_site.json.backup`.

*Em linguagem simples: antes de atualizar a ficha, o sistema guarda uma cópia da ficha
anterior — por segurança. Se algo der errado na atualização, dá para restaurar a versão
anterior.*

**O que pode dar errado:**

- **Script 09 falha no meio da execução** → JSON 03 fica corrompido ou incompleto

  *Em linguagem simples: se a luz cair enquanto o Script 09 está montando o arquivo, o
  arquivo pode ficar pela metade — e a tela pode travar ou mostrar dados errados.*

  *Exemplo: Script 09 processou 30 das 36 threads e parou por erro de memória. O JSON 03
  ficou com só 30 threads. A tela sumiu com 6 cases sem avisar Michel.*

  *O que fazer: restaurar o backup (`03_integrador_dados_site.json.backup`) e rodar o
  Script 09 de novo.*

- **`_resolver_empresa()` lança exceção** → thread inteira é pulada silenciosamente

  *Em linguagem simples: se der algum erro na hora de buscar o nome da empresa de uma
  thread específica, o Script 09 pode pular essa thread inteira e não gravá-la no arquivo.*

  *Isso é raro — mas se uma thread sumir misteriosamente após rodar o Script 09, verificar
  o log de execução.*

- **Arquivo de cadastro corrompido** → `_resolver_empresa()` carrega dicionário vazio →
  todas as threads ficam com `empresa: ""`

  *Em linguagem simples: se o arquivo de lista de empresas estiver com erro de formatação,
  o sistema não consegue abrir e deixa todas as empresas vazias — sem aviso.*

  *Exemplo: alguém editou o `cadastro_clientes_cadoc.json` manualmente e introduziu uma
  vírgula a mais. O arquivo ficou inválido. O Script 09 não abortou — simplesmente usou
  lista vazia e gravou empresa vazia para todas as 36 threads.*

**O que Michel faz para verificar se o campo foi gravado:**
- Abrir `data/json/pipeline/03_integrador_dados_site.json` e procurar por `"empresa"`
- Verificar se o valor está preenchido para as threads que deveriam ter empresa identificada

### Passo 3 — Entrega pela API

**O que acontece:** quando a tela operacional carrega, ela faz uma chamada ao endereço
`/api/dados` do Flask. O Flask lê o JSON 03 (ou usa a cópia em memória, se ainda válida),
processa cada thread e devolve os dados para o navegador — incluindo o campo `empresa`.

*Em linguagem simples: é como um garçom que vai até o arquivo central (JSON 03), pega as
fichas de todas as threads e serve ao navegador. Mas antes de servir, ele aplica alguns
retoques finais — incluindo na empresa.*

**Caminho do código:**
1. `painel_oraculo.py` → rota `/api/dados` (linha 3540)
2. Chama `painel_operacional_snapshot.montagem_api_dados_snapshot()`
3. Dentro desse processamento, para cada thread:
   - Se a thread tem `empresa` vazia no JSON 03, tenta buscar novamente pelo e-mail do lado CLIENTE
   - Depois aplica `_rotulo_empresa_gestao_para_api()` — que consulta um segundo arquivo de
     rótulos (`rotulos_empresa_gestao.json`) para padronizar nomes

*Em linguagem simples: o Sistema tem uma segunda chance de descobrir a empresa — mesmo que
o Script 09 não tenha encontrado. E antes de enviar para a tela, padroniza o nome: por
exemplo, troca `oliveiratrust.com.br` pelo nome legível `Oliveira Trust`.*

**Dupla computação — este é o ponto crítico:**
O campo `empresa` é calculado **duas vezes** — uma no Script 09 (Passo 1+2) e outra na
API (Passo 3). Isso significa que:
- Mesmo que o Script 09 grave `empresa: ""`, a API pode preencher o campo na hora
- Mas também significa que a lógica está em dois lugares diferentes — se um muda e o outro
  não, os resultados podem divergir

*Em linguagem simples: é como ter dois cozinheiros preparando o mesmo prato com receitas
ligeiramente diferentes. Na maioria das vezes o resultado parece igual, mas quando há uma
diferença entre as receitas, o prato sai diferente dependendo de quem cozinhou.*

**Cache em memória — atenção ao fluxo:**
O Flask mantém o JSON 03 em memória para não ler o arquivo do disco a cada requisição.
Quando o Script 09 atualiza o JSON 03, o cache invalida automaticamente ao detectar que
o arquivo mudou.

*Em linguagem simples: o servidor guarda uma cópia do arquivo na memória para responder
mais rápido. Quando o arquivo muda no disco, o servidor descarta a cópia e carrega a
versão nova. Isso acontece automaticamente — sem precisar reiniciar o servidor.*

**O que pode dar errado:**

- **Rótulo não cadastrado** → nome da empresa fica como domínio cru (ex: `oliveiratrust.com.br`)

  *Em linguagem simples: o sistema não encontrou o nome bonito no segundo arquivo de
  rótulos. A tela exibe o endereço do site em vez do nome da empresa.*

  *Exemplo: Oliveira Trust tinha o domínio cadastrado mas o rótulo estava escrito como
  `Oliveira Trust Dtvm` — nome diferente do que o sistema esperava. A tela mostrava
  `oliveiratrust.com.br` em vez do nome correto.*

- **Cache desatualizado durante testes** → tela mostra dados antigos mesmo após rodar Script 09

  *Em linguagem simples: você rodou o Script 09, a ficha foi atualizada no disco — mas a
  tela ainda mostra os dados antigos porque o servidor não percebeu a mudança ainda.*

  *O que fazer: aguardar alguns segundos e recarregar a tela. Se persistir, reiniciar o
  servidor Flask (`/admin/reiniciar` ou pelo terminal).*

**O que Michel faz para verificar:**
- Abrir a tela operacional e verificar se o nome da empresa aparece no card
- Se estiver vazio mas o domínio está no cadastro: possível problema de rótulo — verificar
  `data/json/config/rotulos_empresa_gestao.json`

### Passo 4 — Exibição na tela

**O que acontece:** o JavaScript da tela recebe os dados da API e monta cada card da lista
e o modal de detalhes. O campo `empresa` aparece em dois lugares distintos na tela.

*Em linguagem simples: o navegador pega os dados que o servidor enviou e os exibe na tela.
O JavaScript decide o que mostrar em cada lugar, com regras de fallback — se a empresa
não veio, usa o cliente; se o cliente não veio, mostra "DESCONHECIDO".*

**No card da lista:**

Linha no código (`email_operacional.html`, linha ~3732):
```javascript
<span>📩 ${escapeHtml(decodeMimeHeader((latest.empresa || latest.cliente) || '') || 'DESCONHECIDO')}</span>
```

*Em linguagem simples: o card sempre mostra alguma coisa no campo empresa — em ordem de
prioridade: (1) nome oficial da empresa, (2) nome do cliente (nome bruto do DE:), (3)
"DESCONHECIDO" se ambos estiverem vazios.*

**No modal de detalhes (badge "Empresa"):**

Linha no código (linha ~4617):
```javascript
var empresa = (thread.empresa || "").trim();
// Fallback: usa dados do card quando a thread da API não tem empresa
if (!empresa && currentThreadId && THREADS[currentThreadId]) {
    var ev = getThreadLatest(THREADS[currentThreadId]);
    empresa = (ev.empresa || ev.cliente || "").trim();
}
if (empresa) {
    empresaEl.textContent = empresa;
    empresaChip.style.display = "inline-flex"; // mostra o badge
} // se vazio: badge fica oculto (display: none)
```

*Em linguagem simples: o modal tenta mostrar a empresa. Se a empresa vier vazia, tenta
usar o nome do cliente do card. Se ambos estiverem vazios, o badge "Empresa" fica
completamente oculto — não aparece nem vazio, simplesmente desaparece.*

**O que pode dar errado:**

- **`empresa` e `cliente` ambos vazios** → card mostra "📩 DESCONHECIDO"; modal oculta badge

  *Em linguagem simples: nenhuma informação de quem é — nem empresa nem cliente. O card
  mostra um ícone de e-mail com a palavra "DESCONHECIDO". No modal o campo empresa
  simplesmente some — não aparece em branco, desaparece mesmo.*

  *Quando acontece: e-mail chega sem campo "DE:" válido e o domínio não está no cadastro.*

- **`empresa` vazia mas `cliente` preenchido** → card mostra o nome bruto do DE:

  *Em linguagem simples: o sistema não encontrou o nome oficial da empresa, então mostra
  o que o remetente colocou no campo "De:" — que pode ser só o primeiro nome da pessoa
  (ex: "Adriana") ou o nome de um setor (ex: "compliance@oliveiratrust.com.br").*

  *Isso é o comportamento de fallback — não é erro, mas indica que a empresa não foi
  identificada.*

- **Encoding no nome** → caracteres especiais aparecem errados no card

  *Em linguagem simples: nomes com acentos ou caracteres especiais podem aparecer com
  símbolos estranhos se o encoding não for tratado corretamente. A função
  `decodeMimeHeader()` tenta corrigir isso — mas nem sempre funciona para todos os casos.*

**Resumo de fallback — ordem de exibição:**

| Situação | Card mostra | Modal badge |
|---|---|---|
| `empresa` preenchida | nome oficial | nome oficial |
| `empresa` vazia, `cliente` preenchido | nome bruto do DE: | nome bruto do DE: |
| ambos vazios | 📩 DESCONHECIDO | badge oculto |

### Passo 5 — Caminho feliz completo resumido

*O que acontece quando tudo funciona corretamente:*

| Etapa | Quem faz | O que acontece | Resultado |
|---|---|---|---|
| 1 | Script 02 | Acessa o Gmail e baixa o e-mail da Lastro Capital com `From: compliance@lastrocapital.com.br` | `01_extração...json` → `remetente: compliance@lastrocapital.com.br` |
| 2 | Script 05 | Não há `Reply-To` → `remetente_real = remetente` → identifica lado CLIENTE pelo domínio | `02_classificação...json` → `contato_origem.email: compliance@lastrocapital.com.br` |
| 3 | Script 09 | Extrai domínio `lastrocapital.com.br` → encontra no cadastro → `empresa = "Lastro Capital"` | `03_integrador...json` → `"empresa": "Lastro Capital"` |
| 4 | API `/api/dados` | Lê JSON 03 → passa `empresa` por `_rotulo_empresa_gestao_para_api()` → confirma nome padronizado | Payload JSON → `"empresa": "Lastro Capital"` |
| 5 | JavaScript | Recebe `empresa: "Lastro Capital"` → monta card e modal | Card mostra 📩 Lastro Capital; modal mostra badge "Empresa: Lastro Capital" |

**Condições para o caminho feliz:**
- E-mail tem campo `From:` válido com endereço de e-mail completo
- Não tem `Reply-To` (ou tem, mas é do mesmo domínio)
- Domínio do remetente está em `cadastro_clientes_cadoc.json`
- Script 09 rodou após o último e-mail chegar
- Servidor Flask está em execução

**Quando o caminho feliz quebra → ver Passos 1–4 para diagnóstico por etapa.**

---

> ✅ **Campo 3 — Empresa** rastreamento completo em 09/07/2026.
> Este campo serve de **modelo e exemplo** para o rastreamento dos demais campos (4–11).

---
