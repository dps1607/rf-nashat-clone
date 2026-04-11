# ADR 002 — Library registry, continuous diff ingestion, and library-aware agents

**Date proposed:** 2026-04-11
**Date decided:** 2026-04-11
**Status:** DECIDED
**Deciders:** Daniel Smith (founder, RF / RH)
**Context:** Phase A design pass during the RF internal education RAG build,
following the GCP foundation work.

---

## Summary

The Reimagined Fertility RAG ingester is being built as a continuously-updated
content management system, not a one-shot bulk loader. Three connected
components define the system:

1. A **library registry** (`rf_library_index` ChromaDB collection) that tracks
   every file the system knows about, what library it belongs to, what tier
   it sits in, and what its ingestion status is. The registry is the single
   source of truth for "what content does the RAG have."

2. A **diff engine** that walks the in-scope Google Drive sources, compares
   what it finds against the registry, and produces work lists (new, modified,
   deleted, unchanged) for the ingestion pipelines.

3. **Library-aware agents** that know which libraries they have access to,
   how fresh each one is, and what coverage they offer — and can incorporate
   that self-knowledge into responses to clients.

This ADR locks the architecture for all three components.

---

## The library concept

A **library** is a first-class named entity in the registry, defined as a
tuple of:

```
(collection, filter, tier, privacy_class, status, description)
```

- `collection` — the ChromaDB collection where the library's chunks live
  (e.g., `rf_internal_education`)
- `filter` — a metadata predicate that selects this library's chunks within
  the collection (e.g., `{program: fksp, asset_type: coaching_call}`)
- `tier` — one of four access tiers; see below
- `privacy_class` — `public | paywalled | internal_reference | clinical_phi |
  semi_private`
- `status` — `active | maintenance | archived | planned`
- `description` — a one-line human-readable description of what the library is

Libraries are **flat** — there is no two-level hierarchy. A library is owned
by exactly one tier. Sub-slicing within a library happens at retrieval time
via additional metadata filters, not by introducing sub-libraries.

### The rule for creating a new library

A new library is created when content has its own ingestion source AND its
own conceptual identity to a human asking "what kind of thing is this." Same
source + more content of the same kind = same library, just more chunks.

### The four access tiers

The tier model matches the architecture already implicit in the existing
agent YAML's `coaching_n` / `reference_n` / `published_n` retrieval knobs,
plus a reserved slot for clinical content.

| Tier | Purpose | Who can see it |
|------|---------|----------------|
| **Reference** | Internal source material the team draws from to create content | Internal coaching agent + admin tooling |
| **Paywalled** | Behind-paywall content for paying clients | Internal coaching agent only |
| **Published** | Public-facing distribution | Public sales agent + internal coaching agent |
| **Clinical** | PHI and clinical data | Reserved — no libraries today; populated when first PHI dataset arrives, with separate scoped credentials per ADR-001 |

The privacy boundary the public sales agent must respect (no paywalled
content, no client-identifying data) is enforced at the **tier** level, not
the library level. Adding a new library to an existing tier inherits the
existing access rules. Adding a new tier requires an explicit YAML edit.

### Starter library list (15 libraries)

| # | Tier | Library name | Notes |
|---|------|--------------|-------|
| 1 | Reference | `a4m_course` | Existing — already in `rf_reference_library` collection (584 chunks) |
| 2 | Reference | `external_research` | Placeholder for "other materials we use to create internal content" |
| 3 | Reference | `canva_design_library` | Canonical visual asset source. Deduped. See ADR-003. |
| 4 | Paywalled | `historical_coaching_transcripts` | Existing — 9,224 chunks in `rf_coaching_transcripts`. Backfilled into the registry. |
| 5 | Paywalled | `fksp_curriculum` | New |
| 6 | Paywalled | `fksp_coaching_calls` | New. Program-scoped. |
| 7 | Paywalled | `fertility_formula_curriculum` | New |
| 8 | Paywalled | `fertility_formula_coaching_calls` | New. Program-scoped. |
| 9 | Paywalled | `preconception_detox_curriculum` | New |
| 10 | Paywalled | `preconception_detox_coaching_calls` | New. Program-scoped. |
| 11 | Published | `blog_posts` | New |
| 12 | Published | `lead_magnets` | New |
| 13 | Published | `masterclass_recordings` | New |
| 14 | Published | `ig_content` | New. Drafts excluded — only published IG content. |
| 15 | Published | `nashat_dms` | New. `privacy_class: semi_private`. Retention/redaction sub-design deferred. |

The Clinical tier is intentionally empty.

---

## Q&A — the seven design questions and their resolutions

The seven open questions in the original PROPOSED stub were resolved as
follows during the 2026-04-11 design pass.

### Q1 — Library taxonomy

**Decision:** Flat list of named libraries grouped by tier, as documented
above. Libraries are first-class with the schema `(collection + filter +
tier + privacy_class + status + description)`.

### Q2 — Where does the registry physically live?

**Decision:** ChromaDB collection named `rf_library_index`. One storage
system across the whole project. Records are stored as documents with
metadata fields covering all registry attributes; the embedding can be a
filename-plus-description embedding for free semantic search over the
content inventory.

**Rationale:** Adding a second storage system (SQLite, etc.) was considered
and rejected. ChromaDB is sufficient at current scale, the existing backup
workflow already covers it, and the relational shape we worried about (Canva
cross-references) can be expressed as pipe-delimited metadata fields without
unacceptable awkwardness. If the registry ever outgrows what Chroma handles
comfortably, we revisit then.

### Q3 — Backfill the existing 9,224 transcript chunks?

**Decision:** Yes, backfill. The existing `rf_coaching_transcripts` collection
gets a one-time pass that creates registry entries for each historical file,
all assigned to the `historical_coaching_transcripts` library. Without
backfill, the registry has a blind spot for the largest existing collection
and the agent cannot honestly self-describe its coverage.

### Q4 — Deletion handling

**Decision:** Soft delete with human review queue. When the diff engine sees
that a file has disappeared from Drive, it marks the registry entry as
`pending_review` (not `deleted`). Chunks remain in ChromaDB. The file appears
in a review queue in the admin UI, where the human operator decides per file
whether to (a) confirm the deletion and purge the chunks, or (b) restore
the file.

This is a two-step process by design: it makes accidental deletions
recoverable and intentional removals deliberate. It preserves the audit
trail clinic auditors will eventually want to see.

### Q5 — Versioning of modified files

**Decision:** Replace by default. When a file's content hash changes, the
old chunks are deleted from ChromaDB and new chunks are written. The
registry reflects current state, not history.

**Exception:** the `nashat_dms` library uses append-only behavior because
DMs are conversations and "modification" doesn't really apply (you don't
edit a sent DM, you send a new one). The append-only rule for DMs will be
formalized when the DM ingestion sub-design is undertaken.

### Q6 — Diff trigger mechanism

**Decision:** The **Save button in the folder-selection UI** (see ADR-004)
is the primary trigger. When the user saves a new selection in the UI, the
diff engine runs against the new selection set, computes work lists, and
queues the actual ingestion as a background job on the Railway worker
service.

The **Railway CLI manual trigger** remains available as a fallback for admin
operations. Cron-based polling and Drive API webhook push notifications are
explicitly **off the table** for this build. The selection UI gives the user
direct, on-demand control over when ingestion happens; that removes the need
for either polling or webhooks.

### Q7 — Registry-as-content-management UX

**Decision:** Build a folder-selection UI in the admin console (see ADR-004
for the full design). The UI shows the in-scope Google Drive Shared Drives
as a navigable tree with checkboxes. The user expands folders, checks the
ones they want included in the RAG, assigns each checked folder set to a
library, and hits Save. The diff engine respects the selection on the next
ingestion run.

This is a substantially bigger and better answer than the original
"read-only browse the registry" page. It inverts the build: instead of
folder ingestion being controlled by hardcoded folder IDs in `config.py`,
it's controlled at runtime by a non-engineer-friendly UI. The selection UI
becomes the front door to the RAG.

---

## The registry schema

The `rf_library_index` ChromaDB collection stores two kinds of records,
distinguished by the `record_type` metadata field:

### Library records (`record_type: "library"`)

One record per library. ID format: `library:{library_name}`.

```
record_type:        "library"
library_name:       string         # e.g., "fksp_curriculum"
tier:               string         # reference | paywalled | published | clinical
privacy_class:      string         # public | paywalled | internal_reference | clinical_phi | semi_private
status:             string         # active | maintenance | archived | planned
collection:         string         # target ChromaDB collection name
filter_json:        string         # JSON-encoded metadata filter
description:        string         # one-line human-readable
created_at:         ISO timestamp
updated_at:         ISO timestamp
```

### File records (`record_type: "file"`)

One record per file the registry knows about. ID format: `file:{drive_file_id}`.

```
record_type:           "file"
drive_file_id:         string                    # primary key
drive_path:            string                    # human-readable path
name:                  string                    # filename
mime_type:             string
size_bytes:            int
modified_time:         ISO timestamp             # from Drive metadata
content_hash:          string                    # md5/sha256; used for diff
library_name:          string                    # FK → library record
source_drive:          string                    # which Shared Drive
source_folder_id:      string                    # immediate parent folder
selected:              bool                      # checked in the UI?
ingestion_status:      string                    # unprocessed | processing | done | failed | pending_review | skipped
chunk_count:           int                       # how many chunks produced
last_ingested_at:      ISO timestamp | null
last_diff_seen_at:     ISO timestamp             # last seen by diff engine
target_collection:     string                    # which content collection
topics:                string                    # pipe-delimited tags
distribution:          string                    # pipe-delimited; for Canva: channel-libraries that reference this entry
flagged_sensitive:     bool                      # UI requires confirmation
error:                 string                    # last error if status=failed
```

The `embedding` for each record is the embedding of `{name} {description}
{topics}` — small but useful for "do we have anything about gut health"
inventory queries.

### Why two record types in one collection

Putting libraries and files in the same collection lets us query both
through the same Chroma client, keeps the backup story simple, and avoids
the overhead of a second collection for what is fundamentally a tiny amount
of data (15 libraries vs. thousands of files).

---

## The diff engine

### Inputs

- The current selection set from the folder-selection UI
- The current registry state (files we know about + their hashes/status)
- A live walk of the in-scope Drive folders via the service account

### Outputs (work lists)

- `new_files` — present in the live walk, not in the registry → ingest
- `modified_files` — present in both, but `content_hash` differs → re-ingest
- `deleted_files` — present in registry, not in live walk → mark `pending_review`
- `unchanged_files` — present in both, no changes → skip
- `unselected_files` — file still in Drive but parent folder no longer
  checked in the UI → mark `pending_review`

### Run lifecycle

1. User clicks Save in the folder-selection UI
2. UI POSTs the new selection state to a Flask endpoint on the admin service
3. Admin service updates the registry's `selected` flags and queues a diff
   run on the Railway ingester worker
4. Worker runs the diff: walks the in-scope folders, computes work lists,
   writes a manifest at `/data/manifests/diff_{timestamp}.json`
5. Worker processes the manifest: ingests new and modified files, marks
   deleted/unselected files as `pending_review`, updates the registry as it
   goes
6. Worker writes a final summary back to the registry; admin UI shows results

### Resumability

The manifest is the recovery point. If the worker crashes mid-run, the
next invocation reads the manifest, skips files marked `done`, retries
files marked `in_progress`, and continues with `pending` files.

---

## Library-aware agents

### What library-awareness gives the agent

At query time, the agent reads the registry to compute live statistics for
each library it has access to and incorporates them into responses where
relevant. New capabilities this enables:

- "I have 47 weekly coaching calls indexed in the FKSP coaching calls
  library, the most recent from April 8, 2026."
- "My FKSP curriculum content is comprehensive, but my coverage of
  pre-2026 calls is sparse — let me know if you need older context."
- (Sales agent) "I have 23 published blog posts and 87 published IG
  posts available — what topic are you exploring?"

### How it's wired in

The agent YAMLs gain a new optional `libraries` block on each mode. The
existing modes are NOT refactored — they continue to work as today.
**New modes** added going forward can reference libraries by name
instead of (collection, top_k) tuples directly.

Example new mode (illustrative; not yet committed):

```yaml
modes:
  fksp_full_curriculum:
    label: "FKSP Full Curriculum"
    description: "All FKSP teaching content — curriculum + coaching calls"
    libraries:
      - fksp_curriculum
      - fksp_coaching_calls
    top_k_per_library: 5
    self_describe: true        # render registry stats into prompt overlay
```

When `self_describe: true`, the agent's system prompt is augmented at
runtime with a small block like:

```
LIBRARY CONTEXT FOR THIS CONVERSATION:
- fksp_curriculum: 1,247 chunks across 24 lessons, last updated April 8, 2026
- fksp_coaching_calls: 312 chunks across 47 calls, most recent April 8, 2026
```

This gives the agent honest, current self-knowledge without baking
freshness data into the YAML.

### Why we are NOT refactoring existing modes

The existing modes (`internal_full`, `coaching_only`, `reference_only`,
`a4m_course_analysis`, `public_default`) work today and are tested in
production. Rewriting them to reference libraries by name before the
registry is populated and the pattern is proven would mean touching
working code to support a feature that does not yet exist. The pattern
proves itself on new modes against real data first; existing modes get
refactored only if and when there is a specific reason to.

---

## Implications for previously-locked decisions

### What this changes

- **Bulk vs. continuous (was Model A bulk-only):** becomes "bulk for
  first-time setup of each library, diff-incremental for ongoing updates."
  The two modes coexist; a first-time library load is just "everything is
  in the new_files list because the registry has nothing for this library
  yet."
- **Service account credential lifetime:** the "rotate after each
  ingestion run" plan from the original master plan is abandoned. With
  the diff engine handling ongoing updates and the selection UI driving
  ingestion on demand, the credential's "live" window is no longer
  bounded by a single bulk run. Periodic rotation on a calendar schedule
  (e.g., quarterly) is the appropriate replacement.
- **Diff trigger:** the master plan's "manual via Railway CLI" becomes
  "Save button in the UI, with CLI as fallback" per Q6.

### What this does NOT change

- Vertex AI for vision calls — locked, unchanged
- The four content collections (`rf_coaching_transcripts`,
  `rf_reference_library`, `rf_internal_education`, `rf_published_content`)
  — locked, unchanged. The registry is a *separate* metadata-only
  collection that sits alongside them.
- FKSP-as-pilot — locked, unchanged
- One-off Railway worker job topology — locked, unchanged. The worker
  just gets invoked from a different trigger (the UI Save button).

---

## Consequences

### Immediate (this build)

1. The ingester package gains new modules: `registry.py` (CRUD on the
   `rf_library_index` collection), `diff.py` (the diff engine), and a
   library-management CLI subcommand.
2. A one-time backfill script populates the registry for the existing
   9,224 `rf_coaching_transcripts` chunks under the
   `historical_coaching_transcripts` library.
3. The folder-selection UI (per ADR-004) becomes a critical-path feature.
   Built after first inventory walk so it can be designed against real
   folder-tree data.
4. The first ingestion run (FKSP pilot) is driven by the UI for the
   second pilot onwards; the very first one may be CLI-driven against
   hardcoded folder IDs to bootstrap.
5. The `PROGRAMS` dict in `config.py` becomes a starter set the UI ships
   with, not the source of truth.

### Future

1. As content libraries grow, the agent's self-description quality
   improves automatically — no code changes needed, just registry updates.
2. New libraries can be added by non-engineers through the UI without
   touching code.
3. When the Clinical tier is populated for the first time (PHI dataset
   arrives), ADR-001's dedicated-drive pattern is reactivated for that
   tier specifically. The registry already supports it.

---

## Open items deferred to other ADRs

- **ADR-003** — Canva dedup mechanism (perceptual hashing, version
  handling, Canva API as canonical source)
- **ADR-004** — Folder-selection UI design (the actual UI layout, the
  flag-and-confirm interaction for sensitive drives, the build sequencing)

---

*ADR locked 2026-04-11 at the close of the Phase A design pass. The
registry, diff engine, and library-aware agent layer are now first-class
parts of the build, not afterthoughts.*
