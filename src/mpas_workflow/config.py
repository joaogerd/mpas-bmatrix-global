from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import os

try:
    import yaml
except ImportError as exc:
    raise SystemExit("ERRO: PyYAML não encontrado. Use: python -m pip install --user pyyaml") from exc


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERRO: configuração não encontrada: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"ERRO: configuração deve conter um mapa YAML no topo: {path}")
    return data


def _contract_path(platform_path: Path, platform: Dict[str, Any]) -> Path | None:
    bmatrix = platform.get("bmatrix")
    if not isinstance(bmatrix, dict):
        return None
    specification = bmatrix.get("configuration")
    if specification is None:
        return None
    if not isinstance(specification, str) or not specification:
        raise SystemExit("ERRO: bmatrix.configuration deve ser um caminho YAML não vazio.")

    candidate = Path(os.path.expandvars(specification))
    if not candidate.is_absolute():
        candidate = platform_path.parent / candidate
    return candidate


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load platform settings and, when configured, the scientific B-matrix contract.

    The platform YAML remains the entry point used by every command.  Its optional
    ``bmatrix.configuration`` path points to the scientific contract containing
    ``bflow``, ``controls`` and the other B-matrix settings.  The contract is
    merged below the platform settings so that infrastructure values always remain
    owned by the platform YAML.
    """
    platform_path = Path(path)
    platform = expand_env(_load_yaml(platform_path))
    contract_path = _contract_path(platform_path, platform)
    if contract_path is None:
        return platform

    contract = expand_env(_load_yaml(contract_path))
    merged = dict(contract)
    merged.update(platform)
    merged["bmatrix_contract"] = contract
    merged["bmatrix_contract_path"] = str(contract_path)
    return merged


def expand_env(obj):
    if isinstance(obj, dict):
        return {k: expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env(v) for v in obj]
    if isinstance(obj, str):
        return os.path.expandvars(obj)
    return obj


def safe_time(init_time: str) -> str:
    return init_time.replace(":", ".")


def ymdh(init_time: str) -> str:
    return init_time[0:4] + init_time[5:7] + init_time[8:10] + init_time[11:13]


def date_part(init_time: str) -> str:
    return init_time[0:4] + init_time[5:7] + init_time[8:10]


def cycle_part(init_time: str) -> str:
    return init_time[11:13]
