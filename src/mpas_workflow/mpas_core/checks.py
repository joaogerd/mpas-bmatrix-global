from __future__ import annotations

from pathlib import Path

from ..shell import require_file
from .model import DA_STATE_REQUIRED_VARIABLES, bflow_file, forecast_run_dir, restart_file


def check_forecast_setup(config, init_time: str, lead_hours: int, dt: int, output_interval: str) -> None:
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    mesh = config["mesh"]
    graph = Path(mesh["graph"])
    nproc = int(mesh["nproc"])
    partition = Path(mesh["partitions_dir"]) / f"{graph.name}.part.{nproc}"
    expected_restart = restart_file(config, init_time, lead_hours, dt)
    expected_da_state = bflow_file(config, init_time, lead_hours, dt)

    checks = [
        (run_dir / "mpas_atmosphere", "run-local mpas_atmosphere"),
        (run_dir / "init.nc", "run-local init.nc"),
        (run_dir / f"{mesh['name']}.invariant.nc", "run-local invariant input"),
        (run_dir / Path(mesh["grid"]).name, "run-local mesh grid link"),
        (run_dir / graph.name, "run-local graph.info link"),
        (run_dir / partition.name, "run-local graph partition link"),
        (run_dir / "namelist.atmosphere", "namelist.atmosphere"),
        (run_dir / "streams.atmosphere", "streams.atmosphere"),
        (run_dir / "stream_list.atmosphere.background", "stream_list.atmosphere.background"),
        (run_dir / "stream_list.atmosphere.analysis", "stream_list.atmosphere.analysis"),
        (run_dir / "stream_list.atmosphere.control", "stream_list.atmosphere.control"),
        (run_dir / "stream_list.atmosphere.ensemble", "stream_list.atmosphere.ensemble"),
        (run_dir / "run_mpas_forecast.pbs", "run_mpas_forecast.pbs"),
    ]
    for path, label in checks:
        require_file(path, label)

    namelist = (run_dir / "namelist.atmosphere").read_text(errors="replace")
    streams = (run_dir / "streams.atmosphere").read_text(errors="replace")
    pbs_text = (run_dir / "run_mpas_forecast.pbs").read_text(errors="replace")

    run_duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    dt_value = f"{float(dt):.1f}"
    required_namelist_tokens = [
        f"config_dt = {dt_value}",
        f"config_start_time = '{init_time}'",
        f"config_run_duration = '{run_duration}'",
        "config_do_restart = .false.",
        "config_do_DAcycling = .true.",
        "config_jedi_da = .true.",
        f"config_block_decomp_file_prefix = '{graph.name}.part.'",
    ]
    for token in required_namelist_tokens:
        if token not in namelist:
            raise SystemExit(f"ERRO: namelist.atmosphere não contém configuração esperada: {token}")

    required_stream_tokens = [
        f'filename_template="{mesh["name"]}.invariant.nc"',
        'filename_template="init.nc"',
        'name="da_state"',
        'filename_template="mpasout.$Y-$M-$D_$h.$m.$s.nc"',
        'packages="jedi_da"',
        f'output_interval="{output_interval}"',
        'filename_interval="output_interval"',
        'clobber_mode="overwrite"',
        'name="restart"',
        'filename_template="restart.$Y-$M-$D_$h.$m.$s.nc"',
    ]
    for token in required_stream_tokens:
        if token not in streams:
            raise SystemExit(f"ERRO: streams.atmosphere não contém configuração esperada: {token}")

    if "#PBS -l walltime=" not in pbs_text:
        raise SystemExit("ERRO: script de forecast não contém diretiva walltime.")

    print("OK: preflight do MPAS forecast passou")
    print(f"  RUN_DIR={run_dir}")
    print(f"  INIT_INPUT={run_dir / 'init.nc'}")
    print(f"  EXPECTED_RESTART={expected_restart}")
    print(f"  EXPECTED_DA_STATE={expected_da_state}")
    print("  DA_STATE_REQUIRED_VARIABLES=" + ",".join(DA_STATE_REQUIRED_VARIABLES))
    for line in pbs_text.splitlines():
        if line.startswith("#PBS -q") or line.startswith("#PBS -l walltime") or line.startswith("#PBS -l select"):
            print(f"  PBS={line}")
