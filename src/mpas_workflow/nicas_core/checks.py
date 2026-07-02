from __future__ import annotations

from pathlib import Path

from ..vbal_core.validate import validate_ranked_products
from .model import NICAS_VARIABLES


def home_failure_files(run_dir: Path) -> list[Path]:
    failures = []
    for pattern in ["*.o*", "*.e*"]:
        for path in run_dir.glob(pattern):
            if path.is_file() and "Could not chdir to home directory" in path.read_text(errors="replace"):
                failures.append(path)
    return sorted(set(failures))


def variable_errors(run_dir: Path) -> list[str]:
    runlog = run_dir / "run_nicas.runlog"
    text = runlog.read_text(errors="replace") if runlog.is_file() else ""
    errors = []
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente")
    for name in ["mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        if not (run_dir / name).is_file():
            errors.append(f"produto ausente: {name}")
    errors.extend(validate_ranked_products(sorted(run_dir.glob("mpas_nicas_local_*")), "mpas_nicas_local"))
    errors.extend(validate_ranked_products(sorted(run_dir.glob("mpas_nicas_grids_local_*")), "mpas_nicas_grids_local"))
    return errors


def check(workspace: str | Path) -> bool:
    root = Path(workspace)
    errors = []
    warnings = []
    for variable in NICAS_VARIABLES:
        run_dir = root / variable
        var_errors = variable_errors(run_dir)
        if home_failure_files(run_dir) and var_errors:
            errors.append(f"{variable}: falha PBS/HOME: Could not chdir to home directory")
        elif home_failure_files(run_dir):
            warnings.append(f"{variable}: stale PBS output: Could not chdir to home directory")
        errors.extend(f"{variable}: {error}" for error in var_errors)

    merge_dir = root / "merge"
    merge_errors = []
    for name in ["merge.done", "mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        if not (merge_dir / name).is_file():
            merge_errors.append(f"produto ausente: {name}")
    merge_errors.extend(validate_ranked_products(sorted(merge_dir.glob("mpas_nicas_local_*")), "mpas_nicas_local"))
    merge_errors.extend(validate_ranked_products(sorted(merge_dir.glob("mpas_nicas_grids_local_*")), "mpas_nicas_grids_local"))
    if home_failure_files(merge_dir) and merge_errors:
        errors.append("merge: falha PBS/HOME: Could not chdir to home directory")
    elif home_failure_files(merge_dir):
        warnings.append("merge: stale PBS output: Could not chdir to home directory")
    errors.extend(f"merge: {error}" for error in merge_errors)

    print("=== NICAS validation ===")
    print(f"WORKSPACE={root}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"  - {error}")
        raise SystemExit("ERRO: NICAS falhou ou ficou incompleto.")
    print("SUCCESS: NICAS split/merge validado.")
    return True
