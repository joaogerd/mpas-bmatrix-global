from __future__ import annotations

from mpas_workflow.case_render_cli import parser


def test_renderer_help_renders_date_format():
    help_text = parser().format_help()
    date_format = chr(37) + "Y-" + chr(37) + "m-" + chr(37) + "d_" + chr(37) + "H:" + chr(37) + "M:" + chr(37) + "S"

    assert date_format in help_text
    assert "--init-time" in help_text
