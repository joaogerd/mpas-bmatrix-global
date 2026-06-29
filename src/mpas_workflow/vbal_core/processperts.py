from __future__ import annotations

import shutil
from pathlib import Path

from ..shell import qsub, require_file, symlink_force, wait_for_pbs_job, write_text
from .config_files import write_processperts_pbs, write_processperts_yaml
from .model import vbal_date
from .validate import validate as validate_vbal


def _link_process_inputs(vbal_root: Path, run_dir: Path) -> None:
    vbal_run = vbal_root / "VBAL"

    symlink_force(vbal_root / "samples", vbal_root / "PROCESSPERTS" / "samples")
    symlink_force(vbal_run, vbal_root / "PROCESSPERTS" / "vbal")

    required = ["bg.nc", "namelist.atmosphere_240km", "streams.atmosphere_240km"]
    template_fields = sorted(vbal_run.glob("templateFields.*.nc"))
    if len(template_fields) != 1:
        raise SystemExit("ERRO: esperado exatamente um templateFields.*.nc no workspace VBAL.")

    for name in required:
        symlink_force(require_file(vbal_run / name, name), run_dir / name)
    symlink_force(template_fields[0], run_dir / template_fields[0].name)

    for pattern in [
        "*.graph.info",
        "*.graph.info.part.*",
        "*.invariant.nc",
        "stream_list.atmosphere.*",
        "geovars.yaml",
        "keptvars.yaml",
        "[A-Z]*",
    ]:
        for source in vbal_run.glob(pattern):
            if source.name not in required:
                symlink_force(source, run_dir / source.name)


def _member_count(vbal_root: Path) -> int:
    samples = sorted((vbal_root / "samples").glob("PTB_f48mf24_*.nc"))
    if not samples:
        raise SystemExit("ERRO: nenhum PTB original encontrado no workspace VBAL.")
    return len(samples)


def prepare_process(config, workspace: str | Path, clean: bool = False) -> Path:
    """Prepare ProcessPerts to apply K2^-1 and write unbalanced samples."""
    root = Path(workspace)
    validate_vbal(root)
    nmembers = _member_count(root)

    run_dir = root / "PROCESSPERTS"
    if clean and run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (root / "samples_unbalanced").mkdir(parents=True, exist_ok=True)

    _link_process_inputs(root, run_dir)
    write_processperts_yaml(run_dir / "process_unbalanced.yaml", nmembers, vbal_date(root))
    write_processperts_pbs(config, run_dir)

    write_text(
        root / "PROCESSPERTS_README.md",
        "# VBAL unbalanced sample processing\n\n"
        "This step uses `mpasjedi_process_perts.x` with `BUMP_VerticalBalance` "
        "in `right inverse` mode to materialize K2^-1(PTB) samples.\n\n"
        "Outputs are written to `samples_unbalanced/PTB_unbalanced_%mem%.nc`.\n",
    )

    print("=== VBAL ProcessPerts workspace ===")
    print(f"WORKSPACE={root}")
    print(f"RUN_DIR={run_dir}")
    print(f"MEMBERS={nmembers}")
    print(f"YAML={run_dir / 'process_unbalanced.yaml'}")
    print(f"PBS={run_dir / 'qsub_process_unbalanced.bash'}")
    return root


def submit_process(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    root = Path(workspace)
    run_dir = root / "PROCESSPERTS"
    require_file(run_dir / "qsub_process_unbalanced.bash", "qsub_process_unbalanced.bash")
    jobid = qsub("qsub_process_unbalanced.bash", run_dir)
    write_text(run_dir / "job_id.txt", jobid + "\n")
    if wait:
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    return jobid


def validate_process(workspace: str | Path) -> bool:
    root = Path(workspace)
    run_dir = root / "PROCESSPERTS"
    samples_dir = root / "samples_unbalanced"
    original = sorted((root / "samples").glob("PTB_f48mf24_*.nc"))
    produced = sorted(samples_dir.glob("PTB_unbalanced_*.nc"))
    log = run_dir / "process_perts.runlog"
    text = log.read_text(errors="replace") if log.is_file() else ""

    errors: list[str] = []
    if not log.is_file():
        errors.append("process_perts.runlog ausente")
    if "Finishing oops::ProcessPerts<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente no process_perts.runlog")
    if not original:
        errors.append("samples originais ausentes")
    if len(produced) != len(original):
        errors.append(f"amostras unbalanced incompletas: esperadas={len(original)}, geradas={len(produced)}")

    print("=== VBAL ProcessPerts validation ===")
    print(f"WORKSPACE={root}")
    print(f"RUNLOG={log}")
    print(f"ORIGINAL_SAMPLES={len(original)}")
    print(f"UNBALANCED_SAMPLES={len(produced)}")

    if errors:
        print("Problemas:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit("ERRO: processamento das amostras unbalanced falhou ou ficou incompleto.")

    print("SUCCESS: amostras unbalanced validadas.")
    return True
