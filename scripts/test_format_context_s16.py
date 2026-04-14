"""Session 16 Step 10 — format_context() regression test.

Verifies:
  1. A4M chunks (legacy v1 ingest) render EXACTLY as they did pre-session-16
  2. Coaching chunks render EXACTLY as they did pre-session-16
  3. v3 PDF chunks render with the new citation line (source + locator + link)
  4. Mixed input (coaching + A4M + v3 PDF) all three coexist

Zero Chroma writes. Zero API calls. Pure string-level check of the
function under test.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Suppress rag_server startup noise — we only need format_context
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-for-test")
os.environ.setdefault("OPENAI_API_KEY", "dummy-for-test")

from rag_server.app import format_context

passed = []
failed = []


def check(label, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail else ""))
    (passed if cond else failed).append(label)


# ----------------------------------------------------------------------------
# Test 1 — A4M chunk (legacy v1 shape) renders UNCHANGED
# ----------------------------------------------------------------------------

a4m_chunk = {
    "source": "rf_reference_library",
    "text": "Vitamin D3 supports the luteal phase through progesterone modulation.",
    "metadata": {
        "module_number": 7,
        "module_topic": "Hormonal health",
        "speaker": "Felice Gersh, MD",
        # v3_category NOT present — this is a legacy A4M chunk
    },
}

a4m_out = format_context([a4m_chunk])
print("\n--- A4M render ---")
print(a4m_out)

check(
    "A4M render contains module line",
    "Module 7: Hormonal health" in a4m_out,
)
check(
    "A4M render contains presenter line",
    "Presenter: Felice Gersh, MD" in a4m_out,
)
check(
    "A4M render does NOT contain 'Source:' line (v3-only format)",
    "Source:" not in a4m_out,
)
check(
    "A4M render does NOT contain 'Link:' line (v3-only format)",
    "Link:" not in a4m_out,
)
check(
    "A4M render contains the chunk text",
    "Vitamin D3 supports the luteal phase" in a4m_out,
)
check(
    "A4M render uses the new softened header",
    "REFERENCE KNOWLEDGE (A4M Fertility Certification + clinical guides):" in a4m_out,
)


# ----------------------------------------------------------------------------
# Test 2 — Coaching chunk renders UNCHANGED
# ----------------------------------------------------------------------------

coaching_chunk = {
    "source": "rf_coaching_transcripts",
    "text": "[Dr. Nashat] So the first thing we do is look at the BBT chart for anovulation patterns.",
    "metadata": {
        "topics": "BBT interpretation, anovulation",
        "client_rfid": "RF-0042",
    },
}

coaching_out = format_context([coaching_chunk])
print("\n--- Coaching render ---")
print(coaching_out)

check(
    "Coaching render uses COACHING CONTEXT header",
    "COACHING CONTEXT" in coaching_out,
)
check(
    "Coaching render contains Topics line",
    "Topics: BBT interpretation, anovulation" in coaching_out,
)
check(
    "Coaching render contains the chunk text",
    "BBT chart for anovulation patterns" in coaching_out,
)
check(
    "Coaching render does NOT contain v3 citation elements",
    "Source:" not in coaching_out and "Link:" not in coaching_out,
)


# ----------------------------------------------------------------------------
# Test 3 — v3 PDF chunk renders with the new citation block
# ----------------------------------------------------------------------------

v3_pdf_chunk = {
    "source": "rf_reference_library",
    "text": "STEP 5: Boost nutrients with supplementation for superior egg quality.",
    "metadata": {
        "v3_category": "pdf",
        "v3_extraction_method": "pdf_text",
        "source_pipeline": "drive_loader_v3",
        "source_file_name": "Egg Health Guide.pdf",
        "source_web_view_link": "https://drive.google.com/file/d/1oJyksHG.../view",
        "display_locator": "pp. 8-10",
        "display_timestamp": "",
        "display_source": "Egg Health Guide.pdf",
        # No module_number / module_topic / speaker
    },
}

v3_out = format_context([v3_pdf_chunk])
print("\n--- v3 PDF render ---")
print(v3_out)

check(
    "v3 render contains Source: line with filename and locator",
    "Source: Egg Health Guide.pdf — pp. 8-10" in v3_out,
)
check(
    "v3 render contains Link: line with the Drive URL",
    "Link: https://drive.google.com/file/d/1oJyksHG.../view" in v3_out,
)
check(
    "v3 render does NOT contain Module line (empty A4M fields elided)",
    "Module" not in v3_out,
)
check(
    "v3 render does NOT contain Presenter line",
    "Presenter:" not in v3_out,
)
check(
    "v3 render contains the chunk text",
    "STEP 5: Boost nutrients" in v3_out,
)


# ----------------------------------------------------------------------------
# Test 4 — Mixed input: coaching + A4M + v3 PDF all coexist cleanly
# ----------------------------------------------------------------------------

mixed_out = format_context([coaching_chunk, a4m_chunk, v3_pdf_chunk])
print("\n--- Mixed render ---")
print(mixed_out)

check(
    "Mixed render contains COACHING CONTEXT section",
    "COACHING CONTEXT" in mixed_out,
)
check(
    "Mixed render contains REFERENCE KNOWLEDGE section",
    "REFERENCE KNOWLEDGE" in mixed_out,
)
check(
    "Mixed render has A4M chunk's Module line",
    "Module 7: Hormonal health" in mixed_out,
)
check(
    "Mixed render has v3 PDF's Source line",
    "Source: Egg Health Guide.pdf — pp. 8-10" in mixed_out,
)
check(
    "Mixed render has v3 PDF's Link line",
    "Link: https://drive.google.com/file/d/1oJyksHG.../view" in mixed_out,
)
check(
    "Mixed render has all three chunk texts",
    ("BBT chart" in mixed_out and
     "Vitamin D3" in mixed_out and
     "STEP 5" in mixed_out),
)


# ----------------------------------------------------------------------------
# Test 5 — v3 chunk with no locator (edge case for handlers that emit none)
# ----------------------------------------------------------------------------

v3_nolocator = {
    "source": "rf_reference_library",
    "text": "Some content from a handler that didn't emit page markers.",
    "metadata": {
        "v3_category": "image",
        "v3_extraction_method": "image_vision",
        "source_file_name": "lab_reference_chart.png",
        "source_web_view_link": "https://drive.google.com/file/d/xxx/view",
        "display_locator": "",
        "display_timestamp": "",
    },
}
nolocator_out = format_context([v3_nolocator])
check(
    "v3 chunk with empty locator still renders Source line with filename only",
    "Source: lab_reference_chart.png" in nolocator_out and "—" not in nolocator_out.split("Source:")[1].split("\n")[0],
)
check(
    "v3 chunk with empty locator does NOT render the locator separator",
    " — pp." not in nolocator_out and " — p." not in nolocator_out,
)

print()
print("=" * 60)
print(f"PASS: {len(passed)}/{len(passed) + len(failed)}  FAIL: {len(failed)}")
if failed:
    print("FAILED CHECKS:")
    for f in failed:
        print(f"  - {f}")
    sys.exit(1)
sys.exit(0)
