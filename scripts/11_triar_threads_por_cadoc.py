"""
ORÁCULO 360 — Etapa 11: Triar Threads por CADOC

Classifica automaticamente threads em "Aguardando" ou "Concluído" com base nas
regras de cada CADOC regulatório, depois de o integrador (etapa 09) consolidar
os dados no painel.

Lê   : data/json/pipeline/03_integrador_dados_site.json
Grava (via helpers ``save_aguardando`` / ``save_concluidas`` de paths.py):
       data/json/pipeline/threads_aguardando_auto.json
       data/json/pipeline/threads_aguardando_manual.json
       data/json/pipeline/threads_concluidas_auto.json
       data/json/pipeline/threads_concluidas_manual.json

Os registos são separados por ``origem_triagem_auto``: True → _auto, caso
contrário _manual. As marcações manuais do painel ficam no _manual e
são preservadas pela triagem (só é rescrito o _auto).

╔══════════════════════════════════════════════════════════════════════╗
║  REGRA FUNDAMENTAL                                                   ║
║  Este script SÓ GRAVA em threads_aguardando_* / threads_concluidas_*.║
║  Nunca modifica o JSON 03 nem qualquer arquivo das etapas anteriores.║
╚══════════════════════════════════════════════════════════════════════╝

Triagens executadas (em ordem):
   1. DDR / 4111             — ativa com TRIAGEM_AUTO_DDR4111=1 (ou pela cadeia abaixo)
   2. DLI_2062               — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_DLI=1
   3. DLO_2061               — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_DLO=1
   4. S5                     — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_S5=1
   5. SUPORTE                — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_SUPORTE=1
   6. DRSAC                  — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_DRSAC=1
   7. FORCAPITAL             — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_FORCAPITAL=1
   8. DRM_2060               — ativa com TRIAGEM_AUTO_DDR4111=1 ou TRIAGEM_AUTO_DRM=1
   9. RETORNO BACEN          — ativa SOMENTE com TRIAGEM_AUTO_RETORNO_BACEN=1
  10. CADOC 6209             — ativa SOMENTE com TRIAGEM_AUTO_6209=1
Data de referência (filtra só threads do dia):
  TRIAGEM_AUTO_DATA_REF=YYYY-MM-DD   (definido pelo executar_tudo para não
                                       reprocessar dias anteriores)

Uso directo (fora do executar_tudo.py):
  python scripts/11_triar_threads_por_cadoc.py
  python scripts/11_triar_threads_por_cadoc.py --data-ref 2026-02-24
  python scripts/11_triar_threads_por_cadoc.py --dry-run    # só mostra, não grava
"""

import os
import sys
import argparse

# ── Path setup ────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
for _p in (_SCRIPTS, _BASE):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Fallback: carregar módulos triagem_auto_* de __pycache__ se .py não existe ─
# Necessário para módulos cujo código-fonte foi perdido/não commitado.
import importlib.util as _iutil


class _PyccFinder:
    """Meta-path finder que carrega .pyc de __pycache__ quando .py não existe."""

    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith("triagem_auto"):
            return None
        ver = f"{sys.version_info.major}{sys.version_info.minor}"
        pyc = os.path.join(_SCRIPTS, "__pycache__", f"{fullname}.cpython-{ver}.pyc")
        if os.path.exists(pyc):
            return _iutil.spec_from_file_location(fullname, pyc)
        return None


if not any(isinstance(f, _PyccFinder) for f in sys.meta_path):
    sys.meta_path.append(_PyccFinder())


try:
    from paths import registrar_execucao, verificar_dependencias
    from pipeline_log import cabecalho, resumo, Cronometro, iniciar_log_standalone
except ImportError:
    def registrar_execucao(*a, **k): pass  # type: ignore
    def verificar_dependencias(*a, **k): return True  # type: ignore


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _importar_modulo_triagem(modulo_str: str):
    """
    Importa um módulo de triagem. Se o .py não existir, tenta o .pyc em __pycache__.
    Isso permite carregar módulos cujo código fonte foi perdido/não commitado.
    """
    import importlib
    import importlib.util
    try:
        return importlib.import_module(modulo_str)
    except ModuleNotFoundError:
        # Fallback: procurar .pyc compilado em __pycache__ de scripts/
        pasta = os.path.dirname(os.path.abspath(__file__))
        ver = f"{sys.version_info.major}{sys.version_info.minor}"
        pyc = os.path.join(pasta, "__pycache__", f"{modulo_str}.cpython-{ver}.pyc")
        if os.path.exists(pyc):
            spec = importlib.util.spec_from_file_location(modulo_str, pyc)
            if spec:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[modulo_str] = mod
                spec.loader.exec_module(mod)
                return mod
        raise


def _executar_triagem(nome_func: str, modulo_str: str, apply: bool, data_ref=None) -> int:
    """Importa o módulo e chama a função de triagem com timeout. Devolve 0 (OK) ou 1 (erro)."""
    from pipeline_watchdog import processar_com_timeout
    _timeout = int(os.environ.get("ORACULO_TIMEOUT_TRIAGEM", "900"))  # 15 min por módulo

    def _run():
        mod = _importar_modulo_triagem(modulo_str)
        func = getattr(mod, nome_func)
        return func(apply=apply, data_ref=data_ref)

    resultado, ok = processar_com_timeout(
        _run, args=(),
        timeout_s=_timeout,
        item_desc=f"triagem {modulo_str}",
    )
    if not ok:
        return 1
    return resultado if isinstance(resultado, int) else 0


def main(apply: bool = True, data_ref: str | None = None) -> int:
    """
    Ponto de entrada: roda todas as triagens habilitadas via variáveis de ambiente.

    Parâmetros
    ----------
    apply    : se False, modo dry-run (imprime mas não grava)
    data_ref : YYYY-MM-DD; se None, lê de TRIAGEM_AUTO_DATA_REF ou processa tudo
    """
    # ── Data de referência ─────────────────────────────────────────────────────
    if data_ref is None:
        data_ref = os.environ.get("TRIAGEM_AUTO_DATA_REF", "").strip() or None

    from pipeline_watchdog import iniciar_watchdog
    iniciar_watchdog(max_horas=1, nome_script="11_triar")

    relogio = Cronometro()
    cabecalho(11, "Triar Threads por CADOC", modo="DRY-RUN" if not apply else "APPLY")
    verificar_dependencias("11_triar", requer=["09_integrar"])
    modo = "DRY-RUN" if not apply else "APPLY"
    ref_str = data_ref or "(sem filtro de data — processa todo o 03)"
    print(f"\n=== Etapa 11: Triar Threads por CADOC [{modo}] ===")
    print(f"    Data de referência: {ref_str}")

    # ── Flags de activação ────────────────────────────────────────────────────
    ddr_on    = _env_on("TRIAGEM_AUTO_DDR4111")
    dli_on    = _env_on("TRIAGEM_AUTO_DLI")
    dlo_on    = _env_on("TRIAGEM_AUTO_DLO")
    s5_on     = _env_on("TRIAGEM_AUTO_S5")
    sup_on    = _env_on("TRIAGEM_AUTO_SUPORTE")
    drsac_on  = _env_on("TRIAGEM_AUTO_DRSAC")
    fcap_on   = _env_on("TRIAGEM_AUTO_FORCAPITAL")
    drm_on    = _env_on("TRIAGEM_AUTO_DRM")
    rb_on     = _env_on("TRIAGEM_AUTO_RETORNO_BACEN")
    c6209_on  = _env_on("TRIAGEM_AUTO_6209")
    # DDR ativa toda a cadeia (DLI, DLO, S5, SUPORTE, DRSAC, FORCAPITAL, DRM).
    # FOGBUGZ, LEIAUTES_BACEN e RISK_DRIVER_* são INTERNO — não entram na triagem.
    if ddr_on:
        dli_on = dlo_on = s5_on = sup_on = drsac_on = fcap_on = drm_on = True

    if not any([ddr_on, dli_on, dlo_on, s5_on, sup_on, drsac_on, fcap_on, drm_on,
                rb_on, c6209_on]):
        print("    Nenhuma triagem activada. "
              "Use TRIAGEM_AUTO_DDR4111=1 para activar a cadeia completa.")
        return 0

    # Resumo explícito das triagens que vão correr — evita que o utilizador
    # seja surpreendido por triagens activadas via env var residual na sessão.
    _ativas = [
        nome for nome, on in (
            ("DDR4111", ddr_on),
            ("DLI_2062", dli_on),
            ("DLO_2061", dlo_on),
            ("S5", s5_on),
            ("SUPORTE", sup_on),
            ("DRSAC", drsac_on),
            ("FORCAPITAL", fcap_on),
            ("DRM_2060", drm_on),
            ("RETORNO_BACEN", rb_on),
            ("6209", c6209_on),
        ) if on
    ]
    print(f"    Triagens activas nesta corrida: {', '.join(_ativas)}")

    # Pré-aquece o cache do arquivo 03 no thread principal — todos os 15 módulos
    # reutilizarão os dados sem releitura, evitando 15 × 356 MB de I/O.
    from triagem.motor import precarregar_dados_03
    precarregar_dados_03()

    erros = 0

    # ── 1. DDR / 4111 ─────────────────────────────────────────────────────────
    if ddr_on:
        print("\n  [1/15] Triagem DDR / 4111")
        erros += _executar_triagem(
            "run_triagem_ddr4111", "triagem_auto", apply, data_ref
        )

    # ── 2. DLI_2062 ───────────────────────────────────────────────────────────
    if dli_on:
        print("\n  [2/15] Triagem DLI_2062")
        erros += _executar_triagem(
            "run_triagem_dli", "triagem_auto_dli", apply, data_ref
        )

    # ── 3. DLO_2061 ───────────────────────────────────────────────────────────
    if dlo_on:
        print("\n  [3/10] Triagem DLO_2061")
        erros += _executar_triagem(
            "run_triagem_dlo", "triagem_auto_dlo", apply, data_ref
        )

    # ── 4. S5 ─────────────────────────────────────────────────────────────────
    if s5_on:
        print("\n  [4/10] Triagem S5")
        erros += _executar_triagem(
            "run_triagem_s5", "triagem_auto_s5", apply, data_ref
        )

    # ── 5. SUPORTE ────────────────────────────────────────────────────────────
    if sup_on:
        print("\n  [5/10] Triagem SUPORTE")
        erros += _executar_triagem(
            "run_triagem_suporte", "triagem_auto_suporte", apply, data_ref
        )

    # ── 6. DRSAC ──────────────────────────────────────────────────────────────
    if drsac_on:
        print("\n  [6/10] Triagem DRSAC")
        erros += _executar_triagem(
            "run_triagem_drsac", "triagem_auto_drsac", apply, data_ref
        )

    # ── 7. FORCAPITAL ─────────────────────────────────────────────────────────
    if fcap_on:
        print("\n  [7/10] Triagem FORCAPITAL")
        erros += _executar_triagem(
            "run_triagem_forcapital", "triagem_auto_forcapital", apply, data_ref
        )

    # ── 8. DRM_2060 ───────────────────────────────────────────────────────────
    if drm_on:
        print("\n  [8/10] Triagem DRM_2060")
        erros += _executar_triagem(
            "run_triagem_drm", "triagem_auto_drm", apply, data_ref
        )

    # ── 9. RETORNO BACEN ──────────────────────────────────────────────────────
    # Propositalmente separado da cadeia DDR — requer activação explícita
    if rb_on:
        print("\n  [9/10] Triagem RETORNO_BACEN")
        erros += _executar_triagem(
            "run_triagem_retorno_bacen", "triagem_auto_retorno_bacen", apply, data_ref
        )

    # ── 10. CADOC 6209 ────────────────────────────────────────────────────────
    # Propositalmente separado da cadeia DDR — requer activação explícita
    if c6209_on:
        print("\n  [10/10] Triagem CADOC 6209")
        erros += _executar_triagem(
            "run_triagem_6209", "triagem_auto_6209", apply, data_ref
        )

    # ── Resumo ────────────────────────────────────────────────────────────────
    if erros:
        print(f"\n  [AVISO] {erros} triagem(ns) com erro.")
    else:
        print("\n  [OK] Triagem concluída sem erros.")

    resumo(processados=10 - erros, erros=erros, tempo_s=relogio.elapsed)
    registrar_execucao("11_triar")
    return 0 if erros == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Triagem automática de threads por CADOC (etapa 11 do pipeline)."
    )
    parser.add_argument(
        "--data-ref", metavar="YYYY-MM-DD",
        help="Filtrar só threads do dia indicado (ex.: 2026-02-24)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Mostra o que seria feito sem gravar nada."
    )
    parser.add_argument(
        "--ddr",   action="store_true", help="Activar triagem DDR/4111 + cadeia."
    )
    parser.add_argument(
        "--dli",   action="store_true", help="Activar triagem DLI_2062."
    )
    parser.add_argument(
        "--dlo",   action="store_true", help="Activar triagem DLO_2061."
    )
    parser.add_argument(
        "--s5",    action="store_true", help="Activar triagem S5."
    )
    parser.add_argument(
        "--suporte", action="store_true", help="Activar triagem SUPORTE."
    )
    parser.add_argument(
        "--retorno-bacen", action="store_true", help="Activar triagem RETORNO_BACEN."
    )
    parser.add_argument(
        "--drm",     action="store_true", help="Activar triagem DRM_2060."
    )
    parser.add_argument(
        "--drsac",   action="store_true", help="Activar triagem DRSAC."
    )
    parser.add_argument(
        "--forcapital", action="store_true", help="Activar triagem FORCAPITAL."
    )
    parser.add_argument(
        "--6209",    action="store_true", dest="c6209", help="Activar triagem CADOC 6209."
    )
    args = parser.parse_args()

    # MODO CLI EXPLÍCITO: limpa env vars residuais e ativa só as flags passadas
    _todas_flags = [
        args.ddr, args.dli, args.dlo, args.s5, args.suporte, args.drm, args.retorno_bacen,
        args.drsac, args.forcapital, args.c6209,
    ]
    if any(_todas_flags):
        for _k in (
            "TRIAGEM_AUTO_DDR4111", "TRIAGEM_AUTO_DLI", "TRIAGEM_AUTO_DLO",
            "TRIAGEM_AUTO_S5", "TRIAGEM_AUTO_SUPORTE", "TRIAGEM_AUTO_DRM",
            "TRIAGEM_AUTO_RETORNO_BACEN", "TRIAGEM_AUTO_DRSAC", "TRIAGEM_AUTO_FORCAPITAL",
            "TRIAGEM_AUTO_6209",
        ):
            os.environ.pop(_k, None)

    if args.ddr:                    os.environ["TRIAGEM_AUTO_DDR4111"]              = "1"
    if args.dli:                    os.environ["TRIAGEM_AUTO_DLI"]                  = "1"
    if args.dlo:                    os.environ["TRIAGEM_AUTO_DLO"]                  = "1"
    if args.s5:                     os.environ["TRIAGEM_AUTO_S5"]                   = "1"
    if args.suporte:                os.environ["TRIAGEM_AUTO_SUPORTE"]              = "1"
    if args.drm:                    os.environ["TRIAGEM_AUTO_DRM"]                  = "1"
    if args.retorno_bacen:          os.environ["TRIAGEM_AUTO_RETORNO_BACEN"]        = "1"
    if args.drsac:                  os.environ["TRIAGEM_AUTO_DRSAC"]                = "1"
    if args.forcapital:             os.environ["TRIAGEM_AUTO_FORCAPITAL"]           = "1"
    if args.c6209:                  os.environ["TRIAGEM_AUTO_6209"]                 = "1"

    with iniciar_log_standalone(11, "triar_threads_por_cadoc"):
        sys.exit(main(apply=not args.dry_run, data_ref=args.data_ref))
