"""Execute a resumable range of MPAS init + forecast cycles.

This module deliberately reuses the existing ``ungrib``, ``init`` and
``forecast`` implementations.  It does not submit dependent PBS jobs in a
single burst: with ``--submit --wait`` it validates each init before preparing
and submitting its forecast, which keeps failures local to one analysis time
and makes resume deterministic.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .config import load_config
from .forecast import bflow_file, prepare_forecast, restart_file, submit_forecast
from .mpas_init import (
    init_file,
    init_validation_error,
    prepare_init,
    submit_init,
    validate_init,
)
from .shell import wait_for_pbs_job
from .wps import run_ungrib, ungrib_run_dir


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def parse_time(value: str) -> datetime:
    """Parse a workflow timestamp in the canonical MPAS form."""
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except ValueError as exc:
        raise SystemExit(
            f"ERRO: horário inválido {value!r}; use YYYY-MM-DD_HH:MM:SS."
        ) from exc


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def iter_init_times(start: str, end: str, interval_hours: int) -> Iterable[str]:
    """Yield inclusive analysis times in chronological order."""
    if interval_hours <= 0:
        raise SystemExit("ERRO: --interval-hours deve ser positivo.")

    current = parse_time(start)
    last = parse_time(end)
    if last < current:
        raise SystemExit("ERRO: --end deve ser maior ou igual a --start.")

    step = timedelta(hours=interval_hours)
    while current <= last:
        yield format_time(current)
        current += step


def _slug(value: str) -> str:
    return value.replace("-", "").replace(":", "").replace("_", "T")


def default_manifest_path(
    config: Dict[str, Any], start: str, end: str, lead_hours: int, dt: int
) -> Path:
    """Return a stable manifest name under the configured work root."""
    filename = (
        f"cycle-range_{_slug(start)}_{_slug(end)}_"
        f"f{int(lead_hours):03d}_dt{int(dt)}.json"
    )
    return Path(config["project"]["work_root"]) / "cycle-manifests" / filename


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_manifest(path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return {"metadata": metadata, "cycles": {}}

    try:
        manifest = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERRO: manifesto inválido: {path}: {exc}") from exc

    existing = manifest.get("metadata", {})
    incompatible = {
        key: (existing.get(key), value)
        for key, value in metadata.items()
        if key in existing and existing.get(key) != value
    }
    if incompatible:
        detail = ", ".join(
            f"{key}: manifesto={old!r}, execução={new!r}"
            for key, (old, new) in incompatible.items()
        )
        raise SystemExit(
            "ERRO: o manifesto pertence a uma configuração de ciclo diferente. " + detail
        )

    manifest["metadata"] = {**existing, **metadata}
    manifest.setdefault("cycles", {})
    return manifest


def _write_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    """Atomically persist progress, so a login interruption does not corrupt it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = _now()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _entry(manifest: Dict[str, Any], init_time: str) -> Dict[str, Any]:
    return manifest["cycles"].setdefault(
        init_time,
        {
            "init_time": init_time,
            "status": "pending",
            "history": [],
        },
    )


def _record(entry: Dict[str, Any], status: str, **details: Any) -> None:
    event = {"at": _now(), "status": status, **details}
    entry.update(details)
    entry["status"] = status
    entry.setdefault("history", []).append(event)


def forecast_validation_error(
    config: Dict[str, Any], init_time: str, lead_hours: int, dt: int
) -> Optional[str]:
    """Return a concise error when forecast products are incomplete."""
    expected = [
        (restart_file(config, init_time, lead_hours, dt), "restart"),
        (bflow_file(config, init_time, lead_hours, dt), "da_state"),
    ]
    missing = [f"{label}: {path}" for path, label in expected if not path.exists()]
    if missing:
        return "saídas de forecast ausentes: " + "; ".join(missing)
    return None


def _cycle_state(
    config: Dict[str, Any], init_time: str, lead_hours: int, dt: int
) -> str:
    if forecast_validation_error(config, init_time, lead_hours, dt) is None:
        return "forecast_complete"
    if init_validation_error(config, init_time) is None:
        return "init_complete"
    return "pending"


def run_one_cycle(
    config: Dict[str, Any],
    init_time: str,
    lead_hours: int,
    dt: int,
    submit: bool,
    wait: bool,
    download: bool,
    poll_seconds: int,
    force_forecast: bool,
    entry: Dict[str, Any],
) -> bool:
    """Advance one analysis time and return ``True`` only when fNNN is valid.

    When ``submit`` is used without ``wait``, only the first missing stage is
    submitted and this function returns ``False``.  Re-running the same command
    resumes from the file validation checks rather than repeating completed work.
    """
    init_error = init_validation_error(config, init_time)
    if init_error is None:
        validate_init(config, init_time)
        _record(entry, "init_complete", init_file=str(init_file(config, init_time)))
    else:
        _record(entry, "init_preparing", detail=init_error)
        run_ungrib(config, init_time, download=download)
        wps_file = ungrib_run_dir(config, init_time) / f"FILE:{init_time[:13]}"
        prepare_init(config, init_time, wps_file)
        _record(entry, "init_prepared", wps_file=str(wps_file))

        if not submit:
            return False

        jobid = submit_init(config, init_time)
        _record(entry, "init_submitted", init_jobid=jobid)
        print(f"Job de init submetido para {init_time}: {jobid}")
        if not wait:
            return False

        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
        validate_init(config, init_time, jobid=jobid)
        _record(entry, "init_complete", init_file=str(init_file(config, init_time)))

    forecast_error = forecast_validation_error(config, init_time, lead_hours, dt)
    if forecast_error is None and not force_forecast:
        _record(
            entry,
            "forecast_complete",
            restart=str(restart_file(config, init_time, lead_hours, dt)),
            da_state=str(bflow_file(config, init_time, lead_hours, dt)),
        )
        return True

    if force_forecast:
        print(f"Forçando forecast f{lead_hours:03d} para {init_time}.")

    _record(entry, "forecast_preparing", detail=forecast_error or "forçado")
    prepare_forecast(config, init_time, lead_hours, dt)
    _record(entry, "forecast_prepared")

    if not submit:
        return False

    jobid = submit_forecast(config, init_time, lead_hours, dt)
    _record(entry, "forecast_submitted", forecast_jobid=jobid)
    print(f"Job de forecast f{lead_hours:03d} submetido para {init_time}: {jobid}")
    if not wait:
        return False

    wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    forecast_error = forecast_validation_error(config, init_time, lead_hours, dt)
    if forecast_error is not None:
        raise SystemExit(
            f"ERRO: forecast f{lead_hours:03d} terminou, mas {forecast_error}."
        )

    _record(
        entry,
        "forecast_complete",
        restart=str(restart_file(config, init_time, lead_hours, dt)),
        da_state=str(bflow_file(config, init_time, lead_hours, dt)),
    )
    print(f"OK: ciclo concluído: {init_time} f{lead_hours:03d}")
    return True


def run_range(
    config: Dict[str, Any],
    start: str,
    end: str,
    interval_hours: int,
    lead_hours: int,
    dt: int,
    submit: bool,
    wait: bool,
    download: bool,
    poll_seconds: int,
    force_forecast: bool,
    manifest_path: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run or inspect a contiguous range of analysis times."""
    if wait and not submit:
        raise SystemExit("ERRO: --wait exige --submit.")
    if lead_hours <= 0:
        raise SystemExit("ERRO: --lead-hours deve ser positivo.")

    metadata = {
        "start": start,
        "end": end,
        "interval_hours": int(interval_hours),
        "lead_hours": int(lead_hours),
        "dt": int(dt),
        "work_root": str(config["project"]["work_root"]),
    }
    manifest = _load_manifest(manifest_path, metadata)

    for init_time in iter_init_times(start, end, interval_hours):
        entry = _entry(manifest, init_time)
        print("\n=== MPAS cycle ===")
        print(f"INIT_TIME={init_time}")
        print(f"LEAD_HOURS={lead_hours}")
        print(f"DT={dt}")

        if dry_run:
            _record(entry, _cycle_state(config, init_time, lead_hours, dt))
            _write_manifest(manifest_path, manifest)
            continue

        try:
            complete = run_one_cycle(
                config=config,
                init_time=init_time,
                lead_hours=lead_hours,
                dt=dt,
                submit=submit,
                wait=wait,
                download=download,
                poll_seconds=poll_seconds,
                force_forecast=force_forecast,
                entry=entry,
            )
        except BaseException as exc:
            _record(entry, "failed", error=str(exc))
            _write_manifest(manifest_path, manifest)
            raise

        _write_manifest(manifest_path, manifest)
        if not complete:
            print(
                "Ciclo ainda não concluído. O manifesto foi atualizado; "
                "execute novamente o mesmo comando para retomar."
            )
            break

    return manifest


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mpaswf-cycle-range",
        description="Executa uma faixa resumível de ciclos MPAS init + forecast.",
    )
    parser.add_argument("--config", default="configs/jaci-x1.10242.yaml")
    parser.add_argument("--start", required=True, help="primeiro INIT_TIME")
    parser.add_argument("--end", required=True, help="último INIT_TIME")
    parser.add_argument("--interval-hours", type=int, default=24)
    parser.add_argument("--lead-hours", type=int, default=48)
    parser.add_argument("--dt", type=int)
    parser.add_argument("--submit", action="store_true", help="submete init/forecast ao PBS")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="aguarda e valida cada job antes de avançar para o próximo estágio/ciclo",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="não baixa GFS ausente; falha explicitamente se o GRIB2 não estiver disponível",
    )
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument(
        "--force-forecast",
        action="store_true",
        help="refaz o forecast mesmo quando restart e da_state já existem",
    )
    parser.add_argument("--manifest", help="caminho opcional para o manifesto JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="somente registra o estado atual de cada ciclo; não prepara nem submete jobs",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = parser().parse_args(argv)
    config = load_config(args.config)
    dt = int(args.dt or config["runtime"]["config_dt"])
    manifest_path = Path(args.manifest) if args.manifest else default_manifest_path(
        config, args.start, args.end, args.lead_hours, dt
    )

    manifest = run_range(
        config=config,
        start=args.start,
        end=args.end,
        interval_hours=args.interval_hours,
        lead_hours=args.lead_hours,
        dt=dt,
        submit=args.submit,
        wait=args.wait,
        download=not args.no_download,
        poll_seconds=args.poll_seconds,
        force_forecast=args.force_forecast,
        manifest_path=manifest_path,
        dry_run=args.dry_run,
    )

    completed = sum(
        1 for entry in manifest["cycles"].values() if entry.get("status") == "forecast_complete"
    )
    total = len(list(iter_init_times(args.start, args.end, args.interval_hours)))
    print(f"MANIFEST={manifest_path}")
    print(f"SUMMARY: {completed}/{total} forecasts f{args.lead_hours:03d} concluídos.")


if __name__ == "__main__":
    main()
