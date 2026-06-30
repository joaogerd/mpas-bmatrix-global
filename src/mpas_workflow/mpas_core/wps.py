from __future__ import annotations

from pathlib import Path

from ..config import safe_time, ymdh
from ..shell import require_file


def wps_file_name(init_time: str) -> str:
    return "FILE:" + init_time[:13]


def render_path_template(template: str, init_time: str, config) -> Path:
    return Path(
        template.format(
            init_time=init_time,
            safe_time=safe_time(init_time),
            ymdh=ymdh(init_time),
            file_time=init_time[:13],
            file_name=wps_file_name(init_time),
            project_root=config["project"]["project_root"],
            data_root=config["project"]["data_root"],
            work_root=config["project"]["work_root"],
        )
    )


def resolve_wps_file(
    config,
    init_time: str,
    wps_file: str | Path | None = None,
    wps_dir: str | Path | None = None,
    wps_template: str | None = None,
) -> Path:
    if wps_file:
        return require_file(Path(wps_file), "WPS input")

    if wps_template:
        return require_file(render_path_template(wps_template, init_time, config), "WPS input")

    wps = config.get("wps", {}) if isinstance(config.get("wps", {}), dict) else {}
    if wps.get("file_template"):
        return require_file(render_path_template(wps["file_template"], init_time, config), "WPS input")

    name = wps_file_name(init_time)
    candidates: list[Path] = []
    if wps_dir:
        candidates.append(Path(wps_dir) / name)
    if wps.get("input_dir"):
        candidates.append(Path(wps["input_dir"]) / name)
    if wps.get("input_root"):
        root = Path(wps["input_root"])
        candidates.append(root / ymdh(init_time) / name)
        candidates.append(root / safe_time(init_time) / name)
        candidates.append(root / init_time[:10] / name)

    work_root = Path(config["project"]["work_root"])
    data_root = Path(config["project"]["data_root"])
    candidates.extend(
        [
            work_root / "wps_ungrib" / f"gfs.{ymdh(init_time)}.f000" / name,
            work_root / "wps" / ymdh(init_time) / name,
            work_root / "wps" / safe_time(init_time) / name,
            work_root / "wps" / init_time[:10] / name,
            data_root / "wps" / ymdh(init_time) / name,
            data_root / "wps" / safe_time(init_time) / name,
            data_root / "wps" / init_time[:10] / name,
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = "\n".join(f"- {path}" for path in candidates)
    raise SystemExit(
        f"ERRO: entrada WPS não encontrada para {init_time}.\n"
        "Informe --wps-file, --wps-dir, --wps-template ou configure wps.file_template.\n"
        f"Candidatos testados:\n{searched}"
    )
