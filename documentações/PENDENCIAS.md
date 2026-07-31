# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-07-31
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui (nunca o
contrário, para não perder histórico). Ver regra completa no `CLAUDE.md`.

---

## ✅ Especificação §10 completa (31/07/2026)

**Campo 6 ✅ concluído (30/07/2026)** — análise de 6.989 e-mails em 12 categorias, regras L1–L8 escritas em `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §10`.
**Campo 7 ✅ concluído (31/07/2026)** — 78.087 arquivos analisados, 6 cenários não previstos identificados, regras escritas em `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §10`.
**Campo 8 ✅ concluído (31/07/2026)** — Thread ID, campos de data, regra de inferência de ano validada, 3 tipos de threads de canal definidos.

---

## 🔴 §7 — Adicionar "Como o sistema processa" em cada campo (identificado 31/07/2026)

**O que falta:**
O §7 (Mapeamento de campos do e-mail) documenta o **que é** cada campo, mas não o **como** o sistema processa. Falta um bloco "passo a passo" para cada um dos 8 campos — sequência exata de decisões que o sistema executa ao ler aquele campo.

**Por que é importante:**
- Quando houver dúvida sobre o que o sistema fez em um caso real, o passo a passo responde
- Quando um novo recurso for adicionado, o desenvolvedor sabe exatamente onde encaixar
- Sem isso, decisões de implementação ficam à cargo do desenvolvedor, sem registro na spec

**Inclui especificamente:**
- Campo 1: passo a passo de filtragem — o sistema verifica endereço contra lista exata → verifica contra padrões (`noreply`, `newsletter`, etc.) → verifica assunto → se qualquer match: descarta antes de classificar
- Campos 2 a 8: mesma lógica — descrever a sequência de decisões que o sistema toma ao processar cada campo

**Quando resolver:** obrigatório antes do desenvolvimento das telas (§10 da spec).
**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §7, em cada campo.

---

## 🔴 OCR — RETORNO_BACEN depende 100% das imagens para classificação e aprendizado (identificado 30/07/2026)

**O que foi observado:**
Na análise do RETORNO_BACEN (1.298 e-mails), os elementos `[image:]` (36,3%) e `[cid:]` (41,0%)
são os mais altos de todas as 12 categorias. Isso não é coincidência: nesta categoria, o cliente
envia **prints de tela** com as mensagens de erro do BACEN para mostrar o problema que precisa
ser resolvido.

**Por que isso é crítico:**
Ao contrário das outras categorias — onde as imagens são logos e decorações descartáveis — no
RETORNO_BACEN as imagens **são o conteúdo da mensagem**. O texto do e-mail diz apenas:

> *"Prezados, recebemos a seguinte crítica referente ao DLO de dezembro: [image: image.png]"*

O que está dentro da imagem é o erro real: código de crítica, conta contábil afetada, valor
divergente, mensagem do sistema BACEN. Sem ler a imagem, a IA recebe apenas a casca do e-mail
— não sabe qual é o erro, não consegue classificar corretamente e não aprende nada útil.

**Impacto no classificador (Fase 3):**
- Sem OCR: a IA classifica como RETORNO_BACEN genérico, sem entender o problema específico
- Com OCR: a IA lê o código de erro, a conta, o valor — e pode entender e classificar com precisão

**Impacto no aprendizado da IA (IA Assistente):**
Esta é a categoria onde o OCR é mais crítico para o aprendizado. Cada caso resolvido tem:
1. O erro do BACEN (dentro de uma imagem)
2. A análise da Finaud (às vezes também em imagem)
3. A solução enviada ao cliente

Sem OCR, o aprendizado da IA sobre RETORNO_BACEN fica cego para o conteúdo mais importante.

**O que decidir antes da Fase 3:**
1. Garantir que OCR está implementado antes de qualquer classificação de RETORNO_BACEN
2. Definir o que fazer se o OCR falhar: fila de revisão humana (como já previsto pela regra L6)
3. Avaliar se é necessário OCR especializado para prints de sistema BACEN (tipografia e layout
   diferentes de documentos normais — pode precisar de ajuste ou modelo específico)

**Quando discutir:** obrigatório antes da Fase 3 (ligar IA). O OCR para esta categoria não é
opcional — é pré-requisito para o sistema funcionar corretamente.
**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — seção do Campo 6
(regra L6) e seção da IA Assistente.

---

## 🟡 CLASSIFICADOR — Convites de calendário chegam na caixa como se fossem e-mails (encontrado 30/07/2026)

**Onde foi encontrado:**
Durante a análise do DRM_2060, um dos 163 e-mails da categoria era, na verdade, um convite de
reunião do Google Calendar. O assunto era:

> `Convite: [SANTS] SMM - 2060 - LIM 2061 - LIM 2062 | quinta-feira 9 abr. 2026 ⋅ 4pm – 5pm`

O corpo continha apenas: data/hora da reunião, link do Google Meet e lista de participantes.
**Não era um e-mail de cliente — era uma notificação automática do Google.**

**Por que isso acontece:**
Quando alguém agenda uma reunião pelo Google Calendar e inclui o endereço `suporte@finaud.com.br`
(ou o grupo do Google Groups ligado ao suporte) como participante ou destinatário, o Google envia
automaticamente um convite para esse endereço. O Gmail recebe e armazena como e-mail normal —
sem distinguir se é mensagem humana ou notificação de sistema.

**O problema para o classificador:**
As regras atuais (R1–R5) foram desenhadas para e-mails de clientes com conteúdo regulatório
(DDR, DRM, DLO, etc.) ou de suporte. Um convite de calendário não se encaixa em nenhuma delas:

- Não é uma entrega de CADOC (não tem arquivo, não tem dados regulatórios)
- Não é uma pergunta de suporte do cliente
- Não é um encaminhamento interno com arquivo
- Não tem assinatura, não tem texto de mensagem — é estrutura de convite

Se o classificador receber esse texto, vai tentar encaixar em alguma categoria e provavelmente
vai errar ou ficar confuso.

**O que precisa ser decidido:**
1. **Filtrar antes do classificador?** — detectar convites de calendário pelo padrão do assunto
   (`Convite:` ou `Invitation:` no início + presença de horário + link Google Meet/Teams/Zoom)
   e descartar antes de chegar na IA.
2. **Criar uma categoria para isso?** — ex.: `NOTIFICACAO_SISTEMA` para convites, confirmações
   automáticas, respostas automáticas ("Estou de férias"), notificações de entrega, etc.
3. **Marcar para revisão humana?** — o sistema sinaliza "não reconheci este tipo de mensagem"
   e o gestor decide manualmente o que fazer com ele.

**Outros tipos similares que podem aparecer:**
Além de convites de calendário, outras notificações automáticas podem chegar:
- Respostas automáticas de ausência ("Estou em férias, retorno em...")
- Confirmações automáticas de recebimento de arquivo
- Notificações de sistemas internos da Finaud
- E-mails de marketing ou listas de email que entraram no grupo por engano

**Quando discutir:** antes de construir o classificador IA (Fase 3 da nova arquitetura).
Saber o que fazer com esses casos é pré-requisito para o classificador funcionar corretamente.
**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — seção do classificador,
em "Casos que o classificador não reconhece".

---

## 🟡 CLASSIFICADOR — Palavra de fechamento "Abraço" (singular) não está no detector de assinatura (encontrado 30/07/2026)

**Onde foi encontrado:**
Durante a análise do DLI_2062, um dos e-mails não detectados como "tem assinatura" tinha o
seguinte fechamento:

> `ABRAÇO,`

**O problema:**
O padrão atual de detecção de assinatura reconhece `abraços` (plural, com "s"), mas não reconhece
`abraço` (singular, sem "s"). São a mesma coisa na prática — é o jeito informal de encerrar um
e-mail em português, como "Att," ou "Atenciosamente" — mas o detector só conhece uma forma.

**Impacto:**
E-mails que fecham com "Abraço," ou "Abraço!" ou "Abraço." não terão a assinatura removida.
A IA vai receber o nome, cargo e telefone do remetente junto com o texto da mensagem.
Isso não impede a classificação, mas é conteúdo desnecessário que a IA vai ter que ignorar.

**O que fazer:**
Adicionar `abraço[,!.\s]` (singular) ao padrão `PAD_ASSINATURA` no script
`scripts/consultas/analisar_corpo_emails.py` — e depois também no código de limpeza real
quando for construído (Fase 1 da nova arquitetura).

**Variações que podem existir e ainda não foram vistas:**
- `abraço!` — com exclamação
- `um abraço,` — com artigo antes
- `grande abraço,` — forma mais formal
- `abs,` — abreviação (já está no padrão como `abs[,.\s]`) ✅

**Quando corrigir:** antes de construir o módulo de limpeza do corpo (Passo 3) na Fase 1.
**Arquivo a alterar:** `scripts/consultas/analisar_corpo_emails.py` → `PAD_ASSINATURA`; e depois
o módulo real de limpeza quando for criado.

---

## 🟡 IA ASSISTENTE — Como preservar o histórico completo para aprendizado (registrado 30/07/2026)

**Contexto da conversa (30/07/2026):**
Enquanto validávamos o Campo 6 (Passo 3 — limpeza do corpo do e-mail), Michel levantou uma questão
arquitetural importante: o Passo 3 **remove** todo o histórico citado (`>`) e encaminhado (`---`)
antes de passar o texto para a IA classificadora. Isso é correto para **classificação** — a IA
precisa só do texto novo de cada e-mail, não do histórico repetido.

Mas há um segundo uso futuro do sistema: a **IA Assistente de Aprendizado** (registrada em memória
como `projeto-ia-assistente-aprendizado.md`) — uma IA que aprende com os e-mails resolvidos para
ajudar o gestor e novos colaboradores a entender como cada tipo de caso foi resolvido.

**O problema:**
Para aprendizado, o histórico completo da thread IMPORTA. A IA assistente precisa ver:
- O e-mail original (como o caso chegou)
- Todas as respostas (como foi tratado)
- A resolução final (como foi encerrado)

Se removermos o histórico para classificação, perdemos esse conteúdo para o aprendizado.

**Agravante — threads com histórico anterior ao início da coleta:**
A conta oraculo@finaud.com.br foi criada em julho de 2026. As primeiras threads coletadas já
chegaram com histórico de conversas anteriores (de junho, maio, etc.) apenas disponíveis como
conteúdo citado (`>`) no primeiro e-mail coletado. Se esse `>` for removido para classificação,
esse histórico pré-coleta se perde para sempre.

**O que precisa ser decidido:**
1. Como separar as duas necessidades: texto limpo para classificação vs. thread completa para aprendizado?
2. Guardar o `corpo_texto` original (com todo o histórico) em campo separado antes de aplicar o Passo 3?
3. Para a IA assistente: reconstruir a thread completa via Gmail API (que tem acesso a todo o histórico da thread)?
4. O que fazer com threads que têm histórico anterior a julho/2026 — descartamos esse passado ou tentamos recuperar?

**Quando discutir:** após concluir o Campo 6 e antes de construir o módulo da IA Assistente.
**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — nova seção sobre IA Assistente.

---

## 🟡 PAINEL DO GESTOR — Design para threads com múltiplos CADOCs (registrado 30/07/2026)

**Contexto da conversa (30/07/2026):**
Michel levantou a questão do painel de acompanhamento para o gestor. O problema tem duas camadas:

**Camada 1 — o problema do sistema antigo (já decidido):**
O sistema antigo carimbava **toda a thread** com um único CADOC — se a thread falava de DDR e DRM
ao mesmo tempo, ela ficava registrada só como DDR (o primeiro encontrado). Isso era um problema
porque o gestor não sabia que aquela thread também tinha um DDR pendente, por exemplo.

Já foi decidido (27/07/2026, ver pendência "simular modelo de duas camadas") que na nova
arquitetura cada ocorrência de CADOC numa thread é rastreada **separadamente**, com status próprio.
Uma thread pode gerar múltiplos registros: um para DDR, um para DRM, etc.

**Camada 2 — o problema aberto (não decidido): como mostrar isso no painel?**
Se uma thread agora pode gerar múltiplos registros, o painel do gestor precisa ser redesenhado.
Michel quer algo **amigável, rápido e fácil** para acompanhar o que está pendente e concluído.

As perguntas em aberto:
1. O painel agrupa por **thread** (conversa) ou por **CADOC** (obrigação regulatória)?
   - Por thread: o gestor vê conversas, mas pode ter vários CADOCs misturados numa linha
   - Por CADOC: o gestor vê cada obrigação separada, mas a thread pode aparecer várias vezes
2. Como mostrar claramente "thread X tem DDR pendente e DRM concluído"?
3. Quais **status** existem para cada CADOC? (ex.: Aguardando → Em análise → Concluído → Vencido?)
4. O que o gestor mais precisa ver de relance? (o que está atrasado? o que chegou hoje? o que está quase vencendo?)
5. Filtros: por cliente? por tipo de CADOC? por data de vencimento?

**O que Michel quer:** visualização rápida, clara, sem precisar abrir cada e-mail para saber o status.

**Quando discutir:** após definir o modelo de dados da nova arquitetura (campos, status, regras).
Pode ser durante ou após a simulação do modelo de duas camadas (ver pendência acima).
**Arquivo de destino:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — seção do Painel do Gestor.

---

## 🟡 ENCODING — Corrigir codificação quebrada nos e-mails da TRUSTEE DTVM (registrado 30/07/2026)

Durante a validação do Campo 6 (artifact), os exemplos dos e-mails da TRUSTEE DTVM apareceram com
caracteres quebrados: `movimenta??o`, `?cone`, `Descri??o`, `confian?a`. O texto original deveria
ser `movimentação`, `ícone`, `Descrição`, `confiança`.

**Causa provável:** os e-mails da TRUSTEE foram enviados originalmente em codificação Windows-1252
(padrão antigo de e-mail) e, ao serem processados pelo pipeline como UTF-8, os caracteres especiais
(ç, ã, ê, ô, etc.) viraram caracteres de substituição (U+FFFD → exibido como `?`).

**Impacto:** a IA classificadora vai receber texto com `??` no lugar de palavras reais — pode
prejudicar a leitura e a classificação. Ocorre em todos os e-mails da TRUSTEE DTVM presentes no
JSON01.

**Quando corrigir:** antes de construir o classificador IA. Pode ser na fase de pré-processamento
(etapa de limpeza do corpo — Passo 3), detectando encoding e convertendo corretamente.

**O que fazer:**
1. Identificar quantos e-mails no JSON01 têm esse problema (buscar por U+FFFD no campo `corpo_texto`)
2. Verificar se o problema é só TRUSTEE ou há outros remetentes afetados
3. Implementar detecção e reconversão de encoding no coletor Gmail

---

## 🟡 SPEC — Revisar formato dos Campos 1 a 5 (registrado 30/07/2026)

O Campo 6 foi escrito com um formato mais rico e estruturado (Para que serve / O que o Gmail entrega / Passos / O que utilizaremos / Regras de negócio). Os Campos 1 a 5 foram escritos antes deste padrão e têm formato diferente.

**Quando fazer:** após a Fase 2 estar concluída (análise das 12 categorias) e os Campos 6, 7 e 8 estarem completos — ou seja, quando a spec estiver completa em conteúdo.
**O que fazer:** revisar Campos 1 a 5 e adaptar para o mesmo formato do Campo 6.
**Arquivo:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10 (Campos 1 a 5)

---

## 🟡 NOVA ARQUITETURA — Pós-catálogo: simular modelo de duas camadas (registrado 27/07/2026)

**Para fazer após concluir o Catálogo de Categorias (Seção 15):**

1. **Simular o modelo de duas camadas** com dados reais do `oraculo_360`:
   - Pegar e-mails que mencionam múltiplos CADOCs (ex.: "Segue DDR, DRM e DLI - MIRAE março/2026")
   - Confirmar que a IA consegue extrair todos os CADOCs presentes, não só o primeiro
   - Verificar: quantos e-mails no histórico têm múltiplos CADOCs?

2. **Revisar a spec** (`documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md`) para alinhar Seção 2 (Funcionalidades) e Seção 9 (Plano de implantação) com o novo modelo de rastreamento (Seção 16).

**Onde foi decidido:** chat de 27/07/2026 — discussão sobre e-mails com múltiplos CADOCs no mesmo assunto.

---

## 🟡 NOVO PROJETO — Criar MAPA_DO_PROJETO.md para a nova arquitetura (registrado 28/07/2026)

**O que falta:**
O MAPA antigo (que descrevia os 16 scripts) foi arquivado em `_archive/documentacao_sistema_antigo/`.
Quando a estrutura do novo projeto estiver definida (Gmail reader + IA classificadora + painel),
criar um novo `documentações/MAPA_DO_PROJETO.md` descrevendo:
- O que o sistema faz (em 30 segundos)
- As duas partes: leitura do Gmail e IA classificadora
- Onde mora cada coisa no projeto
- Regras que não se quebram

**Quando fazer:** após a estrutura do novo código estar definida (ainda em andamento).
**Por que é importante:** sem o mapa, uma IA nova que abrir o projeto não sabe por onde começar.

---

## 🟡 PAINEL — Ideias para amadurecer no painel lateral de categoria (registrado 31/07/2026)

Michel gostou do painel lateral que abre ao clicar numa categoria. Ideias para evolução futura:

**1. Fora do prazo**
Antes da lista de threads em cada seção (Aguardando Finaud / Aguardando Cliente), mostrar
a quantidade que está fora do prazo. Exemplo:
> AGUARDANDO FINAUD (54)
> ⚠ 12 fora do prazo
> [lista de threads]

**2. Linguagem do status no cartão de thread**
No cartão de cada thread, não exibir apenas o código técnico (ex.: R2) — exibir o significado
em linguagem simples para o usuário leigo entender sem precisar decorar os códigos.
Exemplo: em vez de "R2", mostrar "Aguardando a Finaud processar o material do cliente".

**3. Concluídas com regra de triagem**
Na seção "Concluídas", manter o mesmo padrão visual dos outros cartões e adicionar qual
regra de triagem foi usada para marcar como concluído (ex.: "Encerrado pela regra R1 — sem
pendência identificada").

**Quando amadurecer:** durante a especificação do painel do gestor (§13 da spec), depois
que toda a parte funcional estiver completa. Ver também pendência "PAINEL DO GESTOR —
Design para threads com múltiplos CADOCs".

---

## 🟡 NOVO PROJETO — Escrever README.md (registrado 28/07/2026)

O README antigo (que descrevia o pipeline de 16 scripts) foi arquivado em
`_archive/documentacao_sistema_antigo/README_sistema_antigo.md`.

**Quando fazer:** após a Fase 1 estar funcional (leitor Gmail + classificador IA rodando).
**O que escrever:** o que o sistema faz, como rodar localmente, onde está cada coisa.
**Por que esperar:** um README descreve um sistema que funciona — escrever agora seria descrever algo que ainda não existe.

---
