# NEXT SESSION PROMPT — session 29

## ⚠ CRITICAL: s28 drift recovery applies — mandatory reading before any scope pick

s28-extended scope F surfaced significant alignment drift between s28 scopes A/C/D/E and the canonical architecture decided in ADR_001–006. Before ANY new scope work, read the drift analysis and align.

**Mandatory s29 pre-work, in order:**

1. Read `docs/2026-04-17-drift-recovery-s28.md` in full. This is the drift-analysis doc — covers what went wrong, what the canonical architecture actually is (ADR_002's 4-collection + 15-library model), what schema compliance requires (ADR_006's 48 marker flags + 7 universal fields), and what s29 has to fix.

2. Read `ADR_001_drive_ingestion_scope.md`, `ADR_002_continuous_diff_and_registry.md` (including 2026-04-12 addendum), `ADR_005_static_libraries.md`, `ADR_006_chunk_reference_contract.md`. **These take precedence over anything in `CONTENT_SOURCES.md` or the s28 HANDOVER entries where they conflict.** `ADR_003_canva_dedup.md` + `ADR_004_folder_selection_ui.md` are DECIDED-in-principle with detail deferred; skim to know they exist.

3. Read `HANDOVER_INTERNAL_EDUCATION_BUILD.md` sections "What is already decided (do NOT re-litigate these)" + "The three Google Drive source folders" + "Collection architecture and metadata schemas" + "The ingestion pipeline — end to end" + "Session-by-session build plan". This is the April-10 master plan; the April-11/12 ADRs refine it but don't replace it.

4. Read `docs/CONTENT_SOURCES.md` — has a **DRIFT NOTICE banner at top** identifying what's misaligned. Treat as informational input (the per-domain source mapping is useful) not as canonical architecture.

5. Read `docs/STATE_OF_PLAY.md` CURRENT STATE — has the corrected 4-collection architecture table after s28 scope-F cleanup.

6. Read `docs/HANDOVER.md` session 28 entries (6 scope entries total: B, A, cont., extended/C, extended cont./D, extended cont./E, extended F drift recovery). Scope F is the most recent and explains the drift finding.

7. Then proceed to Step 0 below.

**No new canonical schemas, new collections, or new ingester architecture may be written in s29 without first acknowledging how the new work conforms to ADR_002/005/006 (or formally supersedes them via a new ADR).** This is the primary drift control introduced s28-scope-F.

> **tl;dr on s28:** SIX scopes landed. **B/A/C/D/E** shipped infrastructure (Railway sync, CONTENT_SOURCES.md, rf_published_content migration, blog_loader, ac_email_loader + classifier). **Scope F (drift recovery)** caught that scopes A/C/D/E contradicted ADR_001–006: proposed 13 collections instead of the 4-collection + 15-library model; 14 committed chunks lack ADR_006's universal schema including 48 required marker flags; two new loaders ran locally despite the master plan saying "no more local ChromaDB runs." The content is valid; the architecture framing was wrong. **s29's primary scope is alignment** — see Step 2 below.

---

## OPERATING MODEL — carries forward from s27/s28, + new rule #8 (s28 scope F)

All seven rules from s27 apply (read `docs/NEXT_SESSION_PROMPT_S27.md` sections OPERATING MODEL + ALL FLIGHT RULES). Anti-goals unchanged except as noted below. Cost gates unchanged ($1.00 interactive / $25.00 refuse / $0.15 live-A/B floor). Governance update triggers (#7) active.

### NEW rule #8 (s28 scope F) — predecessor-canonical-doc reading required

**Before writing or amending any doc that will be referenced as "canonical source of truth"** (CONTENT_SOURCES, CHUNK_SCHEMA, ingestion architecture specs, new ADRs), read all predecessor canonical docs — at minimum ADR_001–006, `HANDOVER_INTERNAL_EDUCATION_BUILD.md`, and any doc flagged as canonical in STATE_OF_PLAY's "Governance model" section. **Include explicit `Supersedes:` / `Aligns with:` / `Complements:` headers** on any new canonical doc. A doc that contradicts an ADR without explicit supersession is a governance violation.

Triggering conditions — read predecessors BEFORE writing any of these:
- A doc named `docs/CONTENT_SOURCES.md`, `docs/CHUNK_SCHEMA.md`, or similar architecture-level names
- A new `docs/ADR_NNN_*.md` file
- A proposed new collection in Chroma (not a new library within an existing collection)
- A proposed schema change to chunks (new required metadata fields, renaming existing fields)
- A significant amendment to `HANDOVER_INTERNAL_EDUCATION_BUILD.md`

### NEW anti-goal (s28 scope F)

- **NO new canonical schemas or collection architecture without reading ADR_002, ADR_005, ADR_006 first.** This is the specific case that drifted in s28.

### s28 context-window recalibration (from scope D close, unchanged)

Dan is using Claude Code with 1M context window enabled. Operating Model #6 context thresholds (30% warning / 20% wrap) were written against a 200K baseline. At 1M, the equivalent absolute thresholds are ~240K remaining (warning) / ~200K remaining (wrap-and-write-next-prompt). Claude should report context percentage against the active window, not the 200K default.

### Flight rule (s28 scope E, unchanged)

`load_dotenv(override=True)` required for any script reading secrets from `.env` — shell-exported empty strings silently win over `.env` values with default `load_dotenv()`.

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
- rf_published_content = **14** (8 migrated per #44: 7 Egg Health + 1 Sugar Swaps; 5 blog chunks per #56 smoke: Indoor Air Pollution post 18885; 1 AC email chunk per #57 smoke: msg 3 "[10 Steps Download Inside] Welcome")
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

Has a ⚠ DRIFT NOTICE banner at top (added s28 scope F). Verify banner is present before treating any collection architecture in this doc as authoritative. Rewrite scheduled for s29.

### 0.6 — NEW s28-F — ADR-alignment sanity check (Step 1.5 5th item)

Grep ADR_002 starter library list + ADR_006 collection names. Verify every collection referenced in the current BACKLOG / CURRENT STATE / CONTENT_SOURCES.md exists in the ADRs or has an explicit supersession commit. Current known non-compliant items (from scope F drift finding, all documented):

- BACKLOG #50-#55 propose "new collections" that are actually libraries per ADR_002 — marked superseded in BACKLOG triage
- 14 chunks in `rf_published_content` lack ADR_006 schema — scheduled for s29 metadata backfill
- `ingester/blog_loader.py` + `ingester/ac_email_loader.py` emit non-compliant schema — scheduled for s29 rework

If you see a NEW drift (not in this list), surface to Dan before proceeding.

---

## Step 1 + 1.5 — same pattern as s28

Default reading: CURRENT STATE section of STATE_OF_PLAY + HANDOVER s28 entries (both) + CONTENT_SOURCES.md in full. Quick-check on plan-docs + ADR status + drift markers. Full audit due **s31** (every 5 sessions, last full = s26).

---

## Step 2 — scope options

### PRIMARY SCOPE (strongly recommended): **s29-A — Drift alignment**

The drift found s28-scope-F must be addressed before any new forward motion. This is not optional if we want the ingestion work to be coherent long-term.

**s29-A.1 — Rewrite `CONTENT_SOURCES.md` to align with ADR_002/005/006.** Keep the per-domain source mapping (blogs → WP REST, emails → AC/GHL, lead magnets → PDF vs Google Doc, etc.) — that content is useful — but re-express in the 4-collection + 15-library vocabulary. Add explicit `Supersedes:` headers acknowledging the original s28 v1.0. Cross-reference ADRs at every architectural decision. ~2 hr.

**s29-A.2 — ADR_006 schema backfill on the 14 committed chunks in `rf_published_content`.** Metadata-only Chroma upsert, mirrors the #44 migration pattern. Per-chunk: set `entry_type` (`published_post`), `origin` (`static_library` — REST API pulls are static-library-adjacent until a new ADR defines `rest_api` as a third origin), `tier` (`published`), correct `library_name` (`blog_posts` / `lead_magnets` / `nurture_emails`), `source_id` (per ADR_002 addendum format), and the **48 marker flags** via regex detection on chunk text. Zero embed cost. ~1-2 hr including test.

**s29-A.3 — BACKLOG re-triage.** Close #50-#55 (collection-creation items that are actually library-creation; superseded). Keep #73, #75, #78 (bulk-ingest items; unchanged). Keep #76, #77 (still valid). Triage #62-#72 against ADR_002/005/006. ~30 min.

**s29-A.4 — Schema fix in `blog_loader.py` and `ac_email_loader.py`.** Update both to emit ADR_006-compliant metadata on new ingestions (not just the backfilled chunks). ~1 hr.

**s29-A.5 — New ADR for REST-API-origin ingestion** (if Dan greenlights). Define `origin: rest_api` as a third value alongside `drive_walk` and `static_library`. Covers blog_loader, ac_email_loader, future ig_post_loader. ~1 hr ADR draft.

**Total s29-A: 5-6 hr, $0 LLM, significant cleanup value.** After s29-A, the codebase is honestly aligned with the ADRs and master plan, and we can proceed to master-plan-Session-2 work (FKSP pilot) with a clean architectural conscience.

### Alternative scopes (only if drift is acknowledged but Dan wants to defer)

#### s29-B — Master plan Session 2: FKSP pilot (Pipeline A video + Pipeline C PDF)

Per master plan April 10: validate the video + PDF pipelines on ONE FKSP video + ONE FKSP PDF before scaling. Produces the first chunks in `rf_internal_education`.
**Requires:** either (a) doing s29-A first so new ingesters emit compliant schema, or (b) emitting compliant schema from day one in the new Pipeline A/C scripts (more disciplined). Either way, s29-A is the right sequence.
**Spend:** design $0; pilot ingestion ~$0.10-0.50 (Gemini vision for PDF, OpenAI embeddings).
**Effort:** ~4-5 hr.

#### s29-C — #45 RFID cleanup (tactical quick win)

Strip stale `client_rfids` from 9,224 coaching chunks. Mirrors #44 migration pattern. ~30 min, $0. Can pair with s29-A.3 triage as a cleanup sub-day.

#### s29-D — F3 PersistentClient guard + #49 two-tier access decision

Retires two small items. ~1 hr combined. Pair with s29-A if a tactical win is wanted alongside alignment work.

### NOT recommended for s29

- Any "ship new file-processing capability" scope (IG loader, Canva loader, new handler) until s29-A lands — would compound the schema drift
- #75 bulk blog or #78 bulk AC — both need s29-A.4 compliant loaders first
- #56/#57-style smoke commits of new content — same reason

### Tech-lead rec

**s29-A, sequenced.** Specifically: A.1 (rewrite CONTENT_SOURCES) first because it's the doc that future work references, then A.2 (schema backfill) because it removes the largest single source of technical debt, then A.3 (BACKLOG triage) as close-out. A.4 (loader schema fix) and A.5 (new ADR for REST origin) can split to s30 if s29 runs long.

If you want to pair a tactical win with alignment: **s29-A + s29-C (RFID cleanup) as a single "governance + cleanup" session.** Both are metadata-only Chroma upserts — same pattern — and they compound nicely.

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

s28 shipped **six scopes** including scope F drift recovery. Scopes B/A/C/D/E built real infrastructure (Railway sync, CONTENT_SOURCES.md, rf_published_content migration, blog_loader, ac_email_loader + classifier, 5 git commits, 15-script regression suite green). Scope F identified alignment gaps with ADR_001–006 and documented them honestly without destructive undo.

**s29's mandatory first move is scope s29-A (drift alignment).** Anything else compounds the technical debt.

**s29-A deliverables:**
- Rewritten `CONTENT_SOURCES.md` v2.0 aligned with ADR_002's 4-collection + 15-library model
- ADR_006 metadata backfill on the 14 committed chunks in `rf_published_content`
- BACKLOG re-triage closing superseded collection-creation items
- Schema fix in `blog_loader.py` + `ac_email_loader.py` so future ingestions are compliant
- (Optional) New ADR defining `origin: rest_api` for REST-API-pull ingesters

Only after s29-A lands should master plan Session 2 (FKSP pilot) begin. Good luck.
