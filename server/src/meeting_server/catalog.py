"""A catalog that resolves `${VAR}` before a team is built from it.

The CLI calls `bootstrap.load_team_card`, which resolves placeholders after
hydration. The server never gets that chance: `wire_community` builds its own
plain `Catalog` and `TeamService` loads the card through it, so a team created
over HTTP would be handed a tool configured to call a host literally named
`${MEETING_MCP_URL}`.

Resolving here rather than writing a resolved copy of the catalog to disk is
deliberate. The placeholders exist so that API keys are not in the repository;
expanding them into a temp directory would put them back on a filesystem, just
a less obvious one.
"""

from __future__ import annotations

import logging

from akgentic.catalog import Catalog
from akgentic.team import TeamCard
from meeting_agents.bootstrap import resolve_env_in_place

logger = logging.getLogger(__name__)


class EnvResolvingCatalog(Catalog):
    """`Catalog`, plus the resolution step the framework leaves to its callers.

    Only `load_team` is overridden. That is the single door `TeamService` uses,
    and the admin catalog routes deliberately keep reading the raw entries:
    an operator inspecting the catalog through `/admin/catalog/...` should see
    `${MEETING_MCP_API_KEY}`, not the key.
    """

    def load_team(self, namespace: str) -> TeamCard:
        card = super().load_team(namespace)
        resolve_env_in_place(card)
        logger.info("resolved environment placeholders in team '%s'", card.name)
        return card
