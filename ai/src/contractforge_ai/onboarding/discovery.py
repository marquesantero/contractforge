"""Environment discovery for ContractForge AI onboarding."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable

CommandLookup = Callable[[str], str | None]
PackageLookup = Callable[[str], bool]

PACKAGE_GROUPS = {
    "contractforge": (
        "contractforge_core",
        "contractforge_ai",
    ),
    "adapters": (
        "contractforge_databricks",
        "contractforge_aws",
    ),
    "parsing": ("yaml",),
    "provider_clients": (
        "openai",
        "boto3",
    ),
    "platform_sdks": ("databricks.sdk",),
}

PROVIDER_ENV_VARS = (
    "CONTRACTFORGE_AI_PROVIDER",
    "CONTRACTFORGE_AI_MODEL",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "DATABRICKS_HOST",
    "DATABRICKS_TOKEN",
    "DATABRICKS_SERVING_ENDPOINT",
    "DATABRICKS_MODEL_SERVING_ENDPOINT",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
)


@dataclass(frozen=True)
class EnvironmentReport:
    """Redacted environment discovery report."""

    python_version: str
    platform: str
    packages: dict[str, bool]
    commands: dict[str, bool]
    package_groups: dict[str, dict[str, bool]] = field(default_factory=dict)
    provider_environment: dict[str, Any] = field(default_factory=dict)
    databricks: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        package_groups = self.package_groups or group_packages(self.packages)
        return {
            "python_version": self.python_version,
            "platform": self.platform,
            "packages": self.packages,
            "package_groups": package_groups,
            "commands": self.commands,
            "provider_environment": self.provider_environment,
            "databricks": self.databricks,
            "warnings": self.warnings,
        }


def discover_environment(
    *,
    environ: dict[str, str] | None = None,
    command_lookup: CommandLookup | None = None,
    package_lookup: PackageLookup | None = None,
) -> EnvironmentReport:
    """Discover local environment capabilities without exposing secret values."""

    env = dict(os.environ if environ is None else environ)
    command_exists = command_lookup or shutil.which
    package_exists = package_lookup or _package_available

    packages = _discover_packages(package_exists)
    package_groups = group_packages(packages)
    commands = {
        "databricks": command_exists("databricks") is not None,
        "git": command_exists("git") is not None,
        "dbt": command_exists("dbt") is not None,
    }
    provider_environment = {
        key: _env_presence(env, key)
        for key in PROVIDER_ENV_VARS
        if key in env
    }
    databricks = {
        "in_notebook": _looks_like_databricks_notebook(env),
        "host_configured": bool(env.get("DATABRICKS_HOST")),
        "token_configured": bool(env.get("DATABRICKS_TOKEN")),
        "cli_available": commands["databricks"],
        "sdk_available": packages["databricks.sdk"],
    }

    warnings = _warnings(packages=packages, commands=commands, provider_environment=provider_environment, databricks=databricks)

    return EnvironmentReport(
        python_version=platform.python_version(),
        platform=platform.platform(),
        packages=packages,
        package_groups=package_groups,
        commands=commands,
        provider_environment=provider_environment,
        databricks=databricks,
        warnings=warnings,
    )


def _package_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


def _discover_packages(package_exists: PackageLookup) -> dict[str, bool]:
    names = []
    for group in PACKAGE_GROUPS.values():
        names.extend(group)
    return {name: package_exists(name) for name in dict.fromkeys(names)}


def group_packages(packages: dict[str, bool]) -> dict[str, dict[str, bool]]:
    """Group package availability by setup concern while preserving optional adapters."""

    grouped = {
        group_name: {name: packages.get(name, False) for name in names}
        for group_name, names in PACKAGE_GROUPS.items()
    }
    known = {name for names in PACKAGE_GROUPS.values() for name in names}
    other = {name: available for name, available in packages.items() if name not in known}
    if other:
        grouped["other"] = other
    return grouped


def _env_presence(env: dict[str, str], key: str) -> dict[str, Any]:
    value = env.get(key)
    return {
        "configured": value is not None and value != "",
        "value": "[REDACTED]" if _looks_secret_key(key) and value else value,
    }


def _looks_secret_key(key: str) -> bool:
    normalized = key.lower()
    return any(marker in normalized for marker in ("key", "token", "secret", "password"))


def _looks_like_databricks_notebook(env: dict[str, str]) -> bool:
    return any(key.startswith("DATABRICKS_RUNTIME_") for key in env) or "DATABRICKS_RUNTIME_VERSION" in env


def _warnings(
    *,
    packages: dict[str, bool],
    commands: dict[str, bool],
    provider_environment: dict[str, Any],
    databricks: dict[str, Any],
) -> list[str]:
    result: list[str] = []
    if not packages["contractforge_core"]:
        result.append("contractforge-core is not installed; generated contract validation will be skipped.")
    if not packages["contractforge_ai"]:
        result.append("contractforge-ai is not importable in this environment; CLI entry points may be using a different Python environment.")
    if provider_environment and not provider_environment.get("CONTRACTFORGE_AI_PROVIDER", {}).get("configured", False):
        result.append("Provider environment variables are partially configured but CONTRACTFORGE_AI_PROVIDER is missing.")
    if databricks["host_configured"] and not commands["databricks"]:
        result.append("DATABRICKS_HOST is configured but the Databricks CLI was not found.")
    if databricks["in_notebook"] and not packages["databricks.sdk"]:
        result.append("Databricks runtime is detected but databricks.sdk is not importable.")
    return result
