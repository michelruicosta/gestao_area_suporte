# Histórico de sessões — agosto–setembro/2026

> Diários arquivados do `SESSAO_ATUAL.md`, movidos para manter o arquivo de bordo enxuto —
> ele é lido inteiro em todo `/iniciar`.
> **Índice de todas as sessões** → `SESSAO_ATUAL.md`, seção "Sessões anteriores".
> Nada foi editado: os textos estão exatamente como foram escritos.

---

## 📓 Diário da sessão (2026-09-01) — Administração: E-mail, Notificações e aviso por e-mail

### O que foi feito

**Frente única: organizar a Administração e o recado quando a busca de e-mail parar**

Michel pediu um mapa claro ao abrir a tela, depois aprovou item a item e pediu para implementar e publicar.

**Decisões aprovadas**
- Administração só para administrador.
- Três menus: **E-mail** (abas na mesma pasta), **Notificações**, **Usuários e Perfis**.
- E-mail: buscar agora, histórico, agendamentos (só e-mails; Fog saiu), regras de Sem Retorno, situação da busca (só luz ligada/parada).
- Notificações: o que é, ligada/desligada, grupos (Administrador / Gestor / Operador — pode marcar vários).
- Primeiro recado: **Busca de e-mail parou**. Quem recebe = grupo, não caixa no cadastro.
- Entrada no dia a dia pelo **portal**, não pela URL direta.
- Visual do e-mail: envelope Finaud (igual Portal/Auditoria), botão Abrir a Gestão → portal.

**O que subiu em produção** (`a8d7799`)
- Telas novas da Administração.
- E-mail no visual aprovado, um recado por episódio de parada (relógio a cada 15 min).
- Não sobe neste commit: motivos/filtros do outro chat, lista de pendências, rascunhos HTML locais.

### Estado atual

**Produção:** no ar em `gestao-suporte.finaudapps.com.br` (entrar pelo portal).
**GitHub:** `main` em `a8d7799`.
**pytest:** `tests/test_servidor_telas.py` + `tests/test_agendador_pipeline.py` → 24 passed.
**Assunto deste chat:** encerrado.

Último /fechar: 2026-09-01 11:56 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-28/29) — Planilha de classificação + bug Outlook no grupo saudação

### O que foi feito

**Frente principal: projetar a planilha de referência de motivos e investigar o grupo "saudação"**

---

**1. Grupo D — análise concluída**

Thread `1a01b7bb8a4e4c5c` (Caroline Costa de Oliveira, Global Exchange, 19/08 19:24):
- Mensagem: "Prezados, boa tarde!" — 1 mensagem no banco, sem conteúdo identificável
- Contexto: Caroline enviou após Flávio (Finaud) entregar os relatórios DLO às 16:00
- Classificação atual: DLO_2061 / Aguardando Finaud / "Cliente enviou saudação"
- Conclusão: sem sinal de entrega, pergunta ou solicitação detectável — motivo correto
  seria "Mensagem sem conteúdo identificado — aguarda verificação"

**Por que 3 threads para a mesma conversa:**
O Gmail cria Thread IDs separados quando:
- O filtro `**UNVERIFIED SENDER**` modifica o assunto (remetente externo não verificado)
- Os destinatários mudam (alguém entra ou sai do CC)
- Alguém responde num ramo mais antigo da cadeia em vez da última mensagem

Confirmado no Gmail de Michel: 3 threads para "Tratamento prudencial dos Direitos de Uso na
apuração do DLO" (Caroline + 2 threads do Rodrigo, mesma conversa de negócio).

---

**2. Solução aprovada para agrupamento de threads**

Usar os cabeçalhos `In-Reply-To` e `References` do protocolo de e-mail. Todo e-mail de
resposta carrega o Message-ID do original — com esses campos o sistema sabe que dois
Thread IDs diferentes são ramos da mesma conversa.

Contexto completo (o que cobre, o que não cobre, como implementar):
`documentações/PENDENCIAS.md` → seção "COLETOR + TELAS — Agrupar threads relacionadas".
Chat dedicado para implementação criado em 28/08/2026.

---

**3. Planilha de referência de motivos — estrutura 100% definida**

Objetivo: o usuário abre a planilha ao lado do sistema para entender por que uma thread
recebeu determinado Status + Motivo.

**Aba 1 — REGRAS** (uma linha por motivo):

| Status | Motivo | Razão do motivo | Termos que acionaram o motivo | Criado em | Situação |

- **Status:** Aguardando Finaud / Aguardando Cliente / Concluída
- **Motivo:** texto exato exibido na tela
- **Razão do motivo:** explicação de negócio em linguagem simples
- **Termos que acionaram o motivo:** palavras/frases que o sistema detectou na mensagem
- **Criado em:** data de criação (dd/mm/aaaa)
- **Situação:** Ativa ou Inativa — nunca apagar linha, só inativar

**Aba 2 — ALTERAÇÕES DE REGRAS** (cresce ao longo do tempo):

| Quando | Motivo | Campo alterado | Antes | Depois |

---

**4. Motivos aprovados por Michel — conteúdo da aba REGRAS**

*Aguardando Finaud:* 1–5 (informações/extratos, pergunta, solicitação, questionou resposta, e-mail interno)
*Aguardando Cliente:* 6–11 (extrato/planilha, orientação técnica, reunião/ligação, pergunta, prometeu retornar, enviou arquivo)
*Concluída:* 12–13 (concluiu solicitação, agradeceu)
*Pendente:* 14 — grupo "saudação" (aguardava correção do bug Outlook)

---

**5–7. Bug Outlook descoberto e corrigido**

`_extrair_texto_novo()` parava na primeira linha `De:` do cabeçalho automático do Outlook e
descartava o conteúdo real. Corrigido em commit `bce6add`: só interrompe se já houver
conteúdo real antes do separador. Validação: 403 testes + deploy + recalculate ✅

### Estado atual

**GitHub:** `main` em `a5ecaf0`. **Artefato motivos:** 18 de 18 aprovados ✅

Último /fechar: 2026-08-29 (continuação) — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-27 — noite tarde) — Senha no portal — perfil e login

### O que foi feito

**Frente única: conta e senha saem deste app e ficam no portal Finaud**

Michel pediu para esconder **Meu Perfil** (a senha passa a ser alterada no portal). Em seguida
padronizou o login com o Leiautes: olho **dentro** da caixa da senha, e tirou **Esqueceu a senha?**
— recuperação também é no portal. E-mail, senha, Entrar e Portal de apps continuam (quem abre o
link direto ainda entra).

**O que mudou na tela**

| Antes | Depois |
|---|---|
| Menu do nome → Meu Perfil → Alterar senha (não gravava de verdade) | Só aparência e Sair |
| Olho da senha num quadradinho ao lado da caixa | Olho no canto direito, dentro da caixa |
| Link Esqueceu a senha? + formulário de senha temporária neste app | Sumiu; quem esquecer usa o portal |

**Publicação:** GitHub + VPS (`gestao-suporte.finaudapps.com.br`). No primeiro pull o git do
servidor estava com dono misturado (root vs finaud-tec); corrigido o dono da pasta `.git` e o
código subiu. Michel confirmou no PC; login publicado conferido (sem Esqueceu, olho dentro).

### Estado atual

**Produção:** no ar com as mudanças de perfil e login.
**GitHub:** `main` em `a581c7a` (código desta sessão já commitado e enviado antes do `/fechar`).
**Pendência resolvida:** "Alterar senha pelo perfil ainda não grava" saiu da lista — não vamos
ligar isso neste app.

### Próximo passo

**Investigação ~130 "outro" threads: CONCLUÍDA.** 3 grupos encontrados + textos aprovados.
**Textos pendentes** sendo resolvidos em chat paralelo (28/08):
- Fix R + arquivo sem entrega (5x): propostas prontas, aprovação em andamento
- Saudação (~16x): maioria são "Segue" singular não detectado — verificar e corrigir antes do texto
- Excel de referência (2 abas: Regras + Alterações): sendo montado lá

🔴 **Quando o outro chat terminar — voltar aqui para:**
1. Fechar artefato visual de motivos (100%) → https://claude.ai/code/artifact/30448858-e3b1-4a40-a64d-4b989b0b7029
2. Atualizar PENDENCIAS com todos os motivos aprovados
3. Alterar `_determinar_status()` para ler regras de tabela no banco (não hardcoded)
   ⚠️ ANTES de implementar: analisar impacto (sistema em produção, não pode quebrar),
   testar localmente, definir plano de rollback, decidir se vale fazer em etapas
4. Criar tela no sistema: usuário mantém regras de classificação sem código
   — Aba Regras: ver/editar regras ativas · Aba Alterações: histórico automático

*(Conferências automáticas do `/fechar` = prioridade MÉDIA, não passam na frente.)*

Último /fechar: 2026-08-28 00:16 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-27 — noite) — Textos campo MOTIVO — grupo ❌

### O que foi feito

**Frente única: definir submotivos para a "caixa preta" e aprovar textos restantes do grupo ❌**

Metodologia continuada da manhã: analisar dados reais primeiro, nomear depois.

**Análise das 354 threads da "caixa preta"** (motivo atual: "Cliente escreveu — aguarda resposta da Finaud"):

| Grupo | Critério de detecção | Threads |
|---|---|---|
| Entrega | "segue", "em anexo", "encaminho"... | ~105 (29%) |
| Pergunta | "?" real (não saudação/URL) | ~69 (19%) |
| Misto | Entrega + Pergunta | ~3 (0%) |
| Outro | Nenhum padrão detectado | ~177 (50%) |

**Textos aprovados nesta sessão:**

| Texto aprovado | Status | Qtd |
|---|---|---|
| **Cliente fez pergunta — aguarda resposta da Finaud** | Aguardando Finaud | ~69x |
| **Cliente agradeceu — problema resolvido** (unifica "Fix H" 41x + "Cliente confirmou" 39x) | Concluída | ~80x |

**Grupo "outro" (~177):** texto "Cliente enviou mensagem" rejeitado por Michel (redundante — todo registro é uma mensagem). Decisão: chat novo para investigar por que o sistema não detectou padrão em ~130 dessas threads.

**Artefato publicado:** rastreador visual de todos os motivos em aprovação:
https://claude.ai/code/artifact/30448858-e3b1-4a40-a64d-4b989b0b7029

### Estado atual

**Produção:** sem alteração — nenhum código de classificação modificado nesta sessão.
**Commit desta sessão (`/fechar`):** 9 arquivos — corrigida a porta do servidor local (5001→8004), SSO portal (8002→8000), testes de ambos, CLAUDE.md, DEPLOY.md, PENDENCIAS.md, arquivo histórico.

### Próximo passo

🔴 **Novo chat: investigar ~130 threads sem padrão ("outro")** — por que o sistema não identificou? O que são? Só após a investigação: nomear o motivo final.
Depois: aprovar textos pendentes (saudação 15x, arquivo sem entrega 5x, Fix R) e implementar tudo em `_determinar_status()` (`scripts/banco_threads.py`).

Último /fechar: 2026-08-27 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-27 — fim da tarde) — Organização dos chats + conserto do `/fechar`

### O que foi feito

**Frente única: organizar as conversas do projeto — e consertar o que mantinha isso vivo**

Michel abriu o chat perguntando como organizar as conversas para não perder o que já foi falado
e feito. Virou três frentes, e uma quarta apareceu no caminho.

**1. Dois tipos de chat — regra nova no `CLAUDE.md` §2.5**
Michel apontou o furo da primeira proposta: nem todo chat é sessão de trabalho, e uma resposta
gera dúvidas novas. A regra ficou: **Michel não decide nada na abertura** — abre e pergunta;
quem detecta que virou trabalho é o Gestor, com três frases de gatilho. O `/iniciar` funciona
a qualquer momento do chat, não precisa ser a 1ª mensagem.

**2. Grupos na barra lateral — feito por Michel no app**
Quatro grupos, por assunto: ⚙️ CLAUDE CONFIGURAÇÕES · 📐 REGRAS DE NEGÓCIOS · 🔧 DESENVOLVIMENTO
· 🔁 Rotinas. Os chats soltos foram distribuídos; "Sem grupo" deve ficar permanentemente vazio.

**3. Índice de sessões — `SESSAO_ATUAL.md` 450 → 183 linhas**
Tabela "🗂️ Sessões anteriores" no topo com todas as sessões, 3 diários completos abaixo.

**4. O `/fechar` apontava para o projeto antigo**
9 referências ao `oraculo_360_finaud`: dois `cd` para pasta inexistente, memórias erradas e 6
documentos inexistentes. Dois blocos falhavam e eram pulados. Nada foi perdido — bordo e
memórias sempre foram gravados nas pastas certas. O que nunca rodou: as 2 conferências
automáticas (auditoria de documentação e links quebrados) — viraram pendência.

### Estado atual

**Produção:** sem alteração — nenhum código tocado.
**GitHub:** `main` alinhada ao origin (`4ed3290`).

### Próximo passo

🔴 **Definir os motivos do grupo ❌ (caixa preta + Fix H + Fix R).**
Depois: implementar os textos aprovados em `_determinar_status()` (`scripts/banco_threads.py`).

Último /fechar: 2026-08-27 15:50 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-27 — tarde) — Reorganização do CLAUDE.md

### O que foi feito

**Frente única: revisão e reorganização do arquivo de instruções (`CLAUDE.md`)**

Michel pediu sugestões de melhoria no `CLAUDE.md`. Levantadas 7, todas aplicadas. Nenhum código
de produção alterado — só documentação e instruções.

**O problema central:** o `CLAUDE.md` é carregado inteiro em **toda mensagem de todo chat**. Com
519 linhas, custava entre 6 e 8 mil tokens por resposta — contrariando a própria regra de "chat
curto = menor custo" que está dentro dele.

**O que mudou:**

| # | Melhoria | Resultado |
|---|---|---|
| 1 | Dividir o arquivo | `CLAUDE.md` 519 → 371 linhas · criado `documentações/REGRAS_TRABALHO.md` (190 linhas) |
| 2 | "Declarar plano" separado por consequência | Escreve ou gasta API → aguarda OK · Só lê → faz e mostra |
| 3 | Juntar as 4 regras de "verifique antes de afirmar" | Viraram uma seção única com 4 itens |
| 4 | Corrigir o erro do `/fast` | `/fast` não troca de modelo — liga o modo rápido do Opus |
| 5 | Cada coisa no arquivo certo | Tabela de status → spec §8.3 · regra do artifact → já era o Passo 0 do `/iniciar` |
| 6 | Adicionar "Como rodar o projeto" | Não existia · porta corrigida de 5000 para **5001** |
| 7 | Ordem de prioridade entre regras | Dados > OK do Michel > registro > tokens > velocidade |

**Decisão de processo tomada no caminho:** ao criar um ramo seguindo a regra "nunca commitar
direto na `main`", apareceu a contradição — o `DEPLOY.md` manda publicar da `main` e os últimos
5 commits foram direto nela. Michel decidiu: **trabalhamos direto na `main`**. Ramo separado só
para mudança grande que talvez seja descartada, com aviso antes. Regra reescrita no `CLAUDE.md`
§6 e registrada no `REGISTRO_CORRECOES.md`.

**Ganho real:** ~30% menos tokens por resposta (não os ~65% estimados no começo — entraram ~50
linhas novas que não existiam: índice, "Como rodar" e ordem de prioridade).

### Estado atual

**Produção:** sem alteração — nada foi publicado, nenhum código tocado.
**Suíte de testes:** não rodada — nenhum `.py` foi modificado nesta sessão.
**GitHub:** `main` alinhada ao origin (`6003021`).
**Arquivo novo:** `documentações/REGRAS_TRABALHO.md` — rodada paga, tipografia, recursos
externos, backup e resumo do deploy.

### Próximo passo

🔴 **Definir os motivos do grupo ❌ (caixa preta + Fix H + Fix R)** — segue sendo o item mais
quente, herdado da sessão da manhã. São os motivos mais frequentes e os que expõem nome interno
na tela do usuário.
Depois: implementar todos os textos aprovados em `_determinar_status()`
(`scripts/banco_threads.py`).

*(Cruzado com o `PENDENCIAS.md`: nenhum item urgente novo entrou hoje; a tela de gerenciamento
de motivos está marcada como prioridade ALTA e vem logo depois da definição do grupo ❌.)*

Último /fechar: 2026-08-27 13:05 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-27 — manhã) — Definição dos textos do campo MOTIVO

### O que foi feito

**Frente única: definir os textos descritivos do campo MOTIVO para cada situação de e-mail**

Sessão de revisão colaborativa: Michel e Claude analisaram os dados reais do banco para aprovar novos textos. Metodologia: dados primeiro, nome depois. Nenhum código alterado — só decisões de design aprovadas.

**Princípio aprovado (e vigente daqui em diante):**
> O MOTIVO deve responder "por que o status é esse?" — não apenas "quem escreveu".

**Vocabulário fixo aprovado:**
- O que o cliente/Finaud envia → **informações** (dados no corpo) ou **extratos** (arquivos)
- O que a Finaud faz ao receber → **processar**
- O que o cliente faz ao receber → **responder**, **enviar** ou **executar**

**Motivos aprovados nesta sessão:**

| Motivo atual (no banco) | Novo texto aprovado | Status |
|---|---|---|
| "Cliente enviou conteúdo — aguarda processamento da Finaud" (383x) | **Cliente enviou informações e extratos — aguarda processamento** | Aguardando Finaud |
| "Cliente encaminhou — aguarda processamento da Finaud" (64x) | **consolidado no item acima** | Aguardando Finaud |
| "Finaud escreveu — aguarda retorno do cliente" (49x) | **4 submotivos — ver abaixo** | Aguardando Cliente |
| "Finaud encerrou a conversa" (68x) | **Finaud concluiu a solicitação** | Concluída |

**4 submotivos aprovados para "Finaud escreveu — aguarda retorno do cliente":**
1. Finaud solicitou extrato ou planilha — aguarda envio (~15 casos)
2. Finaud deu orientação técnica — aguarda execução (~20 casos)
3. Finaud propôs reunião ou ligação — aguarda confirmação (~5 casos)
4. Finaud fez pergunta — aguarda resposta (~9 casos)

### Estado atual

**Produção:** sem alteração — nenhum código modificado nesta sessão.
**Decisões:** 4 motivos aprovados + 4 submotivos aprovados por Michel em 27/08.
**Planilhas:** `documentações/matriz_motivos_status.xlsx` e `documentações/varredura_motivos.xlsx` — criadas nesta sessão para apoiar a análise.

Último /fechar: 2026-08-27 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-26 — noite) — Esqueceu a senha + faxina FOG

### O que foi feito

**Frente 1: “Esqueceu a senha?” não fazia nada**

- O botão na tela de entrar estava desligado de propósito. Passou a abrir **Recuperar acesso** no mesmo cartão (padrão Finaud): e-mail → senha temporária no correio → essa senha vira a senha de entrar.
- Michel testou no site, recebeu o e-mail, entrou e **aprovou**.
- A tela **Alterar senha** (dentro do app, no menu do nome) ainda só mostra “Senha atualizada” e **não grava**. Quem entra depois de “Esqueceu a senha?” está usando a senha do e-mail — isso é o fluxo certo. Mudar senha pelo perfil continua pendente.

**Frente 2: pendências fechadas nesta conversa**

- Robô de coleta: Michel confirmou que já rodou sozinho. Item “confirmar amanhã” saiu da fila.
- Classificação por IA: Michel decidiu **não usar IA para classificar**. O item 🔴 SPEC §10 saiu do `PENDENCIAS.md`. Continua valendo só o classificador de regras.

**Frente 3: atalhos mortos do FogBugz**

- Apagadas as URLs `/fog/gerencial` e `/fog/operacional` (não estavam em nenhum menu; se alguém digitasse, a página quebrava). FogBugz que você usa não mudou. Publicado no ar.

### Estado atual

**Produção:** `https://gestao-suporte.finaudapps.com.br` — senha, Sair, SSO e faxina FOG no ar.
**Nada urgente** nesta fila.

### Próximo passo

Fila futura (nenhum 🔴):
- Python 3.9 no servidor (🟡 risco de segurança futuro)
- Lista de bloqueio pela tela
- Painel unificado configurável
- Alterar senha pelo perfil (hoje não grava)
- Mostrar nome do colaborador Finaud em vez de "suporte" nas threads (investigado 26/08 — padrão identificado, pendência registrada em PENDENCIAS.md)

**Investigação registrada (pós-fechar 23:40):** varrido o banco de produção para entender como o cabeçalho `smtp.mailfrom` se compara com o `Reply-To`. Resultado: o nome do colaborador (ex.: "Sarah Sá") já está gravado no campo `remetente` — o sistema só precisa exibir o nome em vez do endereço do grupo. Padrão para distinguir cliente de colaborador: clientes têm "via Suporte" no From, colaboradores não têm.

Último /fechar: 2026-08-26 23:59 — memórias revisadas ✅

---

---

## 📓 Diário da sessão (2026-08-26 — madrugada) — Badges nas abas + CI corrigido

### O que foi feito

**Frente 1: badges de notificação migrados do menu para as abas**

- Bolinhas que ficavam ao lado de "Não Classificadas" e "Bloqueadas por Regras" no menu lateral foram removidas — menu ficou mais limpo.
- Badges vermelhos adicionados diretamente nas abas horizontais (tabs). Regra: só aparecem se o número for maior que zero.
- Corrigida armadilha CSS: `display: inline-flex` no `.tab-badge` sobrescrevia o atributo `hidden` do browser — adicionada regra `.tab-badge[hidden] { display: none !important; }`.
- Abas receberam `white-space: nowrap` + `inline-flex` para o texto e a bolinha ficarem na mesma linha.
- Sidebar reduzida de 270px para 230px aproveitando o espaço liberado pelas bolinhas.
- Deploy confirmado em `https://gestao-suporte.finaudapps.com.br`.

**Frente 2: CI do GitHub corrigido (dois commits consecutivos)**

- **Falha 1:** `apscheduler` ausente no `requirements-dev.txt`. `servidor_telas.py` importa `APScheduler` a nível de módulo; o CI não encontrava o pacote. Corrigido adicionando `APScheduler==3.10.4` ao arquivo.
- **Falha 2:** `portal_sso.py` e `tests/test_sso_portal.py` criados na sessão anterior mas nunca commitados. O CI baixa só o que está no repositório — sem esses arquivos, a importação falhava na coleta de testes. Commitados os dois arquivos.
- CI passou com 394 testes.

### Estado atual

**Produção:** no ar em `https://gestao-suporte.finaudapps.com.br` · badges nas abas funcionando.
**CI:** passando (394 testes).
**GitHub:** main alinhado ao origin.

### Próximo passo

Nada urgente. Fila futura em `PENDENCIAS.md`:
- Python 3.9 no servidor (🟡 risco de segurança futuro)
- UI para gerenciar lista de bloqueio pela tela
- Painel unificado configurável

Último /fechar: 2026-08-26 23:32 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-26 — noite) — SSO + Sair encerra o portal

### O que foi feito

**Frente única:** o card do portal abria o Gestão, mas o **Sair** voltava ao login do portal e logo a home de apps reaparecia.

- Causa: `/sair` e `/logout` limpavam só a sessão deste app e redirecionavam para `https://finaudapps.com.br`. O cookie do grupo continuava; o portal perguntava à API e reabria a home.
- Correção: ao Sair, apagar também `auditoria_sessao` e `finaud_portal_sessao`. SSO pelo cookie do portal (`portal_sso.py`) para abrir o app sem login local.
- Testes: `tests/test_sso_portal.py` + `test_sair_e_logout_redirecionam_para_o_portal` (cookies no `Set-Cookie`).
- Deploy: backup `servidor_telas.py.bak-20260826-logout-portal` · arquivo no VPS · `systemctl restart gestao-suporte` · `GET /sair` 302 + cookies expirados.
- Michel **confirmou** no site: Sair permanece no login.

Rotas mortas `/fog/gerencial` e `/fog/operacional`: já excluídas no outro chat, a pedido do Michel. Não voltam à fila.

### Estado atual

**Produção:** no ar em `https://gestao-suporte.finaudapps.com.br`. SSO + Sair corretos (Michel 26/08).
**Pendência deste tema:** nenhuma.

### Próximo passo

Nada urgente deste chat. Fila futura permanece em `PENDENCIAS.md` (Python 3.9, lista de bloqueio pela tela, painel unificado).

Último /fechar: 2026-08-26 23:21 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-26 — madrugada) — Fix filtro §4: automáticos na fila de suporte

### O que foi feito

**Frente única: automáticos escaparam para a fila "Aguardando Finaud"**

Michel identificou 5 threads que deveriam ter sido descartadas automaticamente mas apareceram na fila de suporte — relatórios internos do RiskDriver, avisos do sistema Finaud e spam de "cesta solidariedade". Investigação + correção completa.

**Investigação:**
- `log_coletas` confirmou 0 descartes em 42 threads processadas na coleta das 19:29 — filtro §4 falhou silenciosamente
- `print()` usado no filtro era suprimido pelo Gunicorn — problema ficou invisível
- `contato@cestaincentivo.com.br` não estava na lista de bloqueio

**Correções aplicadas:**
- `validador_classificacao.py`: `contato@cestaincentivo.com.br` adicionado a `_ENDERECOS_EXATOS`
- `classificador_regras.py`: todos os `print()` em `classificar_banco()` substituídos por `_log.info/warning/error()` — visíveis no `journalctl`. `except ImportError` → `except Exception` com log de alerta explícito
- `classificador_regras.py`: nova função `reavaliar_automaticos(janela_horas=48)` — após cada coleta, verifica threads recentes em `principal` contra o filtro §4 e move para `descartes` as que escaparam
- `servidor_telas.py`: chama `reavaliar_automaticos()` logo após `classificar_banco()` em todo job de coleta agendado

**Banco de produção:** 5 threads movidas manualmente via SSH para `destino='descartes'` com motivo de correção datado

**Testes:** 3 novos — `test_filtro_cestaincentivo_bloqueado`, `test_reavaliar_automaticos_move_automatico_para_descartes`, `test_reavaliar_automaticos_nao_move_thread_normal`. Suíte completa: **393 passed**.

**Deploy:** commit `edfa6c0` · push · pull no servidor (stash automático do trabalho SSO em andamento, merge limpo) · `systemctl restart gestao-suporte` · `active` ✅ · agendador confirmado no journal.

**Documentação:** `REGISTRO_CORRECOES.md` atualizado (entrada 22:45). `PENDENCIAS.md`: novo item "Gerenciar lista de bloqueio pela tela".

---

### Estado atual

**Produção:** no ar em `https://gestao-suporte.finaudapps.com.br` · filtro §4 corrigido · reavaliar_automaticos() ativo.
**Suíte de testes:** 393 passed.
**GitHub:** main alinhado (`edfa6c0`).
**SSO portal:** no ar (commit no /fechar 23:21).

---

## 📓 Diário da sessão (2026-08-26 — noite) — UI + fix agendador

### O que foi feito

**Frente 1: padronização de cabeçalhos na tela de e-mails**

- Cabeçalho "Classificação e Status" movido para fora do card escuro — agora usa `page-header` igual às outras abas (título solto + descrição). Seta de colapso `▼` e função `toggleTblResumo()` removidos.
- Dois relógios de atualização na mesma tela corrigidos: pílula grande removida dos cabeçalhos; relógio pequeno (estilo `fog-cd`) adicionado dentro do `tabela-wrap` (visível no fullscreen). FOG Visão Consolidada e Evolução sem relógio (não atualizam automaticamente).
- Commits `6504d16` e `913e61c` · deploy confirmado.

**Frente 2: bug crítico — agendador nunca rodava em produção**

- Causa raiz: `_scheduler.start()` estava dentro de `if __name__ == '__main__':`, que o Gunicorn nunca executa. O robô NUNCA rodou automaticamente — toda coleta era manual (via tela de Admin).
- Correção: inicialização do agendador movida para nível de módulo. Log de confirmação adicionado.
- Verificado no journal do servidor às 19:23:27: "Agendador iniciado — coleta automática a cada 60 minuto(s)." ✅
- Commit `dcf7644` · deploy confirmado.

**Pytest:** sem alteração (mudanças visuais e infraestrutura de runtime).

---

### Estado atual

**Produção:** no ar em `https://gestao-suporte.finaudapps.com.br`.
**Sair:** volta para `https://finaudapps.com.br` — aprovado por Michel (18:41).
**Esqueceu a senha:** no ar; Michel testou temporária, entrou e aprovou (22:47).
**Agendador:** confirmado por Michel (26/08 noite) — coleta automática já rodou.
**GitHub:** `main` alinhado ao origin após o publish da senha (`8020e8c`).

---

### Próximo passo

*(rotas mortas do FOG removidas em 26/08/2026 — ver REGISTRO_CORRECOES.md)*

Último /fechar: 2026-08-26 18:56 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-09-01) — Fog: dias úteis, feriados e Sem atualização

### O que foi feito

**Frente única: a coluna Sem atualização do Fog passou a contar dia útil**

Michel viu que o número incluía sábado e domingo. Só desenvolvedor trabalha fora do útil; misturar relógio por pessoa bagunçaria a tela. Decisão: **uma conta só, para todo mundo, em dias úteis**.

**Decisões aprovadas**
- Função `contar_dias_uteis` — segunda a sexta, sem o dia inicial.
- Cores alinhadas à conta nova: verde &lt; 6 · âmbar 6–10 · vermelho ≥ 11 (equivalente ao peso de 8 e 15 corridos).
- Na tela o número leva **du**; a legenda continua com a palavra "dias".
- Feriados: só oficiais do Brasil (calendário de banco, inclusive Carnaval e Corpus Christi). Sem feriado de cidade e sem folga só da Finaud. Datas móveis saem da Páscoa — sem lista anual.
- O número mede **o caso parado no Fog** (qualquer mexida zera). Caso fechado: célula em branco (—); "duração do caso" saiu. Não criamos coluna de duração.

**Arquivos:** `scripts/servidor_telas.py`, `templates/gestao_email.html`, `tests/test_servidor_telas.py`, `documentações/REGISTRO_CORRECOES.md`

### Estado atual

**Produção:** no ar em `gestao-suporte.finaudapps.com.br`.
**pytest:** `tests/test_servidor_telas.py` — 24 passed (inclui feriado, cortes 6/11, fechado sem número).
**Assunto deste chat:** encerrado.

Último /fechar: 2026-09-01 13:36 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-26) — Sair volta ao portal

### O que foi feito

**Frente única:** o botão **Sair** caía no login deste app. Padrão Finaud: voltar sempre para `https://finaudapps.com.br`.

- Rotas `/sair` e `/logout`: depois de limpar a sessão, redirecionam para o portal (ou `PORTAL_URL`)
- Teste `tests/test_servidor_telas.py` trava esse destino
- Commit `869bedf` · push · deploy · Michel **aprovou** no site (18:41)
- Pytest: 375 passaram

---

## 📓 Diário da sessão (2026-08-24 — noite) — Melhorias de UI + Coletor

### O que foi feito hoje (sessão da noite — UI)

**Frente única: melhorias visuais e funcionais na tela web (Flask/localhost:5001)**

---

#### 1. FOGBUGZ — abas horizontais e sort

- Submenus do FOGBUGZ (Casos / Gerencial) convertidos para abas horizontais, igual ao padrão do E-MAILS
- `fogSort()` atualizado com: toggle de direção, indicadores de coluna (`▲`/`▼`), texto descritivo do sort ativo
- Botões redundantes "Mais antigo" / "Mais casos" removidos da tela Gerencial (duplicavam o sort)
- Badge CSS fix: `.fog-urg-badge[hidden] { display: none !important; }` — bug onde badge ficava visível mesmo com `hidden`

#### 2. Coletor — erro + auto-refresh + UTF-8

- **Auto-refresh do log:** `setInterval` de 15s na página do Coletor; limpo ao navegar para outra seção
- **Captura de erro:** `_rodar()` tinha `try/finally` sem `except` — exceções eram engolidas silenciosamente; corrigido com `except Exception as e` que grava em `_ultimo_erro_coleta`
- **UTF-8 no Windows:** `coletor_gmail.py` tem emojis nos `print()` — quebravam com `charmap` (Windows-1252). Corrigido reconfigurando `sys.stdout`/`sys.stderr` para UTF-8 na inicialização do servidor
- Endpoint `/api/admin/status-coleta` atualizado para retornar `ultimo_erro`

#### 3. Tela de detalhe da execução (nova)

- Botão `⋯` em cada linha do histórico de coletas → abre tela completa `#pag-admin-detalhe`
- **Linhas de erro:** mostra explicação em português + como resolver (função `_traduzirErro()`)
- **Linhas concluídas:** tabela com threads processadas (assunto, categoria, status, motivo)
- Filtros client-side por Categoria e Status (atributos `data-cat` / `data-st`)
- "Bloqueada por filtro" como opção no filtro de Categoria
- Layout: título alinhado à esquerda, botão "← Voltar" à direita, sem breadcrumb "Coletor"
- Cores usando CSS custom properties (`--neg-bg`, `--neg`, `--accent-bg`, `--accent`) — funciona em dark/light mode

#### 4. Fix no banco — 5 threads FogBugz com destino=NULL

- Coleta com erro às 22:21 atualizou `ultima_sync` de 5 threads FogBugz antes de quebrar, deixando `destino=NULL`
- Corrigido: `UPDATE threads SET destino='descartes' WHERE assunto LIKE 'FogBugz%' AND destino IS NULL`
- Backup criado em `data/backups/20260824_2257_fogbugz_destino_nulo/`
- "Não Classificados" voltou a 0; "Bloqueados por Filtro" subiu de 258 → 263

---

### Estado atual

**GitHub:** 10 commits enviados (push confirmado por Michel) — repositório sincronizado.
**Git:** limpo (sem arquivos pendentes).
**Banco:** corrigido (5 FogBugz threads restauradas para `destino='descartes'`).
**Servidor:** Michel precisa reiniciar o servidor na porta 5001 para a correção UTF-8 ter efeito.

---

### Próximo passo

**🟡 Construir Fase 1 — código de produção**

- `coletor_gmail.py` — lê e-mails da caixa de coleta via Gmail API
- Pipeline de processamento — classifica e grava no banco
- 3 telas Flask (§14 da spec): painel principal + revisão + histórico

Detalhes e contexto → `documentações/PENDENCIAS.md` (seção "⏭ ETAPA ATUAL")
Spec completa → `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md`

Último /fechar: 2026-08-24 23:59 — memórias revisadas ✅

---

## 📓 Diário da sessão (2026-08-24) — Pente fino completo das AF

### O que foi feito hoje

**Frente única: pente fino completo de todas as threads Aguardando Finaud**

Varredura categoria por categoria. Para cada thread suspeita: conteúdo lido, apresentado a Michel, corrigido no banco com status e motivo corretos.

---

#### Pente fino das AF — resumo completo (2 sessões em 24/08/2026)

| Categoria | Threads AF | Corretas | Fixes manuais |
|---|---|---|---|
| FORCAPITAL | 2 | 2 ✅ | 0 |
| INTERNO | 2 | 0 | 2 → Concluída |
| S5 | 3 | 2 ✅ | 1 → Concluída |
| DLI_2062 | 0 | — | 0 |
| DDR_2011 | 472 | 469 ✅ | 3 (1 AC + 2 Concluída) |
| DRM_2060 | 20 | 20 ✅ | 0 |
| DRL_2160 | 21 | 21 ✅ | 0 |
| SUPORTE (parcial sessão 1) | 37 | 32 ✅ | 3 → Concluída |
| SUPORTE (parcial sessão 2) | — | — | 2 → Concluída |

**Total: 8 fixes manuais no banco. Taxa de acerto: ~99% das threads AF estavam corretas.**

---

#### Regras de negócio novas aprovadas por Michel (24/08/2026)

Adicionadas ao CLAUDE.md (tabela de regras de status):

- **Empresa em liquidação, cliente aguardando liquidante → AC** (pendência está no cliente)
- **Agradecimento do cliente pós-processamento da Finaud → Concluída**
- **Cliente diz que vai ligar + agradece → Concluída** (resolução encaminhada para canal síncrono)

---

#### Sessão anterior (mesmo dia) — Pente fino das Concluídas + Fix U + Fix V

| O que | Resultado |
|---|---|
| Pente fino das 339 Concluídas | 12 corrigidas (11 → AF, 1 → AC) |
| Fix U — "Favor + verbo" bloqueia Fix H | Implementado, 374 testes ✅ |
| Fix V — "e retorno" → AC | Implementado, 374 testes ✅ |

---

### Estado atual

**Suíte de testes:** 374/374 (`tests/test_banco_threads.py`) — inalterada nesta sessão.
**Banco:** pente fino completo — Concluídas (12 correções) + AF (8 correções) — total 20 correções manuais.
**GitHub:** pendente de push (commit feito ao fechar).
**PENDENCIAS.md:** item "Pente fino das AF" removido — concluído.

---

### Próximo passo

**🟡 Construir Fase 1 — código de produção**

- `coletor_gmail.py` — lê e-mails da caixa de coleta via Gmail API
- Pipeline de processamento — classifica e grava no banco
- 3 telas Flask (§14 da spec): painel principal + revisão + histórico

Detalhes e contexto → `documentações/PENDENCIAS.md` (seção "⏭ ETAPA ATUAL")
Spec completa → `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md`

Último /fechar: 2026-08-24 — memórias revisadas ✅

---
