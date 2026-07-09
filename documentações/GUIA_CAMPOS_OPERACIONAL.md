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

## Campo 3 — Cliente / Empresa

**A história:** Cada e-mail tem um campo "DE:" com o nome e endereço de quem enviou. O pipeline captura esse nome bruto e guarda como `cliente`. Para exibir o **nome oficial da empresa** (ex.: `Oliveira Trust` em vez de `compliance`), o sistema consulta o cadastro oficial de empresas (`cadastro_clientes_cadoc.json`) — hoje isso acontece no momento errado (veja nota de arquitetura abaixo), mas o resultado na tela é o mesmo: se o domínio do remetente estiver no cadastro, aparece o nome oficial; se não estiver, aparece o nome bruto do "DE:".

**Regras de como o Script 05 lê o "DE:":**
1. Extrai separadamente o nome (`contato_origem.nome`) e o endereço (`contato_origem.email`)
2. Verifica o domínio: é `@finaud.com.br`? → `contato_origem.lado = FINAUD`. Caso contrário → `contato_origem.lado = CLIENTE`

**Regras de como o Script 09 define o nome bruto do cliente (`cliente`):**

| Situação | Campo usado | Fallback |
|---|---|---|
| Remetente é CLIENTE | `contato_origem.nome` | `contato_origem.email` |
| Destinatário é CLIENTE (Finaud enviou primeiro) | `contato_destino.nome` | `contato_destino.email` |
| Ambos os lados são FINAUD (e-mail interno) | `contato_destino.nome` | `contato_destino.email` |
| `DE:` vazio ou sem dado válido | `CLIENTE_DESCONHECIDO` | — |

**Como o nome oficial da empresa é resolvido (via `cadastro_clientes_cadoc.json`):**
1. Pega o e-mail do lado CLIENTE da thread
2. Procura esse e-mail exato no cadastro → se achar, usa o nome da empresa
3. Não achou por e-mail → tenta pelo domínio (ex.: `oliveiratrust.com.br` → `Oliveira Trust`)
4. Não achou por domínio → tenta encontrar o nome da empresa no assunto do e-mail
5. Não achou em nenhum dos três → `empresa` fica vazio → tela usa `cliente` (nome bruto)

**Regra de exibição na tela:** `empresa` (nome oficial do cadastro) → se vazio, usa `cliente` (nome bruto do `DE:`)

**✅ Arquitetura corrigida em 2026-07-08:** a resolução do `empresa` foi movida para o Script 09 — o JSON 03 já traz o campo preenchido e a tela apenas lê. Ver REGISTRO_CORRECOES.md entrada 2026-07-08 22:03.

**O passo a passo técnico (como deveria ser):**

| Etapa | Script | O que faz | Arquivo gerado |
|---|---|---|---|
| 1 | `02_coletar_emails_gmail.py` | Captura o `DE:` bruto | `01_extração_dados_brutos_gmail.json` → `remetente` |
| 2 | `05_classificar_emails_regulatorio.py` | Separa nome e e-mail, identifica lado FINAUD/CLIENTE | `02_classificação_dados_brutos_gmail_editado.json` → `contato_origem.nome`, `.email`, `.lado` |
| 3 | `09_integrar_dados_painel.py` | Grava nome bruto (`cliente`) e consulta cadastro para gravar nome oficial (`empresa`) | `03_integrador_dados_site.json` → campos `cliente` e `empresa` |
| 4 | Tela (`email_operacional.html`) | Exibe `empresa` (oficial) → fallback `cliente` (bruto) | — |

**Bugs conhecidos (registrados em `PENDENCIAS.md`):**

**Bug A — Empresas fora do cadastro:** quando o domínio do remetente não está em `cadastro_clientes_cadoc.json`, o sistema não consegue resolver o nome oficial e a tela exibe o nome bruto do `DE:` — que pode ser um apelido de setor (ex.: `compliance`, `Financeiro`) em vez do nome da empresa. Correção: cadastrar os domínios faltantes (solução planejada: auto-cadastro).

**Bug B — `CLIENTE_DESCONHECIDO` sem alerta:** quando o `DE:` vem vazio, a tela exibe `📩 CLIENTE_DESCONHECIDO` sem avisar ninguém. ✅ **Resolvido em 2026-07-08** — adicionado alerta `cliente_desconhecido` no sistema de notificações da tela (`/admin/alertas`): quando disparado, envia e-mail listando assunto e data de cada caso para identificação manual.

---
