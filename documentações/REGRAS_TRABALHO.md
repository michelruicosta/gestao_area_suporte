# Regras de Trabalho — Gestão Área Suporte

> **O que é este arquivo:** o detalhamento das regras que não precisam ser lidas em toda
> sessão. O `CLAUDE.md` (na raiz do projeto) carrega em **toda mensagem de todo chat** e
> por isso guarda só o essencial; aqui ficam os procedimentos que se lê **quando o assunto
> aparece**.
>
> **Quando ler este arquivo:**
> - Antes de disparar qualquer rodada que gaste API paga → §1
> - Antes de mexer em tela / CSS → §2
> - Antes de criar ou alterar tarefa agendada, webhook ou integração → §3
> - Antes de rodar algo que grava ou altera arquivos de dados → §4

---

## §1 — Ciclo de uma rodada paga (validação, classificação, reteste)

Estas quatro travas nasceram do mesmo dia (06/08/2026), quando a Rodada 3 colapsou de 5 para
188 incertos e não foi possível saber qual mudança causou. Elas são **um procedimento de
quatro passos**, não quatro regras soltas — a ordem importa.

### Passo 1 — Nenhum caso pendente antes de começar

Toda rodada com custo de API só é disparada quando **todos** os casos apontados na análise
anterior estiverem:

1. **Corrigidos** — a causa foi tratada (spec, parser, filtro etc.)
2. **Registrados** — entrada datada no `REGISTRO_CORRECOES.md` ou item no `PENDENCIAS.md`
3. **Aprovados por Michel** — confirmação explícita de que pode avançar

> **Por que existe:** os 4 casos que regrediram na Rodada 2 vieram de uma rodada disparada
> sem revisão completa dos casos anteriores. *(Michel, 06/08/2026)*

### Passo 2 — Uma mudança por vez na spec

Ao adicionar regras ao §10 da spec (ou a qualquer seção que o classificador lê), **nunca
mais de uma regra por ciclo de teste**:

1. Adicionar **uma** regra
2. Rodar a amostra (Passo 3)
3. Aprovada → commitar e seguir para a próxima
4. Reprovada → remover e entender o motivo antes de tentar outra abordagem

> **Por que existe:** em 06/08/2026 foram adicionadas 4 regras de uma vez. Quando a R3
> colapsou, não se sabia qual das 4 causou — horas removendo regras sem certeza. Uma
> mudança por vez isola o problema imediatamente. *(Michel, 06/08/2026)*

### Passo 3 — Amostra de 20 antes da rodada completa

Antes de disparar a validação completa (768 threads), rodar **20 threads** para verificar
que a regra nova não causa regressão.

**Critério de aprovação da amostra:**
- Incertos na amostra ≤ 1 (proporcional ao histórico — a R2 teve 0,7%)
- Nenhuma thread que já tinha categoria certa voltando para INCERTO

Amostra reprovada → corrigir a spec **antes** de gastar os tokens da rodada completa.

> **Por que existe:** na Rodada 3 uma regra mal formulada no §10 SUPORTE causou 188 incertos
> (24,5%). Uma amostra de 20 teria detectado o problema por 20 chamadas em vez de 768.
> *(Michel, 06/08/2026)*

### Passo 4 — Todo parâmetro de API explícito

Ao chamar qualquer API externa (OpenAI, Anthropic, Gmail…), definir **explicitamente** todo
parâmetro que afeta o comportamento — nunca depender do padrão do SDK.

**No classificador OpenAI:**

| Parâmetro | Valor | Por quê |
|---|---|---|
| `temperature` | `0` | Sem isso, a mesma thread muda de categoria entre rodadas |
| `max_tokens` | sempre definido | Evita corte silencioso da resposta |
| `response_format` | sempre definido | Garante o formato que o parser espera |

> **Por que existe:** o classificador rodou semanas sem `temperature` definido. O padrão da
> OpenAI (1.0) tornava as respostas aleatórias — a mesma thread saía
> SALDOS_CONTABEIS_DIARIOS_4111 numa rodada e INCERTO na seguinte. As Rodadas 1 e 2 deram
> certo em parte por sorte. *(Michel, 06/08/2026)*

### Fecho do ciclo — commitar o baseline

Rodada aprovada = **novo baseline**. Commitar imediatamente
`documentações/ESPECIFICACAO_NOVA_ARQUITETURA.md` + `scripts/classificador_regras.py` e
criar a tag (`git tag rodada-N-baseline`).

> **Por que existe:** a R2 não foi commitada — quando a R3 regrediu, não havia estado limpo
> para restaurar. *(06/08/2026)*

---

## §2 — Tipografia das telas

Toda tela nova ou modificada usa **`rem`**, nunca `px` fixo, para fontes de conteúdo.

| Tipo de tela | Corpo da tabela | Cabeçalho `th` | Labels / auxiliares |
|---|---|---|---|
| **Relatório / resumo** (E-mails, Admin) | `0.875rem` | `0.75rem` | `0.72rem` |
| **Grade densa** (FOG — colunas estreitas, muitos dados) | `0.75rem` | `0.625rem` | `0.5625rem` |

**Conversão obrigatória:** `12px → 0.75rem` · `11px → 0.6875rem` · `10px → 0.625rem` ·
`9px → 0.5625rem`.

**Numa grade densa, não aumentar fontes sem alargar as colunas** — texto maior em coluna
estreita espreme o layout.

**Cores:** componentes usam sempre token de tema — `var(--surface)`, `var(--border)`. Cor de
um tema específico vai dentro de `[data-theme="claro"]`; nunca hex fixo em regra global.

> Padrão aprovado por Michel em 25/08/2026, após o erro de aumentar as fontes do FOG sem
> ajustar as colunas. Regra de cores confirmada em 26/08/2026.

---

## §3 — Recursos externos precisam estar documentados

Recurso EXTERNO = tarefa agendada, webhook, integração cloud, API. Faz parte do projeto e
precisa estar rastreado em `documentações/TAREFAS_AGENDADAS.md`.

**Ao criar ou modificar um:**

1. Implementar e testar
2. Documentar em `TAREFAS_AGENDADAS.md`: ID do recurso · data de criação · schedule/trigger ·
   próxima execução · prompt completo · como recriar do zero · erros conhecidos · última
   manutenção
3. Commitar junto com o código

**Por quê:** quem for alterar ou recriar o recurso depois sabe tudo sem gastar tokens
redescobrindo. Documentação é a aprendizagem da sessão anterior, guardada.

**Checklist do `/fechar`:** "Criei ou alterei algo externo hoje? ☐ Se sim, está no
TAREFAS_AGENDADAS.md? ☐"

---

## §4 — Backup antes de mexer em dados (procedimento)

A regra está no `CLAUDE.md`; aqui está o passo a passo.

**Estrutura obrigatória:**

```
data/backups/
└── AAAAMMDD_HHMM_motivo/          ← data + motivo curto
    ├── arquivo1.json               ← cópia do que será modificado
    ├── arquivo2.json
    └── CONTEXTO.md                 ← obrigatório
```

**Conteúdo obrigatório do `CONTEXTO.md`:**

```
Data: DD/MM/AAAA HH:MM
Motivo: [por que este backup foi feito]
O que vai mudar: [o que a rotina vai alterar]
Quem autorizou: Michel
Como restaurar: copiar os arquivos desta pasta para o local original
```

**PowerShell para criar a estrutura:**

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$pasta = "data/backups/${ts}_motivo_aqui"
New-Item -ItemType Directory -Path $pasta
Copy-Item "arquivo.json" "$pasta/arquivo.json"
# Criar CONTEXTO.md com as informações obrigatórias
```

**Nunca** deixar backup solto na pasta de produção (`arquivo.json.backup_$ts`).

---

## §5 — Deploy (resumo; ritual completo em `DEPLOY.md`)

Quando Michel disser "publicar", "publicar em produção" ou "atualizar a VPS", **Claude faz o
deploy inteiro via SSH** — nunca pedir para Michel colar comandos no terminal.

1. Commit + push na `main` — **só com OK explícito de Michel**
2. SSH pelo alias: `ssh -o RequestTTY=no finaud-vps`
3. Servidor: pasta `/srv/finaud/tec/gestao_area_suporte` · usuário `finaud-tec` · serviço
   `gestao-suporte`
4. `git checkout main && git pull origin main` como `finaud-tec` — se o pull bloquear, mostrar
   o diff e perguntar
5. App Flask — **não rodar npm build** · Gunicorn workers = **1**
6. `systemctl restart gestao-suporte` (e `gestao-suporte-agendador` se esse serviço já existir)
   → conferir `is-active` → abrir `https://gestao-suporte.finaudapps.com.br`
7. Depois de "Sair": deve redirecionar para `https://finaudapps.com.br` (não para o `/login`
   deste app)
