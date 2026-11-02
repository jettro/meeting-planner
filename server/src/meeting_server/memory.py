"""The two process settings memory depends on (design_memory.md M12, M13).

Both are environment variables read by akgentic's `WorkspaceTool` in the process
that binds agents - in the community tier, this server - so they are set here,
before the first team is built, rather than left for a deployment to get right.

- **M12 - one root.** The server's routes and team deletion read
  `WORKSPACES_ROOT`; the agents write under `AKGENTIC_WORKSPACES_ROOT`, which
  defaults to `./workspaces`. Left apart, the agents write off the volume and the
  console reads an empty directory (spike S3). The server's own setting wins.
- **M13 - permission to share.** `memory-shared` is a shared tree, which needs
  `AKGENTIC_WORKSPACE_SHARED_KINDS` to permit `id`. A refused bind does not stop a
  team from being built - the agent is left half-wired (spike S5) - so an
  explicit value that forbids it stops the server instead. Unset, it is set:
  sharing that one kind is what this deployment's catalog asks for.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from meeting_agents.memory import MemoryConfigurationError, permit_sharing

logger = logging.getLogger(__name__)

ROOT_ENV = "AKGENTIC_WORKSPACES_ROOT"

#: What a catalog entry using memory names; its presence is what needs sharing.
MEMORY_MODEL_TYPE = "meeting_agents.memory.MemoryTool"


__all__ = ["MemoryConfigurationError", "configure_memory", "uses_memory"]


def uses_memory(catalog_path: Path) -> bool:
    """True when any catalog entry is a `MemoryTool`."""
    return any(MEMORY_MODEL_TYPE in path.read_text() for path in Path(catalog_path).rglob("*.yaml"))


def configure_memory(workspaces_root: Path, catalog_path: Path) -> None:
    """Make the agents write where the server reads, and let them share (M12, M13)."""
    root = str(Path(workspaces_root).resolve())
    previous = os.environ.get(ROOT_ENV)
    if previous and str(Path(previous).resolve()) != root:
        logger.warning("%s was %s; using the server's workspaces root %s", ROOT_ENV, previous, root)
    os.environ[ROOT_ENV] = root

    if uses_memory(catalog_path):
        permit_sharing()
