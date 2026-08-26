import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from segment_reviewer.config import ReviewConfig  # noqa: E402
from segment_reviewer.review import ReviewSession  # noqa: E402
from segment_reviewer.storage import LocalBackend  # noqa: E402


def write_wav(path: Path, seconds: float = 0.5, sr: int = 22050) -> None:
    """A short silent WAV, written without an audio stack.

    Tests that only exercise bookkeeping do not need one; the few that decode
    audio go through librosa on these same files.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sr)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(sr)
        fh.writeframes(struct.pack(f"<{frames}h", *([0] * frames)))


#: Default convention: the label is the folder, the name carries site and times.
DEFAULT_LAYOUT = [
    ("PONTO_A/BOAALB", "PONTO_A_20240115_053000_12.0_17.0_det1.wav"),
    ("PONTO_A/PHYLUT", "PONTO_A_20240115_061500_3.5_8.5_det2.wav"),
    ("POCA/BOAALB", "POCA_20240116_190000_40.0_45.0_det3.wav"),
]

#: What the bioacoustic vector-search notebooks write: label and score in the name.
VECTOR_SEARCH_LAYOUT = [
    ("PONTO_A/BOAALB", "PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav"),
    ("PONTO_A/PHYLUT", "PONTO_A_20240115_061500_3.5-8.5s_0.712_PHYLUT.wav"),
    ("POCA/BOAALB", "POCA_20240116_190000_40.0-45.0s_0.655_BOAALB.wav"),
]


def build_folder(root: Path, layout, manifest_for=(0,)) -> Path:
    """Write a segments folder, and a source manifest naming some of the clips."""
    for folder, name in layout:
        write_wav(root / folder / name)
    rows = "".join(
        f"{layout[i][1]},{layout[i][1].split('_20')[0]}_20240115_053000.wav\n"
        for i in manifest_for
    )
    (root / "segment_sources.csv").write_text("segment,recording\n" + rows, encoding="utf-8")
    return root


@pytest.fixture
def segments_dir(tmp_path):
    return build_folder(tmp_path / "segments", DEFAULT_LAYOUT)


@pytest.fixture
def vector_search_dir(tmp_path):
    return build_folder(tmp_path / "vs_segments", VECTOR_SEARCH_LAYOUT)


def make_session(root, **kwargs) -> ReviewSession:
    config = ReviewConfig(segments=str(root), **kwargs)
    return ReviewSession(LocalBackend(str(root)), config)


def goto_name(session: ReviewSession, needle: str) -> None:
    """Put the segment whose path contains *needle* on screen."""
    for i, path in enumerate(session.segments):
        if needle in path:
            session.goto(i)
            return
    raise AssertionError(f"no pending segment matching {needle!r}")


@pytest.fixture
def session(segments_dir):
    return make_session(segments_dir)
