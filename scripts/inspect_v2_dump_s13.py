"""Session 13 — inspect the v2 dump for scrub verification."""
import json
from pathlib import Path

dump = json.loads(Path("data/dumps/supplement_info_pilot_v2_s13.json").read_text())

print("=" * 70)
print("SUMMARY")
print("=" * 70)
for k, v in dump["summary"].items():
    if k != "vision_ledger":
        print(f"  {k}: {v}")

print()
print("=" * 70)
print("FILES")
print("=" * 70)
for f in dump["files"]:
    status = "SKIPPED" if f.get("skipped") else "INGESTED"
    print(f"  [{status}] {f['name']}")
    print(f"    stitched: {f['stitched_chars']:,} chars / {f['stitched_words']:,} words")
    print(f"    images:   {f['stream_image_count']}  chunks: {f['chunk_count']}")
    if f.get("skipped"):
        print(f"    reason:   {f.get('skip_reason')}")

print()
print("=" * 70)
print("SCRUB VERIFICATION — name_replacements per chunk")
print("=" * 70)
total_replacements = 0
leaks = 0
for c in dump["chunks"]:
    md = c["metadata"]
    nr = md.get("name_replacements", "MISSING")
    total_replacements += nr if isinstance(nr, int) else 0
    # Check for any leaked names
    lower = c["text"].lower()
    if "christina" in lower or "massinople" in lower:
        leaks += 1
        print(f"  LEAK in {md['source_file_name']} chunk {md['chunk_index']}")
    print(f"  {md['source_file_name'][:50]:50} chunk {md['chunk_index']} "
          f"wc={md['word_count']} name_replacements={nr}")

print()
print(f"  total replacements across all chunks: {total_replacements}")
print(f"  leak count (should be 0): {leaks}")

print()
print("=" * 70)
print("FIRST CHUNK PREVIEW from each image-heavy doc")
print("=" * 70)
seen = set()
for c in dump["chunks"]:
    md = c["metadata"]
    name = md["source_file_name"]
    if name in seen or md["chunk_index"] != 0:
        continue
    if "Professional" in name:
        continue
    seen.add(name)
    print(f"\n--- {name} chunk 0 ---")
    print(f"    name_replacements: {md['name_replacements']}")
    print(f"    image_derived_word_count: {md['image_derived_word_count']}")
    print(f"    word_count: {md['word_count']}")
    # First 500 chars of text
    txt = c["text"]
    print(f"    text[:600]:")
    for line in txt[:600].split("\n"):
        print(f"      {line}")
