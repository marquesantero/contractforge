# Agent and IDE Instruction Assets

ContractForge AI can generate repository instruction files for coding assistants and IDE agents. The output is deterministic: it does not call a model provider and it does not inspect secrets. The generated files define how assistants should review contracts, run validation, handle uncertainty and avoid unsafe production actions.

Use this when a team wants consistent AI-assisted behavior across local IDEs, pull-request work and generated ContractForge projects.

## Command

```bash
contractforge-ai agent-instructions \
  --target all \
  --project-name "Orders Platform" \
  --contract-root contracts \
  --output-dir .
```

Preview without writing files:

```bash
contractforge-ai agent-instructions \
  --target all \
  --project-name "Orders Platform" \
  --dry-run \
  --format json
```

Write under a subdirectory instead of the repository root:

```bash
contractforge-ai agent-instructions \
  --target generic \
  --output-prefix docs/agent-guidance \
  --output-dir .
```

## Targets

| Target | Generated files |
| --- | --- |
| `generic` | `AGENT_INSTRUCTIONS.md`, `AGENT_CHECKLIST.md` |
| `codex` | Generic files plus `.codex/contractforge-instructions.md` |
| `claude` | Generic files plus `CLAUDE.md` |
| `cursor` | Generic files plus `.cursor/rules/contractforge.mdc` |
| `github-copilot` | Generic files plus `.github/copilot-instructions.md` |
| `all` | Generic files plus all supported agent-specific entrypoints |

The generic files are the canonical source. Agent-specific files point back to them so teams can keep the core guidance consistent.

## Generated Guidance

Generated instructions enforce the following operating model:

- Treat ContractForge contracts as reviewable source code.
- Run deterministic ContractForge AI checks before relying on provider-backed enrichment.
- Do not resolve, print or invent secret values.
- Do not invent ContractForge parameters; use documented fields or mark required decisions.
- Do not mutate production data, cloud resources, adapter jobs, deployments or access policies unless explicitly allowed.
- Preserve contract separation between ingestion, annotations, operations and access.
- Preserve ContractForge core/adapter boundaries: core owns contracts, semantic validation and evidence schemas; adapters own platform execution.
- Keep adapter planning statuses visible when adapter-aware validation is run. Do not rewrite `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or `UNSUPPORTED` into success.
- Use adapter-specific extensions only when core contract semantics cannot express the intent, and document portability impact.
- Flag row-cardinality changes caused by shape operations such as flatten and explode.
- Summarize exact validation commands and results before reporting work as complete.

## Validation Commands

The default generated checklist includes:

```bash
contractforge-ai review <contract> --fail-on high
contractforge-ai validate-project-structure . --format html > project_validation.html
contractforge-ai eval-prompts
```

Use JSON or Markdown instead when the command is intended only for CI logs or a
pull request comment. Use HTML when a reviewer needs to inspect full
paths, findings and adapter evidence.

Override them for a repository:

```bash
contractforge-ai agent-instructions \
  --target all \
  --validation-command "contractforge-ai review contracts/silver/orders.ingestion.yaml --fail-on high" \
  --validation-command "pytest tests/contracts -q" \
  --output-dir .
```

Prefer repository-specific commands. For example, use the same contract paths and CI commands that reviewers already trust.

## Production Safety

By default, generated instructions prohibit production mutation. This is intentional: coding assistants should be safe for contract review, planning, docs, local scaffolding and CI diagnostics without being able to change production jobs, access policies or data.

If a repository intentionally allows production mutations after explicit user instruction, generate that wording with:

```bash
contractforge-ai agent-instructions --allow-production-mutation --output-dir .
```

This does not grant any permission by itself. It only changes the written guidance. Runtime credentials and access controls remain external to ContractForge AI.

## Recommended Repository Workflow

1. Generate `generic` or `all` instruction assets in a pull request.
2. Review the generated validation commands and production mutation stance.
3. Keep `AGENT_INSTRUCTIONS.md` and `AGENT_CHECKLIST.md` as the canonical guidance.
4. Add IDE-specific files only for tools used by the team.
5. Update the instruction assets whenever contract structure, validation commands or operational boundaries change.

## Relationship to Onboarding Profiles

The `agent-skill` onboarding profile describes the configuration contract for coding assistants. The `agent-instructions` command generates the actual files that can be checked into a repository.

Useful commands:

```bash
contractforge-ai profile agent-skill
contractforge-ai init --profile agent-skill --instruction-path AGENT_INSTRUCTIONS.md --output-dir ./contractforge-ai-setup
contractforge-ai agent-instructions --target all --output-dir .
```
