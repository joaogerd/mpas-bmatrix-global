from __future__ import annotations

from pathlib import Path
import subprocess
import os


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
    return run(["qsub", str(pbs_file)], cwd=cwd)
