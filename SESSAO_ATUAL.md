# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-08-07) — Investigação LEC + descoberta de hierarquia de regras

### Resumo do que foi feito (sessão de continuação — 07/08/2026)

Sessão focada em investigar o LEC e na descoberta de um problema estrutural na spec.

**O que fizemos:**

- **Investigação LEC completa:** 4 threads com "LEC" no assunto eram INCERTO no R6. Causas identificadas:
  - Spec não explicava que LEC é **exclusiva** do DLO 2061 — só dizia que era um sinal de Alta
  - Script lia só `mensagens[0]`, perdendo anexos de mensagens posteriores
- **Parágrafo LEC adicionado à spec §10 DLO_2061:** explicação de que LEC = DLO_2061 sempre, mesmo sem COSIF
- **Script atualizado** para ler até 5 mensagens (últimas) e coletar anexos de todas as mensagens
- **Validador: argumento `--filtrar-ids` adicionado** — permite rodar só um subconjunto de threads por arquivo de IDs
- **Teste das 88 threads** (4 LEC + 84 DLO/DLI corretos do R6):
  - Com ambas as mudanças (spec + script): 2 regressões
  - Com só spec (script revertido): 3 incertos, sendo 2 regressões
  - **Conclusão: a mudança na spec causou regressões** — AI ficou mais exigente sobre anexos em DLO genérico
- **Script revertido** para estabilidade (volta ao comportamento do R6)
- **LEC congelado em PENDENCIAS** — retomar após hierarquia do §10 estar resolvida
- **Descoberta estrutural:** a spec §10 não tem hierarquia de regras — regras amplas conflitam com específicas e a IA não sabe qual aplicar. Isso é a causa raiz das regressões.
- **Decisão de abordagem:** próximo passo é revisar o §10 completo com hierarquia explícita (mais específico → mais geral)

---

### Estado atual

**Classificador:** `rodada-6-baseline` — 134 incertos (17,4%) — estado preservado, sem regressão commitada
**Spec:** parágrafo LEC adicionado (não commitado ainda — aguarda resolução das regressões)
**Script classificador:** revertido para comportamento R6 (mensagens[0])
**Validador:** `--filtrar-ids` adicionado — funcional
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

**🔴 PRIMEIRO — Revisar §10 da spec com hierarquia de regras:**
Ler cada categoria, reescrever do mais específico para o mais geral, adicionar instrução explícita de prioridade. Testar amostra de 20 após cada categoria. Só rodar 768 se amostra não regredir. Meta: < 134 incertos sem regressão.

**Depois:** retomar LEC (congelado) — 1 thread ainda INCERTO (WNT DTVM), 2 regressões a resolver.

Último /fechar: 2026-08-07 — memórias revisadas ✅ — investigação LEC concluída; descoberta: spec sem hierarquia de regras é a causa raiz das regressões

---
