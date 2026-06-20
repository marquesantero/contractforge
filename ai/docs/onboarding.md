# Onboarding Profiles

ContractForge AI supports multiple integration profiles because the same assistant capability is used in different execution contexts: a developer workstation, CI, Databricks notebooks, Databricks jobs, coding assistants and future service/tool integrations.

The profile layer is deterministic. It does not call a model provider. It describes required configuration, unsupported capabilities and recommended commands so setup issues can be found before a user reaches a failed job or an incomplete generated project.

## List Profiles

```bash
contractforge-ai profiles
```

For automation:

```bash
contractforge-ai profiles --format json
```

Supported profiles:

| Profile | Use case |
| --- | --- |
| `local-cli` | Local review, diagnostics and project generation from a developer workstation. |
| `github-actions` | Non-interactive CI checks for contract review and pull-request feedback. |
| `databricks-notebook` | Notebook diagnostics and ContractForge control-table evidence collection. |
| `databricks-job` | Runtime-safe execution inside Databricks Jobs or Databricks Asset Bundles. |
| `agent-skill` | Instruction assets for coding assistants working on ContractForge projects. |
| `mcp` | Future MCP/tool wrapper profile for safe review and generation services. |

## Validate One Profile

Use `profile` to inspect the contract for one integration style:

```bash
contractforge-ai profile databricks-job
```

Pass a JSON configuration file when validating a concrete setup:

```json
{
  "catalog": "main",
  "ctrl_schema": "ops",
  "workspace_profile": "prod"
}
```

```bash
contractforge-ai profile databricks-job --config databricks-profile.json --format json
```

The validation result reports missing required configuration and capabilities that should not be used in that context. For example, `github-actions` and `databricks-job` reject interactive prompt expectations because those flows must be non-interactive.

## Environment Report

Use `environment-report` before troubleshooting provider setup, Databricks setup or generated scaffold execution:

```bash
contractforge-ai environment-report
```

For CI, notebooks or support bundles:

```bash
contractforge-ai environment-report --format json
```

The report includes:

| Section | Contents |
| --- | --- |
| `python_version` and `platform` | Local runtime information for reproducibility. |
| `packages` | Backward-compatible flat package availability map. |
| `package_groups` | Classified package availability for ContractForge packages, optional adapters, parser dependencies, provider clients and platform SDKs. |
| `commands` | Availability of `databricks`, `git` and `dbt`. |
| `provider_environment` | Provider-related environment variables with secret values redacted. |
| `databricks` | Notebook detection, CLI availability, SDK availability and host/token presence. |
| `warnings` | Human-readable setup risks that should be resolved before deeper diagnostics. |

Secret-like values are not printed. Keys containing markers such as `key`, `token`, `secret` or `password` are represented as `[REDACTED]`.

Package groups make the wheel split visible:

| Group | Packages | Required when |
| --- | --- | --- |
| `contractforge` | `contractforge_core`, `contractforge_ai` | Always for deterministic AI validation and generation. |
| `adapters` | `contractforge_databricks`, `contractforge_aws` | Only when running adapter-aware validation, deployment guidance or platform execution workflows. |
| `parsing` | `yaml` | YAML contracts, project files and onboarding configuration. |
| `provider_clients` | `openai`, `boto3` | Provider-enriched AI output through OpenAI-compatible providers or AWS Bedrock. |
| `platform_sdks` | `databricks.sdk` | Databricks evidence collection and Databricks provider/model-serving workflows. |

Missing adapter packages are not treated as a setup failure by default. They become actionable only when the user asks for adapter-specific checks, such as `validate-project-structure --adapter databricks --adapter aws`.

## Generate Onboarding Files

Use `init` to generate a reviewable setup file and setup report:

```bash
contractforge-ai init \
  --profile databricks-job \
  --catalog main \
  --ctrl-schema ops \
  --output-dir ./contractforge-ai-setup
```

Generated files:

| File | Purpose |
| --- | --- |
| `contractforge-ai.yaml` | Non-secret setup configuration for the selected integration profile. |
| `SETUP_REPORT.md` | Human-readable evidence, warnings, assumptions and decisions required before using the setup. |

Run without writing files:

```bash
contractforge-ai init \
  --profile databricks-job \
  --catalog main \
  --ctrl-schema ops \
  --dry-run \
  --format json
```

Generate a provider-enriched setup without writing secrets to disk:

```bash
contractforge-ai init \
  --profile local-cli \
  --mode provider-enriched \
  --provider openai \
  --model gpt-4.1 \
  --output-dir ./contractforge-ai-setup
```

The generated configuration references environment variables such as `OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `DATABRICKS_HOST` and `DATABRICKS_TOKEN`. It does not persist secret values.

Existing files are skipped by default. Use `--force` only when intentionally replacing a previous setup:

```bash
contractforge-ai init --profile local-cli --output-dir ./contractforge-ai-setup --force
```

## Generate Agent Instructions

Use `agent-instructions` when a repository needs consistent guidance for coding assistants and IDE agents:

```bash
contractforge-ai agent-instructions \
  --target all \
  --project-name "Orders Platform" \
  --contract-root contracts \
  --output-dir .
```

Supported targets are `generic`, `codex`, `claude`, `cursor`, `github-copilot` and `all`.

Generated files include canonical guidance and a completion checklist:

| File | Purpose |
| --- | --- |
| `AGENT_INSTRUCTIONS.md` | Main repository guidance for assistant behavior, deterministic validation and safety rules. |
| `AGENT_CHECKLIST.md` | Completion checklist for contract review, generated output and validation. |
| `.codex/contractforge-instructions.md` | Codex-specific entrypoint when `--target codex` or `--target all` is used. |
| `CLAUDE.md` | Claude-specific entrypoint when `--target claude` or `--target all` is used. |
| `.cursor/rules/contractforge.mdc` | Cursor rule file when `--target cursor` or `--target all` is used. |
| `.github/copilot-instructions.md` | GitHub Copilot repository instructions when `--target github-copilot` or `--target all` is used. |

Preview the generated assets:

```bash
contractforge-ai agent-instructions --target all --dry-run --format json
```

See [Agent and IDE Instruction Assets](agent-instructions.md) for the full command reference and recommended repository workflow.

## Recommended Setup Flow

1. Run `contractforge-ai environment-report --format json` and keep the output with the project onboarding evidence.
2. Choose the integration profile that matches the execution context.
3. Run `contractforge-ai profile <profile> --config <config.json>`.
4. Generate onboarding files with `contractforge-ai init`.
5. Fix missing required configuration before enabling CI gates, notebooks or jobs.
6. Run the deterministic ContractForge AI command for that profile, such as `review`, `explain-run` or `generate-project`.

## Profile Guidance

### Local CLI

Use this profile for developer onboarding and local project generation. A model provider is optional. Deterministic commands work without OpenAI, Azure OpenAI or Databricks connectivity.

Recommended commands:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml
contractforge-ai explain-run --input failed-run.json
contractforge-ai generate-project --target contractforge-yaml ...
```

### GitHub Actions

Use this profile for pull-request validation. Keep output machine-readable and avoid interactive behavior.

Recommended command:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --fail-on high --format json
```

### Databricks Notebook

Use this profile when a human is investigating a failed run or collecting evidence from ContractForge control tables. Required configuration is the catalog and control schema that hold the ContractForge control tables.

Recommended command:

```bash
contractforge-ai explain-run --run-id <run_id> --catalog <catalog> --ctrl-schema <schema>
```

### Databricks Job

Use this profile for Databricks Asset Bundle jobs and other non-interactive job runs. Do not rely on prompts, local files outside the bundle or credentials that are not available through the runtime.

Recommended commands:

```bash
databricks bundle run <job-name>
contractforge-ai explain-run --run-id <run_id> --catalog <catalog>
```

### Agent Skill

Use this profile for coding assistant instructions. The assistant should be constrained to reviewable file changes and deterministic validation. It should not mutate production data or resolve secrets.

### MCP

Use this profile for future service-style tool boundaries. Tools should expose narrow, reviewable operations such as contract review, environment reporting and project-plan generation, not unrestricted filesystem or production access.
