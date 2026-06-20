"""Provider-neutral validation for model structured outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from contractforge_ai.context.redaction import redact_secrets
from contractforge_ai.evaluation.prompts import get_prompt_template

StructuredOutputStatus = Literal["PASS", "FAIL"]


@dataclass(frozen=True)
class StructuredOutputFinding:
    """One structured-output validation finding."""

    code: str
    message: str
    path: str = "$"
    severity: Literal["medium", "high", "critical"] = "high"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class StructuredOutputValidation:
    """Structured-output validation result."""

    status: StructuredOutputStatus
    data: dict[str, Any] | None = None
    findings: list[StructuredOutputFinding] = field(default_factory=list)
    deterministic_fallback: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "data": self.data,
            "findings": [finding.to_dict() for finding in self.findings],
            "deterministic_fallback": self.deterministic_fallback,
        }


def validate_model_output(
    raw_output: str | dict[str, Any],
    *,
    prompt: str,
    deterministic_fallback: dict[str, Any] | None = None,
) -> StructuredOutputValidation:
    """Validate model output against a registered prompt output schema."""

    template = get_prompt_template(prompt)
    data, parse_finding = _parse_output(raw_output)
    if parse_finding is not None:
        return StructuredOutputValidation(
            status="FAIL",
            findings=[parse_finding],
            deterministic_fallback=redact_secrets(deterministic_fallback),
        )

    findings = _validate_schema(data, template.output_schema)
    redacted_data = redact_secrets(data)
    return StructuredOutputValidation(
        status="FAIL" if findings else "PASS",
        data=redacted_data if not findings else None,
        findings=findings,
        deterministic_fallback=redact_secrets(deterministic_fallback) if findings else None,
    )


def _parse_output(raw_output: str | dict[str, Any]) -> tuple[dict[str, Any], StructuredOutputFinding | None]:
    if isinstance(raw_output, dict):
        return raw_output, None
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return {}, StructuredOutputFinding(
            code="structured_output.invalid_json",
            message=f"Model output is not valid JSON: {exc.msg}.",
            severity="critical",
        )
    if not isinstance(data, dict):
        return {}, StructuredOutputFinding(
            code="structured_output.not_object",
            message="Model output must be a JSON object.",
            severity="critical",
        )
    return data, None


def _validate_schema(data: dict[str, Any], schema: dict[str, Any], *, path: str = "$") -> list[StructuredOutputFinding]:
    findings: list[StructuredOutputFinding] = []
    schema_type = schema.get("type")
    if schema_type == "object":
        findings.extend(_validate_object(data, schema, path=path))
    elif not _matches_type(data, schema_type):
        findings.append(_type_finding(path, schema_type, data))
    return findings


def _validate_object(data: Any, schema: dict[str, Any], *, path: str) -> list[StructuredOutputFinding]:
    if not isinstance(data, dict):
        return [_type_finding(path, "object", data)]

    findings: list[StructuredOutputFinding] = []
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    for key in required:
        if key not in data:
            findings.append(
                StructuredOutputFinding(
                    code="structured_output.required_missing",
                    message=f"Required property {key!r} is missing.",
                    path=f"{path}.{key}",
                    severity="critical",
                )
            )
    if schema.get("additionalProperties") is False:
        for key in data:
            if key not in properties:
                findings.append(
                    StructuredOutputFinding(
                        code="structured_output.additional_property",
                        message=f"Additional property {key!r} is not allowed.",
                        path=f"{path}.{key}",
                        severity="high",
                    )
                )
    for key, property_schema in properties.items():
        if key in data and isinstance(property_schema, dict):
            findings.extend(_validate_property(data[key], property_schema, path=f"{path}.{key}"))
    return findings


def _validate_property(value: Any, schema: dict[str, Any], *, path: str) -> list[StructuredOutputFinding]:
    findings: list[StructuredOutputFinding] = []
    if "const" in schema and value != schema["const"]:
        findings.append(
            StructuredOutputFinding(
                code="structured_output.const_mismatch",
                message=f"Expected constant value {schema['const']!r}.",
                path=path,
                severity="critical",
            )
        )
    schema_type = schema.get("type")
    if schema_type and not _matches_type(value, schema_type):
        findings.append(_type_finding(path, schema_type, value))
        return findings
    if schema_type == "array":
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        for index, item in enumerate(value):
            findings.extend(_validate_property(item, item_schema, path=f"{path}[{index}]"))
    if schema_type == "object":
        findings.extend(_validate_object(value, schema, path=path))
    if schema_type == "number":
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < minimum:
            findings.append(
                StructuredOutputFinding(
                    code="structured_output.number_below_minimum",
                    message=f"Value must be >= {minimum}.",
                    path=path,
                    severity="high",
                )
            )
        if maximum is not None and value > maximum:
            findings.append(
                StructuredOutputFinding(
                    code="structured_output.number_above_maximum",
                    message=f"Value must be <= {maximum}.",
                    path=path,
                    severity="high",
                )
            )
    return findings


def _matches_type(value: Any, schema_type: Any) -> bool:
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type is None:
        return True
    return True


def _type_finding(path: str, expected: Any, value: Any) -> StructuredOutputFinding:
    return StructuredOutputFinding(
        code="structured_output.type_mismatch",
        message=f"Expected type {expected!r}, got {type(value).__name__}.",
        path=path,
        severity="critical",
    )
