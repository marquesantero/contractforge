from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_core_pyproject_packages_only_core_package() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-core"' in pyproject
    assert 'packages = ["src/contractforge_core"]' in pyproject
    assert 'contractforge = "contractforge_core.cli:main"' in pyproject
    assert '"adapters/databricks/src"' in pyproject
    assert '"adapters/snowflake/src"' in pyproject
    assert 'packages = ["src/contractforge_core", "src/contractforge_databricks"]' not in pyproject
    assert 'contractforge-databricks = "contractforge_databricks.cli:main"' not in pyproject


def test_databricks_pyproject_publishes_adapter_wheel() -> None:
    pyproject = (ROOT / "adapters" / "databricks" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-databricks"' in pyproject
    assert '"contractforge-core>=0.2,<0.3"' in pyproject
    assert 'contractforge-databricks = "contractforge_databricks.cli:main"' in pyproject
    assert 'packages = ["src/contractforge_databricks"]' in pyproject
    assert 'packages = ["src/contractforge_core"]' not in pyproject


def test_databricks_package_lives_under_adapter_project() -> None:
    assert not (ROOT / "src" / "contractforge_databricks").exists()
    assert (ROOT / "adapters" / "databricks" / "src" / "contractforge_databricks" / "__init__.py").exists()


def test_aws_pyproject_publishes_adapter_wheel() -> None:
    pyproject = (ROOT / "adapters" / "aws" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-aws"' in pyproject
    assert '"contractforge-core>=0.2,<0.3"' in pyproject
    assert 'runtime = ["boto3>=1.34", "botocore[crt]>=1.34"]' in pyproject
    assert 'contractforge-aws = "contractforge_aws.cli:main"' in pyproject
    assert 'packages = ["src/contractforge_aws"]' in pyproject
    assert 'packages = ["src/contractforge_core"]' not in pyproject


def test_aws_package_lives_under_adapter_project() -> None:
    assert not (ROOT / "src" / "contractforge_aws").exists()
    assert (ROOT / "adapters" / "aws" / "src" / "contractforge_aws" / "__init__.py").exists()


def test_snowflake_pyproject_publishes_adapter_wheel() -> None:
    pyproject = (ROOT / "adapters" / "snowflake" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-snowflake"' in pyproject
    assert '"contractforge-core>=0.2,<0.3"' in pyproject
    assert 'runtime = ["snowflake-connector-python>=3"]' in pyproject
    assert 'snowpark = ["snowflake-snowpark-python>=1"]' in pyproject
    assert 'contractforge-snowflake = "contractforge_snowflake.cli:main"' in pyproject
    assert 'packages = ["src/contractforge_snowflake"]' in pyproject
    assert 'packages = ["src/contractforge_core"]' not in pyproject


def test_snowflake_package_lives_under_adapter_project() -> None:
    assert not (ROOT / "src" / "contractforge_snowflake").exists()
    assert (ROOT / "adapters" / "snowflake" / "src" / "contractforge_snowflake" / "__init__.py").exists()


def test_fabric_pyproject_publishes_adapter_wheel() -> None:
    pyproject = (ROOT / "adapters" / "fabric" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-fabric"' in pyproject
    assert '"contractforge-core>=0.2,<0.3"' in pyproject
    assert 'contractforge-fabric = "contractforge_fabric.cli:main"' in pyproject
    assert 'packages = ["src/contractforge_fabric"]' in pyproject
    assert 'packages = ["src/contractforge_core"]' not in pyproject


def test_fabric_package_lives_under_adapter_project() -> None:
    assert not (ROOT / "src" / "contractforge_fabric").exists()
    assert (ROOT / "adapters" / "fabric" / "src" / "contractforge_fabric" / "__init__.py").exists()


def test_gcp_pyproject_publishes_adapter_wheel() -> None:
    pyproject = (ROOT / "adapters" / "gcp" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-gcp"' in pyproject
    assert '"contractforge-core>=0.2,<0.3"' in pyproject
    assert 'contractforge-gcp = "contractforge_gcp.cli:main"' in pyproject
    assert 'packages = ["src/contractforge_gcp"]' in pyproject
    assert 'packages = ["src/contractforge_core"]' not in pyproject


def test_gcp_package_lives_under_adapter_project() -> None:
    assert not (ROOT / "src" / "contractforge_gcp").exists()
    assert (ROOT / "adapters" / "gcp" / "src" / "contractforge_gcp" / "__init__.py").exists()


def test_ai_pyproject_publishes_ai_wheel() -> None:
    pyproject = (ROOT / "ai" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "contractforge-ai"' in pyproject
    assert '"contractforge-core>=0.2,<0.3"' in pyproject
    assert 'contractforge-ai = "contractforge_ai.cli:main"' in pyproject
    assert 'where = ["src"]' in pyproject


def test_ai_package_lives_under_ai_project() -> None:
    assert not (ROOT / "src" / "contractforge_ai").exists()
    assert (ROOT / "ai" / "src" / "contractforge_ai" / "__init__.py").exists()


def test_publication_packaging_spec_defines_independent_wheels() -> None:
    spec = (ROOT / "docs" / "specs" / "publication-packaging.md").read_text(encoding="utf-8")

    required_phrases = [
        "ContractForge Core, every platform adapter and the AI companion are published as separate Python distributions.",
        "`contractforge-core`",
        "`contractforge-databricks`",
        "`contractforge-aws`",
        "`contractforge-fabric`",
        "`contractforge-snowflake`",
        "`contractforge-gcp`",
        "`contractforge-ai`",
        "`contractforge_core`",
        "`contractforge_databricks`",
        "`contractforge_aws`",
        "`contractforge_fabric`",
        "`contractforge_snowflake`",
        "`contractforge_gcp`",
        "`contractforge_ai`",
        "platform adapter wheel -> contractforge-core wheel",
        "contractforge-core wheel -> no platform adapter wheel",
        "The core wheel must not include:",
        "the `contractforge-databricks` console script",
        "each adapter declares `contractforge-core` as a dependency",
        "adapters/databricks/pyproject.toml",
        "adapters/aws/pyproject.toml",
        "adapters/fabric/pyproject.toml",
        "adapters/snowflake/pyproject.toml",
        "adapters/gcp/pyproject.toml",
        "ai/pyproject.toml",
        "cd adapters/databricks",
        "cd adapters/aws",
        "cd adapters/fabric",
        "cd adapters/snowflake",
        "cd adapters/gcp",
        "cd ai",
    ]

    for phrase in required_phrases:
        assert phrase in spec


def test_readme_links_publication_packaging_spec() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/specs/publication-packaging.md" in readme
    assert "The core wheel owns only `contractforge_core`" in readme


def test_release_workflow_publishes_runtime_assets() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "Create ZIP aliases for wheel-only runtimes" in workflow
    assert 'cp "$wheel" "dist/${base}.zip"' in workflow
    assert "Upload PyPI distributions" in workflow
    assert "Upload GitHub Release assets" in workflow
    assert "gh release upload" in workflow
    assert "-pypi-dist" in workflow
    assert "-release-assets" in workflow
