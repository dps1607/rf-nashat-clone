# RF Nashat RAG — Backlog (deferred work)

Deferred items with enough detail to resume cold. Pulled into context only when picked up.

---

## NEW — added session 15 (2026-04-14, post-Gap-1)

These 7 items are the wake of session 14 closing Gap 1. Captured here so the
governance docs reflect them and future sessions can pick them up cold.

### 1. v3 multi-type Drive loader (Gap 2)
**Priority:** High. This is the named successor to Gap 1.

**Scope:** Build a fresh `drive_loader_v3` module that handles non-Google-Docs
file types: PDF, images, sheets, slides, docx, plain text, audio/video
transcription. Per Dan's standing requirement, "all file types must
eventually be selectable and ingestible." v3 is the vehicle.

**Anti-scope:** Do NOT bolt new file types onto v2. v2 stays Google-Docs-only
and frozen. v3 is a new module that lives next to v1 and v2 in
`ingester/loaders/`.

**Rough shape (full design in `docs/plans/2026-04-XX-drive-loader-v3.md`,
session 15 deliverable):**
- Per-type dispatcher: file MIME → handler module
- Per-type extractors: pdfplumber/PyPDF, vision OCR fallback, openpyxl,
  python-pptx, python-docx, Whisper or Gemini transcription
- Per-type cost model (vision $, OCR $, Whisper $, embedding $/GB source)
- Layer B scrub validation per type — does the existing scrub catch
  collaborator names in each format, or does scrub need extensions?
- File-level selection UI/server unlock (item #2 below) lands as part of
  v3 rollout
- Pilot type (TBD by Dan in design doc) ingested end-to-end as Gap 2
  closure proof, same shape as Gap 1's DFH proof

**Spans:** 3–5 sessions. Design = session 15. Pilot type implementation =
session 16. Remaining types one or two per session after that.

**Dependency:** none — v1, v2, scrub, admin UI all in place.

### 2. File-level selection UI + server unlock
**Priority:** High. Pairs with v3.

**Context:** Session 14 added file-level dispatch plumbing inside
`drive_loader_v2.run()` (forward-compatible, dormant). The admin UI and
server save endpoint were locked to folder-only in the same commit
because v2 is Google-Docs-only and exposing per-file selection over a
folder-only loader would mislead Dan about what's ingestible.

**Scope:**
- `admin_ui/static/folder-tree.js`: re-introduce file checkboxes
- `admin_ui/templates/folders.html`: render file rows
- `admin_ui/app.py` `api_folders_save`: drop the folder-only guard, accept
  arbitrary Drive IDs
- `data/selection_state.json` schema: already supports file IDs (no
  migration needed)

**Anti-scope:** Don't unlock until v3 actually handles non-doc types, or
the UI will let users select PDFs that silently get skipped.

**When:** alongside v3 pilot in session 16.

### 3. Scrub retrofit for legacy collections
**Priority:** Medium. Real liability. Carried from session 13.

**Scope:** Run `ingester/text/scrub.py` Layer B against all chunks in:
- `rf_coaching_transcripts` (9,224 chunks)
- `rf_reference_library` first 584 chunks (the pre-scrub A4M body)

Both contain text from the pre-scrub era. Former-collaborator names
(Dr. Christina Massinople / Mass / Massinople Park) may be present in
chunk text and will surface in retrieval results to end users.

**Implementation shape:**
- Read-only first pass: count chunks where scrub would fire
  (`name_replacements > 0` if applied)
- Show Dan the count + sample chunks
- If approved: write a one-shot retrofit script that updates chunk text
  in place via Chroma `collection.update(ids=..., documents=...)`
- Backup the affected collection before any writes (`tar.gz` of the
  Chroma directory subtree)
- Verify post-write with a second read-only pass: 0 chunks should match
  the scrub patterns

**Anti-scope:** No re-embedding. Embeddings don't shift on a name
replacement that small. No re-chunking. Pure text patch.

**When:** after v3 pilot lands. Not session 15.

### 4. Admin UI "save selection" visual feedback
**Priority:** Low. Pure UX.

**Context:** Session 14 spent ~10 minutes confused about whether saves were
going through because the save button blinks with no toast. Server response
is correct; UI swallows it.

**Scope:** Add a toast component (success/error variants) to
`admin_ui/templates/folders.html` + a `showToast(msg, level)` helper in
`admin_ui/static/folder-tree.js`. Wire it to the save endpoint's response
handling.

**When:** any cleanup session. ~15 min.

### 5. UI selection state reset on save failure
**Priority:** Low. Bug, but workaround exists.

**Context:** When the server guard rejects a save (e.g., a non-folder ID
slipped through to the folder-only endpoint), the JS keeps the stale
selection in memory. The user clicks save again → re-sends the same
rejected payload → loops. Workaround: page reload.

**Scope:** In `folder-tree.js`, on a non-2xx save response, refetch
`/api/folders` and rebuild the in-memory selection from the server's
canonical state.

**When:** alongside item #4. Same file, same trip.

### 6. `/chat` endpoint 500 debug — CLOSED session 15, could not reproduce
**Priority:** Closed. Reopen only with a captured traceback.

**Context:** During session 14 verification I tried `/chat` for end-to-end
RAG retrieval and got a 500 — Claude API error about empty content.
Worked around by using `/query` directly.

**Session 15 investigation:**
- Reproduction attempted against commit `d33d6a9` (same state session 14
  saw the 500 in)
- Sales agent (`nashat_sales`, default mode, `rf_reference_library`
  only): 2 calls, both returned HTTP 200 with well-formed Sonnet 4.6
  responses and 5 cited chunks
- Coaching agent (`nashat_coaching`, `internal_full` mode, both
  collections): 1 call, HTTP 200, 8 chunks retrieved (5 coaching + 3
  reference), full response
- Read `call_claude()` in `rag_server/app.py`: wraps the API call in
  try/except and returns error strings, so a genuine 500 would have
  come from somewhere else in the handler (retrieve_for_mode or
  format_context), not call_claude itself
- Three possibilities named: transient Anthropic API issue during
  session 14, a code path not exercised in session 15 (empty question,
  malformed history, zero-chunk retrieval), or an environment drift
  that self-healed

**Closure:** No current reproducer. Endpoint demonstrably works on both
agents across both collections on `d33d6a9`. Carrying an open bug with
no reproducer eats session budget forever; better to close and reopen
if it recurs.

**If it recurs:** capture the actual traceback from the server stderr
log (not the HTTP response body) and file a new backlog item with the
traceback, the exact curl command, the loaded agent, and the loaded
mode. Without those, the next investigation will hit the same dead
end.

### 6b. Scrub retrofit liability is now CONCRETE (upgraded from #3)
**Priority:** Medium → raised to Medium-High based on session 15 observation.

**Observation (session 15, via coaching agent `/chat` test):** A single
`/chat` query against `internal_full` mode retrieved 5 coaching chunks,
of which 4 contained former-collaborator references in either the
`coaches` metadata field (`"Dr. Christina"`, `"Dr. Nashat + Dr. Christina"`,
`"Dr. Nashat + Dr. Christina"`) or in the chunk text as speaker tags
(`[Dr. Christina]` prefixing transcript lines).

**Why this upgrades the priority:** BACKLOG #3 as originally written
treated the retrofit as a general hygiene task. Session 15's reproducer
shows the liability is **active at the user-facing surface** — every
coaching query returns chunks with these references in the payload.
The LLM response in the session 15 test correctly did not echo the
former-collaborator name (Sonnet 4.6 handled it well), but the raw
chunks returned to the caller still contain them, and nothing in the
current pipeline prevents a future model (or a future prompt, or a
future debugging session that logs chunks verbatim) from surfacing
them.

**No change to the retrofit plan** itself (see BACKLOG #3 above — read-only
count first, approval, one-shot in-place update, backup, no re-embedding).
Just raising the priority signal so it gets picked up sooner rather than
after v3 ships.

**When:** next session after v3 pilot (session 16 or 17), not session 15.

### 7. `scripts/test_login_dan.py` `sys.path` shim — DONE session 15
**Priority:** Closed.

**Context:** Diagnostic script added in session 14. Required
`PYTHONPATH=. ./venv/bin/python scripts/test_login_dan.py` to find
`admin_ui`.

**Fix (session 15):** Added an `os.path`-based sys.path shim at the top
of the imports that prepends the repo root (computed from `__file__`)
to `sys.path` before the `from admin_ui.auth import ...` line. Docstring
updated to drop the `PYTHONPATH=.` prefix from the usage line. Verified
the script imports cleanly from a clean environment and runs through
to its auth check without import errors.

**Commit:** lands in session 15 handover commit alongside the governance
updates.

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


---

## NEW — added session 16 (2026-04-14, post-Gap-2)

These 20 items are the wake of session 16 closing Gap 2 (PDF pilot) plus the
admin UI file-level unlock and the four bugs surfaced during the click-through.
Captured here so future sessions can pick them up cold.

### 8. Answer-grounding verification pass
**Priority:** Medium.

**Scope:** A second-pass check (Claude or programmatic) that maps every factual
claim in a Sonnet response back to a specific chunk in the retrieved context.
Flag any claim that has no clear chunk source as "potentially hallucinated."
Useful for evaluating retrieval quality and catching cases where Sonnet
synthesizes beyond the retrieved evidence.

**Why it matters:** the Step 10 /chat smoke test in session 16 visually verified
that Sonnet's response was grounded in the Egg Health Guide chunks, but the
verification was manual. A programmatic check would scale.

**Estimated effort:** ~half-day session.

---

### 9. Retrieval confidence thresholding
**Priority:** Low-Medium.

**Scope:** When the top retrieval result has similarity below a threshold,
have the agent refuse to answer rather than synthesizing from weak evidence.
Today, retrieval always returns top-N regardless of similarity scores.

**Estimated effort:** ~2 hours including A/B testing on representative queries.

---

### 10. Reconcile requirements.txt with venv state
**Priority:** Medium.

**Scope:** The local venv has drifted from `requirements.txt`. v2's Google/Vertex
SDK upgrade in session 14 added packages that weren't pinned, and session 16
added `pdfplumber`, `Pillow`, `reportlab`, `pypdfium2`, `pdfminer.six` via pip
without updating `requirements.txt`. This means a fresh clone + `pip install -r
requirements.txt` won't reproduce the working environment. Railway is
unaffected (Railway's lockfile is separate), but local dev is brittle.

**Action:** `pip freeze > requirements.txt` after pruning dev-only packages,
then verify a fresh venv reproduces from it. Test that v2 still works against
the new `requirements.txt` before committing.

**Estimated effort:** ~1 hour with testing.


### 11. ✅ RESOLVED in session 17 — refactor v2 to expose Google Doc helper for v3
**Priority:** Closed.

**Background:** Session 16's design doc D2 assumed v3 could `from
ingester.loaders.drive_loader_v2 import process_google_doc` and use it
unchanged for Google Docs alongside the new PDF handler. The function never
existed — v2's Google Doc logic is inline in its `run()` method, not extracted.
Session 16 deferred Google Doc support entirely (raise `HandlerNotAvailable`)
and shipped PDF-only.

**Scope:**
1. Extract v2's Google Doc fetching/parsing/chunking logic into a standalone
   `process_google_doc(file_id, drive_client, scrubber, chunker) -> ExtractResult`
   function that returns the same shape as v3's PDF handler.
2. v3 dispatcher's existing `_HANDLERS["v2_google_doc"]` slot wires this in.
3. Re-test v2's existing functionality to make sure the refactor doesn't
   regress the legacy path (v2 still ships and is still used for legacy ingests).
4. Pilot end-to-end: ingest a Google Doc via v3 dispatcher, verify chunk shape
   matches PDF chunks (same v3_category-style metadata, scrub, locator tags
   where applicable — Google Docs don't have pages but do have headings).

**Why this matters:** until this lands, the admin UI can save mixed
folder/file selections, but if the user picks a folder containing Google Docs,
v3's dispatcher will deferred-skip them and the user won't get those docs into
the collection. The user has to know which file types are supported.

**Estimated effort:** dedicated session. ~3-4 hours including v2 regression test.

---

**Closure (session 17):** Shipped via M3 design — extracted v2's inline Google Doc
logic (export_html, resolve_image_bytes, walk_html_in_order, stitch_stream) into
`ingester/loaders/types/google_doc_handler.py` as a single source of truth.
v2's run() now imports these functions and calls a new `extract_from_html_bytes()`
entrypoint with `emit_section_markers=False` (byte-identical contract). v3's
dispatcher routes `v2_google_doc` MIME to the same handler with
`emit_section_markers=True` (L3 design — emits [SECTION N] markers at h1-h6
headings so display_locator can render as §N).

**Closure proof:** end-to-end commit-run on `[RH] The Fertility-Smart Sugar Swap
Guide` (file_id `1ucqhpCFg5fmj78XyU2yj0ANGM3kJuG7Tuut1jBd2Vrk`, in
`//7. Lead Magnets/[RF] Sugar Swaps Guide`). 1 chunk written to
`rf_reference_library` (604 → 605). Chunk has `source_pipeline=drive_loader_v3`,
`v3_category=v2_google_doc`, `display_locator='§1'` (first real Google Doc with
a § locator), `name_replacements=1` (scrub fired on real production content).
End-to-end /chat smoke test against Sonnet 4.6 returned a grounded response
with zero name leakage (6/6 safety checks PASS, see
`scripts/test_chat_smoke_s17.py`). v2 dry-run regression byte-identical to
session-16 baseline (verified twice — pre and post v3 dispatcher edit).

**Verification environment:** Real Drive API + real OpenAI embeddings + real
Vertex AI Gemini OCR (cache-only path on this run, no live calls) + real
Anthropic Sonnet 4.6 + real local Chroma write. Same standard session 16 used
to close Gap 2.

**Files touched:** `ingester/loaders/types/google_doc_handler.py` (new, 492 lines),
`ingester/loaders/drive_loader_v2.py` (1,105 → 900 lines, three surgical edits),
`ingester/loaders/drive_loader_v3.py` (888 → 896 lines, dispatcher branch),
`scripts/test_google_doc_handler_synthetic.py` (new, 9/9 PASS),
`scripts/test_chat_smoke_s17.py` (new, 6/6 PASS). Backups at
`.s17-backup` (v2, v3) and `.s17-pre-pilot` (selection_state.json).


### 12. `--retry-quarantine RUN_ID` CLI flag
**Priority:** Low.

**Scope:** v3's dispatcher already writes a quarantine JSON for failed files
at `data/ingest_runs/{run_id}.quarantine.json`. The `--retry-quarantine` CLI
flag is stubbed but not implemented. Implement it: load the quarantine, retry
each file, write a new quarantine if any still fail.

**Estimated effort:** ~1 hour.

---

### 13. ✅ RESOLVED in session 16
**Original scope:** "Direct-file chunk ID normalization (`drive:(direct-file):...`
metadata bug)." Fixed mid-Step-9 in session 16 — `_enumerate_files()` now reads
`drive_file["parents"][0]` as `real_parent_folder_id`, populates `folder_meta_by_id`
the same way folder-selected entries do. Manifest miss → quarantine as REAL
failure. Removed the `(direct-file)` fallback entirely. Verified across all 7
Egg Health Guide chunks.


### 14. Orphan chunk cleanup via md5Checksum metadata
**Priority:** Medium.

**Scope:** When a Drive file is updated (md5 changes), v3 will currently write
NEW chunks for the new content but leave the OLD chunks orphaned in the
collection — both versions retrievable. Add `source_file_md5` to chunk
metadata at write time, then a periodic cleanup pass that:
1. Lists all distinct (file_id, md5) pairs in the collection
2. For each file_id with multiple md5s, queries Drive for the current md5
3. Deletes chunks with stale md5s

**Dependency:** BACKLOG #23 (also uses `source_file_md5`). Bundle.

**Estimated effort:** ~2 hours.

---

### 15. Canonical display_subheading format decision
**Priority:** Low.

**Scope:** Today the display_subheading is constructed inconsistently across
the three chunk populations (9,224 coaching, 584 pre-scrub A4M, 13 v2 DFH,
7 v3 PDF). Decide on a canonical format — leading slashes? Drive name prefix?
And retrofit all populations to it.

**Bundle with:** #17 (cosmetic normalization), #6b (coaching scrub retrofit),
#18 (format_context migration). Single coordinated retrofit session.

---

### 16. Document schema-union intent
**Priority:** Low.

**Scope:** v3 chunks have fields v1/v2 chunks don't (`v3_category`,
`source_pipeline`, `display_locator`, `source_file_md5`, etc.). Document the
fact that the chunk schema is a UNION across pipelines, not a strict shared
schema. Add a section to `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` (or rename
that file to `CHUNK_SCHEMA.md`) explaining which fields are required vs
optional vs pipeline-specific.

**Why:** future engineers (or future-me) reading retrieval code will assume
all chunks have all fields. They don't. This trips up `format_context()`
maintenance specifically.

**Estimated effort:** ~30 min.


### 17. display_subheading cosmetic normalization (REVISED SCOPE)
**Priority:** Medium.

**Original scope (session 15):** Normalize leading `//` and drive-name prefix
in `display_subheading` for the 13 v2 DFH chunks.

**Revised scope (session 16):** This affects ALL THREE chunk populations:
- 9,224 `rf_coaching_transcripts` chunks
- 584 pre-scrub A4M chunks in `rf_reference_library`
- 13 v2 DFH chunks in `rf_reference_library`
- 7 v3 PDF chunks in `rf_reference_library` (newest, may already be canonical)

The 9,224 coaching chunks dominate by ~15x. Cosmetic-only changes to those
shouldn't require re-embedding (metadata-only update).

**Strong recommendation: bundle with #6b (coaching scrub retrofit), #18
(`format_context()` migration), and #20 (inline citation prompting) into a
single coordinated retrofit session.** One backup, one read pass, one write
pass per collection. The bundle saves ~3-4 sessions of incremental work and
~$10-20 in re-embedding if any of the changes need it.

**Estimated effort as a bundled retrofit session:** ~half-day.

---

### 18. `format_context()` doesn't use session-9 normalized display fields
**Priority:** Medium.

**Scope:** `rag_server/app.py:format_context()` was written before session 9's
display-field normalization and still reads old A4M-specific names
(`module_number`, `module_topic`, `speaker`, `topics`). Session 16's Step 10
added a minimal v3-aware branch (Option R3) so v3 PDF chunks render with
`Source: ... — Link: ...`, but the legacy A4M code path is untouched.

**Migration plan:**
1. Define a canonical `chunk_to_display(chunk) -> dict` helper with fields
   like `source_label`, `locator`, `link`, `summary` etc.
2. Each chunk population's writer populates these at ingest time.
3. `format_context()` reads only the canonical fields, no special branches.
4. A/B test on representative queries to ensure response quality doesn't
   regress.

**Bundle with:** #17, #20.

**Estimated effort:** ~half-day in the retrofit bundle session.

---

### 19. Post-scrub text quality check
**Priority:** Low (cosmetic).

**Scope:** Layer B scrub sometimes produces awkward sentences like "Drs.
Nashat Latib and Dr. Nashat Latib" when the original mentioned the
collaborator twice in the same paragraph. Add a post-scrub pass that detects
these patterns (regex for repeated names, "and X and X", title repetition)
and rewrites to natural-sounding prose.

**Estimated effort:** ~1 hour. Optional polish.


### 20. Inline citation prompting in agent system prompts
**Priority:** Medium.

**Scope:** Session 16's `format_context()` update makes source filenames, page
locators, and Drive links available to Sonnet in retrieved context. The
session 16 /chat smoke test confirmed Sonnet uses the chunks for grounding,
but does NOT inline-cite them in the response — neither `nashat_sales.yaml`
nor `nashat_coaching.yaml` currently prompts Sonnet to surface sources.

**Action:** add to both persona prompts something like:
> "When referencing specific facts from the retrieved context, cite the source
> filename and page (e.g., 'per the Egg Health Guide, p. 8'). When referencing
> a guide the user could read in full, offer the Drive link."

**Bundle with:** #18 (`format_context()` migration). Same retrofit session.

**Caveat:** A/B test required. Inline citations can change response tone in
ways that affect Dr. Nashat's voice. May want sales agent to cite sparingly
(brand voice) and coaching agent to cite explicitly (clinical accuracy).

**Estimated effort:** ~1 hour including A/B test.

---

### 21. Folder-selection UI redesign
**Priority:** Medium. **Single biggest friction point** in the folder-selection workflow.

**Scope:** Eliminate the pending-panel/tree redundancy. Currently the
`folders.html` template has a tree view with checkboxes AND a separate
pending panel listing every selected folder/file. These show the same
selection state twice, with the pending panel adding only a per-item library
dropdown (vestigial — only one writable library exists). Session 16's
file-unlock amplified the problem by adding file rows to both surfaces.

**Redesign sketch:**
- Remove the pending panel entirely
- Add a sticky summary bar: `"N folders, M files selected — [Save]"`
- Add inline `[N selected]` badges to folder rows in the tree where
  descendants are checked
- Auto-assign `rf_reference_library` at save time; drop the library dropdown
  until a second writable library exists
- Visual differentiation between drives, folders, and files (icons + indent),
  which also fixes the "user can't tell drive checkbox from folder checkbox"
  problem from session 16's bug #4

**Dependencies:** none structural — server endpoint already accepts the
correct shape. Pure UI work.

**Estimated effort:** dedicated 60–90 min session, probably session 18 or 19.


### 22. Drive-root selection UX
**Priority:** Low.

**Scope:** When a user checks a whole drive-root checkbox in the tree, session
16 emits a clean error toast: `"Selecting whole drives is not supported yet —
expand the drive and select individual folders."` Two improvements possible:

(a) **Actually support drive-root selection** by walking all top-level folders
when the ID matches a `drive_id` in the manifest. Adds a "select-all-folders-
in-drive" semantic without requiring the user to click each one.

(b) **Or just leave the error message as-is**, since it's already clear and
correct. This is the simpler path.

**Recommendation:** (b) for now. Revisit if users actually want (a).

**Estimated effort:** (a) is ~2 hours; (b) is zero (already done).

---

### 23. Content-hash dedup at v3 commit time
**Priority:** Medium.

**Scope:** v3 currently dedupes by chunk_id (`drive:{slug}:{file_id}:{chunk_index}`).
Different file IDs for the same content → separate chunk rows → retrieval
noise. Session 16's user feedback raised this re: multiple Low AMH Guide
versions in the same folder (`RH - Low AMH Guide.pdf`, `Low AMH GPT Guide`,
`RH - Low AMH Guide-min.pdf`, `RH | Low AMH Guide - Original`).

**Action:** add `source_file_md5` (from Drive's `md5Checksum` field, already
in v3's `FILE_FIELDS`) to chunk metadata. Before writing chunks for a new
file, query the target collection for existing chunks with the same md5. If
found, skip with a "already ingested under different file_id" warning.

Strategy D1 from the session 16 dedup discussion. Catches exact re-uploads
(same content, different filename) but NOT "same topic, slightly different
wording" — that's BACKLOG #24.

**Bundle with:** #14 (orphan cleanup also uses md5 metadata).

**Estimated effort:** ~30 lines of code + 1 test. ~1 hour.

---

### 24. Version-aware file selection UX
**Priority:** Low-Medium.

**Scope:** In the folder-selection UI, detect files within the same folder
that share a naming pattern (`RH - X.pdf`, `X-min.pdf`, `X - Original`,
`NL EDIT X`, etc.) and surface them as "possible duplicates" with a warning
badge so the user can pick the canonical version explicitly.

Optionally add embedding-similarity-based near-duplicate detection (strategy
D3 from the session 16 discussion): for each new file, embed just the first
chunk and query for similar first-chunks. If high similarity to an existing
file, flag for user review rather than auto-skipping.

**Bundle candidate:** with #21 (UI redesign session).

**Estimated effort:** ~half-day in the redesign session.


### 25. Non-recursive folder cascade option
**Priority:** Low (design question).

**Scope:** Today, checking a folder in the tree cascades the visual check
state to all descendant folders (which then land in `selectionState`). Ingest
behavior: v3 walks each of those descendant folders and picks up files. This
is intentional — "select this whole branch."

**Alternative:** check ONLY the top folder, and let v3's enumerator recurse
at ingest time. Less surprising visually, but requires v3's `_enumerate_files()`
to walk recursively, which it currently does not (v3 only walks the immediate
contents of selected folders).

**Decision needed:** which semantics? Recursive cascade (current, pre-session-16
preserved) or single-folder-with-server-side-recursion (new)?

**Recommendation:** keep current. The redesign session (#21) is when to revisit
because the visual feedback for "what's selected" needs to make the answer obvious.

**Estimated effort:** N/A — design question only.

---

### 26. Admin UI Safari testing protocol + selectionState retrofit
**Priority:** Medium.

**Scope:** Two related items from session 16's Bug 3:

(a) **Testing protocol:** when developing the admin UI, test in Chrome FIRST.
Safari has aggressive caching, console quirks (paste-doesn't-execute, filtered
errors), and CSS oddities that make it unreliable for iterative development.
The session 16 toast/save debugging loop took 4 rounds in Safari that would
have taken 1 round in Chrome. **Add this to the standing session prompt
checklist** so future sessions don't repeat the experience.

(b) **`selectionState` retrofit:** session 16's save handler now reads from
the DOM at save time, ignoring `selectionState`. But the **pending panel render
path** still uses `selectionState` to know what to show. This means the panel
can still drift out of sync with the DOM in edge cases (lazy-load re-renders,
search filter rebuilds, etc.). Either:
- (i) Rewrite the pending panel to also read from the DOM, OR
- (ii) Eliminate the pending panel entirely as part of #21 (UI redesign)

**Strong recommendation:** (ii). The UI redesign in #21 already removes the
pending panel, so the `selectionState` retrofit becomes free.

**Estimated effort:** (a) 5 min (add a sentence to session prompts).
(b) folded into #21.

---

### 27. CSP allows Google Fonts (or self-host)
**Priority:** Low.

**Scope:** Safari's console showed during session 16 click-through:
`[Error] Refused to load https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap because it does not appear in the style-src directive of the Content Security Policy.`

The admin UI uses Google Fonts but Talisman's CSP `style-src` directive in
`admin_ui/app.py` doesn't allowlist `fonts.googleapis.com`. Browser falls back
to system fonts, which is why nobody noticed visually until now.

**Two options:**
(a) Add `fonts.googleapis.com` and `fonts.gstatic.com` to the CSP allowlist.
(b) Self-host the fonts in `admin_ui/static/fonts/` and reference them locally.

**Recommendation:** (b) for security/privacy and to eliminate an external
dependency. Cormorant Garamond and Inter are both available under Open Font
License — download once, ship locally.

**Estimated effort:** ~30 min.

---

### 28. Verify BACKLOG closures end-to-end in the environment where they manifested
**Priority:** Process improvement.

**Scope:** Session 15 marked BACKLOG #4 (toast bug) "fixed" based on a CSS
tweak that nobody verified in a real browser session. Session 16 discovered
the toast was still completely broken — the fix was cosmetic and didn't
address the actual root cause. Cost: 2 hours of session 16 time spent
re-discovering and properly fixing the same bug.

**Process change:** when closing a BACKLOG item, the closure note must include
a verification step in the environment where the bug was originally reported.
For UI bugs, that means a real browser click-through, not just a CSS file
edit. For data bugs, that means a query against the live collection, not just
a unit test on synthetic data.

**Action:** add this to the standing session prompt checklist + the BACKLOG
file's preamble.

**Estimated effort:** 5 min documentation. Real cost is the discipline.

---

## NEW — added session 17 (2026-04-14, post-#11-closure)

These items are wake from session 17 (BACKLOG #11 closure). Captured here so
future sessions can pick them up cold.

### 29. Strip Canva and editor metadata from Google Doc extraction
**Priority:** Medium. Pre-existing in v2; surfaced again by session 17 pilot.

**Scope:** When v3's google_doc_handler extracts content from real lead-magnet
Google Docs, the first ~120 chars are often editor metadata that has no value
for retrieval and pollutes embeddings:

  - Canva design edit URLs (`https://www.canva.com/design/.../edit?utm_content=...`)
  - Production tags like `COVER:`, `PAGE 1:`, `HEADER:`, etc.
  - Internal "draft notes," "editor notes," version stamps

The Sugar Swaps Guide pilot in session 17 produced a chunk that starts:

  "Canva design to edit: https://www.canva.com/design/DAGlfxX42jY/_WuqmWVxGC6rcZLnko8RCw/edit?utm_content=DAGlfxX42jY&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton / / COVER: / / The Fertili..."

Same behavior exists in v2 on its 13 DFH chunks (session 14). Not blocking
\#11 closure but it will degrade retrieval similarity scores for Google Doc
content vs cleaner sources (PDFs, A4M).

**Action:** add an editor-metadata stripper to `google_doc_handler` that runs
during `stitch_stream` or as a post-pass on `stitched_text`. Strategy:

1. Strip lines matching common Canva URL patterns (`canva\.com/design/[^\s]+`)
2. Strip lines that are bare "production tags" — uppercase word followed by
   colon at start of paragraph, no body content (`COVER:`, `PAGE 1:`,
   `HEADER:`, `FOOTER:`, etc.)
3. Strip standalone "draft" / "editor note" markers
4. Be conservative — false positives that strip real content are worse than
   leaving editor noise in.

**A/B test required:** before-and-after comparison on the Sugar Swaps Guide
chunk plus the 2 DFH Google Doc chunks. Verify retrieval similarity on a
known-good query improves (or at least doesn't regress) after the strip.

**Estimated effort:** ~1-2 hours including the A/B test on existing chunks.

---

### 30. v3 metadata writer drops `extraction_method` and `library_name`
**Priority:** Medium. Observation; non-blocking but worth fixing during the
retrofit bundle session (#18).

**Scope:** Session 17 commit verification surfaced that v3-written chunks have
`extraction_method=None` and `library_name=None` in their stored Chroma
metadata, even though:

  - `pdf_handler.extract` returns an `ExtractResult` with
    `extraction_method='pdf_text'` or `'pdf_ocr_fallback'`
  - `google_doc_handler.extract` returns
    `extraction_method='google_doc_html_vision'`
  - The selection state explicitly assigns `library_name='rf_reference_library'`
    and the chunk DOES land in the right collection

Same shape on session 16's PDF chunks — this is not a session 17 regression,
it's a pre-existing v3 metadata writer bug where these two fields aren't
propagated from the handler/dispatcher into the per-chunk metadata dict
written via `collection.add`.

**Where to look:** `drive_loader_v3.py` per-chunk metadata builder (search
for the `metadatas.append` call inside the commit branch). The
`extraction_method` should come from `extract_result.extraction_method` and
`library_name` from the resolved selection assignment.

**Why it matters:** `extraction_method` is used by per-type cost rollups
(D5 from the v3 design doc) and the retrofit bundle's canonical
`chunk_to_display(chunk)` helper (#18) will need `library_name` to render
collection-aware citations. Both are dead-letter today.

**Bundle with:** #18 (`format_context()` migration). Same retrofit session
that touches the chunk metadata writers.

**Estimated effort:** ~30 min including verification on existing v3 chunks.

---

### 31. `test_admin_save_endpoint_s16.py` clobbers `data/selection_state.json`
**Priority:** Low. Side effect, not a bug per se.

**Scope:** When `scripts/test_admin_save_endpoint_s16.py` runs, it ends with
the line:

    restored /Users/.../data/selection_state.json to session 16 working state

The test has hardcoded restore logic that overwrites `data/selection_state.json`
with a fixed session-16 shape (DFH folder + Egg Health Guide PDF) regardless
of what was in the file before the test ran. Session 17 hit this when running
the test battery after restoring `selection_state.json` to a different state —
the test silently undid the restore.

**Action:** either (a) make the test save the original file's contents in a
`finally` block and restore them at exit, or (b) use a temp file for the test
and never touch `data/selection_state.json`. Option (b) is cleaner.

**Why low priority:** the hardcoded restore happens to match what most
sessions want (session-16 working state), so the side effect is benign in
practice. But it's a foot-gun for any session that's iterating on
`selection_state.json` and runs the full test battery in between iterations.

**Estimated effort:** ~15 min.

---

### 32. Smarter Google Doc locator detection (beyond h1-h6 headings)
**Priority:** Low-Medium. Cosmetic — affects retrieval citation quality for
Google Docs that don't use real heading tags.

**Background:** Session 17's L3 design emits `[SECTION N]` markers at `<h1>`
through `<h6>` tags so `derive_locator` can produce `§N` locators. This
worked correctly on the Sugar Swaps Guide (which has real headings) but on
the DFH virtual dispensary (which uses bold text as pseudo-headings) it
produces an empty locator. The dispatcher correctly stores `display_locator=''`
in that case, and `format_context()` handles empty locators gracefully — but
the chunk is less citable than it could be.

**Two paths:**

(a) **Detect bold-text-as-pseudo-heading** by looking for `<strong>` or
    `<b>` tags that are the only content of a `<p>` element and treating
    them as section breaks. Riskier — Canva-styled Google Docs sometimes
    bold random words for emphasis.

(b) **Fall back to paragraph numbering** when no real headings are found.
    Locator becomes something like `¶12` or `block 12`. Less semantic
    but always populated.

**Recommendation:** (b), as a fallback that only fires when the doc has zero
`<h1>`-`<h6>` tags. Add a `PARA` marker unit to `types/__init__.py`
`PAGE_MARKER_RE` and update `derive_locator` to render it as `¶N` /
`¶¶N-M`.

**Estimated effort:** ~2 hours including a synthetic test for the no-headings
fallback path and a re-extraction (dry-run only, no Chroma writes) of the 2
DFH chunks to verify they get fallback locators.

---


---

## NEW — added session 18

### 33. Rename `SESSION_16_CATEGORIES` to something accurate
**Priority:** Low. Cosmetic.

**Scope:** The constant `SESSION_16_CATEGORIES` in `drive_loader_v3.py` now contains `{"pdf", "v2_google_doc", "docx"}`. The name is misleading — pdf was session 16, v2_google_doc was session 17, docx was session 18. Future handlers will keep adding to it.

**Action:** rename to `SUPPORTED_CATEGORIES` (or `LIVE_HANDLER_CATEGORIES`). Pure rename, all-references update, no behavioral change. Touches `drive_loader_v3.py` and any tests/docs that grep for the old name.

**Estimated effort:** ~15 min.

---

### 34. v3 dry-run dump-json doesn't include per-chunk text
**Priority:** Low-Medium. Inspection-quality issue surfaced session 18.

**Scope:** When `drive_loader_v3 --dry-run` writes its run record (`data/ingest_runs/<run_id>.dry_run.json`), the `per_file` array contains summary stats (chunk count, vision cost, extraction method) but no per-chunk text or per-chunk metadata. To inspect projected chunks during a halt-before-commit gate, sessions have to run a separate ad-hoc extraction script (session 18 wrote `/tmp/rf_docx_pilot_chunks.py` for this).

**Why it matters:** The standing rule is "halt before --commit and show Dan dump-json output first." The dry-run dump should be self-contained enough to satisfy that rule without re-running extraction.

**Action:** add a `sample_chunks` array to each `per_file` entry containing the first 3 chunks (or all if ≤3) with `text_preview` (first 200 chars), `word_count`, `display_locator`, `name_replacements`. Keep the dump under a few MB even on large runs. Don't include full chunk text (that's what the actual chunk store is for).

**Estimated effort:** ~30 min including a regression test against the existing dry-run records.

---

### 35. Document content source-of-truth before bulk ingestion
**Priority:** HIGH. Blocks bulk ingestion of any text-bearing file type.

**Scope:** Surfaced session 18. The corpus we're building has multiple file forms of the same content:
- Same content × multiple file forms (docx draft + published HTML + email broadcast of the same blog)
- Same content × multiple file copies (filesystem dups already visible: 2× Biocanic guide, 2× FKSP Call Booked email seq)
- Drafts × revisions
- Source × derivative (audio + transcript + Google Doc summary of one event)

Without a designated canonical source per content domain, we'll ingest near-duplicates and pollute retrieval.

**Deliverable:** `docs/CONTENT_SOURCES.md` mapping content domain → canonical Drive folder(s) → file forms to ingest vs. skip. Format roughly:

| Content domain | Canonical source | Skip |
|---|---|---|
| Blog posts | Published HTML on website | docx drafts, email broadcasts of blog content |
| Lead magnets | The PDF or Google Doc actually delivered to customers | Drafts, Canva editor exports, internal review copies |
| Coaching content | The transcript (already in `rf_coaching_transcripts`) | Email summaries, Google Doc recaps |
| Email sequences | The docx of record | One-off sends, archived versions |
| Educational reference | The A4M course PDFs and similar | Notes, summaries, blog versions of the same material |

Dan decides the mappings; Claude documents. Becomes the input to selection decisions for any subsequent bulk ingestion.

**Estimated effort:** ~1 hour of conversation with Dan to walk the inventory and decide canonical sources, then ~30 min to write the doc.

---

### 36. April-May 2023 Blogs.docx commit deferred indefinitely
**Priority:** Marker, not a task. Tracks a deferred decision.

**Scope:** Session 18 successfully dry-ran the docx handler against `April-May 2023 Blogs.docx` (file_id `1IjhVUc6Px8II4FH0PsMJlOvNX01E6S1-`, 7 chunks projected, all clean and locator-populated). The commit was deferred at the halt-before-commit gate because the same blog content exists in at least three forms (docx, published HTML on website, email broadcasts) and we hadn't decided which form is canonical.

**Resolution path:** once `docs/CONTENT_SOURCES.md` (#35) is written and assigns a canonical source for "blog posts," revisit:
  - If docx is canonical → commit the blogs file (re-run the dry-run, confirm 7-chunk count unchanged, run --commit, verify 7-point closure checklist)
  - If HTML is canonical → skip the docx, plan an HTML handler for a future session
  - If email broadcasts are canonical → skip the docx, plan a different ingestion strategy

**Until resolved:** the docx handler stays wired, but no blog-form docx files get committed. The pilot record at `data/ingest_runs/e1f02930bb104928.dry_run.json` documents what would have been written.

