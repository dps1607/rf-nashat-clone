"""Post-process merge pass: combine sub-250w chunks into their smaller neighbor.
Reads a4m_transcript_chunks_full.json, writes a4m_transcript_chunks_merged.json.
Preserves metadata from the chunk being kept; appends text with \\n separator.
Does NOT touch ChromaDB.
"""
import json
from pathlib import Path

FLOOR = 250
IN_PATH = Path("data/a4m_transcript_chunks_full.json")
OUT_PATH = Path("data/a4m_transcript_chunks_merged.json")

chunks = json.loads(IN_PATH.read_text())
print(f"Loaded {len(chunks)} chunks")

# Group by module, preserve order
by_mod = {}
for c in chunks:
    by_mod.setdefault(c["module_number"], []).append(c)

def merge_two(a, b):
    """Merge b into a. Keep a's metadata, append b's text."""
    merged = dict(a)
    merged["text"] = a["text"] + "\n" + b["text"]
    merged["word_count"] = a["word_count"] + b["word_count"]
    if "end_time" in b:
        merged["end_time"] = b["end_time"]
    sp = set(a.get("speakers", [])) | set(b.get("speakers", []))
    merged["speakers"] = sorted(sp)
    return merged

merged_all = []
for mod_num in sorted(by_mod):
    mod_chunks = list(by_mod[mod_num])
    changed = True
    while changed:
        changed = False
        for i, c in enumerate(mod_chunks):
            if c["word_count"] >= FLOOR:
                continue
            if len(mod_chunks) == 1:
                break
            # Pick smaller neighbor
            prev_w = mod_chunks[i-1]["word_count"] if i > 0 else float("inf")
            next_w = mod_chunks[i+1]["word_count"] if i < len(mod_chunks)-1 else float("inf")
            if prev_w <= next_w:
                mod_chunks[i-1] = merge_two(mod_chunks[i-1], c)
                mod_chunks.pop(i)
            else:
                mod_chunks[i] = merge_two(c, mod_chunks[i+1])
                mod_chunks.pop(i+1)
            changed = True
            break
    # Reindex chunk_index within module
    for idx, c in enumerate(mod_chunks):
        c["chunk_index"] = idx
    merged_all.extend(mod_chunks)

wc = [c["word_count"] for c in merged_all]
print(f"After merge: {len(merged_all)} chunks")
print(f"Mean: {sum(wc)/len(wc):.0f}w  Min: {min(wc)}  Max: {max(wc)}")
under = sum(1 for w in wc if w < FLOOR)
print(f"Chunks still under {FLOOR}w: {under}")
print()
print("Per-module:")
bm = {}
for c in merged_all:
    bm.setdefault(c["module_number"], []).append(c["word_count"])
for m in sorted(bm):
    ws = bm[m]
    print(f"  Mod {m:>2}: {len(ws):>3} chunks  mean={sum(ws)/len(ws):.0f}  min={min(ws)}  max={max(ws)}")

OUT_PATH.write_text(json.dumps(merged_all, indent=2))
print(f"\nWrote: {OUT_PATH}")
