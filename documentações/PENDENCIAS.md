# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-07-30
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui (nunca o
contrário, para não perder histórico). Ver regra completa no `CLAUDE.md`.

---

## 🔴 URGENTE — Campo 6 (Corpo): análise de limpeza por categoria (iniciado 29/07/2026)

Sem o Campo 6 documentado, a `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10 está incompleta
e o classificador IA não pode ser construído. **Campo 6 é o mais crítico** — é o texto que a IA lê
para classificar cada e-mail.

**Decisão de abordagem (29/07/2026):** a IA nunca recebe o e-mail bruto. Antes de classificar, o
sistema aplica regras de limpeza. O Campo 6 define exatamente essas regras. Para definir as regras
com segurança, analisamos **todos** os e-mails de cada categoria nos dados de produção (JSON01 × JSON03).

### Regras de limpeza estabelecidas na análise do DDR_2011 (baseline para todas as categorias)

| # | Regra | O que faz | Descoberta em |
|---|---|---|---|
| L1 | Assinatura | Corta em `Att,` / `Atenciosamente` / `À disposição` / `Cordialmente` / `Desde já agradeço` / `Antecipadamente grata` | DDR_2011 |
| L2 | Histórico com traços | Corta em `-----` (Gmail forward) e `___` (Outlook separator) | DDR_2011 |
| L3 | Histórico com seta `>` | Remove linhas que começam com `>` (reply citado) | DDR_2011 |
| L4 | Rodapé de lista | Corta em `To unsubscribe from this group` (rodapé Google Groups) | DDR_2011 |
| L5 | Imagem decorativa | Remove `[image: facebook/instagram/linkedin/youtube/whatsapp/logo/ícone/esign]` | DDR_2011 |
| L6 | Imagem com nome genérico antes da assinatura | Tenta OCR → se lê texto útil: inclui; se não lê: arquiva para revisão humana | DDR_2011 |
| L7 | Imagem com nome genérico depois da assinatura | Remove (provavelmente logo de rodapé) | DDR_2011 |
| L8 | Corpo vazio após limpeza | Sinaliza como `ENCAMINHAMENTO_INTERNO` (R5) — não classifica sem texto | DDR_2011 |

> **Regra de ouro — imagens:** nenhuma imagem é descartada silenciosamente. Se não for decorativa
> e o OCR falhar, o e-mail vai para fila de revisão humana. A IA não classifica até resolver.

### Status da análise por categoria

| # | Categoria | E-mails no JSON01 | Análise L1–L8 | Imagens inspecionadas | Protocolo registrado |
|---|---|---|---|---|---|
| 1 | **DDR_2011** | 2.350 | ✅ concluída | ✅ concluída | ✅ (ver REGISTRO_CORRECOES 30/07) |
| 2 | SCD_4111 | — | ☐ | ☐ | ☐ |
| 3 | DRM_2060 | — | ☐ | ☐ | ☐ |
| 4 | DLO_2061 | — | ☐ | ☐ | ☐ |
| 5 | DLI_2062 | — | ☐ | ☐ | ☐ |
| 6 | DRL_2160 | — | ☐ | ☐ | ☐ |
| 7 | S5 | — | ☐ | ☐ | ☐ |
| 8 | RETORNO_BACEN | — | ☐ | ☐ | ☐ |
| 9 | SUPORTE | — | ☐ | ☐ | ☐ |
| 10 | FORCAPITAL | — | ☐ | ☐ | ☐ |
| 11 | DRSAC_2030 | — | ☐ | ☐ | ☐ |
| 12 | PVCA_6209 | — | ☐ | ☐ | ☐ |

### Metodologia por categoria (repetir para cada ☐ acima)

Para cada categoria, executar em ordem:

1. **Contar e-mails** — cruzar JSON03 (categoria) × JSON01 (corpo) via `x_gm_thrid`
2. **Simular as 8 regras de limpeza** em todos os e-mails:
   - Quantos cada regra afeta (%)
   - Padrões novos não cobertos pelas regras → adicionar à lista se encontrar
   - Quantos ficam vazios após limpeza
3. **Inspecionar imagens**:
   - Quais nomes aparecem (Counter por nome)
   - Quantas estão antes vs. depois da assinatura
   - Exemplos de contexto para imagens com nome genérico (`image.png`)
   - Definir: o que é decorativo (descartar) vs. conteúdo (OCR)
4. **Registrar protocolo da categoria** no REGISTRO_CORRECOES com:
   - Regras L1–L8: funcionam? Alguma exceção?
   - Imagens: lista de nomes decorativos + protocolo OCR para esta categoria
   - Casos especiais encontrados

**Scripts prontos no scratchpad:**
- `simular_limpeza_ddr.py` — adaptar mudando o filtro de cadoc
- `inspecionar_imagens_ddr.py` — adaptar mudando o filtro de cadoc

**Após todas as 12 categorias concluídas:**
- Consolidar regras universais vs. exceções por categoria
- Escrever Campo 6 em `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10
- Publicar artifact atualizado

**Outros campos pendentes (aguardam Campo 6 estar concluído):**
- **Campo 7 — Anexos:** tipos de arquivo por categoria, o que a IA extrai
- **Campo 8 — Thread ID e Data:** rastreamento de thread, data de referência regulatória

**Arquivo:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10

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

## 🟡 NOVO PROJETO — Escrever README.md (registrado 28/07/2026)

O README antigo (que descrevia o pipeline de 16 scripts) foi arquivado em
`_archive/documentacao_sistema_antigo/README_sistema_antigo.md`.

**Quando fazer:** após a Fase 1 estar funcional (leitor Gmail + classificador IA rodando).
**O que escrever:** o que o sistema faz, como rodar localmente, onde está cada coisa.
**Por que esperar:** um README descreve um sistema que funciona — escrever agora seria descrever algo que ainda não existe.

---
