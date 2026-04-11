# HANDOVER — rf_internal_education Build + rf_published_content Build
## Next-Session Entry Point · Written 2026-04-10

---

## ⚠ Updates from 2026-04-11 design pass — READ FIRST

This master plan has been **substantially refined** by the Phase A
design pass on 2026-04-11. The core build goal and the four content
collections are unchanged, but the architecture around them is now
significantly more developed. Read these four ADRs *before* this
master plan — they take precedence where they conflict:

1. **ADR_001_drive_ingestion_scope.md** — RESCOPED. The dedicated
   `RF AI Ingestion Source` drive is no longer being created for
   the current build. Behavioral scoping via the folder-selection
   UI replaces credential-level scoping for non-PHI content. The
   dedicated-drive pattern is reserved for the eventual Clinical
   tier when PHI arrives.
2. **ADR_002_continuous_diff_and_registry.md** — DECIDED. The
   ingester is now built as a continuously-updated content
   management system with a library registry, diff engine, and
   library-aware agents. 14 starter libraries across 4 access
   tiers. Soft-delete with review queue. Replace-on-modify
   versioning with append-only exception for DMs.
3. **ADR_003_canva_dedup.md** — PROPOSED stub. Canva is its own
   Reference-tier library; channels reference it by ID. Detailed
   dedup mechanism (perceptual hashing, version handling) deferred.
4. **ADR_004_folder_selection_ui.md** — DECIDED in principle. A
   web-based folder-tree UI in the admin console drives ingestion;
   the Save button is the primary diff trigger. Built after the
   first inventory walk so it can be designed against real data.

### What changed from this master plan as a result

- **Build sequence:** Phase B is now "share twelve Shared Drives
  with the service account" instead of "create dedicated drive +
  populate shortcuts." Roughly 30 minutes saved per `info@` work
  session.
- **`config.py` PROGRAMS dict:** the hardcoded folder IDs become
  a starter seed for the UI, not the source of truth. The UI's
  selection state in the registry is the source of truth.
- **First ingestion:** still FKSP-pilot via CLI, but the second
  ingestion onwards goes through the new UI.
- **Diff trigger:** the master plan's "manual via Railway CLI"
  becomes "Save button in the UI, with CLI as admin fallback."
- **Library concept:** libraries are now first-class entities in
  the registry. Modes in YAML can reference them by name. Existing
  modes are NOT refactored — new modes get the new pattern, old
  modes keep working.
- **Canva:** treated as a single canonical library, not as
  duplicate content sprawled across IG/blog/lead-magnet folders.

### What did NOT change

- The four content collections (`rf_coaching_transcripts`,
  `rf_reference_library`, `rf_internal_education`,
  `rf_published_content`) — all locked, all going to ChromaDB
- Vertex AI for vision calls
- FKSP-as-pilot
- One-off Railway worker job topology
- The locked decisions in HANDOVER_SESSION_20260411_CLOSE.md

---

## TL;DR for the next Claude session

You are picking up a major content ingestion build for the Reimagined Fertility RAG system. Two new ChromaDB collections are being created:

1. **`rf_internal_education`** — behind-the-paywall course curriculum. Three programs (FKSP 12-week, Fertility Formula 6-week, Preconception Detox 4-week) will be ingested, each including Zoom course videos with slide visuals + voiceover, plus associated PDFs, handouts, workbooks, and worksheets.
2. **`rf_published_content`** — public-facing marketing and lead-magnet content. Canva designs, IG posts/carousels/reels, blogs, nurture emails, and public lead magnets.

This build is distinct from anything you have done before on this project in one critical way: **execution happens on Railway, not locally.** Daniel has explicitly deprecated local-machine execution for ingestion work. Your machine is for writing and committing code; Railway is where it runs.

Before you start implementing anything, read this document end-to-end. The architecture decisions have been made deliberately, and the rationale matters for every downstream choice.

---

## What is already decided (do NOT re-litigate these)

These were decided across the session on 2026-04-10. They are locked in. If Daniel wants to change them later, fine, but do not open them up unprompted:

1. **Execution architecture:** Railway-based worker service. All ingestion runs on Railway. Local Mac is for code authoring only.
2. **Collection strategy for course content:** ONE collection (`rf_internal_education`) for all three programs, with `program` as a required metadata field. NOT three separate collections. Rationale: programs share ~80% of subject matter, cross-program retrieval has value, per-program filtering via `where={"program": "fksp"}` gives the same strictness as separate collections when needed.
3. **Image presentation is a first-class feature.** Every visual asset (slide keyframes, PDF pages, Canva designs, IG content) is stored as a file with a path referenced in chunk metadata. Admin UI will render images alongside retrieved chunks. Not optional, not deferred.
4. **Vision approach for visuals:** Approach 1 (vision-LLM transcription via Gemini 2.5 Flash) for all content. Approach 2 (true multimodal embeddings) is deferred to a future dedicated `rf_bbt_chart_library` build.
5. **Handout routing:** Course-affiliated handouts (PDFs, worksheets, workbooks that ship with a paid program) go in `rf_internal_education` with `asset_type: "handout"`. Canva designs, lead magnets, and public downloadables go in `rf_published_content`. The rule is: **paywall vs. public, determined by whether the asset is bundled with a paid program**.
6. **No more local ChromaDB runs.** Ingestion writes directly to the production ChromaDB on the Railway volume. No more bootstrap-tarball workflow for new content.
7. **Embedding model:** OpenAI `text-embedding-3-large` (3072-dim), same as existing collections for consistency.
8. **FKSP voiceover transcripts will be RE-transcribed from the source videos**, not reused from prior transcription runs. Rationale: clean alignment between voiceover timestamps and video scene-change timestamps, single source of truth.
9. **Parallel pilot:** video pipeline and PDF pipeline are both piloted in Session 2, not sequentially.
10. **Pilot is on a single short FKSP video + a single FKSP PDF**, validated end-to-end before scaling to the full corpus of any program.

---

## What is NOT yet decided (answer these before Session 1 execution)

These are open questions that need Daniel's input before the first build session actually starts:

1. **Railway worker service topology.** Options: (a) new Railway service in the same project sharing the ChromaDB volume, (b) Railway one-off job triggered on-demand, (c) scheduled cron-style job. Recommendation in the Build Plan section below, but Daniel should confirm.
2. **Google Cloud service account setup** — Daniel needs to actually do the clicking in Google Cloud Console (create project, enable Drive API, create service account, download JSON key, share each Drive folder with the service account email). Walk him through it step by step in Session 1. The key itself will go in Railway env vars as `GOOGLE_SERVICE_ACCOUNT_JSON`.
3. **Cost ceiling** — before kicking off any full-program ingestion run, estimate the LLM cost (tokens × asset count × model pricing) and confirm with Daniel. Do not scale to a full program without a cost estimate he has explicitly approved.

---

## Context: what state the project is in before this build starts

**Production state (as of 2026-04-10):**
- Flask admin UI live at https://console.drnashatlatib.com (bcrypt auth, brand-styled)
- Railway deployment running, chroma_db volume at ~485 MB
- `rf_coaching_transcripts` collection: 9,224 chunks, JUST HAD RFID TAGS WIPED (see next section)
- `rf_reference_library` collection: 584 A4M course chunks, intact
- `rf_internal_education` collection: **does not exist yet** — this build creates it
- `rf_published_content` collection: **does not exist yet** — this build creates it

**Local state:**
- Repo at `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/` on branch `main`, clean working tree, in sync with `origin/main`
- Latest commit: `b877236` (docs: update Phase 3 handover after chroma_db upload + bootstrap hardening)
- Local chroma_db at `/Users/danielsmith/Claude - RF 2.0/chroma_db/` — **HAS DIVERGED from Railway prod**. Local has had all RFID tags wiped (3,041 chunks cleared of `client_rfids` and `client_names`). Railway still has the old tagged version. This drift is intentional and will be resolved as part of this build (see "Deferred Railway sync" below).

**Two new backups exist locally and should not be deleted:**
- `chroma_db_backup_20260405` — pre-tagging backup from the Pass 2 resolver session
- `chroma_db_backup_pre_wipe_20260410` — 484 MB, taken before the RFID wipe earlier in today's session

---

## Important: the deferred Railway sync

At the start of today's session, Daniel discovered that the RFID client tags we applied in previous sessions had bad data. We did a full wipe of all `client_rfids` and `client_names` metadata fields across all 3,041 previously-tagged chunks in the local `rf_coaching_transcripts` collection. Verification confirmed: 0 tagged, 9,224 untagged, 9,224 total. Document text and embeddings untouched.

**Railway production still has the old tagged version.** We deliberately deferred the Railway sync because Daniel wanted to batch it with other DB work rather than doing two bootstrap-tarball uploads in a row.

**This build is the "other DB work."** At the end of this build (Session 6 in the plan below), we will do ONE atomic Railway sync that ships:
1. The RFID-cleaned `rf_coaching_transcripts`
2. The newly-built `rf_internal_education`
3. The newly-built `rf_published_content`

All at once, in one bootstrap-tarball operation, using the Phase 3.5 upload playbook documented in `HANDOVER_PHASE3_ARCHIVED_20260409.md`.

**BUT**: if we successfully set up the Railway worker architecture as planned, the ingestion for the new collections will happen *directly against the Railway volume*, not locally. In that case, the only thing that needs the tarball bootstrap is the cleaned `rf_coaching_transcripts`. The new collections will already be on Railway because that's where they were built. This is one of the major benefits of moving to the Railway worker architecture.

---

## The three Google Drive source folders

Daniel provided these parent folder links during the planning session:

- **FKSP (Fertility Kickstart Program — 12 weeks, flagship):** https://drive.google.com/drive/folders/1b_HQqzLCXfOjMXSDB_W2sUF9loJziZ2b?usp=drive_link
- **Fertility Formula (6 weeks):** https://drive.google.com/drive/folders/1_mQFLQS1poldEOfaU1LZC1KnY3dYcgpZ?usp=drive_link
- **4-Week Detox (Preconception Detox):** https://drive.google.com/drive/folders/1ux8JELm29CTsSEPwyC5GM1H4jCVJ7GQU?usp=drive_link

Folders are described as "organized neatly in multiple nested folders" — do not assume a flat structure. Session 1 inventory work will need to walk the tree recursively.

These folders contain:
- Zoom course recordings (video with slides + voiceover)
- Course PDFs
- Handouts
- Workbooks and worksheets
- Possibly other supporting materials

The service account we create will need read access to all three of these parent folders. Share each folder with the service account email after the account is created.

**Canva/public content folders:** not yet identified. Daniel will provide separate folder links for `rf_published_content` sources when we get to that part of the build.

---

## Collection architecture and metadata schemas

### rf_internal_education

**Purpose:** All behind-the-paywall course content from FKSP, Fertility Formula, and Preconception Detox. This is the structured curriculum side of the AI clone.

**Access:** Internal coaching agent only. Public sales agent MUST NOT have access to this collection. The privacy/IP boundary is enforced at the connection layer via the agent YAMLs.

**Metadata schema (every chunk):**

```
program:             "fksp" | "fertility_formula" | "preconception_detox"
asset_type:          "video_slide" | "handout" | "workbook" | "worksheet" | "document"
module:              (string) — module or week identifier within the program
asset_title:         (string) — human-readable name
source_path:         (string) — Drive file ID or path for citation and traceability
slide_index:         (int | null) — for video_slide only: position in deck
slide_start_time:    (float | null) — for video_slide only: seconds from video start
slide_end_time:      (float | null) — for video_slide only: seconds from video start
image_path:          (string | null) — local/Railway path to rendered image of this asset
image_thumbnail:     (string | null) — optional smaller preview
visual_role:         "primary" | "supporting" | "none"
topics:              (pipe-delimited string) — same convention as transcripts
content_type:        "fksp_course" | (reserved for future distinctions)
word_count:          (int)
```

### rf_published_content

**Purpose:** Public-facing marketing content. Canva designs, IG posts/carousels/reels, blogs, nurture emails, public lead magnets. The voice corpus for the public sales agent and the reference library for the Reddit marketing companion.

**Access:** BOTH agents (public sales + internal coaching). This is the primary corpus for the public sales agent.

**Metadata schema (every chunk):**

```
source_type:         "blog" | "ig_post" | "ig_carousel" | "ig_reel_caption" | "nurture_email" | "lead_magnet" | "canva_design"
title:               (string)
publish_date:        (ISO date | null)
url:                 (string | null) — canonical URL if published
campaign:            (string | null) — email sequence name, IG content pillar, etc.
audience:            "ttc" | "general" | "post_loss" | ... (matches archetypes)
topics:              (pipe-delimited)
image_path:          (string | null)
image_thumbnail:     (string | null)
visual_role:         "primary" | "supporting" | "none"
voice_marker:        "nashat_first_person" | "rf_brand_voice" | "guest_contributor"
word_count:          (int)
```

**Note on `voice_marker`:** this is strategically important. It lets retrieval prefer content that's actually in Nashat's first-person voice vs. brand-voice content written by a copywriter. Critical for the Reddit marketing companion and any future AI-clone-voice applications. Do not skip tagging this field.

---

## The ingestion pipeline — end to end

### Pipeline A: Video with slides + voiceover (course videos)

Input: one Zoom course recording (mp4), accessed via Drive API.

1. **Stream download** the video to the Railway worker's temp directory. Stream, don't fully download first if the file is large — use chunked download.
2. **Scene change detection** via ffmpeg or similar → list of `(slide_index, start_time, end_time)` tuples. The existing `run_hq.py` Gemini pipeline already does this for coaching calls; reuse or adapt it.
3. **Keyframe extraction**: one JPG per slide at the midpoint of its time range. Target resolution: 1280x720 or native if smaller. Quality: JPEG 85. Store at `assets/internal_education/{program}/{module}/slide_{index:03d}.jpg`.
4. **Audio extraction**: pull the audio track to a temporary .wav or .mp3.
5. **Speech-to-text**: transcribe the audio with timestamps. Use the same transcription approach already in use on this project. Output: list of `(start_time, end_time, text)` segments.
6. **Per-slide enrichment via Gemini 2.5 Flash vision call**: for each keyframe, prompt Gemini for:
   - Literal transcription of all on-screen text
   - Visual description (layout, diagrams, emphasis, mood)
   - Identified teaching concept / key message
   - Any numerical data, tables, or frameworks visible
7. **Voiceover slicing**: for each slide, pull the transcript segments whose timestamps fall within `[slide_start_time, slide_end_time]`. Concatenate.
8. **Chunk composition**: build a fused chunk per slide containing:
   - Slide visual description + on-screen text (from step 6)
   - Voiceover text for that slide (from step 7)
   - Full metadata per the schema above
9. **Context-aware chunking pass**: run each composed chunk through the Haiku-powered context wrapper already in use for the coaching transcripts. This gives each chunk its surrounding context for retrieval.
10. **Embed** via OpenAI `text-embedding-3-large`.
11. **Store** in `rf_internal_education` via the ChromaDB client connected to the Railway volume.
12. **Cleanup**: delete the local video, audio, and scratch files from the worker's temp directory. Keep only the slide keyframes (they go into the asset directory for display).
13. **Update manifest**: mark this video as `done` with chunk count.

### Pipeline B: PDF — text-heavy (workbooks, documents)

Input: one PDF, accessed via Drive API.

1. **Stream download** the PDF to temp.
2. **Text layer extraction** via `pdfplumber` or `pypdf`. If text extraction returns empty or near-empty (scanned PDF without OCR layer), route to Pipeline C instead.
3. **Document-level metadata extraction**: title, author, page count, creation date.
4. **Section-aware chunking**: split on major headings where detectable, fall back to page-based chunking (1 page = 1 chunk) if no heading structure. Maximum chunk size ~500 words; merge small sections with adjacent ones.
5. **Overview chunk**: also generate one 200-400 word summary chunk of the whole document. Tag it with `visual_role: "none"` and `asset_type: "handout"` (or appropriate type). This improves retrieval for "do you have anything about X" queries.
6. **Context-aware chunking pass**: same Haiku wrapper as Pipeline A.
7. **Embed and store** in `rf_internal_education` (or `rf_published_content` for public PDFs).
8. **Cleanup**: delete the local PDF.

### Pipeline C: PDF — visual / designed (handouts, lead magnets, Canva exports, scanned)

Input: one visually-designed PDF, accessed via Drive API.

1. **Stream download** the PDF.
2. **Page rendering**: render each page as a PNG at 150 DPI using `pdf2image` or similar. Store at `assets/{collection}/{program_or_category}/{asset_name}/page_{index:03d}.png`.
3. **Text layer extraction**: if a text layer exists, pull it. Do not rely on it being complete.
4. **Per-page vision enrichment via Gemini 2.5 Flash**:
   - Literal transcription of all visible text (catches text the PDF layer missed)
   - Visual description
   - Key message
5. **Merge**: for each page, combine extracted text + vision description into one chunk.
6. **Overview chunk**: 200-400 word summary of the whole asset.
7. **Context-aware chunking, embed, store.**
8. **Cleanup**: delete the PDF, KEEP the rendered page images for display.

### Pipeline D: IG content, Canva standalone designs, image-only assets

Input: one image file (PNG/JPG) or set of images (carousel).

1. **Download** to temp.
2. **Copy image(s)** to `assets/{collection}/{category}/{asset_name}/` (keep them, don't delete).
3. **Vision enrichment**: Gemini describes visual + transcribes text + identifies key message. For carousels, describe each slide in sequence within a single chunk.
4. **Accompanying text**: if the asset has a caption, alt text, or description pulled from the source (IG export, Canva export), include it in the chunk.
5. **Chunk composition**: one chunk per standalone asset OR per carousel (not per carousel slide). A carousel is one piece of content; splitting slide-by-slide loses the narrative.
6. **Embed and store** in `rf_published_content`.

---

## Railway worker architecture

### Why a separate worker service

The existing Railway service runs the Flask admin UI 24/7. It's small, cheap, and should stay that way. Running ingestion jobs in that same service would:
- Block the admin UI during long jobs
- Risk timeouts killing ingestion mid-run
- Mix concerns (serving vs. batch processing)

A separate worker service in the same Railway project shares the ChromaDB volume but runs as an on-demand job.

### Proposed topology

**Service 1 (existing):** `rf-nashat-admin` — Flask admin UI. Always on. Reads ChromaDB from the shared volume.

**Service 2 (new):** `rf-nashat-ingester` — Python worker. Normally idle. Triggered manually via Railway CLI or dashboard to run ingestion jobs. Reads from Google Drive (service account), writes to ChromaDB on the shared volume, writes assets to the shared volume's `assets/` subdirectory.

**Shared volume:** both services mount the same Railway volume containing `chroma_db/` and `assets/`. The admin UI reads, the worker writes.

### Worker script structure

One entry-point script with subcommands:

```
python -m ingester.main inventory --program fksp
python -m ingester.main pilot --program fksp --asset <drive-file-id>
python -m ingester.main ingest --program fksp --pipeline video
python -m ingester.main ingest --program fksp --pipeline pdf
python -m ingester.main ingest --all
python -m ingester.main status
python -m ingester.main verify --program fksp
```

Each subcommand does one thing, can be run independently, and is fully resumable (reads the manifest, skips completed items).

### Resumability pattern

Every ingestion run uses a manifest file at `/data/manifests/{program}_{timestamp}.json`:

```json
{
  "program": "fksp",
  "started_at": "2026-04-15T10:00:00Z",
  "assets": [
    {
      "drive_file_id": "1abc...",
      "path": "FKSP/Module 1/Lesson 1 Introduction.mp4",
      "type": "video",
      "status": "done",
      "chunks_written": 23,
      "started_at": "...",
      "completed_at": "...",
      "error": null
    },
    {
      "drive_file_id": "1def...",
      "path": "FKSP/Module 1/Workbook.pdf",
      "type": "pdf_text",
      "status": "in_progress",
      "chunks_written": 0,
      "started_at": "...",
      "completed_at": null,
      "error": null
    }
  ]
}
```

On restart after a crash: load the manifest, skip `done` items, retry `in_progress` (assume they were interrupted), process `pending` in order. Never re-process `done` items unless explicitly told to via `--force`.

### Google Drive service account setup (do this in Session 1)

**Walk Daniel through these steps in the first session before any code runs:**

1. Go to https://console.cloud.google.com/
2. Create a new project named "rf-rag-ingester" (or use existing if he has one)
3. Enable the Google Drive API: APIs & Services → Library → search "Google Drive API" → Enable
4. Create a service account: IAM & Admin → Service Accounts → Create Service Account. Name it `rf-ingester@{project-id}.iam.gserviceaccount.com`
5. Grant role: no project-level roles needed (we'll use Drive sharing instead)
6. Create a JSON key for the service account, download it, and **immediately** store it as a Railway env var called `GOOGLE_SERVICE_ACCOUNT_JSON` (paste the entire JSON content as the value)
7. **Delete the local copy** of the JSON key after copying it into Railway. Do not commit it to the repo. Do not leave it in Downloads.
8. Copy the service account email address (it looks like `rf-ingester@{project-id}.iam.gserviceaccount.com`)
9. In Google Drive, right-click each of the three program folders and share them with the service account email as "Viewer"
10. In Railway, set the env var and redeploy the ingester service so it picks up the credential

**Security note:** this service account will only have access to folders explicitly shared with it. It cannot see Daniel's other Drive content. That's the whole point of service accounts over OAuth — tight, explicit, scoped access.

**Credential hygiene:** Daniel has previously leaked API keys in chat. Do NOT paste the service account JSON into chat, ever, under any circumstances. If Daniel offers to paste it, stop him and redirect to the Railway dashboard.

---

## Session-by-session build plan

### Session 1 — Setup and inventory (no ingestion yet)

**Goal:** Everything that is not "running the pipeline" is in place and verified.

1. Walk Daniel through the Google Cloud service account setup (above). Verify Railway env var is set.
2. Create the new Railway service `rf-nashat-ingester` in the same project. Configure it to mount the same ChromaDB volume. Leave it idle (no active deployment yet).
3. Create the repo scaffold for the ingester:
   ```
   rf-nashat-clone/
     ingester/
       __init__.py
       main.py                  # CLI entry point
       drive_client.py          # service account Drive wrapper
       pipelines/
         __init__.py
         video.py               # Pipeline A
         pdf_text.py            # Pipeline B
         pdf_visual.py          # Pipeline C
         image.py               # Pipeline D
       chunking.py              # shared chunking utilities (import from existing transcript chunker)
       embedding.py             # OpenAI embedding client
       storage.py               # ChromaDB writer
       manifest.py              # resumability state tracker
       config.py                # collection names, model names, paths
     ingester_requirements.txt
   ```
4. Write `drive_client.py` first — it is the foundation of everything. Test it by running `inventory --program fksp` and confirming the script can walk the FKSP folder tree and list files with their IDs, types, and sizes.
5. Generate the inventory report: a JSON file listing every asset across all three programs, categorized by pipeline (video / pdf_text / pdf_visual / image / other).
6. Rough cost estimate: `(video count × average slides × Gemini vision tokens) + (PDF count × average pages × Gemini vision tokens) + (total chunks × OpenAI embedding tokens)`. Present the estimate to Daniel before Session 2.
7. Commit and push. Tag this commit as `v0.4.0-inventory` or similar.

**Session 1 deliverable:** the inventory report + the cost estimate + a working `drive_client.py`. No ingestion yet. Daniel approves the cost before Session 2 starts.

### Session 2 — Parallel pilot (video + PDF on FKSP)

**Goal:** Validate both primary pipelines on real FKSP content before scaling.

1. Pick the shortest FKSP course video from the inventory. Pick one FKSP PDF (prefer a handout that is clearly visually-designed, so we are exercising Pipeline C, not just B).
2. Implement Pipeline A (video). Run on the pilot video. Inspect the resulting chunks:
   - Did slide boundary detection work? How many slides did it find?
   - Does the vision-LLM output match what is actually on each slide?
   - Is the voiceover correctly sliced per slide?
   - Do the composed chunks read coherently?
   - Are slide keyframes stored at the expected paths?
3. Implement Pipeline C (visual PDF). Run on the pilot PDF. Inspect:
   - Are page images rendered cleanly?
   - Does the vision output cover what is on each page?
   - Do the chunks read like useful knowledge, not just "there is a page with some text"?
4. Run retrieval smoke tests through the admin UI:
   - "What does the FKSP course teach about [topic from the pilot video]?"
   - "Show me the handout about [topic from the pilot PDF]"
   - Confirm the right chunks come back, with the right images attached.
5. If anything is weak, tune prompts and re-run on the same pilot. Do not scale until pilot quality is genuinely good.

**Session 2 deliverable:** one video and one PDF fully ingested into `rf_internal_education` on Railway, with retrieval validated and images rendering in the admin UI.

### Session 3 — Admin UI image rendering + FKSP full ingestion

**Goal:** Finish the UI work and ingest all of FKSP.

1. Update the admin UI test panel to render images alongside retrieved chunks when `image_path` is populated. Serve images via a new Flask route behind the existing bcrypt auth. Style to match the brand (Santorini script typography, copper/ivory/navy).
2. Run the full FKSP ingestion. Both video and PDF pipelines. Monitor progress via Railway logs and ChromaDB count as progress proxy.
3. Spot-check ~10 random chunks across the full ingestion for quality.
4. Commit and push everything.

**Session 3 deliverable:** all FKSP content live in `rf_internal_education`, admin UI renders images, quality spot-checked.

### Session 4 — Fertility Formula + Preconception Detox ingestion

**Goal:** Ingest the remaining two programs using the validated pipelines.

1. Run full ingestion on Fertility Formula.
2. Run full ingestion on Preconception Detox.
3. Cross-program retrieval validation: run queries like "compare how all three programs teach the luteal phase" and confirm the results draw from all three programs with correct attribution.
4. Verify metadata counts per program match expectations from the Session 1 inventory.

**Session 4 deliverable:** all three programs fully live in `rf_internal_education`.

### Session 5 — rf_published_content build

**Goal:** Build the public-facing content collection.

1. Daniel provides Drive folder links for Canva content, IG exports, blogs, nurture emails, lead magnets.
2. Inventory those folders.
3. Run the appropriate pipelines (D for images, B or C for PDFs, a new simple pipeline for text-only blog/email content).
4. Ingest into `rf_published_content`.
5. Validate retrieval through the admin UI.

**Session 5 deliverable:** `rf_published_content` collection fully populated.

### Session 6 — Agent integration + deferred Railway sync

**Goal:** Wire the new collections into the agent YAMLs and close out the RFID wipe from 2026-04-10.

1. Update `nashat_coaching.yaml`:
   - New mode `fksp_curriculum` (queries `rf_internal_education` with `program=fksp` filter)
   - New mode `fertility_formula_curriculum`
   - New mode `preconception_detox_curriculum`
   - New mode `all_programs` (queries `rf_internal_education` with no program filter)
   - New mode `published_content` (queries `rf_published_content`)
   - Update any existing modes that should pull from multiple collections
2. Update `nashat_sales.yaml`:
   - New mode `published_content` (queries `rf_published_content`) — this becomes the primary mode for the sales agent
   - **Do NOT add access to `rf_internal_education`.** The privacy/IP boundary applies.
3. Test every new mode through the admin UI test panel.
4. Sync the RFID-cleaned `rf_coaching_transcripts` from local to Railway. Options:
   - **(a) Tarball bootstrap** (same as Phase 3.5 playbook): tar local chroma_db, host temporarily, set `CHROMA_BOOTSTRAP_URL`, redeploy, tear down. Atomic swap.
   - **(b) Run the RFID wipe script directly against Railway's volume** via the ingester worker. Write a small script that re-runs the wipe logic on Railway's DB. Only if (a) is impractical for some reason.
5. Verify production: RFID count = 0 on `rf_coaching_transcripts`, all three programs populated in `rf_internal_education`, `rf_published_content` populated.
6. Commit the final build, tag the release, write a closing status doc.

**Session 6 deliverable:** entire build shipped to production. Full AI clone with coaching transcripts, A4M reference library, three-program course curriculum, and public content library. All agent modes wired. RFID drift between local and Railway resolved.

---

## Cost modeling

Before committing to full runs, estimate costs per program using these inputs. Numbers below are approximations as of April 2026 and should be verified against current pricing in Session 1.

**Gemini 2.5 Flash (vision calls):**
- Approximately $0.075 per 1M input tokens, $0.30 per 1M output tokens
- Each slide keyframe ≈ 250-500 input tokens (image) + 200 prompt tokens + 300-500 output tokens
- Per slide: roughly $0.0002-0.0005 in raw cost

**OpenAI text-embedding-3-large:**
- Approximately $0.13 per 1M tokens
- Each chunk ≈ 300-500 tokens
- Per chunk: roughly $0.00005-0.00008

**Claude Haiku (context-aware chunking):**
- Current pricing applies
- Each chunk wrapper call ≈ 500 input tokens + 200 output
- Per chunk: roughly $0.0002-0.0004

**Rough per-program estimate (order of magnitude only):**
- Assume 20 videos × 40 slides/video = 800 slide chunks
- Assume 30 PDFs × 10 pages/PDF = 300 page chunks
- Total ≈ 1,100 chunks per program
- Vision calls: 1,100 × $0.0003 = ~$0.33
- Embedding: 1,100 × $0.00007 = ~$0.08
- Chunking: 1,100 × $0.0003 = ~$0.33
- **Per program: probably $1-3 total**
- **All three programs: probably $5-15 total**

These are small numbers. The expensive part would be iterating — re-running the full ingestion because a prompt was wrong. Pilot-first discipline in Session 2 protects against that.

**Railway compute:** the worker service runs intermittently. Estimate maybe 5-10 hours of active compute total across all sessions. At Railway's current pricing that is pennies.

**Total expected cost for the entire rf_internal_education + rf_published_content build: well under $50.** If it starts looking like it will exceed $100, stop and reassess.

---

## Technical gotchas and lessons from prior sessions

1. **Long-running processes exceed MCP timeout (~4 min).** When running scripts from the local Mac during development, use the background + polling pattern: `ps aux | grep [script]` plus ChromaDB collection count as a progress proxy.

2. **Desktop Commander REPL struggles with long multi-line inputs.** When writing large files during development, load content in chunks, concatenate in variables, then write with a single `f.write()` call. This document was written that way.

3. **macOS adds `com.apple.provenance` xattr to files**, which accounts for ~180 bytes of on-disk-vs-in-memory size discrepancy. Git does not see xattrs, so commits are unaffected. Ignore the discrepancy.

4. **Google Drive MCP tooling is unreliable for cross-account content.** This is precisely why we are moving to service account access via the Drive API directly, not via MCP.

5. **Credentials should never appear in chat.** Both Anthropic and OpenAI keys were leaked in previous sessions and had to be rotated. Treat any credential pasted in chat as compromised. Guide Daniel to paste directly into Railway env vars, never into the conversation.

6. **Full absolute paths required with Desktop Commander** — relative paths fail.

7. **The `with open(...) as f:` multi-line pattern in Python REPL often confuses the REPL state.** Use the `f = open(...); f.write(x); f.close()` pattern instead for REPL work.

8. **Daniel is a self-described novice coder who relies on AI and logic.** Explain technical concepts in plain language before implementing. Check in at decision points rather than charging ahead. Do not assume technical context.

---

## What goes in the repo after this build

After Session 6, the repo structure should look like:

```
rf-nashat-clone/
  admin/                       # existing Flask admin UI
  ingester/                    # NEW: the ingestion worker
    main.py
    drive_client.py
    pipelines/
    chunking.py
    embedding.py
    storage.py
    manifest.py
    config.py
  config/                      # existing Pydantic schemas
  agents/                      # YAMLs (updated with new modes)
  scripts/                     # existing one-off scripts
  HANDOVER_PHASE3_ARCHIVED_20260409.md
  HANDOVER_PHASE3_COMPLETE.md
  HANDOVER_INTERNAL_EDUCATION_BUILD.md  # THIS DOCUMENT
  HANDOVER_INTERNAL_EDUCATION_COMPLETE.md  # written at end of Session 6
  README.md
  ingester_requirements.txt    # NEW
  requirements.txt             # existing
```

The Railway volume (not in the repo) should contain:

```
/data/
  chroma_db/                   # the vector store
  assets/
    internal_education/
      fksp/
      fertility_formula/
      preconception_detox/
    published_content/
      canva/
      ig/
      blogs/
      lead_magnets/
  manifests/                   # ingestion run state
```

---

## Strategic significance (do not skip this section)

This build is probably the single highest-leverage data move on the RF roadmap right now. Here is why the next session should treat it with the weight it deserves:

1. **Patent strategy.** The FKSP methodology, including the 25 QPTs, is core IP. A fully-structured, AI-queryable representation of the course curriculum — with videos, slides, voiceover, and supporting materials all linked and retrievable — strengthens the "proprietary clinical methodology" argument in any patent claim. It is tangible proof that the methodology exists not just as "something Nashat teaches" but as a structured, machine-readable, reproducible knowledge base.

2. **Clinic pilot deck.** When pitching IVF/IUI clinics, the ability to say "our AI teaches patients the same structured methodology our certified practitioners teach — here are the actual slides from the course, here is how the system retrieves and presents them" is a fundamentally different pitch than "our AI answers questions well." It turns the AI clone from a chatbot into a credential-backed clinical tool.

3. **App lesson delivery.** The slide+voiceover fusion is the data layer the app's curriculum module will eventually consume. Building this collection correctly means the app build is not starting from scratch later — it is reading from an already-structured source. Same effort, two downstream consumers.

4. **Voice fidelity for the AI clone.** Until now, the AI clone has represented Nashat's voice through coaching transcripts (how she talks to clients) and the A4M reference library (authoritative medical content). Adding the course curriculum gives the clone what it teaches, in Nashat's structured voice, with her frameworks and her visual explanations. This is the curriculum backbone that was missing.

5. **Published content powers the Reddit marketing companion.** The `rf_published_content` collection, especially the `voice_marker: "nashat_first_person"` subset, is exactly the reference material the Reddit responder needs to draft VA-posted responses that genuinely sound like Nashat. Building this now makes that downstream workflow much more powerful with no additional effort.

6. **Cross-program comparative intelligence.** Once all three programs are in one collection, the AI clone can answer queries like "how has the methodology evolved from Preconception Detox to Fertility Formula to FKSP?" — a comparative capability that is uniquely valuable for Nashat's own teaching, for marketing (showcasing depth and evolution), and for any certification/training work she might pursue.

Treat this build with the care it deserves. Do not cut corners on the pilot. Do not scale until the pilot is genuinely good. Do not skip the cost estimate. Do not bypass Daniel's approval gates.

---

## Resume prompt for the next Claude session

Paste this at the start of the next session to give the next Claude full context:

> We are continuing the Reimagined Fertility RAG build. Please read the following files in order before doing anything:
>
> 1. `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/HANDOVER_INTERNAL_EDUCATION_BUILD.md` (the master plan)
> 2. `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/HANDOVER_PHASE3_COMPLETE.md` (the production architecture from Phase 3.5)
> 3. `/Users/danielsmith/Claude - RF 2.0/HANDOVER_PROMPT.md` (the project-level master handover)
>
> The immediate next step is Session 1 of the internal education build: Google Cloud service account setup, Railway ingester service creation, repo scaffolding for the `ingester/` package, and the inventory + cost estimate pass across the three program Drive folders. Do NOT start any actual ingestion until Daniel has approved the cost estimate.
>
> Open decisions Daniel needs to answer in Session 1 before you proceed past scaffolding:
> (a) Railway worker topology (separate service vs. one-off job vs. cron)
> (b) Cost ceiling approval after the inventory pass
>
> Do not re-litigate any of the architectural decisions in the "What is already decided" section of the master plan. They are locked.

---

*Document end. Written 2026-04-10 at the close of the RFID wipe + rf_internal_education planning session. Next session begins with the service account setup.*
