# NEXT SESSION PROMPT — session 18

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Every session 9 onward has used a Step 0 reality check before doing any work. It has paid for itself every single time. Session 14 missed a dirty working tree. Session 16 surfaced four pre-existing UI bugs. Session 17 caught a poor pilot file pick before any commit. **Session 18 must run Step 0 in full**, including the admin UI sanity gate from session 16.

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all gates. Stop and tell Dan if anything surprises you.

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 18 ok"); 2+2`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -8`.
   - **Expected top commit: a single session 17 commit** landing the M3 google_doc_handler extraction (new module + 2 new tests + v2/v3 surgical edits + 4 doc updates + 4 new BACKLOG items + #11 closure note).
   - Below session 17: the session 16 commit (`98f8011`), session 15 (`d0c381f`), session 14 (`d33d6a9`), session 13 (`ac3f1fc`), etc.
   - **Working tree must be completely clean.** If `git status` shows ANY modified or untracked files, STOP and surface them. Do not assume they're stale or safe to ignore. (Session 14 lesson.)

### 0.3 — Data plane reality

4. **Reality-vs-prompt check.** Verify these against the actual filesystem:

   - **Chroma baseline.** Run a Python one-liner to count `rf_reference_library`. **Expected: 605** (604 session-16 baseline + 1 session-17 Sugar Swaps Guide chunk). If 604, session 17 commit rolled back — stop. If 606+, something wrote between sessions — stop.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** `col.get(where={"source_pipeline":"drive_loader_v3"}, limit=30)` — should return **8 chunk IDs**. 7 are PDF (Egg Health Guide, session 16, all from `ingest_run_id=fd712b4d2cd440c0`, all with `v3_category='pdf'`, all with `display_locator` populated as `pp. 1-6`/`pp. 6-8`/etc.). **The 8th is the Sugar Swaps Guide Google Doc** (`ingest_run_id=cf63f977f51d4d43`, `v3_category='v2_google_doc'`, `display_locator='§1'`, `name_replacements=1`).

   - **v2-ingested chunks still queryable.** `col.get(where={"source_pipeline":"drive_loader_v2"}, limit=30)` — should still return **13 chunk IDs** (session 14 unchanged). At least 3 should have `name_replacements >= 1`.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → **29** (unchanged from session 16; session 17 had zero new OCR calls because the Sugar Swaps Guide has no images).

   - **Drive auth.**
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
     ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"
     ```
     Expected: `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth (gemini-2.5-flash via google.genai SDK).**
     ```python
     from google import genai
     c = genai.Client(vertexai=True, project="rf-rag-ingester-493016", location="us-central1")
     print(c.models.generate_content(model="gemini-2.5-flash", contents="Say 'ok' and nothing else.").text)
     ```
     Expected: `ok`.

   - **OpenAI auth (live, not just presence).** Source `.env` in a subshell (`set -a && . ./.env && set +a`), then a minimal `embeddings.create("test")` call. Never read `.env` contents into chat.

   - **Scrub module on disk, wired, tests passing.**
     ```bash
     ./venv/bin/python scripts/test_scrub_s13.py            # 19/19
     ./venv/bin/python scripts/test_scrub_wiring_s13.py     # PASS
     ```

   - **v3 module tests still green** (session 16 + session 17). All must pass.
     ```bash
     ./venv/bin/python scripts/test_types_module.py                    # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py             # PASS
     GOOGLE_APPLICATION_CREDENTIALS=... ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_format_context_s16.py              # 23/23
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py         # 16/16
     ./venv/bin/python scripts/test_google_doc_handler_synthetic.py    # 9/9 (NEW session 17)
     ```
     **Note:** `test_admin_save_endpoint_s16.py` clobbers `data/selection_state.json` as a side effect (BACKLOG #31). If you run the battery in a sequence that depends on `selection_state.json`'s contents, restore it AFTER the test, not before.

   - **v1 regression.** v1 still works for the original pilot.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader        --selection-file /tmp/rf_pilot_selection.json        --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54        --dry-run 2>&1 | tail -15
     ```
     Expect `files ingested: 1`, 2 low-yield skips. If `/tmp/rf_pilot_selection.json` no longer exists (reboot wiped `/tmp/`), recreate it from HANDOVER session 10.

   - **v2 regression.** v2 still works for Google Docs (and is now post-M3 — extracted helpers come from google_doc_handler).
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v2 --dry-run 2>&1 | tail -20
     ```
     Expect a clean enumeration of the 13 chunks already ingested, no errors. **The v2 dry-run output must be byte-identical to session 16's baseline**: 2 files seen, 2 ingested, 1 vision_cache_hit, 0 errors, ~1,303 est_tokens, $0.0002 est_cost. M3's whole point is byte-identical v2 behavior.

   - **v3 regression.** v3 works on both PDF and Google Doc handlers.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -30
     ```
     Default selection_state should resolve to the DFH folder + Egg Health Guide PDF. Expected: 3 files enumerated, 3 processed OK, 0 quarantined, 9 chunks projected (1+1+7), `by_handler={pdf: 1, v2_google_doc: 2}`, $0 vision cost (cache hit), ~$0.0010 projected total.

### 0.4 — Admin UI sanity (session 16 gate, still in effect)

5. **Admin UI process state.**
   ```bash
   lsof -iTCP:5052 -sTCP:LISTEN -P -n
   ```
   - If a Python process is listening on 5052: existing dev server is up. Verify it's running session-16/17 code by checking the modification time of its working files matches what the disk has.
   - If no process is listening: that's fine, start a fresh one with `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s18_admin_ui.log 2>&1 & disown` from the repo root.

6. **HTML cache disable hook is active.** Quick curl smoke test:
   ```bash
   curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'
   ```
   - 302 redirect to login is fine
   - But a `Cache-Control: no-store` header on the response confirms the after_request hook is wired.

7. **Selection state on disk has the session 16 two-bucket shape.**
   ```bash
   cat data/selection_state.json
   ```
   Expected: a JSON object with `selected_folders` AND `selected_files` keys (both arrays), `library_assignments` dict, and a `timestamp`. Default state at end of session 17 is the session-16 shape (DFH folder + Egg Health Guide PDF).

### 0.5 — Final reality summary

8. **Print a one-line state summary** to confirm Step 0 passed:
   ```
   ✓ Step 0 PASS — repo at <commit_hash>, rf_reference_library: 605, v3 chunks: 8 (7 pdf + 1 v2_google_doc),
     all 8 test scripts green, admin UI on PID <pid>, selection_state v2 shape OK
   ```

If anything in 0.1–0.5 fails, **STOP and surface the failure to Dan before reading any further or doing any work.**

---

## Step 1 — Read the BACKLOG and pick scope (~5 minutes)

After Step 0 passes, read these files in this order. Don't read more than necessary.

1. **`docs/STATE_OF_PLAY.md` — session 17 amendment** (the bottom section, ~90 lines). Tells you the state of the world coming into session 18.

2. **`docs/HANDOVER.md` — session 17 entry** (the bottom section, ~180 lines). Tells you what shipped in session 17, what bugs were found, what lessons carry forward.

3. **`docs/BACKLOG.md` — items #29 through #32** (the new "NEW — added session 17" section, ~80 lines). These are session 17's wake.

4. Skim BACKLOG.md briefly for #6b, #11 (now closed), #17, #18, #20 (the retrofit bundle candidates) plus #21, #29, #30 (the immediate session 18 candidates).

---

## Step 2 — Scope decision (Dan picks)

Session 17 closed BACKLOG #11. **The two main paths forward both retain their session-16 framing**, with one new candidate from session 17:

### Option A — The retrofit bundle (still highest leverage)

**Bundles:** BACKLOG #6b (coaching scrub retrofit) + #17 (display_subheading normalization across all chunk populations) + #18 (`format_context()` migration to canonical fields) + #20 (inline citation prompting) + **#30 (v3 metadata writer drops `extraction_method` and `library_name` — new in session 17)**.

**Why bundle:** all five items touch the same chunks (now 9,224 coaching + 584 A4M + 13 v2 + 8 v3 = 9,829 total). One backup, one read pass, one write pass per collection. Doing them sequentially is 5 sessions of overlapping work + 5× partial-state risk.

**Estimated effort:** ~half-day, one session.

**Real risks:**
1. **#6b has a known unknown.** Scrub has never been validated against the full coaching corpus, only synthetic test data + v2 DFH chunks + v3 PDF chunks + v3 Google Doc chunks. Read-only count + sample first.
2. **9,224 chunks is 15× the rest.** Metadata-only update at this scale needs to be batched, idempotent, resumable.
3. **#20 is the only piece that might warrant re-embedding** — but only if the change to retrieved-context format affects retrieval similarity. Prompt-only changes don't.

### Option B — Another v3 handler

**Single item:** ship one of the deferred v3 file types in `MIME_CATEGORY`. Priority order based on Drive content unlock:

1. **docx** — `application/vnd.openxmlformats-officedocument.wordprocessingml.document`. Library: `python-docx`. Locator: `§N` (sections — same convention as Google Docs). Closest to Google Doc handler in shape.
2. **plain text** — `text/plain`, `text/markdown`. Locator: `line N`. Trivial handler. Smallest unlock but smallest risk.
3. **sheets** — `application/vnd.google-apps.spreadsheet`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Library: `openpyxl`. Locator: `row N`. Bigger because rows-as-chunks is a different semantic from paragraphs.
4. **slides** — `application/vnd.google-apps.presentation`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`. Locator: `slide N`. Bigger because slides need vision OCR for embedded images.
5. **image** — single-image vision OCR. Locator: none.
6. **av** — audio/video transcription. Largest unlock, largest cost, requires Whisper or Gemini audio.

**Recommendation if Option B:** docx first. Same shape as the Google Doc handler. Likely ~3 hours.

### Option C — BACKLOG #29 (Canva editor metadata strip)

**Single item:** add an editor-metadata stripper to `google_doc_handler` that removes Canva edit URLs, production tags (`COVER:`, `PAGE 1:`, etc.), and draft notes from the stitched text before chunking. A/B test on the 14 existing v2/v3 Google Doc chunks (re-extraction dry-run only, no Chroma writes) to verify retrieval similarity improves.

**Why it matters:** the Sugar Swaps Guide chunk's first ~120 chars are Canva editor metadata that pollutes the embedding. Same on the 13 DFH chunks. Affects retrieval quality across all current Google Doc content.

**Estimated effort:** ~1-2 hours.

### Other candidates

- **BACKLOG #21** — folder-selection UI redesign (eliminate pending-panel, drive-vs-folder visual differentiation). 60–90 min. Biggest UX friction point.
- **BACKLOG #10** — reconcile `requirements.txt`. ~1 hour.
- **BACKLOG #27** — self-host Google Fonts. ~30 min.
- **BACKLOG #23 + #14** — content-hash dedup + orphan cleanup. ~2 hours.
- **BACKLOG #32** — smarter Google Doc locator detection (paragraph fallback). ~2 hours.

**Tech-lead recommendation: Option A (retrofit bundle).** Same reasoning as session 17:
1. Highest leverage per session-hour
2. Touches the largest fraction of the corpus (9,829 chunks)
3. Closes 5 BACKLOG items in one session (now including #30)
4. #6b is still the biggest standing liability — pre-scrub coaching chunks may contain the former-collaborator name, and we have no idea how many.
5. Sets up a cleaner foundation for any subsequent v3 handler work.

But **Option B (docx handler)** is also defensible if Dan wants to keep extending v3's file-type coverage before doing retrofit work. The Google Doc handler from session 17 is a clean reference implementation.

And **Option C (Canva strip)** is the smallest, fastest, content-quality-focused option if Dan wants a quick session.

It's Dan's call — surface all three, recommend A, wait for the answer.

---

## Step 3+ — Execute the chosen scope

Once Dan picks, scope a tight plan **before** writing any code:
1. List the files you'll touch
2. List the test scripts you'll write or update
3. List any data writes (Chroma operations, file edits) and identify halt points
4. Identify the "minimum viable closure" — the smallest deliverable that proves the scope landed
5. Estimate spend in API calls (embeddings + LLM inference)

Get Dan's approval on the plan, THEN execute.

**Standing rules carried forward (do not skip):**

- **Halt before --commit.** Show dump-json before any write to Chroma. (Session 14 lesson.)
- **Pipe commit stdout to a file**, not `| tail` — session 16 step 9 lesson.
- **Tech-lead volunteers architecture review at design-halt points.** When a design doc has a question mark or assumption, surface it as M-options (M1/M2/...) before code. (Session 15/16 lesson.)
- **Read the Flask access log first** when debugging UI cache or save issues. (Session 16 lesson.)
- **Test in Chrome before Safari** for admin UI iterative work. (Session 16 lesson.)
- **When closing a BACKLOG item, verify in the environment where it manifested.** Real browser click-through for UI bugs, real query against live collection for data bugs, real /chat smoke against Sonnet for end-to-end content-safety bugs. (Session 16/17 lesson.)
- **No deletions without approval + backup.**
- **No Railway writes from sessions.** Railway is read-only.
- **No touching legacy collections** (`rf_coaching_transcripts`, pre-scrub 584 A4M) without Dan's explicit OK.
- **Credentials ephemeral** — never read `.env` content into chat.
- **Never reference Dr. Christina / Dr. Chris / Dr. Massinople** in agent responses. Layer B scrub catches new content; legacy is not yet protected (BACKLOG #6b).
- **Dan does git operations**, not Claude.
- **NEW (session 17):** v2 is frozen UNLESS the change is an extract-and-redirect to a shared module that preserves byte-identical v2 behavior, verified by dry-run regression. M3 is the precedent. Anything else still needs explicit approval.
- **NEW (session 17):** when piloting a new feature, scan for real-world examples that exercise the feature, not just any small example. (DFH-pilot-rejection lesson.)
- **NEW (session 17):** prefer write-script-to-file over inline heredocs for any Python script longer than ~10 lines. Heredoc + Python triple-quotes + bash escaping is fragile.

---

## Budget for session 18

- **$1.00 interactive gate.** If any single task projects above $1.00 in API spend, halt and surface the cost to Dan before proceeding.
- **$25.00 hard refuse.** No single session should ever spend more than $25 in API calls. If a task projects above this, refuse and require explicit Dan approval.
- **Session 17 spent ~$0.020** of $1.00 — well under. Session 18 has the same envelope.

## Files you'll likely touch (depending on scope)

**For Option A (retrofit bundle):**
- `ingester/text/scrub.py` (or wherever the Layer B scrub helper lives)
- `rag_server/app.py` (`format_context()` migration + canonical field reads)
- `config/nashat_sales.yaml`, `config/nashat_coaching.yaml` (inline citation prompting)
- `ingester/loaders/drive_loader_v3.py` (metadata writer fix for #30)
- New: `scripts/retrofit_coaching_scrub_s18.py` (one-time pass over the 9,224 chunks)
- New: `scripts/retrofit_display_subheading_s18.py` (one-time pass)
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

**For Option B (docx handler):**
- New: `ingester/loaders/types/docx_handler.py` (model on `google_doc_handler.py`)
- `ingester/loaders/drive_loader_v3.py` (wire docx category in `_dispatch_file`, add to `SESSION_16_CATEGORIES` or rename)
- New: `scripts/test_docx_handler_synthetic.py`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

**For Option C (Canva strip):**
- `ingester/loaders/types/google_doc_handler.py` (add `_strip_editor_metadata()` post-pass to `extract_from_html_bytes`)
- New: `scripts/test_canva_strip_synthetic.py`
- New: `scripts/test_canva_strip_dryrun_existing_chunks.py` (re-extract the 14 existing Google Doc chunks in dry-run mode and compare retrieval similarity before/after — no Chroma writes)
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

## Files you should NOT touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via the audit module
- Anything under `rf-coaching-call-recordings/` — pure read-only data
- `ingester/loaders/drive_loader_v2.py` — frozen except for M3-style extract-and-redirect (session 17 precedent)


## Step 0 cheat sheet (for quick reference at the start of session 18)

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -8

# Chroma baseline (expect 605)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks queryable (expect 8 = 7 pdf + 1 v2_google_doc)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); print('v3 chunks:', len(r['ids']))"

# OCR cache (expect 29, unchanged from session 16)
ls data/image_ocr_cache/*.json | wc -l

# Test suite (expect all 8 green)
./venv/bin/python scripts/test_scrub_s13.py
./venv/bin/python scripts/test_scrub_wiring_s13.py
./venv/bin/python scripts/test_types_module.py
./venv/bin/python scripts/test_chunk_with_locators.py
./venv/bin/python scripts/test_format_context_s16.py
./venv/bin/python scripts/test_admin_save_endpoint_s16.py
./venv/bin/python scripts/test_google_doc_handler_synthetic.py     # session 17, 9/9
GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py

# Drive auth
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"

# v2 dry-run regression (must be byte-identical to session 16 baseline)
./venv/bin/python -m ingester.loaders.drive_loader_v2 --dry-run 2>&1 | tail -20

# v3 dry-run regression (3 files, 9 chunks projected, 0 vision cost)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -30

# Admin UI process check
lsof -iTCP:5052 -sTCP:LISTEN -P -n

# Selection state shape
cat data/selection_state.json
```

If all of the above passes, print:
```
✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc),
  OCR cache: 29, all tests green, admin UI on PID <pid>, selection_state v2 shape OK
```

Then proceed to Step 1.

---

## End of session 18 prompt

Session 17 closed BACKLOG #11 by extracting v2's Google Doc logic into a shared handler module (M3 design), wiring it into v3's dispatcher, and proving end-to-end via the Sugar Swaps Guide commit. v3 now supports both PDF and Google Doc file types with locator-aware chunk metadata, and v2 still works byte-identically. The system has 605 chunks, 8 of them v3-ingested. Session 18 picks up clean. Good luck.
