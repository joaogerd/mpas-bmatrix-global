"""Configuration-driven compatibility layer for MPAS-JEDI B-matrix workflows.

This module keeps the existing execution/submission code in ``bcov`` while
replacing its scientific hard-coding with one external B-matrix contract YAML.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable

from .config import load_config
from .shell import write_text


DEFAULT_PLATFORM_CONFIG = "configs/jaci-x1.10242.yaml"


class BMatrixConfigurationError(SystemExit):
    """Raised when the B-matrix scientific configuration is incomplete."""


def _error(message: str) -> None:
    raise BMatrixConfigurationError(f"ERRO de configuração da matriz B: {message}")


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return _yaml_bool(value)
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(char in text for char in ":#{}[],&*!|>'\"%@`") or text.strip() != text:
        return repr(text)
    return text


def _yaml_list(values: Iterable[Any], indent: int) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}- {_yaml_scalar(value)}" for value in values)


def _yaml_mapping(values: dict[str, Any], indent: int) -> str:
    prefix = " " * indent
    lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_yaml_mapping(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            lines.append(_yaml_list(value, indent + 2))
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return "\n".join(lines)


class BMatrixContract:
    """Validated scientific contract shared by BFLOW, SABER and diagnostics."""

    def __init__(self, data: dict[str, Any], source: Path):
        self.data = data
        self.source = source
        self._validate()

    @property
    def controls(self) -> list[dict[str, Any]]:
        return self.data["controls"]

    @property
    def code_variables(self) -> list[str]:
        return [item["code"] for item in self.controls]

    @property
    def file_variables(self) -> list[str]:
        return [item["file"] for item in self.controls]

    @property
    def file_to_code(self) -> dict[str, str]:
        return {item["file"]: item["code"] for item in self.controls}

    @property
    def code_to_file(self) -> dict[str, str]:
        return {item["code"]: item["file"] for item in self.controls}

    @property
    def aliases(self) -> list[dict[str, str]]:
        return [{"in code": item["code"], "in file": item["file"]} for item in self.controls]

    @property
    def variables_by_code(self) -> dict[str, dict[str, Any]]:
        return {item["code"]: item for item in self.controls}

    def code_for_file(self, file_name: str) -> str:
        try:
            return self.file_to_code[file_name]
        except KeyError as exc:
            _error(f"não existe variável de controle com file={file_name!r}.")
            raise AssertionError from exc

    def file_for_code(self, code_name: str) -> str:
        try:
            return self.code_to_file[code_name]
        except KeyError as exc:
            _error(f"não existe variável de controle com code={code_name!r}.")
            raise AssertionError from exc

    def config(self, name: str) -> dict[str, Any]:
        value = self.data.get(name)
        if not isinstance(value, dict):
            _error(f"bloco obrigatório ausente ou inválido: {name}.")
        return value

    def alias_yaml(self, indent: int) -> str:
        prefix = " " * indent
        lines: list[str] = []
        for item in self.aliases:
            lines.append(f"{prefix}- in code: {item['in code']}")
            lines.append(f"{prefix}  in file: {item['in file']}")
        return "\n".join(lines)

    def pair_aliases(self) -> list[dict[str, str]]:
        """Return aliases for all lower-triangular NetCDF-4 VBAL group names."""
        group_order = self.config("vbal").get("group_variable_order", self.code_variables)
        if set(group_order) != set(self.code_variables) or len(group_order) != len(self.code_variables):
            _error(
                "vbal.group_variable_order deve conter exatamente uma ocorrência "
                "de cada controls[].code."
            )
        output: list[dict[str, str]] = []
        for right_index, right_code in enumerate(group_order):
            for left_code in group_order[: right_index + 1]:
                output.append(
                    {
                        "in code": f"{left_code}-{right_code}",
                        "in file": f"{self.file_for_code(left_code)}-{self.file_for_code(right_code)}",
                    }
                )
        return output

    def _validate(self) -> None:
        if self.data.get("schema_version") != 1:
            _error("schema_version deve ser 1.")
        controls = self.data.get("controls")
        if not isinstance(controls, list) or not controls:
            _error("controls deve ser uma lista não vazia.")
        for index, item in enumerate(controls):
            if not isinstance(item, dict):
                _error(f"controls[{index}] deve ser um mapa.")
            for key in ("code", "file", "dimensions"):
                if not isinstance(item.get(key), str) or not item[key]:
                    _error(f"controls[{index}].{key} deve ser uma string não vazia.")
            if item["dimensions"] not in {"3d", "2d"}:
                _error(f"controls[{index}].dimensions deve ser 3d ou 2d.")
        for key, values in (
            ("controls[].code", self.code_variables),
            ("controls[].file", self.file_variables),
        ):
            if len(values) != len(set(values)):
                _error(f"{key} contém nomes duplicados.")
        if sum(item["dimensions"] == "2d" for item in controls) != 1:
            _error("o workflow atual requer exatamente uma variável 2d em controls.")
        for required in ("vbal", "hdiag", "nicas", "dirac", "single_observation"):
            self.config(required)
        vbal = self.config("vbal")
        relations = vbal.get("relations")
        if not isinstance(relations, list) or not relations:
            _error("vbal.relations deve ser uma lista não vazia.")
        for index, relation in enumerate(relations):
            if not isinstance(relation, dict):
                _error(f"vbal.relations[{index}] deve ser um mapa.")
            for key in ("balanced_variable", "unbalanced_variable"):
                if relation.get(key) not in self.code_variables:
                    _error(
                        f"vbal.relations[{index}].{key} deve referenciar controls[].code."
                    )
        nicas = self.config("nicas")
        if not isinstance(nicas.get("dirac_points"), list) or not nicas["dirac_points"]:
            _error("nicas.dirac_points deve conter pelo menos um ponto.")
        for point in nicas["dirac_points"]:
            if not isinstance(point, dict) or point.get("variable") not in self.code_variables:
                _error("cada nicas.dirac_points[] deve informar uma variável de controle canônica.")
        dirac = self.config("dirac")
        if dirac.get("variable") not in self.code_variables:
            _error("dirac.variable deve referenciar controls[].code.")
        if not isinstance(dirac.get("latitudes"), list) or not isinstance(dirac.get("longitudes"), list):
            _error("dirac.latitudes e dirac.longitudes devem ser listas.")
        if len(dirac["latitudes"]) != len(dirac["longitudes"]) or not dirac["latitudes"]:
            _error("dirac.latitudes e dirac.longitudes devem ter o mesmo tamanho não nulo.")
        so = self.config("single_observation")
        if not isinstance(so.get("analysis_variables"), list) or not so["analysis_variables"]:
            _error("single_observation.analysis_variables deve ser uma lista não vazia.")
        if not isinstance(so.get("background_variables"), list) or not so["background_variables"]:
            _error("single_observation.background_variables deve ser uma lista não vazia.")
        if not isinstance(so.get("observations"), dict) or not so["observations"]:
            _error("single_observation.observations deve ser um mapa não vazio.")
        if not isinstance(so.get("variants"), dict) or not so["variants"]:
            _error("single_observation.variants deve ser um mapa não vazio.")
        for variant, observations in so["variants"].items():
            if not isinstance(observations, list) or not observations:
                _error(f"single_observation.variants.{variant} deve ser uma lista não vazia.")
            unknown = set(observations) - set(so["observations"])
            if unknown:
                _error(
                    f"single_observation.variants.{variant} referencia observações inexistentes: "
                    f"{sorted(unknown)}."
                )


def _platform_config_path(argv: list[str]) -> Path:
    environment_path = os.environ.get("MPAS_BMATRIX_PLATFORM_CONFIG")
    path = Path(environment_path) if environment_path else Path(DEFAULT_PLATFORM_CONFIG)
    for index, token in enumerate(argv):
        if token == "--config":
            if index + 1 >= len(argv):
                _error("--config foi informado sem caminho.")
            path = Path(argv[index + 1])
        elif token.startswith("--config="):
            path = Path(token.split("=", 1)[1])
    return path


def load_contract_from_argv(argv: list[str] | None = None) -> tuple[dict[str, Any], BMatrixContract]:
    argv = list(sys.argv[1:] if argv is None else argv)
    platform_path = _platform_config_path(argv)
    platform = load_config(platform_path)
    section = platform.get("bmatrix")
    if not isinstance(section, dict):
        _error(f"{platform_path} deve conter o bloco bmatrix.")
    contract_path = section.get("configuration")
    if not isinstance(contract_path, str) or not contract_path:
        _error(f"{platform_path}: bmatrix.configuration deve apontar para um YAML científico.")
    source = Path(contract_path)
    if not source.is_absolute():
        source = platform_path.parent / source
    return platform, BMatrixContract(load_config(source), source)


def _relations_yaml(contract: BMatrixContract, indent: int) -> str:
    prefix = " " * indent
    lines: list[str] = []
    for relation in contract.config("vbal")["relations"]:
        lines.append(f"{prefix}- balanced variable: {relation['balanced_variable']}")
        lines.append(f"{prefix}  unbalanced variable: {relation['unbalanced_variable']}")
        if "diagonal_regression" in relation:
            lines.append(
                f"{prefix}  diagonal regression: "
                f"{_yaml_bool(bool(relation['diagonal_regression']))}"
            )
    return "\n".join(lines)


def _geometry_yaml(
    contract: BMatrixContract,
    indent: int,
    *,
    deallocate: bool = False,
    bump_vunit: str | None = None,
    include_alias: bool = True,
) -> str:
    prefix = " " * indent
    lines = [
        f"{prefix}nml_file: \"./namelist.atmosphere_240km\"",
        f"{prefix}streams_file: \"./streams.atmosphere_240km\"",
    ]
    if deallocate:
        lines.append(f"{prefix}deallocate non-da fields: true")
    if bump_vunit:
        lines.append(f"{prefix}bump vunit: {_yaml_scalar(bump_vunit)}")
    if include_alias:
        lines.append(f"{prefix}alias:")
        lines.append(contract.alias_yaml(indent + 2))
    return "\n".join(lines)


def _relations_read_yaml(contract: BMatrixContract, indent: int) -> str:
    return _relations_yaml(contract, indent)


def _write_vbal_yaml(contract: BMatrixContract, path: Path, nmembers: int, date: str) -> None:
    vbal = contract.config("vbal")
    sampling = vbal["sampling"]
    variables_yaml = _yaml_list(contract.code_variables, 2)
    text = f"""_member config: &memberConfig
  state variables: &vars
{variables_yaml}
  date: &date '{date}'
  stream name: control
  transform model to analysis: false
geometry:
{_geometry_yaml(contract, 2)}
background:
  state variables: *vars
  filename: \"./bg.nc\"
  date: *date
  stream name: control
  transform model to analysis: false

background error:
  covariance model: SABER
  iterative ensemble loading: false

  ensemble:
    members from template:
      template:
        <<: *memberConfig
        filename: ../samples/PTB_f48mf24_%mem%.nc
      pattern: '%mem%'
      nmembers: {nmembers}
      zero padding: 3

  saber central block:
    saber block name: ID

  saber outer blocks:
  - saber block name: BUMP_VerticalBalance
    calibration:
      io:
        files prefix: {vbal['files_prefix']}
      drivers:
        write local sampling: {_yaml_bool(vbal['drivers']['write_local_sampling'])}
        write global sampling: {_yaml_bool(vbal['drivers']['write_global_sampling'])}
        compute vertical covariance: {_yaml_bool(vbal['drivers']['compute_vertical_covariance'])}
        compute vertical balance: {_yaml_bool(vbal['drivers']['compute_vertical_balance'])}
        write vertical balance: {_yaml_bool(vbal['drivers']['write_vertical_balance'])}
      sampling:
{_yaml_mapping(sampling, 8)}
      vertical balance:
        vbal:
{_relations_yaml(contract, 10)}
        pseudo inverse: {_yaml_bool(vbal['pseudo_inverse'])}
        dominant mode: {vbal['dominant_mode']}
"""
    write_text(path, text)


def _write_hdiag_yaml(contract: BMatrixContract, path: Path, nmembers: int, date: str) -> None:
    hdiag = contract.config("hdiag")
    variables_yaml = _yaml_list(contract.code_variables, 2)
    initial_scales = hdiag["variance"]["initial_length_scales"]
    initial_scale_lines: list[str] = []
    for entry in initial_scales:
        initial_scale_lines.append("        - variables:")
        initial_scale_lines.append(_yaml_list(entry["variables"], 10))
        initial_scale_lines.append(f"          value: {entry['value']}")
    text = f"""_member config: &memberConfig
  state variables: &vars
{variables_yaml}
  date: &date '{date}'
  stream name: control
  transform model to analysis: false
geometry:
{_geometry_yaml(contract, 2, bump_vunit=hdiag['bump_vunit'])}
background:
  state variables: *vars
  filename: \"./bg.nc\"
  date: *date
  stream name: control
  transform model to analysis: false

background error:
  covariance model: SABER
  iterative ensemble loading: {_yaml_bool(hdiag['iterative_ensemble_loading'])}

  ensemble:
    members from template:
      template:
        <<: *memberConfig
        filename: ../samples/PTB_f48mf24_%mem%.nc
      pattern: '%mem%'
      nmembers: {nmembers}
      zero padding: 3

  saber central block:
    saber block name: BUMP_NICAS
    calibration:
      io:
        files prefix: {hdiag['files_prefix']}
      drivers:
{_yaml_mapping(hdiag['drivers'], 8)}
      sampling:
{_yaml_mapping(hdiag['sampling'], 8)}
      variance:
        objective filtering: {_yaml_bool(hdiag['variance']['objective_filtering'])}
        filtering iterations: {hdiag['variance']['filtering_iterations']}
        initial length-scale:
{chr(10).join(initial_scale_lines)}
      fit:
{_yaml_mapping(hdiag['fit'], 8)}
      output model files:
      - parameter: stddev
        file:
          filename: ./mpas.stddev.nc
          date: *date
          stream name: control
      - parameter: cor_rh
        file:
          filename: ./mpas.cor_rh.nc
          date: *date
          stream name: control
      - parameter: cor_rv
        file:
          filename: ./mpas.cor_rv.nc
          date: *date
          stream name: control

  saber outer blocks:
  - saber block name: BUMP_VerticalBalance
    read:
      io:
        data directory: ../vbal
        files prefix: {contract.config('vbal')['files_prefix']}
      drivers:
        read local sampling: true
        read vertical balance: true
      vertical balance:
        vbal:
{_relations_read_yaml(contract, 10)}
"""
    write_text(path, text)


def _nicas_dirac_yaml(contract: BMatrixContract, variable: str, nvertlevels: int, indent: int) -> str:
    nicas = contract.config("nicas")
    prefix = " " * indent
    lines: list[str] = []
    variable_info = contract.variables_by_code[variable]
    default_level = (
        1
        if variable_info["dimensions"] == "2d"
        else nvertlevels - nicas["dirac_level_from_top"] + 1
    )
    matching = [point for point in nicas["dirac_points"] if point["variable"] == variable]
    for point in matching or nicas["dirac_points"]:
        level = point.get("level", default_level)
        lines.extend(
            [
                f"{prefix}- longitude: {point['longitude']}",
                f"{prefix}  latitude: {point['latitude']}",
                f"{prefix}  level: {level}",
                f"{prefix}  variable: {variable}",
            ]
        )
    return "\n".join(lines)


def _write_nicas_yaml(
    contract: BMatrixContract,
    path: Path,
    variable_file: str,
    date: str,
    nvertlevels: int,
) -> None:
    nicas = contract.config("nicas")
    variable = contract.code_for_file(variable_file)
    text = f"""geometry:
{_geometry_yaml(contract, 2, deallocate=True, bump_vunit=nicas['bump_vunit'])}
background:
  state variables:
  - {variable}
  filename: \"./bg.nc\"
  date: &date '{date}'
  stream name: control
  transform model to analysis: false

background error:
  covariance model: SABER

  saber central block:
    saber block name: BUMP_NICAS
    calibration:
      io:
        files prefix: {nicas['files_prefix']}
      drivers:
{_yaml_mapping(nicas['drivers'], 8)}
      nicas:
{_yaml_mapping(nicas['nicas'], 8)}
      dirac:
{_nicas_dirac_yaml(contract, variable, nvertlevels, 8)}
      input model files:
      - parameter: rh
        file:
          filename: ../mpas.cor_rh.nc
          date: *date
          stream name: control
      - parameter: rv
        file:
          filename: ../mpas.cor_rv.nc
          date: *date
          stream name: control
      output model files:
      - parameter: nicas_norm
        file:
          filename: ./mpas.nicas_norm.nc
          date: *date
          stream name: control
      - parameter: dirac_nicas
        file:
          filename: ./mpas.dirac_nicas.nc
          date: *date
          stream name: control
"""
    write_text(path, text)


def _grids_yaml(contract: BMatrixContract, indent: int) -> str:
    prefix = " " * indent
    three_d = [item["code"] for item in contract.controls if item["dimensions"] == "3d"]
    two_d = [item["code"] for item in contract.controls if item["dimensions"] == "2d"]
    lines = [f"{prefix}- model:", f"{prefix}    variables:"]
    lines.extend(f"{prefix}    - {name}" for name in three_d)
    lines.extend([f"{prefix}- model:", f"{prefix}    variables:"])
    lines.extend(f"{prefix}    - {name}" for name in two_d)
    return "\n".join(lines)


def _so_observer_yaml(contract: BMatrixContract, key: str, epoch: str, indent: int) -> str:
    observation = contract.config("single_observation")["observations"][key]
    prefix = " " * indent
    return f"""{prefix}- obs space:
{prefix}    name: {observation['name']}
{prefix}    simulated variables: [{observation['simulated_variable']}]
{prefix}    obsdatain:
{prefix}      engine:
{prefix}        type: GenList
{prefix}        lats: [{observation['latitude']}]
{prefix}        lons: [{observation['longitude']}]
{prefix}        vert coord type: pressure
{prefix}        vert coords: [{observation['pressure']}]
{prefix}        dateTimes: [0]
{prefix}        epoch: \"seconds since {epoch}\"
{prefix}        obs errors: [{observation['error']}]
{prefix}        obs values: [{observation['value']}]
{prefix}    obsdataout:
{prefix}      engine:
{prefix}        type: H5File
{prefix}        obsfile: ./{observation['output_file']}
{prefix}  obs operator:
{prefix}    name: VertInterp
{prefix}    vertical coordinate: air_pressure
{prefix}    interpolation method: log-linear"""


def _write_so_yaml(
    contract: BMatrixContract,
    path: Path,
    date: str,
    nicas_dir: Path,
    stddev_file: Path,
    vbal_dir: Path,
    variant: str = "default",
) -> None:
    so = contract.config("single_observation")
    if variant not in so["variants"]:
        _error(f"single_observation.variants não define a variante {variant!r}.")
    from datetime import datetime, timedelta

    analysis_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    window_begin = (analysis_date - timedelta(hours=so["window_hours_before_analysis"])).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    observer_blocks = "\n".join(
        _so_observer_yaml(contract, key, date, 4) for key in so["variants"][variant]
    )
    text = f"""output:
  filename: ./an.$Y-$M-$D_$h.$m.$s.nc
  stream name: analysis

variational:
  minimizer:
    algorithm: {so['minimizer']}
  iterations:
  - geometry:
{_geometry_yaml(contract, 6, include_alias=False)}
    gradient norm reduction: {so['gradient_norm_reduction']}
    diagnostics:
      departures: ombg
    ninner: {so['ninner']}

final:
  diagnostics:
    departures: oman

cost function:
  cost type: 3D-Var
  time window:
    begin: '{window_begin}'
    length: PT{so['window_hours']}H
  jb evaluation: false
  geometry:
{_geometry_yaml(contract, 4, deallocate=True, include_alias=False)}
  analysis variables: &incvars
{_yaml_list(so['analysis_variables'], 2)}
  background:
    state variables:
{_yaml_list(so['background_variables'], 4)}
    filename: ./bg_so.nc
    date: &analysisDate '{date}'
    transform model to analysis: false
  background error:
    covariance model: SABER
    saber central block:
      saber block name: BUMP_NICAS
      active variables: &ctlvars
{_yaml_list(contract.code_variables, 6)}
      read:
        io:
          data directory: {nicas_dir}
          files prefix: {contract.config('nicas')['files_prefix']}
        drivers:
          multivariate strategy: univariate
          read local nicas: true
        grids:
{_grids_yaml(contract, 8)}
    saber outer blocks:
    - saber block name: StdDev
      read:
        model file:
          filename: {stddev_file}
          date: *analysisDate
          stream name: control
    - saber block name: BUMP_VerticalBalance
      read:
        io:
          data directory: {vbal_dir}
          files prefix: {contract.config('vbal')['files_prefix']}
        drivers:
          read local sampling: true
          read vertical balance: true
      vertical balance:
        vbal:
{_relations_read_yaml(contract, 10)}
    linear variable change:
      linear variable change name: Control2Analysis
      input variables: *ctlvars
      output variables: *incvars

  observations:
    observers:
{observer_blocks}
"""
    write_text(path, text)


def _write_dirac_yaml(
    contract: BMatrixContract,
    path: Path,
    date: str,
    nicas_dir: Path,
    stddev_file: Path,
    vbal_dir: Path,
) -> None:
    dirac = contract.config("dirac")
    so = contract.config("single_observation")
    latitudes = ", ".join(str(value) for value in dirac["latitudes"])
    longitudes = ", ".join(str(value) for value in dirac["longitudes"])
    text = f"""geometry:
{_geometry_yaml(contract, 2, deallocate=True, include_alias=False)}
background:
  state variables: &incvars
{_yaml_list(so['analysis_variables'], 2)}
  filename: ./bg.nc
  date: &date '{date}'
  stream name: control
  transform model to analysis: false

background error:
  covariance model: SABER

  saber central block:
    saber block name: BUMP_NICAS
    active variables: &ctlvars
{_yaml_list(contract.code_variables, 4)}
    read:
      io:
        data directory: {nicas_dir}
        files prefix: {contract.config('nicas')['files_prefix']}
      drivers:
        multivariate strategy: univariate
        read local nicas: true
      grids:
{_grids_yaml(contract, 6)}

  saber outer blocks:
  - saber block name: StdDev
    read:
      model file:
        filename: {stddev_file}
        date: *date
        stream name: control
  - saber block name: BUMP_VerticalBalance
    read:
      io:
        data directory: {vbal_dir}
        files prefix: {contract.config('vbal')['files_prefix']}
      drivers:
        read local sampling: true
        read vertical balance: true
      vertical balance:
        vbal:
{_relations_read_yaml(contract, 10)}

  linear variable change:
    linear variable change name: Control2Analysis
    input variables: *ctlvars
    output variables: *incvars

dirac:
  ndir: {dirac['ndir']}
  dirLats: [{latitudes}]
  dirLons: [{longitudes}]
  ildir: {dirac['index']}
  dirvar: {dirac['variable']}

output dirac:
  filename: ./mpas.dirac.nc
  date: *date
  stream name: control
"""
    write_text(path, text)


def apply_contract(legacy: Any, contract: BMatrixContract) -> None:
    """Inject configuration-driven renderers into the established workflow runner."""
    legacy.STATE_VARIABLES = contract.code_variables
    # Workspace directories and diagnostic NetCDF fields retain physical names.
    legacy.NICAS_VARIABLES = contract.file_variables
    legacy.MIN_HDIAG_MEMBERS = int(contract.config("hdiag")["min_members"])
    legacy.SO_BACKGROUND_VARIABLES = list(contract.config("single_observation")["background_variables"])
    legacy.SO_VARIANTS = tuple(contract.config("single_observation")["variants"])
    legacy.NICAS_DIRAC_POINTS = [
        (point["longitude"], point["latitude"])
        for point in contract.config("nicas")["dirac_points"]
    ]
    legacy.DIRAC_LATS = list(contract.config("dirac")["latitudes"])
    legacy.DIRAC_LONS = list(contract.config("dirac")["longitudes"])

    def write_stream_list_control(path: Path) -> None:
        write_text(path, "\n".join(contract.file_variables) + "\n")

    legacy.write_stream_list_control = write_stream_list_control
    legacy.write_vbal_yaml = lambda path, nmembers, date: _write_vbal_yaml(
        contract, path, nmembers, date
    )
    legacy.write_hdiag_yaml = lambda path, nmembers, date: _write_hdiag_yaml(
        contract, path, nmembers, date
    )
    legacy.write_nicas_yaml = lambda path, variable, date, nvertlevels: _write_nicas_yaml(
        contract, path, variable, date, nvertlevels
    )
    legacy.write_so_yaml = (
        lambda path, date, nicas_dir, stddev_file, vbal_dir, variant="default": _write_so_yaml(
            contract, path, date, nicas_dir, stddev_file, vbal_dir, variant
        )
    )
    legacy.write_dirac_yaml = lambda path, date, nicas_dir, stddev_file, vbal_dir: _write_dirac_yaml(
        contract, path, date, nicas_dir, stddev_file, vbal_dir
    )


def main() -> int:
    from . import bcov

    _, contract = load_contract_from_argv()
    apply_contract(bcov, contract)
    return bcov.main()
