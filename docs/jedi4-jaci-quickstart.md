# JEDI-4 B-matrix quickstart on JACI

Install the branch in editable mode:

```bash
python -m pip install -e .
```

Validate the canonical contract:

```bash
python scripts/validate_jedi4_contract.py configs/bmatrix-x1.10242-jedi4.yaml
```

Use the dedicated JACI configuration and JEDI-4 entry points:

```bash
mpasbflow-jedi4 all --config configs/jaci-x1.10242-jedi4.yaml
mpasbcov-jedi4 vbal-prepare --config configs/jaci-x1.10242-jedi4.yaml
```

The JEDI-4 BFLOW entry point adds canonical derived variables before validating `FULL` and before creating NMC perturbations.

After the VBAL PBS job completes, inspect its products before preparing HDIAG:

```bash
mpasvbal-inspect <workspace-vbal>/VBAL
mpasvbal-inspect <workspace-vbal>/VBAL --require-unbalanced
```

The second command is expected to fail when the current VBAL issue is still present. Do not run HDIAG/NICAS until the VBAL output has been inspected.
