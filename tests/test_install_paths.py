import pytest

from mpas_workflow.case_config import load_case_config, resolve_context
from mpas_workflow.config import load_config
from mpas_workflow.install_paths import InstallPathError, resolve_install_paths


def test_root_supplies_default_layout():
    paths = resolve_install_paths({"root": "/opt/mpas"})
    assert paths["mpas_init"] == "/opt/mpas/bin/mpas_init_atmosphere"
    assert paths["mpas_atmosphere"] == "/opt/mpas/bin/mpas_atmosphere"
    assert paths["init_share"] == "/opt/mpas/share/MPAS/core_init_atmosphere"
    assert paths["atmosphere_share"] == "/opt/mpas/share/MPAS/core_atmosphere"


def test_explicit_names_use_bin_and_relative_shares_use_root():
    paths = resolve_install_paths(
        {
            "root": "/opt/mpas",
            "mpas_init": "custom_init",
            "mpas_atmosphere": "custom_atmosphere",
            "init_share": "share/MPAS/custom_init",
            "atmosphere_share": "share/MPAS/custom_atmosphere",
        }
    )
    assert paths["mpas_init"] == "/opt/mpas/bin/custom_init"
    assert paths["mpas_atmosphere"] == "/opt/mpas/bin/custom_atmosphere"
    assert paths["init_share"] == "/opt/mpas/share/MPAS/custom_init"
    assert paths["atmosphere_share"] == "/opt/mpas/share/MPAS/custom_atmosphere"


def test_absolute_override_ignores_root():
    paths = resolve_install_paths(
        {"root": "/opt/mpas", "mpas_atmosphere": "/custom/bin/mpas_atmosphere"}
    )
    assert paths["mpas_atmosphere"] == "/custom/bin/mpas_atmosphere"


def test_relative_path_without_root_is_invalid():
    with pytest.raises(InstallPathError):
        resolve_install_paths({"mpas_init": "mpas_init_atmosphere"})


def test_legacy_loader_normalizes_root_only_install(tmp_path):
    path = tmp_path / "workflow.yaml"
    path.write_text("install:\n  root: /opt/mpas\n")
    assert load_config(path)["install"]["mpas_init"] == "/opt/mpas/bin/mpas_init_atmosphere"


def test_case_context_normalizes_install_root(tmp_path):
    (tmp_path / "site.yaml").write_text(
        "context:\n  project_root: /opt/user\ninstall:\n  root: '{project_root}/builds/mpas'\n"
    )
    case = tmp_path / "case.yaml"
    case.write_text("includes:\n  - site.yaml\ncase:\n  name: case\n")
    context = resolve_context(load_case_config(case))
    assert context["mpas_init_executable"] == "/opt/user/builds/mpas/bin/mpas_init_atmosphere"
