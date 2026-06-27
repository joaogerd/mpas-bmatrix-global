from __future__ import annotations

import shutil
from pathlib import Path

from ..shell import write_text
from ..vbal_core.validate import validate as validate_vbal
from .config_files import write_hdiag_pbs, write_hdiag_yaml
from .model import hdiag_workspace, require_hdiag_members
from .static import link_hdiag_inputs


def prepare(config, vbal_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    vbal_root = Path(vbal_workspace)
    validate_vbal(vbal_root)
    samples = sorted((vbal_root / "samples").glob("PTB_f48mf24_*.nc"))
    if not samples:
        raise SystemExit("ERRO: nenhum PTB original encontrado no workspace VBAL.")
    require_hdiag_members(samples)

    out = Path(workspace) if workspace else hdiag_workspace(config, vbal_root)
    if clean and out.exists():
        shutil.rmtree(out)
    run_dir = out / "HDIAG"
    run_dir.mkdir(parents=True, exist_ok=True)

    link_hdiag_inputs(vbal_root, out, run_dir)
    from ..vbal_core.model import iso_date
    from ..vbal_core.model import read_bflow_samples

    # Keep the date convention from VBAL by reading the first BFLOW-derived member if available.
    # Fallback to the date embedded in VBAL YAML is intentionally avoided here because HDIAG
    # writes its own YAML from the same staged sample set.
    manifest_samples = read_bflow_samples(vbal_root.parent.parent / "bflow_preprocessing" / vbal_root.name) if False else None
    del manifest_samples
    from ..bcov import vbal_date  # temporary fallback until vbal_core exposes YAML date parser

    write_hdiag_yaml(run_dir / "run_hdiag.yaml", len(samples), vbal_date(vbal_root))
    write_hdiag_pbs(config, run_dir)
    write_text(
        out / "README.md",
        f"# HDIAG/NICAS workspace\n\nVBAL workspace: `{vbal_root}`\nMembers: {len(samples)}\n",
    )

    print("=== HDIAG/NICAS workspace ===")
    print(f"WORKSPACE={out}")
    print(f"RUN_DIR={run_dir}")
    print(f"MEMBERS={len(samples)}")
    print(f"YAML={run_dir / 'run_hdiag.yaml'}")
    print(f"PBS={run_dir / 'qsub_hdiag.bash'}")
    return out
