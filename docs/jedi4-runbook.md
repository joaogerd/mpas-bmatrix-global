# JEDI-4 B-matrix runbook

Run the canonical workflow with:

```bash
python -m pip install -e .
python scripts/validate_jedi4_contract.py configs/bmatrix-x1.10242-jedi4.yaml
mpasbflow-jedi4 all --config configs/jaci-x1.10242-jedi4.yaml
mpasbcov-jedi4 vbal-prepare --config configs/jaci-x1.10242-jedi4.yaml
```

After the VBAL job, inspect before HDIAG:

```bash
mpasvbal-inspect <workspace-vbal>/VBAL
mpasvbal-inspect <workspace-vbal>/VBAL --require-unbalanced
```

Do not continue to HDIAG/NICAS until the VBAL products have been reviewed.
