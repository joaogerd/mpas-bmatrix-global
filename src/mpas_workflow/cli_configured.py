"""Configured MPAS workflow command entry point."""
from __future__ import annotations

from . import cli as legacy
from .mpas_init_configured import install


def main(argv=None):
    install()
    return legacy.main(argv)
