# AWS Stable-Surface Waiver Registry

## Purpose

This registry records any exception that allows the AWS stable supported
surface to proceed while a specific criterion in
[aws-ga-criteria.md](aws-ga-criteria.md) is not fully met.

Waivers are scoped, auditable and temporary. They do not allow silent semantic
downgrades.

## Waiver Rules

A waiver is allowed only when all of the following hold:

- the gap is not a core platform-isolation, secret-handling or data-loss
  control;
- the affected behavior is documented in user-facing docs and release notes;
- the adapter returns `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or
  `UNSUPPORTED` instead of claiming full support;
- a remediation owner and target date are recorded;
- the waiver expires within 90 days unless renewed as a new registry row.

Waivers are forbidden for:

- core importing AWS SDKs;
- plaintext secrets in rendered artifacts;
- write modes that lose rows or report incorrect successful metrics;
- failures that skip `ctrl_ingestion_errors` and failed-run evidence when the
  evidence store is reachable;
- Lake Formation behavior that grants broader access than the contract declares
  without explicit review.

## Registry

| ID | Criterion | State | Recorded | Expires | Owner |
| --- | --- | --- | --- | --- | --- |

No waivers are currently recorded.

## Active Waivers

No active waivers.

The remaining AWS production-certification boundaries are not waivers because
they are not claimed as stable behavior. They remain explicit
`SUPPORTED_WITH_WARNINGS` or `REVIEW_REQUIRED` boundaries in
[aws-ga-criteria.md](aws-ga-criteria.md) and
[aws-stabilization-matrix.md](aws-stabilization-matrix.md).

## Expired Waivers

No expired waivers.

## Revoked Waivers

No revoked waivers.
