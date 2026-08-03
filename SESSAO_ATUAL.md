# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-08-03) — Revisão sequencial §8–§11 + "entregue" por categoria (§9 atualizado)

### Resumo do que foi feito

Sessão longa em dois blocos: o primeiro cobriu §8 (regras de classificação), §9–§11 (catálogo, exemplos), e outras decisões pontuais. O segundo foi inteiramente dedicado a responder uma pergunta fundamental da spec: **o que significa "entregue" para cada categoria?**

---

**Bloco 1 — Revisão sequencial §8 a §11 (detalhes no REGISTRO_CORRECOES.md, 03/08):**

- **§8 Regras de classificação:** 3 lacunas identificadas e corrigidas (escopo do texto analisado, veto + pergunta no mesmo e-mail, "transmitido no BACEN" pelo cliente).
- **T04 Western Union:** papel da Finaud confirmado — CAM0050 + Balancete de Câmbio = insumo para o DDR (subcategoria cambial).
- **§9 Modelo de rastreamento / §10 Catálogo / §11 Exemplos (T01–T19):** aprovados por Michel.
- **Campo CC revisado:** CC usado condicionalmente (35% dos e-mails têm Finaud só no CC).
- **"Threads irmãs":** Michel decidiu deixar para a Fase 2 — na Fase 1 a regra do último e-mail cobre todos os casos normais.

---

**Bloco 2 — "Entregue" por categoria: varredura histórica + spec atualizada:**

Investigação item a item com scripts contra o histórico real (oraculo_360_finaud). Resultados confirmados:

| Categoria | O que a Finaud entrega |
|---|---|
| DDR 2011, DRM 2060, DRL 2160, DLO 2061, DLI 2062, CADOC 4111 | ZIP `CNPJ_CATEGORIA_DATA.zip` (substituição: sufixo `_S_N`) |
| S5 | PDF (`Resultado Quantitativo - S5.pdf`) — não vai ao BACEN |
| FORCAPITAL | Varia: e-mail texto, XLSX ou PDF — não vai ao BACEN |
| PVCA 6209 | `BACEN.ZIP` com 8 TXT na raiz (CONGLOME, USUREMOT, ESTATCRT, ESTATATM, TRANSOPA, OPEINTRA, CONTATOS, DATABASE) — cliente transmite via STA |
| DRSAC 2030 | XML (`DocumentoDRSAC`, CNPJ 8 dígitos, data AAAA-MM) |
| RETORNO_BACEN | Não é entrega — é a etapa de crítica do BACEN |

**DDR — problema multi-thread descoberto:** 99% das entregas de CADOC DDR acontecem em thread SEPARADA da thread onde o cliente enviou os dados brutos. Chave de ligação: CNPJ + data\_competencia extraída do nome do ZIP (padrão 100% padronizado). Registrado na spec. Fase 2 definirá a ligação automática.

**RETORNO\_BACEN — requisito de leitura de imagem:** 1.061 PNG/JPGs detectados no histórico — a crítica do BACEN está embutida em prints de tela do sistema do BACEN. O classificador usará a visão nativa do Claude (multimodal) para extrair o texto. Confirmado por Michel e gravado na spec.

**§9 atualizado** em `ESPECIFICACAO_NOVA_ARQUITETURA.md` e `spec_nova_arquitetura.html` (artifact republicado com mesmo link).

---

### Estado atual

**Revisão sequencial da spec:** §8, §9, §10, §11 ✅ concluídos
**§9 "Entregue" por categoria:** ✅ confirmado e gravado na spec (03/08/2026)
**RETORNO\_BACEN imagem:** ✅ requisito gravado na spec
**Spec §10 (Campos 1–8):** ✅ todos concluídos
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

> **Regra (aprovada por Michel, 31/07/2026):** a spec responde tudo antes de qualquer implementação começar.

**🔴 BLOQUEADORES (antes do desenvolvimento das telas):**

1. 🔴 **§7 — "Como o sistema processa"** (passo a passo) em cada um dos 8 campos
2. 🔴 **OCR RETORNO\_BACEN** — requisito gravado na spec; implementação é bloqueador da Fase 3

**Revisão sequencial — seções restantes:**

3. 🟡 **§12 Padrões observados** ← PRÓXIMA SESSÃO
4. 🟡 **§13 Telas do sistema** (só após seções funcionais completas)
5. 🟡 **§14 Decisões e justificativas**
6. 🟡 **§15 Plano de implantação**

**Outras pendências ativas:**
- 🟡 Convites de calendário e notificações automáticas — antes da Fase 3
- 🟡 IA Assistente — histórico completo vs. limpeza para classificação
- 🟡 Painel do gestor — design para threads com múltiplos CADOCs
- 🟡 Encoding TRUSTEE DTVM — corrigir no pré-processamento
- 🟡 `Abraço` (singular) — adicionar ao detector de assinatura

**Após spec completa:**
- 🟡 **Fase 1** — protótipo `coletor_gmail.py` + `classificador_ia.py`
- 🟡 **MAPA\_DO\_PROJETO.md** — criar para a nova arquitetura

Último /fechar: 2026-08-03 — memórias revisadas ✅ — §8–§11 revisados; "entregue" por categoria confirmado; próximo: §12

---
