from __future__ import annotations

from pathlib import Path


def clean_forecast_run_dir(run_dir: Path) -> None:
    patterns = [
        "stdout.log",
        "stderr.log",
        "log.atmosphere.*",
        "*.o[0-9]*",
        "*.e[0-9]*",
        "restart.*.nc",
        "history.*.nc",
        "diagnostics.*.nc",
        "bflow.*.nc",
        "mpasout.*.nc",
        "background.*.nc",
        "analysis.*.nc",
        "ensemble.*.nc",
        "control.*.nc",
        "restart_timestamp",
    ]
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.exists() or path.is_symlink():
                path.unlink()
