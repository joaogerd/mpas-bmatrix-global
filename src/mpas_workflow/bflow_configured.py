"""Configuration-driven BFLOW renderer.

The legacy :mod:`mpas_workflow.bflow` module owns CLI, workspaces and job
execution. This adapter replaces only the scientific/rendering decisions with
the ``bflow`` block from the B-matrix contract YAML.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from .bcov_configured import BMatrixContract, _error, load_contract_from_argv
from .forecast import bflow_file
from .shell import write_text


@dataclass(frozen=True)
class BFlowConfiguration:
    """Validated BFLOW section of a scientific B-matrix contract."""

    contract: BMatrixContract
    data: dict[str, Any]

    @classmethod
    def from_contract(cls, contract: BMatrixContract) -> "BFlowConfiguration":
        value = contract.data.get("bflow")
        if not isinstance(value, dict):
            _error("bloco obrigatório ausente ou inválido: bflow.")
        instance = cls(contract=contract, data=value)
        instance.validate()
        return instance

    @property
    def nmc(self) -> dict[str, Any]:
        return self.data["nmc"]

    @property
    def products(self) -> dict[str, str]:
        return self.data["products"]

    @property
    def regridding(self) -> dict[str, Any]:
        return self.data["regridding"]

    @property
    def wind_transform(self) -> dict[str, Any]:
        return self.data["wind_transform"]

    def file_for_control(self, control: str) -> str:
        return self.contract.file_for_code(control)

    def output_file(self, specification: dict[str, Any]) -> str:
        control = specification.get("output_control")
        if control is not None:
            return self.file_for_control(str(control))
        name = specification.get("output_file")
        if not isinstance(name, str) or not name:
            _error("cada produto BFLOW precisa de output_control ou output_file.")
        return name

    def weight_name(self, key: str, mesh_name: str) -> str:
        value = self.regridding[key]
        if not isinstance(value, str) or not value:
            _error(f"bflow.regridding.{key} deve ser uma string não vazia.")
        return value.format(mesh_name=mesh_name)

    def runtime_data(self) -> dict[str, Any]:
        """Return only physical names and values needed by generated scripts."""
        wind = self.wind_transform
        outputs: dict[str, dict[str, Any]] = {}
        for name in ("stream_function", "velocity_potential"):
            entry = dict(wind["outputs"][name])
            entry["output_file"] = self.output_file(entry)
            outputs[name] = entry

        derived: list[dict[str, Any]] = []
        for entry in self.data["derived_variables"]:
            item = dict(entry)
            item["output_file"] = self.output_file(item)
            derived.append(item)

        copied: list[dict[str, str]] = []
        for entry in self.data["copy_variables"]:
            if isinstance(entry, str):
                copied.append({"source": entry, "output": entry})
            else:
                copied.append({"source": entry["source"], "output": entry.get("output", entry["source"])})

        return {
            "nmc": dict(self.nmc),
            "products": dict(self.products),
            "wind_transform": {
                "zonal_file_variable": wind["zonal_file_variable"],
                "meridional_file_variable": wind["meridional_file_variable"],
                "template_file_variable": wind["template_file_variable"],
                "radius_numerator_m": wind["radius_numerator_m"],
                "radius_denominator_m": wind["radius_denominator_m"],
                "outputs": outputs,
            },
            "copy_variables": copied,
            "derived_variables": derived,
            "validation": self.data["validation"],
        }

    def validate(self) -> None:
        required_maps = ("nmc", "products", "regridding", "wind_transform", "validation")
        for key in required_maps:
            if not isinstance(self.data.get(key), dict):
                _error(f"bflow.{key} deve ser um mapa.")
        for key in ("copy_variables", "derived_variables"):
            if not isinstance(self.data.get(key), list):
                _error(f"bflow.{key} deve ser uma lista.")

        for key in ("older_lead_hours", "newer_lead_hours"):
            value = self.nmc.get(key)
            if not isinstance(value, int) or value <= 0:
                _error(f"bflow.nmc.{key} deve ser um inteiro positivo.")
        if self.nmc["older_lead_hours"] <= self.nmc["newer_lead_hours"]:
            _error("bflow.nmc.older_lead_hours deve ser maior que newer_lead_hours.")
        for key in ("older_label", "newer_label"):
            if not isinstance(self.nmc.get(key), str) or not self.nmc[key]:
                _error(f"bflow.nmc.{key} deve ser uma string não vazia.")

        for key in ("template", "older_full", "newer_full", "perturbation"):
            if not isinstance(self.products.get(key), str) or not self.products[key]:
                _error(f"bflow.products.{key} deve ser uma string não vazia.")

        regridding_keys = (
            "module_load",
            "mpas_grid_file",
            "scrip_grid_file",
            "esmf_grid_file",
            "scrip_resolution",
            "interpolation_method",
            "weight_latlon_to_mpas",
            "weight_mpas_to_latlon",
        )
        for key in regridding_keys:
            if not isinstance(self.regridding.get(key), str) or not self.regridding[key]:
                _error(f"bflow.regridding.{key} deve ser uma string não vazia.")
        for key in ("lower_left", "upper_right"):
            value = self.regridding.get(key)
            if not isinstance(value, list) or len(value) != 2:
                _error(f"bflow.regridding.{key} deve ser uma lista [latitude, longitude].")

        wind = self.wind_transform
        for key in (
            "zonal_file_variable",
            "meridional_file_variable",
            "template_file_variable",
        ):
            if not isinstance(wind.get(key), str) or not wind[key]:
                _error(f"bflow.wind_transform.{key} deve ser uma string não vazia.")
        for key in ("radius_numerator_m", "radius_denominator_m"):
            if not isinstance(wind.get(key), (int, float)) or wind[key] <= 0:
                _error(f"bflow.wind_transform.{key} deve ser numérico e positivo.")
        outputs = wind.get("outputs")
        if not isinstance(outputs, dict):
            _error("bflow.wind_transform.outputs deve ser um mapa.")
        for name in ("stream_function", "velocity_potential"):
            entry = outputs.get(name)
            if not isinstance(entry, dict):
                _error(f"bflow.wind_transform.outputs.{name} deve ser um mapa.")
            self.output_file(entry)
            for key in ("long_name", "units", "scale"):
                if key not in entry:
                    _error(f"bflow.wind_transform.outputs.{name}.{key} é obrigatório.")

        valid_operations = {
            "sum",
            "potential_temperature_to_temperature",
            "mixing_ratio_to_specific_humidity",
        }
        produced: set[str] = set()
        for index, entry in enumerate(self.data["derived_variables"]):
            if not isinstance(entry, dict):
                _error(f"bflow.derived_variables[{index}] deve ser um mapa.")
            output = self.output_file(entry)
            if output in produced:
                _error(f"bflow.derived_variables define saída duplicada: {output}.")
            produced.add(output)
            if entry.get("operation") not in valid_operations:
                _error(
                    f"bflow.derived_variables[{index}].operation deve ser uma de "
                    f"{sorted(valid_operations)}."
                )
            if not isinstance(entry.get("template_file"), str):
                _error(f"bflow.derived_variables[{index}].template_file é obrigatório.")
            if not isinstance(entry.get("attributes"), dict):
                _error(f"bflow.derived_variables[{index}].attributes deve ser um mapa.")

        validation = self.data["validation"]
        for key in ("full_required", "ptb_required", "dimension_checks"):
            if not isinstance(validation.get(key), list):
                _error(f"bflow.validation.{key} deve ser uma lista.")


def _json_literal(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _write_runtime_config(workspace: Path, configuration: BFlowConfiguration) -> None:
    payload = configuration.runtime_data()
    payload["contract_source"] = str(configuration.contract.source)
    write_text(workspace / "bflow_config.json", _json_literal(payload) + "\n")


def _write_weights_script(platform: dict[str, Any], workspace: Path, config: BFlowConfiguration) -> None:
    mesh_name = platform["mesh"]["name"]
    invariant = Path(platform["static"]["invariant"])
    regrid = config.regridding
    mpas_grid = config.weight_name("mpas_grid_file", mesh_name)
    scrip_grid = config.weight_name("scrip_grid_file", mesh_name)
    esmf_grid = config.weight_name("esmf_grid_file", mesh_name)
    weight_1 = config.weight_name("weight_latlon_to_mpas", mesh_name)
    weight_2 = config.weight_name("weight_mpas_to_latlon", mesh_name)
    lower_lat, lower_lon = regrid["lower_left"]
    upper_lat, upper_lon = regrid["upper_right"]
    script = f'''#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p ESMF_weights
cd ESMF_weights

{regrid["module_load"]}

ln -sf "{invariant}" "./{mpas_grid}"
isSinglePrecision=$(ncdump -h "./{mpas_grid}" | grep 'float {regrid.get("precision_probe_variable", "latCell")}' | wc -l)
echo "isSinglePrecision=$isSinglePrecision"

cat > generateEsmfWeights.ncl <<'EOF_NCL'
load "$NCARG_ROOT/lib/ncarg/nclscripts/esmf/ESMF_regridding.ncl"

begin
    dstFileName = "{mpas_grid}"
    interpMethod = "{regrid["interpolation_method"]}"

    srcGridName = "{scrip_grid}"
    dstGridName = "{esmf_grid}"
    wgtFile1    = "{weight_1}"
    wgtFile2    = "{weight_2}"

    SKIP_TRI_SCRIP_GEN  = False
    SKIP_MPAS_ESMF_GEN  = False
    SKIP_WGT_GEN_1      = False
    SKIP_WGT_GEN_2      = False

    if(.not.SKIP_TRI_SCRIP_GEN) then
      Opt                = True
      Opt@ForceOverwrite = True
      Opt@PrintTimings   = True
      Opt@LLCorner       = (/ {lower_lat}d0, {lower_lon}d0/)
      Opt@URCorner       = (/ {upper_lat}d0, {upper_lon}d0/)
      Opt@Title          = "{regrid.get("title", "Configured latitude-longitude grid")}" 
      latlon_to_SCRIP(srcGridName,"{regrid["scrip_resolution"]}",Opt)
      delete(Opt)
    end if

    dfile = addfile(dstFileName,"r")
    r2d = 180.0/(atan(1)*4.0)
    lonCell = dfile->lonCell*r2d
    latCell = dfile->latCell*r2d

    if(.not.SKIP_MPAS_ESMF_GEN) then
      Opt                = True
      Opt@ForceOverwrite = True
      Opt@PrintTimings   = True
      Opt@InputFileName  = dstFileName
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
      ESMF_regrid_gen_weights(dstGridName, srcGridName, wgtFile2, Opt)
      delete(Opt)
    end if
end
EOF_NCL

ncl generateEsmfWeights.ncl < /dev/null
'''
    path = workspace / "scripts" / "01_generate_esmf_weights.bash"
    write_text(path, script)
    path.chmod(0o755)


def _write_template_script(workspace: Path, first_ref: Path, config: BFlowConfiguration) -> None:
    wind = config.wind_transform
    template = wind["template_file_variable"]
    fields: list[str] = []
    grep_names: list[str] = []
    for item in wind["outputs"].values():
        output = config.output_file(item)
        grep_names.append(output)
        fields.extend(
            [
                'cp template_PTB.nc_single template_PTB.nc_work',
                f'ncrename -O -v {template},{output} template_PTB.nc_work',
                f"ncatted -O -a long_name,{output},o,c,'{item['long_name']}' template_PTB.nc_work",
                f"ncatted -O -a units,{output},o,c,'{item['units']}' template_PTB.nc_work",
                f'ncks -A -v {output} template_PTB.nc_work template_PTB.nc',
                '',
            ]
        )
    script = f'''#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
module load nco 2>/dev/null || true

REF="{first_ref}"
test -f "$REF" || {{ echo "ERRO: arquivo não encontrado: $REF" >&2; exit 1; }}

rm -f template_PTB.nc template_PTB.nc_single template_PTB.nc_work
ncks -O -v {template} "$REF" template_PTB.nc_single
ncap2 -O -s '{template}={template}*0.0' template_PTB.nc_single template_PTB.nc_single

{chr(10).join(fields)}
rm -f template_PTB.nc_single template_PTB.nc_work
ncdump -h template_PTB.nc | grep -E '{"|".join(grep_names)}'
'''
    path = workspace / "scripts" / "02_generate_template_ptb.bash"
    write_text(path, script)
    path.chmod(0o755)


def _write_psichi_script(platform: dict[str, Any], workspace: Path, config: BFlowConfiguration) -> None:
    mesh_name = platform["mesh"]["name"]
    products = config.products
    regrid = config.regridding
    wind = config.wind_transform
    sf = config.output_file(wind["outputs"]["stream_function"])
    vp = config.output_file(wind["outputs"]["velocity_potential"])
    sf_spec = wind["outputs"]["stream_function"]
    vp_spec = wind["outputs"]["velocity_potential"]
    weight_1 = config.weight_name("weight_mpas_to_latlon", mesh_name)
    weight_2 = config.weight_name("weight_latlon_to_mpas", mesh_name)
    script = f'''#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
{regrid.get("ncl_module_load", "module load ncl 2>/dev/null || true")}

MANIFEST=manifest.tsv
WGT1="ESMF_weights/{weight_1}"
WGT2="ESMF_weights/{weight_2}"
TEMPLATE="{products['template']}"

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

  u_cell = transpose(f_in->{wind['zonal_file_variable']}(0,:,:))
  v_cell = transpose(f_in->{wind['meridional_file_variable']}(0,:,:))

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
  u = new((/nZ,nY,nX/), float)
  v = new((/nZ,nY,nX/), float)
  sf = new((/nZ,nY,nX/), float)
  vp = new((/nZ,nY,nX/), float)
  u(:,:,:) = u_ll(:,:,:)
  v(:,:,:) = v_ll(:,:,:)
  delete(u_ll)
  delete(v_ll)

  uv2sfvpf(u, v, sf, vp)
  delete(u)
  delete(v)

  sf_cell4write = f_in->{wind['template_file_variable']}(:,:,:)
  vp_cell4write = f_in->{wind['template_file_variable']}(:,:,:)
  sf_cell = ESMF_regrid_with_weights(sf,FILE_WGT2,Opt)
  vp_cell = ESMF_regrid_with_weights(vp,FILE_WGT2,Opt)
  delete(sf)
  delete(vp)

  ratio={wind['radius_numerator_m']}/{wind['radius_denominator_m']}
  sf_cell_transpose = transpose(sf_cell(:,:) * ratio * {sf_spec['scale']})
  vp_cell_transpose = transpose(vp_cell(:,:) * ratio * {vp_spec['scale']})
  delete(sf_cell)
  delete(vp_cell)

  sf_cell4write(0,:,:)= (/ sf_cell_transpose(:,:) /)
  vp_cell4write(0,:,:)= (/ vp_cell_transpose(:,:) /)
  delete(sf_cell_transpose)
  delete(vp_cell_transpose)

  sf_cell4write@units = "{sf_spec['units']}"
  sf_cell4write@long_name = "{sf_spec['long_name']}"
  vp_cell4write@units = "{vp_spec['units']}"
  vp_cell4write@long_name = "{vp_spec['long_name']}"

  system("/bin/rm -f " + FILE_OUT)
  system("/bin/cp " + FILE_TEMPLATE + " " + FILE_OUT)
  system("/bin/chmod u+w " + FILE_OUT)
  f_out = addfile(FILE_OUT,"rw")
  f_out->{sf} = sf_cell4write
  f_out->{vp} = vp_cell4write
  delete(sf_cell4write)
  delete(vp_cell4write)
  delete(f_out)
end
EOF_NCL
}}

while IFS=$'\t' read -r valid f048 f024; do
  vcompact=$(python -c 'from datetime import datetime; import sys; print(datetime.strptime(sys.argv[1], "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H"))' "$valid")
  outdir="output/$vcompact"
  mkdir -p "$outdir"
  in_old="inputs/$vcompact/f048.nc"
  in_new="inputs/$vcompact/f024.nc"
  test -f "$in_old" || {{ echo "ERRO: input ausente: $in_old" >&2; exit 1; }}
  test -f "$in_new" || {{ echo "ERRO: input ausente: $in_new" >&2; exit 1; }}

  rm -f "$outdir/{products['older_full']}" "$outdir/{products['newer_full']}" "$outdir/uv_to_psichi_{config.nmc['older_label']}.ncl" "$outdir/uv_to_psichi_{config.nmc['newer_label']}.ncl"
  make_ncl "$in_old" "$outdir/{products['older_full']}" "$outdir/uv_to_psichi_{config.nmc['older_label']}.ncl"
  make_ncl "$in_new" "$outdir/{products['newer_full']}" "$outdir/uv_to_psichi_{config.nmc['newer_label']}.ncl"

  echo "NCL {config.nmc['older_label']} $valid"
  ncl "$outdir/uv_to_psichi_{config.nmc['older_label']}.ncl" < /dev/null
  test -f "$outdir/{products['older_full']}" || {{ echo "ERRO: NCL não gerou $outdir/{products['older_full']}" >&2; exit 1; }}

  echo "NCL {config.nmc['newer_label']} $valid"
  ncl "$outdir/uv_to_psichi_{config.nmc['newer_label']}.ncl" < /dev/null
  test -f "$outdir/{products['newer_full']}" || {{ echo "ERRO: NCL não gerou $outdir/{products['newer_full']}" >&2; exit 1; }}
done < <(tail -n +2 "$MANIFEST")
'''
    path = workspace / "scripts" / "03_convert_uv_to_psichi.bash"
    write_text(path, script)
    path.chmod(0o755)


def _write_add_variables_script(workspace: Path) -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import netCDF4

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "bflow_config.json").read_text())
MANIFEST = ROOT / "manifest.tsv"


def compact(valid_time: str) -> str:
    return datetime.strptime(valid_time, "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H")


def ensure_dims(src, dst, variable):
    for dim_name in variable.dimensions:
        if dim_name not in dst.dimensions:
            dimension = src.dimensions[dim_name]
            dst.createDimension(dim_name, None if dimension.isunlimited() else len(dimension))


def copy_attrs(src_var, dst_var):
    for attr in src_var.ncattrs():
        if attr == "_FillValue":
            continue
        try:
            dst_var.setncattr(attr, src_var.getncattr(attr))
        except Exception:
            pass


def upsert_var(dst, template, name, values):
    if name in dst.variables:
        variable = dst.variables[name]
    else:
        fill_value = getattr(template, "_FillValue", None)
        kwargs = {"fill_value": fill_value} if fill_value is not None else {}
        variable = dst.createVariable(name, template.dtype, template.dimensions, **kwargs)
        copy_attrs(template, variable)
    variable[:] = values.astype(template.dtype, copy=False)
    return variable


def derive(entry, values):
    operation = entry["operation"]
    if operation == "sum":
        names = entry["inputs"]
        return sum(values[name] for name in names)
    if operation == "potential_temperature_to_temperature":
        theta = values[entry["theta_file"]]
        pressure = values[entry["pressure_file"]]
        return theta * ((pressure / entry["reference_pressure_pa"]) ** entry["exponent"])
    if operation == "mixing_ratio_to_specific_humidity":
        mixing_ratio = values[entry["mixing_ratio_file"]]
        return mixing_ratio / (1.0 + mixing_ratio)
    raise SystemExit(f"ERRO: operação BFLOW desconhecida: {operation}")


def add_variables(input_path: Path, full_path: Path):
    if not full_path.exists():
        raise SystemExit(f"ERRO: FULL file não existe; rode primeiro uv_to_psichi: {full_path}")
    with netCDF4.Dataset(input_path) as src, netCDF4.Dataset(full_path, "a") as dst:
        values = {}
        for entry in CONFIG["copy_variables"]:
            source_name = entry["source"]
            output_name = entry["output"]
            if source_name not in src.variables:
                print(f"AVISO: variável ausente em {input_path}: {source_name}")
                continue
            source = src.variables[source_name]
            ensure_dims(src, dst, source)
            output = upsert_var(dst, source, output_name, source[:])
            values[output_name] = output[:]
            values[source_name] = source[:]

        for entry in CONFIG["derived_variables"]:
            template_name = entry["template_file"]
            if template_name not in src.variables:
                raise SystemExit(f"ERRO: template BFLOW ausente: {template_name} em {input_path}")
            required = []
            if entry["operation"] == "sum":
                required = entry["inputs"]
            elif entry["operation"] == "potential_temperature_to_temperature":
                required = [entry["theta_file"], entry["pressure_file"]]
            elif entry["operation"] == "mixing_ratio_to_specific_humidity":
                required = [entry["mixing_ratio_file"]]
            for name in required:
                if name not in values:
                    if name not in src.variables:
                        raise SystemExit(f"ERRO: entrada BFLOW ausente: {name} em {input_path}")
                    values[name] = src.variables[name][:]
            template = src.variables[template_name]
            ensure_dims(src, dst, template)
            output_name = entry["output_file"]
            output = upsert_var(dst, template, output_name, derive(entry, values))
            for key, value in entry.get("attributes", {}).items():
                output.setncattr(key, value)
            values[output_name] = output[:]


def main():
    products = CONFIG["products"]
    with MANIFEST.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            output_dir = ROOT / "output" / compact(row["valid_time"])
            print(f"add variables {row['valid_time']} {CONFIG['nmc']['older_label']}")
            add_variables(Path(row["f048"]), output_dir / products["older_full"])
            print(f"add variables {row['valid_time']} {CONFIG['nmc']['newer_label']}")
            add_variables(Path(row["f024"]), output_dir / products["newer_full"])


if __name__ == "__main__":
    main()
'''
    path = workspace / "scripts" / "04_add_variables.py"
    write_text(path, script)
    path.chmod(0o755)


def _write_ncdiff_script(workspace: Path) -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "bflow_config.json").read_text())
MANIFEST = ROOT / "manifest.tsv"


def compact(valid_time: str) -> str:
    return datetime.strptime(valid_time, "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H")


def copy_attrs(src, dst):
    for attr in src.ncattrs():
        try:
            dst.setncattr(attr, src.getncattr(attr))
        except Exception:
            pass


def diff_file(older: Path, newer: Path, output: Path, valid_time: str):
    if output.exists():
        output.unlink()
    with netCDF4.Dataset(older) as old_ds, netCDF4.Dataset(newer) as new_ds, netCDF4.Dataset(output, "w") as dst:
        for name, dimension in old_ds.dimensions.items():
            dst.createDimension(name, None if dimension.isunlimited() else len(dimension))
        copy_attrs(old_ds, dst)
        operation = f"{CONFIG['nmc']['older_label']}_minus_{CONFIG['nmc']['newer_label']}"
        dst.setncattr("nmc_difference", operation)
        dst.setncattr("valid_time", valid_time)
        dst.setncattr("source_older", str(older))
        dst.setncattr("source_newer", str(newer))
        for name in [item for item in old_ds.variables if item in new_ds.variables]:
            old_var = old_ds.variables[name]
            new_var = new_ds.variables[name]
            if old_var.dimensions != new_var.dimensions or not np.issubdtype(old_var.dtype, np.number):
                continue
            fill_value = getattr(old_var, "_FillValue", None)
            kwargs = {"fill_value": fill_value} if fill_value is not None else {}
            out_var = dst.createVariable(name, old_var.dtype, old_var.dimensions, **kwargs)
            copy_attrs(old_var, out_var)
            out_var.setncattr("nmc_operation", operation)
            out_var[:] = old_var[:] - new_var[:]


def main():
    products = CONFIG["products"]
    with MANIFEST.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            output_dir = ROOT / "output" / compact(row["valid_time"])
            older = output_dir / products["older_full"]
            newer = output_dir / products["newer_full"]
            output = output_dir / products["perturbation"]
            print(f"ncdiff {row['valid_time']}: {output}")
            diff_file(older, newer, output, row["valid_time"])


if __name__ == "__main__":
    main()
'''
    path = workspace / "scripts" / "05_ncdiff.py"
    write_text(path, script)
    path.chmod(0o755)


def _write_validate_script(workspace: Path) -> None:
    script = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import netCDF4

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "bflow_config.json").read_text())
MANIFEST = ROOT / "manifest.tsv"


def compact(valid_time: str) -> str:
    return datetime.strptime(valid_time, "%Y-%m-%d_%H:%M:%S").strftime("%Y%m%d%H")


def require_vars(path: Path, names: list[str]):
    if not path.exists():
        raise SystemExit(f"ERRO: produto ausente: {path}")
    with netCDF4.Dataset(path) as ds:
        for name in names:
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente em {path}: {name}")
        for check in CONFIG["validation"]["dimension_checks"]:
            name = check["file"]
            if name not in ds.variables:
                continue
            dimensions = tuple(check["dimensions"])
            if tuple(ds.variables[name].dimensions) != dimensions:
                raise SystemExit(
                    f"ERRO: dimensões inválidas para {name} em {path}: "
                    f"{ds.variables[name].dimensions}; esperado {dimensions}"
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["full", "ptb"], required=True)
    args = parser.parse_args()
    required = CONFIG["validation"]["full_required" if args.stage == "full" else "ptb_required"]
    products = CONFIG["products"]
    with MANIFEST.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            output_dir = ROOT / "output" / compact(row["valid_time"])
            if args.stage == "full":
                require_vars(output_dir / products["older_full"], required)
                require_vars(output_dir / products["newer_full"], required)
            else:
                require_vars(output_dir / products["perturbation"], required)
            print(f"OK {args.stage}: {row['valid_time']}")


if __name__ == "__main__":
    main()
'''
    path = workspace / "scripts" / "06_validate_products.py"
    write_text(path, script)
    path.chmod(0o755)


def _write_master_script(workspace: Path, config: BFlowConfiguration) -> None:
    products = config.products
    script = f'''#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
if [[ "${{CLEAN_OUTPUT:-0}}" == "1" ]]; then
  echo "Cleaning output directory"
  rm -rf output
  mkdir -p output
fi
mkdir -p output logs

if [[ "${{SKIP_WEIGHTS:-0}}" != "1" ]]; then
  bash scripts/01_generate_esmf_weights.bash
else
  echo "Skipping ESMF weights because SKIP_WEIGHTS=1"
fi

bash scripts/02_generate_template_ptb.bash
bash scripts/03_convert_uv_to_psichi.bash
python scripts/06_validate_products.py --stage full
python scripts/04_add_variables.py
python scripts/05_ncdiff.py
python scripts/06_validate_products.py --stage ptb
find output -name '{products['perturbation']}' -printf '%p\n' | sort
'''
    path = workspace / "scripts" / "run_all_bflow.sh"
    write_text(path, script)
    path.chmod(0o755)


def _build_pairs_from_range(legacy, configuration: BFlowConfiguration):
    def build_pairs(platform, start_valid_time: str, end_valid_time: str, step_hours: int, dt: int):
        pairs = []
        older_hours = configuration.nmc["older_lead_hours"]
        newer_hours = configuration.nmc["newer_lead_hours"]
        for valid_time in legacy.iter_valid_times(start_valid_time, end_valid_time, step_hours):
            valid = legacy.parse_time(valid_time)
            pairs.append(
                legacy.BflowPair(
                    valid_time=valid_time,
                    f048=bflow_file(
                        platform,
                        legacy.format_time(valid - timedelta(hours=older_hours)),
                        older_hours,
                        dt,
                    ),
                    f024=bflow_file(
                        platform,
                        legacy.format_time(valid - timedelta(hours=newer_hours)),
                        newer_hours,
                        dt,
                    ),
                )
            )
        return pairs

    return build_pairs


def apply_bflow_configuration(legacy, platform: dict[str, Any], configuration: BFlowConfiguration) -> None:
    """Replace BFLOW physical/scientific renderers while retaining the CLI."""
    original_write_readme = legacy.write_readme

    def write_weights_script(platform_config, workspace):
        _write_runtime_config(workspace, configuration)
        _write_weights_script(platform_config, workspace, configuration)

    def write_template_script(workspace, first_ref):
        _write_template_script(workspace, first_ref, configuration)

    def write_psichi_script(platform_config, workspace):
        _write_psichi_script(platform_config, workspace, configuration)

    def write_add_variables_script(workspace):
        _write_add_variables_script(workspace)

    def write_ncdiff_script(workspace):
        _write_ncdiff_script(workspace)

    def write_validate_script(workspace):
        _write_validate_script(workspace)

    def write_master_script(workspace):
        _write_master_script(workspace, configuration)

    def write_readme(workspace, pairs):
        original_write_readme(workspace, pairs)
        readme = workspace / "README.md"
        readme.write_text(
            readme.read_text()
            + "\n## Scientific BFLOW configuration\n\n"
            + f"- Contract: `{configuration.contract.source}`\n"
            + "- Snapshot: `bflow_config.json`\n"
            + f"- NMC pair: `{configuration.nmc['older_label']}` minus `{configuration.nmc['newer_label']}`\n"
        )

    legacy.build_pairs_from_range = _build_pairs_from_range(legacy, configuration)
    legacy.write_weights_script = write_weights_script
    legacy.write_template_script = write_template_script
    legacy.write_psichi_script = write_psichi_script
    legacy.write_add_variables_script = write_add_variables_script
    legacy.write_ncdiff_script = write_ncdiff_script
    legacy.write_validate_script = write_validate_script
    legacy.write_master_script = write_master_script
    legacy.write_readme = write_readme


def main() -> int:
    from . import bflow

    platform, contract = load_contract_from_argv()
    apply_bflow_configuration(bflow, platform, BFlowConfiguration.from_contract(contract))
    return bflow.main()
