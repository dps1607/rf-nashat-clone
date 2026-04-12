# Folder-Selection UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the folder-selection UI into the existing Flask admin console, enabling admins to browse Drive folder trees, select content for ingestion, and assign folders to libraries.

**Architecture:** New Flask routes added to `admin_ui/app.py` (additive only — no existing routes modified). Manifest JSON loaded at startup for search and drive metadata. Live Drive API calls via `DriveClient` for tree expansion (2-level prefetch). Vanilla JS tree component with tri-state checkboxes. Selection state persisted to JSON file (registry integration is Phase E).

**Tech Stack:** Flask/Jinja2 (existing), DriveClient (existing `ingester/drive_client.py`), vanilla HTML/CSS/JS (matching existing brand), JSONL audit log (existing `admin_ui/audit.py`)

**Key files to read before starting:**
- `PHASE_D_POST_SPEC.md` — the authoritative spec
- `admin_ui/app.py` — existing Flask routes (DO NOT MODIFY existing routes)
- `admin_ui/auth.py` — `login_required` decorator, `current_user()` function
- `admin_ui/audit.py` — `audit.log()` function, existing event types
- `admin_ui/templates/base.html` — base Jinja template with topbar and `{% block content %}`
- `admin_ui/static/style.css` — brand palette (CSS vars: `--navy`, `--rose`, `--coral`, etc.)
- `ingester/drive_client.py` — `DriveClient` class, `list_children()`, `DRIVE_SCOPES`
- `ingester/config.py` — `SHARED_DRIVE_IDS`, `SENSITIVE_DRIVE_SLUGS`
- `data/inventories/folder_walk_20260411_213418.json` — authoritative manifest (1.7MB)

**CRITICAL RULES (from spec — read these before every task):**
- Do NOT modify existing Flask routes in `admin_ui/app.py`
- Do NOT add `EXCLUDED_FOLDER_PATTERNS` for Christina Massinople Park's folders — her content IS ingested
- 8-labs (0 folders, 12 files, depth 0) must render as a flat file list, not an error
- 10-external-content personal-name Zoom folders get NO special treatment
- Do NOT run `railway variables` bare
- Do NOT touch credentials or run ingestion

---

### Task 1: Manifest loader module

**Files:**
- Create: `admin_ui/manifest.py`

**Step 1: Create the manifest loader**

This module loads the most recent `folder_walk_*.json` from `data/inventories/`, parses it, and provides helper methods for search and drive metadata lookup. It is used by the admin routes for search and for the initial page load (drive list with metadata).

```python
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
        self._folder_index: list[dict] = []  # flat list for search
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
            slug = drive["slug"]
            self._index_node(slug, drive.get("root", {}))

    def _index_node(self, drive_slug: str, node: dict, parent_path: str = "") -> None:
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
            self._index_node(drive_slug, sub, path)

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
        """Case-insensitive substring search on folder paths. Returns up to `limit` matches."""
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
```

**Step 2: Commit**

```bash
git add admin_ui/manifest.py
git commit -m "feat: manifest loader for folder-selection UI"
```

---

### Task 2: Drive API wrapper for admin

**Files:**
- Create: `admin_ui/drive_api.py`

**Step 1: Create the Drive API wrapper**

This module wraps `DriveClient` for use by the admin UI. It provides tree-fetching methods with graceful fallback to manifest data when the credential is not available (local dev without Railway).

```python
"""
Drive API wrapper for the admin UI.

Uses DriveClient from the ingester package for live folder listing.
Falls back to manifest data when GOOGLE_SERVICE_ACCOUNT_JSON is not set
(common in local dev without railway run).
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

_client = None  # lazy singleton
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
    Returns list of {id, name, mimeType, isFolder, fileCount} dicts.

    Uses corpora='drive' with driveId for Shared Drive folders.
    """
    client = _get_client()
    if client is None:
        return []

    from ingester import config
    items = []
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

    # Sort: folders first, then files, alphabetical within each group
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
```

**Step 2: Commit**

```bash
git add admin_ui/drive_api.py
git commit -m "feat: Drive API wrapper for admin tree endpoints"
```

---

### Task 3: Flask routes — tree, search, save, audit

**Files:**
- Modify: `admin_ui/app.py` (ADD routes at the end, before `if __name__`)

**Step 1: Add imports and manifest initialization**

At the top of `app.py`, after the existing imports, add:

```python
from admin_ui.manifest import ManifestLoader
from admin_ui import drive_api
```

After the `audit.log("startup", ...)` call, add:

```python
# Load the most recent folder-walk manifest for the folder-selection UI
manifest = ManifestLoader()
```

**Step 2: Add all new routes**

Add these routes AFTER the existing `api_health` route and BEFORE the `ratelimit_handler`:

```python
# -----------------------------------------------------------------------------
# Folder-selection UI routes (Phase D-post)
# -----------------------------------------------------------------------------

@app.route("/admin/folders")
@login_required
def folders():
    """Render the folder-selection page."""
    from ingester import config
    drives = manifest.drives
    # Enrich with sensitive flag from config (in case manifest is stale)
    sensitive_slugs = config.SENSITIVE_DRIVE_SLUGS
    for d in drives:
        d["sensitive_flag"] = d.get("slug", "") in sensitive_slugs
    return render_template(
        "folders.html",
        drives=drives,
        walk_metadata=manifest.walk_metadata,
    )


@app.route("/admin/api/drive/<drive_id>/tree")
@login_required
def api_drive_tree(drive_id):
    """Return two-level folder tree for a drive. Live API with manifest fallback."""
    if drive_api.is_available():
        try:
            tree = drive_api.get_two_level_tree(drive_id)
            return jsonify(tree)
        except Exception as e:
            return jsonify({"error": str(e), "fallback": True}), 500

    # Fallback: extract two levels from manifest
    slug = request.args.get("slug", "")
    drive_data = manifest.get_drive_tree(slug)
    if not drive_data or not drive_data.get("root"):
        return jsonify({"children": []})
    root = drive_data["root"]
    children = []
    for sub in root.get("subfolders", []):
        child = {
            "id": sub["id"],
            "name": sub.get("name", ""),
            "is_folder": True,
            "children": [],
            "file_count_direct": sub.get("file_count_direct", 0),
        }
        for subsub in sub.get("subfolders", []):
            child["children"].append({
                "id": subsub["id"],
                "name": subsub.get("name", ""),
                "is_folder": True,
                "children": [],
                "file_count_direct": subsub.get("file_count_direct", 0),
            })
        children.append(child)
    # Also include root-level files (for flat drives like 8-labs)
    if root.get("file_count_direct", 0) > 0 and not root.get("subfolders"):
        # Flat drive: signal that files exist at root level
        pass  # file_count is shown in the drive metadata
    return jsonify({
        "children": children,
        "root_file_count": root.get("file_count_direct", 0),
    })


@app.route("/admin/api/folder/<folder_id>/children")
@login_required
def api_folder_children(folder_id):
    """Return one level of children for a folder (lazy deeper loading)."""
    drive_id = request.args.get("drive_id", "")
    if not drive_id:
        return jsonify({"error": "drive_id query param required"}), 400
    if not drive_api.is_available():
        return jsonify({"error": "Drive API not available", "children": []}), 503
    try:
        children = drive_api.list_children_for_tree(folder_id, drive_id)
        return jsonify({"children": children})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/api/folders/search")
@login_required
def api_folders_search():
    """Search manifest folder paths by substring."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    results = manifest.search_folders(q, limit=20)
    total = len([1 for e in manifest._folder_index
                 if q.lower() in e["path"].lower() or q.lower() in e["name"].lower()])
    return jsonify({
        "results": results,
        "total": total,
        "showing": len(results),
    })


@app.route("/admin/api/folders/save", methods=["POST"])
@login_required
def api_folders_save():
    """Save folder selection state to JSON file."""
    import json as json_mod
    from pathlib import Path as P

    user = current_user()
    user_label = _user_label(user)
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "JSON body required"}), 400

    # Write selection state to data dir
    state_path = P(os.environ.get("INGESTER_DATA_ROOT", "data")) / "selection_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json_mod.dumps(data, indent=2, default=str))

    # Audit log
    folder_count = len(data.get("selected_folders", []))
    audit.log("folder_selection_saved", user=user_label, details={
        "selected_folders": folder_count,
        "libraries": list(data.get("library_assignments", {}).keys()),
    })

    return jsonify({"ok": True, "saved_folders": folder_count})


@app.route("/admin/api/folders/refresh-inventory", methods=["POST"])
@login_required
def api_refresh_inventory():
    """Reload manifest from disk (after a new folder_walk run)."""
    user_label = _user_label(current_user())
    ok = manifest.load()
    audit.log("inventory_refreshed", user=user_label, details={"success": ok})
    return jsonify({"ok": ok, "drives": len(manifest.drives)})


@app.route("/admin/audit")
@login_required
def audit_view():
    """Render the audit log view."""
    return render_template("audit.html")


@app.route("/admin/api/audit/events")
@login_required
def api_audit_events():
    """Return recent audit events as JSON."""
    n = request.args.get("n", 100, type=int)
    events = audit.tail(n)
    action_filter = request.args.get("action", "")
    if action_filter:
        events = [e for e in events if e.get("event") == action_filter]
    return jsonify({"events": list(reversed(events))})  # newest first
```

**Step 3: Update CSP to allow Google Fonts (if not already)**

Check if the CSP `style-src` and `font-src` allow Google Fonts. The existing admin console already uses them, so this should already work. If font loading fails, add `"fonts.googleapis.com"` to `style-src` and `"fonts.gstatic.com"` to a new `font-src` entry in the `_csp` dict.

**Step 4: Commit**

```bash
git add admin_ui/app.py
git commit -m "feat: add folder-selection API routes to admin UI"
```

---

### Task 4: Folder-selection page template

**Files:**
- Create: `admin_ui/templates/folders.html`

**Step 1: Create the template**

Extends `base.html`. Contains:
- Page header with title "Content Selection" and walk metadata (when last refreshed)
- Search input above the tree
- Drive list rendered as expandable tree nodes
- Each drive node shows: name, status, folder count, file count, sensitive badge
- Not-shared drives rendered as disabled/grayed out
- "Refresh Inventory" button (calls `/admin/api/folders/refresh-inventory`)
- "Save Selection" button (calls `/admin/api/folders/save`)
- Sensitive-drive confirmation modal (hidden by default)

Key template structure:

```html
{% extends "base.html" %}
{% block title %}Content Selection — Nashat Admin{% endblock %}

{% block content %}
<div class="folders-layout">
  <div class="folders-header">
    <h1>Content Selection</h1>
    <div class="folders-meta">
      {% if walk_metadata.walk_finished_at %}
      <span class="meta-label">Last inventory:</span>
      <span class="meta-value">{{ walk_metadata.walk_finished_at }}</span>
      {% endif %}
      <button class="btn-secondary" id="btn-refresh">Refresh Inventory</button>
    </div>
  </div>

  <div class="folders-toolbar">
    <div class="search-container">
      <input type="text" id="folder-search" placeholder="Search folders..." autocomplete="off">
      <div id="search-results" class="search-results hidden"></div>
    </div>
    <button class="btn-primary" id="btn-save">Save Selection</button>
  </div>

  <div class="folder-tree" id="folder-tree">
    {% for drive in drives %}
    <div class="tree-drive {% if drive.status == 'not_shared' %}drive-disabled{% endif %}"
         data-slug="{{ drive.slug }}"
         data-drive-id="{{ drive.drive_id or '' }}"
         data-sensitive="{{ drive.sensitive_flag | lower }}">
      <div class="tree-node tree-node-drive">
        <span class="tree-toggle {% if drive.status != 'not_shared' %}expandable{% endif %}">&#9654;</span>
        <input type="checkbox" class="tree-check drive-check"
               data-slug="{{ drive.slug }}"
               {% if drive.status == 'not_shared' %}disabled{% endif %}>
        <span class="drive-name">{{ drive.drive_name_google or drive.slug }}</span>
        {% if drive.sensitive_flag %}
        <span class="sensitive-flag" title="Flagged: sensitive content">&#x1F512;</span>
        {% endif %}
        {% if drive.status == 'not_shared' %}
        <span class="drive-status-badge">Not shared</span>
        {% else %}
        <span class="drive-stats">{{ drive.total_folders }} folders &middot; {{ drive.total_files }} files</span>
        {% endif %}
      </div>
      <div class="tree-children hidden"></div>
    </div>
    {% endfor %}
  </div>
</div>

<!-- Sensitive drive confirmation modal -->
<div id="sensitive-modal" class="modal hidden">
  <div class="modal-backdrop"></div>
  <div class="modal-content">
    <h3>&#x26A0; This folder is in a flagged drive</h3>
    <p>Drive <strong id="modal-drive-name"></strong> is flagged as containing sensitive content.
       Are you sure you want to include content from this folder in the RAG?</p>
    <div class="modal-actions">
      <button class="btn-secondary" id="modal-cancel">Cancel</button>
      <button class="btn-primary" id="modal-confirm">Yes, include</button>
    </div>
  </div>
</div>

<!-- Save confirmation toast -->
<div id="save-toast" class="toast hidden"></div>
{% endblock %}

{% block scripts %}
<link rel="stylesheet" href="{{ url_for('static', filename='folder-tree.css') }}">
<script src="{{ url_for('static', filename='folder-tree.js') }}"></script>
<script src="{{ url_for('static', filename='folder-search.js') }}"></script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add admin_ui/templates/folders.html
git commit -m "feat: folder-selection page template"
```

---

### Task 5: Folder tree CSS

**Files:**
- Create: `admin_ui/static/folder-tree.css`

**Step 1: Create the stylesheet**

Must use the existing CSS variables from `style.css` (`--navy`, `--rose`, `--coral`, `--charcoal`, `--gray`, `--off-white`, `--serif`, `--sans`). Key styles:

- `.folders-layout` — full-width container with padding
- `.folders-header` — flex row with h1 (Cormorant Garamond) and metadata
- `.folders-toolbar` — flex row with search input and save button
- `.tree-drive` — drive-level container with slight border
- `.tree-node` — flex row: toggle + checkbox + name + stats
- `.tree-node-drive` — slightly larger/bolder for drive level
- `.tree-children` — nested container, indented via `padding-left`
- `.tree-toggle` — rotate arrow on expand (`transform: rotate(90deg)`)
- `.tree-check` — styled checkbox (navy accent)
- `.sensitive-flag` — copper/coral colored lock icon
- `.drive-disabled` — `opacity: 0.5`, no pointer events
- `.drive-status-badge` — small pill for "Not shared"
- `.drive-stats` — gray text with folder/file counts
- `.modal` + `.modal-backdrop` — centered overlay for sensitive confirmation
- `.search-container` — relative positioned for dropdown
- `.search-results` — absolute dropdown, max 20 items
- `.toast` — fixed bottom-right notification
- `.hidden` — `display: none`
- Indentation: `padding-left: calc(var(--depth, 0) * 1.25rem)`

**Step 2: Commit**

```bash
git add admin_ui/static/folder-tree.css
git commit -m "feat: folder tree CSS with brand styling"
```

---

### Task 6: Folder tree JS component

**Files:**
- Create: `admin_ui/static/folder-tree.js`

**Step 1: Create the tree component**

This is the largest piece of frontend code. It handles:

1. **Drive expand/collapse:** Click toggle arrow on a drive node → fetch two-level tree via `/admin/api/drive/<drive_id>/tree?slug=<slug>` → render children into `.tree-children` container → remove `.hidden` class.

2. **Deeper lazy loading:** Click toggle on a depth-2+ folder → fetch via `/admin/api/folder/<folder_id>/children?drive_id=<drive_id>` → render one level.

3. **Flat drive rendering (8-labs case):** When drive has `total_folders === 0` and `total_files > 0`, the tree response will have `root_file_count > 0` and empty `children`. Render a message: "12 files at drive root" with a single drive-level checkbox. No expand arrow needed — the checkbox covers all files.

4. **Checkbox cascade:** Checking a parent checks all visible children. Unchecking unchecks all visible children. Partially-checked subtree shows indeterminate state on parent.

5. **Sensitive drive modal:** Before checking any node inside a `data-sensitive="true"` drive, show the confirmation modal. On confirm, proceed with check and log via audit. On cancel, revert the checkbox.

6. **Node rendering function:** `renderChildren(container, children, driveId, driveSensitive, depth)` — creates tree nodes with proper depth indentation.

Key JS structure:

```javascript
(function() {
  'use strict';

  // State
  const selectionState = {};  // folder_id -> {checked, library}
  let pendingSensitiveCheck = null;

  // DOM refs
  const tree = document.getElementById('folder-tree');
  const modal = document.getElementById('sensitive-modal');
  const saveBtn = document.getElementById('btn-save');
  const refreshBtn = document.getElementById('btn-refresh');

  // Initialize drive toggles
  tree.querySelectorAll('.tree-drive').forEach(initDriveNode);

  function initDriveNode(driveEl) {
    const toggle = driveEl.querySelector('.tree-toggle');
    const check = driveEl.querySelector('.tree-check');
    const childContainer = driveEl.querySelector('.tree-children');
    const driveId = driveEl.dataset.driveId;
    const slug = driveEl.dataset.slug;
    const sensitive = driveEl.dataset.sensitive === 'true';
    let loaded = false;

    if (!driveId) return;  // not_shared drives have no driveId

    toggle.addEventListener('click', async () => {
      if (!loaded) {
        toggle.textContent = '...';
        const resp = await fetch(`/admin/api/drive/${driveId}/tree?slug=${slug}`);
        const data = await resp.json();
        renderChildren(childContainer, data.children || [], driveId, sensitive, 1);
        // Handle flat drives (root files only, no subfolders)
        if (data.root_file_count > 0 && (!data.children || data.children.length === 0)) {
          renderFlatDriveMessage(childContainer, data.root_file_count);
        }
        loaded = true;
        toggle.textContent = '\u25BC';  // down arrow
        childContainer.classList.remove('hidden');
      } else {
        const isHidden = childContainer.classList.toggle('hidden');
        toggle.textContent = isHidden ? '\u25B6' : '\u25BC';
      }
    });

    check.addEventListener('change', (e) => {
      if (sensitive && e.target.checked) {
        e.target.checked = false;
        showSensitiveModal(driveEl, check);
        return;
      }
      cascadeCheck(driveEl, e.target.checked);
    });
  }

  function renderChildren(container, children, driveId, sensitive, depth) { /* ... */ }
  function renderFlatDriveMessage(container, fileCount) { /* ... */ }
  function cascadeCheck(parentEl, checked) { /* ... */ }
  function updateParentCheckState(childEl) { /* ... */ }
  function showSensitiveModal(driveEl, checkbox) { /* ... */ }

  // Save handler
  saveBtn.addEventListener('click', async () => { /* POST to /admin/api/folders/save */ });

  // Refresh handler
  refreshBtn.addEventListener('click', async () => { /* POST to /admin/api/folders/refresh-inventory */ });

  // Modal handlers
  document.getElementById('modal-cancel').addEventListener('click', () => { /* ... */ });
  document.getElementById('modal-confirm').addEventListener('click', () => { /* ... */ });
})();
```

**Step 2: Commit**

```bash
git add admin_ui/static/folder-tree.js
git commit -m "feat: folder tree JS component with lazy loading and checkbox cascade"
```

---

### Task 7: Search component JS

**Files:**
- Create: `admin_ui/static/folder-search.js`

**Step 1: Create the search component**

- Debounced input (300ms) on `#folder-search`
- Calls `/admin/api/folders/search?q=...`
- Renders results in `#search-results` dropdown
- Each result shows: drive slug + folder path
- Clicking a result: expands the tree to that drive, highlights the folder
- Max 20 results shown, with "N more..." if truncated
- Escape key or click-outside closes the dropdown

**Step 2: Commit**

```bash
git add admin_ui/static/folder-search.js
git commit -m "feat: folder search component with debounced manifest query"
```

---

### Task 8: Audit log view

**Files:**
- Create: `admin_ui/templates/audit.html`

**Step 1: Create the audit log template**

Extends `base.html`. Simple table view:
- Filter dropdown by event type
- Columns: timestamp, event, user, IP, details
- Loads via fetch to `/admin/api/audit/events?n=100`
- Auto-refresh button
- Newest events first

**Step 2: Commit**

```bash
git add admin_ui/templates/audit.html
git commit -m "feat: audit log view template"
```

---

### Task 9: Add navigation links to base template

**Files:**
- Modify: `admin_ui/templates/base.html`

**Step 1: Add nav links to the topbar**

In the `.topbar-left` div, after the brand and env-tag spans, add navigation links:

```html
<nav class="topbar-nav">
  <a href="{{ url_for('edit') }}" class="nav-link">Editor</a>
  <a href="{{ url_for('folders') }}" class="nav-link">Content</a>
  <a href="{{ url_for('audit_view') }}" class="nav-link">Audit</a>
</nav>
```

Add corresponding CSS for `.topbar-nav` and `.nav-link` to `style.css` (or inline in `base.html` within a `<style>` block if modifying style.css feels too invasive — either is fine since the CSP allows inline styles).

**Step 2: Commit**

```bash
git add admin_ui/templates/base.html
git commit -m "feat: add Content and Audit nav links to admin topbar"
```

---

### Task 10: Integration test — verify routes return correct responses

**Step 1: Manual verification**

Start the admin UI locally:
```bash
cd admin_ui && python3 app.py
```

(This will work without Drive credentials — the manifest loader and manifest-based fallback will handle tree expansion.)

Verify these endpoints:
1. `GET /admin/folders` — returns HTML with 9 drive nodes
2. `GET /admin/api/folders/search?q=FKSP` — returns JSON with matching folders
3. `GET /admin/api/drive/{drive_id}/tree?slug=8-labs` — returns JSON (may be from manifest fallback)
4. `POST /admin/api/folders/save` with JSON body — writes `data/selection_state.json`
5. `GET /admin/audit` — returns HTML audit log page
6. `GET /admin/api/audit/events` — returns JSON array of events

**Step 2: Fix any issues found during verification**

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Phase D-post folder-selection UI complete"
```

---

## Task dependency graph

```
Task 1 (manifest.py) ──┐
                        ├── Task 3 (Flask routes) ── Task 4 (template) ── Task 6 (tree JS) ── Task 7 (search JS)
Task 2 (drive_api.py) ─┘                                                                      │
                                                                                               ├── Task 9 (nav links)
                                                                    Task 5 (CSS) ──────────────┘
                                                                    Task 8 (audit template) ───── Task 10 (verify)
```

Tasks 1 and 2 are independent (parallel). Tasks 4, 5, 8 can also be parallelized once Task 3 is done. Task 10 is the final verification pass.

---

## Stretch goals (Phase E, not this plan)

- Library assignment sub-flow (dropdown for existing libraries, create new)
- Library inventory view (`/admin/libraries`)
- Library retire action
- Diff engine integration (Save triggers real ingestion)
- Registry writes (replace flat JSON with registry entries)
- Live API tree expansion (upgrade from manifest fallback to always-live)
