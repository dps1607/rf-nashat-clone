"""
Shared helpers for drive_loader (v1) and drive_loader_v2.

Extracted from v1 in session 11 as part of the v2 build. Behavior is
identical to the v1 inline versions. A regression dry-run of v1 against
Supplement Info after this refactor must match the pre-refactor output
byte-for-byte.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# -----------------------------------------------------------------------------
# Repo root discovery
# -----------------------------------------------------------------------------
# Same path as v1: ingester/loaders/_drive_common.py -> repo root is 3 up
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def repo_root() -> Path:
    return _REPO_ROOT


# -----------------------------------------------------------------------------
# Constants shared by v1 and v2
# -----------------------------------------------------------------------------

ALLOWED_LIBRARIES = {"rf_reference_library"}

SUPPORTED_GOOGLE_DOC = "application/vnd.google-apps.document"
SUPPORTED_PLAIN_TEXT = {"text/plain", "text/markdown"}

# Chunking tunables (paragraph-aware sliding window)
MAX_CHUNK_WORDS = 700
MIN_CHUNK_WORDS = 80
PARAGRAPH_OVERLAP = True

# Cost estimate constants for embedding spend
EMBEDDING_PRICE_PER_1M_TOKENS_USD = 0.13
APPROX_CHARS_PER_TOKEN = 4
COST_WARNING_THRESHOLD_USD = 1.00

# Low-text-yield guard (v1 semantics; v2 redefines numerator in its own path)
LOW_YIELD_RATIO_THRESHOLD = 0.05
LOW_YIELD_MIN_BYTES = 10_000

DEFAULT_MANIFEST_DIR = _REPO_ROOT / "data" / "inventories"
DEFAULT_SELECTION_FILE = _REPO_ROOT / "data" / "selection_state.json"


# -----------------------------------------------------------------------------
# Manifest lookup
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
# Text normalization and chunking
# -----------------------------------------------------------------------------

def normalize_text(raw: str) -> str:
    """
    Normalize raw exported text:
      - Strip leading BOM (U+FEFF)
      - Strip zero-width / invisible Unicode
      - Normalize CRLF/CR to LF
      - Strip trailing whitespace per line
      - Collapse runs of 3+ newlines to exactly 2
    """
    if raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")
    text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
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
            if PARAGRAPH_OVERLAP and current:
                current = [current[-1], p]
                current_words = word_count(current[-2]) + pw
            else:
                current = [p]
                current_words = pw
        else:
            current.append(p)
            current_words += pw

    if current:
        chunk_text_str = "\n\n".join(current)
        if current_words >= MIN_CHUNK_WORDS or chunk_index == 0:
            chunks.append({
                "text": chunk_text_str,
                "word_count": current_words,
                "chunk_index": chunk_index,
            })

    return chunks


# -----------------------------------------------------------------------------
# Chunk ID + metadata (shared; v2 wraps this to add pipeline-specific fields)
# -----------------------------------------------------------------------------

def build_chunk_id(drive_slug: str, file_id: str, chunk_index: int) -> str:
    """Stable, deterministic, collision-proof across v1/v2/pre-existing collections."""
    return f"drive:{drive_slug}:{file_id}:{chunk_index:04d}"


def build_metadata_base(
    chunk: dict,
    file_record: dict,
    folder_record: dict,
    library: str,
    ingest_run_id: str,
    ingest_timestamp_utc: str,
    source_pipeline: str,
) -> dict:
    """
    Build the full metadata dict for one chunk. `source_pipeline` varies
    between v1 ("drive_loader_v1") and v2 ("drive_loader_v2"). v2 adds
    `image_derived_word_count` on top of this base by updating the dict.
    """
    return {
        # Sequence + sizing
        "chunk_index": chunk["chunk_index"],
        "word_count": chunk["word_count"],
        # Provenance
        "source_pipeline": source_pipeline,
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
        # Display fields
        "display_source": file_record["name"],
        "display_subheading": folder_record["folder_path"],
        "display_speaker": "",
        "display_date": file_record.get("modified_time") or "",
        "display_topics": "",
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
