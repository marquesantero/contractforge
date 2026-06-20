"""Validated enriched project specifications."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from contractforge_ai.models import Assumption, EvidenceItem, RequiredDecision, Traceability, confidence_level
from contractforge_ai.planning.project import ProjectPlannerResult
from contractforge_ai.write_modes import canonical_write_mode

SpecValueSource = Literal["user", "deterministic", "provider", "default", "review_required"]
SpecValidationStatus = Literal["READY", "NEEDS_DECISIONS", "INVALID"]

CRITICAL_BUSINESS_FIELDS = {"merge_keys", "hash_columns", "owner", "sla", "delete_policy"}
CONTRACT_MUTATING_PROVIDER_FIELDS = {
    "annotations": "Annotations can affect governance metadata, tags and user-facing table/column descriptions.",
    "dab_compute": "Compute selection changes deployment/runtime behavior and must be confirmed for the target workspace.",
    "operations": "Operations metadata can affect ownership, criticality, runbooks and alert expectations.",
    "quality_rules": "Quality rules can reject, quarantine or warn on production records.",
    "shape": "Shape suggestions can change schema, values or row cardinality.",
    "transform": "Transform blocks can change schema, values or row cardinality.",
}
PROVIDER_UPDATABLE_FIELDS = {
    "selected_target",
    "connector",
    "source_path",
    "target_catalog",
    "target_schema",
    "target_table",
    "layer",
    "mode",
    "schedule",
    "freshness",
    "governance",
    "portability_priority",
    "owner",
    "source_format",
    "merge_keys",
    "hash_columns",
    "quality_rules",
    "transform",
    "shape",
    "annotations",
    "operations",
    "dab_compute",
}
PLANNER_CONTROLLED_FIELDS = {
    "selected_target",
    "connector",
    "source_path",
    "target_catalog",
    "target_schema",
    "target_table",
    "layer",
    "mode",
    "schedule",
    "freshness",
    "portability_priority",
    "owner",
}


@dataclass(frozen=True)
class SpecValue:
    """One project-spec value with provenance and review boundary."""

    value: Any
    source: SpecValueSource
    confidence: float = 1.0
    evidence: list[EvidenceItem] = field(default_factory=list)
    review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "confidence_level": confidence_level(self.confidence),
            "review_required": self.review_required,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class SpecValidation:
    """Validation result for an enriched project specification."""

    status: SpecValidationStatus
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class EnrichedProjectSpec:
    """Canonical planning object used before project artifact generation."""

    project_name: SpecValue
    selected_target: SpecValue
    connector: SpecValue
    source_path: SpecValue
    target_catalog: SpecValue
    target_schema: SpecValue
    target_table: SpecValue
    layer: SpecValue
    mode: SpecValue
    source_system: SpecValue | None = None
    schedule: SpecValue | None = None
    freshness: SpecValue | None = None
    governance: SpecValue | None = None
    portability_priority: SpecValue | None = None
    schema_path: SpecValue | None = None
    owner: SpecValue | None = None
    source_format: SpecValue | None = None
    merge_keys: SpecValue | None = None
    hash_columns: SpecValue | None = None
    quality_rules: SpecValue | None = None
    transform: SpecValue | None = None
    shape: SpecValue | None = None
    annotations: SpecValue | None = None
    operations: SpecValue | None = None
    dab_compute: SpecValue | None = None
    assumptions: list[Assumption] = field(default_factory=list)
    decisions_required: list[RequiredDecision] = field(default_factory=list)
    traceability: Traceability = field(default_factory=Traceability)

    @classmethod
    def from_planner(
        cls,
        planner: ProjectPlannerResult,
        *,
        selected_target: str | None = None,
    ) -> EnrichedProjectSpec:
        """Create a spec from deterministic planner output."""

        intent = planner.intent
        target = selected_target or (planner.recommendations[0].target if planner.recommendations else "contractforge-yaml")
        evidence = [
            EvidenceItem(
                source="deterministic_planner",
                reason="Value extracted from deterministic natural-language planning.",
                value={"status": planner.status, "signals": intent.signals},
                confidence=planner.traceability.confidence,
            )
        ]

        decisions = list(planner.decisions_required)
        for field_name, value in {
            "project_name": intent.project_name,
            "connector": intent.connector,
            "source_path": intent.source_path,
            "target_catalog": intent.target_catalog,
            "target_schema": intent.target_schema,
            "target_table": intent.target_table,
            "layer": intent.layer,
            "mode": intent.mode,
        }.items():
            if value in (None, ""):
                decisions.append(
                    RequiredDecision(
                        question=f"Confirm {field_name.replace('_', ' ')}.",
                        reason="The value was not available in the user request or deterministic planner output.",
                        path=field_name,
                    )
                )

        return cls(
            project_name=_spec_value(intent.project_name or "REVIEW_REQUIRED", "deterministic", evidence=evidence),
            selected_target=_spec_value(target, "deterministic", evidence=evidence),
            connector=_spec_value(intent.connector or "REVIEW_REQUIRED", "deterministic", evidence=evidence),
            source_path=_spec_value(intent.source_path or "REVIEW_REQUIRED", "deterministic", evidence=evidence),
            target_catalog=_spec_value(intent.target_catalog or "REVIEW_REQUIRED", "deterministic", evidence=evidence),
            target_schema=_spec_value(intent.target_schema or "REVIEW_REQUIRED", "deterministic", evidence=evidence),
            target_table=_spec_value(intent.target_table or "REVIEW_REQUIRED", "deterministic", evidence=evidence),
            layer=_spec_value(intent.layer or "bronze", "deterministic", evidence=evidence),
            mode=_spec_value(intent.mode or "append", "deterministic", evidence=evidence),
            source_system=_spec_value(intent.source_system, "deterministic", evidence=evidence) if intent.source_system else None,
            schedule=(
                _spec_value(
                    {
                        "cron": intent.schedule_cron,
                        "timezone": intent.schedule_timezone,
                        "enabled": True,
                    },
                    "deterministic",
                    evidence=evidence,
                    review_required=not bool(intent.schedule_timezone),
                )
                if intent.schedule_cron
                else None
            ),
            freshness=(
                _spec_value(
                    {
                        "class": intent.freshness,
                        **({"latency_target": intent.latency_target} if intent.latency_target else {}),
                    },
                    "deterministic",
                    evidence=evidence,
                )
                if intent.freshness
                else None
            ),
            governance=_spec_value(intent.governance, "deterministic", evidence=evidence, review_required=True) if intent.governance else None,
            portability_priority=(
                _spec_value(intent.portability_priority, "deterministic", evidence=evidence) if intent.portability_priority else None
            ),
            schema_path=_spec_value(intent.schema_path, "user", evidence=evidence) if intent.schema_path else None,
            owner=_spec_value(intent.owner, "user", evidence=evidence) if intent.owner else None,
            quality_rules=_spec_value(intent.quality_rules, "user", evidence=evidence) if intent.quality_rules else None,
            operations=_spec_value(intent.operations, "user", evidence=evidence) if intent.operations else None,
            dab_compute=_spec_value(intent.dab_compute, "user", evidence=evidence) if intent.dab_compute else None,
            decisions_required=decisions,
            assumptions=planner.assumptions,
            traceability=Traceability(
                confidence=planner.traceability.confidence,
                evidence=[*planner.traceability.evidence, *evidence],
                assumptions=planner.traceability.assumptions,
                decisions_required=decisions,
                review_required=True,
            ),
        )

    def validate(self) -> SpecValidation:
        """Validate whether the enriched spec is ready for generation or still needs review."""

        decisions = list(self.decisions_required)
        warnings: list[str] = []

        for field_name in (
            "project_name",
            "selected_target",
            "connector",
            "source_path",
            "target_catalog",
            "target_schema",
            "target_table",
            "layer",
            "mode",
        ):
            value = getattr(self, field_name)
            if _is_review_required_value(value):
                decisions.append(
                    RequiredDecision(
                        question=f"Confirm {field_name.replace('_', ' ')}.",
                        reason="The enriched spec still contains a review placeholder.",
                        path=field_name,
                    )
                )

        if self.schedule is not None and isinstance(self.schedule.value, dict):
            if not self.schedule.value.get("timezone"):
                decisions.append(
                    RequiredDecision(
                        question="Confirm schedule timezone.",
                        reason="Project schedule intent must include an explicit timezone.",
                        path="schedule.timezone",
                    )
                )

        canonical_mode = canonical_write_mode(str(self.mode.value))
        if canonical_mode in {"scd1_upsert", "scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}:
            if self.merge_keys is None or _is_review_required_value(self.merge_keys):
                decisions.append(
                    RequiredDecision(
                        question="Confirm merge keys.",
                        reason="Merge-based modes require stable business keys and the AI must not invent them without evidence.",
                        path="merge_keys",
                    )
                )

        if canonical_mode == "scd1_hash_diff" and (self.hash_columns is None or _is_review_required_value(self.hash_columns)):
            decisions.append(
                RequiredDecision(
                    question="Confirm hash diff columns.",
                    reason="Hash diff behavior depends on business-approved column inclusion/exclusion rules.",
                    path="hash_columns",
                )
            )

        for field_name in CRITICAL_BUSINESS_FIELDS:
            value = getattr(self, field_name, None)
            if isinstance(value, SpecValue) and value.source == "provider" and not value.review_required:
                warnings.append(f"Provider-suggested critical field must stay review-required: {field_name}.")
                decisions.append(
                    RequiredDecision(
                        question=f"Review provider-suggested {field_name.replace('_', ' ')}.",
                        reason="Critical business semantics require explicit human confirmation.",
                        path=field_name,
                    )
                )

        return SpecValidation(status="NEEDS_DECISIONS" if decisions or warnings else "READY", decisions_required=decisions, warnings=warnings)

    def generation_kwargs(self) -> dict[str, Any]:
        """Return kwargs compatible with existing project generators."""

        return {
            "project_name": str(self.project_name.value),
            "connector": str(self.connector.value),
            "source_path": str(self.source_path.value),
            "target_catalog": str(self.target_catalog.value),
            "target_schema": str(self.target_schema.value),
            "target_table": str(self.target_table.value),
            "layer": str(self.layer.value),
            "mode": str(self.mode.value),
            "owner": str(self.owner.value) if self.owner and self.owner.value else None,
        }

    def with_provider_enrichment(self, enrichment_data: dict[str, Any]) -> EnrichedProjectSpec:
        """Return a copy with validated provider field updates applied."""

        updates = enrichment_data.get("field_updates")
        if not isinstance(updates, dict):
            return self

        values: dict[str, Any] = {}
        decisions = list(self.decisions_required)
        assumptions = list(self.assumptions)
        provider_assumptions: list[Assumption] = []
        evidence = [
            EvidenceItem(
                source="provider_enrichment",
                reason="Provider suggested pre-generation project spec updates.",
                value={"summary": enrichment_data.get("summary"), "fields": sorted(updates)},
                confidence=_confidence(enrichment_data.get("confidence"), default=0.65),
            )
        ]

        for field_name, raw_update in updates.items():
            if field_name not in PROVIDER_UPDATABLE_FIELDS:
                decisions.append(
                    RequiredDecision(
                        question=f"Review unsupported provider field update: {field_name}.",
                        reason="The provider suggested a field outside the allowed project spec surface.",
                        path=field_name,
                    )
                )
                continue

            value, confidence, update_evidence, review_required = _parse_provider_update(raw_update)
            current = getattr(self, field_name, None)
            if isinstance(current, SpecValue) and not _is_review_required_value(current):
                if current.value == value:
                    continue
                decisions.append(
                    RequiredDecision(
                        question=f"Review provider attempt to change {field_name.replace('_', ' ')}.",
                        reason="Provider enrichment cannot silently override deterministic or user-provided project intent.",
                        path=field_name,
                    )
                )
                continue

            if field_name in PLANNER_CONTROLLED_FIELDS:
                review_required = True
                decisions.append(
                    RequiredDecision(
                        question=f"Confirm provider-filled {field_name.replace('_', ' ')}.",
                        reason="Planner-controlled identity fields suggested by a provider require explicit review.",
                        path=field_name,
                    )
                )

            if field_name in CRITICAL_BUSINESS_FIELDS:
                review_required = True
                decisions.append(
                    RequiredDecision(
                        question=f"Confirm provider-suggested {field_name.replace('_', ' ')}.",
                        reason="Critical business semantics must be explicitly approved before generation is treated as production-ready.",
                        path=field_name,
                    )
                )

            if field_name in CONTRACT_MUTATING_PROVIDER_FIELDS:
                review_required = True
                decisions.append(
                    RequiredDecision(
                        question=f"Review provider-suggested {field_name.replace('_', ' ')}.",
                        reason=CONTRACT_MUTATING_PROVIDER_FIELDS[field_name],
                        path=field_name,
                    )
                )

            values[field_name] = SpecValue(
                value=value,
                source="provider",
                confidence=confidence,
                evidence=[
                    *evidence,
                    *[
                        EvidenceItem(source="provider_enrichment", reason=str(item), confidence=confidence)
                        for item in update_evidence
                    ],
                ],
                review_required=review_required,
            )

        for item in enrichment_data.get("assumptions") or []:
            provider_assumptions.append(
                Assumption(statement=str(item), confidence=_confidence(enrichment_data.get("confidence"), default=0.65))
            )
        assumptions.extend(provider_assumptions)
        for item in enrichment_data.get("decisions_required") or []:
            decisions.append(
                RequiredDecision(
                    question=str(item),
                    reason="Provider enrichment marked this as requiring human review.",
                )
            )

        return replace(
            self,
            **values,
            assumptions=assumptions,
            decisions_required=decisions,
            traceability=Traceability(
                confidence=min(self.traceability.confidence, _confidence(enrichment_data.get("confidence"), default=0.65)),
                evidence=[*self.traceability.evidence, *evidence],
                assumptions=[*self.traceability.assumptions, *provider_assumptions],
                decisions_required=decisions,
                review_required=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        fields = {
            "project_name": self.project_name,
            "selected_target": self.selected_target,
            "connector": self.connector,
            "source_path": self.source_path,
            "target_catalog": self.target_catalog,
            "target_schema": self.target_schema,
            "target_table": self.target_table,
            "layer": self.layer,
            "mode": self.mode,
            "source_system": self.source_system,
            "schedule": self.schedule,
            "freshness": self.freshness,
            "governance": self.governance,
            "portability_priority": self.portability_priority,
            "schema_path": self.schema_path,
            "owner": self.owner,
            "source_format": self.source_format,
            "merge_keys": self.merge_keys,
            "hash_columns": self.hash_columns,
            "quality_rules": self.quality_rules,
            "transform": self.transform,
            "shape": self.shape,
            "annotations": self.annotations,
            "operations": self.operations,
            "dab_compute": self.dab_compute,
        }
        return {
            "fields": {key: value.to_dict() for key, value in fields.items() if isinstance(value, SpecValue)},
            "assumptions": [item.to_dict() for item in self.assumptions],
            "decisions_required": [item.to_dict() for item in self.decisions_required],
            "traceability": self.traceability.to_dict(),
            "validation": self.validate().to_dict(),
        }


def _spec_value(
    value: Any,
    source: SpecValueSource,
    *,
    evidence: list[EvidenceItem] | None = None,
    confidence: float = 0.75,
    review_required: bool = False,
) -> SpecValue:
    return SpecValue(
        value=value,
        source=source,
        confidence=confidence,
        evidence=evidence or [],
        review_required=review_required,
    )


def _parse_provider_update(raw_update: Any) -> tuple[Any, float, list[str], bool]:
    if not isinstance(raw_update, dict) or "value" not in raw_update:
        return raw_update, 0.65, [], False
    evidence = raw_update.get("evidence") if isinstance(raw_update.get("evidence"), list) else []
    return (
        raw_update.get("value"),
        _confidence(raw_update.get("confidence"), default=0.65),
        [str(item) for item in evidence],
        bool(raw_update.get("review_required", False)),
    )


def _confidence(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 0.0), 1.0)


def _is_review_required_value(value: SpecValue | None) -> bool:
    if value is None:
        return True
    if value.review_required:
        return True
    if value.value in (None, "", "REVIEW_REQUIRED", [], {}):
        return True
    return False
