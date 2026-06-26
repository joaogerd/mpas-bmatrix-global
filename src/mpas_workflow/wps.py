from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import subprocess

from .config import date_part, cycle_part, ymdh
from .shell import require_file, run, symlink_force, write_text


REQUIRED_SURFACE_LEVELS = ("2013.0", "2001.0")


def grib_path(config, init_time, fhour="000"):
    data_root = Path(config["project"]["data_root"])
    gfs_date = date_part(init_time)
    gfs_cycle = cycle_part(init_time)
    return data_root / "external" / "gfs" / gfs_date / gfs_cycle / f"gfs.t{gfs_cycle}z.pgrb2.0p25.f{fhour}"


def ungrib_run_dir(config, init_time, fhour="000"):
    work_root = Path(config["project"]["work_root"])
    return work_root / "wps_ungrib" / f"gfs.{ymdh(init_time)}.f{fhour}"


def _write_namelist_wps(path: Path, init_time: str, fhour: str = "000"):
    start = datetime.strptime(init_time, "%Y-%m-%d_%H:%M:%S") + timedelta(hours=int(fhour))
    end = start

    content = f"""&share
 wrf_core = 'ARW',
 max_dom = 1,
 start_date = '{start:%Y-%m-%d_%H}:00:00',
 end_date   = '{end:%Y-%m-%d_%H}:00:00',
 interval_seconds = 21600,
 io_form_geogrid = 2,
 /

&ungrib
 out_format = 'WPS',
 prefix = 'FILE',
 /

&metgrid
 fg_name = 'FILE',
 io_form_metgrid = 2,
 /
"""
    write_text(path, content)
    return path


def _clean_ungrib_run_dir(run_dir: Path):
    patterns = [
        "GRIBFILE.*",
        "FILE:*",
        "PFILE:*",
        "Vtable",
        "namelist.wps",
        "ungrib.exe",
        "link_grib.csh",
        "ungrib.stdout.log",
    ]
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.exists() or path.is_symlink():
                path.unlink()


def _download_gfs(grib: Path, gfs_date: str, gfs_cycle: str, fhour: str) -> None:
    grib.parent.mkdir(parents=True, exist_ok=True)
    url = (
        "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
        f"?dir=%2Fgfs.{gfs_date}%2F{gfs_cycle}%2Fatmos"
        f"&file=gfs.t{gfs_cycle}z.pgrb2.0p25.f{fhour}"
        "&all_lev=on&all_var=on"
    )
    temporary = grib.with_name(f"{grib.name}.download")
    if temporary.exists():
        temporary.unlink()
    run(["curl", "-fL", "--retry", "3", "-o", str(temporary), url])
    temporary.replace(grib)


def _run_ungrib_logged(run_dir: Path) -> str:
    cmd = ["./ungrib.exe"]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(
        cmd,
        cwd=run_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = proc.stdout or ""
    print(output, end="", flush=True)
    write_text(run_dir / "ungrib.stdout.log", output)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=output)
    return output


def missing_surface_inventory_levels(ungrib_output: str) -> list[str]:
    """Return required GFS surface inventory levels absent from ungrib stdout.

    GFS 0.25 analyses accepted by the legacy MPAS-init path include the 2013.0
    and 2001.0 surface inventory rows. Their absence means the GRIB cache lacks
    the surface/land records needed by MPAS init (for example LANDSEA).
    """
    present = {
        match.group(1)
        for line in ungrib_output.splitlines()
        if (match := re.match(r"^\s*(\d+\.\d+)\s+[XO](?:\s|$)", line))
    }
    return [level for level in REQUIRED_SURFACE_LEVELS if level not in present]


def _validate_surface_inventory(ungrib_output: str, inventory_log: Path) -> None:
    missing = missing_surface_inventory_levels(ungrib_output)
    if missing:
        raise SystemExit(
            "ERRO: inventário do ungrib não contém os níveis de superfície obrigatórios: "
            f"{', '.join(missing)}\n"
            "O GRIB GFS em cache está incompleto para o MPAS-init "
            "(campos como LANDSEA não foram disponibilizados).\n"
            f"Log do inventário: {inventory_log}"
        )


def _run_ungrib_once(wps: dict, run_dir: Path, grib: Path, init_time: str, fhour: str) -> Path:
    _clean_ungrib_run_dir(run_dir)
    symlink_force(wps["vtable_gfs"], run_dir / "Vtable")
    symlink_force(wps["ungrib_exe"], run_dir / "ungrib.exe")
    symlink_force(wps["link_grib"], run_dir / "link_grib.csh")
    _write_namelist_wps(run_dir / "namelist.wps", init_time, fhour)

    run(["./link_grib.csh", str(grib)], cwd=run_dir)
    output = _run_ungrib_logged(run_dir)
    _validate_surface_inventory(output, run_dir / "ungrib.stdout.log")

    expected = run_dir / f"FILE:{init_time[:13]}"
    require_file(expected, "WPS FILE")
    return expected


def _quarantine_invalid_grib(grib: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = grib.with_name(f"{grib.name}.invalid-{stamp}")
    grib.replace(backup)
    print(f"AVISO: GFS em cache movido para {backup}")
    return backup


def run_ungrib(config, init_time, fhour="000", download=True):
    wps = config["wps"]
    require_file(wps["ungrib_exe"], "ungrib.exe")
    require_file(wps["link_grib"], "link_grib.csh")
    require_file(wps["vtable_gfs"], "Vtable.GFS")

    gfs_date = date_part(init_time)
    gfs_cycle = cycle_part(init_time)
    grib = grib_path(config, init_time, fhour)
    run_dir = ungrib_run_dir(config, init_time, fhour)
    run_dir.mkdir(parents=True, exist_ok=True)

    cached_grib = grib.exists() and grib.stat().st_size > 0
    if download and not cached_grib:
        _download_gfs(grib, gfs_date, gfs_cycle, fhour)

    require_file(grib, "GFS GRIB2")
    try:
        expected = _run_ungrib_once(wps, run_dir, grib, init_time, fhour)
    except SystemExit:
        if not (download and cached_grib):
            raise

        _quarantine_invalid_grib(grib)
        print("Baixando novamente o GFS completo e repetindo ungrib...")
        _download_gfs(grib, gfs_date, gfs_cycle, fhour)
        expected = _run_ungrib_once(wps, run_dir, grib, init_time, fhour)

    print(f"OK: ungrib gerou {expected}")
    return expected
