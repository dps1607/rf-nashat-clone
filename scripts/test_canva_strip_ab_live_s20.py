"""
BACKLOG #38 — live A/B retrieval-similarity test on Sugar Swaps Canva strip.
Session 20.

Method (M-38-x.2): Reuse the existing Sugar Swaps chunk text from
rf_reference_library as the strip-OFF baseline (it was committed in
session 17, before the strip helper existed, so it carries the real
production pollution: Canva URL line + bare `COVER:` tag at the head).
Apply `_strip_editor_metadata()` directly to that text to produce the
strip-ON version. Embed both, plus 6 representative queries, via
`text-embedding-3-large`. Compute cosine similarities and print a
delta table per query.

Why this method (vs. re-extracting from Drive):
- Tests the exact text currently sitting in production retrieval — the
  most honest read on "does the strip help retrieval *for the chunk
  Sonnet sees today*?"
- No Drive auth, no vision client, no extraction-pipeline moving parts.
- Synthetic tests (test_canva_strip_synthetic_s19.py, 15/15 PASS)
  already cover the extraction-pipeline integration path.

Honest small-N caveat: n=1 chunk in the corpus has Canva pollution today
(Sugar Swaps). The 13 v2 DFH chunks and 7 v3 PDF chunks are unaffected
by the strip (synthetic tests confirm zero false positives on clean
input). Results below are directional only — they corroborate the
synthetic-test correctness with real similarity numbers, not a
statistical retrieval-quality finding.

Read-only against ChromaDB. No writes. Spend: ~$0.0008 (8 small
embeddings of `text-embedding-3-large`).
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import chromadb
from openai import OpenAI

from ingester.loaders.types.google_doc_handler import _strip_editor_metadata


CHROMA_PATH = "/Users/danielsmith/Claude - RF 2.0/chroma_db"
COLLECTION = "rf_reference_library"
SUGAR_SWAPS_CHUNK_ID = (
    "drive:3-marketing:1ucqhpCFg5fmj78XyU2yj0ANGM3kJuG7Tuut1jBd2Vrk:0000"
)
EMBED_MODEL = "text-embedding-3-large"


# M-38-A: topical fertility queries — Sugar Swaps should match strongly
# on these. Expect strip-ON to be ~equal-or-better (less noise diluting
# the topical signal).
QUERIES_TOPICAL = [
    "sugar substitutes for fertility",
    "how does sugar affect hormones",
    "low glycemic foods for egg quality",
]

# M-38-B: pollution-adjacent queries — should match the polluted text
# higher than the cleaned text. If strip-ON shows lower similarity
# here, that confirms the strip is removing real noise that was
# attracting off-topic queries.
QUERIES_POLLUTION = [
    "canva design template",
    "page 1 cover layout",
    "how to edit a canva document",
]


def cosine(a, b):
    """Cosine similarity between two embedding vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def main():
    # 1) Fetch the live Sugar Swaps chunk text
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    col = client.get_collection(COLLECTION)
    res = col.get(ids=[SUGAR_SWAPS_CHUNK_ID])
    if not res["ids"]:
        print(f"FAIL: chunk id not found: {SUGAR_SWAPS_CHUNK_ID}")
        sys.exit(1)
    text_off = res["documents"][0]
    text_on = _strip_editor_metadata(text_off)

    print("=" * 70)
    print("BACKLOG #38 — live A/B on Sugar Swaps Canva strip")
    print("=" * 70)
    print(f"Chunk id:       {SUGAR_SWAPS_CHUNK_ID}")
    print(f"strip-OFF len:  {len(text_off):,} chars / {len(text_off.split()):,} words")
    print(f"strip-ON  len:  {len(text_on):,} chars / {len(text_on.split()):,} words")
    print(f"delta:          {len(text_off) - len(text_on):,} chars removed")
    print()
    print("strip-OFF head (first 250 chars):")
    print("  " + repr(text_off[:250]))
    print()
    print("strip-ON  head (first 250 chars):")
    print("  " + repr(text_on[:250]))
    print()

    if text_off == text_on:
        print("WARN: strip produced no change. Synthetic tests pass, so this")
        print("would mean the live chunk has no patterns the strip targets.")
        print("Look at the head above to debug.")
        sys.exit(2)

    # 2) Embed both chunk versions + all queries in one batched call
    oai = OpenAI()
    inputs = [text_off, text_on] + QUERIES_TOPICAL + QUERIES_POLLUTION
    print(f"Embedding {len(inputs)} inputs via {EMBED_MODEL} ...")
    resp = oai.embeddings.create(model=EMBED_MODEL, input=inputs)
    embs = [d.embedding for d in resp.data]
    emb_off = embs[0]
    emb_on = embs[1]
    emb_topical = embs[2:2 + len(QUERIES_TOPICAL)]
    emb_pollution = embs[2 + len(QUERIES_TOPICAL):]
    usage_tokens = resp.usage.total_tokens
    # text-embedding-3-large = $0.13 per 1M tokens
    est_cost = usage_tokens * 0.13 / 1_000_000
    print(
        f"  embedded ok. usage={usage_tokens:,} tokens, est ${est_cost:.6f}"
    )
    print()

    # 3) Cosine similarities
    def report(label, queries, query_embs):
        print(f"--- {label} ---")
        print(f"{'query':<45} {'OFF':>8} {'ON':>8} {'Δ':>8} {'%Δ':>8}")
        for q, qe in zip(queries, query_embs):
            s_off = cosine(qe, emb_off)
            s_on = cosine(qe, emb_on)
            d = s_on - s_off
            pct = (d / s_off * 100) if s_off else 0.0
            print(f"{q[:44]:<45} {s_off:>8.4f} {s_on:>8.4f} {d:>+8.4f} {pct:>+7.2f}%")
        print()

    report("M-38-A: TOPICAL queries (expect strip-ON ≥ strip-OFF)",
           QUERIES_TOPICAL, emb_topical)
    report("M-38-B: POLLUTION-adjacent queries (expect strip-ON < strip-OFF)",
           QUERIES_POLLUTION, emb_pollution)

    print("Note: n=1 chunk. Directional read only — corroborates the 15/15")
    print("synthetic tests with live similarity numbers; does not constitute")
    print("a statistical retrieval-quality finding.")
    print()
    print(f"BACKLOG #38 — live A/B complete. Spend: ~${est_cost:.6f}")


if __name__ == "__main__":
    main()
