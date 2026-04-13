# REPO_MAP — canonical doc locations

> **Orientation note (added session 9):** Before reading any other doc in this map, read **`docs/STATE_OF_PLAY.md`** first. It is the authoritative current-state document as of 2026-04-13 (session 9 stabilization). It supersedes parts of this REPO_MAP, parts of `docs/ARCHITECTURE.md`, and the session 7 entry of `docs/HANDOVER.md`. Specifically: any claim in this map about local Chroma being primary, about the 584 reference-library chunks being "mystery" or "to be dropped," about Plans 1/2/3 from session 7, or about ADR_006's 48 marker boolean flags being on the critical path — those claims are **superseded**. STATE_OF_PLAY.md tells the truth about all of them.

**Purpose:** Single source of truth for where docs live. Every session prompt should tell Claude to read this file FIRST, then the task-relevant docs it flags below. Paths are relative to repo root `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`.

**Rule:** If you move or rename a doc, update this file in the same commit. No exceptions.

---

## ADRs — architectural decisions (at repo root, NOT in docs/)
Read before changing ingestion, retrieval, or collection schemas.

- `ADR_001_drive_ingestion_scope.md` — what Drive ingestion covers and excludes
- `ADR_002_continuous_diff_and_registry.md` — folder-walk manifest + registry model (applies to Drive-sourced ingestion). **Amended 2026-04-12** — see Addendum section at end of file for `origin` field and non-Drive file record support.
- `ADR_003_canva_dedup.md` — Canva export dedup rules
- `ADR_004_folder_selection_ui.md` — folder-selection UI design
- `ADR_005_static_libraries.md` — static libraries (non-Drive sources for `rf_reference_library` and future curated collections); UI is Drive-only by design. Amended 2026-04-12 after BUILD_GUIDE review.
- `ADR_006_chunk_reference_contract.md` — universal chunk metadata schema for every content collection. 48 marker boolean flags (hybrid encoding for exact filtering), 25 QPT flags (forward-compat), phased backfill plan for existing 9,224 coaching chunks. Extends BUILD_GUIDE §7's `entry_type` enum, relaxes `client_id` to optional. Load-bearing for any loader work. Amended same-day (2026-04-12) to replace pipe-delimited marker encoding with boolean flags after recognizing substring-collision risk.

## Specs (at repo root)
- `PHASE_D_PRIME_SPEC.md` — Phase D (pre) spec
- `PHASE_D_POST_SPEC.md` — Phase D (post) spec

## Operational state
- `docs/ARCHITECTURE.md` — metadata schema pointer, collections, retrieval guardrails (Christina/Kelsey/Erica exclusions, HIPAA boundary). Updated 2026-04-12 to point at ADR_006 for chunk schema, including the hybrid boolean/delimited encoding rules.
- `docs/BACKLOG.md` — what's blocked and why. Updated 2026-04-13 (session 7) with: ADR_002 file-record backfill plan, BUILD_GUIDE §3G/§7 amendment, 584 legacy A4M chunks drop-and-re-ingest, Railway sync cadence strategic decision, `markers_discussed` casing cleanup.
- `docs/DECISIONS.md` — resolved decisions (incl. service-account path at ~/.config/gcloud/rf-service-account.json)
- `docs/HANDOVER.md` — rolling handover log (most recent entries at top). Session 7 entry (2026-04-13) contains the full text of the three approved backfill plans (A4M migration, coaching Phase 1 structural, coaching Phase 2 marker detection) and the tech-lead mandate established this session.
- `docs/NEXT_SESSION_PROMPT.md` — the bootstrap prompt for the next session. Refreshed each session-end.
- `docs/STATE_OF_PLAY.md` — **created session 9 (2026-04-13)**. Authoritative current-state document. Read FIRST in any new session before reading any other doc in this map. Supersedes parts of REPO_MAP, ARCHITECTURE, and the session 7 HANDOVER entry. Captures: Railway-canonical truth, full breakdown of the 584 `rf_reference_library` chunks (NOT stale, NOT droppable), the actual minimum metadata-consistency gap (5 display fields against `rag_server/app.py:format_context()`, not 48 marker booleans), the parallel A4M ingestion lineages story, and the coaching collection word-count distribution as observation-only.
- `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` — **created session 8**. Single source of truth for the current metadata shape of `rf_coaching_transcripts` chunks in local Chroma (post-2026-04-10 RFID wipe). Generated via read-only peek at 5 sample chunks. Required input for Plan 2 (Phase 1 structural backfill). Does not yet exist in session 7.
- `docs/A4M_LEGACY_CHUNKS_INVENTORY.md` — **created session 8**. Read-only inventory of the 584 pre-ADR_006 A4M chunks in `rf_reference_library`. Verification step before the drop-and-re-ingest decision from session 7 is executed. Does not yet exist in session 7.

## Incident + task-specific handovers (at repo root)
- `INCIDENTS.md` — things that broke and how (scan before touching related subsystems)
- `HANDOVER_INTERNAL_EDUCATION_BUILD.md` — A4M / reference library build notes. Source of truth for the 2026-04-10 RFID wipe history on `rf_coaching_transcripts` and the local↔Railway drift that followed.
- `HANDOVER_RAG_SESSION.md` — general RAG session handover
- `HANDOVER_PROMPT.md` — master project handover (in `/Users/danielsmith/Claude - RF 2.0/`, NOT in repo)
- `VECTOR_DB_BUILD_GUIDE.md` — **canonical RAG/Chroma build guide and data architecture** (in `/Users/danielsmith/Claude - RF 2.0/`, NOT in repo). Source-of-truth for project scope, unified ID system (`RF-XXXX` / `RF-XXXX-T1` / `RF-XXXX-T1-AMH`), data source map, 44 lab markers (§5), and the cross-source correlation model that the vector DB must preserve. Read this BEFORE any architectural decision about ingestion, schema, collections, or retrieval — the ADRs and `docs/ARCHITECTURE.md` should be consistent with this guide, not the other way around. Dated April 3, 2026; predates the current ADR-numbered workflow. Where ADRs extend or diverge from it (notably ADR_005 for reference-library content and ADR_006 for the chunk schema), the ADRs document the divergence explicitly. §3G and §7 amendments are elevated-priority backlog items per session 7.

## Plans (in-flight, dated)
- `docs/plans/2026-04-11-folder-selection-ui.md`

---

## Code layout (ingestion-related) — locked session 7
All ingestion/backfill/loader code lives under the `ingester/` package at repo root. Layout:

- `ingester/marker_detection.py` — **canonical shared module**. 48 `MARKER_PATTERNS` regexes (one per ADR_006 §2a flag), `CANONICAL_FLAGS` list, `COLLISION_MARKERS` set, `detect_markers(text) -> dict[str, bool]` always returns all 48 keys, `detect_markers_hybrid(text, llm_client)` for coaching-content Phase 2 collision disambiguation. Every loader and backfill imports from here; drift is prohibited. Created in session 8 Plan 1 execution.
- `ingester/backfills/_common.py` — shared helpers for all backfill and migration passes: ADR_006 record validator (checks universal required fields, entry_type enum, 48 marker flags present as explicit booleans, client_id/linked_test_event_id explicit None on non-client types, chunk_id uniqueness, type_metadata_json is string or None), `build_chunk_id(library_name, entry_type, source_component, chunk_index) -> str`, `build_markers_discussed(flags) -> str | None` (lowercase bookend-delimited), `serialize_type_metadata(dict) -> str`. Created in session 8 Plan 1 execution.
- `ingester/backfills/migrate_a4m_to_adr006.py` — Plan 1 (session 8)
- `ingester/backfills/backfill_coaching_phase1_structural.py` — Plan 2 (session 8)
- `ingester/backfills/backfill_coaching_phase2_markers.py` — Plan 3 (deferred to a dedicated later session)
- `ingester/loaders/` — future real loaders (A4M slides, Drive-walk ingester, Zoom-episode loader). Not yet created.

**Chunk ID format (all libraries):** `{library_name}:{entry_type}:{source_component}:{chunk_index_zero_padded}`. Generated by `build_chunk_id()`. One format, every library, forever.

**`markers_discussed` display casing (all loaders):** lowercase, derived mechanically from flag names, bookend-delimited (`"|amh|fsh|tsh|"`). Generated by `build_markers_discussed()`. Never uppercase at storage time; presentation layer may uppercase if needed.

---

## Collections (ChromaDB)
- `rf_coaching_transcripts` — ACTIVE, 9,224 chunks, coaching client data (behind paywall, internal agent only). **Post-2026-04-10 RFID wipe:** all `client_rfids` and `client_names` fields cleared on the 3,041 previously-tagged chunks; local count is 9,224 total with 0 tagged. Railway production still has the pre-wipe version — deferred sync. Metadata backfill pending to bring chunks into ADR_006 compliance — phased: Phase 1 structural annotation (session 8 executes), Phase 2 marker detection (dedicated later session, Option C hybrid decided).
- `rf_reference_library` — in build, target for A4M course materials + clinical refs (public agent allowed). Loaded via static-library path (ADR_005); chunks must conform to ADR_006 including 48 marker flags populated by regex detection. **Contains 584 pre-ADR_006 A4M chunks** as of 2026-04-10 — scheduled for drop-and-re-ingest (session 7 decision, executed in a post-session-8 session after the verification inventory).
- `rf_published_content` — planned, blogs + IG posts (public agent allowed).
- `rf_coaching_episodes` — planned, Zoom video pipeline output.
- `rf_library_index` — planned, metadata-only registry (ADR_002 + 2026-04-12 addendum). File records + library records; single source of truth for "what content does the RAG have." Backfill for historical corpora has no written plan yet — added to BACKLOG session 7.

## Ingestion paths (taxonomy — locked 2026-04-12)
1. **Drive-walked content** (ADR_002) — folder-walk + manifest + diff + registry. File records have `origin: "drive_walk"`. Governed end-to-end by ADR_002 and surfaced via the folder-selection UI (ADR_004).
2. **Static libraries** (ADR_005) — one-shot CLI loaders for curated non-Drive content. File records have `origin: "static_library"`. Not surfaced in the folder-selection UI by design. A4M is the first instance.

Both paths write chunks conforming to ADR_006's chunk reference contract. All loaders must share the canonical `ingester/marker_detection.py` module for consistent marker flag population across sources. All backfills must use the shared `ingester/backfills/_common.py` validator — a non-compliant loader is non-compliant by definition.

## Hard guardrails (from ARCHITECTURE.md — never violate)
- Never reference Dr. Christina in any response
- Exclude Kelsey Poe and Erica from retrieval results
- Dr. Chris stays internal only (diarization label, not surfaced)
- Public agent must never access `rf_coaching_transcripts`
- Never store API keys / tokens / passwords in memory or files
- Static-library loaders must verify their source contains no client-identifying data before ingesting (Reference tier is public-agent-eligible by default — ADR_005)
- Marker flags must be written as explicit `false`, not omitted (missing Chroma metadata fields become `None` and cannot be filtered on — silently breaks retrieval)
- Dan runs all git operations. Claude never runs git push/commit/add — Claude suggests the commit, Dan executes.
- First-touch of any live Chroma collection requires a manual eyeball-diff gate with Dan before writing.

## Tech-lead mandate (session 7)
Claude holds tech-lead role on the RAG build. Makes tactical build decisions (script layout, mapping conventions, validator shape, detection method tradeoffs where cost is low). Brings to Dan: strategic tradeoffs, irreversible operations, money spend >$25, cross-domain decisions. Gate between tactical and strategic is the "can we fix this later?" test — reversible by migration script is tactical; reversible only by re-embedding/re-ingest/rollback is strategic. Safety discipline is unchanged — tech-lead authority does not skip gates. See session 7 HANDOVER entry for full text.

## Session bootstrap checklist
Every new session MUST:
1. Read `docs/REPO_MAP.md` (this file) first
2. Read `docs/NEXT_SESSION_PROMPT.md` for the specific task
3. Read `docs/HANDOVER.md` top entry for the authoritative task description (session 7+ handover entries contain full plans and decisions inline rather than in separate plan files)
4. State in its own words: the gate/decision question, which docs it will read, which it will skip, and why
5. NOT touch Chroma, git push, Railway, or deletions without explicit Dan confirmation
