"""
chat_ensino.py  —  Sessao de ensino em 3 fases

FASE 1 — Pre-classificacao automatica
  A IA analisa todos os casos da fila (incertas + regressoes) em silencio.
  Para cada caso verifica: confianca, conflito com gabarito, risco de regressao.

FASE 2 — Revisao do lote
  Apresenta os casos de alta confianca para aprovacao em bloco.
  Michel aprova tudo, revisa um a um, ou pula direto para os imprecisos.

FASE 3 — Conversa com os imprecisos
  Conversa caso a caso. Ao confirmar: grava gabarito E atualiza o registro
  definitivo — a thread passa para "confirmada" e nao volta para a fila.

Comandos durante a conversa:
  [Enter]                   continua conversando
  salvar / sim / yes / s    salva o gabarito e confirma a thread no registro
  pular / proximo / n       pula sem salvar (thread continua "incerta")
  sair                      encerra a sessao
"""

import json
import os
import sys
from datetime import datetime, date

from dotenv import load_dotenv
from openai import OpenAI

BASE = r'D:\02_Finaud\Projetos\ativos\gestao_area_suporte'
sys.path.insert(0, os.path.join(BASE, 'scripts'))
load_dotenv(os.path.join(BASE, '.env'))

from classificador_ia import _SISTEMA, CAMINHO_GAB, buscar_imagens, _extrair_texto_ocr

cliente = OpenAI()

PASTA_VALID      = os.path.join(BASE, 'data', 'validacao_classificacao')
ARQUIVO_DADOS    = os.path.join(BASE, 'data', 'json', 'pipeline',
                                '01_extração_dados_brutos_gmail.json')
ARQUIVO_REG_AMO  = os.path.join(PASTA_VALID, 'ultima_amostra_regressoes.json')
ARQUIVO_REGISTRO = os.path.join(BASE, 'data', 'registro_definitivo_threads.json')


# ── Carregamento ───────────────────────────────────────────────────────────────

def carregar_gabarito() -> dict:
    with open(CAMINHO_GAB, encoding='utf-8') as f:
        return json.load(f)


def carregar_registro() -> dict:
    """Carrega o registro definitivo de classificacoes das threads."""
    with open(ARQUIVO_REGISTRO, encoding='utf-8') as f:
        return json.load(f)


def salvar_registro(registro: dict):
    """Salva o registro atualizado e recalcula o resumo."""
    threads = registro['threads']
    registro['atualizado_em'] = date.today().isoformat()
    registro['resumo'] = {
        'total':        len(threads),
        'confirmadas':  sum(1 for t in threads.values() if t['status_regra'] == 'confirmada'),
        'incertas':     sum(1 for t in threads.values() if t['status_regra'] == 'incerta'),
        'sem_categoria': sum(1 for t in threads.values() if t['status_regra'] == 'sem_categoria'),
    }
    with open(ARQUIVO_REGISTRO, 'w', encoding='utf-8') as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def confirmar_no_registro(registro: dict, thread_id: str, assunto: str,
                           categorias: list, regra_usada: str, motivo: str):
    """Marca uma thread como confirmada no registro definitivo e salva."""
    registro['threads'][thread_id] = {
        'assunto':                assunto,
        'categorias':             categorias,
        'status_regra':           'confirmada',
        'regra_usada':            regra_usada,
        'motivo_regra_usada':     motivo,
        'data_confirmacao_regra': date.today().isoformat(),
    }
    salvar_registro(registro)


def carregar_threads() -> tuple[dict, dict, dict]:
    """
    Retorna (por_assunto, por_id, indices).
      por_assunto : assunto -> thread dict
      por_id      : thread_id -> thread dict
      indices     : assunto -> posicao na lista (para busca de imagens OCR)
    """
    with open(ARQUIVO_DADOS, encoding='utf-8') as f:
        dados = json.load(f)
    lista = dados if isinstance(dados, list) else dados.get('threads', [])
    por_assunto, por_id, indices = {}, {}, {}
    for i, t in enumerate(lista):
        ass = t.get('assunto', '')
        tid = t.get('thread_id', '')
        por_assunto[ass] = t
        por_id[tid]      = t
        indices[ass]     = i
    return por_assunto, por_id, indices


def carregar_regressoes() -> list:
    if not os.path.isfile(ARQUIVO_REG_AMO):
        return []
    with open(ARQUIVO_REG_AMO, encoding='utf-8') as f:
        return json.load(f)


# ── Formatacao ─────────────────────────────────────────────────────────────────

def _formatar_gabarito_completo(gabarito: dict) -> str:
    """Formata regras + gabaritos (v2) para exibição no prompt de ensino."""
    regras    = gabarito.get('regras', [])
    gabaritos = gabarito.get('gabaritos', [])
    linhas = ['## Regras e Gabaritos aprovados por Michel\n']

    if regras:
        linhas.append('### Regras — aplicar sempre que o padrão aparecer\n')
        for r in regras:
            cats = ', '.join(r.get('categorias', []))
            linhas.append(f'[{r["id"]}] {cats}')
            linhas.append(f'  Padrão: {r.get("padrao","")}')
            linhas.append(f'  Instrução: {r.get("instrucao","")}')
            if r.get('excecao'):
                linhas.append(f'  Exceção: {r["excecao"]}')
            linhas.append('')

    if gabaritos:
        linhas.append('### Gabaritos — exemplos para casos ambíguos\n')
        for g in gabaritos:
            cats = ', '.join(g.get('categorias', []))
            linhas.append(f'[{g["id"]}] "{g.get("assunto_exemplo","")}" → {cats}')
            linhas.append(f'  Por quê: {g.get("por_que_gabarito","")}')
            linhas.append('')

    return '\n'.join(linhas)


def _resumo_classificacoes(registro: dict) -> str:
    """Resume as threads confirmadas para incluir no prompt da IA."""
    contagem: dict[str, int] = {}
    n_conf = 0
    for entrada in registro['threads'].values():
        if entrada.get('status_regra') == 'confirmada':
            n_conf += 1
            for cat in entrada.get('categorias', []):
                contagem[cat] = contagem.get(cat, 0) + 1
    linhas = [f'## Baseline — {n_conf} threads classificadas corretamente\n']
    for cat, n in sorted(contagem.items(), key=lambda x: -x[1]):
        linhas.append(f'  {cat}: {n} threads')
    return '\n'.join(linhas)


def _formatar_email(thread: dict, indice: int = None) -> str:
    msgs    = thread.get('mensagens', [])
    assunto = thread.get('assunto', '')
    partes  = []

    for i, msg in enumerate(msgs, start=1):
        rem    = msg.get('remetente', '')[:80]
        corpo  = msg.get('corpo_texto', '')
        anexos = msg.get('nomes_anexos', [])

        if i == 1:
            bloco = f'De: {rem}'
            if anexos:
                imgs   = [a for a in anexos if a.lower().endswith(('.png','.jpg','.jpeg','.gif','.bmp'))]
                outros = [a for a in anexos if a not in imgs]
                if imgs:
                    bloco += f'\nAnexos (imagem): {", ".join(imgs)}'
                if outros:
                    bloco += f'\nAnexos: {", ".join(outros)}'
            bloco += f'\n\nCorpo:\n{corpo}'
        else:
            bloco = f'--- Mensagem {i} ---\nDe: {rem}\n\n{corpo}'

        partes.append(bloco)

    txt = f'Assunto: {assunto}\n\n' + '\n\n'.join(partes)

    if indice is not None:
        imgs_paths = buscar_imagens(indice)
        if imgs_paths:
            ocr = _extrair_texto_ocr(imgs_paths)
            if ocr:
                txt += f'\n\nTexto extraido das imagens (OCR):\n{ocr[:1000]}'

    return txt


def _buscar_casos_similares(assunto: str, registro: dict, n: int = 3) -> list:
    """Busca threads confirmadas com assunto parecido para usar como referencia."""
    palavras  = {w for w in assunto.lower().split() if len(w) > 3}
    pontuados = []
    for entrada in registro['threads'].values():
        if entrada.get('status_regra') != 'confirmada':
            continue
        ass_r = entrada.get('assunto', '')
        score = len(palavras & {w for w in ass_r.lower().split() if len(w) > 3})
        if score >= 1:
            pontuados.append((score, ass_r, entrada.get('categorias', [])))
    pontuados.sort(key=lambda x: -x[0])
    return [(a, c) for _, a, c in pontuados[:n]]


# ── Prompts do sistema ────────────────────────────────────────────────────────

def _sistema_ensino(gabarito_txt: str, resumo_txt: str) -> str:
    return f"""{_SISTEMA}

---

{gabarito_txt}

---

{resumo_txt}

---

## Modo sessao de ensino — regras de comportamento

Voce esta numa conversa de ensino com Michel, especialista de negocio da Finaud.

**Ao analisar cada e-mail:**
1. Explique o que ve: assunto, remetente, anexos, corpo.
2. Diga qual e a duvida especifica que te impediu de classificar.
3. Diga o que precisaria saber para classificar com confianca.

**Ao receber uma regra nova de Michel:**
1. Verifique se ela contradiz algum exemplo do gabarito acima.
2. Verifique se ela poderia reclassificar threads do baseline que estao corretas.
3. Se houver conflito ou risco de regressao:
   CONFLITO: a regra nova contradiz [ID] / afeta o baseline de [categoria].
   Proposta para atender os dois casos: [reformulacao que cobre ambos].
   Confirma esta proposta antes de salvarmos?
4. Se nao houver conflito: propor formulacao final e encerrar com:
   PRONTO PARA SALVAR — digite salvar para gravar ou continue conversando.

**Seja direto e objetivo. Sem texto desnecessario.**
"""


def _sistema_pre(gabarito_txt: str, resumo_txt: str) -> str:
    return f"""{_SISTEMA}

---

{gabarito_txt}

---

{resumo_txt}

---

## Modo pre-classificacao

Analise o e-mail e retorne JSON com esta estrutura exata:

{{
  "confianca": "alta" | "baixa",
  "categorias": ["CATEGORIA"],
  "motivo": "explicacao curta",
  "conflito_id": null | "G-DDR-001",
  "conflito_descricao": null | "descricao do conflito",
  "alternativa": null | "proposta que atende novo e antigo caso"
}}

- "alta": voce classifica com seguranca usando gabarito ou spec — sem duvida.
- "baixa": ha ambiguidade, falta de sinal, ou o caso nao se encaixa claramente.
- "conflito_id": preencha se a classificacao contradiz um exemplo do gabarito.
- "alternativa": preencha quando houver conflito — proponha reformulacao que cubra ambos.
"""


# ── Gabarito — ID, impacto e salvamento ──────────────────────────────────────

def _proximo_num_gabarito(gabarito: dict, prefixo_cat: str) -> int:
    """Retorna o próximo número sequencial de gabarito para a categoria indicada."""
    nums = []
    for g in gabarito.get('gabaritos', []):
        gid = g.get('id', '')
        if gid.startswith(prefixo_cat):
            partes = gid.split(' - ')
            try:
                nums.append(int(partes[1].replace('Gabarito ', '')))
            except (ValueError, IndexError):
                pass
    return (max(nums) + 1) if nums else 1


def _verificar_impacto(novo: dict, registro: dict) -> list:
    """
    Verifica quais threads 'confirmada' seriam afetadas pelo novo gabarito.
    Usa sobreposicao de palavras entre o por_que_gabarito e os assuntos confirmados.
    """
    cats_novo = novo.get('categorias', [])
    if isinstance(cats_novo, str):
        cats_novo = [cats_novo]
    por_que = novo.get('por_que_gabarito', '').lower()
    assunto_ex = novo.get('assunto_exemplo', '').lower()

    stop   = {'a', 'e', 'o', 'de', 'no', 'na', 'ou', 'em', 'do', 'da'}
    afetadas = []
    for tid, entrada in registro['threads'].items():
        if entrada.get('status_regra') != 'confirmada':
            continue
        assunto         = entrada.get('assunto', '').lower()
        palavras_regra  = set(por_que.split() + assunto_ex.split()) - stop
        palavras_ass    = set(assunto.split())
        overlap         = palavras_regra & palavras_ass
        if len(overlap) >= 2:
            afetadas.append({
                'assunto':     entrada.get('assunto', ''),
                'cats_atuais': entrada.get('categorias', []),
                'cats_novo':   cats_novo,
                'regra_era':   entrada.get('regra_usada', ''),
                'overlap':     sorted(overlap),
            })
    return afetadas


def _confirmar_impacto(afetadas: list, novo_id: str) -> bool:
    if not afetadas:
        return True

    print(f'\n  A regra {novo_id} pode afetar {len(afetadas)} thread(s) ja confirmadas:\n')
    for a in afetadas[:10]:
        mudanca = '(sem mudanca de categoria)' if set(a['cats_atuais']) == set(a['cats_novo']) else \
                  f'{a["cats_atuais"]} -> {a["cats_novo"]}'
        print(f'  • {a["assunto"][:60]}')
        print(f'    Confirmada via {a["regra_era"]} | {mudanca}')
    if len(afetadas) > 10:
        print(f'  ... e mais {len(afetadas)-10} threads.')

    print('\nDeseja reclassificar as afetadas? (s = sim / n = nao / c = cancelar salvar)')
    escolha = input().strip().lower()
    if escolha in ('c', 'cancelar'):
        print('Salvamento cancelado.')
        return False
    if escolha in ('s', 'sim', 'yes'):
        print(f'  {len(afetadas)} threads marcadas — serao revisadas na proxima sessao.')
    else:
        print('Ok — threads existentes permanecem com a classificacao atual.')
    return True


def _salvar_gabarito(gabarito: dict, novo: dict, registro: dict) -> bool:
    afetadas = _verificar_impacto(novo, registro)
    if not _confirmar_impacto(afetadas, novo['id']):
        return False

    gabarito.setdefault('gabaritos', []).append(novo)
    gabarito['atualizado'] = datetime.now().strftime('%Y-%m-%d')
    with open(CAMINHO_GAB, 'w', encoding='utf-8') as f:
        json.dump(gabarito, f, ensure_ascii=False, indent=2)
    print(f'\nGabarito {novo["id"]} salvo.\n')
    return True


# ── FASE 1 — Pre-classificacao automatica ─────────────────────────────────────

def _pre_classificar(fila: list, sistema: str, por_assunto: dict,
                     indices: dict, registro: dict) -> list:
    avaliados = []
    total     = len(fila)

    for i, caso in enumerate(fila, 1):
        assunto = caso['assunto']
        thread  = caso['thread']
        indice  = indices.get(assunto)
        email   = _formatar_email(thread, indice)
        similares = _buscar_casos_similares(assunto, registro)

        msg_user = f'Analise este caso:\n\n{email}'
        if similares:
            msg_user += '\n\nCasos similares no baseline:'
            for ass, cats in similares:
                msg_user += f'\n  • {ass[:65]} -> {cats}'

        print(f'  [{i:02d}/{total}] {assunto[:55]}', end=' ', flush=True)

        resp = cliente.chat.completions.create(
            model='gpt-4o-mini',
            temperature=0,
            max_tokens=300,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': sistema},
                {'role': 'user',   'content': msg_user},
            ]
        )
        resultado = json.loads(resp.choices[0].message.content)
        conf = resultado.get('confianca', 'baixa')
        cats = resultado.get('categorias', [])
        print(f'-> {conf.upper()} {cats}')

        avaliados.append({
            'caso':               caso,
            'confianca':          conf,
            'categorias':         cats,
            'motivo':             resultado.get('motivo', ''),
            'conflito_id':        resultado.get('conflito_id'),
            'conflito_descricao': resultado.get('conflito_descricao'),
            'alternativa':        resultado.get('alternativa'),
        })

    return avaliados


# ── FASE 2 — Revisao do lote ──────────────────────────────────────────────────

def _e_suspeito(a: dict) -> bool:
    """Detecta casos com CADOC+SUPORTE misturados ou categorias vazias."""
    cats = a.get('categorias', [])
    if not cats:
        return True
    cadocs = {c for c in cats if c != 'SUPORTE'}
    return bool(cadocs and 'SUPORTE' in cats)


def _revisar_lote(avaliados: list) -> tuple[list, list]:
    claros     = [a for a in avaliados if a['confianca'] == 'alta' and not a['conflito_id']]
    imprecisos = [a for a in avaliados if a['confianca'] != 'alta' or a['conflito_id']]
    suspeitos  = [a for a in claros if _e_suspeito(a)]
    limpos     = [a for a in claros if not _e_suspeito(a)]

    print(f'\n{"=" * 58}')
    print(f'FASE 2 - REVISAO DO LOTE')
    print(f'  OK Alta confianca (limpos):  {len(limpos)} casos')
    print(f'  ?? Suspeitos (revisar):      {len(suspeitos)} casos')
    print(f'  ?? Baixa confianca:          {len(imprecisos)} casos')
    print(f'{"=" * 58}\n')

    if suspeitos:
        print('Casos suspeitos (CADOC+SUPORTE misturado ou categoria vazia):')
        for a in suspeitos:
            rotulo = 'REGRESSAO' if a['caso']['tipo'] == 'REGRESSAO' else 'INCERTO'
            print(f'  {rotulo} | {a["categorias"]} | {a["caso"]["assunto"][:50]}')
        print()

    if limpos:
        print('Casos limpos (alta confianca sem problema):')
        for i, a in enumerate(limpos, 1):
            rotulo = 'REGRESSAO' if a['caso']['tipo'] == 'REGRESSAO' else 'INCERTO'
            print(f'  [{i:02d}] {rotulo} | {a["categorias"]} | {a["caso"]["assunto"][:45]}')

    print()
    print('O que deseja?')
    print('  s / sim  -> aprovar limpos em lote + revisar suspeitos na conversa')
    print('  t / tudo -> revisar todos um a um')
    print('  pular    -> pular lote inteiro, ir para os imprecisos')
    print()
    print('Escolha: ', end='')
    escolha = input().strip().lower()

    if escolha in ('s', 'sim', 'yes', 'aprovar'):
        print(f'\nOK {len(limpos)} casos aprovados em lote.')
        if suspeitos:
            print(f'{len(suspeitos)} suspeitos adicionados a fila de conversa.')
        return limpos, suspeitos + imprecisos
    elif escolha in ('pular', 'p', 'skip'):
        print('\nLote pulado. Indo para os imprecisos.')
        return [], imprecisos
    else:
        print('\nOk, vou incluir todos na fila de conversa.')
        return [], claros + imprecisos


# ── FASE 3 — Conversa com os imprecisos ──────────────────────────────────────

def _chat(email_txt: str, similares: list, sistema: str,
          conflito_pre: str = None, alternativa_pre: str = None) -> dict | None:
    """
    Conversa multi-turno sobre um caso.
    Retorna dict com gabarito formulado, None (pular) ou 'SAIR'.
    """
    msg_inicial = f'Analise este e-mail e explique seu raciocinio:\n\n{email_txt}'

    if similares:
        msg_inicial += '\n\nCasos similares ja classificados corretamente:'
        for ass, cats in similares:
            msg_inicial += f'\n  • {ass[:70]} -> {cats}'

    if conflito_pre:
        msg_inicial += (
            f'\n\nNa pre-analise detectei conflito: {conflito_pre}'
            f'\nAlternativa sugerida: {alternativa_pre or "a definir"}'
            f'\nVamos conversar sobre isso.'
        )

    historico = [
        {'role': 'system', 'content': sistema},
        {'role': 'user',   'content': msg_inicial},
    ]

    _DICA = '\n[salvar = gravar gabarito  |  pular = proximo caso  |  sair = encerrar]\n'

    resp   = cliente.chat.completions.create(
        model='gpt-4o-mini', temperature=0, max_tokens=500,
        messages=historico,
    )
    ia_txt = resp.choices[0].message.content.strip()
    historico.append({'role': 'assistant', 'content': ia_txt})
    print(f'\nIA -> {ia_txt}')
    print(_DICA)

    while True:
        print('Voce -> ', end='', flush=True)
        entrada = input().strip()

        if not entrada:
            continue

        cmd      = entrada.lower()
        cmd_base = cmd.split()[0].rstrip(',.!?;:') if cmd.split() else ''

        if cmd in ('sair', 'q', 'quit') or cmd_base in ('sair', 'quit'):
            return 'SAIR'

        if cmd in ('pular', 'p', 'skip', 'n', 'proximo', 'continuar',
                   'proximo caso') or cmd_base in ('pular', 'proximo', 'skip'):
            return None

        _salvar_palavras = ('salvar', 's', 'save', 'sim', 'yes', 'confirmar', 'gravar')
        if cmd in _salvar_palavras or cmd_base in _salvar_palavras:
            if len(entrada.split()) > 1:
                historico.append({'role': 'user', 'content': entrada})
            historico.append({
                'role': 'user',
                'content': (
                    'Formule o gabarito deste caso. '
                    'Retorne APENAS JSON com:\n'
                    '{\n'
                    '  "categoria": "CATEGORIA",\n'
                    '  "padrao": "descricao curta do padrao",\n'
                    '  "assunto_exemplo": "assunto do e-mail",\n'
                    '  "corpo_tipico": "caracteristica do corpo",\n'
                    '  "regra": "regra em 1-2 frases que generaliza"\n'
                    '}'
                )
            })
            resp = cliente.chat.completions.create(
                model='gpt-4o-mini', temperature=0, max_tokens=350,
                response_format={'type': 'json_object'},
                messages=historico,
            )
            return json.loads(resp.choices[0].message.content)

        historico.append({'role': 'user', 'content': entrada})
        resp   = cliente.chat.completions.create(
            model='gpt-4o-mini', temperature=0, max_tokens=500,
            messages=historico,
        )
        ia_txt = resp.choices[0].message.content.strip()
        historico.append({'role': 'assistant', 'content': ia_txt})
        print(f'\nIA -> {ia_txt}')
        print(_DICA)


# ── Montar fila ───────────────────────────────────────────────────────────────

def _montar_fila(registro: dict, regressoes: list, por_id: dict) -> list:
    """
    Monta a fila de casos para a sessao:
    - Threads com status_regra 'incerta' ou 'sem_categoria' no registro
    - Regressoes detectadas pela ultima amostra de controle
    """
    fila = []

    # Incertas e sem_categoria vem do registro definitivo
    for tid, entrada in registro['threads'].items():
        if entrada['status_regra'] not in ('incerta', 'sem_categoria'):
            continue
        thread = por_id.get(tid)
        if thread:
            fila.append({
                'tipo':      'INCERTO',
                'assunto':   entrada['assunto'],
                'thread':    thread,
                'thread_id': tid,
                'extra':     f'Motivo: {entrada.get("motivo_regra_usada", "")}',
            })

    # Regressoes vem da ultima amostra de controle
    for reg in regressoes:
        assunto = reg.get('assunto', '')
        # Localizar thread_id pelo assunto no registro
        tid_reg = next((tid for tid, e in registro['threads'].items()
                        if e.get('assunto') == assunto), '')
        thread  = por_id.get(tid_reg)
        if thread:
            fila.append({
                'tipo':      'REGRESSAO',
                'assunto':   assunto,
                'thread':    thread,
                'thread_id': tid_reg,
                'extra':     f'Era: {reg.get("antes",[])} -> Agora: {reg.get("agora",[])}',
            })

    return fila


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print('\nSESSAO DE ENSINO — Oraculo 360 Finaud')
    print('=' * 58)
    print('Carregando contexto...')

    gabarito                  = carregar_gabarito()
    registro                  = carregar_registro()
    por_assunto, por_id, indices = carregar_threads()
    regressoes                = carregar_regressoes()
    fila                      = _montar_fila(registro, regressoes, por_id)

    gab_txt    = _formatar_gabarito_completo(gabarito)
    resumo_txt = _resumo_classificacoes(registro)
    sis_pre    = _sistema_pre(gab_txt, resumo_txt)
    sis_ensino = _sistema_ensino(gab_txt, resumo_txt)

    res = registro['resumo']
    print(f'  Registro: {res["total"]} threads')
    print(f'    Confirmadas: {res["confirmadas"]}  |  Pendentes: {res.get("incertas",0)}')
    print(f'  Gabarito: {len(gabarito.get("exemplos",[]))} exemplos')
    print(f'  Regressoes detectadas: {len(regressoes)}')
    print(f'  Total na fila: {len(fila)} casos\n')

    # ── FASE 1 ────────────────────────────────────────────────────────────────
    print('-' * 58)
    print('FASE 1 — Pre-classificando todos os casos...')
    print('-' * 58)
    avaliados = _pre_classificar(fila, sis_pre, por_assunto, indices, registro)

    # ── FASE 2 ────────────────────────────────────────────────────────────────
    _, imprecisos = _revisar_lote(avaliados)

    if not imprecisos:
        print('\nNenhum caso impreciso. Sessao concluida.')
        return

    # ── FASE 3 ────────────────────────────────────────────────────────────────
    print(f'\n{"-" * 58}')
    print(f'FASE 3 — Conversa com {len(imprecisos)} casos')
    print(f'{"-" * 58}')
    print('Comandos: salvar / pular / sair\n')

    salvos  = 0
    pulados = 0

    for i, aval in enumerate(imprecisos, 1):
        caso      = aval['caso']
        assunto   = caso['assunto']
        thread    = caso['thread']
        thread_id = caso.get('thread_id', '')
        indice    = indices.get(assunto)

        email_txt = _formatar_email(thread, indice)
        similares = _buscar_casos_similares(assunto, registro)

        rotulo = 'REGRESSAO' if caso['tipo'] == 'REGRESSAO' else 'INCERTO'
        print(f'\n{"-" * 58}')
        print(f'[{i}/{len(imprecisos)}] {rotulo}')
        print(f'{assunto[:58]}')
        print(f'{caso["extra"]}')
        if aval.get('conflito_id'):
            print(f'Conflito detectado: {aval["conflito_id"]} — {aval["conflito_descricao"]}')
            print(f'  Alternativa pre-sugerida: {aval.get("alternativa","—")}')
        print(f'{"-" * 58}')

        resultado = _chat(
            email_txt, similares, sis_ensino,
            conflito_pre    = aval.get('conflito_descricao'),
            alternativa_pre = aval.get('alternativa'),
        )

        if resultado == 'SAIR':
            break

        if resultado is None:
            pulados += 1
            continue

        cats    = resultado.get('categorias', ['SUPORTE'])
        if isinstance(cats, str):
            cats = [cats]
        sigla_cat   = cats[0].split('_')[0] if cats else 'X'
        prefixo_cat = f'{sigla_cat} - '
        num         = _proximo_num_gabarito(gabarito, prefixo_cat)
        por_que     = resultado.get('por_que_gabarito', resultado.get('regra', ''))
        novo_id     = f'{sigla_cat} - Gabarito {num:02d} - {resultado.get("titulo_curto", assunto[:30])}'

        print('Formulacao proposta:')
        print(f'  ID:        {novo_id}')
        print(f'  Categorias:{cats}')
        print(f'  Assunto:   {resultado.get("assunto_exemplo", assunto)[:60]}')
        print(f'  Por que:   {por_que[:80]}')
        print()
        print('Confirma salvar? (s/n): ', end='')

        if input().strip().lower() in ('s', 'sim', 'y', 'yes'):
            novo = {
                'id':               novo_id,
                'categorias':       cats,
                'regra_base':       resultado.get('regra_base', ''),
                'assunto_exemplo':  resultado.get('assunto_exemplo', assunto),
                'por_que_gabarito': por_que,
                'confirmado_por':   'Michel',
                'data':             datetime.now().strftime('%Y-%m-%d'),
            }
            if _salvar_gabarito(gabarito, novo, registro):
                if thread_id:
                    confirmar_no_registro(
                        registro, thread_id, assunto, cats,
                        novo_id, por_que[:120]
                    )
                salvos += 1
        else:
            print('Nao salvo. Proximo.\n')
            pulados += 1

    print(f'\n{"=" * 58}')
    print('Sessao encerrada.')
    print(f'  Salvos:  {salvos} novos gabaritos')
    print(f'  Pulados: {pulados}')

    res = registro['resumo']
    print(f'\nRegistro atualizado:')
    print(f'  Confirmadas: {res["confirmadas"]}')
    pendentes = res.get('incertas', 0) + res.get('sem_categoria', 0)
    print(f'  Pendentes:   {pendentes}')
    if pendentes == 0:
        print('\nTodas as threads foram classificadas!')
    elif salvos > 0:
        print('\nProximos passos:')
        print('  1. Rodar amostra de controle')
        print('  2. Se aprovada (0 regressoes reais): commitar com tag')


if __name__ == '__main__':
    main()
