"""Reading a segment's metadata off its folder and its file name.

Two independent sources:

* **The folder** the clip sits in gives its **label**. A reviewed collection is
  normally organised one folder per class — ``.../PONTO_A/BOAALB/clip.wav`` — so
  the folder immediately above the file is the label the clip currently carries.
* **The file name** gives the recording site, when it was recorded, and the
  position of the clip inside that recording. The default pattern is
  ``[site]_[YYYYMMDD]_[HHMMSS]_[start]_[end]_*``; anything else is left alone and
  the clip is still reviewable, just with less shown about it.

Both are configurable: ``--label-from`` chooses the label source and
``--filename-pattern`` the regular expression, so a collection named by any other
convention can be read by giving a pattern with the named groups it uses.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

#: Groups a filename pattern may capture. Every one of them is optional.
PATTERN_GROUPS = ("site", "date", "time", "datetime", "start", "end", "label", "score", "extra")

#: ``[site]_[YYYYMMDD]_[HHMMSS]_[start]_[end]_*`` — the default.
#: The site may itself contain underscores, so the match is anchored on the fixed
#: date and time tokens rather than split blindly. Start/end accept either
#: separator (``12.0_17.0`` and ``12.0-17.0s``) and may be absent altogether.
DEFAULT_PATTERN = (
    r"^(?P<site>.+)_(?P<date>\d{8})_(?P<time>\d{6})"
    r"(?:_(?P<start>\d+(?:\.\d+)?)[_-](?P<end>\d+(?:\.\d+)?)s?)?"
    r"(?:_(?P<extra>.*))?$"
)

#: ``SITE_YYYYMMDD_HHMMSS_START-ENDs_SCORE_LABEL`` — what the bioacoustic
#: vector-search notebooks write, where the label and score live in the name.
#: Two expressions, because a name may carry the score and label without the
#: site/date prefix; the groups found by each are merged.
VECTOR_SEARCH_PATTERNS = (
    r"^(?P<site>.+)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<start>[\d.]+)-(?P<end>[\d.]+)s_",
    # The score is the last _<number>_ token before the label; the greedy prefix
    # forces the match onto it even if other decimals appear earlier.
    r".*_(?P<score>\d+\.\d+)_(?P<label>.+)$",
)

PRESETS: dict[str, tuple[str, ...]] = {
    "default": (DEFAULT_PATTERN,),
    "vector-search": VECTOR_SEARCH_PATTERNS,
}

#: Where a segment's label is read from.
LABEL_SOURCES = ("folder", "filename", "none")

DEFAULT_DATETIME_FORMAT = "%Y%m%d%H%M%S"


@dataclass(frozen=True)
class SegmentName:
    """What a clip's folder and file name say about it."""

    label: str = ""
    site: str | None = None
    recorded_at: datetime | None = None
    det_start: float | None = None
    det_end: float | None = None
    score: float | None = None
    extra: str | None = None
    #: Folders between the segments root and the clip, outermost first. In
    #: folder mode the last one is the label and is not repeated here.
    prefix: tuple[str, ...] = field(default_factory=tuple)
    #: True when the label was captured from the file name rather than a folder.
    label_in_filename: bool = False


class SegmentParser:
    """Reads segment metadata according to the configured conventions."""

    def __init__(
        self,
        pattern: str | tuple[str, ...] = "default",
        label_from: str = "folder",
        datetime_format: str = DEFAULT_DATETIME_FORMAT,
    ) -> None:
        if label_from not in LABEL_SOURCES:
            raise ValueError(f"label_from must be one of {LABEL_SOURCES}, not {label_from!r}")
        self.label_from = label_from
        self.datetime_format = datetime_format
        self.pattern_name = pattern if isinstance(pattern, str) and pattern in PRESETS else "custom"
        raw = PRESETS.get(pattern, pattern) if isinstance(pattern, str) else pattern
        if isinstance(raw, str):
            raw = (raw,)
        self.patterns = tuple(raw)
        self.regexes = tuple(re.compile(p) for p in self.patterns)

    # ── reading ──────────────────────────────────────────────────────────────
    def parse(self, path: str, root: str = "") -> SegmentName:
        """Everything known about the clip at *path*, relative to the segments *root*."""
        posix = path.replace("\\", "/")
        stem = posixpath.splitext(posixpath.basename(posix))[0]
        folders = self._folders(posix, root)
        found = self._match_groups(stem)

        label, in_filename, prefix = self._resolve_label(found.get("label"), folders)
        return SegmentName(
            label=label,
            site=self._clean(found.get("site")),
            recorded_at=self._to_datetime(found),
            det_start=self._to_float(found.get("start")),
            det_end=self._to_float(found.get("end")),
            score=self._to_float(found.get("score")),
            extra=found.get("extra") or None,
            prefix=prefix,
            label_in_filename=in_filename,
        )

    def _match_groups(self, stem: str) -> dict[str, str]:
        """Groups captured by the pattern(s); later ones only fill what is missing."""
        found: dict[str, str] = {}
        for regex in self.regexes:
            match = regex.search(stem)
            if not match:
                continue
            for name, value in match.groupdict().items():
                if value is not None and found.get(name) is None:
                    found[name] = value
        return found

    @staticmethod
    def _folders(posix_path: str, root: str) -> tuple[str, ...]:
        """Folders between *root* and the clip, outermost first."""
        if not root:
            return ()
        root = root.replace("\\", "/").rstrip("/")
        directory = posixpath.dirname(posix_path)
        if not directory.startswith(root):
            return ()
        rel = directory[len(root):].strip("/")
        return tuple(part for part in rel.split("/") if part) if rel else ()

    def _resolve_label(
        self, from_name: str | None, folders: tuple[str, ...]
    ) -> tuple[str, bool, tuple[str, ...]]:
        """Label, whether it came from the file name, and the folders above it."""
        if self.label_from == "filename":
            return (self._clean(from_name) or ""), bool(from_name), folders
        if self.label_from == "folder" and folders:
            return self._clean(folders[-1]) or "", False, folders[:-1]
        return "", False, folders

    def _to_datetime(self, found: dict[str, str]) -> datetime | None:
        stamp = found.get("datetime") or f"{found.get('date', '')}{found.get('time', '')}"
        if not stamp:
            return None
        try:
            return datetime.strptime(stamp, self.datetime_format)
        except ValueError:
            return None

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        try:
            return float(value) if value else None
        except ValueError:
            return None

    @staticmethod
    def _clean(value: str | None) -> str | None:
        """Underscores in a captured name stand in for spaces."""
        return nfc(value).replace("_", " ").strip() if value else None

    # ── writing ──────────────────────────────────────────────────────────────
    def replace_label(self, filename: str, labels: list[str]) -> str:
        """Rewrite a file name so it carries the labels the reviewer settled on.

        Only meaningful when the pattern captures a ``label`` group: the span it
        matched is replaced, so a segment corrected to ``TURDRU`` is saved as
        ``..._TURDRU.wav`` and one given two labels as ``..._BOAALB_PHYLUT.wav``.
        A name whose pattern carries no label is returned unchanged — there the
        label lives in the folder, and the file name is left as extraction wrote it.
        """
        stem, ext = posixpath.splitext(filename)
        safe = [slug(x) for x in labels if str(x).strip()]
        if not safe:
            return filename
        for regex in self.regexes:
            match = regex.search(stem)
            if not match or "label" not in (match.groupdict() or {}):
                continue
            if match.group("label") is None:
                continue
            start, end = match.span("label")
            return stem[:start] + "_".join(safe) + stem[end:] + ext
        return filename


def slug(label: str) -> str:
    """Label as it is written into a file or folder name."""
    return str(label).strip().replace(" ", "_").replace("/", "-").replace("\\", "-")


def split_labels(text: str, fallback: str = "") -> list[str]:
    """Split a comma-separated label box into a clean list, keeping the order."""
    out: list[str] = []
    for part in str(text or "").split(","):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out or ([fallback] if fallback else [])


def source_key(name: str) -> str:
    """Manifest lookup key for a clip, immune to how a filesystem spells accents.

    Some filesystems and transports hand a name back with its accents composed
    (NFC) and others decomposed (NFD), so ``POÇA_....wav`` as written need not
    compare equal to the very same name read back. Matching on the
    accent-stripped, lower-cased form makes both spellings meet.
    """
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.encode("ascii", "ignore").decode("ascii").lower()


def nfc(value: object) -> str:
    """Compose accents, so one site or label never reads as two values downstream."""
    return unicodedata.normalize("NFC", str(value or ""))
