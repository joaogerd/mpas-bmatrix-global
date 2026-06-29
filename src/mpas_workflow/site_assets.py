"""Validate and materialize immutable site assets required by MPAS cases.

The operational MONAN WPS_GEOG tree is shared and read-only.  A case can add a
small user-owned overlay for assets that are absent from the institutional tree.
This module creates a lightweight view made only of symbolic links; it never
copies or modifies the source datasets.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .case_config import CaseConfig, resolve_context, resolve_structure


class SiteAssetError(ValueError):
    """Raised when declared shared or overlay site assets are invalid."""


@dataclass(frozen=True)
class AssetSource:
    """One read-only source tree contributing to an asset view."""

    name: str
    root: Path


@dataclass(frozen=True)
class AssetResolution:
    """One required relative file resolved from a declared source tree."""

    relative_path: Path
    source: AssetSource
    source_path: Path


@dataclass(frozen=True)
class WpsGeogAssetsResult:
    """Validated WPS geography sources and, optionally, their materialized view."""

    profile: str
    view_root: Path
    manifest: Path
    sources: tuple[AssetSource, ...]
    required_files: tuple[AssetResolution, ...]
    materialized: bool


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SiteAssetError(f"{label} deve ser um mapa YAML.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SiteAssetError(f"{label} deve ser uma string não vazia.")
    return value


def _absolute_path(value: Any, label: str) -> Path:
    path = Path(_text(value, label)).expanduser()
    if not path.is_absolute():
        raise SiteAssetError(f"{label} deve ser um caminho absoluto: {path}")
    return path.resolve()


def _relative_path(value: Any, label: str) -> Path:
    path = Path(_text(value, label))
    if path.is_absolute() or ".." in path.parts:
        raise SiteAssetError(f"{label} deve ser relativo e não conter '..': {path}")
    return path


def _wps_geog_spec(
    case: CaseConfig,
    context: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    assets = case.data.get("assets")
    if assets is None:
        return None
    assets = _mapping(assets, "assets")
    wps_geog = assets.get("wps_geog")
    if wps_geog is None:
        return None
    return _mapping(resolve_structure(wps_geog, context), "assets.wps_geog")


def _sources(spec: Mapping[str, Any]) -> tuple[AssetSource, ...]:
    raw_sources = spec.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise SiteAssetError("assets.wps_geog.sources deve ser uma lista não vazia.")

    result: list[AssetSource] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_sources):
        item = _mapping(raw, f"assets.wps_geog.sources[{index}]")
        name = _text(item.get("name"), f"assets.wps_geog.sources[{index}].name")
        if name in names:
            raise SiteAssetError(f"Fonte WPS_GEOG duplicada: {name}")
        names.add(name)
        root = _absolute_path(item.get("root"), f"assets.wps_geog.sources[{index}].root")
        result.append(AssetSource(name=name, root=root))
    return tuple(result)


def _required_paths(spec: Mapping[str, Any]) -> tuple[Path, ...]:
    raw = spec.get("required_files", [])
    if not isinstance(raw, list) or not raw:
        raise SiteAssetError("assets.wps_geog.required_files deve ser uma lista não vazia.")
    paths = tuple(_relative_path(item, f"assets.wps_geog.required_files[{index}]") for index, item in enumerate(raw))
    if len(set(paths)) != len(paths):
        raise SiteAssetError("assets.wps_geog.required_files não pode conter caminhos duplicados.")
    return paths


def _validate_source_roots(sources: Sequence[AssetSource]) -> None:
    missing = [source.root for source in sources if not source.root.is_dir()]
    if missing:
        details = "\n".join(f"- {path}" for path in missing)
        raise SiteAssetError(f"Árvores WPS_GEOG ausentes:\n{details}")


def _resolve_required_files(
    sources: Sequence[AssetSource],
    required_paths: Sequence[Path],
) -> tuple[AssetResolution, ...]:
    resolutions: list[AssetResolution] = []
    missing: list[Path] = []
    for relative_path in required_paths:
        for source in sources:
            candidate = source.root / relative_path
            if candidate.is_file():
                resolutions.append(
                    AssetResolution(
                        relative_path=relative_path,
                        source=source,
                        source_path=candidate.resolve(),
                    )
                )
                break
        else:
            missing.append(relative_path)
    if missing:
        details = "\n".join(f"- {path}" for path in missing)
        raise SiteAssetError(f"Ativos WPS_GEOG obrigatórios ausentes nas fontes declaradas:\n{details}")
    return tuple(resolutions)


def _visible_entries(sources: Sequence[AssetSource]) -> dict[str, tuple[AssetSource, Path]]:
    """Build a first-source-wins top-level view without copying dataset files."""
    visible: dict[str, tuple[AssetSource, Path]] = {}
    for source in sources:
        for child in sorted(source.root.iterdir(), key=lambda path: path.name):
            if child.name.startswith("."):
                continue
            visible.setdefault(child.name, (source, child.resolve()))
    return visible


def _ensure_view_link(destination: Path, source: Path) -> None:
    if destination.is_symlink():
        try:
            if destination.resolve() == source.resolve():
                return
        except OSError:
            pass
        raise SiteAssetError(
            f"View WPS_GEOG contém link incompatível: {destination} -> {destination.readlink()}"
        )
    if destination.exists():
        raise SiteAssetError(
            f"View WPS_GEOG contém entrada não gerenciada: {destination}. "
            "Remova-a ou escolha outro assets.wps_geog.view_root."
        )
    os.symlink(source, destination, target_is_directory=source.is_dir())


def _materialize_view(view_root: Path, sources: Sequence[AssetSource]) -> None:
    if view_root.is_symlink() or (view_root.exists() and not view_root.is_dir()):
        raise SiteAssetError(f"assets.wps_geog.view_root deve ser um diretório real: {view_root}")
    view_root.mkdir(parents=True, exist_ok=True)
    for _, source_path in _visible_entries(sources).values():
        _ensure_view_link(view_root / source_path.name, source_path)


def _manifest_data(
    *,
    case: CaseConfig,
    context: Mapping[str, Any],
    profile: str,
    view_root: Path,
    sources: Sequence[AssetSource],
    resolutions: Sequence[AssetResolution],
) -> dict[str, Any]:
    return {
        "schema": "mpas-wps-geog-assets/v1",
        "case": case.name,
        "case_source": str(case.source),
        "profile": profile,
        "model": {
            "monan_version": context.get("monan_version"),
            "mpas_version": context.get("mpas_version"),
        },
        "view_root": str(view_root),
        "sources": [{"name": source.name, "root": str(source.root)} for source in sources],
        "required_files": [
            {
                "path": str(item.relative_path),
                "source": item.source.name,
                "source_path": str(item.source_path),
                "size_bytes": item.source_path.stat().st_size,
                "mtime_ns": item.source_path.stat().st_mtime_ns,
            }
            for item in resolutions
        ],
    }


def prepare_wps_geog_assets(
    case: CaseConfig,
    *,
    overrides: Mapping[str, Any] | None = None,
    materialize: bool = True,
) -> WpsGeogAssetsResult | None:
    """Validate WPS_GEOG sources and optionally create their symlink-only view.

    Sources are ordered by precedence. The common MONAN tree comes first and a
    local overlay supplies only top-level datasets absent from that shared tree.
    """
    context = resolve_context(case, overrides)
    spec = _wps_geog_spec(case, context)
    if spec is None:
        return None

    profile = _text(spec.get("profile"), "assets.wps_geog.profile")
    view_root = _absolute_path(spec.get("view_root"), "assets.wps_geog.view_root")
    sources = _sources(spec)
    required_paths = _required_paths(spec)
    _validate_source_roots(sources)
    resolutions = _resolve_required_files(sources, required_paths)
    manifest = view_root / "mpas-wps-geog-assets.json"

    if materialize:
        _materialize_view(view_root, sources)
        unresolved = [item.relative_path for item in resolutions if not (view_root / item.relative_path).is_file()]
        if unresolved:
            details = "\n".join(f"- {path}" for path in unresolved)
            raise SiteAssetError(f"View WPS_GEOG incompleta após materialização:\n{details}")
        manifest.write_text(
            json.dumps(
                _manifest_data(
                    case=case,
                    context=context,
                    profile=profile,
                    view_root=view_root,
                    sources=sources,
                    resolutions=resolutions,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    return WpsGeogAssetsResult(
        profile=profile,
        view_root=view_root,
        manifest=manifest,
        sources=sources,
        required_files=resolutions,
        materialized=materialize,
    )
