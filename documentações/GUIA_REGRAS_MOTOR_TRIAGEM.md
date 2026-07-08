# Guia de Regras do Motor de Triagem — Oráculo 360 Finaud

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

> **Para quem é este documento:** referência rápida para entender o que o sistema verifica para
> classificar cada conversa como AGUARDANDO ou CONCLUÍDO. Organizado por categoria de CADOC.
> Atualizado em: 2026-06-29

---

## Como funciona o motor

O motor de triagem roda em duas etapas para cada thread:

1. **Regras do supervisor** — cada categoria de CADOC tem sua própria lista de regras que verificam
   o estado da última mensagem e o histórico da conversa.
2. **Pós-processamento universal** — regras que se aplicam a **todos os CADOCs** após as regras
   do supervisor. Ficam em `motor.py` e cobrem casos transversais.

As regras de CONCLUÍDO são verificadas primeiro. Se nenhuma disparar, o motor verifica as regras
de AGUARDANDO. Se nenhuma das duas disparar, a thread fica sem triagem.

---

## Regras universais (pós-processamento — `motor.py`)

Aplicam-se a **todos os 10 CADOCs**, na ordem abaixo. A primeira que disparar encerra a análise.

| Regra | O que detecta | Resultado |
|-------|--------------|-----------|
| **R0 (M30)** | Mensagem de "recall" (e-mail retirado) | CONCLUÍDO |
| **R0b** | Spam / newsletter automático sem demanda real | CONCLUÍDO |
| **R0c** | Comunicado interno F→F (aviso automático, RH, norma, teste) | CONCLUÍDO |
| **R1** | Finaud entregou arquivo ou realizou ação conclusiva | CONCLUÍDO |
| **R1b** | Finaud deu instrução conclusiva ao cliente ("para solucionar, faça X") | CONCLUÍDO |
| **R2** | Cliente agradeceu o recebimento sem novo pedido | CONCLUÍDO |
| **R2c** | Cliente confirmou que executou a ação que a Finaud pediu | CONCLUÍDO |
| **R2b** | Cliente confirmou conclusão (substituiu doc, arquivo aceito no BACEN) | CONCLUÍDO |
| **R1c** | Finaud realizou reset de senha / liberou acesso | CONCLUÍDO |
| **R1d** | Finaud confirmou que o arquivo foi aceito no BACEN/STA | CONCLUÍDO |
| **R1e** | Finaud entregou análise conclusiva respondendo pergunta do cliente | CONCLUÍDO |
| **R6** | Finaud confirmou reunião agendada | CONCLUÍDO |
| **R4** | F→F conclusivo — colaborador confirmou internamente que tarefa foi concluída | CONCLUÍDO |
| **R4b** | F→F com agradecimento / envio de relatório final | CONCLUÍDO |
| **R9-A** | Thread no pós-CO com última msg C→F com insumo do cliente → reverte | AGUARDANDO |
| **R9-B** | Thread no pós-CO com Finaud pedindo insumo sem remessa → reverte | AGUARDANDO |
| **R9-C (M31)** | Thread fechada com msg nova do cliente após a data de conclusão → reverte | AGUARDANDO |

---

## Regras por CADOC

### Legenda das colunas

- **Gatilho** — qual padrão na última mensagem (ou no histórico) faz a regra disparar
- **Exige histórico Finaud** — a regra só funciona se a Finaud já tiver respondido antes nessa conversa
- **Resultado** — o status que a regra produz

---

### DDR_2011 · DRL_2160 · 4111

Supervisor: `ddr4111.py`

#### Regras de CONCLUÍDO

**Globais (verificadas em qualquer última mensagem):**

| # | Regra | Gatilho | Resultado |
|---|-------|---------|-----------|
| 1 | §3.1 transmitido no BACEN | Texto confirma que o arquivo foi transmitido ao BACEN | CONCLUÍDO |
| 2 | §5 remessa Finaud → cliente | Finaud enviou arquivo DDR/DRL/4111 ao cliente | CONCLUÍDO |
| 3 | §5b RES | Finaud enviou resposta formal com assunto + corpo mínimo | CONCLUÍDO |
| 4 | §5c texto conclusivo | Finaud encerrou com fecho operacional ("segue para transmissão", etc.) | CONCLUÍDO |

**Quando a última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita da Finaud | Sim (via §4d) | CONCLUÍDO |
| 2 | §4e DDR | Cliente só agradeceu / confirmou recebimento (curto, sem novo pedido) | Não¹ | CONCLUÍDO |
| 3 | G3 | Cliente disse "de acordo", "ok", "certo" após instrução da Finaud | Sim | CONCLUÍDO |

> ¹ DDR/DRL/4111 usam o detector original — não exige msg prévia da Finaud no histórico.
> Os demais 8 CADOCs usam a versão com salvaguarda.

**Regras de AGUARDANDO:**

| Última msg de | Regra | Gatilho | Fila de espera |
|---------------|-------|---------|----------------|
| Finaud → cliente | §3-inv | Finaud pediu insumos ao cliente | Aguarda cliente |
| Finaud → cliente | §3.5 | Finaud só reconheceu recebimento (sem remessa) | Aguarda Finaud |
| Finaud → cliente | §3.5+ | Finaud só agradeceu sem msg prévia do cliente | Aguarda Finaud |
| Finaud → cliente | §3-fc | Finaud respondeu em análise (corpo ≥ 40 chars) | Aguarda Finaud |
| F → F interna | — | Última msg é entre colaboradores da Finaud | Aguarda Finaud |
| Cliente → Finaud | §3 | Cliente enviou insumo / pergunta (catch-all) | Aguarda Finaud |

**Configurações especiais:**
- §5-anexo: ✅ ativo (detecta arquivo DDR/DRL/4111 em anexo)
- §3.5+: ✅ ativo
- §6 cluster: ✅ ativo
- §6b espelho: ✅ ativo

---

### SUPORTE

Supervisor: `suporte.py`

#### Regras de CONCLUÍDO

**Globais:**

| # | Regra | Gatilho | Resultado |
|---|-------|---------|-----------|
| 1 | §3.1 transmitido | Texto confirma transmissão ao BACEN | CONCLUÍDO |
| 2 | §5 remessa | Finaud enviou arquivo ao cliente | CONCLUÍDO |
| 3 | §5b RES | Resposta formal com assunto + corpo mínimo | CONCLUÍDO |
| 4 | §5c texto conclusivo | Fecho operacional da Finaud | CONCLUÍDO |

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e SUPORTE | Cliente só agradeceu (curto, sem novo pedido) | Não¹ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

> ¹ Mesmo comportamento do DDR — detector original sem salvaguarda de histórico.

**Configurações especiais:**
- §5-anexo: ❌ inativo
- §3.5+: ✅ ativo
- §6b espelho: ✅ ativo

---

### DLO_2061

Supervisor: `dlo.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e DLO | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ✅ ativo (detecta arquivo DLO em anexo)
- §3.5+: ✅ ativo (Finaud agradece sem msg prévia do cliente → AGUARDANDO Finaud)
- §6b espelho: ✅ ativo

---

### DLI_2062

Supervisor: `dli.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e DLI | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ✅ ativo (detecta arquivo DLI em anexo)
- §3.5+: ❌ inativo
- §6b espelho: ✅ ativo

---

### DRM_2060

Supervisor: `drm.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e DRM | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ✅ ativo (detecta arquivo DRM em anexo)
- §3.5+: ✅ ativo
- §6b espelho: ✅ ativo

---

### S5

Supervisor: `s5.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e S5 | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ❌ inativo (histórico confirma: Finaud não envia arquivos via e-mail nesse CADOC)
- §3.5+: ✅ ativo
- §6b espelho: ✅ ativo

---

### RETORNO_BACEN

Supervisor: `retorno_bacen.py`

#### Regras de CONCLUÍDO

**Globais:**

| # | Regra | Gatilho | Resultado |
|---|-------|---------|-----------|
| 1 | §3.1 transmitido | Texto confirma transmissão ao BACEN | CONCLUÍDO |
| 2 | §5 remessa | Finaud enviou arquivo ao cliente | CONCLUÍDO |
| 3 | §5b RES | Resposta formal com assunto + corpo mínimo | CONCLUÍDO |
| 4 | §5c texto conclusivo | Fecho operacional da Finaud | CONCLUÍDO |
| 5 | §5d | Finaud orientou / entregou conclusivamente — bola no cliente | CONCLUÍDO |

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e RB | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | §4f-rb | Cliente confirmou que o protocolo foi aceito pelo BACEN | — | CONCLUÍDO |
| 4 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ❌ inativo
- §3.5+: ❌ inativo
- §6b espelho: ✅ ativo

---

### DRSAC

Supervisor: `drsac.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e DRSAC | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ❌ inativo (histórico confirma: Finaud não envia arquivos nesse CADOC)
- §3.5+: ✅ ativo
- §6b espelho: ✅ ativo

---

### FORCAPITAL

Supervisor: `forcapital.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e FORCAPITAL | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ❌ inativo (histórico confirma: Finaud não envia arquivos nesse CADOC)
- §3.5+: ✅ ativo
- §6b espelho: ✅ ativo

---

### 6209

Supervisor: `cadoc6209.py`

#### Regras de CONCLUÍDO

**Globais:** idênticas ao DDR (§3.1, §5, §5b, §5c).

**Última mensagem é do cliente para a Finaud:**

| # | Regra | Gatilho | Exige hist. Finaud | Resultado |
|---|-------|---------|-------------------|-----------|
| 1 | §4d | Cliente agradeceu após remessa explícita | Sim | CONCLUÍDO |
| 2 | §4e 6209 | Cliente só agradeceu (curto, sem novo pedido) | **Sim** ✅ | CONCLUÍDO |
| 3 | G3 | "de acordo", "ok", "certo" após instrução | Sim | CONCLUÍDO |

**Configurações especiais:**
- §5-anexo: ❌ inativo (histórico confirma: Finaud não envia arquivos nesse CADOC)
- §3.5+: ✅ ativo
- §6b espelho: ✅ ativo

---

## Quadro comparativo — configurações por CADOC

| CADOC | §5-anexo | §3.5+ | §4e | §5d | §4f-rb | §6b espelho |
|-------|---------|-------|-----|-----|--------|-------------|
| DDR_2011 / DRL_2160 / 4111 | ✅ | ✅ | ✅ (sem guard) | ❌ | ❌ | ✅ |
| SUPORTE | ❌ | ✅ | ✅ (sem guard) | ❌ | ❌ | ✅ |
| DLO_2061 | ✅ | ✅ | ✅ (com guard) | ❌ | ❌ | ✅ |
| DLI_2062 | ✅ | ❌ | ✅ (com guard) | ❌ | ❌ | ✅ |
| DRM_2060 | ✅ | ✅ | ✅ (com guard) | ❌ | ❌ | ✅ |
| S5 | ❌ | ✅ | ✅ (com guard) | ❌ | ❌ | ✅ |
| RETORNO_BACEN | ❌ | ❌ | ✅ (com guard) | ✅ | ✅ | ✅ |
| DRSAC | ❌ | ✅ | ✅ (com guard) | ❌ | ❌ | ✅ |
| FORCAPITAL | ❌ | ✅ | ✅ (com guard) | ❌ | ❌ | ✅ |
| 6209 | ❌ | ✅ | ✅ (com guard) | ❌ | ❌ | ✅ |

**Legenda:**
- **§5-anexo** — detecta arquivo do CADOC em anexo numa msg da Finaud → CONCLUÍDO
- **§3.5+** — Finaud só agradece sem msg prévia do cliente → AGUARDANDO Finaud
- **§4e** — cliente só agradece (curto, sem novo pedido) → CONCLUÍDO
- **§4e com guard** — exige pelo menos 1 msg da Finaud no histórico antes de concluir
- **§5d** — Finaud orientou / entregou conclusivamente (específico RETORNO_BACEN)
- **§4f-rb** — cliente confirmou protocolo aceito no BACEN (específico RETORNO_BACEN)
- **§6b espelho** — threads com mesmo núcleo de assunto são espelhadas (se uma fecha, as outras fecham)

---

## Glossário rápido das regras

| Sigla | Nome completo | O que verifica |
|-------|--------------|----------------|
| §3 | Insumo do cliente | Última msg é do cliente → aguarda Finaud processar |
| §3-inv | Pedido de insumo pela Finaud | Finaud pediu documentos/dados ao cliente → aguarda cliente |
| §3.5 | Reconhecimento sem remessa | Finaud só disse "recebi, aguarde" → aguarda Finaud agir |
| §3.5+ | Agradecimento sem msg prévia | Finaud agradece mas cliente nunca tinha mandado nada antes → aguarda Finaud |
| §3.1 | Transmitido no BACEN | Texto menciona que arquivo já foi transmitido ao BACEN → concluído |
| §4d | Agradecimento pós-remessa | Cliente agradece APÓS remessa explícita da Finaud → concluído |
| §4e | Agradecimento curto geral | Cliente só agradece/confirma recebimento (sem novo pedido) → concluído |
| §4f-rb | Protocolo aceito BACEN | Cliente confirma que BACEN aceitou o protocolo → concluído (só RETORNO_BACEN) |
| §5 | Remessa Finaud | Finaud enviou o arquivo do CADOC → concluído |
| §5b | RES formal | Finaud respondeu com assunto "RES:" e corpo mínimo → concluído |
| §5c | Texto conclusivo | Finaud encerrou com frase de fecho operacional → concluído |
| §5d | Orientação conclusiva | Finaud orientou o cliente sobre como resolver → concluído (só RETORNO_BACEN) |
| §6 | Cluster de threads | Threads com mesmo cliente e mesma demanda são agrupadas |
| §6b | Espelho de assunto | Threads com mesmo núcleo de assunto espelham o status entre si |
| G3 | Concordância pós-instrução | Cliente disse "de acordo / ok / certo" após instrução da Finaud → concluído |

---

*Arquivo gerado em 2026-06-29 | Fonte: `scripts/triagem/` — verificado após commit `0de9f27`*
