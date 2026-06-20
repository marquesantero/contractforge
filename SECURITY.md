# Security Policy

ContractForge handles contracts, deployment metadata, evidence and references
to secrets. It must not store plaintext credentials in contracts, examples,
logs or generated artifacts.

## Supported Versions

Security fixes are applied to the current `main` branch while the project is in
early release. Versioned support windows will be documented when the packages
reach stable release lines.

## Reporting A Vulnerability

Do not create a public issue for vulnerabilities, leaked credentials or
tenant-specific infrastructure details.

Use GitHub private vulnerability reporting or contact the repository owner
privately. Include:

- affected package or adapter;
- minimal reproduction details;
- whether credentials, tenant IDs, account IDs or logs were exposed;
- observed impact and affected runtime.

## Secret Handling Expectations

- Use `{{ secret:scope/key }}` style placeholders in contracts.
- Keep real tokens, passwords, private keys and cloud credentials out of Git.
- Do not paste secrets into issues, pull requests, logs or screenshots.
- Rotate any credential that was committed, pasted publicly or uploaded to CI.

## Maintainer Response

The maintainer will triage reports, confirm impact, prepare a fix or mitigation,
and publish a security note when public disclosure is appropriate.
