from __future__ import annotations

"""Compatibility entry point for the BFLOW command.

The implementation was moved to :mod:`mpas_workflow.bflow_core` so the BFLOW
workflow is now orchestrated as a Python pipeline instead of a Python file that
writes helper Python scripts and a master shell script.
"""

from pathlib import Path

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
from .bflow_core.runner import run_bflow_pipeline
from .bflow_core.workspace import link_pair_inputs, prepare_workspace, validate_pairs
from .config import load_config


def run_workspace(workspace: Path, clean_output: bool = False, skip_weights: bool = False, config=None) -> int:
    """Run a prepared BFLOW workspace.

    Kept for callers that imported ``mpas_workflow.bflow.run_workspace`` before
    the refactor. New code should prefer ``bflow_core.runner.run_bflow_pipeline``.
    """
    cfg = config if config is not None else load_config(DEFAULT_CONFIG)
    run_bflow_pipeline(cfg, Path(workspace), clean_output=clean_output, skip_weights=skip_weights)
    return 0


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
