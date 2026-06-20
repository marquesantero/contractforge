# AWS Project Generation

The AWS target is `aws-glue-iceberg`. ContractForge AI should generate contracts and project scaffolds that use the AWS adapter runtime-library model, not per-contract generated ingestion code as the default.

## Generated Artifacts

An AWS project should include:

- `project.yaml`
- `environments/aws.environment.yaml`
- optional `connections/*.yaml`
- split contracts
- `README.md`
- `RUNBOOK.md`
- `VALIDATION.md`
- `DECISIONS.md`
- `AI_REVIEW.html` for guided generation
- `project_validation.html` when `validate-project-structure --format html` is run

## Deployment Flow

The intended runtime flow is:

1. Validate the project deterministically with `contractforge-ai validate-project-structure`.
2. Resolve connection YAML and split bundles through the core.
3. Publish contracts and runtime artifacts to the environment artifact URI.
4. Create or update Glue jobs and orchestration through `contractforge-aws deploy-project`.
5. Glue jobs load the contract at runtime and call the AWS adapter runtime library.

The contract remains configuration. The adapter runtime owns source reading, preparation, quality, writes, evidence and state.

## Example Command

```bash
contractforge-ai generate-project \
  --target aws-glue-iceberg \
  --schema schemas/orders.json \
  --project-name orders_aws \
  --connector s3 \
  --source-path s3://landing/orders \
  --target-catalog analytics \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir generated/orders-aws
```

Then:

```bash
contractforge-ai validate-project-structure generated/orders-aws --adapter aws --format html > project_validation.html
contractforge-aws deploy-project generated/orders-aws/project.yaml --environment generated/orders-aws/environments/aws.environment.yaml
```

`READY_WITH_WARNINGS` means the generated project is structurally valid and
`ready=true`, while AWS adapter warnings remain visible for review. Treat
`NEEDS_DECISIONS`, `INVALID` and `UNSAFE` as non-deployable until resolved.

## Review Boundaries

AI must preserve:

- no AWS SDK dependency in the core;
- no generated Glue ingestion code as the default execution model;
- AWS-native settings only under environment/deployment/extension namespaces;
- planner warnings for Lake Formation, historical, streaming and other review-required semantics.
