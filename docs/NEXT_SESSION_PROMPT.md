# NEXT SESSION PROMPT — session 12

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Sessions 9, 10, and 11 all used a "step 0 reality check" before doing any work. Session 11's step 0 caught that the `google-genai` SDK import path was deprecated and let us pick the right path before writing any code. **Keep doing this.** The reality check has paid for itself three sessions in a row.

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all five checks. Stop and tell Dan if anything surprises you.

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `read_multiple_files`. If only filesystem and no process pathway, stop and tell Dan the chat needs Desktop Commander.

2. **Smoke test process execution.** Run `echo "session 12 tool check $(date -u +%Y-%m-%dT%H:%M:%SZ)"`.

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -5`. Expected: session-11 work is uncommitted (Dan runs git); top commit is still `567e6cc session 10`. If Dan has committed session 11 work between sessions, top commit will be that commit — either is fine, just know which.

4. **Reality-vs-prompt check.** Verify these against the actual filesystem before reading the reading list:
   - **Drive auth still works locally.** `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"`. Should print OK and `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.
   - **Gemini Vertex AI still works.**
     ```python
     from google import genai
     c = genai.Client(vertexai=True, project="rf-rag-ingester-493016", location="us-central1")
     r = c.models.generate_content(model="gemini-2.5-flash", contents="Say 'ok' and nothing else.")
     print(r.text)
     ```
     Expected: `ok`. If permission error → IAM role dropped (shouldn't happen, but check).
   - **OCR cache is present.** `ls data/image_ocr_cache/*.json | wc -l` — should be **27**. If 0, the cache was wiped between sessions; session 12's first dry-run will cost ~$0.0045 to refill it (still cheap). If 27, session 12 dry-runs cost $0.
   - **v2 loader and shared helpers are on disk.** `ls ingester/loaders/drive_loader_v2.py ingester/loaders/_drive_common.py ingester/vision/*.py`.
   - **v1 regression still passes.** `./venv/bin/python -m ingester.loaders.drive_loader --selection-file /tmp/rf_pilot_selection.json --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 --dry-run 2>&1 | tail -15`. Should report `files ingested: 1`, `low_text_yield: 2 (Comprehensive 0.07%, Supplement Details 0.45%)`, `unsupported_mime: 1 spreadsheet`, total chunks 1, $0.0001. If `/tmp/rf_pilot_selection.json` is gone (Mac reboot wipes /tmp), recreate it per HANDOVER's session 10 entry.
   - **Railway production is still alive.** `curl -sI https://console.drnashatlatib.com | head -3`. HTTP/2 302.

If any check returns a surprise, stop and surface it.

---

## Reading order (after step 0 passes)

Tight reading list. Context budget goes to fixing the guard and validating, not reading.

1. **`docs/HANDOVER.md`** — read the session 11 entry at the top in full. Session 10 and earlier entries: skip unless a specific question forces it. The session 11 entry documents everything session 12 needs to know about v2's current state, what OCR actually produced, and the two bugs still in v2.
2. **`docs/plans/2026-04-13-drive-loader-v2.md`** — the v2 design doc. Skim for context; the session 11 handover captured all decisions.
3. **`ingester/loaders/drive_loader_v2.py`** — read in full. Specifically focus on:
   - `run()` — the dry-run vs commit path, where `all_files_dumped.append(...)` is called (bug: not called on skip paths)
   - `stitch_stream()` — understand how `[IMAGE #N: ...]` markers are assembled
   - The `low_yield_even_with_vision` guard block — the thing you're going to redesign
4. **`ingester/loaders/_drive_common.py`** — skim. Do not modify unless the guard fix specifically needs a shared helper change (it shouldn't — v1's guard stays, v2 gets a v2-specific guard).

**Do NOT read** (deliberate skips):
- The session 7 HANDOVER entry — frozen
- ADR_005, ADR_006, the session 7 plans — frozen
- `drive_loader.py` (v1) — session 11 refactored it to import from `_drive_common`; no changes needed this session
- `rag_pipeline_v3_llm.py`, A4M ingestion files, Lineage A dead code — irrelevant

---

## The actual goal for session 12 — three fixes, dry-run, halt, commit

### The problem from session 11, in one paragraph

v2 built and runs end-to-end. Gemini OCR quality is excellent — Pure Encapsulations, Designs for Health, Douglas Labs product photos transcribed verbatim with full supplement facts panels, doses, ingredient lists. But **the v2 low-yield guard is wrong**: it inherits v1's ratio-against-drive-size heuristic, which made sense when "drive size" correlated with "text content volume," but in v2 drive size is dominated by image payloads. Both image-heavy supplement docs get skipped at 0.39% and 3.16% yield respectively, even though OCR produced ~2,500 usable words each. **Second bug**: v2's dry-run dump-json drops the stitched text and per-image OCR records for any file the guard skips — exactly the files Dan most needs to eyeball. The dump is the halt-for-review artifact and currently fails at the wrong moment. **Third issue**: before fixing either bug, Dan needs to personally sign off on OCR quality. Session 11 Claude read the cache files and confirmed the transcriptions look correct, but Dan has not personally confirmed these match his actual product images.

### Staircase for session 12

Use the same approach as sessions 10 and 11. Stop at each halt.

1. **Step 1 — eyeball gate for OCR quality (HALT for Dan's sign-off).**
   Read 6–10 representative non-decorative entries from `data/image_ocr_cache/*.json`. Show Dan the `ocr_text` field for each. He confirms "yes these are accurate" or pushes back on specific ones. If he pushes back, the fix is a prompt iteration (bump `PROMPT_VERSION` in `ingester/vision/gemini_client.py` from `"v1"` to `"v2"`, which auto-invalidates the cache, and re-dry-run — cost ~$0.005). **Do not touch the guard until Dan has green-lit OCR quality.** Explain in plain language what "ratio-based guard is wrong" means so Dan is making an informed call.

2. **Step 2 — guard redesign, plain-language write-up for Dan's sign-off before code.**
   Propose the replacement logic in text form, flag to Dan, wait for approval. Claude's recommended shape (tactical call under mandate):
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
   This lets any doc through where Gemini extracted text from at least one non-decorative image, regardless of drive size ratio. The v1 ratio guard stays in `_drive_common.py` and continues to be used by v1 unchanged — only v2 gets the new logic, locally defined inside `drive_loader_v2.py`. Alternative Dan might push: "just lower the ratio to 0.3%" — argue against unless he insists; that chases numbers instead of fixing the concept.

3. **Step 3 — dump-json fix.** Inside `drive_loader_v2.py:run()`, find every `continue` on a skip-after-stitch path (currently 2: the `low_yield_even_with_vision` path and the `vision_failure_rate_too_high` path). Before each `continue`, append an entry to `all_files_dumped` with the stitched text and per-image records so the dump captures them. Keep the low_yield_skipped / vision_failed_skipped lists unchanged (they're summary metadata for the top of the dump). The fix is additive; no existing dump field moves.

4. **Step 4 — re-run v2 dry-run against Supplement Info, dump-json the result, eyeball.**
   ```
   ./venv/bin/python -m ingester.loaders.drive_loader_v2 \
       --selection-file /tmp/rf_pilot_selection.json \
       --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 \
       --dry-run --dump-json data/dumps/supplement_info_pilot_v2_post_fix.json
   ```
   Expected: 3 files ingest (Professional Nutritionals, Comprehensive, Supplement Details), 1 skipped (spreadsheet), a few chunks total, $0 vision (cache hits), trivial embedding estimate. Show Dan the dump contents — specifically the `[IMAGE #N: ...]` markers inside the chunks for Comprehensive and Supplement Details. **HALT for Dan's final review before any commit.**

5. **Step 5 — commit-run only with explicit Dan approval.** Real chunks into local `rf_reference_library` collection (584 → ~589). Reversible via chunk IDs in the run record at `data/ingest_runs/<id>.json`. No Railway writes. No git operations by Claude.

### Stop conditions (any of which is a successful session 12)

- Guard + dump fixes land, dry-run produces coherent chunks from both image-heavy docs, commit-run deferred for Dan's review
- Commit-run lands ~5 chunks from Supplement Info into local Chroma, queryable via `rag_server`
- Dan rejects OCR quality after eyeball, session pivots to prompt iteration + re-dry-run (also a success — the eyeball gate did its job)

### Anti-goals for session 12 (unchanged from session 11)

- NO push of v2 to Railway
- NO modification of v1 except via `_drive_common` (refactor already done; v1 is frozen)
- NO ingestion of any other folder besides Supplement Info
- NO bolting PDF/Slides/image-file support onto v2
- NO touching ADR_006, the three session-7 plans, or anything under "frozen"
- NO edits to `_drive_common.py` unless the guard fix specifically requires a shared helper change (it shouldn't — v2's new guard lives inside `drive_loader_v2.py`)

---

## Cost expectations

- Step 1 eyeball: $0 (reading on-disk cache files)
- Step 4 dry-run: $0 vision (all cache hits, 27 unique SHAs already cached) + ~$0.0001 embedding estimate
- Step 5 commit-run: ~$0.0001 actual embedding, $0 vision
- **Total session 12 projected: < $0.001**

Cost gate thresholds unchanged: $1.00 interactive, $25 hard refuse. Neither should come anywhere near tripping.

**If the cache was wiped** (check in Step 0): first dry-run refills it for ~$0.0045. Still well under any gate. Not a strategic spend.

---

## Hard rules carried forward (unchanged from sessions 7–11)

- No ChromaDB writes without explicit Dan approval at the specific write moment; never to Railway without a pre-flight discussion + verified backup
- No git push/commit/add by Claude — Dan runs git; Claude suggests
- No Railway operations without explicit approval
- No deletions without approval and verified backup
- Never reference Dr. Christina; exclude Kelsey Poe and Erica from retrieval results
- Public agent never accesses `rf_coaching_transcripts`
- Credentials ephemeral — never read `.env` and reproduce contents in chat output
- **Use Desktop Commander heredocs for file writes to the repo.** `create_file` writes to Claude's sandbox, not the Mac. Sessions 8 and 11 both confirmed this matters.
- **Before any commit-run, halt and show Dan the dump-json.** The v1 loader plan doc codified this ("first-touch of live Chroma requires a manual eyeball-diff gate"). v2 inherits it.

---

## Tech-lead mandate (unchanged)

Claude holds tech-lead role. Tactical decisions (guard logic, prompt wording, cache structure, chunking parameters) are Claude's call. Strategic decisions (irreversible operations, money spend > $25, anything crossing the RAG/app/product/legal boundary, anything failing the "can we fix this later?" test) get flagged to Dan first. Session start includes Step 0 reality check against on-disk evidence before reading the bootstrap prompt's reading list.

---

## Quick reference

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/` (dev sandbox)
- Railway production: `https://console.drnashatlatib.com` (untouched this work)
- venv: `./venv/bin/python` (Python 3.11.3, chromadb 1.5.6, google-genai 1.72.0, beautifulsoup4 4.14.3)
- v1 loader: `ingester/loaders/drive_loader.py` (refactored session 11 — imports from `_drive_common`)
- v2 loader: `ingester/loaders/drive_loader_v2.py` (new session 11)
- Shared helpers: `ingester/loaders/_drive_common.py` (new session 11)
- Vision stack: `ingester/vision/{ocr_cache,gemini_client}.py` (new session 11)
- OCR cache: `data/image_ocr_cache/*.json` (27 files as of end of session 11)
- Session 11 dump (BROKEN — only has 1 of 3 files): `data/dumps/supplement_info_pilot_v2.json`
- Session 11 v1 regression dump baseline: session 10's dump at `data/dumps/supplement_info_pilot_v1guard.json` (unchanged)
- Pilot folder: Supplement Info, ID `1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`, in drive `1-operations`
- GCP project: `rf-rag-ingester-493016`
- Vertex AI region: `us-central1`
- Gemini model: `gemini-2.5-flash` (per `ingester/config.py:VISION_MODEL`)
- Prompt version: `v1` (in `ingester/vision/gemini_client.py:PROMPT_VERSION`). Bump to `"v2"` if prompt needs iteration — automatically invalidates cache.
- Service account: `/Users/danielsmith/.config/gcloud/rf-service-account.json` (mode 600)
- Selection file for pilot: `/tmp/rf_pilot_selection.json` (contents in HANDOVER session 10 entry — recreate if /tmp wiped)
