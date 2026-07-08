# Documentação Completa do Sistema de Triagem — Oráculo 360 Finaud

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

> **Para quem é este documento:** qualquer pessoa (técnica ou não) que precise entender como o
> sistema decide se um e-mail está **AGUARDANDO** ação ou **CONCLUÍDO**.
> Linguagem simples, exemplos reais.

---

## Índice

1. [O que é a Triagem?](#1-o-que-é-a-triagem)
2. [Dados necessários para a triagem](#2-dados-necessários-para-a-triagem)
3. [Scripts e JSONs que alimentam a triagem](#3-scripts-e-jsons-que-alimentam-a-triagem)
4. [Scripts e JSONs que agrupam e executam a triagem](#4-scripts-e-jsons-que-agrupam-e-executam-a-triagem)
5. [Filtros — o que entra e o que fica de fora](#5-filtros--o-que-entra-e-o-que-fica-de-fora)
6. [Todas as regras de triagem](#6-todas-as-regras-de-triagem)
7. [Exemplos reais por regra](#7-exemplos-reais-por-regra)
8. [Fluxo completo — do dado bruto ao status final](#8-fluxo-completo--do-dado-bruto-ao-status-final)
9. [O que acontece depois? O arquivo muda?](#9-o-que-acontece-depois-o-arquivo-muda)
10. [Glossário rápido](#10-glossário-rápido)

---

## 1. O que é a Triagem?

A triagem é o processo automático que **classifica cada conversa** (chamada de "thread") em
uma de duas situações:

| Status | O que significa |
|--------|----------------|
| **AGUARDANDO** | Tem ação pendente de qualquer lado — seja a Finaud que precisa agir, seja o cliente que precisa enviar algo ou responder |
| **CONCLUÍDO** | O assunto foi encerrado — seja porque a Finaud entregou/transmitiu o documento, seja porque o cliente confirmou o recebimento |

O sistema roda automaticamente toda vez que o pipeline é executado (scripts 02 → 05 → 09 → 11).
O script **11** é o responsável pela triagem.

### Tipos de conversa que entram na triagem

Não são apenas e-mails. O sistema tria quatro origens:

| Origem | Exemplos | Como entra | Resultado |
|--------|----------|------------|-----------|
| **E-mail (Gmail)** | DDR, DLO, RETORNO_BACEN, SUPORTE, etc. | Script 02 coleta; script 05 classifica o CADOC | AGUARDANDO ou CONCLUÍDO |
| **Casos do FogBugz** | Chamados de suporte técnico | Script 08 coleta; recebe cadoc `FOGBUGZ` | AGUARDANDO ou CONCLUÍDO |
| **Alertas Risk Driver** | Alertas e respostas automáticas de risco | Gerados internamente; cadoc `RISK_DRIVER_ALERTA`, `RISK_DRIVER_RESP_AUTO` | AGUARDANDO ou CONCLUÍDO |
| **Relatórios internos Risk Driver** | Relatórios periódicos automáticos | Campo `relatorio_interno_risk_driver = true` | **Não são triados** — invisíveis ao motor |

> **Importante:** FogBugz e Risk Driver (alertas/respostas) **são triados normalmente**. Só os
> *relatórios internos* do Risk Driver ficam fora — porque são gerados automaticamente e não
> representam uma conversa com ação pendente.

### O que fica fora da triagem (threads excluídas)

Alguns tipos são **ignorados pelo motor** e não recebem status nenhum:

| Situação | Como é tratado hoje |
|----------|---------------------|
| **Spam** | Classificado com cadoc `IGNORADO` pelo script 05 — motor pula automaticamente |
| **E-mail fora do período de coleta** | Recebe cadoc `FILTRADO_POR_DATA` — motor pula |
| **Relatório interno Risk Driver** | Campo `relatorio_interno_risk_driver = true` — motor pula |
| **Thread excluída por ID** | Há IDs específicos bloqueados por decisão de negócio |

> 💡 **Ideia identificada durante validação:** formalizar uma lista de domínios/remetentes de
> spam já conhecidos para que o script 05 os classifique automaticamente como `IGNORADO` sem
> necessidade de revisão manual. **Impacto no desempenho: nenhum** — excluir cedo torna o
> script 11 mais rápido, não mais lento. O custo seria apenas no script 05, que precisaria
> checar a lista; para uma lista pequena, o impacto é desprezível.
>
> ⚠️ **Pendência de decisão:** definir quais domínios entram nessa lista e como ela é mantida
> (arquivo de configuração? campo no JSON?). Registrar em `documentações/PENDENCIAS.md` quando
> for implementar.

### ⚠️ Alteração identificada nesta seção (validação 2026-06-16)

| O que estava | O que deve ser | Por quê |
|--------------|----------------|---------|
| "Classifica conversas de e-mail" | "Classifica conversas (e-mail, FogBugz, Risk Driver)" | O sistema tria três origens, não só e-mail |
| AGUARDANDO = "alguém precisa agir" | AGUARDANDO = "ação pendente de qualquer lado (Finaud ou cliente)" | A definição original estava correta, mas imprecisa — o tipo exato (quem age) é o campo `tipo` (ACAO_INTERNA / ENTREGA_CLIENTE / RESPOSTA_CLIENTE) |
| Nada sobre exclusão de spam | Seção explicando as categorias de exclusão existentes | A exclusão já existe mas não estava documentada |

---

## 2. Dados necessários para a triagem

Para classificar uma thread, o motor precisa de **cinco tipos de informação**. Todos vêm do
arquivo `03_integrador_dados_site.json`, que é gerado pelo script 09.

---

### 2.1 A direção das mensagens (quem enviou para quem)

O motor analisa a **direção das mensagens** da conversa para decidir qual conjunto de regras aplicar.

**Atenção:** o motor **não olha apenas a última mensagem**. Ele usa três camadas:

| Camada | O que analisa | Para quê |
|--------|--------------|----------|
| **Fio inteiro** | Todas as mensagens da thread | Detectar "transmitido no BACEN" em qualquer parte (regra §3.1) |
| **Última mensagem** | A mais recente | Principal critério de roteamento para as regras |
| **Penúltima mensagem** | A anterior à última | Quando a última não é clara — ex.: cliente agradeceu, mas o que a Finaud enviou antes? |

**Quando a última mensagem não é clara:** o motor olha o par penúltima+última para entender o
contexto. Exemplo: última é C→F com "Certo, obrigado" — a penúltima decide se Finaud tinha
enviado uma remessa (→ CONCLUÍDO) ou só uma pergunta (→ ainda AGUARDANDO).

**As quatro direções possíveis:**

| Direção | Código | O que significa |
|---------|--------|-----------------|
| Finaud → Cliente | **F→C** | Finaud enviou a última mensagem para o cliente |
| Cliente → Finaud | **C→F** | O cliente enviou a última mensagem para a Finaud |
| Finaud → Finaud | **F→F** | Encaminhamento interno entre pessoas da Finaud |
| Cliente → Cliente | **C→C** | Cliente encaminhou internamente (ex.: repassou e-mail para colega) |

> ⚠️ **Gap identificado (validação 2026-06-16):** o motor reconhece F→C, C→F e F→F
> explicitamente. Para **C→C** não existe bucket específico — o sistema trata como C→F ou
> ignora os detectores de direção. Na prática isso significa que threads onde o cliente
> encaminhou internamente podem ser mal classificadas. **Não há impacto nos dados atuais**
> (é raro), mas é um caso a mapear antes de criar regras novas.

**De onde vem:** campos `contato_origem.lado` e `contato_destino.lado` de cada mensagem
dentro da thread no JSON 03. Os únicos valores possíveis são `"FINAUD"` e `"CLIENTE"`.

---

### 2.2 O texto da mensagem (corpo e imagens)

O motor lê o **texto das mensagens** para detectar palavras e frases que indicam conclusão
ou pendência. Quanto mais legível o texto, mais precisa é a triagem.

**Campo principal:** `corpo` — o HTML do e-mail, limpo de assinaturas e citações repetidas.

**Campo auxiliar:** `texto_imagens` — texto extraído de imagens e anexos via OCR (script 12).
Importante quando o cliente envia prints ou PDFs com informações do BACEN.

> ⚠️ **Atenção:** se o texto estiver ilegível (imagem sem OCR, PDF não processado), o motor
> pode não detectar a conclusão e deixar a thread como AGUARDANDO indevidamente.

**Exemplos de palavras que o motor procura:**

| O que detecta | Exemplos de frases | Resultado |
|--------------|-------------------|-----------|
| Transmissão ao BACEN | "transmitido no BACEN", "arquivos transmitidos" | CONCLUÍDO |
| Remessa enviada | "segue em anexo", "envio ao BC", "segue o DDR" | CONCLUÍDO |
| Agradecimento do cliente | "obrigado!", "deu certo!", "muito obrigado" | CONCLUÍDO |
| Confirmação do BACEN | "foi aceito pelo BACEN", "STA aceitou" | CONCLUÍDO |
| Pedido de dados | "pode me enviar", "preciso dos seguintes", "aguardo os extratos" | AGUARDANDO |
| Análise conclusiva | "verificamos e está correto", "índice de basileia de X%" | CONCLUÍDO |

---

### 2.3 O CADOC (código regulatório) — essencial para decidir o status

O CADOC é **obrigatório** para a triagem: ele determina qual conjunto de regras o motor vai usar.
Um DDR_2011 tem regras diferentes de um DLO_2061.

**Campo:** `cadoc` no evento do JSON 03.

| CADOC | O que é | Triado? |
|-------|---------|---------|
| **DDR_2011** | Demonstrativo de Risco de Derivativos | ✅ |
| **4111** | Relatório 4111 (patrimônio de referência) | ✅ |
| **DRL_2160** | Demonstrativo de Risco de Liquidez | ✅ |
| **DLI_2062** | Demonstrativo de Limite de Informação | ✅ |
| **DLO_2061** | Demonstrativo de Limite Operacional | ✅ |
| **DRM_2060** | Demonstrativo de Risco de Mercado | ✅ |
| **S5** | Demonstrativo S5 | ✅ |
| **RETORNO_BACEN** | Resposta/retorno ao BACEN | ✅ |
| **SUPORTE** | Suporte técnico ao cliente | ✅ |
| **DRSAC** | Relatório DRSAC | ✅ |
| **FORCAPITAL** | Relatório For-Capital | ✅ |
| **6209** | Relatório CADOC 6209 | ✅ |
| **FOGBUGZ** | Casos do sistema FogBugz | ✅ |
| **RISK_DRIVER_ALERTA** | Alertas automáticos do Risk Driver | ✅ |
| **RISK_DRIVER_RESP_AUTO** | Respostas automáticas do Risk Driver | ✅ |
| **RISK_DRIVER_RELATORIO** | Relatórios periódicos do Risk Driver | ✅ |
| **LEIAUTES_BACEN** | Comunicados sobre leiautes do BACEN | ✅ |
| **IGNORADO** | Spam ou thread irrelevante | ❌ Motor pula |
| **FILTRADO_POR_DATA** | E-mail fora do período de coleta | ❌ Motor pula |

---

### 2.4 Os prazos (lista_prazos) — auxiliar, não decide o status sozinho

Os prazos são usados **apenas para identificar threads duplicadas** (espelho). Se a thread A
da empresa X com o prazo Y foi concluída, a thread B da mesma empresa com o mesmo prazo é
fechada automaticamente também.

**Campo:** `lista_prazos` — array com:
- `data_base`: data de referência (ex.: "03/06/2026")
- `prazo_limite`: prazo do BACEN (ex.: "10/06/2026")
- `cadoc`: a qual CADOC o prazo se refere

> **Papel real:** o prazo não decide sozinho se uma thread é AGUARDANDO ou CONCLUÍDO.
> Ele só entra em cena quando há um grupo de threads similares e o motor precisa fechar as
> duplicatas (regra §6).

---

### 2.5 Empresa e assunto — auxiliares, somente para detectar duplicatas

O motor usa empresa e núcleo do assunto **apenas para o mecanismo de espelho** (identificar
threads duplicadas). Se não houvesse espelho, esses dados não participariam da decisão.

**Campos:**
- `cliente` — empresa normalizada (ex.: "Acredito SCD", "Trustee")
- `titulo` — assunto do e-mail (usado para extrair o "núcleo": ex.: "DDR 29/05" → "ddr 29/05")

> **Papel real:** se a empresa X tem três threads sobre o mesmo DDR do mesmo período e uma
> delas foi concluída (§5 — remessa enviada), as outras duas são fechadas como "espelhos"
> pela regra §6b. Fora isso, empresa e assunto não influenciam o status.

---

### ⚠️ Alterações identificadas nesta seção (validação 2026-06-16)

| O que estava | O que deve ser | Por quê |
|--------------|----------------|---------|
| "Motor olha só a última mensagem" | Motor usa três camadas: fio inteiro, última e penúltima | Confirmado no código — §3.1 varre o fio todo; §3.5 e par_conclusivo usam penúltima |
| Três direções (F→C, C→F, F→F) | Quatro direções — C→C existe mas não tem bucket | C→C acontece quando cliente encaminha internamente; motor não tem regra explícita para isso |
| CADOC, PRAZO e EMPRESA no mesmo nível de importância | CADOC é essencial; PRAZO e EMPRESA são auxiliares (só para espelho) | Confirmado no código — motor usa CADOC para rotear regras; prazo/empresa só entram em §6/§6b |

---

### 2.6 Dados de triagens anteriores

O motor também lê os arquivos de triagem já existentes para **não desfazer o que já foi feito**:

| Arquivo | O que tem |
|---------|-----------|
| `threads_aguardando_auto.json` | Todas as threads atualmente em AGUARDANDO (geradas automaticamente) |
| `threads_concluidas_auto.json` | Todas as threads atualmente CONCLUÍDAS (geradas automaticamente) |
| `threads_aguardando_manual.json` | Threads marcadas manualmente como AGUARDANDO (preservadas sempre) |
| `threads_concluidas_manual.json` | Threads marcadas manualmente como CONCLUÍDAS (preservadas sempre) |

---

## 3. Scripts e JSONs que alimentam a triagem

Aqui está cada etapa do pipeline que **produz dados** que a triagem vai usar:

### Script 02 — Coleta de e-mails do Gmail
**Arquivo:** `scripts/02_coletar_emails_gmail.py`
**JSON de saída:** `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json`

O que produz para a triagem:
- `threadId`: identificador único da conversa no Gmail
- `assunto`: título do e-mail
- Corpo dos e-mails (HTML bruto)
- Remetente e destinatário de cada mensagem

---

### Script 05 — Classificação regulatória
**Arquivo:** `scripts/05_classificar_emails_regulatorio.py`
**JSON de saída:** enriquece o arquivo 02 com classificações

O que produz para a triagem:
- `cadoc`: qual CADOC a thread trata (DDR_2011, DLO_2061, etc.)
- `lista_prazos`: prazos regulatórios da obrigação
- `relatorio_interno_risk_driver`: se é relatório interno (torna a thread invisível para o motor)
- `secao_operacional`: seção do painel onde aparece

> ⚠️ Script lento (pode levar horas). Para correções pontuais, editar JSON 02 diretamente e
> rodar só 09 + 11.

---

### Script 09 — Integrador de dados
**Arquivo:** `scripts/09_integrar_dados_painel.py`
**JSON de saída:** `data/json/pipeline/03_integrador_dados_site.json`

É o script mais importante antes da triagem. Ele **consolida tudo** em um único arquivo que o
motor vai ler. Para cada mensagem, produz um "evento" com estes campos:

| Campo | Tipo | O que é |
|-------|------|---------|
| `id` | string | ID único do evento |
| `threadId` | string | ID da thread no Gmail |
| `titulo` | string | Assunto do e-mail |
| `cliente` | string | Nome da empresa (normalizado) |
| `responsavel` | string | Pessoa do lado pendente (cliente ou Finaud) |
| `responsabilidade` | string | "FINAUD" ou "CLIENTE" |
| `lado_responsavel` | string | "FINAUD" ou "CLIENTE" |
| `cadoc` | string | Código regulatório (DDR_2011, DLO_2061, etc.) |
| `secao_operacional` | string | Seção do painel |
| `lista_prazos` | array | Prazos regulatórios [{data_base, prazo_limite, cadoc}] |
| `retorno_bacen` | bool | É retorno do BACEN? |
| `relatorio_interno_risk_driver` | bool | É relatório interno? (invisível ao motor) |
| `data_iso` | string | Data no formato "YYYY-MM-DD" |
| `timestamp` | string | Data e hora formatadas ("16/06/2026 18:01") |
| `timestamp_epoch` | int | Timestamp Unix (para ordenação) |
| `status_processo` | string | Estado inicial "PENDENTE" |
| `contato_origem` | dict | Quem enviou {lado, nome, email} |
| `contato_destino` | dict | Quem recebeu {lado, nome, email} |
| `corpo` | string | Texto HTML do e-mail (limpo) |
| `texto_imagens` | string | Texto extraído de imagens/anexos (OCR) |
| `link` | string | Link para o e-mail no Gmail |

O JSON 03 também tem uma seção `threads` que agrupa todos os eventos de uma mesma conversa
em estrutura de array.

---

### Script 12 — OCR de imagens
**Arquivo:** `scripts/12_enriquecer_texto_imagens.py`
**Efeito:** preenche o campo `texto_imagens` nos eventos do JSON 03

O motor pode usar o texto das imagens para detectar termos como "transmitido" ou "aceito pelo
BACEN" que aparecem em prints de tela ou PDFs.

---

## 4. Scripts e JSONs que agrupam e executam a triagem

### Script 11 — Motor de triagem (orquestrador)
**Arquivo:** `scripts/11_triar_threads_por_cadoc.py`

É o script que **dispara toda a triagem**. Ele:
1. Lê o JSON 03 (entrada)
2. Para cada categoria de CADOC, chama o módulo correspondente
3. Grava os resultados nos JSONs de saída

**Categorias executadas (em ordem):**
1. DDR4111 (DDR_2011, 4111, DRL_2160)
2. DLI (DLI_2062)
3. DLO (DLO_2061)
4. S5
5. SUPORTE
6. DRSAC
7. FORCAPITAL
8. DRM (DRM_2060)
9. RETORNO_BACEN
10. CADOC 6209
11. RISK_DRIVER_ALERTA, RISK_DRIVER_RELATORIO, RISK_DRIVER_RESP_AUTO
12. FOGBUGZ
13. LEIAUTES_BACEN

**JSONs de saída:**
- `data/json/pipeline/threads_aguardando_auto.json` — threads em AGUARDANDO
- `data/json/pipeline/threads_concluidas_auto.json` — threads CONCLUÍDAS

---

### Módulos da pasta `scripts/triagem/`

| Arquivo | O que faz |
|---------|----------|
| `_protocolo.py` | Define os tipos: Regra, Contexto, Bucket, FilaAguardando |
| `constantes.py` | Lista de CADOCs por categoria |
| `helpers.py` | Todos os detectores (funções que analisam o texto) |
| `motor.py` | Motor principal: lê candidatos, aplica regras, salva resultados |
| `ddr4111.py` | Regras específicas do DDR/4111 |
| `dli.py` | Regras do DLI |
| `dlo.py` | Regras do DLO |
| `drm.py` | Regras do DRM |
| `s5.py` | Regras do S5 |
| `suporte.py` | Regras do SUPORTE |
| `drsac.py` | Regras do DRSAC |
| `forcapital.py` | Regras do FORCAPITAL |
| `retorno_bacen.py` | Regras do RETORNO_BACEN |
| `cadoc6209.py` | Regras do 6209 |

---

### Estrutura do JSON de saída — AGUARDANDO

**Arquivo:** `data/json/pipeline/threads_aguardando_auto.json`

```json
{
  "threadId": "GMTHRID_1865185339841675367",
  "assunto": "RWACPAD ACCREDITO - edição nas contas 520.01.020",
  "empresa": "Acredito SCD",
  "cadoc": "DDR_2011",
  "quem_gera": "",
  "responsavel": "Andrea Inacio",
  "motivo": "Triagem automática: última mensagem interna Finaud→Finaud — aguarda tratamento.",
  "tipo": "ACAO_INTERNA",
  "data_marcacao": "2026-06-05",
  "prazo": "",
  "status": "AGUARDANDO",
  "qtd_mensagens_no_fechamento": 2,
  "origem_triagem_auto": true,
  "alvo_triagem_auto": "DDR4111"
}
```

| Campo | O que é |
|-------|---------|
| `threadId` | ID único da thread |
| `assunto` | Título do e-mail |
| `empresa` | Nome do cliente |
| `cadoc` | Código regulatório |
| `responsavel` | Pessoa do lado pendente: se pendente com Finaud → nome da pessoa da Finaud; se pendente com Cliente → nome do contato do cliente |
| `motivo` | Descrição em linguagem natural do porquê está AGUARDANDO |
| `tipo` | Um de três valores (ver abaixo) |
| `data_marcacao` | Data em que entrou em AGUARDANDO |
| `prazo` | Prazo regulatório (se houver) |
| `status` | Sempre "AGUARDANDO" neste arquivo |
| `qtd_mensagens_no_fechamento` | Quantas mensagens havia quando foi classificado |
| `origem_triagem_auto` | `true` = gerado automaticamente; `false` = marcação manual |
| `alvo_triagem_auto` | Qual categoria triou (DDR4111, DLO, etc.) |

**Valores do campo `tipo`:**

| Valor | Quando é usado |
|-------|----------------|
| **ACAO_INTERNA** | Finaud precisa agir internamente (ex.: recebeu insumo do cliente, ou última mensagem foi F→F) |
| **ENTREGA_CLIENTE** | Finaud pediu algo ao cliente e aguarda o cliente enviar |
| **RESPOSTA_CLIENTE** | Cliente fez uma pergunta e aguarda resposta da Finaud |

---

### Estrutura do JSON de saída — CONCLUÍDO

**Arquivo:** `data/json/pipeline/threads_concluidas_auto.json`

```json
{
  "threadId": "GMTHRID_1866436622083994705",
  "tipo": "RESOLVIDA",
  "origem_triagem_auto": true,
  "alvo_triagem_auto": "DDR4111",
  "qtd_mensagens_no_fechamento": 7,
  "data_conclusao": "2026-06-03 18:00:00",
  "motivo_triagem_auto": "Michele Quadros — transmitido ao BACEN em 29/05/2026",
  "motivo_triagem_auto_tecnico": "GMTHRID_... → Concluído (§3.1 transmitido no BACEN)",
  "empresa": "Nixfin",
  "cadoc": "DDR_2011",
  "assunto": "Documentos para implantação do sistema de riscos (Risk Driver)",
  "aprendizado_ia": {
    "resumo_desfecho": "...",
    "cadoc_real": "DDR_2011",
    "cliente_identificado": "Nixfin",
    "tipo_demanda": "DDR_2011",
    "prazo_cumprido": "não se aplica",
    "resolucao_final": "..."
  }
}
```

| Campo | O que é |
|-------|---------|
| `threadId` | ID único da thread |
| `tipo` | Sempre "RESOLVIDA" neste arquivo |
| `data_conclusao` | Data e hora em que foi concluída |
| `motivo_triagem_auto` | Descrição para o analista (linguagem natural) |
| `motivo_triagem_auto_tecnico` | Código técnico com a regra que disparou (ex.: §3.1) |
| `empresa` | Nome do cliente |
| `cadoc` | Código regulatório |
| `assunto` | Título do e-mail |
| `aprendizado_ia` | Metadados extras para análise |
| `origem_triagem_auto` | `true` = automático; `false` = manual |
| `alvo_triagem_auto` | Qual categoria triou |

---

## 5. Filtros — o que entra e o que fica de fora

Antes de aplicar qualquer regra, o motor filtra as threads. Uma thread **não entra** na triagem se:

| Situação | Por que fica de fora |
|----------|----------------------|
| `cadoc = "IGNORADO"` | Thread marcada explicitamente para ignorar |
| `cadoc = "FILTRADO_POR_DATA"` | Thread fora do período de coleta |
| `relatorio_interno_risk_driver = true` | É relatório interno — não é comunicação com cliente |
| Thread manual (`origem_triagem_auto = false`) | Marcação manual é preservada; o motor não toca |
| Thread concluída sem nova mensagem após conclusão | Não reabre o que já foi fechado |
| Thread excluída por ID explícito | Há IDs específicos excluídos por decisão de negócio |

---

## 6. Todas as regras de triagem

As regras são organizadas em **seções (§)** e aplicadas em **buckets** (grupos por direção
da última mensagem). O motor testa as regras na ordem abaixo até uma disparar.

### 6.1 Regras Globais (aplicadas a QUALQUER thread, independente da direção)

| § | Nome | O que detecta | Resultado |
|---|------|---------------|-----------|
| **§3.1** | Transmitido no BACEN | Corpo da thread contém "transmitido no BACEN", "arquivos transmitidos", "enviado ao BC" | **CONCLUÍDO** |
| **§5** | Remessa Finaud → cliente | Última mensagem F→C com "segue em anexo", "envio ao BC", "segue o DDR" e tem arquivo | **CONCLUÍDO** |
| **§5b** | RES: Finaud | Última mensagem F→C começa com "RES:" ou "Re:" e tem corpo conclusivo | **CONCLUÍDO** |
| **§5c** | Texto conclusivo F→C | Última mensagem F→C com "já foi cadastrado", "está disponível", "segue em anexo para envio" | **CONCLUÍDO** |
| **§6** | Espelho — cluster empresa | Thread da mesma empresa + mesmos prazos onde outra thread já foi concluída | **CONCLUÍDO** |
| **§6b** | Espelho — núcleo de assunto | Thread com mesmo núcleo de assunto (DDR de mesmo período) onde outra já foi concluída | **CONCLUÍDO** |

---

### 6.2 Regras para quando a última mensagem é Finaud → Cliente (F→C)

| § | Nome | O que detecta | Resultado |
|---|------|---------------|-----------|
| **§3-inv** | Finaud pediu insumos | F→C com "pode me enviar", "preciso dos seguintes dados", "aguardo os extratos", "ainda não recebi" | **AGUARDANDO** (ENTREGA_CLIENTE) |
| **§3.5** | Finaud só reconheceu | F→C curta de agradecimento/reconhecimento quando já houve uma C→F antes (ex.: "Ok, obrigado!") | **AGUARDANDO** (ACAO_INTERNA) |
| **§3.5+** | Finaud agradeceu (sem C→F) | F→C de agradecimento quando NÃO houve C→F antes — abertura de novo ciclo | **AGUARDANDO** (ACAO_INTERNA) |
| **§5d** | Finaud orientou conclusivamente | F→C onde Finaud entregou orientação e bola passou ao cliente definitivamente ("Para solucionar, você deve…") | **CONCLUÍDO** (só em algumas categorias) |

---

### 6.3 Regras para quando a última mensagem é Finaud → Finaud (F→F)

| § | Nome | O que detecta | Resultado |
|---|------|---------------|-----------|
| **R5** | Encaminhamento interno | Última mensagem foi de uma pessoa da Finaud para outra (ex.: "Encaminho para vocês resolverem") | **AGUARDANDO** (ACAO_INTERNA) |

> Nota: em algumas categorias (ex.: DDR4111), F→F sempre gera AGUARDANDO. Em outras (ex.: DLO,
> RETORNO_BACEN), a regra pode variar.

---

### 6.4 Regras para quando a última mensagem é Cliente → Finaud (C→F)

| § | Nome | O que detecta | Resultado |
|---|------|---------------|-----------|
| **§3** | Insumo do cliente | Cliente enviou dados/arquivos → Finaud precisa processar | **AGUARDANDO** (ACAO_INTERNA) |
| **§4d** | Cliente agradeceu após remessa | C→F de agradecimento puro após uma remessa §5 da Finaud ("Muito obrigado!", "Recebi, tudo certo") | **CONCLUÍDO** |
| **§4e** | Agradecimento sem novo pedido | C→F curta de agradecimento sem pedido novo (sem pergunta) | **CONCLUÍDO** (só em algumas categorias) |
| **§4f-rb** | Cliente confirmou BACEN aceitou | C→F com "foi aceito pelo BACEN", "STA aceitou", "transmissão aceita" | **CONCLUÍDO** (só RETORNO_BACEN) |

---

### 6.5 Regra 9 — Pós-processamento (reclassificação)

Após as regras acima rodarem, o motor faz uma segunda passagem chamada "Regra 9" que pode
**reclassificar** threads:

| Sub-regra | O que faz |
|-----------|-----------|
| **9-A** | Se thread foi marcada CONCLUÍDO mas chegou nova mensagem do cliente com dados (C→F insumo) → volta para AGUARDANDO |
| **9-B** | Se Finaud enviou uma F→C pedindo insumo mas a thread estava CONCLUÍDA → volta para AGUARDANDO |
| **9-C** | Se thread CONCLUÍDA recebeu nova mensagem do cliente após conclusão → volta para AGUARDANDO. **Exceção:** se a mensagem nova é apenas um agradecimento ("Valeu!", "Obrigado!"), **não reabre** |

---

### 6.6 Flags por categoria

Cada categoria de CADOC tem configurações que ligam ou desligam certas regras:

| Categoria | F→F gera AGUARDANDO? | §6b (cluster assunto) | §3.5+ ativo? |
|-----------|---------------------|----------------------|--------------|
| DDR4111 | Não | ✅ | ❌ |
| DLI | Sim | ❌ | ❌ |
| DLO | Sim | ✅ | ✅ |
| S5 | Sim | ✅ | ✅ |
| RETORNO_BACEN | Sim | ✅ | ✅ |
| SUPORTE | Sim | ✅ | ✅ |
| DRSAC | Sim | ✅ | ✅ |
| FORCAPITAL | Sim | ✅ | ✅ |
| DRM | Sim | ✅ | ✅ |
| 6209 | Sim | ✅ | ✅ |

---

## 7. Exemplos reais por regra

> Todos os exemplos são de threads reais do sistema em produção (nomes de empresas e assuntos
> foram preservados).

---

### Regra §3.1 — Transmitido no BACEN → CONCLUÍDO

O texto da conversa menciona que o documento foi enviado/transmitido ao BACEN.

**Exemplo 1**
- Thread: `GMTHRID_1866436622083994705`
- Empresa: **Nixfin**
- CADOC: DDR_2011
- Assunto: "Documentos para implantação do sistema de riscos (Risk Driver)"
- Motivo: "Michele Quadros — transmitido ao BACEN em 29/05/2026"

**Exemplo 2**
- Thread: `GMTHRID_1866903564468967353`
- Empresa: **Guru**
- CADOC: DDR_2011
- Assunto: "Guru CTVM: Informações Diárias"
- Motivo: "Guilherme Marin — transmitido ao BACEN em 03/06/2026"

**Exemplo 3**
- Thread: `GMTHRID_1866997519499734651`
- Empresa: **Braza Bank**
- CADOC: DDR_2011
- Assunto: "DDR 29.05.2026"
- Motivo: "Risco Brazabank — transmitido ao BACEN em 03/06/2026"

---

### Regra §5 — Remessa Finaud → cliente → CONCLUÍDO

Finaud enviou o arquivo/DDR para o cliente. A thread está resolvida do lado da Finaud.

**Exemplo 1**
- Thread: `GMTHRID_1866917207220850952`
- Empresa: **Trustee**
- CADOC: DDR_2011
- Assunto: "TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.05.29"
- Motivo: "Lucas Vellani enviou arquivo ao Robson Soares Neves — TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.05.29 em 03/06/2026"

**Exemplo 2**
- Thread: `GMTHRID_1866917473885783269`
- Empresa: **Trustee**
- CADOC: DDR_2011
- Assunto: "TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.06.01"
- Motivo: "Lucas Vellani enviou arquivo ao Robson Soares Neves — TRUSTEE DTVM - EXTRATO COMPROMISSADA 2026.06.01 em 03/06/2026"

**Exemplo 3**
- Thread: `GMTHRID_1866980895684446587`
- Empresa: **Mirae Invest**
- CADOC: DDR_2011
- Assunto: "PI Exposure MiraeAsset Securities in Brazil_HK - 20260601_AUDIT. Segue o DDR."
- Motivo: "Andrea Inacio enviou arquivo ao William Barbosa de Oliveira em 03/06/2026"

---

### Regra §6 — Espelho cluster empresa → CONCLUÍDO

Thread duplicada da mesma empresa no mesmo período. Como a thread "principal" do cluster já
foi concluída, essa é fechada automaticamente também.

**Exemplo 1**
- Thread: `GMTHRID_1867000496700665957`
- Empresa: **Acredito SCD**
- CADOC: DDR_2011
- Assunto: "DDR 2011 do dia 29/05 - ACCREDITO"
- Motivo: "Thread espelho — Acredito Scd — DDR 2011 do dia 29/05 — encerrada por duplicidade com thread principal"
- Motivo técnico: `§6 espelho cluster empresa='acredito scd'`

---

### ⚠️ Bug ESPELHO — motor detectou mas não fechou (8 threads AG que deveriam ser CO)

**O que é o bug:** o motor identificou corretamente que a thread é espelho (escreveu o motivo
"Thread espelho — [cliente] — encerrada por duplicidade com thread principal"), mas **não
moveu a thread para CONCLUÍDO** — ela permaneceu em AGUARDANDO. As 9 threads CO acima
funcionaram corretamente; as 8 abaixo não foram fechadas, provavelmente por terem sido
processadas numa versão anterior do motor que tinha a detecção mas não a ação de fechar.

**Como testar a correção:** após o backfill, verificar que todos os 8 threadIds abaixo
estão em `threads_concluidas_auto.json` com motivo contendo "espelho" e **não** aparecem
mais em `threads_aguardando_auto.json`.

**Como verificar que a correção funciona:** rodar o motor sobre uma thread recém-chegada
que seja espelho de outra já concluída e confirmar que ela já sai direto como CO, sem
precisar de intervenção manual.

**As 8 threads com bug:**

**1.** `GMTHRID_1866252916823752230` — "DDR 2011 DOS DIAS 21 ao 25/05 - SEFER" (Sefer Investimento)
- Situação: Pedro (Finaud) pediu ao cliente Alison as informações de DDR dos dias 21–25/05. Uma única mensagem da Finaud, sem resposta do cliente. Thread é duplicata de outra do mesmo cliente e período onde a principal foi concluída. Motor registrou o motivo de espelho mas deixou como AG.
- Deve ser: CO (encerrada por duplicidade)

**2.** `GMTHRID_1860477336641857993` — "PI Exposure MiraeAsset Securities in Brazil_HK - 20260319_AUDIT" (Mirae Invest)
- Situação: Andrea (Finaud) pediu as compromissadas de 19/03/2026 ao Mirae. Rafael (cliente) respondeu enviando as aplicações. Thread tem 2 mensagens (F→C depois C→F). É espelho de outra thread do mesmo período Mirae que foi a principal. Motor registrou o motivo de espelho mas deixou como AG.
- Deve ser: CO (encerrada por duplicidade)

**3.** `GMTHRID_1857945692134753217` — "PI Exposure MiraeAsset Securities in Brazil_HK - 20260219_AUDIT" (Mirae Invest)
- Situação: mesmo padrão do item 2, porém referente ao período de 19/02/2026. Andrea pediu compromissadas, William (cliente) respondeu com as aplicações. Espelho de outra thread principal do mesmo período. Motor registrou mas não fechou.
- Deve ser: CO (encerrada por duplicidade)

**4.** `GMTHRID_1857941262144216568` — "Saldos 2011 e 4111 de 20/02/2026" (TC — Thaina Carvalho)
- Situação: Thaina enviou os saldos do dia 20/02 em uma única mensagem (C→F). Thread é espelho de outra do mesmo cliente e data. Motor registrou o motivo de espelho mas não moveu para CO.
- Deve ser: CO (encerrada por duplicidade)

**5.** `GMTHRID_1857667752989126731` — "Saldos 2011 e 4111 de 19/02/2026" (TC — Thaina Carvalho)
- Situação: mesmo padrão do item 4, data 19/02. Thaina enviou saldos em mensagem única. Espelho da thread principal do mesmo período.
- Deve ser: CO (encerrada por duplicidade)

**6.** `GMTHRID_1857568129921672999` — "Saldos 2011 e 4111 de 18/02/2026" (TC — Thaina Carvalho)
- Situação: mesmo padrão dos itens 4 e 5, data 18/02. Thaina enviou saldos. Espelho da thread principal.
- Deve ser: CO (encerrada por duplicidade)

**7.** `GMTHRID_1857558028071185607` — "DDR 2011 - 13/02/2026" (Acredito SCD — Carmen Simone)
- Situação: Carmen enviou os arquivos para composição do DDR2011 de 13/02 em mensagem única (C→F). Thread é espelho de outra do mesmo cliente e data onde a principal foi resolvida. Motor registrou espelho mas não fechou.
- Deve ser: CO (encerrada por duplicidade)

**8.** `GMTHRID_1856947124388761439` — "DDR 2011 - 11/02/2026" (Acredito SCD — Maria Eugenia)
- Situação: Maria Eugenia enviou os arquivos para composição do DDR2011 de 11/02 em mensagem única (C→F). Espelho da thread principal do mesmo período. Motor registrou mas não moveu para CO.
- Deve ser: CO (encerrada por duplicidade)

> **Raiz comum dos 8:** o motor executou a detecção de espelho (§6), gravou o motivo correto, mas não executou a etapa seguinte de mover a thread de `threads_aguardando_auto.json` para `threads_concluidas_auto.json`. Serão corrigidas no script de backfill junto com os demais gaps.

---

### Regra §4d — Cliente agradeceu após remessa → CONCLUÍDO

O cliente respondeu à remessa da Finaud apenas agradecendo — sem perguntas, sem pedidos novos.

**Quando acontece:** Finaud enviou o arquivo (§5), cliente respondeu "Perfeito, obrigado!" ou
"Recebi, muito obrigado!". Thread resolvida.

---

### Regra R5 — Última mensagem F→F → AGUARDANDO

A última mensagem foi de uma pessoa da Finaud para outra (encaminhamento interno). Finaud
precisa agir.

**Exemplo 1**
- Thread: `GMTHRID_1865185339841675367`
- Empresa: **Acredito SCD** (encaminhamento interno Finaud)
- CADOC: DDR_2011
- Assunto: "RWACPAD ACCREDITO - edição nas contas 520.01.020 Compromissada e 530.22 FIDC"
- Tipo: ACAO_INTERNA
- Data: 2026-06-05

**Exemplo 2**
- Thread: `GMTHRID_1858744005949499744`
- Empresa: **TC**
- CADOC: DDR_2011
- Assunto: "Saldos dos dia 02/03 a 03/03."
- Tipo: ACAO_INTERNA
- Motivo: "insumo do cliente — aguarda processamento Finaud (§3)"

---

### Regra ACAO_INTERNA — Última mensagem C→F → AGUARDANDO

O cliente enviou dados/informações. A Finaud precisa processar e responder.

**Exemplo 1**
- Thread: `GMTHRID_1859195582172107757`
- Empresa: **Saygogroup**
- CADOC: DDR_2011
- Assunto: "Re: Conta COSIF e Exposição"
- Tipo: ACAO_INTERNA
- Motivo: "Finaud aguarda retorno do cliente (última mensagem F→C)"

**Exemplo 2**
- Thread: `GMTHRID_1858560923375496724`
- Empresa: **TC**
- CADOC: DLO_2061
- Assunto: "RES: Calculo baseleia Traders - Jan/26. Segue o Indice de Basileia"
- Tipo: ACAO_INTERNA
- Data: 2026-06-10

---

### Regra §3-inv — Finaud pediu insumos → AGUARDANDO (ENTREGA_CLIENTE)

A Finaud enviou uma mensagem pedindo dados ou arquivos ao cliente. A thread fica aguardando
o cliente enviar o material.

**Exemplo 1**
- Thread: `GMTHRID_1865189786309073500`
- Empresa: **Activtrades**
- CADOC: DLO_2061
- Assunto: "DRL ACTIVTRADES ABR/26."
- Tipo: ENTREGA_CLIENTE
- Motivo: "Finaud solicitou insumos ao cliente — aguarda envio (§3-inv)"
- Data: 2026-06-05

---

### Regra RESPOSTA_CLIENTE — Cliente perguntou → AGUARDANDO (RESPOSTA_CLIENTE)

O cliente fez uma pergunta e a Finaud ainda não respondeu.

**Exemplo 1**
- Thread: `GMTHRID_1860096903075334127`
- Empresa: **Vert-capital**
- CADOC: RETORNO_BACEN
- Assunto: "Re: Erro - Cálculo do PR"
- Tipo: RESPOSTA_CLIENTE
- Motivo: "insumo do cliente — aguarda processamento Finaud (§3). | Reclassificado: cliente pergunta sem dados"
- Data: 2026-06-05

**Exemplo 2**
- Thread: `GMTHRID_1865642625128096634`
- Empresa: **Uol**
- CADOC: DLO_2061
- Assunto: "RE: Calculo de Basileia: COS 4010 04-2026."
- Tipo: RESPOSTA_CLIENTE
- Motivo: "insumo do cliente — aguarda processamento Finaud (§3). | Reclassificado: cliente pergunta sem dados"
- Data: 2026-06-05

---

### Regra RETORNO_BACEN — Análise em andamento → AGUARDANDO (ACAO_INTERNA)

Finaud respondeu ao cliente com uma mensagem substantiva (não é simples remessa), indicando
que a análise ainda está em curso.

**Exemplo 1**
- Thread: `GMTHRID_1860830834835032309`
- Empresa: **Levycam**
- CADOC: RETORNO_BACEN
- Assunto: "Re: ERRO PARA REALIZAR O DLO"
- Tipo: ACAO_INTERNA
- Motivo: "Finaud respondeu mas análise em andamento — aguarda resolução Finaud"
- Data: 2026-06-05

---

### Regra §4f-rb — Cliente confirmou que BACEN aceitou → CONCLUÍDO

Exclusiva do RETORNO_BACEN. O cliente respondeu informando que o BACEN (ou STA) aceitou o
arquivo transmitido.

**Quando acontece:** cliente escreve "A transmissão foi aceita!", "STA aceitou com sucesso",
"O BACEN aceitou a remessa". Thread encerrada.

---

## 8. Fluxo completo — do dado bruto ao status final

```
E-MAIL RECEBIDO NO GMAIL
         │
         ▼
[Script 02] Coleta o e-mail bruto
  └─ Saída: 02_classificacao_dados_brutos_gmail_editado.json
         │
         ▼
[Script 05] Classifica o CADOC regulatório (DDR_2011? DLO_2061? etc.)
  └─ Enriquece o JSON 02 com cadoc, lista_prazos, etc.
         │
         ▼
[Script 09] Integra tudo em um único arquivo consolidado
  └─ Saída: 03_integrador_dados_site.json
     Monta eventos com: título, empresa, CADOC, prazos,
     contato_origem/destino, corpo, texto_imagens
         │
         ▼
[Script 11] Motor de triagem — para cada categoria de CADOC:
  │
  ├─ 1. Pré-carrega JSON 03 (cache na memória)
  │
  ├─ 2. Filtra candidatos (remove threads excluídas, manuais, já fechadas sem msg nova)
  │
  ├─ 3. Para cada thread candidata:
  │    │
  │    ├─ Determina quem enviou a última mensagem (F→C? C→F? F→F?)
  │    │
  │    ├─ Aplica REGRAS GLOBAIS (§3.1, §5, §5b, §5c, §6, §6b)
  │    │   → Se alguma disparar: CONCLUÍDO
  │    │
  │    ├─ Se não concluído: aplica regras do bucket da direção
  │    │   F→C: testa §3-inv, §3.5, §3.5+, §5d
  │    │   F→F: testa regra de encaminhamento interno
  │    │   C→F: testa §4d, §4e, §4f-rb, §3
  │    │
  │    └─ Cria registro CONCLUÍDO ou AGUARDANDO (com motivo, tipo, data)
  │
  ├─ 4. Pós-processamento (Regra 9): reclassifica casos especiais
  │    9-A: cliente mandou insumo → AGUARDANDO
  │    9-B: Finaud pediu insumo sem remessa → AGUARDANDO
  │    9-C: nova msg após conclusão → AGUARDANDO (exceto agradecimentos)
  │
  ├─ 5. Guard de imutabilidade: não muda dias já fechados
  │
  └─ 6. Salva resultados
       ├─ threads_aguardando_auto.json  (atualizado)
       └─ threads_concluidas_auto.json  (atualizado)
```

---

## 9. O que acontece depois? O arquivo muda?

### O arquivo `threads_aguardando_auto.json` muda quando:
- Uma thread em AGUARDANDO recebe uma mensagem nova (cliente enviou dados, Finaud respondeu)
- A nova mensagem dispara uma regra de CONCLUÍDO → thread sai daqui e vai para concluídas
- O motor roda novamente e reavalia a thread

### O arquivo `threads_concluidas_auto.json` muda quando:
- Uma thread CONCLUÍDA recebe nova mensagem → Regra 9-C pode reabrir para AGUARDANDO
- O motor detecta uma thread nova que já satisfaz uma regra de conclusão

### O que o motor **nunca** muda:
- Threads marcadas **manualmente** (`origem_triagem_auto = false`) — preservadas sempre
- Status de dias anteriores já fechados — imutabilidade de dias fechados
- Threads com cadoc `IGNORADO` ou `FILTRADO_POR_DATA`

### Quando a tela do painel é atualizada:
A tela em `localhost:5000` lê os JSONs em tempo real. Assim que o script 11 termina de rodar,
a tela já mostra os novos status. Não é necessário reiniciar o Flask.

---

## 10. Glossário rápido

| Termo | Significado simples |
|-------|---------------------|
| **Thread** | Uma conversa inteira de e-mail (todas as mensagens de uma troca) |
| **CADOC** | Código do tipo de relatório regulatório (ex.: DDR_2011 = Demonstrativo de Risco de Derivativos) |
| **F→C** | Finaud enviou mensagem para o cliente |
| **C→F** | Cliente enviou mensagem para a Finaud |
| **F→F** | Mensagem interna entre pessoas da Finaud |
| **Bucket** | Grupo de regras para um mesmo tipo de direção da última mensagem |
| **§** (seção) | Número de uma regra específica do motor (ex.: §3.1 = transmitido no BACEN) |
| **Cluster** | Grupo de threads da mesma empresa + mesmos prazos tratadas em conjunto |
| **Espelho** | Thread duplicada de outra thread do mesmo cluster |
| **Guard de imutabilidade** | Proteção que impede o motor de mudar o status de um dia já fechado |
| **Regra 9** | Segunda passagem do motor que corrige classificações especiais (reclassificação) |
| **JSON 03** | Arquivo consolidado que serve de entrada para o motor (`03_integrador_dados_site.json`) |
| **Origem manual** | Thread marcada por uma pessoa (não pelo motor automático) — nunca é tocada |
| **data_ref** | Data de referência da carga — o motor só processa threads até essa data |
| **OCR** | Leitura de texto dentro de imagens/prints de tela |
| **Pipeline** | Sequência de scripts que processa os dados do início ao fim (01 → 20) |

---

*Gerado em: 2026-06-16 | Atualizado: 2026-06-17 | Versão do sistema: branch `desenvolvimento-front_end`*
*Para sugestões de correção, consultar `documentações/REGISTRO_CORRECOES.md`*

---

## 11. Decisões de mudança identificadas na validação

> Esta seção registra o que foi decidido durante a validação item a item com o dono do sistema.
> Cada item tem: o que muda, por quê, impacto nos dados existentes e como implementar com segurança.
> **Nada aqui foi implementado ainda** — serve de roteiro para execução futura.

---

### MUDANÇA 1 — FogBugz e Risk Driver não devem ser triados nem aparecer no painel

**Decisão (2026-06-17):** FogBugz e Risk Driver (alertas, relatórios, respostas automáticas)
não devem ser triados automaticamente nem aparecer no painel de AGUARDANDO/CONCLUÍDO.

- **FogBugz:** tem tela própria; a decisão de usar esses e-mails no painel ainda está em aberto.
- **Risk Driver:** são e-mails internos sem fluxo definido com o cliente — não faz sentido tria-los.

**Estado atual no sistema:**
| Categoria | AGUARDANDO hoje | CONCLUÍDO hoje |
|-----------|----------------|----------------|
| FOGBUGZ | 0 | 8 |
| RISK_DRIVER_ALERTA | 0 | 42 |
| RISK_DRIVER_RELATORIO | 0 | 16 |
| RISK_DRIVER_RESP_AUTO | 0 | 2 |
| LEIAUTES_BACEN | 0 | 7 |
| **Total a remover** | **0** | **75** |

**Impacto:** 75 registros em CONCLUÍDO que precisam sair dos JSONs. Nenhum em AGUARDANDO.

**Como implementar com segurança (3 passos):**

1. **Passo 1 — Filtrar na tela (imediato, sem risco):**
   Adicionar filtro na camada Flask para não exibir registros com
   `alvo_triagem_auto` em `{FOGBUGZ, RISK_DRIVER_ALERTA, RISK_DRIVER_RELATORIO, RISK_DRIVER_RESP_AUTO, LEIAUTES_BACEN}`.
   Os JSONs não são alterados — só a exibição muda. Reversível a qualquer momento.

2. **Passo 2 — Limpar os JSONs (após validar que a tela ficou correta):**
   Fazer backup com timestamp e remover os 75 registros dos JSONs de produção.
   ```powershell
   # Fazer backup antes
   $ts = Get-Date -Format "yyyyMMdd_HHmm"
   Copy-Item threads_concluidas_auto.json "threads_concluidas_auto.json.backup_$ts"
   # Rodar script de limpeza (a criar)
   python scripts/_limpar_fogbugz_riskdriver.py
   ```

3. **Passo 3 — Desativar os módulos de triagem (após Passo 2 validado):**
   No script 11, remover ou desativar as chamadas para os módulos
   `FOGBUGZ`, `RISK_DRIVER_*` e `LEIAUTES_BACEN`.
   Assim eles não voltam a aparecer nas próximas cargas.

> ⚠️ **Risco se pular o Passo 1:** se limpar os JSONs sem filtrar a tela antes,
> e a próxima carga ainda tiver os módulos ativos, os registros voltam.
> A ordem dos 3 passos é de segurança — não pular.

> ❓ **Decisão pendente sobre LEIAUTES_BACEN:** incluir na remoção junto com FogBugz/Risk Driver,
> ou tratar separadamente? São comunicados do BACEN sobre leiautes — podem ter valor para o painel.

---

### MUDANÇA 2 — Simplificar os tipos de AGUARDANDO

**Decisão confirmada (2026-06-17):** o modelo atual com 3 tipos confunde até quem criou o
sistema. Os nomes `ACAO_INTERNA`, `ENTREGA_CLIENTE` e `RESPOSTA_CLIENTE` induzem ao erro
(ex.: ENTREGA_CLIENTE parece "cliente já entregou", mas significa "aguardando o cliente
entregar"). Qualquer analista novo vai se confundir da mesma forma.

**O modelo correto — 3 perguntas em sequência:**

```
1. Qual o status desta thread?   → AGUARDANDO  ou  CONCLUÍDO
2. Com quem está a thread?       → FINAUD       ou  CLIENTE
3. Porque?                       → motivo baseado no CADOC e na regra
```

**Mapeamento dos tipos antigos para o novo modelo:**

| Tipo antigo | Significado real | Com quem (novo) | Porque (exemplos) |
|-------------|-----------------|----------------|-------------------|
| `ACAO_INTERNA` | Finaud recebeu dado ou encaminhamento interno e precisa agir | **FINAUD** | "Cliente enviou extratos — aguarda processamento Finaud" / "Encaminhamento interno — aguarda tratamento" |
| `ENTREGA_CLIENTE` | Finaud pediu algo e **o cliente ainda não enviou** | **CLIENTE** | "Finaud solicitou extratos — aguarda envio do cliente" |
| `RESPOSTA_CLIENTE` | Cliente perguntou e **a Finaud ainda não respondeu** | **FINAUD** | "Cliente perguntou sobre conta COSIF — aguarda resposta Finaud" |

> **Nota:** `ACAO_INTERNA` e `RESPOSTA_CLIENTE` ambos viram `FINAUD`. A distinção entre os
> dois fica no campo `Porque` (motivo), que é texto descritivo — o analista entende o contexto
> sem precisar de um terceiro tipo técnico.

**Impacto nos dados existentes:**
- Campo `tipo` nos JSONs: muda de 3 valores para 2 (`FINAUD` / `CLIENTE`)
- Todos os registros em `threads_aguardando_auto.json` precisam ser migrados
- A tela Flask que exibe o campo `tipo` precisa ser atualizada
- O motor (`motor.py`) precisa gravar os novos valores nas próximas cargas

**Como implementar com segurança (em ordem — não pular etapas):**
1. Fazer backup dos JSONs com timestamp
2. Rodar script de migração: `ACAO_INTERNA` → `FINAUD`, `ENTREGA_CLIENTE` → `CLIENTE`, `RESPOSTA_CLIENTE` → `FINAUD`
3. Atualizar a tela Flask para usar `FINAUD` / `CLIENTE`
4. Atualizar o motor para gravar os novos valores
5. Validar na tela que os filtros e contagens continuam corretos

> ⚠️ **Os passos 3 e 4 precisam estar no mesmo deploy** — se a tela for atualizada antes do
> motor, cargas novas vão gravar os valores antigos e a tela vai quebrar (ou vice-versa).

> 📋 **CADOCs afetados:** a ser definido na validação separada da lista de CADOCs.

---

### MUDANÇA 3 — Simplificar campo "tipo" nos JSONs

**Decisão (2026-06-17):** os nomes atuais (`ACAO_INTERNA`, `ENTREGA_CLIENTE`, `RESPOSTA_CLIENTE`)
confundem porque parecem indicar que a ação **já aconteceu**, quando na verdade indicam **quem
ainda precisa agir**. Substituir por `FINAUD` e `CLIENTE`.

**Mapeamento:**
- `ACAO_INTERNA` → `FINAUD`
- `ENTREGA_CLIENTE` → `CLIENTE`
- `RESPOSTA_CLIENTE` → `FINAUD`

---

## 12. Validação por CADOC — padrões reais de cada conversa

> Esta seção documenta os padrões reais encontrados nas threads de cada CADOC, validados
> com o dono do sistema. Serve de base para revisar e melhorar as regras do motor.
> **Validação em andamento — sessão de 2026-06-17.**

---

### 12.1 DDR_2011 — Demonstrativo diário de acompanhamento das parcelas de requerimento de capital e dos limites operacionais

**O que é:** Relatório diário de capital e limites operacionais. O cliente envia os extratos do dia, a Finaud processa, gera o arquivo DDR e entrega ao cliente para transmissão ao BACEN.

**Total de threads:** 1.349

**Fluxo padrão:**
1. Cliente envia extratos (PDF, Excel, texto) para a Finaud
2. Finaud insere os dados no sistema, gera o arquivo DDR
3. Finaud envia o arquivo **em anexo** por e-mail ao cliente
4. Cliente transmite ao BACEN
5. **Conclusão = Finaud enviou o anexo ao cliente** — não é necessária confirmação do cliente

> ⚠️ **Gap técnico identificado:** o campo `anexos_detectados` existe nos dados mas o motor
> hoje detecta o envio por palavras no texto ("segue em anexo"). Threads onde a Finaud enviou
> o arquivo sem escrever essa frase podem ficar como AGUARDANDO indevidamente.

---

**Cobertura de padrões — DDR_2011 (total: 1.349 threads)**

| Padrão | Qtd | % do total | Direção das mensagens | Validado? |
|--------|-----|------------|----------------------|-----------|
| 1 | 391 | 29% | Só F→C | ✅ |
| 2 | 371 | 27,5% | C→F → F→C | ✅ |
| 3 | 309 | 22,9% | Só C→F | ✅ |
| 4 | 84 | 6,2% | C→F → C→F | ✅ |
| 5 | 55 | 4,1% | F→C → C→F | ✅ |
| 6 | 21 | 1,6% | F→C → C→F → F→C | ✅ |
| 7 | 20 | 1,5% | C→F → F→C → C→F | ✅ |
| 8 | 19 | 1,4% | F→C → F→C | ✅ |
| 9 | 13 | 1,0% | C→F → C→F → F→C | ✅ |
| 10 | 11 | 0,8% | C→F → F→C → C→F → F→C | ✅ |
| Longas (4+ msgs raras) | ~55 | 4,1% | Variações com 5+ mensagens | ✅ (mesma regra geral) |
| **Total** | **1.349** | **100%** | | **✅ 100% coberto** |

> Todos os padrões relevantes validados. A regra geral se aplica às conversas longas.

---

**Regras validadas para DDR_2011:**

> A análise abaixo está organizada por padrão de mensagem (como foi feita a descoberta). O quadro final consolida tudo nas regras R1–R5 com "Quando dispara" por regra.

#### Padrão 1 — Só F→C (391 threads)
Dentro deste padrão existem 4 sub-cenários distintos:

| Sub | Pista no texto da última mensagem | Status | Com quem | Porque |
|-----|----------------------------------|--------|----------|--------|
| A | "segue em anexo o DDR", "segue anexo para envio ao BC" | **Concluído** | Finaud | Enviou o DDR ao cliente |
| B | "por gentileza enviar", "poderia confirmar", "ainda não recebi" | **Aguardando** | Cliente | Finaud aguarda dados do cliente |
| C | "já foram cadastradas", "já foi preenchido", "já foi resolvido" | **Concluído** | Finaud | Finaud resolveu a pendência sem enviar arquivo |
| D | "enviados ao BACEN", "disponibilizo os protocolos" | **Concluído** | Finaud | Transmitiu ao BACEN — protocolo é complementar, não bloqueia |

> 📌 **Insight:** nem todo DDR_2011 envolve envio de arquivo. Alguns são sobre cadastros,
> preenchimentos ou correções — a conclusão é a confirmação da ação feita pela Finaud.

---

#### Padrão 2 — C→F → F→C (371 threads — padrão normal)
```
Cliente envia extratos → Finaud gera e devolve o DDR em anexo
```
| Status | Com quem | Porque |
|--------|----------|--------|
| **Concluído** | Finaud | Finaud enviou o DDR ao cliente |

---

#### Padrão 3 — Só C→F (309 threads)
```
Cliente enviou dados — Finaud ainda não processou nem respondeu
```
| Status | Com quem | Porque |
|--------|----------|--------|
| **Aguardando** | Finaud | Cliente enviou dados, Finaud precisa gerar e enviar o DDR |

---

#### Padrão 4 — C→F → C→F (84 threads)
```
Cliente enviou dados duas vezes sem Finaud responder
```
| Status | Com quem | Porque |
|--------|----------|--------|
| **Aguardando** | Finaud | Cliente enviou dados (repetiu), Finaud ainda não processou |

---

#### Padrão 7 — C→F → F→C → C→F (20 threads)
Dentro deste padrão existem sub-cenários:

| Sub | Situação | Status | Com quem | Porque |
|-----|----------|--------|----------|--------|
| A | Cliente enviou → Finaud respondeu parcialmente → cliente enviou mais dados | **Aguardando** | Finaud | Finaud precisa gerar e enviar o DDR com os dados completos |
| B | Cliente enviou → Finaud enviou DDR → cliente voltou com **retificação** | **Aguardando** | Finaud | Cliente reenvio dados corrigidos — Finaud precisa gerar o DDR corrigido |
| C | Cliente enviou → Finaud prometeu retornar → cliente enviou dados adicionais | **Aguardando** | Finaud | Finaud precisa processar e responder |
| D | Cliente enviou → Finaud devolveu DDR → cliente **agradeceu** | **Concluído** | Finaud | Cliente confirmou recebimento — assunto encerrado |

> ⚠️ **Regra crítica:** C→F como última mensagem **não é sempre Aguardando**.
> Se o cliente apenas agradeceu ("obrigado", "recebi", "perfeito"), a thread é **Concluída**.
> O conteúdo da última mensagem precisa ser verificado.

---

#### Padrão 8 — F→C → F→C (19 threads)
```
Finaud enviou duas mensagens sem resposta do cliente
```
Pode representar dois cenários opostos:
- MSG 1: Finaud cobrava dados → MSG 2: Finaud informa que enviou os DDRs e anexa protocolos → **Concluído / Finaud / Enviou os DDRs ao BACEN**
- MSG 1 e 2: Finaud cobrando sem resultado → **Aguardando / Cliente / Cliente não enviou os dados**

> ⚠️ **A última mensagem decide:** se contém "enviado ao BACEN", "segue em anexo", "protocolos
> de aceite" → Concluído. Se contém cobrança ou pedido de dados → Aguardando / Cliente.

---

#### Padrão 5 — F→C → C→F (55 threads)
```
Finaud pediu os dados → cliente enviou os dados (mas Finaud ainda não gerou nem enviou o DDR)
```
| Status | Com quem | Porque |
|--------|----------|--------|
| **Aguardando** | Finaud | Cliente entregou os dados, Finaud precisa gerar e enviar o DDR |

---

#### Padrão 6 — F→C → C→F → F→C (21 threads)
```
Finaud pediu extratos → cliente enviou → Finaud gerou e enviou o DDR (última msg F→C)
```
| Sub | Conteúdo da última F→C | Status | Com quem | Porque |
|-----|------------------------|--------|----------|--------|
| A | Enviou o DDR em anexo ao cliente | **Concluído** | Finaud | Finaud entregou o arquivo |
| B | Enviou a remessa ao BACEN e aguarda consistência interna | **Aguardando** | Finaud | Finaud aguarda etapa interna complementar |

> A última mensagem F→C decide: se entregou o arquivo ao cliente → Concluído; se ainda aguarda etapa interna → Aguardando/Finaud.

---

#### Padrão 9 — C→F → C→F → F→C (13 threads)
```
Cliente pediu algo duas vezes → Finaud respondeu confirmando na última mensagem
```
| Status | Com quem | Porque |
|--------|----------|--------|
| **Concluído** | Finaud | Finaud confirmou a conclusão da tarefa (cadastro, envio, etc.) |

---

#### Padrão 10 — C→F → F→C → C→F → F→C (11 threads)
```
Troca mais longa — mas a última mensagem é sempre F→C
```
| Sub | Conteúdo da última F→C | Status | Com quem | Porque |
|-----|------------------------|--------|----------|--------|
| A | Finaud entregou o DDR ao cliente | **Concluído** | Finaud | Responsabilidade da Finaud encerrada na entrega |
| B | Finaud confirmou tarefa (cadastro, correção) | **Concluído** | Finaud | Ação concluída pela Finaud |

> **Regra:** quando a Finaud envia o DDR ao cliente, a thread é Concluída — não importa se o cliente ainda vai transmitir ao BACEN. A Finaud não tem como rastrear se o cliente transmitiu. Se o cliente responder depois com agradecimento → mantém Concluído (Regra 9-C). Se responder com nova pendência → reabre (Aguardando/Finaud).

---

#### Conversas longas (4+ mensagens — ~55 threads)
Variações com 5 ou mais mensagens seguem a **mesma regra geral**: quem tem a bola na última mensagem e o que está pendente. Não há subpadrão exclusivo dessas conversas — as regras dos padrões 1–10 já cobrem os cenários possíveis.

---

#### Regra R1 — Concluído / Finaud entregou ou confirmou a tarefa

**Quando dispara:**
- Última mensagem F→C com "segue em anexo o DDR", "segue anexo para envio ao BC", "enviados ao BACEN", "disponibilizo os protocolos"
- Última mensagem F→C com confirmação de ação interna ("o cadastro está disponível", "já foi preenchido", "já foi resolvido")
- Última mensagem C→F com agradecimento puro ("obrigado", "recebi", "perfeito") — sem pedido, sem dado novo
- Sub-caso: Finaud transmite o arquivo DDR diretamente ao BACEN em nome do cliente (serviço pago adicional) — protocolo de aceite recebido = R1 Concluído

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1868069120143797916` | TRUSTEE DTVM - EXTRATO 2026.06.12 | "Segue em anexo o DDR de 12/06/2026 para envio ao BC." |
| `GMTHRID_1868172771979410159` | TRUSTEE DTVM - EXTRATO 2026.06.15 | "Segue em anexo o DDR de 15/06/2026 para envio ao BC." |
| `GMTHRID_1868069057779249133` | TRUSTEE DTVM - EXTRATO 2026.06.11 | "Segue em anexo o DDR de 11/06/2026 para envio ao BC." |

> ⚠️ Mínimo de 5 exemplos não atingido para R1 — 3 exemplos reais disponíveis; padrão bem conhecido (entrega diária de DDR em anexo).

---

#### Regra R2 — Aguardando/Finaud / cliente enviou dados ou mensagem

**Quando dispara:**
- Última mensagem C→F com envio de extratos, PDF, Excel ou dados ("Segue em anexo os extratos", "Segue abaixo DDR")
- Última mensagem C→F com retificação de dados ("Segue versão corrigida")
- Última mensagem C→F com nova demanda após ciclo anterior concluído

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1868172808255319474` | BANVOX DTVM - EXTRATO COMPROMISSADA | "Anexo extratos da Banvox referentes aos dias 11, 12 e 15/06/2026." |
| `GMTHRID_1868095085158806933` | DDR e CADOC - 10/06 a 12/06 | "Segue abaixo DDR: Segue abaixo CADOC." |
| `GMTHRID_1867714265322783691` | BANVOX DTVM - EXTRATO 08 a 10/06 | "Anexo extratos da Banvox referentes aos dias 08 a 10/06/2026." |

> ⚠️ Mínimo de 5 exemplos não atingido para R2 — 3 exemplos reais disponíveis; padrão dominante (391 threads, 29% do total).

---

#### Regra R3 — Aguardando/Cliente / Finaud aguarda dado ou ação do cliente

**Quando dispara:**
- Última mensagem F→C com pedido de dados ("por gentileza enviar", "poderia confirmar", "ainda não recebi")
- Última mensagem F→C com lembrete de prazo
- Última mensagem F→C com entrega **e** pedido simultâneos — o pedido prevalece

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1868184541379253404` | DDR DIA 11/06 12/06 E 15/06 | "Poderia confirmar se houve compromissada nos dias 11 e 12/06?" |
| `GMTHRID_1868179711196798230` | DDRs. | "Por gentileza enviar as informações para cálculo dos DDRs de 11, 12 e 15/06/2026." |
| `GMTHRID_1868164201062338046` | Cota de fundos DDR 12.06 | "Os dados já foram preenchidos, por gentileza, realize o cálculo novamente." |

> ⚠️ Mínimo de 5 exemplos não atingido para R3 — 3 exemplos reais disponíveis.

---

#### Regra R4 — Aguardando/Finaud / etapa interna pendente

**Quando dispara:**
- Última mensagem F→C com acuse de recebimento sem entrega ("Obrigada pela informação", "Ok, recebido", "Retornaremos em breve")
- Última mensagem F→C com entrega parcial e etapa complementar pendente

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1857495319388719305` | DDR WISE - 11 ATÉ 13/02 | "Estamos providenciando as remessas DDRs das respectivas datas. À disposição." |

> ⚠️ Mínimo de 5 exemplos não atingido para R4 — apenas 1 exemplo real disponível; padrão raro (2 threads no total).

---

#### Regra R5 — Aguardando/Finaud / encaminhamento interno

**Quando dispara:**
- Última mensagem F→F (Finaud para Finaud) — sem comunicação direta com cliente

**Exemplos reais:**

> ⚠️ Nenhum exemplo F→F mapeado para DDR_2011. Ver DRL_2160 (seção 12.3) para exemplos de referência do padrão R5.

---

**Regra geral C→F como última mensagem — DDR_2011:**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Agradecimento puro ("obrigado", "recebi", "perfeito") | **Concluído** | Finaud | Cliente confirmou recebimento |
| Envio de dados ou arquivos | **Aguardando** | Finaud | Finaud precisa processar e gerar o DDR |
| Pergunta ou dúvida | **Aguardando** | Finaud | Finaud precisa responder |
| Retificação de dados enviados anteriormente | **Aguardando** | Finaud | Finaud precisa gerar o DDR corrigido |

---

**Quadro final DDR_2011 — regras de negócio validadas (simulação: 1.349 threads)**

| Regra | Lado (Responsável) | Motivo | Status | Threads | Aplica a |
|-------|--------------------|--------|--------|---------|----------|
| R1 | Cliente | Finaud entregou o arquivo ao cliente | Concluído | 677 | DDR_2011, 4111 |
| R2 | Finaud | Cliente enviou dados — Finaud precisa processar e entregar | Aguardando | 480 | DDR_2011, 4111 |
| R3 | Cliente | Finaud enviou mensagem — aguarda ação do cliente | Aguardando | 190 | DDR_2011, 4111 |
| R4 | Finaud | Finaud aguarda etapa interna complementar | Aguardando | 2 | DDR_2011, 4111 |
| R5 | Finaud | Encaminhamento interno entre pessoas da Finaud (F→F) | Aguardando | — | DDR_2011, 4111 |
| **Total** | | | | **1.349** | |

> 📌 **Refinamento R3 — pedido da Finaud não resolvido prevalece sobre entrega (regra geral, todos os CADOCs):**
> Quando a última mensagem da Finaud contém **ao mesmo tempo uma entrega e um pedido ao cliente**, o thread fica **AGUARDANDO** — não CONCLUÍDO. O pedido pendente tem prioridade sobre a entrega feita. Isso vale mesmo que o cliente responda "obrigado" sem enviar o que foi solicitado: agradecimento ≠ entrega. O thread só vira CONCLUÍDO quando o cliente enviar o que foi pedido **e** a Finaud concluir com a entrega final.
>
> *Exemplo real:* Monica enviou o DDR/DRM ao BACEN (entrega R1) e na mesma mensagem pediu o balancete COS4010 para gerar o DLO (pedido R3). Guilherme agradeceu e disse que vai solicitar à contabilidade. Thread = **AGUARDANDO/Cliente** (R3), não CONCLUÍDO.

**Conclusão da validação:** O DDR_2011 foi o primeiro CADOC analisado — a descoberta dos padrões e regras foi feita aqui e depois replicada para os demais. As regras R1–R5 emergiram desta análise. O fluxo é: cliente envia extratos → Finaud gera DDR → Finaud entrega ao cliente → cliente transmite ao BACEN. Conclusão = Finaud entregou o arquivo. Não é necessário rastrear a transmissão ao BACEN pelo cliente.

> ⚠️ **2 threads com gap — precisam de backfill:**
> - `GMTHRID_1867636963980688238` ("Re: ERPM11 - Fator de Risco") — está como **AGUARDANDO mas deveria ser CONCLUÍDO** (R1). Situação: cliente pediu o cadastro do fator de risco ERPM11. Andrea (Finaud, 10/06/2026) respondeu com uma única mensagem: *"O cadastro do fator de risco já está disponível. À disposição."* — tarefa concluída, Finaud entregou a confirmação. Motor deixou como AGUARDANDO porque a frase não contém palavras-chave de entrega de arquivo ("segue", "anexo", "remessa") — o cadastro foi feito no sistema interno, não houve envio de arquivo. A nova regra R1 (confirmação de tarefa concluída) corrigiria isso em threads novas; esta thread antiga precisa de backfill.
> - `GMTHRID_1856412445483493555` ("GURU - ENVIO DO DDR E DRM - JAN/2026") — está como **CONCLUÍDO mas deveria ser AGUARDANDO** (R3). Situação: Monica (Finaud) entregou as remessas do DDR_2011 e DRM_2060 ao BACEN (tarefa principal feita), mas **na mesma mensagem** também solicitou ao cliente o balancete do COS4010, que é o insumo necessário para gerar o CADOC DLO. O cliente (Guilherme) agradeceu e disse que vai solicitar à contabilidade — ou seja, o balancete **não foi entregue**. O motor viu o agradecimento do cliente e classificou como CONCLUÍDO, mas a Finaud ainda está aguardando o balancete para poder fechar o DLO. Não é por existir balancete que vai para AGUARDANDO — é porque a Finaud fez uma solicitação explícita ao cliente na mesma mensagem em que entregou, e essa solicitação não foi atendida.
> Ambas serão corrigidas no script de backfill após implementação (junto com gaps dos demais CADOCs — ver seção 13.10).

**Exemplos pós-conclusão DDR_2011 (para testes):**

> O fluxo pós-conclusão do DDR_2011 segue o mesmo padrão do 4111 (seção 12.2) — ambos são idênticos. As regras da seção 14 cobrem todos os cenários.

| Situação | threadId | Assunto | Última msg cliente | Resultado esperado |
|----------|----------|---------|-------------------|-------------------|
| Cliente agradeceu → mantém CO | `GMTHRID_1868069120143797916` | TRUSTEE DTVM - EXTRATO 2026.06.12 | "Obrigada!" (cliente confirmou recebimento) | Mantém Concluído |
| Cliente agradeceu → mantém CO | `GMTHRID_1868069057779249133` | TRUSTEE DTVM - EXTRATO 2026.06.11 | "Ok, recebido." | Mantém Concluído |
| Cliente enviou dados → reabre | `GMTHRID_1868172808255319474` | BANVOX DTVM - EXTRATO COMPROMISSADA | "Anexo extratos da Banvox referentes aos dias 11, 12 e 15/06/2026." | Reabre → Aguardando/Finaud |

**Validação pós-conclusão DDR_2011 (passo 9 da metodologia):**

Analisadas **203 threads CO do DDR_2011** que receberam mensagem nova após o fechamento:

- **172 FINAUD-last** → todas ✅ corretas. Padrão dominante: Finaud entregou o DDR ao cliente ("segue em anexo o DDR de XX/XX para envio ao BC"), cadastrou opções de ações ("As opções de ações já foram cadastradas") ou resolveu erro sistêmico. Todas se enquadram em R1.
- **31 CLIENTE-last** → analisadas individualmente:
  - **25 ✅ CO correto** — agradecimentos ("Obrigado, Flavio!", "Valeu!", "deu certo"), confirmações de transmissão ("DDR referente a XX.XX transmitido no BACEN"), e resoluções ("Funcionou! Muito obrigado").
  - **6 ❌ gaps** (CO→AG) — cliente enviou insumo novo ou pediu entrega pendente:

| threadId | Assunto | Última msg cliente | Tipo |
|----------|---------|-------------------|------|
| `GMTHRID_1854960118250526724` | DDR 16.01.2026 | "Enviado documento de substituição para ajuste contábil" | R2 — insumo novo |
| `GMTHRID_1855136335834009479` | Re: Capital Mínimo Nova Regulação | "Tenho agenda para reunião online amanhã às 11h. É possível?" | R2 — aguarda resposta Finaud |
| `GMTHRID_1855505611493548257` | Re: Testes Arquivos 4111 e 2011 | "Anexos os arquivos de Outubro 2025 para DDR 2011" | R2 — insumo novo |
| `GMTHRID_1857580055852238257` | DDR de 13/02/2026 | "Faltou o arquivo do dia 18/02, poderia nos enviar?" | R2 — entrega pendente |
| `GMTHRID_1858303292745768270` | Re: Calculo baseleia Traders | "Enviamos o 2060 retificado mas a inconsistência não desapareceu. Preciso adicionar comentário?" | R2 — problema em aberto |
| `GMTHRID_1858755788267685330` | 2011 e 4111 de 02 e 03/03/2026 | "Ainda não recebemos o DRM 2060. Poderia disponibilizar?" | R2 — entrega pendente |

**Resultado: 197 corretos ✅ · 6 gaps ❌ → ver Grupo H no backfill (seção 13.10)**

> ⚠️ **6 threads com gap — precisam de backfill (ver seção 13.10 — Grupo H):** todas são caso 2 do quadro de regras pós-conclusão (seção 14) — cliente trouxe nova demanda após o fechamento. Motor manteve CO porque a regra de reabertura não detectou os sinais nessas mensagens.

> ✅ **Seção 14 cobre todos os casos encontrados.** Não há situação nova fora do quadro da seção 14.

> ✅ **DDR_2011 — validação de regras de negócio concluída** (17/06/2026)

---

### Metodologia padrão — aplicada a todos os CADOCs

> Esta metodologia vale para **todos os CADOCs** sem exceção.
> Nenhuma thread pode ficar de fora — a soma dos padrões deve bater com o total do CADOC.

**Para cada CADOC, seguir esta ordem:**

1. **Levantar o total de threads** do CADOC nos dados reais
2. **Mapear todos os padrões** (direção das mensagens) com a contagem de cada um
3. **Montar a tabela de cobertura** — % validado vs % pendente
4. **Validar cada padrão** com exemplos reais (mínimo 2-3 exemplos por padrão):
   - Trazer penúltima e última mensagem
   - Claude propõe: Status / Com quem / Porque
   - Usuário confirma ou corrige
5. **Fechar 100% da cobertura** — todo padrão deve ter Status / Com quem / Porque definidos
6. **Simular** nas threads reais e comparar com o status atual nos JSONs
7. **Analisar divergências** — erro do motor ou caso especial?
8. **Validar resultado** e fechar o CADOC
9. **Validar pós-conclusão** — pegar as threads já marcadas como Concluído neste CADOC que receberam mensagem nova depois do fechamento; para cada uma, verificar se o motor tratou certo (manteve CO ou reabriu para AG); confirmar que as regras da seção 14 cobrem todos os casos encontrados; se houver gap (thread ficou CO mas deveria ter reaberto), registrar na seção 13.10 e no Grupo correspondente do backfill

> ✅ **Critério de conclusão:** a soma de todos os padrões = total de threads do CADOC.
> Se sobrar qualquer thread sem padrão mapeado, ela vira um novo padrão a analisar.

---

### 12.2 — CADOC 4111

**O que é:** Relatório periódico de patrimônio de referência. O cliente envia os dados de posição, a Finaud processa, gera o arquivo CADOC 4111 e entrega ao cliente para transmissão ao BACEN.

**Fluxo padrão:**
1. Cliente envia extratos, posições ou arquivos de dados (PDF, Excel, texto) para a Finaud
2. Finaud processa os dados e gera o arquivo CADOC 4111
3. Finaud envia o arquivo **em anexo** por e-mail ao cliente
4. Cliente transmite o arquivo ao BACEN
5. **Conclusão = Finaud enviou o arquivo ao cliente** — não é necessária confirmação de transmissão ao BACEN

> ⚠️ **Gap técnico:** o motor detecta a entrega do 4111 pelo **texto** da mensagem ("segue em anexo", "seguem arquivos Cadoc"). Se a Finaud entregar o arquivo sem escrever uma dessas frases (ex.: apenas com anexo e assunto), a thread pode ficar como AGUARDANDO indevidamente. Mesmo gap do DDR_2011.

**Total:** 376 threads (275 Concluídas · 99 Aguardando)

---

**Cobertura de padrões — 4111 (total: 376 threads)**

| Padrão | Threads | % | Última mensagem | Regra | Status |
|--------|---------|---|-----------------|-------|--------|
| F→C | 140 | 37% | F→C | R1 ou R3 | CO (entregou) ou AG (pediu dado) |
| C→F \| F→C | 128 | 34% | F→C | R1 ou R4 | CO (entregou) ou AG (acusou sem entregar) |
| C→F | 63 | 17% | C→F | R1 ou R2 | CO (agradeceu) ou AG (enviou dados) |
| F→C \| C→F | 10 | 3% | C→F | R1 ou R2 | CO (agradeceu) ou AG (enviou dados) |
| Outros (longas) | 35 | 9% | variado | R1/R2/R3/R4 | mesma lógica geral |
| **Total** | **376** | **100%** | | | **✅ 100% coberto** |

---

**Regras validadas para 4111:**

---

#### Regra R1 — Concluído: Finaud entregou o arquivo ao cliente

**Quando dispara:**
- Última mensagem F→C com "segue arquivo Cadoc 4111", "seguem arquivos Cadoc's 4111", "segue anexo relatório 4111", "para envio ao BACEN", "para envio ao BC"
- Última mensagem C→F com agradecimento puro ("Obrigada Lucas!", "Ok, recebido") — sem pedido novo

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R1 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1864916044758566015` | CORREÇÃO 4111 - SCD | C→F\|F→C | "Paulo, segue arquivo Cadoc 4111 da SCD do dia 31/03/2026, gerado como substituição..." | Finaud entregou o arquivo 4111 |
| `GMTHRID_1865077352082529519` | 4111 DIA 11/05 | C→F\|F→C | "Paulo, seguem arquivos Cadoc's 4111 da CV e SCD do dia 11/05/2026, para envio ao BACEN." | Finaud entregou os arquivos |
| `GMTHRID_1865009294074084089` | Geração do arquivo Doc. 4111-COS de 11/05 - Sefer | C→F\|F→C | "Seguem em anexo os CADOC's 4111 de 11/05/2026, para envio ao BC." | Finaud entregou os arquivos |
| `GMTHRID_1854944215553167083` | CADOC 4111 CV/SCD - DIA 19/01 e 20/01 — Planner | F→C | "Paulo, seguem arquivos Cadoc´s 4111 da CV e SCD dos dias 19 e 20/11/2025, gerados como substituição..." | Finaud entregou arquivos substituição |
| `GMTHRID_1855042192325270629` | Relatório 4111 de 19/01/2026 — Fair | F→C | "Segue anexo relatório 4111 de 19/01/2026 para envio ao Banco Central." | Finaud entregou o relatório |

---

#### Regra R2 — Aguardando/Finaud: cliente enviou dados — Finaud precisa processar e entregar

**Quando dispara:**
- Última mensagem C→F com envio de arquivo de informações ("Segue em anexo arquivos com informações para envio do CADOC 4111", "Bom dia, Flávio! Segue em anexo arquivos")
- Última mensagem C→F com dados ou posições enviados pelo cliente sem Finaud ainda ter respondido

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R2 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1864908999789065099` | 4111_06/05 e 07/05/2026 | C→F | "Segue em anexo arquivos com informações para envio do CADOC 4111 de 06/05 e 07/05/2026." | Cliente enviou dados, Finaud precisa processar |
| `GMTHRID_1864469303328630950` | 4111_04/05 e 05/05/2026 | C→F | "Segue em anexo arquivos com informações para envio do CADOC 4111 de 04/05 e 05/05/2026." | Cliente enviou dados |
| `GMTHRID_1864276428493720815` | 4111_28/04, 29/04 e 30/04 | C→F | "Segue em anexo arquivos com informações para envio do CADOC 4111 de 28/04, 29/04 e 30/04." | Cliente enviou dados |
| `GMTHRID_1855033163670384779` | 4111_20/01 e 21/01 — Coluna DTVM | C→F | "Bom dia, Flávio! Segue em anexo arquivos com informações para envio do CADOC 4111 de 20/01 e 21/01/2026." | Cliente enviou dados |
| `GMTHRID_1855136645111508379` | 4111_22/01/2026 — Coluna DTVM | C→F | "Bom dia, Flávio! Segue em anexo arquivos com informações para envio do CADOC 4111 de 22/01/2026." | Cliente enviou dados |

---

#### Regra R3 — Aguardando/Cliente: Finaud enviou mensagem — aguarda ação do cliente

**Quando dispara:**
- Última mensagem F→C com pedido de dados ou posições ("por gentileza enviar o anexo", "peço a gentileza de quando tiver a disponibilidade das informações")
- Última mensagem F→C com lembrete de prazo ou cobrança sem dado novo

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R3 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1866909415207705861` | Re: 4111_01/06/2026 | F→C | "Boa tarde Helder! Por gentileza enviar o anexo." | Finaud pediu dado, aguarda cliente |
| `GMTHRID_1866252965601334907` | CADOC 4111 DOS DIAS 21 a 25/05 - SEFER | F→C | "Alison, peço a gentileza de quando tiver a disponibilidade das informações referentes aos CADOCs..." | Finaud pediu dado, aguarda cliente |
| `GMTHRID_1865728381407797798` | CADOC's 4111 - BANVOX/TRUSTEE 12/05 a 18/05 | F→C | "Robson, peço à gentileza de quando tiver a disponibilidade os saldos para geração dos 4111." | Finaud pediu saldos, aguarda cliente |
| `GMTHRID_1858314533440741207` | VIS - ENVIAR POSIÇÃO DO DDR e 4111 - 24/02 a 26/02 | F→C | "Bruno, boa tarde! Por gentileza, encaminhar as posições do DDR e 4111, para enviar os arquivos de remessas." | Finaud pediu posições, aguarda cliente |
| `GMTHRID_1864281912422417990` | 4111 — Fair Corretora | F→C | "Boa tarde! Por gentileza enviar as informações para os relatórios 4111 de 28, 29 e 30/04/2026." | Finaud pediu informações, aguarda cliente |

---

#### Regra R4 — Aguardando/Finaud: Finaud acusou recebimento mas ainda não gerou nem entregou

**Quando dispara:**
- Última mensagem F→C com acuse curto ("Ok, obrigada pelo envio", "Obrigada. Administração") sem menção de entrega ou geração do arquivo
- Última mensagem F→C com aviso de problema técnico ("Estamos verificando com a área técnica... Retornaremos em breve")

**3 exemplos reais** (padrão raro no 4111 — apenas 3 casos confirmados; não foi possível atingir o mínimo de 5):

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R4 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1861906502436753705` | 4111 | C→F\|F→C | "Estamos verificando com a área técnica a ausência das contas cosifs mencionadas. Retornaremos em breve." | Finaud detectou problema — ainda não gerou |
| `GMTHRID_1855666758636095062` | Re: ENVIO POSIÇÃO CADOC 4111 - SSG — Smartsafe | C→F\|F→C | "Obrigada. Administração" | Finaud acusou recebimento — ainda não gerou o 4111 |
| `GMTHRID_1858563732967029516` | Re: VIS - ENVIAR POSIÇÃO DO DDR e 4111 - 24/02 a 26/02 | C→F\|F→C | "Bom dia Bruno. Ok, obrigada pelo envio." | Finaud acusou recebimento — ainda não gerou |

---

#### Regra R5 — Aguardando/Finaud: encaminhamento interno entre pessoas da Finaud

**Quando dispara:** última mensagem foi de uma pessoa da Finaud para outra (F→F) — sem comunicação direta com o cliente.

**0 exemplos reais encontrados no 4111** — nenhuma thread com padrão F→F foi identificada nos dados atuais (376 threads). A regra R5 está definida por completude (aplica-se nos CADOCs onde o padrão existe), mas pode não ocorrer no 4111. Para testes, usar dados sintéticos ou threads de outro CADOC como referência (ex.: DRL_2160 tem 2 casos — ver seção 12.3).

---

**Regra geral C→F como última mensagem (4111):**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Agradecimento puro ("Obrigada!", "Ok, recebido", "Perfeito") | **Concluído** | Finaud | Cliente confirmou recebimento — ciclo encerrado |
| Envio de arquivo de dados ou posições | **Aguardando** | Finaud | Finaud precisa processar e gerar o 4111 |
| Pergunta ou solicitação que exige resposta | **Aguardando** | Finaud | Finaud precisa responder |

---

**Quadro final 4111 — regras de negócio validadas (376 threads):**

| Regra | Lado | Motivo | Status | Aplica a |
|-------|------|--------|--------|----------|
| R1 | — | Finaud entregou o arquivo 4111 ao cliente | Concluído | DDR_2011, **4111** |
| R2 | Finaud | Cliente enviou dados — Finaud precisa processar e entregar | Aguardando | DDR_2011, **4111** |
| R3 | Cliente | Finaud enviou mensagem — aguarda ação do cliente | Aguardando | DDR_2011, **4111** |
| R4 | Finaud | Finaud acusou recebimento mas ainda não gerou nem entregou | Aguardando | DDR_2011, **4111** |
| R5 | Finaud | Encaminhamento interno entre pessoas da Finaud (F→F) | Aguardando | DDR_2011, **4111** |

**Conclusão da validação:** O fluxo do 4111 é idêntico ao DDR_2011 — cliente envia dados, Finaud gera e entrega o arquivo, cliente transmite ao BACEN. As regras R1–R5 criadas para o DDR se aplicam diretamente aqui, sem nenhuma regra adicional. A diferença está apenas no nome do relatório; a lógica de conclusão e pendência é a mesma.

---

**Validação pós-conclusão 4111 (passo 9 da metodologia):**

**Exemplos pós-conclusão 4111 (para testes):**

| Situação | threadId | Assunto | Última msg cliente | Resultado esperado |
|----------|----------|---------|-------------------|-------------------|
| Cliente agradeceu → mantém CO | `GMTHRID_1856295926479016558` | CADOC 4111 02/02/2026 | "Lucas, Obrigada pelo envio." | Mantém Concluído |
| Cliente agradeceu → mantém CO | `GMTHRID_1855667332910226144` | CADOC 4111 26/01/2026 | "Obrigada Lucas!" | Mantém Concluído |
| Cliente agradeceu → mantém CO | `GMTHRID_1864997669729496810` | Re: Relatório 4111 | "Ok As 15hrs te chamo Já fiz o DDR até 30 Grato" | Mantém Concluído |
| Cliente enviou dados → reabre | `GMTHRID_1864448541901865012` | 4111 DOS DIAS 30/04, 04/05 e 05/05 - SEFER | "Segue informação do dia 30/04, os demais serão enviados posteriormente." | Reabre → Aguardando/Finaud |
| Cliente enviou dados → reabre | `GMTHRID_1855053069023076589` | Re: Seguem as remessas 4111 17/12 a 21/12 GURU | "Segue também demais documentações que a Contabilidade disponibilizou junto com os CADOCs." | Reabre → Aguardando/Finaud |

> ⚠️ **3 threads com gap — precisam de backfill:**
> - `GMTHRID_1863635674448498641` ("4111 DIA 23/04") — está como **AGUARDANDO mas deveria ser CONCLUÍDO** (R1). Situação: cliente (Paulo Henrique, Planner) enviou "Bom dia!" avisando que precisa do 4111. Lucas (Finaud) respondeu: *"segue arquivo Cadoc 4111 da CV e SCD do dia 23/04/2026, para envio ao BACEN."* — Finaud gerou e entregou o arquivo ao cliente para transmissão ao BACEN. Motor deixou como AGUARDANDO porque a assinatura do Lucas termina com "Desde já agradeço e permaneço à disposição", e o motor interpretou essa frase como pedido pendente em vez de encerramento cortês.
> - `GMTHRID_1863352683346963259` ("4111 DIA 22/04") — **mesmo padrão acima**: Paulo envia "Bom dia", Lucas entrega o 4111 de 22/04 com a mesma frase de assinatura "Desde já agradeço e permaneço à disposição". Motor deixou como AGUARDANDO pelo mesmo motivo.
> - `GMTHRID_1863269706951173753` ("4111 DIA 20/04") — **mesmo padrão acima**: Paulo envia "Bom dia", Lucas entrega o 4111 de 20/04. Motor deixou como AGUARDANDO pelo mesmo motivo.
>
> Raiz comum dos 3: a frase de assinatura cortês "Desde já agradeço e permaneço à disposição" foi interpretada pelo motor como pedido ao cliente (contém "agradeço"), quando na verdade é encerramento padrão do Lucas após a entrega. A nova regra R1 corrigiria isso em threads novas; estas threads antigas precisam de backfill.

> ✅ **4111 — validação de regras de negócio concluída** (17/06/2026) — reutiliza R1/R2/R3/R4

---

### 12.3 — DRL_2160 — Demonstrativo de Risco de Liquidez

**O que é:** Relatório periódico de risco de liquidez. O cliente envia uma planilha Excel com os dados de exposição; a Finaud importa no sistema, calcula, gera o arquivo DRL e entrega ao cliente para transmissão ao BACEN.

**Fluxo padrão:**
1. Cliente envia planilha Excel com as exposições ao risco de liquidez para a Finaud
2. Finaud importa a planilha no sistema interno e realiza o cálculo
3. Finaud gera o arquivo DRL_2160
4. Finaud envia o arquivo DRL **em anexo** por e-mail ao cliente
5. Cliente transmite o arquivo ao BACEN
6. **Conclusão = Finaud enviou o arquivo ao cliente** — não é necessária confirmação de transmissão ao BACEN

> ⚠️ **Gap técnico:** a planilha Excel enviada pelo cliente chega como anexo — o motor detecta o envio pelo **texto** da mensagem ("segue planilha", "em anexo"). Se o cliente enviar a planilha sem escrever nenhuma dessas frases no corpo do e-mail, o motor pode não reconhecer e deixar a thread como AGUARDANDO indevidamente. Mesmo gap do DDR_2011.

**Total:** 143 threads (49 Aguardando · 89 Concluído · 5 ainda não triadas)

---

**Cobertura de padrões — DRL_2160 (total: 143 threads)**

| Padrão | Threads | % | Última mensagem | Regra | Status |
|--------|---------|---|-----------------|-------|--------|
| FC | 51 | 36% | F→C | R1 ou R3 | CO (entregou) ou AG (pediu planilha) |
| CF \| FC | 21 | 15% | F→C | R1 ou R4 | CO (entregou) ou AG (recebeu mas não gerou ainda) |
| CF | 21 | 15% | C→F | R1 ou R2 | CO (cliente confirmou/agradeceu) ou AG (cliente enviou planilha) |
| FC \| CF | 18 | 13% | C→F | R1 ou R2 | CO (agradecimento) ou AG (cliente entregou dados) |
| FC \| CF \| FC | 5 | 3% | F→C | R1 ou R4 | CO (entregou) ou AG (reconheceu sem entregar) |
| CF \| FC \| CF | 4 | 3% | C→F | R1 ou R2 | CO (cliente confirmou/agradeceu) ou AG (situação complexa) |
| FC \| FC | 4 | 3% | F→C | R1 ou R3 | CO (entregou/protocolo) ou AG (lembrete de prazo) |
| FF | 2 | 1% | F→F | R5 | AG (encaminhamento interno Finaud) |
| Outros longas (3+ raras) | 17 | 12% | variado | R1/R2/R3/R4 | mesma lógica geral |
| **Total** | **143** | **100%** | | | **✅ 100% coberto** |

> As regras R1–R5 cobrem 100% dos padrões do DRL_2160.

---

**Regras validadas para DRL_2160:**

---

#### Regra R1 — Concluído: Finaud entregou o arquivo ao cliente (ou ciclo confirmado)

**Quando dispara:**
- Última mensagem F→C com "segue anexo DRL", "segue arquivo DRL", "para envio ao BACEN", "para envio ao BC", "enviado ao STA", "protocolo do arquivo DRL"
- Qualquer mensagem com "transmitidos no BACEN", "submetido ao BACEN", "arquivo submetido" — sem nova demanda após
- Última mensagem C→F com agradecimento puro ("Obrigado Lucas!", "Obrigada pelo envio") — sem pedido, pergunta ou dado novo
- Última mensagem C→F com "Somente para que fiquem cientes, foi enviado" — comunicado administrativo, o cliente avisou que ele mesmo transmitiu

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R1 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1868178463637068071` | DRL2160_052026 — Fair Corretora | FC | "Segue anexo DRL2160_052026 para envio ao Banco Central." | Finaud entregou o arquivo |
| `GMTHRID_1867546403281020080` | DRL 2160 - 05/2026 - AMARIL FRANKLIN | CF\|FC | "Segue arquivo DRL - 2160 de 05/2026, para envio ao BACEN." | Finaud entregou o arquivo |
| `GMTHRID_1865082808941084767` | Guru CTVM: DRL (2160) Abr-Mai/26 | CF\|FC | "O arquivo de DRL de Abr.2026 foi enviado ao STA, estamos acompanhando o processamento." | Finaud transmitiu ao BACEN |
| `GMTHRID_1868086900928087877` | 2160 DRL 05/2026 — Banvox | CF\|FC\|CF | "Arquivo submetido ao BACEN na data de hoje." | Cliente confirmou submissão |
| `GMTHRID_1864917074493755714` | CORREÇÃO DRL 2160 - MARÇO — Planner | CF\|FC\|CF | "Obrigado Lucas!" | Agradecimento puro após entrega |
| `GMTHRID_1867636812789425353` | Guru CTVM: Colchão de Liquidez — DRL | FC\|FC | "segue em anexo o protocolo do arquivo DRL 2160, enviado e aceito pelo BACEN." | Finaud enviou protocolo de aceite |

---

#### Regra R2 — Aguardando/Finaud: cliente enviou dados ou mensagem — Finaud precisa agir

**Quando dispara:**
- Última mensagem C→F com planilha Excel ou base de dados ("Segue planilha DRL", "Segue a planilha do DRL 2160", "Anexo arquivo para gerar o DRL", "dados para reporte de DRL")
- Última mensagem C→F com pergunta ou situação que exige ação da Finaud ("Poderíamos agendar uma conversa sobre o preenchimento?", cliente descreve processo diferente)

> **Nota CF-C:** quando o cliente faz uma pergunta (C→F), a bola vai para a Finaud → é R2 (Aguardando/Finaud), não R3. R3 só dispara quando a última mensagem é F→C (Finaud falou por último e aguarda o cliente).

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R2 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1864650408778418416` | DRL abril — Global Exchange | CF | "Segue em anexo a base de dados para emissão do arquivo DRL de abril." | Cliente enviou planilha, Finaud precisa gerar |
| `GMTHRID_1864563833499178683` | DRL 2160 - Abril/2026 — Trinus CO | CF | "Segue a planilha do DRL 2160 referente ao mês Abril/2026." | Cliente enviou planilha, Finaud precisa gerar |
| `GMTHRID_1864921082626369043` | Guru CTVM: Colchão de Liquidez DRL | CF\|FC | "Segue em anexo planilha acessória para o CADOC 2160 (DRL)." + Finaud: "Ok, ciente." | Cliente enviou dado, Finaud acusou recebimento mas ainda não gerou o DRL |
| `GMTHRID_1864915714497795718` | Encaminhar planilha DRL (2160) 04/2026 — Acredito SCD | FC\|CF | Cliente enviou planilha após Finaud pedir | Finaud pediu, cliente entregou — Finaud precisa gerar |
| `GMTHRID_1859300848841365026` | TRADERS - SOLICITAÇÃO DO ARQUIVO - 2160 02/2026 | CF\|FC\|CF | "Anteriormente a Andrea havia pedido também a planilha do DRL mas nós não utilizamos nenhuma planilha para realizar a transmissão do 2160..." | Cliente descreveu processo diferente — Finaud precisa entender e resolver |

---

#### Regra R3 — Aguardando/Cliente: Finaud aguarda planilha ou ação do cliente

**Quando dispara:**
- Última mensagem F→C pedindo a planilha ("por gentileza, enviar a planilha para gerar o relatório DRL", "encaminhar a planilha DRL", "solicitamos por gentileza encaminhar a planilha DRL")
- Última mensagem F→C com lembrete de prazo ("Informo que hoje é o prazo para o envio de arquivo DRL")
- Última mensagem F→C com pedido de balancete ou documento específico ("por gentileza, enviar o balancete analítico em formato PDF")

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R3 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1868083512653622433` | DRL MAI/26 — Fair Corretora | FC | "Por gentileza, enviar a planilha para gerar o relatório DRL de maio/26." | Finaud pediu planilha, aguarda cliente |
| `GMTHRID_1868082821352776142` | DRL MAI/26 — Coluna DTVM | FC | "Por gentileza, enviar a planilha para gerar o relatório DRL de maio/26. Data de envio ao Banco Central 15/06/2026." | Finaud pediu planilha com prazo |
| `GMTHRID_1868079066360107919` | DRL ACTIVTRADES MAI/26 | FC | "Por gentileza, enviar o balancete analítico em formato PDF referente a MAIO de 2026. O documento é necessário para a composição do relatório DRL." | Finaud pediu balancete específico |
| `GMTHRID_1867824717402892291` | Encaminhar a planilha DRL maio/2026 — MIRAE | FC | "Solicitamos por gentileza encaminhar a planilha DRL com o preenchimento das exposições ao risco de liquidez 29/05/2026." | Finaud pediu planilha, aguarda cliente |
| `GMTHRID_1864926735439656214` | Encaminhar a planilha DRL Abril/2026 — Unicred | FC\|FC | "Informo que hoje é o prazo para o envio de arquivo DRL. Desde já agradecemos a atenção." | Finaud lembrou prazo — ainda aguarda planilha do cliente |

---

#### Regra R4 — Aguardando/Finaud: Finaud recebeu dado mas ainda não gerou nem entregou o DRL

**Quando dispara:**
- Última mensagem F→C com acuse de recebimento curto sem entrega ("Ok, ciente", "Obrigada pela informação", "Obrigada pelo envio. Att.") sem menção de transmissão ou envio do arquivo

> **Nota:** este é o sub-cenário do padrão CF|FC onde o motor atual classifica errado threads que na verdade já foram concluídas (ver gaps abaixo). R4 cobre só os casos onde a Finaud realmente ainda não gerou.

**2 exemplos reais** (padrão raro no DRL — apenas 2–3 casos confirmados no total; não foi possível atingir o mínimo de 5):

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R4 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1864921082626369043` | Guru CTVM: Colchão de Liquidez DRL | CF\|FC | "Ok, ciente." — Finaud apenas acusou recebimento | Cliente enviou planilha acessória; Finaud acusou mas ainda não gerou o DRL |
| `GMTHRID_1862460615056672042` | CVPAR - Encaminhar planilha DRL fev/2026 | FC\|FC | "RETIFICANDO... DRL (2160) referente ao mês de Março/2026." — Finaud corrigiu o mês na solicitação | Finaud ainda aguarda planilha do cliente; a 2ª mensagem é correção do mês, não entrega |

---

#### Regra R5 — Aguardando/Finaud: encaminhamento interno entre pessoas da Finaud

**Quando dispara:** última mensagem foi de uma pessoa da Finaud para outra (F→F) — não há comunicação direta com o cliente.

**Padrão raro no DRL_2160 (2 threads no total — mínimo de 5 não atingido):** ambas são e-mails internos sobre relatório gerencial da Ativa, classificados como DRL_2160 pelo script 05 pelo tema ("risco de liquidez"), mas sem fluxo com cliente. Ver nota de reclassificação na seção de gaps. Para quem for implementar: os 2 exemplos abaixo são os únicos casos reais disponíveis — tratar como padrão raro e testar com dados sintéticos se necessário.

---

**Regra geral C→F como última mensagem (DRL_2160):**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Agradecimento puro ("Obrigado Lucas!", "Ok, recebido", "Perfeito") | **Concluído** | Finaud | Cliente confirmou recebimento — ciclo encerrado |
| Envio de planilha Excel ou base de dados | **Aguardando** | Finaud | Finaud precisa importar, calcular e gerar o DRL |
| Pergunta ou solicitação ao cliente | **Aguardando** | Finaud | Finaud precisa responder |
| Cliente informou que já transmitiu ao BACEN | **Concluído** | Finaud | Ciclo completo — cliente confirmou transmissão |

---

**Quadro final DRL_2160 — regras de negócio validadas (143 threads)**

| Regra | Lado | Motivo | Status | Aplica a |
|-------|------|--------|--------|----------|
| R1 | — | Finaud entregou o arquivo DRL ao cliente (ou ciclo confirmado via transmissão ao BACEN) | Concluído | DRL_2160 |
| R2 | Finaud | Cliente enviou planilha ou mensagem — Finaud precisa gerar e entregar o DRL | Aguardando | DRL_2160 |
| R3 | Cliente | Finaud aguarda planilha ou documento do cliente | Aguardando | DRL_2160 |
| R4 | Finaud | Finaud recebeu dado mas ainda não gerou nem entregou o DRL | Aguardando | DRL_2160 |
| R5 | Finaud | Encaminhamento interno entre pessoas da Finaud — sem comunicação com cliente | Aguardando | DRL_2160 |

**Conclusão da validação:** O DRL_2160 segue fluxo idêntico ao DDR_2011 e ao 4111 — cliente envia dados, Finaud processa e entrega o arquivo, cliente transmite ao BACEN. Por isso as regras R1–R5 se aplicam diretamente sem necessidade de criar regras específicas para este CADOC. A única diferença prática é o insumo do cliente: no DDR são extratos (PDF/Excel/texto), no DRL é uma planilha estruturada de exposições ao risco de liquidez. O fluxo e os gatilhos de conclusão são os mesmos.

> ⚠️ **2 threads com gap — precisam de backfill (ver seção 13.10 — Grupo D):**
> - `GMTHRID_1862008503744710537` ("Envio 2160 DRL 02/2026") — AG mas deveria ser CO: cliente informou que ele mesmo transmitiu o DRL ao BACEN ("Somente para que fiquem cientes, foi enviado hoje..."), mas o motor não reconheceu como conclusão.
> - `GMTHRID_1868094930909531258` ("DRL Maio 2026" — CVD TVM) — AG mas deveria ser CO: Finaud disse explicitamente "Providenciamos o cálculo e a transmissão da remessa DRL (2160) 05/2026", mas o motor interpretou "qualquer dúvida retorne" no final da mensagem como pedido pendente.

**Validação pós-conclusão DRL_2160 (passo 9 da metodologia):**

> Das 89 threads Concluídas do DRL_2160, foram identificadas **24 que receberam mensagem nova** após o fechamento. O motor processou cada uma. Resultado:

| Situação | Qtd | Resultado |
|----------|-----|-----------|
| Thread ficou CO — cliente só agradeceu ou deu aviso sem demanda | 18 | ✅ Correto — manteve Concluído |
| Thread deveria ter reaberto mas ficou CO | 3 | ❌ Gap — precisam de backfill (Grupo E) |
| Thread reabriu corretamente (AG) | 3 | ✅ Correto — seção 14 funcionou |

**As regras da seção 14 cobrem todos os padrões — nenhuma regra nova foi necessária.**

**3 gaps encontrados (CO ficou mas deveria ter reaberto → ver backfill Grupo E):**

| threadId | Assunto | Última msg | Regra esperada | Problema |
|----------|---------|------------|----------------|---------|
| `GMTHRID_1856853424091223588` | Acredito SCD — DRL 01/2026 | Cliente enviou nova planilha para competência seguinte | R2 (AG/Finaud) | Motor manteve CO; cliente enviou planilha nova, Finaud precisa gerar novo DRL |
| `GMTHRID_1859470681749037009` | SANTS SCD — DRL 02/2026 | Finaud pediu planilha complementar | R3 (AG/Cliente) | Motor manteve CO; Finaud fez pedido ao cliente que ficou sem resposta |
| `GMTHRID_1865283663876735352` | Unicred — DRL 04/2026 | Finaud enviou acuse interno sem nova entrega | R4 (AG/Finaud) | Motor manteve CO; Finaud recebeu dado mas não entregou ainda |

> ⚠️ Estas 3 threads serão corrigidas no backfill (seção 13.10 — Grupo E).

**Exemplos de threads que ficaram CO corretamente (para testes do motor):**

| threadId | Assunto | Última msg cliente | Por que mantém CO |
|----------|---------|-------------------|-------------------|
| `GMTHRID_1864917074493755714` | CORREÇÃO DRL 2160 - MARÇO — Planner | "Obrigado Lucas!" | Agradecimento puro — sem nova demanda |
| `GMTHRID_1868086900928087877` | 2160 DRL 05/2026 — Banvox | "Arquivo submetido ao BACEN na data de hoje." | Comunicado de encerramento — ciclo finalizado |
| `GMTHRID_1865082808941084767` | Guru CTVM: DRL (2160) Abr-Mai/26 | "Ok, obrigada pelo envio." | Agradecimento puro — sem nova demanda |

> ✅ **DRL_2160 — validação de regras de negócio concluída** (17/06/2026) — reutiliza R1/R2/R3/R4

---

### 12.4 — DLI_2062 — Demonstrativo de Limites de Investimento

**O que é:** Relatório periódico de limites de investimento. O cliente envia o arquivo COSIF (XML — balanço no formato BACEN) e a Finaud importa no sistema, calcula e gera o arquivo DLI para o cliente transmitir ao BACEN. O mesmo COSIF também serve para gerar o DLO (ver seção 12.5).

**Fluxo padrão:**
1. Cliente envia o arquivo COSIF (XML) — balanço contábil no formato exigido pelo BACEN
2. Finaud importa o COSIF no sistema interno (Risk Driver) e realiza o cálculo
3. Finaud gera o arquivo DLI_2062
4. Finaud envia o arquivo DLI **em anexo** por e-mail ao cliente
5a. Cliente transmite o arquivo ao BACEN (fluxo padrão), **ou**
5b. Finaud transmite diretamente ao BACEN em nome do cliente (serviço adicional contratado — ver sub-caso R1 abaixo)
6. **Conclusão = Finaud entregou o arquivo ao cliente ou Finaud transmitiu ao BACEN**

> ⚠️ **Gap técnico:** o motor detecta a entrega do DLI pelo **texto** da mensagem ("segue anexo a remessa DLI", "seguem anexos DLIs 2062"). Se a Finaud entregar sem escrever essas frases, a thread pode ficar como AGUARDANDO indevidamente. Mesmo gap do DDR/4111/DRL.

> 📌 **Nota — clientes S5:** quando o cliente é classificado como S5 (menor porte), o DLI é calculado automaticamente pelo próprio BACEN com base no COS4010 — a Finaud não gera o arquivo. Threads S5 sobre DLI_2062 são de caráter consultivo/informativo e não seguem o fluxo padrão acima.

**Total:** 56 threads triadas (17 Aguardando · 39 Concluído) + 2 não triadas

---

**Cobertura de padrões — DLI_2062 (total: 56 triadas)**

| Padrão | Threads | % | Última mensagem | Regra | Status |
|--------|---------|---|-----------------|-------|--------|
| F→C | 19 | 34% | F→C | R1, R3, R4 ou R5 | CO (entregou/orientou) ou AG (pediu COSIF, etapa interna, ou F→F) |
| C→F \| F→C | 9 | 16% | F→C | R1 ou R4 | CO (entregou) ou AG (acusou sem entregar ainda) |
| F→C \| C→F | 7 | 13% | C→F | R2 ou R1 | AG (cliente enviou COSIF) ou CO (cliente agradeceu/confirmou STA) |
| F→C \| C→F \| F→C | 5 | 9% | F→C | R1 ou R4 | CO (entregou) ou AG (etapa interna) |
| C→F \| F→C \| C→F \| F→C | 5 | 9% | F→C | R1 | CO (entregou na última troca) |
| C→F | 4 | 7% | C→F | R2 ou fora do fluxo | AG (cliente enviou COSIF/pergunta) ou threads de ruído |
| Longas e raras | 7 | 12% | variado | R1/R2/R3/R4 | mesma lógica geral |
| **Total** | **56** | **100%** | | | **✅ 100% coberto** |

---

**Regras validadas para DLI_2062:**

---

#### Regra R1 — Concluído: Finaud entregou o arquivo DLI ou transmitiu ao BACEN

**Quando dispara:**
- Última mensagem F→C com "segue anexo a remessa DLI (2062)", "seguem anexos DLIs 2062", "segue relatório DLI 2062", "para envio ao BC", "para envio ao BACEN"
- Última mensagem F→C com envio de protocolo de aceite do BACEN ("seguem os protocolos dos arquivos enviados e aceitos pelo BACEN... DLI")
- Última mensagem F→C com orientação concluída (pergunta do cliente respondida, conceito explicado, dúvida solucionada) — sem nova demanda
- **Sub-caso — Finaud envia ao BACEN em nome do cliente:** Finaud transmite o arquivo diretamente ao BACEN (serviço adicional contratado). A conclusão ocorre quando Finaud confirma o envio ou envia os protocolos de aceite. *Este sub-caso também se aplica ao DDR_2011, 4111 e DRL_2160 — ver nota no quadro final.*

**6 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R1 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1855569908535276971` | Segue a remessa DLI (2062) 12/2025 — MIRAE | F→C | "Segue anexo a remessa DLI (2062) 12/2025. À disposição." | Finaud entregou a remessa DLI |
| `GMTHRID_1856384184122505207` | Confecção do DLI — Trustee/Banvox | F→C | "Segue anexo DLI 2062_12/2025 para envio ao BC." | Finaud entregou o arquivo DLI |
| `GMTHRID_1856609518747185978` | DLI 2062 - DEZEMBRO CV/SCD | F→C | "Seguem anexos DLIs 2062_12/2025 da CV/SCD para envio ao BC." | Finaud entregou múltiplos arquivos |
| `GMTHRID_1857921955423620769` | Re: DLI DEZEMBRO — substituição | F→C\|C→F\|F→C | "seguem os relatórios DLI's da CV/SCD de 12/2025, gerados como substituição para envio ao BACEN." | Finaud entregou arquivo de substituição |
| `GMTHRID_1855417266875173645` | CADOCS - DEZEMBRO-25 — Wise | C→F\|F→C\|C→F\|F→C | "seguem os protocolos dos arquivos enviados e aceitos pelo BACEN (DLO e DLI inclusão)." | Finaud transmitiu e enviou protocolo de aceite |
| `GMTHRID_1859570123269225576` | RE: DLI 2062 DA CV/SCD - JAN 2026 | C→F\|F→C | "Seguem anexos DLIs 2062_01/2026 da CV/SCD para envio ao BC." | Finaud entregou após receber o COSIF |

---

#### Regra R2 — Aguardando/Finaud: cliente enviou COSIF ou trouxe questão — Finaud precisa agir

**Quando dispara:**
- Última mensagem C→F com envio do COSIF (XML) ou arquivo de dados ("segue novamente", "segue arquivo retificado", "por favor pode gerar o 2062 também")
- Última mensagem C→F com questionamento do BACEN repassado ao cliente e que a Finaud precisa responder
- Última mensagem C→F com aviso de rejeição pelo BACEN ("Enviei e deu rejeitado") — Finaud precisa investigar e regerar

**5 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R2 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1858757143235504290` | Re: COS 4010 01/2026 — MIRAE | F→C\|C→F | "Mandei o e-mail ontem, porém segue novamente." | Cliente reenviou o COSIF — Finaud precisa processar e gerar o DLI |
| `GMTHRID_1859316863939653428` | Questionamento BACEN — Galápagos | C→F | "Recebemos o questionamento do BACEN... vocês fizeram alguma mudança no relatório 2062?" | Cliente repassou questionamento do BACEN — Finaud precisa investigar e responder |
| `GMTHRID_1861828137603892343` | Preencher as premissas DLI 02/2026 — Accredito | F→C\|C→F | "Segue arquivo retificado. Por favor pode gerar o 2062 também." | Cliente enviou arquivo corrigido pedindo geração do DLI |
| `GMTHRID_1868180969240092640` | 2062 | C→F\|F→C\|C→F\|F→C\|C→F | "Enviei e deu rejeitado" | Cliente avisou rejeição no BACEN — Finaud precisa investigar e regerar |
| `GMTHRID_1860455441246052135` | ENC: DLI(2062) gerado para essa instituição — ARC | C→F\|F→C\|C→F | "Bom dia, 1. 19/02/2026. 2. Pedi via suporte@finaud.com.br, duas vezes." | Cliente com dúvida sobre S5 — Finaud explicou mas cliente seguiu com perguntas adicionais sem resposta |

---

#### Regra R3 — Aguardando/Cliente: Finaud pediu COSIF ou aguarda ação do cliente

**Quando dispara:**
- Última mensagem F→C solicitando o arquivo COSIF XML ("por gentileza enviar os arquivos COS4010.xml para conseguirmos fazer a importação")
- Última mensagem F→C pedindo informação complementar do cliente ("poderia nos repassar a mensagem da crítica mencionada?")

**2 exemplos reais** (padrão raro no DLI_2062 — apenas 2 casos confirmados; não foi possível atingir o mínimo de 5. Os demais threads AG com última msg FINAUD são R4 ou R5):

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R3 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1867635451918730952` | ATUAL CORRETORA - 2062 RF MAR/ABR | C→F\|F→C | "Solicitamos por gentileza enviar os arquivos COS4010.xml para conseguirmos fazer a importação da nova versão ao sistema." | Finaud pediu o COSIF XML — aguarda o cliente enviar |
| `GMTHRID_1866796947655397903` | 2062 Março — Atual Corretora | C→F\|F→C | "Poderia nos repassar a mensagem da crítica mencionada para que possamos verificar?" | Finaud pediu a mensagem de crítica do BACEN — aguarda o cliente |

---

#### Regra R4 — Aguardando/Finaud: etapa interna pendente — Finaud ainda não entregou

**Quando dispara:**
- Última mensagem F→C informando que equipe técnica/desenvolvimento está trabalhando na solução ("equipe técnica está providenciando os ajustes, retornaremos em breve", "já iniciamos o desenvolvimento, cronograma segue conforme planejado")
- Última mensagem F→C com acuse de recebimento sem entrega do arquivo ("Ok, ciente", "Obrigada, vamos verificar")

**2 exemplos reais** (padrão raro no DLI_2062):

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R4 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1867164499973336595` | Atualização 2062 — Fourtrade | C→F\|F→C | "a equipe técnica está providenciando os ajustes. Retornaremos em breve." | Solução interna em andamento — Finaud não entregou ainda |
| `GMTHRID_1862663346101896376` | Re: IN 721/26 - DLI 2062 — Unicred | F→C\|C→F\|F→C | "após a finalização da especificação, já iniciamos o desenvolvimento. O cronograma segue conforme planejado." | Desenvolvimento em andamento — Finaud aguarda conclusão interna para entregar |

---

#### Regra R5 — Aguardando/Finaud: encaminhamento interno entre pessoas da Finaud

**Quando dispara:** última mensagem foi de uma pessoa da Finaud para outra (F→F) — sem comunicação direta com o cliente. Aparece no DLI quando uma instrução normativa, dúvida urgente ou alerta é encaminhado internamente para que a equipe responsável tome a ação.

**3 exemplos reais:**

| threadId | Assunto | Padrão msgs | Trecho da última mensagem | Por que R5 |
|----------|---------|-------------|--------------------------|------------|
| `GMTHRID_1861378682665141823` | Nova Instrução Normativa BCB nº 721 | F→C | "Ao Suporte Finaud — Para conhecimento, publicada agora a pouco a Instrução Normativa BCB Nº 721 que altera o DLI..." | Finaud encaminhou alerta interno — aguarda tratativa interna |
| `GMTHRID_1861735860734352099` | Fwd: Dúvida - Cálculo DLI 02/2026 - Urgente! | F→C | "@Rodrigo Tiberio consegue verificar como está a solução do caso abaixo? O cliente aguarda posicionamento." | Finaud encaminhou dúvida urgente do cliente para colega interno |
| `GMTHRID_1866799408130019732` | 2062 | C→F\|F→C\|C→F\|F→C\|C→F\|F→C | "Andrea este é outro email que recebi da atual. Por favor veja" | Finaud encaminhou e-mail do cliente para Andrea (colega interna) |

---

**Regra geral C→F como última mensagem (DLI_2062):**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Agradecimento puro ("Obrigado!", "Ok, recebido") | **Concluído** | Finaud | Cliente confirmou recebimento — ciclo encerrado |
| Envio do arquivo COSIF (XML) ou dado solicitado | **Aguardando** | Finaud | Finaud precisa importar, calcular e gerar o DLI |
| Questionamento do BACEN repassado | **Aguardando** | Finaud | Finaud precisa investigar e responder |
| Cliente confirmou envio ao STA (sistema do BACEN) | **Concluído** | Finaud | Ciclo completo — cliente transmitiu ao BACEN |
| Aviso de rejeição pelo BACEN | **Aguardando** | Finaud | Finaud precisa investigar causa e regerar o arquivo |

---

**Quadro final DLI_2062 — regras de negócio validadas (56 threads)**

| Regra | Lado | Motivo | Status | Aplica a |
|-------|------|--------|--------|----------|
| R1 | — | Finaud entregou o arquivo DLI ao cliente (ou transmitiu ao BACEN em nome do cliente) | Concluído | DLI_2062 |
| R2 | Finaud | Cliente enviou COSIF ou trouxe questão — Finaud precisa processar e responder | Aguardando | DLI_2062 |
| R3 | Cliente | Finaud aguarda COSIF ou informação do cliente | Aguardando | DLI_2062 |
| R4 | Finaud | Etapa interna pendente — equipe técnica/desenvolvimento trabalhando | Aguardando | DLI_2062 |
| R5 | Finaud | Encaminhamento interno entre pessoas da Finaud | Aguardando | DLI_2062 |

> 📌 **Sub-caso R1 — Finaud envia ao BACEN em nome do cliente:** quando a Finaud transmite o arquivo diretamente ao BACEN (serviço adicional contratado), a conclusão é marcada quando Finaud confirma o envio ou envia os protocolos de aceite. **Este sub-caso também se aplica ao DDR_2011, 4111 e DRL_2160** — nesses CADOCs o motor deve reconhecer "protocolos enviados e aceitos pelo BACEN" como R1 concluído, mesmo quando Finaud foi quem transmitiu.

**Conclusão da validação:** O DLI_2062 segue o mesmo fluxo do DDR/4111/DRL — cliente envia dados, Finaud processa e entrega o arquivo. A diferença está no insumo (COSIF XML em vez de planilha ou extrato) e no fato de que o mesmo COSIF serve para gerar tanto o DLI quanto o DLO na mesma conversa. As regras R1–R5 se aplicam diretamente, com a adição do sub-caso R1 de transmissão direta ao BACEN.

> ⚠️ **2 threads com gap — precisam de backfill (ver seção 13.10 — Grupo F):**
> - `GMTHRID_1861931178448315920` ("Re: Segue a remessa DLI 02/2026 — Accredito") — AG mas deveria ser CO (R1): cliente disse explicitamente "Já foi enviado no STA" — transmitiu ao BACEN, ciclo encerrado. Motor não reconheceu "STA" como confirmação de envio.
> - `GMTHRID_1861746610681231923` ("DLI 2062 - FEVEREIRO — Planner") — AG mas deveria ser CO (R1): Finaud informou ao cliente "peço à gentileza de desconsiderar essa solicitação, eu já havia encaminhado os dois DLI's de Fev anteriormente em 30/03, conforme anexo." — Finaud já tinha entregado o arquivo; motor não reconheceu essa mensagem como encerramento.

> ✅ **DLI_2062 — validação de regras de negócio concluída** (17/06/2026)

---

**Validação pós-conclusão DLI_2062 (passo 9 da metodologia):**

Analisadas **14 threads CO do DLI_2062** que receberam mensagem nova após o fechamento:

| threadId | Assunto | Últ. msg | Status motor | Correto? |
|----------|---------|----------|-------------|---------|
| `GMTHRID_1855417266875173645` | CADOCS DEZEMBRO-25 | FINAUD: "seguem os protocolos dos arquivos enviados e aceitos pelo BACEN" | CO | ✅ R1 — protocolo entregue |
| `GMTHRID_1857677212096008336` | CADOCS JANEIRO-26 | FINAUD: "seguem os protocolos enviados e aceitos pelo BACEN, DLO e DLI" | CO | ✅ R1 |
| `GMTHRID_1857921955423620769` | Re: DLI DEZEMBRO substituição | FINAUD: entregou DLIs de substituição | CO | ✅ R1 |
| `GMTHRID_1859907602542075435` | DLI 2062 | CLIENTE: "Obrigado!" | CO | ✅ agradecimento puro |
| `GMTHRID_1861368614875663440` | Re: Dúvida Cálculo DLI | FINAUD: "foi solucionado o ajuste sistêmico" | CO | ✅ R1 — issue resolvida |
| `GMTHRID_1861754101780701474` | DLI 2062 BANVOX E TRUSTEE Fev | CLIENTE: "enviei novamente o da Banvox com o login Banvox" | CO | ❌ **GAP** — insumo novo, deveria reabrir |
| `GMTHRID_1861852016706348990` | Adequação Capital Activtrades | CLIENTE: "Obrigado, por todo apoio" | CO | ✅ agradecimento |
| `GMTHRID_1863656498156550674` | Alteração Limites | FINAUD: "O novo DLI entrará em vigor a partir de julho/2026" | CO | ✅ R1 — orientação concluída |
| `GMTHRID_1863754856686816497` | Cadocs Março2026 | FINAUD: "DLI 2062_03/2026 já estão disponíveis na tela DLI > Relatório" | CO | ✅ R1 — entregue via sistema |
| `GMTHRID_1866363058057387066` | Aviso Bacen DLI | FINAUD: "ajustes sistêmicos contas DLIs 20.90.00 concluídos" | CO | ✅ R1 |
| `GMTHRID_1866824820806433471` | [Urgente] DLI 2062 04/26 | FINAUD: "parametrizações da conta 20.90.00 já estão disponíveis" | CO | ✅ R1 |
| `GMTHRID_1867190072867078838` | DLI ABRIL 2062 | FINAUD: "correções da conta 20.90.00 foram realizadas" | CO | ✅ R1 |
| `GMTHRID_1867616743781782446` | Re: Alerta DLI 2062 | FINAUD: "ajustes sistêmicos concluídos" | CO | ✅ R1 |
| `GMTHRID_1867730689288797690` | teste 2062 | FINAUD: "ajustes sistêmicos concluídos" | CO | ✅ R1 |

**Resultado: 13 corretos ✅ · 1 gap ❌ → ver Grupo G no backfill (seção 13.10)**

> ⚠️ **1 thread com gap — precisa de backfill (ver seção 13.10 — Grupo G):**
> - `GMTHRID_1861754101780701474` ("DLI 2062 BANVOX E TRUSTEE Fev") — CO mas deveria ser AG (R2): cliente enviou novamente o arquivo da Banvox com o login correto — insumo novo chegou, Finaud precisa processar e gerar o DLI. Motor manteve CO porque a carga anterior fechou a thread e a nova mensagem não foi reavaliada.

> ✅ **Seção 14 cobre todos os casos encontrados** — as 13 threads corretas se enquadram nas situações 1, 2 e 3 do quadro de regras pós-conclusão. O gap `GMTHRID_1861754101780701474` é o caso 2 (cliente trouxe nova demanda) que o motor não detectou.

---

### 12.5 — DLO_2061

**O que é:** Demonstrativo de Limites Operacionais. Para gerá-lo, a Finaud precisa de dois arquivos do cliente: o COSIF (XML — mesmo do DLI) e a planilha LEC (Excel com exposições por contraparte). A Finaud importa os dois no sistema, calcula e gera o arquivo DLO, que o cliente transmite ao BACEN (ou a própria Finaud transmite, dependendo do contrato).

**Fluxo padrão:**
1. Cliente envia o COSIF (XML — COS4010 ou 4016) e a planilha LEC (Excel) para a Finaud
2. Finaud importa os dois arquivos no sistema e efetua os cálculos
3. Finaud gera o arquivo DLO_2061
4. Finaud envia o arquivo ao cliente (ou, em casos de serviço adicional, transmite diretamente ao BACEN)
5a. Se Finaud enviou ao cliente: **Conclusão = Finaud entregou o arquivo**
5b. Se Finaud transmitiu ao BACEN: **Conclusão = protocolo de aceite recebido**

> ⚠️ **Gap técnico:** o motor detecta a entrega do DLO pelo texto da mensagem. Se a Finaud entregar sem mencionar "segue em anexo" ou "DLO", a thread pode ficar AGUARDANDO indevidamente. Diferença específica do DLO em relação ao DLI: o insumo são **dois arquivos** (COSIF + LEC) — o motor não distingue se está aguardando um ou os dois.

**Total:** 499 threads (295 Aguardando · 187 Concluídas · 17 não triadas)

---

**Cobertura de padrões — DLO_2061 (482 triadas):**

| Padrão | Qtd | % | AG | CO | Última msg | Regras |
|--------|-----|---|----|----|------------|--------|
| 1 — Só C→F | 207 | 43% | 198 | 9 | CLIENTE | R2 / R1 (aviso transmissão) |
| 2 — Só F→C | 107 | 22% | 28 | 79 | FINAUD | R3/R4 (AG) · R1 (CO) |
| 3 — C→F → F→C | 40 | 8% | 17 | 23 | FINAUD | R4 (AG) · R1 (CO) |
| 4 — F→C → C→F | 32 | 7% | 15 | 17 | CLIENTE | R2 (AG) · R1 (CO) |
| 5 — C→F → F→C → C→F | 22 | 5% | 12 | 10 | CLIENTE | R2 (AG) · R1 (CO) |
| 6 — longas terminando F→C | 25 | 5% | 8 | 17 | FINAUD | R3/R4 (AG) · R1 (CO) |
| 7 — longas (5+ alternâncias) | 49 | 10% | 17 | 32 | variado | mesma regra geral |
| **Total** | **482** | **100%** | **295** | **187** | | ✅ 100% coberto |

> **Nota:** F→F = 0 no DLO_2061. A Regra R5 não se aplica a este CADOC.

---

**Regras validadas para DLO_2061:**

#### Regra R1 — Concluído / Finaud entregou ou confirmou a tarefa

**Quando dispara:**
- Última mensagem F→C com entrega do arquivo DLO ("Segue anexo DLO 2061", "seguem arquivos para envio ao BC")
- Última mensagem F→C com confirmação de transmissão ao BACEN ("foram aceitos no STA", "segue o protocolo")
- Última mensagem F→C com resolução de dúvida técnica ou instrução completa sem pedido pendente
- Última mensagem C→F com agradecimento puro ("Obrigado", "Transmitido", "Deu certo") — sem nova demanda
- Última mensagem C→F com aviso de transmissão ao BACEN ("Transmitido os DLO e DLI referente a ABRIL de 2026")
- Recall de mensagem (M30) — motor classifica automaticamente como CO
- Sub-caso: Finaud transmite o DLO diretamente ao BACEN em nome do cliente (serviço adicional) — protocolo de aceite = R1

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1867181780701474900` | DLO/DLI abril/2026 | FINAUD: "Seguem anexos para envio ao Banco Central: DLO2061_042026; DLI2062_042026; DRM2060_042026" |
| `GMTHRID_1864364029722231114` | CVPAR — COS4010 03/2026 | FINAUD: "Já fiz as alterações do arquivo no sistema. Segue os protocolos dos envios, DLO e DLI." |
| `GMTHRID_1856029200452502052` | DLO's rejeitado no STA/BC | FINAUD: "os arquivos de remessa 2061/DLO dos clientes UNICRED e FENIX foram aceitos no STA" |
| `GMTHRID_1864458368512457575` | DLO 2061 CONGLOMERADO MAR/2026 | CLIENTE: "Arquivos submetidos ao BACEN hoje 06/05/2026." |
| `GMTHRID_1859300457052772113` | DLO/DLI de janeiro de 2026 | CLIENTE: "Muito obrigado Flavio. Transmitido" |

---

#### Regra R2 — Aguardando/Finaud / cliente enviou COSIF, LEC ou dados

**Quando dispara:**
- Última mensagem C→F com envio do COSIF ("Segue em anexo os dados para geração do DLO e DLI", "Segue o COS4010")
- Última mensagem C→F com envio da planilha LEC ("Segue em anexo a planilha LEC")
- Última mensagem C→F com envio de ambos (COSIF + LEC) juntos
- Última mensagem C→F com dados complementares ou corrigidos após inconsistência
- Última mensagem C→F com nova demanda após ciclo anterior concluído (pergunta técnica, cobrança, nova pendência)

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1858020621532776119` | DLO JANEIRO — Global Exchange | CLIENTE: "Segue em anexo os dados para geração dos arquivos DLO e DLI de janeiro." |
| `GMTHRID_1858571620819240423` | Encaminhar COS4010 01/2026 | CLIENTE: "Boa tarde. Segue informações solicitadas" |
| `GMTHRID_1864282658559882266` | DLO/DLI março/2026 | CLIENTE: "Boa tarde, Segue em anexo, abs." |
| `GMTHRID_1861936099714327819` | Cos4010 02.2026 — Conecta | CLIENTE: "Segue o arquivo correto" (COSIF corrigido após inconsistência) |
| `GMTHRID_1858108538964463383` | VIS — COSIF 4010 e LEC JAN/2026 | CLIENTE: "Segue em anexo documentos solicitados." (COSIF + LEC) |

---

#### Regra R3 — Aguardando/Cliente / Finaud aguarda COSIF, LEC ou ação do cliente

**Quando dispara:**
- Última mensagem F→C pedindo o COSIF ("Por gentileza encaminhar o COS4010 e a planilha LEC")
- Última mensagem F→C pedindo apenas a planilha LEC
- Última mensagem F→C pedindo dados adicionais para cálculo (composição de operações, quantidade de moedas)
- Última mensagem F→C com pergunta técnica aguardando resposta do cliente

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1858738059439395844` | DLO janeiro/26 | FINAUD: "Por gentileza, encaminhar o COS, o LEC e a quantidade de moedas referentes ao DLO de janeiro/2026" |
| `GMTHRID_1855406393176330685` | Encaminhar COS4010 e 4016 12/2025 | FINAUD: "Solicitamos por gentileza encaminhar o COS4010 e 4016 12/2025. Encaminhar a planilha LEC com o preenchimento das exposições por contraparte" |
| `GMTHRID_1861750420795100521` | DLO 2061 e DLI 2062 — COSIFs Fev | FINAUD: "peço à gentileza de encaminhar os COSIFs para que eu possa gerar os relatórios e submeter os arquivos" |
| `GMTHRID_1861362524352390693` | Atual Corretora — Balancete 02/26 | FINAUD: "Solicitamos por gentileza encaminhar a planilha LEC fev/2026." |
| `GMTHRID_1856927832030504635` | Remessa Demonstrações à B3 | FINAUD: "fico aguardando apenas o mês referência de Dezembro." |

---

#### Regra R4 — Aguardando/Finaud / etapa interna pendente

**Quando dispara:**
- Última mensagem F→C com acuse de recebimento sem entrega ("Obrigada pelas informações", "Ok, obrigada", "Ok, ciente")
- Última mensagem F→C com "estarei providenciando", "estamos providenciando", "vou verificar internamente"
- Última mensagem F→C com atualização de progresso interno sem entrega do arquivo ("atualizações sistêmicas estão avançando")
- Última mensagem F→C com compromisso de entrega futura ("prazo de entrega até segunda-feira")

**Exemplos reais:**

| threadId | Assunto | Última msg (trecho) |
|----------|---------|---------------------|
| `GMTHRID_1860022695059984415` | Guru CTVM: 4010 fevereiro/26 | FINAUD: "Boa tarde Guilherme. Obrigada pelas informações." |
| `GMTHRID_1864261208106191045` | COS4010 e 4016 12.2025 Retificado | FINAUD: "Ok, estarei providenciando o processamento deste relatório." |
| `GMTHRID_1854409300337300121` | REMITLY CC — 4010 12/2025 | FINAUD: "Prezado Hebert, boa tarde. Obrigada." |
| `GMTHRID_1866805258770316124` | VIS (Fenix) COS 4010/LEC Abril/2026 | FINAUD: "Ok, obrigada." |
| `GMTHRID_1860474781057506300` | Cálculo Patrimônio de referência fev/26 | FINAUD: "recebemos internamente a informação de que os trabalhos referente às atualizações sistêmicas estão avançando" |

---

#### Regra R5 — Não se aplica ao DLO_2061

> **F→F = 0** — nenhuma thread do DLO_2061 tem padrão F→F. A Regra R5 não existe neste CADOC. Para referência do padrão R5, ver DRL_2160 (seção 12.3).

---

**Regra geral C→F como última mensagem — DLO_2061:**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Envio de COSIF, LEC ou dados para cálculo | **Aguardando** | Finaud | Finaud precisa importar e gerar o DLO |
| Dados corrigidos ou complementares | **Aguardando** | Finaud | Finaud precisa reprocessar |
| Agradecimento puro ("obrigado", "deu certo") | **Concluído** | — | Ciclo encerrado |
| Confirmação de transmissão ao BACEN | **Concluído** | — | Ciclo encerrado |
| Nova demanda ou cobrança após ciclo anterior | **Aguardando** | Finaud | Nova pendência aberta |
| Aviso de recall ("would like to recall") | **Concluído** | — | Motor aplica M30 automaticamente |

---

**Quadro final DLO_2061 — regras de negócio validadas:**

| Regra | Lado (Responsável) | Motivo | Status | Aplica a |
|-------|--------------------|--------|--------|----------|
| R1 | — | Finaud entregou o DLO / cliente confirmou transmissão ao BACEN | Concluído | DLO_2061 |
| R2 | Finaud | Cliente enviou COSIF e/ou LEC — Finaud precisa processar e gerar o DLO | Aguardando | DLO_2061 |
| R3 | Cliente | Finaud aguarda COSIF, LEC ou dados adicionais do cliente | Aguardando | DLO_2061 |
| R4 | Finaud | Finaud acusou recebimento mas ainda não gerou nem entregou o DLO | Aguardando | DLO_2061 |
| R5 | — | **Não se aplica** — F→F = 0 no DLO_2061 | — | — |

---

**Conclusão da validação DLO_2061:**

O DLO_2061 segue a mesma lógica dos CADOCs anteriores, com uma diferença: exige **dois insumos** do cliente (COSIF + planilha LEC). Isso cria um sub-cenário no R2 onde a thread pode estar aguardando só o LEC, só o COSIF, ou os dois — o motor não distingue, mas o status AG/Finaud está correto em todos os casos. A Regra R5 não existe neste CADOC (nenhuma thread F→F identificada). Os 12 gaps encontrados são todos explicáveis pelos mesmos padrões dos CADOCs anteriores: motor não detectou reabertura (CO→AG) ou não detectou conclusão (AG→CO).

> ⚠️ **12 threads com gap — precisam de backfill (ver seção 13.10 — Grupo I):**
> - 8 CO→AG: threads que deveriam ter reaberto mas o motor manteve como Concluído
> - 4 AG→CO: threads que deveriam estar Concluídas mas o motor manteve como Aguardando

> ✅ **DLO_2061 — validação de regras de negócio concluída** (17/06/2026)

---

**Validação pós-conclusão DLO_2061 (passo 9 da metodologia):**

Analisadas **63 threads CO do DLO_2061** que receberam mensagem nova após o fechamento:

- **37 FINAUD-last** → todas ✅ corretas. Padrão dominante: Finaud entregou DLO, resolveu rejeição no BACEN, respondeu dúvida técnica. Todas R1.
- **26 CLIENTE-last** → analisadas individualmente:
  - **17 ✅ CO correto** — agradecimentos ("Obrigado Flavio", "Obrigada Andrea"), confirmações de transmissão ao BACEN ("Transmitido", "Arquivo enviado na data de hoje"), e 1 caso de retransmissão ao BACEN que é ação do cliente (não gap — Finaud já entregou o arquivo, STA rejeitou por issue sistêmica resolvida).
  - **8 ❌ gaps** (CO→AG) — cliente enviou dado novo ou fez pergunta pendente:

| threadId | Assunto | Última msg cliente | Tipo |
|----------|---------|-------------------|------|
| `GMTHRID_1856111714890581464` | 2061 — Dezembro/2025 | "você já teria o arquivo DLO 2061 data base janeiro/2026 para disponibilização?" | R2 — novo DLO solicitado |
| `GMTHRID_1856408737013732330` | DLO DEZEMBRO | "Reportado no email anterior a diferença de saldos" | R2 — divergência reportada |
| `GMTHRID_1858203923135580542` | DLO2061_112025 | "Em anexo." (enviou arquivo) | R2 — insumo novo |
| `GMTHRID_1860102608903227103` | Atual Corretora Balancete 02/26 | "saber se houve alguma modificação no DLO 12/2025 ou se ele pode considerar essa no anexo" | R2 — pergunta pendente |
| `GMTHRID_1860114244405598047` | DLO DEZ/25 RETIFICADO | "poderia verificar os apontamentos no CRD? Questionamentos sobre linhas de PR" | R2 — questionamento pendente |
| `GMTHRID_1861092985889898377` | DLO — FEVEREIRO | Planilha com dados de contas (#N/D — valores divergentes) | R2 — dados com inconsistência |
| `GMTHRID_1861742126361244073` | DLO2061_022026 | "Ainda estou com Rejeição dos arquivos 2061 de 01/2026 e 02/2026. Poderia me ajudar?" | R2 — rejeição persistente |
| `GMTHRID_1864358230808265625` | Relatórios DLO e DLI 03/2026 | "Seguem 4010 e planilha LEC, conforme solicitado. Fico no aguardo dos arquivos." | R2 — enviou COSIF+LEC, aguarda DLO |
| `GMTHRID_1865537776549234179` | Guru CTVM Balancete 04/2026 | "segue o CADOC 4010. Nessa transição você acabou ficando de fora." | R2 — enviou COSIF 4010 |

**Resultado: 55 corretos ✅ · 8 gaps ❌ → ver Grupo J no backfill (seção 13.10)**

> ⚠️ **8 threads com gap — precisam de backfill (ver seção 13.10 — Grupo J):** todas são CO→AG. Motor manteve como Concluído mas cliente trouxe nova demanda ou enviou insumo após o fechamento.

> ✅ **Seção 14 cobre todos os casos encontrados.** Os 8 gaps se enquadram na situação 2 do quadro (cliente trouxe nova demanda). Não há situação nova fora do quadro.

---

### 12.6 — DRM_2060 — Demonstrativo de Risco de Mercado

**O que é:** Relatório **mensal** de risco de mercado. A Finaud processa os dados do cliente e gera o arquivo DRM_2060 para transmissão ao BACEN. Em alguns clientes, a Finaud transmite diretamente ao BACEN (serviço pago adicional).

**Total de threads:** 97 (no integrador) · **90 triadas** (34 AG · 56 CO) · 7 sem status

**Fluxo padrão:**
1. Cliente envia os dados do mês (saldos, posições, extratos) para a Finaud
2. Finaud processa os dados e gera o arquivo DRM_2060
3. Finaud envia o arquivo **em anexo** por e-mail ao cliente
4. Cliente transmite ao BACEN — **ou** Finaud transmite diretamente ao BACEN (serviço pago)
5. **Conclusão = Finaud entregou o arquivo ao cliente** (ou transmissão ao BACEN confirmada)

**Variante "Prévia":**
- Alguns clientes enviam uma "prévia" dos dados (rascunho) para a Finaud validar antes de gerar a versão oficial
- Thread fica AGUARDANDO/Finaud até a validação ser concluída
- Após validação, a Finaud entrega o DRM definitivo → CONCLUÍDO

**Casos especiais identificados:**
- **Reuniões e convites Teams:** alguns clientes enviam convites de reunião sobre o DRM (ex.: Baru Financeira "Reuniao DRM", Read "🗓"). O sistema os classifica como AGUARDANDO/Finaud — **correto**, o mesmo tratamento dado nos CADOCs anteriores (ex.: DDR_2011 "Tenho agenda para reunião online amanhã"). Finaud precisa responder/participar.
- **Convites BACEN ([SANTS] SMM):** e-mails onde o próprio regulador convida para reunião sobre DRM 2060 + DLI 2061 + DLO 2062. Classified como AGUARDANDO — **correto**, são conversas ativas de suporte técnico com o regulador.
- **Acredito SCD — escalado para desenvolvimento:** F→C onde Pedro (Finaud) informou que escalou o caso para a equipe interna e vai retornar. Motor classificou como ACAO_INTERNA — **correto** (Finaud precisa agir internamente).
- **BGC — explicação técnica sem entrega:** F→C onde Andrea explicou o sistema de crítica do BACEN. Motor classificou como ACAO_INTERNA (caminho fallback); semanticamente seria RESPOSTA_CLIENTE. Status AG correto — apenas o tipo ficou impreciso (gap menor, não afeta a triagem).

---

**Cobertura de padrões — DRM_2060 (90 threads triadas)**

| Padrão (última mensagem) | AG | CO | Total | % | Regra dominante |
|--------------------------|----|----|-------|---|-----------------|
| F→C — Finaud enviou ao cliente | 7 | 50 | 57 | 63% | R1 (CO) / R3 ou R4 (AG) |
| C→F — Cliente enviou dados ou confirmou | 27 | 6 | 33 | 37% | R2 (AG) / R1 (CO, agradecimento) |
| **Total** | **34** | **56** | **90** | **100%** | |

---

**Regras validadas para DRM_2060:**

---

#### Regra R1 — Concluído: Finaud entregou o DRM ao cliente (ou transmissão confirmada ao BACEN)

**Quando dispara:**
- Última mensagem F→C com envio do arquivo DRM ("segue anexo a remessa DRM (2060)", "segue o DRM (2060)", "DRM_2060 para transmissão ao BACEN")
- Texto em qualquer parte do fio com "transmitido ao BACEN" (§3.1)
- Última mensagem C→F com agradecimento puro após entrega ("Ok, obrigado!", "Recebido")

**Exemplos reais (CO — F→C):**

| threadId | Empresa | Assunto | Trecho da última mensagem |
|----------|---------|---------|--------------------------|
| *(Planner — ver CO)* | Planner | DRM 2060_01/2026 | "transmitido ao BACEN em 06/02/2026" |
| *(Fair Corretora)* | Fair Corretora | DRM2060_012026 | "Flavio Camargo enviou DRM_2060 ao Fair Corretora" |
| *(Banvox)* | Banvox | Confecção DRM Jan/26 | "Lucas Vellani enviou DRM_2060 ao Banvox" |

> ⚠️ Exemplos com threadId completo a confirmar na pós-conclusão (seção 14 cobre os casos).

---

#### Regra R2 — Aguardando/Finaud: cliente enviou dados — Finaud precisa processar e gerar o DRM

**Quando dispara:**
- Última mensagem C→F com envio de saldos, posições ou extratos mensais
- Última mensagem C→F com envio de "prévia" para validação
- Última mensagem C→F com retificação de dados

**Exemplos reais (AG — C→F → ACAO_INTERNA):**

| Empresa | Assunto | Padrão |
|---------|---------|--------|
| Global Exchange | DRM JANEIRO / DRM fevereiro / DRM abril | Cliente enviou dados mensais (recorrente) |
| Trinus CO | RE: Informações DRM 2060 - Janeiro/26 … Março/26 | Cliente enviou informações mensais |
| Coluna DTVM | DRM 2060 - BASE 01/26, 03/26, 04/26 | Cliente enviou base de dados |
| Western Union | Prévia DRM Janeiro/2026, Fevereiro/2026 | Cliente enviou prévia para validação |
| TC | Saldo 02/02 e 03/02 | Cliente enviou saldos do período |
| Amaril Franklin | RELATÓRIO DRM 12/2025 | Cliente enviou relatório |

---

#### Regra R3 — Aguardando/Cliente: Finaud aguarda dados ou insumos do cliente

**Quando dispara:**
- Última mensagem F→C com pedido de extratos, saldos ou posições ("encaminhar os extratos", "aguardo o balancete")
- Finaud aguarda entrega de arquivo que o cliente não enviou ainda

**Exemplos reais (AG — F→C → ENTREGA_CLIENTE):**

| Empresa | Assunto | Situação |
|---------|---------|---------|
| Atual Câmbio | Encaminhar os extratos das operações 02/2026 | Finaud pediu extratos — cliente não enviou |
| Wise | DRM 2060 - 04/2026, 05/2026 | Finaud pediu dados — cliente não respondeu |
| Igua Corretora | Re: Doctos Igua Corretora | Finaud pediu documentos |
| Acredito SCD | DRM 2060_05/26 | Finaud pediu dados mês 05/26 |

---

#### Regra R4 — Aguardando/Finaud: Finaud enviou resposta substantiva — aguarda retorno do cliente

**Quando dispara:**
- Última mensagem F→C com conteúdo substantivo que não é entrega de arquivo (análise, esclarecimento, pergunta)
- Motor classifica como RESPOSTA_CLIENTE quando o corpo tem ≥ 40 caracteres fora de §5/§3-inv/§3.5

**Exemplos reais (AG — F→C → RESPOSTA_CLIENTE):**

| Empresa | Assunto | Situação |
|---------|---------|---------|
| Guru CTVM | Re: Guru CTVM: SMM - 2060 | Andrea respondeu pergunta técnica — aguarda retorno |
| Guru CTVM | Re: Guru CTVM: DRM (2060) maio 2026 | Idem — consulta técnica em aberto |
| Bacen (Gabriel) | Re: [SANTS] SMM - 2060 - LIM 2061 - LIM 2062 | Andrea agendou reunião — aguarda confirmação |
| Atual Câmbio | Re: Extratos - Atual - Março/2026. Segue o DRM | Andrea esclareceu erro de mês no texto — aguarda retorno |

---

#### Regra R5 — Aguardando/Finaud: encaminhamento interno (F→F)

> **F→F = 0** — nenhuma thread do DRM_2060 identificada com padrão F→F como última mensagem.
> A Regra R5 não se aplica neste CADOC. Para referência do padrão R5, ver DRL_2160 (seção 12.3).

---

**Regra geral C→F como última mensagem — DRM_2060:**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Agradecimento puro ("Obrigado", "Recebi") | **Concluído** | — | Cliente confirmou recebimento |
| Envio de dados, saldos, posições ou prévia | **Aguardando** | Finaud | Finaud precisa processar e gerar o DRM |
| Pergunta técnica ou dúvida | **Aguardando** | Finaud | Finaud precisa responder |
| Convite de reunião (Teams, calendar) | **Aguardando** | Finaud | Finaud precisa aceitar/participar |

---

**Quadro final DRM_2060 — regras de negócio:**

| Regra | Lado | Motivo | Status | Aplica a |
|-------|------|--------|--------|----------|
| R1 | — | Finaud entregou o DRM / transmissão confirmada ao BACEN | Concluído | DRM_2060 |
| R2 | Finaud | Cliente enviou dados mensais ou prévia — Finaud precisa processar | Aguardando | DRM_2060 |
| R3 | Cliente | Finaud aguarda extratos, saldos ou arquivo do cliente | Aguardando | DRM_2060 |
| R4 | Finaud | Finaud enviou resposta substantiva — aguarda retorno do cliente | Aguardando | DRM_2060 |
| R5 | — | **Não se aplica** — F→F = 0 no DRM_2060 | — | — |

---

**Conclusão da validação DRM_2060:**

O DRM_2060 é o único CADOC **mensal** do sistema (vs. DDR_2011 que é diário). O fluxo é idêntico: cliente envia dados → Finaud processa → gera o arquivo → entrega ao cliente (ou transmite diretamente ao BACEN no modelo de serviço pago). A Regra R5 (F→F) não se aplica — nenhuma thread com encaminhamento interno identificada. Dois sub-padrões específicos: (a) "Prévia" — cliente envia rascunho para validação antes da entrega final, thread fica AG/Finaud até a entrega; (b) reuniões/convites — tratados como AG/Finaud igual aos outros CADOCs.

**Gaps encontrados:**
- 1 gap menor de tipo: BGC classificado como ACAO_INTERNA em vez de RESPOSTA_CLIENTE (status AG correto — apenas o tipo impreciso, motor fallback)
- Threads de "Prévia" (3 — Western Union): aguardam a Finaud validar e entregar o DRM final — status AG correto

> ✅ **DRM_2060 — validação de regras de negócio concluída** (2026-06-18)

---

**Validação pós-conclusão DRM_2060 (passo 9 da metodologia):**

Analisadas **11 threads CO do DRM_2060** que receberam mensagem nova após o fechamento:

| Empresa | Situação pós-conclusão | Motor certo? | Regra |
|---------|------------------------|--------------|-------|
| Braza Bank ×4 (jan–abr/26) | C→F "Enviado o DRM de substituição X/2026" — cliente avisando que transmitiu ao BACEN por conta própria | ✅ CO correto | §3.1 — informacional, não exige ação Finaud |
| Amaril Franklin ×2 (fev, abr/26) | C→F dados → F→C Finaud entregou DRM novo | ✅ CO correto | Ciclo novo concluído dentro da mesma thread |
| **Mirae Invest (fev/26)** | C→F balancete → F→C Finaud pediu COS4010 → C→F cliente enviou COS4010 | ❌ **Gap** — última C→F com dado novo, deveria ser AG | R2 — insumo não detectado |
| Denver Contábil | C→F "agradeço o atendimento" | ✅ CO correto | §4d — agradecimento puro |
| Fair Corretora | F→C "realizamos as correções..." | ✅ CO correto | R1 — Finaud entregou correção |
| Mirae Invest (abr/26) | F→C "estou trabalhando" → F→C Finaud entregou | ✅ CO correto | R1 — entrega confirmada |
| Guru | F→C protocolo DRM entregue | ✅ CO correto | R1 |

**Resultado: 10 corretos ✅ · 1 gap ❌**

> ⚠️ **1 thread com gap — Mirae Invest (fev/26):** cliente enviou o COS4010 como última mensagem após ciclo aberto pela Finaud. Motor manteve CO porque a regra de reabertura (9-A) não detectou o dado novo. Será corrigida no backfill junto com os demais gaps — ver seção 13.10 (Grupo K).

> ✅ **As regras da seção 14 cobrem todos os casos encontrados.** O padrão Braza Bank ("cliente transmite ao BACEN por conta própria e avisa via C→F") já estava documentado no DDR_2011 — confirmado válido também no DRM_2060.

> ✅ **DRM_2060 — pós-conclusão concluída** (2026-06-18)

---

### 12.7 — S5 — Demonstrativo do Segmento S5

**O que é:** Relatório **mensal** de requerimentos de capital para instituições financeiras no segmento prudencial S5. A Finaud importa o COSIF enviado pelo cliente no sistema Risk Driver S5, gera a "Apuração dos Requerimentos Mínimos S5" (Resultado Quantitativo) e envia ao cliente.

**Total de threads:** 47 (24 AG · 23 CO)

**Fluxo padrão:**
1. Cliente envia o arquivo COSIF (COS4010/COS4016) à Finaud
2. Finaud importa o COSIF no sistema Risk Driver S5
3. Finaud gera o relatório de requerimentos mínimos (Resultado Quantitativo)
4. Finaud envia o relatório **em anexo** por e-mail ao cliente
5. **Conclusão = Finaud entregou o relatório ao cliente**

**Fluxos adicionais:**
- **Estudo de migração S5→S4:** clientes que querem mudar de segmento prudencial pedem à Finaud um estudo de viabilidade. A Finaud calcula, importa COSIFs, faz testes internos e responde ao cliente. **Conclusão = Finaud respondeu todas as dúvidas do estudo** (comportamento de suporte — igual à seção SUPORTE).
- **Acesso ao Risk Driver S5:** novos clientes no S5 precisam de senha/acesso ao sistema. **Conclusão = Finaud enviou a senha ao cliente.**
- **Encaminhamentos internos F→F:** para os estudos de migração, a Finaud encaminha internamente entre pessoas (ex.: "importar COS4010 na base da Açoriana para o estudo"). Esses casos ficam em AGUARDANDO/Finaud até a tarefa interna ser concluída.

---

**Cobertura de padrões — S5 (47 threads)**

| Padrão (última mensagem) | AG | CO | Total | % | Regra dominante |
|--------------------------|----|----|-------|---|-----------------|
| F→C — Finaud enviou relatório ou respondeu | 13 | 16 | 29 | 62% | R1 (CO) / R3 ou R4 (AG) |
| C→F — Cliente enviou COSIF ou confirmou | 7 | 6 | 13 | 28% | R2 (AG) / R1 (CO, agradecimento) |
| F→F — Encaminhamento interno Finaud | 4 | 1 | 5 | 11% | R5 (AG) / caso especial (CO) |
| **Total** | **24** | **23** | **47** | **100%** | |

---

**Regras validadas para S5:**

---

#### Regra R1 — Concluído: Finaud entregou o relatório / respondeu o estudo / enviou acesso

**Quando dispara:**
- Última F→C com entrega do Resultado Quantitativo ("Segue anexo a apuração dos requerimentos mínimos S5", "segue o Resultado Quantitativo", "segue o Demonstrativo S5")
- Última F→C com envio de senha/acesso ao Risk Driver S5
- Última F→C com conclusão de estudo de migração (respondeu todas as dúvidas)
- Última C→F com agradecimento puro após entrega

**Exemplos reais (CO):**

| Empresa | Motivo CO |
|---------|-----------|
| Acoriana Corretora (×3) | "Monica Macedo enviou S5 à Acoriana — ECSA (S5). Resultado Quantitativo" |
| Vector (×4) | "Monica Macedo / Pedro Silva enviou S5 ao Vector — VBS (Vector) - Relatório Quantitativo" |
| Carol DTVM (×3) | "Monica Macedo enviou S5 ao Carol DTVM — Carol DTVM (S5). Segue o Resultado Quantitativo" |
| Executive Câmbio (×2) | "Lucas/Finaud enviou S5 ao Executive Câmbio — Demonstrativo S5" |
| Conecta Câmbio (×2) | "Monica Macedo enviou S5 ao Conecta Câmbio — CONECTA S5 - Relatório Quantitativo" |

---

#### Regra R2 — Aguardando/Finaud: cliente enviou COSIF — Finaud precisa processar e entregar

**Quando dispara:**
- Última C→F com envio de COSIF ou dados de posição para geração do relatório

**Exemplos reais (AG — C→F → ACAO_INTERNA):**

| Empresa | Assunto | Situação |
|---------|---------|---------|
| Executive Câmbio | RE: Executive Corretora — Demonstrativo S5 — jan/2026 | Cliente enviou COSIF mensal |
| Acredito SCD | Mudança de segmento S5 para S4 | Cliente enviou dados para composição do DDR (thread complexo pós-migração) |
| Acoriana Corretora | Re: Cálculo de risco S5 para S4 — Encaminhar COS | Cliente enviou COSIF para o estudo |
| ARC Corretora | ENC: s4 para s5 | Cliente enviou documentação da migração |
| Numatur | Solicitamos por gentileza encaminhar o relatório S5 | Cliente respondeu à solicitação |

---

#### Regra R3 — Aguardando/Cliente: Finaud aguarda COSIF ou dados do cliente

**Quando dispara:**
- Última F→C com pedido de COS4010 ou COS4016 ("Solicitamos por gentileza encaminhar o COS4010")
- Finaud aguarda o cliente enviar o arquivo mensal

**Exemplos reais (AG — F→C → ENTREGA_CLIENTE):**

| Empresa | Assunto | Situação |
|---------|---------|---------|
| Acoriana Corretora | ECSA (S5) — Encaminhar o COS4010 JAN/2026 e FEV/2026 | Finaud pediu os COSIFs — cliente não enviou |
| Btcambio | Solicitamos por gentileza encaminhar o relatório S5 | Finaud aguarda dados |
| Buni Digital | RISK DRIVER S5 — Solicitamos encaminhar o COS4010 | Finaud aguarda COSIF |
| Conta Simples | Estudo da mudança do S5 para o S4 | Finaud aguarda informações para o estudo |

---

#### Regra R4 — Aguardando/Finaud: Finaud respondeu consulta — aguarda retorno do cliente

**Quando dispara:**
- Última F→C com resposta substantiva a uma consulta de migração, acesso ou dúvida técnica
- Finaud explicou, orientou ou parcialmente respondeu — mas o processo ainda não foi concluído

**Exemplos reais (AG — F→C → ACAO_INTERNA ou RESPOSTA_CLIENTE):**

| Empresa | Assunto | Situação |
|---------|---------|---------|
| Acoriana Corretora | Re: Cálculo de risco S5 para S4 | Finaud enviou instrução sobre o estudo — aguarda retorno |
| Buni Digital | Re: Gerenciamento de Riscos - Finaud | Finaud respondeu consulta — aguarda cliente |
| Smartsafe Brasil | Re: SSG (S5). Resultado Quantitativo Dez/2025 | Finaud enviou orientação — aguarda confirmação |
| Acredito SCD | Re: Arquivo BNDES | Finaud respondeu — aguarda cliente |
| ARC Corretora | Re: Ajuste no contrato ARC de Risk S4 para Risk | Finaud orientou sobre o processo — aguarda ação do cliente |

---

#### Regra R5 — Aguardando/Finaud: encaminhamento interno (F→F)

**Quando dispara:**
- Última mensagem foi de uma pessoa da Finaud para outra (estudo interno, importação de dados, testes)

**Exemplos reais (AG — F→F → ACAO_INTERNA):**

| Empresa | Assunto | Situação |
|---------|---------|---------|
| Acoriana Corretora | Fwd: Cálculo de risco S5 para S4 — Importar os COS | Andrea pediu a Monica para importar COS4010 para o estudo |
| Bezz SCD | Cálculos DLO - S5 — BEZZ SCD | Encaminhamento interno sobre cálculos |
| (Encaminhamento interno) | Fwd: Testes Risk Driver S5 — Dezembro 2025 | Troca interna sobre testes do sistema S5 |

---

**Regra geral C→F como última mensagem — S5:**

| Conteúdo da última C→F | Status | Com quem | Porque |
|------------------------|--------|----------|--------|
| Envio de COSIF / arquivo de posição | **Aguardando** | Finaud | Finaud precisa importar e gerar o relatório |
| Agradecimento puro ("Obrigada!", "Recebido") | **Concluído** | — | Cliente confirmou recebimento |
| Pergunta técnica / dúvida sobre migração | **Aguardando** | Finaud | Finaud precisa responder |

---

**Quadro final S5 — regras de negócio:**

| Regra | Lado | Motivo | Status | Aplica a |
|-------|------|--------|--------|----------|
| R1 | — | Finaud entregou o relatório / respondeu o estudo / enviou acesso | Concluído | S5 |
| R2 | Finaud | Cliente enviou COSIF — Finaud precisa importar e gerar o relatório | Aguardando | S5 |
| R3 | Cliente | Finaud aguarda COSIF ou dados do cliente | Aguardando | S5 |
| R4 | Finaud | Finaud respondeu consulta substantiva — aguarda retorno do cliente | Aguardando | S5 |
| R5 | Finaud | Encaminhamento interno entre pessoas da Finaud (F→F) | Aguardando | S5 |

---

**Conclusão da validação S5:**

O S5 tem o mesmo fluxo principal do DLO/DLI (cliente envia COSIF → Finaud processa → entrega relatório), mas adiciona dois serviços de consultoria: estudos de migração S5→S4 (comportamento igual ao SUPORTE — concluído quando Finaud respondeu tudo) e configuração de acesso ao Risk Driver S5 (concluído quando Finaud enviou a senha). A Regra R5 (F→F) existe e aparece nos estudos de migração — a Finaud encaminha internamente para importar dados ou fazer testes.

**Gaps encontrados:** nenhum identificado nas 24 AG (status todos corretos com base nos padrões acima).

> ✅ **S5 — validação de regras de negócio concluída** (2026-06-18)

---

**Validação pós-conclusão S5 (passo 9 da metodologia):**

Analisadas **3 threads CO do S5** que receberam mensagem nova após o fechamento:

| Empresa | Situação pós-conclusão | Motor certo? | Regra |
|---------|------------------------|--------------|-------|
| Executive Câmbio | C→F "Segue em anexo COS de fevereiro para cálculo do índice. Aguardo." | ❌ **Gap** — cliente enviou COSIF novo, thread deveria reabrir para AG | R2 |
| Carol DTVM | F→C "Segue anexo a apuração dos requerimentos mínimos S5 data base de Março/2026" | ✅ CO correto | R1 — novo ciclo concluído |
| Vector | F→C "Segue anexo a apuração dos requerimentos mínimos S5 data base: Abril/2026" | ✅ CO correto | R1 — novo ciclo concluído |

**Resultado: 2 corretos ✅ · 1 gap ❌**

> ⚠️ **1 gap — Executive Câmbio:** cliente enviou COSIF de fev/2026 após thread fechada. Motor manteve CO porque a regra de reabertura (9-A) não detectou o insumo. Registrado no Grupo L do backfill (seção 13.10).

> ✅ **S5 — pós-conclusão concluída** (2026-06-18)

---

### 12.8 — RETORNO_BACEN

#### O que é

O BACEN pode enviar comunicações ao cliente quando detecta problemas nos arquivos enviados:
inconsistências, indícios de problema de qualidade, avisos de atraso, reiterações. O cliente
encaminha esse comunicado à Finaud pedindo ajuda. A Finaud analisa, identifica o erro, corrige
(ou orienta a correção) e devolve o arquivo corrigido ao cliente para retransmitir ao BACEN — ou,
em alguns casos, transmite diretamente.

Diferente dos outros CADOCs (DDR, DLO, etc.), **RETORNO_BACEN não é um documento específico** — é
uma categoria que abriga os retornos do BACEN sobre *qualquer* CADOC (DLO 2061, DDR 2011, DLI 2062,
DRM 2060, DRL 2160, etc.). O assunto do e-mail normalmente indica o CADOC afetado.

#### Fluxo padrão

```
BACEN detecta problema → envia comunicado ao cliente
      ↓
Cliente encaminha à Finaud (C→F)
      ↓
Finaud analisa: qual CADOC? qual erro? como corrigir?
      ↓
Finaud corrige o arquivo e entrega ao cliente (F→C) → ou orienta o cliente
      ↓
Cliente retransmite ao BACEN → BACEN aceita
      ↓
Thread CONCLUÍDA
```

Variante mais curta: cliente confirma que o BACEN aceitou no mesmo thread ("STA aceitou",
"transmissão aceita") → conclui por §4f-rb, sem precisar esperar mais nada.

#### Números (estado atual dos JSONs)

| Situação | Quantidade |
|----------|-----------|
| AGUARDANDO (triadas) | 98 |
| CONCLUÍDAS (triadas) | 205 |
| Total triadas | 303 |
| No integrador | 336 |
| Não triadas | ~33 |

> Os ~33 não triados são threads recentes ainda não processadas pelo motor.

#### Padrões de conclusão — o que dispara CONCLUÍDO

| Regra | O que dispara | Condição |
|-------|--------------|----------|
| **§3.1** | Texto do fio contém "transmitido no BACEN", "transmitido ao BACEN" | Global — varre o fio todo |
| **§5** | Finaud enviou arquivo em anexo ao cliente ("segue em anexo", "arquivo corrigido...") | Veto: C→F substantiva depois |
| **§5b** | Finaud enviou resposta com "RES:" + corpo mínimo | Idem |
| **§5c** | Finaud enviou texto conclusivo operacional ("segue o arquivo", "arquivo ajustado", etc.) | Idem |
| **§5d** | Finaud orientou/entregou conclusivamente ("para solucionar...", fix confirmado) | Idem + veto F→F interno |
| **§4f-rb** | Cliente confirma BACEN aceitou ("foi aceito", "STA aceitou", "protocolo aceito") | **Exclusiva do RETORNO_BACEN** |
| **§4d** | Cliente agradece após remessa Finaud | C→F de agradecimento puro |
| **§6** | Mesma empresa + mesmo fingerprint de prazos, alguma já concluída | Cluster espelho |
| **§6b** | Mesma empresa + mesmo núcleo de assunto, alguma já concluída | Cluster espelho |

#### Padrões de aguardando — o que mantém AGUARDANDO

| Regra | Situação | Tipo |
|-------|---------|------|
| **§3-inv** | Finaud pediu insumos ao cliente (arquivo, dados, planilha) | ENTREGA_CLIENTE |
| **§3.5** | Finaud só reconheceu recebimento, sem entregar nada | ACAO_INTERNA |
| **F→C em análise** | Finaud respondeu com análise em andamento (mensagem ≥40 chars) | ACAO_INTERNA |
| **F→F** | Finaud encaminhou internamente para colega | ACAO_INTERNA |
| **§3 fallback** | Cliente enviou dados/arquivo — Finaud ainda não processou | ACAO_INTERNA |

#### Distribuição atual dos AGUARDANDO (98)

| Tipo | Quantidade |
|------|-----------|
| ACAO_INTERNA | 62 |
| RESPOSTA_CLIENTE | 24 |
| ENTREGA_CLIENTE | 12 |

Última direção das mensagens em AGUARDANDO:
- **54 C→F** — cliente enviou, Finaud precisa processar
- **40 F→C** — Finaud respondeu, análise em andamento ou pediu insumo
- **4 F→F** — encaminhamento interno

#### Distribuição atual dos CONCLUÍDOS (205)

| Tipo | Quantidade |
|------|-----------|
| RESOLVIDA | 147 |
| ACAO_INTERNA | 55 |
| ENTREGA_CLIENTE | 3 |

> "RESOLVIDA" é o tipo genérico de conclusão para threads encerradas pelas regras §3.1/§5/§5b/§5c/§5d/§4f-rb ou clusters.

#### Regra geral de decisão

```
Se texto do fio indica "transmitido ao BACEN" → CONCLUÍDO (§3.1)
Senão, se Finaud enviou arquivo/resposta conclusiva → CONCLUÍDO (§5/§5b/§5c/§5d)
Senão, se cliente confirmou BACEN aceitou → CONCLUÍDO (§4f-rb)
Senão, se cliente agradeceu após remessa → CONCLUÍDO (§4d)
Senão, se Finaud pediu insumos → AGUARDANDO ENTREGA_CLIENTE (§3-inv)
Senão, se Finaud só reconheceu → AGUARDANDO ACAO_INTERNA (§3.5)
Senão, se Finaud respondeu (análise em andamento) → AGUARDANDO ACAO_INTERNA
Senão, se F→F interno → AGUARDANDO ACAO_INTERNA
Senão (C→F) → AGUARDANDO ACAO_INTERNA (§3 fallback)
```

#### Regras validadas (R1–R6)

> Validadas por amostragem de threads reais (2026-06-18). Cada regra representa um padrão
> recorrente confirmado — não hipotético.

---

#### Regra R1 — Aguardando\Finaud: Finaud ainda está analisando ou processando internamente

**Padrão:** última mensagem é F→C com linguagem de análise em andamento (sem entrega real de
arquivo ou orientação conclusiva), ou F→F de encaminhamento interno.

**Frases típicas:**
- "Estou analisando...", "Vou verificar...", "Nossa equipe está verificando..."
- "Retornaremos em breve", "Assim que tivermos retorno..."
- "Vou fazer um teste na base de produção e qualquer dificuldade retorno"
- Encaminhamento interno: F→F sem C→F depois

**Campos:**
- `status`: AGUARDANDO
- `pendente`: FINAUD
- `responsavel`: nome da pessoa da Finaud que aparece na última mensagem
- `motivo`: "Finaud está analisando/processando — sem entrega ainda"
- `regra`: §3.5 (só reconheceu) ou §3 fallback (análise em andamento)

**Veto importante:** frases como "estou analisando", "retornaremos", "realizando os ajustes"
impedem a conclusão mesmo que a mensagem também contenha frases positivas.

---

#### Regra R2 — Aguardando\Cliente: Finaud pediu insumo (arquivo, dado, planilha)

**Padrão:** última mensagem é F→C com pedido explícito de arquivo ou dado ao cliente (§3-inv).

**Frases típicas:**
- "Por gentileza envie...", "Poderia encaminhar...", "Precisamos do arquivo..."
- "Pode nos enviar a planilha de...", "Aguardamos o COS4010..."

**Campos:**
- `status`: AGUARDANDO
- `pendente`: CLIENTE
- `responsavel`: nome do cliente (empresa)
- `motivo`: "Finaud aguarda envio de [arquivo/dado] pelo cliente"
- `regra`: §3-inv

---

#### Regra R3 — Aguardando\Finaud: cliente enviou o comunicado BACEN — Finaud precisa processar

**Padrão:** última mensagem é C→F com o comunicado do BACEN ou dados do erro. Finaud ainda não
respondeu (nenhuma F→C depois).

**Frases típicas:** encaminhamento do indício de qualidade, aviso de atraso, reiteração do BACEN.

**Campos:**
- `status`: AGUARDANDO
- `pendente`: FINAUD
- `responsavel`: pessoa da Finaud responsável pelo cliente (se conhecida)
- `motivo`: "Cliente encaminhou retorno BACEN — aguarda análise Finaud"
- `regra`: §3 fallback

---

#### Regra R4 — Concluído: Finaud entregou arquivo/solução conclusiva

**Padrão:** última F→C contém entrega real de arquivo ou orientação conclusiva com frase positiva
confirmada **e** sem frase de incerteza ou pendência posterior.

**Frases conclusivas positivas (§5d):**
- "Segue em anexo", "Providenciamos o recálculo", "Realizei a atualização"
- "Para solucionar, basta copiar e enviar", "Transmita a versão", "Foi corrigido"
- "Elaboramos um texto de resposta", "Está de acordo"

**Veto:** frases de incerteza ("aparentemente", "provavelmente", "acredito") ou pedido pendente
("por gentileza envie", "retornaremos") na mesma mensagem cancelam a conclusão.

**Campos:**
- `status`: CONCLUÍDO
- `pendente`: null
- `responsavel`: pessoa da Finaud que entregou
- `motivo`: "Finaud entregou [arquivo/orientação] — ciclo encerrado"
- `regra`: §5 / §5b / §5c / §5d

---

#### Regra R5 — Concluído: cliente confirmou BACEN aceitou ou confirmou envio (§4f-rb)

**Padrão:** última mensagem é C→F com confirmação de que o BACEN aceitou o arquivo, ou de que
o cliente transmitiu ao BACEN com sucesso. **Exclusiva do RETORNO_BACEN.**

**Frases típicas:**
- "O Bacen desconsiderou a crítica e aceitou o arquivo"
- "Arquivos submetidos ao BACEN hoje e respectivos indícios respondidos"
- "foram aceitos", "STA aceitou", "foi aceito"
- "Realizamos o envio do DLI de substituição ao Banco Central"

**Campos:**
- `status`: CONCLUÍDO
- `pendente`: null
- `responsavel`: null (cliente quem confirmou)
- `motivo`: "Cliente confirmou BACEN aceitou / arquivo transmitido com sucesso"
- `regra`: §4f-rb

---

#### Regra R6 — Concluído: cliente agradeceu (§4d)

**Padrão:** última mensagem é C→F de agradecimento puro, sem nova demanda embutida.

**Frases típicas:** "Muito obrigado", "Obrigada pelo retorno", "Ok, obrigado!", "Agradeço o retorno"

**Distinção crítica:** agradecimento acompanhado de nova pergunta ou nova ação sugerida pelo
cliente **não** é §4d — é reabertura (ver pós-conclusão abaixo).

**Campos:**
- `status`: CONCLUÍDO
- `pendente`: null
- `responsavel`: null
- `motivo`: "Cliente agradeceu — ciclo encerrado"
- `regra`: §4d

---

> ✅ **Conclusão da validação RETORNO_BACEN:** os padrões R1–R6 cobrem 100% dos casos amostrados.
> Não há situação encontrada fora deste quadro.

---

#### Pós-conclusão — o que chega depois do CONCLUÍDO

Das 205 threads CONCLUÍDAS, **69 têm última mensagem C→F** — o cliente enviou algo depois do
fechamento. Padrões encontrados:

**✅ CO correto — ~75% dos casos (amostragem de 20 threads, 2026-06-18)**

| Padrão | Exemplos reais | Resultado |
|--------|---------------|-----------|
| Agradecimento simples | "Muito obrigado", "Obrigada pelo retorno", "Obrigado!" | ✅ CO — mensagem informacional |
| BACEN aceitou / cliente confirmou envio | "foram aceitos", "O Bacen desconsiderou a crítica e aceitou o arquivo", "Arquivos submetidos ao BACEN hoje" | ✅ CO — §4f-rb confirmado |
| Cliente vai agir | "Irei comunicar o BC", "Vamos responder, obrigada" | ✅ CO — cliente tomou ciência e age |
| Cliente rodou/executou como instruído | "rodei novamente", "Ok Andrea, obrigado. Arquivo reenviado" | ✅ CO — cliente seguiu orientação |
| Problema resolvido explícito | "Problema resolvido, era isso mesmo" | ✅ CO — confirmação direta |

**❌ CO indevido — ~25% dos casos → deveriam ser AGUARDANDO**

| Padrão | Exemplos reais | Por que é gap |
|--------|---------------|--------------|
| Novo retorno BACEN no fio (M-A) | Planner — "favor verificar o retorno do Banco Central..." | Novo problema chegou — precisa de ação Finaud |
| Cliente fez nova pergunta a Finaud (M-B) | Nikos — "pode checar com ele por gentileza?"; Trinus CO — "foi possível substituir os arquivos?" | Finaud ainda tem ação pendente |
| Cliente ainda aguardando Finaud (M-B) | Oliveira Trust — "Ficaremos no aguardo" | Expresso que espera retorno |
| Cliente sugeriu nova ação necessária (M-B) | Atual Câmbio — "Acredito que tenhamos que enviar o março antes DLI 2062" | Nova demanda aberta |

O motor atual **não reabre** threads CONCLUÍDAS quando chega C→F pós-conclusão — mantém CO.
Das ~69 C→F CO, estimativa: ~17 são gaps reais (25%); ~52 são agradecimentos ou confirmações corretas.

> ⚠️ **Gaps registrados no backfill (Grupo M — seção 13.10):**
> - Subgrupo M-A: novo retorno BACEN no fio — detectar por palavras-chave ("banco central", "bcb", "inconsistência", "indício", "reiteração", "aviso de atraso")
> - Subgrupo M-B: nova pergunta/espera de cliente — detectar por ("pode checar", "foi possível", "conseguiu", "ficaremos no aguardo", "aguardamos", "esperando seu retorno")

> ✅ **RETORNO_BACEN — documentação concluída** (2026-06-18)

---

### 12.9 — SUPORTE

#### O que é

SUPORTE agrupa demandas operacionais e administrativas que não são regulatórias: criação de usuários,
resets de senha, acesso a sistemas, questões técnicas sobre cálculos, dúvidas sobre planilhas,
auditoria interna, estudos tributários, e outras solicitações de clientes que exigem resposta mas
não envolvem remessas ao BACEN ou documentos regulatórios.

Diferente dos CADOCs regulatórios (DDR, DLO, etc.), **SUPORTE não tem prazo regulatório** e pode
permanecer aberto indefinidamente até resolução da demanda — o status reflete apenas se Finaud
respondeu e resolveu ou ainda está processando/aguardando cliente.

#### Fluxo padrão

```
Cliente solicita (criar usuário, resetar senha, dúvida técnica, etc.)
      ↓
Finaud recebe e analisa
      ↓
Finaud responde resolvendo ("já foi criado", "password enviada") → CONCLUÍDO
      OU
Finaud pede insumo ao cliente (planilha, dados, confirmação) → AGUARDANDO CLIENTE
      OU
Finaud precisa processar internamente (análise, pesquisa) → AGUARDANDO FINAUD
```

#### Números (estado atual dos JSONs)

| Situação | Quantidade |
|----------|-----------|
| AGUARDANDO (triadas) | 115 (descontados 36 gaps: O, O2, P, P2, Q) |
| CONCLUÍDAS (triadas) | 81 |
| Total triadas | 196 |
| Não triadas/spam | 36 |

> Os 36 não triadas/spam são threads que já têm tratamento no código mas ficaram presas histórico:
> 26 spam (Facebookmail, Messaging, 3cx), 10 Risk Driver interno.

#### Regras validadas (R1–R7)

> Validadas por amostragem de 115 AG + 81 CO (2026-06-18). Cada regra representa padrão
> recorrente confirmado — não hipotético.

---

**Regra R1 — Aguardando\Finaud: cliente enviou insumo ou dado (§3 fallback)**

**Padrão:** última mensagem é C→F com arquivo, planilha, informação ou pergunta. Finaud ainda não
respondeu ou respondeu com análise em andamento.

**Exemplos reais:**
- Guru: "O BACEN entrou em contato pedindo envio do 4111... precisava de apoio de vocês para passar
  as informações corretas"
- Fair Corretora: cliente envia PCAM (arquivo)
- TC: cliente envia saldos diários para Finaud processar

**Campos:**
- `status`: AGUARDANDO
- `pendente`: FINAUD
- `responsavel`: pessoa Finaud responsável pelo cliente
- `motivo`: "Cliente enviou [insumo/dado] — Finaud aguarda processar"
- `regra`: §3 fallback

---

**Regra R2 — Aguardando\Finaud: Finaud ainda está analisando (§3.5)**

**Padrão:** última mensagem é F→C com linguagem de análise em andamento (sem resolução real).

**Frases típicas:** "estou analisando", "vou verificar", "nossa equipe está verificando", "retornaremos"

**Campos:**
- `status`: AGUARDANDO
- `pendente`: FINAUD
- `responsavel`: pessoa Finaud que está analisando
- `motivo`: "Finaud em análise/verificação — sem resposta final ainda"
- `regra`: §3.5

---

**Regra R3 — Aguardando\Finaud: encaminhamento interno F→F (§3.5)**

**Padrão:** última mensagem é F→F entre colaboradores Finaud. Aguarda processamento/resposta interna.

**Exemplos reais:** Márcio pedindo a Andrea para encaminhar indicador; encaminhamento de divulgação
BACEN internamente.

**Campos:**
- `status`: AGUARDANDO
- `pendente`: FINAUD
- `responsavel`: pessoa F que recebeu a solicitação
- `motivo`: "Encaminhamento interno Finaud — aguarda tratamento"
- `regra`: §3.5 / §3 fallback

---

**Regra R4 — Aguardando\Cliente: Finaud pediu info/documento (§3-inv)**

**Padrão:** última mensagem é F→C com pedido explícito de arquivo, dado ou informação ao cliente.

**Frases típicas:** "por gentileza, poderia retornar?", "poderia encaminhar...", "precisamos do arquivo..."

**Campos:**
- `status`: AGUARDANDO
- `pendente`: CLIENTE
- `responsavel`: nome do cliente (empresa)
- `motivo`: "Finaud aguarda [arquivo/dado/info] do cliente"
- `regra`: §3-inv

---

**Regra R5 — Aguardando\Cliente: questão técnica aberta ao cliente**

**Padrão:** última mensagem é F→C com pergunta ou questão pendente. Cliente precisa responder com
informação, confirmação, ou ação.

**Exemplos reais:**
- Guru para cliente: "Desse fundo tem mais alguma informação pendente?"
- TC cliente: "Não conseguimos os arquivos antes? Queria saber como vai ficar o Basileia"

**Campos:**
- `status`: AGUARDANDO
- `pendente`: CLIENTE
- `responsavel`: nome do cliente (empresa)
- `motivo`: "Questão técnica aberta — cliente responde"
- `regra`: §3-inv / §3 fallback

---

**Regra R6 — Concluído: Finaud resolveu (resposta conclusiva)**

**Padrão:** última mensagem é F→C resolvendo o problema. Cliente não precisa mais responder.

**Frases típicas:** "O usuário já foi criado", "password foi enviada", "problema resolvido", "arquivo
está pronto", "já configuramos"

**Campos:**
- `status`: CONCLUÍDO
- `pendente`: null
- `responsavel`: pessoa Finaud que resolveu
- `motivo`: "Finaud respondeu e resolveu — demanda encerrada"
- `regra`: ciclo encerrado

---

**Regra R7 — Concluído: F→F que se resolveu internamente**

**Padrão:** última mensagem é F→F de encaminhamento que resultou em ação interna resolvida. Demanda
foi processada internamente sem retorno ao cliente.

**Campos:**
- `status`: CONCLUÍDO
- `pendente`: null
- `responsavel`: pessoa F que resolveu
- `motivo`: "Encaminhamento interno Finaud — resolvido internamente"
- `regra`: ciclo encerrado

---

> ✅ **Conclusão da validação SUPORTE:** os padrões R1–R7 cobrem 100% dos 196 threads amostrados.
> Não há situação encontrada fora deste quadro.

---

#### Pós-conclusão — o que chega depois do CONCLUÍDO

Diferente de RETORNO_BACEN e outros CADOCs regulatórios, **SUPORTE sem prazo** pode permanecer CO
indefinidamente. Se cliente responde após conclusão com nova demanda, será um novo ciclo (nova thread
ou continuação da mesma com nova abertura). Padrão observado: reabertura rara em SUPORTE — maioria das
threads fecha definitivamente após Finaud responder.

---

> ✅ **SUPORTE — validação de regras de negócio concluída** (2026-06-18)

---

### 12.10 — DRSAC

#### O que é

DRSAC é um relatório regulatório (Demonstração de Responsabilidade em Soluções de Aplicações em Crédito)
que clientes de Finaud enviam ou consultam sobre. Diferente de DDR/4111/DLO (que Finaud gera), DRSAC
é normalmente comunicação do BACEN ou dúvida do cliente sobre se deve enviar.

#### Fluxo padrão

```
Cliente pergunta sobre DRSAC ou BACEN retorna comunicado
      ↓
Finaud analisa: é realmente obrigatório? qual é a situação?
      ↓
Finaud responde esclarecendo / orientando
      ↓
Cliente aceita orientação → CONCLUÍDO (não precisa responder)
```

#### Números (estado atual dos JSONs)

| Situação | Quantidade |
|----------|-----------|
| AGUARDANDO (triadas) | 0 |
| CONCLUÍDAS (triadas) | 2 |
| Total triadas | 2 |

> Volume muito pequeno — apenas 2 threads desde janeiro 2026.

#### Regras (compartilhadas com SUPORTE, sem variações)

DRSAC usa o mesmo conjunto de regras que SUPORTE:
- **R1 (AGUARDANDO):** cliente enviou dado/pergunta → Finaud processa
- **R2 (AGUARDANDO):** Finaud analisando → sem decisão
- **R3 (AGUARDANDO):** F→F interno
- **R4 (AGUARDANDO):** Finaud pediu insumo
- **R5 (AGUARDANDO):** questão técnica aberta
- **R6 (CONCLUÍDO):** Finaud respondeu resolvendo/orientando

**Diferença vs. SUPORTE:** DRSAC não tem §4e (cliente somente agradecimento sem contexto).

#### Validação e gaps

**Analisadas 2 threads (100% do volume):**

| threadId | Empresa | Assunto | Padrão | Status correto |
|----------|---------|---------|--------|----------------|
| `GMTHRID_1858833627365979844` | Braza Bank | DRSAC - Rejeitado | Finaud esclareceu que BACEN não exige DRSAC; orientou CADOC 2030 | ✅ CONCLUÍDO (regra R6) |
| `GMTHRID_1858032546602033166` | TC | RE: [Traders] DRSAC | Cliente agradeceu: "Obrigado vou apurar aqui" | ✅ CONCLUÍDO |

**Resultado: 1 gap ❌ + 1 correto ✅**

→ Braza Bank está classificada como AG mas deveria ser CO (registrado em Grupo R do backfill).

---

> ✅ **DRSAC — validação de regras de negócio concluída** (2026-06-18)
> **Conclusão:** Com apenas 2 threads (volume irrelevante), não há padrões variados a validar.
> Regras são idênticas a SUPORTE. O gap Braza Bank é simples reclassificação.

---

### 12.11 — FORCAPITAL

#### O que é

FORCAPITAL é uma ferramenta/relatório que Finaud oferece a clientes para planejamento financeiro e
projeção de capital. Diferente de relatórios regulatórios (DDR, DLO, etc.), FORCAPITAL é mais próximo
de SUPORTE: cliente faz pergunta, solicita acesso, ou Finaud envia projeção/documentação.

#### Fluxo padrão

```
Cliente solicita projeção, acesso, ou tem dúvida sobre FORCAPITAL
      ↓
Finaud recebe e verifica requisitos / prépara resposta
      ↓
Finaud responde entregando projeção/acesso OU pedindo dados do cliente → CONCLUÍDO ou AGUARDANDO
```

#### Números (estado atual dos JSONs)

| Situação | Quantidade |
|----------|-----------|
| AGUARDANDO (triadas) | 11 |
| CONCLUÍDAS (triadas) | 19 |
| Total triadas | 30 |

#### Regras (compartilhadas com SUPORTE, sem variações)

FORCAPITAL usa exatamente o mesmo conjunto de regras que SUPORTE:
- **R1 (AGUARDANDO):** cliente pediu projeção/acesso → Finaud processa/prepara
- **R2 (AGUARDANDO):** Finaud analisando requisitos → sem decisão
- **R3 (AGUARDANDO):** F→F interno (parecer, validação)
- **R4 (AGUARDANDO):** Finaud pediu dados do cliente
- **R5 (AGUARDANDO):** questão técnica/dúvida aberta
- **R6 (CONCLUÍDO):** Finaud entregou projeção/acesso/resposta conclusiva

#### Validação e gaps

**Analisadas 30 threads (100% do volume):**

**AG (11) — todos corretos:**
- 8 RESPOSTA_CLIENTE: Finaud pedindo projeção atualizada OU cliente questionando → aguarda ação/resposta
- 3 ACAO_INTERNA: Finaud pedindo parecer internamente OU encaminhamento

Exemplos:
- Terra Investimentos: "poderia nos enviar a projeção de capital atualizada para 36 meses?"
- Guru: "Conseguimos falar sobre o DLO? Como explica a projeção de 3 anos?"
- Intercam (F→F): "poderiam me dar um parecer sobre o apontamento?"

**CO (19) — 1 gap ❌ + 18 corretos ✅:**
- 17 RESOLVIDA (manual): Finaud entregou projeção/acesso/dados
  - Exemplo: AGK "Encaminhamos projeção de capital para DEZ/25 a DEZ/28"
- 1 RESPOSTA_CLIENTE (correto): Braza "Acesso ForCapital + credenciais"
- **1 ACAO_INTERNA (Gap S):** Oliveira Trust — misclassificada como FORCAPITAL mas é SUPORTE (Active Directory)

---

#### Pós-conclusão — o que chega depois do CONCLUÍDO

Das 19 threads CONCLUÍDAS, apenas **4 têm múltiplas mensagens** (indicador de reabertura possível):
- Fair Corretora (2 msgs)
- Terra Investimentos (2 msgs)
- Planner (19 msgs — thread longa)
- Oliveira Trust (5 msgs, data_marcacao: 2026-05-05)

**15 CO têm 1 msg** → sem pós-conclusão possível.

> ⚠️ **VALIDAÇÃO PENDENTE:** análise de pós-conclusão requer clareza sobre datas de marcação CO 
> (faltam dados sistematizados) e formatação HTML do integrador. Será validada junto com implementação
> do motor quando contexto completo de cada thread estiver acessível. Critério: se cliente enviou nova
> demanda/pergunta após CO, reclassificar para AGUARDANDO.

---

> ✅ **FORCAPITAL — validação de regras de negócio concluída** (2026-06-18)
> **Conclusão:** Padrões idênticos a SUPORTE (R1–R6). 1 gap de misclassificação (Grupo S).
> **Pós-conclusão:** ⚠️ VALIDAÇÃO PENDENTE (4 threads com múltiplas msgs, datas incompletas).

---

### 12.12 — CADOC 6209

#### O que é

CADOC 6209 — classificação genérica para comunicados/documentos diversos que não se encaixam em
outros CADOCs.

#### Números (estado atual dos JSONs)

| Situação | Quantidade |
|----------|-----------|
| No integrador | 1 (4 duplicatas do mesmo threadId) |
| Triadas | 0 |
| Não triadas | 1 |

#### Gap encontrado

**Grupo T — 1 thread 6209 não triada (falta informação de cliente)**

| threadId | Assunto | Problema | Ação |
|----------|---------|----------|------|
| `GMTHRID_1863628234606221398` | "CADOC 6209" | Empresa vazia; remetente vazio; assunto genérico | Complementar dados de cliente OU marcar como IGNORADO |

**Conteúdo:** Finaud respondendo a "Henrique" sobre "ajustes em andamento, expectativa conclusão hoje ou amanhã".

> ⚠️ **Conclusão:** 6209 existe mas com volume irrelevante (1 thread incompleta). Sem padrões a validar.
> Registrado como Grupo T para limpeza/complementação de dados.

---

## 13. Plano de Implementação — O que muda no sistema

> **Para o agente que implementar:** leia esta seção inteira antes de tocar em qualquer arquivo.
> Toda decisão de negócio que embasou estas mudanças está na seção 12 (regras por CADOC).
> Os dados estão em produção — qualquer erro aqui tem impacto real. Siga a ordem dos passos.

---

### 13.1 Resumo das mudanças (em linguagem simples)

Hoje o sistema classifica cada thread como AGUARDANDO ou CONCLUÍDO mas não registra **por qual regra** chegou nessa decisão, **quem é o responsável** pela ação, nem o **motivo** de forma padronizada. Após esta mudança, cada thread terá três campos extras que dão rastreabilidade completa — qual regra a classificou, quem tem a bola e por quê.

---

### 13.2 Novos campos nos JSONs de triagem

Cada registro nos arquivos `threads_aguardando_auto.json` e `threads_concluidas_auto.json` passará a ter:

| Campo | Tipo | Exemplo | Descrição |
|-------|------|---------|-----------|
| `regra` | string | `"R1"` | **Novo.** Código da regra que classificou a thread. Hoje não existe. |
| `pendente` | string | `"Finaud"`, `"Cliente"` ou `null` | **Novo.** De quem está pendente a ação. Preenchido apenas quando AGUARDANDO — fica vazio (`null`) quando CONCLUÍDO. Se a thread for reaberta, volta a ser preenchido. |
| `motivo` | string | `"Finaud entregou o DDR ou confirmou a tarefa"` | Já existe, mas com texto livre. Passa a ter valor padronizado por regra. |

> **Como ler os campos juntos (modelo de 3 perguntas):**
>
> **AGUARDANDO:** Status → `pendente` (Finaud ou Cliente) → `responsavel` (pessoa do lado pendente) → `motivo` (porque)
> - Se pendente com **Finaud**: *Aguardando → Finaud → Lucas Vellani (pessoa da Finaud) → Cliente enviou dados, Finaud precisa gerar e enviar o DDR*
> - Se pendente com **Cliente**: *Aguardando → Cliente → Pedro Silva (contato do cliente) → Finaud enviou mensagem — aguarda ação do cliente*
>
> **CONCLUÍDO:** Status → `responsavel` (quem fechou, geralmente pessoa da Finaud) → `motivo` (porque foi concluído) — `pendente` fica vazio
> Exemplo: *Concluído → Andrea Inacio → Finaud entregou o DDR ou confirmou a tarefa*
>
> **Regra central:** `responsavel` sempre aponta para a pessoa do lado que tem a ação. Se está pendente com o cliente, não faz sentido ter nome de alguém da Finaud neste campo.
>
> **REABERTO (Concluído → Aguardando):** quando chega nova mensagem após conclusão, `pendente` volta a ser preenchido e `responsavel` é atualizado para a pessoa do novo lado pendente.
>
> **Exemplo real de thread reaberta 3 vezes (assunto: DDR 2011 - 30/04/2026):**
>
> | Momento | status | pendente | responsavel | motivo |
> |---------|--------|----------|-------------|--------|
> | Após MSG 3 — Finaud entregou DDR | Concluído | *(vazio)* | Andrea Inacio | Finaud entregou o DDR ou confirmou a tarefa |
> | Após MSG 4 — Cliente enviou retificação | Aguardando | Finaud | Andrea Inacio | Cliente enviou dados/mensagem — Finaud precisa gerar e enviar o DDR |
> | Após MSG 5 — Finaud entregou DDR corrigido | Concluído | *(vazio)* | Andrea Inacio | Finaud entregou o DDR ou confirmou a tarefa |
> | Após MSG 6 — Cliente pediu novo arquivo | Aguardando | Finaud | Andrea Inacio | Cliente enviou dados/mensagem — Finaud precisa gerar e enviar o DDR |
> | Após MSG 7 — Finaud informou problema técnico | Aguardando | Cliente | Pedro Silva | Finaud enviou mensagem — aguarda ação do cliente |

**Campos que já existem e NÃO mudam:**

*(nenhum campo desta categoria — todos os campos existentes ou são mantidos sem alteração ou têm definição/valor atualizado)*

**Campos que já existem e mudam de definição/valor:**

| Campo | Definição/valor atual | Definição/valor novo | Observação |
|-------|-----------------------|----------------------|------------|
| `responsavel` | `"Andrea Inacio"`, `"Lucas Vellani"` — sempre pessoa da Finaud | Pessoa do **lado pendente**: se `pendente = "Finaud"` → nome da pessoa da Finaud; se `pendente = "Cliente"` → nome do contato do cliente | Lógica muda: o campo passa a apontar para o lado que tem a ação, não sempre para a Finaud |
| `motivo` | texto livre variado | texto padronizado por regra | Padronizado por CADOC |

**Campos aposentados (legado — manter valor atual, não apagar agora):**

| Campo | Valor atual (exemplo) | Motivo da aposentadoria |
|-------|-----------------------|------------------------|
| `tipo` | `"ACAO_INTERNA"`, `"ENTREGA_CLIENTE"`, `"RESPOSTA_CLIENTE"` | Substituído pelo campo `pendente` — redundante após a mudança |

> Marcar no código com: `# LEGADO — remover após validação (ver seção 13 da DOCUMENTACAO_TRIAGEM.md)`

**Campos candidatos a legado (manter por ora, marcar para excluir após validação):**

| Campo | Onde existe | Por quê é legado |
|-------|-------------|-----------------|
| `motivo_triagem_auto` | `threads_concluidas_auto.json` | Substituído pelo novo `motivo` |
| `motivo_triagem_auto_tecnico` | `threads_concluidas_auto.json` | Era texto técnico interno, substituído por `regra` |
| `aprendizado_ia` | `threads_concluidas_auto.json` | Bloco complexo que não é usado na tela atual |
| `quem_gera` | `threads_aguardando_auto.json` | Campo nunca preenchido corretamente |

> ⚠️ **Não remover** os campos legado nesta implementação. Mantê-los com os valores atuais.
> Após validar que o novo fluxo funciona corretamente, abrir tarefa específica para limpeza.
> Marcar no código com comentário: `# LEGADO — remover após validação (ver seção 13 da DOCUMENTACAO_TRIAGEM.md)`

---

### 13.3 Mapa de impacto — o que muda em cada arquivo

| Arquivo | Tipo de mudança | Detalhe |
|---------|----------------|---------|
| `scripts/triagem/motor.py` | **Alteração** | Ao classificar, preencher `regra`, `responsavel`, `motivo` com base nas regras de cada CADOC |
| `scripts/triagem/helpers.py` | **Alteração** | Funções de classificação devolvem também o código da regra |
| `data/json/pipeline/threads_aguardando_auto.json` | **Migração** | Adicionar `regra` nos registros existentes; atualizar `responsavel` e `motivo` |
| `data/json/pipeline/threads_concluidas_auto.json` | **Migração** | Adicionar `regra` nos registros existentes; atualizar `responsavel` e `motivo` |
| `scripts/11_triagem_auto.py` | **Alteração** | Passar os novos campos ao gravar nos JSONs |
| Tela Flask (templates + rotas) | **Alteração** | Exibir `regra`, `responsavel`, `motivo` no painel; remover exibição de campos legado |
| `tests/test_motor_triagem.py` | **Alteração** | Atualizar testes para verificar os novos campos nas saídas |
| `tests/test_motor_integracao_regras.py` | **Alteração** | Idem |

---

### 13.4 Estratégia para o histórico — migração leve

**Problema:** há 4.555+ threads já classificadas nos JSONs. Re-triá-las do zero levaria horas e há risco de alterar status que estão corretos.

**Solução: migração por inferência** — um script de migração percorre os JSONs existentes e atribui `regra`, `responsavel` e `motivo` com base nos campos já disponíveis (`cadoc`, `status`, `motivo` atual), sem rodar o motor completo e sem alterar o `status`.

**Regra para threads que não couberem em nenhuma regra inferida:**
- Campo `regra` recebe `"LEGADO-SEM-REGRA"`
- Campo `motivo` mantém o valor atual
- Registrar em log de migração para análise posterior
- Essas threads viram **backlog de revisão manual** — não bloqueia a migração

**Campos que o script de migração pode inferir com segurança:**

| Campo | Como inferir |
|-------|-------------|
| `responsavel` | Se AGUARDANDO + tipo atual `ACAO_INTERNA` → manter valor atual (já é pessoa da Finaud); se `ENTREGA_CLIENTE`/`RESPOSTA_CLIENTE` → preencher com nome do contato do cliente da thread (campo `cliente` ou contato extraído das mensagens). **Atenção:** para threads AGUARDANDO onde o pendente é com o cliente, o campo atual (pessoa da Finaud) ficará errado após a migração — marcar para revisão manual ou deixar vazio até o motor preencher corretamente na próxima execução. |
| `motivo` | Pelo CADOC + status atual, aplicar a regra mais frequente do CADOC (ex: DDR_2011 + CONCLUÍDO → `"Finaud entregou o DDR ou confirmou a tarefa"`) |
| `regra` | Pelo CADOC + status atual, atribuir a regra mais provável (ex: DDR_2011 + CONCLUÍDO → `"R1"`) |

> ⚠️ A inferência não é perfeita — algumas threads receberão a regra mais comum do CADOC, não necessariamente a exata. Isso é aceitável para o histórico. Novas threads (pós-implementação) receberão a regra correta pelo motor.

---

### 13.5 Ordem de execução — passo a passo

> **Versão detalhada e atualizada em 18/06/2026:** ver **seção 13.11** — em caso de conflito entre as
> duas seções, a 13.11 prevalece.

> **Pré-requisito:** ler a seção 13 inteira e ter lido as regras de todos os CADOCs (seção 12) antes de começar.

**Passo 0 — Criar branch dedicada**
```
git checkout -b implementacao/regras-triagem-v2
```
Nunca implementar diretamente na `main` ou na branch de desenvolvimento atual.

**Passo 1 — Backup obrigatório de todos os arquivos críticos**
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
Copy-Item "data/json/pipeline/threads_aguardando_auto.json" "data/json/pipeline/threads_aguardando_auto.json.backup_$ts"
Copy-Item "data/json/pipeline/threads_concluidas_auto.json" "data/json/pipeline/threads_concluidas_auto.json.backup_$ts"
Copy-Item "data/json/pipeline/03_integrador_dados_site.json" "data/json/pipeline/03_integrador_dados_site.json.backup_$ts"
```

**Passo 2 — Atualizar o motor (`motor.py` + `helpers.py`)**
- Cada função de classificação passa a retornar `(status, responsavel, motivo, regra)`
- Implementar as regras de todos os CADOCs conforme seção 12
- **Não rodar o pipeline ainda**

**Passo 3 — Atualizar o script 11**
- Ao gravar nos JSONs, incluir os novos campos
- Marcar campos legado com comentário no código

**Passo 4 — Rodar os testes**
```
pytest tests/ -q -m "not agent and not pdf and not integration"
```
Zero regressões antes de avançar.

**Passo 5 — Rodar o script de migração do histórico**
- Script percorre os JSONs existentes e preenche `regra`, `responsavel`, `motivo` por inferência
- Mostrar resumo: quantas threads inferidas com sucesso, quantas ficaram como `"LEGADO-SEM-REGRA"`
- **Aguardar confirmação do usuário** antes de gravar

**Passo 6 — Verificar integridade pós-migração**
- Total de registros idêntico ao backup
- Nenhum `status` alterado
- Todos os registros têm os 3 novos campos
- Tamanho do arquivo ≥ 95% do backup (nunca menor)

**Passo 7 — Atualizar a tela Flask**
- Exibir `regra`, `responsavel`, `motivo` no painel
- Testar a tela manualmente (localhost:5000)

**Passo 8 — Atualizar os testes**
- Verificar que testes novos cobrem os campos `regra`, `responsavel`, `motivo`
- Rodar pytest novamente — zero regressões

**Passo 9 — Backfill dos gaps conhecidos**
- Executar o backfill dos gaps listados na seção 13.10 (em ordem: Grupo A, B, C, D, E, F, G, H, I, J, K, L + Grupo M após varredura manual)
- Verificar cada thread na tela após a correção
- **Não pular:** sem o backfill, 13 threads ficam com status errado indefinidamente

**Passo 10 — Commit e PR**
- Commit na branch `implementacao/regras-triagem-v2`
- Abrir PR para `desenvolvimento-front_end` (nunca direto para `main`)
- Descrição do PR deve referenciar esta seção

---

### 13.6 Branch e backup — regras invioláveis

1. **Nunca** implementar diretamente em `main` ou `desenvolvimento-front_end`
2. **Sempre** fazer backup dos 3 JSONs críticos antes de qualquer script (Passo 1)
3. **Nunca** rodar dois scripts de migração em paralelo (os JSONs são compartilhados)
4. Se qualquer passo falhar, **restaurar do backup** antes de tentar de novo:
   ```powershell
   Copy-Item "threads_aguardando_auto.json.backup_AAAAMMDD_HHMM" "threads_aguardando_auto.json"
   ```

---

### 13.7 Critérios de validação

| Critério | Como verificar | Aprovado quando |
|----------|---------------|-----------------|
| Todos os registros têm `regra` | `grep -c '"regra"' threads_aguardando_auto.json` | Igual ao total de registros |
| Nenhum status foi alterado | Comparar totais AG/CO com backup | Igual ao backup |
| Testes passam | `pytest tests/ -q` | Zero regressões, zero falhas |
| Threads sem regra mapeada | Contar `"LEGADO-SEM-REGRA"` no JSON | Documentar no backlog; não bloqueia |
| Tela exibe novos campos | Abrir localhost:5000 e verificar visualmente | Campos visíveis e corretos |

---

### 13.8 Riscos e pontos de atenção

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Script de migração altera `status` indevidamente | Média | Passo 6 verifica isso; restaurar backup se ocorrer |
| Threads sem CADOC gravado não recebem regra | Baixa | Verificado: CADOC existe em todos os registros |
| Campo `tipo` antigo usado em outro script não mapeado | Alta | Fazer `grep -r "tipo" scripts/` antes do Passo 3 para mapear todos os usos |
| Tela quebra ao exibir campo inexistente no histórico | Média | Campos novos devem ter valor padrão (`""`) para registros antigos sem migração |
| Regras de CADOCs ainda não validados (seção 12.2+) | Alta | Implementar só após validar **todos** os CADOCs na seção 12 |

> ⛔ **Não iniciar a implementação antes de concluir a validação de todos os CADOCs (seção 12).**
> Implementar com regras incompletas vai gerar campos `"LEGADO-SEM-REGRA"` em excesso e exigir
> uma segunda migração. Terminar a seção 12 primeiro é mais eficiente.

---

### 13.9 Backlog de revisão manual (threads não mapeadas)

Após a migração, qualquer thread com `regra: "LEGADO-SEM-REGRA"` entra neste backlog.
O script de migração deve gerar um arquivo `_archive/analise/backlog_sem_regra_AAAAMMDD.json`
com a lista dessas threads, incluindo:
- `threadId`, `cadoc`, `status`, `motivo` original
- Motivo pelo qual não foi possível inferir a regra

Este backlog é revisado manualmente após a implementação estabilizar.

---

### 13.10 Backfill — gaps conhecidos (threads com status errado)

> **O que é backfill:** threads antigas que já estão gravadas nos JSONs com status incorreto. O motor novo classificaria certo threads novas, mas estas antigas só são corrigidas se um script de backfill for rodado explicitamente sobre elas. **Rodar o backfill é obrigatório após a implementação** — sem ele, 13 threads ficam com status errado indefinidamente.

**Como executar o backfill (em ordem — não pular):**
1. Fazer backup dos JSONs (ver Passo 1 da seção 13.5)
2. Para cada thread listada abaixo, atualizar o `status` no JSON correto (`threads_aguardando_auto.json` ou `threads_concluidas_auto.json`)
3. Preencher os campos `regra`, `pendente` e `motivo` com os valores corretos conforme a regra indicada
4. Verificar que o total de threads em AG + CO permanece o mesmo (nenhuma thread é criada ou apagada — apenas movida)
5. Rodar a tela Flask e confirmar que as threads aparecem no status correto

**Como verificar que o backfill funcionou:**
- Buscar cada threadId na tela (localhost:5000) e confirmar o status exibido
- Conferir no JSON que o campo `status` e `motivo` foram atualizados
- Conferir que a thread saiu do arquivo origem e entrou no arquivo destino

---

**Grupo A — 3 threads de CADOC 4111 (AG → devem ser CO)**

Raiz comum: Lucas (Finaud) entregou o CADOC 4111 ao cliente (Paulo Henrique, Planner) com a frase de assinatura "Desde já agradeço e permaneço à disposição". O motor interpretou essa frase como pedido pendente ao cliente quando é apenas encerramento cortês padrão do Lucas.

| threadId | Assunto | Regra correta | Correção |
|----------|---------|--------------|---------|
| `GMTHRID_1863635674448498641` | 4111 DIA 23/04 | R1 | AG → CO |
| `GMTHRID_1863352683346963259` | 4111 DIA 22/04 | R1 | AG → CO |
| `GMTHRID_1863269706951173753` | 4111 DIA 20/04 | R1 | AG → CO |

**Motivo a gravar:** `"Finaud entregou o CADOC 4111 ao cliente para envio ao BACEN"`
**Regra a gravar:** `"R1"`
**Pendente a gravar:** `null` (CONCLUÍDO não tem pendente)

---

**Grupo B — 2 threads de DDR_2011 (uma AG→CO, uma CO→AG)**

| threadId | Assunto | Problema | Regra correta | Correção |
|----------|---------|----------|--------------|---------|
| `GMTHRID_1867636963980688238` | Re: ERPM11 - Fator de Risco | Andrea disse "O cadastro do fator de risco já está disponível" — R1 não detectada por ausência de palavra-chave de arquivo | R1 | AG → CO |
| `GMTHRID_1856412445483493555` | GURU - ENVIO DO DDR E DRM - JAN/2026 | Monica entregou DDR+DRM mas na mesma mensagem pediu balancete COS4010 para o DLO; cliente agradeceu sem entregar; motor viu só o agradecimento | R3 | CO → AG |

Para o ERPM11 (AG→CO): **Motivo a gravar:** `"Finaud confirmou conclusão da tarefa (cadastro no sistema interno)"` | **Regra:** `"R1"` | **Pendente:** `null`

Para o GURU (CO→AG): **Motivo a gravar:** `"Finaud entregou DDR/DRM e solicitou balancete COS4010 ao cliente — balancete não entregue"` | **Regra:** `"R3"` | **Pendente:** `"Cliente"`

---

**Grupo C — 8 threads ESPELHO de DDR_2011 (AG → devem ser CO)**

Raiz comum: motor identificou corretamente cada thread como espelho (duplicata) e gravou o motivo "Thread espelho — [cliente] — encerrada por duplicidade com thread principal", mas não executou a etapa de mover a thread para CONCLUÍDO. Todas devem ser fechadas como CO com o motivo de espelho já gravado.

| threadId | Assunto | Cliente |
|----------|---------|---------|
| `GMTHRID_1866252916823752230` | DDR 2011 DOS DIAS 21 ao 25/05 - SEFER | Sefer Investimento |
| `GMTHRID_1860477336641857993` | PI Exposure MiraeAsset 20260319 | Mirae Invest |
| `GMTHRID_1857945692134753217` | PI Exposure MiraeAsset 20260219 | Mirae Invest |
| `GMTHRID_1857941262144216568` | Saldos 2011 e 4111 de 20/02/2026 | TC (Thaina Carvalho) |
| `GMTHRID_1857667752989126731` | Saldos 2011 e 4111 de 19/02/2026 | TC (Thaina Carvalho) |
| `GMTHRID_1857568129921672999` | Saldos 2011 e 4111 de 18/02/2026 | TC (Thaina Carvalho) |
| `GMTHRID_1857558028071185607` | DDR 2011 - 13/02/2026 | Acredito SCD |
| `GMTHRID_1856947124388761439` | DDR 2011 - 11/02/2026 | Acredito SCD |

**Motivo a gravar:** manter o `motivo_triagem_auto` já existente (já está correto — "Thread espelho — [cliente] — encerrada por duplicidade com thread principal")
**Regra a gravar:** `"ESPELHO"` — não é uma regra de negócio como R1/R2/R3/R4. É um mecanismo técnico interno do motor (§6) que detecta duplicatas pela empresa + período + assunto. Não analisa o conteúdo da conversa. Por isso não recebe numeração R0 — fica separado das regras de negócio.
**Pendente a gravar:** `null` (CONCLUÍDO)

---

**Resumo total do backfill:**

| Grupo | Direção | Qtd | CADOC |
|-------|---------|-----|-------|
| A — assinatura confundida | AG → CO | 3 | 4111 |
| B — ERPM11 sem palavra-chave | AG → CO | 1 | DDR_2011 |
| B — GURU entrega+pedido na mesma msg | CO → AG | 1 | DDR_2011 |
| C — ESPELHO detectado mas não fechado | AG → CO | 8 | DDR_2011 |
| **Total** | | **13** | |

---

**Grupo D — 2 threads de DRL_2160 (AG → devem ser CO)**

| threadId | Assunto | Problema | Regra correta | Correção |
|----------|---------|----------|--------------|---------|
| `GMTHRID_1862008503744710537` | Envio 2160 DRL 02/2026 | Cliente informou "Somente para que fiquem cientes, foi enviado hoje o 2160 DRL de 02/2026" — comunicado administrativo; motor não reconheceu como conclusão | R1 | AG → CO |
| `GMTHRID_1868094930909531258` | DRL Maio 2026 (CVD TVM) | Finaud disse "Providenciamos o cálculo e a transmissão da remessa DRL (2160) 05/2026"; motor interpretou "qualquer dúvida retorne" no final como pedido pendente | R1 | AG → CO |

Para ambas (AG→CO): **Motivo a gravar:** `"Finaud calculou e entregou o DRL ao cliente / ciclo confirmado"` | **Regra:** `"R1"` | **Pendente:** `null`

---

**Grupo E — 3 threads de DRL_2160 pós-conclusão (CO → devem ser AG)**

Raiz comum: thread estava Concluída mas recebeu mensagem nova que deveria ter reaberto. O motor manteve CO indevidamente. Detectado na validação pós-conclusão (passo 9 da metodologia).

| threadId | Assunto | Regra correta | Correção | Pendente |
|----------|---------|--------------|---------|---------|
| `GMTHRID_1856853424091223588` | Acredito SCD — DRL 01/2026 | R2 | CO → AG | Finaud |
| `GMTHRID_1859470681749037009` | SANTS SCD — DRL 02/2026 | R3 | CO → AG | Cliente |
| `GMTHRID_1865283663876735352` | Unicred — DRL 04/2026 | R4 | CO → AG | Finaud |

**Acredito SCD (CO→AG/Finaud):** **Motivo a gravar:** `"Cliente enviou nova planilha DRL para competência seguinte — Finaud precisa gerar e entregar"` | **Regra:** `"R2"` | **Pendente:** `"Finaud"`

**SANTS SCD (CO→AG/Cliente):** **Motivo a gravar:** `"Finaud solicitou planilha complementar ao cliente — aguardando resposta"` | **Regra:** `"R3"` | **Pendente:** `"Cliente"`

**Unicred (CO→AG/Finaud):** **Motivo a gravar:** `"Finaud recebeu dado do cliente mas ainda não gerou nem entregou o DRL"` | **Regra:** `"R4"` | **Pendente:** `"Finaud"`

---

**Resumo total do backfill (atualizado):**

| Grupo | Direção | Qtd | CADOC |
|-------|---------|-----|-------|
| A — assinatura confundida | AG → CO | 3 | 4111 |
| B — ERPM11 sem palavra-chave | AG → CO | 1 | DDR_2011 |
| B — GURU entrega+pedido na mesma msg | CO → AG | 1 | DDR_2011 |
| C — ESPELHO detectado mas não fechado | AG → CO | 8 | DDR_2011 |
| D — cliente avisou transmissão / Finaud transmitiu | AG → CO | 2 | DRL_2160 |
| E — pós-conclusão: thread reaberta indevidamente mantida CO | CO → AG | 3 | DRL_2160 |
| F — cliente confirmou STA / Finaud já havia entregado | AG → CO | 2 | DLI_2062 |
| G — pós-conclusão DLI: insumo novo não detectado | CO → AG | 1 | DLI_2062 |
| H — pós-conclusão DDR: reabertura não detectada | CO → AG | 6 | DDR_2011 |
| I — DLO: motor não detectou reabertura ou conclusão | CO→AG / AG→CO | 12 | DLO_2061 |
| J — pós-conclusão DLO: nova demanda não detectada | CO → AG | 8 | DLO_2061 |
| **Total** | | **47** | |

---

**Grupo F — 2 threads de DLI_2062 (AG → devem ser CO)**

| threadId | Assunto | Problema | Regra correta | Correção |
|----------|---------|----------|--------------|---------|
| `GMTHRID_1861931178448315920` | Re: Segue a remessa DLI 02/2026 — Accredito | Cliente disse "Já foi enviado no STA" — motor não reconheceu "STA" como confirmação de envio ao BACEN | R1 | AG → CO |
| `GMTHRID_1861746610681231923` | DLI 2062 - FEVEREIRO — Planner | Finaud informou que já havia entregado os DLI's em 30/03 — motor não reconheceu o contexto de encerramento | R1 | AG → CO |

Para ambas (AG→CO): **Motivo a gravar:** `"Finaud entregou o arquivo DLI ao cliente / ciclo confirmado"` | **Regra:** `"R1"` | **Pendente:** `null`

---

**Grupo G — 1 thread de DLI_2062 pós-conclusão (CO → deve ser AG)**

Raiz comum: thread estava Concluída mas recebeu insumo novo do cliente que o motor não detectou como reabertura.

| threadId | Assunto | Problema | Regra correta | Correção | Pendente |
|----------|---------|----------|--------------|---------|---------|
| `GMTHRID_1861754101780701474` | DLI 2062 BANVOX E TRUSTEE Fev | Cliente enviou novamente o arquivo da Banvox com login correto — motor manteve CO | R2 | CO → AG | Finaud |

**Motivo a gravar:** `"Cliente enviou insumo novo (arquivo Banvox com login correto) — Finaud precisa processar e gerar o DLI"` | **Regra:** `"R2"` | **Pendente:** `"Finaud"`

---

**Grupo H — 6 threads de DDR_2011 pós-conclusão (CO → devem ser AG)**

Raiz comum: thread estava Concluída mas recebeu mensagem nova do cliente com nova demanda (insumo, pedido ou problema em aberto). Motor manteve CO porque a regra de reabertura não detectou os sinais dessas mensagens.

| threadId | Assunto | Última msg cliente | Regra correta | Correção | Pendente |
|----------|---------|-------------------|--------------|---------|---------|
| `GMTHRID_1854960118250526724` | DDR 16.01.2026 | "Enviado documento de substituição para ajuste contábil" | R2 | CO → AG | Finaud |
| `GMTHRID_1855136335834009479` | Re: Capital Mínimo Nova Regulação | "Tenho agenda para reunião online amanhã às 11h. É possível?" | R2 | CO → AG | Finaud |
| `GMTHRID_1855505611493548257` | Re: Testes Arquivos 4111 e 2011 | "Anexos os arquivos de Outubro 2025 para DDR 2011" | R2 | CO → AG | Finaud |
| `GMTHRID_1857580055852238257` | DDR de 13/02/2026 | "Faltou o arquivo do dia 18/02, poderia nos enviar?" | R2 | CO → AG | Finaud |
| `GMTHRID_1858303292745768270` | Re: Calculo baseleia Traders | "Enviamos o 2060 retificado mas a inconsistência não desapareceu. Preciso adicionar comentário?" | R2 | CO → AG | Finaud |
| `GMTHRID_1858755788267685330` | 2011 e 4111 de 02 e 03/03/2026 | "Ainda não recebemos o DRM 2060. Poderia disponibilizar?" | R2 | CO → AG | Finaud |

Para todas (CO→AG/Finaud): **Motivo a gravar:** `"Cliente enviou nova demanda após fechamento — Finaud precisa agir"` | **Regra:** `"R2"` | **Pendente:** `"Finaud"`

---

**Grupo I — 12 threads de DLO_2061 (8 CO→AG · 4 AG→CO)**

**Sub-grupo I-A: 8 threads CO → devem ser AG**

| threadId | Assunto | Motivo do gap | Regra correta | Pendente |
|----------|---------|--------------|--------------|---------|
| `GMTHRID_1857033085840710344` | Avenue — Dúvida CPAD e DRC DLO Jan/26 | Cliente fez pergunta técnica, motor não detectou como reabertura | R2 | Finaud |
| `GMTHRID_1861818698334476620` | RES: DLO/DLI fev/26 | Cliente enviou saldo complementar fora do LEC | R2 | Finaud |
| `GMTHRID_1856022755137828211` | TRADERS — 4060 E 4066 12/2025 | Finaud disse "providenciando" (ainda gerando) — não entregou | R4 | Finaud |
| `GMTHRID_1858292510150466721` | ACCREDITO — Fechamento 12/2025 | Finaud só importou o COSIF, não gerou nem entregou o DLO | R4 | Finaud |
| `GMTHRID_1862359045279433529` | Recusa DLO 2061 Nikos Fev/2026 | Finaud fez pergunta sobre rejeição BACEN — aguarda cliente | R3 | Cliente |
| `GMTHRID_1857679411473939866` | DLO — DEZEMBRO | Cliente cobrou prazo e entrega | R2 | Finaud |
| `GMTHRID_1857480445808272579` | SISOM — Requisição 127482 | Cliente abriu nova demanda após agradecer | R2 | Finaud |
| `GMTHRID_1865639639033992423` | Conta 590.11 ACCP Inconsistente | Finaud resolveu inconsistência mas pediu cliente refazer cálculo — aguarda cliente | R3 | Cliente |

**Sub-grupo I-B: 4 threads AG → devem ser CO**

| threadId | Assunto | Motivo do gap | Regra correta |
|----------|---------|--------------|--------------|
| `GMTHRID_1864357760454257473` | Preenchimento para planilha LEC | Finaud entregou CNPJ solicitado — pergunta respondida, ciclo encerrado | R1 |
| `GMTHRID_1864988298133264947` | Informações relacionadas aos ativos ponderados | Finaud deu instruções completas de navegação — dúvida sanada | R1 |
| `GMTHRID_1859579092220554659` | DLO junho/2025 — CPC 06 | Finaud respondeu questão sobre impacto do CPC 06 no DLO | R1 |
| `GMTHRID_1863024337423764953` | Solicitação de esclarecimentos e ajustes | Cliente agradeceu o retorno detalhado — ciclo encerrado | R1 |

Para I-A CO→AG: **Motivo a gravar:** `"Thread reaberta — nova demanda do cliente ou etapa Finaud pendente"` | **Pendente:** conforme coluna acima
Para I-B AG→CO: **Motivo a gravar:** `"Finaud respondeu/entregou — ciclo encerrado"` | **Regra:** `"R1"` | **Pendente:** `null`

---

**Grupo J — 8 threads de DLO_2061 pós-conclusão (CO → devem ser AG)**

Raiz comum: thread estava Concluída mas recebeu mensagem nova do cliente com nova demanda (insumo, pergunta ou problema). Motor manteve CO.

| threadId | Assunto | Última msg cliente | Regra | Correção | Pendente |
|----------|---------|-------------------|-------|---------|---------|
| `GMTHRID_1856111714890581464` | 2061 — Dezembro/2025 | "você já teria o arquivo DLO 2061 jan/2026?" | R2 | CO → AG | Finaud |
| `GMTHRID_1856408737013732330` | DLO DEZEMBRO | "Reportado diferença de saldos" | R2 | CO → AG | Finaud |
| `GMTHRID_1858203923135580542` | DLO2061_112025 | "Em anexo." (enviou arquivo) | R2 | CO → AG | Finaud |
| `GMTHRID_1860102608903227103` | Atual Corretora Balancete 02/26 | "houve alguma modificação no DLO 12/2025?" | R2 | CO → AG | Finaud |
| `GMTHRID_1860114244405598047` | DLO DEZ/25 RETIFICADO | "poderia verificar apontamentos no CRD?" | R2 | CO → AG | Finaud |
| `GMTHRID_1861092985889898377` | DLO — FEVEREIRO | Planilha com dados divergentes (#N/D) | R2 | CO → AG | Finaud |
| `GMTHRID_1861742126361244073` | DLO2061_022026 | "Ainda com Rejeição de 01/2026 e 02/2026" | R2 | CO → AG | Finaud |
| `GMTHRID_1864358230808265625` | Relatórios DLO e DLI 03/2026 | "Seguem 4010 e LEC. Fico no aguardo dos arquivos." | R2 | CO → AG | Finaud |
| `GMTHRID_1865537776549234179` | Guru CTVM Balancete 04/2026 | "segue o CADOC 4010" | R2 | CO → AG | Finaud |

Para todas: **Motivo a gravar:** `"Cliente enviou nova demanda após fechamento — Finaud precisa agir"` | **Regra:** `"R2"` | **Pendente:** `"Finaud"`

---

---

**Grupo K — 1 thread de DRM_2060 pós-conclusão (CO → deve ser AG)**

| threadId | Empresa | Assunto | Última msg | Regra | Correção | Pendente |
|----------|---------|---------|-----------|-------|---------|---------|
| `GMTHRID_1858939525912507742` | Mirae Invest | DRM fev/2026 | C→F "Bom dia, Segue." (COS4010 enviado após Finaud pedir) | R2 | CO → AG | Finaud |

**Motivo a gravar:** `"Cliente enviou insumo novo após fechamento — Finaud precisa processar"` | **Regra:** `"R2"` | **Pendente:** `"Finaud"`

---

---

**Grupo L — 1 thread de S5 pós-conclusão (CO → deve ser AG)**

| threadId | Empresa | Situação | Última msg | Regra | Correção | Pendente |
|----------|---------|---------|-----------|-------|---------|---------|
| `GMTHRID_1858311771379069512` | Executive Câmbio | S5 fev/2026 | C→F "Segue em anexo COS de fevereiro para cálculo do índice. Aguardo." | R2 | CO → AG | Finaud |

**Motivo a gravar:** `"Cliente enviou COSIF novo após fechamento — Finaud precisa importar e gerar o relatório"` | **Regra:** `"R2"` | **Pendente:** `"Finaud"`

---

---

---

**Grupo M — threads de RETORNO_BACEN pós-conclusão com novo retorno BACEN (CO → devem ser AG)**

> ⚠️ A lista exata precisa de varredura manual: das 69 CO com última C→F, identificar quais contêm novo comunicado do BACEN (inconsistência, indício, reiteração, aviso de atraso) vs. agradecimento simples.

Exemplos confirmados durante documentação (2026-06-18):

| Empresa | Assunto parcial | Corpo da última C→F | Correção |
|---------|----------------|---------------------|---------|
| Planner | — | "Lucas, favor verificar o retorno do Banco Central sobre o t..." | CO → AG |
| Unidas DTVM | — | "O Bacen retornou com essa orientação..." | CO → AG |
| Planner | — | "Lucas, segue o outro comunicado referente a outra crítica..." | CO → AG |

**Subgrupo M-A (novo retorno BACEN explícito):** detectar C→F pós-conclusão com palavras-chave
("banco central", "bcb", "inconsistência", "indício", "reiteração", "aviso de atraso") → reabrir thread para AGUARDANDO.

**Subgrupo M-B — última C→F é nova demanda/pergunta/espera (não é agradecimento nem confirmação BACEN)**

Confirmados na amostragem de 20 threads CO C→F (2026-06-18):

| Empresa | Corpo da última C→F | Padrão detectado | Correção |
|---------|---------------------|-----------------|---------|
| Nikos | "O outro cliente mandou o arquivo novamente como envio ou reenvio, pode checar com ele por gentileza?" | cliente fez nova pergunta a Finaud | CO → AG |
| Oliveira Trust | "Obrigado pelo retorno. Ficaremos no aguardo." | cliente ainda aguardando retorno de Finaud | CO → AG |
| Trinus CO | "foi possível substituir os arquivos?" | cliente perguntando se Finaud executou ação | CO → AG |
| Atual Câmbio | "Acredito que tenhamos que enviar o março antes DLI 2062" | cliente sugerindo nova ação necessária | CO → AG |

**Regra a implementar (M-B):** vetar conclusão quando última C→F contém pergunta direta a Finaud
("pode checar", "foi possível", "conseguiu", "você conseguiu") ou frase de espera ("ficaremos no aguardo",
"aguardamos", "esperando seu retorno") — são reabertura de thread, não encerramento.

---

---

---

**Grupo M2 — 3 threads RETORNO_BACEN classificadas CO mas devem ser AG (motor não vetou incerteza)**

Motor classificou como CONCLUÍDO mas a última F→C contém linguagem de incerteza ("aparentemente", "provavelmente") ou pedido de verificação ao cliente — sem fix real entregue.

| threadId | Empresa | Assunto | Motivo do gap | Correção |
|----------|---------|---------|--------------|---------|
| `GMTHRID_1861745565222520569` | BGC | Re: BANCO CENTRAL - COMUNICACAO DE INCONSISTENCIA | Finaud disse "Aparentemente o P10 já aparece" — incerto, sem confirmação | CO → AG |
| `GMTHRID_1861926618012919601` | BGC | — | Finaud disse "Provavelmente a crítica ocorreu porque..." — explicação incerta sem fix | CO → AG |
| `GMTHRID_1859302789979033147` | Global DTVM | — | Finaud pediu "verifique com a contabilidade a versão do COS4010" — bola no cliente | CO → AG |

**Regra a implementar:** vetar conclusão quando última F→C contém "aparentemente", "provavelmente" + não tem frase conclusiva positiva.

---

---

**Grupo M3 — 1 thread RETORNO_BACEN classificada CO com última F→F ainda em andamento (CO → deve ser AG)**

| threadId | Empresa | Situação | Motivo do gap | Correção |
|----------|---------|---------|--------------|---------|
| `GMTHRID_1858734805423604883` | Encaminhamento interno Finaud | Thread com 10 msgs — DLI de múltiplos clientes. MSG9: "Ótimo está em testes de homologação". MSG10 F→F: "Vou fazer um teste na base de produção e qualquer dificuldade retorno." | Motor concluiu por regra anterior mas thread reabriu com F→F de problema em andamento | CO → AG |

**Regra a implementar:** F→F pós-conclusão com frase de pendência ("vou testar", "qualquer dificuldade retorno", "em homologação") → reabrir para AGUARDANDO.

---

---

**Grupo M4 — threads RETORNO_BACEN CO com linguagem de incerteza na única F→C (CO → devem ser AG)**

Padrão: única mensagem F→C com "provavelmente" ou "acredito" sem frase conclusiva positiva — motor concluiu indevidamente.

| threadId | Empresa | Corpo da F→C | Correção |
|----------|---------|-------------|---------|
| `GMTHRID_1862450616068101282` | Commcor | "Provavelmente a crítica ocorreu porque a importação do COS4010 ocorreu antes do dia 06/04..." — explicação incerta, sem fix | CO → AG |
| `GMTHRID_1864381267328757762` | Atual Câmbio | "Acredito que já havíamos providenciado a remessa DRM 31/12/20..." — incerto, sem confirmação real | CO → AG |

**Regra a implementar (reforça Grupo M2):** vetar conclusão quando última F→C contém "acredito", "provavelmente" sem frase conclusiva positiva.

---

---

**Grupo N — 2 threads RETORNO_BACEN com CADOC errado (devem ser SUPORTE)**

Threads classificadas como RETORNO_BACEN pelo script 05 mas cujo assunto real é cálculo do Índice de Basileia — serviço da Finaud para a TC, sem relação com retorno do BACEN. Devem ser reclassificadas para SUPORTE.

| threadId | Empresa | Assunto | Correção |
|----------|---------|---------|---------|
| `GMTHRID_1858560923375496724` | TC | Re: Calculo baseleia Traders - Jan/26. Segue o IB com base no COS4010 | RETORNO_BACEN → SUPORTE |
| `GMTHRID_1861195917996631113` | TC | Calculo basileia Traders - Jan/26. Segue o IB com base no COS4010 | RETORNO_BACEN → SUPORTE |

**Ação:** reclassificar o CADOC dessas threads no JSON do integrador e re-triá-las pelo motor do SUPORTE.

---

**Grupo O — 26 threads triadas como SUPORTE que são spam/notificações automáticas (AG → IGNORADO)**

Threads de domínios de spam que passaram pelo motor e foram classificadas como SUPORTE porque
`facebookmail.com` e `3cx` não estão em `_SPAM_DOMINIOS_MOTOR` (motor usa só `messaging.metamail.com`,
`noreply`, `mailer-daemon`). O `dominios_a_ignorar` do script 05 não alcança threads já no pipeline.

| Empresa | Qtd | Tipo de conteúdo | Período |
|---------|-----|-----------------|--------|
| Facebookmail | 15 | Sugestões de amizade, notificações de perfil | 2026-01-22 a 2026-05-07 |
| Messaging (WhatsApp Biz) | 9 | Newsletters e atualizações de produto | 2026-01-22 a 2026-05-07 |
| 3cx | 2 | Alertas de renovação do sistema de telefonia | 2026-01-22 a 2026-05-07 |

**Dois problemas a resolver:**

1. **Backfill (histórico):** remover estas 26 threads de `threads_aguardando_auto.json` — nenhuma delas tem ação pendente real.

2. **Regra futura (motor):** adicionar `facebookmail.com` e `3cx` a `_SPAM_DOMINIOS_MOTOR` em `scripts/triagem/motor.py` para que novas cargas não classifiquem esses domínios como SUPORTE.

---

**Grupo O2 — 10 threads de relatório interno Risk Driver presas no AG SUPORTE**

O motor já filtra `relatorio_interno_risk_driver=True` por padrão, mas estas 10 threads foram
triadas antes da flag existir e ficaram "congeladas" em AGUARDANDO. O painel as oculta, mas
`threads_aguardando_auto.json` ainda as carrega — precisam ser removidas do JSON de AGUARDANDO.

| threadId | Assunto |
|----------|---------|
| `GMTHRID_1854961635141762952` | 📢 Atenção: Atualização na página de Leiautes do Bacen 21/01 |
| `GMTHRID_1855052227282614816` | 📢 Atenção: Atualização na página de Leiautes do Bacen 22/01 |
| `GMTHRID_1855287485739570957` | Re: Risk Driver - CV INVESTIMENTOS DTVM LTDA DLO — Situação |
| `GMTHRID_1856834197377671678` | Re: Solicitação informações iniciais Risk Driver - SANTS SCD |
| `GMTHRID_1858232719525824078` | ENC: Risk Driver - IB CORRETORA DE CAMBIO, TVM LTDA DLO |
| `GMTHRID_1859207318776365530` | Re: Risk Driver - EBURY BANCO DE CAMBIO S.A — CONTA(S) COSIF(S) |
| `GMTHRID_1860101974249834502` | Re: Risk Driver - EBURY BANCO DE CAMBIO S.A — CONTA(S) COSIF(S) |
| `GMTHRID_1860120320764222285` | Re: Risk Driver - BARU SOCIEDADE DE CREDITO |
| `GMTHRID_1860850851555849586` | Re: Risk Driver - divergência no PU Debenture RISP24 |
| `GMTHRID_1862562780579250198` | Re: Risk Driver - Resultado Quantitativo Movimento 02/2026 |

**Ação:** remover do `threads_aguardando_auto.json` — o código já os filtra, basta limpar o histórico.

---

**Grupo P — 7 threads TC "Saldo" classificadas como SUPORTE mas são DDR_2011 ou 4111**

TC envia saldos diários para confecção dos relatórios DDR (2011) e 4111. Quando o assunto é curto
("Saldo 30/01/2026") sem mencionar o código do CADOC, o script 05 não detecta e classifica como SUPORTE.
Threads da mesma série com assunto mais explícito ("Saldos 2011 e 4111 de 13/02") foram corretamente
classificadas como DDR_2011 ou 4111.

| threadId | Assunto | Correção |
|----------|---------|---------|
| `GMTHRID_1855116589627713892` | RES: Encaminhar os saldos 20 a 22/01/2026. TRADERS | SUPORTE → DDR_2011 ou 4111 |
| `GMTHRID_1856026490745381511` | Saldo 30/01/2026 | SUPORTE → DDR_2011 ou 4111 |
| `GMTHRID_1856747941676738765` | Saldo 09/02. | SUPORTE → DDR_2011 ou 4111 |
| `GMTHRID_1858744005949499744` | Saldos dos dia 02/03 a 03/03. | SUPORTE → DDR_2011 ou 4111 |
| `GMTHRID_1859195654031417611` | Saldos dos dia 04/03 a 06/03. | SUPORTE → DDR_2011 ou 4111 |
| `GMTHRID_1859556168033333775` | RES: Saldos dos dia 11/03 a 12/03. | SUPORTE → DDR_2011 ou 4111 |
| `GMTHRID_1862361909339875134` | Saldos dos dia 08/04 e 09/04. | SUPORTE → DDR_2011 ou 4111 |

**Ação:** verificar conteúdo de cada thread para confirmar DDR_2011 ou 4111 e reclassificar o CADOC
no integrador. Regra de melhoria no script 05: detectar "saldo" + empresa TC → DDR_2011.

---

**Grupo P2 — 1 thread BGC classificada como SUPORTE mas é DLO_2061**

| threadId | Empresa | Assunto | Correção |
|----------|---------|---------|---------|
| *(a confirmar via integrador)* | BGC | "RES: [URGENTE] Problema Cálculo Parcela RWACPAD \| DLO" | SUPORTE → DLO_2061 |

**Ação:** confirmar threadId no integrador e reclassificar cadoc para DLO_2061.

---

**Grupo Q — 1 thread SUPORTE que é insumo de CADOC regulatório (CO indevido → deveria ser AG + CADOC certo)**

| threadId | Empresa | Assunto | Conteúdo real | Classificação errada |
|----------|---------|---------|---------------|---------------------|
| `GMTHRID_1865896145105691245` | Unicred | "Re: 2026.05.19 - FLUXO DE CAIXA - ZIIN" | Cliente (Celso) envia fluxo de caixa até 19/05 → Finaud (Mônica) reconhece: "Ok, obrigada" | SUPORTE CO (errado) |

**Análise:** Cliente enviou insumo (fluxo de caixa), Finaud só reconheceu — não processou nem entregou. Status deveria ser AG + ACAO_INTERNA. CADOC deveria ser identificado (S5, DLI, ou outro que exija fluxo de caixa de Unicred/ZIIN).

**Ação:** (1) identificar qual CADOC correto (S5, DLI, etc.); (2) reclassificar cadoc no integrador; (3) marcar como AG se continuar como SUPORTE.

---

**Grupo S — 1 thread FORCAPITAL misclassificada (deveria ser SUPORTE)**

| threadId | Empresa | Assunto | Conteúdo real | Classificação errada |
|----------|---------|---------|---------------|---------------------|
| `GMTHRID_1864369812673905681` | Oliveira Trust | "Re: [compliance] Integração sistemas Finaud com Active Directory" | Cliente pergunta sobre integração AD; Finaud responde que não tem integração. Questão técnica. | FORCAPITAL ACAO_INTERNA (errado) |

**Análise:** É questão técnica/SUPORTE, não FORCAPITAL. Deveria ser SUPORTE CO RESOLVIDA (Finaud respondeu resolvendo).

**Ação:** reclassificar cadoc para SUPORTE e tipo para RESOLVIDA.

---

**Grupo T — 1 thread CADOC 6209 não triada (dados incompletos)**

| threadId | Assunto | Problema | Ação |
|----------|---------|----------|------|
| `GMTHRID_1863628234606221398` | "CADOC 6209" | Empresa vazia; remetente vazio; assunto genérico | Complementar dados de cliente OU marcar como IGNORADO |

**Análise:** Thread não foi triada automaticamente porque falta informação de cliente (empresa vazia, remetente vazia).

**Ação:** pesquisar contexto completo e complementar dados de cliente, OU classificar como IGNORADO se for comunicado genérico.

---

**Grupo U — Auditoria: 24 threads não triadas (gap entre integrador e triadas)**

**RESUMO DA INVESTIGAÇÃO (18/06/2026):**
- Script 03 (integrador): **4.573 threads únicas coletadas**
- Script 11 (triadas): **4.549 threads** em aguardando + concluidas
- **GAP: 24 threads** — investigadas; **nenhuma é bug de pipeline**

**Breakdown dos 24 não triados:**
| CADOC | Qtd | Resultado da investigação |
|-------|-----|--------------------------|
| IGNORADO | 18 | Marcadas para ignorar — **comportamento correto** ✅ |
| DDR_2011 | 2 | **F→F internos Finaud** — correto não triar ✅ |
| 4111 | 1 | **F→F interno Finaud** — correto não triar ✅ |
| FORCAPITAL | 1 | **Já triada** (Oliveira Trust — falso alarme) ✅ |
| DRL_2160 | 1 | **F→F interno Finaud** (encaminhamento interno) ✅ |
| 6209 | 1 | Já registrado em Grupo T — dados incompletos ❌ |

**Característica comum dos 4 gaps regulatórios investigados:** todos têm `empresa = ''`,
`contato_origem.lado = 'FINAUD'` e `contato_destino.lado = 'FINAUD'` — são **discussões internas
da Finaud sobre clientes**, não e-mails de clientes para a Finaud. O motor corretamente ignora
threads F→F sem empresa identificada.

**Detalhamento dos 4 threads F→F internos:**
| ThreadId | Quem escreveu | Para quem | Assunto | status_processo |
|----------|---------------|-----------|---------|-----------------|
| `GMTHRID_1865262591143210689` | Andrea Inácio (F) | Mônica Macedo (F) | FLUXO DE CAIXA - ZIIN (falta conta COSIF) | PENDENTE |
| `GMTHRID_1865189590887992466` | Andrea Inácio (F) | Flávio Camargo (F) | Atual Câmbio — remessas mensais | PENDENTE |
| `GMTHRID_1864562224455518487` | Andrea Inácio (F) | Rodrigo Tibério (F) | Habilitar 4111 para Kinel/Iguá Corretora | INFORMATIVO |
| `GMTHRID_1863717251896403174` | Pedro Silva (F) | Marcio Vellani (F) | Encaminhamento do relatório DRL Ativa 2024 | INFORMATIVO |

> ⚠️ As 2 threads com `status_processo = PENDENTE` (ZIIN/Unicred e Atual Câmbio) têm tarefas
> internas abertas na Finaud. Não são bugs de pipeline, mas podem precisar de acompanhamento
> operacional fora da triagem.

**Conclusão:** O pipeline está íntegro. O único gap real é o Grupo T (6209 sem dados).
O motor nunca triou F→F internos — isso é correto e intencional.

**Próximo passo — script de auditoria pós-carga:**
Criar verificação automática após cada execução do script 11 que:
1. Compara threadIds do integrador vs triadas
2. Para cada gap, verifica se `contato_origem.lado = 'FINAUD'` + `contato_destino.lado = 'FINAUD'` (F→F) ou se está na lista IGNORADO
3. Alerta apenas threads que **não se enquadram** em nenhuma dessas categorias
4. Critério de sucesso: zero alertas após cada carga (todos os gaps têm justificativa documentada)

---

**Grupo R — 1 thread DRSAC classificada AG que é CO (classificação de tipo errada)**

| threadId | Empresa | Assunto | Conteúdo real | Classificação errada |
|----------|---------|---------|---------------|---------------------|
| `GMTHRID_1858833627365979844` | Braza Bank | "DRSAC - Rejeitado" | Finaud esclarece que BACEN não exige DRSAC; instituição entendeu errado; correto é CADOC 2030 | AG RESPOSTA_CLIENTE (errado) |

**Análise:** Finaud respondeu com orientação/esclarecimento conclusivo — cliente não precisa responder confirmando. Status deveria ser CO RESOLVIDA com regra R6.

**Ação:** reclassificar tipo para RESOLVIDA e status para CONCLUÍDO.

---

> ⚠️ **Este backlog cobre DDR_2011, 4111, DRL_2160, DLI_2062, DLO_2061, DRM_2060, S5, RETORNO_BACEN, SUPORTE (completo), DRSAC (completo), FORCAPITAL (completo), CADOC 6209 (1 thread com dados incompletos) + AUDITORIA DE CONSISTÊNCIA PIPELINE (24 threads investigadas — todas com justificativa, nenhum bug)** — Total: ~50 gaps + reclassificações registradas (Grupos A–U). Referência completa em Passo 9 da metodologia (seção 14).

---

## 14. Regras de Pós-Conclusão

Regras internas do motor — não aparecem na tela. Definem o que acontece quando uma nova mensagem chega numa thread já marcada como Concluída.

> **Princípio geral:** o motor reavalia toda thread a cada carga. Não existe thread "protegida". Se chegou mensagem nova, o motor aplica as regras abaixo.

---

### 14.1 Quadro de regras pós-conclusão

| # | Situação | Como o motor identifica | Status resultante | Coberto? |
|---|----------|------------------------|-------------------|----------|
| 1 | Cliente agradeceu / confirmou / comunicado administrativo | Última msg C→F **sem nova demanda** (sem pedido, sem pergunta, sem dado novo para Finaud) | Mantém Concluído | ✅ |
| 2 | Cliente trouxe nova demanda (dado, pedido ou pergunta) | Última msg C→F com qualquer sinal de nova demanda: "?", "poderia", "faltou", "segue" + dado sem confirmação de transmissão ao BACEN | Reabre → Aguardando/Finaud | ✅ |
| 3 | Finaud respondeu sem pedir nada ao cliente | Última msg F→C sem pedido ou solicitação (sem "poderia", "por gentileza", "aguardo", "encaminhar") | Volta para Concluído | ⚠️ Regra existe (R1) mas motor atual não aplica em threads reabertas — gap de implementação |
| 4 | Finaud respondeu e pediu algo ao cliente | Última msg F→C com pedido ou solicitação | Aguardando/Cliente | ✅ (regra R3) |
| 5 | Cliente sumiu — sem nova mensagem | Não há nova mensagem desde a última avaliação | Permanece no último status | ⚠️ Sem solução automática |

**Exemplos reais para teste (Item 2 — nova demanda → reabre Aguardando/Finaud):**

| threadId | Assunto | CADOC | Última msg cliente | Sinal detectado |
|----------|---------|-------|--------------------|----------------|
| `GMTHRID_1857580055852238257` | DDR de 13/02/2026 | DDR_2011 | "Faltou o arquivo do dia 18/02, poderia nos enviar?" | "faltou" + "poderia" + "?" |
| `GMTHRID_1858583145041246678` | DDR 2011 - 27/02/2026. Segue a remessa | DDR_2011 | "Seguem os arquivos para composição do DDR2011 retificados..." | "segue" + dado novo |
| `GMTHRID_1864448541901865012` | 4111 DOS DIAS 30/04, 04/05 e 05/05 - SEFER | 4111 | "Segue informação do dia 30/04, os demais serão enviados posteriormente." | "segue" + dado parcial |
| `GMTHRID_1855053069023076589` | Re: Seguem as remessas 4111 17/12 a 21/12 GURU | 4111 | "Segue também demais documentações que a Contabilidade disponibilizou junto com os CADOCs." | "segue" + dado novo |

**Exemplos reais para teste (Item 3 — Finaud respondeu sem pedir nada → Concluído):**

> ⏳ Exemplos a adicionar após validar os demais CADOCs — padrão identificado mas threadIds de DDR_2011/4111 ainda não encontrados para este cenário específico.

**Threads com gap de implementação (motor atual não detecta — Item 3):**

> ⏳ Exemplos a adicionar após validar os demais CADOCs.

> ⚠️ **Gap de implementação:** o motor atual não aplica a regra R1 em threads reabertas — só na triagem inicial. O agente implementador deve garantir que a regra "F→C sem pedido = Concluído" se aplique também ao fluxo pós-conclusão.

> **Itens 2 e 3 originais foram fundidos** — "cliente trouxe dados/retificação" e "cliente fez pergunta/dúvida" usam o mesmo mecanismo de detecção e produzem o mesmo resultado.

---

### 14.2 Regra de detecção de "nova demanda" (itens 1 e 2)

Não existe lista fechada de palavras de agradecimento — o que importa é detectar **ausência de nova demanda**.

O motor verifica se a última msg C→F contém qualquer um destes sinais:
- **Pedido:** "poderia", "por gentileza", "pode enviar", "precisamos", "solicito"
- **Pergunta:** "?" no corpo da mensagem
- **Dado/arquivo:** "segue", "anexo", "planilha", "extrato", "retificado", com ou sem `anexos_detectados`
- **Problema:** "faltou", "erro", "não consta", "divergência", "inconsistência"

Se **nenhum** desses sinais estiver presente → considera agradecimento/confirmação → mantém Concluído.
Se **qualquer um** estiver presente → reabre → Aguardando/Finaud.

> ✅ Validado com 18 mensagens reais (17/06/2026): a regra classificou corretamente 16 de 18.
> Os 2 ambíguos tinham agradecimento + nova demanda na mesma mensagem — a nova demanda tem prioridade.

**Exemplos reais para teste (Item 1 — agradecimento → mantém Concluído):**

| threadId | Assunto | CADOC | Última msg cliente |
|----------|---------|-------|-------------------|
| `GMTHRID_1856295926479016558` | CADOC 4111 02/02/2026 | 4111 | "Lucas, Obrigada pelo envio." |
| `GMTHRID_1855667332910226144` | CADOC 4111 26/01/2026 | 4111 | "Obrigada Lucas!" |
| `GMTHRID_1864997669729496810` | Re: Relatório 4111 | 4111 | "Ok As 15hrs te chamo Já fiz o DDR até 30 Grato" |

**Exemplos reais para teste (Item 2 — cliente trouxe dados → reabre Aguardando/Finaud):**

| threadId | Assunto | CADOC | Última msg cliente |
|----------|---------|-------|-------------------|
| `GMTHRID_1858583145041246678` | DDR 2011 - 27/02/2026. Segue a remessa | DDR_2011 | "Seguem os arquivos para composição do DDR2011 retificados..." |
| `GMTHRID_1864448541901865012` | 4111 DOS DIAS 30/04, 04/05 e 05/05 - SEFER | 4111 | "Segue informação do dia 30/04, os demais serão enviados posteriormente." |

---

### 14.4 Ajuste de regra — falso positivo "cliente trouxe dado"

**Problema identificado (17/06/2026):** ao analisar 9 threads classificadas como Concluído onde a última mensagem do cliente continha palavras como "arquivo" ou "submetidos", verificamos que **5 de 9 estavam corretas** — o cliente estava confirmando que transmitiu ao BACEN, não enviando dado novo para a Finaud.

**Causa do falso positivo:** palavras como "arquivo", "submetidos", "enviamos" disparavam a detecção de "dado enviado" mesmo quando o cliente estava apenas confirmando uma ação própria.

**Casos analisados (DDR_2011 e 4111):**

| threadId | Última msg cliente | Correto? | Por quê |
|----------|--------------------|----------|---------|
| `GMTHRID_1856295926479016558` | "Lucas, Obrigada pelo envio." | ✅ Concluído | Agradecimento puro |
| `GMTHRID_1864997669729496810` | "Ok As 15hrs te chamo Já fiz o DDR até 30 Grato" | ✅ Concluído | Confirmação/agradecimento |
| `GMTHRID_1857580055852238257` | "Faltou o arquivo do dia 18/02, poderia nos enviar?" | ❌ Deveria ser Aguardando | Novo pedido explícito — "faltou" + "poderia" + "?" |
| `GMTHRID_1864448541901865012` | "Segue informação do dia 30/04, os demais serão enviados posteriormente." | ❌ Deveria ser Aguardando | Dado parcial enviado — Finaud ainda precisa processar |

> ⏳ Exemplos adicionais de outros CADOCs serão acrescentados conforme cada CADOC for validado.

**Regra ajustada — como distinguir "dado novo" de "confirmação do cliente":**

| Sinal na última msg C→F | Classificação | Lógica |
|------------------------|---------------|--------|
| "submetidos ao BACEN", "transmitidos", "arquivos foram transmitidos" | Mantém Concluído | Cliente confirmou ação própria — não há demanda para a Finaud |
| "somente para que fiquem cientes", "apenas informando" | Mantém Concluído | Comunicado administrativo — sem demanda |
| "poderia", "por gentileza", "faltou", "?" | Reabre → Aguardando/Finaud | Pedido ou pergunta explícita — nova demanda |
| "segue", "segue anexo", "retificado" **sem** "submetidos/transmitidos" | Reabre → Aguardando/Finaud | Cliente enviou dado para Finaud processar |

> ⚠️ **Prioridade de detecção:** verificar primeiro se há confirmação de transmissão ao BACEN ("submetidos", "transmitidos") — se sim, mantém Concluído independente de outras palavras. Só depois verificar se há pedido ou dado novo.

---

### 14.3 Item em aberto — cliente sumiu

Quando o cliente não responde mais após a Finaud ter feito uma pergunta ou pedido, a thread fica em Aguardando indefinidamente.

**O sistema já detecta esse cenário** — o `painel_operacional_snapshot.py` marca como "Não Resolvidos" toda thread em Aguardando há **7 ou mais dias** desde a `data_marcacao`. Essas threads já aparecem destacadas no painel operacional.

**Dimensão real do problema (verificado em 17/06/2026):**

| Tempo em Aguardando | Threads |
|--------------------|---------|
| Menos de 30 dias | 115 |
| 30–60 dias | 227 |
| 60–90 dias | 287 |
| **90–180 dias** | **581** |
| Sem data registrada | 30 |
| **Total** | **1.240** |

**581 threads (47% do total)** estão há mais de 90 dias sem resolução — já visíveis como "Não Resolvidos" no painel.

**Exemplos das mais antigas (verificadas em 17/06/2026):**

| threadId | Assunto | CADOC |
|----------|---------|-------|
| `GMTHRID_1851881700490432799` | Cálculo de risco S5 para S4 | S5 |
| `GMTHRID_1843529890625455068` | ENVIO POSIÇÃO CADOC 4111 - SSG | RETORNO_BACEN |

**Conclusão:** o problema é de **ação**, não de **detecção** — o sistema já sabe quais threads estão paradas, mas não toma nenhuma ação automática. O campo `prazo` está preenchido em apenas 31% das threads (1.422 de 4.555), então não é base confiável para fechar automaticamente.

**Decisão:** permanece no último status conhecido. A visibilidade já existe via "Não Resolvidos" no painel. Caso se deseje ação automática futura (ex: fechar após X dias por CADOC), criar tarefa específica com definição do prazo por CADOC.

---

### 13.11 Plano de implementação refinado — versão detalhada (18/06/2026)

> Esta seção aprofunda e refina a seção 13.5. Em caso de conflito entre as duas, **esta prevalece**.
> Origem: planejamento detalhado realizado em 18/06/2026 antes de iniciar qualquer implementação.

---

#### 13.11.1 Nomenclatura do campo `regra` — distinção obrigatória

Durante o planejamento de 18/06/2026 foi identificada uma ambiguidade que precisa ser fixada:
os códigos `§3.1`, `§5`, `§4f-rb` são **nomes internos do código** (`helpers.py`) e **nunca devem
aparecer no campo `regra` dos JSONs**. O campo `regra` armazena apenas rótulos de negócio.

| Onde fica | O que armazena | Exemplos |
|-----------|---------------|---------|
| Código interno (`helpers.py`) | Nomes técnicos das funções de detecção | `§3.1`, `§5`, `§4f-rb`, `§6` |
| Campo `regra` no JSON + tela | Rótulos de negócio — sempre R1, R2, R3... | `"R1"`, `"R2"`, `"ESPELHO"` |

**Regras de nomenclatura:**
- O campo `regra` nos JSONs **nunca** armazena os códigos §. Eles são internos ao código.
- Cada CADOC tem sua própria numeração R1–R5 (ou R1–R7 para SUPORTE) — são independentes entre CADOCs.
  - Ex: DDR_2011 R1 ≠ 4111 R1 (regras diferentes com o mesmo número; o campo `cadoc` diferencia)
- Exceções ao padrão R1/R2/R3...:
  - `"ESPELHO"` — mecanismo técnico de deduplicação (§6); não é regra de negócio; não recebe numeração Rn
  - `"LEGADO-SEM-REGRA"` — valor temporário para threads do histórico onde a regra não pôde ser inferida

---

#### 13.11.2 Princípio central — o que não muda

A lógica que decide AGUARDANDO vs CONCLUÍDO **não muda**. Estamos adicionando rótulos a uma decisão
que já está certa. O motor continua acertando o status — passa a também explicar *por quê*.

Consequência prática: o risco desta implementação é menor do que parece. Uma regressão no novo
código afeta os rótulos (`regra`, `pendente`, `motivo`), não o status AG/CO. O pipeline não para.

---

#### 13.11.3 Os 4 pontos de mudança no código

| Arquivo | O que muda | O que não muda | Como testar |
|---------|------------|----------------|-------------|
| `scripts/triagem/helpers.py` | Retorno de cada função: de apenas o status para `(status, regra, pendente, motivo)` — uma tupla com 4 valores | Toda a lógica de detecção — o §-cérebro não muda | Testes unitários por função, um CADOC por vez |
| `scripts/triagem/motor.py` | Coleta os 4 valores e monta o dict completo com campos novos | Fluxo de decisão e ordem de prioridade das regras | Testes de integração (já existe `test_motor_integracao_regras.py`) |
| `scripts/11_triagem_auto.py` | Grava os campos novos no JSON ao salvar cada thread | Toda a lógica de "quando salvar" — o script é quase um pass-through | Dry run do pipeline + verificar JSON gerado |
| Tela Flask (templates + rotas) | Exibir `regra`, `pendente`, `motivo` no painel | Toda a estrutura de rotas e filtros existentes | Abrir localhost:5000 e verificar cada painel visualmente |

---

#### 13.11.4 A sequência de execução — 9 fases (em ordem, sem pular)

> Esta sequência substitui e detalha o "Passo a passo" da seção 13.5.

**Fase 0 — Branch dedicada**

Criar `implementacao/regras-triagem-v2`. Nunca implementar diretamente em
`desenvolvimento-front_end` ou `main`.

- Salvaguarda: qualquer erro fica isolado — as branches existentes nunca são afetadas.

---

**Fase 1 — Escrever os testes primeiro (TDD) — 1 CADOC por vez**

Para cada CADOC, escrever testes que definem o contrato esperado:
> "dado este tipo de thread DDR_2011, espero `regra=R1`, `pendente=null`,
> `motivo=Finaud entregou o DDR ou confirmou a tarefa`"

- O gabarito de cada teste já está definido na seção 12 — validado com o usuário durante a
  documentação. **Não é necessário repetir a validação de negócio nesta fase.** Só se aparecer
  um caso ambíguo não coberto pela seção 12 é que o usuário será consultado.
- Usar 2–3 threads reais por regra (extraídas dos JSONs existentes como fixtures)
- Os testes **vão falhar** inicialmente — isso é esperado. Eles são o alvo a atingir.
- Total estimado: ~12 CADOCs × ~5 regras × 2 casos = ~120 testes novos
- Estes testes ficam no sistema permanentemente em `tests/` e rodam em toda alteração futura
  (manual, pre-commit, CI no GitHub) — são a rede de segurança do sistema a longo prazo

- Salvaguarda: testes falhando antes de implementar provam que o contrato foi definido corretamente.

---

**Fases 2+3 — Implementar `helpers.py` + `motor.py` — 1 CADOC por vez (fases acopladas)**

> `helpers.py` e `motor.py` são acoplados: se helpers.py passa a devolver 4 valores e motor.py
> ainda espera só 1, o sistema quebra imediatamente. Por isso estas duas fases andam juntas,
> CADOC por CADOC. Nunca atualizar todos os helpers de uma vez e deixar o motor para depois.

Para cada CADOC, em sequência:
1. Atualizar as funções de detecção em `helpers.py` (devolvem 4 valores: status, regra, pendente, motivo)
2. Atualizar `motor.py` para receber e usar os 4 valores daquele CADOC
3. Rodar `pytest tests/ -q -m "not agent and not pdf and not integration"`
4. Só avançar para o próximo CADOC quando **todos os testes daquele CADOC passarem**

**Conexão com a Fase 1:** os testes escritos na Fase 1 são exatamente os que rodam aqui.
O fluxo por regra é: Fase 1 escreve o teste (fica vermelho) → Fase 2+3 implementa o código
→ pytest fica verde → próxima regra.

**Três momentos de teste automático:**

| Quando | Quem aciona | O que roda |
|--------|------------|------------|
| Durante o desenvolvimento | Claude (após cada CADOC) | pytest completo |
| No commit | Automático (pre-commit hook já ativo) | pytest completo |
| No PR para desenvolvimento-front_end | Automático (GitHub CI) | pytest completo |

- Salvaguarda: nunca pular o pytest entre CADOCs — regras de CADOCs diferentes podem interagir

---

**Fase 4 — Atualizar `11_triagem_auto.py`**

Gravar os campos novos no JSON ao salvar. Campos legado continuam sendo gravados também —
não remover ainda.

- Salvaguarda: campos legado continuam existindo — nada quebra na tela por enquanto

---

**Fase 5 — Rodada a seco (dry run) — ver sem gravar**

Rodar o motor sobre os JSONs existentes em modo "só mostrar" — listar quais threads receberiam
qual `regra` e `pendente`, sem alterar nenhum arquivo. O usuário revisa e confirma que os
resultados fazem sentido antes de qualquer gravação.

- Salvaguarda: nenhum arquivo JSON é tocado nesta fase — 100% reversível

---

**Fase 6 — Migração do histórico (~4.555 threads)**

> **Princípio desta fase:** falha silenciosa é pior do que falha visível. O sistema avisa
> sempre que algo for incerto — o usuário decide. Nenhuma thread pode ser migrada com erro
> sem que isso seja visível e rastreável.

**Como funciona — motor novo nos dados reais (não inferência):**
1. Para cada thread no JSON de triagem, buscar os dados completos no integrador (JSON 03)
2. Rodar o motor novo sobre esses dados — retorna `regra`, `pendente`, `responsavel`, `motivo` exatos
3. Cada thread recebe também um indicador de confiança (ver abaixo)
4. O script gera o relatório completo antes de gravar qualquer coisa
5. Só grava após confirmação explícita do usuário

**Três resultados possíveis por thread:**

| Situação | O que acontece |
|----------|---------------|
| Status correto + motor concorda | Adiciona os campos novos, status não muda |
| Status errado + thread está nos Grupos A-U | Corrige o status E adiciona os campos novos (já documentado e aprovado) |
| Motor discorda do status atual + thread NÃO está nos Grupos A-U | Não toca no status — vai para lista de revisão manual |

**Indicador de confiança — nada fica silencioso:**

Cada thread migrada recebe um campo `regra_confianca`:

| Valor | Significado | Ação |
|-------|------------|------|
| `"ALTA"` | Passou nas 4 camadas com correspondência forte de conteúdo | Sem revisão necessária |
| `"MÉDIA"` | Camadas lógicas OK, mas match de conteúdo fraco | Spot-check recomendado |
| `"BAIXA"` | Passou só na camada lógica, sem match de conteúdo | Revisão manual obrigatória |

**4 camadas de validação automática (rodam em 100% das threads):**

1. **Consistência lógica:** CONCLUÍDO → pendente=null; AGUARDANDO → pendente=Finaud ou Cliente; regra compatível com o CADOC
2. **Conteúdo bate com a regra:** para cada regra, palavras-chave esperadas na mensagem; R1 DDR → deve ter "transmitido", "enviou", "segue em anexo"; R2 DDR → última mensagem deve ser do cliente
3. **Motor novo vs motor antigo:** onde concordam no status → confiança alta; onde discordam → sinalizado
4. **Revisão manual:** só as threads que falharam nas camadas 1, 2 ou 3 — estimativa: 5–10% do total

**Relatório completo de migração:**

Gerado antes de qualquer gravação. Contém **todas** as 4.555 threads — não só as problemáticas.
Agrupado por CADOC e por regra. O usuário pode revisar qualquer CADOC a qualquer momento.
Threads com `regra_confianca` BAIXA ou MÉDIA ficam destacadas para revisão prioritária.

**`"LEGADO-SEM-REGRA"` só para casos genuinamente excepcionais:**
- Thread cujos dados no integrador estão incompletos (motor não consegue processar)
- Thread de CADOC não coberto pela documentação

**Salvaguardas obrigatórias:**
- Backup organizado antes de qualquer gravação — em pasta própria com CONTEXTO.md (ver padrão abaixo)
- Total de threads idêntico antes e depois — nenhuma some ou é criada
- Nenhum `status` muda fora do que está documentado nos Grupos A-U

**Padrão de backup obrigatório (definido em 18/06/2026 — vale para todo o sistema):**

```
data/json/pipeline/backups/
└── AAAAMMDD_HHMM_motivo/
    ├── threads_aguardando_auto.json
    ├── threads_concluidas_auto.json
    ├── 03_integrador_dados_site.json
    └── CONTEXTO.md   ← data, motivo, o que vai mudar, quem autorizou, como restaurar
```

Nunca usar arquivo solto com sufixo `_backup_$ts` na pasta de produção.
Este padrão vale para qualquer rotina do sistema que modifique dados — não só esta migração.

---

**Fase 7 — Atualizar a tela Flask**

Exibir `regra`, `pendente`, `responsavel` e `motivo` padronizado no painel.
O campo `regra_confianca` **não aparece na tela** — é usado só internamente no relatório de
migração e no script de comparação. A tela mostra apenas o que o usuário usa no dia a dia.

Template usa fallback se o campo não existir (mostra vazio — não quebra para threads não migradas).

**Script de comparação antes/depois (roda nesta fase e em toda implementação futura):**

O script tira uma "foto" do estado do sistema e compara dois momentos:

- **Antes das mudanças:** registra o baseline — total por status, por CADOC, por regra,
  campos vazios ou com valores inesperados. Detecta problemas que já existem hoje.
- **Depois das mudanças:** tira nova foto e compara com o baseline.
  Relatório: ✅ esperado / ⚠️ diferente / ❌ problema novo detectado

Campos verificados pelo script: `regra`, `pendente`, `responsavel`, `motivo`, `status`,
`cadoc`, `empresa` — qualquer vazio inesperado ou valor fora do padrão é reportado.

> Este script não é só para a migração. Passa a ser uma ferramenta permanente de saúde
> do sistema — pode rodar a qualquer momento para detectar falhas silenciosas existentes.
> Ver IF-01 em PENDENCIAS.md para uso contínuo após a implementação.

Testar visualmente em localhost:5000 após a atualização da tela:
- Regra aparece corretamente por thread?
- Pendente (Finaud/Cliente) está visível?
- Motivo está em texto claro, sem códigos §?
- Threads sem campos novos não quebraram?

- Salvaguarda: campos legado ainda existem — tela não quebra para threads não migradas

---

**Fase 8 — Limpeza dos campos legado (fase separada, sempre depois)**

> Só executar após o sistema novo estar estável por dias/cargas reais. Nunca junto com
> a implementação — são commits separados, fase separada.

**Campos a remover:**

| Campo | Onde | Substituído por |
|-------|------|----------------|
| `tipo` | JSON aguardando | `pendente` |
| `motivo_triagem_auto` | JSON concluído | `motivo` |
| `motivo_triagem_auto_tecnico` | JSON concluído | `regra` |
| `aprendizado_ia` | JSON concluído | não usado — removido sem substituto |
| `quem_gera` | JSON aguardando | não usado — removido sem substituto |

**Ordem obrigatória — não inverter:**

1. `grep -r "campo_a_remover" scripts/ templates/` em cada campo → zero usos antes de avançar
2. Atualizar o código para parar de gravar os campos (threads novas já não terão)
3. Backup organizado em pasta própria com CONTEXTO.md (padrão do projeto — ver CLAUDE.md)
4. Rodar script de comparação antes/depois (ver Fase 7) para confirmar o que mudou
5. Script remove os campos dos JSONs existentes
6. Validar: tela funciona, totais de threads iguais, nenhum campo legado visível

Se a ordem for invertida — remover do JSON antes de parar de gravar — os campos voltam
na próxima carga.

- Condição obrigatória: OK explícito do usuário antes de cada etapa
- Qualquer campo só é removido após grep confirmar zero usos em qualquer arquivo

---

#### 13.11.5 Como simular cada CADOC antes de implementar

Para cada CADOC, antes de escrever uma linha de código:

1. Pegar 3 threads reais desse CADOC dos JSONs existentes (preferencialmente uma por regra R1/R2/R3)
2. Anotar qual regra cada thread DEVERIA receber segundo a documentação (seção 12)
3. Isso vira o teste — o código só estará certo quando retornar exatamente aquele resultado
4. Após implementar, rodar o motor novo sobre as mesmas threads e comparar com o esperado
5. Se bater → CADOC implementado corretamente. Se não bater → revisar o código antes de avançar

> Esta sequência é o protocolo dos 7 passos (CLAUDE.md) aplicado individualmente a cada CADOC.

---

#### 13.11.6 Critérios de validação por fase

| Fase | Critério de aprovação | Como verificar |
|------|-----------------------|----------------|
| 1 (testes) | Testes escritos para todos os CADOCs | Contar novos testes em `tests/` |
| 2 (helpers) | pytest zero regressões após cada CADOC | `pytest tests/ -q -m "not agent and not pdf and not integration"` |
| 3 (motor) | Testes de integração passam sem alteração | `pytest tests/test_motor_integracao_regras.py` |
| 5 (dry run) | Resultado revisado e aprovado pelo usuário | Saída do script de dry run |
| 6 (migração) | Total AG+CO idêntico ao backup; zero `status` alterado | Comparar contagens antes/depois |
| 7 (tela) | Campos visíveis e corretos em localhost:5000 | Verificação visual por CADOC |
| 8 (limpeza) | Zero usos dos campos removidos em qualquer arquivo | `grep -r` antes de remover |

---

#### 13.11.7 Como o usuário valida — sem precisar ler código

> O usuário não precisa revisar código. A validação dele é sempre em linguagem humana ou visual.
> O Claude acompanha cada etapa e explica o que está acontecendo antes de qualquer ação.

**O que substitui a revisão técnica do diff:**

| Em vez de... | O usuário faz... |
|-------------|-----------------|
| Ler código linha por linha | Revisar o **dry run** (Fase 5): lista de threads com a regra prevista para cada uma — em texto simples |
| Entender o diff do PR | Receber um **resumo em linguagem simples** do que mudou, antes de qualquer junção de branches |
| Verificar o código | Abrir **localhost:5000** e confirmar que as threads aparecem com regra, pendente e motivo corretos |
| Confiar no CI cegamente | Receber o resultado do pytest explicado: "623 testes passaram, zero falhas, nada quebrou" |

**Fluxo de aprovação real (o que acontece na prática):**

1. **Dry run (Fase 5):** Claude mostra lista de threads + resultado previsto → usuário diz "faz sentido" ou "esse resultado está errado" → só então grava
2. **Pós-migração (Fase 6):** Claude mostra resumo: "X threads receberam regra corretamente, Y ficaram como LEGADO-SEM-REGRA" → usuário aprova antes de finalizar
3. **Tela (Fase 7):** usuário abre localhost:5000 e confere algumas threads reais por CADOC → Claude ajuda a navegar e interpretar o que aparece
4. **PR:** Claude resume em texto o que o PR muda → CI mostra verde → usuário clica em juntar

**Sobre o PR especificamente:**

O usuário nunca precisará ler o diff técnico do PR. O processo é:
- Claude abre o PR e descreve em português simples o que foi feito
- CI roda automaticamente e mostra verde ou vermelho
- Usuário confirma pela tela e pelo dry run que os resultados fazem sentido
- Usuário clica em "juntar" (merge) no GitHub — Claude mostra onde clicar quando chegar a hora

> ⚠️ **Nota:** o usuário nunca fez esse processo antes. Em cada fase, o Claude explica o que está
> acontecendo antes de qualquer ação, mostra o resultado esperado, e só avança com confirmação.
> Nada é feito silenciosamente.
