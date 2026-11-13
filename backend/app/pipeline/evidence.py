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
