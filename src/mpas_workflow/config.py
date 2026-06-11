from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import os

try:
    import yaml
except ImportError as exc:
    raise SystemExit("ERRO: PyYAML não encontrado. Use: python -m pip install --user pyyaml") from exc


def load_config(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"ERRO: configuração não encontrada: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    return expand_env(data)


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
