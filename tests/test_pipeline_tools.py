from pathlib import Path

import pytest

from mpas_workflow import bcov_pipeline
from mpas_workflow.dirac_summary import summarize_dirac_file


def test_pipeline_resolves_default_workspaces(tmp_path):
    config = {"project": {"work_root": str(tmp_path)}}
    args = type(
        "Args",
        (),
        {
            "bflow_workspace": str(tmp_path / "bmatrix" / "bflow_preprocessing" / "np128_case"),
            "vbal_workspace": None,
            "hdiag_workspace": None,
            "nicas_workspace": None,
            "so_workspace": None,
            "dirac_workspace": None,
        },
    )()

    workspaces = bcov_pipeline.resolve_workspaces(config, args)

    assert workspaces["vbal"] == tmp_path / "bmatrix" / "covariance" / "vbal" / "np128_case"
    assert workspaces["hdiag"] == tmp_path / "bmatrix" / "covariance" / "hdiag" / "np128_case"
    assert workspaces["nicas"] == tmp_path / "bmatrix" / "covariance" / "nicas" / "np128_case"
    assert workspaces["so"] == tmp_path / "bmatrix" / "covariance" / "so" / "np128_case"
    assert workspaces["dirac"] == tmp_path / "bmatrix" / "covariance" / "dirac" / "np128_case"


def test_pipeline_validate_calls_steps_in_order(tmp_path, monkeypatch):
    calls = []
    for name in ["vbal", "hdiag", "nicas", "dirac"]:
        monkeypatch.setattr(
            bcov_pipeline,
            f"validate_{name}",
            lambda workspace, name=name: calls.append((name, Path(workspace).name)),
        )
    monkeypatch.setattr(
        bcov_pipeline,
        "validate_so",
        lambda workspace, variant="default": calls.append((f"so:{variant}", Path(workspace).name)),
    )

    bcov_pipeline.validate_pipeline(
        {
            "vbal": tmp_path / "vbal",
            "hdiag": tmp_path / "hdiag",
            "nicas": tmp_path / "nicas",
            "so": tmp_path / "so",
            "dirac": tmp_path / "dirac",
        }
    )

    assert calls == [
        ("vbal", "vbal"),
        ("hdiag", "hdiag"),
        ("nicas", "nicas"),
        ("so:default", "so"),
        ("dirac", "dirac"),
    ]


def test_dirac_summary_reports_nonzero_numeric_variables(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    path = tmp_path / "mpas.dirac.nc"
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("nCells", 3)
        variable = dataset.createVariable("temperature", "f4", ("nCells",))
        variable[:] = [0.0, 2.0, -2.0]

    rows = summarize_dirac_file(path)

    row = next(item for item in rows if item["variable"] == "temperature")
    assert row["shape"] == (3,)
    assert row["min"] == pytest.approx(-2.0)
    assert row["max"] == pytest.approx(2.0)
    assert row["absmax"] == pytest.approx(2.0)
    assert row["rms"] == pytest.approx((8.0 / 3.0) ** 0.5)
    assert row["nonzero"] is True
