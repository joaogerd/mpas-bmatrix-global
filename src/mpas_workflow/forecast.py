from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timedelta

from .config import safe_time
from .mpas_init import init_file
from .pbs import mpas_forecast_pbs
from .shell import require_file, symlink_force, write_text, qsub


BFLOW_STREAM_VARIABLES = [
    # Variables required by the official MPAS-JEDI Bflow preprocessing scripts.
    "uReconstructZonal",
    "uReconstructMeridional",
    "theta",
    "pressure",
    "pressure_p",
    "pressure_base",
    "qv",
    "surface_pressure",
    "relhum",
    # Optional hydrometeors used by the tutorial when hydrometeor statistics are enabled.
    "qc",
    "qr",
    "qi",
    "qs",
    "qg",
]


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


def bflow_file(config, init_time, lead_hours, dt):
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    return forecast_run_dir(config, init_time, lead_hours, dt) / f"bflow.{fmt_file_time(valid)}.nc"


def patch_namelist(text, replacements):
    missing = []
    for key, value in replacements.items():
        pattern = rf"(^\s*{re.escape(key)}\s*=\s*)[^,\n]*(.*)$"
        repl = rf"\g<1>{value}\g<2>"
        new_text, count = re.subn(pattern, repl, text, flags=re.MULTILINE)
        if count == 0:
            missing.append(key)
        text = new_text

    if missing:
        raise SystemExit(
            "ERRO: opções esperadas não foram encontradas no namelist.atmosphere: "
            + ", ".join(missing)
        )
    return text


def clean_forecast_run_dir(run_dir: Path):
    patterns = [
        "stdout.log",
        "stderr.log",
        "log.atmosphere.*",
        "*.o[0-9]*",
        "*.e[0-9]*",
        "restart.*.nc",
        "history.*.nc",
        "diagnostics.*.nc",
        "bflow.*.nc",
        "restart_timestamp",
    ]
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.exists() or path.is_symlink():
                path.unlink()


def _write_bflow_stream_list(run_dir: Path):
    write_text(
        run_dir / "stream_list.atmosphere.bflow",
        "\n".join(BFLOW_STREAM_VARIABLES) + "\n",
    )


def validate_forecast_setup(config, init_time, lead_hours, dt, output_interval):
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    mesh = config["mesh"]
    graph = Path(mesh["graph"])
    nproc = int(mesh["nproc"])
    partition = Path(mesh["partitions_dir"]) / f"{graph.name}.part.{nproc}"
    expected_restart = restart_file(config, init_time, lead_hours, dt)
    expected_bflow = bflow_file(config, init_time, lead_hours, dt)

    checks = [
        (run_dir / "mpas_atmosphere", "run-local mpas_atmosphere"),
        (run_dir / "init.nc", "run-local init.nc"),
        (run_dir / f"{mesh['name']}.invariant.nc", "run-local invariant input"),
        (run_dir / Path(mesh["grid"]).name, "run-local mesh grid link"),
        (run_dir / graph.name, "run-local graph.info link"),
        (run_dir / partition.name, "run-local graph partition link"),
        (run_dir / "namelist.atmosphere", "namelist.atmosphere"),
        (run_dir / "streams.atmosphere", "streams.atmosphere"),
        (run_dir / "stream_list.atmosphere.bflow", "stream_list.atmosphere.bflow"),
        (run_dir / "run_mpas_forecast.pbs", "run_mpas_forecast.pbs"),
    ]
    for path, label in checks:
        require_file(path, label)

    namelist = (run_dir / "namelist.atmosphere").read_text(errors="replace")
    streams = (run_dir / "streams.atmosphere").read_text(errors="replace")
    bflow_stream_list = (run_dir / "stream_list.atmosphere.bflow").read_text(errors="replace")
    pbs_text = (run_dir / "run_mpas_forecast.pbs").read_text(errors="replace")

    run_duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    required_namelist_tokens = [
        f"config_dt = {dt}",
        f"config_start_time = '{init_time}'",
        f"config_run_duration = '{run_duration}'",
        "config_do_restart = .false.",
        "config_do_DAcycling = .true.",
        f"config_block_decomp_file_prefix = '{graph.name}.part.'",
    ]
    for token in required_namelist_tokens:
        if token not in namelist:
            raise SystemExit(f"ERRO: namelist.atmosphere não contém configuração esperada: {token}")

    required_stream_tokens = [
        f'{mesh["name"]}.invariant.nc',
        "init.nc",
        "restart.$Y-$M-$D_$h.$m.$s.nc",
        "bflow.$Y-$M-$D_$h.$m.$s.nc",
        "stream_list.atmosphere.bflow",
        f'output_interval="{output_interval}"',
        'clobber_mode="overwrite"',
    ]
    for token in required_stream_tokens:
        if token not in streams:
            raise SystemExit(f"ERRO: streams.atmosphere não contém configuração esperada: {token}")

    for variable in BFLOW_STREAM_VARIABLES:
        if variable not in bflow_stream_list.split():
            raise SystemExit(
                f"ERRO: stream_list.atmosphere.bflow não contém variável esperada: {variable}"
            )

    if "#PBS -l walltime=" not in pbs_text:
        raise SystemExit("ERRO: PBS de forecast não contém diretiva walltime.")

    print("OK: preflight do MPAS forecast passou")
    print(f"  RUN_DIR={run_dir}")
    print(f"  INIT_INPUT={run_dir / 'init.nc'}")
    print(f"  EXPECTED_RESTART={expected_restart}")
    print(f"  EXPECTED_BFLOW={expected_bflow}")
    print("  BFLOW_VARIABLES=" + ",".join(BFLOW_STREAM_VARIABLES))
    for line in pbs_text.splitlines():
        if line.startswith("#PBS -q") or line.startswith("#PBS -l walltime") or line.startswith("#PBS -l select"):
            print(f"  PBS={line}")


def prepare_forecast(config, init_time, lead_hours, dt=None, output_interval=None):
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
        "config_block_decomp_file_prefix": f"'{graph.name}.part.'",
        "config_sst_update": ".false.",
        "config_sstdiurn_update": ".false.",
        "config_deepsoiltemp_update": ".false.",
        "config_do_DAcycling": ".true.",
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

<stream name="bflow"
        type="output"
        filename_template="bflow.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="{output_interval}"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.bflow" />

</streams>
'''
    write_text(run_dir / "streams.atmosphere", streams)
    _write_bflow_stream_list(run_dir)
    write_text(run_dir / "run_mpas_forecast.pbs", mpas_forecast_pbs(config, run_dir, nproc, lead_hours=lead_hours))
    validate_forecast_setup(config, init_time, lead_hours, dt, output_interval)

    print(f"OK: forecast f{lead_hours:03d} preparado: {run_dir}")
    print(f"Arquivo restart esperado: {restart_file(config, init_time, lead_hours, dt)}")
    print(f"Arquivo Bflow esperado: {bflow_file(config, init_time, lead_hours, dt)}")
    return run_dir


def submit_forecast(config, init_time, lead_hours, dt=None):
    dt = int(dt or config["runtime"]["config_dt"])
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    require_file(run_dir / "run_mpas_forecast.pbs", "PBS de forecast")
    return qsub("run_mpas_forecast.pbs", run_dir)
