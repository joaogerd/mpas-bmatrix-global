from __future__ import annotations

import shutil
from pathlib import Path

from ..hdiag_core.checks import check as validate_hdiag
from ..hdiag_core.model import hdiag_date
from ..shell import require_file, symlink_force, write_text
from .config_files import write_nicas_merge_files, write_nicas_pbs, write_nicas_yaml
from .model import NICAS_VARIABLES, nicas_workspace
from .static import link_nicas_support


def prepare(config, hdiag_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    hdiag_root = Path(hdiag_workspace)
    validate_hdiag(hdiag_root)
    hdiag_run = hdiag_root / "HDIAG"
    date = hdiag_date(hdiag_root)
    out = Path(workspace) if workspace else nicas_workspace(config, hdiag_root)
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    symlink_force(require_file(hdiag_run / "mpas.cor_rh.nc"), out / "mpas.cor_rh.nc")
    symlink_force(require_file(hdiag_run / "mpas.cor_rv.nc"), out / "mpas.cor_rv.nc")
    symlink_force(require_file(hdiag_run / "mpas.stddev.nc"), out / "mpas.stddev.nc")

    for variable in NICAS_VARIABLES:
        run_dir = out / variable
        run_dir.mkdir(parents=True, exist_ok=True)
        link_nicas_support(hdiag_run, run_dir)
        write_nicas_yaml(
            run_dir / "run_nicas.yaml",
            variable,
            date,
            int(config["mesh"].get("nvertlevels", 55)),
        )
        write_nicas_pbs(config, run_dir, variable)

    write_nicas_merge_files(config, out)
    write_text(out / "README.md", f"# NICAS split/merge workspace\n\nHDIAG workspace: `{hdiag_root}`\n")
    print("=== NICAS split/merge workspace ===")
    print(f"WORKSPACE={out}")
    print(f"VARIABLES={','.join(NICAS_VARIABLES)}")
    print(f"MERGE_DIR={out / 'merge'}")
    return out
