# SESSAO_ATUAL — Oráculo 360 Finaud

> **BASTÃO ENTRE SESSÕES.** Leia este arquivo antes de tudo — ele traz o estado de agora e o próximo passo.
> História completa → `documentações/REGISTRO_CORRECOES.md` · Pendências → `documentações/PENDENCIAS.md`
> Como tudo funciona / como rodar uma carga → `documentações/MAPA_DO_PROJETO.md`
>
> **📂 Onde cada coisa mora:** REGRA → `CLAUDE.md` · CONHECIMENTO → `MAPA`/`GUIA` · ESTADO → `SESSAO_ATUAL` (este) · O QUE FALTA → `PENDENCIAS` · HISTÓRICO → `REGISTRO_CORRECOES`

---

## 📓 Diário da sessão (2026-07-07)

> **Como usar:** cada passo do plano de correção do TESTE tem uma entrada aqui.
> Formato: análise feita → decisão tomada → o que foi executado.
> A IA que abrir o próximo chat lê isto e **não precisa re-analisar** — parte da decisão já tomada.

---

### Passo 3 ✅ — Prazo RETORNO_BACEN: D+5 → D+3
- **Análise:** config tinha `D+5_UTIL`; código do calculador já suporta D+3 (usado por outros CADOCs); `D+3_UTIL` não precisava ser criado.
- **Decisão:** corrigir config JSON + texto do log no Script 05 + 4 testes que afirmavam D+5.
- **Feito:** commit `d999034` — 5 arquivos alterados.

---

### Passo 4 — Incluir nome dos anexos na detecção de CADOC
- **Análise completa feita (07/07):**
  - 20 dos 47 e-mails do TESTE têm `anexos_detectados` no JSON 01.
  - Script 05 linha 1923: `texto_completo = f"{assunto} {corpo}"` — nomes de arquivo ficam de fora.
  - O campo `anexos_detectados` **não é repassado ao JSON 02** — downstream nunca vê os nomes.
  - Guru CTVM (`2011 (DDR) (28).xlsx`): já classifica DDR_2011 corretamente pelo **corpo** ("4111 (Saldos Diários)\n2011 (DDR)") — anexo não é necessário.
  - TC/Economatica (`Saldos 4111.xlsx`): corpo genérico, "4111" só no nome do arquivo → classifica como **SUPORTE** (errado).
  - Dos 20 anexos, **apenas 1 muda** com a correção: TC/Economatica SUPORTE → 4111.
  - Cadastro `cadastro_clientes_cadoc.json`: TC não tem 4111 cadastrado — mas o cadastro **não influencia** a classificação do Script 05, apenas estatísticas. Não precisa alterar.
- **Decisão:** alterar só 1 linha (Script 05 linha 1923) — adicionar `nomes_anexos` ao `texto_completo`.
- **Feito:** ✅ commit `(ver abaixo)` — Script 05 linhas 1922–1923 alteradas.

---

### Passo 5 ✅ — "Balancete de Câmbio" → DDR_2011 (Western Union)
- **Análise:** regra `#PF30` usava `\bbalancete\b` genérico → tudo ia para DLO_2061. "Balancete de Câmbio" é documento cambial do DDR, não balanço patrimonial do DLO.
- **Decisão:** inserir regra específica (`balancete de câmbio` → DDR_2011) antes da genérica (`balancete` → DLO_2061). Regex aceita acento (`c[aâ]mbio`).
- **Feito:** ✅ commit `(ver abaixo)` — Script 05 linhas 1341–1345.

### Passo 6 ✅ — Consulta de norma → SUPORTE (Terra Investimentos)
- **Análise:** "Risco de Liquidez" no assunto ativava DRL_2160. Causa: termo cadastrado no config como indicador de DRL. "Norma BCB" no assunto é sinal de dúvida, não de envio. Apenas 1 e-mail afetado no TESTE.
- **Decisão:** nova regra antes do `#PF23` — se assunto tem "Norma BCB", "IN BCB" ou "Instrução Normativa" → SUPORTE imediato, antes de qualquer CADOC ser avaliado.
- **Feito:** ✅ commit `(ver abaixo)` — Script 05 linha 1348.

### Passo 7 — Fallback de data para Guru CTVM
- **Análise:** DDR_2011 é DIARIA; sem data em assunto/corpo/thread → retornava `exibir_card: False`. `data_referencia` (data de envio) já estava disponível na linha 1996.
- **Decisão:** usar `data_referencia` como fallback quando `todas_datas` continua vazio após busca no corpus da thread.
- **Feito:** ✅ Script 05 linhas 2028-2036 — fallback com log de aviso. 656 testes passando, 28 pré-existentes, zero regressões.

### Passo 8 — Detecção RETORNO_BACEN ampliada
- **Análise:** investigação completa nos 2 ambientes: 35 e-mails perdidos na produção; 5 falsos positivos FogBugz descartados (barrados por `eh_email_interno`); 2 borderlines confirmados como legítimos.
- **Decisão:** adicionar `rejeitado/rejeição/recusado/recusa/aviso bacen` a `termos_assunto` no config + expandir `tem_sinal_bc` no corpo do Script 05.
- **Feito:** ✅ config + Script 05 atualizados. 656 testes passando, zero regressões.

### Passo 9 — Anexo XML não capturado (Amaril Franklin)
- **Análise:** ⬜ não iniciada

### Passo 10 — E-mail de analista não capturado (Green DTVM)
- **Análise:** ⬜ não iniciada

---

## 📍 Estado de agora (2026-07-07 — encerramento TESTE)

> **Este arquivo é do AMBIENTE TESTE** (`oraculo_360_finaud_TESTE`).
> O ambiente TESTE foi criado para validar 47 e-mails coletados em 03/07/2026 antes de
> aplicar mudanças na produção.

| Conta coleta | E-mails coletados | Ambiente | Branch |
|---|---|---|---|
| coleta.oraculo@finaud.com.br | 47 (03/07/2026) | **TESTE** | desenvolvimento-front_end |

> **Como funciona a coleta no TESTE:** o script 02 faz login com `coleta.oraculo@finaud.com.br`
> no Gmail via IMAP, mas a busca retorna e-mails que têm `@finaud.com.br` no remetente OU no
> destinatário — ou seja, captura e-mails endereçados ao `suporte@finaud.com.br`, `andrea@finaud.com.br`
> etc., desde que estejam visíveis nessa caixa. `coleta.oraculo` é a conta de acesso, não o filtro.

Último /fechar: 2026-07-07 (sessão TESTE — auditoria completa 36 threads) — memórias revisadas ✅

### 🔥 Próximo passo — 9 pendências 🔴 URGENTES para a próxima sessão

Todas registradas em `documentações/PENDENCIAS.md` (seção AMBIENTE TESTE):

| # | Problema | Arquivo |
|---|---|---|
| #06 | Guru CTVM — sem data no arquivo, sem prazo, sem card | Script 05 — fallback de data |
| #07-P1 | "Cadastro" na assinatura dispara DDR_2011 | Script 05 — detecção de CADOC |
| #07-P2 | Thread não herda RETORNO_BACEN do segundo email | Script 09 — prioridade de CADOC |
| #08 | Nome do anexo não entra na detecção de CADOC | Script 05 — `identificar_cadoc` |
| #12 | Prazo RETORNO_BACEN: D+5 no config, deveria ser D+3 | `mapeamento_regras_negocio.json` |
| #19 | Anexo XML existe no Gmail mas não foi capturado | Script 02 — captura de anexos |
| #20 | Email da Andrea para cliente presente no `coleta.oraculo` mas ausente no JSON 01 | Script 02 — coleta IMAP |
| #29 | "Balancete de Câmbio" → DLO_2061, deveria ser DDR_2011 | Script 05 — regra #PF30 |
| #32 | Consulta sobre norma BCB → DRL_2160, deveria ser SUPORTE | Script 05 — detecção de consulta |

---

### Feito nesta sessão (07/07/2026 — auditoria completa das 36 threads TESTE)

**Objetivo:** auditar thread a thread todas as 36 threads do integrador (carga 03/07/2026) —
verificar CADOC, prazo, responsável e detectar bugs.

**Resultado: auditoria 100% concluída. 24 threads corretas, 9 problemas identificados e registrados.**

**Bugs encontrados (todos 🔴 URGENTE no PENDENCIAS.md):**
- **#06** — Guru CTVM: sem data no arquivo → sem prazo, sem card na tela
- **#07-P1** — "Cadastro" na assinatura da Intra dispara DDR_2011 indevidamente
- **#07-P2** — Thread Intra não herdou RETORNO_BACEN mesmo com segundo email classificado como tal
- **#08** — TC/Economatica: nome do anexo `Saldos 4111.xlsx` não entra na detecção de CADOC → classificado como SUPORTE
- **#12** — Prazo fallback RETORNO_BACEN: `D+5_UTIL` no config, Michel confirmou que é `D+3`
- **#19** — Amaril Franklin: anexo XML (COS4010) existe no Gmail mas `anexos_detectados: []`
- **#20** — Green DTVM: email da Andrea → Barbara (13:02) presente no `coleta.oraculo` mas não aparece no JSON 01
- **#29** — Western Union: "Balancete de Câmbio" → DLO_2061, deveria ser DDR_2011 (regra #PF30 muito ampla)
- **#32** — Terra Investimentos: consulta sobre norma BCB → DRL_2160, deveria ser SUPORTE

**Limitações conhecidas confirmadas (não são bugs novos):**
- Thread #20 Green DTVM também tem característica de Cenário C (emails diretos entre cliente e analista), mas o bug principal é a falha de coleta do `coleta.oraculo`
- Thread #28 (regras de responsável/lado_responsável): deferido para revisão de regras de status (próxima sessão dedicada)

### Feito nesta sessão (06/07/2026 — investigação ambiente TESTE)

**Objetivo:** descobrir por que a thread "Conexão" (newsletter do Banco Central) foi classificada
como DDR_2011 no ambiente TESTE. Michel perguntou: "Onde exatamente no texto está 2011?"

**Resultado: 3 bugs encontrados (1 já corrigido, 2 pendentes)**

**Bug 1 ✅ (já corrigido):** a configuração antiga tinha "Cadastro" como palavra-chave do
DDR_2011. O rodapé da newsletter ("Clique aqui para atualizar o seu cadastro") ativou a
classificação. A config já está corrigida: `deteccao_cadoc.DDR_2011` agora está vazia.

**Bug 2 🔴 (pendente):** `'marco': 3` no mapa de meses — a palavra "marco" (como em "marco
relevante") estava mapeada como março. O texto "marco relevante para a modernização" gerou
a data falsa 31/03/2026, que foi aceita como prazo do DDR_2011.
- Arquivo: `scripts/05_classificar_emails_regulatorio.py` linha ~803
- Fix: remover `'marco': 3` do dicionário de meses

**Bug 3 🔴 (pendente):** `FILTROS_DE_IGNORAR` na configuração está completamente vazio —
o endereço `comunicacao@comunicacao.bcb.gov.br` (boletim institucional do BACEN) passa pelo
sistema sem filtro.
- Arquivo: `data/json/config/mapeamento_regras_negocio.json`
- Fix: adicionar `"comunicacao@comunicacao.bcb.gov.br"` em `por_conteudo_especifico`

**Correções aplicadas nesta sessão (antes da compressão de contexto):**
- Script 05 linha ~1799: FogBugz recebe `cadoc=FOGBUGZ` e `exibir_card=False`
- Script 11 linha ~183: removido `fog_on = lei_on = True` — FogBugz e Leiautes_BACEN não
  vão mais para a triagem
- `iniciar.md`: health check que alerta sobre cadoc vazio/IGNORADO/FILTRADO_POR_DATA

**JSON 02 do TESTE:** ainda tem `cadoc=DDR_2011` e prazos falsos para a thread "Conexão"
(GMTHRID_1869725950497986970). Precisa correção manual (ver PENDENCIAS.md).

**Auditoria dos 47 e-mails:** focou na thread "Conexão". Threads 19/20/21 têm inconsistência
(CONCLUÍDO mas motivo diz "aguarda processamento") — investigar na próxima sessão.

### 🔥 Próximo passo (TESTE)

1. **Bug 2:** remover `'marco': 3` do script 05 linha ~803
2. **Bug 3:** adicionar filtro BACEN em `FILTROS_DE_IGNORAR` no config JSON
3. **JSON 02:** backup + corrigir thread "Conexão" (`cadoc=IGNORADO`, `prazos=[]`) + rodar 09+11
4. **Auditoria:** verificar threads 19/20/21 + completar os 47 e-mails
5. **Produção:** após TESTE validado, aplicar Bug 2 + Bug 3 na produção também

---

## 📍 Estado de agora (2026-07-02 — encerramento)

| AG (aguardando) | CO (concluídas) | Total | pytest (pre-commit) | Última carga triagem (02→11) | Último enriquecimento (12→17) |
|-----------------|-----------------|-------|--------|------------------------------|-------------------------------|
| 996 | 3.741 | 4.737 | **220 passed, 1.5s** | **06/07/2026** ✅ | **06/07/2026** ✅ |

- Branch ativa: **`desenvolvimento-front_end`** (sincronizada com GitHub ✅ — push 02/07/2026)
- Branch estável: **`main`** (PR #2 mergeado em 23/06)
- Integrador: 21/01 → **01/07/2026** (Carga #57 concluída — 24 a 25/06, +17 threads)
- Motor: G3 + Sinal K + R6 + R0b + R0c + Sinal L + Grupo 8 + R0/R1b/R9-C + R1c/R1d/R2b ativos em **todos os 10 supervisores**
- ✅ **Revisão arquitetural CONCLUÍDA:** `_base.py` criado; 10 supervisores migrados
- ✅ **CI no GitHub ativo e VERDE** + **pre-commit local** ativo
- ✅ **Script 10 removido** do pipeline — `resolver_aguardando_auto.py` arquivado; funções migradas para `helpers.py`
- ✅ **REGISTRO_CORRECOES.md limpo** — 0 itens VALIDAÇÃO PENDENTE

Último /fechar: 2026-07-02 (4ª sessão — Análise Fable do pipeline) — memórias revisadas ✅

### Feito nesta sessão (02/07/2026 — 4ª sessão: Análise Fable — auditoria completa do pipeline)

**Auditoria completa do pipeline executada pelo Fable (100% diagnóstico, nada alterado no sistema):**
- Lidos integralmente: scripts 02–17 e 20, motor de triagem (`motor.py`, `_base.py`, `helpers.py`), 11_triar + wrappers, orquestrador (`executar_tudo.py`, `pipeline_jobs.py`, `pipeline_watchdog.py`), `paths.py`, `guard_imutabilidade.py` e a estrutura real dos JSONs (01=605 MB, 02=368 MB, 03=392 MB).
- Cada achado cruzado com o REGISTRO_CORRECOES para não reapontar o que já foi corrigido (ex.: `regra="R1"` em CO é decisão documentada da Fase 4, não bug — reclassificada como observação de desenho).
- **Entrega:** `documentações/ANALISE_FABLE_PIPELINE.md` — 35 achados com arquivo:linha, mapa do fluxo, mapa de responsabilidades por campo, plano em 4 pacotes e proposta de 12 padrões.
- **Destaques 🔴:** try/except único em volta de todas as regras do motor (triagem pode rodar sem regras em silêncio) · normativo perdido para sempre se a IA do 07 falhar · coletas 06/08 fingem sucesso · `datetime` sem import no 02 · retomada por checkpoint do 05 perde dados · `origem_triagem_auto=False` gravado pelo motor em registros automáticos (campo mente) · corpos de e-mail em triplicata (1,4 GB).
- **Bordo:** pendência "ANÁLISE FABLE" fechada (REGISTRO primeiro, depois removida do PENDENCIAS); 4 pacotes de correção registrados no PENDENCIAS na ordem recomendada 1 → 2 → 4 → 3.

### Feito nesta sessão (02/07/2026 — 3ª sessão: revisão UX 2ª rodada + navegação)

**Painel de Gestão — 6 fixes de lógica concluídos (todos com código + registro):**
- **2-H** `data_conclusao` errada (carga vs. última msg real) — corrigida no motor + backfill 671 threads — commit `2-H`
- **2-I** catálogo de categorias com visibilidade (`config/categorias.py`) — LEIAUTES_BACEN/RISK_DRIVER*/FOGBUGZ invisíveis na tela — commit `08ca01f`
- **2-J** "Fora do prazo" usava o prazo mais antigo (atraso fantasma de 300+ dias) — agora usa o prazo vigente na data de conclusão — commit `20cbaae`
- **2-K/2-L** ranking agora mostra todos os 7 analistas cadastrados (role=operacional, @finaud.com.br), pré-inicializa com 0 casos, exclui Michel (admin) e Luiz Antonio (domínio externo) — commits `123c206` + `96976f3`
- **2-M** confirmado: "perto de vencer" é intencional independente do filtro de período (decisão registrada, sem alteração de código)
- **2-N** `data_marcacao` em AGUARDANDO usava data da carga — corrigida para usar `data_iso` da mensagem real (215 threads corrigidas) — commit `0a11abb`

**UX e navegação — reorganização completa:**
- Painel de Gestão vira grupo expansível no menu; tela renomeada para "Resumo Período"
- Base de Conhecimento renomeada para "Aprendizado IA"
- Banner "Retorno BACEN tem tela própria" removido
- IA Assistente saiu do menu principal → entrou em Protótipos
- Grupo "Custos" removido → "APIs Custos" entrou em Administrador
- Produtividade por Analista saiu de E-mails → entrou em Protótipos
- **E-mails** agora tem só "Triagem" · **Protótipos** tem: IA Assistente, Produtividade, Visão Gestão, Gerencial Mensal, Gestão e Direção

**Tempo médio de resolução:** cálculo corrigido (mede 1ª mensagem até conclusão, não a última) + exibe inteiro (8d em vez de 7.8d)

**Commits do dia:** `d91c6dd` · `20cbaae` · `0a11abb` · `08ca01f` · `123c206` · `96976f3` · `b4a7386` · `5194012` · `994e1ad` · `6eb5fe3` · `eab24d3` · `4fb0c18` (+ commits de fix do painel da 1ª rodada já existentes)

---

### Feito nesta sessão (01/07/2026 — 2ª sessão: revisão da tela Painel de Gestão)

**Correção de dados (data_conclusao) — 1.191 threads:** tinham data de conclusão errada (o timestamp
da re-triagem em massa de 05/06 às 22h21, não a data real da última mensagem). Corrigidas com
`data_ultima_msg` do integrador. KPIs de 30 dias: de **2.115 / +325%** (impossível) → **942 / +17,4%**
(real). Backup + CONTEXTO.md. Commit `97ccffd`.

**Home (Visão Geral) redesenhada:** card único de e-mails (Pendente/Aguardando/Concluído/Não resolvidos)
+ FOG e Normativos com dado real + limpeza de "Acesso Rápido" e botões do topo. (REGISTRO 15:20)

**Painel de Gestão — 1ª rodada (5 fixes de UX, um a um: analisar → corrigir → testar → commitar):**
- **2-B** "perto de vencer" só mostra prazos de hoje/futuro (`dias_ate >= 0`) — commit `b207cf9`
- **2-C** cliente "—" na tabela Fora do Prazo → usa campo `empresa` como fallback — `db32f4f`
- **2-D** "Unicred" (cliente) saiu do ranking de analistas (ignora responsavel == cliente) — `3baaee0`
- **2-E** race condition nos filtros de período resolvida com contador `_pgReqId` — `a1d63e8`
- **2-F** badge "ranking" → "N analistas" (contagem real via `total_colaboradores`) — `033a68e`
- **2-G** prefixo "4111"/"DDR4111" fica para sessão de pipeline (não corrigido)
- 4 testes novos em `tests/test_03_painel.py`; **215 pre-commit ✅** em cada commit

**Painel de Gestão — 2ª rodada (6 achados de LÓGICA de dados — DIAGNOSTICADO, NÃO corrigido):**
- Diagnóstico feito com script sobre as **funções reais de produção** (não estimativa). **4 dos 6
  dependem de decisão de negócio do Michel** antes de corrigir.
- **2-H** tempo médio inflado (45,8d; mede a conversa inteira, casos de 0 a 143d) · **2-I** categoria+volumosa
  poluída (alertas RISK_DRIVER_* + duplicados 4111/DDR4111, DLO/DLO_2061) · **2-J** "fora do prazo" com
  atraso fantasma (usa o prazo mais ANTIGO já cumprido) · **2-K/2-L** colaboradores (Michel quer rank único
  só Finaud — mas **NÃO existe cadastro de analistas**; campo `responsavel` está sujo) · **2-M** confirmar
  que tudo reflete o filtro (só "perto de vencer" a decidir).
- Tudo detalhado em `PENDENCIAS.md`, seção "REVISÃO — Painel de Gestão: 2ª rodada", associado à página.

### Feito nesta sessão (16/06 — tarde, 1ª sessão)
**Fix do script 13** (correlação travava por lentidão — cache nas funções puras, ~190× mais rápido:
∞ → ~30 s) · carga 15-16/06 rodada de ponta a ponta sem erros · REGISTRO + PENDENCIAS atualizados.

**Validação em produção do fix do script 13 (19:05):** usuário rodou a carga do **16/06 pela tela**.
Log: `ETAPA 13 CONCLUÍDA em 56.4s` (antes travava); tela carimbou **✓ 16/16, 21m28s, Erros 0**.

**Bug do MEL-07 corrigido (19:34):** `scripts_status` vinha vazio — emoji perdido no pipe cp1252.
Fix em `pipeline_jobs.py` + teste novo; 546 passed. ⚠️ Falta validar em uso na próxima carga.

**Regra de bordo nova:** pendência resolvida sai do PENDENCIAS e vira REGISTRO (gravada no CLAUDE.md).

### Feito nesta sessão (16/06 — 2ª sessão, testes de integração)
**Testes de integração do motor criados** — `tests/test_motor_integracao_regras.py`, 27 testes:
cobrem `_run_triagem_cadocs` com Regras 9-A/B/C e 0–8 completas. Todo I/O mockado (sem tocar
arquivos do pipeline). Resultado: **573 passed, 23 xfailed** (27 testes novos, zero regressões).
Descobertas fixadas: `_cpa` veta "arquivo" no corpo; `_fec` cobre "segue em anexo" e "seguem cadoc...bacen";
guard de imutabilidade requer `ORACULO_CARGA_EM_CURSO=1` para CO→AG.

### Feito nesta sessão (16/06 — 3ª sessão, bomba-relógio)
**Bomba-relógio desativada** — 9 módulos `triagem_auto*.py` recriados sem source (M6):
`triagem_auto.py`, `triagem_auto_drm.py`, `triagem_auto_6209.py`, `triagem_auto_conclusivo_automatico.py`,
`triagem_auto_risk_driver_alerta.py`, `triagem_auto_risk_driver_relatorio.py`, `triagem_auto_risk_driver_resp_auto.py`,
`triagem_auto_fogbugz.py`, `triagem_auto_leiautes_bacen.py`. Todos importam OK (9/9) · pytest **573 passed, 23 xfailed**
(zero regressões) · commit + push concluídos.

### Feito nesta sessão (16/06 — 4ª sessão, ambiguidade G1/G3 + protocolo)
**Análise das threads ambíguas em AGUARDANDO (55 casos):** classificadas em G1/G2/G3/G4.
**MEL-05 (script 10):** mantido desativado; 43 novos testes em `test_10_resolver_aguardando.py`.
**Fix G1 — "Valeu!" agora é conclusivo:** `helpers.py` + `motor.py` (Regra 9-C não reabre por agradecimento).
Backfill aplicado: **Monte Bravo → CONCLUÍDO** com data real 2026-02-03.
AG: 1.078 · CO: 3.479 · pytest **623 passed, 23 xfailed** · commit realizado.
**CLAUDE.md atualizado:** protocolo obrigatório de 7 passos para alterações no motor/triagem.
**PENDENCIAS.md atualizado:** G3 (4 casos: Fourtrade, Acredito SCD, Activtrades ×2) como 🔴 URGENTE.

### Feito nesta sessão (17/06 — documentação triagem)
**Documentação completa do sistema de triagem** → `documentações/DOCUMENTACAO_TRIAGEM.md`
Validação item a item com o dono do sistema (checker 5/5 ✅ ao fechar).

**CADOCs concluídos (5 de ~11):**
- ✅ DDR_2011 (seção 12.1) — R1–R5 + pós-conclusão, Grupos B/C/H (gaps)
- ✅ 4111 (seção 12.2) — R1–R5 + pós-conclusão, Grupo A
- ✅ DRL_2160 (seção 12.3) — R1–R5 + pós-conclusão, Grupo D/E
- ✅ DLI_2062 (seção 12.4) — R1–R5 + pós-conclusão, Grupo F/G
- ✅ DLO_2061 (seção 12.5) — R1–R5 + pós-conclusão, Grupos I/J (12+8 gaps)

**Backfill pendente:** 47 gaps mapeados — Grupos A–J → seção 13.10 do documento.

### Feito nesta sessão (18/06 — preparação da branch e qualidade do chat)
**Verificação completa antes de criar a branch:**
- Pipeline auditado (`executar_tudo.py --status`): DESATUALIZADO esperado (regra em vigor)
- JSONs restaurados: backup 22:24 de 16/06 → 1.079 AG / 3.478 CO ✅
- 83 arquivos `.backup_*` soltos deletados; 6 backups históricos migrados para pastas com CONTEXTO.md
- Auto-backups: 6 das 7 pastas deletadas (duplicatas ~9 GB liberados); 1 mantida com CONTEXTO.md

**Branch criada:** `implementacao/regras-triagem-v2` a partir de `desenvolvimento-front_end` → publicada no GitHub.

**Regras de saúde do chat adicionadas (`CLAUDE.md` + `gestor.md`):**
- `/gestor` agora reporta modelo em uso + adequação para o trabalho planejado
- Matriz de modelos: Sonnet (padrão), Opus (`/fast` para lógica complexa), Haiku (só dúvidas simples)
- Claude avisa quando parte Opus termina: "pode voltar para o Sonnet com `/fast`"
- Claude avisa quando contexto foi comprimido: "abra um chat novo ao terminar esta tarefa"

### Feito nesta sessão (18/06 — planejamento da implementação, completo)
**Seção 13.11 completa no DOCUMENTACAO_TRIAGEM.md** — plano detalhado e validado com o usuário:
- 13.11.1 Nomenclatura: `regra` = R1/R2... apenas; §-códigos são internos ao código
- 13.11.2 Princípio central: AG/CO não muda, só adicionamos rótulos
- 13.11.3 4 pontos de mudança (helpers → motor → script 11 → Flask)
- 13.11.4 9 fases detalhadas com salvaguardas, discussão e correções do usuário:
  - Fases 2+3 acopladas (helpers e motor andam juntos por CADOC)
  - Fase 6 corrigida: motor novo nos dados reais, não inferência aproximada
  - Fase 6 adicionada: 4 camadas de validação + indicador de confiança + relatório completo
  - Fase 7: script de comparação antes/depois como ferramenta permanente
  - Fase 8: limpeza com grep obrigatório + ordem de remoção definida
- 13.11.5 Simulação por CADOC (gabarito já definido na seção 12)
- 13.11.6 Critérios de validação por fase
- 13.11.7 Como o usuário valida sem ler código

**Decisões e princípios registrados:**
- `regra_confianca` não aparece na tela — só no relatório interno
- Falha silenciosa é pior que falha visível — princípio inviolável do sistema
- Padrão de backup com pasta organizada + CONTEXTO.md → virou regra geral no CLAUDE.md
- Script de comparação antes/depois → ferramenta permanente (triagem + IF-01)
- IF-01 e IF-02 documentados em PENDENCIAS.md com contexto completo

### Feito nesta sessão (19/06 — infraestrutura de memória compartilhada entre IAs)

**Repositório `memoria-compartilhada-projetos-ias` criado no GitHub:**
- GitHub CLI (`gh`) instalado na máquina e autenticado
- Repositório privado criado: `github.com/michelruicosta/memoria-compartilhada-projetos-ias`
- Arquivo `PROJETOS.md` já presente com estado de todos os projetos + IF-01 completo

**IF-01 formalizado com estrutura e regra de manutenção:**
- Estrutura padrão definida para todos os documentos de todos os projetos:
  O que é → Por que existe → Como funciona → Regras → Exemplos → Dependências
- Modelo de referência: `DOCUMENTACAO_TRIAGEM.md`
- Regra obrigatória: mudança no sistema = atualização da documentação no mesmo commit
- Dois gatilhos: dentro de qualquer protocolo de mudança + no `/fechar`
- Tudo registrado no `PROJETOS.md` para que qualquer IA encontre ao iniciar

**`PROJETOS.md` adicionado ao ritual de abertura de todas as IAs:**
- `CLAUDE.md` (este projeto): leitura de `D:\template_projeto_ai\PROJETOS.md` no `/iniciar`
- `normativos_ia` gestor-projeto.mdc: idem
- `Auditoria IA` gestor-projeto.mdc: idem
- `AppSheet` AGENTS.md: idem
- `app_treino` AGENTS.md: idem
- A partir do próximo `/iniciar` em qualquer projeto, todas as IAs têm visão cruzada

### Feito nesta sessão (21/06 — sistema de documentação + análise G3)

**Sistema de documentação permanente criado:**
- `GUIA_DO_PROJETO_IA.md` criado (13 seções) — porta de entrada para qualquer IA ou pessoa entrar no projeto do zero
- Seção 9 adicionada ao `MAPA_DO_PROJETO.md`: cascata de dependências (9.1/9.2) + estrutura dos arquivos JSON (9.3) + backups obrigatórios (9.4)
- `PADROES.md` (template) atualizado com modelo completo replicável: 3 camadas, papéis, hierarquia de regras, checklist /fechar, /iniciar, auditoria mensal, papel de mentor, "Plano antes de agir"
- `CLAUDE.md` atualizado: regra "Plano antes de agir" (declaração obrigatória antes de qualquer ação), verificação de estrutura de arquivos de dados, verificação de gatilhos no /iniciar
- `PENDENCIAS.md`: seção "🔗 AGUARDANDO GATILHO" criada (IF-01 como primeiro gatilho)

**Análise G3 — Passo 1 (Simular) concluído:**
- 7 threads encontradas (não só 4) via `03_integrador_dados_site.json`
- 3 devem ir para CONCLUÍDO, 4 ficam em AGUARDANDO
- Thread IDs e classificação salvos em `PENDENCIAS.md` → prontos para Fase 1 TDD
- Decisão: G3 NÃO é patch avulso — pertence à Fase 1 como caso de teste

**Lições registradas (processos):**
- "Plano antes de agir" é o mecanismo central: Michel vê o plano antes de qualquer ação e pode interromper
- Análises que vão ao PENDENCIAS devem ser exaustivas (script em todos os dados, não amostra)
- Perguntas sobre sequência/dependência exigem consulta ao plano documentado antes de responder

### Feito nesta sessão (21/06 — refinamentos pós-teste do /iniciar)

Após testar o `/iniciar` numa sessão nova, identificamos e corrigimos três lacunas:

- **`CLAUDE.md`:** observação de mentor obrigatória ao encerrar o `/iniciar` — a IA deve apontar algo que Michel não perguntou mas deveria saber antes de começar
- **`SESSAO_ATUAL.md`:** campo "Última carga" separado em dois — "Última carga triagem (02→11)" e "Último enriquecimento (12→17)" — para distinguir pipeline core de enriquecimento
- **`CLAUDE.md`:** checklist de restrições no `/fechar` — 3 perguntas obrigatórias: surgiu restrição nova? alguma foi cumprida? as que ficaram ainda fazem sentido?
- **`PENDENCIAS.md`:** gatilho registrado para automatizar atualização dos campos de carga via `executar_tudo.py` após Fase 6
- **Decisão:** `/fechar` registra WHAT + WHERE em `SESSAO_ATUAL.md` e HOW + WHY detalhado em `REGISTRO_CORRECOES.md`

### Feito nesta sessão (19/06 — padronização do /iniciar e simulação de fluxo)

**Regra do `/iniciar` reescrita em todos os projetos:**
A IA agora deve reproduzir o motivo real dos documentos ao abrir o chat — não parafrasear. Para números: explicar a origem (por que esses valores, o que aconteceu para chegarem aqui). Para regras em vigor: dizer qual pacote de tarefas, quais etapas e qual o risco concreto de violar. Aplicado em: Oráculo (`iniciar.md`), Claude Code global, Auditoria IA, normativos_ia, app_treino, AppSheet e template.

**Simulação do `/iniciar` validada (Simulação 3):**
Fluxo correto confirmado com Michel — nível de detalhe aprovado. Identificado que a Simulação 1 e 2 falharam por inventar contexto genérico em vez de ler o SESSAO_ATUAL.md.

**Cursor — User Rules:** confirmado que não é necessário configurar — todos os projetos Cursor já têm `.cursor/rules/gestor-projeto.mdc`.

**GUIA_DO_PROJETO_IA.md — decisão confirmada:**
Mesmo nome em todos os projetos. Fazer APÓS pendências de cada projeto entregues. Não criar do zero — revisar o que existe e preencher lacunas.

**Pendência registrada:** discussão sobre como a IA lê e entende o sistema (fluxo de leitura, quais documentos, em que ordem) ficou confusa — registrada em PENDENCIAS.md para retomar em sessão específica.

### Feito nesta sessão (19/06 — padronização multi-projeto e preparação da Fase 1)

**Fase 1 NÃO iniciada** — sessão focou em alinhamento de comunicação entre Michel e todas as IAs.
Era necessário antes de começar a implementação para evitar ruído de vocabulário.

**Padronização de comunicação em todos os projetos:**
- `CLAUDE.md` (este projeto): seção "Como falar com Michel" + protocolo de 6 pontos (O que / Por que / Como / Onde / O que muda / Impactos) + protocolo "parquear e continuar"
- `normativos_ia/.cursor/rules/gestor-projeto.mdc`: **criado do zero** (projeto não tinha config de IA) — rituais de abertura/encerramento + ambos os protocolos
- `Projeto_Auditoria_IA/.cursor/rules/gestor-projeto.mdc`: "Como falar com Michel" + protocolo de 6 pontos + "parquear e continuar" + corrigido "Bruna" → "Michel" (era o nome da máquina Windows, não uma pessoa)
- `AppSheet/AGENTS.md`: "Como falar com Michel" + protocolo de 6 pontos + "parquear e continuar"
- `app_treino/AGENTS.md`: "Como falar com Michel" + protocolo de 6 pontos + "parquear e continuar"
- ✅ Confirmado: **Antigravity lê o mesmo AGENTS.md que o Codex** (app_treino) — nenhum novo arquivo necessário

**Problema de nomenclatura inconsistente documentado em `PENDENCIAS.md`:**
- Campos como `alvo_triagem_auto`, grupos como `DDR4111` têm nomes confusos — seção nova no PENDENCIAS.md com o problema completo (6 pontos + salvaguardas)
- **NÃO fazer agora** — risco alto (30+ arquivos); fazer após Fase 1 da implementação, com levantamento completo primeiro

### Feito nesta sessão (18/06 — documentação triagem, continuação)
**CADOCs concluídos (mais 7):**
- ✅ DRM_2060 (seção 12.6) — regras completas + pós-conclusão + Grupo K
- ✅ S5 (seção 12.7) — regras completas + pós-conclusão + Grupo L
- ✅ RETORNO_BACEN (seção 12.8) — R1–R6 + pós-conclusão + Grupos M/M2/M3/M4/N
- ✅ SUPORTE (seção 12.9) — R1–R7 + pós-conclusão + Grupos O/O2/P/P2/Q
- ✅ DRSAC (seção 12.10) — regras + Grupo R
- ✅ FORCAPITAL (seção 12.11) — regras + Grupo S + pós-conclusão VALIDAÇÃO PENDENTE
- ✅ CADOC 6209 (seção 12.12) — 1 thread incompleta + Grupo T

**Auditoria de consistência do pipeline (Grupo U):**
- Investigados os 24 threads que estavam no integrador mas não nas triadas
- **Conclusão: pipeline íntegro.** 18 IGNORADO (correto) + 4 F→F internos Finaud (correto) + 1 Oliveira Trust (já triada) + 1 CADOC 6209 (Grupo T, dados incompletos)
- Todos os 4 F→F investigados: Andrea/Pedro → colega interno, empresa='', correto não triar
- 2 com `status_processo=PENDENTE` (ZIIN/Unicred, Atual Câmbio): tarefas internas abertas na Finaud — fora do escopo da triagem automática

**Total de gaps documentados:** ~50 (Grupos A–U) → seção 13.10 do documento

✅ **JSONs restaurados (18/06/2026)** — inconsistência corrigida, dados limpos para a implementação.

  **O que aconteceu:** a carga automática de 23:50 de 16/06 moveu incorretamente 203 threads de
  CONCLUÍDAS para AGUARDANDO. Em 18/06, antes de criar a branch de implementação, os JSONs foram
  restaurados para o backup de 22:24 de 16/06 (estado correto).

  **Estado atual:** 1.079 AG / 3.478 CO ✅
  **Backup pré-implementação:** `data/json/pipeline/backups/20260618_2322_pre_implementacao_regras_v2/`

  **Regra em vigor:** ✅ LEVANTADA em 23/06 — merge concluído, cargas liberadas.

---

## 🔥 Pendência mais quente

🔴 **Tela de Triagem — revisão UX com o Fable** — a tela `/operacional` está "muito poluída"; revisar juntos ao vivo → condensar diagnóstico → Fable ajusta. Ver `PENDENCIAS.md`.
🔴 **Pacote 1 da Análise Fable — falhas silenciosas** — 6 correções pequenas de baixo risco que fecham os buracos mais perigosos (motor sem regras em silêncio, normativo perdido, coletas fingindo sucesso). Ver `ANALISE_FABLE_PIPELINE.md` seção 4 + `PENDENCIAS.md`.

**Michel decide a ordem entre os dois no próximo `/iniciar`.**

🟡 **Pacote 2 (responsabilidades)** — executar junto com a padronização de categorias já planejada.
🟡 **Revisão das demais telas** — após Triagem: Aprendizado IA, Normativos, FOG.
🟡 **Renumeração dos scripts** — buraco no 10, 18/19 nunca existiram, 20 avulso; incluir renomeação dos JSONs (achado P-07).

---

## ▶️ Próximo passo

1. **Sempre ao iniciar:** `python executar_tudo.py --status` + verificar seção "🔗 AGUARDANDO GATILHO" do `PENDENCIAS.md`.
2. **🔴 Tela de Triagem com Fable** OU **🔴 Pacote 1 da Análise Fable** — Michel escolhe qual vem primeiro.
3. **🟡 Pacote 2 + Padronização de categorias** — desbloqueada: a Análise Fable (pré-requisito) foi entregue em 02/07.
4. **🟡 Revisão das demais telas** · **🟡 Renumeração dos scripts + JSONs**.
5. **🔵 BACKLOG:** Pacote 3 performance (absorve o item ijson) · Pacote 4 faxina (pode ser fatiado).

Demais pendências abertas: ver `PENDENCIAS.md`.

### Feito nesta sessão (01/07/2026 — itens pequenos do backlog + carga + 23 validações)

**Itens do backlog concluídos:**

- **Item #2 — CLAUDE.md consolidado:** seção "Atualizar no momento certo" (duplicata) removida. Conteúdo integrado em "Regra: toda decisão importante vai para o lugar certo" com tabela de 6 linhas e nota de timing.
- **Item #3 — Auditoria da pasta `documentações/`:** datas de revisão adicionadas em `ARQUIVOS_NAO_UTILIZADOS_NA_ROTINA.md`, `ESPEC_TELA_OPERACIONAL.md` e `MATRIZ_PADROES_CADOC.md`. Sobreposição entre DOCUMENTACAO_TECNICA e MAPA avaliada — sem ação necessária (complementares). Item resolvido; removido do PENDENCIAS.md.
- **Item #4 — Bug do watchdog corrigido:** timer de script anterior não era cancelado ao iniciar novo script — com 17 scripts no pipeline, timers se acumulavam. Fix: variável global `_evento_parar_atual` cancela o timer anterior a cada novo `iniciar_watchdog()`. 3 testes novos em `tests/test_pipeline_watchdog.py`. Commit `ab7921d`.

**Carga de 01/07:**
- Michel subiu a carga pela tela. Pipeline completo rodou em ~15 minutos.
- AG: 990 → 996 (+6) | CO: 3.730 → 3.741 (+11) | Total: 4.720 → 4.737 (+17 threads novas)
- Script 13 (correlações): 2.190/4.754 = 46,1% — dentro da faixa esperada 30-60% ✅
- 0 watchdogs disparados.

**REGISTRO_CORRECOES.md completamente limpo:**
- 23 itens com `⚠️ VALIDAÇÃO PENDENTE` acumulados desde junho foram fechados.
- 13 fechados automaticamente por verificação nos dados (grep nos JSONs).
- 10 fechados após confirmação de Michel no painel.
- REGISTRO agora tem 0 itens pendentes — marco histórico da sessão.

**Commits:** `ab7921d` (watchdog + docs) · `8ab911c` (23 validações fechadas)

### Feito nesta sessão (30/06 — 4ª sessão: investigação P-AUD-03 + consistência motor)

**Investigação P-AUD-03 (Atual Câmbio):**
- Thread `GMTHRID_1865189590887992466` investigada: 1 msg F→F (Andrea→Flávio), aguarda COS4010 de abr/2026 da empresa. Sistema correto (AGUARDANDO). Bloqueador externo.
- Descoberta: thread estava incorretamente em CO com regra R1 + motivo "aguarda tratamento" (contradição). Causa: backfills Fase 6/8 em junho/22 gravaram regra e status em momentos separados.

**Varredura e correção de consistência regra/motivo:**
- 7 threads movidas CO→AG (F→F internas sem entrega ao cliente): Guru/4111, Acoriana/S5, Unicred/DRL, Corpservices/DLO, Rfacontabil/S5, Commcor/DLO, Atual Câmbio/DDR
- 1 motivo corrigido em CO (Terra/DDR — entrega real ao cliente, motivo desatualizado)
- 24 threads CO com motivo "aguarda tratamento" stale: campo `motivo` atualizado com `motivo_conclusao` (status CO correto, só texto errado)
- AG: 983→990 | CO: 3.737→3.730 | Total: 4.720 preservado

**Infraestrutura:**
- Nova regra gravada no `CLAUDE.md`: "verificar fonte primária antes de afirmar, mesmo em perguntas pequenas"
- `tests/test_consistencia_co_motivo.py` criado: 6 testes garantem que motivo F→F "aguarda tratamento" nunca aparece em CO
- Pre-commit corrigido: de 9 minutos → 3 segundos (só testes rápidos; CI continua com suite completa)
- PENDENCIAS.md: ijson registrado como solução para re-triagem completa sem MemoryError

**Commits:** `e1ecb81` (correção 7 threads + CLAUDE.md) · `53e16c2` (pre-commit 3s) · `800d7a9` (teste consistência + 24 motivos)

Último /fechar: 2026-06-30 (4ª sessão) — memórias revisadas ✅

### Feito nesta sessão (30/06 — 3ª sessão: migração do projeto para nova pasta)

**Projeto migrado de `D:\oraculo_360_finaud` para `D:\02_Finaud\Projetos\ativos\oraculo_360_finaud`:**
- Pasta movida sem quebrar nenhum processo (nenhum path hardcoded no código)
- venv funcionou normalmente no novo caminho (Windows preservou os caminhos internos)
- Memória do Claude: já estava na pasta correta (`D--02-Finaud-Projetos-ativos-oraculo-360-finaud`) pois o chat já rodava a partir do novo caminho
- Git corrigido: `safe.directory` adicionado para o novo caminho (bloqueio de ownership pós-migração)
- Nenhum script, regra ou dado afetado — sistema íntegro

### Feito nesta sessão (30/06 — 2ª sessão: GUIA_DO_PROJETO_IA.md + push GitHub)

**`documentações/GUIA_DO_PROJETO_IA.md` criado** — documento de entrada único para qualquer IA ou pessoa nova. 8 seções: o que é o projeto, glossário básico, fluxo do pipeline, mapa de documentos, o que não tocar, como começar nos primeiros 10 minutos, números-chave e glossário completo. Pendência 🔴 URGENTE removida do PENDENCIAS.md; entrada no REGISTRO_CORRECOES.md gravada.

**Push ao GitHub:** 17 commits enviados para `desenvolvimento-front_end` — branch sincronizada. Commit final: `ef2d352`.

---

### Feito nesta sessão (30/06 — sistema de continuidade + reorganização da memória)

**Problema resolvido:** qualquer IA ou pessoa que chegasse ao projeto após meses parado não saberia
por onde começar, o que está atualizado, o que mudou. Sem mecanismo que garanta isso.

**Backfill motor (2 threads AG→CO):**
- Causa: regras novas do motor (§4e DLO, G3) adicionadas ao código após a última carga — JSON estava desatualizado.
- 2 threads movidas para CONCLUÍDO: `GMTHRID_1868369590452880259` (Monopólio Câmbio — DLO §4e) e `GMTHRID_1867439186878557305` (DDR).
- AG: 985→983 / CO: 3.735→3.737 / Total: 4.720 preservado.

**Migração de regras da memória → CLAUDE.md (5 regras):**
- "Verificar o sistema inteiro antes de afirmar que algo não existe" (grep .py + .html + tests + config)
- "Três verificações antes de qualquer correção" (REGISTRO + PENDENCIAS + conflito)
- "Varrer VALIDAÇÃO PENDENTE ao fechar qualquer ciclo de pipeline"
- "Propor texto antes de gravar conhecimento em documento"
- Passo 3 do protocolo de 7 passos: adicionado `ORACULO_CARGA_EM_CURSO=1`

**Sistema de continuidade implementado:**
- Memória reorganizada: subpastas `comportamento/` (13), `projeto/` (4), `tecnico/` (8)
- 19 arquivos movidos para `_archive/memory/` (preservados, não apagados)
- `/fechar`: Bloco 1.8 — revisão de memórias + registro de timestamp no SESSAO_ATUAL
- `/iniciar`: Passo 0 — detecta se `/fechar` rodou na sessão anterior; avisa Michel se não rodou
- `CLAUDE.md`: regra de sugestão proativa do `/fechar` + regra de revisão de memórias ao encerrar
- `PENDENCIAS.md`: GUIA_DO_PROJETO_IA marcado como 🔴 URGENTE para próxima sessão

**Commits do dia:** `e2ba0ef`, `1dce18f`, `48e00b9`

### Feito nesta sessão (29/06 — P-AUD completo + Carga #56 + Script 10 removido)

**P-AUD-01/07/08 implementados e validados:**
- `_ff_comunicado_interno` (Regra 0c): e-mails internos informativos F→F → CONCLUÍDO automaticamente. 7 threads backfill.
- `_finaud_entrega_conclusiva` Grupo 8: "enviando em anexo" / "compartilhar detalhes da estimativa" → CONCLUÍDO.
- `_finaud_instruiu_cliente` Sinal L: habilitação de transação via STA/Autran/SLIM800 → CONCLUÍDO.
- 6 testes novos em `test_triagem_categorias.py` · 10 testes em `TestFfComunicadoInterno`.
- P-AUD-02/04/05 já implementados em sessões anteriores. P-AUD-03/06 confirmados como corretos (sem ação).

**Carga #56 (25-29/06) concluída:** 44 novas threads — 24 AGUARDANDO, 20 CONCLUÍDO. Pipeline limpo. MEL-07 ✅ VALIDADO em uso real.

**Script 10 removido do pipeline definitivamente:**
- Problema: ignorava as regras do motor — qualquer mensagem nova removia thread de AGUARDANDO (266 casos incorretos em simulação).
- Solução: Script 11 já faz o trabalho correto. Script 10 arquivado em `_archive/scripts/`.
- `resolver_aguardando_auto.py` (alias) também arquivado. Funções `_parse_data_msg` e `_get_ultima_mensagem` migradas para `helpers.py`.
- MEL-05 e MEL-06 encerrados. 658 passed, 23 xfailed (zero regressões).
- Commits: `a86dcc7`, `8332e2a`, `70c2445`, `15c9bce`, `60a1f08`, `e4a6789`.

**Decisão registrada:** renumeração dos scripts (buraco no 10, 18/19 nunca existiram, 20 avulso) → fazer em sessão dedicada futura.

### Feito nesta sessão (27/06 — backfill G4/R6 + revisão arquitetural completa)

**pytz instalado:** `pip install pytz` no venv → desbloqueou 18 testes de infraestrutura; total passou de 648 → 666 passed, 23 xfailed.

**Backfill G4/R6 — 4 threads movidas para CONCLUÍDO:**
- Azumidtvm (RETORNO_BACEN) — Sinal K: "para solucionar... precisará fazer X"
- Saygogroup (DDR_2011) — R6: Finaud confirmou horário de reunião
- Galápagos Capital (DDR_2011) — Thiago Alves era o contato, mesma empresa
- BGC (FORCAPITAL) — R6: reunião agendada
- ARC Corretora: já estava em CONCLUÍDAS (não movida). AG: 997→993 / CO: 3.679→3.683.
- Commits `32a9622` (backfill) + push OK.

**Revisão arquitetural dos 10 supervisores — CONCLUÍDA:**
- `scripts/triagem/_base.py` criado: função `triar_base()` centraliza todo o motor (§6/§6b/§5-anexo/F→C/F→F/C→F).
- 10 supervisores migrados (ddr4111, dlo, drm, dli, drsac, forcapital, retorno_bacen, s5, suporte, cadoc6209): de ~400 linhas cada → ~80-200 linhas (só tabelas de regras + delegate).
- Parâmetros variáveis por supervisor preservados: `com_sec5_anexo` (True em ddr4111/dlo/drm/dli), `com_sec6b` (False só em dli), `sec35` (False em ddr4111/retorno_bacen).
- Baseline AG/CO: 993/3683=4676 — idêntico antes e depois da migração.
- Commit `ae84136` + push. Pre-commit hook OK (2664 linhas removidas).

### Feito nesta sessão (26-27/06 — CLAUDE.md + motor G4/R6)

**CLAUDE.md consolidado:** removidas seções duplicadas (SITUAÇÃO, INTAKE, ENCERRAMENTO, VERSIONAMENTO, PRIMEIRA COISA, Saúde do chat detalhada) — substituídas por referência única aos comandos `/iniciar`, `/salvar`, `/fechar`. Adicionadas: regra "atualizar no momento certo" (tabela onde vai cada tipo de mudança) e regra "consultar antes de explorar" (ciclo: consultar MAPA → descobrir → confirmar → documentar).

**INICIO_CHAT.md:** removida info desatualizada de branch/regras (agora buscadas ao vivo pelo `/iniciar`).

**MAPA_DO_PROJETO.md seção 9.3:** adicionado bloco de navegação do JSON 03 com código confirmado em sessão (`j03['threads']` → `mensagens` → `contato_origem['lado']`).

**Motor G4 — Sinal K + R6:**
- `helpers.py`: Sinal K adicionado em `_finaud_instruiu_cliente` — "para solucionar... precisará/deverá + verbo" (confirmado Azumidtvm RETORNO_BACEN)
- `helpers.py`: nova função `_finaud_agendou_reuniao` — Finaud confirmou reunião agendada = CONCLUÍDO (casos Saygogroup DDR_2011 e BGC FORCAPITAL)
- `motor.py`: bloco R6 adicionado no pós-processamento
- `test_triagem_helpers.py`: 7 testes novos · **174 passed, 23 xfailed** ✅

**Pendência pytz registrada:** 42 testes falham por `pytz` não instalado — só os testes de triagem/motor (174) são afetados pelo trabalho do motor; os 42 são infraestrutura.

**Passo 3 (backfill) pendente:** simulação e gravação ficaram para a próxima sessão — 5 threads confirmadas: Azumidtvm, Saygogroup, Galápagos Capital, ARC Corretora, BGC.

### Feito nesta sessão (26/06 — reorganização da documentação, Frente 2)

**Problema definido e validado com Michel:**
- Problema raiz: informação espalhada sem endereço fixo — a IA vai no código, gasta tokens, e qualquer pessoa nova ficaria perdida
- Objetivo: um padrão de trabalho que não depende de quem está na cadeira — qualquer IA ou pessoa chega, lê e continua
- 12 impactos mapeados (guardados em memória)
- 3 passos: Classificar → Limpar → Travar

**Executado:**
- 36 arquivos classificados em: fica / atualizar / arquivar / criar
- 10 arquivos movidos para `_archive/docs/documentacao_20260626/` com CONTEXTO.md
- `MAPA_DO_PROJETO.md` seção 5 reescrita: "para cada pergunta, um documento"
- REGISTRO_CORRECOES.md atualizado com entrada datada

**O que falta da Frente 2:**
- Inventário completo do sistema → tabela de todas as regras ativas no motor
- Verificador de links quebrados nos `.md`
- Frente 3: trava no `/fechar` + regra no `CLAUDE.md`

---

### Feito nesta sessão (26/06 — reorganização da documentação, Frente 1)

**Diagnóstico da bagunça:** 42 arquivos / +14 mil linhas com 3 doenças — mente (info falsa), duplica (regra em vários lugares), sem manutenção. Foi a causa da confusão de 25/06 (auditoria na ordem errada).

**Frente 1 "Estancar a mentira" — 6 correções** (ver REGISTRO 26/06): branch, 2 travas mortas da Fase 6, 2 comandos renomeados (`/gestor-*` → `/fechar` e `/salvar`), números AG/CO 1.003/3.673 → 997/3.679. Nenhum histórico tocado.

**Princípios decididos (validados com Michel):**
- **5 tipos de documento:** REGRA (`CLAUDE.md`) · CONHECIMENTO (`MAPA`/`GUIA`) · ESTADO (`SESSAO_ATUAL`) · O QUE FALTA (`PENDENCIAS`) · HISTÓRICO (`REGISTRO`).
- Regra mora num lugar só; os outros apontam. Em conflito, manda o `CLAUDE.md`.
- O que o sistema sabe (branch, números) não se escreve à mão — o `/iniciar` busca ao vivo.
- A IA avalia e aponta se pode rodar o pipeline (não Michel de cabeça).
- MAPA vira índice navegável por links; regra de motor mostra só a atual, histórico no REGISTRO.
- Propor antes de gravar conhecimento (criar ou atualizar).

**3 memórias gravadas:** IA avalia pipeline · propor antes de gravar conhecimento · re-verificar travas com condição de expirar.

### Feito nesta sessão (25/06 — tarde, análise arquitetural + decisão de ordem)

**Leitura completa dos 10 supervisores:** ddr4111, dlo, drm, dli, s5, suporte, retorno_bacen, drsac, forcapital, cadoc6209 lidos integralmente.

**Mapeamento concluído — universal vs específico:**
- **Universal (idêntico em todos os 10):** 12 funções de detecção wrapper, bloco F→F inline, §6 cluster, §6b espelho, motor de execução (~300 linhas)
- **Específico por CADOC:** §5d (só RB), §4e DDR4111/SUPORTE, §4f-rb (só RB), §3.5+ desligado em DDR4111/DLI/RB, F→C substantiva ausente em DDR4111/DLO/DLI/S5, §5-anexo só em DDR4111/DLO/DRM/DLI

**Decisão de ordem — Michel (25/06):**
- Ordem nova: **Auditoria (1º) → Arquitetura (2º, obrigatória antes da produção)**
- Motivo Michel: auditoria tem impacto imediato no trabalho; sistema ainda não está em produção, então há tempo
- Restrição: arquitetura NÃO pode ficar para depois da produção — em produção, regras esquecidas têm consequências regulatórias

**PENDENCIAS.md:** ordem dos dois PLANEJADO swapada para refletir a decisão.

---

### Feito nesta sessão (25/06 — F→F backfill + padrões conclusivos)

**Padrões F→F conclusivos adicionados ao `_PAT_FF_CONCLUSIVO` (`helpers.py`):**
- "conforme solicitado/combinado/alinhado, segue" + variantes
- Corrigido bug em `simular_regra_ff.py` (variável `total_muda` indefinida)

**Backfill F→F concluído:**
- 7 threads PENDENTE (DDR/4111/DRL) agora classificadas: 1 CONCLUÍDO (DRL_2160 Ativa), 6 AGUARDANDO
- AG: 1.002→1.003 | CO: 3.673→3.673 | pytest: 648 passed, 23 xfailed ✅

**Descobertas importantes registradas em PENDENCIAS.md:**
- Revisão arquitetural (1º): centralizar decisões universais dos supervisores
- Auditoria de cobertura (2º): varrer ~1.003 threads AGUARDANDO sistematicamente com Michel
- Revisão arquitetural: centralizar decisões universais dos supervisores (hoje cada um é independente)

**Entendimento do domínio F→F aprofundado:**
- F→F conclusivo = mesma lógica dos outros casos: quem pediu/perguntou foi atendido?
- "conforme solicitado, segue" = sinal universal de entrega interna → CONCLUÍDO
- Raiz dos buracos: 10 supervisores independentes sem camada de regras compartilhadas obrigatória

---

### Feito nesta sessão (24/06 — G3 completa + qualidade do motor)

**Carga 23/06 rodada + MEL-07 validado:** campo `scripts_status` com 16 scripts "ok" confirmado em `/admin/logs`. AG: 1.003 / CO: 3.672 na entrada do dia.

**Regra G3 implementada (DDR/4111 → todos os 10 supervisores):**
- `helpers.py`: nova função `_par_conclusivo` — detecta quando cliente diz "de acordo", "ok", "anotado", "ciente", "tudo certo" etc. após instrução da Finaud, sem nova pergunta.
- `ddr4111.py`: Regra G3 como Regra(3) em `REGRAS_CONCLUIR["ultima_cliente_para_finaud"]`.
- 9 outros supervisores (dlo, dli, drm, s5, suporte, retorno_bacen, drsac, forcapital, cadoc6209): mesma regra adicionada.
- Backfill: Acredito SCD movida de AG→CO (única afetada). AG: 1.003→1.002 / CO: 3.672→3.673.
- Testes: 2 casos G3 + snapshot DDR4111 atualizado. **648 passed, 23 xfailed**.

**Hook pre-commit corrigido:** usava `python` global (sem pytest). Agora detecta e usa `./venv/Scripts/python.exe` automaticamente.

**CLAUDE.md atualizado:**
- Passo 0 adicionado ao protocolo de 7 passos: declarar escopo (universal ou específico) antes de qualquer implementação. Referência real: G3 implementada só no DDR/4111 inicialmente.
- Regra nova: nomes de funções/arquivos precisam de aprovação prévia do Michel — devem ser intuitivos, não jargão técnico.

**Descobertas e aprendizados:**
- Arquitetura atual: cada supervisor é independente — regras universais precisam ser adicionadas manualmente em todos. Passo 0 do protocolo garante que isso não seja esquecido.
- 22 dos 23 casos G3 nos outros supervisores já eram cobertos por §4d/§4e. G3 adicionou proteção para casos futuros e 1 caso atual (Joana Martines/SUPORTE).
- Alerta recebido sobre Leonardo Herz (Monte Bravo, DDR_2011) — confirmado como pendência F→F já conhecida.

**Commits:**
- `e6081a7` — G3 no DDR/4111 + backfill Acredito SCD + protocolo Passo 0 + hook corrigido
- `7e17c6b` — G3 expandida para os outros 9 supervisores

### Feito nesta sessão (23/06 — merge da branch + documentação de amanhã)

**Merge `implementacao/regras-triagem-v2` → `desenvolvimento-front_end` (PR #1):**
- PR criado via `gh pr create` e aprovado por Michel no GitHub
- Merge confirmado: 3.013 linhas inseridas, 32 arquivos atualizados
- Testes pós-merge: **646 passed, 23 xfailed** — zero regressão ✅
- Restrição "não rodar carga" levantada

**Documentação:**
- `documentações/PENDENCIAS.md`: item 🔴 URGENTE adicionado — passo a passo da retomada de cargas amanhã (7 passos: verificar dependências → acionar pela tela → acompanhar via Claude in Chrome → PR `desenvolvimento-front_end` → `main` após carga validar)

---

### Feito nesta sessão (22/06 — Fases 4+6+7+8: badge R-code + correção 119 AG→CO)

**Badges R-code na tela de Triagem (Fases 4+7):**
- `painel_oraculo.py`: endpoint `/api/triagem_motivos` passou a retornar campo `regra` por thread
- `templates/email_operacional.html`: CSS `.badge-regra` (R1-R5 em cores distintas) + função JS `badgeRegra()` + badge nos cards
- 22 cards verificados com badges corretos na tela real do Flask ✅

**Backfill histórico (Fase 6):**
- `scripts/backfill_regra_fase6.py` rodado — campo `regra` adicionado em 3.265 registros existentes
- Backup em `data/json/pipeline/backups/20260622_1422_backfill_regra_fase6/`

**Correção 119 threads AG→CO (Fase 8):**
- Michel identificou: threads com `regra=R1` (motor diz CO) ainda marcadas como AGUARDANDO — status errado
- Causa: backfill da Fase 6 usou resultado do motor dry-run; motor disse CO→R1 mas thread estava no JSON AG
- `scripts/backfill_ag_para_co_fase8.py` criado e executado: 119 threads movidas com datas reais do JSON 03
- Backup: `data/json/pipeline/backups/20260622_1740_backfill_ag_para_co_fase8/`
- Resultado: AG 1.079→960, CO 3.478→3.597, R1 em AG = 0 ✅
- **646 passed, 23 xfailed** (pre-commit hook) — zero regressão ✅

**Scripts arquivados:** `dry_run_fase5.py`, `backfill_regra_fase6.py`, `backfill_ag_para_co_fase8.py` → `_archive/`
**Pendências criadas:** Fase B (auditoria CO reversa) + 6 threads sem regra em AG → `PENDENCIAS.md`

---

### Feito nesta sessão (22/06 — Fase 1 TDD)

**Fase 1 TDD CONCLUÍDA — Testes de triagem prontos**

- **Arquivo criado:** `tests/test_fase1_regras_2011_e_4111.py` (376 linhas)
- **6 testes com threads REAIS** (DDR_2011 R1+R2, 4111 R1)
- **Commit:** `[implementacao/regras-triagem-v2 662ccea]`

### Feito nesta sessão (22/06 — Fase 2+3: DDR_2011 + 4111)

**Fase 2+3 CONCLUÍDA para DDR_2011 e 4111 — campos `status` e `regra` implementados**

- **`scripts/triagem/motor.py`:**
  - `_registro_concluido_auto`: adicionou parâmetro `regra: str = "R1"` + campo `"status": "CONCLUIDO"` no dict
  - `_registro_aguardando_auto`: adicionou parâmetro `regra: str = ""` + campo `"regra": regra` no dict
  - Pós-processamento AG→CO: varredura que garante `status="CONCLUIDO"` e `regra="R1"` em todos os CO
- **`scripts/triagem/ddr4111.py`:**
  - `tid_regra: Dict[str, str] = {}` para rastrear R-code por thread
  - R2 (C→F), R3 (§3-inv + fallback F→C), R4 (§3.5), R5 (F→F) — todos rastreados no loop
  - `regra=tid_regra.get(tid, ...)` passado nas 3 chamadas de `_registro_*_auto`
- **Validação:** 6/6 testes passando · **629 passed, 23 xfailed** (zero regressão)
- **REGISTRO_CORRECOES.md:** entrada datada com Em miúdos + validação ✅
- **PENDENCIAS.md:** Fase 2+3 removida (concluída); CADOCs restantes adicionados como próximo passo

**Decisão de mentor:** Parar por aqui hoje. Fase 2+3 DDR+4111 entregue. Próxima sessão: DRL_2160 → DLI → DLO → RETORNO_BACEN.

---

### Feito nesta sessão (21/06 — sistema de auditoria automática)

**Implementação completa: hook diário + rotina mensal agendada**

- **Auditoria Diária (no `/fechar`):** 
  - Criei `scripts/auditar_documentacao.py` — valida 5 checks críticos
  - Atualizado `.claude/commands/fechar.md` com Bloco 1.5 (auditoria + aviso)
  - Roda ~2-3s; avisa se encontrar buraco (não bloqueia commit)
  - Resultado: arquivo `documentações/AUDITORIA_ULTIMACARGA_VALIDACAO.md`

- **Auditoria Mensal (agendada, cloud-based):**
  - Criei `scripts/auditar_documentacao_completa.py` — análise cruzada completa
  - Configurei tarefa persistente: **dia 28 do mês às 17h** (Brasília)
  - Se encontrar problema: cria entry automática em PENDENCIAS.md
  - Faz git commit + push para `desenvolvimento-front_end`
  - Próxima execução: 28/07/2026 às 17h

- **Documentação atualizada:**
  - `CLAUDE.md`: seção nova "Auditoria de documentação — diária e mensal"
  - `/fechar.md`: Bloco 1.5 com instruções de auditoria

- **Validação:**
  - ✅ Scripts rodam sem erros (exit code 0)
  - ✅ Estrutura de 5 checks operacional
  - ✅ Integração com `/fechar` funciona
  - ✅ Tarefa agendada criada e persistente
  - ⚠️ Alguns regex precisam ajuste (false positives em data/Fases) — não bloqueante

**Impacto:** Zero regressão. `/fechar` fica 2-3s mais lento (aceitável). Dia 28/mês às 17h, auditoria roda automaticamente na cloud — Michel recebe alerta no próximo `/iniciar` se houver problema.

---

## ⚠️ Regra obrigatória — nunca supor sem verificar

Nunca afirmar que o sistema faz ou não faz algo sem consultar os arquivos/código primeiro.
Exemplo real (17/06): afirmei que havia triagem manual pela tela — após verificar, confirmou-se que não existe nada manual no sistema. Informação errada entregue antes de checar.
**Sempre usar Read, Grep, Glob ou script de verificação antes de qualquer afirmação sobre o sistema.**

---

## 🔁 Ao encerrar

Rode **`/fechar`** — ele atualiza este arquivo (estado + próximo passo) e mais
`REGISTRO_CORRECOES.md`, `PENDENCIAS.md` e `PLANO_IMPLEMENTACAO_MOTOR.md` quando tocados.
