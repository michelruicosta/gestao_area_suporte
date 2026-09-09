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
| 09/09 | Contaminação cruzada DRM 2060: investigação, restauração e prevenção | abaixo |
| 09/09 | Sentry: guia interativo + fix UndefinedError media_dias | abaixo |
| 09/09 | Modal — Cenário 3: listas com marcadores implementadas e publicadas na VPS | abaixo |
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

## 📓 Diário da sessão (2026-09-09) — Contaminação cruzada DRM 2060: investigação, restauração e prevenção

### O que foi feito

1. **Investigação do bug** — Michel relatou que o sistema mostrava mensagens erradas na thread Trustee DTVM (`1a05d9178be1c1b7`). Sistema: 22 msgs, última Flávio → Raphael (WU). Gmail real: 2 msgs, Miguel Santos → Igor Menezes Costa (Trustee). Outras threads do DRM 2060 com o mesmo problema.

2. **Causa raiz confirmada** — `scripts/coletor_enviados_colaboradores.py` identifica a qual thread uma mensagem pertence pelo assunto normalizado (sem Re:/ENC:/FW:). Com 20+ threads compartilhando "BANCO CENTRAL - COMUNICACAO DE INCONSISTENCIA NO DRM - 2060", todas caem na mesma chave — mensagens de um cliente vão parar em threads de outros. 527 threads contaminadas em 8 ondas entre 02/09 e 09/09/2026.

3. **Restauração do banco** — re-buscamos os 527 threads diretamente na API do Gmail via `_processar_thread` + `salvar_thread`. 168 threads decontaminadas. Trustee DTVM: 22 msgs → 2 msgs, destinatário corrigido (WU → Trustee) ✅. Snapshots antes/depois em `data/backups/snapshot_antes_restauracao.csv` e `snapshot_depois_restauracao.csv`. Backup do banco em `data/backups/20260909_1529_restauracao_banco/`.

4. **Prevenção** — `executar_pipeline.py` (função `rodar_sem_retorno`): `coletar_colaboradores()` desativado com comentário explicativo até o bug ser corrigido.

5. **Documentação** — `PENDENCIAS.md` e `REGISTRO_CORRECOES.md` atualizados com a contaminação.

6. **Commit `e714861`**, push e deploy VPS — tela + agendador ativos ✅.

7. **Fix do coletor encontrado já implementado** — ao fechar a sessão, descobrimos que a sessão anterior havia implementado o fix completo em `coletor_enviados_colaboradores.py` (usando `Message-ID`/`In-Reply-To` em vez de assunto), reativado o coletor em `executar_pipeline.py` e escrito 20 testes, mas não havia commitado. 638 testes passando ✅. Coletor voltou a rodar — bug resolvido.

### Estado atual

**pytest:** 638 passed ✅ (test_coletor_colaboradores.py reescrito com nova lógica).
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `e714861` publicado.
**Coletor de colaboradores:** ATIVO com fix de Message-ID/In-Reply-To. ✅

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — acabamentos menores: Cenário 2b (COSIF citada 2× perde espaços duplos) e `white-space: nowrap` na coluna Valor
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-09 17:00 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-09) — Sentry: guia interativo + fix UndefinedError media_dias

### O que foi feito

1. **Guia interativo do Sentry** — artifact publicado em claude.ai com 6 abas (Erros, Rastreamento, Perfis, Logs, Relógio, Proteção de Dados), cada uma seguindo a estrutura âncora simples → conceito técnico → consequência prática → o que fazer. Dados reais do projeto (4,81s, nomes das rotas, filtros LGPD).

2. **Fix: `UndefinedError 'dict object' has no attribute 'media_dias'`** — Sentry capturou o erro às 13h21 de hoje na rota `index` (`gestao_email.html`, linha 2104).
   - **Causa:** template tinha coluna "Média/caso" usando `p.media_dias` no ranking FOG, mas `servidor_telas.py` não calculava esse campo no dict. As mudanças estavam no working tree não commitado; o servidor em produção rodava `a5521b5` (commit anterior) sem o campo.
   - **Correção:** `media_dias` adicionado ao dict do ranking em `index()` (`servidor_telas.py`, linha 663); template com coluna "Média/caso" + grid 6 colunas + ordenação; teste `test_ranking_media_dias_calculada` adicionado.
   - **642 testes passando ✅**. Commit `32fb917`, push e deploy na VPS — tela + agendador ativos.

### Estado atual

**pytest:** 642 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `32fb917` publicado.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — acabamentos menores: Cenário 2b (COSIF citada 2× perde espaços duplos) e `white-space: nowrap` na coluna Valor
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-09 14:45 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-09) — Modal: Cenário 3 — listas com marcadores implementadas e publicadas

### O que foi feito

Sessão dedicada ao **Cenário 3 da leitura inteligente**: detecção automática de listas com marcadores (`-`, `*`, `•`, `N.`, `N)`) no texto das mensagens do modal, renderizando `<ul>`/`<ol>` em vez de texto plano.

1. **Pesquisa na base local** — varridos os 153 threads com listas no banco (`corpo_texto`): padrão traço (`- item`), asterisco Outlook (`  *   item`), numerada (`1. texto`). Falsos positivos identificados: URLs nos itens, traço no meio de frase, menos de 3 itens, item >300 chars.

2. **Implementação em `templates/gestao_email.html`:**
   - CSS adicionado: `.msg-lista` e `.msg-lista li` (~linha 661)
   - Nova função `_listaMarcadores(texto)` inserida após `_tabelaEspacos`:
     - Detecta ≥3 itens consecutivos (linhas em branco entre itens são toleradas)
     - Exclui URLs nos itens e itens >300 chars
     - Retorna HTML com `.msg-tcampos-badge` + `<ul>`/`<ol class="msg-lista">` + toggle "Ver texto original"
   - 5 call sites encadeados: `m.texto_novo` (×2), `m.corpo_encaminhado`, `m.historico_citado`, `m.corpo`

3. **Validação Node.js** — 6 casos reais: 4 devem detectar (ul seguido, ul com blanks, ol numerada), 2 devem ignorar (URLs, só 2 itens). Resultado: **6/6 ✅**.

4. **pytest:** 640 passed ✅ (zero regressões).

5. **Teste na UI:** Michel pesquisou "Posição de Câmbio corretora" na Visão Geral → thread `1a010965b497ec0f` → badge "📋 Lista detectada" apareceu, `<ul>` renderizado, toggle funcionou.

6. **Commit, push e deploy na VPS:** commit `a5521b5`, serviço `gestao-suporte` active ✅. Site responde normalmente em `gestao-suporte.finaudapps.com.br`.

### Estado atual

**pytest:** 640 passed ✅.
**Produção:** `gestao-suporte.finaudapps.com.br` — tela + agendador ativos ✅. Commit `a5521b5` publicado.

### Próximo passo

🔴 **Threads irmãs** — 11 grupos com thread Concluída + pendente no mesmo caso. Chat dedicado.

**Pendências que continuam:**
- 🟡 Modal — acabamentos menores: Cenário 2b (COSIF citada 2× perde espaços duplos) e `white-space: nowrap` na coluna Valor
- 🟡 Passo C — tela de manutenção de regras
- 🟡 Monitorar caixas colaboradores Gap 3 — 345 threads sem passar por suporte@

Último /fechar: 2026-09-09 — memórias revisadas ✅

---

---
<!-- fim das 3 sessões recentes -->
