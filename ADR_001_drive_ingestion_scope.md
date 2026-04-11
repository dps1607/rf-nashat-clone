# ADR 001 — Drive ingestion source scope: behavioral vs. credential-level scoping

**Date originally decided:** 2026-04-11
**Date rescoped:** 2026-04-11 (same day, Phase A design pass)
**Status:** DECIDED (rescoped — see "Rescope" section below)
**Deciders:** Daniel Smith (founder, RF / RH)
**Context:** Setting up the Google Drive service account for the
RF internal education + published content RAG build.

---

## Decision (final, after rescope)

The Reimagined Fertility RAG ingester uses **behavioral scoping** as the
primary mechanism for controlling what content the system actually
processes from Google Drive — not credential-level scoping.

Concretely:

- The service account `rf-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`
  is granted **Viewer** access to the relevant subset of the existing
  Reimagined Fertility Workspace Shared Drives (see "Shared drives in
  scope" below).
- The ingester only ever processes folders that the user has **explicitly
  checked in the folder-selection UI** (per ADR-004). The credential is
  broad; the system's *behavior* is tightly scoped.
- Sensitive drives (`8. Labs`, `4. Finance`, `5. HR & Legal`) are visible
  in the UI but **flagged as `do_not_ingest`**. Checking a flagged folder
  requires an explicit confirmation step. This prevents the obvious
  foot-gun where someone accidentally ingests financial or PHI-adjacent
  content through the non-PHI credential.
- The original "dedicated `RF AI Ingestion Source` Shared Drive" approach
  is **deferred and reserved for the Clinical tier**. When the first PHI
  dataset is formally brought into the system, a separate dedicated drive
  with its own scoped service account credential will be created for it.
  Until then, the dedicated-drive pattern is not in use.

---

## Rescope

This ADR was originally written and decided earlier on 2026-04-11 to
require a dedicated `RF AI Ingestion Source` Shared Drive populated with
Drive shortcuts to source content. That decision was rescoped during the
Phase A design pass later the same day.

### What changed

The original ADR was written before the folder-selection UI (ADR-004) was
designed. The dedicated drive existed to solve the over-sharing problem:
granting the service account access to a business-function Shared Drive
gives it read access to everything in that drive, including content the
RAG should not ingest.

The folder-selection UI solves the same problem differently. If the
service account has read access to many drives but **the ingester only
processes folders the user has explicitly checked in the UI**, the
over-sharing concern shifts from "what can the credential reach" to "what
does the system actually do with what the credential can reach." The
credential is broad, but the behavior is tightly scoped — and the user
sees and controls every scoping decision through the UI.

For non-PHI content, this is a good tradeoff: it eliminates 30-60 minutes
of `info@` Workspace work per build, removes the risk of the dedicated
drive falling out of sync with the source content, makes new content
visible in the UI the moment it lands in any Shared Drive, and centralizes
"what's in the RAG" in one user-facing place.

For PHI content, it is **not** a good tradeoff. PHI demands credential-level
isolation, not behavioral scoping. The dedicated-drive pattern is the right
answer for PHI — it just is not the right answer for everything.

### The hybrid model that resulted

| Tier | Scoping mechanism |
|------|-------------------|
| Reference, Paywalled, Published | Behavioral scoping via the selection UI; broad credential, narrow behavior |
| Clinical (PHI) | Credential-level scoping via dedicated `RF Clinical Source` drive with its own service account credential, when the first PHI dataset arrives |

The Clinical tier has no libraries today. When it does, the dedicated-drive
pattern from the original ADR is reactivated *for that tier specifically*.
The non-PHI build never adopts it.

### Why this is honest about the security tradeoff

The non-PHI credential reaches more drives than it would have under the
original ADR. A clinic auditor's question "what could your AI service
account theoretically read" gets a worse answer ("the in-scope subset of
the Reimagined Fertility Shared Drives") than the original answer ("one
named drive"). This is a real cost.

The mitigation is twofold:

1. **The selection UI is the real boundary.** The system never processes
   anything that has not been explicitly checked. The UI's selection state
   is itself auditable: at any moment we can produce a list of "every folder
   the RAG is currently configured to ingest from," with names, paths,
   library assignments, and the date each was last selected.
2. **PHI does not flow through this credential.** When PHI exists, it
   exists in the Clinical tier behind a separate credential. The non-PHI
   credential's broader reach is acceptable precisely because the
   highest-sensitivity content category never touches it.

---

## Shared drives in scope

Per the Phase A design pass decision, **the folder-selection UI shows all
twelve Reimagined Fertility Shared Drives** so the user can pick at
click-time rather than guessing upfront which drives are RAG-relevant.

The service account is therefore granted Viewer at the drive level on all
twelve. Drives marked **flagged** are visible in the UI but require
confirmation before any folder inside them can be checked.

| # | Drive | Flagged? | Why |
|---|-------|----------|-----|
| 0 | `0-Shared Drive Content Outline` | No | Index/metadata for friendly drive names in the UI |
| 1 | `1. Operations` | No | Internal ops; user decides per folder whether anything is RAG-relevant |
| 2 | `2. Sales & Relationships` | No | Primary source for FKSP/FF/Detox program content and coaching calls |
| 3 | `3. Marketing` | No | Primary source for blogs, lead magnets, masterclasses, IG content |
| 4 | `4. Finance` | **Yes** | Sensitive financial data, no RAG content expected |
| 5 | `5. HR & Legal` | **Yes** | Sensitive personnel and legal data, no RAG content expected |
| 6 | `6. Ideas, Planning & Research` | No | May feed `external_research` library |
| 7 | `7. Supplements` | No | Protocol references; may feed `external_research` |
| 8 | `8. Labs` | **Yes** | PHI-adjacent. Future Clinical tier content. Will eventually move to a dedicated drive with its own credential. |
| 9 | `9. Biocanic` | No | User's call; flag at click-time if appropriate |
| 10 | `10. External Content` | No | Source material for `external_research` and reference libraries |
| 11 | `11. RH Transition` | No | User's call; flag at click-time if appropriate |

The flag list can be edited through the UI by the admin user — drives can
be flagged or unflagged as understanding of what they contain evolves. The
initial flags above are conservative defaults.

---

## Original context (preserved)

Daniel originally proposed sharing the entire `2. Sales & Relationships`
drive at drive level on the basis that drive-level access is operationally
simpler than folder-by-folder sharing. Investigation via screenshot
revealed that the Workspace's Shared Drives are organized by **business
function** (Operations, Sales, Marketing, Finance, Labs, etc.), not by
AI-vs-human content boundaries. This means drive-level access on any
business-function drive over-shares significantly relative to a folder-
specific scoping approach.

The decisive factor in the original ADR was Daniel's explicit answer to
a direct question:

> "We do not currently have PHI. But we want to be able to add it in the
> future."

This reframed the architecture decision from "what's secure enough for
today's content" to "what discipline does today's design need so that
when PHI arrives, we don't have to re-architect."

The original ADR concluded: create a dedicated drive now, populate it
with shortcuts, scope the service account to only that drive.

The rescope concluded: behavioral scoping via the UI is good enough for
non-PHI today, the dedicated-drive pattern is held in reserve for PHI
when it arrives. **The original ADR's reasoning is still correct for
PHI.** It is just no longer being applied to non-PHI content.

---

## Forces (post-rescope)

### For behavioral scoping (chosen path for non-PHI)

- No `info@` Workspace work to create or maintain a dedicated drive
- No risk of the dedicated drive falling out of sync with source content
- New content appears in the UI the moment it's added to any in-scope drive
- The selection UI is the single source of truth for "what's in the RAG,"
  and it's a user-facing surface — not a hidden config file
- Operationally simple: the user clicks folders, the system processes
  what's clicked, nothing else
- The flag-and-confirm pattern protects against the obvious accidents

### Against behavioral scoping (the cost we're accepting for non-PHI)

- The credential reaches more drives than necessary; a clinic auditor's
  "what can your AI read" question has a worse answer
- The protection is in code, not in Google's permissions system; if the
  ingester has a bug that ignores the selection state, the credential
  could be used to read content that should not be read
- Auditors prefer credential-scoped answers because they're enforced by
  Google IAM, not by the application layer

### For credential-level scoping (the original ADR; now reserved for PHI)

- One named, narrowly-scoped drive: easy to explain in security
  questionnaires
- Permission enforcement at the Google IAM layer, not at the application
  layer
- The right answer for PHI

### Against credential-level scoping for non-PHI

- Real ongoing operational cost (drive maintenance, shortcut sync, library
  proliferation requires new shortcuts each time)
- Friction every time content moves or gets added
- For non-PHI content, the security benefit doesn't justify the cost

---

## Consequences

### Immediate

- The Phase B "create dedicated drive and populate shortcuts" work from
  the original ADR is **cancelled**. The new Phase B is just "share the
  twelve in-scope drives with the service account."
- The `ingester/config.py` `PROGRAMS` dict's hardcoded folder IDs become
  a starter seed list for the UI, not the source of truth. The UI's
  selection state in the registry is the source of truth.
- The folder-selection UI (ADR-004) becomes a critical-path feature for
  this build, not an optional admin nicety.

### When PHI arrives

- A new dedicated Shared Drive (e.g., `RF Clinical Source`) is created
  by `info@` in the same Workspace
- A second service account credential is created scoped only to that
  drive: `rf-clinical-ingester@rf-rag-ingester-493016.iam.gserviceaccount.com`
  (or a separate GCP project entirely if the BAA paperwork requires it)
- The ingester gains a separate code path for Clinical tier libraries
  that uses the new credential
- The non-PHI credential never touches PHI; the PHI credential never
  touches non-PHI
- ADR-001's *original* reasoning is now applicable, scoped to PHI only

### For vendor security questionnaires

- Today's answer: "Our AI ingester reads from the in-scope subset of our
  internal Workspace Shared Drives. Specific folders are explicitly
  selected by an authorized admin through a UI; the system never processes
  unselected content. We can produce an audit log of every folder the
  ingester is currently configured to read."
- Tomorrow's answer (when PHI exists): "Our PHI handling uses a separate,
  dedicated Shared Drive with its own service account credential, scoped
  only to that drive. PHI never flows through the same credential as
  non-PHI content."

---

## Status of related decisions

- Vertex AI for vision calls: locked (separate decision, see master plan)
- Service account scope: read-only, drive-level Viewer on the twelve
  in-scope drives
- Service account credential rotation: quarterly calendar-based rotation
  (the "rotate after every ingestion run" idea from earlier sessions is
  abandoned because it doesn't fit the diff-incremental model from
  ADR-002)
- Folder-selection UI: see ADR-004 for the design
- Continuous diff and registry: see ADR-002

---

*ADR originally written and decided 2026-04-11 morning. Rescoped 2026-04-11
afternoon during Phase A design pass after the folder-selection UI emerged
as a better mechanism for non-PHI scoping. The original "dedicated drive"
discipline is preserved and reserved for the eventual Clinical tier.*
