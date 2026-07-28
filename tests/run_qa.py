"""
QA – Runner: executa todos os testes na ordem dos módulos.

Fluxo: 1) Ler REGISTRO_CORRECOES.md  2) Montar cenário (estes arquivos)  3) Você roda este script.

Uso (na raiz do projeto):
  python run_qa.py
  python tests/run_qa.py
"""
from __future__ import annotations

import os
import sys

# Garante que a raiz do projeto e a pasta tests estão no path
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_raiz = os.path.dirname(_tests_dir)
if _raiz not in sys.path:
    sys.path.insert(0, _raiz)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

# Módulos de teste na ordem (alinhada ao REGISTRO_CORRECOES.md)
MODULOS = [
    "test_01_registro",
    "qa_registro_correcoes",
    "test_02_templates",
    "test_03_painel",
    "test_03_painel_integracao_03",  # 03 real: "ENC: COS 12 2025 - Conecta" não no dia 13
    "test_04_classificador",   # separação threads por datas no assunto (4111-COS Sefer)
    "test_04_script_08",
    "test_05_script_01",
    "test_06_script_09",
    "test_07_script_13",             # correlação e-mail ↔ FOG (script 13)
    "test_08_sugerir_aguardo",       # API sugerir_aguardo — UNICRED DDR (motivo com 12/02, 18/02)
    "test_09_api_threads_modal",     # API threads com barra no threadId; datas + abrir cards
    "test_10_verificar_thread_gmail", # Script verificar quantas mensagens na thread no Gmail
    "test_api_dados_24_02",          # API dados retorna pendentes para 24/02/2026
]


def run_all():
    """Importa cada módulo, executa sua lista TESTS e retorna 0 se todos passaram, 1 caso contrário."""
    total = 0
    failed = []
    for nome in MODULOS:
        try:
            mod = __import__(nome)
        except Exception as e:
            print(f"  ERRO import {nome}: {e}")
            failed.append((nome, str(e)))
            continue
        testes = getattr(mod, "TESTS", [])
        for t in testes:
            total += 1
            try:
                t()
                print(f"  OK  [{nome}] {t.__name__}")
            except Exception as e:
                print(f"  FAIL [{nome}] {t.__name__}: {e}")
                failed.append((t.__name__, str(e)))
    if failed:
        print(f"\n{len(failed)} teste(s) falharam (total: {total}).")
        return 1
    print(f"\nTodos os {total} testes passaram.")
    return 0


if __name__ == "__main__":
    print("QA – Registro de correções (REGISTRO_CORRECOES.md)")
    print("Módulos:", ", ".join(MODULOS), "\n")
    sys.exit(run_all())
