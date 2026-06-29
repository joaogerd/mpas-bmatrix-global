"""Orchestration of declarative MPAS cases from static through forecast."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import json
import re
from typing import Any, Mapping

from .case_config import CaseConfig, resolve_context, resolve_structure
from .case_render import _time_context, render_stage
from .case_wps import ensure_wps_file
from .runtime_prepare import RuntimePrepareError, prepare_stage
from .shell import qsub, wait_for_pbs_job


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


class CaseRunError(ValueError):
    """Raised when a declared MPAS cycle cannot be prepared or validated."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaseRunError(f"{label} deve ser um mapa YAML.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CaseRunError(f"{label} deve ser uma string não vazia.")
    return value


def _stage(case: CaseConfig, stage_name: str, overrides: Mapping[str, Any]) -> tuple[dict[str, Any], Mapping[str, Any]]:
    context = resolve_context(case, overrides)
    stages = _mapping(case.data.get("stages", {}), "stages")
    if stage_name not in stages:
        raise CaseRunError(f"Estágio não declarado: {stage_name}")
    return context, _mapping(resolve_structure(stages[stage_name], context), f"stages.{stage_name}")


def _runtime_dir(stage: Mapping[str, Any]) -> Path:
    runtime = _mapping(stage.get("runtime"), "stage.runtime")
    return Path(_text(runtime.get("output_dir"), "runtime.output_dir")).expanduser().resolve()


def _expand_mpas_time(value: str, valid_time: str) -> str:
    try:
        instant = datetime.strptime(valid_time, TIME_FORMAT)
    except ValueError as exc:
        raise CaseRunError(f"valid_time inválido: {valid_time}") from exc
    for token, replacement in {
        "$Y": instant.strftime("%Y"), "$M": instant.strftime("%m"), "$D": instant.strftime("%d"),
        "$h": instant.strftime("%H"), "$m": instant.strftime("%M"), "$s": instant.strftime("%S"),
    }.items():
        value = value.replace(token, replacement)
    return value


def _outputs(stage: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[Path, ...]:
    runtime = _mapping(stage.get("runtime"), "stage.runtime")
    raw = list(runtime.get("expected_outputs", [])) + list(runtime.get("additional_expected_outputs", []))
    if not raw or not all(isinstance(item, str) and item for item in raw):
        raise CaseRunError("runtime.expected_outputs deve declarar ao menos uma saída.")
    directory = _runtime_dir(stage)
    result: list[Path] = []
    for item in raw:
        path = Path(_expand_mpas_time(item, str(context.get("valid_time", context.get("init_time", "")))))
        if path.is_absolute() or ".." in path.parts:
            raise CaseRunError(f"Saída de runtime deve ser relativa: {item}")
        result.append(directory / path)
    return tuple(result)


def _execution(stage: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(stage.get("execution"), "stage.execution")


def _walltime(execution: Mapping[str, Any], lead_hours: int) -> str:
    raw = execution.get("walltime")
    if isinstance(raw, str) and raw:
        return raw
    if not isinstance(raw, Mapping):
        raise CaseRunError("execution.walltime deve ser uma string ou mapa.")
    by_lead = raw.get("by_lead_hours", {})
    if isinstance(by_lead, Mapping):
        candidate = by_lead.get(str(lead_hours), by_lead.get(lead_hours))
        if isinstance(candidate, str) and candidate:
            return candidate
    return _text(raw.get("default"), "execution.walltime.default")


def _pbs_text(
    *,
    context: Mapping[str, Any],
    stage_name: str,
    stage: Mapping[str, Any],
    runtime_dir: Path,
    lead_hours: int,
) -> str:
    runtime = _mapping(stage.get("runtime"), "stage.runtime")
    executable = _mapping(runtime.get("executable"), "runtime.executable")
    execution = _execution(stage)
    nproc = int(context.get("nproc", 0))
    if nproc <= 0:
        raise CaseRunError("context.nproc deve ser positivo.")
    job_name = _text(execution.get("job_name"), "execution.job_name")
    queue = _text(execution.get("queue"), "execution.queue")
    walltime = _walltime(execution, lead_hours)
    repo = _text(context.get("repository_root"), "context.repository_root")
    local_executable = _text(executable.get("destination"), "runtime.executable.destination")
    stdout = f"stdout.{stage_name}.log"
    stderr = f"stderr.{stage_name}.log"
    return f"""#!/bin/bash
#PBS -N {job_name}
#PBS -q {queue}
#PBS -l select=1:ncpus={nproc}:mpiprocs={nproc}
#PBS -l walltime={walltime}
#PBS -j oe

set -euo pipefail
source \"{repo}/scripts/load_jaci_env.sh\"
cd \"{runtime_dir}\"

export OMP_NUM_THREADS=1
export FI_CXI_RX_MATCH_MODE=hybrid
export GFORTRAN_CONVERT_UNIT=big_endian:101-200
ulimit -s unlimited || true

rm -f \"{stdout}\" \"{stderr}\"
mpiexec -n {nproc} \"./{local_executable}\" > \"{stdout}\" 2> \"{stderr}\"
"""


def _write_pbs(context: Mapping[str, Any], stage_name: str, stage: Mapping[str, Any], lead_hours: int) -> Path:
    runtime_dir = _runtime_dir(stage)
    path = runtime_dir / f"run_mpas_{stage_name}.pbs"
    path.write_text(_pbs_text(context=context, stage_name=stage_name, stage=stage, runtime_dir=runtime_dir, lead_hours=lead_hours))
    return path


def _remove_outputs(outputs: tuple[Path, ...]) -> None:
    for path in outputs:
        if path.exists() and not path.is_symlink():
            path.unlink()


def _validate_outputs(outputs: tuple[Path, ...]) -> None:
    missing = [path for path in outputs if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise CaseRunError("Saídas MPAS ausentes ou vazias:\n" + "\n".join(f"- {path}" for path in missing))


def _base_overrides(init_time: str, lead_hours: int, dt: int) -> dict[str, Any]:
    return _time_context(init_time, lead_hours, dt)


def ensure_stage(
    case: CaseConfig,
    stage_name: str,
    *,
    init_time: str,
    lead_hours: int = 0,
    dt: int = 1200,
    submit: bool = False,
    wait: bool = False,
    force: bool = False,
    download: bool = True,
    poll_seconds: int = 30,
) -> bool:
    """Ensure one stage exists; init obtains FILE:* only when it is absent."""
    overrides = _base_overrides(init_time, lead_hours, dt)
    if stage_name == "init":
        file_path = ensure_wps_file(case, init_time, overrides=overrides, download=download)
        overrides["wps_input_dir"] = str(file_path.parent)

    context, stage = _stage(case, stage_name, overrides)
    outputs = _outputs(stage, context)
    if not force and all(path.is_file() and path.stat().st_size > 0 for path in outputs):
        print(f"OK: estágio {stage_name} já concluído: {outputs[0]}")
        return True
    if force:
        _remove_outputs(outputs)

    render_stage(case, stage_name, overrides=overrides)
    prepared = prepare_stage(case, stage_name, overrides=overrides)
    pbs = _write_pbs(context, stage_name, stage, lead_hours)
    print(f"OK: runtime {stage_name} preparado: {prepared.output_dir}")
    print(f"PBS={pbs}")

    if not submit:
        return False
    jobid = qsub(pbs.name, prepared.output_dir)
    print(f"JOBID={jobid}")
    if not wait:
        return False
    wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    _validate_outputs(outputs)
    print(f"OK: estágio {stage_name} validado: {outputs[0]}")
    return True


def ensure_cycle(
    case: CaseConfig,
    *,
    init_time: str,
    lead_hours: int,
    dt: int,
    submit: bool,
    wait: bool,
    force: bool = False,
    download: bool = True,
    poll_seconds: int = 30,
) -> bool:
    """Ensure static, init, and one forecast in dependency order."""
    if submit and not wait:
        raise CaseRunError("Um ciclo completo com --submit requer --wait para respeitar dependências PBS.")
    if not ensure_stage(case, "static", init_time=init_time, dt=dt, submit=submit, wait=wait, force=force, poll_seconds=poll_seconds):
        return False
    if not ensure_stage(case, "init", init_time=init_time, dt=dt, submit=submit, wait=wait, force=force, download=download, poll_seconds=poll_seconds):
        return False
    return ensure_stage(case, "forecast", init_time=init_time, lead_hours=lead_hours, dt=dt, submit=submit, wait=wait, force=force, poll_seconds=poll_seconds)


def _forecast_data_file(case: CaseConfig, init_time: str, lead_hours: int, dt: int) -> Path:
    overrides = _base_overrides(init_time, lead_hours, dt)
    context, stage = _stage(case, "forecast", overrides)
    streams = _mapping(_mapping(stage.get("streams"), "forecast.streams").get("streams"), "forecast.streams.streams")
    da_state = _mapping(streams.get("da_state", {}), "forecast.streams.da_state")
    attrs = _mapping(da_state.get("attributes", {}), "forecast.streams.da_state.attributes")
    if attrs.get("type") != "output":
        raise CaseRunError("O caso não ativa da_state; use o caso MONAN-JEDI para produzir pares NMC da matriz B.")
    template = _text(attrs.get("filename_template"), "da_state.filename_template")
    path = _runtime_dir(stage) / _expand_mpas_time(template, _text(context.get("valid_time"), "context.valid_time"))
    return path


def ensure_nmc_pair(
    case: CaseConfig,
    *,
    valid_time: str,
    dt: int,
    submit: bool,
    wait: bool,
    force: bool = False,
    download: bool = True,
    poll_seconds: int = 30,
) -> Path:
    """Produce one f048/f024 pair with the same valid time for BFLOW."""
    try:
        valid = datetime.strptime(valid_time, TIME_FORMAT)
    except ValueError as exc:
        raise CaseRunError(f"valid_time deve seguir {TIME_FORMAT}: {valid_time}") from exc
    old_init = (valid - timedelta(hours=48)).strftime(TIME_FORMAT)
    new_init = (valid - timedelta(hours=24)).strftime(TIME_FORMAT)
    if not ensure_cycle(case, init_time=old_init, lead_hours=48, dt=dt, submit=submit, wait=wait, force=force, download=download, poll_seconds=poll_seconds):
        raise CaseRunError("Forecast f048 ainda não concluído.")
    if not ensure_cycle(case, init_time=new_init, lead_hours=24, dt=dt, submit=submit, wait=wait, force=force, download=download, poll_seconds=poll_seconds):
        raise CaseRunError("Forecast f024 ainda não concluído.")

    f048 = _forecast_data_file(case, old_init, 48, dt)
    f024 = _forecast_data_file(case, new_init, 24, dt)
    _validate_outputs((f048, f024))
    context = resolve_context(case, _base_overrides(valid_time, 0, dt))
    pair_root = Path(_text(context.get("nmc_pair_root"), "context.nmc_pair_root"))
    pair_dir = pair_root / f"nmc_{context['case_name']}_valid_{valid_time.replace(':', '.')}"
    pair_dir.mkdir(parents=True, exist_ok=True)
    for source, name in ((f048, "f048.nc"), (f024, "f024.nc")):
        destination = pair_dir / name
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        destination.symlink_to(source)
    (pair_dir / "manifest.json").write_text(json.dumps({"valid_time": valid_time, "f048": str(f048), "f024": str(f024)}, indent=2) + "\n")
    print(f"OK: par NMC preparado: {pair_dir}")
    return pair_dir
