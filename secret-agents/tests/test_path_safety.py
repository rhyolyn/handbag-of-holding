from pathlib import Path

import pytest

from secret_agents_setup.path_safety import is_path_within


def test_lexical_parent_traversal_is_outside(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    home.mkdir()

    assert not is_path_within(home / ".." / "victim", home, follow_leaf=False)


def test_parent_directory_leaf_is_outside_without_following_leaf(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    home.mkdir()

    assert not is_path_within(home / "..", home, follow_leaf=False)


def test_destination_below_home_is_inside_without_following_leaf(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    home.mkdir()

    assert is_path_within(home / ".codex" / "AGENTS.md", home, follow_leaf=False)


def test_linked_parent_outside_home_is_rejected(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    outside = (tmp_path / "outside").resolve()
    home.mkdir()
    outside.mkdir()
    try:
        (home / ".codex").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"host cannot create parent symlink: {exc}")

    assert not is_path_within(home / ".codex" / "AGENTS.md", home, follow_leaf=False)
