# Tarefas Agendadas e Recursos Externos — Gestão Área Suporte

**Início:** 18/08/2026
**Propósito:** rastrear todos os recursos externos ao código (tarefas agendadas, regras de roteamento, integrações, webhooks) para que qualquer sessão futura saiba o que existe, como funciona e como recriar do zero.

---

## Google Workspace — Regras de Roteamento de E-mail

### Regra: Cópia de segurança para IA - Interações Externas

| Campo | Valor |
|---|---|
| **ID / Nome** | "Cópia de segurança para IA - Interações Externas" |
| **Onde fica** | admin.google.com → Apps → Google Workspace → Gmail → Roteamento |
| **Criada por** | Michel (data de criação original desconhecida) |
| **Última modificação** | 18/08/2026 — adicionado `suporte@finaud.com.br` ao filtro de remetentes |

**O que faz:**
Copia automaticamente para `coleta.oraculo@finaud.com.br` todos os e-mails enviados pelos colaboradores da Finaud — tanto pelos endereços pessoais (`sarah.sa@finaud.com.br`, etc.) quanto pelo endereço do grupo (`suporte@finaud.com.br`). Garante que o banco do Gestão Área Suporte capture os dois lados da conversa: os e-mails dos clientes (que chegam via associação de grupo) e as respostas da Finaud (que chegam via esta regra).

**Configuração atual:**

- **Mensagens afetadas:** Enviadas + Interno-enviando (e possivelmente Recebidas/Interno-recebendo)
- **Tipos de conta:** Contas de usuário ativas + Contas de grupos
- **Ação:** Entregar também a `coleta.oraculo@finaud.com.br` (CCO/BCC)
- **Filtro de remetentes (RegExp):**
```
andrea.inacio@finaud.com.br|flavio.camargo@finaud.com.br|lucas.vellani@finaud.com.br|marcio@finaud.com.br|monica.macedo@finaud.com.br|pedro.silva@finaud.com.br|rodrigo.tiberio@finaud.com.br|miguel.santos@finaud.com.br|sarah.sa@finaud.com.br|suporte@finaud.com.br
```
- **Filtro de destinatários (RegExp):** mesmo padrão acima

**Por que foi criada:**
Sem esta regra, o coletor (`coletor_gmail.py`) só via os e-mails que chegavam à caixa de coleta via associação de grupo — ou seja, apenas os e-mails *dos clientes*. As respostas *da Finaud* enviadas via `suporte@finaud.com.br` não chegavam à caixa de coleta e ficavam invisíveis para o banco.

**Como recriar do zero:**
1. Acesse admin.google.com com conta de administrador
2. Apps → Google Workspace → Gmail → Roteamento
3. Adicionar regra → preencher com os valores acima
4. Salvar

**Erros conhecidos:**
- E-mails enviados *antes* de 18/08/2026 via `suporte@finaud.com.br` não foram capturados — histórico incompleto para este período; aceito como limitação.

**Última manutenção:** 18/08/2026 — adicionado `suporte@finaud.com.br` ao RegExp de remetentes (por Michel, guiado pela sessão do Gestão Área Suporte).

---

## Google Cloud — Service Account (autenticação do coletor)

| Campo | Valor |
|---|---|
| **Arquivo de credenciais** | `oraculo-ia-coleta.json` (na raiz do projeto, fora do git) |
| **Conta impersonada** | `coleta.oraculo@finaud.com.br` |
| **Escopo** | `gmail.readonly` |
| **Usado por** | `scripts/coletor_gmail.py` |

**O que faz:** permite que o `coletor_gmail.py` acesse a caixa `coleta.oraculo@finaud.com.br` via Gmail API sem precisar de senha — usa autenticação de serviço (service account com domain-wide delegation).

**Como recriar do zero:**
1. Google Cloud Console → IAM → Service Accounts → criar nova conta de serviço
2. Baixar JSON de credenciais → salvar como `oraculo-ia-coleta.json` na raiz do projeto
3. Google Admin Console → Segurança → Acesso e controle de dados → Controles de API → Delegação em todo o domínio
4. Adicionar o client_id da service account com o escopo `https://www.googleapis.com/auth/gmail.readonly`

**Erros conhecidos:** nenhum registrado.

**Última manutenção:** data de criação desconhecida (anterior a 28/07/2026).
