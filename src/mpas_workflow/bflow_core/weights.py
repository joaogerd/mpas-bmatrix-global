from __future__ import annotations

from pathlib import Path

from ..shell import write_text
from .external import run_shell


def render_weights_ncl(mesh_name: str) -> str:
    return f'''load "$NCARG_ROOT/lib/ncarg/nclscripts/esmf/ESMF_regridding.ncl"

begin
    dstFileName = "MPAS_{mesh_name}.nc"
    interpMethod = "bilinear"

    srcGridName = "SCRIP_latlon_1p0.nc"
    dstGridName = "ESMF_MPAS_{mesh_name}.nc"
    wgtFile1    = "latlon_1p0_to_MPAS_{mesh_name}_" + interpMethod + ".nc"
    wgtFile2    = "MPAS_{mesh_name}_to_latlon_1p0_" + interpMethod + ".nc"

    Opt                = True
    Opt@ForceOverwrite = True
    Opt@PrintTimings   = True
    Opt@LLCorner       = (/ -89.50d0, -179.50d0/)
    Opt@URCorner       = (/  89.50d0,  179.50d0/)
    Opt@Title          = "Fixed lat/lon grid : 1.0 degree"
    latlon_to_SCRIP(srcGridName,"1.0deg",Opt)
    delete(Opt)

    dfile = addfile(dstFileName,"r")
    r2d = 180.0/(atan(1)*4.0)
    lonCell = dfile->lonCell
    latCell = dfile->latCell
    lonCell = lonCell*r2d
    latCell = latCell*r2d

    Opt                = True
    Opt@ForceOverwrite = True
    Opt@PrintTimings   = True
    Opt@InputFileName  = dstFileName
    print("Converting MPAS to Unstructured ESMF convention file ...")
    unstructured_to_ESMF(dstGridName,latCell,lonCell,Opt)
    delete(Opt)

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
end
'''


def generate_esmf_weights(config, workspace: Path) -> None:
    mesh_name = config["mesh"]["name"]
    invariant = Path(config["static"]["invariant"])
    weight_dir = Path(workspace) / "ESMF_weights"
    weight_dir.mkdir(parents=True, exist_ok=True)
    write_text(weight_dir / "generateEsmfWeights.ncl", render_weights_ncl(mesh_name))
    command = (
        "module load ncl netcdf 2>/dev/null || module load ncl 2>/dev/null || true; "
        f"ln -sf '{invariant}' './MPAS_{mesh_name}.nc'; "
        f"ncdump -h './MPAS_{mesh_name}.nc' | grep 'float latCell' | wc -l; "
        "ncl generateEsmfWeights.ncl < /dev/null"
    )
    run_shell(command, cwd=weight_dir, log_path=Path(workspace) / "logs" / "01_generate_esmf_weights.log")
