"""PDF handler for v3 Drive loader.

Session 16 — first v3 handler. Implements the two PDF extraction paths
from D4 of docs/plans/2026-04-14-drive-loader-v3.md:

  1. Primary: pdfplumber native text extraction, one extract per page
  2. Fallback: rasterize each page to PNG via pypdfium2, hand to the
     shared GeminiVisionClient for OCR. Cache-keyed by SHA-256 so
     re-runs against the same scanned PDF cost $0.

Fallback trigger (Option A, chosen session 16, divergence from D4):
  Average extracted chars per page < 50.
  Rationale: D4's `extracted_chars / pdf_size_bytes < 5%` is HTML-tuned;
  PDFs have large non-text overhead (fonts, metadata, compression) so a
  byte-ratio threshold false-triggers on legitimate text PDFs. A per-page
  character floor is the correct measurement for this file type.

Marker convention (Option X, chosen session 16):
  Each page's extracted text is preceded by a [PAGE N] marker. The
  dispatcher's post-pass derives display_locator from these markers
  after chunk_text() runs Layer B scrub, then strips them before
  the chunk is written to Chroma.

Public interface:
  extract_from_path(path, *, vision_client=None, force_ocr=False)
      -> ExtractResult

  extract(drive_file, drive_client, config) -> ExtractResult
      -> dispatcher entrypoint (session 16 implements stub; full Drive
         download path is exercised during the Step 9 closure run)
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from ingester.loaders.types import (
    ExtractResult,
    make_page_marker,
)

log = logging.getLogger(__name__)


# Fallback trigger: if the mean characters-per-page on the native
# extraction is below this floor, the handler switches to vision OCR.
# See module docstring for the Option-A rationale.
MIN_CHARS_PER_PAGE_FLOOR = 50

# pypdfium2 render scale for OCR fallback. 2.0 ≈ 144 DPI, a good
# balance between OCR accuracy and vision-call input cost. Gemini
# 2.5 Flash charges on input tokens (image pixels → tokens), so
# cranking this higher directly increases cost.
OCR_RENDER_SCALE = 2.0


def extract_from_path(
    path: Path,
    *,
    vision_client=None,
    force_ocr: bool = False,
) -> ExtractResult:
    """Extract text from a PDF file on local disk.

    Args:
      path: local filesystem path to the PDF
      vision_client: optional pre-constructed GeminiVisionClient. If None
        and OCR fallback triggers, one is lazily constructed against
        the shared OCR cache dir. Passing a shared client lets the
        dispatcher roll up ledger totals across multiple PDFs in one run.
      force_ocr: if True, skip the native pdfplumber path entirely and
        OCR every page. Used by test_pdf_ocr_fallback_scrub in the
        scrub test suite — the synthetic scanned PDF it builds does in
        fact have low text yield, but force_ocr gives the test a
        deterministic trigger that doesn't depend on the heuristic.

    Returns:
      ExtractResult with stitched_text containing [PAGE N] markers
      between pages, extraction_method set to either 'pdf_text' or
      'pdf_ocr_fallback', and vision cost / image counters populated
      when the OCR path was used.
    """
    import pdfplumber  # lazy import

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages_text: list[str] = []
    pages_total = 0
    warnings: list[str] = []

    if not force_ocr:
        # ------------------------------------------------------------
        # Native path: pdfplumber page-by-page text extraction
        # ------------------------------------------------------------
        with pdfplumber.open(str(path)) as pdf:
            pages_total = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    txt = page.extract_text() or ""
                except Exception as e:  # noqa: BLE001
                    warnings.append(f"page {i} extract failed: {type(e).__name__}: {e}")
                    txt = ""
                pages_text.append(txt)


        total_chars = sum(len(t) for t in pages_text)
        mean_chars_per_page = total_chars / pages_total if pages_total else 0
        fallback_needed = (
            pages_total > 0
            and mean_chars_per_page < MIN_CHARS_PER_PAGE_FLOOR
        )

        if not fallback_needed:
            # Happy path: stitch native text with markers and return
            stitched = _stitch_with_markers(pages_text)
            return ExtractResult(
                stitched_text=stitched,
                extraction_method="pdf_text",
                source_unit_label="page",
                pages_total=pages_total,
                units_total=pages_total,
                warnings=warnings,
                extra={
                    "mean_chars_per_page": round(mean_chars_per_page, 1),
                    "total_native_chars": total_chars,
                },
            )

        # Fell through — native extraction came back thin, trigger OCR.
        warnings.append(
            f"low text yield ({mean_chars_per_page:.1f} chars/page < "
            f"{MIN_CHARS_PER_PAGE_FLOOR} floor) — falling back to vision OCR"
        )

    # ------------------------------------------------------------
    # OCR fallback path: rasterize each page, send to Gemini
    # ------------------------------------------------------------
    vision_client = _ensure_vision_client(vision_client)
    ocr_pages_text, images_seen, images_ocr_called = _ocr_all_pages(
        path, vision_client, warnings
    )
    if pages_total == 0:
        pages_total = len(ocr_pages_text)

    stitched = _stitch_with_markers(ocr_pages_text)
    return ExtractResult(
        stitched_text=stitched,
        extraction_method="pdf_ocr_fallback",
        source_unit_label="page",
        pages_total=pages_total,
        units_total=pages_total,
        images_seen=images_seen,
        images_ocr_called=images_ocr_called,
        vision_cost_usd=round(vision_client.ledger.vision_cost_usd, 6),
        warnings=warnings,
        extra={
            "mean_chars_per_page": 0.0 if not pages_total else sum(
                len(t) for t in ocr_pages_text
            ) / pages_total,
            "ocr_pages": len(ocr_pages_text),
        },
    )


# ----------------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------------

def _stitch_with_markers(pages_text: list[str]) -> str:
    """Join per-page extracted text with [PAGE N] markers between pages.

    Empty pages still get a marker so the dispatcher's locator derivation
    sees a uniform structure — but they contribute no content. Pages that
    failed to extract at all produce a single marker with no body text,
    which is fine because chunk_text() will simply collapse the whitespace.
    """
    parts: list[str] = []
    for i, text in enumerate(pages_text, start=1):
        marker = make_page_marker("PAGE", i)
        body = (text or "").strip()
        if body:
            parts.append(f"{marker}\n\n{body}")
        else:
            parts.append(marker)
    return "\n\n".join(parts)


def _ensure_vision_client(vision_client):
    """If the caller didn't pass a vision client, construct one against
    the shared OCR cache directory. This path is only used by standalone
    handler tests; the dispatcher always passes its own client."""
    if vision_client is not None:
        return vision_client
    from ingester.vision.gemini_client import GeminiVisionClient
    from ingester.vision.ocr_cache import OcrCache
    # Match v2's OCR_CACHE_DIR to share the 28-file cache
    repo_root = Path(__file__).resolve().parents[3]
    cache_dir = repo_root / "data" / "image_ocr_cache"
    cache = OcrCache(cache_dir)
    return GeminiVisionClient(cache)


def _ocr_all_pages(
    path: Path,
    vision_client,
    warnings: list[str],
) -> tuple[list[str], int, int]:
    """Rasterize each page via pypdfium2, OCR through the shared Gemini
    client. Returns (per_page_text, images_seen, images_ocr_called).

    Images failures don't abort — v2's OcrResult contract says .failed=True
    returns an empty ocr_text string, so a failed page just yields no
    text and a warning is recorded. The dispatcher's quarantine logic
    (D12) handles the case where OCR fails on enough pages to make the
    whole file useless.
    """
    import pypdfium2 as pdfium

    pages_text: list[str] = []
    images_seen_start = vision_client.ledger.images_seen
    images_ocr_start = vision_client.ledger.images_ocr_called

    pdf = pdfium.PdfDocument(str(path))
    try:
        for i, page in enumerate(pdf, start=1):
            try:
                pil_image = page.render(scale=OCR_RENDER_SCALE).to_pil()
                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                png_bytes = buf.getvalue()
            except Exception as e:  # noqa: BLE001
                warnings.append(
                    f"page {i} raster failed: {type(e).__name__}: {e}"
                )
                pages_text.append("")
                continue

            ocr_result = vision_client.ocr_image(
                png_bytes, mime_type="image/png", use_cache=True
            )
            if ocr_result.failed:
                warnings.append(
                    f"page {i} OCR failed: {ocr_result.failure_reason}"
                )
                pages_text.append("")
            elif ocr_result.is_decorative:
                pages_text.append("")
            else:
                pages_text.append(ocr_result.ocr_text)
    finally:
        pdf.close()

    images_seen = vision_client.ledger.images_seen - images_seen_start
    images_ocr_called = vision_client.ledger.images_ocr_called - images_ocr_start
    return pages_text, images_seen, images_ocr_called


# ----------------------------------------------------------------------------
# Dispatcher entrypoint
# ----------------------------------------------------------------------------

def extract(drive_file: dict, drive_client, config) -> ExtractResult:
    """Dispatcher entrypoint — downloads the Drive file to a temp path,
    delegates to extract_from_path(), returns the ExtractResult.

    `drive_file` is the Drive API metadata dict (id, name, mimeType, ...).
    `drive_client` is the v1/v2 DriveClient wrapper.
    `config` is a handler-specific config object passed through from
    the dispatcher; session 16 ignores it because pdf_handler has no
    tunable knobs beyond force_ocr (which is test-only). Kept in the
    signature so future handlers match the D3 shape.
    """
    import tempfile

    file_id = drive_file["id"]
    file_name = drive_file.get("name", file_id)

    # Download binary to a temp path. Drive's get_media returns raw bytes
    # for non-Google-Docs MIME types.
    data = drive_client.download_file_bytes(file_id)
    with tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix="v3_pdf_"
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        vision_client = getattr(config, "vision_client", None) if config else None
        result = extract_from_path(tmp_path, vision_client=vision_client)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    # Tag extra with Drive-side metadata for diagnostics
    result.extra["drive_file_id"] = file_id
    result.extra["drive_file_name"] = file_name
    return result
