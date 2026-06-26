from pathlib import Path

import yaml

from mpas_workflow.bcov_configured import BMatrixContract
from mpas_workflow.bflow_configured import BFlowConfiguration
from mpas_workflow.bflow_jedi4 import _write_master_script


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_bflow_adds_fields_before_full_validation(tmp_path):
    contract_path = ROOT / "configs" / "bmatrix-x1.10242-jedi4.yaml"
    contract = BMatrixContract(yaml.safe_load(contract_path.read_text()), contract_path)
    configuration = BFlowConfiguration.from_contract(contract)
    (tmp_path / "scripts").mkdir()

    _write_master_script(tmp_path, configuration)

    script = (tmp_path / "scripts" / "run_all_bflow.sh").read_text()
    assert script.index("python scripts/04_add_variables.py") < script.index(
        "python scripts/06_validate_products.py --stage full"
    )
    assert script.index("python scripts/06_validate_products.py --stage full") < script.index(
        "python scripts/05_ncdiff.py"
    )
