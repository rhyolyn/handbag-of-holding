from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from secret_agents_setup.link_errors import LinkOperationError, SymlinkPrivilegeRequired
from secret_agents_setup.links import (
    PosixLinkBackend,
    WindowsLinkBackend,
    backend_for,
)


def test_backend_for_selects_supported_operating_system() -> None:
    assert isinstance(backend_for("posix"), PosixLinkBackend)
    assert isinstance(backend_for("nt"), WindowsLinkBackend)


def test_backend_for_refuses_unknown_operating_system() -> None:
    with pytest.raises(ValueError, match="unsupported operating system.*mystery"):
        backend_for("mystery")


def test_posix_backend_creates_directory_link_and_resolves_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()

    PosixLinkBackend().create_directory_link(source, destination)

    assert destination.is_symlink()
    assert destination.resolve() == source.resolve()


def test_posix_backend_creates_file_link_and_resolves_target(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("canonical", encoding="utf-8")

    backend = PosixLinkBackend()
    backend.create_file_link(source, destination)

    assert destination.is_symlink()
    assert backend.resolved_target(destination) == source.resolve()


def test_posix_backend_removes_broken_link(tmp_path: Path) -> None:
    destination = tmp_path / "broken"
    destination.symlink_to(tmp_path / "missing")

    PosixLinkBackend().remove_link(destination)

    assert not destination.is_symlink()


def test_posix_backend_refuses_to_remove_real_directory(tmp_path: Path) -> None:
    destination = tmp_path / "real-directory"
    destination.mkdir()

    with pytest.raises(LinkOperationError, match="refuse.*real-directory"):
        PosixLinkBackend().remove_link(destination)

    assert destination.is_dir()


def test_posix_file_link_probe_reports_supported(tmp_path: Path) -> None:
    PosixLinkBackend().probe_file_link_capability(tmp_path)


def test_windows_directory_link_uses_exact_junction_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    commands: list[tuple[str, ...]] = []

    def run_command(argv: Sequence[str]) -> CompletedProcess[str]:
        commands.append(tuple(argv))
        destination.mkdir()
        return CompletedProcess(argv, 0, stdout="junction created", stderr="")

    backend = WindowsLinkBackend(run_command=run_command)
    monkeypatch.setattr(backend, "resolved_target", lambda path: source.resolve())

    backend.create_directory_link(source, destination)

    assert commands == [("cmd.exe", "/d", "/c", "mklink", "/J", str(destination), str(source))]


def test_windows_junction_failure_includes_output_and_both_paths(tmp_path: Path) -> None:
    source = tmp_path / "canonical skills"
    destination = tmp_path / "personal skills"

    def run_command(argv: Sequence[str]) -> CompletedProcess[str]:
        return CompletedProcess(argv, 1, stdout="junction stdout", stderr="junction stderr")

    backend = WindowsLinkBackend(run_command=run_command)

    with pytest.raises(LinkOperationError) as raised:
        backend.create_directory_link(source, destination)

    message = str(raised.value)
    assert "junction stdout" in message
    assert "junction stderr" in message
    assert str(source) in message
    assert str(destination) in message


class _WindowsPrivilegeError(OSError):
    winerror = 1314


def test_windows_probe_reports_controlled_privilege_prerequisite(tmp_path: Path) -> None:
    def refuse_symlink(source: Path, destination: Path) -> None:
        raise _WindowsPrivilegeError("A required privilege is not held by the client")

    with pytest.raises(SymlinkPrivilegeRequired, match="Developer Mode or elevation"):
        WindowsLinkBackend(create_symlink=refuse_symlink).probe_file_link_capability(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_windows_successful_probe_removes_every_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def create_probe_file(source: Path, destination: Path) -> None:
        destination.touch()

    backend = WindowsLinkBackend(create_symlink=create_probe_file)
    monkeypatch.setattr(
        backend,
        "resolved_target",
        lambda path: next(path.parent.glob("src-*")),
    )

    backend.probe_file_link_capability(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_windows_file_link_uses_injected_symlink_creator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("canonical", encoding="utf-8")
    calls: list[tuple[Path, Path]] = []

    def create_symlink(link_source: Path, link_destination: Path) -> None:
        calls.append((link_source, link_destination))
        link_destination.touch()

    backend = WindowsLinkBackend(create_symlink=create_symlink)
    monkeypatch.setattr(backend, "resolved_target", lambda path: source.resolve())

    backend.create_file_link(source, destination)

    assert calls == [(source, destination)]


def test_link_backends_never_use_hardlinks_or_copy_fallbacks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("hardlink or copy fallback invoked")

    forbidden_apis: tuple[tuple[object, str], ...] = (
        (os, "link"),
        (shutil, "copy"),
        (shutil, "copy2"),
        (shutil, "copyfile"),
        (shutil, "copytree"),
    )
    for owner, name in forbidden_apis:
        monkeypatch.setattr(owner, name, forbidden)

    source_directory = tmp_path / "source-directory"
    source_directory.mkdir()
    PosixLinkBackend().create_directory_link(source_directory, tmp_path / "directory-link")

    source_file = tmp_path / "source.txt"
    source_file.touch()
    PosixLinkBackend().create_file_link(source_file, tmp_path / "file-link")

    commands: list[tuple[str, ...]] = []

    def run_command(argv: Sequence[str]) -> CompletedProcess[str]:
        commands.append(tuple(argv))
        (tmp_path / "windows-directory-link").mkdir()
        return CompletedProcess(argv, 0, stdout="", stderr="")

    windows_backend = WindowsLinkBackend(run_command=run_command)
    monkeypatch.setattr(
        windows_backend,
        "resolved_target",
        lambda path: source_directory.resolve(),
    )
    windows_backend.create_directory_link(source_directory, tmp_path / "windows-directory-link")

    assert all("/H" not in command for command in commands)


def test_current_host_creates_and_removes_real_directory_link(tmp_path: Path) -> None:
    backend = backend_for(os.name)
    if os.name == "nt":
        try:
            backend.probe_file_link_capability(tmp_path)
        except SymlinkPrivilegeRequired as exc:
            pytest.skip(str(exc))

    source = tmp_path / "real-source"
    destination = tmp_path / "real-link"
    source.mkdir()

    backend.create_directory_link(source, destination)

    assert backend.resolved_target(destination) == source.resolve()
    backend.remove_link(destination)
    assert not destination.exists()
    assert source.is_dir()
