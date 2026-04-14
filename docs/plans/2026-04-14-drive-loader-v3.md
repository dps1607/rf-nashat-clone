# Drive Loader v3 — Multi-type ingestion (Gap 2)

**Status:** DESIGN ONLY, session 15 (2026-04-14). No v3 code this session.
**Author:** Claude (tech-lead, under mandate)
**Predecessors:**
- v1 drive_loader — text-only Google Docs, conservative, low-yield guard
  (`docs/plans/2026-04-13-drive-loader-pilot.md`)
- v2 drive_loader — Google Docs HTML + Gemini vision OCR on embedded images
  (`docs/plans/2026-04-13-drive-loader-v2.md`)
- Session 14 — closed Gap 1, file-level dispatch plumbing landed dormant in v2
- Session 15 — STATE_OF_PLAY amendment introducing Gap 2, BACKLOG.md items 1–7

**Implements:** Gap 2 from `docs/STATE_OF_PLAY.md` session 14/15 amendment.

---

## Why v3 exists

v2 closed the image-trapped-Google-Docs problem and proved Gap 1 closable
(595 → 597 chunks via the DFH ingest in session 14). But v2's reach is
narrow by design: it ingests **only** Google Docs (`mimeType ==
application/vnd.google-apps.document`). Everything else on Drive — PDFs,
loose images, spreadsheets, slide decks, Word docs, plain text, audio, video
— is invisible to v2.

This is structural, not incidental. Most of Dr. Nashat's reference material
on Drive is **not** Google Docs. It's PDFs (research papers, supplement
monographs, A4M certification handouts), images (lab marker reference
charts, BBT examples), Canva exports, and slide decks. v2 sees a small
slice of the library.

Dan's standing requirement, captured verbatim in session 15 governance:

> "All file types must eventually be selectable and ingestible."

v3 is the vehicle for that requirement. It is the named successor to Gap 1
and the closure path for Gap 2.

---

## Scope

**v3 DOES:**
- Ingest non-Google-Doc file types from Drive into ChromaDB collections
- Per-type dispatch: file MIME → handler module
- Reuse v1/v2's plumbing where it already exists: auth, folder walk,
  chunking chokepoint (`_drive_common.py`), Layer B scrub, embedding,
  ChromaDB write path, run records, cost tracking, dump-json inspection
- Per-type cost model accounting (vision $, OCR $, transcription $,
  embedding $/chunk) rolled up into the same run-record shape v2 uses
- Per-type Layer B scrub validation — verify that scrub fires correctly
  on each new format before committing real ingest
- Pair with the file-level UI/server unlock (BACKLOG #2) so users can
  select individual non-doc files, not only folders
- Land one pilot type end-to-end as Gap 2's closure proof, same shape as
  Gap 1's DFH proof in session 14

**v3 does NOT:**
- Replace v1 or v2 — both stay frozen as fast paths for their content
  types. v1 = text-only Google Docs. v2 = image-rich Google Docs. v3 =
  everything else.
- Bolt new types onto v2. v3 is a fresh module: `ingester/loaders/
  drive_loader_v3.py`. Type-specific extractors live in
  `ingester/loaders/types/`.
- Push to Railway. Local Chroma only, same as v1 and v2 development.
- Re-ingest content already in Chroma. Chunk-ID upsert handles that for
  free.
- Touch `rf_coaching_transcripts` or the legacy 584 `rf_reference_library`
  chunks. Scrub retrofit (BACKLOG #3) is the path for those.
- Ship all file types in one session. Pilot type ships first as Gap 2
  closure; remaining types one or two per session after that.

---

## Architectural decisions

### D1. Fresh module, sibling to v1 and v2

```
ingester/loaders/
├── _drive_common.py         # shared chunking + scrub + walk helpers
├── drive_loader.py          # v1 (frozen)
├── drive_loader_v2.py       # v2 (frozen)
├── drive_loader_v3.py       # NEW — v3 dispatcher
└── types/                   # NEW — per-type handler modules
    ├── __init__.py
    ├── pdf_handler.py
    ├── image_handler.py
    ├── sheets_handler.py
    ├── slides_handler.py
    ├── docx_handler.py
    ├── plaintext_handler.py
    └── av_handler.py        # audio/video transcription
```

**Why not extend v2:** session 14 added file-level dispatch plumbing inside
`drive_loader_v2.run()`, but that plumbing was scoped explicitly to
Google-Docs files (it short-circuits to v2's existing HTML+OCR path). Adding
non-doc handling to v2 would mean v2 stops being "the Google Docs loader"
and starts being "the everything loader," which (a) breaks the clean
v1-fast-path / v2-rich-path mental model, (b) makes v2's frozen status a
lie, (c) couples non-doc bugs to v2's well-tested HTML+OCR path. Fresh
module is cheaper.

**Why a `types/` subdirectory:** each handler has different dependencies
(pdfplumber, openpyxl, python-pptx, python-docx, Whisper or Gemini for
transcription) and different cost models. Isolating them keeps imports
cheap (only the dispatcher imports lazily what it needs) and lets each
handler be developed and tested independently.

### D2. Dispatcher reads MIME, routes to handler

The dispatcher is dumb on purpose. It walks the selection (folder or
file IDs from `selection_state.json`), reads `mimeType` from the Drive
metadata, and routes:

```
mime_to_handler = {
    "application/vnd.google-apps.document": v2_google_doc_adapter,  # calls v2 internally
    "application/pdf": pdf_handler,
    "image/jpeg": image_handler,
    "image/png": image_handler,
    "image/webp": image_handler,
    "image/gif": image_handler,
    "application/vnd.google-apps.spreadsheet": sheets_handler,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": sheets_handler,
    "application/vnd.google-apps.presentation": slides_handler,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": slides_handler,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": docx_handler,
    "text/plain": plaintext_handler,
    "text/markdown": plaintext_handler,
    "audio/mpeg": av_handler,
    "audio/mp4": av_handler,
    "audio/wav": av_handler,
    "video/mp4": av_handler,
    "video/quicktime": av_handler,
}
```

Google Docs MIME (`application/vnd.google-apps.document`) **is** in the
dispatch table, but it routes to v2 via a thin adapter rather than a v3
handler. Rationale below.

**Mixed selections and the v3 → v2 adapter (revised session 15).** An
earlier draft of this section said v3 should skip Google Docs and force
the user to run v2 separately. That was wrong for the admin-UI path: if
a user selects a folder containing 10 Google Docs and 5 PDFs, hitting
"ingest" and being told "10 files were ignored, run v2" is a confusing
state and effectively breaks the UI's "one button" promise.

The revised rule: **v3 is the single entry point the admin UI calls. For
Google Docs files, v3's dispatcher invokes v2's existing
`process_google_doc()` internally as the handler** (same function v2
already uses in its own run loop, no code duplication). Results flow
back into the unified v3 run record with `handler: "v2_google_doc"`
tagged on each file's entry.

Properties of the adapter:
- **v2 is not modified.** v3 imports `drive_loader_v2.process_google_doc`
  and calls it. v2 stays frozen as a standalone loader for CLI users who
  want to run it directly.
- **OCR cache is shared.** Both loaders read/write
  `data/image_ocr_cache/*.json` keyed by SHA-256, so re-running a mixed
  folder hits v2's cache for free.
- **Scrub chokepoint is shared.** v2 already routes through
  `_drive_common.chunk_paragraphs()`, so no scrub wiring changes.
- **Cost and run records unified.** v3's run record has a top-level
  `by_handler` breakdown including `v2_google_doc` alongside the v3
  handlers (`pdf_text`, `image`, etc.), so a mixed run produces one
  artifact, not two.
- **CLI behavior unchanged for direct v2 users.** Running
  `drive_loader_v2 --commit` still works exactly as today. The adapter
  is a v3-internal call path.

### D3. Each handler returns the same shape

Every handler implements one function:

```python
def extract(
    drive_file: dict,           # Drive metadata (id, name, mimeType, size, etc.)
    drive_client: DriveClient,  # for download
    config: HandlerConfig,      # per-type knobs (max pages, OCR fallback, etc.)
) -> ExtractResult:
    """
    Returns:
      ExtractResult(
        text_blocks: list[TextBlock],   # ordered prose + image markers
        images_seen: int,
        images_ocr_called: int,
        vision_cost_usd: float,
        transcription_cost_usd: float,  # 0 for non-AV handlers
        extraction_method: str,         # "pdf_text", "pdf_ocr_fallback", etc.
        warnings: list[str],
      )
    """
```

The dispatcher then hands `text_blocks` to the existing
`_drive_common.chunk_paragraphs()` chokepoint (already wired with Layer B
scrub), which means **scrub fires for every type for free**. Per-type
scrub validation (D6 below) verifies that the chokepoint actually catches
collaborator names in each new format.

### D4. Per-type extraction strategies

| Type | Primary | Fallback | Cost driver |
|---|---|---|---|
| PDF (text-native) | `pdfplumber` text extraction | Vision OCR per page (Gemini 2.5 Flash) if `extracted_chars / pdf_size_bytes < 5%` | Embedding only (cheap) |
| PDF (scanned) | `pdfplumber` page → image → vision OCR | (none — fail loud) | Vision OCR per page |
| Image (loose) | Gemini 2.5 Flash vision OCR (single call) | (none) | One vision call per image |
| Sheets (Google) | Sheets API → CSV → row-grouped text blocks | (none) | Embedding only |
| Sheets (xlsx) | `openpyxl` → CSV → row-grouped text blocks | (none) | Embedding only |
| Slides (Google) | Slides API → per-slide text + speaker notes; vision OCR on slide images via slide thumbnail | (none) | Vision OCR per slide with embedded images |
| Slides (pptx) | `python-pptx` → per-slide text + notes; vision OCR on slide images via Pillow render | `pdfplumber` if pptx → PDF first | Vision OCR per image-bearing slide |
| docx | `python-docx` → ordered paragraphs + image references; vision OCR on inline images | (none) | Vision OCR per inline image |
| Plain text / md | direct UTF-8 read | (none) | Embedding only |
| Audio | Gemini 2.5 audio transcription (Vertex) | Whisper local fallback (deferred) | Per-minute transcription |
| Video | Strip audio via `ffmpeg`, then audio path | (none) | Per-minute transcription |

**Vision OCR is the same Gemini path v2 already uses.** Same project, same
region, same service account, same OCR cache directory
(`data/image_ocr_cache/*.json`, currently 28 files), same SHA-256-keyed
cache hits. Re-running v3 against a folder previously processed by v2
costs $0 on the image OCR side because the cache hits the same keys.

### D5. Per-type cost model

The session 14 v2 run cost ~$0.0004 for 2 chunks. v3's costs vary widely
by type. The dispatcher's run record breaks them out:

```
v3 run record:
  files seen:           N
  files dispatched:     N
  by type:
    pdf_text:           {count, chunks, est_tokens, est_cost}
    pdf_ocr:            {count, pages, vision_cost, est_cost}
    image:              {count, vision_cost}
    sheets:             {count, rows, chunks, est_cost}
    slides:             {count, slides, vision_cost, est_cost}
    docx:               {count, chunks, vision_cost, est_cost}
    plaintext:          {count, chunks, est_cost}
    audio:              {count, minutes, transcription_cost}
    video:              {count, minutes, transcription_cost}
  total_vision_cost:    $X
  total_transcription_cost: $Y
  total_embedding_cost: $Z
  total_run_cost:       $X+Y+Z
```

**Cost gates carried from v2 (unchanged):** $1.00 interactive prompt,
$25 hard refuse. v3 dry-run prints projected total and waits for `--commit`
plus, if total > $1, an interactive yes/no.

**Rough cost intuition for sizing decisions:**
- PDF text-native: ~$0.0001 per 100 KB of text (embedding only)
- PDF vision OCR: ~$0.0003 per page (Gemini 2.5 Flash vision)
- Loose image: ~$0.0003 per image (one vision call)
- Slides with images: ~$0.0003 per slide × (slides with images)
- Audio transcription: Gemini 2.5 audio is ~$0.001/minute; Whisper local
  is free but slow; choice deferred to handler implementation session
- 1 GB of mixed reference material: order $1–$5 depending on image density

### D6. Per-type Layer B scrub validation

Scrub is wired at the chunking chokepoint in `_drive_common.py`, so any
text that flows through the chokepoint is scrubbed. **What v3 must verify
per type** is that the handler actually emits the right text into the
chokepoint:

- **PDF text-native:** scrub catches names in extracted prose? Test by
  feeding `pdfplumber` output containing a known scrub pattern (e.g.,
  "Dr. Christina Massinople") and asserting the chokepoint's output
  shows `name_replacements ≥ 1`.
- **PDF OCR:** vision OCR output goes through chokepoint? Already tested
  in v2 (DFH landing page). Same code path.
- **Image:** same as PDF OCR. Same path.
- **Sheets:** does scrub fire on cell text? Test with a cell containing
  the pattern. Expected: yes, because the row-grouped text blocks are
  just strings going through the chokepoint.
- **Slides:** speaker notes and slide text both go through chokepoint?
  Test both fields independently — speaker notes are a different field
  in the Slides API and could be missed by a naive handler.
- **docx:** paragraph text + inline image OCR text both reach chokepoint?
  Test with a docx containing both.
- **Plain text:** trivially scrubbed via chokepoint.
- **Audio/video:** transcription output goes through chokepoint? Yes
  by construction, but verify in pilot.

**A new test file** `scripts/test_scrub_v3_handlers.py` is added in the
session that builds each handler. Each handler's first commit lands with
its scrub validation test passing. This is non-negotiable — the legacy
collections (BACKLOG #3) prove what happens when content lands in Chroma
without scrub. v3 cannot create more of that liability.

### D7. Citation rendering for non-prose types

The session-9 STATE_OF_PLAY locked a 5-field display normalization
(`display_source`, `display_subheading`, `display_speaker`, `display_date`,
`display_topics`) that works cleanly for lectures and coaching calls. It
does **not** work cleanly for the v3 types:

- **Sheets.** "Row 47 of the Supplements tab" is not a subheading. A
  chunk groups multiple rows; the citation needs a row range.
- **Slides.** A slide deck has its own per-slide structure and slide
  numbers; module-number semantics don't apply.
- **PDFs.** Pages are the natural locator; not always a subheading.
- **Audio/video.** Needs a timestamp range (`[00:14:32]–[00:16:10]`),
  which the current rag_server citation renderer doesn't format.

**The extension rule (decided in session 15, implemented in session 16):**
add two optional display fields to the convention. Existing A4M and
coaching chunks continue to work unchanged; v3 handlers populate the
new fields as appropriate for their type.

| New field | Type | Semantics | Example values |
|---|---|---|---|
| `display_locator` | str or null | In-document position, handler-defined format | `"p. 4"`, `"slide 12"`, `"rows 40–47"`, `"§3.2"` |
| `display_timestamp` | str or null | Time range for AV content | `"[00:14:32]–[00:16:10]"` |

**Per-handler population rules:**

| Handler | `display_source` | `display_subheading` | `display_locator` | `display_timestamp` |
|---|---|---|---|---|
| pdf | filename | section heading if detected, else null | `"p. N"` or `"pp. N–M"` | null |
| image | filename | null | null | null |
| sheets | workbook name | sheet/tab name | `"rows N–M"` | null |
| slides | deck title | slide title if present, else null | `"slide N"` | null |
| docx | filename | heading style text if detected | `"§N"` if detected, else null | null |
| plaintext | filename | null | `"lines N–M"` | null |
| audio | filename | null | null | `"[HH:MM:SS]–[HH:MM:SS]"` |
| video | filename | null | null | `"[HH:MM:SS]–[HH:MM:SS]"` |

**`rag_server/app.py:format_context()` update.** When either new field is
present, the citation header renders `{display_source} — {display_subheading} —
{display_locator}{display_timestamp}` with null fields elided. A chunk
without either new field renders exactly as it does today (no regression
on A4M or coaching chunks).

**One rule to prevent handler drift:** `display_locator` is always a
human-readable string, never a structured object. Handlers format their
own locators. The renderer is dumb — it concatenates what the handler
gives it. This prevents the Gap-1-era problem (inconsistent metadata
shapes forcing the renderer to know every handler's internals) from
coming back in a new shape.

---

### D8. File-level selection unlock pairs with v3 rollout

Session 14 hid file checkboxes in the admin UI and added a server-side
folder-only guard, because exposing file selection over a Google-Docs-only
loader would mislead users. **v3 unlocks both:**

- `admin_ui/static/folder-tree.js`: re-introduce file checkboxes (BACKLOG
  #2)
- `admin_ui/templates/folders.html`: render file rows with type icons
- `admin_ui/app.py:api_folders_save`: drop the folder-only guard, accept
  arbitrary Drive IDs (BACKLOG #2)

These changes land **in the same session as the v3 pilot type**, not
before. Reason: if the unlock ships before v3 handles non-doc types,
users select PDFs, hit ingest, and silently get nothing because the
v2 file-level dispatch only handles Google Docs. The unlock is gated on
v3 actually doing something with non-doc selections.

### D9. selection_state.json schema is unchanged

Already supports file IDs alongside folder IDs. v2's session 14 dispatch
plumbing reads them. v3 reads the same shape. No migration.

```json
{
  "selected_folders": ["folder_id_1", "folder_id_2"],
  "selected_files":   ["file_id_1", "file_id_2"],
  "library_assignments": {
    "folder_id_1": "rf_reference_library",
    "file_id_1": "rf_reference_library"
  },
  "timestamp": "2026-04-XXTHH:MM:SSZ"
}
```

(`selected_files` is currently absent from real `selection_state.json`
files because the UI doesn't write it yet — but the loader code already
tolerates its presence.)

### D10. Run records and dump-json carry forward

v3 writes to `data/ingest_runs/{run_id}.json` in the same shape as v2,
extended with the per-type breakdown from D5. `--dump-json` output for
dry-run inspection follows v2's format, again extended with per-type
sections.

### D11. No re-triggering of OCR eyeball gate

Session 11/12 had an "eyeball gate" where a human reviewed Gemini OCR
output before committing. v2 retired that gate after the DFH run proved
OCR quality is stable. v3 inherits the no-eyeball-gate posture because
the OCR call path is identical. New non-OCR handlers (pdfplumber,
openpyxl, python-pptx, python-docx) don't need an eyeball gate at all —
they're deterministic text extraction.

### D12. Per-file quarantine + retry flag (stability at scale)

**The problem this prevents.** v2 got away without per-file failure
handling because it processed 1–2 files per run. v3 will routinely hit
runs with 50+ files across multiple types. Real failure modes include:
Gemini vision rate-limited (429) mid-run, a corrupt PDF that crashes
pdfplumber, a Drive download timeout, an audio file with an unsupported
codec, an embedding API transient 500. Without per-file isolation, one
failure kills the whole run and any preceding work is wasted.

**The design:**

1. **Per-file try/except in the dispatcher.** Each file's handler call
   is wrapped. On exception, the file is recorded with error type,
   message, and traceback truncated to 20 lines. The run continues with
   the next file.
2. **Quarantine directory.** Failed files get an entry in
   `data/ingest_runs/{run_id}.quarantine.json` containing:
   `{drive_file_id, file_name, mime_type, handler, error_type,
   error_message, traceback_truncated, retry_count}`.
3. **`--retry-quarantine {run_id}` flag.** Re-runs only the quarantined
   files from a prior run. Writes a new run record. Successful retries
   update the original quarantine file's `retry_count` and mark the
   file `resolved_in: {new_run_id}`.
4. **Run record shows quarantine in the summary.** Dry-run and commit
   both print: `files seen: N, files ingested: M, files quarantined: K
   (see {run_id}.quarantine.json)`. A non-zero K is not a failure in
   itself — it's a signal to investigate and retry.
5. **Hard failure threshold.** If more than 50% of files quarantine in
   a single run, the dispatcher halts before writing any chunks and
   surfaces the quarantine file to the operator. This is the "something
   is fundamentally broken" detector (bad auth, bad config, dead
   dependency) vs. "a few files have issues."

**Why this goes in from day one, not later.** Adding per-file isolation
to an already-shipped dispatcher is more painful than building it in —
the cost is ~30 lines of code at build time vs. a refactor after the
first 100-file run fails. This is the cheapest place to catch the
class of problem.

**What this does NOT do:** it doesn't retry automatically within a run
(transient failures like 429 are surfaced to the user, not silently
retried). Automatic in-run retry with exponential backoff can be added
later if it becomes a real pain point; for now, explicit retry via
flag is more honest about what happened.

---

## End-to-end proof criterion (Gap 2 closure)

Same shape as Gap 1's session 14 closure proof:

1. User opens admin UI, selects a folder containing the pilot file type
2. UI saves `selection_state.json` (file-level UI optional for the proof —
   folder-level works)
3. `drive_loader_v3 --commit` reads the selection, dispatches by MIME,
   processes one or more files of the pilot type, writes chunks to
   `rf_reference_library`
4. Chunk count rises (e.g., 597 → 600)
5. `rag_server /query` retrieves at least one new chunk as a top-ranked
   result for a query about the pilot file's content
6. Run record on disk at `data/ingest_runs/{run_id}.json` with full per-type
   breakdown
7. Real spend < $0.10 for the pilot
8. No Railway writes
9. Layer B scrub fires correctly on at least one chunk if the pilot file
   contains a collaborator name (or the test file is augmented to ensure
   it does)

---

## Pilot type — DAN PICKS, then continue

v3 design above is type-agnostic. The pilot type — the first handler built
and the file type that closes Gap 2 — is a Dan decision because the answer
depends on what's actually in the reference library on Drive in volume.
This section halts session 15 until Dan picks.

### Candidate pilot types

**Option A — PDF (text-native).** Tech-lead lean.
- **Why:** Likely the highest-volume non-Google-Doc type in the reference
  library. Native text extraction via `pdfplumber` is cheap, deterministic,
  and well-trodden — no vision OCR cost on the happy path. Falls back to
  vision OCR cleanly if a PDF is scanned (gives v3 a built-in escape hatch
  for the small fraction of scanned PDFs).
- **Risk:** scanned PDFs in the library might be more common than expected,
  pushing real cost up. Mitigated by the fallback being explicit and
  cost-tracked, not silent.
- **Rough scope:** ~1 session (handler + dispatcher + scrub validation +
  pilot ingest of one PDF + Gap 2 closure proof).
- **Coverage gain:** large (probably 20–40% of the library by file count,
  guess).
- **Dependency on other types:** none.

**Option B — Loose images** (PNG/JPEG/WebP files in Drive, not embedded
in docs).
- **Why:** Entire OCR path is already proven in v2 (DFH landing page
  image). Handler is essentially "download → existing v2 OCR call → done."
  Smallest possible v3 to ship — would close Gap 2 in maybe half a
  session.
- **Risk:** low coverage gain. Most reference library images are embedded
  in PDFs or Canva exports, not loose files.
- **Rough scope:** ~0.5 session.
- **Coverage gain:** small.
- **Dependency on other types:** none.

**Option C — docx.**
- **Why:** Common business format. `python-docx` is mature. Catches Word
  docs that escaped Google Docs conversion.
- **Risk:** may not be high-volume in this specific library. Inline
  images need vision OCR fallback (familiar path but a second moving
  part).
- **Rough scope:** ~1 session.
- **Coverage gain:** medium-low.

**Option D — Slides (Google Slides + .pptx).**
- **Why:** Visual-heavy presentations are core to how Dr. Nashat teaches.
  If the library has lecture decks, this is high-value content.
- **Risk:** highest-complexity handler. Two sub-formats (Google Slides
  via API, .pptx via python-pptx). Vision OCR on slide images. Speaker
  notes are a separate field. Slide ordering matters for citation
  rendering. Probably 1.5–2 sessions to land.
- **Coverage gain:** depends on library composition.
- **Dependency on other types:** none, but it's the most complex first
  pilot, which carries the highest "v3 plumbing isn't quite right and
  we won't know until the complex handler hits the edge case" risk.

**Option E — Sheets (Google Sheets + .xlsx).**
- **Why:** Lab data, supplement schedules, protocols often live in sheets.
  Native API/`openpyxl` extraction is clean.
- **Risk:** chunking sheets is a different problem than chunking prose —
  row-grouping rules need design work specific to the handler. Citation
  rendering for "row 47 of sheet 'Supplements'" is not the same shape as
  "Module 7, Felice Gersh, MD."
- **Rough scope:** ~1.5 sessions.
- **Coverage gain:** depends on library.

### Tech-lead recommendation: PDF (Option A)

Three reasons:

1. **Highest expected coverage gain per session of work.** PDFs are the
   default container for reference papers, supplement monographs, and
   downloaded handouts. The fertility / functional medicine reference
   space leans heavily on PDFs.
2. **Cleanest happy path.** Native text extraction is deterministic, cheap,
   and well-tested. The fallback (vision OCR per page) is the same Gemini
   path v2 already uses, so the hard part is already proven.
3. **Forces v3 plumbing on a moderate-complexity handler, not an extreme
   one.** Loose images would be too easy to teach v3 anything (single
   vision call, no document structure). Slides would be too hard for a
   first pilot. PDFs sit in the right middle: real document structure
   (pages, paragraph order), real fallback path, real cost tracking, but
   no exotic per-format chunking rules.

### Dan's decision — PDF (Option A), locked session 15

Dan picked PDF as the v3 pilot type. The rest of the staircase is scoped
to PDF. Remaining types (images, docx, slides, sheets, AV) become their
own sessions after session 16 closes Gap 2.

---

## Session staircase (scoped to PDF pilot)

### Session 16 — PDF handler + v3 dispatcher + Gap 2 closure

**Goal:** ship `drive_loader_v3.py` + `types/pdf_handler.py` + the v2
Google Docs adapter, ingest one real PDF from the reference library into
`rf_reference_library`, prove Gap 2 closure with the same rigor as Gap 1.

**Deliverables:**

1. **`ingester/loaders/drive_loader_v3.py`** — dispatcher with:
   - MIME → handler routing table (D2)
   - v2 Google Docs adapter (D2 revised)
   - Per-file try/except + quarantine file writer (D12)
   - 50% hard-fail threshold check
   - OpenAI pre-flight on `--commit` (mirrors v2's session 14 addition)
   - Unified run record writer with `by_handler` breakdown (D5, D10)
   - `--dry-run`, `--commit`, `--dump-json`, `--retry-quarantine {run_id}` flags
   - `--selection-file` flag reading `data/selection_state.json` (D9)

2. **`ingester/loaders/types/__init__.py`** — exports the `extract()`
   protocol + `ExtractResult` dataclass (D3).

3. **`ingester/loaders/types/pdf_handler.py`** — PDF handler:
   - Primary: `pdfplumber` text extraction, page-by-page
   - Fallback trigger: if `extracted_chars / pdf_size_bytes < 5%`, switch
     to vision OCR per page (reuses v2's Gemini vision call via shared
     helper in `_drive_common.py`)
   - Emits `TextBlock` sequence with `display_locator = "p. N"` or
     `"pp. N–M"` per chunk (D7)
   - Section heading detection: best-effort via font-size heuristic
     in pdfplumber; null if detection fails (acceptable per D7)
   - Warnings list: captures scanned-fallback triggers, pages that failed
     to extract, pages with zero text

4. **`scripts/test_scrub_v3_handlers.py`** — new test file:
   - Test 1: feed PDF handler a synthetic PDF containing a scrub pattern
     in native text ("Dr. Christina Massinople"). Assert chokepoint
     output shows `name_replacements ≥ 1`.
   - Test 2: feed PDF handler a scanned PDF (page rendered as image)
     containing the same pattern. Assert OCR-path output shows
     `name_replacements ≥ 1`.
   - Both tests must PASS before any commit-run.
   - Pattern: each future handler appends to this same file.

5. **`rag_server/app.py:format_context()` update** — handle the two new
   display fields (D7). Render `display_locator` and `display_timestamp`
   when present, elide when null. Existing A4M and coaching chunks
   unchanged (verified via a read-only test query against both
   collections, no Chroma writes).

6. **`admin_ui/app.py`, `admin_ui/static/folder-tree.js`,
   `admin_ui/templates/folders.html`** — file-level unlock (D8,
   BACKLOG #2): drop folder-only guard, re-introduce file checkboxes,
   render file rows with type icons.

7. **Gap 2 closure proof run:**
   - Dan selects a folder containing 1+ PDFs via the unlocked UI
     (or hand-edits `selection_state.json` for the proof)
   - `drive_loader_v3 --dry-run` — inspect projected cost, quarantine
     count, per-type breakdown. Halt and show Dan.
   - Dan approves → `drive_loader_v3 --commit`
   - Verify: `rf_reference_library` count rises, new chunks have
     `display_locator` populated, scrub fired if the PDF had a pattern,
     run record written, `by_handler.pdf_text.count > 0`.
   - `rag_server /query` returns at least one new PDF chunk as a top
     result. Citation renders with page locator.

**Cost gate:** $1.00 interactive, $25 hard refuse. PDF pilot projected
spend: < $0.05 for a single PDF of typical reference-library size
(5–50 pages), pdfplumber happy path. Vision OCR fallback would push
this higher (~$0.0003/page); still under gate for reasonable sizes.

**Anti-goals for session 16:**
- NO image/docx/slides/sheets/AV handlers. Session 16 is PDF-only.
- NO modification of v1 or v2. Adapter in v3 calls v2, doesn't alter it.
- NO Railway writes.
- NO touching legacy collections.
- NO shipping file-level UI unlock separately from v3 pilot (they land
  in the same commit so the unlock is immediately useful).

**Session 16 risks:**
- **pdfplumber on a weird PDF.** Mitigated by per-file try/except (D12)
  — one bad PDF quarantines, rest proceed.
- **Section heading detection flaky.** Acceptable — it's best-effort,
  null fallback is fine per D7.
- **v2 adapter coupling.** Mitigated by importing v2's existing
  `process_google_doc` function unchanged. If v2 breaks, v3's Google
  Doc path breaks the same way, which is a feature (one code path).
- **Scrub test file construction.** Building synthetic PDFs with known
  patterns is a small task (reportlab or fpdf2). Scripted once, reused
  for every future handler session.

### Session 17 — Hardening pass (only if session 16 surfaces issues)

**Trigger:** runs session 17 only if session 16's commit run surfaces
any of these:
- Quarantine rate > 10% on a typical folder
- Scrub test fails on a real-world PDF (not just synthetic)
- Citation rendering regression on A4M or coaching chunks
- pdfplumber crashes on a PDF type that isn't cleanly quarantined
- Vision OCR fallback triggers on > 30% of pages in a "normal" PDF

**If none of these surface:** skip session 17 entirely, proceed to
session 18 (next handler type).

**If they do:** session 17 is bounded to fixing the specific issues
found. No new handlers.

### Session 18+ — Remaining handlers, one per session

Pick order (tentative, Dan can re-order when we get there):

- **Session 18:** `image_handler.py` — loose images in Drive. Cheapest,
  reuses v2 OCR directly. Likely < 0.5 session of actual work, so
  session 18 may also cover session 19's item.
- **Session 19:** `docx_handler.py` — python-docx + inline image OCR
  fallback.
- **Session 20:** `slides_handler.py` — Google Slides API + python-pptx,
  per-slide citation shape. Most complex handler; likely spans 1.5
  sessions.
- **Session 21:** (slides continued or) `sheets_handler.py` — Google
  Sheets API + openpyxl, row-grouped chunks.
- **Session 22:** `plaintext_handler.py` — trivial, piggybacks.
- **Session 23+:** `av_handler.py` — audio/video transcription. Separate
  cost tier; likely needs its own cost gate conversation with Dan
  before shipping. Deferred until the text-based handlers are all
  proven in production.

Each session in this range adds:
- One new handler module in `types/`
- One new test case in `test_scrub_v3_handlers.py`
- Closure proof: one real file of that type ingested end-to-end

No session in this range modifies v1, v2, the v3 dispatcher (after
session 16), or the admin UI (after session 16). Handlers are
additive by construction.

### Out-of-scope throughout

- Railway writes (every v3 session is local-only until an explicit
  sync session is scheduled)
- Legacy collection scrub retrofit (BACKLOG #3, its own session)
- Coaching Q&A re-merge (does not exist; see session 9 post-mortem)
- `rf_published_content` collection (separate future thread)
- ADR_006 marker/QPT flag work (still frozen)

---

## What session 15 is NOT doing

To be explicit, session 15 is design + governance only. Session 15:
- Writes this doc (done)
- Updates BACKLOG.md (done, Step 2)
- Updates STATE_OF_PLAY.md (done, Step 3)
- Optionally fixes the two cleanup items: `/chat` 500 and
  `test_login_dan.py` sys.path shim (Step 5 stretch)
- Ends with a handover commit run by Dan

Session 15 does NOT:
- Write any v3 code (`drive_loader_v3.py`, handlers, dispatcher)
- Modify v1 or v2
- Run any ingestion
- Write to any Chroma collection
- Touch Railway
- Build the test_scrub_v3_handlers.py file (it's a session 16 deliverable)

Session 16 starts with a fresh Step 0, reads this doc as its primary
spec, and begins implementation.

