# Spec — Display do Modal de E-mails

**Criado:** 2026-09-03  
**Status:** em construção — tipo por tipo, com Michel  
**Regra:** nenhuma alteração no modal sem esta spec concluída (PENDENCIAS.md, 03/09/2026)

---

## Como ler este documento

Para cada tipo de mensagem (A–G), a spec define:
- **O que é** — em linguagem simples
- **Sub-cenários** — variações reais encontradas no banco
- **O que o modal deve mostrar** — decisão aprovada por Michel
- **O que não fazer** — restrições explícitas

---

## Tipo A — Mensagem simples (sem histórico citado)

**O que é:** e-mail com texto puro, sem resposta citada abaixo e sem bloco encaminhado.  
**Volume:** 1.244 threads (maior grupo).

### Sub-cenário A1 — Texto limpo (834 threads — 67%)

Mensagem pura, sem imagens embutidas.

**Decisão (03/09/2026):** exibir o corpo completo, incluindo assinatura.

**Motivo:** não há forma confiável de separar assinatura de conteúdo — qualquer
regra automática erra nos casos onde o remetente mistura texto real com o
fechamento ("Seguem os arquivos. Qualquer dúvida, ligue. Att, Jair"). O telefone
do contato, presente na assinatura, não está salvo em nenhum outro lugar no
sistema.
