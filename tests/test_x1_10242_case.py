from __future__ import annotations

from pathlib import Path

from mpas_workflow.case_config import load_case_config, resolve_context
from mpas_workflow.case_render import _time_context, render_stage


ROOT = Path(__file__).resolve().parents[1]
CORE_CASE = ROOT / "configs/mpas/cases/global-x1.10242"
JEDI_CASE = ROOT / "configs/mpas/cases/global-x1.10242-monan-jedi"


def test_core_case_declares_static_init_and_forecast_stages():
    case = load_case_config(CORE_CASE)

    assert case.name == "global-x1.10242"
    assert set(case.data["stages"]) == {"static", "init", "forecast"}

    context = resolve_context(
        case,
        _time_context("2026-06-12_00:00:00", lead_hours=48, dt=1200),
    )
    assert context["static_output_name"] == "x1.10242.static.nc"
    assert context["init_output_name"] == "x1.10242.init.2026-06-12_00.00.00.nc"
    assert context["run_duration"] == "2_00:00:00"


def test_core_case_dry_run_plans_all_mpas_stages(tmp_path: Path):
    case = load_case_config(CORE_CASE)
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
        assert result.outputs


def test_jedi_case_adds_da_state_without_redefining_core_stages():
    case = load_case_config(JEDI_CASE)

    assert case.name == "global-x1.10242-monan-jedi"
    streams = case.data["stages"]["forecast"]["streams"]["streams"]
    assert "invariant" in streams
    assert "input" in streams
    assert "restart" in streams
    assert streams["da_state"]["attributes"]["packages"] == "jedi_da"
