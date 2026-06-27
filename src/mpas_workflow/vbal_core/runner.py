from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_vbal, submit_vbal, validate_vbal


def prepare(config, bflow_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    return prepare_vbal(config, bflow_workspace, workspace=workspace, clean=clean)


def submit(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    return submit_vbal(workspace, wait=wait, poll_seconds=poll_seconds)


def validate(workspace: str | Path) -> bool:
    return validate_vbal(workspace)
