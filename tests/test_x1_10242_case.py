from __future__ import annotations

from pathlib import Path

from mpas_workflow.case_config import load_case_config, resolve_context
from mpas_workflow.case_render import _time_context, render_stage


ROOT = Path(__file__).resolve().parents[1]
CASE_FILE = ROOT / "configs/mpas/cases/global-x1.10242.yaml"
OVERLAY_FILE = ROOT / "configs/mpas/overlays/monan-jedi.yaml"


def test_public_case_declares_all_mpas_stages_and_runtime_context():
    case = load_case_config(CASE_FILE)
    context = resolve_context(
        case,
        _time_context("2026-06-12_00:00:00", lead_hours=6, dt=1200),
    )

    assert case.name == "global-x1.10242"
    assert set(case.data["stages"]) == {"static", "init", "forecast"}
    assert context["mesh_name"] == "x1.10242"
    assert context["mesh_resolution_km"] == 240
    assert context["nvertlevels"] == 55
    assert context["init_output_name"] == "x1.10242.init.2026-06-12_00.00.00.nc"
    assert context["wps_geog_data_path"].endswith("WPS_GEOG_LOW_RES")


def test_public_case_plans_all_stages_without_internal_fragments(tmp_path: Path):
    case = load_case_config(CASE_FILE)
    context = _time_context("2026-06-12_00:00:00", lead_hours=6, dt=1200)

    for stage in ("static", "init", "forecast"):
        result = render_stage(
            case,
            stage,
            overrides=context,
            output_dir=tmp_path / stage,
            dry_run=True,
        )
        assert result.stage == stage
        assert result.manifest.name == "mpas-render-manifest.json"
        assert len(result.outputs) == 2


def test_base_case_disables_optional_jedi_streams_and_overlay_restores_da_state(tmp_path: Path):
    base = load_case_config(CASE_FILE)
    base_streams = base.data["stages"]["forecast"]["streams"]["streams"]
    assert base_streams["iau"]["attributes"]["type"] == "none"
    assert base_streams["da_state"]["attributes"]["type"] == "none"

    composed = tmp_path / "global-x1.10242-monan-jedi.yaml"
    composed.write_text(
        "includes:\n"
        f"  - {CASE_FILE}\n"
        f"  - {OVERLAY_FILE}\n"
        "case:\n"
        "  name: global-x1.10242-monan-jedi\n"
    )
    streams = load_case_config(composed).data["stages"]["forecast"]["streams"]["streams"]
    assert streams["da_state"]["attributes"]["type"] == "output"
    assert streams["da_state"]["attributes"]["packages"] == "jedi_da"
