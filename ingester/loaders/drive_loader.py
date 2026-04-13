"""
Drive Loader v1 — pilot content ingestion path for the folder-selection UI.

Reads `data/selection_state.json` (or a path passed via --selection-file),
fetches each selected Drive folder via the Drive API, exports/downloads
supported file types as plain text, chunks them, and writes to a local
ChromaDB collection.

Hard rules enforced in code, not just docs:
  - REFUSES to run if CHROMA_DB_PATH starts with /data/ (Railway production guard)
  - REFUSES to run if selection_state.json contains the placeholder ["abc","def"]
  - REFUSES to run if any selected folder is missing from library_assignments
  - REFUSES to run if any library assignment is not in the allowed set
  - --dry-run is the DEFAULT; --commit must be passed explicitly to write anything
  - Idempotent at the file level: same source → same chunk IDs → upsert, not duplicate

CLI:
    python3 -m ingester.loaders.drive_loader \
        [--selection-file PATH]    (default: data/selection_state.json)
        [--folder-id ID]            (filter to one folder; recommended for pilot runs)
        [--dry-run | --commit]      (default: --dry-run)
        [--verbose]                 (per-chunk previews)

Design doc: docs/plans/2026-04-13-drive-loader-pilot.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# Repo root on sys.path so we can import sibling packages
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ingester.drive_client import DriveClient
from ingester import config as ingester_config

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Allowed target collections for the Drive loader path. Coaching is intentionally
# excluded — Drive-walked content has no business in the coaching collection
# (HIPAA boundary + category mismatch with the v3 transcript pipeline).
ALLOWED_LIBRARIES = {"rf_reference_library"}

# MIME types we know how to ingest in v1
SUPPORTED_GOOGLE_DOC = "application/vnd.google-apps.document"
SUPPORTED_PLAIN_TEXT = {"text/plain", "text/markdown"}

# Chunking tunables (paragraph-aware sliding window)
MAX_CHUNK_WORDS = 700
MIN_CHUNK_WORDS = 80
PARAGRAPH_OVERLAP = True  # last paragraph of previous chunk starts the next

# Cost estimate constants (text-embedding-3-large pricing as of 2026-04)
EMBEDDING_PRICE_PER_1M_TOKENS_USD = 0.13
APPROX_CHARS_PER_TOKEN = 4  # rough heuristic for English text
COST_WARNING_THRESHOLD_USD = 1.00  # warn if dry-run estimate exceeds this

# Pipeline identifier written to every chunk for forensic traceability
SOURCE_PIPELINE = "drive_loader_v1"

# Low-text-yield safety guard.
# When a Google Doc contains embedded images / tables / rich content, the
# text/plain export silently drops most of it. We detect this by comparing
# exported text size against the file's reported Drive size, and skip files
# whose ratio falls below the threshold. Without this guard, the loader
# would happily ingest text fragments stripped of their visual context,
# producing chunks that look authoritative but are missing the actual data.
#
# The MIN_BYTES floor exists because small text-only docs can have unusual
# ratios (Drive's reported size has metadata overhead). The guard only kicks
# in when the file is large enough that a low ratio is meaningful.
LOW_YIELD_RATIO_THRESHOLD = 0.05  # 5% — exported_chars / drive_size_bytes
LOW_YIELD_MIN_BYTES = 10_000      # only apply guard to files >= 10 KB on Drive

# Manifest path (used to look up human-readable folder paths)
DEFAULT_MANIFEST_DIR = _REPO_ROOT / "data" / "inventories"

# Default selection state location
DEFAULT_SELECTION_FILE = _REPO_ROOT / "data" / "selection_state.json"


# -----------------------------------------------------------------------------
# Manifest lookup (read-only — does not depend on the admin_ui ManifestLoader
# class to keep this CLI standalone)
# -----------------------------------------------------------------------------

def load_latest_manifest() -> Optional[dict]:
    """Load the most recent folder_walk_*.json manifest, or None if missing."""
    if not DEFAULT_MANIFEST_DIR.exists():
        return None
    candidates = sorted(DEFAULT_MANIFEST_DIR.glob("folder_walk_*.json"), reverse=True)
    if not candidates:
        return None
    with open(candidates[0], encoding="utf-8") as f:
        return json.load(f)


def lookup_folder_in_manifest(manifest: dict, folder_id: str) -> Optional[dict]:
    """
    Walk the manifest tree to find a folder by ID. Returns a dict with
    {drive_slug, drive_id, drive_name, folder_path, folder_name} or None.
    """
    if not manifest:
        return None

    def _walk(node: dict, drive_slug: str, drive_id: str, drive_name: str):
        if node.get("id") == folder_id:
            return {
                "drive_slug": drive_slug,
                "drive_id": drive_id,
                "drive_name": drive_name,
                "folder_path": node.get("path", "/"),
                "folder_name": node.get("name", folder_id),
            }
        for sub in node.get("subfolders", []):
            result = _walk(sub, drive_slug, drive_id, drive_name)
            if result is not None:
                return result
        return None

    for drive in manifest.get("drives", []):
        if drive.get("status") != "walked":
            continue
        result = _walk(
            drive.get("root", {}),
            drive.get("slug", ""),
            drive.get("drive_id", ""),
            drive.get("drive_name_google", ""),
        )
        if result is not None:
            return result
    return None


# -----------------------------------------------------------------------------
# File fetching
# -----------------------------------------------------------------------------

def fetch_file_text(client: DriveClient, file_id: str, mime: str) -> Optional[str]:
    """
    Return the plain-text content of a file, or None if the MIME type is
    not supported in v1. Uses Drive API export for Google-native types
    and direct media download for plain text.
    """
    if mime == SUPPORTED_GOOGLE_DOC:
        # Export Google Doc to plain text
        request = client._service.files().export_media(
            fileId=file_id, mimeType="text/plain"
        )
        # export_media returns bytes
        from googleapiclient.http import MediaIoBaseDownload
        import io
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")
    elif mime in SUPPORTED_PLAIN_TEXT:
        request = client._service.files().get_media(fileId=file_id)
        from googleapiclient.http import MediaIoBaseDownload
        import io
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue().decode("utf-8", errors="replace")
    else:
        return None


# -----------------------------------------------------------------------------
# Chunking
# -----------------------------------------------------------------------------

def normalize_text(raw: str) -> str:
    """
    Normalize raw exported text:
      - Strip leading BOM (U+FEFF) that Drive's text/plain export adds
      - Strip other zero-width / invisible Unicode noise
      - Normalize CRLF/CR to LF
      - Strip trailing whitespace per line
      - Collapse runs of 3+ newlines to exactly 2 (paragraph break)
    """
    # Strip leading BOM if present
    if raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")
    # Remove zero-width and similar invisible characters anywhere in the text
    # \u200b ZERO WIDTH SPACE, \u200c ZWNJ, \u200d ZWJ, \u2060 WORD JOINER, \ufeff BOM
    text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", raw)
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip trailing spaces per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse runs of 3+ newlines to exactly 2 (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraphs(text: str) -> list[str]:
    """Split normalized text into paragraphs on blank-line boundaries."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def split_paragraph_into_sentences(paragraph: str) -> list[str]:
    """Sentence-aware split for paragraphs that exceed MAX_CHUNK_WORDS."""
    parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    return [p for p in parts if p]


def word_count(s: str) -> int:
    return len(s.split())


def chunk_text(text: str) -> list[dict]:
    """
    Paragraph-aware sliding-window chunker.

    Returns list of dicts: {text, word_count, chunk_index}.
    """
    text = normalize_text(text)
    if not text:
        return []

    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return []

    # Pre-split any paragraph that's too long, by sentence
    expanded: list[str] = []
    for p in paragraphs:
        if word_count(p) > MAX_CHUNK_WORDS:
            # Greedy sentence-level repack
            sentences = split_paragraph_into_sentences(p)
            buf: list[str] = []
            buf_words = 0
            for s in sentences:
                sw = word_count(s)
                if buf_words + sw > MAX_CHUNK_WORDS and buf:
                    expanded.append(" ".join(buf))
                    buf = [s]
                    buf_words = sw
                else:
                    buf.append(s)
                    buf_words += sw
            if buf:
                expanded.append(" ".join(buf))
        else:
            expanded.append(p)

    # Greedy assembly with paragraph-level overlap
    chunks: list[dict] = []
    current: list[str] = []
    current_words = 0
    chunk_index = 0

    for p in expanded:
        pw = word_count(p)
        if current_words + pw > MAX_CHUNK_WORDS and current_words >= MIN_CHUNK_WORDS:
            chunk_text_str = "\n\n".join(current)
            chunks.append({
                "text": chunk_text_str,
                "word_count": current_words,
                "chunk_index": chunk_index,
            })
            chunk_index += 1
            # Overlap: start next chunk with last paragraph of this one
            if PARAGRAPH_OVERLAP and current:
                current = [current[-1], p]
                current_words = word_count(current[-2]) + pw
            else:
                current = [p]
                current_words = pw
        else:
            current.append(p)
            current_words += pw

    # Emit final chunk if there's anything left
    if current:
        chunk_text_str = "\n\n".join(current)
        # Only emit if it meets MIN, OR if it's the only chunk in the file
        if current_words >= MIN_CHUNK_WORDS or chunk_index == 0:
            chunks.append({
                "text": chunk_text_str,
                "word_count": current_words,
                "chunk_index": chunk_index,
            })

    return chunks


# -----------------------------------------------------------------------------
# Metadata building
# -----------------------------------------------------------------------------

def build_chunk_id(drive_slug: str, file_id: str, chunk_index: int) -> str:
    """Stable, deterministic, collision-proof against existing collections."""
    return f"drive:{drive_slug}:{file_id}:{chunk_index:04d}"


def build_metadata(
    chunk: dict,
    file_record: dict,
    folder_record: dict,
    library: str,
    ingest_run_id: str,
    ingest_timestamp_utc: str,
) -> dict:
    """
    Build the full metadata dict for one chunk. See design doc §5 for the
    field-by-field rationale. All `display_*` fields are populated for
    forward compatibility with the future read-time normalizer.
    """
    return {
        # Sequence + sizing
        "chunk_index": chunk["chunk_index"],
        "word_count": chunk["word_count"],
        # Provenance
        "source_pipeline": SOURCE_PIPELINE,
        "source_collection": library,
        "source_drive_slug": folder_record["drive_slug"],
        "source_drive_id": folder_record["drive_id"],
        "source_folder_id": folder_record["folder_id"],
        "source_folder_path": folder_record["folder_path"],
        "source_file_id": file_record["id"],
        "source_file_name": file_record["name"],
        "source_file_mime": file_record["mime_type"],
        "source_file_modified_time": file_record.get("modified_time") or "",
        "source_file_size_bytes": file_record.get("size") or 0,
        "source_web_view_link": file_record.get("web_view_link") or "",
        # Run identity
        "ingest_run_id": ingest_run_id,
        "ingest_timestamp_utc": ingest_timestamp_utc,
        # Display fields (future read-time normalizer reads these)
        "display_source": file_record["name"],
        "display_subheading": folder_record["folder_path"],
        "display_speaker": "",  # always empty for Drive content
        "display_date": file_record.get("modified_time") or "",
        "display_topics": "",  # tagging hook for future use
    }


# -----------------------------------------------------------------------------
# Validation gates
# -----------------------------------------------------------------------------

def assert_local_chroma_path() -> Path:
    """
    Refuse to run if CHROMA_DB_PATH points at a Railway-style /data path.
    Returns the resolved Chroma path.
    """
    raw = os.environ.get("CHROMA_DB_PATH")
    if not raw:
        # Fall back to the project's local default
        raw = str(_REPO_ROOT.parent / "chroma_db")
    p = Path(raw)
    p_str = str(p)
    if p_str.startswith("/data/") or p_str.startswith("/data\\"):
        print(
            f"REFUSING TO RUN: CHROMA_DB_PATH={p_str!r} looks like a Railway "
            f"production path. The drive_loader is local-sandbox-only.",
            file=sys.stderr,
        )
        sys.exit(2)
    return p


def load_and_validate_selection(
    path: Path, folder_filter: Optional[str] = None
) -> tuple[list[str], dict[str, str]]:
    """
    Read selection_state.json, validate schema, optionally filter to one
    folder. Returns (selected_folders, library_assignments).
    """
    if not path.exists():
        print(f"REFUSING TO RUN: selection file not found: {path}", file=sys.stderr)
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    selected = data.get("selected_folders", []) or []
    assignments = data.get("library_assignments", {}) or {}

    # Reject the legacy placeholder explicitly
    if set(selected) == {"abc", "def"} or selected == ["abc", "def"]:
        print(
            "REFUSING TO RUN: selection_state.json still contains the "
            "placeholder ['abc','def']. Use the admin UI to make a real "
            "selection first.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not isinstance(selected, list) or not isinstance(assignments, dict):
        print("REFUSING TO RUN: malformed selection_state.json", file=sys.stderr)
        sys.exit(2)

    if folder_filter:
        if folder_filter not in selected:
            print(
                f"REFUSING TO RUN: --folder-id {folder_filter} is not in "
                f"selection_state.json's selected_folders.",
                file=sys.stderr,
            )
            sys.exit(2)
        selected = [folder_filter]
        assignments = {folder_filter: assignments.get(folder_filter, "")}

    missing = [fid for fid in selected if fid not in assignments]
    if missing:
        print(
            f"REFUSING TO RUN: {len(missing)} folder(s) missing library assignment: {missing}",
            file=sys.stderr,
        )
        sys.exit(2)

    bad = [v for v in assignments.values() if v not in ALLOWED_LIBRARIES]
    if bad:
        print(
            f"REFUSING TO RUN: library not in allowed set {ALLOWED_LIBRARIES}: {bad}",
            file=sys.stderr,
        )
        sys.exit(2)

    return selected, assignments


# -----------------------------------------------------------------------------
# Main run logic
# -----------------------------------------------------------------------------

def run(
    selection_file: Path,
    folder_filter: Optional[str],
    commit: bool,
    verbose: bool,
    dump_json_path: Optional[Path] = None,
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

    manifest = load_latest_manifest()
    if manifest is None:
        print("REFUSING TO RUN: no folder-walk manifest found in data/inventories/", file=sys.stderr)
        return 2

    ingest_run_id = uuid.uuid4().hex[:16]
    ingest_timestamp_utc = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print(f"Drive Loader Pilot — {'COMMIT' if commit else 'DRY RUN'}")
    print("=" * 70)
    print(f"ingest_run_id:    {ingest_run_id}")
    print(f"chroma path:      {chroma_path} (LOCAL)")
    print(f"selection file:   {selection_file}")
    print(f"folders selected: {len(selected)}")
    print()

    try:
        client = DriveClient()
    except RuntimeError as e:
        print(f"ERROR: DriveClient init failed: {e}", file=sys.stderr)
        return 1
    print(f"drive client:     {client.service_account_email}")
    print()

    total_files_seen = 0
    total_files_ingested = 0
    total_files_skipped = 0
    total_chunks = 0
    total_chars_for_embedding = 0
    all_chunks_to_write: list[dict] = []  # populated during dry-run too, for verbose mode
    all_files_dumped: list[dict] = []  # full per-file capture for --dump-json artifact
    files_low_yield_skipped: list[dict] = []  # files skipped by low-text-yield guard

    for folder_id in selected:
        library = assignments[folder_id]
        folder_meta = lookup_folder_in_manifest(manifest, folder_id)
        if folder_meta is None:
            # Fall back to a live Drive lookup if the manifest doesn't have it
            try:
                live = client.get_file(folder_id)
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
        # Add folder_id to the record for build_metadata
        folder_meta["folder_id"] = folder_id

        print(f"=== folder: {folder_meta['folder_name']} ===")
        print(f"  drive:        {folder_meta['drive_slug']}")
        print(f"  folder_id:    {folder_id}")
        print(f"  path:         {folder_meta['folder_path']}")
        print(f"  target lib:   {library}")

        # List immediate children (no recursion in v1)
        try:
            raw_children = list(client.list_children(folder_id))
        except Exception as e:
            print(f"  ERROR: cannot list children: {e}", file=sys.stderr)
            continue

        files = [c for c in raw_children if c.get("mimeType") != ingester_config.MIME_FOLDER]
        print(f"  files seen:   {len(files)}")

        files_to_ingest: list[dict] = []
        files_skipped: list[tuple[dict, str]] = []
        for child in files:
            mime = child.get("mimeType", "")
            if mime == SUPPORTED_GOOGLE_DOC or mime in SUPPORTED_PLAIN_TEXT:
                files_to_ingest.append(child)
            else:
                files_skipped.append((child, "unsupported_mime"))

        print(f"  files to ingest: {len(files_to_ingest)}")
        print(f"  files skipped:   {len(files_skipped)}")
        print()

        total_files_seen += len(files)

        for child in files_to_ingest:
            file_id = child["id"]
            name = child.get("name", "<unnamed>")
            mime = child.get("mimeType", "")
            modified = child.get("modifiedTime", "")
            size = child.get("size")

            print(f"  --- file: {name} ---")
            print(f"      mime:      {mime}")
            print(f"      modified:  {modified}")

            try:
                text = fetch_file_text(client, file_id, mime)
            except Exception as e:
                print(f"      ERROR fetching: {e}", file=sys.stderr)
                continue

            if text is None:
                print(f"      SKIP: no text extracted")
                continue

            chars = len(text)
            words = word_count(text)
            print(f"      exported:  {chars:,} chars / {words:,} words")

            # Low-text-yield guard: if this is a Google Doc large enough to
            # be image-heavy and the export ratio is too low, skip it as
            # 'low_text_yield'. v2 loader (HTML export + Gemini OCR) is the
            # planned fix for these files.
            drive_size = int(size) if size else 0
            if (
                mime == SUPPORTED_GOOGLE_DOC
                and drive_size >= LOW_YIELD_MIN_BYTES
                and chars / drive_size < LOW_YIELD_RATIO_THRESHOLD
            ):
                ratio_pct = (chars / drive_size) * 100
                print(
                    f"      SKIP: low_text_yield "
                    f"({ratio_pct:.2f}% < {LOW_YIELD_RATIO_THRESHOLD*100:.0f}% threshold) "
                    f"— likely image-heavy doc, defer to v2 loader"
                )
                files_low_yield_skipped.append({
                    "name": name,
                    "file_id": file_id,
                    "drive_size_bytes": drive_size,
                    "exported_chars": chars,
                    "ratio": chars / drive_size,
                })
                total_files_skipped += 1
                print()
                continue

            chunks = chunk_text(text)
            print(f"      chunks:    {len(chunks)}")

            if chunks:
                first = chunks[0]
                preview = first["text"][:120].replace("\n", " ")
                first_id = build_chunk_id(folder_meta["drive_slug"], file_id, 0)
                print(f"      chunk[0]:  {first['word_count']}w, id={first_id}")
                print(f"                 preview: \"{preview}...\"")
                if verbose and len(chunks) > 1:
                    for c in chunks[1:]:
                        cid = build_chunk_id(folder_meta["drive_slug"], file_id, c["chunk_index"])
                        cprev = c["text"][:80].replace("\n", " ")
                        print(f"      chunk[{c['chunk_index']}]: {c['word_count']}w, id={cid}")
                        print(f"                 preview: \"{cprev}...\"")
                elif len(chunks) > 1 and not verbose:
                    print(f"      [{len(chunks) - 1} more chunks not shown — use --verbose]")

            file_record = {
                "id": file_id,
                "name": name,
                "mime_type": mime,
                "modified_time": modified,
                "size": int(size) if size else None,
                "web_view_link": child.get("webViewLink"),
            }
            # Capture the raw exported text for dump-json inspection
            all_files_dumped.append({
                "file_id": file_id,
                "name": name,
                "mime": mime,
                "drive_modified": modified,
                "drive_size_bytes": int(size) if size else None,
                "exported_chars": chars,
                "exported_words": words,
                "chunk_count": len(chunks),
                "raw_exported_text": text,
            })
            for chunk in chunks:
                meta = build_metadata(
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
            print()

        for child, reason in files_skipped:
            print(f"  --- SKIPPED: {child.get('name', '<unnamed>')} ---")
            print(f"      mime:    {child.get('mimeType', '?')}")
            print(f"      reason:  {reason}")
            print()
            total_files_skipped += 1

    # Run summary
    est_tokens = total_chars_for_embedding // APPROX_CHARS_PER_TOKEN
    est_cost = est_tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS_USD

    print("=" * 70)
    print("Run summary")
    print("=" * 70)
    print(f"  files seen:        {total_files_seen}")
    print(f"  files ingested:    {total_files_ingested}{' (dry-run, no actual writes)' if not commit else ''}")
    print(f"  files skipped:     {total_files_skipped}")
    if files_low_yield_skipped:
        print(f"    of which low_text_yield: {len(files_low_yield_skipped)} (defer to v2 loader)")
        for ly in files_low_yield_skipped:
            print(f"      - {ly['name']} ({ly['ratio']*100:.2f}% yield)")
    print(f"  total chunks:      {total_chunks}")
    print(f"  estimated tokens:  ~{est_tokens:,} (chunk text only, embedding input)")
    print(f"  estimated cost:    ${est_cost:.4f} (text-embedding-3-large @ ${EMBEDDING_PRICE_PER_1M_TOKENS_USD}/1M tokens)")
    if est_cost > COST_WARNING_THRESHOLD_USD:
        print(f"  ⚠ COST WARNING: estimate exceeds ${COST_WARNING_THRESHOLD_USD:.2f}")
    print()

    if not commit:
        if dump_json_path is not None:
            # Inspection artifact: full file text + chunks + metadata, no Chroma writes
            dump_payload = {
                "ingest_run_id": ingest_run_id,
                "ingest_timestamp_utc": ingest_timestamp_utc,
                "selection_file": str(selection_file),
                "folder_filter": folder_filter,
                "summary": {
                    "files_seen": total_files_seen,
                    "files_ingested": total_files_ingested,
                    "files_skipped": total_files_skipped,
                    "total_chunks": total_chunks,
                    "estimated_tokens": est_tokens,
                    "estimated_cost_usd": round(est_cost, 6),
                },
                "files": all_files_dumped,
                "low_yield_skipped": files_low_yield_skipped,
                "chunks": all_chunks_to_write,
            }
            dump_json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dump_json_path, "w", encoding="utf-8") as f:
                json.dump(dump_payload, f, indent=2, ensure_ascii=False)
            print(f"Dump written: {dump_json_path}")
        print("DRY RUN — nothing written to ChromaDB. Use --commit to actually ingest.")
        return 0

    # ---- Commit path (NOT exercised in session 10 per Re-Scope B) ----
    print("COMMIT mode — writing to local ChromaDB...")
    try:
        import chromadb
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    except ImportError as e:
        print(f"ERROR: chromadb not installed: {e}", file=sys.stderr)
        return 1

    chroma_client = chromadb.PersistentClient(path=str(chroma_path))
    target_collection = list(ALLOWED_LIBRARIES)[0]  # v1: only one allowed
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

    # Write run record for auditability
    run_record_dir = _REPO_ROOT / "data" / "ingest_runs"
    run_record_dir.mkdir(parents=True, exist_ok=True)
    run_record_path = run_record_dir / f"{ingest_run_id}.json"
    run_record = {
        "ingest_run_id": ingest_run_id,
        "ingest_timestamp_utc": ingest_timestamp_utc,
        "selection_file": str(selection_file),
        "target_collection": target_collection,
        "selected_folders": selected,
        "library_assignments": assignments,
        "files_seen": total_files_seen,
        "files_ingested": total_files_ingested,
        "files_skipped": total_files_skipped,
        "total_chunks_written": total_chunks,
        "estimated_cost_usd": round(est_cost, 4),
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
        prog="ingester.loaders.drive_loader",
        description="Drive Loader v1 — ingest Drive folder content into local Chroma",
    )
    p.add_argument(
        "--selection-file",
        type=Path,
        default=DEFAULT_SELECTION_FILE,
        help=f"Path to selection_state.json (default: {DEFAULT_SELECTION_FILE})",
    )
    p.add_argument(
        "--folder-id",
        default=None,
        help="Filter to one folder ID (recommended for pilot runs)",
    )
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be ingested without writing (DEFAULT)",
    )
    mode_group.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help="Actually ingest. Requires OPENAI_API_KEY. Writes to local Chroma only.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Per-chunk previews instead of per-file summaries",
    )
    p.add_argument(
        "--dump-json",
        type=Path,
        default=None,
        help="In dry-run, write the full file text + chunks + metadata to this JSON path for inspection. No Chroma writes.",
    )
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
    )


if __name__ == "__main__":
    sys.exit(main())
