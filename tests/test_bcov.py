from pathlib import Path

import pytest

import mpas_workflow.bcov as bcov
from mpas_workflow.bcov import (
    NICAS_VARIABLES,
    SO_BACKGROUND_VARIABLES,
    create_so_background,
    link_static_files,
    link_so_support,
    require_hdiag_members,
    submit_nicas,
    submit_nicas_variable,
    submit_so,
    validate_dirac,
    validate_hdiag,
    validate_nicas,
    validate_so,
    validate_so_background,
    validate_vbal,
    write_dirac_pbs,
    write_dirac_yaml,
    write_hdiag_yaml,
    write_nicas_yaml,
    write_so_pbs,
    write_so_t_only_diagnostic_pbs,
    write_so_yaml,
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


def test_write_so_yaml_reads_nicas_stddev_and_vbal(tmp_path):
    output = tmp_path / "run_SO.yaml"
    nicas = tmp_path / "nicas" / "merge"
    stddev = tmp_path / "hdiag" / "HDIAG" / "mpas.stddev.nc"
    vbal = tmp_path / "vbal" / "VBAL"

    write_so_yaml(
        output,
        date="2026-06-10T00:00:00Z",
        nicas_dir=nicas,
        stddev_file=stddev,
        vbal_dir=vbal,
    )

    text = output.read_text()
    assert "cost type: 3D-Var" in text
    assert "saber block name: BUMP_NICAS" in text
    assert "read local nicas: true" in text
    assert f"data directory: {nicas}" in text
    assert "saber block name: StdDev" in text
    assert f"filename: {stddev}" in text
    assert "saber block name: BUMP_VerticalBalance" in text
    assert f"data directory: {vbal}" in text
    assert "read local sampling: true" in text
    assert "read vertical balance: true" in text
    assert "linear variable change name: Control2Analysis" in text
    assert "obsfile: ./obsout_SO_T.h5" in text
    assert "obsfile: ./obsout_SO_U.h5" in text
    assert text.count("vertical coordinate: air_pressure") == 2
    assert text.count("interpolation method: log-linear") == 2
    assert "stream name: background" not in text
    assert "filename: ./bg_so.nc" in text
    assert "transform model to analysis: false" in text
    assert "filename: ./bg.nc" not in text


@pytest.mark.parametrize(
    ("variant", "present", "absent"),
    [
        ("t-only", "name: SO_T", "name: SO_U"),
        ("u-only", "name: SO_U", "name: SO_T"),
    ],
)
def test_write_so_yaml_selects_diagnostic_observer(
    tmp_path, variant, present, absent
):
    output = tmp_path / f"run_SO_{variant}.yaml"

    write_so_yaml(
        output,
        date="2026-06-10T00:00:00Z",
        nicas_dir=tmp_path / "nicas",
        stddev_file=tmp_path / "mpas.stddev.nc",
        vbal_dir=tmp_path / "vbal",
        variant=variant,
    )

    text = output.read_text()
    assert present in text
    assert absent not in text


def test_link_so_support_returns_template_without_linking_background(tmp_path):
    hdiag_run = tmp_path / "HDIAG"
    run_dir = tmp_path / "SO"
    hdiag_run.mkdir()
    run_dir.mkdir()
    for name in [
        "bg.nc",
        "templateFields.10242.nc",
        "namelist.atmosphere_240km",
        "streams.atmosphere_240km",
    ]:
        (hdiag_run / name).touch()

    template = link_so_support(hdiag_run, run_dir)

    assert template == hdiag_run / "templateFields.10242.nc"
    assert not (run_dir / "bg.nc").exists()


def test_create_so_background_adds_required_derived_variables(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    source = tmp_path / "templateFields.10242.nc"
    output = tmp_path / "bg_so.nc"
    with netCDF4.Dataset(source, "w") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 1)
        dataset.createDimension("nEdges", 1)
        dataset.createDimension("nVertLevels", 1)
        cell_dims = ("Time", "nCells", "nVertLevels")
        edge_dims = ("Time", "nEdges", "nVertLevels")
        values = {
            "surface_pressure": (cell_dims, 100000.0),
            "uReconstructMeridional": (cell_dims, 1.0),
            "uReconstructZonal": (cell_dims, 2.0),
            "theta": (cell_dims, 300.0),
            "rho": (cell_dims, 1.0),
            "u": (edge_dims, 3.0),
            "qv": (cell_dims, 0.01),
            "pressure_base": (cell_dims, 90000.0),
            "pressure_p": (cell_dims, 10000.0),
        }
        for name, (dimensions, value) in values.items():
            dataset.createVariable(name, "f4", dimensions)[:] = value

    create_so_background(source, output)

    assert validate_so_background(output)
    with netCDF4.Dataset(output) as dataset:
        assert set(SO_BACKGROUND_VARIABLES) <= set(dataset.variables)
        assert dataset.variables["pressure"][0, 0, 0] == pytest.approx(100000.0)
        assert dataset.variables["air_pressure"][0, 0, 0] == pytest.approx(100000.0)
        assert dataset.variables["air_pressure_at_surface"][0, 0] == pytest.approx(
            100000.0
        )
        assert dataset.variables["temperature"][0, 0, 0] == pytest.approx(300.0)
        assert dataset.variables["air_temperature"][0, 0, 0] == pytest.approx(
            300.0
        )
        assert dataset.variables["spechum"][0, 0, 0] == pytest.approx(
            0.01 / 1.01
        )
        assert dataset.variables["eastward_wind"][0, 0, 0] == pytest.approx(2.0)
        assert dataset.variables["northward_wind"][0, 0, 0] == pytest.approx(1.0)


def test_validate_so_background_rejects_missing_derived_variables(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    background = tmp_path / "bg_so.nc"
    with netCDF4.Dataset(background, "w"):
        pass

    with pytest.raises(SystemExit, match="spechum.*temperature.*pressure"):
        validate_so_background(background)


def test_write_so_pbs_uses_variational_and_jaci_workdir(tmp_path):
    install = tmp_path / "install"
    exe = install / "bin" / "mpasjedi_variational.x"
    exe.parent.mkdir(parents=True)
    exe.touch()
    run_dir = tmp_path / "SO"
    run_dir.mkdir()
    config = {
        "project": {"project_root": str(tmp_path)},
        "environment": {"loader": "load.sh"},
        "install": {"root": str(install)},
        "mesh": {"nproc": 2},
        "pbs": {"queue": "queue", "walltime_short": "00:10:00"},
    }

    write_so_pbs(config, run_dir)

    text = (run_dir / "qsub_so.bash").read_text()
    assert str(exe) in text
    assert f'cd "{run_dir}"' in text
    assert "GFORTRAN_CONVERT_UNIT=big_endian:101-200" in text
    assert "./run_SO.yaml ./run_SO.runlog" in text
    assert "#PBS -d" not in text
    assert "#PBS -J" not in text


def test_write_so_pbs_uses_variant_artifacts(tmp_path):
    install = tmp_path / "install"
    exe = install / "bin" / "mpasjedi_variational.x"
    exe.parent.mkdir(parents=True)
    exe.touch()
    run_dir = tmp_path / "SO"
    run_dir.mkdir()
    config = {
        "project": {"project_root": str(tmp_path)},
        "environment": {"loader": "load.sh"},
        "install": {"root": str(install)},
        "mesh": {"nproc": 2},
        "pbs": {"queue": "queue", "walltime_short": "00:10:00"},
    }

    write_so_pbs(config, run_dir, variant="t-only")

    text = (run_dir / "qsub_so_t_only.bash").read_text()
    assert "./run_SO_t_only.yaml ./run_SO_t_only.runlog" in text
    assert "> stdout_t_only.log 2> stderr_t_only.log" in text
    assert "ulimit -c unlimited" not in text
    assert "GFORTRAN_ERROR_BACKTRACE" not in text


def test_write_so_t_only_diagnostic_pbs(tmp_path):
    install = tmp_path / "install"
    exe = install / "bin" / "mpasjedi_variational.x"
    exe.parent.mkdir(parents=True)
    exe.touch()
    run_dir = tmp_path / "SO"
    run_dir.mkdir()
    config = {
        "project": {"project_root": str(tmp_path)},
        "environment": {"loader": "load.sh"},
        "install": {"root": str(install)},
        "mesh": {"nproc": 128},
        "pbs": {"queue": "queue", "walltime_short": "00:10:00"},
    }

    write_so_t_only_diagnostic_pbs(config, run_dir)

    debug = (run_dir / "qsub_so_t_only_debug.bash").read_text()
    gdb = (run_dir / "qsub_so_t_only_gdb1.bash").read_text()
    assert "run_SO_t_only.yaml ./run_SO_t_only_debug.runlog" in debug
    assert "stdout_t_only_debug.log" in debug
    assert "stderr_t_only_debug.log" in debug
    assert "ulimit -c unlimited" in debug
    assert "export GFORTRAN_ERROR_BACKTRACE=1" in debug
    assert "cat /proc/sys/kernel/core_pattern" in debug
    assert "module list" in debug
    assert "command -v \"$tool\"" in debug
    assert "#PBS -l select=1:ncpus=1:mpiprocs=1" in gdb
    assert "mpiexec -n 1 gdb --batch --quiet" in gdb
    assert "thread apply all bt full" in gdb
    assert "./run_SO_t_only.yaml ./run_SO_t_only_gdb1.runlog" in gdb


def write_so_products(run_dir, variant="default"):
    artifacts = bcov.so_artifacts(variant)
    (run_dir / artifacts["runlog"]).write_text(
        "Run: Finishing oops::Variational<MPAS, UFO and IODA observations> "
        "with status = 0\n"
    )
    (run_dir / "an.2026-06-10_00.00.00.nc").touch()
    if variant in ("default", "t-only"):
        (run_dir / "obsout_SO_T.h5").touch()
    if variant in ("default", "u-only"):
        (run_dir / "obsout_SO_U.h5").touch()


def test_validate_so_accepts_minimum_products(tmp_path):
    write_so_products(tmp_path)
    assert validate_so(tmp_path)


@pytest.mark.parametrize("variant", ["t-only", "u-only"])
def test_validate_so_accepts_variant_products(tmp_path, variant):
    write_so_products(tmp_path, variant=variant)
    assert validate_so(tmp_path, variant=variant)


def test_validate_so_variant_requires_its_observation_output(tmp_path):
    artifacts = bcov.so_artifacts("t-only")
    (tmp_path / artifacts["runlog"]).write_text(
        "Run: Finishing oops::Variational<MPAS, UFO and IODA observations> "
        "with status = 0\n"
    )
    (tmp_path / "an.2026-06-10_00.00.00.nc").touch()

    with pytest.raises(SystemExit):
        validate_so(tmp_path, variant="t-only")


def test_validate_so_ignores_other_variant_and_old_pbs_logs(tmp_path):
    write_so_products(tmp_path, variant="t-only")
    (tmp_path / "run_SO.runlog").write_text("ERROR: falha default antiga\n")
    (tmp_path / "stderr.log").write_text("FATAL: falha default antiga\n")
    (tmp_path / "SOTest.o123").write_text("Could not chdir to home directory\n")

    assert validate_so(tmp_path, variant="t-only")


def test_validate_so_ignores_crayblas_warning(tmp_path):
    write_so_products(tmp_path, variant="t-only")
    artifacts = bcov.so_artifacts("t-only")
    (tmp_path / artifacts["stderr"]).write_text(
        "CRAYBLAS_WARNING: ERROR: fallback interno da biblioteca\n"
    )

    assert validate_so(tmp_path, variant="t-only")


def test_validate_so_accepts_irrelevant_error_line_with_success(tmp_path):
    write_so_products(tmp_path, variant="t-only")
    artifacts = bcov.so_artifacts("t-only")
    (tmp_path / artifacts["stderr"]).write_text(
        "ERROR: mensagem não fatal emitida por biblioteca\n"
    )

    assert validate_so(tmp_path, variant="t-only")


@pytest.mark.parametrize("missing", ["obsout_SO_T.h5", "obsout_SO_U.h5"])
def test_validate_so_default_requires_both_observation_outputs(tmp_path, missing):
    write_so_products(tmp_path)
    (tmp_path / missing).unlink()

    with pytest.raises(SystemExit):
        validate_so(tmp_path)


@pytest.mark.parametrize(
    ("variant", "required", "not_required"),
    [
        ("t-only", "obsout_SO_T.h5", "obsout_SO_U.h5"),
        ("u-only", "obsout_SO_U.h5", "obsout_SO_T.h5"),
    ],
)
def test_validate_so_single_variant_product_requirements(
    tmp_path, variant, required, not_required
):
    write_so_products(tmp_path, variant=variant)
    assert not (tmp_path / not_required).exists()
    assert validate_so(tmp_path, variant=variant)

    (tmp_path / required).unlink()
    with pytest.raises(SystemExit):
        validate_so(tmp_path, variant=variant)


def test_validate_so_rejects_fatal_in_current_variant_log(tmp_path):
    write_so_products(tmp_path, variant="t-only")
    artifacts = bcov.so_artifacts("t-only")
    (tmp_path / artifacts["stderr"]).write_text("FATAL: falha atual\n")

    with pytest.raises(SystemExit):
        validate_so(tmp_path, variant="t-only")


def test_validate_so_rejects_nonzero_status(tmp_path):
    write_so_products(tmp_path, variant="t-only")
    artifacts = bcov.so_artifacts("t-only")
    (tmp_path / artifacts["runlog"]).write_text(
        "Run: Finishing oops::Variational<MPAS, UFO and IODA observations> "
        "with status = 1\n"
    )

    with pytest.raises(SystemExit):
        validate_so(tmp_path, variant="t-only")


def test_submit_so_retries_pbs_home_failure(tmp_path, monkeypatch, capsys):
    attempts = []

    def fake_qsub(pbs_file, cwd):
        attempts.append(1)
        return f"job{len(attempts)}"

    def fake_wait(jobid, poll_seconds):
        if jobid == "job1":
            (tmp_path / "SOTest.o123").write_text("Could not chdir to home directory\n")
        else:
            write_so_products(tmp_path)

    monkeypatch.setattr(bcov, "qsub", fake_qsub)
    monkeypatch.setattr(bcov, "wait_for_pbs_job", fake_wait)

    assert submit_so(tmp_path, wait=True, retries=2, poll_seconds=1) == "job2"
    assert len(attempts) == 2
    assert "Falha PBS/HOME na JACI, ressubmetendo etapa SO." in capsys.readouterr().out


def test_submit_so_uses_variant_pbs(tmp_path, monkeypatch):
    submitted = []

    def fake_qsub(pbs_file, cwd):
        submitted.append((pbs_file, cwd))
        return "job1"

    monkeypatch.setattr(bcov, "qsub", fake_qsub)

    assert submit_so(tmp_path, variant="u-only") == "job1"
    assert submitted == [("qsub_so_u_only.bash", tmp_path)]


def test_write_dirac_yaml_reads_validated_covariance_products(tmp_path):
    output = tmp_path / "run_dirac.yaml"
    nicas = tmp_path / "nicas" / "merge"
    stddev = tmp_path / "hdiag" / "HDIAG" / "mpas.stddev.nc"
    vbal = tmp_path / "vbal" / "VBAL"

    write_dirac_yaml(
        output,
        date="2026-06-10T00:00:00Z",
        nicas_dir=nicas,
        stddev_file=stddev,
        vbal_dir=vbal,
    )

    text = output.read_text()
    assert "saber block name: BUMP_NICAS" in text
    assert f"data directory: {nicas}" in text
    assert "read local nicas: true" in text
    assert "saber block name: StdDev" in text
    assert f"filename: {stddev}" in text
    assert "saber block name: BUMP_VerticalBalance" in text
    assert f"data directory: {vbal}" in text
    assert "read local sampling: true" in text
    assert "read vertical balance: true" in text
    assert "linear variable change name: Control2Analysis" in text
    assert 'filename: "./bg.nc"' in text
    assert "transform model to analysis: false" in text
    assert "dirvar: temperature" in text
    assert 'filename: "./mpas.dirac.nc"' in text


def test_write_dirac_pbs_uses_toolbox_and_mesh_rank_count(tmp_path):
    install = tmp_path / "install"
    exe = install / "bin" / "mpasjedi_error_covariance_toolbox.x"
    exe.parent.mkdir(parents=True)
    exe.touch()
    run_dir = tmp_path / "Dirac"
    run_dir.mkdir()
    config = {
        "project": {"project_root": str(tmp_path)},
        "environment": {"loader": "load.sh"},
        "install": {"root": str(install)},
        "mesh": {"nproc": 128},
        "pbs": {"queue": "queue", "walltime_short": "00:10:00"},
    }

    write_dirac_pbs(config, run_dir)

    text = (run_dir / "qsub_dirac.bash").read_text()
    assert str(exe) in text
    assert f'cd "{run_dir}"' in text
    assert "#PBS -l select=1:ncpus=128:mpiprocs=128" in text
    assert "mpiexec -n 128" in text
    assert "./run_dirac.yaml ./run_dirac.runlog" in text
    assert "GFORTRAN_CONVERT_UNIT=big_endian:101-200" in text
    assert "#PBS -d" not in text
    assert "#PBS -J" not in text


def test_validate_dirac_accepts_status_and_output(tmp_path):
    (tmp_path / "run_dirac.runlog").write_text(
        "Run: Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0\n"
    )
    (tmp_path / "mpas.dirac.nc").touch()

    assert validate_dirac(tmp_path)


def test_validate_dirac_requires_output(tmp_path):
    (tmp_path / "run_dirac.runlog").write_text(
        "Run: Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0\n"
    )

    with pytest.raises(SystemExit, match="Dirac falhou"):
        validate_dirac(tmp_path)


def test_parser_exposes_dirac_commands():
    command_parser = bcov.parser()

    assert command_parser.parse_args(
        ["dirac-validate", "--workspace", "/tmp/dirac"]
    ).func is bcov.dirac_validate_command
    assert command_parser.parse_args(
        ["dirac-submit", "--workspace", "/tmp/dirac"]
    ).func is bcov.dirac_submit_command


def test_parser_exposes_dirac_summary():
    args = bcov.parser().parse_args(
        ["dirac-summary", "--workspace", "/tmp/dirac", "--csv", "/tmp/dirac.csv"]
    )

    assert args.func is bcov.dirac_summary_command
    assert args.workspace == "/tmp/dirac"
    assert args.csv == "/tmp/dirac.csv"


def test_dirac_summary_missing_file_fails(tmp_path):
    with pytest.raises(SystemExit, match="produto Dirac ausente"):
        bcov.summarize_dirac(tmp_path)


def test_dirac_summary_reports_numeric_variables(tmp_path, capsys):
    netCDF4 = pytest.importorskip("netCDF4")
    workspace = tmp_path / "dirac"
    workspace.mkdir()
    with netCDF4.Dataset(workspace / "mpas.dirac.nc", "w") as dataset:
        dataset.createDimension("nCells", 3)
        temperature = dataset.createVariable("temperature", "f4", ("nCells",))
        temperature[:] = [1.0, -2.0, float("nan")]
        dataset.createVariable("category", str, ("nCells",))

    rows = bcov.summarize_dirac(workspace)
    bcov.print_dirac_summary(rows)

    assert rows == [
        {
            "variable": "temperature",
            "shape": "3",
            "min": -2.0,
            "max": 1.0,
            "mean": -0.5,
            "rms": pytest.approx((5.0 / 2.0) ** 0.5),
            "max_abs": 2.0,
            "nonzero_count": 2,
        }
    ]
    output = capsys.readouterr().out
    assert "variable shape min max mean rms max_abs nonzero_count" in output
    assert "temperature 3 -2 1 -0.5" in output


def test_dirac_summary_reports_zero_nonzero_count(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    workspace = tmp_path / "dirac"
    workspace.mkdir()
    with netCDF4.Dataset(workspace / "mpas.dirac.nc", "w") as dataset:
        dataset.createDimension("nCells", 2)
        values = dataset.createVariable("surface_pressure", "f4", ("nCells",))
        values[:] = [0.0, 0.0]

    rows = bcov.summarize_dirac(workspace)

    assert rows[0]["variable"] == "surface_pressure"
    assert rows[0]["nonzero_count"] == 0
    assert rows[0]["rms"] == 0.0
    assert rows[0]["max_abs"] == 0.0


def test_dirac_summary_writes_csv(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    workspace = tmp_path / "dirac"
    workspace.mkdir()
    with netCDF4.Dataset(workspace / "mpas.dirac.nc", "w") as dataset:
        dataset.createDimension("nCells", 2)
        values = dataset.createVariable("spechum", "f4", ("nCells",))
        values[:] = [0.0, 3.0]

    csv_path = tmp_path / "summary.csv"
    args = bcov.parser().parse_args(
        ["dirac-summary", "--workspace", str(workspace), "--csv", str(csv_path)]
    )

    assert bcov.dirac_summary_command(args) == 0

    text = csv_path.read_text()
    assert "variable,shape,min,max,mean,rms,max_abs,nonzero_count" in text
    assert "spechum,2,0.0,3.0,1.5" in text


def write_dirac_plot_workspace(tmp_path, variable_dims=("Time", "nCells")):
    netCDF4 = pytest.importorskip("netCDF4")
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "dirac"
    workspace.mkdir()
    with netCDF4.Dataset(workspace / "x1.10242.invariant.nc", "w") as dataset:
        dataset.createDimension("nCells", 4)
        lat = dataset.createVariable("latCell", "f8", ("nCells",))
        lon = dataset.createVariable("lonCell", "f8", ("nCells",))
        lat[:] = [-0.2, -0.1, 0.1, 0.2]
        lon[:] = [0.0, 0.1, 0.2, 0.3]
    with netCDF4.Dataset(workspace / "mpas.dirac.nc", "w") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 4)
        dataset.createDimension("nVertLevels", 3)
        shape = tuple(dataset.dimensions[dim].size for dim in variable_dims)
        values = dataset.createVariable("temperature", "f4", variable_dims)
        if variable_dims == ("Time", "nCells"):
            values[:] = [[-1.0, 0.0, 1.0, 2.0]]
        elif variable_dims == ("Time", "nCells", "nVertLevels"):
            values[:] = [[[-1.0, -2.0, -3.0], [0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [2.0, 4.0, 6.0]]]
        else:
            values[:] = list(range(1, shape[0] + 1))
    return workspace


def test_parser_exposes_dirac_plot():
    args = bcov.parser().parse_args(
        [
            "dirac-plot",
            "--workspace",
            "/tmp/dirac",
            "--variables",
            "temperature",
            "surface_pressure",
            "--level",
            "2",
            "--output-dir",
            "/tmp/figures",
            "--dpi",
            "90",
        ]
    )

    assert args.func is bcov.dirac_plot_command
    assert args.variables == ["temperature", "surface_pressure"]
    assert args.level == 2
    assert args.output_dir == "/tmp/figures"
    assert args.dpi == 90


def test_dirac_plot_writes_png_for_time_cell_variable(tmp_path):
    workspace = write_dirac_plot_workspace(tmp_path)
    output = tmp_path / "figures"

    figures = bcov.plot_dirac(
        workspace,
        variables=["temperature"],
        output_dir=output,
        dpi=60,
    )

    assert figures == [output / "dirac_temperature.png"]
    assert figures[0].is_file()
    assert figures[0].stat().st_size > 0
    index = (output / "index.md").read_text()
    assert "temperature" in index
    assert "dirac_temperature.png" in index


def test_dirac_plot_writes_png_for_3d_variable_level(tmp_path):
    workspace = write_dirac_plot_workspace(
        tmp_path, variable_dims=("Time", "nCells", "nVertLevels")
    )
    output = tmp_path / "figures"

    figures = bcov.plot_dirac(
        workspace,
        variables=["temperature"],
        level=2,
        output_dir=output,
        dpi=60,
    )

    assert figures == [output / "dirac_temperature_level002.png"]
    assert figures[0].is_file()
    assert "| temperature | 2 |" in (output / "index.md").read_text()


def test_dirac_plot_missing_variable_fails(tmp_path):
    workspace = write_dirac_plot_workspace(tmp_path)

    with pytest.raises(SystemExit, match="variável ausente"):
        bcov.plot_dirac(workspace, variables=["surface_pressure"])


def test_dirac_plot_level_out_of_range_fails(tmp_path):
    workspace = write_dirac_plot_workspace(
        tmp_path, variable_dims=("Time", "nCells", "nVertLevels")
    )

    with pytest.raises(SystemExit, match="nível fora do intervalo"):
        bcov.plot_dirac(workspace, variables=["temperature"], level=3)


def write_plot_coordinates(workspace):
    netCDF4 = pytest.importorskip("netCDF4")
    with netCDF4.Dataset(workspace / "x1.10242.invariant.nc", "w") as dataset:
        dataset.createDimension("nCells", 4)
        dataset.createVariable("latCell", "f8", ("nCells",))[:] = [-0.2, -0.1, 0.1, 0.2]
        dataset.createVariable("lonCell", "f8", ("nCells",))[:] = [0.0, 0.1, 0.2, 0.3]


def write_cell_level_file(path, variable="temperature"):
    netCDF4 = pytest.importorskip("netCDF4")
    path.parent.mkdir(parents=True, exist_ok=True)
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("Time", 1)
        dataset.createDimension("nCells", 4)
        dataset.createDimension("nVertLevels", 3)
        values = dataset.createVariable(variable, "f4", ("Time", "nCells", "nVertLevels"))
        values[:] = [[[-1.0, -2.0, -3.0], [0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [2.0, 4.0, 6.0]]]


def test_parser_exposes_hdiag_nicas_vbal_plot():
    parser = bcov.parser()

    assert parser.parse_args(["hdiag-plot", "--workspace", "/tmp/hdiag"]).func is bcov.hdiag_plot_command
    assert parser.parse_args(["nicas-plot", "--workspace", "/tmp/nicas"]).func is bcov.nicas_plot_command
    assert parser.parse_args(["vbal-plot", "--workspace", "/tmp/vbal"]).func is bcov.vbal_plot_command


def test_hdiag_plot_creates_png_and_index(tmp_path):
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "hdiag"
    workspace.mkdir()
    write_plot_coordinates(workspace)
    for name in ["mpas.stddev.nc", "mpas.cor_rh.nc", "mpas.cor_rv.nc"]:
        write_cell_level_file(workspace / "HDIAG" / name)
    output = tmp_path / "hdiag_figures"

    figures = bcov.plot_hdiag(
        workspace,
        variables=["temperature"],
        level=1,
        output_dir=output,
        dpi=60,
    )

    assert figures
    assert all(path.is_file() for path in figures)
    assert (output / "index.md").is_file()
    assert "temperature" in (output / "index.md").read_text()


def test_nicas_plot_creates_png_and_index(tmp_path):
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "nicas"
    workspace.mkdir()
    write_plot_coordinates(workspace)
    write_cell_level_file(workspace / "merge" / "mpas_nicas.nc", variable="stream_function")
    output = tmp_path / "nicas_figures"

    figures = bcov.plot_nicas(
        workspace,
        variables=["stream_function"],
        level=1,
        output_dir=output,
        dpi=60,
    )

    assert figures == [output / "nicas_mpas_nicas_stream_function_level001.png"]
    assert figures[0].is_file()
    assert "stream_function" in (output / "index.md").read_text()


def test_vbal_plot_creates_png_and_index_for_1d_variable(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "vbal"
    run_dir = workspace / "VBAL"
    run_dir.mkdir(parents=True)
    for filename in ["mpas_vbal.nc", "mpas_sampling.nc"]:
        with netCDF4.Dataset(run_dir / filename, "w") as dataset:
            dataset.createDimension("nVertLevels", 3)
            dataset.createVariable("regression", "f4", ("nVertLevels",))[:] = [0.0, 1.0, 2.0]
    output = tmp_path / "vbal_figures"

    figures = bcov.plot_vbal(
        workspace,
        variables=["regression"],
        level=None,
        output_dir=output,
        dpi=60,
    )

    assert len(figures) == 2
    assert all(path.is_file() for path in figures)
    assert "regression" in (output / "index.md").read_text()


def test_diagnostic_plot_missing_variable_fails(tmp_path):
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "nicas"
    workspace.mkdir()
    write_plot_coordinates(workspace)
    write_cell_level_file(workspace / "merge" / "mpas_nicas.nc", variable="temperature")

    with pytest.raises(SystemExit, match="variável ausente"):
        bcov.plot_nicas(workspace, variables=["surface_pressure"])


def test_diagnostic_plot_level_out_of_range_fails(tmp_path):
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "nicas"
    workspace.mkdir()
    write_plot_coordinates(workspace)
    write_cell_level_file(workspace / "merge" / "mpas_nicas.nc", variable="temperature")

    with pytest.raises(SystemExit, match="nível fora do intervalo"):
        bcov.plot_nicas(workspace, variables=["temperature"], level=5)


def test_parser_exposes_report():
    args = bcov.parser().parse_args(
        [
            "report",
            "--config",
            "configs/test.yaml",
            "--dirac-workspace",
            "/tmp/dirac",
            "--figures-dir",
            "/tmp/figures",
            "--output",
            "/tmp/report.md",
            "--title",
            "Smoke Report",
            "--no-html-index",
        ]
    )

    assert args.func is bcov.report_command
    assert args.figures_dir == ["/tmp/figures"]
    assert args.title == "Smoke Report"
    assert args.no_html_index


def test_report_writes_markdown_with_workspaces_products_and_figures(tmp_path):
    dirac = tmp_path / "dirac"
    figures = tmp_path / "figures"
    dirac.mkdir()
    figures.mkdir()
    (dirac / "mpas.dirac.nc").touch()
    (figures / "dirac_temperature.png").touch()
    output = tmp_path / "report.md"

    bcov.write_bmatrix_report(
        output,
        title="Smoke Report",
        config_path="configs/test.yaml",
        bflow_workspace_path=tmp_path / "bflow",
        dirac_workspace_path=dirac,
        figures_dirs=[figures],
    )

    text = output.read_text()
    assert "# Smoke Report" in text
    assert "configs/test.yaml" in text
    assert "Bflow" in text
    assert "mpas.dirac.nc" in text
    assert "dirac_temperature.png" in text
    assert "SKIP" in text


def test_report_command_writes_html_index_by_default(tmp_path):
    dirac = tmp_path / "dirac"
    figures = tmp_path / "figures"
    nested = figures / "hdiag"
    dirac.mkdir()
    nested.mkdir(parents=True)
    (dirac / "mpas.dirac.nc").touch()
    (nested / "hdiag_temperature.png").touch()
    output = dirac / "report.md"

    args = bcov.parser().parse_args(
        [
            "report",
            "--dirac-workspace",
            str(dirac),
            "--figures-dir",
            str(figures),
            "--output",
            str(output),
            "--title",
            "Smoke Report",
        ]
    )

    assert bcov.report_command(args) == 0

    html = dirac / "index.html"
    text = html.read_text()
    assert html.is_file()
    assert 'href="report.md"' in text
    assert "hdiag_temperature.png" in text
    assert "<img" in text
    assert "smoke test" in text


def test_report_command_no_html_index(tmp_path):
    output = tmp_path / "report.md"
    args = bcov.parser().parse_args(
        [
            "report",
            "--output",
            str(output),
            "--no-html-index",
        ]
    )

    assert bcov.report_command(args) == 0

    assert output.is_file()
    assert not (tmp_path / "index.html").exists()


def test_report_strict_fails_on_validation_failure(tmp_path):
    output = tmp_path / "report.md"

    with pytest.raises(SystemExit, match="strict"):
        bcov.write_bmatrix_report(
            output,
            title="Smoke Report",
            vbal_workspace_path=tmp_path / "missing-vbal",
            strict=True,
        )


def test_parser_exposes_pipeline_all():
    args = bcov.parser().parse_args(
        [
            "pipeline-all",
            "--config",
            "config.yaml",
            "--bflow-workspace",
            "/work/bflow",
            "--clean",
            "--poll-seconds",
            "5",
            "--retries",
            "4",
            "--validate-only",
        ]
    )

    assert args.func is bcov.pipeline_all_command
    assert args.config == "config.yaml"
    assert args.bflow_workspace == "/work/bflow"
    assert args.clean
    assert args.poll_seconds == 5
    assert args.retries == 4
    assert args.validate_only


def test_pipeline_all_requires_bflow_workspace():
    args = bcov.parser().parse_args(["pipeline-all", "--validate-only"])

    with pytest.raises(SystemExit, match="--bflow-workspace"):
        bcov.pipeline_all_command(args)


def test_pipeline_validate_only_calls_only_validators(tmp_path, monkeypatch, capsys):
    config = {"project": {"work_root": str(tmp_path / "work")}}
    bflow = tmp_path / "bflow" / "np128_2026061000_2026061300"
    calls = []

    monkeypatch.setattr(bcov, "load_config", lambda path: config)
    monkeypatch.setattr(bcov, "validate_vbal", lambda workspace: calls.append(("vbal", Path(workspace))))
    monkeypatch.setattr(bcov, "validate_hdiag", lambda workspace: calls.append(("hdiag", Path(workspace))))
    monkeypatch.setattr(bcov, "validate_nicas", lambda workspace: calls.append(("nicas", Path(workspace))))
    monkeypatch.setattr(
        bcov,
        "validate_so",
        lambda workspace, variant="default": calls.append(("so", Path(workspace), variant)),
    )
    monkeypatch.setattr(bcov, "validate_dirac", lambda workspace: calls.append(("dirac", Path(workspace))))
    monkeypatch.setattr(
        bcov,
        "prepare_vbal",
        lambda *args, **kwargs: pytest.fail("validate-only nao deve preparar"),
    )
    monkeypatch.setattr(
        bcov,
        "submit_vbal",
        lambda *args, **kwargs: pytest.fail("validate-only nao deve submeter"),
    )

    args = bcov.parser().parse_args(
        [
            "pipeline-all",
            "--config",
            "config.yaml",
            "--bflow-workspace",
            str(bflow),
            "--validate-only",
        ]
    )

    assert bcov.pipeline_all_command(args) == 0

    base = tmp_path / "work" / "bmatrix" / "covariance"
    assert calls == [
        ("vbal", base / "vbal" / bflow.name),
        ("hdiag", base / "hdiag" / bflow.name),
        ("nicas", base / "nicas" / bflow.name),
        ("so", base / "so" / bflow.name, "default"),
        ("dirac", base / "dirac" / bflow.name),
    ]
    assert "B-matrix pipeline summary" in capsys.readouterr().out


def test_pipeline_all_runs_stages_in_order_without_real_pbs(tmp_path, monkeypatch):
    config = {"project": {"work_root": str(tmp_path / "work")}}
    bflow = tmp_path / "bflow" / "np128_2026061000_2026061300"
    order = []

    monkeypatch.setattr(bcov, "load_config", lambda path: config)

    def record_prepare(name):
        def inner(config_arg, input_workspace, **kwargs):
            order.append((f"prepare_{name}", Path(input_workspace), Path(kwargs["workspace"]), kwargs.get("clean")))
            return Path(kwargs["workspace"])

        return inner

    def record_submit(name, jobid):
        def inner(workspace, **kwargs):
            order.append((f"submit_{name}", Path(workspace), kwargs.get("wait"), kwargs.get("poll_seconds"), kwargs.get("retries")))
            return jobid

        return inner

    def record_validate(name):
        def inner(workspace, **kwargs):
            order.append((f"validate_{name}", Path(workspace), kwargs.get("variant")))
            return True

        return inner

    monkeypatch.setattr(bcov, "prepare_vbal", record_prepare("vbal"))
    monkeypatch.setattr(bcov, "submit_vbal", record_submit("vbal", "vbaljob"))
    monkeypatch.setattr(bcov, "validate_vbal", record_validate("vbal"))
    monkeypatch.setattr(bcov, "prepare_hdiag", record_prepare("hdiag"))
    monkeypatch.setattr(bcov, "submit_hdiag", record_submit("hdiag", "hdiagjob"))
    monkeypatch.setattr(bcov, "validate_hdiag", record_validate("hdiag"))
    monkeypatch.setattr(bcov, "prepare_nicas", record_prepare("nicas"))
    monkeypatch.setattr(bcov, "submit_nicas", record_submit("nicas", "nicasjob"))
    monkeypatch.setattr(bcov, "validate_nicas", record_validate("nicas"))
    monkeypatch.setattr(bcov, "prepare_so", record_prepare("so"))
    monkeypatch.setattr(bcov, "submit_so", record_submit("so", "sojob"))
    monkeypatch.setattr(bcov, "validate_so", record_validate("so"))
    monkeypatch.setattr(bcov, "prepare_dirac", record_prepare("dirac"))
    monkeypatch.setattr(bcov, "submit_dirac", record_submit("dirac", "diracjob"))
    monkeypatch.setattr(bcov, "validate_dirac", record_validate("dirac"))

    args = bcov.parser().parse_args(
        [
            "pipeline-all",
            "--config",
            "config.yaml",
            "--bflow-workspace",
            str(bflow),
            "--clean",
            "--poll-seconds",
            "7",
            "--retries",
            "3",
        ]
    )

    assert bcov.pipeline_all_command(args) == 0

    assert [entry[0] for entry in order] == [
        "prepare_vbal",
        "submit_vbal",
        "validate_vbal",
        "prepare_hdiag",
        "submit_hdiag",
        "validate_hdiag",
        "prepare_nicas",
        "submit_nicas",
        "validate_nicas",
        "prepare_so",
        "submit_so",
        "validate_so",
        "prepare_dirac",
        "submit_dirac",
        "validate_dirac",
    ]
    submit_calls = [entry for entry in order if entry[0].startswith("submit_")]
    assert all(call[2] is True for call in submit_calls)
    assert all(call[3] == 7 for call in submit_calls)
    assert [call[4] for call in submit_calls[-3:]] == [3, 3, 3]
