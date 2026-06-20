from pathlib import Path
from types import SimpleNamespace

import yaml

from mpas_workflow.bcov_configured import BMatrixContract, apply_contract


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPOSITORY_ROOT / "configs" / "bmatrix-x1.10242.yaml"


def contract() -> BMatrixContract:
    return BMatrixContract(yaml.safe_load(CONTRACT_PATH.read_text()), CONTRACT_PATH)


def configured_legacy() -> SimpleNamespace:
    legacy = SimpleNamespace()
    apply_contract(legacy, contract())
    return legacy


def test_contract_declares_canonical_and_physical_names():
    value = contract()

    assert value.code_variables == [
        "air_horizontal_streamfunction",
        "air_horizontal_velocity_potential",
        "air_temperature",
        "water_vapor_mixing_ratio_wrt_moist_air",
        "air_pressure_at_surface",
    ]
    assert value.file_variables == [
        "stream_function",
        "velocity_potential",
        "temperature",
        "spechum",
        "surface_pressure",
    ]
    assert value.code_for_file("temperature") == "air_temperature"
    assert value.file_for_code("air_pressure_at_surface") == "surface_pressure"


def test_contract_builds_vbal_group_aliases_for_legacy_products():
    aliases = contract().pair_aliases()

    assert {
        "in code": "air_horizontal_streamfunction-air_temperature",
        "in file": "stream_function-temperature",
    } in aliases
    assert {
        "in code": "air_pressure_at_surface-air_pressure_at_surface",
        "in file": "surface_pressure-surface_pressure",
    } in aliases


def test_configured_vbal_uses_canonical_controls_and_physical_stream(tmp_path):
    legacy = configured_legacy()
    yaml_path = tmp_path / "run_vbal.yaml"
    stream_path = tmp_path / "stream_list.atmosphere.control"

    legacy.write_vbal_yaml(yaml_path, nmembers=4, date="2018-04-15T00:00:00Z")
    legacy.write_stream_list_control(stream_path)

    text = yaml_path.read_text()
    assert "- air_horizontal_streamfunction" in text
    assert "- water_vapor_mixing_ratio_wrt_moist_air" in text
    assert "balanced variable: air_temperature" in text
    assert "unbalanced variable: air_horizontal_streamfunction" in text
    assert "in code: air_temperature" in text
    assert "in file: temperature" in text
    assert stream_path.read_text().splitlines() == contract().file_variables


def test_configured_nicas_and_dirac_use_canonical_control_names(tmp_path):
    legacy = configured_legacy()
    nicas_path = tmp_path / "run_nicas.yaml"
    dirac_path = tmp_path / "run_dirac.yaml"

    legacy.write_nicas_yaml(
        nicas_path,
        variable="temperature",
        date="2018-04-15T00:00:00Z",
        nvertlevels=55,
    )
    legacy.write_dirac_yaml(
        dirac_path,
        date="2018-04-15T00:00:00Z",
        nicas_dir=Path("/tmp/nicas"),
        stddev_file=Path("/tmp/mpas.stddev.nc"),
        vbal_dir=Path("/tmp/vbal"),
    )

    nicas_text = nicas_path.read_text()
    dirac_text = dirac_path.read_text()
    assert "- air_temperature" in nicas_text
    assert "variable: air_temperature" in nicas_text
    assert "active variables: &ctlvars" in dirac_text
    assert "- air_horizontal_velocity_potential" in dirac_text
    assert "dirvar: air_temperature" in dirac_text
    assert "dirvar: temperature" not in dirac_text
    assert "alias:" not in dirac_text


def test_configured_so_uses_canonical_variables_without_aliases(tmp_path):
    legacy = configured_legacy()
    yaml_path = tmp_path / "run_SO.yaml"

    legacy.write_so_yaml(
        yaml_path,
        date="2018-04-15T00:00:00Z",
        nicas_dir=Path("/tmp/nicas"),
        stddev_file=Path("/tmp/mpas.stddev.nc"),
        vbal_dir=Path("/tmp/vbal"),
    )

    text = yaml_path.read_text()
    assert "- air_horizontal_streamfunction" in text
    assert "- water_vapor_mixing_ratio_wrt_moist_air" in text
    assert "alias:" not in text
