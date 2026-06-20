"""Public packages must expose __version__ that matches their distribution metadata."""

from __future__ import annotations

import re
from importlib.metadata import version as _pkg_version

import contractforge_core
import contractforge_ai
import contractforge_aws
import contractforge_databricks
import contractforge_fabric
import contractforge_gcp
import contractforge_snowflake

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([+-].+)?$")


def test_core_exposes_version() -> None:
    assert hasattr(contractforge_core, "__version__")
    assert VERSION_RE.match(contractforge_core.__version__)
    assert contractforge_core.__version__ == _pkg_version("contractforge-core")


def test_databricks_exposes_version() -> None:
    assert hasattr(contractforge_databricks, "__version__")
    assert VERSION_RE.match(contractforge_databricks.__version__)
    assert contractforge_databricks.__version__ == _pkg_version("contractforge-databricks")


def test_aws_exposes_version() -> None:
    assert hasattr(contractforge_aws, "__version__")
    assert VERSION_RE.match(contractforge_aws.__version__)
    assert contractforge_aws.__version__ == _pkg_version("contractforge-aws")


def test_snowflake_exposes_version() -> None:
    assert hasattr(contractforge_snowflake, "__version__")
    assert VERSION_RE.match(contractforge_snowflake.__version__)
    assert contractforge_snowflake.__version__ == _pkg_version("contractforge-snowflake")


def test_fabric_exposes_version() -> None:
    assert hasattr(contractforge_fabric, "__version__")
    assert VERSION_RE.match(contractforge_fabric.__version__)
    assert contractforge_fabric.__version__ == _pkg_version("contractforge-fabric")


def test_gcp_exposes_version() -> None:
    assert hasattr(contractforge_gcp, "__version__")
    assert VERSION_RE.match(contractforge_gcp.__version__)
    assert contractforge_gcp.__version__ == _pkg_version("contractforge-gcp")


def test_ai_exposes_version() -> None:
    assert hasattr(contractforge_ai, "__version__")
    assert VERSION_RE.match(contractforge_ai.__version__)
    assert contractforge_ai.__version__ == _pkg_version("contractforge-ai")
