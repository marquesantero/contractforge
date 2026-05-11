from lakehouse_ingestion.config import CTRL_SCHEMA_VERSION, FRAMEWORK_VERSION
from lakehouse_ingestion.ingestion import _short_error_message


def test_short_error_message_uses_last_traceback_line():
    traceback_text = (
        "Traceback (most recent call last):\n"
        "  File \"job.py\", line 1, in <module>\n"
        "ValueError: invalid contract\n"
    )

    assert _short_error_message(traceback_text) == "ValueError: invalid contract"


def test_framework_and_ctrl_schema_versions_are_current():
    assert FRAMEWORK_VERSION == "1.0.5"
    assert CTRL_SCHEMA_VERSION == 3
