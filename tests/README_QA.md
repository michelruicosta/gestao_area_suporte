# QA – Registro de Correções (ORÁCULO 360)

Testes automatizados que garantem a consistência das correções em **REGISTRO_CORRECOES.md**.

---

## Fluxo recomendado

1. **Ler o arquivo de correções**  
   Antes de alterar código, o assistente (ou você) lê `REGISTRO_CORRECOES.md` na raiz.

2. **Montar o cenário para o QA**  
   Ao corrigir ou implementar, o assistente atualiza o registro e adiciona/ajusta testes em `tests/` (pastas e nomes abaixo).

3. **Você roda o script do QA**  
   Na raiz do projeto:
   ```bash
   python run_qa.py
   ```
   - **Saída 0:** todos os testes passaram.  
   - **Saída 1:** algum teste falhou; a mensagem indica qual.

---

## Como rodar

```bash
# Na raiz do projeto (recomendado)
python run_qa.py
```

Ou diretamente o runner dos testes:

```bash
python tests/run_qa.py
```

Com pytest (opcional):

```bash
pytest tests/ -v -k "test_"
```

---

## Organização dos testes

Os testes ficam em **arquivos por área**, alinhados às seções do **REGISTRO_CORRECOES.md**:

| Arquivo | O que valida |
|---------|----------------|
| **conftest.py** | Configuração compartilhada: `RAIZ`, `decode_mime_header`, `deduplica_cadocs`, `filter_signature_from_attachment`, `extrair_data_evento`. |
| **test_01_registro.py** | Existência e conteúdo do `REGISTRO_CORRECOES.md`. |
| **test_02_templates.py** | Contrato do frontend: decode MIME, CADOCs únicos, filtro de assinatura; template tem as funções. |
| **test_03_painel.py** | `_extrair_data_evento`, filtro por data (thread só aparece se houver mensagem na data), uso de `thread_datas_presentes`. |
| **test_03_painel_integracao_03.py** | **Dado real:** carrega `data/json/03_integrador_dados_site.json` e verifica que a thread "ENC: COS 12 2025 - Conecta" não está em "hoje" ao filtrar por 13/02 (pois as mensagens são só de 12/02). Se o 03 não existir, o teste é ignorado. |
| **test_04_script_08.py** | Script 08: `_parse_data_br` (DD/MM/YYYY e RFC 2822). |
| **test_05_script_01.py** | Script 01: mensagem amigável em erro getaddrinfo/rede. |
| **test_06_script_09.py** | Script 09: opção `--incremental` e log em arquivo. |
| **run_qa.py** | Runner: importa os módulos acima e executa a lista `TESTS` de cada um. |

Cada `test_XX_*.py` expõe uma lista **`TESTS`** com as funções de teste. Ao adicionar uma nova correção no registro, inclua o teste no arquivo da área correspondente e, se precisar, use os helpers em **conftest.py**.

---

## Adicionando novos testes

1. Inclua a correção em **REGISTRO_CORRECOES.md** (data, descrição, arquivos).
2. No **arquivo de testes da área** (ex.: painel → `test_03_painel.py`), adicione uma função `test_nome_descritivo` e inclua-a na lista **`TESTS`** do módulo.
3. Rode `python run_qa.py` e confira que tudo passa.

Assim, o QA continua alinhado ao registro e organizado por pasta e nomes.
