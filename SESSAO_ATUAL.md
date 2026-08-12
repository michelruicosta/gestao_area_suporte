# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-08-12) — Gabarito v2.0 + campo orientação + normalização SCD_4111

### Resumo do que foi feito

- **Backup dos dados antigos (gabarito v1.x):** movidos 33 arquivos de resultados de validação, 3 arquivos de IDs e 8 backups soltos para `data/backups/20260812_1450_dados_gabarito_v1/`. Pasta de dados limpa.

- **Limpeza de testes do projeto antigo:** 41 arquivos de teste da arquitetura antiga (pipeline de 16 scripts) removidos de `tests/` e backupados em `data/backups/20260812_1455_testes_projeto_antigo/`. Ficaram só: `__init__.py`, `conftest.py`, `test_classificador_ia.py`.

- **Normalização SCD_4111 → SALDOS_CONTABEIS_DIARIOS_4111:** 116 threads no `registro_definitivo_threads.json` tinham o nome antigo. Todas corrigidas para o nome canônico. 1 thread adicional tinha categorias como string `"DDR_2011, DRM_2060"` em vez de lista — corrigida para `["DDR_2011", "DRM_2060"]`. Backup em `data/backups/20260812_1510_normalizacao_scd4111/`.

- **Campo `orientacao` no classificador:** quando o GPT retorna vazio ou INCERTO, agora explica o motivo e orienta como ajudá-lo a classificar. Campo adicionado ao `_SISTEMA` em `scripts/classificador_ia.py`. Novo teste `test_orientacao_no_sistema` — suite: 13/13 passando.

- **`chat_ensino.py` corrigido:** função `_formatar_gabarito_completo()` ainda lia o formato antigo (`exemplos`). Atualizada para v2.0 (`regras` + `gabaritos`).

- **Gabarito v2.0 — "Usuário Ativo":** palavras genéricas `usuário`, `permissão`, `login`, `reset` adicionadas à instrução do classificador. SUPORTE Gabarito 11 ("Usuário Ativo") adicionado ao `gabarito.json`. SUPORTE Regra 01 removida (redundante com o gabarito, conforme regra de não duplicar).

- **Amostra de controle rodada:** 15/20 corretas, 2 INCERTO, 3 erradas → **REPROVADA**.
  - "Usuário Ativo" permanece INCERTO na amostra, mas já é CONFIRMADA no registro — em produção, o GPT é bypassado e ela retorna SUPORTE corretamente. O gabarito ancora e-mails futuros similares.
  - 3 casos pendentes de investigação (um por vez):
    1. "[CV INVEST] DLO - 05/2026" — esperado DLO, obtido DLO+DLI
    2. "2026.07.07 - FLUXO DE CAIXA - ZIIN" — esperado DDR_2011+SALDOS, obtido só SALDOS
    3. "Erro do DRM e DLO" — esperado DLO+DRM+RETORNO_BACEN, obtido DLO+DRM

### Sessões anteriores (07–11/08/2026)

- Criado `data/registro_definitivo_threads.json` — 768 threads (634 confirmadas / 134 incertas).
- `chat_ensino.py` reescrito para usar o registro.
- Gabarito v2.0 criado: 18 regras + 24 gabaritos, integrado ao prompt do classificador.
- Classificador consulta registro antes do GPT — threads confirmadas não chamam API.
- B1 concluído: 136 IDs em `ids_incertos.txt`. Rodada 6 é o baseline (134 incertos, 17,4%).

---

### Estado atual

**Registro definitivo:** `data/registro_definitivo_threads.json` — 768 threads (634 confirmadas / 134 incertas)  
**Gabarito:** `documentações/gabarito.json` v2.0 — 18 regras + 24 gabaritos  
**Classificador:** consulta registro antes do GPT — threads confirmadas não chamam API  
**Campo `orientacao`:** GPT explica o motivo quando fica INCERTO ou retorna vazio  
**chat_ensino.py:** usa registro + lê gabarito v2.0 corretamente  
**Suite de testes:** 13/13 passando  
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

**🔴 PRÓXIMO — Investigar os 3 casos da amostra (um por vez):**

Cada caso segue o ciclo: analisar → corrigir spec ou gabarito → rodar amostra → aprovar → commitar.

**Caso 1:** "[CV INVEST] DLO - 05/2026"
- Esperado: `[DLO_2061]` → Obtido: `[DLO_2061, DLI_2062]`
- Investigar: por que o GPT adicionou DLI? O corpo menciona 4010/4016?

**Caso 2:** "2026.07.07 - FLUXO DE CAIXA - ZIIN"
- Esperado: `[DDR_2011, SALDOS_CONTABEIS_DIARIOS_4111]` → Obtido: `[SALDOS_CONTABEIS_DIARIOS_4111]`
- Investigar: por que DDR_2011 sumiu? "FLUXO DE CAIXA" está nas keywords DDR?

**Caso 3:** "Erro do DRM e DLO"
- Esperado: `[DLO_2061, DRM_2060, RETORNO_BACEN]` → Obtido: `[DLO_2061, DRM_2060]`
- Investigar: por que RETORNO_BACEN sumiu? O corpo menciona crítica do BACEN?

**Depois dos 3 casos:** rodar amostra de controle com resultado ≤ 1 INCERTO e 0 erros para aprovar o gabarito v2.0 e commitar com tag `gabarito-v2-estavel`.

**Depois:** continuar sessões de ensino com `chat_ensino.py` para resolver os 134 incertos restantes.

Último /fechar: 2026-08-12 — memórias revisadas ✅

---
