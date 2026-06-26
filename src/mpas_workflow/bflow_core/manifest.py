from __future__ import annotations

import csv
from pathlib import Path

from ..shell import require_file
from .model import BflowPair


def read_manifest(path: str | Path) -> list[BflowPair]:
    path = Path(path)
    require_file(path, "manifest.tsv")
    pairs: list[BflowPair] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"valid_time", "f048", "f024"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise SystemExit(
                f"ERRO: manifesto {path} deve ter cabeçalho tabulado: valid_time, f048, f024"
            )
        for row in reader:
            pairs.append(BflowPair(row["valid_time"], Path(row["f048"]), Path(row["f024"])))
    return pairs


def write_manifest(path: str | Path, pairs: list[BflowPair]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["valid_time", "f048", "f024"], delimiter="\t")
        writer.writeheader()
        for pair in pairs:
            writer.writerow({"valid_time": pair.valid_time, "f048": str(pair.f048), "f024": str(pair.f024)})
    return path
