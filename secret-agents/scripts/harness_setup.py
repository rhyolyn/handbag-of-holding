#!/usr/bin/env python3
"""Zero-install bootstrap: run the harness-setup CLI directly from a source checkout."""

from __future__ import annotations

import sys
from pathlib import Path


def _run() -> int:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "src"))
    from secret_agents_setup.cli import main

    return main(script_path=Path(__file__))


if __name__ == "__main__":
    raise SystemExit(_run())
