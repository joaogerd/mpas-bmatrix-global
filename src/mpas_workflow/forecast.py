from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from .config import safe_time
from .mpas_init import init_file
from .pbs import mpas_forecast_pbs
from .shell import require_file, symlink_force, write_text, qsub


DA_STATE_REQUIRED_VARIABLES = [
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
]


def parse_time(t):
    return datetime.strptime(t, "%Y-%m-%d_%H:%M:%S")


def fmt_file_time(dt):
    return dt.strftime("%Y-%m-%d_%H.%M.%S")


def forecast_run_dir(config, init_time, lead_hours, dt):
    mesh = config["mesh"]["name"]
    nproc = int(config["mesh"].get("nproc", 64))
    return Path(config["project"]["work_root"]) / "runs" / f"forecast_{mesh}_{safe_time(init_time)}_f{lead_hours:03d}_dt{dt}_np{nproc}"


def restart_file(config, init_time, lead_hours, dt):
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    return forecast_run_dir(config, init_time, lead_hours, dt) / f"restart.{fmt_file_time(valid)}.nc"


def bflow_file(config, init_time, lead_hours, dt):
    """Return the Bflow-ready MPAS-JEDI da_state file.

    The historical helper name is kept for CLI compatibility. The actual file is
    produced by the MPAS-JEDI da_state stream as mpasout.$Y-$M-$D_$h.$m.$s.nc.
    """
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    return forecast_run_dir(config, init_time, lead_hours, dt) / f"mpasout.{fmt_file_time(valid)}.nc"


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
        "mpasout.*.nc",
        "background.*.nc",
        "analysis.*.nc",
        "ensemble.*.nc",
        "control.*.nc",
        "restart_timestamp",
    ]
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.exists() or path.is_symlink():
                path.unlink()


def _tutorial_physics_dir(config) -> Path:
    return Path(config["static"]["tutorial_physics_files"])


def _copy_tutorial_stream_lists(config, run_dir: Path):
    tutorial_dir = _tutorial_physics_dir(config)
    if not tutorial_dir.exists():
        return

    for path in tutorial_dir.glob("stream_list.atmosphere.*"):
        if path.is_file():
            symlink_force(path, run_dir / path.name)


def _find_stream(root: ET.Element, name: str) -> ET.Element | None:
    for child in root:
        if child.get("name") == name:
            return child
    return None


def _ensure_restart_stream(root: ET.Element, output_interval: str):
    restart = _find_stream(root, "restart")
    if restart is None:
        restart = ET.Element("stream")
        insert_at = 0
        for i, child in enumerate(list(root)):
            if child.tag == "immutable_stream":
                insert_at = i + 1
        root.insert(insert_at, restart)

    restart.set("name", "restart")
    restart.set("type", "output")
    restart.set("filename_template", "restart.$Y-$M-$D_$h.$m.$s.nc")
    restart.set("filename_interval", "output_interval")
    restart.set("output_interval", output_interval)
    restart.set("clobber_mode", "overwrite")


def _prepare_streams(config, run_dir: Path, output_interval: str):
    mesh = config["mesh"]
    share = Path(config["install"]["atmosphere_share"])
    tutorial_dir = _tutorial_physics_dir(config)

    streams_template = tutorial_dir / "streams.atmosphere_240km"
    if not streams_template.exists():
        streams_template = share / "streams.atmosphere"
    require_file(streams_template, "streams.atmosphere template")

    tree = ET.parse(streams_template)
    root = tree.getroot()

    invariant = _find_stream(root, "invariant")
    if invariant is None:
        invariant = ET.SubElement(root, "immutable_stream")
        invariant.set("name", "invariant")
    invariant.set("type", "input")
    invariant.set("filename_template", f"{mesh['name']}.invariant.nc")
    invariant.set("input_interval", "initial_only")

    input_stream = _find_stream(root, "input")
    if input_stream is None:
        input_stream = ET.SubElement(root, "immutable_stream")
        input_stream.set("name", "input")
    input_stream.set("type", "input")
    input_stream.set("filename_template", "init.nc")
    input_stream.set("input_interval", "initial_only")

    da_state = _find_stream(root, "da_state")
    if da_state is None:
        da_state = ET.SubElement(root, "immutable_stream")
        da_state.set("name", "da_state")
    da_state.set("type", "output")
    da_state.set("precision", da_state.get("precision", "single"))
    da_state.set("io_type", da_state.get("io_type", "pnetcdf,cdf5"))
    da_state.set("filename_template", "mpasout.$Y-$M-$D_$h.$m.$s.nc")
    da_state.set("packages", "jedi_da")
    da_state.set("output_interval", output_interval)
    da_state.set("filename_interval", "output_interval")
    da_state.set("clobber_mode", "overwrite")

    # Keep restart output for the existing NMC validation path. Bflow itself uses
    # the MPAS-JEDI da_state/mpasout file.
    _ensure_restart_stream(root, output_interval)

    # The tutorial keeps ordinary history/diagnostics disabled for this workflow.
    for stream_name in ["output", "diagnostics"]:
        stream = _find_stream(root, stream_name)
        if stream is not None:
            stream.set("type", "none")
            stream.set("output_interval", "none")

    tree.write(run_dir / "streams.atmosphere", encoding="unicode")


def validate_forecast_setup(config, init_time, lead_hours, dt, output_interval):
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
        raise SystemExit("ERRO: PBS de forecast não contém diretiva walltime.")

    print("OK: preflight do MPAS forecast passou")
    print(f"  RUN_DIR={run_dir}")
    print(f"  INIT_INPUT={run_dir / 'init.nc'}")
    print(f"  EXPECTED_RESTART={expected_restart}")
    print(f"  EXPECTED_DA_STATE={expected_da_state}")
    print("  DA_STATE_REQUIRED_VARIABLES=" + ",".join(DA_STATE_REQUIRED_VARIABLES))
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

    _copy_tutorial_stream_lists(config, run_dir)

    tutorial_dir = _tutorial_physics_dir(config)
    template = tutorial_dir / "namelist.atmosphere_240km"
    if not template.exists():
        template = share / "namelist.atmosphere"
    require_file(template, "namelist.atmosphere template")

    run_duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    dt_value = f"{float(dt):.1f}"
    namelist = template.read_text()
    namelist = patch_namelist(namelist, {
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
    })
    write_text(run_dir / "namelist.atmosphere", namelist)

    _prepare_streams(config, run_dir, output_interval)
    write_text(run_dir / "run_mpas_forecast.pbs", mpas_forecast_pbs(config, run_dir, nproc, lead_hours=lead_hours))
    validate_forecast_setup(config, init_time, lead_hours, dt, output_interval)

    print(f"OK: forecast f{lead_hours:03d} preparado: {run_dir}")
    print(f"Arquivo restart esperado: {restart_file(config, init_time, lead_hours, dt)}")
    print(f"Arquivo MPAS-JEDI da_state esperado: {bflow_file(config, init_time, lead_hours, dt)}")
    return run_dir


def submit_forecast(config, init_time, lead_hours, dt=None):
    dt = int(dt or config["runtime"]["config_dt"])
    run_dir = forecast_run_dir(config, init_time, lead_hours, dt)
    require_file(run_dir / "run_mpas_forecast.pbs", "PBS de forecast")
    return qsub("run_mpas_forecast.pbs", run_dir)
