from __future__ import annotations

import json
from pathlib import Path

import pytest

from mpas_workflow.case_config import CaseConfigError, load_case_config
from mpas_workflow.case_render import RenderError, patch_namelist, patch_streams_xml, render_stage


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_layered_case_merges_includes_and_resolves_context(tmp_path: Path):
    write(
        tmp_path / "base.yaml",
        """case:
  family: atmosphere
context:
  output_root: "{work_root}/rendered"
  nproc: 8
""",
    )
    case_path = write(
        tmp_path / "case.yaml",
        """includes:
  - base.yaml
case:
  name: unit-case
context:
  work_root: /tmp/work
  nproc: 16
""",
    )

    case = load_case_config(case_path)
    assert case.name == "unit-case"
    assert case.data["case"]["family"] == "atmosphere"

    from mpas_workflow.case_config import resolve_context

    context = resolve_context(case)
    assert context["output_root"] == "/tmp/work/rendered"
    assert context["nproc"] == 16


def test_layered_case_rejects_include_cycles(tmp_path: Path):
    first = write(tmp_path / "first.yaml", "includes:\n  - second.yaml\ncase:\n  name: first\n")
    write(tmp_path / "second.yaml", "includes:\n  - first.yaml\ncase:\n  name: second\n")

    with pytest.raises(CaseConfigError, match="Ciclo"):
        load_case_config(first)


def test_namelist_patch_replaces_inserts_and_removes_options():
    source = """&nhyd_model
    config_dt = 60.0
    config_epssm = 0.1
/
&damping
    config_zd = 22000.0
/
"""

    rendered = patch_namelist(
        source,
        {
            "nhyd_model": {
                "config_dt": "1200.0",
                "config_epssm": None,
            },
            "damping": {
                "config_epssm_minimum": "0.1",
                "config_epssm_maximum": "0.5",
            },
        },
    )

    assert "config_dt = 1200.0" in rendered
    assert "config_epssm = 0.1" not in rendered
    assert "config_epssm_minimum = 0.1" in rendered
    assert "config_epssm_maximum = 0.5" in rendered


def test_stream_patch_updates_and_creates_streams():
    source = """<streams>
  <immutable_stream name="invariant" type="input" filename_template="invariant.nc" />
</streams>
"""

    rendered = patch_streams_xml(
        source,
        {
            "invariant": {
                "attributes": {"filename_template": "x1.invariant.nc"},
            },
            "restart": {
                "create": True,
                "tag": "stream",
                "attributes": {
                    "type": "output",
                    "output_interval": "06:00:00",
                },
            },
        },
    )

    assert 'name="invariant"' in rendered
    assert 'filename_template="x1.invariant.nc"' in rendered
    assert '<stream name="restart" type="output" output_interval="06:00:00"' in rendered


def test_render_stage_writes_rendered_files_and_manifest(tmp_path: Path):
    namelist = write(
        tmp_path / "template.nml",
        """&nhyd_model
    config_dt = 60.0
    config_start_time = 'old'
    config_run_duration = '0_01:00:00'
/
&restart
    config_do_restart = true
/
""",
    )
    streams = write(
        tmp_path / "template.xml",
        """<streams>
  <immutable_stream name="invariant" type="input" filename_template="invariant.nc" />
  <immutable_stream name="input" type="input" filename_template="init.nc" />
</streams>
""",
    )
    case_path = write(
        tmp_path / "case.yaml",
        f"""case:
  name: unit-render
context:
  template_namelist: {namelist}
  template_streams: {streams}
  output_root: {tmp_path / 'rendered'}
  graph_basename: x1.graph.info
  invariant_local_name: invariant.nc
  init_local_name: init.nc
stages:
  forecast:
    output_dir: "{{output_root}}/f{{lead_hours:03d}}"
    namelist:
      template: "{{template_namelist}}"
      groups:
        nhyd_model:
          config_dt: "{{dt}}.0"
          config_start_time: "'{{init_time}}'"
          config_run_duration: "'{{run_duration}}'"
          config_block_decomp_file_prefix: "'{{graph_basename}}.part.'"
        restart:
          config_do_restart: false
    streams:
      template: "{{template_streams}}"
      streams:
        invariant:
          attributes:
            filename_template: "{{invariant_local_name}}"
        input:
          attributes:
            filename_template: "{{init_local_name}}"
        restart:
          create: true
          tag: stream
          attributes:
            type: output
            output_interval: "06:00:00"
""",
    )

    from mpas_workflow.case_render import _time_context

    result = render_stage(
        load_case_config(case_path),
        "forecast",
        overrides=_time_context("2026-06-12_00:00:00", 6, 1200),
    )

    namelist_out = result.output_dir / "namelist.atmosphere"
    streams_out = result.output_dir / "streams.atmosphere"
    assert namelist_out.is_file()
    assert streams_out.is_file()
    assert result.manifest.is_file()
    assert "config_dt = 1200.0" in namelist_out.read_text()
    assert "config_run_duration = '0_06:00:00'" in namelist_out.read_text()
    assert 'name="restart"' in streams_out.read_text()

    manifest = json.loads(result.manifest.read_text())
    assert manifest["case"] == "unit-render"
    assert manifest["stage"] == "forecast"
    assert manifest["context"]["valid_time"] == "2026-06-12_06:00:00"


def test_render_rejects_unknown_stage(tmp_path: Path):
    case_path = write(tmp_path / "case.yaml", "case:\n  name: unit\nstages: {}\n")
    with pytest.raises(RenderError, match="não definido"):
        render_stage(load_case_config(case_path), "forecast")
