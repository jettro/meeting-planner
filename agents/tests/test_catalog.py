"""Tests for the catalog YAML that defines the agent team.

The point of these tests is the isolation guarantee from `design_akgents.md`:
each specialist may reach its own service's MCP server and no other. That is a
property of the YAML, so it is worth asserting against the YAML rather than
trusting a review of it.
"""

import os
from pathlib import Path

import pytest
from akgentic.catalog import Catalog, YamlEntryRepository
from akgentic.catalog.env import resolve_env_vars
from akgentic.core import AgentCard
from akgentic.tool.mcp import MCPHTTPConnectionConfig, MCPTool
from meeting_agents.settings import Settings

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "catalog"
NAMESPACE = "meeting-planner"

# Which single MCP server each agent is allowed to reach, by tool_prefix.
EXPECTED_SERVER = {
    "scheduler": ("meeting", "MEETING"),
    "facility_manager": ("facility", "LOCATION"),
    "catering": ("catering", "NOMNOM"),
}


@pytest.fixture
def catalog() -> Catalog:
    return Catalog(repository=YamlEntryRepository(root=CATALOG_ROOT))


def load_agent(catalog: Catalog, entry_id: str) -> AgentCard:
    card = catalog.resolve_by_id(namespace=NAMESPACE, id=entry_id)
    assert isinstance(card, AgentCard)
    return card


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_agent_entry_resolves(catalog: Catalog, entry_id: str):
    card = load_agent(catalog, entry_id)
    assert card.agent_class == "akgentic.agent.BaseAgent"
    assert card.config.name.startswith("@")
    assert card.role
    # The prompt __ref__ must have been replaced by the real prompt body.
    assert "__ref__" not in card.config.prompt.template
    assert len(card.config.prompt.template) > 200
    assert card.config.model_cfg is not None
    assert card.config.model_cfg.model == "gpt-6-luna"


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_each_agent_gets_exactly_one_mcp_server(catalog: Catalog, entry_id: str):
    """The isolation guarantee: one agent, one server, no extras."""
    card = load_agent(catalog, entry_id)
    prefix, _ = EXPECTED_SERVER[entry_id]

    assert len(card.config.tools) == 1, "an agent must not reach a second service"
    tool = card.config.tools[0]
    assert isinstance(tool, MCPTool), "the ref must rehydrate as a real MCPTool"
    assert isinstance(tool.connection, MCPHTTPConnectionConfig)
    assert tool.connection.tool_prefix == prefix


def test_no_two_agents_share_a_server(catalog: Catalog):
    urls = []
    for entry_id in EXPECTED_SERVER:
        tool = load_agent(catalog, entry_id).config.tools[0]
        urls.append(tool.connection.url)  # type: ignore[union-attr]
    assert len(set(urls)) == len(urls)


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_secrets_are_placeholders_not_values(catalog: Catalog, entry_id: str):
    """The catalog is committed to git, so it must hold ${VAR}, never a real key."""
    tool = load_agent(catalog, entry_id).config.tools[0]
    connection = tool.connection  # type: ignore[union-attr]
    _, env_prefix = EXPECTED_SERVER[entry_id]
    assert connection.bearer_token == "${" + env_prefix + "_MCP_API_KEY}"
    assert connection.url == "${" + env_prefix + "_MCP_URL}"


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_placeholders_resolve_against_settings(catalog: Catalog, entry_id: str, monkeypatch):
    """What the catalog stores must be resolvable by what Settings provides."""
    for key, value in Settings.from_env().as_catalog_env().items():
        monkeypatch.setenv(key, value)

    connection = load_agent(catalog, entry_id).config.tools[0].connection  # type: ignore[union-attr]
    assert resolve_env_vars(connection.url).endswith("/mcp")
    assert "${" not in resolve_env_vars(connection.bearer_token)


def test_resolve_env_vars_fails_loudly_when_unset(monkeypatch):
    monkeypatch.delenv("MEETING_MCP_API_KEY", raising=False)
    with pytest.raises(OSError):
        resolve_env_vars("${MEETING_MCP_API_KEY}")


def test_catalog_env_covers_every_placeholder_in_the_yaml():
    """No placeholder may exist that Settings cannot supply."""
    import re

    placeholders: set[str] = set()
    for path in CATALOG_ROOT.rglob("*.yaml"):
        placeholders |= set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", path.read_text()))

    assert placeholders, "expected the catalog to reference env vars"
    assert placeholders <= set(Settings.from_env().as_catalog_env()) | set(os.environ)
