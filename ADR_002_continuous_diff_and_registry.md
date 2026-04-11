# ADR 002 — Continuous diff ingestion + library registry + library-aware agents

**Date:** 2026-04-11
**Status:** PROPOSED — design deferred to next session
**Proposer:** Daniel Smith
**Context:** Mid-session conversation during GCP foundation setup, after
the dedicated AI Ingestion Source drive was decided in ADR-001.

---

## Status note

This ADR is a STUB. The full design pass (forces, alternatives,
consequences, open questions) is deferred to the next session so it
gets the careful treatment it deserves. This file exists to capture
the core idea and its components so they don't evaporate between
sessions.

---

## The proposal in one paragraph

Instead of treating the RAG ingester as a one-shot bulk loader (the
master plan's Model A), build it as a continuously-updated content
management system. Three connected components: (1) a **library
registry** that knows what content exists in the AI Ingestion Source
drive — useful for the human team as a content inventory tool, not
just for the AI; (2) a **diff engine** that detects new and changed
files since the last run and only processes the deltas; (3)
**library-aware agents** that know which collections they have access
to, how fresh each is, what date range it spans, and can reference
this in responses ("my most recent FKSP content is from April 2026").

---

## Why this came up

Daniel raised it in response to the Step 5 (Drive sharing) discussion:

> "We need a way to keep track of what is in various libraries anyway.
> This could easily be adapted to do so. And we have weekly calls that
> are constantly being added to the drive so we could create an updater
> that would continuously update the diff? And inform the various
> clones of what libraries they have, etc. thoughts?"

The trigger was the realization that the master plan's bulk-ingestion
framing doesn't handle the realities of how RF actually generates
content:

- Weekly coaching calls are added to Drive constantly. The bulk
  ingestion model would leave them stale until someone remembered to
  re-run the ingester.
- The team has 11 shared drives and content scattered across them.
  Nobody has a single source of truth on "what do we actually have
  published about gut health" or "which call covered AMH labs."
- The Nashat agents currently have no awareness of how fresh their
  collections are. They can't say "my most recent content is from X"
  or "I'm sparse on Y, you should check the team."

The library registry solves all three at once. The diff engine makes
the registry maintainable without human effort. The library-aware
agents turn the registry into a user-facing capability.

---

## Three components (sketch)

### 1. Library registry (`ingester/registry.py`)

A separate ChromaDB collection (or SQLite table — TBD) called
`rf_library_index` holding one record per file in the AI Ingestion
Source drive. Fields per record:

- `drive_file_id` — the Google Drive file ID, primary key
- `name`, `path` — human-readable identifiers
- `mime_type`, `size`, `modified_time`, `md5_checksum` — Drive metadata
- `ingestion_status` — `unprocessed | processing | done | failed | skipped`
- `chunk_count` — how many chunks this file produced
- `last_ingested_at` — timestamp of last successful processing
- `source_library` — which conceptual library this file belongs to
  (e.g., `fksp_curriculum`, `weekly_coaching_calls`, `blog_posts`)
- `target_collection` — which ChromaDB collection it was written to
  (e.g., `rf_internal_education`, `rf_published_content`)
- `topics` — pipe-delimited tags pulled from chunk-level analysis
- `error` — any error message from the last run

This is the **single source of truth for "what content do we have"**
and is queryable both by the ingester (to skip already-processed
files) and by human team members (to answer questions like "do we
have anything on X").

### 2. Diff engine (`ingester/diff.py`)

Walks the AI Ingestion Source drive (or specific subfolders) using
the existing `drive_client.py`, compares each file against the
registry, and emits four lists:

- `new_files` — present in Drive, not in registry → ingest
- `modified_files` — present in both, but `modified_time` or
  `md5_checksum` differs → re-ingest (and mark old chunks for cleanup)
- `deleted_files` — present in registry, not in Drive → mark in
  registry as deleted, optionally remove chunks (TBD)
- `unchanged_files` — present in both, no changes → skip

The diff engine becomes the first step of every ingestion run.
Bulk first-time ingestion is just "everything is in the new_files
list because the registry is empty." Continuous updates are "new_files
and modified_files contain only the deltas."

### 3. Library-aware agents (YAML config update)

Each agent's YAML gets a new section (sketch — to be designed in
detail next session):

```yaml
libraries:
  - name: fksp_curriculum
    collection: rf_internal_education
    filter: {program: fksp}
    description: "The 12-week Fertility Kickstart Program curriculum"
  - name: weekly_coaching_calls
    collection: rf_internal_education
    filter: {asset_type: coaching_call}
    description: "Weekly group coaching call recordings"
```

At query time, the agent reads the registry to compute live
statistics for each library (chunk count, freshness, date range,
top topics) and can incorporate them into its responses. Examples
of new capabilities this enables:

- "I have 47 weekly coaching calls indexed, the most recent from
  April 8, 2026. Want me to focus on a specific date range?"
- "My FKSP curriculum content is comprehensive, but my coaching
  call coverage of pre-2026 calls is sparse — let me know if you
  need older context and I'll flag it for the team."
- Sales agent: "I have 23 published blog posts and 87 IG posts
  available — what topic are you exploring?"

---

## Implications for previously-locked decisions

This proposal **does not** invalidate the locked decisions from this
session, but it does shift two of them:

- **Bulk-vs-sync (was Model A bulk-only):** becomes "bulk for first-
  time setup, diff-incremental for ongoing updates." Both modes
  coexist.
- **Service account credential lifetime:** the "rotate after each
  ingestion run" compensating control proposed earlier doesn't fit
  cleanly with continuous diff ingestion (you can't rotate after every
  weekly call). Instead, the credential lifetime is bounded by the
  dedicated AI Ingestion Source drive's scope (per ADR-001), which is
  the actually-meaningful security boundary anyway. Periodic rotation
  on a calendar schedule (e.g., quarterly) is still appropriate.

The Vertex AI decision, the dedicated drive decision, the FKSP-pilot
decision, and the one-off-Railway-job topology are **all unaffected**.
The Railway worker still runs as a one-off job — it just gets invoked
more often (e.g., weekly) and reads the registry to know what to do.

---

## Open questions for next session

Things we need to design before building:

1. **Where does the registry physically live?** ChromaDB collection
   (consistent with existing storage), SQLite table on the Railway
   volume (better for relational queries), or both (registry in
   SQLite, with a small mirror collection in Chroma for AI-side
   visibility)?

2. **Diff trigger mechanism.** Manual via Railway CLI (matches the
   one-off job topology), scheduled via Railway cron (more automatic
   but requires committing to a polling schedule), or webhook-based
   via Drive API push notifications (most efficient but adds
   complexity)?

3. **Deletion handling.** When a file disappears from Drive, do we
   (a) mark it deleted in the registry but keep its chunks in Chroma,
   (b) hard-delete the chunks, or (c) flag for human review? Each
   has different implications for audit trail and accidental deletion
   recovery.

4. **Registry-as-content-management-tool UX.** Daniel said the
   registry should help the human team track what's in their content
   libraries. Does that mean a new admin UI page that exposes the
   registry as a searchable inventory? A read-only export to a Google
   Sheet? Both?

5. **Library taxonomy.** What are the actual "libraries" we want
   the agents to know about? "FKSP curriculum" is one. "Weekly
   coaching calls" is another. But are blog posts one library, or
   split by topic? Are IG posts one library, or split by content
   pillar? This is a content-architecture decision Daniel should
   drive.

6. **Versioning of modified files.** When a file is re-ingested
   because it changed, do we keep the old chunks (for historical
   "what did we used to say about X") or replace them entirely
   (for "always reflect current state")? For coaching calls this
   probably doesn't matter (a call is a call). For evolving content
   like blog posts or course slides, it matters more.

7. **Registry as a diff against EXISTING ChromaDB content.** The
   current `rf_coaching_transcripts` collection has 9,224 chunks
   with NO entries in the registry. Do we backfill the registry from
   the existing Chroma data? Or treat the registry as forward-looking
   only and accept that pre-registry content is opaque to library
   awareness?

---

## Next-session agenda for ADR-002

1. Daniel reviews this stub and reacts — push back, refine, expand,
   or reject any part
2. Walk through the seven open questions and make calls on each
3. Promote ADR-002 from PROPOSED to DECIDED (or split into multiple
   ADRs if it grows too big)
4. Update the master `HANDOVER_INTERNAL_EDUCATION_BUILD.md` to
   reflect the registry/diff/library-awareness layer as a first-
   class part of the build, not an afterthought
5. Update `ingester/main.py` CLI to expose the new commands:
   `inventory --diff`, `registry --search`, `registry --status`,
   `ingest --diff`, etc.
6. THEN start building (after ADR-001's drive setup is also done)

---

*ADR stub written 2026-04-11 at the close of the GCP setup session.
Full design pass deferred to next session. The proposal came from
Daniel and reflects a meaningfully bigger-and-better system than the
master plan's bulk-ingestion framing.*
