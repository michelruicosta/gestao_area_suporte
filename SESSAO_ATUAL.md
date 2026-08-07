# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-08-06/07) — Rodada 6 + mapa dos 134 incertos

### Resumo do que foi feito

Sessão de validação: Rodada 5 → Rodada 6. O trabalho girou em torno de entender e reduzir os incertos do classificador.

**O que fizemos:**

- **R5 commitada** com tag `rodada-5-baseline` — 195 incertos (25,4%), primeiro baseline determinístico com `temperature=0`.
- **Regra DDR específica adicionada à spec §10:** 4 padrões de assunto sem "DDR" explícito → DDR_2011 imediato (PI Exposure, PCAM, Compromissada, Cadastro de Ações e Opções).
- **Regra geral de desambiguação testada e rejeitada:** instrução no `classificador_ia.py` para usar assunto quando incerto causou regressão (PI Exposure → S5). Revertida via `git restore`.
- **R6 rodada:** 768 threads → 634 corretas + **134 incertos (17,4%)**. Melhora de 61 casos.
- **Mapa dos 134 incertos concluído:**
  - 97 têm sinal no assunto → fallback por keyword é possível
  - ~25 são SUPORTE sem nenhum sinal de CADOC
  - 14 genuinamente ambíguos → Michel classificou todos: 6 DDR, 6 SUPORTE, 2 DLO/LEC, 1 precisa do corpo
- **Descoberta crítica:** "Planilha LEC" JÁ está na spec como sinal de Alta para DLO_2061 — mas a IA ainda retornou INCERTO para 2 threads com esse assunto. Causa não investigada.
- **Decisão de abordagem:** em vez de regras de keyword, ensinar o **significado dos termos** (VMTM, POSICAO, LEC etc.) para que a IA raciocine corretamente.
- **R6 tagueada** como `rodada-6-baseline`. Commit: `cdfaf01`.

---

### Estado atual

**Classificador R6:** `rodada-6-baseline` — 134 incertos (17,4%) — estado salvo e rastreável
**Mapa dos incertos:** ✅ concluído — 97 solucionáveis, ~25 SUPORTE, 14 analisados com Michel
**Abordagem decidida:** ensinar significado dos termos na spec (uma mudança por vez + amostra de 20)
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main` (10 commits à frente do origin)

---

### Próximos passos

**🔴 PRIMEIRO — investigar por que "Planilha LEC" é INCERTO:**
A spec já tem a regra (DLO_2061, sinal Alta). A IA ignorou. Antes de adicionar novas regras, entender o motivo — senão corremos o risco de R3 novamente.

**Depois (uma mudança por vez, amostra de 20 após cada):**
1. Fechar os 6 DDR sem sinal (VMTM, POSICAO, Cadastro Operações, Criação COSIF, CNPJ fundo, Doc. 2011-LIM) — significado dos termos no §10 DDR_2011
2. Verificar os 3 keywords DDR que faltaram (Posição de Câmbio, FLUXO DE CAIXA) — já estão ou faltam na spec?
3. Decidir o que fazer com "ARQUIVOS" (Fair Corretora) — precisa do corpo

Último /fechar: 2026-08-07 — memórias revisadas ✅ — R6 baseline + mapa dos 134 incertos concluído; próximo: investigar LEC

---
