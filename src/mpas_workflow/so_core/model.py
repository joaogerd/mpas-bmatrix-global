from __future__ import annotations

import re
from pathlib import Path

from ..shell import require_file
from ..vbal_core.model import covariance_root

SO_VARIANTS = ("default", "t-only", "u-only")
SO_BACKGROUND_VARIABLES = [
    "temperature",
    "spechum",
    "surface_pressure",
    "air_temperature",
    "air_pressure",
    "air_pressure_at_surface",
    "eastward_wind",
    "northward_wind",
]


def so_workspace(config, nicas_workspace_path: str | Path) -> Path:
    return covariance_root(config) / "so" / Path(nicas_workspace_path).name


def workspace_from_readme(workspace: Path, label: str) -> Path | None:
    readme = workspace / "README.md"
    if not readme.is_file():
        return None
    match = re.search(rf"(?m)^{re.escape(label)}:\s*`([^`]+)`\s*$", readme.read_text())
    return Path(match.group(1)) if match else None


def variational_exe(config) -> Path:
    path = Path(config["install"]["root"]) / "bin" / "mpasjedi_variational.x"
    return require_file(path, "mpasjedi_variational.x")


def so_artifacts(variant: str) -> dict[str, str]:
    if variant not in SO_VARIANTS:
        raise SystemExit(f"ERRO: variante SO inválida: {variant}; use {', '.join(SO_VARIANTS)}.")
    suffix = "" if variant == "default" else f"_{variant.replace('-', '_')}"
    return {
        "yaml": f"run_SO{suffix}.yaml",
        "pbs": f"qsub_so{suffix}.bash",
        "runlog": f"run_SO{suffix}.runlog",
        "stdout": f"stdout{suffix}.log",
        "stderr": f"stderr{suffix}.log",
    }
