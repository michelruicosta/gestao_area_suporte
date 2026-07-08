# Tarefas Agendadas — Oráculo 360 Finaud

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

> **Recursos externos que rodam automaticamente.** Qualquer IA que precisar alterar, recriar ou debugar deve ler este arquivo antes de tocar.
> Toda tarefa agendada é parte do projeto e deve estar rastreada aqui.

---

## 📋 Índice de Tarefas Agendadas

1. [Auditoria Mensal de Documentação](#auditoria-mensal-de-documentação)

---

## Auditoria Mensal de Documentação

### O que é
Validação automática de consistência em documentação interna do projeto (SESSAO_ATUAL.md, PENDENCIAS.md, REGISTRO_CORRECOES.md). Roda sem intervenção, na cloud, todo mês no mesmo dia e hora.

### Por que existe
Documentação desatualizada ou inconsistente causa implementações erradas nas sessões seguintes. Sem validação automática, buracos só aparecem quando alguém lê tudo (raro). Sistema manual é frágil — IA seguinte implementa baseada em doc confusa → threads em produção ficam erradas.

### Como funciona

**Trigger:** Dia 28 do mês às 17:00 (horário de Brasília)

**Execução:**
1. Cloud agent inicia automaticamente (não precisa PC ligado)
2. Roda `python scripts/auditar_documentacao_completa.py --gera-pendencia`
3. Se encontrar problema:
   - Cria arquivo: `documentações/AUDITORIA_MENSAL_YYYYMM.md` (relatório)
   - Adiciona entry em `PENDENCIAS.md` (automático)
   - Faz git commit + push para `desenvolvimento-front_end`
4. Log criado em `logs/pipeline/auditoria_mensal_YYYYMM.log`

**Notificação:** No próximo `/iniciar`, Michel vê alerta se houver problema

### Regras (o que não pode mudar)
- ❌ Nunca push para `main` (sempre `desenvolvimento-front_end`)
- ❌ Nunca usar `--force` ou `--no-verify`
- ✅ Sempre criar entry em PENDENCIAS.md se encontrar buraco
- ✅ Sempre fazer git push (não deixar só em local)
- ✅ Log deve ser criado mesmo se falhar

### Exemplos Reais

**Exemplo 1: Auditoria sem problemas (esperado)**
```
2026-07-28 17:00 → Tarefa roda
→ Valida 5 checks (cardinality, recency, consistency, linkage, coherence)
→ Tudo OK ✅
→ Arquivo: documentações/AUDITORIA_MENSAL_202607.md (vazio de problemas)
→ Commit: "docs(auditoria): mensal 2026-07 — relatório de consistência"
→ Push: OK ✅
```

**Exemplo 2: Auditoria com problema detectado**
```
2026-07-28 17:00 → Tarefa roda
→ LINKAGE check falha: "Fase 6 referenced in PENDENCIAS but not found in DOCUMENTACAO_TRIAGEM.md"
→ Arquivo: documentações/AUDITORIA_MENSAL_202607.md (com erro listado)
→ Entry criada em PENDENCIAS.md: "🔴 AUDITORIA_MENSAL_202607: 1 problema encontrado"
→ Commit + push OK ✅
→ Próximo /iniciar: Michel vê "⚠️ Auditoria Mensal encontrou 1 problema — ver PENDENCIAS.md"
```

### Dependências
- Script: `scripts/auditar_documentacao_completa.py` (deve existir, não pode ser deletado)
- Branch: `desenvolvimento-front_end` (alvo do push, deve estar protegida com regra de merge)
- Arquivos validados: `SESSAO_ATUAL.md`, `PENDENCIAS.md`, `REGISTRO_CORRECOES.md`, `DOCUMENTACAO_TRIAGEM.md`
- Git config: `core.hooksPath .githooks` (pre-commit hook deve estar ativo)

---

## 📝 Rastreamento de Tarefas Agendadas

| ID | Nome | Tipo | Criada em | Por quem | Schedule | Próxima execução | Status | Últimas alterações |
|---|---|---|---|---|---|---|---|---|
| `auditoria-mensal-oraculo360` | Auditoria Mensal de Documentação | Cloud-based recurring | 2026-06-21 22:55 | Claude Code (Sonnet 4.6) | Dia 28, 17:00 BRT | 2026-07-28 17:00 | ✅ Ativa | Nenhuma (primeira criação) |

---

## 🔧 Como Recriar (se precisar)

**Cenário:** Tarefa deletada por engano, ou precisa mudar de schedule

**Pré-requisitos:**
- Estar em sessão Claude Code com acesso a `D:\oraculo_360_finaud`
- Ter permissão para usar ferramentas de scheduled tasks
- Scripts `auditar_documentacao_completa.py` devem existir

**Passos:**

1. Usar ferramenta `mcp__scheduled-tasks__create_scheduled_task`:
   ```
   taskId: "auditoria-mensal-oraculo360"
   cronExpression: "0 17 28 * *"  (dia 28, 17:00 local)
   description: "Auditoria mensal de consistência de documentação — Oráculo 360 Finaud"
   notifyOnCompletion: true
   ```

2. Prompt (self-contained, sem referência a este chat):
   ```
   Você é o Gestor do Projeto Oráculo 360 Finaud. Execute a auditoria mensal de documentação no dia 28 do mês às 17h (Brasília).

   OBJETIVO: Validar consistência de documentação interna (SESSAO_ATUAL.md, PENDENCIAS.md, REGISTRO_CORRECOES.md) e detectar inconsistências cruzadas.

   PASSOS:
   1. cd D:\oraculo_360_finaud
   2. python scripts/auditar_documentacao_completa.py --gera-pendencia
   3. git add documentações/AUDITORIA_MENSAL_*.md PENDENCIAS.md logs/pipeline/auditoria_mensal_*.log
   4. git commit -m "docs(auditoria): mensal $(date +'%Y-%m') — relatório de consistência"
   5. git push origin desenvolvimento-front_end

   RESTRIÇÕES:
   - ❌ Nunca main, nunca --force, nunca --no-verify
   - ✅ Sempre desenvolvimento-front_end
   - ✅ Log deve existir mesmo se falhar
   ```

3. Verificar: Task deve aparecer em "Scheduled" na sidebar com próxima execução em 28º dia

---

## ⚠️ Erros Conhecidos / Limitações

### Problema: False positives em regex
**Sintoma:** Auditoria reporta erro em "data" ou "Fase" que na verdade existe
**Causa:** Padrões regex não batem 100% com formato do documento
**Status:** ⚠️ Conhecida, não bloqueante (Fase 1 TDD vai fixar)
**Impacto:** Pode criar pendência falsa em PENDENCIAS.md — revisar antes de agir

### Problema: Tarefa roda mesmo se PC está ligado
**Sintoma:** Auditoria roda duas vezes (local hook + cloud agendada)
**Causa:** Não há sincronização entre hook diário e rotina mensal
**Status:** ✅ Esperado — sem impacto (resultados são iguais)
**Impacto:** Zero, commit redundante apenas

### Problema: Se git push falhar
**Sintoma:** Log criado, relatório existe, mas push não foi
**Causa:** Rede, SSH key expirada, branch protegida
**Status:** ⚠️ Documentado no log — não bloqueia próximo ciclo
**Impacto:** Relatório fica local, não aparece no GitHub — revisar antes de assumir que rodou

---

## 📜 Histórico de Alterações

| Data | O que mudou | Por quê | Quem |
|---|---|---|---|
| 2026-06-21 | Tarefa criada | Implementação do sistema de auditoria | Claude Code (Sonnet 4.6) |

---

*Última atualização: 2026-06-21 22:55 — Criação inicial*
