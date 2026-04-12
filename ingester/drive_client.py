"""
Google Drive client — service-account-backed wrapper around the Drive v3 API.

Responsibilities:
  - Load the service account credential from the GOOGLE_SERVICE_ACCOUNT_JSON
    env var (a JSON string, NOT a file path — this is the Railway-friendly form)
  - Recursively walk a Drive folder tree and yield DriveFile records
  - Classify each file by which ingestion pipeline it should route to
  - Stay READ-ONLY — the service account is granted Viewer access only

Nothing in this module touches ChromaDB, LLMs, or local filesystem state.
It is deliberately the lowest layer of the ingester so it can be tested
in isolation with `python3 -m ingester.main inventory --program fksp`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Iterator, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import config

# Read-only scope — the service account cannot write or delete anything
# even if we had a bug asking it to.
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Fields we request from Drive for every file. Keeping this tight minimizes
# quota consumption on large folder walks.
FILE_FIELDS = (
    "id, name, mimeType, size, modifiedTime, "
    "parents, md5Checksum, webViewLink"
)
LIST_FIELDS = f"nextPageToken, files({FILE_FIELDS})"


@dataclass
class DriveFile:
    """
    A single file found during a Drive walk, classified by pipeline.

    `pipeline` is the string key used by main.py to decide how to process it:
      - "video"        → Pipeline A (video with slides + voiceover)
      - "pdf"          → Pipeline B or C (decided later by probing the PDF)
      - "image"        → Pipeline D (standalone image/design)
      - "google_doc"   → Google-native doc, needs export to text
      - "google_slides"→ Google-native slides, needs export + per-slide treatment
      - "folder"       → not a file, folders are traversed not processed
      - "skip"         → unknown/unsupported mime type
    """

    id: str
    name: str
    mime_type: str
    size: Optional[int]
    modified_time: Optional[str]
    md5_checksum: Optional[str]
    web_view_link: Optional[str]
    # Full slash-joined path from the walk root, e.g. "FKSP/Module 1/Lesson 1.mp4"
    path: str
    # How deep under the walk root (0 = immediate child of the root)
    depth: int
    pipeline: str
    parents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def classify(mime_type: str) -> str:
    """Map a Drive mimeType to an ingestion pipeline key."""
    if mime_type == config.MIME_FOLDER:
        return "folder"
    if mime_type == config.MIME_PDF:
        return "pdf"
    if mime_type == config.MIME_GOOGLE_DOC:
        return "google_doc"
    if mime_type == config.MIME_GOOGLE_SLIDES:
        return "google_slides"
    if mime_type in config.VIDEO_MIMES:
        return "video"
    if mime_type in config.IMAGE_MIMES:
        return "image"
    return "skip"


class DriveClient:
    """Thin wrapper around the Drive v3 API keyed to a service account."""

    def __init__(self, credentials_json: Optional[str] = None):
        """
        Load credentials from the GOOGLE_SERVICE_ACCOUNT_JSON env var (a raw
        JSON string), or accept an explicit JSON string for testing.

        We deliberately do NOT accept a file path argument — the production
        form of this credential is an env var on Railway, and we want the
        local dev form to match so there is no divergence.
        """
        raw = credentials_json or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not raw:
            cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if cred_path:
                try:
                    with open(cred_path, "r") as f:
                        raw = f.read()
                except OSError as e:
                    raise RuntimeError(
                        f"GOOGLE_APPLICATION_CREDENTIALS points to "
                        f"{cred_path!r} but the file could not be read: {e}"
                    ) from e
        if not raw:
            raise RuntimeError(
                "No Drive credentials found. Set either "
                "GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON, Railway-style) or "
                "GOOGLE_APPLICATION_CREDENTIALS (file path, local-dev-style)."
            )
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                "Service account credentials are not valid JSON. "
                f"Parse error: {e}"
            )
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=DRIVE_SCOPES
        )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._service_account_email = info.get("client_email", "<unknown>")

    @property
    def service_account_email(self) -> str:
        return self._service_account_email

    # ------------------------------------------------------------------ #
    # Folder walking
    # ------------------------------------------------------------------ #

    def get_file(self, file_id: str) -> dict:
        """Fetch a single file's metadata by ID. Useful for root-folder lookup."""
        return (
            self._service.files()
            .get(fileId=file_id, fields=FILE_FIELDS, supportsAllDrives=True)
            .execute()
        )

    def list_children(self, folder_id: str) -> Iterator[dict]:
        """
        Yield every immediate child of a folder, handling pagination and
        shared-drive visibility. Raw Drive dicts, not DriveFile records.
        """
        page_token: Optional[str] = None
        while True:
            try:
                resp = (
                    self._service.files()
                    .list(
                        q=f"'{folder_id}' in parents and trashed = false",
                        fields=LIST_FIELDS,
                        pageSize=1000,
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora="allDrives",
                    )
                    .execute()
                )
            except HttpError as e:
                raise RuntimeError(
                    f"Drive API error listing folder {folder_id}: {e}"
                ) from e
            for item in resp.get("files", []):
                yield item
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    def walk(self, root_folder_id: str, root_name: Optional[str] = None) -> Iterator[DriveFile]:
        """
        Recursively walk a Drive folder tree starting at root_folder_id.

        Yields one DriveFile per file AND per folder encountered (folders
        are yielded so callers can see the tree structure, but they won't
        be routed to any pipeline — their `pipeline` will be "folder").

        Order is not guaranteed; this is a BFS-ish traversal using a queue.
        """
        if root_name is None:
            root_meta = self.get_file(root_folder_id)
            root_name = root_meta.get("name", root_folder_id)

        # Queue entries: (drive_folder_id, path_prefix, depth)
        queue: list[tuple[str, str, int]] = [(root_folder_id, root_name, 0)]

        while queue:
            folder_id, prefix, depth = queue.pop(0)
            for item in self.list_children(folder_id):
                name = item.get("name", "<unnamed>")
                mime = item.get("mimeType", "")
                item_path = f"{prefix}/{name}"
                size_raw = item.get("size")
                size = int(size_raw) if size_raw is not None else None
                record = DriveFile(
                    id=item["id"],
                    name=name,
                    mime_type=mime,
                    size=size,
                    modified_time=item.get("modifiedTime"),
                    md5_checksum=item.get("md5Checksum"),
                    web_view_link=item.get("webViewLink"),
                    path=item_path,
                    depth=depth,
                    pipeline=classify(mime),
                    parents=item.get("parents", []),
                )
                yield record
                if record.pipeline == "folder":
                    queue.append((record.id, item_path, depth + 1))
