"""
validador_classificacao.py
O que faz: roda o classificador IA em todos os threads válidos da base
           e gera relatório para identificar lacunas na especificação §10.
Entrada:   data/json/pipeline/01_extração_dados_brutos_gmail.json
Saída:     data/validacao_classificacao/YYYYMMDD_HHMM_resultados.jsonl
           data/validacao_classificacao/YYYYMMDD_HHMM_relatorio.txt
"""

import os
import sys
import json
import re
import time
import argparse
from datetime import datetime
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from classificador_regras import classificar_thread

load_dotenv()

# ── Caminhos ──────────────────────────────────────────────────────────────────

BASE_DIR        = Path(__file__).parent.parent
CAMINHO_THREADS = BASE_DIR / 'data' / 'json' / 'pipeline' / '01_extração_dados_brutos_gmail.json'
DIR_SAIDA       = BASE_DIR / 'data' / 'validacao_classificacao'
LOCK_FILE       = DIR_SAIDA / 'validacao.lock'

# ── Filtros §4 — mesma lógica que o coletor aplicará em produção ───────────────

_ENDERECOS_EXATOS = {
    'riskdriver@finaud.com.br',
    'contato@finaud.com.br',
    'coleta.oraculo@finaud.com.br',
    'do-not-reply@finaud.fogbugz.com',
    'comunicacao@comunicacao.bcb.gov.br',
}

_PADROES_ENDERECO = re.compile(
    r'noreply|no-reply|mailer-daemon|newsletter|notification|bounce',
    re.IGNORECASE
)

_DOMINIOS_BLOQUEADOS = {
    'employer.com.br', 'content.pwc.com', 'grafana.com',
    'eadtiexames.com.br', 'appsheet.com', 'freshworks.com', 'nasajon.com.br',
}

_NOMES_REDES_SOCIAIS = re.compile(
    r'\b(Facebook|Meta|Instagram|LinkedIn|Twitter|YouTube|Telegram|WhatsApp)\b',
    re.IGNORECASE
)


def _extrair_email_e_nome(remetente: str) -> tuple[str, str]:
    """Extrai (nome, email) do campo remetente no formato 'Nome <email>' ou só 'email'."""
    m = re.match(r'^(.*?)\s*<([^>]+)>', remetente.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip().lower()
    return '', remetente.strip().lower()


def _dominio(email: str) -> str:
    return email.split('@')[-1] if '@' in email else ''


def eh_automatico(thread: dict) -> str | None:
    """Retorna o motivo do filtro §4 se automático, None se deve ir para a IA."""
    msg0    = thread.get('mensagens', [{}])[0] if thread.get('mensagens') else {}
    rem     = msg0.get('remetente', '')
    assunto = thread.get('assunto', '')
    nome, email = _extrair_email_e_nome(rem)
    dominio = _dominio(email)

    if email in _ENDERECOS_EXATOS:
        return f'endereço exato: {email}'
    if _PADROES_ENDERECO.search(email):
        return f'padrão no endereço: {email}'
    if dominio in _DOMINIOS_BLOQUEADOS:
        return f'domínio bloqueado: {dominio}'
    if _NOMES_REDES_SOCIAIS.search(nome):
        return f'rede social: {nome}'
    if '3CX Communications System' in nome:
        return '3CX chamada perdida'
    if 'FINAUDTEC' in nome and 'FogBugz' in assunto:
        return 'ticket FogBugz interno'
    if 'Finaud Equipe' in nome and 'Confirma' in assunto:
        return 'confirmação de conta Finaud'
    if 'IT Service Desk' in assunto:
        return 'IT Service Desk'
    if assunto.startswith('Aceito:'):
        return 'aceite de convite de calendário'
    assunto_u = assunto.upper()
    if any(p in assunto_u for p in ('CÓDIGO DE VERIFICAÇÃO', 'CODIGO DE VERIFICACAO',
                                     'CÓDIGO DE ACESSO', 'CODIGO DE ACESSO',
                                     'VERIFICATION CODE', 'CÓDIGO DE SEGURANÇA',
                                     'CODIGO DE SEGURANCA')):
        return 'código de verificação automático'
    if any(p in nome for p in ('via Microsoft', 'via Google', 'via LinkedIn', 'via Apple')):
        return f'notificação automática de plataforma: {nome}'
    return None


# ── Camada 1: trava de processo único ─────────────────────────────────────────

def _processo_ativo(pid: int) -> bool:
    """Verifica se um PID ainda está rodando (Windows)."""
    try:
        import subprocess
        r = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
            capture_output=True, text=True, timeout=5
        )
        return str(pid) in r.stdout
    except Exception:
        return False


def _adquirir_lock():
    """Bloqueia se já existe outro processo ativo; grava PID no lock."""
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
        except ValueError:
            pid = None
        if pid and _processo_ativo(pid):
            print(f'\n❌ Já existe um processo rodando (PID {pid}).')
            print(f'   Aguarde ele terminar antes de iniciar outra rodada.')
            print(f'   Para forçar (apenas se tiver certeza), apague: {LOCK_FILE}')
            sys.exit(1)
        print(f'⚠️  Lock órfão (PID {pid} não existe mais). Limpando...')
        LOCK_FILE.unlink()
    LOCK_FILE.write_text(str(os.getpid()))
    print(f'🔒 Processo registrado (PID {os.getpid()})')


def _liberar_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


# ── Execução principal ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resumir', metavar='ARQUIVO.jsonl',
                        help='Retoma de um arquivo parcial — pula threads já processadas')
    parser.add_argument('--filtrar-ids', metavar='ARQUIVO.txt',
                        help='Processa só as threads cujos IDs estão no arquivo (um por linha)')
    args = parser.parse_args()

    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    _adquirir_lock()  # Camada 1 — impede segundo processo

    # Modo retomar: usa o mesmo arquivo e pula o que já foi feito
    if args.resumir:
        arq_resultados = Path(args.resumir)
        ja_feitos = set()
        resultados_anteriores = []
        if arq_resultados.exists():
            for linha in arq_resultados.read_text(encoding='utf-8').splitlines():
                if linha.strip():
                    r = json.loads(linha)
                    tid = r.get('thread_id', '')
                    ja_feitos.add(tid)
                    if tid not in {x['thread_id'] for x in resultados_anteriores}:
                        resultados_anteriores.append(r)  # sem duplicatas
        print(f'Retomando {arq_resultados.name} — {len(ja_feitos)} threads já feitas')
        ts = arq_resultados.stem.replace('_resultados', '')
    else:
        ts = datetime.now().strftime('%Y%m%d_%H%M')
        arq_resultados = DIR_SAIDA / f'{ts}_resultados.jsonl'
        ja_feitos = set()
        resultados_anteriores = []

    arq_relatorio  = DIR_SAIDA / f'{ts}_relatorio.txt'
    arq_concluido  = DIR_SAIDA / f'{ts}_concluido.txt'

    ids_alvo = None
    if args.filtrar_ids:
        ids_alvo = set(Path(args.filtrar_ids).read_text(encoding='utf-8').split())
        print(f'Modo filtrado: {len(ids_alvo)} threads-alvo de {args.filtrar_ids}')

    try:
      _executar(ts, arq_resultados, arq_relatorio, arq_concluido, ja_feitos, resultados_anteriores, ids_alvo)
    finally:
      _liberar_lock()  # Camada 1 — sempre libera, mesmo com erro


def _executar(ts, arq_resultados, arq_relatorio, arq_concluido, ja_feitos, resultados_anteriores, ids_alvo=None):
    print(f'Carregando threads de:\n  {CAMINHO_THREADS}\n')
    with open(CAMINHO_THREADS, encoding='utf-8') as f:
        todos = json.load(f)
    print(f'Total carregado: {len(todos)} threads')

    validos   = []
    filtrados = []
    for t in todos:
        motivo = eh_automatico(t)
        if motivo:
            filtrados.append((t, motivo))
        else:
            validos.append(t)

    if ids_alvo is not None:
        validos = [t for t in validos if t.get('thread_id', '') in ids_alvo]
        print(f'Filtro de IDs aplicado: {len(validos)} threads no subconjunto')

    print(f'Filtrados (§4): {len(filtrados)} | Válidos para IA: {len(validos)}\n')

    # Excluir threads já processadas no modo retomar
    pendentes = [t for t in validos if t.get('thread_id', '') not in ja_feitos]
    print(f'Já processadas: {len(ja_feitos)} | Pendentes: {len(pendentes)}\n')

    cliente    = OpenAI()
    resultados = list(resultados_anteriores)
    erros      = []

    print(f'Iniciando classificação de {len(pendentes)} threads...\n')

    for i, thread in enumerate(pendentes, 1):
        assunto   = thread.get('assunto', '')
        msg0      = thread.get('mensagens', [{}])[0] if thread.get('mensagens') else {}
        remetente = msg0.get('remetente', '')

        try:
            resultado = classificar_thread(thread, cliente)
            resultado['thread_id'] = thread.get('thread_id', '')
            resultado['assunto']   = assunto
            resultado['remetente'] = remetente
            resultado['erro']      = None

        except Exception as e:
            if getattr(e, 'status_code', None) == 429:
                print(f'  [!] Rate limit na thread {i} — aguardando 60s...')
                time.sleep(60)
                try:
                    resultado = classificar_thread(thread, cliente)
                    resultado['thread_id'] = thread.get('thread_id', '')
                    resultado['assunto']   = assunto
                    resultado['remetente'] = remetente
                    resultado['erro']      = None
                except Exception as e2:
                    resultado = _resultado_erro(thread, str(e2))
                    erros.append(resultado)
            else:
                resultado = _resultado_erro(thread, str(e))
                erros.append(resultado)

        resultados.append(resultado)

        # Salvar incrementalmente — se interromper, o que foi feito não se perde
        with open(arq_resultados, 'a', encoding='utf-8') as f:
            f.write(json.dumps(resultado, ensure_ascii=False) + '\n')

        if i % 10 == 0 or i == len(pendentes):
            incertos_agora = sum(1 for r in resultados if r.get('incerto'))
            print(f'  [{i:>3}/{len(validos)}]  incertos até agora: {incertos_agora}')

        time.sleep(0.3)

    _gerar_relatorio(arq_relatorio, resultados, filtrados, erros, len(todos))

    # Camada 2 — arquivo de conclusão: prova positiva de que terminou
    unicos = len({r['thread_id'] for r in resultados})
    arq_concluido.write_text(
        f'Concluído: {datetime.now().strftime("%d/%m/%Y %H:%M")}\n'
        f'Threads únicas processadas: {unicos}\n'
        f'Erros: {len(erros)}\n',
        encoding='utf-8'
    )

    print(f'\n✅ Concluído!')
    print(f'   Resultados : {arq_resultados}')
    print(f'   Relatório  : {arq_relatorio}')
    print(f'   Conclusão  : {arq_concluido}')
    print(f'🔓 Lock liberado.')


def _resultado_erro(thread: dict, msg_erro: str) -> dict:
    msg0 = thread.get('mensagens', [{}])[0] if thread.get('mensagens') else {}
    return {
        'thread_id': thread.get('thread_id', ''),
        'assunto':   thread.get('assunto', ''),
        'remetente': msg0.get('remetente', ''),
        'categorias': [], 'confianca': 'baixa',
        'motivo': '', 'incerto': True,
        'erro': msg_erro[:200],
    }


def _gerar_relatorio(caminho, resultados, filtrados, erros, total_raw):
    alta     = sum(1 for r in resultados if r.get('confianca') == 'alta'  and not r.get('incerto'))
    media    = sum(1 for r in resultados if r.get('confianca') == 'media' and not r.get('incerto'))
    incertos = [r for r in resultados if r.get('incerto')]
    com_erro = [r for r in resultados if r.get('erro')]

    contagem = Counter()
    for r in resultados:
        for cat in r.get('categorias', []):
            contagem[cat] += 1

    sep = '═' * 56
    linhas = [
        sep,
        f'RELATÓRIO DE VALIDAÇÃO — {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        sep,
        '',
        'RESUMO',
        '─' * 56,
        f'{"Total de threads na base:":<38} {total_raw:>4}',
        f'{"Filtradas (§4 — automáticos):":<38} {len(filtrados):>4}',
        f'{"Classificadas pela IA:":<38} {len(resultados):>4}',
        f'  {"• Confiança alta:":<36} {alta:>4}',
        f'  {"• Confiança média:":<36} {media:>4}',
        f'  {"• Incertas / sem categoria:":<36} {len(incertos):>4}',
        f'{"Erros de API:":<38} {len(com_erro):>4}',
        '',
        'DISTRIBUIÇÃO POR CATEGORIA',
        '─' * 56,
    ]

    for cat, n in sorted(contagem.items(), key=lambda x: -x[1]):
        pct = n / len(resultados) * 100 if resultados else 0
        linhas.append(f'  {cat:<22} {n:>4}   ({pct:>5.1f}%)')

    linhas += [
        '',
        f'THREADS INCERTAS — POSSÍVEIS LACUNAS DA SPEC  ({len(incertos)})',
        '─' * 56,
    ]
    for i, r in enumerate(incertos, 1):
        linhas.append(f'{i:>3}. "{r["assunto"]}"')
        linhas.append(f'     Motivo: {r["motivo"]}')
        linhas.append('')

    if com_erro:
        linhas += ['', 'ERROS DE API', '─' * 56]
        for r in com_erro:
            linhas.append(f'  "{r["assunto"]}"')
            linhas.append(f'  Erro: {r["erro"]}')
            linhas.append('')

    texto = '\n'.join(linhas)
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(texto)

    print('\n' + texto)


if __name__ == '__main__':
    main()
