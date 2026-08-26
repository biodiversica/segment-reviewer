"""Segments sitting on a folder this machine can already see."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .base import Backend


class LocalBackend(Backend):
    def __init__(self, root: str) -> None:
        self.root = str(Path(root).expanduser().resolve())
        self.display = self.root

    # ── path helpers ─────────────────────────────────────────────────────────
    def join(self, *parts: str) -> str:
        return os.path.join(*parts)

    def basename(self, path: str) -> str:
        return os.path.basename(path)

    def dirname(self, path: str) -> str:
        return os.path.dirname(path)

    def relpath(self, path: str, start: str) -> str:
        return os.path.relpath(path, start)

    def is_absolute(self, path: str) -> bool:
        return os.path.isabs(os.path.expanduser(path))

    def resolve(self, path: str) -> str:
        path = str(path).strip()
        if not path:
            return ""
        path = os.path.expanduser(path)
        return path if os.path.isabs(path) else os.path.join(self.root, path)

    @property
    def sep(self) -> str:
        return os.sep

    # ── filesystem ───────────────────────────────────────────────────────────
    def walk_wavs(self, base: str) -> list[str]:
        found: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                if name.lower().endswith(".wav"):
                    found.append(os.path.join(dirpath, name))
        return sorted(found)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def isdir(self, path: str) -> bool:
        return os.path.isdir(path)

    def makedirs(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def move(self, src: str, dst: str) -> None:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)

    def read_bytes(self, path: str) -> bytes:
        with open(path, "rb") as fh:
            return fh.read()

    def size(self, path: str) -> int:
        return os.path.getsize(path)

    def write_bytes(self, path: str, data: bytes) -> None:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = f"{path}.tmp-segrev"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)

    def fetch(self, path: str) -> Path:
        return Path(path)
