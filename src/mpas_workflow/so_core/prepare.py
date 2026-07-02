from __future__ import annotations

import shutil
from pathlib import Path

from ..hdiag_core.checks import check as validate_hdiag
from ..hdiag_core.model import hdiag_date
from ..nicas_core.checks import check as validate_nicas
from ..shell import require_file, write_text
from ..vbal_core.validate import validate as validate_vbal
from .config_files import write_so_pbs, write_so_t_only_diagnostic_pbs, write_so_yaml
from .model import so_artifacts, so_workspace, workspace_from_readme
from .static import create_so_background, link_so_support


def prepare(
    config,
    nicas_workspace: str | Path,
    hdiag_workspace=None,
    vbal_workspace=None,
    workspace=None,
    clean: bool = False,
    variant: str = "default",
    debug_core: bool = False,
) -> Path:
    artifacts = so_artifacts(variant)
    nicas_root = Path(nicas_workspace)
    hdiag_root = Path(hdiag_workspace) if hdiag_workspace else workspace_from_readme(nicas_root, "HDIAG workspace")
    if hdiag_root is None:
        raise SystemExit("ERRO: informe --hdiag-workspace; metadata NICAS não contém o caminho.")
    vbal_root = Path(vbal_workspace) if vbal_workspace else workspace_from_readme(hdiag_root, "VBAL workspace")
    if vbal_root is None:
        raise SystemExit("ERRO: informe --vbal-workspace; metadata HDIAG não contém o caminho.")

    validate_nicas(nicas_root)
    validate_hdiag(hdiag_root)
    validate_vbal(vbal_root)
    nicas_dir = nicas_root / "merge"
    hdiag_run = hdiag_root / "HDIAG"
    vbal_run = vbal_root / "VBAL"
    require_file(nicas_dir / "mpas_nicas.nc", "NICAS global mesclado")
    stddev = require_file(hdiag_run / "mpas.stddev.nc", "StdDev HDIAG")
    require_file(vbal_run / "mpas_vbal.nc", "VBAL global")
    require_file(vbal_run / "mpas_sampling.nc", "sampling VBAL global")

    out = Path(workspace) if workspace else so_workspace(config, nicas_root)
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    template = link_so_support(hdiag_run, out)
    create_so_background(template, out / "bg_so.nc")
    write_so_yaml(out / artifacts["yaml"], hdiag_date(hdiag_root), nicas_dir, stddev, vbal_run, variant=variant)
    write_so_pbs(config, out, variant=variant)
    if debug_core:
        if variant != "t-only":
            raise SystemExit("ERRO: --debug-core esta restrito a --variant t-only neste diagnostico.")
        write_so_t_only_diagnostic_pbs(config, out)
    write_text(
        out / "README.md",
        "\n".join(
            [
                "# Single Observation workspace",
                "",
                f"NICAS workspace: `{nicas_root}`",
                f"HDIAG workspace: `{hdiag_root}`",
                f"VBAL workspace: `{vbal_root}`",
                "",
            ]
        ),
    )
    print("=== SO workspace ===")
    print(f"WORKSPACE={out}")
    print(f"VARIANT={variant}")
    print(f"YAML={out / artifacts['yaml']}")
    print(f"PBS={out / artifacts['pbs']}")
    return out
