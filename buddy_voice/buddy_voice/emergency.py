"""Deterministic spoken emergency-stop recognition."""

from __future__ import annotations

import re
import unicodedata


_SPACE = re.compile(r'\s+')
_NON_WORD = re.compile(r'[^\w\s]')
_STOP_PHRASES = frozenset({
    'stop',
    'stop now',
    'buddy stop',
    'stop buddy',
    'emergency stop',
    'buddy emergency stop',
})


def normalize_spoken_phrase(text: str) -> str:
    """
    Normalize a transcript without allowing token-substring matches.

    Matching is always against a complete normalized phrase.  For example,
    ``desktop`` remains ``desktop`` and therefore cannot activate ``stop``.
    """
    normalized = unicodedata.normalize('NFKC', text).casefold()
    normalized = _NON_WORD.sub(' ', normalized)
    return _SPACE.sub(' ', normalized).strip()


def is_emergency_stop_phrase(text: str) -> bool:
    """Return true only for a small, auditable set of complete stop phrases."""
    return normalize_spoken_phrase(text) in _STOP_PHRASES
