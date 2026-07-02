from __future__ import annotations

import argparse
from pathlib import Path

from ..config import load_config
from ..nmc_core.model import MINIMUM_PAIRS
from .manifest import read_manifest
from .model import DEFAULT_CONFIG, BflowPair, build_pairs_from_range, default_workspace
from .runner import run_bflow_pipeline
from .workspace import prepare_workspace


def pairs_from_args(args, config) -> tuple[list[BflowPair], str, str]:
    dt = int(args.dt or config["runtime"]["config_dt"])
    if getattr(args, "manifest", None):
        pairs = read_manifest(args.manifest)
        start = pairs[0].valid_time
        end = pairs[-1].valid_time
    else:
        if not args.start_valid_time or not args.end_valid_time:
            raise SystemExit("ERRO: informe --manifest ou --start-valid-time e --end-valid-time.")
        pairs = build_pairs_from_range(config, args.start_valid_time, args.end_valid_time, args.valid_interval_hours, dt)
        start = args.start_valid_time
        end = args.end_valid_time

    minimum_pairs = int(getattr(args, "minimum_pairs", 1))
    if minimum_pairs < 1:
        raise SystemExit("ERRO: --minimum-pairs deve ser um inteiro positivo.")
    if len(pairs) < minimum_pairs:
        raise SystemExit(
            f"ERRO: manifesto/range possui {len(pairs)} pares, mas --minimum-pairs exige {minimum_pairs}."
        )
    return pairs, start, end


def workspace_from_args(args, config, start: str, end: str) -> Path:
    return Path(args.workspace) if getattr(args, "workspace", None) else default_workspace(config, start, end)


def prepare_command(args) -> int:
    config = load_config(args.config)
    pairs, start, end = pairs_from_args(args, config)
    workspace = prepare_workspace(
        config,
        pairs,
        workspace_from_args(args, config, start, end),
        force=args.force,
        minimum_pairs=args.minimum_pairs,
    )
    print("=== Bflow preprocessing workspace ===")
    print(f"WORKSPACE={workspace}")
    print(f"MANIFEST={workspace / 'manifest.tsv'}")
    print(f"PAIRS={len(pairs)}")
    print()
    print("Para rodar:")
    print(f"  mpasbflow run --config {args.config} --workspace {workspace} --clean-output")
    return 0


def run_command(args) -> int:
    config = load_config(args.config)
    run_bflow_pipeline(config, Path(args.workspace), clean_output=args.clean_output, skip_weights=args.skip_weights)
    return 0


def all_command(args) -> int:
    config = load_config(args.config)
    pairs, start, end = pairs_from_args(args, config)
    workspace = prepare_workspace(
        config,
        pairs,
        workspace_from_args(args, config, start, end),
        force=args.force,
        minimum_pairs=args.minimum_pairs,
    )
    print("=== Bflow preprocessing all ===")
    print(f"WORKSPACE={workspace}")
    print(f"PAIRS={len(pairs)}")
    print(f"LOGDIR={workspace / 'logs'}")
    print()
    run_bflow_pipeline(config, workspace, pairs=pairs, clean_output=args.clean_output, skip_weights=args.skip_weights)
    return 0


def add_common_range_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--start-valid-time")
    parser.add_argument("--end-valid-time")
    parser.add_argument("--valid-interval-hours", type=int, default=24)
    parser.add_argument("--dt", type=int)
    parser.add_argument("--manifest")
    parser.add_argument("--workspace")
    parser.add_argument("--minimum-pairs", type=int, default=MINIMUM_PAIRS)
    parser.add_argument("--force", action="store_true")


def parser():
    p = argparse.ArgumentParser(prog="mpasbflow", description="Prepara e executa o Bflow preprocessing do MPAS-JEDI")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare", help="Cria workspace BFLOW a partir do range ou manifesto")
    add_common_range_args(prep)
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("run", help="Executa o pipeline Python em um workspace já preparado")
    run.add_argument("--config", default=DEFAULT_CONFIG)
    run.add_argument("--workspace", required=True)
    run.add_argument("--clean-output", action="store_true")
    run.add_argument("--skip-weights", action="store_true")
    run.set_defaults(func=run_command)

    allp = sub.add_parser("all", help="Prepara, limpa opcionalmente, executa e valida o Bflow de ponta a ponta")
    add_common_range_args(allp)
    allp.add_argument("--clean-output", action="store_true")
    allp.add_argument("--skip-weights", action="store_true")
    allp.set_defaults(func=all_command)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    return args.func(args)
