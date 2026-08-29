"""Module entry point: ``python -m secret_agents_setup``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
