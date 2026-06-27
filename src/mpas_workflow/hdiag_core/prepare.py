from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_hdiag


def prepare(config, vbal_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    return prepare_hdiag(config, vbal_workspace, workspace=workspace, clean=clean)
