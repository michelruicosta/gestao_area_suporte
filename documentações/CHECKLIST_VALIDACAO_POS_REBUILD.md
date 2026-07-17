# Checklist de Validação Pós-Rebuild — Tela Operacional

**Para usar:** após apagar a base de teste e recarregar os dados, execute este checklist item a item.
**Quem executa:** a IA (Claude) comparando os dados carregados com o comportamento esperado.
**Pré-requisito:** pipeline completo rodado (Scripts 01→16), tela em `localhost:5000/operacional`.

---

## Como executar

1. Leia cada item abaixo
2. Verifique no JSON ou na tela conforme indicado
3. Marque ✅ ou registre o problema encontrado
4. Ao final: se todos ✅ → base validada. Se houver ❌ → registrar em PENDENCIAS.md e avisar Michel

---

## Bloco A — Campos do Card (lista de threads)

### A1 — Assunto / Título
- [ ] Nenhuma thread com `titulo` vazio
- [ ] Prefixos `Re:`, `RES:`, `ENC:` removidos do assunto
- **Como verificar:** `grep -c '"titulo": ""' data/json/pipeline/03_integrador_dados_site.json` → deve retornar 0

### A2 — SEM_TRIAGEM: threads invisíveis antes do motor rodar
- [ ] Nenhuma thread com status `PENDENTE` ou `INFORMATIVO` aparece na tela
- [ ] Threads com `SEM_TRIAGEM` não aparecem na listagem
- [ ] 5 CADOCs internos (FOGBUGZ, LEIAUTES_BACEN, RISK_DRIVER_*) não aparecem na tela
- **Como verificar:** abrir tela `/operacional` — checar que só AGUARDANDO e CONCLUÍDO aparecem

### A3 — Empresa / Cliente (Campo 3)
- [ ] Contatos com nome = parte local do e-mail (`financeiro`, `compliance`, `risco`) mostram o **e-mail completo** na tela, não o nome suspeito
- [ ] Quando o mesmo contato aparece com nome completo em outro e-mail, o nome completo prevalece
- **Como verificar:** buscar thread de cliente que tem e-mail genérico (ex.: compliance@empresa.com.br) — conferir o nome exibido no card

### A4 — Categorias no snippet (Campo 7)
- [ ] Snippet abaixo do assunto mostra o CADOC correto da thread (não "SUPORTE" para thread DLO/DDR/RETORNO_BACEN)
- [ ] Threads com CADOC `SUPORTE` real podem continuar mostrando "SUPORTE"
- **Como verificar:** abrir tela e olhar o snippet de pelo menos 3 threads regulatórias (DDR, DLO, RETORNO_BACEN) — confirmar que o CADOC bate com o da thread

---

## Bloco B — Campos do Modal (ao clicar no card)

### B1 — Corpo da mensagem: assinatura removida (Campo 10)
- [ ] Mensagens com "Att. Nome Sobrenome" ao final não mostram a assinatura
- [ ] Mensagens com "Obrigado/Obrigada Nome Sobrenome" ao final não mostram a assinatura
- [ ] Mensagens com "Cordialmente Nome Sobrenome" ao final não mostram a assinatura
- [ ] Texto antes da assinatura permanece intacto (não foi cortado no meio)
- **Como verificar:** abrir pelo menos 5 threads diferentes, expandir mensagens — checar se termina antes da assinatura

### B2 — Corpo da mensagem: histórico citado recolhido (T6)
- [ ] E-mails com histórico colado no corpo (`De: ...` / `*De:*`) mostram o texto novo normalmente e escondem o histórico num bloco "▶ Histórico citado"
- [ ] Badge âmbar "Com histórico" aparece quando há histórico
- **Como verificar:** buscar thread com resposta encadeada — o corpo novo deve aparecer limpo

### B3 — Cabeçalho De/Para (T7)
- [ ] "De:" e "Para:" aparecem em duas linhas separadas (não na mesma linha)
- [ ] Rodapés de "confidencial", "Enviado do iPhone", `---`, `___` não aparecem no corpo
- **Como verificar:** abrir qualquer thread e checar o bloco De/Para no modal

### B4 — Anexos: chips mesmo quando há texto (Campo 11)
- [ ] Mensagens com corpo + anexo mostram chips 📎 abaixo do texto (ex: `📎 rd_prefixada.xlsx`)
- [ ] Imagens inline (content_id) **não** aparecem nos chips
- [ ] Mensagens sem texto (só anexo) continuam mostrando o aviso vermelho "⚠ Sem texto — ver anexo"
- **Como verificar:** buscar thread onde cliente enviou .xlsx ou .pdf junto com texto — os chips devem aparecer abaixo do corpo

### B5 — Prazos: formato MM/AA reconhecido (Campo 9 — Script 05)
- [ ] E-mails com prazo no formato "04/26" (mês/ano 2 dígitos) geram prazo correto (abril/2026)
- [ ] Nenhum prazo em branco que deveria estar preenchido
- **Como verificar:** verificar thread onde o e-mail continha data no formato MM/AA — confirmar que o prazo está preenchido

---

## Bloco C — Regras do pipeline

### C1 — Data de e-mail: INTERNALDATE como fallback (Script 02)
- [ ] Nenhuma thread com `timestamp_epoch = 0` em todas as mensagens
- [ ] Threads ordenadas por data corretamente (mais recente no topo)
- **Como verificar:** `python -c "import json; d=json.load(open('data/json/pipeline/02_classificação_dados_brutos_gmail_editado.json')); zero=[e for e in d if e.get('timestamp_epoch',1)==0]; print(len(zero),'com epoch zero')"` → deve ser 0 ou muito próximo de 0

### C2 — Triagem: motor aplicado em todos os supervisores
- [ ] Threads AGUARDANDO e CONCLUÍDO têm campo `regra` preenchido (R1, R2, etc.)
- [ ] Nenhuma thread com `regra = ""` em AG ou CO
- **Como verificar:** conferir no painel que o badge da regra aparece nos cards

### C3 — Responsável pela ação (Campo 10 — regra De/Para)
- [ ] Thread onde último e-mail foi F→C (Finaud para Cliente): responsável = Cliente
- [ ] Thread onde último e-mail foi C→F (Cliente para Finaud): responsável = Finaud
- **Como verificar:** abrir 3 threads, olhar quem enviou o último e-mail e conferir se o responsável bate com a regra

---

## Bloco D — Verificações rápidas de saúde

### D1 — Contagem geral
- [ ] Número de threads AG + CO bate com o total do integrador (JSON 03)
- [ ] Nenhuma thread duplicada (mesmo ID duas vezes na lista)

### D2 — Sem regressão nos testes
- [ ] `pytest tests/ -q -m "not agent and not pdf and not integration"` → zero falhas
- **Este é o primeiro passo — se pytest falhar, parar aqui e investigar antes de abrir a tela**

### D3 — Campos internos críticos
- [ ] `empresa` preenchida em ao menos 80% das threads (não vazio)
- [ ] `cadoc` preenchido em todas as threads (não "SUPORTE" em thread regulatória)
- [ ] `lista_prazos` não vazia em threads DDR, DLO, DLI, DRM, DRL com data detectada

---

## Como registrar problemas encontrados

Para cada ❌:

```
Campo: [nome do campo]
Problema: [o que está errado em linguagem simples]
Thread de exemplo: [ID ou assunto]
Impacto: [o que o usuário vê de errado]
→ Registrar em PENDENCIAS.md e avisar Michel antes de tentar corrigir
```

---

## Referências

- Correções desta sessão: `documentações/REGISTRO_CORRECOES.md` — entradas de 2026-07-16
- Status dos campos: `documentações/VALIDACAO_CAMPOS_TELA.md`
- Mapa técnico: `documentações/GUIA_CAMPOS_OPERACIONAL.md`
- Linhagem dos dados: `documentações/LINHAGEM_DADOS_OPERACIONAL.md`
