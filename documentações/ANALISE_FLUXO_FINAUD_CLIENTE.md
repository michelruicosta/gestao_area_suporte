# ANÁLISE DO FLUXO FINAUD↔CLIENTE — Oráculo 360

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

**Data:** 03/07/2026 · **Executada por:** Claude Sonnet 4.6
**Objetivo:** mapear o que o sistema captura hoje do fluxo Finaud↔Cliente vs. o que Michel precisa para a
visão completa (e futura integração com IA autônoma).
**Fontes consultadas:** scripts 02, 05, 09; `mapeamento_regras_negocio.json`; `ANALISE_FABLE_PIPELINE.md`;
`PARES_E_CLUSTERS_THREADID_DISTINTOS.md`; motor de triagem (`helpers.py`, `motor.py`, `_base.py`).
**Nada foi alterado nesta análise** — documento 100% diagnóstico.

> **Como ler:** cada obstáculo tem um código (O-1, O-2, O-3) referenciado ao longo do documento.
> Seções: 1. O que o sistema captura hoje · 2. O que escapa e por quê · 3. Perguntas abertas.

---

## 1. O QUE O SISTEMA CAPTURA HOJE

### 1.1 Como um e-mail entra no sistema (passo a passo)

```
Gmail (conta luiz.antonio@finaud.com.br)
    └── Script 02 busca via IMAP: OR (FROM "@finaud.com.br") (TO "@finaud.com.br")
        └── Capturados → JSON 01 (605 MB, e-mails brutos)
            └── Script 05 classifica: define CADOC, prazos, cliente, lado F/C, agrupa por thread
                └── JSON 02 (368 MB, eventos + threads classificados)
                    └── Script 09 integra: monta eventos[] e threads[] para o painel
                        └── JSON 03 (392 MB, base do painel)
                            └── Script 11 triagem: decide AGUARDANDO ou CONCLUÍDO
                                └── threads_aguardando_auto.json / threads_concluidas_auto.json
```

### 1.2 O critério real de captura

A conta `luiz.antonio@finaud.com.br` é o "olho" do sistema. O script 02 conecta nela via IMAP
e busca **todos os e-mails na caixa** onde FROM ou TO contém `@finaud.com.br`.

Portanto, um e-mail SÓ entra no sistema se:

1. **Chega na caixa do Luiz Antonio** (via inbox direto ou via grupo `suporte@finaud.com.br`), **E**
2. **Tem `@finaud.com.br` em FROM ou TO**

### 1.3 O que é capturado com certeza

| Situação | Como entra | Capturado? |
|---|---|---|
| Cliente envia para `suporte@finaud.com.br` | Luiz Antonio é membro do grupo → chega no inbox dele; TO=suporte@finaud.com.br | ✅ SIM |
| Colaborador responde ao cliente copiando `suporte@` | Chega no inbox de Luiz; FROM=colaborador@finaud.com.br | ✅ SIM |
| Cliente responde ao colaborador copiando `suporte@` | Idem | ✅ SIM |
| E-mails internos Finaud→Finaud copiando `suporte@` | Idem | ✅ SIM (mas são filtrados como F→F interno na triagem) |

### 1.4 Como as threads são agrupadas

O Gmail atribui um `X-GM-THRID` (ID de thread) a cada conversa. O script 02 captura esse ID via IMAP.
O script 05 usa o `X-GM-THRID` como chave para agrupar mensagens na mesma thread.

Ou seja: **o sistema herda a lógica de agrupamento do Gmail**. Se o Gmail entende como mesma
conversa → mesma thread no Oráculo. Se o Gmail abre nova thread → novo caso no Oráculo.

### 1.5 Como a triagem decide AGUARDANDO vs. CONCLUÍDO

O motor lê o histórico completo da thread — **não apenas a última mensagem** — e aplica regras
em cascata. As principais:

| Regra | Lógica | Exemplo |
|---|---|---|
| R1 | Finaud enviou o documento/instrução e não há resposta do cliente com nova dúvida | "Segue o arquivo…" → CONCLUÍDO |
| R2 | Cliente respondeu com pergunta → AGUARDANDO do lado da Finaud | "Poderiam verificar?" → AGUARDANDO |
| G3 | Cliente respondeu com concordância após instrução da Finaud | "De acordo", "Anotado", "Ciente" → CONCLUÍDO |
| Sinal L | Finaud habilitou transação via STA/Autran/SLIM800 | → CONCLUÍDO |
| R6 | Finaud confirmou reunião agendada | → CONCLUÍDO |

O motor olha para trás na conversa: se a última mensagem do cliente for "Ok, obrigado" mas a
mensagem anterior da Finaud for uma instrução → o G3 detecta concordância → CONCLUÍDO.

---

## 2. O QUE ESCAPA E POR QUÊ

### O-1: Brechas na captura de e-mail

**Causa raiz:** o sistema só vê o que chega na caixa do `luiz.antonio@finaud.com.br`.
Qualquer conversa que não passe pelo grupo `suporte@finaud.com.br` fica invisível.

| Situação | O que acontece | Capturado? |
|---|---|---|
| Cliente envia direto a `andrea.inacio@finaud.com.br` SEM copiar `suporte@` | Chega só na caixa da Andrea; Luiz nunca recebe | ❌ NÃO |
| Colaborador responde ao cliente SEM copiar `suporte@` | Vai para a caixa do cliente; Luiz nunca recebe | ❌ NÃO |
| E-mail entre dois colaboradores `@finaud.com.br` sem `suporte@` no CC | Se não estiver no inbox de Luiz → não capturado (mesmo que tenha @finaud.com.br nos dois lados) | ❌ NÃO |
| E-mail de/para `@finaudtec.com.br` sem `@finaud.com.br` | O critério IMAP é `@finaud.com.br`; `@finaudtec.com.br` não bate | ❌ NÃO (⚠️ ver nota abaixo) |

> **Nota sobre `@finaudtec.com.br`:** o script 05 (classificador) reconhece `@finaudtec.com.br`
> como domínio Finaud (campo `nossa_equipe.dominios` no `mapeamento_regras_negocio.json`).
> Mas o script 02 (coletor) só busca `@finaud.com.br` via IMAP. Inconsistência: o classificador
> "entenderia" esses e-mails como sendo da Finaud, mas eles nunca chegam até ele.

**Impacto no objetivo de Michel:** se um colaborador responde ao cliente sem copiar `suporte@`,
esse trecho do fluxo some do sistema. A IA futura aprende um fluxo incompleto, sem saber o que
a Finaud disse naquela mensagem.

**Alternativas técnicas conhecidas (sem custo adicional de licença):**

| Alternativa | Como funciona | Resolve O-1? | Complexidade |
|---|---|---|---|
| **A. Regra de roteamento no Google Admin (BCC automático)** | Admin configura no Workspace: todo e-mail enviado por qualquer `@finaud.com.br` → BCC automático para `suporte@finaud.com.br`. Executado pelo servidor do Google, não pelo colaborador | ✅ Resolve outgoing; entrante via suporte já funciona | Baixa — configuração no console do admin |
| **B. Regra de roteamento + também para entrante** | Idem A + configurar que e-mails RECEBIDOS por qualquer `@finaud.com.br` também são copiados para `suporte@` | ✅ Resolve ambos os lados | Média — duas regras de roteamento |
| **C. Gmail API com delegação de domínio (service account)** | Criar conta de serviço Google com permissão de ler todos os e-mails do domínio. Substituir o IMAP pelo Gmail API. | ✅ Resolve tudo sem depender de CC/BCC | Alta — requer OAuth, service account, permissão de admin |
| **D. Google Vault** | Ferramenta de arquivamento do Workspace — captura TODOS os e-mails de todos os usuários automaticamente | ✅ Resolve tudo | Requer licença adicional (Vault) |

> **⚠️ Pergunta aberta P-1:** Michel, qual dessas alternativas faz mais sentido para vocês?
> A alternativa A (roteamento BCC automático) parece o melhor custo-benefício: sem custo de
> licença, sem mudança de código no Oráculo, e resolve o lado mais crítico (outgoing que hoje
> falta). Confirmar com você antes de qualquer ação.

---

### O-2: Fragmentação de threads

**Causa raiz:** o sistema herda a lógica de thread do Gmail (`X-GM-THRID`). O Gmail só agrupa
automaticamente e-mails que são respostas diretas (via "Reply" no mesmo fio). Se alguém abre um
e-mail novo sobre o mesmo assunto → novo `X-GM-THRID` → novo caso no Oráculo.

**Situações de fragmentação identificadas:**

| Situação | Por que o Gmail abre nova thread | Impacto no Oráculo |
|---|---|---|
| Colaborador escreve e-mail novo sobre o mesmo CADOC (em vez de responder no fio) | Novo assunto no e-mail = nova thread no Gmail | Dois cards separados para o mesmo caso operacional |
| Cliente responde por e-mail diferente (ex.: de casa, do celular, sem "Reply") | Gmail não associa ao fio original | Idem |
| Assunto editado além do "Re:" (ex.: cliente apaga o "Re:" ao responder) | Gmail perde a referência de fio | Idem |
| Conversa começa no chat (WhatsApp, phone) e só depois vai ao e-mail | Contexto inicial perdido; e-mail começa "no meio" | Thread incompleta |

**O que o sistema já faz para mitigar:**

O Oráculo tem um mecanismo de "par sugerido" e "par confirmado":
- O algoritmo detecta dois threads do **mesmo cliente** com o **mesmo fingerprint de prazos**
  (mesma combinação CADOC + data_base + prazo_limite) e sugere na tela: "esses dois parecem ser o mesmo caso"
- O analista confirma com um clique → os dois cards se fundem em um só (mantendo histórico dos dois)

**Limitações do mecanismo atual:**
- Só funciona para **exatamente 2 threads** (3 ou mais: mostrado como cluster, sem fusão automática)
- Requer mesmo cliente E mesmo fingerprint de prazos (casos onde o prazo mudou ou é de CADOC diferente: não detectados)
- Depende de **julgamento humano** para confirmar — a IA futura precisaria fazer isso automaticamente

> **⚠️ Pergunta aberta P-2:** como você quer tratar a fragmentação no curto prazo?
> Opções: (a) manter o fluxo atual de "confirmar par" na tela e documentar como limitação conhecida;
> (b) melhorar o algoritmo de sugestão para considerar mais critérios (similaridade de assunto via IA);
> (c) criar disciplina operacional: colaboradores treinados a sempre usar "Reply" no fio original.
> A opção (c) é a mais barata e resolve na raiz — mas depende de mudança de hábito da equipe.

---

### O-3: Fechamentos ambíguos

**Causa raiz:** o motor decide AGUARDANDO/CONCLUÍDO com base em padrões de texto. "Ok, obrigado"
ou "Ciente" isolado é ambíguo: pode ser concordância conclusiva (G3 → CONCLUÍDO) ou apenas
um reconhecimento educado sem resolver nada.

**O que o motor já faz bem:**
- G3 (`_par_conclusivo`): detecta concordância *após instrução da Finaud* — lê o contexto anterior, não só a última mensagem
- Regra 9-C: agradecimentos pós-remessa não reabrem thread (evita falso AGUARDANDO)
- R1: Finaud enviou arquivo/instrução e não há nova pergunta → CONCLUÍDO

**Onde ainda há brechas:**

| Situação | O que o motor faz | Problema |
|---|---|---|
| Cliente responde "Ok" após Finaud fazer pergunta (não instrução) | G3 detecta concordância e pode marcar CONCLUÍDO | Falso positivo: a Finaud tinha feito uma pergunta, não uma instrução; cliente disse "Ok" sem responder a pergunta |
| Finaud pede algo ao cliente, cliente responde "Ciente" | G3 pode marcar CONCLUÍDO | Falso positivo: "ciente" ≠ "vou fazer" |
| Thread com gaps de captura (O-1): última mensagem visible é da Finaud | Motor pode marcar AGUARDANDO | Correto na aparência, mas a resposta do cliente existiu e não foi capturada |
| "Ok obrigado" como fechamento educado após prazo cumprido | G3 → CONCLUÍDO | ✅ Correto na maioria dos casos |

**Implicação para a IA futura:**
Se o banco de dados de treino contém classificações incorretas (CONCLUÍDO quando deveria ser
AGUARDANDO), a IA aprende o padrão errado. A qualidade do motor hoje = a qualidade do treino amanhã.

> **⚠️ Pergunta aberta P-3:** qual o nível de tolerância a erros de classificação aceitável para
> o banco de treino da IA futura? Qualquer dado incorreto contamina o treino. Opções:
> (a) aceitar nível atual de erros (estimativa: <5% baseado nas auditorias) e ajustar continuamente;
> (b) criar etapa de revisão humana para threads com classificação "baixa confiança" antes de entrar
> no banco de treino;
> (c) usar a própria IA para revisar as classificações antes de usar como treino (auto-auditoria).

---

## 3. RESUMO DO QUE TEMOS VS. O QUE MICHEL PRECISA

| Requisito de Michel | Situação hoje | Gap |
|---|---|---|
| Capturar TODO o fluxo Finaud↔Cliente, do início ao fim | Captura apenas o que passa pelo `suporte@finaud.com.br` | O-1: e-mails diretos sem CC ao grupo → invisíveis |
| Threads do mesmo caso na mesma conversa | Parcialmente resolvido via "par confirmado" (humano) | O-2: fragmentações fora do algoritmo de par não são detectadas |
| Classificação correta de AGUARDANDO/CONCLUÍDO para treinar IA | Motor com ~60 detectores; G3, R6, Sinal L, Sinal K ativos | O-3: brechas em casos ambíguos; qualidade do treino depende da qualidade da triagem |
| Base de dados completa e confiável para IA futura | JSONs com 4.737 threads; 1,4 GB; motor com ~60 regras | Incompleto por O-1; potencialmente inconsistente por O-3 |
| Tela intuitiva para operação humana e eventual supervisão de IA | Tela atual: "muito poluída" (diagnóstico do Michel) | Revisão de UX pendente — separada dos obstáculos técnicos |

---

## 4. PERGUNTAS ABERTAS (precisam de decisão do Michel antes de qualquer ação)

| # | Pergunta | Impacto se não decidir |
|---|---|---|
| **P-1** | Qual alternativa adotar para fechar O-1? (roteamento BCC automático, Gmail API, ou aceitar como limitação) | O-1 permanece — fluxos incompletos continuam |
| **P-2** | Como tratar O-2 no curto prazo? (disciplina operacional, melhorar algoritmo, ou manter como está) | Fragmentações continuam sendo tratadas caso a caso |
| **P-3** | Qual tolerância de erros de classificação para o banco de treino da IA? | Define se precisa de etapa de revisão humana antes de usar os dados como treino |
| **P-4** | O `@finaudtec.com.br` é domínio ativo hoje? Colaboradores enviam e-mails por ele? | Se sim, é um gap de captura que nem aparece no diagnóstico de O-1 — precisa de tratamento específico |
| **P-5** | Quando você imagina começar a integrar a IA autônoma? | Define a urgência de resolver O-1 e O-3 — se a IA é próxima, a qualidade dos dados é prioridade máxima agora |

---

## 5. O QUE NÃO É OBSTÁCULO TÉCNICO (é decisão de negócio)

1. **A tela de Triagem (UX)** — pode ser redesenhada independentemente dos obstáculos O-1/O-2/O-3.
   O diagnóstico de UX já foi iniciado (ver `REVISAO_TELAS.md`). Michel decide se resolve primeiro
   a captura ou a tela — são caminhos independentes.

2. **O motor de triagem tem regras suficientes hoje** para a operação atual. Os gaps do O-3 são
   conhecidos e documentados. A decisão é: refinar agora (antes da IA) ou aceitar o nível atual.

3. **A fragmentação (O-2) tem solução operacional simples** (disciplina de Reply no fio).
   A solução técnica (melhorar o algoritmo) é optional — a operacional pode ser suficiente.

---

*Próximo passo: conversar com Michel sobre as perguntas P-1 a P-5 e registrar as decisões aqui
antes de qualquer implementação.*
