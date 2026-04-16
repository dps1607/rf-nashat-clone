# NEXT SESSION PROMPT — session 24

> **⚠ READ THIS FIRST**
>
> Step 0 has paid for itself every session 9 onward. s21 caught a 2-file accidental-ingest. s22 caught a too-tight Vertex smoke test. s23 caught nothing because nothing had drifted (and that's fine — Step 0 is a gate, not a productivity metric). **Session 24 must run Step 0 in full.**

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19-23. Six rules unchanged plus two s23 additions (verification protocol + Chrome-first UI testing).

1. **STEP 0 IS A GATE, NOT A VIBES-CHECK.** Run every numbered sub-check below in order, against actual disk state. Tool enumeration first — if Desktop Commander shows only a partial toolset, call `tool_search` with `"start_process write_file edit_block"`. Same for Filesystem (`"filesystem read file"`). SHOW the output of each sub-check. If reality doesn't match assertions, STOP and surface drift before reading further.

2. **STAIRCASE WITH MANDATORY HALT POINTS.** Plain-language writeup → Dan approves concept → code is written. Halts mandatory before `--commit`, before any Chroma write, at scope-option selection (A/B/C/D/etc.), at design points warranting tech-lead architecture review (M-options).

3. **AUTHORITY LINE.** Tactical → Claude. Strategic → Dan. Test: "can this be undone cheaply?" Yes → Claude. No → Dan. Surface tech-lead recommendations with rationale on scope decisions.

4. **ANTI-GOALS THIS SESSION:**
   - NO new file-type handlers until #35 (CONTENT_SOURCES.md) lands — UNLESS Dan explicitly relaxes
   - NO modifying v2 except via M3-style extract-and-redirect with byte-identical dry-run regression
   - NO Railway pushes
   - NO git operations by Claude
   - NO reading or quoting `.env` contents
   - NO referencing Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park (scrub mechanism enforces; do not bypass)
   - NO inline heredocs for Python > ~10 lines
   - NO re-proposing #6b coaching scrub retrofit (Dan declined s23 — see BACKLOG #6b for trigger conditions to reopen)

5. **COST GATES.** $1.00 interactive, $25.00 hard refuse. State projected spend up front. Track actual spend per step.

6. **CONTEXT BUDGET DISCIPLINE.** One-line context report at every halt: `[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]`. Surface warning at 30% remaining; at 20% recommend wrapping the current item and writing s25 prompt.

**Pace from sessions 21–23:** Larger steps with strategic-only halts. Doc updates batched at session close. Zero-write sessions are valid build progress when they retire optionality (s22 fixed a foot-gun, s23 closed a strategic question + incorporated process improvements).


---

## Step 0 — Tool and reality check (mandatory)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `Filesystem:read_text_file`. If partial DC toolset visible, call `tool_search`. Same for Filesystem.
2. **Smoke test.** Start `python3 -i`, send `print("session 24 ok"); print(2+2)`. Expect `session 24 ok` / `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 23 commit** landing process-improvement docs (BACKLOG annotations for #28, #26a, #10, #6b + HANDOVER s23 entry + NEXT_SESSION_PROMPT_S24.md created).
   - Below s23: s22 (`624d6de`), s21 (`95b5831`), s20 (`fdf0f78`), s19 (`2ad362b`), etc.
   - **Working tree must be clean.**

### 0.3 — Data plane reality (UNCHANGED from s21 close — s22 and s23 were both zero-write)

4. **Reality-vs-prompt check.**

   - **Chroma baseline.** `rf_reference_library` should be **605** (unchanged since s21).
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

   - **Vertex AI auth.** Use `max_output_tokens=50` (s22 lesson):
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

   - **Test suite — all 13 scripts must be green:**
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
     ./venv/bin/python scripts/test_dedup_synthetic_s19.py             # 15/15
     ./venv/bin/python scripts/test_canva_strip_synthetic_s19.py       # 15/15
     ./venv/bin/python scripts/test_stage1_dedup_wiring_s20.py         # 4/4
     ```

   - **v3 dry-run regression.**
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected (assuming s16-shape selection_state still present): 9 chunks / by_handler `{pdf: 1, v2_google_doc: 2}` / vision_cache_hit / est_tokens ~7,603 / $0.0010 / `stage1_dedup_skips: []`. If Dan has changed selection_state, flag the difference rather than assuming drift.

### 0.4 — Admin UI

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If no Python process listening, start one: `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s24_admin_ui.log 2>&1 & disown`.
6. **Cache header.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store` (and a 302 to /login is normal).
7. **Selection state on disk.** `cat data/selection_state.json`. Whatever Dan last set is what should be there. If unexpected, ASK Dan, don't assume.

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

1. **`docs/HANDOVER.md` — session 23 entry** (~100 lines at bottom). Strategic re-baseline rationale, why #6b is off the table, why #28 + #26(a) live in this prompt's flight rules now.
2. **`docs/HANDOVER.md` — session 22 entry** (~120 lines above s23). Context for the snapshot/restore fix and the selection_state foot-gun being gone.
3. **`docs/HANDOVER.md` — session 21 entry** (~130 lines above s22). The 5 lessons there remain authoritative for chunk-ID determinism, selection_state vs existing-chunks comparison, stage-1 self-match semantics, empirical A/B re-verification.
4. **`docs/BACKLOG.md`** — focus on items called out in Step 2 below.
5. **Optional but recommended:** `docs/STATE_OF_PLAY.md` — last amended at s18; HANDOVER s19-23 entries supersede, but STATE_OF_PLAY contains the "build-the-net" framing and the s9 honest post-mortem that explain why the current discipline exists.

**Other governing docs in the repo (read on demand if your chosen scope touches them):**
- ADR_001 through ADR_006 (in repo root): architecture decision records covering Drive ingestion scope, continuous diff & registry, Canva dedup, folder selection UI, static libraries, chunk reference contract.
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/REPO_MAP.md`, `docs/COACHING_CHUNK_CURRENT_SCHEMA.md`, `docs/plans/` — read if scope crosses each area.
- `INCIDENTS.md` (repo root) — recorded credential exposure incidents (informational, no action items).

---

## Step 2 — Scope decision (Dan picks)

**Dan's standing build-discipline frame (s22, s23):** "Unless it's part of the build, it shouldn't be now. Refer to the governing pilot docs as to where we are and what we need to do." Content scope (#35, #36) is HIGH priority but needs Dan's input to land. UI polish (#21) was deferred in s22 as drift relative to current strategic priorities. Each scope option below should be evaluated against that frame.

### Option A — Retrieval-quality bundle (#18 + #20 + #17)

**The next coherent block of build work.** Three coupled items shipped together in one focused session:

- **#18 `format_context()` migration to canonical display fields.** Define a canonical `chunk_to_display(chunk) -> dict` helper with fields like `source_label`, `locator`, `link`, `summary`. Each chunk population's writer populates these at ingest time. `format_context()` reads only the canonical fields, no special branches. Eliminates A4M-specific code paths in retrieval.
- **#20 inline citation prompting** added to both persona YAML configs. A/B test on representative queries. Sales agent voice vs coaching agent clinical accuracy may want different cite densities.
- **#17 display_subheading cosmetic normalization** — metadata-only update across populations. Bundled with #18 because the cosmetic fix is invisible to users until #18's renderer lands.

**Effort:** half-day, dedicated session. **Spend:** ~$0.05 max (A/B chat calls in #20). **Risk:** Low-Medium — no Chroma writes against the 9,224-chunk coaching collection (that was the #6b risk, now declined). Only metadata-only updates on the 605 reference library + persona YAML edits + chat-call A/B testing. Halt before any write.

**Why this fits build-discipline:** retrieval-quality work is load-bearing for both agents. The `chunk_to_display` helper from #18 is the canonical contract that future handlers will populate; landing it now means future handler work doesn't need to re-litigate display-field naming.

### Option B — Just #18 alone (canonical display contract)

Lower-risk slice of A. Lands `chunk_to_display(chunk)` helper + migrates `format_context()` to use it. Defers #17 cosmetic normalization and #20 citation prompting to a follow-up. Defensible if context budget is tight or if you want to validate the canonical contract design before committing to A/B work.

**Effort:** ~2-3 hours. **Spend:** ~$0. **Risk:** Low.

### Option C — Write `docs/CONTENT_SOURCES.md` (#35)

**The other strategic gate.** HIGH priority per BACKLOG. Blocks bulk content ingestion of any text-bearing file type. Format roughly: content domain → canonical Drive folder(s) → file forms to ingest vs skip. Once #35 lands, #36 (April-May 2023 Blogs commit) and the next v3 handler are unblocked.

**Effort:** ~1 hour conversation with Dan to walk inventory and decide canonical sources, then ~30 min documentation. **Spend:** $0. **Risk:** none. **Requires:** Dan's active input — this is a decision-making session, not an execution session.

### Option D — Folder-selection UI redesign (#21)

Biggest UI friction point. Removes pending-panel/tree redundancy, adds sticky summary bar, removes vestigial library dropdown, adds visual differentiation between drives/folders/files. Pure UI work. Folds in #26(b) (`selectionState` retrofit) for free since the redesign removes the pending panel.

**Effort:** dedicated 60-90 min session. **Spend:** $0. **Risk:** Low (UI only, no data writes). Test in Chrome first per s23 process rule.

### Option E — STATE_OF_PLAY.md amendment session

Compress HANDOVER s19-23 into a STATE_OF_PLAY amendment. Pure documentation work. Useful if a fresh-context session is imminent or if Dan wants a planning beat.

**Effort:** ~1 hour. **Spend:** $0. **Risk:** none.

### Tech-lead recommendation

**Option A (retrieval-quality bundle)** if Dan has half-day focus. Three coupled items, naturally co-occurring, low risk profile (no large-collection writes), advances the canonical retrieval contract that all future handlers will inherit.

**Option C (CONTENT_SOURCES.md)** if Dan has time for a structured conversation about content canonicalization. Higher strategic leverage than A — unblocks multiple downstream items — but requires Dan's active decision-making rather than Claude's execution.

**Either A or C is a strong session.** B is the safe slice of A. D is good UI work but lower strategic leverage right now. E is a "rest day" choice.

Not recommended without specific reason from Dan: any next v3 handler (gated by #35), #10 requirements.txt (trigger-driven only per s23 disposition).

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

## ALL FLIGHT RULES (carried forward, sessions 9 → 23)

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
- **#6b coaching scrub retrofit DECLINED s23.** Do not re-propose as a strategic next step. Reopen only if a real downstream surface change makes it newly necessary (future model surfacing raw chunk text directly to users, logging change exposing them).
- **v2 frozen** unless extract-and-redirect (M3 pattern, s17). The only blessed mechanism for v2 modifications is extract-into-shared-module preserving byte-identical v2 behavior, verified by dry-run regression.
- **v1 frozen.** No modifications.
- **No new file-type handlers until #35 (CONTENT_SOURCES.md) lands** — UNLESS Dan explicitly relaxes for a specific reason.
- **Don't ingest a content domain until its source-of-truth is documented** (s18). Once `docs/CONTENT_SOURCES.md` exists, every bulk ingest must map back to a designated canonical source.
- **Build the safety net before the surface area grows** (s18). Adding handlers is fast; cleaning up duplicates after the fact is slow and risks corrupting retrieval. Infrastructure first.
- **Re-baseline scope when a strategic input changes mid-session** (s23). When Dan declines or modifies a key item in a proposed bundle, re-derive the recommendation from remaining items rather than mechanically executing "the bundle minus X."
- **Coupled items shouldn't be split casually** (s23). When a BACKLOG entry says "bundle with #N," doing the item standalone is often busywork until the coupled item lands. Read the bundling rationale before splitting.
- **Trigger-driven beats time-driven for low-urgency infrastructure debt** (s23). Defer infrastructure cleanup until a real trigger surfaces; don't bundle pre-emptively with feature work.

### Privacy & content

- **Credentials ephemeral** — never read `.env` content into chat. Never log, echo, or quote credential strings.
- **Never reference Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park** anywhere — agent responses, code comments, doc text, chat replies. Layer B scrub catches new content; legacy not retrofitted (#6b declined s23).

### Code & file discipline

- **Prefer write-script-to-file** over inline heredocs for Python > ~10 lines.
- **Pre-commit drift audit on any new handler** (s18) — side-by-side comparison of stored Chroma metadata for an existing chunk vs the projected metadata. Schema must match exactly except for type-specific fields.
- **The replicated-block test pattern** for wiring tests beats live Chroma audits when verifying dispatch-loop signatures (s20).

### Verification & debugging

- **Test admin UI in Chrome before Safari** (s16, incorporated s23 from BACKLOG #26a). Safari has aggressive caching, console quirks (paste-doesn't-execute, filtered errors), and CSS oddities that make it unreliable for iterative development. The s16 toast/save debugging loop took 4 rounds in Safari that would have taken 1 round in Chrome.
- **Verify BACKLOG closures end-to-end in the environment where they manifested** (s16, incorporated s23 from BACKLOG #28). When closing a BACKLOG item, the closure note must include a verification step in the environment where the bug was originally reported. For UI bugs → real browser click-through, not just a CSS file edit. For data bugs → query against the live collection, not just a unit test on synthetic data.
- **Read the Flask access log first** when debugging UI cache/save issues (s16).
- **Empirical A/B re-verification on a known-changed chunk is cheap and high-confidence** (s21). Worth doing whenever a Chroma write is supposed to land a previously-tested transformation. ~$0.0001 + 5 min.

### Stage-1 dedup & re-ingest semantics (s21)

- **Read selection_state against existing chunks before trusting prompt assertions** (s21). When a prompt asserts "X chunks across Y files via Z folder," run a `getall` on `source_pipeline=drive_loader_v3` chunks and compare file_ids against the selection_state cascade BEFORE any commit.
- **Chunk-ID determinism is the strongest no-orphan guarantee** (s21). `build_chunk_id` formula at `_drive_common.py:234` is `drive:<drive_slug>:<file_id>:<chunk_index:04d>` — a 1-line read; verify in pre-flight rather than relying on post-write checks.
- **Stage-1 dedup not firing on a re-ingest is correct, not a bug** (s21). Stage-1 only fires on cross-file_id md5 matches. Same file_id self-matches and falls through to extraction.

### Test infrastructure (s22)

- **Snapshot/restore is the safer test pattern than hardcoded restore** (s22). Even when the hardcoded shape "always" matches expected state, it's a foot-gun for any session that iterates on the underlying file. Use byte-for-byte snapshot in `setUp`-equivalent + `try/finally` restore.
- **The probe verification pattern is cheap and conclusive for restore-correctness fixes** (s22). Backup → write distinctive sentinel → run test → diff bytes → restore. ~5 min, no mock framework needed.
- **Step 0 cheat-sheet smoke tests need enough token headroom for reasoning-model overhead** (s22). gemini-2.5-flash burned all 5 tokens on `thoughts_token_count` before emitting any text. `max_output_tokens=50` is a cheap safe default for one-token auth pings.

### Re-scope discipline (s22, s23)

- **Re-scope honestly when context budget is the binding constraint** (s22). A bundled "do D + B if context permits" should be reread against build-discipline before executing the second item.
- **Zero-write sessions are valid build progress when they retire optionality** (s23). s22 (test fix) and s23 (strategic re-baseline + process docs) both consumed real budget by removing future ambiguity. Build discipline doesn't require a Chroma write to count as progress.

---

## Budget for session 24

- **$1.00 interactive gate.**
- **$25.00 hard refuse.**
- **Sessions 22 + 23 each spent ~$0.001.** Session 24 expected: $0 for B/C/D/E, ~$0.05 for A (A/B chat calls in #20 portion).

## Files NOT to touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via audit module
- `ingester/loaders/drive_loader.py` (v1) — frozen
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except via M3 extract-and-redirect
- `ingester/loaders/types/*` — out of scope unless a specific item directs
- `ingester/loaders/drive_loader_v3.py` — modified s20 (M-37-α), s21-23 untouched. Don't touch unless a BACKLOG item directs.


---

## Step 0 cheat sheet

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Chroma baseline (expect 605 — unchanged since s21)
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

# Vertex AI auth (max_output_tokens=50, NOT 5 — s22 lesson)
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

# v3 dry-run (numbers depend on current selection_state)
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
```

If all passes, print the Step 0 summary line and proceed to Step 1.

---

## End of session 24 prompt

Session 23 closed nothing concrete (zero code changes, zero Chroma writes) but retired strategic optionality: #6b declined, #28 + #26(a) incorporated into flight rules, #10 re-prioritized as trigger-driven. All s21-close data state preserved exactly (605 chunks, 8 v3 chunks all metadata-complete, Sugar Swaps strip-ON, 13 tests green). Next session has clean tee-up for retrieval-quality work (#18+#20+#17 bundle, Option A) or strategic content-canonicalization conversation (#35, Option C). Good luck.
