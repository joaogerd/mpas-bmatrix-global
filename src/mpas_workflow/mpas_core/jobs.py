from __future__ import annotations

from ..shell import qsub, require_file
from .model import forecast_run_dir


def run_job(config, init_time: str, lead_hours: int, dt=None, wait: bool = False):
    dt = int(dt or config["runtime"]["config_dt"])
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    require_file(run_dir / "run_mpas_forecast.pbs", "PBS de forecast")
    return qsub("run_mpas_forecast.pbs", run_dir, block=wait)
