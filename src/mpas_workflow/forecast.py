from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .config import safe_time
from .model_config import model_config, render
from .mpas_init import init_file
from .pbs import mpas_forecast_pbs
from .shell import qsub, require_file, symlink_force, write_text


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def fmt_file_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d_%H.%M.%S")


def _mpas_time_template(template: str, value: datetime) -> str:
    replacements = {
        "$Y": value.strftime("%Y"),
        "$M": value.strftime("%m"),
        "$D": value.strftime("%d"),
        "$h": value.strftime("%H"),
        "$m": value.strftime("%M"),
        "$s": value.strftime("%S"),
    }
    for token, replacement in replacements.items():
        template = template.replace(token, replacement)
    return template


def _forecast_settings(config):
    return model_config(config)["forecast"]


def forecast_run_dir(config, init_time, lead_hours, dt):
    mesh = config["mesh"]["name"]
    nproc = int(config["mesh"].get("nproc", 64))
    pattern = _forecast_settings(config)["run_directory"]
    relative = render(
        pattern,
        mesh_name=mesh,
        init_time=init_time,
        safe_time=safe_time(init_time),
        lead_hours=int(lead_hours),
        dt=int(dt),
        nproc=nproc,
    )
    return Path(config["project"]["work_root"]) / relative


def restart_file(config, init_time, lead_hours, dt):
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    filename = _mpas_time_template(_forecast_settings(config)["restart_filename"], valid)
    return forecast_run_dir(config, init_time, lead_hours, dt) / filename


def bflow_file(config, init_time, lead_hours, dt):
    """Return the configured MPAS-JEDI DA-state output for a forecast."""
    valid = parse_time(init_time) + timedelta(hours=lead_hours)
    filename = _mpas_time_template(_forecast_settings(config)["da_state_filename"], valid)
    return forecast_run_dir(config, init_time, lead_hours, dt) / filename


def patch_namelist(text, replacements):
    missing = []
    for key, value in replacements.items():
        pattern = rf"(^\s*{re.escape(key)}\s*=\s*)[^,\n]*(.*)$"
        replacement = rf"\g<1>{value}\g<2>"
        text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if count == 0:
            missing.append(key)
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
    template = _forecast_settings(config)["template"]
    tutorial_dir = _tutorial_physics_dir(config)
    if not tutorial_dir.exists():
        return
    for path in tutorial_dir.glob(template["stream_list_glob"]):
        if path.is_file():
            symlink_force(path, run_dir / path.name)


def _find_stream(root: ET.Element, name: str) -> ET.Element | None:
    for child in root:
        if child.get("name") == name:
            return child
    return None


def _ensure_output_stream(
    root: ET.Element,
    name: str,
    filename_template: str,
    output_interval: str,
    clobber_mode: str,
) -> ET.Element:
    stream = _find_stream(root, name)
    if stream is None:
        stream = ET.Element("stream")
        insert_at = 0
        for index, child in enumerate(list(root)):
            if child.tag == "immutable_stream":
                insert_at = index + 1
        root.insert(insert_at, stream)
    stream.set("name", name)
    stream.set("type", "output")
    stream.set("filename_template", filename_template)
    stream.set("filename_interval", "output_interval")
    stream.set("output_interval", output_interval)
    stream.set("clobber_mode", clobber_mode)
    return stream


def _prepare_streams(config, run_dir: Path, output_interval: str):
    settings = _forecast_settings(config)
    template_cfg = settings["template"]
    streams_cfg = settings["streams"]
    mesh = config["mesh"]
    share = Path(config["install"]["atmosphere_share"])
    tutorial_dir = _tutorial_physics_dir(config)

    template = tutorial_dir / template_cfg["streams"]
    if not template.exists():
        template = share / template_cfg["fallback_streams"]
    require_file(template, "streams.atmosphere template")

    tree = ET.parse(template)
    root = tree.getroot()

    invariant = _find_stream(root, streams_cfg["invariant_stream"])
    if invariant is None:
        invariant = ET.SubElement(root, "immutable_stream")
        invariant.set("name", streams_cfg["invariant_stream"])
    invariant.set("type", "input")
    invariant.set("filename_template", f"{mesh['name']}.invariant.nc")
    invariant.set("input_interval", "initial_only")

    input_stream = _find_stream(root, streams_cfg["input_stream"])
    if input_stream is None:
        input_stream = ET.SubElement(root, "immutable_stream")
        input_stream.set("name", streams_cfg["input_stream"])
    input_stream.set("type", "input")
    input_stream.set("filename_template", "init.nc")
    input_stream.set("input_interval", "initial_only")

    da_state = _ensure_output_stream(
        root,
        streams_cfg["da_state_stream"],
        settings["da_state_filename"],
        output_interval,
        streams_cfg["clobber_mode"],
    )
    da_state.set("precision", da_state.get("precision", streams_cfg["da_state_precision"]))
    da_state.set("io_type", da_state.get("io_type", streams_cfg["da_state_io_type"]))
    da_state.set("packages", streams_cfg["da_state_packages"])

    _ensure_output_stream(
        root,
        streams_cfg["restart_stream"],
        settings["restart_filename"],
        output_interval,
        streams_cfg["clobber_mode"],
    )

    for stream_name in streams_cfg["disable_output_streams"]:
        stream = _find_stream(root, stream_name)
        if stream is not None:
            stream.set("type", "none")
            stream.set("output_interval", "none")

    tree.write(run_dir / "streams.atmosphere", encoding="unicode")


def validate_forecast_setup(config, init_time, lead_hours, dt, output_interval):
    settings = _forecast_settings(config)
    streams_cfg = settings["streams"]
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

    duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    required_namelist_tokens = [
        f"config_dt = {float(dt):.1f}",
        f"config_start_time = '{init_time}'",
        f"config_run_duration = '{duration}'",
        f"config_block_decomp_file_prefix = '{graph.name}.part.'",
    ]
    required_namelist_tokens.extend(
        f"{key} = {value}" for key, value in settings["namelist"].items()
    )
    for token in required_namelist_tokens:
        if token not in namelist:
            raise SystemExit(f"ERRO: namelist.atmosphere não contém configuração esperada: {token}")

    required_stream_tokens = [
        f'filename_template="{mesh["name"]}.invariant.nc"',
        'filename_template="init.nc"',
        f'name="{streams_cfg["da_state_stream"]}"',
        f'filename_template="{settings["da_state_filename"]}"',
        f'packages="{streams_cfg["da_state_packages"]}"',
        f'output_interval="{output_interval}"',
        'filename_interval="output_interval"',
        f'clobber_mode="{streams_cfg["clobber_mode"]}"',
        f'name="{streams_cfg["restart_stream"]}"',
        f'filename_template="{settings["restart_filename"]}"',
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
    print("  DA_STATE_REQUIRED_VARIABLES=" + ",".join(settings["da_state_required_variables"]))
    for line in pbs_text.splitlines():
        if line.startswith("#PBS -q") or line.startswith("#PBS -l walltime") or line.startswith("#PBS -l select"):
            print(f"  PBS={line}")


def prepare_forecast(config, init_time, lead_hours, dt=None, output_interval=None):
    runtime = config["runtime"]
    settings = _forecast_settings(config)
    dt = int(dt or runtime["config_dt"])
    output_interval = output_interval or runtime["output_interval"]
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
    for path in share.iterdir():
        if path.is_file() and path.name not in {"namelist.atmosphere", "streams.atmosphere"}:
            symlink_force(path, run_dir / path.name)
    _copy_tutorial_stream_lists(config, run_dir)

    tutorial_dir = _tutorial_physics_dir(config)
    template_cfg = settings["template"]
    namelist_template = tutorial_dir / template_cfg["namelist"]
    if not namelist_template.exists():
        namelist_template = share / template_cfg["fallback_namelist"]
    require_file(namelist_template, "namelist.atmosphere template")

    duration = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    replacements = {
        "config_dt": f"{float(dt):.1f}",
        "config_start_time": f"'{init_time}'",
        "config_run_duration": f"'{duration}'",
        "config_block_decomp_file_prefix": f"'{graph.name}.part.'",
    }
    replacements.update(settings["namelist"])
    write_text(run_dir / "namelist.atmosphere", patch_namelist(namelist_template.read_text(), replacements))

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
