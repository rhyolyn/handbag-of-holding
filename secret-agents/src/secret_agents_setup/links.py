"""Cross-platform link creation, inspection, and removal backends."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Protocol


class LinkOperationError(Exception):
    """Raised when a link operation cannot be completed safely."""


@dataclass(frozen=True)
class LinkCapability:
    supported: bool
    requires_privilege: bool
    message: str


class LinkBackend(Protocol):
    def probe_file_link_capability(self, probe_root: Path) -> LinkCapability: ...

    def create_directory_link(self, source: Path, destination: Path) -> None: ...

    def create_file_link(self, source: Path, destination: Path) -> None: ...

    def remove_link(self, path: Path) -> None: ...

    def resolved_target(self, path: Path) -> Path: ...


class PosixLinkBackend:
    def probe_file_link_capability(self, probe_root: Path) -> LinkCapability:
        return LinkCapability(
            supported=True,
            requires_privilege=False,
            message="POSIX symbolic links are supported.",
        )

    def create_directory_link(self, source: Path, destination: Path) -> None:
        os.symlink(source, destination, target_is_directory=True)
        self._verify_created_link(source, destination)

    def create_file_link(self, source: Path, destination: Path) -> None:
        os.symlink(source, destination)
        self._verify_created_link(source, destination)

    def remove_link(self, path: Path) -> None:
        _remove_link(path)

    def resolved_target(self, path: Path) -> Path:
        return path.resolve(strict=False)

    def _verify_created_link(self, source: Path, destination: Path) -> None:
        _verify_created_link(self, source, destination)


RunCommand = Callable[[Sequence[str]], CompletedProcess[str]]
CreateSymlink = Callable[..., None]


class WindowsLinkBackend:
    def __init__(
        self,
        run_command: RunCommand | None = None,
        create_symlink: CreateSymlink = os.symlink,
    ) -> None:
        self._run_command = run_command or _run_command
        self._create_symlink = create_symlink

    def probe_file_link_capability(self, probe_root: Path) -> LinkCapability:
        probe_directory = Path(tempfile.mkdtemp(prefix="secret-agents-link-probe-", dir=probe_root))
        source = probe_directory / "source-file"
        destination = probe_directory / "file-link"
        source.write_text("probe", encoding="utf-8")

        try:
            self._create_symlink(source, destination)
            self._verify_created_link(source, destination)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                return LinkCapability(
                    supported=False,
                    requires_privilege=True,
                    message=(
                        "Windows file symbolic links require Developer Mode or elevation "
                        "(error 1314)."
                    ),
                )
            return LinkCapability(
                supported=False,
                requires_privilege=False,
                message=f"Windows file symbolic-link capability probe failed: {exc}",
            )
        finally:
            _remove_probe_artifacts(source, destination, probe_directory)

        return LinkCapability(
            supported=True,
            requires_privilege=False,
            message="Windows file symbolic links are supported.",
        )

    def create_directory_link(self, source: Path, destination: Path) -> None:
        command = (
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(destination),
            str(source),
        )
        result = self._run_command(command)
        if result.returncode != 0:
            raise LinkOperationError(
                f"junction command failed for source {source} and destination {destination}; "
                f"stdout: {result.stdout!r}; stderr: {result.stderr!r}"
            )
        self._verify_created_link(source, destination)

    def create_file_link(self, source: Path, destination: Path) -> None:
        try:
            self._create_symlink(source, destination)
        except OSError as exc:
            raise LinkOperationError(
                f"file symbolic link failed for source {source} and destination {destination}: "
                f"{exc}"
            ) from exc
        self._verify_created_link(source, destination)

    def remove_link(self, path: Path) -> None:
        _remove_link(path)

    def resolved_target(self, path: Path) -> Path:
        return path.resolve(strict=False)

    def _verify_created_link(self, source: Path, destination: Path) -> None:
        _verify_created_link(self, source, destination)


def backend_for(os_name: str) -> LinkBackend:
    if os_name == "posix":
        return PosixLinkBackend()
    if os_name == "nt":
        return WindowsLinkBackend()
    raise ValueError(f"unsupported operating system: {os_name}")


def _run_command(argv: Sequence[str]) -> CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def _verify_created_link(
    backend: LinkBackend,
    source: Path,
    destination: Path,
) -> None:
    resolved_source = source.resolve(strict=False)
    resolved_destination = backend.resolved_target(destination)
    if resolved_destination != resolved_source:
        raise LinkOperationError(
            f"created link destination {destination} resolved to {resolved_destination}, "
            f"not source {resolved_source}"
        )


def _remove_link(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
        return
    if _is_junction(path):
        path.rmdir()
        return
    raise LinkOperationError(f"refuse to remove non-link path: {path}")


def _remove_probe_artifacts(source: Path, destination: Path, probe_directory: Path) -> None:
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif _is_junction(destination) or destination.is_dir():
        destination.rmdir()
    source.unlink(missing_ok=True)
    probe_directory.rmdir()


def _is_junction(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        reparse_tag = getattr(os.lstat(path), "st_reparse_tag", None)
    except OSError:
        return False
    return reparse_tag == 0xA0000003
