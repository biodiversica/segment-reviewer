import os

import pytest

from segment_reviewer.storage import LocalBackend, open_backend
from segment_reviewer.storage.sftp import parse_ssh_spec


@pytest.mark.parametrize(
    "spec, host, user, port, path",
    [
        ("ssh://host/data/seg", "host", None, None, "/data/seg"),
        ("ssh://user@host/data/seg", "host", "user", None, "/data/seg"),
        ("ssh://user@host:2222/data/seg", "host", "user", 2222, "/data/seg"),
        ("sftp://user@host/data", "host", "user", None, "/data"),
        ("host:/data/seg", "host", None, None, "/data/seg"),
        ("user@host:/data/seg", "host", "user", None, "/data/seg"),
        ("user@host:relative/seg", "host", "user", None, "relative/seg"),
    ],
)
def test_ssh_specs_are_recognised(spec, host, user, port, path):
    target = parse_ssh_spec(spec)
    assert target is not None
    assert (target.host, target.user, target.port, target.path) == (host, user, port, path)


@pytest.mark.parametrize("spec", ["/data/segments", "./segments", "~/segments", "segments"])
def test_local_paths_are_not_mistaken_for_ssh(spec):
    assert parse_ssh_spec(spec) is None


def test_open_backend_picks_local(tmp_path):
    backend = open_backend(str(tmp_path))
    assert isinstance(backend, LocalBackend)
    assert backend.root == str(tmp_path.resolve())


def test_free_path_suffixes_instead_of_overwriting(tmp_path):
    backend = LocalBackend(str(tmp_path))
    (tmp_path / "a.wav").write_bytes(b"")
    assert backend.free_path(str(tmp_path), "a.wav") == str(tmp_path / "a_2.wav")
    (tmp_path / "a_2.wav").write_bytes(b"")
    assert backend.free_path(str(tmp_path), "a.wav") == str(tmp_path / "a_3.wav")


def test_append_csv_row_creates_then_appends(tmp_path):
    backend = LocalBackend(str(tmp_path))
    path = os.path.join(str(tmp_path), "out.csv")
    backend.append_csv_row(path, ["a", "1"], ["name", "n"])
    backend.append_csv_row(path, ["b", "2"], ["name", "n"])
    assert open(path).read().splitlines() == ["name,n", "a,1", "b,2"]


def test_resolve_reads_relative_paths_against_the_root(tmp_path):
    backend = LocalBackend(str(tmp_path))
    assert backend.resolve("out.csv") == os.path.join(backend.root, "out.csv")
    assert backend.resolve("/tmp/out.csv") == "/tmp/out.csv"


def test_is_inside(tmp_path):
    backend = LocalBackend(str(tmp_path))
    root = backend.root
    assert backend.is_inside(os.path.join(root, "true", "x.wav"), os.path.join(root, "true"))
    assert not backend.is_inside(os.path.join(root, "trueish", "x.wav"),
                                 os.path.join(root, "true"))
