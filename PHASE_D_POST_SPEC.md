# Phase D-post — Folder-Selection UI Spec (Claude Code handoff)

**Status:** Ready for Claude Code implementation
**Prerequisite:** Phase D-prime complete (manifest at `data/inventories/folder_walk_20260411_213418.json`)
**Depends on:** ADR-004 open items resolved below; ADR-001/002/003 unchanged
**Date:** 2026-04-11

---

## Goal

Build the folder-selection UI described in ADR-004 into the existing Flask
admin console, resolving all seven open design items against real manifest
data from the Phase D-prime walk. The UI is the primary mechanism by which
the RAG's content scope is controlled.

**This spec does NOT:** run ingestion, modify the diff engine, change the
registry schema (that is Phase E), touch credentials, or modify existing
Flask routes. New additive routes only.

---

## Authoritative manifest

**File:** `data/inventories/folder_walk_20260411_213418.json`
**Walk timestamp:** 2026-04-12T02:17:18Z — 02:34:18Z (1,019.9 seconds)
**Drives expected:** 12 | **Accessible:** 9 | **Not shared:** 0-shared-drive-content-outline, 4-finance, 5-hr-legal

| Slug | Folders | Files | Depth | Sensitive | Root fan-out |
|------|---------|-------|-------|-----------|-------------|
| 1-operations | 1,714 | 6,185 | 8 | no | 14 |
| 2-sales-relationships | 1,136 | 3,192 | 7 | no | 10 |
| 3-marketing | 377 | 3,178 | 8 | no | 14 |
| 6-ideas-planning-research | 60 | 571 | 4 | no | 10 |
| 7-supplements | 19 | 246 | 4 | no | 7 |
| 8-labs | 0 | 12 | 0 | **yes** | 0 |
| 9-biocanic | 2 | 8 | 1 | no | 2 |
| 10-external-content | 295 | 1,183 | 6 | no | 14 |
| 11-rh-transition | 346 | 1,018 | 5 | no | 11 |
| **Totals (walked)** | **3,949** | **15,593** | — | — | — |

Depth-0 subfolders across all 9 drives: **82**
Depth-1 subfolders: **265** (combined depth 0+1: **347**)

---

## ADR-004 open item resolutions

### 1. Folder-tree component: roll our own vs. library

**Decision: Roll our own.**

Justification:
- The admin console is vanilla HTML/CSS/JS with Jinja templates (Santorini
  script headers, copper/ivory/navy palette). No SPA framework, no npm
  build pipeline.
- Adding a tree library (jstree, fancy-tree, react-tree) would require
  either a build step or a CDN dependency for a component used on exactly
  one page.
- The tree has a known, bounded shape: 9 drives, 82 root-level folders,
  max depth 8. This is a modest tree, not a filesystem browser for
  millions of nodes.
- Custom code can handle the two special rendering cases (flat-file drives
  like 8-labs; sensitive-flag modals) without fighting library abstractions.
- Estimated complexity: ~200 lines of JS for expand/collapse, checkbox
  cascade, and lazy fetch. Well within "roll our own" territory.

Implementation: a `<ul>`-based tree with `data-folder-id`, `data-drive-id`,
and `data-depth` attributes. CSS handles indent via `padding-left: calc(depth * 1.25rem)`.
Expand/collapse toggles a `.collapsed` class. Checkboxes use tri-state
logic (unchecked / checked / indeterminate for partial subtree selection).

### 2. Lazy-loading depth: one level vs. two levels

**Decision: Two-level prefetch (depth 0 + depth 1 on drive expand).**

Justification:
- **One-level prefetch** on drive expand shows only root subfolders. For
  the three big drives (1-operations: 14 folders, 2-sales: 10, 3-marketing: 14),
  the user immediately needs to click again to see anything useful. One
  click per drive is too shallow.
- **Two-level prefetch** loads root subfolders AND their immediate children
  on drive expand. Cost: 9 + 82 = **91 API calls** total if the user
  expands every drive. In practice, users expand 2-3 drives per session,
  so cost is ~20-30 calls. Each call returns in <200ms. Acceptable.
- **Full prefetch** is ruled out: the full walk made ~3,949 folder-level
  API calls and took 17 minutes. Not viable for UI load.
- Two levels covers the "meaningful content" layer for most drives. For
  example, 1-operations' 14 root folders average 3.6 subfolders each —
  showing those 50 nodes on expand gives the user a real picture of the
  drive's structure without further clicks.
- Drives deeper than depth 2 (1-operations at 8, 3-marketing at 8) load
  deeper levels on demand, one level at a time.

Implementation: when the user expands a drive node, the backend endpoint
`/admin/api/drive/<drive_id>/tree?depth=2` returns a two-level JSON tree.
Subsequent expand clicks on depth-2+ folders call
`/admin/api/folder/<folder_id>/children` which returns one level.

### 3. In-tree search

**Decision: Yes, build it — scoped to the cached manifest, not live API.**

Justification:
- With 3,949 folders across 9 drives, "find the folder named FKSP" is a
  real user need. Scrolling through 1,714 operations subfolders is not
  practical.
- Searching the live Drive API would require walking the full tree on each
  query — 17 minutes. Not viable.
- Instead: the manifest JSON (`folder_walk_*.json`) is loaded server-side
  at admin startup. The search endpoint `/admin/api/folders/search?q=...`
  does a case-insensitive substring match on folder paths in the manifest.
  Returns matching folders with their drive slug and full path. The UI
  auto-expands the tree to the matched folder when the user clicks a
  search result.
- The manifest is refreshed by re-running `folder_walk.py` (admin can
  trigger via a "Refresh inventory" button that shells out to
  `railway run --service rf-nashat-clone python3 -m ingester.folder_walk`).
  Stale manifest data is acceptable between refreshes — the tree only
  needs to be accurate enough for selection, not real-time.

Implementation: a search input above the tree. Debounced at 300ms. Results
appear in a dropdown overlay. Clicking a result scrolls the tree and
highlights the folder. Max 20 results shown (with "N more..." if truncated).

### 4. Bulk operations

**Decision: Yes — multi-select with batch library assignment.**

Justification:
- A typical library maps to multiple sibling folders (e.g., all FKSP
  transcript subfolders under `1-operations/FKSP Transcript Repository` —
  8 subfolders). Assigning one at a time would be tedious.
- Checking a parent folder already selects all descendants (per ADR-004
  functional requirements). This IS the bulk operation for the common case.
- Additionally: the library-assignment dialog appears once per Save, not
  per checkbox click. The user checks N folders, then clicks Save, then
  sees one assignment prompt for all newly-checked folders that have no
  library assignment yet.
- No need for a separate "bulk assign" mode. The natural checkbox +
  recursive-select + single-save workflow IS the bulk operation.

Implementation: the Save POST payload includes all folder IDs with their
current checked/unchecked state and library assignment. The backend diffs
against the registry's previous state.

### 5. Library deletion and retire status

**Decision: Retire only. No hard delete from the UI.**

Justification:
- Libraries map to registry entries and potentially to ChromaDB collections
  with chunks. Hard deletion from the UI risks orphaning chunks or breaking
  references.
- The UI offers a "Retire" action on any library. Retiring sets
  `status: "retired"` in the registry. Retired libraries:
  - Stop appearing in the library-assignment dropdown for new folders
  - Still appear in the inventory view with a "Retired" badge
  - Their chunks remain in ChromaDB (searchable) until a future purge
    operation is explicitly run
- If a library has zero files AND zero chunks, the UI shows "Retire"
  alongside a note: "This library is empty." The admin still clicks
  Retire, not Delete — same flow, no special case.
- Hard deletion (purging chunks from ChromaDB and removing the registry
  entry) is a CLI-only admin operation, not exposed in the UI. This
  prevents accidental data loss from a misclick.

### 6. Visual treatment of flagged drives

**Decision: Icon next to drive name + confirmation modal. No banner.**

Justification:
- Three drives are flagged sensitive: 4-finance, 5-hr-legal, 8-labs. Of
  these, only 8-labs is currently accessible (the other two are not shared).
  So in practice, the user sees ONE flagged drive in the tree today.
- A banner across the top of the tree would be disproportionate for one
  drive out of nine. An icon (shield or lock glyph) next to the drive name
  is sufficient and scales correctly if more drives are flagged later.
- The confirmation modal fires when any folder inside a flagged drive is
  checked (per ADR-004 requirements). For 8-labs specifically: since it is
  a flat drive (0 folders, 12 files at root), the modal fires when the
  drive-level checkbox itself is checked — there are no subfolders to
  check individually.
- Icon: `<span class="sensitive-flag" title="Flagged: sensitive content">&#x1F512;</span>`
  styled in the copper accent color from the brand palette.

### 7. Audit log schema

**Decision: Yes — separate `audit_events` collection in the registry.**

Schema:

```json
{
  "event_id": "uuid-v4",
  "timestamp": "2026-04-12T10:30:00Z",
  "user": "admin@reimaginedfertility.com",
  "action": "folder_selected | folder_deselected | library_created | library_retired | sensitive_confirmed | inventory_refreshed | save_triggered",
  "target_type": "folder | library | drive",
  "target_id": "google-drive-folder-id or library-slug",
  "target_path": "/1-operations/FKSP Transcript Repository",
  "drive_slug": "1-operations",
  "library_slug": "fksp_curriculum",
  "metadata": {},
  "session_id": "browser-session-id"
}
```

Justification:
- ADR-004 called this out as "probably yes for clinic-pitch reasons." With
  the sensitive-flag confirmation modal in place, an audit trail of who
  confirmed access to flagged drives is essential for compliance.
- The audit log records every UI action that modifies selection state,
  library configuration, or triggers ingestion. Read-only actions (tree
  expansion, search) are NOT logged.
- Storage: a JSON-lines file at `{DATA_ROOT}/audit/ui_events.jsonl`,
  appended on each action. Not in ChromaDB (these are not RAG chunks).
  A future migration to a proper database is straightforward since the
  schema is flat.
- The admin console gets a read-only "Audit log" view showing recent
  events in reverse chronological order with filtering by action type
  and drive.

---

## Non-negotiable design decisions

### Christina Massinople Park content: ingest, do NOT exclude

Dr. Christina Massinople Park is no longer with the business. The hard
guardrail — that her name must NEVER appear in any agent response — remains
in effect and is enforced at retrieval/generation time via the system
prompt.

**However, her coaching content and call recordings ARE company intellectual
property and MUST be ingested.** The manifest confirms:

- `11-rh-transition/Dr. Christina's Zoom Call Recordings`: 23 subfolders,
  0 root files (recordings are inside date-stamped subfolders)
- `11-rh-transition/Christina M Park`: 1 file

These folders are ingested as normal content. The voice/attribution problem
is solved at retrieval/generation time:

1. **Speaker tagging on chunks:** During ingestion (Phase E), transcript
   chunks are tagged with `speaker: "Christina"` metadata. The retrieval
   layer can surface the knowledge while the generation layer attributes
   it to the RF model, not to Christina personally.
2. **System prompt enforcement:** Nashat's voice embodies the RF model.
   The system prompt instructs the agent to use Nashat's delivery style
   regardless of which coach's recording sourced the knowledge.

**There is only ONE Chris/Christina person referenced in the data — not
two.** Christina Massinople Park and any "Chris" or "Christina" references
across the drives are the same person.

**EXPLICIT INSTRUCTION TO FUTURE CLAUDE SESSIONS:** Do NOT add
`EXCLUDED_FOLDER_PATTERNS` or any exclusion rule for Christina's folders.
Do NOT "helpfully" filter her content at ingestion time. The exclusion
happens at generation time, not ingestion time. If you are reading this
spec and considering adding a Christina exclusion, stop — re-read this
section.

### 8-labs: flat drive, first-class rendering

The manifest confirms: **8-labs has 0 folders, 12 files at root, depth 0.**

This is not an edge case or error state. The tree component must handle
"drive with no subfolders, just a flat file list" as a first-class case:

- Expanding 8-labs shows the 12 files directly as leaf nodes under the
  drive heading. No "empty folder" message, no intermediate folder layer.
- The drive-level checkbox selects/deselects all 12 files at once.
- The sensitive flag and confirmation modal still apply (8-labs is in
  `SENSITIVE_DRIVE_SLUGS`). Checking the 8-labs drive triggers the modal.
- The tree renderer detects `total_folders == 0 && total_files > 0` and
  switches to flat-file rendering mode for that drive.

### 10-external-content personal-name Zoom folders

The manifest shows these personal-name folders under 10-external-content:

- Erika Thiede's zoom (2 subfolders)
- Jen Lawton's zoom (2 subfolders)
- Kim McPhail's zoom (2 subfolders)
- Melissa Sable's Zoom (5 subfolders)
- Nicole Anderson's Zoom (2 subfolders)
- Shana Tatum's Personal Meeting Room (0 subfolders, 13 files)

These are RF coaching files facing clients. **No special UI treatment.**
Render as standard folders in the tree. No flags, no modals, no name
redaction.

Per-folder dedup against existing coaching transcripts is a **Phase E
diff-engine concern**, not a UI concern. The UI's job is to let the admin
check or uncheck them. Whether their content duplicates recordings already
ingested from other drives is resolved by the diff engine's content hash
comparison.

### Lazy loading is mandatory

The full walk took **1,019.9 seconds** (17 minutes), dominated by
1-operations (1,714 folders, depth 8). Pre-fetching the full tree on UI
load is not viable.

The two-level prefetch strategy (resolution #2 above) limits initial load
to 91 API calls in the worst case (all drives expanded), with deeper
levels loaded on demand. See resolution #2 for the full justification.

---

## Hard guardrails for implementation

- Do NOT re-litigate ADRs 001-004 — they are decided
- Do NOT touch any credential or secret
- Do NOT run ingestion or modify the ingestion pipeline
- Do NOT write pipeline code (chunking, embedding, ChromaDB writes)
- Do NOT modify existing Flask admin console routes — new additive routes
  only (the existing routes serve the current admin UI; do not break them)
- Never run `railway variables` bare — use:
  `railway run --service rf-nashat-clone python3 -c "import os; ..."`
  (see INCIDENTS.md for the near-miss that prompted this rule)
- `SHARED_DRIVE_IDS` and `SENSITIVE_DRIVE_SLUGS` are already populated in
  `ingester/config.py` — do not re-specify or overwrite them

---

## Technical architecture

### New Flask routes (all behind existing bcrypt auth)

| Route | Method | Purpose |
|-------|--------|---------|
| `/admin/folders` | GET | Render the folder-selection page (Jinja template) |
| `/admin/api/drive/<drive_id>/tree` | GET | Return two-level folder tree JSON for a drive |
| `/admin/api/folder/<folder_id>/children` | GET | Return one-level children for lazy deeper loading |
| `/admin/api/folders/search` | GET | Search manifest folder paths, return matches |
| `/admin/api/folders/save` | POST | Save selection state, trigger diff engine |
| `/admin/api/folders/refresh-inventory` | POST | Re-run folder_walk.py, reload manifest |
| `/admin/libraries` | GET | Render the library inventory view |
| `/admin/libraries/<slug>/retire` | POST | Retire a library |
| `/admin/audit` | GET | Render the audit log view |
| `/admin/api/audit/events` | GET | Return audit events JSON (paginated, filterable) |

### Frontend files (new, additive)

| File | Purpose |
|------|---------|
| `templates/admin/folders.html` | Folder-selection page template |
| `templates/admin/libraries.html` | Library inventory view template |
| `templates/admin/audit.html` | Audit log view template |
| `static/js/folder-tree.js` | Tree component: expand/collapse, checkboxes, lazy load |
| `static/js/folder-search.js` | Search input with debounced query + result overlay |
| `static/css/folder-tree.css` | Tree styling (indent, icons, sensitive flag, states) |

### Manifest loading

At admin startup, load the most recent `folder_walk_*.json` from
`data/inventories/` into memory. This provides:
- The drive list and metadata for the tree root nodes
- Folder names and paths for search (no live API call needed)
- File counts and depth data for display

The manifest is reloaded when the admin clicks "Refresh inventory" (which
re-runs the walk script and then reloads the JSON).

### Drive API calls (lazy loading only)

The tree component does NOT read from the cached manifest for live tree
expansion. It calls the Drive API via `DriveClient` for accurate,
up-to-date folder listings. The manifest is used only for search and for
the initial tree structure on page load (drive-level metadata).

This means:
- Tree expansion is always current (new folders appear immediately)
- Search results may be slightly stale (until manifest is refreshed)
- The tradeoff is acceptable: search helps navigate, not discover

---

## Success criteria

1. The folder-selection page renders at `/admin/folders` behind bcrypt auth
2. All 9 accessible drives appear as expandable root nodes
3. Not-shared drives (0, 4-finance, 5-hr-legal) appear grayed out with
   "Not shared" label
4. Expanding a drive shows two levels of subfolders with file counts
5. 8-labs expands to show 12 files directly (flat rendering, no subfolders)
6. Checking a folder in 8-labs triggers the sensitive-drive confirmation
   modal
7. Search finds folders by name across all drives
8. Checking a parent folder cascades to all visible descendants
9. Save persists selection state and library assignments to the registry
10. The audit log records selection changes and sensitive confirmations
11. The library inventory view shows all libraries with file/chunk counts

---

## Claude Code kickoff prompt

> Read these files in order:
> 1. `PHASE_D_POST_SPEC.md` (this file — the full spec)
> 2. `ADR_004_folder_selection_ui.md` (the ADR this spec resolves)
> 3. `ingester/config.py` (for `SHARED_DRIVE_IDS`, `SENSITIVE_DRIVE_SLUGS`)
> 4. `ingester/folder_walk.py` (for `discover_shared_drives`, manifest schema)
> 5. `ingester/drive_client.py` (the `DriveClient` class you will call)
> 6. `admin/` directory structure (existing Flask admin routes — do not
>    modify, only add new routes)
>
> Implement the folder-selection UI per the spec. Work in this order:
>
> 1. **Backend routes first.** Add the new Flask routes listed in the
>    spec's Technical Architecture section. Start with the manifest-loading
>    logic and the `/admin/api/drive/<drive_id>/tree` endpoint. Test it
>    returns valid JSON by hitting it with curl.
>
> 2. **Tree component.** Build `folder-tree.js` with expand/collapse,
>    two-level prefetch, checkbox cascade (tri-state), and lazy deeper
>    loading. The tree must handle 8-labs' flat-file case as a first-class
>    rendering mode, not an error path. Test by loading `/admin/folders`
>    in a browser.
>
> 3. **Sensitive flag.** Add the lock icon next to 8-labs (and any other
>    `SENSITIVE_DRIVE_SLUGS` drive). Wire up the confirmation modal on
>    checkbox check. Log the confirmation to the audit log.
>
> 4. **Search.** Build the search input that queries the cached manifest.
>    Debounced, max 20 results, click-to-expand-and-highlight.
>
> 5. **Save flow.** Wire the Save button to POST selection state. For
>    Phase D-post, the backend writes selection state to a JSON file at
>    `{DATA_ROOT}/selection_state.json` (the registry integration is
>    Phase E). Show a confirmation message on success.
>
> 6. **Library inventory and audit views.** These are lower priority.
>    Build them if time permits; they can also be Phase E work.
>
> **Brand styling:** Santorini script for page headers, Cormorant Garamond
> for serif text, Inter for sans-serif, copper/ivory/navy palette. Match
> the existing admin console look and feel.
>
> **CRITICAL — Christina content rules:** Do NOT add any exclusion
> patterns for Christina Massinople Park's folders. Her content is
> ingested. Read the "Christina Massinople Park content" section of the
> spec for the full rationale.
>
> **CRITICAL — Flat drive rendering:** 8-labs has 0 folders and 12 files.
> The tree must render this as a single expansion showing files directly.
> Do not treat it as an empty or error state.
>
> **Do NOT:** modify existing Flask routes, run ingestion, touch
> credentials, overwrite `SHARED_DRIVE_IDS` or `SENSITIVE_DRIVE_SLUGS`
> in config.py, or run `railway variables` bare.
>
> When the tree renders correctly with all 9 drives and the search works,
> show me a screenshot or describe the UI state, then commit.

---

## Relationship to other phases and ADRs

- **ADR-001:** The twelve drives and their sensitive flags are the tree's
  root data. Three drives not yet shared appear as disabled nodes.
- **ADR-002:** The registry schema (library entries, selection state) is
  consumed by this UI but not modified by this spec. Registry writes are
  Phase E. For now, selection state is persisted to a flat JSON file.
- **ADR-003:** Canva dedup is independent. The Canva library appears as
  one library in the inventory view like any other.
- **ADR-004:** This spec resolves all seven open items from ADR-004.
- **Phase D-prime:** The manifest produced by `folder_walk.py` is the
  authoritative data source for the tree component's structure, search
  index, and the statistics cited throughout this spec.
- **Phase E:** Integrates the selection UI with the diff engine and
  registry. The Save button triggers real ingestion. Library CRUD writes
  to the registry. Dedup runs against existing chunks.

---

*Spec written 2026-04-11 for Phase D-post Claude Code handoff.
Phase D-prime manifest verified; all ADR-004 open items resolved against
real data.*
