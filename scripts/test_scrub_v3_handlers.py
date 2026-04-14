"""Session 16 — scrub validation for v3 PDF handler.

Per D6 in docs/plans/2026-04-14-drive-loader-v3.md, every v3 handler ships
with a scrub validation test that proves the handler's extracted text
flows through _drive_common.chunk_text() and Layer B scrub fires on
collaborator patterns in the extracted prose.

This file holds the PDF handler's two required test cases. Future
handlers (image, docx, slides, sheets, plaintext, AV) each append a
section to this same file — one file, one canonical test for every v3
handler.

Usage:
    ./venv/bin/python scripts/test_scrub_v3_handlers.py

Expected (session 16 TDD status):
    - Step 3: this file exists but tests FAIL (pdf_handler not built yet)
    - Step 5: pdf_handler built, both tests PASS
    - Step 9 onward: tests continue to PASS on every future session

The two PDF tests are:
    1. Native text path — synthetic PDF with selectable text containing
       "Dr. Christina Massinople". pdfplumber extracts, chunk_text scrubs,
       at least one chunk shows name_replacements >= 1 and no chunk
       contains "Christina" or "Massinople".
    2. OCR fallback path — synthetic PDF where the same pattern is
       rendered as an image (no selectable text layer, so pdfplumber
       yields < 5% text, triggering vision OCR fallback). Extracted OCR
       text flows through chunk_text, same assertions hold.
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path

# sys.path shim — matches the pattern used by scripts/test_login_dan.py (s15)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingester.loaders._drive_common import chunk_text

# PDF handler is a session 16 Step 5 deliverable. Import lazily inside each
# test so this file can be run at Step 3 (TDD: tests FAIL with a clear
# ImportError until Step 5 lands the handler).

SCRUB_PATTERN_NATIVE = (
    "This reference document on fertility supplements was co-authored by "
    "Dr. Nashat Latib and Dr. Christina Massinople, with clinical input "
    "from Dr. Chris on progesterone dosing. "
)
# Repeat enough to clear MIN_CHUNK_WORDS floor
SCRUB_BODY_NATIVE = (
    "Vitamin D3 supports healthy ovulatory function and luteal phase length. "
    "Typical starting doses range from 2000 IU to 5000 IU daily depending "
    "on baseline 25-OH vitamin D status. Supplementation should be paired "
    "with adequate magnesium intake. "
) * 8

SCRUB_PATTERN_OCR = (
    "Egg quality protocol co-developed by Dr. Nashat Latib and "
    "Dr. Christina Massinople. See Dr. Chris note on CoQ10 timing."
)


def _assert_scrubbed(chunks, label):
    """Shared assertion helper: no collaborator name leakage + at least
    one chunk shows scrub fired."""
    assert len(chunks) > 0, f"[{label}] chunk_text returned zero chunks"
    joined = " ".join(c["text"] for c in chunks)
    assert "Christina" not in joined, f"[{label}] 'Christina' leaked through scrub"
    assert "Massinople" not in joined, f"[{label}] 'Massinople' leaked through scrub"
    assert "Dr. Chris" not in joined, f"[{label}] 'Dr. Chris' leaked through scrub"
    assert any(c["name_replacements"] > 0 for c in chunks), (
        f"[{label}] no chunk had name_replacements > 0 — scrub did not fire"
    )


def _build_native_text_pdf(path: Path, text: str) -> None:
    """Build a synthetic PDF with a real text layer. Uses reportlab's
    canvas; text is selectable and pdfplumber can extract it directly."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as rl_canvas
    c = rl_canvas.Canvas(str(path), pagesize=letter)
    # Wrap text into lines that fit page width (naive 90-char wrap)
    lines: list[str] = []
    for paragraph in text.split("\n\n"):
        words = paragraph.split()
        line = ""
        for w in words:
            if len(line) + len(w) + 1 > 90:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w) if line else w
        if line:
            lines.append(line)
        lines.append("")  # paragraph break
    y = 720
    for ln in lines:
        if y < 60:
            c.showPage()
            y = 720
        c.drawString(60, y, ln)
        y -= 14
    c.save()


def _build_scanned_pdf(path: Path, text: str) -> None:
    """Build a synthetic PDF where the text is rasterized as an image,
    so there is effectively no selectable text layer and the PDF handler's
    low-text-yield guard will trip, forcing the vision OCR fallback path.

    Strategy: render text onto a PIL Image, paste that image into the PDF
    via reportlab's drawImage. No text is drawn directly on the canvas.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 28
        )
    except Exception:
        font = ImageFont.load_default()
    # Naive wrap
    words = text.split()
    lines, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > 50:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w) if line else w
    if line:
        lines.append(line)
    y = 60
    for ln in lines:
        draw.text((60, y), ln, fill="black", font=font)
        y += 40

    c = rl_canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(ImageReader(img), 40, 80, width=530, height=700)
    c.save()


def test_pdf_native_text_scrub() -> str:
    """Test 1: pdfplumber native path. Build a PDF with selectable text
    containing a collaborator pattern, hand it to the PDF handler, confirm
    the extracted stitched text flows through chunk_text() and scrub fires.
    """
    # Deferred import — will raise ImportError until Step 5 lands the handler.
    from ingester.loaders.types import pdf_handler

    full_text = SCRUB_PATTERN_NATIVE + "\n\n" + SCRUB_BODY_NATIVE
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "native.pdf"
        _build_native_text_pdf(pdf_path, full_text)
        result = pdf_handler.extract_from_path(pdf_path)
        assert result.extraction_method == "pdf_text", (
            f"expected pdf_text method, got {result.extraction_method}"
        )
        chunks = chunk_text(result.stitched_text)
        _assert_scrubbed(chunks, "pdf_native")
    return "PASS"


def test_pdf_ocr_fallback_scrub() -> str:
    """Test 2: vision OCR fallback path. Build a PDF whose text is
    rasterized (no selectable text layer), confirm the handler's fallback
    triggers, OCR extracts the pattern, chunk_text scrubs it.

    This test calls Vertex AI Gemini 2.5 Flash and costs ~$0.0003. It is
    gated on GOOGLE_APPLICATION_CREDENTIALS being set; if not, it SKIPs
    rather than failing, because the scrub path is the same code regardless
    of whether the text came from pdfplumber or OCR — what this test
    uniquely proves is that the fallback trigger works and the OCR text
    reaches the chokepoint.
    """
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return "SKIP (no GOOGLE_APPLICATION_CREDENTIALS set)"

    from ingester.loaders.types import pdf_handler

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "scanned.pdf"
        _build_scanned_pdf(pdf_path, SCRUB_PATTERN_OCR)
        result = pdf_handler.extract_from_path(pdf_path)
        assert result.extraction_method == "pdf_ocr_fallback", (
            f"expected pdf_ocr_fallback method, got {result.extraction_method}"
        )
        chunks = chunk_text(result.stitched_text)
        _assert_scrubbed(chunks, "pdf_ocr")
    return "PASS"


def main() -> int:
    tests = [
        ("pdf_native_text_scrub", test_pdf_native_text_scrub),
        ("pdf_ocr_fallback_scrub", test_pdf_ocr_fallback_scrub),
    ]
    results: list[tuple[str, str, str]] = []
    for name, fn in tests:
        try:
            outcome = fn()
            results.append((name, outcome, ""))
        except AssertionError as e:
            results.append((name, "FAIL", str(e)))
        except ImportError as e:
            results.append((name, "FAIL (import)", str(e)))
        except Exception as e:  # noqa: BLE001 — test harness
            tb = traceback.format_exc().strip().splitlines()[-1]
            results.append((name, "ERROR", f"{type(e).__name__}: {tb}"))

    print("=" * 60)
    print("v3 handler scrub tests")
    print("=" * 60)
    pass_count = 0
    fail_count = 0
    skip_count = 0
    for name, outcome, detail in results:
        line = f"  {name:30s} {outcome}"
        if detail:
            line += f"\n    -> {detail}"
        print(line)
        if outcome == "PASS":
            pass_count += 1
        elif outcome.startswith("SKIP"):
            skip_count += 1
        else:
            fail_count += 1
    total = len(results)
    print("-" * 60)
    print(f"  {pass_count}/{total} passing, {skip_count} skipped, {fail_count} failing")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
