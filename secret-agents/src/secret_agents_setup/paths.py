"""Home-relative source selection shared by installers and standalone skill tools."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def agent_root_path(
    explicit: Path | None = None, *, environment: Mapping[str, str] | None = None, home: Path | None = None
) -> Path:
    """Select explicit path, environment override, then the standard home vault."""
    if explicit is not None:
        return explicit.expanduser().resolve()
    environment = os.environ if environment is None else environment
    configured = environment.get("SECRET_AGENTS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path.home() if home is None else home
    return (home / "obsidian" / "handbag-of-holding" / "secret-agents").resolve()
