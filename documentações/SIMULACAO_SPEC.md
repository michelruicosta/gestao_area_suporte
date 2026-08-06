# Simulação da Especificação com Dados Reais

**Objetivo:** Simular o processamento das 943 threads reais da caixa `coleta.oraculo@finaud.com.br` pelas regras da especificação (`documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md`). Garantir que todas as threads tenham um destino correto — filtrada, retida ou classificada — e documentar cada gap encontrado. Nenhum gap pode ficar sem decisão registrada.

**Base de dados:** `data/json/pipeline/01_extração_dados_brutos_gmail.json` — 943 threads extraídas em 05/08/2026 pelo `scripts/coletor_gmail.py`.

**Regra de trabalho:** quando um cenário não for satisfatório, paramos, analisamos juntos, registramos na seção "Gaps" e atualizamos a spec antes de continuar.

---

## Critério de aprovação por thread

Cada thread deve chegar a um dos três destinos abaixo. Se não chegar → gap.

| Destino | O que significa | Quando é correto |
|---|---|---|
| **FILTRADA** | Descartada automaticamente antes de chegar na IA | Remetente automático (Campo 1) ou assunto automático (Campo 5) identificado corretamente |
| **RETIDA** | Pausada para revisão humana com notificação | Dado faltando ou IA abaixo de 99% de confiança |
| **CLASSIFICADA** | Processada pela IA com categoria e status definidos | Categoria correta + status correto (Aguardando/Concluído) + remetente e destinatário identificados |

---

## Passos da simulação

| # | Passo | Seção da spec | Status | Resultado |
|---|---|---|---|---|
| 1 | Filtros — quais threads são descartadas antes da IA? | §4 | ✅ Concluído | **166 filtradas (17,6%), 777 seguem (82,4%).** Filtro revisado e validado com varredura completa dos 943 threads — zero threads suspeitas fora do filtro. Gap #4 resolvido. **777 é o número base para todos os passos seguintes.** |
| 2 | Identificação do remetente — quem enviou? | §7 Campo 1 → Campo 4 | ✅ Concluído | **777 threads válidas identificadas.** 280 clientes diretos (36%) · 127 colaboradores diretos (16,3%) · 363 clientes via suporte@ com Reply-To (46,7%) · 7 via suporte@ sem Reply-To — campo responsável em branco (0,9%). |
| 3 | Identificação do destinatário — quem recebeu? | §7 Campo 2 + Campo 3 | ⬜ Pendente | — |
| 4 | Classificação — em qual categoria cada thread se encaixa? | §10 + §11 | 🔄 Em andamento | DDR 195 · SCD 168 · DLO 90 · DRM 66 · RETORNO_BACEN 51 · DLI 44 · DRL 29 · S5 11 · SUPORTE 327. Gap #3 resolvido: PCAM = DDR. FogBugz filtrado (novo filtro combinado). |
| 5 | Status — aguardando ou concluído? | §8 | ⬜ Pendente | — |
| 6 | Cobertura geral — todos os tipos de thread têm categoria? | §10 | ⬜ Pendente | — |

**Legenda de status:** ⬜ Pendente · 🔄 Em andamento · ✅ Concluído · ⚠️ Gap encontrado (ver tabela abaixo)

---

## Registro de gaps

Gaps são cenários reais que a spec não cobre, cobre de forma errada ou cobre de forma incompleta.

| # | Data | Passo | Thread de exemplo | O que falhou | Decisão tomada | Spec atualizada? |
|---|---|---|---|---|---|---|
| 1 | 05/08/2026 | 1 — Filtros | "ENC: Risk Driver - ID CORRETORA..." (jean.lessa@denvercontabil.com.br) | O filtro Campo 5 "Risk Driver -" estava filtrando e-mails de **clientes** que encaminham ou respondem sobre o Risk Driver. Os relatórios automáticos já são capturados pelo Campo 1 (From = riskdriver@finaud.com.br). 5 threads afetadas: Denver Contábil, Oslo DTVM, Guru Corretora, CV Investimentos, Broker Brasil. | **Resolvido (05/08/2026):** regra definida por Michel — assunto sozinho nunca descarta. Filtros de assunto removidos da spec. As 5 threads voltam para NÃO_FILTRADAS. | ✅ |
| 2 | 05/08/2026 | 2 — Remetente | `"'Facebook' via Suporte" <suporte@finaud.com.br>` | Notificações do Facebook chegavam via grupo suporte@ sem Reply-To. O filtro de endereço não capturava porque o endereço era suporte@finaud.com.br. 3 threads afetadas. | **Resolvido (05/08/2026):** filtro de nome do remetente adicionado à spec (§4 — "Por nome do remetente"). Facebook, Instagram, LinkedIn e similares são descartados pelo nome antes do passo do Reply-To. | ✅ |
| 3 | 05/08/2026 | 1 — Filtros | `"Atualização programada - Pontofopag"` (employer.com.br), `"Convite PwC"` (content.pwc.com) e outros | 22 threads de newsletters e serviços externos (Grafana, PwC, Epays/Pontofopag, AppSheet, Freshworks, TIEXAMES, Nasajon) passavam pelo filtro porque o critério não cobria domínios — só endereços e padrões. | **Resolvido (05/08/2026):** varredura completa de todos os 46 domínios externos identificados. 7 domínios de serviços adicionados como novo critério "Domínio do remetente" no §4. Filtro consolidado em quadro único. | ✅ |

---

## Decisões tomadas durante a simulação

Mudanças na spec que surgirem durante a análise são registradas aqui antes de serem gravadas no documento mestre.

| # | Data | Decisão | Seção afetada | Registrada na spec? |
|---|---|---|---|---|
| 1 | 05/08/2026 | Assunto sozinho nunca descarta — filtragem é só pelo remetente | §7 Campo 5 | ✅ |
| 2 | 05/08/2026 | Redes sociais via suporte@ filtradas pelo nome do remetente (não pelo endereço) | §4 + §7 Campo 1 Passo 4 | ✅ |
| 3 | 05/08/2026 | Suporte@ sem Reply-To e sem nome: classifica normalmente, campo responsável fica em branco | §7 Campo 1 | ✅ |
| 4 | 05/08/2026 | PCAM (Posição de Câmbio / CAM0050) = parte do fluxo DDR_2011 — não é categoria nova | §10 DDR_2011 | ✅ |
| 5 | 05/08/2026 | FogBugz filtrado por combinação nome FINAUDTEC + assunto FogBugz | §4 filtros | ✅ |
| 6 | 05/08/2026 | §4 consolidado em quadro único com novo critério: Domínio do remetente (7 domínios de serviços externos) | §4 | ✅ |

---

## Referências da spec por passo

| Passo | Seção | O que consultar |
|---|---|---|
| 1 — Filtros | §7 Campo 1 (lista de filtros) + Campo 5 (filtros por assunto) | Endereços exatos, padrões bloqueados, filtros de assunto |
| 2 — Remetente | §7 Campo 1 → Campo 4 | Regra do suporte@, Reply-To, assinatura como fallback |
| 3 — Destinatário | §7 Campo 2 + Campo 3 | Finaud no Para ou CC, identificação do cliente |
| 4 — Classificação | §10 Catálogo de categorias + §11 Exemplos reais | Palavras-chave, anexos, padrões de assunto por categoria |
| 5 — Status | §8 Regras de classificação das threads | Última mensagem de quem? Texto conclusivo? Protocolo STA? |
| 6 — Cobertura | §10 + §3 As 12 categorias | Comparar categorias encontradas com as 12 previstas |
