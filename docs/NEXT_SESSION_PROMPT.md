# NEXT_SESSION_PROMPT — session 8: Execute A4M migration + coaching Phase 1 backfill

> ## ⚠ ENVIRONMENT REQUIREMENT — READ FIRST ⚠
>
> **This session MUST run in Claude Desktop with the Desktop Commander MCP server enabled and loaded into the active chat.** You need bash/process execution tools (`Desktop Commander:start_process`, `bash_tool`, or equivalent) to run Python against live ChromaDB and to monitor long-running backfill processes. Filesystem tools alone are NOT sufficient to complete this session.
>
> **At the very start of the session, BEFORE reading anything, verify your toolset.** You should have all of:
> - Filesystem tools (`Filesystem:read_text_file`, `Filesystem:write_file`, `Filesystem:read_multiple_files`)
> - Some form of process/bash execution — either `Desktop Commander:start_process` / `Desktop Commander:read_process_output` / `Desktop Commander:interact_with_process`, OR a `bash_tool`, OR a `tool_search` you can call to load Desktop Commander.
>
> **If you only have Filesystem tools and no way to load process execution, STOP immediately and tell Dan: "I don't have process execution tools in this chat. Session 8 cannot execute without them. Please check the MCP server configuration for this chat and enable Desktop Commander, then restart the session."** Do NOT attempt to work around it by writing scripts you cannot run. Do NOT proceed past step 0.
>
> This warning exists because session 7 ran in Claude Desktop without Desktop Commander loaded into that specific chat and could not run any code, including git. The solution is not "use the browser" (the browser is worse) — it is "ensure Desktop Commander is enabled for this specific Claude Desktop chat before starting."

---

**Purpose:** Execute Plan 1 (A4M chunks migration to ADR_006) and Plan 2 (`rf_coaching_transcripts` Phase 1 structural backfill) from session 7. Both plans are approved. This session writes the actual scripts, runs them in dry-run first, and — with explicit Dan approval at each gate — runs them for real against the local file artifacts and the local Chroma collection. Plan 3 (Phase 2 marker detection) is NOT executed this session; it is a dedicated later session.

Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`

---

## MANDATE (carried forward from session 7)

Claude holds tech-lead role on this build. Make tactical build decisions yourself — script layout, mapping conventions, validator shape, dry-run output format, error handling, helper-module internals. Bring to Dan only: strategic tradeoffs, irreversible operations, money spend decisions above ~$25, and anything crossing the RAG-system boundary into app/product/legal/business. The "can we fix this later?" test is the gate between tactical and strategic: reversible → you decide; requires re-embedding/re-ingest/rollback → flag to Dan.

Safety discipline stays tight. Tech-lead authority is not a license to skip gates:
- No Chroma writes without explicit Dan approval at the specific write moment
- No git push/commit/add without approval (Dan runs git; Claude suggests what to stage and what message)
- No Railway operations without approval (this session is local-only)
- No deletions without approval and a verified backup
- Dry-run before every write, every time
- First-touch of any live Chroma collection requires a manual eyeball-diff gate where Dan reviews sample before/after pairs before writing

Consistency across sessions is enforced by: governing docs in the repo (ADRs, ARCHITECTURE, REPO_MAP, HANDOVER, BACKLOG, DECISIONS), session-end commits with clear messages (Dan runs git, Claude suggests), handover entries that match what actually landed, and next-session prompts that match handover. When you find drift between memory and reality, flag it and correct it in the handover.

---

## HARD RULES (never violated)

- No ChromaDB writes beyond what Plan 2 explicitly authorizes, and only after Dan's gate approval at the specific write moment.
- No git push, no git commit, no git add — Dan runs git. Claude suggests the commit.
- No Railway deployments or operations.
- No deletions of any kind without explicit Dan approval and a verified backup. **This includes the 584 legacy A4M chunks — session 8 ONLY inventories them, does NOT drop them.**
- No Phase 2 marker detection on coaching chunks. Plan 3 is execution-in-a-dedicated-later-session.
- No A4M ingestion into `rf_reference_library` this session. Plan 1 produces the migrated JSON file only. The actual Chroma write to `rf_reference_library` is a subsequent session after the 584-legacy-drop decision lands.
- No edits to ADR_002, ADR_005, ADR_006, or `docs/ARCHITECTURE.md` unless execution reveals a gap in the contract. If you find a gap, STOP and bring it to Dan as a strategic concern before editing.
- Never reference Dr. Christina in any output.
- Exclude Kelsey Poe and Erica from any retrieval sample output (relevant for the Chroma peek in step 1).
- Dr. Chris stays internal only (diarization label, not surfaced).
- Public agent never touches `rf_coaching_transcripts`. Not directly relevant this session (no agent code written) but flagging for consistency.
- Credentials are ephemeral — never store API keys, tokens, or passwords in files or memory. If you encounter any credential values in any file, ignore them and do not summarize them.
- `create_file` writes to Claude's sandbox, not the Mac. Use `Filesystem:write_file` for anything that must land in the repo.

---

## AVAILABLE TOOLS

**Required tools for this session (see Environment Requirement above):**

1. **Filesystem tools** — for reading repo docs and writing scripts/docs to the Mac:
   - `Filesystem:read_text_file`
   - `Filesystem:write_file`
   - `Filesystem:read_multiple_files`

2. **Process execution tools** — for running Python against live ChromaDB and monitoring long-running backfills. You need at least ONE of these pathways:
   - **Desktop Commander MCP tools** (preferred): `Desktop Commander:start_process`, `Desktop Commander:read_process_output`, `Desktop Commander:interact_with_process`, `Desktop Commander:list_directory`. If these aren't in your initial toolset but `tool_search` is available, call `tool_search(query="start process bash desktop commander")` to load them.
   - **`bash_tool`** (if present) — equivalent capability, acceptable substitute.

**What to do if `tool_search` itself is not available and no process-execution tools are loaded:**

STOP. Do not proceed. Tell Dan: "I have Filesystem tools but no process execution pathway and no `tool_search` to load one. This chat's MCP server configuration needs Desktop Commander enabled. Please check Claude Desktop's MCP settings for this chat and restart."

**You do NOT need:** web search, image search, visualizers, or any other categories of tools.

---

## READING ORDER (do not deviate)

Budget: reads should consume ~25% of your context. Writes and script-iteration consume the rest.

1. `docs/REPO_MAP.md` — orient to current repo state. Pay attention to the "Code layout" section which locks the `ingester/` package structure.
2. `docs/HANDOVER.md` — **session 7 top entry only** (2026-04-13). This is the authoritative task spec: contains the full text of Plans 1, 2, and 3, the four cross-plan consistency decisions, the tech-lead mandate, and the session 8 task outline. Do NOT re-read earlier handover entries unless a specific question forces it.
3. `ADR_006_chunk_reference_contract.md` — load-bearing. Focus on §2 (universal schema + 48 marker flags), §2a (canonical naming), §5 (field matrix), §7 (phased backfill for coaching), §8 (marker detection guidelines + regex starter kit). Unchanged since session 6.
4. `ADR_005_static_libraries.md` — skim. Unchanged since session 6.
5. `ADR_002_continuous_diff_and_registry.md` — **addendum section only** at the bottom, dated 2026-04-12. Skip the 2026-04-11 body.
6. `docs/ARCHITECTURE.md` — skim the chunk metadata schema and ingestion paths sections only.
7. `data/a4m_transcript_chunks_merged.json` — just head peek (first 1–2 chunks) to re-confirm the existing flat-metadata shape. Do NOT dump the whole 353-chunk file.

**Skip deliberately:**
- BUILD_GUIDE (covered by ADR_006 §6 reconciliation)
- HANDOVER entries before session 7
- ADR_001, ADR_003, ADR_004
- INCIDENTS.md (unless a credential issue surfaces)
- Earlier next-session prompts

If you find yourself re-reading ADR_006 more than once, stop — the session 7 HANDOVER entry is authoritative for this session's needs and you should be working from it rather than re-deriving from the source ADRs.

---

## TASK ORDER (execute in this sequence, stop at each gate)

### STEP 0 — Environment and tool verification (HARD PRECONDITION)

Before reading anything else, before loading any docs, **verify your toolset** per the Environment Requirement at the top of this doc and the AVAILABLE TOOLS section.

Specifically:

1. **Enumerate what you actually have.** List the tool names available in your current toolset. Do you have Filesystem? Do you have any form of process execution (Desktop Commander, bash_tool, or similar)? Do you have `tool_search`?

2. **If process execution is missing AND `tool_search` is available:** call `tool_search(query="start process bash desktop commander")` to attempt to load Desktop Commander into your toolset. Verify afterward that you now have `Desktop Commander:start_process` or equivalent.

3. **If process execution is missing AND `tool_search` is not available:** STOP. Tell Dan the specific tool names you do and do not have, and that session 8 cannot execute without process tools. Do not proceed to step 1. Do not start writing scripts you cannot run. Do not "plan around" the missing tools — session 7 already did the planning; session 8 exists to execute.

4. **If process execution IS available:** do a quick smoke test to confirm it works. Run `echo "session 8 tool check $(date -u +%Y-%m-%dT%H:%M:%SZ)"` or equivalent. If the command succeeds and you see the expected output, you are cleared to proceed.

5. **Verify filesystem access** to `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone` (the repo) and `/Users/danielsmith/Claude - RF 2.0/chroma_db/` (the Chroma DB). Confirm the repo is on branch `main` with a clean working tree before making any changes — if it's not clean, STOP and tell Dan what's uncommitted. (Run `git status` via your process tool.)

**Only after all five checks pass do you proceed to step 1.**

---

### STEP 1 — Coaching chunk schema inventory (GATE 1)

**Why this comes first:** Plan 2's field mapping has several cells that depend on the actual current metadata shape of the coaching chunks. That shape is not documented anywhere in the repo; it exists only in the live Chroma DB. This step produces the doc that Plan 2 consumes.

**Write** `scripts/peek_coaching_schema.py` — a **strictly read-only** Python script that:
- Connects to the local Chroma at `/Users/danielsmith/Claude - RF 2.0/chroma_db/` via `chromadb.PersistentClient`
- Opens the `rf_coaching_transcripts` collection
- Reports `coll.count()` (expected: 9,224)
- Pulls 5 sample chunks via `coll.get(limit=5, include=["metadatas", "documents"])`
- Prints: total count, the set of metadata keys observed across all 5 samples, and each sample's full metadata dict (redacted: if any sample's metadata contains Kelsey Poe / Erica / Dr. Christina names, mask them in the printed output — never to disk)
- Calls **no write methods** under any code path

**Run** the script via `Desktop Commander:start_process` (or equivalent process tool). Capture stdout.

**Write** `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` capturing:
- Exact count (confirming 9,224 or noting the discrepancy)
- Field inventory: each metadata key, its inferred type, a sample value, and a note on null rate if detectable from the sample
- Sentinel verification: confirm no `client_rfids` or `client_names` fields are populated (post-2026-04-10 wipe verification)
- Sentinel verification: confirm no `marker_*` flags are already set (re-run-after-Phase-2 trap guard)
- A "Plan 2 mapping resolution" section that fills in the specific source keys for: `source_id` / `source_name`, `chunk_index`, `speaker` (if present), `topics` (if present), `recommendations_given` (if present), and the list of existing keys that route to `type_metadata_json`

**Do not modify the Chroma DB in any way during this step.**

**GATE 1:** Show Dan the inventory doc. Wait for approval before proceeding to step 2.

---

### STEP 2 — Build shared ingestion infrastructure (GATE 2)

**Why this comes before any migration/backfill script:** every loader and backfill shares this infrastructure. Building it once, up front, ensures Plans 1 and 2 are consistent with each other and with all future loaders. This is the "one of each, shared everywhere" consistency mechanism from session 7's cross-plan decisions.

Create, in this order:

**(a) `ingester/marker_detection.py`**
- `CANONICAL_FLAGS: list[str]` — the 48 flag names from ADR_006 §2a, in order
- `MARKER_PATTERNS: dict[str, re.Pattern]` — compiled regexes, one per flag name, case-insensitive, word-boundary-anchored, leaning inclusive-recall. Use ADR_006 §8's starter kit as the seed; expand to all 48.
- `COLLISION_MARKERS: set[str]` — the collision set from session 7 Plan 3: `marker_ft3`, `marker_ft4`, `marker_iron`, `marker_iron_saturation_pct`, `marker_transferrin_sat`, plus any marker whose canonical form is ≤3 characters without strong word-boundary context
- `detect_markers(text: str) -> dict[str, bool]` — **always returns all 48 keys** as explicit booleans. This is the enforcement point for the "explicit false, not missing" rule. Never returns a partial dict.
- `detect_markers_hybrid(text: str, llm_client=None) -> dict[str, bool]` — **stub signature for now**. Plan 3 is deferred; this stub exists so Phase 2 can drop in without restructuring. Body can raise `NotImplementedError` if called. Document in the module docstring that Plan 3 is the session that implements this.
- Module docstring: document the T3/FT3, T4/FT4, iron/iron-saturation/transferrin collision handling explicitly so the next loader author knows why those markers are in `COLLISION_MARKERS` and what the regex decision is for bare T3 (doesn't match bare T3; bare T3 is not in the canonical marker list, so chunks mentioning only bare T3 leave thyroid flags false)

**(b) `ingester/backfills/_common.py`**
- `validate_adr006_record(record: dict, entry_type_expected: str | None = None) -> list[str]` — returns a list of violation strings (empty list = valid). Checks:
  - All 11 universal required fields present and non-null (`chunk_id`, `text`, `collection`, `library_name`, `entry_type`, `origin`, `tier`, `source_id`, `source_name`, `chunk_index`, `ingested_at`)
  - `entry_type` is one of the 10 locked enum values from ADR_006 §3
  - All 48 `marker_*` keys present and of type `bool` (not `None`, not missing)
  - For non-client entry types (`reference_transcript`, `reference_document`, `published_post`, `ig_post`): `client_id` and `linked_test_event_id` are explicitly present and set to `None` (not missing)
  - `type_metadata_json` is either a string or `None`, never a dict
  - If `entry_type_expected` is passed, the record's entry_type must match
- `build_chunk_id(library_name: str, entry_type: str, source_component: str, chunk_index: int) -> str` — returns `f"{library_name}:{entry_type}:{source_component}:chunk_{chunk_index:04d}"`. Zero-padded four-digit chunk index.
- `build_markers_discussed(flags: dict[str, bool]) -> str | None` — builds lowercase bookend-delimited string (`"|amh|fsh|tsh|"`) from the true-flagged keys (stripping the `marker_` prefix), or returns `None` if no flags are true
- `serialize_type_metadata(payload: dict) -> str` — `json.dumps(payload, ensure_ascii=False)`; validates the payload is a dict first
- `validate_unique_chunk_ids(records: list[dict]) -> list[str]` — returns a list of violation strings if any chunk_id is duplicated in the batch

**(c) `ingester/__init__.py` and `ingester/backfills/__init__.py`** — empty module init files so imports work. Also create `scripts/__init__.py` if scripts directory needs to be a package (probably not).

**GATE 2:** Show Dan the shared infra files. Wait for approval before running anything that uses them.

---

### STEP 3 — Plan 1 execution: A4M migration (GATE 3)

**Write** `ingester/backfills/migrate_a4m_to_adr006.py` per the full Plan 1 spec in the session 7 HANDOVER entry. Key constraints:

- Reads `data/a4m_transcript_chunks_merged.json` (353 chunks, read-only)
- Writes `data/a4m_transcript_chunks_adr006.json` (new file)
- Source file is never modified
- Default dry-run; `--write` flag required for real mode
- Preflight checks: count == 353, uniform `source_type == "transcript"`, all 10 expected existing keys present on every chunk
- Uses `detect_markers()` from `ingester/marker_detection.py` — this is the first import-consumer of that module
- Uses `build_chunk_id()`, `build_markers_discussed()`, `serialize_type_metadata()`, `validate_adr006_record()`, `validate_unique_chunk_ids()` from `ingester/backfills/_common.py`
- Explicit `client_id: None`, `linked_test_event_id: None` on every record
- QPT flags (`qpt_01`–`qpt_25`) omitted entirely (not set to false)
- `type_metadata_json` preserves existing `start_time`, `end_time`, `speakers` (as `speakers_raw`), `word_count` alongside the `reference_transcript` standard fields
- Validation pass on all 353 built records before writing; bail on any violation
- Dry-run summary: per-source-file counts, marker flag histogram (how many chunks set each flag to true), sample 3 before/after record pairs, validator result

Run the script in **dry-run mode first** (no `--write` flag). Show Dan the summary output.

**Also** during this step, perform the read-only inventory of the **584 legacy A4M chunks in `rf_reference_library`** — this is the session 7 drop-and-re-ingest verification step. Write a small read-only script `scripts/inventory_legacy_a4m_chunks.py` that:
- Opens `rf_reference_library` in the local Chroma
- Counts total chunks
- Samples 5 chunks with their metadata
- Enumerates unique `source_file` (or equivalent) values across the whole collection
- Reports total document text length (rough token count proxy)

Run it. Capture output into `docs/A4M_LEGACY_CHUNKS_INVENTORY.md`. Compare against the 353 merged JSON's coverage in a "Comparison" section:
- Does the 584-chunk collection cover source files the 353 doesn't? (Enumerate.)
- Does the 584-chunk collection appear to have substantive text the JSON is missing? (Rough token-count comparison.)
- If either answer is yes, **flag for Dan** with specifics before any drop is contemplated.

**GATE 3:** Dan reviews both artifacts — the Plan 1 dry-run output and the legacy-chunks inventory doc.

- If the dry-run looks right and the legacy inventory shows no surprises: Dan approves, re-run with `--write` to produce `data/a4m_transcript_chunks_adr006.json`.
- If the dry-run needs adjustments: fix the script, re-dry-run, back to Dan.
- If the legacy inventory shows surprises (coverage gaps, unexpected source files, substantially more text than the JSON): **STOP**, surface the specifics, do not run `--write` on Plan 1 until Dan decides whether the A4M migration is still the right foundation.

**Do NOT drop the 584 legacy chunks this session.** The drop is a subsequent session's work and requires a backup + its own approval gate.

---

### STEP 4 — Plan 2 execution: coaching Phase 1 structural backfill (GATE 4)

**Write** `ingester/backfills/backfill_coaching_phase1_structural.py` per the full Plan 2 spec in the session 7 HANDOVER entry. Key constraints:

- Reads `rf_coaching_transcripts` from local Chroma at `/Users/danielsmith/Claude - RF 2.0/chroma_db/`
- Default dry-run; `--write` flag required for real mode
- Preflight checks:
  - `coll.count() == 9,224` (bail on mismatch)
  - Field inventory matches `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` (bail if the live schema drifted from what step 1 captured)
  - Post-wipe sanity: no chunk has populated `client_rfids` or `client_names` (bail if any do)
  - Re-run-after-Phase-2 guard: no chunk has any `marker_*` flag set to True (bail if any do — prompts Dan to use `--force-reset-markers` if that's really what's wanted)
  - Backup verification: refuses to run in `--write` mode without a recent `chroma_db_backup_pre_phase1_backfill_YYYYMMDD`. Prints the exact `cp -r` command for Dan to run; does NOT perform the backup itself.
- Uses the shared `ingester/` infrastructure for chunk-ID synthesis (when re-synthesizing), validator, and all 48 marker flag defaults
- Writes: `entry_type="coaching_transcript"`, `origin="drive_walk"`, `tier="paywalled"`, `library_name="historical_coaching_transcripts"`, `collection="rf_coaching_transcripts"`, `source_id` derived from the filename-field per Option B (filename-based, NOT Drive file ID), `source_name` = same, `ingested_at="2026-04-12T00:00:00Z"` (sentinel — same on every chunk, never updates on re-run), `client_id=None`, `linked_test_event_id=None`, all 48 `marker_*` flags = `False` explicit, `qpt_*` omitted
- Preserves all existing metadata fields not in the top-level ADR_006 schema into `type_metadata_json`
- Read-only validator pass: builds all 9,224 updated metadata records in memory (~20MB), validates every record, and only begins writing if the full set validates. **No partial writes.**
- Resumable via progress file `backfill_phase1_progress.json` — checkpoint after each batch of 500
- Pre-write diff sample: prints 3 before/after pairs side by side, waits for an interactive keyboard confirmation before actually calling `coll.update()`
- Uses `coll.update(ids=..., metadatas=...)` to write — metadata-only, no touch to documents or embeddings

Run in **dry-run mode first**. Show Dan the summary output: count, validator result, sample diffs, marker-flag sanity (all False on every chunk).

**GATE 4:** Dan reviews the dry-run.

- If approved and the backup verification passes: Dan runs the backup command, confirms the backup exists, then instructs Claude to re-run with `--write`.
- Launch the write phase via `Desktop Commander:start_process` so it survives any MCP timeout. Monitor progress via the checkpoint file + `ps aux` rather than blocking tool calls on the long-running operation.
- If the write runs clean: verify post-run state via a read-only `coll.get(limit=3)` peek and confirm all 48 marker flags are present as explicit False on the samples, universal required fields are populated, and `client_id` is explicit None.

---

### STEP 5 — Session 8 close

**Append a new top entry to `docs/HANDOVER.md`** (session 8, 2026-04-XX) summarizing:
- What actually landed (file list + short description per file)
- Any deviations from Plans 1 and 2 as written in session 7 (none expected, but flag any)
- Updated collection state: `rf_coaching_transcripts` now Phase-1-compliant (9,224 chunks with ADR_006 universal fields + all 48 marker flags = False), `rf_reference_library` unchanged but inventoried, `a4m_course` ready for ingestion pending the legacy-drop session
- New backlog items or strategic concerns raised during execution
- The specific state of Gates 1–4 (approved / modified / paused)
- Next session's task: A4M ingestion into `rf_reference_library` (first Chroma write to that collection), including the 584-legacy-chunk drop with pre-drop backup and its own approval gate. OR: if the legacy inventory surfaced surprises, the next session's task is whatever resolves those.

**Update `docs/BACKLOG.md`** with any new items.

**Prepare a git commit summary for Dan.** A suggested commit should be multi-line, specific, no "update stuff" garbage. Example shape (do not copy verbatim — customize based on what actually landed):
```
Session 8: Execute A4M migration (Plan 1) + coaching Phase 1 backfill (Plan 2)

Infrastructure:
- Add ingester/marker_detection.py (48 canonical flags, regex patterns, collision set)
- Add ingester/backfills/_common.py (ADR_006 validator, chunk_id synthesis, shared helpers)

Plan 1 — A4M migration to ADR_006:
- Add ingester/backfills/migrate_a4m_to_adr006.py
- Produce data/a4m_transcript_chunks_adr006.json (353 chunks, ADR_006 conformant)

Plan 2 — rf_coaching_transcripts Phase 1 structural backfill:
- Add ingester/backfills/backfill_coaching_phase1_structural.py
- Local Chroma rf_coaching_transcripts: 9,224 chunks now ADR_006 structural-compliant
  (all 48 marker_* flags explicit False, awaiting Phase 2 detection)

Schema + inventory docs:
- Add docs/COACHING_CHUNK_CURRENT_SCHEMA.md (single source of truth for current shape)
- Add docs/A4M_LEGACY_CHUNKS_INVENTORY.md (584-chunk legacy verification for future drop)

Handover + backlog:
- docs/HANDOVER.md: append session 8 entry
- docs/BACKLOG.md: update per session 8 findings
```

**Present the commit summary to Dan. Dan runs git.** Do NOT run git yourself.

**Alternative: if the commit message is long, write it to `.session8_commit_msg.txt` at repo root via `Filesystem:write_file`, give Dan a one-liner `git commit -F .session8_commit_msg.txt`, and tell him to `rm .session8_commit_msg.txt` after. This is the pattern that worked at session 7 close when the editor paste went wrong.**

---

## CONTEXT DISCIPLINE

Session 7 burned significant context on the three plans. Session 8 is execution, which uses less reading and more writing. Budget: ~25% of context on reads (the session 7 HANDOVER entry is the biggest read), ~55% on script writing and dry-run iteration, ~20% reserve for debugging and session-close.

Specific cautions:
- Do not re-read ADR_006 more than once. The session 7 HANDOVER entry is authoritative for session 8's needs.
- Do not re-read earlier HANDOVER entries unless a specific question forces it.
- Do not re-derive Plan 1 or Plan 2 — they are locked and the session 7 HANDOVER entry is the spec.
- If a new question comes up that was not answered in session 7, stop and ask Dan rather than guessing — Dan's tech-lead mandate to Claude is "make tactical calls confidently; bring strategic tradeoffs to me." An unanticipated question is a signal to check which category it falls into.

---

## QUICK REFERENCE — key paths and names

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/`
- A4M source chunks (input): `data/a4m_transcript_chunks_merged.json`
- A4M output chunks (created this session): `data/a4m_transcript_chunks_adr006.json`
- Coaching collection: `rf_coaching_transcripts` (9,224 chunks expected)
- Reference library collection: `rf_reference_library` (584 legacy chunks expected, inventoried not dropped this session)
- Library name for coaching chunks: `historical_coaching_transcripts`
- Library name for A4M: `a4m_course`
- `ingested_at` sentinel for Phase 1 coaching: `2026-04-12T00:00:00Z`
- Backup name template: `chroma_db_backup_pre_phase1_backfill_YYYYMMDD`
