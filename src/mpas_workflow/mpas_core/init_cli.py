from __future__ import annotations

import argparse

from ..config import load_config
from . import init as mpas_init
from .wps import resolve_wps_file

DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpasinit", description="Prepara, submete e valida MPAS init")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("prepare", "submit", "validate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", default=DEFAULT_CONFIG)
        cmd.add_argument("--init-time", required=True)
        if name == "prepare":
            cmd.add_argument("--wps-file")
            cmd.add_argument("--wps-dir")
            cmd.add_argument("--wps-template")
        if name == "submit":
            cmd.add_argument("--wait", action="store_true")
            cmd.add_argument("--poll-seconds", type=int, default=30)
        cmd.set_defaults(func=globals()[f"{name}_command"])
    return p


def prepare_command(args) -> int:
    config = load_config(args.config)
    wps_file = resolve_wps_file(
        config,
        args.init_time,
        wps_file=args.wps_file,
        wps_dir=args.wps_dir,
        wps_template=args.wps_template,
    )
    mpas_init.prepare(config, args.init_time, wps_file)
    return 0


def submit_command(args) -> int:
    config = load_config(args.config)
    print(
        mpas_init.submit(
            config,
            args.init_time,
            wait=args.wait,
            poll_seconds=args.poll_seconds,
        )
    )
    return 0


def validate_command(args) -> int:
    config = load_config(args.config)
    mpas_init.validate(config, args.init_time)
    return 0


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
