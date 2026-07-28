# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-07-28) — Especificação consolidada + documentação reorganizada

### Resumo do que foi feito

**1. Histórico antigo do SESSAO_ATUAL.md arquivado ✅**
1.251 linhas de sessões anteriores (sistema antigo, até 17/07) movidas para
`_archive/sessao_atual_historico/SESSAO_ATUAL_historico_sistema_antigo.md` com CONTEXTO.md.
Este arquivo ficou com apenas o essencial de 28/07.

**2. ESPECIFICACAO_NOVA_ARQUITETURA.md reescrita como documento único ✅**
Versão 2.0 (28/07/2026) — §1 a §16 + Apêndice A, com índice numerado.
Mudanças principais:
- Terminologia corrigida: "dois fluxos" → "10 categorias", "CADOC" → "categoria regulatória"
- §3 reescrito: tabela de 10 categorias com seus fluxos
- §10 Campo 6, 7, 8 marcados como ⚠️ PENDENTE aguardando simulações
- §14 catálogo completo das 10 categorias com sinais de detecção e fluxos típicos
- §15 exemplos reais T01–T19 integrados (vindos do catálogo)
- §16 padrões observados para guiar a IA
- Apêndice A colaboradores Finaud (incluindo Sarah Sá e Luiz Antonio/FinaudTec)

**3. CATALOGO_TIPOS_EMAIL.md mesclado na spec e arquivado ✅**
Conteúdo integrado na spec §14, §15 e §16.
Arquivo movido para `_archive/documentacao_sistema_antigo/CATALOGO_TIPOS_EMAIL.md`.

**4. PENDENCIAS.md atualizado ✅**
- Item do catálogo removido (resolvido)
- Novo bloco 🔴 URGENTE adicionado para Campos 6, 7, 8 da spec

**5. Regra vital salva em memória ✅**
Limite de 32.000 output tokens: nunca gerar arquivo >600 linhas em uma única resposta.
Estratégia: Write (Parte 1 com placeholder) + Edit (Parte 2).
Arquivo de memória: `.claude/projects/.../memory/feedback_limite_output_tokens.md`

### Estado atual

**Especificação:** completa em §1–§12 e §14–§16 + Apêndice A.
**Aberto:** §10 Campos 6, 7, 8 — dependem de 3 simulações de threads reais ainda pendentes.
**Padrão de nomes aprovado:** `ação_domínio.py` (ex.: `coletor_gmail.py`, `classificador_ia.py`)

### Próximos passos

1. 🔴 Concluir 3 simulações de threads (RETORNO_BACEN, DLO/DLI, SUPORTE) → escrever Campos 6, 7, 8
2. 🟡 Confirmar T04 (Western Union) com Michel: o papel da Finaud neste fluxo
3. 🟡 Criar novo MAPA_DO_PROJETO.md para a nova arquitetura
4. 🟡 Fase 1 da nova arquitetura: protótipo do coletor Gmail + classificador IA

---