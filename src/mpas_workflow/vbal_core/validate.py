from __future__ import annotations

from pathlib import Path

from ..bcov import validate_vbal


def validate(workspace: str | Path) -> bool:
    """Validate the VBAL products and logs."""
    return validate_vbal(workspace)
