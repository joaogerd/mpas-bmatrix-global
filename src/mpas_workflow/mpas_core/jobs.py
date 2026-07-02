from __future__ import annotations

from ..shell import qsub, require_file, wait_for_pbs_job
from .model import forecast_run_dir


def run_job(
    config,
    init_time: str,
    lead_hours: int,
    dt=None,
    wait: bool = False,
    poll_seconds: int = 30,
):
    dt = int(dt or config["runtime"]["config_dt"])
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    require_file(run_dir / "run_mpas_forecast.pbs", "PBS de forecast")
    jobid = qsub("run_mpas_forecast.pbs", run_dir)
    if wait:
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    return jobid
