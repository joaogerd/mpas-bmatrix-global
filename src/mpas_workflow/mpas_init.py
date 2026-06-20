from __future__ import annotations

from pathlib import Path
import re

from .config import safe_time
from .model_config import model_config, render
from .pbs import mpas_init_pbs
from .shell import qsub, symlink_force, write_text


def _init_settings(config):
    return model_config(config)["init"]


def init_run_dir(config, init_time):
    mesh = config["mesh"]
    pattern = _init_settings(config)["run_directory"]
    relative = render(
        pattern,
        mesh_name=mesh["name"],
        init_time=init_time,
        safe_time=safe_time(init_time),
        nproc=int(mesh.get("nproc", 64)),
    )
    return Path(config["project"]["work_root"]) / relative


def init_file(config, init_time):
    mesh = config["mesh"]
    pattern = _init_settings(config)["output_filename"]
    filename = render(
        pattern,
        mesh_name=mesh["name"],
        init_time=init_time,
        safe_time=safe_time(init_time),
        nproc=int(mesh.get("nproc", 64)),
    )
    return init_run_dir(config, init_time) / filename


def require_file(path, label=None):
    path = Path(path)
    if not path.exists():
        message = f"ERRO: arquivo obrigatório não encontrado: {path}"
        if label:
            message = f"ERRO: {label} não encontrado: {path}"
        raise SystemExit(message)
    return path


def patch_namelist(text, replacements):
    missing = []
    for key, value in replacements.items():
        pattern = rf"(^\s*{re.escape(key)}\s*=\s*)[^,\n]*(.*)$"
        replacement = rf"\g<1>{value}\g<2>"
        text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if count == 0:
            missing.append(key)

    if missing:
        raise SystemExit(
            "ERRO: opções esperadas não foram encontradas no namelist.init_atmosphere: "
            + ", ".join(missing)
        )
    return text


def patch_streams_init_atmosphere(
    text: str,
    mesh_name: str,
    output_filename: str,
    streams_config: dict | None = None,
) -> str:
    """Patch the installed stream template for the configured mesh and output."""
    streams_config = streams_config or {
        "replace_clobber_mode": "never_modify",
        "output_clobber_mode": "overwrite",
    }

    text = re.sub(
        r"filename_template\s*=\s*([\"'])x1\.[0-9]+\.grid\.nc\1",
        f'filename_template="{mesh_name}.grid.nc"',
        text,
    )
    text = re.sub(
        r"filename_template\s*=\s*([\"'])x1\.[0-9]+\.init(?:\.[^\"']*)?\.nc\1",
        f'filename_template="{output_filename}"',
        text,
    )

    old_clobber = re.escape(str(streams_config["replace_clobber_mode"]))
    new_clobber = str(streams_config["output_clobber_mode"])
    return re.sub(
        rf"clobber_mode\s*=\s*([\"']){old_clobber}\1",
        f'clobber_mode="{new_clobber}"',
        text,
    )


def clean_init_run_dir(run_dir: Path, mesh_name: str):
    """Remove only generated files that make a rerun misleading or non-idempotent."""
    patterns = [
        "stdout.log",
        "stderr.log",
        "log.init_atmosphere.*",
        "*.o[0-9]*",
        "*.e[0-9]*",
        f"{mesh_name}.init.*.nc",
        "x1.*.init*.nc",
    ]
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if path.exists() or path.is_symlink():
                path.unlink()


def validate_init_setup(config, init_time, wps_file):
    """Validate everything that can be checked before spending a PBS job."""
    settings = _init_settings(config)
    run_dir = init_run_dir(config, init_time)
    mesh = config["mesh"]
    nproc = int(mesh["nproc"])
    expected = init_file(config, init_time)
    graph = Path(mesh["graph"])
    partition = Path(mesh["partitions_dir"]) / f"{graph.name}.part.{nproc}"
    grid_name = render(settings["input_grid_filename"], mesh_name=mesh["name"])

    checks = [
        (run_dir / "mpas_init_atmosphere", "run-local mpas_init_atmosphere"),
        (run_dir / grid_name, "run-local mesh/invariant input"),
        (Path(wps_file), "WPS FILE"),
        (run_dir / Path(wps_file).name, "run-local WPS FILE link"),
        (run_dir / graph.name, "run-local graph.info link"),
        (run_dir / partition.name, "run-local graph partition link"),
        (run_dir / "namelist.init_atmosphere", "namelist.init_atmosphere"),
        (run_dir / "streams.init_atmosphere", "streams.init_atmosphere"),
        (run_dir / "run_mpas_init.pbs", "run_mpas_init.pbs"),
    ]
    for path, label in checks:
        require_file(path, label)

    streams_text = (run_dir / "streams.init_atmosphere").read_text(errors="replace")
    namelist_text = (run_dir / "namelist.init_atmosphere").read_text(errors="replace")

    for token in (grid_name, expected.name):
        if token not in streams_text:
            raise SystemExit(
                f"ERRO: streams.init_atmosphere não contém '{token}'. "
                f"Veja {run_dir / 'streams.init_atmosphere'}"
            )

    stale_refs = sorted(
        set(re.findall(r"x1\.[0-9]+\.(?:grid|init)(?:\.[A-Za-z0-9_:\-.]+)?\.nc", streams_text))
    )
    allowed_refs = {grid_name, expected.name}
    bad_refs = [reference for reference in stale_refs if reference not in allowed_refs]
    if bad_refs:
        raise SystemExit(
            "ERRO: streams.init_atmosphere ainda contém referências de outra malha/saída: "
            + ", ".join(bad_refs)
        )

    old_clobber = settings["streams"]["replace_clobber_mode"]
    if (
        f'clobber_mode="{old_clobber}"' in streams_text
        or f"clobber_mode='{old_clobber}'" in streams_text
    ):
        raise SystemExit(
            f"ERRO: streams.init_atmosphere ainda contém clobber_mode={old_clobber}; "
            "isso impede reruns idempotentes."
        )

    required = {
        "config_start_time": f"'{init_time}'",
        "config_stop_time": f"'{init_time}'",
        "config_nvertlevels": str(mesh["nvertlevels"]),
        "config_block_decomp_file_prefix": f"'{graph.name}.part.'",
    }
    required.update(settings["namelist"])
    for key, value in required.items():
        token = f"{key} = {value}"
        if token not in namelist_text:
            raise SystemExit(
                f"ERRO: namelist.init_atmosphere não contém configuração esperada: {token}"
            )

    print("OK: preflight do MPAS init passou")
    print(f"  RUN_DIR={run_dir}")
    print(f"  WPS_FILE={Path(wps_file)}")
    print(f"  MESH_INPUT={run_dir / grid_name}")
    print(f"  EXPECTED_OUTPUT={expected}")


def _tail(path: Path, n: int = 80) -> str:
    if not path.exists():
        return f"{path} não existe"
    return "\n".join(path.read_text(errors="replace").splitlines()[-n:])


def print_init_diagnostics(config, init_time, jobid: str | None = None):
    run_dir = init_run_dir(config, init_time)
    print("\n=== MPAS init diagnostics ===")
    print(f"RUN_DIR={run_dir}")
    print(f"EXPECTED_INIT={init_file(config, init_time)}")

    candidates = [
        run_dir / "stderr.log",
        run_dir / "stdout.log",
        run_dir / "log.init_atmosphere.0000.out",
        run_dir / "log.init_atmosphere.0000.err",
        run_dir / "namelist.init_atmosphere",
        run_dir / "streams.init_atmosphere",
    ]
    if jobid:
        candidates.extend(sorted(run_dir.glob(f"*.o{jobid.split('.')[0]}")))
    candidates.extend(sorted(run_dir.glob("mpas_init_*.o*"))[-3:])

    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        print(f"\n--- tail {path.name} ---")
        print(_tail(path))


def init_validation_error(config, init_time) -> str | None:
    """Return an init validation error without printing diagnostics."""
    output = init_file(config, init_time)
    if not output.exists():
        return f"init.nc não encontrado: {output}"

    log = init_run_dir(config, init_time) / "log.init_atmosphere.0000.out"
    if not log.exists():
        return f"log.init_atmosphere.0000.out não encontrado: {log}"

    text = log.read_text(errors="replace")
    for token in _init_settings(config)["validation"]["log_success_tokens"]:
        if token not in text:
            return f"init não terminou limpo; token ausente {token!r}. Veja {log}"
    return None


def init_is_valid(config, init_time) -> bool:
    return init_validation_error(config, init_time) is None


def prepare_init(config, init_time, wps_file):
    settings = _init_settings(config)
    run_dir = init_run_dir(config, init_time)
    run_dir.mkdir(parents=True, exist_ok=True)

    mesh = config["mesh"]
    install = config["install"]
    static = config["static"]
    nproc = int(mesh["nproc"])

    require_file(wps_file, "WPS FILE")
    require_file(install["mpas_init"], "mpas_init_atmosphere")
    require_file(mesh["graph"], "graph.info")
    graph = Path(mesh["graph"])
    partition = Path(mesh["partitions_dir"]) / f"{graph.name}.part.{nproc}"
    require_file(partition, "graph partition")
    require_file(static["invariant"], "invariant")

    clean_init_run_dir(run_dir, mesh["name"])

    grid_name = render(settings["input_grid_filename"], mesh_name=mesh["name"])
    symlink_force(install["mpas_init"], run_dir / "mpas_init_atmosphere")
    symlink_force(static["invariant"], run_dir / grid_name)
    symlink_force(wps_file, run_dir / Path(wps_file).name)
    symlink_force(mesh["graph"], run_dir / graph.name)
    symlink_force(partition, run_dir / partition.name)

    namelist_template = Path(install["init_share"]) / "namelist.init_atmosphere"
    streams_template = Path(install["init_share"]) / "streams.init_atmosphere"
    require_file(namelist_template, "namelist.init_atmosphere")
    require_file(streams_template, "streams.init_atmosphere")

    replacements = {
        "config_start_time": f"'{init_time}'",
        "config_stop_time": f"'{init_time}'",
        "config_nvertlevels": str(mesh["nvertlevels"]),
        "config_block_decomp_file_prefix": f"'{graph.name}.part.'",
    }
    replacements.update(settings["namelist"])
    write_text(
        run_dir / "namelist.init_atmosphere",
        patch_namelist(namelist_template.read_text(), replacements),
    )
    write_text(
        run_dir / "streams.init_atmosphere",
        patch_streams_init_atmosphere(
            streams_template.read_text(),
            mesh_name=mesh["name"],
            output_filename=init_file(config, init_time).name,
            streams_config=settings["streams"],
        ),
    )

    write_text(run_dir / "run_mpas_init.pbs", mpas_init_pbs(config, run_dir, nproc))
    validate_init_setup(config, init_time, wps_file)

    print(f"OK: diretório de init preparado: {run_dir}")
    print(f"Arquivo esperado: {init_file(config, init_time)}")
    return run_dir


def submit_init(config, init_time):
    run_dir = init_run_dir(config, init_time)
    require_file(run_dir / "run_mpas_init.pbs", "PBS de init")
    return qsub("run_mpas_init.pbs", run_dir)


def validate_init(config, init_time, jobid: str | None = None):
    error = init_validation_error(config, init_time)
    if error is not None:
        print_init_diagnostics(config, init_time, jobid=jobid)
        raise SystemExit(f"ERRO: {error}")
    print(f"OK: init validado: {init_file(config, init_time)}")
