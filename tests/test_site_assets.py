from __future__ import annotations

import json
from pathlib import Path

import pytest

from mpas_workflow.case_config import load_case_config
from mpas_workflow.site_assets import SiteAssetError, prepare_wps_geog_assets
from mpas_workflow.site_assets_cli import main as assets_main


def write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def asset_case(tmp_path: Path, *, include_overlay: bool = True) -> Path:
    shared = tmp_path / "shared"
    overlay = tmp_path / "overlay"
    view = tmp_path / "view"

    write(shared / "topo_gmted2010_30s" / "index")
    write(shared / "soilgrids" / "soilcomp" / "index")
    if include_overlay:
        write(overlay / "soiltype_bot_30s" / "index")

    return write(
        tmp_path / "case.yaml",
        f"""case:
  name: assets-unit
context:
  monan_version: "1.4.x"
  mpas_version: "8.3.1"
assets:
  wps_geog:
    profile: monan-1.4-mpas-8.3.1
    view_root: {view}
    sources:
      - name: monan-shared
        root: {shared}
      - name: local-overlay
        root: {overlay}
    required_files:
      - topo_gmted2010_30s/index
      - soiltype_bot_30s/index
      - soilgrids/soilcomp/index
""",
    )


def test_prepare_wps_geog_creates_symlink_only_combined_view(tmp_path: Path):
    case = load_case_config(asset_case(tmp_path))

    result = prepare_wps_geog_assets(case)

    assert result is not None
    assert result.materialized
    assert (result.view_root / "topo_gmted2010_30s").is_symlink()
    assert (result.view_root / "soilgrids").is_symlink()
    assert (result.view_root / "soiltype_bot_30s").is_symlink()
    assert (result.view_root / "soiltype_bot_30s" / "index").is_file()

    manifest = json.loads(result.manifest.read_text())
    resolutions = {item["path"]: item["source"] for item in manifest["required_files"]}
    assert resolutions["topo_gmted2010_30s/index"] == "monan-shared"
    assert resolutions["soiltype_bot_30s/index"] == "local-overlay"
    assert manifest["model"] == {"monan_version": "1.4.x", "mpas_version": "8.3.1"}


def test_validate_wps_geog_reports_missing_overlay_asset(tmp_path: Path):
    case = load_case_config(asset_case(tmp_path, include_overlay=False))

    with pytest.raises(SiteAssetError, match="soiltype_bot_30s/index"):
        prepare_wps_geog_assets(case, materialize=False)


def test_assets_cli_validate_and_prepare(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    case_path = asset_case(tmp_path)

    assert assets_main(["validate", "--case", str(case_path)]) == 0
    assert "WPS_GEOG validado" in capsys.readouterr().out

    assert assets_main(["prepare", "--case", str(case_path)]) == 0
    output = capsys.readouterr().out
    assert "WPS_GEOG preparado" in output
    assert "MANIFEST=" in output
