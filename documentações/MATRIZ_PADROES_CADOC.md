# Matriz de Padrões — CADOC × Lado × Tipo de Ação

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

**Última revisão:** 2026-05-07

Documentação da matriz de padrões usada para sugerir motivo e tipo ao abrir o modal de aguardo ou clicar em "Sugerir". O sistema aplica a matriz conforme o **CADOC**, o **lado** da última mensagem (Finaud/Cliente) e o **tipo de ação** detectado por heurísticas.

---

## Estrutura

| Dimensão | Valores | Descrição |
|----------|---------|-----------|
| **CADOC** | DDR_2011, 4111, DLO_2061, DLI_2062, DRL_2160, DRM_2060 | Tipo de relatório regulatório |
| **Lado** | FINAUD, CLIENTE | Quem enviou a última mensagem |
| **Tipo de ação** | finaud_solicita, finaud_pergunta, finaud_envia, cliente_solicita, cliente_envia | Ação detectada no conteúdo |

### Prioridade: Lado sobre heurísticas

O **lado** (ultimo_lado / responsabilidade do card) é o sinal principal:
- **FINAUD enviou última** → Padrão A (default), exceto se heurísticas indicam pedido de dados ou dúvida → Padrão C
- **CLIENTE enviou última** → Padrão B (default), exceto se heurísticas indicam confirmação ou questionamento → ajustes

Heurísticas no corpo do e-mail são usadas apenas para **exceções** (ex.: Finaud pediu dados, Finaud perguntou, cliente confirmou).

---

## Cenários e Padrões

### A — Cliente enviou dados (cliente_envia)
- **Última mensagem**: CLIENTE
- **Conteúdo**: "Segue anexo", "Segue DDR", "Segue CADOC", "em anexo", "conforme solicitado"
- **Padrão**: B (Ação interna)
- **Tipo**: ACAO_INTERNA
- **Motivo**: "Dados recebidos. {responsavel} deve gerar e enviar [CADOC] ao BACEN. {prazos_status} Recebido em: {data_recebido}."

### B — Finaud enviou relatório ao cliente (finaud_envia)
- **Última mensagem**: FINAUD
- **Conteúdo**: "Seguem anexos", "para envio ao BACEN", "enviado ao cliente"
- **Padrão**: A (Finaud já enviou)
- **Tipo**: RESPOSTA_CLIENTE
- **Motivo**: "{responsavel} já enviou. [CADOC] enviado ao BACEN. Resposta do cliente não obrigatória."

### C — Finaud solicita dados ao cliente (finaud_solicita)
- **Última mensagem**: FINAUD
- **Conteúdo**: "Por gentileza enviar", "enviar para cálculo", "solicitamos extratos"
- **Padrão**: C (Entrega cliente)
- **Tipo**: ENTREGA_CLIENTE
- **Motivo**: "Aguardando [dados] de {empresa} para [CADOC] de {periodo}. Cliente deve enviar até {prazo_ec}. {responsavel} envia ao BACEN até {prazo}."

### D — Finaud pergunta ao cliente (finaud_pergunta)
- **Última mensagem**: FINAUD
- **Conteúdo**: "Poderia informar qual conta", "por gentileza informar", "não possuo familiaridade"
- **Padrão**: C (Entrega cliente — dúvida)
- **Tipo**: ENTREGA_CLIENTE
- **Motivo**: "Aguardando {empresa} responder sobre dúvida da {responsavel}. [CADOC] ainda não enviado."

### E — Cliente solicita/aguarda Finaud (cliente_solicita)
- **Última mensagem**: CLIENTE
- **Conteúdo**: Pergunta, pedido de simulação, aguardando retorno
- **Padrão**: A (Monitorar)
- **Tipo**: RESPOSTA_CLIENTE
- **Motivo**: "Aguardando {responsavel} responder para {empresa}."

### F — Cliente questiona divergências (heurística especial)
- **Última mensagem**: CLIENTE
- **Conteúdo**: "Divergências encontradas", "aguardando seu retorno", "verifiquem e nos retornem"
- **Padrão**: C (Monitorar — pendência é analista responder)
- **Tipo**: RESPOSTA_CLIENTE
- **Motivo**: "Aguardando {responsavel} responder ao cliente sobre divergências em [período]."

### G — Resposta enviada em outro email (TVM, Dep a Vista)
- **Assunto/corpo**: "TVM", "Depósito a Vista", "Relatórios de TVM e Dep a Vista"
- **Padrão**: Resposta em outro email (standby)
- **Tipo**: RESPOSTA_EM_OUTRO_EMAIL
- **Motivo**: "Resposta enviada em outro email (ex.: TVM/Dep a Vista em email consolidado). Thread em standby até confirmar recebimento."
- **Nota**: A resposta da Finaud costuma vir em email separado. Não auto-remove; usuário confirma manualmente após verificar no Gmail. Use `scripts/buscar_solicitacao_resposta_gmail.py` para verificar.

### H — Cliente confirmou resolução (heurística especial)
- **Última mensagem**: CLIENTE
- **Conteúdo**: "Deu certo", "funcionou", "obrigado", "resolvido"
- **Padrão**: A (Arquivar)
- **Tipo**: RESPOSTA_CLIENTE
- **Motivo**: "Cliente confirmou que [X] está funcionando — arquivar."

---

## Placeholders nos templates

| Placeholder | Descrição | Exemplo |
|-------------|-----------|---------|
| `{empresa}` | Nome do cliente/empresa | Global Exchange, Sefer Investimento |
| `{periodo}` | Período de referência | 19/02, 20/02, 23/02 |
| `{responsavel}` | Nome do analista Finaud | Monica Macedo, Andrea Inacio |
| `{prazo}` | Prazo regulatório (Finaud → BACEN) | 25/02/2026 |
| `{prazo_ec}` | Prazo entrega cliente | 24/02/2026 |
| `{prazos_status}` | Lista de prazos com status | 19/02→24/02 (5d antes). 20/02→25/02 (4d antes). |
| `{data_recebido}` | Data em que o cliente enviou | 24/02/2026 |

---

## Origem do responsável

O campo `responsavel` (ex.: Monica Macedo) é obtido pelo classificador (04) a partir de:

- **Quando CLIENTE envia**: primeiro destinatário Finaud em To/CC (extrai nome de "Nome <email@finaud.com.br>")
- **Quando FINAUD envia**: primeiro destinatário cliente em To/CC
- **Fallback**: mapeamento `colaboradores_finaud` por usuário de e-mail

O integrador (08) propaga `responsavel` da última mensagem para a thread.

---

## Fluxo ao abrir o card

1. Usuário clica em "Aguardar" no card
2. Modal abre e chama `/api/sugerir_aguardo` com contexto completo:
   - assunto, cadoc, empresa, quem_gera, responsabilidade, **responsavel**
   - historico, ultimo_lado, lista_prazos, data_email, data_referencia
3. Backend aplica heurísticas e matriz `padroes_por_cadoc.json`
4. Retorna motivo, tipo, prazo_sugerido, foco_monitoramento
5. Frontend preenche os campos e exibe o painel de foco (Padrão A/B/C)

---

## Arquivos

- **Matriz**: `data/json/padroes_por_cadoc.json`
- **Lógica**: `painel_oraculo.py` — `_motivo_do_padrao`, heurísticas, `api_sugerir_aguardo`
- **Frontend**: `templates/email_operacional.html` — `_executarSugerirAguardo`, `_abrirPainelAguardo`
