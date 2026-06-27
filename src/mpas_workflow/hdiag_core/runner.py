from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_hdiag, submit_hdiag, validate_hdiag


def prepare(config, vbal_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    return prepare_hdiag(config, vbal_workspace, workspace=workspace, clean=clean)


def submit(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    return submit_hdiag(workspace, wait=wait, poll_seconds=poll_seconds)


def validate(workspace: str | Path) -> bool:
    return validate_hdiag(workspace)
