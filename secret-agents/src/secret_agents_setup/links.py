"""Cross-platform link creation, inspection, and removal backends."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from subprocess import CompletedProcess
from typing import Protocol

from .link_errors import (
    JunctionFailed,
    LinkTargetMismatch,
    NotALink,
    PartialLinkCleanupFailed,
    SymlinkFailed,
    SymlinkPrivilegeRequired,
    SymlinkUnsupported,
)
from .link_errors import LinkOperationError as LinkOperationError


class LinkBackend(Protocol):
    def probe_file_link_capability(self, probe_root: Path) -> None: ...

    def create_directory_link(self, src: Path, dst: Path) -> None: ...

    def create_file_link(self, src: Path, dst: Path) -> None: ...

    def remove_link(self, path: Path) -> None: ...

    def resolved_target(self, path: Path) -> Path: ...


class PosixLinkBackend(LinkBackend):
    def probe_file_link_capability(self, probe_root: Path) -> None:
        pass

    def create_directory_link(self, src: Path, dst: Path) -> None:
        _create_and_verify(
            src,
            dst,
            lambda: os.symlink(src, dst, target_is_directory=True),
            self._verify_created_link,
            self.remove_link,
        )

    def create_file_link(self, src: Path, dst: Path) -> None:
        _create_and_verify(src, dst, lambda: os.symlink(src, dst), self._verify_created_link, self.remove_link)

    def remove_link(self, path: Path) -> None:
        _remove_link(path)

    def resolved_target(self, path: Path) -> Path:
        return path.resolve(strict=False)

    def _verify_created_link(self, src: Path, dst: Path) -> None:
        _verify_created_link(self, src, dst)


class WindowsLinkBackend(LinkBackend):
    RunCommand = Callable[[Sequence[str]], CompletedProcess[str]]
    CreateSymlink = Callable[..., None]

    def __init__(
        self,
        run_command: RunCommand | None = None,
        create_symlink: CreateSymlink = os.symlink,
    ) -> None:
        self._run_command = run_command or _run_command
        self._create_symlink = create_symlink

    def probe_file_link_capability(self, probe_root: Path) -> None:
        probe_directory = Path(tempfile.mkdtemp(prefix="secret-agents-link-probe-", dir=probe_root))
        src = probe_directory / "src-file"
        dst = probe_directory / "file-link"
        src.write_text("probe", encoding="utf-8")
        try:
            self._attempt_file_link_probe(src, dst)
        finally:
            _remove_probe_artifacts(src, dst, probe_directory)

    def _attempt_file_link_probe(self, src: Path, dst: Path) -> None:
        try:
            self._create_symlink(src, dst)
            self._verify_created_link(src, dst)
        except OSError as exc:
            if getattr(exc, "winerror", None) == SymlinkPrivilegeRequired.WINERROR_PRIVILEGE_NOT_HELD:
                raise SymlinkPrivilegeRequired() from exc
            raise SymlinkUnsupported(exc) from exc

    def create_directory_link(self, src: Path, dst: Path) -> None:
        _create_and_verify(
            src,
            dst,
            lambda: self._create_directory_junction(src, dst),
            self._verify_created_link,
            self.remove_link,
        )

    def create_file_link(self, src: Path, dst: Path) -> None:
        _create_and_verify(
            src,
            dst,
            lambda: self._create_file_symlink(src, dst),
            self._verify_created_link,
            self.remove_link,
        )

    def remove_link(self, path: Path) -> None:
        _remove_link(path)

    def resolved_target(self, path: Path) -> Path:
        return path.resolve(strict=False)

    def _create_directory_junction(self, src: Path, dst: Path) -> None:
        command = ("cmd.exe", "/d", "/c", "mklink", "/J", str(dst), str(src))
        result = self._run_command(command)
        if result.returncode != 0:
            raise JunctionFailed(src, dst, result)

    def _create_file_symlink(self, src: Path, dst: Path) -> None:
        try:
            self._create_symlink(src, dst)
        except OSError as exc:
            raise SymlinkFailed(src, dst, exc) from exc

    def _verify_created_link(self, src: Path, dst: Path) -> None:
        _verify_created_link(self, src, dst)


def backend_for(os_name: str) -> LinkBackend:
    if os_name == "posix":
        return PosixLinkBackend()
    if os_name == "nt":
        return WindowsLinkBackend()
    raise ValueError(f"unsupported operating system: {os_name}")


def _run_command(argv: Sequence[str]) -> CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def _create_and_verify(
    src: Path,
    dst: Path,
    create_link: Callable[[], None],
    verify_link: Callable[[Path, Path], None],
    remove_link: Callable[[Path], None],
) -> None:
    created = False
    try:
        create_link()
        created = True
        verify_link(src, dst)
    except BaseException as create_error:
        if not created:
            raise
        try:
            remove_link(dst)
        except Exception as cleanup_error:
            raise PartialLinkCleanupFailed(dst, create_error, cleanup_error) from create_error
        raise


def _verify_created_link(
    backend: LinkBackend,
    src: Path,
    dst: Path,
) -> None:
    resolved_src = src.resolve(strict=False)
    resolved_dst = backend.resolved_target(dst)
    if resolved_dst != resolved_src:
        raise LinkTargetMismatch(dst, resolved_dst, resolved_src)


def _remove_link(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
        return
    if _is_junction(path):
        path.rmdir()
        return
    raise NotALink(path)


def _remove_probe_artifacts(src: Path, dst: Path, probe_directory: Path) -> None:
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif _is_junction(dst) or dst.is_dir():
        dst.rmdir()
    src.unlink(missing_ok=True)
    probe_directory.rmdir()


def _is_junction(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        reparse_tag = getattr(os.lstat(path), "st_reparse_tag", None)
    except OSError:
        return False
    return reparse_tag == 0xA0000003
