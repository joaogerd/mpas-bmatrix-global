"""Command-line interface for the MPAS case renderer.

Kept separate from the rendering implementation so command-line presentation
and argument parsing stay small, testable, and independent from artifact
rendering.
"""
from __future__ import annotations

import argparse
from typing import Any

from .case_config import CaseConfigError, load_case_config
from .case_render import RenderError, _time_context, render_stage


def _parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--set deve usar o formato CHAVE=VALOR.")
    key, raw = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("--set exige uma chave não vazia.")
    return key, raw


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        prog="mpas-render",
        description="Renderiza namelist e streams MPAS a partir de um caso YAML agnóstico.",
    )
    value.add_argument("--case", required=True, help="Diretório do caso ou arquivo case.yaml")
    value.add_argument("--stage", required=True, help="Estágio declarado em stages.<nome>")
    value.add_argument("--output-dir", help="Sobrescreve stages.<nome>.output_dir")
    value.add_argument(
        "--init-time",
        help="Data inicial no formato %%Y-%%m-%%d_%%H:%%M:%%S",
    )
    value.add_argument("--lead-hours", type=int)
    value.add_argument("--dt", type=int)
    value.add_argument("--set", dest="assignments", action="append", type=_parse_assignment, default=[])
    value.add_argument("--dry-run", action="store_true", help="Mostra os artefatos planejados sem gravá-los")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    overrides: dict[str, Any] = _time_context(args.init_time, args.lead_hours, args.dt)
    overrides.update(dict(args.assignments))

    try:
        result = render_stage(
            load_case_config(args.case),
            args.stage,
            overrides=overrides,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
    except (CaseConfigError, RenderError) as exc:
        raise SystemExit(f"ERRO: {exc}") from exc

    prefix = "PLANO" if args.dry_run else "OK"
    print(f"{prefix}: caso={result.case_name} estágio={result.stage}")
    print(f"  OUTPUT_DIR={result.output_dir}")
    for path in result.outputs:
        print(f"  OUTPUT={path}")
    print(f"  MANIFEST={result.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
