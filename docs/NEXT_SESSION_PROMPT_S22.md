# NEXT SESSION PROMPT — session 22

> **⚠ READ THIS FIRST**
>
> Step 0 has paid for itself every session 9 onward. Session 21 used it to discover that the prompt's "8 chunks across 3 files" assertion didn't match the selection_state — Halt 1 caught it before the commit would have ingested 2 unrelated new files. **Session 22 must run Step 0 in full**, with sharpened attention on the selection_state vs existing-chunks comparison.

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19, 20, 21. Six rules unchanged:

1. **STEP 0 IS A GATE, NOT A VIBES-CHECK.** Run every numbered sub-check below in order, against actual disk state. Tool enumeration first — if Desktop Commander shows only a partial toolset, call `tool_search` with a query like `"start_process write_file edit_block"` to force-load. SHOW the output of each sub-check. If reality doesn't match assertions, STOP and surface drift before reading further.
2. **STAIRCASE WITH MANDATORY HALT POINTS.** Plain-language writeup → Dan approves concept → code is written. Halts mandatory before `--commit`, before any Chroma write, at scope-option selection (A/B/C/D), at design points warranting tech-lead architecture review (M-options).
3. **AUTHORITY LINE.** Tactical → Claude. Strategic → Dan. Test: "can this be undone cheaply?" Yes → Claude. No → Dan. Surface tech-lead recommendations with rationale on scope decisions.
4. **ANTI-GOALS THIS SESSION:**
   - NO new file-type handlers until #35 (CONTENT_SOURCES.md) lands
   - NO modifying v2 except via M3-style extract-and-redirect with byte-identical dry-run regression
   - NO Railway pushes
   - NO git operations by Claude
   - NO reading or quoting `.env` contents
   - NO referencing Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park (scrub mechanism enforces; do not bypass)
   - NO inline heredocs for Python > ~10 lines
5. **COST GATES.** $1.00 interactive, $25.00 hard refuse. State projected spend up front. Track actual spend per step.
6. **CONTEXT BUDGET DISCIPLINE.** One-line context report at every halt: `[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]`. Surface warning at 30% remaining; at 20% recommend wrapping the current item and writing s23 prompt.

**Pace from session 21:** Larger steps with strategic-only halts. Doc updates batched at session close. (Session 21 hit the 30% threshold right as #39 closed — natural stopping point. Worked well.)

---

## Step 0 — Tool and reality check (mandatory)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `start_search` + `Filesystem:read_text_file`. If partial DC toolset visible, call `tool_search`.
2. **Smoke test.** Start `python3 -i`, send `print("session 22 ok"); print(2+2)`. Expect `session 22 ok` / `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 21 commit** landing #39 backfill (8 v3 chunks upserted) + 2 new one-shot scripts (`snapshot_v3_chunks_pre_s21.py`, `verify_sugar_strip_in_production_s21.py`) + selection_state backup + 1 chunk-level snapshot JSON + doc updates (HANDOVER session 21 entry, BACKLOG #39 marked RESOLVED).
   - Below session 21: session 20 (`fdf0f78`), session 19 (`2ad362b`), session 18 (`1c12155`), etc.
   - **Working tree must be clean.** All `data/*` artifacts are gitignored, so run records and snapshots from s21 (`data/ingest_runs/*.json`, `data/snapshots/v3_chunks_pre_s21_n39.json`, `data/selection_state.json.s21-backup`) won't appear in `git status`. The s21 chroma backup dir was deleted at session close.

### 0.3 — Data plane reality

4. **Reality-vs-prompt check.**

   - **Chroma baseline.** `rf_reference_library` should be **605** (s21 was pure upsert; count unchanged from s17 close).
     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** Should return **8 chunk IDs**: 7 PDF + 1 v2_google_doc. **All 8 should now have `extraction_method`, `library_name`, `content_hash` populated; 7/8 have `source_file_md5` (Google Doc empty by Drive-API design).** This is the s21 #39 closure state.
     ```bash
     ./venv/bin/python3 -c "
     import chromadb
     c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db')
     col=c.get_collection('rf_reference_library')
     r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30)
     cats=[m.get('v3_category','?') for m in r['metadatas']]
     print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})
     for f in ['extraction_method','library_name','source_file_md5','content_hash']:
         n=sum(1 for m in r['metadatas'] if m.get(f))
         print(f'  {f}: {n}/8')
     "
     ```
     Expected: `v3: 8 {'pdf': 7, 'v2_google_doc': 1}` plus `extraction_method: 8/8`, `library_name: 8/8`, `source_file_md5: 7/8`, `content_hash: 8/8`.

   - **Sugar Swaps chunk is strip-ON in production.** Quick spot-check.
     ```bash
     ./venv/bin/python3 -c "
     import chromadb
     c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db')
     col=c.get_collection('rf_reference_library')
     r=col.get(ids=['drive:3-marketing:1ucqhpCFg5fmj78XyU2yj0ANGM3kJuG7Tuut1jBd2Vrk:0000'], include=['documents'])
     t=r['documents'][0]
     print('len:', len(t), 'has_canva:', 'canva.com' in t, 'starts_cover:', t.lstrip().startswith('COVER:'))
     "
     ```
     Expected: `len: 3737 has_canva: False starts_cover: False`.

   - **OCR cache.** `ls data/image_ocr_cache/*.json | wc -l` → **34** (unchanged).

   - **Drive auth.** `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python3 -c "from google.oauth2 import service_account; import os; creds = service_account.Credentials.from_service_account_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS']); print('OK', creds.service_account_email)"` — expect `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth.** Same pattern, generate one-token Gemini call — expect `ok`.

   - **OpenAI auth.** Source `.env` in subshell, minimal `embeddings.create("test")` returning 3072 dims.

   - **Test suite — all 13 scripts must be green** (no new tests added in s21):
     ```bash
     ./venv/bin/python scripts/test_scrub_s13.py                       # 19/19
     ./venv/bin/python scripts/test_scrub_wiring_s13.py                # PASS
     ./venv/bin/python scripts/test_types_module.py                    # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py             # PASS
     ./venv/bin/python scripts/test_format_context_s16.py              # 23/23
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py         # 16/16  (clobbers selection_state — #31)
     ./venv/bin/python scripts/test_google_doc_handler_synthetic.py    # 9/9
     GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_docx_handler_synthetic.py          # 12/12
     ./venv/bin/python scripts/test_v3_metadata_writer_s19.py          # 4/4
     ./venv/bin/python scripts/test_dedup_synthetic_s19.py             # 15/15
     ./venv/bin/python scripts/test_canva_strip_synthetic_s19.py       # 15/15
     ./venv/bin/python scripts/test_stage1_dedup_wiring_s20.py         # 4/4
     ```

   - **v3 dry-run regression.** With selection_state in s16 shape (where `test_admin_save_endpoint_s16.py` left it):
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected: 3 files, 9 chunks, by_handler `{pdf: 1, v2_google_doc: 2}`, vision_cache_hit, est_tokens ~7,603, $0.0010, **stage-1 dedup skips: 0** (re-ingesting same file_id self-matches and falls through — correct, not a bug; #37 fires only on cross-file_id md5 matches).

### 0.4 — Admin UI

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If a Python process is listening, fine. If not, start one: `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s22_admin_ui.log 2>&1 & disown`.
6. **Cache header.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store` (and a 302 to /login is normal — auth gate).
7. **Selection state on disk.** `cat data/selection_state.json`. Should be the s16 shape: `selected_folders: ["18S1Vf..."]`, `selected_files: ["1oJyks..."]`, library_assignments for both. (After s21 close, `test_admin_save_endpoint_s16.py` restored this shape per BACKLOG #31.)

### 0.5 — Final summary

8. **Print:**
   ```
   ✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc),
     all 4 s19 metadata fields populated (8/8 except source_file_md5 7/8 by design),
     Sugar Swaps strip-ON in production (3737 chars, no canva.com),
     OCR cache: 34, all 13 test scripts green, admin UI on PID <pid>,
     v3 dry-run shows 9 chunks / ~7,603 est_tokens / $0.0010 / stage-1 skips: 0
   ```

If anything fails, STOP and surface to Dan.

---

## Step 1 — Read context

After Step 0 passes, read:

1. **`docs/HANDOVER.md` — session 21 entry** (~130 lines at the bottom). Tells you what shipped (#39 closed, Sugar Swaps strip-ON live, A/B verified, 5 lessons), the selection_state drift caught at Halt 1, and the chunk-ID determinism verification pattern that should be reused.
2. **`docs/BACKLOG.md` — items #35, #21, #20, #31** (the candidates for s22 scope).
3. **Optional:** `docs/STATE_OF_PLAY.md` (last amended at s18 — HANDOVER s19/20/21 entries supersede).

---

## Step 2 — Scope decision (Dan picks)

### Option A — #35: CONTENT_SOURCES.md

Single deliverable: `docs/CONTENT_SOURCES.md` mapping content domain → canonical Drive folder(s) → file forms to ingest vs. skip. Dan walks the inventory, Claude documents. **Gates all bulk ingestion of new content domains** (#36 blogs commit + future Reddit/IG/blog ingestions blocked on this). Conversation-heavy, low API spend.

**Effort:** ~1.5 hours conversation. **Spend:** $0.

### Option B — #21: Folder-selection UI redesign

Standalone, no data-plane risk. Removes pending-panel/tree redundancy. Single biggest UX friction point per s16. Pure UI work — no Chroma, no Drive, no embedding.

**Effort:** ~60–90 min. **Spend:** $0.

### Option C — #20: Inline citation prompting

Add to both persona prompts (`nashat_sales.yaml`, `nashat_coaching.yaml`) instructions to inline-cite source filenames + page locators. A/B test on representative queries. Bundles naturally with #18 (`format_context()` migration) but ships standalone.

**Effort:** ~1 hour including A/B. **Spend:** ~$0.05 (Sonnet 4.6 chat calls).

### Option D — #31: Fix `test_admin_save_endpoint_s16.py` selection_state clobber

Quick win. The test currently restores selection_state to a hardcoded s16 shape after running, which has bitten 3+ sessions. Fix: have the test snapshot-and-restore the actual pre-test state instead of writing a hardcoded one.

**Effort:** ~20 min. **Spend:** $0.

### Tech-lead recommendation: **Option A (#35)** if Dan has dedicated focus for the inventory walk; otherwise **Option D (#31)** as a 20-min cleanup + **Option B (#21)** as a UI win in the same session.

Reasoning:
1. **#35 is the highest-leverage strategic item left.** It blocks #36 (blogs commit) and gates all future bulk ingestion. Worth a dedicated session when Dan can think through canonical-source decisions across the corpus.
2. **#35 is conversation-bound, not code-bound.** Better when not also tracking code execution. Don't pair it with anything heavy.
3. **#21 is the cleanest UI win** — no data risk, ~60-90 min, biggest friction point per s16 lessons. Good "fresh context" item.
4. **#20 is interesting but A/B on agent prompts produces ambiguous "is this better?" results** — needs careful A/B design.
5. **#31 is small enough to bundle with anything else** — the kind of cleanup that's been deferred 3 sessions. Worth knocking out.

**If Dan picks #35:** scope it tight. Don't write more than a strawman + Dan's edits. The doc only needs to be useful enough to unblock #36, not perfect.

**If Dan picks #21:** plan to ship one well-designed iteration, not a full UI overhaul. The s16 redesign sketch in BACKLOG #21 is concrete enough to execute against.

---

## Step 3+ — Execute

Once Dan picks, scope tight plan **before** writing code:
1. Files touched
2. Test scripts written/updated
3. Data writes (Chroma, file edits) and halt points
4. Minimum viable closure
5. Spend estimate

Get approval, THEN execute.

**Standing rules carried forward (do not skip):**

- **Halt before `--commit`.** Show dump-json before any Chroma write.
- **Halt before any direct Chroma write.** No exceptions.
- **No deletions** without approval AND backup.
- **Pipe commit stdout to file**, not `| tail`.
- **Surface M-options at design halts** when uncertainty warrants tech-lead review.
- **Read Flask access log first** when debugging UI cache/save issues.
- **Test in Chrome before Safari** for admin UI iterative work.
- **When closing a BACKLOG item, verify in the environment where it manifested.**
- **No Railway writes.**
- **No touching legacy collections** without Dan's explicit OK.
- **Credentials ephemeral** — never read `.env` content into chat.
- **Never reference Dr. Christina / Dr. Chris / Massinople** anywhere.
- **Dan does git operations.**
- **v2 frozen** unless extract-and-redirect.
- **Prefer write-script-to-file** over inline heredocs for Python > ~10 lines.
- **Pre-commit drift audit on any new handler.**
- **Don't ingest a content domain until its source-of-truth is documented.**
- **Build the safety net before the surface area grows.**

**Five new rules from session 21:**
- **Read selection_state against existing chunks before trusting prompt assertions.** When a prompt asserts "X chunks across Y files via Z folder," run a `getall` on `source_pipeline=drive_loader_v3` chunks and compare file_ids against the selection_state cascade before any commit. Halt 1 of s21 caught a 2-file accidental-ingest that would have happened otherwise.
- **Chunk-ID determinism is the strongest no-orphan guarantee.** `build_chunk_id` formula at `_drive_common.py:234` is a 1-line read; verify it in pre-flight rather than relying on post-write checks.
- **Stage-1 dedup not firing on a re-ingest is correct, not a bug.** Stage-1 only fires on cross-file_id md5 matches. Same file_id self-matches and falls through.
- **Empirical A/B re-verification on a known-changed chunk is cheap and high-confidence.** ~$0.0001 + 5 min to confirm production matches prior A/B winner. Worth doing whenever a Chroma write is supposed to land a previously-tested transformation.
- **#31 keeps biting at session-close.** Worth fixing as a 20-min cleanup item (Option D this session).

---

## Budget for session 22

- **$1.00 interactive gate.**
- **$25.00 hard refuse.**
- **Session 21 spent ~$0.0011.** Session 22 expected: $0 for A/B/D, ~$0.05 for C.

## Files NOT to touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via audit module
- `ingester/loaders/drive_loader.py` (v1) — frozen
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except via M3 extract-and-redirect
- `ingester/loaders/types/*` — out of scope unless a specific item directs
- `ingester/loaders/drive_loader_v3.py` — modified s20 (M-37-α), s21 used as-is. Don't touch unless a BACKLOG item directs.

---

## Step 0 cheat sheet

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Chroma baseline (expect 605 — unchanged)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks (expect 8, all 4 metadata fields populated except source_file_md5: 7/8)
./venv/bin/python3 -c "
import chromadb
c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db')
col=c.get_collection('rf_reference_library')
r=col.get(where={'source_pipeline':'drive_loader_v3'}, limit=30)
cats=[m.get('v3_category','?') for m in r['metadatas']]
print('v3:', len(r['ids']), {c: cats.count(c) for c in set(cats)})
for f in ['extraction_method','library_name','source_file_md5','content_hash']:
    n=sum(1 for m in r['metadatas'] if m.get(f))
    print(f'  {f}: {n}/8')
"

# Sugar Swaps strip-ON spot check
./venv/bin/python3 -c "
import chromadb
c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db')
col=c.get_collection('rf_reference_library')
r=col.get(ids=['drive:3-marketing:1ucqhpCFg5fmj78XyU2yj0ANGM3kJuG7Tuut1jBd2Vrk:0000'], include=['documents'])
t=r['documents'][0]
print('len:', len(t), 'has_canva:', 'canva.com' in t, 'starts_cover:', t.lstrip().startswith('COVER:'))
"

# Test suite (expect all 13 green)
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
set -a && . ./.env && set +a
for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py scripts/test_v3_metadata_writer_s19.py scripts/test_dedup_synthetic_s19.py scripts/test_canva_strip_synthetic_s19.py scripts/test_stage1_dedup_wiring_s20.py; do
  echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -2
done

# v3 dry-run (expect 9 chunks / $0.0010 / stage-1 skips: 0)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
```

If all passes, print the Step 0 summary line and proceed to Step 1.

---

## End of session 22 prompt

Session 21 closed BACKLOG #39 (backfill of all 8 v3 chunks with s19 metadata fields, plus Sugar Swaps strip applied in production). First Chroma write since s17, executed cleanly via the snapshot → halt → upsert → verify pattern. Empirical A/B re-verification confirmed production retrieval matches s20 strip-ON winner. System still has 605 chunks in `rf_reference_library`, all 8 v3 chunks now metadata-complete. Thirteen test scripts green. Chroma backup deleted at session close (484 MB recovered); chunk-level JSON snapshot retained at `data/snapshots/v3_chunks_pre_s21_n39.json` for surgical recovery if ever needed. Good luck.
