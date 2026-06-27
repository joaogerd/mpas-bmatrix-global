from __future__ import annotations

from ..forecast import prepare_forecast


def setup_run(config, init_time: str, lead_hours: int, dt=None, output_interval=None):
    return prepare_forecast(config, init_time, lead_hours, dt=dt, output_interval=output_interval)
