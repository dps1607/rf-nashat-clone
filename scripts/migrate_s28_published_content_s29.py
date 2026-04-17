"""
BACKLOG #44 — migrate 8 v3 chunks from rf_reference_library to rf_published_content.

Findings from inventory (s28):
- All 8 v3 chunks in rf_reference_library are OUR content, not external:
  - 7 chunks from Egg Health Guide.pdf ([RF] Optimizing Egg Health Guide lead magnet)
  - 1 chunk Sugar Swaps Guide Google Doc form
- Per CONTENT_SOURCES.md, these belong in rf_published_content (our public educational),
  not rf_reference_library (external-approved only).

Operation:
1. Create rf_published_content with the SAME embedding function as rf_reference_library
   (OpenAIEmbeddingFunction, text-embedding-3-large) so embeddings stay comparable.
2. Pull the 8 chunks WITH their embeddings (no re-embedding cost, no drift).
3. Update each chunk's metadata: library_name = "rf_published_content".
4. Upsert into new collection with preserved embeddings.
5. Verify new collection is populated correctly.
6. Delete the 8 chunks from rf_reference_library (ONLY after new-collection verify).
7. Final cross-collection verification.

Usage:
  ./venv/bin/python scripts/migrate_s28_published_content_s29.py            # DRY-RUN (default)
  ./venv/bin/python scripts/migrate_s28_published_content_s29.py --commit   # PERFORM migration

Dry-run prints exactly what would be moved, verifies collection would-be state, no writes.
--commit performs writes. Idempotent-ish: re-running after success shows 0 chunks to migrate.
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

SRC_COLLECTION = "rf_reference_library"
DST_COLLECTION = "rf_published_content"
V3_FILTER = {"source_pipeline": "drive_loader_v3"}

EXPECTED_SRC_BEFORE = 605
EXPECTED_MOVED = 8
EXPECTED_SRC_AFTER = EXPECTED_SRC_BEFORE - EXPECTED_MOVED  # 597


def build_embedding_function() -> OpenAIEmbeddingFunction:
    """Match the function used by drive_loader_v3.py at commit path."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("ERROR: OPENAI_API_KEY not set in environment (.env)")
    return OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-large",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--commit", action="store_true", help="Perform writes. Default is dry-run.")
    args = parser.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    print(f"=== BACKLOG #44 migration — {mode} ===\n")

    chroma_path = os.environ.get("CHROMA_DB_PATH")
    if not chroma_path or not Path(chroma_path).is_dir():
        sys.exit(f"ERROR: CHROMA_DB_PATH not set or path does not exist: {chroma_path!r}")
    print(f"Chroma path: {chroma_path}")

    client = chromadb.PersistentClient(path=chroma_path)
    ef = build_embedding_function()

    # --- 1. Source collection: pull v3 chunks WITH embeddings ---
    src = client.get_collection(SRC_COLLECTION, embedding_function=ef)
    src_count_before = src.count()
    print(f"\n{SRC_COLLECTION} current count: {src_count_before}")

    if src_count_before != EXPECTED_SRC_BEFORE:
        # Could be because migration already ran. Report and inspect.
        print(f"  NOTE: expected {EXPECTED_SRC_BEFORE}, got {src_count_before}. "
              "Migration may have already partially/fully run. Continuing for idempotency check.")

    v3 = src.get(where=V3_FILTER, include=["embeddings", "metadatas", "documents"])
    n_v3 = len(v3["ids"])
    print(f"v3 chunks in {SRC_COLLECTION}: {n_v3}")

    if n_v3 == 0:
        print(f"\n✓ No v3 chunks in {SRC_COLLECTION}. Migration already complete or never needed.")
        # Verify destination state
        try:
            dst = client.get_collection(DST_COLLECTION, embedding_function=ef)
            print(f"{DST_COLLECTION} count: {dst.count()}")
        except Exception:
            print(f"{DST_COLLECTION} does not exist.")
        return 0

    if n_v3 != EXPECTED_MOVED:
        print(f"  WARN: expected {EXPECTED_MOVED} v3 chunks, got {n_v3}. Proceeding but inspect first.")

    # --- 2. Describe each chunk that will move ---
    print(f"\nChunks to migrate ({n_v3}):")
    for i, (cid, meta, doc) in enumerate(zip(v3["ids"], v3["metadatas"], v3["documents"])):
        src_disp = meta.get("display_source", "?")
        cat = meta.get("v3_category", "?")
        print(f"  [{i+1}] {cid[:40]}...")
        print(f"      display_source: {src_disp}")
        print(f"      v3_category:    {cat}")
        print(f"      doc length:     {len(doc) if doc else 0}")
        print(f"      current library_name: {meta.get('library_name', '?')}")

    # --- 3. Update metadata (in memory) ---
    updated_metadatas = []
    for meta in v3["metadatas"]:
        new_meta = dict(meta)  # shallow copy is fine for metadata dict
        new_meta["library_name"] = DST_COLLECTION
        updated_metadatas.append(new_meta)

    # --- 4. Destination collection: create with same embedding function ---
    if args.commit:
        print(f"\n→ Creating/accessing {DST_COLLECTION} with OpenAIEmbeddingFunction (text-embedding-3-large)")
        dst = client.get_or_create_collection(
            name=DST_COLLECTION,
            embedding_function=ef,
        )
        dst_count_before_upsert = dst.count()
        print(f"  {DST_COLLECTION} count before upsert: {dst_count_before_upsert}")
    else:
        print(f"\n[dry-run] Would create/get collection {DST_COLLECTION} with same embedding function.")
        dst_count_before_upsert = None

    # --- 5. Upsert chunks into destination ---
    if args.commit:
        print(f"→ Upserting {n_v3} chunks into {DST_COLLECTION} (preserving embeddings)...")
        dst.upsert(
            ids=v3["ids"],
            embeddings=v3["embeddings"],
            documents=v3["documents"],
            metadatas=updated_metadatas,
        )
        dst_count_after = dst.count()
        print(f"  {DST_COLLECTION} count after upsert: {dst_count_after}")
        expected_dst_after = (dst_count_before_upsert or 0) + n_v3
        if dst_count_after != expected_dst_after:
            sys.exit(f"ERROR: destination count {dst_count_after} != expected {expected_dst_after}. ABORT.")
    else:
        print(f"\n[dry-run] Would upsert {n_v3} chunks with metadata updated (library_name → {DST_COLLECTION}) "
              "and embeddings preserved exactly.")

    # --- 6. Verify destination content matches ---
    if args.commit:
        print(f"\n→ Verifying destination content...")
        dst_v3 = dst.get(where={"library_name": DST_COLLECTION}, include=["metadatas", "documents"])
        if len(dst_v3["ids"]) < n_v3:
            sys.exit(f"ERROR: destination has {len(dst_v3['ids'])} chunks, expected at least {n_v3}. ABORT.")
        # Sugar Swaps spot-check
        sugar = dst.get(where={"display_source": "[RH] The Fertility-Smart Sugar Swap Guide"},
                        include=["documents", "metadatas"])
        if len(sugar["ids"]) != 1:
            sys.exit(f"ERROR: Sugar Swaps chunk not found in {DST_COLLECTION} (got {len(sugar['ids'])}). ABORT.")
        doc = sugar["documents"][0]
        if len(doc) != 3737:
            sys.exit(f"ERROR: Sugar Swaps len mismatch: {len(doc)} != 3737. ABORT.")
        if "canva" in doc.lower() or "[COVER" in doc:
            sys.exit("ERROR: Sugar Swaps strip-ON property regressed. ABORT.")
        print(f"  ✓ Sugar Swaps preserved: len=3737, no canva, no COVER")
        egg = dst.get(where={"display_source": "Egg Health Guide.pdf"}, include=["metadatas"])
        if len(egg["ids"]) != 7:
            sys.exit(f"ERROR: Egg Health Guide expected 7 chunks in {DST_COLLECTION}, got {len(egg['ids'])}. ABORT.")
        print(f"  ✓ Egg Health Guide preserved: 7 chunks")

    # --- 7. Delete chunks from source ---
    if args.commit:
        print(f"\n→ Deleting {n_v3} chunks from {SRC_COLLECTION}...")
        src.delete(ids=v3["ids"])
        src_count_after = src.count()
        print(f"  {SRC_COLLECTION} count after delete: {src_count_after}")
        expected_src_after = src_count_before - n_v3
        if src_count_after != expected_src_after:
            sys.exit(f"ERROR: source count {src_count_after} != expected {expected_src_after}. MIGRATION LEFT IN "
                     "INCONSISTENT STATE — 8 chunks may exist in BOTH collections. Manual reconciliation needed.")
    else:
        print(f"\n[dry-run] Would delete {n_v3} chunks from {SRC_COLLECTION}, leaving {src_count_before - n_v3} chunks.")

    # --- 8. Final summary ---
    print(f"\n=== Final state ({mode}) ===")
    if args.commit:
        print(f"  {SRC_COLLECTION}: {src.count()} chunks (was {src_count_before})")
        print(f"  {DST_COLLECTION}: {dst.count()} chunks")
        # Cross-check: no v3 chunks remain in source
        leftover = src.get(where=V3_FILTER)
        print(f"  v3 chunks remaining in {SRC_COLLECTION}: {len(leftover['ids'])} (expected 0)")
        if len(leftover["ids"]) != 0:
            sys.exit("ERROR: v3 chunks remain in source. ABORT.")
        print("\n✓ Migration complete and verified.")
    else:
        print(f"  {SRC_COLLECTION}: would go from {src_count_before} → {src_count_before - n_v3}")
        print(f"  {DST_COLLECTION}: would be created with {n_v3} chunks (from 0)")
        print("\n✓ Dry-run complete. Re-run with --commit to perform.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
