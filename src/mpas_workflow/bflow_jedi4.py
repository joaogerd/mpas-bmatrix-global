"""JEDI-4 canonical BFLOW runner.

The canonical contract needs the derived control fields to be added to FULL
products before FULL validation and before construction of the NMC PTB.
"""
from __future__ import annotations

from pathlib import Path

from . import bflow_configured as configured
from .bflow_configured import BFlowConfiguration
from .shell import write_text


def _write_master_script(workspace: Path, config: BFlowConfiguration) -> None:
    """Render BFLOW stages in the order required by canonical JEDI-4 fields."""
    products = config.products
    script = f'''#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [[ "${{CLEAN_OUTPUT:-0}}" == "1" ]]; then
  echo "Cleaning output directory"
  rm -rf output
  mkdir -p output
fi
mkdir -p output logs

if [[ "${{SKIP_WEIGHTS:-0}}" != "1" ]]; then
  bash scripts/01_generate_esmf_weights.bash
else
  echo "Skipping ESMF weights because SKIP_WEIGHTS=1"
fi

bash scripts/02_generate_template_ptb.bash
bash scripts/03_convert_uv_to_psichi.bash
python scripts/04_add_variables.py
python scripts/06_validate_products.py --stage full
python scripts/05_ncdiff.py
python scripts/06_validate_products.py --stage ptb
find output -name '{products['perturbation']}' -printf '%p\n' | sort
'''
    path = workspace / "scripts" / "run_all_bflow.sh"
    write_text(path, script)
    path.chmod(0o755)


def main() -> int:
    configured._write_master_script = _write_master_script
    return configured.main()
