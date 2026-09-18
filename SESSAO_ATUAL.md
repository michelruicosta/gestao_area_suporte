# SESSAO_ATUAL — Gestão Área Suporte

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como o sistema deve se comportar → `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` · Como rodar → `CLAUDE.md` §1
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `ESPECIFICACAO_NOVA_ARQUITETURA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 🗂️ Sessões anteriores — o histórico do projeto

| Data | Tema | Onde ler |
|---|---|---|
| 18/09 | Casos 4–6 Remitly — decisão de status + conclusão do Padrão 2 | abaixo |
| 18/09 | Trilha de Auditoria — implementação completa + deploy VPS | abaixo |
| 14/09 | Empresa no Resumo + Fix1+Fix2 + investigação mensagens Gmail vs sistema | abaixo |
| 11/09 | Validação de Status: protocolo + Bloco 1 (22 suspeitos) | arquivo |
| 11/09 | Resumo Semanal: e-mail idêntico ao artefato + caixa BACEN encerrados + fix FOG filter | arquivo |
| 10/09 | prospeccao_finaud: tela Flask separada Bacen/Receita + ingestão 26 estados | arquivo |
| 10/09 | Padrão 2 (Finaud→Cliente): tentativa Fix1+Fix2 → revertida por protocolo | arquivo |
| 10/09 | Jornada: melhorias visuais + filtros bidirecionais + fix label gráfico | arquivo |
| 10/09 | Jornada por Colaborador: nova tela FOG completa implementada e deployada | arquivo |
| 10/09 | Portal: botão copiar senha temporária — tentativa user-select:all → revertida | arquivo |
| 10/09 | Script testar_status_ia.py criado — Fase 1 pronta para rodar | arquivo |
| 10/09 | Teste de IA — planejamento e análise de 1.629 threads para validação de status | arquivo |
| 09/09 | Modal: De/Para unificados — regras por tipo de remetente; deploy e validação em produção | abaixo |
| 09/09 | Coletor de colaboradores — verificação pós-deploy do fix Message-ID/In-Reply-To | arquivo |
| 09/09 | Contaminação cruzada DRM 2060: investigação, restauração e prevenção | arquivo |
| 09/09 | Sentry: guia interativo + fix UndefinedError media_dias | arquivo |
| 09/09 | Modal — Cenário 3: listas com marcadores implementadas e publicadas na VPS | arquivo |
| 08/09 | Tabela COSIF no modal: validação do Cenário 2 + registro Cenários 1–2 + Cenário 3 aberto | arquivo |
| 08/09 | Sentry monitoring + 3 otimizações de performance | arquivo |
| 08/09 | Fix: campo Para — colaborador @finaud em vez de suporte | arquivo |
| 08/09 | Verificação e-mails do dia + criação serviço agendador VPS | arquivo |
| 08/09 | Fix: campo data vazio — retomada /fechar | arquivo |
| 08/09 | Redesign telas Evolução e Classificação e Status | arquivo |
| 08/09 | Fix: CI — pacotes Google ausentes no requirements-dev.txt | arquivo |
| 08/09 | Display modal A–G: mapeamento, implementação, spec e artifact | arquivo |
| 08/09 | UX modal thread: histórico sob demanda, fim do scroll duplo | arquivo |
| 08/09 | Skills/MCPs — limpeza de config + regra de comunicação técnica | arquivo |
| 08/09 | Fix: mensagens duplicadas (coletor colaboradores + message_id) | arquivo |
| 08/09 | Consulta pontual — e-mail DRL 07 2026 rejeitado | arquivo |
| 06/09 | Alerta "busca parada": origem do alerta (local vs produção) | arquivo |
| 06/09 | Visão Geral — filtro de data + dados sempre frescos | arquivo |
| 03/09 | Migração HTML na VPS + fix modal C/D/F | arquivo |
| 02/09 | Fix: cronômetro de atualização | arquivo |
| 02/09 | Visão Geral — busca, filtros, Sem Retorno no dropdown e clique nas linhas | arquivo |
| 02/09 | Validação coletor colaboradores + problema status threads arquivadas | arquivo |
| 02/09 | BACEN motivos 15 e 16 + validação pré-deploy + deploy | arquivo |
| 02/09 | Sem Retorno — filtros por categoria e aba Por Categoria | arquivo |
| 01/09 | Motivos / Caixa preta — Decisões 17–24 | arquivo |
| 01/09 | Fog: dias úteis, feriados e Sem atualização | arquivo |
| 01/09 | Administração: E-mail, Notificações e aviso por e-mail | arquivo |
| 28-29/08 | Planilha de classificação de motivos + bug Outlook no grupo saudação | arquivo |
| 27/08 | Senha no portal — perfil e login | arquivo |
| 27/08 | Textos campo MOTIVO — grupo ❌ (noite) | arquivo |
| 27/08 | Organização dos chats + conserto do `/fechar` | arquivo |
| 27/08 | Reorganização do CLAUDE.md | arquivo |
| 27/08 | Textos campo MOTIVO (manhã) | arquivo |
| 26/08 | Esqueceu a senha + faxina FOG | arquivo |
| 26/08 | Badges nas abas + CI corrigido | arquivo |
| 26/08 | SSO + Sair encerra o portal | arquivo |
| 26/08 | Fix filtro §4 — automáticos na fila de suporte | arquivo |
| 26/08 | UI + fix agendador | arquivo |
| 26/08 | Sair volta ao portal | arquivo |
| 24/08 | Melhorias de UI + Coletor | arquivo |
| 24/08 | Pente fino completo das AF | arquivo |

> **abaixo** = o diário completo está neste arquivo · **arquivo** =
> `_archive/sessao_atual_historico/SESSAO_ATUAL_historico_2026-08.md` (agosto e primeiras sessões de setembro)
> ou `SESSAO_ATUAL_historico_2026-09.md` (setembro)
>
> **Regra:** este arquivo guarda as **3 sessões mais recentes**. O `/fechar` acrescenta a
> linha nova aqui e move a 4ª sessão para o arquivo.

---

## 📓 Diário da sessão (2026-09-18 segunda sessão) — Casos 4–6 Remitly: decisão de status + conclusão do Padrão 2

### O que foi feito

1. **Simulação dos Casos 4, 5, 6 (Remitly)** — consultou banco e mostrou contexto completo das 3 threads que aguardavam decisão de Michel.

2. **Caso 4 (Remitly CC - 4010/4016) — já resolvido** — estava Concluída antes mesmo da revisão. O recálculo automático do pipeline corrigiu após Fix1+Fix2. Nenhuma ação necessária.

3. **Casos 5 e 6 confirmados como Aguardando Finaud (correto)** — Michel decidiu: AF está certo nos dois.
   - Caso 5 (Re: Remitly CC - 4010 - 07): thread com apenas 1 mensagem capturada (Andrea/Finaud: "Recebido. Obrigada!"). Ainda há trabalho da Finaud a fazer.
   - Caso 6 (Re: VIS - ENVIAR CADOC e DDR): Mônica disse "estarei colocando as remessas em dia" — Finaud ainda precisa processar e enviar ao BACEN.

4. **Dois cenários documentados em PENDENCIAS.md (Teste de IA):**
   - Cenário A: thread com 1 mensagem — IA pode precisar do thread completo para classificar com segurança
   - Cenário B: mensagem de intenção futura ("estarei fazendo X") — IA precisa conhecer o papel da Finaud vs cliente
   - Ponto geral de Michel: prompt precisará de "contexto de negócio" (tipos de documentos, papel de cada parte)

5. **Padrão 2 (Finaud→Cliente) encerrado** — todos os 22 casos resolvidos. Seção marcada ✅ no PENDENCIAS.md; decisão registrada no REGISTRO_CORRECOES.md.

### Próximo passo

**🔴 Threads irmãs — chat dedicado.** 11 grupos com thread Concluída + pendente no mesmo caso. Revisar cada grupo com Michel para separar casos reais de falsos positivos, definir critério de detecção e fluxo de tratamento.

**Pendências restantes (ordem de prioridade):**
- 🔴 **Threads irmãs** — 11 grupos · chat dedicado
- 🟡 **Teste de IA** — Fase 1 nos ~80 suspeitos; avaliar substituição do regex por IA. Cenários A e B documentados no PENDENCIAS.md.
- 🟡 **Gap 3 coletor colaboradores** — implementar threadId-based matching + simular nas 6 caixas (OK de Michel antes de rodar)
- 🟡 **Modal** — Cenário 2b (citação dupla COSIF) + `white-space: nowrap` na coluna Valor

Último /fechar: 2026-09-18 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-18) — Trilha de Auditoria: implementação completa + deploy VPS

### O que foi feito

1. **Trilha de Auditoria completa** — nova tela própria no menu Administração (sidebar), substituindo a tentativa anterior que era uma aba dentro da seção E-mail (lugar errado).

2. **Cobertura total de telas** — `_auditMapearTela()` mapeia todos os `data-pagina` do SPA (E-mails, Fogbugz, Administração) para `{menu, tela}`. `navegar()` interceptado: cada troca de tela dispara heartbeat imediato com menu+tela corretos.

3. **Heartbeat corrigido** — antes enviava `document.title` (genérico); agora usa `_auditTelaAtual` (específico por tela).

4. **Tabela da Trilha** — colunas: Data/Hora (formato BR DD/MM/AAAA), Usuário, Tipo, Origem (app/portal), Menu, Tela. Coluna IP removida a pedido de Michel (dado gravado no banco, não exibido).

5. **Backend** — `banco_threads.py`: migração `ADD COLUMN menu` (idempotente); `registrar_acesso()` com `menu=`; `ler_log_acesso()` retorna `menu`. `servidor_telas.py`: `_log_tela()` inclui `menu`; endpoint heartbeat extrai `menu` do JSON.

6. **Deploy** — 3 commits (`06764ff` · `c7dc66e` · `1f74387`) · push · VPS `active` · 678 testes passando.

### Próximo passo

**Cruzando com PENDENCIAS.md — ordem de prioridade:**

- 🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.
- 🟡 **Teste de IA** — Fase 1 nos ~80 suspeitos; avaliar substituição do classificador de regex por IA (elimina erros tipo Fix1/Fix2 para sempre). Ver PENDENCIAS.md.
- 🟡 **Recalcular threads após Fix1+Fix2** — rodar `recalcular_status_todos()` em produção para as 13 threads com status errado.
- 🟡 **Casos 4, 5, 6 (Remitly)** — aguardam decisão de Michel ("Recebido. Obrigada." e "estarei colocando as remessas em dia" — AF ou Concluída?).
- 🟡 **Gap 3 coletor colaboradores** — implementar + simular nas 6 caixas com OK de Michel.
- 🟡 **Modal** — Cenário 2b + `white-space: nowrap` na coluna Valor.

Último /fechar: 2026-09-18 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-14) — Empresa no Resumo + Fix1+Fix2 + investigação mensagens

### O que foi feito

1. **Empresa no Resumo Semanal — deployado** — `config/mapeamento_empresas.json` (42 domínios) + `_extrair_empresa()` reescrita para usar domínio do remetente em vez do assunto. 6 testes novos. Commit `cb5fc6c`, VPS atualizada. Limitação Padrão 2 documentada em PENDENCIAS.

2. **Fix1+Fix2 — commitado e deployado** — Fix1: `tudo\s+(?:bem|bom)` no `_SAUDACAO_RE`; Fix2: `'calcule '` no `_FRASES_PEDIDO_EXPLICITO`. Cobre 13 casos confirmados de status AF errado. 669 testes passando. Commit `7d83f19`, VPS atualizada.

3. **Investigação: mensagens no Gmail mas não no sistema** — análise completa do caso Remitly (`1a01a9391d25286d`): Hebert enviou direto para `andrea@` às 11:58; o coletor de colaboradores encontrou o e-mail mas o descartou por não ter `In-Reply-To`. A VPS tem `colaboradores_suporte` com 6 e-mails configurados (não estava vazia — era campo local desatualizado). Root cause: coletor ignora e-mails originais (sem In-Reply-To).

4. **Solução desenhada e documentada** — substituir `In-Reply-To` por `threadId` do Gmail como método primário de encaixe + criar threads novas para e-mails de domínios corporativos (filtro por `_DOMINIOS_GENERICOS`) + lista `captura_excecoes` no config para casos de domínio pessoal. Decisão gravada em PENDENCIAS.md (Gap 3 do coletor colaboradores). Implementação depende de simulação prévia nas 6 caixas com OK de Michel.

### Próximo passo

**Cruzando com PENDENCIAS.md — ordem de prioridade:**

- 🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.
- 🟡 **Recalcular threads após Fix1+Fix2** — rode `recalcular_status_todos()` em produção para que as 13 threads marcadas incorretamente recebam AC. Feito no início do próximo chat.
- 🟡 **Casos 4, 5, 6 (Remitly)** — aguardam decisão de Michel: "Recebido. Obrigada." é AF (ainda processando) ou Concluída? "estarei colocando as remessas em dia" é AF ou Concluída?
- 🟡 **Gap 3 coletor colaboradores** — implementar + simular nas 6 caixas (Michel aprova antes de rodar). Ver decisão em PENDENCIAS.md.
- 🟡 **Teste de IA** — rodar `testar_status_ia.py --fase 1`
- 🟡 **Modal** — Cenário 2b + `white-space: nowrap` na coluna Valor

Último /fechar: 2026-09-14 — memórias revisadas ✅

---

<!-- fim das 3 sessões recentes -->
