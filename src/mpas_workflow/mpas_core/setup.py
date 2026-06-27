from __future__ import annotations

from pathlib import Path

from ..mpas_init import init_file
from ..pbs import mpas_forecast_pbs
from ..shell import require_file, symlink_force, write_text
from .checks import check_forecast_setup
from .cleanup import clean_forecast_run_dir
from .model import bflow_file, forecast_run_dir, restart_file
from .streams import copy_tutorial_stream_lists, patch_namelist, prepare_streams, tutorial_physics_dir


def setup_run(config, init_time: str, lead_hours: int, dt=None, output_interval=None):
    dt = int(dt or config["runtime"]["config_dt"])
    output_interval = output_interval or config["runtime"]["output_interval"]
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    run_dir.mkdir(parents=True, exist_ok=True)

    mesh = config["mesh"]
    install = config["install"]
    static = config["static"]
    nproc = int(mesh["nproc"])
    graph = Path(mesh["graph"])
    partition = Path(mesh["partitions_dir"]) / f"{graph.name}.part.{nproc}"

    require_file(init_file(config, init_time), "init.nc")
    require_file(install["mpas_atmosphere"], "mpas_atmosphere")
    require_file(mesh["graph"], "graph.info")
    require_file(partition, "graph partition")
    require_file(static["invariant"], "invariant")
    require_file(mesh["grid"], "mesh grid")

    clean_forecast_run_dir(run_dir)

    symlink_force(install["mpas_atmosphere"], run_dir / "mpas_atmosphere")
    symlink_force(init_file(config, init_time), run_dir / "init.nc")
    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.invariant.nc")
    symlink_force(mesh["grid"], run_dir / Path(mesh["grid"]).name)
    symlink_force(mesh["graph"], run_dir / graph.name)
    symlink_force(partition, run_dir / partition.name)

    share = Path(install["atmosphere_share"])
    for source in share.iterdir():
        if source.is_file() and source.name not in {"namelist.atmosphere", "streams.atmosphere"}:
            symlink_force(source, run_dir / source.name)

    copy_tutorial_stream_lists(config, run_dir)

    tutorial_dir = tutorial_physics_dir(config)
    template = tutorial_dir / "namelist.atmosphere_240km"
    if not template.exists():
        template = share / "namelist.atmosphere"
    require_file(template, "namelist.atmosphere template")

    run_duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    dt_value = f"{float(dt):.1f}"
    namelist = template.read_text()
    namelist = patch_namelist(
        namelist,
        {
            "config_dt": dt_value,
            "config_start_time": f"'{init_time}'",
            "config_run_duration": f"'{run_duration}'",
            "config_do_restart": ".false.",
            "config_block_decomp_file_prefix": f"'{graph.name}.part.'",
            "config_sst_update": ".false.",
            "config_sstdiurn_update": ".false.",
            "config_deepsoiltemp_update": ".false.",
            "config_do_DAcycling": ".true.",
            "config_jedi_da": ".true.",
        },
    )
    write_text(run_dir / "namelist.atmosphere", namelist)

    prepare_streams(config, run_dir, output_interval)
    write_text(
        run_dir / "run_mpas_forecast.pbs",
        mpas_forecast_pbs(config, run_dir, nproc, lead_hours=lead_hours),
    )
    check_forecast_setup(config, init_time, lead_hours, dt, output_interval)

    print(f"OK: forecast f{lead_hours:03d} preparado: {run_dir}")
    print(f"Arquivo restart esperado: {restart_file(config, init_time, lead_hours, dt)}")
    print(f"Arquivo MPAS-JEDI da_state esperado: {bflow_file(config, init_time, lead_hours, dt)}")
    return run_dir
