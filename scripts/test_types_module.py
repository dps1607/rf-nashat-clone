"""Smoke test for ingester.loaders.types module helpers.
Verifies marker round-tripping and locator derivation before pdf_handler
is built on top of it."""
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingester.loaders.types import (
    ExtractResult,
    make_page_marker,
    strip_markers,
    derive_locator,
    derive_timestamp,
)

# 1. Import smoke
er = ExtractResult(stitched_text="hello", extraction_method="pdf_text")
assert er.stitched_text == "hello"
assert er.warnings == []
assert er.extra == {}

# 2. Marker round-trip
m1 = make_page_marker("PAGE", 4)
m2 = make_page_marker("PAGE", 5)
text = f"{m1} this is page four content {m2} this is page five content"
assert "[PAGE 4]" in text
stripped = strip_markers(text)
assert "[PAGE" not in stripped
assert "page four" in stripped and "page five" in stripped

# 3. derive_locator — single page
loc = derive_locator(f"{m1} some chunk text here")
assert loc == "p. 4", f"expected 'p. 4', got {loc!r}"

# 4. derive_locator — page range
loc = derive_locator(f"{m1} content {m2} more content")
assert loc == "pp. 4-5", f"expected 'pp. 4-5', got {loc!r}"

# 5. derive_locator — slide range
s1 = make_page_marker("SLIDE", 12)
s2 = make_page_marker("SLIDE", 14)
loc = derive_locator(f"{s1} a {s2}")
assert loc == "slides 12-14"

# 6. derive_locator — single row
loc = derive_locator(make_page_marker("ROW", 47) + " supplement data")
assert loc == "row 47"

# 7. derive_locator — row range
loc = derive_locator(
    make_page_marker("ROW", 40) + " a " + make_page_marker("ROW", 47)
)
assert loc == "rows 40-47"

# 8. derive_locator — section range
loc = derive_locator(
    make_page_marker("SECTION", 3) + " a " + make_page_marker("SECTION", 5)
)
assert loc == "§§3-5"

# 9. derive_locator — no markers
assert derive_locator("just plain text no markers") is None

# 10. derive_timestamp
t1 = make_page_marker("TIME", "00:14:32")
t2 = make_page_marker("TIME", "00:16:10")
ts = derive_timestamp(f"{t1} hello {t2}")
assert ts == "[00:14:32]-[00:16:10]", f"got {ts!r}"
assert derive_timestamp("no time markers") is None

# 11. derive_locator returns None for TIME-only chunks
assert derive_locator(f"{t1} content") is None

# 12. strip_markers collapses whitespace cleanly
messy = f"text {make_page_marker('PAGE', 1)}  more   text"
cleaned = strip_markers(messy)
assert "  " not in cleaned, f"double space not cleaned: {cleaned!r}"

print("types helpers: 12/12 passing")
