"""Normalize MPAS installation declarations into absolute runtime paths."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping


class InstallPathError(ValueError):
    """Raised when an ``install`` declaration is ambiguous or incomplete."""


_DEFAULT_RELATIVE_PATHS = {
    "mpas_init": "bin/mpas_init_atmosphere",
    "mpas_atmosphere": "bin/mpas_atmosphere",
    "init_share": "share/MPAS/core_init_atmosphere",
    "atmosphere_share": "share/MPAS/core_atmosphere",
}

_SIMPLE_NAME_PREFIXES = {
    "mpas_init": "bin",
    "mpas_atmosphere": "bin",
    "init_share": "share/MPAS",
    "atmosphere_share": "share/MPAS",
}



def _render(value: object, render: Callable[[str], str] | None) -> object:
    if isinstance(value, str) and render is not None:
        return render(value)
    return value



def _resolve_one(key: str, value: object, root: Path | None) -> str:
    if not isinstance(value, str) or not value:
        raise InstallPathError(f"install.{key} deve ser uma string não vazia.")

    declared = Path(value)
    if declared.is_absolute():
        return str(declared)

    if root is None:
        raise InstallPathError(
            f"install.{key} é relativo ({value!r}), mas install.root não foi informado. "
            "Sem install.root, todos os caminhos de instalação devem ser absolutos."
        )

    if len(declared.parts) == 1:
        return str(root / _SIMPLE_NAME_PREFIXES[key] / declared)
    return str(root / declared)



def resolve_install_paths(
    install: Mapping[str, object] | None,
    *,
    render: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """Resolve the compact ``install`` schema into absolute paths.

    With ``install.root``, omitted entries use the MPAS install layout and bare
    executable/share names resolve below ``bin`` or ``share/MPAS``. Absolute
    entries are explicit overrides and never use ``root``. Without ``root``,
    all four entries are required and must be absolute.
    """
    if install is None:
        return {}
    if not isinstance(install, Mapping):
        raise InstallPathError("install deve ser um mapa YAML.")

    raw = {str(key): _render(value, render) for key, value in install.items()}
    unknown = sorted(set(raw) - {"root", *_DEFAULT_RELATIVE_PATHS})
    if unknown:
        raise InstallPathError("Chaves desconhecidas em install: " + ", ".join(unknown))

    root_value = raw.get("root")
    root: Path | None = None
    if root_value is not None:
        if not isinstance(root_value, str) or not root_value:
            raise InstallPathError("install.root deve ser uma string não vazia.")
        root = Path(root_value)
        if not root.is_absolute():
            raise InstallPathError("install.root deve ser um caminho absoluto.")

    resolved: dict[str, str] = {}
    if root is not None:
        resolved["root"] = str(root)

    for key, default_relative in _DEFAULT_RELATIVE_PATHS.items():
        value = raw.get(key, default_relative if root is not None else None)
        if value is None:
            raise InstallPathError(
                f"install.{key} é obrigatório quando install.root não é informado."
            )
        resolved[key] = _resolve_one(key, value, root)

    return resolved
