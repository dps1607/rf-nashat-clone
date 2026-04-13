# RF Nashat RAG — Backlog (deferred work)

Deferred items with enough detail to resume cold. Pulled into context only when picked up.

---

## NEW — added session 7 (2026-04-13)

### ADR_002 file-record backfill plan (dedicated planning session)
**Priority:** Medium. Not blocking A4M ingestion (session 7 decided Plan 2 proceeds via Option B — decoupled from this work). Becomes a surprise if deferred indefinitely.

**Scope:** Design and plan the backfill pass that creates `rf_library_index` file records for the existing historical corpora (coaching transcripts post-Phase-1, A4M once ingested, any existing `rf_reference_library` content that survives the drop-and-re-ingest decision). Open questions include: sha256 content hashes for files we may no longer have direct access to, Drive file ID reconstruction for files ingested before Drive IDs were tracked, coordination with Phase 1's filename-based `source_id` convention so the join works retroactively.

**Dependency:** Phase 1 structural backfill (Plan 2) should be complete before this runs so the `source_id` values on chunks are stable. No other dependencies.

---

### BUILD_GUIDE §3G + §7 amendment session (elevated priority)
**Priority:** High for documentation consistency; not blocking execution.

**Scope:** Revise `VECTOR_DB_BUILD_GUIDE.md` to:
- Add §3G `Reference Library Content (Non-Client-Linked)` — flagged in session 4 and session 6, still deferred
- Revise §7 `Vector DB Entry Schema` to reference ADR_006 as authoritative. The sketch in §7 is now superseded by ADR_006's locked schema; a new-session Claude reading BUILD_GUIDE without the ADRs gets a wrong picture of the chunk contract.

**Why elevated:** BUILD_GUIDE is the project's canonical doc. Every drift day between it and the ADRs increases the chance a future session makes a decision against the stale sketch. Target closure within 2-3 sessions.

**Dependency:** None. Pure documentation work.

---

### 584 pre-ADR_006 A4M chunks in `rf_reference_library` — drop-and-re-ingest
**Priority:** Medium. Blocks the first "real" A4M ingestion into `rf_reference_library`.

**Decision (Claude, session 7, tactical):** Drop-and-re-ingest using Plan 1's migration output as the source of truth, rather than backfill-in-place. Rationale captured in session 7 HANDOVER entry §6 of Strategic Concerns. Reversible: pre-drop backup + the 353-chunk JSON stays on disk as source material.

**Verification step before drop (session 8 step 3):** Read-only inventory of the 584 legacy chunks. Sample metadata shape. Enumerate unique `source_file` values. Total token count. Compare against the 353 merged JSON. If the 584 covers source files the 353 doesn't, or has substantive text the JSON is missing, PAUSE and ask Dan. Capture output in `docs/A4M_LEGACY_CHUNKS_INVENTORY.md`.

**Execution (not session 8):** Subsequent session performs the drop (with backup + approval gates) and the first A4M ingestion into `rf_reference_library` from `data/a4m_transcript_chunks_adr006.json` (Plan 1 output).

---

### Railway sync cadence — strategic decision for Dan
**Priority:** Strategic, to decide in the next 2-3 sessions.

**Context:** Local ↔ Railway drift has accumulated since 2026-04-10 and is still growing. Deferred sync items now include: the RFID wipe on coaching chunks (from 04-10), Phase 1 structural backfill (upcoming), Phase 2 marker detection (upcoming), the ADR_006-conforming A4M corpus (upcoming), the 584 legacy A4M chunks (to be dropped and re-ingested), and eventually `rf_published_content`. Each deferred item increases the eventual atomic sync's size and risk.

**Claude's lean:** Set a mid-build sync target — "everything on local that's done by session N gets shipped to Railway in session N+1" — to avoid a single enormous end-of-build sync. Specifically, a reasonable first cut would be: after Phase 1 + A4M ingestion land, do one atomic sync that ships the Phase-1-compliant coaching collection + the newly-built `rf_reference_library`. Phase 2 and `rf_published_content` become the next sync cycle.

**Dan to decide:** (a) mid-build sync cadence now, or (b) defer until all four content collections are built and do one end-of-build sync.

---

### `markers_discussed` casing clarification in ADR_006 §2
**Priority:** Low. Cosmetic doc inconsistency.

**Scope:** ADR_006 §2 has an illustrative example `"|AMH|FSH|TSH|"` (uppercase) but the canonical flag-naming rule in §2a is lowercase (`marker_amh`, etc.). Session 7 locked the display string as lowercase (mechanically derived from flag names) for consistency across all loaders. ADR_006 §2's example should be updated to `"|amh|fsh|tsh|"` to match the rule.

**Not a blocker:** no code depends on the example. Pure doc cleanup, appropriate for the next ADR_006 amendment pass (whenever that happens).

---

## Zoom coaching video pipeline (designed, not built)
**Goal:** ingest live coaching calls into a new `rf_coaching_episodes` collection for the internal coaching agent.

**Three parallel streams per call:**
1. **Diarized transcript** — speakers separated, timestamped.
2. **Visual stream** — Gemini 2.5 Flash scene-change detection + screen classification (BBT chart / lab panel / supplement label / chart-unrelated). Frame extraction at scene boundaries + OCR on extracted frames.
3. **Artifact linkage** — OCR output linked back to transcript timestamps.

**Chunk unit:** "interaction episode" = one clinical topic discussed continuously. Metadata per chunk: `qpt_tags`, `scene_type`, `visual_artifact_id`, `client_rfid`, `timestamp_start`, `timestamp_end`.

**Client ID:** hybrid — transcript content + Zoom tile labels. Haiku resolves to RFID.

**Cost estimate:** ~$500 for 500 hours of footage.

**Execution rule:** pilot one call end-to-end before any batch run.

**Downstream dependency (added session 7):** Coaching-chunk re-tagging (reconstructing `client_id` on the 9,224 historical chunks wiped on 2026-04-10) is downstream of this pipeline. Per the 2026 disambiguation decision in DECISIONS.md, re-tagging should use Zoom participant labels + scene-change data, not pattern matching. This means the historical coaching chunks will carry `client_id: null` until this pipeline exists and a subsequent re-tagging pass runs.

---

## A4M reference library ingestion (next up after folder walk verified)
A4M fertility course materials: slides + transcriptions. Ingest into `rf_reference_library`. Use local Mac sync path, not cross-account Drive. Blocked only on folder walk manifest verification.

**Session 7 status update:** Transcripts are chunked and merged (353 chunks in `data/a4m_transcript_chunks_merged.json`) but NOT yet ADR_006-conforming. Session 8 produces the ADR_006-conforming version at `data/a4m_transcript_chunks_adr006.json` via Plan 1's migration script. First actual Chroma write to `rf_reference_library` (with the 584-legacy-chunk drop) is a subsequent session after session 8. Slides loader is still unwritten.

---

## rf_published_content collection
Blogs + IG posts. Build after A4M reference library. Feeds public sales agent.

**Session 7 note:** Must conform to ADR_006 chunk reference contract. Uses `published_post` and `ig_post` entry types per ADR_006 §3. All 48 marker flags populated via regex at load time per ADR_006 §8. Shares `ingester/marker_detection.py` with all other loaders.

---

## Admin + deployment follow-ups
- Rotate admin password (deferred from Phase 2).
- Add Dr. Nashat as second admin user via `add_user` CLI.
- Railway deployment hardening (Phase 3).
- End-user accounts + conversation persistence (Phase 4).

---

## Lab correlation — Option B
Pending third-party lab work completion. Will correlate the 54-client before/after dataset against coaching themes from the RAG.

---

## Embedding upgrade — Option A
Deferred until all content is ingested. Re-embed everything once at the end rather than mid-stream.

---

## Master Nashat feature spec
Flagged as highest-leverage next strategic doc. Underpins patent, AI training, architecture, clinic pitch deck. Not started.

---

## Reddit marketing companion app
Python script monitors fertility subreddits. AI-drafts responses in Dr. Nashat's voice. Emails draft to VA at `partnerships@reimagined-health.com` for manual posting. SOP, response templates, and classification prompts are ready to build. Not started.

---

## Gut health × fertility lead magnet ebook (FKSP audience)
Outline complete. Dual-archetype framework: Strategist / Science-Seeker. Uses 4R Formula. Hybrid workflow agreed: Gemini for material extraction, Claude for persuasion writing.

---

## 30-article Nashat content launch plan (Track C)
Not started.

---

## App screen recording backlog (Gemini `run_hq.py` pipeline)
Script at `App/Flo Screen Recording/March 2025 Screenrecordings/pipeline/run_hq.py`. Model `gemini-2.5-flash`. Resumable.
- Flo AI assistant / community / symptom checker flows
- Natural Cycles (~15–20 min)
- Clue (~10–15 min)
None yet processed.

---

## Patent strategy, technical architecture doc, clinic pilot deck
Strategic docs, not started.
