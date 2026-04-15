"""Drive Loader v3 — multi-type dispatcher.

Session 16 deliverable — closes Gap 2 for PDFs. Routes Drive files by MIME
to type-specific handlers in ingester.loaders.types. See
docs/plans/2026-04-14-drive-loader-v3.md for the full design (D1-D12).

Key properties:
  - Single entrypoint the admin UI calls. Google Docs route internally
    to v2's process_google_doc via an adapter (D2 revised); all other
    file types go to v3 handlers in types/.
  - Per-file try/except + quarantine file (D12) — one bad file doesn't
    abort the whole run.
  - 50% hard-fail threshold — halts before Chroma writes if more than
    half the files quarantine. That's the "something is fundamentally
    broken" detector (bad auth, dead dep, config drift).
  - OpenAI embedding preflight on --commit (mirrors v2's session 14 add).
  - Unified run record with by_handler breakdown.
  - Local Chroma only — hard refuse if CHROMA_DB_PATH looks Railway-ish.
  - No modifications to v1, v2, _drive_common, or scrub module.

CLI flags:
  --selection PATH        path to selection_state.json
  --dry-run               projected cost + quarantine preview, no writes
  --commit                actual Chroma writes (requires preflight pass)
  --dump-json             on dry-run, write per-file extract details to
                          /tmp/drive_loader_v3_dump_<run_id>.json
  --retry-quarantine ID   re-run only files quarantined by prior run ID

Hard rules:
  - No Railway writes (same guard as v1/v2)
  - No re-embedding of existing chunks (upsert handles idempotency)
  - No touching rf_coaching_transcripts
  - All OpenAI spend gated on preflight + interactive $1 / hard $25
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Repo root on sys.path so `ingester.*` imports work when run as a module
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load .env so OPENAI_API_KEY and other credentials resolve when v3 is
# invoked as a subprocess (e.g. from the admin UI) rather than from an
# interactive shell that has already sourced .env. Mirrors the pattern
# in rag_server/app.py. v2 does NOT load .env today — bringing v2 in
# line is a BACKLOG item, not a session 16 v2 modification.
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass  # python-dotenv is in requirements.txt but tolerate absence

from ingester.drive_client import DriveClient
from ingester.loaders._drive_common import (
    assert_local_chroma_path,
    build_metadata_base,
    load_and_validate_selection,
)
from ingester.loaders.types import (
    ExtractResult,
    chunk_with_locators,
)

# ----------------------------------------------------------------------------
# Constants + MIME dispatch table
# ----------------------------------------------------------------------------

SOURCE_PIPELINE = "drive_loader_v3"

# Cost gates (match v2, session 14 conventions)
INTERACTIVE_COST_PROMPT_USD = 1.00
HARD_REFUSE_COST_USD = 25.00

# Embedding cost constants (match v2)
EMBEDDING_PRICE_PER_1M_TOKENS_USD = 0.13  # text-embedding-3-large
APPROX_CHARS_PER_TOKEN = 4

# D12 — quarantine thresholds
HARD_FAIL_QUARANTINE_RATIO = 0.50  # more than 50% quarantine → halt

# Run artifact directories
_INGEST_RUNS_DIR = _REPO_ROOT / "data" / "ingest_runs"


# MIME types → handler category. Each category maps to one handler module
# (or "unsupported" for session 16). The dispatcher looks up the handler
# by category, so adding a new MIME just needs a row here.
MIME_CATEGORY: dict[str, str] = {
    # Google native docs → v2 adapter (D2 revised)
    "application/vnd.google-apps.document": "v2_google_doc",
    # PDFs → session 16 pilot
    "application/pdf": "pdf",
    # Session 17+ types — recognized but not handled this session
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "application/vnd.google-apps.spreadsheet": "sheets",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "sheets",
    "application/vnd.google-apps.presentation": "slides",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "slides",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "plaintext",
    "text/markdown": "plaintext",
    "audio/mpeg": "av",
    "audio/mp4": "av",
    "audio/wav": "av",
    "video/mp4": "av",
    "video/quicktime": "av",
}

# Categories that have a real handler in session 16. Other categories
# are recognized but skipped with reason="handler_not_implemented".
SESSION_16_CATEGORIES = {"pdf", "v2_google_doc", "docx"}


# ----------------------------------------------------------------------------
# Deferred handler error — for session-16-unsupported categories
# ----------------------------------------------------------------------------

class HandlerNotAvailable(Exception):
    """Raised when a Drive file's MIME routes to a category that doesn't
    have an implemented handler yet. The dispatcher catches this and
    records the file as quarantined with a clear reason, so the session
    16 run still succeeds on the PDFs while flagging the deferred work.
    """
    pass


# ----------------------------------------------------------------------------
# Per-file dispatch
# ----------------------------------------------------------------------------

def _dispatch_file(
    drive_file: dict,
    drive_client: DriveClient,
    vision_client,
) -> tuple[str, ExtractResult]:
    """Route one Drive file to its handler and return (category, result).

    Raises HandlerNotAvailable for categories deferred to session 17+.
    Raises any handler exceptions up for the caller to quarantine.
    """
    mime = drive_file.get("mimeType", "")
    category = MIME_CATEGORY.get(mime, "unknown")

    if category == "unknown":
        raise HandlerNotAvailable(
            f"unrecognized mime {mime!r} — no handler registered"
        )

    if category not in SESSION_16_CATEGORIES:
        raise HandlerNotAvailable(
            f"category {category!r} deferred to a future session "
            f"(session 16 is PDF-only; see BACKLOG #1 / #11)"
        )

    if category == "v2_google_doc":
        # Session 17 (BACKLOG #11) - Google Docs now route through the
        # shared google_doc_handler. M3 design: same module v2 imports
        # for its own run() orchestrator, called here with
        # emit_section_markers=True so chunks get [SECTION N] markers
        # the dispatcher post-pass converts to display_locator.
        from ingester.loaders.types import google_doc_handler
        class _HandlerConfig:
            pass
        cfg = _HandlerConfig()
        cfg.vision_client = vision_client
        cfg.use_cache = True
        result = google_doc_handler.extract(drive_file, drive_client, cfg)
        return category, result


    if category == "pdf":
        from ingester.loaders.types import pdf_handler
        # Pass a shim config object carrying the shared vision client
        # so OCR-fallback calls roll up into the run's vision ledger.
        class _HandlerConfig:
            pass
        cfg = _HandlerConfig()
        cfg.vision_client = vision_client
        result = pdf_handler.extract(drive_file, drive_client, cfg)
        return category, result

    if category == "docx":
        # Session 18 — .docx files via python-docx
        from ingester.loaders.types import docx_handler
        class _HandlerConfig:
            pass
        cfg = _HandlerConfig()
        cfg.vision_client = vision_client
        cfg.use_cache = True
        result = docx_handler.extract(drive_file, drive_client, cfg)
        return category, result

    raise HandlerNotAvailable(f"no dispatch branch for category {category!r}")


# ----------------------------------------------------------------------------
# OpenAI embedding preflight (D5, session 14 pattern)
# ----------------------------------------------------------------------------

def _openai_embedding_preflight() -> None:
    """Live call to OpenAI embeddings endpoint with dims check. Fails
    fast before any Drive downloads or Chroma writes if the embedding
    API is down or returns an unexpected shape.

    Mirrors drive_loader_v2's session 14 preflight exactly so v3 runs
    have the same early-abort contract.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY missing from environment — required for "
            "embedding chunks during --commit. Set it in .env or pass "
            "it in the shell before running."
        )
    try:
        from openai import OpenAI as _OpenAI
        probe = _OpenAI().embeddings.create(
            model="text-embedding-3-large",
            input="v3 preflight",
        )
    except Exception as e:  # noqa: BLE001 — pre-run gate, narrow exception OK
        raise RuntimeError(
            f"OpenAI preflight failed: {type(e).__name__}: {e}"
        ) from e
    if not probe.data or len(probe.data[0].embedding) != 3072:
        raise RuntimeError(
            f"OpenAI preflight returned unexpected embedding shape "
            f"(expected dims=3072)"
        )
    print("openai preflight: OK (text-embedding-3-large, dims=3072)")


# ----------------------------------------------------------------------------
# Quarantine file writer (D12)
# ----------------------------------------------------------------------------

def _write_quarantine_file(run_id: str, entries: list[dict]) -> Path:
    """Write data/ingest_runs/{run_id}.quarantine.json with the list of
    per-file failure records. Returns the path for logging."""
    _INGEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = _INGEST_RUNS_DIR / f"{run_id}.quarantine.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "quarantined": entries}, f, indent=2)
    return path


# ----------------------------------------------------------------------------
# Folder + file enumeration
# ----------------------------------------------------------------------------

def _enumerate_files(
    drive_client: DriveClient,
    selected_folders: list[str],
    selected_files: list[str],
    library_assignments: dict[str, str],
) -> list[dict]:
    """Walk every selected folder's immediate children + any directly
    selected files. Returns a flat list of dicts shaped:

        {
          "drive_file": <raw Drive API file dict>,
          "folder_id":  <parent folder id, or None for directly selected files>,
          "library":    <target collection from library_assignments>,
        }

    v3 only walks immediate children of selected folders (same as v2).
    Recursive folder walks would require manifest-backed paths and
    aren't in session 16 scope.
    """
    out: list[dict] = []
    seen_ids: set[str] = set()

    for folder_id in selected_folders:
        library = library_assignments.get(folder_id, "")
        for child in drive_client.list_children(folder_id):
            fid = child.get("id")
            if not fid or fid in seen_ids:
                continue
            seen_ids.add(fid)
            # Skip nested folders — v3 walks immediate children only
            if child.get("mimeType") == "application/vnd.google-apps.folder":
                continue
            out.append({
                "drive_file": child,
                "folder_id": folder_id,
                "library": library,
            })

    # Directly selected files (may live in unselected folders — D9 schema)
    for file_id in selected_files:
        if file_id in seen_ids:
            continue
        library = library_assignments.get(file_id, "")
        if not library:
            continue
        try:
            meta = drive_client.get_file(file_id)
        except Exception as e:  # noqa: BLE001
            print(f"  WARN: could not fetch file {file_id}: {e}")
            continue
        seen_ids.add(file_id)
        # Resolve the file's REAL parent folder from Drive metadata.
        # Session 16 fix: direct-file selections previously fell back to
        # a "(direct-file)" drive_slug which broke chunk ID idempotency
        # and retrieval filtering. We now read parents[0] and use it to
        # look up the real folder_meta downstream.
        parents = meta.get("parents") or []
        real_parent_folder_id = parents[0] if parents else None
        out.append({
            "drive_file": meta,
            "folder_id": real_parent_folder_id,
            "library": library,
            "direct_file_selection": True,
        })

    return out


# ----------------------------------------------------------------------------
# Main run orchestrator
# ----------------------------------------------------------------------------

def run(
    selection_path: Path,
    commit: bool,
    dump_json: bool,
    retry_quarantine: Optional[str] = None,
) -> int:
    """Execute a v3 dispatch run. Returns shell exit code (0 = success).

    Flow:
      1. Validate Chroma path is local, not Railway
      2. Load + validate selection file
      3. If --commit: run OpenAI embedding preflight
      4. Init DriveClient + shared vision client
      5. Enumerate files from the selection
      6. Dispatch each file, catch per-file errors into quarantine
      7. If quarantine rate > 50%: HALT before any Chroma writes
      8. Chunk each successful file's stitched_text via chunk_with_locators
      9. Dry-run: print summary + est costs + dump. Commit: embed + upsert.
      10. Write run record to data/ingest_runs/{run_id}.json
      11. Write quarantine file if any failures
    """
    # --- 1. Local Chroma guard -------------------------------------------
    chroma_path = assert_local_chroma_path()

    # --- 2. Selection load -----------------------------------------------
    selected_folders, library_assignments = load_and_validate_selection(
        selection_path
    )
    # Read selected_files directly — _drive_common doesn't surface it
    with open(selection_path, encoding="utf-8") as f:
        raw_selection = json.load(f)
    selected_files = raw_selection.get("selected_files", []) or []

    # --- run identity ---
    run_id = uuid.uuid4().hex[:16]
    ingest_ts = datetime.now(timezone.utc).isoformat()

    print("=" * 70)
    print(f"Drive Loader v3 — {'COMMIT' if commit else 'DRY RUN'}")
    print("=" * 70)
    print(f"ingest_run_id:    {run_id}")
    print(f"chroma path:      {chroma_path} (LOCAL)")
    print(f"selection file:   {selection_path}")
    print(f"folders selected: {len(selected_folders)}")
    print(f"files selected:   {len(selected_files)}")
    print()


    # --- 3. OpenAI preflight (only on --commit) --------------------------
    if commit:
        _openai_embedding_preflight()
        print()

    # --- 4. Drive + vision clients ---------------------------------------
    try:
        drive_client = DriveClient()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: DriveClient init failed: {e}", file=sys.stderr)
        return 2

    from ingester.vision.gemini_client import GeminiVisionClient
    from ingester.vision.ocr_cache import OcrCache
    ocr_cache_dir = _REPO_ROOT / "data" / "image_ocr_cache"
    vision_client = GeminiVisionClient(OcrCache(ocr_cache_dir))
    print(f"vision model:     {vision_client.model}")
    print(f"ocr cache dir:    {ocr_cache_dir}")
    print()

    # --- load folder manifest (best-effort; tolerate missing) ------------
    from ingester.loaders._drive_common import (
        load_latest_manifest,
        lookup_folder_in_manifest,
        build_chunk_id,
    )
    manifest = load_latest_manifest()
    folder_meta_by_id: dict[str, dict] = {}
    for folder_id in selected_folders:
        meta = lookup_folder_in_manifest(manifest, folder_id) if manifest else None
        if meta is None:
            meta = {
                "drive_slug": "(unknown-not-in-manifest)",
                "drive_id": "",
                "drive_name": "",
                "folder_path": "/",
                "folder_name": folder_id,
            }
        meta["folder_id"] = folder_id
        folder_meta_by_id[folder_id] = meta

    # --- 5. File enumeration ---------------------------------------------
    entries = _enumerate_files(
        drive_client, selected_folders, selected_files, library_assignments
    )
    print(f"files enumerated: {len(entries)}")
    print()

    # --- 5b. Resolve real parent folders for direct-file entries ---------
    # Session 16 fix: when a file is selected directly (not via a folder),
    # its chunk ID must still be built from the file's REAL parent drive_slug
    # so ID generation is idempotent regardless of selection shape. We look
    # up each direct file's parent folder in the manifest and populate
    # folder_meta_by_id the same way folder-selected entries do.
    #
    # If the manifest doesn't know the parent folder (e.g., it was walked
    # under a different name, or never walked at all), we DO NOT fall back
    # to a dummy string — we mark the entry for quarantine as a real failure
    # so the dispatcher's hard-fail tripwire can catch systemic problems.
    direct_file_parent_miss: set[str] = set()
    for entry in entries:
        if not entry.get("direct_file_selection"):
            continue
        parent_id = entry.get("folder_id")
        if parent_id is None:
            # Drive returned no parents — extremely rare (orphaned file).
            direct_file_parent_miss.add(entry["drive_file"].get("id", ""))
            continue
        if parent_id in folder_meta_by_id:
            continue  # already resolved via selected_folders path
        pmeta = lookup_folder_in_manifest(manifest, parent_id) if manifest else None
        if pmeta is None:
            # Manifest miss — surface rather than silently fall back.
            print(
                f"  WARN: direct-file parent folder {parent_id} not in "
                f"manifest; file will be quarantined (real failure, not "
                f"deferred) to prevent writing chunks with an unresolved "
                f"drive_slug.",
                file=sys.stderr,
            )
            direct_file_parent_miss.add(entry["drive_file"].get("id", ""))
            continue
        pmeta["folder_id"] = parent_id
        folder_meta_by_id[parent_id] = pmeta

    if not entries:
        print("No files to process — selection produced zero entries.")
        return 0


    # --- 6. Per-file dispatch with try/except + quarantine ---------------
    per_file_results: list[dict] = []  # successful
    quarantine_entries: list[dict] = []  # D12

    by_category_counts: dict[str, int] = {}

    for i, entry in enumerate(entries, start=1):
        df = entry["drive_file"]
        file_id = df.get("id", "")
        file_name = df.get("name", "<unnamed>")
        mime = df.get("mimeType", "")
        print(f"  [{i}/{len(entries)}] {file_name}")
        print(f"      id:   {file_id}")
        print(f"      mime: {mime}")

        # Session 16 fix: if this is a direct-file entry whose parent
        # folder couldn't be resolved in the manifest, quarantine as a
        # REAL failure (not deferred) before dispatching. Prevents
        # writing chunks with an unresolved drive_slug.
        if file_id in direct_file_parent_miss:
            msg = (
                "direct-file selection — parent folder not resolvable "
                "via manifest, so drive_slug would be undefined. "
                "Walk the parent folder into the manifest first "
                "(run folder_walk against the shared drive) then retry."
            )
            print(f"      ERROR: {msg}")
            quarantine_entries.append({
                "drive_file_id": file_id,
                "file_name": file_name,
                "mime_type": mime,
                "handler": "preflight",
                "error_type": "ParentFolderUnresolved",
                "error_message": msg,
                "traceback_truncated": "",
                "retry_count": 0,
                "deferred": False,
            })
            continue

        try:
            category, result = _dispatch_file(df, drive_client, vision_client)
        except HandlerNotAvailable as e:
            print(f"      DEFERRED: {e}")
            quarantine_entries.append({
                "drive_file_id": file_id,
                "file_name": file_name,
                "mime_type": mime,
                "handler": MIME_CATEGORY.get(mime, "unknown"),
                "error_type": "HandlerNotAvailable",
                "error_message": str(e),
                "traceback_truncated": "",
                "retry_count": 0,
                "deferred": True,
            })
            by_category_counts[MIME_CATEGORY.get(mime, "unknown")] = (
                by_category_counts.get(MIME_CATEGORY.get(mime, "unknown"), 0) + 1
            )
            continue
        except Exception as e:  # noqa: BLE001 — D12 per-file isolation
            tb = traceback.format_exc().splitlines()[-20:]
            print(f"      ERROR: {type(e).__name__}: {e}")
            quarantine_entries.append({
                "drive_file_id": file_id,
                "file_name": file_name,
                "mime_type": mime,
                "handler": MIME_CATEGORY.get(mime, "unknown"),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback_truncated": "\n".join(tb),
                "retry_count": 0,
                "deferred": False,
            })
            continue

        print(f"      OK:     {result.extraction_method}, "
              f"{result.pages_total} pages, "
              f"{len(result.stitched_text):,} chars stitched")
        by_category_counts[category] = by_category_counts.get(category, 0) + 1
        per_file_results.append({
            "entry": entry,
            "category": category,
            "result": result,
        })


    print()

    # --- 7. D12 hard-fail check ------------------------------------------
    # Count only REAL failures (not deferred handlers) against the threshold.
    # Deferred handlers are expected in session 16 if the user selects a
    # mixed folder, and shouldn't trip the "something is broken" detector.
    real_failures = [q for q in quarantine_entries if not q.get("deferred")]
    total_attempted = len(per_file_results) + len(real_failures)
    if total_attempted > 0:
        fail_ratio = len(real_failures) / total_attempted
        if fail_ratio > HARD_FAIL_QUARANTINE_RATIO:
            print(
                f"HALTING: {len(real_failures)}/{total_attempted} real failures "
                f"({fail_ratio:.0%}) exceeds {HARD_FAIL_QUARANTINE_RATIO:.0%} "
                f"hard-fail threshold. Something is fundamentally broken.",
                file=sys.stderr,
            )
            qpath = _write_quarantine_file(run_id, quarantine_entries)
            print(f"  quarantine written: {qpath}", file=sys.stderr)
            return 3

    # --- 8. Chunking via Option Q pipeline -------------------------------
    all_chunks_to_write: list[dict] = []
    total_chars_for_embedding = 0
    per_file_chunk_counts: list[dict] = []

    for pf in per_file_results:
        entry = pf["entry"]
        result: ExtractResult = pf["result"]
        df = entry["drive_file"]
        library = entry["library"]
        folder_id = entry["folder_id"]

        # Session 16 fix: folder_id must always be resolvable here.
        # direct-file entries whose parent wasn't in the manifest were
        # already quarantined in the dispatch loop. folder-selected
        # entries always have their folder_id in folder_meta_by_id
        # (populated in step 4).
        folder_meta = folder_meta_by_id.get(folder_id)
        if folder_meta is None:
            # Defensive: should be unreachable. Raise loudly rather than
            # fall back to a dummy — session 16 learned that silent
            # fallbacks corrupt chunk IDs.
            raise RuntimeError(
                f"internal error: folder_meta missing for folder_id "
                f"{folder_id!r} on file {df.get('id')!r}. This should have "
                f"been caught by the direct-file preflight."
            )

        file_record = {
            "id": df.get("id", ""),
            "name": df.get("name", ""),
            "mime_type": df.get("mimeType", ""),
            "modified_time": df.get("modifiedTime", ""),
            "size": int(df.get("size", 0) or 0),
            "web_view_link": df.get("webViewLink", ""),
        }

        chunks = chunk_with_locators(result.stitched_text)
        per_file_chunk_counts.append({
            "file_id": file_record["id"],
            "file_name": file_record["name"],
            "category": pf["category"],
            "extraction_method": result.extraction_method,
            "pages_total": result.pages_total,
            "chunks": len(chunks),
            "vision_cost_usd": result.vision_cost_usd,
            "images_seen": result.images_seen,
            "images_ocr_called": result.images_ocr_called,
            "warnings": result.warnings,
        })


        for chunk in chunks:
            base_meta = build_metadata_base(
                chunk, file_record, folder_meta, library,
                run_id, ingest_ts,
                source_pipeline=SOURCE_PIPELINE,
            )
            # D7 additions: optional locator + timestamp fields.
            # Chroma metadata values must be scalar (str/int/float/bool/None)
            # and Chroma doesn't accept None — store as empty string when absent
            # so format_context() can `elide when null` via truthy check.
            base_meta["display_locator"] = chunk.get("display_locator") or ""
            base_meta["display_timestamp"] = chunk.get("display_timestamp") or ""
            # Handler provenance for run record / debugging
            base_meta["v3_category"] = pf["category"]
            base_meta["v3_extraction_method"] = result.extraction_method
            base_meta["source_unit_label"] = result.source_unit_label or ""

            cid = build_chunk_id(
                folder_meta["drive_slug"], file_record["id"], chunk["chunk_index"]
            )
            all_chunks_to_write.append({
                "id": cid,
                "text": chunk["text"],
                "metadata": base_meta,
                "library": library,
            })
            total_chars_for_embedding += len(chunk["text"])

    # --- Embedding cost estimate -----------------------------------------
    est_embed_tokens = total_chars_for_embedding // APPROX_CHARS_PER_TOKEN
    est_embed_cost = est_embed_tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS_USD
    total_projected = est_embed_cost + vision_client.ledger.vision_cost_usd


    # --- Run summary (printed on both dry-run and commit) ----------------
    print("=" * 70)
    print("Run summary")
    print("=" * 70)
    print(f"  files enumerated:   {len(entries)}")
    print(f"  files processed OK: {len(per_file_results)}")
    print(f"  files quarantined:  {len(quarantine_entries)} "
          f"({len(real_failures)} real, "
          f"{len(quarantine_entries) - len(real_failures)} deferred)")
    print(f"  total chunks:       {len(all_chunks_to_write)}")
    print()
    if by_category_counts:
        print("  by_handler:")
        for cat, n in sorted(by_category_counts.items()):
            print(f"    {cat:20s} {n}")
        print()
    print("  vision ledger:")
    for k, v in vision_client.ledger.to_dict().items():
        if k == "errors":
            continue
        print(f"    {k:25s} {v}")
    print()
    print("  embedding estimate:")
    print(f"    est_tokens               ~{est_embed_tokens:,}")
    print(f"    est_cost                 ${est_embed_cost:.4f}")
    print()
    print(f"  TOTAL projected spend:     ${total_projected:.4f}")
    print()

    # --- Cost gate checks (same as v2) -----------------------------------
    if total_projected > HARD_REFUSE_COST_USD:
        print(
            f"REFUSING TO RUN: projected spend ${total_projected:.2f} "
            f"exceeds hard-refuse ceiling ${HARD_REFUSE_COST_USD:.2f}",
            file=sys.stderr,
        )
        return 4
    if commit and total_projected > INTERACTIVE_COST_PROMPT_USD:
        print(
            f"INTERACTIVE GATE: projected spend ${total_projected:.2f} "
            f"exceeds ${INTERACTIVE_COST_PROMPT_USD:.2f}. Type 'yes' to "
            f"continue with commit, anything else to abort: ",
            end="", flush=True,
        )
        ans = sys.stdin.readline().strip().lower()
        if ans != "yes":
            print("aborted by user at cost gate.")
            return 5


    # --- Build run record ------------------------------------------------
    run_record = {
        "run_id": run_id,
        "pipeline": SOURCE_PIPELINE,
        "timestamp_utc": ingest_ts,
        "mode": "commit" if commit else "dry_run",
        "chroma_path": str(chroma_path),
        "selection_file": str(selection_path),
        "files_enumerated": len(entries),
        "files_processed_ok": len(per_file_results),
        "files_quarantined": len(quarantine_entries),
        "files_quarantined_real": len(real_failures),
        "files_quarantined_deferred": len(quarantine_entries) - len(real_failures),
        "by_handler": dict(by_category_counts),
        "total_chunks": len(all_chunks_to_write),
        "per_file": per_file_chunk_counts,
        "vision_ledger": vision_client.ledger.to_dict(),
        "estimated_embed_tokens": est_embed_tokens,
        "estimated_embed_cost_usd": round(est_embed_cost, 6),
        "total_projected_usd": round(total_projected, 6),
    }

    # --- Dump-json helper (dry-run) --------------------------------------
    if dump_json:
        dump_path = Path(f"/tmp/drive_loader_v3_dump_{run_id}.json")
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump({
                "run_record": run_record,
                "per_file_results": [
                    {
                        "file_id": c["file_id"],
                        "file_name": c["file_name"],
                        "category": c["category"],
                        "extraction_method": c["extraction_method"],
                        "pages": c["pages_total"],
                        "chunks": c["chunks"],
                        "warnings": c["warnings"],
                    }
                    for c in per_file_chunk_counts
                ],
                "quarantine": quarantine_entries,
                "sample_chunks": [
                    {
                        "id": c["id"],
                        "text_preview": c["text"][:200],
                        "word_count": c["metadata"]["word_count"],
                        "name_replacements": c["metadata"]["name_replacements"],
                        "display_locator": c["metadata"]["display_locator"],
                    }
                    for c in all_chunks_to_write[:10]
                ],
            }, f, indent=2, ensure_ascii=False)
        print(f"  dump written:              {dump_path}")

    # --- Quarantine file (always, if non-empty) --------------------------
    if quarantine_entries:
        qpath = _write_quarantine_file(run_id, quarantine_entries)
        print(f"  quarantine written:        {qpath}")


    # --- Dry-run terminates here -----------------------------------------
    if not commit:
        # Write the dry-run run record too (useful for post-hoc inspection)
        _INGEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
        rr_path = _INGEST_RUNS_DIR / f"{run_id}.dry_run.json"
        with open(rr_path, "w", encoding="utf-8") as f:
            json.dump(run_record, f, indent=2)
        print(f"  run record written:        {rr_path}")
        print()
        print("DRY RUN — nothing written to ChromaDB. Use --commit to ingest.")
        return 0

    # --- 9. COMMIT path: embed + upsert to Chroma ------------------------
    if not all_chunks_to_write:
        print("No chunks to write.")
        return 0

    print("=" * 70)
    print(f"COMMIT — writing {len(all_chunks_to_write)} chunks to ChromaDB")
    print("=" * 70)

    import chromadb
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

    ef = OpenAIEmbeddingFunction(
        api_key=os.environ["OPENAI_API_KEY"],
        model_name="text-embedding-3-large",
    )
    chroma_client = chromadb.PersistentClient(path=str(chroma_path))

    # Group chunks by target library (v3 supports multi-library selections)
    by_library: dict[str, list[dict]] = {}
    for c in all_chunks_to_write:
        by_library.setdefault(c["library"], []).append(c)

    for library, chunks_for_lib in by_library.items():
        print(f"  library: {library} ({len(chunks_for_lib)} chunks)")
        collection = chroma_client.get_or_create_collection(
            name=library,
            embedding_function=ef,
        )
        pre_count = collection.count()
        ids = [c["id"] for c in chunks_for_lib]
        docs = [c["text"] for c in chunks_for_lib]
        metas = [c["metadata"] for c in chunks_for_lib]
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
        post_count = collection.count()
        print(f"    count before: {pre_count}")
        print(f"    count after:  {post_count}")
        print(f"    delta:        {post_count - pre_count}")

    run_record["commit_complete"] = True
    rr_path = _INGEST_RUNS_DIR / f"{run_id}.json"
    _INGEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(rr_path, "w", encoding="utf-8") as f:
        json.dump(run_record, f, indent=2)
    print(f"  run record written:        {rr_path}")
    print()
    print("COMMIT COMPLETE.")
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="drive_loader_v3",
        description="v3 multi-type Drive loader dispatcher (session 16: PDF pilot).",
    )
    p.add_argument(
        "--selection",
        type=Path,
        default=_REPO_ROOT / "data" / "selection_state.json",
        help="Path to selection_state.json (default: data/selection_state.json)",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Project cost, quarantine, chunks. No Chroma writes. (default)",
    )
    mode.add_argument(
        "--commit",
        action="store_true",
        default=False,
        help="Actual ingest. Runs OpenAI preflight, writes Chroma, honors cost gates.",
    )
    p.add_argument(
        "--dump-json",
        action="store_true",
        default=False,
        help="On dry-run, write per-file extract details to /tmp/drive_loader_v3_dump_<run_id>.json",
    )
    p.add_argument(
        "--retry-quarantine",
        type=str,
        default=None,
        metavar="RUN_ID",
        help="(Deferred in session 16) Re-run only files quarantined by a prior run ID.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.retry_quarantine:
        print(
            "ERROR: --retry-quarantine is a session 17+ feature "
            "(listed in v3 design doc D12 but deferred). "
            "File: BACKLOG #12 (to be added).",
            file=sys.stderr,
        )
        return 2

    commit = args.commit
    return run(
        selection_path=args.selection,
        commit=commit,
        dump_json=args.dump_json,
        retry_quarantine=None,
    )


if __name__ == "__main__":
    sys.exit(main())
