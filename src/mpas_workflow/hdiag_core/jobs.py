from __future__ import annotations

from pathlib import Path

from ..bcov import submit_hdiag


def run_job(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    return submit_hdiag(workspace, wait=wait, poll_seconds=poll_seconds)
