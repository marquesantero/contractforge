# Platform Parity Analysis

ContractForge AI compares Databricks and AWS project behavior by evaluating the same core contract semantics against adapter planners.

## Command

```bash
contractforge-ai compare-platforms \
  --project-root examples/real-world/supabase-jdbc-medallion \
  --adapters databricks aws \
  --format markdown
```

## What It Reports

- shared contract fields;
- platform-specific fields;
- unsupported semantics;
- review-required semantics;
- adapter warnings and blockers;
- deployment differences;
- evidence persistence differences.

## Expected Outcome

The goal is not byte-for-byte identical YAML. The goal is minimal semantic drift:

- source intent stays the same;
- write mode stays the same;
- keys and hash behavior stay the same;
- quality rules stay the same;
- annotations, operations and access intent stay the same;
- environment and deployment binding differ explicitly.

When a platform needs review, the report must show it. AI must not convert `REVIEW_REQUIRED` or `UNSUPPORTED` into “portable”.

## Status Interpretation

Adapter parity analysis and project-structure validation intentionally separate
warning-only projects from blocked projects:

| Status | Meaning |
| --- | --- |
| `READY` | Core structure is valid and requested adapter planners returned supported plans without warnings. |
| `READY_WITH_WARNINGS` | Core structure is valid and adapter planners returned only reviewable warnings. The project remains `ready=true`, but warnings must stay visible in review material. |
| `NEEDS_DECISIONS` | Required decisions or review-required semantics remain. They must be resolved before deploy. |
| `INVALID` / `UNSAFE` | Structure, adapter planning or secret-safety checks failed. |

This is important for real projects. A known-success Databricks/AWS parity
project may still show `READY_WITH_WARNINGS` because AWS exposes warnings such
as Spark SQL quality expression portability or Iceberg hash-diff performance
review. Those warnings are useful evidence, not a reason to mark the whole
project invalid.
