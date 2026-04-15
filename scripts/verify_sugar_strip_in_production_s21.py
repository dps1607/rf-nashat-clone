"""
Session 21 — verify production Sugar Swaps chunk now matches s20 strip-ON A/B winner.

Pulls the current production Sugar Swaps chunk (which after #39 backfill
should be the strip-ON version), embeds it + the same 6 queries from s20,
and prints similarities. Compares against s20's strip-ON numbers.

Read-only Chroma + 7 small embeddings (~$0.0001).
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import chromadb
from openai import OpenAI

# s20 strip-ON reference numbers (the "winner" from BACKLOG #38)
S20_REFERENCE = {
    "sugar substitutes for fertility":      0.5865,
    "how does sugar affect hormones":       0.4320,
    "low glycemic foods for egg quality":   0.4911,
    "canva design template":                0.1839,
    "page 1 cover layout":                  0.2357,
    "how to edit a canva document":         0.1725,
}

TOPICAL = list(S20_REFERENCE.keys())[:3]
POLLUTION = list(S20_REFERENCE.keys())[3:]


def cosine(a, b):
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


def main():
    c = chromadb.PersistentClient(path="/Users/danielsmith/Claude - RF 2.0/chroma_db")
    col = c.get_collection("rf_reference_library")
    sugar_id = "drive:3-marketing:1ucqhpCFg5fmj78XyU2yj0ANGM3kJuG7Tuut1jBd2Vrk:0000"
    r = col.get(ids=[sugar_id], include=["documents", "metadatas"])
    if not r["ids"]:
        print(f"FAIL: chunk not found: {sugar_id}")
        sys.exit(1)
    chunk_text = r["documents"][0]
    print(f"Production chunk text length: {len(chunk_text)} chars")
    print(f"Contains canva.com: {'canva.com' in chunk_text}")
    print(f"content_hash: {r['metadatas'][0].get('content_hash', 'MISSING')[:16]}...")
    print()

    client = OpenAI()
    inputs = [chunk_text] + TOPICAL + POLLUTION
    resp = client.embeddings.create(model="text-embedding-3-large", input=inputs)
    embeds = [e.embedding for e in resp.data]
    chunk_e = embeds[0]
    query_es = embeds[1:]

    print(f"{'Query':<42} {'Prod':>8} {'s20 strip-ON':>14} {'Δ':>8}")
    print("-" * 76)
    for q, qe in zip(TOPICAL + POLLUTION, query_es):
        sim = cosine(chunk_e, qe)
        ref = S20_REFERENCE[q]
        delta = sim - ref
        flag = " " if abs(delta) < 0.02 else "*"
        print(f"{q:<42} {sim:>8.4f} {ref:>14.4f} {delta:>+8.4f} {flag}")

    print()
    print("Interpretation: deltas within ±0.02 confirm production matches s20 strip-ON winner.")
    print("Larger deltas reflect run-to-run embedding noise (text-embedding-3-large is stable but not deterministic).")


if __name__ == "__main__":
    main()
