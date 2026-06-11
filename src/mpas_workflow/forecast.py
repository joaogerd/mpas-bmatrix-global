from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timedelta

from .config import safe_time
from .mpas_init import init_file
from .pbs import mpas_forecast_pbs
from .shell import require_file, symlink_force, write_text, qsub


def parse_time(t):
    return datetime.strptime(t, "%Y-%m-%d_%H:%M:%S")


def fmt_file_time(dt):
    return dt.strftime("%Y-%m-%d_%H.%M.%S")


def forecast_run_dir(config, init_time, lead_hours, dt):
    mesh = config["mesh"]["name"]
    return Path(config["project"]["work_root"]) / "runs" / f"forecast_{mesh}_{safe_time(init_time)}_f{lead_hours:03d}_dt{dt}_np64"


def restart_file(config, init_time, lead_hours, dt):
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    return forecast_run_dir(config, init_time, lead_hours, dt) / f"restart.{fmt_file_time(valid)}.nc"


def patch_namelist(text, replacements):
    for key, value in replacements.items():
        pattern = rf"{key}\s*=\s*[^,\n]*"
        repl = f"{key} = {value}"
        text = re.sub(pattern, repl, text)
    return text


def prepare_forecast(config, init_time, lead_hours, dt=None, output_interval=None):
    dt = int(dt or config["runtime"]["config_dt"])
    output_interval = output_interval or config["runtime"]["output_interval"]
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    run_dir.mkdir(parents=True, exist_ok=True)

    mesh = config["mesh"]
    install = config["install"]
    static = config["static"]
    nproc = int(mesh["nproc"])

    require_file(init_file(config, init_time), "init.nc")
    require_file(install["mpas_atmosphere"], "mpas_atmosphere")
    require_file(mesh["graph"], "graph.info")
    require_file(Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{nproc}", "graph partition")

    symlink_force(install["mpas_atmosphere"], run_dir / "mpas_atmosphere")
    symlink_force(init_file(config, init_time), run_dir / "init.nc")
    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.invariant.nc")
    symlink_force(mesh["grid"], run_dir / Path(mesh["grid"]).name)
    symlink_force(mesh["graph"], run_dir / Path(mesh["graph"]).name)
    symlink_force(Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{nproc}", run_dir / f"{Path(mesh['graph']).name}.part.{nproc}")

    share = Path(install["atmosphere_share"])
    for f in share.iterdir():
        if f.is_file() and f.name not in {"namelist.atmosphere", "streams.atmosphere"}:
            symlink_force(f, run_dir / f.name)

    template = Path(static["tutorial_physics_files"]) / "namelist.atmosphere_240km"
    if not template.exists():
        template = share / "namelist.atmosphere"
    require_file(template, "namelist.atmosphere template")

    run_duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    namelist = template.read_text()
    namelist = patch_namelist(namelist, {
        "config_dt": str(dt),
        "config_start_time": f"'{init_time}'",
        "config_run_duration": f"'{run_duration}'",
        "config_do_restart": ".false.",
        "config_block_decomp_file_prefix": f"'{Path(mesh['graph']).name}.part.'",
        "config_sst_update": ".false.",
        "config_sstdiurn_update": ".false.",
        "config_deepsoiltemp_update": ".false.",
        "config_do_DAcycling": ".false.",
    })
    write_text(run_dir / "namelist.atmosphere", namelist)

    streams = f'''<streams>

<immutable_stream name="invariant"
                  type="input"
                  filename_template="{mesh['name']}.invariant.nc"
                  input_interval="initial_only" />

<immutable_stream name="input"
                  type="input"
                  filename_template="init.nc"
                  input_interval="initial_only" />

<stream name="restart"
        type="output"
        filename_template="restart.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="{output_interval}"
        clobber_mode="overwrite" />

<stream name="output"
        type="output"
        filename_template="history.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="{output_interval}"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.output" />

<stream name="diagnostics"
        type="output"
        filename_template="diagnostics.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="{output_interval}"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.diagnostics" />

</streams>
'''
    write_text(run_dir / "streams.atmosphere", streams)
    write_text(run_dir / "run_mpas_forecast.pbs", mpas_forecast_pbs(config, run_dir, nproc))
    print(f"OK: forecast f{lead_hours:03d} preparado: {run_dir}")
    print(f"Arquivo esperado: {restart_file(config, init_time, lead_hours, dt)}")
    return run_dir


def submit_forecast(config, init_time, lead_hours, dt=None):
    dt = int(dt or config["runtime"]["config_dt"])
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    require_file(run_dir / "run_mpas_forecast.pbs", "PBS de forecast")
    qsub("run_mpas_forecast.pbs", run_dir)
