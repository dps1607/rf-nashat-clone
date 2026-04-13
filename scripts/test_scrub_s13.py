"""Session 13 scrub battery — includes session 12 tests + triple-dedup fix."""
import sys
sys.path.insert(0, '.')
from ingester.text.scrub import scrub_text

tests = [
    # Session 12 core
    ("by Dr. Nashat Latib & Dr. Christina Massinople", "by Dr. Nashat Latib"),
    ("body mass index", "body mass index"),
    ("Merry Christmas", "Merry Christmas"),
    ("Dr. Chris said 500mg", "Dr. Nashat Latib said 500mg"),
    ("Dr. Christina Massinople, MD", "Dr. Nashat Latib, MD"),
    ("Christina Massinople recommends", "Dr. Nashat Latib recommends"),
    ("Dr. Massinople Park", "Dr. Nashat Latib"),
    ("Massinople Park", "Dr. Nashat Latib"),
    ("Dr. Massinople", "Dr. Nashat Latib"),
    ("Massinople said", "Dr. Nashat Latib said"),
    ("Dr. Christina told me", "Dr. Nashat Latib told me"),
    ("Dr. Mass said", "Dr. Nashat Latib said"),
    ("by Mass", "by Dr. Nashat Latib"),
    ("Mass Park", "Dr. Nashat Latib"),
    # Dedup pairwise
    ("Dr. Chris & Dr. Christina", "Dr. Nashat Latib"),
    ("Dr. Chris and Dr. Christina", "Dr. Nashat Latib"),
    ("Dr. Chris, Dr. Christina", "Dr. Nashat Latib"),
    # Triple (session 13 fix target)
    ("Dr. Chris, Dr. Christina, and Dr. Massinople", "Dr. Nashat Latib"),
    # Negative controls
    ("lean body mass and mass spectrometry", "lean body mass and mass spectrometry"),
]

fails = 0
for inp, expected in tests:
    out, n = scrub_text(inp)
    status = "OK  " if out == expected else "FAIL"
    if out != expected:
        fails += 1
        print(f"  {status}: {inp!r}")
        print(f"        got:      {out!r}")
        print(f"        expected: {expected!r}")

print(f"\n{len(tests)-fails}/{len(tests)} passing")
sys.exit(0 if fails == 0 else 1)
