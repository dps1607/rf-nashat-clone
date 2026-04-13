"""
Read-only schema + content inventory of the rf_reference_library ChromaDB collection.

Session 9 / stabilization investigation.

Per April 9 HANDOVER_PHASE3_COMPLETE.md and confirmed by Dan in session 9:
  - rf_reference_library contains 584 chunks
  - This is the LIVE A4M reference library currently serving the system
  - It is NOT stale, it is NOT a mystery; it is part of the production asset
  - Goal of this script is to understand its shape, not to evaluate whether to drop it

This script:
  - Connects to local ChromaDB
  - Opens rf_reference_library
  - Reports total count (expected: 584)
  - Samples 10 chunks (more than coaching peek; smaller collection, lower cost)
  - Prints the union of metadata keys observed
  - Prints sample metadata + first 200 chars of text per sample
  - Enumerates unique source_file values (or whatever filename-like field exists) across the WHOLE collection
  - Reports rough total token count proxy (sum of len(text)/4)
  - Calls NO write methods under any code path

Usage:
    ./venv/bin/python scripts/peek_reference_library.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from typing import Any

CHROMA_DIR = "/Users/danielsmith/Claude - RF 2.0/chroma_db"
COLLECTION_NAME = "rf_reference_library"
SAMPLE_LIMIT = 10

REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bKelsey\s+Poe\b", re.IGNORECASE), "[REDACTED-STAFF]"),
    (re.compile(r"\bKelsey\b", re.IGNORECASE), "[REDACTED-STAFF]"),
    (re.compile(r"\bErica\b", re.IGNORECASE), "[REDACTED-STAFF]"),
    (re.compile(r"\bDr\.?\s*Christina\b", re.IGNORECASE), "[REDACTED-EXCLUDED]"),
    (re.compile(r"\bChristina\b", re.IGNORECASE), "[REDACTED-EXCLUDED]"),
]


def redact(s: str) -> str:
    out = s
    for pat, replacement in REDACT_PATTERNS:
        out = pat.sub(replacement, out)
    return out


def redact_value(v: Any) -> Any:
    if isinstance(v, str):
        return redact(v)
    if isinstance(v, list):
        return [redact_value(x) for x in v]
    if isinstance(v, dict):
        return {k: redact_value(val) for k, val in v.items()}
    return v


def main() -> int:
    try:
        import chromadb
    except ImportError:
        print("ERROR: chromadb not installed", file=sys.stderr)
        return 2

    print(f"Connecting to Chroma at: {CHROMA_DIR}")
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    collection_names = [c.name for c in client.list_collections()]
    print(f"Collections present: {collection_names}")

    if COLLECTION_NAME not in collection_names:
        print(f"ERROR: collection {COLLECTION_NAME!r} not found", file=sys.stderr)
        return 3

    coll = client.get_collection(COLLECTION_NAME)
    total = coll.count()
    print(f"\n=== COLLECTION: {COLLECTION_NAME} ===")
    print(f"Total count: {total}")
    print(f"Expected (per April 9 handover): 584")
    print(f"Match: {total == 584}")

    # Sample for shape inspection
    sample = coll.get(limit=SAMPLE_LIMIT, include=["metadatas", "documents"])
    ids = sample.get("ids") or []
    metadatas = sample.get("metadatas") or []
    documents = sample.get("documents") or []

    print(f"\n=== SAMPLE (n={len(ids)}) ===")
    key_union: set[str] = set()
    for m in metadatas:
        if m:
            key_union.update(m.keys())
    print(f"\nMetadata key union across sample: {sorted(key_union)}")
    print(f"Key count: {len(key_union)}")

    for i, (cid, meta, doc) in enumerate(zip(ids, metadatas, documents)):
        print(f"\n--- Sample {i + 1} ---")
        print(f"id: {cid}")
        safe_meta = redact_value(meta) if meta is not None else None
        print(f"metadata:\n{json.dumps(safe_meta, indent=2, ensure_ascii=False, default=str)}")
        if isinstance(doc, str):
            snippet = redact(doc[:300])
            print(f"document (first 300 chars, redacted): {snippet!r}")
            print(f"document length: {len(doc)} chars")
        else:
            print(f"document: {type(doc).__name__}")

    # Now do a FULL-collection inventory of source files and total text size.
    # This is read-only but pulls all 584 chunks into memory for analysis.
    print(f"\n=== FULL-COLLECTION INVENTORY (all {total} chunks) ===")
    full = coll.get(include=["metadatas", "documents"])
    full_ids = full.get("ids") or []
    full_metas = full.get("metadatas") or []
    full_docs = full.get("documents") or []

    print(f"Loaded {len(full_ids)} chunks for full inventory")

    # Collect every metadata key seen across the full collection
    full_key_counts: Counter[str] = Counter()
    for m in full_metas:
        if m:
            for k in m.keys():
                full_key_counts[k] += 1

    print(f"\nFull-collection metadata key inventory (key: chunks_with_this_key):")
    for k, c in full_key_counts.most_common():
        pct = (c / len(full_metas) * 100) if full_metas else 0
        print(f"  {k}: {c}/{len(full_metas)} ({pct:.1f}%)")

    # Look for filename-like fields across the full collection.
    # Try common candidates we've seen elsewhere.
    candidates = ["source_file", "source", "filename", "file", "module", "module_title",
                  "module_number", "call_file", "title", "name", "library_name",
                  "doc_id", "document_id", "source_path"]
    print(f"\n=== Filename / source-identifier candidate fields ===")
    for cand in candidates:
        values = [m.get(cand) for m in full_metas if m and cand in m]
        if values:
            unique = sorted(set(str(v) for v in values))
            print(f"  {cand}: {len(values)} chunks have it, {len(unique)} unique values")
            for u in unique[:20]:
                print(f"    - {u}")
            if len(unique) > 20:
                print(f"    ... and {len(unique) - 20} more")

    # Rough total content size
    total_chars = sum(len(d) for d in full_docs if isinstance(d, str))
    rough_tokens = total_chars // 4
    print(f"\n=== Total content size ===")
    print(f"Total characters across all chunks: {total_chars:,}")
    print(f"Rough token estimate (chars/4): {rough_tokens:,}")
    print(f"Mean chars per chunk: {total_chars // max(len(full_docs), 1):,}")

    # ID format inspection
    print(f"\n=== Chunk ID format inspection ===")
    print(f"First 10 IDs:")
    for cid in full_ids[:10]:
        print(f"  {cid}")
    print(f"Last 10 IDs:")
    for cid in full_ids[-10:]:
        print(f"  {cid}")

    # Sentinel checks: ADR_006 fields present?
    print(f"\n=== ADR_006 sentinel check ===")
    adr006_fields = [
        "chunk_id", "collection", "library_name", "entry_type", "origin",
        "tier", "source_id", "source_name", "chunk_index", "ingested_at",
    ]
    for f in adr006_fields:
        present = sum(1 for m in full_metas if m and f in m)
        print(f"  {f}: {present}/{len(full_metas)}")

    marker_keys = sorted(set(k for m in full_metas if m for k in m.keys() if k.startswith("marker_")))
    print(f"  marker_* keys present anywhere in collection: {len(marker_keys)}")
    if marker_keys:
        print(f"    examples: {marker_keys[:5]}")

    print("\n=== DONE (read-only, no writes performed) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
