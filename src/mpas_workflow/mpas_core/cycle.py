from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ..bflow_core.manifest import write_manifest
from ..bflow_core.model import BflowPair
from ..shell import require_file
from . import init as mpas_init
from .jobs import run_job as submit_forecast
from .model import bflow_file, restart_file
from .setup import setup_run
from .wps import resolve_wps_file

TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


@dataclass(frozen=True)
class ForecastRequest:
    init_time: str
    lead_hours: int


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def iter_valid_times(start: str, end: str, step_hours: int):
    if step_hours <= 0:
        raise SystemExit("ERRO: --valid-interval-hours deve ser positivo.")
    current = datetime.strptime(start, TIME_FORMAT)
    last = datetime.strptime(end, TIME_FORMAT)
    step = timedelta(hours=step_hours)
    while current <= last:
        yield format_time(current)
        current += step


def pair_requests(valid_time: str) -> tuple[ForecastRequest, ForecastRequest]:
    valid = datetime.strptime(valid_time, TIME_FORMAT)
    return (
        ForecastRequest(format_time(valid - timedelta(hours=48)), 48),
        ForecastRequest(format_time(valid - timedelta(hours=24)), 24),
    )


def forecast_complete(config, request: ForecastRequest, dt: int) -> bool:
    paths = [
        restart_file(config, request.init_time, request.lead_hours, dt),
        bflow_file(config, request.init_time, request.lead_hours, dt),
    ]
    return all(path.is_file() and path.stat().st_size > 0 for path in paths)


def ensure_init(
    config,
    init_time: str,
    *,
    wps_file: str | Path | None = None,
    wps_dir: str | Path | None = None,
    wps_template: str | None = None,
    submit: bool = False,
    wait: bool = False,
    force: bool = False,
    poll_seconds: int = 30,
) -> Path:
    target = mpas_init.init_file(config, init_time)
    if not force and mpas_init.init_is_valid(config, init_time):
        print(f"OK: init já válido: {target}")
        return target
    resolved = resolve_wps_file(
        config,
        init_time,
        wps_file=wps_file,
        wps_dir=wps_dir,
        wps_template=wps_template,
    )
    mpas_init.prepare(config, init_time, resolved)
    if submit:
        mpas_init.submit(config, init_time, wait=wait, poll_seconds=poll_seconds)
    if wait:
        mpas_init.validate(config, init_time)
    return target


def ensure_forecast(
    config,
    request: ForecastRequest,
    *,
    dt: int,
    output_interval: str | None = None,
    submit: bool = False,
    wait: bool = False,
    force: bool = False,
    poll_seconds: int = 30,
) -> Path:
    da_state = bflow_file(config, request.init_time, request.lead_hours, dt)
    if not force and forecast_complete(config, request, dt):
        print(f"OK: forecast já válido: {da_state}")
        return da_state
    setup_run(config, request.init_time, request.lead_hours, dt=dt, output_interval=output_interval)
    if submit:
        submit_forecast(
            config,
            request.init_time,
            request.lead_hours,
            dt=dt,
            wait=wait,
            poll_seconds=poll_seconds,
        )
    if wait:
        require_file(restart_file(config, request.init_time, request.lead_hours, dt), "restart forecast")
        require_file(da_state, "MPAS-JEDI da_state forecast")
    return da_state


def ensure_forecast_cycle(
    config,
    request: ForecastRequest,
    *,
    dt: int,
    wps_file: str | Path | None = None,
    wps_dir: str | Path | None = None,
    wps_template: str | None = None,
    output_interval: str | None = None,
    submit: bool = False,
    wait: bool = False,
    force: bool = False,
    poll_seconds: int = 30,
) -> Path:
    if submit and not wait:
        raise SystemExit("ERRO: ciclo com --submit requer --wait para respeitar dependências init -> forecast.")
    ensure_init(
        config,
        request.init_time,
        wps_file=wps_file,
        wps_dir=wps_dir,
        wps_template=wps_template,
        submit=submit,
        wait=wait,
        force=force,
        poll_seconds=poll_seconds,
    )
    return ensure_forecast(
        config,
        request,
        dt=dt,
        output_interval=output_interval,
        submit=submit,
        wait=wait,
        force=force,
        poll_seconds=poll_seconds,
    )


def ensure_nmc_pair(
    config,
    valid_time: str,
    *,
    dt: int,
    wps_dir: str | Path | None = None,
    wps_template: str | None = None,
    output_interval: str | None = None,
    submit: bool = False,
    wait: bool = False,
    force: bool = False,
    poll_seconds: int = 30,
) -> BflowPair:
    f48, f24 = pair_requests(valid_time)
    f048_path = ensure_forecast_cycle(
        config,
        f48,
        dt=dt,
        wps_dir=wps_dir,
        wps_template=wps_template,
        output_interval=output_interval,
        submit=submit,
        wait=wait,
        force=force,
        poll_seconds=poll_seconds,
    )
    f024_path = ensure_forecast_cycle(
        config,
        f24,
        dt=dt,
        wps_dir=wps_dir,
        wps_template=wps_template,
        output_interval=output_interval,
        submit=submit,
        wait=wait,
        force=force,
        poll_seconds=poll_seconds,
    )
    if wait:
        require_file(f048_path, f"f048 para {valid_time}")
        require_file(f024_path, f"f024 para {valid_time}")
    pair = BflowPair(valid_time=valid_time, f048=f048_path, f024=f024_path)
    print(f"OK: par NMC {valid_time}")
    print(f"  f048={pair.f048}")
    print(f"  f024={pair.f024}")
    return pair


def ensure_nmc_pair_range(
    config,
    *,
    start_valid_time: str,
    end_valid_time: str,
    valid_interval_hours: int,
    dt: int,
    manifest: str | Path | None = None,
    wps_dir: str | Path | None = None,
    wps_template: str | None = None,
    output_interval: str | None = None,
    submit: bool = False,
    wait: bool = False,
    force: bool = False,
    poll_seconds: int = 30,
) -> list[BflowPair]:
    pairs = []
    for valid_time in iter_valid_times(start_valid_time, end_valid_time, valid_interval_hours):
        pairs.append(
            ensure_nmc_pair(
                config,
                valid_time,
                dt=dt,
                wps_dir=wps_dir,
                wps_template=wps_template,
                output_interval=output_interval,
                submit=submit,
                wait=wait,
                force=force,
                poll_seconds=poll_seconds,
            )
        )
    if manifest:
        write_manifest(manifest, pairs)
        print(f"OK: manifesto BFLOW escrito: {manifest}")
    return pairs
