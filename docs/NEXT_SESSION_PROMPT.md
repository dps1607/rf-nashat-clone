# NEXT SESSION PROMPT — session 17

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Sessions 9–16 all used a "Step 0 reality check" before doing any work. It has paid for itself every single session. Session 14 missed a dirty working tree. Session 16 surfaced four pre-existing UI bugs that had been hidden by each other. **Session 17's Step 0 must include UI-state sanity checks too**, not just data-plane checks — see Step 0 below for the new gates.

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all gates. Stop and tell Dan if anything surprises you.

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 17 ok"); 2+2`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -8`.
   - **Expected top commit: a single session 16 commit** landing the v3 drive loader, types module, PDF handler, admin UI changes (api_folders_save two-bucket contract, after_request HTML cache disable, folder-tree.js DOM-source-of-truth save handler, toast repositioning), `format_context()` v3 branch, design doc, 7 new test scripts, 4 docs updates (HANDOVER, BACKLOG, STATE_OF_PLAY, NEXT_SESSION_PROMPT).
   - Below session 16: the session 15 design-doc commit, session 14 commits (cookie patch + folder-only UI + v2 OpenAI preflight), session 13, etc.
   - **Working tree must be completely clean.** If `git status` shows ANY modified or untracked files, STOP and surface them. Do not assume they're stale or safe to ignore. (Session 14 lesson.)

### 0.3 — Data plane reality

4. **Reality-vs-prompt check.** Verify these against the actual filesystem:

   - **Chroma baseline.** Run a Python one-liner to count `rf_reference_library`. **Expected: 604** (597 session-15 baseline + 7 v3 PDF chunks for Egg Health Guide). If 597, session 16 commit rolled back — stop. If 605+, something wrote between sessions — stop.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3-ingested chunks queryable.** Query for `where={"source_pipeline":"drive_loader_v3"}` — should return **7 chunk IDs**, all from `ingest_run_id=fd712b4d2cd440c0` (Egg Health Guide), all with `v3_category='pdf'`, all with `display_locator` populated (`pp. 1-6`, `pp. 6-8`, `pp. 8-10`, `pp. 10-12`, `pp. 12-16`, `pp. 16-18`, `p. 18`). Chunk index 0 should have `name_replacements=1`.

   - **v2-ingested chunks still queryable.** `col.get(where={"source_pipeline":"drive_loader_v2"}, limit=30)` — should still return **13 chunk IDs** (session 14 unchanged). At least 3 should have `name_replacements >= 1`.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → **29** (28 session-15 baseline + 1 from session 16's synthetic PDF OCR test).


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

   - **v3 module tests still green.** Session 16 added these — they must still pass.
     ```bash
     ./venv/bin/python scripts/test_types_module.py             # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py      # PASS
     GOOGLE_APPLICATION_CREDENTIALS=... ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_format_context_s16.py       # 23/23
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py  # 16/16
     ```


   - **v1 regression.** v1 still works for the original pilot.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader \
       --selection-file /tmp/rf_pilot_selection.json \
       --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 \
       --dry-run 2>&1 | tail -15
     ```
     Expect `files ingested: 1`, 2 low-yield skips. If `/tmp/rf_pilot_selection.json` no longer exists (reboot wiped `/tmp/`), recreate it from HANDOVER session 10.

   - **v2 regression.** v2 still works for Google Docs.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v2 --dry-run 2>&1 | tail -20
     ```
     Expect a clean enumeration of the 13 chunks already ingested, no errors.

### 0.4 — Admin UI sanity (NEW gate added in session 16)

5. **Admin UI process state.**
   ```bash
   lsof -iTCP:5052 -sTCP:LISTEN -P -n
   ```
   - If a Python process is listening on 5052: existing dev server is up. Verify it's running session-16 code by checking the modification time of its working files matches what the disk has.
   - If no process is listening: that's fine, start a fresh one with `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s17_admin_ui.log 2>&1 & disown` from the repo root.

6. **HTML cache disable hook is active.** Quick curl smoke test:
   ```bash
   curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'
   ```
   - 302 redirect to login is fine
   - But a `Cache-Control: no-store` header on the 200 page (post-login) confirms the after_request hook is wired. If it's missing, session 16's Bug 2 fix didn't land — investigate before any UI iteration.


7. **Selection state on disk has the session 16 two-bucket shape.**
   ```bash
   cat data/selection_state.json
   ```
   Expected: a JSON object with `selected_folders` AND `selected_files` keys (both arrays), `library_assignments` dict, and a `timestamp`. If only `selected_folders` exists (old shape), session 16 didn't land — investigate.

### 0.5 — Final reality summary

8. **Print a one-line state summary** to confirm Step 0 passed:
   ```
   ✓ Step 0 PASS — repo clean at <commit_hash>, rf_reference_library: 604, v3 chunks: 7,
     scrub tests green, admin UI on PID <pid>, selection_state v2 shape OK
   ```

If anything in 0.1–0.5 fails, **STOP and surface the failure to Dan before reading any further or doing any work.** Don't skip Step 0.

---

## Step 1 — Read the BACKLOG and pick scope (~5 minutes)

After Step 0 passes, read these files in this order. Don't read more than necessary.

1. **`docs/STATE_OF_PLAY.md` — session 16 amendment** (the bottom section, ~70 lines). Tells you the state of the world coming into session 17.

2. **`docs/HANDOVER.md` — session 16 entry** (the bottom section, ~200 lines). Tells you what shipped in session 16, what bugs were fixed, what lessons carry forward.

3. **`docs/BACKLOG.md` — items 8 through 28** (the "NEW — added session 16" section). These are session 17's candidate scopes.

4. Skim the rest of BACKLOG.md briefly for context on the older items (#1–#7 from session 15, plus the deferred-from-earlier-sessions items below). You don't need to read them in detail unless you pick something from there.


---

## Step 2 — Scope decision (Dan picks)

Session 16's tech-lead recommendation is one of two paths for session 17. **Do not pick autonomously — surface the options and let Dan choose.**

### Option A — The retrofit bundle (highest leverage)

**Bundles:** BACKLOG #6b (coaching scrub retrofit) + #17 (display_subheading normalization across all 3 chunk populations) + #18 (`format_context()` migration to canonical fields) + #20 (inline citation prompting in agent system prompts).

**Why bundle:** these four items all touch the same chunks (9,224 coaching + 584 A4M + 13 v2 + 7 v3 = 9,828 total). Doing them as a single coordinated session means one backup, one read pass, one write pass per collection. Doing them incrementally would be 4 separate sessions of overlapping work plus 4× the risk of partial-state collections.

**Estimated effort:** ~half-day in one session.

**Key risks:**
- Re-embedding cost if any change requires it (most are metadata-only, but #20 might prompt-tune in a way that warrants an A/B retrieval test against a real query set)
- The 9,224 coaching chunks dominate by ~15x — any per-chunk operation on them needs to be cheap or batched
- BACKLOG #6b is the biggest unknown — has scrub ever been validated against the full coaching corpus, or just synthetic test data?

**Approach:** Session 17 Step 0 + read STATE_OF_PLAY + read HANDOVER session 16 entry + read BACKLOG #6b/#17/#18/#20 in detail + scope a tight plan with Dan + execute. Halt before any write to a collection. Halt before any re-embed.

### Option B — Google Doc adapter (unblocks "one-button" admin UI flow)

**Single item:** BACKLOG #11. Refactor v2 to expose `process_google_doc(file_id, drive_client, scrubber, chunker) -> ExtractResult` as a standalone function. Wire it into v3 dispatcher's `_HANDLERS["v2_google_doc"]` slot. Re-test v2's existing functionality. Pilot end-to-end via v3 on a real Google Doc.

**Why:** today, if the user picks a folder containing Google Docs through the admin UI, v3 deferred-skips them. The user has to know which file types are supported. Closing #11 means "select any folder, ingest all supported file types in one click" actually works.

**Estimated effort:** dedicated session, ~3-4 hours including v2 regression test.

**Key risks:**
- v2's Google Doc logic may be more entangled with v2-specific state than the design assumes
- Refactoring v2 risks regressing v2's existing 13-chunk path — must re-test
- The pilot Google Doc needs to come from the existing manifest, not be created fresh

### Other candidates (lower priority but valid)

- **BACKLOG #21** — folder-selection UI redesign (eliminate pending-panel redundancy + drive-vs-folder visual differentiation). Session 16 user-tested and confirmed this is the biggest friction point in the admin UI. Dedicated 60–90 min session.
- **BACKLOG #10** — reconcile `requirements.txt` with venv state. ~1 hour. Important for any new local dev clone.
- **BACKLOG #27** — self-host Google Fonts to fix the CSP error. ~30 min.
- **BACKLOG #23 + #14** — content-hash dedup + orphan cleanup (md5-based). Bundle, ~2 hours.


**Tech-lead recommendation: Option A.** Reasons:
1. Highest leverage per session-hour
2. Touches the largest fraction of the corpus (9,828 chunks)
3. Closes 4 BACKLOG items in one session
4. Sets up a cleaner foundation for any subsequent work (especially #20 inline citations, which depends on #18 having landed)

But Option B is also defensible if Dan wants to maximize "the admin UI works for everything" before doing more retrofit work. **It's Dan's call — surface both, recommend A, wait for the answer.**

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
- **Pipe commit stdout to a file**, not `| tail` — Step 9 of session 16 showed why.
- **Tech-lead volunteers architecture review at design-halt points.** When a design doc has a question mark or assumption, surface it as M-options (M1/M2/...) before code. (Session 15 lesson, validated again in session 16's M2 phantom-helper case.)
- **Read the Flask access log first** when debugging UI cache or save issues. (Session 16 lesson.)
- **Test in Chrome before Safari** for admin UI iterative work. (Session 16 lesson.)
- **When closing a BACKLOG item, verify in the environment where it manifested.** Real browser click-through for UI bugs, real query against live collection for data bugs. (Session 16 lesson, the matryoshka one.)
- **No deletions without approval + backup.**
- **No Railway writes from sessions.** Railway is read-only.
- **No touching legacy collections** (`rf_coaching_transcripts`, pre-scrub 584 A4M) without Dan's explicit OK.
- **Credentials ephemeral** — never read `.env` content into chat.
- **Never reference Dr. Christina / Dr. Chris / Dr. Massinople** in agent responses. Layer B scrub catches new content; legacy is not yet protected (BACKLOG #6b).
- **Dan does git operations**, not Claude.


---

## Budget for session 17

- **$1.00 interactive gate.** If any single task projects above $1.00 in API spend, halt and surface the cost to Dan before proceeding.
- **$25.00 hard refuse.** No single session should ever spend more than $25 in API calls. If a task projects above this, refuse and require explicit Dan approval.
- **Session 16 spent ~$0.021** of $1.00 — well under. Session 17 has the same envelope.

## Files you'll likely touch (depending on scope)

**For Option A (retrofit bundle):**
- `ingester/scrub.py` (or wherever the Layer B scrub helper lives)
- `rag_server/app.py` (`format_context()` migration)
- `config/nashat_sales.yaml`, `config/nashat_coaching.yaml` (inline citation prompting)
- New: `scripts/retrofit_coaching_scrub_s17.py` (one-time pass over the 9,224 chunks)
- New: `scripts/retrofit_display_subheading_s17.py` (one-time pass)
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

**For Option B (Google Doc adapter):**
- `ingester/loaders/drive_loader_v2.py` (extract `process_google_doc()`)
- `ingester/loaders/drive_loader_v3.py` (wire the new helper into `_HANDLERS["v2_google_doc"]`)
- `ingester/loaders/types/__init__.py` (maybe new locator type for Google Doc headings)
- New: `scripts/test_v3_google_doc_handler.py`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

## Files you should NOT touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via the audit module
- Anything under `rf-coaching-call-recordings/` — pure read-only data


## Step 0 cheat sheet (for quick reference at the start of session 17)

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -8

# Chroma baseline (expect 604)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks queryable (expect 7)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); print('v3 chunks:', len(r['ids']))"

# OCR cache (expect 29)
ls data/image_ocr_cache/*.json | wc -l

# Test suite (expect all green)
./venv/bin/python scripts/test_scrub_s13.py
./venv/bin/python scripts/test_scrub_wiring_s13.py
./venv/bin/python scripts/test_types_module.py
./venv/bin/python scripts/test_chunk_with_locators.py
./venv/bin/python scripts/test_format_context_s16.py
./venv/bin/python scripts/test_admin_save_endpoint_s16.py
GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py

# Drive auth
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"

# Admin UI process check
lsof -iTCP:5052 -sTCP:LISTEN -P -n

# Selection state shape
cat data/selection_state.json
```

If all of the above passes, print:
```
✓ Step 0 PASS — repo at <hash>, rf_reference_library: 604, v3: 7, OCR cache: 29,
  all tests green, admin UI on PID <pid>, selection_state v2 shape OK
```

Then proceed to Step 1.

---

## End of session 17 prompt

Session 16 closed Gap 2 with the Egg Health Guide as proof. The system has 604 chunks, the v3 PDF pipeline works end-to-end with scrub, the admin UI supports file-level selection in Safari, and four pre-existing UI bugs were fixed along the way. Session 17 picks up clean. Good luck.
