"""Shared resolved-path containment checks for managed directories."""

from pathlib import Path


def is_path_within(path: Path, root: Path, *, follow_leaf: bool) -> bool:
    if not path.is_absolute() or not root.is_absolute() or path.name == "..":
        return False
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False) if follow_leaf else path.parent.resolve(strict=False) / path.name
    return resolved_path.is_relative_to(resolved_root)
