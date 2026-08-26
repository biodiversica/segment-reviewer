"""The review session: which segment is on screen, and what a verdict does to it."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from .annotations import AnnotationTable, segment_bounds
from .config import ALL_VERDICT_DIR_NAMES, ReviewConfig
from .labels import LabelStore
from .naming import SegmentParser, nfc, slug, split_labels
from .spectrogram import SpectrogramError, duration_seconds, render
from .storage import Backend


@dataclass
class SegmentView:
    """What the browser is told about the segment on screen."""

    index: int
    total: int
    name: str
    relpath: str
    #: Folders between the segments root and the clip, as one path.
    folder: str
    label: str
    #: Where that label came from: "folder", "filename" or "" when it has none.
    label_from: str
    site: str | None
    recorded_at: str | None
    det_start: float | None
    det_end: float | None
    score: float | None
    extra: str | None


class ReviewSession:
    """Holds the pending list and applies verdicts to it.

    One session per running server: the reviewer is a single person walking a
    folder, and every mutation is serialised behind one lock so a double-click
    cannot file the same clip twice.
    """

    def __init__(self, backend: Backend, config: ReviewConfig) -> None:
        self.backend = backend
        self.config = config
        self.dirs = config.resolved_verdict_dirs()
        self.parser = SegmentParser(
            pattern=config.filename_pattern,
            label_from=config.label_from,
            datetime_format=config.datetime_format,
        )
        self._lock = threading.RLock()
        self._ensure_dirs()
        self.annotations = AnnotationTable(
            backend,
            self._annotations_path(),
            enabled=config.save_annotations,
        )
        self.segments: list[str] = []
        self.index = 0
        self._reviewed: dict[str, int] = {k: 0 for k in self.dirs}
        self.rescan()
        self.labels = LabelStore(
            backend,
            backend.resolve(config.labels_file) if config.labels_file else "",
            configured=config.labels,
            discovered=self.discovered_labels(),
            persist=config.persist_labels,
        )

    # ── setup ────────────────────────────────────────────────────────────────
    def _ensure_dirs(self) -> None:
        wanted = [self.dirs["true"], self.dirs["false"]]
        if self.config.multi_label:
            wanted.append(self.dirs["multi"])
        for name in wanted:
            self.backend.makedirs(self.backend.join(self.backend.root, name))

    def _annotations_path(self) -> str:
        if not self.config.save_annotations:
            return self.backend.resolve(self.config.annotations_path)
        raw = self.config.annotations_path.strip()
        if not raw:
            raw = "annotations.csv"
        return self.backend.resolve(raw)

    # ── the pending list ─────────────────────────────────────────────────────
    def _skip_roots(self) -> list[str]:
        """Folders excluded from review — every verdict name, in any language."""
        names = set(ALL_VERDICT_DIR_NAMES) | set(self.dirs.values())
        return [self.backend.join(self.backend.root, name) for name in sorted(names)]

    def collect(self) -> list[str]:
        skip = self._skip_roots()
        return [
            path
            for path in self.backend.walk_wavs(self.backend.root)
            if not any(self.backend.is_inside(path, root) for root in skip)
        ]

    def rescan(self) -> None:
        with self._lock:
            current = self.segments[self.index] if 0 <= self.index < len(self.segments) else None
            self.segments = self.collect()
            self.index = self.segments.index(current) if current in self.segments else 0
            self.index = max(0, min(self.index, max(0, len(self.segments) - 1)))
            self._reviewed = self._count_reviewed()

    def _count_reviewed(self) -> dict[str, int]:
        """Walk the verdict folders once. Over SFTP this is the expensive call."""
        done = {}
        for key, name in self.dirs.items():
            folder = self.backend.join(self.backend.root, name)
            done[key] = len(self.backend.walk_wavs(folder)) if self.backend.isdir(folder) else 0
        return done

    def counts(self) -> dict[str, int]:
        """Pending and reviewed totals.

        The reviewed tallies are taken at rescan and then kept up to date by each
        verdict, rather than re-walking three folders on every request the browser
        makes — a recount over SFTP costs a full remote listing.
        """
        with self._lock:
            return {**self._reviewed, "pending": len(self.segments)}

    # ── the segment on screen ────────────────────────────────────────────────
    def path_at(self, index: int) -> str:
        with self._lock:
            if not self.segments:
                raise IndexError("no segments pending review")
            if not 0 <= index < len(self.segments):
                raise IndexError(f"segment {index} is out of range")
            return self.segments[index]

    def view(self) -> SegmentView | None:
        with self._lock:
            if not self.segments:
                return None
            path = self.segments[self.index]
            info = self._parse(path)
            relpath = self.backend.relpath(path, self.backend.root)
            folder = self.backend.dirname(relpath).replace(self.backend.sep, "/")
            return SegmentView(
                index=self.index,
                total=len(self.segments),
                name=self.backend.basename(path),
                relpath=relpath.replace(self.backend.sep, "/"),
                folder=folder,
                label=info.label,
                label_from=("filename" if info.label_in_filename
                            else ("folder" if info.label else "")),
                site=info.site,
                recorded_at=info.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if info.recorded_at else None,
                det_start=info.det_start,
                det_end=info.det_end,
                score=info.score,
                extra=info.extra,
            )

    def navigate(self, delta: int) -> None:
        with self._lock:
            if not self.segments:
                return
            self.index = max(0, min(len(self.segments) - 1, self.index + delta))

    def goto(self, index: int) -> None:
        with self._lock:
            if self.segments:
                self.index = max(0, min(len(self.segments) - 1, index))

    def _parse(self, path: str):
        return self.parser.parse(path, self.backend.root)

    # ── labels offered in the reviewer ───────────────────────────────────────
    def discovered_labels(self) -> list[str]:
        """Every label the pending clips already carry, in alphabetical order.

        The folder names in folder mode, the labels in the file names in filename
        mode. Used to seed the label list the first time a collection is opened.
        """
        with self._lock:
            pending = list(self.segments)
        return sorted({
            nfc(info.label).strip()
            for info in map(self._parse, pending)
            if str(info.label).strip()
        })

    def label_choices(self) -> list[str]:
        """The labels offered as buttons in the reviewer."""
        return self.labels.labels

    # ── verdicts ─────────────────────────────────────────────────────────────
    def _destination_dir(self, info, verdict: str, final: list[str]) -> str:
        """Where a segment goes once a verdict is given.

        A clip carrying several labels belongs to no single true/false folder, so
        it goes to the multi folder either way. Beyond that the layout follows
        where the label lives:

        * **Label in a folder** (the default) — the clip keeps the path it had,
          with its label folder swapped for the one the reviewer confirmed:
          ``PONTO_A/BOAALB/x.wav`` accepted stays ``true/PONTO_A/BOAALB/x.wav``,
          and corrected to TURDRU becomes ``false/PONTO_A/TURDRU/x.wav``. Nothing
          about the clip's place in the collection is lost by reviewing it.
        * **Label in the file name** — the name already carries the verdict's
          label, so the clip is filed flat under the verdict folder, with one
          subfolder per label for rejections.
        """
        bucket = "multi" if len(final) > 1 else verdict
        verdict_root = self.backend.join(self.backend.root, self.dirs[bucket])

        if info.label_in_filename:
            if bucket == "false" and final:
                return self.backend.join(verdict_root, slug(final[0]))
            return verdict_root

        # The folders above the label are kept exactly as they are on disk; only
        # the label the reviewer typed is made safe for a file name.
        parts = list(info.prefix)
        label_folder = "_".join(slug(x) for x in final if str(x).strip())
        if label_folder:
            parts.append(label_folder)
        return self.backend.join(verdict_root, *parts) if parts else verdict_root

    def apply_verdict(self, verdict: str, labels: list[str] | None = None) -> dict:
        """File the current segment under its verdict and drop it from the list."""
        if verdict not in ("true", "false"):
            raise ValueError(f"unknown verdict: {verdict}")
        with self._lock:
            if not self.segments:
                return {"moved": None}
            src = self.segments.pop(self.index)
            info = self._parse(src)
            final = [x for x in (labels or []) if str(x).strip()]
            if not final and info.label:
                final = [info.label]

            # Read the clip before moving it: it has to be on disk to be measured.
            start_s = end_s = None
            if self.annotations.enabled:
                duration = None
                try:
                    duration = duration_seconds(self.backend.fetch(src))
                except Exception:  # noqa: BLE001 - fall back to the filename window
                    duration = None
                start_s, end_s = segment_bounds(duration, info.det_start, info.det_end)

            folder = self._destination_dir(info, verdict, final)
            self.backend.makedirs(folder)
            # Only a name that carries its own label is rewritten; where the label
            # lives in the folder the file name is left exactly as it was found.
            filename = self.parser.replace_label(self.backend.basename(src), final)
            dest = self.backend.free_path(folder, filename)
            try:
                self.backend.move(src, dest)
            except Exception:
                self.segments.insert(self.index, src)  # put it back, nothing happened
                raise

            if self.annotations.enabled:
                recording = self.annotations.recording_for(self.backend.basename(src))
                try:
                    # One row per label: a segment holding two species produces two
                    # rows sharing the same recording, times and site.
                    for one in final:
                        self.annotations.append(info.site, recording, one, start_s, end_s)
                except Exception as exc:  # noqa: BLE001
                    self.annotations.state.error = str(exc)

            bucket = "multi" if len(final) > 1 else verdict
            self._reviewed[bucket] = self._reviewed.get(bucket, 0) + 1

            if self.index >= len(self.segments) and self.index > 0:
                self.index -= 1
            return {"moved": self.backend.relpath(dest, self.backend.root)}

    # ── media ────────────────────────────────────────────────────────────────
    def spectrogram(self, index: int, *, spec_type: str, fmin: int, fmax: int,
                    db_min: int) -> bytes:
        path = self.path_at(index)
        local: Path = self.backend.fetch(path)
        return render(
            local, spec_type=spec_type, fmin_hz=fmin, fmax_hz=fmax, db_min=db_min
        )

    def audio_bytes(self, index: int) -> tuple[bytes, str]:
        path = self.path_at(index)
        return self.backend.read_bytes(path), self.backend.basename(path)

    # ── helpers used by the API layer ────────────────────────────────────────
    @staticmethod
    def parse_labels(text: str, fallback: str = "") -> list[str]:
        return split_labels(text, fallback)


__all__ = ["ReviewSession", "SegmentView", "SpectrogramError"]
