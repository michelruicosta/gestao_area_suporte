---
description: "FECHA O CHAT — atualiza o bordo e salva no git. Use só no final do dia. Não precisa de /salvar depois: este já faz tudo."
---

# /fechar — Encerramento da sessão

> **Quando usar:** só no final do dia, quando for fechar o chat.
> **Não precisa** rodar `/salvar` depois — este comando já inclui o commit e o push.
> Se quiser salvar no meio da sessão, use `/salvar`. No final, use só este.

Você é o **Gestor do Projeto Oráculo 360** fazendo o ENCERRAMENTO da sessão. Execute os dois
blocos abaixo em ordem. Não pule nenhum.

## Bloco 1 — Atualizar os arquivos de bordo

Atualize cada arquivo abaixo. Para os que não precisarem de mudança, diga "sem alteração".

1. **`SESSAO_ATUAL.md`** — estado AG/CO/pytest · tabela do que foi feito nesta sessão · reescrever
   os PASSOS de "o que fazer agora" com o que ficou faltando.
   **Antes de escrever o "Próximo passo", cruzar com `PENDENCIAS.md`:** se houver item 🔴 URGENTE
   que não está no topo da fila, colocá-lo na frente. O SESSAO_ATUAL define a ordem de execução —
   o PENDENCIAS é o estoque. Os dois devem estar alinhados ao encerrar.
2. **`documentações/REGISTRO_CORRECOES.md`** — entrada datada (HH:MM) para cada mudança feita, com
   ✅ VALIDADO ou ⚠️ VALIDAÇÃO PENDENTE (sempre com critério mensurável).
3. **`documentações/PENDENCIAS.md`** — status novo de cada pendência tocada (aberta / concluída / cancelada).
4. **`documentações/PLANO_IMPLEMENTACAO_MOTOR.md`** — marcar itens com ✅ ou ⚠️ PARCIAL se foram tocados.

Mostre ao usuário um resumo de uma linha por arquivo do que foi escrito.

5. **Decisões do dia:** antes de avançar, fazer uma varredura rápida do chat e perguntar:
   *"Ficou alguma decisão importante na conversa de hoje que ainda não foi registrada em nenhum arquivo?"*
   Se sim: registrar agora no lugar certo (ver tabela no `CLAUDE.md` — regra "toda decisão importante").
   Se não: seguir para o Bloco 1.5.

6. **Varredura de VALIDAÇÃO PENDENTE:** executar o grep abaixo e listar os resultados para o Michel:

   ```powershell
   Select-String -Path "documentações/REGISTRO_CORRECOES.md" -Pattern "VALIDAÇÃO PENDENTE" | Select-Object LineNumber, Line
   ```

   Para cada entrada encontrada, perguntar: *"Esta validação já pode ser marcada como ✅ VALIDADO?
   (critério: a carga rodou e os casos-alvo estão corretos)"*
   - **Sim** → atualizar a linha no REGISTRO substituindo ⚠️ VALIDAÇÃO PENDENTE pelo critério cumprido + ✅ VALIDADO
   - **Não** → manter como está e registrar no PENDENCIAS.md se precisar de acompanhamento

   Só avançar para o Bloco 1.5 após resolver ou registrar cada pendência.

## Bloco 1.5 — Auditoria rápida de documentação

> **Importante:** Este bloco roda automaticamente e NÃO bloqueia o commit. Serve para detectar
> inconsistências de bordo ANTES de fazer git push.

Execute este comando:

```powershell
cd D:\oraculo_360_finaud
$auditResult = python scripts/auditar_documentacao.py | ConvertFrom-Json
```

Mostre o resultado:

```powershell
Write-Host "🔍 Auditoria de documentação:" -ForegroundColor Cyan
Write-Host "Status: $($auditResult.status)" -ForegroundColor $(if($auditResult.status -eq 'PASS') { 'Green' } else { 'Yellow' })

if ($auditResult.errors.Count -gt 0) {
    Write-Host "`n⚠️ ERROS ENCONTRADOS:" -ForegroundColor Red
    $auditResult.errors | ForEach-Object { Write-Host "  ❌ $_" }
    Write-Host "`n(Os achados ficam registrados em documentações/AUDITORIA_ULTIMACARGA_VALIDACAO.md)"
}

if ($auditResult.warnings.Count -gt 0) {
    Write-Host "`nℹ️ Avisos:" -ForegroundColor Yellow
    $auditResult.warnings | ForEach-Object { Write-Host "  ⚠️ $_" }
}

if ($auditResult.status -eq 'PASS') {
    Write-Host "`n✅ Documentação OK" -ForegroundColor Green
}
```

Se encontrar **erros** (não só avisos):
- Conferir qual arquivo precisa atualizar
- Corrigir agora (antes do commit)
- Rodar a auditoria novamente para confirmar
- Depois avançar para o Bloco 2

Se encontrar só **avisos**: você decide se corrige agora ou registra em PENDENCIAS.md para depois.
Se não encontrar nada: avance direto para Bloco 2.

## Bloco 1.55 — Verificar links quebrados na documentação

Execute:

```powershell
cd D:\oraculo_360_finaud
python scripts/verificar_links_documentacao.py
```

- **"OK - Nenhum link quebrado"** → avance para Bloco 1.6
- **"ATENCAO: X link(s) quebrado(s)"** → corrigir agora antes do commit, depois rodar novamente para confirmar

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
   - Documento criado ou movido para `_archive/`? → seção 5 do MAPA_DO_PROJETO.md atualizada? ☐
3. **Há restrição temporária que expirou hoje?** — verificar seção "Regra em vigor" do SESSAO_ATUAL.md
   - Se sim: remover do SESSAO_ATUAL.md e registrar no REGISTRO que foi levantada
4. **Os números AG/CO do SESSAO_ATUAL.md estão corretos?** — comparar com os valores ao vivo:
   ```powershell
   python -c "import json; ag=json.load(open('data/json/pipeline/threads_aguardando_auto.json',encoding='utf-8')); co=json.load(open('data/json/pipeline/threads_concluidas_auto.json',encoding='utf-8')); print(f'AG: {len(ag)} | CO: {len(co)}')"
   ```
   - Se divergir: corrigir o SESSAO_ATUAL antes de commitar

Só avançar para o Bloco 2 após responder as 4 perguntas.

## Bloco 1.8 — Revisão de memórias (não pular)

Comparar o que foi feito nesta sessão com as memórias existentes em
`C:\Users\Bruna\.claude\projects\D--oraculo-360-finaud\memory\` e verificar se alguma ficou desatualizada.

**Perguntas a responder:**
1. Alguma memória em `tecnico/` descreve algo que mudou hoje no código ou no sistema?
2. Alguma memória em `projeto/` registra um fato que já não é mais verdadeiro?
3. Alguma memória em `comportamento/` foi contrariada ou confirmada de forma nova hoje?

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
2. **Mostrar** o que vai no commit: `git status -sb` + `git diff --stat`. Confirmar branch (nunca `main`).
3. **Um commit só:** incluir JUNTOS o bordo (SESSAO_ATUAL, PENDENCIAS, REGISTRO) e qualquer código
   pendente do dia. Não fazer commit separado só de bordo — isso faz os testes rodarem uma vez extra
   sem necessidade (~4 min a mais). Só separar se os assuntos forem muito distintos e precisarem de
   histórico próprio (ex.: fix de motor + documentação de outra funcionalidade).
   Mensagem no padrão do projeto: `docs(bordo):`, `fix:`, `feat:`, etc. — em português. Nunca `--no-verify`.
4. **Perguntar** antes do push. Nunca `--force`.
