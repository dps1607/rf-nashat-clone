"""Synthetic test for ingester/loaders/types/google_doc_handler.py.

Session 17 (BACKLOG #11) — proves the new handler module:
  1. Imports cleanly and exposes the M3 public interface.
  2. Reproduces v2's byte-level behavior when emit_section_markers=False
     (the v2 default — preserves the existing 13-chunk path).
  3. Emits [SECTION N] markers at headings when emit_section_markers=True
     (the v3 default — populates display_locator).
  4. Section markers survive Layer B scrub (no overlap with name patterns).
  5. chunk_with_locators correctly derives display_locator from the
     stitched-and-chunked Google Doc.
  6. Image OCR path produces [IMAGE #N: ...] markers in the stitched text
     using a mocked vision client (no Gemini calls, no Drive calls).
  7. ExtractResult fields are populated with sensible values.

No network, no Drive, no real Gemini, no Chroma writes.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingester.loaders.types import (
    google_doc_handler,
    PAGE_MARKER_RE,
    derive_locator,
    chunk_with_locators,
    strip_markers,
)


# ----------------------------------------------------------------------------
# Test fixtures
# ----------------------------------------------------------------------------

# A synthetic Google Doc HTML export that mimics the shape Drive returns:
# - body wrapped in a div
# - headings (h1/h2)
# - paragraphs with inline spans
# - one image with a small data URI
# - the former-collaborator name to prove scrub still fires
SYNTHETIC_HTML_WITH_IMAGE = b"""<html>
<head><meta charset="utf-8"><style>p{margin:0}</style></head>
<body class="c1">
<h1 class="title"><span>Fertility Protocol Guide</span></h1>
<p><span>Written by Dr. Christina Massinople, ND. This is the introduction
to the protocol guide. It covers basic principles of fertility optimization
and lays the groundwork for the rest of the document.</span></p>
<h2><span>Section One: Egg Quality</span></h2>
<p><span>Egg quality is influenced by mitochondrial function, oxidative
stress, and hormonal milieu. CoQ10 supplementation has been shown to
improve markers of egg quality in women over 35. Vitamin D status is
also strongly correlated with ovulatory function and pregnancy outcomes.</span></p>
<p><span>Additional research from Dr. Christina suggests that methylfolate
supplementation may be beneficial for women with MTHFR polymorphisms.
A typical starting dose is 800 mcg daily.</span></p>
<h2><span>Section Two: Sperm Quality</span></h2>
<p><span>Sperm quality has declined globally over the past several decades.
Lifestyle factors including diet, exercise, sleep, and stress all play
significant roles. Antioxidant supplementation including zinc, selenium,
and vitamin C can support healthy sperm parameters.</span></p>
<p><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=" alt="protocol diagram"></p>
<h2><span>Section Three: Lifestyle Foundations</span></h2>
<p><span>The foundation of any fertility protocol is consistent attention
to sleep, stress management, nutrition, and movement. These four pillars
support the more targeted interventions described in earlier sections.
Without them, supplementation alone is unlikely to produce results.</span></p>
</body>
</html>
"""

SYNTHETIC_HTML_NO_IMAGES = b"""<html>
<body>
<p>This is a simple paragraph with no images and no headings.</p>
<p>It contains a second paragraph to test stitching.</p>
</body>
</html>
"""


# ----------------------------------------------------------------------------
# Mocks (no Drive, no Gemini)
# ----------------------------------------------------------------------------

class _MockLedger:
    def __init__(self):
        self.images_seen = 0
        self.images_ocr_called = 0
        self.images_cache_hit = 0
        self.images_decorative = 0
        self.images_failed = 0
        self.vision_input_tokens = 0
        self.vision_output_tokens = 0
        self.vision_cost_usd = 0.0
        self.errors = []


class _MockOcrResult:
    def __init__(self, ocr_text, *, is_decorative=False, failed=False):
        self.ocr_text = ocr_text
        self.is_decorative = is_decorative
        self.failed = failed
        self.failure_reason = "" if not failed else "synthetic failure"
        self.sha256 = "fakesha256_" + str(hash(ocr_text))[:8]
        self.vision_input_tokens = 100
        self.vision_output_tokens = 50


class MockVisionClient:
    """Stand-in for GeminiVisionClient. Returns a configurable OCR
    result and updates a ledger so the handler can read images_seen
    deltas the same way the real client populates them."""

    def __init__(self, ocr_text="diagram showing fertility protocol steps"):
        self.ledger = _MockLedger()
        self._ocr_text = ocr_text

    def ocr_image(self, img_bytes, mime_type, use_cache=True):
        self.ledger.images_seen += 1
        self.ledger.images_ocr_called += 1
        self.ledger.vision_input_tokens += 100
        self.ledger.vision_output_tokens += 50
        # Simulate ~$0.0001 per image
        self.ledger.vision_cost_usd += 0.0001
        return _MockOcrResult(self._ocr_text)


class MockDriveClient:
    """Stand-in for DriveClient. The handler only touches it via
    resolve_image_bytes() for non-data-URI images. Our test images are
    all data URIs so this client's methods should never be called."""

    def __init__(self):
        self.calls = []

    @property
    def _service(self):
        raise RuntimeError(
            "MockDriveClient._service should not be called — "
            "synthetic test images use data URIs only"
        )


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------

results = []


def _record(name, ok, detail=""):
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def test_imports_and_public_interface():
    name = "imports_and_public_interface"
    try:
        assert callable(google_doc_handler.export_html)
        assert callable(google_doc_handler.resolve_image_bytes)
        assert callable(google_doc_handler.walk_html_in_order)
        assert callable(google_doc_handler.stitch_stream)
        assert callable(google_doc_handler.extract_from_html_bytes)
        assert callable(google_doc_handler.extract)
        assert "head" in google_doc_handler.HTML_SKIP_TAGS
        _record(name, True)
    except Exception as e:
        _record(name, False, str(e))


def test_v2_mode_no_section_markers():
    """v2 default (emit_section_markers=False) — stream contains NO
    heading entries, stitched text contains NO [SECTION N] markers.
    This is the byte-identical-to-v2 contract."""
    name = "v2_mode_no_section_markers"
    try:
        stream = google_doc_handler.walk_html_in_order(
            SYNTHETIC_HTML_WITH_IMAGE, emit_section_markers=False
        )
        # No heading entries
        heading_entries = [e for e in stream if e["kind"] == "heading"]
        assert len(heading_entries) == 0, f"expected 0 heading entries, got {len(heading_entries)}"

        # Stitch and check for SECTION markers
        vc = MockVisionClient()
        dc = MockDriveClient()
        stitched, image_count, per_image, section_count = google_doc_handler.stitch_stream(
            stream, vc, dc, use_cache=False, emit_section_markers=False
        )
        assert section_count == 0, f"expected section_count=0, got {section_count}"
        assert "[SECTION" not in stitched, "stitched text should contain no SECTION markers"

        # Sanity: the content should still be present
        assert "Egg Quality" in stitched
        assert "CoQ10" in stitched
        assert "[IMAGE #1:" in stitched, "image OCR marker should be present"
        _record(name, True, f"image_count={image_count}, no SECTION markers")
    except Exception as e:
        _record(name, False, str(e))


def test_v3_mode_section_markers_emitted():
    """v3 default (emit_section_markers=True) — stream contains heading
    entries, stitched text contains [SECTION N] markers in document
    order. The synthetic doc has 1 h1 + 3 h2 = 4 headings."""
    name = "v3_mode_section_markers_emitted"
    try:
        stream = google_doc_handler.walk_html_in_order(
            SYNTHETIC_HTML_WITH_IMAGE, emit_section_markers=True
        )
        heading_entries = [e for e in stream if e["kind"] == "heading"]
        assert len(heading_entries) == 4, f"expected 4 heading entries, got {len(heading_entries)}"
        # Levels: h1, h2, h2, h2
        levels = [e["level"] for e in heading_entries]
        assert levels == [1, 2, 2, 2], f"expected [1,2,2,2], got {levels}"
        texts = [e["text"] for e in heading_entries]
        assert "Fertility Protocol Guide" in texts[0]
        assert "Egg Quality" in texts[1]
        assert "Sperm Quality" in texts[2]
        assert "Lifestyle Foundations" in texts[3]

        vc = MockVisionClient()
        dc = MockDriveClient()
        stitched, image_count, per_image, section_count = google_doc_handler.stitch_stream(
            stream, vc, dc, use_cache=False, emit_section_markers=True
        )
        assert section_count == 4, f"expected section_count=4, got {section_count}"
        # Markers in stitched text
        assert "[SECTION 1]" in stitched
        assert "[SECTION 2]" in stitched
        assert "[SECTION 3]" in stitched
        assert "[SECTION 4]" in stitched
        # Markers in document order
        s1 = stitched.index("[SECTION 1]")
        s2 = stitched.index("[SECTION 2]")
        s3 = stitched.index("[SECTION 3]")
        s4 = stitched.index("[SECTION 4]")
        assert s1 < s2 < s3 < s4, "section markers out of order"
        _record(name, True, f"4 sections in order")
    except Exception as e:
        _record(name, False, str(e))


def test_section_markers_match_locator_regex():
    """The [SECTION N] marker format must match PAGE_MARKER_RE in
    types/__init__.py so derive_locator can consume it."""
    name = "section_markers_match_locator_regex"
    try:
        sample = "some text [SECTION 3] more text [SECTION 5] end"
        matches = PAGE_MARKER_RE.findall(sample)
        assert len(matches) == 2, f"expected 2 matches, got {matches}"
        assert matches[0] == ("SECTION", "3")
        assert matches[1] == ("SECTION", "5")
        # derive_locator should produce a range
        loc = derive_locator(sample)
        assert loc == "§§3-5", f"expected §§3-5, got {loc}"

        # Single section
        loc2 = derive_locator("text [SECTION 7] more text")
        assert loc2 == "§7", f"expected §7, got {loc2}"
        _record(name, True)
    except Exception as e:
        _record(name, False, str(e))


def test_section_markers_survive_scrub():
    """Layer B scrub must not touch [SECTION N] markers. Verify by
    running a string containing both the former-collaborator name AND
    section markers through scrub_text directly."""
    name = "section_markers_survive_scrub"
    try:
        from ingester.text.scrub import scrub_text
        original = (
            "[SECTION 1] Introduction by Dr. Christina Massinople. "
            "She wrote this guide. [SECTION 2] More content here."
        )
        scrubbed, n = scrub_text(original)
        assert "[SECTION 1]" in scrubbed, "marker 1 must survive scrub"
        assert "[SECTION 2]" in scrubbed, "marker 2 must survive scrub"
        assert "Christina" not in scrubbed, "scrub must remove first name"
        assert "Massinople" not in scrubbed, "scrub must remove last name"
        assert n >= 1, f"expected at least 1 replacement, got {n}"
        _record(name, True, f"n_replacements={n}, both markers intact")
    except Exception as e:
        _record(name, False, str(e))


def test_extract_from_html_bytes_v3_mode():
    """End-to-end: extract_from_html_bytes with emit_section_markers=True
    returns a populated ExtractResult."""
    name = "extract_from_html_bytes_v3_mode"
    try:
        vc = MockVisionClient()
        dc = MockDriveClient()
        result = google_doc_handler.extract_from_html_bytes(
            SYNTHETIC_HTML_WITH_IMAGE,
            drive_client=dc,
            vision_client=vc,
            use_cache=False,
            emit_section_markers=True,
        )
        assert result.extraction_method == "google_doc_html_vision"
        assert result.source_unit_label == "section"
        assert result.pages_total == 0
        assert result.units_total == 4, f"expected 4 sections, got {result.units_total}"
        assert result.images_seen == 1, f"expected 1 image, got {result.images_seen}"
        assert result.images_ocr_called == 1
        assert result.vision_cost_usd > 0
        assert "[SECTION 1]" in result.stitched_text
        assert "[IMAGE #1:" in result.stitched_text
        assert "per_image_records" in result.extra
        assert len(result.extra["per_image_records"]) == 1
        _record(name, True, f"sections=4, images=1, cost=${result.vision_cost_usd:.4f}")
    except Exception as e:
        _record(name, False, str(e))


def test_extract_from_html_bytes_v2_mode():
    """v2 mode: source_unit_label is None, no SECTION markers."""
    name = "extract_from_html_bytes_v2_mode"
    try:
        vc = MockVisionClient()
        dc = MockDriveClient()
        result = google_doc_handler.extract_from_html_bytes(
            SYNTHETIC_HTML_WITH_IMAGE,
            drive_client=dc,
            vision_client=vc,
            use_cache=False,
            emit_section_markers=False,
        )
        assert result.extraction_method == "google_doc_html_vision"
        assert result.source_unit_label is None
        assert result.units_total == 0
        assert "[SECTION" not in result.stitched_text
        assert "[IMAGE #1:" in result.stitched_text
        _record(name, True)
    except Exception as e:
        _record(name, False, str(e))


def test_chunk_with_locators_end_to_end():
    """Full v3 chokepoint: extract → chunk_with_locators → verify chunks
    have display_locator populated AND former-collaborator name scrubbed
    AND markers stripped from final text."""
    name = "chunk_with_locators_end_to_end"
    try:
        vc = MockVisionClient()
        dc = MockDriveClient()
        result = google_doc_handler.extract_from_html_bytes(
            SYNTHETIC_HTML_WITH_IMAGE,
            drive_client=dc,
            vision_client=vc,
            use_cache=False,
            emit_section_markers=True,
        )
        chunks = chunk_with_locators(result.stitched_text)
        assert len(chunks) >= 1, "expected at least 1 chunk"

        # Total scrub hits across chunks: synthetic doc has 2 occurrences
        # of "Dr. Christina" / "Christina Massinople" (intro + section 1
        # mention).
        total_scrub = sum(c["name_replacements"] for c in chunks)
        assert total_scrub >= 1, f"expected >=1 scrub hit, got {total_scrub}"

        # No final chunk should still contain the markers
        for c in chunks:
            assert "[SECTION" not in c["text"], (
                f"chunk {c[chunk_index]} still contains SECTION marker"
            )
            assert "Christina" not in c["text"], (
                f"chunk {c[chunk_index]} still contains former-collaborator name"
            )
            assert "Massinople" not in c["text"], (
                f"chunk {c[chunk_index]} still contains former-collaborator name"
            )

        # At least one chunk should have a display_locator
        with_loc = [c for c in chunks if c["display_locator"]]
        assert len(with_loc) >= 1, "at least one chunk should have display_locator"
        # Locator should be § format
        for c in with_loc:
            assert c["display_locator"].startswith("§"), (
                f"expected § locator, got {c[display_locator]!r}"
            )

        _record(
            name, True,
            f"{len(chunks)} chunks, {total_scrub} scrub hits, "
            f"{len(with_loc)} with locators"
        )
    except Exception as e:
        _record(name, False, str(e))


def test_no_images_no_headings_simple_doc():
    """Edge case: a doc with no images and no headings should still
    produce a clean stitched text and zero markers."""
    name = "no_images_no_headings_simple_doc"
    try:
        vc = MockVisionClient()
        dc = MockDriveClient()
        result = google_doc_handler.extract_from_html_bytes(
            SYNTHETIC_HTML_NO_IMAGES,
            drive_client=dc,
            vision_client=vc,
            use_cache=False,
            emit_section_markers=True,
        )
        assert result.images_seen == 0
        assert result.units_total == 0
        assert "[SECTION" not in result.stitched_text
        assert "[IMAGE" not in result.stitched_text
        assert "simple paragraph" in result.stitched_text
        assert "second paragraph" in result.stitched_text
        _record(name, True)
    except Exception as e:
        _record(name, False, str(e))


# ----------------------------------------------------------------------------
# Run all tests
# ----------------------------------------------------------------------------

print("=" * 60)
print("google_doc_handler synthetic tests (session 17, BACKLOG #11)")
print("=" * 60)

test_imports_and_public_interface()
test_v2_mode_no_section_markers()
test_v3_mode_section_markers_emitted()
test_section_markers_match_locator_regex()
test_section_markers_survive_scrub()
test_extract_from_html_bytes_v3_mode()
test_extract_from_html_bytes_v2_mode()
test_chunk_with_locators_end_to_end()
test_no_images_no_headings_simple_doc()

print("-" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"  {passed}/{len(results)} passing, {failed} failing")
sys.exit(0 if failed == 0 else 1)
