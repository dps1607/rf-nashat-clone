"""
Manifest loader — reads the Phase D-prime folder-walk inventory.

Loaded at admin startup. Provides:
  - Drive list with metadata (folder counts, file counts, depth, sensitive flag)
  - Folder path search (case-insensitive substring match)
  - Refresh (re-read from disk after a new walk)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Relative to repo root — matches where folder_walk.py writes output
_INVENTORY_DIR = Path(__file__).resolve().parent.parent / "data" / "inventories"


class ManifestLoader:
    def __init__(self, inventory_dir: Path | None = None):
        self._dir = inventory_dir or _INVENTORY_DIR
        self._manifest: dict[str, Any] | None = None
        self._folder_index: list[dict] = []
        self.load()

    def load(self) -> bool:
        """Load the most recent folder_walk_*.json. Returns True on success."""
        candidates = sorted(self._dir.glob("folder_walk_*.json"), reverse=True)
        if not candidates:
            logger.warning("No manifest found in %s", self._dir)
            self._manifest = None
            self._folder_index = []
            return False
        path = candidates[0]
        logger.info("Loading manifest: %s", path)
        with open(path, encoding="utf-8") as f:
            self._manifest = json.load(f)
        self._build_folder_index()
        return True

    def _build_folder_index(self) -> None:
        """Flatten the folder tree into a searchable list."""
        self._folder_index = []
        if not self._manifest:
            return
        for drive in self._manifest.get("drives", []):
            if drive.get("status") != "walked":
                continue
            self._index_node(drive["slug"], drive.get("root", {}))

    def _index_node(self, drive_slug: str, node: dict) -> None:
        path = node.get("path", "/")
        self._folder_index.append({
            "drive_slug": drive_slug,
            "folder_id": node.get("id", ""),
            "name": node.get("name", ""),
            "path": path,
            "depth": node.get("depth", 0),
            "file_count_direct": node.get("file_count_direct", 0),
        })
        for sub in node.get("subfolders", []):
            self._index_node(drive_slug, sub)

    @property
    def drives(self) -> list[dict]:
        """Return drive-level metadata (no folder tree — just summary stats)."""
        if not self._manifest:
            return []
        result = []
        for d in self._manifest.get("drives", []):
            result.append({
                "slug": d.get("slug"),
                "drive_id": d.get("drive_id"),
                "drive_name_google": d.get("drive_name_google", ""),
                "status": d.get("status"),
                "sensitive_flag": d.get("sensitive_flag", False),
                "total_folders": d.get("total_folders", 0),
                "total_files": d.get("total_files", 0),
                "max_depth": d.get("max_depth", 0),
            })
        return result

    def search_folders(self, query: str, limit: int = 20) -> list[dict]:
        """Case-insensitive substring search on folder paths."""
        if not query or not query.strip():
            return []
        q = query.strip().lower()
        results = []
        for entry in self._folder_index:
            if q in entry["path"].lower() or q in entry["name"].lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def count_search_results(self, query: str) -> int:
        """Count total matches (for 'N more...' display)."""
        if not query or not query.strip():
            return 0
        q = query.strip().lower()
        return sum(1 for e in self._folder_index
                   if q in e["path"].lower() or q in e["name"].lower())

    def get_folder_children(self, folder_id: str) -> list[dict] | None:
        """Look up a folder by ID in the manifest and return its children.

        Returns a list of {id, name, is_folder, children, file_count_direct}
        dicts matching the live API shape, or None if the folder is not found.
        """
        if not self._manifest:
            return None
        for drive in self._manifest.get("drives", []):
            if drive.get("status") != "walked":
                continue
            result = self._find_node(drive.get("root", {}), folder_id)
            if result is not None:
                return self._node_children_to_api_shape(result)
        return None

    def _find_node(self, node: dict, folder_id: str) -> dict | None:
        """Recursively find a node by folder ID in the manifest tree."""
        if node.get("id") == folder_id:
            return node
        for sub in node.get("subfolders", []):
            found = self._find_node(sub, folder_id)
            if found is not None:
                return found
        return None

    @staticmethod
    def _node_children_to_api_shape(node: dict) -> list[dict]:
        """Convert manifest subfolders to the same shape the live API returns."""
        children = []
        for sub in node.get("subfolders", []):
            children.append({
                "id": sub["id"],
                "name": sub.get("name", ""),
                "is_folder": True,
                "children": [],
                "file_count_direct": sub.get("file_count_direct", 0),
            })
        # Folders first (already are), sorted alphabetically
        children.sort(key=lambda x: x["name"].lower())
        return children

    def get_drive_tree(self, slug: str) -> dict | None:
        """Return the full tree for a specific drive from the manifest."""
        if not self._manifest:
            return None
        for d in self._manifest.get("drives", []):
            if d.get("slug") == slug:
                return d
        return None

    @property
    def walk_metadata(self) -> dict:
        if not self._manifest:
            return {}
        return {
            "walk_started_at": self._manifest.get("walk_started_at"),
            "walk_finished_at": self._manifest.get("walk_finished_at"),
            "walk_duration_seconds": self._manifest.get("walk_duration_seconds"),
            "drives_expected": self._manifest.get("drives_expected"),
            "drives_accessible": self._manifest.get("drives_accessible"),
        }
