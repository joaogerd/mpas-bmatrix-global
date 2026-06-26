from __future__ import annotations

"""Compatibility entry point for the BFLOW command.

The implementation lives in :mod:`mpas_workflow.bflow_core` so the BFLOW
workflow is now orchestrated as a Python pipeline instead of a Python file that
writes helper Python scripts and a master shell script.
"""

from .bflow_core import (
    BflowPair,
    BflowProducts,
    build_pairs_from_range,
    compact_time,
    default_workspace,
    format_time,
    iter_valid_times,
    main,
    parse_time,
    prepare_workspace,
    read_manifest,
    run_workspace,
    validate_pairs,
    write_manifest,
)

__all__ = [
    "BflowPair",
    "BflowProducts",
    "build_pairs_from_range",
    "compact_time",
    "default_workspace",
    "format_time",
    "iter_valid_times",
    "main",
    "parse_time",
    "prepare_workspace",
    "read_manifest",
    "run_workspace",
    "validate_pairs",
    "write_manifest",
]


if __name__ == "__main__":
    raise SystemExit(main())
