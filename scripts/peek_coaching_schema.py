"""
Read-only schema inventory of the rf_coaching_transcripts ChromaDB collection.

Session 8 / Step 1 / Gate 1 precondition for ADR_006 Phase 1 structural backfill.

This script:
  - Connects to the local ChromaDB persistent client
  - Opens rf_coaching_transcripts
  - Reports total count (expected: 9,224)
  - Samples 5 chunks via coll.get(limit=5, include=["metadatas", "documents"])
  - Prints the union of metadata keys observed across the 5 samples
  - Prints each sample's full metadata dict, with Kelsey Poe / Erica / Dr. Christina
    names masked in the STDOUT output only (never written to disk)
  - Calls NO write methods under any code path

Usage:
    ./venv/bin/python scripts/peek_coaching_schema.py

Output is printed to stdout; the human (Dan) captures it into
docs/COACHING_CHUNK_CURRENT_SCHEMA.md.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

CHROMA_DIR = "/Users/danielsmith/Claude - RF 2.0/chroma_db"
COLLECTION_NAME = "rf_coaching_transcripts"
SAMPLE_LIMIT = 5

# Names to mask in stdout output (never written to disk by this script).
# Word-boundary anchored, case-insensitive.
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
        print("ERROR: chromadb not installed in this Python environment.", file=sys.stderr)
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
    print(f"Expected (per HANDOVER session 7): 9224")
    print(f"Match: {total == 9224}")

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
        print(f"id: {redact(cid) if isinstance(cid, str) else cid}")
        safe_meta = redact_value(meta) if meta is not None else None
        print(f"metadata:\n{json.dumps(safe_meta, indent=2, ensure_ascii=False, default=str)}")
        if isinstance(doc, str):
            snippet = redact(doc[:300])
            print(f"document (first 300 chars, redacted): {snippet!r}")
        else:
            print(f"document: {type(doc).__name__}")

    print("\n=== SENTINEL CHECKS (sample-level only) ===")
    for field in ("client_rfids", "client_names"):
        observed = []
        for m in metadatas:
            if m and field in m:
                observed.append(m.get(field))
        if observed:
            print(f"  {field}: PRESENT on {len(observed)} sampled chunks -- values: {observed}")
        else:
            print(f"  {field}: not present on any sampled chunk (consistent with post-wipe)")

    marker_keys_seen: set[str] = set()
    marker_true_count = 0
    for m in metadatas:
        if m:
            for k, v in m.items():
                if k.startswith("marker_"):
                    marker_keys_seen.add(k)
                    if v is True:
                        marker_true_count += 1
    print(f"  marker_* keys present in sample: {sorted(marker_keys_seen) or 'none'}")
    print(f"  marker_* True values in sample: {marker_true_count}")

    print("\n=== DONE (read-only, no writes performed) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
