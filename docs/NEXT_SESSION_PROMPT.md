# NEXT SESSION PROMPT — session 19

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Every session 9 onward has used a Step 0 reality check before doing any work. It has paid for itself every single time. Session 14 missed a dirty working tree. Session 16 surfaced four pre-existing UI bugs. Session 17 caught a poor pilot file pick before any commit. Session 18 confirmed the docx handler shipped clean — but also surfaced a content-strategy gap that pivots session 19's scope away from new handlers and toward dedup + content quality. **Session 19 must run Step 0 in full.**

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all gates. Stop and tell Dan if anything surprises you.

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 19 ok"); 2+2`. Expect `session 19 ok` and `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 18 commit** landing the docx handler (new module + new test + v3 dispatcher edits + requirements.txt + 4 doc updates + 4 new BACKLOG items #33-#36 + no Chroma writes).
   - Below session 18: session 17 (`93efce3`), session 16 (`98f8011`), session 15 (`d0c381f`), etc.
   - **Working tree must be completely clean.** If `git status` shows ANY modified or untracked files, STOP and surface them. (Session 14 lesson.)

### 0.3 — Data plane reality

4. **Reality-vs-prompt check.** Verify these against the actual filesystem:

   - **Chroma baseline.** `rf_reference_library` should still be **605** (unchanged from session 17 close — session 18 had zero Chroma writes). If 604 or lower, session 17 commit rolled back — stop. If 606+, something wrote between sessions — stop and check what.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** Should still return **8 chunk IDs**: 7 PDF (Egg Health Guide, session 16) + 1 v2_google_doc (Sugar Swaps Guide, session 17). **Zero docx chunks** — session 18 wired the handler but committed nothing.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); cats=[m.get('v3_category','?') for m in r['metadatas']]; print('v3 chunks:', len(r['ids']), 'by category:', {c: cats.count(c) for c in set(cats)})"
     ```
     Expected: `v3 chunks: 8 by category: {'pdf': 7, 'v2_google_doc': 1}`. If a 'docx' category appears, an unintended commit happened — stop and investigate.

   - **v2-ingested chunks still queryable.** Still 13 (session 14 unchanged), at least 3 with `name_replacements >= 1`.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → likely **34** (29 baseline + 5 from the session 18 blogs pilot images). Could be different if cache deduplication kicked in. Anything between 29 and 36 is fine. Outside that range, investigate.

   - **Drive auth.**
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
     ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"
     ```
     Expected: `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.**
     ```bash
     ./venv/bin/python -c "from google import genai; c = genai.Client(vertexai=True, project='rf-rag-ingester-493016', location='us-central1'); print(c.models.generate_content(model='gemini-2.5-flash', contents='Say ok and nothing else.').text)"
     ```
     Expected: `ok`.

   - **OpenAI auth (live, not just presence).** Source `.env` in a subshell (`set -a && . ./.env && set +a`), then a minimal `embeddings.create("test")` call returning 3072 dims. Never read `.env` contents into chat.

   - **Test suite — all 9 scripts must be green** (session 18 added the docx synthetic).
     ```bash
     ./venv/bin/python scripts/test_scrub_s13.py                       # 19/19
     ./venv/bin/python scripts/test_scrub_wiring_s13.py                # PASS
     ./venv/bin/python scripts/test_types_module.py                    # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py             # PASS
     ./venv/bin/python scripts/test_format_context_s16.py              # 23/23
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py         # 16/16
     ./venv/bin/python scripts/test_google_doc_handler_synthetic.py    # 9/9
     GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_docx_handler_synthetic.py          # 12/12 (NEW session 18)
     ```
     **Note:** `test_admin_save_endpoint_s16.py` clobbers `data/selection_state.json` (BACKLOG #31). Restore AFTER the test, not before, if you depend on the file.

   - **v1 regression.** v1 still works for the original pilot.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader \
       --selection-file /tmp/rf_pilot_selection.json \
       --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 \
       --dry-run 2>&1 | tail -15
     ```
     Expect `files ingested: 1`, 2 low-yield skips. If `/tmp/rf_pilot_selection.json` no longer exists (reboot wiped `/tmp/`), recreate it from HANDOVER session 10.

   - **v2 regression.** Must be byte-identical to session 16/17 baseline.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v2 --dry-run 2>&1 | tail -20
     ```
     Expected: 2 files seen, 2 ingested, 1 vision_cache_hit, 0 errors, ~1,303 est_tokens, $0.0002.

   - **v3 regression.** Default selection_state should resolve to DFH folder + Egg Health Guide PDF.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -30
     ```
     Expected: 3 files enumerated, 3 processed OK, 0 quarantined, 9 chunks projected (1+1+7), `by_handler={pdf: 1, v2_google_doc: 2}`, $0 vision cost (cache hit), ~$0.0010 projected total. **Identical to session 17 baseline.**

### 0.4 — Admin UI sanity (session 16 gate, still in effect)

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If a Python process is listening, verify it's running session-18 code (modification time of working files matches disk). If no process, start a fresh one with `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s19_admin_ui.log 2>&1 & disown`.

6. **HTML cache disable hook is active.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store` header.

7. **Selection state on disk has the session 16/17 default shape.** `cat data/selection_state.json`. Should be the DFH folder + Egg Health Guide PDF assignment, two-bucket shape with `selected_folders`, `selected_files`, `library_assignments`, `timestamp`.

### 0.5 — Final reality summary

8. **Print a one-line state summary** to confirm Step 0 passed:
   ```
   ✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc + 0 docx),
     OCR cache: ~34, all 9 test scripts green, admin UI on PID <pid>, selection_state v2 shape OK
   ```

If anything in 0.1–0.5 fails, **STOP and surface the failure to Dan before reading any further or doing any work.**

---

## Step 1 — Read context (~5 minutes)

After Step 0 passes, read these in this order. Don't read more than necessary.

1. **`docs/STATE_OF_PLAY.md` — session 18 amendment** (the bottom section, ~70 lines). Tells you the state of the world coming into session 19 and why scope pivoted away from new handlers.

2. **`docs/HANDOVER.md` — session 18 entry** (the bottom section, ~170 lines). Tells you what shipped, what didn't, why the blogs commit was deferred, and the lessons.

3. **`docs/BACKLOG.md` — items #29, #30, #23, plus #33-#36** (the new session 18 wake). These are the candidates for session 19 scope.

---

## Step 2 — Scope decision (Dan picks)

**Session 19 pivots away from new handlers and toward content quality + dedup infrastructure.** Three options:

### Option A — The dedup + quality bundle (TECH-LEAD RECOMMENDATION)

**Bundles three items that compound:**
- **BACKLOG #23 (content-hash dedup)** — pre-write filter in v3's commit path. Idempotent: re-ingesting an already-committed file becomes a no-op. Catches filesystem duplicates and re-runs.
- **BACKLOG #29 (Canva editor metadata strip)** — `_strip_editor_metadata()` post-pass in `google_doc_handler` removing Canva edit URLs, production tags (`COVER:`, `PAGE 1:`, etc.), draft notes. A/B retrieval-similarity test on the 14 existing Google Doc chunks (no Chroma writes).
- **BACKLOG #30 (extraction_method/library_name not written to Chroma)** — fix in v3's per-chunk metadata builder. Affects all v3 chunks (PDF + Google Doc + future docx).

**Why bundle:** all three improve corpus quality and unblock future handler work. Dedup is the safety net every future handler benefits from. #29 cleans existing Google Doc chunks. #30 cleans v3 metadata for all existing v3 chunks. Each is small (~1-2 hours); doing them sequentially across three sessions wastes per-session overhead.

**Estimated effort:** ~half-day, one session. Spend ~$0.05 (small re-embedding for any chunks where #29 changes content meaningfully + standard test/dry-run costs).

**Real risks:**
1. **#23 needs careful schema design.** Hash what? The pre-scrub text? Post-scrub text? Per-chunk or per-file? Surface as M-options before code.
2. **#29 might require re-embedding the 14 existing Google Doc chunks** if the Canva strip changes content meaningfully. Halt-before-write for that.
3. **#30 is metadata-only**, no re-embedding. Smallest risk.

### Option B — Content source-of-truth doc (BACKLOG #35)

**Single deliverable:** `docs/CONTENT_SOURCES.md` mapping content domain → canonical Drive folder(s) → file forms to ingest vs. skip. Dan and Claude walk the inventory together; Dan decides; Claude documents.

**Why it matters:** without this, Option A's dedup safety net catches the *easy* duplicates (literal hash matches) but doesn't catch *format-duplicates* (same blog as docx + HTML + email). The content map catches those upstream by deciding which form is canonical per domain.

**Estimated effort:** ~1.5 hours of conversation + writing. Mostly conversational, low API spend.

**Trade-off:** doesn't fix any code. Pure content-strategy work. Could be done before, after, or alongside Option A.

### Option C — Both (recommended if energy allows)

Do Option A in the morning, Option B in the afternoon (or split across the session). Option A produces the safety net code; Option B produces the content map. Together they unblock session 20+'s handler work cleanly. Both options have low API spend and complementary scope (one is code, one is conversation).

**Estimated effort:** ~5-6 hours total, one session.

### Other candidates (lower priority for session 19)

- **BACKLOG #21** — folder-selection UI redesign. 60-90 min. Biggest UX friction point but not a content-quality issue.
- **BACKLOG #32** — smarter Google Doc / docx locator detection (paragraph fallback for docs without h1-h6). ~2 hours. Useful but doesn't unblock anything.
- **BACKLOG #34** — add `sample_chunks` to v3 dry-run dump-json. ~30 min. Quality-of-life for future halt-before-commit gates.
- **BACKLOG #33** — rename `SESSION_16_CATEGORIES` → `SUPPORTED_CATEGORIES`. ~15 min. Cosmetic.
- **BACKLOG #36** — revisit blogs commit decision (gated on #35 landing).

**Tech-lead recommendation: Option C (A + B together).** Reasoning:
1. Option A's three items are tightly related and benefit from one design pass (especially #23's hash-what-exactly question and #29's strip-strategy question).
2. Option B unblocks the next handler session by giving it a content map to work from.
3. Together they put us in the right state to resume handler work cleanly in session 20.

If only one: **Option A.** The safety net code is the higher-leverage win because it benefits every future ingestion forever.

It's Dan's call — surface all three, recommend C (or A as fallback), wait for the answer.

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
- **Halt before any direct Chroma write of any kind.** No exceptions.
- **No deletions** (files, chunks, collections) without approval AND a backup of the affected state.
- **Pipe commit stdout to a file**, not `| tail` — session 16 lesson.
- **Tech-lead volunteers architecture review at design-halt points.** When a design doc has a question mark or assumption, surface it as M-options (M1/M2/...) before code. (Session 15/16/17 lesson.)
- **Read the Flask access log first** when debugging UI cache or save issues. (Session 16 lesson.)
- **Test in Chrome before Safari** for admin UI iterative work. (Session 16 lesson.)
- **When closing a BACKLOG item, verify in the environment where it manifested.** (Session 16/17 lesson.)
- **No Railway writes from sessions.** Railway is read-only. Only Dan deploys.
- **No touching legacy collections** (`rf_coaching_transcripts`, pre-scrub 584 A4M) without Dan's explicit OK.
- **Credentials ephemeral** — never read `.env` content into chat.
- **Never reference Dr. Christina / Dr. Chris / Dr. Massinople** in agent responses, sample chunks, test data, or anywhere else.
- **Dan does git operations**, not Claude.
- **v2 frozen** unless extract-and-redirect to a shared module with byte-identical behavior verified by dry-run regression. M3 is the precedent. (Session 17.)
- **When piloting a new feature, scan for real-world examples that exercise the feature**, not just any small example. (Session 17 lesson.)
- **Prefer write-script-to-file over inline heredocs** for any Python script longer than ~10 lines. (Session 17 lesson.)
- **Pre-commit drift audit on any new handler.** Side-by-side comparison of stored Chroma metadata for an existing chunk vs. the projected metadata. Schema must match exactly except for type-specific fields. (Session 18 lesson.)
- **Don't ingest a content domain until its source-of-truth is documented.** Once `docs/CONTENT_SOURCES.md` exists, every bulk ingest must map back to a designated canonical source. (Session 18 lesson.)
- **Build the safety net before the surface area grows.** Adding handlers is fast; cleaning duplicates after the fact is slow and risks corrupting retrieval. (Session 18 lesson.)

---

## Budget for session 19

- **$1.00 interactive gate.** If any single task projects above $1.00 in API spend, halt and surface the cost to Dan before proceeding.
- **$25.00 hard refuse.** No single session should ever spend more than $25 in API calls.
- **Session 18 spent ~$0.0008.** Session 19 expected: ~$0.05 if Option A or C executes (small re-embedding for #29). Option B alone is ~$0.

## Files you'll likely touch (depending on scope)

**For Option A (dedup + quality bundle):**
- `ingester/loaders/drive_loader_v3.py` (#23 dedup pre-write filter, #30 metadata writer fix)
- `ingester/loaders/types/google_doc_handler.py` (#29 `_strip_editor_metadata()`)
- New: `scripts/test_canva_strip_synthetic.py`
- New: `scripts/test_canva_strip_dryrun_existing_chunks.py` (re-extract 14 existing Google Doc chunks, dry-run, similarity comparison)
- New: `scripts/test_dedup_synthetic.py`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

**For Option B (content sources):**
- New: `docs/CONTENT_SOURCES.md`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`, `docs/NEXT_SESSION_PROMPT.md`

## Files you should NOT touch

- `chroma_db/*` — never edit directly. Any writes go through the v3 commit path.
- `data/inventories/*.json` — folder walk output, never hand-edit.
- `data/audit.jsonl` — append-only via the audit module.
- Anything under `rf-coaching-call-recordings/` — pure read-only data.
- `ingester/loaders/drive_loader.py` (v1) — frozen.
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except for M3-style extract-and-redirect.
- `ingester/loaders/types/pdf_handler.py` — no scope this session.
- `ingester/loaders/types/docx_handler.py` — shipped session 18, no changes needed.

## Step 0 cheat sheet (for quick reference at the start of session 19)

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Chroma baseline (expect 605 — unchanged from session 17 close)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks (expect 8 = 7 pdf + 1 v2_google_doc + 0 docx)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); cats=[m.get('v3_category','?') for m in r['metadatas']]; print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})"

# OCR cache (expect ~34: 29 baseline + ~5 from session 18 blogs pilot)
ls data/image_ocr_cache/*.json | wc -l

# Test suite (expect all 9 green)
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
set -a && . ./.env && set +a
for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py; do
  echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -3
done

# Drive auth
./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"

# Vertex auth
./venv/bin/python -c "from google import genai; c = genai.Client(vertexai=True, project='rf-rag-ingester-493016', location='us-central1'); print(c.models.generate_content(model='gemini-2.5-flash', contents='Say ok and nothing else.').text)"

# v2 dry-run regression (must be byte-identical to session 16/17 baseline)
./venv/bin/python -m ingester.loaders.drive_loader_v2 --dry-run 2>&1 | tail -20

# v3 dry-run regression on default selection (3 files / 9 chunks / cache hit)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -30

# Admin UI process check
lsof -iTCP:5052 -sTCP:LISTEN -P -n

# Selection state shape (DFH folder + Egg Health Guide PDF, two-bucket)
cat data/selection_state.json
```

If all of the above passes, print:
```
✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc + 0 docx),
  OCR cache: ~34, all 9 tests green, admin UI on PID <pid>, selection_state v2 shape OK
```

Then proceed to Step 1.

---

## End of session 19 prompt

Session 18 shipped the docx handler clean (12/12 synthetic tests, drift-audit passed against PDF and Google Doc handlers, end-to-end dry-run on April-May 2023 Blogs.docx producing 7 chunks with `§§N-M` locators) but deferred the commit at the halt-before-commit gate when Dan surfaced the content-strategy gap (same blogs exist as docx, HTML, email — no canonical-source decision yet).

Session 19 pivots: build the dedup safety net (#23) + clean existing Google Doc chunks (#29) + fix v3 metadata writer (#30) + produce the content sources doc (#35). Then session 20+ resumes handler work with a clean foundation.

The system has 605 chunks, 8 of them v3-ingested. Zero docx chunks committed yet. Selection state restored to session-16/17 default. Working tree clean (after session 18 commit lands). Good luck.
