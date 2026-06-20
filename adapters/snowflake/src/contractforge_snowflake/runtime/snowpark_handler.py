"""Snowflake Python stored procedure handler for the library-runner model."""

from __future__ import annotations

import json
from typing import Any

from contractforge_snowflake.runtime.runner import run_snowflake_contract


def run(session: Any, contract_uri: str, environment_uri: str | None = None) -> str:
    """Execute a published ContractForge contract from a Snowflake procedure."""

    result = run_snowflake_contract(
        contract_uri=contract_uri,
        environment_uri=environment_uri,
        session=session,
        set_query_tag=False,
    )
    return json.dumps(result, default=str, sort_keys=True)
