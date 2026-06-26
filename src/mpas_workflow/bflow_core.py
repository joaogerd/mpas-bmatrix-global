from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import netCDF4
import numpy as np

from .config import load_config
from .forecast import bflow_file
from .shell import require_file, symlink_force, write_text


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"

COPY_VARIABLES = [
    "surface_pressure",
    "uReconstructZonal",
    "uReconstructMeridional",
    "qv",
    "qc",
    "qr",
    "qi",
    "qs",
    "qg",
    "pressure_p",
    "pressure_base",
]

FULL_REQUIRED = [
    "stream_function",
    "velocity_potential",
]

PTB_REQUIRED = [
    "stream_function",
    "velocity_potential",
    "temperature",
    "spechum",
    "pressure",
    "surface_pressure",
    "uReconstructZonal",
    "uReconstructMeridional",
]


@dataclass(frozen=True)
class BflowPair:
    valid_time: str
    f048: Path
    f024: Path


@dataclass(frozen=True)
class BflowPaths:
    workspace: Path

    @property
    def manifest(self) -> Path:
        return self.workspace / "manifest.tsv"

    @property
    def inputs(self) -> Path:
        return self.workspace / "inputs"

    @property
    def output(self) -> Path:
        return self.workspace / "output"

    @property
    def logs(self) -> Path:
        return self.workspace / "logs"

    @property
    def esmf_weights(self) -> Path:
        return self.workspace / "ESMF_weights"

    @property
    def template_ptb(self) -> Path:
        return self.workspace / "template_PTB.nc"

    def valid_output_dir(self, valid_time: str) -> Path:
        return self.output / compact_time(valid_time)

    def linked_input(self, valid_time: str, lead: str) -> Path:
        if lead not in {"f048", "f024"}:
            raise ValueError(f"lead inválido: {lead}")
        return self.inputs / compact_time(valid_time) / f"{lead}.nc"

    def full_file(self, valid_time: str, lead: str) -> Path:
        if lead not in {"f48", "f24"}:
            raise ValueError(f"lead inválido: {lead}")
        return self.valid_output_dir(valid_time) / f"FULL_{lead}.nc"

    def ptb_file(self, valid_time: str) -> Path:
        return self.valid_output_dir(valid_time) / "PTB_f48mf24.nc"


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def compact_time(value: str) -> str:
    return parse_time(value).strftime("%Y%m%d%H")


def iter_valid_times(start: str, end: str, step_hours: int) -> Iterable[str]:
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


def build_pairs_from_range(
    config,
    start_valid_time: str,
    end_valid_time: str,
    step_hours: int,
    dt: int,
) -> list[BflowPair]:
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


def write_manifest(path: str | Path, pairs: Sequence[BflowPair]) -> Path:
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


def validate_pairs(pairs: Sequence[BflowPair]) -> None:
    if not pairs:
        raise SystemExit("ERRO: nenhum par BFLOW encontrado.")
    for pair in pairs:
        require_file(pair.f048, f"f048 para {pair.valid_time}")
        require_file(pair.f024, f"f024 para {pair.valid_time}")


def link_pair_inputs(paths: BflowPaths, pairs: Sequence[BflowPair]) -> None:
    for pair in pairs:
        vdir = paths.inputs / compact_time(pair.valid_time)
        symlink_force(pair.f048, vdir / "f048.nc")
        symlink_force(pair.f024, vdir / "f024.nc")
        write_text(
            vdir / "pair.env",
            f"VALID_TIME={pair.valid_time}\nF048={pair.f048}\nF024={pair.f024}\n",
        )


def write_readme(paths: BflowPaths, pairs: Sequence[BflowPair]) -> None:
    lines = [
        "# BFLOW preprocessing workspace",
        "",
        "Generated by `mpasbflow prepare` or `mpasbflow all`.",
        "",
        "This workspace is now executed by the Python BFLOW pipeline.",
        "External NCL/NCO-compatible tools may still be called by Python for ESMF weights and `u/v -> psi/chi` conversion.",
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
            "mpasbflow run --workspace $(pwd) --clean-output",
            "```",
            "",
            "Products are written below `output/YYYYMMDDHH/`.",
        ]
    )
    write_text(paths.workspace / "README.md", "\n".join(lines) + "\n")


def prepare_workspace(config, pairs: Sequence[BflowPair], workspace: Path, force: bool = False) -> Path:
    paths = BflowPaths(Path(workspace))
    paths.workspace.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(exist_ok=True)
    paths.output.mkdir(exist_ok=True)
    paths.inputs.mkdir(exist_ok=True)
    paths.esmf_weights.mkdir(exist_ok=True)

    validate_pairs(pairs)
    write_manifest(paths.manifest, pairs)
    link_pair_inputs(paths, pairs)
    write_readme(paths, pairs)
    return paths.workspace


def _append_log(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(text)


def run_logged_shell(command: str, cwd: Path, log_path: Path) -> None:
    """Run a shell command and mirror stdout/stderr into a log file.

    This is intentionally the only shell boundary in the BFLOW Python pipeline.
    It is used for external scientific tools that are not Python yet, mainly NCL.
    """
    cwd = Path(cwd)
    log_path = Path(log_path)
    _append_log(log_path, f"\n+ {command}\n")
    print(f"+ {command}", flush=True)
    proc = subprocess.Popen(
        ["bash", "-lc", command],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout is not None
    with log_path.open("a") as log:
        for line in proc.stdout:
            print(line, end="", flush=True)
            log.write(line)
    rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"ERRO: comando falhou com código {rc}: {command}\nLOG={log_path}")


def generate_esmf_weights(config, paths: BflowPaths) -> None:
    mesh_name = config["mesh"]["name"]
    invariant = Path(config["static"]["invariant"])
    require_file(invariant, "static.invariant")
    paths.esmf_weights.mkdir(parents=True, exist_ok=True)
    symlink_force(invariant, paths.esmf_weights / f"MPAS_{mesh_name}.nc")

    ncl = f'''load "$NCARG_ROOT/lib/ncarg/nclscripts/esmf/ESMF_regridding.ncl"

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
'''
    script = paths.esmf_weights / "generateEsmfWeights.ncl"
    write_text(script, ncl)
    run_logged_shell(
        "module load ncl netcdf 2>/dev/null || module load ncl 2>/dev/null || true; "
        f"ncl {script.name} < /dev/null",
        cwd=paths.esmf_weights,
        log_path=paths.logs / "01_generate_esmf_weights.log",
    )


def _copy_global_attrs(src: netCDF4.Dataset, dst: netCDF4.Dataset) -> None:
    for attr in src.ncattrs():
        try:
            dst.setncattr(attr, src.getncattr(attr))
        except Exception:
            pass


def _copy_var_attrs(src_var, dst_var) -> None:
    for attr in src_var.ncattrs():
        if attr == "_FillValue":
            continue
        try:
            dst_var.setncattr(attr, src_var.getncattr(attr))
        except Exception:
            pass


def _ensure_dims(src: netCDF4.Dataset, dst: netCDF4.Dataset, var) -> None:
    for dim_name in var.dimensions:
        if dim_name not in dst.dimensions:
            src_dim = src.dimensions[dim_name]
            dst.createDimension(dim_name, None if src_dim.isunlimited() else len(src_dim))


def create_template_ptb(paths: BflowPaths, first_ref: Path) -> None:
    require_file(first_ref, "primeiro arquivo de referência BFLOW")
    if paths.template_ptb.exists():
        paths.template_ptb.unlink()

    with netCDF4.Dataset(first_ref) as src, netCDF4.Dataset(paths.template_ptb, "w") as dst:
        if "theta" not in src.variables:
            raise SystemExit(f"ERRO: variável theta ausente em {first_ref}")
        theta = src.variables["theta"]
        _copy_global_attrs(src, dst)
        _ensure_dims(src, dst, theta)
        fill_value = getattr(theta, "_FillValue", None)
        kwargs = {"fill_value": fill_value} if fill_value is not None else {}
        for name, long_name in [
            ("stream_function", "stream function"),
            ("velocity_potential", "velocity potential"),
        ]:
            out = dst.createVariable(name, theta.dtype, theta.dimensions, **kwargs)
            out[:] = np.zeros(theta.shape, dtype=theta.dtype)
            out.setncattr("long_name", long_name)
            out.setncattr("units", "m^2 s^(-2)")


def _uv_to_psichi_ncl(input_path: Path, output_path: Path, template: Path, wgt1: Path, wgt2: Path) -> str:
    return f'''load "$NCARG_ROOT/lib/ncarg/nclscripts/esmf/ESMF_regridding.ncl"

begin
  FILE_IN  = "{input_path}"
  FILE_OUT = "{output_path}"
  FILE_TEMPLATE = "{template}"
  FILE_WGT1 = "{wgt1}"
  FILE_WGT2 = "{wgt2}"

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
'''


def convert_uv_to_psichi(config, paths: BflowPaths, pairs: Sequence[BflowPair]) -> None:
    mesh_name = config["mesh"]["name"]
    wgt1 = paths.esmf_weights / f"MPAS_{mesh_name}_to_latlon_1p0_bilinear.nc"
    wgt2 = paths.esmf_weights / f"latlon_1p0_to_MPAS_{mesh_name}_bilinear.nc"
    require_file(wgt1, "peso ESMF MPAS -> latlon")
    require_file(wgt2, "peso ESMF latlon -> MPAS")
    require_file(paths.template_ptb, "template_PTB.nc")

    for pair in pairs:
        outdir = paths.valid_output_dir(pair.valid_time)
        outdir.mkdir(parents=True, exist_ok=True)
        jobs = [
            (paths.linked_input(pair.valid_time, "f048"), paths.full_file(pair.valid_time, "f48"), "f48"),
            (paths.linked_input(pair.valid_time, "f024"), paths.full_file(pair.valid_time, "f24"), "f24"),
        ]
        for input_path, output_path, label in jobs:
            require_file(input_path, f"input {label} para {pair.valid_time}")
            script = outdir / f"uv_to_psichi_{label}.ncl"
            write_text(script, _uv_to_psichi_ncl(input_path, output_path, paths.template_ptb, wgt1, wgt2))
            run_logged_shell(
                "module load ncl 2>/dev/null || true; " f"ncl {script} < /dev/null",
                cwd=paths.workspace,
                log_path=paths.logs / "03_convert_uv_to_psichi.log",
            )
            require_file(output_path, f"FULL_{label}.nc gerado pelo NCL")


def _upsert_var(dst: netCDF4.Dataset, src_var, name: str, data=None):
    if name in dst.variables:
        out = dst.variables[name]
    else:
        fill_value = getattr(src_var, "_FillValue", None)
        kwargs = {"fill_value": fill_value} if fill_value is not None else {}
        out = dst.createVariable(name, src_var.dtype, src_var.dimensions, **kwargs)
        _copy_var_attrs(src_var, out)
    out[:] = src_var[:] if data is None else data
    return out


def add_variables(input_path: Path, full_path: Path) -> None:
    if not full_path.exists():
        raise SystemExit(f"ERRO: FULL file não existe; rode primeiro uv_to_psichi: {full_path}")
    with netCDF4.Dataset(input_path) as src, netCDF4.Dataset(full_path, "a") as dst:
        for name in ["theta", "pressure_p", "pressure_base", "qv"]:
            if name not in src.variables:
                raise SystemExit(f"ERRO: variável obrigatória ausente em {input_path}: {name}")

        theta = src.variables["theta"]
        _ensure_dims(src, dst, theta)

        pressure = src.variables["pressure_p"][:] + src.variables["pressure_base"][:]
        temperature = src.variables["theta"][:] * ((pressure / 100000.0) ** (2.0 / 7.0))
        spechum = src.variables["qv"][:] / (1.0 + src.variables["qv"][:])

        for name in COPY_VARIABLES:
            if name not in src.variables:
                print(f"AVISO: variável ausente em {input_path}: {name}", flush=True)
                continue
            var = src.variables[name]
            _ensure_dims(src, dst, var)
            _upsert_var(dst, var, name)

        pvar = src.variables["pressure_p"]
        out = _upsert_var(dst, pvar, "pressure", pressure.astype(pvar.dtype, copy=False))
        out.setncattr("long_name", "pressure")
        out.setncattr("units", "Pa")

        tvar = _upsert_var(dst, theta, "temperature", temperature.astype(theta.dtype, copy=False))
        tvar.setncattr("long_name", "temperature")
        tvar.setncattr("units", "K")

        qv = src.variables["qv"]
        svar = _upsert_var(dst, qv, "spechum", spechum.astype(qv.dtype, copy=False))
        svar.setncattr("long_name", "specific humidity")
        svar.setncattr("units", "kg kg^{-1}")


def add_variables_for_pairs(paths: BflowPaths, pairs: Sequence[BflowPair]) -> None:
    for pair in pairs:
        print(f"add variables {pair.valid_time} f48", flush=True)
        add_variables(pair.f048, paths.full_file(pair.valid_time, "f48"))
        print(f"add variables {pair.valid_time} f24", flush=True)
        add_variables(pair.f024, paths.full_file(pair.valid_time, "f24"))


def diff_file(f48: Path, f24: Path, out: Path, valid_time: str) -> None:
    if out.exists():
        out.unlink()
    with netCDF4.Dataset(f48) as ds48, netCDF4.Dataset(f24) as ds24, netCDF4.Dataset(out, "w") as dst:
        for name, dim in ds48.dimensions.items():
            dst.createDimension(name, None if dim.isunlimited() else len(dim))

        _copy_global_attrs(ds48, dst)
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
            kwargs = {"fill_value": fill_value} if fill_value is not None else {}
            outvar = dst.createVariable(name, v48.dtype, v48.dimensions, **kwargs)
            _copy_var_attrs(v48, outvar)
            outvar.setncattr("nmc_operation", "f048_minus_f024")
            outvar[:] = v48[:] - v24[:]


def compute_differences(paths: BflowPaths, pairs: Sequence[BflowPair]) -> None:
    for pair in pairs:
        out = paths.ptb_file(pair.valid_time)
        print(f"ncdiff {pair.valid_time}: {out}", flush=True)
        diff_file(
            paths.full_file(pair.valid_time, "f48"),
            paths.full_file(pair.valid_time, "f24"),
            out,
            pair.valid_time,
        )


def require_vars(path: Path, names: Sequence[str]) -> None:
    if not path.exists():
        raise SystemExit(f"ERRO: produto ausente: {path}")
    with netCDF4.Dataset(path) as ds:
        for name in names:
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente em {path}: {name}")
            var = ds.variables[name]
            if name in {"stream_function", "velocity_potential"}:
                expected = ("Time", "nCells", "nVertLevels")
                if tuple(var.dimensions) != expected:
                    raise SystemExit(
                        f"ERRO: dimensões inválidas para {name} em {path}: "
                        f"{var.dimensions}; esperado {expected}"
                    )


def validate_products(paths: BflowPaths, pairs: Sequence[BflowPair], stage: str) -> None:
    if stage not in {"full", "ptb"}:
        raise ValueError(f"stage inválido: {stage}")
    for pair in pairs:
        if stage == "full":
            require_vars(paths.full_file(pair.valid_time, "f48"), FULL_REQUIRED)
            require_vars(paths.full_file(pair.valid_time, "f24"), FULL_REQUIRED)
        else:
            require_vars(paths.ptb_file(pair.valid_time), PTB_REQUIRED)
        print(f"OK {stage}: {pair.valid_time}", flush=True)


def clean_output(paths: BflowPaths) -> None:
    if paths.output.exists():
        shutil.rmtree(paths.output)
    paths.output.mkdir(parents=True, exist_ok=True)


def run_workspace(
    workspace: Path,
    *,
    clean_output_flag: bool = False,
    skip_weights: bool = False,
    config=None,
) -> int:
    paths = BflowPaths(Path(workspace))
    require_file(paths.manifest, "manifest.tsv")
    pairs = read_manifest(paths.manifest)
    if config is None:
        config_path = paths.workspace / "config.yaml"
        if config_path.exists():
            config = load_config(config_path)
        else:
            config = load_config(DEFAULT_CONFIG)

    paths.logs.mkdir(parents=True, exist_ok=True)
    if clean_output_flag:
        print("Cleaning output directory", flush=True)
        clean_output(paths)

    if not skip_weights:
        generate_esmf_weights(config, paths)
    else:
        print("Skipping ESMF weights because --skip-weights was provided", flush=True)

    create_template_ptb(paths, pairs[0].f048)
    convert_uv_to_psichi(config, paths, pairs)
    validate_products(paths, pairs, "full")
    add_variables_for_pairs(paths, pairs)
    compute_differences(paths, pairs)
    validate_products(paths, pairs, "ptb")

    for pair in pairs:
        print(paths.ptb_file(pair.valid_time), flush=True)
    return 0


def run_pipeline(
    config,
    pairs: Sequence[BflowPair],
    workspace: Path,
    *,
    force: bool = False,
    clean_output_flag: bool = False,
    skip_weights: bool = False,
) -> int:
    workspace = prepare_workspace(config, pairs, workspace, force=force)
    return run_workspace(
        workspace,
        clean_output_flag=clean_output_flag,
        skip_weights=skip_weights,
        config=config,
    )


def pairs_from_args(args, config) -> tuple[list[BflowPair], str, str]:
    dt = int(args.dt or config["runtime"]["config_dt"])

    if getattr(args, "manifest", None):
        pairs = read_manifest(args.manifest)
        start = pairs[0].valid_time
        end = pairs[-1].valid_time
    else:
        if not args.start_valid_time or not args.end_valid_time:
            raise SystemExit("ERRO: informe --manifest ou --start-valid-time e --end-valid-time.")
        pairs = build_pairs_from_range(
            config,
            args.start_valid_time,
            args.end_valid_time,
            args.valid_interval_hours,
            dt,
        )
        start = args.start_valid_time
        end = args.end_valid_time

    return pairs, start, end


def workspace_from_args(args, config, start: str, end: str) -> Path:
    return Path(args.workspace) if getattr(args, "workspace", None) else default_workspace(config, start, end)


def prepare_command(args) -> int:
    config = load_config(args.config)
    pairs, start, end = pairs_from_args(args, config)
    workspace = workspace_from_args(args, config, start, end)
    workspace = prepare_workspace(config, pairs, workspace, force=args.force)

    print("=== BFLOW preprocessing workspace ===")
    print(f"WORKSPACE={workspace}")
    print(f"MANIFEST={Path(workspace) / 'manifest.tsv'}")
    print(f"PAIRS={len(pairs)}")
    print()
    print("Para rodar:")
    print(f"  mpasbflow run --workspace {workspace} --clean-output --config {args.config}")
    return 0


def run_command(args) -> int:
    config = load_config(args.config)
    return run_workspace(
        Path(args.workspace),
        clean_output_flag=args.clean_output,
        skip_weights=args.skip_weights,
        config=config,
    )


def all_command(args) -> int:
    config = load_config(args.config)
    pairs, start, end = pairs_from_args(args, config)
    workspace = workspace_from_args(args, config, start, end)

    print("=== BFLOW preprocessing all ===")
    print(f"WORKSPACE={workspace}")
    print(f"PAIRS={len(pairs)}")
    print(f"LOGDIR={Path(workspace) / 'logs'}")
    print()

    return run_pipeline(
        config,
        pairs,
        workspace,
        force=args.force,
        clean_output_flag=args.clean_output,
        skip_weights=args.skip_weights,
    )


def add_common_range_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--start-valid-time")
    parser.add_argument("--end-valid-time")
    parser.add_argument("--valid-interval-hours", type=int, default=24)
    parser.add_argument("--dt", type=int)
    parser.add_argument("--manifest")
    parser.add_argument("--workspace")
    parser.add_argument("--force", action="store_true")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mpasbflow",
        description="Prepara e executa o BFLOW preprocessing do MPAS-JEDI",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare", help="Cria workspace BFLOW a partir do range ou manifesto")
    add_common_range_args(prep)
    prep.set_defaults(func=prepare_command)

    run = sub.add_parser("run", help="Executa o pipeline Python BFLOW em um workspace preparado")
    run.add_argument("--workspace", required=True)
    run.add_argument("--config", default=DEFAULT_CONFIG)
    run.add_argument("--clean-output", action="store_true")
    run.add_argument("--skip-weights", action="store_true")
    run.set_defaults(func=run_command)

    allp = sub.add_parser("all", help="Prepara, limpa opcionalmente, executa e valida o BFLOW de ponta a ponta")
    add_common_range_args(allp)
    allp.add_argument("--clean-output", action="store_true")
    allp.add_argument("--skip-weights", action="store_true")
    allp.set_defaults(func=all_command)

    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)
