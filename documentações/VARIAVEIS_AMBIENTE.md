# Variáveis de Ambiente — Oráculo 360 Finaud

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

Catálogo completo de todas as variáveis de ambiente usadas no sistema.
Criado em 05/06/2026 — atualizar sempre que adicionar ou remover uma variável.

---

## Como usar

Variáveis permanentes ficam no arquivo `.env` na raiz do projeto.
Variáveis temporárias (para um único run) podem ser definidas no terminal:

```powershell
# Windows PowerShell
$env:ORACULO_VERBOSE = "1"
python executar_tudo.py
```

---

## 1. Período de coleta

Definem qual intervalo de datas o pipeline vai processar.

| Variável | Formato | Exemplo | Descrição |
|----------|---------|---------|-----------|
| `DATA_COLETA_INICIO` | DD-MMM-YYYY | `2-Jun-2026` | Início do período (inclusivo) |
| `DATA_LIMITE_EXCLUIR` | DD-MMM-YYYY | `3-Jun-2026` | Fim do período (exclusivo — esse dia não entra) |
| `ORACULO_DATA_COLETA_INICIO` | DD-MMM-YYYY | `2-Jun-2026` | Sobrescreve DATA_COLETA_INICIO sem editar o arquivo |
| `ORACULO_DATA_LIMITE_EXCLUIR` | DD-MMM-YYYY | `3-Jun-2026` | Sobrescreve DATA_LIMITE_EXCLUIR sem editar o arquivo |

**Regra:** [DATA_COLETA_INICIO, DATA_LIMITE_EXCLUIR) — o dia limite é excluído.
Ex: início=1-Jun e limite=3-Jun → processa os dias 1 e 2 de junho.

---

## 2. Modo de execução

Controlam o comportamento geral do pipeline.

| Variável | Valores | Padrão | Descrição |
|----------|---------|--------|-----------|
| `ORACULO_INCREMENTAL` | `0` ou `1` | `0` | `1` = reutiliza classificações anteriores, processa só e-mails novos. Muito mais rápido em cargas do dia a dia. |
| `ORACULO_VERBOSE` | `0` ou `1` | `0` | `1` = mostra detalhes de cada e-mail processado no console. Útil para debug, torna o log muito longo. |
| `ORACULO_PRESERVAR_CLASSIFICACAO_FORA_PERIODO` | `0` ou `1` | `1` | `1` = mantém a classificação de e-mails antigos (fora do período atual) em vez de reclassificá-los como FILTRADO_POR_DATA. |

---

## 3. Controle de fluxo do pipeline

Ligam ou desligam etapas específicas.

| Variável | Valores | Padrão | Descrição |
|----------|---------|--------|-----------|
| `ORACULO_CARGA_EM_CURSO` | `0` ou `1` | `0` | Definido automaticamente pelo `executar_tudo.py` durante a execução. Sinaliza que alterações de status são esperadas. Não definir manualmente. |
| `ORACULO_PULAR_RESOLVER_AGUARDANDO_AUTO` | `0` ou `1` | `1` | `1` = pula a etapa 10 (não remove cards "Aguardando" automaticamente com base em mensagem nova). Comportamento padrão para não interferir em cargas do dia a dia. |
| `ORACULO_EXECUTAR_9B_RESOLVER_AGUARDANDO` | `0` ou `1` | `0` | `1` = força a etapa 10 mesmo quando ela seria pulada. |
| `ORACULO_SUBIR_ALTERAR_DIAS_ANTERIORES` | `0` ou `1` | `0` | `1` = desativa a preservação automática de dias anteriores. Usar com cuidado — pode alterar status de cards já fechados. |

---

## 4. Limpeza e refazer dias

Para apagar e reprocessar dados de datas específicas.

| Variável | Formato | Exemplo | Descrição |
|----------|---------|---------|-----------|
| `ORACULO_REFazer_DIA` | DD/MM/YYYY | `03/06/2026` | Apaga e reprocessa um dia específico antes do pipeline rodar. |
| `ORACULO_LIMPAR_PERIODO_ANTES` | `0` ou `1` | `1` | `1` = limpa o período antes de rodar (requer ORACULO_LIMPAR_DE e ORACULO_LIMPAR_ATE). |
| `ORACULO_LIMPAR_DE` | DD/MM/YYYY | `01/06/2026` | Início do período a limpar (com ORACULO_LIMPAR_PERIODO_ANTES=1). |
| `ORACULO_LIMPAR_ATE` | DD/MM/YYYY | `05/06/2026` | Fim do período a limpar (com ORACULO_LIMPAR_PERIODO_ANTES=1). |
| `ORACULO_LIMPAR_DATA` | DD/MM/YYYY | `03/06/2026` | Atalho: limpar um único dia (substitui DE e ATE). |
| `ORACULO_REFazer_PRESERVAR_MARCACOES_MANUAIS` | `0` ou `1` | `1` | `1` = ao refazer um dia, mantém as marcações manuais de Aguardando/Concluído feitas pelo analista. |

---

## 5. Triagem automática

Ativam ou desativam as regras de classificação automática de threads.

| Variável | Valores | Padrão | Descrição |
|----------|---------|--------|-----------|
| `TRIAGEM_AUTO_DDR4111` | `0` ou `1` | `1` | Ativa a triagem principal (DDR/4111) **e toda a cadeia** (DLI, DLO, DRL, S5, SUPORTE, DRSAC, FORCAPITAL, DRM e categorias automáticas). |
| `TRIAGEM_AUTO_RETORNO_BACEN` | `0` ou `1` | `1` | Ativa a triagem de threads RETORNO_BACEN. Separada da cadeia principal por ser mais delicada. |
| `TRIAGEM_AUTO_DATA_REF` | YYYY-MM-DD | `2026-06-02` | Limita a triagem ao dia indicado — só reclassifica threads que têm mensagem nesse dia. Definido automaticamente pelo pipeline em cargas de um único dia. |
| `ORACULO_TRIAGEM_FILTRO_DATA_REF` | `0` ou `1` | `1` | `0` = desativa o filtro de data da triagem (processa todas as threads históricas). Usado internamente pelo pipeline em cargas multi-dia. |
| `TRIAGEM_AUTO_DLI` | `0` ou `1` | via DDR | Ativa triagem DLI_2062 individualmente (normalmente ativada pela cadeia DDR). |
| `TRIAGEM_AUTO_DLO` | `0` ou `1` | via DDR | Ativa triagem DLO_2061 individualmente. |
| `TRIAGEM_AUTO_DRM` | `0` ou `1` | via DDR | Ativa triagem DRM_2060 individualmente. |
| `TRIAGEM_AUTO_S5` | `0` ou `1` | via DDR | Ativa triagem S5 individualmente. |
| `TRIAGEM_AUTO_SUPORTE` | `0` ou `1` | via DDR | Ativa triagem SUPORTE individualmente. |
| `TRIAGEM_AUTO_DRSAC` | `0` ou `1` | via DDR | Ativa triagem DRSAC individualmente. |
| `TRIAGEM_AUTO_FORCAPITAL` | `0` ou `1` | via DDR | Ativa triagem FORCAPITAL individualmente. |
| `TRIAGEM_AUTO_6209` | `0` ou `1` | `0` | Ativa triagem CADOC 6209 (requer ativação explícita, não faz parte da cadeia DDR). |
| `TRIAGEM_AUTO_RISK_DRIVER_ALERTA` | `0` ou `1` | via DDR | Ativa triagem RISK_DRIVER_ALERTA individualmente. |
| `TRIAGEM_AUTO_RISK_DRIVER_RELATORIO` | `0` ou `1` | via DDR | Ativa triagem RISK_DRIVER_RELATORIO individualmente. |
| `TRIAGEM_AUTO_RISK_DRIVER_RESP_AUTO` | `0` ou `1` | via DDR | Ativa triagem RISK_DRIVER_RESP_AUTO individualmente. |
| `TRIAGEM_AUTO_FOGBUGZ` | `0` ou `1` | via DDR | Ativa triagem FOGBUGZ individualmente. |
| `TRIAGEM_AUTO_LEIAUTES_BACEN` | `0` ou `1` | via DDR | Ativa triagem LEIAUTES_BACEN individualmente. |

---

## 6. Scripts específicos

Controlam comportamentos pontuais de scripts individuais.

| Variável | Script | Valores | Descrição |
|----------|--------|---------|-----------|
| `ORACULO_SCRIPT12_SEM_FILTRO_DATA` | 12 — OCR | `0` ou `1` | `1` = processa todas as imagens do histórico (limpa o backlog). Padrão é processar só o dia atual. |
| `ORACULO_SCRIPT16_SEM_FILTRO_DATA` | 16 — LLM BACEN | `0` ou `1` | `1` = regenera resumos LLM de todas as threads RETORNO_BACEN (não só as do dia). |
| `INTEGRADOR_08_SEM_PRESERVAR_TEXTO_IMAGENS` | 09 — Integrador | `0` ou `1` | `1` = não preserva texto OCR de imagens ao reintegrar. Uso excepcional. |
| `ORACULO_IGNORAR_DEPS` | todos | `0` ou `1` | `1` = ignora avisos de dependência entre scripts (ex: rodar 09 sem ter rodado 05 antes). Só para uso cirúrgico. |
| `ORACULO_BLOQUEAR_REGRESSAO_STATUS` | motor | `0` ou `1` | `1` = impede que o motor altere status de threads fora de uma carga em curso. |
| `FOGBUGZ_FILTER_ID` | 08 — FogBugz | número | ID do filtro ativo no FogBugz. Padrão: `218`. Alterar se o filtro for recriado. |

---

## 7. Alertas por e-mail

| Variável | Descrição |
|----------|-----------|
| `ORACULO_ALERTA_EMAIL` | `0` = desativa envio de e-mails de alerta (mantém o log). |
| `ORACULO_ALERTA_DESTINO` | E-mail alternativo para receber alertas (substitui ADMIN_EMAIL). |
| `ADMIN_EMAIL` | E-mail padrão do administrador para receber alertas. |

---

## 8. Credenciais (arquivo .env)

Estas variáveis contêm senhas e tokens — ficam **apenas no `.env`**, nunca no código.

| Variável | Descrição |
|----------|-----------|
| `GMAIL_USER` | Endereço Gmail usado para coletar e-mails via IMAP. |
| `GMAIL_APP_PASS` | App Password do Gmail (não é a senha normal da conta). |
| `EMAIL_USER` | Conta Gmail para envio de alertas. |
| `EMAIL_PASS` | App Password da conta de envio. |
| `FOGBUGZ_TOKEN` | Token de API do FogBugz. Gerar em Configurações > API no FogBugz. |
| `OPENAI_API_KEY` | Chave da API OpenAI (usada nos scripts 07, 15, 16). |
| `GEMINI_API_KEY` | Chave da API Gemini (alternativa ao OpenAI, usada no gemini_engine). |
| `GEMINI_MODEL` | Modelo Gemini a usar (ex: `gemini-1.5-pro`). |

---

## Referência rápida — situações comuns

| Situação | Variáveis a definir |
|----------|-------------------|
| Carga normal do dia | Nenhuma — o `executar_tudo.py` define tudo automaticamente |
| Ver detalhes de cada e-mail | `ORACULO_VERBOSE=1` |
| Limpar o backlog de OCR | `ORACULO_SCRIPT12_SEM_FILTRO_DATA=1` |
| Regenerar todos os resumos BACEN | `ORACULO_SCRIPT16_SEM_FILTRO_DATA=1` |
| Refazer um dia do zero | `ORACULO_REFazer_DIA=DD/MM/YYYY` |
| Rodar um script isolado sem aviso de dependência | `ORACULO_IGNORAR_DEPS=1` |
| Testar sem enviar e-mail de alerta | `ORACULO_ALERTA_EMAIL=0` |

---

*Última atualização: 05/06/2026*
