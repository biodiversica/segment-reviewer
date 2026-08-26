"""Storage backends for the segments folder."""

from __future__ import annotations

from .base import Backend
from .local import LocalBackend
from .sftp import SFTPBackend, SSHTarget, parse_ssh_spec

__all__ = [
    "Backend",
    "LocalBackend",
    "SFTPBackend",
    "SSHTarget",
    "parse_ssh_spec",
    "open_backend",
]


def open_backend(
    spec: str,
    *,
    ssh_user: str | None = None,
    ssh_port: int | None = None,
    ssh_key: str | None = None,
    ssh_password: str | None = None,
    known_hosts: str | None = None,
    accept_new_host_key: bool = False,
    cache_dir: str | None = None,
    use_ssh_config: bool = True,
) -> Backend:
    """Open the segments folder, locally or over SSH depending on *spec*."""
    target = parse_ssh_spec(spec)
    if target is None:
        return LocalBackend(spec)
    if ssh_user:
        target.user = ssh_user
    if ssh_port:
        target.port = ssh_port
    if use_ssh_config:
        target.apply_ssh_config()
    if ssh_key:
        target.key_filename = ssh_key
    if ssh_password:
        target.password = ssh_password
    target.known_hosts = known_hosts
    target.accept_new_host_key = accept_new_host_key
    return SFTPBackend(target, cache_dir=cache_dir)
