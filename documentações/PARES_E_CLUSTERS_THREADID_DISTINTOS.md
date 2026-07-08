# Pares e clusters com **threadId** diferentes

> **Contexto geral do projeto:** ver `documentações/MAPA_DO_PROJETO.md`

Documentação de negócio + técnica: quando o Gmail abre **dois ou mais fios** (`threadId` distintos) para o **mesmo caso operacional**, como o ORÁCULO os relaciona na tela, o que é **sugerido automaticamente** e o que depende de **regra documentada** ou **confirmação humana**.

**Última atualização:** 2026-04-14

---

## 1. Três mecanismos no produto

| Mecanismo | Origem | Quando usar |
|-----------|--------|-------------|
| **Par sugerido** (`pares_sugeridos` na API `/api/dados`) | Algoritmo no backend | Dois fios com **mesma empresa** (chave do card) e **mesmo fingerprint** de `lista_prazos` — ver §2. |
| **Cluster multi-thread** (`clusters_multi_thread` na API com `?data=…`) | Algoritmo no backend | **Três ou mais** fios com a mesma chave; exposto para revisão na UI (badge **«Grupo 3+»**); **não** funde automaticamente. |
| **Par confirmado** (`pares_confirmados` na API) | Ficheiro `data/json/pipeline/pares_threads_confirmados.json` | Utilizador **confirmou** na UI que dois `threadId` são o mesmo caso; o operacional **funde** num só card e o modal pode mostrar **as duas threads** (histórico fundido). |
| **Cluster / cruzamento** (matriz, triagem manual) | `MATRIZ_DECISOES_DDR_4111_E_EXCECOES.md`, §6 e tabelas de cruzamento | **Três ou mais** fios, **títulos diferentes**, ou **mesmo cliente** com **datas-base diferentes** — o algoritmo de par **não** liga sozinho; define-se política de card único, fundir ou manter separado. |

Referência de código: `painel_oraculo._computar_pares_sugeridos_operacional`, resposta JSON `pares_sugeridos` / `pares_confirmados`; `templates/email_operacional.html` — `getReciprocalParPeer`, `aplicarFusaoCardsPar`, `mergeThreadApiObjectsForModal`.

---

## 2. Algoritmo do **par sugerido** (resumo)

1. Para cada `threadId` visível na **DATA REF**, fica o **evento mais recente** (por `timestamp_epoch` / `timestamp`).
2. **Chave de empresa:** texto normalizado de `empresa` do evento; na prática no `03` costuma coincidir com o **cliente** do card — ver `painel_oraculo._empresa_chave_par_operacional` (ignora vazio / «desconhecido»).
3. **Fingerprint de prazos:** conjunto **ordenado** de tuplas `(cadoc, data_base, prazo_limite)` vindas de `lista_prazos` — `painel_oraculo._fingerprint_lista_prazos_operacional`.
4. Agrupa por `(chave_empresa, fingerprint)`. Só entra na lista de pares se o bucket tiver **exatamente dois** `threadId` **distintos** (evita ambiguidade com 3+ fios).

**Limitação:** fios que são o mesmo negócio mas com **listas de prazos diferentes** (ex.: remendos de classificação), **empresa** distinta no JSON, ou **três** fios no mesmo objeto **não** formam par automático — tratam-se na matriz como **cluster** (ex.: Mirae 19/02).

---

## 3. Pares **automáticos** (exemplo DATA REF 23/02/2026)

Lista **regenerável** a partir do `03` atual:

```text
python scripts/gerar_documentacao_pares_threadid.py --data 2026-02-23
```

Saída: `documentações/PARES_AUTOMATICOS_ALGORITMO_2026-02-23.md` (sobrescreve ao mudar de data no argumento).

**Snapshot já gerado no repositório (4 pares em 23/02/2026):**

| threadId A | threadId B | Contexto |
|------------|------------|----------|
| `GMTHRID_1857919633775523126` | `GMTHRID_1857921955423620769` | **Planner** — pedido DLI dezembro (**91933**) e resposta com remessas **2062** (**91940**); mesmo fingerprint de prazos. |
| `GMTHRID_1857930797949325527` | `GMTHRID_1857934562842580009` | **Fair** — pedido de dados **4111** (**91973**) e envio de relatórios **4111** (**91980**). |
| `GMTHRID_1857941262144216568` | `GMTHRID_1857943550501312143` | **TC** — cliente envia **saldos** 20/02 e, noutro fio, Finaud devolve **DDR+4111** 20/02 (mesmo conjunto de prazos no `03`). |
| `GMTHRID_1857938111478876957` | `GMTHRID_1857948329421136282` | **BCP Securities** — fios DLO / retorno (não DDR); aparecem no operacional do dia com mesmo fingerprint. |

> Para a lista **atualizada** após novo pipeline, abra o ficheiro `PARES_AUTOMATICOS_ALGORITMO_2026-02-23.md` gerado pelo script ou volte a executá-lo.

---

## 4. Clusters e pares **negociais** (threadId distintos, **fora** ou **além** do par automático)

Casos já alinhados na **matriz** (`documentações/MATRIZ_DECISOES_DDR_4111_E_EXCECOES.md`); o painel **não** assume estes vínculos sem confirmação ou regra futura.

### 4.1 BANVOX / Trustee — cancelamento + pedido (**§1**)

| threadId | ids (ref.) | Papel |
|----------|--------------|--------|
| `GMTHRID_1857927536823708713` | 91968, 92018 | Pedido / cobrança retorno (extrato **20/02**). |
| `GMTHRID_1857957622791390768` | 92019 | **Cancelar** o mesmo pedido. |

**Regra:** um único objeto de negócio; cancelamento encerra os dois fios (**Concluído**). **Não** depende de `lista_prazos` idêntica entre títulos «RES:» e «Cancelar:».

### 4.2 Acredito — **duas datas-base** DDR (cruzamento)

| threadId | Data base DDR | Nota |
|----------|----------------|------|
| `GMTHRID_1857673290831320590` | **19/02** | Remessa Finaud ao cliente (**91946**). |
| `GMTHRID_1857949781567601972` | **20/02** | Cliente envia insumos composição (**92013**). |

**Regra:** mesmo cliente; **não** fundir automaticamente só por nome — são **ciclos distintos** (ver tabela «Cruzamento» na matriz).

### 4.3 Mirae — **PI Exposure** audit **19/02** (três `threadId`)

| threadId | ids | Função no cluster |
|----------|-----|---------------------|
| `GMTHRID_1857945692134753217` | 92002, 92003 | Pedido Finaud → resposta cliente (aplicações). |
| `GMTHRID_1857946244000662182` | 92004 | Andrea envia **DDR 19/02** (fio só com remessa). |
| `GMTHRID_1857658685669939294` | 92001 | Ramo paralelo «Segue aplicações» **19/02**. |

**Motivo de não ser «par» de 2:** são **três** fios; títulos **diferentes**; política §6 = cluster / fundir âncora conforme triagem.

### 4.4 Mirae — audit **20/02** (outro dia no assunto)

| threadId | ids |
|----------|-----|
| `GMTHRID_1857939595420197235` | 91986, 91999 |

**Regra:** **não** fundir com os fios do **19/02** — data do audit no assunto distingue o objeto.

### 4.5 Risk Driver — **mesmo título**, dois Gmail (varredura matriz)

| threadId A | threadId B |
|------------|------------|
| `GMTHRID_1857925167668018751` | `GMTHRID_1857973059228231907` |

Alerta automático duplicado; padrão estrutural semelhante a «dois cards para um facto», mas **cadoc** típico **risk driver** / fora da sub-fila DDR/4111.

---

## 5. Par **confirmado** pelo utilizador

- Persistência: `data/json/pipeline/pares_threads_confirmados.json` (lista de `{ "thread_a", "thread_b", ... }`; apaga com nova carga / `deletar_carga`).
- Efeito na UI: um **só card** na lista quando o par está confirmado; **KPIs** e «monitorar resposta» podem **deduplicar** os dois `threadId` (ver `REGISTRO_CORRECOES.md` — entrada operacional par fundido).

---

## 6. Boas práticas para triagem automática futura

1. **Respeitar** primeiro os **pares sugeridos** quando empresa + prazos batem certo com o caso real.  
2. **Clusters** (Mirae, BANVOX, Acredito 19 vs 20): exigir **regras explícitas** ou ML com **features** (assunto, data base no título, `In-Reply-To`) — não inferir só por cliente.  
3. Após **confirmação humana**, gravar **par confirmado** para o painel replicar o comportamento entre cargas.

---

## 7. Ficheiros relacionados

| Ficheiro | Conteúdo |
|----------|----------|
| `documentações/PARES_AUTOMATICOS_ALGORITMO_2026-02-23.md` | Saída do script (pares do algoritmo para uma data). |
| `scripts/gerar_documentacao_pares_threadid.py` | Gera a tabela de pares automáticos. |
| `documentações/MATRIZ_DECISOES_DDR_4111_E_EXCECOES.md` | §6, cruzamentos Acredito / Mirae / BANVOX. |
| `documentações/THREADIDS_OPERACIONAL_2026-02-23.md` | Lista de todos os cards do dia (contexto). |
