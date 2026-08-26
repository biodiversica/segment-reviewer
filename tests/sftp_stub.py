"""A throwaway in-process SFTP server, so the SSH backend is tested for real.

Serves one temporary directory over a real socket with password auth. Modelled on
paramiko's own stub server demo; it exists only for the test suite.
"""

from __future__ import annotations

import os
import socket
import threading

import paramiko


class _Handle(paramiko.SFTPHandle):
    def stat(self):
        try:
            return paramiko.SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def chattr(self, attr):
        return paramiko.SFTP_OK


def _make_sftp_interface(root: str):
    class _Interface(paramiko.SFTPServerInterface):
        ROOT = root

        def _real(self, path: str) -> str:
            path = os.path.normpath("/" + path.replace("\\", "/")).lstrip("/")
            return os.path.join(self.ROOT, path)

        def _canon(self, path: str) -> str:
            return "/" + os.path.relpath(path, self.ROOT).replace(os.sep, "/").lstrip("./")

        def list_folder(self, path):
            real = self._real(path)
            try:
                out = []
                for name in os.listdir(real):
                    attr = paramiko.SFTPAttributes.from_stat(os.stat(os.path.join(real, name)))
                    attr.filename = name
                    out.append(attr)
                return out
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)

        def stat(self, path):
            try:
                return paramiko.SFTPAttributes.from_stat(os.stat(self._real(path)))
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)

        lstat = stat

        def open(self, path, flags, attr):
            real = self._real(path)
            try:
                fd = os.open(real, flags, getattr(attr, "st_mode", None) or 0o666)
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
            if flags & os.O_WRONLY:
                mode = "ab" if flags & os.O_APPEND else "wb"
            elif flags & os.O_RDWR:
                mode = "a+b" if flags & os.O_APPEND else "r+b"
            else:
                mode = "rb"
            try:
                fobj = os.fdopen(fd, mode)
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
            handle = _Handle(flags)
            handle.filename = real
            handle.readfile = handle.writefile = fobj
            return handle

        def remove(self, path):
            try:
                os.remove(self._real(path))
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
            return paramiko.SFTP_OK

        def rename(self, oldpath, newpath):
            try:
                os.rename(self._real(oldpath), self._real(newpath))
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
            return paramiko.SFTP_OK

        def posix_rename(self, oldpath, newpath):
            return self.rename(oldpath, newpath)

        def mkdir(self, path, attr):
            try:
                os.mkdir(self._real(path))
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
            return paramiko.SFTP_OK

        def rmdir(self, path):
            try:
                os.rmdir(self._real(path))
            except OSError as exc:
                return paramiko.SFTPServer.convert_errno(exc.errno)
            return paramiko.SFTP_OK

        def chattr(self, path, attr):
            return paramiko.SFTP_OK

        def canonicalize(self, path):
            real = os.path.abspath(self._real(path))
            return self._canon(real) if real.startswith(self.ROOT) else "/"

    return _Interface


class _Server(paramiko.ServerInterface):
    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED


class SFTPTestServer:
    """Start with ``with SFTPTestServer(root) as server: server.port``."""

    def __init__(self, root: str) -> None:
        self.root = os.path.realpath(root)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self._key = paramiko.RSAKey.generate(2048)
        self._transports: list[paramiko.Transport] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        interface = _make_sftp_interface(self.root)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            transport = paramiko.Transport(conn)
            transport.add_server_key(self._key)
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, interface)
            try:
                transport.start_server(server=_Server())
            except Exception:
                continue
            self._transports.append(transport)

    def __enter__(self) -> "SFTPTestServer":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        for transport in self._transports:
            try:
                transport.close()
            except Exception:
                pass
        self._sock.close()
