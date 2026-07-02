from __future__ import annotations

import argparse
from pathlib import Path

from ..config import load_config
from .runner import prepare, submit, validate

DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpasnicas", description="Prepara, submete e valida a etapa NICAS")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--hdiag-workspace", required=True)
    prep.add_argument("--workspace")
    prep.add_argument("--clean", action="store_true")
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("submit")
    run.add_argument("--workspace", required=True)
    run.add_argument("--wait", action="store_true")
    run.add_argument("--poll-seconds", type=int, default=30)
    run.add_argument("--parallel", action="store_true")
    run.add_argument("--retries", type=int, default=2)
    run.set_defaults(func=submit_command)

    val = sub.add_parser("validate")
    val.add_argument("--workspace", required=True)
    val.set_defaults(func=validate_command)
    return p


def prepare_command(args) -> int:
    config = load_config(args.config)
    prepare(config, args.hdiag_workspace, workspace=args.workspace, clean=args.clean)
    return 0


def submit_command(args) -> int:
    print(
        submit(
            Path(args.workspace),
            wait=args.wait,
            poll_seconds=args.poll_seconds,
            parallel=args.parallel,
            retries=args.retries,
        )
    )
    return 0


def validate_command(args) -> int:
    validate(Path(args.workspace))
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
