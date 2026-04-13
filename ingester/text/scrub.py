"""
Text scrub rules for RF ingest pipelines.

Purpose
-------
Replace names of former collaborators with "Dr. Nashat Latib" while
preserving all substantive content. Originally motivated by the
Dr. Christina Massinople case (session 12) but designed as a general
mechanism — add entries to NAME_REPLACEMENTS to cover future cases.

Design
------
Layer B scrub: runs once per chunk, on the text emitted by
`_drive_common.chunk_text()`, before the chunk is handed to embedding
or the dry-run dump. Cache stays warm (cache is ground-truth raw OCR).
Vector embeddings reflect the substitution, so similarity search for
the old name does not retrieve the renamed chunks.

Rules are ordered from most specific to least specific so that
"Dr. Christina Massinople" is matched by rule 1 and does not cascade
through rules 2–9.

The "Mass" short-form is context-gated: bare `mass` is never touched
(it collides with legitimate clinical vocabulary — body mass index,
lean mass, mass spec, etc.). Only "Dr. Mass", "by Mass", and
"Mass Park" are recognized as person references.

Usage
-----
    from ingester.text.scrub import scrub_text

    clean, n_replacements = scrub_text(raw_text)

If n_replacements > 0 the caller should log or surface the count so
downstream review can audit scrub behavior.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


CANONICAL_REPLACEMENT = "Dr. Nashat Latib"


@dataclass(frozen=True)
class NameRule:
    pattern: re.Pattern
    replacement: str
    description: str


# Ordered most-specific first. Every pattern is case-insensitive.
# Order matters: longer matches must come before their substrings
# so we don't partially replace "Dr. Christina Massinople" via a
# shorter rule and leave dangling text.
NAME_REPLACEMENTS: list[NameRule] = [
    # === Full formal names (most specific) ===
    NameRule(
        pattern=re.compile(r"\bDr\.?\s+Christina\s+Massinople\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Dr. Christina Massinople (full formal)",
    ),
    NameRule(
        pattern=re.compile(r"\bChristina\s+Massinople\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Christina Massinople (no title)",
    ),
    NameRule(
        pattern=re.compile(r"\bDr\.?\s+Massinople\s+Park\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Dr. Massinople Park",
    ),
    NameRule(
        pattern=re.compile(r"\bMassinople\s+Park\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Massinople Park",
    ),
    NameRule(
        pattern=re.compile(r"\bDr\.?\s+Massinople\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Dr. Massinople",
    ),
    NameRule(
        pattern=re.compile(r"\bMassinople\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Massinople (bare surname)",
    ),

    # === Christina variants (title-prefixed) ===
    # Must not match "Dr. Christina Massinople" (already handled above) —
    # achieved by negative lookahead for " Massinople"
    NameRule(
        pattern=re.compile(r"\bDr\.?\s+Christina\b(?!\s+Massinople)", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Dr. Christina (not followed by Massinople)",
    ),

    # === Chris variants (title-prefixed, NOT Christina) ===
    # Negative lookahead for "tina" prevents matching "Dr. Christina"
    # which has already been handled. Word boundary on both sides.
    NameRule(
        pattern=re.compile(r"\bDr\.?\s+Chris\b(?!tina)", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Dr. Chris (but not Dr. Christina)",
    ),

    # === Mass short-form (context-gated) ===
    # Only matches when "Mass" is unambiguously a person reference.
    # Never matches bare "mass" (collides with medical vocab).
    NameRule(
        pattern=re.compile(r"\bDr\.?\s+Mass\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Dr. Mass (short form)",
    ),
    NameRule(
        pattern=re.compile(r"\bby\s+Mass\b", re.IGNORECASE),
        replacement="by " + CANONICAL_REPLACEMENT,
        description="by Mass (byline)",
    ),
    NameRule(
        pattern=re.compile(r"\bMass\s+Park\b", re.IGNORECASE),
        replacement=CANONICAL_REPLACEMENT,
        description="Mass Park (short form of Massinople Park)",
    ),
]


# Second-pass dedup rules: after the primary substitutions run, collapse
# "Dr. Nashat Latib & Dr. Nashat Latib" (and and-variants) into a single
# attribution. This handles joint-byline cases cleanly.
DEDUP_PATTERNS: list[tuple[re.Pattern, str]] = [
    # "& "
    (
        re.compile(
            re.escape(CANONICAL_REPLACEMENT)
            + r"\s*&\s*"
            + re.escape(CANONICAL_REPLACEMENT),
            re.IGNORECASE,
        ),
        CANONICAL_REPLACEMENT,
    ),
    # " and "
    (
        re.compile(
            re.escape(CANONICAL_REPLACEMENT)
            + r"\s+and\s+"
            + re.escape(CANONICAL_REPLACEMENT),
            re.IGNORECASE,
        ),
        CANONICAL_REPLACEMENT,
    ),
    # ", "
    (
        re.compile(
            re.escape(CANONICAL_REPLACEMENT)
            + r"\s*,\s*"
            + re.escape(CANONICAL_REPLACEMENT),
            re.IGNORECASE,
        ),
        CANONICAL_REPLACEMENT,
    ),
    # ", and " — handles triple-author residue like
    # "Dr. Nashat Latib, and Dr. Nashat Latib" which is what the
    # pairwise ", " pass leaves behind when the source was
    # "A, B, and C" and all three normalized to the same name.
    (
        re.compile(
            re.escape(CANONICAL_REPLACEMENT)
            + r"\s*,\s*and\s+"
            + re.escape(CANONICAL_REPLACEMENT),
            re.IGNORECASE,
        ),
        CANONICAL_REPLACEMENT,
    ),
]


def scrub_text(text: str) -> tuple[str, int]:
    """
    Apply name-replacement rules to text.

    Returns
    -------
    (cleaned_text, replacement_count)
        cleaned_text: text with all matched names replaced and
            joint-byline duplicates collapsed.
        replacement_count: number of substitutions made across all
            primary rules (dedup pass not counted — it's cleanup,
            not new replacements).
    """
    if not text:
        return text, 0

    total = 0
    current = text

    for rule in NAME_REPLACEMENTS:
        current, n = rule.pattern.subn(rule.replacement, current)
        total += n

    # Dedup pass — run until stable (shouldn't need more than 1 iter
    # in practice, but protects against triple-author cases).
    for _ in range(3):
        changed = False
        for pattern, replacement in DEDUP_PATTERNS:
            new, n = pattern.subn(replacement, current)
            if n > 0:
                current = new
                changed = True
        if not changed:
            break

    return current, total


def scrub_text_simple(text: str) -> str:
    """Convenience wrapper when caller doesn't need the count."""
    return scrub_text(text)[0]
