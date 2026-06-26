"""Inspect VBAL NetCDF products produced by MPAS-JEDI/SABER."""
from __future__ import annotations

import argparse
from pathlib import Path

import netCDF4


def iter_netcdf_paths(root: Path):
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*.nc")):
        if path.is_file():
            yield path


def walk_groups(group: netCDF4.Group, prefix: str = ""):
    current = prefix or "/"
    yield current, sorted(group.variables)
    for name, child in group.groups.items():
        child_prefix = f"{prefix}/{name}" if prefix else f"/{name}"
        yield from walk_groups(child, child_prefix)


def inspect(path: Path) -> tuple[bool, list[str]]:
    lines: list[str] = []
    unbalanced = False
    with netCDF4.Dataset(path) as dataset:
        for group_name, variables in walk_groups(dataset):
            label = f"{path}:{group_name}"
            lines.append(f"{label}: {', '.join(variables) if variables else '(no variables)'}")
            haystack = f"{group_name} {' '.join(variables)}".lower()
            if "unbalanced" in haystack:
                unbalanced = True
    return unbalanced, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="VBAL NetCDF file or directory")
    parser.add_argument(
        "--require-unbalanced",
        action="store_true",
        help="exit nonzero when no VBAL group or variable contains 'unbalanced'",
    )
    args = parser.parse_args()

    paths = list(iter_netcdf_paths(args.path))
    if not paths:
        raise SystemExit(f"ERROR: no NetCDF files found below {args.path}")

    any_unbalanced = False
    for path in paths:
        has_unbalanced, lines = inspect(path)
        any_unbalanced = any_unbalanced or has_unbalanced
        print(f"## {path}")
        print("\n".join(lines))

    if args.require_unbalanced and not any_unbalanced:
        raise SystemExit(
            "ERROR: no group or variable containing 'unbalanced' was found. "
            "Inspect this output together with the rendered VBAL YAML before proceeding to HDIAG."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
