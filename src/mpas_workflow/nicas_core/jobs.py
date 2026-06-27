from __future__ import annotations

import subprocess
from pathlib import Path

from ..shell import qsub, wait_for_pbs_job, write_text
from .checks import check, home_failure_files, variable_errors
from .model import NICAS_VARIABLES


def qsub_afterok(pbs_file: str, cwd: Path, jobids: list[str]) -> str:
    dependency = ":".join(jobids)
    cmd = ["qsub", "-W", f"depend=afterok:{dependency}", pbs_file]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    if proc.returncode != 0:
        raise SystemExit(f"ERRO: qsub do merge NICAS falhou com código {proc.returncode}")
    return proc.stdout.strip().split()[0]


def clean_variable_outputs(run_dir: Path) -> None:
    for name in [
        "run_nicas.runlog",
        "stdout.log",
        "stderr.log",
        "mpas_nicas.nc",
        "mpas.nicas_norm.nc",
        "mpas.dirac_nicas.nc",
    ]:
        (run_dir / name).unlink(missing_ok=True)
    for pattern in ["mpas_nicas_local_*", "mpas_nicas_grids_local_*"]:
        for path in run_dir.glob(pattern):
            path.unlink()


def run_variable(variable: str, run_dir: Path, retries: int, poll_seconds: int) -> str:
    for attempt in range(retries + 1):
        clean_variable_outputs(run_dir)
        for path in home_failure_files(run_dir):
            path.unlink()
        jobid = qsub("qsub_nicas.bash", run_dir)
        write_text(run_dir / "job_id.txt", jobid + "\n")
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)

        if home_failure_files(run_dir):
            if attempt < retries:
                print(f"Falha PBS/HOME na JACI, ressubmetendo variável {variable}.")
                continue
            raise SystemExit(f"ERRO: falha PBS/HOME persistiu para {variable} após {retries} retries.")

        errors = variable_errors(run_dir)
        if not errors:
            print(f"SUCCESS: NICAS validado para {variable}.")
            return jobid

        raise SystemExit(f"ERRO: NICAS falhou para {variable}: " + "; ".join(errors))
    raise AssertionError("loop de retry NICAS terminou inesperadamente")


def run_job(
    workspace: str | Path,
    wait: bool = False,
    poll_seconds: int = 30,
    parallel: bool = False,
    retries: int = 2,
) -> str:
    root = Path(workspace)
    merge_dir = root / "merge"
    retries = max(0, retries)

    if parallel:
        jobids = []
        for variable in NICAS_VARIABLES:
            run_dir = root / variable
            jobid = qsub("qsub_nicas.bash", run_dir)
            write_text(run_dir / "job_id.txt", jobid + "\n")
            jobids.append(jobid)
        merge_jobid = qsub_afterok("qsub_nicas_merge.bash", merge_dir, jobids)
    else:
        for variable in NICAS_VARIABLES:
            run_variable(variable, root / variable, retries=retries, poll_seconds=poll_seconds)
        merge_jobid = qsub("qsub_nicas_merge.bash", merge_dir)

    write_text(merge_dir / "job_id.txt", merge_jobid + "\n")
    if wait:
        wait_for_pbs_job(merge_jobid, poll_seconds=poll_seconds)
        check(root)
    return merge_jobid
