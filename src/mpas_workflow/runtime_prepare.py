"""Prepare deterministic MPAS runtime directories from declarative case YAML.

This module intentionally does not execute MPAS, WPS, PBS, JEDI, or B-matrix
steps. It validates already-rendered artifacts and declaratively links them
with executables and model inputs into an idempotent runtime directory.
"""
from __future__ import annotations

from dataclasses import dataclass
import glob
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .case_config import CaseConfig, resolve_context, resolve_structure


class RuntimePrepareError(ValueError):
    """Raised when a runtime directory cannot be prepared safely."""


@dataclass(frozen=True)
class RuntimeLink:
    """One resolved runtime symlink."""

    source: Path
    destination: Path


@dataclass(frozen=True)
class RuntimePrepareResult:
    """Artifacts planned or written for one MPAS runtime stage."""

    case_name: str
    stage: str
    output_dir: Path
    executable: Path
    links: tuple[RuntimeLink, ...]
    manifest: Path


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimePrepareError(f"{label} deve ser um mapa YAML.")
    return value


def _as_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimePrepareError(f"{label} deve ser uma string não vazia.")
    return value


def _as_relative_path(value: Any, label: str) -> Path:
    path = Path(_as_non_empty_string(value, label))
    if path.is_absolute() or ".." in path.parts:
        raise RuntimePrepareError(f"{label} deve ser um caminho relativo sem '..': {path}")
    return path


def _absolute_path(value: Any, label: str) -> Path:
    return Path(_as_non_empty_string(value, label)).expanduser().resolve()


def _path_list(runtime: Mapping[str, Any], key: str) -> list[Path]:
    raw = runtime.get(key, [])
    if not isinstance(raw, list):
        raise RuntimePrepareError(f"runtime.{key} deve ser uma lista.")
    return [_absolute_path(value, f"runtime.{key}[{index}]") for index, value in enumerate(raw)]


def _resolve_stage(case: CaseConfig, stage_name: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
    stages = _as_mapping(case.data.get("stages", {}), "stages")
    if stage_name not in stages:
        available = ", ".join(sorted(str(name) for name in stages)) or "nenhum"
        raise RuntimePrepareError(f"Estágio {stage_name!r} não definido. Disponíveis: {available}.")
    return _as_mapping(resolve_structure(stages[stage_name], context), f"stages.{stage_name}")


def _resolve_output_dir(runtime: Mapping[str, Any], override: str | Path | None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    return _absolute_path(runtime.get("output_dir"), "runtime.output_dir")


def _link_from_spec(spec: Mapping[str, Any], runtime_dir: Path, label: str) -> RuntimeLink:
    source = _absolute_path(spec.get("source"), f"{label}.source")
    destination = runtime_dir / _as_relative_path(spec.get("destination"), f"{label}.destination")
    return RuntimeLink(source=source, destination=destination)


def _expand_globs(specs: Sequence[Any], runtime_dir: Path) -> list[RuntimeLink]:
    links: list[RuntimeLink] = []
    for index, raw in enumerate(specs):
        label = f"runtime.globs[{index}]"
        spec = _as_mapping(raw, label)
        pattern = _as_non_empty_string(spec.get("pattern"), f"{label}.pattern")
        if not Path(pattern).is_absolute():
            raise RuntimePrepareError(f"{label}.pattern deve ser um caminho absoluto: {pattern}")
        destination_dir = runtime_dir / _as_relative_path(
            spec.get("destination_dir", "."), f"{label}.destination_dir"
        )
        min_matches = spec.get("min_matches", 1)
        if not isinstance(min_matches, int) or min_matches < 0:
            raise RuntimePrepareError(f"{label}.min_matches deve ser um inteiro não negativo.")
        matches = sorted(Path(item).resolve() for item in glob.glob(pattern) if Path(item).is_file())
        if len(matches) < min_matches:
            raise RuntimePrepareError(
                f"{label} encontrou {len(matches)} arquivo(s), mas exige ao menos {min_matches}: {pattern}"
            )
        links.extend(RuntimeLink(source=source, destination=destination_dir / source.name) for source in matches)
    return links


def _symlink_matches(destination: Path, source: Path) -> bool:
    if not destination.is_symlink():
        return False
    try:
        return destination.resolve() == source.resolve()
    except OSError:
        return False


def _preflight(
    executable: Path,
    links: Sequence[RuntimeLink],
    required_directories: Sequence[Path],
    required_files: Sequence[Path],
) -> None:
    problems: list[str] = []
    if not executable.is_file() or not os.access(executable, os.X_OK):
        problems.append(f"executável ausente ou não executável: {executable}")
    for directory in required_directories:
        if not directory.is_dir():
            problems.append(f"diretório ausente: {directory}")
    for required_file in required_files:
        if not required_file.is_file():
            problems.append(f"arquivo obrigatório ausente: {required_file}")
    for link in links:
        if not link.source.is_file():
            problems.append(f"arquivo ausente: {link.source}")

    destinations: set[Path] = set()
    for link in links:
        if link.destination in destinations:
            problems.append(f"destino duplicado: {link.destination}")
        destinations.add(link.destination)
        if link.destination.exists() or link.destination.is_symlink():
            if not _symlink_matches(link.destination, link.source):
                problems.append(f"destino existente incompatível: {link.destination}")

    if problems:
        raise RuntimePrepareError(
            "Insumos de runtime ausentes ou inválidos:\n- " + "\n- ".join(problems)
        )


def _materialize_link(link: RuntimeLink) -> None:
    link.destination.parent.mkdir(parents=True, exist_ok=True)
    if link.destination.is_symlink():
        return
    os.symlink(link.source, link.destination)


def _expected_output_paths(runtime_dir: Path, values: Sequence[str]) -> list[str]:
    return [str(runtime_dir / _as_relative_path(value, "runtime.expected_outputs")) for value in values]


def _resolved_install_manifest(context: Mapping[str, Any]) -> dict[str, Any]:
    """Expose normalized installation paths independently of template aliases."""
    return {
        "root": context.get("mpas_install_root"),
        "mpas_init": context.get("mpas_init_executable"),
        "mpas_atmosphere": context.get("mpas_atmosphere_executable"),
        "init_share": context.get("init_share"),
        "atmosphere_share": context.get("atmosphere_share"),
    }


def prepare_stage(
    case: CaseConfig,
    stage_name: str,
    *,
    overrides: Mapping[str, Any] | None = None,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
) -> RuntimePrepareResult:
    """Validate and prepare one runtime directory declared under ``stages.*.runtime``."""
    context = resolve_context(case, overrides)
    stage = _resolve_stage(case, stage_name, context)
    runtime = _as_mapping(stage.get("runtime"), f"stages.{stage_name}.runtime")
    runtime_dir = _resolve_output_dir(runtime, output_dir)

    executable_spec = _as_mapping(runtime.get("executable"), "runtime.executable")
    executable_link = RuntimeLink(
        source=_absolute_path(executable_spec.get("source"), "runtime.executable.source"),
        destination=runtime_dir
        / _as_relative_path(executable_spec.get("destination"), "runtime.executable.destination"),
    )

    raw_links = runtime.get("links", [])
    if not isinstance(raw_links, list):
        raise RuntimePrepareError("runtime.links deve ser uma lista.")
    links = [executable_link]
    for index, raw in enumerate(raw_links):
        spec = _as_mapping(raw, f"runtime.links[{index}]")
        links.append(_link_from_spec(spec, runtime_dir, f"runtime.links[{index}]"))

    raw_globs = runtime.get("globs", [])
    if not isinstance(raw_globs, list):
        raise RuntimePrepareError("runtime.globs deve ser uma lista.")
    links.extend(_expand_globs(raw_globs, runtime_dir))

    required_directories = _path_list(runtime, "required_directories")
    required_files = _path_list(runtime, "required_files")

    expected_outputs = runtime.get("expected_outputs", [])
    if not isinstance(expected_outputs, list) or not all(
        isinstance(item, str) and item for item in expected_outputs
    ):
        raise RuntimePrepareError("runtime.expected_outputs deve ser uma lista de strings não vazias.")

    _preflight(executable_link.source, links, required_directories, required_files)
    manifest = runtime_dir / str(runtime.get("manifest", "mpas-runtime-manifest.json"))

    if not dry_run:
        for link in links:
            _materialize_link(link)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        manifest_data = {
            "schema": "mpas-runtime-manifest/v1",
            "case": case.name,
            "case_source": str(case.source),
            "stage": stage_name,
            "dry_run": False,
            "context": context,
            "resolved_install": _resolved_install_manifest(context),
            "runtime_dir": str(runtime_dir),
            "executable": str(executable_link.destination),
            "required_directories": [str(path) for path in required_directories],
            "required_files": [str(path) for path in required_files],
            "links": [
                {"source": str(link.source), "destination": str(link.destination)} for link in links
            ],
            "expected_outputs": _expected_output_paths(runtime_dir, expected_outputs),
        }
        manifest.write_text(json.dumps(manifest_data, indent=2, sort_keys=True) + "\n")

    return RuntimePrepareResult(
        case_name=case.name,
        stage=stage_name,
        output_dir=runtime_dir,
        executable=executable_link.destination,
        links=tuple(links),
        manifest=manifest,
    )


def main() -> int:
    """Compatibility entry point; use :mod:`mpas_workflow.runtime_prepare_cli`."""
    from .runtime_prepare_cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
