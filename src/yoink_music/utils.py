"""Shared utilities."""
from __future__ import annotations

import difflib
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def _norm(s: str) -> str:
    import unicodedata
    # Decompose unicode (Ø -> O + combining stroke) then drop combining marks
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Strip common noise: featured artists, remix tags, remaster notes
    s = re.sub(r"\(feat\.?[^)]*\)", "", s)
    s = re.sub(r"\(ft\.?[^)]*\)", "", s)
    s = re.sub(r"\(.*?remaster.*?\)", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def score(a: str, b: str) -> float:
    """Similarity score [0..1] between two normalized strings."""
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def track_score(
    candidate_artist: str,
    candidate_title: str,
    expected_artist: str,
    expected_title: str,
) -> float:
    """Combined match score for a track candidate.

    Returns the geometric mean of title and artist similarity so that
    a wrong artist with a matching title (or vice versa) scores poorly.
    Both components must be above their individual minimums for the
    result to be usable.
    """
    ts = score(candidate_title, expected_title)
    # Artist field may be empty for some platforms - skip penalty if both empty
    if not expected_artist and not candidate_artist:
        return ts
    as_ = score(candidate_artist, expected_artist)
    # Geometric mean: one bad component tanks the whole score
    import math
    return math.sqrt(ts * as_)


def normalize_url(url: str) -> str:
    """Strip tracking params (si, utm_*, nd, context) for consistent cache keys."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    filtered = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if not k.startswith("utm_") and k not in ("si", "context", "nd")
    }
    return urlunparse(parsed._replace(query=urlencode(filtered, doseq=True)))
