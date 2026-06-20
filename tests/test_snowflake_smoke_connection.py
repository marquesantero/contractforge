from __future__ import annotations

from pathlib import Path

import pytest

from contractforge_snowflake.smoke.connection import require_smoke_connection, smoke_connect_options


def test_smoke_connect_options_can_use_connection_name_without_yaml() -> None:
    assert smoke_connect_options(
        connection="cfingestsvc-pat",
        connect_options=None,
        load_connect_options=lambda path: None,
    ) == {"connection_name": "cfingestsvc-pat"}


def test_smoke_connect_options_merges_connection_name_when_yaml_omits_it() -> None:
    assert smoke_connect_options(
        connection="cfingestsvc-pat",
        connect_options=Path("connect.yaml"),
        load_connect_options=lambda path: {"warehouse": "COMPUTE_WH"},
    ) == {"warehouse": "COMPUTE_WH", "connection_name": "cfingestsvc-pat"}


def test_smoke_connect_options_keeps_yaml_connection_name_authoritative() -> None:
    assert smoke_connect_options(
        connection="ignored",
        connect_options=Path("connect.yaml"),
        load_connect_options=lambda path: {"connection_name": "from-yaml"},
    ) == {"connection_name": "from-yaml"}


def test_require_smoke_connection_requires_yaml_or_connection_name() -> None:
    with pytest.raises(ValueError, match="requires --connect-options or --connection"):
        require_smoke_connection(connection=None, connect_options=None, command_name="Snowflake smoke")

    require_smoke_connection(connection="cfingestsvc-pat", connect_options=None, command_name="Snowflake smoke")
