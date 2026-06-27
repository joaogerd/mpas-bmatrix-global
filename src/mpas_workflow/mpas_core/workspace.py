from __future__ import annotations

from pathlib import Path

from .model import bflow_file as _bflow_file
from .model import forecast_run_dir, restart_file as _restart_file


def workspace(config, init_time: str, lead_hours: int, dt: int) -> Path:
    """Return the MPAS forecast run directory."""
    return forecast_run_dir(config, init_time, lead_hours, dt)


def restart_file(config, init_time: str, lead_hours: int, dt: int) -> Path:
    return _restart_file(config, init_time, lead_hours, dt)


def bflow_file(config, init_time: str, lead_hours: int, dt: int) -> Path:
    return _bflow_file(config, init_time, lead_hours, dt)
