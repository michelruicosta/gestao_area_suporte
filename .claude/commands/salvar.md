---
description: "SALVA NO MEIO DA SESSÃO — use quando o chat estiver ficando longo ou antes de algo arriscado. Para fechar o dia, use /fechar."
argument-hint: [descrição curta do que foi feito (opcional)]
---

# /salvar — Salvar progresso no meio da sessão

> **Quando usar:** durante a sessão, quando quiser salvar um progresso importante antes de continuar.
> **Não usar no final do chat** — para encerrar, use `/fechar` (ele atualiza o bordo E salva).
>
> **Regra simples:** se você está no meio do dia e terminou algo importante, use o `/salvar`.
> Se for fechar o chat, use o `/fechar` — ele faz tudo.
>
> Exemplos práticos de quando usar o `/salvar`:
> - Acabou de rodar uma carga e quer garantir que os dados e logs estão salvos antes de continuar
> - Vai fazer algo que pode dar errado (ex.: rodar um script novo) e quer um ponto de retorno
> - O chat já está muito longo e você ainda tem mais trabalho pela frente

Você é o **Gestor do Projeto Gestão Área Suporte** cuidando do versionamento, em linguagem simples
(o usuário é leigo). Regra de ouro: **commit é local e reversível** (pode fazer após validar);
**push envia pro GitHub** (sempre mostrar o que vai e pedir OK antes).

## Passo 0 — Arrumar rascunhos (faxina segura, antes de commitar)
1. **Mover sozinho (risco zero):** rascunhos de raiz `tmp*.py` e `tmp*.txt` → `_archive/rascunhos_raiz_AAAAMMDD/`
   (são scratch, já ignorados pelo `.gitignore`; movimento puro de arquivo). Informe quantos moveu.
2. **Só sinalizar, NUNCA mover sozinho:** scripts nomeados soltos em `scripts/` que pareçam one-off
   (`backfill_*`, `simular_*`, `pf*_backfill*`, `_analise_*`, `injetar_*`, `buscar_*`). Liste-os e
   **pergunte** se o usuário quer arquivar em `_archive/correcao|simulacao|analise/`. Mover script
   nomeado às cegas já quebrou o projeto antes — só mova após confirmar que ninguém o importa
   (`grep` por `import <nome>` no núcleo) e com o "sim" do usuário.
3. Destinos no `_archive/` (já existe): `correcao/` (backfills aplicados), `simulacao/` (simulações),
   `analise/` (análises, diagnósticos e relatórios `.txt`).

## Passo 1 — Mostrar o que mudou
1. Rode `git status -sb` e `git diff --stat` e dê um resumo simples: quantos arquivos mudaram e quais
   os principais.
2. Confirme que nada sensível está entrando. O `.gitignore` já bloqueia `.env`, `data/`, `logs/` e
   backups — mas avise se algo suspeito aparecer como arquivo novo.
3. Confirme a branch com `git branch --show-current`. Se for `main`, **pare e avise** — o trabalho deve
   ir numa branch de desenvolvimento, nunca direto na `main`.

## Passo 2 — Commitar (local, seguro)
1. Agrupe as mudanças de forma coerente. Se forem assuntos diferentes, sugira mais de um commit.
2. Proponha a(s) mensagem(ns) no padrão do projeto: `fix:`, `feat:`, `test:`, `refactor:`, `docs:`
   (+ escopo entre parênteses quando fizer sentido), em português. Contexto do usuário: "$ARGUMENTS".
3. Faça o(s) commit(s). NUNCA use `--no-verify`.

## Passo 3 — Enviar ao GitHub (só com OK)
1. Mostre quantos commits estão prontos para enviar: `git log origin/<branch>..HEAD --oneline`.
2. **Pergunte explicitamente** se pode enviar (`git push`). Só faça o push depois do "sim".
3. Nunca use `git push --force`. Se o push for rejeitado, explique o motivo em vez de forçar.
