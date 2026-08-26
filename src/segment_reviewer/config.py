"""Everything the reviewer is configured with, in one place."""

from __future__ import annotations

from dataclasses import dataclass, field

#: Verdict folder names per interface language, matching what each notebook writes.
VERDICT_DIRS: dict[str, dict[str, str]] = {
    "en": {"true": "true", "false": "false", "multi": "multi"},
    "pt-BR": {"true": "verdadeiro", "false": "falso", "multi": "multi"},
}

#: Folders never offered for review, whichever language wrote them. A folder
#: reviewed in English is not handed back for review under a Portuguese session.
ALL_VERDICT_DIR_NAMES: set[str] = {
    name for mapping in VERDICT_DIRS.values() for name in mapping.values()
}

SOURCES_CSV = "segment_sources.csv"
ANNOTATION_COLUMNS = ["site", "file", "label", "start_time", "end_time"]


@dataclass
class ReviewConfig:
    """Settings the reviewer starts with.

    The spectrogram fields are only the *initial* values shown in the browser;
    they can be changed live without restarting. The rest is fixed for the run —
    switching the interface language in the browser deliberately does **not**
    rename the verdict folders, so a review split over two sessions files its
    clips in one consistent place.
    """

    segments: str = "."
    lang: str = "en"
    labels: list[str] = field(default_factory=list)
    multi_label: bool = False
    save_annotations: bool = False
    annotations_path: str = ""

    # Spectrogram defaults
    spec_type: str = "mel"
    freq_min_hz: int = 0
    freq_max_hz: int = 0  # 0 → Nyquist
    db_min: int = -80

    # Verdict folder names (resolved from `lang` when left empty)
    true_dir: str = ""
    false_dir: str = ""
    multi_dir: str = ""

    def resolved_verdict_dirs(self) -> dict[str, str]:
        defaults = VERDICT_DIRS.get(self.lang, VERDICT_DIRS["en"])
        return {
            "true": self.true_dir or defaults["true"],
            "false": self.false_dir or defaults["false"],
            "multi": self.multi_dir or defaults["multi"],
        }
