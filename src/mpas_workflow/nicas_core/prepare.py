from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_nicas


def prepare(config, hdiag_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    return prepare_nicas(config, hdiag_workspace, workspace=workspace, clean=clean)
