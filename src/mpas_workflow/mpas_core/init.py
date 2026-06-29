from __future__ import annotations

from pathlib import Path

from ..mpas_init import (
    init_file,
    init_is_valid,
    init_run_dir,
    prepare_init,
    submit_init,
    validate_init,
)
from ..shell import wait_for_pbs_job


def prepare(config, init_time: str, wps_file: str | Path) -> Path:
    return prepare_init(config, init_time, Path(wps_file))


def submit(
    config,
    init_time: str,
    wait: bool = False,
    poll_seconds: int = 30,
    validate: bool = True,
) -> str:
    jobid = submit_init(config, init_time)
    if wait:
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
        if validate:
            validate_init(config, init_time, jobid=jobid)
    return jobid


def validate(config, init_time: str) -> bool:
    validate_init(config, init_time)
    return True


__all__ = [
    "init_file",
    "init_is_valid",
    "init_run_dir",
    "prepare",
    "submit",
    "validate",
]
