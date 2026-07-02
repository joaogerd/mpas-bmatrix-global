from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mpasnmc")
    parser.add_argument("command", choices=["validate-manifest"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--minimum-pairs", type=int, default=4)
    args = parser.parse_args(argv)
    path = Path(args.manifest)
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if len(rows) < args.minimum_pairs:
        raise SystemExit(f"ERRO: manifesto possui {len(rows)} pares; mínimo: {args.minimum_pairs}.")
    pairs = []
    for row in rows:
        f048, f024 = Path(row["f048"]), Path(row["f024"])
        if not f048.is_file() or not f024.is_file() or not f048.stat().st_size or not f024.stat().st_size:
            raise SystemExit("ERRO: manifesto contém produto ausente ou vazio.")
        pairs.append({"valid_time": row["valid_time"], "f048": {"path": str(f048), "bytes": f048.stat().st_size}, "f024": {"path": str(f024), "bytes": f024.stat().st_size}})
    print(json.dumps({"manifest": str(path), "minimum_pairs": args.minimum_pairs, "pair_count": len(rows), "pairs": pairs, "valid": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
