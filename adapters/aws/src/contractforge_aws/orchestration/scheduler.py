"""Render EventBridge Scheduler payloads for AWS project orchestration."""

from __future__ import annotations

from typing import Any, Mapping

from contractforge_core.project import adapter_scheduling, parse_standard_cron


def render_eventbridge_scheduler_payload(
    project: Mapping[str, Any],
    *,
    state_machine_arn: str | None = None,
    role_arn: str | None = None,
) -> dict[str, Any] | None:
    """Render an optional Scheduler payload from neutral project scheduling."""

    schedule = _aws_schedule(project)
    if not schedule:
        return None
    payload = {
        "Name": schedule.get("name") or _schedule_name(project),
        "ScheduleExpression": _schedule_expression(schedule),
        "ScheduleExpressionTimezone": _schedule_timezone(schedule),
        "State": schedule.get("state") or _schedule_state(schedule),
        "FlexibleTimeWindow": {"Mode": str(schedule.get("flexible_time_window") or "OFF")},
        "Target": {
            "Arn": state_machine_arn or schedule.get("state_machine_arn") or "${STATE_MACHINE_ARN}",
            "RoleArn": role_arn or schedule.get("role_arn") or "${EVENTBRIDGE_SCHEDULER_ROLE_ARN}",
        },
    }
    group_name = schedule.get("group_name") or schedule.get("group")
    return {**payload, **({"GroupName": group_name} if group_name else {})}


def _aws_schedule(project: Mapping[str, Any]) -> Mapping[str, Any]:
    schedule = adapter_scheduling(project, "aws").get("schedule")
    return schedule if isinstance(schedule, Mapping) else {}


def _schedule_name(project: Mapping[str, Any]) -> str:
    name = str(project.get("name") or "contractforge_project").strip().replace("_", "-")
    return f"{name}-schedule"


def _schedule_expression(schedule: Mapping[str, Any]) -> str:
    expression = _text(schedule.get("expression"))
    cron = _text(schedule.get("cron"))
    if expression:
        return _normalize_expression(expression)
    if cron:
        return _cron_expression(cron)
    raise ValueError("schedule.cron or schedule.adapters.aws.expression is required")


def _schedule_timezone(schedule: Mapping[str, Any]) -> str:
    return _text(schedule.get("timezone") or schedule.get("timezone_id")) or "UTC"


def _normalize_expression(expression: str) -> str:
    if expression.startswith(("cron(", "rate(", "at(")):
        return expression
    return _cron_expression(expression)


def _cron_expression(value: str) -> str:
    fields = value.split()
    if len(fields) == 5:
        cron = parse_standard_cron(value)
        return f"cron({cron.minute} {cron.hour} {_aws_day_of_month(cron)} {cron.month} {_aws_day_of_week(cron)} *)"
    if len(fields) == 6:
        return f"cron({' '.join(fields)})"
    raise ValueError("schedule.cron must use 5 standard fields or schedule.adapters.aws.expression must use native AWS syntax")


def _aws_day_of_month(cron) -> str:
    _validate_day_fields(cron.day_of_month, cron.day_of_week)
    return "?" if cron.day_of_month == "*" and cron.day_of_week != "*" else cron.day_of_month


def _aws_day_of_week(cron) -> str:
    _validate_day_fields(cron.day_of_month, cron.day_of_week)
    return "?" if cron.day_of_week == "*" else cron.day_of_week


def _validate_day_fields(day_of_month: str, day_of_week: str) -> None:
    if day_of_month != "*" and day_of_week != "*":
        raise ValueError("AWS Scheduler cron cannot set both day-of-month and day-of-week; use '*' for one of them")


def _schedule_state(schedule: Mapping[str, Any]) -> str:
    return "DISABLED" if schedule.get("enabled") is False else "ENABLED"


def _text(value: Any) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    return value
