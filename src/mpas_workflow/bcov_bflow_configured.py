"""BFLOW-aware covariance command."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from . import bcov
from .bcov_configured import apply_contract, load_contract_from_argv
from .bflow_configured import BFlowConfiguration
from .shell import require_file


def products_from_bflow_workspace(workspace: Path, configuration: BFlowConfiguration) -> dict[str, str]:
    snapshot = workspace / "bflow_config.json"
    if not snapshot.is_file():
        return {
            "perturbation": configuration.products["perturbation"],
            "newer_full": configuration.products["newer_full"],
        }
    payload = json.loads(snapshot.read_text())
    products = payload["products"]
    return {
        "perturbation": products["perturbation"],
        "newer_full": products["newer_full"],
    }


def read_bflow_samples(workspace_path: str | Path, configuration: BFlowConfiguration):
    workspace = Path(workspace_path)
    manifest = require_file(workspace / "manifest.tsv", "Bflow manifest.tsv")
    products = products_from_bflow_workspace(workspace, configuration)
    samples = []
    with manifest.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            output = workspace / "output" / bcov.compact_time(row["valid_time"])
            samples.append(
                bcov.Sample(
                    row["valid_time"],
                    require_file(output / products["perturbation"], "PTB"),
                    require_file(output / products["newer_full"], "FULL recente"),
                    require_file(row["f024"], "forecast recente"),
                )
            )
    if not samples:
        raise SystemExit("ERRO: nenhum sample Bflow encontrado.")
    return samples


def main() -> int:
    _, contract = load_contract_from_argv()
    configuration = BFlowConfiguration.from_contract(contract)
    apply_contract(bcov, contract)

    def reader(workspace_path):
        return read_bflow_samples(workspace_path, configuration)

    bcov.read_bflow_samples = reader
    return bcov.main()
