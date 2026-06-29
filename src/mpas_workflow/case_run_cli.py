"""Command line interface for complete declarative MPAS cycles."""
from __future__ import annotations

import argparse

from .case_config import CaseConfigError, load_case_config
from .case_run import CaseRunError, ensure_cycle, ensure_nmc_pair, ensure_stage
from .case_wps import CaseWpsError


TIME_HELP = "UTC no formato YYYY-MM-DD_HH:MM:SS"


def _common(parser: argparse.ArgumentParser, *, lead: bool = False) -> None:
    parser.add_argument("--case", required=True, help="Caso YAML MPAS composto")
    parser.add_argument("--init-time", required=True, help=TIME_HELP)
    if lead:
        parser.add_argument("--lead-hours", required=True, type=int)
    parser.add_argument("--dt", required=True, type=int)
    parser.add_argument("--submit", action="store_true", help="Submete o PBS depois de preparar o runtime")
    parser.add_argument("--wait", action="store_true", help="Aguarda PBS e valida produtos esperados")
    parser.add_argument("--force", action="store_true", help="Remove as saídas do estágio e refaz")
    parser.add_argument("--no-download", action="store_true", help="Não baixa GFS quando o cache estiver ausente")
    parser.add_argument("--poll-seconds", type=int, default=30)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="mpas-cycle", description="Executa a cadeia MPAS declarativa")
    sub = value.add_subparsers(dest="command", required=True)

    for stage_name in ("static", "init"):
        stage = sub.add_parser(stage_name)
        _common(stage)
    forecast = sub.add_parser("forecast")
    _common(forecast, lead=True)
    cycle = sub.add_parser("cycle")
    _common(cycle, lead=True)

    pair = sub.add_parser("nmc-pair")
    pair.add_argument("--case", required=True)
    pair.add_argument("--valid-time", required=True, help=TIME_HELP)
    pair.add_argument("--dt", required=True, type=int)
    pair.add_argument("--submit", action="store_true")
    pair.add_argument("--wait", action="store_true")
    pair.add_argument("--force", action="store_true")
    pair.add_argument("--no-download", action="store_true")
    pair.add_argument("--poll-seconds", type=int, default=30)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        case = load_case_config(args.case)
        if args.command in {"static", "init", "forecast"}:
            lead_hours = getattr(args, "lead_hours", 0)
            done = ensure_stage(
                case,
                args.command,
                init_time=args.init_time,
                lead_hours=lead_hours,
                dt=args.dt,
                submit=args.submit,
                wait=args.wait,
                force=args.force,
                download=not args.no_download,
                poll_seconds=args.poll_seconds,
            )
            return 0 if done or not args.submit else 2
        if args.command == "cycle":
            done = ensure_cycle(
                case,
                init_time=args.init_time,
                lead_hours=args.lead_hours,
                dt=args.dt,
                submit=args.submit,
                wait=args.wait,
                force=args.force,
                download=not args.no_download,
                poll_seconds=args.poll_seconds,
            )
            return 0 if done or not args.submit else 2
        ensure_nmc_pair(
            case,
            valid_time=args.valid_time,
            dt=args.dt,
            submit=args.submit,
            wait=args.wait,
            force=args.force,
            download=not args.no_download,
            poll_seconds=args.poll_seconds,
        )
        return 0
    except (CaseConfigError, CaseRunError, CaseWpsError) as exc:
        raise SystemExit(f"ERRO: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
