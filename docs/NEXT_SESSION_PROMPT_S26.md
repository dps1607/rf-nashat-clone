# NEXT SESSION PROMPT — session 26

> **⚠ READ THIS FIRST**
>
> Step 0 has paid for itself every session 9 onward. s25 closed BACKLOG #20 fully (live A/B validated citation_instructions; ship-as-is). Two new BACKLOG items opened s25: #40 (encourage coaching link-surfacing — Dan-directed), #41 (emoji drift marker, watch-only). **Session 26 must run Step 0 in full, then a Step 1.5 status audit of all open BACKLOG items vs plan docs.**

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19-25. All six rules unchanged.

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
   - NO re-proposing #6b coaching scrub retrofit (Dan declined s23)
   - NO re-proposing #17 display_subheading normalization (Dan deferred s24)
   - NO modifying `rag_server/display.py` unless a BACKLOG item directs (#40 Option 3 would qualify; nothing else currently)
   - NO modifying citation_instructions YAML text without scoping a live-A/B in the same session (s25 flight rule; #40 execution is the expected path)
   - NO promoting drift markers (e.g. #41) to tasks on fewer than 3 observations

5. **COST GATES.** $1.00 interactive, $25.00 hard refuse. State projected spend up front. Track actual spend per step. **Floor for live-API A/B validation: $0.15 (s25 lesson — NOT $0.05).**

6. **CONTEXT BUDGET DISCIPLINE.** One-line context report at every halt: `[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]`. Surface warning at 30% remaining; at 20% recommend wrapping and writing s27 prompt.

**Pace from sessions 21–25:** Larger steps with strategic-only halts. Doc updates batched at session close. Zero-write sessions are valid build progress when they retire optionality. Live-API validation is **not** a Step 0 regression — run on demand only.

---

## Step 0 — Tool and reality check (mandatory)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `Filesystem:read_text_file`. If partial DC toolset visible, call `tool_search`. Same for Filesystem.
2. **Smoke test.** Start `python3 -i`, send `print("session 26 ok"); print(2+2)`. Expect `session 26 ok` / `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: a single session 25 commit** landing `scripts/test_citation_instructions_ab_live_s25.py` + BACKLOG #20 closure + #40/#41 new entries + HANDOVER s25 entry + NEXT_SESSION_PROMPT_S26.md.
   - Below s25: s24 (`4ba085b`), s23 (`acbc174`), s22 (`624d6de`), s21 (`95b5831`).
   - **Working tree must be clean.**

### 0.3 — Data plane reality (UNCHANGED from s21 close — s22/23/24/25 all zero-write on Chroma)

4. **Reality-vs-prompt check.**

   - **Chroma baseline — `rf_reference_library` = 605:**
     ```bash
     ./venv/bin/python3 -c "import chromadb; c=chromadb.PersistentClient(path='/Users/danielsmith/Claude - RF 2.0/chroma_db'); col=c.get_collection('rf_reference_library'); print('rf_reference_library:', col.count())"
     ```

   - **v3 chunks queryable — 8 chunks (7 pdf + 1 v2_google_doc), all metadata fields populated:**
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

   - **Sugar Swaps chunk strip-ON:**
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

   - **OCR cache:** `ls data/image_ocr_cache/*.json | wc -l` → **34**.

   - **Drive auth:**
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
     ./venv/bin/python3 -c "from google.oauth2 import service_account; import os; creds = service_account.Credentials.from_service_account_file(os.environ['GOOGLE_APPLICATION_CREDENTIALS']); print('OK', creds.service_account_email)"
     ```
     Expect `OK rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`.

   - **Vertex AI auth:**
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

   - **OpenAI auth:** Source `.env` in subshell, minimal `embeddings.create("test")` returning 3072 dims.

   - **Test suite — 14 scripts (s25 A/B script NOT in suite per flight rule):**
     ```bash
     set -a && . ./.env && set +a
     export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json
     for t in scripts/test_scrub_s13.py scripts/test_scrub_wiring_s13.py scripts/test_types_module.py scripts/test_chunk_with_locators.py scripts/test_format_context_s16.py scripts/test_admin_save_endpoint_s16.py scripts/test_google_doc_handler_synthetic.py scripts/test_scrub_v3_handlers.py scripts/test_docx_handler_synthetic.py scripts/test_v3_metadata_writer_s19.py scripts/test_dedup_synthetic_s19.py scripts/test_canva_strip_synthetic_s19.py scripts/test_stage1_dedup_wiring_s20.py scripts/test_format_context_s24.py; do
       echo "=== $t ==="; ./venv/bin/python "$t" 2>&1 | tail -2
     done
     ```
     Expect: 19/19, PASS, 12/12, PASS, 22/22, 16/16, 9/9, 2/2, 12/12, 4/4, 15/15, 15/15, 4/4, 79/79.

   - **v3 dry-run regression:**
     ```bash
     ./venv/bin/python -m ingester.loaders.drive_loader_v3 --dry-run 2>&1 | tail -25
     ```
     Expected: 9 chunks / by_handler `{pdf: 1, v2_google_doc: 2}` / vision_cache_hit / est_tokens ~7,603 / $0.0010.

   - **Canonical renderer + both YAMLs:**
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
     Expected: sales 468 chars + `['rf_reference_library']`; coaching 574 chars + `['rf_coaching_transcripts', 'rf_reference_library']`.

### 0.4 — Admin UI

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If nothing listening: `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s26_admin_ui.log 2>&1 & disown`.
6. **Cache header:** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'` — expect `Cache-Control: no-store`.
7. **Selection state on disk:** `cat data/selection_state.json`.

### 0.5 — Final Step 0 summary

```
✓ Step 0 PASS — repo at <s25-hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc),
  all 4 s19 metadata fields populated (8/8 except source_file_md5 7/8 by design),
  Sugar Swaps strip-ON, OCR cache: 34,
  14 test scripts green, admin UI on PID <pid>,
  canonical renderer + both YAMLs validate, v3 dry-run byte-identical to s24 baseline
```

If anything fails, STOP and surface to Dan.

---

## Step 1 — Read context

After Step 0 passes:

1. **`docs/HANDOVER.md` — session 25 entry** (~130 lines at bottom). #20 closure, link-surfacing observation → #40, emoji drift → #41, cost-floor and regression-suite flight rules.
2. **`docs/HANDOVER.md` — session 24 entry** (~200 lines above). Canonical renderer + protected-fields contract + 2-layer retrieval/rendering separation.
3. **`docs/BACKLOG.md`** — focus on #40, #41 (new s25), #35 (HIGH, still blocking), whatever the chosen scope touches. #17/#6b reopen triggers: reference only, do NOT re-propose.

---

## Step 1.5 — Status audit (NEW s26 requirement from Dan)

**Before scope selection**, produce a status snapshot. This is a one-shot read of the BACKLOG + key plan docs to give Dan an at-a-glance view of where everything stands, and to catch any drift between what the BACKLOG claims and what the plan docs assume.

**Plan docs to cross-reference (read as needed — use `grep` for specific BACKLOG numbers or topics rather than full reads if context budget is tight):**
- `docs/STATE_OF_PLAY.md` — the canonical project plan; anything marked "next step" here should have a corresponding BACKLOG entry or be in active scope
- `docs/ARCHITECTURE.md` — system design; cross-check that closed BACKLOG items (e.g. #18, #20, #23, #29, #30, #37, #38, #39) are reflected architecturally
- `docs/DECISIONS.md` — decision log; confirm declined items (#6b, #17) are captured with rationale
- `docs/REPO_MAP.md` — file/module inventory; spot-check that new files from recent sessions (display.py s24, test_citation_instructions_ab_live_s25.py s25, the handler types s17-18) are listed
- `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` — chunk schema; confirm no drift vs what v3 loaders are writing
- `docs/plans/` — any in-flight design docs (v3 drive loader etc.)
- `INCIDENTS.md` — incident log; confirm nothing is open that scope should address
- `ADR_001` through `ADR_006` at repo root — grep for any BACKLOG numbers referenced

**Deliverable (print to stdout, do NOT write to disk):**

### 1.5.a — BACKLOG status table

For every numbered BACKLOG item, one row: **#N | Title | Status (Open | Closed | Declined | Deferred | Marker)** | **Priority (HIGH / MEDIUM / LOW / Observation-only)** | **Dependency** (if any) | **Session closed** (if applicable) | **Plan-doc alignment flag** (✓ aligned / ⚠ drift / ? not-referenced)

### 1.5.b — Key build-step audit

For each major build axis, one-line status:
- **Data plane (Chroma collections):** counts, known pollution status, open retrofits
- **Ingestion pipeline (v1/v2/v3):** which loaders are live, which are frozen, what handlers exist (pdf, google_doc, docx — what's next)
- **Retrieval + rendering (display.py + YAMLs):** what's canonical, what's YAML-configurable, what's hardcoded-protected
- **Agent configs (sales, coaching):** modes, citation behavior status, known drift markers
- **Admin UI:** auth, folder selection, known friction points (#21)
- **Deployment (Railway):** last sync state, pending changes
- **Content source-of-truth (#35):** status, items blocked on it (#36, bulk ingestion)
- **Testing (regression suite):** count, categories, what's NOT in suite (live-API one-shots)

### 1.5.c — Plan-doc drift report

List any items where BACKLOG says one thing and a plan doc says another. Expected to be empty or short; if >3 items drift, surface as a flag for Dan.

### 1.5.d — Observations / drift markers tracker

List all HANDOVER-logged drift markers that are NOT tasks: their name, current observation count, promotion threshold. (At s25 close: #41 emoji drift at 1/3.)

**Estimated effort:** ~15-20 min of reading + writing the snapshot. **Spend:** $0 (read-only).

**Halt after 1.5:** show Dan the snapshot, let him absorb, then proceed to Step 2 scope selection.

---

## Step 2 — Scope decision (Dan picks)

### Option A — #35 CONTENT_SOURCES.md (HIGH priority, carries forward from s25 tech-lead rec)

**Scope:** Document canonical source per content domain. Blocks bulk ingestion of all text-bearing file types. **Requires Dan's active decision-making input** — conversation session, not execution.

**Shape:** ~1hr walking the inventory (blogs, lead magnets, coaching, email sequences, educational reference) + ~30min writing `docs/CONTENT_SOURCES.md`. Dan decides canonical source per domain; Claude captures.

**Why HIGH:** Every future ingestion session is blocked. April-May 2023 Blogs.docx (#36) is waiting. Next v3 handler is technically ready but can't commit without source-of-truth mappings.

**Effort:** ~1.5hr. **Spend:** $0. **Risk:** none.

### Option B — #40 encourage coaching link-surfacing

**Scope:** Pick one of the three YAML options documented in BACKLOG #40 (recommended: Option 1 soft nudge), apply YAML edit, re-run live A/B validation modeled on s25 script.

**Effort:** ~45 min YAML + A/B run. **Spend:** ~$0.20-0.30 (live Sonnet). **Risk:** Low-Medium (YAML text change that could affect voice; A/B catches it).

**Good pick if:** Dan wants to close the loop on the s25 observation before it fades from context, has ~$0.25 budget, prefers a short quality-polish session over the heavier #35 conversation.

### Option C — #21 folder-selection UI redesign

**Scope:** Remove pending-panel/tree redundancy, sticky summary bar, remove vestigial library dropdown, visual differentiation drives/folders/files. Folds in #26(b) `selectionState` retrofit.

**Effort:** 60-90 min. **Spend:** $0. **Risk:** Low (UI only). Test Chrome first per s23 flight rule.

### Option D — #34 dry-run dump-json includes per-chunk text

**Scope:** Add `sample_chunks` array to each `per_file` entry in dry-run run records (text_preview, word_count, display_locator, name_replacements). Satisfies halt-before-commit inspection need without ad-hoc extraction scripts.

**Effort:** ~30-45 min. **Spend:** $0. **Risk:** Low.

### Option E — STATE_OF_PLAY amendment for s19-25

Compress HANDOVER s19-25 into STATE_OF_PLAY amendment.

**Effort:** ~1hr. **Spend:** $0. **Risk:** none.

### Tech-lead recommendation

**Option A (#35)** still the highest-leverage pick — it's the last strategic blocker before bulk ingestion. But **Option B (#40)** is a good tactical alternative if Dan wants to ship something concrete quickly and has the A/B budget. If Dan is short on strategic decision-energy, **C or D** are clean tactical wins. **E is the rest-day pick** and worth doing within 2 sessions before HANDOVER bloats further.

If the 1.5 status audit surfaces any unexpected drift or incidents, **that becomes Option F** and may outrank everything.

---

## Step 3+ — Execute

Once Dan picks, scope tight plan **before** writing code. Files touched, tests added, data writes + halts, minimum viable closure, spend estimate. Get approval, THEN execute.

---

## ALL FLIGHT RULES (carried forward, sessions 9 → 25)

All rules from s25's prompt carry forward. Two s25 additions explicitly captured:

### Live-API validation scripts are not regression tests (s25)

- Any test script that makes live Sonnet / Vertex / OpenAI generation calls is a **one-shot validation tool**, not a regression test. Lives in `scripts/` but NOT in Step 0 suite.
- Step 0 suite requires (a) <$0.001 per run, (b) stable output across sessions. Live A/B violates both.
- Naming convention for live-API one-shots: `test_*_ab_live_s<N>.py`. Docstring must explicitly flag cost-bearing + one-shot.
- Current live-API one-shots retained for on-demand re-runs: `scripts/test_citation_instructions_ab_live_s25.py`, `scripts/test_canva_strip_ab_live_s20.py`, `scripts/test_chat_smoke_s17.py`.

### Cost floor for live-API A/B validation: $0.15 (s25)

- Never estimate live-API A/B spend below $0.15 for an 8-call run. s25 quoted $0.05, spent $0.23 (~5× miss).
- Token floor: 5,500-8,000 input + 400-650 output per Sonnet call with retrieved context.
- Pricing (Sonnet 4.6): $3/M input, $15/M output → $0.02-0.04 per call.
- When proposing live-API validation, include token floor in the spend justification, not just a round number.

### Drift-marker convention (s25)

- Observations that might become problems but haven't yet live in HANDOVER (and BACKLOG if recurring) as **markers**, not tasks.
- Promotion threshold: **3 independent occurrences** of the same drift pattern across separate runs or production responses. Until then, just watch.
- Current markers: #41 (sales emoji, 1/3).

### (All s9-24 rules unchanged — see session 25 prompt for the full list.)

---

## Budget for session 26

- **$1.00 interactive gate. $25.00 hard refuse.**
- **Sessions 22-24 spent ~$0.001 each. Session 25 spent $0.23 (live A/B).**
- **Session 26 expected:** $0 for A/C/D/E; $0.20-0.30 for B (if picked).

---

## Files NOT to touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output, never hand-edit
- `data/audit.jsonl` — append-only via audit module
- `ingester/loaders/drive_loader.py` (v1) — frozen
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except via M3 extract-and-redirect
- `ingester/loaders/types/*` — out of scope unless specific item directs
- `ingester/loaders/drive_loader_v3.py` — out of scope (unless Option D)
- `rag_server/display.py` — s24 delivery; untouchable this session even under #40 (pick Option 1 or 2, not Option 3)
- `config/nashat_sales.yaml` — s24-25 stable; don't edit without A/B budget
- `config/nashat_coaching.yaml` — edit ONLY under Option B (#40) and only per one of the three documented options
- `scripts/test_citation_instructions_ab_live_s25.py` + `data/s25_citation_ab_results.json` — s25 artifacts

---

## Step 0 cheat sheet

```bash
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# All checks as documented in Step 0 above. Copy-paste block by block.
```

---

## End of session 26 prompt

Session 25 shipped #20 A/B validation ($0.23 spend), ship-as-is verdict, #20 fully closed. Two new BACKLOG items from Dan-directed observations: #40 (encourage coaching link-surfacing) and #41 (emoji drift marker, watch-only). Three new flight rules: live-API scripts not in regression suite; $0.15 cost floor for live A/B; drift-marker promotion at n=3.

All data state preserved (605 chunks, 8 v3 metadata-complete, Sugar Swaps strip-ON, 14 regression tests green).

**s26 requirement from Dan:** Step 1.5 status audit before scope selection. Produce BACKLOG table + key-build-step audit + plan-doc drift report + drift-marker tracker. ~15-20 min, $0.

Tech-lead pick still #35 (HIGH, strategic, overdue). Tactical alternatives: #40 (Dan-directed quality polish, ~$0.25), #21 (UI redesign), #34 (dry-run dump-json). Good luck.
