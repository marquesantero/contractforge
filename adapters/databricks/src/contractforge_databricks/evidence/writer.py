"""Evidence writer using an injected SQL runner."""

from __future__ import annotations

from contractforge_core.evidence import (
    AccessEvidenceRecord,
    CostEvidenceRecord,
    ErrorEvidenceRecord,
    LineageEvidenceRecord,
    QualityEvidenceRecord,
    QuarantineEvidenceRecord,
    RunEvidenceRecord,
    SchemaChangeEvidenceRecord,
    SourceMetadataEvidenceRecord,
    StreamBatchEvidenceRecord,
)
from contractforge_databricks.evidence.helpers import TimestampClock
from contractforge_databricks.evidence.ops_log import (
    render_error_log_insert_sql,
    render_schema_change_log_insert_sql,
    render_stream_finish_update_sql,
    render_stream_log_insert_sql,
)
from contractforge_databricks.evidence.governance_log import (
    render_access_log_insert_sql,
    render_annotation_log_insert_sql,
    render_operations_log_insert_sql,
)
from contractforge_databricks.evidence.run_log import render_run_log_insert_sql
from contractforge_databricks.evidence.sql import (
    render_access_insert_sql,
    render_cost_insert_sql,
    render_error_insert_sql,
    render_lineage_insert_sql,
    render_quality_insert_sql,
    render_quarantine_insert_sql,
    render_run_insert_sql,
    render_schema_change_insert_sql,
    render_source_metadata_insert_sql,
    render_stream_batch_insert_sql,
)
from contractforge_databricks.execution.sql_merge import SqlRunner


class EvidenceWriter:
    def __init__(
        self,
        runner: SqlRunner,
        *,
        catalog: str = "main",
        schema: str = "ops",
        clock: TimestampClock | None = None,
    ) -> None:
        self.runner = runner
        self.catalog = catalog
        self.schema = schema
        self.clock = clock

    def write_run(self, record: RunEvidenceRecord) -> None:
        self.runner.sql(render_run_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_run_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_run_log_insert_sql(payload, catalog=self.catalog, schema=self.schema))

    def write_error(self, record: ErrorEvidenceRecord) -> None:
        self.runner.sql(render_error_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_error_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_error_log_insert_sql(payload, catalog=self.catalog, schema=self.schema))

    def write_lineage(self, record: LineageEvidenceRecord) -> None:
        self.runner.sql(render_lineage_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_quality(self, record: QualityEvidenceRecord) -> None:
        self.runner.sql(render_quality_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_schema_change(self, record: SchemaChangeEvidenceRecord) -> None:
        self.runner.sql(render_schema_change_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_schema_change_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_schema_change_log_insert_sql(payload, catalog=self.catalog, schema=self.schema))

    def write_cost(self, record: CostEvidenceRecord) -> None:
        self.runner.sql(render_cost_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_quarantine(self, record: QuarantineEvidenceRecord) -> None:
        self.runner.sql(render_quarantine_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_source_metadata(self, record: SourceMetadataEvidenceRecord) -> None:
        self.runner.sql(render_source_metadata_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_stream_batch(self, record: StreamBatchEvidenceRecord) -> None:
        self.runner.sql(render_stream_batch_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_stream_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_stream_log_insert_sql(payload, catalog=self.catalog, schema=self.schema, clock=self.clock))

    def finish_stream_log(self, *, stream_run_id: str, payload: dict[str, object]) -> None:
        statement = render_stream_finish_update_sql(
            stream_run_id=stream_run_id,
            payload=payload,
            catalog=self.catalog,
            schema=self.schema,
        )
        if statement is not None:
            self.runner.sql(statement)

    def write_access(self, record: AccessEvidenceRecord) -> None:
        self.runner.sql(render_access_insert_sql(record, catalog=self.catalog, schema=self.schema))

    def write_annotation_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_annotation_log_insert_sql(payload, catalog=self.catalog, schema=self.schema, clock=self.clock))

    def write_access_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_access_log_insert_sql(payload, catalog=self.catalog, schema=self.schema, clock=self.clock))

    def write_operations_log(self, payload: dict[str, object]) -> None:
        self.runner.sql(render_operations_log_insert_sql(payload, catalog=self.catalog, schema=self.schema, clock=self.clock))
