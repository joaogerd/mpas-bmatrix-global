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

The JEDI-4 BFLOW runner creates canonical fields before FULL validation and the NMC difference.

After the VBAL PBS job completes:

```bash
mpasvbal-inspect <workspace-vbal>/VBAL
mpasvbal-inspect <workspace-vbal>/VBAL --contract configs/bmatrix-x1.10242-jedi4.yaml --require-relations
```

The second command requires every configured VBAL relation group and its explained/regression products. Do not run HDIAG or NICAS until it passes and the VBAL logs are reviewed.
