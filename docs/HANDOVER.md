# RF Nashat RAG — Handover (living cursor)

Updated in place each session-end. Read this first to resume.

---

## State
- Two fixes this session, both verified end-to-end:
  1. `DriveClient` credential fallback — local dev now reads service account from `GOOGLE_APPLICATION_CREDENTIALS` file path. Railway's `GOOGLE_SERVICE_ACCOUNT_JSON` blob path is unchanged and still checked first. Committed + pushed.
  2. `folder_walk.py` field-persistence bug — Drive API was correctly fetching 9 file fields, but `_walk_folder` was only storing 3 into the manifest. Both `append({...})` blocks (top-level loop AND nested BFS loop) now persist all 9 keys via `.get()`. **Needs commit + push** (see Next step 1).
- `.env` line 4 fixed: `CHROMA_DB_PATH` double-quoted so `source .env` works.
- Local credential: `GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json`.
- Last full walk: `data/inventories/folder_walk_20260412_141626.json` — 9 drives, 3,949 folders, 15,593 files, 21.6 min. **STALE — pre-fix, missing the 6 fields. Needs re-run.**
- Smoke-walked `9-biocanic` (`folder_walk_20260412_150658.json`) post-fix, jq-verified on a video/mp4 record: size, modifiedTime, createdTime, webViewLink, md5Checksum all populated. `owners: null` is correct Drive API behavior for Shared Drive files (ownership lives with the drive), not a bug.
- ⚠️ Security: `.env` containing live `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` was exposed in a chat transcript this session. Rotate both keys when convenient.

## Just did
- Quoted `CHROMA_DB_PATH` in `.env` line 4.
- Patched `DriveClient.__init__`: explicit arg → `GOOGLE_SERVICE_ACCOUNT_JSON` blob → `GOOGLE_APPLICATION_CREDENTIALS` file. Committed + pushed.
- Patched both `append({...})` blocks in `folder_walk.py::_walk_folder` to persist all 9 file fields. Verified with `--drive 9-biocanic` + jq. Not yet committed.

## Next (in order)
1. **Commit the folder_walk fix:**
   ```bash
   cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
   git add ingester/folder_walk.py docs/HANDOVER.md
   git commit -m "fix(ingester): folder_walk persists all Drive API fields into manifest"
   git push
   ```
2. **Re-run full walk** (fresh Terminal, export credential first):
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/Users/danielsmith/.config/gcloud/rf-service-account.json"
   python3 -m ingester.folder_walk
   ```
   ~22 min. Writes new timestamped manifest to `data/inventories/`.
3. **Verify new manifest** with jq (command in Do NOT section).
4. **Plan A4M `rf_reference_library` ingestion** — locally synced Mac path, NOT Drive (A4M not in Drive, confirmed this session).
5. Deferred: admin password rotation, add Dr. Nashat as second admin user via `add_user` CLI.

## Blockers / deferred
- None on the walk pipeline — clean.
- Network stability: first full walk failed mid-way on Wi-Fi drop. Not a code bug. If recurs, consider resume-from-partial-manifest for `folder_walk.py` (queued for BACKLOG).
- Rotate exposed `ANTHROPIC_API_KEY` + `OPENAI_API_KEY`.
- Zoom coaching video pipeline design still in BACKLOG.

## Do NOT
- Do NOT re-read full `folder_walk.py` or `drive_client.py` — both fixes verified.
- Do NOT dump full JSON manifests — always jq. Field-verification one-liner:
  ```bash
  jq '[.. | .files? // empty | .[]? | select(.mimeType | test("google-apps") | not) | select(.mimeType != "application/vnd.google-apps.folder")][0]' data/inventories/folder_walk_<timestamp>.json
  ```
- Do NOT commit `.env` or the service account JSON.
- Do NOT remove `GOOGLE_SERVICE_ACCOUNT_JSON` support from `DriveClient` — Railway depends on it.
- Do NOT run the walk on Railway yet — local first, verify, then Railway.
