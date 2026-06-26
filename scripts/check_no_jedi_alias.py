#!/usr/bin/env python3
"""Fail when rendered JEDI YAMLs still contain geometry alias blocks.

Usage:
  python scripts/check_no_jedi_alias.py <rendered-workspace-or-yaml>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ALIAS_RE = re.compile(r"^\s*alias\s*:\s*$")
YAML_SUFFIXES = {".yaml", ".yml"}


def iter_yaml(path: Path):
    if path.is_file():
        if path.suffix in YAML_SUFFIXES:
            yield path
        return
    for item in sorted(path.rglob("*")):
        if item.is_file() and item.suffix in YAML_SUFFIXES:
            yield item


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_no_jedi_alias.py <rendered-workspace-or-yaml>")
    root = Path(sys.argv[1])
    if not root.exists():
        raise SystemExit(f"ERROR: path does not exist: {root}")
    hits: list[str] = []
    for path in iter_yaml(root):
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
            if ALIAS_RE.match(line):
                hits.append(f"{path}:{lineno}: {line.strip()}")
    if hits:
        print("ERROR: rendered JEDI YAMLs still contain alias blocks:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        return 1
    print(f"OK: no alias blocks found below {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
