from __future__ import annotations

from pathlib import Path

from ..bcov import validate_nicas


def check(workspace: str | Path) -> bool:
    return validate_nicas(workspace)
