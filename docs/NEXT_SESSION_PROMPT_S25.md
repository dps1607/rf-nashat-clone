# NEXT SESSION PROMPT — session 25

> **⚠ READ THIS FIRST**
>
> Step 0 has paid for itself every session 9 onward. s24 shipped canonical rendering + YAML-configurable citation guidance (#18 + #20 code). s24 deferred the #20 A/B validation for this session. **Session 25 must run Step 0 in full.**

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19-24. All six rules unchanged.

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

6. **CONTEXT BUDGET DISCIPLINE.** One-line context report at every halt: `[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]`. Surface warning at 30% remaining; at 20% recommend wrapping the current item and writing s26 prompt.

**Pace from sessions 21–24:** Larger steps with strategic-only halts. Doc updates batched at session close. Zero-write sessions are valid build progress when they retire optionality.


---

## Step 0 — Tool and reality check (mandatory)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `Filesystem:read_text_file`. If partial DC toolset visible, call `tool_search`. Same for Filesystem.
2. **Smoke test.** Start `python3 -i`, send `print("session 25 ok"); print(2+2)`. Expect `session 25 ok` / `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 24 commit** landing canonical rendering (`rag_server/display.py`) + schema updates + YAML render/citation blocks + new 79/79 test + HANDOVER/BACKLOG s24 entries + NEXT_SESSION_PROMPT_S25.md.
   - Below s24: s23 (`acbc174`), s22 (`624d6de`), s21 (`95b5831`), etc.
   - **Working tree must be clean.**

### 0.3 — Data plane reality (UNCHANGED from s21 close — s22/23/24 were all zero-write)

4. **Reality-vs-prompt check.**

   - **Chroma baseline.** `rf_reference_library` should be **605** (unchanged since s21).
     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable.** Should return **8 chunk IDs**: 7 PDF + 1 v2_google_doc. All 4 s19 metadata fields populated (`source_file_md5` 7/8 by design).
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

   - **Vertex AI auth.** `max_output_tokens=50`:
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

   - **Test suite — all 14 scripts must be green (s24 added test_format_context_s24.py):**
     ```bash
     ./venv/bin/python scripts/test_scrub_s13.py                       # 19/19
     ./venv/bin/python scripts/test_scrub_wiring_s13.py                # PASS
     ./venv/bin/python scripts/test_types_module.py                    # 12/12
     ./venv/bin/python scripts/test_chunk_with_locators.py             # PASS
     ./venv/bin/python scripts/test_format_context_s16.py              # 22/22 (was 23/23; one assertion updated s24 for canonicalization)
     ./venv/bin/python scripts/test_admin_save_endpoint_s16.py         # 16/16
     ./venv/bin/python scripts/test_google_doc_handler_synthetic.py    # 9/9
     GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json ./venv/bin/python scripts/test_scrub_v3_handlers.py  # 2/2
     ./venv/bin/python scripts/test_docx_handler_synthetic.py          # 12/12
     ./venv/bin/python scripts/test_v3_metadata_writer_s19.py          # 4/4
     ./venv/bin/python scripts/test_dedup_synthetic_s19.py             # 15/15
     ./venv/bin/python scripts/test_canva_strip_synthetic_s19.py       # 15/15
     ./venv/bin/python scripts/test_stage1_dedup_wiring_s20.py         # 4/4
     ./venv/bin/python scripts/test_format_context_s24.py              # 79/79  NEW s24
     ```

   - **v3 dry-run regression.**
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected: 9 chunks / by_handler `{pdf: 1, v2_google_doc: 2}` / vision_cache_hit / est_tokens ~7,603 / $0.0010 / `stage1_dedup_skips: []`.

   - **Canonical renderer smoke (NEW s24 sub-check).** Verify display.py imports + both YAMLs load with render + citation_instructions:
     ```bash
     ./venv/bin/python3 -c "
     from rag_server.display import chunk_to_display, format_context
     from shared.config_loader import ConfigLoader
     from pathlib import Path
     for name in ['nashat_sales', 'nashat_coaching']:
         cfg = ConfigLoader(Path(f'config/{name}.yaml')).config
         print(f'{name}: citation_instructions={len(cfg.behavior.citation_instructions)} chars, render collections={list(cfg.knowledge.render.keys())}')
     "
     ```
     Expected:
     ```
     nashat_sales: citation_instructions=468 chars, render collections=['rf_reference_library']
     nashat_coaching: citation_instructions=574 chars, render collections=['rf_coaching_transcripts', 'rf_reference_library']
     ```

### 0.4 — Admin UI

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If no Python process listening, start one: `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s25_admin_ui.log 2>&1 & disown`.
6. **Cache header.** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'`. Expect `Cache-Control: no-store`.
7. **Selection state on disk.** `cat data/selection_state.json`. Whatever Dan last set.

### 0.5 — Final summary

8. **Print:**
   ```
   ✓ Step 0 PASS — repo at <hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc),
     all 4 s19 metadata fields populated (8/8 except source_file_md5 7/8 by design),
     Sugar Swaps strip-ON in production, OCR cache: 34,
     all 14 test scripts green, admin UI on PID <pid>,
     canonical renderer + both YAMLs validate, v3 dry-run byte-identical to s24 baseline
   ```

If anything fails, STOP and surface to Dan.


---

## Step 1 — Read context

After Step 0 passes, read:

1. **`docs/HANDOVER.md` — session 24 entry** (~200 lines at bottom). Design principles of the canonical renderer + 2-layer separation + protected-fields contract + #20 A/B deferral rationale.
2. **`docs/HANDOVER.md` — session 23 entry** (~100 lines above). Strategic re-baseline + #6b decline + process-improvement incorporations.
3. **`docs/BACKLOG.md`** — focus on #18 closure notes (s24), #20 deferred-A/B scope, #17 reopen trigger, and whatever the chosen scope touches.
4. **Optional:** `docs/HANDOVER.md` s21-22 entries if scope touches chunk-ID determinism (s21) or test infrastructure (s22).

Governing docs (read on demand): ADR_001-006, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/REPO_MAP.md`, `docs/plans/`, `INCIDENTS.md`.

---

## Step 2 — Scope decision (Dan picks)

### Option A — #20 A/B validation (the deferred s24 work)

**Scope:** Validate `citation_instructions` effect on both agents. Representative queries × before/after prompts × sales + coaching agents. Verify:
- Sales voice stays warm, doesn't become stilted or clinical
- Coaching responses gain explicit source references without losing warmth
- Neither agent hallucinates page numbers, links, or source titles when context lacks them
- Graceful degradation when only source name is in context (no invented pages)

**Method:** Two queries per agent (one that touches Egg Health Guide w/ locator+link, one that touches a chunk without locator or link). Run `/chat` with `citation_instructions=""` (baseline) and with current YAML (treatment). Compare response text.

**Effort:** ~45 min. **Spend:** ~$0.05 (8 Sonnet calls × ~$0.006). **Risk:** none (read-only /chat calls).

**Deliverable:** `scripts/test_citation_instructions_ab_live_s25.py` + a one-pager in HANDOVER with the before/after and a verdict (ship as-is / tune YAML text / any observations for future tuning).

### Option B — #35 CONTENT_SOURCES.md (HIGH priority)

**Scope:** Document canonical source per content domain (blogs, lead magnets, coaching, email sequences, educational reference). Blocks bulk ingestion of any text-bearing file type. **Requires Dan's active input** — decision-making session, not execution.

**Effort:** ~1hr conversation + ~30min doc. **Spend:** $0. **Risk:** none.

### Option C — #21 folder-selection UI redesign

**Scope:** Remove pending-panel/tree redundancy, sticky summary bar, remove vestigial library dropdown, visual differentiation drives/folders/files. Folds in #26(b) `selectionState` retrofit.

**Effort:** 60-90 min. **Spend:** $0. **Risk:** Low (UI only). Test Chrome first.

### Option D — STATE_OF_PLAY amendment

Compress HANDOVER s19-24 into STATE_OF_PLAY amendment.

**Effort:** ~1hr. **Spend:** $0. **Risk:** none.

### Tech-lead recommendation

**Option A.** The natural closure of the s24 work. Low effort, low cost, validates that the citation_instructions are actually doing what the YAML text expects. Leaving A/B un-done leaves a "did this actually change response quality?" question open, which will become harder to answer the further we get from the change. Do it while the context is fresh.

**Option B** is the higher strategic leverage pick if Dan has ~1.5hr of focused decision-making energy and wants to unblock bulk ingestion. Good alternative to A.

C is fine work but lower current leverage. D is a rest-day choice.


---

## Step 3+ — Execute

Once Dan picks, scope tight plan **before** writing code. Files touched, tests added, data writes + halts, minimum viable closure, spend estimate. Get approval, THEN execute.


---

## ALL FLIGHT RULES (carried forward, sessions 9 → 24)

All rules from s24's prompt carry forward unchanged. Two s24 additions:

### Rendering & protection (s24)

- **Two-layer separation between retrieval and rendering is load-bearing.** Retrieval returns full chunks (metadata preserved for downstream systems — lab correlation, client tracking, analytics). Rendering filters what the LLM sees via per-collection YAML `render` blocks. Do not conflate the two into one config knob — it creates either a data leak or a downstream-systems blocker.

- **Code-enforced protection beats YAML-only protection for guardrail-critical fields.** `client_rfids`, `client_names`, `call_fksp_id`, `call_file` are never surfaced to the LLM regardless of any YAML config. Enforced in `rag_server/display.py` resolver functions. The protection is not exposed as a YAML knob by design — a knob that theoretically could flip a guardrail will eventually be flipped by accident. If you find yourself wanting to add a knob that surfaces a protected field, stop and ask instead.

- **`_clean()` normalizes "Unknown" / "None" / whitespace to "" at every resolver.** No "Presenter: Unknown" artifacts. Every display-field resolver must go through it. When adding a new resolver, start from `_clean(meta.get(...))`.

- **Render config is YAML-first, not code-first.** Operators should tune citation density, metadata visibility, and source-label format via YAML. Only add a new YAML knob when there's a concrete operator need — don't pre-add knobs speculatively (s24 decision: dropped `show_client_identifiers` knob because it would expose a guardrail; dropped mode-level citation_instructions override because no mode needs it today).

### (All s9-23 rules unchanged — see session 24 prompt for the full list.)

---

## Budget for session 25

- **$1.00 interactive gate.**
- **$25.00 hard refuse.**
- **Sessions 22-24 each spent ~$0.001.** Session 25 expected: ~$0.05 for Option A (A/B chat calls), $0 for B/C/D.

## Files NOT to touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via audit module
- `ingester/loaders/drive_loader.py` (v1) — frozen
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except via M3 extract-and-redirect
- `ingester/loaders/types/*` — out of scope unless a specific item directs
- `ingester/loaders/drive_loader_v3.py` — out of scope this session
- `rag_server/display.py` — s24 delivery, don't touch unless a BACKLOG item directs

---

## Step 0 cheat sheet

```bash
# Tools + repo
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Chroma baseline (expect 605 — unchanged since s21)
./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"

# v3 chunks
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

# Sugar Swaps strip-ON
./venv/bin/python3 -c "
import chromadb
c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db')
col=c.get_collection('rf_reference_library')
r=col.get(ids=['drive:3-marketing:1ucqhpCFg5fmj78XyU2yj0ANGM3kJuG7Tuut1jBd2Vrk:0000'], include=['documents'])
t=r['documents'][0]
print('len:', len(t), 'has_canva:', 'canva.com' in t, 'starts_cover:', t.lstrip().startswith('COVER:'))
"

# Vertex AI auth
export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
./venv/bin/python3 -c "
import vertexai
from vertexai.generative_models import GenerativeModel
vertexai.init(project='rf-rag-ingester-493016', location='us-central1')
m = GenerativeModel('gemini-2.5-flash')
r = m.generate_content('say ok', generation_config={'max_output_tokens': 50, 'temperature': 0})
print('text:', repr(r.text.strip().lower()[:20]))
" 2>&1 | grep -v -i 'warning\|deprecat'

# Canonical renderer + YAML smoke (NEW s24)
./venv/bin/python3 -c "
from rag_server.display import chunk_to_display, format_context
from shared.config_loader import ConfigLoader
from pathlib import Path
for name in ['nashat_sales', 'nashat_coaching']:
    cfg = ConfigLoader(Path(f'config/{name}.yaml')).config
    print(f'{name}: citation_instructions={len(cfg.behavior.citation_instructions)} chars, render collections={list(cfg.knowledge.render.keys())}')
"

# Test suite (expect all 14 green)
set -a && . ./.env && set +a
for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py scripts/test_v3_metadata_writer_s19.py scripts/test_dedup_synthetic_s19.py scripts/test_canva_strip_synthetic_s19.py scripts/test_stage1_dedup_wiring_s20.py scripts/test_format_context_s24.py; do
  echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -2
done

# v3 dry-run
./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
```

---

## End of session 25 prompt

Session 24 shipped the canonical retrieval-rendering contract + YAML-configurable citation guidance. #18 closed, #20 code shipped with A/B deferred to this session, #17 deferred with explicit reopen trigger. All data state preserved exactly (605 chunks, 8 v3 chunks all metadata-complete, Sugar Swaps strip-ON, 14 tests green — 209 individual checks). Next session's natural work is validating the #20 citation guidance effect (Option A), or the strategic CONTENT_SOURCES.md conversation (Option B). Good luck.
