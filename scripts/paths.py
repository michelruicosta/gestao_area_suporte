"""
Caminhos centrais do projecto GESTÃO ÁREA SUPORTE.

Importar em qualquer script:
    from paths import PIPELINE_DIR, PAINEL_DIR, CONFIG_DIR, BACKUPS_DIR
    from paths import F_EMAILS_BRUTOS, F_EMAILS_CLASS, F_INTEGRADOR, ...
    from paths import load_aguardando, save_aguardando
    from paths import load_concluidas, save_concluidas

Estrutura de data/json/:
  pipeline/      — gerado pela carga; apagável com ``deletar_carga``
                   (integrador 03, threads aguardando/concluídas, **pares confirmados Gmail**, …)
  painel_estado/ — apenas persistência auxiliar sobrevivente (**cartao_overrides**)
  config/        — regras + **cadastro de clientes**, **rótulos de empresa** (manutenção futura UI)
  _backups/      — cópias; pode limpar periodicamente

Na primeira importação, cópias defensivas a partir dos antigos paths em ``painel_estado/``
(``cadastro_*``, ``rotulos_*``, ``pares_threads_*``) se o destino novo ainda não existir.

--- STATUS DOS FIOS (Aguardando / Concluídas) ---

Cada status é gravado em UM arquivo único dentro de pipeline/:
  threads_aguardando_auto.json    — todos os registros aguardando
  threads_concluidas_auto.json    — todos os registros concluídos

O código deve usar SEMPRE as funções ``load_*`` / ``save_*``.
O status PENDENTE é derivado (fio sem registo em nenhum dos arquivos).

``deletar_carga.py`` apaga ``pipeline/`` inteiro — inclui **pares confirmados**.
"""
import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PIPELINE_DIR    = os.path.join(BASE_DIR, "data", "json", "pipeline")
PAINEL_DIR      = os.path.join(BASE_DIR, "data", "json", "painel_estado")
CONFIG_DIR      = os.path.join(BASE_DIR, "data", "json", "config")
BACKUPS_DIR     = os.path.join(BASE_DIR, "data", "json", "_backups")
BACKUPS_AUTO_DIR = os.path.join(BACKUPS_DIR, "auto")

# ── PIPELINE ──────────────────────────────────────────────────────────────────
F_EMAILS_BRUTOS     = os.path.join(PIPELINE_DIR, "01_extração_dados_brutos_gmail.json")
F_EMAILS_CLASS      = os.path.join(PIPELINE_DIR, "02_classificação_dados_brutos_gmail_editado.json")
F_INTEGRADOR        = os.path.join(PIPELINE_DIR, "03_integrador_dados_site.json")
F_INTEGRADOR_BACKUP = os.path.join(BACKUPS_DIR,  "03_integrador_dados_site.json.backup")
F_FOG               = os.path.join(PIPELINE_DIR, "massa_bruta_fog.json")
F_CHAT              = os.path.join(PIPELINE_DIR, "massa_bruta_chat.json")
F_CACHE_IMAGENS     = os.path.join(PIPELINE_DIR, "cache_texto_imagens_validado.json")
F_CACHE_RESUMOS_LLM = os.path.join(PIPELINE_DIR, "cache_resumos_llm.json")
F_CORRELACOES       = os.path.join(PIPELINE_DIR, "correlacoes.json")
F_CRD                = os.path.join(PIPELINE_DIR, "crd_indicio_qualidade.json")
F_INDICIOS_QUALIDADE = os.path.join(CONFIG_DIR,   "indicios_qualidade.json")
F_FERIADOS          = os.path.join(PIPELINE_DIR, "calendario_feriados.json")
F_CONSUMO_API       = os.path.join(PIPELINE_DIR, "consumo_api.json")
F_REGISTROS_FOG     = os.path.join(PIPELINE_DIR, "registros_id_emails_de_envios_ao_fog.json")
F_DIARIO            = os.path.join(PIPELINE_DIR, "diario_agente.json")
F_MEMORIA_THREADS   = os.path.join(PIPELINE_DIR, "memoria_threads.json")
F_BASE_CONHECIMENTO_RB = os.path.join(PIPELINE_DIR, "base_conhecimento_retorno_bacen.json")

# ── STATUS DOS FIOS (em pipeline/, apagados a cada nova carga) ───────────────
F_AGUARDANDO_AUTO    = os.path.join(PIPELINE_DIR, "threads_aguardando_auto.json")
F_CONCLUIDAS_AUTO    = os.path.join(PIPELINE_DIR, "threads_concluidas_auto.json")

# ── Pares confirmados Gmail (pipeline — apaga com ``deletar_carga``) ─────────────
F_PARES_THREADS = os.path.join(PIPELINE_DIR, "pares_threads_confirmados.json")

# ── Cadastro clientes CADOC + rótulos gestão (config — manutenção futura UI) ───
F_ROTULOS = os.path.join(CONFIG_DIR, "rotulos_empresa_gestao.json")
F_CADASTRO_CLIENTES = os.path.join(CONFIG_DIR, "cadastro_clientes_cadoc.json")

# ── Overrides manuais cartão por thread (painel_estado — fora da pipeline)
F_CARTAO_OVERRIDES = os.path.join(PAINEL_DIR, "cartao_overrides.json")

# ── CONFIG ────────────────────────────────────────────────────────────────────
F_MAPEAMENTO        = os.path.join(CONFIG_DIR, "mapeamento_regras_negocio.json")
F_CRITERIOS_FOG     = os.path.join(CONFIG_DIR, "criterios_ia_de_alertas_fog.json")
F_DESTINATARIOS_FOG = os.path.join(CONFIG_DIR, "destinatarios_alertas_fog.json")
F_USUARIOS          = os.path.join(CONFIG_DIR, "usuarios.json")
F_PROMPTS_LLM       = os.path.join(CONFIG_DIR, "prompts_llm.json")

for _d in (PIPELINE_DIR, PAINEL_DIR, CONFIG_DIR, BACKUPS_DIR):
    os.makedirs(_d, exist_ok=True)


def _migrar_copia_legados_painel_estado_so_se_destino_ausente() -> None:
    """Se ainda só existirem cópias em ``painel_estado/``, copia para pipeline/config uma vez."""
    legado = os.path.join(PAINEL_DIR, "pares_threads_confirmados.json")
    try:
        if os.path.isfile(legado) and not os.path.isfile(F_PARES_THREADS):
            shutil.copy2(legado, F_PARES_THREADS)
    except OSError:
        pass
    for nome, dest in (
        ("cadastro_clientes_cadoc.json", F_CADASTRO_CLIENTES),
        ("rotulos_empresa_gestao.json", F_ROTULOS),
    ):
        src = os.path.join(PAINEL_DIR, nome)
        try:
            if os.path.isfile(src) and not os.path.isfile(dest):
                shutil.copy2(src, dest)
        except OSError:
            pass


_migrar_copia_legados_painel_estado_so_se_destino_ausente()


# ── HELPERS: leitura/gravação unificada de aguardando/concluídas ─────────────

def _load_list(path: str) -> list:
    """Lê uma lista JSON; devolve [] se ficheiro não existir ou estiver inválido."""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_list(path: str, lista: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)



def load_aguardando() -> list:
    """Devolve a lista de fios em aguardando (arquivo único unificado)."""
    return _load_list(F_AGUARDANDO_AUTO)


def save_aguardando(lista: list) -> None:
    """Grava todos os fios aguardando no arquivo único."""
    _save_list(F_AGUARDANDO_AUTO, lista)


def load_concluidas() -> list:
    """Devolve a lista de fios concluídos (arquivo único unificado)."""
    return _load_list(F_CONCLUIDAS_AUTO)


def save_concluidas(lista: list) -> None:
    """Grava todos os fios concluídos no arquivo único."""
    _save_list(F_CONCLUIDAS_AUTO, lista)


def load_cartao_overrides() -> dict:
    """Lê mapa threadId -> { cadoc?, status? } — ficheiro em painel_estado/ (persistente)."""
    if not os.path.isfile(F_CARTAO_OVERRIDES):
        return {}
    try:
        with open(F_CARTAO_OVERRIDES, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cartao_overrides(d: dict) -> None:
    os.makedirs(os.path.dirname(F_CARTAO_OVERRIDES) or ".", exist_ok=True)
    with open(F_CARTAO_OVERRIDES, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ── UTILITÁRIOS DE DATA (#50) ────────────────────────────────────────────────
#
# Função centralizada de parse de data para o pipeline.
# Aceita os formatos mais comuns encontrados nos e-mails e JSONs do sistema.

from datetime import date as _date, datetime as _datetime
from email.utils import parsedate_to_datetime as _parsedate_rfc2822

def parse_data_flexivel(valor) -> "_date | None":
    """
    Tenta interpretar ``valor`` como uma data, aceitando múltiplos formatos:
      - RFC 2822  : "Mon, 23 Feb 2026 11:00:43 +0000"  (e-mails Gmail)
      - ISO       : "2026-02-23" ou "2026-02-23T11:00:43"
      - BR        : "23/02/2026" ou "23/02/26"
      - Epoch int : 1740312043  (timestamp_epoch)

    Retorna um objeto ``date`` ou None se nenhum formato funcionar.
    Nunca lança exceção.
    """
    if valor is None:
        return None
    # Epoch numérico
    if isinstance(valor, (int, float)):
        try:
            return _datetime.fromtimestamp(int(valor)).date()
        except (OSError, ValueError, OverflowError):
            return None
    s = str(valor).strip()
    if not s:
        return None
    # RFC 2822 (e-mails Gmail)
    try:
        return _parsedate_rfc2822(s).date()
    except Exception:
        pass
    # ISO: YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS
    try:
        return _date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        pass
    # BR: DD/MM/YYYY ou DD/MM/YY
    if "/" in s:
        partes = s.split("/")
        if len(partes) >= 3:
            try:
                d, m, a = int(partes[0]), int(partes[1]), int(partes[2][:4])
                if a < 100:
                    a += 2000
                return _date(a, m, d)
            except (ValueError, IndexError):
                pass
    # Epoch string
    try:
        return _datetime.fromtimestamp(int(s)).date()
    except (OSError, ValueError, OverflowError):
        pass
    return None


# ── BACKUP AUTOMÁTICO DE CARGA ────────────────────────────────────────────────

def backup_pre_carga(rotulo: str = "carga") -> str | None:
    """
    Cria backup dos 5 arquivos críticos do pipeline antes de uma carga.

    Os arquivos são copiados para:
        data/json/_backups/auto/YYYYMMDD_HHMM_<rotulo>/

    Retém os últimos 7 backups automáticos — o mais antigo é apagado.
    Retorna o caminho da pasta criada, ou None se não houver nada para copiar.

    Uso no executar_tudo.py:
        from paths import backup_pre_carga
        backup_pre_carga("carga")
    """
    import shutil as _shutil
    from datetime import datetime as _dt

    arquivos_criticos = [
        F_EMAILS_BRUTOS,   # 01 — e-mails brutos do Gmail
        F_EMAILS_CLASS,    # 02 — classificações de e-mails
        F_INTEGRADOR,      # 03 — base do painel (mais importante)
    ]
    # Arquivos de triagem
    _pipeline = PIPELINE_DIR
    for _nome in (
        "threads_aguardando_auto.json",
        "threads_concluidas_auto.json",
    ):
        arquivos_criticos.append(os.path.join(_pipeline, _nome))

    # Só cria backup se pelo menos um arquivo existir
    existentes = [f for f in arquivos_criticos if os.path.isfile(f)]
    if not existentes:
        return None

    ts = _dt.now().strftime("%Y%m%d_%H%M")
    pasta = os.path.join(BACKUPS_AUTO_DIR, f"{ts}_{rotulo}")
    os.makedirs(pasta, exist_ok=True)

    for src in existentes:
        dest = os.path.join(pasta, os.path.basename(src))
        try:
            _shutil.copy2(src, dest)
        except Exception as e:
            print(f"  [AVISO] Backup nao criado para {os.path.basename(src)}: {e}")

    # Manter apenas os ultimos 7 backups automaticos
    try:
        todas = sorted(
            [d for d in os.scandir(BACKUPS_AUTO_DIR) if d.is_dir()],
            key=lambda d: d.name,
        )
        for antiga in todas[:-7]:
            _shutil.rmtree(antiga.path, ignore_errors=True)
    except Exception:
        pass

    print(f"  [BACKUP] {len(existentes)} arquivos -> {os.path.basename(pasta)}/")
    return pasta


# ── UTILITÁRIOS DE STRINGS COMPARTILHADOS ────────────────────────────────────

from email.header import decode_header as _decode_header

def limpar_nome_arquivo(nome: str) -> str:
    """
    Normaliza o nome de um arquivo para uso seguro no sistema de arquivos.

    Etapas:
      1. Decodifica cabeçalhos MIME encoded (ex: =?utf-8?b?...?=) — comum em
         anexos de e-mail cujo nome foi codificado pelo cliente de e-mail.
      2. Remove caracteres proibidos no Windows (\\/:*?"<>|) substituindo por '_'.
      3. Remove pontos e espaços iniciais/finais.
      4. Limita a 120 caracteres para compatibilidade com sistemas de arquivos.

    Uso: scripts 02, 06, 08 — importar daqui em vez de reimplementar.
    """
    if not nome:
        return "sem_nome"
    # Decodifica MIME encoding (ex: =?utf-8?b?cmVsYXRvcmlvLnBkZg==?=)
    try:
        partes = _decode_header(nome)
        nome_dec = ""
        for conteudo, codificacao in partes:
            if isinstance(conteudo, bytes):
                nome_dec += conteudo.decode(codificacao or "utf-8", errors="replace")
            else:
                nome_dec += str(conteudo)
        nome = nome_dec
    except Exception:
        pass
    # Remove caracteres proibidos no Windows
    for c in '\\/:*?"<>|':
        nome = nome.replace(c, "_")
    nome = nome.strip(". ")
    return nome[:120] if nome else "sem_nome"


# ── REGISTRO DE ESTADO DO PIPELINE (#53) ─────────────────────────────────────
#
# Cada script registra quando terminou e o mtime do arquivo que produziu.
# Isso permite detectar quando um script foi rodado com entrada desatualizada.
#
# Uso:
#   from paths import registrar_execucao, verificar_dependencias
#
#   # No início do main():
#   verificar_dependencias("09_integrar", requer=["05_classificar"])
#
#   # No final do main() (após gravar os arquivos):
#   registrar_execucao("09_integrar", arquivo_saida=F_INTEGRADOR)

import time as _time

F_PIPELINE_ESTADO = os.path.join(PIPELINE_DIR, "pipeline_estado.json")

# Mapa: id do script → nome do arquivo .py correspondente
# Usado por verificar_dependencias para sugerir o comando exato a rodar
_ARQUIVO_POR_SCRIPT: dict[str, str] = {
    "01_feriados":            "01_coletar_feriados_bancarios.py",
    "02_coletar_emails":      "02_coletar_emails_gmail.py",
    "03_corrigir_anexos":     "03_corrigir_anexos_resposta_finaud.py",
    "04_mapear_clientes":     "04_mapear_clientes.py",
    "05_classificar":         "05_classificar_emails_regulatorio.py",
    "06_coletar_chat":        "06_coletar_chat_google.py",
    "07_abrir_fog":           "07_abrir_casos_fogbugz.py",
    "08_coletar_fog":         "08_coletar_fogbugz.py",
    "09_integrar":            "09_integrar_dados_painel.py",
    "10_resolver_aguardando": "10_resolver_threads_aguardando.py",
    "11_triar":               "11_triar_threads_por_cadoc.py",
    "12_enriquecer_ocr":      "12_enriquecer_texto_imagens.py",
    "13_correlacionar":       "13_correlacionar_threads.py",
    "14_sincronizar_crd":     "14_sincronizar_indicios_qualidade_crd.py",
    "15_aprendizados":        "15_reprocessar_aprendizados_ia.py",
    "16_resumos_rb":          "16_resumir_retorno_bacen_llm.py",
}


def _carregar_estado() -> dict:
    """Lê pipeline_estado.json; retorna {} se não existir ou inválido."""
    if not os.path.isfile(F_PIPELINE_ESTADO):
        return {}
    try:
        with open(F_PIPELINE_ESTADO, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _salvar_estado(estado: dict) -> None:
    """Grava pipeline_estado.json de forma atômica."""
    tmp = F_PIPELINE_ESTADO + ".tmp"
    try:
        os.makedirs(os.path.dirname(F_PIPELINE_ESTADO), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        os.replace(tmp, F_PIPELINE_ESTADO)
    except OSError:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def registrar_execucao(nome_script: str, arquivo_saida: str | None = None) -> None:
    """
    Registra que o script terminou com sucesso.

    Parâmetros
    ----------
    nome_script   : identificador único do script (ex: "05_classificar")
    arquivo_saida : caminho do arquivo principal que o script produziu.
                    Se informado, registra também o mtime para comparação futura.

    Nunca lança exceção — qualquer falha é silenciosa para não interromper o pipeline.
    """
    try:
        estado = _carregar_estado()
        entrada: dict = {
            "concluido_em": _time.strftime("%Y-%m-%d %H:%M:%S"),
            "concluido_em_epoch": int(_time.time()),
        }
        if arquivo_saida and os.path.isfile(arquivo_saida):
            entrada["arquivo_saida"] = arquivo_saida
            entrada["mtime_saida"] = int(os.path.getmtime(arquivo_saida))
        estado[nome_script] = entrada
        _salvar_estado(estado)
    except Exception:
        pass  # nunca interrompe o pipeline


def verificar_dependencias(
    nome_script: str,
    requer: list[str],
    silencioso: bool = False,
) -> bool:
    """
    Verifica se os scripts listados em ``requer`` rodaram e estão atualizados.
    Emite aviso acionável (com comando exato) se algum estiver desatualizado.

    Retorna True se tudo OK, False se alguma dependência está desatualizada.
    Nunca lança exceção — qualquer falha retorna True (permissivo).

    Para ignorar os avisos e continuar mesmo com dependências desatualizadas:
        ORACULO_IGNORAR_DEPS=1 python scripts/XX_script.py

    Parâmetros
    ----------
    nome_script : nome do script que está chamando (para o aviso)
    requer      : lista de nomes de scripts que devem ter rodado antes
    silencioso  : se True, não imprime nada (para testes)
    """
    # Permite bypass explícito para execuções cirúrgicas
    if os.environ.get("ORACULO_IGNORAR_DEPS", "").strip().lower() in ("1", "true", "yes"):
        return True

    try:
        estado = _carregar_estado()
        tudo_ok = True
        problemas: list[str] = []

        for dep in requer:
            reg = estado.get(dep)
            arquivo_dep = _ARQUIVO_POR_SCRIPT.get(dep, dep + ".py")
            cmd_corrigir = f"python scripts/{arquivo_dep}"

            if not reg:
                problemas.append(
                    f"  '{dep}' nunca foi executado nesta máquina.\n"
                    f"    → Rode primeiro: {cmd_corrigir}"
                )
                tudo_ok = False
                continue

            # Verifica se o arquivo de saída foi modificado após o registro
            arq = reg.get("arquivo_saida")
            mtime_registrado = reg.get("mtime_saida")
            if arq and mtime_registrado and os.path.isfile(arq):
                mtime_atual = int(os.path.getmtime(arq))
                if mtime_atual > mtime_registrado:
                    ultima = reg.get("concluido_em", "?")
                    problemas.append(
                        f"  '{dep}' está desatualizado — '{os.path.basename(arq)}' "
                        f"foi modificado após sua última execução ({ultima}).\n"
                        f"    → Rode novamente: {cmd_corrigir}"
                    )
                    tudo_ok = False

        if problemas and not silencioso:
            sep = "-" * 60
            print("\n  [PIPELINE] AVISO -- " + nome_script)
            print("  " + sep)
            for p in problemas:
                print("  " + p)
            print("  " + sep)
            print("  Pipeline completo (ordem correta): python executar_tudo.py")
            print("  Ver estado atual:                  python executar_tudo.py --status")
            print("  Ignorar avisos (uso cirurgico):    set ORACULO_IGNORAR_DEPS=1")
            print("  " + sep + "\n")

        return tudo_ok
    except Exception:
        return True  # permissivo em caso de erro inesperado


def status_pipeline() -> None:
    """
    Imprime o estado atual de todos os scripts do pipeline.
    Útil para diagnosticar o que já rodou e o que está desatualizado.

    Uso:
        python -c "import sys; sys.path.insert(0,'scripts'); from paths import status_pipeline; status_pipeline()"
    Ou via executar_tudo.py --status
    """
    estado = _carregar_estado()
    sep = "=" * 62
    print("\n" + sep)
    print("   ESTADO DO PIPELINE -- GESTAO AREA SUPORTE")
    print(sep)

    ordem = [
        "01_feriados", "02_coletar_emails", "03_corrigir_anexos",
        "04_mapear_clientes", "05_classificar", "06_coletar_chat",
        "07_abrir_fog", "08_coletar_fog", "09_integrar",
        "10_resolver_aguardando", "11_triar", "12_enriquecer_ocr",
        "13_correlacionar", "14_sincronizar_crd", "15_aprendizados",
        "16_resumos_rb",
    ]

    for nome in ordem:
        reg = estado.get(nome)
        arquivo = _ARQUIVO_POR_SCRIPT.get(nome, nome + ".py")
        if not reg:
            status = "[NUNCA EXECUTADO]"
            detalhe = "   -> python scripts/" + arquivo
        else:
            concluido = reg.get("concluido_em", "?")
            arq = reg.get("arquivo_saida")
            mtime_reg = reg.get("mtime_saida")
            if arq and mtime_reg and os.path.isfile(arq):
                mtime_atual = int(os.path.getmtime(arq))
                if mtime_atual > mtime_reg:
                    status = "[DESATUALIZADO] ultima execucao: " + concluido
                    detalhe = "   -> python scripts/" + arquivo
                else:
                    status = "[OK] " + concluido
                    detalhe = ""
            else:
                status = "[OK] " + concluido
                detalhe = ""

        print("  " + nome.ljust(26) + " " + status)
        if detalhe:
            print(detalhe)

    print(sep)
    print("  Para rodar o pipeline completo: python executar_tudo.py")
    print("  Para ignorar avisos (cirurgico): set ORACULO_IGNORAR_DEPS=1")
    print(sep + "\n")
