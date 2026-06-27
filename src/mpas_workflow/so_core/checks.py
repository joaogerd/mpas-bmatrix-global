from __future__ import annotations

from pathlib import Path

from ..bcov import validate_so


def check(workspace: str | Path, variant: str = "default") -> bool:
    return validate_so(workspace, variant=variant)
