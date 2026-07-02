from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..shell import require_file, symlink_force, write_text
from .model import STATE_VARIABLES, TIME_FORMAT, Sample


def write_stream_list_control(path: Path) -> None:
    write_text(path, "\n".join(STATE_VARIABLES) + "\n")


def stage_samples(workspace: Path, samples: list[Sample]) -> None:
    samples_dir = workspace / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    for index, sample in enumerate(samples, start=1):
        member = f"{index:03d}"
        destination = samples_dir / f"PTB_f48mf24_{member}.nc"
        destination.unlink(missing_ok=True)
        # Keep the original behavior. This requires nccopy in the environment.
        import subprocess

        subprocess.run(["nccopy", "-k", "cdf5", str(sample.ptb), str(destination)], check=True)


def link_static_files(config, run_dir: Path, bg_file: Path, template_fields: Path, valid_time: str) -> None:
    mesh = config["mesh"]
    static = config["static"]
    tutorial = Path(static["tutorial_physics_files"])

    symlink_force(mesh["graph"], run_dir / Path(mesh["graph"]).name)
    partition = Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{int(mesh['nproc'])}"
    if partition.exists():
        symlink_force(partition, run_dir / partition.name)

    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.invariant.nc")
    symlink_force(bg_file, run_dir / "bg.nc")
    mesh_id = str(mesh["name"]).removeprefix("x1.")
    symlink_force(template_fields, run_dir / f"templateFields.{mesh_id}.nc")

    namelist = tutorial / "namelist.atmosphere_240km"
    if namelist.exists():
        text = namelist.read_text()
        start_time = datetime.strptime(valid_time, TIME_FORMAT).strftime("%Y-%m-%d_%H:%M:%S")
        text, replacements = re.subn(
            r"(?m)^(\s*config_start_time\s*=\s*)'[^']+'",
            rf"\1'{start_time}'",
            text,
            count=1,
        )
        if replacements != 1:
            raise SystemExit(f"ERRO: config_start_time não encontrado em {namelist}")
        write_text(run_dir / namelist.name, text)

    streams = tutorial / "streams.atmosphere_240km"
    if streams.exists():
        symlink_force(streams, run_dir / streams.name)

    physics_dir = Path(config.get("install", {}).get("atmosphere_share", tutorial))
    for source in physics_dir.iterdir():
        if source.is_file() and source.name[:1].isupper():
            symlink_force(source, run_dir / source.name)

    for key in ["geovars", "keptvars"]:
        if key in static:
            source = require_file(static[key], key)
            symlink_force(source, run_dir / source.name)

    for source in tutorial.glob("stream_list.atmosphere.*"):
        if source.name != "stream_list.atmosphere.control":
            symlink_force(source, run_dir / source.name)
    write_stream_list_control(run_dir / "stream_list.atmosphere.control")
