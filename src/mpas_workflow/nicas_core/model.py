from __future__ import annotations

from pathlib import Path

from ..vbal_core.model import STATE_VARIABLES, covariance_root

NICAS_VARIABLES = STATE_VARIABLES
NICAS_DIRAC_POINTS = [
    (-45.0, 0.0),
    (-135.0, 0.0),
    (45.0, 0.0),
    (135.0, 0.0),
    (-135.0, 45.0),
    (-45.0, 45.0),
    (45.0, 45.0),
    (135.0, 45.0),
    (-135.0, -45.0),
    (-45.0, -45.0),
    (45.0, -45.0),
    (135.0, -45.0),
]


def nicas_workspace(config, hdiag_workspace_path: str | Path) -> Path:
    return covariance_root(config) / "nicas" / Path(hdiag_workspace_path).name
