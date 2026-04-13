# Drive Loader v2 — HTML export + Gemini vision OCR

**Status:** Approved by Dan at session 11 start. Builds on v1 (`docs/plans/2026-04-13-drive-loader-pilot.md`).
**Written:** 2026-04-13 (session 11)
**Author:** Claude (tech-lead, under mandate)
**Predecessor:** v1 drive_loader — text-only, conservative by default, skips image-heavy docs via `low_text_yield` guard

---

## Why v2 exists

v1 proved the Drive ingestion plumbing works end-to-end (auth, walk, chunk, metadata, guards, dump-json) but exposed a structural limitation: Drive's `text/plain` export of Google Docs is lossy on image-heavy content. The Supplement Info pilot's two most substantive docs exported at 0.07% and 0.45% yield because their actual content — supplement product names, doses, substitution recommendations — lives inside embedded product images and Canva-designed infographics that don't survive text export.

v1's low-yield guard correctly skips these files rather than ingesting misleading fragments. But "skipped" is not "ingested," and most of Dr. Nashat's reference content is built this way. v2 is what unblocks Drive ingestion as a real pipeline for RF reference material.

---

## Scope

**v2 DOES:**
- Ingest image-heavy Google Docs by switching from `text/plain` export to `text/html` export
- Parse HTML in document order, preserving prose + image positions
- Download each embedded image via authorized Drive access
- OCR each image via Gemini 2.5 Flash (Vertex AI, `google-genai` SDK)
- Cache OCR results on disk by image SHA-256 so re-runs are free
- Stitch image descriptions back into the text stream as `[IMAGE #N: ...]` markers
- Track embedding cost (as v1) AND vision cost separately
- Apply a v2 low-yield guard that uses the stitched length (so files passing v2 are genuinely empty, not just image-trapped)

**v2 does NOT:**
- Replace v1 — v1 stays as a fast path for text-only docs
- Support PDFs, Google Slides, direct image files, or spreadsheets (all deferred to v3)
- Push to Railway (local Chroma only this session)
- Re-ingest files already in Chroma (chunk-ID-level upsert handles that for free)

---

## Auth path (locked)

**Vertex AI via `google-genai` SDK**, project `rf-rag-ingester-493016`, region `us-central1`, service account `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`, credentials at `/Users/danielsmith/.config/gcloud/rf-service-account.json`.

Verified end-to-end in session 11 Step 0 smoke test. `roles/aiplatform.user` granted by Dan between sessions 10 and 11.

**NOT used:** `google-generativeai` (AI Studio API key path), `vertexai.generative_models` (deprecated June 2026). The `google-genai` SDK in Vertex AI mode is the only code path.

---

## Key decisions

### D1. Sibling module + shared common, not a flag

v2 lives at `ingester/loaders/drive_loader_v2.py`. A new `ingester/loaders/_drive_common.py` holds shared helpers (`normalize_text`, `chunk_text`, `build_chunk_id`, `build_metadata`, `assert_local_chroma_path`, `load_and_validate_selection`, manifest lookup). v1 is patched to import from `_drive_common` with zero behavior change; a v1 dry-run regression test confirms byte-for-byte equivalence before any v2 code runs.

### D2. `google-genai` SDK, Vertex AI mode

See auth path section above.

### D3. BeautifulSoup + `html.parser`

No `lxml`. Stdlib parser is sufficient — Google Doc HTML export is well-formed. Document order preserved by walking the parse tree; prose and `<img>` tags are emitted as an ordered stream.

### D4. Image delivery to Gemini: bytes, not URLs

Drive HTML export references images as `googleusercontent.com` URLs that need authenticated access. Rather than handing auth to Gemini, we download the bytes with the existing `DriveClient`'s authorized session, then pass `{bytes, mime_type}` to `client.models.generate_content`. Deterministic, auth-contained.

### D5. SHA-256 keyed disk cache

Cache location: `data/image_ocr_cache/{sha256}.json`. Key is the SHA-256 of the image **bytes**, not the URL (URLs in HTML exports are signed and expire; bytes are stable). Cache entry shape:

```json
{
  "sha256": "...",
  "model": "gemini-2.5-flash",
  "prompt_version": "v1",
  "mime_type": "image/png",
  "byte_size": 123456,
  "ocr_text": "...",
  "is_decorative": false,
  "vision_input_tokens": 257,
  "vision_output_tokens": 142,
  "created_at": "2026-04-13T..."
}
```

Two images with the same bytes — even across different docs — are OCR'd once. A `--no-cache` flag exists for debugging.

### D6. OCR prompt — v1 (Canva-aware)

Versioned. Bumping `prompt_version` invalidates prior cache entries automatically.

```
You are extracting text and visual information from a fertility-medicine reference document.

Describe what this image shows. Handle each category below:

1. If the image contains a PRODUCT (supplement bottle, package, label, box):
   transcribe all visible text verbatim — brand name, product name, dose,
   serving size, ingredient list, claims. Do not summarize.

2. If the image is an INFOGRAPHIC, chart, diagram, or designed visual
   (including Canva-style content): transcribe all visible text preserving
   logical reading order and hierarchy. Capture headings, bullet points,
   labels, numeric data, and any text associated with icons or illustrations.
   Do not summarize — transcribe.

3. If the image is a MEDICAL/CLINICAL figure (lab reference range chart,
   anatomy diagram, protocol flowchart): transcribe labels, values, and
   any legend or caption text.

4. If the image is PURELY STRUCTURAL (horizontal divider, solid color
   block, single decorative icon with no text, ruler line, spacer):
   reply with exactly: DECORATIVE

Return plain text only. No commentary, no speculation about content
not visible. Preserve the document's own terminology.
```

### D7. Stitched-text format

Each non-decorative image description is inserted inline at its document position:

```
[IMAGE #3: Pure Encapsulations B-Complex Plus, 60 capsules, 1 capsule
daily. Contains B1 3mg, B2 1.7mg, B6 20mg, folate 400mcg (as Metafolin),
B12 1000mcg (methylcobalamin).]
```

The `[IMAGE #N: ...]` wrapper is the contract: downstream chunker treats it as prose; downstream retrieval/agent can tell image-derived text from doc-prose text. `DECORATIVE` responses are dropped from the stream entirely (not wrapped).

### D8. Metadata additions

Two new fields added by v2's metadata builder:
- `source_pipeline = "drive_loader_v2"` (replaces v1's `"drive_loader_v1"` constant)
- `image_derived_word_count: int` — word count of `[IMAGE #N: ...]` text inside this specific chunk (zero for prose-only chunks)

All other metadata fields identical to v1. The read-time normalizer and `display_*` fields work unchanged.

### D9. Low-yield guard v2

Same 5% threshold, same 10 KB floor, but numerator is `len(stitched_text)` (which includes image-derived content). A doc that was 0.07% yield on v1 should pass comfortably on v2. If it *still* fails v2, reason becomes `low_yield_even_with_vision` — clear signal the file is genuinely un-ingestible (empty, locked, unsupported internal format).

### D10. Cost tracking

Per-file and per-run:
- Embedding cost — same as v1 (text-embedding-3-large)
- Vision cost — separate: `{images_seen, images_ocr_called, images_cache_hit, vision_input_tokens, vision_output_tokens, vision_cost_usd}`

Gemini 2.5 Flash pricing constants (Vertex AI, verify at build time):
- Input: $0.075 per 1M tokens (text + image tokens)
- Output: $0.30 per 1M tokens
- Per-image token cost: ~258 tokens fixed (image encoding)

### D11. Cost gates

- Dry-run: projected vision cost > $1.00 → print warning but proceed (dry-run is the only way to iterate the prompt, and the spend is real)
- Commit: projected vision cost > $1.00 → require interactive `y/N`
- Commit: projected vision cost > $25.00 → hard refuse unless `--allow-strategic-spend` flag passed
- Hard cost ceilings match the session 11 prompt's numbers exactly

### D12. Per-image error handling

If Gemini errors on a specific image (quota, safety block, transient 5xx):
- Log the error
- Insert `[IMAGE #N: OCR_FAILED — <reason>]` as a placeholder so chunk alignment is preserved
- Continue processing the file
- Append error details to per-run `vision_errors: list[dict]` in the run record

**Per-file fallback gate:** if > 20% of images in a single file fail OCR, skip the file entirely with reason `vision_failure_rate_too_high`. The partial chunks are not written.

### D13. Dry-run calls Gemini for real

The "dry" in dry-run is "no Chroma writes, no embeddings" — not "no Gemini spend." Real Gemini calls happen during dry-run because:
1. Prompt iteration requires eyeballing actual outputs
2. Dump-json is meaningless without real OCR text in it
3. Expected pilot dry-run spend is $0.05–$0.15, well under any gate

Approved by Dan in design review.

### D14. No decorative-image bypass

Call Gemini on every image. Canva infographics can be small-filesize but substantively critical — any size/format heuristic risks dropping the actual reference content. Let the model itself decide `DECORATIVE` vs transcription. Cost delta is trivial (~20% more vision calls, ~$0.01 on the pilot).

---

## Flow (pseudocode)

```
for each selected folder:
    list children via DriveClient (unchanged from v1)
    for each Google Doc:
        html_bytes = drive.files().export(mimeType="text/html")
        soup = BeautifulSoup(html_bytes, "html.parser")

        stream = []  # ordered list of (kind, payload)
        image_counter = 0
        for element in walk_body_in_order(soup):
            if element.is_text_block:
                stream.append(("text", element.get_text()))
            elif element.is_image:
                image_counter += 1
                img_bytes, img_mime = download_image(element["src"], drive_auth)
                sha = sha256(img_bytes)
                if cache.has(sha, prompt_version):
                    ocr_result = cache.get(sha)
                else:
                    ocr_result = gemini.ocr(img_bytes, img_mime, prompt_v1)
                    cache.put(sha, ocr_result)
                if ocr_result.is_decorative:
                    pass  # drop from stream
                elif ocr_result.failed:
                    stream.append(("image", f"[IMAGE #{image_counter}: OCR_FAILED — {ocr_result.reason}]"))
                else:
                    stream.append(("image", f"[IMAGE #{image_counter}: {ocr_result.text.strip()}]"))

        stitched = stitch_stream(stream)  # preserves paragraph structure
        stitched = normalize_text(stitched)  # v1's helper, unchanged

        if low_yield_v2_guard(stitched, drive_size_bytes):
            skip with reason "low_yield_even_with_vision"
            continue

        if vision_error_rate_too_high:
            skip with reason "vision_failure_rate_too_high"
            continue

        chunks = chunk_text(stitched)  # v1's helper, unchanged
        for chunk in chunks:
            meta = build_metadata_v2(chunk, ..., image_derived_word_count=count_image_words(chunk))
            write chunk with v2 metadata
```

---

## Pilot success criteria

Against the Supplement Info folder, specifically the **Comprehensive List of Supplements and substitutions** doc (4.3 MB, 0.07% v1 yield):

1. Ingestion proceeds past the v2 low-yield guard (stitched yield > 5%)
2. Dump-json contains `[IMAGE #N: ...]` markers with recognizable supplement brand names — Pure Encapsulations, Thorne, Designs for Health, Metagenics, Douglas Labs, etc.
3. Chunks are coherent — a product name and its substitution recommendation appear in the same chunk, not split across boundaries
4. Total vision cost across the folder < $1.00
5. `Supplement Details` doc (0.45% v1 yield) also passes v2 guard and produces usable chunks

**If any criterion fails, halt before commit-run and debug.**

---

## File layout

**New:**
- `ingester/loaders/drive_loader_v2.py` — v2 entry point
- `ingester/loaders/_drive_common.py` — shared helpers (extracted from v1 body)
- `ingester/vision/__init__.py`
- `ingester/vision/gemini_client.py` — wraps `google-genai` Vertex AI client, prompt template, cost accounting
- `ingester/vision/ocr_cache.py` — SHA-256 keyed disk cache
- `data/image_ocr_cache/` — runtime dir (gitignored)

**Modified:**
- `ingester/loaders/drive_loader.py` — import shared helpers from `_drive_common`. Behavior-preserving refactor only.
- `.gitignore` — add `data/image_ocr_cache/`

**Untouched:**
- `ingester/config.py` (already has `VISION_MODEL`, `GCP_PROJECT_ID`, `VERTEX_AI_REGION`)
- `ingester/drive_client.py`
- `admin_ui/`, `rag_server/`
- Any ChromaDB collection
- Any doc under `docs/` except this file

---

## Hard rules carried forward from v1

- Refuses `/data/*` Chroma paths (Railway production guard)
- Refuses placeholder `["abc","def"]` selection
- Refuses missing library assignments
- Refuses libraries outside `ALLOWED_LIBRARIES`
- `--dry-run` is the default; `--commit` must be explicit
- Requires `OPENAI_API_KEY` for `--commit`
- Chunk IDs are `drive:{drive_slug}:{file_id}:{chunk_index:04d}` — collision-proof, deterministic, idempotent via upsert

## Hard rules added in v2

- Requires `GOOGLE_APPLICATION_CREDENTIALS` (or `GOOGLE_SERVICE_ACCOUNT_JSON`) — same env var already used for Drive auth, now also used for Vertex AI auth via the same service account
- Vision cost gates at $1.00 (interactive) and $25.00 (hard refuse)
- Per-file vision failure rate gate at 20%

---

## Staircase

1. Design doc (this file) — approved
2. `_drive_common.py` refactor + v1 import patch + v1 regression test
3. Vision modules (`gemini_client`, `ocr_cache`)
4. `drive_loader_v2.py`
5. v2 dry-run against Supplement Info, dump-json to `data/dumps/supplement_info_pilot_v2.json`
6. **HALT** — Dan eyeballs the OCR'd output
7. Only with explicit approval: v2 commit-run against Supplement Info into local Chroma

---

## Out of scope (defer to v3 or later)

- PDF support
- Google Slides support
- Direct image file support (image/jpeg, image/png as top-level files)
- Video/audio
- Railway deployment of v2
- Re-ingest/migration logic for files already in Chroma (idempotent upsert handles this for free)
- Multiple target collections (`rf_published_content` etc.) — same one-line change as v1 when the collection exists
