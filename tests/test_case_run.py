from pathlib import Path

from mpas_workflow.case_config import load_case_config, resolve_context, resolve_structure
from mpas_workflow.case_render import _time_context

ROOT = Path(__file__).resolve().parents[1]


def test_bmatrix_case_requires_da_state():
    case = load_case_config(ROOT / "configs/mpas/cases/global-x1.10242-bmatrix.json")
    context = resolve_context(case, _time_context("2026-06-12_00:00:00", 24, 1200))
    stage = resolve_structure(case.data["stages"]["forecast"], context)
    attrs = stage["streams"]["streams"]["da_state"]["attributes"]
    assert attrs["type"] == "output"
    assert stage["runtime"]["additional_expected_outputs"] == ["mpasout.$Y-$M-$D_$h.$m.$s.nc"]
