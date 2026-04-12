# Phase D-prime — Folder-Walk Inventory Spec (Claude Code handoff)

**Status:** Ready for Claude Code implementation
**Prerequisite:** Phase C verified (smoke test PASS on 2026-04-11 night)
**Blocker:** Phase B drive sharing — may be partial when this runs; spec handles that

---

## Goal

Walk every Google Shared Drive the `rf-ingester` service account has been
granted Viewer access to, recursively enumerate the folder tree (folders
only, with file counts per folder), and dump the result to a JSON manifest
on disk. This manifest becomes the input data for the folder-selection UI
design (ADR-004, Phase D-post).

**This script does NOT:** download files, hash content, read file bodies,
create chunks, call Vertex AI, write to ChromaDB, or touch the registry.
Pure read-only metadata walk.

---

## Architecture

**New module:** `ingester/folder_walk.py`
**Uses:** `DriveClient` from `ingester/drive_client.py` (existing, do not modify)
**Uses constants from:** `ingester/config.py` (existing, may extend with `SHARED_DRIVE_IDS` list — see below)
**CLI entry point:** `python3 -m ingester.folder_walk [args]`

**Do not modify:** `drive_client.py`, `main.py`, any YAML files, any ADRs.
**May extend:** `config.py` ONLY to add `SHARED_DRIVE_IDS` dict (drive ID → human name).

---

## Inputs

### Twelve Shared Drives (from ADR-001)

The script must walk these twelve drives. Drive IDs are NOT currently in
`config.py` — they need to be added as a new constant. The human names are
known from ADR-001 but the actual Google Drive IDs are NOT yet recorded in
the repo. **Claude Code's first task is to retrieve these IDs** by calling
`drive.drives().list(pageSize=50).execute()` via the existing `DriveClient`
and matching names to IDs, then writing them into `config.py` as a new
constant:

```python
SHARED_DRIVE_IDS = {
    "0-shared-drive-content-outline": "<id>",
    "1-operations": "<id>",
    "2-sales-relationships": "<id>",
    "3-marketing": "<id>",
    "4-finance": "<id>",                    # FLAGGED sensitive
    "5-hr-legal": "<id>",                   # FLAGGED sensitive
    "6-ideas-planning-research": "<id>",
    "7-supplements": "<id>",
    "8-labs": "<id>",                       # FLAGGED sensitive
    "9-biocanic": "<id>",
    "10-external-content": "<id>",
    "11-rh-transition": "<id>",
}
SENSITIVE_DRIVE_SLUGS = {"4-finance", "5-hr-legal", "8-labs"}
```

If a drive from the ADR-001 table is NOT returned by `drives().list()`, it
means Phase B sharing is incomplete for that drive. Log it, include it in
the manifest with `status: "not_shared"`, and continue.

---

## Outputs

### Manifest file

**Path:** `data/inventories/folder_walk_{YYYYMMDD_HHMMSS}.json`
(Local run: create `data/inventories/` if missing. Do NOT use `/data` —
that's the Railway volume path. For local dev, use a `data/` subdir at
the repo root. Add `data/` to `.gitignore` if not already there.)

### JSON schema

```json
{
  "walk_started_at": "2026-04-12T09:30:00Z",
  "walk_finished_at": "2026-04-12T09:31:47Z",
  "walk_duration_seconds": 107,
  "service_account_email": "rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com",
  "drives_expected": 12,
  "drives_accessible": 9,
  "drives_not_shared": ["4-finance", "5-hr-legal", "8-labs"],
  "drives": [
    {
      "slug": "2-sales-relationships",
      "drive_id": "0AI...",
      "drive_name_google": "2. Sales & Relationships",
      "sensitive_flag": false,
      "status": "walked",
      "total_folders": 47,
      "total_files": 312,
      "max_depth": 5,
      "root": {
        "id": "0AI...",
        "name": "2. Sales & Relationships",
        "path": "/",
        "depth": 0,
        "file_count_direct": 3,
        "subfolders": [
          {
            "id": "1abc...",
            "name": "FKSP Enrollment",
            "path": "/FKSP Enrollment",
            "depth": 1,
            "file_count_direct": 12,
            "subfolders": [ ... recursive ... ]
          }
        ]
      }
    },
    {
      "slug": "4-finance",
      "drive_id": null,
      "status": "not_shared",
      "error": "Drive not visible to service account — Phase B share pending",
      "sensitive_flag": true
    }
  ]
}
```

**Rules:**
- `file_count_direct` is the number of non-folder items in THAT folder only (not recursive)
- `total_files` and `total_folders` at the drive level ARE recursive totals
- Folders are walked breadth-first so `depth` increments cleanly
- Do not enumerate individual files in the output — names and counts only
- Shortcuts (`application/vnd.google-apps.shortcut`) are counted as files, not followed

---

## Function signatures

```python
# ingester/folder_walk.py

def discover_shared_drives(client: DriveClient) -> dict[str, dict]:
    """
    Call drive.drives().list() and return {drive_id: {name, ...}} for
    every drive the service account can see. Used to match against
    SHARED_DRIVE_IDS and populate it on first run.
    """

def walk_drive(client: DriveClient, drive_id: str, slug: str) -> dict:
    """
    Recursively walk a single Shared Drive. Returns the drive-level dict
    matching the schema above. Uses corpora='drive' and driveId=drive_id
    in the files().list() call, with supportsAllDrives=True and
    includeItemsFromAllDrives=True. Pages through results with pageToken.
    On permission errors, returns a dict with status='not_shared' and
    error message. Does not raise.
    """

def walk_all(client: DriveClient, drive_map: dict[str, str]) -> dict:
    """
    Walk every drive in drive_map ({slug: drive_id}) and assemble the
    top-level manifest dict. Handles partial failures — one drive
    failing does not stop the others.
    """

def write_manifest(manifest: dict, output_dir: Path) -> Path:
    """
    Write manifest to data/inventories/folder_walk_{timestamp}.json.
    Create output_dir if missing. Return the written path.
    """

def main() -> int:
    """
    CLI entry: parse args, build DriveClient, dispatch to walk_all or
    walk_drive, write manifest, print summary, return exit code.
    """
```

---

## CLI

```bash
# Full walk (default)
python3 -m ingester.folder_walk

# Single drive (for testing)
python3 -m ingester.folder_walk --drive 0-shared-drive-content-outline

# Discovery only — list drives the service account can see, do not walk
python3 -m ingester.folder_walk --discover

# Custom output path
python3 -m ingester.folder_walk --out data/inventories/test.json
```

Exit codes: `0` success (even with partial drive failures), `1` total
failure (no drives walked), `2` auth/config error.

---

## Error handling contract

| Error | Response |
|-------|----------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` not set | Print clear message telling user to run via `railway run --service rf-nashat-clone`, exit 2 |
| Drive not in `drives().list()` result | Mark slug as `status: "not_shared"`, continue |
| `HttpError 403` on a folder deep in the tree | Log warning, mark that subtree as `status: "partial_access"`, continue walking siblings |
| `HttpError 429` rate limit | Sleep and retry with exponential backoff, max 3 retries, then skip that page |
| Network error mid-walk | Retry once, then mark drive as `status: "walk_failed"` with error string, continue to next drive |
| Empty drive (zero folders, zero files) | Valid — walk returns normally with zero counts |

**The script never crashes the whole walk on a single drive failure.**
Partial results are always written to the manifest. If zero drives
succeed, exit 1 after still writing the manifest (for debugging).

---

## Running it

Because the credential lives only in Railway env, the script MUST run via
`railway run`:

```bash
cd "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone"
railway run --service rf-nashat-clone python3 -m ingester.folder_walk --discover
```

`--discover` is the cheapest possible test — one API call, no recursion,
prints the drives the service account can see. Run this FIRST before a
full walk.

Then full walk:
```bash
railway run --service rf-nashat-clone python3 -m ingester.folder_walk
```

---

## Success criteria

1. `--discover` returns at least 1 drive (more is better, 12 is ideal)
2. A single-drive walk against drive #0 completes without error
3. A full walk produces a manifest file that:
   - Parses as valid JSON
   - Has `walk_finished_at` populated
   - Has at least one drive with `status: "walked"`
   - Shows total file + folder counts Dan can eyeball against intuition
4. The manifest file path is printed to stdout at end of run
5. Git status shows `config.py` modified (new `SHARED_DRIVE_IDS` dict) and
   `ingester/folder_walk.py` created

---

## Dependencies

Already installed (per `ingester_requirements.txt`):
- `google-api-python-client`
- `google-auth`
- `google-auth-httplib2`

No new deps needed. Do not add any.

---

## Claude Code kickoff prompt (paste this into a fresh Claude Code session)

> Read `PHASE_D_PRIME_SPEC.md` in the repo root. Then read
> `ingester/drive_client.py` and `ingester/config.py` for context on the
> existing `DriveClient` class and config constants.
>
> Implement `ingester/folder_walk.py` per the spec. Also extend
> `ingester/config.py` with the `SHARED_DRIVE_IDS` and
> `SENSITIVE_DRIVE_SLUGS` constants described in the spec — leave the
> drive ID values as empty strings initially; they'll be populated after
> the first `--discover` run.
>
> Do not modify `drive_client.py`, `main.py`, any YAML, or any ADR.
>
> Workflow:
> 1. Implement the module and the config extension
> 2. Run `railway run --service rf-nashat-clone python3 -m ingester.folder_walk --discover`
> 3. Show me the output — a list of drive names and IDs the service
>    account can see
> 4. I'll tell you which IDs map to which slugs in `SHARED_DRIVE_IDS`,
>    you patch them in
> 5. Run `railway run --service rf-nashat-clone python3 -m ingester.folder_walk --drive 0-shared-drive-content-outline`
>    as a single-drive smoke test
> 6. If that works, run the full walk
> 7. Show me the manifest output summary (total counts per drive,
>    which drives were not_shared)
> 8. Commit the new module + config changes + the manifest output dir
>    addition to .gitignore
>
> Expected total time: 45-75 minutes. If you get stuck on auth, Drive
> API pagination, or partial-access handling, stop and ask me rather
> than guessing — the spec's error handling contract is authoritative
> and I'd rather clarify than have you diverge.
>
> The credential lives in Railway env var `GOOGLE_SERVICE_ACCOUNT_JSON`
> on the `rf-nashat-clone` service in `diligent-tenderness` project.
> `railway run` is the only way to inject it — never read it from local
> disk, never echo it, never log JSON contents on error paths.

---

## Open questions (to resolve with Dan before Claude Code runs this)

None. The spec is decision-complete. If Claude Code asks a clarifying
question, the answer should be in this document — if it isn't, escalate
to Dan instead of guessing.

---

## Relationship to other ADRs

- **ADR-001:** Walks the twelve drives from the ADR-001 table; honors
  the sensitive-flag metadata but does NOT refuse to walk flagged drives
  (walking is metadata-only and non-invasive; selection is what requires
  the confirmation modal in ADR-004)
- **ADR-002:** This script does NOT write to the `rf_library_index`
  registry. The registry is populated in Phase D-post (after the UI is
  built against this manifest's data). Phase D-prime is deliberately
  registry-free.
- **ADR-003:** Canva dedup is not in scope. No hashing, no vision calls.
- **ADR-004:** The manifest produced by this script is the primary input
  for the UI design pass.

---

*Spec written 2026-04-11 night for next-session Claude Code handoff.
Phase C verified, Phase B may be partial when this runs — spec handles
partial drive access gracefully.*
