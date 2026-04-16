# NEXT SESSION PROMPT — session 27

> **⚠ READ THIS FIRST**
>
> Session 26 did a governance reset. Step 1.5 is now permanent (tiered). STATE_OF_PLAY.md has a canonical CURRENT STATE section at the top — **read that instead of the full HANDOVER on session open.** Update triggers are installed: closures that change CURRENT STATE must update STATE_OF_PLAY in the same commit; declines/defers must append to DECISIONS.md.
>
> **The goal of every session's bootstrap is to spend as little context as possible getting oriented so maximum context is available for the work.** The s26 reset made this possible. Do not re-read HANDOVER s9–s25 by default.

---

## OPERATING MODEL — read this before anything else

Carries forward from sessions 19–26. Seven rules unchanged, one new (#7):

1. **STEP 0 IS A GATE, NOT A VIBES-CHECK.** Run every numbered sub-check below in order, against actual disk state. Tool enumeration first — if Desktop Commander shows only a partial toolset, call `tool_search` with `"start_process write_file edit_block"`. Same for Filesystem (`"filesystem read file"`). SHOW the output of each sub-check. If reality doesn't match assertions, STOP and surface drift before reading further.

2. **STAIRCASE WITH MANDATORY HALT POINTS.** Plain-language writeup → Dan approves concept → code is written. Halts mandatory before `--commit`, before any Chroma write, at scope-option selection (A/B/C/D/etc.), at design points warranting tech-lead architecture review (M-options).

3. **AUTHORITY LINE.** Tactical → Claude. Strategic → Dan. Test: "can this be undone cheaply?" Yes → Claude. No → Dan. Surface tech-lead recommendations with rationale on scope decisions.

4. **ANTI-GOALS THIS SESSION:**
   - NO new file-type handlers until #35 (CONTENT_SOURCES.md) lands — UNLESS Dan explicitly relaxes
   - NO modifying v2 except via M3-style extract-and-redirect with byte-identical dry-run regression
   - NO Railway pushes until #43 lands, then #42 ships them
   - NO git operations by Claude
   - NO reading or quoting `.env` contents
   - NO referencing Dr. Christina / Dr. Chris / Massinople / Mass / Massinople Park (scrub mechanism enforces; do not bypass)
   - NO inline heredocs for Python > ~10 lines
   - NO re-proposing declined/deferred items — **check `docs/DECISIONS.md` before proposing anything that might re-litigate a prior decline**
   - NO modifying `rag_server/display.py` unless a BACKLOG item directs
   - NO modifying citation_instructions YAML text without scoping a live-A/B in the same session (s25 flight rule)
   - NO promoting drift markers to tasks on fewer than 3 observations

5. **COST GATES.** $1.00 interactive, $25.00 hard refuse. State projected spend up front. Track actual spend per step. **Floor for live-API A/B validation: $0.15.**

6. **CONTEXT BUDGET DISCIPLINE.** One-line context report at every halt: `[Context: ~XX% remaining. Spend so far: $Y.YY. Halts hit: N.]`. Warning at 30% remaining; at 20% recommend wrapping and writing s28 prompt.

7. **NEW s26 — GOVERNANCE UPDATE TRIGGERS (one-touch maintenance).** Installed s26 to prevent plan-doc drift:
   - If a session **closes a BACKLOG item that changes a fact in the CURRENT STATE section of STATE_OF_PLAY.md**, that session updates CURRENT STATE in the same commit (don't defer to a cleanup session that never gets scheduled).
   - If a session **declines or defers a BACKLOG item with a reopen trigger**, that session appends a 3-line entry to `docs/DECISIONS.md` with the trigger language.
   - If a session **closes an ADR-related BACKLOG item**, update the ADR's `Status:` line in the same commit (ADR_003 today: `Status: IMPLEMENTED (BACKLOG #29 closed s19 code / s20 A/B)`).
   - `docs/ARCHITECTURE.md`, `docs/REPO_MAP.md`, `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` are **demoted to historical-snapshot status.** Do not maintain. Read on demand only.

**Pace from sessions 21–26:** Larger steps with strategic-only halts. Doc updates batched at session close UNLESS they are one-touch triggers per #7 above. Zero-write sessions are valid build progress when they retire optionality. Live-API validation is **not** a Step 0 regression — run on demand only.

---

## Step 0 — Tool and reality check (mandatory)

### 0.1 — Tools

1. **Tool enumeration.** Need `Desktop Commander:start_process` + `interact_with_process` + `write_file` + `edit_block` + `Filesystem:read_text_file`. If partial DC toolset visible, call `tool_search`. Same for Filesystem.
2. **Smoke test.** Start `python3 -i`, send `print("session 27 ok"); print(2+2)`. Expect `session 27 ok` / `4`.

### 0.2 — Repo state

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -10`.
   - **Expected top commit: single session 26 commit** landing STATE_OF_PLAY rewrite + DECISIONS appends + BACKLOG #42/#43 + HANDOVER s26 + NEXT_SESSION_PROMPT_S27.md.
   - Below s26: s25 (`395d2f9`), s24 (`4ba085b`), s23 (`acbc174`), s22 (`624d6de`), s21 (`95b5831`).
   - **Working tree must be clean.**

### 0.3 — Data plane reality (UNCHANGED from s21 close)

4. **Reality-vs-prompt check.** Same 8 sub-checks as s26 prompt — no drift expected since s26 was zero-write on Chroma:

   - **Chroma baseline — `rf_reference_library` = 605**
   - **v3 chunks queryable — 8 chunks (7 pdf + 1 v2_google_doc), all metadata fields populated**
   - **Sugar Swaps chunk strip-ON** (len 3737, no canva, no COVER tag)
   - **OCR cache: 34 files**
   - **Drive + Vertex + OpenAI auth green**
   - **14 test scripts green** (19/19, PASS, 12/12, PASS, 22/22, restore, 9/9, 2/2, 12/12, 4/4, 15/15, 15/15, 4/4, 79/79)
   - **v3 dry-run byte-identical to s24 baseline** (9 chunks, $0.0010, vision cache hit)
   - **Canonical renderer + both YAMLs validate** (sales 468 chars / coaching 574 chars)

   Full bash cheat sheet at bottom of this prompt (copy-paste block by block).

### 0.4 — Admin UI

5. **Admin UI process state.** `lsof -iTCP:5052 -sTCP:LISTEN -P -n`. If nothing listening: `nohup ./venv/bin/python -m admin_ui.app > /tmp/rf_s27_admin_ui.log 2>&1 & disown`.
6. **Cache header:** `curl -sI http://localhost:5052/admin/folders | grep -i 'cache-control\|location'` — expect `Cache-Control: no-store`.
7. **Selection state on disk:** `cat data/selection_state.json`.

### 0.5 — Final Step 0 summary (expected shape)

```
✓ Step 0 PASS — repo at <s26-hash>, rf_reference_library: 605, v3: 8 (7 pdf + 1 v2_google_doc),
  all 4 s19 metadata fields populated, Sugar Swaps strip-ON, OCR cache: 34,
  14 test scripts green, admin UI on PID <pid>, canonical renderer + both YAMLs validate,
  v3 dry-run byte-identical to s24 baseline
```

If anything fails, STOP and surface to Dan.

---

## Step 1 — Read context (NEW SHRUNK SCOPE as of s26)

**Default reading order for session 27+ (changed s26):**

1. **`docs/STATE_OF_PLAY.md` — ONLY the CURRENT STATE section at the top** (~15 min read). This replaces reading HANDOVER s9–s25 entries by default. Everything below CURRENT STATE in STATE_OF_PLAY is historical amendment-log material — skip unless scope touches that era.

2. **`docs/HANDOVER.md` — only the most recent entry** (session 26, governance reset). Read in full. Earlier entries are read **on demand only** if the chosen scope touches that session's work.

3. **`docs/BACKLOG.md`** — scan for any items the chosen scope touches. Active priority list is already in CURRENT STATE section; don't re-read BACKLOG in full unless scope is ambiguous.

4. **`docs/DECISIONS.md`** — scan only if proposing something that might re-litigate a prior decision. Check before proposing any scope that touches #6b (coaching scrub), #17 (display_subheading), or anything declined/deferred.

**Anti-read list** (do NOT read by default — read on demand only if scope requires):
- HANDOVER entries sessions 1–25 (captured in STATE_OF_PLAY CURRENT STATE)
- STATE_OF_PLAY amendment log below the CURRENT STATE section
- `docs/ARCHITECTURE.md`, `docs/REPO_MAP.md`, `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` (demoted s26)
- ADR_001–006 (decision records — read the specific ADR if scope touches it)
- `docs/plans/*` (in-flight design docs, read only if scope crosses the relevant area)
- `INCIDENTS.md` (no open incidents)

---

## Step 1.5 — Status quick-check (tiered, as of s26)

**Default per-session: quick-check only (~2 min, $0).** Four lines to stdout:

1. **Plan docs last touched:** `ls -la docs/STATE_OF_PLAY.md docs/DECISIONS.md docs/BACKLOG.md docs/HANDOVER.md` — confirm all four were touched in the last session (or note which weren't and why).
2. **BACKLOG closure count since last full audit:** grep BACKLOG for `RESOLVED.*s<N>` where `<N>` is sessions since last full audit. Flag if >5 closures since last audit.
3. **ADR status scan:** grep `^**Status:**` across ADR_001–006. If any ADR has `PROPOSED` or `DEFERRED` but the referenced BACKLOG item is closed, flag for next-session fix.
4. **Open drift markers:** list count. Currently #41 (emoji, 1/3).

**Full audit (1.5.a–1.5.d per s26 prompt) required every 5 sessions OR if quick-check shows drift.** Last full audit: session 26. Next mandatory full audit: session 31. The four sub-deliverables are: BACKLOG status table, key-build-step audit, plan-doc drift report, drift-marker tracker.

**Halt after quick-check** — show Dan, proceed to Step 2 unless drift surfaced.

---

## Step 2 — Scope decision (Dan picks)

Recommended options carried forward from s26 audit:

### Option A — #35 CONTENT_SOURCES.md (HIGH, strategic)
**Scope:** Document canonical source per content domain. Blocks bulk ingestion. ~1hr conversation with Dan + ~30min writing `docs/CONTENT_SOURCES.md`. **Spend: $0. Risk: none.** Still the highest-leverage strategic pick.

### Option B — #43 ruamel.yaml fix + #42 Railway sync (HIGH if Dr. Nashat is about to share Railway URL)
**Scope:** #43 first (`admin_ui/forms.py` yaml.safe_dump → ruamel.yaml round-trip, ~45 min), then #42 Railway sync via cloudflared tarball playbook (~1hr including smoke test on prod URL). **Spend: ~$0.05 (prod smoke test). Risk: Low-Medium (Railway push is reversible per documented playbook).** Combined total ~2hr.

### Option C — #40 coaching link-surfacing A/B
**Scope:** Option 1 (soft nudge) YAML edit on coaching agent + live A/B validation. **Spend: ~$0.25. Risk: Low (YAML-only, reversible).** Good pick if Dan wants a tactical polish session with defined budget.

### Option D — #21 folder-selection UI redesign
**Scope:** Remove pending-panel/tree redundancy, sticky summary bar, drop vestigial library dropdown. Folds in #26(b). **Spend: $0. Risk: Low (UI only). Effort: 60–90 min.**

### Option E — #34 dry-run dump-json per-chunk text
**Scope:** Add `sample_chunks` array to per_file entries. **Spend: $0. Risk: Low. Effort: 30–45 min.**

### Tech-lead recommendation

Revised post-s26: **Option B (#43 + #42) may now be highest-leverage** if the Railway sync debt is actively blocking Dr. Nashat from testing, because it unblocks her testing workflow and retires accumulated risk in one session. **Option A (#35) stays the strategic pick** for when Dan has energy for the content-source-of-truth conversation. If neither feels right, **C or D** are clean tactical wins.

If the 1.5 quick-check surfaces unexpected drift, **that becomes Option F** and may outrank everything.

---

## Step 3+ — Execute

Once Dan picks, scope tight plan **before** writing code. Files touched, tests added, data writes + halts, minimum viable closure, spend estimate. Get approval, THEN execute.

**Remember the new flight rule (#7):** if execution closes a BACKLOG item that changes CURRENT STATE, update STATE_OF_PLAY in the same commit. If it declines/defers with reopen trigger, append to DECISIONS.md. No separate cleanup session.

---

## Optional: Use Claude Code with 1M context window

Installed s26-era: Claude Code CLI is available (`npm install -g @anthropic-ai/claude-code`, then `claude` from repo root). For long build sessions where context is tight in Desktop Claude, toggle 1M context with `/context-1m` inside the Claude Code session.

**When to use Claude Code 1M:**
- Heavy build sessions (scoping a new v3 handler, the ruamel.yaml + Railway sync combo, the content-sources conversation)
- Sessions where you expect to read 3+ large docs plus do real work
- Sessions that would otherwise hit the 20%-context warning before Step 2

**When to stay in Desktop Claude:**
- Short tactical sessions (single BACKLOG item, well-scoped)
- Conversations and scope decisions (memory + conversation history is richer here)
- Sessions where artifacts/visuals matter (Claude Code is terminal-only)

**Cost note:** Claude Code 1M is billed per-token with a premium tier above 200K tokens in context. A session that loads 200K of docs + does real work is meaningfully pricier than Desktop Claude but unlocks work that would otherwise require 2–3 Desktop sessions.

**Bootstrap for Claude Code sessions:** paste this file's path as the first message (`Read /Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/docs/NEXT_SESSION_PROMPT_S27.md first and follow it.`). The default reading order (STATE_OF_PLAY CURRENT STATE + latest HANDOVER) scales identically in either environment.

---

## ALL FLIGHT RULES (carried forward, sessions 9 → 26)

All rules from s26's prompt carry forward. One s26 addition captured in Operating Model #7 above:

### Governance update triggers (s26)
- BACKLOG closure changes CURRENT STATE → update STATE_OF_PLAY same commit
- BACKLOG decline/defer with reopen trigger → append DECISIONS.md same commit
- ADR-related BACKLOG closure → update ADR `Status:` line same commit
- ARCHITECTURE/REPO_MAP/COACHING_CHUNK_CURRENT_SCHEMA demoted, do not maintain

### Live-API validation scripts are not regression tests (s25)
- Naming: `test_*_ab_live_s<N>.py`. Retain in `scripts/` but NOT in Step 0 suite.
- Step 0 suite requires (a) <$0.001 per run, (b) stable output across sessions.
- Current live-API one-shots: `test_citation_instructions_ab_live_s25.py`, `test_canva_strip_ab_live_s20.py`, `test_chat_smoke_s17.py`.

### Cost floor for live-API A/B validation: $0.15 (s25)
- Never estimate below $0.15 for an 8-call Sonnet run with retrieved context.
- Token floor: 5,500–8,000 input + 400–650 output per call.
- Pricing (Sonnet 4.6): $3/M input, $15/M output → $0.02–0.04 per call.

### Drift-marker convention (s25)
- Observations in HANDOVER (and BACKLOG if recurring) as markers, not tasks.
- Promotion threshold: 3 independent occurrences across separate runs.
- Current markers: #41 (sales emoji, 1/3).

### (All s9–24 rules unchanged — see session 25 / 26 prompts for the full list.)

---

## Budget for session 27

- **$1.00 interactive gate. $25.00 hard refuse.**
- **Sessions 22–26 spent: $0, $0, $0.001, $0.23 (s25 live A/B), $0.001 (s26 governance reset).**
- **Session 27 expected:** $0 for A/D/E; $0.05 for B (prod smoke test); $0.20–0.30 for C.

---

## Files NOT to touch

- `chroma_db/*` — never edit directly
- `data/inventories/*.json` — folder walk output
- `data/audit.jsonl` — append-only via audit module
- `ingester/loaders/drive_loader.py` (v1) — frozen
- `ingester/loaders/drive_loader_v2.py` (v2) — frozen except via M3
- `ingester/loaders/types/*` — out of scope unless specific item directs
- `ingester/loaders/drive_loader_v3.py` — out of scope unless #34 picked
- `rag_server/display.py` — s24 delivery; untouchable unless BACKLOG directs
- `config/nashat_sales.yaml` — s24-25 stable; no edit without A/B budget
- `config/nashat_coaching.yaml` — edit ONLY under Option C (#40)
- `scripts/test_citation_instructions_ab_live_s25.py` — s25 artifact
- **`docs/ARCHITECTURE.md`, `docs/REPO_MAP.md`, `docs/COACHING_CHUNK_CURRENT_SCHEMA.md`** — demoted s26, do not edit

---

## Step 0 cheat sheet

```bash
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
git status && git log --oneline -10

# Reality checks as documented in Step 0 above. Full bash block is identical
# to session 26's prompt — copy-paste from there if needed.
```

---

## End of session 27 prompt

Session 26 did a governance reset: STATE_OF_PLAY has a canonical CURRENT STATE section, DECISIONS.md has entries for #6b/#17 declines + s26 reset rationale, BACKLOG has #42 (Railway sync backlog) and #43 (ruamel.yaml fix) added. HANDOVER s26 entry documents it all. Update-trigger flight rules (#7) are installed. Step 1.5 is now tiered — quick-check by default, full audit every 5 sessions or on drift.

Default per-session reading is now STATE_OF_PLAY CURRENT STATE + latest HANDOVER entry. HANDOVER s9–s25 and the three demoted plan docs are read on demand only. This should free ~30% of context for actual work vs. the s25/s26 baseline.

Tech-lead picks: **B (#43 + #42)** if Dr. Nashat is about to share Railway URL; **A (#35)** for strategic unblocking; **C (#40)** for tactical polish. Good luck.
