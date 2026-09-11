"""Captura semanal de estado — salva toda sexta-feira para habilitar deltas no resumo de segunda."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)

_BASE_DIR      = Path(__file__).resolve().parent.parent
_SNAPSHOTS_DIR = _BASE_DIR / 'data' / 'snapshots'


# ── Config do scheduler ───────────────────────────────────────────────────────

def snapshot_semanal_padrao() -> dict:
    return {'ativa': True, 'dia_semana': 4}  # 4 = sexta-feira


def normalizar_snapshot_semanal(bruto: dict | None) -> dict:
    padrao = snapshot_semanal_padrao()
    if not isinstance(bruto, dict):
        return padrao
    return {
        'ativa':      bool(bruto.get('ativa', padrao['ativa'])),
        'dia_semana': int(bruto.get('dia_semana', padrao['dia_semana'])),
    }


# ── Captura ───────────────────────────────────────────────────────────────────

def capturar_snapshot(cfg: dict) -> dict:
    """Coleta estado atual de BACEN e FOG e salva em data/snapshots/YYYY-MM-DD.json."""
    from resumo_semanal import buscar_dados_bacen, buscar_dados_fog_semanal

    fog_token = cfg.get('fogbugz_token') or os.environ.get('FOGBUGZ_TOKEN', '')

    dados_bacen = buscar_dados_bacen()
    dados_fog   = buscar_dados_fog_semanal(fog_token)

    # Agrupar BACEN por CADOC com totais
    por_cadoc: dict[str, dict] = {}
    por_status = dados_bacen.get('por_status', {})
    for status_key, grupos in por_status.items():
        for cadoc, empresas in grupos.items():
            if cadoc not in por_cadoc:
                por_cadoc[cadoc] = {'cliente': 0, 'finaud': 0, 'total': 0}
            n = len(empresas)
            if 'Cliente' in status_key:
                por_cadoc[cadoc]['cliente'] += n
            else:
                por_cadoc[cadoc]['finaud'] += n
            por_cadoc[cadoc]['total'] += n

    snapshot = {
        'data':  datetime.now(timezone.utc).date().isoformat(),
        'bacen': {
            'total':    dados_bacen.get('total', 0),
            'cliente':  dados_bacen.get('cliente', 0),
            'finaud':   dados_bacen.get('finaud', 0),
            'por_cadoc': por_cadoc,
        },
        'fog': {
            'total':           sum(p['total'] for p in dados_fog),
            'por_responsavel': dados_fog,
        },
    }

    _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = _SNAPSHOTS_DIR / f"{snapshot['data']}.json"
    caminho.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    _log.info('Snapshot semanal salvo: %s', caminho)
    return snapshot


# ── Leitura ───────────────────────────────────────────────────────────────────

def carregar_ultimo_snapshot(antes_de: str | None = None) -> dict | None:
    """Carrega o snapshot mais recente, opcionalmente anterior a uma data (YYYY-MM-DD)."""
    if not _SNAPSHOTS_DIR.exists():
        return None
    arquivos = sorted(_SNAPSHOTS_DIR.glob('*.json'), reverse=True)
    for arq in arquivos:
        nome = arq.stem
        if antes_de and nome >= antes_de:
            continue
        try:
            return json.loads(arq.read_text(encoding='utf-8'))
        except Exception:
            _log.warning('Snapshot corrompido, ignorando: %s', arq)
    return None


# ── Cálculo de deltas ─────────────────────────────────────────────────────────

def calcular_deltas(
    snapshot: dict,
    bacen_atual: dict,
    fog_atual: list[dict],
) -> dict:
    """Retorna diferenças entre o snapshot anterior e os dados atuais.

    Convenção: negativo = fila diminuiu (bom para BACEN/FOG), positivo = cresceu.
    """
    snap_b = snapshot.get('bacen', {})
    snap_f = snapshot.get('fog', {})

    bacen_delta  = bacen_atual.get('total', 0)   - snap_b.get('total', 0)
    ac_delta     = bacen_atual.get('cliente', 0) - snap_b.get('cliente', 0)
    af_delta     = bacen_atual.get('finaud', 0)  - snap_b.get('finaud', 0)
    fog_delta    = sum(p['total'] for p in fog_atual) - snap_f.get('total', 0)

    # Deltas por CADOC: atual − snapshot
    snap_cadoc = snap_b.get('por_cadoc', {})
    por_status = bacen_atual.get('por_status', {})
    cadoc_atual: dict[str, int] = {}
    for grupos in por_status.values():
        for cadoc, empresas in grupos.items():
            cadoc_atual[cadoc] = cadoc_atual.get(cadoc, 0) + len(empresas)

    cadoc_deltas: dict[str, int] = {}
    todos_cadocs = set(cadoc_atual) | set(snap_cadoc)
    for cadoc in todos_cadocs:
        atual = cadoc_atual.get(cadoc, 0)
        ant   = snap_cadoc.get(cadoc, {}).get('total', 0) if isinstance(snap_cadoc.get(cadoc), dict) else snap_cadoc.get(cadoc, 0)
        delta = atual - ant
        if delta != 0:
            cadoc_deltas[cadoc] = delta

    return {
        'bacen':  bacen_delta,
        'ac':     ac_delta,
        'af':     af_delta,
        'fog':    fog_delta,
        'cadoc':  cadoc_deltas,
        'data_referencia': snapshot.get('data', ''),
    }


# ── Job do scheduler ──────────────────────────────────────────────────────────

def verificar_e_capturar_snapshot(
    cfg: dict,
    *,
    agora: datetime | None = None,
) -> tuple[dict, bool]:
    """Verifica se hoje é sexta e ainda não foi capturado — se sim, captura."""
    cfg   = dict(cfg or {})
    agora = agora or datetime.now(timezone.utc)

    cfg_snap = normalizar_snapshot_semanal(cfg.get('snapshot_semanal'))
    if not cfg_snap.get('ativa'):
        return cfg, False

    if agora.weekday() != cfg_snap.get('dia_semana', 4):
        return cfg, False

    hoje_str = agora.date().isoformat()
    if cfg.get('snapshot_semanal_ultima_captura') == hoje_str:
        return cfg, False

    try:
        capturar_snapshot(cfg)
        cfg['snapshot_semanal_ultima_captura'] = hoje_str
        _log.info('Snapshot semanal capturado para %s', hoje_str)
        return cfg, True
    except Exception:
        _log.exception('Falha ao capturar snapshot semanal.')
        return cfg, False
