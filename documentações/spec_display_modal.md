# Spec — Display do Modal de E-mails

**Criado:** 2026-09-03  
**Atualizado:** 2026-09-04  
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
| A | Parcialmente decidido — A1 concluído, A2+ pendente |
| B–G | Pendente |

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

**Decisão:** pendente — aguarda mapeamento completo de todos os tipos.

### Sub-cenário A3 — Só anexo, texto mínimo (106 mensagens — 6%)

Mensagem cuja única função é entregar arquivos. O corpo tem no máximo uma frase
de cortesia ("Seguem os arquivos") seguida de assinatura. O conteúdo real está
nos anexos (Excel, PDF, etc.).

Exemplo real: *"Prezada, Seguem os arquivos para composição do DDR2011 de
14/08/2026. Atenciosamente,"* — com 4 planilhas Excel como anexos.

**Decisão:** pendente — aguarda mapeamento completo de todos os tipos.

### Sub-cenário A4 — Texto real + anexo (455 mensagens — 28%)

Mensagem com conteúdo escrito real que explica ou contextualiza os arquivos
enviados. O corpo tem pelo menos um parágrafo com informação — não é só cortesia.

Exemplo real: *"Prezada Juliana, Seguem em anexo as projeções de capital
referentes aos cenários Otimista e de Stress. No cenário Otimista, avaliamos
o crescimento..."* — com relatórios PDF e planilhas Excel.

**Decisão:** pendente — aguarda mapeamento completo de todos os tipos.

---

## Tipos B–G — Pendente

A ser definido com Michel, tipo por tipo.

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
| Push dos 4 commits para a VPS | 🔴 Pendente — aguarda OK do Michel |
