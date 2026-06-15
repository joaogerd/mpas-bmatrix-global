from __future__ import annotations

import argparse
from pathlib import Path

from .bcov import (
    DEFAULT_CONFIG,
    dirac_workspace,
    hdiag_workspace,
    nicas_workspace,
    so_workspace,
    validate_dirac,
    validate_hdiag,
    validate_nicas,
    validate_so,
    validate_vbal,
    vbal_workspace,
)
from .config import load_config


def resolve_workspaces(config, args) -> dict[str, Path]:
    bflow = Path(args.bflow_workspace)
    vbal = Path(args.vbal_workspace) if args.vbal_workspace else vbal_workspace(config, bflow)
    hdiag = Path(args.hdiag_workspace) if args.hdiag_workspace else hdiag_workspace(config, vbal)
    nicas = Path(args.nicas_workspace) if args.nicas_workspace else nicas_workspace(config, hdiag)
    so = Path(args.so_workspace) if args.so_workspace else so_workspace(config, nicas)
    dirac = Path(args.dirac_workspace) if args.dirac_workspace else dirac_workspace(config, nicas)
    return {"bflow": bflow, "vbal": vbal, "hdiag": hdiag, "nicas": nicas, "so": so, "dirac": dirac}


def print_workspaces(workspaces: dict[str, Path]) -> None:
    print("=== B-matrix pipeline workspaces ===")
    for name in ["bflow", "vbal", "hdiag", "nicas", "so", "dirac"]:
        print(f"{name.upper()}={workspaces[name]}")


def validate_pipeline(workspaces: dict[str, Path]) -> None:
    validate_vbal(workspaces["vbal"])
    validate_hdiag(workspaces["hdiag"])
    validate_nicas(workspaces["nicas"])
    validate_so(workspaces["so"], variant="default")
    validate_dirac(workspaces["dirac"])


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mpasbcov-pipeline",
        description="Valida os workspaces do smoke test da matriz B global",
    )
    p.add_argument("--config", default=DEFAULT_CONFIG)
    p.add_argument("--bflow-workspace", required=True)
    p.add_argument("--vbal-workspace")
    p.add_argument("--hdiag-workspace")
    p.add_argument("--nicas-workspace")
    p.add_argument("--so-workspace")
    p.add_argument("--dirac-workspace")
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    config = load_config(args.config)
    workspaces = resolve_workspaces(config, args)
    print_workspaces(workspaces)
    validate_pipeline(workspaces)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
