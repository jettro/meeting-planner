"""Composing the server: the community tier, plus the two things we add.

The first is `/platform/health`. The second is a login (design_auth.md): the
framework already checks who owns which team, and `AuthModule` tells it who is
asking. There used to be a second, `/plans`, read
from a plan store of our own; it went when the coordinator's state became the
meeting's record (design_durability.md R3, R7). The browser now lists teams
and reads each coordinator's snapshot through the framework's own routes.

The assembly follows the framework's own instructions rather than inventing a
parallel one. `server_modules` is spliced into, never retyped - a retyped copy
of the composition drifts silently at the next upgrade, which the framework's
own docstring warns about.

Two things happen here that the framework cannot do for us:

1. The event store is taught to write a `time`, without which no message
   carrying a slot is ever persisted - see `yaml_types`.
2. The catalog is replaced with one that resolves `${VAR}`. `TeamService` reads
   `services.catalog` at the moment it loads a team, so assigning after wiring
   is enough - and there is a test that holds the framework to that.
3. `apply_env` is called, because the placeholders have to refer to something.
4. With `AUTH=demo`, `services.auth` is replaced the same way as the catalog,
   and the identity gate is added to the composition.
5. The agents are told to write their workspaces where the server reads them,
   and allowed the shared memory tree (`memory.py`, design_memory.md M12/M13).
"""

from __future__ import annotations

import logging

from akgentic.catalog import YamlEntryRepository
from akgentic.infra import CommunitySettings, create_app, wire_community
from akgentic.infra.server.app import server_modules
from fastapi import FastAPI
from meeting_agents.bootstrap import apply_env
from meeting_agents.settings import Settings as AgentSettings

from meeting_server.auth import AuthModule, DemoLogin, People, people_from
from meeting_server.catalog import EnvResolvingCatalog
from meeting_server.memory import configure_memory
from meeting_server.platform import PlatformModule
from meeting_server.settings import ServerSettings
from meeting_server.yaml_types import install_yaml_representers

logger = logging.getLogger(__name__)

#: The team the browser creates. One namespace, one team card - the server does
#: not need a team picker to run one demo.
NAMESPACE = "meeting-planner"


def community_settings(settings: ServerSettings) -> CommunitySettings:
    """The framework's settings, filled from ours.

    `catalog_model_type_prefixes` is the one that bites: the app factory
    reapplies the allowlist from settings at startup, so setting it anywhere
    else is overwritten and every `{__type__: meeting_agents....}` in the
    catalog is rejected as a disallowed prefix.
    """
    return CommunitySettings(
        catalog_path=settings.catalog_path,
        event_store_path=settings.event_store_path,
        workspaces_root=settings.workspaces_root,
        cors_origins=settings.cors_origins,
        catalog_model_type_prefixes=["meeting_agents."],
        # An admin sees every team, including the ones made as `anonymous`
        # before there was a login (design_auth.md A7). Without a login nobody
        # holds the role, so this changes nothing then.
        admin_list_all_teams=True,
        host=settings.host,
        port=settings.port,
    )


def create_meeting_app(settings: ServerSettings | None = None, *, people: People | None = None) -> FastAPI:
    """The server, ready to run.

    `people` is who may log in; by default, everyone the meeting service knows.
    """
    settings = settings or ServerSettings.from_env()
    agent_settings = AgentSettings.from_env()

    # Before the event store sees its first slot.
    install_yaml_representers()

    # Before anything loads a card: the placeholders have to point at values.
    apply_env(agent_settings)

    # Before the first team binds a workspace.
    configure_memory(settings.workspaces_root, settings.catalog_path)

    infra_settings = community_settings(settings)
    services = wire_community(infra_settings)
    services.catalog = EnvResolvingCatalog(repository=YamlEntryRepository(root=infra_settings.catalog_path))

    modules = [
        *server_modules(services, infra_settings),
        PlatformModule(settings),
    ]
    if settings.auth.mode == "demo":
        strategy = DemoLogin(
            settings.auth,
            people or people_from(settings.service_url("meeting-service") or "http://meeting-service:8001"),
            settings.cors_origins,
        )
        services.auth = strategy
        modules.append(AuthModule(strategy))
    logger.info("login: %s", settings.auth.mode)
    logger.info(
        "serving team namespace '%s' from %s, events in %s",
        NAMESPACE,
        settings.catalog_path,
        settings.event_store_path,
    )
    return create_app(services, infra_settings, modules=modules)


def main() -> None:
    """Run the server. The container's entry point."""
    import uvicorn

    settings = ServerSettings.from_env()
    uvicorn.run(create_meeting_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
