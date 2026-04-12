# RF Nashat RAG — Handover (living cursor)

Updated in place each session-end. Read this first to resume.

---

## State
- Last commit: `0de73a8` — "docs: add ARCHITECTURE, DECISIONS, BACKLOG, HANDOVER (context management)" — pushed to `main`.
- Previous commit `b6635ba` — "folder_walk: expand Drive fields..." — still deployed green on Railway. Folder walk has NOT been run with new fields anywhere yet.
- Local Drive creds: service account JSON at `/Users/danielsmith/.config/gcloud/rf-service-account.json` (chmod 600). Verified readable. `client_email: rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`, `project_id: rf-rag-ingester-493016`.
- `.env` has `GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json` appended. `.env` is gitignored. `.gitignore` verified clean.

## Just did
- Created docs scaffolding: `ARCHITECTURE.md`, `DECISIONS.md`, `BACKLOG.md`, `HANDOVER.md`. Committed + pushed as `0de73a8`.
- Added `GOOGLE_APPLICATION_CREDENTIALS` to `.env`.
- Attempted `python3 -m ingester.folder_walk --discover` — **failed**, surfaced two issues (see below).

## ⚠️ Two issues found, NOT yet fixed

### Issue 1: `.env` line 4 syntax error
`source .env` fails with `line 4: -: command not found`. Some value on line 4 has an unquoted dash or shell-special char. Need to `sed -n '1,10p' .env` to inspect and quote the offending value.

### Issue 2: Env var name mismatch (the real blocker)
`ingester/folder_walk.py` / `DriveClient` expects **`GOOGLE_SERVICE_ACCOUNT_JSON`** (raw JSON blob as env var, Railway-style). Handover assumed **`GOOGLE_APPLICATION_CREDENTIALS`** (file path, standard Google SDK convention). These are different things.

**Recommended fix (Option B): patch `DriveClient`** to fall back to reading the file at `GOOGLE_APPLICATION_CREDENTIALS` when `GOOGLE_SERVICE_ACCOUNT_JSON` is unset. ~5 line diff. Railway keeps working (`GOOGLE_SERVICE_ACCOUNT_JSON` still checked first). Local gets the cleaner file-path convention.

Alternative (Option A, quick-and-dirty): put the raw JSON blob inline in `.env` as `GOOGLE_SERVICE_ACCOUNT_JSON='{...}'`. No code change but uglier.

Dan chose Option B.

## Next (in order)
1. **Inspect & fix `.env` line 4:** `sed -n '1,10p' .env` → quote whatever value is breaking shell parsing.
2. **Find `DriveClient` definition:** probably in `ingester/drive_client.py` or similar. Grep: `grep -rn "GOOGLE_SERVICE_ACCOUNT_JSON" ingester/`.
3. **Patch `DriveClient`** to fall back to file at `GOOGLE_APPLICATION_CREDENTIALS` path when `GOOGLE_SERVICE_ACCOUNT_JSON` is unset. Keep existing Railway path working.
4. **Commit** the patch: `fix(ingester): DriveClient falls back to GOOGLE_APPLICATION_CREDENTIALS file path for local dev`.
5. **Re-run discover locally:** `python3 -m ingester.folder_walk --discover`. Should list visible Shared Drives.
6. **Run the full walk:** `python3 -m ingester.folder_walk`. Writes manifest to `data/inventories/folder_walk_<timestamp>.json`.
7. **Verify manifest with `jq`:** pull ONE sample non-native file record (PDF/slide/docx) and confirm all six new fields present (`size`, `modifiedTime`, `createdTime`, `webViewLink`, `md5Checksum`, `owners`). Do NOT dump the whole file. Native Google Docs legitimately lack `size`/`md5Checksum` — that's Drive API, not a bug.
8. Once verified → plan A4M `rf_reference_library` ingestion (see BACKLOG.md).

## Blockers / deferred
- Folder walk blocked on Issue 2 patch above.
- Zoom pipeline design captured in BACKLOG.md for later phase.

## Do NOT
- Do NOT re-read full `folder_walk.py` — you already know the arg structure: `--discover`, `--drive <slug>`, `--out`, or no args for all.
- Do NOT dump full JSON manifests — always filter with `jq`.
- Do NOT commit `.env` or the service account JSON.
- Do NOT run the walk on Railway yet — local first, verify, then Railway.
- Do NOT remove `GOOGLE_SERVICE_ACCOUNT_JSON` support from `DriveClient` — Railway depends on it.
