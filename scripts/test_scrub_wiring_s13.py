"""Session 13 — smoke test the scrub wiring through chunk_text()."""
import sys
sys.path.insert(0, '.')
from ingester.loaders._drive_common import chunk_text

para = ("This is a test paragraph about fertility supplements. " * 15).strip()
text = (
    "by Dr. Nashat Latib & Dr. Christina Massinople\n\n"
    + para + "\n\n"
    + para + "\n\n"
    + "See also Dr. Chris for dosing guidance. " + para
)

chunks = chunk_text(text)
print("chunks: {}".format(len(chunks)))
for c in chunks:
    print("  idx={} wc={} name_replacements={}".format(
        c["chunk_index"], c["word_count"], c["name_replacements"]
    ))
    print("    text: {!r}".format(c["text"][:120]))

joined = " ".join(c["text"] for c in chunks)
assert "Christina" not in joined, "Christina leaked!"
assert "Massinople" not in joined, "Massinople leaked!"
assert any(c["name_replacements"] > 0 for c in chunks), "no replacements counted!"
print("SCRUB WIRED: PASS")
