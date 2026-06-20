from __future__ import annotations

from contractforge_aws.runtime.athena import AthenaSqlRunner


class FakeAthenaClient:
    def start_query_execution(self, **kwargs):
        self.started = kwargs
        return {"QueryExecutionId": "q-1"}

    def get_query_execution(self, **kwargs):
        return {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}}

    def get_query_results(self, **kwargs):
        return {
            "ResultSet": {
                "Rows": [
                    {"Data": [{"VarCharValue": "status"}, {"VarCharValue": "runs"}]},
                    {"Data": [{"VarCharValue": "SUCCESS"}, {"VarCharValue": "5"}]},
                    {"Data": [{"VarCharValue": "FAILED"}, {"VarCharValue": "1"}]},
                ]
            }
        }


def test_athena_sql_runner_query_returns_named_rows() -> None:
    client = FakeAthenaClient()
    runner = AthenaSqlRunner(
        database="cf_ops",
        output_location="s3://bucket/query-results/",
        athena_client=client,
    )

    rows = runner.query('SELECT status, count(*) AS runs FROM "cf_ops"."ctrl_ingestion_runs" GROUP BY status')

    assert rows == [{"status": "SUCCESS", "runs": "5"}, {"status": "FAILED", "runs": "1"}]
    assert client.started["QueryExecutionContext"] == {"Database": "cf_ops"}
