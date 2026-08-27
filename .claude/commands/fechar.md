---
description: "FECHA O CHAT — atualiza o bordo e salva no git. Use só no final do dia. Não precisa de /salvar depois: este já faz tudo."
---

# /fechar — Encerramento da sessão

> **Quando usar:** só no final do dia, quando for fechar o chat.
> **Não precisa** rodar `/salvar` depois — este comando já inclui o commit e o push.
> Se quiser salvar no meio da sessão, use `/salvar`. No final, use só este.

Você é o **Gestor do Projeto Gestão Área Suporte** fazendo o ENCERRAMENTO da sessão. Execute os dois
blocos abaixo em ordem. Não pule nenhum.

## Bloco 1 — Atualizar os arquivos de bordo

Atualize cada arquivo abaixo. Para os que não precisarem de mudança, diga "sem alteração".

1. **`SESSAO_ATUAL.md`** — estado AG/CO/pytest · tabela do que foi feito nesta sessão · reescrever
   os PASSOS de "o que fazer agora" com o que ficou faltando.
   **Antes de escrever o "Próximo passo", cruzar com `PENDENCIAS.md`:** se houver item 🔴 URGENTE
   que não está no topo da fila, colocá-lo na frente. O SESSAO_ATUAL define a ordem de execução —
   o PENDENCIAS é o estoque. Os dois devem estar alinhados ao encerrar.

   **1.1 — Manter o arquivo enxuto (3 sessões):** o `SESSAO_ATUAL.md` guarda o diário completo
   das **3 sessões mais recentes**. Ao escrever o diário de hoje:
   - acrescentar uma linha na tabela **"🗂️ Sessões anteriores"**, no topo (data · tema · `abaixo`);
   - se passar de 3 diários, **mover o mais antigo** para
     `_archive/sessao_atual_historico/SESSAO_ATUAL_historico_AAAA-MM.md` (criar o arquivo do mês
     se não existir, com o mesmo cabeçalho dos anteriores) e trocar o `abaixo` daquela linha por
     `arquivo`.
   - **Nunca editar o texto do diário ao mover** — ele vai como está.
2. **`documentações/REGISTRO_CORRECOES.md`** — entrada datada (HH:MM) para cada mudança feita, com
   ✅ VALIDADO ou ⚠️ VALIDAÇÃO PENDENTE (sempre com critério mensurável).
3. **`documentações/PENDENCIAS.md`** — status novo de cada pendência tocada (aberta / concluída / cancelada).

Mostre ao usuário um resumo de uma linha por arquivo do que foi escrito.

4. **Decisões do dia:** antes de avançar, fazer uma varredura rápida do chat e perguntar:
   *"Ficou alguma decisão importante na conversa de hoje que ainda não foi registrada em nenhum arquivo?"*
   Se sim: registrar agora no lugar certo (ver tabela no `CLAUDE.md` — regra "toda decisão importante").
   Se não: seguir para o item 5.

5. **Varredura de VALIDAÇÃO PENDENTE:** executar o grep abaixo e listar os resultados para o Michel:

   ```powershell
   Select-String -Path "documentações/REGISTRO_CORRECOES.md" -Pattern "VALIDAÇÃO PENDENTE" | Select-Object LineNumber, Line
   ```

   Para cada entrada encontrada, perguntar: *"Esta validação já pode ser marcada como ✅ VALIDADO?
   (critério: a carga rodou e os casos-alvo estão corretos)"*
   - **Sim** → atualizar a linha no REGISTRO substituindo ⚠️ VALIDAÇÃO PENDENTE pelo critério cumprido + ✅ VALIDADO
   - **Não** → manter como está e registrar no PENDENCIAS.md se precisar de acompanhamento

   Só avançar para o Bloco 1.6 após resolver ou registrar cada pendência.

## Bloco 1.6 — Checklist obrigatório: recursos externos

Antes de avançar para Bloco 2, responder:

- **Criei ou alterei algo externo nesta sessão?** (tarefa agendada, webhook, integração cloud, API, etc.)
  - Não ☐ → avance para Bloco 2
  - Sim ☐ → responda as próximas perguntas

- **Está documentado em `documentações/TAREFAS_AGENDADAS.md`?**
  - Não ☐ → **PARAR aqui e documentar agora** (use a estrutura IF-01: O que é → Por que → Como → Regras → Exemplos → Dependências)
  - Sim ☐ → avance para Bloco 2

**Por quê:** Próxima IA não precisa refazer o trabalho. Documentação é aprendizagem, não burocracia.

## Bloco 1.7 — Trava de encerramento (não pular)

Responda explicitamente cada pergunta antes de avançar para o commit:

1. **O que toquei nesta sessão?** — listar arquivos de código e documentação modificados
2. **Atualizei o documento certo para cada mudança?**
   - Código mudou → REGISTRO_CORRECOES.md tem entrada datada? ☐
   - Pendência resolvida → saiu do PENDENCIAS.md? ☐
   - Pendência nova → entrou no PENDENCIAS.md? ☐
   - Regra nova → entrou no CLAUDE.md? ☐
3. **Há restrição temporária que expirou hoje?** — verificar seção "Regra em vigor" do SESSAO_ATUAL.md
   - Se sim: remover do SESSAO_ATUAL.md e registrar no REGISTRO que foi levantada

Só avançar para o Bloco 2 após responder as 3 perguntas.

## Bloco 1.8 — Revisão de memórias (não pular)

Comparar o que foi feito nesta sessão com as memórias existentes em
`C:\Users\Bruna\.claude\projects\D--02-Finaud-Projetos-ativos-gestao-area-suporte\memory\`
e verificar se alguma ficou desatualizada.

**Perguntas a responder:**
1. Alguma memória de **projeto** (`projeto-*`, `nova-arquitetura-*`, `estrutura-*`) registra um
   fato que já não é mais verdadeiro?
2. Alguma memória de **feedback** (`feedback_*`) foi contrariada ou confirmada de forma nova hoje?
3. Alguma memória cita arquivo, função ou caminho que mudou hoje?

**Para cada memória desatualizada encontrada:**
- Atualizar o arquivo diretamente
- Registrar no `MEMORY.md` se o título ou descrição mudou

**Se nenhuma ficou desatualizada:** dizer explicitamente "memórias OK — nenhuma desatualizada hoje".

Depois de revisar, registrar no `SESSAO_ATUAL.md` a linha:
```
Último /fechar: YYYY-MM-DD HH:MM — memórias revisadas ✅
```

## Bloco 2 — Salvar no git (commit + push)

Depois de atualizar o bordo, salve tudo no git:
1. **Faxina:** varrer arquivos temporários soltos (`tmp*`, `_probe_*`, `*.out`) — mover para `_archive/`.
2. **Mostrar** o que vai no commit: `git status -sb` + `git diff --stat`. Trabalhamos direto na
   `main` (`CLAUDE.md` §6) — ramo separado só na exceção acordada, avisando antes.
3. **Um commit só:** incluir JUNTOS o bordo (SESSAO_ATUAL, PENDENCIAS, REGISTRO) e qualquer código
   pendente do dia. Não fazer commit separado só de bordo — isso faz os testes rodarem uma vez extra
   sem necessidade (~4 min a mais). Só separar se os assuntos forem muito distintos e precisarem de
   histórico próprio (ex.: fix de motor + documentação de outra funcionalidade).
   Mensagem no padrão do projeto: `docs(bordo):`, `fix:`, `feat:`, etc. — em português. Nunca `--no-verify`.
4. **Perguntar** antes do push. Nunca `--force`.
