# Especificação — Nova Arquitetura do Oráculo 360
**Versão:** 2.0  
**Data:** 28/07/2026  
**Status:** Em desenvolvimento ativo — Fase 0 concluída (19 tipos documentados); Fase 1 aguarda conclusão dos campos 6, 7 e 8

---

## Índice

| § | Seção |
|---|---|
| 1 | Por que estamos fazendo isso |
| 2 | O que o sistema faz |
| 3 | As 10 categorias de e-mail e seus fluxos |
| 4 | Quem usa e para quê |
| 5 | Como o sistema é construído (as 3 peças) |
| 6 | Onde roda |
| 7 | Ganho principal e risco principal |
| 8 | Plano de implantação por fases |
| 9 | Decisões tomadas e justificativas |
| 10 | Mapeamento de campos do e-mail (Campos 1–8) |
| 11 | Regras de classificação das threads |
| 12 | Modelo de rastreamento — duas camadas |
| 13 | Telas do sistema |
| 14 | Catálogo de categorias — o que a IA precisa saber |
| 15 | Exemplos reais de threads (T01–T19) |
| 16 | Padrões observados para guiar a IA |
| A | Apêndice A — Colaboradores Finaud identificados |

---

## 1. Por que estamos fazendo isso

O sistema atual funciona, mas é difícil de manter — são 16 scripts que dependem uns dos outros, rodam só na máquina do Michel, e qualquer mudança exige cuidado para não quebrar outra coisa. A nova arquitetura resolve isso: lê os e-mails direto do Gmail, usa IA para entender e classificar, e roda em servidor permanente acessível pela equipe.

### Como os e-mails são lidos

Via **Gmail API direta** — o protocolo oficial do Google para sistemas acessarem caixas de e-mail. Não via Gmail MCP.

**Por que API e não MCP:**  
O Gmail MCP é uma ferramenta que o Claude usa durante o desenvolvimento para consultar e-mails no chat (construir o catálogo, verificar casos reais). Ele entrega campos limitados — por exemplo, não expõe o campo Reply-To, que é necessário para identificar o remetente real quando o e-mail passa pelo grupo `suporte@finaud.com.br`.

A Gmail API direta entrega todos os campos do e-mail (From, To, CC, Reply-To, Subject, corpo, anexos, Thread ID etc.) e já está funcionando no projeto — o `coletor_teste.py` usa exatamente essa abordagem.

> **Decisão confirmada por Michel (22/07/2026):** o sistema usará Gmail API direta para leitura dos e-mails em produção. O Gmail MCP continua disponível como ferramenta de análise durante o desenvolvimento.

---

## 2. O que o sistema faz

### Funcionalidades obrigatórias

| # | O que faz | Detalhes |
|---|---|---|
| F1 | Lê todas as threads do Gmail | Conecta direto na caixa, sem coleta dia a dia |
| F2 | Classifica por categoria regulatória | DDR, DLI, DRM, DLO, S5, etc. — automático via IA |
| F3 | Detecta de qual lado está a thread | Aguardando ação da Finaud ou do cliente |
| F4 | Rastreia prazos | Regras do calendário regulatório (reutilizar as que já existem) |
| F5 | Lê texto de imagens (OCR) | Para entender prints de tela e documentos enviados como imagem |
| F6 | IA que aprende dos casos | Após a thread ser resolvida, vira conhecimento consultável |

### O que está fora do escopo
- Integração com sistema interno da Finaud (cálculo, geração de CADOC)
- Anotações manuais — tudo que importa está no e-mail
- Comunicação por outros canais (WhatsApp, telefone)

---

## 3. As 12 categorias de e-mail e seus fluxos

O sistema trata 12 categorias distintas de e-mail. Cada categoria tem suas próprias regras, prazo regulatório e fluxo — o que a IA precisa saber sobre cada uma está no §14 (Catálogo de categorias) e os exemplos reais estão no §15.

| Categoria | O que é | Frequência | Prazo | Quem entrega ao BACEN |
|---|---|---|---|---|
| DDR 2011 | Documento Diário de Posições — posições financeiras do cliente ao final do dia | Diária | D+3 úteis | Cliente (após Finaud gerar) |
| SCD 4111 | Saldo Contábil Diário — lançamentos nas contas COSIF | Diária | D+3 úteis | Cliente (após Finaud gerar) |
| DRM 2060 | Demonstrativo de Risco de Mercado | Mensal | D+5 úteis do mês seguinte | Cliente (após Finaud gerar) |
| DLO 2061 | Demonstrativo de Limites Operacionais | Mensal | Dia 5 do 2º mês seguinte | Cliente (após Finaud gerar) |
| DLI 2062 | Demonstrativo de Limites Operacional Individual | Mensal | Dia 5 do 2º mês seguinte | Cliente ou Finaud diretamente |
| DRL 2160 | Demonstrativo de Risco de Liquidez ("Colchão de Liquidez") | Mensal | D+10 úteis do mês seguinte | Cliente (após Finaud gerar) |
| S5 | Resultado Quantitativo de Risco — Segmento 5 | Mensal | D+5 úteis | Não vai ao BACEN |
| RETORNO_BACEN | Críticas e rejeições do BACEN a entregas anteriores | Conforme ocorrência | Urgente — prazo do BACEN | Não se aplica |
| SUPORTE | Apoio, dúvidas, acesso a sistemas, comunicação geral | Conforme ocorrência | Conforme urgência | Não se aplica |
| FORCAPITAL | Ferramenta de projeção de capital — serviço da Finaud | Conforme ocorrência | D+5 úteis | Não vai ao BACEN |
| DRSAC 2030 | Demonstrativo de Responsabilidade em Soluções de Aplicações em Crédito | Semestral (jun e dez) | 10º DU do 2º mês após a data-base | Cliente (Finaud orienta/responde) |
| PVCA 6209 | Elaboração e Remessa de Informações Relativas a Pagamentos de Varejo e a Canais de Atendimento | Trimestral | Último DU do mês seguinte ao fim do trimestre | Cliente — via STA |

> **Nota:** um e-mail pode conter mais de uma categoria (ex.: "DDR + DRM + DLI de março"). O sistema rastreia cada entrega separadamente — ver §12 (Modelo de rastreamento, duas camadas).

---

## 4. Quem usa e para quê

| Usuário | O que usa | Para quê |
|---|---|---|
| Michel | Painel principal | Acompanhar prazos, ver o que está aguardando ação |
| Equipe (futuro) | Painel + IA assistente | Ver threads por cliente, consultar histórico |
| Novo colaborador | IA assistente | Aprender o que foi feito em cada cliente sem depender de quem saiu |

**Escala:** ~50 threads/semana, ~100 clientes ativos

---

## 5. Como o sistema é construído (as 3 peças)

Em vez de 16 scripts, três peças:

### Peça 1 — Leitor de e-mails
Conecta no Gmail da Finaud e lê todas as threads relevantes. **Processa continuamente** — quando chega um e-mail novo, o sistema o processa automaticamente, sem Michel precisar passar uma data ou acionar o sistema manualmente. Substitui os Scripts 01 a 09 do pipeline atual.

> **Decisão confirmada por Michel (22/07/2026):** o sistema deve monitorar o Gmail continuamente e processar cada e-mail novo à medida que chega — diferente do sistema atual onde Michel passava uma data e o sistema coletava só daquele dia.

### Peça 2 — Classificador (IA)
Para cada thread, a IA entende: qual categoria, de qual lado está, qual é o prazo, se há imagens com contexto importante. Usa as regras de prazo que já existem no sistema atual. Substitui os 10 supervisores de triagem com regras escritas à mão.

### Peça 3 — Painel + IA assistente
Tela web acessível por qualquer membro da equipe. A IA assistente responde perguntas como *"como resolvemos o erro VCRD0007 com a Banvox em maio?"*. Evolui o painel atual (Flask).

### OCR de imagens
Continua existindo — necessário porque muitos erros do BACEN chegam como print de tela. Roda quando a thread é aberta (não em lote como hoje).

### Prazos
As regras de prazo já existem no sistema atual (arquivo JSON). Serão reutilizadas — nada precisa ser reescrito.

---

## 6. Onde roda

Servidor em produção — acessível pela equipe a qualquer hora, sem depender do computador do Michel estar ligado. (Diferente do sistema atual que roda em localhost:5000.)

---

## 7. Ganho principal e risco principal

**Ganho:** em vez de manter 10 supervisores com regras escritas à mão (que quebram quando aparece caso novo), a IA classifica — e se aparecer um caso nunca visto, ela ainda consegue entender.

**Risco:** IA pode errar em casos ambíguos.  
**Solução:** ela classifica, mas Michel (ou a equipe) pode corrigir com um clique — e a correção vira aprendizado para casos futuros.

---

## 8. Plano de implantação por fases

| Fase | Nome | O que acontece | Status |
|---|---|---|---|
| **0** | Catálogo de tipos | Olhar Gmail real e mapear todos os tipos de e-mail que aparecem | **Em validação** — 19 tipos documentados em §15; T04 aguarda confirmação de Michel |
| **1** | Protótipo | Construir as 3 peças com dados reais, sem IA ainda | Aguardando |
| **2** | Validação | Michel testa: o que o sistema classificou está certo? | Aguardando |
| **3** | IA | Ligar a IA assistente com os casos validados | Aguardando |
| **4** | Histórico | Importar casos anteriores do sistema atual para a IA aprender | Aguardando |
| **5** | Produção | Publicar em servidor, liberar para a equipe | Aguardando |

### Como a Fase 0 foi feita

**Método:** leitura direta de 25+ threads reais da caixa `oraculo@finaud.com.br` via Gmail MCP (ferramenta de análise e desenvolvimento). Cada thread foi documentada com 8 dimensões:

| Dimensão | O que foi registrado |
|---|---|
| **Categoria** | Tipo exato — DDR_2011, DLO_2061, DRM_2060, DLI_2062, S5, RETORNO_BACEN, SUPORTE, FORCAPITAL, etc. |
| **Iniciador** | Quem abriu a thread: nome, e-mail e empresa |
| **Fluxo completo** | Cada mensagem em ordem: data/hora · quem enviou · ação concreta |
| **O que a Finaud fez** | Ações concretas: qual colaborador, o que fez, em que momento |
| **Como está resolvido** | Sinal concreto de encerramento (protocolo STA, agradecimento, entrega de arquivo) |
| **Timing total** | Duração da thread — da primeira à última mensagem |
| **Timing por lado** | Quanto tempo ficou aguardando a Finaud · aguardando o cliente |
| **Participantes** | Cliente: nome + e-mail + empresa · Colaborador Finaud: nome + e-mail |

**Resultado:** 19 tipos documentados (T01–T19). Os tipos T18 e T19 são filtrados automaticamente pelo sistema — não chegam à triagem. T04 (Western Union) aguarda confirmação de Michel sobre o papel exato da Finaud no fluxo.

**O que esta base permite depois:**
- Identificar quais clientes enviam mais e-mails (por empresa e por contato individual)
- Ver qual colaborador Finaud é mais solicitado
- Entender onde o tempo fica represado (Finaud ou cliente)
- Calcular tempo médio por categoria de resolução
- Usar como base de exemplos para treinar e guiar a IA classificadora

Este catálogo é o guia de todas as fases seguintes — não avançar para a Fase 1 sem T04 confirmado.

---

## 9. Decisões tomadas e justificativas

| Decisão | Justificativa |
|---|---|
| Leitura direta do Gmail (sem pipeline) | Elimina 16 scripts e a complexidade de orquestração |
| IA classifica em vez de regras à mão | Mais robusto a casos novos; menos manutenção |
| OCR mantido | Muitos erros do BACEN chegam como imagem |
| Prazos reutilizados do JSON atual | Já testados e corretos; não precisa reescrever |
| Servidor em produção | Equipe precisa de acesso independente da máquina do Michel |
| Histórico só depois dos testes | Não contaminar o aprendizado da IA com dados não validados |
| Fora do escopo: sistema interno e anotações | Foco no rastreamento de comunicação — o resto é separado |
| Gmail API direta (não Gmail MCP) | MCP não expõe Reply-To — necessário para identificar remetente real quando e-mail passa pelo grupo suporte@ |
| Processamento contínuo | Sistema monitora o Gmail e processa cada e-mail novo automaticamente, sem acionamento manual |
| CC não utilizado pelo sistema | CC serve só para ciência — não determina quem age; De e Para já cobrem todos os cenários mapeados |

---

## 10. Mapeamento de campos do e-mail

Como cada campo do e-mail será lido e usado pelo sistema. Campos mapeados um por um com simulação em dados reais antes de documentar.

---

### Campo 1 — From/Sender (Remetente)

O campo `From` não é sempre o remetente real. Quando o e-mail passa pelo grupo `suporte@finaud.com.br`, o Google substitui o `From` original pelo endereço do grupo. A solução é usar o campo `Reply-To` — que preserva o endereço original — como fonte primária.

**Regra de identificação — cenários encontrados na caixa real:**

| Valor do From | Exemplo real | Quem é | O que fazer |
|---|---|---|---|
| `*@finaud.com.br` | `andrea.inacio@finaud.com.br` | Colaborador Finaud | Usar direto — cobre automaticamente novos colaboradores, sem cadastrar |
| `*@finaudtec.com.br` | `luiz.antonio@finaudtec.com.br` | Colaborador Finaud (segunda empresa) | Usar direto |
| `suporte@finaud.com.br` | `suporte@finaud.com.br` | Grupo compartilhado | Verificar Reply-To: (1) fora da Finaud → cliente é o remetente real; (2) dentro da Finaud → colaborador Finaud é o remetente real; (3) vazio → Finaud via grupo, colaborador não identificado |
| `riskdriver@finaud.com.br` | `riskdriver@finaud.com.br` | Sistema automático (Risk Driver) | Filtrar |
| `contato@finaud.com.br` | `contato@finaud.com.br` | Sistema automático (alertas BACEN) | Filtrar |
| `coleta.oraculo@finaud.com.br` | `coleta.oraculo@finaud.com.br` | Conta de coleta | Ignorar |
| Qualquer outro domínio | `risco@brazabank.com.br` | Cliente | Usar direto |

**Cenários teóricos (não encontrados na varredura, mas possíveis):**

| Valor do From | Situação | O que fazer |
|---|---|---|
| `comunicacao.bcb.gov.br` | BACEN enviando notificação diretamente | Filtrar |
| `noreply@...` ou `no-reply@...` | Sistema automático externo | Filtrar |
| `mailer-daemon@...` | E-mail rejeitado/devolvido (bounce) | Filtrar |
| `newsletter@...`, `notification@...`, `bounce@...` | Automático de qualquer domínio | Filtrar |
| `do-not-reply@finaud.fogbugz.com` | FogBugz (sistema de tickets da Finaud) | Filtrar |
| From vazio | E-mail sem remetente identificado | Filtrar |

> **Nota de implementação:** as regras de filtro acima já estão implementadas no `coletor_teste.py` (variáveis `SPAM_DOMINIOS` e `SPAM_ADDR_SUBSTRINGS`). O novo sistema deve replicar essa lógica. Novos colaboradores Finaud **não precisam ser cadastrados** — qualquer endereço `@finaud.com.br` ou `@finaudtec.com.br` é tratado como Finaud automaticamente.

**Exemplos reais (simulação em 50 threads, 22/07/2026):**

| From observado | Reply-To | Remetente real identificado | Correto? |
|---|---|---|---|
| `andrea.inacio@finaud.com.br` | — | Finaud — Andrea Inácio | ✅ |
| `sarah.sa@finaud.com.br` | — | Finaud — Sarah Sá | ✅ |
| `luiz.antonio@finaudtec.com.br` | — | Finaud — Luiz Antonio | ✅ |
| `suporte@finaud.com.br` | `psilveira@planner.com.br` | Cliente — Paulo Henrique (Planner SCD) | ✅ |
| `suporte@finaud.com.br` | vazio | Finaud — alguém enviando pelo grupo (ex.: Sarah Sá) | ✅ |
| `riskdriver@finaud.com.br` | — | Sistema automático → filtrado | ✅ |
| `contato@finaud.com.br` | — | Sistema automático → filtrado | ✅ |
| `risco@brazabank.com.br` | — | Cliente — Braza Bank | ✅ |
| `jessica.silva@banvox.com.br` | — | Cliente — Banvox | ✅ |
| `noesantana@amarilfranklin.com.br` | — | Cliente — Amaril Franklin | ✅ |

> **Decisão confirmada por Michel (22/07/2026):** usar Reply-To como fonte primária quando From = suporte@finaud.com.br. Replicar a mesma lógica do sistema atual (script 05), que já faz isso via campo Reply-To do cabeçalho do e-mail.

---

### Lista completa de filtros do Campo "De"

E-mails que o sistema descarta automaticamente sem processar. No sistema atual esses filtros estão espalhados entre código Python e um arquivo JSON — no novo sistema ficam todos em um lugar só.

> **Nota — tela de gestão de filtros (23/07/2026):** o novo sistema precisará de uma **tela de configuração** onde Michel (ou a equipe) possa adicionar, editar ou remover endereços e assuntos filtrados sem precisar mexer no código. Endereços novos que precisem ser bloqueados (ex.: novo sistema automático, novo comunicado indesejado) devem ser inseríveis pela tela, sem intervenção técnica.

**Filtros por endereço exato:**

| Endereço | Motivo |
|---|---|
| `riskdriver@finaud.com.br` | Risk Driver — sistema automático da Finaud |
| `contato@finaud.com.br` | Alertas BACEN — sistema automático |
| `coleta.oraculo@finaud.com.br` | Conta de coleta do Oráculo 360 |
| `do-not-reply@finaud.fogbugz.com` | FogBugz — sistema de tickets |
| `comunicacao@comunicacao.bcb.gov.br` | BACEN — comunicado automático |

**Filtros por padrão no endereço (qualquer domínio que contenha o texto abaixo):**

| Padrão | Tipo |
|---|---|
| `noreply` | Resposta automática |
| `no-reply` | Resposta automática |
| `donotreply` | Resposta automática |
| `mailer-daemon` | E-mail devolvido (bounce) |
| `maildaemon` | E-mail devolvido (bounce) |
| `newsletter` | Boletim informativo |
| `notificacao` / `notificação` | Notificação automática |
| `notification` | Notificação automática |
| `bounce` | E-mail devolvido |
| `autorespond` | Resposta automática |

**Filtros por assunto (descarta mesmo que o remetente não esteja nas listas acima):**

| Texto no assunto | Motivo |
|---|---|
| `FogBugz` | Notificação de ticket FogBugz |
| `Risk Driver -` | Relatório automático Risk Driver |
| `Atualização na página de Leiautes do Bacen` | Comunicado automático BACEN |
| `Atualização Bacen` | Comunicado automático BACEN |
| `ATENÇÃO: ATUALIZAÇÃO NA PÁGINA DE LEIAUTES DO BACEN` | Comunicado automático BACEN |
| `Relatório do Serviço - Finaud` | Relatório interno automático |
| `Atualização de Comunicados e Normativos` | Comunicado interno |
| `FinaudTec LEC` | Comunicado interno |
| `FINAUD MASTER` | Comunicado interno |
| `INFORMATIVO` | Comunicado interno |
| `LOG DE PROCESSAMENTO` | Log automático de sistema |
| `SUCESSO NA IMPORTAÇÃO` | Log automático de sistema |
| `STAY AHEAD` | Newsletter externa |
| `M4D-NEWSLETTER` | Newsletter externa |

**Outros casos sempre filtrados:**

| Situação | O que fazer |
|---|---|
| Campo "De" vazio | Filtrar — sem remetente identificado |

---

### Campo 2 — To (Destinatários)

Lista de endereços do campo "Para:" do e-mail. Usado junto com o From para determinar a direção da comunicação e identificar o e-mail do cliente quando a Finaud está enviando.

**Regra para extrair o cliente do campo To:**
1. Remover todos os endereços Finaud (`@finaud.com.br`, `@finaudtec.com.br`)
2. O que sobrar = endereços do cliente
3. Se sobrar vazio → o cliente está só no CC ou BCC — verificar CC em seguida
4. Se sobrar múltiplos domínios **diferentes** → thread com mais de uma empresa envolvida — registrar todos, a IA determina o principal

**Cenários encontrados na caixa real (simulação em 50 threads, 22/07/2026):**

| # | Situação | De (endereço real) | Para (endereço real) | O sistema identifica | Quem age | Por que |
|---|---|---|---|---|---|---|
| C1 | Cliente enviando para a Finaud via grupo | `risco@brazabank.com.br` | `suporte@finaud.com.br` | Cliente: Braza Bank | `suporte@finaud.com.br` | Único endereço Finaud no Para; responde pelo grupo |
| C2 | Cliente enviando direto para pessoa específica | `pedro.silva@accredito-scd.com.br` | `pedro.silva@finaud.com.br`, `andrea.inacio@finaud.com.br` | Cliente: Accredito SCD | `pedro.silva@finaud.com.br` + `andrea.inacio@finaud.com.br` | Dois colaboradores receberam; thread fica para os dois — quem responder primeiro vira responsável |
| C3 | Cliente copiando grupo e pessoa | `jessica.silva@banvox.com.br` | `suporte@finaud.com.br`, `andrea.inacio@finaud.com.br` | Cliente: Banvox | `andrea.inacio@finaud.com.br` | Colaborador específico tem prioridade sobre suporte@ (grupo não é uma pessoa) |
| C4 | Finaud respondendo ao cliente | `andrea.inacio@finaud.com.br` | `guilherme.marin@guru.com.vc` | Cliente: Guru CTVM | `guilherme.marin@guru.com.vc` | Finaud já agiu; o cliente no Para é quem precisa responder |
| C5 | Finaud se copiou mas incluiu o cliente no Para | `andrea.inacio@finaud.com.br` | `andrea@finaud.com.br`, `victor@miraeinvest.com.br` | Cliente: Mirae Invest | `victor@miraeinvest.com.br` | Andrea se copiou, mas copiou o cliente também — quem age é o cliente |
| C6 | Cliente se copiou mas incluiu a Finaud no Para | `wu@wu.com` | `wu1@wu.com`, `wu2@wu.com`, `suporte@finaud.com.br` | Cliente: WU (múltiplos contatos) | `suporte@finaud.com.br` | WU se copiou, mas copiou o suporte@ — quem age é a Finaud |
| C7 | Notificação automática ou relay interno | `suporte@finaud.com.br` | `suporte@finaud.com.br` | Sem cliente — filtrar | — | E-mail enviado para si mesmo; sem destinatário externo — descartado |
| C8 | Reply-all com múltiplos parceiros de empresas diferentes | `suporte@finaud.com.br` | `contato@tc.com.br`, `op@ignis.com.br`, `andrea@finaud.com.br` | Múltiplas empresas — IA determina principal | IA determina | Empresas diferentes no Para; IA identifica qual é o cliente principal da thread |
| C9 | Mensagem interna Finaud → Finaud | `sarah.sa@finaud.com.br` | `suporte@finaud.com.br`, `miguel.santos@finaud.com.br` | Mensagem interna — entra na thread | `miguel.santos@finaud.com.br` | Thread interna não é ignorada: entra como contexto para a IA e para o histórico |
| C10 | Cliente se comunicando; Finaud só observa (está no CC) | `victor@miraeinvest.com.br` | `rafael@miraeinvest.com.br` | Cliente: Mirae Invest (identificado pelo CC) | `rafael@miraeinvest.com.br` | Finaud está só no CC (observando); o destinatário do Para é quem age |

**Cenários teóricos (não encontrados, mas possíveis):**

| # | Situação | O que fazer |
|---|---|---|
| T1 | To = `coleta.oraculo@finaud.com.br` (alguém enviando direto para nossa conta) | Tratar como C1 — Finaud recebendo |
| T2 | To vazio (e-mail enviado só com BCC) | Identificar destinatário pelo corpo; se não encontrar, filtrar |
| T3 | To = `riskdriver@` ou `contato@` | Filtrar — enviando para sistema automático |

> **Decisão confirmada por Michel (22/07/2026):** novos colaboradores Finaud não precisam ser cadastrados — qualquer `@finaud.com.br` é identificado como Finaud automaticamente, tanto no From quanto no To. Melhoria em relação ao sistema atual que mantém lista manual de COLABORADORES.

---

### Campo 3 — CC (Cópia)

> **Decisão (24/07/2026):** o CC **não será utilizado** pelo sistema.
>
> O CC serve apenas para "ciência" — quem está copiado está observando, não é o destinatário principal. Ele não afeta nenhuma regra de direcionamento nem determina quem age a seguir. De e Para já são suficientes para identificar o cliente e definir o status da thread em todos os cenários mapeados. O campo é lido pela Gmail API mas descartado antes das regras.

---

### Campo 4 — Reply-To (Remetente real)

Quando alguém envia por um grupo (como `suporte@finaud.com.br`), o campo De mostra o grupo — não a pessoa. O Reply-To revela quem realmente enviou: é o "endereço de resposta real".

**Regra de uso:** o Reply-To só importa quando **De = `suporte@finaud.com.br`**. Em todos os outros casos (De já é um endereço específico), o Reply-To é ignorado pelo sistema.

| # | De | Reply-To | Para | O sistema faz | Quem age |
|---|---|---|---|---|---|
| R1 | `suporte@finaud.com.br` | `risco@brazabank.com.br` | `andrea.inacio@finaud.com.br` | Remetente real = cliente (Braza Bank) | `suporte@finaud.com.br` — Thread nova: sem responsável até alguém assumir. Thread existente: herda `andrea.inacio@finaud.com.br` (último colaborador que respondeu) |
| R2 | `suporte@finaud.com.br` | `andrea.inacio@finaud.com.br` | `risco@brazabank.com.br` | Remetente real = Andrea (Finaud) | `risco@brazabank.com.br` — Finaud (Andrea) já agiu; cliente responde |
| R3 | `suporte@finaud.com.br` | vazio | `risco@brazabank.com.br` | Remetente = Finaud via grupo, colaborador não identificado | `risco@brazabank.com.br` — Finaud agiu via grupo; cliente responde |
| R4 | `andrea.inacio@finaud.com.br` | qualquer | `risco@brazabank.com.br` | Reply-To ignorado — De já é claro | `risco@brazabank.com.br` — Regra normal do Campo 1; De é quem define |
| R5 | `suporte@finaud.com.br` | `suporte@finaud.com.br` | `suporte@finaud.com.br` | Mesmo que R3 — grupo enviou para si mesmo | — (filtrar) — Sem cliente externo; e-mail descartado |
| R6 | `suporte@finaud.com.br` | `luiz.antonio@finaudtec.com.br` | `risco@brazabank.com.br` | Mesmo que R2 — `@finaudtec.com.br` é domínio Finaud | `risco@brazabank.com.br` — Finaud (finaudtec) já agiu; cliente responde |
| R7 | `suporte@finaud.com.br` | `riskdriver@finaud.com.br` | `risco@brazabank.com.br` | Reply-To ignorado — endereço filtrado. Tratar como R3 | `risco@brazabank.com.br` — Finaud agiu via grupo; cliente responde |

**Regra de atribuição de responsável (R1 — thread nova):**
Quando o cliente envia para `suporte@` e não há colaborador identificado no Reply-To, a thread entra como "Aguardando Finaud — sem responsável". O responsável é registrado no momento em que um colaborador responde. Se for uma thread existente com histórico, o sistema herda o colaborador da última mensagem Finaud.

---

### Campo 5 — Assunto

**Problema que resolve:** identificar qual categoria regulatória é este e-mail (DDR, DLO, DRM, 4111, Suporte, Retorno Bacen etc.). O prazo será tratado na Seção 2 — Conceitos Derivados, que combina assunto + corpo + regra da categoria.

**Método de classificação:** IA. As regras abaixo são instruções para a IA — não são código regex.

**Filtros:** não há filtro por assunto. Exclusões são feitas pelo Campo 1 (De/remetente).

| O assunto contém | Exemplo real | Categoria | Confiança |
|---|---|---|---|
| Código explícito: DDR, DRM, DLO, DLI, DRL, 4111 (ou: 2011, 2060, 2061, 2062, 2160) | "Emissão DDR 02/07/2026" / "DRM junho" / "Doc 4111" | Conforme o código | Alta — usar sem ir pro corpo |
| "Balancete de Câmbio" | "Posição de Câmbio CAM0050, Balancete de Câmbio PDF/Excel" | DDR 2011 | Alta |
| "indício", "rejeitado", "arquivo rejeitado" | "DRM 30 06 2026 - ENTREGUE E REJEITADO" | Retorno Bacen | Alta |
| "Norma BCB", "instrução normativa", "IN BCB" | "RES: Norma BCB - Risco de Liquidez e LCR" | Suporte | Alta |
| S5 (palavra isolada) | "ECSA (S5) - COS4010 ..." | S5 | Alta |
| Dois CADOCs juntos | "DLO \| DLI - Referente a MAI.2026" | Ambíguo — ler o corpo | Baixa |
| Termos de conteúdo sem código explícito | "Guru CTVM: Informações Diárias" / "Saldos do dia 29 e 30/06" / "COS 4010" | IA infere com contexto do e-mail | Média |
| Sem pista | "Re: SUPORTE - FINAUD - INTRA INVESTIMENTOS" | Desconhecido — ler o corpo | Nula |

> **Por que IA e não regex:** o regex atual falha em ~30% dos casos onde o cliente não coloca o código no assunto ("Informações Diárias", "TVM", "COS 4010"). A IA, seguindo as instruções desta tabela, cobre esses casos com contexto. Simulação confirmada em 23 threads do histórico real (24/07/2026).

---

### Campo 6 — Corpo (texto da mensagem)

**Para que serve:** é o texto que a IA lê para decidir o status de cada thread.

---

#### O que o Gmail entrega

**Passo 1 — Formato de entrega**
O Gmail entrega o corpo do e-mail no campo `body` em dois formatos:
- HTML (maioria — e-mails enviados por pessoas)
- Texto puro (minoria — sistemas automáticos)

**Passo 2 — Conversão**
O sistema converte o `body` para texto puro:
- Se veio HTML → converte para texto puro
- Se veio texto puro → usa direto

Resultado sempre: texto puro.

**Passo 3 — O que o texto puro contém**
Junto com a mensagem real, podem aparecer os seguintes elementos:

| Elemento | O que é |
|---|---|
| Assinatura | Texto do remetente ao final da mensagem ("Att, Lucas / Finaud") |
| Histórico citado (`>`) | Replies anteriores da thread copiados no corpo |
| Histórico encaminhado (`---`) | Conteúdo de e-mails anteriores colado ao encaminhar |
| Rodapé automático | Texto gerado automaticamente por sistemas (ex: Google Groups) |
| Marcador de imagem | Referência no lugar onde havia uma imagem |

**Sobre imagens:**
O Gmail não coloca o conteúdo visual da imagem no texto — coloca um marcador. O arquivo da imagem existe separado, acessível se necessário.

Formatos de marcador identificados até agora:
- `[image: nome_do_arquivo]`
- `[cid:identificador]`
- Outros formatos possíveis — a confirmar na Fase 2

---

#### O que utilizaremos e Regras de negócio

> ⚠️ **Pendente — a definir após análise das 12 categorias (Fase 2, iniciada 30/07/2026)**
>
> A Fase 2 identificará, por categoria, quais elementos do Passo 3 aparecem e com que frequência, e definirá as regras de limpeza: o que remover, o que manter, o que encaminhar para revisão humana.

---

### Campo 7 — Anexos

> ⚠️ **PENDENTE — aguardando simulações de threads reais**
>
> Os nomes e tipos de anexo por categoria já estão parcialmente mapeados em §14 (Catálogo de categorias). O que falta definir nas simulações:
> - Como tratar e-mails com muitos anexos ou ZIP dentro de ZIP?
> - Quando o nome do anexo é suficiente para identificar a categoria sem ler o corpo?
> - Quais anexos precisam de OCR e quando acioná-lo?
> - Limite de tamanho para processamento?

---

### Campo 8 — Thread ID e Data

> ⚠️ **PENDENTE — aguardando simulações de threads reais**
>
> **Questões a responder:**
> - Como o Thread ID do Gmail se relaciona com o histórico de aprendizado da IA?
> - Como tratar threads de canal (0,3% do total — mesma thread reutilizada por meses)?
> - Data de referência regulatória: usar a data do e-mail ou a data mencionada no corpo/assunto?
> - Como registrar a data de competência (referência do CADOC) separada da data do e-mail?

---

## 11. Regras de classificação das threads

Como o sistema decide se uma thread está **Aguardando Finaud**, **Aguardando Cliente** ou **Concluída**. Regras confirmadas por Michel (23/07/2026) com base no motor de triagem atual.

A classificação olha sempre o **último e-mail da thread** — não o histórico completo. Isso garante que o status reflita sempre o estado atual, não o estado passado.

---

### 11.1 Aguardando Finaud

O caso está com a Finaud — ela precisa agir.

| Situação | Exemplo |
|---|---|
| Último e-mail é do cliente para a Finaud | Cliente enviou dados, perguntou algo, mandou documento |
| Último e-mail é interno (Finaud → Finaud) | Andrea encaminhou para Monica cuidar — ainda não foi para o cliente |

---

### 11.2 Aguardando Cliente

O caso está com o cliente — ele precisa agir.

| Situação | Exemplo |
|---|---|
| Último e-mail é da Finaud para o cliente | Finaud respondeu, pediu algo, enviou arquivo |
| Último e-mail é de cliente para cliente | Cliente repassa internamente sem responder à Finaud |

---

### 11.3 Concluída

O caso foi encerrado. As regras abaixo são as mesmas para todos os tipos de e-mail (DDR, SCD, DLO, DLI, DRM, S5, SUPORTE, RETORNO_BACEN, FORCAPITAL, DRSAC, PVCA).

**Quando o último e-mail é da Finaud para o cliente:**

| Situação | O que isso significa na prática |
|---|---|
| Texto do fio menciona "transmitido no BACEN" | O CADOC foi entregue ao BACEN — caso encerrado |
| Finaud enviou o arquivo ao cliente (remessa) | Enviou o DDR, DLO, DRM etc. ao cliente para transmissão |
| Finaud respondeu com "RES:" no assunto | Resposta formal da Finaud ao caso |
| Finaud enviou texto de encerramento | Linguagem conclusiva: "segue em anexo", "conforme solicitado", "procedemos com..." |

**Quando o último e-mail é do cliente para a Finaud:**

| Situação | O que isso significa na prática |
|---|---|
| Cliente agradeceu após ação da Finaud | "obrigado", "muito obrigado" — sem novo pedido |
| Cliente só confirmou recebimento | E-mail curto de confirmação, sem conteúdo novo |
| Cliente disse "de acordo" | "ok", "de acordo", "concordo" — após instrução da Finaud |

**Veto universal (impede o Concluído mesmo com as regras acima):**
Se após a ação da Finaud o cliente mandou algo com conteúdo real — uma pergunta, um dado novo, uma reclamação — o caso **não fecha**. A bola voltou para a Finaud.

**Regra universal — frases de cortesia após entrega = Concluído (confirmado por Michel, 29/07/2026):**
Se o arquivo foi entregue e a mensagem seguinte — de qualquer colaborador da Finaud ou do cliente — contém apenas frase de cortesia, agradecimento ou assinatura padrão sem novo pedido, a thread é **Concluída**.

| Frases que NÃO reabrem nem bloqueiam o Concluído | Porque |
|---|---|
| "Desde já agradeço e permaneço à disposição" (assinatura do colaborador Finaud) | Encerramento cortês após entrega — não é pedido |
| "Obrigada", "Obrigado", "Valeu", "Perfeito", "Ok", "Recebido" do cliente | Confirmação de recebimento sem conteúdo novo |
| Qualquer frase de fechamento padrão sem pedido explícito | A cortesia não cria pendência |

> Aplica a: todas as 12 categorias.

**Regra adicional exclusiva do RETORNO_BACEN:**

| Situação |
|---|
| Finaud orientou o cliente de forma conclusiva (não apenas enviou arquivo) |
| Cliente confirmou que o BACEN aceitou o protocolo |

---

### 11.4 Reabertura de caso

Caso estava Concluído → cliente manda nova mensagem → caso volta automaticamente para **Aguardando Finaud**.

O sistema não precisa "lembrar" que estava concluído — a lógica do último e-mail já cuida disso: se o último e-mail é do cliente, o caso é Aguardando Finaud.

> **Decisão confirmada por Michel (23/07/2026).**

---

## 12. Modelo de Rastreamento — duas camadas

**Decisão confirmada por Michel (27/07/2026)**

O sistema rastreia dois conceitos distintos:

### Camada 1 — E-mail (comunicação)
O e-mail é o veículo. A IA lê tudo: De, Para, Assunto, Corpo, Anexo. Este registro existe para o histórico de aprendizado — a IA sabe o que foi enviado, por quem, em que contexto.

### Camada 2 — Entregas regulatórias (rastreamento)
Cada categoria mencionada no e-mail gera um item independente de rastreamento com seu próprio prazo e ciclo de vida.

**Exemplo:**
```
E-mail: "Segue DDR, DRM e DLI - MIRAE março/2026"
    └── Entrega DDR_2011 | competência 31/03/2026 | prazo D+3             | entregue
    └── Entrega DRM_2060 | competência 31/03/2026 | prazo D+5 mês seguinte | entregue
    └── Entrega DLI_2062 | competência 03/2026    | prazo dia 5 seg. mês   | entregue
```

**Ciclo de vida de cada entrega:**
> entregue → crítica recebida → substituição enviada → concluído

**Por que este modelo:**
Um e-mail que entrega DDR + DRM + DLI não pode ser forçado em uma única categoria sem perder rastreabilidade dos outros dois. Com duas camadas, a IA aprende o fluxo completo (entregas, críticas, substituições, suporte) e a Finaud tem controle individual de cada obrigação regulatória.

**Impacto na classificação:**
A saída da IA deixa de ser "este e-mail É DDR" e passa a ser "este e-mail CONTÉM: DDR_2011 + DRM_2060". O Catálogo de Categorias (§14) continua válido — o que muda é que a saída é uma lista, não um valor único.

---

## 13. Telas do sistema

### Tela 1 — Painel Operacional

Lista de threads ativas, organizada por prazo, com destaque visual:

| Cor | Urgência | Critério |
|---|---|---|
| 🔴 Urgente | Vence em até 3 dias | |
| 🟡 Atenção | Vence em até 7 dias | |
| 🟢 Normal | Mais de 7 dias | |

Cada linha mostra: **cliente · categoria · lado (Finaud/cliente) · prazo · última mensagem**

### Tela 2 — Gestão de Filtros (Remetente)

Tela de configuração onde Michel (ou a equipe) pode adicionar, editar ou remover endereços e assuntos filtrados sem precisar de intervenção técnica. Ver lista completa de filtros em §10 (Campo 1).

> **Decisão confirmada por Michel (23/07/2026).**

---

## 14. Catálogo de categorias — o que a IA precisa saber

Esta seção alimenta diretamente o prompt da IA. Para cada categoria, a IA recebe: o que é, como reconhece no e-mail (assunto + corpo + histórico da thread) e qual prazo aplicar.

**Referência de prazos:**

| Categoria | Prazo |
|---|---|
| DDR 2011 | D+3 úteis após a data de referência |
| 4111 | D+3 úteis após a data de referência |
| DRM 2060 | D+5 úteis do mês seguinte à data de referência |
| DLO 2061 | Dia 5 do segundo mês seguinte à data de referência |
| DLI 2062 | Dia 5 do segundo mês seguinte à data de referência |
| DRL 2160 | D+10 úteis do mês seguinte à data de referência |
| S5 | D+5 úteis após a data de referência |
| Retorno Bacen | D+3 úteis após a data do e-mail |

---

### 4111 — Saldos Contábeis Diários

**O que é:** documento que registra os lançamentos nas contas contábeis da instituição a cada dia útil, baseado no plano COSIF (sistema de contas contábeis das instituições financeiras do Banco Central). O relatório de conglomerado (consolidação de todas as empresas do grupo) usa o mesmo formato e CADOC, mas é enviado mensalmente.

**Frequência:** diária — enviado todo dia útil.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "4111", "CADOC 4111", "saldos diários", "saldos do dia" | Alta |
| Assunto | Nome do cliente + data, sem código explícito | Média |
| Corpo | Planilhas de saldos por conta COSIF, lançamentos contábeis diários | Média |
| Anexo | `CADOC 4111.xlsx`, `DOC_4111_YYYYMMDD.xlsx` | Alta |
| Anexo | `CNPJ_4111_YYYYMMDD_I_1.zip` (CADOC gerado — Finaud entrega ao cliente) | Muito alta |

> ⚠️ "conglomerado" no assunto sozinho não identifica o CADOC — pode aparecer em DDR, DLO, DLI e outros. A IA deve buscar contexto adicional (corpo, histórico da thread) para confirmar.

**O que NÃO é:**
- Não é DDR — 4111 é posição contábil, DDR é posição de mercado e câmbio
- Não é DLO/DLI — os arquivos COS4010, COS4016, COS4060 e COS4066 (XML mensais) pertencem ao DLO e DLI, não ao 4111
- Criptoativos não entram no 4111 — têm classificação própria

**Fluxo típico:**
1. Cliente envia planilha de saldos do dia à Finaud — "Segue saldos do dia 29 e 30/06" (`Saldos 4111.xlsx`)
2. Finaud importa, processa e gera o CADOC 4111 (ZIP: `CNPJ_4111_DATA.zip`)
3. Finaud entrega o ZIP ao cliente via e-mail
4. Cliente transmite ao BACEN

**Prazo:** D+3 úteis após a data de referência

**Regras de classificação — Aguardando ou Concluído:**

As mesmas 5 regras do DDR_2011. Sinais específicos do SCD_4111:

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou o arquivo 4111 ao cliente — OU cliente respondeu com agradecimento sem novo pedido | Concluído | — |
| R2 | Cliente enviou dados, retificação, fez pergunta ou trouxe nova demanda — e Finaud ainda não respondeu | Aguardando | Finaud |
| R3 | Finaud fez pedido ao cliente ou cobra dado/confirmação e aguarda resposta | Aguardando | Cliente |
| R4 | Finaud acusou recebimento mas ainda não gerou nem entregou o arquivo | Aguardando | Finaud |
| R5 | Última mensagem foi interna da Finaud (de um colaborador para outro) sem resposta ao cliente | Aguardando | Finaud |

**R1:** "segue arquivo Cadoc 4111", "seguem arquivos Cadoc's 4111", "segue anexo relatório 4111", "para envio ao BC"; anexo `CNPJ_4111_*.zip` pela Finaud; agradecimento puro do cliente ("Obrigada Lucas!", "Ok, recebido")

**R2:** "Segue em anexo arquivos com informações para envio do CADOC 4111"; Excel de saldos ou posições enviado pelo cliente

**R3:** "Por gentileza enviar o anexo", "peço a gentileza de quando tiver a disponibilidade das informações", "encaminhar as posições do 4111"

**R4:** "Ok, obrigada pelo envio", "Obrigada. Administração", "Estamos verificando com a área técnica... Retornaremos em breve"

---

### DDR 2011 — Documento Diário de Posições

**O que é:** documento que agrega várias posições financeiras do cliente ao final de cada dia útil. Não é um tipo único de dado — é uma consolidação de diferentes instrumentos, todos enviados diariamente para a Finaud.

**O que compõe o DDR:**
- Títulos e Valores Mobiliários (TVM)
- Depósitos à Vista
- Compromissadas e Custódia
- Ações e Opções (cadastro diário)
- Posição de Câmbio / Balancete de Câmbio (CAM0050)
- LFTs (Letras Financeiras do Tesouro)
- Renda Fixa / Exposição contábil
- PI Exposure (posição de portfólio — clientes específicos como Mirae)

**Frequência:** diária — enviado todo dia útil.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DDR", "2011" | Alta |
| Assunto | "TVM", "Dep a Vista", "Compromissada", "Custódia", "Balancete de Câmbio", "CAM0050", "LFT", "PI Exposure" | Alta |
| Assunto | "posição diária", "remessa", nome do cliente + data | Média |
| Corpo | Posições financeiras do dia anterior, referências a CAM0050, valores em diferentes instrumentos | Média |
| Anexo | `RD_MOEDA.csv`, `RD_LFT.xlsx`, `RD_PREFIXADA.xlsx` (prefixo `RD_` — padrão dominante) | Alta |
| Anexo | `DDR_YYYYMM.xlsx`, `Operacoes compromissadas SCD.xlsx` | Alta |
| Anexo | `CNPJ_2011_YYYYMMDD.zip` (CADOC gerado — Finaud entrega ao cliente) | Muito alta |

**O que NÃO é DDR:**
- Não é DLO — DDR é diário, DLO é mensal (balanço patrimonial)
- Não é DRM — DRM é sobre risco de mercado, também mensal
- Não é 4111 — 4111 é saldo contábil diário (aparece junto com o DDR em alguns clientes, mas é documento separado)

**Fluxo típico:**
1. Cliente envia dados do dia à Finaud — planilhas de posição (`RD_MOEDA.csv`, balancetes, TVM) — "Segue em anexo arquivo com informações para envio do DDR"
2. Finaud processa e gera o CADOC DDR (ZIP: `CNPJ_2011_DATA.zip`)
3. Finaud entrega o ZIP ao cliente — "Segue em anexo a remessa DDR (2011) para encaminhar ao BACEN"
4. Cliente transmite ao BACEN — alguns confirmam: "DDR referente a 30.06.2026 transmitido no BACEN"

**Prazo:** D+3 úteis após a data de referência

**Regras de classificação — Aguardando ou Concluído:**

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud enviou o DDR em anexo, confirmou envio ao BACEN, resolveu ação interna — OU cliente respondeu só com agradecimento sem novo pedido | Concluído | — |
| R2 | Cliente enviou dados, retificação, fez pergunta ou trouxe nova demanda — e Finaud ainda não respondeu | Aguardando | Finaud |
| R3 | Finaud fez pedido ao cliente ou cobra dado/confirmação e aguarda resposta | Aguardando | Cliente |
| R4 | Finaud acusou recebimento mas ainda não processou nada | Aguardando | Finaud |
| R5 | Última mensagem foi interna da Finaud (de um colaborador para outro) sem resposta ao cliente | Aguardando | Finaud |

**Sinais detalhados de cada regra:**

**R1 — Concluído:**
- Corpo: "Segue em anexo o DDR", "Segue anexo para envio ao BC", "Enviados ao BACEN", "Disponibilizo os protocolos"
- Corpo: "O cadastro está disponível", "Já foi preenchido", "Já foi resolvido" (ação interna — sem arquivo)
- Anexo `DDR_YYYYMM.xlsx` ou `CNPJ_2011_YYYYMMDD.zip` enviado pela Finaud
- Sub-caso: Finaud transmitiu o DDR ao BACEN diretamente em nome do cliente — protocolo de aceite = R1
- Última mensagem do cliente é agradecimento puro ("Obrigado", "Recebi", "Perfeito", "Ok") sem novo pedido

**R2 — Aguardando Finaud:**
- Cliente enviou extratos ou planilhas (prefixo `RD_`, PDF, Excel de saldos)
- Cliente enviou versão corrigida/retificada dos dados
- Cliente fez pergunta ou dúvida e aguarda resposta da Finaud
- Cliente trouxe nova demanda após ciclo anterior concluído

**R3 — Aguardando Cliente:**
- Corpo Finaud: "Por gentileza enviar", "Poderia confirmar", "Ainda não recebi", cobrança de prazo
- Finaud entregou o DDR e fez pedido no mesmo e-mail → R3 (o pedido pendente prevalece sobre a entrega)
- ⚠️ Se o cliente respondeu "obrigado" sem entregar o que foi pedido → ainda é R3 (agradecimento ≠ entrega)

**Armadilha importante:**
- DDR Concluído nem sempre tem arquivo — confirmação de ação interna ("O cadastro está disponível") também é R1

---

### DRM 2060 — Demonstrativo de Risco de Mercado

**O que é:** relatório mensal que mede o quanto a instituição está exposta a riscos de variações de mercado — taxas de juros, câmbio, preços de ativos. Parecido com o DDR, mas mensal: a data de referência é sempre o **último dia útil do mês**.

**Frequência:** mensal — base: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DRM 2060", "DRM (2060)", "DRM2060_MMAAAA", "2060 DRM", "Documento 2060", "SMM - 2060" | Alta |
| Assunto | "DRM" + mês/ano | Alta |
| Corpo | Relatório de risco de mercado, exposição a taxas, VaR (valor em risco) | Média |
| Anexo | `Saldos DRM.xlsx`, `DRM_2060_Finaud_YYYYMM.xlsx` | Alta |
| Anexo | `CNPJ_2060_YYYYMMDD.zip` (CADOC gerado — Finaud entrega ao cliente) | Muito alta |
| Anexo | `SALDOS BANCOS.pdf`, `CAIXA.pdf`, `SELIC.xls` | Baixa — genérico, não identifica |

**O que NÃO é DRM 2060:**
- "COMUNICACAO DE INCONSISTENCIA NO DRM - 2060" → é **RETORNO_BACEN** (o BACEN rejeitou um DRM anterior)
- "RELATORIO DRM - Amaril Franklin" → pode ser **DLO** (é a planilha LEC usada para gerar o DLO)
- DRM + DDR no mesmo assunto → registrar ambos (ver §12 — modelo de duas camadas)

**Fluxo típico:**
1. Cliente envia dados mensais à Finaud — planilha "Saldos DRM" — "Segue a base de dados para geração do DRM"
2. Finaud processa e gera o CADOC DRM (ZIP: `CNPJ_2060_DATA.zip`)
3. Finaud entrega o ZIP ao cliente via e-mail
4. Cliente transmite ao BACEN — alguns confirmam: "DRM referente a JUNHO/2026 transmitido no BACEN"

**Prazo:** D+5 úteis do mês seguinte à data de referência

**Regras de classificação — Aguardando ou Concluído:**

Validado em 90 threads reais (29/07/2026). Cobertura: 100% (57 F→C + 33 C→F).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou o DRM ao cliente ou transmissão ao BACEN confirmada — OU cliente respondeu com agradecimento sem novo pedido | Concluído | — |
| R2 | Cliente enviou dados mensais, prévia ou retificação — e Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda extratos, saldos ou arquivo que o cliente ainda não enviou | Aguardando | Cliente |
| R4 | Finaud enviou análise técnica, explicação ou pergunta (sem entrega de arquivo) — aguarda retorno do cliente | Aguardando | Finaud |
| R5 | Não se aplica — nenhuma thread F→F identificada no DRM_2060 | — | — |

**R1:** "segue anexo a remessa DRM (2060)", "segue o DRM (2060)", "DRM_2060 para transmissão ao BACEN", "transmitido ao BACEN"; agradecimento puro do cliente após entrega

**R2:** cliente enviou saldos/posições/extratos mensais; cliente enviou "prévia" para validação antes da versão final; cliente enviou retificação

**R3:** "encaminhar os extratos", "aguardo o balancete", Finaud pediu dado que ainda não chegou

**R4:** Finaud respondeu pergunta técnica; Finaud agendou reunião com cliente ou BACEN; Finaud esclareceu erro — aguarda retorno

**Sub-padrão "Prévia":** quando o cliente envia rascunho dos dados para Finaud validar antes da versão oficial → R2 (Aguardando/Finaud) até a entrega do DRM definitivo.

**Sub-padrão convite de reunião** (Teams, calendário): R2 (Aguardando/Finaud) — Finaud precisa participar.

**Sub-padrão cliente transmite ao BACEN por conta própria** e avisa a Finaud via C→F → R1 (Concluído) — informacional, nenhuma ação da Finaud necessária.

---

### DLO 2061 — Demonstrativo de Limites Operacionais

**O que é:** relatório mensal sobre os limites regulatórios da instituição — concentração por contraparte, adequação de capital (Basileia) e outros indicadores. O cliente envia à Finaud os quatro arquivos COSIF (**COS4010.xml**, **COS4016.xml**, **COS4060.xml**, **COS4066.xml**) mais a planilha **LEC** (`.xls`/`.xlsx`). A Finaud processa e gera o CADOC, entregando-o ao cliente, que transmite ao BACEN. Em alguns casos a Finaud entrega diretamente.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DLO", "DLO 2061", "2061", "DLO/DLI" | Alta |
| Assunto | "COS 4010", "COS4010", "Planilha LEC", "Indicadores de Basiléia" | Alta |
| Assunto | "Balancete" + mês/ano, nome do cliente + mês/ano | Média |
| Corpo | Balancete patrimonial, concentração por contraparte, limites de Basileia, planilha LEC | Média |
| Anexo | `COS4010.xml`, `COS4016.xml`, `COS4060.xml`, `COS4066.xml` + `LEC_MMAAAA.xls/xlsx` (do cliente) | Alta — LEC junto com COSIFs confirma DLO |
| Anexo | `CNPJ_2061_YYYYMMDD.zip`, `Cos4010.zip`, `Cos4016.zip` (CADOC gerado) | Muito alta |

**O que NÃO é DLO 2061:**
- "RELATORIO DRM - AMARIL FRANKLIN" → pode ser DLO (esse cliente envia a LEC junto com e-mails de DRM — verificar anexo para confirmar)
- "ECSA (S5) - COS4010..." → é **S5** (código S5 no assunto prevalece sobre a menção ao COS4010)
- "Colchão de Liquidez" / "DRL" → é **DRL 2160**, não DLO — podem vir no mesmo e-mail, registrar separado
- COS4060, COS4066 → pertencem ao **DLI 2062**, não ao DLO
- DLO + DLI no mesmo e-mail → registrar ambos (§12 — modelo de duas camadas)

**Fluxo típico:**
1. Cliente envia `COS4010.xml` + planilha LEC à Finaud — "Seguem 4010 e planilha LEC, para que seja gerado o DLO"
2. Pode haver troca de mensagens sobre ajustes ou metodologia antes de finalizar
3. Finaud processa e gera o CADOC DLO (ZIP: `CNPJ_2061_DATA.zip`)
4. Finaud entrega o ZIP ao cliente via e-mail
5. Cliente transmite ao BACEN — alguns confirmam: "Transmitido o DLO referente a MAI/2026"

**Prazo:** Dia 5 do segundo mês seguinte à data de referência

**Regras de classificação — Aguardando ou Concluído:**

Validado em 482 threads reais (29/07/2026). Cobertura: 100%. Mesmas regras R1–R4 dos CADOCs anteriores. R5 não se aplica (nenhum F→F identificado).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou o DLO ao cliente ou transmissão ao BACEN confirmada — OU cliente agradeceu sem novo pedido | Concluído | — |
| R2 | Cliente enviou COSIF, planilha LEC ou ambos — e Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda COSIF, planilha LEC ou dados adicionais do cliente | Aguardando | Cliente |
| R4 | Finaud acusou recebimento, prometeu retorno ou está processando internamente — ainda não entregou o arquivo | Aguardando | Finaud |
| R5 | Não se aplica — nenhum F→F identificado no DLO_2061 | — | — |

**R1:** "Seguem anexos para envio ao Banco Central: DLO2061", "foram aceitos no STA", "segue o protocolo"; agradecimento puro do cliente; cliente avisando transmissão ("Transmitido os DLO e DLI")

**R2:** cliente enviou COSIF (COS4010.xml, COS4016.xml) e/ou planilha LEC; dados corrigidos ou complementares após inconsistência. ⚠️ Cliente pode ter enviado só um dos dois — status AG/Finaud é correto em qualquer caso.

**R3:** "Por gentileza encaminhar o COS4010 e a planilha LEC", "Solicitamos encaminhar o COSIF", "fico aguardando"

**R4:** "Obrigada pelas informações", "Ok, estarei providenciando", "estamos providenciando", atualização de progresso interno, promessa de entrega futura

---

### DLI 2062 — Demonstrativo de Limites Operacional Individual

**O que é:** relatório mensal semelhante ao DLO 2061, mas focado nos limites operacionais de cada instituição individualmente (não do conglomerado). Usa os mesmos quatro arquivos COSIF do DLO (**COS4010.xml**, **COS4016.xml**, **COS4060.xml**, **COS4066.xml**), mas **sem** a planilha LEC. Quando há erro na entrega original, uma **Substituição** é gerada e enviada. A Finaud entrega o CADOC ao cliente, que transmite ao BACEN.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DLI", "DLI 2062", "2062", "DLI2062_MMAAAA" | Alta |
| Assunto | "Segue a remessa DLI", "Preencher as premissas DLI", "Confecção do DLI", "Substituição" + DLI | Alta |
| Assunto | Nome do cliente + mês/ano, sem código explícito | Média |
| Corpo | Adequação de capital, Basileia, limites individuais, referências a COS4060/COS4066, premissas DLI | Média |
| Anexo | `COS4010.xml`, `COS4016.xml`, `COS4060.xml`, `COS4066.xml` — sem LEC (LEC é exclusiva do DLO) | Alta |
| Anexo | `CNPJ_2062_YYYYMMDD.zip` (CADOC gerado) | Muito alta |

**O que NÃO é DLI 2062:**
- "Instrução Normativa BCB — Altera o DLI" → alerta regulatório sobre mudança de regra, não é entrega do CADOC — pode caber em SUPORTE
- "Aviso Bacen - DLI" / "Questionamento BACEN" → pode ser **RETORNO_BACEN** — verificar contexto
- DLO + DLI no mesmo e-mail → registrar ambos (§12 — modelo de duas camadas)

**Fluxo típico:**
1. Cliente envia arquivos COSIF (XML) à Finaud — sem a planilha LEC (diferença do DLO)
2. Finaud importa no Risk Driver e calcula os limites individuais
3. Finaud gera o CADOC DLI (ZIP: `CNPJ_2062_DATA.zip`)
4. Finaud entrega o ZIP ao cliente — ou, em alguns casos, transmite diretamente ao BACEN
5. Cliente transmite ao BACEN

**Prazo:** Dia 5 do segundo mês seguinte à data de referência

**Regras de classificação — Aguardando ou Concluído:**

Validado em 56 threads reais (29/07/2026). Cobertura: 100%. R5 se aplica (3 casos F→F identificados).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou o DLI ao cliente, transmitiu ao BACEN ou orientação foi concluída — OU cliente agradeceu sem novo pedido | Concluído | — |
| R2 | Cliente enviou COSIF, arquivo corrigido ou avisou rejeição do BACEN — e Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda COSIF ou informação complementar do cliente | Aguardando | Cliente |
| R4 | Finaud acusou recebimento ou equipe técnica está processando internamente — ainda não entregou o arquivo | Aguardando | Finaud |
| R5 | Última mensagem foi interna da Finaud (encaminhamento para colega) sem resposta ao cliente | Aguardando | Finaud |

**R1:** "segue anexo a remessa DLI (2062)", "seguem anexos DLIs 2062", "para envio ao BC", "seguem os protocolos dos arquivos enviados e aceitos pelo BACEN"; agradecimento puro do cliente; cliente confirmando envio ao STA

**R2:** cliente enviou COSIF (XML); cliente avisou "deu rejeitado" (Finaud precisa investigar e regenerar); cliente enviou arquivo corrigido

**R3:** "por gentileza enviar os arquivos COS4010.xml", "poderia nos repassar a mensagem da crítica mencionada?"

**R4:** "Ok, ciente", "Obrigada, vamos verificar", "a equipe técnica está providenciando os ajustes, retornaremos em breve", "o cronograma segue conforme planejado"

**R5:** mensagem encaminhada internamente — instrução normativa repassada à equipe, dúvida urgente do cliente encaminhada para colega responsável

**Nota clientes S5:** quando o cliente é segmento S5, o DLI é calculado pelo próprio BACEN com base no COSIF — a Finaud não gera o arquivo. Threads desse tipo são consultivas e não seguem o fluxo padrão acima.

---

### DRL 2160 — Demonstrativo de Risco de Liquidez

**O que é:** relatório mensal que mede o risco de liquidez da instituição — o chamado "Colchão de Liquidez" (quanto de ativos líquidos a instituição mantém para cobrir saídas de caixa em cenário de estresse). O cliente envia à Finaud uma **planilha DRL** (`.xlsx`), que é importada no sistema. A Finaud gera o CADOC e entrega ao cliente, que transmite ao BACEN. Frequentemente entregue junto com o DDR.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DRL", "DRL 2160", "2160", "DRL2160_MMAAAA" | Alta |
| Assunto | "Colchão de Liquidez", "Encaminhar a planilha DRL", "Geração do arquivo Doc. 2160_DRL" | Alta |
| Assunto | "Protocolo DRL2160", nome do cliente + mês/ano | Média |
| Corpo | Colchão de liquidez, risco de liquidez, ativos líquidos, mapeamento COSIF × DRL | Média |
| Anexo | Planilha DRL (`.xlsx`) do cliente | Alta |
| Anexo | `CNPJ_2160_YYYYMMDD.zip` (CADOC gerado) | Muito alta |

**O que NÃO é DRL 2160:**
- "CONGLOMERADO" + DRL → variante do DRL para o conglomerado — ainda é DRL 2160, base de dados maior
- "Substituição" / "CORREÇÃO" + DRL → reentregas normais — ainda é DRL 2160
- "VENCIMENTO HOJE" + DRL → alerta de prazo — ainda é DRL 2160 (urgente)
- DRL + DDR no mesmo e-mail → registrar ambos (§12 — modelo de duas camadas)

**Fluxo típico:**
1. Cliente envia planilha DRL (`.xlsx`) com dados mensais à Finaud
2. Finaud importa, calcula e gera o CADOC DRL (ZIP: `CNPJ_2160_DATA.zip`)
3. Finaud entrega o ZIP ao cliente — "Segue anexo DRL2160 para envio ao Banco Central"
4. Cliente transmite ao BACEN — alguns confirmam: "Arquivo submetido ao BACEN na data de hoje"

**Prazo:** D+10 úteis do mês seguinte à data de referência

**Regras de classificação — Aguardando ou Concluído:**

Validado em 143 threads reais (29/07/2026). Cobertura: 100%. R5 se aplica (2 casos F→F identificados).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou o DRL ao cliente, cliente confirmou envio ao BACEN — OU agradecimento/confirmação sem novo pedido | Concluído | — |
| R2 | Cliente enviou a planilha DRL (`.xlsx`) e Finaud ainda não processou — OU cliente fez pergunta que Finaud precisa responder | Aguardando | Finaud |
| R3 | Finaud aguarda a planilha DRL do cliente — ou solicitou balancete analítico (PDF) complementar | Aguardando | Cliente |
| R4 | Finaud acusou recebimento com mensagem curta ("Ok, ciente", "Obrigada pela informação") sem entregar o CADOC | Aguardando | Finaud |
| R5 | Última mensagem foi encaminhamento interno da Finaud (F→F), sem resposta ao cliente | Aguardando | Finaud |

**R1:** "Segue anexo DRL2160 para envio ao Banco Central", "segue o DRL (2160)", "DRL para transmissão ao BACEN", "Arquivo submetido ao BACEN na data de hoje", "Somente para que fiquem cientes, foi enviado"; agradecimento puro do cliente ou da Finaud após entrega

**R2:** cliente enviou planilha DRL (`.xlsx`) — Finaud ainda não processou; cliente fez pergunta (mensagem C→F sem planilha) — bola na Finaud para responder

**R3:** "por gentileza enviar a planilha DRL", "fico aguardando a planilha", "poderia encaminhar o balancete analítico?"

**R4:** "Ok, ciente", "Obrigada pela informação", "Recebido" — acuse curto sem entrega. ⚠️ R4 é estreito: só para acuses curtos. Promessa de entrega futura ou atualização de andamento → R2 (bola na Finaud).

**R5:** encaminhamento interno — relatório ou dúvida do cliente repassada a colega da Finaud sem resposta ao cliente ainda

⚠️ **Atenção:** quando a última mensagem é uma pergunta do cliente (C→F), o status é R2 (Finaud precisa responder), não R3. R3 só se aplica quando a Finaud falou por último pedindo algo ao cliente (F→C).

---

### S5 — Resultado Quantitativo de Risco (Segmento 5)

**O que é:** relatório de risco gerado pelo sistema **Risk Driver** para instituições classificadas no Segmento 5 (S5) do BACEN — o segmento de menor complexidade regulatória. O cliente envia à Finaud os quatro arquivos COSIF (**COS4010.xml**, **COS4016.xml**, **COS4060.xml**, **COS4066.xml**), que são importados no Risk Driver. A Finaud gera o **Resultado Quantitativo** e entrega diretamente ao cliente.

> ⚠️ **Diferença chave:** o cliente **não envia o S5 ao BACEN** — este relatório fica entre Finaud e cliente. Diferente de todos os outros CADOCs.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "S5", "(S5)", "Risk Driver S5", "Resultado Quantitativo S5", "Demonstrativo S5" | Alta |
| Assunto | "COS4010" + S5, nome do cliente + "S5" + mês/ano | Alta |
| Corpo | "Segmento 5", resultado quantitativo, Risk Driver, COSIFs — combinado com S5 no assunto | Alta |
| Corpo | COSIFs (COS4010/COS4016/COS4060/COS4066) sem "S5" no assunto | Média — verificar contexto (pode ser DLO ou DLI) |
| Anexo | `COS4010.xml`, `COS4016.xml`, `COS4060.xml`, `COS4066.xml` (do cliente) | Alta — com S5 no contexto |
| Anexo | Resultado Quantitativo S5 (PDF ou Excel gerado pelo Risk Driver) | Alta — não tem padrão ZIP com CNPJ |

**O que NÃO é S5:**
- "S5 para S4" / "S4 para S5" → estudo de mudança de categoria prudencial — é **SUPORTE**, não entrega de relatório
- "Senha" / "Acesso ao Risk Driver" → gestão de credenciais — é **SUPORTE**
- COS4010 mencionado sem "S5" no assunto → pode ser **DLO** ou **DLI** — verificar contexto

**Fluxo típico:**
1. Cliente envia COSIF (`COS4010`/`COS4016`) à Finaud
2. Finaud importa no Risk Driver S5 e gera o Resultado Quantitativo (Requerimentos Mínimos S5)
3. Finaud entrega o relatório ao cliente — "Segue o Resultado Quantitativo S5"
4. Fluxo encerra aqui — S5 não vai ao BACEN

**Prazo:** D+5 úteis após a data de referência

**Regras de classificação — Aguardando ou Concluído:**

Validado em 47 threads reais (29/07/2026). Cobertura: 100%. R5 se aplica (5 casos F→F identificados).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou o Resultado Quantitativo S5, concluiu estudo de migração ou enviou acesso — OU cliente agradeceu sem novo pedido | Concluído | — |
| R2 | Cliente enviou COSIF — Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda COSIF do cliente — OU aguarda resposta do cliente em consulta de migração ou dúvida técnica | Aguardando | Cliente |
| R4 | Finaud acusou recebimento do COSIF com mensagem curta — ainda não entregou o relatório | Aguardando | Finaud |
| R5 | Última mensagem foi encaminhamento interno da Finaud (F→F) sem resposta ao cliente | Aguardando | Finaud |

**R1:** "Segue o Resultado Quantitativo S5", "segue o Demonstrativo S5", "segue a apuração dos requerimentos mínimos S5"; estudo de migração concluído (Finaud respondeu todas as dúvidas); senha/acesso enviados; agradecimento puro do cliente após receber o relatório

**R2:** cliente enviou COS4010.xml / COS4016.xml para geração do relatório mensal — Finaud ainda não processou

**R3:** "Solicitamos por gentileza encaminhar o COS4010", "fico aguardando a planilha", "aguardamos retorno sobre o estudo de migração"; cliente não respondeu consulta da Finaud

**R4:** "Ok, recebido, já vou processar", "Obrigada, vou gerar o relatório" — acuse curto sem entregar ainda

**R5:** encaminhamento interno — ex.: "Andrea, por favor importar o COS4010 da Açoriana para o estudo"; dúvida do cliente repassada a colega

⚠️ **Diferença do S5:** o relatório fica entre Finaud e cliente — não vai ao BACEN. A thread conclui quando a Finaud entrega ao cliente, não quando o cliente transmite ao regulador.

---

### SUPORTE — Apoio e comunicação geral

**O que é:** categoria de apoio que cobre toda comunicação que **não é entrega de CADOC** e **não é resposta do BACEN**. Inclui dúvidas, suporte técnico, gestão de acesso a sistemas, reuniões, auditorias, cobranças e onboarding de novos clientes. Não tem prazo regulatório — o prazo depende da urgência de cada solicitação.

**Como a IA reconhece — por eliminação e por sinais:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto e corpo | Nenhum código CADOC (4111, 2011, 2060, 2061, 2062, 2160, S5) identificado | Alta — por eliminação |
| Assunto | "Acesso", "Senha", "Usuário", "Reset", "Bloqueado" | Alta — gestão de acesso |
| Assunto | "Reunião", "Apresentação", "Horário" | Alta — comunicação geral |
| Assunto | "Auditoria", "Análise de sensibilidade" | Alta — revisão externa |
| Assunto | "Boleto", "mensalidade", "contrato" | Alta — cobrança / contrato |
| Assunto | "Dúvida", "Questionamento", "Informações" | Média — confirmar ausência de CADOC |
| Assunto | "- Situação -" + nome de CADOC | Alta — status de processo, não entrega |
| Corpo | Spam / notificações automáticas de sistemas | Baixa — ruído, pode ignorar |

**O que NÃO é SUPORTE:**
- E-mail com código CADOC no assunto e anexo correspondente → é entrega do **CADOC específico**
- "COMUNICACAO DE INCONSISTENCIA" / "REJEIÇÃO" / "CRÍTICA" do BACEN → é **RETORNO_BACEN**
- "S5 para S4" (mudança de categoria prudencial) → é **SUPORTE** — não é entrega de relatório S5

**Fluxo típico:**
1. Cliente envia e-mail com dúvida, pedido de acesso ou solicitação geral
2. Finaud avalia e responde — ou encaminha para a equipe responsável
3. Resolvido quando o cliente confirma ou agradece — sem prazo regulatório

**Prazo:** sem prazo regulatório fixo — depende da urgência da solicitação

**Regras de classificação — Aguardando ou Concluído:**

Validado em 196 threads reais (29/07/2026). Cobertura: 100%. R5 se aplica.

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud resolveu a demanda ("usuário criado", "senha enviada", "problema resolvido") — OU agradecimento puro do cliente após resolução | Concluído | — |
| R2 | Cliente enviou dado, arquivo ou pergunta — Finaud ainda não respondeu | Aguardando | Finaud |
| R3 | Finaud aguarda insumo, dado ou confirmação do cliente | Aguardando | Cliente |
| R4 | Finaud está analisando — respondeu mas sem resolução ainda ("estou verificando", "retornaremos") | Aguardando | Finaud |
| R5 | Última mensagem foi encaminhamento interno da Finaud (F→F) sem resposta ao cliente | Aguardando | Finaud |

**R1:** "O usuário já foi criado", "password foi enviada", "problema resolvido", "arquivo está pronto", "já configuramos"; agradecimento puro do cliente após resolução. ⚠️ Finaud resolver = R1 imediato — não precisa aguardar confirmação do cliente.

**R2:** cliente enviou planilha, arquivo, dados de posição ou fez pergunta — Finaud ainda não processou nem respondeu

**R3:** "por gentileza, poderia retornar com essa informação?", "poderia encaminhar o arquivo?", "precisamos do dado X para continuar"

**R4:** "estou analisando", "vou verificar", "nossa equipe está verificando", "retornaremos em breve"

**R5:** encaminhamento interno para colega da Finaud — ex.: "Márcio, por favor encaminhar o indicador ao cliente"

⚠️ **Filtro obrigatório antes de classificar:** e-mails de spam (Facebook, sistemas automáticos, notificações 3cx) e notificações internas do Risk Driver não entram na triagem SUPORTE — filtrar antes de classificar.

---

### RETORNO_BACEN — Críticas e rejeições do BACEN

**O que é:** situações em que uma entrega regulatória ao BACEN foi rejeitada, criticada ou recebeu um indício de problema de qualidade. O cliente — que recebeu o aviso do BACEN — encaminha o comunicado à Finaud, que investiga, orienta a correção e acompanha até a aceitação pelo BACEN.

**Dois tipos de comunicado (ambos chegam via cliente):**

| Tipo | Como chega | Sinal principal |
|---|---|---|
| Rejeição CRD | Cliente cola ou encaminha o XML de resposta do BACEN no e-mail | Tags `<respostaCRD>`, `<situacao codigo="2">Rejeitado pelo CRD</situacao>`, código VCRD* |
| Indício de Qualidade | Cliente encaminha o comunicado formal do BACEN exigindo correção | Código DLO000xx, DLI000xx etc.; texto "Determinamos a correção e substituição do documento" |

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "ARQUIVO REJEITADO", "ENTREGUE E REJEITADO", "REJEITADO" | Alta |
| Assunto | "INDÍCIO DE PROBLEMA DE QUALIDADE IDENTIFICADO NO DOCUMENTO [número]" | Alta — linguagem do próprio BACEN |
| Assunto | "Erro [CADOC]" (ex.: "Erro DRM") | Alta |
| Assunto | "Indício de Problema Bacen" | Alta |
| Corpo | XML com `<respostaCRD>`, `Rejeitado pelo CRD`, número de protocolo CRD | Muito alta |
| Corpo | Código de erro BACEN: VCRD0007, DLO00020, DLO00024, DLO00075 etc. | Muito alta |
| Corpo | "recebemos um apontamento", "foi rejeitado", "poderiam nos ajudar" | Média |

**O que o sistema extrai de cada thread:**
- Código da crítica (VCRD0007, DLO00020…) e qual CADOC foi criticado (2060, 2061, 2062…)
- Data-base da remessa (MM/AAAA) e número de protocolo CRD
- Prazo que o BACEN deu para correção
- CNPJ da instituição
- O que foi feito passo a passo e o que ainda falta

**Fluxo típico:**
1. BACEN rejeita ou critica a entrega → cliente recebe o aviso
2. Cliente encaminha para suporte@finaud.com.br pedindo orientação
3. Finaud analisa o código de erro
4. Finaud orienta: corrigir o arquivo, reenviar ao BACEN, ou abrir chamado no sistema CRD
5. Cliente corrige e reenvia → BACEN aceita → protocolo de aprovação confirma o fechamento

**CADOCs que podem gerar RETORNO_BACEN:** qualquer CADOC que o cliente entrega ao BACEN — DDR 2011, DLO 2061, DLI 2062, DRM 2060, DRL 2160. O S5 nunca gera RETORNO_BACEN pois não é enviado ao BACEN.

**O que NÃO é RETORNO_BACEN:**
- E-mail perguntando sobre prazo de entrega ao BACEN → é o **CADOC específico** (DDR, DRM, DLO etc.)
- Comunicado regulatório do BACEN sobre mudança de regra ou normativa → é **SUPORTE**
- "Protocolo" ou "Resultado" referindo-se à entrega normal já aceita → é o **CADOC da entrega**

**Prazo:** urgente — o BACEN define prazo curto para correção e substituição do documento.

> ⚠️ **Nota de amostra:** o histórico disponível (sistema de teste) tem apenas 6 threads RETORNO_BACEN. Os padrões documentados são reais, mas a variedade de códigos de crítica crescerá à medida que o histórico de produção for integrado.

**Regras de classificação — Aguardando ou Concluído:**

Validado em 303 threads reais (29/07/2026). Cobertura: 100%. R5 se aplica (4 casos F→F).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou arquivo corrigido ou orientação conclusiva — OU cliente confirmou BACEN aceitou — OU agradecimento puro após resolução | Concluído | — |
| R2 | Cliente encaminhou comunicado do BACEN (rejeição, indício, crítica) e Finaud ainda não respondeu | Aguardando | Finaud |
| R3 | Finaud aguarda insumo do cliente (arquivo, dado, planilha necessária para corrigir) | Aguardando | Cliente |
| R4 | Finaud está analisando o problema — respondeu mas sem entregar ainda ("estou verificando", "retornaremos em breve") | Aguardando | Finaud |
| R5 | Última mensagem foi encaminhamento interno da Finaud (F→F) sem resposta ao cliente | Aguardando | Finaud |

**R1:** "Segue em anexo arquivo corrigido", "foi corrigido", "Providenciamos o recálculo", "arquivo aceito pelo BACEN"; cliente: "O BACEN aceitou", "foi aceito", "STA aceitou", "arquivos submetidos ao BACEN hoje"; agradecimento puro do cliente

**R2:** cliente encaminhou o XML de rejeição CRD, o comunicado de indício de qualidade ou aviso de atraso — Finaud ainda não respondeu

**R3:** "Por gentileza envie o arquivo [CADOC] do período X", "Precisamos da planilha original para verificar", "Aguardamos o COS4010 para regenerar"

**R4:** "Estou analisando...", "Vou verificar...", "Nossa equipe está verificando...", "Retornaremos em breve", "Realizando os ajustes". ⚠️ Mesmo que a mensagem tenha tom positivo, se termina com "retornaremos" ou "estou verificando" → R4, não R1

⚠️ **Exclusivo do RETORNO_BACEN:** cliente confirmar que o BACEN aceitou (C→F) = R1 (Concluído). Nos outros CADOCs, C→F de confirmação só é R1 se for agradecimento. Aqui, confirmação de aceite do BACEN também encerra a thread.

---

### FORCAPITAL — Ferramenta de projeção de capital

**O que é:** serviço da Finaud para planejamento financeiro e projeção de capital. Não é um relatório regulatório do BACEN — não tem código CADOC e não é enviado ao BACEN. O cliente solicita uma projeção ou acesso à ferramenta, e a Finaud prepara e entrega.

**Fluxo típico:**
1. Cliente solicita projeção de capital, acesso à ferramenta, ou tem dúvida
2. Finaud verifica requisitos e prepara a resposta
3. Finaud entrega a projeção (planilha ou PDF) ou credenciais de acesso — ou pede dados adicionais ao cliente

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto ou corpo | "FORCAPITAL", "ForCapital", "For Capital", "For-Capital" (qualquer variação) | Alta |
| Assunto ou corpo | "projeção de capital" | Alta |
| Assunto ou corpo | "projeção" isolado | Média — confirmar que não é projeção de outro relatório |
| Destinatário | suporteforcapital@finaud.com.br | Alta |
| Exemplos reais | "poderia nos enviar a projeção de capital para 36 meses?"; "Acesso ForCapital + credenciais"; "Encaminhamos projeção de capital DEZ/25 a DEZ/28" | — |

**O que NÃO é FORCAPITAL:**
- "projeção" referindo-se a dados regulatórios de Basileia, DLO ou DLI → é **DLO 2061** ou **DLI 2062**
- "projeção" de calendário, prazo ou cronograma → é **SUPORTE**
- Acesso a sistemas regulatórios (Risk Driver, CRD do BACEN) → é **SUPORTE**

**Prazo:** D+5 úteis após a data do e-mail

**Regras de classificação — Aguardando ou Concluído:**

Validado em 30 threads reais (29/07/2026). Cobertura: 100%. Mesmas regras que SUPORTE — R5 se aplica (F→F interno de parecer).

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud entregou a projeção, credenciais de acesso ou respondeu conclusivamente — OU agradecimento puro | Concluído | — |
| R2 | Cliente pediu projeção, acesso ou enviou dado — Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda dados do cliente para montar a projeção | Aguardando | Cliente |
| R4 | Finaud está verificando requisitos ou analisando — sem entrega ainda | Aguardando | Finaud |
| R5 | Encaminhamento interno F→F — ex.: Finaud pedindo parecer interno sobre a projeção | Aguardando | Finaud |

**R1:** "Encaminhamos projeção de capital para DEZ/25 a DEZ/28", "Acesso ForCapital + credenciais enviados"; agradecimento puro do cliente. ⚠️ Finaud pode enviar projeção atualizada sem o cliente pedir — ainda é R1 (Concluído).

**R2:** "poderia nos enviar a projeção de capital para 36 meses?", "preciso de acesso ao ForCapital" — cliente pediu, Finaud ainda não entregou

**R3:** "precisamos dos dados de capital do período X para montar a projeção", "poderia enviar o balanço para calcularmos?"

**R4:** "estou verificando os requisitos", "vou preparar a projeção", "retornaremos em breve"

**R5:** "poderiam me dar um parecer sobre o apontamento?" — encaminhamento interno

---

### DRSAC 2030 — Demonstrativo de Responsabilidade em Soluções de Aplicações em Crédito

**O que é:** relatório regulatório semestral sobre operações de crédito. A Finaud orienta e responde dúvidas — **não gera o arquivo** (diferente de DDR, DLO, DRM). O cliente entrega diretamente ao BACEN.

**Frequência e prazo:**
- Datas-base: posições de fechamento de **junho** e **dezembro**
- Prazo: até o **10º dia útil do 2º mês subsequente** à data-base
  - Base junho → prazo: 10º DU de agosto
  - Base dezembro → prazo: 10º DU de fevereiro

**Sinais de detecção:**
| Sinal | Exemplo | Confiança |
|---|---|---|
| Assunto | "DRSAC", "CADOC 2030", "Demonstrativo 2030" | Alta |
| Corpo | Cliente pergunta se deve enviar / BACEN envia comunicado sobre DRSAC | Alta |
| Contexto | Volume muito baixo — apenas 2 threads desde jan/2026 | — |

**Fluxo típico:**
1. Cliente pergunta se precisa entregar o DRSAC (ou BACEN comunica sobre inconsistência)
2. Finaud analisa e orienta sobre obrigatoriedade e formato
3. Cliente entrega diretamente ao BACEN (sem passar arquivo pela Finaud)

**Cuidado:** um e-mail com "DRSAC rejeitado" + prazo urgente → é **RETORNO_BACEN**, não DRSAC.

**Regras de classificação — Aguardando ou Concluído:**

Validado em 2 threads reais (29/07/2026). Cobertura: 100%. Mesmas regras que SUPORTE — R5 se aplica.

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud orientou, esclareceu ou entregou análise/correção conclusiva — OU agradecimento puro | Concluído | — |
| R2 | Cliente enviou o arquivo DRSAC para análise ou correção — Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda dado, informação ou confirmação do cliente | Aguardando | Cliente |
| R4 | Finaud está analisando — respondeu mas sem conclusão ainda | Aguardando | Finaud |
| R5 | Encaminhamento interno F→F sem resposta ao cliente | Aguardando | Finaud |

**R1:** "O BACEN não exige o DRSAC para sua instituição", "segue a análise corrigida", "orientação concluída"; agradecimento puro do cliente

**R2:** cliente enviou o arquivo DRSAC para Finaud verificar e corrigir. ⚠️ Se o cliente encaminhou comunicado de **rejeição do BACEN** → é **RETORNO_BACEN**, não DRSAC.

**R3:** "precisamos saber o período de referência", "poderia confirmar o CNPJ da instituição?"

**R4:** "estou verificando a obrigatoriedade", "vou analisar o arquivo", "retornaremos em breve"

**R5:** dúvida do cliente repassada internamente para colega da Finaud

---

### PVCA 6209 — Elaboração e Remessa de Informações Relativas a Pagamentos de Varejo e a Canais de Atendimento

**O que é:** relatório regulatório trimestral sobre pagamentos de varejo e canais de atendimento. O cliente transmite via STA ao BACEN.

**Frequência e prazo:**
- Trimestral — datas-base: **31/mar, 30/jun, 30/set, 31/dez**
- Prazo: **último dia útil do mês seguinte ao fim do trimestre**
  - Base 31/mar → prazo: último DU de abril
  - Base 30/jun → prazo: último DU de julho
  - Base 30/set → prazo: último DU de outubro
  - Base 31/dez → prazo: último DU de janeiro

**Sinais de detecção:**
| Sinal | Exemplo | Confiança |
|---|---|---|
| Assunto ou corpo | "CADOC 6209", "6209", "pagamentos de varejo" | Alta |
| Assunto ou corpo | "canais de atendimento" + contexto regulatório | Média |

**Data de referência:** usa a data do trimestre se mencionada no e-mail; caso contrário usa a data do e-mail para inferir o trimestre.

**Cuidado:** volume histórico muito baixo (1 thread documentada). Tratar como SUPORTE se não houver sinal claro de 6209.

**Regras de classificação — Aguardando ou Concluído:**

Volume histórico irrelevante (1 thread documentada, 29/07/2026). Mesmas regras que SUPORTE e DRSAC — R5 se aplica.

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud orientou, esclareceu ou entregou análise/correção conclusiva — OU agradecimento puro | Concluído | — |
| R2 | Cliente enviou o arquivo PVCA para análise ou correção — Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda dado, informação ou confirmação do cliente | Aguardando | Cliente |
| R4 | Finaud está analisando — respondeu mas sem conclusão ainda | Aguardando | Finaud |
| R5 | Encaminhamento interno F→F sem resposta ao cliente | Aguardando | Finaud |

**R2:** cliente enviou o arquivo PVCA para Finaud verificar e corrigir. ⚠️ Se o cliente encaminhou comunicado de **rejeição do BACEN** → é **RETORNO_BACEN**, não PVCA.

⚠️ **Volume baixo:** se o sinal de "6209" não estiver claro no assunto ou corpo, tratar como SUPORTE até confirmar.

---

### Anexos — sinal auxiliar de detecção

O nome do arquivo em anexo é um sinal adicional para a IA. Quando o assunto não tem código explícito, o nome do anexo pode ser decisivo. Padrões abaixo foram **verificados no histórico real**.

| Categoria | Alta confiança — identifica a categoria | Baixa confiança — genérico, não identifica |
|---|---|---|
| DDR 2011 | `RD_MOEDA.csv`, `RD_LFT.xlsx`, `RD_PREFIXADA.xlsx` (prefixo `RD_`); `DDR_YYYYMM.xlsx` | — |
| SCD 4111 | `CADOC 4111.xlsx`, `DOC_4111_YYYYMMDD.xlsx`, `CNPJ_4111_DATA_I_1.zip` | — |
| DRM 2060 | `Saldos DRM.xlsx`, `DRM_2060_Finaud_YYYYMM.xlsx`, `CNPJ_2060_DATA.zip` | `SALDOS BANCOS.pdf`, `CAIXA.pdf`, `SELIC.xls` |
| DLO 2061 | `Cos4010.zip`, `Cos4016.zip` | — |
| DLI 2062 | `CNPJ_2062_YYYYMM_I_1_4010.zip` | — |
| DRL 2160 | planilha DRL (`.xlsx`) do cliente; `CNPJ_2160_YYYYMMDD.zip` (CADOC gerado) | — |

**Padrão transversal — ZIP do CADOC gerado:**  
O padrão `CNPJ_CADOC_DATA.zip` é universal — aparece em todos os CADOCs. O número do CADOC está diretamente no nome do arquivo, tornando-o o sinal de maior confiança quando presente.

**Fluxo padrão:** Finaud gera o CADOC → entrega ao **cliente** → cliente transmite ao BACEN. Em casos menos comuns a Finaud entrega diretamente ao BACEN.

| Categoria | Exemplo de ZIP |
|---|---|
| DDR 2011 | `CNPJ_2011_YYYYMMDD.zip` |
| DRM 2060 | `32648370_2060_20260130.zip` |
| DLO 2061 | `CNPJ_2061_YYYYMMDD.zip` |
| DLI 2062 | `62280490_2062_202602_I_1_4010.zip` |
| DRL 2160 | `CNPJ_2160_YYYYMMDD.zip` |
| 4111 | `32648370_4111_20260219_I_1.zip` |

> **Nota:** os arquivos XML (COS4010.xml, COS4016.xml, COS4060.xml, COS4066.xml) aparecem como **anexo direto** quando o cliente os envia à Finaud. O ZIP do CADOC gerado é o que a Finaud devolve ao cliente (ou envia ao BACEN diretamente).

---

## 15. Exemplos reais de threads (T01–T19)

Exemplos coletados durante a Fase 0 (22/07/2026) com leitura direta de 25+ threads reais da caixa `oraculo@finaud.com.br`. Cada exemplo documenta um tipo de fluxo com mensagens reais, participantes identificados e critério de conclusão.

> **Nota de desenvolvimento:** estes exemplos foram coletados via Gmail MCP (ferramenta de análise, não produção). O campo `sender` da ferramenta de busca pode mostrar `suporte@finaud.com.br` mesmo quando o remetente real é outro — em todos os casos abaixo o corpo do e-mail foi lido para confirmar o remetente real. Em produção, a Gmail API direta (Campo 1 e Campo 4 em §10) resolve isso automaticamente.

> **Sobre os anexos nos exemplos:** os anexos revelam o que está sendo trocado e em qual direção. Arquivo de dados brutos (Excel, CSV, XML) = cliente enviando dados para a Finaud processar. ZIP com remessa BACEN = entrega do CADOC. PDF de comunicação = notificação do BACEN. Sem anexo = dúvida, orientação ou confirmação textual.

---

### T01 — DDR_2011 | Envio diário de dados pelo cliente

**O que é:** cliente envia arquivo com dados financeiros do dia para a Finaud calcular e gerar o DDR, que é o relatório enviado ao BACEN.

**CADOC:** DDR_2011

**Clientes frequentes:** Amaril Franklin, Accredito SCD, Braza Bank, Mirae Asset

**Fluxo completo (exemplo: Amaril Franklin — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 21/07 13:29 BRT | Noe Santana (Amaril Franklin) → Monica Macedo, Pedro Silva, Lucas Vellani | Enviou ZIP `20072026.zip` com arquivo-fonte para emissão do DDR de 20/07/2026 |
| — | — | Finaud (Monica/Pedro/Lucas) | Importa arquivo, gera o DDR no sistema Risk Driver, transmite ao BACEN (sem resposta por e-mail nesta thread — confirmação é via protocolo STA) |

**Variante — Accredito SCD:** envia múltiplos arquivos para composição (inclui balancete COS e planilha de dados), com CC para dois contatos da empresa.

**Variante — Braza Bank:** envia apenas a notificação "DDR referente a [data] transmitido no BACEN" — já fez a transmissão sozinha e avisa a Finaud.

**O que a Finaud fez (com detalhe):**
- Monica/Pedro/Lucas recebe o arquivo
- Importa no sistema Risk Driver
- Sistema calcula o DDR automaticamente
- Finaud gera a remessa (ZIP: `CNPJ_2011_DATA_I_versao.zip`)
- Transmite ao BACEN via STA
- Em geral não há resposta por e-mail — resolução é silenciosa

**Como sabemos que está resolvido:**
- Finaud recebe protocolo de aceite do STA (sistema BACEN)
- Thread sem resposta após o envio do cliente = concluído (Finaud processou internamente)
- Em alguns casos Braza Bank notifica "DDR transmitido" = ele mesmo faz a transmissão

**Participantes:**
- Cliente: Noe Santana | noesantana@amarilfranklin.com.br | Amaril Franklin CTV Ltda
- Finaud: Monica Macedo, Pedro Silva, Lucas Vellani

**Anexos típicos:** ZIP com nome de data (ex.: `20072026.zip`), arquivos XML/Excel com dados financeiros do dia

---

### T02 — DDR_2011 + DRM_2060 | Remessa de substituição

**O que é:** Finaud envia ao cliente remessas corrigidas (DDR e/ou DRM) para o cliente transmitir como versão substituta ao BACEN. Ocorre quando houve inconsistência identificada (manual ou via crítica do BACEN) e o arquivo precisa ser reprocessado.

**CADOC:** DDR_2011 + DRM_2060 (frequentemente enviados juntos)

**Fluxo completo (exemplo: Mirae Asset — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | Anterior | Rafael Nakamura (Mirae) | Enviou COS4016 (balanço contábil de junho/2026) solicitando remessas de substituição |
| 2 | 21/07 11:54 BRT | Andrea Inacio → Rafael Nakamura (CC: William Oliveira, suporte@) | "Obrigada. Seguem anexo as remessas DDR (2011) e DRM (2060) de Substituição a serem transmitidas ao BC para consistência com o balanço contábil (COS4016) junho/2026." |

**O que a Finaud fez:** recebeu o COS4016, identificou necessidade de ajustar DDR e DRM, reprocessou os dois CADOCs e gerou remessas de substituição.

**Como sabemos que está resolvido:** cliente transmite ao BACEN e recebe aceite do STA. Frequentemente não há resposta por e-mail confirmando.

**Participantes:**
- Cliente: Rafael Nakamura | rafael.nakamura@miraeinvest.com.br | Mirae Asset Securities
- Finaud: Andrea Inacio

**Anexos típicos:** ZIPs com remessas de substituição (`CNPJ_2011_DATA_S_versao.zip`, `CNPJ_2060_DATA.zip`)

---

### T03 — DDR_2011 | Comunicação de variação relevante BACEN

**O que é:** BACEN detecta variação relevante no DDR e comunica formalmente ao cliente. Cliente encaminha à Finaud para análise. Finaud verifica e orienta.

**CADOC:** DDR_2011

**Fluxo completo (exemplo: VIS DTVM — 20–21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 20/07 16:16 | BACEN (DESIG/DIRIM/CORIM) → Bruno Machioski (VIS DTVM) | Enviou "BANCO CENTRAL - COMUNICAÇÃO DE VARIAÇÃO RELEVANTE NO DDR - 2011" |
| 2 | 20/07 16:16 | Bruno Machioski → Monica Macedo (CC: Maria Eugenia, suporte@) | Encaminhou o e-mail do BACEN: "Monica, bom dia. Poderia por gentileza verificar a variação indicada." |
| 3 | 21/07 15:05 | Monica Macedo → Bruno (CC: Maria Eugenia, suporte@) | Consultou Risk Driver e perguntou ao cliente sobre ajustes nos períodos 08, 09 e 10 |
| 4 | 21/07 15:46 | Bruno (VIS DTVM) → Monica | "Monica, boa tarde. Obrigado pelas verificações. Darei a tratativa e o andamento por aqui. Muito obrigado." |

**Como sabemos que está resolvido:** cliente responde que vai "dar a tratativa" — confirmação de que recebeu e vai agir.

**Timing:** duração ~23h30 · tempo na Finaud ~22h50 · tempo no cliente ~41 min

**Participantes:**
- Cliente: Bruno Machioski | bruno.machioski@visdtvm.com.br | VIS DTVM
- Finaud: Monica Macedo

---

### T04 — DDR_2011 (câmbio) | Balancete de Câmbio / CAM0050 — distribuição diária pela WU

**O que é:** Jair Bonetti Junior (Western Union Bank) envia diariamente o CAM0050 BACEN e o Balancete de Câmbio para uma lista de distribuição interna da WU — e inclui suporte@finaud.com.br como destinatária. A Finaud **recebe** esse e-mail. O papel exato da Finaud neste fluxo **aguarda confirmação de Michel**.

**CADOC:** DDR_2011 (subcategoria cambial)

**Fluxo completo (exemplo: Western Union — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 21/07 15:42 | Jair Bonetti Junior (WU Accounting) → lista distribuição WU + suporte@finaud.com.br | "Segue Posição de Câmbio do Banco Western Union S/A — CAM0050 BACEN PDF · Balancete de Câmbio PDF e Excel. Apuração realizada até 17/07/2026. Integração realizada até 17/07/2026 — Guia: 1436." |

**Recorrência:** diária (observadas múltiplas datas na mesma semana)

**Participantes:**
- Remetente: Jair Bonetti Junior | jair.bonetti@wu.com | Senior Specialist, Accounting — Western Union Bank
- Finaud (receptora): suporte@finaud.com.br

**Anexos recebidos:** `CAM0050 17 07 2026 - BANCO.pdf`, `BALANCETE 17 07 2026 - BANCO.pdf`, `BALANCETE 17 07 2026 - BANCO.xlsx`

> ⚠️ **Ponto pendente — revisão com Michel:** o e-mail menciona "Integração realizada até [data] — Guia: 1436". Confirmar: a Finaud faz essa integração? E qual é o fluxo completo — WU envia dados brutos → Finaud calcula → Finaud devolve CADOC? Como sabemos que está resolvido?

---

### T05 — DRM_2060 | Crítica de inconsistência BACEN

**O que é:** BACEN detecta inconsistência no DRM enviado e comunica ao cliente. Cliente encaminha à Finaud com toda a evidência. Finaud diagnostica a causa, orienta a correção, e cliente confirma que resolveu.

**CADOC:** DRM_2060

**Fluxo completo (exemplo: Oliveira Trust — 20/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | Anterior | BACEN → Oliveira Trust | Enviou "Comunicação de inconsistência no DRM - 2060" |
| 2 | 20/07 15:05 | compliance@oliveiratrust.com.br (Victor) → Andrea Inacio (CC: suporte@) | Encaminhou e-mail do BACEN + 5 arquivos em anexo. Explicou que já tinham submetido DRM novo e recebido aceite via STA. Perguntou se podiam desconsiderar a crítica. |
| 3 | 20/07 15:31 | Andrea Inacio → Victor (CC: suporte@) | Verificou no Risk Driver: agrupamento P30 passou a ser apresentado. Orientou: basta gerar e transmitir nova versão. Mencionou possível atraso no sistema validador do BACEN. |
| 4 | 20/07 15:39 | Victor (Oliveira Trust) → Andrea | "Conferimos que o primeiro arquivo DRM enviado não tinha o agrupamento P30, presente no novo arquivo enviado e que foi aceito. Muito obrigado." |

**Como sabemos que está resolvido:** cliente confirmou que o novo arquivo foi aceito via STA e que P30 está no novo arquivo.

**Timing:** duração ~34 min · tempo na Finaud ~26 min · tempo no cliente ~8 min

**Participantes:**
- Cliente: Victor (compliance) | compliance@oliveiratrust.com.br | Oliveira Trust
- Finaud: Andrea Inacio

---

### T06 — DLO_2061 | Dúvida técnica / erro de cálculo

**O que é:** cliente identifica comportamento inesperado no cálculo de um campo do DLO e pergunta à Finaud o que está errado.

**CADOC:** DLO_2061

**Fluxo completo (exemplo: Green DTVM — 20/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 20/07 10:48 | Barbara Cota (Green DTVM) → suporte@, andrea.inacio@ | Reportou: importando arquivo 4010 e 4016, mas cálculo do patrimônio de referência não está considerando linha do balancete. |
| 2 | 20/07 11:28 | Barbara Cota → Rodrigo Tiberio (CC: Valeria Taniguchi) | "Rodrigo, o aumento de capital R$1.950.000,00 foi integralizado e aguarda autorização do BACEN — deveria ser considerado no cálculo?" |

**Como sabemos que está resolvido:** não observado nesta thread — resolução ocorreu em canal separado (outro e-mail ou ligação).

> **Nota:** algumas dúvidas técnicas são resolvidas fora da thread visível. O sistema deve registrar a thread como "Aguardando Finaud" até receber uma mensagem de encerramento.

**Participantes:**
- Cliente: Barbara Cota | barbara.cota@green.com.ai | Green DTVM
- Finaud: Rodrigo Tiberio (responsável), Andrea Inacio (CC inicial)

---

### T07 — DLO_2061 | Demandas BACEN / agendamento e solicitação de documentos

**O que é:** cliente tem demandas do BACEN sobre DLO e contata a Finaud para alinhar o que precisa ser feito. Finaud responde com a lista de documentos necessários para calcular as remessas.

**CADOC:** DLO_2061 (+ DLI_2062 frequentemente junto)

**Fluxo completo (exemplo: Planner — 22/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 22/07 11:23 | suporte@finaud.com.br → Andrea, Planner (Jailson Silva, Paulo Silveira), Rodrigo Tiberio | Jailson solicitou reunião para repassar demandas do BACEN e alinhar DLOs de junho (Antecipações) |
| 2 | 22/07 11:32 | Andrea Inacio → Jailson Silva (CC: todos) | Antecipou a lista de documentos necessários: COS 4010 (balancete), COS 4016 (balanço) e outros COS de junho/2026 |

**Como sabemos que está resolvido:** quando o cliente enviar os documentos solicitados (thread continua em T10 ou T01).

**Timing:** resposta da Finaud: ~9 minutos após o e-mail do cliente

**Participantes:**
- Cliente: Jailson Silva, Paulo Silveira | jfsilva@planner.com.br | Planner
- Finaud: Andrea Inacio, Rodrigo Tiberio

---

### T08 — DLO_2061 | Arquivo DLO rejeitado pelo BACEN

**O que é:** BACEN rejeitou o arquivo DLO enviado. Cliente aciona a Finaud para resolver. Situação em aberto — cliente cobrou resposta duas vezes.

**CADOC:** DLO_2061

**Fluxo observado (exemplo: TC/Luiza Milet — 20–21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | Anterior | BACEN → cliente | Rejeitou arquivo DLO de maio |
| 2 | 20/07 17:56 | suporte@finaud.com.br (Luiza Milet) → Monica Macedo (CC: suporte@) | "Monica, Recebemos mais um alerta de atraso no envio do DLO de maio, por gentileza, poderia informar se teve atualizações dos ajustes?" |
| 3 | 21/07 11:38 | suporte@finaud.com.br (Luiza Milet) → Monica Macedo | "Bom dia, Por gentileza, poderia retornar?" |

**Como sabemos que está resolvido:** Finaud retorna informando que ajustes foram feitos + protocolo de aceite do STA.

**Observação:** "Mais um alerta" sugere problema recorrente para este cliente.

**Participantes:**
- Cliente: Luiza Ferreira Milet | luizamilet@ (via suporte@finaud.com.br) | TC
- Finaud: Monica Macedo (responsável pelos ajustes)

---

### T09 — DLO_2061 | Indícios / Prestação de Esclarecimento

**O que é:** BACEN detecta indícios de problema de qualidade no DLO e solicita esclarecimento formal. Finaud coordena com múltiplas partes (cliente, contabilidade) para identificar a causa e responder ao BACEN.

**CADOC:** DLO_2061 (indício)

**Fluxo observado (exemplo: TC/Ignis — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 20/07 15:50 | BACEN (DLO) → múltiplos destinatários (TC, Ignis, CorpServices) | Enviou "Prestação de Esclarecimento — Indícios DLO00159 e DLO00160 — DLO 04/2026 — Protocolo 418503920" |
| 2 | 21/07 11:21 | suporte@finaud.com.br → múltiplos (TC, Ignis, CorpServices, Finaud: Andrea, Rodrigo, Flavio, Pedro) | "Bom dia, Moises, tudo bem? Por favor seria contigo estes ajustes? Muito obrigado" |

**Observação:** neste tipo, a Finaud não age sozinha — precisa da contabilidade do cliente para identificar e corrigir a origem do indício.

**Participantes:**
- Cliente: Israel Massa, Leandro Alves (TC) | israel.massa@tc.com.br
- Contabilidade: Moises Silva, Jean Santos (Ignis/CorpServices) | moisessilva@igniscontabil.com.br
- Finaud: suporte@, Andrea Inacio, Rodrigo Tiberio, Flavio Camargo, Pedro Silva

---

### T10 — DLI_2062 | Envio de remessa pelo cliente + Finaud calcula e entrega

**O que é:** cliente envia os dados necessários (COS 4010, COS 4016, planilha LEC) e a Finaud calcula e gera a remessa DLI para transmissão ao BACEN.

**CADOC:** DLI_2062 (frequentemente junto com DLO_2061)

**Fluxo completo (exemplo: Trinusco + Denver Contábil — 09–10/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 09/07 09:31 | Luiz Eduardo Coelho (Finaud/Trinusco) → Jean Lessa (Denver Contábil), Flavio Camargo (CC: suporte@) | Solicitou envio dos 4010/4060 e planilha LEC ao Jean; pediu ao Flavio que gerasse os arquivos de risco após recebimento |
| 2 | 10/07 12:07 | Jean Lessa (Denver Contábil) → todos | Enviou os arquivos solicitados em anexo |
| 3 | 10/07 19:17 | Monica Macedo → Jean Lessa (CC: suporte@, Andrea Inacio) | "Prezados. Segue em anexo, os arquivos de remessa DLI (2062) referente a maio/2026, para serem enviados ao BACEN." |

**Como sabemos que está resolvido:** Finaud entregou os ZIPs de remessa. Cliente transmite ao BACEN (confirmação via protocolo STA — não visível nesta thread).

**Variante — Coluna DTVM:** Finaud envia pacote completo DDR + DRM + DLO + DLI de maio/2026 em um único e-mail.

**Timing:** duração ~29h46 · aguardando dados do cliente ~26h · processamento após receber ~7h

**Participantes:**
- Cliente: Luiz Filho (Trinusco); Jean Lessa (Denver Contábil — contabilidade do cliente)
- Finaud: Flavio Camargo (geração), Monica Macedo (entrega)

---

### T11 — DLI_2062 | Substituição por indício de qualidade

**O que é:** DLI enviado anteriormente recebeu indício de qualidade do BACEN. Finaud precisa corrigir e enviar a remessa de substituição. Urgência: prazo de resposta é imediato.

**CADOC:** DLI_2062

**Fluxo observado (exemplo: Planner CV + SCD — 08/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 08/07 09:57 | suporte@ (Paulo Henrique, Planner) → Andrea, suporte@ | "Bom dia! @Andrea Inacio precisamos que façam a correção para substituição. Qual o parecer?" |
| 2 | 08/07 10:13 | suporte@ (Paulo Henrique) → suporte@, Andrea | "Perfeito! Te agradeço Pedro" (resposta após Pedro Silva ter respondido internamente) |

**Como sabemos que está resolvido:** cliente confirma recebimento ("Perfeito! Te agradeço Pedro") + remessa de substituição transmitida ao BACEN.

**Participantes:**
- Cliente: Paulo Henrique | Planner SCD / CV
- Finaud: Pedro Silva, Andrea Inacio

---

### T12 — DLI_2062 + DLO_2061 | Planilha LEC sob responsabilidade da Finaud

**O que é:** a planilha LEC (necessária para calcular o DLI e o DLO) foi acordada que seria feita pela Finaud, não pelo cliente. Cliente apenas confirma as atualizações dos dados.

**CADOC:** DLI_2062 + DLO_2061

**Fluxo observado (exemplo: ActivTrades — 07–08/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 07/07 | Monica Macedo → ActivTrades | Solicitou ao cliente enviar a planilha LEC de maio/2026 para gerar o DLO/DLI |
| 2 | 08/07 | Eduardo Galasini (ActivTrades) → Monica | "Monica, bom dia. Foi alinhado que a planilha LEC seria feita pela Finaud, e nos apenas confirmaríamos as atualizações." |

**Como sabemos que está resolvido:** Finaud conclui a LEC, monta o DLO e DLI, entrega ao cliente para transmissão.

**Observação:** tipo com risco de confusão de responsabilidade — precisa estar claro no sistema quem faz a LEC por cliente.

**Participantes:**
- Cliente: Eduardo Galasini | egalasini@activtrades.com | ActivTrades CCTVM
- Finaud: Monica Macedo

---

### T13 — S5 | Resultado quantitativo (Índice de Basileia)

**O que é:** cliente envia o COS4010 (balancete) e a Finaud calcula os requerimentos mínimos de capital (S5) para o mês de referência. Entrega o relatório com o Índice de Basileia e demais parcelas de risco.

**CADOC:** S5

**Fluxo completo (exemplo: Vector / VBS SCD — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | Anterior | Gabriel Santos (Vector Unitech / VBS SCD) → suporte@ | Enviou o COS4010 06/2026 para cálculo do S5 de junho/2026 |
| 2 | 21/07 17:59 | suporte@finaud.com.br → Gabriel Santos (CC: Monica Macedo, Joyce Sinatolli, outros) | "Prezados, boa tarde. Arquivos recebidos. Obrigada. Segue anexo a apuração dos requerimentos mínimos S5 data base: junho/2026. O resultado quantitativo S5 apurou um Índice de Basileia de: **545,23%**. O requerimento mínimo S5 estabelecido no art. 12 da Resolução 4606 é 17%, portanto a Instituição permanece enquadrada. [...]" |

**Como sabemos que está resolvido:** Finaud entregou o relatório com o Índice de Basileia. Cliente não precisa transmitir ao BACEN (S5 não é uma remessa diária).

**Participantes:**
- Cliente: Gabriel Santos | gabriel.santos@vector-unitech.com | Vector Unitech / VBS SCD
- Finaud: suporte@ (Monica Macedo identificada no CC)

---

### T14 — SUPORTE | Erro de transmissão ao BACEN

**O que é:** cliente tentou transmitir um arquivo ao BACEN e recebeu mensagem de erro que não consegue resolver. Aciona a Finaud para orientação.

**CADOC:** SUPORTE (qualquer CADOC que falhou na transmissão)

**Fluxo completo (exemplo: Intra Investimentos — 03/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 03/07 17:07 | suporte@finaud.com.br (Intra) → suporte@ Finaud (CC: Lucas Vellani) | "Tentei realizar o envio do DRM no sistema hoje, porém o arquivo foi rejeitado em duas tentativas. A mensagem de retorno foi: 'Instituição não existe no Unicad. [...]'" |
| 2 | 03/07 17:13 | suporte@finaud.com.br → Ana Caroline (Intra) (CC: Lucas Vellani) | "A mensagem do protocolo sugere algum tipo de erro no sistema de recepção do arquivo no BC. Encaminhe o questionamento sobre o erro via CRD ou no endereço drm-envio@bcb.gov.br" |

**Como sabemos que está resolvido:** cliente resolve com o BACEN diretamente.

**Timing:** resposta da Finaud em ~6 minutos (problema identificado como do lado do BACEN — orientação direta)

**Participantes:**
- Cliente: Ana Caroline | ana.caroline@intrainvestimentos.com.br | Intra Investimentos
- Finaud: suporte@ Finaud, Lucas Vellani

---

### T15 — SUPORTE | Solicitação de arquivos históricos

**O que é:** cliente (ou ex-cliente) solicita os arquivos que a Finaud gerou durante o período do contrato.

**CADOC:** SUPORTE

**Fluxo observado (exemplo: Unicred — 15–17/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | 15/07 15:09 | Rafaela Fonseca (Unicred) → Monica, Andrea, suporte@ (CC: Luis Paiva) | "Prezados, boa tarde! Solicitamos os xmls gerados (2061/2062) pela Finaud durante o período do contrato." |
| 2 | 17/07 14:36 | suporte@ (Unicred) → Monica, Andrea, suporte@ | Cobrou novamente após 2 dias sem resposta |

**Como sabemos que está resolvido:** Finaud envia os arquivos solicitados.

**Participantes:**
- Cliente: Rafaela Fonseca | rafaela.hot@unicred.com.br | Unicred do Brasil
- Finaud: Monica Macedo, Andrea Inacio

---

### T16 — Indício de qualidade 4016/4010 (multi-CADOC)

**O que é:** BACEN detecta problema de qualidade em documento 4016 (Balanço Patrimonial) ou 4010 (Balancete). Envia comunicação formal. Geralmente há múltiplas partes envolvidas: cliente, contabilidade e Finaud.

**CADOC:** multi-CADOC (afeta DDR, DRM, DLO, DLI — qualquer um que usou o 4016/4010 errado)

**Fluxo completo (exemplo: TC/Ignis — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | Anterior | BACEN → TC, Ignis, CorpServices | Enviou "BANCO CENTRAL - INDÍCIO DE PROBLEMA DE QUALIDADE IDENTIFICADO NO DOCUMENTO 4016 - CNPJ 62.280.490" |
| 2 | 21/07 10:21 | suporte@finaud.com.br → TC (Israel, Leandro), Ignis, CorpServices, Finaud (Andrea, Rodrigo, Flavio, Pedro) | Pediu a Sarah para regerar novo 4111 e 4010 com os dados em anexo; perguntou quem é Reinaldo Dantas (nome no arquivo transmitido) |
| 3 | 21/07 14:39 | Jean Santos (CorpServices) → todos | "Reinaldo é um dos sócios da Ignis...o login do BACEN está em nome dele... Esse 4016 já foi substituído." |
| 4 | 21/07 14:41 | suporte@finaud.com.br → Jean, todos | "Muito obrigado Jean." |

**Como sabemos que está resolvido:** Jean confirmou que o 4016 já foi substituído.

**Timing:** da pergunta de quem é Reinaldo até a resposta: ~18 minutos

**Participantes:**
- Cliente: Israel Massa, Leandro Alves (TC) | israel.massa@tc.com.br
- Contabilidade: Jean Santos (CorpServices/Ignis) | JeanSantos@corpservices.com.br
- Finaud: suporte@, Andrea Inacio, Rodrigo Tiberio, Flavio Camargo, Pedro Silva

---

### T17 — Indício de qualidade 4111 (BACEN → Finaud instrui regeneração)

**O que é:** BACEN detecta indício no documento 4111. Finaud instrui o time interno a regerar o 4111 e o 4010 com os dados corretos.

**CADOC:** 4111 (com geração conjunta do 4010)

**Fluxo observado (exemplo: TC/Ignis — 21/07/2026):**

| # | Data/Hora | Quem | O que fez |
|---|---|---|---|
| 1 | Anterior | BACEN → TC (Marcos, Israel, Leandro, Ignis, CorpServices) | "BANCO CENTRAL - INDÍCIO DE PROBLEMA DE QUALIDADE IDENTIFICADO NO DOCUMENTO 4111 - CNPJ 62.280.490" |
| 2 | 21/07 10:21 | suporte@finaud.com.br → suporte@ (internamente) | "Sarah, bom dia! pode por favor regerar um novo 4111 e um novo 4010 para correção junto ao BACEN. Dados em anexo. No aguardo, obrigado!" |

**Como sabemos que está resolvido:** Sarah regenera os arquivos, Finaud transmite a versão corrigida ao BACEN, recebe protocolo de aceite do STA.

**Participantes:**
- Cliente: TC (Marcos Cardoso, Israel Massa)
- Finaud interna: Sarah (sarah.sa@finaud.com.br), suporte@

---

### T18 — Alertas automáticos do sistema Finaud (FILTRAR)

**O que é:** e-mails gerados automaticamente pelo sistema da Finaud sobre atualizações de leiautes do BACEN e normativos regulatórios. Não são de clientes — não devem entrar na triagem operacional.

**Tipos:**
- "📢 Atenção: Atualização na página de Leiautes do Bacen na data: [data]"
- "📢 Atualização Bacen – RISCOS – [data]"

**Remetente:** contato@finaud.com.br  

**Como identificar:** remetente é contato@finaud.com.br e/ou assunto começa com "📢"

**Ação:** filtrar automaticamente — não entrar na triagem

---

### T19 — FogBugz / Bug interno (FILTRAR)

**O que é:** notificações do sistema interno FogBugz sobre casos de desenvolvimento (bugs, melhorias). Não são de clientes.

**Exemplo observado:** "FogBugz (Caso 8549) S5 - Verificar a diferença no RWAOSimp - FREEX"

**Remetente:** suporte@finaud.com.br (notificação do FogBugz)  

**Como identificar:** assunto contém "FogBugz" ou "Caso NNNN"

**Ação:** filtrar automaticamente — não entrar na triagem

---

## 16. Padrões observados para guiar a IA

### Padrão de conclusão por tipo

| Tipo | Sinal de conclusão |
|---|---|
| T01 (envio diário) | Thread sem resposta após envio = Finaud processou internamente |
| T02 (substituição) | Finaud entregou os ZIPs de substituição |
| T03 (variação relevante) | Cliente diz "darei a tratativa" ou similar |
| T04 (balancete câmbio) | Thread de 1 mensagem, sem retorno esperado — aguarda confirmação de Michel |
| T05 (inconsistência DRM) | Cliente confirma que novo arquivo foi aceito no STA |
| T06 (dúvida técnica) | Finaud responde e cliente confirma entendimento |
| T07 (demanda BACEN/reunião) | Cliente envia os documentos solicitados (thread continua em T10) |
| T08 (arquivo rejeitado) | Finaud confirma ajuste feito + protocolo STA |
| T09 (indícios) | Esclarecimento prestado ao BACEN dentro do prazo |
| T10 (envio remessa DLI) | Finaud entrega ZIPs + cliente confirma recebimento |
| T11 (substituição DLI) | Cliente confirma ("Perfeito") ou protocolo STA |
| T12 (planilha LEC) | Finaud entrega DLO/DLI calculados |
| T13 (S5) | Finaud entrega relatório com Índice de Basileia |
| T14 (erro transmissão) | Finaud orienta canal correto para resolver |
| T15 (arquivos históricos) | Finaud entrega os arquivos solicitados |
| T16 (indício 4016/4010) | Problema identificado + arquivo já substituído |
| T17 (indício 4111) | Finaud regenera e transmite versão corrigida |

### Lado da Finaud vs. lado do cliente

| Situação | Lado responsável |
|---|---|
| Finaud entregou remessa, aguarda cliente transmitir | Cliente |
| Cliente enviou dados, aguarda Finaud processar | Finaud |
| Finaud orientou, aguarda confirmação do cliente | Cliente |
| BACEN comunicou algo, aguarda ação de qualquer das partes | Depende de quem respondeu por último |

### Colaboradores mais solicitados (observados na Fase 0)

| Colaborador | Tipos frequentes |
|---|---|
| Andrea Inacio | DRM crítica (T05), DLO reunião (T07), DLI substituição (T11), DDR substituição (T02) |
| Monica Macedo | DDR variação (T03), DLI entrega (T10), DLO rejeitado (T08) |
| Pedro Silva | DDR diário (T01), DLI substituição (T11) |
| Rodrigo Tiberio | DLO dúvida técnica (T06), Indícios (T09) |
| Flavio Camargo | DLI geração (T10), Indícios (T09) |

### Clientes mais ativos (observados nos últimos 30 dias — Fase 0)

| Cliente | Tipos mais frequentes |
|---|---|
| TC / Ignis / CorpServices | T09, T16, T17, T08 (múltiplos CADOCs) |
| Mirae Asset | T01, T02 (DDR diário + substituição) |
| Amaril Franklin | T01 (DDR diário) |
| Accredito SCD | T01, T10 (DDR + DLI) |
| Planner | T07, T11 (DLO demanda + DLI substituição) |
| Western Union | T04 (câmbio diário) |
| Oliveira Trust | T05 (DRM inconsistência) |

---

## Apêndice A — Colaboradores Finaud identificados

Lista dos colaboradores identificados durante a Fase 0. Pode estar incompleta — o sistema não depende desta lista para identificar colaboradores Finaud (qualquer `@finaud.com.br` ou `@finaudtec.com.br` é tratado como Finaud automaticamente, sem cadastro manual).

| Nome | E-mail | Papel |
|---|---|---|
| Andrea Inacio | andrea.inacio@finaud.com.br | Coordenadora de Suporte |
| Monica Macedo | monica.macedo@finaud.com.br | Analista de Suporte Jr. |
| Pedro Silva | pedro.silva@finaud.com.br | Analista de Suporte |
| Rodrigo Tiberio | rodrigo.tiberio@finaud.com.br | Analista de Suporte |
| Flavio Camargo | flavio.camargo@finaud.com.br | Analista de Suporte |
| Lucas Vellani | lucas.vellani@finaud.com.br | Analista de Suporte |
| Sarah Sá | sarah.sa@finaud.com.br | Analista (regeneração de arquivos — T16/T17) |
| Luiz Antonio | luiz.antonio@finaudtec.com.br | Colaborador Finaud (empresa FinaudTec) |
| suporte@finaud.com.br | — | Caixa compartilhada (grupo) |

