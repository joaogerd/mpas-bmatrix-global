"""Read and validate configurable MPAS init/forecast workflow settings."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


DEFAULT_MODEL_CONFIG: dict[str, Any] = {
    "init": {
        "run_directory": "mpas_init/{mesh_name}/{init_time}_invariant_np{nproc}",
        "output_filename": "{mesh_name}.init.{safe_time}.nc",
        "input_grid_filename": "{mesh_name}.grid.nc",
        "namelist": {
            "config_init_case": "7",
            "config_met_prefix": "'FILE'",
            "config_sfc_prefix": "'FILE'",
            "config_static_interp": ".false.",
            "config_native_gwd_static": ".false.",
            "config_native_gwd_gsl_static": ".false.",
            "config_vertical_grid": ".true.",
            "config_met_interp": ".true.",
        },
        "streams": {
            "replace_clobber_mode": "never_modify",
            "output_clobber_mode": "overwrite",
        },
        "validation": {
            "log_success_tokens": [
                "Critical error messages =            0",
                "Error messages =                     0",
            ],
        },
    },
    "forecast": {
        "run_directory": "runs/forecast_{mesh_name}_{safe_time}_f{lead_hours:03d}_dt{dt}_np{nproc}",
        "da_state_filename": "mpasout.$Y-$M-$D_$h.$m.$s.nc",
        "restart_filename": "restart.$Y-$M-$D_$h.$m.$s.nc",
        "template": {
            "namelist": "namelist.atmosphere_240km",
            "streams": "streams.atmosphere_240km",
            "fallback_namelist": "namelist.atmosphere",
            "fallback_streams": "streams.atmosphere",
            "stream_list_glob": "stream_list.atmosphere.*",
        },
        "namelist": {
            "config_do_restart": ".false.",
            "config_sst_update": ".false.",
            "config_sstdiurn_update": ".false.",
            "config_deepsoiltemp_update": ".false.",
            "config_do_DAcycling": ".true.",
            "config_jedi_da": ".true.",
        },
        "streams": {
            "invariant_stream": "invariant",
            "input_stream": "input",
            "da_state_stream": "da_state",
            "restart_stream": "restart",
            "da_state_packages": "jedi_da",
            "da_state_precision": "single",
            "da_state_io_type": "pnetcdf,cdf5",
            "clobber_mode": "overwrite",
            "disable_output_streams": ["output", "diagnostics"],
        },
        "da_state_required_variables": [
            "uReconstructZonal",
            "uReconstructMeridional",
            "theta",
            "pressure_p",
            "pressure_base",
            "qv",
            "surface_pressure",
            "qc",
            "qr",
            "qi",
            "qs",
            "qg",
        ],
    },
}


def _merge(default: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = deepcopy(dict(default))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def model_config(config: Mapping[str, Any]) -> dict[str, Any]:
    override = config.get("model", {})
    if override is None:
        override = {}
    if not isinstance(override, Mapping):
        raise SystemExit("ERRO: o bloco model deve ser um mapa YAML.")
    value = _merge(DEFAULT_MODEL_CONFIG, override)
    validate_model_config(value)
    return value


def validate_model_config(value: Mapping[str, Any]) -> None:
    for section in ("init", "forecast"):
        if not isinstance(value.get(section), Mapping):
            raise SystemExit(f"ERRO: model.{section} deve ser um mapa YAML.")

    init = value["init"]
    forecast = value["forecast"]
    for key in ("run_directory", "output_filename", "input_grid_filename"):
        if not isinstance(init.get(key), str) or not init[key]:
            raise SystemExit(f"ERRO: model.init.{key} deve ser uma string não vazia.")
    for key in ("namelist", "streams", "validation"):
        if not isinstance(init.get(key), Mapping):
            raise SystemExit(f"ERRO: model.init.{key} deve ser um mapa YAML.")

    for key in ("run_directory", "da_state_filename", "restart_filename"):
        if not isinstance(forecast.get(key), str) or not forecast[key]:
            raise SystemExit(f"ERRO: model.forecast.{key} deve ser uma string não vazia.")
    for key in ("template", "namelist", "streams"):
        if not isinstance(forecast.get(key), Mapping):
            raise SystemExit(f"ERRO: model.forecast.{key} deve ser um mapa YAML.")
    required = forecast.get("da_state_required_variables")
    if not isinstance(required, list) or not all(isinstance(name, str) and name for name in required):
        raise SystemExit(
            "ERRO: model.forecast.da_state_required_variables deve ser uma lista de strings não vazias."
        )


def render(pattern: str, **context: Any) -> str:
    try:
        return pattern.format(**context)
    except KeyError as exc:
        raise SystemExit(
            f"ERRO: placeholder desconhecido no padrão {pattern!r}: {exc.args[0]}"
        ) from exc
