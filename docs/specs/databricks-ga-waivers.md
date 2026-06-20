# Databricks GA Criteria — Waiver Registry

## Purpose

The Databricks GA gate documented in
[databricks-ga-criteria.md](databricks-ga-criteria.md) is intentionally
strict. A waiver is the documented exception that allows the `1.0.0`
release window to proceed when one criterion cannot be met by the cutoff
date.

A waiver is never blanket. Each one is scoped to a single criterion, has a
named accountable owner, an expiration date, and a remediation plan. The
GA review uses this file as the source of truth for which exceptions are
currently in force.

If this file does not list a waiver for a specific criterion, that
criterion is treated as `not_met` for the purposes of the release
checklist.

## When A Waiver Is Allowed

A waiver may be granted only when **all** of the following hold:

- the criterion is not a security or data-correctness control;
- the gap is documented with reproducible evidence (test ids, smoke run
  links, or workspace logs);
- a concrete remediation plan exists with a target date no more than 90
  days after the waiver is recorded;
- there is no workaround that introduces silent semantic degradation;
- the affected behavior is either documented as a known limitation in
  the user-facing CHANGELOG or behind a feature flag.

Waivers are forbidden for:

- core platform isolation (any violation blocks GA outright);
- adapter independence boundaries;
- evidence persistence for `ctrl_ingestion_runs` and
  `ctrl_ingestion_errors`;
- write modes producing incorrect row counts or losing rows;
- governance application that silently grants more access than declared.

## Waiver Lifecycle

Each waiver moves through three states:

- `active` — recorded, in force, blocking nothing.
- `expired` — past its expiration date and not renewed. The release
  checklist must treat the underlying criterion as `not_met` until the
  waiver is renewed or the criterion is met.
- `revoked` — withdrawn before expiration, either because the criterion
  was met or because the underlying condition for the waiver no longer
  holds.

Once a waiver is recorded, its row in the registry below is never
deleted. It is only marked `expired` or `revoked` with a date and reason.
This preserves audit history.

## Approval Requirements

- The project maintainer approves any waiver and is the default owner
  unless another owner is explicitly assigned.
- A second reviewer is required for waivers that touch evidence,
  governance or quality criteria (sections 4, 5, 7 of the GA criteria).
- Approvals are recorded in the registry row, not in PR comments.
- Renewals reset the 90-day clock and are recorded as a new row, not by
  editing the original.

## Waiver Entry Format

Every waiver is one row in the registry table below, plus one subsection
under "Active Waivers" with full detail.

The detail subsection must contain:

- **Criterion**: the exact section heading from
  [databricks-ga-criteria.md](databricks-ga-criteria.md).
- **State**: `active`, `expired` or `revoked`.
- **Recorded**: ISO date.
- **Expires**: ISO date (90 days max from recorded).
- **Owner**: GitHub handle of the accountable person.
- **Approver(s)**: GitHub handle(s) of the approving maintainer(s).
- **Reason**: why the criterion cannot be met by the GA cutoff.
- **Evidence**: links to test ids, smoke runs or logs.
- **Workaround**: what behavior consumers see in the meantime; must not
  introduce silent semantic degradation.
- **Remediation plan**: concrete steps and target date for closure.
- **Renewal policy**: whether renewal is anticipated and under what
  condition.

## Registry

The registry table is the authoritative summary. It is consulted by the
release checklist and by the GA review process.

| ID | Criterion | State | Recorded | Expires | Owner |
| --- | --- | --- | --- | --- | --- |

No waivers are currently recorded. The registry above is intentionally
empty so that the first entry establishes the format precedent.

## Active Waivers

No active waivers.

## Expired Waivers

No expired waivers.

## Revoked Waivers

No revoked waivers.

## Cross-References

- Gate definition: [databricks-ga-criteria.md](databricks-ga-criteria.md)
- Reference implementation surface: [databricks-adapter.md](databricks-adapter.md)
- Adapter parameter policy: [adapter-parameter-policy.md](adapter-parameter-policy.md)
- API stability: [api-stability.md](api-stability.md)
