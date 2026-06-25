"""Command-line interface for declarative MPAS runtime preparation."""
from __future__ import annotations

import argparse
from typing import Any

from .case_config import CaseConfigError, load_case_config
from .case_render import RenderError, _time_context
from .runtime_prepare import RuntimePrepareError, prepare_stage


def _parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--set deve usar o formato CHAVE=VALOR.")
    key, raw = value.split("=", 1)
    if not key:
        raise argparse.ArgumentTypeError("--set exige uma chave não vazia.")
    return key, raw


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        prog="mpas-stage-prepare",
        description="Prepara links de runtime MPAS a partir de um caso YAML renderizado.",
    )
    value.add_argument("--case", required=True, help="Arquivo YAML ou diretório do caso MPAS")
    value.add_argument("--stage", required=True, help="Estágio declarado em stages.<nome>.runtime")
    value.add_argument("--output-dir", help="Sobrescreve runtime.output_dir")
    value.add_argument("--init-time", help="Data inicial no formato %Y-%m-%d_%H:%M:%S")
    value.add_argument("--lead-hours", type=int)
    value.add_argument("--dt", type=int)
    value.add_argument("--set", dest="assignments", action="append", type=_parse_assignment, default=[])
    value.add_argument("--dry-run", action="store_true", help="Valida e mostra o plano sem criar links")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    overrides: dict[str, Any] = _time_context(args.init_time, args.lead_hours, args.dt)
    overrides.update(dict(args.assignments))

    try:
        result = prepare_stage(
            load_case_config(args.case),
            args.stage,
            overrides=overrides,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
    except (CaseConfigError, RenderError, RuntimePrepareError) as exc:
        raise SystemExit(f"ERRO: {exc}") from exc

    prefix = "PLANO" if args.dry_run else "OK"
    print(f"{prefix}: caso={result.case_name} estágio={result.stage}")
    print(f"  RUNTIME_DIR={result.output_dir}")
    print(f"  EXECUTABLE={result.executable}")
    for link in result.links:
        print(f"  LINK={link.destination} -> {link.source}")
    print(f"  MANIFEST={result.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
