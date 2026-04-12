"""
Phase D-prime — Shared Drive folder-walk inventory.

Walks every Google Shared Drive the rf-ingester service account can see,
enumerates folder trees (folders only, with file counts per folder), and
dumps a JSON manifest to disk.  Pure read-only metadata walk — no file
downloads, no content reading, no writes to ChromaDB or the registry.

CLI usage:
    python3 -m ingester.folder_walk              # full walk
    python3 -m ingester.folder_walk --discover   # list visible drives
    python3 -m ingester.folder_walk --drive SLUG # walk one drive
    python3 -m ingester.folder_walk --out PATH   # custom output path
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from googleapiclient.errors import HttpError

from .drive_client import DriveClient
from . import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_shared_drives(client: DriveClient) -> dict[str, dict]:
    """
    Call drives().list() and return {drive_id: {name, id}} for every
    Shared Drive the service account can see.
    """
    drives: dict[str, dict] = {}
    page_token: str | None = None
    while True:
        resp = (
            client._service.drives()
            .list(pageSize=50, pageToken=page_token)
            .execute()
        )
        for d in resp.get("drives", []):
            drives[d["id"]] = {"name": d["name"], "id": d["id"]}
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return drives


# ---------------------------------------------------------------------------
# Single-drive walk
# ---------------------------------------------------------------------------

def _walk_folder(
    client: DriveClient,
    drive_id: str,
    folder_id: str,
    folder_name: str,
    folder_path: str,
    depth: int,
) -> dict:
    """
    BFS walk of a single folder.  Returns the folder node dict with
    recursive subfolders and file_count_direct.
    """
    node: dict[str, Any] = {
        "id": folder_id,
        "name": folder_name,
        "path": folder_path,
        "depth": depth,
        "file_count_direct": 0,
        "files": [],
        "subfolders": [],
    }

    # Queue: (parent_node, folder_id, folder_name, path, depth)
    queue: deque[tuple[dict, str, str, str, int]] = deque()

    # First: list children of the current folder
    try:
        children = _list_drive_children(client, drive_id, folder_id)
    except _PartialAccessError as e:
        node["status"] = "partial_access"
        node["error"] = str(e)
        return node

    for child in children:
        mime = child.get("mimeType", "")
        if mime == config.MIME_FOLDER:
            child_name = child.get("name", "<unnamed>")
            child_path = f"{folder_path}/{child_name}"
            child_node: dict[str, Any] = {
                "id": child["id"],
                "name": child_name,
                "path": child_path,
                "depth": depth + 1,
                "file_count_direct": 0,
                "files": [],
                "subfolders": [],
            }
            node["subfolders"].append(child_node)
            queue.append((child_node, child["id"], child_name, child_path, depth + 1))
        else:
            node["file_count_direct"] += 1
            node["files"].append({
                "id": child["id"],
                "name": child.get("name", "<unnamed>"),
                "mimeType": mime,
            })

    # BFS the rest
    while queue:
        parent_node, fid, fname, fpath, fdepth = queue.popleft()
        try:
            children = _list_drive_children(client, drive_id, fid)
        except _PartialAccessError as e:
            parent_node["status"] = "partial_access"
            parent_node["error"] = str(e)
            continue

        for child in children:
            mime = child.get("mimeType", "")
            if mime == config.MIME_FOLDER:
                child_name = child.get("name", "<unnamed>")
                child_path = f"{fpath}/{child_name}"
                child_node = {
                    "id": child["id"],
                    "name": child_name,
                    "path": child_path,
                    "depth": fdepth + 1,
                    "file_count_direct": 0,
                    "files": [],
                    "subfolders": [],
                }
                parent_node["subfolders"].append(child_node)
                queue.append((child_node, child["id"], child_name, child_path, fdepth + 1))
            else:
                parent_node["file_count_direct"] += 1
                parent_node["files"].append({
                    "id": child["id"],
                    "name": child.get("name", "<unnamed>"),
                    "mimeType": mime,
                })

    return node


class _PartialAccessError(Exception):
    pass


def _list_drive_children(client: DriveClient, drive_id: str, folder_id: str) -> list[dict]:
    """List children of a folder within a Shared Drive, with retry on 429."""
    items: list[dict] = []
    page_token: str | None = None
    max_retries = 3

    while True:
        for attempt in range(max_retries + 1):
            try:
                resp = (
                    client._service.files()
                    .list(
                        q=f"'{folder_id}' in parents and trashed = false",
                        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime, webViewLink, md5Checksum, owners(emailAddress))",
                        pageSize=1000,
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora="drive",
                        driveId=drive_id,
                    )
                    .execute()
                )
                break
            except HttpError as e:
                if e.resp.status == 403:
                    raise _PartialAccessError(
                        f"403 Forbidden on folder {folder_id}: {e}"
                    ) from e
                if e.resp.status == 429 and attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning("Rate limited, sleeping %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                raise
            except Exception as e:
                if attempt < 1:
                    logger.warning("Network error listing folder %s, retrying: %s", folder_id, e)
                    time.sleep(2)
                    continue
                raise

        for item in resp.get("files", []):
            items.append(item)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return items


def _count_recursive(node: dict) -> tuple[int, int, int]:
    """Return (total_folders, total_files, max_depth) from a folder tree node."""
    total_folders = len(node.get("subfolders", []))
    total_files = node.get("file_count_direct", 0)
    max_depth = node.get("depth", 0)

    for sub in node.get("subfolders", []):
        sf, sfi, sd = _count_recursive(sub)
        total_folders += sf
        total_files += sfi
        max_depth = max(max_depth, sd)

    return total_folders, total_files, max_depth


def walk_drive(client: DriveClient, drive_id: str, slug: str, drive_name_google: str = "") -> dict:
    """
    Recursively walk a single Shared Drive.  Returns the drive-level dict
    matching the manifest schema.  On permission errors, returns a dict
    with status='not_shared'.  Does not raise.
    """
    sensitive = slug in config.SENSITIVE_DRIVE_SLUGS

    try:
        root = _walk_folder(client, drive_id, drive_id, drive_name_google or slug, "/", 0)
    except HttpError as e:
        return {
            "slug": slug,
            "drive_id": drive_id,
            "drive_name_google": drive_name_google,
            "sensitive_flag": sensitive,
            "status": "walk_failed",
            "error": str(e),
        }
    except Exception as e:
        return {
            "slug": slug,
            "drive_id": drive_id,
            "drive_name_google": drive_name_google,
            "sensitive_flag": sensitive,
            "status": "walk_failed",
            "error": str(e),
        }

    total_folders, total_files, max_depth = _count_recursive(root)

    return {
        "slug": slug,
        "drive_id": drive_id,
        "drive_name_google": drive_name_google,
        "sensitive_flag": sensitive,
        "status": "walked",
        "total_folders": total_folders,
        "total_files": total_files,
        "max_depth": max_depth,
        "root": root,
    }


# ---------------------------------------------------------------------------
# Full walk
# ---------------------------------------------------------------------------

def walk_all(client: DriveClient, drive_map: dict[str, str]) -> dict:
    """
    Walk every drive in drive_map ({slug: drive_id}).  Handles partial
    failures — one drive failing does not stop the others.
    """
    started = datetime.now(timezone.utc)
    drives_result: list[dict] = []
    not_shared: list[str] = []

    # Discover what the SA can actually see
    visible = discover_shared_drives(client)
    visible_ids = set(visible.keys())

    for slug, drive_id in drive_map.items():
        if not drive_id or drive_id not in visible_ids:
            not_shared.append(slug)
            drives_result.append({
                "slug": slug,
                "drive_id": None,
                "status": "not_shared",
                "error": "Drive not visible to service account — Phase B share pending",
                "sensitive_flag": slug in config.SENSITIVE_DRIVE_SLUGS,
            })
            continue

        drive_name = visible[drive_id]["name"]
        logger.info("Walking drive: %s (%s)", slug, drive_name)
        result = walk_drive(client, drive_id, slug, drive_name)
        drives_result.append(result)

    finished = datetime.now(timezone.utc)
    accessible = sum(1 for d in drives_result if d["status"] != "not_shared")

    return {
        "walk_started_at": started.isoformat(),
        "walk_finished_at": finished.isoformat(),
        "walk_duration_seconds": round((finished - started).total_seconds(), 1),
        "service_account_email": client.service_account_email,
        "drives_expected": len(drive_map),
        "drives_accessible": accessible,
        "drives_not_shared": not_shared,
        "drives": drives_result,
    }


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def write_manifest(manifest: dict, output_path: Path | None = None) -> Path:
    """Write manifest JSON to disk. Returns the written path."""
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/inventories")
        output_path = output_dir / f"folder_walk_{ts}.json"
    else:
        output_dir = output_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, default=str))
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Walk Google Shared Drives and produce a folder inventory manifest."
    )
    parser.add_argument(
        "--discover", action="store_true",
        help="List drives the service account can see, then exit.",
    )
    parser.add_argument(
        "--drive", type=str, default=None,
        help="Walk a single drive by slug (e.g. '1-operations').",
    )
    parser.add_argument(
        "--out", type=str, default=None,
        help="Custom output path for the manifest JSON.",
    )
    args = parser.parse_args()

    # Build client — exits 2 on auth/config error
    try:
        client = DriveClient()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(
            "Hint: run via  railway run --service rf-nashat-clone python3 -m ingester.folder_walk",
            file=sys.stderr,
        )
        return 2

    # --discover: just list drives and exit
    if args.discover:
        visible = discover_shared_drives(client)
        print(f"\nService account: {client.service_account_email}")
        print(f"Visible Shared Drives: {len(visible)}\n")
        for did, info in sorted(visible.items(), key=lambda x: x[1]["name"]):
            print(f"  {info['name']}")
            print(f"    ID: {did}")
            print()
        return 0

    # --drive: walk a single drive
    if args.drive:
        slug = args.drive
        drive_id = config.SHARED_DRIVE_IDS.get(slug, "")
        if not drive_id:
            print(f"ERROR: slug '{slug}' not found in SHARED_DRIVE_IDS or has empty ID.", file=sys.stderr)
            print("Run --discover first and populate config.py.", file=sys.stderr)
            return 2

        visible = discover_shared_drives(client)
        drive_name = visible.get(drive_id, {}).get("name", slug)
        print(f"Walking single drive: {slug} ({drive_name})")
        result = walk_drive(client, drive_id, slug, drive_name)

        manifest = {
            "walk_started_at": datetime.now(timezone.utc).isoformat(),
            "walk_finished_at": datetime.now(timezone.utc).isoformat(),
            "service_account_email": client.service_account_email,
            "drives_expected": 1,
            "drives_accessible": 1 if result["status"] == "walked" else 0,
            "drives": [result],
        }
        out_path = Path(args.out) if args.out else None
        written = write_manifest(manifest, out_path)
        _print_summary(manifest)
        print(f"\nManifest written to: {written}")
        return 0

    # Default: full walk
    drive_map = config.SHARED_DRIVE_IDS
    if not any(drive_map.values()):
        print("ERROR: SHARED_DRIVE_IDS in config.py has no populated drive IDs.", file=sys.stderr)
        print("Run --discover first and populate config.py.", file=sys.stderr)
        return 2

    print(f"Starting full walk of {len(drive_map)} drives...")
    manifest = walk_all(client, drive_map)

    out_path = Path(args.out) if args.out else None
    written = write_manifest(manifest, out_path)
    _print_summary(manifest)
    print(f"\nManifest written to: {written}")

    # Exit 1 if zero drives walked
    walked = sum(1 for d in manifest["drives"] if d["status"] == "walked")
    return 0 if walked > 0 else 1


def _print_summary(manifest: dict) -> None:
    """Print a human-readable summary of the walk."""
    print("\n" + "=" * 60)
    print("FOLDER WALK SUMMARY")
    print("=" * 60)
    print(f"Service account: {manifest.get('service_account_email', 'N/A')}")
    print(f"Duration: {manifest.get('walk_duration_seconds', 'N/A')}s")
    print(f"Drives expected: {manifest.get('drives_expected', 'N/A')}")
    print(f"Drives accessible: {manifest.get('drives_accessible', 'N/A')}")

    not_shared = manifest.get("drives_not_shared", [])
    if not_shared:
        print(f"Not shared: {', '.join(not_shared)}")

    print(f"\n{'Slug':<40} {'Status':<15} {'Folders':>8} {'Files':>8} {'Depth':>6}")
    print("-" * 80)
    for d in manifest.get("drives", []):
        slug = d.get("slug", "?")
        status = d.get("status", "?")
        folders = d.get("total_folders", "")
        files = d.get("total_files", "")
        depth = d.get("max_depth", "")
        sens = " [SENSITIVE]" if d.get("sensitive_flag") else ""
        print(f"{slug:<40} {status:<15} {folders:>8} {files:>8} {depth:>6}{sens}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
