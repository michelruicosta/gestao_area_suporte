# Registro de Correções — Oráculo 360 (Nova Arquitetura)

**Início:** 28/07/2026 — nova arquitetura (Gmail API + IA Classificadora)

> Histórico do sistema antigo (pipeline de 16 scripts, até 22/07/2026) →
> `_archive/documentacao_sistema_antigo/REGISTRO_CORRECOES_historico_sistema_antigo.md`

**Como usar:** toda correção — de bug, regra ou comportamento — entra aqui no momento em que é feita,
com entrada datada (HH:MM). Formato obrigatório: "Em miúdos" + Problema + Correção + Validação.

---

## 2026-08-03 — Revisão sequencial: §8, §9, §10 e §11 aprovados

### 03/08 — T04 (Western Union): papel da Finaud confirmado

**🔎 Em miúdos:** descobrimos o que a Finaud faz com o e-mail diário da Western Union — não é só informação de fundo, ela usa os dados para gerar o DDR (componente de câmbio).

**Problema:** T04 estava documentado como "aguarda confirmação de Michel" — o papel da Finaud no fluxo do CAM0050 e Balancete de Câmbio não estava claro.

**Correção:** Michel confirmou em 03/08/2026: a Finaud recebe o CAM0050 e o Balancete de Câmbio e os utiliza como insumo para compor o DDR (subcategoria cambial). T04 classificado como DDR_2011. Sinal de encerramento: thread de distribuição — Finaud processa internamente, sem resposta por e-mail esperada.

**Arquivos alterados:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — T04, §12 tabela de sinais, §14 Plano (Fase 0 marcada como Concluída).

**Validação:** ✅ Confirmado por Michel.

---

### 03/08 — §8 Regras de classificação: três lacunas identificadas e corrigidas na spec

**🔎 Em miúdos:** cruzamos todas as regras de classificação com o histórico real de 4.786 threads e encontramos três situações que as regras não cobriam — agora estão todas documentadas.

**Lacunas confirmadas e adicionadas à spec:**

1. **Escopo do texto analisado** — as regras se aplicam só ao texto novo, não ao histórico citado (linhas `>` ou separadas por `---`).
2. **Veto + pergunta no mesmo e-mail** — quando a última mensagem começa com agradecimento mas contém uma pergunta ou pedido novo, o agradecimento não cancela o conteúdo — o caso não fecha.
3. **"Transmitido no BACEN" pelo cliente** — se o texto novo do último e-mail contiver "transmitido no BACEN" (qualquer variação), o caso é Concluído independente de quem enviou.

**Validação:** ✅ Confirmado por Michel. Script de validação `scripts/consultas/validar_regras_classificacao.py` executado contra 4.786 threads reais — 1.137 divergências restantes são esperadas (classificação histórica do pipeline antigo vs. regras novas).

---

### 03/08 — §9 atualizado: "entregue" por categoria + RETORNO_BACEN leitura de imagem

**🔎 Em miúdos:** descobrimos e gravamos na spec o que a Finaud entrega ao cliente em cada tipo de trabalho — e identificamos que as críticas do BACEN chegam como foto de tela, não como texto.

**Problema:** a spec não definia o que significa "entregue" para cada categoria. Sem isso, a IA não sabe quando o trabalho da Finaud está concluído.

**Investigação:** scripts contra o histórico real (oraculo_360_finaud) para cada categoria. Resultados:
- DDR 2011, DRM 2060, DRL 2160, DLO 2061, DLI 2062, CADOC 4111 → ZIP `CNPJ_CATEGORIA_DATA.zip`
- S5 → PDF (`Resultado Quantitativo - S5.pdf`)
- FORCAPITAL → varia: texto, XLSX ou PDF
- PVCA 6209 → `BACEN.ZIP` com 8 TXT (inclui CONTATOS.TXT — antes estava como 7 arquivos)
- DRSAC 2030 → XML (`DocumentoDRSAC`) — confirmado via XSD oficial do BACEN
- RETORNO\_BACEN → não é entrega — é a crítica do BACEN; 1.061 PNG/JPG detectados (prints de tela)

**Decisão adicional — DDR multi-thread:** 99% dos CADOC DDR chegam em thread SEPARADA dos dados brutos do cliente. Chave de ligação: CNPJ + data_competencia do nome do ZIP (padrão 100% padronizado). Fase 2 resolverá a ligação automática.

**Decisão — RETORNO\_BACEN imagem:** o classificador usa a visão nativa do Claude (multimodal) para ler os PNG/JPG e extrair o texto da crítica. Confirmado por Michel em 03/08/2026.

**Correção:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — §9 (tabela de "entregue" por categoria + requisito de imagem). `documentações/spec_nova_arquitetura.html` — §9 atualizado e publicado como artifact.

**Validação:** ✅ Confirmado por Michel em 03/08/2026.

---

### 03/08 — §9 e §10 Catálogo revisados e aprovados

**🔎 Em miúdos:** passagem rápida pelas 12 categorias e pelos 19 exemplos reais — conteúdo confirmado como correto por Michel.

**§9 Modelo de rastreamento:** aprovado sem alterações.

**§10 Catálogo de categorias:** 12 categorias (4111, DDR_2011, DRM_2060, DLO_2061, DLI_2062, DRL_2160, S5, SUPORTE, RETORNO_BACEN, FORCAPITAL, DRSAC_2030, PVCA_6209) aprovadas — cada uma com sinais de detecção e regras R1–R5.

**§11 Exemplos reais:** T01–T19 aprovados. T04 encerrado (ver entrada acima). Fase 0 marcada como Concluída.

**Validação:** ✅ Confirmado por Michel.

---

## 2026-07-31 — Reorganização estrutural da spec + início da revisão sequencial

### 31/07 — Spec: três mudanças estruturais aprovadas por Michel

**🔎 Em miúdos:** reorganizamos a especificação para ter uma ordem mais lógica de leitura — o que o sistema é e como funciona primeiro, as decisões e o plano de implantação por último.

**O que foi mudado:**

1. **Seção "Ganho principal e risco principal" — excluída.** A seção era desnecessária: a regra de que a IA só classifica quando todos os campos obrigatórios estão preenchidos (e o que não estiver vai para fila de revisão humana) já trata o risco por design — não precisava de seção separada. Decisão de Michel.

2. **"Plano de implantação por fases" — movido de posição intermediária para §15 (final).** Motivação: seções de planejamento de execução não pertencem no meio da spec técnica. Foram feitas três rodadas completas de renumeração e atualização de todas as referências cruzadas no documento.

3. **"Decisões tomadas e justificativas" — movido para §14 (penúltimo).** Mesmo critério: será preenchido gradualmente conforme a spec avança; deve ficar no final para não interromper a leitura técnica.

**Arquivo alterado:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` — estrutura e numeração de seções

**Validação:** estrutura final verificada; todas as referências cruzadas (§X) atualizadas nas três rodadas de renumeração. ✅ VALIDADO

---

### 31/07 — Spec §7 (Mapeamento de campos): passagem rápida de revisão — duas lacunas identificadas

**🔎 Em miúdos:** fizemos uma passagem rápida pela seção que mapeia os 8 campos do e-mail. O conteúdo está correto, mas identificamos que cada campo documenta só O QUE é — falta descrever COMO o sistema processa cada campo passo a passo.

**Lacunas identificadas:**
- Campo 1: descreve o que filtra mas não o passo a passo de filtragem (verificar endereço → padrões → assunto → descartar)
- Campos 1 a 8: não têm bloco "Como o sistema processa" — sequência de decisões que o sistema executa

**Ação tomada:** registrado como 🔴 BLOQUEADOR em `documentações/PENDENCIAS.md`. Obrigatório resolver antes do desenvolvimento das telas (§10 da spec). Nada alterado na spec — espera resolução em sessão dedicada.

**Correção do status:** linha de status da spec atualizada de "§9 completa" para "§7 completa" (o mapeamento migrou de §9 para §7 após as renumerações).

---

## 2026-07-31 — Campo 8 completo na spec §10

### 31/07 — Campo 8 (Thread ID e Data): regras definidas com base no histórico de 8.825 e-mails

**🔎 Em miúdos:** definimos como o sistema vai identificar cada conversa (Thread ID), quais datas vai usar, como vai descobrir o mês do CADOC quando não está escrito explicitamente no assunto, e o que vai fazer quando a mesma conversa de e-mail é usada por meses para entregas diferentes.

**O que foi feito:**
- Scripts de análise criados e executados: `analisar_threads_datas.py` e `analisar_mes_sem_ano.py`
- 3.270 threads analisadas; 59 identificadas como "threads de canal" (1,8% do total)
- 118 threads mistas (categorias diferentes na mesma thread) identificadas e regra definida
- 157 casos com mês por extenso sem ano testados — regra de inferência validada (100% nos 5 com ground truth)
- Decisões gravadas na spec `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §10 Campo 8`
- Artifact visual atualizado: https://claude.ai/code/artifact/4eb2c74e-27d9-41a2-ad7c-6bc5b1d6ab01

**Regras escritas:**
- Thread ID (`thread_root`) = chave de agrupamento de toda a thread; 100% preenchido no histórico
- `data_email` (sempre preenchida) vs. `data_competencia` (extraída pela IA, pode ser null)
- Inferência de ano quando assunto tem só o mês: se mês ≤ mês do e-mail → mesmo ano; se maior → ano anterior
- `data_competencia = null` → sistema não monitora prazo (decisão Michel, 31/07/2026)
- Threads de canal: 3 tipos definidos (entrega recorrente / coordenação / caso complexo)
- 4111 (diário): `data_competencia` = `data_email` pois o arquivo nunca traz data no nome

**Validação:** regras derivadas do histórico real de 8.825 e-mails. ✅ VALIDADO

---

## 2026-07-31 — Campo 7 completo na spec §10

### 31/07 — Campo 7 (Anexos): regras definidas com base no histórico completo de 8.825 e-mails

**🔎 Em miúdos:** sabemos agora exatamente o que o sistema vai fazer com cada tipo de arquivo em anexo — desde o ZIP padrão do CADOC até formatos que não estavam previstos, como COSIF em formato antigo `.bc`, e-mails encaminhados como anexo e arquivos com nome embaralhado.

**O que foi feito:**
- Script `scripts/consultas/analisar_anexos_emails.py` criado e executado — varreu 78.087 arquivos em disco
- 6 cenários não previstos identificados e documentados: `.bc`, `.xml` direto, sem extensão (2 tipos), `.rar`, `.eml`
- 4 questões pendentes resolvidas com dados reais: ZIP dentro de ZIP (0 casos), muitos anexos (máx. 37), nomes genéricos (39,4% — quase todos images), tamanho (máx. 18 MB, sem limite para triagem)
- Decisões gravadas na spec `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §10 Campo 7`
- Artifact visual atualizado: https://claude.ai/code/artifact/4eb2c74e-27d9-41a2-ad7c-6bc5b1d6ab01

**Regras escritas:**
- ZIP do CADOC padrão `CNPJ_CADOC_DATA.zip` — 6 categorias, confiança altíssima
- Sufixo `_S_N` = substituição solicitada pelo BACEN (351 casos no histórico)
- COSIF em 3 formatos: `.xml` direto (642), `.bc` antigo (123), ZIP genérico
- Formatos especiais: `.rar` (6), `.eml` (8), sem extensão BACEN (30), encoding quebrado (200)

**Validação:** ✅ VALIDADO — regras derivadas do histórico completo de 8.825 e-mails · 78.087 arquivos

---

## 2026-07-30 (continuação de sessão — Campo 6 completo na spec)

### 30/07 — Campo 6: análise das 12 categorias concluída e escrita na spec §10

**🔎 Em miúdos:** após analisar todos os e-mails das 12 categorias, gravamos as regras de limpeza definitivas na especificação — agora qualquer desenvolvedor (ou IA) sabe exatamente o que o sistema vai fazer com o texto de cada e-mail antes de entregar para a IA classificar.

**O que foi feito:**
- 6.989 e-mails analisados via `scripts/consultas/analisar_corpo_emails.py`
- 12 categorias validadas individualmente (DDR_2011 até PVCA_6209)
- Seção "O que temos / O que utilizaremos / Regras de negócio" escrita em `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §10` (Campo 6)
- Tabela completa com percentuais de cada elemento por categoria guardada na spec

**Resultados consolidados:**

| Categoria | E-mails | Assinatura | Hist. `>` | Hist. `---` | Rodapé | `[image:]` | `[cid:]` |
|---|---|---|---|---|---|---|---|
| DDR_2011 | 2.350 | 96,4% | 37,1% | 22,1% | 95,5% | 23,9% | 18,9% |
| SCD_4111 | 728 | 97,7% | 38,2% | 25,1% | 92,3% | 19,8% | 22,0% |
| DRM_2060 | 163 | 96,3% | 35,0% | 16,6% | 98,2% | 22,1% | 27,6% |
| DLO_2061 | 1.172 | 77,7% | 39,2% | 26,6% | 96,8% | 29,1% | 28,0% |
| DLI_2062 | 119 | 88,2% | 47,1% | 31,9% | 100,0% | 37,8% | 22,7% |
| DRL_2160 | 267 | 96,3% | 43,1% | 19,1% | 99,6% | 26,6% | 18,0% |
| S5 | 122 | 92,6% | 63,9% | 22,1%★ | 100,0% | 30,3% | 18,0% |
| RETORNO_BACEN | 1.298 | 92,2% | 50,2% | 31,3% | 100,0% | 36,3% | 41,0% |
| SUPORTE | 678 | 79,8% | 46,2% | 15,9% | 97,3% | 28,5% | 29,4% |
| FORCAPITAL | 85 | 84,7% | 29,4% | 20,0% | 100,0% | 9,4% | 36,5% |
| DRSAC_2030 | 3 | 100,0% | 66,7% | 33,3% | 100,0% | 33,3% | 33,3% |
| PVCA_6209 | 4 | 75,0% | 75,0% | 0,0% | 100,0% | 0,0% | 0,0% |
| **TOTAL** | **6.989** | | | | | | |

★ Corrigido após fix da regra L2 (ver entrada anterior neste registro).

**Validação:** ✅ Todas as 12 categorias validadas por Michel durante a sessão de 30/07/2026.
**Sem teste:** script de consulta somente-leitura — não modifica dados de produção.

---

## 2026-07-30 (continuação de sessão — análise Campo 6 categorias)

### 30/07 — Regra L2 corrigida: separador decorativo `---` não é mais confundido com histórico encaminhado

**🔎 Em miúdos:** o sistema aprendeu a diferença entre um traço usado como enfeite visual dentro do texto e um traço que separa o e-mail antigo do novo. Antes, qualquer fileira de traços acionava o corte — agora só aciona quando há dados de e-mail (remetente, data, destinatário) logo depois.

**Problema:** na análise do S5, o padrão `PAD_ENCAMINHADO` detectava `-----` como "histórico encaminhado" mesmo quando os traços eram separadores decorativos dentro do conteúdo real do e-mail. Exemplo encontrado: Rodrigo enviou orientação regulatória formatada com `-----` como título de seção — a regra iria cortar o conteúdo útil achando que era histórico.

**Causa raiz:** o padrão original `-{5,}|_{5,}|={5,}` detectava qualquer sequência de 5+ traços, sem verificar o que vinha depois. Num e-mail encaminhado real, depois dos traços sempre aparecem `De:`, `Para:`, `Data:` — os campos do e-mail original. Num separador decorativo, aparecem emojis ou texto normal.

**Correção:** `scripts/consultas/analisar_corpo_emails.py` — `PAD_ENCAMINHADO` atualizado:
- Antes: `-{5,}|_{5,}|={5,}` (qualquer traço de 5+)
- Depois: `(?:-{5,}|_{5,}|={5,})\s*\n\s*(?:de:|from:|para:|to:|data:|date:|enviado\s*em:|sent:)` (traço de 5+ **somente** se seguido de cabeçalho de e-mail na linha seguinte)

**Validação:** ✅ S5 re-rodado — Histórico encaminhado caiu de 39,3% (48 e-mails, com falsos positivos) para 22,1% (27 e-mails, só histórico real). Agora alinhado com as demais categorias (DDR: 22,1%, DRM: 16,6%, DRL: 19,1%).
**Sem teste:** script de consulta somente-leitura — não modifica dados de produção.

---

## 2026-07-30 (continuação de sessão)

### 30/07 — Campo 6 DDR_2011: Passo 3 validado por Michel — todos os 6 elementos ✅

**🔎 Em miúdos:** Michel olhou exemplos reais do que o sistema detecta (e não detecta) em cada elemento de "sujeira" no corpo dos e-mails, e confirmou que está correto para todos os 6 tipos.

**O que foi feito:**
1. Criado script permanente `scripts/consultas/analisar_corpo_emails.py` — analisa qualquer categoria com os padrões do Passo 3; parametrizado por projeto e CADOC.
2. Padrão de assinatura iterado até 96,4% (3 rodadas de melhoria): adicionados fechamentos em inglês (`Kind Regards`, `Sincerely`, etc.) e `Grata/Grato`; corrigido problema do rodapé Google Groups que empurrava assinatura para fora da janela de busca.
3. Artifact de validação publicado: https://claude.ai/code/artifact/5054a35e-cbae-4beb-af23-df3c0972bcae
4. Michel validou os 6 elementos via artifact — exemplos detectados e não detectados conferidos.

**Resultados validados:**

| Elemento | Detectado em | Decisão |
|---|---|---|
| Assinatura | 96,4% (2.266/2.350) | ✅ 84 casos top-post aceitos — não prejudica a IA |
| Histórico citado (`>`) | 37,1% (873/2.350) | ✅ |
| Histórico encaminhado (`---`) | 22,1% (519/2.350) | ✅ |
| Rodapé automático | 95,5% (2.244/2.350) | ✅ |
| `[image:]` | 23,9% (562/2.350) | ✅ |
| `[cid:]` | 18,9% (445/2.350) | ✅ |

**Conceitos entendidos e confirmados por Michel (30/07/2026):**
- O Passo 3 resolve deduplicação automaticamente: cada e-mail fica só com o texto novo
- `>` = resposta (reply); `---` = encaminhamento (forward) — dois formatos, mesmo propósito: remover conteúdo antigo
- Para classificação: remover tudo é suficiente. Para IA Assistente de aprendizado: precisa do histórico completo → pendência registrada
- Threads com múltiplos CADOCs no painel do gestor → pendência registrada

**Validação:** ✅ Todos os 6 elementos aprovados por Michel (30/07/2026).
**Sem teste:** script de consulta — não modifica dados, não tem lógica de produção que precise de cobertura de teste.

---

## 2026-07-30

### 30/07 — Estrutura de documentação do projeto aprovada: 5 documentos com papéis distintos

**🔎 Em miúdos:** definimos como organizar todo o conhecimento do projeto — cada tipo de informação tem um lugar certo, e sabe-se onde olhar sem precisar lembrar.

**Problema:** ao crescer a documentação, ficou difícil decidir onde gravar cada tipo de informação — a spec estava virando um depósito de tudo.

**Decisão (30/07/2026):**

| Documento | Papel |
|---|---|
| `ESPECIFICACAO_NOVA_ARQUITETURA.md` | O mapa — decisões e regras ("o que temos" / "o que usaremos") |
| Artifact visual (claude.ai) | Visual — como ficará na tela e por quê |
| Lista de tarefas + fases (a criar) | Roteiro do desenvolvimento |
| `REGISTRO_CORRECOES.md` | Histórico datado do que foi feito |
| `PENDENCIAS.md` | O que falta — com checklist |

**Estrutura interna de cada campo da spec (3 partes):**
1. "O que temos" — dados reais da produção analisados
2. "O que utilizaremos" — decisão tomada
3. "Regras de negócio" — o que a IA vai seguir

**Validação:** ✅ Aprovado por Michel (30/07/2026). Gravado em memória (`projeto-estrutura-documentacao.md`) e aplicado a partir do Campo 6.

---

### 30/07 — Análise do Campo 6 (corpo do e-mail): DDR_2011 concluída — 8 regras de limpeza estabelecidas

**🔎 Em miúdos:** descobrimos como chegam os e-mails do DDR na produção e definimos as regras de "faxina" que o sistema precisa aplicar antes de entregar o texto para a IA ler. Sem essa faxina, a IA leria assinatura, histórico antigo e logos como se fossem parte da mensagem — e classificaria errado.

**Problema:** Campo 6 (corpo do e-mail) estava pendente. Não sabíamos como os e-mails chegam na produção nem o que a IA receberia se passássemos o texto direto.

**Causa raiz:** o e-mail bruto tem muita "sujeira" misturada ao texto real da mensagem: assinaturas com logos, histórico de respostas citadas (`>`), histórico encaminhado, rodapé automático do Google Groups, imagens decorativas convertidas em texto.

**Análise executada:** todos os 2.350 e-mails DDR_2011 (JSON01 × JSON03 via `x_gm_thrid`).

**Descobertas por regra:**

| Regra | O que afeta | % dos e-mails |
|---|---|---|
| L1 — Assinatura (`Att,`, `Atenciosamente`, etc.) | Detectada em 92,8% — corte funcionando | 92,8% |
| L2 — Histórico com traços (`---`, `___` Outlook) | Detectado em 6,3% | 6,3% |
| L3 — Histórico com seta `>` (reply citado) | **91% dos e-mails** — regra nova crítica | 91,0% |
| L4 — Rodapé Google Groups (`To unsubscribe`) | **95,5% dos e-mails** — regra nova crítica | 95,5% |
| L5 — Imagem decorativa (redes sociais, logos) | Maioria das 562 imagens encontradas | — |
| L6 — Imagem genérica (`image.png`) antes da assinatura | 249 ocorrências — OCR obrigatório | — |
| L7 — Imagem genérica depois da assinatura | Descartar (logo de rodapé) | — |
| L8 — Corpo vazio após limpeza | 4 e-mails (encaminhamento R5 puro) | 0,2% |

**Protocolo de imagens DDR_2011:**
- Nomes decorativos seguros para descartar: `instagram`, `linkedin`, `facebook`, `youtube`, `whatsapp`, `traders logo`, `esign`, `ícone`, `site mb`, `www.guru.com.vc` e variações de redes sociais/logos
- Nome genérico `image.png` antes da assinatura: pode ser arquivo de dados (ex.: RD_Moedas enviado como imagem) → **OCR obrigatório** → se OCR falhar → fila de revisão humana
- Nome genérico depois da assinatura: descartar (rodapé decorativo)
- Regra de ouro: nenhuma imagem descartada silenciosamente — OCR falhou = e-mail arquivado para revisão

**Artifact visual:** https://claude.ai/code/artifact/f86d271e-b354-49e2-8d2b-b110e68652c6 — 4 casos de imagem (decorativa / OCR / OCR falhou / corpo vazio).

**Validação:** ✅ Confirmado por Michel (30/07/2026). Regras L1–L8 registradas em `documentações/PENDENCIAS.md` como baseline para análise das demais 11 categorias.

---

## 2026-07-29

### 29/07 14:43 — Regras de classificação R1–R5 escritas para todas as 12 categorias

**🔎 Em miúdos:** escrevemos o "manual" que a IA vai usar para classificar cada e-mail — para cada tipo de e-mail (DDR, DLO, etc.), definimos exatamente quando a thread está "Aguardando" e quando está "Concluída", com exemplos reais.

**Problema:** a spec (`documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §14`) tinha apenas a descrição de cada categoria (o que é, como reconhecer, o fluxo). Não tinha as regras de classificação — sem elas, a IA não sabe decidir o status de cada thread.

**Causa raiz:** as regras precisavam ser derivadas do histórico real de threads validadas (`oraculo_360_finaud/documentações/DOCUMENTACAO_TRIAGEM.md`) com cobertura confirmada de 100%.

**Correção:** para cada uma das 12 categorias, executamos:
1. Leitura da seção do histórico
2. Varredura de cobertura (tabela com todos os padrões e a regra que cobre cada um)
3. Aprovação do Michel
4. Gravação em `ESPECIFICACAO_NOVA_ARQUITETURA.md §14` e `spec_nova_arquitetura.html §14`

Regras transversais confirmadas durante o processo:
- §11.5 regra universal de cortesia (escrita no início da sessão — ver entrada abaixo)
- DRSAC/PVCA R2: cliente pode enviar arquivo para Finaud analisar/corrigir (exceto retorno BACEN)
- S5 R4: mesmo significado padrão (acuse curto), não "resposta substantiva" como no histórico antigo

**Validação:** ✅ Confirmado por Michel categoria por categoria. Artifact publicado como v2.13. Total: 3.075 threads históricas cobrindo 100% dos padrões documentados.

---

### 29/07 — Regra universal: frases de cortesia após entrega = Concluído

**🔎 Em miúdos:** quando a Finaud entrega o arquivo e assina com "Desde já agradeço" — ou quando o cliente responde "Obrigado" — isso não cria nenhuma pendência. A thread está encerrada.

**Problema:** o sistema antigo interpretava frases de assinatura cortês do colaborador Lucas ("Desde já agradeço e permaneço à disposição") como pedido ao cliente, marcando a thread como Aguardando/Cliente quando na verdade o arquivo já havia sido entregue. 3 threads do SCD_4111 tinham esse gap documentado.

**Correção:** regra universal adicionada ao §11.5 da especificação e aplicada a todas as 12 categorias: frase de cortesia/agradecimento/assinatura padrão após a entrega = Concluído, independente de quem enviou (Finaud ou cliente).

**Validação:** ✅ Confirmado por Michel (29/07/2026). Gravado em `ESPECIFICACAO_NOVA_ARQUITETURA.md §11.3` e `spec_nova_arquitetura.html §11.5`.

---

## 2026-07-28

### 28/07 — GitHub conectado e repositório publicado

**🔎 Em miúdos:** o projeto agora tem backup na nuvem (GitHub). Antes estava só no PC — se o PC quebrasse, perdia tudo.

**Problema:** repositório local sem remote configurado; arquivos novos (testes, templates, nova arquitetura) nunca haviam sido commitados; planilha com dados sensíveis de clientes em risco de ser exposta acidentalmente.

**Correção:**
- `documentações/indício-qualidade.xlsx` adicionado ao `.gitignore` (dados sensíveis de clientes)
- Branch local renomeada de `master` para `main` (padrão GitHub)
- Remote `origin` apontado para `github.com/michelruicosta/gestao_area_suporte`
- 57 commits do histórico enviados ao GitHub
- 98 arquivos novos commitados e enviados (sistema atual + nova arquitetura + testes + CI)

**Validação:** ✅ Push confirmado no GitHub — `github.com/michelruicosta/gestao_area_suporte`; `.xlsx` não aparece no repositório remoto.

