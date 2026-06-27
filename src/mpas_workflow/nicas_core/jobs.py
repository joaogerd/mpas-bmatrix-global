from __future__ import annotations

from pathlib import Path

from ..bcov import submit_nicas


def run_job(
    workspace: str | Path,
    wait: bool = False,
    poll_seconds: int = 30,
    parallel: bool = False,
    retries: int = 2,
) -> str:
    return submit_nicas(
        workspace,
        wait=wait,
        poll_seconds=poll_seconds,
        parallel=parallel,
        retries=retries,
    )
