# NEXT SESSION PROMPT — session 21

> **⚠ READ THIS FIRST, BEFORE ANYTHING ELSE**
>
> Step 0 has paid for itself every session 9 onward. Session 20 used it to confirm session 19's commits had landed, all auths were live, and v3 dry-run still produced 9 chunks at $0.0010. **Session 21 must run Step 0 in full.**

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19 and 20, which both worked cleanly. Six rules:

1. **STEP 0 IS A GATE, NOT A VIBES-CHECK.** Run every numbered sub-check below in order, against actual disk state. Tool enumeration first — if Desktop Commander shows only a partial toolset, call `tool_search` with a query like `"start_process write_file edit_block"` to force-load. SHOW the output of each sub-check, do not just claim it passed. If the prompt's reality assertions don't match disk, STOP and surface the drift before reading anything else.

2. **STAIRCASE WITH MANDATORY HALT POINTS.** Code-touching steps get a plain-language writeup FIRST, Dan approves the concept, THEN code is written. Halts mandatory: halt before `--commit`, halt before any Chroma write, halt at scope-option selection (A/B/C/D), halt at design points where tech-lead architecture review is warranted (surface as M-options). "Approval" is asked freshly at each halt — never inherited.

3. **AUTHORITY LINE.** Claude holds tech-lead role. Tactical decisions (regex patterns, helper placement, chunking parameters, prompt versions, where a function lives) are Claude's call — make them, report them, move on. Strategic decisions (irreversible operations, money spend > $25, anything crossing RAG/app/product/legal boundaries, anything failing the "can we fix this later?" test, content-source canonicalization, schema-shape changes) flag to Dan BEFORE execution. Test for "is this strategic": can it be undone cheaply? Yes → Claude's call. No → Dan's call. When presenting scope options, include a tech-lead recommendation with rationale.

4. **ANTI-GOALS THIS SESSION (specific, not generic):**
   - NO new file-type handlers until #35 (CONTENT_SOURCES.md) lands
   - NO modifying v2 except via M3-style extract-and-redirect with byte-identical behavior verified by dry-run regression
   - NO Railway pushes
   - NO git operations by Claude — Dan runs git
   - NO reading or quoting `.env` contents
   - NO referencing Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park (scrub mechanism enforces; do not bypass)
   - NO inline heredocs for Python scripts > ~10 lines — write to file, then execute

5. **COST GATES ARE HARD CONSTRAINTS.** State projected spend up front in the staircase writeup. Existing thresholds: $1.00 interactive (ask first), $25.00 hard refuse. Track actual spend per step.

6. **CONTEXT BUDGET DISCIPLINE.** Surface a warning at 30% remaining, not 10%. Track and report context usage at each halt point so Dan can plan accordingly.

**Pace note from session 20:** Dan asked for "a little faster" mid-session. Default to larger steps with strategic-only halts; batch doc updates at session close unless changes are non-trivial enough to warrant mid-session review.

---

## CONTEXT-AVAILABILITY DISCIPLINE (NEW for s21)

**At every halt point and at every "your call" / scope decision, give Dan a one-line context budget report.** Format:

```
[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]
```

Surface a warning at 30% remaining (not 10%). If approaching 20%, recommend wrapping the current item and writing the s22 prompt before context runs out. This rule exists because session 19 noted late-session compression had cost time; session 20 hit 30%-remaining without issue but the discipline should be standing, not optional.

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `start_search` + `Filesystem:read_text_file` (or DC `read_file` if available). If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 21 ok"); print(2+2)`. Expect `session 21 ok` and `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 20 commit** landing #38 A/B verification + #37 stage-1 dedup (M-37-α refactor) + 1 new test script (4/4) + 1 new one-shot A/B script + extended dedup test (10/10 → 15/15) + doc updates.
   - Below session 20: session 19 (`2ad362b`), session 18 (`1c12155`), session 17 (`93efce3`), etc.
   - **Working tree must be completely clean.** If `git status` shows ANY modified or untracked files, STOP and surface them. The `.s20-backup` file may or may not still be on disk — if present, it's untracked and harmless; flag for Dan to delete after verification.

### 0.3 — Data plane reality

4. **Reality-vs-prompt check.** Verify these against the actual filesystem:

   - **Chroma baseline.** `rf_reference_library` should still be **605** (unchanged from session 17 close — sessions 18, 19, 20 had zero Chroma writes). If 604 or lower, an unexpected delete happened — stop. If 606+, something wrote between sessions — stop and check what.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** Should still return **8 chunk IDs**: 7 PDF + 1 v2_google_doc. **Zero docx chunks.** **None of the 8 have the s19 metadata fields** (`extraction_method`, `library_name`, `source_file_md5`, `content_hash`) populated yet — backfill is BACKLOG #39, still deferred.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); cats=[m.get('v3_category','?') for m in r['metadatas']]; print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})"
     ```
     Expected: `v3: 8 {'pdf': 7, 'v2_google_doc': 1}`. Identical to session 18/19/20 close.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → likely **34** (unchanged — no new images OCR'd in sessions 19 or 20).

   - **Drive auth.** `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python3 -c "from google.oauth2 import service_account; import os; creds = service_account.Credentials.from_service_account_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS']); print('OK', creds.service_account_email)"` — expect `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.** Same pattern, generate one-token Gemini call — expect `ok`.

   - **OpenAI auth (live).** Source `.env` in subshell, minimal `embeddings.create("test")` returning 3072 dims.

   - **Test suite — all 13 scripts must be green** (session 20 added 1 new + extended 1 existing):
     ```bash
     ./venv/bin/python scripts/test_scrub_s13.py                       # 19/19
     ./venv/bin/python scripts/test_scrub_wiring_s13.py                # PASS
     ./venv/bin/python scripts/test_types_module.py                    # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py             # PASS
     ./venv/bin/python scripts/test_format_context_s16.py              # 23/23
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py         # 16/16
     ./venv/bin/python scripts/test_google_doc_handler_synthetic.py    # 9/9
     GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_docx_handler_synthetic.py          # 12/12
     ./venv/bin/python scripts/test_v3_metadata_writer_s19.py          # 4/4
     ./venv/bin/python scripts/test_dedup_synthetic_s19.py             # 15/15 (extended s20: was 10/10)
     ./venv/bin/python scripts/test_canva_strip_synthetic_s19.py       # 15/15
     ./venv/bin/python scripts/test_stage1_dedup_wiring_s20.py         # 4/4 (NEW s20)
     ```

   - **v3 regression.** Default selection_state should resolve to DFH folder + Egg Health Guide PDF.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected: 3 files, 9 chunks, `by_handler={pdf: 1, v2_google_doc: 2}`, $0 vision (cache), ~$0.0010 projected total, est_tokens **~7,603**, **stage-1 dedup skips: 0** (the 8 existing v3 chunks have no `source_file_md5` to match against — confirmed s20). Identical to session 20 baseline.

   - **v2 regression** (only re-verify if anything in v2's path was touched): byte-identical to session 16/17/18/19 baseline (2 files / 2 chunks / 1 vision_cache_hit / ~1,303 est_tokens / $0.0002).

### 0.4 — Admin UI sanity (session 16 gate)

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If a Python process is listening, it's the carryover process — fine; admin_ui code didn't change in s19 or s20. If no process, start a fresh one with `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s21_admin_ui.log 2>&1 & disown`.

6. **Cache header active.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store`.

7. **Selection state on disk.** `cat data/selection_state.json`. Should be the DFH folder + Egg Health Guide PDF assignment, two-bucket shape.

### 0.5 — Final reality summary

8. **Print a one-line state summary** to confirm Step 0 passed:
   ```
   ✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc + 0 docx),
     OCR cache: 34, all 13 test scripts green, admin UI on PID <pid>, selection_state v2 shape OK,
     v3 dry-run shows ~7,603 est_tokens (Canva strip active), stage-1 dedup skips: 0
   ```

If anything in 0.1–0.5 fails, **STOP and surface the failure to Dan before reading any further or doing any work.**

---

## Step 1 — Read context (~5 minutes)

After Step 0 passes, read these in this order:

1. **`docs/HANDOVER.md` — session 20 entry** (the bottom section, ~144 lines). Tells you what shipped (#37 closed via M-37-α refactor, #38 closed with strong A/B numbers, #29 fully closed), why the 8 existing v3 chunks still have no md5 (deferred to #39), and the M-options selected for each design decision.

2. **`docs/BACKLOG.md` — items #39 (still deferred), #35 (still untouched), #21 (UI redesign).** These plus #20 (inline citation prompting) are the candidates for session 21 scope.

3. **Optionally:** `docs/STATE_OF_PLAY.md` (last amended at session 18). HANDOVER sessions 19 and 20 capture everything STATE_OF_PLAY would have.

---

## Step 2 — Scope decision (Dan picks)

Several reasonable directions for session 21. Tech-lead recommendation at the bottom.

### Option A — #39: backfill the 8 existing v3 chunks

The first Chroma write since session 17. Re-ingest the 8 existing v3 chunks (DFH folder + Sugar Swaps + Egg Health Guide) so they pick up the new s19/s20 metadata fields (`extraction_method`, `library_name`, `source_file_md5`, `content_hash`).

**Why valuable:**
- Activates stage-1 dedup against existing chunks (currently fires on nothing since no md5s populated)
- Replaces the polluted Sugar Swaps chunk with the strip-ON version (closes the s20 #38 follow-on)
- Makes the four new metadata fields actually present on every v3 chunk (not just future ones)

**Spend:** ~$0.001 embeddings.
**Risk:** First Chroma write since s17. Upsert in place — no orphans, no deletions. Dan must OK before commit. Halt before `--commit` is mandatory.

### Option B — #35: CONTENT_SOURCES.md

Single deliverable: `docs/CONTENT_SOURCES.md` mapping content domain → canonical Drive folder(s) → file forms to ingest vs. skip. Conversation-heavy, low API spend. Untouched since first proposed in s18. **Gates all bulk ingestion of new content domains** (#36 blogs commit + future Reddit/IG/blog ingestions are all blocked on this).

**Effort:** ~1.5 hours conversation. **Spend:** $0.

### Option C — #21: Folder-selection UI redesign

Standalone, no data-plane risk. Removes pending-panel/tree redundancy. Single biggest UX friction point per s16. Pure UI work — no Chroma, no Drive, no embedding.

**Effort:** ~60-90 min. **Spend:** $0.

### Option D — #20: Inline citation prompting

Add to both persona prompts (`nashat_sales.yaml`, `nashat_coaching.yaml`) something prompting Sonnet to inline-cite source filenames + page locators. A/B test on representative queries to ensure response quality doesn't regress. Bundles naturally with #18 (`format_context()` migration) but can ship standalone.

**Effort:** ~1 hour including A/B. **Spend:** ~$0.05 (a few Sonnet 4.6 chat calls).

### Tech-lead recommendation: **Option A (#39)**, then **Option C (#21)** if time allows.

Reasoning:
1. **#39 unlocks the latent value built in s19+s20.** Stage-1 dedup, Canva strip, new metadata fields — all are wired but only operate on future writes. #39 makes them operate on the existing corpus too.
2. **The Chroma-write skill needs exercising.** Sessions 18, 19, 20 all had no-write constraints. The s17 commit-run pattern (halt before --commit, show dump-json, OK gate, post-write verification) hasn't been used since session 17. Worth running it through on a small (8-chunk) low-risk write before the corpus grows.
3. **#21 is the natural pairing** — once the data work is done, ship a clean standalone UI item to bank that win too.
4. **#35 is high-value but conversation-bound** — better when Dan has dedicated focus rather than after a code-execution session.
5. **#20 is good standalone but slightly more brittle** — A/B testing on agent prompts can produce ambiguous "is this better?" results.

**If only one item:** **#39** alone. Smallest closure of the s19/s20 deferred work, exercises the Chroma-write path, ~30 min plus halt time.

---

## Step 3+ — Execute the chosen scope

Once Dan picks, scope a tight plan **before** writing any code:
1. List the files you'll touch
2. List the test scripts you'll write or update
3. List any data writes (Chroma operations, file edits) and identify halt points
4. Identify the "minimum viable closure"
5. Estimate spend in API calls

Get Dan's approval on the plan, THEN execute.

**Standing rules carried forward (do not skip):**

- **Halt before `--commit`.** Show Dan dump-json before any write to Chroma. (Session 14 lesson.)
- **Halt before any direct Chroma write of any kind.** No exceptions.
- **No deletions** (files, chunks, collections) without approval AND a backup of the affected state.
- **Pipe commit stdout to file**, not `| tail` — session 16 lesson.
- **Tech-lead volunteers architecture review at design-halt points.** Surface M-options before code when a design has uncertainty.
- **Read the Flask access log first** when debugging UI cache or save issues. (Session 16 lesson.)
- **Test in Chrome before Safari** for admin UI iterative work. (Session 16 lesson.)
- **When closing a BACKLOG item, verify in the environment where it manifested.** (Session 16/17 lesson.)
- **No Railway writes from sessions.** Railway is read-only.
- **No touching legacy collections** (`rf_coaching_transcripts`, pre-scrub 584 A4M) without Dan's explicit OK.
- **Credentials ephemeral** — never read `.env` content into chat.
- **Never reference Dr. Christina / Dr. Chris / Dr. Massinople** in agent responses, sample chunks, test data, anywhere.
- **Dan does git operations**, not Claude.
- **v2 frozen** unless extract-and-redirect to a shared module with byte-identical behavior verified by dry-run regression.
- **When piloting a new feature, scan for real-world examples that exercise the feature.**
- **Prefer write-script-to-file over inline heredocs** for Python > ~10 lines.
- **Pre-commit drift audit on any new handler.**
- **Don't ingest a content domain until its source-of-truth is documented.**
- **Build the safety net before the surface area grows.**

**Three rules from session 19 (still active):**
- When the constraint is "no Chroma writes," respect it sharply (Path Z pattern).
- A/B testing on n=1 is honest small-N work — report directional deltas as directional.
- Drift audit by replicated-block test beats live Chroma audit.

**Three new rules from session 20:**
- **The "no Chroma writes" constraint is fully compatible with substantial progress.** Two BACKLOG items closed at zero data risk. Pattern: read-only Chroma queries are safe; writes are the gate.
- **Pre-flight read of the Chroma state can reveal why a feature won't fire before code is even written.** Always check whether the data the feature queries actually exists.
- **Sequencing matters when items interact.** When two BACKLOG items touch the same chunk, check whether one would destroy the baseline the other needs. Surface at scope-decision time.

---

## Budget for session 21

- **$1.00 interactive gate.** If any single task projects above $1.00, halt and surface to Dan.
- **$25.00 hard refuse.**
- **Session 20 spent ~$0.0003.** Session 21 expected: ~$0.001 if Option A executes (#39 backfill), $0 for Options B/C, ~$0.05 for Option D.

## Files you'll likely touch (depending on scope)

**For Option A (#39):**
- `data/selection_state.json` — confirm it covers all 8 chunks (DFH folder + Sugar Swaps + Egg Health Guide)
- Run `--commit` against drive_loader_v3, halt before commit, show dump-json
- After commit: read-only verification that all 8 chunks now have `extraction_method`, `library_name`, `source_file_md5`, `content_hash`, and that Sugar Swaps text no longer contains the Canva URL line
- `docs/HANDOVER.md`, `docs/BACKLOG.md`

**For Option B (#35):**
- New: `docs/CONTENT_SOURCES.md`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`

**For Option C (#21):**
- `admin_ui/static/folder-tree.js`
- `admin_ui/templates/folders.html`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`

**For Option D (#20):**
- `config/agents/nashat_sales.yaml`
- `config/agents/nashat_coaching.yaml`
- New: `scripts/test_inline_citation_ab_s21.py` (A/B test against representative queries)
- `docs/HANDOVER.md`, `docs/BACKLOG.md`

## Files you should NOT touch

- `chroma_db/*` — never edit directly. Any writes go through the v3 commit path.
- `data/inventories/*.json` — folder walk output, never hand-edit.
- `data/audit.jsonl` — append-only via the audit module.
- `ingester/loaders/drive_loader.py` (v1) — frozen.
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except for M3-style extract-and-redirect.
- `ingester/loaders/types/pdf_handler.py` — out of scope.
- `ingester/loaders/types/docx_handler.py` — shipped session 18, no changes needed.
- `ingester/loaders/types/google_doc_handler.py` — shipped session 17 + session 19 strip, no changes needed unless adding new strip patterns.
- `ingester/loaders/drive_loader_v3.py` — modified in s20 (M-37-α). Don't touch unless a specific BACKLOG item directs it.

## Step 0 cheat sheet (for quick reference at the start of session 21)

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Chroma baseline (expect 605 — unchanged from session 17 close)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks (expect 8 = 7 pdf + 1 v2_google_doc, no s19 backfill yet)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); cats=[m.get('v3_category','?') for m in r['metadatas']]; print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})"

# Test suite (expect all 13 green)
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
set -a && . ./.env && set +a
for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py scripts/test_v3_metadata_writer_s19.py scripts/test_dedup_synthetic_s19.py scripts/test_canva_strip_synthetic_s19.py scripts/test_stage1_dedup_wiring_s20.py; do
  echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -2
done

# v3 dry-run (expect 9 chunks, $0.0010, est_tokens ~7,603, stage-1 skips: 0)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
```

If all of the above passes, print:
```
✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc + 0 docx),
  OCR cache: 34, all 13 tests green, admin UI on PID <pid>, selection_state v2 shape OK,
  v3 est_tokens ~7,603 (Canva strip active), stage-1 dedup skips: 0
```

Then proceed to Step 1.

---

## End of session 21 prompt

Session 20 closed BACKLOG #38 (live A/B verification of Canva strip — strong directional signal in both directions) and #37 (stage-1 dedup via M-37-α refactor — Chroma client moved up top, stage-1 fires inside dispatch loop before extraction). #29 now fully resolved. Zero Chroma writes per Dan's session-open constraint. System has 605 chunks, 8 of them v3-ingested, none with s19/s20 metadata fields populated yet (deferred to #39). Thirteen test scripts green. Working tree clean (after session 20 commit lands). Good luck.
