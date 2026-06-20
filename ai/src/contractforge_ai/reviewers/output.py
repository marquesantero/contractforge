"""Output helpers for deterministic contract review results."""

from __future__ import annotations

from contractforge_ai.models import ReviewResult


def review_to_markdown(result: ReviewResult) -> str:
    """Render a concise Markdown report suitable for pull request comments."""

    lines = [
        "## ContractForge AI Review",
        "",
        f"- **Contract:** `{result.contract_path}`",
        f"- **Status:** `{result.status}`",
        f"- **Risk:** `{result.risk}`",
        f"- **Summary:** {result.summary}",
    ]
    if not result.findings:
        lines.extend(["", "No deterministic issues were found."])
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(["", "### Findings", ""])
    lines.append("| Severity | Code | Location | Recommendation |")
    lines.append("| --- | --- | --- | --- |")
    for finding in result.findings:
        location = finding.path or "-"
        recommendation = finding.recommendation.replace("\n", " ")
        lines.append(f"| `{finding.severity}` | `{finding.code}` | `{location}` | {recommendation} |")

    lines.extend(["", "### Details", ""])
    for finding in result.findings:
        location = f" at `{finding.path}`" if finding.path else ""
        lines.extend(
            [
                f"#### `{finding.code}`{location}",
                "",
                f"**Severity:** `{finding.severity}`",
                "",
                finding.detail,
                "",
                f"**Recommendation:** {finding.recommendation}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def should_fail_review(result: ReviewResult, *, fail_on: str = "none", fail_on_codes: list[str] | None = None) -> bool:
    """Return whether review should fail CI for severity or finding-code policies."""

    code_set = set(fail_on_codes or [])
    if code_set and any(finding.code in code_set for finding in result.findings):
        return True
    if fail_on == "critical":
        return result.risk == "critical"
    if fail_on == "high":
        return result.risk in {"high", "critical"}
    return False
