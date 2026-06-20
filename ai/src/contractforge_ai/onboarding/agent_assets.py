"""Generate IDE and agent instruction assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from contractforge_ai.models import Assumption, RequiredDecision, Traceability
from contractforge_ai.projects import DecisionReport, ProjectArtifact, ProjectPlan

AgentAssetTarget = Literal["generic", "codex", "claude", "cursor", "github-copilot", "all"]


def _default_validation_commands() -> list[str]:
    return [
        "contractforge-ai review <contract> --fail-on high",
        "contractforge-ai validate-project-structure . --format markdown",
        "contractforge-ai eval-prompts",
    ]


@dataclass(frozen=True)
class AgentInstructionRequest:
    """Inputs for generating coding-agent instruction assets."""

    target: AgentAssetTarget = "generic"
    project_name: str = "ContractForge Project"
    contract_root: str = "contracts"
    validation_commands: list[str] = field(default_factory=_default_validation_commands)
    output_prefix: str = "."
    allow_production_mutation: bool = False


def generate_agent_instruction_plan(request: AgentInstructionRequest) -> ProjectPlan:
    """Generate reviewable agent instruction assets."""

    targets = _expand_targets(request.target)
    artifacts = [
        ProjectArtifact(
            path=_artifact_path(request, "AGENT_INSTRUCTIONS.md"),
            kind="markdown",
            description="Portable coding-agent instructions for ContractForge projects.",
            content=_instructions_markdown(request),
        ),
        ProjectArtifact(
            path=_artifact_path(request, "AGENT_CHECKLIST.md"),
            kind="markdown",
            description="Checklist agents should follow before considering work complete.",
            content=_checklist_markdown(request),
        ),
    ]
    if "codex" in targets:
        artifacts.append(
            ProjectArtifact(
                path=_artifact_path(request, ".codex/contractforge-instructions.md"),
                kind="markdown",
                description="Codex-oriented instruction entrypoint.",
                content=_tool_entrypoint_markdown(request, tool_name="Codex", canonical="AGENT_INSTRUCTIONS.md"),
            )
        )
    if "claude" in targets:
        artifacts.append(
            ProjectArtifact(
                path=_artifact_path(request, "CLAUDE.md"),
                kind="markdown",
                description="Claude-oriented instruction entrypoint.",
                content=_tool_entrypoint_markdown(request, tool_name="Claude", canonical="AGENT_INSTRUCTIONS.md"),
            )
        )
    if "cursor" in targets:
        artifacts.append(
            ProjectArtifact(
                path=_artifact_path(request, ".cursor/rules/contractforge.mdc"),
                kind="markdown",
                description="Cursor rule file for ContractForge projects.",
                content=_cursor_rule_markdown(request),
            )
        )
    if "github-copilot" in targets:
        artifacts.append(
            ProjectArtifact(
                path=_artifact_path(request, ".github/copilot-instructions.md"),
                kind="markdown",
                description="GitHub Copilot repository instructions for ContractForge projects.",
                content=_tool_entrypoint_markdown(
                    request,
                    tool_name="GitHub Copilot",
                    canonical="AGENT_INSTRUCTIONS.md",
                ),
            )
        )

    report = DecisionReport(
        title="Agent Instruction Assets",
        summary=f"Generated {request.target} agent instruction assets for {request.project_name}.",
        assumptions=[
            Assumption(
                statement="Generated instructions are advisory and should be reviewed before use in shared repositories.",
                confidence=0.95,
                review_required=True,
            ),
            Assumption(
                statement="Repository agents can run the configured validation commands from the project root.",
                confidence=0.85,
                review_required=True,
            )
        ],
        decisions_required=[
            RequiredDecision(
                question="Confirm the validation commands match the repository and runtime.",
                reason="Agents must run project-specific validation instead of assuming success.",
                path="validation_commands",
            ),
            RequiredDecision(
                question="Confirm whether production mutation is intentionally allowed.",
                reason="Generated instructions default to review-only behavior for production resources.",
                path="allow_production_mutation",
            )
        ],
    )
    return ProjectPlan(
        name=f"{request.project_name} agent instructions",
        target=f"agent-instructions-{request.target}",
        artifacts=artifacts,
        report=report,
        traceability=Traceability(
            confidence=0.9,
            assumptions=report.assumptions,
            decisions_required=report.decisions_required,
            review_required=True,
        ),
    )


def _instructions_markdown(request: AgentInstructionRequest) -> str:
    commands = "\n".join(f"- `{command}`" for command in request.validation_commands)
    production_rule = (
        "Production mutation is allowed only when the user explicitly requests it and the command is scoped."
        if request.allow_production_mutation
        else "Do not mutate production data, cloud resources, secrets, adapter jobs, deployments or access policies."
    )
    return f"""# ContractForge Agent Instructions

Project: `{request.project_name}`

These instructions define how a coding assistant should work on ContractForge contracts, examples and generated projects.

## Operating Rules

- Treat ContractForge contracts as reviewable source code.
- Prefer deterministic ContractForge AI checks before proposing AI-enriched changes.
- Do not resolve, print or invent secret values.
- {production_rule}
- Keep generated contracts marked as drafts until a human reviews required decisions.
- Preserve contract separation: ingestion, annotations, operations and access should remain distinct when the repository uses that structure.
- When nested payloads are involved, call out row-cardinality changes caused by flatten or explode operations.
- When connector credentials are needed, reference secret names or environment variables only.
- Do not invent ContractForge parameters. Use documented fields or mark the field as a required decision.
- Keep deterministic findings authoritative when provider-backed enrichment is enabled.
- Preserve the core/adapter boundary: contracts, semantic validation and evidence schemas are core concerns; Databricks, AWS and future platform execution are adapter concerns.
- Use adapter-specific contract extensions only when the core contract cannot express the required intent, and call out portability impact.
- When adapter-aware validation is requested, keep `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` and `UNSUPPORTED` statuses visible instead of smoothing them into success.

## Expected Workflow

1. Inspect the changed files under `{request.contract_root}` and related generated artifacts.
2. Run deterministic review or generation commands before making recommendations.
3. Make minimal, reviewable file edits.
4. Run validation commands.
5. Summarize changed files, decisions required and validation results.

## Contract Review Focus

- Validate connector configuration, runtime assumptions and required dependencies.
- Validate target naming, write mode, keys, schema policy, quality rules and shape operations.
- Validate annotations, operations and access contracts when present.
- Flag credentials, raw tokens, personal data exposure and unmanaged production side effects.
- Record uncertainty explicitly instead of converting assumptions into facts.

## Validation Commands

{commands}

## Review Boundary

AI suggestions are advisory. Deterministic validation, generated reports and human review remain authoritative.
"""


def _checklist_markdown(request: AgentInstructionRequest) -> str:
    commands = "\n".join(f"- [ ] `{command}`" for command in request.validation_commands)
    return f"""# ContractForge Agent Checklist

Use this checklist before reporting work as complete.

## Contract Safety

- [ ] Source connector settings are explicit and do not contain raw secrets.
- [ ] Target catalog, schema and table are explicit.
- [ ] Merge/hash/SCD modes declare stable keys.
- [ ] Key columns have quality rules such as `not_null`.
- [ ] JSON, XML, Avro, Parquet or other file sources have explicit schema when required.
- [ ] Shape transformations are explicit and cardinality-changing operations are reviewed.
- [ ] Annotations and operations metadata are present when expected.
- [ ] Reusable connection YAMLs are resolved through the project structure, and ingestion-level source settings intentionally override global connection settings.
- [ ] Adapter-specific extensions are isolated and documented with portability impact.
- [ ] Adapter planning statuses and warnings are preserved when adapter validation is run.

## Generated Output

- [ ] Generated files are marked as drafts where appropriate.
- [ ] Required decisions are listed instead of silently assumed.
- [ ] No production mutation was performed without explicit user instruction.
- [ ] Validation output is summarized with exact commands and result status.
- [ ] Provider-backed text is clearly treated as advisory when present.

## Validation

{commands}
"""


def _tool_entrypoint_markdown(request: AgentInstructionRequest, *, tool_name: str, canonical: str) -> str:
    return f"""# {tool_name} Instructions for {request.project_name}

Follow `{canonical}` and `AGENT_CHECKLIST.md`.

Priority rules:

- Run deterministic validation first.
- Keep output reviewable.
- Do not expose secrets.
- Preserve ContractForge core/adapter boundaries.
- Do not change production resources, adapter jobs or deployments without explicit instruction.
"""


def _cursor_rule_markdown(request: AgentInstructionRequest) -> str:
    return f"""---
description: ContractForge contract review and generation rules
globs:
  - "{request.contract_root}/**/*.yaml"
  - "{request.contract_root}/**/*.yml"
  - "{request.contract_root}/**/*.json"
  - "**/databricks.yml"
alwaysApply: false
---

# ContractForge Cursor Rules

Use `AGENT_INSTRUCTIONS.md` and `AGENT_CHECKLIST.md` as the authoritative repository guidance.

- Run deterministic ContractForge AI commands before relying on provider-backed enrichment.
- Keep generated contracts reviewable and mark required decisions explicitly.
- Do not print, resolve or infer secret values.
- Preserve ContractForge core/adapter boundaries and keep adapter warnings visible.
- Do not mutate production systems without explicit user instruction.
"""


def _expand_targets(target: AgentAssetTarget) -> set[str]:
    if target == "all":
        return {"codex", "claude", "cursor", "github-copilot"}
    if target == "generic":
        return set()
    return {target}


def _artifact_path(request: AgentInstructionRequest, path: str) -> str:
    prefix = request.output_prefix.strip().replace("\\", "/")
    normalized = path.strip().replace("\\", "/")
    if not prefix or prefix == ".":
        return normalized
    return f"{prefix.rstrip('/')}/{normalized}"
