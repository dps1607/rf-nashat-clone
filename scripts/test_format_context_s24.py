"""
Test format_context + chunk_to_display — session 24 (BACKLOG #18)
==================================================================

Verifies:
- chunk_to_display() normalizes all 4 chunk populations uniformly
- "Unknown", "None", None, whitespace all normalize to ""
- Missing metadata fields degrade gracefully — no "Presenter: Unknown"
- YAML-driven render configs control what surfaces to the LLM
- Protected fields (client_rfids, client_names) never appear in output
  regardless of any YAML knob state
- format_context() groups by collection in canonical order
- Empty inputs produce empty output

Runs synthetically — zero Chroma reads, zero network, zero embeddings.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Repo-root path shim
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rag_server.display import (
    chunk_to_display,
    format_context,
    _clean,
    _DEFAULT_RENDER,
)
from config.schema import RenderConfig


# ============================================================================
# FIXTURES
# ============================================================================

def _v3_pdf_chunk(**overrides) -> dict:
    """A v3 PDF chunk with full metadata (Egg Health Guide shape)."""
    meta = {
        "source_pipeline": "drive_loader_v3",
        "v3_category": "pdf",
        "source_file_name": "RH - Egg Health Guide.pdf",
        "display_locator": "pp. 1-3",
        "source_web_view_link": "https://drive.google.com/file/d/1abc/view",
        "display_speaker": "",
        "display_topics": "egg quality, AMH",
        "display_timestamp": "",
        "display_date": "",
        "library_name": "rf_reference_library",
    }
    meta.update(overrides)
    return {
        "text": "Egg quality is improved by CoQ10...",
        "metadata": meta,
        "source": "rf_reference_library",
        "distance": 0.3,
    }


def _v3_google_doc_chunk(**overrides) -> dict:
    """A v3 Google Doc chunk (Sugar Swaps shape)."""
    meta = {
        "source_pipeline": "drive_loader_v3",
        "v3_category": "v2_google_doc",
        "source_file_name": "[RH] The Fertility-Smart Sugar Swap Guide",
        "display_locator": "§1",
        "source_web_view_link": "https://docs.google.com/document/d/xyz",
        "display_speaker": "",
        "display_topics": "sugar, blood glucose",
        "display_timestamp": "",
        "library_name": "rf_reference_library",
    }
    meta.update(overrides)
    return {
        "text": "Swap refined sugar for...",
        "metadata": meta,
        "source": "rf_reference_library",
        "distance": 0.4,
    }


def _legacy_a4m_chunk(**overrides) -> dict:
    """Legacy A4M lecture chunk (pre-v3 metadata shape)."""
    meta = {
        "module_number": "3",
        "module_topic": "Male Fertility Assessment",
        "speaker": "Dr. Smith",
        "content_type": "transcript",
        "course": "A4M Fertility",
    }
    meta.update(overrides)
    return {
        "text": "Semen analysis reveals...",
        "metadata": meta,
        "source": "rf_reference_library",
        "distance": 0.35,
    }


def _coaching_chunk(**overrides) -> dict:
    """Coaching transcript chunk (real shape — has client identifiers)."""
    meta = {
        "call_date": "2024-05-03",
        "call_file": "FKSP_2024-05-03_call3.m4a",
        "call_fksp_id": "FKSP-042",
        "call_section": "midcall",
        "call_type": "coaching",
        "client_names": "Jane Doe",
        "client_rfids": "RF-1234",
        "coaches": "Dr. Nashat Latib",
        "topics": "AMH, egg quality, supplementation",
    }
    meta.update(overrides)
    return {
        "text": "When AMH is low, we focus on...",
        "metadata": meta,
        "source": "rf_coaching_transcripts",
        "distance": 0.28,
    }


# ============================================================================
# TEST RUNNER
# ============================================================================

_RESULTS: list[tuple[str, bool, str]] = []


def _t(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, condition, detail))
    status = "PASS" if condition else "FAIL"
    line = f"  [{status}] {name}"
    if detail and not condition:
        line += f"  --  {detail}"
    print(line)


# ============================================================================
# _clean() — the normalizer
# ============================================================================

def test_clean() -> None:
    print()
    print("_clean() normalization:")
    _t("None -> ''", _clean(None) == "")
    _t("'' -> ''", _clean("") == "")
    _t("'   ' -> ''", _clean("   ") == "")
    _t("'Unknown' -> ''", _clean("Unknown") == "")
    _t("'unknown' -> ''", _clean("unknown") == "")
    _t("'UNKNOWN' -> ''", _clean("UNKNOWN") == "")
    _t("'None' -> ''", _clean("None") == "")
    _t("'  Dr. Smith  ' -> 'Dr. Smith'",
       _clean("  Dr. Smith  ") == "Dr. Smith")
    _t("integer 3 -> '3'", _clean(3) == "3")


# ============================================================================
# chunk_to_display() — per-population coverage
# ============================================================================

def test_v3_pdf_full() -> None:
    d = chunk_to_display(_v3_pdf_chunk())
    _t("v3 pdf full: source_label set",
       d["source_label"] == "RH - Egg Health Guide.pdf")
    _t("v3 pdf full: locator set", d["locator"] == "pp. 1-3")
    _t("v3 pdf full: link set", d["link"].startswith("https://drive.google"))
    _t("v3 pdf full: topics set", d["topics"] == "egg quality, AMH")
    _t("v3 pdf full: speaker empty (no author)", d["speaker"] == "")
    _t("v3 pdf full: date empty (no date meta)", d["date"] == "")
    _t("v3 pdf full: item_label correct", d["item_label"] == "Reference")


def test_v3_pdf_degraded() -> None:
    """PDF missing link and locator (e.g., single-page PDF, no Drive link)."""
    d = chunk_to_display(_v3_pdf_chunk(
        display_locator="",
        source_web_view_link="",
    ))
    _t("v3 pdf degraded: source_label still set",
       d["source_label"] == "RH - Egg Health Guide.pdf")
    _t("v3 pdf degraded: locator empty", d["locator"] == "")
    _t("v3 pdf degraded: link empty", d["link"] == "")


def test_v3_google_doc_no_headings() -> None:
    """Google Doc with empty locator (DFH case — no h1-h6 tags)."""
    d = chunk_to_display(_v3_google_doc_chunk(display_locator=""))
    _t("v3 gdoc no-headings: source_label set",
       d["source_label"].startswith("[RH]"))
    _t("v3 gdoc no-headings: locator empty", d["locator"] == "")
    _t("v3 gdoc no-headings: link still set", d["link"] != "")


def test_legacy_a4m_full() -> None:
    d = chunk_to_display(_legacy_a4m_chunk())
    _t("a4m full: source_label from module",
       d["source_label"] == "A4M Module 3: Male Fertility Assessment")
    _t("a4m full: speaker from legacy field",
       d["speaker"] == "Dr. Smith")
    _t("a4m full: locator empty (no display_locator)", d["locator"] == "")
    _t("a4m full: link empty (no webViewLink)", d["link"] == "")


def test_legacy_a4m_unknown_speaker() -> None:
    """M3 transcript case — speaker literal 'Unknown' must normalize to ''."""
    d = chunk_to_display(_legacy_a4m_chunk(speaker="Unknown"))
    _t("a4m unknown speaker: normalized to empty", d["speaker"] == "")


def test_legacy_a4m_missing_module() -> None:
    """A4M chunk with only a topic, no module number."""
    d = chunk_to_display(_legacy_a4m_chunk(
        module_number="",
        module_topic="Nutrition Basics",
    ))
    _t("a4m partial: source_label uses topic",
       d["source_label"] == "A4M: Nutrition Basics")


def test_legacy_a4m_no_meta() -> None:
    """Chunk with zero useful metadata — should render just text."""
    d = chunk_to_display({
        "text": "Bare chunk text",
        "metadata": {},
        "source": "rf_reference_library",
    })
    _t("a4m no meta: source_label empty", d["source_label"] == "")
    _t("a4m no meta: speaker empty", d["speaker"] == "")
    _t("a4m no meta: text preserved", d["text"] == "Bare chunk text")


def test_coaching_default() -> None:
    """Coaching default render: topics only, NO speaker/date/clients."""
    c = _coaching_chunk()
    d = chunk_to_display(c)
    _t("coaching default: source_label empty (section header scopes)",
       d["source_label"] == "")
    _t("coaching default: topics surfaced",
       d["topics"] == "AMH, egg quality, supplementation")
    _t("coaching default: speaker absorbed (empty)", d["speaker"] == "")
    _t("coaching default: date empty (protected)", d["date"] == "")
    _t("coaching default: link empty", d["link"] == "")
    # Client identifiers: verify they're NOT in any display field value
    all_values = " ".join(str(v) for v in d.values())
    _t("coaching default: client_rfids NOT in display",
       "RF-1234" not in all_values)
    _t("coaching default: client_names NOT in display",
       "Jane Doe" not in all_values)
    _t("coaching default: call_fksp_id NOT in display",
       "FKSP-042" not in all_values)
    # But: original chunk metadata must still have them for downstream systems
    _t("coaching default: metadata preserves client_rfids",
       c["metadata"]["client_rfids"] == "RF-1234")
    _t("coaching default: metadata preserves client_names",
       c["metadata"]["client_names"] == "Jane Doe")


def test_coaching_missing_topics() -> None:
    d = chunk_to_display(_coaching_chunk(topics=""))
    _t("coaching no topics: topics empty", d["topics"] == "")


# ============================================================================
# (main block at bottom of file)
# ============================================================================



# ============================================================================
# YAML-driven render configs
# ============================================================================

def test_render_config_overrides_default() -> None:
    """YAML can turn off a field that default has on."""
    configs = {
        "rf_reference_library": RenderConfig(
            show_source_label=True,
            show_speaker=False,       # off, overrides default on
            show_topics=False,
            show_locator=True,
            show_link=False,          # off, overrides default on
            show_date=False,
        ),
    }
    d = chunk_to_display(_legacy_a4m_chunk(), configs)
    _t("render override: speaker off", d["speaker"] == "")
    _t("render override: topics off", d["topics"] == "")
    _t("render override: link off (meta had none anyway)", d["link"] == "")
    _t("render override: source_label still on",
       d["source_label"] != "")


def test_render_config_coaching_date_opt_in() -> None:
    """Even if YAML says show_date=true for coaching, code protection wins."""
    configs = {
        "rf_coaching_transcripts": RenderConfig(
            show_source_label=True,
            show_topics=True,
            show_speaker=True,   # YAML asks for it
            show_date=True,      # YAML asks for it
            show_locator=False,
            show_link=False,
        ),
    }
    d = chunk_to_display(_coaching_chunk(), configs)
    _t("coaching + YAML opts in to speaker: still absorbed",
       d["speaker"] == "")
    _t("coaching + YAML opts in to date: still protected",
       d["date"] == "")


def test_render_config_missing_collection() -> None:
    """Collection absent from render dict -> defaults apply."""
    configs = {"rf_published_content": RenderConfig(show_topics=True)}
    # Pass coaching chunk; its collection isn't in the config dict
    d = chunk_to_display(_coaching_chunk(), configs)
    _t("missing collection: coaching defaults apply (topics on)",
       d["topics"] != "")


def test_render_config_empty_map() -> None:
    """Empty render dict -> defaults apply everywhere."""
    d = chunk_to_display(_v3_pdf_chunk(), render_configs={})
    _t("empty render map: v3 defaults apply (source + link on)",
       d["source_label"] != "" and d["link"] != "")


# ============================================================================
# format_context() — end-to-end rendering
# ============================================================================

def test_format_context_empty() -> None:
    _t("format_context empty list -> ''", format_context([]) == "")


def test_format_context_pdf_with_link() -> None:
    rendered = format_context([_v3_pdf_chunk()])
    expected_bits = [
        "REFERENCE KNOWLEDGE",
        "--- Reference 1 ---",
        "Source: RH - Egg Health Guide.pdf — pp. 1-3",
        "Link: https://drive.google.com",
        "Topics: egg quality, AMH",
        "Egg quality is improved by CoQ10",
    ]
    ok = all(bit in rendered for bit in expected_bits)
    _t("format_context pdf: all expected bits present", ok,
       f"missing: {[b for b in expected_bits if b not in rendered]}")
    _t("format_context pdf: no 'Presenter:' line (no speaker)",
       "Presenter:" not in rendered)


def test_format_context_degraded_pdf() -> None:
    """PDF missing locator/link — Source line only has the filename."""
    rendered = format_context([_v3_pdf_chunk(
        display_locator="",
        source_web_view_link="",
    )])
    _t("degraded pdf: source present",
       "Source: RH - Egg Health Guide.pdf" in rendered)
    _t("degraded pdf: no Link line", "Link:" not in rendered)
    _t("degraded pdf: no em-dash in Source (single bit)",
       "Source: RH - Egg Health Guide.pdf —" not in rendered)


def test_format_context_a4m_unknown_speaker() -> None:
    rendered = format_context([_legacy_a4m_chunk(speaker="Unknown")])
    _t("a4m unknown speaker: no 'Presenter: Unknown'",
       "Unknown" not in rendered)
    _t("a4m unknown speaker: no Presenter line at all",
       "Presenter:" not in rendered)
    _t("a4m unknown speaker: source label still rendered",
       "A4M Module 3" in rendered)


def test_format_context_coaching_no_leaks() -> None:
    """The critical safety test — client identifiers must not appear."""
    rendered = format_context([_coaching_chunk()])
    _t("coaching render: no RFID in output",
       "RF-1234" not in rendered)
    _t("coaching render: no client name in output",
       "Jane Doe" not in rendered)
    _t("coaching render: no FKSP-ID in output",
       "FKSP-042" not in rendered)
    _t("coaching render: no call filename",
       "FKSP_2024-05-03_call3" not in rendered)
    _t("coaching render: no date (protected)",
       "2024-05-03" not in rendered)
    _t("coaching render: no coach name",
       "Dr. Nashat Latib" not in rendered)
    _t("coaching render: topics DO appear",
       "AMH, egg quality" in rendered)
    _t("coaching render: item label correct",
       "--- Coaching Exchange 1 ---" in rendered)


def test_format_context_mixed_populations() -> None:
    """All 4 types in one render — groups and orders correctly."""
    chunks = [
        _v3_pdf_chunk(),
        _coaching_chunk(),
        _legacy_a4m_chunk(),
        _v3_google_doc_chunk(),
    ]
    rendered = format_context(chunks)
    # Coaching section header should appear before reference header
    coaching_idx = rendered.find("COACHING CONTEXT")
    reference_idx = rendered.find("REFERENCE KNOWLEDGE")
    _t("mixed: coaching section present", coaching_idx >= 0)
    _t("mixed: reference section present", reference_idx >= 0)
    _t("mixed: coaching section comes first",
       coaching_idx < reference_idx)
    # All 3 reference-library chunks should land in the reference section,
    # indexed 1, 2, 3
    _t("mixed: Reference 1 present", "--- Reference 1 ---" in rendered)
    _t("mixed: Reference 2 present", "--- Reference 2 ---" in rendered)
    _t("mixed: Reference 3 present", "--- Reference 3 ---" in rendered)
    _t("mixed: coaching exchange 1 present",
       "--- Coaching Exchange 1 ---" in rendered)
    # Safety again on the integrated render
    _t("mixed: no client RFID", "RF-1234" not in rendered)
    _t("mixed: no client name", "Jane Doe" not in rendered)


def test_format_context_unknown_collection() -> None:
    """Unknown collection name degrades gracefully, no crash."""
    chunk = {
        "text": "Orphan chunk",
        "metadata": {},
        "source": "rf_future_collection_xyz",
    }
    rendered = format_context([chunk])
    _t("unknown collection: renders without crash", rendered != "")
    _t("unknown collection: emits fallback header",
       "CONTEXT (rf_future_collection_xyz)" in rendered)
    _t("unknown collection: preserves text", "Orphan chunk" in rendered)


# ============================================================================
# RUN ALL + SUMMARY
# ============================================================================

if __name__ == "__main__":
    test_clean()
    print()
    print("chunk_to_display per-population:")
    test_v3_pdf_full()
    test_v3_pdf_degraded()
    test_v3_google_doc_no_headings()
    test_legacy_a4m_full()
    test_legacy_a4m_unknown_speaker()
    test_legacy_a4m_missing_module()
    test_legacy_a4m_no_meta()
    test_coaching_default()
    test_coaching_missing_topics()

    print()
    print("YAML-driven render configs:")
    test_render_config_overrides_default()
    test_render_config_coaching_date_opt_in()
    test_render_config_missing_collection()
    test_render_config_empty_map()

    print()
    print("format_context end-to-end:")
    test_format_context_empty()
    test_format_context_pdf_with_link()
    test_format_context_degraded_pdf()
    test_format_context_a4m_unknown_speaker()
    test_format_context_coaching_no_leaks()
    test_format_context_mixed_populations()
    test_format_context_unknown_collection()

    total = len(_RESULTS)
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    failed = total - passed
    print()
    print("=" * 60)
    print(f"PASS: {passed}/{total}  FAIL: {failed}")
    if failed:
        print()
        print("Failures:")
        for name, ok, detail in _RESULTS:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)
