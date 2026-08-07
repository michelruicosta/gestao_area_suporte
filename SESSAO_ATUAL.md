# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-08-07) — Validação 634 + B1 + início análise C2

### Resumo do que foi feito (sessão de continuação 2 — 07/08/2026)

**O que fizemos:**

- **Validação das 634 threads "corretas":** 11 suspeitas identificadas por varredura automática; Michel revisou todas uma por uma. Todas corretas. Um caso (COS 4010 junho/2026) ficou em pendência para a fase 3.
- **B1 concluído:** `data/ids_incertos.txt` criado com 136 IDs:
  - 134 threads com `incerto=true` da R6
  - 2 threads Monte Bravo erroneamente classificadas como SUPORTE (adicionadas manualmente)
- **Descoberta Monte Bravo:** "Cadastro de Ações e Opções" deveria ser sempre DDR_2011, mas a IA classifica de forma inconsistente (3 corretos, 2 SUPORTE errado, 15 INCERTO). Causa: a IA busca confirmação no corpo; sem ela, vacila.
- **Análise dos 134 incertos por grupo:**
  - 68 sem sinal de CADOC (vários são DDR — Monte Bravo, OP. SELIC, TRUSTEE EXTRATO)
  - 66 com sinal de CADOC (precisam de regra por categoria)
  - **Conclusão: SUPORTE deve ser a última regra** (fallback), não a primeira

### Sessão anterior (continuação 1 — 07/08/2026)

- **Investigação LEC:** 4 threads INCERTO. Parágrafo LEC adicionado à spec + script multi-mensagem → causou regressões → revertido. LEC congelado em PENDENCIAS.
- **Descoberta estrutural:** spec §10 sem hierarquia de regras = causa raiz das regressões.
- **Validador `--filtrar-ids`:** adicionado — funcional.

---

### Estado atual

**Classificador:** `rodada-6-baseline` — 134 incertos (17,4%) — estado preservado
**ids_incertos.txt:** 136 IDs — pronto para fase 2
**Spec:** parágrafo LEC adicionado (não commitado — aguarda hierarquia §10 resolvida)
**Script classificador:** revertido para comportamento R6 (mensagens[0])
**Validador:** `--filtrar-ids` adicionado — funcional
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

**🔴 PRÓXIMA SESSÃO — Construir o gabarito (data/gabarito.json):**
Base completa: 136 threads categorizadas por Michel. O gabarito conterá exemplos de cada categoria para ensinar a IA pelo exemplo — especialmente os casos onde a regra existe na spec mas a IA ignora (EXTRATO COMPROMISSADA, OP. SELIC, Cadastro de Ações e Opções).

**Depois:** criar `data/ids_controle.txt` (~50 threads dos 634 corretos) para teste de regressão.

**Depois:** integrar gabarito ao `scripts/classificador_ia.py` e rodar nos 136 IDs para medir melhora.

Último /fechar: 2026-08-07 18:30 — memórias revisadas ✅ — 136 incertos categorizados por Michel; gabarito é a próxima etapa; IDs em ids_incertos.txt prontos para fase 2

---
