from __future__ import annotations

import shutil
from pathlib import Path

from .diff import diff_pairs
from .manifest import read_manifest
from .model import BflowPair, compact_time
from .psichi import convert_uv_to_psichi
from .template import generate_template_ptb
from .validate import validate_products
from .variables import add_variables_for_pairs
from .weights import generate_esmf_weights


def clean_outputs(workspace: Path) -> None:
    output = workspace / "output"
    if output.exists():
        print("Cleaning output directory")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def load_workspace_pairs(workspace: Path) -> list[BflowPair]:
    return read_manifest(workspace / "manifest.tsv")


def list_ptb_samples(workspace: Path, pairs: list[BflowPair]) -> list[Path]:
    return [workspace / "output" / compact_time(pair.valid_time) / "PTB_f48mf24.nc" for pair in pairs]


def run_bflow_pipeline(
    config,
    workspace: Path,
    pairs: list[BflowPair] | None = None,
    clean_output: bool = False,
    skip_weights: bool = False,
) -> list[Path]:
    workspace = Path(workspace)
    pairs = pairs or load_workspace_pairs(workspace)
    (workspace / "logs").mkdir(parents=True, exist_ok=True)
    (workspace / "output").mkdir(parents=True, exist_ok=True)

    if clean_output:
        clean_outputs(workspace)

    if not skip_weights:
        generate_esmf_weights(config, workspace)
    else:
        print("Skipping ESMF weights because --skip-weights was requested")

    generate_template_ptb(pairs[0].f048, workspace)
    convert_uv_to_psichi(config, workspace, pairs)
    validate_products(workspace, pairs, stage="full")
    add_variables_for_pairs(workspace, pairs)
    diff_pairs(workspace, pairs)
    validate_products(workspace, pairs, stage="ptb")

    samples = list_ptb_samples(workspace, pairs)
    for sample in samples:
        print(sample)
    return samples
