from pathlib import Path

import yaml

from mpas_workflow.bcov_configured import BMatrixContract
from mpas_workflow.bflow_configured import (
    BFlowConfiguration,
    _build_pairs_from_range,
    _write_add_variables_script,
    _write_ncdiff_script,
    _write_psichi_script,
    _write_template_script,
    _write_validate_script,
    _write_weights_script,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPOSITORY_ROOT / "configs" / "bmatrix-x1.10242.yaml"
PLATFORM = {
    "mesh": {"name": "x1.10242"},
    "static": {"invariant": "/tmp/x1.10242.invariant.nc"},
}


def configuration() -> BFlowConfiguration:
    contract = BMatrixContract(yaml.safe_load(CONTRACT_PATH.read_text()), CONTRACT_PATH)
    return BFlowConfiguration.from_contract(contract)


def test_bflow_configuration_resolves_control_outputs():
    value = configuration()

    assert value.nmc["older_lead_hours"] == 48
    assert value.nmc["newer_lead_hours"] == 24
    assert value.output_file(value.wind_transform["outputs"]["stream_function"]) == "stream_function"
    assert value.output_file(value.wind_transform["outputs"]["velocity_potential"]) == "velocity_potential"
    assert value.runtime_data()["derived_variables"][1]["output_file"] == "temperature"
    assert value.runtime_data()["derived_variables"][2]["output_file"] == "spechum"


def test_bflow_renderers_take_field_names_and_formula_values_from_configuration(tmp_path):
    value = configuration()
    first_forecast = tmp_path / "forecast.nc"
    first_forecast.touch()

    _write_weights_script(PLATFORM, tmp_path, value)
    _write_template_script(tmp_path, first_forecast, value)
    _write_psichi_script(PLATFORM, tmp_path, value)
    _write_add_variables_script(tmp_path)
    _write_ncdiff_script(tmp_path)
    _write_validate_script(tmp_path)

    weights = (tmp_path / "scripts" / "01_generate_esmf_weights.bash").read_text()
    template = (tmp_path / "scripts" / "02_generate_template_ptb.bash").read_text()
    psichi = (tmp_path / "scripts" / "03_convert_uv_to_psichi.bash").read_text()
    derived = (tmp_path / "scripts" / "04_add_variables.py").read_text()
    ncdiff = (tmp_path / "scripts" / "05_ncdiff.py").read_text()
    validate = (tmp_path / "scripts" / "06_validate_products.py").read_text()

    assert "latlon_1p0_to_MPAS_x1.10242_bilinear.nc" in weights
    assert "uReconstructZonal" in psichi
    assert "uReconstructMeridional" in psichi
    assert "f_out->stream_function" in psichi
    assert "f_out->velocity_potential" in psichi
    assert "ncrename -O -v theta,stream_function" in template
    assert "potential_temperature_to_temperature" in derived
    assert "mixing_ratio_to_specific_humidity" in derived
    assert "f48_minus_f24" in ncdiff
    assert '"full_required"' in validate


def test_bflow_build_pairs_uses_configured_nmc_lead_times(monkeypatch):
    value = configuration()

    class Pair:
        def __init__(self, valid_time, f048, f024):
            self.valid_time = valid_time
            self.f048 = f048
            self.f024 = f024

    class Legacy:
        BflowPair = Pair

        @staticmethod
        def iter_valid_times(start, end, step):
            return ["2018-04-15_00:00:00"]

        @staticmethod
        def parse_time(value):
            from datetime import datetime

            return datetime.strptime(value, "%Y-%m-%d_%H:%M:%S")

        @staticmethod
        def format_time(value):
            return value.strftime("%Y-%m-%d_%H:%M:%S")

    calls = []

    def fake_bflow_file(platform, init_time, lead, dt):
        calls.append((init_time, lead, dt))
        return Path(f"/{lead}.nc")

    monkeypatch.setattr("mpas_workflow.bflow_configured.bflow_file", fake_bflow_file)
    builder = _build_pairs_from_range(Legacy, value)
    pairs = builder({}, "2018-04-15_00:00:00", "2018-04-15_00:00:00", 24, 60)

    assert len(pairs) == 1
    assert calls == [
        ("2018-04-13_00:00:00", 48, 60),
        ("2018-04-14_00:00:00", 24, 60),
    ]
