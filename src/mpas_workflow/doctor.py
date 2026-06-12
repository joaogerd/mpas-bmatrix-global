from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import shutil
import os

from .config import ymdh
from .wps import grib_path, ungrib_run_dir
from .mpas_init import init_file
from .forecast import restart_file
from .nmc import pair_dir

TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def _ok(label: str, value: str | Path = ""):
    print(f"[OK]   {label}{': ' + str(value) if value else ''}")


def _warn(label: str, value: str | Path = ""):
    print(f"[WARN] {label}{': ' + str(value) if value else ''}")


def _fail(label: str, value: str | Path = ""):
    print(f"[FAIL] {label}{': ' + str(value) if value else ''}")


def _path_exists(path: str | Path, label: str, executable: bool = False) -> bool:
    path = Path(path)
    if not path.exists():
        _fail(label, path)
        return False
    if executable and not os.access(path, os.X_OK):
        _fail(f"{label} existe, mas não é executável", path)
        return False
    _ok(label, path)
    return True


def _path_writable(path: str | Path, label: str) -> bool:
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        _fail(f"{label} não pôde ser criado", f"{path} ({exc})")
        return False
    if not os.access(path, os.W_OK):
        _fail(f"{label} sem permissão de escrita", path)
        return False
    _ok(label, path)
    return True


def _command_exists(name: str, required: bool = True) -> bool:
    found = shutil.which(name)
    if found:
        _ok(f"comando {name}", found)
        return True
    if required:
        _fail(f"comando {name} não encontrado no PATH")
        return False
    _warn(f"comando opcional {name} não encontrado no PATH")
    return True


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def _iter_valid_times(start: str, end: str, step_hours: int):
    current = _parse_time(start)
    last = _parse_time(end)
    step = timedelta(hours=step_hours)
    while current <= last:
        yield current.strftime(TIME_FORMAT)
        current += step


def _nmc_times(valid_time: str):
    valid = _parse_time(valid_time)
    return (
        (valid - timedelta(hours=48)).strftime(TIME_FORMAT),
        (valid - timedelta(hours=24)).strftime(TIME_FORMAT),
        valid_time,
    )


def doctor_config(config) -> bool:
    """Check static requirements that should exist before running any workflow."""
    print("=== mpaswf doctor: configuração e ambiente ===")
    ok = True

    required_sections = ["project", "environment", "install", "mesh", "static", "wps", "pbs", "runtime"]
    for section in required_sections:
        if section not in config:
            _fail(f"seção ausente no YAML: {section}")
            ok = False
        else:
            _ok(f"seção YAML", section)

    if not ok:
        return False

    project = config["project"]
    install = config["install"]
    mesh = config["mesh"]
    static = config["static"]
    wps = config["wps"]

    for key in ["project_root", "data_root", "work_root"]:
        ok = _path_writable(project[key], f"project.{key}") and ok

    ok = _path_exists(install["mpas_init"], "mpas_init_atmosphere", executable=True) and ok
    ok = _path_exists(install["mpas_atmosphere"], "mpas_atmosphere", executable=True) and ok
    ok = _path_exists(install["init_share"], "MPAS init share") and ok
    ok = _path_exists(install["atmosphere_share"], "MPAS atmosphere share") and ok
    ok = _path_exists(Path(install["init_share"]) / "namelist.init_atmosphere", "template namelist.init_atmosphere") and ok
    ok = _path_exists(Path(install["init_share"]) / "streams.init_atmosphere", "template streams.init_atmosphere") and ok

    ok = _path_exists(mesh["grid"], "mesh.grid") and ok
    ok = _path_exists(mesh["graph"], "mesh.graph") and ok
    partition = Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{int(mesh['nproc'])}"
    ok = _path_exists(partition, f"mesh partition np{mesh['nproc']}") and ok

    ok = _path_exists(static["invariant"], "static.invariant") and ok
    ok = _path_exists(static["tutorial_physics_files"], "static.tutorial_physics_files") and ok

    ok = _path_exists(wps["ungrib_exe"], "WPS ungrib.exe", executable=True) and ok
    ok = _path_exists(wps["link_grib"], "WPS link_grib.csh") and ok
    ok = _path_exists(wps["vtable_gfs"], "WPS Vtable.GFS") and ok

    for cmd in ["qsub", "qstat", "curl", "ncdump"]:
        ok = _command_exists(cmd, required=True) and ok

    print()
    if ok:
        print("SUCCESS: requisitos estáticos básicos estão presentes.")
    else:
        print("ERRO: há requisitos estáticos ausentes. Corrija antes de rodar o workflow.")
    return ok


def doctor_nmc_range(config, start_valid_time: str, end_valid_time: str, interval_hours: int, dt: int) -> bool:
    """Print a status table for the files involved in an NMC range."""
    print("\n=== mpaswf doctor: status do intervalo NMC ===")
    print(f"START_VALID_TIME={start_valid_time}")
    print(f"END_VALID_TIME={end_valid_time}")
    print(f"VALID_INTERVAL_HOURS={interval_hours}")
    print(f"DT={dt}")
    print()

    for valid_time in _iter_valid_times(start_valid_time, end_valid_time, interval_hours):
        old_init, new_init, _ = _nmc_times(valid_time)
        print(f"--- VALID_TIME={valid_time} ---")
        print(f"OLD_INIT_TIME={old_init}")
        print(f"NEW_INIT_TIME={new_init}")

        for label, init_time in [("OLD", old_init), ("NEW", new_init)]:
            grib = grib_path(config, init_time)
            wps_file = ungrib_run_dir(config, init_time) / f"FILE:{init_time[:13]}"
            init_nc = init_file(config, init_time)
            print(f"  {label} GRIB   : {'OK' if grib.exists() else 'missing'} {grib}")
            print(f"  {label} WPS    : {'OK' if wps_file.exists() else 'missing'} {wps_file}")
            print(f"  {label} INIT   : {'OK' if init_nc.exists() else 'missing'} {init_nc}")

        f048 = restart_file(config, old_init, 48, dt)
        f024 = restart_file(config, new_init, 24, dt)
        pdir = pair_dir(config, valid_time)
        diff = pdir / "nmc_diff_f048_minus_f024.nc"
        print(f"  F048 restart: {'OK' if f048.exists() else 'missing'} {f048}")
        print(f"  F024 restart: {'OK' if f024.exists() else 'missing'} {f024}")
        print(f"  PAIR dir    : {'OK' if pdir.exists() else 'missing'} {pdir}")
        print(f"  DIFF file   : {'OK' if diff.exists() else 'missing'} {diff}")
        print()

    print("Doctor NMC concluído. Arquivos 'missing' podem ser produzidos pelo workflow; requisitos estáticos devem estar OK antes de submeter PBS.")
    return True
