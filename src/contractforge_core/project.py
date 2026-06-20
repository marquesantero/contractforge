"""Platform-neutral project metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ProjectScheduleIntent:
    """Portable project schedule intent.

    Adapters render this into their native scheduler syntax. The core owns the
    public schedule vocabulary, not the platform-specific trigger artifact.
    """

    cron: str
    timezone: str = "UTC"
    enabled: bool = True
    max_concurrent_runs: int | None = None
    queue: bool | None = None


@dataclass(frozen=True)
class StandardCron:
    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str


def adapter_scheduling(project: Mapping[str, Any], adapter: str) -> dict[str, Any]:
    """Return portable project schedule settings plus adapter-specific overrides."""

    root = mapping(project.get("schedule"))
    adapters = mapping(root.get("adapters"))
    common = {str(key): value for key, value in root.items() if key != "adapters"}
    adapter_block = dict(mapping(adapters.get(adapter)))
    schedule_keys = ("cron", "timezone", "enabled", "state", "pause_status", "paused", "expression", "flexible_time_window")
    adapter_schedule = {key: adapter_block.pop(key) for key in tuple(adapter_block) if key in schedule_keys}
    schedule = {key: common[key] for key in ("cron", "timezone", "enabled") if key in common}
    return {
        **{key: common[key] for key in ("max_concurrent_runs", "queue", "tags") if key in common},
        **adapter_block,
        **({"schedule": {**schedule, **adapter_schedule}} if schedule or adapter_schedule else {}),
    }


def project_schedule_intent(project: Mapping[str, Any]) -> ProjectScheduleIntent | None:
    """Return the neutral project schedule intent, when declared."""

    schedule = mapping(project.get("schedule"))
    cron = text(schedule.get("cron"))
    if not cron:
        return None
    return ProjectScheduleIntent(
        cron=cron,
        timezone=text(schedule.get("timezone")) or "UTC",
        enabled=bool(schedule.get("enabled", True)),
        max_concurrent_runs=_optional_int(schedule.get("max_concurrent_runs")),
        queue=_optional_bool(schedule.get("queue")),
    )


def parse_standard_cron(value: str) -> StandardCron:
    """Parse the ContractForge public five-field cron format."""

    fields = value.split()
    if len(fields) != 5:
        raise ValueError("schedule.cron must use standard five-field cron syntax")
    return StandardCron(*fields)


def quartz_cron_expression(value: str) -> str:
    """Render five-field project cron as a Quartz-compatible expression."""

    cron = parse_standard_cron(value)
    return f"0 {cron.minute} {cron.hour} {cron.day_of_month} {cron.month} {_quartz_day_of_week(cron)}"


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None and str(value).strip() else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _quartz_day_of_week(cron: StandardCron) -> str:
    if cron.day_of_month != "*" and cron.day_of_week != "*":
        raise ValueError("schedule.cron cannot set both day-of-month and day-of-week")
    return "?" if cron.day_of_week == "*" else cron.day_of_week
