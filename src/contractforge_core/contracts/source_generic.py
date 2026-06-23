"""Generic portable and passthrough source contract model."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from contractforge_core.contracts.base import StrictContractModel


SourceIntentName = Literal[
    "api_call",
    "catalog_query",
    "custom_treatment",
    "database_query",
    "file_batch",
    "file_stream",
    "native_handoff",
    "object_files",
    "stream_replay",
]

DiscoveryStrategy = Literal["event_driven", "file_listing", "queue_based"]
DiscoveryTracking = Literal["external_queue", "external_state", "filename_pattern", "modification_time"]
StateStorage = Literal["adapter_managed", "external", "job_local"]
StateLocationType = Literal["database_table", "key_value_store", "object_storage"]


class SourceDiscoveryContract(StrictContractModel):
    strategy: DiscoveryStrategy | None = None
    tracking: DiscoveryTracking | None = None
    pattern: str | None = None
    queue: str | None = None


class SourceStateLocationContract(StrictContractModel):
    type: StateLocationType
    path: str | None = None
    table: str | None = None
    key: str | None = None

    @model_validator(mode="after")
    def _requires_target(self) -> "SourceStateLocationContract":
        if self.path or self.table or self.key:
            return self
        raise ValueError("source.state.location requires path, table or key")


class SourceStateContract(StrictContractModel):
    storage: StateStorage = "adapter_managed"
    location: SourceStateLocationContract | None = None

    @model_validator(mode="after")
    def _external_requires_location(self) -> "SourceStateContract":
        if self.storage == "external" and self.location is None:
            raise ValueError("source.state.storage='external' requires source.state.location")
        return self


class SourceTableReferenceContract(StrictContractModel):
    """Portable logical reference to another contract-managed table."""

    layer: str
    table: str
    schema_: str | None = Field(default=None, alias="schema")
    catalog: str | None = None


class SourceInputReferenceContract(StrictContractModel):
    """Named input consumed by a custom treatment boundary."""

    alias: str
    ref: str | None = None
    table: str | None = None
    table_ref: str | SourceTableReferenceContract | None = None
    path: str | None = None
    query: Any = None

    @model_validator(mode="after")
    def _requires_reference(self) -> "SourceInputReferenceContract":
        if self.ref or self.table or self.table_ref or self.path or self.query not in (None, ""):
            return self
        raise ValueError("source input requires one of ref, table, table_ref, path or query")


class GenericSourceContract(StrictContractModel):
    """Portable and passthrough source contract shape."""

    type: str
    intent: SourceIntentName | None = None
    name: str | None = None
    format: str | None = None
    path: str | None = None
    table: str | None = None
    ref: str | None = None
    table_ref: str | SourceTableReferenceContract | None = None
    inputs: list[SourceInputReferenceContract] | None = None
    query: Any = None
    url: str | None = None
    system: str | None = None
    object: str | None = None
    connection_path: str | None = None
    progress_location: str | None = None
    schema_tracking_location: str | None = None
    schema_hints: str | dict[str, Any] | None = None
    trigger: str | None = None
    bootstrap_servers: str | None = None
    topic: str | None = None
    topics: list[str] | None = None
    assign: str | dict[str, Any] | None = None
    starting_offsets: str | dict[str, Any] | None = None
    ending_offsets: str | dict[str, Any] | None = None
    starting_timestamp: str | None = None
    ending_timestamp: str | None = None
    max_offsets_per_trigger: int | None = Field(default=None, gt=0)
    connection_string: str | None = None
    event_hub_name: str | None = None
    profile_file: str | None = None
    starting_position: str | dict[str, Any] | None = None
    ending_position: str | dict[str, Any] | None = None
    max_events_per_trigger: int | None = Field(default=None, gt=0)
    checkpoint_location: str | None = None
    discovery: SourceDiscoveryContract | None = None
    state: SourceStateContract | None = None
    read: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    watermark: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    pagination: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    incremental: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _type_name(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _custom_transform_requires_named_inputs(self) -> "GenericSourceContract":
        if self.type != "custom_transform":
            return self
        if not self.inputs:
            raise ValueError("source.inputs is required for connector=custom_transform")
        aliases: set[str] = set()
        for item in self.inputs:
            if not item.alias:
                raise ValueError("source.inputs.alias is required")
            if item.alias in aliases:
                raise ValueError(f"source.inputs alias {item.alias!r} is duplicated")
            aliases.add(item.alias)
        return self
