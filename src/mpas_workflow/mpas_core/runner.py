from __future__ import annotations

from ..forecast import prepare_forecast, submit_forecast


def prepare(config, init_time: str, lead_hours: int, dt=None, output_interval=None):
    return prepare_forecast(config, init_time, lead_hours, dt=dt, output_interval=output_interval)


def submit(config, init_time: str, lead_hours: int, dt=None):
    return submit_forecast(config, init_time, lead_hours, dt=dt)
