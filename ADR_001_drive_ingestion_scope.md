# ADR 001 — Drive ingestion source scope: dedicated drive vs. sharing existing folders

**Date:** 2026-04-11
**Status:** Decided
**Deciders:** Daniel Smith (founder, RF / RH)
**Context:** Setting up the Google Drive service account for the
rf_internal_education + rf_published_content RAG build.

---

## Decision

The Reimagined Fertility RAG ingester will read source content from a
**dedicated Google Workspace Shared Drive** named `RF AI Ingestion Source`
(or similar), NOT from the existing business-function Shared Drives
(`2. Sales & Relationships`, `3. Marketing`, etc.).

The dedicated drive will use **Drive shortcuts** to point at content
that physically lives in other drives (e.g., FKSP course folders in
`2. Sales & Relationships`). This is non-destructive — original files
stay where they are, owned by the original drive — and self-updating,
so adding a new lesson to the original folder propagates automatically
to the AI-accessible view.

The Google Cloud service account `rf-ingester@rf-rag-ingester.iam.gserviceaccount.com`
will be granted **Viewer** at the **drive level** of `RF AI Ingestion
Source` only. It will NOT be granted access to any other Shared Drive
or any other folder in the Workspace.

---

## Context

Daniel proposed sharing the entire existing Shared Drive (most likely
`2. Sales & Relationships`, which contains the FKSP course content)
with the service account at drive level, on the basis that:
- The build will eventually source many folders, not just FKSP
- Folder-by-folder sharing is operationally tedious
- Sharing once at drive level is much simpler going forward

Investigation via screenshot revealed that the Workspace's Shared
Drives are organized by **business function** (Operations, Sales,
Marketing, Finance, Labs, etc.), not by AI-vs-human content boundaries.
This means drive-level access on any business-function drive over-shares
significantly: granting Viewer on `2. Sales & Relationships` would give
the service account read access to client enrollment records, sales
pipeline data, and any other operational content in that drive — far
beyond the course materials we actually want to ingest.

The decisive factor was Daniel's explicit answer to a direct question:
**"We do not currently have PHI. But we want to be able to add it in
the future."**

This reframes the architecture decision from "what's secure enough for
today's content" to "what discipline does today's design need so that
when PHI arrives, we don't have to re-architect."

---

## Forces

### For drive-level access on the existing business-function drive

- Operational simplicity: one share, never touched again
- Matches Daniel's stated desire to use "many many folders"
- Today's content has no PHI, so the immediate risk is bounded

### Against drive-level access on the existing business-function drive

- Drives are organized for humans by business function, not for AI
  scope boundaries — the "blast radius" is the entire business
  function, not the intended subset of content
- When a clinic vendor security questionnaire asks "what data can the
  AI service account reach," the answer would be "everything in the
  Sales & Relationships drive, including future additions we don't
  control" — that's a hard sell to a clinic auditor
- When PHI is eventually added to the system, it cannot be added to a
  business-function drive without immediately leaking it to the
  ingester. Either the architecture has to change at that moment, or
  PHI flows through a credential it shouldn't reach.
- Google's HIPAA BAA covers specific GCP services and Workspace
  surfaces. A dedicated drive whose entire purpose is "AI-accessible
  source content under our security discipline" is straightforward
  to BAA-cover. A business-function drive with mixed content is not.
- Periodic audit becomes impossible: nobody knows what's been added
  to the Sales drive in the last quarter, so nobody can confidently
  say what the ingester has been able to read.

### For the dedicated drive (chosen path)

- Single, named, auditable scope: "the AI service account can read
  exactly the contents of this one drive, here is the list, here is
  the audit log of additions"
- PHI can be added in the future to specific subfolders inside the
  dedicated drive without changing the security model — the drive's
  entire purpose is already aligned with PHI discipline
- Drive shortcuts make the operational cost cheap and non-destructive:
  original files stay in their business-function drives, the dedicated
  drive is just a curated view
- Matches the discipline a B2B2C clinic-pitched system actually needs
  for vendor security reviews

### Against the dedicated drive

- Upfront work: 30-60 minutes of `info@` clicking to create the drive
  and add shortcuts to the right source folders
- Adds a layer of indirection — humans editing the original files
  must remember the AI is reading them via the dedicated drive
- New content categories require updating the dedicated drive's
  shortcut tree (small ongoing maintenance, but well under the cost
  of folder-by-folder sharing)

---

## Consequences

### Immediate (this build)

- Step 5 of `GCP_ORG_SETUP_FOR_INFO.md` needs to be rewritten to share
  the new dedicated drive (at drive level), not the existing drives
  (at folder level)
- A separate walkthrough will be written for `info@` covering: create
  the new Shared Drive, populate it with shortcuts to source content,
  add the service account as Viewer
- The `ingester/config.py` `PROGRAMS` dict will need its
  `drive_folder_id` values updated to point at the dedicated-drive
  paths instead of the original FKSP/TFF/Detox folder IDs (these
  values are wrong as currently committed)
- The session-by-session build plan in
  `HANDOVER_INTERNAL_EDUCATION_BUILD.md` is unaffected — the inventory
  pass, pilot, ingestion sessions all work the same way against the
  dedicated drive

### Future (when PHI arrives)

- PHI can be added to specific subfolders inside the dedicated drive
  (NOT via shortcut from a business-function drive — directly placed
  in the dedicated drive) once the appropriate Google BAA is in place
- The BAA covers the dedicated drive cleanly because the drive's
  entire scope is aligned with HIPAA discipline
- The ingester pipeline does not need to change to handle PHI — the
  same vision/embedding/storage path applies, with the addition of
  PHI-handling discipline at the chunk-metadata layer (e.g., redaction
  flags, audit logging on retrieval)

### Long-term (vendor security reviews, clinic pitches)

- The "what can your AI access" answer is one sentence: "the contents
  of one named Shared Drive, here's the audit log"
- The "how do you prevent the AI from seeing PHI it shouldn't" answer
  is "the AI's entire source corpus is a dedicated drive that we
  curate; we don't share business-function drives with AI credentials"
- BAA paperwork applies cleanly to a single drive, not a sprawl of
  shared business-function drives

---

## Status of related decisions

- Vertex AI for vision calls: locked (separate decision, see master plan)
- Service account scope: read-only (Drive Viewer role only)
- Service account credential rotation: planned for after each
  ingestion run (because Model A bulk ingestion means the credential's
  "live" window is short)
- Bulk ingestion (Model A) vs continuous sync (Model B): Model A
  locked

---

*ADR written 2026-04-11 at the close of the GCP setup session.
The dedicated drive setup itself is deferred to the next session.*
