"""Google Doc handler for v3 Drive loader (session 17, BACKLOG #11).

This module is the single source of truth for Google Doc ingestion in
both v2 and v3. Session 17 extracted this code from
`drive_loader_v2.py` (where it was previously inline in `run()`) so
that v3's dispatcher can route Google Docs through the same code path
PDFs use, without duplicating the HTML-export + image-OCR logic.

M3 design (session 17 BACKLOG #11):
  - This module owns `export_html`, `resolve_image_bytes`,
    `walk_html_in_order`, and `stitch_stream`. v2 imports them from
    here for backward compatibility — v2 still uses them inside its
    own `run()` orchestrator.
  - v3's dispatcher calls `extract(drive_file, drive_client, config)`,
    which downloads the HTML and delegates to `extract_from_html_bytes`.

L3 design (session 17, locator markers):
  - Google Docs have no pages, but they do have headings (h1-h6).
  - When `emit_section_markers=True`, `walk_html_in_order` emits a
    `{kind: "heading", level, text}` entry at every heading, and
    `stitch_stream` inserts a `[SECTION N]` marker before the heading
    body. The dispatcher's `chunk_with_locators` post-pass derives
    `display_locator` (e.g., "§3" or "§§2-4") from these markers
    and strips them before chunks are written.
  - When `emit_section_markers=False` (the v2 default), no markers
    are inserted and behavior is byte-identical to pre-session-17 v2.
    v2's 13 existing chunks have empty `display_locator`; this default
    preserves that.

Marker convention (Option X, session 16):
  Section markers are `[SECTION N]` per the format defined in
  `ingester/loaders/types/__init__.py`. Layer B scrub does not touch
  this token (no alphabetic name patterns, no "Dr." prefix), so it
  survives `chunk_text()` and is consumed by `derive_locator` after
  scrub runs.

Public interface:
  extract_from_html_bytes(html_bytes, *, drive_client, vision_client,
                          use_cache=True, emit_section_markers=False)
      -> ExtractResult

  extract(drive_file, drive_client, config) -> ExtractResult
      -> dispatcher entrypoint. Calls export_html() then
         extract_from_html_bytes(emit_section_markers=True).
"""

from __future__ import annotations

import html as html_module
import io
import logging
from typing import TYPE_CHECKING, Optional

from ingester.loaders.types import (
    ExtractResult,
    make_page_marker,
)

if TYPE_CHECKING:
    from ingester.drive_client import DriveClient
    from ingester.vision.gemini_client import GeminiVisionClient

log = logging.getLogger(__name__)


# HTML tags whose text contents we skip entirely (metadata/styling).
# Moved here from drive_loader_v2 in session 17 (BACKLOG #11 / M3).
HTML_SKIP_TAGS = {"head", "style", "script", "meta", "link", "title"}


# ----------------------------------------------------------------------------
# Drive HTML export
# ----------------------------------------------------------------------------

def export_html(client, file_id: str) -> bytes:
    """Export a Google Doc as HTML. Returns raw bytes.

    Lifted from drive_loader_v2 in session 17 unchanged. v2 still
    imports this function from here for its own `run()` orchestrator.
    """
    request = client._service.files().export_media(
        fileId=file_id, mimeType="text/html"
    )
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def resolve_image_bytes(client, src: str) -> tuple[bytes, str]:
    """
    Resolve an image src attribute from a Google Doc HTML export into
    (bytes, mime_type).

    Google Docs HTML export inlines images as base64 data URIs — this
    is the common case and requires no network call. We handle that
    path first. As a fallback for any doc that embeds an absolute URL,
    we fetch via the DriveClient's authorized http session.

    Raises RuntimeError on malformed data URIs or HTTP failures.

    Lifted from drive_loader_v2 in session 17 unchanged.
    """
    import base64

    if src.startswith("data:"):
        try:
            header, payload = src.split(",", 1)
        except ValueError:
            raise RuntimeError("Malformed data URI (no comma)")
        meta = header[5:]  # strip "data:"
        if ";base64" in meta:
            mime = meta.split(";base64")[0] or "image/png"
            try:
                img_bytes = base64.b64decode(payload)
            except Exception as e:
                raise RuntimeError(f"Base64 decode failed: {e}")
        else:
            from urllib.parse import unquote_to_bytes
            mime = meta or "image/png"
            img_bytes = unquote_to_bytes(payload)
        return img_bytes, mime

    if src.startswith(("http://", "https://")):
        http = client._service._http
        resp, content = http.request(src, method="GET")
        status = int(resp.get("status", 0))
        if status != 200:
            raise RuntimeError(f"Image fetch failed: HTTP {status}")
        mime = resp.get("content-type", "image/png").split(";")[0].strip()
        return content, mime

    raise RuntimeError(f"Unsupported image src scheme: {src[:40]}")


# ----------------------------------------------------------------------------
# HTML stream walk
# ----------------------------------------------------------------------------

# Block-level container tags that produce one paragraph in the stream.
# Headings are intentionally NOT in this set because they get special
# treatment when emit_section_markers=True — they emit a {kind: "heading"}
# entry first, then their text content.
_BLOCK_TAGS_NON_HEADING = {
    "p", "li", "div", "td", "th", "blockquote", "pre",
}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS_ALL = _BLOCK_TAGS_NON_HEADING | _HEADING_TAGS


def walk_html_in_order(
    html_bytes: bytes,
    *,
    emit_section_markers: bool = False,
) -> list[dict]:
    """
    Parse Google Doc HTML export and return an ordered stream of
    {kind: "text"|"image"|"heading", ...} dicts, preserving document order.

    Args:
      html_bytes: raw HTML bytes from Drive export.
      emit_section_markers: when True, headings (h1-h6) emit a
        {kind: "heading", level: int, text: str} entry in addition to
        being processed as a normal block. When False (v2 default),
        headings are processed as normal blocks only — no separate
        heading entries — yielding byte-identical behavior to v2.

    Lifted and lightly amended from drive_loader_v2 in session 17.
    The L3 amendment is small: a single new branch in the recurse()
    function that checks for heading tags and emits a heading entry
    before falling through to normal block handling.
    """
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(html_bytes, "html.parser")
    body = soup.body or soup

    stream: list[dict] = []

    def recurse(node):
        # Skip metadata/styling subtrees entirely
        if hasattr(node, "name") and node.name in HTML_SKIP_TAGS:
            return

        # Handle <img> tag directly (do not recurse into children)
        if hasattr(node, "name") and node.name == "img":
            src = node.get("src", "")
            alt = node.get("alt", "") or ""
            if src:
                stream.append({"kind": "image", "src": src, "alt": alt})
            return

        # L3 amendment: emit a heading entry for h1-h6 BEFORE the normal
        # block-level handling that follows. Only when the caller asked
        # for section markers; v2 default is False so v2 behavior is
        # byte-identical to pre-session-17.
        if (
            emit_section_markers
            and hasattr(node, "name")
            and node.name in _HEADING_TAGS
        ):
            try:
                level = int(node.name[1])
            except (ValueError, IndexError):
                level = 1
            heading_text = node.get_text(separator=" ", strip=True)
            stream.append({
                "kind": "heading",
                "level": level,
                "text": heading_text,
            })
            # Fall through — the normal block handler below also processes
            # this node and emits its text as a paragraph. That's what
            # v2 did for headings, so we preserve it.

        # Block-level containers that represent paragraphs in Docs HTML
        # export. Note: _BLOCK_TAGS_ALL includes h1-h6 so heading text
        # still emits as a paragraph after the heading entry above.
        if hasattr(node, "name") and node.name in _BLOCK_TAGS_ALL:
            text_buf: list[str] = []
            for child in node.children:
                if isinstance(child, NavigableString):
                    s = str(child)
                    if s.strip():
                        text_buf.append(s)
                elif hasattr(child, "name"):
                    if child.name == "img":
                        if text_buf:
                            stream.append({
                                "kind": "text",
                                "text": " ".join(text_buf),
                            })
                            text_buf = []
                        src = child.get("src", "")
                        alt = child.get("alt", "") or ""
                        if src:
                            stream.append({"kind": "image", "src": src, "alt": alt})
                    elif child.name in HTML_SKIP_TAGS:
                        continue
                    else:
                        if child.find("img"):
                            if text_buf:
                                stream.append({
                                    "kind": "text",
                                    "text": " ".join(text_buf),
                                })
                                text_buf = []
                            recurse(child)
                        else:
                            t = child.get_text()
                            if t.strip():
                                text_buf.append(t)
            if text_buf:
                stream.append({"kind": "text", "text": " ".join(text_buf)})
            return

        # Fallback: recurse into any other container
        if hasattr(node, "children"):
            for child in node.children:
                if isinstance(child, NavigableString):
                    s = str(child).strip()
                    if s:
                        stream.append({"kind": "text", "text": s})
                elif hasattr(child, "name"):
                    recurse(child)

    recurse(body)
    return stream


# ----------------------------------------------------------------------------
# Stream stitch + image OCR
# ----------------------------------------------------------------------------

def stitch_stream(
    stream: list[dict],
    vision_client,
    drive_client,
    use_cache: bool,
    *,
    emit_section_markers: bool = False,
) -> tuple[str, int, list[dict], int]:
    """
    Walk the ordered stream, OCR images, and produce a single stitched
    text string with [IMAGE #N: ...] markers inserted at image positions
    and (optionally) [SECTION N] markers inserted at headings.

    Returns (stitched_text, image_count, per_image_records, section_count).

    `per_image_records` is for the dump-json inspection artifact.
    `section_count` is the number of [SECTION N] markers emitted (zero
    when emit_section_markers=False).

    Lifted from drive_loader_v2 in session 17 with one amendment: when
    emit_section_markers=True, encountering a {kind: "heading"} stream
    entry increments a section counter and inserts a [SECTION N] marker.
    The marker format matches PAGE_MARKER_RE in types/__init__.py so the
    dispatcher's post-pass can derive display_locator from it.
    """
    parts: list[str] = []
    image_count = 0
    section_count = 0
    per_image: list[dict] = []

    for entry in stream:
        kind = entry["kind"]

        if kind == "heading":
            # Only emitted when emit_section_markers=True (walk_html_in_order
            # gates this), but check anyway for defensiveness.
            if emit_section_markers:
                section_count += 1
                marker = make_page_marker("SECTION", section_count)
                parts.append(marker)
            # Note: the heading's own text is emitted by the subsequent
            # text block (walk_html_in_order falls through after emitting
            # the heading entry), not by this branch. This keeps the
            # marker positioned immediately before the heading text.
            continue

        if kind == "text":
            txt = html_module.unescape(entry["text"])
            if txt.strip():
                parts.append(txt)
            continue

        if kind == "image":
            image_count += 1
            src = entry["src"]
            alt = entry.get("alt", "")
            record = {
                "index": image_count,
                "src_prefix": src[:80],
                "alt": alt,
            }
            try:
                img_bytes, img_mime = resolve_image_bytes(drive_client, src)
                record["byte_size"] = len(img_bytes)
                record["mime_type"] = img_mime
            except Exception as e:
                reason = str(e)[:80]
                record["download_failed"] = reason
                parts.append(f"\n\n[IMAGE #{image_count}: DOWNLOAD_FAILED — {reason}]\n\n")
                per_image.append(record)
                continue

            ocr = vision_client.ocr_image(img_bytes, img_mime, use_cache=use_cache)
            record["sha256"] = ocr.sha256
            record["is_decorative"] = ocr.is_decorative
            record["failed"] = ocr.failed
            record["ocr_text_preview"] = ocr.ocr_text[:200]
            record["vision_input_tokens"] = ocr.vision_input_tokens
            record["vision_output_tokens"] = ocr.vision_output_tokens

            if ocr.is_decorative:
                # Drop from stream entirely
                pass
            elif ocr.failed:
                parts.append(
                    f"\n\n[IMAGE #{image_count}: OCR_FAILED — {ocr.failure_reason}]\n\n"
                )
            else:
                parts.append(
                    f"\n\n[IMAGE #{image_count}: {ocr.ocr_text.strip()}]\n\n"
                )
            per_image.append(record)
            continue

    stitched = "\n\n".join(parts)
    return stitched, image_count, per_image, section_count


# ----------------------------------------------------------------------------
# extract_from_html_bytes — the main M3 entrypoint
# ----------------------------------------------------------------------------

def extract_from_html_bytes(
    html_bytes: bytes,
    *,
    drive_client,
    vision_client,
    use_cache: bool = True,
    emit_section_markers: bool = False,
) -> ExtractResult:
    """Extract text from a Google Doc HTML export.

    Walks the HTML in document order, OCRs embedded images via the shared
    Gemini vision client, and produces a stitched text representation
    with [IMAGE #N: ...] markers at image positions. Optionally inserts
    [SECTION N] markers at headings (L3 mode).

    Args:
      html_bytes: raw HTML from Drive's text/html export.
      drive_client: DriveClient for image URL fallback (data URIs are
        the common path and don't hit the network).
      vision_client: shared GeminiVisionClient. The caller (v2's run()
        or v3's dispatcher) constructs this once per run so the ledger
        rolls up across files.
      use_cache: pass-through to vision_client.ocr_image. False bypasses
        the OCR cache for re-runs that should re-call Gemini.
      emit_section_markers: when True (v3 default), inserts [SECTION N]
        markers at headings so the dispatcher can derive display_locator.
        When False (v2 default), behavior is byte-identical to pre-
        session-17 v2.

    Returns:
      ExtractResult with stitched_text, extraction_method set to
      "google_doc_html_vision", source_unit_label set to "section" if
      markers were emitted (None otherwise), images_seen / vision_cost
      populated from the vision ledger delta, and extra carrying the
      v2-shape per_image_records so v2's dump-json can use them.
    """
    pre_seen = vision_client.ledger.images_seen
    pre_called = vision_client.ledger.images_ocr_called
    pre_cost = vision_client.ledger.vision_cost_usd

    stream = walk_html_in_order(html_bytes, emit_section_markers=emit_section_markers)

    stitched, image_count, per_image_records, section_count = stitch_stream(
        stream,
        vision_client,
        drive_client,
        use_cache=use_cache,
        emit_section_markers=emit_section_markers,
    )

    delta_seen = vision_client.ledger.images_seen - pre_seen
    delta_called = vision_client.ledger.images_ocr_called - pre_called
    delta_cost = vision_client.ledger.vision_cost_usd - pre_cost

    return ExtractResult(
        stitched_text=stitched,
        extraction_method="google_doc_html_vision",
        source_unit_label="section" if emit_section_markers else None,
        pages_total=0,  # Google Docs have no pages
        units_total=section_count,
        images_seen=delta_seen,
        images_ocr_called=delta_called,
        vision_cost_usd=round(delta_cost, 6),
        warnings=[],
        extra={
            # v2's run() reads per_image_records from extra to populate
            # its dump-json artifact. Keep this contract stable.
            "per_image_records": per_image_records,
            "image_count_in_stream": image_count,
            "section_count": section_count,
        },
    )


# ----------------------------------------------------------------------------
# Dispatcher entrypoint (called by drive_loader_v3._dispatch_file)
# ----------------------------------------------------------------------------

def extract(drive_file: dict, drive_client, config) -> ExtractResult:
    """Dispatcher entrypoint — exports the Google Doc as HTML and
    delegates to extract_from_html_bytes() with section markers enabled.

    `drive_file` is the Drive API metadata dict (id, name, mimeType, ...).
    `drive_client` is the v1/v2 DriveClient wrapper.
    `config` carries the shared `vision_client` and (optionally) a
    `use_cache` flag. Same shim shape as pdf_handler.extract.
    """
    file_id = drive_file["id"]
    file_name = drive_file.get("name", file_id)

    vision_client = getattr(config, "vision_client", None) if config else None
    if vision_client is None:
        raise RuntimeError(
            "google_doc_handler.extract requires config.vision_client; "
            "the dispatcher must construct one and pass it via the shim."
        )
    use_cache = getattr(config, "use_cache", True) if config else True

    html_bytes = export_html(drive_client, file_id)

    result = extract_from_html_bytes(
        html_bytes,
        drive_client=drive_client,
        vision_client=vision_client,
        use_cache=use_cache,
        emit_section_markers=True,  # v3 default — populate display_locator
    )

    # Tag extra with Drive-side metadata for diagnostics, matching pdf_handler
    result.extra["drive_file_id"] = file_id
    result.extra["drive_file_name"] = file_name
    result.extra["html_bytes"] = len(html_bytes)
    return result
