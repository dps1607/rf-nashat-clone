# NEXT SESSION PROMPT — session 23

> **⚠ READ THIS FIRST**
>
> Step 0 has paid for itself every session 9 onward. Session 21 used it to discover the prompt's "8 chunks across 3 files" assertion didn't match selection_state — Halt 1 caught a 2-file accidental-ingest. Session 22 caught a too-tight Vertex AI smoke test (5 tokens eaten by reasoning overhead). **Session 23 must run Step 0 in full**, with the cheat-sheet updates noted below.

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19, 20, 21, 22. Six rules unchanged:

1. **STEP 0 IS A GATE, NOT A VIBES-CHECK.** Run every numbered sub-check below in order, against actual disk state. Tool enumeration first — if Desktop Commander shows only a partial toolset, call `tool_search` with `"start_process write_file edit_block"` to force-load. Same for Filesystem if needed (`"filesystem read file"`). SHOW the output of each sub-check. If reality doesn't match assertions, STOP and surface drift before reading further.
2. **STAIRCASE WITH MANDATORY HALT POINTS.** Plain-language writeup → Dan approves concept → code is written. Halts mandatory before `--commit`, before any Chroma write, at scope-option selection (A/B/C/D), at design points warranting tech-lead architecture review (M-options).
3. **AUTHORITY LINE.** Tactical → Claude. Strategic → Dan. Test: "can this be undone cheaply?" Yes → Claude. No → Dan. Surface tech-lead recommendations with rationale on scope decisions.
4. **ANTI-GOALS THIS SESSION:**
   - NO new file-type handlers until #35 (CONTENT_SOURCES.md) lands — UNLESS Dan explicitly relaxes this for a specific reason
   - NO modifying v2 except via M3-style extract-and-redirect with byte-identical dry-run regression
   - NO Railway pushes
   - NO git operations by Claude
   - NO reading or quoting `.env` contents
   - NO referencing Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park (scrub mechanism enforces; do not bypass)
   - NO inline heredocs for Python > ~10 lines
5. **COST GATES.** $1.00 interactive, $25.00 hard refuse. State projected spend up front. Track actual spend per step.
6. **CONTEXT BUDGET DISCIPLINE.** One-line context report at every halt: `[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]`. Surface warning at 30% remaining; at 20% recommend wrapping the current item and writing s24 prompt.

**Pace from sessions 21–22:** Larger steps with strategic-only halts. Doc updates batched at session close. (Session 22 hit the 30% threshold and wrapped cleanly — both behaviors are working.)

---

## Step 0 — Tool and reality check (mandatory)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `start_search` + `Filesystem:read_text_file`. If partial DC toolset visible, call `tool_search`. Same for Filesystem.
2. **Smoke test.** Start `python3 -i`, send `print("session 23 ok"); print(2+2)`. Expect `session 23 ok` / `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 22 commit** landing #31 closure (`scripts/test_admin_save_endpoint_s16.py` rewrite to snapshot/restore pattern) + doc updates (HANDOVER session 22 entry, BACKLOG #31 marked RESOLVED, NEXT_SESSION_PROMPT_S23.md created).
   - Below session 22: session 21 (`95b5831`), session 20 (`fdf0f78`), session 19 (`2ad362b`), etc.
   - **Working tree must be clean.**

### 0.3 — Data plane reality (UNCHANGED from s22 — no Chroma writes in s22)

4. **Reality-vs-prompt check.**

   - **Chroma baseline.** `rf_reference_library` should be **605** (unchanged from s17/s21 close).
     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** Should return **8 chunk IDs**: 7 PDF + 1 v2_google_doc. All 8 have `extraction_method`, `library_name`, `content_hash`; 7/8 have `source_file_md5` (Google Doc empty by Drive-API design).
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

   - **Sugar Swaps chunk strip-ON in production.**
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

   - **Vertex AI auth.** **Use `max_output_tokens=50`, NOT 5** (s22 lesson — gemini-2.5-flash burns reasoning tokens before emitting any text; 5 tokens gives `finish_reason: MAX_TOKENS` with empty content even when auth is fine):
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
     ./venv/bin/python3 -c "
     import vertexai
     from vertexai.generative_models import GenerativeModel
     vertexai.init(project='rf-rag-ingester-493016', location='us-central1')
     m = GenerativeModel('gemini-2.5-flash')
     r = m.generate_content('say ok', generation_config={'max_output_tokens': 50, 'temperature': 0})
     print('text:', repr(r.text.strip().lower()[:20]))
     " 2>&1 | grep -v -i 'warning\|deprecat'
     ```
     Expect `text: 'ok'`.

   - **OpenAI auth.** Source `.env` in subshell, minimal `embeddings.create("test")` returning 3072 dims.

   - **Test suite — all 13 scripts must be green** (no new tests added s22; #31 fix kept the script at 16/16 passing checks):
     ```bash
     ./venv/bin/python scripts/test_scrub_s13.py                       # 19/19
     ./venv/bin/python scripts/test_scrub_wiring_s13.py                # PASS
     ./venv/bin/python scripts/test_types_module.py                    # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py             # PASS
     ./venv/bin/python scripts/test_format_context_s16.py              # 23/23
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py         # 16/16  (NOW snapshot/restore — NO LONGER clobbers selection_state, #31 fixed)
     ./venv/bin/python scripts/test_google_doc_handler_synthetic.py    # 9/9
     GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_docx_handler_synthetic.py          # 12/12
     ./venv/bin/python scripts/test_v3_metadata_writer_s19.py          # 4/4
     ./venv/bin/python scripts/test_dedup_synthetic_s19.py             # 15/15
     ./venv/bin/python scripts/test_canva_strip_synthetic_s19.py       # 15/15
     ./venv/bin/python scripts/test_stage1_dedup_wiring_s20.py         # 4/4
     ```

   - **v3 dry-run regression.**
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected (assuming selection_state still in s16 shape OR whatever shape Dan has — the test no longer overrides it): if s16 shape, 3 files / 9 chunks / by_handler `{pdf: 1, v2_google_doc: 2}` / vision_cache_hit / est_tokens ~7,603 / $0.0010 / `stage1_dedup_skips: []`. If Dan has changed selection_state since s22, the numbers will reflect that — flag the difference, don't assume drift.


### 0.4 — Admin UI

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If a Python process is listening, fine. If not, start one: `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s23_admin_ui.log 2>&1 & disown`.
6. **Cache header.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store` (and a 302 to /login is normal — auth gate).
7. **Selection state on disk.** `cat data/selection_state.json`. **Whatever Dan last set is what should be there** — the s22 fix means this file is no longer auto-restored to s16 shape after running tests. If shape looks unexpected, ASK Dan, don't assume.

### 0.5 — Final summary

8. **Print:**
   ```
   ✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc),
     all 4 s19 metadata fields populated (8/8 except source_file_md5 7/8 by design),
     Sugar Swaps strip-ON in production (3737 chars, no canva.com),
     OCR cache: 34, all 13 test scripts green, admin UI on PID <pid>,
     v3 dry-run shows <files>/<chunks>/<est_tokens>/$<spend>/stage-1 skips: 0
   ```

If anything fails, STOP and surface to Dan.

---

## Step 1 — Read context

After Step 0 passes, read:

1. **`docs/HANDOVER.md` — session 22 entry** (~100 lines at the bottom). Tells you what shipped (#31 closed), the 5 lessons, and the rationale for skipping #21.
2. **`docs/HANDOVER.md` — session 21 entry** (~130 lines above session 22). Re-read the 5 lessons there too — they remain authoritative for chunk-ID determinism, selection_state vs existing-chunks comparison, stage-1 self-match semantics, and empirical A/B re-verification.
3. **`docs/BACKLOG.md`** — the open items called out in Step 2 below.
4. **Optional but recommended:** `docs/STATE_OF_PLAY.md` — last amended at s18 — HANDOVER s19/20/21/22 entries supersede, but STATE_OF_PLAY contains the "build-the-net" framing and the s9 honest post-mortem that explain *why* the current discipline exists. Re-read if you're feeling tempted toward architectural rabbit holes.

**Other governing docs in the repo (read on demand if your chosen scope touches them):**
- ADR_001 through ADR_006 (in repo root): architecture decision records covering Drive ingestion scope, continuous diff & registry, Canva dedup, folder selection UI, static libraries, chunk reference contract.
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/REPO_MAP.md`, `docs/COACHING_CHUNK_CURRENT_SCHEMA.md`, `docs/plans/` — read if scope crosses into the area each covers.
- `INCIDENTS.md` (repo root) — recorded credential exposure incidents (informational, no action items).

---

## Step 2 — Scope decision (Dan picks)

**Dan's standing build-discipline frame (s22):** "Unless it's part of the build, it shouldn't be now. Refer to the governing pilot docs as to where we are and what we need to do." Content scope (#35, #36) is explicitly OUT until the build progresses further. UI polish (#21) was deferred in s22 as drift relative to current strategic priorities. Each scope option below should be evaluated against that frame.

### Option A — Retrofit bundle (#6b + #18 + #17 + #20)

The single biggest leverage item left. Single coordinated session that touches all chunk populations once:
- **#6b** scrub retrofit on `rf_coaching_transcripts` (9,224 chunks) + first 584 `rf_reference_library` chunks (pre-scrub A4M). Real liability — every coaching `/chat` query currently returns chunks containing former-collaborator references (verified s15). Pure text patch via `collection.update(ids=..., documents=...)`. No re-embedding. Backup required.
- **#18** `format_context()` migration to canonical display fields (`source_label`, `locator`, `link`, `summary`). Eliminates A4M-specific branches in retrieval code.
- **#17** `display_subheading` cosmetic normalization across all populations (metadata-only update, no re-embed).
- **#20** inline citation prompting added to both persona YAML configs. A/B test on representative queries.

**Effort:** ~half-day, dedicated session. **Spend:** ~$0 (text patch) to ~$0.05 (A/B chat calls). **Risk:** medium — touches the largest collection. Mitigated by backup + read-only count first + chunk-by-chunk update with progress log. Halt before any write.

**Why this fits build-discipline:** safety-net work in line with s18's principle. The scrub retrofit closes a real user-facing liability (chunks with former-colleague names returned in retrieval). The other three are load-bearing for retrieval quality across all collections.

### Option B — Just #6b (coaching scrub retrofit alone)

Same as A but scoped to just the scrub retrofit. Lower risk, faster session, but leaves #17/#18/#20 as a separate later session.

**Effort:** ~2 hours. **Spend:** ~$0. **Risk:** low — text-only, well-understood pattern.

### Option C — Next v3 handler (plaintext / sheets / slides / images / av)

The s18 halt said handler work resumes once dedup + Canva + metadata writer ship. Those landed s19/20/21. Each new handler:
- Increases retrofit surface (every future #18-style migration touches more chunks)
- Doesn't unblock anything urgent — current handlers cover ~80% of useful Drive content
- Is increasingly hard to commit cleanly without #35 (CONTENT_SOURCES.md) — exactly the trap s18 warned about

**Tech-lead read:** likely premature. The s18 explicit advice was "next handler inherits dedup + Canva + clean metadata + clean Google Doc chunks" — true today — but ALSO inherits the absence of CONTENT_SOURCES.md, which gates commits. Dry-run-only handler work is fine; commits aren't.

### Option D — STATE_OF_PLAY.md amendment session

Compress HANDOVER s19/20/21/22 into a STATE_OF_PLAY amendment so the orientation surface stops drifting. Pure documentation work. Useful if a fresh-context session is imminent or if Dan wants to take a planning beat.

**Effort:** ~1 hour. **Spend:** $0. **Risk:** none.

### Tech-lead recommendation: **Option A (retrofit bundle)** if Dan has half-day focus and is comfortable with a Chroma write to the largest collection. Otherwise **Option B (just #6b)**.

Reasoning:
1. **A is the most strategic build item left that fits the discipline frame.** Closes a real liability + lands canonical retrieval contract + removes pipeline-specific branches in `format_context`. All four bundle items have been waiting since s15-s17.
2. **B is the safe slice of A** — pure text patch, no re-embed, smallest blast radius. If Dan wants to land #6b alone first and revisit #17/#18/#20 separately, that's a defensible smaller step.
3. **C is a deferred temptation.** It feels like progress but adds retrofit surface without closing anything load-bearing. Skip until at least #6b is shipped.
4. **D is a "rest day" choice** — useful if context budget across recent sessions has been tight or if a longer break is coming. Otherwise low-leverage.

---

## Step 3+ — Execute

Once Dan picks, scope tight plan **before** writing code:
1. Files touched
2. Test scripts written/updated
3. Data writes (Chroma, file edits) and halt points
4. Minimum viable closure
5. Spend estimate

Get approval, THEN execute.

---

## ALL FLIGHT RULES (carried forward, sessions 9 → 22)

These are the standing rules accumulated across sessions. None expire unless explicitly revoked. Read before any decision that could violate one.

### Process & authority

- **Halt before `--commit`.** Show dump-json before any Chroma write.
- **Halt before any direct Chroma write.** No exceptions.
- **No deletions** (files, chunks, collections) without approval AND backup.
- **Dan does git operations.** Claude never runs `git add`, `git commit`, `git push`, `git checkout`, `git reset`, `git rm`, etc.
- **Pipe commit stdout to file**, not `| tail` — preserves full record for forensics.
- **Surface M-options at design halts** when uncertainty warrants tech-lead review.
- **Tech-lead volunteers architecture review at design-halt points** (s15 lesson).

### Scope discipline

- **No Railway writes from sessions.** Railway is read-only. Sync is on-demand via tarball + cloudflared, run by Dan.
- **No touching legacy collections** without Dan's explicit OK. (`rf_coaching_transcripts` 9,224 chunks; pre-scrub 584 A4M chunks in `rf_reference_library`.)
- **v2 frozen** unless extract-and-redirect (M3 pattern, s17). The only blessed mechanism for v2 modifications is extract-into-shared-module preserving byte-identical v2 behavior, verified by dry-run regression.
- **v1 frozen.** No modifications.
- **No new file-type handlers until #35 (CONTENT_SOURCES.md) lands** — UNLESS Dan explicitly relaxes for a specific reason.
- **Don't ingest a content domain until its source-of-truth is documented** (s18). Once `docs/CONTENT_SOURCES.md` exists, every bulk ingest must map back to a designated canonical source.
- **Build the safety net before the surface area grows** (s18). Adding handlers is fast; cleaning up duplicates after the fact is slow and risks corrupting retrieval. Infrastructure first.

### Privacy & content

- **Credentials ephemeral** — never read `.env` content into chat. Never log, echo, or quote credential strings.
- **Never reference Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park** anywhere — agent responses, code comments, doc text, chat replies. Layer B scrub catches new content; legacy is not yet protected (BACKLOG #6b).

### Code & file discipline

- **Prefer write-script-to-file** over inline heredocs for Python > ~10 lines.
- **Pre-commit drift audit on any new handler** (s18) — side-by-side comparison of stored Chroma metadata for an existing chunk vs the projected metadata. Schema must match exactly except for type-specific fields.
- **The replicated-block test pattern** for wiring tests beats live Chroma audits when verifying dispatch-loop signatures (s20).

### Verification & debugging

- **Test in Chrome before Safari** for admin UI iterative work (s16 lesson).
- **Read the Flask access log first** when debugging UI cache/save issues (s16).
- **Verify BACKLOG closures end-to-end in the environment where they manifested** (s16, s28). For UI bugs → real browser click-through. For data bugs → query against the live collection.
- **Empirical A/B re-verification on a known-changed chunk is cheap and high-confidence** (s21). Worth doing whenever a Chroma write is supposed to land a previously-tested transformation. ~$0.0001 + 5 min.

### Stage-1 dedup & re-ingest semantics (s21)

- **Read selection_state against existing chunks before trusting prompt assertions** (s21). When a prompt asserts "X chunks across Y files via Z folder," run a `getall` on `source_pipeline=drive_loader_v3` chunks and compare file_ids against the selection_state cascade BEFORE any commit. Halt 1 of s21 caught a 2-file accidental-ingest this way.
- **Chunk-ID determinism is the strongest no-orphan guarantee** (s21). `build_chunk_id` formula at `_drive_common.py:234` is `drive:<drive_slug>:<file_id>:<chunk_index:04d>` — a 1-line read; verify in pre-flight rather than relying on post-write checks.
- **Stage-1 dedup not firing on a re-ingest is correct, not a bug** (s21). Stage-1 only fires on cross-file_id md5 matches. Same file_id self-matches and falls through to extraction.

### Test infrastructure (s22)

- **Snapshot/restore is the safer test pattern than hardcoded restore** (s22). Even when the hardcoded shape "always" matches expected state, it's a foot-gun for any session that iterates on the underlying file. Use byte-for-byte snapshot in `setUp`-equivalent + `try/finally` restore.
- **The probe verification pattern is cheap and conclusive for restore-correctness fixes** (s22). Backup → write distinctive sentinel → run test → diff bytes → restore. ~5 min, no mock framework needed.
- **Step 0 cheat-sheet smoke tests need enough token headroom for reasoning-model overhead** (s22). gemini-2.5-flash burned all 5 tokens on `thoughts_token_count` before emitting any text. `max_output_tokens=50` is a cheap safe default for one-token auth pings.

### Re-scope discipline (s22)

- **Re-scope honestly when context budget is the binding constraint** (s22). A bundled "do D + B if context permits" should be reread against build-discipline before executing the second item — what looked safe-low-risk at scope-decision time may be drift relative to current strategic priorities once the first item lands.

---

## Budget for session 23

- **$1.00 interactive gate.**
- **$25.00 hard refuse.**
- **Session 22 spent ~$0.001.** Session 23 expected: $0 for B/D, ~$0.05 for A (if A/B chat calls in #20 portion), ~$0.50 max if a re-embed slips into #17/#18 (it shouldn't — text/metadata only).

## Files NOT to touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via audit module
- `ingester/loaders/drive_loader.py` (v1) — frozen
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except via M3 extract-and-redirect
- `ingester/loaders/types/*` — out of scope unless a specific item directs
- `ingester/loaders/drive_loader_v3.py` — modified s20 (M-37-α), s21 used as-is, s22 untouched. Don't touch unless a BACKLOG item directs.

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

# Vertex AI auth (NOTE: max_output_tokens=50, NOT 5 — s22 lesson)
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
./venv/bin/python3 -c "
import vertexai
from vertexai.generative_models import GenerativeModel
vertexai.init(project='rf-rag-ingester-493016', location='us-central1')
m = GenerativeModel('gemini-2.5-flash')
r = m.generate_content('say ok', generation_config={'max_output_tokens': 50, 'temperature': 0})
print('text:', repr(r.text.strip().lower()[:20]))
" 2>&1 | grep -v -i 'warning\|deprecat'

# Test suite (expect all 13 green)
set -a && . ./.env && set +a
for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py scripts/test_v3_metadata_writer_s19.py scripts/test_dedup_synthetic_s19.py scripts/test_canva_strip_synthetic_s19.py scripts/test_stage1_dedup_wiring_s20.py; do
  echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -2
done

# v3 dry-run (numbers depend on current selection_state — no longer auto-restored)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
```

If all passes, print the Step 0 summary line and proceed to Step 1.

---

## End of session 23 prompt

Session 22 closed BACKLOG #31 (test_admin_save_endpoint_s16.py snapshot/restore). Zero Chroma writes. The selection_state foot-gun is gone — Step 0 sub-check 0.4.7 will reflect whatever Dan actually has set, not a hardcoded restore. All other s21-close state preserved exactly (605 chunks, 8 v3 chunks all metadata-complete, Sugar Swaps strip-ON, 13 tests green). Good luck.
