"""AWS Lake Formation grant / data-filter artifact rendering."""

from __future__ import annotations

import json

from contractforge_aws import (
    apply_aws_lake_formation_contract,
    apply_aws_lake_formation_plan,
    plan_aws_contract,
    render_aws_contract,
    render_aws_lake_formation_evidence_sql,
    render_aws_lake_formation_plan,
)
from contractforge_aws.smoke.lakeformation import LakeFormationMatrixConfig, execute_preflight
from contractforge_aws.smoke.lakeformation_athena import AthenaReadValidationConfig, validate_athena_reads
from contractforge_aws.smoke.lakeformation_glue import GlueReadValidationConfig, validate_glue_reads


class FakeLakeFormationClient:
    def __init__(self) -> None:
        self.grants: list[dict] = []
        self.filters: list[dict] = []

    def grant_permissions(self, **kwargs: dict) -> None:
        self.grants.append(kwargs)

    def create_data_cells_filter(self, **kwargs: dict) -> None:
        self.filters.append(kwargs)


class _FakeBoto3:
    def client(self, service: str, region_name: str | None = None) -> object:
        if service == "sts":
            return _FakeSts()
        if service == "glue":
            return _FakeGlue()
        if service == "lakeformation":
            return _FakeLakeFormationMatrixClient()
        if service == "athena":
            return _FakeAthena()
        raise AssertionError(service)


class _FakeBoto3Registered:
    def __init__(self, permissions: list[dict]) -> None:
        self.permissions = permissions

    def client(self, service: str, region_name: str | None = None) -> object:
        if service == "sts":
            return _FakeSts()
        if service == "glue":
            return _FakeRegisteredGlue()
        if service == "lakeformation":
            return _FakeLakeFormationMatrixClientWithPermissions(self.permissions)
        if service == "athena":
            return _FakeAthena()
        raise AssertionError(service)


class _FakeSts:
    def get_caller_identity(self) -> dict:
        return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:root"}


class _FakeGlue:
    def get_table(self, **kwargs: dict) -> dict:
        return {
            "Table": {
                "DatabaseName": kwargs["DatabaseName"],
                "Name": kwargs["Name"],
                "IsRegisteredWithLakeFormation": False,
                "TableType": "EXTERNAL_TABLE",
                "StorageDescriptor": {"Location": "s3://bucket/table"},
            }
        }


class _FakeRegisteredGlue:
    def get_table(self, **kwargs: dict) -> dict:
        return {
            "Table": {
                "DatabaseName": kwargs["DatabaseName"],
                "Name": kwargs["Name"],
                "IsRegisteredWithLakeFormation": True,
                "TableType": "EXTERNAL_TABLE",
                "StorageDescriptor": {"Location": "s3://bucket/table"},
            }
        }


class _FakeLakeFormationMatrixClient:
    def list_permissions(self, **kwargs: dict) -> dict:
        return {"PrincipalResourcePermissions": []}

    def list_data_cells_filter(self, **kwargs: dict) -> dict:
        return {"DataCellsFilters": []}


class _FakeLakeFormationMatrixClientWithPermissions:
    def __init__(self, permissions: list[dict]) -> None:
        self.permissions = permissions

    def list_permissions(self, **kwargs: dict) -> dict:
        return {"PrincipalResourcePermissions": self.permissions}

    def list_data_cells_filter(self, **kwargs: dict) -> dict:
        return {
            "DataCellsFilters": [
                {
                    "TableCatalogId": "123456789012",
                    "DatabaseName": kwargs["Table"]["DatabaseName"],
                    "TableName": kwargs["Table"]["Name"],
                    "Name": "country_filter",
                    "RowFilter": {"FilterExpression": "country = 'BR'"},
                    "ColumnNames": ["id", "country"],
                }
            ]
        }


class _FakeAthena:
    def get_work_group(self, **kwargs: dict) -> dict:
        return {"WorkGroup": {"Name": kwargs["WorkGroup"], "State": "ENABLED"}}


class _FakeAthenaQuery:
    def __init__(self, state: str) -> None:
        self.state = state
        self.query_id = f"query-{state.lower()}"

    def start_query_execution(self, **kwargs: dict) -> dict:
        return {"QueryExecutionId": self.query_id}

    def get_query_execution(self, **kwargs: dict) -> dict:
        return {
            "QueryExecution": {
                "QueryExecutionId": self.query_id,
                "Status": {"State": self.state, "StateChangeReason": "Access denied by Lake Formation"},
            }
        }

    def get_query_results(self, **kwargs: dict) -> dict:
        return {"ResultSet": {"Rows": [{"Data": [{"VarCharValue": "c"}]}, {"Data": [{"VarCharValue": "3"}]}]}}


class _FakeStsAssume:
    def assume_role(self, **kwargs: dict) -> dict:
        return {
            "Credentials": {
                "AccessKeyId": "ak",
                "SecretAccessKey": "sk",
                "SessionToken": "token",
            }
        }


class _FakeBoto3AthenaValidation:
    def __init__(self) -> None:
        self.states: list[str] = []

    def client(self, service: str, region_name: str | None = None) -> object:
        if service == "sts":
            return _FakeStsAssume()
        raise AssertionError(service)

    def Session(self, **kwargs: str) -> object:  # noqa: N802 - mirrors boto3 API
        state = "SUCCEEDED" if not self.states else "FAILED"
        self.states.append(state)
        return _FakeAthenaSession(state)


class _FakeStsRootBlocked:
    def assume_role(self, **kwargs: dict) -> dict:
        raise RuntimeError("An error occurred (AccessDenied) when calling the AssumeRole operation: Roles may not be assumed by root accounts.")


class _FakeBoto3RootBlocked:
    def client(self, service: str, region_name: str | None = None) -> object:
        if service == "sts":
            return _FakeStsRootBlocked()
        raise AssertionError(service)


class _FakeAthenaSession:
    def __init__(self, state: str) -> None:
        self.state = state

    def client(self, service: str, region_name: str | None = None) -> object:
        assert service == "athena"
        return _FakeAthenaQuery(self.state)


class _FakeGlueReadClient:
    def __init__(self) -> None:
        self.states: list[str] = []

    def get_job(self, **kwargs: dict) -> dict:
        return {"Job": {"Name": kwargs["JobName"]}}

    def update_job(self, **kwargs: dict) -> dict:
        return {}

    def start_job_run(self, **kwargs: dict) -> dict:
        state = "SUCCEEDED" if not self.states else "FAILED"
        self.states.append(state)
        return {"JobRunId": f"jr-{state.lower()}"}

    def get_job_run(self, **kwargs: dict) -> dict:
        state = "SUCCEEDED" if kwargs["RunId"].endswith("succeeded") else "FAILED"
        return {"JobRun": {"JobRunState": state, "ErrorMessage": "Access denied by Lake Formation"}}


class _FakeBoto3GlueValidation:
    def __init__(self) -> None:
        self.glue = _FakeGlueReadClient()

    def client(self, service: str, region_name: str | None = None) -> object:
        if service == "glue":
            return self.glue
        raise AssertionError(service)


def _contract(access: dict) -> dict:
    return {
        "source": {"type": "parquet", "path": "s3://landing/customers"},
        "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
        "mode": "scd0_append",
        "access": access,
    }


def test_grants_map_to_lake_formation_permissions() -> None:
    plan = json.loads(
        render_aws_lake_formation_plan(
            _contract({"grants": [{"principal": "arn:aws:iam::111:role/Analyst", "privileges": ["select", "describe"]}]})
        )
    )

    assert plan["resource"] == {"DatabaseName": "lake_silver", "TableName": "customers"}
    grant = plan["permissions"][0]
    assert grant["Principal"]["DataLakePrincipalIdentifier"] == "arn:aws:iam::111:role/Analyst"
    assert grant["Resource"]["Table"] == {"DatabaseName": "lake_silver", "Name": "customers"}
    assert grant["Permissions"] == ["SELECT", "DESCRIBE"]


def test_row_filter_renders_fail_closed_data_cells_filter() -> None:
    plan = json.loads(
        render_aws_lake_formation_plan(
            _contract(
                {
                    "row_filters": [
                        {
                            "name": "country_filter",
                            "function": "security.country_filter",
                            "columns": ["country"],
                            "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                        }
                    ]
                }
            )
        )
    )

    entry = plan["data_cells_filters"][0]
    table_data = entry["create_data_cells_filter"]["TableData"]
    assert table_data["Name"] == "country_filter"
    assert table_data["RowFilter"] == {"FilterExpression": "false"}  # fail-closed
    assert table_data["ColumnWildcard"] == {}
    assert entry["grants"][0]["Resource"]["DataCellsFilter"]["Name"] == "country_filter"
    assert entry["grants"][0]["Permissions"] == ["SELECT"]
    assert "security.country_filter" in entry["todo"]


def test_column_mask_excludes_column_and_documents_gap() -> None:
    plan = json.loads(
        render_aws_lake_formation_plan(
            _contract(
                {
                    "column_masks": [
                        {
                            "column": "ssn",
                            "function": "security.mask_ssn",
                            "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                        }
                    ]
                }
            )
        )
    )

    entry = plan["data_cells_filters"][0]
    table_data = entry["create_data_cells_filter"]["TableData"]
    assert table_data["Name"] == "ssn_mask"
    assert table_data["RowFilter"] == {"AllRowsWildcard": {}}
    assert table_data["ColumnWildcard"] == {"ExcludedColumnNames": ["ssn"]}
    assert "no value-masking function" in entry["todo"]


def test_no_access_section_renders_empty() -> None:
    assert render_aws_lake_formation_plan(
        {
            "source": {"type": "parquet", "path": "s3://landing/customers"},
            "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
        }
    ) == ""


def test_lake_formation_artifact_is_published() -> None:
    artifacts = render_aws_contract(
        _contract({"grants": [{"principal": "arn:aws:iam::111:role/Analyst", "privileges": "select"}]})
    )

    assert "lake_silver_customers.lakeformation.json" in artifacts.artifacts
    assert "lake_silver_customers.lakeformation_evidence.sql" in artifacts.artifacts


def test_lake_formation_evidence_records_grants_and_review_required_filters() -> None:
    sql = render_aws_lake_formation_evidence_sql(
        _contract(
            {
                "grants": [{"principal": "arn:aws:iam::111:role/Analyst", "privileges": ["select"]}],
                "row_filters": [
                    {
                        "name": "country_filter",
                        "function": "security.country_filter",
                        "columns": ["country"],
                        "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                    }
                ],
                "column_masks": [
                    {
                        "column": "ssn",
                        "function": "security.mask_ssn",
                        "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                    }
                ],
            }
        ),
        run_id="run-1",
    )

    assert "INSERT INTO glue_catalog.`lake_silver_ops`.`ctrl_ingestion_access`" in sql
    assert "'grant_permissions'" in sql
    assert "'PLANNED'" in sql
    assert "'create_data_cells_filter'" in sql
    assert "'REVIEW_REQUIRED'" in sql
    assert "'row_filter'" in sql
    assert "'column_mask'" in sql
    assert "'ssn'" in sql


def test_row_filter_still_requires_review_planning_status() -> None:
    result = plan_aws_contract(
        _contract(
            {
                "row_filters": [
                    {"name": "country_filter", "function": "security.country_filter", "columns": ["country"]}
                ]
            }
        )
    )

    # The LF artifact does not change planning status; row filters stay REVIEW_REQUIRED.
    assert result.status == "REVIEW_REQUIRED"


def test_apply_lake_formation_plan_applies_grants_and_skips_filters_by_default() -> None:
    plan = render_aws_lake_formation_plan(
        _contract(
            {
                "grants": [{"principal": "arn:aws:iam::111:role/Analyst", "privileges": "select"}],
                "row_filters": [
                    {
                        "name": "country_filter",
                        "function": "security.country_filter",
                        "columns": ["country"],
                        "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                    }
                ],
            }
        )
    )
    client = FakeLakeFormationClient()

    result = apply_aws_lake_formation_plan(plan, lakeformation_client=client)

    assert result.permissions_granted == 1
    assert result.skipped_data_cells_filters == 1
    assert result.data_cells_filters_created == 0
    assert len(client.grants) == 1
    assert client.filters == []


def test_apply_lake_formation_plan_requires_account_id_for_filters() -> None:
    plan = render_aws_lake_formation_plan(
        _contract(
            {
                "column_masks": [
                    {
                        "column": "ssn",
                        "function": "security.mask_ssn",
                        "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                    }
                ]
            }
        )
    )

    try:
        apply_aws_lake_formation_plan(plan, lakeformation_client=FakeLakeFormationClient(), allow_data_cells_filters=True)
    except ValueError as exc:
        assert "account_id is required" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected account_id validation error")


def test_apply_lake_formation_plan_can_apply_reviewed_filters() -> None:
    plan = render_aws_lake_formation_plan(
        _contract(
            {
                "column_masks": [
                    {
                        "column": "ssn",
                        "function": "security.mask_ssn",
                        "applies_to": {"principals": ["arn:aws:iam::111:role/Analyst"]},
                    }
                ]
            }
        )
    )
    client = FakeLakeFormationClient()

    result = apply_aws_lake_formation_plan(
        plan,
        lakeformation_client=client,
        account_id="123456789012",
        allow_data_cells_filters=True,
    )

    assert result.data_cells_filters_created == 1
    assert result.data_cells_filter_grants == 1
    assert client.filters[0]["TableData"]["TableCatalogId"] == "123456789012"
    assert client.grants[0]["Resource"]["DataCellsFilter"]["TableCatalogId"] == "123456789012"


def test_apply_lake_formation_contract_renders_and_applies_plan() -> None:
    client = FakeLakeFormationClient()

    result = apply_aws_lake_formation_contract(
        _contract({"grants": [{"principal": "arn:aws:iam::111:role/Analyst", "privileges": "select"}]}),
        lakeformation_client=client,
    )

    assert result.permissions_granted == 1
    assert client.grants[0]["Permissions"] == ["SELECT"]


def test_lake_formation_consumer_matrix_preflight_blocks_unregistered_table(monkeypatch) -> None:
    import contractforge_aws.smoke.lakeformation as smoke_lakeformation

    monkeypatch.setattr(smoke_lakeformation, "require_boto3", lambda: _FakeBoto3())

    result = execute_preflight(
        LakeFormationMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            database="lake_silver",
            table="customers",
            consumer_principal=None,
            athena_workgroup="primary",
            athena_output_location=None,
        )
    )

    assert result["status"] == "BLOCKED"
    assert "Glue table is not registered with Lake Formation." in result["blockers"]
    assert "No non-root consumer principal was provided." in result["blockers"]
    assert "No Lake Formation DataCellsFilter exists for the declared table." in result["blockers"]


def test_lake_formation_consumer_matrix_blocks_iam_allowed_principals(monkeypatch) -> None:
    import contractforge_aws.smoke.lakeformation as smoke_lakeformation

    permissions = [
        {
            "Principal": {"DataLakePrincipalIdentifier": "IAM_ALLOWED_PRINCIPALS"},
            "Resource": {"Table": {"CatalogId": "123456789012", "DatabaseName": "lake_silver", "Name": "customers"}},
            "Permissions": ["ALL"],
        }
    ]
    monkeypatch.setattr(smoke_lakeformation, "require_boto3", lambda: _FakeBoto3Registered(permissions))

    result = execute_preflight(
        LakeFormationMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            database="lake_silver",
            table="customers",
            consumer_principal="arn:aws:iam::123456789012:role/Consumer",
            athena_workgroup="primary",
            athena_output_location="s3://bucket/athena/",
        )
    )

    assert result["status"] == "BLOCKED"
    assert any("IAM_ALLOWED_PRINCIPALS has broad table access" in item for item in result["blockers"])


def test_lake_formation_consumer_matrix_blocks_unfiltered_consumer_select(monkeypatch) -> None:
    import contractforge_aws.smoke.lakeformation as smoke_lakeformation

    consumer = "arn:aws:iam::123456789012:role/Consumer"
    permissions = [
        {
            "Principal": {"DataLakePrincipalIdentifier": consumer},
            "Resource": {"Table": {"CatalogId": "123456789012", "DatabaseName": "lake_silver", "Name": "customers"}},
            "Permissions": ["SELECT"],
        }
    ]
    monkeypatch.setattr(smoke_lakeformation, "require_boto3", lambda: _FakeBoto3Registered(permissions))

    result = execute_preflight(
        LakeFormationMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            database="lake_silver",
            table="customers",
            consumer_principal=consumer,
            athena_workgroup="primary",
            athena_output_location="s3://bucket/athena/",
        )
    )

    assert result["status"] == "BLOCKED"
    assert any("unfiltered table SELECT/ALL access" in item for item in result["blockers"])


def test_lake_formation_consumer_matrix_marks_athena_validation_pending_without_roles(monkeypatch) -> None:
    import contractforge_aws.smoke.lakeformation as smoke_lakeformation

    monkeypatch.setattr(smoke_lakeformation, "require_boto3", lambda: _FakeBoto3Registered([]))

    result = execute_preflight(
        LakeFormationMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            database="lake_silver",
            table="customers",
            consumer_principal="arn:aws:iam::123456789012:role/Consumer",
            athena_workgroup="primary",
            athena_output_location="s3://bucket/athena/",
            validate_athena_reads=True,
        )
    )

    assert result["status"] == "READ_VALIDATION_PENDING"
    assert result["athena_read_validation"]["status"] == "READ_VALIDATION_PENDING"


def test_lake_formation_consumer_matrix_allows_read_validation_when_filter_is_not_listable(monkeypatch) -> None:
    import contractforge_aws.smoke.lakeformation as smoke_lakeformation

    monkeypatch.setattr(smoke_lakeformation, "require_boto3", lambda: _FakeBoto3Registered([]))
    monkeypatch.setattr(smoke_lakeformation, "_data_cells_filters", lambda lakeformation, config: {"count": 0, "filters": []})
    monkeypatch.setattr(
        smoke_lakeformation,
        "athena_validation",
        lambda boto3, config, blockers: {"status": "PASS", "cases": {"allowed_role_count": {}, "denied_role_count": {}}},
    )

    result = execute_preflight(
        LakeFormationMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            database="lake_silver",
            table="customers",
            consumer_principal="arn:aws:iam::123456789012:role/Consumer",
            athena_workgroup="primary",
            athena_output_location="s3://bucket/athena/",
            validate_athena_reads=True,
            athena_allowed_role_arn="arn:aws:iam::123456789012:role/Allowed",
            athena_denied_role_arn="arn:aws:iam::123456789012:role/Denied",
        )
    )

    assert result["status"] == "PASS"
    assert "No Lake Formation DataCellsFilter exists for the declared table." in result["blockers"]


def test_lake_formation_athena_validation_passes_allowed_success_and_denied_failure() -> None:
    result = validate_athena_reads(
        _FakeBoto3AthenaValidation(),
        AthenaReadValidationConfig(
            region="us-east-1",
            database="lake_silver",
            table="customers",
            workgroup="primary",
            output_location="s3://bucket/athena/",
            allowed_role_arn="arn:aws:iam::123456789012:role/Allowed",
            denied_role_arn="arn:aws:iam::123456789012:role/Denied",
            poll_interval_seconds=0,
            max_wait_seconds=1,
        ),
    )

    assert result["status"] == "PASS"
    assert result["cases"]["allowed_role_count"]["row_count"] == 3
    assert result["cases"]["denied_role_count"]["expected_failure"] is True


def test_lake_formation_athena_validation_marks_root_assume_role_block_pending() -> None:
    result = validate_athena_reads(
        _FakeBoto3RootBlocked(),
        AthenaReadValidationConfig(
            region="us-east-1",
            database="lake_silver",
            table="customers",
            workgroup="primary",
            output_location="s3://bucket/athena/",
            allowed_role_arn="arn:aws:iam::123456789012:role/Allowed",
            denied_role_arn="arn:aws:iam::123456789012:role/Denied",
            poll_interval_seconds=0,
            max_wait_seconds=1,
        ),
    )

    assert result["status"] == "READ_VALIDATION_PENDING"
    assert result["cases"]["allowed_role_count"]["status"] == "READ_VALIDATION_PENDING"
    assert result["cases"]["denied_role_count"]["status"] == "READ_VALIDATION_PENDING"


def test_lake_formation_consumer_matrix_marks_glue_validation_pending_without_script(monkeypatch) -> None:
    import contractforge_aws.smoke.lakeformation as smoke_lakeformation

    monkeypatch.setattr(smoke_lakeformation, "require_boto3", lambda: _FakeBoto3Registered([]))

    result = execute_preflight(
        LakeFormationMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            database="lake_silver",
            table="customers",
            consumer_principal="arn:aws:iam::123456789012:role/Consumer",
            athena_workgroup="primary",
            athena_output_location="s3://bucket/athena/",
            validate_glue_reads=True,
        )
    )

    assert result["status"] == "READ_VALIDATION_PENDING"
    assert result["glue_read_validation"]["status"] == "READ_VALIDATION_PENDING"


def test_lake_formation_glue_validation_passes_allowed_success_and_denied_failure() -> None:
    result = validate_glue_reads(
        _FakeBoto3GlueValidation(),
        GlueReadValidationConfig(
            region="us-east-1",
            database="lake_silver",
            table="customers",
            script_s3_uri="s3://bucket/scripts/read.py",
            allowed_role_arn="arn:aws:iam::123456789012:role/GlueAllowed",
            denied_role_arn="arn:aws:iam::123456789012:role/GlueDenied",
            poll_interval_seconds=0,
            max_wait_seconds=1,
        ),
    )

    assert result["status"] == "PASS"
    assert result["cases"]["allowed_role_count"]["state"] == "SUCCEEDED"
    assert result["cases"]["denied_role_count"]["expected_failure"] is True
