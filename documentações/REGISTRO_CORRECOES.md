# Registro de Correções — Oráculo 360 (Nova Arquitetura)

**Início:** 28/07/2026 — nova arquitetura (Gmail API + IA Classificadora)

> Histórico do sistema antigo (pipeline de 16 scripts, até 22/07/2026) →
> `_archive/documentacao_sistema_antigo/REGISTRO_CORRECOES_historico_sistema_antigo.md`

**Como usar:** toda correção — de bug, regra ou comportamento — entra aqui no momento em que é feita,
com entrada datada (HH:MM). Formato obrigatório: "Em miúdos" + Problema + Correção + Validação.

---

## 2026-07-30 (continuação de sessão)

### 30/07 — Campo 6 DDR_2011: Passo 3 validado por Michel — todos os 6 elementos ✅

**🔎 Em miúdos:** Michel olhou exemplos reais do que o sistema detecta (e não detecta) em cada elemento de "sujeira" no corpo dos e-mails, e confirmou que está correto para todos os 6 tipos.

**O que foi feito:**
1. Criado script permanente `scripts/consultas/analisar_corpo_emails.py` — analisa qualquer categoria com os padrões do Passo 3; parametrizado por projeto e CADOC.
2. Padrão de assinatura iterado até 96,4% (3 rodadas de melhoria): adicionados fechamentos em inglês (`Kind Regards`, `Sincerely`, etc.) e `Grata/Grato`; corrigido problema do rodapé Google Groups que empurrava assinatura para fora da janela de busca.
3. Artifact de validação publicado: https://claude.ai/code/artifact/5054a35e-cbae-4beb-af23-df3c0972bcae
4. Michel validou os 6 elementos via artifact — exemplos detectados e não detectados conferidos.

**Resultados validados:**

| Elemento | Detectado em | Decisão |
|---|---|---|
| Assinatura | 96,4% (2.266/2.350) | ✅ 84 casos top-post aceitos — não prejudica a IA |
| Histórico citado (`>`) | 37,1% (873/2.350) | ✅ |
| Histórico encaminhado (`---`) | 22,1% (519/2.350) | ✅ |
| Rodapé automático | 95,5% (2.244/2.350) | ✅ |
| `[image:]` | 23,9% (562/2.350) | ✅ |
| `[cid:]` | 18,9% (445/2.350) | ✅ |

**Conceitos entendidos e confirmados por Michel (30/07/2026):**
- O Passo 3 resolve deduplicação automaticamente: cada e-mail fica só com o texto novo
- `>` = resposta (reply); `---` = encaminhamento (forward) — dois formatos, mesmo propósito: remover conteúdo antigo
- Para classificação: remover tudo é suficiente. Para IA Assistente de aprendizado: precisa do histórico completo → pendência registrada
- Threads com múltiplos CADOCs no painel do gestor → pendência registrada

**Validação:** ✅ Todos os 6 elementos aprovados por Michel (30/07/2026).
**Sem teste:** script de consulta — não modifica dados, não tem lógica de produção que precise de cobertura de teste.

---

## 2026-07-30

### 30/07 — Estrutura de documentação do projeto aprovada: 5 documentos com papéis distintos

**🔎 Em miúdos:** definimos como organizar todo o conhecimento do projeto — cada tipo de informação tem um lugar certo, e sabe-se onde olhar sem precisar lembrar.

**Problema:** ao crescer a documentação, ficou difícil decidir onde gravar cada tipo de informação — a spec estava virando um depósito de tudo.

**Decisão (30/07/2026):**

| Documento | Papel |
|---|---|
| `ESPECIFICACAO_NOVA_ARQUITETURA.md` | O mapa — decisões e regras ("o que temos" / "o que usaremos") |
| Artifact visual (claude.ai) | Visual — como ficará na tela e por quê |
| Lista de tarefas + fases (a criar) | Roteiro do desenvolvimento |
| `REGISTRO_CORRECOES.md` | Histórico datado do que foi feito |
| `PENDENCIAS.md` | O que falta — com checklist |

**Estrutura interna de cada campo da spec (3 partes):**
1. "O que temos" — dados reais da produção analisados
2. "O que utilizaremos" — decisão tomada
3. "Regras de negócio" — o que a IA vai seguir

**Validação:** ✅ Aprovado por Michel (30/07/2026). Gravado em memória (`projeto-estrutura-documentacao.md`) e aplicado a partir do Campo 6.

---

### 30/07 — Análise do Campo 6 (corpo do e-mail): DDR_2011 concluída — 8 regras de limpeza estabelecidas

**🔎 Em miúdos:** descobrimos como chegam os e-mails do DDR na produção e definimos as regras de "faxina" que o sistema precisa aplicar antes de entregar o texto para a IA ler. Sem essa faxina, a IA leria assinatura, histórico antigo e logos como se fossem parte da mensagem — e classificaria errado.

**Problema:** Campo 6 (corpo do e-mail) estava pendente. Não sabíamos como os e-mails chegam na produção nem o que a IA receberia se passássemos o texto direto.

**Causa raiz:** o e-mail bruto tem muita "sujeira" misturada ao texto real da mensagem: assinaturas com logos, histórico de respostas citadas (`>`), histórico encaminhado, rodapé automático do Google Groups, imagens decorativas convertidas em texto.

**Análise executada:** todos os 2.350 e-mails DDR_2011 (JSON01 × JSON03 via `x_gm_thrid`).

**Descobertas por regra:**

| Regra | O que afeta | % dos e-mails |
|---|---|---|
| L1 — Assinatura (`Att,`, `Atenciosamente`, etc.) | Detectada em 92,8% — corte funcionando | 92,8% |
| L2 — Histórico com traços (`---`, `___` Outlook) | Detectado em 6,3% | 6,3% |
| L3 — Histórico com seta `>` (reply citado) | **91% dos e-mails** — regra nova crítica | 91,0% |
| L4 — Rodapé Google Groups (`To unsubscribe`) | **95,5% dos e-mails** — regra nova crítica | 95,5% |
| L5 — Imagem decorativa (redes sociais, logos) | Maioria das 562 imagens encontradas | — |
| L6 — Imagem genérica (`image.png`) antes da assinatura | 249 ocorrências — OCR obrigatório | — |
| L7 — Imagem genérica depois da assinatura | Descartar (logo de rodapé) | — |
| L8 — Corpo vazio após limpeza | 4 e-mails (encaminhamento R5 puro) | 0,2% |

**Protocolo de imagens DDR_2011:**
- Nomes decorativos seguros para descartar: `instagram`, `linkedin`, `facebook`, `youtube`, `whatsapp`, `traders logo`, `esign`, `ícone`, `site mb`, `www.guru.com.vc` e variações de redes sociais/logos
- Nome genérico `image.png` antes da assinatura: pode ser arquivo de dados (ex.: RD_Moedas enviado como imagem) → **OCR obrigatório** → se OCR falhar → fila de revisão humana
- Nome genérico depois da assinatura: descartar (rodapé decorativo)
- Regra de ouro: nenhuma imagem descartada silenciosamente — OCR falhou = e-mail arquivado para revisão

**Artifact visual:** https://claude.ai/code/artifact/f86d271e-b354-49e2-8d2b-b110e68652c6 — 4 casos de imagem (decorativa / OCR / OCR falhou / corpo vazio).

**Validação:** ✅ Confirmado por Michel (30/07/2026). Regras L1–L8 registradas em `documentações/PENDENCIAS.md` como baseline para análise das demais 11 categorias.

---

## 2026-07-29

### 29/07 14:43 — Regras de classificação R1–R5 escritas para todas as 12 categorias

**🔎 Em miúdos:** escrevemos o "manual" que a IA vai usar para classificar cada e-mail — para cada tipo de e-mail (DDR, DLO, etc.), definimos exatamente quando a thread está "Aguardando" e quando está "Concluída", com exemplos reais.

**Problema:** a spec (`documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md §14`) tinha apenas a descrição de cada categoria (o que é, como reconhecer, o fluxo). Não tinha as regras de classificação — sem elas, a IA não sabe decidir o status de cada thread.

**Causa raiz:** as regras precisavam ser derivadas do histórico real de threads validadas (`oraculo_360_finaud/documentações/DOCUMENTACAO_TRIAGEM.md`) com cobertura confirmada de 100%.

**Correção:** para cada uma das 12 categorias, executamos:
1. Leitura da seção do histórico
2. Varredura de cobertura (tabela com todos os padrões e a regra que cobre cada um)
3. Aprovação do Michel
4. Gravação em `ESPECIFICACAO_NOVA_ARQUITETURA.md §14` e `spec_nova_arquitetura.html §14`

Regras transversais confirmadas durante o processo:
- §11.5 regra universal de cortesia (escrita no início da sessão — ver entrada abaixo)
- DRSAC/PVCA R2: cliente pode enviar arquivo para Finaud analisar/corrigir (exceto retorno BACEN)
- S5 R4: mesmo significado padrão (acuse curto), não "resposta substantiva" como no histórico antigo

**Validação:** ✅ Confirmado por Michel categoria por categoria. Artifact publicado como v2.13. Total: 3.075 threads históricas cobrindo 100% dos padrões documentados.

---

### 29/07 — Regra universal: frases de cortesia após entrega = Concluído

**🔎 Em miúdos:** quando a Finaud entrega o arquivo e assina com "Desde já agradeço" — ou quando o cliente responde "Obrigado" — isso não cria nenhuma pendência. A thread está encerrada.

**Problema:** o sistema antigo interpretava frases de assinatura cortês do colaborador Lucas ("Desde já agradeço e permaneço à disposição") como pedido ao cliente, marcando a thread como Aguardando/Cliente quando na verdade o arquivo já havia sido entregue. 3 threads do SCD_4111 tinham esse gap documentado.

**Correção:** regra universal adicionada ao §11.5 da especificação e aplicada a todas as 12 categorias: frase de cortesia/agradecimento/assinatura padrão após a entrega = Concluído, independente de quem enviou (Finaud ou cliente).

**Validação:** ✅ Confirmado por Michel (29/07/2026). Gravado em `ESPECIFICACAO_NOVA_ARQUITETURA.md §11.3` e `spec_nova_arquitetura.html §11.5`.

---

## 2026-07-28

### 28/07 — GitHub conectado e repositório publicado

**🔎 Em miúdos:** o projeto agora tem backup na nuvem (GitHub). Antes estava só no PC — se o PC quebrasse, perdia tudo.

**Problema:** repositório local sem remote configurado; arquivos novos (testes, templates, nova arquitetura) nunca haviam sido commitados; planilha com dados sensíveis de clientes em risco de ser exposta acidentalmente.

**Correção:**
- `documentações/indício-qualidade.xlsx` adicionado ao `.gitignore` (dados sensíveis de clientes)
- Branch local renomeada de `master` para `main` (padrão GitHub)
- Remote `origin` apontado para `github.com/michelruicosta/gestao_area_suporte`
- 57 commits do histórico enviados ao GitHub
- 98 arquivos novos commitados e enviados (sistema atual + nova arquitetura + testes + CI)

**Validação:** ✅ Push confirmado no GitHub — `github.com/michelruicosta/gestao_area_suporte`; `.xlsx` não aparece no repositório remoto.

