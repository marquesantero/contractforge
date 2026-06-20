# AWS Adapter Hardening Checklist

## Purpose

The AWS adapter should evolve with the same engineering shape as the Databricks reference adapter:

- strict core/adapter boundary
- optional platform SDK imports
- explicit capability and review boundaries
- domain-split modules instead of god files
- security behavior enforced before rendering or runtime execution

This checklist records the near-term hardening work before adding broad AWS runtime capability.

## Required Guardrails

| Area | Required action | Acceptance |
| --- | --- | --- |
| Architecture tests | Add `tests/test_aws_architecture.py` mirroring Databricks architecture tests. | Tests prove the core does not import AWS, AWS SDK imports are lazy/optional, and AWS modules stay below the agreed file-size threshold. |
| Runtime dependencies | Keep `boto3`/`botocore` optional under `contractforge-aws[runtime]`. | Importing `contractforge_aws` and rendering artifacts works without AWS SDKs installed. |
| Public API shape | Keep `plan_aws_contract()` and `render_aws_contract()` as the high-level adapter API. | AWS service operations stay in `contractforge_aws.runtime`, not mixed into core planning/rendering entry points. |
| Source interpretation | Add `contractforge_aws.sources.interpret` for source capability translation. | `source.intent: file_stream` and `source.type: incremental_files` use the same explicit AWS mapping rules. |
| Source security | For every executable source renderer, validate secret policy before rendering. | JDBC rejects inline passwords and URL credentials; HTTP/REST renderers validate target URLs and limits before execution. |
| Secret handling | Never bake real credentials into rendered Glue scripts or S3-published artifacts. | Secrets are represented as runtime Secrets Manager lookups or rejected. |
| HTTP/REST safety | Reuse the Databricks SSRF design when AWS gains HTTP/REST execution. | Only `http`/`https` are accepted; private/link-local targets require explicit opt-in. |
| Evidence parity | Keep AWS evidence tables generated from core evidence schemas. | Control table columns remain equivalent across adapters; AWS only maps persistence to Iceberg/Glue/S3. |
| Failure evidence | Preserve the primary Glue failure while writing best-effort error/run evidence. | Generated jobs redact exception text, append `ctrl_ingestion_errors`, append a `FAILED` `ctrl_ingestion_runs` row with `write_committed = false`, and re-raise the original exception even if evidence persistence fails. |
| Run identity and timing | Use platform run identifiers and precise write timing where available. | Generated jobs prefer Glue `JOB_RUN_ID`, fall back to timestamp + UUID, record Glue job/run ids in master fields, capture write start/finish timestamps, and capture batch rows-read before quarantine filters mutate the dataframe. |
| Capability honesty | Use `SUPPORTED_WITH_WARNINGS` or `REVIEW_REQUIRED` for semantic approximations. | No silent fallback from streaming/available-now, historical, row filters or masks to weaker behavior. |
| Module size | Split large rendering/runtime modules by domain. | Mature surfaces live in domain folders such as `annotations/`, `governance/`, `quality/`, `preparation/`, `schema/`, `state/`, `evidence/` and `lineage/`; `rendering/` is kept for cross-artifact orchestration and deployment rendering. |

## Near-Term Work Order

1. Add AWS architecture tests. **Done.**
2. Split AWS preparation rendering into focused modules. **Done.**
3. Move optional Glue/S3 runtime helpers behind a runtime-facing namespace while keeping high-level API small. **Done.**
4. Add AWS source interpretation for `file_stream` and `incremental_files`. **Done.**
5. Add HTTP/REST safety helpers before rendering executable HTTP/REST AWS jobs. **Done:** `http_file` validates targets and refuses inline secrets; `rest_api` reads through the core REST client (`contractforge_core.connectors.read_rest_api_records` / `contractforge_core.connectors.api.rest`), which validates targets and to which the Databricks runtime also delegates.
6. Promote mature rendering/runtime helper groups into domain folders. **Done:** annotations, governance, quality, preparation, schema, state, evidence and lineage are no longer flat `rendering/*_runtime.py` modules.
7. Harden generated Glue evidence ordering and failure paths. **Done:** success evidence is written only after `job.commit()`, failures write redacted error evidence plus failed run evidence, and evidence-write failures do not mask the original Glue failure.
8. Extend parity docs after each new AWS semantic mapping.

## Adapter Extension Policy

Platform behavior that the core API cannot standardize follows the order in
[adapter-parameter-policy.md](adapter-parameter-policy.md): core semantic param
→ safe default + warning → adapter extension → `REVIEW_REQUIRED` → `UNSUPPORTED`.

Prefer portable parameters over adapter extensions. When a feature needs a
different parameter count per platform (e.g. one platform needs one, AWS two),
model the superset of portable parameters in the core contract with the AWS-only ones
optional ("Core optional detail" layer), rather than reaching for an extension.
Decision test: *could a second platform implement this param under the same
semantic name?* Yes → portable optional core param (named by intent, not the
vendor API). No → adapter extension as a last resort.

Adapter extensions live in `environment.parameters.aws` (tuning/deploy) and
`extensions.aws` (execution). Security boundaries for any extension:

1. Allowlist per adapter; unknown keys warn and are never honored silently.
2. Extension values pass through the same secret/redaction path; never bake a
   credential into a rendered Glue script or S3-published artifact.
3. Contract/extension data must never relax a security control — only operator
   environment flags (e.g. `CONTRACTFORGE_ALLOW_PRIVATE_HTTP_TARGETS`) may lower
   the posture. A contract cannot disable the SSRF guard or force inline secrets.
4. Extension paths/URLs get the same traversal/SSRF validation as core fields.
5. Each adapter ignores other adapters' extension blocks.

Done: AWS reads `extensions.aws`, warns on unknown keys with
`AWS_UNKNOWN_EXTENSION`, and documents the allowlisted keys in
[extensions-aws.md](extensions-aws.md).

Done: the `rds_iam` JDBC auth path renders a runtime `_cf_rds_iam_token(...)`
call (boto3 `rds.generate_db_auth_token`) for the core's `{{rds_iam_token}}`
placeholder and strips the `contractforge.rdsIam*` metadata, so the token is
generated when the job runs and no credential is baked into the artifact.

## Non-Goals

- Do not move AWS SDK imports into the core.
- Do not make the AWS adapter mimic Databricks implementation details when AWS semantics differ.
- Do not mark a feature supported just because Glue, Athena, Lake Formation or Iceberg has a related primitive.
- Do not keep adding behavior to one large module when a domain-specific renderer/runtime file is clearer.
