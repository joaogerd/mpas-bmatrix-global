from __future__ import annotations

from pathlib import Path

from ..shell import write_text
from .external import require_files, run_shell
from .model import BflowPair, compact_time


def render_uv_to_psichi_ncl(input_path: Path, output_path: Path, template: Path, wgt1: Path, wgt2: Path) -> str:
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


def convert_pair(config, workspace: Path, pair: BflowPair) -> None:
    mesh_name = config["mesh"]["name"]
    wgt1 = workspace / "ESMF_weights" / f"MPAS_{mesh_name}_to_latlon_1p0_bilinear.nc"
    wgt2 = workspace / "ESMF_weights" / f"latlon_1p0_to_MPAS_{mesh_name}_bilinear.nc"
    template = workspace / "template_PTB.nc"
    require_files([wgt1, wgt2, template], "uv_to_psichi")

    vcompact = compact_time(pair.valid_time)
    outdir = workspace / "output" / vcompact
    outdir.mkdir(parents=True, exist_ok=True)
    for label, input_path, output_path in [
        ("f48", workspace / "inputs" / vcompact / "f048.nc", outdir / "FULL_f48.nc"),
        ("f24", workspace / "inputs" / vcompact / "f024.nc", outdir / "FULL_f24.nc"),
    ]:
        require_files([input_path], f"uv_to_psichi {label}")
        ncl_script = outdir / f"uv_to_psichi_{label}.ncl"
        write_text(ncl_script, render_uv_to_psichi_ncl(input_path, output_path, template, wgt1, wgt2))
        print(f"NCL {label} {pair.valid_time}")
        run_shell(
            f"module load ncl 2>/dev/null || true; ncl '{ncl_script}' < /dev/null",
            cwd=workspace,
            log_path=workspace / "logs" / f"03_convert_uv_to_psichi_{vcompact}_{label}.log",
        )
        require_files([output_path], f"uv_to_psichi {label} output")


def convert_uv_to_psichi(config, workspace: Path, pairs: list[BflowPair]) -> None:
    for pair in pairs:
        convert_pair(config, workspace, pair)
