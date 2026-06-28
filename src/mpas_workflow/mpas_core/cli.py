from __future__ import annotations

import argparse

from ..config import load_config
from .runner import prepare, submit

DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpasforecast", description="Prepara e submete forecasts MPAS para o fluxo NMC/BFLOW")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--init-time", required=True)
    prep.add_argument("--lead-hours", type=int, required=True)
    prep.add_argument("--dt", type=int)
    prep.add_argument("--output-interval")
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("submit")
    run.add_argument("--config", default=DEFAULT_CONFIG)
    run.add_argument("--init-time", required=True)
    run.add_argument("--lead-hours", type=int, required=True)
    run.add_argument("--dt", type=int)
    run.add_argument("--wait", action="store_true", help="monitora o job PBS até ele sair do qstat")
    run.add_argument("--poll-seconds", type=int, default=30, help="intervalo de monitoramento quando --wait é usado")
    run.set_defaults(func=submit_command)
    return p


def prepare_command(args) -> int:
    config = load_config(args.config)
    prepare(config, args.init_time, args.lead_hours, dt=args.dt, output_interval=args.output_interval)
    return 0


def submit_command(args) -> int:
    config = load_config(args.config)
    print(
        submit(
            config,
            args.init_time,
            args.lead_hours,
            dt=args.dt,
            wait=args.wait,
            poll_seconds=args.poll_seconds,
        )
    )
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
