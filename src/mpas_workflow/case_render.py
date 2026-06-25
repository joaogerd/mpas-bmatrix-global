"""Render MPAS configuration artifacts from layered, case-oriented YAML.

The renderer deliberately handles only deterministic artifact generation. It
loads a case, resolves placeholders, patches a Fortran namelist and MPAS XML
streams, then records the exact render context and template hashes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
from xml.etree import ElementTree as ET

from .case_config import (
    CaseConfig,
    CaseConfigError,
    load_case_config,
    resolve_context,
    resolve_structure,
)


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


class RenderError(ValueError):
    """Raised when a requested MPAS stage cannot be rendered safely."""


@dataclass(frozen=True)
class RenderResult:
    """Paths emitted by one deterministic stage render."""

    case_name: str
    stage: str
    output_dir: Path
    outputs: tuple[Path, ...]
    manifest: Path


def _as_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RenderError(f"{context} deve ser um mapa YAML.")
    return value


def _as_non_empty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise RenderError(f"{context} deve ser uma string não vazia.")
    return value


def _fortran_value(value: Any) -> str:
    if isinstance(value, bool):
        return ".true." if value else ".false."
    return str(value)


def _namelist_group_bounds(lines: list[str], group: str) -> tuple[int, int] | None:
    header = re.compile(rf"^\s*&{re.escape(group)}\b", re.IGNORECASE)
    closing = re.compile(r"^\s*/\s*(?:!.*)?$")
    start: int | None = None
    for index, line in enumerate(lines):
        if start is None:
            if header.match(line):
                start = index
            continue
        if closing.match(line):
            return start, index
    if start is not None:
        raise RenderError(f"Grupo &{group} sem delimitador '/' no namelist.")
    return None


def _replace_option(
    lines: list[str], start: int, end: int, key: str, value: Any
) -> tuple[list[str], int]:
    option = re.compile(rf"^(?P<indent>\s*){re.escape(key)}\s*=.*$", re.IGNORECASE)
    matches = [index for index in range(start + 1, end) if option.match(lines[index])]

    if value is None:
        for index in reversed(matches):
            del lines[index]
            end -= 1
        return lines, end

    rendered = _fortran_value(value)
    if matches:
        index = matches[0]
        match = option.match(lines[index])
        assert match is not None
        lines[index] = f"{match.group('indent')}{key} = {rendered}\n"
        for duplicate in reversed(matches[1:]):
            del lines[duplicate]
            end -= 1
        return lines, end

    indent = "    "
    for index in range(start + 1, end):
        match = re.match(r"^(\s*)[A-Za-z_][A-Za-z0-9_]*\s*=", lines[index])
        if match:
            indent = match.group(1)
            break
    lines.insert(end, f"{indent}{key} = {rendered}\n")
    return lines, end + 1


def patch_namelist(text: str, groups: Mapping[str, Any], *, strict_groups: bool = True) -> str:
    """Patch a Fortran namelist with ``group -> option -> value`` mappings.

    A YAML null removes the option. An absent option is inserted before the
    group's closing slash. This keeps version-specific MPAS settings in YAML.
    """
    lines = text.splitlines(keepends=True)
    if text and not text.endswith("\n"):
        lines[-1] += "\n"

    for group, entries in groups.items():
        group_name = _as_non_empty_string(group, "nome do grupo de namelist")
        options = _as_mapping(entries, f"namelist.groups.{group_name}")
        bounds = _namelist_group_bounds(lines, group_name)
        if bounds is None:
            if strict_groups:
                raise RenderError(f"Grupo &{group_name} não encontrado no namelist.")
            continue

        start, end = bounds
        for key, value in options.items():
            option = _as_non_empty_string(key, f"opção de &{group_name}")
            lines, end = _replace_option(lines, start, end, option, value)

    return "".join(lines)


def _find_stream(root: ET.Element, name: str) -> ET.Element | None:
    for child in root:
        if child.get("name") == name:
            return child
    return None


def _xml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def patch_streams_xml(text: str, streams: Mapping[str, Any]) -> str:
    """Patch MPAS streams by name.

    Declaring ``tag`` is explicit permission to convert an existing stream tag.
    This supports MPAS templates where an input ``immutable_stream`` named
    ``restart`` must become a dynamic output ``stream`` for a forecast case.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise RenderError(f"streams XML inválido: {exc}") from exc

    for name, raw_spec in streams.items():
        stream_name = _as_non_empty_string(name, "nome do stream")
        spec = _as_mapping(raw_spec, f"streams.{stream_name}")
        stream = _find_stream(root, stream_name)
        create = bool(spec.get("create", False))
        requested_tag = spec.get("tag")
        tag = _as_non_empty_string(requested_tag, f"tag de stream {stream_name}") if requested_tag is not None else "stream"

        if stream is None:
            if not create:
                raise RenderError(
                    f"Stream {stream_name!r} não encontrado; use create: true para criá-lo."
                )
            stream = ET.Element(tag)
            stream.set("name", stream_name)
            root.append(stream)
        elif requested_tag is not None and stream.tag != tag:
            stream.tag = tag

        attributes = _as_mapping(
            spec.get("attributes", {}), f"streams.{stream_name}.attributes"
        )
        for attribute, value in attributes.items():
            attr_name = _as_non_empty_string(attribute, f"atributo de stream {stream_name}")
            if value is None:
                stream.attrib.pop(attr_name, None)
            else:
                stream.set(attr_name, _xml_value(value))

    return ET.tostring(root, encoding="unicode") + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_output_dir(
    case: CaseConfig, stage: Mapping[str, Any], override: str | Path | None
) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    raw = _as_non_empty_string(stage.get("output_dir"), "stages.<stage>.output_dir")
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (case.root / path).resolve()


def _read_template(path: Path, label: str, dry_run: bool) -> str | None:
    if not path.is_file():
        if dry_run:
            return None
        raise RenderError(f"Template {label} não encontrado: {path}")
    return path.read_text()


def _stage_config(
    case: CaseConfig, stage_name: str, context: Mapping[str, Any]
) -> Mapping[str, Any]:
    stages = _as_mapping(case.data.get("stages", {}), "stages")
    if stage_name not in stages:
        available = ", ".join(sorted(str(name) for name in stages)) or "nenhum"
        raise RenderError(f"Estágio {stage_name!r} não definido. Disponíveis: {available}.")
    return _as_mapping(resolve_structure(stages[stage_name], context), f"stages.{stage_name}")


def render_stage(
    case: CaseConfig,
    stage_name: str,
    *,
    overrides: Mapping[str, Any] | None = None,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
) -> RenderResult:
    """Render namelist/streams and a manifest for one declarative MPAS stage."""
    context = resolve_context(case, overrides)
    stage = _stage_config(case, stage_name, context)
    target_dir = _resolve_output_dir(case, stage, output_dir)
    outputs: list[Path] = []
    input_records: list[dict[str, str]] = []

    namelist = stage.get("namelist")
    if namelist is not None:
        spec = _as_mapping(namelist, f"stages.{stage_name}.namelist")
        template = Path(_as_non_empty_string(spec.get("template"), "namelist.template"))
        destination = target_dir / str(spec.get("output", "namelist.atmosphere"))
        text = _read_template(template, "namelist", dry_run)
        if text is not None:
            groups = _as_mapping(spec.get("groups", {}), "namelist.groups")
            rendered = patch_namelist(
                text,
                groups,
                strict_groups=bool(spec.get("strict_groups", True)),
            )
            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(rendered)
            input_records.append({"path": str(template), "sha256": _sha256(template)})
        outputs.append(destination)

    streams = stage.get("streams")
    if streams is not None:
        spec = _as_mapping(streams, f"stages.{stage_name}.streams")
        template = Path(_as_non_empty_string(spec.get("template"), "streams.template"))
        destination = target_dir / str(spec.get("output", "streams.atmosphere"))
        text = _read_template(template, "streams", dry_run)
        if text is not None:
            mutations = _as_mapping(spec.get("streams", {}), "streams.streams")
            rendered = patch_streams_xml(text, mutations)
            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(rendered)
            input_records.append({"path": str(template), "sha256": _sha256(template)})
        outputs.append(destination)

    if not outputs:
        raise RenderError(
            f"O estágio {stage_name!r} não declara namelist nem streams para renderizar."
        )

    manifest = target_dir / str(stage.get("manifest", "mpas-render-manifest.json"))
    manifest_data = {
        "schema": "mpas-render-manifest/v1",
        "case": case.name,
        "case_source": str(case.source),
        "stage": stage_name,
        "dry_run": dry_run,
        "context": context,
        "inputs": input_records,
        "outputs": [str(path) for path in outputs],
    }
    if not dry_run:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(manifest_data, indent=2, sort_keys=True) + "\n")

    return RenderResult(
        case_name=case.name,
        stage=stage_name,
        output_dir=target_dir,
        outputs=tuple(outputs),
        manifest=manifest,
    )


def _time_context(init_time: str | None, lead_hours: int | None, dt: int | None) -> dict[str, Any]:
    """Build runtime placeholders supplied by the renderer command line."""
    context: dict[str, Any] = {}
    if init_time is not None:
        try:
            instant = datetime.strptime(init_time, TIME_FORMAT)
        except ValueError as exc:
            raise RenderError(
                f"--init-time deve seguir {TIME_FORMAT}: {init_time!r}"
            ) from exc
        context["init_time"] = init_time
        context["safe_time"] = init_time.replace(":", ".")
        if lead_hours is not None:
            context["valid_time"] = (instant + timedelta(hours=lead_hours)).strftime(TIME_FORMAT)
    if lead_hours is not None:
        if lead_hours < 0:
            raise RenderError("--lead-hours não pode ser negativo.")
        context["lead_hours"] = lead_hours
        context["run_duration"] = f"{lead_hours // 24}_{lead_hours % 24:02d}:00:00"
    if dt is not None:
        if dt <= 0:
            raise RenderError("--dt deve ser positivo.")
        context["dt"] = dt
    return context


if __name__ == "__main__":
    from .case_render_cli import main

    raise SystemExit(main())
