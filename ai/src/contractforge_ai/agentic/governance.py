"""Governed-generation primitives inspired by CFA patterns."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from contractforge_ai.agentic.models import GapPlan, IntentSpec, ProjectState, TransformationPlan
from contractforge_ai.write_modes import canonical_write_mode

PolicyAction = Literal["approve", "review_required", "block"]
ProviderProposalOutcome = Literal["accepted", "rejected", "requires_review"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ContextSnapshot:
    """Reproducible snapshot of the analyzed generation context."""

    project_state: ProjectState
    schema_source: dict[str, Any]
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def snapshot_hash(self) -> str:
        payload = {
            "project_state": self.project_state.to_dict(),
            "schema_source": self.schema_source,
        }
        return _hash_payload(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_hash": self.snapshot_hash,
            "created_at": self.created_at.isoformat(),
            "project_state": self.project_state.to_dict(),
            "schema_source": self.schema_source,
        }


@dataclass(frozen=True)
class GenerationSignature:
    """Deterministic signature for one intent-first generation attempt."""

    intent: IntentSpec
    context_snapshot: ContextSnapshot
    gap_plan: GapPlan
    transformation_plan: TransformationPlan
    signature_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def signature_hash(self) -> str:
        payload = {
            "intent": self.intent.to_dict(),
            "context_snapshot_hash": self.context_snapshot.snapshot_hash,
            "gap_plan": self.gap_plan.to_dict(),
            "transformation_plan": self.transformation_plan.to_dict(),
        }
        return _hash_payload(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature_id": self.signature_id,
            "signature_hash": self.signature_hash,
            "created_at": self.created_at.isoformat(),
            "intent": self.intent.to_dict(),
            "context_snapshot": self.context_snapshot.to_dict(),
            "gap_plan": self.gap_plan.to_dict(),
            "transformation_plan": self.transformation_plan.to_dict(),
        }


@dataclass(frozen=True)
class GenerationPolicyFinding:
    """One policy finding produced before artifact generation."""

    code: str
    action: PolicyAction
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "action": self.action,
            "message": self.message,
            "path": self.path,
        }


@dataclass(frozen=True)
class GenerationPolicyResult:
    """Policy result for a generation signature."""

    action: PolicyAction
    findings: list[GenerationPolicyFinding] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return self.action == "block"

    @property
    def needs_review(self) -> bool:
        return self.action == "review_required"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "findings": [finding.to_dict() for finding in self.findings],
        }


class GenerationPolicyEngine:
    """Lightweight policy gate for intent-first project generation."""

    def evaluate(self, signature: GenerationSignature) -> GenerationPolicyResult:
        findings: list[GenerationPolicyFinding] = []
        intent = signature.intent
        schema_source = signature.context_snapshot.schema_source

        if schema_source.get("kind") == "missing" or schema_source.get("status") == "FAILED":
            findings.append(
                GenerationPolicyFinding(
                    code="generation.schema_evidence_missing",
                    action="block",
                    message="Schema evidence is required before generating implementation contracts.",
                    path="schema_path",
                )
            )
        if signature.gap_plan.layers_to_generate and any(layer in {"silver", "gold"} for layer in signature.gap_plan.layers_to_generate):
            if canonical_write_mode(intent.silver_mode) in {"scd1_hash_diff", "scd1_upsert", "scd2_historical"} and not _has_merge_key_evidence(intent.prompt):
                findings.append(
                    GenerationPolicyFinding(
                        code="generation.merge_keys_review_required",
                        action="review_required",
                    message="Historical/upsert generation requires human confirmation of merge keys and hash-diff policy.",
                        path="contracts/silver/*.ingestion.yaml.merge_keys",
                    )
                )
        if "gold" in signature.gap_plan.layers_to_generate and _mentions_aggregation(intent.prompt) and not _has_grain_evidence(intent.prompt):
            findings.append(
                GenerationPolicyFinding(
                    code="generation.gold_grain_review_required",
                    action="review_required",
                    message="Gold aggregation requests require an explicit grain before transformation logic can be treated as ready.",
                    path="contracts/gold/*.ingestion.yaml.transform",
                )
            )
        for decision in signature.transformation_plan.decisions_required:
            findings.append(
                GenerationPolicyFinding(
                    code="generation.transform_mapping_review_required",
                    action="review_required",
                    message=decision.question,
                    path=decision.path,
                )
            )

        if any(finding.action == "block" for finding in findings):
            action: PolicyAction = "block"
        elif findings:
            action = "review_required"
        else:
            action = "approve"
        return GenerationPolicyResult(action=action, findings=findings)


@dataclass(frozen=True)
class ProviderProposalDecision:
    """Decision recorded for one provider-proposed update."""

    stage: str
    field_path: str
    proposed_value: Any
    outcome: ProviderProposalOutcome
    rule: str
    reason: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "field_path": self.field_path,
            "proposed_value": self.proposed_value,
            "outcome": self.outcome,
            "rule": self.rule,
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ProviderProposalAudit:
    """Traceable provider proposal audit before artifact materialization."""

    provider: str
    prompt: str
    decisions: list[ProviderProposalDecision] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return self._count("accepted")

    @property
    def rejected_count(self) -> int:
        return self._count("rejected")

    @property
    def review_required_count(self) -> int:
        return self._count("requires_review")

    @property
    def action(self) -> PolicyAction:
        if self.rejected_count:
            return "review_required"
        if self.review_required_count:
            return "review_required"
        return "approve"

    def _count(self, outcome: ProviderProposalOutcome) -> int:
        return sum(1 for decision in self.decisions if decision.outcome == outcome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "prompt": self.prompt,
            "action": self.action,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "review_required_count": self.review_required_count,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


@dataclass(frozen=True)
class GenerationAuditEvent:
    """Tamper-evident audit event for generation stages."""

    stage: str
    outcome: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utcnow)
    previous_hash: str = ""
    event_hash: str = ""

    def with_hash(self, previous_hash: str) -> GenerationAuditEvent:
        event = GenerationAuditEvent(
            stage=self.stage,
            outcome=self.outcome,
            details=self.details,
            timestamp=self.timestamp,
            previous_hash=previous_hash,
        )
        return GenerationAuditEvent(
            stage=event.stage,
            outcome=event.outcome,
            details=event.details,
            timestamp=event.timestamp,
            previous_hash=previous_hash,
            event_hash=_hash_payload(
                {
                    "stage": event.stage,
                    "outcome": event.outcome,
                    "details": event.details,
                    "timestamp": event.timestamp.isoformat(),
                    "previous_hash": previous_hash,
                }
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "outcome": self.outcome,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
        }


@dataclass
class GenerationAuditTrail:
    """Append-only in-memory audit trail for a generation run."""

    events: list[GenerationAuditEvent] = field(default_factory=list)

    def record(self, stage: str, outcome: str, **details: Any) -> GenerationAuditEvent:
        previous_hash = self.events[-1].event_hash if self.events else ""
        event = GenerationAuditEvent(stage=stage, outcome=outcome, details=details).with_hash(previous_hash)
        self.events.append(event)
        return event

    @property
    def last_hash(self) -> str:
        return self.events[-1].event_hash if self.events else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": len(self.events),
            "last_hash": self.last_hash,
            "events": [event.to_dict() for event in self.events],
        }


def _hash_payload(payload: dict[str, Any]) -> str:
    content = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _has_merge_key_evidence(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ("merge key", "merge keys", "key:", "keys:", "chave", "chaves"))


def _mentions_aggregation(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ("aggregate", "aggregation", "group by", "sum", "count", "agregar", "agregação"))


def _has_grain_evidence(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ("grain", "granularity", "grão", "granularidade", "group by"))
