"""
Context rendering for retrieved chunks
======================================

Produces the labeled context blocks that Sonnet sees during /chat. This is
the *rendering* layer — what the LLM reads — and is separate from the
*retrieval* layer in rag_server/app.py which returns full chunks (with all
metadata, including client identifiers for downstream systems).

Design principles (session 24, BACKLOG #18):

1. **Canonical display contract.** `chunk_to_display()` normalizes any chunk
   (regardless of pipeline: v3 PDF, v3 Google Doc, legacy A4M, coaching
   transcript) into a uniform dict of display fields. `format_context()`
   reads only these canonical fields — no per-pipeline branches in the
   rendering code.

2. **Graceful degradation.** Every display field returns "" when the
   underlying metadata is absent, "Unknown", "None", or whitespace-only.
   The renderer conditionally emits lines only when a field has real
   content. Never emits "Presenter: Unknown" or "Source: None".

3. **YAML-configurable visibility.** Per-collection `render` configs in
   the agent YAML control which display fields are surfaced to the LLM.
   Retrieved chunks are unchanged — only the prompt-context rendering is
   filtered.

4. **Hardcoded non-negotiables.** Client identifiers (client_rfids,
   client_names, call_fksp_id, call_file) are NEVER surfaced to the LLM
   regardless of YAML config. This is enforced in code, not config —
   there is no knob to flip by accident. Downstream systems continue to
   read these fields directly from chunk.metadata.

Collection naming conventions:
- rf_coaching_transcripts: real coaching sessions (9,224 chunks)
- rf_reference_library: A4M course + v3 Drive-sourced reference content
- rf_published_content: planned, Dr. Nashat's own writing (not yet built)
"""
from __future__ import annotations
from typing import Optional

from config.schema import RenderConfig


# ============================================================================
# DEFAULTS — used when agent YAML has no `render` block for a collection
# ============================================================================

# Conservative defaults per collection. Each preserves the spirit of the
# pre-session-24 format_context() behavior:
#   - coaching: source label + topics, everything else absorbed
#   - reference: full citation (source + speaker + locator + link) if
#     available; topics + date also surfaced
#   - published: source + topics + link + date (speaker is always Dr. Nashat,
#     redundant to cite)
_DEFAULT_RENDER: dict[str, RenderConfig] = {
    "rf_coaching_transcripts": RenderConfig(
        show_source_label=True,
        show_topics=True,
        show_speaker=False,
        show_locator=False,
        show_link=False,
        show_date=False,
    ),
    "rf_reference_library": RenderConfig(
        show_source_label=True,
        show_speaker=True,
        show_topics=True,
        show_locator=True,
        show_link=True,
        show_date=True,
    ),
    "rf_published_content": RenderConfig(
        show_source_label=True,
        show_speaker=False,
        show_topics=True,
        show_locator=False,
        show_link=True,
        show_date=True,
    ),
}


# Section headers per collection. What the LLM reads at the top of each
# collection's block in the assembled context.
_SECTION_HEADERS: dict[str, str] = {
    "rf_coaching_transcripts": "COACHING CONTEXT (from real coaching sessions):",
    "rf_reference_library": (
        "REFERENCE KNOWLEDGE "
        "(A4M Fertility Certification + clinical guides):"
    ),
    "rf_published_content": (
        "PUBLISHED CONTENT (Dr. Nashat's own writing/teaching):"
    ),
}


# Per-chunk label prefix inside each section (the "--- Reference N ---" line).
_ITEM_LABELS: dict[str, str] = {
    "rf_coaching_transcripts": "Coaching Exchange",
    "rf_reference_library": "Reference",
    "rf_published_content": "Published",
}


# Client-identifier metadata fields that are NEVER surfaced to the LLM prompt
# regardless of YAML config. Enforced in code for defense in depth. The
# fields remain fully available in chunk.metadata for downstream consumers
# (lab correlation, client tracking, analytics).
_PROTECTED_FIELDS: frozenset[str] = frozenset({
    "client_rfids",
    "client_names",
    "call_fksp_id",
    "call_file",
})


# ============================================================================
# HELPERS
# ============================================================================

def _clean(value) -> str:
    """Normalize a metadata value to a safe display string.

    Returns "" if the value is None, "Unknown", "None" (any case), or
    whitespace-only. This prevents "Presenter: Unknown" artifacts and
    ensures `if field:` checks in the renderer behave correctly.

    Non-string scalars (int, float, bool) are stringified.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in {"unknown", "none", ""}:
        return ""
    return s


def _resolve_source_label(meta: dict, collection: str) -> str:
    """Human-readable name for the source of this chunk.

    v3 Drive-sourced chunks expose source_file_name.
    Legacy A4M chunks expose module_number + module_topic.
    Coaching chunks have no per-chunk source label worth surfacing — the
    collection-level "COACHING CONTEXT" header already scopes them, and
    per-exchange labels would only surface session identifiers.
    """
    # v3 path: source_file_name is canonical
    name = _clean(meta.get("source_file_name"))
    if name:
        return name
    # Legacy A4M path: reconstruct from module metadata
    module_number = _clean(meta.get("module_number"))
    module_topic = _clean(meta.get("module_topic"))
    if module_number and module_topic:
        return f"A4M Module {module_number}: {module_topic}"
    if module_topic:
        return f"A4M: {module_topic}"
    # Coaching path: intentionally empty — the section header scopes it
    return ""


def _resolve_speaker(meta: dict, collection: str) -> str:
    """Presenter / author of the source, if known.

    v3 chunks use display_speaker (populated by handlers when identifiable).
    Legacy A4M uses speaker. Coaching absorbs per character rules — never
    surface a coach name even if the YAML knob says show_speaker=true.
    """
    if collection == "rf_coaching_transcripts":
        return ""  # absorbed by design; YAML knob cannot override
    return _clean(meta.get("display_speaker") or meta.get("speaker"))


def _resolve_topics(meta: dict, collection: str) -> str:
    """Topic tags for the chunk."""
    return _clean(meta.get("display_topics") or meta.get("topics"))


def _resolve_locator(meta: dict, collection: str) -> str:
    """Page/section reference (e.g. 'pp. 1-3', '§1')."""
    return _clean(meta.get("display_locator"))


def _resolve_link(meta: dict, collection: str) -> str:
    """Drive webViewLink for the source file."""
    return _clean(meta.get("source_web_view_link"))


def _resolve_date(meta: dict, collection: str) -> str:
    """Date reference. Coaching date is protected (timelines can identify)."""
    if collection == "rf_coaching_transcripts":
        return ""  # protected; even if YAML opts in, do not surface
    return _clean(meta.get("display_timestamp") or meta.get("display_date"))


# ============================================================================
# PUBLIC API
# ============================================================================

def chunk_to_display(
    chunk: dict,
    render_configs: Optional[dict[str, RenderConfig]] = None,
) -> dict:
    """Normalize one retrieved chunk into a uniform display dict.

    Args:
        chunk: A retrieved chunk of the shape returned by
            rag_server.app.retrieve_for_mode — requires "text", "metadata",
            and "source" keys. Distance is ignored.
        render_configs: Per-collection RenderConfig map from agent YAML.
            Missing entries fall back to _DEFAULT_RENDER. Missing map
            entirely → defaults used everywhere.

    Returns:
        dict with keys: collection, text, source_label, speaker, topics,
        locator, link, date, item_label. Every string field is either
        meaningful content or "". Protected fields (client identifiers)
        are never populated.

    The returned dict is for renderer consumption only. Downstream
    systems that need client identifiers, RFIDs, or call metadata MUST
    read chunk["metadata"] directly, not this dict.
    """
    collection = chunk.get("source", "")
    meta = chunk.get("metadata") or {}
    text = chunk.get("text", "")

    cfg = (render_configs or {}).get(collection)
    if cfg is None:
        cfg = _DEFAULT_RENDER.get(collection, RenderConfig())

    # Resolve each field if (a) metadata has something cleanable AND
    # (b) the render config permits surfacing it.
    source_label = (
        _resolve_source_label(meta, collection) if cfg.show_source_label else ""
    )
    speaker = _resolve_speaker(meta, collection) if cfg.show_speaker else ""
    topics = _resolve_topics(meta, collection) if cfg.show_topics else ""
    locator = _resolve_locator(meta, collection) if cfg.show_locator else ""
    link = _resolve_link(meta, collection) if cfg.show_link else ""
    date = _resolve_date(meta, collection) if cfg.show_date else ""

    return {
        "collection": collection,
        "text": text,
        "source_label": source_label,
        "speaker": speaker,
        "topics": topics,
        "locator": locator,
        "link": link,
        "date": date,
        "item_label": _ITEM_LABELS.get(collection, "Context"),
    }


def _render_one_chunk(display: dict, index: int) -> list[str]:
    """Render a single chunk's display dict into text lines.

    Skips lines for any field that is "". Always emits the "--- Label N ---"
    divider and the chunk text, even if every other field is empty.
    """
    lines: list[str] = []
    lines.append(f"--- {display['item_label']} {index} ---")

    # Source line: combine source_label + locator + date when any are set.
    # E.g. "Source: RH - Egg Health Guide.pdf — pp. 1-3 — 2024-05-03"
    citation_bits = []
    if display["source_label"]:
        citation_bits.append(display["source_label"])
    if display["locator"]:
        citation_bits.append(display["locator"])
    if display["date"]:
        citation_bits.append(display["date"])
    if citation_bits:
        lines.append("Source: " + " — ".join(citation_bits))

    # Separate lines for presenter, link, topics
    if display["speaker"]:
        lines.append(f"Presenter: {display['speaker']}")
    if display["link"]:
        lines.append(f"Link: {display['link']}")
    if display["topics"]:
        lines.append(f"Topics: {display['topics']}")

    lines.append(display["text"])
    lines.append("")
    return lines


def format_context(
    chunks: list[dict],
    render_configs: Optional[dict[str, RenderConfig]] = None,
) -> str:
    """Turn a list of retrieved chunks into a labeled prompt context block.

    Groups chunks by source collection, emits each group under its
    section header, renders each chunk via chunk_to_display() +
    _render_one_chunk().

    Empty chunks list → empty string. Chunks from unknown collections
    (not in _SECTION_HEADERS) are grouped under a generic "CONTEXT"
    header as a last-resort fallback — this shouldn't happen in
    normal operation but degrades gracefully rather than dropping
    data silently.

    Collections are emitted in a deterministic order: coaching first
    (most context-anchoring), then reference, then published, then
    any unknown collections.
    """
    if not chunks:
        return ""

    # Group chunks by source collection, preserving arrival order within
    # each group so the renderer output is deterministic given the same
    # retrieval result.
    by_source: dict[str, list[dict]] = {}
    for chunk in chunks:
        by_source.setdefault(chunk.get("source", ""), []).append(chunk)

    # Render order: canonical collections first, then alphabetically for
    # any unknown collections (shouldn't happen; belt-and-suspenders).
    known_order = [
        "rf_coaching_transcripts",
        "rf_reference_library",
        "rf_published_content",
    ]
    unknown = sorted(k for k in by_source if k not in known_order)
    render_order = [k for k in known_order if k in by_source] + unknown

    blocks: list[str] = []
    for collection in render_order:
        header = _SECTION_HEADERS.get(
            collection,
            f"CONTEXT ({collection}):",
        )
        blocks.append(header)
        blocks.append("")
        for i, chunk in enumerate(by_source[collection], 1):
            display = chunk_to_display(chunk, render_configs)
            blocks.extend(_render_one_chunk(display, i))

    return "\n".join(blocks)


# ============================================================================
# Module surface note
# ============================================================================
# Exported for external consumers:
#   - chunk_to_display(chunk, render_configs) -> dict
#   - format_context(chunks, render_configs) -> str
#
# The _PROTECTED_FIELDS constant is intentionally private. It documents which
# metadata fields will never be surfaced to the LLM prompt regardless of
# YAML knobs. If you find yourself wanting to "opt in" to surfacing a
# protected field, reconsider: the reason it's protected is that the
# retrieval guardrails forbid it, and the YAML knob that would flip it
# does not exist by design.
