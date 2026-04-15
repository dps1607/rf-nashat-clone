# STATE OF PLAY — corrected current-state document

**Written:** 2026-04-13 (session 9, stabilization session)
**Amended:** 2026-04-13 (session 10, drive loader pilot — see § "Session 10 amendment" near the bottom)
**Supersedes orientation in:** `docs/HANDOVER.md` session 7 entry, `docs/NEXT_SESSION_PROMPT.md`, large parts of `docs/REPO_MAP.md` and `docs/ARCHITECTURE.md` that describe local Chroma as primary
**Earlier handover entries:** preserved as history; do not drive next-session work
**Status:** Authoritative orientation surface for sessions 10+

---

## What we shipped and what it does

There is a real, deployed product running at **https://console.drnashatlatib.com**, gated by Cloudflare Access, allowing two users (Dan and Dr. Nashat Latib) to log in via Google OAuth. It has been live since 2026-04-09.

The deployed stack:
- **Railway** project `diligent-tenderness`, service `rf-nashat-clone`
- **Two gunicorn processes** managed by honcho (`Procfile.honcho`):
  - `admin_ui/app.py` — public on the Cloudflare-fronted port; YAML config editor for `nashat_sales.yaml` and `nashat_coaching.yaml`, folder browser at `/admin/folders`, audit log viewer, inline test-query panel
  - `rag_server/app.py` — localhost-bound (no external port); answers test queries by retrieving from ChromaDB and generating with Claude Sonnet
- **ChromaDB on Railway's persistent volume** at `/data/chroma_db`, ~485 MB, two collections currently populated:
  - `rf_coaching_transcripts` — 9,224 chunks of FKSP coaching call transcripts
  - `rf_reference_library` — 584 chunks of A4M Fertility Certification course material (transcripts + slides + summaries) — see "What's actually in `rf_reference_library`" below
- **Audit logging** to `/data/audit.jsonl` on the persistent volume
- **Cloudflare Access** in front, doing JWT verification on every request via JWKS, allowlisting `dan@reimagined-health.com` and `znahealth@gmail.com`

**What a user can do today:** log in, open one of the two agent YAML configs, edit it, save it (with hot-reload picked up by the rag_server), browse the Drive folder tree of the 12 connected Shared Drives, run a test query through the admin UI's inline test panel and see real cited chunks come back from `rf_coaching_transcripts` and `rf_reference_library`. The deployed product works end-to-end on the read path.

**What a user cannot yet do:** drive the folder-selection UI through to an actual ingestion event. Folders can be browsed, but `data/selection_state.json` still contains placeholder data (`["abc", "def"]`) — no real folder has been assigned to a real library through the UI and run through an ingestion. The "save selections" button persists state, but no downstream ingestion trigger consumes that state.

---

## What's canonical where (the most important correction)

**Railway is canonical for what users touch.** The 2026-04-09 Phase 3.5 deploy uploaded a tarball of local Chroma to Railway via cloudflared quick tunnel (the playbook is documented in `HANDOVER_PHASE3_COMPLETE.md` "How chroma_db was uploaded"). After that upload, Railway became the live, user-facing data store. Nashat and other early users interact with the Railway copy.

**Local Chroma is a development sandbox.** It exists at `/Users/danielsmith/Claude - RF 2.0/chroma_db/`, contains the same data the April 9 tarball was built from (`rf_coaching_transcripts` 9,224 chunks + `rf_reference_library` 584 chunks), and is appropriate for: schema inspection, loader development, dry-runs of new ingestion logic, and any iterative work that should not touch what users are poking at. **Local has not been kept in sync with Railway since 2026-04-09** and should not be assumed to match production for anything other than the two collections that were uploaded.

**The workflow when local needs to become canonical** (i.e., when you want a local change to land in production): tarball + bootstrap upload via cloudflared quick tunnel, same playbook as the April 9 deploy. This is reversible, well-documented, costs about 6 minutes of wall clock time, and is the explicit pattern the system was built to support. Do not invent a new sync mechanism unless there's a strong reason — and there is not currently a strong reason.

**The framing in the session 7 HANDOVER and parts of REPO_MAP/ARCHITECTURE/HANDOVER_INTERNAL_EDUCATION_BUILD that describes "local primary, Railway sync deferred" is wrong.** That framing was inherited drift from low-context sessions and was not corrected before it shaped session 7's plans. It is corrected here. Do not re-derive Plan 1, Plan 2, or Plan 3 from the session 7 entry without re-reading this document first.

---

## What's actually in `rf_reference_library` (the 584 chunks)

The April 9 handover flagged the 584 chunks in `rf_reference_library` as "unexpected" and "mystery" because they predated the recorded ingestion plan. **They are not a mystery. They are a deliberate, well-built, polished A4M Fertility Certification reference library, and they are part of the live system serving Dr. Nashat and other early users.** They are not stale. They must not be dropped without an extremely good reason and a verified replacement path.

**Inventory** (captured 2026-04-13 via `scripts/peek_reference_library.py`):

- **584 total chunks**, ~1.58M characters, ~395K rough tokens, mean 2,704 chars per chunk
- **15 modules** of the A4M Fertility Certification course (modules 1 through 15)
- **15 distinct module topics**, each cleanly named (Epigenetics & Nutrigenomics, Fertility Assessment Female, PCOS and Infertility, Recurrent Pregnancy Loss, The Reproductive Microbiome, etc.)
- **5 named lecturers** with proper attribution across 513 of 584 chunks: Jaclyn Smeaton, ND (275 — the lead), Warner (90), Felice Gersh, MD (82), Espinosa (40), Uzzi Reiss, MD (26). The remaining **71 "Unknown"-speaker chunks** (36 transcripts + 27 slides + 8 summaries) are concentrated in **3 specific modules**: M3 (Fertility Assessment Male, 18 transcript), M5 (Case Study 1, 8 transcript), M10 (Case Study 2, 10 transcript). Modules 5 and 10 are *case study panels* where attribution is genuinely ambiguous; M3 likely has a lecturer name available in the slide deck but not propagated to transcripts. A targeted backfill for M3 would resolve the cleanest 18; the case study modules are intentional ambiguity.
- **3 source types** per module (with light per-module variation):
  - `transcript` — 263 chunks, raw transcribed lecture audio with `[HH:MM:SS]` timestamps and SPK_N speaker tags
  - `slides` — 269 chunks, extracted slide deck content with `[Slide N]` markers and `start_slide` / `end_slide` / `total_slides` metadata
  - `summary` — 52 chunks, distilled HTML/Google-Docs source material with inline `STUDY/STAT:` and `CLINICAL PEARL:` markers, accompanied by `has_clinical_pearl` and `has_study_reference` boolean quality flags
- **One small gap:** Module 15 has only 2 slide chunks. Looks intentional (it's a fertility cases module) but worth knowing.

**Metadata fields, all 100% populated across all 584 chunks:**
`chunk_index`, `content_type`, `course`, `module_number`, `module_topic`, `source_file`, `source_type`, `speaker`, `word_count`

**Metadata fields populated on subsets:**
- `start_timestamp` / `end_timestamp` — 315/584 (transcripts + summaries)
- `start_slide` / `end_slide` / `total_slides` — 269/584 (slides only)
- `has_clinical_pearl` / `has_study_reference` — 52/584 (summaries only)

**Chunk row ID format:** `a4m-m{module_number}-{source_type}-{NNN}` (e.g., `a4m-m10-transcript-001`, `a4m-m14-summary-002`, `a4m-m15-slides-001`). Stable, readable, deterministic.

**Implication for the session 7 plans:** the Plan 1 + drop-and-re-ingest-the-584 plan from session 7 was built on the false premise that `data/a4m_transcript_chunks_merged.json` (353 chunks, transcripts only) was the source of truth and the 584 was stale. The reverse is true: the JSON is a stale intermediate from an earlier chunking pass; the 584 is the result of substantial follow-on work (slide extraction, summary enrichment, speaker attribution, quality flagging) that is not present in the JSON at all. **Executing Plan 1 as written would have silently destroyed the 269 slide chunks and 52 summary chunks** because they have no source-of-truth in the JSON. This was caught by the session 9 stabilization, not by the planning sessions.

### Two parallel A4M ingestion lineages: which one won and why

There are **two completely separate A4M ingestion attempts** in the repo, and only understanding both explains the metadata mess.

**Lineage A — `ingest_a4m_transcripts.py` → `merge_small_chunks.py` → never-ingested JSON files.** Built 2026-04-12 (per HANDOVER.md "A4M full batch — COMPLETE" entry). `ingest_a4m_transcripts.py` adapted the v3 LLM-chunking pipeline (`rag_pipeline_v3_llm.py`, originally built for coaching Q&A calls) for A4M lecture content. Wrote `data/a4m_transcript_chunks_full.json` (452 chunks). The Q&A-tuned prompt produced sub-250w chunks on lecture content (the "small chunk" problem), so `merge_small_chunks.py` was written as a post-process pass that merges any chunk under 250w into its smaller neighbor, per-module, producing `data/a4m_transcript_chunks_merged.json` (353 chunks, mean 489w, min 252w). HANDOVER.md called this "the canonical file for ChromaDB ingestion." **It was never actually written to ChromaDB.** Module 14 of A4M required special handling in this lineage — the source transcript is unusually fragmented (17 words/block avg vs ~40 elsewhere) and the merge pass took it from 40 chunks at mean 181w down to 21 chunks at mean 345w. (**This is the "session 14 / merge chunks" memory you may carry forward.** The "14" refers to A4M Module 14, not session number 14, and the corpus is A4M lectures, not coaching Q&A. There has never been a coaching Q&A re-merge.)

**Lineage B — direct ingestion into `rf_reference_library`.** Built by some earlier or concurrent session whose handover entries are not visible in the repo (the April 9 Phase 3 handover called the 584 chunks "unexpected" and "mystery"). This lineage produced **transcripts, slides, and summaries** — three source types per module — with a chunking pass tuned for lecture content from the start. Median transcript chunk is **716 words** (vs Lineage A's 446w median); only 7 of 263 transcript chunks are below 250w (vs Lineage A's source `_full.json` having 15 chunks below 100w that needed merging). Lineage B's chunking is **higher quality for lecture content** because it was tuned for that content type, and it captures slide and summary material that Lineage A doesn't even attempt.

**The session 7 plans assumed Lineage A was canonical** because Lineage A's artifacts were visible in `data/` while Lineage B's were buried in ChromaDB and undocumented. **Lineage B is canonical** because it's the one that's actually serving Dr. Nashat in production. Lineage A's artifacts (`a4m_transcript_chunks_full.json`, `a4m_transcript_chunks_merged.json`, `a4m_transcript_chunks_pilot.json`, `ingest_a4m_transcripts.py`, `merge_small_chunks.py`) are **dead code from an abandoned attempt that nobody removed**. They should be archived to `data/_archive/` with a README explaining why, in a future small cleanup session. Do NOT delete them outright — they're useful as a reference for how the v3 chunking pipeline was adapted for non-Q&A content, in case that pattern is ever needed again.

### Coaching collection word-count distribution (observation only, not a problem)

For reference, the live 9,224-chunk `rf_coaching_transcripts` collection has the following word-count distribution (verified read-only against local Chroma, 2026-04-13):

- min: 30w, p10: 291w, **median: 564w**, p90: 652w, max: 2891w, mean: 573w
- 267 chunks below 100w
- 515 chunks at 100–249w
- 7,915 chunks at 250–999w (the bulk)
- 527 chunks at 1000w or larger

**This is the production state of v3 LLM chunking. It is not a known problem.** A previous draft of this section (and the original session 9 BACKLOG entry) framed it as "the same small-chunk problem `merge_small_chunks.py` was built to fix on A4M, never run on coaching." That framing was wrong and is corrected here.

**Why no merge pass should be applied to this corpus:**

1. `merge_small_chunks.py`'s `FLOOR=250` was tactical for A4M lecture content, not a generally-applicable rule.
2. The v3 chunker's `<150w merge escape hatch` for Q&A boundaries was a prompt-engineering parameter, not a quality threshold.
3. Q&A in fertility coaching is typically long-form (Dr. Nashat explaining lab results, walking through protocols). Short chunks are likely clean topic transitions or brief coaching moments, not over-fragmented content. Forcing a numeric floor would merge chunks that should stay separate.
4. The right rule is "whatever chunk size makes the chunk a coherent retrievable unit," which is a per-chunk LLM judgment that the v3 chunker already makes.

**If a real retrieval-quality failure surfaces** (e.g., "this query returned a 30-word chunk that was meaningless out of context"), investigate that specific chunk and decide what to do with it. There is no global fix. No corpus-wide merge pass. The "session 14 / Q&A re-merge" memory in earlier handover material was a conflation of two unrelated things — the v3 prompt rule for Q&A boundaries, and the A4M Module 14 rescue — neither of which generalizes to a coaching-collection merge pass.

This observation is captured in BACKLOG.md as a "no action item" for the same reason: future sessions should know the distribution exists, and should know not to "fix" it.

---

## The actual goal (one paragraph)

The folder-selection UI in `admin_ui/` lets a real user point at a folder in Google Drive, hit "ingest into library X," and have those chunks become queryable through the same agent that already serves coaching transcripts and the A4M reference library — with metadata consistent enough across sources that the agent can render coherent citations and the LLM can see provenance regardless of which collection a chunk came from. That is the single thing the system needs to do next that it cannot do today.

---

## The minimum bar for "metadata consistent enough"

This is derived from reading `rag_server/app.py` directly, not from ADR_006.

**The deployed retrieval code reads exactly four metadata fields from chunks** (see `format_context()` in `rag_server/app.py` around line 230):

- From `rf_coaching_transcripts` chunks: `topics`
- From `rf_reference_library` chunks: `module_number`, `module_topic`, `speaker`
- (`text`, `distance`, and the source-collection name are universal and don't count as "metadata fields" in this sense)

**The actual consistency gap, expressed against this consumer:** when the agent retrieves a coaching chunk and a reference chunk in the same response, the reference chunk gets a header like `Module 7: PCOS and Infertility — Presenter: Felice Gersh, MD` and the coaching chunk gets `Topics: Vitamin D|Insulin/Blood Sugar` with no provenance, no date, no speaker, no source identifier visible to the LLM. **The LLM literally cannot tell where a coaching exchange came from.** Citations on the response side suffer the same problem.

**The minimum fix** is a small normalization that gives every chunk in every collection enough fields for the agent's `format_context()` to render a coherent header for it. Concrete shape:

| Normalized field | A4M reference source | Coaching transcript source | New library source (template) |
|---|---|---|---|
| `display_source` | `module_topic` | derive from `call_file` (e.g., "FKSP Q&A 2024-02-14") | filename or library-defined display name |
| `display_subheading` | `f"Module {module_number}"` | derive from `call_fksp_id` | section / chapter / page identifier |
| `display_speaker` | `speaker` | scrub `coaches` to safe form (drop excluded names) or `null` | author / speaker if known |
| `display_date` | `null` (A4M doesn't carry recording date) | parse from `call_file` if possible, else `null` | publication / capture date |
| `display_topics` | `module_topic` (single string is fine) | existing `topics` value, optionally cleaned | comma- or pipe-separated list |

Five normalized fields. None of them are boolean marker flags. None of them require a 48-flag universal contract. None of them require touching ADR_006. The fix can land as a small read-time helper in `rag_server/app.py` (zero Chroma writes) **or** as a write-time normalization at ingest time when new libraries land via the folder-selection UI (Chroma writes only on new ingestion, no backfill of existing collections required).

**The read-time helper is the lower-risk first move** because it costs zero Chroma writes, requires no backup, runs against both local and Railway identically (it's a code change, not a data change), and any new loader that writes the normalized fields directly is automatically forward-compatible. Recommended sequence: (1) build the read-time helper, (2) verify both collections render coherent citations through the deployed agent, (3) make sure new loaders write the normalized fields at ingest time so future libraries don't need a backfill pass.

---

## The metadata-consistency gap, in detail

For reference, here is the full field-level diff between the two collections that are actually in production. This is the actual "metadata consistency" problem you were trying to solve, sized correctly.

| Concept | Coaching collection | A4M reference library | Aligned? |
|---|---|---|---|
| Chunk text | `documents` | `documents` | ✅ |
| Filename / source identifier | `call_file` | `source_file` | different key name |
| Sequence in source | parsed from row ID `CHUNK-{file_idx}-{chunk_idx}` | `chunk_index` (proper field) | different storage |
| Time markers | `start_time` / `end_time` | `start_timestamp` / `end_timestamp` (transcripts); `start_slide` / `end_slide` (slides) | different key names; slides need a different concept entirely |
| Tags / topics | `topics` (free-form pipe-delimited, no bookends) | `module_topic` (single string) | different shape |
| Speaker | `coaches` (file-level, contains a guardrail-excluded name) | `speaker` (chunk-level, real lecturer names) | different shape; coaching's value is sensitive |
| Content sub-type | (none — assumed coaching call) | `source_type` ∈ {transcript, slides, summary} | A4M has it, coaching doesn't |
| Course / collection | (none) | `course` | A4M has it, coaching doesn't |
| Word count | `word_count` | `word_count` | ✅ |

**Eight misalignments. None are about the 48 marker boolean flags from ADR_006.** Every one is solvable by the small read-time normalizer described above, plus a ~5-field convention for new loaders to follow at write time.

---

## What's not the goal right now (deferred work, not deleted)

The following are real ideas, captured in committed governing docs, **valid in their domains** but **not on the current critical path**. They stay where they are. They are not deleted. They are not driving next-session work.

- **ADR_006 universal chunk schema** (48 marker boolean flags + 25 QPT flags + 11 universal required fields). A defensible design for a system that needs structured marker filtering at retrieval time. The deployed retrieval layer does not currently filter on marker flags, does not read `marker_*` fields, and does not consume any of ADR_006's universal fields beyond what the existing collections already provide. ADR_006 becomes valuable when (a) the retrieval layer adds a feature that needs lab-marker filtering, AND (b) the regex-on-text approach at query time turns out to be insufficient. Neither has happened. Both are speculative.
- **Plans 1, 2, and 3 from session 7 HANDOVER.** Plan 1 (A4M migration to ADR_006) was built on the false premise above and would have destroyed real data; it is invalid as written. Plan 2 (rf_coaching_transcripts Phase 1 structural backfill) writes 11+48 fields to local Chroma that no consumer reads; it can be executed later if and when ADR_006 becomes load-bearing. Plan 3 (Phase 2 marker detection, LLM-assisted) is downstream of Plan 2 and inherits the same caveat.
- **The 25 QPT flags forward-compat spec.** Same argument: speculative until the QPT-aware loader exists, and there's no QPT-aware loader on the roadmap right now.
- **`markers_discussed` casing standardization, the cross-plan consistency decisions, the tech-lead mandate's "every loader must use the shared validator" enforcement clause.** These are coherent design ideas that presuppose Plan 2 has run. They become valid after Plan 2 runs, which itself is deferred.
- **The 584-chunk drop-and-re-ingest decision from session 7.** Explicitly reversed. The 584 chunks are the live A4M reference library; they are not dropped under any circumstances without a verified replacement that includes the slide and summary content that the JSON does not contain.
- **`VECTOR_DB_BUILD_GUIDE.md` §3G and §7 amendments.** Documentation alignment work. Not blocking anything user-facing.
- **ADR_002 file-record backfill for historical corpora.** Same — documentation/registry work that's downstream of features the deployed product doesn't need yet.

**To repeat: none of these are deleted.** The ADR documents stay in the repo as committed history. The session 7 HANDOVER entry stays intact. They are simply demoted from "the roadmap" to "a body of design work that may become valid later." The next-session work is driven by `STATE_OF_PLAY.md` (this document) and `NEXT_SESSION_PROMPT.md` (forthcoming).

---

## Honest post-mortem of the rabbit hole (for future sessions)

Two paragraphs. Read these if you are a future Claude session about to read the session 7 HANDOVER and feel inspired by the tech-lead mandate and the three-plan structure.

**What happened.** Between 2026-04-12 afternoon and 2026-04-13 morning, four sessions in a row (sessions 5, 6, 7, and the start of session 8) progressively expanded a real but small concern — "the A4M chunks I was about to ingest don't have the same metadata shape as the coaching chunks already in the system" — into a comprehensive universal chunk metadata contract (ADR_006), a same-day amendment to that ADR (replacing pipe-delimited markers with 48 boolean flags), a static-libraries ADR (ADR_005), an ADR_002 addendum for non-Drive file records, three written backfill plans (Plan 1 for A4M migration, Plan 2 for coaching Phase 1 structural backfill, Plan 3 for coaching Phase 2 marker detection), four cross-plan consistency decisions, a tech-lead mandate granting Claude tactical decision authority, and a session-8 execution prompt. Across all four sessions, **zero code shipped**, zero production state changed, and the actual deployed product (the folder-selection UI built in early-April sessions) sat with placeholder data in `selection_state.json` and a never-driven end-to-end ingestion path. None of the planning sessions verified their own premises against the actual deployed system, the actual contents of `rf_reference_library`, or the actual fields read by `rag_server/app.py`. Session 8's step 1 caught one small drift ("the wipe was empty-string, not key-removal") but did not catch the larger drift that the entire session 7 plan tree was operating on stale, partial, and partly-fictional information. Session 9's stabilization caught the larger drift, plus three additional ones uncovered while writing this document: (a) `data/a4m_transcript_chunks_merged.json` and friends are *Lineage A* of an abandoned A4M ingestion attempt, not the source of truth for the live `rf_reference_library`; (b) the live coaching collection has the same small-chunk distribution problem the A4M merge pass was built to fix, and the merge pass has never been run on it (see BACKLOG.md session 9 entry); (c) two parallel Claude sessions ran concurrently during session 9 against the same working tree, with the second session catching the first session's near-miss of overwriting the first session's good work — a second-order failure mode of the same trust-the-bootstrap-prompt pattern that produced sessions 5–8. The fix in both cases is the same: verify state before acting.

**The pattern to recognize.** When a low-context session inherits a vague concern and a clean architectural framing, the architectural framing is intoxicating because every step within it produces visible, internally-consistent progress. Three sessions of ADR work all looked like progress. None of it was. The check that would have caught this at any point was: **"verify the bootstrap prompt's premises against the actual system before reading the prompt's reading list."** Specifically: read the actual deployed code that consumes the data the architecture is about; read the actual contents of the data the architecture proposes to migrate; check the actual git history for what was last shipping before the architecture work started. None of those checks take more than 10 minutes and any one of them would have caught the drift. The tech-lead mandate, as written in session 7, did not include this check. **It does now**, in the session-10 next-prompt: at session start, before reading the bootstrap prompt's reading list, independently verify that the bootstrap prompt's description of the world matches the evidence on disk. If it doesn't, stop and raise the drift before doing any other work.

---

## Files inventoried during session 9 (read-only, no Chroma writes)

- `scripts/peek_coaching_schema.py` — created session 8, ran successfully against local Chroma, output captured in `docs/COACHING_CHUNK_CURRENT_SCHEMA.md`. Reusable.
- `scripts/peek_reference_library.py` — created session 9, ran successfully against local Chroma. Output is the inventory section of this document. Reusable.
- `docs/COACHING_CHUNK_CURRENT_SCHEMA.md` — created session 8, captures the current shape of `rf_coaching_transcripts`. Still accurate. Note: a previous "post-wipe state" claim in session 7 HANDOVER described `client_rfids` and `client_names` as "wiped/cleared" — actual on-disk state is the values are the literal string `"[]"`, not absent. Documented in COACHING_CHUNK_CURRENT_SCHEMA.md.
- `docs/STATE_OF_PLAY.md` — this document.
- `docs/NEXT_SESSION_PROMPT.md` — to be rewritten in session 9 to point session 10 at the UI thread (see next session prompt for details).

**No code outside `scripts/` was created or modified. No Chroma collection was written to. No git operations were run by Claude. No Railway operations were performed.**

---

## What the next session (session 10) should do

See `docs/NEXT_SESSION_PROMPT.md` for the full bootstrap. Short version: drive the folder-selection UI end-to-end with one real folder, building the read-time normalizer for citation rendering as a side quest if and only if it surfaces as the actual blocker. The metadata work from sessions 5–8 stays frozen. ADR_006 and the three plans stay in the repo as history.

---

## Session 10 amendment (2026-04-13) — drive loader pilot, dry-run only

Session 10 took Re-Scope B from its own staircase: ship the library-picker UI patch + the Drive content loader as code, exercise the loader in dry-run mode against one real folder, stop short of any actual ingest. Full session entry is in `docs/HANDOVER.md` under "Session 10". Full design rationale is in `docs/plans/2026-04-13-drive-loader-pilot.md`.

**What changed about the world (versus the body of this document above):**

1. **Gap 1 from the body of this doc — "save persists state, but no downstream ingestion trigger consumes that state" — is HALF closed.** The library picker now exists in the UI (`Pending Selections` panel + per-folder dropdown) and the save endpoint validates assignments. The "no downstream consumer" half of Gap 1 is now addressed by the loader (next bullet), but only in dry-run.

2. **The Drive content loader exists.** `ingester/loaders/drive_loader.py`. Reads `selection_state.json`, walks the selected folder via the existing `DriveClient`, exports Google Docs to plain text, chunks paragraph-aware, writes 21-field-per-chunk metadata including all 5 `display_*` normalization fields and the `source_folder_id` slicing key. **It has never been run with `--commit`.** Dry-run only as of session 10 end.

3. **The 5-field display normalization shape from this doc's "minimum bar for metadata consistent enough" section is now realized at ingest time** for any chunk the new loader writes. The future read-time normalizer in `rag_server/app.py:format_context()` will need to handle coaching and A4M chunks (which lack these fields) but can read drive-loader chunks through unchanged. The forward-compat decision was honored.

4. **One critical loader finding that's likely to bite session 11:** Drive's `text/plain` export of Google Docs is lossy. The pilot folder's largest file (4.3 MB by Drive metadata) exported to ~3 KB of text. Tables, images, and formatting do not survive. The v1 chunker is therefore functionally untested against multi-chunk content because every pilot file fit in a single chunk. A v2 loader probably needs HTML or DOCX export, not `text/plain`.

**What did NOT change:**

- Railway production. Untouched. `console.drnashatlatib.com` still serving the 2026-04-09 deploy.
- `rf_coaching_transcripts` (9,224 chunks) and `rf_reference_library` (584 chunks). Untouched. No writes, no reads-with-side-effects.
- `data/selection_state.json`. Still contains the placeholder `["abc","def"]`. The pilot used `/tmp/rf_pilot_selection.json`.
- ADR_006, the three plans from session 7, the marker flag work, the QPT flag work. All still frozen.
- The session-7 reading list and prior handover history. Still preserved as history. STATE_OF_PLAY (this doc, with this amendment) is still the authoritative orientation surface.

**Pointer to the next-session prompt:** `docs/NEXT_SESSION_PROMPT.md` should be refreshed by session 11 (or by Dan if he refreshes it before session 11 starts) to reflect the new state. The session-10 work removed two of session 10's three tasks; the remaining task ("commit-run the loader against a real folder") plus the lossy-export finding should drive session 11's framing.

### Session 10 addendum — low-yield safety guard added

After post-run inspection of the dry-run dump confirmed the lossy-export problem (the 4.3 MB "Comprehensive List of Supplements and substitutions" exported to ~3 KB of placeholder text with all substitution data trapped in product images), the v1 drive_loader gained a `--dump-json` inspection flag and a hard-coded `low_text_yield` skip guard.

**The guard:** Google Docs ≥10 KB on Drive whose `exported_chars / drive_size_bytes < 5%` are skipped with reason `low_text_yield`, deferred to a future v2 loader. v2 is sketched in the session 10 HANDOVER addendum: HTML export + Gemini OCR on embedded images. Not built yet.

**Effect on the Supplement Info pilot:** of 4 files in the folder, only 1 (Professional Nutritionals FKP Schedule, 96% yield) would now ingest. 2 files skipped as low_yield, 1 skipped as unsupported_mime (spreadsheet).

**Strategic note for session 11+:** The v1 loader is now intentionally conservative — it only ingests content that survives plain-text export. This means most image-heavy reference material in the Drive (which is much of it, given how Dr. Nashat builds visual handouts) is **un-ingestible by v1**. Building v2 is the natural next major piece of work. Until v2 lands, session 11 needs to either commit-run v1 against the small subset of text-heavy content, or skip ahead to v2.


---

## Session 14/15 amendment (2026-04-14) — Gap 1 CLOSED, Gap 2 OPEN

**Written:** session 15 (2026-04-14), reflecting work shipped in session 14.

### Gap 1 is CLOSED

The gap that has driven this document since session 9 — *"the folder-selection
UI persists state but no downstream ingestion trigger consumes that state"* —
is closed as of session 14, commit `d33d6a9`.

Full end-to-end roundtrip verified live:

1. Admin UI folder picker → user assigns DFH virtual dispensary folder to
   `rf_reference_library`, hits save
2. `data/selection_state.json` written with the real folder ID
3. `drive_loader_v2 --commit` reads `selection_state.json`, walks the folder,
   exports HTML, runs Gemini vision OCR on embedded images (1 image, cache
   miss → live call → cached), Layer B scrub fires once (1 name replacement
   on the DFH landing page), chunks paragraph-aware, embeds via
   `text-embedding-3-large`, writes 2 chunks to `rf_reference_library`
4. `rf_reference_library` count: 595 → 597
5. `rag_server /query` retrieves the 2 new chunks as top-ranked results for
   a DFH-relevant query

Real spend: ~$0.0004 total. No Railway writes. Run record at
`data/ingest_runs/5fb763c8b9194f72.json`.

### What also shipped in session 14 (carried in the same commit)

These are not Gap 1 itself but they're load-bearing for what's coming:

- **Folder-only enforcement** in admin UI (server save guard +
  `folder-tree.js` hides file checkboxes). This encodes an explicit
  decision that file-level selection is **not supported today** because
  v2 is Google-Docs-only and exposing per-file selection would mislead
  users about what's actually ingestible. The unlock is tied to v3
  shipping — see Gap 2.
- **Login cookie fix** (`ADMIN_DEV_INSECURE_COOKIES` env var) so localhost
  HTTP development works.
- **OpenAI live pre-flight** in `drive_loader_v2 --commit` — catches a
  silent 401 before any file is processed.
- **File-level dispatch plumbing** in `drive_loader_v2.run()` — forward-
  compatible, dormant until v3 UI lands. No behavior change in v2.

### Gap 2 — v3 multi-type loader

Dan's standing requirement: **"all file types must eventually be selectable
and ingestible."** v2 handles only Google Docs. v3 is the vehicle for
everything else.

**Definition of Gap 2:** the loader stack cannot ingest non-Google-Doc file
types (PDF, images, sheets, slides, docx, plain text, audio/video) from
Drive into any collection. The reference library on Drive is heavily
image-and-PDF-based — most of Dr. Nashat's handouts and references are
not Google Docs — so v2 reaches only a small subset of what's actually
on Drive.

**Closure proof for Gap 2** (same shape as Gap 1's proof): one PDF (or
whichever pilot type Dan selects) ingested through the full pipeline,
retrieved through `rag_server`, citations render correctly. Real spend
captured. No Railway writes. Run record on disk.

**Approach:** v3 is a **fresh module**, not modifications to v2. v2 stays
Google-Docs-only and frozen. v3 is `ingester/loaders/drive_loader_v3.py`,
designed in `docs/plans/2026-04-XX-drive-loader-v3.md` (session 15
deliverable, design only, no v3 code this session). v3 is per-type
dispatching: file MIME → handler module. Pilot type ships first as Gap
2's closure proof; remaining types one or two per session after that.

**Spans:** 3–5 sessions. Design = session 15. Pilot type implementation =
session 16. File-level UI/server unlock pairs with v3 rollout (BACKLOG
item #2).

### Other gaps tracked under Gap 2's umbrella (from session 15 BACKLOG)

These are real, but they're not the headline. They live in BACKLOG.md and
get picked up alongside or after v3 work:

- **Scrub retrofit for legacy collections** (`rf_coaching_transcripts`
  9,224 chunks + first 584 `rf_reference_library` chunks). Real liability —
  former-collaborator names may be present in pre-scrub chunk text.
  Carried from session 13. Read-only count first, then approval, then
  one-shot patch with backup. No re-embedding. (BACKLOG #3.)
- **File-level selection UI + server unlock.** Plumbing already in v2
  loader as of session 14; UI/server stay locked until v3 handles
  non-doc types. (BACKLOG #2, pairs with Gap 2 implementation.)
- **Admin UI save-toast feedback** + **selection state reset on save
  failure.** Pure UX, ~15 min combined. (BACKLOG #4 + #5.)
- **`/chat` endpoint 500** debug + **`test_login_dan.py` sys.path** shim.
  Cleanup, ~10 min each, candidates for session 15 stretch. (BACKLOG
  #6 + #7.)

### What did NOT change

- Railway production. Untouched. Still serving the 2026-04-09 deploy.
- `rf_coaching_transcripts` (9,224 chunks). Untouched.
- The legacy 584 `rf_reference_library` chunks. Untouched. (Scrub retrofit
  is on backlog, not scheduled.)
- ADR_006, Plans 1/2/3 from session 7, marker/QPT flag work. Still frozen.
- The Lineage A archival cleanup task. Still on backlog, low priority.
- The "no merge pass on coaching collection" decision. Still correct.
- The session-9 honest post-mortem and the Step-0-verify-before-acting
  rule. Still load-bearing — session 14 dirty-tree miss is a fresh
  reminder.

### Pointer to next-session prompt

After session 15 closes: `docs/NEXT_SESSION_PROMPT.md` will be refreshed
to point session 16 at the v3 pilot type implementation, using the v3
design doc from session 15 as the spec. Until then, session 15's named
work is governance catch-up + v3 design only.


---

## Session 16 amendment (2026-04-14)

### What changed

**Gap 2 closed.** v3 drive loader now ships with PDF + page-marker locator support. End-to-end scrub proven through ingest → retrieval → Sonnet generation on real production content (Egg Health Guide, 7 chunks, 18-page PDF). The full Layer B scrub chain works on real data — chunk 0 had "Dr. Christina Massinople" rewritten to "Dr. Nashat Latib" at ingest, and Sonnet's response to a real query had zero leakage of the collaborator name anywhere.

**`rf_reference_library` now contains 604 chunks** (was 597 at end of session 15):
- 584 pre-scrub A4M chunks (unchanged, NOT yet retrofitted with scrub — see BACKLOG #6b)
- 13 v2 DFH chunks (post-scrub, from session 14)
- **7 v3 PDF chunks (NEW, session 16, post-scrub, with `display_locator` page references)**

**v3 drive loader is now the production path** for new ingests of supported file types. v2 still works for legacy ingests but is frozen — no new file types will be added to it. Currently v3 supports: PDF (text-native + Gemini OCR fallback for scanned PDFs). Currently v3 explicitly DOES NOT support: Google Docs (`HandlerNotAvailable` raised; deferred to BACKLOG #11).

**Admin UI file-level selection works in Safari** with verified click-through. Both the positive path (check folders/files → save → green toast) and the drive-root rejection path (check whole drive → save → clean error toast) verified end-to-end. The save handler reads from the DOM at save time rather than from a parallel `selectionState` cache, which was the pre-existing session-14 latency-bug source.

### Permanent infrastructure improvements

1. **Admin UI now sets `Cache-Control: no-store` on HTML responses** via an `@app.after_request` hook in `admin_ui/app.py`. This was added because Safari's page cache aggressively retains rendered HTML and ignored standard cache headers, which made iterative UI development unreliable. The hook only affects HTML; CSS/JS still cache normally. This is permanent infrastructure — any future admin UI iteration benefits from it.

2. **JS save handler is now DOM-source-of-truth** for which checkboxes are selected. The pre-session-16 pattern was a parallel `selectionState` JavaScript object that was supposed to mirror the DOM but could drift out of sync. The new pattern queries `:checked` selectors at save time, which guarantees the save matches what the user sees. This is also permanent — eliminates a whole class of state-sync bugs.

### What `selection_state.json` looks like now

The session 16 schema is a two-bucket shape:

```json
{
  "selected_folders": ["18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM"],
  "selected_files": ["1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL"],
  "library_assignments": {
    "18S1VfRyFdckGU_p15m3UmXS8cjHtMEKM": "rf_reference_library",
    "1oJyksHGx9wo_44k31MD3nTnfxnBKBMlL": "rf_reference_library"
  },
  "timestamp": "2026-04-14T..."
}
```

The old folder-only shape (no `selected_files` key) is still accepted by the server endpoint for backward compatibility, but the admin UI now always sends both arrays.

### Hard rules carried forward (still in effect)

- No v1/v2/common modifications without explicit reason. v3 is a fresh module.
- No Railway writes from sessions. Railway is read-only for sessions.
- No deletions without approval + backup.
- No touching legacy collections (`rf_coaching_transcripts`, pre-scrub 584 A4M).
- Credentials ephemeral — never read `.env` content into chat.
- Never reference Dr. Christina / Dr. Chris / Dr. Massinople in agent responses.
  Layer B scrub catches new content; legacy is not yet protected (BACKLOG #6b).
- Halt before `--commit` and show Dan dump-json output.
- Pipe commit stdout to file, not `| tail`.
- Step 0 of every session checks git status carefully (session 14 lesson).
- Tech-lead volunteers architecture review at design-halt points (session 15 lesson).
- **NEW (session 16):** Test in Chrome before Safari for admin UI iterative work (lesson from Bug 3).
- **NEW (session 16):** Read the Flask access log first when debugging UI cache issues (lesson from Bug 2).
- **NEW (session 16):** Verify BACKLOG closures end-to-end in the environment where they manifested (lesson from Bug 1).

### What's actionable for next session

The retrofit bundle is the single biggest leverage point: BACKLOG #6b (coaching scrub) + #17 (display_subheading normalization) + #18 (`format_context()` migration to canonical fields) + #20 (inline citation prompting). Together these are ~half-day of coordinated work that touches all 9,224 + 584 + 13 + 7 chunks once (one backup, one read pass, one write pass per collection) instead of being four incremental passes.

Alternative: BACKLOG #11 (refactor v2 to expose `process_google_doc()` for v3 D2 adapter) unblocks the "one-button mixed-folder ingest" UX. Single dedicated session. Decision is Dan's at the start of session 17.

---

## Session 17 amendment (2026-04-14)

### What changed

**BACKLOG #11 closed.** v3 drive loader now routes Google Docs to a shared
`google_doc_handler` module via M3 design — same code path v2 uses for its
own `run()` orchestrator. Single source of truth, byte-identical v2
behavior verified twice via dry-run regression. The "one-button mixed-folder
ingest" promise that #11 was supposed to unlock now works end-to-end:
v3's dispatcher routes PDFs and Google Docs through the same run, and the
admin UI's mixed folder/file selection actually ingests both types in one
commit.

**`rf_reference_library` now contains 605 chunks** (was 604 at end of
session 16):
- 584 pre-scrub A4M chunks (unchanged, still NOT retrofitted with scrub —
  see BACKLOG #6b)
- 13 v2 DFH chunks (post-scrub, from session 14)
- 7 v3 PDF chunks (post-scrub, from session 16, with page-range locators)
- **1 v3 Google Doc chunk (NEW, session 17, post-scrub, with section locator §1)**

### M3 design proven

Session 17's BACKLOG #11 closure ships the M3 design: extract v2's inline
Google Doc logic into `ingester/loaders/types/google_doc_handler.py` as
the single source of truth, and have v2's run() import the helpers back.
This **deliberately crosses the session-14 "no v2 modifications" rule**,
justified by:

1. Byte-identical contract: v2 calls `extract_from_html_bytes()` with
   `emit_section_markers=False`, which preserves the exact same stream
   walking, image OCR, and stitching behavior as the pre-session-17 inline
   code.
2. Verified twice: v2 dry-run regression run before AND after the v3
   dispatcher edit, both byte-identical to the session-16 baseline (2
   files / 2 chunks / 1 vision cache hit / $0.0002 / same chunk-0 preview
   text including the post-scrub `Dr. Nashat Latib` substitution).
3. Backups on disk: `drive_loader_v2.py.s17-backup` (1,105 lines, pre-edit)
   and `drive_loader_v3.py.s17-backup` (888 lines, pre-edit).

### L3 (section markers) proven on real production content

The L3 design — emit `[SECTION N]` markers at `<h1>`–`<h6>` headings so
`derive_locator` can produce `§N` locators — works as designed. The Sugar
Swaps Guide pilot chunk has `display_locator='§1'` from a real heading in
the Google Doc HTML export. Two follow-up findings:

1. **Google Docs without real heading tags get empty locators**, not crashes.
   The DFH virtual dispensary docs use bold-text-as-pseudo-heading, so they
   produced `display_locator=''` in the earlier 3-file dry-run. Filed as
   BACKLOG #32 (smarter Google Doc locator detection with paragraph fallback).
2. **`display_locator` is stored as empty string, not `None`**, due to a
   Chroma-compat coercion in the v3 metadata writer. Session 16's
   `test_format_context_s16.py` already covers the empty-locator render
   path (one of its 23 tests), so this is non-blocking.

### Permanent infrastructure improvements

1. **`google_doc_handler.py` is the new dispatch path for Google Docs in
   both v2 and v3.** Any future change to Google Doc extraction lands in
   this one module. Future v3 handlers should follow the same M3 pattern
   if they need to share code with v2 (which they shouldn't, because v2 is
   frozen — but the precedent is here if needed).

2. **L3 section-marker design generalizes.** Future handlers for other
   section-bearing formats (docx, slides) can reuse the `[SECTION N]`
   marker convention from `types/__init__.py` and `derive_locator` will
   automatically render `§N` for them too. PAGE / SLIDE / ROW / SECTION /
   LINE / TIME are all defined and tested.

### What's actionable for next session

The retrofit bundle (BACKLOG #6b + #17 + #18 + #20) is still the single
biggest leverage point and is now joined by BACKLOG #30 (v3 metadata writer
drops `extraction_method` and `library_name`), which bundles naturally
with #18's canonical-display-fields migration. Session 17 also surfaced
BACKLOG #29 (Canva editor metadata strip — the Sugar Swaps Guide chunk
starts with a Canva edit URL that pollutes embeddings) as the next
content-quality issue to address. Lower-priority items added: BACKLOG #31
(`test_admin_save_endpoint_s16.py` clobbers `selection_state.json`) and
BACKLOG #32 (smarter Google Doc locator detection beyond h1-h6).

Alternative: another v3 handler. The natural next file types per the
existing `MIME_CATEGORY` table in `drive_loader_v3.py` are docx, plain
text, sheets, slides, image, av — in roughly that priority order based on
how much Drive content each one would unlock. None are blocking; all are
candidates for a focused session.

### Hard rules carried forward (still in effect)

All session 16 hard rules unchanged:

- No Railway writes from sessions. Railway is read-only for sessions.
- No deletions without approval + backup.
- No touching legacy collections (`rf_coaching_transcripts`, pre-scrub 584 A4M).
- Credentials ephemeral — never read `.env` content into chat.
- Never reference Dr. Christina / Dr. Chris / Dr. Massinople in agent
  responses. Layer B scrub catches new content; legacy is still not yet
  protected (BACKLOG #6b).
- Halt before `--commit` and show Dan dump-json output.
- Pipe commit stdout to file, not `| tail`.
- Step 0 of every session checks git status carefully + admin UI sanity.
- Tech-lead volunteers architecture review at design-halt points.
- Test in Chrome before Safari for admin UI iterative work.
- Read the Flask access log first when debugging UI cache issues.
- Verify BACKLOG closures end-to-end in the environment where they manifested.

**One rule modified in session 17:** the "no v1/v2/common modifications without
explicit reason" rule from session 14 was crossed deliberately for the M3
extract-and-redirect pattern. The justification is documented above. Future
sessions should treat v2 as frozen UNLESS the change is an extract-and-redirect
to a shared module that preserves byte-identical v2 behavior, verified by
dry-run regression. Anything else still needs explicit approval.



---

## Session 18 amendment (2026-04-15)

### Where we are

Session 18 built the v3 docx handler end-to-end and proved it on a real production file (April-May 2023 Blogs.docx, 7 chunks projected, full schema parity verified) — but did **NOT commit** the chunks. Mid-pilot, Dan surfaced a content-strategy question that warranted pausing handler-building before adding more types and multiplying cleanup surface area.

The handler itself is shipped and tested:
- 12/12 synthetic tests passing (`scripts/test_docx_handler_synthetic.py`)
- Wired into `_dispatch_file` in `drive_loader_v3.py`
- Drift-audited against PDF and Google Doc handlers — schema, chunker, scrub, marker convention, vision client, dispatcher signature all identical
- Pilot dry-run produced 7 clean chunks with `§§N-M` locators and zero leakage

The corpus state is unchanged from session 17:
- `rf_reference_library`: 605 chunks
- `rf_coaching_transcripts`: 9,224 chunks
- v3 chunks: 8 (7 pdf + 1 v2_google_doc) — docx handler is wired but has zero chunks committed

### The content-strategy halt (and why session 19 pivots)

The blog content in `April-May 2023 Blogs.docx` exists in at least three forms:
1. The docx (this file)
2. Published HTML on the Reimagined Health website
3. Email broadcasts that went out at the time

If we ingest the docx form now and then later add an HTML handler that pulls the same blogs from the website, we'll have ~95%-overlap chunks polluting retrieval. Same problem will hit:
- Slides handler vs. PDF handler vs. docx handler (same content presented as deck, exported as PDF, drafted in Word)
- AV handler vs. coaching-transcript collection (audio + Whisper transcript + Google Doc summary of one event)
- HTML handler (777 currently-UNMAPPED files in inventory) vs. essentially every other text-bearing format

This is a content-strategy gap, not a code gap. The handler architecture is fine. The corpus we ingest into is not yet protected from format-duplicate pollution.

### What changes for session 19

Session 19 pivots away from new handlers and onto **content quality and dedup infrastructure**:

1. **Build BACKLOG #23 (content-hash dedup)** as a pre-write filter in v3's commit path. Idempotent — re-running an ingest of an already-ingested file becomes a no-op. Catches filesystem duplicates and re-ingestion. ~2 hours.

2. **Close BACKLOG #29 (Canva editor metadata strip)** in `google_doc_handler` so existing Google Doc chunks (Sugar Swaps + 13 DFH) and any future Google Doc / docx chunks aren't polluted by Canva edit URLs and production tags. A/B retrieval-similarity test on the 14 existing Google Doc chunks, no Chroma writes. ~1-2 hours.

3. **Close BACKLOG #30 (`extraction_method` and `library_name` not written to Chroma metadata)** in v3's metadata writer. Affects all v3-ingested chunks (PDF + Google Doc + future docx). Small fix in the per-chunk metadata builder. ~30 min.

4. **Produce `docs/CONTENT_SOURCES.md`** — a mapping of content domain → canonical Drive folder(s) → file forms to ingest vs. skip. Dan decides; Claude documents. This becomes the input to selection decisions for any subsequent bulk ingestion.

5. **(Stretch) BACKLOG #21 (folder-selection UI redesign)** if items 1-4 land with time to spare.

After session 19, handler work resumes in session 20+ with a dedup safety net + content map + clean v3 metadata + clean Google Doc chunks. The next handler (likely plaintext or slides) inherits all of these and the next pilot can commit cleanly.

### What's NOT changing

- v1, v2, all existing v3 chunks — untouched
- Existing test suite — all 9 scripts (93 tests) green at session 18 close
- Dispatcher pattern, ExtractResult contract, `[SECTION N]` marker convention, chunker config (`MAX_CHUNK_WORDS=700`) — all proven, all stay
- M3 extract-and-redirect precedent (session 17) — still the only blessed mechanism for v2 modifications
- All session 14-17 hard rules — unchanged

### Hard rules carried forward (still in effect)

All session 17 hard rules unchanged. Plus three new ones from session 18:

- **Pre-commit drift audit on any new handler.** Before any `--commit` for a chunk produced by a new handler, run a side-by-side comparison of stored Chroma metadata for an existing chunk in the same collection vs. the projected metadata. Schema must match exactly except for type-specific fields (`v3_category`, `v3_extraction_method`, `source_unit_label`, `source_file_mime`, locator format).

- **Don't ingest a content domain until its source-of-truth is documented.** Once `docs/CONTENT_SOURCES.md` exists, every bulk ingest must map back to a designated canonical source for that content domain. Files not on the canonical list get skipped, not ingested-and-deduped-later.

- **Build the safety net before the surface area grows.** Adding handlers is fast. Cleaning up duplicates after the fact is slow and risks corrupting retrieval. Content-hash dedup must land before the next handler does.

### What's actionable for session 19

See `docs/NEXT_SESSION_PROMPT.md`. Step 0 reality check + read this amendment + read HANDOVER session 18 entry + read BACKLOG items #23, #29, #30, plus the new #33-#36. Then surface scope options (recommendation: A = the 3-item dedup + quality bundle).
