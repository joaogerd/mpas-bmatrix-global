from __future__ import annotations

from pathlib import Path
import re

from .config import safe_time
from .pbs import mpas_init_pbs
from .shell import symlink_force, write_text, qsub


def init_run_dir(config, init_time):
    return Path(config["project"]["work_root"]) / "mpas_init" / config["mesh"]["name"] / f"{init_time}_invariant_np64"


def init_file(config, init_time):
    s = safe_time(init_time)
    return init_run_dir(config, init_time) / f"{config['mesh']['name']}.init.{s}.nc"


def require_file(path, label=None):
    path = Path(path)
    if not path.exists():
        msg = f"ERRO: arquivo obrigatório não encontrado: {path}"
        if label:
            msg = f"ERRO: {label} não encontrado: {path}"
        raise SystemExit(msg)
    return path


def patch_namelist(text, replacements):
    missing = []
    for key, value in replacements.items():
        pattern = rf"(^\s*{re.escape(key)}\s*=\s*)[^,\n]*(.*)$"
        repl = rf"\g<1>{value}\g<2>"
        new_text, count = re.subn(pattern, repl, text, flags=re.MULTILINE)
        if count == 0:
            missing.append(key)
        text = new_text

    if missing:
        raise SystemExit(
            "ERRO: opções esperadas não foram encontradas no namelist.init_atmosphere: "
            + ", ".join(missing)
        )
    return text


def patch_streams_init_atmosphere(text: str, mesh_name: str, output_filename: str) -> str:
    """Patch the MPAS init streams template for the configured mesh/run.

    The installed MPAS-JEDI template may contain tutorial mesh names such as
    x1.40962.grid.nc and output names such as x1.40962.init.nc.  Leaving those
    values in place makes the job fail only after PBS submission, so we patch and
    validate the generated stream file before qsub.
    """

    # Mesh stream: replace any MPAS x1.* grid file by the configured mesh file.
    text = re.sub(
        r"filename_template\s*=\s*([\"'])x1\.[0-9]+\.grid\.nc\1",
        f'filename_template="{mesh_name}.grid.nc"',
        text,
    )

    # Output stream: replace both x1.40962.init.nc and timestamped init names.
    text = re.sub(
        r"filename_template\s*=\s*([\"'])x1\.[0-9]+\.init(?:\.[^\"']*)?\.nc\1",
        f'filename_template="{output_filename}"',
        text,
    )

    # Idempotent workflow: a rerun must be able to overwrite a partial/stale init file.
    text = re.sub(
        r"clobber_mode\s*=\s*([\"'])never_modify\1",
        'clobber_mode="overwrite"',
        text,
    )

    return text


def clean_init_run_dir(run_dir: Path, mesh_name: str):
    """Remove only generated files that can make a rerun misleading or non-idempotent."""
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
    run_dir = init_run_dir(config, init_time)
    mesh = config["mesh"]
    nproc = int(mesh["nproc"])
    expected = init_file(config, init_time)
    graph = Path(mesh["graph"])
    partition = Path(mesh["partitions_dir"]) / f"{graph.name}.part.{nproc}"

    checks = [
        (run_dir / "mpas_init_atmosphere", "run-local mpas_init_atmosphere"),
        (run_dir / f"{mesh['name']}.grid.nc", "run-local mesh/invariant input"),
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

    required_stream_tokens = [
        f'{mesh["name"]}.grid.nc',
        expected.name,
    ]
    for token in required_stream_tokens:
        if token not in streams_text:
            raise SystemExit(
                f"ERRO: streams.init_atmosphere não contém '{token}'. Veja {run_dir / 'streams.init_atmosphere'}"
            )

    stale_refs = sorted(set(re.findall(r"x1\.[0-9]+\.(?:grid|init)(?:\.[A-Za-z0-9_:\-.]+)?\.nc", streams_text)))
    allowed_refs = {f"{mesh['name']}.grid.nc", expected.name}
    bad_refs = [ref for ref in stale_refs if ref not in allowed_refs]
    if bad_refs:
        raise SystemExit(
            "ERRO: streams.init_atmosphere ainda contém referências de outra malha/saída: "
            + ", ".join(bad_refs)
        )

    if 'clobber_mode="never_modify"' in streams_text or "clobber_mode='never_modify'" in streams_text:
        raise SystemExit(
            "ERRO: streams.init_atmosphere ainda contém clobber_mode=never_modify; "
            "isso impede reruns idempotentes."
        )

    required_namelist_tokens = [
        "config_init_case = 7",
        f"config_start_time = '{init_time}'",
        f"config_stop_time = '{init_time}'",
        "config_static_interp = .false.",
        "config_met_interp = .true.",
        f"config_block_decomp_file_prefix = '{graph.name}.part.'",
    ]
    for token in required_namelist_tokens:
        if token not in namelist_text:
            raise SystemExit(
                f"ERRO: namelist.init_atmosphere não contém configuração esperada: {token}"
            )

    print("OK: preflight do MPAS init passou")
    print(f"  RUN_DIR={run_dir}")
    print(f"  WPS_FILE={Path(wps_file)}")
    print(f"  MESH_INPUT={run_dir / (mesh['name'] + '.grid.nc')}")
    print(f"  EXPECTED_OUTPUT={expected}")


def _tail(path: Path, n: int = 80) -> str:
    if not path.exists():
        return f"{path} não existe"
    lines = path.read_text(errors="replace").splitlines()
    return "\n".join(lines[-n:])


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

    candidates.extend(sorted(run_dir.glob("mpas_init_x1.10242.o*"))[-3:])

    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        print(f"\n--- tail {path.name} ---")
        print(_tail(path))


def prepare_init(config, init_time, wps_file):
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

    symlink_force(install["mpas_init"], run_dir / "mpas_init_atmosphere")
    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.grid.nc")
    symlink_force(wps_file, run_dir / Path(wps_file).name)
    symlink_force(mesh["graph"], run_dir / graph.name)
    symlink_force(partition, run_dir / partition.name)

    template = Path(install["init_share"]) / "namelist.init_atmosphere"
    streams = Path(install["init_share"]) / "streams.init_atmosphere"
    require_file(template, "namelist.init_atmosphere")
    require_file(streams, "streams.init_atmosphere")

    namelist = template.read_text()
    namelist = patch_namelist(namelist, {
        "config_init_case": "7",
        "config_start_time": f"'{init_time}'",
        "config_stop_time": f"'{init_time}'",
        "config_nvertlevels": str(mesh["nvertlevels"]),
        "config_met_prefix": "'FILE'",
        "config_sfc_prefix": "'FILE'",
        "config_static_interp": ".false.",
        "config_native_gwd_static": ".false.",
        "config_native_gwd_gsl_static": ".false.",
        "config_vertical_grid": ".true.",
        "config_met_interp": ".true.",
        "config_block_decomp_file_prefix": f"'{graph.name}.part.'",
    })
    write_text(run_dir / "namelist.init_atmosphere", namelist)

    streams_text = patch_streams_init_atmosphere(
        streams.read_text(),
        mesh_name=mesh["name"],
        output_filename=Path(init_file(config, init_time)).name,
    )
    write_text(run_dir / "streams.init_atmosphere", streams_text)

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
    f = init_file(config, init_time)
    if not f.exists():
        print_init_diagnostics(config, init_time, jobid=jobid)
        raise SystemExit(f"ERRO: init.nc não encontrado: {f}")

    log = init_run_dir(config, init_time) / "log.init_atmosphere.0000.out"
    if not log.exists():
        print_init_diagnostics(config, init_time, jobid=jobid)
        raise SystemExit(f"ERRO: log.init_atmosphere.0000.out não encontrado: {log}")

    txt = log.read_text(errors="replace")
    if "Critical error messages =            0" not in txt:
        print_init_diagnostics(config, init_time, jobid=jobid)
        raise SystemExit(f"ERRO: init não terminou limpo. Veja {log}")

    if "Error messages =                     0" not in txt:
        print_init_diagnostics(config, init_time, jobid=jobid)
        raise SystemExit(f"ERRO: init terminou com mensagens de erro. Veja {log}")

    print(f"OK: init validado: {f}")
