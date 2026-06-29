"""Command-line interface for shared MONAN site assets."""
from __future__ import annotations

import argparse
from typing import Sequence

from .case_config import CaseConfigError, load_case_config
from .site_assets import SiteAssetError, prepare_wps_geog_assets


def _overrides(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"--set deve usar CHAVE=VALOR: {raw}")
        key, value = raw.split("=", 1)
        if not key:
            raise ValueError(f"--set deve usar CHAVE=VALOR: {raw}")
        result[key] = value
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mpas-assets",
        description="Valida e materializa ativos compartilhados para casos MPAS.",
    )
    parser.add_argument("command", choices=("validate", "prepare"))
    parser.add_argument("--case", required=True, help="Arquivo YAML/JSON declarativo do caso MPAS.")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="CHAVE=VALOR",
        help="Sobrescreve uma chave simples do context do caso.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the site-assets command."""
    args = _parser().parse_args(argv)
    try:
        case = load_case_config(args.case)
        result = prepare_wps_geog_assets(
            case,
            overrides=_overrides(args.set),
            materialize=args.command == "prepare",
        )
        if result is None:
            raise SiteAssetError("O caso não declara assets.wps_geog.")
    except (CaseConfigError, SiteAssetError, ValueError) as exc:
        print(f"ERRO: {exc}")
        return 2

    action = "preparado" if result.materialized else "validado"
    print(f"OK: WPS_GEOG {action}: {result.view_root}")
    print(f"PROFILE={result.profile}")
    for item in result.required_files:
        print(f"OK: {item.relative_path} <- {item.source.name}")
    if result.materialized:
        print(f"MANIFEST={result.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
