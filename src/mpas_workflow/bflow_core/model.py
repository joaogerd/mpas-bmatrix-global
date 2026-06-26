from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from ..forecast import bflow_file

TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"


@dataclass(frozen=True)
class BflowPair:
    valid_time: str
    f048: Path
    f024: Path


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def compact_time(value: str) -> str:
    return parse_time(value).strftime("%Y%m%d%H")


def iter_valid_times(start: str, end: str, step_hours: int) -> Iterator[str]:
    if step_hours <= 0:
        raise SystemExit("ERRO: --valid-interval-hours deve ser positivo.")
    current = parse_time(start)
    last = parse_time(end)
    step = timedelta(hours=step_hours)
    while current <= last:
        yield format_time(current)
        current += step


def default_workspace(config, start_valid_time: str, end_valid_time: str) -> Path:
    nproc = int(config["mesh"].get("nproc", 64))
    return (
        Path(config["project"]["work_root"])
        / "bmatrix"
        / "bflow_preprocessing"
        / f"np{nproc}_{compact_time(start_valid_time)}_{compact_time(end_valid_time)}"
    )


def build_pairs_from_range(
    config,
    start_valid_time: str,
    end_valid_time: str,
    step_hours: int,
    dt: int,
) -> list[BflowPair]:
    pairs: list[BflowPair] = []
    for valid_time in iter_valid_times(start_valid_time, end_valid_time, step_hours):
        valid = parse_time(valid_time)
        old_init = format_time(valid - timedelta(hours=48))
        new_init = format_time(valid - timedelta(hours=24))
        pairs.append(
            BflowPair(
                valid_time=valid_time,
                f048=bflow_file(config, old_init, 48, dt),
                f024=bflow_file(config, new_init, 24, dt),
            )
        )
    return pairs
