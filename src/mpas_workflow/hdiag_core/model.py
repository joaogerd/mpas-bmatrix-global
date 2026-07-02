from __future__ import annotations

import re
from pathlib import Path

from ..shell import require_file
from ..vbal_core.model import STATE_VARIABLES, covariance_root, toolbox_exe

MIN_HDIAG_MEMBERS = 4


def hdiag_workspace(config, vbal_workspace_path: str | Path) -> Path:
    return covariance_root(config) / "hdiag" / Path(vbal_workspace_path).name


def require_hdiag_members(samples: list[Path]) -> None:
    if len(samples) < MIN_HDIAG_MEMBERS:
        raise SystemExit(
            "ERRO: HDIAG/NICAS requer pelo menos "
            f"{MIN_HDIAG_MEMBERS} membros; encontrados={len(samples)}. "
            "O BUMP exige ens_ne/ens_nsub > 3."
        )


def hdiag_date(hdiag_root: Path) -> str:
    text = require_file(hdiag_root / "HDIAG" / "run_hdiag.yaml", "run_hdiag.yaml").read_text()
    match = re.search(r"(?m)^\s*date:\s*&date\s+'([^']+)'", text)
    if not match:
        raise SystemExit("ERRO: data principal não encontrada no run_hdiag.yaml")
    return match.group(1)
