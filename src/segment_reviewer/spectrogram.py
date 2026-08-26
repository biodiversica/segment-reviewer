"""Spectrogram rendering.

Rendering goes through matplotlib's object API behind a lock rather than
``pyplot``: the server draws from a worker thread, and the pyplot state machine
is not safe to share.
"""

from __future__ import annotations

import io
import threading
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import librosa  # noqa: E402
import librosa.display  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

# A 1x1 transparent PNG, used whenever there is nothing to draw.
BLANK_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
    "0000000b4944415478da6364f8cf500f00038601805a347d6b0000000049454e44"
    "ae426082"
)

_RENDER_LOCK = threading.Lock()


class SpectrogramError(RuntimeError):
    """Raised when a clip cannot be read or drawn."""


def duration_seconds(path: str | Path) -> float:
    """Length of a clip in seconds."""
    try:
        return float(librosa.get_duration(path=str(path)))
    except TypeError:  # librosa < 0.10 named the argument filename=
        return float(librosa.get_duration(filename=str(path)))


def render(
    path: str | Path,
    *,
    spec_type: str = "mel",
    fmin_hz: int = 0,
    fmax_hz: int = 0,
    db_min: int = -80,
    width_in: float = 9.0,
    height_in: float = 4.0,
    dpi: int = 100,
) -> bytes:
    """Draw one clip as a PNG.

    ``fmax_hz`` of 0 means the Nyquist frequency of the clip.
    """
    try:
        y, sr = librosa.load(str(path), sr=None, mono=True)
    except Exception as exc:  # noqa: BLE001 - surfaced to the browser verbatim
        raise SpectrogramError(str(exc)) from exc

    fmax = fmax_hz if fmax_hz and fmax_hz > 0 else sr // 2
    fmin = max(0, min(fmin_hz, max(0, fmax - 1)))

    with _RENDER_LOCK:
        try:
            fig = Figure(figsize=(width_in, height_in))
            FigureCanvasAgg(fig)
            ax = fig.subplots()
            if spec_type == "mel":
                S = librosa.feature.melspectrogram(
                    y=y, sr=sr, n_mels=128, fmin=fmin, fmax=fmax
                )
                Sd = librosa.power_to_db(S, ref=np.max)
                img = librosa.display.specshow(
                    Sd, sr=sr, x_axis="time", y_axis="mel", ax=ax,
                    fmin=fmin, fmax=fmax, vmin=db_min, vmax=0,
                )
            else:
                D = librosa.stft(y)
                Sd = librosa.amplitude_to_db(np.abs(D), ref=np.max)
                img = librosa.display.specshow(
                    Sd, sr=sr, x_axis="time", y_axis="hz", ax=ax,
                    vmin=db_min, vmax=0,
                )
                ax.set_ylim(fmin, fmax)
            fig.colorbar(img, ax=ax, format="%+2.0f dB")
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
            return buf.getvalue()
        except Exception as exc:  # noqa: BLE001
            raise SpectrogramError(str(exc)) from exc
        finally:
            fig.clf()
