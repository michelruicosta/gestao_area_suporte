# Contratos do Pipeline — Oráculo 360 Finaud

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

> **Regra de ouro:** qualquer correção que altere um campo de **saída** de um script
> deve disparar revisão obrigatória no script seguinte que consome esse campo.
>
> Antes de aplicar uma correção: verificar a coluna "Lido por" do campo afetado
> e checar se o comportamento esperado no script seguinte ainda é válido.

**Atualizado:** 2026-06-10

---

## Fluxo geral

```
Script 01 → JSON 01 (bruto Gmail)
Script 02 → coleta IMAP, grava JSON 01
Script 05 → lê JSON 02, grava JSON 02 (classifica e enriquece)
Script 09 → lê JSON 02 + cache OCR + concluídas, grava JSON 03
Script 11 → lê JSON 03, grava threads_aguardando_auto + threads_concluidas_auto
```

---

## Script 05 — Classificador de e-mails

**Lê:** `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json`

**Grava:** `data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json` (atualiza in-place)

### Campos que produz / atualiza

| Campo | Tipo | Usado por | Observação |
|-------|------|-----------|------------|
| `cadoc` | string | Script 09, Motor | Identificador do CADOC regulatório (ex: "DDR4111"). Script 09 usa para prazo e exibição. |
| `data_email` | string DD/MM/AAAA | Script 09 | Base para calcular prazo_limite. Formato com `/` obrigatório. |
| `prazo_limite` | string DD/MM/AAAA | Script 09, Motor | Prazo regulatório calculado. Motor exige `/` no valor para parsear. |
| `exibir_card` | bool | Script 09 | False = invisível no painel (Risk Driver, spam). |
| `tipo_painel` | string | Script 09 | "REGULATORIO", "SUPORTE", etc. |
| `contato_origem.lado` | string | Script 09, Motor | "FINAUD", "CLIENTE", "EXTERNO". Determina direção da bola. |
| `contato_origem.nome` | string | Tela | Nome decodificado (MIME). Corrigido em #PF6. |
| `contato_destino.lado` | string | Motor (helpers) | Necessário para _facr, _fpic, _fec (exigem F→C). |
| `responsavel` | string | Script 09, Tela | Analista Finaud responsável. Pode ser inferido pelo script 09. |
| `remetente` | string | Script 09 | Adicionado em #PF43 — ausente em versões anteriores. |
| `finaud_somente_cc` | bool | Script 09 | True = Finaud estava só no CC. Script 09 força exibir_card=True. |
| `relatorio_interno_risk_driver` | bool | Motor | True = thread invisível para o motor. |

### Regras críticas

- `cadoc` derivado do **assunto** tem prioridade sobre corpo (desde #PF23 Sit.2)
- `prazo_limite` usa `calcular_prazo_limite(data, cadoc)` — resultado em DD/MM/AAAA
- Risk Driver: `cadoc = "SUPORTE"`, `prazo_limite` em D+5 úteis (desde #PF30B)

---

## Script 09 — Integrador de dados do painel

**Lê:**
- `02_classificação_dados_brutos_gmail_editado.json`
- `threads_concluidas_auto.json` + `threads_concluidas_manual.json` (ressurreição)
- `cache_texto_imagens_validado.json` (preservação OCR)
- `03_integrador_dados_site.json.backup` (OCR anterior)

**Grava:** `data/json/pipeline/03_integrador_dados_site.json`

### Estrutura do JSON 03

```json
{
  "gerado_em": "ISO",
  "total": N,
  "total_threads": N,
  "eventos": [ ... ],   // um por email; consumido por /api/dados e /api/operacional
  "threads": [ ... ]    // uma por thread; consumido por /api/threads (modal)
}
```

### Campos que produz em `eventos[]`

| Campo | Tipo | Usado por | Observação |
|-------|------|-----------|------------|
| `threadId` | string | Motor, Tela | Identificador único da thread. |
| `cadoc` | string | Motor, Tela | Herdado do script 05. |
| `data_iso` | string AAAA-MM-DD | Motor, Tela | Data do e-mail em ISO. |
| `lista_prazos` | list | Motor, Tela | Prazos calculados. Motor usa para alertas. |
| `status_processo` | string | Motor | Sempre "PENDENTE" no JSON 03 — Motor é fonte de verdade de status. |
| `relatorio_interno_risk_driver` | bool | Motor | Copiado do script 05. |
| `responsavel` | string | Tela | Inferido pelo script 09 se "Suporte Finaud" (#PF42). |
| `responsabilidade` | string | Tela | "FINAUD" ou "CLIENTE". |
| `lado_responsavel` | string | Tela | Lado de quem tem a bola. |

### Campos que produz em `threads[].mensagens[]`

| Campo | Tipo | Usado por | Observação |
|-------|------|-----------|------------|
| `contato_origem.lado` | string | Motor | "FINAUD", "CLIENTE", "EXTERNO". |
| `contato_origem.email` | string | Motor | Email do remetente. Detecta spam. |
| `corpo_limpo` | string | Motor, Tela | Texto limpo (sem HTML, assinaturas, CSS). #PF33. |
| `texto_imagens` | string | Motor (RETORNO_BACEN) | OCR das imagens. Preservado entre execuções. |
| `remetente_original_fwd` | string | Template | Remetente original de encaminhamentos. #PF45. |
| `anexos` | list | Motor | Nomes de arquivos anexados. |

### Regras críticas

- `corpo_limpo` gerado por `limpar_corpo_email()` — remove `<style>`, `<script>`, `<head>` inteiros (#PF33)
- `remetente_original_fwd` extraído por `_extrair_remetente_original_fwd()` — prioriza @bcb.gov.br (#PF45)
- Thread em `threads_concluidas` com nova mensagem → removida das concluídas → reprocessada pelo motor (#PF32)
- `texto_imagens` preservado do backup/cache — não sobrescrever com string vazia

---

## Script 11 — Motor de triagem (scripts/triagem/motor.py)

**Lê:**
- `03_integrador_dados_site.json` (eventos + threads com mensagens)
- `threads_aguardando_auto.json` (estado atual)
- `threads_concluidas_auto.json` (estado atual)

**Grava:**
- `threads_aguardando_auto.json`
- `threads_concluidas_auto.json`

### Campos que consome de JSON 03

| Campo | De onde vem | Para quê |
|-------|-------------|----------|
| `eventos[].threadId` | Script 09 | Identificar a thread |
| `eventos[].cadoc` | Script 05 → 09 | Selecionar módulo de triagem |
| `eventos[].relatorio_interno_risk_driver` | Script 05 → 09 | Se True: thread invisível ao motor |
| `threads[].mensagens[].contato_origem.lado` | Script 09 | Determinar lado da última mensagem |
| `threads[].mensagens[].contato_origem.email` | Script 09 | Detectar spam |
| `threads[].mensagens[].corpo_limpo` | Script 09 | Avaliar regras (_facr, _fec, _fpic, _ffar) |
| `threads[].mensagens[].texto_imagens` | Script 09 | Regras RETORNO_BACEN |

### Campos que grava em `threads_aguardando_auto[]`

| Campo | Tipo | Observação |
|-------|------|------------|
| `threadId` | string | Obrigatório. Único na lista. |
| `tipo` | string | "ACAO_INTERNA", "RESPOSTA_CLIENTE" ou "ENTREGA_CLIENTE" |
| `alvo_triagem_auto` | string | CADOC que gerou a triagem (ex: "DDR4111") |
| `origem_triagem_auto` | bool | True = automático; False = manual (não reprocessado) |
| `motivo` | string | Texto descritivo do motivo de aguardar |
| `prazo` | string | Prazo herdado do evento |
| `empresa` | string | Nome do cliente |

### Cadeia de regras do pós-processamento

```
Regra 1 (_fec)  → CONCLUIDO se Finaud entregou/transmitiu
Regra 2 (_cac)  → CONCLUIDO se cliente confirmou
Regra 4 (_ffc)  → CONCLUIDO se F→F conclusivo
Regra 4b (_ffar, pré-computado antes do elif) → CONCLUIDO ou AGUARDANDO F→F relatorio
Regra 3 (_cpa)  → preserva aguardando se cliente pediu algo
Regra 5         → ENTREGA_CLIENTE se Finaud entregou arquivo ao cliente transmitir
Regra 6 (_fpic) → RESPOSTA_CLIENTE se Finaud pediu insumo ao cliente
Regra 7 (_facr) → CONCLUIDO se Finaud agradeceu sem pedido/pergunta
```

**Atenção:** Regra 4b DEVE ser pré-computada antes do if/elif para não bloquear Regras 5/6/7 (#PF47).

---

## Invariantes do sistema (não podem ser violados)

| # | Invariante | Detectado por |
|---|------------|---------------|
| I1 | Nenhum threadId aparece em aguardando E concluidas ao mesmo tempo | test_idempotencia_pipeline.py |
| I2 | Cada threadId aparece no máximo uma vez em aguardando_auto | test_idempotencia_pipeline.py |
| I3 | Cada threadId aparece no máximo uma vez em threads[] do JSON 03 | test_idempotencia_pipeline.py |
| I4 | threads_aguardando_auto.tipo ∈ {ACAO_INTERNA, RESPOSTA_CLIENTE, ENTREGA_CLIENTE} | pipeline_validar.py --schema |
| I5 | JSON 03: % de eventos sem cadoc ≤ 5% | pipeline_validar.py --schema |
| I6 | threads_concluidas_auto: % sem motivo_triagem_auto ≤ 2% | pipeline_validar.py --schema |
| I7 | Rodar script duas vezes não gera duplicatas | test_idempotencia_pipeline.py |
| I8 | Thread com origem_triagem_auto=False não é reprocessada pelo motor | Motor: guard de imutabilidade |

---

## Como usar na prática

**Antes de qualquer correção em script 05:**
1. Verificar quais campos da tabela acima são afetados
2. Checar a coluna "Usado por" — se Motor estiver listado, revisar a cadeia de regras
3. Se alterar formato de `prazo_limite` ou `data_email`: confirmar que Motor ainda parseia corretamente

**Antes de qualquer correção em script 09:**
1. Verificar se o campo alterado está na tabela de `threads[].mensagens[]`
2. Se alterar `corpo_limpo`, `contato_origem.lado` ou `texto_imagens`: rodar test_regressoes_pf47_pf46_pf35.py

**Antes de qualquer correção no Motor (script 11):**
1. A cadeia de regras é sensível à ordem — não reordenar sem simular
2. Regra 4b deve SEMPRE ser pré-computada (fix #PF47)
3. Rodar: `python scripts/pipeline_validar.py --schema --snapshot` antes; `--diff` depois
