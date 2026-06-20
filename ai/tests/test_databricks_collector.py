from contractforge_ai.context import collect_databricks_run_evidence


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows


class FakeSpark:
    def __init__(self, responses, failures=None):
        self.responses = responses
        self.failures = failures or {}
        self.queries = []

    def sql(self, query):
        self.queries.append(query)
        for marker, exc in self.failures.items():
            if marker in query:
                raise exc
        for marker, rows in self.responses.items():
            if marker in query:
                return FakeDataFrame(rows)
        return FakeDataFrame([])


def test_collect_databricks_run_evidence_queries_control_tables_and_redacts():
    spark = FakeSpark(
        {
            "ctrl_ingestion_runs": [
                {
                    "run_id": "run-1",
                    "status": "FAILED",
                    "source_auth": {"password": "plain-text"},
                    "error_message": "Access denied",
                }
            ],
            "ctrl_ingestion_errors": [{"run_id": "run-1", "stack_trace": "Permission denied"}],
            "ctrl_ingestion_quality": [{"run_id": "run-1", "failed_count": 2}],
            "ctrl_ingestion_streams": [{"stream_run_id": "run-1", "batches_processed": 1}],
        }
    )

    evidence = collect_databricks_run_evidence(
        run_id="run-1",
        catalog="main",
        ctrl_schema="ops",
        spark=spark,
    )

    assert evidence["run"]["run_id"] == "run-1"
    assert evidence["run"]["source_auth"]["password"].startswith("[REDACTED")
    assert evidence["errors"][0]["stack_trace"] == "Permission denied"
    assert evidence["quality"][0]["failed_count"] == 2
    assert evidence["streams"][0]["batches_processed"] == 1
    assert evidence["collection"]["tables"]["run"] == "`main`.`ops`.`ctrl_ingestion_runs`"
    assert len(spark.queries) == 4


def test_collect_databricks_run_evidence_records_missing_optional_tables():
    spark = FakeSpark(
        {"ctrl_ingestion_runs": [{"run_id": "run-2", "status": "FAILED"}]},
        failures={"ctrl_ingestion_errors": RuntimeError("table not found")},
    )

    evidence = collect_databricks_run_evidence(
        run_id="run-2",
        catalog="main",
        ctrl_schema="ops",
        spark=spark,
    )

    assert evidence["run"]["status"] == "FAILED"
    assert evidence["errors"] == []
    assert evidence["collection"]["collection_errors"][0]["kind"] == "errors"
    assert "table not found" in evidence["collection"]["collection_errors"][0]["error_message"]


def test_collect_databricks_run_evidence_escapes_identifiers_and_run_id():
    spark = FakeSpark({"ctrl_ingestion_runs": []})

    collect_databricks_run_evidence(
        run_id="run-'quoted'",
        catalog="main-cat",
        ctrl_schema="ops`schema",
        spark=spark,
    )

    assert "`main-cat`.`ops``schema`.`ctrl_ingestion_runs`" in spark.queries[0]
    assert "'run-''quoted'''" in spark.queries[0]
