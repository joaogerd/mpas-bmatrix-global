from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Dict, Iterable, List, Optional

from .forecast import restart_file
from .shell import require_file, symlink_force, write_text


DEFAULT_DIFF_VARIABLES = [
    "u",
    "w",
    "rho",
    "theta",
    "qv",
    "qc",
    "qr",
    "qi",
    "qs",
    "qg",
    "pressure",
    "pressure_p",
    "surface_pressure",
    "temperature",
    "air_temperature",
    "water_vapor_mixing_ratio_wrt_moist_air",
    "water_vapor_mixing_ratio_wrt_dry_air",
]


def pair_dir(config, valid_time):
    return (
        Path(config["project"]["work_root"])
        / "nmc_pairs"
        / f"nmc_{config['mesh']['name']}_valid_{valid_time.replace(':', '.')}"
    )


def prepare_pair(config, old_init_time, new_init_time, valid_time, dt=None):
    dt = int(dt or config["runtime"]["config_dt"])
    f048 = restart_file(config, old_init_time, 48, dt)
    f024 = restart_file(config, new_init_time, 24, dt)

    require_file(f048, "forecast antigo f048")
    require_file(f024, "forecast novo f024")

    out = pair_dir(config, valid_time)
    out.mkdir(parents=True, exist_ok=True)

    symlink_force(f048, out / "f048.nc")
    symlink_force(f024, out / "f024.nc")

    env = (
        f"MESH_NAME={config['mesh']['name']}\n"
        f"CONFIG_DT={dt}\n"
        f"OLD_INIT_TIME={old_init_time}\n"
        f"NEW_INIT_TIME={new_init_time}\n"
        f"VALID_TIME={valid_time}\n"
        f"F048={out / 'f048.nc'}\n"
        f"F024={out / 'f024.nc'}\n"
    )
    write_text(out / "pair.env", env)

    readme = (
        "# Par NMC\n\n"
        f"- `f048.nc`: forecast antigo, iniciado em `{old_init_time}`\n"
        f"- `f024.nc`: forecast novo, iniciado em `{new_init_time}`\n"
        f"- horário válido comum: `{valid_time}`\n\n"
        "Diferença NMC esperada:\n\n"
        "```text\n"
        "f048 - f024\n"
        "```\n"
    )
    write_text(out / "README.md", readme)

    print(f"OK: par NMC montado: {out}")
    return out


def _run_capture(cmd: List[str]) -> str:
    proc = subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout


def _ncdump_header(path: Path) -> str:
    try:
        return _run_capture(["ncdump", "-h", str(path)])
    except FileNotFoundError as exc:
        raise SystemExit("ERRO: comando ncdump não encontrado no ambiente atual.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"ERRO: ncdump falhou para {path}\nSTDERR:\n{exc.stderr}"
        ) from exc


def _parse_dimensions(header: str) -> Dict[str, int]:
    dims = {}
    in_dims = False

    for line in header.splitlines():
        if line.strip() == "dimensions:":
            in_dims = True
            continue

        if in_dims and line.strip() == "variables:":
            break

        if not in_dims:
            continue

        m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*(\d+)\s*;", line)
        if m:
            dims[m.group(1)] = int(m.group(2))
            continue

        m = re.match(
            r"\s*([A-Za-z0-9_]+)\s*=\s*UNLIMITED\s*;\s*//\s*\((\d+)\s+currently\)",
            line,
        )
        if m:
            dims[m.group(1)] = int(m.group(2))

    return dims


def _parse_variables(header: str) -> Dict[str, Dict[str, object]]:
    variables = {}

    for line in header.splitlines():
        m = re.match(
            r"\s*([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\(([^)]*)\)\s*;",
            line,
        )
        if not m:
            continue

        dtype = m.group(1)
        name = m.group(2)
        dims = tuple(x.strip() for x in m.group(3).split(",") if x.strip())
        variables[name] = {"dtype": dtype, "dims": dims}

    return variables


def _basic_summary(path: Path) -> Dict[str, object]:
    header = _ncdump_header(path)
    return {
        "path": path,
        "dimensions": _parse_dimensions(header),
        "variables": _parse_variables(header),
    }


def validate_pair(config, valid_time, strict: bool = True):
    out = pair_dir(config, valid_time)
    f048 = require_file(out / "f048.nc", "par NMC f048.nc")
    f024 = require_file(out / "f024.nc", "par NMC f024.nc")

    s048 = _basic_summary(f048)
    s024 = _basic_summary(f024)

    required_dims = [
        "Time",
        "nCells",
        "nEdges",
        "nVertices",
        "nVertLevels",
    ]

    errors = []

    for dim in required_dims:
        d048 = s048["dimensions"].get(dim)
        d024 = s024["dimensions"].get(dim)
        if d048 != d024:
            errors.append(f"dimensão incompatível {dim}: f048={d048}, f024={d024}")

    common_vars = set(s048["variables"]) & set(s024["variables"])
    required_vars = ["u", "rho", "theta", "qv"]

    for var in required_vars:
        if var not in common_vars:
            errors.append(f"variável obrigatória ausente no par: {var}")

    for var in sorted(common_vars):
        v048 = s048["variables"][var]
        v024 = s024["variables"][var]
        if v048["dims"] != v024["dims"]:
            errors.append(
                f"dimensões incompatíveis na variável {var}: "
                f"f048={v048['dims']}, f024={v024['dims']}"
            )

    print("=== NMC pair validation ===")
    print(f"PAIR_DIR={out}")
    print(f"F048={f048.resolve()}")
    print(f"F024={f024.resolve()}")
    print()
    print("Dimensions:")
    for dim in required_dims:
        print(f"  {dim}: {s048['dimensions'].get(dim)}")
    print()
    print(f"Common variables: {len(common_vars)}")

    if errors:
        print()
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")

        if strict:
            raise SystemExit("ERRO: par NMC inválido.")

        print("WARNING: par NMC tem inconsistências.")
        return False

    print()
    print("SUCCESS: par NMC estruturalmente consistente.")
    return True


def parse_variables_arg(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def diff_pair(
    config,
    valid_time,
    variables: Optional[Iterable[str]] = None,
    output: Optional[str | Path] = None,
):
    try:
        import netCDF4
    except ImportError as exc:
        raise SystemExit(
            "ERRO: o comando nmc diff requer o módulo Python netCDF4.\n"
            "Tente no JACI:\n"
            "  python3 -m pip install --user netCDF4\n"
            "ou carregue um ambiente que já tenha esse módulo."
        ) from exc

    out = pair_dir(config, valid_time)
    f048 = require_file(out / "f048.nc", "par NMC f048.nc")
    f024 = require_file(out / "f024.nc", "par NMC f024.nc")

    validate_pair(config, valid_time, strict=True)

    output = Path(output) if output else out / "nmc_diff_f048_minus_f024.nc"
    requested = list(variables) if variables else list(DEFAULT_DIFF_VARIABLES)

    with netCDF4.Dataset(f048) as ds48, netCDF4.Dataset(f024) as ds24:
        available = [
            v for v in requested
            if v in ds48.variables
            and v in ds24.variables
            and ds48.variables[v].dimensions == ds24.variables[v].dimensions
        ]

        if not available:
            raise SystemExit(
                "ERRO: nenhuma variável solicitada está disponível nos dois arquivos "
                "com as mesmas dimensões."
            )

        with netCDF4.Dataset(output, "w") as dst:
            for name, dim in ds48.dimensions.items():
                dst.createDimension(name, None if dim.isunlimited() else len(dim))

            for attr in ds48.ncattrs():
                try:
                    dst.setncattr(attr, ds48.getncattr(attr))
                except Exception:
                    pass

            dst.setncattr("nmc_difference", "f048_minus_f024")
            dst.setncattr("source_f048", str(f048.resolve()))
            dst.setncattr("source_f024", str(f024.resolve()))
            dst.setncattr("valid_time", valid_time)
            dst.setncattr("nmc_variables", ",".join(available))

            for name in available:
                v48 = ds48.variables[name]
                v24 = ds24.variables[name]

                fill_value = getattr(v48, "_FillValue", None)

                if fill_value is not None:
                    outvar = dst.createVariable(
                        name,
                        v48.dtype,
                        v48.dimensions,
                        zlib=False,
                        fill_value=fill_value,
                    )
                else:
                    outvar = dst.createVariable(
                        name,
                        v48.dtype,
                        v48.dimensions,
                        zlib=False,
                    )

                for attr in v48.ncattrs():
                    if attr == "_FillValue":
                        continue
                    try:
                        outvar.setncattr(attr, v48.getncattr(attr))
                    except Exception:
                        pass

                outvar.setncattr("nmc_operation", "f048_minus_f024")
                outvar[:] = v48[:] - v24[:]

    print("=== NMC difference ===")
    print(f"PAIR_DIR={out}")
    print(f"OUTPUT={output}")
    print("Variables:")
    for name in available:
        print(f"  - {name}")
    print()
    print("SUCCESS: arquivo de diferença NMC criado.")
    return output
