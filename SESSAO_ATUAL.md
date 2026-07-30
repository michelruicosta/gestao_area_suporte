# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-07-30) — Campo 6: metodologia de limpeza do corpo do e-mail

### Resumo do que foi feito

**Decisão fundamental (30/07/2026):** a IA nunca recebe o e-mail bruto — existe uma etapa de limpeza obrigatória entre o Gmail e a IA. O Campo 6 da spec define exatamente essa limpeza.

**8 Regras de limpeza estabelecidas — DDR_2011 (baseline para todas as categorias):**

| # | Regra | O que corta |
|---|---|---|
| L1 | Assinatura | `Att,` / `Atenciosamente` / `À disposição` / `Cordialmente` / `Desde já agradeço` / `Antecipadamente grata` |
| L2 | Histórico com traços | `-----` (Gmail forward) e `___` (Outlook separator) |
| L3 | Histórico com seta `>` | Linhas de reply citado — afeta 91% dos e-mails DDR_2011 |
| L4 | Rodapé de lista | `To unsubscribe from this group` (Google Groups) — afeta 95,5% dos e-mails DDR_2011 |
| L5 | Imagem decorativa | `[image: instagram/linkedin/facebook/logo/ícone...]` — descarta por nome |
| L6 | Imagem genérica antes da assinatura | `[image: image.png]` → tenta OCR → se OCR falhar → fila de revisão humana |
| L7 | Imagem genérica depois da assinatura | Descarta (logo de rodapé) |
| L8 | Corpo vazio após limpeza | Sinaliza como `ENCAMINHAMENTO_INTERNO` (R5) — não classifica sem texto |

**DDR_2011 analisado — todos os 2.350 e-mails:**

| Verificação | Resultado |
|---|---|
| HTML (não texto puro) | 99,8% |
| Seta `>` (reply citado) | 37,1% têm histórico citado |
| Rodapé Google Groups | 95,5% têm rodapé automático |
| Separador encaminhado (`---`) | 22,1% têm histórico encaminhado |
| Assinatura detectada | **96,4%** (após 3 rodadas de melhoria do padrão) |
| Com `[image:]` no texto | 23,9% |
| Com `[cid:]` no texto | 18,9% |
| Corpo vazio após limpeza | 0,2% (4 e-mails — todos ENCAMINHAMENTO_INTERNO R5) |

**Artifact visual publicado (4 casos de imagem — Fase 1 e Fase 2):**
https://claude.ai/code/artifact/f86d271e-b354-49e2-8d2b-b110e68652c6

**Artifact de validação Campo 6 — Passo 3 (6 elementos, DDR_2011):**
https://claude.ai/code/artifact/5054a35e-cbae-4beb-af23-df3c0972bcae
✅ **Todos os 6 elementos validados por Michel (30/07/2026):**
- Assinatura: 96,4% — 84 casos top-post aceitos como limitação conhecida
- Histórico citado (`>`): 37,1% ✅
- Histórico encaminhado (`---`): 22,1% ✅
- Rodapé automático: 95,5% ✅
- `[image:]`: 23,9% ✅
- `[cid:]`: 18,9% ✅

**Script permanente criado:** `scripts/consultas/analisar_corpo_emails.py`
(parametrizado por projeto e categoria — reutilizável para todas as 12 categorias)

**Estrutura de documentação aprovada (5 componentes):**
- Especificação = o mapa (decisões e regras)
- Artifact = o visual (como ficará na tela)
- Lista de tarefas = roteiro do desenvolvimento
- REGISTRO_CORRECOES = histórico do que foi feito
- PENDENCIAS = o que falta (com checklist)

**Estrutura interna de cada campo da spec (3 partes):**
"O que temos" → "O que utilizaremos" → "Regras de negócio"

---

### Estado atual

**§14 da spec:** ✅ completo — todas as 12 categorias com regras R1–R5 documentadas e validadas
**§10 Campo 6 — Passo 3:** ✅ DDR_2011 analisado e validado · 11 categorias restantes ☐
**§10 Campos 7, 8:** 🔴 aguardam Campo 6 concluído
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

1. 🔴 **Campo 6 — próxima categoria: SCD_4111** — mesmo fluxo do DDR_2011:
   - Rodar `scripts/consultas/analisar_corpo_emails.py` com `CADOC_FILTRO = '4111'`
   - Validar os 6 elementos no artifact de validação (ou criar novo artifact para SCD_4111)
   - Demais 10 categorias na sequência
2. 🔴 Após todas as 12 → escrever Campo 6 na spec §10 (3 partes: "O que temos" / "O que utilizaremos" / "Regras de negócio") + artifact visual completo
3. 🟡 Confirmar T04 (Western Union) com Michel: o papel da Finaud neste fluxo
4. 🟡 Criar novo MAPA_DO_PROJETO.md para a nova arquitetura
5. 🟡 Fase 1 da nova arquitetura: protótipo do coletor Gmail + classificador IA

Último /fechar: 2026-07-30 18:XX — memórias revisadas ✅ — Campo 6 DDR_2011 Passo 3 validado e commitado

---
