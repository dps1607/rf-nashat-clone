"""v3 Drive loader — per-type handler protocol and shared primitives.

Session 16 introduces this package as part of Gap 2 closure. Each file
type (PDF, image, docx, slides, sheets, plaintext, AV) gets a handler
module in this directory. Handlers share:

  - The `ExtractResult` dataclass, which every handler's `extract_*`
    function returns.
  - The page-marker convention (Option X, decided session 16): a
    handler stitches its extracted text into a single string and
    inserts marker tokens like `[PAGE 4]` at page/slide/row/timestamp
    boundaries. The dispatcher passes the stitched text to
    `_drive_common.chunk_text()` (which runs Layer B scrub), then runs
    a post-pass that scans each resulting chunk for markers, derives
    `display_locator` from the min/max marker in the chunk, and strips
    the markers from final chunk text before the chunk is written.
  - A deliberately dumb protocol: handlers know nothing about ChromaDB,
    embeddings, cost tracking, or scrub. They return text blocks and
    cost/diagnostics. The dispatcher does the rest.

Handler protocol:

    from ingester.loaders.types import ExtractResult, PAGE_MARKER

    def extract_from_path(path: Path, **kwargs) -> ExtractResult:
        ...

    def extract(drive_file: dict, drive_client, config) -> ExtractResult:
        '''Dispatcher entrypoint — downloads the Drive file, delegates
        to extract_from_path() for format-specific work, returns the
        same ExtractResult shape.'''
        ...

See `docs/plans/2026-04-14-drive-loader-v3.md` for the full design.
Session 16 lands `pdf_handler.py` as the pilot; future sessions add
one handler per session.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ----------------------------------------------------------------------------
# Page-marker convention (Option X, session 16)
# ----------------------------------------------------------------------------
#
# Handlers insert markers like `[PAGE 4]` at boundaries in their stitched
# text. The dispatcher post-pass uses these to derive display_locator on
# each chunk AFTER chunking is complete, then strips them.
#
# Marker format is a human-unreadable-looking sentinel so it's easy to
# match with a regex and unlikely to collide with real content. The sentinel
# is designed to NOT match any Layer B scrub pattern (no alphabetic names,
# no periods, no "Dr.").
#
# Future handlers reuse the same format with different UNIT values:
#   - pdf:       [PAGE N]
#   - slides:    [SLIDE N]
#   - sheets:    [ROW N]
#   - docx:      [SECTION N]
#   - plaintext: [LINE N]
#   - av:        [TIME HH:MM:SS]   (special-cased for timestamp rendering)

PAGE_MARKER_RE = re.compile(
    r"\[(?P<unit>PAGE|SLIDE|ROW|SECTION|LINE|TIME)\s+"
    r"(?P<value>[0-9:]+)\]"
)


def make_page_marker(unit: str, value: int | str) -> str:
    """Construct a marker token a handler inserts in its stitched text."""
    return f"[{unit} {value}]"


def strip_markers(text: str) -> str:
    """Remove all page markers from a string (used on final chunk text
    before it's handed to the embedder and written to Chroma)."""
    # Collapse any whitespace left over from stripped markers
    out = PAGE_MARKER_RE.sub("", text)
    # Clean up double-spaces and orphaned whitespace the strip may have left
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def derive_locator(chunk_text_str: str) -> Optional[str]:
    """Scan a chunk's (pre-strip) text for page markers and derive the
    human-readable display_locator.

    Returns None if the chunk contains no markers (e.g., a chunk of
    plain text from a format that didn't insert any).

    Format rules:
      - Single PAGE value:   "p. 4"
      - Range of PAGE values: "pp. 3-5"
      - Single SLIDE value:  "slide 12"
      - Range of SLIDE:      "slides 12-14"
      - Single ROW:          "row 47"
      - Range of ROW:        "rows 40-47"
      - Single SECTION:      "§3"
      - Range of SECTION:    "§§3-5"
      - Single LINE:         "line 120"
      - Range of LINE:       "lines 120-145"
      - TIME markers are handled separately by derive_timestamp() —
        this function returns None for TIME-only chunks.
    """
    matches = PAGE_MARKER_RE.findall(chunk_text_str)
    if not matches:
        return None

    # All markers in one chunk are expected to share a unit, but be lenient:
    # if a chunk somehow contains two different units, prefer the first one
    # seen and log a warning via return format.
    units = [m[0] for m in matches]
    first_unit = units[0]
    if first_unit == "TIME":
        return None  # handled by derive_timestamp()

    # Pull integer values for non-TIME units
    int_values: list[int] = []
    for unit, value in matches:
        if unit != first_unit:
            continue
        try:
            int_values.append(int(value))
        except ValueError:
            continue
    if not int_values:
        return None

    lo, hi = min(int_values), max(int_values)
    is_range = lo != hi

    formats = {
        "PAGE":    ("p. {lo}",    "pp. {lo}-{hi}"),
        "SLIDE":   ("slide {lo}", "slides {lo}-{hi}"),
        "ROW":     ("row {lo}",   "rows {lo}-{hi}"),
        "SECTION": ("§{lo}",      "§§{lo}-{hi}"),
        "LINE":    ("line {lo}",  "lines {lo}-{hi}"),
    }
    single_fmt, range_fmt = formats[first_unit]
    fmt = range_fmt if is_range else single_fmt
    return fmt.format(lo=lo, hi=hi)


def derive_timestamp(chunk_text_str: str) -> Optional[str]:
    """Scan a chunk for TIME markers and return a display_timestamp
    string like '[00:14:32]-[00:16:10]'. Returns None if no TIME markers
    are present. Used by the future av_handler."""
    time_matches = [
        m[1] for m in PAGE_MARKER_RE.findall(chunk_text_str) if m[0] == "TIME"
    ]
    if not time_matches:
        return None
    lo, hi = time_matches[0], time_matches[-1]
    if lo == hi:
        return f"[{lo}]"
    return f"[{lo}]-[{hi}]"


# ----------------------------------------------------------------------------
# ExtractResult — the shape every handler returns (D3)
# ----------------------------------------------------------------------------

@dataclass
class ExtractResult:
    """Returned by every v3 handler's extract_* function.

    Fields:
      stitched_text: single-string representation of the extracted content,
        with page/slide/row markers embedded at boundaries. This is what
        the dispatcher hands to `_drive_common.chunk_text()`. Must be
        non-empty for the dispatcher to produce chunks.

      extraction_method: short identifier describing which code path
        produced the text. Examples:
          'pdf_text'           — pdfplumber native text extraction
          'pdf_ocr_fallback'   — vision OCR on page rasters
          'image_vision'       — single-image vision OCR
          'sheets_openpyxl'    — openpyxl row extraction
          'slides_api'         — Google Slides API
          'docx_python_docx'   — python-docx paragraph extraction
          'plaintext_read'     — UTF-8 file read
          'audio_gemini'       — Vertex Gemini audio transcription
        Per-type breakdown in run records keys off this value (D5).

      source_unit_label: the singular label for this type's locator unit,
        used by the dispatcher to populate display_locator fallbacks.
        Examples: 'page', 'slide', 'row', 'section', 'line'. None for
        types without a locator concept (e.g., single loose images).

      pages_total / units_total: count of pages, slides, rows, etc. in
        the source file. Used for per-file diagnostics and cost rollups.

      images_seen / images_ocr_called: image handling counters (mirrors
        v2's per-image ledger for parity in run records).

      vision_cost_usd: dollar spend on vision OCR for this file.
      transcription_cost_usd: dollar spend on audio/video transcription.
        Zero for non-AV handlers.

      warnings: handler-captured soft warnings (e.g., 'page 7 extracted
        zero characters', 'OCR fallback triggered on 3/12 pages').

      extra: free-form per-handler diagnostics that don't fit the common
        shape. Stored in run records for debugging, not used downstream.
    """
    stitched_text: str
    extraction_method: str
    source_unit_label: Optional[str] = None
    pages_total: int = 0
    units_total: int = 0
    images_seen: int = 0
    images_ocr_called: int = 0
    vision_cost_usd: float = 0.0
    transcription_cost_usd: float = 0.0
    warnings: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Chunking pipeline — Option Q (session 16 decision)
# ----------------------------------------------------------------------------
#
# Every v3 handler follows the same three-step chunking pipeline:
#   1. handler.extract_from_path() returns ExtractResult with stitched_text
#      containing [UNIT N] markers at boundaries
#   2. chunk_with_locators() runs _drive_common.chunk_text() (Layer B scrub
#      fires here), then for each resulting chunk:
#        - derive display_locator / display_timestamp from markers
#        - strip markers from final chunk text
#   3. dispatcher embeds chunks, writes to Chroma
#
# This function is the single entrypoint handlers go through for chunking.
# Future handlers MUST call this helper — calling chunk_text() directly
# would skip the locator derivation and leave markers in the chunk text,
# which would pollute embeddings and break retrieval.

def chunk_with_locators(stitched_text: str) -> list[dict]:
    """Chunk stitched text via the shared chokepoint, derive locators,
    strip markers. Returns a list of chunk dicts with shape:

        {
          "text": str,                # marker-free final chunk text
          "word_count": int,
          "chunk_index": int,
          "name_replacements": int,   # Layer B scrub hit count
          "display_locator": str | None,
          "display_timestamp": str | None,
        }

    The dispatcher writes these chunks to Chroma verbatim — the `text`
    field goes to the embedder, the other fields go to metadata.
    """
    # Deferred import — _drive_common imports scrub which imports regex etc.
    # Importing lazily keeps this module cheap to import from test files
    # that only need the marker helpers.
    from ingester.loaders._drive_common import chunk_text

    raw_chunks = chunk_text(stitched_text)
    out: list[dict] = []
    for c in raw_chunks:
        raw_text = c["text"]
        locator = derive_locator(raw_text)
        timestamp = derive_timestamp(raw_text)
        clean_text = strip_markers(raw_text)
        out.append({
            "text": clean_text,
            "word_count": c["word_count"],
            "chunk_index": c["chunk_index"],
            "name_replacements": c["name_replacements"],
            "display_locator": locator,
            "display_timestamp": timestamp,
        })
    return out
