# ADR 004 — Folder-selection UI for RAG content management

**Date:** 2026-04-11
**Status:** DECIDED (in principle) — detailed design deferred until
after first inventory walk
**Deciders:** Daniel Smith (founder, RF / RH)
**Context:** Phase A design pass for the RF RAG build. Emerged as
the answer to ADR-002 Q7 (registry-as-content-management UX) and
became substantially more important than originally framed —
inverting how the ingestion pipeline is driven.

---

## Decision

A web-based folder-selection UI is built into the existing Flask
admin console at , behind the existing
bcrypt auth. The UI displays the in-scope Google Drive Shared Drives
as a navigable folder tree with checkboxes. The user expands folders,
checks the ones they want included in the RAG, assigns each checked
folder set to a library (existing or new), and clicks Save. The diff
engine respects the saved selection state on the next ingestion run.

The UI is the **primary mechanism** by which the RAG's content scope
is controlled. It replaces the original master plan's "edit hardcoded
folder IDs in " approach for everything except a fallback
admin path.

---

## Why this is bigger than the original framing

The original ADR-002 Q7 was "should the registry have a read-only
admin UI page so the team can browse it?" The answer Daniel proposed
inverted that: instead of a passive registry viewer, build an active
content-selection tool.

The implications are significant:

**1. Folder selection IS the library definition.** Libraries are no
longer defined by hardcoded filter rules in the registry. They are
defined by the act of checking folders and assigning them a library
name in the UI. The library name lives in the registry; the
*membership* of the library is determined by which folders the user
has checked.

**2. The UI is how non-engineers control the RAG.** Today, modifying
which content goes into the clone means editing YAML, editing Python,
or asking Daniel. With the UI, Nashat (or any authorized admin) can
say "include this new folder" or "stop indexing this old workshop
series" and the system responds. **This is the difference between
"Daniel's RAG" and "Reimagined Fertility's RAG."** It is a real
product surface, not a developer tool.

**3. The Save button is the diff trigger.** Per ADR-002 Q6, the
selection UI's Save button is the primary trigger for the diff
engine. Cron and webhook triggers are explicitly off the table —
they are not needed because the UI provides direct, on-demand control
over when ingestion happens.

**4. It changes the build sequencing.** The folder-selection UI is
no longer optional. It is on the critical path for shipping the
diff-engine-driven build. See "Sequencing" below.

---

## Functional requirements

### Core view: the folder tree

- Tree rooted at the list of in-scope Shared Drives (per ADR-001:
  the twelve RF Workspace Shared Drives, with sensitive ones flagged)
- Each drive expands to show its top-level folders
- Each folder expands to show its subfolders, lazy-loaded via the
  Drive API to avoid up-front cost
- Each folder has a checkbox indicating whether it is currently
  selected
- Each folder shows: folder name, file count (if known from a
  previous walk), last-modified date, and any library assignment
  (e.g., "→ fksp_curriculum")
- Selecting a folder by default selects all its descendants
  (recursive); the user can override per-subfolder if needed

### Library assignment

When the user checks a folder (or set of folders), the UI prompts:

> Assign these folders to a library:
> ( ) Use existing library: [dropdown of existing libraries]
> ( ) Create new library: [text input + tier dropdown + privacy_class dropdown]

A folder can only belong to one library at a time. Re-assigning a
folder to a different library moves it (the diff engine handles the
transition: chunks are re-tagged and the registry is updated).

### Sensitive-drive flag-and-confirm

Drives marked  in the registry (initially , ,  per ADR-001) display with a
visible warning indicator in the tree. Checking any folder inside a
flagged drive triggers a confirmation modal:

> ⚠ **This folder is in a flagged drive.**
> Drive  is flagged as containing sensitive content
> ({reason}). Are you sure you want to ingest content from this
> folder?
>
> [Cancel] [Yes, ingest from {folder_name}]

Cancel leaves the folder unchecked. Confirming proceeds with the
selection. The UI logs the confirmation event in the registry for
audit purposes.

The flag itself can be edited from the UI (admins can flag or
unflag a drive as understanding evolves).

### Save behavior

When the user clicks Save:

1. The new selection state is POSTed to a Flask endpoint on the
   admin service
2. The admin service writes the new state to the registry
   ( per file/folder, library assignments)
3. The admin service queues a diff run on the Railway worker
4. The UI displays a "diff in progress" status, polling for
   completion
5. When the diff completes, the UI shows a summary: "X new files
   queued for ingestion, Y modified files queued for re-ingest, Z
   files moved to pending review"
6. The user can click through to a detail view of any of the
   summary categories

### Pending review queue

Per ADR-002 Q4, files that have been removed from Drive (or whose
parent folder has been unselected) are marked 
rather than deleted. The UI exposes a queue view where the admin
can see all pending-review files and decide per file whether to:

- **Confirm deletion** — purges the file's chunks from ChromaDB
  and removes the registry entry
- **Restore** — re-checks the file's parent folder so the next diff
  brings it back

### Inventory view

Beyond the folder-selection tree, the UI provides a flat "inventory"
view of every library, showing:

- Library name, tier, privacy class, status, description
- File count, total chunk count
- Most recent file's modification date (the freshness indicator)
- A "view files" link that drills into the file list for that
  library

This is the "content management tool for the human team" Daniel
asked about — the team can answer "do we have anything on gut
health" by browsing the inventory or searching by topic.

---

## Sequencing — Path B (build the UI after first inventory walk)

A real choice was made about whether to build the UI before or after
the first ingestion run.

**Path A (rejected):** Build the UI first, then drive the first
ingestion through the UI. Cleaner final state but means designing
the UI against guessed folder-tree shape.

**Path B (chosen):** Run a one-time folder-walk inventory pass
*before* building the UI, so the UI is designed against real folder-
tree data from the actual RF Shared Drives. The first ingestion may
be triggered manually via the CLI (matching the original master
plan), then the UI is built and the second ingestion onwards goes
through the UI.

**Why Path B:**

- The UI design (what fields to show, how deep folders nest, what
  the library-assignment prompt looks like) depends entirely on
  what the tree actually looks like. Designing in the abstract
  produces a generic-feeling tool; designing against real data
  produces something that fits.
- The first ingestion is a small, controlled operation (FKSP pilot:
  one short video, one PDF). Driving it from the CLI is fine for
  one round.
- Building the UI against an empty registry means the design has no
  real content to test with. Building it after FKSP is partially
  ingested means the UI can be tested against real registry rows
  from day one.

**Sequencing in detail:**

1. **Phase B-lite** —  shares the twelve in-scope Shared
   Drives with the service account (per ADR-001 rescope)
2. **Phase C** — Service account created, Drive API + Vertex AI
   APIs enabled on 
3. **Phase D-prime** — Run a folder-walk inventory pass: walk all
   in-scope drives, dump the tree structure to JSON, surface the
   shape to Daniel for review
4. **Phase D** — First FKSP pilot ingestion driven by CLI against
   hardcoded folder IDs (one short video + one PDF, per the
   master plan)
5. **Phase D-post** — Build the folder-selection UI against the
   real folder-tree data and the now-populated registry
6. **Phase E** — All subsequent ingestion is driven through the UI

---

## Build estimate

A polished version of the UI is roughly **2–3 build days** broken
down as:

| Component | Estimate |
|-----------|----------|
| Flask routes + Jinja templates + brand-styled CSS | 0.5 day |
| Folder-tree component with lazy loading via Drive API | 1 day |
| Library assignment sub-flow | 0.5 day |
| Save button → diff engine integration with progress polling | 0.5 day |
| Pending review queue view | 0.5 day |
| Inventory view | 0.5 day |
| Flag-and-confirm modal | 0.25 day |

A rough functional version (no inventory view, no pending review
queue, just the tree + library assignment + save) is roughly **1
build day**. The other features can be added incrementally as the
RAG grows and the need for them surfaces.

---

## Technical sketch

### Backend (Flask routes on the existing admin service)



All routes are behind the existing bcrypt auth.

### Frontend

Vanilla HTML/CSS/JS with the same brand styling as the rest of the
admin console (Santorini script for headers, copper/ivory/navy
palette, Cormorant Garamond for serif, Inter for sans). No SPA
framework — Flask + Jinja templates with progressive enhancement
via small JS modules. The folder-tree component is the only
non-trivial frontend code.

### Drive API access

The folder-tree lazy-load endpoints call the Drive v3 API via
 (already scaffolded in ),
authenticating with the service account credential from
. Lazy loading means we never walk the
entire tree up front — only what the user expands.

### Diff engine integration

The Save button POSTs the new selection state to
, which:

1. Writes the new selection to the registry (transaction: all
   selection changes succeed or none do)
2. Queues a diff run by writing a job marker file at
    and triggering the Railway
   ingester worker via Railway CLI from within the admin service
3. Returns immediately with a job ID; the UI polls
    for status

The Railway ingester worker, when invoked, picks up the job marker,
runs the diff, and writes status updates back to the registry as
it goes.

---

## Open items

The detailed design pass for ADR-004 will be done after Phase D
(first inventory walk) and is responsible for resolving:

1. **Folder-tree component:** roll our own or use a library?
2. **Lazy-loading depth:** load one level at a time or pre-fetch
   two levels for snappier UX?
3. **Search within the tree:** is "find folder named X" useful
   enough to build, or do we punt?
4. **Bulk operations:** can the user select multiple folders and
   assign them to a library in one operation, or is it one folder
   at a time?
5. **Library deletion:** if a library has no files in it, can the
   user delete it from the UI? What if a library has files — does
   the UI offer to "retire" (status change) vs. delete?
6. **Visual treatment of flagged drives:** banner across the top
   of the tree, icon next to the drive name, both?
7. **Audit log:** does the registry need a separate audit-events
   collection that records every UI action with timestamp and user
   ID? Probably yes for clinic-pitch reasons; defer the schema.

---

## Status of related decisions

- ADR-001 (drive ingestion scope): rescoped to depend on this UI
- ADR-002 (registry, diff engine): the registry schema includes
  the fields this UI needs; the diff engine is triggered by this
  UI's Save button
- ADR-003 (Canva dedup): independent of this UI; the Canva library
  is one library among many in the inventory view

---

*ADR written 2026-04-11 at the close of the Phase A design pass.
Decided in principle; detailed design deferred to a focused session
after Phase D inventory completion.*
