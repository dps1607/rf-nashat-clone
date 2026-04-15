"""Snapshot all v3 chunks in rf_reference_library before s21 #39 backfill."""
import json
import os
from datetime import datetime, timezone
import chromadb

OUT = "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/data/snapshots/v3_chunks_pre_s21_n39.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

c = chromadb.PersistentClient(path="/Users/danielsmith/Claude - RF 2.0/chroma_db")
col = c.get_collection("rf_reference_library")
r = col.get(
    where={"source_pipeline": "drive_loader_v3"},
    include=["documents", "metadatas"],
    limit=30,
)

snapshot = {
    "snapshot_taken_utc": datetime.now(timezone.utc).isoformat(),
    "collection": "rf_reference_library",
    "filter": {"source_pipeline": "drive_loader_v3"},
    "count": len(r["ids"]),
    "chunks": [
        {"id": cid, "document": doc, "metadata": meta}
        for cid, doc, meta in zip(r["ids"], r["documents"], r["metadatas"])
    ],
}

with open(OUT, "w") as f:
    json.dump(snapshot, f, indent=2)

print(f"Wrote snapshot of {len(r['ids'])} chunks to:")
print(f"  {OUT}")
print(f"  size: {os.path.getsize(OUT)} bytes")
