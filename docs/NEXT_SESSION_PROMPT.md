# NEXT SESSION PROMPT — session 13

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Sessions 9, 10, 11, and 12 all used a "step 0 reality check" before doing any work. It has paid for itself four sessions in a row — session 11 caught a deprecated SDK import path, session 12 caught that Desktop Commander was half-loaded in the chat. **Keep doing this.**

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all five gates. Stop and tell Dan if anything surprises you.

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible (session 12 hit this — only 3 tools loaded initially), call `tool_search` with a relevant query to force-load the rest. If that still doesn't work, the chat needs Desktop Commander re-enabled in Claude Desktop settings.

2. **Smoke test process execution.** Run `python3 -i`, verify you get a `>>>` prompt, send `print("session 13 ok"); 2+2`.

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -5`. Expected top commit: whatever Dan committed at the end of session 12, OR `84fa22f session 11` if session 12 work was not committed. Session 12 work (scrub module + image review script) may or may not be committed depending on whether Dan ran git between sessions. Either state is fine — just know which.

4. **Reality-vs-prompt check.** Verify these against the actual filesystem before reading the reading list:

   - **Drive auth.** `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"`. Expect `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.**
     ```python
     from google import genai
     c = genai.Client(vertexai=True, project="rf-rag-ingester-493016", location="us-central1")
     r = c.models.generate_content(model="gemini-2.5-flash", contents="Say 'ok' and nothing else.")
     print(r.text)
     ```
     Expected: `ok`.

   - **OCR cache still present.** `ls data/image_ocr_cache/*.json | wc -l` — should be **27**. Dan personally signed off on OCR quality in session 12 via the side-by-side viewer, so session 13 should NOT re-trigger the eyeball gate unless the cache has changed. If cache count differs from 27, stop and ask.

   - **Session 12 scrub module on disk.** `ls ingester/text/scrub.py ingester/text/__init__.py` — both should exist. `ingester/text/scrub.py` should be ~130 lines.

   - **Scrub module still works.** Run the session 12 test battery inline:
     ```python
     import sys; sys.path.insert(0, '.')
     from ingester.text.scrub import scrub_text
     # Critical cases:
     assert scrub_text("by Dr. Nashat Latib & Dr. Christina Massinople")[0] == "by Dr. Nashat Latib"
     assert scrub_text("body mass index")[0] == "body mass index"  # must NOT match
     assert scrub_text("Merry Christmas")[0] == "Merry Christmas"  # must NOT match
     assert scrub_text("Dr. Chris said 500mg")[0] == "Dr. Nashat Latib said 500mg"
     print("scrub core tests: PASS")
     ```

   - **Image review page still viewable.** `ls data/image_samples/index.html` — should exist. Not required for session 13 work, but confirms session 12 artifacts weren't cleaned up.

   - **v1 regression still passes.** `./venv/bin/python -m ingester.loaders.drive_loader --selection-file /tmp/rf_pilot_selection.json --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 --dry-run 2>&1 | tail -15`. Should still report `files ingested: 1`, 2 low-yield skips, 1 unsupported spreadsheet, $0.0001.

   - **Railway alive.** `curl -sI https://console.drnashatlatib.com | head -3`. HTTP/2 302.

If any check returns a surprise, stop and surface it.

---

## What happened in session 12 (critical context)

Session 12 ran Step 0 cleanly, then hit Step 1 (the OCR eyeball gate) and **detoured** on an issue discovered during sample review: one of the cached OCR entries contains "by Dr. Nashat Latib & Dr. Christina Massinople" from the cover page of the Supplement Info docs. Dr. Christina Massinople is Dan's former collaborator and per the RF memory guardrail, her name must never surface in Nashat agent output.

Dan's decision: content stays, name gets scrubbed and reattributed to "Dr. Nashat Latib". Dan also confirmed that "Dr. Chris" (previously in memory as the co-coach) and "Dr. Christina Massinople" are **the same person** — this resolves what had been a two-entry split in memory.

Session 12 built two things to handle this:

1. **A side-by-side image review page** (`scripts/build_image_review.py` + `data/image_samples/index.html`) that lets Dan eyeball the actual product images next to the cached Gemini OCR text. 54 image instances rendered, Dan reviewed and said "that looks awesome" — **OCR quality is signed off**. Session 13 does NOT re-run this gate.

2. **A standalone name-scrub module** at `ingester/text/scrub.py` with 11 rules (ordered most-specific first), a joint-byline dedup pass, and an 18/19-test unit battery. The one failing test is a cosmetic triple-byline edge case ("Dr. Chris, Dr. Christina, and Dr. Massinople" → doesn't fully collapse to a single attribution; leaves an intermediate triple-duplicate). Not blocking — session 13 should add the missing dedup pattern.

**What session 12 did NOT do** — and session 13 must:

- Wire `scrub_text()` into the ingest pipeline (Layer B hookup in `_drive_common.py`)
- Fix the triple-dedup edge case in `scrub.py`
- Thread replacement counts into chunk metadata
- Execute the original session 12 plan: guard redesign → dump-json fix → dry-run → commit-run

Session 12 ran $0 total. Session 13 projected the same (cache still warm).

---

## Reading order (after Step 0 passes)

1. **`docs/HANDOVER.md`** — read the session 12 entry at the top in full. It documents the scrub module design, the Dr. Christina decision, the layering rationale (Layer B primary, Layer C retrieval backstop deferred), and the three bugs still open from session 11 that session 12 never got to. Session 11 and earlier entries: skip.

2. **`ingester/text/scrub.py`** — read in full. It's ~130 lines. Understand:
   - The `NAME_REPLACEMENTS` list (11 rules, ordered most-specific first, all case-insensitive)
   - The `DEDUP_PATTERNS` second pass (handles `Dr. Nashat Latib & Dr. Nashat Latib` → `Dr. Nashat Latib`)
   - The `scrub_text()` function signature returns `(cleaned_text, replacement_count)` — callers are expected to surface the count for observability

3. **`ingester/loaders/_drive_common.py`** — skim. You're going to wire the scrub in at the `chunk_text()` emit point or immediately after. Pick the layer based on what reads cleanest; `_drive_common.chunk_text()` is called by both v1 and v2 so this is the single chokepoint that gives you automatic coverage of both loaders.

4. **`ingester/loaders/drive_loader_v2.py`** — read in full (same as session 12 intended). Specifically focus on:
   - `run()` — the dry-run vs commit path, where `all_files_dumped.append(...)` is called (**bug**: not called on skip-after-stitch paths; session 11 left this broken, session 12 did not get to it)
   - `stitch_stream()` — understand how `[IMAGE #N: ...]` markers are assembled
   - The `low_yield_even_with_vision` guard block around the `LOW_YIELD_RATIO_THRESHOLD` check — the thing you're going to redesign

5. **`docs/plans/2026-04-13-drive-loader-v2.md`** — skim only if context from reading 3 and 4 isn't enough. Session 11's handover captured most decisions.

**Do NOT read** (deliberate skips):
- Session 7, session 8, session 9, session 10 HANDOVER entries — frozen
- ADR_005, ADR_006, the session 7 plans — frozen
- `drive_loader.py` (v1) — v1 is frozen except via `_drive_common`; if you wire the scrub into `_drive_common.chunk_text()`, v1 picks it up automatically without any edits to v1 code
- `rag_pipeline_v3_llm.py`, A4M ingestion files, Lineage A dead code
- The image review viewer (`scripts/build_image_review.py`, `data/image_samples/index.html`) — session 12 artifact, do not re-open unless specifically asked

---

## The actual goal for session 13 — wire scrub, finish session 12's original plan

### Staircase (use the same pattern as sessions 10, 11, 12)

1. **Step 1 — Fix the scrub triple-dedup edge case (quick warm-up).**
   Add one pattern to `DEDUP_PATTERNS` in `ingester/text/scrub.py` that handles the case where three consecutive `Dr. Nashat Latib` tokens appear separated by `,` and `, and`. The missing pattern is roughly: `Dr. Nashat Latib, Dr. Nashat Latib, and Dr. Nashat Latib` → `Dr. Nashat Latib`. Re-run the session 12 test battery; expect 19/19 passing. No halt needed — this is pure code debt cleanup. ~5 minutes.

2. **Step 2 — Wire scrub into `_drive_common.chunk_text()`.**
   Import `scrub_text` from `ingester.text.scrub`. Call it on each chunk's text right before the chunk dict is returned from `chunk_text()`. Store the returned `replacement_count` as a new field on the chunk dict (`name_replacements: int`). Then update `build_metadata_base()` (or the v1/v2 per-loader metadata builders — whichever is the single chokepoint) to propagate `name_replacements` into chunk metadata alongside existing fields. This gives you per-chunk observability in the dump-json and in Chroma metadata. **HALT for Dan's review of the diff before moving on** — this touches the single chokepoint that both v1 and v2 use for chunking, and you want a second set of eyes on it.

3. **Step 3 — Plain-language guard-redesign writeup (HALT for Dan's approval before code).**
   Propose the v2 low-yield guard replacement in text form. Session 12's original plan sketched the shape:
   ```
   # v2-specific guard, replaces the ratio check inherited from v1
   MIN_STITCHED_WORDS_FLOOR = 200  # absolute floor, not a ratio

   skip with reason "low_yield_even_with_vision" IF:
       stitched_words < MIN_STITCHED_WORDS_FLOOR
       AND (
           images_seen == 0
           OR all images are decorative/failed
       )
   ```
   The v1 ratio guard stays in `_drive_common.py` and continues to be used by v1 unchanged — only v2 gets the new logic, locally defined inside `drive_loader_v2.py`. Flag to Dan, wait for approval. Dan may push: "just lower the ratio to 0.3%" — argue against unless he insists; that chases numbers instead of fixing the concept.

4. **Step 4 — Guard fix + dump-json skip-path fix.**
   In `drive_loader_v2.py:run()`:
   - Replace the inherited v1 low-yield guard with the new absolute-floor + no-usable-images logic (Step 3's design)
   - Find every `continue` on a skip-after-stitch path (currently 2: `low_yield_even_with_vision` and `vision_failure_rate_too_high`). Before each `continue`, append an entry to `all_files_dumped` with the stitched text and per-image records so the dump captures skipped files. Keep `files_low_yield_skipped` / `files_vision_failed_skipped` summary lists unchanged — the fix is additive.

5. **Step 5 — v2 dry-run against Supplement Info, dump-json the result, eyeball.**
   ```
   ./venv/bin/python -m ingester.loaders.drive_loader_v2 \
       --selection-file /tmp/rf_pilot_selection.json \
       --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 \
       --dry-run --dump-json data/dumps/supplement_info_pilot_v2_s13.json
   ```
   Expected: 3 files ingest (Professional Nutritionals, Comprehensive, Supplement Details), 1 skipped (spreadsheet), a handful of chunks total, $0 vision (cache hits), trivial embedding estimate. Every chunk from the two image-heavy docs should show `name_replacements >= 1` in its metadata (the cover-image OCR contains the Dr. Christina reference). Show Dan:
   - The overall summary numbers
   - Confirmation that the two image-heavy docs now ingest instead of being skipped
   - The first chunk from each of the two image-heavy docs, with the `[IMAGE #N: ...]` markers visible AND the Dr. Christina reference replaced with Dr. Nashat Latib
   - The `name_replacements` counts across all chunks
   **HALT for Dan's final review before any commit.**

6. **Step 6 — commit-run only with explicit Dan approval.** Real chunks into local `rf_reference_library` collection (584 → ~589). Reversible via chunk IDs in the run record at `data/ingest_runs/<id>.json`. No Railway writes. No git operations by Claude.

### Stop conditions (any of which is a successful session 13)

- Scrub wired, triple-dedup fixed, guard + dump fixes land, dry-run produces coherent chunks from both image-heavy docs with the name-scrub visibly working, commit-run deferred for Dan's review — **success**
- Commit-run lands ~5 chunks from Supplement Info into local Chroma, queryable via `rag_server`, with zero references to Dr. Christina anywhere in the chunk text — **full success**
- Scrub wiring surfaces an unexpected bug in `_drive_common.chunk_text()` behavior, session pivots to fixing that — **also success** (the hookup revealed a real issue)

### Anti-goals for session 13 (unchanged)

- NO push of v2 to Railway
- NO modification of v1 except via `_drive_common` (the chunk-level scrub hookup is legitimate; it's additive and flows through the shared helper)
- NO ingestion of any other folder besides Supplement Info
- NO touching `rf_coaching_transcripts` (the scrub will eventually need to apply there in a separate session when transcripts get re-embedded; not session 13's job)
- NO bolting PDF/Slides/image-file support onto v2
- NO re-triggering the OCR eyeball gate — Dan signed off in session 12
- NO touching ADR_006, the three session-7 plans, or anything under "frozen"
- NO editing `_drive_common.py` beyond the scrub hookup unless specifically required

---

## Cost expectations

- Step 1 scrub fix: $0
- Step 2 wiring: $0
- Step 3 writeup: $0
- Step 4 code edits: $0
- Step 5 dry-run: $0 vision (all cache hits, 27 unique SHAs cached) + ~$0.0001 embedding estimate
- Step 6 commit-run: ~$0.0001 actual embedding, $0 vision
- **Total session 13 projected: < $0.001**

Cost gate thresholds unchanged: $1.00 interactive, $25 hard refuse. Neither should come near tripping.

---

## Hard rules carried forward (unchanged from sessions 7–12)

- No ChromaDB writes without explicit Dan approval at the specific write moment; never to Railway without a pre-flight discussion + verified backup
- No git push/commit/add by Claude — Dan runs git; Claude suggests
- No Railway operations without explicit approval
- No deletions without approval and verified backup
- Never reference Dr. Christina / Dr. Chris / Dr. Massinople / Massinople Park / Mass Park in any output; the scrub module is the mechanism that enforces this at ingest time
- Public agent never accesses `rf_coaching_transcripts`
- Credentials ephemeral — never read `.env` and reproduce contents in chat
- **Use Desktop Commander heredocs (`start_process` + bash -c) for file writes.** `create_file` writes to Claude's sandbox, not Dan's Mac.
- **Before any commit-run, halt and show Dan the dump-json.** v2 inherits the v1 "first-touch of live Chroma requires manual eyeball-diff gate" rule.

---

## Tech-lead mandate (unchanged)

Claude holds tech-lead role. Tactical decisions (guard logic, scrub rules, dedup patterns, chunking parameters, wiring layer) are Claude's call. Strategic decisions (irreversible operations, money spend > $25, anything crossing RAG/app/product/legal boundaries, anything failing the "can we fix this later?" test) get flagged to Dan first.

Session start includes Step 0 reality check against on-disk evidence before reading the bootstrap prompt's reading list.

---

## Quick reference

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/` (dev sandbox)
- Railway production: `https://console.drnashatlatib.com` (untouched this work)
- venv: `./venv/bin/python` (Python 3.11.3, chromadb 1.5.6, google-genai 1.72.0, beautifulsoup4 4.14.3)
- v1 loader: `ingester/loaders/drive_loader.py` (frozen; imports from `_drive_common`)
- v2 loader: `ingester/loaders/drive_loader_v2.py` (new session 11, not yet fixed)
- Shared helpers: `ingester/loaders/_drive_common.py` (chunking chokepoint — scrub wires in here)
- Scrub module: `ingester/text/scrub.py` (session 12, 18/19 tests passing, needs 1 pattern added)
- Image review (session 12 artifact, DO NOT re-run): `data/image_samples/index.html`
- Vision stack: `ingester/vision/{ocr_cache,gemini_client}.py`
- OCR cache: `data/image_ocr_cache/*.json` (27 files, warm)
- Session 11 dump (BROKEN — only 1 of 3 files): `data/dumps/supplement_info_pilot_v2.json`
- Pilot folder: Supplement Info, ID `1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`, in drive `1-operations`
- GCP project: `rf-rag-ingester-493016`
- Vertex AI region: `us-central1`
- Gemini model: `gemini-2.5-flash` (per `ingester/config.py:VISION_MODEL`)
- Prompt version: `v1` (in `ingester/vision/gemini_client.py:PROMPT_VERSION`). Bump to `"v2"` only if OCR prompt needs iteration — would invalidate cache.
- Service account: `/Users/danielsmith/.config/gcloud/rf-service-account.json` (mode 600)
- Selection file for pilot: `/tmp/rf_pilot_selection.json` (contents in HANDOVER session 10 entry — recreate if /tmp wiped on reboot)
