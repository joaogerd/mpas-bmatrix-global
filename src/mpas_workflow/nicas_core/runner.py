from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_nicas, submit_nicas, validate_nicas


def prepare(config, hdiag_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    return prepare_nicas(config, hdiag_workspace, workspace=workspace, clean=clean)


def submit(
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


def validate(workspace: str | Path) -> bool:
    return validate_nicas(workspace)
