from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from ..shell import require_file, symlink_force


def patch_namelist(text: str, replacements: dict[str, str]) -> str:
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


def tutorial_physics_dir(config) -> Path:
    return Path(config["static"]["tutorial_physics_files"])


def copy_tutorial_stream_lists(config, run_dir: Path) -> None:
    tutorial_dir = tutorial_physics_dir(config)
    if not tutorial_dir.exists():
        return

    for path in tutorial_dir.glob("stream_list.atmosphere.*"):
        if path.is_file():
            symlink_force(path, run_dir / path.name)


def find_stream(root: ET.Element, name: str) -> ET.Element | None:
    for child in root:
        if child.get("name") == name:
            return child
    return None


def ensure_restart_stream(root: ET.Element, output_interval: str) -> None:
    restart = find_stream(root, "restart")
    if restart is None:
        restart = ET.Element("stream")
        insert_at = 0
        for index, child in enumerate(list(root)):
            if child.tag == "immutable_stream":
                insert_at = index + 1
        root.insert(insert_at, restart)

    restart.set("name", "restart")
    restart.set("type", "output")
    restart.set("filename_template", "restart.$Y-$M-$D_$h.$m.$s.nc")
    restart.set("filename_interval", "output_interval")
    restart.set("output_interval", output_interval)
    restart.set("clobber_mode", "overwrite")


def prepare_streams(config, run_dir: Path, output_interval: str) -> None:
    mesh = config["mesh"]
    share = Path(config["install"]["atmosphere_share"])
    tutorial_dir = tutorial_physics_dir(config)

    streams_template = tutorial_dir / "streams.atmosphere_240km"
    if not streams_template.exists():
        streams_template = share / "streams.atmosphere"
    require_file(streams_template, "streams.atmosphere template")

    tree = ET.parse(streams_template)
    root = tree.getroot()

    invariant = find_stream(root, "invariant")
    if invariant is None:
        invariant = ET.SubElement(root, "immutable_stream")
        invariant.set("name", "invariant")
    invariant.set("type", "input")
    invariant.set("filename_template", f"{mesh['name']}.invariant.nc")
    invariant.set("input_interval", "initial_only")

    input_stream = find_stream(root, "input")
    if input_stream is None:
        input_stream = ET.SubElement(root, "immutable_stream")
        input_stream.set("name", "input")
    input_stream.set("type", "input")
    input_stream.set("filename_template", "init.nc")
    input_stream.set("input_interval", "initial_only")

    da_state = find_stream(root, "da_state")
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

    ensure_restart_stream(root, output_interval)

    for stream_name in ["output", "diagnostics"]:
        stream = find_stream(root, stream_name)
        if stream is not None:
            stream.set("type", "none")
            stream.set("output_interval", "none")

    tree.write(run_dir / "streams.atmosphere", encoding="unicode")
