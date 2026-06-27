from __future__ import annotations

from pathlib import Path

from ..bcov import prepare_so


def prepare(config, nicas_workspace: str | Path, hdiag_workspace=None, vbal_workspace=None, workspace=None, clean: bool = False, variant: str = "default") -> Path:
    return prepare_so(
        config,
        nicas_workspace,
        hdiag_workspace_path=hdiag_workspace,
        vbal_workspace_path=vbal_workspace,
        workspace=workspace,
        clean=clean,
        variant=variant,
    )
