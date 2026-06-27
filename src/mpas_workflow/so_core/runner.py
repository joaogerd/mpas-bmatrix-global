from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_so, submit_so, validate_so


def prepare(config, nicas_workspace: str | Path, hdiag_workspace: str | Path | None = None, vbal_workspace: str | Path | None = None, workspace: str | Path | None = None, clean: bool = False, variant: str = "default") -> Path:
    return prepare_so(
        config,
        nicas_workspace,
        hdiag_workspace_path=hdiag_workspace,
        vbal_workspace_path=vbal_workspace,
        workspace=workspace,
        clean=clean,
        variant=variant,
    )


def submit(workspace: str | Path, wait: bool = False, poll_seconds: int = 30, variant: str = "default") -> str:
    return submit_so(workspace, wait=wait, poll_seconds=poll_seconds, variant=variant)


def validate(workspace: str | Path, variant: str = "default") -> bool:
    return validate_so(workspace, variant=variant)
