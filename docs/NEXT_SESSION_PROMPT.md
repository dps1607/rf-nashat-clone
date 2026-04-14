# NEXT SESSION PROMPT — session 15

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Sessions 9–14 all used a "step 0 reality check" before doing any work. It has paid for itself every single session — session 11 caught a deprecated SDK import, session 12 caught half-loaded DC tools, session 13 caught uncommitted session 12 work, **session 14 MISSED a dirty working tree** (4 modified files plus 1 untracked were on disk at Step 0 and I didn't notice until 20 minutes in). Session 15 Step 0 has to be more careful about `git status` — not just "does it say clean on first glance" but "what files are actually listed as modified or untracked."

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all gates. Stop and tell Dan if anything surprises you.

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 15 ok"); 2+2`.

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -8`.
   - Expected top commit: **a single session 14 commit** landing:
     - `admin_ui/app.py` (cookie patch + save-endpoint guard)
     - `admin_ui/manifest.py` (`is_folder` helper)
     - `admin_ui/static/folder-tree.js` + `folder-tree.css` (folder-only UI)
     - `ingester/loaders/drive_loader_v2.py` (OpenAI pre-flight + file-level dispatch)
     - `scripts/test_login_dan.py` (diagnostic, new)
     - `docs/HANDOVER.md` (session 14 entry)
     - `docs/NEXT_SESSION_PROMPT.md` (this file)
   - Below session 14: `0463c94`, `76903ac` (session 13 followups), `ac3f1fc` (session 13), `84fa22f` (session 11), etc.
   - **Working tree must be completely clean** — if `git status` shows ANY modified or untracked files, STOP and surface them to Dan before proceeding. Do not assume they're stale or safe to ignore.

4. **Reality-vs-prompt check.** Verify these against the actual filesystem:

   - **Chroma baseline.** `./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"`. Expected: **597** (595 from session 13 + 2 from session 14). If 595, session 14 rolled back — stop. If 598+, something wrote between sessions — stop.

   - **v2-ingested chunks queryable.** `col.get(where={"source_pipeline":"drive_loader_v2"}, limit=30)` — should return **13 chunk IDs** (11 from session 13 `ingest_run_id=8eb7bb77aedd4a4c`, 2 from session 14 `ingest_run_id=5fb763c8b9194f72`). At least 3 should have `name_replacements >= 1` (2 from session 13's supplement files, 1 from session 14's DFH landing page).

   - **Drive auth.** `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"` → `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.** `from google import genai; c = genai.Client(vertexai=True, project="rf-rag-ingester-493016", location="us-central1"); print(c.models.generate_content(model="gemini-2.5-flash", contents="Say 'ok' and nothing else.").text)` → `ok`.

   - **OpenAI auth (live, not just presence).** Source `.env` in a subshell (`set -a && . ./.env && set +a`), then a minimal `embeddings.create("test")` call. Session 14 added this as a pre-flight inside the v2 loader itself, but still run it at Step 0 to catch a broken key before getting deep into work. Never read `.env` contents into chat.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → **28** (27 from session 13 + 1 new from session 14's DFH landing page image). If 27, session 14's vision OCR didn't persist — investigate.

   - **Scrub module on disk, wired, tests passing.**
     ```
     ./venv/bin/python scripts/test_scrub_s13.py
     ./venv/bin/python scripts/test_scrub_wiring_s13.py
     ```
     Both should print `PASS`.

   - **v1 regression.** `./venv/bin/python -m ingester.loaders.drive_loader --selection-file /tmp/rf_pilot_selection.json --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 --dry-run 2>&1 | tail -15`. Expect `files ingested: 1`, 2 low-yield skips. If `/tmp/rf_pilot_selection.json` no longer exists (reboot wiped `/tmp/`), recreate it from HANDOVER session 10.

   - **v2 regression against real selection_state.json.** This is new for session 15. `cat data/selection_state.json` — should show `Designs for Health virtual dispensary` folder selection (or whatever Dan last saved in the UI; placeholder `["abc","def"]` is also acceptable as "fresh state"). If it's a real selection, run: `./venv/bin/python -m ingester.loaders.drive_loader_v2 --selection-file data/selection_state.json --dry-run 2>&1 | tail -20`. Dry-run should report files consistent with whatever folder is selected, exit 0, no tracebacks. If placeholder, skip this gate.

   - **Railway alive.** `curl -sI https://console.drnashatlatib.com | head -3` → HTTP/2 302.

If any check returns a surprise, stop and surface it.

---

## What happened in session 14 (critical context)

Session 14 **closed Gap 1** — the goal STATE_OF_PLAY has named since session 9. Full end-to-end: admin UI folder picker → `data/selection_state.json` → `drive_loader_v2` → `rf_reference_library` (595 → 597) → `rag_server /query` returning the new chunks as top-ranked results. Two new chunks from `Designs for Health virtual dispensary`: one pure-text supplement list, one with a vision-OCR'd logo. Real spend: ~$0.0004 total. Scrub fired once (`name_replacements=1` on the DFH landing page). No Railway writes.

**Session 14 also shipped** (via pre-existing uncommitted work that landed in the same commit, plus session 14's own additions):
- Folder-only enforcement in admin UI (server-side guard + file checkboxes removed from tree) — **this encodes an explicit decision that file-level selection is not supported today**
- Login cookie fix (`ADMIN_DEV_INSECURE_COOKIES` env var) for localhost HTTP dev
- OpenAI live pre-flight on v2 `--commit` (catches silent 401 before processing files)
- File-level dispatch in v2 loader (forward-compatible plumbing; dormant until v3 UI lands)

**Two findings from session 14 worth carrying forward:**

1. **Dirty-tree blind spot at Step 0.** Session 14 started with 4 modified files and 1 untracked on disk from a prior uncommitted session. I treated the tree as clean and got confused ~20 minutes in when I saw unfamiliar code in `admin_ui/app.py`. Session 15 must check `git status` carefully, full output, not just a scan for "clean."

2. **Don't poll long-lived shells to check file state.** When verifying file contents, use a fresh `start_process` + `cat`, not `read_process_output` on an old PID. Old shells' stdout buffers are concatenated histories and will mislead you.

---

## Reading order (after Step 0 passes)

1. **`docs/HANDOVER.md`** — session 14 entry at the top, in full. Session 13 for context if needed.
2. **`docs/STATE_OF_PLAY.md`** — needs a session 14 update marking Gap 1 as CLOSED and naming Gap 2 (v3 multi-type). **First writing task of session 15 is this update, before any new implementation work.**
3. **`docs/BACKLOG.md`** — read and verify the session 15 backlog commitments (listed below) have all been added. If any are missing, that's the second writing task of session 15.
4. **`ingester/loaders/drive_loader_v2.py` `run()` function around lines 480–620** — see the file-level dispatch code that landed in session 14. Understand it before touching v2.
5. **`admin_ui/app.py` save endpoint (`api_folders_save`)** — see the folder-only guard that landed in session 14. Understand it before touching folder-selection flow.

**Do NOT read:** session 7/8/9/10 HANDOVER entries beyond orientation, ADR_005/006, session-7 plans, `drive_loader.py` v1 body (frozen), A4M Lineage A dead code.

---

## What session 15 is actually for

Session 14 closed Gap 1 but left **seven named items** in its wake. Session 15's job is to pick the most load-bearing one and close it. The list, ordered by priority:

1. **BACKLOG.md entries for session 14's commitments** (small writing task, highest priority because everything downstream depends on these being captured):
   - **v3 multi-type loader** (PDF, images, sheets, slides, docx, plain text, audio/video transcription). Named requirement from Dan: "all files have to happen." Needs per-type scope, per-type cost/risk, likely spans 3–5 sessions.
   - **File-level selection UI + server unlock.** Loader dispatch already in place (session 14). UI needs to stop hiding file checkboxes; server guard needs to accept non-folder IDs. Naturally lands alongside v3.
   - **Scrub retrofit** for legacy collections (`rf_coaching_transcripts` 9,224 chunks + original 584 `rf_reference_library` chunks). Carried from session 13. Real liability — former-collaborator names still present in legacy data.
   - **Admin UI "save selection" visual feedback.** Button blinks with no toast on success/failure. Cost ~10 min of debugging in session 14. Pure UX.
   - **UI selection state reset on save failure.** When the server guard rejects a save, the UI keeps the stale selection in memory and the next click re-sends the rejected payload. Workaround: page reload. Related to #4.
   - **`/chat` endpoint 500'd on first test** in session 14 with a Claude API error about empty content. Used `/query` instead. Needs a 5-min look — maybe a payload shape issue, maybe a real bug.
   - **`scripts/test_login_dan.py` needs a `sys.path` shim** so it runs without `PYTHONPATH=.`.

2. **STATE_OF_PLAY.md update**: mark Gap 1 CLOSED, introduce Gap 2 = v3 multi-type, carry forward the other 6 items as tracked gaps under Gap 2's umbrella or as a separate "known issues" section.

3. **v3 multi-type scoping document** (`docs/plans/2026-04-XX-drive-loader-v3.md`). Don't start coding v3 in session 15. Write the design first, same level of care as the session 11 v2 design doc. Key questions to answer:
   - Which file types land in which order? (Dan's preference matters here — what's highest-volume in the reference library?)
   - Per-type extraction strategy: native libraries, vision OCR fallback, transcription pipelines, etc.
   - Per-type scrub validation — can the existing Layer B scrub catch collaborator names in each format, or does scrub need extensions?
   - Per-type cost model (vision $, OCR $, Whisper $, embedding $ per GB of source material)
   - File-level selection UI/server re-enablement as part of v3 rollout
   - Staircase: which type is the v3 pilot? (My tentative suggestion: PDF first, because PDFs are probably the highest-volume non-Google-Doc type in the reference library, and native text extraction is cheap before any OCR work.)
   - End-to-end proof criterion, same style as Gap 1 for Gap 2: one PDF ingested through the full pipeline, retrieved through rag_server, citations render.

### Session 15 staircase

1. **Step 1** — Step 0 reality check (above).
2. **Step 2** — BACKLOG.md updates for the 7 items. HALT and show Dan before moving on.
3. **Step 3** — STATE_OF_PLAY.md update. HALT and show Dan.
4. **Step 4** — v3 design doc first draft. This is the bulk of session 15. HALT at the "pilot type + staircase" section so Dan picks the pilot type, then continue writing.
5. **Step 5** — (stretch) fix the 2 cheap items from the backlog: `/chat` 500 debug + `test_login_dan.py` sys.path fix. Both are ~10 min of work each, both land in a session-15 cleanup commit.
6. **Step 6** — end-of-session commit. Dan runs git.

### Anti-goals for session 15

- NO v3 implementation code — design doc only
- NO modification of v1 or v2 loaders (they're working; leave them alone)
- NO touching `rf_coaching_transcripts`
- NO scrub retrofit execution (it's on the backlog for a later session)
- NO Railway writes
- NO bolting new file types onto v2 (all new file-type work goes into v3, fresh module)
- NO re-triggering the OCR eyeball gate
- NO git push/commit/add by Claude — Dan runs git
- NO "offering Dan a menu of session-scope options" — the governance names the task, proceed (session 13 lesson, still valid)
- NO writing premature handover messages mid-session — only at session end (session 14 lesson)

---

## Cost expectations

- Step 1 (reality check): $0
- Step 2 (backlog writes): $0
- Step 3 (STATE_OF_PLAY writes): $0
- Step 4 (v3 design doc): $0
- Step 5 (cheap fixes): $0 (no ingest work)
- **Total projected session 15 spend: $0**

Cost gates unchanged: $1.00 interactive, $25 hard refuse.

---

## Hard rules carried forward

- No ChromaDB writes without explicit Dan approval at the write moment
- No git operations by Claude
- No Railway operations
- No deletions without approval and verified backup
- Never reference Dr. Christina / Dr. Chris / Dr. Massinople / Massinople Park / Mass Park — scrub enforces at ingest; legacy chunks still unprotected (retrofit on backlog, not session 15)
- Public agent never accesses `rf_coaching_transcripts`
- Credentials ephemeral — never read `.env` into chat
- Use Desktop Commander for file writes (`create_file` writes to Claude's sandbox, not Dan's Mac)
- Before any commit-run, halt and show Dan the dump-json
- Pipe commit-run stdout to a file, not `| tail`
- **Step 0 checks `git status` carefully and treats ANY modified/untracked files as a surprise to surface** (session 14 lesson)
- **Don't write handover messages mid-session** (session 14 lesson)
- **Don't poll long-lived shells to check file state — use fresh processes** (session 14 lesson)

---

## Tech-lead mandate (unchanged)

Claude holds tech-lead role. Tactical decisions (guard tuning, scrub rules, loader wiring, ingest mechanics, admin UI integration, v3 per-type design) are Claude's call. Strategic decisions (irreversible operations, money spend > $25, Railway writes, cross-collection retrofits, anything failing the "can we fix this later?" test) get flagged to Dan first.

Session scope is not a "strategic decision." STATE_OF_PLAY, BACKLOG, and HANDOVER name what's next. Read them and proceed. Don't offer Dan a menu of session-scope options.

---

## Quick reference

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/` — **597 chunks in rf_reference_library as of session 14 end**
- Railway production: `https://console.drnashatlatib.com` (untouched)
- venv: `./venv/bin/python` (Python 3.11.3)
- v1 loader: `ingester/loaders/drive_loader.py` (frozen)
- v2 loader: `ingester/loaders/drive_loader_v2.py` (Google-Docs-only; OpenAI pre-flight + file-level dispatch added session 14)
- Shared helpers: `ingester/loaders/_drive_common.py` (chunking chokepoint, Layer B scrub wired)
- Scrub module: `ingester/text/scrub.py` (19/19 tests passing)
- Admin UI: `admin_ui/app.py` (ADMIN_DEV_INSECURE_COOKIES env var + save-endpoint folder-only guard) + `admin_ui/templates/folders.html` + `admin_ui/static/folder-tree.js` (file checkboxes hidden)
- Real selection state: `data/selection_state.json` — last used in session 14 to ingest `Designs for Health virtual dispensary`
- Session 13 run record: `data/ingest_runs/8eb7bb77aedd4a4c.json` (11 chunks)
- Session 14 run record: `data/ingest_runs/5fb763c8b9194f72.json` (2 chunks)
- GCP project: `rf-rag-ingester-493016`, region: `us-central1`, model: `gemini-2.5-flash`
- Service account: `/Users/danielsmith/.config/gcloud/rf-service-account.json` (mode 600)
- Diagnostic script: `scripts/test_login_dan.py` (bcrypt hash verification — run with `PYTHONPATH=.`)
- **Gap 1:** CLOSED in session 14
- **Gap 2:** v3 multi-type loader — session 15 design doc, later sessions implement
