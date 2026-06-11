from __future__ import annotations

from pathlib import Path
from .config import date_part, cycle_part, ymdh
from .shell import require_file, run, symlink_force


def grib_path(config, init_time, fhour="000"):
    data_root = Path(config["project"]["data_root"])
    gfs_date = date_part(init_time)
    gfs_cycle = cycle_part(init_time)
    return data_root / "external" / "gfs" / gfs_date / gfs_cycle / f"gfs.t{gfs_cycle}z.pgrb2.0p25.f{fhour}"


def ungrib_run_dir(config, init_time, fhour="000"):
    work_root = Path(config["project"]["work_root"])
    return work_root / "wps_ungrib" / f"gfs.{ymdh(init_time)}.f{fhour}"


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

    if download and not grib.exists():
        grib.parent.mkdir(parents=True, exist_ok=True)
        url = (
            "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
            f"?dir=%2Fgfs.{gfs_date}%2F{gfs_cycle}%2Fatmos"
            f"&file=gfs.t{gfs_cycle}z.pgrb2.0p25.f{fhour}"
            "&all_lev=on&all_var=on"
        )
        run(["curl", "-fL", "-o", str(grib), url])

    require_file(grib, "GFS GRIB2")
    symlink_force(wps["vtable_gfs"], run_dir / "Vtable")
    run([wps["link_grib"], str(grib)], cwd=run_dir)
    run([wps["ungrib_exe"]], cwd=run_dir)

    expected = run_dir / f"FILE:{init_time[:13].replace(':', '')}"
    # WPS usa FILE:YYYY-MM-DD_HH
    expected = run_dir / f"FILE:{init_time[:13]}"
    require_file(expected, "WPS FILE")
    print(f"OK: ungrib gerou {expected}")
    return expected
