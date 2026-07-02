"""Compatibility dispatcher for the pre-refactor ``mpaswf`` entry point.

The old monolithic CLI imported modules removed by ``refactor/bflow-python-pipeline``.
Forecast production now belongs to ``mpasforecast`` and NMC manifest validation to
``mpasnmc``.  The producer workflow owns downloads, WPS and MPAS initialization.
"""
from __future__ import annotations

import argparse
import sys

from .mpas_core.cli import main as forecast_main
from .nmc_core.cli import main as nmc_main


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="mpaswf",
        description="Compatibility dispatcher for the reorganized MPAS B-matrix tools.",
    )
    sub = result.add_subparsers(dest="tool", required=True)

    forecast = sub.add_parser("forecast", help="delegate to mpasforecast")
    forecast.add_argument("arguments", nargs=argparse.REMAINDER)

    nmc = sub.add_parser("nmc", help="delegate to mpasnmc")
    nmc.add_argument("arguments", nargs=argparse.REMAINDER)

    migration = sub.add_parser("migration", help="print the workflow migration guidance")
    migration.set_defaults(migration=True)
    return result


def _migration_message() -> str:
    return "\n".join(
        [
            "The monolithic mpaswf workflow was retired by refactor/bflow-python-pipeline.",
            "Use monan-jedi-workflow for input retrieval, WPS/UNGRIB, MPAS init and f024/f048 production.",
            "Use mpasnmc validate-manifest --manifest bflow-manifest.tsv before BFLOW.",
            "Use mpasbflow all --manifest bflow-manifest.tsv for preprocessing.",
            "Use mpasforecast prepare|submit only for direct MPAS forecast operations.",
        ]
    )


def main(argv=None) -> int:
    args = parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.tool == "forecast":
        return forecast_main(args.arguments)
    if args.tool == "nmc":
        return nmc_main(args.arguments)
    print(_migration_message())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
