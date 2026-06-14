from pathlib import Path

import pytest

import mpas_workflow.bcov as bcov
from mpas_workflow.bcov import (
    NICAS_VARIABLES,
    link_static_files,
    nicas_home_failure_files,
    require_hdiag_members,
    submit_nicas,
    submit_nicas_variable,
    validate_hdiag,
    validate_nicas,
    validate_vbal,
    write_hdiag_yaml,
    write_nicas_yaml,
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


def test_write_nicas_yaml_reads_hdiag_correlations(tmp_path):
    output = tmp_path / "run_nicas.yaml"

    write_nicas_yaml(
        output,
        variable="temperature",
        date="2026-06-10T00:00:00Z",
        nvertlevels=55,
    )

    text = output.read_text()
    assert "saber block name: BUMP_NICAS" in text
    assert "compute nicas: true" in text
    assert "write local nicas: true" in text
    assert "write global nicas: true" in text
    assert "filename: ../mpas.cor_rh.nc" in text
    assert "filename: ../mpas.cor_rv.nc" in text
    assert "variable: temperature" in text
    assert "level: 36" in text
    assert "BUMP_VerticalBalance" not in text
    assert "PTB_f48mf24" not in text


def test_validate_nicas_accepts_split_and_merged_products(tmp_path):
    for variable in NICAS_VARIABLES:
        run_dir = tmp_path / variable
        run_dir.mkdir()
        (run_dir / "run_nicas.runlog").write_text(
            "Run: Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0\n"
        )
        for name in ["mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
            (run_dir / name).touch()
        write_ranked_products(run_dir, "mpas_nicas")
        write_ranked_products(run_dir, "mpas_nicas_grids")

    merge_dir = tmp_path / "merge"
    merge_dir.mkdir()
    for name in ["merge.done", "mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        (merge_dir / name).touch()
    write_ranked_products(merge_dir, "mpas_nicas")
    write_ranked_products(merge_dir, "mpas_nicas_grids")

    assert validate_nicas(tmp_path)


def write_nicas_variable_products(run_dir, count=2):
    (run_dir / "run_nicas.runlog").write_text(
        "Run: Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0\n"
    )
    for name in ["mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        (run_dir / name).touch()
    write_ranked_products(run_dir, "mpas_nicas", count=count)
    write_ranked_products(run_dir, "mpas_nicas_grids", count=count)


def test_submit_nicas_is_sequential_by_default(tmp_path, monkeypatch):
    variables = ["stream_function", "temperature"]
    for variable in variables:
        (tmp_path / variable).mkdir()
    (tmp_path / "merge").mkdir()

    submitted = []
    jobs = {}

    def fake_qsub(pbs_file, cwd):
        jobid = f"job{len(submitted) + 1}"
        submitted.append((pbs_file, Path(cwd).name))
        jobs[jobid] = Path(cwd)
        return jobid

    def fake_wait(jobid, poll_seconds):
        write_nicas_variable_products(jobs[jobid])

    monkeypatch.setattr(bcov, "NICAS_VARIABLES", variables)
    monkeypatch.setattr(bcov, "qsub", fake_qsub)
    monkeypatch.setattr(bcov, "wait_for_pbs_job", fake_wait)

    assert submit_nicas(tmp_path) == "job3"
    assert submitted == [
        ("qsub_nicas.bash", "stream_function"),
        ("qsub_nicas.bash", "temperature"),
        ("qsub_nicas_merge.bash", "merge"),
    ]


def test_submit_nicas_parallel_preserves_dependency_mode(tmp_path, monkeypatch):
    variables = ["stream_function", "temperature"]
    for variable in variables:
        (tmp_path / variable).mkdir()
    (tmp_path / "merge").mkdir()

    submitted = []
    monkeypatch.setattr(bcov, "NICAS_VARIABLES", variables)
    monkeypatch.setattr(
        bcov,
        "qsub",
        lambda pbs_file, cwd: submitted.append(Path(cwd).name) or f"job{len(submitted)}",
    )
    monkeypatch.setattr(
        bcov,
        "_qsub_afterok",
        lambda pbs_file, cwd, jobids: submitted.append(("merge", jobids)) or "mergejob",
    )
    monkeypatch.setattr(
        bcov,
        "wait_for_pbs_job",
        lambda *args, **kwargs: pytest.fail("parallel sem --wait não deve aguardar"),
    )

    assert submit_nicas(tmp_path, parallel=True) == "mergejob"
    assert submitted == [
        "stream_function",
        "temperature",
        ("merge", ["job1", "job2"]),
    ]


def test_nicas_home_failure_detection_and_retry(tmp_path, monkeypatch, capsys):
    attempts = []

    def fake_qsub(pbs_file, cwd):
        attempts.append(1)
        return f"job{len(attempts)}"

    def fake_wait(jobid, poll_seconds):
        if jobid == "job1":
            (tmp_path / "NICAS_temperature.o123").write_text(
                "Could not chdir to home directory\n"
            )
        else:
            write_nicas_variable_products(tmp_path)

    monkeypatch.setattr(bcov, "qsub", fake_qsub)
    monkeypatch.setattr(bcov, "wait_for_pbs_job", fake_wait)

    assert submit_nicas_variable("temperature", tmp_path, retries=2, poll_seconds=1) == "job2"
    assert len(attempts) == 2
    assert "Falha PBS/HOME na JACI, ressubmetendo variável temperature." in (
        capsys.readouterr().out
    )


def test_nicas_home_failure_retry_is_limited(tmp_path, monkeypatch):
    attempts = []
    monkeypatch.setattr(
        bcov,
        "qsub",
        lambda pbs_file, cwd: attempts.append(1) or f"job{len(attempts)}",
    )
    monkeypatch.setattr(
        bcov,
        "wait_for_pbs_job",
        lambda jobid, poll_seconds: (tmp_path / f"NICAS_temperature.o{jobid}").write_text(
            "Could not chdir to home directory\n"
        ),
    )

    with pytest.raises(SystemExit, match="após 2 retries"):
        submit_nicas_variable("temperature", tmp_path, retries=2, poll_seconds=1)
    assert len(attempts) == 3


def test_validate_nicas_warns_for_stale_pbs_home_failure_with_complete_products(
    tmp_path, capsys
):
    for variable in NICAS_VARIABLES:
        run_dir = tmp_path / variable
        run_dir.mkdir()
        write_nicas_variable_products(run_dir)
    (tmp_path / NICAS_VARIABLES[0] / "NICAS.o123").write_text(
        "Could not chdir to home directory\n"
    )

    merge_dir = tmp_path / "merge"
    merge_dir.mkdir()
    for name in ["merge.done", "mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        (merge_dir / name).touch()
    write_ranked_products(merge_dir, "mpas_nicas")
    write_ranked_products(merge_dir, "mpas_nicas_grids")
    (merge_dir / "NICASmerge.o456").write_text("Could not chdir to home directory\n")

    assert validate_nicas(tmp_path)
    output = capsys.readouterr().out
    assert "WARNING: stream_function: stale PBS output" in output
    assert "WARNING: merge: stale PBS output" in output
    assert "SUCCESS: NICAS split/merge validado." in output


def test_validate_nicas_reports_pbs_home_failure_when_products_are_missing(
    tmp_path, capsys
):
    for variable in NICAS_VARIABLES:
        run_dir = tmp_path / variable
        run_dir.mkdir()
        write_nicas_variable_products(run_dir)
    broken = tmp_path / NICAS_VARIABLES[0]
    (broken / "mpas_nicas.nc").unlink()
    (broken / "NICAS.o123").write_text("Could not chdir to home directory\n")
    (tmp_path / "merge").mkdir()

    with pytest.raises(SystemExit):
        validate_nicas(tmp_path)
    assert "falha PBS/HOME: Could not chdir to home directory" in capsys.readouterr().out


def test_nicas_pbs_avoids_unsupported_jaci_directives(tmp_path, monkeypatch):
    install = tmp_path / "install"
    exe = install / "bin" / "mpasjedi_error_covariance_toolbox.x"
    exe.parent.mkdir(parents=True)
    exe.touch()
    config = {
        "project": {"project_root": str(tmp_path)},
        "environment": {"loader": "load.sh"},
        "install": {"root": str(install)},
        "mesh": {"nproc": 2},
        "pbs": {"queue": "queue", "walltime_short": "00:10:00"},
    }
    run_dir = tmp_path / "temperature"
    run_dir.mkdir()

    bcov.write_nicas_pbs(config, run_dir, "temperature")
    bcov.write_nicas_merge_files(config, tmp_path)

    texts = [
        (run_dir / "qsub_nicas.bash").read_text(),
        (tmp_path / "merge" / "qsub_nicas_merge.bash").read_text(),
    ]
    assert all("#PBS -d" not in text for text in texts)
    assert all("%1" not in text for text in texts)
