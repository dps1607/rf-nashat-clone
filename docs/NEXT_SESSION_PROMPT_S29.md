# NEXT SESSION PROMPT — session 29

## Bootstrap reading (do this before anything else)

This prompt is compact. The "carries forward unchanged" references below resolve to content in prior session prompts — a cold session must actually read that content, not just acknowledge the phrase.

1. Read this file (`docs/NEXT_SESSION_PROMPT_S29.md`) in full.
2. Read `docs/NEXT_SESSION_PROMPT_S28.md` sections **"OPERATING MODEL"** and **"ALL FLIGHT RULES"** (which itself points to S27's sections — read those too).
3. Read `docs/HANDOVER.md` session 28 entries (there are two — scope B starts at `## Session 28 — BACKLOG #42 RESOLVED...`; scope A continues at `## Session 28 (cont.) — BACKLOG #35 RESOLVED...`). Read both.
4. Read the **CURRENT STATE section** of `docs/STATE_OF_PLAY.md` (first ~170 lines).
5. Read `docs/CONTENT_SOURCES.md` in full — this is a NEW canonical doc as of s28 that scopes 14 content domains + 13 target collections + 28 follow-up seeds. Essential context for almost any s29+ scope.
6. Then proceed to Step 0 below.

**This bootstrap pattern carries forward to s30+.** When writing the s30 prompt at session close, copy this block and bump the S28/s28 references to S29/s29.

> **tl;dr on s28:** Four scopes landed in one extended session. **Scope B:** Railway chroma sync (#42 RESOLVED). **Scope A:** `docs/CONTENT_SOURCES.md` shipped (#35 RESOLVED, 489 lines, 14 domains, 13 target collections). **Scope C:** BACKLOG expansion #50-#75 (30 new entries) + #44 migration executed (`rf_published_content` created + 8 chunks migrated). **Scope D:** #56 HTML handler + blog pipeline shipped via WordPress REST API, single-post smoke committed (rf_published_content 8→13), bulk ingestion deferred to #75 per build-vs-go-live discipline. #36 closed as superseded. Total spend $0.000618 across all four scopes.

---

## OPERATING MODEL — carries forward from s27/s28 unchanged

All seven rules from s27 apply (read `docs/NEXT_SESSION_PROMPT_S27.md` sections OPERATING MODEL + ALL FLIGHT RULES). Anti-goals unchanged. Cost gates unchanged ($1.00 interactive / $25.00 refuse / $0.15 live-A/B floor). Governance update triggers (#7) active.

**s28 context-window recalibration.** s28 surfaced that Dan is using Claude Code with 1M context window enabled. Operating Model #6 context thresholds (30% warning / 20% wrap) were written against a 200K baseline. At 1M, the equivalent absolute thresholds are ~240K remaining (warning) / ~200K remaining (wrap-and-write-next-prompt). Claude should report context percentage against the active window, not the 200K default. If unsure which window is active, ask.

**s28 lessons added to flight rules:**

1. **"Already-resolved on reading" is a recurring governance-drift pattern** (s27 for #43, s28 partial for code-already-deployed). Step 1.5 quick-check should gain a line for "grep 1 active HIGH-priority BACKLOG item at random, sanity-check its stated premise against code." Applied ad-hoc; formalize when a third occurrence surfaces.

2. **Silent architectural changes must be flagged in the main conversation, not buried in a doc edit.** s28 caught one instance: v1 of CONTENT_SOURCES.md silently folded `rf_published_content` into `rf_reference_library` without telling Dan. Rule: any re-interpretation or reversal of a prior-session decision goes through conversation halt before doc edit.

3. **Over-explanation is a tax.** Canonical source-of-truth docs should be decisions + one-sentence rationale. Implementation sketches belong in ADRs or BACKLOG items. V2→v3 of CONTENT_SOURCES.md cut 48 lines of narration without losing any decision.

4. **Visual redline for doc review.** `difflib.HtmlDiff.make_table()` generates a side-by-side color-coded HTML redline that's dramatically easier to review than unified-format diff. Use this recipe for any ≥100-line doc review.

5. **UUID-subdir equality is not content equality.** Chroma UUIDs are stable across upserts. Always query row counts + metadata, not filesystem structure, when diagnosing sync state.

---

## Step 0 — Reality check

Same pattern as s28. Run each numbered sub-check and show output.

### 0.1 — Tools + smoke

Same as s28. `tool_search` if partial toolset. Python smoke test: `python3 -c 'print("session 29 ok"); print(2+2)'`.

### 0.2 — Repo state

Expected top commit: **single session 28 close commit** landing `docs/CONTENT_SOURCES.md` (new) + BACKLOG updates (#35 closed, #44-#49 added) + STATE_OF_PLAY updates (collections table expanded) + HANDOVER s28 scope-A section + this prompt. Below that: `c1db89d` (s28 scope B, Railway chroma sync), `00ee651` (s27 follow-up), `a3a5c0a` (s27 main), `4ffbfe4` (s26).

Working tree clean. `origin/main` may or may not match local HEAD depending on whether Dan pushed. Check with `git fetch origin main && git log --oneline origin/main..HEAD`.

### 0.3 — Data plane (post s28-extended scope D — #44 + #56 applied)

- `CHROMA_DB_PATH` from `.env` → `/Users/danielsmith/Claude - RF 2.0/chroma_db` (absolute; avoid relative-path foot-gun from s27)
- rf_reference_library = **597** (external-approved only per s28 tightening)
- rf_published_content = **13** (8 migrated per #44: 7 Egg Health + 1 Sugar Swaps; 5 blog chunks per #56 single-post smoke: Indoor Air Pollution post 18885)
- rf_coaching_transcripts = **9,224** (unchanged; `client_rfids` still flagged for #45 removal)
- Total: 9,834 chunks across 3 collections
- v3 chunks = 8, all in rf_published_content
- blog_loader chunks = 5, all in rf_published_content, `source_pipeline=blog_loader`
- Sugar Swaps: len=3737, no canva, no COVER (strip-ON preserved across migration)
- OCR cache at `data/image_ocr_cache`: **34 files**
- Admin UI on PID from `lsof -iTCP:5052 -sTCP:LISTEN -P -n`; `Cache-Control: no-store`
- **Railway: diverges from local by 13 chunks** — all in `rf_published_content` which doesn't exist on Railway. Low impact until agents retrieve from `rf_published_content` specifically. Tracked as #74.
- **Regression suite: 15 test scripts** (was 14) — new `test_blog_loader_synthetic.py` adds 23 assertions

### 0.4 — Origin/main ghost-push check

`git fetch origin main && git log --oneline origin/main..HEAD`. Expect empty or one or two commits depending on whether Dan pushed s28 close.

### 0.5 — CONTENT_SOURCES.md sanity

New canonical doc as of s28. Run `wc -l docs/CONTENT_SOURCES.md` → expect 489. Grep for `^## ` → expect 21 sections (intro, framing, collections, domains 1-14, anti-ingestion, cross-cutting rules, BACKLOG seeds, end). If either is off, the doc has drifted — surface to Dan before proceeding.

---

## Step 1 + 1.5 — same pattern as s28

Default reading: CURRENT STATE section of STATE_OF_PLAY + HANDOVER s28 entries (both) + CONTENT_SOURCES.md in full. Quick-check on plan-docs + ADR status + drift markers. Full audit due **s31** (every 5 sessions, last full = s26).

---

## Step 2 — scope options

### Option A — #57 Email platform export mechanism (MED-HIGH)
**Scope:** Identify the authoritative email platform (Kajabi most likely; possibly ActiveCampaign or Mailchimp for legacy sequences) and build an export pipeline. Export surface likely HTML (rendered email body) + metadata (sequence name, send date, audience tag). Integrates with `blog_loader.py`'s `extract_plain_text_from_html` helper for body rendering — existing BeautifulSoup utilities from #56 are reusable.
**Spend:** $0 for handler; ~$0.01-0.05 for smoke ingestion depending on corpus size.
**Risk:** Medium. Depends heavily on which platform is authoritative and what API/export is available.
**Effort:** ~2 hr platform discovery + ~3-4 hr handler + test. Single-sequence smoke before bulk.

~~Option A (prior) — #56 HTML handler + blog pipeline~~ — **✅ shipped s28-extended.** `ingester/blog_loader.py` (411 lines) + 23 synthetic tests (passing) + single-post smoke (Indoor Air Pollution post, 5 chunks committed). Bulk ingestion deferred to #75 pending consumer (agent retrieval config) or cross-domain dedup design (#68).

### Option B — #45 Remove stale `client_rfids` from `rf_coaching_transcripts` (MED)
**Scope:** Tactical cleanup. The `client_rfids` field on all 9,224 coaching chunks contains values from an unfinished RFID system. Remove via upsert-with-metadata-minus-field. Add a verification probe showing zero chunks retain the field.
**Spend:** $0. Wall clock ~30 min.
**Risk:** Low-Medium (metadata edit on live collection). Zero chunk-count change expected; zero content change expected.

### Option C — #21 folder-selection UI redesign + collection-expansion UI
**Scope:** Both tickets compound now — #21's original pending-panel/tree redundancy fix overlaps with #46's per-item review workflow and the need to surface 13 collections as `library_assignments` targets (vs today's 2). Treat as one coherent UI scope. Significant effort — probably 2 sessions.
**Spend:** $0. Wall clock ~60-90 min for a scoped vertical slice (one sub-surface at a time).
**Risk:** Low (UI only).

### Option D — #49 Two-tier access framing decision
**Scope:** ~15 min Dan conversation to decide whether to proceed with `rf_internal_knowledge` collection + agent-level allow-list. If yes, ~1 hr schema + agent-config plumbing.
**Spend:** $0. Wall clock 15 min–1.5 hr depending on decision.
**Risk:** Low.

### Option E — #47 Multi-modal ingestion handler (LARGE)
**Scope:** Multi-session design + build. Session 29 scope would be the design doc (not the build). Slide-deck alignment (Option β) vs frame-capture-plus-OCR (Option α), cost model per minute of video, retrieval-layer integration. Critical path for RF 2.0 BBT-trends feature.
**Spend:** $0 for design session. Build sessions will have cost estimates attached.
**Risk:** Medium — scope boundaries need discipline or it sprawls.

### Option F — F3 from s27 HANDOVER: `PersistentClient` guard (~30 min add-on)
**Scope:** Guard against silent empty-chroma auto-creation on wrong relative paths. s27's 30-minute drift-panic-investigation foot-gun. ~15 lines + test in `ingester/loaders/_drive_common.py` or shared helper.
**Spend:** $0. Wall clock ~30 min.
**Risk:** Very Low.

### Tech-lead rec

**A first** (#57 Email platform export — blog loader's HTML extraction helpers reusable; next big file-processing capability). Scope discipline: platform discovery first, then single-sequence smoke, defer bulk until consumer exists (same pattern as #56).

Then based on energy:
- **B (#45)** as a clean tactical win (RFID field cleanup, ~30 min, $0, mirrors the #44 migration pattern)
- **D (#49)** — two-tier access decision (Dan's call, strategic conversation, ~15 min if decision only)
- **F (PersistentClient guard)** — quick safety add-on, ~30 min, $0

**Alternative first pick — tactical cleanup day:** start with #45 (RFID cleanup) then #49 (two-tier access decision) then F3 (PersistentClient guard). All three together ~1.5 hr and retire three items.

If #57 email platform discovery surfaces blockers (no API access, export format unclear, etc.), pivot to **E (#47 multi-modal handler design doc)** — that's the next biggest file-processing capability in the backlog, and a design session is $0 value.

---

## Budget for session 29

- **$1.00 interactive / $25.00 refuse.**
- s28 spent: $0 (scope B) + $0 (scope A).
- s29 expected: $0 for A/B/C/D/F; Option E design-only also $0.

---

## Files NOT to touch (same as s27/s28)

- `chroma_db/*` — never edit directly
- `data/inventories/*.json`, `data/audit.jsonl`
- v1/v2/v3 loaders — out of scope unless specific item directs
- `rag_server/display.py` — s24 delivery; untouchable unless BACKLOG directs
- `config/nashat_*.yaml` — stable; no edit without A/B budget
- The three demoted plan docs (ARCHITECTURE, REPO_MAP, COACHING_CHUNK_CURRENT_SCHEMA)
- **NEW s28:** `docs/CONTENT_SOURCES.md` — treat as canonical; update only per Operating Model #7 governance trigger when a session changes a canonical-source decision

---

## End of session 29 prompt

s28 shipped **four scopes** in a single extended session: Railway sync (#42), CONTENT_SOURCES.md (#35), #44 migration, and #56 HTML handler + blog pipeline (code + single-post smoke). Session 29's biggest leverage options: **#57 Email platform export** (biggest remaining file-processing capability, reuses #56 helpers), **#45 RFID cleanup** (quick tactical win), or a **governance cleanup day** (#45 + #49 + F3 together). Good luck.
