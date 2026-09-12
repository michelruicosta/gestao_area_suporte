# Validação Completa — Tela E-mails: Classificação e Status

**Objetivo:** confirmar que todos os dados exibidos na tela estão corretos — sem erros de status, categoria, motivo, empresa ou remetente.
**Criado em:** 12/09/2026
**Regra:** cada parte tem um chat dedicado. Este documento é o mapa — qualquer chat futuro abre aqui e sabe exatamente onde parou.

---

## Mapa das partes

| Parte | O que valida | Estado | Detalhes |
|---|---|---|---|
| 1 | Status (AF / AC / Concluída) | ✅ Concluída (11/09/2026) | `validacao_status_suspeitos.md` |
| 2 | Categoria (DDR, DLO, SUPORTE...) | ⬜ Pendente | abaixo |
| 3 | Motivo (texto do motivo na tela) | ⬜ Pendente | abaixo |
| 4 | Empresa (nome da empresa na tela) | ⬜ Pendente | abaixo |
| 5 | Remetente (quem enviou o último e-mail) | ⬜ Pendente | abaixo |
| 6 | 364 threads sem status | ⬜ Pendente | abaixo |

---

## ✅ Parte 1 — Status

**Resultado:** 22 suspeitos revisados · 8 erros corrigidos (Fix W, Fix X + 6 ajustes) · 0 regressões.
**Detalhes completos:** `documentações/validacao_status_suspeitos.md`
**Data:** 11/09/2026

---

## ⬜ Parte 2 — Categoria

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

## ⬜ Parte 3 — Motivo

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

### Estado

⬜ Não iniciada — depende de decisão sobre os motivos pendentes (PENDENCIAS.md) primeiro

---

## ⬜ Parte 4 — Empresa

### O que é

Cada thread tem um campo `empresa` exibido na tela. A validação confirma se o nome da empresa está correto para todas as threads ativas.

### Contexto

Identificados 24 casos "Sem empresa identificada" no Resumo Semanal (cards BACEN). São threads onde o assunto do e-mail não contém o nome da empresa de forma legível para o sistema.

### O que verificar

1. Quantas threads ativas têm `empresa = NULL ou "Sem empresa identificada"`?
2. Para cada uma: ler o assunto e remetente e determinar o nome correto
3. Atualizar o banco com o nome certo

### Como fazer

- Script de levantamento no banco
- Resultado: lista de threads sem empresa para Michel completar

### Estado

⬜ Não iniciada — aguarda chat dedicado

---

## ⬜ Parte 5 — Remetente

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

### Estado

⬜ Não iniciada — aguarda chat dedicado

---

## ⬜ Parte 6 — 364 threads sem status

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

### Estado

⬜ Não iniciada — aguarda chat dedicado

---

## Ordem sugerida de execução

1. ✅ ~~Parte 1 — Status~~ (concluída)
2. **Parte 6 — 364 sem status** (mais simples: a maioria parece automático)
3. **Parte 4 — Empresa** (24 casos — escopo pequeno e bem delimitado)
4. **Parte 2 — Categoria** (precisa de script novo)
5. **Parte 3 — Motivo** (depende de decisões pendentes no PENDENCIAS.md)
6. **Parte 5 — Remetente** (maior esforço — migração de banco)
