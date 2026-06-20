"""Argument parser construction for the ContractForge AI CLI."""

from __future__ import annotations

import argparse

from contractforge_ai.generators.targets import supported_project_targets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contractforge-ai")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser("review", help="Review a ContractForge contract")
    review_parser.add_argument("contract", help="Path to a ContractForge YAML or JSON contract")
    review_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")
    review_parser.add_argument(
        "--fail-on",
        choices=["none", "high", "critical"],
        default="none",
        help="Return a non-zero exit code when findings reach the selected severity",
    )
    review_parser.add_argument(
        "--fail-on-code",
        action="append",
        default=[],
        help="Return a non-zero exit code when a specific finding code is present. Can be repeated.",
    )
    review_parser.add_argument("--with-ai", action="store_true", help="Add optional provider-backed enrichment")
    review_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")
    review_parser.add_argument(
        "--bundle",
        action="store_true",
        help="Review an ingestion contract together with sibling .annotations and .operations files",
    )

    explain_parser = subparsers.add_parser("explain-run", help="Explain a failed ContractForge run from JSON or Databricks evidence")
    explain_parser.add_argument("--input", help="Path to a JSON file with run/error evidence")
    explain_parser.add_argument("--run-id", help="ContractForge run_id to collect from Databricks control tables")
    explain_parser.add_argument("--catalog", help="Catalog containing ContractForge control tables")
    explain_parser.add_argument("--ctrl-schema", default="ops", help="Schema containing ContractForge control tables")
    explain_parser.add_argument("--limit", type=int, default=20, help="Maximum related rows to collect per control table")
    explain_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    explain_parser.add_argument("--with-ai", action="store_true", help="Add optional provider-backed enrichment")
    explain_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")

    control_parser = subparsers.add_parser(
        "analyze-control-tables",
        help="Analyze ContractForge control-table evidence from JSON",
    )
    control_parser.add_argument("--input", required=True, help="Path to JSON evidence with runs/errors/quality/streams")
    control_parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format")
    control_parser.add_argument("--with-ai", action="store_true", help="Add optional provider-backed enrichment")
    control_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")
    control_parser.add_argument("--language", default="en", help="Translate rendered reports with the selected provider. Labels remain English.")

    knowledge_parser = subparsers.add_parser(
        "knowledge-index",
        help="Build or query a local ContractForge AI knowledge index",
    )
    knowledge_subparsers = knowledge_parser.add_subparsers(dest="knowledge_command", required=True)
    knowledge_build_parser = knowledge_subparsers.add_parser("build", help="Build a local knowledge index")
    knowledge_build_parser.add_argument("paths", nargs="+", help="Files or directories to index")
    knowledge_build_parser.add_argument("--output", required=True, help="Path to write the knowledge index JSON")
    knowledge_build_parser.add_argument("--root", help="Optional root used for relative source paths")
    knowledge_build_parser.add_argument("--max-chars", type=int, default=1800, help="Maximum characters per chunk")
    knowledge_build_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    knowledge_query_parser = knowledge_subparsers.add_parser("query", help="Query a local knowledge index")
    knowledge_query_parser.add_argument("--index", required=True, help="Path to a knowledge index JSON")
    knowledge_query_parser.add_argument("--query", required=True, help="Search query")
    knowledge_query_parser.add_argument("--limit", type=int, default=5, help="Maximum results")
    knowledge_query_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    route_task_parser = subparsers.add_parser(
        "route-task",
        help="Infer the task, prompt and context retrieval plan for a ContractForge AI intent",
    )
    route_task_parser.add_argument("--intent", required=True, help="User intent or task description")
    route_task_parser.add_argument(
        "--task-hint",
        choices=[
            "contract_review",
            "failure_explanation",
            "metadata_suggestion",
            "shape_suggestion",
            "project_planning",
            "project_synthesis",
            "observability_analysis",
        ],
        help="Optional explicit task hint",
    )
    route_task_parser.add_argument("--knowledge-index", help="Optional local knowledge index JSON")
    route_task_parser.add_argument("--context-limit", type=int, default=5, help="Maximum retrieved context chunks")
    route_task_parser.add_argument(
        "--prefer-http-only",
        action="store_true",
        help="Prefer HTTP-only providers for low-risk advisory routing",
    )
    route_task_parser.add_argument(
        "--prefer-databricks-boundary",
        action="store_true",
        help="Prefer Databricks model-serving boundary in provider routing",
    )
    route_task_parser.add_argument(
        "--require-strict-schema",
        action="store_true",
        help="Require strict structured-output support in provider routing",
    )
    route_task_parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format")

    suggest_parser = subparsers.add_parser(
        "suggest-metadata",
        help="Suggest annotations and quality rules from schema/profile metadata",
    )
    suggest_parser.add_argument("--schema", required=True, help="Path to schema/profile JSON or YAML")
    suggest_parser.add_argument("--format", choices=["text", "json", "yaml"], default="text", help="Output format")

    shape_parser = subparsers.add_parser("suggest-shape", help="Suggest ContractForge shape config from JSON samples")
    shape_parser.add_argument("--sample", required=True, help="Path to a JSON object or array sample")
    shape_parser.add_argument(
        "--source-column",
        default="raw_payload",
        help="Logical source column name used in generated examples",
    )
    shape_parser.add_argument("--format", choices=["text", "json", "yaml"], default="text", help="Output format")

    draft_parser = subparsers.add_parser("generate-contract", help="Generate a draft ContractForge ingestion contract")
    draft_parser.add_argument("--schema", required=True, help="Path to schema/profile JSON or YAML")
    draft_parser.add_argument("--connector", required=True, help="Source connector name")
    draft_parser.add_argument("--source-path", required=True, help="Source path/table/API identifier")
    draft_parser.add_argument("--target-catalog", required=True, help="Target catalog")
    draft_parser.add_argument("--target-schema", required=True, help="Target schema")
    draft_parser.add_argument("--target-table", required=True, help="Target table")
    draft_parser.add_argument("--layer", default="bronze", help="Contract layer")
    draft_parser.add_argument("--mode", help="Write mode. Defaults conservatively from layer.")
    draft_parser.add_argument("--owner", help="Technical owner for operations metadata")
    draft_parser.add_argument("--format", choices=["text", "json", "yaml"], default="yaml", help="Output format")

    project_parser = subparsers.add_parser("project-plan", help="Inspect or write a generated project plan")
    project_parser.add_argument("--input", required=True, help="Path to a project plan JSON or YAML file")
    project_parser.add_argument("--output-dir", help="Directory where artifacts should be written")
    project_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    project_parser.add_argument("--dry-run", action="store_true", help="Plan writes without touching the filesystem")
    project_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format when not writing files",
    )

    generate_project_parser = subparsers.add_parser("generate-project", help="Generate a reviewable project scaffold")
    generate_project_parser.add_argument(
        "--target",
        choices=supported_project_targets(),
        required=True,
        help="Project target",
    )
    generate_project_parser.add_argument("--schema", required=True, help="Path to schema/profile JSON or YAML")
    generate_project_parser.add_argument("--project-name", required=True, help="Logical generated project name")
    generate_project_parser.add_argument("--connector", required=True, help="Source connector name")
    generate_project_parser.add_argument("--source-path", required=True, help="Source path/table/API identifier")
    generate_project_parser.add_argument("--target-catalog", required=True, help="Target catalog")
    generate_project_parser.add_argument("--target-schema", required=True, help="Target schema")
    generate_project_parser.add_argument("--target-table", required=True, help="Target table")
    generate_project_parser.add_argument("--layer", default="bronze", help="Contract layer")
    generate_project_parser.add_argument("--mode", help="Write mode. Defaults conservatively from layer.")
    generate_project_parser.add_argument("--owner", help="Technical owner for operations metadata")
    generate_project_parser.add_argument("--schedule-cron", default="0 6 * * *", help="Project schedule as standard five-field cron")
    generate_project_parser.add_argument("--schedule-timezone", default="UTC", help="Project schedule timezone, for example America/Sao_Paulo")
    generate_project_parser.add_argument("--schedule-enabled", action="store_true", help="Enable the generated schedule")
    generate_project_parser.add_argument("--naming-file", help="JSON/YAML file with ContractForge naming overrides")
    generate_project_parser.add_argument("--output-dir", help="Directory where artifacts should be written")
    generate_project_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    generate_project_parser.add_argument("--dry-run", action="store_true", help="Plan writes without touching the filesystem")
    generate_project_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format when not writing files",
    )

    planner_parser = subparsers.add_parser(
        "plan-project",
        help="Plan a ContractForge project from natural-language intent without writing files",
    )
    planner_input = planner_parser.add_mutually_exclusive_group(required=True)
    planner_input.add_argument("--intent", help="Natural-language ingestion scenario")
    planner_input.add_argument("--intent-file", help="Path to a text file containing the ingestion scenario")
    planner_parser.add_argument("--schema", dest="schema_path", help="Optional schema/profile path")
    planner_parser.add_argument("--default-catalog", help="Default target catalog when not stated in the intent")
    planner_parser.add_argument("--default-schema", help="Default target schema when not stated in the intent")
    planner_parser.add_argument("--default-layer", help="Default ContractForge layer when not stated in the intent")
    planner_parser.add_argument(
        "--preferred-target",
        choices=supported_project_targets(),
        help="Preferred generated project target",
    )
    planner_parser.add_argument("--with-ai", action="store_true", help="Add optional provider-backed enrichment")
    planner_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")
    planner_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a ContractForge project from free-form intent",
    )
    generate_input = generate_parser.add_mutually_exclusive_group(required=True)
    generate_input.add_argument("--prompt", help="Free-form project request")
    generate_input.add_argument("--prompt-file", help="Path to a text file containing the project request")
    generate_parser.add_argument("--schema", dest="schema_path", help="Schema/profile path used as source evidence")
    generate_parser.add_argument(
        "--schemas",
        dest="schema_paths",
        nargs="+",
        help="Schema/profile paths for multi-dataset generation in one project",
    )
    generate_parser.add_argument("--sample-table", help="Databricks table used as source schema evidence")
    generate_parser.add_argument("--project-root", help="Existing ContractForge project directory to analyze before generation")
    generate_parser.add_argument("--default-catalog", help="Default target catalog when not stated in the prompt")
    generate_parser.add_argument(
        "--target",
        choices=supported_project_targets(),
        default="contractforge-yaml",
        help="Generation target. Multi-layer generation currently emits ContractForge contracts.",
    )
    generate_parser.add_argument("--with-ai", action="store_true", help="Add optional provider-backed report enrichment")
    generate_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")
    generate_parser.add_argument("--language", default="en", help="Translate generated reports with the selected provider. Labels remain English.")
    generate_parser.add_argument("--output-dir", help="Directory where artifacts should be written")
    generate_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    generate_parser.add_argument("--dry-run", action="store_true", help="Plan writes without touching the filesystem")
    generate_parser.add_argument(
        "--format",
        choices=["text", "json", "html"],
        default="text",
        help="Output format when not writing files",
    )

    guided_project_parser = subparsers.add_parser(
        "guided-project",
        help="Plan and generate a project scaffold from guided natural-language intent",
    )
    guided_project_input = guided_project_parser.add_mutually_exclusive_group(required=True)
    guided_project_input.add_argument("--intent", help="Natural-language ingestion scenario")
    guided_project_input.add_argument("--intent-file", help="Path to a text file containing the ingestion scenario")
    guided_project_input.add_argument(
        "--requirements",
        help="Path to a guided project requirements JSON or YAML file",
    )
    guided_project_parser.add_argument("--schema", dest="schema_path", help="Schema/profile path")
    guided_project_parser.add_argument(
        "--context-dir",
        help="Directory with sample data, schema/profile files or project context used when synthesizing a scaffold",
    )
    guided_project_parser.add_argument(
        "--runtime",
        choices=["databricks-serverless", "databricks-classic", "serverless", "classic", "local", "unknown"],
        help="Target runtime used for context and dependency guidance",
    )
    guided_project_parser.add_argument("--default-catalog", help="Default target catalog when not stated in the intent")
    guided_project_parser.add_argument("--default-schema", help="Default target schema when not stated in the intent")
    guided_project_parser.add_argument("--default-layer", help="Default ContractForge layer when not stated in the intent")
    guided_project_parser.add_argument(
        "--target",
        choices=supported_project_targets(),
        help="Project target. Defaults to the planner's first recommendation.",
    )
    guided_project_parser.add_argument(
        "--allow-review-required",
        action="store_true",
        help="Generate artifacts even when planner decisions remain open.",
    )
    guided_project_parser.add_argument("--naming-file", help="JSON/YAML file with ContractForge naming overrides")
    guided_project_parser.add_argument("--output-dir", help="Directory where artifacts should be written")
    guided_project_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    guided_project_parser.add_argument("--dry-run", action="store_true", help="Plan writes without touching the filesystem")
    guided_project_parser.add_argument(
        "--with-ai",
        action="store_true",
        help="Use a model provider to enrich the project specification before generation",
    )
    guided_project_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")
    guided_project_parser.add_argument("--language", default="en", help="Translate generated reports with the selected provider. Labels remain English.")
    guided_project_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown", "html"],
        default="text",
        help="Output format when not writing files",
    )

    profiles_parser = subparsers.add_parser("profiles", help="List supported integration profiles")
    profiles_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    profile_parser = subparsers.add_parser("profile", help="Inspect or validate one integration profile")
    profile_parser.add_argument("name", help="Integration profile name")
    profile_parser.add_argument(
        "--config",
        help="Path to a JSON file with profile configuration to validate",
    )
    profile_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    env_parser = subparsers.add_parser("environment-report", help="Discover local onboarding environment capabilities")
    env_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    init_parser = subparsers.add_parser("init", help="Generate ContractForge AI onboarding configuration")
    init_parser.add_argument("--profile", default="local-cli", help="Integration profile name")
    init_parser.add_argument(
        "--mode",
        choices=["deterministic", "provider-enriched"],
        default="deterministic",
        help="Onboarding mode",
    )
    init_parser.add_argument("--provider", help="Optional model provider name")
    init_parser.add_argument("--model", help="Optional provider model or deployment name")
    init_parser.add_argument("--catalog", help="Databricks catalog containing ContractForge control tables")
    init_parser.add_argument("--ctrl-schema", help="Databricks schema containing ContractForge control tables")
    init_parser.add_argument("--workspace-profile", help="Databricks CLI workspace profile")
    init_parser.add_argument("--instruction-path", help="Agent instruction output path")
    init_parser.add_argument("--tool-boundary", help="MCP/tool boundary description")
    init_parser.add_argument("--output-dir", default=".", help="Directory where onboarding files should be written")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    init_parser.add_argument("--dry-run", action="store_true", help="Plan writes without touching the filesystem")
    init_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format when reporting the generated plan",
    )

    agent_parser = subparsers.add_parser(
        "agent-instructions",
        help="Generate reviewable IDE and coding-agent instruction assets",
    )
    agent_parser.add_argument(
        "--target",
        choices=["generic", "codex", "claude", "cursor", "github-copilot", "all"],
        default="generic",
        help="Instruction target to generate",
    )
    agent_parser.add_argument("--project-name", default="ContractForge Project", help="Project display name")
    agent_parser.add_argument("--contract-root", default="contracts", help="Directory containing ContractForge contracts")
    agent_parser.add_argument(
        "--validation-command",
        action="append",
        dest="validation_commands",
        help="Validation command agents should run. Can be repeated.",
    )
    agent_parser.add_argument(
        "--output-prefix",
        default=".",
        help="Relative prefix for generated files inside the output directory",
    )
    agent_parser.add_argument(
        "--allow-production-mutation",
        action="store_true",
        help="Generate instructions that allow explicitly requested production mutations",
    )
    agent_parser.add_argument("--output-dir", default=".", help="Directory where instruction files should be written")
    agent_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    agent_parser.add_argument("--dry-run", action="store_true", help="Plan writes without touching the filesystem")
    agent_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format when reporting the generated plan",
    )

    eval_prompts_parser = subparsers.add_parser("eval-prompts", help="Run deterministic prompt evaluation checks")
    eval_prompts_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    eval_prompts_parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List prompt templates instead of running evaluation cases",
    )

    validate_output_parser = subparsers.add_parser("validate-output", help="Validate model output against a prompt schema")
    validate_output_parser.add_argument("--prompt", required=True, help="Registered prompt template name")
    validate_output_parser.add_argument("--input", required=True, help="Path to JSON model output")
    validate_output_parser.add_argument("--fallback", help="Optional path to deterministic fallback JSON")
    validate_output_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    validate_artifact_parser = subparsers.add_parser(
        "validate-artifact",
        help="Run the deterministic validation gate for generated or AI-reviewed artifacts",
    )
    validate_artifact_source = validate_artifact_parser.add_mutually_exclusive_group(required=True)
    validate_artifact_source.add_argument("--contract", help="Path to a generated ContractForge YAML/JSON contract")
    validate_artifact_source.add_argument("--project-plan", help="Path to a generated project plan YAML/JSON file")
    validate_artifact_source.add_argument("--project-root", help="Path to a real ContractForge project folder")
    validate_artifact_source.add_argument("--model-output", help="Path to provider output JSON or raw JSON text")
    validate_artifact_parser.add_argument("--prompt", help="Required with --model-output; registered prompt template name")
    validate_artifact_parser.add_argument("--fallback", help="Optional deterministic fallback JSON for model output validation")
    validate_artifact_parser.add_argument(
        "--skip-contractforge",
        action="store_true",
        help="Skip ContractForge core validation and use ContractForge AI deterministic checks only",
    )
    validate_artifact_parser.add_argument(
        "--adapter",
        action="append",
        default=[],
        help="Optionally plan generated contract/project-plan artifacts against an installed adapter. Can be repeated.",
    )
    validate_artifact_parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format")

    validate_project_structure_parser = subparsers.add_parser(
        "validate-project-structure",
        help="Validate a real ContractForge project folder, including project.yaml, environments, connections and split contracts",
    )
    validate_project_structure_parser.add_argument("root", help="ContractForge project root")
    validate_project_structure_parser.add_argument(
        "--format",
        choices=["text", "json", "markdown", "html"],
        default="text",
        help="Output format",
    )
    validate_project_structure_parser.add_argument(
        "--adapter",
        action="append",
        default=[],
        help="Optionally plan project ingestion bundles against an installed adapter. Can be repeated.",
    )

    compare_platforms_parser = subparsers.add_parser(
        "compare-platforms",
        help="Compare one contract or project folder across adapter public planners",
    )
    compare_platforms_source = compare_platforms_parser.add_mutually_exclusive_group(required=True)
    compare_platforms_source.add_argument("--contract", help="Path to a ContractForge YAML/JSON contract or ingestion bundle")
    compare_platforms_source.add_argument("--project-root", help="Path to a real ContractForge project folder")
    compare_platforms_parser.add_argument(
        "--adapter",
        action="append",
        default=[],
        help="Adapter to compare. Can be repeated. Defaults to databricks and aws.",
    )
    compare_platforms_parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format")

    critique_parser = subparsers.add_parser(
        "critique-output",
        help="Run second-pass critique and confidence scoring over generated or enriched output",
    )
    critique_parser.add_argument("--input", required=True, help="Path to generated/enriched output JSON")
    critique_parser.add_argument("--validation", help="Optional deterministic validation report JSON")
    critique_parser.add_argument("--context", help="Optional retrieved context JSON with context_results/results")
    critique_parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format")

    architecture_parser = subparsers.add_parser(
        "review-architecture",
        help="Review a repository for governed execution architecture concepts",
    )
    architecture_parser.add_argument("root", help="Repository or project directory to review")
    architecture_parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format")

    eval_enrichment_parser = subparsers.add_parser(
        "eval-enrichment",
        help="Evaluate AI enrichment quality against deterministic baseline",
    )
    eval_enrichment_parser.add_argument("--deterministic", required=True, help="Path to deterministic baseline JSON")
    eval_enrichment_parser.add_argument("--enrichment", required=True, help="Path to enrichment JSON or payload containing ai_enrichment")
    eval_enrichment_parser.add_argument("--kind", help="Expected enrichment kind, such as review, explain or project_plan")
    eval_enrichment_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")

    eval_provider_parser = subparsers.add_parser("eval-provider", help="Evaluate a configured model provider")
    eval_provider_parser.add_argument("--provider", help="Provider name. Defaults to CONTRACTFORGE_AI_PROVIDER or offline")
    eval_provider_parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help="Prompt template to evaluate. Can be repeated. Defaults to the provider evaluation suite.",
    )
    eval_provider_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")

    route_provider_parser = subparsers.add_parser("route-provider", help="Recommend providers for a ContractForge AI task")
    route_provider_parser.add_argument(
        "--task",
        choices=["review_enrichment", "failure_explanation", "metadata_enrichment", "project_planning"],
        required=True,
        help="ContractForge AI task to route",
    )
    route_provider_parser.add_argument("--require-strict-schema", action="store_true", help="Only allow strict-schema providers")
    route_provider_parser.add_argument("--allow-planned", action="store_true", help="Allow planned providers in recommendations")
    route_provider_parser.add_argument("--prefer-http-only", action="store_true", help="Prefer providers that can run with HTTP-only dependencies")
    route_provider_parser.add_argument(
        "--prefer-databricks-boundary",
        action="store_true",
        help="Prefer Databricks model-serving boundary",
    )
    route_provider_parser.add_argument("--include-offline", action="store_true", help="Include offline provider in routing")
    route_provider_parser.add_argument("--allow-provider", action="append", default=[], help="Restrict routing to one provider. Can be repeated.")
    route_provider_parser.add_argument("--exclude-provider", action="append", default=[], help="Exclude one provider. Can be repeated.")
    route_provider_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format")

    return parser
