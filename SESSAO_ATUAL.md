# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-07-31) — Spec §10 completa + reorganização estrutural + início da revisão sequencial

### Resumo do que foi feito

A sessão de hoje teve duas partes: primeiro, fechou os dois últimos campos da especificação (§10); depois, iniciou a revisão sequencial da spec com reorganização estrutural importante.

---

**Campo 7 — Anexos (concluído 31/07/2026):**

Script `scripts/consultas/analisar_anexos_emails.py` criado e executado — varreu 78.087 arquivos em disco cruzando com os 8.825 e-mails do histórico. Resultado: além dos formatos esperados (ZIP do CADOC, COSIF), foram identificados 6 cenários que não estavam no plano original.

| Tipo de arquivo | Qtde | Tratamento definido |
|---|---|---|
| ZIP padrão `CNPJ_CADOC_DATA.zip` | maioria | Sinal forte de categoria — extrair e analisar internos |
| Sufixo `_S_N` (substituição BACEN) | 351 | Marcar como substituição solicitada |
| COSIF `.xml` direto | 642 | Processar diretamente |
| COSIF `.bc` (formato antigo) | 123 | Mesma lógica do .xml — histórico retroativo exige suporte |
| `.rar` | 6 | Tentar abrir; se falhar → revisão humana |
| `.eml` (e-mail encaminhado) | 8 | Extrair assunto + anexos internos e reclassificar |
| Sem extensão — nome embaralhado | ~200 | Classificar pelo assunto; marcar como VERIFICAR_NOME |
| Sem extensão — código protocolo BACEN | ~30 | `ADRM060-...` = DRM; `ALIM262-...` = DLI — sinal forte |

Decisão adicional do Michel: para as categorias 2061, 2062, S5 e FORCAPITAL, os balancetes COSIF 4010/4060 são obrigatórios todo mês; nos meses de junho e dezembro também chegam o 4016 ou 4066. Isso **não diferencia a triagem** — é só contexto de conhecimento.

---

**Campo 8 — Thread ID e Data (concluído 31/07/2026):**

Três temas discutidos um por vez e consolidados em sequência:

**Tema 1 — Thread ID:**
- `thread_root` (histórico) / `threadId` (Gmail API) = chave que agrupa toda a conversa
- Três funções: unir o caso na tela do gestor · determinar o status atual · guardar histórico para a IA aprender
- 100% preenchido no histórico de 8.825 e-mails

**Tema 2 — Campos de data:**
- `data_email` (sempre preenchida, vem do Gmail) vs. `data_competencia` (extraída pela IA do assunto/anexo)
- A data de competência é o mês do CADOC — necessária para calcular o prazo regulatório
- Script `scripts/consultas/analisar_mes_sem_ano.py` validou a regra de inferência de ano: 157 casos testados, 100% de acerto nos 5 com ground truth
- Regra aprovada por Michel: `data_competencia = null` → sistema não monitora prazo

**Tema 3 — Threads de canal:**
- 59 threads (1,8%) com 10+ e-mails ou abrangendo 3+ meses
- 3 tipos identificados com exemplos reais do histórico:
  - **Entrega recorrente** (SSG/4111): cada e-mail com anexo = nova entrega na Camada 2; `data_competencia` = `data_email`
  - **Coordenação** (UNICRED/DDR): zero anexos = zero itens na Camada 2
  - **Caso complexo** (EQI CTVM/RETORNO_BACEN): um único caso que levou meses para resolver

**Script permanente criado:** `scripts/consultas/analisar_threads_datas.py`

---

**Reorganização estrutural da spec (31/07/2026):**

Após concluir os Campos 7 e 8, a sessão continuou com uma revisão da estrutura da especificação. Três mudanças aprovadas por Michel:

1. **§7 "Ganho principal e risco principal" — excluído.** Decisão de Michel: o item era desnecessário porque a regra de que a IA só classifica quando todos os campos obrigatórios estão preenchidos (e o que não estiver vai para revisão humana) já trata o risco implicitamente — não precisava de seção separada.

2. **"Plano de implantação por fases" — movido para §15 (final).** Motivação: seções de implementação não pertencem no meio da especificação técnica; devem ficar no final, após tudo estar validado.

3. **"Decisões tomadas e justificativas" — movido para §14 (penúltimo).** Mesmo critério: será completado gradualmente conforme a spec avança; fica no final para não interromper a leitura da spec técnica.

Após a reorganização, revisão rápida (passagem A) do §7 "Mapeamento de campos do e-mail". Michel identificou duas lacunas:
- Campo 1: não descreve o passo a passo de filtragem (como vai filtrar, não só o que filtra)
- Campos 1 a 8: não têm bloco "Como o sistema processa" — só dizem o que cada campo é, não como o sistema decide o que fazer com ele

Ambas as lacunas foram registradas como 🔴 BLOQUEADOR no PENDENCIAS.md — obrigatório resolver antes do desenvolvimento das telas.

---

### Estado atual

**Mapeamento de campos (§7 da spec):** ✅ completo em conteúdo — 🔴 pendência de "Como processa" em cada campo
**§7 Campo 6 — Limpeza do corpo:** ✅ **CONCLUÍDO (30/07/2026)** — 6.989 e-mails, 12 categorias, regras L1–L8
**§7 Campo 7 — Anexos:** ✅ **CONCLUÍDO (31/07/2026)** — 78.087 arquivos, 6 cenários novos, regras escritas
**§7 Campo 8 — Thread ID e Data:** ✅ **CONCLUÍDO (31/07/2026)** — Thread ID, datas, inferência de ano, 3 tipos de threads de canal
**Especificação §7 (Mapeamento) completa:** ✅ — todos os 8 campos fechados
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

> **Regra (aprovada por Michel, 31/07/2026):** a spec responde tudo antes de qualquer implementação começar.
> Nenhum código de produção é escrito enquanto houver perguntas sem resposta no documento mestre.

**🔴 BLOQUEADORES (antes do desenvolvimento das telas):**

1. 🔴 **§7 — "Como o sistema processa"** (passo a passo) em cada um dos 8 campos — Campo 1 inclui passo a passo de filtragem
2. 🔴 **OCR RETORNO_BACEN** — como o sistema lida quando a imagem É o conteúdo (não decoração)? Regra L6 existe mas OCR não está especificado na íntegra

**Revisão sequencial da spec — próxima seção:**

3. 🟡 **§8 — Regras de classificação das threads** ← PRÓXIMA SESSÃO (segunda-feira)

**Demais seções pendentes de revisão:**
- §9 Modelo de rastreamento — duas camadas
- §10 Telas do sistema
- §11 Catálogo de categorias
- §12 Exemplos reais de threads
- §13 Padrões observados
- §14 Decisões tomadas e justificativas
- §15 Plano de implantação

**Outras pendências ativas:**
- 🟡 Convites de calendário e notificações automáticas — definir antes da Fase 3
- 🟡 IA Assistente — histórico completo vs. limpeza para classificação
- 🟡 Painel do gestor — design para threads com múltiplos CADOCs
- 🟡 Encoding TRUSTEE DTVM — corrigir no pré-processamento
- 🟡 `Abraço` (singular) — adicionar ao detector de assinatura
- 🟡 Campos 1 a 5 — revisar formato para alinhar com padrão do Campo 6

**Após spec completa:**
- 🟡 **Fase 1** — protótipo `coletor_gmail.py` + `classificador_ia.py`
- 🟡 **MAPA_DO_PROJETO.md** — criar para a nova arquitetura

Último /fechar: 2026-07-31 — memórias revisadas ✅ — Spec §10 completa; reorganização estrutural; próximo: §8

---
