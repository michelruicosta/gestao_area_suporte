# Padrões de Anexos — Oráculo 360 Finaud

Documento vivo. Cada padrão é mapeado a partir do histórico real de produção e validado com Michel antes de ser gravado aqui. Serve de consulta para o sistema e para futuras sessões.

**Como usar:** antes de implementar qualquer regra que envolva anexos, consultar este documento primeiro. Se o padrão não estiver aqui, mapear e registrar antes de implementar.

**Fonte dos dados:** ambiente de produção (`oraculo_360_finaud`) — 8825 emails, 4786 threads, 2527 emails com anexo.

**Última atualização:** 2026-07-07

---

## Índice

| ID | Nome | Quem envia | Extensão | Status da regra |
|---|---|---|---|---|
| A | ZIP de CADOC enviado pela Finaud ao cliente | Finaud | .zip | Mapeado — regra futura |
| B | ZIP de extrato diário Amaril Franklin (DDR) | Cliente (Amaril Franklin) | .zip | Mapeado — sem regra |
| C | ZIP de CADOC problemático reenviado pelo cliente | Cliente | .zip | Mapeado — sem regra |
| D | ZIP de retorno do sistema CRD do BACEN | Cliente | .zip | Mapeado — sem regra |
| E | Dados financeiros do cliente (insumo para CADOC) | Cliente | .pdf, .xlsx, .xls, .csv | Mapeado — sem regra |
| E2 | Comunicação do BACEN enviada pelo cliente | Cliente | .pdf | Mapeado — sem regra |
| F | Templates da Finaud preenchidos pelo cliente | Cliente | .xlsx, .xls | Mapeado — sem regra |
| G | E-mails informativos da Finaud (CADOC=INTERNO) | Finaud | .pdf | Mapeado — sem ação |
| H | Arquivos COSIF (COS4010, COS4016, conglomerado) | Cliente | .zip, .txt, .pdf | Mapeado — sem regra |

---

## Padrão A — ZIP de CADOC enviado pela Finaud ao cliente

**Quem envia:** Finaud
**Direção:** Finaud → Cliente
**Extensão:** .zip
**Nome do arquivo:** `CNPJ_CADOC_DATA_I/D_versao.zip`

Exemplos:
- `32648370_2011_20260218_I_1.zip`
- `67030395_4111_20260224_I_1.zip`
- `00329598_2062_202512_S_4_4016.zip`

Legenda dos campos no nome:
- `CNPJ`: CNPJ do cliente (8 dígitos)
- `CADOC`: código do documento (2011, 4111, 2061, 2062, 2160, 2060)
- `DATA`: data de competência no formato YYYYMMDD (DDR/DLO/DLI) ou YYYYMM (mensais)
- `I/D/S/E`: I=inclusão, D=substituição, S=substituição (variante), E=exclusão — para o negócio não muda nada
- `versao`: número de versão gerado pelo browser ao baixar duplicatas — para o negócio não muda nada

**O que é:** O arquivo gerado pelo sistema da Finaud contendo o CADOC pronto para envio ao BACEN. A Finaud gerou, conferiu e está entregando ao cliente (ou enviando diretamente ao BACEN, dependendo do contrato).

**CADOCs que aparecem:** DDR_2011, 4111, DLO_2061, DLI_2062, DRL_2160, DRM_2060

**Significado para o negócio:** A Finaud cumpriu sua obrigação — o documento regulatório foi gerado e entregue. Do lado da Finaud: CONCLUÍDO.

**Regra de triagem (futura):**
Quando a Finaud envia um email com ZIP neste padrão → classificar thread como CONCLUÍDO automaticamente.
⚠️ Ainda não implementada — aguarda definição de como detectar o padrão no nome do arquivo.

**Evidência no histórico (produção):**
- 176 emails da Finaud com anexo ZIP classificados como DDR_2011
- 83 como 4111, 30 como DLO_2061, etc.
- Assuntos típicos: "DDRs de 18 e 19/02/2026.", "Relatórios 4111 de 18, 19 e 20/02/2026."

**O que não sabemos:**
O conteúdo interno do ZIP (não foi lido). Não é necessário para a regra — o nome do arquivo já identifica o padrão.

---

## Padrão B — ZIP de extrato diário Amaril Franklin (DDR)

**Quem envia:** Cliente — exclusivamente `noesantana@amarilfranklin.com.br` (Amaril Franklin CTV LTDA)
**Direção:** Cliente → Finaud
**Extensão:** .zip
**Nome do arquivo:** `DDMMYYYY.zip` (apenas a data, sem outros campos)

Exemplos:
- `20022026.zip`, `23022026.zip`, `01062026.zip`

**O que é:** Arquivo de extrato diário de operações que a Amaril Franklin envia à Finaud para que ela importe os dados e gere o DDR do dia. É o insumo que a Finaud precisa para trabalhar.

**Assunto padrão:** "Emissão DDR DD/MM/YYYY"
**Corpo padrão:** "Segue em anexo o arquivo para emissão do DDR de DD/MM/YYYY."

**CADOCs:** DDR_2011 (exclusivo)

**Significado para o negócio:** A Finaud recebeu os dados do dia e precisa processar. Não é o CADOC pronto — é a matéria-prima. Thread fica AGUARDANDO até a Finaud gerar e enviar o DDR.

**Regra de triagem:** Nenhuma. A data está no assunto e no corpo do email — não é necessário extrair do nome do arquivo. A data de competência já é capturada pelo pipeline.

**Observação:** O conteúdo do ZIP não foi lido. Não é necessário para nenhuma regra atual.

---

## Padrão C — ZIP de CADOC problemático reenviado pelo cliente

**Quem envia:** Clientes (vários)
**Direção:** Cliente → Finaud
**Extensão:** .zip
**Nome do arquivo:** Segue o padrão BACEN (`CNPJ_CADOC_DATA_I/D.zip`) — é o mesmo arquivo que o cliente enviou ao BACEN e que foi rejeitado ou criticado.

Exemplos:
- `47965438_2061_20251201_4016_D.zip`
- `54541468_2061_20251201_4016_I.zip`
- `42723848_2061_20260101_4060_I.zip`
- `34335592_2062_202601_S_1_4010.zip`

**O que é:** O cliente recebeu rejeição ou crítica do BACEN em relação a um arquivo que enviou. Está reenviando esse arquivo para a Finaud analisar, identificar o problema e corrigir.

**Contexto típico:**
- Assuntos: "Crítica DLO 12.2025", "DLO Recusado Nikos DTVM", "Indício de Qualidade - DLO - jan/2026", "Inconsistências DLO 12/2025"
- Corpo: "Segue o arquivo", "Segue conforme solicitado", "Seguem os arquivos que enviamos ao BACEN"

**CADOCs:** Aparece principalmente em RETORNO_BACEN, DLO_2061, DLI_2062, DDR_2011

**Significado para o negócio:** A Finaud precisa analisar o arquivo e orientar o cliente a corrigi-lo ou reenviar. Thread fica AGUARDANDO.

**Regra de triagem:** Nenhuma. O padrão do nome é idêntico ao Padrão A — não é possível distinguir só pelo nome se foi a Finaud ou o cliente que enviou. A distinção vem do campo `lado` do remetente ("FINAUD" vs "CLIENTE").

---

## Padrão D — ZIP de retorno do sistema CRD do BACEN

**Quem envia:** Clientes (vários)
**Direção:** Cliente → Finaud
**Extensão:** .zip (ou .txt dentro do zip)
**Nome do arquivo:** Número genérico gerado pelo browser ao baixar do portal CRD do BACEN.

Exemplos:
- `371795241.zip`, `364950806.zip`, `361885185.zip`
- `372923218.zip`, `374840178.zip`, `374186733.zip`

**O que é:** O cliente baixou do portal CRD do BACEN o arquivo de resposta contendo o XML com as críticas/rejeições. Envia para a Finaud entender qual é o problema e orientar a correção.

**Contexto típico:**
- Corpo pode conter diretamente o XML: `"<?xml version="1.0"... <respostaCRD..."`
- Ou o cliente diz: "Essa é a mensagem que veio do sistema CRD", "BC retornou como rejeitado, segue arquivo"
- Às vezes vem junto com um ZIP de CADOC (Padrão C)

**CADOCs:** RETORNO_BACEN (quase exclusivo)

**Significado para o negócio:** A Finaud precisa ler o XML de retorno do BACEN para entender a crítica e orientar a correção. Thread fica AGUARDANDO.

**Regra de triagem:** Nenhuma. Não há como identificar o conteúdo pelo nome do arquivo — seria necessário abrir e ler. Baixa prioridade para automação.

**O que não sabemos:** O conteúdo exato dos ZIPs (não foram lidos). Uma análise futura poderia identificar os tipos de crítica mais recorrentes.

---

## Padrão E — Dados financeiros do cliente (insumo para CADOC)

**Quem envia:** Clientes (vários)
**Direção:** Cliente → Finaud
**Extensões:** .pdf, .xlsx, .xls, .csv
**CADOCs:** DDR_2011, DLO_2061, DRL_2160, DRM_2060 e outros

**O que é:** O cliente envia documentos com sua posição financeira para que a Finaud importe os dados e gere o CADOC correspondente. São a matéria-prima do trabalho — sem esses arquivos, a Finaud não consegue gerar o documento regulatório. O formato varia por cliente e por CADOC: alguns enviam PDF, outros planilha, outros CSV.

**Tipos de conteúdo que aparecem:**
- Balancete (balanço contábil do período)
- Extrato bancário / extrato de investimentos
- Posição de operações compromissadas
- Posição de derivativos
- Posição de câmbio (CAM 0050 — planilha padrão do BACEN)
- Saldos de conta corrente / caixa
- Posições de renda fixa (RD_PREFIXADA, RD_LFT)
- Posições em fundos de investimento

**Exemplos de nomes (.pdf):**
- `Balancete - 18.02.pdf`, `BALANCETE 20-02-2026.pdf`
- `BANCO COMPROMISSADA 20022026.pdf`
- `DERIVATIVOS 20-02-2026.pdf`
- `CAM 0050 20-02-2026.pdf`
- `EXTRATO INVESTIMENTO CDB - BB - FEV-26.pdf`

**Exemplos de nomes (.xlsx/.xls):**
- `RD_PREFIXADA 19 02 2026.xlsx`, `RD_LFT - 19 02 2026.xlsx`
- `Fundo de investimento - 19 02 2026.xlsx`
- `BALANCETE 20-02-2026.xlsx`
- `Operacoes compromissadas SCD.xlsx`
- `DADOS BI - DRL REF 01.2026.xlsx`
- `DRM_2060_Finaud_202601.xlsx` — planilha do cliente sobre DRM (não é template da Finaud)

**Exemplos de nomes (.csv):**
- `BANCO COMPROMISSADA 20022026.csv`
- `CORRETORA CDB PRE 20022026.csv`
- `RD_MOEDA_19.02.2026.csv`

**Significado para o negócio:** Thread fica AGUARDANDO — a Finaud recebeu os dados e precisa processar para gerar o CADOC.

**Regra de triagem:** Nenhuma. Não é possível identificar pelo nome do arquivo qual CADOC será gerado.

---

## Padrão E2 — Comunicação do BACEN enviada pelo cliente

**Quem envia:** Clientes (vários)
**Direção:** Cliente → Finaud
**CADOCs:** RETORNO_BACEN (exclusivo)

**O que é:** O cliente recebeu alguma comunicação do BACEN sobre um problema no arquivo que enviou (crítica, rejeição, indício de qualidade, ofício) e encaminha para a Finaud analisar e orientar a correção. Pode ser:
- Print da tela do sistema CRD do BACEN salvo como PDF
- Ofício oficial do BACEN
- Relatório de apontamento de qualidade
- Mensagem de indício de qualidade com protocolo

**Exemplos de nomes:**
- `OFICIO_15988_2026-BCB_DESUC.pdf` — ofício oficial
- `RELATORIO SUMULA ID 10108 - APONTAMENTO 10108.AD001.pdf`
- `Mensagem protocolo 399829415 - Indicio de qde - DLO.pdf`
- `bccorreio.bcb.gov.br_...aspx.pdf` — print da página do BACEN

**Significado para o negócio:** Thread fica AGUARDANDO — a Finaud precisa analisar a crítica e orientar o cliente.

**Regra de triagem:** Nenhuma.

**O que não sabemos:** O conteúdo dos PDFs (não foram lidos). Uma análise futura poderia identificar os CADOCs mais criticados e os tipos de erro mais recorrentes.

---

## Padrão F — Templates da Finaud preenchidos pelo cliente

**Quem envia:** Clientes (vários)
**Direção:** Cliente → Finaud
**Extensões:** .xlsx, .xls
**CADOCs:** DLO_2061, DRL_2160, DDR_2011, 4111 e outros

**O que é:** A Finaud disponibiliza planilhas com layout padronizado para que o cliente preencha com os dados do período e devolva. A Finaud então importa esses dados para gerar o CADOC. É diferente do Padrão E porque o arquivo segue um formato que a Finaud definiu — não é o cliente escolhendo como enviar.

**Templates identificados por CADOC:**

| Template | CADOC | Descrição |
|---|---|---|
| `Importacao_LEC_YYYYMM.xls` | DLO_2061 | Planilha LEC (Livro de Escrituração Contábil) |
| `Importacao_DRL_2160_YYYY.MM.xls` | DRL_2160 | Planilha de importação para DRL |
| `DOC_4111_YYYYMMDD.xlsx` | 4111 | Planilha diária do documento 4111 |
| `RD_PREFIXADA DD MM YYYY.xlsx` | DDR_2011 | Posição de renda fixa prefixada (template Finaud) |
| `RD_LFT - DD MM YYYY.xlsx` | DDR_2011 | Posição em LFT (template Finaud) |
| `Fundo de investimento - DD MM YYYY.xlsx` | DDR_2011 | Posição em fundos (template Finaud) |

**Exemplos de nomes:**
- `Importacao_LEC 012026.xlsx`, `Importacao_LEC_202512.xls`
- `Importacao_DRL_2160_2026.01.xls`, `Importacao_DRL_01_2026.xls`
- `DOC_4111_20260219.xlsx`, `DOC_4111_20260220.xlsx`
- `RD_PREFIXADA 19 02 2026.xlsx`
- `CADOC 4111.xlsx`

**Significado para o negócio:** Thread fica AGUARDANDO — a Finaud recebeu o template preenchido e precisa importar para gerar o CADOC.

**Regra de triagem:** Nenhuma direta. No futuro, poderia ser usada para confirmar que o cliente enviou os dados necessários para iniciar a geração.

---

## Padrão G — E-mails informativos da Finaud (CADOC=INTERNO)

**Quem envia:** Finaud (`contato@finaud.com.br`)
**Direção:** Finaud → Clientes (mailing)
**Extensão:** .pdf
**CADOCs:** INTERNO (nunca chegam à triagem)

**O que é:** Serviço de curadoria de normativos que a Finaud criou para manter os clientes informados sobre publicações do BACEN. Disparado todo dia útil com os comunicados, resoluções e instruções normativas publicados naquele dia.

**Três tipos de assunto:**
- "Atualização de Comunicados e Normativos – DD/MM/YYYY"
- "Atualização Bacen – DD/MM/YYYY"
- "Atenção: Atualização na página de Leiautes do Bacen na data: DD/MM/YYYY"

**Anexos típicos:**
- `BC - Comunicado Nº 44.763 de 23_02_2026.pdf`
- `BC - Instrução Normativa BCB Nº 710 de 23_02_2026.pdf`
- `BC - Resolução CMN Nº 5.284 de 26_02_2026.pdf`

**Significado para o negócio:** Não requer ação — é informativo.

**Tratamento no sistema:** Já classificado como CADOC=INTERNO pelo assunto em `mapeamento_regras_negocio.json`. Nunca chega à triagem. Nenhuma mudança necessária.

---

## Padrão H — Arquivos COSIF enviados pelo cliente

**Quem envia:** Clientes (vários)
**Direção:** Cliente → Finaud
**Extensões:** .zip, .txt, .pdf
**CADOCs:** DLO_2061, DLI_2062, S5

**O que é:** O COSIF (Plano Contábil das Instituições do Sistema Financeiro Nacional) é o padrão contábil obrigatório do BACEN. Os clientes exportam esses arquivos do sistema de contabilidade deles e enviam para a Finaud importar no RiskDriver, que usa os dados para calcular e gerar os CADOCs.

**Documentos COSIF que aparecem:**
- **COS4010** — Balancete/Balanço Patrimonial
- **COS4016** — Extrato de posições específicas
- **4060 e 4066** — COSIF de conglomerado (junção de mais de uma empresa). Não encontrados como arquivo separado no histórico — a Wise os envia dentro do arquivo MDR junto com os demais.

**Formatos:**
- `.zip` — arquivo COSIF compactado para envio
- `.txt` — arquivo COSIF em texto puro (formato de importação)
- `.pdf` — versão "CosifNovo" (novo padrão BACEN), ex: `Guru CTVM Ltda_Ir26_IF CosifNovo v.1.2.0.pdf`

**Exemplos de nomes:**
- `COS4010_2026-01-I.zip`, `Cos4010.zip`, `Cos4016.zip`
- `4010 12.2025_Vert.txt`, `4016 12.2025_Vert.txt`
- `VIS DTVM - Arquivos COS4010 08-2025.zip`
- `EXECUTIVE CORRETORA - COS 4010 01_2026.zip`

**Contexto típico:**
- "Segue em anexo os dados para geração dos arquivos DLO e DLI"
- "Segue Arquivos COS 4010 Mes 01.2026 para seu cálculo"
- "Arquivos retificados" (cliente corrigiu e reenvia)

**Significado para o negócio:** Thread fica AGUARDANDO — a Finaud recebeu o COSIF e precisa importar no RiskDriver para gerar o CADOC.

**Regra de triagem:** Nenhuma.

**Observação — MDR:** Arquivos com prefixo `MDR_` e timestamp (`MDR_2026-01-23_12-02-15.zip`) aparecem exclusivamente da Wise. A Wise menciona que o MDR contém os dados 4060 e 4066 (COSIF de conglomerado). Provavelmente é um export do sistema deles que agrupa múltiplos COSIFs num único arquivo. Origem do formato desconhecida — esclarecer com a Wise se necessário.

---

## Backlog

Todos os padrões identificados no histórico de produção foram mapeados.
