from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_vbal


def prepare(config, bflow_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    """Prepare the VBAL workspace from a completed BFLOW workspace."""
    return prepare_vbal(config, bflow_workspace, workspace=workspace, clean=clean)
