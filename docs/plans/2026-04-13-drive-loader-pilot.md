# Drive Loader Pilot — design doc

**Status:** PROPOSAL, awaiting Dan sign-off
**Author:** Claude, session 10 (2026-04-13)
**Scope:** Re-Scope B from session-10 staircase — design + UI patch + dry-run loader. NO real ingest, NO embedding spend, NO Chroma writes in this session.
**Supersedes:** nothing
**Authority:** This is a **plan**, not a state document. It does not supersede STATE_OF_PLAY, REPO_MAP, or any ADR. If approved and shipped, this doc gets a "shipped 2026-MM-DD" header amendment and stays as history.

---

## 1. Goal of this work

Push **one real Drive folder** through the existing folder-selection UI all the way to a dry-run loader that prints exactly what it would chunk, embed, and write — without writing anything. Establish a real end-to-end path between the UI and a Chroma collection so that future sessions can either (a) flip the dry-run flag and actually ingest, or (b) iterate on chunking/metadata in isolation against this pilot folder.

This closes the documented gap in `STATE_OF_PLAY.md`: "the 'save selections' button persists state, but no downstream ingestion trigger consumes that state."

**This work explicitly does NOT:**
- Touch Railway, the Railway-side `chroma_db`, or production at all
- Modify the existing 9,224 coaching chunks or 584 reference chunks
- Add or alter ADR_006 marker flags, QPT flags, or any frozen schema work from sessions 5–8
- Build any per-clone sub-collection slicing (Interpretation 3 — that's later)
- Spend money on embeddings (dry-run only)

---

## 2. Pilot folder

**`Supplement Info`**
- Folder ID: `1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`
- Drive: `1-operations` (`0AFn8_syivpiXUk9PVA`)
- Path: `//To Organise/docs@reimaginedfertility.com/Reimagined Fertility/Supplement Info`
- Modified: 2023-03-22

**Contents** (verified live via Drive API at session start):

| File | MIME | Size | Modified | Loader behavior |
|---|---|---|---|---|
| Professional Nutritionals FKP Schedule | google-apps.document | 2 KB | 2023-07-14 | INGEST (export to text) |
| Comprehensive List of Supplements and substitutions | google-apps.document | 4.3 MB | 2022-09-15 | INGEST (export to text) |
| Supplement Details | google-apps.document | 522 KB | 2022-07-09 | INGEST (export to text) |
| Supplement List with Brands | google-apps.spreadsheet | 6 KB | 2022-09-15 | SKIP (`skipped_unsupported_mime`) |

This folder was chosen because it: contains zero client PII, contains zero coaching data, exercises 3-of-4 supported MIME paths with realistic size variance (2KB → 4.3MB), AND naturally exercises the unsupported-MIME skip path (the spreadsheet) so the loader's skip logic is tested without contrivance. Reference-style content (supplement protocols + brand lists) is also the correct semantic fit for `rf_reference_library`.

---

## 3. Architecture: where does the loader fit

```
┌─────────────────────┐
│  /admin/folders     │  (existing) admin UI
│  browse + select    │
│  + library picker   │  (NEW — Gap 1)
└──────────┬──────────┘
           │ POST /admin/api/folders/save
           ▼
┌─────────────────────┐
│ selection_state.json│  (existing JSON, but with library_assignments populated)
└──────────┬──────────┘
           │ read by
           ▼
┌─────────────────────────────┐
│ ingester.loaders.drive_loader│  (NEW — Gap 2, the loader)
│ --dry-run (default)          │
│ --commit                     │
└──────────┬──────────────────┘
           │ writes (only with --commit)
           ▼
┌─────────────────────┐
│  LOCAL chroma_db    │  (development sandbox; NEVER Railway in this session)
│  rf_reference_library│
└─────────────────────┘
```

**Design principles holding the architecture together:**

1. **CLI-driven, not HTTP-driven.** The loader is `python3 -m ingester.loaders.drive_loader`, not a Flask endpoint behind a button. The UI's job is to select; the loader's job is to ingest. Coupling them via a button creates a long-running HTTP request and gives the UI uptime expectations the architecture isn't ready for. CLI-driven means the loader can be run from your terminal under direct supervision, and the UI stays a thin selection tool.
2. **Read-once contract on `selection_state.json`.** The loader reads the file at startup, snapshots what it's about to do, and proceeds. It does not watch the file or react to changes mid-run. If the UI is used to edit selections during a loader run, that's a "next run" problem, not a race condition.
3. **Local-only enforcement.** The loader hard-checks `CHROMA_DB_PATH` at startup and **refuses to run** if the path begins with `/data/` (the Railway volume convention). This is a code-level safeguard, not a docs-level one. Bypassing it requires editing the loader file, which would be a deliberate act, not an accident.
4. **Idempotent at the file level.** Re-running the loader against the same folder produces the same chunks (deterministic IDs, deterministic chunk boundaries given the same source text). If the same chunk ID already exists in Chroma, it's an upsert, not a duplicate. This means the dry-run can be run repeatedly without consequence and a real run can be re-run safely.
5. **Forward-compatible metadata.** Every chunk written includes the `display_*` fields STATE_OF_PLAY identifies as the future read-time normalization shape, AND the `source_folder_id` field that the future Interpretation-3 per-clone slicer will filter on. Writing these now means no backfill is needed when those features land later.
6. **No marker flags, no QPT flags, no ADR_006 universal contract.** Per STATE_OF_PLAY, ADR_006 is frozen and not load-bearing. The loader does not import from `ingester/marker_detection.py` or `ingester/backfills/_common.py`. If those modules become canonical later, the loader can be retrofitted; today it would be premature coupling to frozen design work.

---

## 4. The library picker UI patch (Gap 1)

### Current behavior
`folder-tree.js` line 454 hardcodes `library_assignments: {}`. The save handler accepts this and writes it to disk. There is no UI element for picking a library.

### After patch
A **Pending Selections** panel renders between the toolbar and the tree, showing each currently-checked folder as a row:

```
┌───────────────────────────────────────────────────┐
│  Pending Selections (1)                           │
│  ┌─────────────────────────────────────────────┐  │
│  │ Supplement Info                             │  │
│  │ //To Organise/.../Reimagined Fertility/...  │  │
│  │ Library: [rf_reference_library ▾]    [×]    │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

**Picker options for v1:**
- `rf_reference_library` (default, only option in v1)

**NOT offered in v1** (with reasoning):
- `rf_coaching_transcripts` — Drive-walked content has no business going into the coaching collection. The coaching collection is built by the v3 transcript pipeline against a single concatenated transcript file, not from arbitrary Drive folders. Letting a UI dropdown route a Drive folder there would be a category error with HIPAA implications.
- `rf_published_content` — Collection doesn't exist yet. Offering it as an option promises something the system can't deliver.

If a second collection becomes a valid Drive-loader target in the future, adding it is a 1-line edit to a JS array.

### JSON shape posted to `/admin/api/folders/save`

Before:
```json
{
  "selected_folders": ["folderId1", "folderId2"],
  "library_assignments": {},
  "timestamp": "..."
}
```

After:
```json
{
  "selected_folders": ["folderId1", "folderId2"],
  "library_assignments": {
    "folderId1": "rf_reference_library",
    "folderId2": "rf_reference_library"
  },
  "timestamp": "..."
}
```

**Schema rule:** every folder ID in `selected_folders` MUST appear as a key in `library_assignments`. Frontend enforces this by construction (the Pending Selections panel is built from the same `selectionState` object). Backend enforces it as defense in depth (your call from the earlier round of questions).

### Files modified

| File | Change | Approx lines |
|---|---|---|
| `admin_ui/templates/folders.html` | Add `<div class="pending-selections">` block between toolbar and tree | ~12 |
| `admin_ui/static/folder-tree.js` | Add `renderPendingSelections()`, `getFolderDisplayInfo()`, modify the save handler to read dropdown values, hook checkbox change events into the panel re-render | ~80–100 |
| `admin_ui/app.py` | Add 4-line server-side validation in `api_folders_save()` returning HTTP 400 if any selected folder is missing from `library_assignments` | ~6 |
| `admin_ui/static/folder-tree.css` | Inline a small `<style>` block in folders.html instead of editing the CSS file (faster to land, easier to revert) | 0 (inlined) |

**Total**: ~100–120 lines added, 3 files touched. Fully reversible via `git checkout`.

---

## 5. The loader (Gap 2)

### File location
`ingester/loaders/__init__.py` — empty package marker
`ingester/loaders/drive_loader.py` — the loader

### Module dependencies
- `ingester.drive_client.DriveClient` — already exists, used as-is
- `ingester.config` — already exists, used for MIME constants and `CHROMA_DB_PATH`
- `googleapiclient` (already in requirements) — for the `files().export()` call to convert Google Docs to text
- `chromadb` (already in requirements) — for the actual collection write
- `chromadb.utils.embedding_functions.OpenAIEmbeddingFunction` (already in requirements)

**No new dependencies required.** This is verified — `requirements.txt` already has everything needed because the v3 pipeline and the existing rag_server use the same libraries.

### Supported MIME types in v1

| MIME type | Strategy |
|---|---|
| `application/vnd.google-apps.document` | Drive `files().export(fileId=..., mimeType="text/plain")` → returns plain text |
| `text/plain`, `text/markdown` | Drive `files().get_media(fileId=...)` → returns raw bytes, decoded as UTF-8 |

### Skipped in v1 (logged, not errored)
- `application/vnd.google-apps.spreadsheet` — needs cell-aware export; deferred
- `application/vnd.google-apps.presentation` — needs slide-aware export; deferred (Lineage B handles this for A4M, but that pipeline is undocumented)
- `application/pdf` — needs PDF text extraction; deferred (would add `pypdf` or similar)
- `image/*` — needs vision model and real cost; deferred
- `video/*`, `audio/*` — completely separate transcription pipeline territory; deferred indefinitely
- Anything else — generic skip

### Chunking strategy

**Approach: paragraph-aware sliding window, no LLM.**

1. Normalize whitespace: collapse runs of >2 newlines to exactly 2, strip trailing spaces.
2. Split into paragraphs on `\n\n`.
3. Greedy assembly: walk paragraphs, accumulate into a chunk until adding the next paragraph would push word count past `MAX_CHUNK_WORDS = 700`. Emit the chunk.
4. Overlap: the next chunk starts with the **last paragraph of the previous chunk** (paragraph-level overlap, not word-level — cleaner boundaries).
5. Hard floor: never emit a chunk smaller than `MIN_CHUNK_WORDS = 80` unless it's the only chunk in the file (a 30-word document is one chunk, not zero).
6. Hard ceiling: if a single paragraph exceeds `MAX_CHUNK_WORDS`, split it at sentence boundaries (regex `(?<=[.!?])\s+`) using the same greedy strategy.

**Why not the v3 LLM chunker?** The v3 chunker is tuned for Q&A coaching transcripts with speaker turns. Reference documents have no speaker structure, no Q&A boundaries, and the LLM pass would cost ~$0.001 per chunk for marginal benefit on this content type. We can upgrade later if retrieval quality is poor.

**Why not the v3 chunker's word-count fallback?** Same reason — it's tuned for transcripts and doesn't respect paragraph structure, which matters more for prose than for Q&A.

**Tunables, set as constants in the loader:**
```python
MAX_CHUNK_WORDS = 700
MIN_CHUNK_WORDS = 80
PARAGRAPH_OVERLAP = True   # last paragraph of previous chunk starts the next
```

### Chunk ID format

`drive:{drive_slug}:{file_id}:{chunk_index:04d}`

Examples:
- `drive:1-operations:1abc...:0000`
- `drive:1-operations:1abc...:0001`

**Properties:** stable, deterministic, scoped to the drive-loader path so no collision risk with the existing `a4m-m{N}-{type}-{NNN}` (A4M reference library) or `CHUNK-{N}-{N}` (coaching transcripts) formats. The `drive:` prefix makes the source pipeline identifiable from the ID alone.

### Metadata fields written per chunk

Every chunk written to Chroma will carry **all** of these fields. Marked **R** = required, **O** = optional/may be null.

| Field | Type | Required | Source | Future use |
|---|---|---|---|---|
| `chunk_index` | int | R | loader | sequence in source file |
| `word_count` | int | R | loader | filtering, debugging |
| `source_pipeline` | str | R | constant `"drive_loader_v1"` | provenance, helps later forensics |
| `source_collection` | str | R | from `library_assignments` | retrieval routing |
| `source_drive_slug` | str | R | from manifest | grouping by drive |
| `source_drive_id` | str | R | Drive API | uniqueness |
| `source_folder_id` | str | R | from `selected_folders` | **Interpretation-3 slicing key** |
| `source_folder_path` | str | R | from manifest | human-readable display |
| `source_file_id` | str | R | Drive API | uniqueness, re-ingest dedup |
| `source_file_name` | str | R | Drive API | display |
| `source_file_mime` | str | R | Drive API | filtering, debugging |
| `source_file_modified_time` | str | R | Drive API | re-ingest detection |
| `source_file_size_bytes` | int | O | Drive API | may be null for Google-native types |
| `source_web_view_link` | str | R | Drive API | citation, "view source" link |
| `ingest_run_id` | str | R | UUID generated at loader startup | grouping all chunks from one run |
| `ingest_timestamp_utc` | str | R | ISO 8601 | when this run happened |
| `display_source` | str | R | = `source_file_name` | future read-time normalizer header |
| `display_subheading` | str | R | = `source_folder_path` | future read-time normalizer subheading |
| `display_speaker` | str/null | O | always null for Drive content | future read-time normalizer speaker line |
| `display_date` | str | R | = `source_file_modified_time` | future read-time normalizer date |
| `display_topics` | str/null | O | always null in v1 | future tagging hook |

**Fields deliberately NOT written** (and why):
- `topics` (v3 coaching style) — that's a v3-pipeline thing, no equivalent here
- `coaches` / `client_names` / `client_rfids` — coaching-only, not relevant
- `module_number` / `module_topic` / `speaker` — A4M reference library style, not relevant
- ADR_006 marker flags / QPT flags — frozen, not load-bearing per STATE_OF_PLAY

**Why these field names and not ADR_006 names?** Because ADR_006 is frozen. Using ADR_006's names would imply commitment to a schema that was correctly identified in session 9 as not load-bearing. The `display_*` field names match the 5-field shape STATE_OF_PLAY recommends for the future read-time normalizer. The `source_*` field names are descriptive and unambiguous. Future schema unification can rename these mechanically if needed.

### CLI shape

```
python3 -m ingester.loaders.drive_loader \
    --selection-file data/selection_state.json \
    [--dry-run | --commit] \
    [--folder-id <id>] \
    [--verbose]
```

**Defaults:**
- `--dry-run` is the default. `--commit` must be passed explicitly to actually write.
- `--folder-id` filters the run to one folder ID even if the selection file contains more. **For the session-10 pilot, this will always be passed** — defense against accidentally processing other entries.
- `--verbose` prints per-chunk previews; otherwise prints per-file summaries.

**Refuses to run if:**
- `CHROMA_DB_PATH` starts with `/data/` (Railway production guard)
- `OPENAI_API_KEY` is not set
- `selection_state.json` contains placeholder data (`["abc", "def"]`) — tells you to actually use the UI first
- Any selected folder is missing from `library_assignments`
- Any `library_assignments` value is not in the v1 allowed set (`{"rf_reference_library"}`)

### Dry-run output shape

```
=== Drive Loader Pilot — DRY RUN ===
ingest_run_id:  9f4b...
chroma path:    /Users/danielsmith/Claude - RF 2.0/chroma_db (LOCAL)
target coll:    rf_reference_library

=== folder: Supplement Info ===
  drive:        1-operations (0AFn8_syivpiXUk9PVA)
  folder_id:    1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54
  path:         //To Organise/.../Supplement Info
  files seen:   4
  files to ingest: 3
  files skipped:   1 (unsupported MIME)

  --- file: Professional Nutritionals FKP Schedule ---
      mime:        application/vnd.google-apps.document
      modified:    2023-07-14T18:25:30Z
      exported:    1,847 chars / 312 words
      chunks:      1
      chunk[0]:    312 words, id=drive:1-operations:1xxx:0000
                   preview: "Professional Nutritionals FKP Schedule\n\nSupplement protocols..."

  --- file: Comprehensive List of Supplements and substitutions ---
      mime:        application/vnd.google-apps.document
      modified:    2022-09-15T02:14:06Z
      exported:    412,883 chars / 64,127 words
      chunks:      ~98
      chunk[0]:    684 words, id=drive:1-operations:1yyy:0000
                   preview: "Comprehensive List of Supplements..."
      [97 more chunks not shown — pass --verbose to see all]

  --- file: Supplement Details ---
      mime:        application/vnd.google-apps.document
      modified:    2022-07-09T05:34:12Z
      exported:    52,184 chars / 8,041 words
      chunks:      ~13
      chunk[0]:    695 words, id=drive:1-operations:1zzz:0000

  --- SKIPPED: Supplement List with Brands ---
      mime:        application/vnd.google-apps.spreadsheet
      reason:      unsupported_mime (spreadsheet support deferred)

=== Run summary ===
  files seen:        4
  files ingested:    3 (dry-run, no actual writes)
  files skipped:     1
  total chunks:      ~112
  estimated tokens:  ~75,000 (chunk text only, embedding input)
  estimated cost:    $0.0098 (text-embedding-3-large @ $0.13/1M tokens)
  
  Use --commit to actually write. Currently: DRY RUN, nothing written.
```

This output gives you everything you need to decide whether to flip to `--commit` in a future session: file list, skip reasons, chunk counts, cost estimate, and the chunk ID format so you can spot-check the deterministic-ID claim by re-running.

### Commit-mode behavior (NOT executed in this session, but designed)

When eventually run with `--commit`:
1. Same dry-run output as above, plus:
2. Embed each chunk via OpenAI `text-embedding-3-large`, in batches of 100
3. Write to local `rf_reference_library` collection via `collection.add()` with `ids`, `documents`, `metadatas`
4. If a chunk ID already exists, use `collection.upsert()` instead — this is the idempotent path
5. Print per-batch progress
6. Final verification: query the collection for one chunk by ID and print it back, to prove the write succeeded
7. Write a JSON run record to `data/ingest_runs/{ingest_run_id}.json` with the full list of file IDs, chunk IDs, and costs — for auditability and possible future undo

**The run record is the undo path.** If a commit-mode run produces bad chunks, the run record contains every chunk ID written. A separate `--undo-run <run_id>` flag (NOT built in v1, but designed for) would read the run record and call `collection.delete(ids=...)` to remove exactly those chunks.

---

## 6. What gets shipped this session if you approve the doc

In order:

1. **Library picker UI patch** — `folders.html` + `folder-tree.js` + `app.py` validation. ~30-45 min.
2. **Loader written** — `ingester/loaders/__init__.py` + `ingester/loaders/drive_loader.py`. ~45-60 min. The dry-run code path is fully implemented; the commit code path is fully implemented but stays gated behind the `--commit` flag.
3. **Dry-run executed** against `Supplement Info`, output shown to you. ~5 min if everything works, longer if I hit bugs.
4. **STOP**. No `--commit` invocation in this session. Per Re-Scope B.

---

## 7. What's NOT shipped this session

- Actual ingestion. No `--commit` runs.
- PDF / spreadsheet / slide / image / video support.
- The v3 LLM chunker integration.
- Per-clone sub-collection slicing (Interpretation 3) — the loader writes `source_folder_id` so this becomes possible later, but the rag_server query path doesn't yet filter on it.
- Any change to `rag_server/app.py` — including the read-time normalizer side quest. Defer to a session where it's the actual blocker.
- Any change to existing chunks in either collection. Read-only on the existing data.
- The `--undo-run` flag.
- Auto-running the loader on save (no Flask endpoint, no background worker — CLI only).

---

## 8. Hard rules carried forward (verbatim from session 9)

- No ChromaDB writes without explicit Dan approval at the specific write moment, and never to Railway without a pre-flight discussion of backups → **honored:** dry-run only this session, plus the loader has a hard guard against `/data/` paths
- No git push, commit, or add — Dan runs git, Claude suggests → **honored**
- No Railway operations without explicit approval → **honored:** loader refuses to run against Railway paths
- No deletions without approval and a verified backup → **honored:** loader has no delete code path in v1
- Never reference Dr. Christina; exclude Kelsey Poe + Erica → **n/a:** Drive loader for non-coaching content
- Public agent never accesses `rf_coaching_transcripts` → **honored:** loader's allowed library set excludes it by code, not docs
- Credentials are ephemeral → **honored:** loader reads from env, never logs key values
- `create_file` writes to Claude's sandbox, not the Mac → **honored:** all repo edits via Desktop Commander heredocs or Filesystem write tools

---

## 9. Open questions for Dan to weigh in on

1. **Library picker dropdown behavior when `rf_reference_library` is the only option.** I'm planning to render it as a real `<select>` with one option, defaulting to that option, so the schema (each folder needs an assignment) is enforced uniformly and adding a second option later is trivial. Alternative: render it as a static label "→ rf_reference_library" with no dropdown until there's >1 option. Slightly cleaner UI, slightly more code to change later. **My pick: real dropdown.** Push back if you disagree.
2. **Should the loader also write a `data/ingest_runs/{run_id}.json` record in dry-run mode?** Argument for: same code path as commit-mode, easier to test. Argument against: dry-run is supposed to be zero-side-effect. **My pick: dry-run writes no files anywhere. The run record only happens in commit mode.** Push back if you disagree.
3. **Embedding cost estimate threshold.** If the dry-run says "~$5.00", I'd want a soft warning printed even though we're not committing, because it tells you the "cost to flip" of going to commit. If it says "$0.01" no warning. I'm picking $1.00 as the threshold for the warning. Trivial choice, just flagging.

None of these block writing the patch. If you say "approve, proceed" I'll go with my picks above. If you flag any of them, I'll adjust.

---

## 10. Approval gate

If you approve, I proceed in this order:

1. UI patch (folders.html + folder-tree.js + app.py) → show you the diff → curl-test the new save shape
2. Loader (ingester/loaders/drive_loader.py) → show you the file → run `--dry-run --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`
3. Show you the dry-run output
4. STOP. Hand back for review.

If you reject or want changes, we adjust the doc first and re-approve before any code.
