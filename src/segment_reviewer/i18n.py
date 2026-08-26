"""Interface languages.

Two ship with the tool — ``en`` and ``pt-BR`` — one JSON file each under
``locales/``. Dropping another JSON in that folder is all a third takes.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "en"


@lru_cache(maxsize=None)
def available() -> tuple[str, ...]:
    """Language codes with a locale file, default first."""
    codes = sorted(p.stem for p in LOCALE_DIR.glob("*.json"))
    if DEFAULT_LANG in codes:
        codes.remove(DEFAULT_LANG)
        codes.insert(0, DEFAULT_LANG)
    return tuple(codes)


@lru_cache(maxsize=None)
def bundle(lang: str) -> dict:
    """The whole translation bundle for *lang*, falling back to the default."""
    path = LOCALE_DIR / f"{lang}.json"
    if not path.exists():
        path = LOCALE_DIR / f"{DEFAULT_LANG}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(lang: str | None) -> str:
    """Best available match for a requested language tag."""
    if not lang:
        return DEFAULT_LANG
    codes = available()
    if lang in codes:
        return lang
    lower = lang.lower()
    for code in codes:
        if code.lower() == lower:
            return code
    base = lower.split("-")[0]
    for code in codes:
        if code.lower().split("-")[0] == base:
            return code
    return DEFAULT_LANG


def language_names() -> list[dict[str, str]]:
    """``[{code, name}]`` for the language picker."""
    return [
        {"code": code, "name": bundle(code).get("meta", {}).get("name", code)}
        for code in available()
    ]


class Translator:
    """Dotted-key lookup with ``{placeholder}`` substitution."""

    def __init__(self, lang: str) -> None:
        self.lang = normalize(lang)
        self._data = bundle(self.lang)
        self._fallback = bundle(DEFAULT_LANG)

    def __call__(self, key: str, **kwargs) -> str:
        value = self._lookup(self._data, key)
        if value is None:
            value = self._lookup(self._fallback, key)
        if value is None:
            return key
        return value.format(**kwargs) if kwargs else value

    @staticmethod
    def _lookup(data: dict, key: str) -> str | None:
        node: object = data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if isinstance(node, str) else None
