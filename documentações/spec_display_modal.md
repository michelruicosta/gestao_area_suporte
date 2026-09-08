# Spec — Display do Modal de E-mails

**Criado:** 2026-09-03  
**Atualizado:** 2026-09-08  
**Status:** em construção — tipo por tipo, com Michel  
**Regra:** nenhuma alteração no modal sem esta spec concluída (PENDENCIAS.md, 03/09/2026)

---

## Como ler este documento

Para cada tipo de mensagem (A–G), a spec define:
- **O que é** — em linguagem simples
- **Sub-cenários** — variações reais encontradas no banco
- **O que o modal deve mostrar** — decisão aprovada por Michel
- **O que não fazer** — restrições explícitas

---

## Visão geral — os 7 tipos de estrutura de e-mail

O sistema classifica automaticamente cada mensagem em um dos 7 tipos abaixo,
dependendo de como o corpo está organizado.

| Tipo | O que é | Threads | % |
|---|---|---|---|
| A | Texto puro, sem histórico citado | 1.241 | 67% |
| B | Resposta com texto novo + histórico citado abaixo | 293 | 15% |
| C | Encaminhamento Outlook com texto novo antes do bloco | 96 | 5% |
| D | Encaminhamento Outlook sem texto novo (só assinatura antes) | 128 | 6% |
| E | Resposta sem texto novo (só assinatura antes do separador) | 21 | 1% |
| F | Encaminhamento Gmail | 51 | 2% |
| G | Corpo vazio ou quase vazio | 2 | 0% |
| **Total** | | **1.832** | **100%** |

**O que muda entre os tipos no modal:** o que separamos em "parte nova" (o que o
remetente escreveu agora) e "parte encadeada" (o histórico citado) depende do tipo.
Tipo A não tem parte encadeada — é tudo parte nova.

**Status da spec por tipo:**

| Tipo | Status |
|---|---|
| A | ✅ Concluído — A1, A2, A3 e A4 decididos em 08/09/2026 |
| B | ✅ Revisado 08/09/2026 — parte nova visível; histórico oculto com toggle |
| C | ✅ Revisado 08/09/2026 — parte nova visível; bloco interno oculto / externo visível |
| D | ✅ Revisado 08/09/2026 — bloco interno oculto / externo visível |
| E | ✅ Revisado 08/09/2026 — parte encadeada ocultada com toggle |
| F | ✅ Revisado 08/09/2026 — bloco interno oculto / externo visível |
| G | ✅ Decidido 08/09/2026 — mostrar só metadados e anexos (sem corpo de texto) |

---

## Tipo A — Mensagem simples (sem histórico citado)

**O que é:** e-mail com texto puro, sem resposta citada abaixo e sem bloco encaminhado.  
**Volume:** 1.241 threads (maior grupo — 67% do total).

### Sub-cenário A1 — Texto limpo (834 threads — 67% do tipo A)

Mensagem pura, sem imagens embutidas.

**Decisão (03/09/2026):** exibir o corpo completo, incluindo assinatura.

**Motivo:** não há forma confiável de separar assinatura de conteúdo — qualquer
regra automática erra nos casos onde o remetente mistura texto real com o
fechamento ("Seguem os arquivos. Qualquer dúvida, ligue. Att, Jair"). O telefone
do contato, presente na assinatura, não está salvo em nenhum outro lugar no sistema.

### Sub-cenário A2 — Texto com imagens inline (642 mensagens — 40%)

Mensagem com imagens embutidas diretamente no corpo. As imagens aparecem no
texto como referências do tipo `[cid:...]` (formato Outlook) ou `[image: nome.ext]`
(formato Gmail). Podem ou não ter anexos adicionais.

Exemplo real: *"Prezados, bom dia! Seguem as posições de TVM´s e o relatório do
Depósito a Vista."* — com logo da empresa embutido no início e arquivos PDF/CSV
como anexos separados.

**Decisão (08/09/2026):** exibir o corpo completo incluindo assinatura, e todas as imagens
da parte nova (não há parte encadeada no Tipo A).

**Motivo:** mesma lógica do A1 — risco de ocultar conteúdo real (screenshot, logo relevante)
não é aceitável. Regra de imagens da parte nova (decidida em 04/09/2026) já cobre este caso.

### Sub-cenário A3 — Só anexo, texto mínimo (106 mensagens — 6%)

Mensagem cuja única função é entregar arquivos. O corpo tem no máximo uma frase
de cortesia ("Seguem os arquivos") seguida de assinatura. O conteúdo real está
nos anexos (Excel, PDF, etc.).

Exemplo real: *"Prezada, Seguem os arquivos para composição do DDR2011 de
14/08/2026. Atenciosamente,"* — com 4 planilhas Excel como anexos.

**Decisão (08/09/2026):** exibir o corpo completo (incluindo a frase de cortesia e a
assinatura) e os anexos. Nenhum elemento é ocultado.

**Motivo:** o texto mínimo pode conter informação útil (data, referência ao arquivo enviado).
Ocultar para "limpar" a tela arriscaria suprimir contexto que Michel possa precisar.

### Sub-cenário A4 — Texto real + anexo (455 mensagens — 28%)

Mensagem com conteúdo escrito real que explica ou contextualiza os arquivos
enviados. O corpo tem pelo menos um parágrafo com informação — não é só cortesia.

Exemplo real: *"Prezada Juliana, Seguem em anexo as projeções de capital
referentes aos cenários Otimista e de Stress. No cenário Otimista, avaliamos
o crescimento..."* — com relatórios PDF e planilhas Excel.

**Decisão (08/09/2026):** exibir o corpo completo — texto real, parágrafo explicativo,
assinatura — e os anexos. Nenhum elemento é ocultado.

**Motivo:** o texto é o conteúdo principal — contextualiza os arquivos e muitas vezes
contém informação que não está nos próprios anexos (premissas, resultados esperados).

---

## Tipo B — Resposta com texto novo + histórico citado

**O que é:** e-mail de resposta onde o remetente escreve algo novo no topo e mantém o
e-mail anterior citado abaixo (separado por uma linha como "Em seg., 31 de ago. escreveu:").  
**Volume:** 293 threads (15% do total).

**Origem:** respostas via Gmail e via Outlook. A diferença entre os dois é técnica — o
formato do arquivo é diferente, mas na tela o resultado é o mesmo. Não é possível
distinguir visualmente uma resposta Gmail de uma resposta Outlook.

**Estrutura:**
- **Parte nova** — o que o remetente escreveu agora (antes do separador)
- **Parte encadeada** — o e-mail anterior citado abaixo (após o separador) — é sempre
  repetição de uma mensagem que já aparece separadamente no modal

**Exemplo real:** thread "INDICE DE BASILEIA - 06.2026" — Monica (Finaud) responde a Carol
(Coluna DTVM) com o relatório DLO solicitado. A parte nova tem texto explicativo + arquivo
ZIP. A parte encadeada repete o e-mail original da Carol já visível na mensagem anterior.

**Decisão (08/09/2026 — revisão 08/09/2026):**
- Parte nova: exibida integralmente.
- Parte encadeada: **ocultada por padrão** com botão "Histórico da conversa — já visível
  acima (clique para expandir)". O conteúdo expande ao clicar. Motivo: é sempre repetição
  de mensagem já visível acima no modal — exibir por padrão aumenta o ruído sem acrescentar informação.

---

## Tipo C — Encaminhamento Outlook com texto novo

**O que é:** e-mail encaminhado via Outlook onde o remetente escreveu algo antes do bloco
encaminhado. Identificado pelos cabeçalhos "De: / Enviada em: / Para: / Assunto:" do Outlook.  
**Volume:** 96 threads (5% do total).

**Origem:** encaminhamentos via Outlook. O bloco encaminhado começa com os cabeçalhos
`De: / Enviada em: / Para: / Assunto:` — visível na tela. É por isso que Outlook e Gmail
estão em tipos separados neste documento, ao contrário das respostas (B e E).

**Sub-cenários do bloco encaminhado:**

| Sub-cenário | O que é | Como o sistema detecta | Decisão |
|---|---|---|---|
| C-interno | O e-mail encaminhado já é uma mensagem desta thread | Remetente ou assunto do bloco batem com participantes/assuntos da thread | Ocultar com toggle |
| C-externo | O e-mail encaminhado veio de fora da thread | Remetente não encontrado na thread | Mostrar sempre |
| C-sem-id | Não foi possível identificar (0,9% dos casos) | Nenhuma verificação resolveu | Tratar como externo — mostrar |

**Lógica de detecção (08/09/2026):** cascata de 4 verificações aplicadas ao cabeçalho do bloco:
1. E-mail no `De:`/`From:` → compara com participantes da thread
2. Nome no `De:`/`From:` → cruza com nomes dos participantes
3. Assunto do bloco → compara com assuntos das mensagens da thread
4. Não resolvido → trata como externo (seguro)
Cobertura: 99,1% do banco classificado (validado em 08/09/2026).

**Decisão (08/09/2026 — revisão 08/09/2026):**
- Parte nova: exibida integralmente.
- Bloco encaminhado interno: **oculto por padrão** com botão "Encaminhamento — conteúdo já
  visível neste chat (clique para expandir)".
- Bloco encaminhado externo: **sempre visível** — contém informação que não aparece em outro lugar.

---

## Tipo D — Encaminhamento Outlook sem texto novo

**O que é:** e-mail encaminhado via Outlook onde não há texto novo antes do bloco — só
assinatura ou campo vazio antes dos cabeçalhos "De: / Enviada em:".  
**Volume:** 128 threads (6% do total).

**Origem:** encaminhamentos via Outlook. O bloco encaminhado começa com os cabeçalhos
`De: / Enviada em: / Para: / Assunto:` — visível na tela. É por isso que Outlook e Gmail
estão em tipos separados neste documento, ao contrário das respostas (B e E).

**Sub-cenários e lógica de detecção:** idênticos ao Tipo C — ver tabela e cascata acima.

**Decisão (08/09/2026 — revisão 08/09/2026):**
- Parte nova: "(encaminhou sem adicionar texto)" — sempre visível.
- Bloco encaminhado interno: **oculto por padrão** com toggle.
- Bloco encaminhado externo: **sempre visível**.

---

## Tipo E — Resposta sem texto novo

**O que é:** e-mail de resposta onde não há conteúdo real antes do separador — só assinatura
ou campo vazio. O remetente respondeu mas não escreveu nada de novo.  
**Volume:** 21 threads (1% do total).

**Origem:** respostas via Gmail e via Outlook. A diferença entre os dois é técnica — o
formato do arquivo é diferente, mas na tela o resultado é o mesmo. Não é possível
distinguir visualmente uma resposta Gmail de uma resposta Outlook.

**Decisão (08/09/2026 — revisão 08/09/2026):**
- Parte nova: "(respondeu sem adicionar texto)" — sempre visível.
- Parte encadeada: **ocultada por padrão** com toggle. Mesma lógica do Tipo B — é sempre
  repetição de mensagem já visível acima no modal.

---

## Tipo F — Encaminhamento Gmail

**O que é:** e-mail encaminhado via Gmail, identificado pelo separador "---------- Forwarded
message ---------" seguido dos cabeçalhos Gmail (From: / Date: / Subject: / To:).  
**Volume:** 51 threads (2% do total).

**Origem:** encaminhamentos via Gmail. O bloco começa com o separador
`---------- Forwarded message ---------` seguido dos cabeçalhos Gmail (From / Date /
Subject / To) — visível na tela. É por isso que Outlook e Gmail estão em tipos separados
neste documento, ao contrário das respostas (B e E).

**Sub-cenários e lógica de detecção:** idênticos ao Tipo C — ver tabela e cascata acima.
Observação: encaminhamentos Gmail aparecem frequentemente com cabeçalho prefixado por `>`
(linhas citadas). O sistema limpa esses prefixos antes de analisar.

**Decisão (08/09/2026 — revisão 08/09/2026):**
- Parte nova: exibida integralmente (ou "(encaminhou sem adicionar texto)" se vazia).
- Bloco encaminhado interno: **oculto por padrão** com toggle.
- Bloco encaminhado externo: **sempre visível**.

---

## Tipo G — Corpo vazio

**O que é:** e-mail sem corpo de texto — só assunto e anexos, ou campo completamente vazio.  
**Volume:** 2 threads (0% do total).

**Decisão (08/09/2026):** não há corpo para exibir — o modal mostra só os anexos e metadados
(remetente, data, assunto).

---

## Imagens inline — padrões, volumes e decisões (04/09/2026)

Esta seção vale para todos os tipos (A–G). Sempre que uma mensagem contiver
referência de imagem inline, as regras abaixo se aplicam.

### O que são imagens inline

Imagens embutidas diretamente no corpo do e-mail — não são anexos que o usuário
baixa, são imagens que o remetente incluiu dentro do texto. No banco, aparecem
como referências entre colchetes.

### Padrões encontrados (varredura completa — 04/09/2026)

| ID | Formato no texto | Exemplo real | Qtde no banco | O que o sistema faz |
|---|---|---|---|---|
| I1 | `[cid:identificador]` | `[cid:a64ae88@01DD]` | 7.519 | Busca no Gmail API por Content-ID — formato Outlook |
| I2 | `[image: nome.ext]` | `[image: image.png]` | 790 | Busca no Gmail API por nome do arquivo — formato Gmail |
| I3 | `[nome.ext]` | `[image.png]` | 102 | Mesmo tratamento que I2 |
| I4 | URL externa em colchetes | `[https://terra.com/logo.png]` | 1.360 | Removido silenciosamente — logo externo, inacessível |
| I5 | Texto decorativo ou URL sem extensão | `[image: espaço.png]` | 2.480 | Removido silenciosamente |
| I6 | Mensagem do Gmail | `[Imagem removida pelo remetente.]` | 288 | Mantido como texto — o Gmail já removeu antes |
| I7 | Descrição de IA do Gmail | `[Texto O conteúdo gerado por IA pode estar incorreto.]` | 104 | Substituído pela imagem real via busca posicional no payload |

**Resultado da varredura:** nenhum caso ficou sem tratamento.

### Por que não é possível separar logo de conteúdo real com 100% de precisão

I1, I2 e I3 usam o mesmo formato técnico para dois propósitos opostos:

- **Conteúdo real** — screenshot de um sistema, foto de um documento, captura de
  tela enviada para ilustrar um problema → Michel quer ver
- **Logo/assinatura** — logo corporativo embutido na assinatura do e-mail, banner
  decorativo → Michel não quer ver

O formato do texto (`[cid:...]` ou `[image: nome.ext]`) não diz qual é qual.
A intenção do remetente não está registrada em nenhum campo. Heurísticas como
posição no corpo, nome do arquivo e recorrência por remetente existem, mas nenhuma
é 100% confiável — sempre haverá casos que fogem.

### Decisões aprovadas por Michel (04/09/2026)

| Situação | Decisão | Motivo |
|---|---|---|
| Imagens na **parte encadeada** (histórico citado nas respostas) | **Ocultar** | Quase sempre logos de assinaturas de quem respondeu antes — não ajudam a entender o caso |
| Imagens na **parte nova** (o que o remetente escreveu agora) | **Mostrar todas** | Risco de ocultar conteúdo real (screenshot, documento) não é aceitável |
| Filtragem por nome de arquivo (lista configurável de nomes a ocultar) | **Não implementar por agora** | Revisitar se necessário após uso em produção |

### Status de implementação

| Item | Status |
|---|---|
| Suporte a `[cid:...]` Outlook via Gmail API | ✅ Implementado e commitado (67162df) |
| Suporte a `[image: nome.ext]` e `[nome.ext]` Gmail via Gmail API | ✅ Implementado e commitado (0fd94fb) |
| Correção de bug SSL (thread-safety do Gmail service) | ✅ Implementado e commitado (c7024b5) |
| Correção de performance (Gmail API só chamado quando há imagem) | ✅ Implementado e commitado (a3082d5) |
| Ocultar imagens da parte encadeada | 🔴 Pendente — decisão aprovada em 04/09/2026 |
| Exibir imagens I7 (descrições de IA do Gmail) | ✅ Implementado e commitado (0782317) |
