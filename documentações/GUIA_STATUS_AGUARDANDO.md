# Guia: Status "Aguardando Resposta"

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

**Versão:** 1.0 — 2026-02-27  
**Para:** Analistas da equipe Finaud

---

## O que é este recurso?

O status **"Aguardando"** permite sinalizar, para qualquer thread de e-mail aberta, que você está esperando alguma coisa — uma entrega de arquivo do cliente, uma resposta, uma ação interna — antes de poder continuar ou resolver o caso.

O sistema monitora automaticamente quanto tempo cada thread fica aguardando e te avisa quando o prazo foi ultrapassado.

---

## Por que usar?

Antes deste recurso, quando você arquivava um e-mail pendente a única forma de lembrar era manualmente. Agora:

- O sistema **lembra por você** e exibe um contador de dias
- A IA **aprende** quais casos ficaram aguardando, por quanto tempo e por quê
- Vencimentos aparecem em **vermelho** na tela e no painel inicial
- Fica registrado no histórico para análise futura (KPIs de tempo de resolução)

---

## Como usar — passo a passo

### 1. Abrir um e-mail

Na tela **Operacional**, clique em qualquer thread aberta para abrir o modal de detalhes.

---

### 2. Clicar em "⏳ Aguardando"

No topo do modal, ao lado dos botões "Ciente — Arquivar" e "Marcar como Resolvido", existe o botão:

> **⏳ Aguardando**

Clique nele. Um painel de formulário vai abrir logo abaixo.

---

### 3. Preencher o formulário

O formulário já vem **preenchido automaticamente** com base no CADOC e no cliente do e-mail. Você só precisa confirmar ou ajustar:

| Campo | O que é | Exemplo |
|-------|---------|---------|
| **Tipo de espera** | Que tipo de ação você está esperando | "Entrega do cliente" |
| **Prazo esperado** | Até quando você espera | 2026-02-28 |
| **Motivo** | Frase curta explicando o que está aguardando | "Aguardando extrato para geração do DDR — Conecta Câmbio" |

**Dica:** o motivo já vem sugerido. Se quiser que a IA leia o e-mail e refine a sugestão, clique em **✨ Sugerir** (chama o GPT apenas neste momento).

---

### 4. Confirmar

Clique em **"⏳ Confirmar Aguardo"**.

O que acontece:
- A thread recebe o badge amarelo/vermelho na lista
- A seção **"Aguardando Resposta / Entrega"** aparece no topo da tela operacional
- O evento fica registrado no diário da IA

---

### 5. Quando a resposta/entrega chegar

Abra o modal da thread novamente e clique em **"⏳ Aguardando"** para reabrir o painel.

Clique em **"✅ Marcar como Recebido"** para encerrar o aguardo.

O sistema registra automaticamente quantos dias a thread ficou aguardando — esse dado alimenta os KPIs de tempo de resolução.

---

## Onde ver as threads aguardando

### Tela Operacional

Uma seção fixa aparece no topo da lista:

```
⏳ Aguardando Resposta / Entrega       [2 vencidos]
─────────────────────────────────────────────
Extrato DDR — Conecta Câmbio          DDR_2011   3d ⚠️
Balanço COS — Sefer Investimento      DLO_2061   1d
```

- **Verde** = dentro do prazo
- **Amarelo** = 3+ dias aguardando
- **Vermelho** = prazo vencido ⚠️

Clique em qualquer linha para abrir o modal da thread.

Você também pode clicar no card KPI **"⏳ Aguardando"** (ao lado dos outros KPIs do topo) para filtrar a lista principal e ver só essas threads.

### Painel Inicial (Home)

O card **"Aguardando Resposta"** no painel inicial mostra:
- Quantas threads estão aguardando no total
- Quantas estão com o prazo vencido (badge vermelho)

Clique no card para ir direto à tela operacional.

---

## Preenchimento automático por CADOC

Quando você abre o painel de aguardo, o sistema já infere o motivo com base no CADOC da thread:

| CADOC | Motivo pré-preenchido | Tipo | Prazo sugerido |
|-------|-----------------------|------|----------------|
| DDR_2011 | Aguardando extrato/arquivo para geração do DDR | Entrega cliente | D+2 dias |
| 4111 | Aguardando extrato para geração do 4111 | Entrega cliente | D+2 dias |
| DLO_2061 | Aguardando balancete/arquivo COS para geração do DLO | Entrega cliente | D+3 dias |
| DLI_2062 | Aguardando arquivo para geração do DLI | Entrega cliente | D+3 dias |
| DRL_2160 | Aguardando planilha DRL do cliente | Entrega cliente | D+5 dias |
| DRM_2060 | Aguardando arquivos DRM do cliente | Entrega cliente | D+5 dias |
| Sem CADOC | Aguardando resposta do cliente | Resposta cliente | D+3 dias |
| TVM / Dep a Vista (DDR_2011) | Resposta enviada em outro email | **Resposta em outro email** | D+5 dias |

Se o CADOC for gerado pela **Finaud** (campo `quem_gera = FINAUD`), o motivo muda para "Gerar e enviar relatório — [empresa]" e o tipo fica "Ação interna".

---

## O que a IA aprende com isso?

Cada marcação e resolução de aguardo fica registrada no arquivo `data/json/diario_agente.json` com:

- Data da marcação
- Empresa, CADOC, motivo
- Prazo definido
- Data da resolução
- Quantos dias ficou aguardando

Com o tempo, a IA conseguirá identificar padrões como:
- "A Conecta Câmbio costuma demorar 2 dias para enviar o extrato"
- "Threads de DLO_2061 ficam em média 4 dias aguardando"
- "Clientes X e Y nunca enviam antes do prazo"

---

## O que fazer agora (primeiros passos)

1. **Entre na tela Operacional** (menu lateral → Operacional)
2. **Escolha uma thread** que você está aguardando algo (ex.: extrato, arquivo, resposta de cliente)
3. **Clique em "⏳ Aguardando"** no modal
4. **Revise o motivo** e clique em "Confirmar"
5. Repita para todas as threads pendentes do dia

Com algumas threads marcadas, a seção de aguardo no topo da tela vai mostrar o painel de monitoramento em tempo real.

---

---

## Tipo "Resposta em outro email" (standby)

Para casos como **TVM e Depósito a Vista**, a resposta da Finaud costuma vir em um **email consolidado separado** (não na mesma thread). Use o tipo **"Resposta em outro email"** para colocar a thread em **standby**:

- A thread sai da lista de pendentes e vai para Aguardando
- **Não** é removida automaticamente quando há nova mensagem na thread (a resposta vem em outro email)
- Confirme manualmente **"Marcar como Recebido"** após verificar no Gmail que a resposta foi enviada
- Use o script `scripts/buscar_solicitacao_resposta_gmail.py` para verificar se houve resposta

**Preparação para IA:** No futuro, a IA poderá detectar padrões (ex.: assunto "TVM e Dep a Vista") e sugerir este tipo automaticamente, além de integrar a verificação de resposta em outro email ao pipeline.

---

## Dúvidas frequentes

**Posso marcar como aguardando e depois ainda arquivar a thread?**  
Sim. Os dois estados são independentes. "Aguardando" é um monitoramento; "Arquivar" é uma decisão de fluxo.

**E se eu resolver antes do prazo?**  
Abra o modal, clique em "⏳ Aguardando" e depois em "✅ Marcar como Recebido". O sistema registra a resolução antecipada.

**Posso atualizar o motivo depois de confirmar?**  
Sim. Abra o modal novamente, o formulário reabre com os dados anteriores. Edite e clique em "⏳ Atualizar Aguardo".

**O que acontece quando uma nova mensagem chega na thread?**  
O pipeline `executar_tudo.py` inclui a etapa **9b — Resolver Aguardando (auto)**. Após o Integrador atualizar os dados, o script compara as threads em Aguardando com a base: se a última mensagem for posterior à data de marcação e do lado esperado (cliente enviou, Finaud enviou ou cliente respondeu), a thread é removida automaticamente e registrada no diário. Não é necessário abrir cada uma.
