# NEXT SESSION PROMPT — session 28

> **Read s27 HANDOVER entry first.** s27 closed #43 as "already resolved, verified" and narrowed #42 to a single chroma content-verification query. The main flight-rule and governance framework from s27 (and s26 before it) carries forward unchanged.

---

## OPERATING MODEL — carries forward from s27 unchanged

All seven rules from s27 apply. Anti-goals unchanged. Cost gates unchanged ($1.00 interactive / $25.00 refuse / $0.15 live-A/B floor). Governance update triggers (#7) active.

**One small s27 lesson added:** Copy v3 metadata field names **verbatim from CURRENT STATE** instead of paraphrasing, to avoid the prompt-text drift s27 flagged. The correct v3 marker fields are `source_pipeline=drive_loader_v3`, `v3_category` (pdf / v2_google_doc / docx), `v3_extraction_method`, plus the four s21 backfill fields (`extraction_method`, `library_name`, `content_hash`, `source_file_md5`). Display fields start with `display_*`.

---

## Step 0 — Reality check (short version; s27's passed clean so expect zero drift)

### 0.1 — Tools + smoke

Same as s27. If `tool_search` needed, invoke with `"start_process write_file edit_block"` / `"filesystem read file"`.

### 0.2 — Repo state

Expected top commit: **s27 commit** landing #43 closure + STATE_OF_PLAY update + HANDOVER s27 entry + this prompt. Below that: `4ffbfe4` (s26), `395d2f9` (s25). Working tree clean. `origin/main` = local HEAD (s27 included a push).

### 0.3 — Data plane (UNCHANGED from s27 close — zero writes)

- `CHROMA_DB_PATH` (from `.env`) points to `/Users/danielsmith/Claude - RF 2.0/chroma_db`
- **Never use relative path `chroma_db` from cwd = repo root** — triggers s27's empty-stub foot-gun
- rf_reference_library = **605** / rf_coaching_transcripts = **9,224**
- v3 chunks = **8** via `source_pipeline=drive_loader_v3` filter (7 `v3_category=pdf` + 1 `v3_category=v2_google_doc`)
- Sugar Swaps chunk (display_source "[RH] The Fertility-Smart Sugar Swap Guide", v3_category v2_google_doc): len = **3737**, no "canva" substring, no "[COVER" tag
- OCR cache at `data/image_ocr_cache`: **34** files
- Admin UI on PID from `lsof -iTCP:5052 -sTCP:LISTEN -P -n`; `Cache-Control: no-store`

### 0.4 — NEW 0.4 check: Railway origin/main status

One-liner: `git fetch origin main && git log --oneline origin/main..HEAD`. Expect empty output (no unpushed local commits). Catches s27-style "intermittent-session ghost push" state.

### 0.5 — NEW 0.5 check for #42 scope: Railway chroma content verification

**This is the one real pending verification from s27.** If scope includes #42, run early:

```
railway ssh "ls /app/rag_server/display.py && wc -l /app/rag_server/display.py"
# expect: exists, 358 lines  (confirms s24 code deployed)

railway ssh '/path/to/app/venv/bin/python -c "<chroma-query-script>"'
# expect: 605 total, 8 v3 chunks, Sugar Swaps len=3737 no canva
```

Finding the right python binary on Railway was the blocker in s27. Options to try in order: `/app/.venv/bin/python`, `/app/venv/bin/python`, or read the Railway Procfile to see which python runs the app. If none works, upload a probe script via `railway run bash -c "cat > /tmp/probe.py"` then `railway run python3 /tmp/probe.py`.

**If query confirms Railway has the 8 v3 chunks + strip-ON Sugar Swaps:** close #42 as already-resolved-s28 (same pattern as #43). Update BACKLOG + STATE_OF_PLAY per governance trigger #7. $0 spend. Zero-write session.

**If query shows Railway chroma is stale:** proceed with Z1 per `HANDOVER_PHASE3_COMPLETE.md` §"How chroma_db was uploaded" — tarball + python http.server + cloudflared + `railway variables set CHROMA_BOOTSTRAP_URL` + `railway redeploy --yes`. Clear /data/chroma_db first (bootstrap only fires on empty dir). ~$0.05 spend.

---

## Step 1 + 1.5 — same pattern as s27

Default reading: CURRENT STATE section of STATE_OF_PLAY + HANDOVER s27 entry only. Quick-check on plan-docs + ADR status + drift markers. Full audit due **s31** (every 5 sessions, last full = s26).

---

## Step 2 — scope options

### Option A — #35 CONTENT_SOURCES.md (HIGH, strategic)
Still the highest-leverage strategic pick. $0 / ~1.5hr incl. conversation. Blocks all new handler work.

### Option B — #42 verify-or-sync
Per 0.5 above. One query, probably $0. If Z1 needed: $0.05.

### Option D — #21 folder-selection UI redesign (carried from s27)
$0 / 60-90 min. Deferred from s27 due to context pressure. Solo-scopable.

### Option E — #34 dry-run dump per-chunk text
$0 / 30-45 min. Tactical observability.

### Option F — small governance cleanups (F1/F2/F3 from s27 HANDOVER)
- F1/F2: tiny — fix prompt-text drift in future session prompts (already partly done in this prompt)
- F3: guard `PersistentClient` from silent empty-chroma auto-creation on relative paths. ~15 lines + test in `ingester/loaders/_drive_common.py` or shared helper. Low-Medium priority.

### Tech-lead rec

**B first** (verify #42 — cheap and retires optionality). If verify-only ($0) closes #42, then:
- **D (#21)** if you want a tactical UI win today, OR
- **A (#35)** if you have energy for the strategic content-sources conversation

F3 is a clean ~30min add-on to B or D if budget permits.

---

## Budget for session 28

- **$1.00 interactive / $25.00 refuse.**
- s27 spent: $0.
- s28 expected: $0 (B verify-only) to $0.05 (B Z1 sync) plus whatever scope-2 adds.

---

## Files NOT to touch (same list as s27)

- `chroma_db/*` — never edit directly
- `data/inventories/*.json`, `data/audit.jsonl`
- v1/v2/v3 loaders — out of scope unless specific item directs
- `rag_server/display.py` — s24 delivery; untouchable unless BACKLOG directs
- `config/nashat_*.yaml` — stable; no edit without A/B budget
- The three demoted plan docs (ARCHITECTURE, REPO_MAP, COACHING_CHUNK_CURRENT_SCHEMA)

---

## End of session 28 prompt

s27 produced two governance closures (#43 + narrowed #42) with zero code changes and zero spend. s28's cheapest win is the one remaining Railway verify query. If that closes #42, the session can pivot to any of A/D/E/F without carrying forward deferred sync debt. Good luck.
