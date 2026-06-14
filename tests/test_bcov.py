import pytest

from mpas_workflow.bcov import (
    link_static_files,
    require_hdiag_members,
    validate_hdiag,
    validate_vbal,
    write_hdiag_yaml,
    write_vbal_yaml,
)


def test_write_vbal_yaml_matches_toolbox_member_syntax(tmp_path):
    output = tmp_path / "run_vbal.yaml"

    write_vbal_yaml(output, nmembers=3, date="2026-06-10T00:00:00Z")

    text = output.read_text()
    assert "filename: ../samples/PTB_f48mf24_%mem%.nc" in text
    assert "pattern: '%mem%'" in text
    assert "nmembers: 3" in text
    assert "iterative ensemble loading: false" in text
    assert "output ensemble:" not in text


def test_link_static_files_uses_stream_template_filename(tmp_path):
    source = tmp_path / "source"
    run_dir = tmp_path / "run"
    source.mkdir()
    run_dir.mkdir()
    for name in ["graph.info", "x1.10242.invariant.nc", "FULL_f24.nc", "mpasout.nc"]:
        (source / name).touch()
    for name in ["namelist.atmosphere_240km", "streams.atmosphere_240km"]:
        (source / name).touch()
    (source / "namelist.atmosphere_240km").write_text(
        "&nhyd_model\n    config_start_time = '2018-04-15_00:00:00'\n/\n"
    )

    config = {
        "mesh": {
            "name": "x1.10242",
            "graph": str(source / "graph.info"),
            "partitions_dir": str(source),
            "nproc": 128,
        },
        "static": {
            "invariant": str(source / "x1.10242.invariant.nc"),
            "tutorial_physics_files": str(source),
        },
    }

    link_static_files(
        config,
        run_dir,
        source / "FULL_f24.nc",
        source / "mpasout.nc",
        "2026-06-10_00:00:00",
    )

    template = run_dir / "templateFields.10242.nc"
    assert template.is_symlink()
    assert template.resolve() == source / "mpasout.nc"
    assert "config_start_time = '2026-06-10_00:00:00'" in (
        run_dir / "namelist.atmosphere_240km"
    ).read_text()


def write_ranked_products(run_dir, prefix, count=2):
    for rank in range(1, count + 1):
        (run_dir / f"{prefix}_local_{count:06d}-{rank:06d}.nc").touch()


def test_validate_vbal_prints_diagnostics_when_products_are_missing(tmp_path, capsys):
    run_dir = tmp_path / "VBAL"
    samples = tmp_path / "samples"
    run_dir.mkdir()
    samples.mkdir()
    (samples / "PTB_f48mf24_001.nc").touch()
    (run_dir / "run_vbal.runlog").write_text("CRITICAL ERROR\n")
    (run_dir / "stdout.log").write_text("toolbox output\n")
    (run_dir / "stderr.log").write_text("MPI_Abort\n")

    with pytest.raises(SystemExit):
        validate_vbal(tmp_path)

    output = capsys.readouterr().out
    assert "produto VBAL ausente" in output
    assert "=== VBAL diagnostics ===" in output
    assert "toolbox output" in output
    assert "MPI_Abort" in output
    assert "run_vbal.runlog" in output
    assert "arquivos gerados" in output


def test_validate_vbal_accepts_calibration_products_without_unbalanced_samples(tmp_path, capsys):
    run_dir = tmp_path / "VBAL"
    run_dir.mkdir()
    (run_dir / "mpas_sampling.nc").touch()
    (run_dir / "mpas_vbal.nc").touch()
    write_ranked_products(run_dir, "mpas_sampling")
    write_ranked_products(run_dir, "mpas_vbal")
    (run_dir / "run_vbal.runlog").write_text(
        "Run: Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0\n"
    )

    assert validate_vbal(tmp_path)

    output = capsys.readouterr().out
    assert "SUCCESS: VBAL validado." in output
    assert "LEGACY_UNBALANCED_SAMPLES=0" in output
    assert "Isso e esperado neste fluxo" in output


def test_write_hdiag_yaml_reads_original_ptbs_and_vbal(tmp_path):
    output = tmp_path / "run_hdiag.yaml"

    write_hdiag_yaml(output, nmembers=3, date="2026-06-10T00:00:00Z")

    text = output.read_text()
    assert "saber block name: BUMP_NICAS" in text
    assert "saber block name: BUMP_VerticalBalance" in text
    assert "read:" in text
    assert "read local sampling: true" in text
    assert "read vertical balance: true" in text
    assert "data directory: ../vbal" in text
    assert "files prefix: mpas" in text
    assert "filename: ../samples/PTB_f48mf24_%mem%.nc" in text
    assert "iterative ensemble loading: true" in text
    assert "samplesUnbalanced" not in text


def test_require_hdiag_members_rejects_three_members(tmp_path):
    with pytest.raises(SystemExit, match="pelo menos 4 membros"):
        require_hdiag_members([tmp_path / f"member_{index}.nc" for index in range(3)])


def test_validate_hdiag_reports_bump_minimum_ensemble(tmp_path, capsys):
    run_dir = tmp_path / "HDIAG"
    run_dir.mkdir()
    (run_dir / "run_hdiag.runlog").write_text(
        'Info: Ensemble sizes:{"total ensemble size":3,"sub-ensembles":1}\n'
    )
    (run_dir / "stdout.log").write_text(
        "!!! ABORT in nam_check: ens_ne/ens_nsub should be larger than 3\n"
    )

    with pytest.raises(SystemExit):
        validate_hdiag(tmp_path)

    output = capsys.readouterr().out
    assert "=== HDIAG diagnostics ===" in output
    assert "ens_ne/ens_nsub should be larger than 3" in output
    assert "CAUSA IDENTIFICADA" in output
