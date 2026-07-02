from __future__ import annotations

from .jobs import run_job
from .setup import setup_run

prepare = setup_run
submit = run_job
