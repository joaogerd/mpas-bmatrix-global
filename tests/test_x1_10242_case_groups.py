from __future__ import annotations

from pathlib import Path

from mpas_workflow.case_config import load_case_config, resolve_context


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "configs/mpas/cases/global-x1.10242"


def test_static_stage_uses_preproc_dimensions_and_decomposition_groups():
    case = load_case_config(CASE)
    stage = case.data["stages"]["static"]
    groups = stage["namelist"]["groups"]

    assert groups["dimensions"]["config_nvertlevels"] == "{nvertlevels}"
    assert groups["decomposition"]["config_block_decomp_file_prefix"] == "'{graph_basename}.part.'"
    assert groups["data_sources"]["config_geog_data_path"] == "'{wps_geog_data_path}/'"
    assert groups["preproc_stages"]["config_static_interp"] is True
    assert groups["preproc_stages"]["config_vertical_grid"] is False
    assert groups["preproc_stages"]["config_met_interp"] is False
    assert "config_nvertlevels" not in groups["nhyd_model"]
    assert "config_static_interp" not in groups["nhyd_model"]

    context = resolve_context(case)
    assert "/glade/" not in context["wps_geog_data_path"]
    assert context["wps_geog_data_path"].endswith("WPS_GEOG_LOW_RES")


def test_init_stage_switches_preproc_stages_and_data_sources():
    stage = load_case_config(CASE).data["stages"]["init"]
    groups = stage["namelist"]["groups"]

    assert groups["data_sources"]["config_met_prefix"] == "'FILE'"
    assert groups["data_sources"]["config_sfc_prefix"] == "'FILE'"
    assert groups["preproc_stages"]["config_static_interp"] is False
    assert groups["preproc_stages"]["config_vertical_grid"] is True
    assert groups["preproc_stages"]["config_met_interp"] is True


def test_forecast_stage_keeps_restart_and_decomposition_outside_nhyd_model():
    stage = load_case_config(CASE).data["stages"]["forecast"]
    groups = stage["namelist"]["groups"]

    assert groups["restart"]["config_do_restart"] is False
    assert groups["decomposition"]["config_block_decomp_file_prefix"] == "'{graph_basename}.part.'"
    assert "config_do_restart" not in groups["nhyd_model"]
