import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from segment_reviewer.config import ReviewConfig  # noqa: E402
from segment_reviewer.review import ReviewSession  # noqa: E402
from segment_reviewer.storage import LocalBackend  # noqa: E402

# A 0.5 s, 22.05 kHz mono WAV header + silence, written without soundfile so the
# tests that only exercise bookkeeping do not need an audio stack.
def write_wav(path: Path, seconds: float = 0.5, sr: int = 22050) -> None:
    import struct
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sr)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sr)
        fh.writeframes(struct.pack(f"<{frames}h", *([0] * frames)))


@pytest.fixture
def segments_dir(tmp_path):
    root = tmp_path / "segments"
    write_wav(root / "PONTO_A" / "BOAALB" / "PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav")
    write_wav(root / "PONTO_A" / "PHYLUT" / "PONTO_A_20240115_061500_3.5-8.5s_0.712_PHYLUT.wav")
    write_wav(root / "POCA" / "BOAALB" / "POCA_20240116_190000_40.0-45.0s_0.655_BOAALB.wav")
    (root / "segment_sources.csv").write_text(
        "segment,recording\n"
        "PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav,PONTO_A_20240115_053000.wav\n",
        encoding="utf-8",
    )
    return root


def make_session(root, **kwargs) -> ReviewSession:
    config = ReviewConfig(segments=str(root), **kwargs)
    return ReviewSession(LocalBackend(str(root)), config)


def goto_name(session: ReviewSession, needle: str) -> None:
    """Put the segment whose file name contains *needle* on screen."""
    for i, path in enumerate(session.segments):
        if needle in path:
            session.goto(i)
            return
    raise AssertionError(f"no pending segment matching {needle!r}")


@pytest.fixture
def session(segments_dir):
    return make_session(segments_dir)
