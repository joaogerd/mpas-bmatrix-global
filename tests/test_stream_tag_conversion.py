from __future__ import annotations

from mpas_workflow.case_render import patch_streams_xml


def test_explicit_stream_tag_converts_existing_immutable_stream():
    source = """<streams>
  <immutable_stream name="restart" type="input" filename_template="restart.nc" />
</streams>
"""

    rendered = patch_streams_xml(
        source,
        {
            "restart": {
                "tag": "stream",
                "attributes": {
                    "type": "output",
                    "filename_template": "restart.$Y-$M-$D_$h.$m.$s.nc",
                },
            }
        },
    )

    assert '<stream name="restart"' in rendered
    assert '<immutable_stream name="restart"' not in rendered
    assert 'type="output"' in rendered
    assert 'filename_template="restart.$Y-$M-$D_$h.$m.$s.nc"' in rendered
