# RF Nashat RAG — Handover (living cursor)

Updated in place each session-end. Read this first to resume.

> **Orientation note (added session 9):** The session 7 entry below is preserved as history. **It is no longer authoritative for next-session work.** For current state of the system and the actual next-session goal, read `docs/STATE_OF_PLAY.md` first. Then read this file's session 9 entry (immediately below) for the stabilization summary. Then read whatever older entries the current task actually needs — but do not re-derive Plan 1, Plan 2, or Plan 3 from session 7 without first reading STATE_OF_PLAY.md in full.

---

## Session 15 — 2026-04-14 — Governance catch-up + v3 design (no v3 code)

**Goal (from NEXT_SESSION_PROMPT):** governance catch-up after session 14
closed Gap 1. Not implementation work. Specifically: (1) add 7 named
backlog items, (2) update STATE_OF_PLAY to mark Gap 1 CLOSED and
introduce Gap 2, (3) write v3 multi-type loader design doc (halt at
pilot-type section for Dan to pick), (4) stretch: fix `/chat` 500 +
`test_login_dan.py` sys.path shim.

**Outcome:** All 4 targets hit. Design doc is complete through session
staircase. Pilot type locked to PDF. Two stretch items both resolved
(one fixed, one closed as unreproducible). No v3 code written. No
Chroma writes. No Railway writes. No git operations by Claude. Session
spend: $0 interactive + 1 coaching `/chat` call for repro (Sonnet 4.6,
~$0.01, well under gates).

**Step 0 reality check:** all 12 gates green. Working tree clean, top
commit `d33d6a9`, `rf_reference_library` count 597, 13 v2-ingested
chunks with 3 showing `name_replacements ≥ 1`, Drive/Vertex/OpenAI all
live, OCR cache at 28, scrub tests 19/19 + wiring PASS, v1 regression
1 ingested + 2 low-yield skips, v2 regression 2 files / 2 chunks /
$0.0002 / cache hit on DFH logo, Railway HTTP/2 302. No drift. The
dirty-tree miss from session 14 did not recur — checked `git status`
carefully per the updated Step 0 rule.

### What shipped

**Documentation:**

- `docs/BACKLOG.md` — added 7 session-15 items at top under new dated
  section:
  1. v3 multi-type Drive loader (Gap 2), scope + anti-scope + 3–5
     session span
  2. File-level selection UI + server unlock (pairs with v3)
  3. Scrub retrofit for legacy collections (carried from session 13;
     upgraded to Medium-High based on session 15 coaching `/chat`
     repro — see 6b below)
  4. Admin UI save-toast feedback
  5. UI selection state reset on save failure
  6. `/chat` endpoint 500 debug → **closed this session**, could not
     reproduce
  6b. Scrub retrofit priority upgrade based on session 15 observation
      (active liability visible at user-facing retrieval surface)
  7. `test_login_dan.py` sys.path shim → **done this session**

- `docs/STATE_OF_PLAY.md` — appended a session 14/15 amendment:
  - Gap 1 marked CLOSED with full roundtrip evidence (595 → 597,
    $0.0004, scrub fired once)
  - Session 14's other shipped items noted (folder-only enforcement,
    cookie fix, OpenAI pre-flight, file-level dispatch plumbing)
  - Gap 2 introduced and defined (v3 multi-type loader, Dan's "all
    file types" requirement quoted, closure proof shape specified)
  - Other gaps tracked under Gap 2's umbrella
  - "What did NOT change" section preserved (Railway, legacy
    collections, ADR_006, etc.)

- `docs/plans/2026-04-14-drive-loader-v3.md` — 738-line design doc,
  design only, no v3 code this session:
  - Why v3 exists (Dan's requirement quoted)
  - Scope (DOES / does NOT)
  - D1–D12 architectural decisions:
    - D1: fresh module + `types/` subdirectory
    - D2 (revised mid-session per Dan's question about architecture
      stability): MIME dispatch with v2 Google Docs adapter for mixed
      selections — v3 is the single admin-UI entry point, Google Docs
      route internally to v2's existing `process_google_doc()`, unified
      run records
    - D3: shared `extract()` signature / `ExtractResult` dataclass
    - D4: per-type extraction strategy table
    - D5: per-type cost model with $1/$25 gate carryover
    - D6: per-type scrub validation + mandatory
      `test_scrub_v3_handlers.py` test file
    - D7 (added mid-session per architecture review): citation
      rendering for non-prose types — new `display_locator` and
      `display_timestamp` optional fields with per-handler population
      rules. Renderer stays dumb, handlers format their own locators.
    - D8: file-level UI/server unlock gated to v3 pilot
    - D9: `selection_state.json` schema unchanged
    - D10: run records and dump-json carry forward
    - D11: no eyeball gate
    - D12 (added mid-session per architecture review): per-file
      try/except + quarantine + `--retry-quarantine` flag + 50%
      hard-fail threshold. Non-negotiable for stability at scale.
  - End-to-end Gap 2 closure criterion (9 numbered points)
  - Pilot type section with 5 candidates analyzed → **Dan picked
    Option A (PDF)**
  - Session staircase (PDF-scoped): session 16 deliverables (7 items),
    session 17 conditional hardening pass, sessions 18–23+ tentative
    handler ordering (image, docx, slides, sheets, plaintext, AV)
  - Out-of-scope list
  - Explicit "what session 15 is NOT doing" section

**Code:**

- `scripts/test_login_dan.py` — added `sys.path` shim computing repo
  root from `__file__` and prepending to `sys.path` before the
  `from admin_ui.auth import ...` line. Docstring updated to drop
  `PYTHONPATH=.` from usage. Verified it imports and runs from a clean
  env. (BACKLOG #7 closed.)

**No code changes to:** v1 loader, v2 loader, admin_ui, rag_server,
`_drive_common.py`, scrub module, any test file (other than
`test_login_dan.py`).

**No ChromaDB writes. No Railway operations. No git operations by
Claude.**

### Mid-session architecture review (Dan's question)

After writing D1–D10 and halting for pilot-type pick, Dan asked whether
this was the right architecture for stability and performance at
build-out scale. The review surfaced three gaps in the design as
originally drafted:

1. **No per-file failure isolation.** v2 got away without it because
   runs were small. v3 runs will hit 50+ files across multiple types,
   where one bad PDF or a Gemini 429 could kill the whole run. Added
   **D12 quarantine + retry flag** before starting session 16.

2. **Citation rendering was under-specified for non-prose types.** The
   session-9 5-field display normalization (source/subheading/speaker/
   date/topics) works for lectures and coaching but doesn't cleanly
   fit sheets (row ranges), slides (slide numbers), PDFs (page
   numbers), or AV (timestamps). Each handler would have invented its
   own shape, re-creating the Gap-1-era inconsistency in a new form.
   Added **D7 with `display_locator` and `display_timestamp` optional
   fields** and per-handler population table. Existing A4M and
   coaching chunks unaffected — new fields are additive, renderer
   elides when null.

3. **Google-Docs-routes-to-v2 was wrong for the admin UI.** Original
   D2 said v3 would skip Google Docs and force users to run v2
   separately. Correct for CLI use, confusing for "one button" admin
   UI use. **Revised D2** to have v3 call into v2's existing
   `process_google_doc()` internally via a thin adapter, with unified
   run records. v2 stays frozen as a standalone loader for direct CLI
   users; v3 is the single entry point the admin UI invokes.

Also noted but not added to D-list (governance/process, not architecture):

- **Per-handler smoke tests in Step 0** of every session that has
  v3 handlers built. Each handler ships with a known-good test file
  and a scrub pattern assertion. Dependency upgrades (pdfplumber,
  openpyxl, python-docx, python-pptx) can silently break a handler;
  Step 0 should catch it before ingest work.

### Stretch items

**BACKLOG #7 — `test_login_dan.py` sys.path shim: DONE.** Standard
`os.path`-computed-from-`__file__` shim. Verified it works from a
clean env with `PYTHONPATH` unset. ~5 min of work as estimated.

**BACKLOG #6 — `/chat` 500 debug: CLOSED, could not reproduce.**

Session 14 saw a 500 with a "Claude API empty content" error on first
test of `/chat` after closing Gap 1. Session 15 attempted reproduction
on the same commit (`d33d6a9`, same Chroma, same `.env`):

- **Sales agent** (`nashat_sales`, `public_default` mode, `rf_reference_library`
  only): 2 test calls (one substantive DFH query, one `"test"`), both
  HTTP 200 with well-formed Sonnet 4.6 responses + 5 cited chunks.
- **Coaching agent** (`nashat_coaching`, `internal_full` mode, both
  collections): 1 test call ("What do coaches typically recommend for
  egg quality?"), HTTP 200, 8 chunks retrieved (5 coaching + 3
  reference), full response.

`call_claude()` in `rag_server/app.py` wraps the API call in try/except
and returns error strings — a genuine 500 would have come from
somewhere else in the handler (retrieve_for_mode or format_context on
a code path not yet exercised).

Closed BACKLOG #6 with a closure note specifying: if it recurs, capture
the actual traceback from server stderr (not the HTTP body), the curl
command, the loaded agent, and the loaded mode. Without those, the
next investigation will hit the same dead end.

### Session 15 observation — scrub retrofit liability is concrete

The coaching-agent `/chat` test for BACKLOG #6 repro surfaced something
worth escalating. The 5 coaching chunks returned by that single query
contained:

- `coaches: "Dr. Christina"` in metadata (multiple chunks)
- `coaches: "Dr. Nashat + Dr. Christina"` in metadata (2 chunks)
- Chunk text with `[Dr. Christina]` prefixing transcript speaker lines
  (at least one chunk)

The Sonnet 4.6 response correctly did not echo the former-collaborator
name, but the raw chunk payload returned to the caller still contains
them. This means BACKLOG #3 (scrub retrofit for legacy collections) is
not a theoretical liability — it's active at the user-facing retrieval
surface on every coaching query.

**Added this as BACKLOG #6b**, raising the retrofit priority from
Medium to Medium-High. Retrofit plan itself unchanged (read-only count,
approval, one-shot in-place update, backup, no re-embedding — see
BACKLOG #3). Just raising the urgency signal.

**When:** next session after v3 pilot (session 16 or 17). Not session 15.

### What this session did NOT do

- Write any v3 code (`drive_loader_v3.py`, handlers, dispatcher) — as
  planned
- Modify v1 or v2 loaders — as planned
- Run any ingestion — as planned
- Write to any Chroma collection — as planned
- Touch Railway — as planned
- Build `test_scrub_v3_handlers.py` — it's a session 16 deliverable
- Refresh `NEXT_SESSION_PROMPT.md` for session 16 — Dan does this
  between sessions or session 16 does it as Step 1

### Key lessons carried forward

- **Session 14's "check `git status` carefully" rule worked.** Step 0
  caught nothing because there was nothing to catch, but the careful
  read was the right habit.
- **Architecture review mid-design saved three D-items of drift.** Dan
  asked the right question at the right time ("is this the right
  architecture for stability at scale?") and three gaps surfaced that
  would have bitten in sessions 17–20. Process note: tech-lead should
  volunteer this review at the design-halt point in future
  architecture sessions, not wait for Dan to ask.
- **"Could not reproduce" is a valid closure state** as long as the
  recovery path is documented. A permanently open bug with no
  reproducer eats session budget every time a future session tries to
  "finally fix it." Better to close with a "if it recurs, capture X Y
  Z" note.
- **`/chat` coaching test surfaced a real liability** that the theoretical
  retrofit plan had underweighted. Repro tests are worth doing even when
  they succeed — the 200s taught me something the 500 would not have.

### Files modified

- `docs/BACKLOG.md` — 7 items added, 2 updated with closure notes,
  1 new item (6b) added mid-session
- `docs/STATE_OF_PLAY.md` — session 14/15 amendment appended
- `docs/plans/2026-04-14-drive-loader-v3.md` — NEW, 738 lines
- `scripts/test_login_dan.py` — sys.path shim + docstring update
- `docs/HANDOVER.md` — this entry (first writing in session)

### Ready for Dan's end-of-session commit

Suggested commit message:

    session 15: governance catch-up + v3 design (PDF pilot)

    - BACKLOG.md: add 7 items, close #6 (unreproducible) + #7 (done),
      add #6b upgrading scrub retrofit priority
    - STATE_OF_PLAY.md: Gap 1 CLOSED, Gap 2 introduced (v3 multi-type)
    - docs/plans/2026-04-14-drive-loader-v3.md: NEW, D1-D12 decisions,
      PDF pilot locked, session 16-23+ staircase
    - scripts/test_login_dan.py: sys.path shim so it runs without
      PYTHONPATH=.

    No v3 code. No Chroma writes. No Railway ops. No v1/v2 changes.

---

## Session 14 — 2026-04-13 — GAP 1 CLOSED: end-to-end UI → selection → ingest → retrieval

**Scope shipped:** full end-to-end roundtrip from admin_ui folder picker through `data/selection_state.json` through v2 ingest through `rf_reference_library` through rag_server semantic retrieval, proved with a live query. **`rf_reference_library`: 595 → 597** (2 new chunks from `Designs for Health virtual dispensary`, run_id `5fb763c8b9194f72`). Real spend: ~$0.0004 total (vision $0.0002, embedding $0.0002). No Railway writes. No git operations by Claude.

**Gap 1 is closed.** STATE_OF_PLAY has named this as the goal since session 9; sessions 10, 11, 12, 13 all made real progress on pieces but all bypassed `selection_state.json` via `/tmp/rf_pilot_selection.json`. Session 14 stopped bypassing. Next major gap: **v3 multi-type loader** (see BACKLOG).

**Step 0 reality check:** passed all functional gates but **missed a dirty working tree** — 4 files modified at session start that weren't mine (admin_ui folder-only enforcement work from a prior uncommitted session). Surfaced mid-session after reading `admin_ui/app.py` diff and seeing unfamiliar save-endpoint guard code. Cost ~20 min of confusion and one premature "partial handover" message that had to be walked back. Step 0 for session 15 must check `git status` in full, not just "working tree clean on first glance."

### What landed

1. **Login fix: `ADMIN_DEV_INSECURE_COOKIES` env var** (`admin_ui/app.py`). `SESSION_COOKIE_SECURE=True` combined with `session_cookie_secure=True` in Talisman was silently dropping session cookies when admin_ui ran on localhost HTTP — POST `/login` succeeded (audit log confirmed `login_success` events), but the browser discarded the `Secure`-flagged cookie on a plain HTTP response, so `@login_required` bounced the user back to `/login?next=/edit` in a loop. Patch: both cookie flags now read from `_SESSION_COOKIE_SECURE = not os.environ.get("ADMIN_DEV_INSECURE_COOKIES") == "1"`. Default is still `True` (production Cloudflare/Railway unchanged). Local dev opts in with `ADMIN_DEV_INSECURE_COOKIES=1` and gets a stderr warning at startup. Fully reversible, production behavior preserved.

2. **OpenAI pre-flight on `--commit`** (`ingester/loaders/drive_loader_v2.py`). Session 13 wasted effort on a silent 401 from an expired key that passed the presence check but failed on first real embedding call. Added a ~15-line live pre-flight: on `--commit` only, make a minimal `embeddings.create(model="text-embedding-3-large", input="preflight")` call before processing any files; bail with a clear message on any exception. Verified firing in the session 14 commit-run (`openai preflight: OK`). Dry-runs unaffected (pre-flight is gated on `commit`, keeping dry-runs free).

3. **File-level selection dispatch in v2** (`ingester/loaders/drive_loader_v2.py`, ~60 lines). Added a pre-resolve step before the main ingest loop that classifies each entry in `selected_folders` via `drive_client.get_file()`. Folders route to the existing `list_children` path unchanged. Files are grouped by parent folder and fed into the main loop as "virtual folder" entries with a prebuilt file list, skipping `list_children`. Dedup: if a folder AND files inside that folder are both selected, the folder walk subsumes the file-level entries. Design rationale: forward-compatible with v3 multi-type work — when PDF/image/sheet handlers land in v3, they plug into the same file branch. **Harmless in session 14 because Option A (folder-only) was picked,** but the code is in place for v3's benefit. Loop header changed from `for folder_id in selected:` to `for folder_id, library, prebuilt_files in resolved_entries:`; the list_children call is now gated on `prebuilt_files is None`.

4. **Pre-existing folder-only enforcement work committed alongside session 14** (NOT authored in session 14, but landing in the same commit). These were on disk uncommitted at session start and I missed them in Step 0:
   - `admin_ui/app.py` — server-side guard in `/admin/api/folders/save` rejecting any selected ID that isn't a folder in the manifest; returns clean 400 with first-offender ID
   - `admin_ui/manifest.py` — `is_folder(fid)` helper for the guard
   - `admin_ui/static/folder-tree.js` — file checkbox rendering removed from the tree UI
   - `admin_ui/static/folder-tree.css` — styling support for the above
   
   Decision made in-session (Option A, explicitly confirmed by Dan): keep folder-only as the current behavior. File-level selection is a permanent requirement but belongs to the v3 multi-type effort, not session 14. The v2 dispatch code from point 3 above is the loader half of file-level support; the UI and server guard are the UI half that will need reversing in v3.

5. **`scripts/test_login_dan.py`** — diagnostic kept for future login debugging. Prompts for a password via `getpass`, runs it through the exact `authenticate()` path admin_ui uses, prints PASS/FAIL. Password never touches chat or logs. Used in session 14 to rule out bcrypt-hash mismatch before finding the cookie bug.

### End-to-end proof (Gap 1)

Full roundtrip, all in session 14:

1. **UI save** — Dan opened http://localhost:5052, selected `Designs for Health virtual dispensary` under `7. Supplements`, assigned `rf_reference_library`, hit save. `audit.jsonl` logged `folder_selection_saved` at 04:18:53 UTC, 1 folder, user `dan`.
2. **File on disk** — `data/selection_state.json` contained exactly 1 folder ID `18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM` with correct library assignment, valid schema.
3. **Dry-run** — v2 against real `data/selection_state.json`: 2 files seen, 2 ingested, 0 skipped. `Wish list for PL of DFH supps - 9/23` (536 words, 0 images) and `DFH Virtual Dispensary landing page` (247 words, 1 image). Projected spend $0.0002.
4. **Commit-run** — exit 0, `openai preflight: OK`, `wrote 2/2 chunks`, run record `data/ingest_runs/5fb763c8b9194f72.json`.
5. **Chroma direct query** — `rf_reference_library.count() == 597`, both new chunk IDs retrievable with full metadata populated (`source_pipeline=drive_loader_v2`, `source_collection=rf_reference_library`, `display_*` fields set).
6. **Scrub fired** — `DFH Virtual Dispensary landing page` chunk has `name_replacements=1`. Something in that doc had a former-collaborator name; Layer B replaced it with "Dr. Nashat Latib" at ingest time. Confirms scrub is wired into v2's write path, not just the tests.
7. **rag_server retrieval** — started locally on :5051, health endpoint reported `loaded_collections.rf_reference_library: 597`. POST `/query` with question "What supplements does Designs for Health offer for private label?" returned the two new chunks as top-2 results (distances 0.346 / 0.428), followed by session 13 supplement chunks. End-to-end proven.

### Known issues captured (not fixed in session 14 — BACKLOG fodder)

- **`/chat` endpoint 500'd on first test** with a `messages.0: user messages must have non-empty content` Claude API error. Used `/query` (raw retrieval) instead to close Gap 1. Retrieval layer proven; Claude-generated citation response not proven. 5-min look in session 15.
- **Admin UI "save selection" button has no visual feedback.** POST succeeds (200 OK logged, audit entry written) but nothing changes on screen. Cost ~10 min of "I hit save, nothing happened" debugging during session 14. Pure UX, low priority.
- **UI cascade leaves stale in-memory state after failing saves.** When the save-endpoint guard rejects a selection (e.g., cascaded file IDs), the UI's `selectionState` object doesn't reset, so the next click sends the same rejected payload. Workaround: reload the page. Related to the lack of visual feedback above.
- **`scripts/test_login_dan.py` has an import-path foot-gun.** Needs `PYTHONPATH=.` to find `admin_ui.auth`. Either fix the script to add the repo root to `sys.path`, or document it in the file header. Documented in the file header for session 14; script-path fix is session 15 cleanup.

### Process failures in session 14 (for the record)

- **Missed dirty working tree at Step 0.** Should have been caught by the first `git status`. Cost ~20 min of mid-session confusion when I misread the pre-existing changes as someone "working in parallel" and wrote a panicked handover message. Session 15 Step 0 must check `git status` carefully.
- **Misread polled process output as current state.** When I tried to check `selection_state.json` via `read_process_output`, I got back a buffer that concatenated hours of old output — mistook a stale `cat` result for the live file contents. Switched to `start_process` + direct `cat` and the actual state became clear. Lesson: for file state checks, always use a fresh process, never poll a long-lived shell.
- **Wrote a premature "session ended, handover for session 15" message** based on the misread above, then had to retract it when Dan asked "what happened, there's only one session open." Cost conversational trust. **Rule going forward: do not write handover messages mid-session unless the session is genuinely over.**
- **Login-cookie debug took ~15 min** when the audit log already showed `login_success` for user `dan` — that alone should have told me auth was working and the bug was in session handling. Should have checked cookie config immediately. Lesson: when auth logs say success but the user sees a redirect loop, session cookies are the first suspect, not auth.

### State at session end

- **`rf_reference_library`:** 597 chunks (13 via `drive_loader_v2`, 584 via `drive_loader`/pre-scrub legacy)
- **Working tree before commit:** 5 modified files (listed above), 1 untracked (`scripts/test_login_dan.py`). Everything listed gets committed as session 14. Clean afterward.
- **Branch:** `main`, 4 commits ahead of `origin/main` (unpushed session 13 followup work carried forward, plus the forthcoming session 14 commit = 5 ahead). Push is Dan's call.
- **Admin UI:** still running on :5052, PID `11300`, started by Dan with `ADMIN_DEV_INSECURE_COOKIES=1`, serves current (patched) code. No need to restart for session 15 unless cookie/auth behavior is under test.
- **rag_server:** stopped at end of session 14 (was only started for Step 7 smoke test).
- **Hard rules honored:** no git by Claude, no Railway writes, no non-approved deletions, no references to scrubbed collaborator names, no credentials persisted.

---

## Session 13 — 2026-04-13 — Wire scrub, redesign v2 guard, first v2 commit-run

**Scope shipped:** triple-dedup edge case fixed in `scrub.py`, `scrub_text()` wired into `_drive_common.chunk_text()` as the single chokepoint for v1+v2, v2 low-yield guard redesigned from ratio-based to absolute-word-floor with usable-images check, dump-json skip-path bug fixed, persistent `skipped_files_log.jsonl` audit trail added, **first v2 commit-run landed: 11 chunks into local `rf_reference_library` (584 → 595).** Real spend: $0.0012 embeddings, $0 vision (54/54 cache hits). No Railway writes. No git operations by Claude.

**Step 0 reality check:** PASSED all gates. One drift caught and surfaced immediately: session 12's work (scrub module + image review script) was uncommitted at session start — the bootstrap prompt claimed "session 12 committed" but `git log` showed `84fa22f session 11` as the top commit. Non-blocking (the prompt body itself allowed for either state), but worth flagging as exactly the kind of premise-vs-reality drift Step 0 exists to catch.

### What landed

1. **Scrub triple-dedup fix** (`ingester/text/scrub.py`). Added one pattern to `DEDUP_PATTERNS`: `CANONICAL\s*,\s*and\s+CANONICAL`. The existing pairwise `", "` pattern was collapsing the first two in `A, A, and A` to leave `A, and A` — which no existing pattern matched. The new pattern plus the existing 3-iteration stability loop now composes cleanly for arbitrary-length "and"-chain triples. Test battery at `scripts/test_scrub_s13.py` (19 cases including all session 12 positive/negative cases plus the triple plus negative controls for `body mass index`, `Merry Christmas`, `lean body mass and mass spectrometry`) — **19/19 passing**.

2. **Scrub wired into the chunking chokepoint** (`ingester/loaders/_drive_common.py`). `chunk_text()` now imports `scrub_text` and applies it at both append sites (mid-loop chunk close and end-of-function trailing chunk). `word_count` is recomputed from the scrubbed text so it reflects what's actually stored, and `name_replacements` is added to the chunk dict. `build_metadata_base()` propagates `name_replacements` into chunk metadata via `chunk.get("name_replacements", 0)`. **Single chokepoint: both v1 and v2 get scrub coverage automatically**, no per-loader wiring. v1 regression dry-run against Supplement Info matches baseline byte-for-byte.

3. **v2 low-yield guard redesigned** (`ingester/loaders/drive_loader_v2.py`). The inherited v1 ratio check (`stitched_chars / drive_size < 5%`) was semantically wrong for v2 — stitched OCR text compared to compressed-PNG byte size is apples-to-oranges and would skip legitimate image-heavy docs. Replaced with:

   ```
   MIN_STITCHED_WORDS_FLOOR = 50
   skip as low_yield_even_with_vision IF
       stitched_words < 50 AND usable_images == 0
   ```

   The `AND` is load-bearing: Canva IG posts (future `rf_published_content` work) are often short but carry one usable image, so the usable-images check protects them even with a tight word floor. Rationale cross-checked against the real 27-image OCR cache (median 28 words per usable image, 0 decorative, 0 failed).

4. **v2 dump-json skip-path bug fixed.** Session 11 left `all_files_dumped.append(...)` missing on both skip paths (`low_yield_even_with_vision` and `vision_failure_rate_too_high`), so the dump-json only captured ingested files. Fix: both skip paths now append to `all_files_dumped` with full stitched text + per-image OCR records + `"skipped": true` + `"skip_reason"` flag. To make this work for the vision-failure path, `stitched_chars`/`stitched_words` computation moved above the failure-rate gate.

5. **Persistent skipped-files audit log** (`data/skipped_files_log.jsonl`). New `log_skipped_file()` helper in `drive_loader_v2.py` appends one JSON line per skip decision, across all runs. Fields: `run_id`, `timestamp_utc`, `pipeline`, `reason`, `file_id`, `file_name`, `folder_id`, `folder_path`, `details`. Best-effort — write failures log a warning but do not block ingest. Grep-able, tail-able, easy to audit months later. Dan asked for "clear access to the skipped folder" and this is the persistent version of that ask. Gitignored under the existing `data/` rule.

6. **Run summary now shows skip previews.** For each low-yield skip, the run summary prints `Nw stitched, X/Y usable images` plus a 160-char preview of the stitched text, so you see exactly what's being dropped before a commit.

7. **First v2 commit-run.** After dry-run review and Dan's explicit `commit` approval: 3 files ingested (Professional Nutritionals FKP Schedule, Comprehensive List of Supplements and substitutions, Supplement Details), 1 skipped (spreadsheet via `unsupported_mime_v2` path), **11 total chunks written to local `rf_reference_library` (584 → 595 verified).** All 11 chunks queryable via `where={"source_pipeline": "drive_loader_v2"}`. `name_replacements` metadata populated correctly: 2 chunks show `=1` (the cover-image chunks from both image-heavy docs where the `Dr. Nashat Latib & Dr. Christina Massinople` byline lived), 9 show `=0`. **Leak check across all 11 committed chunks: 0 occurrences of "christina" or "massinople" (case-insensitive).** Run record written to `data/ingest_runs/8eb7bb77aedd4a4c.json` with all chunk IDs, fully reversible via `col.delete(ids=run_record["chunk_ids"])`.

### Critical findings

**The session 11 "halted on guard" was actually a latent `NameError`, not a legitimate skip.** Session 11's v2 used `LOW_YIELD_RATIO_THRESHOLD` and `LOW_YIELD_MIN_BYTES` in the body of `run()` without importing them. The broken session 11 dump (1 of 3 files) was v2 crashing on the first file that exceeded 10 KB — which for Supplement Info is every file. Neither session 11 nor session 12 caught this because session 12 detoured to the scrub work. Session 13's guard redesign replaces the whole broken block, so the NameError is moot — but it's worth recording so future sessions don't re-derive a misleading history from "session 11 halted on guard."

**Commit-path errors get swallowed when stdout is piped through `| tail`.** The first Step 6 commit attempt failed with `openai.AuthenticationError: 401` (expired API key in `.env`), but `| tail -60` made the exit code look like 0 and the error scroll past. Had to re-run with `> /tmp/log 2>&1; echo $?` to see the real state. Paper cut worth remembering; a ~10-line OpenAI pre-flight check at the top of the commit path would have turned the 15-second failure into a 1-second one. On the session 14 backlog.

**Security housekeeping done this session.** Two temp log files (`/tmp/s13_commit.log`, `/tmp/s13_commit2.log`) and one diagnostic script contained echoed API key fragments in OpenAI error output and were deleted immediately after diagnosis. `.env` sourced in subshells only, never read into chat context.

### State of the world after session 13

- `rf_reference_library` local: **595 chunks** (+11 vs start of session), of which 11 are `source_pipeline=drive_loader_v2` and the original 584 are the A4M Fertility Certification material from Lineage B.
- `rf_coaching_transcripts` local: 9,224 chunks, **unchanged.**
- Railway production: **untouched.** `console.drnashatlatib.com` still serving the 2026-04-09 deploy.
- `data/selection_state.json`: **still the placeholder `["abc","def"]`.** Session 13 used `/tmp/rf_pilot_selection.json` as a bypass, just like sessions 10–12. Closing this gap is session 14's job — Gap 1 from STATE_OF_PLAY is still half-open.
- `data/ingest_runs/8eb7bb77aedd4a4c.json`: new run record, reversible. (Gitignored by the existing `data/` rule; see open item.)
- `data/skipped_files_log.jsonl`: **not yet written** (nothing tripped a content guard this session — the only skip was a spreadsheet via `unsupported_mime_v2`, which is a different code path). Will be created on first real skip.
- Scrub module: **canonical Layer B.** Any chunk written through `_drive_common.chunk_text()` — both v1 and v2 — gets scrubbed at ingest time. The **9,224 coaching transcript chunks and the original 584 reference library chunks are unprotected** because they were embedded before scrub existed. This is a known gap; see open items.

### Files touched

**Modified, committed in `ac3f1fc`:**
- `ingester/text/scrub.py` (dedup pattern added)
- `ingester/loaders/_drive_common.py` (scrub import + wiring + metadata propagation + docstring)
- `ingester/loaders/drive_loader_v2.py` (new constants, `log_skipped_file()` helper, guard redesign, dump-json skip-path fix, moved stitched_words computation, cleaned summary output)

**Added, committed in `ac3f1fc`:**
- `scripts/test_scrub_s13.py` — 19-case scrub unit battery
- `scripts/test_scrub_wiring_s13.py` — scrub+chunk_text smoke test
- `scripts/inspect_v2_dump_s13.py` — dump-json inspection helper (reusable)

**Latent bug in `ac3f1fc`, fixed in session 13 followup commit:**
- `ingester/text/__init__.py` was never committed. Session 12 created it as an empty package marker; session 13 imported from it successfully because the working tree had it, but `ac3f1fc` staged `scrub.py` without its sibling `__init__.py`. Any fresh clone would `ImportError` on first v1 or v2 invocation. Followup commit closes this.

**Gitignored by the existing `data/` rule (not tracked):**
- `data/dumps/supplement_info_pilot_v2_s13.json` — dry-run dump, regenerable
- `data/ingest_runs/8eb7bb77aedd4a4c.json` — reversibility run record. **Recommend whitelisting `data/ingest_runs/` in session 14** so run records are in git going forward.

**Not touched:** v1 loader (only flows through `_drive_common`), any existing Chroma collection except the additive v2 write, Railway, `.env`, any session-7-era plan or ADR.

### Guardrails honored

- Railway production: untouched ✓
- `rf_coaching_transcripts`: zero reads-with-side-effects ✓
- ChromaDB writes: only the approved v2 commit-run, preceded by dry-run and explicit `commit` approval ✓
- Git operations by Claude: zero ✓
- Dr. Christina / Dr. Chris / Dr. Massinople / Massinople Park / Mass Park: **zero references in any committed chunk text** ✓ (case-insensitive check across all 11 new chunks)
- Credentials in chat: zero ✓

### Open items for session 14 (in priority order)

1. **Commit `ingester/text/__init__.py` plus the session 13 followup artifacts** (this HANDOVER entry, new `NEXT_SESSION_PROMPT.md`, `scripts/build_image_review.py` session 12 straggler). Latent import bug from `ac3f1fc` needs closing before any new code lands.

2. **Drive the folder-selection UI end-to-end with real `data/selection_state.json`.** This is Gap 1 from STATE_OF_PLAY and has been the stated goal since session 9. Sessions 10–13 have all bypassed it via `/tmp/rf_pilot_selection.json`. The v2 loader now works, proven against real data. Session 14's job: select a real folder via the admin UI, persist real state, run v2 ingest off that state (not `/tmp/`), confirm end-to-end. This is the "natural next major piece of work" STATE_OF_PLAY's session 10 amendment pointed at, with v2 now in place.

3. **OpenAI pre-flight check on commit path.** ~10 lines. Would have turned today's 15-second auth failure into a 1-second one. Low effort, high value.

4. **Route `unsupported_mime_v2` (spreadsheets, PDFs, etc.) through `log_skipped_file()`.** That skip path is currently un-instrumented — it doesn't flow through `all_files_dumped` or `skipped_files_log.jsonl`. ~8 lines.

5. **Whitelist `data/ingest_runs/` in `.gitignore`.** Run records are the reversibility audit trail for every commit-run; they belong in git. Add `!data/ingest_runs/` + `!data/ingest_runs/*.json` after the existing `data/` ignore line. Back-fill `8eb7bb77aedd4a4c.json` in the same commit.

6. **Scrub retrofit against existing collections is NOT on session 14's path.** The 9,224 coaching transcript chunks and the original 584 A4M reference chunks are unprotected by scrub. If Dr. Christina / Dr. Chris appears in that content (likely for coaching transcripts — Christina was a co-coach before the split), the Nashat agent could leak the name via retrieval. This is a real correctness/liability concern and belongs as a named BACKLOG.md item, but it is not the work of session 14. Flagging here so it doesn't drift. Add it to BACKLOG.md as part of the session 13 followup commit.

### Session 13 cost summary

- Scrub fix, wiring, guard writeup, guard code: $0
- v2 dry-run: $0 vision (54/54 cache hits), $0 embedding (dry-run)
- v2 commit-run: $0 vision, ~$0.0012 embedding (real spend)
- **Total session 13: ~$0.0012 real spend.** Projected was <$0.001; the ~$0.0002 overage is noise-level. Well under any cost gate.

---

## Session 11 — 2026-04-13 — Drive loader v2 (built + dry-run, halted on guard tuning)

**Scope shipped:** v2 Drive loader (HTML export + Gemini 2.5 Flash vision OCR) built end-to-end, refactored v1 with regression-verified equivalence, executed two dry-runs against Supplement Info, confirmed OCR quality is excellent on real product images. **Halted before guard redesign and commit-run per staircase.** No ChromaDB writes. No Railway changes. No git operations by Claude. Total real spend: $0.0045 vision.

**Step 0 reality check:** PASSED all five gates. Gemini Vertex AI smoke test passed on first run — Dan's IAM grant of `roles/aiplatform.user` landed cleanly between sessions 10 and 11. One surprise surfaced and resolved: `vertexai.generative_models` import path is deprecated June 24 2026; Dan approved switching to the `google-genai` SDK in Vertex AI mode for forward compatibility. Verified working with the same service account.

### What landed

1. **Design doc** (`docs/plans/2026-04-13-drive-loader-v2.md`, 309 lines). Full spec of 14 decisions, pilot success criteria, flow diagram, staircase. Read this before touching v2.

2. **Shared helpers extracted** (`ingester/loaders/_drive_common.py`, 348 lines). Extracted from v1's body: constants, manifest lookup, `normalize_text`, `chunk_text`, `build_chunk_id`, `build_metadata_base`, `assert_local_chroma_path`, `load_and_validate_selection`. Single source of truth for v1 and v2.

3. **v1 patched** (`ingester/loaders/drive_loader.py`, 827 → 522 lines). Imports from `_drive_common`; `build_metadata` is a thin wrapper over `build_metadata_base` with `source_pipeline="drive_loader_v1"`. **Regression dry-run against Supplement Info matches session 10 byte-for-byte:** 1 ingested, 2 low_text_yield (Comprehensive 0.07%, Supplement Details 0.45%), 1 unsupported_mime, 1 chunk, $0.0001. Refactor is safe.

4. **Vision stack** (new):
   - `ingester/vision/__init__.py`
   - `ingester/vision/ocr_cache.py` (97 lines) — SHA-256 keyed disk cache. Keys on image bytes (not URLs, which expire in HTML exports). Atomic writes via tmp-rename. Prompt-version invalidation. Hit/miss stats.
   - `ingester/vision/gemini_client.py` (179 lines) — `google-genai` Vertex AI client (lazy-init so v1 doesn't pay the import cost). `VisionLedger` tracks `images_seen / ocr_called / cache_hit / decorative / failed`, input/output tokens, and `vision_cost_usd` computed live from `VISION_INPUT_PRICE_PER_1M = 0.075` and `VISION_OUTPUT_PRICE_PER_1M = 0.30`. **Canva-aware OCR prompt** (`PROMPT_VERSION = "v1"`) with 4 categories: product labels, infographics/charts/designed visuals, medical/clinical figures, `DECORATIVE`. Per-image error resilience: failures logged to ledger and returned as result objects with `failed=True`, never raised — a single bad image cannot abort a file.

5. **v2 loader** (`ingester/loaders/drive_loader_v2.py`, ~830 lines):
   - `export_html()` — Drive API export with `mimeType="text/html"`
   - `walk_html_in_order()` — BeautifulSoup (stdlib `html.parser`) tree walk preserving prose + `<img>` positions in document order. Handles block-level containers (`p`, `h1-h6`, `li`, `div`, `td`, `blockquote`, etc.) by flushing text buffers around embedded images so ordering is preserved inside blocks.
   - `resolve_image_bytes()` — decodes base64 data URIs (the common case, see finding below) with HTTP fallback for absolute URLs
   - `stitch_stream()` — produces `[IMAGE #N: ...]` markers inline at document positions, drops `DECORATIVE` responses, writes `OCR_FAILED — <80-char-reason>` or `DOWNLOAD_FAILED — <80-char-reason>` markers for error cases (80-char cap prevents base64 leakage — see fix below)
   - `count_image_words_in_chunk()` — populates the v2 metadata field `image_derived_word_count` per chunk
   - **Hard gates**: refuses `/data/*` Chroma, refuses placeholder selection, refuses missing assignments, refuses libraries outside `ALLOWED_LIBRARIES`, requires `OPENAI_API_KEY` on commit, requires `GOOGLE_APPLICATION_CREDENTIALS`/`GOOGLE_SERVICE_ACCOUNT_JSON` (same service account does Drive AND Vertex AI), interactive `y/N` gate at $1.00 vision spend, hard refuse at $25.00 without `--allow-strategic-spend`, per-file vision failure rate ceiling at 20% (min 5 images) → skip as `vision_failure_rate_too_high`
   - **v2 low-yield guard**: same 5% threshold / 10 KB floor as v1, but numerator is `len(stitched_text)`. **This guard is wrong for v2 — see Critical findings below.**
   - **CLI**: `--selection-file`, `--folder-id`, `--dry-run`/`--commit`, `--dump-json PATH`, `--no-cache`, `--allow-strategic-spend`, `--verbose`

### Dry-runs executed

**Run 1** (first attempt, pre-patch): Surfaced **two bugs**, both caught by the staircase before any commit. Zero actual spend.

- **Bug A**: my design-doc assumption that Drive HTML export serves images via authenticated `googleusercontent.com` URLs was wrong. The real behavior is **images are inlined as `data:image/png;base64,...` URIs directly in the HTML**. My `download_image_bytes()` tried to HTTP-fetch those and every call raised "Only absolute URIs are allowed". This is actually better news than the assumption — no auth round-trip, no network latency, more reliable — we just need to decode instead of fetch.
- **Bug B**: the error messages from Bug A were inserted verbatim into the stitched text stream, leaking multi-megabyte base64 payloads into `stitched_text`. The 4.3 MB Comprehensive doc "stitched" to 6 million chars / 542 words — those chars were base64 garbage inside `DOWNLOAD_FAILED` markers. Embedding-cost gate would have caught this at $0.39 but commit-run was still halted by the staircase design.

**Patches applied** (same session):
- Replaced `download_image_bytes` with `resolve_image_bytes`: detects `data:` scheme and decodes base64 locally via stdlib, falls back to authorized HTTP fetch for `http(s)://` URLs
- Capped `DOWNLOAD_FAILED` reason strings at 80 characters (defense-in-depth against any future edge case leaking payload into chunks)

**Run 2** (post-patch): Vision pipeline works end-to-end. Cleaner numbers:

- **Professional Nutritionals FKP Schedule**: 0 images, 2,006 chars / 360 words, 1 chunk — same as v1, makes it through.
- **Comprehensive List of Supplements and substitutions**: 4.33 MB on Drive, 6.26 MB HTML export, 104 text blocks + 27 images in stream, **stitched to 16,801 chars / 2,583 words**. Skipped by guard at 0.39% yield (threshold 5%).
- **Supplement Details**: 522 KB on Drive, 6.20 MB HTML export, 91 text blocks + 27 images, **stitched to 16,511 chars / 2,543 words**. Skipped by guard at 3.16% yield.
- Supplement List with Brands: spreadsheet, `unsupported_mime_v2`, skipped (expected).
- **Vision ledger**: 54 images seen, 27 OCR'd, **27 cache hits** (the second doc's images are duplicates of the first doc's — SHA-256 cache earning its keep immediately), 0 decorative, 0 failed. 39,732 input tokens, 5,078 output tokens, **$0.0045 vision spend**.

### Critical findings

1. **The OCR output is excellent.** Verified by reading the on-disk cache files directly (`data/image_ocr_cache/*.json`). Representative samples:
   - **Pure Encapsulations** Liver-G.I. Detox, 120 capsules, full dietary supplement facts panel
   - **Designs for Health** L-Glutamine 120 vegetarian capsules, Magnesium Chelate (Bisglycinate) 120 tablets, Stellar C (Vitamin C + Bioflavonoids) 90 vegetarian capsules
   - **Douglas Laboratories** Quell Fish Oil EPA/DHA Plus D, 60 softgels
   - Full supplement facts panels with mg doses, % daily values, ingredient lists (Alpha lipoic acid 100mg, NAC 100mg, Turmeric 100mg std to 95% curcuminoids, Milk thistle 125mg std to 80% silymarin...)
   - Melatonin 3mg product with lot number MEL060-6 and full "Other Ingredients" transcription
   
   This is exactly the content the v1 guard was correctly refusing to guess at and exactly why v2 exists. Gemini 2.5 Flash is reading Canva-designed product photos accurately enough to be ingestion-grade.

2. **The v2 low-yield guard is incorrect as designed, and blocks both image-heavy docs.** The 5% threshold was a v1 heuristic based on "exported plain text chars ÷ drive size bytes," where drive size correlates with text content volume. In v2, drive size is dominated by embedded image bytes — a 4.3 MB doc that's 95% product photos has ~15 KB of prose plus 4.3 MB of images, and OCR adds ~16 KB of descriptive text back. The **ratio against drive size is now measuring the wrong thing** — it treats a successful vision extraction as a failure because the OCR output volume is tiny relative to the image payload volume.
   
   The guard's original purpose was "detect when plain-text export dropped the content." For v2 the analogous question is "detect when HTML export AND vision OCR together produced nothing usable." A better metric: **absolute stitched word count floor plus a non-decorative image produced condition**. Proposed: skip only if `stitched_words < 200 AND (images_seen == 0 OR all_images_decorative_or_failed)`. This lets through any doc where Gemini actually got something out of the images, regardless of drive size ratio. Rejected alternative: "lower the ratio to 0.3%" — that just chases the specific numbers in this pilot and would miss the conceptual fix.

3. **The dump-json artifact is broken for the most important files.** When `low_yield_even_with_vision` fires, the file's stitched text and per-image OCR records are **dropped from the dump entirely** — only a tiny skip record with filename and ratio lands in `low_yield_skipped[]`. This is a dump-inspection bug: the dump is supposed to be the halt-for-Dan inspection artifact, and it currently omits the exact files we most need to inspect. The bug lives in the dry-run branch of `run()` where `all_files_dumped` only gets appended inside the ingest path, not inside the skip-after-stitch path. Needs a one-sided fix.
   
   **Workaround this session**: I eyeballed OCR quality by reading the cache files directly (27 JSONs at `data/image_ocr_cache/`, each containing `ocr_text` + token counts keyed by SHA-256). The cache has the content; the dump currently doesn't. Session 12 fix should append to `all_files_dumped` before the skip `continue`, not after the chunk-write loop.

### What's in the cache (session 12 starts free here)

27 OCR results in `data/image_ocr_cache/` are keyed by image SHA-256. Any re-run of v2 against Supplement Info is **zero vision spend** — the cache rehydrates everything. A session 12 dry-run to validate the guard fix should complete in ~15 seconds at $0.00. The cache survives restarts. **This is a significant carry-forward**: the expensive validation work is done.

### Files touched this session

**New:**
- `docs/plans/2026-04-13-drive-loader-v2.md` (309 lines)
- `ingester/loaders/_drive_common.py` (348 lines)
- `ingester/loaders/drive_loader_v2.py` (~830 lines)
- `ingester/vision/__init__.py`
- `ingester/vision/ocr_cache.py` (97 lines)
- `ingester/vision/gemini_client.py` (179 lines)
- `data/dumps/supplement_info_pilot_v2.json` (inspection artifact, currently incomplete per finding 3)
- `data/image_ocr_cache/` (27 JSONs, ~20 KB total, runtime dir — should be gitignored)

**Modified:**
- `ingester/loaders/drive_loader.py` (behavior-preserving refactor; 827 → 522 lines)

**New pip dependencies installed in venv:**
- `google-cloud-aiplatform-1.147.0` (pulls in `google-genai-1.72.0` as dep — the SDK actually used)
- `beautifulsoup4-4.14.3`, `soupsieve-2.8.3`

**Not touched**: `ingester/config.py`, `ingester/drive_client.py`, `admin_ui/`, `rag_server/`, any ChromaDB collection, Railway, git, `.env`, any doc under `docs/` except the new v2 design doc.

### Hard rules honored (verbatim from sessions 7–10)

- No ChromaDB writes ✓ (dry-run only; cache writes go only to `data/image_ocr_cache/`)
- No Railway operations ✓ (v2 refuses `/data/` paths in code)
- No git operations by Claude ✓
- No deletions ✓
- No reference to Dr. Christina ✓ (n/a — Drive content)
- Credentials ephemeral ✓ (`.env` not re-read; service account JSON referenced by path only)
- Desktop Commander used throughout ✓ (no `create_file`; all writes via heredoc to disk)

### Cost this session

- Vision: $0.0045 (54 image calls, 27 unique + 27 cache hits)
- Embedding: $0 (no commit)
- **Total: $0.0045**

Well under the $1.00 interactive gate and $25 hard gate. Zero strategic spend used.

### What session 12 should do (in order)

**Step 0**: same reality check as sessions 9/10/11. Tool load, repo state, drive auth, Gemini smoke test (should still be green, no IAM changes expected). Crucially, **verify the OCR cache is still present** at `data/image_ocr_cache/` — 27 files. If present, session 12's dry-runs cost $0. If the user blew it away between sessions, a fresh dry-run costs ~$0.0045.

**Step 1 — eyeball gate (the halt Dan asked for at session 11 end).** Read cache files directly and show Dan representative OCR samples so he can sign off on OCR quality before any guard change. Session 11 saw Pure Encapsulations, Designs for Health, Douglas Labs product transcriptions — but Dan has not personally confirmed these are accurate transcriptions of his actual product images. **Do not change the guard until Dan has personally OK'd the OCR output.**

**Step 2 — guard redesign**, assuming Dan greenlights OCR quality. Replace the ratio-based `LOW_YIELD_RATIO_THRESHOLD` with an absolute-floor + signal-present test. Proposed logic (Claude's tactical call, flag to Dan before coding):
```
skip with reason "low_yield_even_with_vision" IF:
    stitched_words < MIN_STITCHED_WORDS_FLOOR   # proposed: 200
    AND (
        images_seen == 0
        OR all(image is decorative or failed for image in images)
    )
```
This lets through any doc where Gemini actually got text out of at least one non-decorative image, regardless of the ratio against drive size. The v1 ratio guard is preserved in `_drive_common.py` and still used by v1 unchanged — only v2 gets the new logic.

**Step 3 — dump-json fix**. Append `all_files_dumped` entry before the `continue` on each skip path inside `run()`, so the dump captures the full stitched text + per-image records for skipped files too. This is the inspection artifact's whole job and it's currently failing at exactly the wrong moment.

**Step 4 — re-run dry-run against Supplement Info with fixes**. Expected: 3 files ingest (Professional Nutritionals + Comprehensive + Supplement Details), 1 skipped (spreadsheet), ~0–5 chunks total across the two image-heavy docs (given ~2,500 words each and a 700-word chunk ceiling). Cost: $0 vision (cache), ~$0.0001 embedding estimate. **HALT for Dan to eyeball the full dump-json.**

**Step 5 — only with explicit Dan approval**, commit-run against Supplement Info into local Chroma. Expected: ~5 chunks into `rf_reference_library`, collection grows 584 → ~589. Reversible via chunk IDs in the run record (`data/ingest_runs/<id>.json`).

### Stop conditions any of which makes session 12 a success

- Guard fix lands, v2 dry-run shows Comprehensive + Supplement Details both ingesting with coherent chunks containing recognizable supplement brand names
- v2 commit-run into local Chroma, chunks queryable
- Dan pushes back on OCR quality and we iterate the prompt (the `PROMPT_VERSION = "v1"` bump invalidates the cache automatically; a prompt change is cheap to test — ~$0.005 for a fresh cache fill)

### Anti-goals for session 12 (same as session 11)

- Do NOT push v2 to Railway
- Do NOT delete or modify v1 except via `_drive_common` (refactor already done)
- Do NOT ingest any folder besides Supplement Info
- Do NOT bolt PDF/Slides/image-file support onto v2
- Do NOT touch ADR_006, the three session-7 plans, or anything under "frozen"

### Deferred / still-on-the-backlog

- `.gitignore` entry for `data/image_ocr_cache/` — not added this session, should be added before any git commit lands v2
- Visual sanity-test of the session-10 library-picker UI in a real browser — still not done
- Embedding-cost gate for v2 should use the same $1.00 threshold as the v1 gate; currently v2 prints a `COST WARNING` but doesn't gate (minor)
- v2's `unsupported_mime_v2` skip reason should probably be renamed to just `unsupported_mime` for consistency with v1 (cosmetic)

### Cost prediction for session 12

- Step 1 eyeball: $0 (reading cache)
- Step 4 dry-run post-fix: $0 (cache hit) + ~$0.0001 embedding estimate in dry-run print
- Step 5 commit-run: ~$0.0001 embedding actual, $0 vision
- **Total session 12 projected: < $0.001**

---

## Session 10 — 2026-04-13 — Drive loader pilot (dry-run only)

**Scope shipped:** Re-Scope B from session-10 staircase. Library-picker UI patch + Drive content loader (dry-run only). NO actual ingest. NO embedding spend. NO Chroma writes. NO Railway changes.

**Step 0 reality check:** PASSED. All five session-9 verification gates green. No drift from STATE_OF_PLAY's description of the world.

### What landed

1. **Design doc**: `docs/plans/2026-04-13-drive-loader-pilot.md` — full architecture, metadata schema, CLI shape, hard rules. Read this before touching `ingester/loaders/drive_loader.py`.

2. **Library-picker UI** (closes Gap 1 from STATE_OF_PLAY):
   - `admin_ui/templates/folders.html` — added Pending Selections panel between toolbar and tree
   - `admin_ui/static/folder-tree.js` — `renderPendingSelections()`, `getFolderDisplayInfo()`, dropdown wiring, modified save handler. Functional: hooks into `cascadeDown`/`updateParentCheck` via wrapper-reassignment trick at IIFE init time.
   - `admin_ui/static/folder-tree.css` — pending panel styling, +116 lines, all using existing CSS vars
   - `admin_ui/app.py` — `/admin/api/folders/save` now validates: every selected folder has a library assignment AND every assignment is in `ALLOWED_LIBRARIES = {"rf_reference_library"}`. Returns HTTP 400 on violation.
   - **Verified end to end** with Flask test client: 3 reject scenarios (empty assignments, partial assignments, bad library name) + 1 accept scenario (writes correct JSON to disk).

3. **Drive loader** (closes Gap 2 from STATE_OF_PLAY, dry-run only):
   - `ingester/loaders/__init__.py` — package marker
   - `ingester/loaders/drive_loader.py` — 723 lines. CLI tool. Reads `selection_state.json`, fetches Drive folder contents via the existing `DriveClient`, exports Google Docs to plain text, chunks paragraph-aware, and (in commit mode) embeds via OpenAI `text-embedding-3-large` and writes to local Chroma.
   - **Hard guards in code (not docs)**: refuses to run if `CHROMA_DB_PATH` starts with `/data/`, refuses placeholder `["abc","def"]`, refuses missing assignments, refuses non-allowed libraries, requires `OPENAI_API_KEY` for `--commit`. `--dry-run` is the default; `--commit` must be passed explicitly.
   - **Metadata schema**: 21 fields per chunk including `source_folder_id` (Interpretation-3 slicing key for future per-clone work) and the 5 `display_*` fields (forward-compat with the read-time normalizer side quest from STATE_OF_PLAY). Does NOT use ADR_006 marker flags or QPT flags — those remain frozen.
   - **Chunk ID format**: `drive:{drive_slug}:{file_id}:{chunk_index:04d}`. Collision-proof against existing `a4m-m{N}-{type}-{NNN}` and `CHUNK-{N}-{N}` formats.
   - **Chunking**: paragraph-aware sliding window, 700-word ceiling, 80-word floor, paragraph-level overlap. Sentence-level repack for over-long paragraphs. NOT LLM-driven (the v3 LLM chunker is wrong fit for non-Q&A content).

4. **Pilot dry-run executed** against `Supplement Info` (folder `1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54` in `1-operations`, 4 files: 3 Google Docs + 1 Sheet). Result: 3 files ingested → 3 chunks, 1 file skipped (`unsupported_mime` — spreadsheet support deferred), estimated cost $0.0002. No writes.

5. **`normalize_text` BOM fix**: Drive's `text/plain` export prepends U+FEFF and may include other zero-width chars. Loader strips them at normalization time. Re-verified after fix.

### Critical findings for whoever picks up the loader work

1. **Google Doc text export is lossy.** The "Comprehensive List of Supplements and substitutions" file is 4.3 MB on disk (per Drive metadata) but only ~3 KB / 294 words after `text/plain` export. Tables, images, embedded objects, and rich formatting do not survive. **Implication**: a v2 loader probably needs HTML or DOCX export instead of plain text, OR a separate visual-aware path for content-rich documents. The v1 chunker is therefore functionally untested against multi-chunk content because every pilot file fit in a single chunk — every chunk count was 1.

2. **The picker dropdown is single-option in v1.** Only `rf_reference_library` is in `AVAILABLE_LIBRARIES`. Adding `rf_published_content` is a one-line change once that collection exists. Coaching is intentionally excluded for HIPAA/category reasons.

3. **`data/selection_state.json` is still the placeholder `["abc","def"]`.** I did not touch it. The pilot run used `/tmp/rf_pilot_selection.json`. The real file gets written when you click save in the browser, OR when a future session drives the loader against a real selection.

4. **Visual UI not tested in browser.** Only the data path was tested (via Flask test client). You'll want to spin up the admin UI locally and click through the Pending Selections panel before considering this UI ready for Nashat to use.

### Hard rules honored (verbatim from sessions 7, 8, 9)
- No ChromaDB writes ✓ (dry-run only)
- No Railway operations ✓ (loader actively refuses `/data/` paths)
- No git operations by Claude ✓ (Dan runs git)
- No deletions ✓
- No reference to Dr. Christina ✓ (n/a — Drive content)
- Credentials ephemeral ✓ (`.env` was read once for verification, dropped from working memory at Dan's instruction; will not be re-read)

### Tree state at session end
- 4 files modified (`admin_ui/app.py`, `admin_ui/static/folder-tree.css`, `admin_ui/static/folder-tree.js`, `admin_ui/templates/folders.html`)
- 3 files new (`docs/plans/2026-04-13-drive-loader-pilot.md`, `ingester/loaders/__init__.py`, `ingester/loaders/drive_loader.py`)
- ~1300 lines added
- Everything reversible via `git checkout` + `rm` of the new files
- Branch `main`, in sync with `origin/main`, no commits made

### What session 11 should consider doing first

Pick one (in order of likely impact):

1. **Visual sanity-test the picker UI in a browser.** Spin up the admin UI locally, navigate to `/admin/folders`, click a folder, confirm the Pending Selections panel appears with the correct name/path/dropdown. This is the only piece of session-10 work that wasn't user-tested.
2. **Decide whether to flip the loader to commit mode against `Supplement Info`.** Cost: $0.0002. Output: 3 chunks in local `rf_reference_library` (which would grow from 584 → 587). Reversible via the chunk IDs in the run record. This is the smallest, lowest-risk way to validate the whole pipeline against real data.
3. **OR**: address the Google Doc export issue first (item 1 in critical findings). If the v1 loader is going to be used for real reference content, the lossy-export problem will bite immediately. Switching to HTML export + a markdownify pass would likely recover most of the missing content.
4. **Optional side-quest**: build the read-time normalizer in `rag_server/app.py:format_context()` per STATE_OF_PLAY's "minimum bar for metadata consistent enough" section. The loader already writes the `display_*` fields at ingest time, so the normalizer can read them through unchanged. ~50 lines.

**Do NOT in session 11**: re-open ADR_006, re-derive Plan 1/2/3, push anything to Railway without an explicit pre-flight discussion, or commit-mode-run the loader without first eyeballing what happens to the Google Doc export problem.

### Session 10 addendum — `--dump-json` flag + low-yield safety guard

After the initial dry-run, Dan inspected the captured content and confirmed the lossy-export hypothesis: the 4.3 MB "Comprehensive List of Supplements and substitutions" Google Doc contains product-image substitutions that don't survive `text/plain` export. The exported text is ~3 KB of structural placeholders ("Substitute if OOS:" headers followed by blank space where the image-based substitute names should be).

**Two changes shipped in response:**

1. **`--dump-json PATH` flag added to drive_loader.** Dry-run-only inspection artifact: writes the full raw exported text per file + all chunks + all metadata to a JSON file, so a human can eyeball what the loader actually captured before committing anything. Pure inspection, no Chroma writes, no embedding spend. Used for the post-run audit.

2. **Low-text-yield safety guard added to drive_loader.** Constants: `LOW_YIELD_RATIO_THRESHOLD = 0.05` (5%), `LOW_YIELD_MIN_BYTES = 10_000` (10 KB floor). For Google Docs ≥10 KB on Drive, if `exported_chars / drive_size_bytes < 5%`, the file is skipped with reason `low_text_yield` and a note "defer to v2 loader". The 10 KB floor exists because small text-only docs can have unusual ratios from Drive metadata overhead, and the guard would false-positive on them.

**Verified post-guard behavior on Supplement Info pilot folder:**
- Files seen: 4
- Files ingested: 1 (Professional Nutritionals FKP Schedule, 96% yield)
- Files skipped: 3
  - 2 × `low_text_yield`: Comprehensive (0.07% yield), Supplement Details (0.45% yield)
  - 1 × `unsupported_mime`: Supplement List with Brands (spreadsheet)
- Estimated commit cost: $0.0001

**Strategic implication for session 11+:**

The v1 loader is now conservative-by-default: it will only ingest content that survives plain-text export cleanly. This is the right behavior for unblocking a low-risk pilot commit run, but it means **most image-heavy reference content in the Drive is currently un-ingestible by v1**. The folders most likely to contain valuable RF reference material (clinical handouts, supplement protocols, lab interpretation guides) are precisely the folders most likely to be image-heavy.

**Building the v2 path is the natural next major piece of work.** Sketch:
- Use Drive `files().export(mimeType="text/html")` instead of `text/plain` for Google Docs
- Parse the HTML to extract embedded image URLs (Drive serves them via authenticated googleusercontent.com URLs)
- Download each image using the existing service account credentials
- Send each image to Gemini 2.5 Flash for OCR + visual description (the existing `ingester/config.py` already names this model)
- Stitch the OCR'd text back into the document at the correct position
- Chunk the stitched result the same way v1 does

Estimated cost: probably $0.001–0.01 per image-heavy document, depending on image count. Probably 2–4 hours of dev work for the v2 loader. Should be its own session, not bolted onto session 11.

**Until v2 lands, session 11's options are:**
1. Commit-run the v1 loader against Supplement Info anyway. 1 file lands, 2 deferred. Validates the full pipeline on real data with $0.0001 spend. Defensible as a pilot-of-the-pilot.
2. Pick a different Drive folder more likely to have text-heavy content (e.g. policies, protocols written as prose). Better v1 fit but won't validate the guard.
3. Skip ahead to building v2. Higher impact, higher complexity, higher cost. Probably the right answer if the v1-only content base is too thin to be useful.

**Inspection artifacts on disk:**
- `data/dumps/supplement_info_pilot.json` — original dry-run dump (3 files would ingest)
- `data/dumps/supplement_info_pilot_v1guard.json` — post-guard dry-run dump (1 file would ingest, 2 flagged low_yield)


---

## 2026-04-13 (session 9) — Stabilization: corrected drift inherited from sessions 5–8

**Status:** Stabilization session. No production code shipped, no Chroma writes, no git operations performed by Claude. Output is documentation: a corrected current-state doc (`docs/STATE_OF_PLAY.md`), a refreshed BACKLOG with session 9 entries superseding session 7's framing, a rewritten next-session prompt pointing session 10 at the folder-selection UI thread, and two read-only inventory scripts (`scripts/peek_coaching_schema.py`, `scripts/peek_reference_library.py`).

**What this session corrected.** Sessions 5–8 expanded a real but small concern ("the A4M chunks I'm about to ingest don't have the same metadata shape as the coaching chunks already in the system") into a comprehensive universal chunk metadata contract (ADR_006), three written backfill plans (Plans 1/2/3), four cross-plan consistency decisions, and a session-8 execution prompt. Session 8 began executing those plans against local Chroma, hit Gate 1, and Dan interrupted with the observation that the plans didn't match what was actually deployed. Session 9 investigated and found multiple cascading drifts, all corrected in `docs/STATE_OF_PLAY.md`. Highlights:

1. **Railway is canonical, not local.** The 2026-04-09 Phase 3.5 deploy uploaded a tarball of local Chroma to Railway via cloudflared quick tunnel. After that upload, Railway became the live data store serving Dr. Nashat and other early users. Local Chroma has not been kept in sync since 2026-04-09 and is a development sandbox. The session 7 framing of "local primary, Railway sync deferred" was inverted from reality.

2. **The 584 chunks in `rf_reference_library` are the live A4M reference library, not stale.** They contain 263 transcripts + 269 slides + 52 summaries across 15 modules, with 5 named lecturers (Jaclyn Smeaton ND being the lead at 275 chunks) properly attributed across 513 of 584 chunks. The session 7 plan to "drop and re-ingest from `data/a4m_transcript_chunks_merged.json`" would have silently destroyed the 269 slide chunks and 52 summary chunks because they have no source-of-truth in that JSON. Plan 1 as written would have done real harm.

3. **`data/a4m_transcript_chunks_*.json` and `merge_small_chunks.py` are dead code from an abandoned A4M ingestion attempt (Lineage A).** The 584 chunks in `rf_reference_library` came from a different, parallel ingestion attempt (Lineage B) that produced higher-quality chunks (median 716w vs Lineage A's 446w) and captured slides+summaries that Lineage A doesn't have. Lineage A artifacts should be archived (BACKLOG item) but not deleted.

4. **There has never been a coaching Q&A re-merge, and there should not be one.** Earlier session memory referenced "the Q&A re-merge / session 14" — this was a conflation of two unrelated things: the v3 chunker's prompt rule about Q&A topic boundaries, and the A4M Module 14 rescue work that `merge_small_chunks.py` performed pre-RAG on lecture content. Neither generalizes to a coaching-collection merge pass. Per Dan's session 9 clarification: "that 150 word limit should not be there. it is whatever is right and appropriate. most q&a with this work are long responses." The right rule for chunk size is "whatever makes the chunk a coherent retrievable unit," which is a per-chunk LLM judgment, not a numeric floor. The coaching collection's word-count distribution is captured in STATE_OF_PLAY.md as observation only — no action item.

5. **The actual minimum metadata-consistency gap is much smaller than ADR_006.** Read against `rag_server/app.py:format_context()`, the deployed retrieval code reads exactly four metadata fields: `topics` from coaching, `module_number` / `module_topic` / `speaker` from reference library. The "consistency gap" between the two collections is solved by a 5-field display normalization (~50 lines of Python in `format_context()`, zero Chroma writes), not by a 48-marker-flag universal contract. ADR_006's marker-flag schema becomes valuable when (and only when) the retrieval layer adds a feature that needs lab-marker filtering AND the regex-on-text approach turns out to be insufficient. Neither has happened.

6. **Two parallel Claude sessions ran concurrently during session 9** (different chats, same working tree). The second session caught the first session's near-miss of overwriting good work the first session had already written. Both sessions independently produced overlapping investigations, both arrived at the same authoritative findings via different paths. The second session's additions (the parallel-lineages explanation, the coaching-distribution observation, the speaker-count refinement, the post-mortem update) are integrated into the single `docs/STATE_OF_PLAY.md` that landed.

**What's NOT changed this session:**

- ADR_002, ADR_005, ADR_006, ADR_002 addendum — all preserved as committed history. Not edited. They remain coherent design work that may become valid in their domains later.
- The session 7 HANDOVER entry below — preserved verbatim as history. Demoted from "the roadmap" to "a body of design work that is not driving next-session work."
- `data/`, `ingester/`, `admin_ui/`, `rag_server/`, `config/` — zero code touched.
- ChromaDB (local or Railway) — zero writes.
- Git — zero operations performed by Claude. Dan runs git.

**Tech-lead mandate (carried forward, with one new addition).** Claude holds tech-lead role on the build. Tactical decisions are Claude's call; strategic decisions get flagged to Dan. The session 9 addition: **before reading any bootstrap prompt's reading list, independently verify the prompt's description of the world against the actual filesystem, git history, and deployed system.** If the prompt describes a world that doesn't match the evidence on disk, stop and surface the drift before doing anything else. Step 0 of `docs/NEXT_SESSION_PROMPT.md` implements this check explicitly. This addition exists because session 8 followed an inherited reading list that described a world that no longer matched reality, and the resulting work was about to do harm.

**Files touched this session (writes only to docs/ and scripts/):**

1. `docs/STATE_OF_PLAY.md` (NEW) — authoritative current-state doc, supersedes session 7 framing.
2. `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` (NEW, session 8 carryover) — read-only inventory of coaching collection metadata shape.
3. `docs/BACKLOG.md` (modified) — session 9 block at top with: coaching chunk-size observation as explicit "no action item," Lineage A artifact archival item, optional M3 speaker backfill. Session 7 entries preserved with a superseded note.
4. `docs/NEXT_SESSION_PROMPT.md` (modified) — rewritten for session 10. Drives folder-selection UI end-to-end goal. Step 0 reality check is the new defensive rule.
5. `docs/HANDOVER.md` (this entry, modified) — session 9 stabilization summary prepended; session 7 entry preserved below.
6. `docs/REPO_MAP.md` (modified) — pointer to STATE_OF_PLAY.md added as authoritative orientation surface.
7. `scripts/peek_coaching_schema.py` (NEW, session 8 carryover) — read-only schema inspector.
8. `scripts/peek_reference_library.py` (NEW) — read-only inventory script for `rf_reference_library`.

**Next session (session 10):** drive the folder-selection UI end-to-end with one real folder. Full bootstrap in `docs/NEXT_SESSION_PROMPT.md`. The metadata work from sessions 5–8 stays frozen; ADR_006 and Plans 1/2/3 stay in the repo as history but do not drive session 10 work.

---

## 2026-04-13 (session 7) — Three approved backfill plans + tech-lead mandate established

**Status:** Planning session. No code written. No Chroma touched. No git operations. Three written plans produced and approved by Dan: Plan 1 (Unit 14 / A4M migration to ADR_006), Plan 2 (`rf_coaching_transcripts` Phase 1 structural backfill), Plan 3 (`rf_coaching_transcripts` Phase 2 marker detection). Tactical build decisions on the two open coordination questions were made by Claude under a newly-established tech-lead mandate, with the strategic concerns flagged to Dan. Session 7 is the execution spec for session 8.

**Reading done this session (in order, per session 6 next-session block):**
1. `docs/REPO_MAP.md`
2. `docs/HANDOVER.md` — session 6 top entry only
3. `ADR_006_chunk_reference_contract.md` — full
4. `ADR_005_static_libraries.md` — full
5. `ADR_002_continuous_diff_and_registry.md` — addendum only (2026-04-12)
6. `docs/ARCHITECTURE.md` — full
7. `data/a4m_transcript_chunks_merged.json` — first 2 chunks via head
8. `HANDOVER_INTERNAL_EDUCATION_BUILD.md` — top ~200 lines (loaded mid-session to recover the current coaching-chunk state, which surfaced the RFID wipe history)
9. `INCIDENTS.md` — top section (for credential-rotation awareness)
10. `docs/BACKLOG.md`, `docs/DECISIONS.md` — skimmed for strategic context

**Drift discovered and noted for correction:** Session memory claims "3,041 chunks tagged with client RFIDs" in `rf_coaching_transcripts`. This is **stale**. Per `HANDOVER_INTERNAL_EDUCATION_BUILD.md`, on 2026-04-10 all `client_rfids` and `client_names` metadata fields were wiped from the 3,041 previously-tagged chunks in the local Chroma DB. Current local state is "0 tagged, 9,224 untagged, 9,224 total." Railway production still has the pre-wipe tagged version — this is the deferred Railway sync noted in that handover. Session 7's Plan 2 and Plan 3 are built against the post-wipe local state and write `client_id: null` on every coaching chunk. Any session reading memory that contradicts this should treat this handover entry as authoritative.

---

### Tech-lead mandate established this session (carried forward)

Dan granted Claude tech-lead role on the RAG build from this session forward. The mandate has five components, all binding on future sessions:

1. **Tactical authority.** Claude makes tactical build decisions unilaterally — script layout, mapping conventions, validator shape, dry-run output format, error handling, helper-module shapes, detection method tradeoffs where cost is low, etc. Dan is brought in on: strategic tradeoffs, irreversible operations, money spend decisions above ~$25, anything crossing the RAG-system boundary into app/product/legal/business, and anything that fails the "can we fix this later?" test.

2. **Safety discipline unchanged.** Tech-lead authority is not a license to skip gates. All prior rules still apply:
   - No Chroma writes without explicit Dan approval at the specific write moment
   - No git push/commit/add without approval (Dan runs git; Claude suggests what to stage and what message)
   - No Railway operations without approval
   - No deletions without approval and a verified backup
   - Dry-run before every write, every time
   - First-touch of any live Chroma collection requires a manual eyeball-diff gate where Dan reviews sample before/after pairs

3. **"Can we fix this later?" test.** For every tactical decision: if reversing the decision requires a migration script and a dry-run, Claude decides it. If reversing requires re-embedding, re-ingest, or a production rollback, Claude flags it to Dan before shipping. This is the load-bearing gate between "tactical" and "strategic."

4. **Consistency across all surfaces.** What session N's plans say must match: repo governing docs (ADRs, ARCHITECTURE, REPO_MAP, HANDOVER, BACKLOG, DECISIONS), project-root governing docs (HANDOVER_PROMPT, VECTOR_DB_BUILD_GUIDE where applicable), git history (via session-close commits with clear messages), and next-session bootstrap prompts. When drift is found between memory and reality, it is flagged and corrected in the handover before the session closes.

5. **Session-close discipline.** Every session that touches governing docs closes with: HANDOVER entry describing what actually landed (not what was planned), BACKLOG updates for new deferred items, REPO_MAP updates if new docs were added, and a git commit summary suggested to Dan (Dan runs git).

---

### Three plans produced and approved this session

All three plans live in full inside this handover entry. Session 8 executes Plans 1 and 2 only; Plan 3 remains planning-only until a dedicated later session.

#### Plan 1 — Unit 14 / A4M chunks migration plan (APPROVED)

**Scope.** Migrate the 353 existing chunks in `data/a4m_transcript_chunks_merged.json` from their current flat-metadata shape into a new `data/a4m_transcript_chunks_adr006.json` that conforms to ADR_006. Does NOT write to Chroma. Does NOT modify the source file. Does NOT touch the A4M slides loader (separate future work).

**Field mapping (existing → ADR_006):**

| ADR_006 field | Source / derivation |
|---|---|
| `chunk_id` | Synthesize via shared helper: `a4m_course:reference_transcript:module_{NN}:chunk_{IIII}` (zero-padded) |
| `text` | Copy existing `text`, unchanged |
| `collection` | `"rf_reference_library"` |
| `library_name` | `"a4m_course"` |
| `entry_type` | `"reference_transcript"` |
| `origin` | `"static_library"` |
| `tier` | `"reference"` |
| `source_id` | `static:a4m_course:Transcriptions/{source_file}` |
| `source_name` | Copy existing `source_file` |
| `source_path` | Null (absolute local path known but optional; leave null for now) |
| `chunk_index` | Copy existing `chunk_index` |
| `chunk_total` | Computed: group by `source_file`, count per group |
| `date` | Null (A4M recording date not in existing metadata) |
| `ingested_at` | ISO-8601 UTC at script run time |
| `client_id` | **Explicit `None`** |
| `linked_test_event_id` | **Explicit `None`** |
| `marker_*` (48 flags) | All 48 populated via regex, default `false`, set `true` per `detect_markers(chunk["text"])` |
| `markers_discussed` | Display string, derived from true-flag set, **lowercase bookend-delimited** (`"|amh|fsh|tsh|"`) — canonical casing decision, see "Cross-plan consistency decisions" below |
| `qpt_01`–`qpt_25` | **Omitted entirely** (forward-compat, not yet required; omit rather than populate as false so the eventual QPT-aware amendment cleanly triggers a detection backfill) |
| `qpt_patterns_referenced` | Omitted |
| `speaker` | Null (existing `speakers` list is diarization labels like `SPK_1`, not resolvable to real names without a per-module speaker map; preserve the raw list inside `type_metadata_json`) |
| `topics` | Null (LLM extraction out of scope) |
| `recommendations_given` | N/A per ADR_006 §5 matrix |
| `type_metadata_json` | JSON-encoded string containing the `reference_transcript` block from ADR_006 §4 plus A4M-specific extensions: `course_name`, `module_number`, `module_title`, `lecturer: null`, `run_time_total_seconds: null`, `speaker_block_count: null`, `speakers_raw` (the existing `speakers` list), `start_time`, `end_time`, `word_count` |

**Preserved but routed to `type_metadata_json`:** `start_time`, `end_time`, `speakers` (as `speakers_raw`), `word_count`, `source_type`. No data is dropped from the existing file.

**No conflicts with ADR_006.** All existing fields map cleanly or lift into type_metadata_json.

**Prerequisite:** `ingester/marker_detection.py` must exist before this migration runs. Creating it is part of Plan 1's execution. See "Cross-plan consistency decisions" below for module layout and shape.

**Migration script location:** `ingester/backfills/migrate_a4m_to_adr006.py`. Script is described-not-written this session.

**Execution outline:** preflight checks (count = 353, uniform `source_type`, existing keys present); build phase (construct all records in memory); validation pass (shared validator from `ingester/backfills/_common.py`); dry-run summary; optional `--write` to produce the output file. Source `merged.json` is never modified. Re-running overwrites the output file byte-for-byte.

**Out of scope for Plan 1:** slides loader, Chroma write, file record creation in `rf_library_index`, QPT detection, topic extraction.

#### Plan 2 — `rf_coaching_transcripts` Phase 1 structural backfill (APPROVED, Option B decided by Claude)

**Scope.** Bring all 9,224 existing chunks in the local `rf_coaching_transcripts` collection into ADR_006 structural compliance by adding the required universal fields and all 48 `marker_*` flags set to explicit `false`. No marker detection. No chunk text changes. No re-embedding. Writes to **local Chroma only**, not Railway — the Railway sync is deferred and remains its own operation.

**Count reconciliation:** 9,224 chunks total, 0 client-tagged (post-wipe). Plan 2 writes `client_id: null` and `linked_test_event_id: null` on every chunk. Future re-tagging is downstream of the Zoom pipeline per the 2026 disambiguation decision in `docs/DECISIONS.md` and is NOT Phase 1's work.

**Required preflight — field inventory on live Chroma.** The existing coaching-chunk metadata shape is not documented anywhere in the repo. Session 8 step 1 is a read-only peek script that samples 5 chunks, prints their metadata keys and values, and captures the output into a new doc `docs/COACHING_CHUNK_CURRENT_SCHEMA.md`. That doc becomes the input to the Plan 2 field-mapping table below and serves as reference material for anyone debugging retrieval later.

**Field mapping (existing → ADR_006) — schema-shape-driven.** The inventory fills in a few specific cells; structural mapping is locked.

| ADR_006 field | Source / derivation | Depends on inventory? |
|---|---|---|
| `chunk_id` | Reuse existing Chroma ID if well-formed, else synthesize via shared helper | Yes |
| `text` | Copy from Chroma `documents` field | No |
| `collection` | `"rf_coaching_transcripts"` | No |
| `library_name` | `"historical_coaching_transcripts"` | No |
| `entry_type` | `"coaching_transcript"` | No |
| `origin` | `"drive_walk"` (per ADR_006 §7) | No |
| `tier` | `"paywalled"` | No |
| `source_id` | Derived from existing filename-like field (filename-based convention — see "Option B" note below) | Yes |
| `source_name` | Copy from filename-like field | Yes |
| `source_path` | Populate if path-like field exists, else null | Yes |
| `chunk_index` | Copy existing (likely `chunk_index`) | Yes |
| `chunk_total` | Computed per source file | No |
| `date` | Call date if present, else null | Yes |
| `ingested_at` | **Sentinel `2026-04-12T00:00:00Z`** per ADR_006 §7. Same value on every chunk, never updates on re-run | No |
| `client_id` | **Explicit `None`** (wiped, not reconstructed) | No |
| `linked_test_event_id` | **Explicit `None`** | No |
| `marker_*` (48 flags) | **All 48 explicit `False`** | No |
| `markers_discussed` | Null | No |
| `qpt_01`–`qpt_25` | Omitted | No |
| `speaker` | If existing, preserve; if diarization label only, route to type_metadata_json and set top-level to null | Yes |
| `topics` | If existing, normalize to lowercase bookend-delimited; else null | Yes |
| `recommendations_given` | Same | Yes |
| `type_metadata_json` | JSON-encoded. Base: ADR_006 §4 `coaching_transcript` block. Plus: every existing metadata field that doesn't map to a top-level ADR_006 field, preserved under a clearly named key. Don't-drop-data principle | Yes |

**Option B decided by Claude (tactical call under mandate):** Plan 2 does NOT coordinate with the ADR_002 file-record backfill this session. Rationale: Option A (strict coordination, build both in one script) requires solving the ADR_002 file-record backfill design inside Plan 2's scope — non-trivial questions including sha256 of files we may no longer have direct access to and Drive file ID reconstruction for pre-registry files. That design work inflates session 8's scope beyond the stated mandate and gates A4M ingestion on work that doesn't need to gate it. Option B's only cost is that `source_id` on coaching chunks is filename-based until a future file-record backfill upgrades it — a deterministic one-to-one rewrite, cheap to reverse. **Reversibility test passes for Option B, fails for Option A.** If Option B turns out wrong: write a future backfill pass that rewrites `source_id` values. No data loss, no re-embedding, no reingest.

**Safety mechanisms:**
- Default dry-run. `--write` flag required for real mode.
- Read-only validator pass builds all updated metadata records in memory (~20MB for 9,224 chunks), validates every single record via the shared validator, and only begins writing if the full set validates. **No partial writes.**
- Resumable via progress file `backfill_phase1_progress.json`. Each batch is idempotent at Chroma's level.
- Pre-write diff sample: 3 before/after pairs printed, waits for keyboard confirmation before writing.
- **Backup verification gate:** script refuses to run in write mode without a recent `chroma_db_backup_pre_phase1_backfill_YYYYMMDD`. Prints the exact `cp -r` command for Dan to run; does NOT perform the backup itself.

**Idempotency and the re-run-after-Phase-2 trap:** Phase 1's validator checks, before writing, whether any chunk has any `marker_*` flag set to True. If so, Phase 2 (or something else) has already flipped flags, and re-running Phase 1 would destroy that work. Script refuses to write and prints a clear error. The `--force-reset-markers` flag exists as an explicit escape hatch but defaults off.

**Local/Railway divergence:** Plan 2 writes to local only. Railway sync is deferred; strategic concern flagged separately (see below).

**Script location:** `ingester/backfills/backfill_coaching_phase1_structural.py`.

**Out of scope for Plan 2:** marker detection (Plan 3), `client_id` reconstruction (future Zoom-pipeline-dependent work), Drive file ID reconstruction, `rf_library_index` creation, Railway sync, any other collection.

#### Plan 3 — `rf_coaching_transcripts` Phase 2 marker detection (APPROVED, Option C hybrid decided by Claude)

**Scope.** A second pass over 9,224 coaching chunks (post-Phase 1) that flips `marker_*` flags from False to True based on chunk text. Writes `markers_discussed` display string. No chunk text changes, no re-embedding. **Execution-only-in-a-dedicated-later-session.** Not run in session 8.

**Detection method — Option C (hybrid regex + LLM disambiguation) decided by Claude:**

- **Option A (pure regex):** Eliminated. Coaching transcripts have conversational clinical language where regex-only precision on the T3/FT3 collision set reintroduces the exact bug ADR_006's marker-boolean decision was made to prevent.
- **Option B (pure LLM):** Eliminated. Cost is fine (~$30), but non-determinism is unacceptable — Phase 2 runs against a collection with no ground truth for flags, so re-runs must be deterministic to allow spot-check confidence.
- **Option C (hybrid):** Regex for ~40 unambiguous markers (zero cost, deterministic). LLM only for the collision set (`marker_ft3` vs bare T3, `marker_ft4` vs bare T4, the three-way iron/iron-saturation/transferrin-saturation case, any ≤3-char marker without strong word-boundary context). Cost estimate: $2-5, worst case $15. Non-deterministic surface area reduced from 9,224 chunks to ~500-1,500 collision-hitting chunks.

**The collision set — precisely defined:**
- `marker_ft3` vs bare `T3`
- `marker_ft4` vs bare `T4`
- `marker_iron` × `marker_iron_saturation_pct` × `marker_transferrin_sat` (three-way)
- Any ≤3-character canonical form or alias without strong word-boundary context

Everything else is regex-only. `marker_detection.py` carries a `COLLISION_MARKERS: set[str]` alongside `MARKER_PATTERNS`, and hybrid mode routes to the LLM only when regex hits something in `COLLISION_MARKERS`.

**Cost gate:** script computes projected LLM call count after the regex pass, prints estimated cost, and waits for Dan's confirmation before any Haiku calls. Refuses to proceed automatically if projected cost exceeds $25. Override via explicit `--cost-ceiling 50`.

**Batching:** regex pass is one loop in memory, ~30s. LLM pass is serial with progress bar and rate limiting, ~15-25 min wall-clock. Chroma write pass is batches of 500. Total runtime ~30 min end-to-end, well over MCP 4-minute ceiling — Phase 2 must be launched as a detached process with monitoring via `ps aux` + progress file.

**Sanity checks:**
1. Flag distribution histogram after the full pass. Zero hits on `marker_amh` across 9,224 coaching chunks → bail, something's wrong.
2. No-marker-chunk fraction. If >70% or <10%, flag for manual review.
3. Collision resolution audit log (`phase2_collision_audit.jsonl`) with every LLM input/output for spot-checking.
4. Delta against Phase 1 — Phase 2 only flips False → True, never the reverse. Bail on any False-reverse.
5. Manual spot-check gate: 5 random chunks printed with detected flag set + text side by side, Dan confirms before Chroma write.

**Rollback:** pre-Phase-2 backup required (`chroma_db_backup_pre_phase2_markers_YYYYMMDD`). Secondary rollback: re-run Phase 1 with `--force-reset-markers`.

**Dependencies:**
- Phase 1 must have completed and validated
- `ingester/marker_detection.py` must include both pure-regex `detect_markers()` and hybrid `detect_markers_hybrid(text, llm_client)` — signature stubbed in session 8's Plan 1 work so Phase 2 drops in without restructuring
- Haiku API access working (HANDOVER session 6 flagged auth issues; still on deferred list)

**Script location:** `ingester/backfills/backfill_coaching_phase2_markers.py`.

**Out of scope for Plan 3:** QPT detection, `client_id` reconstruction, any other collection, Railway sync.

---

### Cross-plan consistency decisions (apply to ALL current and future loaders/backfills)

Four decisions made this session that carry forward and bind all future work:

1. **`markers_discussed` display string casing: lowercase, derived mechanically from flag names, bookend-delimited.** Format: `"|amh|fsh|tsh|ft3|"`. One helper, one source of truth (the canonical flag names from ADR_006 §2a), zero per-loader drift. Citation rendering at retrieval time may uppercase for display — that's a presentation concern, not a storage concern. A one-line clarification to ADR_006 §2 matching the example to this rule is flagged in BACKLOG but is not a session-7 edit.

2. **Directory layout for all ingestion-related code:**
   - `ingester/marker_detection.py` — canonical marker regex module (created in session 8 Plan 1 step)
   - `ingester/backfills/_common.py` — shared helpers: ADR_006 record validator, `build_chunk_id()`, `build_markers_discussed()`, `serialize_type_metadata()`
   - `ingester/backfills/migrate_a4m_to_adr006.py` — Plan 1
   - `ingester/backfills/backfill_coaching_phase1_structural.py` — Plan 2
   - `ingester/backfills/backfill_coaching_phase2_markers.py` — Plan 3 (not built in session 8)
   - `ingester/loaders/` — future real loaders (A4M slides, Drive-walk ingester, Zoom-episode loader). Not built in session 8.

3. **Consistency mechanism — one of each, shared everywhere:** one `marker_detection.py`, one validator, one chunk-ID synth helper, one display-string builder, one dry-run pattern, one `type_metadata_json` serializer. Shared by every current and future loader and backfill. The validator is the enforcement point; the shared helpers make "the easy path is the correct path." A loader that bypasses the shared helpers is non-compliant by definition.

4. **Chunk-ID format for all libraries:** `{library_name}:{entry_type}:{source_component}:{chunk_index_zero_padded}`. Works for A4M (`a4m_course:reference_transcript:module_01:chunk_0007`), coaching (`historical_coaching_transcripts:coaching_transcript:{source_file_stem}:chunk_0042`), published content (`rf_blog:published_post:{slug}:chunk_0003`), any future library. One helper generates it.

---

### Strategic concerns raised this session (on Dan's radar, not blocking session 8)

1. **Local ↔ Railway drift has been deferred since 2026-04-10 and the pile is growing.** Deferred list now includes: the 2026-04-10 RFID wipe on coaching chunks, Phase 1 structural backfill, Phase 2 marker detection, the ADR_006-conforming A4M corpus (when ingested), the 584 pre-ADR_006 A4M chunks (to be dropped and re-ingested — see below), and eventually `rf_published_content`. Each deferred item makes the eventual atomic Railway sync bigger and riskier. **Strategic question for Dan:** do we set a target session where we cut and run the atomic Railway sync (i.e., "everything on local that's done by session N gets shipped in session N+1") or keep deferring until all four content collections are built? Claude's lean: mid-build sync after Phase 1 + A4M ingestion land, to avoid a single enormous high-risk sync at the end. Not blocking session 8 but needs a decision in the next 2-3 sessions.

2. **No single-source-of-truth document for the coaching collection's current metadata shape.** It exists only in the live Chroma DB. If local gets corrupted and we restore from the Railway tarball, the Railway version has a different metadata shape (pre-wipe), and nothing on disk documents either version. Session 8 step 1 creates `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` as the fix. Cheap insurance.

3. **ADR_002 file-record backfill for historical coaching transcripts has no written plan.** Phase 1 proceeds via Option B without it, but this work needs its own planning session before it becomes a surprise. Adding to BACKLOG.

4. **Coaching chunk re-tagging (client_id reconstruction) is downstream of the Zoom pipeline build.** Per the 2026 disambiguation decision in DECISIONS.md, re-tagging should use Zoom participant labels + scene-change data, not pattern matching. Not a next-session concern, but a dependency worth tracking for the Zoom pipeline's design phase.

5. **`VECTOR_DB_BUILD_GUIDE.md` §3G and §7 amendments still deferred.** That doc is canonical for the project but ADRs 005 and 006 now extend it. New-session Claude reading BUILD_GUIDE without the ADRs would get a wrong picture. Closing this gap within 2-3 sessions is the target. Adding to BACKLOG as elevated priority.

6. **The 584 pre-ADR_006 A4M chunks in `rf_reference_library`.** HANDOVER_INTERNAL_EDUCATION_BUILD.md notes 584 A4M course chunks "intact" in `rf_reference_library` as of 2026-04-10. This pre-dates ADR_006 and has an unaudited metadata shape. **Decision (Claude, tactical):** drop-and-re-ingest using Plan 1's migration output as the source of truth. Rationale: one code path (Plan 1's migration + future real loader) produces one uniform set of chunks conforming to one contract, versus two code paths producing chunks that in theory match but in practice drift. Reversible: pre-drop backup + the 353-chunk JSON stays on disk. Strategic concern worth flagging but not blocking: before the drop runs, session 8 performs a read-only inventory of the 584 chunks and compares against the 353 merged JSON. If the 584 covers source files the 353 doesn't (or has substantive text the JSON is missing), the drop pauses for Dan's call. The drop itself is NOT session 8's work — it's a subsequent session that also performs the first A4M ingestion into `rf_reference_library`.

---

### Files touched this session (writes only to HANDOVER, BACKLOG, and REPO_MAP)

1. **`docs/HANDOVER.md`** — this entry appended at top, earlier entries preserved verbatim.
2. **`docs/BACKLOG.md`** — added new items for: ADR_002 file-record backfill plan (dedicated planning session), BUILD_GUIDE §3G/§7 amendment session (elevated priority), the 584 pre-ADR_006 A4M chunks decision (drop-and-re-ingest, verification required), Railway sync cadence strategic decision, `markers_discussed` casing ADR_006 §2 clarification.
3. **`docs/REPO_MAP.md`** — updated to note the new `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` doc (will exist after session 8 step 1) and the new `ingester/backfills/` code location convention.

**Files NOT touched this session (deliberate):** ADR_002, ADR_005, ADR_006, ARCHITECTURE.md, VECTOR_DB_BUILD_GUIDE.md, any code, Chroma, git, Railway. Plans are captured in this handover entry; they are not ADRs and do not need a separate governing doc.

---

### Hard rules carried forward

- No Chroma writes without explicit Dan approval at the specific write moment
- No git push/commit/add without approval (Dan runs git)
- No Railway operations without approval
- No deletions without approval + verified backup
- Never reference Dr. Christina
- Exclude Kelsey Poe and Erica from retrieval results
- Dr. Chris stays internal (diarization label)
- Public agent never accesses `rf_coaching_transcripts`
- Credentials are ephemeral — never stored in memory or files
- Marker flags written as explicit `false`, never omitted
- Static-library loaders verify source contains no client-identifying data

---

### Next session (session 8) — execution

Session 8 is the execution session for Plan 1 and Plan 2 (planning-only for the 584 A4M chunks inventory and a gate before any drop). Plan 3 is deferred to a dedicated later session.

The full next-session bootstrap prompt lives at `docs/NEXT_SESSION_PROMPT.md` (written this session, not appended here to keep the handover readable). Session 8 Claude reads REPO_MAP, this HANDOVER entry, ADR_006, ADR_005, ADR_002 addendum, and ARCHITECTURE sections, then executes in this order with manual gates:

1. **Step 0:** Tool load (`tool_search` for filesystem tools). Verify access to repo and local Chroma.
2. **Step 1 (Gate 1):** Read-only coaching-chunk schema inventory via `scripts/peek_coaching_schema.py`. Write `docs/COACHING_CHUNK_CURRENT_SCHEMA.md`. Dan reviews before proceeding.
3. **Step 2 (Gate 2):** Build shared ingestion infrastructure — `ingester/marker_detection.py`, `ingester/backfills/_common.py`, package inits. Dan reviews before running anything.
4. **Step 3 (Gate 3):** Plan 1 execution — write `ingester/backfills/migrate_a4m_to_adr006.py`, run dry-run, show Dan the summary (353 chunks processed, marker histogram, sample before/after records). If approved, re-run with `--write` to produce `data/a4m_transcript_chunks_adr006.json`. Separately and before any drop, perform read-only inventory of the 584 legacy A4M chunks in `rf_reference_library` and capture output in `docs/A4M_LEGACY_CHUNKS_INVENTORY.md`. The 584-chunk drop itself is NOT session 8's work.
5. **Step 4 (Gate 4):** Plan 2 execution — write `ingester/backfills/backfill_coaching_phase1_structural.py`, preflight (count 9,224, post-wipe sanity check, no marker flags already set, backup verification), build phase, validator, dry-run summary. If approved and backup verified, Dan confirms `chroma_db_backup_pre_phase1_backfill_YYYYMMDD` exists, then re-run with `--write`. Monitor via progress file; relaunch via `start_process` if MCP timeout looms.
6. **Step 5:** Session close. Append session 8 entry to HANDOVER summarizing what landed, any deviations, updated collection state, new backlog items or strategic concerns. Prepare git commit summary for Dan.

**Hard stops for session 8:** no Phase 2 marker detection, no A4M ingestion into `rf_reference_library`, no drop of the 584 legacy chunks, no Railway operations, no git push, no edits to ADR_002/005/006 or ARCHITECTURE unless execution reveals a gap in the contract (in which case STOP and ask).

**Still deferred from earlier sessions (unchanged):**
- Unblock Haiku auth for `claude-haiku-4-5` (session 3 noted Haiku 3.5 family 404s for this org)
- Admin password rotation + add Dr. Nashat as second admin user via `add_user` CLI
- Rotate exposed `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` if not already done

**Context discipline lesson from this session:** When the user hands Claude tech-lead authority, the right response is not to relax gates — it's to make tactical calls confidently within the existing gates and surface the strategic tradeoffs clearly. The two tactical decisions this session (Option B for Plan 2 coordination, Option C for Plan 3 detection method) were both made by applying the "can we fix this later?" test explicitly. The strategic concerns flagged to Dan were the ones that failed that test or crossed domain boundaries. Default for future sessions: when in doubt about tactical vs strategic, apply the reversibility test — reversible by migration script → tactical; reversible only by re-embedding/re-ingest/rollback → strategic.

---

## 2026-04-12 (session 6) — BUILD_GUIDE review resolved; ADR_002 amended, ADR_005 revised, ADR_006 created AND amended same-session

**Status:** Governing docs for the static-library path and chunk metadata contract are now locked end-to-end. No code written. No Chroma touched. No git. Ready for the next session to return to the (b) Unit 14 merge plan and then the A4M ChromaDB ingestion with a locked schema. Note the same-session amendment to ADR_006 — the first draft used pipe-delimited marker encoding; Dan flagged the substring-collision risk; the amendment replaces that with 48 boolean flags and a phased backfill. The amendment is the current state; the original first draft is not preserved anywhere and should not be reconstructed.

**What triggered this session.** Session 4 drafted ADR_005 without having read `VECTOR_DB_BUILD_GUIDE.md`. Session 5 flagged that the BUILD_GUIDE is the canonical source-of-truth for the entire project (unified ID system, data source map, correlation model) and that ADR_005 needed to be evaluated against it before any further work built on it. The review prompt (`docs/NEXT_SESSION_PROMPT_ADR005_REVIEW.md`) specified evaluation-only — no file edits. This session executed that evaluation, reported findings to Dan, and then Dan approved a follow-on work pass to fix the gaps in governing docs.

**Evaluation verdict:** Consistent with minor additions. ADR_005's core claim (static-vs-living lifecycle is a separate ingestion category) held up against the BUILD_GUIDE. Five specific gaps surfaced:

1. `client_id` treated as universal in BUILD_GUIDE §7 but ADR_005 leaves room for non-client content (A4M lectures). Needs to be optional in the contract.
2. Correlation fields (BUILD_GUIDE §8: `linked_test_event_id`, `markers_discussed`, `qpt_patterns_referenced`) need to be optional for the same reason.
3. ADR_005 §5 wrongly framed the registry as "mostly aspirational" — ADR_002 §Q2 had locked it as a `rf_library_index` ChromaDB collection with a full file record schema on 2026-04-11. ADR_005 also omitted that the `origin` field and non-Drive primary key it assumes are not actually in ADR_002's schema yet.
4. The word "static library" grammatically overlaps with ADR_002's first-class "library" entity. Needed an orthogonality clarification: `tier` (ADR_002) × `origin` (ADR_005) × `entry_type` (BUILD_GUIDE §7 / ADR_006) are three independent dimensions.
5. Reference-tier content is public-agent-eligible by default, so static-library loaders must verify source material contains no client-identifying data before ingesting. Not stated anywhere before this session.

Also surfaced: BUILD_GUIDE §3 (Data Source Map) does not list reference-library content at all. Not a blocker — flagged as a recommended `§3G` addendum for a future session.

**Dan's decisions (chat, this session):**

- Q-A: ADR_002 gets a formal 2026-04-12 addendum adding `origin` and generalizing the file record primary key. Not deferred.
- Q-B: Keep the name "static libraries." Add the orthogonality clarification in ADR_005 §7.
- Q-C: Generic `entry_type` values — `reference_transcript`, `reference_document` — not A4M-specific. Future-proof for ACOG and other curated snapshots.
- Q-D: Lock the governing docs this session before resuming (c)/(b) in later sessions.
- Q-E: The chunk reference contract goes in **ADR_006** (a new ADR), not into ARCHITECTURE.md. Pattern mirrors ADR_002 — ADRs hold schemas, ARCHITECTURE.md points.
- BUILD_GUIDE §3G addendum: defer to a separate future session. Don't fold in now.

**Dan's mid-session follow-ups (after first draft of ADR_006 landed):**

- On pipe-delimited strings for list fields: Dan pushed back with "is this the best way to handle it?" Claude reassessed and found the BUILD_GUIDE §5 marker name collisions (`T3`/`FT3`, `T4`/`FT4`, `Iron`/`Iron Saturation %`) make substring filtering genuinely unsafe — not just slightly awkward.
- **New decisions Dan approved ("go with your leans"):**
  - Hybrid encoding: **48 boolean flags for markers** (one per BUILD_GUIDE §5 marker) + pipe-delimited display string kept for rendering only. Filtering always goes through booleans.
  - 25 QPT flags as forward-compat spec (optional today, required when the first QPT-aware loader is built — amendment will flip them to required and trigger a detection backfill).
  - Topics and recommendations_given stay pipe-delimited with bookend delimiters (`"|fertility|amh|"`) because their vocabularies are unbounded and boolean expansion is impractical.
  - **Phased backfill** for existing 9,224 coaching chunks: Phase 1 is structural annotation only (cheap, unblocks A4M, all 48 marker flags set to explicit `false`); Phase 2 is marker detection (independent, can run later, detection method decided in the Phase 2 session).
  - A4M loaders do **regex-based marker detection** (~20 lines, sufficient for lecture content precision). Phase 2 coaching-transcript detection method is deferred.
  - Shared `marker_detection.py` module in the ingester package so all loaders use the same regex patterns.
  - All 48 flags must be written as **explicit `false`**, never omitted. Missing Chroma metadata fields become `None` and can't be filtered on — silent retrieval bug.

**Files touched this session (all writes to Mac via `Filesystem:write_file`):**

1. **`ADR_002_continuous_diff_and_registry.md`** — appended an "Addendum (2026-04-12) — `origin` field and non-Drive file records" section at the end. Adds the `origin` field (required, values `drive_walk | static_library`), generalizes primary key to `file:{source_id}`, makes Drive-specific fields nullable for static records, adds `local_path` field, specifies that the diff engine filters `WHERE origin = "drive_walk"`, and clarifies that soft-delete does not apply to static libraries. ADR_002 status line updated to "DECIDED (amended 2026-04-12 — see Addendum at bottom)". A pointer to the addendum was also inserted at the top of the registry schema section so a reader of the original schema knows to read the addendum.

2. **`ADR_005_static_libraries.md`** — full rewrite that preserves all 7 original decisions verbatim but adds:
   - A "Relationship to VECTOR_DB_BUILD_GUIDE.md" subsection in Context explaining that A4M is not in BUILD_GUIDE §3 and that a §3G addendum is flagged for later
   - A "Business-priority pivot note" subsection acknowledging that BUILD_GUIDE §12's priority order (labs, transcripts, retrieval, IG) has shifted and that reference-library content is now a near-term focus
   - §4 expanded to explicitly require `client_id` and correlation fields to be optional in the contract
   - §5 rewritten from "registry is aspirational" to "registry architecture is decided per ADR_002 §Q2; this is now a present-tense requirement backed by the 2026-04-12 addendum." Explicit reference to `origin`, generalized `source_id` key, nullable Drive-specific fields, `local_path`, sha256 content hash, and diff-engine filtering behavior
   - §7 expanded with the orthogonality clarification (tier × origin × entry_type as three independent dimensions), including a table and a worked example for `a4m_course`
   - New Consequence bullet: "Static libraries are public-agent-eligible by default" with the loader-author-owned audit responsibility
   - New Cross-reference to ADR_006
   - Out-of-scope "forward-compat" language replaced with present-tense language throughout §5

3. **`ADR_006_chunk_reference_contract.md`** — new file, then amended same-session. Universal chunk metadata schema for every content collection. Final locked state:
   - Contract lives in an ADR (not ARCHITECTURE.md), mirroring ADR_002's registry schema pattern
   - Universal required fields (11): `chunk_id`, `text`, `collection`, `library_name`, `entry_type`, `origin`, `tier`, `source_id`, `source_name`, `chunk_index`, `ingested_at`
   - **48 `marker_*` boolean flags required on every chunk**, all 48 defaulting to `false` and set `true` per detection. Canonical naming derived from BUILD_GUIDE §5 (§2a in ADR_006 has the full expansion). Adding or renaming a marker requires ADR_006 amendment.
   - **25 `qpt_01`–`qpt_25` flags as forward-compat spec**, optional today, required when first QPT-aware loader is built
   - Optional fields accommodating client-free content: `client_id`, `linked_test_event_id`, `speaker`, `topics`, `recommendations_given`, `type_metadata_json`, `markers_discussed` (display-only string), `qpt_patterns_referenced` (display-only string)
   - Extended `entry_type` enum (10 values): `coaching_transcript`, `reference_transcript`, `reference_document`, `published_post`, `ig_post`, `dm_exchange`, `lab_summary`, `supplement_rec`, `qpt_reference`, `coaching_episode`. Renames: `transcript` → `coaching_transcript`, `dm` → `dm_exchange`.
   - Per-type `type_metadata_json` expectations for all 5 currently-planned types
   - Required/optional field matrix per entry_type
   - BUILD_GUIDE §7 reconciliation table (7 divergences documented)
   - Chroma encoding rules: booleans for filterable closed-vocabulary lists, bookend-delimited strings for unbounded lists, JSON-encoded string for nested metadata
   - §7 phased backfill plan for existing 9,224 `rf_coaching_transcripts` chunks: Phase 1 structural annotation (unblocks A4M), Phase 2 marker detection (independent)
   - §8 marker detection guidelines for new loaders + illustrative regex starter kit
   - §9 retrieval-time usage section explaining that `tier`, `library_name`, `marker_*`, `entry_type` denormalized onto chunks means agent variant routing and marker filtering work without registry joins
   - ADR_006 amendment note in the footer documenting the pipe-delimited → boolean encoding change and why

4. **`docs/ARCHITECTURE.md`** — full rewrite. Added:
   - `rf_library_index` to the Collections list with a note about the 2026-04-12 addendum
   - New "Chunk metadata schema (locked 2026-04-12)" section pointing to ADR_006 as authoritative — including the 48 marker flags, the hybrid boolean/delimited encoding rules, and the phased backfill plan
   - New "Ingestion paths" section summarizing the two categories and noting both must share a canonical `marker_detection.py` module
   - New "Governing docs" section listing BUILD_GUIDE, ADR_001–006 in order
   - New hard guardrail: "Static-library loaders must verify their source contains no client-identifying data before ingesting" (ADR_005 Consequences, codified here)
   - New hard guardrail: "Marker flags must be written as explicit `false`, not omitted" (ADR_006 field-rule, codified here)

5. **`docs/REPO_MAP.md`** — full rewrite. Added ADR_006 to the ADRs section with the hybrid-encoding and phased-backfill notes. Added amendment notes to ADR_002 and ADR_005. Added `rf_library_index` to the Collections list. Rewrote the "Ingestion paths" subsection to reflect the locked taxonomy and the shared `marker_detection.py` requirement. Added the two new hard guardrails (client-data audit + explicit false) to the hard-guardrails list.

6. **`docs/HANDOVER.md`** — this entry.

**Files NOT touched this session (deliberate, per plan):**
- `VECTOR_DB_BUILD_GUIDE.md` — load-bearing canonical doc. §3G addendum and §7 revision deferred to a future focused session. Tracked in BACKLOG (to be added by Dan or next session).
- `ADR_001`, `ADR_003`, `ADR_004` — unrelated to this work.
- `ingest_a4m_transcripts.py` and other code — no code written. (b) Unit 14 merge plan and the two backfill plans remain the next session's work.
- ChromaDB, git, Railway — untouched. No commits. Nothing pushed.

**Hard rules carried forward:** No Chroma writes, no git push/commit/add, no Railway, no deletions without explicit Dan approval. Never reference Dr. Christina. Public agent never touches `rf_coaching_transcripts`. Credentials ephemeral.

### Next session — execute in this exact order

1. **READ FIRST:**
   - `docs/REPO_MAP.md`
   - `docs/HANDOVER.md` (this entry only — do NOT re-read earlier entries unless a specific question forces it)
   - `ADR_006_chunk_reference_contract.md` (entirely new, load-bearing, amended same-session — read in full including §2 marker flag block, §2a canonical naming, §7 phased backfill, §8 marker detection for new loaders)
   - `ADR_005_static_libraries.md` (the amended version)
   - `ADR_002_continuous_diff_and_registry.md` — **addendum section only** (at the bottom of the file, dated 2026-04-12). Do NOT re-read the 2026-04-11 body unless a specific question forces it.
   - Existing pilot chunks at `data/a4m_transcript_chunks_merged.json` — just a file-head peek (first 1-2 chunks) to see the current flat-metadata shape, don't dump the full file

2. **(b) Unit 14 merge-work plan — plan only, no execution.** With ADR_006 now locked, the plan needs to identify:
   - Which fields in the existing 353 merged A4M chunks already match ADR_006's required universal fields (probably `text`, `module_number`, `module_title`, `source_file`, `chunk_index` — map them to the new required field names)
   - Which ADR_006 required fields are missing and need to be added by a migration pass: `chunk_id`, `collection`, `library_name`, `entry_type`, `origin`, `tier`, `source_id`, `source_name`, `ingested_at`, and **all 48 `marker_*` flags**
   - Marker detection specifically: A4M loaders do regex-based detection per ADR_006 §8. Plan should enumerate which markers are expected to appear in A4M lecture content (likely AMH, FSH, LH, progesterone, TSH, FT3, FT4, vitamin D, HbA1c, insulin, homocysteine, hsCRP) and note that the shared `marker_detection.py` module does not yet exist — creating it is part of the plan.
   - Whether any fields in the current flat metadata contract conflict with ADR_006 (none expected, but verify)
   - Unit 14's specific rescue state — 21 chunks mean 345w after the merge pass — and whether any of those need further work to conform
   - Output: a written plan Dan can review before any code runs. Do NOT edit the chunks in this session unless Dan explicitly approves.

3. **Coaching-transcripts Phase 1 backfill plan — plan only, no execution.** The existing 9,224 `rf_coaching_transcripts` chunks need Phase 1 annotation-only metadata backfill per ADR_006 §7. Produce a written plan including:
   - Exact field-set to write (§7 Phase 1 list: `entry_type`, `origin`, `tier`, `library_name`, `collection`, `source_id`, `ingested_at`, all 48 marker flags set to explicit `false`)
   - Coordination with ADR_002's file-record backfill (they should share a coordinator script)
   - Sentinel `ingested_at` timestamp convention
   - How `source_id` is derived from existing chunks (presumably from the existing `source_file` field but verify against a sample chunk first)
   - Safety mechanism: a dry-run mode that reports what would be updated without writing
   - Dan approves before the script is written and again before it runs.

4. **Coaching-transcripts Phase 2 backfill plan — plan only, no execution, independent of Phase 1.** Marker detection pass that flips the 48 `marker_*` flags from `false` to `true` based on chunk text. Plan should compare the three detection method options from ADR_006 §7 (regex / LLM / hybrid) with rough cost estimates and a recommendation. Phase 2 can run in a dedicated later session; it does not block A4M ingestion.

5. **Only after Unit 14 merge plan + Phase 1 backfill plan are approved and their scripts written in subsequent sessions** — resume A4M ChromaDB ingestion from `data/a4m_transcript_chunks_merged.json`. First touch of `rf_reference_library` collection. Dan approves before Chroma write.

6. **Still deferred from session 2:**
   - Unblock Haiku auth if the `claude-haiku-4-5` model ID works (session 3 noted Haiku 3.5 family is 404ing for this org)
   - Admin password rotation + add Dr. Nashat as second admin user via `add_user` CLI
   - Rotate exposed `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` if not already done

7. **Still deferred, separate session:**
   - BUILD_GUIDE `§3G Reference Library Content (Non-Client-Linked)` addendum
   - BUILD_GUIDE `§7` revision to reference ADR_006 as authoritative chunk schema
   - Zoom coaching video pipeline design (in BACKLOG)

**Context discipline lesson from this session:** The mandate was "resolve and create docs to resume dev" and the work was six file writes with nothing else touched. Reading budget was spent mostly on the initial evaluation (REPO_MAP, HANDOVER top entry, task file, BUILD_GUIDE in full, ADR_005, ARCHITECTURE.md, ADR_002). The actual writing phase used no re-reads — the evaluation notes from the first half of the session carried forward into the writes. **The valuable move**: Dan pushing back on the pipe-delimited marker encoding after the first draft of ADR_006 landed. Without that pushback, the contract would have shipped with a silent-wrong-answer bug waiting to bite on the first T3/FT3 query. Default assumption for future sessions: **when Dan asks "is this the best way?", assume the answer is no and reassess properly** — the question is a signal, not a request for reassurance. **Do the next session's reads before writing any loader code**, especially ADR_006 §2, §2a, §7, §8.

---

## 2026-04-12 (session 3) — ADR_005 (a) decided in discussion, ready to draft

**Status:** Discussion-only session. No files written except this handover entry. Step (a) of the a→c→b sequence is **decided** (Dan approved in chat); the actual ADR_005 file still needs to be written by the next session. Steps (c) and (b) untouched — deferred to subsequent sessions per Dan's call.

**Reading done this session:** `docs/REPO_MAP.md`, `docs/HANDOVER.md` (top entry), `docs/plans/2026-04-11-folder-selection-ui.md`. **Skipped:** `ADR_002`, `ADR_004`, `docs/ARCHITECTURE.md` — context-budget call. ADR_002/004 unnecessary because the decision is "local sources don't participate in the Drive registry/walk model and aren't in the UI" — I don't need to know their internals to write an ADR that says "this doesn't apply." ARCHITECTURE.md deferred to (c).

**Reframe that drove the decision:** Prior session was thinking about local-vs-Drive as a *byte-source* distinction (amend ADR_002 with a `source_origin` field on a shared registry path). Dan corrected this in discussion: it's a **content-lifecycle** distinction. Drive is the *living* corpus — walked, diffed, UI-managed. Local libraries (A4M, future ACOG-style snapshots) are **static libraries** — curated once, dropped in, don't change. Different lifecycle = different ingestion path = separate ADR, not an amendment.

**The UI plan confirms this cleanly.** The folder-selection UI is built around `drive_id`/`slug` as primary keys, with libraries as *destinations* that Drive folders get *assigned to* (`library_assignments` field in `selection_state.json`). Libraries are already a first-class concept in the UI plan, but only as targets. ADR_005 can define libraries as the entities that *contain* chunks regardless of byte source — Drive content gets *assigned* to a library through the UI; static-library content gets *loaded into* a library via CLI. Same destination, different doors. No collision.

### ADR_005 — decided content (Dan approved in chat; next session writes the file)

**Title:** ADR_005 — Static libraries: non-Drive sources for `rf_reference_library` and future curated collections

**Decisions:**
1. **Static libraries are a distinct ingestion category from Drive-walked content.** ADR_002 stays Drive-scoped; ADR_005 covers everything else. Not an amendment.
2. **Loaded via dedicated CLI scripts** (e.g., `ingest_a4m_transcripts.py`). No walk, no diff, no manifest. One-shot operations.
3. **NOT surfaced in the folder-selection UI.** The UI is Drive-only by deliberate design. Adding static sources would conflate two unlike lifecycles. This is **permanent**, not "for now."
4. **Shared chunk reference contract.** All chunks in the RAG system, regardless of byte source, must conform to a shared output contract — enough fields to identify the source unambiguously, attribute citations correctly, and route retrieval based on which agent variant is asking. Exact field list is **(c)'s job** (next ADR or ARCHITECTURE.md update), not (a)'s. ADR_005 only mandates that the contract exists and that static-library loaders must produce conforming output.
5. **Registry integration (forward compat).** When the registry comes online (Phase E in the UI plan), static-library loads write registry entries via a separate code path that bypasses `folder_walk → manifest → diff`. Each entry must record an **`origin`** field (Dan's preferred name; values like `"drive_walk"`, `"static_library"`) so the eventual library inventory view can show static-loaded content alongside Drive-loaded content. Today the registry is mostly aspirational — `selection_state.json` is a flat file — so this is a forward-compat requirement, not a present-tense one.
6. **Flexible CLI structure.** ADR_005 does NOT mandate one script per static library. A4M needed two (transcripts + slides). The constraint that matters is the **output contract**, not the script structure. One or more CLI scripts per static library, each producing chunks that conform to the shared contract.
7. **Naming locked:** "static libraries" (not "local libraries" — local is incidental, static is the actual property). Discriminator field name: **`origin`**.

**Out of scope, flagged for later (separate ADR when relevant):** How clone variants (content-gen, paid-client, public) declare which libraries they're allowed to draw from. Probably lives in agent YAML (`nashat_sales.yaml`, `nashat_coaching.yaml`, future content-gen config), not the UI. Touches ADR_005 only insofar as the chunk contract must carry enough metadata for variant-based retrieval routing.

### Next session — execute in this exact order

1. **Read first:** `docs/REPO_MAP.md`, `docs/HANDOVER.md` (this entry), `docs/plans/2026-04-11-folder-selection-ui.md` (skim — already summarized above, but verify nothing changed). **Do NOT re-derive the ADR_005 decision** — it's locked above. Just write it up.
2. **(a) Write `ADR_005_static_libraries.md`** at repo root (matching the location of ADR_001–004). Use the 7 decisions above verbatim as the substance. Include: context section explaining the lifecycle distinction, the 7 decisions, consequences (what this enables, what it constrains), and explicit cross-references to ADR_002 ("does not apply to static libraries") and ADR_004 ("UI is Drive-only by design — see ADR_005 for why static libraries are excluded"). Update `docs/REPO_MAP.md` to list ADR_005. Get Dan approval before committing.
3. **(c) Lock the `rf_reference_library` metadata schema.** Read `docs/ARCHITECTURE.md` first (this session skipped it). Take the chunk reference contract from ADR_005 and instantiate it specifically for `rf_reference_library`: required vs optional fields, examples per source type (`a4m_course`, `external_research`, `clinical_paper`). Must align with `rf_coaching_transcripts` flat-metadata convention (locked 2026-04-12) AND with whatever `rf_published_content` will need for cross-collection coherence. Decide: does this go in ARCHITECTURE.md as a schema update, or in a new ADR_006? Get Dan approval.
4. **(b) Unit 14 merge-work plan.** Plan only — no execution. Bring remaining A4M chunks up to whatever (c) locks down. Identify which chunks in `data/a4m_transcript_chunks_merged.json` need re-merging or field backfill. The 353 chunks already have flat metadata at root per the locked 2026-04-12 contract — main risk is missing fields that (c) makes required.
5. **Then return to `NEXT_SESSION_PROMPT.md`** with schema and taxonomy locked, and proceed with A4M ChromaDB ingestion (still requires Dan approval — first touch of new collection).

**Hard rules carried forward:** No Chroma writes, no git push, no Railway, no deletions without explicit Dan approval. Never reference Dr. Christina. Public agent never touches `rf_coaching_transcripts`. Credentials ephemeral. No git commits this session — `docs/HANDOVER.md` was the only file touched.

**Context discipline lesson from this session:** Discussion-first worked. Spending the early budget on alignment (gate question, Q1/Q2 framing, naming) before reading meant the eventual UI-plan read had a sharp focus and I didn't burn tokens reading docs that turned out to be irrelevant (ADR_002, ADR_004). The cost: ran out of budget before writing the actual ADR file. That's the right tradeoff IF the discussion-locked decision is faithfully captured in handover — which is what this entry is for. Next session should NOT re-litigate the 7 decisions; it should just write them down.

---

## 2026-04-12 — Aborted A4M schema session, restart required

**Status:** STOP and restart in fresh session. This session ran out of context room before producing usable work.

**What happened:** Session was loaded with `NEXT_SESSION_PROMPT.md` (A4M metadata schema + ingestion taxonomy gate question). Read REPO_MAP, NEXT_SESSION_PROMPT, ADR_001, ADR_002, ARCHITECTURE.md, and HANDOVER_INTERNAL_EDUCATION_BUILD.md. **Did NOT read this HANDOVER.md or `docs/plans/2026-04-11-folder-selection-ui.md`** — that was the wrong call. Dan flagged that an entire prior session today went into the folder-selection UI walkthrough, and any "additional load path" decision must be grounded in what was actually built there, not designed in a vacuum from the ADRs alone.

**Gate question still open:** What is the canonical metadata schema for `rf_reference_library`, AND where does a local non-Drive source like A4M legitimately fit in the ingestion-path taxonomy that the folder-selection UI now governs?

**Draft answer produced this session (treat as input, not decision):** Local-source loads should still write `file` records into `rf_library_index` (registry is the single source of truth per ADR_002), with a new `source_origin: "drive" | "local_oneshot"` discriminator field. Schema sketch in this session's chat transcript — re-derive from the UI plan, don't just lift it.

**Next session — execute in this exact order (Dan's call):**

1. **READ FIRST, before anything else:**
   - `docs/REPO_MAP.md`
   - `docs/HANDOVER.md` (this entry + whatever's below it)
   - `docs/plans/2026-04-11-folder-selection-ui.md` ← the load-bearing one this session skipped
   - `ADR_002_continuous_diff_and_registry.md` (registry + diff model)
   - `ADR_004_folder_selection_ui.md` (UI design as decided)
   - `docs/ARCHITECTURE.md` (current schema + collection definitions)

2. **(a) Codify the additional-load path in governing docs.** Decide whether this is an amendment to ADR_002 or a new ADR_005 ("Local and non-Drive ingestion sources for `rf_reference_library`"). Must define: (i) that all writes to `rf_reference_library` create `rf_library_index` records regardless of byte source, (ii) the `source_origin` field, (iii) how local-source diff/dedup works without a Drive walk (content_hash on file bytes), (iv) whether the folder-selection UI surfaces local sources at all or whether they're CLI-only. Write the ADR. Get Dan approval before moving on.

3. **(c) Lock the `rf_reference_library` metadata schema** — rock-solid, aligned with what the UI/registry assume and with `rf_published_content` for cross-collection coherence. Required vs optional fields, examples per source type (a4m_course, external_research, clinical_paper). Get Dan approval.

4. **(b) Unit 14 merge-work plan** — bring remaining A4M chunks up to schema compliance (Haiku merge to 490w mean / 250w floor, add all required schema fields, compute content_hash). Plan only — execution after approval.

5. **Back to plan** — resume the A4M ingestion path from `NEXT_SESSION_PROMPT.md` with the now-correct schema and taxonomy.

**Hard rules carried forward:** No Chroma writes, no git push, no Railway, no deletions without explicit Dan approval. Never reference Dr. Christina. Public agent never touches `rf_coaching_transcripts`. Credentials ephemeral.

**Context discipline lesson for next session:** With ~9 docs in scope, do not try to read all of them. But do not skip `docs/HANDOVER.md` or active `docs/plans/*` files — those carry the most recent state and override the ADRs where they're more current. Reading plan should always include: REPO_MAP → HANDOVER → any in-flight plan from the last 48 hours → then ADRs/architecture as the task requires.

**Known state unchanged from prior entry:** 353 merged A4M chunks at `data/a4m_transcript_chunks_merged.json` (flat metadata at root, empty `metadata: {}` to ignore). Unit 14 chunks not yet merged. `rag_pipeline_v3_llm.py` still has stale `claude-3-5-haiku-*` model ID — one-line fix deferred.

---

## State
- Two fixes this session, both verified end-to-end:
  1. `DriveClient` credential fallback — local dev now reads service account from `GOOGLE_APPLICATION_CREDENTIALS` file path. Railway's `GOOGLE_SERVICE_ACCOUNT_JSON` blob path is unchanged and still checked first. Committed + pushed.
  2. `folder_walk.py` field-persistence bug — Drive API was correctly fetching 9 file fields, but `_walk_folder` was only storing 3 into the manifest. Both `append({...})` blocks (top-level loop AND nested BFS loop) now persist all 9 keys via `.get()`. Committed (`d145bf6`) and pushed.
- `.env` line 4 fixed: `CHROMA_DB_PATH` double-quoted so `source .env` works.
- Local credential: `GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json`.
- Last full walk: `data/inventories/folder_walk_20260412_153931.json` — fresh post-fix, 13 MB, ~21.5 min runtime. jq-verified: first non-folder file record has all 9 fields populated (size, modifiedTime, createdTime, webViewLink, md5Checksum). `owners: null` on Shared Drive files is correct Drive API behavior.
- Stale pre-fix manifest `folder_walk_20260412_141626.json` archived to `data/inventories/archive/`.
- Smoke-walked `9-biocanic` (`folder_walk_20260412_150658.json`) post-fix, jq-verified on a video/mp4 record: size, modifiedTime, createdTime, webViewLink, md5Checksum all populated. `owners: null` is correct Drive API behavior for Shared Drive files (ownership lives with the drive), not a bug.
- ⚠️ Security: `.env` containing live `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` was exposed in a chat transcript this session. Rotate both keys when convenient.

## Just did (Apr 12 session 2)
- Wrote `rf-nashat-clone/ingest_a4m_transcripts.py` — A4M transcript pilot. Copies `parse_speaker_blocks` / `get_boundaries_from_llm` / `assemble_chunk_from_blocks` from `rag_pipeline_v3_llm.py`. Regex extended to handle `SPK_N`. Prompt re-framed for lecture (no client Q&A framing). Abort-on-failure instead of silent fallback. Pilot mode: Module 1 only → writes JSON to `data/a4m_transcript_chunks_pilot.json`, NO ChromaDB.
- `MODULE_TITLES` dict in the new script: **modules 13/14 flipped** vs `ingest_reference_library.py` `MODULE_MAP` to match transcript filename ground truth (MODULE_MAP had them swapped).
- Skipping `alltranscriptionscombined.txt` in Transcriptions folder (duplicate).
- Parse stage verified working: Module 1 → 394 speaker blocks, 15,829 words, 95,839 chars.
- **BLOCKED on Haiku auth.** Ran twice, both `invalid x-api-key`. User rotated key in `~/.zshrc` + `.env` between runs; post-rotation key is structurally valid (length 108, `sk-ant-api` prefix) but still rejected. Suspected: wrong org, propagation delay, or clipboard mixup. Diagnostic curl proposed but session ran out of budget before running it.
- Exposed keys from previous session: status of rotation unclear — new key is in place but rejected, so we don't know if old key was actually revoked.

## Previously did
- Quoted `CHROMA_DB_PATH` in `.env` line 4.
- Patched `DriveClient.__init__`: explicit arg → `GOOGLE_SERVICE_ACCOUNT_JSON` blob → `GOOGLE_APPLICATION_CREDENTIALS` file. Committed + pushed.
- Patched both `append({...})` blocks in `folder_walk.py::_walk_folder` to persist all 9 file fields. Verified with `--drive 9-biocanic` + jq. Not yet committed.

## Next (in order)
1. **Unblock Haiku auth.** Run diagnostic: `curl -s -o /dev/null -w "%{http_code}\n" https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-3-5-haiku-20241022","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'`. If 401 → regenerate key in console.anthropic.com, confirm correct org has credits. If 200 → something else, inspect response body. Then re-run `source ~/.zshrc && cd rf-nashat-clone && python3 ingest_a4m_transcripts.py`. Parse stage will reproduce 394 blocks / 15,829 words — if those numbers match, only auth was broken.
2. **Inspect the pilot JSON.** When pilot runs clean, read `data/a4m_transcript_chunks_pilot.json`: chunk count (expect ~30-50 at 300-500w target), mean word count, first 3 and last chunk. Verify metadata: `module_number=1`, `module_title="Epigenetics & Nutrigenomics..."`, `source_type="transcript"`, `source_file`, `chunk_index` all present. Verify chunk boundaries look topically coherent (Haiku job quality check).
3. **Approval gate.** DO NOT batch remaining 13 modules until user explicitly approves Module 1 chunks.
4. **Batch ingestion.** After approval: extend `main()` to loop all 14 modules, still write to JSON first. Then ChromaDB load step (new collection `rf_reference_library`, OpenAI `text-embedding-3-large`). Ask user before Chroma write — first touch of a new collection.
5. **A4M slides** — `ingest_a4m_slides.py`. Rule-based per-slide PDF extraction via `pdfplumber`. Same collection, `source_type="slides"`. Not started.
6. **Admin password rotation + add Dr. Nashat as second admin user via `add_user` CLI.** Deferred from prior session.

## Previous "Next" items (superseded)
1. **A4M `rf_reference_library` ingestion** — path confirmed, inventory done, plan agreed.
   - **Path:** `/Users/danielsmith/Library/CloudStorage/GoogleDrive-znahealth@gmail.com/Shared drives/11. RH Transition/A4M Fertility Course`
   - **Contents:** 14 `.mkv` lecture videos (ignore), 15 PDFs in `Slides/`, 15 TXTs in `Transcriptions/`, 14 HTMLs in `Module Summaries for Nashat/`, 1 `.gdoc`.
   - **Ingest:** Transcripts (TXT, LLM-chunked via Haiku, same approach as coaching v3) + Slides (PDF, rule-based per slide). **Skip summaries** — derivative of transcripts, would add retrieval noise. Revisit only if retrieval proves they capture something unique.
   - **Collection:** new `rf_reference_library` (separate from `rf_coaching_transcripts`).
   - **Metadata schema:** `module_number`, `module_title`, `source_type` (transcript|slides), `source_file`, `chunk_index`.
   - **Sequence:** Pilot Module 1 end-to-end (transcript + slides) → verify chunk quality + retrieval → batch remaining 13.
   - **Scaffolding check done:** `ingest_reference_library.py` in project root is **summary-only** (hardcoded to `Module Summaries for Nashat`, HTML parser, timestamp chunking). Do NOT extend — it's solving a different problem. **Leave it alone.** Only reusable piece is its `MODULE_MAP` dict (module number → title → speaker) — copy that, discard the rest.
   - **Architecture for next session:** two new files in project root.
     - `ingest_a4m_transcripts.py` — reads `Transcriptions/*.txt`, Haiku-chunked (reuse logic from `rag_pipeline_v3_llm.py` — peek first to confirm reusability), embeds with `text-embedding-3-large`, loads into `rf_reference_library` with `source_type="transcript"`.
     - `ingest_a4m_slides.py` — reads `Slides/*.pdf`, rule-based per-slide chunks via `pdfplumber`, same collection, `source_type="slides"`.
   - **First action next session:** peek head of `/Users/danielsmith/Claude - RF 2.0/rag_pipeline_v3_llm.py` to assess Haiku chunker reusability, then build pilot `ingest_a4m_transcripts.py` for Module 1 ONLY. Inspect chunks before batching remaining 13.
2. Deferred: admin password rotation, add Dr. Nashat as second admin user via `add_user` CLI.
3. Deferred: rotate exposed `ANTHROPIC_API_KEY` + `OPENAI_API_KEY`.

## Blockers / deferred
- None on the walk pipeline — clean.
- Network stability: first full walk failed mid-way on Wi-Fi drop. Not a code bug. If recurs, consider resume-from-partial-manifest for `folder_walk.py` (queued for BACKLOG).
- Rotate exposed `ANTHROPIC_API_KEY` + `OPENAI_API_KEY`.
- Zoom coaching video pipeline design still in BACKLOG.

## Do NOT
- Do NOT re-read full `folder_walk.py` or `drive_client.py` — both fixes verified.
- Do NOT dump full JSON manifests — always jq. Field-verification one-liner:
  ```bash
  jq '[.. | .files? // empty | .[]? | select(.mimeType | test("google-apps") | not) | select(.mimeType != "application/vnd.google-apps.folder")][0]' data/inventories/folder_walk_<timestamp>.json
  ```
- Do NOT commit `.env` or the service account JSON.
- Do NOT remove `GOOGLE_SERVICE_ACCOUNT_JSON` support from `DriveClient` — Railway depends on it.
- Do NOT run the walk on Railway yet — local first, verify, then Railway.


---

## Metadata contract (LOCKED — 2026-04-12)

A4M transcript chunks use **FLAT metadata** at the chunk root, not nested under a `metadata` key. Fields present at top level of each chunk:

- `text`, `start_time`, `end_time`, `speakers`, `word_count`
- `module_number`, `module_title`, `source_type`, `source_file`, `chunk_index`

The `metadata` key (if present) is an empty dict and should be ignored. When batching to ChromaDB, pull metadata fields from the chunk root — do NOT look under `chunk["metadata"]`. This matches how Chroma ingests (flat dict) and is simpler than nesting.

Applies to: `ingest_a4m_transcripts.py` output and any future transcript-based ingesters in this repo.

> **Note (2026-04-12 session 6):** This flat-at-root convention is *compatible* with ADR_006's chunk reference contract — ADR_006's schema is also flat at root (no nested `metadata: {}` dict). ADR_006 adds required fields (`chunk_id`, `collection`, `library_name`, `entry_type`, `origin`, `tier`, `source_id`, `source_name`, `ingested_at`, **and all 48 `marker_*` boolean flags**) that the existing A4M pilot chunks don't yet carry. The (b) Unit 14 merge-work plan in the next session must add those fields to the 353 merged A4M chunks — including regex-based marker detection via a shared `marker_detection.py` module — before they can be written to `rf_reference_library`.

---

## Module 1 pilot — APPROVED (2026-04-12)

Final chunking prompt tuned through 3 iterations. Locked config:
- **Model:** `claude-haiku-4-5` (Haiku 3.5 family no longer accessible to current org — 404s on `claude-3-5-haiku-20241022` AND `claude-3-5-haiku-latest`. Same will apply when rerunning `rag_pipeline_v3_llm.py` — needs same swap.)
- **Prompt rules:** Q&A exchanges are hard topic boundaries (with a <150w merge escape hatch), hard ceiling 1,100w, hard floor 250w, target 300-700w.

**Module 1 results:** 32 chunks, mean 494w, range 157–962w. 66% in 400-799w sweet spot. Smallest is the natural module-end tail, largest is a coherent lifestyle-factors topic. Parse stage matched v3 exactly: 394 blocks, 15,829 words, 95,839 chars.

**Next:** batch modules 2–14 with same script, same pilot JSON output format, still no ChromaDB writes. Then review aggregate stats before approving ingestion.


---

## A4M full batch — COMPLETE (2026-04-12)

All 14 modules chunked and ready for ChromaDB ingestion.

**Pipeline as-run:**
1. `ingest_a4m_transcripts.py` — parses transcripts, calls Haiku 4.5 for topic boundaries, writes chunks. Output: `data/a4m_transcript_chunks_full.json` (452 chunks)
2. `merge_small_chunks.py` — post-process pass that merges any chunk under 250w into its smaller neighbor, per-module. Output: `data/a4m_transcript_chunks_merged.json` (353 chunks)

**Final corpus stats:**
- 353 chunks, mean 490w, min 252w, max 1557w
- Zero floor violations (all chunks ≥250w after merge pass)
- One ceiling outlier: Module 6 chunk at 1557w — manually inspected, coherent single-topic (mitochondrial/metabolic dysfunction in Fertility Over 40). Approved.
- Module 14 required rescue: source transcript is unusually fragmented (17 words/block avg vs ~40 elsewhere) — merge pass took it from 40 chunks mean 181w to 21 chunks mean 345w. Not Haiku's fault.

**`merged.json` is the canonical file for ChromaDB ingestion.** `full.json` is kept for audit/diff.

**Still deferred (approval required before next session proceeds):**
1. Write chunks from `a4m_transcript_chunks_merged.json` to the new `rf_reference_library` collection with `text-embedding-3-large`
2. Verify collection count and run sample retrieval queries
3. Admin password rotation + add Nashat as second admin user
4. Swap Haiku model ID in `rag_pipeline_v3_llm.py` from `claude-3-5-haiku-*` to `claude-haiku-4-5` (Haiku 3.5 family is no longer accessible to this org — confirmed via 404 on two separate snapshot IDs)
