# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-07-28
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui (nunca o
contrário, para não perder histórico). Ver regra completa no `CLAUDE.md`.

---

## 🟠 EM CURSO — Simulação de threads reais para projetar Campo 6 da spec (registrado 28/07/2026)

**O que estamos fazendo e por que registramos aqui:**
Estamos no meio da construção da `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md`.
A seção §12 mapeia cada campo de e-mail que a nova IA vai ler. Os campos 1–5 (De, Para, CC, Reply-To, Assunto) já estão documentados. O Campo 6 — Corpo do e-mail — é o mais crítico e não foi escrito ainda.

**Por que não escrevemos direto:**
Antes de definir como o Campo 6 funciona, Michel quer ver as mensagens de verdade — como elas chegam, como se atualizam ao longo de uma thread, o que o texto contém, o que a IA vai conseguir ler. Só com isso na mão saberemos como projetar o campo corretamente.

**O que já descobrimos (análise da sessão 28/07):**
- Produção: 8.825 e-mails (JSON01), 4.786 threads (JSON03) em `oraculo_360_finaud`
- Qualidade do campo `corpo_texto`: 81% texto puro ✅ | 19% HTML (sistemas automáticos) | 23% tem `[cid:]` de imagens decorativas | 15% tem histórico de encaminhamento colado
- CSS VML (bug que apareceu em 17/07): **0%** na produção normal — só ocorre quando a flag proibida é usada erroneamente
- Tipos de thread: **99,7%** são de evento único (uma conversa, um CADOC) | **0,3%** são de canal (mesma thread reaberta por meses) — caso raro, não o padrão

**O que falta simular (faça um por vez, mostre ao Michel):**
1. ☑ Thread DDR_2011 típica — simulada em 28/07/2026 (Accredito SCD, 5 mensagens, ciclo completo com .zip)
2. ☐ Thread RETORNO_BACEN (complexa: XML no corpo, prazo urgente D+3)
3. ☐ Thread DLO_2061 ou DLI_2062 (cliente envia print da tela)
4. ☐ Thread SUPORTE (dúvida sem CADOC definido)

**Pendências da spec após a simulação:**
- **P2 — Campo 6 (Corpo):** escrever em §12 após a simulação. Decisões: como pré-processar, o que a IA recebe de cada tipo, como tratar histórico acumulado e mensagens curtas demais.
- **P3 — Campo 7 (Anexos):** documentar em §12 como campo próprio
- **P4 — Campo 8 (Thread ID e Data):** documentar em §12
- **P5 — "Conceitos Derivados":** criar seção ausente (prazo = data de referência + regra do CADOC) — referenciada no Campo 5 mas não existe
- **P6 — Revisão leve de §2 e §9:** alinhar com o modelo de duas camadas (já documentado em §16)

**Arquivo central:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md`
**Scripts de análise (temporários, no scratchpad):** `ver_thread_completa.py`, `threads_canal_vs_evento.py`, `analisar_qualidade_texto.py`

---

## 🔴 URGENTE — Campos 6, 7 e 8 da especificação (aguardam simulações) (registrado 28/07/2026)

**Bloqueado por:** simulações de threads reais (itens ☐ 2–4 do bloco "EM CURSO" acima)

Sem estes campos, a `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10 está incompleta e o classificador IA não pode ser construído — estes campos alimentam diretamente o motor de classificação.

| Campo | O que é | O que falta definir |
|---|---|---|
| **Campo 6 — Corpo** | O texto da mensagem que a IA vai ler | Como pré-processar; o que a IA recebe de cada tipo de thread; como tratar histórico acumulado e mensagens curtas |
| **Campo 7 — Anexos** | Lista de arquivos em anexo | Tipos de arquivo relevantes por categoria; padrões de nome; o que a IA extrai de cada um |
| **Campo 8 — Thread e Data** | ID da thread e data de cada mensagem | Como a IA usa thread_id para rastrear; como extrair a data de referência do CADOC a partir da data da mensagem |

**Próximo passo:** concluir as 3 simulações ☐ pendentes (RETORNO_BACEN, DLO/DLI, SUPORTE) e então escrever os três campos na spec.

**Arquivo:** `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10

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
