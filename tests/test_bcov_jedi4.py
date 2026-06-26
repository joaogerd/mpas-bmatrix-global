from pathlib import Path

import yaml

from mpas_workflow import bcov_jedi4
from mpas_workflow.bcov_configured import BMatrixContract


ROOT = Path(__file__).resolve().parents[1]


def load_contract(name: str) -> BMatrixContract:
    path = ROOT / "configs" / name
    return BMatrixContract(yaml.safe_load(path.read_text()), path)


def test_canonical_contract_geometry_has_no_alias():
    contract = load_contract("bmatrix-x1.10242-jedi4.yaml")
    rendered = bcov_jedi4._geometry_yaml(contract, 2)
    assert "alias:" not in rendered


def test_legacy_contract_geometry_retains_alias():
    contract = load_contract("bmatrix-x1.10242.yaml")
    rendered = bcov_jedi4._geometry_yaml(contract, 2)
    assert "alias:" in rendered
