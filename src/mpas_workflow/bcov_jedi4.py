"""JEDI-4 canonical B-matrix runner.

This entry point reuses the configured covariance workflow, but suppresses
geometry aliases when the selected B-matrix contract already uses identical
canonical JEDI and physical NetCDF variable names.
"""
from __future__ import annotations

from . import bcov_configured as configured
from .bcov_configured import BMatrixContract

_LEGACY_GEOMETRY_YAML = configured._geometry_yaml


def _geometry_yaml(
    contract: BMatrixContract,
    indent: int,
    *,
    deallocate: bool = False,
    bump_vunit: str | None = None,
    include_alias: bool = True,
) -> str:
    """Render geometry without aliases for canonical JEDI-4 contracts."""
    canonical = all(item["code"] == item["file"] for item in contract.controls)
    return _LEGACY_GEOMETRY_YAML(
        contract,
        indent,
        deallocate=deallocate,
        bump_vunit=bump_vunit,
        include_alias=include_alias and not canonical,
    )


def main() -> int:
    configured._geometry_yaml = _geometry_yaml
    return configured.main()
