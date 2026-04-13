# NEXT SESSION PROMPT — session 11

> **⚠ READ THIS FIRST, BEFORE ANY READING LIST**
>
> Sessions 9 and 10 both used a "step 0 reality check" before doing any work. Session 9 corrected drift inherited from sessions 5–8. Session 10 used the reality check to catch a path mismatch in the bootstrap prompt before it caused harm. **Keep doing this.** The reality check has paid for itself twice. Do not skip it.

---

## Step 0 — Tool and reality check (mandatory, ~5 minutes)

Before reading anything else, run all four checks. **Stop and tell Dan if anything surprises you.**

1. **Tool enumeration.** You need filesystem tools (`Filesystem:read_text_file`, `Filesystem:write_file`) AND process execution (`Desktop Commander:start_process` and friends). If you only have filesystem and no process pathway, stop and tell Dan the chat needs Desktop Commander loaded.

2. **Smoke test process execution.** Run `echo "session 11 tool check $(date -u +%Y-%m-%dT%H:%M:%SZ)"`. Confirm it works.

3. **Repo state.** `cd /Users/danielsmith/Claude\ -\ RF\ 2.0/rf-nashat-clone && git status && git log --oneline -5`. Expected baseline: clean tree on `main`, top commit is the session-10 squash that Dan landed (or close to it). If the tree isn't clean or the top commits don't match what HANDOVER's session-10 entry describes, stop and surface it.

4. **Reality-vs-prompt check.** Independently verify these claims against the actual filesystem before reading the reading list:
   - **Drive auth still works locally.** Run: `export GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json && ./venv/bin/python -c "from ingester.drive_client import DriveClient; c=DriveClient(); print('OK', c.service_account_email)"`. Should print OK and the service account email.
   - **The session 10 v1 loader exists and dry-runs cleanly.** `./venv/bin/python -m ingester.loaders.drive_loader --selection-file /tmp/rf_pilot_selection.json --folder-id 1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54 --dry-run 2>&1 | tail -20`. (You may need to recreate `/tmp/rf_pilot_selection.json` first — it gets wiped on Mac reboot. Contents are in HANDOVER's session 10 entry.) Should report 1 file would ingest, 2 skipped as `low_text_yield`, 1 skipped as `unsupported_mime`. If those numbers don't match, the loader has changed since session 10 and you need to understand why before proceeding.
   - **Railway production is still alive.** `curl -sI https://console.drnashatlatib.com | head -3`. HTTP/2 302.
   - **`data/selection_state.json` state.** It may now contain real data if Dan visually-tested the picker between sessions, or may still be the placeholder. Either is fine — just know which.

If any check returns a surprise, stop and surface it before reading further.

---

## Reading order (after step 0 passes)

Tight reading list. Most context budget should go to building, not reading.

1. **`docs/STATE_OF_PLAY.md`** — authoritative current-state document. Read in full, including both session-10 amendments at the bottom.
2. **`docs/HANDOVER.md`** — read the session 10 entry AND the session 10 addendum at the very top. The addendum is where the v2 loader sketch lives.
3. **`docs/plans/2026-04-13-drive-loader-pilot.md`** — the v1 loader design doc. Read for context on the architectural decisions you'll be inheriting (chunk ID format, metadata schema, hard guards, refusal-to-run-against-Railway). v2 should keep these.
4. **`ingester/loaders/drive_loader.py`** — the v1 loader itself. ~770 lines. Most of v2 will reuse v1's plumbing (CLI, validation gates, manifest lookup, metadata building, dump-json, low-yield guard) and replace only the `fetch_file_text` + chunking entry points.
5. **`ingester/drive_client.py`** — already understood from session 10, just refresh.
6. **`ingester/config.py`** — already names `VISION_MODEL = "gemini-2.5-flash"` for image enrichment. v2 will actually use this for the first time.

**Do NOT read** (deliberate skips):
- The session 7 HANDOVER entry — frozen
- ADR_005, ADR_006, the three plans from session 7 — frozen
- The v3 LLM coaching pipeline (`/Users/danielsmith/Claude - RF 2.0/rag_pipeline_v3_llm.py`) — wrong fit, do not adapt it for v2
- The original Lineage A files (`ingest_a4m_transcripts.py`, `merge_small_chunks.py`, the JSON files in `data/`) — abandoned dead code per STATE_OF_PLAY

---

## The actual goal for session 11 — build the v2 Drive loader

**v2's job:** ingest image-heavy Google Docs that v1's `text/plain` export cannot handle.

The v1 loader inspection in session 10 confirmed the lossy-export problem quantitatively: the pilot folder's most substantive doc (4.3 MB on Drive) exported to ~3 KB of text, with all the substitution data trapped in product images. The v1 low-yield guard correctly skipped it, but **most of Dr. Nashat's reference content is built this way** — visual handouts, supplement protocols with product photos, lab interpretation diagrams. v1 cannot deliver them. v2 is what unblocks Drive ingestion as a real pipeline.

### v2 architecture sketch (from session 10 HANDOVER addendum)

The shape Claude proposed at session-10 end. **Treat this as a starting point, not a contract.** Push back on it if anything is wrong.

```
Drive Google Doc (image-heavy)
    │
    ├─► Drive API: files().export(mimeType="text/html")
    │       returns HTML with embedded <img src="..."> tags
    │
    ├─► Parse HTML (BeautifulSoup) to extract:
    │       - prose text in document order
    │       - image URLs in document order (Drive serves these via
    │         authenticated googleusercontent.com URLs)
    │       - structural elements (headings, lists, tables)
    │
    ├─► For each image:
    │       - Download via service account credentials
    │       - Send to Gemini 2.5 Flash with a focused prompt:
    │         "You are extracting visual information from a fertility
    │         reference document. Describe what is shown. If this is a
    │         product photo, transcribe the product name, brand, dose,
    │         and any visible label text. Return as a brief structured
    │         description."
    │       - Receive OCR'd / described text
    │       - Cache by image URL hash so re-runs are cheap
    │
    ├─► Stitch: rebuild a single text stream with image descriptions
    │   inserted in their original document positions, marked as
    │   [IMAGE: ...] so the chunker (and downstream agent) can tell
    │   "image-derived text" from "doc-prose text"
    │
    └─► Chunk + embed + write (same as v1)
```

### What v2 inherits from v1 unchanged
- CLI shape (`--selection-file`, `--folder-id`, `--dry-run`/`--commit`, `--dump-json`, `--verbose`)
- All hard guards (Railway path refusal, placeholder rejection, schema validation, OPENAI_API_KEY check)
- Metadata schema (21 fields, including `display_*` and `source_folder_id`)
- Chunk ID format: `drive:{drive_slug}:{file_id}:{chunk_index:04d}`
- Paragraph-aware chunking with the 700/80-word window
- The `low_text_yield` guard (still needed as a safety net even with v2 — some docs may still fail extraction for reasons we haven't anticipated)
- The dump-json inspection flag

### What v2 adds
- New `fetch_file_html()` function alongside the existing `fetch_file_text()`
- HTML→stitched-text pipeline with embedded image OCR
- A new `source_pipeline = "drive_loader_v2"` constant so v2-ingested chunks are distinguishable from v1-ingested chunks in retrieval
- Per-image OCR cache (probably `data/image_ocr_cache/{sha256}.json`) so re-runs skip already-OCR'd images
- New metadata field per chunk: `image_derived_word_count` (how many words in this chunk came from image OCR vs doc prose)
- Cost tracking that includes both embedding spend AND Gemini vision spend
- A new low-yield variant: if HTML export ALSO yields very little (no images, no text), still skip with a clear reason

### What v2 explicitly does NOT do (defer to v3)
- PDF support
- Spreadsheet support
- Slide-deck support (Google Slides)
- Direct image files (`image/jpeg`, `image/png`)
- Video/audio
- Re-running v2 against files already ingested by v1 (idempotency at the chunk-ID level handles this naturally; no special migration logic needed)

### Pilot for v2

Re-use the same pilot folder: **Supplement Info** (`1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`). v1's dry-run on this folder skipped the two image-heavy docs (Comprehensive List, Supplement Details). v2's success criterion: those two docs ingest cleanly, the substitution product names appear in the dump-json output, and the chunks pass an eyeball test.

### The staircase for session 11

Use the same approach as session 10:

1. **Step 1**: read code, verify Drive auth + Gemini auth (NEW — Gemini hasn't been wired up before, so credentials may need setup). The `GCP_PROJECT_ID = "rf-rag-ingester-493016"` already in `ingester/config.py` is the right project; the service account at `/Users/danielsmith/.config/gcloud/rf-service-account.json` may or may not have Vertex AI permissions. **Verify this first.** If it doesn't, that's a Dan-side GCP IAM change before any code can run.
2. **Step 2**: design doc for v2, including: HTML parsing strategy, image OCR prompt, cache shape, cost model, what to do if Gemini fails on a specific image. Halt for Dan review.
3. **Step 3**: build v2 as `ingester/loaders/drive_loader_v2.py` (NOT replacing v1 — both should coexist, controlled by a `--version v1|v2` flag, OR v2 gets its own module name. Tactical call.)
4. **Step 4**: dry-run v2 against Supplement Info, dump-json the result, eyeball the OCR'd substitution names in the Comprehensive doc. Halt for Dan review.
5. **Step 5**: only with explicit Dan approval — commit-run v2 against Supplement Info into LOCAL Chroma. Real chunks, real $$, reversible via the chunk IDs in the run record.

### Stop conditions

Any of these is a successful session 11:
- v2 dry-run produces correct OCR'd output for the Comprehensive doc, even if commit-run is deferred
- v2 commit-run lands ~10-30 chunks from Supplement Info into local Chroma, queryable via the rag_server
- A Gemini-side blocker is identified (auth, IAM, quota) and a clean plan to resolve it is written up

### Anti-goals for session 11
- Do NOT push v2 to Railway in this session. Local Chroma only.
- Do NOT delete or modify v1. v1 stays as a fast-path for text-only docs.
- Do NOT ingest any other folders besides Supplement Info. One folder, one validation, then stop.
- Do NOT bolt PDF / slide / image-file support onto v2 in this session. Single concern: image-heavy Google Docs.

---

## Cost expectations

Rough estimate, please verify against Gemini 2.5 Flash current pricing before any commit-run:

- Per image: ~250 input tokens (image) + ~200 prompt tokens + ~150 output tokens. At ~$0.075/1M input + ~$0.30/1M output: ~$0.00010 per image.
- The Comprehensive doc likely has ~50-150 images based on its 4.3 MB size. Estimated v2 cost for that one doc: $0.005 - $0.015.
- Embedding cost is unchanged from v1: trivial.

**Likely total for the Supplement Info pilot in commit mode: under $0.05.**

If your dry-run estimate exceeds **$1.00**, stop and surface to Dan before any commit-run. If it exceeds **$25.00**, that's a strategic spend that requires Dan approval per the tech-lead mandate.

---

## Hard rules carried forward (unchanged from sessions 7, 8, 9, 10)

- No ChromaDB writes without explicit Dan approval at the specific write moment, and never to Railway without a pre-flight discussion of backups
- No git push, commit, or add — Dan runs git, Claude suggests
- No Railway operations without explicit approval
- No deletions without approval and a verified backup
- Never reference Dr. Christina; exclude Kelsey Poe and Erica
- Public agent never accesses `rf_coaching_transcripts`
- Credentials are ephemeral — never read `.env` and reproduce its contents in chat output, never write credential values into memory or files. If a credential gets into context, treat it as ephemeral and drop it.
- **Use Desktop Commander heredocs or `Filesystem:write_file` for any file that must land in the repo.** `create_file` writes to Claude's sandbox, not the Mac. Session 8 hit this trap.
- The session 10 finding that Drive's `text/plain` export is lossy on image-heavy docs is the entire reason v2 exists. Do not "simplify" v2 by going back to plain-text export. The lossiness IS the problem.

---

## Tech-lead mandate (unchanged)

Claude holds tech-lead role on the RAG build. Tactical decisions (script layout, prompt wording, cache shape, chunking parameters) are Claude's call. Strategic decisions (irreversible operations, money spend > $25, anything crossing the RAG/app/product/legal boundary, anything that fails the "can we fix this later?" reversibility test) get flagged to Dan first.

The session-9 addition still applies: at session start, before reading the reading list, independently verify the bootstrap prompt's description of the world against the evidence on disk. The Step 0 reality check IS this rule.

---

## Quick reference

- Repo root: `/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone`
- Local Chroma: `/Users/danielsmith/Claude - RF 2.0/chroma_db/` (dev sandbox; Railway is canonical for production)
- Railway production: `https://console.drnashatlatib.com` (Cloudflare Access; allowlisted: dan@reimagined-health.com, znahealth@gmail.com)
- venv interpreter: `./venv/bin/python` (Python 3.11.3, chromadb 1.5.6)
- v1 loader: `ingester/loaders/drive_loader.py`
- Pilot folder: Supplement Info, ID `1rOvLMMC4uiC9w60Kc3s4oUEc-SGxNj54`, in drive `1-operations`
- Pilot dump (v1, post-guard): `data/dumps/supplement_info_pilot_v1guard.json`
- GCP project: `rf-rag-ingester-493016` (per `ingester/config.py`)
- Gemini model: `gemini-2.5-flash` (per `ingester/config.py`'s `VISION_MODEL`)
- Service account creds: `/Users/danielsmith/.config/gcloud/rf-service-account.json` (mode 600)
