from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import date_part, cycle_part, ymdh
from .shell import require_file, run, symlink_force, write_text


REQUIRED_WPS_FIELDS = (
    "LANDSEA",
    "LANDN",
    "SOILHGT",
    "SKINTEMP",
    "PSFC",
    "PMSL",
)


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


def _run_ungrib_once(wps: dict, run_dir: Path, grib: Path, init_time: str, fhour: str) -> Path:
    _clean_ungrib_run_dir(run_dir)
    symlink_force(wps["vtable_gfs"], run_dir / "Vtable")
    symlink_force(wps["ungrib_exe"], run_dir / "ungrib.exe")
    symlink_force(wps["link_grib"], run_dir / "link_grib.csh")
    _write_namelist_wps(run_dir / "namelist.wps", init_time, fhour)

    run(["./link_grib.csh", str(grib)], cwd=run_dir)
    run(["./ungrib.exe"], cwd=run_dir)

    expected = run_dir / f"FILE:{init_time[:13]}"
    require_file(expected, "WPS FILE")
    return expected


def missing_wps_fields(path: Path, required_fields=REQUIRED_WPS_FIELDS) -> list[str]:
    """Return required WPS field labels absent from one intermediate FILE:* artifact."""
    payload = Path(path).read_bytes()
    return [field for field in required_fields if field.encode("ascii") not in payload]


def _validate_wps_fields(path: Path) -> None:
    missing = missing_wps_fields(path)
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"ERRO: WPS FILE incompleto: {path}\n"
            f"Campos obrigatórios ausentes: {names}\n"
            "O GRIB GFS em cache pode estar incompleto; o MPAS-init não será submetido."
        )


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
    expected = _run_ungrib_once(wps, run_dir, grib, init_time, fhour)

    try:
        _validate_wps_fields(expected)
    except SystemExit:
        if not (download and cached_grib):
            raise

        _quarantine_invalid_grib(grib)
        print("Baixando novamente o GFS completo e repetindo ungrib...")
        _download_gfs(grib, gfs_date, gfs_cycle, fhour)
        expected = _run_ungrib_once(wps, run_dir, grib, init_time, fhour)
        _validate_wps_fields(expected)

    print(f"OK: ungrib gerou {expected}")
    return expected
