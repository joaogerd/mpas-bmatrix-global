from mpas_workflow.wps import REQUIRED_WPS_FIELDS, missing_wps_fields


def test_missing_wps_fields_reports_absent_labels(tmp_path):
    artifact = tmp_path / "FILE:2026-06-18_00"
    artifact.write_bytes(b"PSFC\x00PMSL\x00LANDSEA\x00")

    assert missing_wps_fields(artifact) == [
        "LANDN",
        "SOILHGT",
        "SKINTEMP",
    ]


def test_missing_wps_fields_accepts_complete_minimum_contract(tmp_path):
    artifact = tmp_path / "FILE:2026-06-18_00"
    artifact.write_bytes(b"\x00".join(field.encode("ascii") for field in REQUIRED_WPS_FIELDS))

    assert missing_wps_fields(artifact) == []
