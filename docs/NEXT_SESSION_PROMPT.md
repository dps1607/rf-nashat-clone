# NEXT SESSION PROMPT — session 20

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Step 0 has paid for itself every session 9 onward. Session 19 used it to confirm session 18's docx handler hadn't drifted, all auths were live, and v3 dry-run still produced 9 chunks at $0.0010. **Session 20 must run Step 0 in full.**

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `read_file` + `write_file` + `edit_block` + `start_search`. If only a partial DC toolset is visible, call `tool_search` with a relevant query to force-load the rest.

2. **Smoke test process execution.** Run `python3 -i`, verify `>>>` prompt, send `print("session 20 ok"); 2+2`. Expect `session 20 ok` and `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 19 commit** landing the dedup helpers + Canva strip + #30 metadata writer fix + 3 new test scripts (29 individual tests across them) + 3 doc updates + 3 new BACKLOG items #37-#39 + no Chroma writes.
   - Below session 19: session 18 (`1c12155`), session 17 (`93efce3`), session 16 (`98f8011`), etc.
   - **Working tree must be completely clean.** If `git status` shows ANY modified or untracked files, STOP and surface them.

### 0.3 — Data plane reality

4. **Reality-vs-prompt check.** Verify these against the actual filesystem:

   - **Chroma baseline.** `rf_reference_library` should still be **605** (unchanged from session 17 close — sessions 18 and 19 had zero Chroma writes). If 604 or lower, an unexpected delete happened — stop. If 606+, something wrote between sessions — stop and check what.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** Should still return **8 chunk IDs**: 7 PDF + 1 v2_google_doc. **Zero docx chunks.** **None of the 8 have the new s19 metadata fields** (`extraction_method`, `library_name`, `source_file_md5`, `content_hash`) populated yet — backfill is BACKLOG #39.

     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); cats=[m.get('v3_category','?') for m in r['metadatas']]; print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})"
     ```
     Expected: `v3: 8 {'pdf': 7, 'v2_google_doc': 1}`. Identical to session 18/19 close.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → likely **34** (unchanged — no new images OCR'd in session 19).

   - **Drive auth.** Same command as session 19 — expect `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.** Same command — expect `ok`.

   - **OpenAI auth (live).** Source `.env` in subshell, minimal `embeddings.create("test")` returning 3072 dims.

   - **Test suite — all 12 scripts must be green** (session 19 added 3: v3_metadata_writer_s19, dedup_synthetic_s19, canva_strip_synthetic_s19):
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
     ./venv/bin/python scripts/test_v3_metadata_writer_s19.py          # 4/4 (NEW s19)
     ./venv/bin/python scripts/test_dedup_synthetic_s19.py             # 10/10 (NEW s19)
     ./venv/bin/python scripts/test_canva_strip_synthetic_s19.py       # 15/15 (NEW s19)
     ```

   - **v1 regression.** `files ingested: 1`, 2 low-yield skips (unchanged).

   - **v2 regression.** Must be byte-identical to session 16/17/18/19 baseline: 2 files, 2 chunks, 1 vision_cache_hit, ~1,303 est_tokens, $0.0002.

   - **v3 regression.** Default selection_state should resolve to DFH folder + Egg Health Guide PDF.
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected: 3 files, 9 chunks, `by_handler={pdf: 1, v2_google_doc: 2}`, $0 vision (cache), ~$0.0010 projected total. **est_tokens should be ~7,603 (NOT 7,605)** — that 2-token delta is the Canva strip removing pollution from Sugar Swaps. If you see ~7,605 the strip didn't fire — investigate.

### 0.4 — Admin UI sanity (session 16 gate)

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If a Python process is listening, it's the session 18 process — fine; admin_ui code didn't change in s19. If no process, start a fresh one with `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s20_admin_ui.log 2>&1 & disown`.

6. **Cache header active.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store`.

7. **Selection state on disk.** `cat data/selection_state.json`. Should be the DFH folder + Egg Health Guide PDF assignment, two-bucket shape.

### 0.5 — Final reality summary

8. **Print a one-line state summary** to confirm Step 0 passed:
   ```
   ✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc + 0 docx),
     OCR cache: 34, all 12 test scripts green, admin UI on PID <pid>, selection_state v2 shape OK,
     v3 dry-run shows ~7,603 est_tokens (Canva strip active)
   ```

If anything in 0.1–0.5 fails, **STOP and surface the failure to Dan before reading any further or doing any work.**

---

## Step 1 — Read context (~5 minutes)

After Step 0 passes, read these in this order:

1. **`docs/HANDOVER.md` — session 19 entry** (the bottom section, ~150 lines). Tells you what shipped (#30 done, #23 stage-2 done with stage-1 deferred to #37, #29 code done with A/B deferred to #38), why backfill of existing chunks was deferred (#39), and the M-options selected for each design decision.

2. **`docs/BACKLOG.md` — items #37, #38, #39 (new s19), plus #35 (still untouched), and #21 (the long-standing folder-selection UI redesign).** These are the candidates for session 20 scope.

3. **Optionally:** `docs/STATE_OF_PLAY.md` session 18 amendment (still the most recent — session 19 did not amend STATE_OF_PLAY to save context). HANDOVER session 19 captures everything STATE_OF_PLAY would have.

---

## Step 2 — Scope decision (Dan picks)

Several reasonable directions for session 20. Tech-lead recommendation at the bottom.

### Option A — The deferred s19 trio (#37 + #38 + #39)

Land everything session 19 deferred. Three small items that compound:
- **#39 (re-ingest the 8 existing v3 chunks)** — populates the new s19 metadata fields on all chunks. ~$0.001. Requires Dan's OK on a Chroma write (it's an upsert in place, no orphans, no deletions).
- **#38 (A/B retrieval test on Sugar Swaps Canva strip)** — corroborates the synthetic test results with live retrieval similarity numbers. ~$0.001.
- **#37 (Stage 1 dedup)** — Chroma-client-up-top refactor + pre-extraction md5 check. ~2 hours, no spend, no Chroma writes (read-only query).

**Estimated effort:** ~4 hours, one session. **Spend:** ~$0.002 + Dan's OK on the #39 write.

### Option B — Content sources doc (#35)

Single deliverable: `docs/CONTENT_SOURCES.md` mapping content domain → canonical Drive folder(s) → file forms to ingest vs. skip. Conversation-heavy, low API spend. Was Option B in session 19; deferred.

**Estimated effort:** ~1.5 hours.

### Option C — Resume handler work (a new file type)

The dedup safety net (#23 stage-2) is now in place. The Canva strip (#29) is in place. Both protect future handler work. Per the existing `MIME_CATEGORY` table, the next priorities are: **plaintext** (text/plain, text/markdown) → small + low-risk → **slides** (pptx) → larger → **sheets** (xlsx) → larger still.

**Estimated effort:** ~3-4 hours including drift audit + dry-run.

### Option D — Folder-selection UI redesign (#21)

Biggest UX friction point per session 16. Standalone, no dependencies on RAG/data plane work. ~60-90 min.

### Tech-lead recommendation: **Option A**, with #38 and #39 first, #37 if time allows.

Reasoning:
1. Closing the deferred trio makes session 19's investment fully realized. #39 in particular gives the new metadata fields actual coverage (currently they exist only on chunks that don't exist yet).
2. #38 is the verification that closes BACKLOG #29 fully — currently #29 is "code shipped, not yet measured against real corpus."
3. #37 is the lowest priority of the three (vision OCR caching makes its real-world impact small) — can slip to session 21 if needed.
4. Option B (#35) is high-value but conversation-bound — better when Dan has dedicated focus.
5. Option C (new handler) violates the session 18 lesson "don't ingest a content domain until its source-of-truth is documented" — needs #35 first.
6. Option D (#21) is good standalone work but doesn't compound with anything else in flight.

If only one: **#39 + #38** as the smallest closure of session 19's loose ends. Both touchable in ~90 min.

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

- **Halt before --commit.** Show Dan dump-json before any write to Chroma. (Session 14 lesson.)
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

**Three new rules from session 19:**

- **When the constraint is "no Chroma writes," respect it sharply.** Path Z (defer the Chroma-client-up-top refactor) was the right call in session 19. Don't argue around hard constraints — work within them.
- **A/B testing on n=1 is honest small-N work.** Don't oversell directional wins; report them as directional.
- **Drift audit by replicated-block test beats live Chroma audit.** When verifying a metadata writer fix, write a synthetic test that replicates the exact dispatcher block. It catches future drift loudly without side effects.

- **Watch context budget proactively.** Surface a warning at 30% remaining, not 10%. (Session 19 self-critique.)

---

## Budget for session 20

- **$1.00 interactive gate.** If any single task projects above $1.00, halt and surface to Dan.
- **$25.00 hard refuse.**
- **Session 19 spent ~$0.0001.** Session 20 expected: ~$0.002 if Option A executes (small embedding spend for #38 and #39).

## Files you'll likely touch (depending on scope)

**For Option A:**
- `ingester/loaders/drive_loader_v3.py` (#37 Chroma-client-up-top refactor + stage-1 logic)
- New: `scripts/test_canva_strip_ab_existing_chunks_s20.py` (#38 A/B retrieval)
- New: `scripts/test_dedup_stage1_synthetic_s20.py` (#37 stage-1 tests)
- `data/selection_state.json` (#39 — temporarily widen to include the 8 v3 chunks for re-ingest, then restore)

**For Option B:**
- New: `docs/CONTENT_SOURCES.md`
- `docs/HANDOVER.md`, `docs/BACKLOG.md`, `docs/STATE_OF_PLAY.md`

## Files you should NOT touch

- `chroma_db/*` — never edit directly. Any writes go through the v3 commit path.
- `data/inventories/*.json` — folder walk output, never hand-edit.
- `data/audit.jsonl` — append-only via the audit module.
- `ingester/loaders/drive_loader.py` (v1) — frozen.
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except for M3-style extract-and-redirect.
- `ingester/loaders/types/pdf_handler.py` — out of scope.
- `ingester/loaders/types/docx_handler.py` — shipped session 18, no changes needed.
- `ingester/loaders/types/google_doc_handler.py` — shipped session 17 + session 19 strip, no changes needed unless adding new strip patterns.

## Step 0 cheat sheet (for quick reference at the start of session 20)

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Chroma baseline (expect 605 — unchanged from session 17 close)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks (expect 8 = 7 pdf + 1 v2_google_doc, no s19 backfill yet)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30); cats=[m.get('v3_category','?') for m in r['metadatas']]; print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})"

# Test suite (expect all 12 green)
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
set -a && . ./.env && set +a
for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py scripts/test_v3_metadata_writer_s19.py scripts/test_dedup_synthetic_s19.py scripts/test_canva_strip_synthetic_s19.py; do
  echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -3
done

# v3 dry-run (expect 9 chunks, $0.0010, est_tokens ~7,603 — Canva strip active)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
```

If all of the above passes, print:
```
✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc + 0 docx),
  OCR cache: 34, all 12 tests green, admin UI on PID <pid>, selection_state v2 shape OK,
  v3 est_tokens ~7,603 (Canva strip active)
```

Then proceed to Step 1.

---

## End of session 20 prompt

Session 19 closed the dedup safety net + Canva strip + #30 metadata writer fix at the code level, with three deferred items (#37 stage-1 dedup, #38 A/B retrieval test, #39 backfill of new fields on existing v3 chunks). System has 605 chunks, 8 of them v3-ingested. Zero Chroma writes since session 17. Twelve test scripts green. Working tree clean (after session 19 commit lands). Good luck.
