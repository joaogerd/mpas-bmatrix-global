from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .wps import run_ungrib, ungrib_run_dir
from .mpas_init import prepare_init, submit_init, validate_init, init_file
from .forecast import prepare_forecast, submit_forecast
from .nmc import prepare_pair, validate_pair, diff_pair, parse_variables_arg


DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


def parser():
    p = argparse.ArgumentParser(prog="mpaswf", description="Workflow Python para MPAS global")
    p.add_argument("--config", default=DEFAULT_CONFIG)
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("ungrib")
    u.add_argument("--init-time", required=True)
    u.add_argument("--fhour", default="000")
    u.add_argument("--no-download", action="store_true")

    init = sub.add_parser("init")
    init_sub = init.add_subparsers(dest="init_cmd", required=True)

    ip = init_sub.add_parser("prepare")
    ip.add_argument("--init-time", required=True)
    ip.add_argument("--wps-file")

    isub = init_sub.add_parser("submit")
    isub.add_argument("--init-time", required=True)

    iv = init_sub.add_parser("validate")
    iv.add_argument("--init-time", required=True)

    fc = sub.add_parser("forecast")
    fc_sub = fc.add_subparsers(dest="forecast_cmd", required=True)

    fp = fc_sub.add_parser("prepare")
    fp.add_argument("--init-time", required=True)
    fp.add_argument("--lead-hours", type=int, required=True)
    fp.add_argument("--dt", type=int)
    fp.add_argument("--output-interval")

    fs = fc_sub.add_parser("submit")
    fs.add_argument("--init-time", required=True)
    fs.add_argument("--lead-hours", type=int, required=True)
    fs.add_argument("--dt", type=int)

    nmc = sub.add_parser("nmc")
    nmc_sub = nmc.add_subparsers(dest="nmc_cmd", required=True)

    pair = nmc_sub.add_parser("pair")
    pair.add_argument("--old-init-time", required=True)
    pair.add_argument("--new-init-time", required=True)
    pair.add_argument("--valid-time", required=True)
    pair.add_argument("--dt", type=int)

    val = nmc_sub.add_parser("validate")
    val.add_argument("--valid-time", required=True)
    val.add_argument("--no-strict", action="store_true")

    diff = nmc_sub.add_parser("diff")
    diff.add_argument("--valid-time", required=True)
    diff.add_argument("--variables")
    diff.add_argument("--output")

    one = nmc_sub.add_parser("one-pair")
    one.add_argument("--old-init-time", required=True)
    one.add_argument("--new-init-time", required=True)
    one.add_argument("--valid-time", required=True)
    one.add_argument("--dt", type=int)
    one.add_argument("--submit", action="store_true")

    return p


def main(argv=None):
    args = parser().parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "ungrib":
        run_ungrib(cfg, args.init_time, args.fhour, download=not args.no_download)
        return

    if args.cmd == "init":
        if args.init_cmd == "prepare":
            wps_file = args.wps_file
            if not wps_file:
                wps_file = ungrib_run_dir(cfg, args.init_time) / f"FILE:{args.init_time[:13]}"
            prepare_init(cfg, args.init_time, Path(wps_file))
        elif args.init_cmd == "submit":
            submit_init(cfg, args.init_time)
        elif args.init_cmd == "validate":
            validate_init(cfg, args.init_time)
        return

    if args.cmd == "forecast":
        if args.forecast_cmd == "prepare":
            prepare_forecast(cfg, args.init_time, args.lead_hours, args.dt, args.output_interval)
        elif args.forecast_cmd == "submit":
            submit_forecast(cfg, args.init_time, args.lead_hours, args.dt)
        return

    if args.cmd == "nmc":
        if args.nmc_cmd == "pair":
            prepare_pair(cfg, args.old_init_time, args.new_init_time, args.valid_time, args.dt)
        elif args.nmc_cmd == "validate":
            validate_pair(cfg, args.valid_time, strict=not args.no_strict)
        elif args.nmc_cmd == "diff":
            diff_pair(
                cfg,
                args.valid_time,
                variables=parse_variables_arg(args.variables),
                output=args.output,
            )
        elif args.nmc_cmd == "one-pair":
            # Orquestração idempotente: prepara tudo que falta e submete se solicitado.
            dt = args.dt or cfg["runtime"]["config_dt"]

            for init_time in [args.old_init_time, args.new_init_time]:
                try:
                    validate_init(cfg, init_time)
                except SystemExit:
                    print(f"Init ausente ou inválido para {init_time}; preparando.")
                    run_ungrib(cfg, init_time)
                    prepare_init(cfg, init_time, ungrib_run_dir(cfg, init_time) / f"FILE:{init_time[:13]}")
                    if args.submit:
                        submit_init(cfg, init_time)
                        print("Job de init submetido. Rode o mesmo comando novamente após terminar.")
                        return

            jobs = [(args.old_init_time, 48), (args.new_init_time, 24)]
            from .forecast import restart_file
            for init_time, lead in jobs:
                rf = restart_file(cfg, init_time, lead, dt)
                if not rf.exists():
                    prepare_forecast(cfg, init_time, lead, dt)
                    if args.submit:
                        submit_forecast(cfg, init_time, lead, dt)
                        print("Job de forecast submetido. Rode o mesmo comando novamente após terminar.")
                        return

            prepare_pair(cfg, args.old_init_time, args.new_init_time, args.valid_time, dt)
        return
