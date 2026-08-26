"""The annotation table written as each verdict is given.

One row per label: ``site, file, label, start_time, end_time``, where *file* is
the original recording the segment was cut from and the times are the segment's
position inside it (padding included). Rows are appended as they happen, so a
lost session keeps what was already reviewed.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from .config import ANNOTATION_COLUMNS, SOURCES_CSV
from .naming import nfc, source_key
from .storage import Backend


@dataclass
class AnnotationState:
    """What the status line under the buttons reports."""

    rows: int = 0
    rows_without_recording: int = 0
    error: str = ""
    have_sources: bool = False
    path: str = ""
    enabled: bool = False
    extra: dict = field(default_factory=dict)


class AnnotationTable:
    """Appends reviewed segments to a CSV, resolving their source recording."""

    def __init__(self, backend: Backend, path: str, *, enabled: bool) -> None:
        self.backend = backend
        self.path = path
        self.state = AnnotationState(path=path, enabled=enabled)
        self._sources: dict[str, str] = {}
        if enabled and not path:
            self.state.enabled = False
            self.state.extra["no_path"] = True
        elif enabled:
            self._load_sources()

    @property
    def enabled(self) -> bool:
        return self.state.enabled

    def _load_sources(self) -> None:
        """Read the manifest Step 5 wrote, mapping each clip to its recording.

        A clip's file name does not carry the recording it came from, so without
        this manifest the ``file`` column stays empty.
        """
        csv_path = self.backend.join(self.backend.root, SOURCES_CSV)
        try:
            text = self.backend.read_text(csv_path)
        except Exception as exc:  # noqa: BLE001
            self.state.error = str(exc)
            self.state.extra["read_error"] = str(exc)
            return
        if text is None:
            return
        try:
            for row in csv.DictReader(io.StringIO(text)):
                if row.get("segment"):
                    self._sources[source_key(row["segment"])] = row.get("recording", "")
        except Exception as exc:  # noqa: BLE001
            self.state.extra["read_error"] = str(exc)
            return
        self.state.have_sources = bool(self._sources)

    def recording_for(self, filename: str) -> str:
        return self._sources.get(source_key(filename), "")

    def append(self, site: str | None, recording: str, label: str,
               start_s: float | None, end_s: float | None) -> None:
        """Write one row, creating the table with its header when new."""
        if not self.enabled:
            return
        row = [
            nfc(site),
            recording or "",
            nfc(label),
            "" if start_s is None else f"{start_s:.3f}",
            "" if end_s is None else f"{end_s:.3f}",
        ]
        self.backend.append_csv_row(self.path, row, ANNOTATION_COLUMNS)
        self.state.rows += 1
        if not recording:
            self.state.rows_without_recording += 1


def segment_bounds(duration: float | None, det_start: float | None,
                   det_end: float | None) -> tuple[float | None, float | None]:
    """Start and end of a segment within its source recording, in seconds.

    The filename carries the detection window, but the clip on disk may be wider
    because of the padding used in Step 5. The difference between the clip's real
    duration and that window is split evenly over both sides, which reproduces how
    the extraction cell cut it (clamped at the start of the recording). Falls back
    to the filename window when the clip cannot be measured.
    """
    if det_start is None or det_end is None:
        return None, None
    if duration is None:
        return det_start, det_end
    start = max(0.0, det_start - (duration - (det_end - det_start)) / 2.0)
    return start, start + duration
