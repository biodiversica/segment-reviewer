"""Storage abstraction: the reviewer works the same on a local folder or over SSH."""

from __future__ import annotations

import abc
import csv
import io
from pathlib import Path


class Backend(abc.ABC):
    """A place where segments live.

    Paths handed to and returned by a backend are absolute in that backend's own
    namespace: real filesystem paths for :class:`LocalBackend`, remote POSIX
    paths for :class:`SFTPBackend`.
    """

    #: Absolute path of the segments folder.
    root: str
    #: How the location is shown to the user (may include the ssh:// prefix).
    display: str

    # ── path helpers ─────────────────────────────────────────────────────────
    @abc.abstractmethod
    def join(self, *parts: str) -> str: ...

    @abc.abstractmethod
    def basename(self, path: str) -> str: ...

    @abc.abstractmethod
    def dirname(self, path: str) -> str: ...

    @abc.abstractmethod
    def relpath(self, path: str, start: str) -> str: ...

    @abc.abstractmethod
    def is_absolute(self, path: str) -> bool: ...

    def resolve(self, path: str) -> str:
        """Interpret a user-supplied path against the segments folder."""
        path = str(path).strip()
        if not path:
            return ""
        return path if self.is_absolute(path) else self.join(self.root, path)

    # ── filesystem ───────────────────────────────────────────────────────────
    @abc.abstractmethod
    def walk_wavs(self, base: str) -> list[str]:
        """Every ``*.wav`` under *base*, recursively, as absolute paths."""

    @abc.abstractmethod
    def exists(self, path: str) -> bool: ...

    @abc.abstractmethod
    def isdir(self, path: str) -> bool: ...

    @abc.abstractmethod
    def makedirs(self, path: str) -> None: ...

    @abc.abstractmethod
    def move(self, src: str, dst: str) -> None: ...

    @abc.abstractmethod
    def read_bytes(self, path: str) -> bytes: ...

    @abc.abstractmethod
    def size(self, path: str) -> int: ...

    @abc.abstractmethod
    def write_bytes(self, path: str, data: bytes) -> None: ...

    @abc.abstractmethod
    def fetch(self, path: str) -> Path:
        """A local copy of *path*, for libraries that need a real file."""

    def close(self) -> None:  # pragma: no cover - trivial
        """Release any connection held by the backend."""

    # ── shared conveniences ──────────────────────────────────────────────────
    def read_text(self, path: str) -> str | None:
        if not self.exists(path):
            return None
        return self.read_bytes(path).decode("utf-8", errors="replace")

    def append_csv_row(self, path: str, row: list[str], header: list[str]) -> None:
        """Append one CSV row, creating the file with *header* when new.

        Read-modify-write rather than an append handle: SFTP append modes are not
        uniformly supported, and an annotation table stays small enough that
        rewriting it costs nothing next to decoding a clip.
        """
        folder = self.dirname(path)
        if folder:
            self.makedirs(folder)
        existing = b"" if not self.exists(path) else self.read_bytes(path)
        buf = io.StringIO()
        writer = csv.writer(buf)
        if not existing:
            writer.writerow(header)
        writer.writerow(row)
        chunk = buf.getvalue().encode("utf-8")
        if existing and not existing.endswith(b"\n"):
            existing += b"\r\n"
        self.write_bytes(path, existing + chunk)

    def free_path(self, dest_dir: str, filename: str) -> str:
        """Destination path that does not overwrite an existing file.

        Renaming to the reviewer's labels can make two segments of the same
        window collide, so a ``_2``, ``_3``, ... suffix is added instead of
        replacing a reviewed file.
        """
        stem, _, ext = filename.rpartition(".")
        if not stem:  # no extension
            stem, ext = filename, ""
        ext = f".{ext}" if ext else ""
        path, n = self.join(dest_dir, filename), 2
        while self.exists(path):
            path = self.join(dest_dir, f"{stem}_{n}{ext}")
            n += 1
        return path

    def is_inside(self, path: str, folder: str) -> bool:
        """True when *path* sits inside *folder* (or is it)."""
        rel = self.relpath(path, folder)
        return rel == "." or not (rel == ".." or rel.startswith(".." + self.sep))

    @property
    def sep(self) -> str:
        return "/"
