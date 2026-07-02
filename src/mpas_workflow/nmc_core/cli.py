"""CLI for validating producer-supplied NMC campaign manifests."""
from __future__ import annotations

import argparse
import json

from .checks import validate_manifest
from .model import MINIMUM_PAIRS


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="mpasnmc",
        description="Valida manifestos NMC f048/f024 antes do BFLOW.",
    )
    sub = result.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-manifest", help="confere pares, cronologia e arquivos mpasout")
    validate.add_argument("--manifest", required=True)
    validate.add_argument("--minimum-pairs", type=int, default=MINIMUM_PAIRS)
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.command == "validate-manifest":
        print(json.dumps(validate_manifest(args.manifest, minimum_pairs=args.minimum_pairs), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
