"""Models for deterministic platform parity reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.adapter_validation import AdapterPlanningOutcome

ParityStatus = Literal["READY", "NEEDS_DECISIONS", "INVALID"]


@dataclass(frozen=True)
class ContractParityItem:
    """One contract compared across adapter planners."""

    name: str
    source_type: str | None
    target: str | None
    write_mode: str | None
    adapter_outcomes: list[AdapterPlanningOutcome] = field(default_factory=list)
    platform_extension_namespaces: list[str] = field(default_factory=list)

    @property
    def shared_fields(self) -> list[str]:
        """Return contract fields that are intentionally shared across adapters."""

        fields = ["source.type", "target", "mode"]
        if self.platform_extension_namespaces:
            fields.append("extensions")
        return fields

    @property
    def review_required_adapters(self) -> list[str]:
        """Return adapters whose planner requires review before deployment."""

        return [
            outcome.adapter
            for outcome in self.adapter_outcomes
            if outcome.status == "NEEDS_DECISIONS" or outcome.raw_status == "REVIEW_REQUIRED"
        ]

    @property
    def unsupported_adapters(self) -> list[str]:
        """Return adapters whose planner marked the contract invalid/unsupported."""

        return [
            outcome.adapter
            for outcome in self.adapter_outcomes
            if outcome.status == "INVALID" or outcome.raw_status == "UNSUPPORTED"
        ]

    @property
    def deployment_differences(self) -> dict[str, list[str]]:
        """Return artifact types by adapter to make deployment differences explicit."""

        return {
            outcome.adapter: outcome.artifact_types
            for outcome in self.adapter_outcomes
            if outcome.artifact_types
        }

    @property
    def evidence_differences(self) -> dict[str, str]:
        """Return the evidence storage expectation for each known adapter."""

        return {
            outcome.adapter: _evidence_storage(outcome.adapter)
            for outcome in self.adapter_outcomes
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_type": self.source_type,
            "target": self.target,
            "write_mode": self.write_mode,
            "shared_fields": self.shared_fields,
            "platform_extension_namespaces": self.platform_extension_namespaces,
            "review_required_adapters": self.review_required_adapters,
            "unsupported_adapters": self.unsupported_adapters,
            "deployment_differences": self.deployment_differences,
            "evidence_differences": self.evidence_differences,
            "adapter_outcomes": [outcome.to_dict() for outcome in self.adapter_outcomes],
        }


@dataclass(frozen=True)
class PlatformParityReport:
    """Deterministic comparison of one project or contract across adapters."""

    status: ParityStatus
    summary: str
    adapters: list[str]
    contracts: list[ContractParityItem] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.status == "READY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "summary": self.summary,
            "adapters": self.adapters,
            "contracts": [contract.to_dict() for contract in self.contracts],
        }

    def to_markdown(self) -> str:
        lines = [
            "# ContractForge Platform Parity Report",
            "",
            f"- Status: `{self.status}`",
            f"- Ready: `{str(self.ready).lower()}`",
            f"- Adapters: `{', '.join(self.adapters)}`",
            f"- Summary: {self.summary}",
        ]
        for contract in self.contracts:
            lines.extend(
                [
                    "",
                    f"## `{contract.name}`",
                    "",
                    f"- Source type: `{contract.source_type or 'unknown'}`",
                    f"- Target: `{contract.target or 'unknown'}`",
                    f"- Write mode: `{contract.write_mode or 'unknown'}`",
                    f"- Shared contract fields: `{', '.join(contract.shared_fields)}`",
                    f"- Platform extension namespaces: `{', '.join(contract.platform_extension_namespaces) or 'none'}`",
                    f"- Review required adapters: `{', '.join(contract.review_required_adapters) or 'none'}`",
                    f"- Unsupported adapters: `{', '.join(contract.unsupported_adapters) or 'none'}`",
                    "",
                    "| Adapter | Validation | Planner | Artifact types | Findings |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            for outcome in contract.adapter_outcomes:
                artifact_types = ", ".join(outcome.artifact_types) or "none"
                finding_codes = ", ".join(finding.code for finding in outcome.findings) or "none"
                lines.append(
                    f"| `{outcome.adapter}` | `{outcome.status}` | `{outcome.raw_status or 'UNKNOWN'}` | "
                    f"`{artifact_types}` | `{finding_codes}` |"
                )
            lines.extend(["", "### Deployment Differences", "", "| Adapter | Artifact types |", "| --- | --- |"])
            for adapter, artifact_types in contract.deployment_differences.items():
                lines.append(f"| `{adapter}` | `{', '.join(artifact_types) or 'none'}` |")
            if not contract.deployment_differences:
                lines.append("| `none` | `No native artifacts were rendered.` |")
            lines.extend(["", "### Evidence Differences", "", "| Adapter | Evidence storage |", "| --- | --- |"])
            for adapter, storage in contract.evidence_differences.items():
                lines.append(f"| `{adapter}` | {storage} |")
        return "\n".join(lines).rstrip() + "\n"


def _evidence_storage(adapter: str) -> str:
    storage = {
        "aws": "Iceberg/Glue evidence tables queryable through Athena or Glue Catalog.",
        "databricks": "Delta control tables following the core evidence model.",
    }
    return storage.get(adapter, "Adapter-declared evidence storage; review adapter documentation.")
