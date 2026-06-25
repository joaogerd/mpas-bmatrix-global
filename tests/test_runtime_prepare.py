from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mpas_workflow.case_config import load_case_config
from mpas_workflow.runtime_prepare import RuntimePrepareError, prepare_stage
from mpas_workflow.runtime_prepare_cli import main as runtime_main


def write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def executable(path: Path) -> Path:
    write(path, "#!/usr/bin/env bash\nexit 0\n")
    path.chmod(path.stat().st_mode | os.stat_result((0,) * 10).st_mode | 0o111)
    return path


def static_case(tmp_path: Path, *, missing_input: bool = False) -> Path:
    root = tmp_path / "inputs"
    model = executable(root / "bin" / "mpas_init_atmosphere")
    namelist = write(root / "render" / "namelist.init_atmosphere", "&nhyd_model\n/\n")
    streams = write(root / "render" / "streams.init_atmosphere", "<streams />\n")
    grid = write(root / "mesh" / "x1.grid.nc")
    graph = write(root / "mesh" / "x1.graph.info")
    partition = write(root / "mesh" / "x1.graph.info.part.4")
    geog = root / "geog"
    geog.mkdir(parents=True)
    if missing_input:
        namelist = root / "render" / "missing.namelist"

    return write(
        tmp_path / "case.yaml",
        f"""case:
  name: unit-runtime
stages:
  static:
    runtime:
      output_dir: {tmp_path / 'runtime'}
      executable:
        source: {model}
        destination: mpas_init_atmosphere
      required_directories:
        - {geog}
      links:
        - source: {namelist}
          destination: namelist.init_atmosphere
        - source: {streams}
          destination: streams.init_atmosphere
        - source: {grid}
          destination: x1.grid.nc
        - source: {graph}
          destination: x1.graph.info
        - source: {partition}
          destination: x1.graph.info.part.4
      expected_outputs:
        - x1.static.nc
""",
    )


def test_prepare_runtime_links_inputs_writes_manifest_and_is_idempotent(tmp_path: Path):
    case = load_case_config(static_case(tmp_path))

    first = prepare_stage(case, "static")
    second = prepare_stage(case, "static")

    assert first.output_dir == second.output_dir
    assert first.manifest.is_file()
    assert first.executable.is_symlink()
    assert (first.output_dir / "namelist.init_atmosphere").is_symlink()
    assert (first.output_dir / "x1.graph.info.part.4").is_symlink()

    manifest = json.loads(first.manifest.read_text())
    assert manifest["schema"] == "mpas-runtime-manifest/v1"
    assert manifest["stage"] == "static"
    assert manifest["expected_outputs"] == [str(first.output_dir / "x1.static.nc")]


def test_prepare_runtime_rejects_missing_input_before_creating_directory(tmp_path: Path):
    case = load_case_config(static_case(tmp_path, missing_input=True))

    with pytest.raises(RuntimePrepareError, match="arquivo ausente"):
        prepare_stage(case, "static")

    assert not (tmp_path / "runtime").exists()


def test_prepare_runtime_expands_absolute_glob_inputs(tmp_path: Path):
    root = tmp_path / "inputs"
    model = executable(root / "bin" / "mpas_init_atmosphere")
    wps_dir = root / "wps"
    write(wps_dir / "FILE:2026-06-12_00")
    write(wps_dir / "FILE:2026-06-12_06")
    case_path = write(
        tmp_path / "case.yaml",
        f"""case:
  name: unit-glob
stages:
  init:
    runtime:
      output_dir: {tmp_path / 'runtime'}
      executable:
        source: {model}
        destination: mpas_init_atmosphere
      required_directories:
        - {wps_dir}
      globs:
        - pattern: {wps_dir}/FILE:*
          destination_dir: .
          min_matches: 2
""",
    )

    result = prepare_stage(load_case_config(case_path), "init")

    assert (result.output_dir / "FILE:2026-06-12_00").is_symlink()
    assert (result.output_dir / "FILE:2026-06-12_06").is_symlink()


def test_runtime_cli_dry_run_reports_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    case_path = static_case(tmp_path)

    assert runtime_main(["--case", str(case_path), "--stage", "static", "--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "PLANO: caso=unit-runtime estágio=static" in output
    assert "RUNTIME_DIR=" in output
