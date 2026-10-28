"""Turning the catalog YAML into a running team.

This module exists because of one verified fact about the framework: **nothing
in it resolves `${VAR}` for us**. `akgentic.catalog.env.resolve_env_vars` says
so itself - "called by runtime consumers, not by catalog services" - and a
search of the installed packages finds no caller. The catalog deliberately
stores `${MEETING_MCP_API_KEY}` verbatim so the YAML is safe to commit; turning
that into a real key at startup is this module's job and nobody else's.

Resolution is loud on a missing variable. A placeholder left unresolved would
otherwise travel all the way to an HTTP client, which would then try to connect
to a host literally named `${MEETING_MCP_URL}` and fail somewhere far away from
the cause.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from akgentic.catalog import Catalog, YamlEntryRepository, resolve_env_vars, set_allowed_prefixes
from akgentic.team import TeamCard
from pydantic import BaseModel

from meeting_agents.settings import Settings

logger = logging.getLogger(__name__)


def apply_env(settings: Settings) -> None:
    """Export the values the catalog's `${VAR}` placeholders refer to.

    Set, not defaulted: `Settings` has already applied the precedence rules, so
    this is the resolved truth rather than another layer of fallback.
    """
    for key, value in settings.as_catalog_env().items():
        os.environ[key] = value


def resolve_env_in_place(obj: Any) -> None:
    """Walk a hydrated model and replace every `${VAR}` it carries.

    Done after hydration rather than on the raw YAML so that it reaches values
    wherever they ended up - a tool's URL, its bearer token -
    without this module needing to know the shape of each card.
    """
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            value = getattr(obj, name, None)
            if isinstance(value, str):
                if "${" in value:
                    object.__setattr__(obj, name, resolve_env_vars(value))
            else:
                resolve_env_in_place(value)
    elif isinstance(obj, list):
        for item in obj:
            resolve_env_in_place(item)
    elif isinstance(obj, dict):
        for item in obj.values():
            resolve_env_in_place(item)


#: The packages whose classes a catalog entry may name as its `model_type`.
#: `akgentic.` is always allowed; ours is needed once a card names one of our
#: own tool cards (`meeting_agents.intake.IntakeTools`). The server sets the
#: same list through `catalog_model_type_prefixes`.
MODEL_TYPE_PREFIXES = ["meeting_agents."]


def build_catalog(settings: Settings) -> Catalog:
    """A catalog reading the YAML namespace directories under `catalog_path`."""
    set_allowed_prefixes(MODEL_TYPE_PREFIXES)
    root = Path(settings.catalog_path)
    if not root.is_dir():
        raise FileNotFoundError(f"catalog directory not found: {root.resolve()}")
    return Catalog(repository=YamlEntryRepository(root=root))


def load_team_card(settings: Settings, namespace: str = "meeting-planner") -> TeamCard:
    """The team card, fully resolved and ready to build.

    Every `${VAR}` is real by the time this returns, so a configuration mistake
    surfaces here - at startup, naming the variable - rather than mid-saga.
    """
    apply_env(settings)
    card = build_catalog(settings).load_team(namespace)
    resolve_env_in_place(card)
    logger.info("loaded team '%s' from %s", card.name, settings.catalog_path)
    return card
