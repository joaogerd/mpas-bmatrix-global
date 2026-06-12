from __future__ import annotations

import argparse
import csv
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .config import load_config
from .forecast import bflow_file
from .shell import require_file, symlink_force, write_text


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


@dataclass(frozen=True)
class BflowPair:
    valid_time: str
    f048: Path
    f024: Path


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def compact_time(value: str) -> str:
    return parse_time(value).strftime("%Y%m%d%H")


def iter_valid_times(start: str, end: str, step_hours: int):
    if step_hours <= 0:
        raise SystemExit("ERRO: --valid-interval-hours deve ser positivo.")
    current = parse_time(start)
    last = parse_time(end)
    step = timedelta(hours=step_hours)
    while current <= last:
        yield format_time(current)
        current += step


def default_workspace(config, start_valid_time: str, end_valid_time: str) -> Path:
    nproc = int(config["mesh"].get("nproc", 64))
    return (
        Path(config["project"]["work_root"])
        / "bmatrix"
        / "bflow_preprocessing"
        / f"np{nproc}_{compact_time(start_valid_time)}_{compact_time(end_valid_time)}"
    )


def build_pairs_from_range(config, start_valid_time: str, end_valid_time: str, step_hours: int, dt: int) -> list[BflowPair]:
    pairs: list[BflowPair] = []
    for valid_time in iter_valid_times(start_valid_time, end_valid_time, step_hours):
        valid = parse_time(valid_time)
        old_init = format_time(valid - timedelta(hours=48))
        new_init = format_time(valid - timedelta(hours=24))
        pairs.append(
            BflowPair(
                valid_time=valid_time,
                f048=bflow_file(config, old_init, 48, dt),
                f024=bflow_file(config, new_init, 24, dt),
            )
        )
    return pairs


def read_manifest(path: str | Path) -> list[BflowPair]:
    path = Path(path)
    require_file(path, "manifest.tsv")
    pairs: list[BflowPair] = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"valid_time", "f048", "f024"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise SystemExit(
                f"ERRO: manifesto {path} deve ter cabeçalho tabulado: valid_time, f048, f024"
            )
        for row in reader:
            pairs.append(
                BflowPair(
                    valid_time=row["valid_time"],
                    f048=Path(row["f048"]),
                    f024=Path(row["f024"]),
                )
            )
    return pairs


def write_manifest(path: str | Path, pairs: list[BflowPair]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["valid_time", "f048", "f024"], delimiter="\t")
        writer.writeheader()
        for pair in pairs:
            writer.writerow(
                {
                    "valid_time": pair.valid_time,
                    "f048": str(pair.f048),
                    "f024": str(pair.f024),
                }
            )
    return path


def validate_pairs(pairs: list[BflowPair]) -> None:
    if not pairs:
        raise SystemExit("ERRO: nenhum par Bflow encontrado.")
    for pair in pairs:
        require_file(pair.f048, f"f048 para {pair.valid_time}")
        require_file(pair.f024, f"f024 para {pair.valid_time}")


def link_pair_inputs(workspace: Path, pairs: list[BflowPair]) -> None:
    inputs = workspace / "inputs"
    for pair in pairs:
        vdir = inputs / compact_time(pair.valid_time)
        symlink_force(pair.f048, vdir / "f048.nc")
        symlink_force(pair.f024, vdir / "f024.nc")
        write_text(
            vdir / "pair.env",
            f"VALID_TIME={pair.valid_time}\nF048={pair.f048}\nF024={pair.f024}\n",
        )


def write_weights_script(config, workspace: Path) -> None:
    mesh_name = config["mesh"]["name"]
    invariant = Path(config["static"]["invariant"])
    script = f"""#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p ESMF_weights
cd ESMF_weights

module load ncl netcdf 2>/dev/null || module load ncl 2>/dev/null || true

ln -sf "{invariant}" ./MPAS_{mesh_name}.nc
isSinglePrecision=$(ncdump -h ./MPAS_{mesh_name}.nc | grep 'float latCell' | wc -l)
echo "isSinglePrecision=$isSinglePrecision"

cat > generateEsmfWeights.ncl <<'EOF_NCL'
load "$NCARG_ROOT/lib/ncarg/nclscripts/esmf/ESMF_regridding.ncl"

begin
    dstFileName = "MPAS_{mesh_name}.nc"
    interpMethod = "bilinear"

    srcGridName = "SCRIP_latlon_1p0.nc"
    dstGridName = "ESMF_MPAS_{mesh_name}.nc"
    wgtFile1    = "latlon_1p0_to_MPAS_{mesh_name}_" + interpMethod + ".nc"
    wgtFile2    = "MPAS_{mesh_name}_to_latlon_1p0_" + interpMethod + ".nc"

    SKIP_TRI_SCRIP_GEN  = False
    SKIP_MPAS_ESMF_GEN  = False
    SKIP_WGT_GEN_1      = False
    SKIP_WGT_GEN_2      = False

    if(.not.SKIP_TRI_SCRIP_GEN) then
      Opt                = True
      Opt@ForceOverwrite = True
      Opt@PrintTimings   = True
      Opt@LLCorner       = (/ -89.50d0, -179.50d0/)
      Opt@URCorner       = (/  89.50d0,  179.50d0/)
      Opt@Title          = "Fixed lat/lon grid : 1.0 degree"
      latlon_to_SCRIP(srcGridName,"1.0deg",Opt)
      delete(Opt)
    end if

    dfile = addfile(dstFileName,"r")
    r2d = 180.0/(atan(1)*4.0)
    lonCell = dfile->lonCell
    latCell = dfile->latCell
    lonCell = lonCell*r2d
    latCell = latCell*r2d

    if(.not.SKIP_MPAS_ESMF_GEN) then
      Opt                = True
      Opt@ForceOverwrite = True
      Opt@PrintTimings   = True
      Opt@InputFileName  = dstFileName
      print("Converting MPAS to Unstructured ESMF convention file ...")
      unstructured_to_ESMF(dstGridName,latCell,lonCell,Opt)
      delete(Opt)
    end if

    if(.not.SKIP_WGT_GEN_1) then
      Opt                      = True
      Opt@InterpMethod         = interpMethod
      Opt@SrcESMF              = False
      Opt@DstESMF              = True
      Opt@ForceOverwrite       = True
      Opt@PrintTimings         = True
      Opt@Debug                = True
      Opt@Check                = True
      Opt@DstGridType          = "unstructured"
      print("Generating interpolation weights from latlon to MPAS grid ...")
      ESMF_regrid_gen_weights(srcGridName, dstGridName, wgtFile1, Opt)
      delete(Opt)
    end if

    if(.not.SKIP_WGT_GEN_2) then
      Opt                      = True
      Opt@InterpMethod         = interpMethod
      Opt@SrcESMF              = True
      Opt@DstESMF              = False
      Opt@ForceOverwrite       = True
      Opt@PrintTimings         = True
      Opt@Debug                = True
      Opt@Check                = True
      Opt@DstGridType          = "unstructured"
      print("Generating interpolation weights from MPAS to latlon grid ...")
      ESMF_regrid_gen_weights(dstGridName, srcGridName, wgtFile2, Opt)
      delete(Opt)
    end if
end
EOF_NCL

ncl generateEsmfWeights.ncl
"""
    path = workspace / "scripts" / "01_generate_esmf_weights.bash"
    write_text(path, script)
    path.chmod(0o755)


def write_template_script(workspace: Path, first_ref: Path) -> None:
    script = f"""#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
module load nco 2>/dev/null || true

REF="{first_ref}"
test -f "$REF" || {{ echo "ERRO: arquivo não encontrado: $REF" >&2; exit 1; }}

rm -f template_PTB.nc template_PTB.nc_single template_PTB.nc_work

ncks -O -v theta "$REF" template_PTB.nc_single
# Preserve theta dimensions. Using theta=0.0 collapses the variable to a scalar in some NCO builds.
ncap2 -O -s 'theta=theta*0.0' template_PTB.nc_single template_PTB.nc_single

cp template_PTB.nc_single template_PTB.nc_work
ncrename -O -v theta,stream_function template_PTB.nc_work
ncatted -O -a long_name,stream_function,o,c,'stream function' template_PTB.nc_work
ncatted -O -a units,stream_function,o,c,'m^2 s^(-2)' template_PTB.nc_work
ncks -O -v stream_function template_PTB.nc_work template_PTB.nc

cp template_PTB.nc_single template_PTB.nc_work
ncrename -O -v theta,velocity_potential template_PTB.nc_work
ncatted -O -a long_name,velocity_potential,o,c,'velocity potential' template_PTB.nc_work
ncatted -O -a units,velocity_potential,o,c,'m^2 s^(-2)' template_PTB.nc_work
ncks -A -v velocity_potential template_PTB.nc_work template_PTB.nc

rm -f template_PTB.nc_single template_PTB.nc_work
ncdump -h template_PTB.nc | grep -E 'stream_function|velocity_potential'
"""
    path = workspace / "scripts" / "02_generate_template_ptb.bash"
    write_text(path, script)
    path.chmod(0o755)


def write_psichi_script(config, workspace: Path) -> None:
    mesh_name = config["mesh"]["name"]
    script = f"""#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
module load ncl 2>/dev/null || true

MANIFEST=manifest.tsv
WGT1="ESMF_weights/MPAS_{mesh_name}_to_latlon_1p0_bilinear.nc"
WGT2="ESMF_weights/latlon_1p0_to_MPAS_{mesh_name}_bilinear.nc"
TEMPLATE="template_PTB.nc"

test -f "$WGT1" || {{ echo "ERRO: peso não encontrado: $WGT1" >&2; exit 1; }}
test -f "$WGT2" || {{ echo "ERRO: peso não encontrado: $WGT2" >&2; exit 1; }}
test -f "$TEMPLATE" || {{ echo "ERRO: template não encontrado: $TEMPLATE" >&2; exit 1; }}

make_ncl() {{
  local input="$1"
  local output="$2"
  local script="$3"
  cat > "$script" <<EOF_NCL
load "\$NCARG_ROOT/lib/ncarg/nclscripts/esmf/ESMF_regridding.ncl"

begin
  FILE_IN  = "$input"
  FILE_OUT = "$output"
  FILE_TEMPLATE = "$TEMPLATE"
  FILE_WGT1 = "$WGT1"
  FILE_WGT2 = "$WGT2"

  setfileoption("nc","Format","LargeFile")
  f_in = addfile(FILE_IN, "r")

  u_cell = transpose( f_in->uReconstructZonal(0,:,:) )
  v_cell = transpose( f_in->uReconstructMeridional(0,:,:) )

  Opt = True
  Opt@PrintTimings = True
  u_ll = ESMF_regrid_with_weights(u_cell,FILE_WGT1,Opt)
  v_ll = ESMF_regrid_with_weights(v_cell,FILE_WGT1,Opt)
  delete(u_cell)
  delete(v_cell)

  dims = dimsizes(u_ll)
  nZ = dims(0)
  nY = dims(1)
  nX = dims(2)

  u = new( (/nZ,nY,nX/), float )
  v = new( (/nZ,nY,nX/), float )
  sf = new( (/nZ,nY,nX/), float )
  vp = new( (/nZ,nY,nX/), float )
  u(:,:,:) = u_ll(:,:,:)
  v(:,:,:) = v_ll(:,:,:)
  delete(u_ll)
  delete(v_ll)

  uv2sfvpf(u, v, sf, vp)
  delete(u)
  delete(v)

  sf_cell4write = f_in->theta(:,:,:)
  vp_cell4write = f_in->theta(:,:,:)
  sf_cell = ESMF_regrid_with_weights(sf,FILE_WGT2,Opt)
  vp_cell = ESMF_regrid_with_weights(vp,FILE_WGT2,Opt)
  delete(sf)
  delete(vp)

  ratio=6371229.0/6371220.0
  sf_cell_transpose = transpose(sf_cell(:,:) * ratio )
  vp_cell_transpose = transpose( -1.0 * vp_cell(:,:) * ratio )
  delete(sf_cell)
  delete(vp_cell)

  sf_cell4write(0,:,:)= (/ sf_cell_transpose(:,:) /)
  vp_cell4write(0,:,:)= (/ vp_cell_transpose(:,:) /)
  delete(sf_cell_transpose)
  delete(vp_cell_transpose)

  sf_cell4write@units = "m^2 s^(-2)"
  sf_cell4write@long_name = "stream function"
  vp_cell4write@units = "m^2 s^(-2)"
  vp_cell4write@long_name = "velocity potential"

  system("/bin/rm -f " + FILE_OUT)
  system("/bin/cp " + FILE_TEMPLATE + " " + FILE_OUT)
  system("/bin/chmod u+w " + FILE_OUT)
  f_out = addfile(FILE_OUT,"rw")
  f_out->stream_function    = sf_cell4write
  f_out->velocity_potential = vp_cell4write
  delete(sf_cell4write)
  delete(vp_cell4write)
  delete(f_out)
end
EOF_NCL
}}

tail -n +2 "$MANIFEST" | while IFS=$'\t' read -r valid f048 f024; do
  vcompact=$(python - <<PY
from datetime import datetime
print(datetime.strptime("$valid", "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H"))
PY
)
  outdir="output/$vcompact"
  mkdir -p "$outdir"

  in48="inputs/$vcompact/f048.nc"
  in24="inputs/$vcompact/f024.nc"
  test -f "$in48" || {{ echo "ERRO: input ausente: $in48" >&2; exit 1; }}
  test -f "$in24" || {{ echo "ERRO: input ausente: $in24" >&2; exit 1; }}

  rm -f "$outdir/FULL_f48.nc" "$outdir/FULL_f24.nc" "$outdir/uv_to_psichi_f48.ncl" "$outdir/uv_to_psichi_f24.ncl"
  make_ncl "$in48" "$outdir/FULL_f48.nc" "$outdir/uv_to_psichi_f48.ncl"
  make_ncl "$in24" "$outdir/FULL_f24.nc" "$outdir/uv_to_psichi_f24.ncl"

  echo "NCL f48 $valid"
  ncl "$outdir/uv_to_psichi_f48.ncl"
  echo "NCL f24 $valid"
  ncl "$outdir/uv_to_psichi_f24.ncl"
done
"""
    path = workspace / "scripts" / "03_convert_uv_to_psichi.bash"
    write_text(path, script)
    path.chmod(0o755)


def write_add_variables_script(workspace: Path) -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import netCDF4

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.tsv"

COPY_VARIABLES = [
    "surface_pressure",
    "uReconstructZonal",
    "uReconstructMeridional",
    "qv", "qc", "qr", "qi", "qs", "qg",
    "pressure_p", "pressure_base",
]


def compact(valid_time: str) -> str:
    return datetime.strptime(valid_time, "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H")


def ensure_dims(src, dst, var):
    for dim_name in var.dimensions:
        if dim_name not in dst.dimensions:
            src_dim = src.dimensions[dim_name]
            dst.createDimension(dim_name, None if src_dim.isunlimited() else len(src_dim))


def copy_attrs(src_var, dst_var):
    for attr in src_var.ncattrs():
        if attr == "_FillValue":
            continue
        try:
            dst_var.setncattr(attr, src_var.getncattr(attr))
        except Exception:
            pass


def upsert_var(dst, src_var, name, data=None):
    if name in dst.variables:
        out = dst.variables[name]
    else:
        fill_value = getattr(src_var, "_FillValue", None)
        kwargs = {}
        if fill_value is not None:
            kwargs["fill_value"] = fill_value
        out = dst.createVariable(name, src_var.dtype, src_var.dimensions, **kwargs)
        copy_attrs(src_var, out)
    out[:] = src_var[:] if data is None else data
    return out


def add_variables(input_path: Path, full_path: Path):
    if not full_path.exists():
        raise SystemExit(f"ERRO: FULL file não existe; rode primeiro uv_to_psichi: {full_path}")
    with netCDF4.Dataset(input_path) as src, netCDF4.Dataset(full_path, "a") as dst:
        theta = src.variables["theta"]
        ensure_dims(src, dst, theta)

        pressure = src.variables["pressure_p"][:] + src.variables["pressure_base"][:]
        temperature = src.variables["theta"][:] * ((pressure / 100000.0) ** (2.0 / 7.0))
        spechum = src.variables["qv"][:] / (1.0 + src.variables["qv"][:])

        for name in COPY_VARIABLES:
            if name not in src.variables:
                print(f"AVISO: variável ausente em {input_path}: {name}")
                continue
            var = src.variables[name]
            ensure_dims(src, dst, var)
            upsert_var(dst, var, name)

        pvar = src.variables["pressure_p"]
        out = upsert_var(dst, pvar, "pressure", pressure.astype(pvar.dtype, copy=False))
        out.setncattr("long_name", "pressure")
        out.setncattr("units", "Pa")

        tvar = upsert_var(dst, theta, "temperature", temperature.astype(theta.dtype, copy=False))
        tvar.setncattr("long_name", "temperature")
        tvar.setncattr("units", "K")

        qv = src.variables["qv"]
        svar = upsert_var(dst, qv, "spechum", spechum.astype(qv.dtype, copy=False))
        svar.setncattr("long_name", "specific humidity")
        svar.setncattr("units", "kg kg^{-1}")


def main():
    with MANIFEST.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            vdir = ROOT / "output" / compact(row["valid_time"])
            print(f"add variables {row['valid_time']} f48")
            add_variables(Path(row["f048"]), vdir / "FULL_f48.nc")
            print(f"add variables {row['valid_time']} f24")
            add_variables(Path(row["f024"]), vdir / "FULL_f24.nc")


if __name__ == "__main__":
    main()
'''
    path = workspace / "scripts" / "04_add_variables.py"
    write_text(path, script)
    path.chmod(0o755)


def write_ncdiff_script(workspace: Path) -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import numpy as np
import netCDF4

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.tsv"


def compact(valid_time: str) -> str:
    return datetime.strptime(valid_time, "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H")


def copy_attrs(src, dst):
    for attr in src.ncattrs():
        try:
            dst.setncattr(attr, src.getncattr(attr))
        except Exception:
            pass


def diff_file(f48: Path, f24: Path, out: Path, valid_time: str):
    if out.exists():
        out.unlink()
    with netCDF4.Dataset(f48) as ds48, netCDF4.Dataset(f24) as ds24, netCDF4.Dataset(out, "w") as dst:
        for name, dim in ds48.dimensions.items():
            dst.createDimension(name, None if dim.isunlimited() else len(dim))

        copy_attrs(ds48, dst)
        dst.setncattr("nmc_difference", "f048_minus_f024")
        dst.setncattr("valid_time", valid_time)
        dst.setncattr("source_f048", str(f48))
        dst.setncattr("source_f024", str(f24))

        common = [name for name in ds48.variables if name in ds24.variables]
        for name in common:
            v48 = ds48.variables[name]
            v24 = ds24.variables[name]
            if v48.dimensions != v24.dimensions:
                continue
            if not np.issubdtype(v48.dtype, np.number):
                continue
            fill_value = getattr(v48, "_FillValue", None)
            kwargs = {}
            if fill_value is not None:
                kwargs["fill_value"] = fill_value
            outvar = dst.createVariable(name, v48.dtype, v48.dimensions, **kwargs)
            copy_attrs(v48, outvar)
            outvar.setncattr("nmc_operation", "f048_minus_f024")
            outvar[:] = v48[:] - v24[:]


def main():
    with MANIFEST.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            vdir = ROOT / "output" / compact(row["valid_time"])
            f48 = vdir / "FULL_f48.nc"
            f24 = vdir / "FULL_f24.nc"
            out = vdir / "PTB_f48mf24.nc"
            print(f"ncdiff {row['valid_time']}: {out}")
            diff_file(f48, f24, out, row["valid_time"])


if __name__ == "__main__":
    main()
'''
    path = workspace / "scripts" / "05_ncdiff.py"
    write_text(path, script)
    path.chmod(0o755)


def write_master_script(workspace: Path) -> None:
    script = """#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

bash scripts/01_generate_esmf_weights.bash
bash scripts/02_generate_template_ptb.bash
bash scripts/03_convert_uv_to_psichi.bash
python scripts/04_add_variables.py
python scripts/05_ncdiff.py

find output -name 'PTB_f48mf24.nc' -printf '%p\n' | sort
"""
    path = workspace / "scripts" / "run_all_bflow.sh"
    write_text(path, script)
    path.chmod(0o755)


def write_readme(workspace: Path, pairs: list[BflowPair]) -> None:
    lines = [
        "# Bflow preprocessing workspace",
        "",
        "Generated by `mpasbflow prepare`.",
        "",
        "## Inputs",
        "",
    ]
    for pair in pairs:
        lines.extend(
            [
                f"- `{pair.valid_time}`",
                f"  - f048: `{pair.f048}`",
                f"  - f024: `{pair.f024}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Run",
            "",
            "```bash",
            "bash scripts/run_all_bflow.sh",
            "```",
            "",
            "Products are written below `output/YYYYMMDDHH/`.",
        ]
    )
    write_text(workspace / "README.md", "\n".join(lines) + "\n")


def prepare_workspace(config, pairs: list[BflowPair], workspace: Path, force: bool = False) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "scripts").mkdir(exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    (workspace / "output").mkdir(exist_ok=True)

    validate_pairs(pairs)
    write_manifest(workspace / "manifest.tsv", pairs)
    link_pair_inputs(workspace, pairs)
    write_weights_script(config, workspace)
    write_template_script(workspace, pairs[0].f048)
    write_psichi_script(config, workspace)
    write_add_variables_script(workspace)
    write_ncdiff_script(workspace)
    write_master_script(workspace)
    write_readme(workspace, pairs)
    return workspace


def prepare_command(args) -> int:
    config = load_config(args.config)
    dt = int(args.dt or config["runtime"]["config_dt"])

    if args.manifest:
        pairs = read_manifest(args.manifest)
        start = pairs[0].valid_time
        end = pairs[-1].valid_time
    else:
        pairs = build_pairs_from_range(
            config,
            args.start_valid_time,
            args.end_valid_time,
            args.valid_interval_hours,
            dt,
        )
        start = args.start_valid_time
        end = args.end_valid_time

    workspace = Path(args.workspace) if args.workspace else default_workspace(config, start, end)
    workspace = prepare_workspace(config, pairs, workspace, force=args.force)

    print("=== Bflow preprocessing workspace ===")
    print(f"WORKSPACE={workspace}")
    print(f"MANIFEST={workspace / 'manifest.tsv'}")
    print(f"PAIRS={len(pairs)}")
    print()
    print("Para rodar:")
    print(f"  cd {workspace}")
    print("  bash scripts/run_all_bflow.sh | tee logs/run_all_bflow.log")
    return 0


def run_command(args) -> int:
    workspace = Path(args.workspace)
    require_file(workspace / "scripts" / "run_all_bflow.sh", "run_all_bflow.sh")
    env = os.environ.copy()
    proc = subprocess.run(
        ["bash", "scripts/run_all_bflow.sh"],
        cwd=workspace,
        env=env,
        check=False,
    )
    return proc.returncode


def parser():
    p = argparse.ArgumentParser(prog="mpasbflow", description="Prepara e executa o Bflow preprocessing do MPAS-JEDI")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare", help="Cria workspace/scripts Bflow a partir do range ou manifesto")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--start-valid-time")
    prep.add_argument("--end-valid-time")
    prep.add_argument("--valid-interval-hours", type=int, default=24)
    prep.add_argument("--dt", type=int)
    prep.add_argument("--manifest")
    prep.add_argument("--workspace")
    prep.add_argument("--force", action="store_true")
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("run", help="Executa scripts/run_all_bflow.sh em um workspace já preparado")
    run.add_argument("--workspace", required=True)
    run.set_defaults(func=run_command)

    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.cmd == "prepare" and not args.manifest:
        if not args.start_valid_time or not args.end_valid_time:
            raise SystemExit("ERRO: informe --manifest ou --start-valid-time e --end-valid-time.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
