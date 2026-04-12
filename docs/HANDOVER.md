# RF Nashat RAG — Handover (living cursor)

Updated in place each session-end. Read this first to resume.

---

## State
- Last commit: `b6635ba` — "folder_walk: expand Drive fields..." — pushed to `main`, deployed green on Railway.
- Change: `ingester/folder_walk.py` line 175 `fields=` selector expanded to include `size`, `modifiedTime`, `createdTime`, `webViewLink`, `md5Checksum`, `owners(emailAddress)`.
- Folder walk has **NOT** yet been run with the new fields — not locally, not on Railway.
- Local Drive creds now available: service account JSON at `/Users/danielsmith/.config/gcloud/rf-service-account.json` (chmod 600). Client email `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`. Project `rf-rag-ingester-493016`. Not yet added to `.env`. `.gitignore` coverage not yet verified.

## Just did
- Set up docs structure: `ARCHITECTURE.md`, `DECISIONS.md`, `BACKLOG.md`, `HANDOVER.md`.
- Moved stable reference material out of chat context and into committed docs.

## Next (in order)
1. Add `GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json` to `rf-nashat-clone/.env`. Verify `.env` and `.config/gcloud/` patterns are in `.gitignore`.
2. Run the folder walk locally:
   ```
   cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
   GOOGLE_APPLICATION_CREDENTIALS=/Users/danielsmith/.config/gcloud/rf-service-account.json python3 -m ingester.folder_walk
   ```
3. Verify the new manifest at `data/inventories/folder_walk_<timestamp>.json` has all six new fields on a sample non-native file record. Use `jq` to pull one PDF/slide/docx record — do NOT dump the whole file. Native Google Docs legitimately lack `size` and `md5Checksum` — that's Drive API, not a bug.
4. Once verified, plan A4M `rf_reference_library` ingestion (see BACKLOG.md).

## Blockers / deferred
- None currently blocking. Zoom pipeline design captured in BACKLOG.md for later phase.

## Do NOT
- Do NOT re-read `folder_walk.py`, YAML configs, or full manifests unless debugging a specific failure.
- Do NOT dump full JSON — always filter with `jq`.
- Do NOT commit `.env` or the service account JSON path.
- Do NOT run the walk on Railway yet — local first, verify, then Railway.
