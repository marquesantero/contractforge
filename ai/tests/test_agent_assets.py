from contractforge_ai.onboarding import AgentInstructionRequest, generate_agent_instruction_plan


def test_generate_generic_agent_assets_include_guardrails():
    plan = generate_agent_instruction_plan(
        AgentInstructionRequest(
            project_name="Orders Platform",
            contract_root="contracts/orders",
            validation_commands=["contractforge-ai review contracts/orders/silver.yaml --fail-on high"],
        )
    )

    artifacts = {artifact.path: artifact.content for artifact in plan.artifacts}

    assert plan.target == "agent-instructions-generic"
    assert "AGENT_INSTRUCTIONS.md" in artifacts
    assert "AGENT_CHECKLIST.md" in artifacts
    assert "Do not resolve, print or invent secret values." in artifacts["AGENT_INSTRUCTIONS.md"]
    assert "Preserve the core/adapter boundary" in artifacts["AGENT_INSTRUCTIONS.md"]
    assert "contracts/orders" in artifacts["AGENT_INSTRUCTIONS.md"]
    assert "contractforge-ai review contracts/orders/silver.yaml --fail-on high" in artifacts["AGENT_CHECKLIST.md"]
    assert "Adapter-specific extensions are isolated" in artifacts["AGENT_CHECKLIST.md"]
    assert any(decision.path == "allow_production_mutation" for decision in plan.report.decisions_required)


def test_generate_all_agent_assets_include_ide_specific_paths():
    plan = generate_agent_instruction_plan(
        AgentInstructionRequest(
            target="all",
            project_name="Lakehouse",
        )
    )

    paths = {artifact.path for artifact in plan.artifacts}

    assert "AGENT_INSTRUCTIONS.md" in paths
    assert "AGENT_CHECKLIST.md" in paths
    assert ".codex/contractforge-instructions.md" in paths
    assert "CLAUDE.md" in paths
    assert ".cursor/rules/contractforge.mdc" in paths
    assert ".github/copilot-instructions.md" in paths

    artifacts = {artifact.path: artifact.content for artifact in plan.artifacts}
    assert "contractforge-ai validate-project-structure . --format markdown" in artifacts["AGENT_CHECKLIST.md"]
    assert "Preserve ContractForge core/adapter boundaries." in artifacts[".codex/contractforge-instructions.md"]


def test_generate_agent_assets_respects_output_prefix():
    plan = generate_agent_instruction_plan(
        AgentInstructionRequest(
            target="cursor",
            output_prefix="docs/agent",
        )
    )

    paths = {artifact.path for artifact in plan.artifacts}

    assert "docs/agent/AGENT_INSTRUCTIONS.md" in paths
    assert "docs/agent/.cursor/rules/contractforge.mdc" in paths
