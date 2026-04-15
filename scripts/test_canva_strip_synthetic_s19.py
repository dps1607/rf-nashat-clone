"""
test_canva_strip_synthetic_s19.py — verify BACKLOG #29 _strip_editor_metadata.

Synthetic test, no Drive, no Chroma, no API spend. Hand-crafted fixtures
exercise every documented strip pattern + the position cap + the load-bearing
marker preservation + the v2-default no-op behavior.

Closes BACKLOG #29's regression-safety requirement on clean docs (the
A/B retrieval test on real Sugar Swaps lives in
test_canva_strip_ab_existing_chunks_s19.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingester.loaders.types.google_doc_handler import _strip_editor_metadata


# -----------------------------------------------------------------------------
# Pollution stripping — patterns we know exist
# -----------------------------------------------------------------------------

def test_strips_canva_url_line() -> None:
    text = "Canva design to edit: https://www.canva.com/design/ABC123/edit?utm_content=foo\n\nBody text here."
    out = _strip_editor_metadata(text)
    assert "canva.com" not in out, f"Canva URL not stripped: {out!r}"
    assert "Body text here" in out
    print("  [PASS] strips Canva edit URL line")


def test_strips_bare_cover_tag() -> None:
    text = "COVER:\n\nThe Real Body Text Of The Document\n\nMore content."
    out = _strip_editor_metadata(text)
    assert "COVER" not in out, f"COVER: tag not stripped: {out!r}"
    assert "The Real Body Text" in out
    print("  [PASS] strips bare COVER: tag")


def test_strips_page_tags() -> None:
    text = "PAGE\n\nFirst page content.\n\nPAGE 2:\n\nSecond page content."
    out = _strip_editor_metadata(text)
    assert "PAGE\n" not in out and "PAGE 2:" not in out, f"PAGE tags not stripped: {out!r}"
    assert "First page content" in out
    assert "Second page content" in out
    print("  [PASS] strips PAGE / PAGE N: tags")


def test_strips_header_footer_back_cover() -> None:
    text = "HEADER:\n\nintro text\n\nFOOTER:\n\nBACK COVER:"
    out = _strip_editor_metadata(text)
    assert "HEADER:" not in out
    assert "FOOTER:" not in out
    assert "BACK COVER:" not in out
    assert "intro text" in out
    print("  [PASS] strips HEADER:/FOOTER:/BACK COVER:")


def test_strips_full_canva_pollution_block() -> None:
    """Real-world Sugar Swaps Guide pattern."""
    text = (
        "[RH] The Fertility-Smart Sugar Swap Guide\n"
        "Canva design to edit: https://www.canva.com/design/DAGlfxX42jY/edit?utm_content=foo\n"
        "\n"
        "COVER:\n"
        "\n"
        "The Fertility-Smart Sugar Swap Guide\n"
        "\n"
        "Simple food upgrades to support hormone balance.\n"
        "\n"
        "PAGE\n"
        "\n"
        "We're not here to tell you never to eat dessert again."
    )
    out = _strip_editor_metadata(text)
    assert "canva.com" not in out
    assert "COVER:" not in out
    # "PAGE" alone on a line should be stripped (matches bare tag pattern)
    assert "\nPAGE\n" not in out
    # Real content survives
    assert "The Fertility-Smart Sugar Swap Guide" in out
    assert "Simple food upgrades" in out
    assert "We're not here to tell you" in out
    print("  [PASS] strips full Sugar Swaps-style pollution block")


# -----------------------------------------------------------------------------
# Regression safety — clean docs unchanged, real content preserved
# -----------------------------------------------------------------------------

def test_clean_doc_no_changes() -> None:
    """DFH-like clean doc with no editor noise should pass through unchanged."""
    text = (
        "Professional Nutritional Private Label Protocol for Fertility Program:\n"
        "\n"
        "Core Essentials Females:\n"
        "\n"
        "Omega Boost-R (120caps, 2 qd) - needs 2 bottles. ($29 cost)\n"
        "\n"
        "Daily Optinatal (60caps, 1 bid) - needs 3 bottles ($18)"
    )
    out = _strip_editor_metadata(text)
    assert out == text, f"clean doc was modified:\n  in:  {text!r}\n  out: {out!r}"
    print("  [PASS] clean doc unchanged (no false positives)")


def test_preserves_heading_with_body_text() -> None:
    """'OVERVIEW: This guide covers...' should NOT be stripped — has body text."""
    text = "OVERVIEW: This guide covers fertility nutrition.\n\nMore content."
    out = _strip_editor_metadata(text)
    assert "OVERVIEW: This guide covers" in out, f"colon-heading with body stripped: {out!r}"
    print("  [PASS] preserves heading-with-body (colon line that has content after)")


def test_preserves_section_markers() -> None:
    """Load-bearing [SECTION N] markers must survive even within head cap."""
    text = "[SECTION 1]\n\nFirst section content.\n\n[SECTION 2]\n\nMore content."
    out = _strip_editor_metadata(text)
    assert "[SECTION 1]" in out
    assert "[SECTION 2]" in out
    print("  [PASS] preserves [SECTION N] markers in head")


def test_preserves_image_markers() -> None:
    """Load-bearing [IMAGE #N: ...] markers must survive even within head cap."""
    text = "[IMAGE #1: REIMAGINED FERTILITY by Dr. Nashat Latib]\n\nBody."
    out = _strip_editor_metadata(text)
    assert "[IMAGE #1:" in out
    assert "REIMAGINED FERTILITY" in out
    print("  [PASS] preserves [IMAGE #N: ...] markers in head")


# -----------------------------------------------------------------------------
# Position cap — patterns past line 20 are preserved
# -----------------------------------------------------------------------------

def test_position_cap_preserves_late_pattern_match() -> None:
    """A 'COVER:' that appears at line 30 should NOT be stripped."""
    head_filler = "\n".join([f"Line {i} body content here." for i in range(25)])
    text = head_filler + "\n\nCOVER:\n\nMid-document content."
    out = _strip_editor_metadata(text)
    # The COVER: at line 27 (after 25 filler lines + 2 blanks) should survive
    assert "COVER:" in out, f"late-position COVER: was stripped: {out[-200:]!r}"
    print("  [PASS] position cap preserves matching pattern past line 20")


def test_position_cap_strips_early_pattern_match() -> None:
    """Same 'COVER:' at line 1 SHOULD be stripped."""
    text = "COVER:\n\nLine 1 body.\n\nLine 2 body."
    out = _strip_editor_metadata(text)
    assert "COVER:" not in out, f"early-position COVER: was preserved: {out!r}"
    assert "Line 1 body" in out
    print("  [PASS] position cap strips matching pattern at line 1")


# -----------------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------------

def test_empty_string_returns_empty() -> None:
    assert _strip_editor_metadata("") == ""
    print("  [PASS] empty string returns empty")


def test_no_pollution_no_changes() -> None:
    text = "Just a normal paragraph.\n\nAnother paragraph.\n\nAnd a third."
    assert _strip_editor_metadata(text) == text
    print("  [PASS] no-pollution input returns identical")


def test_collapses_excess_blank_lines_after_strip() -> None:
    """After stripping a polluted line, don't leave 3+ consecutive blanks."""
    text = "COVER:\n\n\n\nBody starts here."
    out = _strip_editor_metadata(text)
    # After strip: "" "" "" "" "Body starts here." → collapse 4 blanks to 2
    # Splitting that by newline shouldn't yield more than 2 consecutive empties.
    parts = out.split("\n")
    max_consec = 0
    cur = 0
    for p in parts:
        if p.strip() == "":
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0
    assert max_consec <= 2, f"found {max_consec} consecutive blanks: {out!r}"
    assert "Body starts here" in out
    print("  [PASS] collapses excess blank lines after strip")


# -----------------------------------------------------------------------------
# Wiring — opt-in flag (M-29-C.3)
# -----------------------------------------------------------------------------

def test_strip_helper_is_pure_no_op_on_clean_input() -> None:
    """Helper itself doesn't gate on a flag — gating happens in extract_from_html_bytes.
    But the helper should be safe to call multiple times and idempotent."""
    text = "Body content with no pollution at all."
    once = _strip_editor_metadata(text)
    twice = _strip_editor_metadata(once)
    assert once == twice == text, "strip should be idempotent"
    print("  [PASS] strip helper is idempotent on clean input")


def main() -> None:
    print("test_canva_strip_synthetic_s19.py")
    print("=" * 60)
    tests = [
        test_strips_canva_url_line,
        test_strips_bare_cover_tag,
        test_strips_page_tags,
        test_strips_header_footer_back_cover,
        test_strips_full_canva_pollution_block,
        test_clean_doc_no_changes,
        test_preserves_heading_with_body_text,
        test_preserves_section_markers,
        test_preserves_image_markers,
        test_position_cap_preserves_late_pattern_match,
        test_position_cap_strips_early_pattern_match,
        test_empty_string_returns_empty,
        test_no_pollution_no_changes,
        test_collapses_excess_blank_lines_after_strip,
        test_strip_helper_is_pure_no_op_on_clean_input,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print("=" * 60)
    print(f"  {len(tests) - failed}/{len(tests)} passing, {failed} failing")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
