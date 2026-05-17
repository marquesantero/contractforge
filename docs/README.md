# ContractForge Documentation

This directory contains the versioned technical documentation for ContractForge. For a navigable web experience, use the published documentation site:

https://marquesantero.github.io/contractforge/

## Start Here

- [Quick start](quickstart.md): minimal flow to validate the installation, run an ingestion and inspect control tables.
- [Official reference](oficial.md): complete reference for contracts, write modes, connectors, shape, governance and observability.
- [Usage guide](guia_de_uso.md): operational walkthrough for packages, notebooks, YAML contracts and Databricks Workflows.
- [Contract templates](templates.md): ready-to-copy scenarios for REST, JDBC, Auto Loader, SCD, snapshot and gold tables.

## Technical Reference

- [Architecture](arquitetura.md): internal modules, execution flow, edge cases and design decisions.
- [ADRs](adrs/README.md): formal architecture decision records.
- [Changelog](../CHANGELOG.md): release history and versioning policy.

## Topic Guides

- [Connector compatibility](compatibilidade_conectores.md): connector matrix, dependencies and runtime support.
- [RDS/Aurora JDBC with IAM Auth](rds_iam_jdbc.md): complete setup for `source.auth.type=rds_iam`, grants, IAM policy, secrets and troubleshooting.
- [Operations and maintenance](operacao.md): control table retention, cleanup/VACUUM and operational practices.
- [Operational dashboards](dashboards/README.md): Databricks SQL/Lakeview blueprint and queries for runs, quality, failures, streams, SLA, connectors and governance.
- [Performance](performance.md): guidelines for write modes, cache, JDBC, REST, Delta layout and metrics.
- [Security](seguranca.md): practices for secrets, explain plans, lineage, control tables and quarantine.
- [Anti-patterns](antipadroes.md): risky configurations and recommended alternatives.
- [Project template](template_projeto.md): recommended structure with contracts, notebooks and Databricks Asset Bundles.
- [Playground](../examples/playground/README.md): example project with complete contracts that can be validated by CLI.

## Website

The GitHub Pages site is published from the `gh-pages` branch:

https://marquesantero.github.io/contractforge/

The Markdown files in this directory are the versioned technical source in the repository.
