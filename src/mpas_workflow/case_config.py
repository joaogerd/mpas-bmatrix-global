"""Layered, case-oriented configuration for reusable MPAS rendering.

This module deliberately knows nothing about a specific experiment, JEDI,
B-matrix generation, WPS, PBS, or a local filesystem layout. It loads a
case YAML document together with optional relative ``includes`` and exposes a
flat rendering context supplied by the case and by the caller.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping

import yaml


class CaseConfigError(ValueError):
    """Raised when a layered MPAS case configuration is invalid."""


def _expand_environment(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge two mappings recursively without modifying either input mapping."""
    merged: dict[str, Any] = deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CaseConfigError(f"Arquivo de configuração não encontrado: {path}")
    try:
        value = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise CaseConfigError(f"YAML inválido em {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise CaseConfigError(f"A configuração em {path} deve conter um mapa YAML.")
    return _expand_environment(value)


def _included_paths(path: Path, document: Mapping[str, Any]) -> list[Path]:
    includes = document.get("includes", [])
    if includes is None:
        return []
    if not isinstance(includes, list) or not all(isinstance(item, str) and item for item in includes):
        raise CaseConfigError(f"includes em {path} deve ser uma lista de caminhos não vazios.")
    return [(path.parent / item).resolve() for item in includes]


def _load_layered(path: Path, ancestry: tuple[Path, ...]) -> dict[str, Any]:
    path = path.resolve()
    if path in ancestry:
        chain = " -> ".join(str(item) for item in (*ancestry, path))
        raise CaseConfigError(f"Ciclo em includes de configuração: {chain}")

    document = _load_mapping(path)
    merged: dict[str, Any] = {}
    for included in _included_paths(path, document):
        merged = deep_merge(merged, _load_layered(included, (*ancestry, path)))

    own = dict(document)
    own.pop("includes", None)
    return deep_merge(merged, own)


@dataclass(frozen=True)
class CaseConfig:
    """Resolved MPAS case configuration and its source document."""

    source: Path
    data: dict[str, Any]

    @property
    def root(self) -> Path:
        return self.source.parent

    @property
    def name(self) -> str:
        case = self.data.get("case", {})
        if not isinstance(case, Mapping) or not isinstance(case.get("name"), str) or not case["name"]:
            raise CaseConfigError("case.name deve ser uma string não vazia.")
        return case["name"]


def load_case_config(case: str | Path) -> CaseConfig:
    """Load a case directory or an explicit ``case.yaml`` with relative includes."""
    source = Path(case)
    if source.is_dir():
        source = source / "case.yaml"
    source = source.resolve()
    data = _load_layered(source, ())
    value = CaseConfig(source=source, data=data)
    _ = value.name
    return value


def render_text(template: str, context: Mapping[str, Any]) -> str:
    """Render one configuration string using explicit, flat context values."""
    try:
        return template.format(**context)
    except KeyError as exc:
        raise CaseConfigError(
            f"Placeholder desconhecido em {template!r}: {exc.args[0]}"
        ) from exc


def resolve_context(case: CaseConfig, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a deterministic flat context, resolving references between values."""
    raw = case.data.get("context", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise CaseConfigError("context deve ser um mapa YAML.")

    context: dict[str, Any] = {"case_name": case.name, "case_root": str(case.root)}
    context.update(deepcopy(dict(raw)))
    if overrides:
        context.update(dict(overrides))

    for _ in range(max(1, len(context) + 1)):
        changed = False
        for key, value in list(context.items()):
            if not isinstance(value, str):
                continue
            rendered = render_text(value, context)
            if rendered != value:
                context[key] = rendered
                changed = True
        if not changed:
            return context

    raise CaseConfigError("Não foi possível estabilizar os placeholders do bloco context.")


def resolve_structure(value: Any, context: Mapping[str, Any]) -> Any:
    """Recursively render strings in a YAML-derived configuration structure."""
    if isinstance(value, Mapping):
        return {str(key): resolve_structure(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_structure(item, context) for item in value]
    if isinstance(value, str):
        return render_text(value, context)
    return deepcopy(value)
