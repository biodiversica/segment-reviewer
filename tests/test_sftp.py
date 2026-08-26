"""End-to-end cover for the SSH backend, against a real (in-process) SFTP server."""

import csv

import pytest

from conftest import write_wav
from segment_reviewer.config import ReviewConfig
from segment_reviewer.review import ReviewSession
from segment_reviewer.storage import open_backend
from sftp_stub import SFTPTestServer


@pytest.fixture
def remote(segments_dir):
    with SFTPTestServer(str(segments_dir)) as server:
        backend = open_backend(
            f"ssh://tester@127.0.0.1:{server.port}/",
            ssh_password="anything",
            accept_new_host_key=True,
            use_ssh_config=False,
        )
        try:
            yield backend, segments_dir
        finally:
            backend.close()


def test_walk_finds_every_clip(remote):
    backend, _ = remote
    found = backend.walk_wavs(backend.root)
    assert len(found) == 3
    assert all(path.startswith("/") and path.endswith(".wav") for path in found)


def test_read_and_write(remote):
    backend, segments_dir = remote
    path = backend.join(backend.root, "segment_sources.csv")
    assert "PONTO_A_20240115_053000.wav" in backend.read_text(path)
    backend.write_bytes(backend.join(backend.root, "note.txt"), b"hello")
    assert (segments_dir / "note.txt").read_bytes() == b"hello"


def test_makedirs_creates_the_whole_chain(remote):
    backend, segments_dir = remote
    backend.makedirs(backend.join(backend.root, "a", "b", "c"))
    assert (segments_dir / "a" / "b" / "c").is_dir()


def test_fetch_caches_a_local_copy(remote):
    backend, _ = remote
    wav = backend.walk_wavs(backend.root)[0]
    first = backend.fetch(wav)
    assert first.exists() and first.stat().st_size > 0
    assert backend.fetch(wav) == first          # served from the cache
    assert first.read_bytes() == backend.read_bytes(wav)


def test_a_full_review_over_ssh(remote):
    backend, segments_dir = remote
    session = ReviewSession(backend, ReviewConfig(save_annotations=True))
    assert session.counts()["pending"] == 3

    session.apply_verdict("true")
    session.apply_verdict("false", ["TURDRU"])
    session.apply_verdict("true", ["BOAALB", "PHYLUT"])

    assert session.counts() == {"pending": 0, "true": 1, "false": 1, "multi": 1}
    assert len(list((segments_dir / "true").glob("*.wav"))) == 1
    assert len(list((segments_dir / "false" / "TURDRU").glob("*.wav"))) == 1
    assert len(list((segments_dir / "multi").glob("*.wav"))) == 1

    rows = list(csv.DictReader((segments_dir / "annotations.csv").open()))
    assert len(rows) == 4        # the multi-label clip contributes two rows
    assert session.view() is None


def test_rescan_picks_up_a_clip_added_remotely(remote):
    backend, segments_dir = remote
    session = ReviewSession(backend, ReviewConfig())
    write_wav(segments_dir / "NEW" / "N_20240101_000000_0.0-5.0s_0.5_XXX.wav")
    session.rescan()
    assert session.counts()["pending"] == 4
    assert "XXX" in session.label_choices()
