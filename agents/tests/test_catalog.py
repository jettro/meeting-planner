"""Tests for the catalog YAML that defines the agent team.

The point of these tests is the isolation guarantee from `design_akgents.md`:
each specialist may reach its own service's MCP server and no other. That is a
property of the YAML, so it is worth asserting against the YAML rather than
trusting a review of it.
"""

import os
from pathlib import Path

import pytest
from akgentic.catalog import Catalog, YamlEntryRepository, set_allowed_prefixes
from akgentic.catalog.env import resolve_env_vars
from akgentic.core import AgentCard
from akgentic.tool.mcp import MCPHTTPConnectionConfig, MCPTool
from meeting_agents.bootstrap import MODEL_TYPE_PREFIXES
from meeting_agents.memory import MemoryTool
from meeting_agents.settings import Settings

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "catalog"
NAMESPACE = "meeting-planner"

# Which single MCP server each agent is allowed to reach, by tool_prefix.
EXPECTED_SERVER = {
    "scheduler": ("meeting", "MEETING"),
    "facility_manager": ("facility", "LOCATION"),
    "catering": ("catering", "NOMNOM"),
}

# Each specialist is its own class, because each handles different assignments.
EXPECTED_CLASS = {
    "scheduler": "meeting_agents.specialists.Scheduler",
    "facility_manager": "meeting_agents.specialists.FacilityManager",
    "catering": "meeting_agents.specialists.Catering",
}


@pytest.fixture
def catalog() -> Catalog:
    # The facility manager's memory card is one of ours, as `build_catalog` allows.
    set_allowed_prefixes(MODEL_TYPE_PREFIXES)
    return Catalog(repository=YamlEntryRepository(root=CATALOG_ROOT))


def load_agent(catalog: Catalog, entry_id: str) -> AgentCard:
    card = catalog.resolve_by_id(namespace=NAMESPACE, id=entry_id)
    assert isinstance(card, AgentCard)
    return card


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_agent_entry_resolves(catalog: Catalog, entry_id: str):
    card = load_agent(catalog, entry_id)
    assert card.agent_class == EXPECTED_CLASS[entry_id]
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

    servers = [tool for tool in card.config.tools if isinstance(tool, MCPTool)]
    assert len(servers) == 1, "an agent must not reach a second service"
    tool = card.config.tools[0]
    assert isinstance(tool, MCPTool), "the ref must rehydrate as a real MCPTool"
    # Anything else is memory, which gives the model no tool at all (design_memory.md M19).
    others = card.config.tools[1:]
    assert all(isinstance(other, MemoryTool) and other.get_tools() == [] for other in others)
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


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_every_prompt_renders(catalog: Catalog, entry_id: str):
    """`Prompt.render()` is `template.format(**params)`, so a literal `{` in the
    text is read as a format field and raises. That happens in `on_start`, where
    the traceback is easy to miss and the agent silently loses its backstory -
    found exactly that way in a live run. Rendering here keeps it visible."""
    prompt = load_agent(catalog, entry_id).config.prompt
    assert prompt is not None
    assert prompt.render().strip()


@pytest.mark.parametrize("entry_id", sorted(EXPECTED_SERVER))
def test_specialists_allow_a_slow_model_call(catalog: Catalog, entry_id: str):
    """akgentic's default is 120s and its retry policy deliberately does not
    retry a timeout, so one slow reasoning call ends the whole plan. It happened
    in a real run; see design_akgents.md section 7.6."""
    card = load_agent(catalog, entry_id)
    assert card.config.runtime_cfg.http_client_config.timeout >= 240.0
