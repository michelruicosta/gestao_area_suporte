# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-08-14) — Correções C40–C46 do classificador determinístico

### Resumo do que foi feito hoje

**Contexto:** após o /fechar de 12/08, sessões em 13/08 e 14/08 continuaram as correções do classificador determinístico, atacando os grupos D e F do mapeamento de erros.

**C40 — DDR2011 colado no assunto detectado:**
Assuntos como "DDR2011 - mês/2026" sem espaço não disparavam DDR. Regex ajustada.

**C41 — DLO+DLI no assunto mas DLI era referência, não entrega:**
Quando o assunto tem DLI+DLO mas só DLI aparece explicitamente, 2061 era referência de arquivo. Guard adicionado na Camada 1b.
Thread corrigida: "Re: Arquivo 2061 e 2062. Segue o DLI. ACCREDITO."

**C42 — DRL-LEC no assunto é template DLO, não entrega DRL:**
LEC com lookbehind detectado: "DRL-LEC" remove a categoria DRL indevida. 
Thread corrigida: "Re: Planilha DRL-LEC Junho/2026".

**C43 — VMTM removido de _DDR_PADROES:**
VMTM é componente de cálculo, não entrega de CADOC. Removido para evitar falsos DDR.
(Sub-padrão 2a do Grupo A: VMTM no corpo gera DDR indevido — documentado como não corrigível.)

**C44 — COS4016 no corpo de e-mail S5 não dispara DLO:**
COS4016 mencionado como referência histórica ("reimportar COS4016 retroativos") estava disparando DLO indevidamente. Guard S5+DLO na Camada 1b e 2b.
Thread corrigida: FREEX COS4010 jan–maio/2026.

**C45 — S5 no assunto: a entrega é S5, DLO não coexiste:**
Regra de Michel: "não existe DLO e S5 ao mesmo tempo." Guard: se assunto tem \bS5\b e resultado tem S5+DLO_2061 → remove DLO.
Gabarito Executive Corretora corrigido de ['DLO_2061'] para ['S5'].

**C46 — Strip de citações antes da detecção CADOC:**
Linhas iniciadas por '>' (histórico citado) removidas do corpo antes de detectar CADOC. Helper `_corpo_sem_citacoes()` adicionado. Sinal 6b (VCRD do BACEN em texto citado) preservado usando `corpo.upper()` diretamente.
Gabaritos corrigidos: ZIIN → ['SUPORTE'], REMITLY LEC → ['DLO_2061'].
Threads fixadas: UNVERIFIED SENDER PR, VBS SCD VECTOR, CNPJ Alfanumérico.

### Sessões anteriores (07–12/08/2026)

- Criado `data/registro_definitivo_threads.json` — 768 threads (634 confirmadas / 134 incertas).
- `chat_ensino.py` reescrito para usar o registro. Gabarito v2.0 criado e integrado.
- Classificador consulta registro antes do GPT. Campo `orientacao` adicionado.
- B1 concluído: 136 IDs em `ids_incertos.txt`. Rodada 6 é o baseline (134 incertos, 17,4%).
- Grupo D mapeado em 13/08 (10 threads com categoria extra). Grupos A, B, C concluídos.

---

### Estado atual

**Placar classificador determinístico:** 741/768 (27 erros). Método: corpo com strip de citações + limite 2000 chars/mensagem.  
**Suite de testes:** 177/177 passando.  
**Registro definitivo:** `data/registro_definitivo_threads.json` — 768 threads  
**Gabarito:** `documentações/gabarito.json` v2.0 — 18 regras + 24 gabaritos  
**Classificador:** consulta registro antes do GPT — threads confirmadas não chamam API  
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

**🔴 PRÓXIMO — Continuar Grupo D (threads com categoria extra ainda abertas):**

Ver `documentações/PENDENCIAS.md` → seção Grupo D. Atacar um caso por vez: analisar qual sinal dispara a categoria errada → guard ou ajuste → pytest → amostra → commitar.

**Depois do Grupo D:** Grupo E (5 threads onde falta SUPORTE ao lado do CADOC).

**Depois do Grupo E:** Grupo F — casos individuais remanescentes (INDICIO 2061, CV INVESTIMENTOS, INTERNO, FREEX treinamento S5).

**Objetivo:** chegar a ≥ 750/768 para iniciar a fase de sessões de ensino com `chat_ensino.py`.

Último /fechar: 2026-08-14 — memórias revisadas ✅

---
