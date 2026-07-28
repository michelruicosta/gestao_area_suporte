# Registro de Correções — Oráculo 360 (Nova Arquitetura)

**Início:** 28/07/2026 — nova arquitetura (Gmail API + IA Classificadora)

> Histórico do sistema antigo (pipeline de 16 scripts, até 22/07/2026) →
> `_archive/documentacao_sistema_antigo/REGISTRO_CORRECOES_historico_sistema_antigo.md`

**Como usar:** toda correção — de bug, regra ou comportamento — entra aqui no momento em que é feita,
com entrada datada (HH:MM). Formato obrigatório: "Em miúdos" + Problema + Correção + Validação.

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

