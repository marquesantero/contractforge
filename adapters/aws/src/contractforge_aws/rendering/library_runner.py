"""Render the stable AWS Glue library-runner script."""

from __future__ import annotations


def render_library_runner_script() -> str:
    return "\n".join(
        [
            '"""Stable ContractForge AWS Glue runner.',
            "",
            "This script is intentionally contract-agnostic. The Glue job passes",
            "ContractForge contract/environment S3 URIs as arguments; the installed",
            "contractforge-aws runtime loads and executes them.",
            '"""',
            "",
            "from contractforge_aws.runtime.library_runner import main",
            "",
            "",
            "if __name__ == '__main__':",
            "    main()",
            "",
        ]
    )


__all__ = ["render_library_runner_script"]
