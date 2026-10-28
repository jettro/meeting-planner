"""The catalog swap: does the server's team get real URLs, or `${VAR}`?

This is the one piece of the server that could fail silently in the most
expensive way. An unresolved placeholder is a perfectly valid string, so the
team builds, the agents start, and the first tool call goes to a host named
`${MEETING_MCP_URL}` several turns into a saga.
"""

from __future__ import annotations

import pytest
from akgentic.catalog import YamlEntryRepository
from akgentic.infra import wire_community
from meeting_agents.bootstrap import apply_env
from meeting_agents.settings import Settings as AgentSettings
from meeting_server.app import NAMESPACE, community_settings
from meeting_server.catalog import EnvResolvingCatalog
from meeting_server.settings import ServerSettings
from pydantic import BaseModel

CATALOG = "agents/catalog"


def placeholders(obj) -> list[str]:
    """Every `${VAR}` left anywhere in a hydrated card."""
    found: list[str] = []

    def walk(value) -> None:
        if isinstance(value, BaseModel):
            for name in type(value).model_fields:
                walk(getattr(value, name, None))
        elif isinstance(value, str):
            if "${" in value:
                found.append(value)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(obj)
    return found


@pytest.fixture
def env():
    """The placeholders pointing at test values, as startup would set them."""
    apply_env(
        AgentSettings(
            **{
                **AgentSettings.from_env().model_dump(),
                "catalog_path": CATALOG,
            }
        )
    )


@pytest.fixture
def settings(tmp_path):
    return ServerSettings(
        catalog_path=CATALOG,
        event_store_path=tmp_path / "events",
        workspaces_root=tmp_path / "workspaces",
    )


def test_the_plain_catalog_hands_out_placeholders(env, settings):
    """The behaviour this module exists to correct. If this ever stops being
    true the framework has started resolving, and the subclass can go."""
    from akgentic.catalog import Catalog

    card = Catalog(repository=YamlEntryRepository(root=settings.catalog_path)).load_team(NAMESPACE)

    assert placeholders(card), "expected the raw catalog to still carry ${VAR}"


def test_the_resolving_catalog_hands_out_real_values(env, settings):
    card = EnvResolvingCatalog(repository=YamlEntryRepository(root=settings.catalog_path)).load_team(
        NAMESPACE
    )

    assert placeholders(card) == []


def test_the_swap_reaches_the_team_service(env, settings):
    """The assumption the whole composition rests on.

    `TeamService` reads `services.catalog` when it loads a team rather than
    holding a reference from construction, so replacing the catalog after
    `wire_community` is enough. That is an implementation detail of a package
    we do not own, which is exactly why it is asserted here: a framework
    upgrade that starts capturing the catalog would otherwise be discovered by
    a demo, not by CI.
    """
    infra_settings = community_settings(settings)
    services = wire_community(infra_settings)
    try:
        services.catalog = EnvResolvingCatalog(
            repository=YamlEntryRepository(root=infra_settings.catalog_path)
        )

        resolved = services.team_service.resolve_team_metadata(NAMESPACE)

        assert placeholders(resolved.team_card) == []
    finally:
        services.actor_system.shutdown()


def test_the_model_type_allowlist_names_our_package(settings):
    """Without the prefix every `{__type__: meeting_agents....}` in the catalog
    is rejected, and the app factory reapplies this from settings at startup -
    so it has to be right here and not anywhere else."""
    assert "meeting_agents." in community_settings(settings).catalog_model_type_prefixes


def test_the_browser_origin_is_allowed_through(settings):
    """The SPA is a second origin by construction (G2)."""
    assert community_settings(settings).cors_origins == settings.cors_origins


def test_a_missing_variable_is_loud(settings, monkeypatch):
    """Resolution raises rather than leaving the placeholder in place. A quiet
    default here would ship a broken team that looks fine until it calls out."""
    monkeypatch.delenv("MEETING_MCP_URL", raising=False)

    with pytest.raises(Exception, match="MEETING_MCP_URL"):
        EnvResolvingCatalog(repository=YamlEntryRepository(root=settings.catalog_path)).load_team(NAMESPACE)


def test_the_chat_team_loads_through_the_team_service(env, settings):
    """The chat namespace names one of our own tool cards as a `model_type`
    (`meeting_agents.intake.IntakeTools`) and refers to the form team's agents
    across namespaces. Both only work as the server wires them - the allowlist
    is applied by the app factory, not by `wire_community` - so it is loaded
    through the composed app, the way `POST /teams` will load it."""
    from akgentic.infra.server import state_keys
    from meeting_server.app import create_meeting_app

    app = create_meeting_app(settings)
    services = state_keys.SERVICES.require(app)
    try:
        resolved = services.team_service.resolve_team_metadata("meeting-planner-chat")

        names = [m.card.config.name for m in resolved.team_card.entry_point.members]
        assert names == ["@Intake"]
        assert placeholders(resolved.team_card) == []
    finally:
        services.actor_system.shutdown()
