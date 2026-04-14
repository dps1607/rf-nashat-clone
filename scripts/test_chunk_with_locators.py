"""Smoke test for chunk_with_locators() — Option Q end-to-end pipeline.
Builds stitched text with markers + scrub patterns, confirms:
  - markers stripped from final chunk text
  - scrub fires (no collaborator names leak)
  - display_locator derives correctly from markers
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingester.loaders.types import chunk_with_locators, make_page_marker

body = "Vitamin D3 supports healthy ovulatory function. " * 15
stitched = (
    make_page_marker("PAGE", 1) + "\n\n" + body + "\n\n" +
    make_page_marker("PAGE", 2) + "\n\n" +
    "Co-authored by Dr. Nashat Latib and Dr. Christina Massinople. " + body + "\n\n" +
    make_page_marker("PAGE", 3) + "\n\n" + body
)

chunks = chunk_with_locators(stitched)
print(f"chunk count: {len(chunks)}")
for c in chunks:
    print(f"  idx={c['chunk_index']} wc={c['word_count']} "
          f"nr={c['name_replacements']} loc={c['display_locator']!r}")
    print(f"    preview: {c['text'][:80]!r}")

joined = " ".join(c["text"] for c in chunks)
assert "[PAGE" not in joined, "markers leaked into final chunk text"
assert "Christina" not in joined, "Christina leaked through scrub"
assert "Massinople" not in joined, "Massinople leaked through scrub"
assert any(c["name_replacements"] > 0 for c in chunks), "no scrub hits recorded"
assert any(c["display_locator"] for c in chunks), "no locator derived"
for c in chunks:
    if c["display_locator"] is not None:
        loc = c["display_locator"]
        assert loc.startswith("p. ") or loc.startswith("pp. "), \
            f"unexpected locator format: {loc!r}"
print("chunk_with_locators smoke: PASS")
