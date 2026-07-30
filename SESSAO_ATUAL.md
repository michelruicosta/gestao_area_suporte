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
| Seta `>` (reply citado) | 91,0% |
| Rodapé Google Groups | 95,5% |
| Separador Outlook | 6,3% |
| Assinatura detectada | 92,8% |
| Com `[image: xxx]` no texto | 23,9% |
| Corpo vazio após limpeza | 0,2% (4 e-mails — todos ENCAMINHAMENTO_INTERNO R5) |

**Artifact visual publicado (4 casos de imagem — Fase 1 e Fase 2):**
https://claude.ai/code/artifact/f86d271e-b354-49e2-8d2b-b110e68652c6

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
**§10 Campo 6:** 🔴 DDR_2011 analisado ✅ · 11 categorias restantes ☐
**§10 Campos 7, 8:** 🔴 aguardam Campo 6 concluído
**GitHub:** `github.com/michelruicosta/gestao_area_suporte` — branch `main`

---

### Próximos passos

1. 🔴 **Campo 6 — próxima categoria: SCD_4111** (mesma metodologia do DDR_2011)
   - Scripts prontos no scratchpad: `simular_limpeza_ddr.py` e `inspecionar_imagens_ddr.py` (adaptar filtro de cadoc)
   - Demais 10 categorias na sequência
2. 🔴 Após todas as 12 → escrever Campo 6 na spec §10 (3 partes) + artifact visual completo
3. 🟡 Confirmar T04 (Western Union) com Michel: o papel da Finaud neste fluxo
4. 🟡 Criar novo MAPA_DO_PROJETO.md para a nova arquitetura
5. 🟡 Fase 1 da nova arquitetura: protótipo do coletor Gmail + classificador IA

Último /fechar: 2026-07-30 — memórias revisadas ✅

---
