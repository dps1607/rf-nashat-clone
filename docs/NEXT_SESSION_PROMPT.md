# NEXT SESSION PROMPT — session 14

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Sessions 9, 10, 11, 12, and 13 all used a "step 0 reality check" before doing any work. It has paid for itself five sessions in a row — session 11 caught a deprecated SDK import, session 12 caught that Desktop Commander was half-loaded, session 13 caught that session 12's work was uncommitted despite the prompt claiming otherwise. **Keep doing this.**

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all gates. Stop and tell Dan if anything surprises you.

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 14 ok"); 2+2`.

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -6`. Expected top commits:
   - `ac3f1fc session 13: wire scrub + v2 guard redesign + first v2 commit-run`
   - Possibly a session 13 followup commit on top of `ac3f1fc` closing the `__init__.py` / HANDOVER / NEXT_SESSION_PROMPT gap
   - `84fa22f session 11: drive loader v2 ...`
   - Working tree should be clean at session start.
   - **If `ingester/text/__init__.py` is untracked or missing, that's Step 1 of session 14.**

4. **Reality-vs-prompt check.** Verify these against the actual filesystem before reading the reading list:

   - **Chroma baseline.** `./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"`. Expected: **595**. If 584, session 13's commit-run was rolled back — stop and surface. If 596+, something else wrote between sessions — stop and investigate.

   - **v2-ingested chunks queryable.** Same Python session, `col.get(where={"source_pipeline":"drive_loader_v2"}, limit=20)` — should return **11 chunk IDs** of the shape `drive:1-operations:...:NNNN`. Two should have `metadata.name_replacements == 1`, nine should have `== 0`, zero should contain "christina" or "massinople" in document text.

   - **Drive auth.** `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"` → `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.** `from google import genai; c = genai.Client(vertexai=True, project="rf-rag-ingester-493016", location="us-central1"); print(c.models.generate_content(model="gemini-2.5-flash", contents="Say 'ok' and nothing else.").text)` → `ok`.

   - **OpenAI auth.** Source `.env` in a subshell (`set -a && . ./.env && set +a`), then a minimal `embeddings.create("test")` call. **This gate is new for session 14** because session 13 wasted time on a silent 401 in the commit path. If it fails, stop and fix before any ingest work. (Never read `.env` contents into chat.)

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → **27**. Do NOT re-trigger the eyeball gate.

   - **Scrub module on disk, wired, tests passing.**
     ```
     ./venv/bin/python scripts/test_scrub_s13.py
     ./venv/bin/python scripts/test_scrub_wiring_s13.py
     ```
     Both should print `PASS`.

   - **v1 regression.** `./venv/bin/python -m ingester.loaders.drive_loader --selection-file /tmp/rf_pilot_selection.json --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 --dry-run 2>&1 | tail -15`. Expect `files ingested: 1`, 2 low-yield skips, 1 unsupported spreadsheet. If `/tmp/rf_pilot_selection.json` no longer exists (reboot wiped `/tmp/`), recreate it from HANDOVER session 10.

   - **Railway alive.** `curl -sI https://console.drnashatlatib.com | head -3` → HTTP/2 302.

If any check returns a surprise, stop and surface it.

---

## What happened in session 13 (critical context)

Session 13 finished what session 12 detoured around: wired the name-scrub into the single chunking chokepoint (`_drive_common.chunk_text()`) so both v1 and v2 now scrub automatically, redesigned v2's low-yield guard from a broken ratio check to an absolute word floor with usable-images gate, fixed the dump-json skip-path bug, added a persistent `skipped_files_log.jsonl` audit trail, and **landed the first v2 commit-run** — 11 chunks into local `rf_reference_library`, taking it from 584 to 595. Full details in `docs/HANDOVER.md` session 13 entry (read that first).

**One latent bug session 13 left open** (expected to be fixed in the session 13 followup commit before session 14 starts): `ingester/text/__init__.py` was never committed even though `ingester/text/scrub.py` was. A fresh clone would `ImportError` on first v1 or v2 invocation. If Step 0 reveals this is unfixed, **that's Step 1 of session 14**.

**Two findings worth carrying forward:**
1. The session 11 "halted on guard" was a `NameError`, not a legitimate skip. Don't re-derive history from that framing.
2. Commit-path errors get swallowed when stdout is piped through `| tail`. Always pipe to a file or check `$?` on commit runs.

---

## Reading order (after Step 0 passes)

1. **`docs/HANDOVER.md`** — session 13 entry at the top, in full. Session 11 entry for v2 background if needed.
2. **`docs/STATE_OF_PLAY.md`** — re-read "Gap 1" language in the main body and the session 10 amendment at the bottom. Session 14's goal is closing Gap 1.
3. **`admin_ui/app.py`** (folder-selection routes + save endpoint) and **`admin_ui/templates/folders.html`** — you'll drive this UI, so know what it does today. Focus: how `data/selection_state.json` gets written, what "save selections" persists, whether there's a downstream trigger.
4. **`data/selection_state.json`** — literally read current contents. Still `["abc","def"]` as of session 13 end. Confirm.
5. **`ingester/loaders/drive_loader_v2.py` `run()` + `load_and_validate_selection()` in `_drive_common.py`** — confirm v2 reads real selection state cleanly. It should.

**Do NOT read:** session 7/8/9 HANDOVER entries beyond orientation, ADR_005/006, session-7 plans, `drive_loader.py` v1 (frozen), A4M Lineage A dead code, image review viewer.

---

## The actual goal for session 14 — close Gap 1

STATE_OF_PLAY has named the same goal since session 9: **drive the folder-selection UI end-to-end with a real folder, through real `data/selection_state.json`, to a real ingestion event in `rf_reference_library`.** Sessions 10–13 all made real progress on the pieces but none closed the gap itself — they all bypassed `selection_state.json` via `/tmp/rf_pilot_selection.json`. The v2 loader now works end-to-end against real data (session 13 proved this). Session 14 does the thing the governance has been pointing at for six sessions: the actual end-to-end UI-driven ingest.

### Staircase (same pattern as sessions 10–13)

1. **Step 1 — Session 13 followup commit (if not already landed).** Add the files that should have been in `ac3f1fc` or a companion commit:
   - `ingester/text/__init__.py` (latent import bug fix)
   - `docs/HANDOVER.md` session 13 entry
   - `docs/NEXT_SESSION_PROMPT.md` (this document)
   - `scripts/build_image_review.py` (session 12 straggler)

   Also add `!data/ingest_runs/` and `!data/ingest_runs/*.json` to `.gitignore` so run records are trackable, and `git add data/ingest_runs/8eb7bb77aedd4a4c.json` to back-fill the session 13 run record. Dan runs git; Claude suggests. **If already landed at session start, skip to Step 2.**

2. **Step 2 — Open the admin UI and pick a real folder.** Dan runs this interactively; Claude cannot drive a browser. Dan opens the admin UI (local or production — see open question below), navigates to the folder picker, selects **one** real folder to ingest, assigns it to `rf_reference_library`, hits save. This writes `data/selection_state.json` with real content instead of the `["abc","def"]` placeholder.
   - **Open question for Dan:** which folder? Obvious candidate is the parent of Supplement Info (so session 14 ingests more reference content) but Dan's call.
   - **Second open question:** local admin_ui or production admin_ui? Production is the real end-to-end test; local is safer for the first run. **Claude's lean:** local first, then repeat on production as validation if local works cleanly.
   - **HALT for Dan to pick folder + run the UI action before Claude proceeds.**

3. **Step 3 — Verify `data/selection_state.json` on disk.** After Dan saves in the UI, Claude reads `data/selection_state.json` and confirms: (a) no longer placeholder, (b) folder ID and library assignment match Dan's selection, (c) schema is what `load_and_validate_selection()` expects. Any schema mismatch between admin_ui's writes and v2's reads is a bug to fix before ingesting.

4. **Step 4 — Pre-flight OpenAI key check.** Add the ~10-line pre-flight to `drive_loader_v2.py`'s commit path: on `--commit`, make a minimal `embeddings.create` call before processing files; bail on error with a clear message. Carries forward from session 13's backlog. ~5 minutes of work.

5. **Step 5 — v2 dry-run against real `selection_state.json`.** Same command as session 13 but without `/tmp/` bypass:
   ```
   ./venv/bin/python -m ingester.loaders.drive_loader_v2 \
       --selection-file data/selection_state.json \
       --dry-run --dump-json data/dumps/s14_real_selection_dryrun.json
   ```
   Show Dan: summary, file list with stitched word counts, skips with preview, `name_replacements` counts, projected cost. **HALT for Dan's approval before commit-run.** Watch for: unexpected file types (v2 only handles Google Docs; everything else is `unsupported_mime_v2`), high vision cost (should be small if folder is similar to Supplement Info), scrub hits on collaborator names (flag if surprising).

6. **Step 6 — v2 commit-run against real `selection_state.json`** (only with explicit Dan approval). Same command with `--commit`. Write to local `rf_reference_library`. Verify via direct Chroma query that chunk count incremented by expected amount. **Zero Railway writes.**

7. **Step 7 — Post-commit sanity test via the deployed agent.** Start `rag_server` locally, make a test query that should retrieve one of the newly-ingested chunks. Confirm the agent returns it with coherent citations (exercises the display-field normalization from session 10). End-to-end proof: UI → selection → ingest → retrieval → citation. **Gap 1 closed.**

### Stop conditions (any of which is a successful session 14)

- Session 13 followup lands + real `selection_state.json` written via UI + v2 dry-run works + v2 commit-run adds chunks + retrieval smoke test returns them cleanly = **full success, Gap 1 closed**
- Followup lands + real `selection_state.json` written + dry-run surfaces a bug blocking commit-run = **success** (the end-to-end hookup revealed a real issue; fix, commit, defer commit-run to session 15)
- Followup lands + admin_ui cannot write `selection_state.json` in expected shape + pivot to fixing the admin_ui save endpoint = **also success** (Gap 1's blocker is now named and addressable)

### Anti-goals for session 14 (unchanged from session 13)

- NO push of v2 to Railway
- NO modification of v1 except via `_drive_common` if absolutely required
- NO touching `rf_coaching_transcripts`
- NO scrub retrofit against existing collections (separate backlog item — session 14 is not the time)
- NO bolting PDF/Slides/image-file support onto v2 (out of scope)
- NO re-triggering the OCR eyeball gate
- NO touching ADR_006, session-7 plans, or anything frozen
- NO git push/commit/add by Claude — Dan runs git

---

## Cost expectations

- Steps 1–4: $0
- Step 5 (dry-run against real selection): $0 vision if same folder types as Supplement Info; otherwise new vision spend proportional to new image count. **If projected > $1.00, HALT for Dan approval before running.**
- Step 6 (commit-run): $0 vision (cache should absorb), embedding spend proportional to chunk count
- Step 7 (retrieval smoke test): $0 (local Chroma + Claude Sonnet generation)

**Total session 14 projected: < $0.01**, unless the real folder has significantly more images than Supplement Info.

Cost gates unchanged: $1.00 interactive, $25 hard refuse.

---

## Hard rules carried forward

- No ChromaDB writes without explicit Dan approval at the write moment
- No git operations by Claude
- No Railway operations
- No deletions without approval and verified backup
- Never reference Dr. Christina / Dr. Chris / Dr. Massinople / Massinople Park / Mass Park — scrub enforces at ingest; 9,224+584 legacy chunks still unprotected, that's a future-session concern
- Public agent never accesses `rf_coaching_transcripts`
- Credentials ephemeral — never read `.env` into chat
- **Use Desktop Commander for file writes.** `create_file` writes to Claude's sandbox, not Dan's Mac.
- **Before any commit-run, halt and show Dan the dump-json.**
- **Pipe commit-run stdout to a file, not `| tail`, so exit codes and errors aren't swallowed.** (Session 13 lesson.)

---

## Tech-lead mandate (updated for session 14)

Claude holds tech-lead role. Tactical decisions (guard tuning, scrub rules, loader wiring, ingest mechanics, admin UI integration) are Claude's call. Strategic decisions (irreversible operations, money spend > $25, Railway writes, cross-collection retrofits, anything failing the "can we fix this later?" test) get flagged to Dan first.

**Session scope is not a "strategic decision."** The governance (STATE_OF_PLAY, BACKLOG, HANDOVER) names what's next. Claude reads those and proceeds. If the governance is ambiguous, Claude picks the tactically sensible option and notes the call in the HANDOVER entry. **Session 13 wasted a turn by offering Dan a menu of session-14 options instead of reading the governance and proceeding.** Don't repeat that pattern.

---

## Quick reference

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/` — **595 chunks in rf_reference_library as of session 13 end** (+11 via v2)
- Railway production: `https://console.drnashatlatib.com` (untouched)
- venv: `./venv/bin/python` (Python 3.11.3)
- v1 loader: `ingester/loaders/drive_loader.py` (frozen; imports from `_drive_common`)
- v2 loader: `ingester/loaders/drive_loader_v2.py` (proven working session 13)
- Shared helpers: `ingester/loaders/_drive_common.py` (chunking chokepoint, Layer B scrub wired)
- Scrub module: `ingester/text/scrub.py` (19/19 tests passing) — **check `ingester/text/__init__.py` exists**
- Admin UI: `admin_ui/app.py` + `admin_ui/templates/folders.html` + `admin_ui/static/folder-tree.js`
- Real selection state target: `data/selection_state.json` (placeholder at session 13 end)
- Session 13 run record: `data/ingest_runs/8eb7bb77aedd4a4c.json`
- Session 13 dry-run dump: `data/dumps/supplement_info_pilot_v2_s13.json`
- GCP project: `rf-rag-ingester-493016`, region: `us-central1`, model: `gemini-2.5-flash`
- Service account: `/Users/danielsmith/.config/gcloud/rf-service-account.json` (mode 600)
- Pilot folder through session 13: Supplement Info, ID `1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`, drive `1-operations`
- Session 14 folder: **TBD by Dan in Step 2**
