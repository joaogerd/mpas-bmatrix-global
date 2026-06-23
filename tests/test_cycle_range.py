import json
from pathlib import Path

import pytest

from mpas_workflow.cycle_range import (
    default_manifest_path,
    iter_init_times,
    parse_time,
    run_range,
)


def test_iter_init_times_is_inclusive_and_regular():
    assert list(
        iter_init_times(
            "2026-06-01_00:00:00",
            "2026-06-02_00:00:00",
            12,
        )
    ) == [
        "2026-06-01_00:00:00",
        "2026-06-01_12:00:00",
        "2026-06-02_00:00:00",
    ]


def test_iter_init_times_rejects_invalid_ranges():
    with pytest.raises(SystemExit, match="--end"):
        list(iter_init_times("2026-06-02_00:00:00", "2026-06-01_00:00:00", 24))

    with pytest.raises(SystemExit, match="interval-hours"):
        list(iter_init_times("2026-06-01_00:00:00", "2026-06-02_00:00:00", 0))


def test_parse_time_requires_workflow_format():
    with pytest.raises(SystemExit, match="YYYY-MM-DD_HH:MM:SS"):
        parse_time("2026-06-01T00:00:00")


def test_default_manifest_path_uses_work_root_and_run_identity(tmp_path):
    config = {"project": {"work_root": str(tmp_path)}}
    path = default_manifest_path(
        config,
        "2026-06-01_00:00:00",
        "2026-06-30_18:00:00",
        48,
        1200,
    )

    assert path == (
        tmp_path
        / "cycle-manifests"
        / "cycle-range_20260601T000000_20260630T180000_f048_dt1200.json"
    )


def test_dry_run_writes_a_resumable_manifest(tmp_path):
    config = {
        "project": {"work_root": str(tmp_path)},
        "runtime": {"config_dt": 1200},
    }
    manifest_path = tmp_path / "range.json"

    manifest = run_range(
        config=config,
        start="2026-06-01_00:00:00",
        end="2026-06-02_00:00:00",
        interval_hours=24,
        lead_hours=48,
        dt=1200,
        submit=False,
        wait=False,
        download=False,
        poll_seconds=1,
        force_forecast=False,
        manifest_path=manifest_path,
        dry_run=True,
    )

    assert set(manifest["cycles"]) == {
        "2026-06-01_00:00:00",
        "2026-06-02_00:00:00",
    }
    saved = json.loads(manifest_path.read_text())
    assert saved["metadata"]["lead_hours"] == 48
    assert saved["metadata"]["dt"] == 1200
