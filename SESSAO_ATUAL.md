# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-07-31) — Campos 7 e 8: especificação §10 completa

### Resumo do que foi feito

A sessão de hoje fechou os dois últimos campos da especificação §10 — o mapa de regras que a nova arquitetura vai seguir.

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

### Estado atual

**§14 da spec:** ✅ completo — todas as 12 categorias com regras R1–R5 documentadas e validadas
**§10 Campo 6 — Limpeza do corpo:** ✅ **CONCLUÍDO (30/07/2026)** — 6.989 e-mails, 12 categorias, regras L1–L8
**§10 Campo 7 — Anexos:** ✅ **CONCLUÍDO (31/07/2026)** — 78.087 arquivos, 6 cenários novos, regras escritas
**§10 Campo 8 — Thread ID e Data:** ✅ **CONCLUÍDO (31/07/2026)** — Thread ID, datas, inferência de ano, 3 tipos de threads de canal
**Especificação §10 completa:** ✅ — todos os 8 campos fechados
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

> **Regra (aprovada por Michel, 31/07/2026):** a spec responde tudo antes de qualquer implementação começar.
> Nenhum código de produção é escrito enquanto houver perguntas sem resposta no documento mestre.

**Pendências que bloqueiam a implementação — spec ainda precisa responder:**

1. 🔴 **OCR RETORNO_BACEN** — como o sistema lida quando a imagem É o conteúdo (não decoração)? Regra L6 existe mas OCR não está especificado na íntegra
2. 🟡 **Convites de calendário e notificações automáticas** — o que o classificador faz com e-mails que não são de cliente? (filtrar antes / categoria nova / revisão humana)
3. 🟡 **IA Assistente — histórico completo** — como preservar o `>` (histórico citado) para aprendizado se a limpeza L3 o remove para classificação? Decisão arquitetural
4. 🟡 **Painel do gestor** — como mostrar threads com múltiplos CADOCs? Por thread ou por CADOC? Quais status?
5. 🟡 **Encoding TRUSTEE DTVM** — como tratar e-mails com Windows-1252 no pré-processamento?
6. 🟡 **`Abraço` (singular)** — adicionar ao detector de assinatura na spec
7. 🟡 **Campos 1 a 5** — revisar formato para alinhar com o padrão do Campo 6

**Após spec completa:**
- 🟡 **Fase 1** — protótipo `coletor_gmail.py` + `classificador_ia.py`
- 🟡 **MAPA_DO_PROJETO.md** — criar para a nova arquitetura

Último /fechar: 2026-07-31 — memórias revisadas ✅ — Campos 7 e 8 concluídos; spec §10 completa

---
