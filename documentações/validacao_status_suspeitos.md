# Validação de Status — Tela E-mails: Classificação e Status

**Gerado em:** 11/09/2026 16:34
**Protocolo completo:** `documentações/PENDENCIAS.md` → seção "VALIDAÇÃO — Tela E-mails"

---

## Estado do trabalho

| Bloco | O que é | Estado |
|---|---|---|
| Bloco 1 | Levantamento automático dos suspeitos | ✅ Concluído (11/09/2026) |
| Bloco 2 | Revisão com Michel — um caso por vez | ✅ Concluído (11/09/2026) |
| Bloco 3 | Correção no banco + registro + commit | ✅ Concluído (11/09/2026) |

---

## Resumo do levantamento

| Universo | Qtd |
|---|---|
| Threads Aguardando Finaud (ativas) | 145 |
| Threads Aguardando Cliente (ativas) | 27 |
| Threads Concluídas (ativas no banco) | 492 |
| Threads sem status (ativas) | 364 |
| **Suspeitos encontrados** | **22** |

---

## Legenda

⬜ aguarda Michel · ✅ correto (falso alarme) · ❌ erro corrigido no Bloco 3 · ✅* correto (já corrigido pelo recálculo anterior)

---

## Tipo A — Aguardando Finaud — mas Finaud enviou por último
> Status = Aguardando Finaud, mas a última mensagem foi enviada por alguém da Finaud. Provavelmente deveria ser Aguardando Cliente.

**Total: 21**

| # | Assunto | Categoria | Último remetente | Data | Decisão |
|---|---|---|---|---|---|
| 1 | 📢 Atualização Bacen – RISCOS – 26/08/2026 | SUPORTE | contato@finaud.com.br | 26/08/2026 | ❌ movida para bloqueadas |
| 2 | ⚠️ Garantia leiautes FALHOU — 26/08/2026 | SUPORTE | contato@finaud.com.br | 26/08/2026 | ❌ movida para bloqueadas |
| 3 | Relatório do Serviço - Finaud Moedas  26/08/2026 1… | SUPORTE | riskdriver@finaud.com.br | 26/08/2026 | ❌ movida para bloqueadas |
| 4 | Relatório do Serviço - Finaud Master  26/08/2026 0… | SUPORTE | riskdriver@finaud.com.br | 26/08/2026 | ❌ movida para bloqueadas |
| 5 | COLUNA - ENVIAR CADOC 08/09/2026. | SALDOS_CONTABEIS_DIARIOS_4111 | Monica Macedo <monica.macedo@finaud.com.… | 10/09/2026 | ✅ correto (AF) |
| 6 | PI Exposure MiraeAsset Securities in Brazil_HK - 2… | DDR_2011 | "Sarah Sá" <suporte@finaud.com.br> | 10/09/2026 | ✅* Concluída via recálculo |
| 7 | Re: Pasta Activetrades | DDR_2011 | fernando souza <fernando.souza@finaud.co… | 09/09/2026 | ✅ correto (Concluída) — campo "Para" vazio investigar em outro chat |
| 8 | Erro no DLI e DLO | DLO_2061 | Andrea Inacio <andrea.inacio@finaud.com.… | 09/09/2026 | ❌ AF → AC corrigido |
| 9 | DDR 2011 - 03/09/2026 Segue a remessa | DDR_2011 | "Sarah Sá" <suporte@finaud.com.br> | 09/09/2026 | ✅* Concluída via recálculo |
| 10 | Re: Arquivo 2061 e 2062 | DLO_2061 | Andrea Inacio <andrea.inacio@finaud.com.… | 09/09/2026 | ✅ correto (AF) |
| 11 | 4111 - dia 31/08/2026, 01 a 08/09/2026 | SALDOS_CONTABEIS_DIARIOS_4111 | Miguel Santos <suporte@finaud.com.br> | 09/09/2026 | ✅* AC via recálculo |
| 12 | 4010, 4060 e planilha LEC. | DLO_2061 | Miguel Santos <suporte@finaud.com.br> | 09/09/2026 | ✅* AC via recálculo |
| 13 | Erro cálculo do DDR | DDR_2011 | suporte@finaud.com.br | 09/09/2026 | ❌ AC → AF corrigido (aviso de leitura mal interpretado) |
| 14 | 4010, 4060 e planilha LEC. | DLO_2061 | Miguel Santos <suporte@finaud.com.br> | 08/09/2026 | ✅* AC via recálculo |
| 15 | Re: LEC Julho 2026. Segue o DLO (2061) e o DLI (20… | DLO_2061 | Andrea Inacio <andrea.inacio@finaud.com.… | 08/09/2026 | ✅ correto (AF — prometeu retornar) |
| 16 | PI Exposure MiraeAsset Securities in Brazil_HK - 2… | DDR_2011 | Andrea Inacio <andrea.inacio@finaud.com.… | 08/09/2026 | ✅* Concluída via recálculo |
| 17 | Wise DDR 01.09 | DDR_2011 | "Sarah Sá" <suporte@finaud.com.br> | 08/09/2026 | ❌ AC → Concluída corrigido pelo Fix W |
| 18 | Sistema com erro | SALDOS_CONTABEIS_DIARIOS_4111 | Rodrigo Tiberio <rodrigo.tiberio@finaud.… | 08/09/2026 | ❌ AC → Concluída corrigido |
| 19 | Relatórios DLO 2061, DLI 2062 e DRM 2060- 08/2026 | DLO_2061 | Miguel Santos <suporte@finaud.com.br> | 04/09/2026 | ✅* AC via recálculo |
| 20 | 4111 - dia 31/08/2026 e 01/09/2026 | SALDOS_CONTABEIS_DIARIOS_4111 | Miguel Santos <suporte@finaud.com.br> | 04/09/2026 | ✅* AC via recálculo |
| 21 | Erro Cálculo PR - Fourtrade | SUPORTE | suporte <suporte@finaud.com.br> | 04/09/2026 | ✅ correto (AF — prometeu retornar) |

---

## Tipo B — Aguardando Cliente — mas cliente enviou por último
> Status = Aguardando Cliente, mas a última mensagem foi enviada pelo cliente. Provavelmente deveria ser Aguardando Finaud.

**Total: 1**

| # | Assunto | Categoria | Último remetente | Data | Decisão |
|---|---|---|---|---|---|
| 1 | DLO JULHO | DLO_2061 | "'Luiza Ferreira Milet' via Suporte" <su… | 09/09/2026 | ✅ correto (AF — Monica precisa ver o DLO) |

---

## Tipo C — Concluída — mas cliente enviou algo recente (últimos 60 dias)
> Thread marcada como Concluída, mas o cliente enviou a última mensagem nos últimos 60 dias. Pode ter sido reaberta sem atualização de status.

**Total: 0**

*Nenhum caso encontrado.*

---

## Tipo D — Remetente vazio
> Campo remetente_ultima_msg está vazio — não é possível cruzar com o status automaticamente.

**Total: 0**

*Nenhum caso encontrado.*

---

## Tipo E — Sem status definido (ativas)
> Threads ativas que não têm status_workflow definido (campo = None/NULL).

**Total: 364**

| # | Assunto | Categoria | Último remetente | Data |
|---|---|---|---|---|
| 1 | Muse Code is now out of beta to help you scale you… | — | "'Meta for Developers' via Suporte" <sup… | 31/08/2026 |
| 2 | 📢 Atualização Bacen – RISCOS – 31/08/2026 | — | contato@finaud.com.br | 31/08/2026 |
| 3 | Relatório do Serviço - Finaud Moedas  31/08/2026 1… | — | riskdriver@finaud.com.br | 31/08/2026 |
| 4 | Relatório do Serviço - Finaud Master  31/08/2026 0… | — | riskdriver@finaud.com.br | 31/08/2026 |
| 5 | 📢 Atualização Bacen – RISCOS – 31/07/2026 | — | contato@finaud.com.br | 31/07/2026 |
| 6 | 📢 Atenção: Atualização na página de Leiautes do Ba… | — | contato@finaud.com.br | 31/07/2026 |
| 7 | Relatório do Serviço - Finaud Moedas  31/07/2026 1… | — | riskdriver@finaud.com.br | 31/07/2026 |
| 8 | Relatório do Serviço - Finaud Master  31/07/2026 0… | — | riskdriver@finaud.com.br | 31/07/2026 |
| 9 | Relatório do Serviço - Finaud Moedas  30/08/2026 1… | — | riskdriver@finaud.com.br | 30/08/2026 |
| 10 | Relatório do Serviço - Finaud Master  30/08/2026 0… | — | riskdriver@finaud.com.br | 30/08/2026 |
| 11 | FogBugz (Caso 8552) RISK DRIVER - ALTERAÇÃO/CORREÇ… | — | — | 30/07/2026 |
| 12 | Your AI blueprint: From adoption to ROI | — | — | 30/07/2026 |
| 13 | Seu plano de IA: da adoção ao ROI | — | — | 30/07/2026 |
| 14 | 📢 Atualização Bacen – RISCOS – 30/07/2026 | — | contato@finaud.com.br | 30/07/2026 |
| 15 | 📢 Atenção: Atualização na página de Leiautes do Ba… | — | contato@finaud.com.br | 30/07/2026 |
| 16 | See what's next at Meta Connect 🔜 Sept 23-24 | — | — | 30/07/2026 |
| 17 | Relatório do Serviço - Finaud Moedas  30/07/2026 1… | — | riskdriver@finaud.com.br | 30/07/2026 |
| 18 | Relatório do Serviço - Finaud Master  30/07/2026 0… | — | riskdriver@finaud.com.br | 30/07/2026 |
| 19 | Imersão gratuita: EXIN AI Essentials - com foco em… | — | — | 30/06/2026 |
| 20 | Relatório do Serviço - Finaud Moedas  29/08/2026 1… | — | riskdriver@finaud.com.br | 29/08/2026 |
| ... | *(+ 344 mais)* | | | |