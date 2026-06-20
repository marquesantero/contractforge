"""Databricks source-level security policy checks."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import JDBC_CONNECTORS, jdbc_common_options
from contractforge_databricks.security.secrets import assert_no_inline_jdbc_secrets


def validate_source_security(source: dict[str, Any]) -> None:
    """Validate adapter security policy before runtime placeholder resolution."""

    source_type = source.get("type")
    connector = source.get("connector")
    if source_type == "jdbc" or connector in JDBC_CONNECTORS:
        assert_no_inline_jdbc_secrets(jdbc_common_options(source))
