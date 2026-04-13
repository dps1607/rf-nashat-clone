"""
Drive Loader v2 — HTML export + Gemini vision OCR.

Ingests image-heavy Google Docs that v1's text/plain export cannot
handle, by switching to text/html export, OCR-ing each embedded image
via Gemini 2.5 Flash (Vertex AI), and stitching the descriptions back
into the document stream before chunking.

Design doc: docs/plans/2026-04-13-drive-loader-v2.md

CLI:
    python3 -m ingester.loaders.drive_loader_v2 \\
        [--selection-file PATH]    (default: data/selection_state.json)
        [--folder-id ID]            (filter to one folder; recommended for pilot)
        [--dry-run | --commit]      (default: --dry-run)
        [--dump-json PATH]          (dry-run inspection artifact)
        [--no-cache]                (bypass OCR cache — re-call Gemini on every image)
        [--allow-strategic-spend]   (override the $25 hard-refuse gate)
        [--verbose]

Hard rules (same as v1 plus vision gates):
  - REFUSES /data/ Chroma paths (Railway guard)
  - REFUSES placeholder selection, missing assignments, non-allowed libraries
  - --dry-run is default; --commit must be explicit
  - Vision cost > $1.00 in commit mode requires interactive y/N
  - Vision cost > $25.00 in commit mode requires --allow-strategic-spend
  - Per-file vision failure rate > 20% → skip file as vision_failure_rate_too_high
"""

from __future__ import annotations

import argparse
import html as html_module
import io
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingester.drive_client import DriveClient
from ingester import config as ingester_config
from ingester.loaders._drive_common import (
    ALLOWED_LIBRARIES,
    SUPPORTED_GOOGLE_DOC,
    EMBEDDING_PRICE_PER_1M_TOKENS_USD,
    APPROX_CHARS_PER_TOKEN,
    COST_WARNING_THRESHOLD_USD,
    LOW_YIELD_RATIO_THRESHOLD,
    LOW_YIELD_MIN_BYTES,
    DEFAULT_SELECTION_FILE,
    load_latest_manifest,
    lookup_folder_in_manifest,
    normalize_text,
    word_count,
    chunk_text,
    build_chunk_id,
    build_metadata_base,
    assert_local_chroma_path,
    load_and_validate_selection,
)
from ingester.vision.gemini_client import GeminiVisionClient
from ingester.vision.ocr_cache import OcrCache

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

SOURCE_PIPELINE = "drive_loader_v2"

# Cost gates (match session 11 prompt's numbers)
VISION_COST_INTERACTIVE_GATE_USD = 1.00
VISION_COST_HARD_GATE_USD = 25.00

# Per-file vision failure rate ceiling
VISION_FAILURE_RATE_CEILING = 0.20  # 20%
VISION_FAILURE_MIN_IMAGES = 5  # only apply rate check to files with >=5 images

# OCR cache on disk
OCR_CACHE_DIR = _REPO_ROOT / "data" / "image_ocr_cache"

# HTML tags whose text contents we skip entirely (metadata/styling)
HTML_SKIP_TAGS = {"head", "style", "script", "meta", "link", "title"}


# -----------------------------------------------------------------------------
# HTML export + parsing
# -----------------------------------------------------------------------------

def export_html(client: DriveClient, file_id: str) -> bytes:
    """Export a Google Doc as HTML. Returns raw bytes."""
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


def resolve_image_bytes(client: DriveClient, src: str) -> tuple[bytes, str]:
    """
    Resolve an image src attribute from a Google Doc HTML export into
    (bytes, mime_type).

    Google Docs HTML export inlines images as base64 data URIs — this
    is the common case and requires no network call. We handle that
    path first. As a fallback for any doc that embeds an absolute URL,
    we fetch via the DriveClient's authorized http session.

    Raises RuntimeError on malformed data URIs or HTTP failures.
    """
    import base64

    if src.startswith("data:"):
        # Format: data:<mime>;base64,<payload>
        try:
            header, payload = src.split(",", 1)
        except ValueError:
            raise RuntimeError(f"Malformed data URI (no comma)")
        # header is like "data:image/png;base64"
        meta = header[5:]  # strip "data:"
        if ";base64" in meta:
            mime = meta.split(";base64")[0] or "image/png"
            try:
                img_bytes = base64.b64decode(payload)
            except Exception as e:
                raise RuntimeError(f"Base64 decode failed: {e}")
        else:
            # URL-encoded, rare for image exports but handle it
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


def walk_html_in_order(html_bytes: bytes) -> list[dict]:
    """
    Parse Google Doc HTML export and return an ordered stream of
    {kind: 'text'|'image', ...} dicts, preserving document order.

    BeautifulSoup walks the body in tree order; we emit text_with_paragraphs
    and <img> tags as we encounter them.
    """
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(html_bytes, "html.parser")
    body = soup.body or soup  # Docs exports always have a body, but be safe

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

        # For block-level containers that represent paragraphs in Docs
        # HTML export (p, h1-h6, li), emit their combined text as one
        # paragraph after recursing children. But we need to keep image
        # order inside those blocks. Strategy: recurse children; any
        # text collected via NavigableString along the way gets buffered
        # per-block and flushed when the block closes.
        if hasattr(node, "name") and node.name in {
            "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "td", "th",
            "blockquote", "pre",
        }:
            # Extract direct text, but also walk children in order so
            # images embedded inside the block appear at the right spot.
            # We do a mini-walk that intersperses text and image stream entries.
            text_buf: list[str] = []
            for child in node.children:
                if isinstance(child, NavigableString):
                    s = str(child)
                    if s.strip():
                        text_buf.append(s)
                elif hasattr(child, "name"):
                    if child.name == "img":
                        # Flush any buffered text as a paragraph first
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
                        # Inline element — recurse, which may add its own stream entries
                        # For inline text (span, a, b, i, etc.) we want the text inline,
                        # not as a separate paragraph. Use get_text to collect, then
                        # check for nested images.
                        if child.find("img"):
                            # Has nested images — flush buffer and recurse properly
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


def stitch_stream(
    stream: list[dict],
    vision_client: GeminiVisionClient,
    drive_client: DriveClient,
    use_cache: bool,
) -> tuple[str, int, list[dict]]:
    """
    Walk the ordered stream, OCR images, and produce a single stitched
    text string with [IMAGE #N: ...] markers inserted at image positions.

    Returns (stitched_text, image_count, per_image_records).
    `per_image_records` is for the dump-json inspection artifact.
    """
    parts: list[str] = []
    image_count = 0
    per_image: list[dict] = []

    for entry in stream:
        if entry["kind"] == "text":
            txt = html_module.unescape(entry["text"])
            if txt.strip():
                parts.append(txt)
        elif entry["kind"] == "image":
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

    stitched = "\n\n".join(parts)
    return stitched, image_count, per_image


def count_image_words_in_chunk(chunk_text_str: str) -> int:
    """
    Count words inside [IMAGE #N: ...] markers within a chunk. Used to
    populate the v2 metadata field `image_derived_word_count`.
    """
    import re
    total = 0
    for match in re.finditer(r"\[IMAGE #\d+: (.*?)\]", chunk_text_str, re.DOTALL):
        total += word_count(match.group(1))
    return total


# -----------------------------------------------------------------------------
# Metadata builder
# -----------------------------------------------------------------------------

def build_metadata_v2(
    chunk: dict,
    file_record: dict,
    folder_record: dict,
    library: str,
    ingest_run_id: str,
    ingest_timestamp_utc: str,
) -> dict:
    base = build_metadata_base(
        chunk, file_record, folder_record, library,
        ingest_run_id, ingest_timestamp_utc,
        source_pipeline=SOURCE_PIPELINE,
    )
    base["image_derived_word_count"] = count_image_words_in_chunk(chunk["text"])
    return base


# -----------------------------------------------------------------------------
# Cost projection
# -----------------------------------------------------------------------------

def project_vision_cost(image_count: int) -> float:
    """
    Rough upper-bound cost projection BEFORE we've called Gemini, used
    for the pre-spend gate. Assumes ~516 input tokens and ~300 output
    tokens per image as a worst-case heuristic (Canva infographic).
    """
    est_input = image_count * 600
    est_output = image_count * 300
    from ingester.vision.gemini_client import (
        VISION_INPUT_PRICE_PER_1M, VISION_OUTPUT_PRICE_PER_1M,
    )
    return (
        est_input / 1_000_000 * VISION_INPUT_PRICE_PER_1M
        + est_output / 1_000_000 * VISION_OUTPUT_PRICE_PER_1M
    )


# -----------------------------------------------------------------------------
# Main run
# -----------------------------------------------------------------------------

def run(
    selection_file: Path,
    folder_filter: Optional[str],
    commit: bool,
    verbose: bool,
    dump_json_path: Optional[Path] = None,
    use_cache: bool = True,
    allow_strategic_spend: bool = False,
) -> int:
    chroma_path = assert_local_chroma_path()
    selected, assignments = load_and_validate_selection(selection_file, folder_filter)

    if commit and not os.environ.get("OPENAI_API_KEY"):
        print(
            "REFUSING TO RUN: --commit requires OPENAI_API_KEY env var "
            "(needed for embedding the chunks).",
            file=sys.stderr,
        )
        return 2

    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    ):
        print(
            "REFUSING TO RUN: v2 requires GOOGLE_APPLICATION_CREDENTIALS (or "
            "GOOGLE_SERVICE_ACCOUNT_JSON) for both Drive auth and Vertex AI "
            "Gemini auth. They share the same service account.",
            file=sys.stderr,
        )
        return 2

    manifest = load_latest_manifest()
    if manifest is None:
        print(
            "REFUSING TO RUN: no folder-walk manifest found in data/inventories/",
            file=sys.stderr,
        )
        return 2

    ingest_run_id = uuid.uuid4().hex[:16]
    ingest_timestamp_utc = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print(f"Drive Loader v2 — {'COMMIT' if commit else 'DRY RUN'}")
    print("=" * 70)
    print(f"ingest_run_id:    {ingest_run_id}")
    print(f"chroma path:      {chroma_path} (LOCAL)")
    print(f"selection file:   {selection_file}")
    print(f"folders selected: {len(selected)}")
    print(f"OCR cache:        {OCR_CACHE_DIR} (use_cache={use_cache})")
    print()

    try:
        drive_client = DriveClient()
    except RuntimeError as e:
        print(f"ERROR: DriveClient init failed: {e}", file=sys.stderr)
        return 1
    print(f"drive client:     {drive_client.service_account_email}")

    cache = OcrCache(OCR_CACHE_DIR)
    vision_client = GeminiVisionClient(cache)
    print(f"vision model:     {vision_client.model} (Vertex AI)")
    print()

    total_files_seen = 0
    total_files_ingested = 0
    total_files_skipped = 0
    total_chunks = 0
    total_chars_for_embedding = 0
    all_chunks_to_write: list[dict] = []
    all_files_dumped: list[dict] = []
    files_low_yield_skipped: list[dict] = []
    files_vision_failed_skipped: list[dict] = []

    for folder_id in selected:
        library = assignments[folder_id]
        folder_meta = lookup_folder_in_manifest(manifest, folder_id)
        if folder_meta is None:
            try:
                live = drive_client.get_file(folder_id)
                folder_meta = {
                    "drive_slug": "(unknown — not in manifest)",
                    "drive_id": "",
                    "drive_name": "",
                    "folder_path": "/",
                    "folder_name": live.get("name", folder_id),
                }
            except Exception as e:
                print(f"  ERROR: cannot resolve folder {folder_id}: {e}", file=sys.stderr)
                continue
        folder_meta["folder_id"] = folder_id

        print(f"=== folder: {folder_meta['folder_name']} ===")
        print(f"  drive:        {folder_meta['drive_slug']}")
        print(f"  folder_id:    {folder_id}")
        print(f"  path:         {folder_meta['folder_path']}")
        print(f"  target lib:   {library}")

        try:
            raw_children = list(drive_client.list_children(folder_id))
        except Exception as e:
            print(f"  ERROR: cannot list children: {e}", file=sys.stderr)
            continue

        files = [c for c in raw_children if c.get("mimeType") != ingester_config.MIME_FOLDER]
        print(f"  files seen:   {len(files)}")

        # v2 only handles Google Docs in this session — other types deferred to v3
        files_to_ingest = [c for c in files if c.get("mimeType") == SUPPORTED_GOOGLE_DOC]
        files_skipped = [(c, "unsupported_mime_v2") for c in files if c.get("mimeType") != SUPPORTED_GOOGLE_DOC]

        print(f"  google docs:  {len(files_to_ingest)}")
        print(f"  other skipped:{len(files_skipped)}")
        print()

        total_files_seen += len(files)

        for child in files_to_ingest:
            file_id = child["id"]
            name = child.get("name", "<unnamed>")
            mime = child.get("mimeType", "")
            modified = child.get("modifiedTime", "")
            size = child.get("size")
            drive_size = int(size) if size else 0

            print(f"  --- file: {name} ---")
            print(f"      mime:         {mime}")
            print(f"      modified:     {modified}")
            print(f"      drive_size:   {drive_size:,} bytes")

            # Export HTML
            try:
                html_bytes = export_html(drive_client, file_id)
            except Exception as e:
                print(f"      ERROR exporting HTML: {e}", file=sys.stderr)
                continue
            print(f"      html_bytes:   {len(html_bytes):,}")

            # Parse in document order
            try:
                stream = walk_html_in_order(html_bytes)
            except Exception as e:
                print(f"      ERROR parsing HTML: {e}", file=sys.stderr)
                continue

            text_count = sum(1 for e in stream if e["kind"] == "text")
            img_count = sum(1 for e in stream if e["kind"] == "image")
            print(f"      stream:       {text_count} text blocks, {img_count} images")

            # Pre-spend projection for the file
            per_file_cost_est = project_vision_cost(img_count)
            print(f"      vision est:   ${per_file_cost_est:.4f} ({img_count} images)")

            # OCR + stitch
            pre_errors = len(vision_client.ledger.errors)
            pre_failed = vision_client.ledger.images_failed
            stitched, actual_img_count, per_image_records = stitch_stream(
                stream, vision_client, drive_client, use_cache=use_cache,
            )
            post_failed = vision_client.ledger.images_failed
            file_failed = post_failed - pre_failed

            # Per-file failure rate gate
            if actual_img_count >= VISION_FAILURE_MIN_IMAGES:
                file_rate = file_failed / actual_img_count
                if file_rate > VISION_FAILURE_RATE_CEILING:
                    print(
                        f"      SKIP: vision_failure_rate_too_high "
                        f"({file_rate*100:.1f}% > {VISION_FAILURE_RATE_CEILING*100:.0f}%)"
                    )
                    files_vision_failed_skipped.append({
                        "name": name,
                        "file_id": file_id,
                        "image_count": actual_img_count,
                        "failed_count": file_failed,
                    })
                    total_files_skipped += 1
                    print()
                    continue

            stitched_chars = len(stitched)
            stitched_words = word_count(stitched)
            print(f"      stitched:     {stitched_chars:,} chars / {stitched_words:,} words")

            # v2 low-yield guard (same threshold, new numerator)
            if drive_size >= LOW_YIELD_MIN_BYTES:
                ratio = stitched_chars / drive_size
                if ratio < LOW_YIELD_RATIO_THRESHOLD:
                    print(
                        f"      SKIP: low_yield_even_with_vision "
                        f"({ratio*100:.2f}% < {LOW_YIELD_RATIO_THRESHOLD*100:.0f}% threshold)"
                    )
                    files_low_yield_skipped.append({
                        "name": name,
                        "file_id": file_id,
                        "drive_size_bytes": drive_size,
                        "stitched_chars": stitched_chars,
                        "ratio": ratio,
                        "image_count": actual_img_count,
                    })
                    total_files_skipped += 1
                    print()
                    continue

            chunks = chunk_text(stitched)
            print(f"      chunks:       {len(chunks)}")

            if chunks and verbose:
                for c in chunks:
                    cid = build_chunk_id(folder_meta["drive_slug"], file_id, c["chunk_index"])
                    cprev = c["text"][:120].replace("\n", " ")
                    img_words = count_image_words_in_chunk(c["text"])
                    print(f"      chunk[{c['chunk_index']}]: {c['word_count']}w "
                          f"({img_words}w from images), id={cid}")
                    print(f"                 preview: \"{cprev}...\"")
            elif chunks:
                first = chunks[0]
                first_id = build_chunk_id(folder_meta["drive_slug"], file_id, 0)
                preview = first["text"][:120].replace("\n", " ")
                img_words = count_image_words_in_chunk(first["text"])
                print(f"      chunk[0]:     {first['word_count']}w "
                      f"({img_words}w from images), id={first_id}")
                print(f"                    preview: \"{preview}...\"")
                if len(chunks) > 1:
                    print(f"      [{len(chunks) - 1} more chunks not shown — use --verbose]")

            file_record = {
                "id": file_id,
                "name": name,
                "mime_type": mime,
                "modified_time": modified,
                "size": drive_size if drive_size else None,
                "web_view_link": child.get("webViewLink"),
            }
            all_files_dumped.append({
                "file_id": file_id,
                "name": name,
                "mime": mime,
                "drive_modified": modified,
                "drive_size_bytes": drive_size,
                "html_bytes": len(html_bytes),
                "stream_text_blocks": text_count,
                "stream_image_count": img_count,
                "stitched_chars": stitched_chars,
                "stitched_words": stitched_words,
                "chunk_count": len(chunks),
                "vision_failed_count": file_failed,
                "stitched_text": stitched,
                "per_image_ocr": per_image_records,
            })
            for chunk in chunks:
                meta = build_metadata_v2(
                    chunk, file_record, folder_meta, library,
                    ingest_run_id, ingest_timestamp_utc,
                )
                cid = build_chunk_id(folder_meta["drive_slug"], file_id, chunk["chunk_index"])
                all_chunks_to_write.append({
                    "id": cid,
                    "text": chunk["text"],
                    "metadata": meta,
                })
                total_chunks += 1
                total_chars_for_embedding += len(chunk["text"])

            total_files_ingested += 1
            print(f"      vision spend so far: ${vision_client.ledger.vision_cost_usd:.4f}")
            print()

        for child, reason in files_skipped:
            print(f"  --- SKIPPED: {child.get('name', '<unnamed>')} ---")
            print(f"      mime:    {child.get('mimeType', '?')}")
            print(f"      reason:  {reason}")
            print()
            total_files_skipped += 1

    # Run summary
    est_embed_tokens = total_chars_for_embedding // APPROX_CHARS_PER_TOKEN
    est_embed_cost = est_embed_tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS_USD
    vision_cost = vision_client.ledger.vision_cost_usd

    print("=" * 70)
    print("Run summary")
    print("=" * 70)
    print(f"  files seen:         {total_files_seen}")
    print(f"  files ingested:     {total_files_ingested}{' (dry-run, no actual writes)' if not commit else ''}")
    print(f"  files skipped:      {total_files_skipped}")
    if files_low_yield_skipped:
        print(f"    of which low_yield_even_with_vision: {len(files_low_yield_skipped)}")
        for ly in files_low_yield_skipped:
            print(f"      - {ly['name']} ({ly['ratio']*100:.2f}% yield, {ly['image_count']} images)")
    if files_vision_failed_skipped:
        print(f"    of which vision_failure_rate_too_high: {len(files_vision_failed_skipped)}")
        for vf in files_vision_failed_skipped:
            print(f"      - {vf['name']} ({vf['failed_count']}/{vf['image_count']} failed)")
    print(f"  total chunks:       {total_chunks}")
    print()
    print(f"  vision ledger:")
    led = vision_client.ledger.to_dict()
    for k in ("images_seen", "images_ocr_called", "images_cache_hit",
              "images_decorative", "images_failed",
              "vision_input_tokens", "vision_output_tokens"):
        print(f"    {k:<24} {led[k]:,}")
    print(f"    vision_cost_usd          ${vision_cost:.4f}")
    if led["errors"]:
        print(f"    errors                   {len(led['errors'])} (see run record)")
    print()
    print(f"  embedding estimate:")
    print(f"    est_tokens               ~{est_embed_tokens:,}")
    print(f"    est_cost                 ${est_embed_cost:.4f}")
    print()
    total_cost = vision_cost + est_embed_cost
    print(f"  TOTAL projected spend:   ${total_cost:.4f}")
    if total_cost > COST_WARNING_THRESHOLD_USD:
        print(f"  ⚠ COST WARNING: estimate exceeds ${COST_WARNING_THRESHOLD_USD:.2f}")
    print()

    if not commit:
        if dump_json_path is not None:
            dump_payload = {
                "ingest_run_id": ingest_run_id,
                "ingest_timestamp_utc": ingest_timestamp_utc,
                "selection_file": str(selection_file),
                "folder_filter": folder_filter,
                "pipeline": SOURCE_PIPELINE,
                "summary": {
                    "files_seen": total_files_seen,
                    "files_ingested": total_files_ingested,
                    "files_skipped": total_files_skipped,
                    "total_chunks": total_chunks,
                    "estimated_embed_tokens": est_embed_tokens,
                    "estimated_embed_cost_usd": round(est_embed_cost, 6),
                    "actual_vision_cost_usd": round(vision_cost, 6),
                    "total_cost_usd": round(total_cost, 6),
                    "vision_ledger": led,
                },
                "files": all_files_dumped,
                "low_yield_skipped": files_low_yield_skipped,
                "vision_failed_skipped": files_vision_failed_skipped,
                "chunks": all_chunks_to_write,
            }
            dump_json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dump_json_path, "w", encoding="utf-8") as f:
                json.dump(dump_payload, f, indent=2, ensure_ascii=False)
            print(f"Dump written: {dump_json_path}")
        print("DRY RUN — nothing written to ChromaDB. Use --commit to actually ingest.")
        return 0

    # ---- Commit path ----
    # Cost gates
    if vision_cost > VISION_COST_HARD_GATE_USD and not allow_strategic_spend:
        print(
            f"REFUSING TO COMMIT: vision cost ${vision_cost:.2f} exceeds "
            f"hard gate ${VISION_COST_HARD_GATE_USD:.2f}. Pass "
            f"--allow-strategic-spend to override.",
            file=sys.stderr,
        )
        return 2
    if vision_cost > VISION_COST_INTERACTIVE_GATE_USD:
        reply = input(
            f"Vision cost ${vision_cost:.2f} exceeds "
            f"${VISION_COST_INTERACTIVE_GATE_USD:.2f}. Commit anyway? [y/N]: "
        )
        if reply.strip().lower() != "y":
            print("Commit aborted by user.")
            return 0

    print("COMMIT mode — writing to local ChromaDB...")
    try:
        import chromadb
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    except ImportError as e:
        print(f"ERROR: chromadb not installed: {e}", file=sys.stderr)
        return 1

    chroma_client = chromadb.PersistentClient(path=str(chroma_path))
    target_collection = list(ALLOWED_LIBRARIES)[0]
    ef = OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-large",
    )
    collection = chroma_client.get_or_create_collection(
        name=target_collection,
        embedding_function=ef,
    )

    BATCH = 100
    written = 0
    for i in range(0, len(all_chunks_to_write), BATCH):
        batch = all_chunks_to_write[i:i + BATCH]
        ids = [c["id"] for c in batch]
        docs = [c["text"] for c in batch]
        metas = [c["metadata"] for c in batch]
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        written += len(batch)
        print(f"  wrote {written}/{len(all_chunks_to_write)} chunks")

    run_record_dir = _REPO_ROOT / "data" / "ingest_runs"
    run_record_dir.mkdir(parents=True, exist_ok=True)
    run_record_path = run_record_dir / f"{ingest_run_id}.json"
    run_record = {
        "ingest_run_id": ingest_run_id,
        "ingest_timestamp_utc": ingest_timestamp_utc,
        "pipeline": SOURCE_PIPELINE,
        "selection_file": str(selection_file),
        "target_collection": target_collection,
        "selected_folders": selected,
        "library_assignments": assignments,
        "files_seen": total_files_seen,
        "files_ingested": total_files_ingested,
        "files_skipped": total_files_skipped,
        "total_chunks_written": total_chunks,
        "embedding_cost_estimate_usd": round(est_embed_cost, 4),
        "vision_cost_actual_usd": round(vision_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "vision_ledger": led,
        "chunk_ids": [c["id"] for c in all_chunks_to_write],
    }
    with open(run_record_path, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)
    print(f"  run record:  {run_record_path}")
    print()
    print("COMMIT complete.")
    return 0


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ingester.loaders.drive_loader_v2",
        description="Drive Loader v2 — HTML export + Gemini vision OCR",
    )
    p.add_argument("--selection-file", type=Path, default=DEFAULT_SELECTION_FILE)
    p.add_argument("--folder-id", default=None)
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", default=True)
    mode_group.add_argument("--commit", action="store_true", default=False)
    p.add_argument("--verbose", action="store_true", default=False)
    p.add_argument("--dump-json", type=Path, default=None)
    p.add_argument("--no-cache", action="store_true", default=False,
                   help="Bypass OCR cache — re-call Gemini on every image")
    p.add_argument("--allow-strategic-spend", action="store_true", default=False,
                   help=f"Override the ${VISION_COST_HARD_GATE_USD:.0f} hard-refuse gate")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        selection_file=args.selection_file,
        folder_filter=args.folder_id,
        commit=args.commit,
        verbose=args.verbose,
        dump_json_path=args.dump_json,
        use_cache=not args.no_cache,
        allow_strategic_spend=args.allow_strategic_spend,
    )


if __name__ == "__main__":
    sys.exit(main())
