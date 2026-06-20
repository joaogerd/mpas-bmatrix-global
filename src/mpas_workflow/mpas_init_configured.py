"""Apply model YAML settings to the legacy MPAS initialization workflow."""
from __future__ import annotations

from pathlib import Path
import re

from . import mpas_init as base
from .model_config import model_config, render


def _settings(config):
    return model_config(config)["init"]


def init_run_dir(config, init_time):
    mesh = config["mesh"]
    return Path(config["project"]["work_root"]) / render(
        _settings(config)["run_directory"],
        mesh_name=mesh["name"], init_time=init_time,
        safe_time=base.safe_time(init_time), nproc=int(mesh["nproc"]),
    )


def init_file(config, init_time):
    mesh = config["mesh"]
    return init_run_dir(config, init_time) / render(
        _settings(config)["output_filename"],
        mesh_name=mesh["name"], init_time=init_time,
        safe_time=base.safe_time(init_time), nproc=int(mesh["nproc"]),
    )


def init_validation_error(config, init_time):
    output = init_file(config, init_time)
    if not output.exists():
        return f"init.nc não encontrado: {output}"
    log = init_run_dir(config, init_time) / "log.init_atmosphere.0000.out"
    if not log.exists():
        return f"log.init_atmosphere.0000.out não encontrado: {log}"
    text = log.read_text(errors="replace")
    for token in _settings(config)["validation"]["log_success_tokens"]:
        if token not in text:
            return f"init não terminou limpo; token ausente {token!r}. Veja {log}"
    return None


def _patch_streams(text, mesh_name, output_filename, settings):
    text = re.sub(r"filename_template\s*=\s*([\"'])x1\.[0-9]+\.grid\.nc\1", f'filename_template="{mesh_name}.grid.nc"', text)
    text = re.sub(r"filename_template\s*=\s*([\"'])x1\.[0-9]+\.init(?:\.[^\"']*)?\.nc\1", f'filename_template="{output_filename}"', text)
    old = re.escape(settings["streams"]["replace_clobber_mode"])
    return re.sub(rf"clobber_mode\s*=\s*([\"']){old}\1", f'clobber_mode="{settings["streams"]["output_clobber_mode"]}"', text)


def prepare_init(config, init_time, wps_file):
    settings = _settings(config)
    old_patch = base.patch_namelist
    old_streams = base.patch_streams_init_atmosphere
    old_validate = base.validate_init_setup

    def patch(text, replacements):
        values = dict(replacements)
        values.update(settings["namelist"])
        return old_patch(text, values)

    base.patch_namelist = patch
    base.patch_streams_init_atmosphere = lambda text, mesh_name, output_filename: _patch_streams(text, mesh_name, output_filename, settings)
    base.validate_init_setup = lambda *_args, **_kwargs: None
    try:
        return _legacy_prepare(config, init_time, wps_file)
    finally:
        base.patch_namelist = old_patch
        base.patch_streams_init_atmosphere = old_streams
        base.validate_init_setup = old_validate


def install():
    global _legacy_prepare
    from . import cli, forecast
    _legacy_prepare = base.prepare_init
    base.init_run_dir = init_run_dir
    base.init_file = init_file
    base.init_validation_error = init_validation_error
    base.init_is_valid = lambda config, init_time: init_validation_error(config, init_time) is None
    base.prepare_init = prepare_init
    forecast.init_file = init_file
    cli.prepare_init = prepare_init
    cli.init_validation_error = init_validation_error
