# Validação Completa — Tela E-mails: Classificação e Status

**Objetivo:** confirmar que todos os dados exibidos na tela estão corretos — sem erros de status, categoria, motivo, empresa ou remetente.
**Criado em:** 12/09/2026
**Regra:** cada parte tem um chat dedicado. Este documento é o mapa — qualquer chat futuro abre aqui e sabe exatamente onde parou.

---

## Mapa das partes

| Parte | O que valida | Estado | Detalhes |
|---|---|---|---|
| 1 | Status (AF / AC / Concluída) | ✅ Concluída (11/09/2026) | `validacao_status_suspeitos.md` |
| 2 | Categoria (DDR, DLO, SUPORTE...) | ✅ Concluída (14/09/2026) | abaixo |
| 3 | Motivo (texto do motivo na tela) | ✅ Concluída (14/09/2026) | abaixo |
| 4 | Empresa (nome da empresa na tela) | ⚠️ Achado registrado (14/09/2026) | abaixo |
| 5 | Remetente (quem enviou o último e-mail) | ✅ Concluída (14/09/2026) | abaixo |
| 6 | 364 threads sem status | ✅ Concluída (14/09/2026) | abaixo |

---

## ✅ Parte 1 — Status

**Resultado:** 22 suspeitos revisados · 8 erros corrigidos (Fix W, Fix X + 6 ajustes) · 0 regressões.
**Detalhes completos:** `documentações/validacao_status_suspeitos.md`
**Data:** 11/09/2026

---

## ✅ Parte 2 — Categoria

### O que é

Cada thread tem uma categoria atribuída pelo classificador: DDR_2011, DLO_2061, DRM_2060, DLI_2062, DRL_2160, SCD_4111, RETORNO_BACEN, SUPORTE, INTERNO. A validação confirma se as categorias exibidas na tela estão certas.

### Contexto

O classificador determinístico foi validado em 17/08/2026 com placar 764/768 (99,5%) numa amostra de 768 threads. Esse placar cobriu o conjunto histórico usado como gabarito. O que ainda não foi feito: varrer as **threads de produção atuais** para identificar categorias suspeitas, nulas ou com padrão inesperado.

### O que verificar

1. Threads sem categoria (campo `categoria = NULL ou vazio`)
2. Threads com mais de uma categoria (multi-CADOC) — estão corretas?
3. Amostra de cada categoria: os assuntos batem com o que se espera?

### Como fazer

- Script de levantamento no banco `data/gestao.db`
- Resultado: tabela de suspeitos para Michel revisar caso a caso

### Estado

⬜ Não iniciada — aguarda chat dedicado

---

## ⚠️ Parte 3 — Motivo

### O que é

Cada thread tem um campo `motivo_status` que aparece na tela como texto explicativo do status (ex.: "Cliente enviou informações e extratos — aguarda processamento"). A validação confirma se os textos estão corretos e atualizados.

### Contexto

Em 27/08/2026 foi feita uma análise completa dos motivos (76 distintos) com Michel. Vários textos novos foram aprovados mas ainda não foram implementados no código. Os motivos pendentes estão listados em `documentações/PENDENCIAS.md` → seção "TELAS — Melhorar textos do campo MOTIVO".

### O que verificar

1. Motivos aprovados por Michel (27/08) que ainda não foram implementados — quantas threads ainda mostram o texto antigo?
2. Threads com motivo genérico ("fundo de gaveta") — quais são?
3. Threads com motivo vazio — existem?

### Como fazer

- Cruzar os motivos aprovados (PENDENCIAS.md) com o banco
- Listar threads com cada motivo pendente de atualização
- Michel confirma ou ajusta — depois implementar tudo de uma vez

### Resultado (14/09/2026)

**ATIVAS (1.017 threads):** ✅ 0 sem motivo. Todos os textos aprovados já em uso.

**SEM RETORNO (700 threads):**
- ✅ 250 threads com textos antigos corrigidos via SQL direto (14/09/2026)
- ⚠️ 25 threads "Finaud escreveu — aguarda retorno do cliente" — aguardam implementação dos 3 submotivos faltantes (orientação técnica, planilha, reunião)
- ⚠️ 210 threads "Cliente escreveu — aguarda resposta da Finaud" (caixa preta) — maioria são entregas não detectadas com "Seguem"/"Anexo"/"Enviado"; aguardam expansão dos termos de detecção

**Complemento (14/09/2026):**
- ✅ Implementados 3 submotivos em `_determinar_status()`: "solicitou extrato ou planilha", "deu orientação técnica", "propôs reunião ou ligação"
- ✅ 235 threads SEM RETORNO recalculadas com código atualizado:
  - 126 → "Cliente enviou informações e extratos — aguarda processamento"
  - 62 → "Cliente fez solicitação — aguarda ação da Finaud"
  - 14 → "Cliente fez pergunta — aguarda resposta da Finaud"
  - 10 → "Finaud fez pergunta — aguarda resposta"
  - 10 → "Finaud deu orientação técnica — aguarda execução"
  - 8 → "Comunicado do BACEN — aguarda análise da Finaud"
  - 4 → "Finaud solicitou extrato ou planilha — aguarda envio"
  - 1 → "Comunicado do BACEN — aguarda retorno do cliente"

**Estado:** ✅ Concluída (14/09/2026) — todos os textos aprovados implementados; 485 threads SEM RETORNO corrigidas (250 via SQL + 235 via recálculo com código atualizado).

---

## ⚠️ Parte 4 — Empresa (Resumo Semanal)

### O que é

⚠️ **Correção de escopo (14/09/2026):** o campo `empresa` não aparece na tela de e-mails (`gestao_email.html` — confirmado). A empresa é calculada dinamicamente pela função `_extrair_empresa` em `scripts/resumo_semanal.py` e aparece apenas no **e-mail semanal automático** com os cards BACEN. Esta parte não é uma validação da tela de e-mails — é uma melhoria do Resumo Semanal.

### Contexto

215 threads ativas com CADOC retornam "Sem empresa identificada" na função `_extrair_empresa`. Dois grupos:

- **Grupo A (~90):** empresa visível no assunto, mas em padrões não reconhecidos ("COLUNA - ENVIAR DDR", "REMITLY : Movimento", "PI Exposure MiraeAsset...", etc.). Corrigível melhorando a função.
- **Grupo B (~125):** empresa não está no assunto ("DDR 2011 - data", "Posição de Câmbio..."). Requer mapeamento remetente → empresa.

### Estado

⚠️ Achado registrado — melhoria do Resumo Semanal, não da tela de e-mails. Ver PENDENCIAS.md → "MELHORIA — Empresa não identificada".

---

## ⚠️ Parte 5 — Remetente

### O que é

Cada thread tem um campo `remetente_principal` no banco. A validação confirma se o remetente exibido corresponde ao cliente real (não ao endereço mascarado do Google Groups).

### Contexto

Varredura de 26/08/2026 identificou **645 threads** com remetente mascarado (`suporte@finaud.com.br` no lugar do cliente real). A tela principal já trata isso via `Reply-To` e mostra o cliente correto. Mas o dado no banco está errado, o que afeta telas secundárias e exportações futuras.

A proposta de correção (coletor + migração histórica) está detalhada em `documentações/PENDENCIAS.md` → seção "BANCO/TELAS — Remetente mascarado".

### O que verificar

1. As 645 threads ainda têm remetente mascarado no banco?
2. A tela principal está mostrando o cliente correto em todos os casos?

### Como fazer

- Confirmar o número atual de threads mascaradas no banco de produção
- Executar a correção proposta (backup + migração) — ver PENDENCIAS.md

### Resultado (14/09/2026)

| | Agosto (26/08) | Hoje (14/09) |
|---|---|---|
| Total threads no banco | ~1.590 | 1.736 |
| Remetente mascarado | 645 (40,6%) | **820 (47,2%)** |
| Recuperáveis via Reply-To (já no JSON) | 645/645 | **759/820** |
| Sem Reply-To (precisam de re-busca via API) | 0 | **61** |

**Tela principal:** continua mostrando o cliente correto via Reply-To — sem impacto operacional para Michel. Problema restrito ao dado no banco (afeta telas secundárias e exportações futuras).

**Execução (14/09/2026):** 764 threads corrigidas via Reply-To já guardado no JSON. 62 sem Reply-To aguardam re-busca via Gmail API (trabalho separado — registrado em PENDENCIAS.md).

**Estado:** ✅ Concluída (14/09/2026) — 764 corrigidos; 62 restantes aguardam Gmail API.

---

## ✅ Parte 6 — 364 threads sem status

### O que é

Durante o Bloco 1 da validação de status (11/09/2026), foram encontradas 364 threads ativas com `status_workflow = NULL`. O sistema não calculou o status dessas threads.

### Contexto

Pelos primeiros 20 casos da lista (`validacao_status_suspeitos.md` — Tipo E), a maioria parece ser:
- E-mails automáticos (alertas Bacen, relatórios do RiskDriver, e-mails de marketing)
- Notificações de sistema (FogBugz, Meta, etc.)

Hipótese: essas threads nunca passaram pelo classificador e por isso não têm status. Se for isso, devem ser bloqueadas — não processadas.

### O que verificar

1. Quantas das 364 são automáticos/spam que deveriam ter sido filtrados?
2. Quantas são threads reais de clientes que ficaram sem status por algum bug?
3. Para as threads reais: recalcular o status
4. Para os automáticos: bloquear e remover da tela

### Como fazer

- Analisar a lista do Tipo E (já em `validacao_status_suspeitos.md`)
- Classificar cada uma: automático / thread real
- Decidir com Michel o que fazer com cada grupo

### Resultado (14/09/2026)

- No banco de produção: **0 threads** `destino='principal'` sem status — o pipeline já as processou.
- 372 threads em `destino='descartes'` sem status — revisadas e confirmadas como corretas:
  - 226 sem remetente: alertas BACEN, Leiautes, Relatórios do Serviço, FogBugz
  - 60 via suporte@finaud: notificações 3CX, marketing Muse/Meta, FogBugz
  - 54 riskdriver@finaud: relatórios diários automáticos
  - 27 contato@finaud: atualizações BACEN – Riscos
  - 2 FogBugz: testes de notificação
  - 3 individuais revisados com Michel: cancelamento Fair Corretora, cancelamento Nova Futura, convite Andrea — todos confirmados como descartes corretos.

**Estado:** ✅ Concluída — nada a corrigir.

---

## Ordem sugerida de execução

1. ✅ ~~Parte 1 — Status~~ (concluída)
2. ✅ ~~Parte 6 — 364 sem status~~ (concluída)
3. ✅ ~~Parte 2 — Categoria~~ (concluída — 0 sem categoria; multi-CADOC DLI/DLO confirmado como comportamento esperado)
4. ✅ ~~Parte 3 — Motivo~~ (concluída — 485 threads corrigidas: 250 via SQL + 235 via recálculo + 3 submotivos implementados)
5. ✅ ~~Parte 5 — Remetente~~ (concluída — 764 corrigidos via Reply-To; 62 aguardam Gmail API)
6. ⚠️ Parte 4 — Empresa (276 casos; achado registrado)
7. Parte 3 complemento — implementar detecção "Seguem"/"Anexo"/"Enviado" + 3 submotivos "Finaud escreveu"
