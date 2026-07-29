# Registro de Correções — Oráculo 360 (Nova Arquitetura)

**Início:** 28/07/2026 — nova arquitetura (Gmail API + IA Classificadora)

> Histórico do sistema antigo (pipeline de 16 scripts, até 22/07/2026) →
> `_archive/documentacao_sistema_antigo/REGISTRO_CORRECOES_historico_sistema_antigo.md`

**Como usar:** toda correção — de bug, regra ou comportamento — entra aqui no momento em que é feita,
com entrada datada (HH:MM). Formato obrigatório: "Em miúdos" + Problema + Correção + Validação.

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

