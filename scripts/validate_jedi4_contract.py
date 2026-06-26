#!/usr/bin/env python3
"""Validate the JEDI-4 B-matrix contract without running JEDI."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REQUIRED = {
    "air_horizontal_streamfunction",
    "air_horizontal_velocity_potential",
    "air_temperature",
    "water_vapor_mixing_ratio_wrt_moist_air",
    "air_pressure_at_surface",
}
FORBIDDEN_FILE_NAMES = {
    "stream_function",
    "velocity_potential",
    "temperature",
    "spechum",
    "surface_pressure",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("configs/bmatrix-x1.10242-jedi4.yaml")
    data = yaml.safe_load(path.read_text())
    controls = data.get("controls", [])
    code = {item.get("code") for item in controls}
    file_names = {item.get("file") for item in controls}
    missing = REQUIRED - code
    if missing:
        fail("missing controls: " + ", ".join(sorted(missing)))
    noncanonical = [item for item in controls if item.get("code") != item.get("file")]
    if noncanonical:
        fail("controls must use file == code in JEDI-4 mode")
    forbidden = FORBIDDEN_FILE_NAMES & file_names
    if forbidden:
        fail("legacy physical names in controls: " + ", ".join(sorted(forbidden)))
    validation = data.get("bflow", {}).get("validation", {})
    forbidden_ptb = set(validation.get("forbidden_ptb_variables", []))
    if not FORBIDDEN_FILE_NAMES <= forbidden_ptb:
        fail("bflow.validation.forbidden_ptb_variables is incomplete")
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
