"""
Drive API wrapper for the admin UI.

Uses DriveClient from the ingester package for live folder listing.
Falls back gracefully when GOOGLE_SERVICE_ACCOUNT_JSON is not set
(common in local dev without railway run).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_client_attempted = False


def _get_client():
    """Lazy-init DriveClient. Returns None if credential not available."""
    global _client, _client_attempted
    if _client_attempted:
        return _client
    _client_attempted = True
    try:
        from ingester.drive_client import DriveClient
        _client = DriveClient()
        logger.info("DriveClient initialized for admin UI")
    except Exception as e:
        logger.warning("DriveClient not available (credential missing?): %s", e)
        _client = None
    return _client


def list_children_for_tree(folder_id: str, drive_id: str) -> list[dict]:
    """
    List immediate children of a folder via the Drive API.
    Returns list of {id, name, is_folder} dicts sorted folders-first.
    """
    client = _get_client()
    if client is None:
        return []

    from ingester import config

    items: list[dict] = []
    page_token = None
    while True:
        resp = (
            client._service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="drive",
                driveId=drive_id,
            )
            .execute()
        )
        for item in resp.get("files", []):
            is_folder = item.get("mimeType") == config.MIME_FOLDER
            items.append({
                "id": item["id"],
                "name": item.get("name", "<unnamed>"),
                "is_folder": is_folder,
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    items.sort(key=lambda x: (not x["is_folder"], x["name"].lower()))
    return items


def get_two_level_tree(drive_id: str) -> dict:
    """
    Fetch two levels of children for a drive root.
    Returns {children: [{id, name, is_folder, children: [...]}]}.
    """
    root_children = list_children_for_tree(drive_id, drive_id)
    for child in root_children:
        if child["is_folder"]:
            child["children"] = list_children_for_tree(child["id"], drive_id)
        else:
            child["children"] = []
    return {"children": root_children}


def is_available() -> bool:
    """Check whether the Drive API is accessible."""
    return _get_client() is not None
