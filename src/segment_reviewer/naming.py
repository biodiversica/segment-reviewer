"""Filename conventions shared with Step 5 of the vector-search notebooks.

Extracted clips are named ``SITE_YYYYMMDD_HHMMSS_START-ENDs_SCORE_LABEL.wav``.
Everything this module does is a port of the parsing/renaming helpers in the
notebook's Step 6 cell, so a folder reviewed here and a folder reviewed in Colab
end up with byte-identical names.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

# Similarity score is the last _<number>_ token before the label; the greedy
# prefix forces the match onto it even if other decimals appear earlier.
_SCORE_RE = re.compile(r".*_(\d+\.\d+)_(.+)$")
# The site itself may contain underscores, so anchor on the fixed date/time
# tokens instead of splitting blindly.
_HEAD_RE = re.compile(r"(.+)_(\d{8})_(\d{6})_([\d.]+)-([\d.]+)s_")
_RENAME_RE = re.compile(r"(.*_\d+\.\d+)_.+$")


@dataclass(frozen=True)
class SegmentName:
    """What a clip's file name says about it."""

    label: str
    score: float | None = None
    site: str | None = None
    recorded_at: datetime | None = None
    det_start: float | None = None
    det_end: float | None = None


def parse(path: str) -> SegmentName:
    """Read label, score, site, timestamp and detection window off a file name."""
    stem = posixpath.splitext(posixpath.basename(path.replace("\\", "/")))[0]

    m = _SCORE_RE.search(stem)
    label = m.group(2).replace("_", " ") if m else stem
    score = float(m.group(1)) if m else None

    site = recorded_at = det_start = det_end = None
    m2 = _HEAD_RE.match(stem)
    if m2:
        site = m2.group(1).replace("_", " ")
        try:
            recorded_at = datetime.strptime(m2.group(2) + m2.group(3), "%Y%m%d%H%M%S")
        except ValueError:
            recorded_at = None
        try:
            det_start, det_end = float(m2.group(4)), float(m2.group(5))
        except ValueError:
            det_start = det_end = None

    return SegmentName(label, score, site, recorded_at, det_start, det_end)


def name_with_labels(filename: str, labels: list[str]) -> str:
    """Rewrite a segment file name so it carries the labels chosen in review.

    The label the model proposed is dropped and every label the reviewer settled
    on is appended in its place, so a corrected segment ends as
    ``..._CONF_TURDRU.wav`` and one with two labels as
    ``..._CONF_BOAALB_PHYLUT.wav``. A name that does not follow the pattern is
    returned unchanged.
    """
    stem, ext = posixpath.splitext(filename)
    m = _RENAME_RE.match(stem)
    safe = [slug(x) for x in labels if str(x).strip()]
    if not m or not safe:
        return filename
    return m.group(1) + "".join("_" + s for s in safe) + ext


def slug(label: str) -> str:
    """Label as it is written into a file or folder name."""
    return str(label).strip().replace(" ", "_").replace("/", "-")


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

    Drive (and some SFTP servers) hand a file name back with its accents either
    composed (NFC) or decomposed (NFD), so ``POÇA_....wav`` written by Step 5
    need not compare equal to the very same name read back here. Matching on the
    accent-stripped, lower-cased form makes both spellings meet.
    """
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.encode("ascii", "ignore").decode("ascii").lower()


def nfc(value: object) -> str:
    """Compose accents, so one site or label never reads as two values downstream."""
    return unicodedata.normalize("NFC", str(value or ""))
