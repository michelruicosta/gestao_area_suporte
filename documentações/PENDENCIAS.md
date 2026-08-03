# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-08-03
**Organização:** por etapa que bloqueia — reorganizado em 03/08/2026 para seguir as fases sem brechas.
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui.

---

## ⏭ ETAPA ATUAL — Completar a spec antes da Fase 1

> Resolver tudo abaixo antes de escrever a primeira linha de código de produção.

---

### 🔴 §7 — Adicionar "Como o sistema processa" em cada campo (identificado 31/07/2026)

**O que falta:**
O §7 (Mapeamento de campos do e-mail) documenta o **que é** cada campo, mas não o **como** o sistema processa. Falta um bloco "passo a passo" para cada um dos 8 campos — sequência exata de decisões que o sistema executa ao ler aquele campo.

**Por que é importante:**
- Quando houver dúvida sobre o que o sistema fez em um caso real, o passo a passo responde
- Quando um novo recurso for adicionado, o desenvolvedor sabe exatamente onde encaixar
- Sem isso, decisões de implementação ficam a cargo do desenvolvedor, sem registro na spec

**Inclui especificamente:**
- Campo 1: passo a passo de filtragem — o sistema verifica endereço contra lista exata → verifica contra padrões (`noreply`, `newsletter`, etc.) → verifica assunto → se qualquer match: descarta antes de classificar
- Campos 2 a 8: mesma lógica — descrever a sequência de decisões que o sistema toma ao processar cada campo

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §7, em cada campo.

---

### 🟡 ENCODING — Corrigir codificação quebrada nos e-mails da TRUSTEE DTVM (identificado 30/07/2026)

Durante a validação do Campo 6, os e-mails da TRUSTEE DTVM apareceram com caracteres quebrados:
`movimenta??o`, `?cone`, `Descri??o`, `confian?a`. O texto original seria `movimentação`, `ícone`, `Descrição`, `confiança`.

**Causa provável:** e-mails enviados em codificação Windows-1252 processados como UTF-8.

**Impacto:** a IA classificadora recebe texto com `??` no lugar de palavras reais — pode prejudicar a classificação. Ocorre em todos os e-mails da TRUSTEE DTVM presentes no JSON01.

**O que fazer:**
1. Identificar quantos e-mails no JSON01 têm esse problema (buscar por U+FFFD no campo `corpo_texto`)
2. Verificar se o problema é só TRUSTEE ou há outros remetentes afetados
3. Implementar detecção e reconversão de encoding no coletor Gmail

**Arquivo de destino:** módulo de limpeza do corpo — Passo 3 da Fase 1.

---

### 🟡 CLASSIFICADOR — Palavra de fechamento "Abraço" (singular) não está no detector de assinatura (identificado 30/07/2026)

O padrão atual reconhece `abraços` (plural) mas não `abraço` (singular). São a mesma coisa na prática — e-mails que fecham com "Abraço," não terão a assinatura removida. A IA vai receber nome, cargo e telefone junto com o texto.

**O que fazer:** adicionar `abraço[,!.\s]` (singular) ao padrão `PAD_ASSINATURA`.

**Variações a incluir:** `abraço!`, `um abraço,`, `grande abraço,` (a abreviação `abs,` já está no padrão ✅).

**Arquivo a alterar:** módulo de limpeza do corpo quando for criado na Fase 1.

---

## ANTES DA FASE 3 — Ligar a IA

> Resolver tudo abaixo antes de conectar a IA classificadora.

---

### 🔴 OCR — RETORNO_BACEN depende 100% das imagens para classificação e aprendizado (identificado 30/07/2026)

Na análise do RETORNO_BACEN (1.298 e-mails), os elementos `[image:]` (36,3%) e `[cid:]` (41,0%) são os mais altos de todas as 12 categorias. Nesta categoria, o cliente envia **prints de tela** com as mensagens de erro do BACEN — o texto do e-mail diz apenas:

> *"Prezados, recebemos a seguinte crítica referente ao DLO de dezembro: [image: image.png]"*

O que está dentro da imagem é o erro real: código de crítica, conta contábil afetada, valor divergente. Sem ler a imagem, a IA recebe apenas a casca do e-mail.

**Impacto sem OCR:** a IA classifica como RETORNO_BACEN genérico sem entender o problema específico; o aprendizado da IA Assistente fica cego para o conteúdo mais importante desta categoria.

**O que decidir antes da Fase 3:**
1. Garantir que OCR está implementado antes de qualquer classificação de RETORNO_BACEN
2. Definir o que fazer se o OCR falhar: fila de revisão humana (já previsto pela regra L6)
3. Avaliar se é necessário OCR especializado para prints de sistema BACEN

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — Campo 6 (regra L6).

---

### 🟡 CLASSIFICADOR — Convites de calendário chegam na caixa como e-mails (identificado 30/07/2026)

Quando alguém agenda uma reunião e inclui `suporte@finaud.com.br`, o Google envia um convite que chega como e-mail normal. O classificador não sabe o que fazer com ele — não é CADOC, não é suporte de cliente.

**O que precisa ser decidido:**
1. **Filtrar antes do classificador?** — detectar pelo padrão do assunto (`Convite:` ou `Invitation:` + horário + link Meet/Teams/Zoom) e descartar
2. **Criar categoria `NOTIFICACAO_SISTEMA`?** — para convites, respostas automáticas de ausência, confirmações automáticas
3. **Marcar para revisão humana?** — sistema sinaliza "não reconheci este tipo" e gestor decide

**Outros tipos similares:** respostas automáticas de ausência, confirmações automáticas de recebimento, notificações de sistemas internos.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — seção do classificador.

---

### 🟡 IA ASSISTENTE — Como preservar o histórico completo para aprendizado (identificado 30/07/2026)

O Passo 3 da limpeza remove o histórico citado (`>` e `---`) antes de passar o texto para a IA classificadora — correto para classificação. Mas a IA Assistente de Aprendizado precisa do histórico completo da thread para entender como cada caso foi resolvido.

**O problema:** se removermos o histórico para classificação, perdemos esse conteúdo para o aprendizado.

**Agravante:** as primeiras threads coletadas já chegaram com histórico de conversas anteriores a julho/2026 disponível apenas como conteúdo citado (`>`). Se esse `>` for removido, esse histórico pré-coleta se perde para sempre.

**O que precisa ser decidido:**
1. Como separar: texto limpo para classificação vs. thread completa para aprendizado?
2. Guardar o `corpo_texto` original (com todo o histórico) em campo separado antes de aplicar a limpeza?
3. Para a IA Assistente: reconstruir a thread completa via Gmail API?
4. O que fazer com threads com histórico anterior a julho/2026?

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — nova seção sobre IA Assistente.

---

## ANTES DAS TELAS — Especificar §13 (Telas do sistema)

> Resolver tudo abaixo antes de definir o design das telas.

---

### 🟡 PAINEL DO GESTOR — Design para threads com múltiplos CADOCs (identificado 30/07/2026)

Uma thread pode gerar múltiplos registros (um DDR + um DRM, por exemplo). O painel precisa mostrar isso de forma clara.

**Perguntas abertas:**
1. O painel agrupa por **thread** (conversa) ou por **CADOC** (obrigação regulatória)?
2. Como mostrar "thread X tem DDR pendente e DRM concluído"?
3. Quais status existem para cada CADOC? (Aguardando → Em análise → Concluído → Vencido?)
4. O que o gestor mais precisa ver de relance?
5. Filtros: por cliente? por tipo de CADOC? por data de vencimento?

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §13 Telas.

---

### 🟡 PAINEL — Ideias para o painel lateral de categoria (identificado 31/07/2026)

Ideias levantadas por Michel para evoluir o painel:

1. **Fora do prazo:** antes da lista de threads em cada seção, mostrar quantas estão fora do prazo
   > AGUARDANDO FINAUD (54) · ⚠ 12 fora do prazo

2. **Linguagem do status no cartão:** em vez de "R2", mostrar "Aguardando a Finaud processar o material do cliente"

3. **Concluídas com regra:** na seção Concluídas, mostrar qual regra foi usada (ex.: "Encerrado pela regra R1")

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §13 Telas.

---

## APÓS A FASE 1 ESTAR RODANDO

> Fazer depois que o protótipo (coletor + classificador sem IA) estiver funcionando.

---

### 🟡 §8 — Threads "irmãs": quando a confirmação chega em thread separada (identificado 03/08/2026)

Situação onde o cliente, em vez de responder na thread original, abre um e-mail novo para confirmar (ex.: "DDR transmitido no BACEN" chega em thread B, mas a thread A ainda aparece como Aguardando Cliente).

**Decisão de Michel (03/08/2026):** deixar para a Fase 2. Na Fase 1, threads irmãs não ocorrem no dia a dia — a regra do último e-mail cobre todos os casos normais.

**Opção favorita para a Fase 2:** Camada 2 rastreia a **entrega**, não a thread — gestor encerra a entrega independente de qual thread trouxe a confirmação.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §8 e/ou §9.

---

### 🟡 NOVA ARQUITETURA — Simular modelo de duas camadas com dados reais (identificado 27/07/2026)

Confirmar com o histórico real que a IA extrai múltiplos CADOCs de um mesmo e-mail (ex.: "DDR + DRM + DLI de março"). Verificar quantos e-mails no histórico têm múltiplos CADOCs.

**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §9.

---

### 🟡 SPEC — Revisar formato dos Campos 1 a 5 (identificado 30/07/2026)

Os Campos 1 a 5 foram escritos antes do padrão do Campo 6 (que é mais rico e estruturado). Ajuste estético — não bloqueia nenhuma fase.

**Arquivo:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §7 (Campos 1 a 5).

---

### 🟡 NOVO PROJETO — Criar MAPA_DO_PROJETO.md para a nova arquitetura (identificado 28/07/2026)

O MAPA antigo foi arquivado. Quando a estrutura do novo código estiver definida, criar novo MAPA descrevendo o que o sistema faz, as duas partes principais, onde mora cada coisa e as regras que não se quebram.

**Quando fazer:** após a estrutura do novo código estar definida (Fase 1).

---

### 🟡 NOVO PROJETO — Escrever README.md (identificado 28/07/2026)

O README antigo foi arquivado. Escrever o novo só quando algo estiver funcionando — um README descreve um sistema que existe.

**Quando fazer:** após a Fase 1 estar funcional.

---
