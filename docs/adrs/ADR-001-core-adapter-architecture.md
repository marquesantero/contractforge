# ADR-001: Core Adapter Architecture

## Status

Accepted

## Context

ContractForge is Databricks adapter and should remain stable. ContractForge Core explores a multiplatform architecture using the same contract-first ideas.

## Decision

ContractForge Core will separate contract semantics from platform execution.

The core owns:

- contract validation
- semantic normalization
- capability matching
- abstract execution planning
- evidence vocabulary

Adapters own:

- platform capability declarations
- native artifact rendering
- optional execution
- platform-specific evidence persistence

## Consequences

The core must not import Spark, Databricks SDK, boto3, Azure SDK, Fabric SDK, or other platform runtime libraries.

Platform-specific features must enter the planner through capabilities and review markers, not `if platform == ...` branches.

