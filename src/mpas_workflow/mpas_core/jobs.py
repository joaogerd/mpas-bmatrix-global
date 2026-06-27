from __future__ import annotations

from ..forecast import submit_forecast


def run_job(config, init_time: str, lead_hours: int, dt=None):
    return submit_forecast(config, init_time, lead_hours, dt=dt)
