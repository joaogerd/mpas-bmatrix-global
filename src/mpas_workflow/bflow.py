from __future__ import annotations

"""Compatibility entrypoint for the BFLOW command.

The implementation was moved to :mod:`mpas_workflow.bflow_core` so the BFLOW
workflow is a Python pipeline instead of a Python file that writes helper
Python scripts and a master shell script.
"""

from .bflow_core.cli import (
    add_common_range_args,
    all_command,
    main,
    pairs_from_args,
    parser,
    prepare_command,
    run_command,
    workspace_from_args,
)
from .bflow_core.manifest import read_manifest, write_manifest
from .bflow_core.model import (
    DEFAULT_CONFIG,
    TIME_FORMAT,
    BflowPair,
    build_pairs_from_range,
    compact_time,
    default_workspace,
    format_time,
    iter_valid_times,
    parse_time,
)
from .bflow_core.runner import run_bflow_pipeline as run_workspace
from .bflow_core.workspace import link_pair_inputs, prepare_workspace, validate_pairs

__all__ = [
    "DEFAULT_CONFIG",
    "TIME_FORMAT",
    "BflowPair",
    "add_common_range_args",
    "all_command",
    "build_pairs_from_range",
    "compact_time",
    "default_workspace",
    "format_time",
    "iter_valid_times",
    "link_pair_inputs",
    "main",
    "pairs_from_args",
    "parse_time",
    "parser",
    "prepare_command",
    "prepare_workspace",
    "read_manifest",
    "run_command",
    "run_workspace",
    "validate_pairs",
    "workspace_from_args",
    "write_manifest",
]


if __name__ == "__main__":
    raise SystemExit(main())
