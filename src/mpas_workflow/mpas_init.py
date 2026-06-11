from __future__ import annotations

from pathlib import Path
import re

from .config import safe_time
from .pbs import mpas_init_pbs
from .shell import require_file, symlink_force, write_text, qsub


def init_run_dir(config, init_time):
    return Path(config["project"]["work_root"]) / "mpas_init" / config["mesh"]["name"] / f"{init_time}_invariant_np64"


def init_file(config, init_time):
    s = safe_time(init_time)
    return init_run_dir(config, init_time) / f"{config['mesh']['name']}.init.{s}.nc"


def patch_namelist(text, replacements):
    for key, value in replacements.items():
        pattern = rf"{key}\s*=\s*[^,\n]*"
        repl = f"{key} = {value}"
        text = re.sub(pattern, repl, text)
    return text


def prepare_init(config, init_time, wps_file):
    run_dir = init_run_dir(config, init_time)
    run_dir.mkdir(parents=True, exist_ok=True)

    mesh = config["mesh"]
    install = config["install"]
    static = config["static"]
    nproc = int(mesh["nproc"])

    require_file(wps_file, "WPS FILE")
    require_file(install["mpas_init"], "mpas_init_atmosphere")
    require_file(mesh["graph"], "graph.info")
    require_file(Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{nproc}", "graph partition")
    require_file(static["invariant"], "invariant")

    symlink_force(install["mpas_init"], run_dir / "mpas_init_atmosphere")
    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.grid.nc")
    symlink_force(wps_file, run_dir / Path(wps_file).name)
    symlink_force(mesh["graph"], run_dir / Path(mesh["graph"]).name)
    symlink_force(Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{nproc}", run_dir / f"{Path(mesh['graph']).name}.part.{nproc}")

    template = Path(install["init_share"]) / "namelist.init_atmosphere"
    streams = Path(install["init_share"]) / "streams.init_atmosphere"
    require_file(template, "namelist.init_atmosphere")
    require_file(streams, "streams.init_atmosphere")

    namelist = template.read_text()
    namelist = patch_namelist(namelist, {
        "config_init_case": "7",
        "config_start_time": f"'{init_time}'",
        "config_stop_time": f"'{init_time}'",
        "config_nvertlevels": str(mesh["nvertlevels"]),
        "config_met_prefix": "'FILE'",
        "config_sfc_prefix": "'FILE'",
        "config_static_interp": ".false.",
        "config_native_gwd_static": ".false.",
        "config_native_gwd_gsl_static": ".false.",
        "config_vertical_grid": ".true.",
        "config_met_interp": ".true.",
        "config_block_decomp_file_prefix": f"'{Path(mesh['graph']).name}.part.'",
    })
    write_text(run_dir / "namelist.init_atmosphere", namelist)
    write_text(run_dir / "streams.init_atmosphere", streams.read_text())

    write_text(run_dir / "run_mpas_init.pbs", mpas_init_pbs(config, run_dir, nproc))
    print(f"OK: diretório de init preparado: {run_dir}")
    print(f"Arquivo esperado: {init_file(config, init_time)}")
    return run_dir


def submit_init(config, init_time):
    run_dir = init_run_dir(config, init_time)
    require_file(run_dir / "run_mpas_init.pbs", "PBS de init")
    qsub("run_mpas_init.pbs", run_dir)


def validate_init(config, init_time):
    f = init_file(config, init_time)
    require_file(f, "init.nc")
    log = init_run_dir(config, init_time) / "log.init_atmosphere.0000.out"
    require_file(log, "log.init_atmosphere.0000.out")
    txt = log.read_text(errors="replace")
    if "Critical error messages =            0" not in txt:
        raise SystemExit(f"ERRO: init não terminou limpo. Veja {log}")
    print(f"OK: init validado: {f}")
