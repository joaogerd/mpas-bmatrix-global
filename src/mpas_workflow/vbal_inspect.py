"""Inspect and validate VBAL NetCDF products produced by MPAS-JEDI/SABER."""
from __future__ import annotations

import argparse
from pathlib import Path

import netCDF4
import yaml


REQUIRED_RELATION_PRODUCTS = {"explained", "reg"}


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


def product_kind(variable_name: str) -> str | None:
    if variable_name.startswith("explained_var"):
        return "explained"
    if variable_name.startswith("reg"):
        return "reg"
    return None


def expected_relation_groups(contract_path: Path) -> set[str]:
    data = yaml.safe_load(contract_path.read_text())
    relations = data["vbal"]["relations"]
    return {
        f"{item['unbalanced_variable']}-{item['balanced_variable']}"
        for item in relations
    }


def inspect(path: Path) -> tuple[dict[str, set[str]], list[str]]:
    products_by_group: dict[str, set[str]] = {}
    lines: list[str] = []
    with netCDF4.Dataset(path) as dataset:
        for group_name, variables in walk_groups(dataset):
            label = f"{path}:{group_name}"
            lines.append(f"{label}: {', '.join(variables) if variables else '(no variables)'}")
            key = group_name.strip("/")
            products = products_by_group.setdefault(key, set())
            for variable in variables:
                kind = product_kind(variable)
                if kind is not None:
                    products.add(kind)
    return products_by_group, lines


def validate_relations(products_by_group: dict[str, set[str]], expected: set[str]) -> list[str]:
    errors: list[str] = []
    for group in sorted(expected):
        products = products_by_group.get(group)
        if products is None:
            errors.append(f"grupo VBAL ausente: {group}")
            continue
        missing = REQUIRED_RELATION_PRODUCTS - products
        if missing:
            errors.append(f"grupo VBAL incompleto: {group}; produtos ausentes: {sorted(missing)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="VBAL NetCDF file or directory")
    parser.add_argument("--contract", type=Path, help="B-matrix contract used to render VBAL")
    parser.add_argument(
        "--require-relations",
        action="store_true",
        help="require all configured VBAL relation groups and their explained/reg products",
    )
    parser.add_argument(
        "--require-unbalanced",
        action="store_true",
        help="deprecated alias for --require-relations; requires --contract",
    )
    args = parser.parse_args()

    if args.require_unbalanced:
        args.require_relations = True
    if args.require_relations and args.contract is None:
        raise SystemExit("ERROR: --require-relations requires --contract")

    paths = list(iter_netcdf_paths(args.path))
    if not paths:
        raise SystemExit(f"ERROR: no NetCDF files found below {args.path}")

    products_by_group: dict[str, set[str]] = {}
    for path in paths:
        groups, lines = inspect(path)
        print(f"## {path}")
        print("\n".join(lines))
        for group, products in groups.items():
            products_by_group.setdefault(group, set()).update(products)

    if args.require_relations:
        errors = validate_relations(products_by_group, expected_relation_groups(args.contract))
        if errors:
            raise SystemExit("ERROR: VBAL relation validation failed: " + "; ".join(errors))
        print("OK: all configured VBAL relation groups contain explained and regression products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
