# RF Nashat RAG — Backlog (deferred work)

Deferred items with enough detail to resume cold. Pulled into context only when picked up.

---

## NEW — added session 9 (2026-04-13, stabilization)

> **Note on the session 7 entries below:** All session 7 backlog items below were captured *before* the session 9 stabilization corrected the framing of the metadata work. Most session 7 items (Plan 1/2/3 execution, ADR_002 file-record backfill prerequisites, the 584-drop-and-re-ingest decision, BUILD_GUIDE §3G/§7 amendment, `markers_discussed` casing, Railway sync cadence as currently framed) are **superseded by `docs/STATE_OF_PLAY.md`**. They are not deleted because the *underlying ideas* may become valid later, but they should not drive next-session work without re-reading STATE_OF_PLAY first. Specifically:
>
> - **The 584-drop-and-re-ingest item below is REVERSED.** The 584 chunks are the live, well-built A4M reference library serving Dr. Nashat in production. They are not dropped under any circumstances.
> - **Plans 1, 2, 3 below are FROZEN.** The "Phase 1 structural backfill" and "Phase 2 marker detection" reference 48 marker boolean flags that no consumer in `rag_server/app.py` reads.
> - **The Railway sync cadence question below has a NEW DEFAULT.** Local is a development sandbox; Railway is canonical. The sync direction is local → Railway via tarball+bootstrap, on demand, when local has something worth shipping. There is no automatic sync. There is no large pending sync queue (because there is no large body of local-only changes to push).

### Coaching collection chunk-size observation (NOT a known problem, NOT a planned fix)
**Priority:** Observation only. No action without a real retrieval-quality trigger.

**Finding (session 9 verification, read-only against local Chroma).** The live 9,224-chunk `rf_coaching_transcripts` collection has the following word-count distribution:

- min: 30w, p10: 291w, **median: 564w**, p90: 652w, max: 2891w, mean: 573w
- 267 chunks below 100w
- 515 chunks at 100–249w
- 7,915 chunks at 250–999w (the bulk)
- 527 chunks at 1000w or larger

**This is the production state of the v3 LLM chunker output, full stop.** It is NOT a known problem. It is NOT a deferred fix. The earlier draft of this backlog item framed it as "the same small-chunk problem `merge_small_chunks.py` was built to fix" — that framing was wrong and is corrected here.

**Why the earlier framing was wrong, and why no hard floor should be applied to coaching content:**

1. **`merge_small_chunks.py` was built for one specific corpus at one specific time.** It applied a `FLOOR=250` post-process pass to A4M lecture transcripts where Haiku had over-fragmented monologue content. That number was tactical, not principled. It is not a generally-applicable rule.
2. **The v3 chunker's `<150w merge escape hatch` was also tactical.** It came from a prompt-engineering decision in `rag_pipeline_v3_llm.py` for coaching call Q&A. The number is not a quality threshold; it's a prompt parameter from one iteration. It should not be carried forward as a rule.
3. **Q&A in fertility coaching is typically long-form.** Dr. Nashat walking through a lab result, explaining a protocol, or answering a multi-part question produces responses that are naturally hundreds of words long. A short chunk is much more likely to be a clean topic transition (one speaker's brief acknowledgment, a question handoff, a coaching moment) than to be over-fragmented content. **Forcing a numeric floor risks merging chunks that should stay separate** because they happen to fall below an arbitrary threshold.
4. **The right rule is "whatever chunk size makes the chunk a coherent retrievable unit."** That's a per-chunk judgment, not a numeric threshold. The v3 chunker already makes that judgment via the LLM's topic-boundary detection. If specific chunks turn out to be bad, that's a per-chunk investigation, not a corpus-wide post-processing pass.

**The actual question to ask, if and only if a real trigger surfaces:** when retrieval quality on coaching content shows a specific failure mode (e.g., "this query returned a 30-word chunk that was meaningless out of context, and a more useful chunk existed adjacent to it"), investigate that specific chunk and its neighbors. If they should be merged, merge them. If they shouldn't, leave them. There is no global fix here. There is no `merge_small_chunks.py`-style pass for coaching content, ever, because the framing that produced that script does not apply to this corpus.

**Why this resolves the "session 14 / Q&A re-merge" memory:** there was never a coaching Q&A re-merge session, and there should not be one. The memory came from real signals — the v3 prompt rule about Q&A topic boundaries, and the A4M Module 14 rescue work — that got conflated in handover docs across low-context sessions. **A4M Module 14** required `merge_small_chunks.py` to recover usable chunks from an unusually fragmented source transcript. That fix was for A4M lecture content, applied pre-RAG, never written to Chroma. It does not generalize. The coaching collection is fine as-is.

**The honest backlog status here is "no action item."** The observation is captured in `docs/STATE_OF_PLAY.md` for future sessions that might wonder what those word-count numbers look like, but the thing future sessions should NOT do is "fix" the distribution by running a merge pass.

### Archive Lineage A artifacts to `data/_archive/`
**Priority:** Low. Pure cleanup.

**Scope:** Move `data/a4m_transcript_chunks_full.json`, `data/a4m_transcript_chunks_merged.json`, `data/a4m_transcript_chunks_pilot.json`, `ingest_a4m_transcripts.py`, and `merge_small_chunks.py` to `data/_archive/lineage_a_a4m_chunking_attempt/` (or similar). Add a README in that directory explaining what they are, why they exist, why they were never ingested, and why the 584-chunk Lineage B in `rf_reference_library` won. See `docs/STATE_OF_PLAY.md` "Two parallel A4M ingestion lineages" section for the full story.

**Why not delete outright:** they're useful as a reference for how the v3 chunking pipeline was adapted for non-Q&A content, in case that pattern is ever needed for a future loader. They also document a real (and non-trivial) piece of session work that should not be lost from history.

**When:** any small cleanup session, low priority. Do not block other work to do this.

### Optional: M3 transcript speaker backfill
**Priority:** Very low. Pure polish.

**Scope:** 18 transcript chunks in M3 (Fertility Assessment Male) of the A4M reference library have `speaker: "Unknown"` while the corresponding slide chunks in M3 likely have a named lecturer in slide 1 of the deck. A targeted backfill script could read the M3 slide chunks, extract the lecturer name, and update the 18 transcript chunks. Total touched: 18 chunks. M5 and M10 are case study panels with intentional ambiguity and should not be touched.

**Why low:** the impact is on citation rendering quality for one module out of 14. Small enough to leave for a polish pass once the UI thread is moving.

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
