from __future__ import annotations

import argparse
from pathlib import Path

from ..config import load_config
from .processperts import prepare_process, submit_process, validate_process
from .runner import prepare, submit, validate

DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpasvbal", description="Prepara, submete e valida a etapa VBAL")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--bflow-workspace", required=True)
    prep.add_argument("--workspace")
    prep.add_argument("--clean", action="store_true")
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("submit")
    run.add_argument("--workspace", required=True)
    run.add_argument("--wait", action="store_true")
    run.add_argument("--poll-seconds", type=int, default=30)
    run.set_defaults(func=submit_command)

    val = sub.add_parser("validate")
    val.add_argument("--workspace", required=True)
    val.set_defaults(func=validate_command)

    proc_prep = sub.add_parser(
        "process-prepare",
        help="prepara ProcessPerts para materializar amostras unbalanced via K2^-1",
    )
    proc_prep.add_argument("--config", default=DEFAULT_CONFIG)
    proc_prep.add_argument("--workspace", required=True)
    proc_prep.add_argument("--clean", action="store_true")
    proc_prep.set_defaults(func=process_prepare_command)

    proc_run = sub.add_parser("process-submit", help="submete ProcessPerts das amostras unbalanced")
    proc_run.add_argument("--workspace", required=True)
    proc_run.add_argument("--wait", action="store_true")
    proc_run.add_argument("--poll-seconds", type=int, default=30)
    proc_run.set_defaults(func=process_submit_command)

    proc_val = sub.add_parser("process-validate", help="valida amostras unbalanced materializadas")
    proc_val.add_argument("--workspace", required=True)
    proc_val.set_defaults(func=process_validate_command)
    return p


def prepare_command(args) -> int:
    config = load_config(args.config)
    prepare(config, args.bflow_workspace, workspace=args.workspace, clean=args.clean)
    return 0


def submit_command(args) -> int:
    print(submit(Path(args.workspace), wait=args.wait, poll_seconds=args.poll_seconds))
    return 0


def validate_command(args) -> int:
    validate(Path(args.workspace))
    return 0


def process_prepare_command(args) -> int:
    config = load_config(args.config)
    prepare_process(config, args.workspace, clean=args.clean)
    return 0


def process_submit_command(args) -> int:
    print(submit_process(Path(args.workspace), wait=args.wait, poll_seconds=args.poll_seconds))
    return 0


def process_validate_command(args) -> int:
    validate_process(Path(args.workspace))
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
