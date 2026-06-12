from __future__ import annotations

from pathlib import Path
import subprocess
import time


def run(cmd, cwd=None, check=True):
    print("+", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=cwd, check=check)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def symlink_force(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.symlink_to(src)


def require_file(path, label=None):
    path = Path(path)
    if not path.exists():
        msg = f"ERRO: arquivo obrigatório não encontrado: {path}"
        if label:
            msg = f"ERRO: {label} não encontrado: {path}"
        raise SystemExit(msg)
    return path


def qsub(pbs_file, cwd):
    cmd = ["qsub", str(pbs_file)]
    print("+", " ".join(map(str, cmd)))
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.stderr.strip():
        print(proc.stderr.strip())
    out = proc.stdout.strip()
    if out:
        print(out)
    return out.split()[0] if out else ""


def pbs_job_exists(jobid: str) -> bool:
    if not jobid:
        return False
    proc = subprocess.run(
        ["qstat", jobid],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def wait_for_pbs_job(jobid: str, poll_seconds: int = 30):
    if not jobid:
        raise SystemExit("ERRO: jobid vazio; não é possível monitorar o PBS.")

    poll_seconds = max(1, int(poll_seconds))
    print(f"Aguardando job PBS terminar: {jobid}")

    while pbs_job_exists(jobid):
        time.sleep(poll_seconds)

    print(f"Job PBS saiu do qstat: {jobid}")
