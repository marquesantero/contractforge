from contractforge_core import adapter_scheduling, project_schedule_intent, quartz_cron_expression


def test_project_schedule_intent_uses_top_level_schedule() -> None:
    project = {
        "schedule": {
            "cron": "0 6 * * *",
            "timezone": "America/Sao_Paulo",
            "enabled": False,
            "max_concurrent_runs": 1,
            "queue": True,
        }
    }

    intent = project_schedule_intent(project)

    assert intent is not None
    assert intent.cron == "0 6 * * *"
    assert intent.timezone == "America/Sao_Paulo"
    assert intent.enabled is False
    assert intent.max_concurrent_runs == 1
    assert intent.queue is True


def test_adapter_scheduling_merges_common_schedule_with_adapter_overrides() -> None:
    project = {
        "schedule": {
            "cron": "0 6 * * *",
            "timezone": "America/Sao_Paulo",
            "enabled": False,
            "max_concurrent_runs": 1,
            "queue": True,
            "adapters": {
                "aws": {"state": "DISABLED", "flexible_time_window": "OFF"},
                "databricks": {"pause_status": "PAUSED", "tasks": {"bronze": {"task_key": "bronze"}}},
            },
        }
    }

    assert adapter_scheduling(project, "aws") == {
        "max_concurrent_runs": 1,
        "queue": True,
        "schedule": {
            "cron": "0 6 * * *",
            "timezone": "America/Sao_Paulo",
            "enabled": False,
            "state": "DISABLED",
            "flexible_time_window": "OFF",
        },
    }
    assert adapter_scheduling(project, "databricks")["tasks"]["bronze"]["task_key"] == "bronze"


def test_quartz_cron_expression_from_standard_project_cron() -> None:
    assert quartz_cron_expression("0 6 * * *") == "0 0 6 * * ?"
