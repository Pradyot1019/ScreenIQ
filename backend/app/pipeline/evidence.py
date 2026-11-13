"""Evidence validation (FR-32): every quote the LLM cites must really be in the resume.

LLMs sometimes "quote" things the resume never says. A score backed by a made-up quote
is worse than no score, because it looks trustworthy. So each quote is fuzzy-matched
against the resume text; quotes that don't match are dropped and the criterion is
flagged low_confidence. Fuzzy (not exact) matching tolerates harmless differences:
line breaks inside a sentence, curly vs straight quotes, extra spaces.
"""

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

MATCH_THRESHOLD = 90  # spec 9.3: rapidfuzz partial_ratio >= 90
MIN_QUOTE_CHARS = 4  # "Go" alone could match anywhere; it isn't evidence of anything

_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "•": " "})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE).lower()
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class EvidenceCheck:
    verified: list[str]
    rejected: list[str]


def check_evidence(quotes: list[str], resume_text: str) -> EvidenceCheck:
    haystack = normalize(resume_text)
    verified: list[str] = []
    rejected: list[str] = []
    for quote in quotes:
        needle = normalize(quote)
        if (
            len(needle) >= MIN_QUOTE_CHARS
            and fuzz.partial_ratio(needle, haystack) >= MATCH_THRESHOLD
        ):
            if quote not in verified:
                verified.append(quote)
        else:
            rejected.append(quote)
    return EvidenceCheck(verified, rejected)


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """normalize(), but also remember which original index each output char came from,
    so a match found in the normalized text can be mapped back to the original."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch).translate(_TRANSLATE).lower():
            if c.isspace():
                if not out or out[-1] == " ":
                    continue  # collapse runs of whitespace, drop leading
                c = " "
            out.append(c)
            origin.append(i)
    return "".join(out), origin


def locate(quote: str, resume_text: str) -> tuple[int, int] | None:
    """(start, end) of the quote in the ORIGINAL resume text, or None if not found.
    Used to highlight evidence in the resume view."""
    needle = normalize(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return None
    haystack, origin = _normalize_with_map(resume_text)
    match = fuzz.partial_ratio_alignment(needle, haystack)
    if match is None or match.score < MATCH_THRESHOLD or match.dest_end <= match.dest_start:
        return None
    return origin[match.dest_start], origin[match.dest_end - 1] + 1
