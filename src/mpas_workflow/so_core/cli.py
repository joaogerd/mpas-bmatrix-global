from __future__ import annotations

import argparse
from pathlib import Path

from ..config import load_config
from .model import SO_VARIANTS
from .runner import prepare, submit, validate

DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpasso", description="Prepara, submete e valida a etapa SO")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--nicas-workspace", required=True)
    prep.add_argument("--hdiag-workspace")
    prep.add_argument("--vbal-workspace")
    prep.add_argument("--workspace")
    prep.add_argument("--variant", choices=SO_VARIANTS, default="default")
    prep.add_argument("--clean", action="store_true")
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("submit")
    run.add_argument("--workspace", required=True)
    run.add_argument("--variant", choices=SO_VARIANTS, default="default")
    run.add_argument("--wait", action="store_true")
    run.add_argument("--poll-seconds", type=int, default=30)
    run.set_defaults(func=submit_command)

    val = sub.add_parser("validate")
    val.add_argument("--workspace", required=True)
    val.add_argument("--variant", choices=SO_VARIANTS, default="default")
    val.set_defaults(func=validate_command)
    return p


def prepare_command(args) -> int:
    config = load_config(args.config)
    prepare(
        config,
        args.nicas_workspace,
        hdiag_workspace=args.hdiag_workspace,
        vbal_workspace=args.vbal_workspace,
        workspace=args.workspace,
        clean=args.clean,
        variant=args.variant,
    )
    return 0


def submit_command(args) -> int:
    print(submit(Path(args.workspace), wait=args.wait, poll_seconds=args.poll_seconds, variant=args.variant))
    return 0


def validate_command(args) -> int:
    validate(Path(args.workspace), variant=args.variant)
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
