from __future__ import annotations

import shutil
from pathlib import Path

from ..shell import write_text
from .config_files import write_vbal_pbs, write_vbal_yaml
from .model import iso_date, read_bflow_samples, vbal_workspace
from .static import link_static_files, stage_samples


def prepare(config, bflow_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    """Prepare the VBAL workspace from a completed BFLOW workspace."""
    samples = read_bflow_samples(bflow_workspace)
    out = Path(workspace) if workspace else vbal_workspace(config, bflow_workspace)
    if clean and out.exists():
        shutil.rmtree(out)
    run_dir = out / "VBAL"
    run_dir.mkdir(parents=True, exist_ok=True)

    stage_samples(out, samples)
    link_static_files(
        config,
        run_dir,
        samples[0].full_f24,
        samples[0].template_fields,
        samples[0].valid_time,
    )
    write_vbal_yaml(run_dir / "run_vbal.yaml", nmembers=len(samples), date=iso_date(samples[0].valid_time))
    write_vbal_pbs(config, run_dir)

    write_text(
        out / "README.md",
        f"# VBAL workspace\n\nBflow workspace: `{bflow_workspace}`\nMembers: {len(samples)}\n\nRun dir: `{run_dir}`\n",
    )
    print("=== VBAL workspace ===")
    print(f"WORKSPACE={out}")
    print(f"RUN_DIR={run_dir}")
    print(f"MEMBERS={len(samples)}")
    print(f"PBS={run_dir / 'qsub_vbal.bash'}")
    return out
