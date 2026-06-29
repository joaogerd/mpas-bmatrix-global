"""Bridge declarative MPAS cases to the established GFS/WPS implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .case_config import CaseConfig, CaseConfigError, resolve_context, resolve_structure
from .wps import run_ungrib, ungrib_run_dir


class CaseWpsError(ValueError):
    """Raised when a declarative case does not define usable WPS inputs."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaseWpsError(f"{label} deve ser um mapa YAML.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CaseWpsError(f"{label} deve ser uma string não vazia.")
    return value


def wps_adapter_config(case: CaseConfig, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build the compact config consumed by the existing, tested WPS module."""
    context = resolve_context(case, overrides)
    try:
        raw_wps = _mapping(case.data.get("wps", {}), "wps")
        wps = _mapping(resolve_structure(raw_wps, context), "wps")
    except CaseConfigError as exc:
        raise CaseWpsError(str(exc)) from exc

    return {
        "project": {
            "data_root": _text(context.get("data_root"), "context.data_root"),
            "work_root": _text(context.get("work_root"), "context.work_root"),
        },
        "wps": {
            "ungrib_exe": _text(wps.get("ungrib_exe"), "wps.ungrib_exe"),
            "link_grib": _text(wps.get("link_grib"), "wps.link_grib"),
            "vtable_gfs": _text(wps.get("vtable_gfs"), "wps.vtable_gfs"),
        },
    }


def ensure_wps_file(
    case: CaseConfig,
    init_time: str,
    *,
    overrides: Mapping[str, Any] | None = None,
    download: bool = True,
) -> Path:
    """Return FILE:*; download GFS and run ungrib only when the cache lacks it."""
    config = wps_adapter_config(case, overrides)
    expected = ungrib_run_dir(config, init_time) / f"FILE:{init_time[:13]}"
    if expected.is_file():
        print(f"OK: WPS FILE existente: {expected}")
        return expected
    return Path(run_ungrib(config, init_time, download=download))
