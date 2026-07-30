# PENDÊNCIAS — Oráculo 360 Finaud

**Atualizado:** 2026-07-30
**Regra:** este arquivo lista **só o que ainda falta** (aberto / aguardando decisão / backlog).
Quando uma pendência for **resolvida**, ela **sai daqui** e vira entrada datada no
`REGISTRO_CORRECOES.md` — nesta ordem: primeiro grava no REGISTRO, depois remove daqui (nunca o
contrário, para não perder histórico). Ver regra completa no `CLAUDE.md`.

---

## 🔴 URGENTE — Campo 6 (Corpo): análise de limpeza por categoria (iniciado 29/07/2026)

Sem o Campo 6 documentado, a `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10 está incompleta
e o classificador IA não pode ser construído. **Campo 6 é o mais crítico** — é o texto que a IA lê
para classificar cada e-mail.

**Decisão de abordagem (29/07/2026):** a IA nunca recebe o e-mail bruto. Antes de classificar, o
sistema aplica regras de limpeza. O Campo 6 define exatamente essas regras. Para definir as regras
com segurança, analisamos **todos** os e-mails de cada categoria nos dados de produção (JSON01 × JSON03).

### Regras de limpeza estabelecidas na análise do DDR_2011 (baseline para todas as categorias)

| # | Regra | O que faz | Descoberta em |
|---|---|---|---|
| L1 | Assinatura | Corta em `Att,` / `Atenciosamente` / `À disposição` / `Cordialmente` / `Desde já agradeço` / `Antecipadamente grata` | DDR_2011 |
| L2 | Histórico com traços | Corta em `-----` (Gmail forward) e `___` (Outlook separator) | DDR_2011 |
| L3 | Histórico com seta `>` | Remove linhas que começam com `>` (reply citado) | DDR_2011 |
| L4 | Rodapé de lista | Corta em `To unsubscribe from this group` (rodapé Google Groups) | DDR_2011 |
| L5 | Imagem decorativa | Remove `[image: facebook/instagram/linkedin/youtube/whatsapp/logo/ícone/esign]` | DDR_2011 |
| L6 | Imagem com nome genérico antes da assinatura | Tenta OCR → se lê texto útil: inclui; se não lê: arquiva para revisão humana | DDR_2011 |
| L7 | Imagem com nome genérico depois da assinatura | Remove (provavelmente logo de rodapé) | DDR_2011 |
| L8 | Corpo vazio após limpeza | Sinaliza como `ENCAMINHAMENTO_INTERNO` (R5) — não classifica sem texto | DDR_2011 |

> **Regra de ouro — imagens:** nenhuma imagem é descartada silenciosamente. Se não for decorativa
> e o OCR falhar, o e-mail vai para fila de revisão humana. A IA não classifica até resolver.

### Status da análise por categoria

| # | Categoria | E-mails no JSON01 | Análise L1–L8 | Imagens inspecionadas | Protocolo registrado |
|---|---|---|---|---|---|
| 1 | **DDR_2011** | 2.350 | ✅ concluída | ✅ concluída | ✅ (ver REGISTRO_CORRECOES 30/07) |
| 2 | SCD_4111 | — | ☐ | ☐ | ☐ |
| 3 | DRM_2060 | — | ☐ | ☐ | ☐ |
| 4 | DLO_2061 | — | ☐ | ☐ | ☐ |
| 5 | DLI_2062 | — | ☐ | ☐ | ☐ |
| 6 | DRL_2160 | — | ☐ | ☐ | ☐ |
| 7 | S5 | — | ☐ | ☐ | ☐ |
| 8 | RETORNO_BACEN | — | ☐ | ☐ | ☐ |
| 9 | SUPORTE | — | ☐ | ☐ | ☐ |
| 10 | FORCAPITAL | — | ☐ | ☐ | ☐ |
| 11 | DRSAC_2030 | — | ☐ | ☐ | ☐ |
| 12 | PVCA_6209 | — | ☐ | ☐ | ☐ |

### Metodologia por categoria (repetir para cada ☐ acima)

Para cada categoria, executar em ordem:

1. **Contar e-mails** — cruzar JSON03 (categoria) × JSON01 (corpo) via `x_gm_thrid`
2. **Simular as 8 regras de limpeza** em todos os e-mails:
   - Quantos cada regra afeta (%)
   - Padrões novos não cobertos pelas regras → adicionar à lista se encontrar
   - Quantos ficam vazios após limpeza
3. **Inspecionar imagens**:
   - Quais nomes aparecem (Counter por nome)
   - Quantas estão antes vs. depois da assinatura
   - Exemplos de contexto para imagens com nome genérico (`image.png`)
   - Definir: o que é decorativo (descartar) vs. conteúdo (OCR)
4. **Registrar protocolo da categoria** no REGISTRO_CORRECOES com:
   - Regras L1–L8: funcionam? Alguma exceção?
   - Imagens: lista de nomes decorativos + protocolo OCR para esta categoria
   - Casos especiais encontrados

**Scripts prontos no scratchpad:**
- `simular_limpeza_ddr.py` — adaptar mudando o filtro de cadoc
- `inspecionar_imagens_ddr.py` — adaptar mudando o filtro de cadoc

**Após todas as 12 categorias concluídas:**
- Consolidar regras universais vs. exceções por categoria
- Escrever Campo 6 em `documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` §10
- Publicar artifact atualizado

**Outros campos pendentes (aguardam Campo 6 estar concluído):**
- **Campo 7 — Anexos:** tipos de arquivo por categoria, o que a IA extrai
- **Campo 8 — Thread ID e Data:** rastreamento de thread, data de referência regulatória

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
