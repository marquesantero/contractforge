# Changelog

All notable changes to `contractforge-ai` are documented in this file.

The format follows Keep a Changelog, and this package follows semantic
versioning as described in `../docs/specs/api-stability.md`.

## [0.3.0] - 2026-06-19

### Added

- Added release metadata for the current ContractForge AI baseline aligned
  with the 0.2.x core and adapter packages.
- Added deterministic intent-to-project generation boundaries that keep the
  core validator authoritative before generated contracts are treated as
  usable.
- Added richer review reporting expectations for generated projects, including
  prompt inputs, inferred parameters, validation decisions, warnings and
  adapter planning outcomes.

### Changed

- Updated adapter extras to depend on the 0.2.x adapter release line.
- Kept AI inference focused on translating user intent into deterministic
  generator parameters instead of bypassing contract validation.

## [0.2.8] - 2026-06-08

### Added

- Initial public alpha release of ContractForge AI.
- Deterministic project generation for ContractForge project structures.
- Project validation integration so generated projects are checked by the
  ContractForge core validator before use.
- Provider routing with offline-safe workflows for environments that cannot
  send schemas or prompts to external LLM providers.
- Prompt evaluation support for repeatable generation and review scenarios.
- HTML review/report generation for contract diagnostics, project summaries
  and validation findings.
- Enrichment hooks and control-table observability helpers for generated
  ingestion projects.
