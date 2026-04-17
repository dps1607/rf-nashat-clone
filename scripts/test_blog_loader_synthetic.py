#!/usr/bin/env python3
"""BACKLOG #56 — synthetic tests for ingester.blog_loader (TDD).

Runs without network access. Exercises the HTML-to-plain-text extraction,
chunk assembly, metadata construction, and edge-case handling for
WordPress REST API blog post payloads.

Per CURRENT STATE line 60 regression-suite convention:
  - Pure synthetic data, <$0.001 per run
  - Deterministic output across sessions
  - Last-line summary shows X/Y passing

Usage:
  ./venv/bin/python scripts/test_blog_loader_synthetic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make ingester imports work when run directly
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingester.blog_loader import (  # noqa: E402
    extract_plain_text_from_html,
    build_blog_chunk_id,
    build_blog_metadata,
    post_to_file_record,
    SOURCE_PIPELINE,
    V3_CATEGORY,
    EXTRACTION_METHOD,
)


# -----------------------------------------------------------------------------
# Test harness (tiny + zero-dep, matches pattern of test_dedup_synthetic_s19.py)
# -----------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def test(name: str):
    def deco(fn):
        try:
            fn()
            _RESULTS.append((name, True, ""))
        except AssertionError as e:
            _RESULTS.append((name, False, str(e) or "assertion failed"))
        except Exception as e:  # noqa: BLE001
            _RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
        return fn
    return deco


# -----------------------------------------------------------------------------
# 1. extract_plain_text_from_html — stripping + normalization
# -----------------------------------------------------------------------------

@test("simple paragraph extraction")
def _():
    html = "<p>Hello world.</p><p>Second paragraph.</p>"
    txt = extract_plain_text_from_html(html)
    assert "Hello world." in txt
    assert "Second paragraph." in txt
    assert "<p>" not in txt and "</p>" not in txt


@test("headings preserved as plain text")
def _():
    html = "<h1>Big Title</h1><h2>Sub Heading</h2><p>Body.</p>"
    txt = extract_plain_text_from_html(html)
    assert "Big Title" in txt
    assert "Sub Heading" in txt
    assert "Body." in txt
    assert "<h1>" not in txt


@test("script and style tags dropped entirely")
def _():
    html = '<p>Visible.</p><script>alert("bad")</script><style>.x{color:red}</style><p>Still visible.</p>'
    txt = extract_plain_text_from_html(html)
    assert "Visible." in txt
    assert "Still visible." in txt
    assert "alert" not in txt
    assert "color:red" not in txt
    assert "bad" not in txt


@test("nested elementor-style divs flattened")
def _():
    html = """
    <div class="elementor-section"><div class="elementor-column">
      <div class="elementor-widget-wrap">
        <div class="elementor-widget">
          <p>Core content inside 4-deep nesting.</p>
        </div>
      </div>
    </div></div>
    """
    txt = extract_plain_text_from_html(html)
    assert "Core content inside 4-deep nesting." in txt
    assert "elementor" not in txt.lower()


@test("images replaced with alt text marker")
def _():
    html = '<p>See this: <img src="x.jpg" alt="Diagram of egg health factors"/> in context.</p>'
    txt = extract_plain_text_from_html(html)
    assert "Diagram of egg health factors" in txt
    # Raw img src URL should NOT appear
    assert "x.jpg" not in txt


@test("image without alt text is silently dropped")
def _():
    html = '<p>Before.</p><img src="x.jpg"/><p>After.</p>'
    txt = extract_plain_text_from_html(html)
    assert "Before." in txt
    assert "After." in txt
    assert "x.jpg" not in txt


@test("wordpress shortcodes stripped")
def _():
    html = "<p>Before.</p>[caption id=\"a\" align=\"alignleft\"]A photo[/caption]<p>[su_quote]Quoted text[/su_quote]After.</p>"
    txt = extract_plain_text_from_html(html)
    assert "Before." in txt
    assert "After." in txt
    assert "A photo" in txt  # content inside shortcodes is kept
    assert "Quoted text" in txt
    # Shortcode brackets themselves stripped
    assert "[caption" not in txt
    assert "[/caption]" not in txt
    assert "[su_quote]" not in txt
    assert "[/su_quote]" not in txt


@test("html entities decoded")
def _():
    html = "<p>Don&#8217;t use &amp; or &lt;brackets&gt; raw.</p>"
    txt = extract_plain_text_from_html(html)
    assert "Don\u2019t use & or <brackets> raw." in txt


@test("whitespace normalized (no multi-blank-line runs)")
def _():
    html = "<p>A.</p>\n\n\n\n\n<p>B.</p>\n\n\n\n\n<p>C.</p>"
    txt = extract_plain_text_from_html(html)
    # Allow paragraph breaks but no >2 consecutive newlines
    assert "\n\n\n" not in txt


@test("empty content returns empty string")
def _():
    assert extract_plain_text_from_html("") == ""
    assert extract_plain_text_from_html("<p></p>").strip() == ""
    assert extract_plain_text_from_html("<div>   </div>").strip() == ""


@test("iframes dropped (embedded video/audio not counted as content)")
def _():
    html = '<p>Before.</p><iframe src="https://youtube.com/embed/abc"></iframe><p>After.</p>'
    txt = extract_plain_text_from_html(html)
    assert "Before." in txt
    assert "After." in txt
    assert "youtube.com" not in txt
    assert "iframe" not in txt.lower()


@test("comments dropped")
def _():
    html = "<p>Visible.</p><!-- editor note: reword this --><p>Also visible.</p>"
    txt = extract_plain_text_from_html(html)
    assert "Visible." in txt
    assert "Also visible." in txt
    assert "editor note" not in txt


@test("list items preserved")
def _():
    html = "<ul><li>Alpha</li><li>Beta</li><li>Gamma</li></ul>"
    txt = extract_plain_text_from_html(html)
    for item in ["Alpha", "Beta", "Gamma"]:
        assert item in txt


@test("blockquote and emphasis flattened")
def _():
    html = "<blockquote><p>Quote body.</p></blockquote><p>Regular <em>emphasis</em> and <strong>strong</strong>.</p>"
    txt = extract_plain_text_from_html(html)
    assert "Quote body." in txt
    assert "emphasis" in txt
    assert "strong" in txt


# -----------------------------------------------------------------------------
# 2. build_blog_chunk_id — stable ID generation
# -----------------------------------------------------------------------------

@test("chunk ID shape matches wp:host:post_id:index")
def _():
    cid = build_blog_chunk_id("drnashatlatib.com", 18885, 0)
    assert cid == "wp:drnashatlatib.com:18885:0000"


@test("chunk IDs idempotent across calls")
def _():
    a = build_blog_chunk_id("drnashatlatib.com", 18885, 3)
    b = build_blog_chunk_id("drnashatlatib.com", 18885, 3)
    assert a == b


@test("chunk IDs stable for different chunk indices")
def _():
    c0 = build_blog_chunk_id("drnashatlatib.com", 18885, 0)
    c1 = build_blog_chunk_id("drnashatlatib.com", 18885, 1)
    assert c0 != c1
    assert c0.endswith(":0000")
    assert c1.endswith(":0001")


# -----------------------------------------------------------------------------
# 3. post_to_file_record — WP post → file_record for metadata builder
# -----------------------------------------------------------------------------

@test("post_to_file_record extracts core fields")
def _():
    post = {
        "id": 18885,
        "slug": "indoor-air-pollution-and-fertility",
        "date": "2025-06-18T08:30:43",
        "modified": "2025-07-02T09:15:28",
        "link": "https://drnashatlatib.com/fertility/indoor-air-pollution-and-fertility/",
        "title": {"rendered": "<span>Indoor Air Pollution</span> and Fertility"},
        "content": {"rendered": "<p>Body.</p>"},
        "categories": [12],
        "tags": [],
        "author": 1,
    }
    rec = post_to_file_record(post)
    assert rec["id"] == "18885"
    assert rec["name"] == "indoor-air-pollution-and-fertility"
    assert rec["mime_type"] == "text/html"
    assert rec["modified_time"] == "2025-07-02T09:15:28"
    assert rec["web_view_link"] == "https://drnashatlatib.com/fertility/indoor-air-pollution-and-fertility/"
    # md5 is a deterministic hash of rendered HTML, non-empty
    assert rec["md5_checksum"] and len(rec["md5_checksum"]) == 32


@test("post title HTML stripped for display_source")
def _():
    post = {
        "id": 18885,
        "slug": "x",
        "date": "2025-06-18T08:30:43",
        "modified": "2025-07-02T09:15:28",
        "link": "https://drnashatlatib.com/fertility/x/",
        "title": {"rendered": '<span style="font-weight: 700;">Indoor Air Pollution </span> and Fertility'},
        "content": {"rendered": "<p>Body.</p>"},
        "categories": [],
        "tags": [],
        "author": 1,
    }
    rec = post_to_file_record(post)
    assert rec["display_title"] == "Indoor Air Pollution and Fertility"


# -----------------------------------------------------------------------------
# 4. build_blog_metadata — full chunk metadata matches s19 contract
# -----------------------------------------------------------------------------

@test("metadata includes required provenance + display fields")
def _():
    post = {
        "id": 18885,
        "slug": "indoor-air-pollution",
        "date": "2025-06-18T08:30:43",
        "modified": "2025-07-02T09:15:28",
        "link": "https://drnashatlatib.com/fertility/indoor-air-pollution/",
        "title": {"rendered": "Indoor Air Pollution"},
        "content": {"rendered": "<p>Body.</p>"},
        "categories": [12],
        "tags": [34, 56],
        "author": 1,
    }
    chunk = {
        "text": "Body text chunk.",
        "word_count": 3,
        "chunk_index": 0,
        "name_replacements": 0,
        "display_locator": "",
        "display_timestamp": "",
    }
    meta = build_blog_metadata(
        chunk=chunk,
        post=post,
        library="rf_published_content",
        run_id="test-run-id-123",
        ingest_ts="2026-04-17T20:00:00Z",
        content_hash="a" * 64,
        category_names={12: "Fertility"},
        tag_names={34: "air quality", 56: "environment"},
        author_names={1: "Dr. Nashat Latib"},
    )
    # Provenance
    assert meta["source_pipeline"] == SOURCE_PIPELINE
    assert meta["source_pipeline"] == "blog_loader"
    assert meta["source_collection"] == "rf_published_content"
    assert meta["library_name"] == "rf_published_content"
    # s19 backfill fields
    assert meta["extraction_method"] == EXTRACTION_METHOD == "wp_rest"
    assert meta["content_hash"] == "a" * 64
    assert meta["source_file_md5"]  # non-empty
    # v3 category convention
    assert meta["v3_category"] == V3_CATEGORY == "wp_post"
    assert meta["v3_extraction_method"] == "wp_rest"
    # Display fields
    assert meta["display_source"] == "Indoor Air Pollution"
    assert meta["display_date"] == "2025-06-18T08:30:43"
    # WP-specific
    assert meta["wp_post_id"] == 18885
    assert meta["wp_slug"] == "indoor-air-pollution"
    assert meta["wp_canonical_url"] == "https://drnashatlatib.com/fertility/indoor-air-pollution/"
    assert meta["wp_author"] == "Dr. Nashat Latib"
    # Taxonomies resolved
    assert "Fertility" in meta["wp_categories"]
    assert "air quality" in meta["wp_tags"]
    assert "environment" in meta["wp_tags"]
    # Run identity
    assert meta["ingest_run_id"] == "test-run-id-123"
    assert meta["ingest_timestamp_utc"] == "2026-04-17T20:00:00Z"


@test("metadata handles empty taxonomies gracefully")
def _():
    post = {
        "id": 99999,
        "slug": "minimal",
        "date": "2025-01-01T00:00:00",
        "modified": "2025-01-01T00:00:00",
        "link": "https://drnashatlatib.com/minimal/",
        "title": {"rendered": "Minimal"},
        "content": {"rendered": "<p>X.</p>"},
        "categories": [],
        "tags": [],
        "author": 1,
    }
    chunk = {
        "text": "X.",
        "word_count": 1,
        "chunk_index": 0,
        "name_replacements": 0,
        "display_locator": "",
        "display_timestamp": "",
    }
    meta = build_blog_metadata(
        chunk=chunk, post=post,
        library="rf_published_content",
        run_id="r", ingest_ts="t", content_hash="h" * 64,
        category_names={}, tag_names={}, author_names={},
    )
    assert meta["wp_categories"] == ""
    assert meta["wp_tags"] == ""
    # author unknown resolves to empty string (not crash)
    assert meta["wp_author"] == ""


# -----------------------------------------------------------------------------
# 5. Content-hash determinism
# -----------------------------------------------------------------------------

@test("identical HTML produces identical md5 (stage-1 dedup input)")
def _():
    post1 = {"id": 1, "slug": "x", "date": "", "modified": "", "link": "", "title": {"rendered": ""}, "content": {"rendered": "<p>same body</p>"}, "categories": [], "tags": [], "author": 0}
    post2 = {"id": 2, "slug": "y", "date": "", "modified": "", "link": "", "title": {"rendered": ""}, "content": {"rendered": "<p>same body</p>"}, "categories": [], "tags": [], "author": 0}
    rec1 = post_to_file_record(post1)
    rec2 = post_to_file_record(post2)
    assert rec1["md5_checksum"] == rec2["md5_checksum"]


@test("different HTML produces different md5")
def _():
    post1 = {"id": 1, "slug": "x", "date": "", "modified": "", "link": "", "title": {"rendered": ""}, "content": {"rendered": "<p>first</p>"}, "categories": [], "tags": [], "author": 0}
    post2 = {"id": 2, "slug": "y", "date": "", "modified": "", "link": "", "title": {"rendered": ""}, "content": {"rendered": "<p>second</p>"}, "categories": [], "tags": [], "author": 0}
    rec1 = post_to_file_record(post1)
    rec2 = post_to_file_record(post2)
    assert rec1["md5_checksum"] != rec2["md5_checksum"]


# -----------------------------------------------------------------------------
# Summary (last-line convention: "  N/M passing, K failing")
# -----------------------------------------------------------------------------

def main() -> int:
    total = len(_RESULTS)
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    failed = total - passed
    for name, ok, reason in _RESULTS:
        marker = "✓" if ok else "✗"
        print(f"  {marker} {name}" + (f"  — {reason}" if not ok else ""))
    print()
    print(f"  {passed}/{total} passing, {failed} failing")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
