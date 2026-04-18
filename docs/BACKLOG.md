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

### 6b. Scrub retrofit liability is now CONCRETE (upgraded from #3) — DECLINED session 23
**Priority:** Declined / not pursuing.

**Decision (session 23):** Dan declined the coaching scrub retrofit. The current Sonnet 4.6 handling of these references in raw chunk payloads is acceptable; the retrofit is not a current build priority. Future sessions should not re-propose this as a strategic next step. If a real downstream surface change makes it newly necessary (e.g., a future model that surfaces raw chunk text directly to users, or a logging change that exposes them), reopen with the new trigger documented.

**Original scope (now historical):**

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
**Priority:** Low (revised session 23). Real but trigger-driven, not time-driven.

**Revised disposition (session 23):** Do this when you actually need a fresh venv — new collaborator, new machine, Railway lockfile drift surfaces a real bug, or a session starts with a `pip install` that fails. Don't bundle pre-emptively. The "1 hour" estimate is optimistic: `pip freeze` dumps 100+ packages including dev cruft and transitive deps; pruning requires judgment ("is `cffi` needed or transitive?"); verification means building a fresh venv and running all 13 test scripts. Worst case: a new requirements.txt that breaks something subtle (e.g., Vertex SDK version mismatch) bundled with unrelated work. Local works, Railway works, tests pass. It's debt, not a wound.

**Original scope (still applies when triggered):**

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


### 17. display_subheading cosmetic normalization — DEFERRED session 24 (no consumer)
**Priority:** Low (revised s24). No current consumer reads `display_subheading`.

**Session 24 finding:** The canonical `chunk_to_display(chunk)` helper (#18 closure) reads `source_file_name` (v3) / `module_number`+`module_topic` (legacy A4M) for the rendered source label, not `display_subheading`. The field is a dead-letter in the current retrieval path. Normalizing it is busywork until a concrete consumer appears (export pipeline, UI surface, new retrieval mode). Per the s23 "coupled items shouldn't be split casually" principle, #17 only becomes real when #18's renderer or a future feature actually reads it.

**Reopen trigger:** A surface appears that reads `display_subheading` (admin UI chunk browser, export to docs, debugging tool, etc.) and rendering inconsistency becomes user-visible.

**Original scope (historical, session 15/16):** This affects ALL THREE chunk populations:
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

### 18. `format_context()` doesn't use session-9 normalized display fields — RESOLVED session 24 — ✅ RESOLVED
**Priority:** Closed.

**Closure (session 24):** Shipped `rag_server/display.py` with canonical `chunk_to_display(chunk, render_configs) -> dict` + `format_context(chunks, render_configs) -> str`. `rag_server/app.py` migrated — the branch-heavy inline renderer is gone, replaced with a thin wrapper that delegates to the canonical helper and passes the current agent's per-collection render config.

**Design highlights:**

1. **Two-layer separation.** Retrieval returns full chunks with all metadata (API responses via `/query` + `/chat` are unchanged — lab correlation and client tracking code reads `chunk.metadata` directly). The *rendering* layer is what gets filtered.

2. **YAML-configurable visibility.** Each agent's `knowledge.render.<collection>` block controls which display fields are surfaced to the LLM. Schema: `show_source_label`, `show_speaker`, `show_topics`, `show_locator`, `show_link`, `show_date`. Missing collection → sensible per-collection defaults in display.py (`_DEFAULT_RENDER`). Missing block entirely → defaults everywhere. Backward compatible with any existing YAML.

3. **Hardcoded protection of client identifiers.** `client_rfids`, `client_names`, `call_fksp_id`, `call_file` are NEVER surfaced to the LLM regardless of any YAML knob. Enforced in `_resolve_speaker()`/`_resolve_date()` for coaching (return "" even when the YAML config says show_speaker=true) and by the fact that no resolver function reads those fields at all. No knob to flip by accident.

4. **Graceful degradation.** `_clean(value)` normalizes `None`, `"Unknown"`, `"unknown"`, `"None"`, and whitespace-only to `""`. Every renderer field goes through it. No "Presenter: Unknown" artifacts. The M3 A4M case (speaker = literal "Unknown") renders with no Presenter line at all. Missing locator → no em-dash separator in the Source line. Missing source_label entirely → renders just the chunk text under the item divider.

5. **Canonical source resolution covers all 4 populations:**
   - v3 PDF / Google Doc / docx → `source_file_name`
   - Legacy A4M → `A4M Module {n}: {topic}` or `A4M: {topic}` if no module number
   - Coaching → `""` (section header scopes it; avoids per-item leak of call identifiers)
   - Unknown collection → falls through to generic `CONTEXT (name):` header

**Files shipped:**
- `config/schema.py` — added `RenderConfig` model + `Behavior.citation_instructions` + `Knowledge.render` (2 optional fields, extra="forbid" honored)
- `rag_server/display.py` — NEW, 260 lines, documents the protection contract explicitly
- `rag_server/app.py` — imports `format_context as _format_context_v2`; thin wrapper delegates with current agent's render config; citation_instructions appended to system prompt when non-empty
- `scripts/test_format_context_s24.py` — NEW, 79/79 PASS, covers 4 populations × full/degraded metadata × YAML override × protected-field leak checks × mixed-population render × unknown-collection fallback
- `scripts/test_format_context_s16.py` — one assertion updated (s24 canonicalization means A4M chunks now emit `Source: A4M Module N: ...` like v3 chunks; the assertion that encoded the old "v3 gets Source:, A4M gets Module:" inconsistency is now `Source: A4M Module 7: ...` expected). 22/22 PASS.
- `config/nashat_sales.yaml` — added `citation_instructions` (light-touch, warm voice) + `knowledge.render` for rf_reference_library
- `config/nashat_coaching.yaml` — added `citation_instructions` (clinical transparency) + `knowledge.render` for both collections

**Verification:**
- All 13 pre-existing test scripts still green
- New test: 79/79 PASS
- Both agent YAMLs validate against the updated schema
- Live render against real Chroma chunks (coaching + v3 PDF) produced expected output: coaching showed only `Topics: ...`, no RFIDs/names/dates; v3 PDF showed full `Source: ... — pp. 1-6 — date` + `Link: ...`
- Zero Chroma writes this session

**What was NOT done (deferred, by design):**
- A/B testing of citation_instructions effect on Sonnet responses — deferred to s25 (~$0.05 budget, 2 queries × 2 agents × before/after). Work is validation-only; code merge doesn't depend on it.
- #17 display_subheading normalization — no current consumer reads the field; deferred until a surface appears.
- Metadata-only upserts on existing chunks — not needed; canonical helper reads existing fields as-is.

**Live observation (not a defect of this work):** Coaching chunks in production contain `"dr christina"` tokens inside the chunk body text itself (speaker diarization labels from pre-scrub ingestion). These are NOT leaked by the renderer — they're content inside `document`, not metadata. Current Sonnet 4.6 handles them correctly per s15 finding. This is the territory BACKLOG #6b was declined s23; the s23 reopen-trigger language still applies.

**Original scope (historical):**
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


### 20. Inline citation prompting in agent system prompts — RESOLVED session 25 — ✅ RESOLVED
**Priority:** Closed.

**Closure (session 25):** Live A/B validation run via `scripts/test_citation_instructions_ab_live_s25.py`. 4 queries (2 sales, 2 coaching) × 2 conditions (baseline with citation_instructions stripped vs. treatment as-shipped) = 8 Sonnet 4.6 calls. Spend: $0.2273. Results dumped to `data/s25_citation_ab_results.json`.

**Verdict: ship as-is.** citation_instructions work as intended; no YAML text changes required.

**Results summary:**

| Criterion | Result |
|---|---|
| Source grounding | ✅ Treatment cited sources when they exist. Baseline cited nothing. |
| Locator honesty | ✅ Cited real locators when present (S1/C2: "Egg Health Guide pp. 8-10"). Did not invent page numbers. |
| No fabrication | ✅ Every treatment citation traces to a real source name in retrieved context. |
| Voice preservation | ✅ Sales stayed warm. Coaching stayed warm-but-clinical. |
| Degradation handling | ✅ A4M chunks with no locator cited as "per the A4M curriculum" — no invented pages. |
| Link surfacing | ⚠ Observation-only: 0/4 treatment responses surfaced the Drive link despite 3/4 having a linked chunk in context. Model being conservative, which the YAML hedge "if they might want to" arguably permits. Not a bug; captured for future tuning if clients request links. |

**S2 observation (not acted on):** sales treatment added a trailing emoji (`🙂`) that baseline did not. Single occurrence across 4 test responses. Log as a drift marker — re-evaluate if it recurs in future A/B passes.

**Session 24 work (historical, all still in production):**
- Added `behavior.citation_instructions` field to schema (optional, empty default)
- `assemble_system_prompt()` appends when non-empty under `CITATION GUIDANCE:` header
- Sales agent YAML: light-touch guidance ("brief, warm, don't interrupt flow, page/link when shown, never invent")
- Coaching agent YAML: clinical transparency guidance ("cite explicitly, include page/section when shown, offer Link when available, never invent")
- Both handle missing metadata gracefully in-prompt: "When only the source name is shown, cite just the name."

**Why the s25 A/B script is NOT added to the Step 0 test suite:** it costs ~$0.23 to run (live Sonnet calls × 8). Step 0 runs every session — a $0.23 gate on every session is not the right pattern. The script is retained in `scripts/` as a one-shot validation tool for future YAML-text changes to citation_instructions; run on demand, not as regression.

**Files retained:**
- `scripts/test_citation_instructions_ab_live_s25.py` (322 lines, re-runnable)
- `data/s25_citation_ab_results.json` (8 responses, token counts, cost per call)

**Original scope (historical):**
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

### 23. Content-hash dedup at v3 commit time — STAGE 2 RESOLVED session 19
**Priority:** Medium.

**Status:** ✅ Stage 2 (post-extraction `content_hash` check) shipped session 19. Stage 1 (pre-extraction md5 fast path) deferred → BACKLOG #37. — ✅ STAGE 2 RESOLVED in session 19, Stage 1 → #37
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

### 26. Admin UI Safari testing protocol + selectionState retrofit — PART (a) INCORPORATED session 23 — ⚠ PART (b) STILL OPEN
**Priority:** Medium (part b only).

**Part (a) closure (session 23):** "Test admin UI in Chrome before Safari" rule incorporated into NEXT_SESSION_PROMPT_S24.md flight rules under "Verification & debugging." Carries forward via the standard mechanism.

**Part (b) still open:** `selectionState` retrofit — pending panel render path still uses `selectionState` and can drift out of sync with DOM in edge cases. Strong recommendation to fold into #21 (UI redesign) which removes the pending panel entirely. Effort then becomes free.

**Original scope (now historical for part a):**

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

### 28. Verify BACKLOG closures end-to-end in the environment where they manifested — INCORPORATED session 23 — ✅ CLOSED-VIA-PROCESS
**Priority:** Closed.

**Closure (session 23):** Incorporated into NEXT_SESSION_PROMPT_S24.md flight rules under "Verification & debugging." Carries forward to all subsequent session prompts via the standard "carries forward unchanged" mechanism. No standalone template file exists; the rule lives in the per-session prompt.

**Original scope (now historical):**

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

### 29. Strip Canva and editor metadata from Google Doc extraction — RESOLVED session 19 (code) + session 20 (A/B verification) — ✅ FULLY RESOLVED
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

### 30. v3 metadata writer drops `extraction_method` and `library_name` — RESOLVED session 19 — ✅ RESOLVED in session 19
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

### 31. `test_admin_save_endpoint_s16.py` clobbers `data/selection_state.json` — RESOLVED session 22 — ✅ RESOLVED
**Priority:** Closed.

**Closure (session 22):** Rewrote the test to snapshot `data/selection_state.json` byte-for-byte before any test runs (or record `_PRE_EXISTED = False` if absent) and restore (or `unlink()`) in a `finally` block. Removed the hardcoded `final = {...}` dict and the misleading "restored to session 16 working state" log line. Probe-verified end-to-end: backed up real state → wrote `PROBE_FOLDER_S22_DO_NOT_USE` sentinel → ran test → confirmed 16/16 PASS and probe values intact post-restore → restored real state, MD5 round-trip identical. The hardcoded restore happened to coincide with Step 0 expectations every session 17–22, which made the foot-gun invisible until you tried iterating on selection_state — snapshot/restore is now byte-transparent.

**Original scope (now historical):**

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

### 35. Document content source-of-truth before bulk ingestion — ✅ RESOLVED session 28
**Priority:** Closed.

**Closure (session 28):** Shipped `docs/CONTENT_SOURCES.md` (489 lines) after ~2 hours of domain-by-domain conversation with Dan. The doc scopes 14 content domains + anti-ingestion list + cross-cutting rules + ~28 follow-up BACKLOG seeds. Key framing decisions captured in the doc and landing as new BACKLOG items below:

- **Collections architecture (13 target collections):** strict separation of external-approved (`rf_reference_library`) vs our-public (`rf_published_content`) vs paywalled curriculum (`rf_curriculum_paywalled`) vs sales playbook (`rf_sales_playbook`) vs marketing (`rf_marketing`) vs testimonials (`rf_testimonials`) vs visual library (`rf_visual_library`) vs supplements (`rf_supplements`) vs lab data (`rf_lab_data`) vs coaching transcripts (existing `rf_coaching_transcripts`) vs coaching visuals (`rf_coaching_visuals`) vs (conditional) internal knowledge (`rf_internal_knowledge`) vs metadata index (`rf_library_index`).
- **Coaching-not-medicine framing:** no PHI; access control via Cloudflare Access allowlist, not content redaction. Client-identity metadata hardcoded-protected in rendering.
- **RFID walkback:** `client_rfids` currently not usable (system incomplete); remove from existing chroma and reintroduce when finalized.
- **Domain 4-OUT reversal:** TFF Program Contracts + cohort spreadsheets previously anti-ingestion, now IN scope for client-timeline linkage.
- **Admin UI surface:** these 13 collections become the selection targets in `library_assignments`; significant UI expansion work ties to #21.

The 28-item seed list stays in `docs/CONTENT_SOURCES.md` as the canonical source. The highest-priority subset is promoted to BACKLOG entries #44–#49 below for s29+ consideration.

**Original scope text (kept as history for anyone cross-referencing):**

**Priority:** HIGH. Blocks bulk ingestion of any text-bearing file type.

**Scope:** Surfaced session 18. The corpus we're building has multiple file forms of the same content:
- Same content × multiple file forms (docx draft + published HTML + email broadcast of the same blog)
- Same content × multiple file copies (filesystem dups already visible: 2× Biocanic guide, 2× FKSP Call Booked email seq)
- Drafts × revisions
- Source × derivative (audio + transcript + Google Doc summary of one event)

Without a designated canonical source per content domain, we'll ingest near-duplicates and pollute retrieval.

**Deliverable:** `docs/CONTENT_SOURCES.md` mapping content domain → canonical Drive folder(s) → file forms to ingest vs. skip.

Dan decides the mappings; Claude documents. Becomes the input to selection decisions for any subsequent bulk ingestion.

**Estimated effort (actual s28):** ~2hr conversation + doc drafting, spanning 3 doc versions (v1 original → v2 after Dan corrections → v3 slim pass).

---

### 36. April-May 2023 Blogs.docx commit — ✅ RESOLVED session 28-extended (superseded by #56 HTML pipeline)
**Priority:** Closed.

**Closure (s28-extended):** `docs/CONTENT_SOURCES.md` Domain 1 (s28) assigned HTML as the canonical source for blog posts, not docx. #56 (s28-extended) shipped the HTML pipeline via WordPress REST API. Same blog content is available through that pipeline. The April-May 2023 Blogs.docx is a manual docx export of one of the monthly Google Doc compilations; ingesting it would introduce duplicate content in a non-canonical form. **Do not commit this docx.** Pilot record at `data/ingest_runs/e1f02930bb104928.dry_run.json` retained for history.

**Original scope text (kept as history for anyone cross-referencing):**

Session 18 successfully dry-ran the docx handler against `April-May 2023 Blogs.docx` (file_id `1IjhVUc6Px8II4FH0PsMJlOvNX01E6S1-`, 7 chunks projected, all clean and locator-populated). The commit was deferred at the halt-before-commit gate because the same blog content exists in at least three forms (docx, published HTML on website, email broadcasts) and we hadn't decided which form is canonical.



## NEW — added session 19

### 37. Stage 1 (pre-extraction md5) dedup — RESOLVED session 20
**Priority:** Closed.

**Closure (session 20):** Shipped via M-37-α design (Chroma client instantiated at the top of `run()` rather than deferred to commit branch). Stage-1 dedup check now runs inside the per-file dispatch loop, before `_dispatch_file()`. When a file's Drive `md5Checksum` matches an existing chunk's `source_file_md5` under a different `file_id` in the target collection, extraction is skipped entirely (saves Drive download + handler work).

**Files touched:**
- `ingester/loaders/drive_loader_v3.py` — added `_check_md5_dedup()` helper alongside `_check_dedup`; moved Chroma client init from line 876 (commit branch) to right after `assert_local_chroma_path()`; added `_get_collection_for_dedup()` lazy cache (returns None for first-ingest case); added stage-1 block to dispatch loop; added `stage1_dedup_skips` to run summary + run record JSON.
- `scripts/test_dedup_synthetic_s19.py` — extended to 15/15 (was 10/10): added 5 stage-1 unit tests (empty collection, match, self-match, empty md5 / Google Doc case, exception handling).
- `scripts/test_stage1_dedup_wiring_s20.py` — NEW, 4/4 PASS. Replicated-block tests in the s19 "drift audit by replicated-block test beats live Chroma audit" pattern. Verifies dispatch-loop call signature matches helper signature, skip record shape, Google Doc bypass, missing-collection bypass.

**Architectural note (M-37-α):** The "dry-run never touches Chroma" rule was a heuristic for "no writes, no cost." Read-only `collection.get()` queries have no side effects and complete in milliseconds — preserved the rule's intent while enabling stage-1. As a side benefit, dry-runs can now also surface stage-2 dedup hits as a preview (zero new code in stage-2 needed).

**Why dry-run currently shows zero stage-1 skips:** the 8 existing v3 chunks (committed sessions 16/17, before s19) have no `source_file_md5` populated. Stage-1 has nothing to match against until #39 (backfill of s19 metadata fields on existing chunks) runs. The synthetic + wiring tests prove the logic works against simulated md5-populated collections.

**v3 dry-run regression:** byte-identical to session 19 baseline (3 files, 9 chunks, est_tokens 7,603, $0.0010, vision cache hit). No regression. Backup at `ingester/loaders/drive_loader_v3.py.s20-backup`.

---

### 38. Live A/B retrieval-similarity test on Sugar Swaps Canva strip — RESOLVED session 20
**Priority:** Closed.

**Closure (session 20):** Shipped via `scripts/test_canva_strip_ab_live_s20.py` using method M-38-x.2 (apply `_strip_editor_metadata()` directly to the existing Chroma chunk text rather than re-extract from Drive). Read-only against Chroma, no writes. Spend: $0.000227 (8 inputs batched into one OpenAI embedding call).

**Result — clean directional signal in both directions:**

Topical queries (expected strip-ON ≥ strip-OFF):
- "sugar substitutes for fertility"      0.5326 → 0.5865  (+10.1%)
- "how does sugar affect hormones"       0.3875 → 0.4320  (+11.5%)
- "low glycemic foods for egg quality"   0.4403 → 0.4911  (+11.5%)

Pollution-adjacent queries (expected strip-ON < strip-OFF):
- "canva design template"                0.2808 → 0.1839  (−34.5%)
- "page 1 cover layout"                  0.3647 → 0.2357  (−35.4%)
- "how to edit a canva document"         0.2401 → 0.1725  (−28.1%)

Strip removed 192 chars / 7 words from the Sugar Swaps chunk (Canva URL line + `COVER:` tag at the head). Honest n=1 caveat in script output: directional only, corroborates the 15/15 synthetic tests with live similarity numbers.

**BACKLOG #29 now fully closed** (was code-resolved s19, A/B-deferred). The strip's quality benefit is empirically verified.

**Open follow-on:** the strip-ON version isn't in Chroma yet — the Sugar Swaps chunk in production still has the pollution. Re-ingest happens whenever #39 (backfill) runs.

---

### 39. Backfill new s19 metadata fields on existing v3 chunks — RESOLVED session 21
**Priority:** Closed.

**Closure (session 21):** Re-ingested the 8 existing v3 chunks via `drive_loader_v3 --commit` against a 2-file selection_state (Egg Health Guide PDF + Sugar Swaps Google Doc). Pure upsert in place: count 605 → 605, no orphans (chunk-ID determinism verified pre-flight via `_drive_common.py:234`). Result: `extraction_method`, `library_name`, `content_hash` populated 8/8; `source_file_md5` populated 7/8 (Google Doc has no Drive md5 by API design — uses `content_hash` for stage-2 dedup per #37 closure). Sugar Swaps chunk now strip-ON in production (canva.com URL + COVER tag removed, 195 chars stripped). Empirical A/B re-verification (`scripts/verify_sugar_strip_in_production_s21.py`) confirmed production retrieval matches s20 strip-ON winner — all 6 query similarities within ±0.02 of s20 reference. Spend: $0.0009 commit + $0.0001 verify. Pre-write snapshots: `data/snapshots/v3_chunks_pre_s21_n39.json` (chunk-level JSON, 42 KB, retained) + `chroma_db_backup_pre_s21_n39/` (full directory, 484 MB, deleted at session close per Dan).

**Original scope (now historical):**

**Scope:** Session 19 added four new metadata fields to the v3 per-chunk metadata builder:
- `library_name` (canonical alias of `source_collection`, #30)
- `extraction_method` (canonical alias of `v3_extraction_method`, #30)
- `source_file_md5` (Drive md5Checksum, #23 stage-1 plumbing)
- `content_hash` (post-extraction stitched_text SHA256, #23 stage-2)

Per Dan's session-19 directive (no Chroma writes), the 8 existing v3 chunks (7 PDF + 1 v2_google_doc as of session 17) were NOT backfilled. They still have only the deprecated keys. New chunks written from session 20+ onward will have all four fields populated.

**Action when resumed:** re-ingest the 8 existing v3 chunks (DFH folder + Sugar Swaps + Egg Health Guide). Upsert behavior overwrites in place — no orphans. Spend: ~$0.001 embeddings.

**Bundle with:** any session that runs a full v3 commit on these files for other reasons (e.g., when Sugar Swaps gets re-ingested with the Canva strip applied).


---

## NEW — added session 25

### 40. Encourage (not require) link-surfacing in coaching agent responses
**Priority:** Low-Medium. Dan-directed s25. Quality polish, not a blocker.

**Background (s25 A/B observation):** The coaching YAML currently says *"When a Link is shown in context, offer it to the client if they might want to read the full guide."* In the s25 live A/B, 0/4 treatment responses surfaced the Drive link even when a linked chunk was in context. C2 specifically had the Egg Health Guide link + pp. 8-10 locator in retrieval and cited the page but not the link. The "if they might want to" hedge is interpreted strictly — model only surfaces links when the client explicitly signals interest in deeper reading.

**Dan's directive:** encourage link-surfacing more in coaching, but don't make it mandatory. The sales agent stays light-touch; this change is coaching-only.

**Three candidate YAML text changes, weakest → strongest:**

1. **Soft nudge.** Replace the current line with: *"When you cite a source that has a Link, include the Link at the end of your citation so the client can explore if useful."* Shift from "only when warranted" to "default include." Lowest risk; still leaves the model room to skip when truly off-topic.

2. **Structural suggestion.** Add an explicit pattern: *"If your response draws from a source with a Link, close with a one-line 'For the full guide: [Link]' note."* More directive; harder for the model to ignore. Risk: may become formulaic across responses.

3. **Display-layer change (not YAML).** Edit `rag_server/display.py` so every chunk with a Link renders `[Full guide: {link}]` inline in the Source line. The model sees it as part of source block formatting, not as a behavioral instruction. Highest reliability, but crosses into `display.py` territory (s24 delivery — currently in the "don't touch unless a BACKLOG item directs" list; THIS item would be that directive).

**Recommendation:** start with Option 1 (soft nudge) — smallest change, YAML-only, reversible in seconds if it degrades voice. Escalate to Option 2 only if A/B shows 1 doesn't move the dial. Option 3 is reserved for "both YAML approaches fail" scenario.

**Required validation:** live A/B re-run (same shape as s25). 4 queries, 2 conditions (current YAML vs Option 1), focus on C1/C2 coaching queries. Verify (a) link-surfacing rate goes from 0/n to >0.5n in C-cases where a link is present, (b) sales voice unchanged (if YAML shared keys shift, unlikely in Option 1), (c) no new drift markers (emoji, tone shift, over-citation). **Estimated cost: ~$0.20-0.30** per the s25 cost-floor rule.

**Anti-scope:** do not modify sales citation_instructions. Do not add new schema fields. Do not touch display.py unless Option 3 is explicitly escalated to.

**When:** any session where Dan has budget for ~$0.25 live A/B and ~1hr of execution. Not HIGH priority vs #35; bundle with another coaching-quality polish if one surfaces.

**Estimated effort:** ~45 min YAML edit + run A/B + diff responses + update BACKLOG entry. Total spend ~$0.25-0.30.

---

### 41. Emoji-in-sales-response drift marker (watch, don't fix)
**Priority:** Observation only. Log-forward, not a task.

**Background (s25 A/B):** Sales treatment response for S2 ("Any advice on reducing sugar for fertility?") ended with a trailing `🙂` emoji. Baseline response for the same query did not. Single occurrence across 4 treatment responses in the s25 run.

**Why logged:** Reimagined Health brand voice is warm-but-professional (Santorini script, copper/ivory/navy, Dr. Nashat as clinical authority). Trailing emoji isn't catastrophic but it's not the register. Possible cause: citation_instructions YAML's "warm, don't interrupt flow" guidance may inadvertently nudge toward casual markers.

**Drift-marker convention (established s25):** observations that might become problems but haven't yet live in HANDOVER / BACKLOG as markers, not tasks. Threshold for promotion to task: **three independent occurrences** of the same drift pattern across separate runs or real production responses. Until then, just watch.

**When to revisit:** automatically check emoji presence in any future sales-agent A/B or /chat smoke test. If 2+ additional emoji occurrences surface, promote this item to a YAML-tuning task (Option: remove or tighten "warm" language in sales citation_instructions; re-run A/B).

**Current count:** 1 occurrence (s25 S2 treatment).

**Anti-scope:** do not edit YAML pre-emptively on n=1.

**Estimated effort (if promoted):** ~30 min YAML adjustment + A/B re-run on sales queries only, ~$0.15 spend.

---

## NEW — added session 26 (2026-04-16, governance reset)

### 42. Railway sync backlog (s21–s25 local changes not in production) — ✅ RESOLVED session 28
**Priority:** Closed.

**Closure (session 28):** Railway chroma synced via Z1 tarball-bootstrap playbook. Pre-sync Railway probe confirmed stale state (rf_reference_library=584, v3 chunks=0, Sugar Swaps missing — the April-9 Phase-3 baseline). Post-sync verification matches local byte-for-byte: 605 / 9224 / 8 v3 (7 pdf + 1 v2_google_doc) / Sugar Swaps len=3737 strip-ON, no canva, no COVER. Railway rag_server log at 16:36:32 UTC confirms `loaded collection 'rf_reference_library': 605 chunks`. Production smoke not required — rag_server startup chunk count is the authoritative signal.

**Execution (what actually happened):**
1. Built 485MB tarball locally (`tar cf /tmp/chroma_db.tar --exclude='.DS_Store' chroma_db/`, 508040704 bytes — matches Phase-3 baseline exactly).
2. Served via `python3 -m http.server 8000` + `cloudflared tunnel --url http://127.0.0.1:8000` — tunnel URL `rear-poison-trackbacks-secretary.trycloudflare.com` (now dead).
3. Verified tunnel end-to-end with `curl -sI` (HTTP/2 200, content-length 508040704, HEAD logged by python http.server).
4. Cleared Railway `/data/chroma_db` via `railway ssh`. Note: deletion left a harmless macOS `._chroma_db` AppleDouble artifact at `/data/._chroma_db`; bootstrap guard checks for subdirs inside `/data/chroma_db` so the artifact doesn't interfere.
5. `railway variables --set "CHROMA_BOOTSTRAP_URL=<tunnel>"` auto-triggered a redeploy (building 11:23:05 local, success at 16:36).
6. Bootstrap logs confirmed: `download complete (485M), extracting… chroma_db extracted: 485M, 55 files`. 55 files matches the Phase-3 baseline in `HANDOVER_PHASE3_COMPLETE.md`.
7. Deleted `CHROMA_BOOTSTRAP_URL` from Railway variables (bootstrap guard path now safe: next redeploy will hit `chroma_db already populated, leaving alone`).
8. Local cleanup: killed cloudflared + python http.server, `rm /tmp/chroma_db.tar`.

**Probe script retained:** `/tmp/rf_s28_railway_chroma_probe.py` on Mac, `/tmp/rf_s28_probe.py` on Railway container. These are ephemeral (`/tmp` on both sides) and will be cleaned up by OS/container restart. Not promoted to `scripts/` because the logic is trivially re-derivable from CURRENT STATE assertions.

**Spend:** $0 (no LLM calls). Railway compute rounding-error. Tarball transfer via free trycloudflare tunnel was the bottleneck — ~12 minutes wall clock for the 508MB download at ~1MB/s.

**Historical scope (what was synced):**

- **s21:** 8 v3 chunks backfilled with s19 metadata fields (`extraction_method`, `library_name`, `content_hash`, `source_file_md5`). Sugar Swaps Google Doc chunk re-ingested with Canva strip-ON (empirically verified matches s20 A/B winner).
- **s24:** `rag_server/display.py` canonical renderer (NEW, 260 lines). `rag_server/app.py` migrated to wrapper pattern. `config/schema.py` extended with `Behavior.citation_instructions` + `Knowledge.render`. Both agent YAMLs (`nashat_sales.yaml`, `nashat_coaching.yaml`) updated with `citation_instructions` text + per-collection `render` blocks.
- **s25:** No code changes (A/B validation run only). Script `test_citation_instructions_ab_live_s25.py` retained for on-demand re-validation. YAML citation text verified ship-as-is.

**Lessons carried forward:**
- Free trycloudflare tunnels are ~1MB/s, which dominates the wall-clock budget for a 485MB sync. Time-boxing future syncs should assume ~15min for tunnel-based transfers.
- `set -euo pipefail` in `bootstrap.sh` + the `if curl …; then` pattern handles curl retry-and-fail correctly; the 3-attempt retry with 5s delay did not trigger during s28 (first download succeeded).
- Railway CLI quirks: `variables --set` auto-triggers redeploy (desirable here), but `variables delete` does not (also desirable — avoids unnecessary churn). `redeploy --yes` returns "cannot be redeployed" while a build is in progress; it's not an error, just wait.
- Code was already on Railway at commit `4ffbfe4` from a prior-session ghost-push (per s27 HANDOVER); this sync only needed to address the chroma data plane, not code. Future syncs should decouple code sync (git push) from data sync (tarball bootstrap) in the same way.

---

### 43. Phase 3.5 `ruamel.yaml` fix in `admin_ui/forms.py` (pre-Dr.-Nashat-sharing blocker) — ✅ RESOLVED session 27 (already-resolved, verified)

**Resolution (s27):** Reality check on session open found `admin_ui/forms.py` **already uses `ruamel.yaml` in round-trip mode** (`YAML(typ="rt")`, `preserve_quotes=True`, `width=4096`). There is no `yaml.safe_dump` call anywhere in the codebase. The fix described below was done at some prior session without being logged as a #43-equivalent closure; s26 added this item on a misread of code state.

**Verification test ran s27** (`/tmp/rf_s27_b0_yaml_roundtrip.py`, not retained in repo): load-dump-reload cycle against both agent YAMLs. Result: **both `nashat_sales.yaml` (13,871 bytes, 259 lines) and `nashat_coaching.yaml` (15,130 bytes, 297 lines) round-trip byte-identical.** `behavior.citation_instructions` preserved exactly (sales 468 chars, coaching 574 chars — matches CURRENT STATE assertions). Parsed structure identical across round-trip.

**Unblocks:** #42 (Railway sync) may proceed without this work.

**Original scope text (kept as history for anyone cross-referencing):**

**Priority:** HIGH if Dr. Nashat is about to touch the Railway URL. Medium otherwise.

**Scope:** `admin_ui/forms.py` currently uses PyYAML's `yaml.safe_dump` to serialize YAML back to disk after edits in the admin UI. Two problems:

1. **Strips comments.** Any human-authored commentary in the agent YAMLs is silently lost on first save.
2. **Can corrupt multi-line strings.** The s24 `citation_instructions` field on both agents is ~470–580 chars of multi-line text. `yaml.safe_dump` has been observed to emit these in formats that don't round-trip cleanly (one prior incident corrupted `nashat_coaching.yaml`, caught and reverted before committing). With s24 citation_instructions in place, this risk is now live on every YAML save.

**Fix:** swap `yaml.safe_dump` → `ruamel.yaml` round-trip API (`YAML(typ='rt')`). Preserves comments, preserves multi-line string formatting, preserves key ordering. Standard substitution; ruamel.yaml is already a transitive dep of a few packages in the stack.

**Files touched:**
- `admin_ui/forms.py` — swap the dump call; update any load call that needs to match
- `requirements.txt` — pin `ruamel.yaml` explicitly (currently transitive)
- New test: `scripts/test_yaml_roundtrip_s<N>.py` — load both agent YAMLs, dump via new path, re-load, assert equality of parsed structure AND presence of the multi-line citation_instructions field formatted correctly

**Anti-scope:** do not refactor adjacent form-handling logic. Pure library swap.

**Estimated effort:** ~45 min including the round-trip test. Spend: $0.

**Required before:** BACKLOG #42 (Railway sync) — the sync will ship the s24 citation_instructions to production, at which point Dr. Nashat saving either YAML via the admin UI could trigger the corruption path. Do #43 first, then #42.



## NEW — added session 28 (from #35 CONTENT_SOURCES.md follow-up seed list)

The full 28-item seed list lives in `docs/CONTENT_SOURCES.md`. The entries below are the highest-priority subset promoted to BACKLOG for s29+ scope consideration. The rest remain in the CONTENT_SOURCES doc and can be promoted here ad-hoc as priorities shift.

### 44. Create `rf_published_content` collection + migrate misplaced chunks — ✅ RESOLVED session 28-extended
**Priority:** Closed.

**Closure (s28-extended, 2026-04-17):** Migration executed via `scripts/migrate_s28_published_content_s29.py --commit`. Inventory finding: **all 8 v3 chunks were OUR content** (not external) — 7 `Egg Health Guide.pdf` chunks (the `[RF] Optimizing Egg Health Guide & Checklist` lead magnet) + 1 `[RH] The Fertility-Smart Sugar Swap Guide` chunk. All 8 migrated to `rf_published_content`.

**Verification (internal + external):**
- rf_reference_library: 605 → **597** chunks (clean delta)
- rf_published_content: 0 → **8** chunks (new collection)
- rf_coaching_transcripts: 9,224 (unchanged)
- Conservation: 597 + 8 = 605 ✓ (no data loss)
- v3 chunks remaining in rf_reference_library: 0 ✓
- Category breakdown in rf_published_content: 7 pdf + 1 v2_google_doc ✓
- library_name metadata updated: all 8 chunks now `library_name="rf_published_content"` ✓
- Sugar Swaps preserved: len=3737, no canva, no COVER (strip-ON property preserved across migration) ✓
- Embedding preservation: query "sugar alternatives for fertility" → Sugar Swaps chunk as top hit with distance 0.3692 (working similarity) ✓
- Regression suite: 14/14 test scripts still passing post-migration ✓

**Execution details:**
- New collection created with `OpenAIEmbeddingFunction(model="text-embedding-3-large")` — matches `rf_reference_library` embedding function exactly, so stored vectors stay comparable across collections.
- Chunks pulled with `include=["embeddings", "metadatas", "documents"]` to preserve vectors without re-embedding (zero embedding cost, zero similarity drift).
- Metadata update: `library_name` field changed from `rf_reference_library` → `rf_published_content` on each of the 8 chunks.
- Upsert to destination, then delete from source — halt-and-verify between steps in the script so failed verify aborts before the delete. Script's internal verification + external fresh-client probe both passed.

**Spend:** $0 (zero LLM calls, zero new embeddings — existing vectors reused).

**Files touched:**
- `scripts/migrate_s28_published_content_s29.py` — NEW, migration script with dry-run default + --commit flag
- `chroma_db/*` — 8 chunks moved between collections (API-mediated)

**Follow-up not done in this scope:** Sugar Swaps is still in its Google Doc form (v3_category=v2_google_doc). Per Domain 2 canonical decision in CONTENT_SOURCES.md, the PDF form should eventually replace the Google Doc form. That's a separate v3 re-ingestion task against the Sugar Swaps PDF file — tracked as a new BACKLOG item below (#73).

**Unblocks:** Domain 1 (Blogs), Domain 2 (Lead magnets), Domain 3 (Email sequences) target-collection prerequisites are now met. First file-processing handler work (#56 HTML handler) can now proceed.

### 45. Remove stale `client_rfids` from `rf_coaching_transcripts`
**Priority:** MEDIUM. Tactical cleanup flagged in CONTENT_SOURCES.md Framing section.

**Scope:** The `client_rfids` metadata field on existing `rf_coaching_transcripts` chunks contains values from an unfinished RFID system. These values are not usable for retrieval/linkage in their current state. Remove the field from all 9,224 chunks. When the RFID system is finalized (future work), re-populate via a dedicated backfill.

**Anti-scope:** do not re-ingest transcript content. Metadata-field removal only via Chroma upsert-with-metadata-minus-field pattern.

**Estimated effort:** ~30 min. Include a verification probe showing zero chunks retain `client_rfids` after run.

### 46. Per-item review-and-select admin UI workflow
**Priority:** MEDIUM-HIGH. Unblocks Domains 4c (sales playbook), 7a (1:1 zoom reconcile), 8a (zoom categorization) per CONTENT_SOURCES.md.

**Scope:** Extend the admin UI beyond folder/file selection-only to support per-item review workflows where Dan must inspect individual files before marking them canonical or out. Needed for: FKSP Call Research (85 files), Curated Sales Call List (22 files), the 551 Christina+Nashat zoom recordings after intelligent-scan classification.

**Deliverables:**
- Per-file preview surface (file metadata + summary + optional LLM preview of content)
- "Accept / Reject / Defer" buttons per item
- Persists decisions alongside existing `selection_state.json`
- Batch review mode for large folders

**Anti-scope:** do not redesign the existing folder-level selection (that's #21). Add per-item as a new lane, not a replacement.

**Estimated effort:** ~3-4 hr design + build. Scope a tight vertical slice first.

### 47. Multi-modal ingestion handler (slide + transcript alignment)
**Priority:** MEDIUM-HIGH. Unblocks Domains 5b (coaching visuals), 5c (Kajabi curriculum lesson videos), 11a (masterclasses) per CONTENT_SOURCES.md.

**Scope:** Build an ingestion handler that processes video content with either (a) slide-deck source available — align PPTX slides with voiceover transcript (Option β, preferred, cheaper, more accurate), or (b) no slide source — frame-capture at scene changes + OCR (Option α, fallback).

**Gating:** accuracy is non-negotiable — this unblocks the RF 2.0 BBT-trends feature which depends on correct visual extraction.

**Estimated effort:** LARGE. Scope design session required before any build. Cost model for frame extraction + OCR per minute of video needed as input.

### 48. Intelligent-scan classifier for zoom recordings
**Priority:** MEDIUM. Gate for Domain 8a per CONTENT_SOURCES.md (551 recordings to categorize).

**Scope:** LLM classifier that categorizes each zoom recording (coaching / sales / marketing / business-ops / unknown) based on transcript content + filename. Business-ops auto-skip; unknown flagged for Dan review. Output feeds into #46 per-item workflow.

**Estimated effort:** ~2 hr once transcript-per-recording is available. Needs cost estimate against 551 × avg transcript length.

### 49. Two-tier access decision — content-creation-tier vs client-facing-tier
**Priority:** MEDIUM. Gate for Domain 9 per CONTENT_SOURCES.md. Dan decision needed before implementation.

**Scope:** Decide whether to introduce a `rf_internal_knowledge` collection retrievable only by internal content-creation agents (Dan/Nashat/team), never by client-facing agents. Specific content pending this decision: EHT Summit Blueprints, strategic frameworks, internal playbooks in `1-operations/`.

**Implementation sketch (if approved):** YAML allow-list of collections per agent — same mechanism as current per-agent per-collection rendering. Low-complexity extension.

**Estimated effort:** ~15 min Dan decision conversation; if yes, ~1 hr schema + agent-config plumbing.



## NEW — added session 28 close (remaining 23 seeds promoted from CONTENT_SOURCES.md)

Entries below are the remaining follow-up seeds from `docs/CONTENT_SOURCES.md` promoted to proper BACKLOG entries. Collectively they cover collection creation, file-processing handlers, discovery tasks, and design decisions needed to execute against the domain map.

## ⚠ s28 scope F drift-recovery note on #50–#55

Items #50–#55 below were opened in s28 scope C as "create new collection" BACKLOG entries. On s28 scope F drift analysis against ADR_001–006, these are misdiagnosed — the proposed "collections" are **libraries within existing 4 collections** per ADR_002, not new Chroma collections. See `docs/2026-04-17-drift-recovery-s28.md` and `ADR_002_continuous_diff_and_registry.md` §"Starter library list" (15 starter libraries).

Correct mapping (applied in s29-A.3):
- #50 `rf_curriculum_paywalled` → supersedes as **ADR_002's `rf_internal_education` collection**, with libraries `fksp_curriculum`, `fertility_formula_curriculum`, `preconception_detox_curriculum`, `fksp_coaching_calls`, etc. Master plan Sessions 2-4 build this.
- #51 `rf_sales_playbook` → supersedes as **libraries within `rf_published_content`**: `nashat_dms` (ADR_002 starter) + future libraries for sales-call transcripts. Not a new collection.
- #52 `rf_marketing` → supersedes as libraries within `rf_published_content`: `masterclass_recordings` (ADR_002 starter) + future library for funnel copy. Not a new collection.
- #53 `rf_testimonials` → multi-modal testimonial assets could be a new library within `rf_published_content` (e.g., `testimonials`). Not a new collection.
- #54 `rf_visual_library` → supersedes as `canva_design_library` (ADR_002 starter, Reference tier) and/or `ig_content` (ADR_002 starter, Published tier). Not a new collection.
- #55 `rf_lab_data` → needs a new ADR; if it's client-specific clinical data, belongs in the **clinical tier** (reserved in ADR_002, no libraries today). If it's educational about labs, belongs in `rf_reference_library` or `rf_internal_education`.

**Triage in s29-A.3:** close #50–#55 as `SUPERSEDED BY ADR_002`. Open new library-creation items as needed.

---

### 50. Create `rf_curriculum_paywalled` collection — ⚠ SUPERSEDED BY ADR_002 (s28 scope F)
**Priority:** MEDIUM. Gate for Domains 4a / 4d / 5c / 7d ingestion.
**Scope:** Create the Chroma collection. Gated on paywall-access-enforcement design (ties to #46 per-item review + #49 two-tier access + possibly #69 TFF client-access screening). Also see #70 naming decision (single vs split for text-vs-multimodal).
**Effort:** ~30 min collection creation + schema metadata fields; longer if access enforcement bundled.

### 51. Create `rf_sales_playbook` collection — ⚠ SUPERSEDED BY ADR_002 (s28 scope F)
**Priority:** MEDIUM. Gate for Domain 4c.
**Scope:** Create the Chroma collection. Gated on IG DMs export pipeline (#58) + sales-call source discovery (#63) + per-item review workflow (#46).
**Effort:** ~30 min collection creation; handler work separate.

### 52. Create `rf_marketing` collection — ⚠ SUPERSEDED BY ADR_002 (s28 scope F)
**Priority:** MEDIUM. Gate for Domain 11 (masterclasses, Meet & Greet, Funnels copy, RF Meet the Doctors).
**Scope:** Create the Chroma collection. Gated on multi-modal handler (#47) for mp4 content + Funnels sub-folder inventory (#67).
**Effort:** ~30 min collection creation.

### 53. Create `rf_testimonials` collection — ⚠ SUPERSEDED BY ADR_002 (s28 scope F)
**Priority:** MEDIUM. Gate for Domain 11b.
**Scope:** Split from `rf_marketing` because multi-modal (images + videos + screenshots + text extractions) and distinct retrieval intent (sales-agent closing patterns, content-creation surfaces, website/Shopify pieces).
**Effort:** ~30 min collection creation; gated on testimonial handler #61 + 3-marketing sub-folder inventory #67.

### 54. Create `rf_visual_library` collection — ⚠ SUPERSEDED BY ADR_002 (s28 scope F)
**Priority:** MEDIUM. Gate for Domain 14.
**Scope:** Separate from `rf_marketing` because visual-library retrieval intent is "find a polished visual to reuse," marketing is "find teaching/copy content." Gated on IG archive export (#60) + Canva export (#59).
**Effort:** ~30 min collection creation.

### 55. Create `rf_lab_data` + design client-lab-upload intake pipeline — ⚠ SUPERSEDED BY ADR_002 (s28 scope F)
**Priority:** MEDIUM-HIGH. Gate for Domain 13 (lab data library — Biocanic + client-provided).
**Scope:** Create the Chroma collection. Design the admin-UI upload surface for clients to share labs directly (uploads, shared in coaching calls, emailed in). Includes a PDF lab-report parser for common lab formats (Quest, LabCorp, Biocanic PDF exports). PII handling consistent with Domain 4b hardcoded-protected metadata pattern.
**Effort:** Collection creation ~30 min; upload UI + parser ~1-2 days depending on lab-format coverage.

### 56. HTML handler + blog export pipeline — ✅ RESOLVED session 28-extended (code+smoke; bulk deferred to #75)
**Priority:** Closed (code + smoke). Bulk ingestion deferred to #75.

**Closure (s28-extended, 2026-04-17):**

**Architecture decision:** built as a **parallel ingester** (`ingester/blog_loader.py`), not a v3 file-type handler, because the source is the WordPress REST API (not Drive). Reuses v3's commit-path infrastructure: same `OpenAIEmbeddingFunction(text-embedding-3-large)`, same `chunk_with_locators` (scrub Layer B runs automatically), same `_compute_content_hash` + `_check_dedup` stage-2 dedup, same `assert_local_chroma_path` guard.

**Source-strategy decision:** WP REST API at `https://drnashatlatib.com/wp-json/wp/v2/posts`. Discovery findings: site is WordPress behind Cloudflare with Yoast SEO sitemap; 81 total blog posts available; REST returns structured JSON with title, content.rendered, date, modified, link, categories, tags, author. Cleaner than HTML scraping because `content.rendered` strips template chrome already. This deviates from the original scope text (live-scrape / WordPress-export / Kajabi-backup) in favor of the best-available pipeline discovered in s28-extended.

**Files shipped:**
- `ingester/blog_loader.py` — NEW, 411 lines. CLI: `--site`, `--library`, `--limit`, `--commit`. Dry-run default. Writes run records to `data/ingest_runs/<run_id>.(dry_run|).json` and appends to `data/audit.jsonl`. Chunk-ID namespace: `wp:<host>:<post_id>:<chunk_index>`.
- `scripts/test_blog_loader_synthetic.py` — NEW, 23 unit tests (HTML stripping, shortcodes, images, nested divs, metadata builder, chunk-ID builder, md5 determinism). All passing.

**Verification:**
- Synthetic tests: **23/23 passing**
- Full regression suite: **15/15 test scripts passing** (14 existing + new `test_blog_loader_synthetic.py`)
- Single-post dry-run (Indoor Air Pollution post 18885): 5 chunks, $0.000618
- Single-post `--commit`: rf_published_content 8 → 13 chunks. Fresh-client probe confirms chunk IDs, metadata (wp_post_id, slug, canonical_url, categories, author all resolved), content_hash, display fields all correctly populated.
- Query sanity: "indoor air pollution fertility" → blog chunks top 3 hits (distance 0.2339). Non-blog query ("sugar alternatives for fertility") → Sugar Swaps top hit (distance 0.3692, unchanged from pre-#44 baseline — no regression).
- Full-corpus dry-run (all 81 posts): 277 chunks, 994,152 chars, est $0.032. Zero errors, zero edge cases across 2+ years of blog content.

**Bulk ingestion deferred (scope discipline):**
Per Dan s28-extended: "We are currently building not going live. Is it good to do this now, or better later when we have full functionality." Agreed to defer. Reasoning:
- No agent currently retrieves from `rf_published_content` — ingesting 277 chunks would be write-only until agent YAML is updated
- Content-quality validation at n=1; 80 more unknowns
- Cross-domain dedup with email content (Domain 3) not designed yet — bulk now + email later produces cross-collection near-duplicates
- Schema may evolve (featured image, author bio, reading time, etc.)
- Pipeline validation complete at n=1; architecture is proven

Bulk run tracked as **#75** — fires when a consumer exists or content-quality/dedup validation completes.

**Spend:** $0.000618 (one single-post commit via OpenAI text-embedding-3-large).

**Unblocks:** Domain 1 canonical ingestion now has working pipeline. Domain 3 Email sequences can reuse the BeautifulSoup extraction helper. #36 (April-May 2023 Blogs.docx) resolved by this scope — canonical is HTML via this pipeline, not docx; #36 closed as superseded.

### 57. Email platform export mechanism — ✅ RESOLVED session 28-extended (code+smoke; AC only; GHL + AC bulk deferred)
**Priority:** Closed (AC code + smoke). See #76 (GHL deferred) and #78 (AC bulk deferred).

**Closure (s28-extended, 2026-04-17):**

Dan confirmed authoritative email platforms are **ActiveCampaign (older)** + **GoHighLevel (newer, migrating to)**. Built ActiveCampaign ingestion pipeline this session; GHL is blocked on API capability and deferred to #76.

**Architectural decisions:**

- **Classifier-gated ingestion as core infra (not email-specific).** Per Dan s28: "per our design we will update the RAG from time to time and the diff will be added. all emails, like new ig posts, and blogs, etc. will need to be put in. So we want this automated, meaning we should use a cheap llm to classify and choose." Built `ingester/classify.py` — small Haiku-4.5-based binary classifier (MARKETING vs OPERATIONAL vs UNCLEAR). Cached by content-hash to `data/classifier_cache.jsonl` — same content → same verdict → $0 on re-runs. Reusable for future loaders (IG, incremental blog, Zoom recordings via #48, etc.).

- **Parallel ingester pattern** — `ingester/ac_email_loader.py` (411 lines) mirrors `blog_loader.py`. Different source (AC REST v3 `/api/3/messages`), same sink (`rf_published_content`). Reuses v3 embedding + chunk_with_locators (scrub Layer B automatic) + stage-2 content_hash dedup + shared HTML-to-text helper from blog_loader.

- **Chunk ID namespace:** `email-ac:<account>:<message_id>:<chunk_index:04d>` (disambiguates from `wp:` and `drive:`).

- **Date floor:** `cdate >= 2022-01-01` applied server-side via AC filter so pagination skips pre-2022 content.

**Classifier calibration (`scripts/test_classify_live_s28.py`):** 8/8 known samples classified correctly. 4 marketing (Vitamin D blog, welcome kickstart series, sugar-fertility, hormone reset guide) all → MARKETING. 4 operational (unsubscribe confirmation, FKSP kickoff reminder, payment received, password reset) all → OPERATIONAL. Total classifier cost across 8 samples: $0.002661.

**Dry-run against live AC (--limit 10):**
- 1,226 messages in AC since 2022
- Sample: 10 fetched → 3 marketing kept, 7 operational skipped, 0 empty
- Classifier calls correctly flagged stock-template AC emails ("Your unsubscription confirmation", "Update your subscription to %LISTNAME%") as operational, and a "Welcome to 5DC" email that was pure logistics + ToC (no teaching content).

**Single-email --commit (msg=3 "[10 Steps Download Inside] Welcome"):**
- rf_published_content: 13 → 14 chunks (1 new AC chunk)
- Fresh-client probe confirms metadata: `source_pipeline=ac_email_loader`, `v3_category=ac_email`, `ac_message_id=3`, `ac_from_name=Nashat Latib`, `display_source=[10 Steps Download Inside] Welcome`, `content_hash` present, `library_name=rf_published_content`
- Query sanity: "welcome 10 steps download" → AC chunk top hit (distance 0.7036)
- Non-regression: blog query ("indoor air pollution") still top at 0.2339; lead magnet query ("sugar alternatives") still top at 0.3692 (both unchanged)
- Full regression suite: 15/15 test scripts passing

**Protocol diagnosis caught in this scope:** `load_dotenv()` default behavior doesn't override shell-exported env vars. The user's shell exports `ANTHROPIC_API_KEY=""` (empty), which masked the valid `.env` value. **Fix applied:** `load_dotenv(override=True)` in `ingester/classify.py`. All future scripts that read from `.env` should use `override=True` to avoid this trap. Existing `scripts/test_citation_instructions_ab_live_s25.py` may have a latent version of this bug (uses default `load_dotenv()`) — would only bite on re-run; flagged but not urgent.

**Files shipped:**
- `ingester/classify.py` — NEW, ~180 lines. `is_operational(subject, body_preview) → bool` + caching.
- `ingester/ac_email_loader.py` — NEW, ~411 lines. Parallel ingester with classifier integration.
- `scripts/test_classify_live_s28.py` — NEW live-API calibration test (not in regression suite per s25 rule).
- `data/classifier_cache.jsonl` — classifier verdict cache (appends on every new classification).
- `data/ingest_runs/39bd0316f8fb42ae.dry_run.json` — 10-message dry-run record with per-message verdicts.
- `data/ingest_runs/50f08362bd4d4ad0.json` — single-email commit record.

**Spend:** $0.002661 classifier calibration + $0.002329 dry-run 10 classifications + $0.000094 embedding for single-email smoke ≈ **$0.005 total this scope**.

**Deferrals:**
- **AC bulk ingestion** (remaining ~1,225 messages since 2022) → #78. Fires when a consumer exists (agent YAML updated to retrieve from `rf_published_content`) OR cross-domain dedup with blogs (#68) is designed. Projected bulk cost: ~$0.35 total (classifier $0.29 + embeddings $0.05).
- **GHL email ingestion** → #76. Blocked on GHL V2 API capability (no detail endpoint for email bodies).
- **Diff-based incremental ingestion** (the "auto-update on source change" Dan asked about) → #77. Loader-agnostic: per-source cursor state, periodic worker, classifier-filtered.

### 58. IG DMs export mechanism
**Priority:** MEDIUM. Gate for Domain 4c (sales playbook) + partial Domain 14.
**Scope:** Design and build a way to extract Nashat's IG DM conversations (marketing, listening, closing clients). Source: Meta Business Suite export or Instagram Graph API. Output: threaded conversations with timestamps, participant tagging, message types (text, image, reel). Consider rate-limiting and incremental sync.
**Effort:** Discovery ~2 hr; build ~1-2 days; ongoing sync design separate.

### 59. Canva export pipeline
**Priority:** MEDIUM. Gate for Domain 14 (visual library).
**Scope:** Design Canva corporate account export. Likely options: (a) Canva API if available in Nashat's plan, (b) manual download + batch ingestion, (c) browser-automation. Output: polished visuals with metadata (project name, tags, date created).
**Effort:** Discovery ~2 hr; build varies widely by chosen path (~4 hr for manual, ~1 day for API).

### 60. IG posts archive export
**Priority:** MEDIUM. Gate for Domain 14.
**Scope:** Export Nashat's IG account posts (image + caption). Source: Meta Business Suite export or IG Graph API. Overlaps with #58 IG DMs but posts are a separate surface.
**Effort:** ~4-6 hr once Meta Business Suite access established.

### 61. Testimonial multi-modal handler
**Priority:** MEDIUM. Gate for Domain 11b (testimonials).
**Scope:** Handler for testimonial assets — images, videos, screenshots, text extractions. Each form needs different processing: image → OCR + caption metadata; video → transcript + key-frame extraction; screenshot → OCR; text → direct chunk. Outputs single collection with modality metadata.
**Effort:** ~1-2 days; reuses some infrastructure from #47 multi-modal handler.

### 62. PDF polish-check gate
**Priority:** LOW-MEDIUM. Gate for Domain 2 (lead magnets) clean ingestion.
**Scope:** Ensure a PDF being ingested as a lead magnet is a polished final, not an interim shared draft. Options: (a) filename convention check (`[RF] <Name>.pdf` pattern inside `[RF] <Name>/` folder), (b) pre-ingest admin-UI "confirm final" flag per file, (c) visual spot-check workflow with sign-off.
**Effort:** ~2-4 hr depending on chosen path.

### 63. Discovery — find high-close accelerator + prior-salesperson calls
**Priority:** MEDIUM. Gate for Domain 4c sales-playbook content.
**Scope:** Nashat's very-high-close-% fertility-accelerator sales calls + prior-salesperson lower-close-% calls (20-30%) are not in current walked Drives. Likely locations: Taylor's shared drive, other salespeople's personal/shared drives. Request access, walk the structure, add to inventory.
**Effort:** ~1-2 hr per drive once access granted.

### 64. 1-operations sub-folder audit
**Priority:** LOW. Gate for Domain 9 anti-ingestion rollout + #49 two-tier access decision.
**Scope:** Per-sub-folder inspection of `1-operations/`: Masterfiles, SOPS, Training & Tutorials, Systems, Website Development, Teams, Domain Troubleshooting, Critical Numbers, Assets, To Organise. Decide per-folder: client-facing-anti-ingestion / content-creation-tier candidate / skip / unknown.
**Effort:** ~1-2 hr walk + Dan review.

### 65. 6-ideas-planning-research sub-folder audit
**Priority:** LOW. Gate for Domain 10 drive 6 scope.
**Scope:** Per-sub-folder inspection of `6-ideas-planning-research/`: AI Resources, Biz Coaching, Competitive Analyses, Conscious Copy course worksheets, Fertility Group Programs, Konain Funnel Strategies, Recruitment Resources, Reimagined MD, Socialthority Selling System, Yuri P and L. Decide per-folder scope.
**Effort:** ~1 hr walk + Dan review.

### 66. TFF slide-deck source discovery
**Priority:** MEDIUM. Gate for Domain 5c TFF multi-modal re-ingest (#47 specifically for TFF program).
**Scope:** Determine whether TFF has a PPTX slide-deck source analogous to FKSP's 32 PPTX in `10-external-content/Kajabi Backups/1. Fertility Kickstart Program/FKSP Lesson Slides/`. If yes, TFF multi-modal uses Option β (slide-deck alignment). If no, falls back to Option α (frame-capture + OCR).
**Effort:** ~1 hr discovery.

### 67. 3-marketing sub-folder inventory
**Priority:** MEDIUM. Gate for Domain 11b / 11c / 11d.
**Scope:** Walk and surface contents of `3-marketing/9. Testimonials & Case Studies/`, `3. Funnels/`, `11. Summit/`, `8. Collabs/`, `12. Affiliates/`, `6. Facebook Ads/`, `1. Brand Assets/`. Produce per-folder categorization matching domain map.
**Effort:** ~2 hr walk + categorization.

### 68. Cross-domain dedup canonical-beat rules
**Priority:** MEDIUM. Required before Domains 1 + 3 + 11 + 14 ship together.
**Scope:** Design explicit canonical-beat rules for content that authors once but distributes multiple ways. Examples: blog content authored once + emailed (Domain 1 vs 3 overlap), masterclass with blog-worthy teaching (Domain 1 vs 11a overlap), IG post sharing a testimonial (Domain 11b vs 14 overlap). Existing stage-1 md5 + stage-2 content_hash cover trivial cases; need explicit priority rules for lineage-overlap cases.
**Effort:** ~2-4 hr design doc + update to ingester dedup logic.

### 69. TFF client-access screening feature decision
**Priority:** LOW-MEDIUM. Optional feature per Domain 5c note.
**Scope:** Decide whether to implement content screening that filters TFF-paid-only content to TFF-tier clients (not to higher-tier clients who have broader program access, but also not to non-TFF clients who shouldn't see TFF-specific material). Implementation: `program_tier` metadata field + retrieval-layer filter + admin UI per-client entitlement.
**Effort:** ~15 min Dan decision; if yes, ~2-4 hr schema + retrieval filter + admin-UI plumbing.

### 70. Paywalled curriculum collection naming — single vs split
**Priority:** LOW. Gate for #50 (`rf_curriculum_paywalled` creation).
**Scope:** Decide: one collection `rf_curriculum` holds text + multi-modal content with `modality` metadata field, OR two collections `rf_curriculum_text` + `rf_curriculum_multimodal`. Driven by empirical retrieval behavior expected at query time.
**Effort:** ~15 min decision.

### 71. Ingest TFF Program Contracts + cohort spreadsheets
**Priority:** MEDIUM. Operational unblock per Domain 4-OUT reversal.
**Scope:** Previously marked anti-ingestion, reversed s28 per Dan — these records enable client-timeline linkage (lab-test-relative-to-program-phase retrieval, first-name identification on call transcripts). Ingest into `rf_curriculum_paywalled` (or a dedicated client-timeline metadata surface). Hardcoded-protected client-identity fields per Domain 4b pattern.
**Effort:** ~2-4 hr including per-file review, PDF text extraction for contracts, spreadsheet parsing for cohort data.

### 72. Collection-expansion admin UI work
**Priority:** MEDIUM-HIGH. Compounds with #21 (folder-selection UI redesign) + #46 (per-item review workflow).
**Scope:** The admin UI currently assigns folders/files to 2 active collections. When the 11+ collections from CONTENT_SOURCES.md exist, the UI needs: dropdown of all collections with descriptions + tier badges, agent-to-collection allow-list configuration (per #49 two-tier access), per-item review workflow (per #46), PDF polish-check flag (per #62).
**Effort:** ~1-2 full sessions of UI design + build. Treat as one coherent scope with #21.

### 73. Sugar Swaps PDF re-ingest (Domain 2 canonical form correction)
**Priority:** LOW. Opened s28-extended post-#44 migration.
**Scope:** Currently Sugar Swaps is ingested in Google Doc form (`v3_category=v2_google_doc`, len=3737) in `rf_published_content`. Per CONTENT_SOURCES.md Domain 2 canonical decision, lead magnets should be ingested as their PDF form. Re-ingest `[RF] The Fertility-Smart Sugar Swap Guide.pdf` (file_id `1P699Ku6y_8wpxj-` per Drive walk) via v3 pipeline, upsert into `rf_published_content`, remove the Google Doc form chunk.
**Effort:** ~30 min (v3 dry-run → --commit → verify). Zero LLM spend beyond v3's standard embedding cost on one re-ingested file.
**Anti-scope:** do not bundle with other lead-magnet re-ingestions. Single-file sanity test first.

### 74. Railway re-sync after #44 migration
**Priority:** LOW-MEDIUM. Opened s28-extended post-#44.
**Scope:** Post-#44, local has `rf_published_content` (8 chunks) + `rf_reference_library` (597) while Railway still has the pre-migration state (rf_reference_library=605, no rf_published_content). The 8 chunks are present on both sides just in different collections, so retrieval behavior is minimally affected until agents start retrieving from `rf_published_content` specifically. Re-sync Railway via the Z1 tarball-bootstrap playbook (per #42 s28 closure) when the next Railway-touching scope lands — or bundle with a later sync that aggregates multiple local-vs-Railway deltas.
**Effort:** ~15 min monitoring (Z1 playbook is ~12 min download over trycloudflare); or batched with a future sync.
**Anti-scope:** do not re-sync in isolation. Bundle with subsequent migrations or feature work that needs to reach production.

### 75. Bulk blog ingestion (80 remaining posts, deferred from #56)
**Priority:** LOW. Opened s28-extended post-#56 code-ship.
**Scope:** Run `./venv/bin/python -m ingester.blog_loader --site https://drnashatlatib.com --library rf_published_content --commit` to ingest the 80 remaining blog posts (post 18885 / Indoor Air Pollution already committed as single-post smoke in #56). Dry-run shows 277 total chunks expected, ~$0.032 cost.

**Fires when any of:**
- An agent YAML is updated to retrieve from `rf_published_content` (making the chunks consumable — no point ingesting write-only data at scale)
- Cross-domain dedup with email content (#57 + #68) is designed, to avoid introducing cross-collection duplicates when email ingestion follows
- Explicit content-quality validation pass completes on a sample of 10-15 posts (spot-check extraction holds across the 2+ years of blog content, Elementor variations, guest posts, etc.)

**Rollback:** `collection.delete(where={"source_pipeline": "blog_loader"})` via Chroma client — trivial undo.
**Effort:** ~90 seconds wall clock for the commit + verification probe.
**Anti-scope:** do not expand beyond bulk blog commit. Schema evolution, author bio enrichment, featured-image OCR, etc., are separate scopes.

### 76. GHL email ingestion (blocked on V2 API capability)
**Priority:** LOW (blocked). Opened s28-extended post-#57.
**Scope:** GoHighLevel is the platform newer email content is migrating to. Discovery in s28-extended found:
- GHL V2 API (`services.leadconnectorhq.com`) exposes **list endpoints** for workflows (62 found), emails/builder templates (2), campaigns (0 used). Auth scopes broadened to workflow.readonly + emails.readonly + campaigns.readonly + locations.readonly — all list endpoints return 200.
- **But no DETAIL endpoints** that return the email HTML body. `GET /workflows/{id}` → 404. `GET /emails/builder/{id}` → 404. `GET /emails/campaigns` → 401 "This route is not yet supported by the IAM Service." These are known GHL API gaps, not scope issues.
- Conversations endpoint returns 44,955 per-contact threads (mostly SMS/IG); pulling email bodies that way is delivery-event-level, not source-authoring.
**Resolution:** wait for GHL to expose detail endpoints (they're actively developing V2), or explore a manual export path (UI → CSV/HTML), or scrape with browser automation (fragile, TOS risk).
**Unblocks:** Domain 3 newer-era email coverage. AC covers legacy corpus.

### 77. Diff-based incremental ingestion (cross-loader infra)
**Priority:** MEDIUM-HIGH. Opened s28-extended.
**Scope:** Per Dan s28: "per our design we will update the RAG from time to time and the diff will be added. all emails, like new ig posts, and blogs, etc. will need to be put in. So we want this automated." Build a cross-loader incremental-sync pattern:
- Per-source cursor state in `data/ingestion_cursors.json` (e.g. `last_message_cdate` for AC, `last_modified` for WP blog posts, `last_media_id` for IG)
- Each loader gains an `--incremental` mode that reads its cursor, pulls items newer than cursor, classifies + filters + commits, updates cursor on success
- Classifier (already built, #57) runs on every new item; operational ones skipped automatically
- Optional scheduled runner (Railway scheduled job, or local cron): fire each loader daily/weekly

**Effort:** ~1 day to add incremental mode to existing blog_loader + ac_email_loader + cursor state; ~1-2 more days for a scheduled runner. Split into phase 1 (incremental mode per loader, manual trigger) and phase 2 (scheduled automation).
**Depends on:** #57 (done) for classifier infra. Fires when a consumer exists (agent YAML retrieving from rf_published_content).

### 78. Bulk AC email ingestion (deferred from #57)
**Priority:** LOW (defer per build-discipline). Opened s28-extended.
**Scope:** Run `./venv/bin/python -m ingester.ac_email_loader --library rf_published_content --commit` against the full AC corpus (~1,225 remaining messages since 2022; 1 already committed as smoke). Expected breakdown from sample: ~30% marketing kept (~370 messages), ~70% operational skipped.
**Fires when:**
- An agent YAML is updated to retrieve from `rf_published_content` (consumer exists), OR
- Cross-domain dedup with blogs (#68) is designed, OR
- Explicit validation pass over a larger sample confirms classifier accuracy holds beyond the 10-message sample
**Projected spend:** ~$0.29 classifier + ~$0.05 embeddings = **~$0.35 total**. Well under $1 gate.
**Rollback:** `collection.delete(where={"source_pipeline": "ac_email_loader"})`.
**Anti-scope:** do not expand to schema changes, metadata enrichment, or cross-platform dedup during bulk run — those are separate scopes.

---

## NEW — s28 scope F drift-recovery items (s29-A primary scope)

### 79. Rewrite `CONTENT_SOURCES.md` v2.0 — align with ADR_002/005/006 (s29-A.1)
**Priority:** HIGH. First s29 deliverable. Per drift analysis at `docs/2026-04-17-drift-recovery-s28.md`.
**Scope:** Keep the per-domain source-mapping content (blogs → WP REST, emails → AC/GHL, lead magnets as PDFs, etc.) but re-express in ADR_002's 4-collection + 15-library architecture. Add explicit `Supersedes:` headers acknowledging v1.0 (s28). Cross-reference ADRs at every architectural decision. Remove the 13-collection proposal; replace with `collection → library → source` mapping tables.
**Effort:** ~2 hr.
**Unblocks:** all future ingestion work can reference a coherent architecture.

### 80. ADR_006 metadata backfill on 14 committed chunks (s29-A.2)
**Priority:** HIGH. Second s29 deliverable.
**Scope:** Metadata-only Chroma upsert against the 14 chunks in `rf_published_content`. Mirrors #44 migration pattern (pre/post count same, embeddings preserved). Per chunk add: `entry_type` (`published_post`), `origin` (`static_library` provisionally; may become `rest_api` per #82), `tier` (`published`), correct `library_name` (`blog_posts` for 5 blog chunks, `lead_magnets` for 8 Egg-Health+Sugar-Swaps chunks, `nurture_emails` for 1 AC chunk), `source_id` per ADR_002 addendum format, and the **48 boolean marker flags** via regex detection on chunk text.
**Effort:** ~1-2 hr including per-chunk verification.
**Spend:** $0 (no re-embedding).
**Anti-scope:** do not add new chunks; do not re-ingest source material; just metadata backfill.

### 81. Schema fix in `blog_loader.py` + `ac_email_loader.py` — emit ADR_006-compliant metadata (s29-A.4)
**Priority:** HIGH. Third s29 deliverable.
**Scope:** Update both loaders to emit ADR_006's universal chunk schema on new ingestions. Specifically: add `entry_type`, `origin`, `tier`, correct `library_name` (matching ADR_002 starter list), `source_id` per ADR_002 addendum, 48 marker flags via regex detection, ADR_006 `ingested_at` / `chunk_id` / `source_name` aligned field names. After this lands, #75 (bulk blog) and #78 (bulk AC) unblock with compliant schema.
**Effort:** ~1 hr for both loaders + synthetic tests.

### 82. New ADR — define `origin: rest_api` for REST-API-pull ingestion (s29-A.5, conditional)
**Priority:** MEDIUM. Conditional on Dan decision.
**Scope:** ADR_002/005 currently define two origins — `drive_walk` (continuously updated via folder walk + diff) and `static_library` (one-shot curated CLI load). REST-API pulls (blog_loader, ac_email_loader, future ig_post_loader) fit neither cleanly: they're remote-API-driven (not local files like static_library) but also change over time (unlike static). Draft ADR proposing `rest_api` as a third origin value with its own idempotency/diff semantics. Update ADR_002 addendum and ADR_006's origin field documentation in the same commit.
**Effort:** ~1 hr ADR draft. Discussion/decision with Dan.

### 83. BACKLOG re-triage against ADR_002/005/006 (s29-A.3)
**Priority:** HIGH. Fourth s29 deliverable.
**Scope:** Go through BACKLOG items #50-#78 systematically, marking those that conflict with ADR_002/005/006 as SUPERSEDED and re-expressing them as library-creation or field-addition items where appropriate. #50-#55 already flagged in s28-F as superseded; #73, #75, #78 bulk items keep. Review #56-#78 for compliance.
**Effort:** ~30 min.
