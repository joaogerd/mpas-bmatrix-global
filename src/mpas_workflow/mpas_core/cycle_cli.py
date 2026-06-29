from __future__ import annotations

import argparse
from pathlib import Path

from ..config import load_config
from .cycle import ForecastRequest, ensure_forecast_cycle, ensure_nmc_pair, ensure_nmc_pair_range

DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--dt", type=int, help="passo de tempo MPAS em segundos; se omitido usa runtime.config_dt")
    parser.add_argument("--wps-dir")
    parser.add_argument("--wps-template")
    parser.add_argument("--output-interval")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=30)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpascycle", description="Executa ciclos MPAS init+forecast e pares NMC")
    sub = p.add_subparsers(dest="cmd", required=True)

    cycle = sub.add_parser("forecast")
    add_common(cycle)
    cycle.add_argument("--init-time", required=True)
    cycle.add_argument("--lead-hours", type=int, required=True)
    cycle.add_argument("--wps-file")
    cycle.set_defaults(func=forecast_command)

    pair = sub.add_parser("nmc-pair")
    add_common(pair)
    pair.add_argument("--valid-time", required=True)
    pair.set_defaults(func=nmc_pair_command)

    rng = sub.add_parser("nmc-range")
    add_common(rng)
    rng.add_argument("--start-valid-time", required=True)
    rng.add_argument("--end-valid-time", required=True)
    rng.add_argument("--valid-interval-hours", type=int, default=24)
    rng.add_argument("--manifest")
    rng.set_defaults(func=nmc_range_command)
    return p


def dt_value(config, args) -> int:
    return int(args.dt or config["runtime"]["config_dt"])


def forecast_command(args) -> int:
    config = load_config(args.config)
    ensure_forecast_cycle(
        config,
        ForecastRequest(args.init_time, args.lead_hours),
        dt=dt_value(config, args),
        wps_file=args.wps_file,
        wps_dir=args.wps_dir,
        wps_template=args.wps_template,
        output_interval=args.output_interval,
        submit=args.submit,
        wait=args.wait,
        force=args.force,
        poll_seconds=args.poll_seconds,
    )
    return 0


def nmc_pair_command(args) -> int:
    config = load_config(args.config)
    ensure_nmc_pair(
        config,
        args.valid_time,
        dt=dt_value(config, args),
        wps_dir=args.wps_dir,
        wps_template=args.wps_template,
        output_interval=args.output_interval,
        submit=args.submit,
        wait=args.wait,
        force=args.force,
        poll_seconds=args.poll_seconds,
    )
    return 0


def nmc_range_command(args) -> int:
    config = load_config(args.config)
    ensure_nmc_pair_range(
        config,
        start_valid_time=args.start_valid_time,
        end_valid_time=args.end_valid_time,
        valid_interval_hours=args.valid_interval_hours,
        dt=dt_value(config, args),
        manifest=Path(args.manifest) if args.manifest else None,
        wps_dir=args.wps_dir,
        wps_template=args.wps_template,
        output_interval=args.output_interval,
        submit=args.submit,
        wait=args.wait,
        force=args.force,
        poll_seconds=args.poll_seconds,
    )
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
