# Especificação da tela operacional

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

**Última revisão:** 2026-05-07  
**Fonte única da verdade** para a página `/operacional`.  
Consultar antes de alterar `email_operacional.html`, `layout.html` ou `painel_oraculo.py`.

---

## 1. Objetivo

- Exibir e-mails/casos regulatórios agrupados por thread
- Filtrar por data (DATA REF), status e busca
- Abrir modal para ver detalhes e tomar ações (Aguardando, Arquivar, etc.)

---

## 2. Controles

| Controle | Função |
|----------|--------|
| Busca (q) | Filtrar por assunto, cliente, CADOC, responsável |
| Apenas +24h | Filtrar só threads com mais de 24h de espera |
| Ver Concluídos | Alternar entre abertos e concluídos |
| Atualizar | Recarregar dados sem filtro de data |
| DATA REF (layout) | Filtrar dados pela data selecionada |

---

## 3. Cards KPI (4 estados)

| Card | Descrição |
|------|-----------|
| **Pendentes** | Casos em aberto (não aguardando). Sub-filtros: Finaud, Cliente, Críticos |
| **Aguardando** | Aguardando resposta ou entrega (Finaud ou Cliente) |
| **Concluídos** | Resolvidos. Sub-badge "👁 X em mon." quando há threads em monitoramento |
| **Não resolvidos** | Pendentes há 7+ dias sem nova mensagem |

---

## 4. Regras de dados

- **API:** `/api/dados?data=YYYY-MM-DD` (formato ISO obrigatório)
- **Sem data:** retorna hoje + acumulado
- **Com data:** retorna dados filtrados para essa data
- **Pendentes e DATA REF:** ao selecionar uma data (ex.: 24/02), só exibir threads cuja **última mensagem** é na data ou anterior (≤ 24/02)

---

## 5. Seções da lista

1. **💬 Cliente respondeu** — acima de HOJE, quando há threads ressuscitadas
2. **HOJE** — casos com atividade na data selecionada
3. **DIAS ANTERIORES** — casos de datas anteriores
4. **Não resolvidos (7+ dias)** — pendentes antigos

---

## 6. Modal

- Abre ao clicar no card
- Rota: `/api/threads/<path:thread_id>` (aceita threadId com `/`)
- Ações: Corrigir IA, Aguardando, Arquivar, Marcar Resolvido

---

## 7. Status de implementação (baseline)

_Preencha conforme o que está funcionando hoje:_

| Item | Implementado | Funciona |
|------|--------------|----------|
| API retorna dados | ? | ? |
| DATA REF recarrega | ? | ? |
| 4 cards KPI | ? | ? |
| Sub-filtros Pendentes | ? | ? |
| Filtro Pendentes por data | Sim | ? |
| Seção Cliente respondeu | ? | ? |
| Sub-badge em mon. | ? | ? |
| Modal com threadId com / | ? | ? |

---

## 8. Arquivos

- `templates/email_operacional.html`
- `templates/layout.html`
- `painel_oraculo.py`
