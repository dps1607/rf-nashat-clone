# NEXT_SESSION_PROMPT — Evaluate ADR_005 against VECTOR_DB_BUILD_GUIDE

**Purpose:** ADR_005 (static libraries) was drafted in session 4 (2026-04-12) without the author having read `VECTOR_DB_BUILD_GUIDE.md`. The guide is the canonical source-of-truth for the entire RAG/Chroma build — project scope, unified ID system, data source map, cross-source correlation requirements. ADR_005 needs to be checked against it before any further work builds on it.

**Hard rules (carried forward, never violated):**
- No ChromaDB writes
- No git push, no git commit, no git add — Dan reviews everything before any git operation
- No Railway deployments
- No deletions without explicit Dan approval
- Never reference Dr. Christina in any output
- Public agent never touches `rf_coaching_transcripts`
- Credentials are ephemeral — never store API keys, tokens, or passwords in files or memory
- `create_file` writes to Claude's sandbox, not the Mac. Use `Desktop Commander:write_file` (chunked, ≤30 lines per call) or `Filesystem:edit_file` for anything that needs to land in the repo.

## Available tools

Load via `tool_search` at the start: `Filesystem:read_text_file`, `Filesystem:edit_file`, `Filesystem:list_directory`, `Desktop Commander:write_file`, `Desktop Commander:edit_block`. **Do NOT use `create_file`** — it writes to Claude's sandbox, not the Mac.

## Read in this exact order

1. `docs/REPO_MAP.md` — orient. Note that the BUILD_GUIDE is now listed under parent-dir docs.
2. `docs/HANDOVER.md` — top entry only (session 4 / 2026-04-12 ADR_005 drafted). Do not re-derive ADR_005's 7 decisions; the task is to *evaluate* them, not regenerate them.
3. **`/Users/danielsmith/Claude - RF 2.0/VECTOR_DB_BUILD_GUIDE.md`** — read in full. This is the load-bearing doc for this session. It is OUTSIDE the repo at the parent project level.
4. `ADR_005_static_libraries.md` (repo root) — the ADR being evaluated.
5. `docs/ARCHITECTURE.md` — current schema + collection definitions; note where it diverges from or under-specifies what the BUILD_GUIDE assumes.
6. `ADR_002_continuous_diff_and_registry.md` — only the parts about the registry contract and `rf_library_index` records. ADR_005 makes a forward-compat claim about an `origin` field on those records; verify that claim against ADR_002 and against whatever the BUILD_GUIDE says about cross-source ID/correlation requirements.

**Skip unless a question forces you to read them:** ADR_001, ADR_003, ADR_004, the folder-selection UI plan, the Phase D specs, BACKLOG.md, INCIDENTS.md, all `HANDOVER_*` files at repo root.

## The task

Evaluate whether ADR_005 is consistent with `VECTOR_DB_BUILD_GUIDE.md`. The 7 decisions in ADR_005 were locked in discussion before the BUILD_GUIDE was re-read, so this is a real (not ceremonial) review. Possible outcomes range from "consistent, no changes needed" to "ADR_005 must be revised" to "ADR_005 must be withdrawn and replaced." Do NOT assume any particular outcome.

### Specific questions to answer (in this order)

1. **Unified ID system compatibility.** The BUILD_GUIDE defines a hierarchical ID scheme: `RF-XXXX` (client) → `RF-XXXX-T1` (test event) → `RF-XXXX-T1-AMH` (result). ADR_005's "shared chunk reference contract" is mentioned but its field list is deferred to a later ADR. Does ADR_005 need to explicitly require that static-library chunks carry compatible ID metadata where applicable (e.g., A4M course chunks won't have an `RF-XXXX`, but the contract still has to leave room for IDs on chunks that DO reference clients)? Or is the deferral to "next ADR / ARCHITECTURE.md" still the right call?

2. **Cross-source correlation.** The BUILD_GUIDE's core value claim is that coaching transcripts reference real lab values, real BBT patterns, real outcomes — and the vector DB must preserve these correlations. Does ADR_005 say anything (or fail to say anything) that would break, weaken, or constrain this correlation requirement? Static libraries (A4M course material) don't reference specific clients, so on the surface no — but check whether ADR_005's "different door, same destination" framing has any side-effects on the metadata contract that the correlation model depends on.

3. **Data source map alignment.** The BUILD_GUIDE's Section 3 (Data Source Map) enumerates where data lives. Does it list A4M course materials? If yes, what category does it put them in, and does that category match ADR_005's "static library" framing? If no, that's a gap in the BUILD_GUIDE that ADR_005 fills — flag it as a recommended BUILD_GUIDE addendum.

4. **Naming and discriminator field.** ADR_005 §7 locks the term "static libraries" and the discriminator field name `origin`. Does the BUILD_GUIDE use any conflicting terminology (e.g., "reference materials," "external sources," "course content") that would create vocabulary collisions? If yes, decide which name wins and update the loser.

5. **Registry forward-compat.** ADR_005 §5 says static-library loaders write registry entries via a separate code path with `origin: "static_library"`. The BUILD_GUIDE may or may not describe a registry at all (it predates ADR_002). If the BUILD_GUIDE describes a different storage/index model, reconcile.

6. **Anything else.** If the BUILD_GUIDE assumes something about ingestion paths, schema, or collections that ADR_005 contradicts or omits, flag it.

## Deliverable

Produce a written evaluation in chat (NOT a new file yet) with this structure:

- **Verdict:** one of `consistent` / `consistent with minor additions` / `needs revision` / `withdraw and replace`.
- **Per-question findings:** answer each of the 6 questions above. For each, cite the specific BUILD_GUIDE section (by section number or heading) and the specific ADR_005 decision number.
- **Recommended actions:** a numbered list of concrete edits — to ADR_005, to ARCHITECTURE.md, to the BUILD_GUIDE, or to REPO_MAP — with the proposed text for each. Do NOT make any of these edits in this session. Dan reviews the evaluation first, then approves edits one by one.
- **Open questions for Dan:** anything that requires Dan's call before edits can proceed.

## Hard stops

- Do not edit ADR_005 in this session.
- Do not edit `VECTOR_DB_BUILD_GUIDE.md` in this session.
- Do not write a new ADR (ADR_006) in this session.
- Do not run any git command.
- Do not touch ChromaDB.
- If the evaluation reveals that ADR_005 needs to be withdrawn, STOP and ask Dan how to proceed (rewrite vs. supersede vs. discard) — do not make that call unilaterally.

## Context discipline

The author of ADR_005 (session 4) made one explicit context tradeoff: skipped ADR_001/004 and the folder-selection plan to save budget, on the rationale that the decision was about what static libraries are NOT (Drive-walked, UI-managed) rather than what they are. That was defensible at the time. The same tradeoff cannot be made in THIS session — the BUILD_GUIDE is the load-bearing read and must be done in full. Budget your reading accordingly: BUILD_GUIDE first and thoroughly, then ADR_005, then ARCHITECTURE.md, then ADR_002 only as needed. Other docs are off-budget unless a specific question forces them in.

## Why this review exists

In session 4, the author wrote ADR_005 from the HANDOVER's locked decisions without re-reading the project's canonical build guide. Dan caught this in session 5 and flagged the BUILD_GUIDE as critical. This session exists to close that loop before any further work — A4M ingestion, Unit 14 merge, the chunk reference contract — gets built on top of an ADR that may not align with the source-of-truth document.
