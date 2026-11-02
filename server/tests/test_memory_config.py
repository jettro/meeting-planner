"""The two process settings memory depends on (design_memory.md M12, M13)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from meeting_server.memory import MemoryConfigurationError, configure_memory, uses_memory

CATALOG = Path("agents/catalog")
SHARED = "AKGENTIC_WORKSPACE_SHARED_KINDS"
ROOT = "AKGENTIC_WORKSPACES_ROOT"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv(SHARED, raising=False)
    monkeypatch.delenv(ROOT, raising=False)


def test_the_agents_write_where_the_server_reads(tmp_path):
    """M12: without it the agents write to ./workspaces, off the volume (spike S3)."""
    configure_memory(tmp_path / "workspaces", CATALOG)

    assert os.environ[ROOT] == str((tmp_path / "workspaces").resolve())


def test_the_servers_root_wins_over_a_different_one(tmp_path, monkeypatch):
    monkeypatch.setenv(ROOT, str(tmp_path / "elsewhere"))

    configure_memory(tmp_path / "workspaces", CATALOG)

    assert os.environ[ROOT] == str((tmp_path / "workspaces").resolve())


def test_our_catalog_uses_memory():
    assert uses_memory(CATALOG)


def test_sharing_is_allowed_when_nobody_said_otherwise(tmp_path):
    configure_memory(tmp_path, CATALOG)

    assert os.environ[SHARED] == "id"


def test_a_setting_that_forbids_it_stops_the_server(tmp_path, monkeypatch):
    """M13: a refused bind would leave a half-wired agent in a built team (spike S5)."""
    monkeypatch.setenv(SHARED, "meta")

    with pytest.raises(MemoryConfigurationError, match="does not permit 'id'"):
        configure_memory(tmp_path, CATALOG)


def test_a_setting_that_includes_it_is_kept(tmp_path, monkeypatch):
    monkeypatch.setenv(SHARED, "meta,id")

    configure_memory(tmp_path, CATALOG)

    assert os.environ[SHARED] == "meta,id"


def test_a_catalog_without_memory_asks_for_no_sharing(tmp_path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "agent.yaml").write_text("model_type: akgentic.core.AgentCard\n")

    configure_memory(tmp_path / "workspaces", catalog)

    assert SHARED not in os.environ
