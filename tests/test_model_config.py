from pathlib import Path

from mpas_workflow.forecast import bflow_file, forecast_run_dir, restart_file
from mpas_workflow.model_config import model_config
from mpas_workflow.mpas_init import (
    init_file,
    init_run_dir,
    patch_streams_init_atmosphere,
)


def configuration():
    return {
        "project": {"work_root": "/tmp/work"},
        "mesh": {"name": "x9.42", "nproc": 16, "nvertlevels": 55},
        "model": {
            "init": {
                "run_directory": "init/{mesh_name}/{safe_time}/np{nproc}",
                "output_filename": "init-{mesh_name}-{safe_time}.nc",
                "input_grid_filename": "grid-{mesh_name}.nc",
                "streams": {
                    "replace_clobber_mode": "never_modify",
                    "output_clobber_mode": "append",
                },
            },
            "forecast": {
                "run_directory": "forecast/{mesh_name}/{lead_hours:03d}/{safe_time}",
                "da_state_filename": "state.$Y$M$D_$h$m$s.nc",
                "restart_filename": "restart.$Y$M$D_$h$m$s.nc",
            },
        },
    }


def test_model_defaults_are_merged_with_platform_overrides():
    cfg = configuration()
    value = model_config(cfg)

    assert value["init"]["output_filename"] == "init-{mesh_name}-{safe_time}.nc"
    assert value["init"]["namelist"]["config_init_case"] == "7"
    assert value["forecast"]["streams"]["da_state_stream"] == "da_state"


def test_init_paths_follow_the_model_configuration():
    cfg = configuration()

    assert init_run_dir(cfg, "2018-04-15_00:00:00") == Path(
        "/tmp/work/init/x9.42/2018-04-15_00.00.00/np16"
    )
    assert init_file(cfg, "2018-04-15_00:00:00").name == (
        "init-x9.42-2018-04-15_00.00.00.nc"
    )


def test_forecast_paths_and_output_timestamps_follow_the_model_configuration():
    cfg = configuration()

    run_dir = forecast_run_dir(cfg, "2018-04-13_00:00:00", 48, 60)
    assert run_dir == Path("/tmp/work/forecast/x9.42/048/2018-04-13_00.00.00")
    assert restart_file(cfg, "2018-04-13_00:00:00", 48, 60).name == (
        "restart.20180415_000000.nc"
    )
    assert bflow_file(cfg, "2018-04-13_00:00:00", 48, 60).name == (
        "state.20180415_000000.nc"
    )


def test_init_stream_renderer_uses_configured_clobber_policy():
    source = """<streams>
<stream filename_template=\"x1.40962.grid.nc\" clobber_mode=\"never_modify\"/>
<stream filename_template=\"x1.40962.init.nc\" clobber_mode=\"never_modify\"/>
</streams>"""

    rendered = patch_streams_init_atmosphere(
        source,
        mesh_name="x9.42",
        output_filename="init-x9.42.nc",
        streams_config=configuration()["model"]["init"]["streams"],
    )

    assert 'filename_template="x9.42.grid.nc"' in rendered
    assert 'filename_template="init-x9.42.nc"' in rendered
    assert 'clobber_mode="append"' in rendered
