"""The list of labels the reviewer offers, and where it is kept.

Seeded on first run from the labels the collection already uses, then stored as
one label per line in a text file beside the segments, so a list built up while
reviewing survives a restart — and, for a remote folder, is shared by whoever
opens it next. Once that file exists it *is* the list: the reviewer edits it from
the GUI, and nothing is added back behind their back.

``--labels`` overrides both: naming labels on the command line is an explicit
choice of what to offer, so those are the whole list the session starts with,
replacing anything stored, and are written out in turn.

A clip's own label and anything typed into the box are always available whether
or not they are on the list, so a trimmed list never blocks a verdict.
"""

from __future__ import annotations

from .naming import nfc
from .storage import Backend


def merge(*groups) -> list[str]:
    """One list out of several, keeping the first order and dropping repeats."""
    out: list[str] = []
    for group in groups:
        for raw in group or ():
            label = nfc(raw).strip()
            if label and label not in out:
                out.append(label)
    return out


class LabelStore:
    """The offered labels, persisted through the storage backend."""

    def __init__(
        self,
        backend: Backend,
        path: str,
        *,
        configured=(),
        discovered=(),
        persist: bool = True,
    ) -> None:
        self.backend = backend
        self.path = path if persist else ""
        self.error = ""
        stored = self._read()
        asked_for = merge(configured)
        if asked_for:
            # Labels named on the command line are the list for this run: only
            # those are offered, whatever the collection uses or the file holds.
            self._labels = asked_for
            if self._labels != stored:
                self._save()
        elif stored is None:
            # First run: the labels the collection already uses.
            self._labels = merge(discovered)
            self._save()
        else:
            # From then on the file is the list.
            self._labels = stored

    # ── reading ──────────────────────────────────────────────────────────────
    @property
    def labels(self) -> list[str]:
        return list(self._labels)

    @property
    def persisted(self) -> bool:
        return bool(self.path) and not self.error

    def _read(self) -> list[str] | None:
        """The stored list, or None when there is nothing stored yet."""
        if not self.path:
            return None
        try:
            text = self.backend.read_text(self.path)
        except Exception as exc:  # noqa: BLE001 - reported, never fatal
            self.error = str(exc)
            return None
        if text is None:
            return None
        return merge(
            line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )

    # ── writing ──────────────────────────────────────────────────────────────
    def _save(self) -> None:
        """Write the list out. A folder that cannot be written to is not fatal."""
        if not self.path:
            return
        body = "".join(f"{label}\n" for label in self._labels)
        try:
            self.backend.write_bytes(self.path, body.encode("utf-8"))
            self.error = ""
        except Exception as exc:  # noqa: BLE001 - the session carries on in memory
            self.error = str(exc)

    def replace(self, labels) -> list[str]:
        """Set the whole list, as the GUI's label editor does."""
        self._labels = merge(labels)
        self._save()
        return self.labels

    def add(self, *labels) -> list[str]:
        """Append labels that are not on the list yet."""
        merged = merge(self._labels, labels)
        if merged != self._labels:
            self._labels = merged
            self._save()
        return self.labels

    def remove(self, *labels) -> list[str]:
        """Drop labels from the list. A clip's own label stays usable regardless."""
        drop = {nfc(x).strip() for x in labels}
        kept = [label for label in self._labels if label not in drop]
        if kept != self._labels:
            self._labels = kept
            self._save()
        return self.labels
