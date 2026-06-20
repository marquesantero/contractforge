import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_snowflake.runtime.schema_policy import enforce_schema_policy, source_column_types_for, target_column_types_for


def _contract(payload: dict | None = None):
    base = {
        "source": {"type": "table", "table": "raw.customers"},
        "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
        "mode": "scd0_append",
        "schema_policy": "additive_only",
    }
    if payload:
        base.update(payload)
    return semantic_contract_from_mapping(base)


def test_snowflake_target_schema_prefers_information_schema() -> None:
    session = _SchemaSession(
        info_schema_rows=[("CUSTOMER_ID", "NUMBER"), ("NAME", "VARCHAR")],
        target_columns=("fallback",),
    )

    columns = target_column_types_for(session, '"ANALYTICS"."BRONZE"."CUSTOMERS"')

    assert columns == {"CUSTOMER_ID": "NUMBER", "NAME": "VARCHAR"}
    assert not any(command.startswith('SELECT * FROM "ANALYTICS"."BRONZE"."CUSTOMERS"') for command in session.commands)


def test_snowflake_target_schema_falls_back_to_connector_metadata() -> None:
    session = _SchemaSession(info_schema_rows=[], target_columns=("CUSTOMER_ID", "NAME"))

    columns = target_column_types_for(session, '"ANALYTICS"."BRONZE"."CUSTOMERS"')

    assert columns == {"CUSTOMER_ID": "VARIANT", "NAME": "VARIANT"}
    assert any(command.startswith('SELECT * FROM "ANALYTICS"."BRONZE"."CUSTOMERS"') for command in session.commands)


def test_snowflake_schema_policy_records_information_schema_fallback_warning() -> None:
    session = _SchemaSession(
        source_columns=("CUSTOMER_ID", "NAME"),
        info_schema_error=RuntimeError("metadata denied password=raw-secret"),
        target_columns=("CUSTOMER_ID", "NAME"),
    )

    result = enforce_schema_policy(
        session=session,
        contract=_contract(),
        source_sql='SELECT * FROM "raw"."customers"',
        target='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.schema_changes["warnings"][0].startswith("information_schema_unavailable: RuntimeError:")
    assert "raw-secret" not in result.schema_changes["warnings"][0]
    assert "***REDACTED***" in result.schema_changes["warnings"][0]
    assert any(command.startswith('SELECT * FROM "ANALYTICS"."BRONZE"."CUSTOMERS"') for command in session.commands)


def test_snowflake_source_schema_prefers_typed_fields_over_names_fallback() -> None:
    session = _SchemaSession(
        source_columns=("CUSTOMER_ID", "EMAIL"),
        source_types={"CUSTOMER_ID": "NUMBER", "EMAIL": "VARCHAR"},
    )

    columns = source_column_types_for(session, 'SELECT * FROM "raw"."customers"')

    assert columns == {"CUSTOMER_ID": "NUMBER", "EMAIL": "VARCHAR"}


def test_snowflake_additive_policy_returns_applied_schema_changes() -> None:
    session = _SchemaSession(
        source_columns=("CUSTOMER_ID", "NAME", "EMAIL"),
        source_types={"CUSTOMER_ID": "NUMBER", "NAME": "VARCHAR", "EMAIL": "VARCHAR"},
        info_schema_rows=[("CUSTOMER_ID", "NUMBER"), ("NAME", "VARCHAR")],
    )

    result = enforce_schema_policy(
        session=session,
        contract=_contract(),
        source_sql='SELECT * FROM "raw"."customers"',
        target='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.commands == ('ALTER TABLE "ANALYTICS"."BRONZE"."CUSTOMERS" ADD COLUMN IF NOT EXISTS "EMAIL" VARCHAR',)
    assert result.schema_changes["added_columns"] == (
        {
            "column": "EMAIL",
            "source_type": "VARCHAR",
            "target_type": None,
            "change_type": "ADD_COLUMN",
            "applied": True,
        },
    )


def test_snowflake_additive_policy_allows_missing_overwrite_target() -> None:
    session = _SchemaSession(
        source_columns=("CUSTOMER_ID", "NAME"),
        source_types={"CUSTOMER_ID": "NUMBER", "NAME": "VARCHAR"},
        info_schema_rows=[],
        target_error=RuntimeError("Object 'ANALYTICS.BRONZE.CUSTOMERS' does not exist or not authorized"),
    )

    result = enforce_schema_policy(
        session=session,
        contract=_contract({"mode": "scd0_overwrite"}),
        source_sql='SELECT * FROM "raw"."customers"',
        target='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.commands == ()
    assert result.source_columns == ("CUSTOMER_ID", "NAME")
    assert result.target_columns == ("CUSTOMER_ID", "NAME")
    assert "target_schema_unavailable" in result.schema_changes["warnings"][0]


def test_snowflake_additive_policy_allows_lazy_missing_overwrite_target() -> None:
    session = _SchemaSession(
        source_columns=("CUSTOMER_ID", "NAME"),
        source_types={"CUSTOMER_ID": "NUMBER", "NAME": "VARCHAR"},
        info_schema_rows=[],
        target_lazy_error=RuntimeError("Object 'ANALYTICS.BRONZE.CUSTOMERS' does not exist or not authorized"),
    )

    result = enforce_schema_policy(
        session=session,
        contract=_contract({"mode": "scd0_overwrite"}),
        source_sql='SELECT * FROM "raw"."customers"',
        target='"ANALYTICS"."BRONZE"."CUSTOMERS"',
    )

    assert result.commands == ()
    assert result.target_columns == ("CUSTOMER_ID", "NAME")
    assert "target_schema_unavailable" in result.schema_changes["warnings"][0]


def test_snowflake_schema_policy_rejects_incompatible_type_changes() -> None:
    session = _SchemaSession(
        source_columns=("CUSTOMER_ID", "EMAIL"),
        source_types={"CUSTOMER_ID": "NUMBER", "EMAIL": "VARCHAR"},
        info_schema_rows=[("CUSTOMER_ID", "NUMBER"), ("EMAIL", "NUMBER")],
    )

    with pytest.raises(ValueError, match="incompatible type changes"):
        enforce_schema_policy(
            session=session,
            contract=_contract(),
            source_sql='SELECT * FROM "raw"."customers"',
            target='"ANALYTICS"."BRONZE"."CUSTOMERS"',
        )


class _SchemaSession:
    def __init__(
        self,
        *,
        source_columns=("CUSTOMER_ID", "NAME"),
        source_types=None,
        target_columns=(),
        info_schema_rows=None,
        info_schema_error=None,
        target_error=None,
        target_lazy_error=None,
    ) -> None:
        self.commands: list[str] = []
        self._source_columns = source_columns
        self._source_types = source_types or {column: "VARIANT" for column in source_columns}
        self._target_columns = target_columns
        self._info_schema_rows = info_schema_rows
        self._info_schema_error = info_schema_error
        self._target_error = target_error
        self._target_lazy_error = target_lazy_error

    def sql(self, command: str):
        self.commands.append(command)
        if "INFORMATION_SCHEMA.COLUMNS" in command:
            if self._info_schema_error:
                raise self._info_schema_error
            return _Result(self._info_schema_rows or [])
        if command.startswith("SELECT * FROM (\n"):
            return _Result([], schema=_Schema(self._source_columns, self._source_types))
        if command.startswith('SELECT * FROM "ANALYTICS"."BRONZE"."CUSTOMERS"'):
            if self._target_error:
                raise self._target_error
            if self._target_lazy_error:
                return _LazySchemaErrorResult(self._target_lazy_error)
            return _Result([], schema=_Schema(self._target_columns, {}))
        return _Result([])


class _Result:
    def __init__(self, rows, *, schema=None):
        self._rows = rows
        self.schema = schema

    def collect(self):
        return self._rows


class _LazySchemaErrorResult:
    def __init__(self, error):
        self._error = error

    @property
    def schema(self):
        raise self._error


class _Schema:
    def __init__(self, names, types):
        self.fields = tuple(_Field(name, types.get(name, "VARIANT")) for name in names)


class _Field:
    def __init__(self, name, datatype):
        self.name = name
        self.datatype = datatype
