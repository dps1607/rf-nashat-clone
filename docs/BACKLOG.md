# RF Nashat RAG — Backlog (deferred work)

Deferred items with enough detail to resume cold. Pulled into context only when picked up.

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

---

## A4M reference library ingestion (next up after folder walk verified)
A4M fertility course materials: slides + transcriptions. Ingest into `rf_reference_library`. Use local Mac sync path, not cross-account Drive. Blocked only on folder walk manifest verification.

---

## rf_published_content collection
Blogs + IG posts. Build after A4M reference library. Feeds public sales agent.

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
