"""Segments sitting on another machine, reached over SSH (SFTP)."""

from __future__ import annotations

import errno
import hashlib
import os
import posixpath
import stat
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

import paramiko

from .base import Backend


@dataclass
class SSHTarget:
    """Everything needed to open one SFTP session."""

    host: str
    path: str
    user: str | None = None
    port: int | None = None
    key_filename: str | None = None
    password: str | None = None
    known_hosts: str | None = None
    accept_new_host_key: bool = False
    options: dict = field(default_factory=dict)

    def apply_ssh_config(self, config_path: str | os.PathLike | None = None) -> "SSHTarget":
        """Fill in host/user/port/key from ``~/.ssh/config``, so aliases work."""
        config_path = Path(config_path or Path.home() / ".ssh" / "config")
        if not config_path.exists():
            return self
        cfg = paramiko.SSHConfig()
        try:
            with open(config_path) as fh:
                cfg.parse(fh)
        except OSError:
            return self
        entry = cfg.lookup(self.host)
        self.options = dict(entry)
        self.host = entry.get("hostname", self.host)
        if self.user is None and entry.get("user"):
            self.user = entry["user"]
        if self.port is None and entry.get("port"):
            self.port = int(entry["port"])
        if self.key_filename is None and entry.get("identityfile"):
            self.key_filename = os.path.expanduser(entry["identityfile"][0])
        return self

    @property
    def label(self) -> str:
        who = f"{self.user}@" if self.user else ""
        where = f":{self.port}" if self.port and self.port != 22 else ""
        return f"ssh://{who}{self.host}{where}{self.path}"


def parse_ssh_spec(spec: str) -> SSHTarget | None:
    """Recognise ``ssh://[user@]host[:port]/path`` and ``[user@]host:/path``."""
    spec = spec.strip()
    if spec.startswith(("ssh://", "sftp://")):
        rest = spec.split("://", 1)[1]
        netloc, _, path = rest.partition("/")
        path = "/" + path if path else "/"
    elif ":" in spec and not os.path.exists(spec) and not spec.startswith(("/", ".", "~")):
        netloc, _, path = spec.partition(":")
        if not path or "\\" in netloc:  # a Windows drive letter, not a host
            return None
        path = path or "."
    else:
        return None

    user = None
    if "@" in netloc:
        user, _, netloc = netloc.rpartition("@")
    port = None
    if ":" in netloc:
        netloc, _, port_s = netloc.rpartition(":")
        try:
            port = int(port_s)
        except ValueError:
            return None
    if not netloc:
        return None
    return SSHTarget(host=netloc, path=path or "/", user=user, port=port)


class SFTPBackend(Backend):
    """SFTP-backed storage with a local cache for audio decoding.

    One paramiko channel serialised behind a lock: the reviewer issues a handful
    of small operations per segment, and a single reviewer drives the session.
    """

    def __init__(self, target: SSHTarget, cache_dir: str | None = None) -> None:
        self.target = target
        self._lock = threading.RLock()
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self._connect()
        assert self._sftp is not None
        root = target.path
        if not root.startswith("/"):
            # Relative to the login directory, which SFTP reports as the cwd.
            root = posixpath.join(self._sftp.normalize("."), root)
        self.root = posixpath.normpath(root)
        self.display = SSHTarget(**{**target.__dict__, "path": self.root}).label
        self._cache = Path(cache_dir or tempfile.mkdtemp(prefix="segment-reviewer-"))
        self._cache.mkdir(parents=True, exist_ok=True)
        self._owns_cache = cache_dir is None

    # ── connection ───────────────────────────────────────────────────────────
    def _connect(self) -> None:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self.target.known_hosts:
            client.load_host_keys(os.path.expanduser(self.target.known_hosts))
        client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy() if self.target.accept_new_host_key else paramiko.RejectPolicy()
        )
        # An explicit password means password auth: leaving the agent in the mix
        # lets a key that cannot sign for this host abort the connection before
        # the password is ever offered.
        by_password = bool(self.target.password) and not self.target.key_filename
        client.connect(
            hostname=self.target.host,
            port=self.target.port or 22,
            username=self.target.user,
            key_filename=self.target.key_filename,
            password=self.target.password,
            allow_agent=not by_password,
            look_for_keys=not by_password,
            timeout=20,
        )
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(30)
        self._client = client
        self._sftp = client.open_sftp()

    def _sftp_call(self, name: str, *args, **kwargs):
        """Run one SFTP operation, reconnecting once if the channel died."""
        with self._lock:
            try:
                return getattr(self._sftp, name)(*args, **kwargs)
            except (OSError, paramiko.SSHException) as exc:
                if isinstance(exc, IOError) and getattr(exc, "errno", None) in (
                    errno.ENOENT,
                    errno.EACCES,
                    errno.EEXIST,
                ):
                    raise
                self._reconnect()
                return getattr(self._sftp, name)(*args, **kwargs)

    def _reconnect(self) -> None:
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass
        self._connect()

    def close(self) -> None:
        with self._lock:
            for obj in (self._sftp, self._client):
                try:
                    if obj is not None:
                        obj.close()
                except Exception:
                    pass
            self._sftp = self._client = None

    # ── path helpers ─────────────────────────────────────────────────────────
    def join(self, *parts: str) -> str:
        return posixpath.join(*parts)

    def basename(self, path: str) -> str:
        return posixpath.basename(path)

    def dirname(self, path: str) -> str:
        return posixpath.dirname(path)

    def relpath(self, path: str, start: str) -> str:
        return posixpath.relpath(path, start)

    def is_absolute(self, path: str) -> bool:
        return path.startswith("/")

    # ── filesystem ───────────────────────────────────────────────────────────
    def walk_wavs(self, base: str) -> list[str]:
        found: list[str] = []
        stack = [base]
        while stack:
            current = stack.pop()
            try:
                entries = self._sftp_call("listdir_attr", current)
            except IOError:
                continue
            for attr in entries:
                path = posixpath.join(current, attr.filename)
                mode = attr.st_mode or 0
                if stat.S_ISDIR(mode):
                    stack.append(path)
                elif attr.filename.lower().endswith(".wav"):
                    found.append(path)
        return sorted(found)

    def exists(self, path: str) -> bool:
        try:
            self._sftp_call("stat", path)
            return True
        except IOError:
            return False

    def isdir(self, path: str) -> bool:
        try:
            return stat.S_ISDIR(self._sftp_call("stat", path).st_mode or 0)
        except IOError:
            return False

    def makedirs(self, path: str) -> None:
        parts, missing = path.rstrip("/"), []
        while parts and parts != "/" and not self.exists(parts):
            missing.append(parts)
            parts = posixpath.dirname(parts)
        for folder in reversed(missing):
            try:
                self._sftp_call("mkdir", folder)
            except IOError:
                if not self.isdir(folder):
                    raise

    def move(self, src: str, dst: str) -> None:
        self.makedirs(posixpath.dirname(dst))
        try:
            self._sftp_call("posix_rename", src, dst)
        except (IOError, AttributeError, paramiko.SSHException):
            # posix_rename is an OpenSSH extension; plain rename is the fallback.
            self._sftp_call("rename", src, dst)
        self._drop_cached(src)

    def read_bytes(self, path: str) -> bytes:
        with self._lock:
            handle = self._sftp_call("open", path, "rb")
            try:
                handle.prefetch()
                return handle.read()
            finally:
                handle.close()

    def size(self, path: str) -> int:
        return int(self._sftp_call("stat", path).st_size or 0)

    def write_bytes(self, path: str, data: bytes) -> None:
        folder = posixpath.dirname(path)
        if folder:
            self.makedirs(folder)
        with self._lock:
            handle = self._sftp_call("open", path, "wb")
            try:
                handle.write(data)
            finally:
                handle.close()

    # ── local cache ──────────────────────────────────────────────────────────
    def _cache_path(self, path: str) -> Path:
        try:
            attr = self._sftp_call("stat", path)
            stamp = f"{attr.st_size}-{int(attr.st_mtime or 0)}"
        except IOError:
            stamp = "0-0"
        digest = hashlib.sha1(f"{path}|{stamp}".encode()).hexdigest()[:16]
        return self._cache / f"{digest}-{posixpath.basename(path)}"

    def _drop_cached(self, path: str) -> None:
        for stale in self._cache.glob(f"*-{posixpath.basename(path)}"):
            try:
                stale.unlink()
            except OSError:
                pass

    def fetch(self, path: str) -> Path:
        local = self._cache_path(path)
        if not local.exists():
            tmp = local.with_suffix(local.suffix + ".part")
            with self._lock:
                self._sftp_call("get", path, str(tmp))
            tmp.replace(local)
        return local
