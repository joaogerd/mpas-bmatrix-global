from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from .config import load_config
from .wps import run_ungrib, ungrib_run_dir
from .mpas_init import prepare_init, submit_init, validate_init
from .forecast import prepare_forecast, submit_forecast, restart_file
from .nmc import prepare_pair, validate_pair, diff_pair, parse_variables_arg
from .shell import wait_for_pbs_job


DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"
TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def iter_times(start: str, end: str, step_hours: int):
    if step_hours <= 0:
        raise SystemExit("ERRO: --valid-interval-hours deve ser positivo.")

    current = parse_time(start)
    last = parse_time(end)
    step = timedelta(hours=step_hours)

    while current <= last:
        yield format_time(current)
        current += step


def nmc_times_from_valid_time(valid_time: str):
    valid = parse_time(valid_time)
    old_init_time = valid - timedelta(hours=48)
    new_init_time = valid - timedelta(hours=24)
    return format_time(old_init_time), format_time(new_init_time), valid_time


def ensure_init_ready(cfg, init_time: str, submit: bool = False, wait: bool = False, poll_seconds: int = 30) -> bool:
    try:
        validate_init(cfg, init_time)
        return True
    except SystemExit:
        print(f"Init ausente ou inválido para {init_time}; preparando.")

    run_ungrib(cfg, init_time)
    prepare_init(cfg, init_time, ungrib_run_dir(cfg, init_time) / f"FILE:{init_time[:13]}")

    if submit:
        jobid = submit_init(cfg, init_time)
        print(f"Job de init submetido: {jobid}")
        if wait:
            wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
            validate_init(cfg, init_time, jobid=jobid)
            return True
        print("Job de init submetido. Use --wait para continuar automaticamente após terminar.")
    else:
        print("Init preparado. Use --submit para submeter automaticamente.")

    return False


def ensure_forecast_ready(
    cfg,
    init_time: str,
    lead_hours: int,
    dt: int,
    submit: bool = False,
    wait: bool = False,
    poll_seconds: int = 30,
) -> bool:
    rf = restart_file(cfg, init_time, lead_hours, dt)
    if rf.exists():
        print(f"OK: forecast f{lead_hours:03d} existente: {rf}")
        return True

    prepare_forecast(cfg, init_time, lead_hours, dt)

    if submit:
        jobid = submit_forecast(cfg, init_time, lead_hours, dt)
        print(f"Job de forecast f{lead_hours:03d} submetido: {jobid}")
        if wait:
            wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
            if rf.exists():
                print(f"OK: forecast f{lead_hours:03d} concluído: {rf}")
                return True
            raise SystemExit(f"ERRO: forecast terminou, mas restart esperado não existe: {rf}")
        print("Job de forecast submetido. Use --wait para continuar automaticamente após terminar.")
    else:
        print("Forecast preparado. Use --submit para submeter automaticamente.")

    return False


def run_one_pair(
    cfg,
    old_init_time: str,
    new_init_time: str,
    valid_time: str,
    dt: int,
    submit: bool,
    wait: bool,
    poll_seconds: int,
    make_diff: bool,
    variables,
):
    for init_time in [old_init_time, new_init_time]:
        if not ensure_init_ready(cfg, init_time, submit=submit, wait=wait, poll_seconds=poll_seconds):
            return False

    if not ensure_forecast_ready(cfg, old_init_time, 48, dt, submit=submit, wait=wait, poll_seconds=poll_seconds):
        return False

    if not ensure_forecast_ready(cfg, new_init_time, 24, dt, submit=submit, wait=wait, poll_seconds=poll_seconds):
        return False

    prepare_pair(cfg, old_init_time, new_init_time, valid_time, dt)
    validate_pair(cfg, valid_time, strict=True)

    if make_diff:
        diff_pair(cfg, valid_time, variables=variables)

    print(f"SUCCESS: par NMC completo para VALID_TIME={valid_time}.")
    return True


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

    cycle = sub.add_parser("cycle")
    cycle_sub = cycle.add_subparsers(dest="cycle_cmd", required=True)

    cr = cycle_sub.add_parser("run")
    cr.add_argument("--init-time", required=True)
    cr.add_argument("--lead-hours", type=int, required=True)
    cr.add_argument("--dt", type=int)
    cr.add_argument("--submit", action="store_true")
    cr.add_argument("--wait", action="store_true")
    cr.add_argument("--poll-seconds", type=int, default=30)

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
    one.add_argument("--wait", action="store_true")
    one.add_argument("--poll-seconds", type=int, default=30)
    one.add_argument("--diff", action="store_true")
    one.add_argument("--variables")

    rng = nmc_sub.add_parser("range")
    rng.add_argument("--start-valid-time", required=True)
    rng.add_argument("--end-valid-time", required=True)
    rng.add_argument("--valid-interval-hours", type=int, default=24)
    rng.add_argument("--dt", type=int)
    rng.add_argument("--submit", action="store_true")
    rng.add_argument("--wait", action="store_true")
    rng.add_argument("--poll-seconds", type=int, default=30)
    rng.add_argument("--diff", action="store_true")
    rng.add_argument("--variables")

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

    if args.cmd == "cycle":
        if args.cycle_cmd == "run":
            dt = int(args.dt or cfg["runtime"]["config_dt"])
            if not ensure_init_ready(
                cfg,
                args.init_time,
                submit=args.submit,
                wait=args.wait,
                poll_seconds=args.poll_seconds,
            ):
                return
            if not ensure_forecast_ready(
                cfg,
                args.init_time,
                args.lead_hours,
                dt,
                submit=args.submit,
                wait=args.wait,
                poll_seconds=args.poll_seconds,
            ):
                return
            print(f"SUCCESS: ciclo completo para {args.init_time} f{args.lead_hours:03d}.")
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
            dt = int(args.dt or cfg["runtime"]["config_dt"])
            run_one_pair(
                cfg,
                old_init_time=args.old_init_time,
                new_init_time=args.new_init_time,
                valid_time=args.valid_time,
                dt=dt,
                submit=args.submit,
                wait=args.wait,
                poll_seconds=args.poll_seconds,
                make_diff=args.diff,
                variables=parse_variables_arg(args.variables),
            )
        elif args.nmc_cmd == "range":
            dt = int(args.dt or cfg["runtime"]["config_dt"])
            variables = parse_variables_arg(args.variables)
            for valid_time in iter_times(
                args.start_valid_time,
                args.end_valid_time,
                args.valid_interval_hours,
            ):
                old_init_time, new_init_time, _ = nmc_times_from_valid_time(valid_time)
                print("\n=== NMC valid time ===")
                print(f"VALID_TIME={valid_time}")
                print(f"OLD_INIT_TIME={old_init_time}")
                print(f"NEW_INIT_TIME={new_init_time}")
                done = run_one_pair(
                    cfg,
                    old_init_time=old_init_time,
                    new_init_time=new_init_time,
                    valid_time=valid_time,
                    dt=dt,
                    submit=args.submit,
                    wait=args.wait,
                    poll_seconds=args.poll_seconds,
                    make_diff=args.diff,
                    variables=variables,
                )
                if not done:
                    print("Par ainda não concluído. Use --wait para continuar automaticamente após PBS terminar.")
                    break
        return
