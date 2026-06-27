from __future__ import annotations

"""Compatibility wrapper for MPAS forecast helpers.

The implementation lives in mpas_workflow.mpas_core.
"""

from .mpas_core.cleanup import clean_forecast_run_dir
from .mpas_core.checks import check_forecast_setup as validate_forecast_setup
from .mpas_core.jobs import run_job as submit_forecast
from .mpas_core.model import (
    DA_STATE_REQUIRED_VARIABLES,
    bflow_file,
    fmt_file_time,
    forecast_run_dir,
    parse_time,
    restart_file,
)
from .mpas_core.setup import setup_run as prepare_forecast
from .mpas_core.streams import (
    copy_tutorial_stream_lists as _copy_tutorial_stream_lists,
    ensure_restart_stream as _ensure_restart_stream,
    find_stream as _find_stream,
    patch_namelist,
    prepare_streams as _prepare_streams,
    tutorial_physics_dir as _tutorial_physics_dir,
)
