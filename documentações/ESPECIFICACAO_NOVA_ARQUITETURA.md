# Especificação — Nova Arquitetura do Oráculo 360
**Versão:** 2.0  
**Data:** 31/07/2026  
**Status:** Em desenvolvimento ativo — revisão sequencial em andamento — §7 a §11 revisados e aprovados; próxima seção: §12 Decisões tomadas e justificativas

---

## Índice

| § | Seção |
|---|---|
| 1 | O que é o Oráculo 360 |
| 2 | O que o sistema faz |
| 3 | As 10 categorias de e-mail e seus fluxos |
| 4 | Quem usa e para quê |
| 5 | Como os e-mails chegam ao sistema |
| 6 | Onde roda |
| 7 | Mapeamento de campos do e-mail (Campos 1–8) |
| 8 | Regras de classificação das threads |
| 9 | Modelo de rastreamento — duas camadas |
| 10 | Catálogo de categorias — o que a IA precisa saber |
| 11 | Exemplos reais de threads (T01–T19) |
| 12 | Decisões tomadas e justificativas |
| 13 | Plano de implantação por fases |
| 14 | Telas do sistema |
| A | Apêndice A — Colaboradores Finaud identificados |
| B | Apêndice B — Terminologia |

---

## 1. O que é o Oráculo 360

O Oráculo 360 monitora os e-mails trocados entre a Finaud e seus clientes. O sistema tem quatro peças:

1. **Leitura do Gmail** — acessa a caixa de e-mail diretamente via Gmail API e lê todas as conversas
2. **IA classificadora** — entende cada e-mail e identifica a qual categoria ele pertence — obrigações regulatórias (como DDR, DRM, DLO) ou suporte — sendo que um mesmo e-mail pode envolver mais de uma categoria ao mesmo tempo
3. **Painel operacional** — mostra ao gestor o que está aguardando ação (da Finaud ou do cliente) e o que já foi concluído, por categoria
4. **IA assistente** *(2ª fase)* — aprende com os casos já resolvidos para ajudar a equipe a entender como tratar situações parecidas no futuro

> **Decisão confirmada por Michel (22/07/2026):** o sistema usará Gmail API direta para leitura dos e-mails em produção. O Gmail MCP continua disponível como ferramenta de análise durante o desenvolvimento.

---

## 2. O que o sistema faz

### O que o sistema faz

- Monitora todas as conversas na caixa coleta.oraculo@finaud.com.br
- Identifica automaticamente a qual categoria cada e-mail pertence (pode ser mais de uma)
- Define o status de cada conversa — aguardando ou concluído
- Monitora prazos regulatórios

O sistema ficará em execução permanente, atualizando automaticamente quando chegarem threads novas ou quando threads existentes receberem novos e-mails.

### O que o sistema não faz

- Não gera os CADOCs (só monitora a entrega)
- Não integra com o sistema interno da Finaud
- Não cobre WhatsApp, telefone ou outros canais

---

### Por que estas escolhas — decisões fundacionais

Três escolhas definem toda a arquitetura. Quem for implementar, manter ou evoluir o sistema precisa entendê-las antes de tudo.

**1. Gmail API direta — por que não uma exportação manual ou agendada?**
Qualquer e-mail novo chega ao sistema em segundos — sem intervenção humana, sem exportação periódica, sem janela de atraso. Obrigações regulatórias têm prazo: um e-mail que chega à tarde e só é visto no dia seguinte pode significar entrega atrasada ao BACEN.

**2. Classificador determinístico agora, IA no futuro**
O sistema usa um classificador baseado em regras (sem custo de API, sem latência, sem incerteza aleatória) para classificar todos os e-mails. As regras cobrem 99,5% dos casos do histórico real (764 de 768 threads). Quando o classificador não consegue determinar a categoria, o e-mail vai para a Tela de Revisão — Michel classifica manualmente e a regra é aprendida.

A IA (GPT-4o-mini) entra em fase futura, quando houver volume suficiente de casos manuais para treinar e validar. O classificador determinístico é o ponto de partida: estável, auditável e sem custo por uso.

**3. Duas camadas — por que separar classificação de rastreamento?**
Um único e-mail pode mencionar DDR, DRM e DLO ao mesmo tempo: "segue o material de março — DDR, DRM e DLI". Se o sistema rastreasse por e-mail, teria que inventar uma categoria "misturada". Com duas camadas, a Camada 1 identifica as categorias presentes no e-mail e a Camada 2 rastreia o ciclo de vida de cada entrega separadamente — cada CADOC tem seu próprio estado, independente dos outros.

---

## 3. As 12 categorias de e-mail e seus fluxos

O sistema trata 12 categorias distintas de e-mail. Cada categoria tem suas próprias regras, prazo regulatório e fluxo — as regras de classificação estão no §10 (Catálogo de categorias) e os exemplos reais estão no §11.

| Categoria | O que é |
|---|---|
| DDR_2011 | Relatório diário das posições financeiras do cliente — títulos, câmbio, compromissadas. O cliente envia à Finaud todo dia útil para gerar o CADOC. |
| SALDOS_CONTABEIS_DIARIOS_4111 | Saldo diário das contas contábeis do cliente no padrão COSIF do BACEN. Enviado todo dia útil. |
| DRM_2060 | Relatório mensal que mede a exposição da instituição a riscos de mercado — juros, câmbio e preços de ativos. |
| DLO_2061 | Relatório mensal sobre os limites regulatórios do conglomerado — adequação de capital (Basileia) e concentração de riscos. |
| DLI_2062 | Mesmo que o DLO, mas individual — foca nos limites de cada instituição separadamente. |
| DRL_2160 | Relatório mensal do "colchão de liquidez" — quanto de ativos líquidos a instituição mantém para cobrir saídas em situações de estresse. |
| S5 | Relatório de risco para instituições de menor porte (Segmento 5 do BACEN). Fica entre Finaud e cliente — não é enviado ao BACEN. |
| RETORNO_BACEN | Comunicado do BACEN rejeitando ou criticando uma entrega anterior. O cliente repassa à Finaud para investigar e corrigir. |
| SUPORTE | Dúvidas, suporte técnico, acesso a sistemas, onboarding de clientes novos, reuniões e comunicação geral — tudo que não é entrega de CADOC. |
| FORCAPITAL | Serviço da Finaud para projeção de capital do cliente. Não é regulatório — não vai ao BACEN. |
| DRSAC_2030 | Relatório semestral sobre operações de crédito. A Finaud orienta, mas quem gera e entrega ao BACEN é o próprio cliente. |
| PVCA_6209 | Relatório trimestral sobre pagamentos de varejo e canais de atendimento. O cliente transmite diretamente ao BACEN via sistema STA. |

> **Nota:** um e-mail pode conter mais de uma categoria (ex.: "DDR + DRM + DLI de março"). O sistema rastreia cada entrega separadamente — ver §9 (Modelo de rastreamento, duas camadas).

---

## 4. E-mails que não entram na triagem

O sistema descarta automaticamente estes remetentes antes de classificar. A lista é configurável na tela de filtros — sem mexer no código.

| Critério | Valor | Motivo |
|---|---|---|
| **Endereço exato** | `riskdriver@finaud.com.br` | Sistema automático Risk Driver |
| **Endereço exato** | `contato@finaud.com.br` | Sistema automático de alertas |
| **Endereço exato** | `coleta.oraculo@finaud.com.br` | Conta de coleta do próprio sistema |
| **Endereço exato** | `do-not-reply@finaud.fogbugz.com` | Sistema de tickets FogBugz |
| **Endereço exato** | `comunicacao@comunicacao.bcb.gov.br` | Comunicados automáticos do BACEN |
| **Padrão no endereço** | `noreply` · `no-reply` · `mailer-daemon` · `newsletter` · `notification` · `bounce` | Endereços automáticos genéricos |
| **Domínio do remetente** | `employer.com.br` | Sistema de RH (Epays, Pontofopag) |
| **Domínio do remetente** | `content.pwc.com` | Newsletter PwC |
| **Domínio do remetente** | `grafana.com` | Ferramenta de monitoramento |
| **Domínio do remetente** | `eadtiexames.com.br` | Plataforma de cursos online |
| **Domínio do remetente** | `appsheet.com` | Ferramenta de apps Google |
| **Domínio do remetente** | `freshworks.com` | Sistema de suporte externo |
| **Domínio do remetente** | `nasajon.com.br` | Software contábil (newsletter) |
| **Nome do remetente** | `Facebook` · `Meta` · `Instagram` · `LinkedIn` · `Twitter` · `YouTube` · `Telegram` · `WhatsApp` | Redes sociais |
| **Nome do remetente** | `3CX Communications System` | Sistema de telefonia (notificações de chamada perdida) |
| **Nome + assunto** | Nome contém `FINAUDTEC` e assunto contém `FogBugz` | Ticket interno do sistema de tickets |
| **Nome + assunto** | Nome contém `Finaud Equipe` e assunto contém `Confirmação` | Confirmação de conta do sistema Finaud |
| **Padrão no assunto** | `IT Service Desk` | Notificações do sistema de TI interno |
| **Padrão no assunto** | `Aceito:` (início do assunto) | Aceite de convite de calendário (Google Agenda, Outlook) |

> **Origem:** simulação completa com 943 threads reais (05/08/2026). Varredura de todos os domínios confirmou cobertura total: **174 threads filtradas, zero threads suspeitas fora do filtro.** Base válida: **769 threads**. A lista de domínios é configurável — novos serviços externos podem ser adicionados na tela de filtros sem intervenção técnica.

> **Regra (05/08/2026):** filtros por assunto sozinho só são permitidos quando o padrão é exclusivo de sistemas automáticos — nunca aparece em e-mail legítimo de cliente. Exemplos válidos: `IT Service Desk`, `Aceito:` (calendário). O assunto combinado com o remetente também é permitido (ex.: FogBugz, Finaud Equipe).

---

## 5. Como os e-mails chegam ao sistema

A conta `coleta.oraculo@finaud.com.br` recebe os e-mails por dois caminhos independentes:

**Caminho 1 — Grupo de suporte**
A conta oraculo@ é membro do grupo `suporte@finaud.com.br`. Isso significa que todo e-mail enviado para suporte@finaud.com.br chega automaticamente também na caixa do oraculo@, da mesma forma que chega para qualquer outro membro do grupo.

**Caminho 2 — Cópia automática configurada no Google Workspace**
O Google Workspace (a plataforma de e-mail da Finaud) está configurado para enviar uma cópia silenciosa de todo e-mail recebido por qualquer endereço @finaud.com.br para a conta oraculo@. Essa configuração fica no painel de administração do Workspace (Gmail → Roteamento padrão) e é transparente: os colaboradores não fazem nada, os clientes não veem, a cópia simplesmente acontece.

Resultado: mesmo quando um cliente escreve diretamente para rodrigo.tiberio@finaud.com.br ou andrea.inacio@finaud.com.br — sem copiar o suporte@ — o oraculo@ ainda recebe o e-mail pelo Caminho 2.

**Verificação feita em 31/07/2026:** encontramos e-mails de clientes externos na caixa do oraculo@ que foram enviados diretamente para colaboradores, sem nenhum campo (Para, CC ou BCC) com suporte@finaud.com.br. Isso confirma que o Caminho 2 está ativo e funcionando.

---

## 6. Onde roda

Servidor em produção — acessível pela equipe a qualquer hora, sem depender do computador do Michel estar ligado. (Diferente do sistema atual que roda em localhost:5000.)

---

## 7. Mapeamento de campos do e-mail

Como cada campo do e-mail será lido e usado pelo sistema. Campos mapeados um por um com simulação em dados reais antes de documentar.

### Regra geral do pipeline — dois destinos para e-mails que não chegam à IA

> **Aprovado por Michel em 03/08/2026.**

Todos os e-mails passam pelos 8 campos em sequência. Se qualquer campo tiver dado faltando ou incorreto, o e-mail não vai para a IA. Há dois destinos para e-mails que não chegam à IA — e um terceiro para quando a IA processa mas não atinge confiança mínima:

| Destino | Quando ocorre | O que acontece |
|---|---|---|
| **Descarte** | E-mail filtrado por regra conhecida — remetente automático (Campo 1) ou assunto automático (Campo 5) | Descartado silenciosamente. Registrado em log interno para auditoria. Sem notificação. |
| **Retenção** | Dado faltando ou incorreto em qualquer campo — algo inesperado que impede o processamento | E-mail não vai para a IA. Sistema envia **notificação imediata** para Michel com: remetente, assunto, data, campo onde parou, motivo exato e ID da thread no Gmail. |
| **Retenção** | IA processa o e-mail mas não atinge 99% de confiança em qualquer dado que vai para a tela | Mesma notificação: remetente, assunto, data, motivo ("classificação incerta — confiança abaixo de 99%") e thread ID do Gmail. |

> **Regra dos 99% — aprovada por Michel em 03/08/2026:** todo dado exibido na tela do sistema (categoria, remetente, destinatário, prazo) precisa ter confiança mínima de 99%. Abaixo disso → Retenção, sem exceção.

**Liberação:** Michel pode liberar um e-mail retido para processamento pela IA a qualquer momento. Esse processamento acontece de forma **isolada do fluxo de produção** — não interfere nas threads que já estão sendo monitoradas.

**Exemplos:**
- `noreply@sistema.com.br` → Campo 1, Passo 3 → **Descarte** (regra conhecida: padrão noreply)
- E-mail com campo From vazio → Campo 1, Passo 1 → **Retenção** (dado faltando — notificação imediata)

---

### Campo 1 — From/Sender (Remetente)

O campo `From` não é sempre o remetente real. Quando o e-mail passa pelo grupo `suporte@finaud.com.br`, o Google substitui o `From` original pelo endereço do grupo. A solução é usar o campo `Reply-To` — que preserva o endereço original — como fonte primária.

**Regra de identificação — cenários encontrados na caixa real:**

| Valor do From | Exemplo real | Quem é | O que fazer |
|---|---|---|---|
| `*@finaud.com.br` | `andrea.inacio@finaud.com.br` | Colaborador Finaud | Usar direto — cobre automaticamente novos colaboradores, sem cadastrar |
| `*@finaudtec.com.br` | `luiz.antonio@finaudtec.com.br` | Colaborador Finaud (segunda empresa) | Usar direto |
| `suporte@finaud.com.br` | `suporte@finaud.com.br` | Grupo compartilhado | Verificar Reply-To: (1) fora da Finaud → cliente é o remetente real; (2) dentro da Finaud → colaborador Finaud é o remetente real; (3) vazio + nome no From → usar nome como colaborador (ex.: `"Pedro Silva" <suporte@...>`); (4) vazio + sem nome → classifica normalmente, campo responsável fica em branco |
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

**Como o sistema processa — passo a passo:**

O sistema percorre os passos abaixo em ordem. Para cada e-mail recebido, aplica uma condição de cada vez até ter uma resposta.

| Passo | Condição | Ação | Exemplo real do histórico |
|---|---|---|---|
| 1 | From vazio | **Retenção** — o sistema precisa deste campo | *(teórico — não ocorreu nos 8.825 e-mails do histórico)* |
| 2 | From na lista de filtros por endereço exato | **Descarte** — remetente automático conhecido | `riskdriver@finaud.com.br` — Risk Driver |
| 3 | From contém padrão bloqueado no endereço | **Descarte** — remetente automático de qualquer domínio | `noreply@`, `mailer-daemon@`, `newsletter@`, etc. |
| 4 | Nome no From contém rede social | **Descarte** — notificação social chegando via grupo | `"'Facebook' via Suporte" <suporte@finaud.com.br>` |
| 5 | From = `suporte@finaud.com.br` | Ir ao Campo 4 (Reply-To) | `"'FINAUDTEC' via Suporte" <suporte@finaud.com.br>` |
| 6 | From termina em `@finaud.com.br` ou `@finaudtec.com.br` | Identificado como Finaud | `andrea.inacio@finaud.com.br`, `luiz.antonio@finaudtec.com.br` |
| 7 | Qualquer outro domínio | Identificado como cliente | `risco@brazabank.com.br`, `jessica.silva@banvox.com.br` |

> **Nota — FogBugz:** os 132 e-mails de notificação do FogBugz chegam com remetente `suporte@finaud.com.br` (Passo 4 → vai ao Campo 4). O Campo 1 **não** os descarta aqui. Eles são descartados mais adiante, no **Campo 5**, pelo assunto ("FogBugz" no assunto). O endereço `do-not-reply@finaud.fogbugz.com` na lista de filtros exatos (Passo 2) é uma rede de segurança teórica — nos 8.825 e-mails do histórico, nenhum chegou com esse remetente.

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

### Campo 2 — Para (Destinatários)

**O que é:** lista de quem recebeu o e-mail no campo "Para:".

**Para que o sistema usa:** identificar com quem está o assunto no momento (se a bola está com a Finaud ou com o cliente), quem é o colaborador responsável pelo lado Finaud e quem é o contato responsável pelo lado do cliente. Ambos alimentarão o painel de atividade na Fase 2 — para visualizar quem está com mais casos em aberto em cada lado. Se a Finaud não estiver no Para, o sistema verifica o CC para saber se está sendo copiada.

> **Regra:** qualquer endereço `@finaud.com.br` ou `@finaudtec.com.br` é tratado como Finaud automaticamente — novos colaboradores não precisam ser cadastrados. *(Decisão confirmada por Michel, 22/07/2026.)*

**Como o sistema processa — passo a passo:**

| Passo | Condição | Ação |
|---|---|---|
| 1 | Para está vazio | Ir para Campo 3 (CC) |
| 2 | Para tem apenas endereços `@finaud.com.br` / `@finaudtec.com.br` | Mensagem interna — segue o fluxo normalmente. Pode ser puramente Finaud↔Finaud, ou uma thread que em algum momento envolveu o cliente e passou a ser troca interna. Em ambos os casos todas as regras se aplicam — o que muda é com quem está a bola. |
| 3 | `suporte@finaud.com.br` envia para `suporte@finaud.com.br` (grupo enviando para si mesmo) | **Descarte** |
| 4 | Para tem Finaud + endereços externos | Cliente = endereço(s) externo(s) — ir para Passo 5 |
| 5 | Para tem colaborador específico Finaud + grupo `suporte@` | Colaborador específico tem prioridade — é o responsável da thread |
| 6 | Para tem dois ou mais colaboradores Finaud | Os dois receberam — quem responder primeiro vira responsável |
| 7 | Para tem dois ou mais clientes externos (domínios diferentes) | IA determina o cliente principal pelo contexto da thread |
| 8 | Para tem apenas endereços externos (Finaud não está no Para) | Ir para Campo 3 (CC) — verificar se Finaud está sendo copiada |

---

**Todos os casos com exemplos reais:**

**Cliente enviando para o grupo Finaud:**
`jessica.silva@banvox.com.br` → `suporte@finaud.com.br`
→ Finaud recebe — direção: cliente → Finaud

**Cliente manda para grupo E colaborador ao mesmo tempo:**
`jessica.silva@banvox.com.br` → `suporte@finaud.com.br` + `andrea.inacio@finaud.com.br`
→ colaborador específico tem prioridade sobre o grupo → Andrea é a responsável

**Cliente manda para dois colaboradores:**
`pedro.silva@accredito-scd.com.br` → `pedro.silva@finaud.com.br` + `andrea.inacio@finaud.com.br`
→ os dois receberam → quem responder primeiro vira responsável pela thread

**Finaud enviando para cliente:**
`andrea.inacio@finaud.com.br` → `guilherme.marin@guru.com.vc`
→ endereço externo no Para → cliente: Guru CTVM

**Finaud se copiou mas incluiu o cliente:**
`andrea.inacio@finaud.com.br` → `andrea@finaud.com.br` + `victor@miraeinvest.com.br`
→ ignora o endereço Finaud, sobra `victor@miraeinvest.com.br` → cliente: Mirae Invest

**Vários clientes no Para:**
`suporte@finaud.com.br` → `contato@tc.com.br` + `op@ignis.com.br`
→ dois domínios externos diferentes → IA determina o cliente principal

**Mensagem interna:**
`sarah.sa@finaud.com.br` → `suporte@finaud.com.br` + `miguel.santos@finaud.com.br`
→ só Finaud no Para → mensagem interna — segue o fluxo normalmente; todas as regras se aplicam, o que muda é com quem está a bola

**E-mail enviado para o próprio grupo (suporte para si mesmo):**
`suporte@finaud.com.br` → `suporte@finaud.com.br`
→ sem cliente externo → **Descarte**

**Finaud está só no CC (não está no Para):**
`victor@miraeinvest.com.br` → `rafael@miraeinvest.com.br` (Finaud no CC)
→ Para não tem Finaud → sistema verifica CC → encontra Finaud → thread monitorada → **status: Aguardando Cliente** (a bola está com o cliente — ele está falando com a própria equipe; a Finaud monitora)

**Para vazio:**
→ sistema verifica CC; se CC também vazio → **Retenção**

---

### Campo 3 — CC (Cópia)

**O que é:** lista de endereços que receberam o e-mail como cópia — estão "por dentro" da conversa mas não são o destinatário principal.

**Para que o sistema usa:** o CC é consultado em dois casos específicos. Fora desses dois casos, é ignorado — não determina quem age nem afeta as regras de classificação.

> **Correção da decisão anterior (24/07/2026 → revisada em 03/08/2026):** a decisão registrada dizia "CC não será utilizado pelo sistema". Essa decisão foi revisada — o CC é utilizado nos dois casos abaixo. Fora deles, permanece ignorado.

> **Confirmado no histórico:** em 3.108 e-mails (35% do total), a Finaud aparece no CC mas não no Para. O CC é importante — não é exceção.

**Como o sistema processa — passo a passo:**

| Passo | Condição | Ação |
|---|---|---|
| 1 | Campo 2 (Para) já identificou Finaud e o cliente | CC não é consultado — segue direto para Campo 4 |
| 2 | Campo 2 não encontrou Finaud (Para vazio ou só externos) | Consultar CC |
| 3 | CC contém endereço `@finaud.com.br` / `@finaudtec.com.br` | Finaud está monitorando — thread registrada; quem age é o destinatário do Para |
| 4 | CC contém endereço externo além de Finaud | Cliente = endereço externo identificado no CC |
| 5 | CC contém só Finaud (sem externo) | Cliente identificado pelo Campo 4 (Reply-To) ou pelo remetente (Campo 1) |
| 6 | CC vazio (chegamos aqui porque Para também estava vazio — relay perdeu o cabeçalho) | **Retenção** — anomalia técnica de roteamento; sistema não consegue identificar destinatário por nenhum campo |

---

**Caso 1 — Finaud não aparece no Para:**
`victor@miraeinvest.com.br` → `rafael@miraeinvest.com.br` (CC: `coleta.oraculo@finaud.com.br`)
→ sistema não encontra Finaud no Para → verifica CC → encontra Finaud → thread monitorada; quem age é o destinatário do Para

**Caso 2 — Para está vazio:**
Henrique Rezende (Wise) enviou para suporte@finaud.com.br. O grupo relayou o e-mail e o "Para" original se perdeu. Assunto: "Re: DRM_2060 - 12/2025".
→ Para vazio → sistema verifica CC → encontra Lucas Vellani + suporte@ (Finaud) → Finaud é o destinatário → thread monitorada, aguardando ação da Finaud

**Variações do Caso 2:**

CC tem endereço externo (além de Finaud):
→ sistema usa o endereço externo como cliente

CC tem só Finaud (como no DRM_2060 acima):
→ Finaud é o destinatário; cliente já identificado pelo Campo 4 (Reply-To)

CC vazio (e Para também estava vazio):
→ anomalia técnica de roteamento — relay perdeu todos os cabeçalhos de destinatário → **Retenção** com alerta para Michel

---

### Campo 4 — Reply-To (Remetente real)

**O que é:** quando alguém envia pelo grupo `suporte@finaud.com.br`, o campo De mostra o grupo — não a pessoa. O Reply-To guarda o endereço de quem realmente enviou.

**Para que o sistema usa:** o Reply-To é lido APENAS quando Campo 1 identificou `De = suporte@finaud.com.br`. Em todos os outros casos é ignorado.

> **Por que a Finaud usa o suporte@:** ao responder via grupo, todos os colaboradores do grupo recebem uma cópia automaticamente — sem precisar copiar cada um manualmente. É intencional.

> **Confirmado no histórico (varredura 04/08/2026 — 1.745 e-mails com De = suporte@):**
> - Reply-To = cliente externo: **1.711 (98,1%)**
> - Reply-To = filtrado (noreply@...): **26 (1,5%)** → Descarte
> - Reply-To = vazio: **8 (0,5%)** → ler assinatura
> - Reply-To = @finaud.com.br (colaborador): **0 (0,0%)** — nunca ocorreu no histórico real; caso teórico ignorado
>
> Os três cenários reais estão cobertos pelos Passos 3, 4 e 5–7 abaixo.

**Como o sistema processa — passo a passo:**

| Passo | Condição | Ação |
|---|---|---|
| 1 | Campo 1 (De) ≠ `suporte@finaud.com.br` | Reply-To ignorado — campo não é consultado |
| 2 | Campo 1 (De) = `suporte@finaud.com.br` | Verificar Reply-To |
| 3 | Reply-To tem endereço externo não-filtrado | Remetente real = esse endereço; cliente identificado — segue para classificação |
| 4 | Reply-To tem endereço filtrado (`noreply@`, notificação automática) | **Descarte** |
| 5 | Reply-To vazio | Ler assinatura do Campo 6 para identificar o colaborador que enviou |
| 6 | Assinatura contém e-mail `@finaud.com.br` / `@finaudtec.com.br` | Colaborador identificado como responsável |
| 7 | Assinatura não contém e-mail Finaud | **Retenção** com alerta para Michel — nada entra no painel sem identificação do responsável |

---

**Casos com exemplos reais do histórico:**

**Reply-To = cliente externo (98,1% dos casos):**
`"'Leonardo Ueda' via Suporte" <suporte@finaud.com.br>` → Reply-To: `Leonardo.Ueda@westernunion.com`
→ remetente real = Leonardo (Western Union — cliente) → Finaud precisa responder

**Reply-To = endereço filtrado — noreply@, notificação automática (1,5% dos casos):**
`"'Facebook' via Suporte" <suporte@finaud.com.br>` → Reply-To: `noreply@facebookmail.com`
→ endereço filtrado → **Descarte**
*(Outros exemplos reais: renovação 3CX, formulário Privacy Tools)*

**Reply-To vazio — Finaud respondeu via grupo (0,5% dos casos):**
→ um colaborador Finaud enviou via suporte@ mas sem Reply-To preenchido
→ o sistema lê a **assinatura do corpo do e-mail** (Campo 6) para identificar o colaborador responsável
→ se encontrar assinatura com e-mail Finaud → colaborador identificado
→ se não encontrar → **Retenção** com alerta para Michel — nada entra no painel sem identificação do responsável

> **Regra universal (confirmada por Michel, 04/08/2026):** nenhum e-mail entra no painel sem identificação completa — cliente e colaborador responsável. Se qualquer um dos dois não puder ser identificado por nenhum meio disponível → Retenção com alerta.
>
> **Exceção — thread nova sem responsável (confirmada por Michel, 04/08/2026):** quando o cliente é identificado mas ainda não há colaborador Finaud designado (ninguém respondeu ainda), a thread entra no painel como "Aguardando Finaud — sem responsável". Não vai para Retenção. Quando um colaborador responder, a IA o identifica automaticamente e o registra como responsável da thread.

**Thread nova sem responsável (cliente enviou para suporte@ pela primeira vez):**
→ entra no painel como "Aguardando Finaud — sem responsável"
→ quando um colaborador da Finaud responder, a IA o identifica e o registra como responsável
→ enquanto ninguém responde: visível no painel, sem nome de responsável

---

### Campo 5 — Assunto

**O que é:** o título do e-mail — o campo "Assunto:" que aparece na caixa de entrada.

**Para que o sistema usa:** ajudar a IA a identificar a categoria da thread. O assunto **não** é usado para descartar e-mails — filtragem é responsabilidade exclusiva do Campo 1 (remetente) e Campo 4 (Reply-To).

> **Regra (05/08/2026):** o assunto sozinho nunca descarta um e-mail. Os e-mails automáticos ("Risk Driver -", "Relatório do Serviço", "FogBugz" etc.) são descartados pelo remetente que os gera — `riskdriver@finaud.com.br`, `contato@finaud.com.br`, `do-not-reply@finaud.fogbugz.com`, `comunicacao@comunicacao.bcb.gov.br`. Um cliente que encaminha ou responde um desses e-mails chega com um remetente diferente e **não é descartado** — segue normalmente para o classificador.

**Como o sistema processa — passo a passo:**

| Passo | Condição | Ação |
|---|---|---|
| 1 | Assunto passou nos filtros de remetente (Campo 1 + Campo 4) | Continua processamento — Campo 6 (corpo) será lido |
| 2 | Assunto contém código CADOC explícito (DDR, DRM, DLO, DLI, DRL, 4111, 2011, 2060, 2061, 2062, 2160) | Classificador determina a categoria pelo assunto; corpo complementa |
| 3 | Assunto não contém código CADOC | Classificador lê o corpo completo para determinar a categoria |
| 4 | Classificador não consegue determinar a categoria | E-mail vai para a **Tela de Revisão** — Michel classifica manualmente |

---

#### Uso 1 — Classificar a categoria

| O assunto tem | Casos no histórico | O que acontece |
|---|---|---|
| Código CADOC explícito (DDR, DRM, DLO, DLI, DRL, 4111, 2011, 2060, 2061, 2062, 2160) | 4.088 (46,3%) | Classificador determina a categoria pelo assunto |
| Sem código explícito | 2.843 (32,2%) | Classificador lê o corpo completo para determinar |
| Classificador não consegue determinar | Estimado < 1% (baseado em 764/768 no histórico) | **Tela de Revisão** — Michel classifica manualmente |

**Assunto vazio:** não ocorreu em nenhum dos 8.825 e-mails do histórico. Se ocorrer → Tela de Revisão.

---

### Campo 6 — Corpo (texto da mensagem)

**O que é:** o texto escrito que está dentro do e-mail — o conteúdo que a pessoa digitou, não os anexos nem o assunto.

**Para que o sistema usa:** criar uma **cópia limpa** do texto para o classificador usar — o e-mail original é sempre preservado intacto no sistema. A cópia limpa remove tudo que não é conteúdo novo (assinatura, histórico antigo, rodapé automático). O §8 (status da thread) e o Campo 4 (identificação do colaborador) leem o e-mail original diretamente — nunca a cópia. O classificador recebe apenas a cópia limpa.

**Como o sistema processa — passo a passo:**

| Passo | O que acontece |
|---|---|
| 1 | Gmail entrega o corpo em HTML ou texto puro |
| 2 | Sistema converte HTML → texto puro (se necessário) |
| 3 | SE `From = suporte@finaud.com.br` E Reply-To vazio: extrai o e-mail do colaborador da assinatura **antes** de limpar (Campo 4 precisa dessa informação — se limpar primeiro, perde para sempre) |
| 4 | Aplica regras L1–L5 e L7–L8 em ordem: remove assinatura, histórico citado, rodapé automático e marcadores de imagem *(OCR — leitura de imagens — entra em fase futura; ver §13-Futuro)* |
| 5 | Se corpo ficar vazio após limpeza: (a) thread existente — mantém a classificação já registrada; §8 atualiza o status lendo o texto original; (b) thread nova — vai para **Tela de Revisão** |
| 6 | Texto limpo vai para o classificador |

> **Regra obrigatória — extrair colaborador antes de limpar (Campo 4):** quando De = `suporte@finaud.com.br` e Reply-To está vazio, o sistema extrai o e-mail do colaborador da assinatura do corpo **antes** de aplicar as regras de limpeza. Só então remove a assinatura. Se a extração acontecer depois da limpeza, a informação do responsável se perde para sempre.

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

#### O que temos — Análise das 12 categorias (30/07/2026)

**6.989 e-mails analisados** via `scripts/consultas/analisar_corpo_emails.py` (30/07/2026).  
Fonte: `oraculo_360_finaud` — histórico completo de produção.

| # | Categoria | E-mails | Assinatura | Hist. `>` | Hist. `---` | Rodapé | `[image:]` | `[cid:]` |
|---|---|---|---|---|---|---|---|---|
| 1 | DDR_2011 | 2.350 | 96,4% | 37,1% | 22,1% | 95,5% | 23,9% | 18,9% |
| 2 | SALDOS_CONTABEIS_DIARIOS_4111 | 728 | 97,7% | 38,2% | 25,1% | 92,3% | 19,8% | 22,0% |
| 3 | DRM_2060 | 163 | 96,3% | 35,0% | 16,6% | 98,2% | 22,1% | 27,6% |
| 4 | DLO_2061 | 1.172 | 77,7% | 39,2% | 26,6% | 96,8% | 29,1% | 28,0% |
| 5 | DLI_2062 | 119 | 88,2% | 47,1% | 31,9% | 100,0% | 37,8% | 22,7% |
| 6 | DRL_2160 | 267 | 96,3% | 43,1% | 19,1% | 99,6% | 26,6% | 18,0% |
| 7 | S5 | 122 | 92,6% | 63,9% | 22,1%★ | 100,0% | 30,3% | 18,0% |
| 8 | RETORNO_BACEN | 1.298 | 92,2% | 50,2% | 31,3% | 100,0% | 36,3% | 41,0% |
| 9 | SUPORTE | 678 | 79,8% | 46,2% | 15,9% | 97,3% | 28,5% | 29,4% |
| 10 | FORCAPITAL | 85 | 84,7% | 29,4% | 20,0% | 100,0% | 9,4% | 36,5% |
| 11 | DRSAC_2030 | 3 | 100,0% | 66,7% | 33,3% | 100,0% | 33,3% | 33,3% |
| 12 | PVCA_6209 | 4 | 75,0% | 75,0% | 0,0% | 100,0% | 0,0% | 0,0% |
| | **TOTAL** | **6.989** | | | | | | |

★ Corrigido após fix da regra L2 (era 39,3% antes — separadores decorativos eram confundidos com histórico encaminhado). Ver REGISTRO_CORRECOES 30/07.

**O que os dados mostram:**
- **Rodapé automático** aparece em quase todos os e-mails: 92–100% em todas as categorias — remoção obrigatória
- **Assinatura** detectada em 75–100%; categorias com e-mails automáticos têm taxa menor (DLO_2061: 77,7%, SUPORTE: 79,8%) — comportamento correto, não é erro do detector
- **Histórico citado (`>`)** presente em 29–75% — varia conforme o volume de respostas de cada categoria
- **Imagens** presentes em todas as categorias; RETORNO_BACEN tem os maiores índices (36,3% `[image:]` e 41,0% `[cid:]`) porque os clientes enviam prints de tela com erros do BACEN — essas imagens são conteúdo, não decoração

---

#### O que utilizaremos

**Decisão (30/07/2026, validada por Michel):**  
Antes de passar qualquer texto para a IA classificadora, o sistema aplica as 8 regras de limpeza (L1–L8) em todos os e-mails de todas as categorias. As regras são **universais** — funcionam para as 12 categorias sem exceção por categoria.

A IA recebe apenas o **texto novo** de cada e-mail — sem assinatura, sem histórico antigo, sem rodapé, sem imagens decorativas.

---

#### Regras de negócio — L1 a L8

| Regra | Nome | O que remove | Quando aciona |
|---|---|---|---|
| L1 | Assinatura | Tudo a partir da linha de fechamento | Detecta `Att,` / `Atenciosamente` / `À disposição` / `Cordialmente` / `Desde já agradeço` / `Antecipadamente grata` / `Regards` / `Best Regards` / `Kind Regards` / `Sincerely` / `Obrigado` / `Grata` / `Grato` / `Abraços` |
| L2 | Histórico com traços | Tudo a partir da linha de traços | Detecta `-----` ou `_____` ou `=====` (5 ou mais caracteres) **somente** quando a linha seguinte contém cabeçalho de e-mail (`De:`, `Para:`, `Data:`, `From:`, `To:`, `Sent:`) — evita cortar separadores decorativos no corpo da mensagem |
| L3 | Histórico com seta | Remove linhas de reply citado | Remove linhas que começam com `>` (convenção de reply citado) |
| L4 | Rodapé de lista | Tudo a partir do rodapé | Detecta `To unsubscribe from this group` / `Para cancelar a inscrição` / `Você está recebendo este e-mail porque se inscreveu` |
| L5 | Imagem decorativa | Remove o marcador | Nome da imagem contém: `instagram`, `linkedin`, `facebook`, `youtube`, `whatsapp`, `traders logo`, `esign`, `ícone`, `site mb`, `logo` ou variações de redes sociais |
| L6 | Imagem não-decorativa | Tenta ler com OCR | Qualquer imagem cujo nome **não** contenha palavra conhecida de decorativo (L5) → aciona OCR, independente da posição no e-mail (antes ou depois da assinatura) → se texto útil: inclui no registro rotulado; se OCR falhar: e-mail vai para fila de revisão humana (não classifica) |
| L7 | ~~Imagem genérica depois da assinatura~~ | **REGRA REMOVIDA** | Removida em 04/08/2026 após simulação com dados reais: 7 de 7 imagens lidas após a assinatura continham conteúdo crítico (STA, CRD, boletas, erros do BACEN). A posição "após assinatura" **não é** sinal confiável de decorativo em e-mails de CADOC — a imagem frequentemente está no histórico citado do e-mail, que aparece depois da assinatura do reply mais recente. |
| L8 | Corpo vazio após limpeza | Decisão por tipo de thread | Se após L1–L6 o texto e o OCR ficarem vazios: **(a) thread existente** → mantém a classificação já registrada; §8 lê o texto original para atualizar o status; **(b) thread nova** → **Retenção** — corpo insuficiente para classificar |

> **Dado real (varredura 04/08/2026 — 8.825 e-mails):** 94 e-mails (1,1%) ficaram com corpo vazio após limpeza — todos eram respostas de cortesia em threads existentes ("Obrigado!", "Obrigada, Andrea!"). 32 tinham anexo, 62 não tinham. Nenhum foi thread nova — a regra "thread nova → Retenção" é teórica, nunca ocorreu no histórico.

**Regra de ouro — imagens:**  
Nenhuma imagem é descartada silenciosamente. O único critério de descarte sem OCR é o nome do arquivo conter palavra conhecida de decorativo (L5). Para todo o resto, o sistema tenta OCR. Se o OCR falhar (L6), o e-mail entra em fila de revisão humana — a IA não classifica até o revisor confirmar o conteúdo.

**Atenção — RETORNO_BACEN (fase futura):**  
Nesta categoria as imagens não são decorativas — são prints de tela com erros do BACEN e são o conteúdo principal do e-mail. Na fase atual, o classificador identifica RETORNO_BACEN pelo assunto e corpo textual. A leitura das imagens por OCR fica para fase futura — quando implementado, permitirá extrair o código da crítica, prazo de resposta e dados específicos do erro.

**Pendência L1 — variação de assinatura:**  
A palavra `Abraço` (singular, sem "s") não está no detector atual. Identificada na categoria DLI_2062. Adicionar antes de construir o módulo de limpeza. Ver `documentações/PENDENCIAS.md`.

---

#### Por que a posição no e-mail não decide — entendendo o comportamento real

Em e-mails de CADOC, o histórico da conversa fica embutido no corpo como texto citado (linhas com `>`). As imagens enviadas em replies anteriores aparecem como marcadores `[image:]` dentro desse histórico — **depois** da assinatura do e-mail mais recente. Isso é diferente de e-mails de consumidor, onde imagens após a assinatura são quase sempre logos decorativos do rodapé.

```
[e-mail mais recente — assinatura de quem está respondendo]
Att,
Andrea Inacio

[histórico citado do e-mail anterior — conteúdo real aqui]
> Ao transmitirmos a remessa DRM (2060), o STA retorna:
> [image: image.png]   ← BACEN error screenshot. Está APÓS a assinatura, mas é o conteúdo principal
```

**Simulação realizada em 04/08/2026:** 7 imagens lidas que estavam posicionadas após a assinatura — todas continham conteúdo crítico:

| Arquivo | Categoria | Conteúdo encontrado |
|---|---|---|
| `90781_image.png` | RETORNO_BACEN | Screenshot Gmail com erro BACEN VCRD3001, DRM_2060, data-base 31/12/2025 |
| `90916_image.png` | RETORNO_BACEN | STA: protocolo 364778868, DDR_2011, "Arquivo entregue ao destinatário", 03/02/2026 |
| `91306_image.png` | DLO_2061 | Screenshot do sistema de arquivos com pastas de clientes com DLO pendente |
| `91524_image.png` | DRL_2160 | Tela do RiskDriver, módulo DRL > Cálculo, data-base em branco |
| `91867_image.png` | DDR_2011 | Boleta financeira: NTN-B 760199, R$87,7M, Planner Corretora + BRADESCO |
| `91864_image.png` | RETORNO_BACEN | STA "Movimentação de arquivos": protocolo 371298848, DRL_2160, entregue 19/02/2026 |
| `93334_image.png` | RETORNO_BACEN | CRD Indício de qualidade: DLO00116, Planner Corretora, protocolo 357561053, prazo 17/03/2026 |

**Conclusão:** 0 de 7 eram decorativos. A regra L7 foi removida com base nessa evidência.

---

#### Padrões de imagem identificados no histórico (04/08/2026)

**Base:** varredura de 51.085 imagens distribuídas em 171 padrões distintos de nome de arquivo (fonte: `oraculo_360_finaud`, dados históricos completos). Imagens lidas diretamente para confirmar o conteúdo real — o nome do arquivo nem sempre reflete o que está dentro.

**Como o sistema decide — dois momentos em sequência:**

**Momento 1 — Decide se vai tentar ler:**

| O sistema observa | Decisão | Motivo |
|---|---|---|
| Nome contém palavra conhecida de decorativo (`logo`, `instagram`, `linkedin`, `facebook`, `youtube`, `whatsapp`, `ícone`, `site mb`, `esign`, `traders logo`, `x`, `app store`, `google play`) | ❌ Descarta sem tentar — regra L5 | Esses nomes identificam decorativo com alta confiabilidade — nunca foram encontrados com conteúdo relevante |
| Nome é `imagem removida pelo remetente` ou variações | ❌ Descarta sem tentar | O próprio Gmail indica que a imagem não existe mais — não há nada a ler |
| Nome é gerado pelo Gmail como descrição automática (ex: `fundo preto com letras brancas descrição gerada automaticamente`, `ícone descrição gerada automaticamente`) | ❌ Descarta sem tentar | O Gmail já tentou descrever a imagem — é sempre um logo ou ícone decorativo |
| Todo o resto — nome genérico, nome descritivo, qualquer posição no e-mail | ✅ Tenta OCR (regra L6) | Simulação mostrou que imagens com qualquer outro tipo de nome podem conter conteúdo crítico |

**Momento 2 — Decide o que fazer com o resultado do OCR:**

| OCR encontrou | Decisão |
|---|---|
| Código de CADOC (DDR, DRM, DLO, DLI, DRL, SCD, PVCA, DRSAC), protocolo BACEN, prazo de resposta, data-base, dados financeiros (valor, saldo, taxa, vencimento), mensagem de erro de sistema, texto de sistema regulatório (CRD, STA, RiskDriver) | ✅ Aceita — texto vai para o registro rotulado como origem imagem |
| Apenas nome de empresa, slogan ou imagem sem texto reconhecível | ❌ Descarta — era decorativo apesar de ter sido lido |
| OCR falhou (não conseguiu extrair texto) | ⚠️ Fila de revisão humana — IA não classifica o e-mail |

---

##### Padrões catalogados — Grupo 1: Descartar sem ler (nome identifica decorativo)

| Padrão de nome | O que é | Exemplo real encontrado |
|---|---|---|
| `Outlook-GUID.png`, `Outlook-GUIDáfico N,.png` | Logo de empresa embutido pelo Outlook — o Outlook automaticamente rotula logos incorporados como "Gráfico N" | `57518_Outlook-Gráfico 4,.png` (DLO) — logo da Executive Corretora de Câmbio |
| `NOME N anos.png` (ex: `HEBERT 22 anos.png`) | Badge de aniversário do colaborador com foto, cargo e empresa — enviado automaticamente pelo sistema de RH | `65475_HEBERT 22 anos.png` (DLO) — Hebert Dias, Departamento Fiscal, MR Henrique Advogados |
| `linkedin`, `instagram`, `facebook`, `youtube`, `whatsapp`, `x`, `app store`, `google play`, `traders logo`, `logo eqi`, `www.guru.com.vc`, `site mb`, `esign` | Ícone de rede social ou logo de empresa na assinatura do e-mail — identificados pelo nome no marcador `[image:]` | Encontrados em milhares de e-mails em todas as categorias — regra L5 já os cobre |
| `imagem removida pelo remetente` e variações | O remetente removeu a imagem antes de encaminhar — não existe arquivo | 594 ocorrências identificadas na varredura — descartar sem tentar |
| `fundo preto com letras brancas descrição gerada automaticamente com confiança média`, `ícone descrição gerada automaticamente` e similares | O Gmail gerou automaticamente uma descrição de texto alternativo para um logo ou ícone — indica imagem decorativa | 699 ocorrências combinadas identificadas na varredura |

---

##### Padrões catalogados — Grupo 2: Ler com OCR (nome identifica conteúdo relevante)

Estes padrões têm conteúdo relevante com alta confiabilidade. OCR obrigatório; falha no OCR → fila de revisão humana.

| Padrão de nome | O que é | Categorias onde aparece | O que o OCR vai extrair |
|---|---|---|---|
| `Inconsistencia N.png`, `Indicio N.png` | E-mail do BACEN ao cliente sobre inconsistência ou indício de qualidade, encaminhado como imagem | RETORNO_BACEN | Tipo do CADOC, código da inconsistência, data-base, protocolo BACEN, prazo de resposta |
| `pagina_N.png` | Screenshot do Gmail mostrando e-mail do BACEN — o cliente tirou print da tela e enviou | RETORNO_BACEN | Mesmos dados: código de crítica, protocolo, prazo, data-base |
| `docx_image.png` | Screenshot do navegador aberto no sistema CRD do BACEN (www3.bcb.gov.br/crd2) | RETORNO_BACEN | Inconsistência, razão social do cliente, data-base, protocolo BACEN, prazo |
| `BACEN LIM N.png` | Print do sistema CRD mostrando indício de qualidade (tipo Aviso ou Alerta) | DLO, DRM | Tipo de indício, identificação do documento (DLO/DRM), protocolo, tolerância concedida |
| `Critica BACEN.PNG`, `Critica BACEN N.PNG` | Tela do sistema interno RiskDriver mostrando críticas do BACEN para aquele cliente | DRM, DLO, DDR | Código da crítica BACEN, CADOC afetado, ações de substituição disponíveis |
| `informações adicionais DRL MM.AAAA.png` | Resumo financeiro da carteira compartilhado via Microsoft Teams pelo cliente | DRL | Saldos: Compromissadas, TVM, totais — serve como data de competência se não estiver no assunto ou corpo |
| `Índice de Basiléia *.png`, `Basileia *.png` | Gráfico do Índice de Basiléia — indicador de solidez financeira regulatório | SUPORTE, FORCAPITAL | Percentual atual, data de referência, mínimo regulatório (8%) |
| `RWACPAD_erro.png`, `ERRO_PLANILHA LEC.png` e similares com `erro` no nome | Screenshot de erro no sistema RiskDriver, enviado pelo cliente para relatar o problema | SUPORTE, DLO, DDR, DRM | Tipo de erro, módulo afetado, mensagem de erro exata |

**Exemplos reais verificados:**
- `92241_pagina_01.png` (RETORNO_BACEN) → screenshot do Gmail com e-mail do BACEN: DLO00115, BARU CTVM, data-base 12/2025, prazo 04/03/2026
- `94928_docx_image.png` (RETORNO_BACEN) → CRD do BACEN: DLO00115, AMARIL FRANKLIN, data-base 02/2026, prazo 17/04/2026
- `98277_BACEN LIM 2062.png` (DLO) → CRD indício DLI206200007, GURU CORRETORA, tolerância até 06/2026
- `48707_Critica BACEN.PNG` (DRM) → RiskDriver: críticas 2282/2283 para DRM com ações de substituição
- `66575_informações adicionais DRL 10.2025.png` (DRL) → Teams: Compromissadas R$67,7M, TVM R$156,3M

---

##### Padrões catalogados — Grupo 3: Nome genérico, OCR decide pelo conteúdo

Estes padrões não identificam o conteúdo pelo nome — o sistema lê e decide com base no que o OCR encontrou.

| Padrão de nome | O que pode conter | Categorias encontradas | Por que OCR é obrigatório |
|---|---|---|---|
| `image.png`, `imagem.jpg`, `image001.png` e similares | Erro do BACEN, confirmação STA, tela de sistema regulatório, print de e-mail — OU logo de empresa, rodapé decorativo | Todas as categorias | Em RETORNO_BACEN, `image.png` é quase sempre o print da crítica do BACEN — o único conteúdo relevante do e-mail. Descartá-la por nome seria perder a informação principal. |
| `{GUID}.png` (ex: `{04D86327-7AFB-46FA-9A35-E937AEE50AC2}.png`) | Tabela financeira com dados de carteira — OU logo de empresa embutido via GUID | SUPORTE (tabela R$39,7B), DLO (logo Executive Corretora) | O mesmo padrão de nome produz conteúdos completamente diferentes dependendo do contexto do e-mail |
| `NNNNNN.jpg`, `NNNNNN.png` (só números no nome, 6+ dígitos) | Relatório financeiro (ex: NE 17 com Patrimônio de Referência, RWA, breakdown de riscos) | SUPORTE | Nome é um protocolo ou ID interno — o conteúdo real só é conhecido após leitura |
| `Captura de tela AAAA-MM-DD HHMMNN.png` | Screenshot de qualquer sistema — RiskDriver, planilha, sistema contábil | Qualquer categoria | Captura genérica de tela — pode ser relevante (erro de sistema) ou não (captura acidental) |

**Regra de contexto — mesmo nome, conteúdo diferente por categoria:**

| Padrão de nome | Na categoria... | O conteúdo tende a ser... | Na categoria... | O conteúdo tende a ser... |
|---|---|---|---|---|
| `image.png` | DRM, DDR, SCD | Logo da empresa na assinatura ou rodapé | RETORNO_BACEN | Print do erro ou da crítica do BACEN — conteúdo principal |
| `{GUID}.png` | DLO | Logo de empresa embutido automaticamente | SUPORTE | Tabela financeira com dados de carteira do cliente |

**Como o sistema resolve:** a categoria da thread é determinada pelo classificador antes de qualquer leitura de imagem. O contexto da categoria informa qual interpretação é mais provável — mas o OCR confirma. Se o OCR encontrar texto relevante, aceita; se encontrar apenas nome de empresa ou nada, descarta.

---

#### Campo OCR — estrutura de armazenamento e formato para a IA

Quando o sistema lê uma imagem com OCR, o texto extraído **não é misturado ao corpo do e-mail**. Fica guardado num campo separado no registro do e-mail, com identificação clara de origem. Isso garante que a IA saiba de onde veio cada trecho de informação — evitando confusão entre o que o cliente escreveu e o que estava dentro de uma imagem.

**Estrutura do campo no registro:**

```json
"ocr_imagens": [
  {
    "arquivo": "image.png",
    "posicao": "corpo",
    "conteudo": "Protocolo 364778868 - ALIM211 (2011)\nEstado: Arquivo entregue ao destinatário\nData: 03/02/2026\nGURU CTVM LTDA → BANCO CENTRAL DO BRASIL",
    "status": "lido"
  },
  {
    "arquivo": "logo_linkedin.png",
    "posicao": "corpo",
    "conteudo": "",
    "status": "descartado"
  },
  {
    "arquivo": "critica_bacen.png",
    "posicao": "anexo",
    "conteudo": "",
    "status": "falhou"
  }
]
```

**Valores do campo `status`:**
- `lido` — OCR extraiu texto com conteúdo útil
- `descartado` — nome identificado como decorativo (L5) ou OCR não encontrou conteúdo útil
- `falhou` — OCR tentou mas não conseguiu extrair texto → e-mail vai para fila de revisão humana

**Valores do campo `posicao`:**
- `corpo` — imagem estava embutida no corpo do e-mail (marcador `[image:]` ou `[cid:]`)
- `anexo` — imagem chegou como arquivo anexo `.png` / `.jpg` (Campo 7)

> **Nota:** as regras de decisão para imagens em anexo (Campo 7) são as mesmas que para imagens no corpo — Momento 1 (decidir se tenta) e Momento 2 (decidir pelo conteúdo do OCR). A diferença é só a origem física do arquivo. O campo `posicao` registra essa distinção para rastreabilidade.

**Como o texto do OCR chega para a IA classificadora:**

O texto extraído não é inserido diretamente no fluxo do corpo — é enviado separado, rotulado, para que a IA entenda a fonte:

```
[IMAGEM: image.png]
Protocolo 364778868 - ALIM211 (2011)
Origem: GURU CTVM LTDA
Destino: BANCO CENTRAL DO BRASIL
Estado: Arquivo entregue ao destinatário
Data: 03/02/2026
[FIM DA IMAGEM]
```

**Por que o rótulo é obrigatório:** sem o rótulo, a IA poderia interpretar o conteúdo da imagem como texto escrito pelo cliente — e fazer inferências incorretas sobre quem disse o quê, ou confundir dados históricos (dentro da imagem) com dados do e-mail atual.

**Por que o campo OCR é guardado no registro permanente — e não só usado na classificação:**

A IA Assistente de Aprendizado precisa do conteúdo das imagens para entender como cada caso foi resolvido. Em categorias como RETORNO_BACEN, a crítica do BACEN (código, protocolo, prazo) está **dentro da imagem** — sem esse texto guardado, o aprendizado fica cego para o problema que a Finaud precisou resolver. O campo `ocr_imagens` é portanto um campo permanente do registro, não um dado temporário de processamento.

---

### Campo 7 — Anexos

**O que é:** os arquivos em anexo — documentos que o cliente ou a Finaud envia junto com o e-mail.

**Para que o sistema usa:** é o sinal mais forte de categoria quando existe — um ZIP no padrão `CNPJ_CADOC_DATA.zip` identifica a categoria sem precisar ler nem o assunto nem o corpo. Mas em 67% dos e-mails não há anexo; nesses casos o campo não participa da classificação.

**Como o sistema processa — passo a passo:**

| Passo | Condição | Ação |
|---|---|---|
| 1 | Sem anexo | Campo não participa — IA usa assunto + corpo |
| 2 | ZIP com padrão `CNPJ_CADOC_DATA.zip` | Categoria identificada com altíssima confiança |
| 3 | ZIP com sufixo `_S_N` | Substituição solicitada pelo BACEN — mesma categoria |
| 4 | Arquivo COSIF (`.xml`, `.bc`) ou planilha LEC | DLO, DLI, S5 ou FORCAPITAL — ver regra COSIF abaixo |
| 5 | Prefixo `RD_` | DDR_2011 — arquivo do cliente |
| 6 | Formatos especiais (`.rar`, `.eml`) | Abrir e ler conteúdo interno |
| 7 | ZIP genérico (sem padrão CADOC no nome) | Abrir e verificar arquivos internos |
| 8 | Imagem em anexo (`.png`, `.jpg`, `.jpeg`) | Aplicar as mesmas regras de imagem do Campo 6: Momento 1 (nome identifica decorativo? → descarta) + Momento 2 (OCR decide pelo conteúdo). Ver seção "Campo OCR" acima. |
| 9 | Nenhum padrão reconhecível | Sinal insuficiente — IA usa assunto + corpo |

**Cobertura verificada em 6.989 e-mails (03/08/2026):**

| Categoria | Emails | Sem anexo | ZIP CADOC | COSIF | RD_ | Sem padrão no nome |
|---|---|---|---|---|---|---|
| DDR_2011 | 2.395 | 60% | 7% | 0% | 10% | 20% |
| SALDOS_CONTABEIS_DIARIOS_4111 | 734 | 75% | 11% | 0% | 0% | 7% |
| DRM_2060 | 177 | 67% | 14% | 1% | 0% | 10% |
| DLO_2061 | 1.183 | 70% | 2% | 2% | 0% | 25% |
| DLI_2062 | 136 | 85% | 5% | 0% | 0% | 9% |
| DRL_2160 | 267 | 78% | 5% | 0% | 0% | 13% |
| S5 | 132 | 69% | 0% | 0% | 2% | 16% |
| RETORNO_BACEN | 1.223 | 56% | 3% | 0% | 0% | **40% (imagens — OCR obrigatório)** |
| SUPORTE | 640 | 88% | 0% | 0% | 0% | 8% |
| **TOTAL** | **6.989** | **67%** | **5%** | **0%** | **4%** | **21%** |

*(RAR: 6 casos · EML: 8 casos · protocolo BACEN sem extensão: ~30 casos — todos abaixo de 1%)*

> **Nota — COSIF baixo (0–2%):** a maioria dos arquivos COSIF chega **dentro de ZIPs com nome genérico** (Passo 7). O sistema precisa abrir o ZIP para encontrar o `.xml` ou `.bc` interno — não é possível identificar só pelo nome externo.

---

#### Regra universal — ZIP do CADOC gerado (altíssima confiança)

Quando a Finaud entrega o CADOC ao cliente, o arquivo ZIP segue o padrão `CNPJ_CADOC_DATA.zip`. O número do CADOC está no próprio nome — identificação imediata, sem verificar assunto nem corpo.

| Categoria | Padrão do ZIP | Exemplo real |
|---|---|---|
| DDR_2011 | `CNPJ_2011_YYYYMMDD.zip` | `12345678_2011_20260630.zip` |
| SALDOS_CONTABEIS_DIARIOS_4111 | `CNPJ_4111_YYYYMMDD_I_1.zip` | `32648370_4111_20260219_I_1.zip` |
| DRM_2060 | `CNPJ_2060_YYYYMMDD.zip` | `32648370_2060_20260130.zip` |
| DLO_2061 | `CNPJ_2061_YYYYMMDD.zip` | `12345678_2061_20260630.zip` |
| DLI_2062 | `CNPJ_2062_YYYYMM_I_1_4010.zip` | `62280490_2062_202602_I_1_4010.zip` |
| DRL_2160 | `CNPJ_2160_YYYYMMDD.zip` | `12345678_2160_20260630.zip` |

**Sufixo de substituição `_S_N`:** quando o BACEN detecta erro num CADOC já entregue e solicita correção, o cliente envia um novo ZIP com `_S_1`, `_S_2`, ... no nome (ex.: `32648370_2011_20241129_S_2.zip` = segunda substituição do DDR de novembro/2024). O sistema reconhece automaticamente como CADOC do mesmo tipo — o padrão de busca captura o sufixo via `.*`. 351 casos no histórico.

---

#### Arquivos que o cliente envia para a Finaud (alta confiança)

| Categoria | O que o cliente envia |
|---|---|
| DDR_2011 | Prefixo `RD_` — ex.: `RD_MOEDA.csv`, `RD_LFT.xlsx`, `RD_PREFIXADA.xlsx`; ou `DDR_YYYYMM.xlsx` |
| SALDOS_CONTABEIS_DIARIOS_4111 | `CADOC 4111.xlsx`, `DOC_4111_YYYYMMDD.xlsx`, `Saldos 4111.xlsx` |
| DRM_2060 | `Saldos DRM.xlsx`, `DRM_2060_Finaud_YYYYMM.xlsx` |
| DLO_2061 | Arquivos COSIF + planilha LEC — ver regra COSIF abaixo |
| DLI_2062 | Arquivos COSIF **sem** planilha LEC — ver regra COSIF abaixo |
| DRL_2160 | Planilha DRL `.xlsx` |
| S5 | Arquivos COSIF — ver regra COSIF abaixo |

---

#### Regra COSIF — DLO_2061, DLI_2062, S5 e FORCAPITAL

Balancetes contábeis que o cliente extrai do seu sistema e envia para a Finaud processar. Existem dois tipos, conforme a estrutura da empresa:

| Arquivo | Empresa | Quando é enviado |
|---|---|---|
| `COS4010.xml` | Individual | Todo mês |
| `COS4016.xml` | Individual | Somente **junho e dezembro** |
| `COS4060.xml` | Conglomerado (grupo de empresas) | Todo mês |
| `COS4066.xml` | Conglomerado (grupo de empresas) | Somente **junho e dezembro** |

**Regra de envio:** todo mês o cliente manda o arquivo mensal (4010 ou 4060). Em **junho e dezembro** manda também o semestral (4016 ou 4066) — resultado: dois arquivos COSIF no mesmo e-mail.

**Para a triagem:** qualquer arquivo COSIF indica uma dessas quatro categorias. O que diferencia:

| Sinal adicional | Categoria |
|---|---|
| COSIF + planilha LEC (`LEC_*.xlsx`) | DLO_2061 |
| COSIF sem planilha LEC | DLI_2062 (confirmar pelo assunto) |
| COSIF + "S5" no assunto ou corpo | S5 |
| COSIF + "FORCAPITAL" no assunto ou corpo | FORCAPITAL |

**Formatos em que o COSIF chega:** o cliente pode enviar o arquivo COSIF de três formas — o sistema precisa reconhecer todas:

| Formato | Extensão | Casos no histórico | Observação |
|---|---|---|---|
| XML direto como anexo | `.xml` | 642 | Padrão atual — `COS4010.xml`, `40602412.XML`, `4060 NomeCliente MM.AAAA.xml` |
| BC formato antigo | `.bc` | 123 | Usado até ~2023; dados retroativos ainda chegam com essa extensão |
| Dentro de ZIP com nome genérico | `.zip` | Varia | ZIP sem padrão CADOC no nome — precisa ser aberto para identificar o XML/BC interno |

---

#### Categorias sem padrão de nome de anexo

| Categoria | Situação |
|---|---|
| RETORNO_BACEN | XMLs de rejeição CRD e PDFs de prints de erro — nomes genéricos, sem padrão. OCR necessário (PENDENCIAS.md) |
| SUPORTE | Qualquer arquivo ou nenhum — o anexo não identifica a categoria |
| FORCAPITAL | Planilha ou PDF de projeção — sem padrão de nome específico |
| DRSAC_2030 | Arquivo DRSAC para análise — sem padrão específico |
| PVCA_6209 | Arquivo PVCA para análise — sem padrão específico |

---

#### Decisões sobre casos difíceis — validadas com histórico de 8.825 e-mails

| Questão | Decisão |
|---|---|
| ZIP dentro de ZIP | 0 casos no histórico (300 ZIPs verificados em disco). Regra: se o nome externo for genérico, abrir um nível e ler nomes internos; nunca recursivo além disso |
| E-mail com muitos anexos | Verificar TODOS os nomes — máximo encontrado foi 37 (DDR com vários dias), mediana ≤ 4 |
| Nome genérico sem pista (`image.png`, `documento.pdf`) | Ignorar para classificação — 39,4% são genéricos mas quase todos são `image.png` / `image001.png`, tratados em Campo 6 (L5–L7) |
| Tamanho do arquivo | Sem limite na triagem (lê só o nome). Para leitura de conteúdo (OCR, fase futura): limite sugerido de 25 MB — maior arquivo encontrado foi 18,26 MB |

#### Formatos especiais e casos de borda

| Formato | Casos no histórico | Regra |
|---|---|---|
| `.RAR` | 6 | Mesma lógica do ZIP — tentar abrir e ler nomes internos. Se não conseguir: flag para revisão humana |
| `.EML` (e-mail encaminhado como anexo) | 8 | Extrair assunto e anexos do e-mail interno e aplicar as regras de classificação normais. Prioritário para RETORNO_BACEN |
| Sem extensão — nome embaralhado | ~200 | Encoding quebrado no parser (`=_utf-8_B_...`). Classificar pelo assunto e corpo; marcar como VERIFICAR_NOME para registro |
| Sem extensão — código de protocolo BACEN | ~30 | `ADRM060-...` = DRM_2060 · `ALIM262-...` = DLI_2062 — sinal forte de categoria, usar direto |

---

### Campo 8 — Thread ID e Data

**O que é:** dois identificadores que chegam junto com cada e-mail — o código da conversa (Thread ID) e as datas associadas. A data de competência (o mês ao qual o CADOC se refere) é extraída pela IA a partir do assunto ou do nome do anexo.

**Para que o sistema usa:** três coisas em paralelo:
1. **Thread ID** → agrupa todos os e-mails da mesma conversa em um único caso na tela do gestor
2. **data_email** → registra quando o e-mail chegou (sempre disponível)
3. **data_competencia** → base para calcular o prazo regulatório — sem ela, o sistema não monitora prazo

**Como o sistema processa — passo a passo:**

| Passo | O que acontece |
|---|---|
| 1 | Thread ID extraído do Gmail — sempre preenchido (100% nos 8.825 e-mails do histórico) |
| 2 | data_email extraída do Gmail — sempre preenchida |
| 3 | IA extrai data_competencia do assunto e do nome do anexo (ver regras abaixo) |
| 4 | data_competencia preenchida → sistema calcula e monitora o prazo regulatório |
| 5 | data_competencia = null → sistema não monitora prazo para este caso |

---

#### Os três conceitos e como se conectam

**`data_email`** — a data e hora em que o e-mail chegou na caixa. O Gmail sempre fornece, nunca está vazio. Indica *quando* a mensagem foi recebida, mas não *de qual mês* é o relatório.

**`data_competencia`** — o mês e ano a que o CADOC se refere. Extraída pela IA do assunto ou do nome do anexo. É a data de referência do relatório — não tem relação com quando o e-mail chegou.

> **Exemplo:** cliente envia em 05/02/2026 o DDR com assunto "DDR 02/02/2026".
> `data_email` = 05/02/2026 (quando chegou na caixa)
> `data_competencia` = 02/02/2026 (data do relatório — pode ser diferente da data de envio)

**`prazo`** — o limite regulatório para entrega daquele CADOC. **Não vem do e-mail** — é calculado pelo sistema combinando a `data_competencia` com a regra da categoria (definida no §10). Cada categoria tem sua própria fórmula:

| Categoria | Fórmula do prazo | Exemplo com data_competencia = 02/02/2026 |
|---|---|---|
| DDR_2011 | D+3 úteis após a data de referência | prazo = 05/02/2026 (quarta) |
| SALDOS_CONTABEIS_DIARIOS_4111 | D+3 úteis após a data de referência | prazo = 05/02/2026 |
| DRM_2060 | D+5 úteis do mês seguinte | prazo = 06/03/2026 |
| DLO_2061 | Dia 5 do 2º mês seguinte | prazo = 05/04/2026 |
| DLI_2062 | Dia 5 do 2º mês seguinte | prazo = 05/04/2026 |
| DRL_2160 | D+10 úteis do mês seguinte | prazo = 12/03/2026 |
| S5 | D+5 úteis após a data de referência | prazo = 09/02/2026 |
| FORCAPITAL | D+5 úteis após a data do e-mail | usa data_email, não data_competencia |
| SUPORTE | Sem prazo regulatório | — |
| RETORNO_BACEN | Prazo definido pelo BACEN na crítica | extraído do corpo do e-mail |
| DRSAC_2030 | 10º dia útil do 2º mês após data-base | base jun → 10º DU de agosto |
| PVCA_6209 | Último DU do mês seguinte ao trimestre | base 30/jun → último DU de julho |

**Como o sistema usa os três:**

```
data_email       → registra quando chegou (histórico + cálculo FORCAPITAL)
data_competencia → identifica o mês do relatório
categoria        → define a fórmula do prazo
prazo            → calculado: data_competencia + fórmula da categoria
```

Na tela, o gestor vê: **cliente · categoria · data de competência · prazo · status**

Se `data_competencia = null` → o sistema não calcula prazo e não exibe no painel de monitoramento. A thread aparece apenas no histórico, não na fila de prazos.

---

#### Thread ID

O Thread ID (`thread_root` no histórico atual / `threadId` na Gmail API) é o código que agrupa todos os e-mails de uma mesma conversa. Serve para três coisas:

1. **Manter o caso unido na tela do gestor** — todos os e-mails de uma conversa aparecem como uma única linha no painel, não como itens separados
2. **Determinar o status atual** — o sistema pega o último e-mail da thread (pelo Thread ID) e aplica as regras do §8
3. **Guardar o histórico completo para a IA aprender (Fase 2)** — o Thread ID é a chave que une toda a história de um caso: primeiro contato, arquivos trocados, erros, resolução

Cada valor único de Thread ID = um caso distinto na tela do gestor.

---

#### Campos de data

O sistema armazena dois campos de data por e-mail:

| Campo | O que é | Como obtém | Sempre preenchido? |
|---|---|---|---|
| `data_email` | Quando o e-mail chegou na caixa | Extraído diretamente do Gmail | Sim |
| `data_competencia` | O mês/ano a que o CADOC se refere | Extraído do assunto ou nome do anexo pela IA | Não — pode ser `null` |

**Por que os dois são necessários:** o prazo regulatório é calculado a partir da competência, não da data do e-mail. Um DDR de janeiro entregue em fevereiro tem prazo calculado sobre 31/01 — se o sistema usasse só a data do e-mail, nunca saberia se estava atrasado.

**Como a IA extrai a `data_competencia`:**
- Data explícita no assunto ou anexo (`01/2026`, `jan/2026`, `DRM 12.2025`, `YYYYMMDD` no nome do ZIP) → extrai diretamente
- Só o mês por extenso sem ano (`DLI DEZEMBRO`, `DRM JANEIRO`) → infere o ano pela data do e-mail como âncora: se o mês mencionado ≤ mês do e-mail, usa o mesmo ano; se maior, usa o ano anterior. Validado com 157 casos do histórico — 100% de acerto nos 5 casos com confirmação via anexo
- Dois meses no assunto (`Fevereiro e Março`) → registra ambos como competências separadas
- Nenhum mês detectável → registra `null`

**Regra de monitoramento de prazo (decidida por Michel, 31/07/2026):**
> `data_competencia` preenchida → o sistema calcula e monitora o prazo regulatório normalmente.  
> `data_competencia = null` → o sistema **não monitora prazo** para esse caso. Não há como calcular sem a data de referência.

---

#### Threads de canal

Threads com 10 ou mais e-mails **ou** abrangendo 3 ou mais meses calendário são chamadas de "threads de canal". Representam 1,8% do total (59 threads no histórico de 8.825 e-mails). O tratamento depende do conteúdo:

| Tipo | Exemplo real | Como identificar | Tratamento na Camada 2 |
|---|---|---|---|
| **Entrega recorrente** | SSG / 4111 (97 e-mails, 5 meses) | Mesmo assunto; novos anexos chegam periodicamente; nome do arquivo não traz data | Cada e-mail com anexo válido = novo item independente na Camada 2 |
| **Coordenação** | UNICRED / DDR (40 e-mails, 0 anexos) | Zero anexos regulatórios em toda a thread | Nenhum item na Camada 2 — apenas comunicação operacional |
| **Caso complexo** | EQI CTVM / RETORNO_BACEN (37 e-mails, 1 competência) | Um único CADOC; muitas rodadas de correção; competência fixa no assunto | Um único item na Camada 2 — status em aberto até o BACEN aceitar a correção |

**Regra especial para 4111 (entrega recorrente diária):**
O CADOC 4111 é uma posição diária — o cliente envia no mesmo dia da data de referência. O arquivo se chama sempre `CADOC 4111.xlsx` sem data no nome. Por isso: `data_competencia` = `data_email`.

> Validado com os dados históricos — 31/07/2026.

---

## 8. Regras de classificação das threads

Como o sistema decide se uma thread está **Aguardando Finaud**, **Aguardando Cliente** ou **Concluída**. Regras confirmadas por Michel (23/07/2026) com base no motor de triagem atual.

A classificação olha sempre o **último e-mail da thread** — não o histórico completo. Isso garante que o status reflita sempre o estado atual, não o estado passado.

---

### 8.1 Aguardando Finaud

O caso está com a Finaud — ela precisa agir.

| Situação | Exemplo |
|---|---|
| Último e-mail é do cliente para a Finaud | Cliente enviou dados, perguntou algo, mandou documento |
| Último e-mail é interno (Finaud → Finaud) | Andrea encaminhou para Monica cuidar — ainda não foi para o cliente. **Exceção:** se o e-mail interno é um forward de entrega já feita ao cliente → ver **§8.6** |

---

### 8.2 Aguardando Cliente

O caso está com o cliente — ele precisa agir.

| Situação | Exemplo |
|---|---|
| Último e-mail é da Finaud para o cliente | Finaud respondeu, pediu algo, enviou arquivo |
| Último e-mail é de cliente para cliente | Cliente repassa internamente sem responder à Finaud |

---

### 8.3 Concluída

O caso foi encerrado. As regras abaixo são as mesmas para todos os tipos de e-mail (DDR, SCD, DLO, DLI, DRM, S5, SUPORTE, RETORNO_BACEN, FORCAPITAL, DRSAC, PVCA).

**Regra especial — "transmitido no BACEN" encerra independente de quem mandou (confirmado por Michel, 03/08/2026):**
Se o texto novo do último e-mail contiver "transmitido no BACEN" (ou variação: "transmitida no BACEN"), o caso é Concluída independente de quem mandou. Quando é o cliente que avisa a transmissão, é sinal de que o CADOC já foi entregue e o caso está encerrado.

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

**Regra de escopo — aplicar apenas ao texto novo, não ao histórico citado (confirmado por Michel, 03/08/2026):**
O sistema aplica as regras de encerramento apenas ao texto da nova mensagem. O conteúdo citado do histórico — linhas que começam com `>` ou separadas por `---` — é ignorado na verificação de status. Isso evita que um "ok" ou "obrigado" de uma troca antiga, presente no histórico citado, feche indevidamente um caso em aberto.

**Veto universal (impede o Concluído mesmo com as regras acima):**
Se após a ação da Finaud o cliente mandou algo com conteúdo real — uma pergunta, um dado novo, uma reclamação — o caso **não fecha**. A bola voltou para a Finaud.

O veto se aplica mesmo quando a mensagem começa com agradecimento: se o mesmo e-mail contiver uma pergunta ou pedido novo além do agradecimento, o caso não fecha — o agradecimento não cancela o conteúdo novo. *(confirmado por Michel, 03/08/2026)*

**Regra universal — frases de cortesia após entrega = Concluído (confirmado por Michel, 29/07/2026):**
Se o arquivo foi entregue e a mensagem seguinte — de qualquer colaborador da Finaud ou do cliente — contém apenas frase de cortesia, agradecimento ou assinatura padrão sem novo pedido, a thread é **Concluída**.

| Frases que NÃO reabrem nem bloqueiam o Concluído | Porque |
|---|---|
| "Desde já agradeço e permaneço à disposição" (assinatura do colaborador Finaud) | Encerramento cortês após entrega — não é pedido |
| "Obrigada", "Obrigado", "Valeu", "Perfeito", "Ok", "Recebido" do cliente | Confirmação de recebimento sem conteúdo novo |
| Qualquer frase de fechamento padrão sem pedido explícito | A cortesia não cria pendência |

> Aplica a: todas as 12 categorias.

**Regra adicional exclusiva do RETORNO_BACEN:**

Este tipo de thread tem dois caminhos de encerramento:

| Caminho | Como fecha |
|---|---|
| Finaud corrige e reenvia ao BACEN | ZIP enviado pela Finaud → **Concluída** (mesma regra dos CADOCs) |
| Finaud orienta o cliente a corrigir e reenviar | Cliente confirma que transmitiu ao BACEN ("transmiti", "BACEN aceitou", "protocolo gerado") → **Concluída** |

Se o cliente disser apenas "ok, vou corrigir" sem confirmar a transmissão → thread continua **Aguardando Cliente**.

> **Decisão confirmada por Michel (05/08/2026).**

---

### 8.4 Reabertura de caso

Caso estava Concluído → cliente manda nova mensagem → caso volta automaticamente para **Aguardando Finaud**.

O sistema não precisa "lembrar" que estava concluído — a lógica do último e-mail já cuida disso: se o último e-mail é do cliente, o caso é Aguardando Finaud.

> **Decisão confirmada por Michel (23/07/2026).**

---

### 8.5 Fechamento automático via ZIP — CADOCs

Aplica a: DDR_2011, SALDOS_CONTABEIS_DIARIOS_4111, DRM_2060, DLO_2061, DLI_2062, DRL_2160

Quando a Finaud envia o arquivo ZIP do CADOC por um e-mail separado — não como resposta no thread do cliente — esse e-mail chega na caixa oraculo@ pelo Caminho 2 (roteamento automático do Google Workspace). Nesses casos, o sistema faz o cruzamento automático:

| Passo | O que acontece |
|---|---|
| 1 | Sistema detecta e-mail com arquivo ZIP chegando no oraculo@ |
| 2 | Identifica o tipo de CADOC e o CNPJ do cliente pelo nome do arquivo (`CNPJ_CADOC_AAAAMMDD*.zip`) |
| 3 | Busca o thread aberto daquele cliente para aquele tipo de CADOC |
| 4 | Fecha o thread como **Concluída** |

**Regra simples:** ZIP enviado pela Finaud = thread Concluída. Não importa se o ZIP foi para o BACEN diretamente ou para o cliente.

Se o ZIP chegar mas não houver thread aberto correspondente → sistema registra alerta para revisão manual.

> **Decisão confirmada por Michel (05/08/2026).**

---

### 8.6 Regras para e-mails encaminhados (Forwards)

Mapa completo aprovado por Michel (18/08/2026).

Quando alguém encaminha um e-mail, o Gmail insere o conteúdo original dentro da mensagem. O sistema reconhece dois formatos:

| Formato | Como aparece no corpo |
|---|---|
| **A — traços** | `---------- Forwarded message ----------` seguido dos cabeçalhos De / Para / Assunto |
| **B — setas** | Cada linha do e-mail original prefixada com `>` (ex.: `> De: Andrea <andrea@finaud.com.br>`) |

**Filtro de falso positivo:** a frase "mensagem encaminhada" pode aparecer dentro de um parágrafo normal sem ser um forward real (ex.: "a mensagem encaminhada anteriormente..."). O sistema só reconhece como forward quando os traços estão presentes no Formato A, ou quando as linhas `> De:` / `> Para:` aparecem em sequência no Formato B.

---

**Os 4 cenários de forward e o status correto:**

| # | Quem encaminha | Para onde | Status | Motivo exibido |
|---|---|---|---|---|
| **1** | Finaud | Registra no suporte após entregar ao cliente | Ver sub-casos abaixo | — |
| **2** | Cliente | suporte@finaud (encaminha algo externo) | Aguardando Finaud | "Cliente escreveu — aguarda resposta da Finaud" |
| **3** | Finaud | Outra pessoa da Finaud (ação interna) | Aguardando Finaud | "E-mail interno — aguarda ação da Finaud" |
| **4** | Cliente | suporte@finaud (encaminha troca interna da empresa dele) | Aguardando Finaud | "Cliente escreveu — aguarda resposta da Finaud" |

Os cenários 2, 3 e 4 já funcionam corretamente pela lógica do último e-mail (§8.1). O §8.6 trata exclusivamente o Cenário 1.

---

**Cenário 1 — como o sistema identifica:**

O sinal é o campo `Para:` (ou `To:`) dentro do bloco forwarded. Se aponta para um endereço externo (não @finaud.com.br / @finaudtec.com.br) → é Cenário 1.

**Sub-casos e status:**

| Sub-caso | Condição | Status | Motivo exibido |
|---|---|---|---|
| **1a** | Forward para cliente + tem arquivo real (.zip, .xls, .pdf…) | Concluída | "Finaud entregou arquivo ao cliente e registrou internamente" |
| **1b — concluída** | Forward para cliente + sinal claro: assunto começa com "RES:" ou texto contém frase conclusiva | Concluída | "Finaud encaminhou confirmação ao cliente e registrou internamente" |
| **1b — padrão** | Forward para cliente + nenhum sinal claro de conclusão | Aguardando Cliente | "Finaud escreveu ao cliente — aguarda retorno" |

**Por que 1b-padrão é "Aguardando Cliente" e não "Concluída":**
O texto de um forward pode combinar sinais opostos ("encaminhamos o arquivo e aguardamos retorno"). Se o sistema errar para "Aguardando Cliente" quando já está concluído, o caso aparece no painel e alguém verifica. Se errar para "Concluída" quando ainda está pendente, o caso some do radar sem ninguém perceber. O erro que aparece é mais seguro que o erro que desaparece. *(Confirmado por Michel, 18/08/2026)*

**Arquivos que NÃO contam como "arquivo real" (sub-caso 1a):**
Imagens inline do e-mail HTML (`.png`, `.gif`, `.jpg`, `.jpeg`, `.bmp`, `.ico`, `.webp`, `.tif`, `.tiff`, `.svg`) não representam entrega — são decoração do layout. Só arquivos de outros tipos (.zip, .xls, .pdf, .xml etc.) acionam o sub-caso 1a.

---

## 9. Modelo de Rastreamento — duas camadas

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

**O que significa "entregue" em cada categoria (confirmado por Michel, 03/08/2026):**

| Grupo | Categorias | O que a Finaud entrega ao cliente |
|---|---|---|
| CADOC ZIP | DDR_2011, DRM_2060, DRL_2160, DLO_2061, DLI_2062, SALDOS_CONTABEIS_DIARIOS_4111 | Arquivo ZIP com padrão `CNPJ_CATEGORIA_DATA.zip` (ex.: `12345678_2011_20260131_I_1.zip`). Substituições seguem o mesmo padrão com sufixo `_S_N`. |
| S5 | S5 | PDF (ex.: `Resultado Quantitativo - S5.pdf`) — não vai ao BACEN, fica entre Finaud e cliente. |
| FORCAPITAL | FORCAPITAL | Varia: e-mail só texto (projeção de capital) ou XLSX/PDF. Não vai ao BACEN. |
| PVCA_6209 | PVCA_6209 | Arquivo `BACEN.ZIP` contendo 8 TXT na raiz: `CONGLOME.TXT`, `USUREMOT.TXT`, `ESTATCRT.TXT`, `ESTATATM.TXT`, `TRANSOPA.TXT`, `OPEINTRA.TXT`, `CONTATOS.TXT`, `DATABASE.TXT`. Transmitido via STA pelo cliente. |
| DRSAC_2030 | DRSAC_2030 | Arquivo XML (elemento raiz `DocumentoDRSAC`, CNPJ de 8 dígitos, data no formato AAAA-MM). |

**RETORNO_BACEN — não é uma entrega, é uma crítica:**
O RETORNO_BACEN não tem "entregue" próprio — ele representa a etapa **"crítica recebida → substituição enviada"** do ciclo de vida de outra categoria (DDR, DRM, DRL etc.). O BACEN rejeitou um CADOC já entregue e solicitou correção.

**Requisito crítico — leitura de imagem no RETORNO_BACEN (confirmado por Michel, 03/08/2026):**
O conteúdo da crítica do BACEN (texto da inconsistência, protocolo, o que precisa corrigir) chega **embutido em imagens PNG/JPG** — são prints de tela do sistema do BACEN feitos pelo cliente. Sem ler essas imagens, o sistema não sabe o que o BACEN pediu.

O classificador (`classificador_ia.py`) deve, em threads RETORNO_BACEN, processar os anexos PNG/JPG usando a capacidade multimodal do Claude (leitura de imagem nativa) para extrair o texto da crítica e determinar: qual CADOC foi rejeitado, qual o protocolo, e qual ação a Finaud deve tomar.

**Por que este modelo:**
Um e-mail que entrega DDR + DRM + DLI não pode ser forçado em uma única categoria sem perder rastreabilidade dos outros dois. Com duas camadas, a IA aprende o fluxo completo (entregas, críticas, substituições, suporte) e a Finaud tem controle individual de cada obrigação regulatória.

**Impacto na classificação:**
A saída da IA deixa de ser "este e-mail É DDR" e passa a ser "este e-mail CONTÉM: DDR_2011 + DRM_2060". O Catálogo de Categorias (§10) continua válido — o que muda é que a saída é uma lista, não um valor único.

**Dupla função do classificador — classificar E detectar encerramento:**
A cada novo e-mail que chega no oraculo@, o classificador executa duas tarefas em sequência:
1. **Classificar:** identifica quais categorias o e-mail contém e gera a lista de entregas correspondentes na Camada 2.
2. **Detectar encerramento:** verifica se o e-mail contém sinais de encerramento (§8.3) e, se sim, muda o status do thread para **Concluída**.

Para CADOCs com ZIP (§8.5), o encerramento é detectado pelo nome do arquivo — não depende do classificador de linguagem.

> **Decisão confirmada por Michel (05/08/2026).**

---

## 10. Catálogo de categorias — o que a IA precisa saber

Esta seção alimenta diretamente o prompt da IA. Para cada categoria, a IA recebe: o que é, como reconhece no e-mail (assunto + corpo + histórico da thread) e qual prazo aplicar.

**Referência de prazos:**

| Categoria | Prazo |
|---|---|
| DDR_2011 | D+3 úteis após a data de referência |
| SALDOS_CONTABEIS_DIARIOS_4111 | D+3 úteis após a data de referência |
| DRM_2060 | D+5 úteis do mês seguinte à data de referência |
| DLO_2061 | Dia 5 do segundo mês seguinte à data de referência |
| DLI_2062 | Dia 5 do segundo mês seguinte à data de referência |
| DRL_2160 | D+10 úteis do mês seguinte à data de referência |
| S5 | D+5 úteis após a data de referência |
| RETORNO_BACEN | Prazo informado pelo BACEN na crítica — se não houver prazo explícito, usar D+3 úteis após a data do e-mail |
| SUPORTE       | Sem prazo regulatório — depende da urgência da solicitação |
| FORCAPITAL    | D+5 úteis após a data do e-mail |
| DRSAC_2030    | 10º dia útil do 2º mês subsequente à data-base |
| PVCA_6209     | Último dia útil do mês seguinte ao fim do trimestre |

---

### SALDOS_CONTABEIS_DIARIOS_4111 — Saldos Contábeis Diários

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

Validado em 386 threads reais (29/07/2026). Cobertura: 100%.

As mesmas 5 regras do DDR_2011. Sinais específicos do SALDOS_CONTABEIS_DIARIOS_4111:

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

**R5:** encaminhamento interno — ex.: "Lucas, por favor verificar esses dados antes de gerar o 4111"; arquivo ou dúvida do cliente repassada a colega da Finaud sem resposta ao cliente ainda

---

### DDR_2011 — Documento Diário de Posições

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
| Assunto | "PCAM", "Posição de Câmbio", "TVM", "Dep a Vista", "Compromissada", "Custódia", "Balancete de Câmbio", "CAM0050", "LFT", "PI Exposure" | Alta |
| Assunto | "Movimento [data]", "Saldos do dia", "Cadastro de Ações e Opções", "Fluxo de Caixa", "OP. SELIC", "RD MES" | Alta — clientes que não escrevem "DDR" no assunto mas enviam dados diários do DDR |
| Assunto | "posição diária", "remessa", nome do cliente + data | Média |
| Corpo | Posições financeiras do dia anterior, referências a CAM0050, valores em diferentes instrumentos | Média |
| Anexo | `RD_MOEDA.csv`, `RD_LFT.xlsx`, `RD_PREFIXADA.xlsx` (prefixo `RD_` — padrão dominante) | Alta |
| Anexo | `DDR_YYYYMM.xlsx`, `Operacoes compromissadas SCD.xlsx` | Alta |
| Anexo | `CNPJ_2011_YYYYMMDD.zip` (CADOC gerado — Finaud entrega ao cliente) | Muito alta |

> **Assuntos de dados diários sem "DDR" explícito — sempre DDR_2011:**
> Os seguintes assuntos identificam envio de componentes do DDR por clientes e devem ser classificados como **DDR_2011 imediatamente**, mesmo que o corpo seja curto ou diga apenas "Seguem os arquivos":
> - Assunto contém "PI Exposure" → DDR_2011
> - Assunto contém "EXTRATO COMPROMISSADA" ou "Compromissada" → DDR_2011
> - Assunto contém "Cadastro de Ações e Opções" → DDR_2011
> - Assunto contém "PCAM" ou "Posição de Câmbio" → DDR_2011
>
> Esses termos não ocorrem em RETORNO_BACEN nem em outras categorias — o sinal do assunto é suficiente, independente do tamanho do corpo.

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

Validado em 1.412 threads reais (29/07/2026). Cobertura: 100%.

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

**R5:** encaminhamento interno — ex.: "Monica, pode verificar esse balancete antes de processar?"; arquivo ou dúvida do cliente repassada a colega da Finaud sem resposta ao cliente ainda

---

### DRM_2060 — Demonstrativo de Risco de Mercado

**O que é:** relatório mensal que mede o quanto a instituição está exposta a riscos de variações de mercado — taxas de juros, câmbio, preços de ativos. Parecido com o DDR, mas mensal: a data de referência é sempre o **último dia útil do mês**.

**Frequência:** mensal — base: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DRM_2060", "DRM (2060)", "DRM2060_MMAAAA", "2060 DRM", "Documento 2060", "SMM - 2060" | Alta |
| Assunto | "DRM" + mês/ano | Alta |
| Corpo | Relatório de risco de mercado, exposição a taxas, VaR (valor em risco) | Média |
| Anexo | `Saldos DRM.xlsx`, `DRM_2060_Finaud_YYYYMM.xlsx` | Alta |
| Anexo | `CNPJ_2060_YYYYMMDD.zip` (CADOC gerado — Finaud entrega ao cliente) | Muito alta |
| Anexo | `SALDOS BANCOS.pdf`, `CAIXA.pdf`, `SELIC.xls` | Baixa — genérico, não identifica |

**O que NÃO é DRM_2060:**
- "COMUNICACAO DE INCONSISTENCIA NO DRM - 2060" → é **RETORNO_BACEN** (o BACEN rejeitou um DRM anterior)
- "RELATORIO DRM - Amaril Franklin" → pode ser **DLO** (é a planilha LEC usada para gerar o DLO)
- DRM + DDR no mesmo assunto → registrar ambos (ver §9 — modelo de duas camadas)

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
| R4 | Finaud enviou análise técnica, explicação ou pergunta (sem entrega de arquivo) — aguarda retorno do cliente | Aguardando | Cliente |
| R5 | Não se aplica — nenhuma thread F→F identificada no DRM_2060 | — | — |

**R1:** "segue anexo a remessa DRM (2060)", "segue o DRM (2060)", "DRM_2060 para transmissão ao BACEN", "transmitido ao BACEN"; agradecimento puro do cliente após entrega

**R2:** cliente enviou saldos/posições/extratos mensais; cliente enviou "prévia" para validação antes da versão final; cliente enviou retificação

**R3:** "encaminhar os extratos", "aguardo o balancete", Finaud pediu dado que ainda não chegou

**R4:** Finaud respondeu pergunta técnica; Finaud comunicou agendamento de reunião por texto (sem invite.ics ou link); Finaud esclareceu erro — aguarda retorno. ⚠️ Se o e-mail contém invite.ics ou link de reunião (Teams, Meet, Zoom) → classificar como **SUPORTE**, não DRM

**Sub-padrão "Prévia":** quando o cliente envia rascunho dos dados para Finaud validar antes da versão oficial → R2 (Aguardando/Finaud) até a entrega do DRM definitivo.

**Sub-padrão cliente transmite ao BACEN por conta própria** e avisa a Finaud via C→F → R1 (Concluído) — informacional, nenhuma ação da Finaud necessária.

---

### DLO_2061 — Demonstrativo de Limites Operacionais

**O que é:** relatório mensal sobre os limites regulatórios da instituição — concentração por contraparte, adequação de capital (Basileia) e outros indicadores. O cliente envia à Finaud os quatro arquivos COSIF (**COS4010.xml**, **COS4016.xml**, **COS4060.xml**, **COS4066.xml**) mais a planilha **LEC** (`.xls`/`.xlsx`). A Finaud processa e gera o CADOC, entregando-o ao cliente, que transmite ao BACEN. Em alguns casos a Finaud entrega diretamente.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DLO", "DLO_2061", "2061", "DLO/DLI" | Alta |
| Assunto | "COS 4010", "COS4010", "Planilha LEC", "Indicadores de Basiléia" | Alta |
| Assunto | "4010", "4016" (sem prefixo "COS") | Alta — cliente referencia os arquivos COSIF pelo número sem o prefixo |
| Assunto | "4060", "4066", "COS4060", "COS4066" | Alta — cliente conglomerado enviando COSIF; identifica DLO_2061 mesmo sem LEC no mesmo e-mail (LEC pode chegar em e-mail separado) |
| Assunto | "Balancete" (com ou sem mês/ano) | Média — padrão DLO quando o corpo não indica DLI ou S5; se corpo indicar DLI → DLI_2062; se S5 → S5 |
| Assunto | "Basileia" (sem "Indicadores de") | Média — confirmar com mês/ano ou corpo; "Indicadores de Basiléia" = Alta |
| Assunto | "PRE" | Média — Patrimônio de Referência Exigido, indicador calculado no DLO |
| Corpo | Balancete patrimonial, concentração por contraparte, limites de Basileia, planilha LEC | Média |
| Anexo | `COS4010.xml`, `COS4016.xml`, `COS4060.xml`, `COS4066.xml` + `LEC_MMAAAA.xls/xlsx` (do cliente) | Alta — LEC junto com COSIFs confirma DLO |
| Anexo | `CNPJ_2061_YYYYMMDD.zip`, `Cos4010.zip`, `Cos4016.zip` (CADOC gerado) | Muito alta |

> **LEC (Limite de Exposição por Contraparte):** planilha exclusiva do DLO_2061 que lista as exposições da instituição por contraparte. O DLI_2062 usa os mesmos arquivos COSIF mas **nunca** usa LEC — ela não existe no fluxo do DLI. Consequência direta: qualquer e-mail que mencione LEC no assunto, no corpo ou no nome do anexo — seja entrega da planilha, solicitação ao cliente para enviá-la, erro de importação, ajuste de dados ou dúvida técnica sobre o preenchimento — é DLO_2061, mesmo sem COSIFs anexados. O arquivo `Importacao_LEC*.xls/xlsx` no anexo identifica a thread como DLO_2061 com Alta confiança.

**O que NÃO é DLO_2061:**
- "RELATORIO DRM - AMARIL FRANKLIN" → pode ser DLO (esse cliente envia a LEC junto com e-mails de DRM — verificar anexo para confirmar)
- "ECSA (S5) - COS4010..." → é **S5** (código S5 no assunto prevalece sobre a menção ao COS4010)
- "Colchão de Liquidez" / "DRL" → é **DRL_2160**, não DLO — podem vir no mesmo e-mail, registrar separado
- COS4060, COS4066 no assunto → são exclusivos do **DLO_2061** (cliente conglomerado) — **nunca** aparecem no DLI_2062 (o que diferencia DLO de DLI é o que o e-mail menciona — ver **Regra DLO / DLI** abaixo, não o tipo de arquivo COSIF)
- DLO + DLI no mesmo e-mail → registrar ambos (§9 — modelo de duas camadas)

**Regra DLO / DLI — determinada pelo que o e-mail menciona:**

A classificação entre DLO_2061 e DLI_2062 é determinada pelo que o assunto ou corpo do e-mail menciona explicitamente:

| O e-mail menciona | Classificação |
|---|---|
| "DLO" e "DLI" (ou "2061" e "2062") | DLO_2061 + DLI_2062 |
| Apenas "DLI" (ou "2062") | DLI_2062 |
| Apenas "DLO" (ou "2061") | DLO_2061 |
| Nenhum dos dois | DLO_2061 (padrão) |

**Nota:** a presença dos arquivos COS4010, COS4016 ou outros COSIF não determina sozinha a categoria — é o texto do e-mail que decide. A planilha LEC continua sendo sinal de Alta confiança para DLO_2061 (ver tabela de sinais acima).

**Regra — Balancete e balanço contábil (aprovada por Michel em 21/08/2026):**
E-mail em que o assunto menciona "balancete" ou "balanço" (base de dados entregue pelo cliente para geração do DLO) → classificar como DLO_2061. Só classificar como SUPORTE se o e-mail for uma dúvida ou pergunta sobre como montar o balancete, sem entrega do arquivo.

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

### DLI_2062 — Demonstrativo de Limites Operacional Individual

**O que é:** relatório mensal semelhante ao DLO_2061, mas focado nos limites operacionais de cada instituição individualmente (não do conglomerado). Usa os mesmos quatro arquivos COSIF do DLO (**COS4010.xml**, **COS4016.xml**, **COS4060.xml**, **COS4066.xml**), mas **sem** a planilha LEC. Quando há erro na entrega original, uma **Substituição** é gerada e enviada. A Finaud entrega o CADOC ao cliente, que transmite ao BACEN.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DLI", "DLI_2062", "2062", "DLI2062_MMAAAA" | Alta |
| Assunto | "Segue a remessa DLI", "Preencher as premissas DLI", "Confecção do DLI", "Substituição" + DLI | Alta |
| Assunto | Nome do cliente + mês/ano, sem código explícito | Média |
| Corpo | Adequação de capital, Basileia, limites individuais, premissas DLI | Média |
| Anexo | `COS4010.xml`, `COS4016.xml` — sem menção a DLO/2061 no texto | Média — confirmar pelo assunto ou corpo; se não houver menção a DLI/2062 tampouco, classificar como DLO_2061 (padrão) |
| Anexo | `CNPJ_2062_YYYYMMDD.zip` (CADOC gerado) | Muito alta |

**O que NÃO é DLI_2062:**
- "Instrução Normativa BCB — Altera o DLI" → alerta regulatório sobre mudança de regra, não é entrega do CADOC — pode caber em SUPORTE
- "Aviso Bacen - DLI" / "Questionamento BACEN" → pode ser **RETORNO_BACEN** — verificar contexto
- COS4060, COS4066 no assunto ou em anexo → é **DLO_2061** (conglomerado) — DLI nunca usa esses arquivos
- DLO + DLI no mesmo e-mail → registrar ambos (§9 — modelo de duas camadas)

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

### DRL_2160 — Demonstrativo de Risco de Liquidez

**O que é:** relatório mensal que mede o risco de liquidez da instituição — o chamado "Colchão de Liquidez" (quanto de ativos líquidos a instituição mantém para cobrir saídas de caixa em cenário de estresse). O cliente envia à Finaud uma **planilha DRL** (`.xlsx`), que é importada no sistema. A Finaud gera o CADOC e entrega ao cliente, que transmite ao BACEN. Frequentemente entregue junto com o DDR.

**Frequência:** mensal — data de referência: último dia útil do mês.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DRL", "DLR", "DRL_2160", "2160", "DRL2160_MMAAAA" | Alta — "DLR" é variante com erro de digitação frequente |
| Assunto | "Colchão de Liquidez", "Encaminhar a planilha DRL", "Geração do arquivo Doc. 2160_DRL" | Alta |
| Assunto | "Protocolo DRL2160", nome do cliente + mês/ano | Média |
| Corpo | Colchão de liquidez, risco de liquidez, ativos líquidos, mapeamento COSIF × DRL | Média |
| Anexo | Planilha DRL (`.xlsx`) do cliente | Alta |
| Anexo | `CNPJ_2160_YYYYMMDD.zip` (CADOC gerado) | Muito alta |

**O que NÃO é DRL_2160:**
- "CONGLOMERADO" + DRL → variante do DRL para o conglomerado — ainda é DRL_2160, base de dados maior
- "Substituição" / "CORREÇÃO" + DRL → reentregas normais — ainda é DRL_2160
- "VENCIMENTO HOJE" + DRL → alerta de prazo — ainda é DRL_2160 (urgente)
- DRL + DDR no mesmo e-mail → registrar ambos (§9 — modelo de duas camadas)

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

**Frequência:** Reativa — ocorre quando o cliente traz uma demanda. Não tem periodicidade fixa.

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
| Corpo / Anexo | Anexo `invite.ics` ou corpo com link de reunião (Microsoft Teams, Google Meet, Zoom, Outlook Calendar) | Alta — convite de agenda; classificar como SUPORTE mesmo que o assunto mencione um CADOC (ex.: "DLO") |

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

**Frequência:** Reativa — ocorre quando o BACEN rejeita ou critica uma entrega. Não tem periodicidade fixa.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "ARQUIVO REJEITADO", "ENTREGUE E REJEITADO", "REJEITADO" | Alta |
| Assunto | "INDÍCIO DE PROBLEMA DE QUALIDADE IDENTIFICADO NO DOCUMENTO [número]" | Alta — linguagem do próprio BACEN |
| Assunto | "Erro [CADOC]" (ex.: "Erro DRM") | Alta |
| Assunto | "Indício de Problema Bacen" | Alta |
| Assunto | "AVISO DE ATRASO" | Alta — comunicado formal do BACEN sobre entrega em atraso |
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

**CADOCs que podem gerar RETORNO_BACEN:** qualquer CADOC que o cliente entrega ao BACEN — DDR_2011, DLO_2061, DLI_2062, DRM_2060, DRL_2160. O S5 nunca gera RETORNO_BACEN pois não é enviado ao BACEN.

**O que NÃO é RETORNO_BACEN:**
- E-mail perguntando sobre prazo de entrega ao BACEN → é o **CADOC específico** (DDR, DRM, DLO etc.)
- Comunicado regulatório do BACEN sobre mudança de regra ou normativa → é **SUPORTE**
- "Protocolo" ou "Resultado" referindo-se à entrega normal já aceita → é o **CADOC da entrega**
- Finaud ou cliente **enviando** remessa ao BACEN ("Seguem as remessas DLO e DLI a serem transmitidas ao BC", "Segue o arquivo transmitido") → é o **CADOC da entrega** (DLO_2061, DLI_2062, DDR_2011 etc.) — o fato de mencionar "BACEN" ou "BC" no corpo não torna RETORNO_BACEN

**Prazo:** prazo informado pelo BACEN na crítica (extraído do corpo do e-mail ou da imagem). Se o BACEN não informar prazo explícito: D+3 úteis após a data do e-mail como padrão.

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

**R5:** encaminhamento interno — comunicado do BACEN chegou ao suporte@finaud.com.br e foi repassado ao colaborador responsável sem resposta ao cliente ainda; ex.: "Fwd: BANCO CENTRAL - COMUNICACAO DE INCONSISTENCIA NO DRM - 2060" de suporte@finaud.com.br para monica.macedo@finaud.com.br ou andrea.inacio@finaud.com.br

⚠️ **Exclusivo do RETORNO_BACEN:** cliente confirmar que o BACEN aceitou (C→F) = R1 (Concluído). Nos outros CADOCs, C→F de confirmação só é R1 se for agradecimento. Aqui, confirmação de aceite do BACEN também encerra a thread.

---

### FORCAPITAL — Ferramenta de projeção de capital

**O que é:** serviço da Finaud para planejamento financeiro e projeção de capital. Não é um relatório regulatório do BACEN — não tem código CADOC e não é enviado ao BACEN. O cliente solicita uma projeção ou acesso à ferramenta, e a Finaud prepara e entrega.

**Frequência:** Sob demanda — ocorre quando o cliente solicita projeção de capital ou acesso à ferramenta.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto ou corpo | "FORCAPITAL", "ForCapital", "For Capital", "For-Capital" (qualquer variação) | Alta |
| Assunto ou corpo | "projeção de capital" ou "projeções de capital" (singular ou plural) | Alta |
| Assunto ou corpo | "projeção" isolado | Média — confirmar que não é projeção de outro relatório |
| Destinatário | suporteforcapital@finaud.com.br | Alta |
| Exemplos reais | "poderia nos enviar a projeção de capital para 36 meses?"; "Acesso ForCapital + credenciais"; "Encaminhamos projeção de capital DEZ/25 a DEZ/28" | — |

**O que NÃO é FORCAPITAL:**
- "projeção" referindo-se a dados regulatórios de Basileia, DLO ou DLI → é **DLO_2061** ou **DLI_2062**
- "projeção" de calendário, prazo ou cronograma → é **SUPORTE**
- Acesso a sistemas regulatórios (Risk Driver, CRD do BACEN) → é **SUPORTE**

**Fluxo típico:**
1. Cliente solicita projeção de capital, acesso à ferramenta, ou tem dúvida
2. Finaud verifica requisitos e prepara a resposta
3. Finaud entrega a projeção (planilha ou PDF) ou credenciais de acesso — ou pede dados adicionais ao cliente

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

### DRSAC_2030 — Demonstrativo de Responsabilidade em Soluções de Aplicações em Crédito

**O que é:** relatório regulatório semestral sobre operações de crédito. A Finaud orienta e responde dúvidas — **não gera o arquivo** (diferente de DDR, DLO, DRM). O cliente entrega diretamente ao BACEN.

**Frequência:** Semestral — datas-base: posições de fechamento de **junho** e **dezembro**.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto | "DRSAC", "CADOC 2030", "Demonstrativo 2030" | Alta |
| Corpo | Cliente pergunta se deve enviar / BACEN envia comunicado sobre DRSAC | Alta |
| Contexto | Volume muito baixo — apenas 2 threads desde jan/2026 | — |


**O que NÃO é DRSAC_2030:**
- Um e-mail com "DRSAC rejeitado" + prazo urgente → é **RETORNO_BACEN**, não DRSAC.

**Fluxo típico:**
1. Cliente pergunta se precisa entregar o DRSAC (ou BACEN comunica sobre inconsistência)
2. Finaud analisa e orienta sobre obrigatoriedade e formato
3. Cliente entrega diretamente ao BACEN (sem passar arquivo pela Finaud)

**Prazo:** até o **10º dia útil do 2º mês subsequente** à data-base
- Base junho → 10º DU de agosto
- Base dezembro → 10º DU de fevereiro

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

### PVCA_6209 — Elaboração e Remessa de Informações Relativas a Pagamentos de Varejo e a Canais de Atendimento

**O que é:** relatório regulatório trimestral sobre pagamentos de varejo e canais de atendimento. O cliente transmite via STA ao BACEN.

**Frequência:** Trimestral — datas-base: **31/mar, 30/jun, 30/set, 31/dez**.

**Como a IA reconhece:**

| Sinal | O que aparece | Confiança |
|---|---|---|
| Assunto ou corpo | "CADOC 6209", "6209", "pagamentos de varejo" | Alta |
| Assunto ou corpo | "canais de atendimento" + contexto regulatório | Média |

**Data de referência:** usa a data do trimestre se mencionada no e-mail; caso contrário usa a data do e-mail para inferir o trimestre.

**O que NÃO é PVCA_6209:**
- Volume histórico muito baixo (1 thread documentada). Tratar como SUPORTE se não houver sinal claro de 6209.

**Fluxo típico:**
1. Cliente pergunta sobre obrigatoriedade, prazo ou como preencher o PVCA
2. Finaud analisa e orienta
3. Cliente prepara o arquivo e entrega diretamente ao BACEN via STA — sem passar arquivo pela Finaud

**Prazo:** **último dia útil do mês seguinte ao fim do trimestre**
- Base 31/mar → último DU de abril
- Base 30/jun → último DU de julho
- Base 30/set → último DU de outubro
- Base 31/dez → último DU de janeiro

**Regras de classificação — Aguardando ou Concluído:**

Volume histórico irrelevante (1 thread documentada, 29/07/2026). Mesmas regras que SUPORTE e DRSAC — R5 se aplica.

| Regra | Situação | Status | Responsável |
|---|---|---|---|
| R1 | Finaud orientou, esclareceu ou entregou análise/correção conclusiva — OU agradecimento puro | Concluído | — |
| R2 | Cliente enviou o arquivo PVCA para análise ou correção — Finaud ainda não processou | Aguardando | Finaud |
| R3 | Finaud aguarda dado, informação ou confirmação do cliente | Aguardando | Cliente |
| R4 | Finaud está analisando — respondeu mas sem conclusão ainda | Aguardando | Finaud |
| R5 | Encaminhamento interno F→F sem resposta ao cliente | Aguardando | Finaud |

**R1:** "o preenchimento está correto", "não há obrigatoriedade para sua instituição", orientação concluída sem pendência; agradecimento puro do cliente após resposta da Finaud

**R2:** cliente enviou o arquivo PVCA para Finaud verificar antes de transmitir; cliente fez pergunta que Finaud ainda não respondeu. ⚠️ Se o cliente encaminhou comunicado de rejeição do BACEN → é **RETORNO_BACEN**, não PVCA.

**R3:** "precisamos saber o período de referência", "poderia confirmar o CNPJ da instituição?"; Finaud pediu dado ou confirmação e aguarda retorno do cliente

**R4:** "estou verificando a obrigatoriedade", "vou analisar", "retornaremos em breve"

**R5:** dúvida do cliente repassada internamente para colega da Finaud sem resposta ao cliente ainda

⚠️ **Volume baixo:** se o sinal de "6209" não estiver claro no assunto ou corpo, tratar como SUPORTE até confirmar.

---

### Anexos — sinal auxiliar de detecção

O nome do arquivo em anexo é um sinal adicional para a IA. Quando o assunto não tem código explícito, o nome do anexo pode ser decisivo. Padrões abaixo foram **verificados no histórico real**.

| Categoria | Alta confiança — identifica a categoria | Baixa confiança — genérico, não identifica |
|---|---|---|
| DDR_2011 | `RD_MOEDA.csv`, `RD_LFT.xlsx`, `RD_PREFIXADA.xlsx` (prefixo `RD_`); `DDR_YYYYMM.xlsx` | — |
| SALDOS_CONTABEIS_DIARIOS_4111 | `CADOC 4111.xlsx`, `DOC_4111_YYYYMMDD.xlsx`, `CNPJ_4111_DATA_I_1.zip` | — |
| DRM_2060 | `Saldos DRM.xlsx`, `DRM_2060_Finaud_YYYYMM.xlsx`, `CNPJ_2060_DATA.zip` | `SALDOS BANCOS.pdf`, `CAIXA.pdf`, `SELIC.xls` |
| DLO_2061 | `Cos4010.zip`, `Cos4016.zip` | — |
| DLI_2062 | `CNPJ_2062_YYYYMM_I_1_4010.zip` | — |
| DRL_2160 | planilha DRL (`.xlsx`) do cliente; `CNPJ_2160_YYYYMMDD.zip` (CADOC gerado) | — |

**Padrão transversal — ZIP do CADOC gerado:**  
O padrão `CNPJ_CADOC_DATA.zip` é universal — aparece em todos os CADOCs. O número do CADOC está diretamente no nome do arquivo, tornando-o o sinal de maior confiança quando presente.

**Fluxo padrão:** Finaud gera o CADOC → entrega ao **cliente** → cliente transmite ao BACEN. Em casos menos comuns a Finaud entrega diretamente ao BACEN.

| Categoria | Exemplo de ZIP |
|---|---|
| DDR_2011 | `CNPJ_2011_YYYYMMDD.zip` |
| DRM_2060 | `32648370_2060_20260130.zip` |
| DLO_2061 | `CNPJ_2061_YYYYMMDD.zip` |
| DLI_2062 | `62280490_2062_202602_I_1_4010.zip` |
| DRL_2160 | `CNPJ_2160_YYYYMMDD.zip` |
| SALDOS_CONTABEIS_DIARIOS_4111 | `32648370_4111_20260219_I_1.zip` |

> **Nota:** os arquivos XML (COS4010.xml, COS4016.xml, COS4060.xml, COS4066.xml) aparecem como **anexo direto** quando o cliente os envia à Finaud. O ZIP do CADOC gerado é o que a Finaud devolve ao cliente (ou envia ao BACEN diretamente).

---

## 11. Exemplos reais de threads (T01–T19)

Exemplos coletados durante a Fase 0 (22/07/2026) com leitura direta de 25+ threads reais da caixa `coleta.oraculo@finaud.com.br`. Cada exemplo documenta um tipo de fluxo com mensagens reais, participantes identificados e critério de conclusão.

> **Nota de desenvolvimento:** estes exemplos foram coletados via Gmail MCP (ferramenta de análise, não produção). O campo `sender` da ferramenta de busca pode mostrar `suporte@finaud.com.br` mesmo quando o remetente real é outro — em todos os casos abaixo o corpo do e-mail foi lido para confirmar o remetente real. Em produção, a Gmail API direta (Campo 1 e Campo 4 em §7) resolve isso automaticamente.

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

**O que é:** Jair Bonetti Junior (Western Union Bank) envia diariamente o CAM0050 BACEN e o Balancete de Câmbio à Finaud. A Finaud usa esses arquivos como insumo para gerar o DDR — fluxo idêntico aos demais clientes DDR com dados cambiais.

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

**Como sabemos que está resolvido:** thread sem resposta após o envio = Finaud processou internamente. Protocolo de aceite do STA confirma a transmissão ao BACEN.

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

**CADOC:** SALDOS_CONTABEIS_DIARIOS_4111 (com geração conjunta do 4010)

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

## 12. Decisões tomadas e justificativas

Índice de referência — todas as decisões relevantes registradas na spec, com localização. Serve para encontrar rapidamente onde uma escolha foi tomada e por quê, sem precisar ler o documento inteiro.

As quatro decisões fundacionais da arquitetura estão explicadas em detalhes no §2 ("Por que estas escolhas"). As demais estão no contexto de cada seção.

| Decisão | Justificativa resumida | Onde está explicada |
|---|---|---|
| Gmail API direta | Leitura em tempo real — e-mail novo chega em segundos, sem exportação manual | §2 — Decisões fundacionais |
| IA classificadora em vez de regras fixas | Clientes descrevem a mesma situação de formas diferentes; IA generaliza, regras fixas quebram | §2 — Decisões fundacionais |
| 99% de confiança mínima | Erro de classificação = CADOC tratado errado = risco de multa do BACEN; preferir retenção a erro | §2 — Decisões fundacionais; §8 — Regra dos 99% |
| Duas camadas (classificação + rastreamento) | Um e-mail pode ter múltiplos CADOCs; cada entrega precisa de estado próprio, independente | §2 — Decisões fundacionais; §9 — Modelo de rastreamento |
| CC ignorado na maior parte dos casos | Consultado só quando Finaud não está no Para — em 65% dos e-mails o Para já identifica tudo | §7 — Campo 3 |
| Reply-To lido apenas quando De = suporte@ | Só faz sentido quando o grupo enviou — nos outros casos De já identifica o remetente | §7 — Campo 4 |
| Extrair colaborador do corpo antes de limpar | A limpeza do Campo 6 remove a assinatura — se extrair depois, perde o e-mail do responsável para sempre | §7 — Campo 6, Passo 3 |
| L7 removida (imagem após assinatura) | Simulação: 7/7 imagens após assinatura continham conteúdo crítico (STA, CRD, boletas) — posição não é sinal de decorativo | §7 — Campo 6, regra L7 |
| OCR aciona para qualquer imagem não-decorativa | O único critério confiável de decorativo é o nome do arquivo — posição e categoria não bastam sozinhos | §7 — Campo 6, regra L6 |
| Campo `ocr_imagens` permanente no registro | IA Assistente precisará do conteúdo das imagens para aprender como cada caso foi resolvido | §7 — Campo 6, Campo OCR |
| Prazo lido da imagem em RETORNO_BACEN | A imagem do CRD/e-mail do BACEN contém o prazo real — substitui qualquer prazo pré-definido | §9 — Entregue por categoria (RETORNO_BACEN) |
| DDR multi-thread (chave CNPJ + data) | 99% das entregas DDR chegam em thread separada dos dados brutos — ligação por nome do ZIP | §9 — Entregue por categoria (DDR) |
| Threads irmãs deixadas para Fase 2 | Na Fase 1, regra do último e-mail cobre todos os casos normais — não vale a complexidade agora | §8 — Regras de classificação; PENDENCIAS.md |
| Convites de calendário → SUPORTE | Qualquer e-mail com invite.ics ou link de reunião (Teams, Meet, Zoom) é classificado como SUPORTE, mesmo que o assunto mencione um CADOC (decidido por Michel, 07/08/2026) | §10 — SUPORTE |
| Telas definidas por último | Design de tela depende de comportamento, regras, filas e ciclo de vida — definir antes inverte a ordem e cria inconsistência | §14 — Telas do sistema |

---

## 13. Plano de implantação por fases

| Fase | Nome | O que acontece | Status |
|---|---|---|---|
| **0** | Catálogo e validação | Mapear tipos de e-mail + validar classificador determinístico (768 threads, 99,5% de acerto) | **Concluído** — 17/08/2026 |
| **1** | Produção | Escrever `coletor_gmail.py` + pipeline determinístico + 3 telas (principal, revisão, descartes) | **Próximo passo** |
| **Futura** | IA e OCR | Ligar o GPT-4o-mini para casos que o determinístico não cobre; OCR para imagens do RETORNO_BACEN; IA Assistente de aprendizado | A definir |

**Decisões de implantação:**

| Decisão | Justificativa |
|---|---|
| Classificador determinístico na Fase 1, IA no futuro | Cobre 99,5% dos casos sem custo de API, sem latência, sem incerteza. A IA entra quando houver volume suficiente de classificações manuais para treinar e validar. |
| OCR na fase futura | RETORNO_BACEN é classificado pelo assunto/corpo na fase atual. OCR das imagens (para extrair código da crítica, prazo, etc.) fica para quando a IA for conectada. |
| Sistema rodando em servidor, não na máquina do Michel | A equipe precisa de acesso independente. |

### Como a Fase 0 foi feita

**Método:** leitura direta de 25+ threads reais da caixa `coleta.oraculo@finaud.com.br` via Gmail MCP (ferramenta de análise e desenvolvimento). Cada thread foi documentada com 8 dimensões:

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

**Resultado:** 19 tipos documentados (T01–T19). Os tipos T18 e T19 são filtrados automaticamente pelo sistema — não chegam à triagem. T04 (Western Union) confirmado por Michel (07/08/2026): fluxo idêntico aos demais clientes DDR com dados cambiais.

**O que esta base permite depois:**
- Identificar quais clientes enviam mais e-mails (por empresa e por contato individual)
- Ver qual colaborador Finaud é mais solicitado
- Entender onde o tempo fica represado (Finaud ou cliente)
- Calcular tempo médio por categoria de resolução
- Usar como base de exemplos para treinar e guiar a IA classificadora

Este catálogo é o guia de todas as fases seguintes. Fase 0 concluída — T04 confirmado por Michel em 03/08/2026.

---

## 14. Telas do sistema

O sistema tem 3 telas principais. Todo e-mail que chega passa por um de três destinos — e cada destino tem sua tela.

**Fluxo geral:**
```
E-mail chega
    │
    ▼
[§4 Filtro automático]
    │
    ├── É automático → Tela de Descartes
    │
    └── Não é automático → [Classificador determinístico]
            │
            ├── Conseguiu classificar → Tela Principal
            │
            └── Não conseguiu → Tela de Revisão
```

---

### Tela 1 — Principal (threads classificadas)

**O que é:** a tela do dia a dia — mostra todas as threads que o classificador conseguiu classificar, com categoria e status atualizados automaticamente.

**O que cada linha mostra:**

| Campo | O que aparece |
|---|---|
| Cliente | Nome da empresa + contato principal |
| Categoria | DDR · DRM · DLO · DLI · DRL · SCD · S5 · RETORNO_BACEN · SUPORTE · FORCAPITAL · DRSAC · PVCA |
| Status | Aguardando Finaud · Aguardando Cliente · Concluído |
| Última mensagem | Data e hora do último e-mail na thread |
| Colaborador Finaud | Quem está responsável do lado Finaud |

**Organização:**

As threads ficam separadas em 3 grupos:
1. **Aguardando Finaud** — a bola está com a equipe; requer ação
2. **Aguardando Cliente** — a bola está com o cliente; aguardando resposta
3. **Concluídas** — thread encerrada (por ZIP, confirmação ou regra de encerramento do §8)

**Atualização automática:** quando chega um novo e-mail numa thread, o status atualiza imediatamente — sem precisar recarregar a tela.

**Threads do mesmo cliente:** quando um cliente tem mais de uma thread aberta, o painel agrupa todas em bloco único. Cada thread fecha pelo seu próprio sinal — de forma independente.

---

### Tela 2 — Revisão (threads sem categoria)

**O que é:** fila de threads que o classificador não conseguiu classificar. Michel entra aqui, lê o e-mail e escolhe a categoria manualmente.

**O que cada linha mostra:**

| Campo | O que aparece |
|---|---|
| Assunto | Assunto do e-mail |
| Remetente | Quem enviou |
| Data | Quando chegou |
| Corpo (prévia) | Primeiras linhas do e-mail |

**O que Michel faz:**
1. Clica na thread para ler o e-mail completo
2. Escolhe a categoria no menu (lista das 12 categorias)
3. Confirma — thread sai desta tela e entra na Tela Principal com a categoria escolhida

> **Decisão (17/08/2026):** a categoria escolhida manualmente fica registrada. Em fase futura, esses registros alimentam o aprendizado da IA.

---

### Tela 3 — Descartes (e-mails barrados pelo filtro)

**O que é:** lista de todos os e-mails que o filtro §4 barrou. Michel pode revisar se algum foi barrado por engano.

**O que cada linha mostra:**

| Campo | O que aparece |
|---|---|
| Remetente | Endereço de e-mail + nome |
| Assunto | Assunto do e-mail |
| Motivo do descarte | Qual regra do §4 disparou (ex.: "noreply no endereço", "via Microsoft no nome") |
| Data | Quando chegou |

**O que Michel pode fazer:**
- **Revisar:** ler o e-mail completo para ver se faz sentido ter sido descartado
- **Reclassificar:** se foi barrado por engano → escolhe a categoria e manda para a Tela Principal
- **Ajustar a regra:** se um tipo de remetente está sendo barrado incorretamente → edita a regra de descarte (sem mexer no código)

> **Nota:** e-mails automáticos legítimos (FogBugz, Risk Driver, etc.) aparecem aqui mas não precisam de ação — são descartados corretamente. A tela serve principalmente para capturar casos onde a regra foi ampla demais.

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

**Tipos frequentes por colaborador (observados na Fase 0):**

| Colaborador | Tipos frequentes |
|---|---|
| Andrea Inacio | DRM crítica (T05), DLO reunião (T07), DLI substituição (T11), DDR substituição (T02) |
| Monica Macedo | DDR variação (T03), DLI entrega (T10), DLO rejeitado (T08) |
| Pedro Silva | DDR diário (T01), DLI substituição (T11) |
| Rodrigo Tiberio | DLO dúvida técnica (T06), Indícios (T09) |
| Flavio Camargo | DLI geração (T10), Indícios (T09) |

**Clientes mais ativos (observados nos últimos 30 dias — Fase 0):**

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

## Apêndice B — Terminologia

Definições dos termos usados ao longo desta especificação, em linguagem simples.

| Termo | O que significa |
|---|---|
| **Mensagem (e-mail)** | Um único e-mail enviado de A para B. Uma caixa com "970 e-mails" tem 970 mensagens individuais. |
| **Thread (conversa)** | Conjunto de mensagens que o Gmail agrupa como uma mesma conversa (pelo assunto e histórico de respostas). Uma conversa com 10 e-mails de ida e volta = 1 thread, não 10. Uma caixa com 201 threads pode ter quase 1.000 mensagens. |
| **coleta.oraculo@finaud.com.br** | Caixa monitorada exclusivamente pelo Oráculo 360 para leitura e classificação. Os colaboradores não respondem por ela — ela recebe cópias automáticas de tudo que passa pelo suporte@. |
| **suporte@finaud.com.br** | Caixa operacional da equipe. É onde os clientes escrevem e onde os colaboradores respondem. O Oráculo 360 não lê esta caixa diretamente — lê a coleta.oraculo@ que recebe as cópias. |
| **Caminho 2** | Regra configurada no Google Workspace da Finaud que envia automaticamente uma cópia de cada e-mail do suporte@ para a coleta.oraculo@. Acontece em tempo real, sem ação humana. |
| **Remessa (CADOC)** | O arquivo gerado pela Finaud e entregue ao cliente (ou diretamente ao BACEN). Formato típico: ZIP com o código do CADOC no nome — ex.: `32648370_2011_20260727.zip`. |
| **Competência** | O período de referência de um relatório — pode ser dia (DDR diário), mês (DRM), semestre (DLO/DLI) ou trimestre (PVCA). Diferente da data de envio: um DDR de competência 27/07 pode ser enviado ao BACEN em 30/07. |
| **Camada 1 — Comunicação** | O nível de conversa: o thread como um todo, com status único (Aguardando / Concluído). |
| **Camada 2 — Entregas** | O nível de cada CADOC dentro do thread. Um thread pode conter múltiplas entregas (ex.: DDR + DRM), cada uma com status próprio. |
| **BACEN** | Banco Central do Brasil — o regulador que recebe os CADOCs e emite críticas ou rejeições quando encontra problemas. |
| **STA** | Sistema de Transferência de Arquivos do BACEN — por onde os CADOCs são transmitidos. O protocolo de aceite do STA confirma a entrega. |
| **CRD** | Central de Rejeições e Devoluções do BACEN — sistema que processa críticas de inconsistência e emite protocolo após a substituição do arquivo. |
| **CNPJ do cliente** | Número de identificação fiscal da instituição regulada. É o identificador principal de cada cliente no sistema. |
| **Thread irmã** | Quando um mesmo cliente tem duas ou mais threads abertas ao mesmo tempo. O painel as agrupa juntas para o operador ver o contexto completo. |
| **Remetente** | Quem enviou a mensagem (campo "De:" do e-mail). |
| **Destinatário** | Quem recebeu a mensagem (campos "Para:", "CC:" ou "CCO:"). |

> Adicionado em 05/08/2026 — originado da dúvida sobre a diferença entre "970 e-mails" (mensagens) e "201 threads" (conversas) ao validar a varredura da caixa oraculo@.

