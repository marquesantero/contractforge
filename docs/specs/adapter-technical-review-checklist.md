# Adapter Technical Review Checklist

Status: Approved execution checklist

Purpose: define the review checklist that ContractForge will use before adding
or promoting platform adapters. Each adapter is reviewed as an independent
module. Do not assume shared state, shared credentials, shared runtime clients,
or shared deployment behavior across adapters.

Initial scope:

1. AWS adapter: `adapters/aws/src/contractforge_aws`
2. Databricks adapter: `adapters/databricks/src/contractforge_databricks`
3. Snowflake adapter: `adapters/snowflake/src/contractforge_snowflake`
4. Fabric adapter: `adapters/fabric/src/contractforge_fabric`
5. GCP adapter: `adapters/gcp/src/contractforge_gcp`

## Review Rules

1. Review every adapter independently.
2. Ground every finding in a file and line number.
3. Prefer concrete risks over generic style advice.
4. Treat generated runtime code as production code when it is executed by Glue,
   Databricks, Snowflake, Fabric, or GCP service.
5. Record both positive controls and violations when they affect risk.
6. Do not mark an item violated only because it exists. For example,
   `except Exception` is acceptable only when it preserves context, redacts
   sensitive data, and is part of an explicit adapter boundary.
7. Use the severity model below consistently.

## Severity Model

| Level | Criterion |
| --- | --- |
| CRITICAL | Exploitable security issue, likely data loss, silent production corruption, or unbounded destructive operation. |
| HIGH | Major architecture violation, bypassable governance/authentication, broad production instability, or testing blocker. |
| MEDIUM | Recurring bad practice, confusing implementation, missing guardrail, or technical debt that can become operational risk. |
| LOW | Local improvement, minor style issue, documentation gap, or low-risk optimization. |

## Evidence Standard

Each finding must include:

- adapter name;
- dimension;
- severity;
- checklist item;
- file path and line number;
- short code evidence;
- production impact;
- recommended fix.

When a checklist item is assessed and no issue is found, do not create a finding.
Mention important positive controls in the executive summary only when useful.

## 1. Security

### Credential And Sensitive Data Management

- [ ] Credentials, tokens, API keys, PATs, private keys, passwords, or secrets
      are hardcoded in adapter code, comments, docs, templates, tests intended
      as production examples, or committed config files.
- [ ] Sensitive data can appear in logs, rendered review artifacts, command
      output, query tags, evidence rows, exception notes, stack traces, or
      generated runtime code.
- [ ] Environment variables are read without explicit defaults, validation, or
      clear failure messages.
- [ ] Secret placeholders are not enforced for connector auth fields that can
      carry credentials.
- [ ] Secret redaction is missing from adapter error handling, evidence writing,
      runtime failure paths, or CLI output.
- [ ] Local smoke config files with real connection material are referenced from
      committed docs or examples without warning or exclusion.

### Input Validation And Sanitization

- [ ] External contract fields are accepted without type, size, allowed-value, or
      identifier validation.
- [ ] Critical fields lack allowlists, including table names, schema names,
      warehouse names, role names, stage names, task names, job names, IAM/Lake
      Formation principals, Unity Catalog objects, and GCP resource names.
- [ ] Third-party payloads are deserialized without schema validation or
      explicit shape checks.
- [ ] Query strings, URL parts, path fragments, object-storage keys, or stage
      paths are used directly without normalization and safety checks.
- [ ] Adapter-specific extension dictionaries are passed through without
      validating known keys, modes, and policy values.

### Injection Vulnerabilities

- [ ] SQL is built from external input without identifier quoting, literal
      escaping, or a reviewed renderer.
- [ ] Shell commands are assembled from external input or passed through
      `shell=True`, `os.system`, or equivalent.
- [ ] Generated Python, SQL, YAML, JSON, or task templates inject external data
      without escaping or syntax validation.
- [ ] File paths are built from user input without checking path traversal,
      absolute paths, drive-qualified paths, or stage path traversal.
- [ ] `eval`, `exec`, `pickle`, or dynamic imports execute untrusted data.
- [ ] Runtime library runners execute generated code without an allowlist,
      validation pass, or explicit trust boundary.

### Dependencies And Libraries

- [ ] Adapter dependencies are declared without version bounds or pins that make
      releases reproducible.
- [ ] Known-vulnerable dependency versions are present in the resolved
      environment or lock file.
- [ ] Optional runtime extras are imported on the default core import path.
- [ ] Unused imports add unnecessary dependency surface.
- [ ] Deprecated or unmaintained libraries are used for production paths.

### Network And Communication

- [ ] HTTP calls omit timeouts.
- [ ] TLS certificate validation is disabled or configurable to insecure values
      without an explicit review-required policy.
- [ ] Sensitive data is sent in URL query parameters where headers or secret
      managers should be used.
- [ ] Custom TLS, JDBC, ODBC, object-storage, or platform clients omit
      certificate/host validation or secure defaults.
- [ ] External API pagination, retries, or failure handling can loop forever or
      silently drop partial results.

### Access Control And Authentication

- [ ] Adapter operations assume broad admin roles instead of least-privilege
      execution roles.
- [ ] Destructive grant/revoke, table drop, task/procedure deletion, or policy
      changes can execute without explicit opt-in or review-required gating.
- [ ] Tokens are cached without expiration, renewal, or scope separation.
- [ ] Sensitive operations lack rate limiting, bounded polling, or retry caps.
- [ ] Cross-account, cross-workspace, cross-catalog, or cross-project access is
      not made explicit in environment or deployment artifacts.

## 2. Development Standards

### Python Idioms

- [ ] Uses Python anti-patterns such as `type(x) == T`, `== None`, mutable
      defaults, broad truthiness where explicit checks are required, or manual
      resource cleanup where context managers are appropriate.
- [ ] Resources requiring cleanup are not managed with `with`, `try/finally`, or
      adapter-specific close semantics.
- [ ] Verbose loops could be clearer as comprehensions without hurting
      readability.
- [ ] Uses `range(len(x))` where `enumerate` is clearer.
- [ ] String formatting is inconsistent or unsafe for the target language.
- [ ] Public API modules lack `__all__` where the adapter intentionally exports
      a stable surface.

### Type Hints And Contracts

- [ ] Public functions or methods are missing parameter or return type hints.
- [ ] `Any` is used where a protocol, dataclass, TypedDict, Mapping, Sequence, or
      domain model would better describe the contract.
- [ ] Type hints disagree with runtime behavior.
- [ ] Complex return dictionaries lack dataclasses, TypedDicts, or documented
      payload schemas.
- [ ] Functions can return `None` implicitly but do not declare that behavior.

### Design Patterns And Architecture

- [ ] A class or function violates single responsibility by mixing planning,
      rendering, deployment, runtime execution, evidence writing, and cleanup in
      one unit.
- [ ] Concrete platform clients are instantiated inside business logic with no
      injection path for testing.
- [ ] Adapter boundaries lack protocols or small wrapper abstractions for
      platform clients.
- [ ] Inheritance is used where composition or strategy registries would be
      simpler.
- [ ] God modules, god functions, or god classes own unrelated behavior.
- [ ] Business logic is mixed with infrastructure mutation in a way that blocks
      dry-run, review-only, or unit tests.

### Documentation

- [ ] Public functions or CLI commands lack docstrings or usage documentation
      where behavior is non-obvious.
- [ ] Docstrings, README examples, or site docs are stale relative to current
      behavior.
- [ ] Comments explain obvious code rather than non-obvious decisions.
- [ ] Review-required behavior is implemented but not documented.
- [ ] Live-smoke prerequisites, grants, roles, cleanup behavior, and cost
      implications are missing or ambiguous.

### PEP 8 And Local Style

- [ ] Lines exceed the local project tolerance without readability
      justification.
- [ ] Names do not follow Python conventions or local adapter conventions.
- [ ] Imports are unordered or not grouped as stdlib, third-party, local.
- [ ] Top-level functions/classes have inconsistent spacing.
- [ ] New code does not follow existing adapter layout, registry, or rendering
      conventions.

## 3. Code Reuse

### Internal Duplication

- [ ] Similar rendering, validation, redaction, polling, pagination, quoting, or
      evidence-writing logic is duplicated inside the same adapter.
- [ ] Data transformation logic is copied between runtime paths without a shared
      helper.
- [ ] The same validation rules are rewritten at multiple entry points.
- [ ] Repeated literals or control-table names should be named constants.

### Structuring And Extraction

- [ ] Long functions over 30 lines should be decomposed unless they are simple
      declarative renderers.
- [ ] Functions over 50 lines need explicit justification or extraction.
- [ ] Complex inline logic should be extracted into named private helpers.
- [ ] Deep nesting should be replaced with guard clauses or early returns.
- [ ] Switch-like `if`/`elif` chains should become registries or dispatch maps
      when they grow or mirror adapter capability tables.

### Existing Abstractions

- [ ] Stdlib utilities are reimplemented unnecessarily.
- [ ] Core project helpers for redaction, naming, validation, source handling,
      schema policy, or evidence records are bypassed.
- [ ] Existing adapter patterns are ignored without a documented reason.
- [ ] Shared constants are copied instead of imported from the adapter's local
      constants module.

## 4. Code Quality

### Readability

- [ ] Variable names are semantically weak outside trivial loops.
- [ ] Functions take more than 3-4 related parameters where a dataclass/config
      object would improve clarity.
- [ ] Boolean conditions are unnecessarily inverted or double-negated.
- [ ] Conditional logic has more than 3 nested levels without helper extraction.
- [ ] Magic numbers or magic strings are used without named constants.

### Exception Handling

- [ ] `except Exception` or bare `except` catches unexpected failures without
      preserving context, redacting secrets, or marking the path as diagnostic.
- [ ] Exceptions are caught and discarded with `pass` without a recovery reason.
- [ ] Re-raised exceptions lose original context.
- [ ] Exceptions are used as normal control flow where explicit checks are
      available.
- [ ] Adapter domain errors lack custom exception types or clear error messages.
- [ ] Error messages lack enough context for production diagnostics.

### Complexity

- [ ] High cyclomatic complexity creates many independent execution paths.
- [ ] Functions exceed 50 lines without clear decomposition.
- [ ] Classes expose more than 10 public methods without clear cohesion.
- [ ] Modules exceed 300 lines and mix unrelated concerns.
- [ ] Generated code renderers are difficult to inspect, validate, or test.

### Consistency

- [ ] Similar functions return inconsistent types or payload shapes.
- [ ] Similar operations handle errors differently without reason.
- [ ] Logging and CLI output styles are inconsistent.
- [ ] Similar parameters use different names across planner, runtime, CLI, and
      smoke paths.
- [ ] Dry-run, validate-only, execute, wait, and cleanup semantics differ across
      similar commands without documentation.

## 5. Performance

### I/O And External Calls

- [ ] External API calls happen inside loops where batching or pagination can be
      used.
- [ ] Reused HTTP, database, Spark, Snowflake, Databricks, AWS, Fabric, or GCP
      clients are not pooled or injected.
- [ ] Large files or stage artifacts are read entirely into memory where
      streaming would be practical.
- [ ] Blocking calls are used where the adapter already has async-compatible
      infrastructure.
- [ ] I/O calls lack timeouts, bounded polling, or cancellation paths.

### Data Structures And Algorithms

- [ ] Lists are used for repeated membership checks where sets are clearer and
      faster.
- [ ] Large structures are recreated on every call without need.
- [ ] Data is repeatedly sorted or normalized without caching within the same
      flow.
- [ ] String concatenation in loops should use `join`.

### Caching And Optimization

- [ ] Expensive deterministic operations are not cached where repeat calls are
      expected.
- [ ] Static configuration or platform metadata is reloaded repeatedly in a
      single adapter invocation.
- [ ] Idempotent computations are repeated multiple times in one flow.
- [ ] Polling intervals or maximum waits are unbounded or not configurable.

### Memory

- [ ] Large objects are retained beyond their useful scope.
- [ ] Eager lists should be lazy iterators/generators for large datasets.
- [ ] Classes instantiated many times with fixed attributes may benefit from
      dataclasses with slots or `__slots__`.

## 6. Testability

### Coupling And Dependency Injection

- [ ] Platform clients, HTTP clients, DB sessions, filesystem access, or clock
      functions are instantiated internally with no injection point.
- [ ] Global variables or singletons share mutable state between tests or runs.
- [ ] Module-level imports have side effects or require optional runtime
      dependencies on import.
- [ ] Calls to `datetime.now`, `uuid.uuid4`, or random generators affect tests
      without injection, wrapper helpers, or stable assertions.

### Side Effects

- [ ] Functions read from filesystem, network, cloud APIs, or platform sessions
      without a mockable intermediate abstraction.
- [ ] Functions mix pure planning/rendering logic with external mutations.
- [ ] Mutating functions do not return enough structured data for assertions.
- [ ] Cleanup paths are not executed in `finally` blocks for live smoke or
      destructive tests.

### Coverage Expectations

- [ ] Error paths lack apparent tests.
- [ ] Critical branches lack tests for both success and failure.
- [ ] Empty, null, malformed, and maximum-size inputs are not covered where they
      affect safety.
- [ ] Timeout, unavailable service, permission denied, and partial failure
      behavior lacks tests.
- [ ] Live-smoke-only behavior lacks a unit-testable approximation.

### Test Structure

- [ ] Classes cannot be instantiated in isolation for unit tests.
- [ ] Obvious fixtures are missing or duplicated.
- [ ] Methods have multiple responsibilities that force heavy test setup.
- [ ] Void functions should return structured results to support assertions.
- [ ] CLI commands cannot be tested without real cloud credentials.

## Report Template

Use this template for each adapter.

```markdown
# Report: `<adapter_name>`

## Executive Summary

<Overall diagnosis, risk level, notable positive controls, and main blockers.>

## Findings By Dimension

### Security

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| HIGH | ... | `path.py:123` / `function_name` | `snippet` | ... |

### Development Standards

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |

### Code Reuse

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |

### Code Quality

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |

### Performance

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |

### Testability

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |

## Severity Metrics

| Level | Count |
| --- | --- |
| Critical | N |
| High | N |
| Medium | N |
| Low | N |

Health score: X/10

Checklist items violated: N out of M assessed items.

## Top 3 Immediate Actions

1. ...
2. ...
3. ...
```

## Consolidated Report Template

```markdown
# Adapter Technical Review Summary

## Comparative Health Scores

| Adapter | Critical | High | Medium | Low | Health score |
| --- | ---: | ---: | ---: | ---: | ---: |
| AWS | 0 | 0 | 0 | 0 | 0/10 |
| Databricks | 0 | 0 | 0 | 0 | 0/10 |
| Fabric | 0 | 0 | 0 | 0 | 0/10 |
| Snowflake | 0 | 0 | 0 | 0 | 0/10 |
| GCP | 0 | 0 | 0 | 0 | 0/10 |

## Recurring Patterns

- ...

## Risk/Effort Matrix

|  | Low effort | High effort |
| --- | --- | --- |
| High risk | ... | ... |
| Low risk | ... | ... |
```

## Execution List

Run this list for each adapter independently. Complete one adapter report before
starting the next adapter report.

### 1. Prepare Review Context

- [ ] Identify adapter package root.
- [ ] Identify adapter CLI entrypoints.
- [ ] Identify adapter optional runtime dependencies.
- [ ] Identify adapter docs, smoke commands, and stabilization matrices.
- [ ] Identify adapter tests and live-smoke tests.
- [ ] Confirm whether live credentials are available.
- [ ] Confirm whether dependency audit tooling is available.

### 2. Run Static Discovery

- [ ] Search for hardcoded credentials, tokens, passwords, private keys, PATs,
      API keys, and committed connection files.
- [ ] Search for redaction paths around logs, errors, evidence, CLI output, and
      generated runtime code.
- [ ] Search for unsafe dynamic execution: `eval`, `exec`, `pickle`, dynamic
      imports, runtime generated Python execution, and library runners.
- [ ] Search for shell execution: `subprocess`, `os.system`, shell strings, and
      platform command wrappers.
- [ ] Search for SQL construction and verify identifier/literal escaping.
- [ ] Search for path construction and verify traversal protections.
- [ ] Search for HTTP/JDBC/platform calls and verify timeouts, retries, and TLS
      defaults.
- [ ] Search for broad `except Exception` handling and verify context/redaction.
- [ ] Search for module-level imports of optional cloud SDKs on default import
      paths.
- [ ] Search for large modules and long functions that may need decomposition.

### 3. Review Security

- [ ] Assess credential and sensitive data management.
- [ ] Assess input validation and sanitization.
- [ ] Assess SQL, shell, template, path, and dynamic-execution injection risks.
- [ ] Assess dependency and optional-extra isolation.
- [ ] Assess network safety: TLS, timeout, retry, and pagination behavior.
- [ ] Assess access control, destructive-operation gating, and least privilege.
- [ ] Record only concrete findings with file/line evidence.

### 4. Review Development Standards

- [ ] Assess Python idioms and resource cleanup patterns.
- [ ] Assess type hints and contracts.
- [ ] Assess adapter architecture and separation of planning, rendering,
      runtime, deployment, evidence, and cleanup concerns.
- [ ] Assess documentation and examples against actual behavior.
- [ ] Assess PEP 8 and local adapter style consistency.
- [ ] Record only concrete findings with file/line evidence.

### 5. Review Code Reuse

- [ ] Assess duplicated validations, renderers, redaction, quoting, polling,
      pagination, and evidence-writing logic.
- [ ] Assess long functions and complex inline logic for extraction.
- [ ] Assess whether core helpers and adapter-local abstractions are reused.
- [ ] Record only concrete findings with file/line evidence.

### 6. Review Code Quality

- [ ] Assess readability, parameter shape, naming, booleans, and magic values.
- [ ] Assess exception handling and adapter-domain error clarity.
- [ ] Assess complexity by function, class, and module.
- [ ] Assess consistency across CLI, planner, runtime, deploy, smoke, and docs.
- [ ] Record only concrete findings with file/line evidence.

### 7. Review Performance

- [ ] Assess external calls in loops and pagination behavior.
- [ ] Assess client/session reuse and injection.
- [ ] Assess large file and artifact memory behavior.
- [ ] Assess data structure choices and repeated deterministic computations.
- [ ] Assess cache opportunities and bounded polling.
- [ ] Record only concrete findings with file/line evidence.

### 8. Review Testability

- [ ] Assess dependency injection for platform clients, filesystem, clocks, UUIDs,
      random values, and live sessions.
- [ ] Assess separation of pure planning/rendering logic from side effects.
- [ ] Assess error-path, timeout, permission-denied, malformed-input, and cleanup
      test coverage.
- [ ] Assess whether CLI commands can be tested without real cloud credentials.
- [ ] Record only concrete findings with file/line evidence.

### 9. Run Verification

- [ ] Run adapter-focused unit tests.
- [ ] Run cross-adapter tests affected by the adapter.
- [ ] Run full test suite when changes or findings affect shared contracts.
- [ ] Run build/package checks.
- [ ] Run CLI help checks for adapter entrypoints.
- [ ] Run live smoke only when credentials are available and cleanup is safe.
- [ ] Verify live smoke cleanup leaves no adapter-created temporary resources.

### 10. Produce Adapter Report

- [ ] Write the adapter report using the report template.
- [ ] Include severity metrics.
- [ ] Include health score.
- [ ] Include top 3 immediate actions.
- [ ] Include important positive controls in the executive summary when they
      reduce risk.
- [ ] Avoid findings without actionable remediation.

### 11. Produce Consolidated Report

- [ ] Add comparative health score table.
- [ ] Add recurring patterns across adapters.
- [ ] Add global risk/effort prioritization matrix.
- [ ] Separate adapter-specific findings from cross-adapter recommendations.
